"""Browser regression for user-reported dialogue and recovery controls.

Optional developer check: requires Playwright + Chromium. Runtime users do not
need those packages. Uses an ephemeral loopback port and access token; neither
are written to test artifacts. This does not test Streamlit Community Cloud.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import threading
from http.server import ThreadingHTTPServer

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import run_academy_local as web
from hwarang_academy.tests.test_dialogue_repair import REPORTED_MESSAGES
from playwright.sync_api import sync_playwright


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='artifacts/academy_dialogue_browser')
    parser.add_argument('--transport',choices=('component','local'),default='component',help='component = real engine with minimal Streamlit message host; local = actual loopback HTTP')
    args=parser.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    from tools.academy_browser_checks import attach
    from hwarang_academy.service import AppState
    def open_view(page,mode):
        if args.transport=='component':
            return attach(page,AppState(independent=True,selection='C07-S01',mode=mode))
        page.goto(base+f'/?view=simulator&scenario=C07-S01&mode={mode}#access='+web.TOKEN)
        return page
    server=ThreadingHTTPServer(('127.0.0.1',0),web.Handler)
    th=threading.Thread(target=server.serve_forever,daemon=True);th.start()
    base=f'http://127.0.0.1:{server.server_port}'
    checks=[];errors=[]
    def check(name,value):
        checks.append({'name':name,'passed':bool(value)})
        if not value:raise AssertionError(name)
    def send(page,text,n,mode):
        page.locator('#message-input').fill(text)
        page.locator('#compose button[type="submit"]').click()
        if mode in ('GUIDE','COACH'):
            page.locator('.coaching').wait_for()
            page.locator('[data-action="commit"]').click()
        page.locator('.chat-title small').filter(has_text=f'답변 {n}개').wait_for()
        return page.locator('.msg.customer .bubble').last.inner_text()
    try:
        with sync_playwright() as p:
            binary=shutil.which('chromium') or shutil.which('google-chrome')
            browser=p.chromium.launch(**({'executable_path':binary} if binary else {}),headless=True,args=['--no-sandbox'])
            for mode in ('GUIDE','COACH','SOLO','ASSESSMENT'):
                page=browser.new_page(viewport={'width':1440,'height':1040});page.on('pageerror',lambda e:errors.append(str(e)))
                view=open_view(page,mode)
                view.locator('[data-action="start"]').click();view.locator('.conversation').wait_for()
                check(mode+'_white_chat',view.locator('.conversation').evaluate('(e)=>getComputedStyle(e).backgroundColor')=='rgb(255, 255, 255)')
                for n,text in enumerate(REPORTED_MESSAGES,1):
                    reply=send(view,text,n,mode)
                    if n==1:check(mode+'_greeting_review_response','같이 확인' in reply)
                    if n==2:check(mode+'_indirect_question_contract','이십만' in reply)
                    if n==6:check(mode+'_short_coverage_response','정확한 보장' in reply)
                    if n==7:check(mode+'_repeat_last_response','정확한 보장' in reply)
                    if n==8:check(mode+'_topic_recovery_premium','사십삼만' in reply)
                check(mode+'_no_endless_customer_questions',view.locator('.dialogue-notice').is_visible())
                check(mode+'_ten_learner_turns',view.locator('.msg.advisor').count()==10)
                if mode in ('SOLO','ASSESSMENT'):
                    check(mode+'_no_hidden_coaching',view.locator('.coaching,.helper,.assist-panel,.states').count()==0)
                reply=send(view,'전체로 한 달 보험료는 얼마인가요?',11,mode)
                check(mode+'_recover_after_notice','사십삼만' in reply and view.locator('.dialogue-notice').count()==0)
                if mode=='SOLO':page.screenshot(path=str(out/'chat_repaired.png'),full_page=True)
                for width in (390,320):
                    page.set_viewport_size({'width':width,'height':844})
                    check(mode+f'_width_{width}',view.locator('html').evaluate('(e)=>e.scrollWidth<=innerWidth'))
                page.close()
            page=browser.new_page(viewport={'width':1280,'height':920})
            view=open_view(page,'SOLO')
            view.locator('[data-action="start"]').click();view.locator('.conversation').wait_for()
            send(view,'그 부분부터 확인할게요.',1,'SOLO')
            reply=send(view,'보험료요',2,'SOLO')
            check('short_reply_resolves_customer_question','사십삼만' in reply)
            check('zero_script_errors',not errors)
            browser.close()
    except Exception as exc:
        if args.transport=='local' and 'ERR_BLOCKED_BY_ADMINISTRATOR' in str(exc):
            result={'status':'NOT_RUN','method':'actual loopback browser navigation','reason':'Browser policy blocked local navigation; no bypass attempted.'}
            (out/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
            print(json.dumps(result));return 2
        raise
    finally:
        server.shutdown();server.server_close();web.STATES.clear()
    result={'method':('Real loopback Handler + actual frontend via HTTP + Chromium' if args.transport=='local' else 'Chromium + actual frontend + real Python engine via minimal component message host; NOT Streamlit runtime/Cloud'),
            'checks':checks,'pass':sum(c['passed'] for c in checks),'fail':sum(not c['passed'] for c in checks),'script_errors':errors}
    (out/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'pass':result['pass'],'fail':result['fail'],'script_errors':errors},ensure_ascii=False))

if __name__=='__main__':raise SystemExit(main() or 0)
