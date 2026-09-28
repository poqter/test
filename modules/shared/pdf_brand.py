"""Shared PDF header/footer. No user or author signature."""
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from modules.shared.paths import PROJECT_ROOT

def draw_brand(c, page=None):
    font='HwarangBrand'
    if font not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font,str(PROJECT_ROOT/'assets/fonts/PretendardVariable.ttf')))
    w,h=c._pagesize
    c.saveState()
    c.setFillColor(HexColor('#112B49')); c.rect(0,h-38,w,38,fill=1,stroke=0)
    c.setFillColor(HexColor('#158391')); c.rect(0,h-41,w,3,fill=1,stroke=0)
    c.setFillColor(white); c.setFont(font,11); c.drawString(32,h-25,'H  |  화랑 WORKSPACE')
    c.setStrokeColor(HexColor('#DCE5EF')); c.line(32,35,w-32,35)
    c.setFillColor(HexColor('#62758A')); c.setFont(font,8); c.drawString(32,21,'화랑 WORKSPACE')
    if page is not None: c.drawRightString(w-32,21,str(page))
    c.restoreState()
