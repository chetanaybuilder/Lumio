"""
Export Service — Lumio Backend
===============================

Renders validated study materials (notes, quiz, flashcards) into
downloadable PDF files using ReportLab.  All rendering happens entirely
in memory via ``BytesIO`` — no temporary files are created on disk.

The exported PDFs feature:
- A branded title page with Lumio's warm accent palette.
- Section-level formatting with colored headings and source-page citations.
- Numbered quiz questions with answer keys and explanations.
- Sequentially numbered flashcards with front/back layout.
- Automatic page numbers in the footer.

Typography note: the default ReportLab fonts (Helvetica, Times, Courier)
cover basic Latin and some extended characters.  For full Unicode glyph
coverage, embed a TrueType font file via ``pdfmetrics.registerFont``.
"""

from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak


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
    output = BytesIO()

    # --- Stylesheet with Lumio-branded custom styles ---
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="Section",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#d04b19"),
        spaceBefore=12,
    ))
    styles.add(ParagraphStyle(
        name="BodyLumio",
        parent=styles["BodyText"],
        leading=15,
        spaceAfter=8,
    ))

    # --- Title block ---
    story = [
        Paragraph(escape(material.get("title", "Lumio Study Material")), styles["Title"]),
        Spacer(1, 0.2 * inch),
    ]

    # --- Content sections by material type ---
    if kind in {"deep-notes", "quick-notes"}:
        # Render each note section with heading, body, and source citations.
        for section in material.get("sections", []):
            story.extend([
                Paragraph(escape(section["heading"]), styles["Section"]),
                Paragraph(
                    escape(section["content"]).replace("\n", "<br/>"),
                    styles["BodyLumio"],
                ),
            ])
            pages = section.get("source_pages", [])
            if pages:
                story.append(Paragraph(
                    f"Source pages: {escape(', '.join(map(str, pages)))}",
                    styles["Italic"],
                ))

    elif kind == "quiz":
        # Render numbered questions with options, answers, and explanations.
        for index, item in enumerate(material.get("questions", []), start=1):
            story.append(Paragraph(f"{index}. {escape(item['question'])}", styles["Section"]))
            story.extend(
                Paragraph(escape(option), styles["BodyLumio"])
                for option in item.get("options", [])
            )
            story.append(Paragraph(f"Answer: {escape(item['answer'])}", styles["BodyLumio"]))
            story.append(Paragraph(f"Explanation: {escape(item['explanation'])}", styles["BodyLumio"]))

    elif kind == "flashcards":
        # Render numbered cards with front (question) and back (answer).
        for index, card in enumerate(material.get("cards", []), start=1):
            story.append(Paragraph(f"{index}. {escape(card['front'])}", styles["Section"]))
            story.append(Paragraph(escape(card["back"]), styles["BodyLumio"]))
            story.append(Spacer(1, 0.12 * inch))

    # --- Page number footer callback ---
    def add_page_number(canvas, document):
        """Draw the page number in the bottom-right corner of every page."""
        canvas.saveState()
        canvas.setFont("Helvetica", 9)
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


# PDFs are built in memory, so exports leave no temporary files behind.