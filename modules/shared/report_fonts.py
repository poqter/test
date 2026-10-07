"""Embed bundled Korean PDF fonts so viewers need no local Korean fonts."""
from __future__ import annotations

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from modules.shared.paths import PROJECT_ROOT

# Preserve Gothic headings and Myeongjo customer body text. CID substitution
# previously depended on the PDF viewer and produced missing Korean glyphs.
DEFAULT_KOREAN_FONT = "HwarangGothicEmbedded"
CUSTOMER_BODY_FONT = "HwarangMyeongjoEmbedded"
CUSTOMER_HEADING_FONT = DEFAULT_KOREAN_FONT
_FONT_FILES = {
    DEFAULT_KOREAN_FONT: "NanumGothic-Regular.ttf",
    CUSTOMER_BODY_FONT: "NanumMyeongjo-Regular.ttf",
}


def _register(name: str) -> str:
    if name not in pdfmetrics.getRegisteredFontNames():
        path = PROJECT_ROOT / "assets" / "fonts" / _FONT_FILES[name]
        pdfmetrics.registerFont(TTFont(name, str(path)))
    return name


def korean_pdf_font() -> str:
    """Return the embedded Gothic font used by existing shared exports."""
    return _register(DEFAULT_KOREAN_FONT)


def customer_pdf_fonts() -> tuple[str, str]:
    """Return (body, heading/value) fonts for customer-facing calculator PDFs.

    Both fonts are bundled and embedded as subsets. Runtime generation makes
    no font download and does not depend on fonts installed on the reader's device.
    """
    return _register(CUSTOMER_BODY_FONT), _register(CUSTOMER_HEADING_FONT)


_SAFE_SYMBOLS = str.maketrans({
    "−": "-", "–": "-", "—": "-", "×": " x ", "÷": " / ",
    "≤": "<=", "≥": ">=", "≠": "!=", "→": " -> ", "↔": " <-> ",
    "☑": "[선택]", "☐": "[ ]", "✓": "[확인]", "✔": "[확인]",
    "·": " / ", "ㆍ": " / ", "•": "-", "²": "^2", "³": "^3", "⁻": "-", " ": " ",
})


def pdf_text(value: object) -> str:
    """Use unambiguous printable operators with the bundled Korean fonts.

    Whole-won digits, signs and decimals are never altered. Unsupported emoji
    are decorative only; their textual labels remain. Font files ship with the
    application and are never downloaded at runtime.
    """
    import re
    text = str(value).translate(_SAFE_SYMBOLS)
    text = re.sub(r"[\U00010000-\U0010ffff\ufe0f\u200d]", "", text)
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
