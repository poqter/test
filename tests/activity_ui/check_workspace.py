"""Real browser against Streamlit with synthetic records; no production access."""
from pathlib import Path
import socket
import subprocess
import sys
import time
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[2]
server=subprocess.Popen([sys.executable,'-m','streamlit','run',str(ROOT/'tests/activity_ui/harness.py'),
    '--server.headless=true','--server.port=8504','--server.address=127.0.0.1',
    '--browser.serverAddress=localhost','--browser.gatherUsageStats=false'],
    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
    for _ in range(150):
        try:
            with socket.create_connection(('127.0.0.1',8504),timeout=.2):break
        except OSError:time.sleep(.2)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1280,'height':900})
        page.goto('http://127.0.0.1:8504')
        expect(page.get_by_text('전체 실행 횟수 1',exact=True)).to_be_visible()
        cal=page.frame_locator('iframe[title="modules.activity.center.sales_calendar_view"]')
        cal.get_by_role('button',name='＋ 일정 등록',exact=True).click()
        dlg=cal.get_by_role('dialog')
        dlg.get_by_role('button',name='일정 등록',exact=True).click()
        assert dlg.get_by_label('일정명',exact=True).evaluate('e=>!e.validity.valid')
        expect(dlg.get_by_label('일정명',exact=True)).to_be_focused()
        dlg.get_by_label('일정명',exact=True).fill('버릴 작성 내용')
        dlg.get_by_label('일정명',exact=True).press('Tab')
        expect(page.get_by_text('전체 실행 횟수 1',exact=True)).to_be_visible()
        dlg.get_by_role('button',name='팝업 닫기',exact=True).click()
        dlg.get_by_role('button',name='저장하지 않고 닫기',exact=True).click()
        expect(dlg).not_to_be_visible()
        cal.locator('.cell[data-key="2026-11-06"] .chip').first.click()
        expect(dlg.get_by_role('button',name='일정 삭제',exact=True)).to_have_css('color','rgb(180, 35, 24)')
        box=dlg.bounding_box();frame=page.locator('iframe[title="modules.activity.center.sales_calendar_view"]').bounding_box()
        assert box['width'] <= 620
        assert abs(box['x']+box['width']/2-frame['x']-frame['width']/2)<3
        dlg.get_by_role('button',name='일정 수정',exact=True).click()
        page.set_viewport_size({'width':1280,'height':600})
        expect(dlg.get_by_role('button',name='변경 저장',exact=True)).to_be_visible()
        header=dlg.locator('.panel-head')
        y=header.bounding_box()['y']
        dlg.evaluate('e=>e.scrollTop=e.scrollHeight')
        assert dlg.evaluate('e=>e.scrollTop')>0
        assert abs(header.bounding_box()['y']-y)<1
        expect(dlg.get_by_role('button',name='팝업 닫기',exact=True)).to_be_visible()
        page.set_viewport_size({'width':1280,'height':900})
        dlg.get_by_label('일정명',exact=True).fill('브라우저 저장한 제목')
        dlg.get_by_label('일정명',exact=True).press('Tab')
        dlg.get_by_role('button',name='변경 저장',exact=True).click()
        expect(dlg.get_by_text('브라우저 저장한 제목',exact=True)).to_be_visible()
        expect(cal.locator('.cell[data-key="2026-11-06"] .chip').first).to_have_text('브라우저 저장한 제목')
        expect(page.get_by_text('전체 실행 횟수 1',exact=True)).to_be_visible()
        # Visible delete action, confirmation, calendar removal and restore.
        expect(dlg.get_by_role('button',name='일정 삭제',exact=True)).to_have_css('background-color','rgb(255, 241, 240)')
        dlg.get_by_role('button',name='일정 삭제',exact=True).click()
        expect(dlg.get_by_role('button',name='일정 삭제 확인',exact=True)).to_have_css('color','rgb(180, 35, 24)')
        dlg.get_by_role('button',name='일정 삭제 확인',exact=True).click()
        expect(dlg.get_by_role('heading',name='삭제한 일정',exact=True)).to_be_visible()
        expect(cal.locator('.chip').filter(has_text='브라우저 저장한 제목')).to_have_count(0)
        dlg.get_by_role('button',name='복구',exact=True).click()
        expect(cal.locator('.chip').filter(has_text='브라우저 저장한 제목')).to_have_count(1)
        # New event stays open as saved detail, and its calendar row arrives immediately.
        dlg.get_by_role('button',name='팝업 닫기',exact=True).click()
        expect(dlg).not_to_be_visible()
        cal.get_by_role('button',name='＋ 일정 등록',exact=True).click()
        dlg.get_by_label('일정명',exact=True).fill('새 일정 저장')
        dlg.get_by_label('일정명',exact=True).press('Tab')
        dlg.get_by_role('button',name='일정 등록',exact=True).click()
        expect(dlg.get_by_text('새 일정 저장',exact=True)).to_be_visible()
        expect(cal.locator('.cell[data-key="2026-11-06"] .chip').filter(has_text='새 일정 저장')).to_have_count(1)
        expect(page.get_by_text('전체 실행 횟수 1',exact=True)).to_be_visible()
        # Report typing and saving only refresh the report fragment.
        dlg.get_by_role('button',name='팝업 닫기',exact=True).click()
        expect(dlg).not_to_be_visible()
        page.get_by_role('tab',name='일일 기록',exact=True).click()
        expect(page.get_by_text('전체 실행 횟수 1',exact=True)).to_be_visible()
        page.get_by_label('주요 성과 · 진행사항',exact=True).fill('보고서 부분 갱신 확인')
        page.get_by_label('주요 성과 · 진행사항',exact=True).press('Tab')
        page.get_by_role('button',name='임시 저장',exact=True).click()
        expect(page.get_by_text('임시 저장했습니다. 서버에 보관된 기록입니다.',exact=True)).to_be_visible()
        expect(page.get_by_text('전체 실행 횟수 1',exact=True)).to_be_visible()
        expect(page.get_by_label('주요 성과 · 진행사항',exact=True)).to_have_value('보고서 부분 갱신 확인')
        browser.close()
    print('PASS draft discard, field focus, saved detail, immediate calendar refresh and report fragment isolation')
finally:
    server.terminate()
    server.wait(timeout=10)
