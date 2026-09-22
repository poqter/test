"""Pure consultation composition and in-memory portrait PDF export."""
import hashlib
import html
import io
import json
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

NOTE = "상담 참고자료입니다. 입력한 사실과 가정을 바탕으로 작성했으며 가입·지급·수익을 보장하거나 개별 상품의 적합성을 자동 판정하지 않습니다."


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def unresolved(value):
    return list(dict.fromkeys(re.findall(r"\[[^\]\n]+\]", value)))


def build_summary(topic, facts, priorities, pending, next_action):
    return "\n\n".join(f"{label}\n{str(value).strip() or '미기재'}" for label, value in (
        ("상담 주제", topic), ("확인한 사실", facts), ("고객 우선순위", priorities),
        ("추가 확인 사항", pending), ("다음 행동", next_action)))


def build_proposal(profile, summary, direction, cautions, next_action):
    return "\n\n".join((
        "상담 목적\n" + profile.get("goal", "보장 점검"),
        "상담 구분\n" + profile.get("visit", "첫 상담"),
        "현재 상황과 확인 내용\n" + summary.strip(),
        "함께 검토할 방향\n" + direction.strip(),
        "주의사항과 추가 확인\n" + (cautions.strip() or "추가 확인할 조건을 상담 시 함께 점검해 주세요."),
        "다음 상담 준비\n" + next_action.strip(),
    ))


def message_draft(intro, template, channel, subject):
    if channel == "이메일":
        return f"제목: {subject}\n\n{intro}\n\n{template}\n\n궁금한 점이나 추가로 확인할 사항을 알려주세요."
    return intro + "\n\n" + template


def document_pdf(title, body, *, prepared_on, customer_label="", note=NOTE):
    """No disk writes, user-data cache, remote fonts, or customer metadata."""
    if not body.strip():
        raise ValueError("Empty consultation document")
    if len(body) > 24000:
        raise ValueError("Consultation document is too long")
    font = "HwarangConsultation"
    if font not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font, str(Path(__file__).resolve().parents[1] / "assets/fonts/PretendardVariable.ttf")))
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, leftMargin=42, rightMargin=42,
                            topMargin=52, bottomMargin=50, title="화랑 WORKSPACE 상담자료", author="화랑 WORKSPACE")
    normal = ParagraphStyle("body", fontName=font, fontSize=11, leading=18,
                            wordWrap="CJK", textColor=colors.HexColor("#172033"), spaceAfter=3)
    heading = ParagraphStyle("title", parent=normal, fontSize=23, leading=31, spaceAfter=12)
    small = ParagraphStyle("small", parent=normal, fontSize=9, leading=14,
                           textColor=colors.HexColor("#586277"))
    section = ParagraphStyle("section", parent=normal, fontSize=13, leading=20, spaceBefore=7,
                             textColor=colors.HexColor("#17233C"), keepWithNext=True)
    paragraph = lambda value, style: Paragraph(html.escape(value), style)
    story = [paragraph(title, heading), paragraph("작성일 " + str(prepared_on) + " · 직접 검토한 상담 참고자료", small)]
    if customer_label:
        story.append(paragraph("상담 구분명: " + customer_label, small))
    story.append(paragraph(note, small))
    story.append(Spacer(1, 14))
    for block in body.strip().split("\n\n"):
        lines = block.splitlines()
        for index, line in enumerate(lines):
            if not line.strip():
                continue
            style = section if index == 0 and len(lines) > 1 and len(line) < 60 else normal
            # Paragraph wrapping handles long text and escapes all markup.
            story.append(paragraph(line, style))
        story.append(Spacer(1, 4))

    def page_marks(canvas, document):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#17233C"))
        canvas.setFont(font, 9)
        canvas.drawString(42, A4[1] - 28, "H  |  화랑 WORKSPACE")
        canvas.setStrokeColor(colors.HexColor("#B89555"))
        canvas.line(42, A4[1] - 36, A4[0] - 42, A4[1] - 36)
        canvas.setFillColor(colors.HexColor("#586277"))
        canvas.drawString(42, 27, "화랑 WORKSPACE · 상담 참고용")
        canvas.drawRightString(A4[0] - 42, 27, str(document.page))
        canvas.setFillColor(colors.Color(.72, .65, .48, alpha=.08))
        canvas.setFont(font, 38)
        canvas.translate(A4[0] / 2, A4[1] / 2)
        canvas.rotate(35)
        canvas.drawCentredString(0, 0, "HWARANG WORKSPACE")
        canvas.restoreState()
    doc.build(story, onFirstPage=page_marks, onLaterPages=page_marks)
    return output.getvalue()
