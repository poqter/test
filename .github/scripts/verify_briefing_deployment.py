"""Verify the deployed Streamlit release without signing in or invoking AI."""
import time
from playwright.sync_api import sync_playwright
from pathlib import Path
import json
# Read release metadata without importing the app's optional runtime dependencies.
ENGINE_VERSION = json.loads(
    (Path(__file__).resolve().parents[2] / 'STAGE1_CHANGED_FILES.json').read_text()
)['engine_version']

expected=f'HWARANG_BRIEFING_RELEASE={ENGINE_VERSION};READY=true'
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page()
    deadline=time.monotonic()+480
    ready=False
    while time.monotonic()<deadline:
        try:
            page.goto('https://hwarang-workspace.streamlit.app/?briefing_health=1',wait_until='domcontentloaded',timeout=45000)
            for _ in range(20):
                if any(expected in frame.locator('body').inner_text(timeout=2000)
                       for frame in page.frames):
                    break
                page.wait_for_timeout(1000)
            else:
                raise RuntimeError('Release not ready in app frame')
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
    for _ in range(30):
        if any(frame.get_by_test_id('stAppViewContainer').count() for frame in page.frames):
            break
        page.wait_for_timeout(1000)
    else:
        raise SystemExit('Workspace app frame did not load.')
    page.wait_for_timeout(3000)
    if any(frame.get_by_test_id('stException').count() for frame in page.frames):
        raise SystemExit('Workspace login view contains a Streamlit exception.')
    frame=next(frame for frame in page.frames if frame.get_by_test_id('stAppViewContainer').count())
    frame.locator('.hw-design-2026').wait_for(state='attached', timeout=15000)
    loaded=frame.evaluate("""async () => {
        const faces = await document.fonts.load('700 16px "HW LINE Seed"', '화랑');
        return faces.length > 0 && faces.every(face => face.status === 'loaded');
    }""")
    if not loaded:
        raise SystemExit('LINE Seed font did not load.')
    heading=frame.locator('.hw-auth-copy h1')
    if not heading.is_visible():
        raise SystemExit('Login heading is not visible.')
    print('WORKSPACE_ENTRY_OK;LINE_SEED_LOADED')
    browser.close()
