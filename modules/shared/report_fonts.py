"""Built-in Korean PDF font registration without bundling external font files."""
from __future__ import annotations

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

DEFAULT_KOREAN_FONT = "HYGothic-Medium"


def korean_pdf_font() -> str:
    """Return ReportLab's built-in Korean CID font name."""
    if DEFAULT_KOREAN_FONT not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(DEFAULT_KOREAN_FONT))
    return DEFAULT_KOREAN_FONT
