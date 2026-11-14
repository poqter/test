"""Synthetic operations UI regression. No production access or records."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]

def run():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    with tempfile.TemporaryFile(mode='w+') as log:
        server=subprocess.Popen([sys.executable,'-m','streamlit','run','tests/operations_harness.py','--server.port',str(port),'--server.address','127.0.0.1','--server.headless','true'],cwd=ROOT,stdout=log,stderr=log)
        try:
            for _ in range(60):
                try:
                    urllib.request.urlopen(f'http://127.0.0.1:{port}/_stcore/health',timeout=1);break
                except Exception:time.sleep(.5)
            with sync_playwright() as pw:
                opts={'headless':True}
                if os.getenv('OPS_TEST_EXECUTABLE'):opts['executable_path']=os.environ['OPS_TEST_EXECUTABLE']
                browser=pw.chromium.launch(**opts)
                context=browser.new_context(viewport={'width':1440,'height':1100},permissions=['clipboard-read','clipboard-write'])
                page=context.new_page();page.goto(f'http://127.0.0.1:{port}')
                listing=page.locator('.st-key-ops_list');detail=page.locator('.st-key-ops_detail')
                expect(listing).to_be_visible();expect(detail).to_be_visible()
                assert listing.bounding_box()['x'] < detail.bounding_box()['x']
                expect(page.get_by_role('textbox',name='요청문 미리보기',exact=True)).to_be_hidden()
                page.get_by_text('상세 근거 · 검사 단계 및 변경 파일',exact=True).click()
                page.get_by_role('button',name='단계별 근거 불러오기',exact=True).click()
                page.get_by_text('요청문 미리보기',exact=True).first.click()
                expect(page.get_by_role('textbox',name='요청문 미리보기',exact=True)).to_have_value(__import__('re').compile('tests/example.py'))
                copyframe=next(f for f in page.frames if f.get_by_role('button',name='요청문 복사',exact=True).count())
                copyframe.get_by_role('button',name='요청문 복사',exact=True).click()
                expect(copyframe.get_by_role('status')).to_have_text('복사 완료')
                assert 'tests/example.py' in page.evaluate('navigator.clipboard.readText()')
                page.get_by_text('요청문 미리보기',exact=True).first.click()
                if os.getenv('OPS_SCREENSHOTS'):
                    page.screenshot(path=os.environ['OPS_SCREENSHOTS']+'/operations-desktop.png',full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                expect(listing).to_be_visible();expect(detail).to_be_hidden()
                page.get_by_role('button',name=__import__('re').compile('Activity browser regression')).click()
                expect(detail).to_be_visible();expect(listing).to_be_hidden()
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                if os.getenv('OPS_SCREENSHOTS'):
                    page.screenshot(path=os.environ['OPS_SCREENSHOTS']+'/operations-mobile.png',full_page=True)
                page.get_by_role('button',name='← 문제 목록',exact=True).click()
                expect(listing).to_be_visible();expect(detail).to_be_hidden()
                expect(page.get_by_test_id('stException')).to_have_count(0)
                browser.close()
            print('PASS: desktop split view, collapsed evidence, refreshed copy payload, mobile detail/back, no overflow')
        finally:
            server.terminate();server.wait(timeout=15)

if __name__=='__main__':run()
