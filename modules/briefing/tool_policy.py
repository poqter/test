from __future__ import annotations

from modules.shell.app_registry import APPS


def registered_briefing_tools() -> list[dict[str, str]]:
    groups = {"consultation", "calculators", "analysis", "materials", "official"}
    return [{"tool_code": app.id, "label": app.label, "description": app.description}
            for app in APPS if app.enabled and app.group_id in groups]


def validated_tool_actions(codes) -> list[dict[str, str]]:
    allowed = {row["tool_code"] for row in registered_briefing_tools()}
    selected = []
    for code in codes if isinstance(codes, list) else []:
        if isinstance(code, str) and code in allowed and code not in selected:
            selected.append(code)
    # User/organization permission remains checked by shell navigation at use time.
    return [{"tool_code": code} for code in selected[:2]]
