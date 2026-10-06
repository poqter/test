from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.briefing import load_direct_source_specs_from_env, run_phase_b, run_phase_c


def main() -> int:
    phase_b = run_phase_b(direct_sources=load_direct_source_specs_from_env())
    phase_c = run_phase_c(phase_b)
    profiles = {}
    for code in ("INSURANCE", "MARKET", "NEWS"):
        rows = phase_c.profile_rows(code)
        profiles[code] = {
            "analyzed": len(rows),
            "core": sum(r.selection_tier == "core" for r in rows),
            "light_digest": sum(r.selection_tier == "light_digest" for r in rows),
            "excluded": sum(r.selection_tier == "excluded" for r in rows),
            "validation_required": sum(r.validation_status == "required" for r in rows),
            "omitted_by_budget": phase_c.omitted_by_profile.get(code, 0),
            "usage": asdict(phase_c.usage_by_profile[code]) if code in phase_c.usage_by_profile else None,
        }
    payload = {
        "as_of": phase_b.as_of.isoformat(),
        "phase_b": {
            "candidate_count": len(phase_b.candidates),
            "event_count": len(phase_b.events),
            "excluded_counts": phase_b.excluded_counts,
            "search_actions": sum(x.usage.search_actions for x in phase_b.discovery_lanes),
        },
        "phase_c": {"profiles": profiles},
        "note": "This smoke run performs live OpenAI calls when web discovery and Phase C analysis are enabled.",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
