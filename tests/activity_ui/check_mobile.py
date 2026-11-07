"""Real browser against Streamlit with synthetic records; no production access."""
from pathlib import Path
import socket
import subprocess
import sys
import time
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[2]
server=subprocess.Popen([sys.executable,'-m','streamlit','run',str(ROOT/'tests/activity_ui/mobile_harness.py'),
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
        page=browser.new_page(viewport={'width':390,'height':844},user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148')
        page.goto('http://127.0.0.1:8504')
        expect(page.get_by_role('button',name='☰',exact=True)).to_be_visible()
        cal=page.frame_locator('iframe[title="modules.activity.center.sales_calendar_view"]')
        assert page.locator('.st-key-mobile_header').bounding_box()['y'] < 24
        expect(page.locator('iframe[title="modules.activity.center.sales_calendar_view"]')).to_be_visible()
        assert page.locator('iframe[title="modules.activity.center.sales_calendar_view"]').bounding_box()['y'] < 200
        for mode in ('주간','월간','날짜별','월간'):
            cal.get_by_role('button',name=mode,exact=True).click()
            expect(cal.get_by_role('button',name=mode,exact=True)).to_have_attribute('aria-pressed','true')
        cal.get_by_role('button',name='조회 대상 · 내 일정',exact=True).click()
        expect(cal.get_by_role('dialog')).to_be_visible()
        cal.get_by_label('직원 이름 검색 · 선택',exact=True).select_option('team')
        cal.get_by_role('button',name='적용',exact=True).click()
        expect(cal.get_by_role('button',name='조회 대상 · 지점 일정',exact=True)).to_be_visible()
        cal.get_by_role('button',name='조회 대상 · 지점 일정',exact=True).click()
        cal.get_by_label('직원 이름 검색 · 선택',exact=True).select_option('my')
        cal.get_by_role('button',name='적용',exact=True).click()
        cal.locator('.view-settings > summary').click()
        expect(cal.get_by_label('주말 표시',exact=True)).not_to_be_checked()
        expect(cal.get_by_role('button',name='모바일 앱 열기',exact=True)).to_have_count(0)
        cal.get_by_role('button',name='보기 설정 닫기').click()
        cal.get_by_role('button',name='2026-11-05 일정 보기',exact=True).click()
        expect(cal.locator('#agenda h3')).to_contain_text('11월 5일')
        expect(cal.get_by_role('dialog')).to_have_count(0)
        import os
        if os.environ.get('ACTIVITY_SCREENSHOT'):page.screenshot(path=os.environ['ACTIVITY_SCREENSHOT'],full_page=True)
        page.get_by_role('button',name='일정 등록',exact=True).click()
        expect(cal.get_by_role('dialog')).to_be_visible()
        assert cal.get_by_role('dialog').bounding_box()['height'] <= page.viewport_size['height']
        expect(cal.get_by_label('날짜',exact=True)).to_have_value('2026-11-05')
        cal.get_by_role('button',name='팝업 닫기',exact=True).click()
        expect(cal.get_by_role('dialog')).to_have_count(0)
        page.get_by_role('button',name='☰',exact=True).click()
        drawer=page.locator('[data-testid="stPopoverBody"]').filter(has=page.locator('.mobile-drawer'))
        expect(drawer.get_by_role('button',name='오늘의 업무',exact=True)).to_have_count(0)
        drawer.get_by_role('button',name='패널 닫기').click()
        expect(drawer).not_to_be_visible()
        page.get_by_role('button',name='☰',exact=True).click()
        drawer.get_by_role('button',name='활동 기록',exact=True).click()
        expect(drawer).not_to_be_visible()
        expect(page.get_by_label('주요 성과 · 진행사항',exact=True)).to_be_visible()
        page.get_by_label('주요 성과 · 진행사항',exact=True).fill('모바일에서 보관할 내용')
        page.get_by_label('주요 성과 · 진행사항',exact=True).press('Tab')
        page.wait_for_timeout(700)
        page.get_by_role('button',name='☰',exact=True).click()
        drawer.get_by_role('button',name='후속 할 일',exact=True).click()
        page.get_by_role('button',name='내용 유지하고 이동',exact=True).click()
        expect(page.get_by_text('남아 있는 후속 할 일이 없습니다.',exact=False)).to_be_visible()
        page.get_by_role('button',name='☰',exact=True).click()
        drawer.get_by_role('button',name='활동 기록',exact=True).click()
        expect(page.get_by_label('주요 성과 · 진행사항',exact=True)).to_have_value('모바일에서 보관할 내용')
        page.get_by_role('button',name='임시 저장',exact=True).click()
        expect(page.get_by_text('임시 저장했습니다. 서버에 보관된 기록입니다.',exact=True)).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.get_by_role('button',name='☰',exact=True).click()
        drawer.get_by_role('button',name='구성원 현황',exact=True).click()
        expect(page.get_by_role('button',name='테스트 구성원 ›',exact=True)).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.get_by_role('button',name='☰',exact=True).click()
        drawer.get_by_role('button',name='활동 기록',exact=True).click()
        page.get_by_role('button',name='주간 기록',exact=True).click()
        page.get_by_role('button',name='활동 합계 · 제출 현황',exact=True).click()
        reference=page.locator('[data-testid="stPopoverBody"]').filter(has=page.locator('.sales-reference'))
        reference.get_by_role('button',name='패널 닫기').click()
        expect(reference).not_to_be_visible()
        page.get_by_role('button',name='일일 기록',exact=True).click()
        browser.close()
    print('PASS mobile drawer, permission-aware menus, report persistence and narrow viewport')
finally:
    server.terminate()
    server.wait(timeout=10)
