import pymupdf

from app.config import MAX_PDF_PAGES


class PDFPageLimitError(ValueError):
    pass


def extract_text_from_pdf(pdf_path: str) -> list[dict]:
    document = pymupdf.open(pdf_path)
    pages = []

    try:
        if document.page_count > MAX_PDF_PAGES:
            raise PDFPageLimitError("PDF exceeds the configured page limit.")
        for page_number, page in enumerate(document, start=1):
            pages.append({
                "page": page_number,
                "text": page.get_text()
            })
    finally:
        document.close()

    return pages


# Page numbers remain attached to text for citations downstream.