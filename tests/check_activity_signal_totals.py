"""Compare both manager views with each snapshot from the same isolated PostgreSQL run."""
import json
from datetime import date, datetime
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.activity.manager import summarize
from modules.activity.period_summary import daily_rows, date_table, period_bounds, totals


def main():
    raw = subprocess.check_output(["node", "tests/activity_report_signals.mjs"], cwd=ROOT)
    fixture = json.loads(raw)
    worker = fixture["worker"]
    members = {worker: {"label": "직원"}}
    anchor = date(2025, 11, 18)
    now = datetime(2025, 11, 18, 12)
    for reports, expected in zip(fixture["snapshots"], (5, 5, 9), strict=True):
        for mode, ap in (("주간", expected), ("월간", expected + 3)):
            start, end = period_bounds(anchor, mode)
            row, = summarize(members, [], reports, [], [], start, end, anchor, now)
            by_date = date_table(reports, start, end, members, anchor)
            assert row["counts"] == totals(daily_rows(reports, start, end, members))
            assert row["counts"]["AP"] == sum(r["AP"] for r in by_date) == ap
            assert row["submitted"] == (2 if mode == "주간" else 3)
            assert row["counts"] == {"TA":2, "AP":ap, "PC":3, "CS":1, "약속 확보":4, "청약":1}
            assert row["contracts"] == 1
            status = {r["날짜"][:5]: r["제출"] for r in by_date}
            assert status["11/17"] == "1/1명"  # Submitted with all zeros.
            if mode == "월간":
                assert status["11/14"] == "0/1명"
    print("PASS: signal increments, notices, date move, stale revision, authorized weekly/monthly manager totals")


if __name__ == "__main__":
    main()
