"""Built-in Korean PDF font registration without shipping external font files."""
from __future__ import annotations

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

# Keep the existing Gothic CID font as the compatibility default for legacy
# exports. Calculator customer PDFs use a more editorial Myeongjo body with a
# clean Gothic heading/value face through the helpers below.
DEFAULT_KOREAN_FONT = "HYGothic-Medium"
CUSTOMER_BODY_FONT = "HYSMyeongJo-Medium"
CUSTOMER_HEADING_FONT = "HYGothic-Medium"


def _register(name: str) -> str:
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(name))
    return name


def korean_pdf_font() -> str:
    """Return the compatibility Korean font used by existing exports."""
    return _register(DEFAULT_KOREAN_FONT)


def customer_pdf_fonts() -> tuple[str, str]:
    """Return (body, heading/value) fonts for customer-facing calculator PDFs.

    Both are ReportLab built-in Korean CID fonts, so deployment does not depend
    on a bundled font binary or an external network request.
    """
    return _register(CUSTOMER_BODY_FONT), _register(CUSTOMER_HEADING_FONT)


_SAFE_SYMBOLS = str.maketrans({
    "−": "-", "–": "-", "—": "-", "×": " x ", "÷": " / ",
    "≤": "<=", "≥": ">=", "≠": "!=", "→": " -> ", "↔": " <-> ",
    "☑": "[선택]", "☐": "[ ]", "✓": "[확인]", "✔": "[확인]",
    "·": " / ", "ㆍ": " / ", "•": "-", "²": "^2", "³": "^3", "⁻": "-", " ": " ",
})


def pdf_text(value: object) -> str:
    """Use unambiguous printable operators with the bundled-free Korean fonts.

    Whole-won digits, signs and decimals are never altered. Unsupported emoji
    are decorative only; their textual labels remain. No external font file is
    shipped or downloaded by the application.
    """
    import re
    text = str(value).translate(_SAFE_SYMBOLS)
    text = re.sub(r"[\U00010000-\U0010ffff\ufe0f\u200d]", "", text)
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
