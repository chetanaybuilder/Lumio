from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak


def make_pdf(kind: str, material: dict) -> bytes:
    output = BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], textColor=colors.HexColor("#d04b19"), spaceBefore=12))
    styles.add(ParagraphStyle(name="BodyLumio", parent=styles["BodyText"], leading=15, spaceAfter=8))
    story = [Paragraph(escape(material.get("title", "Lumio Study Material")), styles["Title"]), Spacer(1, 0.2 * inch)]

    if kind in {"deep-notes", "quick-notes"}:
        for section in material.get("sections", []):
            story.extend([
                Paragraph(escape(section["heading"]), styles["Section"]),
                Paragraph(escape(section["content"]).replace("\n", "<br/>"), styles["BodyLumio"]),
            ])
            pages = section.get("source_pages", [])
            if pages:
                story.append(Paragraph(f"Source pages: {escape(', '.join(map(str, pages)))}", styles["Italic"]))
    elif kind == "quiz":
        for index, item in enumerate(material.get("questions", []), start=1):
            story.append(Paragraph(f"{index}. {escape(item['question'])}", styles["Section"]))
            story.extend(Paragraph(escape(option), styles["BodyLumio"]) for option in item.get("options", []))
            story.append(Paragraph(f"Answer: {escape(item['answer'])}", styles["BodyLumio"]))
            story.append(Paragraph(f"Explanation: {escape(item['explanation'])}", styles["BodyLumio"]))
    elif kind == "flashcards":
        for index, card in enumerate(material.get("cards", []), start=1):
            story.append(Paragraph(f"{index}. {escape(card['front'])}", styles["Section"]))
            story.append(Paragraph(escape(card["back"]), styles["BodyLumio"]))
            story.append(Spacer(1, 0.12 * inch))

    def add_page_number(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.HexColor("#5b5b59"))
        canvas.drawRightString(letter[0] - 0.6 * inch, 0.4 * inch, str(document.page))
        canvas.restoreState()

    SimpleDocTemplate(output, pagesize=letter, rightMargin=0.65 * inch, leftMargin=0.65 * inch, topMargin=0.65 * inch, bottomMargin=0.7 * inch).build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return output.getvalue()


# PDFs are built in memory, so exports leave no temporary files behind.