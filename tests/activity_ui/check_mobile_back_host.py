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
        page.route('http://127.0.0.1:8504/wrapper',lambda r:r.fulfill(body='<iframe id="app" src="/" style="width:100%;height:800px"></iframe>'))
        page.goto('http://127.0.0.1:8504/wrapper')
        app=page.frame_locator('#app')
        expect(app.locator('.st-key-mobile_alerts button')).to_be_visible()
        page.wait_for_function('history.state?.hwarangCalendarBack === true')
        app.locator('.st-key-mobile_alerts button').click()
        expect(app.locator('.mobile-navigation-state')).to_have_attribute('data-page','알림·피드백')
        page.go_back()
        expect(app.locator('.mobile-navigation-state')).to_have_attribute('data-page','캘린더')
        app.get_by_role('button',name='☰',exact=True).click()
        page.wait_for_timeout(400)
        page.go_back()
        expect(app.locator('[data-testid="stPopoverBody"]')).to_have_count(0)
        page.wait_for_timeout(400)
        page.go_back()
        expect(app.get_by_role('dialog',name='캘린더 나가기')).to_be_visible()
        app.get_by_role('button',name='계속 사용',exact=True).click()
        assert page.url.endswith('/wrapper')
        browser.close()
    print('PASS outer host history, alerts rerun, drawer and in-app exit confirmation')
finally:
    server.terminate()
    server.wait(timeout=10)
