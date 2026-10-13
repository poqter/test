"""Internal exports from saved editions only. Never passed to customer DTOs."""
from copy import deepcopy
from .public_body import staff_body, public_pdf

FIELDS = (("recommended_expression", "상담 표현"), ("check_first", "먼저 확인"),
          ("avoid_expression", "주의할 표현"), ("next_step", "다음 단계"))

def consultation_rows(bundle):
    rows = []
    for action in bundle.get("actions") or []:
        payload = action.get("conversation_payload") or {}
        if not any(payload.get(key) for key, _ in FIELDS): continue
        rows.append({"title": str(action.get("title") or ""),
                     "state": {"customer_ready":"고객 설명 가능", "consultation_reference":"조건 확인 후 참고", "internal_only":"내부 참고", "not_applicable":"상담 연결 불필요", "needs_verification":"확인 필요"}.get(action.get("communication_state"), "확인 필요"),
                     "fields": [{"label": label, "text": str(payload[key])} for key, label in FIELDS if payload.get(key)]})
    return rows

def team_summary(bundle):
    body = staff_body(bundle["snapshot"].get("content_payload") or {})
    issues = sorted(body["issues"], key=lambda row: not row.get("representative"))[:3]
    day = str(bundle["briefing"].get("briefing_date") or "")
    lines = [day + " · 팀 1분 요약 · 직원 내부용"]
    for index, row in enumerate(issues, 1):
        lines.extend([f"{index}. {row['title']}", str(row.get("summary") or "")[:220]])
    checks = [field["text"] for row in consultation_rows(bundle) for field in row["fields"] if field["label"] == "먼저 확인"][:2]
    if checks: lines.extend(["상담 전 확인"] + [text[:220] for text in checks])
    lines.append("고객에게 전달할 때는 고객용 공유 본문을 사용하세요.")
    return "\n".join(lines)

def staff_packet(bundle, sender):
    body = staff_body(bundle["snapshot"].get("content_payload") or {})
    body["schema"] = "hwarang-staff-export-v1"
    body["profile_label"] = str(body.get("profile_label") or "브리핑") + " · 직원 내부용"
    body["consultations"] = consultation_rows(bundle)
    revision = bundle["revision"]
    return {"briefing_date": str(bundle["briefing"].get("briefing_date") or ""),
            "sender": {key: str(sender.get(key) or "") for key in ("name", "position")},
            "edition": {"number": revision.get("revision_no"), "corrected_at": revision.get("generated_at") if revision.get("revision_type") == "correction" else None},
            "body": body}

def staff_pdf(bundle, sender):
    return public_pdf(staff_packet(bundle, sender))
