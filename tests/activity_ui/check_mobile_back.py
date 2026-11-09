"""Real browser against Streamlit with synthetic records; no production access."""
from pathlib import Path
import socket
import os
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
        engine=os.environ.get('HW_TEST_BROWSER','chromium')
        browser=getattr(p,engine).launch(headless=True,args=['--no-sandbox'] if engine=='chromium' else [])
        page=browser.new_page(viewport={'width':390,'height':844},user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148')
        page.goto('http://127.0.0.1:8504')
        expect(page.get_by_role('button',name='☰',exact=True)).to_be_visible()
        expect(page.get_by_test_id('stApp')).to_have_attribute('data-test-script-state','notRunning')
        cal=page.frame_locator('iframe[title="modules.activity.center.sales_calendar_view"]')
        assert page.locator('.st-key-mobile_header').bounding_box()['y'] < 24
        expect(page.locator('iframe[title="modules.activity.center.sales_calendar_view"]')).to_be_visible()
        assert page.locator('iframe[title="modules.activity.center.sales_calendar_view"]').bounding_box()['y'] < 200
        page.wait_for_function("history.state?.hwarangCalendarBack === true")
        frame=page.locator('iframe[title="modules.activity.center.sales_calendar_view"]').element_handle().content_frame()
        frame.wait_for_function("calendarLayoutReady && calendarBoot && !calendarLoading")
        # Retiring dialogs can remain in the DOM during the exit transition.
        editor=cal.locator('dialog.calendar-panel[open]')
        base=page.url
        # Settings and drawer close before changing app pages.
        cal.locator('.view-settings > summary').click()
        expect(cal.locator('.view-settings')).to_have_attribute('open','')
        page.go_back()
        expect(cal.locator('.view-settings')).not_to_have_attribute('open','')
        page.get_by_role('button',name='☰',exact=True).click()
        expect(page.locator('[data-testid="stPopoverBody"]')).to_be_visible()
        page.wait_for_timeout(400)
        page.go_back()
        expect(page.locator('[data-testid="stPopoverBody"]')).to_have_count(0)
        # Clean editor uses the same X handler.
        page.get_by_role('button',name='일정 등록',exact=True).click()
        expect(editor).to_be_visible()
        page.wait_for_timeout(400)
        page.go_back()
        expect(cal.get_by_role('dialog')).to_have_count(0)
        # Dirty editor is protected, including repeated Back.
        page.get_by_role('button',name='일정 등록',exact=True).click()
        expect(page.get_by_test_id('stApp')).to_have_attribute('data-test-script-state','notRunning')
        expect(editor).to_be_visible()
        editor.get_by_label('일정명',exact=True).fill('뒤로가기 보존')
        editor.get_by_label('일정명',exact=True).press('Tab')
        frame=page.locator('iframe[title="modules.activity.center.sales_calendar_view"]').element_handle().content_frame()
        try:
            frame.wait_for_function("calendarDraft?.dirty && calendarDraft.values.title==='뒤로가기 보존'",timeout=5000)
        except Exception:
            print('DRAFT_STATE',frame.evaluate("({draft:calendarDraft,panelOpen:calendarPanel?.open,inputs:[...document.querySelectorAll('input[name=title]')].map(e=>({value:e.value,open:e.closest('dialog')?.open,inert:e.closest('dialog')?.inert})),loading:calendarLoading})"),flush=True)
            raise
        page.wait_for_function("history.state?.hwarangCalendarBack === true")
        page.wait_for_timeout(400)
        page.go_back()
        expect(cal.get_by_role('button',name='계속 작성',exact=True)).to_be_visible()
        page.wait_for_timeout(400)
        page.go_back()
        expect(cal.get_by_label('일정명',exact=True)).to_have_value('뒤로가기 보존')
        cal.get_by_role('button',name='저장하지 않고 닫기',exact=True).click()
        expect(cal.get_by_role('dialog')).to_have_count(0)
        # Menu history returns to the actual prior page.
        page.get_by_role('button',name='☰',exact=True).click()
        drawer=page.locator('[data-testid="stPopoverBody"]')
        drawer.get_by_role('button',name='후속 할 일',exact=True).click()
        expect(page.get_by_text('남아 있는 후속 할 일이 없습니다.',exact=False)).to_be_visible()
        page.wait_for_timeout(400)
        page.go_back()
        expect(cal.get_by_role('button',name='내 일정',exact=True)).to_be_visible()
        expect(page.locator('.mobile-navigation-state')).to_have_attribute('data-page','캘린더')
        expect(page.locator('.mobile-navigation-state')).to_have_attribute('data-depth','0')
        page.wait_for_timeout(400)
        page.go_back()
        expect(page.get_by_role('dialog',name='캘린더 나가기')).to_be_visible()
        page.get_by_role('button',name='계속 사용',exact=True).click()
        assert page.url==base
        # Alerts cause full app reruns; handlers must survive component replacement.
        page.locator('.st-key-mobile_alerts button').click()
        expect(page.locator('.mobile-navigation-state')).to_have_attribute('data-page','알림·피드백')
        page.evaluate("document.querySelectorAll('iframe[srcdoc]').forEach(f=>{if(f.srcdoc.includes('calendar-layout-source'))f.remove()})")
        page.wait_for_timeout(400)
        page.go_back()
        expect(page.locator('.mobile-navigation-state')).to_have_attribute('data-page','캘린더')
        browser.close()
    print('PASS browser Back: settings, drawer, clean/dirty editor, menu history, exit cancellation')
finally:
    server.terminate()
    server.wait(timeout=10)
