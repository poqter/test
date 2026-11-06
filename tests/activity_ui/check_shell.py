"""Verify the real workspace tool wrapper keeps shell state mounted on input."""
from pathlib import Path
import subprocess, sys, tempfile, time, socket
from playwright.sync_api import sync_playwright, expect
root=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory() as tmp:
    script=Path(tmp)/'shell.py'
    script.write_text(f'''import sys
sys.path.insert(0,{str(root)!r})
import streamlit as st
import app as workspace
st.set_page_config(initial_sidebar_state="collapsed")
workspace.inject_global_styles()
workspace.apply_workspace_design()
from modules.shared.brand_ui import apply
apply()
with st.sidebar:st.button('메뉴 항목')
from modules.shared.brand_ui import identity
identity('WORKSPACE',{{'display_name':'Test'}})
st.session_state['shell_runs']=st.session_state.get('shell_runs',0)+1
st.caption('SHELL_RUNS='+str(st.session_state['shell_runs']))
def tool(*args,**kwargs):
    text=st.text_input('도구 입력',key='tool_input')
    st.write('입력값: '+text)
workspace.dispatch=tool
workspace.render_task_content('synthetic','user',['synthetic'])
''')
    process=subprocess.Popen([sys.executable,'-m','streamlit','run',str(script),'--server.headless=true','--server.port=8505','--server.address=127.0.0.1','--browser.gatherUsageStats=false'],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                with socket.create_connection(('127.0.0.1',8505),timeout=.2):break
            except OSError:time.sleep(.2)
        with sync_playwright() as p:
            b=p.chromium.launch(headless=True);page=b.new_page();page.goto('http://127.0.0.1:8505')
            expect(page.get_by_text('SHELL_RUNS=1',exact=True)).to_be_visible()
            page.get_by_label('도구 입력').fill('입력 유지');page.get_by_label('도구 입력').press('Tab')
            expect(page.get_by_text('입력값: 입력 유지',exact=True)).to_be_visible()
            expect(page.get_by_text('SHELL_RUNS=1',exact=True)).to_be_visible()
            expect(page.get_by_test_id('stException')).to_have_count(0)
            for width in (1280,390):
                page.set_viewport_size({'width':width,'height':844})
                page.reload()
                expect(page.get_by_test_id('stSidebar')).to_have_attribute('aria-expanded','false')
                if width==390:
                    expect(page.get_by_test_id('stMainBlockContainer')).to_have_css('padding-top','52px')
                    expect(page.locator('.brand-header')).to_be_visible()
                    assert page.locator('.brand-header').bounding_box()['y']<=80
                opener=page.get_by_test_id('stExpandSidebarButton')
                expect(opener).to_be_visible();opener.click()
                expect(page.get_by_test_id('stSidebar')).to_have_attribute('aria-expanded','true')
                page.get_by_test_id('stSidebarCollapseButton').locator('button').click()
                expect(opener).to_be_visible()
            b.close()
    finally:process.terminate();process.wait(timeout=10)
print('PASS common workspace shell stays mounted during tool input')
