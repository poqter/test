"""One-use launch link; client feedback never changes the server ticket policy."""
from hashlib import sha256
from html import escape
import json
import time

import streamlit.components.v1 as components


def launch_link_html(url: str, label: str, *, issued_at: float) -> str:
    config = json.dumps({
        "expires": int((issued_at + 60) * 1000),
        "key": "hw.launch.used." + sha256(url.encode()).hexdigest(),
    }).replace("<", "\\u003c")
    return f'''<!doctype html><html lang="ko"><meta charset="utf-8">
<style>body{{margin:0;font:14px system-ui,sans-serif;color:#536b83}}
a{{display:block;padding:13px;border:1px solid #bdd0e5;border-radius:10px;
background:#2467ba;color:white;text-align:center;text-decoration:none;font-weight:700}}
a[aria-disabled="true"]{{background:#edf2f7;color:#62758a;cursor:default}}
p{{margin:8px 2px;font-size:12px;line-height:1.5}}</style>
<a id="launch" href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{escape(label)}</a>
<p id="status" role="status" aria-live="polite"></p>
<script>
const cfg={config}, link=document.getElementById('launch'), note=document.getElementById('status');
let used=false;
try{{used=Boolean(sessionStorage.getItem(cfg.key))}}catch{{}}
function update(){{
 const remaining=Math.max(0,Math.ceil((cfg.expires-Date.now())/1000));
 if(used||remaining===0){{link.removeAttribute('href');link.setAttribute('aria-disabled','true');
   link.textContent=used?'사용한 연결입니다':'연결 시간이 만료되었습니다';
   note.textContent='위의 ‘연결 다시 준비’를 누르면 새 연결을 받을 수 있습니다.';
 }}else{{note.textContent='이번 연결은 한 번만 사용할 수 있습니다 · 남은 시간 '+remaining+'초'}}
}}
link.addEventListener('click',event=>{{
 if(used||Date.now()>=cfg.expires){{event.preventDefault();update();return}}
 used=true;try{{sessionStorage.setItem(cfg.key,'1')}}catch{{}}
 // Let the native anchor open before removing its href.
 setTimeout(update,0);
}});
update();setInterval(update,1000);
</script></html>'''


def render_launch_link(url: str, label: str, *, issued_at: float | None = None) -> None:
    components.html(launch_link_html(url, label, issued_at=issued_at or time.time()), height=108)
