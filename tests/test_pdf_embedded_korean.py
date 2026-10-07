"""PDF bytes must carry their Korean glyphs, independently of viewer fonts."""
from io import BytesIO
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from modules.consultation.question_pdf import build_question_pdf
from modules.shared.report_fonts import customer_pdf_fonts


def _embedded_fonts(reader):
    names = set()
    for page in reader.pages:
        for ref in page['/Resources'].get('/Font', {}).values():
            font = ref.get_object()
            descriptor = font.get('/FontDescriptor')
            if descriptor and descriptor.get_object().get('/FontFile2'):
                names.add(str(font.get('/BaseFont')))
    return names


def test_question_pdf_embeds_korean_and_preserves_text():
    data, pages = build_question_pdf('한글 상담 질문지', [{'id': 'Q01', 'text': '보험료와 가족의 보장을 확인합니다.'}])
    reader = PdfReader(BytesIO(data))
    assert pages == len(reader.pages)
    assert '보험료와 가족의 보장을 확인합니다.' in ''.join(p.extract_text() for p in reader.pages)
    assert any('NanumGothic' in name for name in _embedded_fonts(reader))


def test_customer_body_and_heading_are_both_embedded():
    buf = BytesIO()
    c = canvas.Canvas(buf)
    for index, font in enumerate(customer_pdf_fonts()):
        c.setFont(font, 12)
        c.drawString(50, 700-index*30, '한글 비교표 보험료 100,000원')
    c.save()
    names = _embedded_fonts(PdfReader(BytesIO(buf.getvalue())))
    assert any('NanumGothic' in name for name in names)
    assert any('NanumMyeongjo' in name for name in names)
