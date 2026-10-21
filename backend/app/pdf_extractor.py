"""
PDF Extractor — Lumio Backend
==============================

Extracts selectable (embedded) text from each page of a PDF using pypdf.
Each page is returned as a dictionary with its 1-based page number and raw
text content.  Downstream modules handle whitespace normalization, heading
detection, and chunking.

If the document exceeds the configured page limit, a ``PDFPageLimitError``
is raised before any text extraction begins so that oversize files are
rejected early.

pypdf is a pure-Python PDF library that works across all platforms
including Cloudflare Workers (Pyodide / WebAssembly).
"""

import logging

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.config import MAX_PDF_PAGES

logger = logging.getLogger("lumio.pdf_extractor")


# ---------------------------------------------------------------------------
# Custom exception for page-limit violations
# ---------------------------------------------------------------------------

class PDFPageLimitError(ValueError):
    """Raised when a PDF exceeds the configured maximum page count."""
    pass


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

def extract_text_from_pdf(pdf_path: str) -> list[dict]:
    """
    Open a PDF file and extract text from every page.

    For each page, the function reads embedded (selectable) text using
    pypdf's text extraction engine.

    Parameters
    ----------
    pdf_path : str
        Absolute or relative filesystem path to the PDF file.

    Returns
    -------
    list[dict]
        A list of ``{"page": int, "text": str}`` dictionaries, one per
        page, preserving the original page order.

    Raises
    ------
    PDFPageLimitError
        If the document exceeds ``MAX_PDF_PAGES``.
    PdfReadError
        If pypdf cannot open or parse the file.
    """
    reader = PdfReader(pdf_path)
    pages = []

    # Enforce the page limit before extracting any content.
    if len(reader.pages) > MAX_PDF_PAGES:
        raise PDFPageLimitError("PDF exceeds the configured page limit.")

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append({
            "page": page_number,
            "text": text,
        })

    return pages


# Page numbers remain attached to text for citations downstream.