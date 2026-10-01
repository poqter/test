"""Real browser smoke + screenshots. Requires real Streamlit and Chromium.

This is not a screenshot-baseline certification; outputs are provided for a
human to inspect. No live accounts, remote app, or real customer data is used.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));return sock.getsockname()[1]


def wait_health(url,process):
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        if process.poll() is not None:raise RuntimeError('Local Streamlit process exited')
        try:
            with urllib.request.urlopen(url+'/_stcore/health',timeout=2) as response:
                if response.status==200:return
        except OSError:time.sleep(.3)
    raise TimeoutError('Local Streamlit did not become healthy')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=ROOT/'artifacts/browser')
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    import streamlit
    from playwright.sync_api import sync_playwright,expect
    if hasattr(streamlit,'_api'):raise RuntimeError('A stub is not a browser runtime')
    servers=[];logs=[];results=[]
    try:
        urls={}
        for name,file in (('calculator','calculator_app.py'),('workspace','app.py')):
            port=free_port();log=(args.out/(name+'.log')).open('w',encoding='utf-8');logs.append(log)
            process=subprocess.Popen([sys.executable,'-m','streamlit','run',str(ROOT/file),'--server.address=127.0.0.1',f'--server.port={port}','--server.headless=true','--browser.gatherUsageStats=false'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            servers.append(process);urls[name]=f'http://127.0.0.1:{port}';wait_health(urls[name],process)
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch()
            context=browser.new_context(viewport={'width':1440,'height':1000})
            page=context.new_page();page.goto(urls['calculator']);page.locator('.st-key-jc_search input').wait_for(timeout=30000)
            search=page.locator('.st-key-jc_search input')
            page.locator('h1,h2,h3,h4').first.click()
            # Support the pinned outer text-input root rather than treating
            # an outline shown only during focus as a visible default border.
            has_border=search.evaluate('''el=>{let node=el;for(let i=0;i<5&&node;i++,node=node.parentElement){const s=getComputedStyle(node);if(parseFloat(s.borderTopWidth)>=1.5&&s.borderTopStyle==='solid'&&!['transparent','rgba(0, 0, 0, 0)'].includes(s.borderTopColor))return true;}return false;}''')
            assert has_border,'Unfocused search must have a visible border'
            page.screenshot(path=str(args.out/'calculator-home-desktop.png'),full_page=False)
            results.append({'test':'home_search_unfocused_border','status':'PASS'})
            page.locator('.st-key-calc_sidebar_group_2 button').click()
            expect(page.locator('.st-key-jc_search')).to_have_count(0)
            page.screenshot(path=str(args.out/'calculator-category-desktop.png'),full_page=False)
            results.append({'test':'category_has_no_search','status':'PASS'})
            with page.expect_popup() as popup_info:page.locator('a.hw-calc-new-tab').first.click()
            single=popup_info.value
            single.locator('.st-key-hw_calc_isolated_shell').wait_for(timeout=30000)
            expect(single.locator('[data-testid="stSidebar"]')).not_to_be_visible()
            expect(single.locator('.st-key-jc_back_catalog')).to_have_count(0)
            expect(single.locator('.st-key-jc_search')).to_have_count(0)
            single.screenshot(path=str(args.out/'calculator-single-desktop.png'),full_page=False)
            results.append({'test':'single_no_navigation','status':'PASS'})
            for name,w,h in [('tablet',1024,768),('mobile',390,844)]:
                context2=browser.new_context(viewport={'width':w,'height':h})
                p=context2.new_page();p.goto(urls['calculator']+'/?calc=calc-007&view=single')
                p.locator('.st-key-hw_calc_isolated_shell').wait_for(timeout=30000)
                assert p.locator('[data-testid="stException"]').count()==0
                overflow=p.evaluate('document.documentElement.scrollWidth>window.innerWidth+2')
                assert not overflow,'Horizontal overflow on '+name
                p.screenshot(path=str(args.out/('calculator-single-'+name+'.png')),full_page=True)
                context2.close();results.append({'test':'single_'+name+'_no_overflow','status':'PASS'})
            login=context.new_page();login.goto(urls['workspace'])
            login.locator('input[type=password]').wait_for(timeout=30000)
            login.screenshot(path=str(args.out/'workspace-login.png'),full_page=False)
            results.append({'test':'workspace_login_still_required','status':'PASS'})
            browser.close()
    finally:
        for server in servers:server.terminate()
        for server in servers:
            try:server.wait(timeout=10)
            except subprocess.TimeoutExpired:server.kill()
        for log in logs:log.close()
        (args.out/'browser_results.json').write_text(json.dumps({'scope':'real browser smoke; screenshots require human review','results':results},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':len(results),'screenshots':str(args.out)},ensure_ascii=False));return 0

if __name__=='__main__':raise SystemExit(main())
