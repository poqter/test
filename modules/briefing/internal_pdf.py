"""On-demand internal PDF from the displayed snapshot, without network access."""
from __future__ import annotations

import html
import io
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether

from modules.shared.report_fonts import korean_pdf_font, pdf_text
from .reading import COMM_LABELS, communication_state, issue_sources, team_brief, published_kst, issue_validation


def internal_pdf(bundle: dict[str, Any], profile_label: str) -> bytes:
    font = korean_pdf_font()
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, leftMargin=36, rightMargin=36,
                           topMargin=42, bottomMargin=45)
    body = ParagraphStyle("briefing_body", fontName=font, fontSize=11, leading=18,
                          wordWrap="CJK", textColor=colors.HexColor("#20344e"), spaceAfter=7)
    heading = ParagraphStyle("briefing_heading", parent=body, fontSize=20, leading=28, spaceAfter=12)
    title = ParagraphStyle("briefing_issue", parent=body, fontSize=14, leading=21, spaceBefore=12)
    small = ParagraphStyle("briefing_meta", parent=body, fontSize=9, leading=14,
                           textColor=colors.HexColor("#57677d"))
    def p(value: Any, style=body):
        return Paragraph(html.escape(pdf_text(str(value or ""))).replace("\n", "<br/>"), style)
    revision, snapshot = bundle.get("revision") or {}, bundle.get("snapshot") or {}
    date_text = str((bundle.get("briefing") or {}).get("briefing_date") or "")
    status = "공개" if revision.get("publication_status") == "published" else "관리자 미리보기"
    story = [p("화랑 WORKSPACE · 내부 업무 브리핑", heading), p(profile_label, title),
             p(f"기준일 {date_text} · {status} · 수집 상태 {revision.get('coverage_status') or '-'}", small),
             p(f"Revision {revision.get('id') or '-'} · Snapshot {snapshot.get('id') or '-'}", small),
             p("직원 업무·상담 준비용 자료입니다. 고객 배포용 PDF가 아닙니다.", small)]
    if revision.get("coverage_status") in {"degraded", "insufficient"} or revision.get("validation_status") != "ok":
        story.append(p("수집 범위 또는 검증이 충분하지 않은 항목이 있습니다. 원문과 상태를 확인하세요.", small))
    rows = [i for i in bundle.get("issues") or [] if i.get("selection_tier") in {"core", "light_digest"}]
    actions = {str(a.get("issue_id")): a for a in bundle.get("actions") or []}
    if not rows:
        story.append(p("현재 검증된 표시 이슈가 없습니다."))
    for issue in rows:
        tier = "핵심" if issue.get("selection_tier") == "core" else "관련 뉴스"
        story.append(KeepTogether([p(f"{tier} · {issue.get('title') or ''}", title), p(issue.get("summary"))]))
        for label, value in (("왜 중요한가", (issue.get("fact_payload") or {}).get("why_important")),
                             ("영향과 해설", (issue.get("analysis_payload") or {}).get("impact_summary"))):
            if value:
                story.extend([p(label, small), p(value)])
        action = actions.get(str(issue.get("id"))) or {}
        state = communication_state(action)
        if state in {"customer_ready", "consultation_reference"} and (issue_validation(issue, bundle) != "ok"
                or (issue.get("profile_payload") or {}).get("confidence") == "low"):
            state = "internal_check"
        if action and state != "not_applicable":
            story.append(p(f"상담 준비 · {COMM_LABELS[state]}", small))
            conversation = action.get("conversation_payload") or {}
            fields = [("먼저 확인", conversation.get("check_first")),
                      ("주의 표현", conversation.get("avoid_expression")),
                      ("다음 단계", (issue.get("profile_payload") or {}).get("next_step"))]
            if state in {"customer_ready", "consultation_reference"}:
                fields.insert(0, ("권장 표현", conversation.get("recommended_expression")))
            for label, value in fields:
                if value:
                    story.append(p(f"{label} · {value}"))
        for source in issue_sources(issue, bundle)[:5]:
            label = str(source.get("publisher_name") or source.get("source_name") or "원문")
            url = html.escape(source["url"], quote=True)
            story.append(Paragraph(f'<a href="{url}" color="#215f9b">{html.escape(pdf_text(label))} · 원문 보기</a>', small))
            if source.get("published_at"):
                story.append(p(f"게시 {published_kst(source['published_at'])}", small))
        story.append(Spacer(1, 5))
    if profile_label.startswith("보험"):
        brief = team_brief(bundle)
        if brief:
            story.extend([p("팀원 1분 브리핑", title), p(brief)])
    def footer(canvas, document):
        canvas.setFont(font, 8)
        canvas.setFillColor(colors.HexColor("#57677d"))
        canvas.drawString(36, 25, pdf_text("화랑 WORKSPACE · 내부 참고 · 고객 배포 금지"))
        canvas.drawRightString(A4[0] - 36, 25, str(document.page))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
