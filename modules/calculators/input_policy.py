"""Versioned money-field policy. Exact won is the conservative fallback."""
from functools import lru_cache
import json
from pathlib import Path

@lru_cache(maxsize=1)
def _policies():
    path = Path(__file__).resolve().parents[2] / "data/calculator_input_policies.json"
    return json.loads(path.read_text(encoding="utf-8"))["calculators"]


def policy_for_field(name, index, label=""):
    record = _policies().get(name, {}).get(str(index))
    # A changed field layout must not silently inherit a previous field policy.
    if record and record.get("label") == label:
        return record["policy"]
    return "exact_won"
