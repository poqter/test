from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.briefing.preflight import preflight_ready, run_runtime_preflight


def main() -> int:
    checks = run_runtime_preflight()
    payload = {
        "ready": preflight_ready(checks),
        "checks": [check.to_dict() for check in checks],
        "note": "No OpenAI API or Direct Source network call is performed by this preflight.",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
