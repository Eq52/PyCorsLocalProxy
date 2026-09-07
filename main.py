# -*- coding: utf-8 -*-
"""
CORS 本地代理 · GUI（tkinter）
双击 EXE / 运行 `python main.py` 即启动：
  - 本机代理服务 http://127.0.0.1:<自动端口>/<目标URL>
  - 本机 mock 测试服务
  - 浏览器测试页自动打开（可在设置关闭）
"""
from __future__ import annotations

import os
import queue
import sys
import threading
import time
import webbrowser
from datetime import timedelta
from urllib.parse import quote

import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from server import VERSION, MockServer, ProxyServer

APP_TITLE = "CORS 本地代理 · Local cors.sh"
BG = "#f4f5fa"
CARD = "#ffffff"
INK = "#1f2430"
DIM = "#7a8194"
ACCENT = "#6d28d9"
ACCENT_SOFT = "#ede9fe"
OK = "#16a34a"
LINE = "#e3e6ef"

# 界面中文字体：Windows 默认微软雅黑；其他平台自动挑选可用 CJK 字体
UI_FONT = "Microsoft YaHei UI"


def _pick_font(root: tk.Tk):
    """按平台挑一个存在的中文字体族（找不到则退回默认）。"""
    global UI_FONT
    import tkinter.font as tkfont
    try:
        fams = set(tkfont.families(root))
    except Exception:
        return
    for cand in ("Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC",
                 "Noto Sans CJK SC", "Noto Sans SC", "Source Han Sans SC",
                 "Sarasa Mono SC", "WenQuanYi Zen Hei", "WenQuanYi Micro Hei"):
        if cand in fams:
            UI_FONT = cand
            return


