# -*- coding: utf-8 -*-
"""内置 CORS 测试页（浏览器访问 http://127.0.0.1:<port>/ 时返回）。
占位符：__MOCK_BASE__ / __PROXY_BASE__ 由 server.py 在响应时替换。
"""

TEST_PAGE_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CORS 本地代理 · 测试页</title>
<style>
:root{
  --bg:#0b1020; --card:#141b31; --card2:#101729; --line:#232d4d;
  --text:#e6eaf5; --dim:#8b93a7; --accent:#8b5cf6; --accent2:#22d3ee;
  --ok:#4ade80; --warn:#fbbf24; --err:#f87171; --radius:14px;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
  font:14px/1.65 "Segoe UI","PingFang SC","Microsoft YaHei",system-ui,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:28px 20px 60px}
header{display:flex;align-items:center;gap:12px;margin-bottom:6px}
.logo{width:40px;height:40px;border-radius:10px;
  background:linear-gradient(160deg,#2b287a,#8b5cf6);display:flex;
  align-items:center;justify-content:center;font-size:20px}
h1{font-size:20px;margin:0}
.sub{color:var(--dim);font-size:12.5px;margin:2px 0 18px 52px}
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
  padding:18px;margin-bottom:16px}
label{display:block;font-size:12px;color:var(--dim);margin:10px 0 4px;letter-spacing:.4px}
.row{display:flex;gap:10px}
.row>*{flex:1}
input[type=text],select,textarea{width:100%;background:var(--card2);color:var(--text);
  border:1px solid var(--line);border-radius:9px;padding:9px 12px;
  font:13px/1.5 Consolas,"Courier New",monospace;outline:none}
