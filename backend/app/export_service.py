"""
Export Service — Lumio Backend
===============================

Renders validated study materials (notes, quiz, flashcards) into
downloadable PDF files using ReportLab. All rendering happens entirely
in memory via ``BytesIO`` — no temporary files are created on disk.

The exported PDFs feature:
- Clean TrueType font registration (Segoe UI, DejaVu Sans, Arial, Liberation Sans)
  with fallback to Helvetica, avoiding UnicodeEncodeError and glyph missing errors.
- Automatic transliteration of Unicode subscripts (H₂O -> H<sub>2</sub>O)
  and superscripts (10⁻⁷ -> 10<sup>-7</sup>) into native ReportLab tags.
- Markdown bold/italic tag conversion (**bold** -> <b>bold</b>).
- Safe HTML entity escaping to prevent XML parsing errors in Platypus Paragraphs.
- Automatic page numbering in the footer.
"""

import os
import re
from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

# ---------------------------------------------------------------------------
# Font Discovery and Registration
# ---------------------------------------------------------------------------

_FONT_INITIALIZED = False
_PRIMARY_FONT = "Helvetica"
_UNICODE_SUPPORTED = False

_FONT_CANDIDATES = [
    # Windows paths
    (
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/segoeuii.ttf",
        "C:/Windows/Fonts/segoeuiz.ttf",
    ),
    (
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/ariali.ttf",
        "C:/Windows/Fonts/arialbi.ttf",
    ),
    # Linux / Ubuntu / GitHub Actions CI paths
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
    ),
    (
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf",
    ),
    # macOS paths
    (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Italic.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf",
    ),
]


def _init_fonts() -> tuple[str, bool]:
    global _FONT_INITIALIZED, _PRIMARY_FONT, _UNICODE_SUPPORTED
    if _FONT_INITIALIZED:
        return _PRIMARY_FONT, _UNICODE_SUPPORTED

    for regular, bold, italic, bold_italic in _FONT_CANDIDATES:
        if os.path.exists(regular):
            try:
                pdfmetrics.registerFont(TTFont("LumioFont", regular))
                has_bold = os.path.exists(bold)
                has_italic = os.path.exists(italic)
                has_bi = os.path.exists(bold_italic)

                if has_bold:
                    pdfmetrics.registerFont(TTFont("LumioFont-Bold", bold))
                if has_italic:
                    pdfmetrics.registerFont(TTFont("LumioFont-Italic", italic))
                if has_bi:
                    pdfmetrics.registerFont(TTFont("LumioFont-BoldItalic", bold_italic))

                pdfmetrics.registerFontFamily(
                    "LumioFont",
                    normal="LumioFont",
                    bold="LumioFont-Bold" if has_bold else "LumioFont",
                    italic="LumioFont-Italic" if has_italic else "LumioFont",
                    boldItalic="LumioFont-BoldItalic" if has_bi else "LumioFont",
                )
                _PRIMARY_FONT = "LumioFont"
                _UNICODE_SUPPORTED = True
                break
            except Exception:
                continue

    _FONT_INITIALIZED = True
    return _PRIMARY_FONT, _UNICODE_SUPPORTED


_SUB_MAP = str.maketrans("₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎", "0123456789+-=()")
_SUP_MAP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ", "0123456789+-=()ni")

_GREEK_FALLBACKS = {
    "α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "Δ": "Delta",
    "ε": "epsilon", "θ": "theta", "λ": "lambda", "μ": "mu", "π": "pi",
    "σ": "sigma", "ω": "omega", "→": " -> ", "⇌": " <=> ", "±": "+/-",
    "°": " deg ", "•": "*", "–": "-", "—": "--", "’": "'", "“": '"', "”": '"'
}


def format_pdf_text(text: str, unicode_supported: bool = True) -> str:
    """
    Format raw textbook notes or quiz text for ReportLab Paragraphs.
    Converts subscripts/superscripts to XML tags and sanitizes entities.
    """
    if not text:
        return ""

    # 1. Escape basic XML entities first
    text = escape(str(text))

    # 2. Convert Markdown bold and italic
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)

    # 3. Convert Unicode subscripts to <sub>...</sub>
    text = re.sub(r"([₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎]+)", lambda m: f"<sub>{m.group(1).translate(_SUB_MAP)}</sub>", text)

    # 4. Convert Unicode superscripts to <sup>...</sup>
    text = re.sub(r"([⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ]+)", lambda m: f"<sup>{m.group(1).translate(_SUP_MAP)}</sup>", text)

    # 5. Transliterate unsupported characters if on legacy font fallback
    if not unicode_supported:
        for char, repl in _GREEK_FALLBACKS.items():
            text = text.replace(char, repl)

    # 6. Convert newlines to ReportLab breaks
    text = text.replace("\n", "<br/>")
    return text


