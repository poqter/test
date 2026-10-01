"""Headless browser regression for Academy V2 UI/engine integration.

Uses the real frontend and Python service through a minimal Streamlit-component
message host. It does not claim to test the Streamlit runtime or Community Cloud.
"""
import sys,json,argparse,shutil
from pathlib import Path
APP=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(APP))
from hwarang_academy.service import AppState,present,handle
from playwright.sync_api import sync_playwright
FRONT=APP/'hwarang_academy/frontend'


def attach(page,app):
    def invoke(action): return handle(app,action)
    page.expose_function('python_action',invoke)
    payload=present(app);payload['base_url']='https://academy.example.invalid/'
    source=(FRONT/'index.html').read_text(encoding='utf-8').replace(
        '<link rel="stylesheet" href="styles.css">','<style>'+(FRONT/'styles.css').read_text(encoding='utf-8')+'</style>').replace(
        '<script src="app.js"></script>','<script>'+(FRONT/'app.js').read_text(encoding='utf-8')+'</script>')
    parent='''<html><style>html,body{margin:0;background:#f4f7fb}iframe{border:0;width:100%;display:block;height:1100px}</style><iframe id="frame" title="Academy test component"></iframe><script>
 const f=document.getElementById('frame');let m=MODEL;
 function send(){f.contentWindow.postMessage({type:'streamlit:render',args:{model:m}},'*');}
 window.addEventListener('message',async e=>{if(e.source!==f.contentWindow)return;
 if(e.data.type==='streamlit:componentReady')send();
 if(e.data.type==='streamlit:setFrameHeight')f.style.height=e.data.height+'px';
 if(e.data.type==='streamlit:setComponentValue'){m=await window.python_action(e.data.value);m.base_url='https://academy.example.invalid/';send();}
 });
 f.srcdoc=SOURCE;
 </script></html>'''.replace('MODEL',json.dumps(payload,ensure_ascii=False)).replace('SOURCE',json.dumps(source,ensure_ascii=False).replace('</','<\\/'))
    page.set_content(parent)
    return page.frame_locator('#frame')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='academy_browser_results');args=parser.parse_args()
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    checks=[];errors=[]
    def check(name,value):
        checks.append({'name':name,'passed':bool(value)})
        if not value: raise AssertionError(name)

    with sync_playwright() as p:
        binary=shutil.which('chromium') or shutil.which('google-chrome')
        b=p.chromium.launch(**({'executable_path':binary} if binary else {}),headless=True,args=['--no-sandbox'])

        home=b.new_page(viewport={'width':1440,'height':1000});home.on('pageerror',lambda e:errors.append(str(e)))
        f=attach(home,AppState());f.locator('.academy-main').wait_for()
        check('home_six_executable_cards',f.locator('.case-card').count()==6)
        check('home_map_97',f.locator('.map-row').count()==97)
        check('home_new_tab_link',f.get_by_role('link',name='가이드 훈련 시작하기 ↗').get_attribute('target')=='_blank')
        home.screenshot(path=str(out/'academy_home.png'),full_page=True)
        home.close()

        for mode in ['GUIDE','COACH','SOLO','ASSESSMENT']:
            app=AppState(independent=True,mode=mode,selection='C07-S01',session_length='STANDARD')
            page=b.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept())
            f=attach(page,app);f.locator('.setup').wait_for()
            check(mode+'_four_modes',f.locator('.mode-card').count()==4)
            check(mode+'_three_lengths',f.locator('.length-card').count()==3)
            check(mode+'_mission_before_start',f.locator('.mission-preview').count()==1 and len(f.locator('.mission-preview').inner_text())>20)
            if mode=='GUIDE': check('guide_setup_points_visible',f.locator('.guide-points').count()==1)
            if mode=='ASSESSMENT': check('assessment_setup_points_hidden',f.locator('.guide-points').count()==0)

            f.locator('[data-action="start"]').click();f.locator('.conversation').wait_for()
            check(mode+'_white_chat',f.locator('.conversation').evaluate('(e)=>getComputedStyle(e).backgroundColor')=='rgb(255, 255, 255)')
            check(mode+'_input_auto_focus_initial',f.locator('#message-input').evaluate('(e)=>document.activeElement===e'))
            if mode=='GUIDE':
                check('guide_panel_default_open',f.locator('.guide-panel').count()==1)
                check('guide_three_answer_cards',f.locator('.guide-card').count()==3)
                rec=f.locator('.guide-card.good [data-action="insert-guide"]')
                rec.click()
                check('guide_insert_populates_input',len(f.locator('#message-input').input_value())>5)
                check('guide_insert_focuses_input',f.locator('#message-input').evaluate('(e)=>document.activeElement===e'))
                f.locator('#message-input').fill('보험료 얼마 내세요?')
                f.locator('#message-input').press('Enter')
                f.locator('.typing-bubble').wait_for()
                check('guide_typing_indicator',f.locator('.typing-bubble').count()==1)
                f.locator('.chat-title small').filter(has_text='답변 1개').wait_for(timeout=5000)
                check('guide_focus_returns_after_reply',f.locator('#message-input').evaluate('(e)=>document.activeElement===e'))
                check('guide_panel_updates_after_reply',f.locator('.guide-panel').count()==1)
                page.screenshot(path=str(out/'simulator_guide.png'),full_page=True)
            elif mode=='COACH':
                check('coach_no_guide_panel',f.locator('.guide-panel').count()==0)
                f.locator('#message-input').fill('보험료 얼마 내세요?');f.locator('#message-input').press('Enter')
                f.locator('.coaching').wait_for();check('coach_draft_not_committed',len(app.session.turns)==0)
                f.locator('[data-action="commit"]').click();f.locator('.typing-bubble').wait_for()
                f.locator('.chat-title small').filter(has_text='답변 1개').wait_for(timeout=5000)
                check('coach_commits_after_review',len(app.session.turns)==1)
                check('coach_focus_returns_after_reply',f.locator('#message-input').evaluate('(e)=>document.activeElement===e'))
            else:
                check(mode+'_no_guide_or_coaching',f.locator('.guide-panel,.coaching,.states').count()==0)
                f.locator('#message-input').fill('보험료 얼마 내세요?');f.locator('#message-input').press('Enter')
                f.locator('.typing-bubble').wait_for()
                f.locator('.chat-title small').filter(has_text='답변 1개').wait_for(timeout=5000)
                check(mode+'_focus_returns_after_reply',f.locator('#message-input').evaluate('(e)=>document.activeElement===e'))

            # A newline must remain in the composer; Enter alone sends.
            f.locator('#message-input').fill('첫 줄');f.locator('#message-input').press('Shift+Enter');f.locator('#message-input').type('둘째 줄')
            check(mode+'_shift_enter_newline','\n' in f.locator('#message-input').input_value())
            # Finish deliberately; result should expose retry choices.
            f.locator('[data-action="finish"]').click();f.locator('.result').wait_for()
            check(mode+'_result_retry_choices',f.locator('[data-action="retry"], [data-action="retry-new"], [data-action="retry-harder"]').count()==3)

            for width in [390,320]:
                page.set_viewport_size({'width':width,'height':844});page.wait_for_timeout(60)
                check(mode+f'_mobile_{width}_no_horizontal_overflow',f.locator('html').evaluate('(e)=>e.scrollWidth<=innerWidth'))
            if mode=='GUIDE':page.screenshot(path=str(out/'simulator_mobile.png'),full_page=True)
            page.close()

        # Markup remains text, never executable HTML.
        app=AppState(independent=True,mode='SOLO');page=b.new_page(viewport={'width':1100,'height':800});page.on('pageerror',lambda e:errors.append(str(e)))
        f=attach(page,app);f.locator('[data-action="start"]').click();f.locator('.conversation').wait_for()
        f.locator('#message-input').fill('<img src=x onerror="window.BAD=1">');f.locator('#message-input').press('Enter')
        f.locator('.chat-title small').filter(has_text='답변 1개').wait_for(timeout=5000)
        check('escaped_user_markup',f.locator('.bubble img').count()==0)
        check('zero_browser_script_errors',not errors)
        page.close();b.close()

    report={'method':'Headless Chromium + real frontend + real Python service via minimal component message host; NOT Streamlit runtime/Cloud',
            'checks':checks,'pass':sum(c['passed'] for c in checks),'fail':sum(not c['passed'] for c in checks),'script_errors':errors}
    (out/'browser_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'pass':report['pass'],'fail':report['fail'],'script_errors':errors},ensure_ascii=False))
    return 0 if not report['fail'] else 1

if __name__=='__main__': raise SystemExit(main())
