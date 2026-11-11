"""Run only synthetic UI harnesses; preserve failure diagnostics for seven days in CI."""
from pathlib import Path
import json
import shutil
import runpy
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
CASES=('check_alert_back.py','check_mobile_menu.py','check_mobile_back.py','check_calendar_devices.py','check_calendar.py',
 'check_persistent_calendar.py','check_calendar_fast.py','check_home_speed.py','check_stability.py',
 'check_calendar_loading.py','check_calendar_host.py','check_entry_routes.py',
 'check_calendar_entry.py','check_install.py','check_workspace.py','check_manager.py',
 'check_daily.py','check_mobile.py','check_mobile_back_host.py','check_shell.py','check_legacy_calendar.py')
OUT=ROOT/'test-results'/'activity-ui'

def run_case(name):
    from playwright.sync_api import Browser
    from playwright.sync_api._context_manager import PlaywrightContextManager
    contexts=[]; messages=[]
    original_context=Browser.new_context; original_page=Browser.new_page
    original_exit=PlaywrightContextManager.__exit__
    def track(context):
        if context in contexts:return
        contexts.append(context)
        context.tracing.start(screenshots=True,snapshots=True,sources=False)
        context.on('page',track_page)
    def track_page(page):
        page.on('pageerror',lambda error:messages.append({'type':'pageerror','message':str(error)}))
        page.on('console',lambda message:messages.append({'type':message.type,'message':message.text}) if message.type in ('error','warning') else None)
    def new_context(self,*a,**kw):
        context=original_context(self,*a,**kw);track(context);return context
    def new_page(self,*a,**kw):
        page=original_page(self,*a,**kw);track(page.context);track_page(page);return page
    def finish(self,exc_type,exc,tb):
        folder=OUT/Path(name).stem
        if exc_type:folder.mkdir(parents=True,exist_ok=True)
        for i,context in enumerate(contexts):
            if exc_type:
                for j,page in enumerate(context.pages):
                    try:page.screenshot(path=str(folder/f'context-{i}-page-{j}.png'),full_page=True,timeout=5000)
                    except Exception:pass  # Preserve the original assertion, even after a browser crash.
            try:context.tracing.stop(path=str(folder/f'context-{i}-trace.zip') if exc_type else None)
            except Exception:pass
        if exc_type:
            (folder/'browser-errors.json').write_text(json.dumps(messages[-200:],ensure_ascii=False,indent=2))
            (folder/'failure.txt').write_text(f'{exc_type.__name__}: {exc}')
        return original_exit(self,exc_type,exc,tb)
    Browser.new_context=new_context;Browser.new_page=new_page;PlaywrightContextManager.__exit__=finish
    if name=='--probe':
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page();page.set_content('<h1>Synthetic diagnostics probe</h1>')
            raise AssertionError('intentional synthetic diagnostic probe')
    if name not in CASES:raise ValueError('Only approved synthetic harnesses may be recorded')
    runpy.run_path(str(ROOT/'tests/activity_ui'/name),run_name='__main__')

if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--case':
        run_case(sys.argv[2])
    else:
        OUT.mkdir(parents=True,exist_ok=True)
        selected=sys.argv[1:] or CASES
        if any(case not in CASES for case in selected):raise SystemExit('Unknown synthetic test')
        results=[]
        for name in selected:
            shutil.rmtree(OUT/Path(name).stem,ignore_errors=True)
            print('RUN '+name,flush=True)
            try:
                result=subprocess.run([sys.executable,__file__,'--case',name],cwd=ROOT,
                    stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=240)
                output=result.stdout;code=result.returncode
            except subprocess.TimeoutExpired as exc:
                output=(exc.stdout or b'').decode(errors='replace') if isinstance(exc.stdout,bytes) else (exc.stdout or '')
                output+='\nHARNESS TIMEOUT (240 seconds)\n';code=124
            (OUT/(Path(name).stem+'.log')).write_text(output)
            print(output,flush=True)
            results.append({'case':name,'exit_code':code})
            (OUT/'summary.json').write_text(json.dumps(results,indent=2))
        raise SystemExit(1 if any(result['exit_code'] for result in results) else 0)
