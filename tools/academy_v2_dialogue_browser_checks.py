"""Actual loopback-browser smoke test for Academy V2 dialogue UX.

Starts the same standard-library HTTP server used by start_academy_local.bat,
opens it in headless Chromium, and exercises a natural C07 SOLO conversation.
This verifies local transport/front-end integration, not Streamlit Cloud.
"""
from __future__ import annotations
import json, shutil, sys, threading
from pathlib import Path
from http.server import ThreadingHTTPServer

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import run_academy_local as local
from playwright.sync_api import sync_playwright, Error as PlaywrightError

OUT=ROOT/'artifacts'/'academy_v2_local_browser'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),local.Handler)
    th=threading.Thread(target=server.serve_forever,daemon=True);th.start()
    base=f'http://127.0.0.1:{server.server_port}/?view=simulator&scenario=C07-S01&mode=SOLO&length=STANDARD#access={local.TOKEN}'
    checks=[];errors=[]
    def ck(name,value):
        checks.append({'name':name,'passed':bool(value)})
        if not value: raise AssertionError(name)
    try:
        with sync_playwright() as p:
            binary=shutil.which('chromium') or shutil.which('google-chrome')
            browser=p.chromium.launch(**({'executable_path':binary} if binary else {}),headless=True,args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)))
            try:
                page.goto(base,wait_until='domcontentloaded');page.locator('.setup').wait_for(timeout=8000)
            except PlaywrightError as exc:
                if 'ERR_BLOCKED_BY_ADMINISTRATOR' in str(exc):
                    result={'status':'NOT_RUN','method':'Actual loopback HTTP server used by BAT + headless Chromium','reason':'Browser policy blocked loopback navigation in this environment; component-host browser regression remains available.'}
                    (OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
                    print(json.dumps(result,ensure_ascii=False));browser.close();return 2
                raise
            ck('mission_visible',page.locator('.mission-preview').count()==1)
            page.locator('[data-action="start"]').click();page.locator('.conversation').wait_for(timeout=8000)
            ck('chat_is_light',page.locator('.conversation').evaluate('(e)=>getComputedStyle(e).backgroundColor')=='rgb(255, 255, 255)')
            ck('input_initial_focus',page.locator('#message-input').evaluate('(e)=>document.activeElement===e'))
            utterances=[
                '안녕하세요, 보험료가 너무 많이 나가서 부담되셨겠어요. 함께 확인해볼까요?',
                '혹시 얼마 정도 납입하고 계실까요?',
                '30만원중에 실손 의료비가 얼마정도 되시나요?',
                '같이 확인해보고자하는데 증권 가지고 계신가요?',
                '자료 확인해주세요',
                '어떻게 확인할 수 있을까요',
            ]
            replies=[]
            for n,text in enumerate(utterances,1):
                inp=page.locator('#message-input');inp.fill(text);inp.press('Enter')
                page.locator('.typing-bubble').wait_for(timeout=2500)
                page.locator('.chat-title small').filter(has_text=f'답변 {n}개').wait_for(timeout=6000)
                replies.append(page.locator('.msg.customer .bubble').last.inner_text())
                ck(f'focus_return_{n}',page.locator('#message-input').evaluate('(e)=>document.activeElement===e'))
            ck('amount_question_understood',any(x in replies[1] for x in ('38','43','51','55')))
            ck('indemnity_component_understood','실손 보험료' in replies[2] and ('증권' in replies[2] or '기억' in replies[2]))
            ck('document_possession_understood',any(x in replies[3] for x in ('증권','자료','배우자')))
            ck('document_check_understood',any(x in replies[4] for x in ('열었','확인','자료','증권')))
            ck('document_method_understood',any(x in replies[5] for x in ('휴대폰','증권','자료','배우자','앱')))
            ck('no_old_clarification_loop',sum(('보험료를 확인하자는 말씀이신가요' in x or '어느 부분을 먼저 확인' in x) for x in replies)==0)
            ck('no_script_errors',not errors)
            page.screenshot(path=str(OUT/'c07_v2_local.png'),full_page=True)
            browser.close()
    finally:
        server.shutdown();server.server_close();local.STATES.clear()
    result={'method':'Actual loopback HTTP server used by BAT + headless Chromium','pass':sum(x['passed'] for x in checks),'fail':sum(not x['passed'] for x in checks),'checks':checks,'script_errors':errors}
    (OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'pass':result['pass'],'fail':result['fail'],'script_errors':errors},ensure_ascii=False))
    return 0 if result['fail']==0 else 1

if __name__=='__main__':raise SystemExit(main())