def resource_path(rel: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:,.0f} {unit}" if unit == "B" else f"{n:,.1f} {unit}"
        n /= 1024
    return f"{n:,.1f} GB"


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        _pick_font(root)
        root.title(APP_TITLE)
        root.geometry("880x640")
        root.minsize(780, 560)
        root.configure(bg=BG)
        try:
            root.iconbitmap(resource_path("icon.ico"))
        except Exception:
            pass

        # 状态
        self.log_q: "queue.Queue[dict]" = queue.Queue()
        self.t_start = time.time()
        self.req_count = 0
        self.bytes_total = 0
        self.proxy: ProxyServer | None = None
        self.mocksrv: MockServer | None = None
        self.base_url = ""
        self.mock_url = ""

        # 设置变量
        self.port_var = tk.StringVar(value="0")            # 0 = 自动
        self.auto_open_var = tk.BooleanVar(value=True)     # 启动后自动开测试页
        self.autoscroll_var = tk.BooleanVar(value=True)    # 日志自动滚动

        self._build()
        self._start_servers(0)
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.after(80, self._poll_log)
        root.after(1000, self._tick)
        if self.auto_open_var.get():
            root.after(600, lambda: webbrowser.open(self.base_url + "/"))

    # ================================================================ UI
    def _build(self):
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except Exception:
            pass
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", padding=(16, 7), font=(UI_FONT, 10))
        s.configure("TCheckbutton", background=BG)

        # ---------- 顶部 ----------
        head = tk.Frame(self.root, bg=CARD, highlightthickness=0)
        head.pack(fill="x")
        inner = tk.Frame(head, bg=CARD)
        inner.pack(fill="x", padx=18, pady=12)

        self.dot = tk.Canvas(inner, width=12, height=12, bg=CARD, highlightthickness=0)
        self.dot.grid(row=0, column=0, padx=(0, 8), pady=4)
        self._draw_dot("#d1d5db")  # 未启动灰
        tk.Label(inner, text="代理地址", bg=CARD, fg=DIM,
                 font=(UI_FONT, 10)).grid(row=0, column=1, padx=(0, 8))

        self.url_var = tk.StringVar(value="启动中…")
        self.url_entry = tk.Entry(inner, textvariable=self.url_var, state="readonly",
                                  font=("Consolas", 12), readonlybackground="#f7f7fd",
                                  fg=ACCENT, relief="flat", highlightthickness=1,
                                  highlightbackground=LINE, highlightcolor=ACCENT,
                                  width=42)
        self.url_entry.grid(row=0, column=2, sticky="ew")

        self.flash = tk.Label(inner, text="", bg=CARD, fg=OK,
                              font=(UI_FONT, 9))
        self.flash.grid(row=0, column=3, padx=(6, 0))

        btn_copy = tk.Button(inner, text="复制", command=self._copy_base,
                             bg=ACCENT, fg="white", activebackground="#5b21b6",
                             activeforeground="white", relief="flat", cursor="hand2",
                             font=(UI_FONT, 10), padx=14)
        btn_copy.grid(row=0, column=4, padx=(10, 0))
        btn_page = tk.Button(inner, text="打开测试页", command=self._open_page,
                             bg=ACCENT_SOFT, fg=ACCENT, activebackground="#ddd6fe",
                             activeforeground="#5b21b6", relief="flat", cursor="hand2",
                             font=(UI_FONT, 10), padx=14)
        btn_page.grid(row=0, column=5, padx=(8, 0))
        self.status_label = tk.Label(inner, text="", bg=CARD, fg=DIM,
                                     font=(UI_FONT, 9))
        self.status_label.grid(row=0, column=6, padx=(12, 0))
        inner.columnconfigure(2, weight=1)

        # ---------- 选项卡 ----------
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=14, pady=(10, 0))

        # --- Tab1 请求日志 ---
        tab1 = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab1, text=" 请求日志 ")
        bar = tk.Frame(tab1, bg=BG)
        bar.pack(fill="x", padx=6, pady=(6, 2))
        tk.Checkbutton(bar, text="自动滚动", variable=self.autoscroll_var,
                       bg=BG, fg=DIM, activebackground=BG,
                       font=(UI_FONT, 9)).pack(side="left")
        tk.Button(bar, text="清空日志", command=self._clear_log,
                  bg="white", fg=DIM, activeforeground=INK, relief="flat",
                  cursor="hand2", font=(UI_FONT, 9),
                  highlightbackground=LINE, highlightthickness=1, padx=10).pack(side="right")

        self.log_text = ScrolledText(tab1, bg="#0f1424", fg="#dfe4f3",
                                     insertbackground="#dfe4f3", relief="flat",
                                     font=("Consolas", 10), state="disabled",
                                     wrap="none", padx=12, pady=10)
        self.log_text.pack(fill="both", expand=True, padx=6, pady=(2, 8))
        for tag, cfg in {
            "dim":   {"foreground": "#6b7490"},
            "time":  {"foreground": "#6b7490"},
            "meth":  {"foreground": "#22d3ee", "font": ("Consolas", 10, "bold")},
            "ok":    {"foreground": "#4ade80", "font": ("Consolas", 10, "bold")},
            "warn":  {"foreground": "#fbbf24", "font": ("Consolas", 10, "bold")},
            "err":   {"foreground": "#f87171", "font": ("Consolas", 10, "bold")},
            "url":   {"foreground": "#c7cfe6"},
            "note":  {"foreground": "#8b93a7"},
            "sys":   {"foreground": "#a5b4fc", "font": ("Consolas", 10, "bold")},
            "sysok": {"foreground": "#4ade80", "font": ("Consolas", 10, "bold")},
        }.items():
            self.log_text.tag_configure(tag, **cfg)

        # --- Tab2 URL 转换器 ---
        tab2 = tk.Frame(self.nb, bg=CARD)
        self.nb.add(tab2, text=" URL 转换器 ")
        box = tk.Frame(tab2, bg=CARD)
        box.pack(fill="both", expand=True, padx=26, pady=24)

        tk.Label(box, text="把任意 URL 一键转成走本机代理的 URL", bg=CARD, fg=INK,
                 font=(UI_FONT, 13, "bold")).pack(anchor="w")
        tk.Label(box, text="在前端代码里直接使用生成的代理 URL，浏览器就不会拦截跨域请求。",
                 bg=CARD, fg=DIM, font=(UI_FONT, 10)).pack(anchor="w", pady=(2, 14))

        tk.Label(box, text="原始 URL", bg=CARD, fg=DIM,
                 font=(UI_FONT, 9)).pack(anchor="w")
        self.conv_in = tk.Entry(box, font=("Consolas", 11), relief="flat",
                                highlightthickness=1, highlightbackground=LINE,
                                highlightcolor=ACCENT)
        self.conv_in.pack(fill="x", ipady=7)
        self.conv_in.insert(0, "https://api.github.com/zen")

        tk.Label(box, text="代理 URL（自动生成）", bg=CARD, fg=DIM,
                 font=(UI_FONT, 9)).pack(anchor="w", pady=(14, 0))
        self.conv_out_var = tk.StringVar(value="")
        out = tk.Entry(box, textvariable=self.conv_out_var, font=("Consolas", 11),
                       relief="flat", state="readonly", readonlybackground="#f6f2ff",
                       fg=ACCENT, highlightthickness=1, highlightbackground=LINE)
        out.pack(fill="x", ipady=7)

        row2 = tk.Frame(box, bg=CARD)
        row2.pack(anchor="w", pady=14)
        tk.Button(row2, text="复制代理 URL", command=self._copy_conv,
                  bg=ACCENT, fg="white", activebackground="#5b21b6",
                  activeforeground="white", relief="flat", cursor="hand2",
                  font=(UI_FONT, 10), padx=14).pack(side="left")
        tk.Button(row2, text="在浏览器中打开", command=self._open_conv,
                  bg=ACCENT_SOFT, fg=ACCENT, activebackground="#ddd6fe",
                  activeforeground="#5b21b6", relief="flat", cursor="hand2",
                  font=(UI_FONT, 10), padx=14).pack(side="left", padx=(8, 0))
        tk.Button(row2, text="去测试页调试", command=self._open_page_with_conv,
                  bg="#eef2ff", fg="#4338ca", activebackground="#e0e7ff",
                  activeforeground="#3730a3", relief="flat", cursor="hand2",
                  font=(UI_FONT, 10), padx=14).pack(side="left", padx=(8, 0))

        tip = ("用法示例：\n"
               "  原始：  fetch(\"https://api.example.com/data\")     ← 被 CORS 拦截\n"
               "  代理：  fetch(\"http://127.0.0.1:端口/https://api.example.com/data\")\n"
               "即在原 URL 前面拼上代理地址 + \"/\"，其余不变。")
        tk.Label(box, text=tip, bg="#f8f8fe", fg=DIM, justify="left",
                 font=(UI_FONT, 9), highlightthickness=1,
                 highlightbackground=LINE, padx=14, pady=12).pack(fill="x", pady=(8, 0))

        self.conv_in.bind("<KeyRelease>", lambda e: self._update_conv())
        self._update_conv()

        # --- Tab3 设置 ---
        tab3 = tk.Frame(self.nb, bg=CARD)
        self.nb.add(tab3, text=" 设置 ")
        sb = tk.Frame(tab3, bg=CARD)
        sb.pack(fill="both", expand=True, padx=26, pady=24)

        tk.Label(sb, text="监听端口", bg=CARD, fg=INK,
                 font=(UI_FONT, 11, "bold")).pack(anchor="w")
        prow = tk.Frame(sb, bg=CARD)
        prow.pack(anchor="w", pady=6)
        tk.Radiobutton(prow, text="自动挑选空闲端口（推荐）", variable=self.port_var,
                       value="0", bg=CARD, activebackground=CARD).pack(side="left")
        tk.Radiobutton(prow, text="固定端口", variable=self.port_var,
                       value="8080", bg=CARD, activebackground=CARD).pack(side="left", padx=(16, 6))
        self.port_spin = tk.Spinbox(prow, from_=1024, to=65535, width=8,
                                    font=("Consolas", 10), relief="flat",
                                    highlightthickness=1, highlightbackground=LINE,
                                    buttonbackground="#eef")
        self.port_spin.delete(0, "end")
        self.port_spin.insert(0, "8080")
        self.port_spin.pack(side="left")
        self.port_spin.configure(command=lambda: self.port_var.set("8080"))
        self.port_spin.bind("<KeyRelease>", lambda e: self.port_var.set(self.port_spin.get()))
        tk.Button(sb, text="应用并重启服务", command=self._apply_port,
                  bg=ACCENT, fg="white", activebackground="#5b21b6",
                  activeforeground="white", relief="flat", cursor="hand2",
                  font=(UI_FONT, 10), padx=14).pack(anchor="w", pady=(2, 16))

        tk.Checkbutton(sb, text="启动后自动用浏览器打开测试页", variable=self.auto_open_var,
                       bg=CARD, activebackground=CARD).pack(anchor="w")

        tk.Label(sb, text="关于", bg=CARD, fg=INK,
                 font=(UI_FONT, 11, "bold")).pack(anchor="w", pady=(18, 4))
        about = ("CORS 本地代理 v" + VERSION + " —— 开源项目 cors.sh (gridaco/cors.sh) 的本地复刻版。\n"
                 "原理：浏览器同源策略阻止网页读取跨域响应；本工具在本机起一个转发服务，\n"
                 "代理响应统一补上 Access-Control-Allow-Origin: *，浏览器即放行。\n"
                 "安全：服务只监听 127.0.0.1，仅本机可访问；转发时会剥离 Cookie 等隐私头。\n"
                 "声明：仅供开发与调试使用，请遵守目标网站的服务条款，勿用于生产环境。")
        tk.Label(sb, text=about, bg="#f8f8fe", fg=DIM, justify="left",
                 font=(UI_FONT, 9), highlightthickness=1,
                 highlightbackground=LINE, padx=14, pady=12).pack(fill="x")

        # ---------- 底部状态栏 ----------
        self.statusbar = tk.Label(self.root, text="", bg=BG, fg=DIM, anchor="e",
                                  font=(UI_FONT, 9))
        self.statusbar.pack(fill="x", side="bottom", padx=16, pady=(4, 8))

    # ================================================================ 服务
    def _start_servers(self, port: int):
        self.proxy = ProxyServer(("127.0.0.1", port), log_fn=lambda e: self.log_q.put(e))
        self.mocksrv = MockServer(("127.0.0.1", 0), log_fn=lambda e: self.log_q.put(e))
        self.proxy.icon_bytes = self._load_icon_bytes()
        self.proxy.mock_base = self.mocksrv.base_url
        self.base_url = self.proxy.base_url
        self.mock_url = self.mocksrv.base_url
        threading.Thread(target=self.proxy.serve_forever, kwargs={"poll_interval": 0.2},
                         daemon=True, name="proxy-srv").start()
        threading.Thread(target=self.mocksrv.serve_forever, kwargs={"poll_interval": 0.2},
                         daemon=True, name="mock-srv").start()
        self._draw_dot("#16a34a")
        self.url_var.set(self.base_url)
        self.status_label.config(text="运行中 · 仅监听本机 127.0.0.1")
        self._log_line("sysok", f"服务已启动   代理 {self.base_url}   mock {self.mock_url}")
        self._log_line("dim", f"测试页 {self.base_url}/ ｜ 用法 {self.base_url}/<目标URL>")

    @staticmethod
    def _load_icon_bytes():
        try:
            with open(resource_path("icon.ico"), "rb") as f:
                return f.read()
        except Exception:
            return None

    def _stop_servers(self):
        for srv in (self.proxy, self.mocksrv):
            if srv is not None:
                try:
                    threading.Thread(target=srv.shutdown, daemon=True).start()
                    srv.server_close()
                except Exception:
                    pass
        self.proxy = None
        self.mocksrv = None
        self._draw_dot("#d1d5db")
        self.status_label.config(text="已停止")

    # ================================================================ 日志
    def _poll_log(self):
        try:
            while True:
                e = self.log_q.get_nowait()
                self._render_entry(e)
        except queue.Empty:
            pass
        self.root.after(80, self._poll_log)

    def _log_line(self, tag: str, msg: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", time.strftime("%H:%M:%S") + "  ", ("time",))
        self.log_text.insert("end", msg + "\n", (tag,))
        self.log_text.configure(state="disabled")
        if self.autoscroll_var.get():
            self.log_text.see("end")

    def _render_entry(self, e: dict):
        if e.get("kind") == "sys":
            self._log_line(e.get("level", "sys"), e.get("message", ""))
            return
        self.req_count += 1
        size = int(e.get("size") or 0)
        self.bytes_total += size
        kind = e.get("kind", "proxy")
        status = str(e.get("status", ""))
        if status == "ERR" or (status[:1] and status[0] in "45"):
            st_tag = "err"
        elif status[:1] == "3":
            st_tag = "warn"
        else:
            st_tag = "ok"
        url = str(e.get("url", ""))
        if len(url) > 110:
            url = url[:110] + "…"
        note = e.get("note") or ""
        method = str(e.get("method", ""))
        self.log_text.configure(state="normal")
        self.log_text.insert("end", e.get("time", "") + "  ", ("time",))
        self.log_text.insert("end", f"{method:<7} ", ("meth",))
        self.log_text.insert("end", f"{status:>3} ", (st_tag,))
        self.log_text.insert("end", f"{human_size(size):>10}  ", ("dim",))
        self.log_text.insert("end", f"{e.get('dur_ms', 0):>5}ms  ", ("dim",))
        self.log_text.insert("end", ("[mock] " if kind == "mock" else "") + url, ("url",))
        if note:
            self.log_text.insert("end", f"   ({note})", ("note",))
        self.log_text.insert("end", "\n")
        self.log_text.configure(state="disabled")
        if self.autoscroll_var.get():
            self.log_text.see("end")

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    # ================================================================ 动作
    def _draw_dot(self, color: str):
        self.dot.delete("all")
        self.dot.create_oval(2, 2, 10, 10, fill=color, outline="")

    def _flash(self, msg: str):
        self.flash.config(text=msg)
        self.root.after(1200, lambda: self.flash.config(text=""))

    def _copy_base(self):
        self._copy(self.base_url, "代理地址已复制")

    def _copy_conv(self):
        self._copy(self.conv_out_var.get(), "代理 URL 已复制")

    def _copy(self, text: str, msg: str):
        if not text:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._flash(msg)

    def _open_page(self):
        webbrowser.open(self.base_url + "/")

    def _open_page_with_conv(self):
        u = self.conv_in.get().strip()
        if u:
            webbrowser.open(self.base_url + "/?url=" + quote(u, safe=""))
        else:
            webbrowser.open(self.base_url + "/")

    def _open_conv(self):
        u = self.conv_out_var.get()
        if u:
            webbrowser.open(u)

    def _update_conv(self):
        u = self.conv_in.get().strip()
        if not u:
            self.conv_out_var.set("")
        elif u.startswith("http://") or u.startswith("https://"):
            self.conv_out_var.set(self.base_url + "/" + u)
        else:
            self.conv_out_var.set("(请输入以 http:// 或 https:// 开头的完整 URL)")

    def _apply_port(self):
        raw = (self.port_spin.get() or "").strip()
        if not raw:
            raw = "0"
        try:
            port = int(raw)
            if not (0 <= port <= 65535):
                raise ValueError
            if port != 0 and port < 1024:
                raise ValueError
        except ValueError:
            messagebox.showwarning("端口无效", "请输入 1024–65535 之间的端口，或选“自动挑选”。")
            return
        self._stop_servers()
        try:
            self._start_servers(port)
            self.log_q.put({"kind": "sys", "level": "sysok",
                            "message": f"服务已重启（端口 {'自动' if port == 0 else port}）"})
        except OSError as ex:
            messagebox.showerror("端口不可用",
                                 f"端口 {port} 启动失败：{ex}\n\n已自动切换为随机空闲端口。")
            self._start_servers(0)
        self._update_conv()

    def _tick(self):
        up = timedelta(seconds=int(time.time() - self.t_start))
        self.statusbar.config(text=f"请求数 {self.req_count:,}    "
                                   f"转发流量 {human_size(self.bytes_total)}    "
                                   f"已运行 {up}")
        self.root.after(1000, self._tick)

    def _on_close(self):
        self._stop_servers()
        self.root.after(150, self.root.destroy)


def main():
    if os.name == "nt":
        try:  # Windows 高分屏清晰化
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
