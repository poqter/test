"""Daily report UX regression with synthetic records and no production writes."""
from pathlib import Path
import socket,subprocess,sys,time
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[2]
server=subprocess.Popen([sys.executable,'-m','streamlit','run',str(ROOT/'tests/activity_ui/harness.py'),'--server.headless=true','--server.port=8507','--server.address=127.0.0.1','--browser.gatherUsageStats=false'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
    for _ in range(150):
        try:
            with socket.create_connection(('127.0.0.1',8507),timeout=.2):break
        except OSError:time.sleep(.2)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
        for mobile in (False,True):
            page=browser.new_page(viewport={'width':390 if mobile else 1280,'height':844 if mobile else 900},user_agent='Mozilla/5.0 (Linux; Android 14) Mobile' if mobile else None)
            page.route('**/app/static/LINESeedKR-Bd.woff2',lambda route:route.fulfill(path=str(ROOT/'static/LINESeedKR-Bd.woff2'),content_type='font/woff2'))
            page.goto('http://127.0.0.1:8507')
            page.get_by_role('tab',name='일일 기록',exact=True).click()
            expect(page.get_by_label('AP',exact=True)).to_be_visible()
            page.wait_for_timeout(700) # Let the menu's app run finish before measuring fragment runs.
            full_runs=page.get_by_text('전체 실행 횟수',exact=False).inner_text()
            record=page.locator('.st-key-daily_record')
            expect(record.locator('.sales-summary')).to_contain_text('2026.11.06')
            expect(record.locator('.st-key-daily_inputs').get_by_role('spinbutton')).to_have_count(6)
            assert record.get_by_label('전화',exact=True).count()==0
            field=record.get_by_label('AP',exact=True)
            field.fill('7');field.press('Tab')
            note=record.get_by_label('주요 성과 · 진행사항',exact=True)
            note.fill('일정 참고 후에도 유지할 내용');note.press('Tab')
            record.get_by_text('지원 요청 · 선택',exact=True).click()
            record.get_by_label('지원받을 내용',exact=True).fill('동행 요청')
            record.get_by_label('지원받을 내용',exact=True).press('Tab')
            expect(record.get_by_label('지원받을 내용',exact=True)).to_be_visible()
            if mobile:
                options=record.get_by_role('radiogroup',name='일일 기록 화면')
                options.get_by_role('radio').nth(1).click()
                expect(record.locator('.st-key-daily_inputs').get_by_role('spinbutton')).to_have_count(0)
                record.get_by_role('button',name='상담 테스트',exact=True).click()
                dlg=page.get_by_role('dialog')
                expect(dlg).to_be_visible()
                dlg.get_by_role('button',name='✕',exact=True).click()
                expect(dlg).not_to_be_visible()
                page.wait_for_timeout(700) # Native dialog close completes an app run.
                full_runs=page.get_by_text('전체 실행 횟수',exact=False).inner_text()
                options.get_by_role('radio',name='기록 작성',exact=True).click()
                expect(field).to_have_value('7')
                expect(note).to_have_value('일정 참고 후에도 유지할 내용')
                inputs=record.locator('[data-testid="stNumberInput"]')
                assert abs(inputs.nth(0).bounding_box()['y']-inputs.nth(1).bounding_box()['y'])<2
                assert inputs.nth(2).bounding_box()['y']>inputs.nth(0).bounding_box()['y']
            else:
                inputs=record.locator('[data-testid="stNumberInput"]')
                assert abs(inputs.nth(0).bounding_box()['y']-inputs.nth(1).bounding_box()['y'])<2
            record.get_by_role('button',name='임시 저장',exact=True).click()
            expect(page.get_by_text('임시 저장했습니다. 서버에 보관된 기록입니다.',exact=True)).to_be_visible()
            expect(note).to_have_value('일정 참고 후에도 유지할 내용')
            expect(field).to_have_value('7')
            expect(page.get_by_text(full_runs,exact=True)).to_be_visible()
            record.get_by_role('button',name='제출하기',exact=True).click()
            record.get_by_role('button',name='제출 확인',exact=True).click()
            expect(record.get_by_role('button',name='수정 내용 제출',exact=True)).to_be_disabled()
            expect(page.locator('[data-testid="stException"]')).to_have_count(0)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.evaluate("document.fonts.load('700 16px \"HW LINE Seed\"','화랑')")
            page.evaluate('document.fonts.ready')
            page.screenshot(path=f'/tmp/daily-{mobile}.png',full_page=True)
            # The footer remains reachable without covering focused input.
            footer=record.locator('.st-key-daily_footer')
            footer.scroll_into_view_if_needed()
            expect(footer.get_by_role('button',name='임시 저장',exact=True)).to_be_visible()
            assert abs(footer.get_by_role('button',name='임시 저장',exact=True).bounding_box()['y']-footer.get_by_role('button',name='수정 내용 제출',exact=True).bounding_box()['y'])<2
            assert page.evaluate('!!window.__hwarangDailyLayout')

            page.close()
        browser.close()
    print('DAILY_UI_OK: six fields, desktop/mobile grids, reference tabs, stable help, persistence, single submission and fragment isolation')
finally:
    server.terminate();server.wait(timeout=10)
