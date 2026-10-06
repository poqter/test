"""Read-only presentation of stored snapshots; no model, HTTP or DB calls."""
from __future__ import annotations

from typing import Any
from datetime import datetime
from zoneinfo import ZoneInfo

from .normalize import is_safe_url
from .tool_policy import registered_briefing_tools, validated_tool_actions

COMM_LABELS = {
    "customer_ready": "바로 설명 가능",
    "consultation_reference": "상담 참고",
    "internal_check": "내부 확인",
    "do_not_mention": "고객 언급 금지",
    "not_applicable": "해당 없음",
}
COMM_GUIDANCE = {
    "customer_ready": "확인된 사실 범위에서 안내할 수 있습니다. 고객의 계약·상황은 별도로 확인하세요.",
    "consultation_reference": "상담을 준비하는 참고 자료입니다. 적용 조건을 확인한 뒤 표현을 정리하세요.",
    "internal_check": "내부 확인을 먼저 진행하세요. 고객 전달 문구를 제공하지 않습니다.",
    "do_not_mention": "고객 대화에 사용하지 마세요. 확인할 항목만 내부에서 검토하세요.",
    "not_applicable": "이 뉴스에는 별도의 상담 연결을 제안하지 않습니다.",
}


def communication_state(action: dict[str, Any] | None) -> str:
    state = str((action or {}).get("communication_state") or "internal_check")
    return state if state in COMM_LABELS else "internal_check"


def published_kst(value: Any) -> str:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return "게시 시각 확인 필요"
        return dt.astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y.%m.%d %H:%M KST")
    except (ValueError, TypeError, OverflowError):
        return "게시 시각 확인 필요"


def issue_sources(issue: dict[str, Any], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    by_id = {str(s.get("id")): s for s in bundle.get("sources") or [] if s.get("id")}
    result, seen = [], set()
    for rel in bundle.get("issue_sources") or []:
        if str(rel.get("issue_id")) != str(issue.get("id")):
            continue
        source = by_id.get(str(rel.get("source_id"))) or {}
        url = str(source.get("canonical_url") or source.get("url") or "")
        if is_safe_url(url) and url not in seen:
            seen.add(url)
            result.append({**source, "url": url})
    return result


def issue_validation(issue: dict[str, Any], bundle: dict[str, Any]) -> str:
    profile = issue.get("profile_payload") or {}
    explicit = profile.get("validation_status") or issue.get("validation_status")
    if explicit:
        return str(explicit)
    # Older snapshots retain validation in their eligible pool. No inference
    # from evidence labels alone: a low-confidence official item can be pending.
    key = str(issue.get("issue_key") or "").partition(":")[2]
    pool = (bundle.get("snapshot") or {}).get("content_payload") or {}
    for row in pool.get("eligible_analysis_pool") or []:
        if key and row.get("event_key") == key:
            return str(row.get("validation_status") or "required")
    return "required"


def customer_copy(issue: dict[str, Any], action: dict[str, Any] | None,
                  bundle: dict[str, Any]) -> tuple[str, str]:
    """Explicit customer-text allowlist. This does not enable public sharing."""
    state = communication_state(action)
    if state != "customer_ready":
        return "", COMM_GUIDANCE[state]
    revision = bundle.get("revision") or {}
    if revision.get("validation_status") != "ok" or revision.get("coverage_status") == "insufficient":
        return "", "브리핑 검증이 끝난 뒤 고객 안내 문구를 사용할 수 있습니다."
    if issue_validation(issue, bundle) != "ok" or (issue.get("profile_payload") or {}).get("confidence") == "low":
        return "", "이 이슈의 검증 결과를 먼저 확인하세요."
    if issue.get("selection_tier") not in {"core", "light_digest"}:
        return "", "표시 대상으로 선정된 이슈만 안내할 수 있습니다."
    if issue.get("evidence_status") not in {"official_confirmed", "multi_source_confirmed"}:
        return "", "고객에게 바로 안내할 근거를 추가로 확인하세요."
    expression = str(((action or {}).get("conversation_payload") or {}).get("recommended_expression") or "").strip()
    sources = [s for s in issue_sources(issue, bundle) if published_kst(s.get("published_at")) != "게시 시각 확인 필요"]
    title = str(issue.get("title") or "").strip()
    if not expression or not title or not sources:
        return "", "권장 안내 문구와 게시일이 확인된 원문이 필요합니다."
    lines = [title, expression, "", "원문"]
    for source in sources[:3]:
        publisher = str(source.get("publisher_name") or source.get("source_name") or "출처")
        lines.append(f"{publisher} · {published_kst(source['published_at'])}\n{source['url']}")
    return "\n".join(lines), ""


def available_tools(action: dict[str, Any] | None, allowed_ids: set[str]) -> list[dict[str, str]]:
    actions = (action or {}).get("workspace_actions") or []
    codes = [a.get("tool_code") for a in actions if isinstance(a, dict)]
    registry = {t["tool_code"]: t for t in registered_briefing_tools()}
    return [registry[a["tool_code"]] for a in validated_tool_actions(codes)
            if a["tool_code"] in allowed_ids]


def _compact(value: Any, limit: int) -> str:
    value = " ".join(str(value or "").split())
    if len(value) <= limit:
        return value
    return value[:max(0, limit - 1)].rstrip() + "…"


def team_brief(bundle: dict[str, Any]) -> str:
    """Target 300–450 characters when there is material; never pad or invent."""
    rows = [i for i in bundle.get("issues") or []
            if i.get("selection_tier") == "core" and issue_validation(i, bundle) == "ok"]
    if not rows or (bundle.get("revision") or {}).get("coverage_status") == "insufficient":
        return ""
    rows.sort(key=lambda i: -float(i.get("importance_score") or 0))
    actions = {str(a.get("issue_id")): a for a in bundle.get("actions") or []}
    date_text = str((bundle.get("briefing") or {}).get("briefing_date") or "")
    lines = [f"{date_text} · 팀원 1분 브리핑 · 내부 참고"]
    if (bundle.get("revision") or {}).get("coverage_status") == "degraded":
        lines.append("일부 출처만 확보된 브리핑입니다.")
    selected = rows[:3]
    per_issue = (450 - len("\n".join(lines)) - 1) // len(selected) - 1
    for index, issue in enumerate(selected, 1):
        action = actions.get(str(issue.get("id"))) or {}
        state = communication_state(action)
        part = f"{index}. {issue.get('title') or ''} — {issue.get('summary') or ''}"
        if state in {"internal_check", "do_not_mention"}:
            part = f"{index}. [{COMM_LABELS[state]}] {issue.get('title') or ''} — {issue.get('summary') or ''}"
        next_step = (issue.get("profile_payload") or {}).get("next_step")
        if next_step:
            part += f" / 확인: {next_step}"
        lines.append(_compact(part, per_issue))
    return "\n".join(lines)[:450]
