"""Verify the deployed Streamlit release without signing in or invoking AI."""
import time
from playwright.sync_api import sync_playwright
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from modules.briefing.diagnostics import ENGINE_VERSION

expected=f'HWARANG_BRIEFING_RELEASE={ENGINE_VERSION};READY=true'
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page()
    deadline=time.monotonic()+480
    ready=False
    while time.monotonic()<deadline:
        try:
            page.goto('https://hwarang-workspace.streamlit.app/?briefing_health=1',wait_until='domcontentloaded',timeout=45000)
            page.get_by_text(expected,exact=False).wait_for(timeout=20000)
            ready=True
            print('DEPLOYED_RELEASE_OK '+ENGINE_VERSION)
            break
        except Exception:
            print('Waiting for Streamlit main deployment',flush=True)
            page.wait_for_timeout(10000)
    if not ready:
        browser.close()
        raise SystemExit('Expected deployed release was not observed. Check Streamlit deployment logs.')
    page.goto('https://hwarang-workspace.streamlit.app/',wait_until='domcontentloaded',timeout=45000)
    page.get_by_test_id('stAppViewContainer').wait_for(timeout=30000)
    page.wait_for_timeout(3000)
    if page.get_by_test_id('stException').count():
        raise SystemExit('Workspace login view contains a Streamlit exception.')
    print('WORKSPACE_ENTRY_OK')
    browser.close()
