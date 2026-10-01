"""Shared PDF header/footer. No user or author signature."""
from reportlab.lib.colors import HexColor, white

from modules.shared.report_fonts import korean_pdf_font

def draw_brand(c, page=None):
    font = korean_pdf_font()
    from modules.shared.organization import active_profile
    profile = active_profile()
    w,h=c._pagesize
    c.saveState()
    c.setFillColor(HexColor(profile['header_color'])); c.rect(0,h-38,w,38,fill=1,stroke=0)
    c.setFillColor(HexColor(profile['accent_color'])); c.rect(0,h-41,w,3,fill=1,stroke=0)
    c.setFillColor(white); c.setFont(font,11); c.drawString(32,h-25,'H  |  ' + profile['brand_name'])
    c.setStrokeColor(HexColor('#DCE5EF')); c.line(32,35,w-32,35)
    c.setFillColor(HexColor('#62758A')); c.setFont(font,8); c.drawString(32,21,profile['brand_name'])
    if page is not None: c.drawRightString(w-32,21,str(page))
    c.restoreState()
