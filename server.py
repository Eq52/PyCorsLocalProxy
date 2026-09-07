# -*- coding: utf-8 -*-
"""
cors-local-proxy · 本地 CORS 代理核心
=====================================
两个独立的本地 HTTP 服务（均只监听 127.0.0.1）：

1. ProxyServer —— 数据面代理（对标 cors.sh 的 proxy.cors.sh）
   规则：http://127.0.0.1:<port>/<目标完整URL>
   - OPTIONS 预检一律短路返回 200（不转发、不计量），与 cors.sh 行为一致
   - 实际响应统一覆盖为 Access-Control-Allow-Origin: *
   - 转发时剥离 hop-by-hop / cookie / origin / referer / sec-* 等浏览器上下文头
   - 响应流式回写；上游 gzip/deflate 自动解压后按 chunked 回写
   - strip 上游 set-cookie；剥离上游自带 CORS 头再叠加自己的

2. MockServer —— 本地 mock 测试端点（对标 mock.cors.sh）
   /no-cors       无任何 CORS 头 → 浏览器直连必被拦
   /allow-all     Access-Control-Allow-Origin: * → 直连即成功
   /wrong-origin  ACAO 指向别的域 → 直连仍被拦
   /echo          回显 method/headers/body（ACAO *）

日志通过注入的 log_fn(dict) 回调交还给 GUI。
"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import requests

try:  # 测试页模板（与 GUI 打包在一起）
    from test_page import TEST_PAGE_HTML
except Exception:  # pragma: no cover
    TEST_PAGE_HTML = "<h1>test_page.py missing</h1>"

VERSION = "1.0.1"
USER_AGENT = f"cors-local-proxy/{VERSION}"

# ---------------------------------------------------------------- 头处理表
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "trailers", "transfer-encoding", "upgrade",
    "proxy-connection", "host", "content-length",
}
# 请求转发时剥离：匿名化 + 去浏览器上下文（sec-*），避免上游风控误判
STRIP_REQUEST = HOP_BY_HOP | {
    "cookie", "cookie2", "origin", "referer",
    "upgrade-insecure-requests",
    "sec-fetch-mode", "sec-fetch-site", "sec-fetch-dest", "sec-fetch-user",
    "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform",
}
# 响应回写时剥离：框架头 + 我们要重写的 CORS 头 + cookie
STRIP_RESPONSE = HOP_BY_HOP | {
    "content-encoding", "set-cookie", "set-cookie2",
    "access-control-allow-origin", "access-control-allow-credentials",
    "access-control-expose-headers", "access-control-allow-methods",
    "access-control-allow-headers", "access-control-max-age",
    "strict-transport-security",
    # 调试头由本代理自行生成（借鉴 cors-anywhere），上游同名头一律丢弃
    "x-request-url", "x-final-url",
}

# 共享连接池（urllib3 线程安全）
SESSION = requests.Session()


def _log(fn, **kw):
    if fn:
        try:
            fn(dict(kw, time=time.strftime("%H:%M:%S")))
        except Exception:
            pass


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = 300  # 客户端连接读超时，防止僵尸线程

    # ---- 静音默认日志 ----
    def log_message(self, fmt, *args):  # noqa: D401
        pass

    @property
    def app(self) -> "ProxyServer":
        return self.server  # type: ignore[return-value]

    # ---------------------------------------------------------------- 路由
    def do_OPTIONS(self):  # noqa: N802
        """预检短路：200 + 空体 + 按请求反射放行的方法/头（cors.sh 同款行为）"""
        t0 = time.time()
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        req_method = self.headers.get("Access-Control-Request-Method") \
            or "GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS"
        self.send_header("Access-Control-Allow-Methods", req_method)
        req_headers = self.headers.get("Access-Control-Request-Headers")
        if req_headers:
            self.send_header("Access-Control-Allow-Headers", req_headers)
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Content-Length", "0")
        self.end_headers()
        _log(self.app.log_fn, kind="proxy", method="OPTIONS", url="(preflight 短路)",
             status=200, size=0, dur_ms=int((time.time() - t0) * 1000), note="preflight")

    def do_GET(self):  # noqa: N802
        self._route()

    def do_HEAD(self):  # noqa: N802
        self._route()

    def do_POST(self):  # noqa: N802
        self._route()

    def do_PUT(self):  # noqa: N802
        self._route()

    def do_PATCH(self):  # noqa: N802
        self._route()

    def do_DELETE(self):  # noqa: N802
        self._route()

    def _route(self):
        path = self.path
        if path in ("/", "/index.html", "/playground") and self.command in ("GET", "HEAD"):
            self._serve_page()
            return
        if path == "/favicon.ico":
            self._serve_icon()
            return
        if path == "/health":
            self._send_json(200, {"ok": True, "service": "cors-local-proxy",
                                  "version": VERSION, "mock_base": self.app.mock_base})
            return
        self._proxy()

    # ---------------------------------------------------------------- 内置页
    def _serve_page(self):
        html = (TEST_PAGE_HTML
                .replace("__MOCK_BASE__", self.app.mock_base)
                .replace("__PROXY_BASE__", self.app.base_url))
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _serve_icon(self):
        icon = getattr(self.app, "icon_bytes", None)
        if not icon:
            self._send_json(404, {"error": "no icon"})
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/x-icon")
        self.send_header("Content-Length", str(len(icon)))
        self.send_header("Cache-Control", "max-age=86400")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(icon)

    def _send_json(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    # ---------------------------------------------------------------- 代理
    def _read_body(self):
        te = (self.headers.get("Transfer-Encoding") or "").lower()
        if "chunked" in te:
            return None  # 浏览器极少用；返回 None → 411
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return b""
        return self.rfile.read(n)

    def _proxy(self):
        t0 = time.time()
        target = self.path[1:]
        parts = urlsplit(target)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            self._send_json(400, {
                "error": "invalid target",
                "usage": "把目标 URL 直接接在本服务后面：http://127.0.0.1:<port>/<目标URL>",
                "example": self.app.base_url + "/https://api.github.com/zen",
            })
            _log(self.app.log_fn, kind="proxy", method=self.command, url=target or "(空)",
                 status=400, size=0, dur_ms=0, note="无效目标")
            return

        body = self._read_body()
        if body is None:
            self._send_json(411, {"error": "Length Required",
                                  "message": "本代理不支持 chunked 请求体（浏览器常规请求不受影响）"})
            return

        up_headers = {}
        for k, v in self.headers.items():
            if k.lower() in STRIP_REQUEST:
                continue
            # 同名头只保留第一个（requests 的 dict 语义）
            if k.lower() not in {kk.lower() for kk in up_headers}:
                up_headers[k] = v
        # 保证可解压的压缩协商（urllib3 自动解压 gzip/deflate）
        for k in list(up_headers):
            if k.lower() == "accept-encoding":
                del up_headers[k]
        up_headers["Accept-Encoding"] = "gzip, deflate"
        up_headers.setdefault("User-Agent", USER_AGENT)
        up_headers.setdefault("Accept", "*/*")

        total = 0
        try:
            resp = SESSION.request(
                self.command, target, headers=up_headers,
                data=body if body else None,
                stream=True, allow_redirects=True, timeout=(10, 120),
            )
        except Exception as e:
            self._send_json(502, {
                "error": "upstream request failed",
                "detail": f"{type(e).__name__}: {e}",
                "target": target,
            })
            _log(self.app.log_fn, kind="proxy", method=self.command, url=target,
                 status="ERR", size=0, dur_ms=int((time.time() - t0) * 1000),
                 note=type(e).__name__)
            return

        try:
            status = resp.status_code
            self.send_response(status)
            expose = []
            for k, v in resp.headers.items():
                lk = k.lower()
                if lk in STRIP_RESPONSE:
                    continue
                self.send_header(k, v)
                if lk not in expose:
                    expose.append(lk)
            # 调试头（借鉴 cors-anywhere）：初始 URL / 重定向链 / 最终 URL
            self.send_header("X-Request-URL", target)
            for i, hop in enumerate(resp.history, 1):
                loc = hop.headers.get("Location", hop.url)
                self.send_header(f"X-CORS-Redirect-{i}", f"{hop.status_code} {loc}")
            self.send_header("X-Final-URL", resp.url)
            # JS 侧可读：暴露上游全部响应头名 + 我们的调试头
            for name in ("x-request-url", "x-final-url"):
                if name not in expose:
                    expose.append(name)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Expose-Headers", ", ".join(expose) or "*")

            no_body = (self.command == "HEAD") or (status in (204, 304))
            if no_body:
                if self.command == "HEAD":
                    clen = resp.headers.get("Content-Length")
                    if clen:
                        self.send_header("Content-Length", clen)
                self.end_headers()
                _log(self.app.log_fn, kind="proxy", method=self.command, url=target,
                     status=status, size=0,
                     dur_ms=int((time.time() - t0) * 1000),
                     note=(f"重定向×{len(resp.history)}" if resp.history else ""))
                return

            has_enc = bool(resp.headers.get("Content-Encoding"))
            clen = resp.headers.get("Content-Length")
            if has_enc or not clen:
                # 长度未知（解压后/无 CL）→ HTTP/1.1 chunked
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                try:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if chunk:
                            total += len(chunk)
                            self.wfile.write(f"{len(chunk):X}\r\n".encode("ascii")
                                             + chunk + b"\r\n")
                    self.wfile.write(b"0\r\n\r\n")
                except (BrokenPipeError, ConnectionResetError, OSError):
                    self.close_connection = True
            else:
                self.send_header("Content-Length", clen)
                self.end_headers()
                try:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if chunk:
                            total += len(chunk)
                            self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    self.close_connection = True
        finally:
            resp.close()
            _log(self.app.log_fn, kind="proxy", method=self.command, url=target,
                 status=status, size=total,
                 dur_ms=int((time.time() - t0) * 1000),
                 note=(f"重定向×{len(resp.history)}" if resp.history else ""))


class ProxyServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address=("127.0.0.1", 0), log_fn=None,
                 mock_base="", icon_bytes=None):
        self.log_fn = log_fn
        self.mock_base = mock_base
        if icon_bytes is None:  # 默认从同目录自动加载图标
            try:
                import os
                with open(os.path.join(
                        os.path.dirname(os.path.abspath(__file__)), "icon.ico"), "rb") as f:
                    icon_bytes = f.read()
            except Exception:
                icon_bytes = None
        self.icon_bytes = icon_bytes
        super().__init__(address, ProxyHandler)

    @property
    def base_url(self) -> str:
        host, port = self.server_address[:2]
        return f"http://{host}:{port}"


# ================================================================ mock 服务
class MockHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = 120

    def log_message(self, fmt, *args):  # noqa: D401
        pass

    @property
    def app(self) -> "MockServer":
        return self.server  # type: ignore[return-value]

    def _json(self, code, obj, acao=None):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        if acao:
            self.send_header("Access-Control-Allow-Origin", acao)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _handle(self):
        t0 = time.time()
        p = urlsplit(self.path).path
        label = f"mock{p}"

        if self.command == "OPTIONS":
            if p in ("/allow-all", "/echo"):
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                m = self.headers.get("Access-Control-Request-Method") or "*"
                h = self.headers.get("Access-Control-Request-Headers") or "*"
                self.send_header("Access-Control-Allow-Methods", m)
                self.send_header("Access-Control-Allow-Headers", h)
                self.send_header("Access-Control-Max-Age", "600")
                self.send_header("Content-Length", "0")
                self.end_headers()
            else:  # no-cors / wrong-origin：不给 CORS 头 → 预检失败
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()
            _log(self.app.log_fn, kind="mock", method="OPTIONS", url=label,
                 status=200, size=0, dur_ms=int((time.time() - t0) * 1000), note="preflight")
            return

        if p == "/":
            self._json(200, {"service": "mock", "endpoints":
                             ["/no-cors", "/allow-all", "/wrong-origin", "/echo"]}, acao="*")
        elif p == "/no-cors":
            self._json(200, {"ok": True, "endpoint": "no-cors",
                             "hint": "本端点不带任何 CORS 头，浏览器直连会被拦截"}, acao=None)
        elif p == "/allow-all":
            self._json(200, {"ok": True, "endpoint": "allow-all",
                             "hint": "ACAO:* —— 浏览器直连即可成功"}, acao="*")
        elif p == "/wrong-origin":
            self._json(200, {"ok": True, "endpoint": "wrong-origin",
                             "hint": "ACAO 指向别的域，浏览器直连仍会被拦截"}, acao="https://someone-else.example")
        elif p == "/echo":
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b""
            self._json(200, {"ok": True, "endpoint": "echo", "method": self.command,
                             "headers": dict(self.headers),
                             "body": raw.decode("utf-8", "replace")}, acao="*")
        else:
            self._json(404, {"error": "not found",
                             "endpoints": ["/no-cors", "/allow-all", "/wrong-origin", "/echo"]}, acao="*")

        _log(self.app.log_fn, kind="mock", method=self.command, url=label,
             status=200, size=0, dur_ms=int((time.time() - t0) * 1000), note="")

    do_GET = _handle
    do_HEAD = _handle
    do_POST = _handle
    do_PUT = _handle
    do_PATCH = _handle
    do_DELETE = _handle
    do_OPTIONS = _handle


class MockServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address=("127.0.0.1", 0), log_fn=None):
        self.log_fn = log_fn
        super().__init__(address, MockHandler)

    @property
    def base_url(self) -> str:
        host, port = self.server_address[:2]
        return f"http://{host}:{port}"
