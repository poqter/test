"""Branded, in-memory question sheet with handwriting space."""
import html
import io

from modules.shared.runtime_cache import session_export


@session_export("consultation-question-pdf-v1", name_arg=False)
def build_question_pdf(title, questions, customer='', consultation_date=''):
    if not title.strip() or not questions or any(not q['text'].strip() for q in questions):
        raise ValueError('제목과 선택한 질문 내용을 입력해 주세요.')
    if len(title)>80 or len(customer)>40 or any(len(q['text'])>500 for q in questions):
        raise ValueError('입력 길이를 확인해 주세요.')
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph
    from modules.shared.pdf_brand import draw_brand
    from modules.shared.report_fonts import korean_pdf_font
    font = korean_pdf_font()
    class NumberedCanvas(canvas.Canvas):
        """Retain page drawing states to add accurate totals in a final pass."""
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.saved_pages = []

        def showPage(self):
            self.saved_pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            self.showPage()
            total = len(self.saved_pages)
            for state in self.saved_pages:
                self.__dict__.update(state)
                self.setFillColor(HexColor('#657B90'))
                self.setFont(font, 9)
                self.drawRightString(A4[0]-42, 25, f'{self._pageNumber} / {total}')
                canvas.Canvas.showPage(self)
            canvas.Canvas.save(self)

    buf=io.BytesIO(); c=NumberedCanvas(buf,pagesize=A4)
    c.setTitle('화랑 WORKSPACE 상담 질문지');c.setAuthor('화랑 WORKSPACE')
    w,h=A4; margin=42; width=w-84; page=0
    navy='#163650';blue='#246BD5'; muted='#657B90';line='#A8B5C3'
    def paragraph(text,x,y,available=width,size=12,leading=19,color=navy):
        p=Paragraph(html.escape(str(text)).replace('\n','<br/>'),ParagraphStyle('q',fontName=font,fontSize=size,leading=leading,wordWrap='CJK',textColor=HexColor(color)))
        _,height=p.wrap(available,h)
        if x is not None:p.drawOn(c,x,y-height)
        return height
    def new_page():
        nonlocal page
        if page:c.showPage()
        page+=1
        if page == 1:
            draw_brand(c)
            y=h-78;y-=paragraph(title,margin,y,size=22,leading=29)+16
            c.setFillColor(HexColor('#F0F5FC'));c.roundRect(margin,y-39,width,39,7,fill=1,stroke=0)
            customer_label=customer.strip() or '____________________'
            date_label=str(consultation_date).strip() or '________________'
            paragraph('고객명: '+customer_label,margin+12,y-8,available=width*.57-18,size=10,leading=13)
            paragraph('상담일: '+date_label,margin+width*.57,y-8,available=width*.43-12,size=10,leading=13)
            start_y=y-62
        else:
            draw_brand(c)
            start_y=h-66
        return start_y
    y=new_page()
    for i,q in enumerate(questions,1):
        ph=paragraph(q['text'],None,0,available=width-85)
        needed=max(ph,24)+74
        if y-needed<57:y=new_page()
        c.setFillColor(HexColor('#F0F5FC'));c.roundRect(margin,y-24,28,26,6,fill=1,stroke=0)
        c.setFillColor(HexColor(blue));c.setFont(font,11);c.drawCentredString(margin+14,y-16,f'{i:02d}')
        paragraph(q['text'],margin+38,y,available=width-85)
        c.setFillColor(HexColor(muted));c.setFont(font,8);c.drawRightString(w-margin,y-12,q['id'])
        base=y-max(ph,24)-13;c.setStrokeColor(HexColor(line));c.setLineWidth(.6)
        for k in range(3):c.line(margin+38,base-k*18,w-margin,base-k*18)
        y-=needed
    # Keep at least half an A4 page for unstructured handwritten notes.
    if y-57< h/2:y=new_page()
    paragraph('종합 메모',margin,y,size=17,leading=24);y-=42
    c.setStrokeColor(HexColor(line))
    while y>=65:
        c.line(margin,y,w-margin,y);y-=22
    c.save()
    return buf.getvalue(),page