input[type=text]:focus,textarea:focus{border-color:var(--accent)}
textarea{resize:vertical;min-height:64px}
.btns{display:flex;gap:10px;margin-top:14px;flex-wrap:wrap}
button{border:0;border-radius:9px;padding:9px 18px;font-size:13.5px;font-weight:600;
  cursor:pointer;transition:.15s;color:#fff;background:#2a3556}
button:hover{filter:brightness(1.15)}
button.primary{background:linear-gradient(120deg,#7c3aed,#8b5cf6)}
button.cyan{background:#0e7490}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.chip{font-size:12px;color:var(--accent2);background:#0d2a33;border:1px solid #14505f;
  border-radius:99px;padding:4px 12px;cursor:pointer;user-select:none}
.chip:hover{background:#124a58}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:760px){.grid{grid-template-columns:1fr}}
.panel{background:var(--card2);border:1px solid var(--line);border-radius:var(--radius);
  padding:16px;min-height:120px}
.panel h3{margin:0 0 10px;font-size:14px;display:flex;align-items:center;gap:8px}
.tag{font-size:11px;padding:2px 9px;border-radius:99px;background:#26304f;color:var(--dim)}
.badge{display:inline-block;font-size:12.5px;font-weight:700;padding:3px 11px;border-radius:99px}
.badge.s2{background:#052e16;color:var(--ok)}
.badge.s3{background:#422006;color:var(--warn)}
.badge.s4,.badge.s5{background:#450a0a;color:var(--err)}
.badge.serr{background:#450a0a;color:var(--err)}
.meta{color:var(--dim);font-size:12px;margin-left:8px}
.hint{background:#1e1b33;border:1px dashed #4c4079;color:#c4b5fd;border-radius:9px;
  padding:10px 12px;font-size:12.5px;margin-top:10px}
pre{background:#0a0f1f;border:1px solid var(--line);border-radius:9px;padding:10px 12px;
  font:12px/1.55 Consolas,monospace;overflow:auto;max-height:340px;white-space:pre-wrap;
  word-break:break-all;margin:8px 0 0}
details{margin-top:10px}
summary{cursor:pointer;color:var(--dim);font-size:12.5px}
table{width:100%;border-collapse:collapse;font-size:12px;margin-top:6px}
td{padding:3px 8px;border-bottom:1px solid #1a2340;vertical-align:top}
td:first-child{color:var(--accent2);white-space:pre;width:220px;
  font-family:Consolas,monospace}
.errbox{color:var(--err);background:#2a1215;border:1px solid #7f1d1d;border-radius:9px;
  padding:10px 12px;font:12.5px/1.6 Consolas,monospace;margin-top:10px;word-break:break-all}
.snippet{margin-top:14px}
.snippet pre{max-height:none}
.kbd{background:#26304f;border-radius:5px;padding:1px 7px;font-size:11.5px;color:#cbd5f5}
footer{color:#55607a;font-size:11.5px;text-align:center;margin-top:34px}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="logo">&#8646;</div>
    <h1>CORS 本地代理 · 测试页</h1>
  </header>
  <div class="sub">代理地址 <span class="kbd">__PROXY_BASE__/&lt;目标URL&gt;</span>
    &nbsp;·&nbsp; Mock 地址 <span class="kbd">__MOCK_BASE__</span>
    &nbsp;·&nbsp; 请求日志见桌面程序窗口</div>

  <div class="card">
    <label>目标 URL</label>
    <input type="text" id="url" placeholder="https://api.example.com/path" spellcheck="false">
    <div class="chips">
      <span class="chip" data-u="__MOCK_BASE__/no-cors">mock /no-cors（必被CORS拦）</span>
      <span class="chip" data-u="__MOCK_BASE__/allow-all">mock /allow-all（直连可通）</span>
      <span class="chip" data-u="__MOCK_BASE__/wrong-origin">mock /wrong-origin</span>
      <span class="chip" data-u="__MOCK_BASE__/echo">mock /echo</span>
      <span class="chip" data-u="https://api.github.com/zen">api.github.com/zen</span>
      <span class="chip" data-u="https://www.baidu.com/">baidu.com</span>
    </div>
    <div class="row">
      <div>
        <label>方法</label>
        <select id="method">
          <option>GET</option><option>POST</option><option>PUT</option>
          <option>PATCH</option><option>DELETE</option><option>HEAD</option>
        </select>
      </div>
    </div>
    <label>请求头（每行一条 <b>名称: 值</b>，部分受限头浏览器会忽略）</label>
    <textarea id="headers" spellcheck="false" placeholder="X-Token: abc123"></textarea>
    <label>请求体（POST / PUT / PATCH 时发送）</label>
    <textarea id="body" spellcheck="false" placeholder='{"hello":"world"}'></textarea>
    <div class="btns">
      <button class="primary" id="run-both">&#9654;&#9654; 同时对比发送</button>
      <button id="run-direct">仅直连</button>
      <button class="cyan" id="run-proxy">仅走代理</button>
      <button id="copy-proxy">复制代理URL</button>
    </div>
  </div>

  <div class="grid">
    <div class="panel">
      <h3>直连请求 <span class="tag">浏览器原生 fetch</span></h3>
      <div id="d-direct"><span class="meta">尚未发送。跨域目标若无 CORS 头，将被浏览器拦截（这是正常演示效果）。</span></div>
    </div>
    <div class="panel">
      <h3>代理请求 <span class="tag">自动加代理前缀</span></h3>
      <div id="d-proxy"><span class="meta">尚未发送。代理会补齐 CORS 头，同请求应能成功。</span></div>
    </div>
  </div>

  <div class="card snippet">
    <label>前端代码示例</label>
    <pre id="snippet"></pre>
  </div>

  <footer>cors-local-proxy · 仅监听本机 127.0.0.1 · 仅供开发调试使用</footer>
</div>

<script>
const $ = id => document.getElementById(id);
const BODY_METHODS = ["POST","PUT","PATCH"];

// —— URL ?url= 预填 ——
const qs = new URLSearchParams(location.search);
if (qs.get("url")) $("url").value = qs.get("url");
else $("url").value = "__MOCK_BASE__/no-cors";

function parseHeaders(){
  const out = {};
  ($("headers").value || "").split(/\n+/).forEach(line=>{
    const i = line.indexOf(":");
    if(i>0){ const k=line.slice(0,i).trim(); const v=line.slice(i+1).trim();
      if(k && !/^(host|content-length|origin|referer|cookie)$/i.test(k)) out[k]=v; }
  });
  return out;
}
function esc(s){return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}

function badgeCls(st){
  if(st>=200&&st<300)return "s2"; if(st>=300&&st<400)return "s3";
  if(st>=400&&st<500)return "s4"; if(st>=500)return "s5"; return "serr";
}
function render(box, r){
  if(!r.ok){
    box.innerHTML = '<span class="badge serr">失败</span><span class="meta">'
      + r.dur.toFixed(0) + ' ms</span>'
      + '<div class="errbox">' + esc(r.error) + '</div>'
      + '<div class="hint">「Failed to fetch」通常就是被 CORS 拦截（浏览器刻意隐藏细节）；也可能是网络不通。</div>';
    return;
  }
  const fin = (r.headers.find(h => String(h[0]).toLowerCase() === "x-final-url") || [])[1];
  const rows = r.headers.map(h=>
    '<tr><td>'+esc(h[0])+'</td><td>'+esc(String(h[1]).slice(0,300))+'</td></tr>').join("");
  const body = r.text.length>200000 ? r.text.slice(0,200000)+"\n…(已截断)" : r.text;
  box.innerHTML =
    '<span class="badge '+badgeCls(r.status)+'">'+r.status+'</span>'
    + '<span class="meta">'+r.dur.toFixed(0)+' ms · '+r.size+' 字节'
    + (fin ? ' · 最终 '+esc(String(fin).slice(0,90)) : '') + '</span>'
    + '<details><summary>响应头 ('+r.headers.length+')</summary><table>'+rows+'</table></details>'
    + '<pre>'+esc(body||"(空)")+'</pre>';
}

async function fire(mode){
  const url = $("url").value.trim();
  if(!url){ alert("请输入目标 URL"); return; }
  const method = $("method").value;
  const headers = parseHeaders();
  const hasBody = BODY_METHODS.includes(method) && $("body").value.length>0;
  const finalUrl = mode==="proxy" ? (location.origin + "/" + url) : url;
  const box = $(mode==="proxy" ? "d-proxy" : "d-direct");
  box.innerHTML = '<span class="meta">请求中…</span>';
  const t0 = performance.now();
  try{
    const resp = await fetch(finalUrl, {method, headers,
      body: hasBody ? $("body").value : undefined});
    const dur = performance.now()-t0;
    const text = await resp.text();
    render(box, {ok:true, status:resp.status, dur,
      size:text.length, headers:[...resp.headers], text});
  }catch(e){
    render(box, {ok:false, dur:performance.now()-t0, error:String(e)});
  }
}

$("run-direct").onclick = ()=>fire("direct");
$("run-proxy").onclick  = ()=>fire("proxy");
$("run-both").onclick   = ()=>{fire("direct"); fire("proxy");};
document.querySelectorAll(".chip").forEach(c=>c.onclick=()=>{$("url").value=c.dataset.u;});
$("copy-proxy").onclick = ()=>{
  navigator.clipboard.writeText(location.origin + "/" + $("url").value.trim());
  const b=$("copy-proxy"); const t=b.textContent; b.textContent="已复制 ✓";
  setTimeout(()=>b.textContent=t,1200);
};
function snippet(){
  $("snippet").textContent =
'// 任何被 CORS 拦的接口，在前面拼上代理地址即可：\n'
+'const PROXY = "'+location.origin+'";\n\n'
+'fetch(PROXY + "/'+ ($("url").value.trim()||"https://api.example.com/data") +'")\n'
+'  .then(r => r.json())\n'
+'  .then(data => console.log(data));';
}
$("url").addEventListener("input", snippet);
$("method").addEventListener("change", snippet);
snippet();
</script>
</body>
</html>
"""
