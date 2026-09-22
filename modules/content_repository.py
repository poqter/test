"""Read packaged editorial templates only; never write user content."""
import json
from pathlib import Path

CONTENT_FILES = {
    "customer_material_templates": {"templates": dict},
    "consultation_topics": {"lifecycles": dict, "questions": list, "goals": list, "visits": list},
    "consultation_scripts": {"scripts": dict, "reactions": dict},
    "message_templates": {"intros": dict, "messages": dict},
    "checklists": {"preparation": list, "explanation": list, "next_meeting": list},
}


def load_content(name):
    if name not in CONTENT_FILES:
        raise ValueError("Unknown packaged content name")
    path = Path(__file__).resolve().parents[1] / "data" / (name + ".json")
    with path.open(encoding="utf-8") as source:
        data = json.load(source)
    if data.get("schema_version") != 1 or not data.get("source") or not data.get("edited_at"):
        raise ValueError("Content metadata is missing")
    for key, expected in CONTENT_FILES[name].items():
        value = data.get(key)
        if not isinstance(value, expected) or not value:
            raise ValueError("Content section is missing: " + key)
        values = value.values() if isinstance(value, dict) else value
        for item in values:
            items = item if isinstance(item, list) else [item]
            if not items or any(not isinstance(text, str) or not text.strip() for text in items):
                raise ValueError("Content contains empty or invalid text")
    return data
