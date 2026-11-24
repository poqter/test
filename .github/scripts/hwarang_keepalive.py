from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import sys
import time
from dataclasses import dataclass

from playwright.sync_api import Error as PlaywrightError
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
    AppTarget("CALENDAR", os.getenv("CALENDAR_URL", "https://hwarang-calendar.streamlit.app"), '.hw-auth-copy h1, [data-testid="stForm"] button:has-text("캘린더 로그인")'),
)


def scheduled_targets():
    academy_enabled = os.getenv("ACADEMY_KEEPALIVE_ENABLED", "").strip().lower() == "true"
    return tuple(target for target in APP_TARGETS if target.name != "ACADEMY" or academy_enabled)


def wait_for_entry(page, target: AppTarget, observation=None) -> bool:
    deadline = time.monotonic() + 120
    wake_requested = False
    last_state = "waiting for the app entry"
    while time.monotonic() < deadline:
        try:
            for frame in page.frames:
                if frame.locator(target.entry_selector).first.is_visible():
                    print(f"[READY] {target.name}: entry visible; wake_requested={wake_requested}", flush=True)
                    return wake_requested
                wake = frame.get_by_role("button", name="Yes, get this app back up!", exact=True)
                if not wake_requested and wake.is_visible():
                    if observation is not None:
                        observation["sleep"] = True
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

        try:
            return check_targets(context, scheduled_targets())
        finally:
            context.close()
            browser.close()


def now_kst():
    return datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")


def check_targets(context, targets):
    rows = {}
    for attempt in (1, 2):
        for target in targets:
            row = rows.setdefault(target.name, {"result": "FAILED", "sleep": False,
                                                "start": None, "entry": "—", "seconds": 0.0})
            if row["result"] != "FAILED":
                continue
            started = time.monotonic()
            row["start"] = row["start"] or now_kst()
            row["attempt"] = attempt
            try:
                page = context.new_page()
                try:
                    response = page.goto(target.url, wait_until="domcontentloaded", timeout=40_000)
                    if response is None or response.status >= 400:
                        raise RuntimeError("Navigation failed")
                    if not target.entry_selector:
                        raise RuntimeError("Missing entry selector")
                    wait_for_entry(page, target, row)
                    row["entry"] = now_kst()
                    row["result"] = "RETRY_SUCCESS" if attempt == 2 else (
                        "RECOVERED" if row["sleep"] else "READY"
                    )
                finally:
                    page.close()
            except Exception as exc:
                print(f"[ERROR] {target.name} attempt={attempt} {type(exc).__name__}: {exc}", flush=True)
            finally:
                row["seconds"] += time.monotonic() - started
    lines = ["| App | Start (KST) | Entry (KST) | Active seconds | Sleep observed | Retried | Result |",
             "|---|---|---|---:|---|---|---|"]
    for name, row in rows.items():
        lines.append(f"| {name} | {row['start']} | {row['entry']} | {row['seconds']:.1f} | "
                     f"{row['sleep']} | {row['attempt'] == 2} | {row['result']} |")
    for name in ("ACADEMY", "SUPABASE"):
        if name not in rows:
            lines.append(f"| {name} | — | — | — | — | — | SKIPPED |")
    report = "\n".join(lines)
    print(report, flush=True)
    if summary := os.getenv("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as stream:
            print(report, file=stream)
    if any(row["result"] == "FAILED" for row in rows.values()):
        raise RuntimeError("Streamlit entry verification failed")


def main() -> int:
    errors: list[str] = []

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
