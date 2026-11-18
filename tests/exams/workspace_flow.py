"""Exercise the WORKSPACE CBT entry against the isolated exam database."""
from contextlib import ExitStack
from pathlib import Path
import os
import socket
import subprocess
import sys
import time
from uuid import uuid4

import requests
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
URL = "http://127.0.0.1:8138"
APP = "http://127.0.0.1:8507"
USER = "00000000-0000-4000-8000-000000000001"
MANAGER = "00000000-0000-4000-8000-000000000003"

def rpc(actor, action, **payload):
    response = requests.post(URL, json={"p_actor": actor, "p_action": action, "p_payload": payload}, timeout=15)
    response.raise_for_status()
    return response.json()


def stop(process):
    process.terminate()
    process.wait(timeout=10)


def main():
    with ExitStack() as stack:
        db = subprocess.Popen(["node", "tests/exams/ui_server.mjs"], cwd=ROOT, stdout=subprocess.PIPE, text=True)
        stack.callback(stop, db)
        assert db.stdout.readline().strip() == "ready"
        exam = rpc(USER, "start", id=str(uuid4()), exam_id="nonlife-test-0", track="main", mode="practice")
        rpc(USER, "save", id=exam["id"], revision=exam["revision"], answers={"1": 2}, flags=[1], cursor=0)
        app = subprocess.Popen([
            sys.executable, "-m", "streamlit", "run", "tests/exams/workspace_harness.py",
            "--server.headless=true", "--server.address=127.0.0.1", "--server.port=8507",
        ], cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)})
        stack.callback(stop, app)
        for _ in range(100):
            try:
                with socket.create_connection(("127.0.0.1", 8507), timeout=.2):
                    break
            except OSError:
                time.sleep(.2)
        browser = stack.enter_context(sync_playwright()).chromium.launch()
        stack.callback(browser.close)
        page = browser.new_page()
        page.goto(APP)
        page.get_by_role("button", name="보험시험 CBT 열기").click()
        expect(page.get_by_role("tab", name="조직 학습 현황")).to_have_count(0)
        page.get_by_role("button", name="이어서 풀기", exact=True).click()
        expect(page.locator('iframe[title*="hwarang_cbt"]')).to_be_visible()
        saved = rpc(USER, "get", id=exam["id"])
        assert saved["answers"] == {"1": 2} and saved["flags"] == [1]
        page.get_by_role("button", name="시험 중단", exact=True).click()
        page.get_by_role("button", name="시험 중단 확정").click()
        expect(page.get_by_text("시험을 중단했습니다. 새 시험을 시작할 수 있습니다.")).to_be_visible()
        stopped = rpc(USER, "get", id=exam["id"])
        assert stopped["status"] == "aborted" and stopped["result"] is None and stopped["answers"] == {"1": 2}
        page.get_by_role("button", name="시작하기", exact=True).click()
        expect(page.locator('iframe[title*="hwarang_cbt"]')).to_be_visible()
        fresh, = [row for row in rpc(USER, "list") if row["status"] == "active"]
        assert fresh["id"] != exam["id"]
        manager = browser.new_page(viewport={"width": 390, "height": 844})
        manager.goto(APP + "/?manager=1")
        manager.get_by_role("button", name="보험시험 CBT 열기").click()
        manager.get_by_role("tab", name="조직 학습 현황").click()
        expect(manager.get_by_role("button", name="사용자1 →")).to_be_visible()
        expect(manager.get_by_role("button", name="사용자2 →")).to_have_count(0)
        assert {member["id"] for member in rpc(MANAGER, "roster")} == {USER, MANAGER}
        manager.get_by_role("button", name="사용자1 →").click()
        expect(manager.get_by_role("button", name="← 학습자 목록")).to_be_visible()
        print("PASS WORKSPACE CBT: existing answer, resume, abort, fresh attempt, scoped manager roster")


if __name__ == "__main__":
    main()