# ---------------------------------------------------------------------------
# Main PDF builder
# ---------------------------------------------------------------------------

def make_pdf(kind: str, material: dict) -> bytes:
    """
    Render a study material dictionary into a PDF byte string.

    Parameters
    ----------
    kind : str
        Material type — one of ``"deep-notes"``, ``"quick-notes"``,
        ``"quiz"``, or ``"flashcards"``.
    material : dict
        The validated material dictionary (matches the corresponding
        Pydantic output schema).

    Returns
    -------
    bytes
        The complete PDF file content, ready to stream as a response.
    """
    font_name, unicode_supported = _init_fonts()
    output = BytesIO()

    # --- Stylesheet with Lumio-branded custom styles ---
    styles = getSampleStyleSheet()

    # Apply detected font to standard styles
    for style_name in ["Normal", "BodyText", "Title", "Heading1", "Heading2", "Italic"]:
        if style_name in styles:
            styles[style_name].fontName = font_name

    styles.add(ParagraphStyle(
        name="Section",
        parent=styles["Heading2"],
        fontName=font_name,
        textColor=colors.HexColor("#d04b19"),
        spaceBefore=12,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="BodyLumio",
        parent=styles["BodyText"],
        fontName=font_name,
        leading=15,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="SourceCite",
        parent=styles["Italic"],
        fontName=font_name,
        textColor=colors.HexColor("#7b7b78"),
        fontSize=9,
        leading=12,
        spaceAfter=8,
    ))

    # --- Title block ---
    title_text = material.get("title", "Lumio Study Material")
    story = [
        Paragraph(format_pdf_text(title_text, unicode_supported), styles["Title"]),
        Spacer(1, 0.2 * inch),
    ]

    # --- Content sections by material type ---
    if kind in {"deep-notes", "quick-notes"}:
        for section in material.get("sections", []):
            story.extend([
                Paragraph(format_pdf_text(section.get("heading", ""), unicode_supported), styles["Section"]),
                Paragraph(format_pdf_text(section.get("content", ""), unicode_supported), styles["BodyLumio"]),
            ])
            pages = section.get("source_pages", [])
            if pages:
                story.append(Paragraph(
                    f"Source pages: {escape(', '.join(map(str, pages)))}",
                    styles["SourceCite"],
                ))

    elif kind == "quiz":
        for index, item in enumerate(material.get("questions", []), start=1):
            q_text = f"{index}. {format_pdf_text(item.get('question', ''), unicode_supported)}"
            story.append(Paragraph(q_text, styles["Section"]))
            for option in item.get("options", []):
                story.append(Paragraph(f"• {format_pdf_text(option, unicode_supported)}", styles["BodyLumio"]))
            story.append(Paragraph(f"<b>Answer:</b> {format_pdf_text(item.get('answer', ''), unicode_supported)}", styles["BodyLumio"]))
            story.append(Paragraph(f"<b>Explanation:</b> {format_pdf_text(item.get('explanation', ''), unicode_supported)}", styles["BodyLumio"]))
            pages = item.get("source_pages", [])
            if pages:
                story.append(Paragraph(
                    f"Source pages: {escape(', '.join(map(str, pages)))}",
                    styles["SourceCite"],
                ))

    elif kind == "flashcards":
        for index, card in enumerate(material.get("cards", []), start=1):
            story.append(Paragraph(f"Card {index}", styles["Section"]))
            story.append(Paragraph(f"<b>Prompt:</b> {format_pdf_text(card.get('front', ''), unicode_supported)}", styles["BodyLumio"]))
            story.append(Paragraph(f"<b>Answer:</b> {format_pdf_text(card.get('back', ''), unicode_supported)}", styles["BodyLumio"]))
            pages = card.get("source_pages", [])
            if pages:
                story.append(Paragraph(
                    f"Source pages: {escape(', '.join(map(str, pages)))}",
                    styles["SourceCite"],
                ))
            story.append(Spacer(1, 0.12 * inch))

    # --- Page number footer callback ---
    def add_page_number(canvas, document):
        canvas.saveState()
        canvas.setFont(font_name, 9)
        canvas.setFillColor(colors.HexColor("#5b5b59"))
        canvas.drawRightString(letter[0] - 0.6 * inch, 0.4 * inch, str(document.page))
        canvas.restoreState()

    # --- Build the final PDF document ---
    SimpleDocTemplate(
        output,
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.7 * inch,
    ).build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)

    return output.getvalue()