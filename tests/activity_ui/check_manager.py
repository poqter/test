"""Manager and member navigation in real browsers, using synthetic records only."""
from pathlib import Path
import socket
import subprocess
import sys
import time
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[2]
server=subprocess.Popen([sys.executable,'-m','streamlit','run',str(ROOT/'tests/activity_ui/harness.py'),'--server.headless=true','--server.port=8506','--server.address=127.0.0.1','--browser.gatherUsageStats=false'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
    for _ in range(150):
        try:
            with socket.create_connection(('127.0.0.1',8506),timeout=.2):break
        except OSError:time.sleep(.2)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
        for mobile in (False,True):
            page=browser.new_page(viewport={'width':390 if mobile else 1280,'height':844 if mobile else 900},user_agent='Mozilla/5.0 (Linux; Android 14) Mobile' if mobile else None)
            page.route('**/app/static/LINESeedKR-Bd.woff2',lambda route:route.fulfill(path=str(ROOT/'static/LINESeedKR-Bd.woff2'),content_type='font/woff2'))
            page.goto('http://127.0.0.1:8506')
            page.get_by_role('tab',name='구성원 현황',exact=True).click()
            expect(page.get_by_label('상세 직원',exact=True)).to_be_visible()
            page.get_by_role('radio',name='직원별',exact=True).click()
            expect(page.locator('.st-key-manager_table')).to_be_visible()
            page.evaluate('document.fonts.ready')
            full_runs=page.get_by_text('전체 실행 횟수',exact=False).inner_text()
            if mobile:
                page.get_by_role('button',name='테스트 작성자 ›',exact=True).click()
                dlg=page.get_by_role('dialog')
                strip=dlg.locator('.st-key-member_date_strip')
                expect(strip.locator('button')).to_have_count(5)
                expect(dlg.get_by_role('button',name='✓ 완료',exact=True)).to_have_count(0)
                expect(dlg.get_by_text('일일 활동 기록',exact=True)).to_be_visible()
                expect(dlg.get_by_text('일정',exact=True)).to_be_visible()
                assert dlg.bounding_box()['width']<=page.viewport_size['width']
                assert dlg.locator('.st-key-sales_dialog_body').evaluate('e=>e.scrollWidth<=e.clientWidth+1')
                expect(page.get_by_test_id('stApp')).to_have_attribute('data-test-script-state','notRunning')
                full_runs=page.get_by_text('전체 실행 횟수',exact=False).inner_text()
                weekend=dlg.get_by_role('switch',name='주말 포함',exact=True)
                weekend.focus();weekend.press('Space')
                expect(weekend).to_be_checked()
                expect(strip.locator('button')).to_have_count(7)
                dlg.get_by_role('button',name='›',exact=True).click()
                expect(strip.locator('button').first).not_to_contain_text('11/02')
                expect(page.get_by_text(full_runs,exact=True)).to_be_visible()
                dlg.get_by_role('button',name='✕',exact=True).click()
                expect(dlg).not_to_be_visible()
            else:
                page.get_by_role('button',name='테스트 작성자',exact=True).click()
                detail=page.locator('.st-key-manager_detail')
                expect(detail.get_by_role('heading',name='테스트 작성자',exact=True)).to_be_visible()
                expect(detail.get_by_text('제출된 일일 기록',exact=True)).to_be_visible()
                expect(detail.get_by_role('button',name='✓ 완료',exact=True)).to_have_count(0)
                expect(detail.get_by_role('radio',name='11.06 미작성',exact=True)).to_be_visible()
                detail.get_by_role('button',name='다음 ›',exact=True).click()
                expect(detail.get_by_role('heading',name='테스트 구성원',exact=True)).to_be_visible()
                detail.get_by_role('button',name='‹ 이전',exact=True).click()
                expect(detail.get_by_role('heading',name='테스트 작성자',exact=True)).to_be_visible()
                assert detail.evaluate('e=>e.scrollWidth<=e.clientWidth+1')
                expect(page.get_by_text(full_runs,exact=True)).to_be_visible()
            page.get_by_label('직원 이름 검색',exact=True).fill('구성원')
            page.get_by_label('직원 이름 검색',exact=True).press('Tab')
            expect(page.get_by_text('검색 결과 1명 / 조회 범위 2명',exact=True)).to_be_visible()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=f'/tmp/manager-{mobile}.png',full_page=True)
            expect(page.locator('[data-testid="stException"]')).to_have_count(0)
            page.close()
        browser.close()
    print('MANAGER_UI_OK desktop/mobile summaries, member weekdays, weekends, navigation, body overflow and fragment isolation')
finally:
    server.terminate();server.wait(timeout=10)
