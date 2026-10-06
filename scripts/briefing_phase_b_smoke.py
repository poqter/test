from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.briefing import load_direct_source_specs_from_env, run_phase_b


def main() -> int:
    result = run_phase_b(direct_sources=load_direct_source_specs_from_env())
    payload = {
        "as_of": result.as_of.isoformat(),
        "candidate_count": len(result.candidates),
        "event_count": len(result.events),
        "excluded_counts": result.excluded_counts,
        "lanes": [
            {
                "lane_code": row.lane_code,
                "profile_code": row.profile_code,
                "search_performed": row.search_performed,
                "retry_used": row.retry_used,
                "candidate_count": len(row.candidates),
                "web_tool_calls": row.usage.web_tool_calls,
                "search_actions": row.usage.search_actions,
                "input_tokens": row.usage.input_tokens,
                "output_tokens": row.usage.output_tokens,
            }
            for row in result.discovery_lanes
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
