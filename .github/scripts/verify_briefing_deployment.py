"""Read-only smoke checks for the deployed Streamlit apps."""
import argparse
import ast
import hashlib
import json
import re
import runpy
import time
from pathlib import Path

from playwright.sync_api import Error, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = 'https://hwarang-workspace.streamlit.app/'
CALCULATOR = 'https://hwarang-calculator.streamlit.app/'
MARKER = re.compile(r'\b(HWARANG_[A-Z_]+)=([\w.-]+(?:;READY=(?:true|false))?)')


def workspace_release(ui_release):
    engine = json.loads((ROOT / 'STAGE1_CHANGED_FILES.json').read_text())['engine_version']
    app = ROOT / 'app.py'
    manifest = next(
        ast.literal_eval(node.value) for node in ast.walk(ast.parse(app.read_text()))
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'activity_files'
                for target in node.targets)
    )
    activity = b''.join((ROOT / 'modules/activity' / name).read_bytes() for name in manifest)
    return {
        'HWARANG_BRIEFING_RELEASE': f'{engine};READY=true',
        'HWARANG_ACTIVITY_RELEASE': hashlib.sha256(activity).hexdigest()[:16],
        'HWARANG_LOGIN_RELEASE': hashlib.sha256(app.read_bytes()).hexdigest()[:16],
        'HWARANG_UI_RELEASE': ui_release,
    }


def verify_release(page, app, url, expected, seconds):
    deadline = time.monotonic() + seconds
    last_failure = 'no response'
    print(f'{app}: expected={json.dumps(expected)}', flush=True)
    while (remaining := deadline - time.monotonic()) > 0:
        try:
            response = page.goto(url, wait_until='domcontentloaded',
                                 timeout=max(1, int(min(30, remaining) * 1000)))
            status = response.status if response else None
            poll_until = min(deadline, time.monotonic() + 20)
            while time.monotonic() < poll_until:
                observed = {}
                app_exception = False
                frame_error = None
                for frame in page.frames:
                    try:
                        text = frame.locator('body').inner_text(timeout=1000)
                        markers = dict(MARKER.findall(text))
                        if all(markers.get(key) == value for key, value in expected.items()):
                            print(f'{app}: release verified; observed={json.dumps(markers)}', flush=True)
                            return
                        observed.update({key: value for key, value in markers.items() if key in expected})
                        app_exception |= frame.get_by_test_id('stException').count() > 0
                    except Error as exc:
                        frame_error = exc.__class__.__name__
                missing = sorted(expected.keys() - observed.keys())
                mismatches = {key: observed[key] for key in observed if observed[key] != expected[key]}
                last_failure = (f'HTTP={status}; observed={json.dumps(observed)}; '
                                f'missing={missing}; mismatched={json.dumps(mismatches)}; '
                                f'Streamlit exception={app_exception}; frame read error={frame_error}')
                if app_exception or (status is not None and status >= 400):
                    break
                page.wait_for_timeout(1000)
        except Error as exc:
            last_failure = f'navigation error={exc.__class__.__name__}: {str(exc).splitlines()[0][:200]}'
        print(f'{app}: waiting for expected release; {last_failure}', flush=True)
        page.wait_for_timeout(max(0, int(min(5, deadline - time.monotonic()) * 1000)))
    raise SystemExit(f'{app}: expected release was not observed within {seconds}s. Last check: {last_failure}')


def verify_workspace_entry(browser):
    page = browser.new_page()
    started = time.monotonic()
    page.goto(WORKSPACE, wait_until='domcontentloaded', timeout=45000)
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        frame = next((f for f in page.frames if f.locator('.hw-auth-copy h1').is_visible()), None)
        if frame:
            break
        if any(f.get_by_test_id('stException').count() for f in page.frames):
            raise SystemExit('WORKSPACE login view contains a Streamlit exception.')
        page.wait_for_timeout(500)
    else:
        raise SystemExit('WORKSPACE login form did not appear within 90s.')
    print(f'LOGIN_SCREEN_SECONDS={time.monotonic()-started:.2f}', flush=True)
    frame.locator('.hw-design-2026').wait_for(state='attached', timeout=15000)
    loaded = frame.evaluate("""async () => {
        const faces = await document.fonts.load('700 16px "HW LINE Seed"', '화랑');
        return faces.length > 0 && faces.every(face => face.status === 'loaded');
    }""")
    if not loaded:
        raise SystemExit('WORKSPACE login: LINE Seed font did not load.')
    frame.get_by_text('이 개인 기기에서 30일간 로그인 유지', exact=True).wait_for(state='visible', timeout=45000)
    print('WORKSPACE_ENTRY_OK;LINE_SEED_LOADED;SALES_LOGIN_OPTION_OK', flush=True)
    page.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('app', nargs='?', choices=['workspace', 'calculator'])
    target = parser.parse_args().app
    ui_release = runpy.run_path(str(ROOT / 'modules/shared/build_info.py'))['BUILD_ID']
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        if target != 'calculator':
            page = browser.new_page()
            verify_release(page, 'WORKSPACE', WORKSPACE + '?briefing_health=1',
                           workspace_release(ui_release), 480)
            page.close()
            verify_workspace_entry(browser)
        if target != 'workspace':
            verify_release(browser.new_page(), 'CALCULATOR', CALCULATOR + '?stability_health=1',
                           {'HWARANG_UI_RELEASE': ui_release}, 240)
        browser.close()


if __name__ == '__main__':
    main()
