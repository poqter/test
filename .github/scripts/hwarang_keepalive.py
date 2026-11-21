from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass

import requests
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


@dataclass(frozen=True)
class AppTarget:
    name: str
    url: str
    entry_selector: str | None = None


APP_TARGETS = (
    AppTarget("WORKSPACE", os.getenv("WORKSPACE_URL", "https://hwarang-workspace.streamlit.app"), ".hw-auth-copy h1"),
    AppTarget("CALCULATOR", os.getenv("CALCULATOR_URL", "https://hwarang-calculator.streamlit.app"), ".calc-gate h1"),
    AppTarget("ACADEMY", os.getenv("ACADEMY_URL", "https://hwarang-academy.streamlit.app")),
    AppTarget("CALENDAR", os.getenv("CALENDAR_URL", "https://hwarang-calendar.streamlit.app")),
)


def scheduled_targets():
    academy_enabled = os.getenv("ACADEMY_KEEPALIVE_ENABLED", "").strip().lower() == "true"
    return tuple(target for target in APP_TARGETS if target.name != "ACADEMY" or academy_enabled)


def ping_supabase() -> None:
    """Create a very small Data API read so an active Free project records activity."""
    base_url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    secret_key = os.environ.get("SUPABASE_SECRET_KEY", "").strip()

    if not base_url or not secret_key:
        raise RuntimeError(
            "GitHub Secrets SUPABASE_URL / SUPABASE_SECRET_KEY가 설정되지 않았습니다."
        )

    response = requests.get(
        f"{base_url}/rest/v1/profiles",
        params={"select": "id", "limit": "1"},
        headers={
            "apikey": secret_key,
            "Accept": "application/json",
        },
        timeout=30,
    )
    response.raise_for_status()
    print(f"[OK] Supabase ping: HTTP {response.status_code}")


def wait_for_entry(page, target: AppTarget) -> None:
    deadline = time.monotonic() + 120
    wake_requested = False
    last_state = "waiting for the app entry"
    while time.monotonic() < deadline:
        try:
            for frame in page.frames:
                if frame.locator(target.entry_selector).first.is_visible():
                    print(f"[READY] {target.name}: entry visible; wake_requested={wake_requested}", flush=True)
                    return
                wake = frame.get_by_role("button", name="Yes, get this app back up!", exact=True)
                if not wake_requested and wake.is_visible():
                    wake.click(timeout=5000)
                    wake_requested = True
                    last_state = "wake requested"
                    print(f"[WAKE] {target.name}", flush=True)
                    break
        except PlaywrightError as exc:
            if page.is_closed():
                raise
            last_state = type(exc).__name__
        page.wait_for_timeout(1000)
    raise RuntimeError(f"{target.name}: entry not visible within 120s ({last_state})")


def visit_streamlit_apps() -> None:
    """Open each public Streamlit app as a real browser session without HWARANG login."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="ko-KR",
        )

        failures: list[str] = []
        try:
            for target in scheduled_targets():
                page = context.new_page()
                try:
                    print(f"[VISIT] {target.name}: {target.url}")
                    response = page.goto(
                        target.url,
                        wait_until="domcontentloaded",
                        timeout=90_000,
                    )
                    if response is None or response.status >= 400:
                        raise RuntimeError(f"Navigation failed: HTTP {response.status if response else 'n/a'}")
                    if target.entry_selector:
                        wait_for_entry(page, target)
                    else:
                        page.wait_for_timeout(15_000)
                        print(f"[VISITED] {target.name}: HTTP {response.status}, title={page.title()!r}")
                except PlaywrightTimeoutError as exc:
                    failures.append(f"{target.name}: browser timeout ({exc})")
                except Exception as exc:  # noqa: BLE001 - workflow should report all targets
                    failures.append(f"{target.name}: {type(exc).__name__}: {exc}")
                finally:
                    page.close()
                    # Small gap between apps to avoid burst-loading all Community Cloud apps.
                    time.sleep(2)
        finally:
            context.close()
            browser.close()

        if failures:
            raise RuntimeError("Streamlit visit failure(s): " + " | ".join(failures))


def main() -> int:
    errors: list[str] = []

    try:
        if os.getenv("SUPABASE_KEEPALIVE_ENABLED", "").lower() == "true":
            ping_supabase()
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Supabase: {type(exc).__name__}: {exc}")

    try:
        visit_streamlit_apps()
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Streamlit: {type(exc).__name__}: {exc}")

    if errors:
        print("\n[FAILED] HWARANG keep-alive")
        for error in errors:
            print(f"- {error}")
        return 1

    print("\n[SUCCESS] HWARANG keep-alive completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
