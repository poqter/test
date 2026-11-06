"""Verify the deployed Streamlit release without signing in or invoking AI."""
import time
from playwright.sync_api import sync_playwright
from pathlib import Path
import json
import hashlib
# Read release metadata without importing the app's optional runtime dependencies.
ENGINE_VERSION = json.loads(
    (Path(__file__).resolve().parents[2] / 'STAGE1_CHANGED_FILES.json').read_text()
)['engine_version']

expected=f'HWARANG_BRIEFING_RELEASE={ENGINE_VERSION};READY=true'
activity_root=Path(__file__).resolve().parents[2]/'modules/activity'
activity_expected='HWARANG_ACTIVITY_RELEASE='+hashlib.sha256(b''.join((activity_root/name).read_bytes() for name in ('center.py','redesign.py','manager.py','ux.py','contracts.py','calendar_view/index.html','mobile.py','device.py'))).hexdigest()[:16]
login_expected='HWARANG_LOGIN_RELEASE='+hashlib.sha256((activity_root.parents[1]/'app.py').read_bytes()).hexdigest()[:16]
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page()
    deadline=time.monotonic()+480
    ready=False
    while time.monotonic()<deadline:
        try:
            page.goto('https://hwarang-workspace.streamlit.app/?briefing_health=1',wait_until='domcontentloaded',timeout=45000)
            for _ in range(20):
                if any(expected in (body:=frame.locator('body').inner_text(timeout=2000)) and activity_expected in body and login_expected in body
                       for frame in page.frames):
                    break
                page.wait_for_timeout(1000)
            else:
                raise RuntimeError('Release not ready in app frame')
            ready=True
            print('DEPLOYED_RELEASE_OK '+ENGINE_VERSION+';'+activity_expected)
            break
        except Exception:
            print('Waiting for Streamlit main deployment',flush=True)
            page.wait_for_timeout(10000)
    if not ready:
        browser.close()
        raise SystemExit('Expected deployed release was not observed. Check Streamlit deployment logs.')
    # Start an independent visit so a still-mounted health screen cannot be selected.
    page.close()
    page=browser.new_page()
    started=time.monotonic()
    page.goto('https://hwarang-workspace.streamlit.app/',wait_until='domcontentloaded',timeout=45000)
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        frame=next((f for f in page.frames if f.locator('.hw-auth-copy h1').is_visible()), None)
        if frame:
            break
        if any(f.get_by_test_id('stException').count() for f in page.frames):
            raise SystemExit('Workspace login view contains a Streamlit exception.')
        page.wait_for_timeout(500)
    else:
        from urllib.parse import urlsplit
        for f in page.frames:
            try:
                print('ENTRY_FRAME', urlsplit(f.url).hostname, 'TITLE', f.title()[:120],
                      'PUBLIC_ENTRY_TEXT', f.locator('body').inner_text(timeout=2500)[:400], flush=True)
            except Exception:
                pass
        raise SystemExit('Workspace login form did not appear.')
    print(f'LOGIN_SCREEN_SECONDS={time.monotonic()-started:.2f}')
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
    remember=frame.get_by_text('이 개인 기기에서 30일간 로그인 유지',exact=True)
    remember.wait_for(state='visible',timeout=45000)
    print('WORKSPACE_ENTRY_OK;LINE_SEED_LOADED;SALES_LOGIN_OPTION_OK')
    browser.close()
