"""Shortcut uses the canonical device-auth entry, never a login-link gate."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[2]/"modules/activity/calendar_view/pwa/calendar"
TARGET="https://shortcut.test/calendar"
with sync_playwright() as p:
    browser=p.chromium.launch()
    for saved in (False,True):
        page=browser.new_page()
        if saved:page.add_init_script("sessionStorage.setItem('hwarang.calendar.session', '{}')")
        page.route("https://shortcut.test/**",lambda r:r.fulfill(path=str(ROOT/('entry.js' if r.request.url.endswith('entry.js') else 'index.html'))))
        page.route(TARGET,lambda r:r.fulfill(body="<p>Canonical calendar entry</p>"))
        page.goto("https://shortcut.test/index.html")
        page.wait_for_url(TARGET)
        expect(page.get_by_text('WORKSPACE 아이디로 로그인',exact=True)).to_have_count(0)
        page.close()
    browser.close()
print('PASS shortcut redirect with and without legacy session')
