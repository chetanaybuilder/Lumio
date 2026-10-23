"""
PDF Extractor — Lumio Backend
==============================

Extracts structured text, tables, diagrams, and figures from each page of a
PDF using PyMuPDF (fitz) with an automatic pypdf fallback.

Capabilities:
1. **File Validation & Protection**:
   - Signature verification (%PDF-).
   - Encryption / password-protection detection (raises ``PDFEncryptedError``).
   - Corrupted or unparseable document detection (raises ``PDFCorruptedError``).
   - Page count limit enforcement (raises ``PDFPageLimitError``).
2. **Diagram, Figure & Visual Understanding**:
   - Extracts embedded images and vector drawing paths (chemical bonds, circuits, axes).
   - Locates figure captions (e.g., "Figure 1.2: ...", "Fig. 3", "Scheme 4", "Diagram:").
   - Synthesizes explicit visual context tags ``[FIGURE / DIAGRAM (Page X): ...]``
     so downstream RAG and LLM prompts understand all visual learning material.
3. **Table Structure Preservation**:
   - Converts structured tabular data into clean Markdown tables rather than
     flattening into disconnected lines of numbers.
4. **Scanned / Image-Only Document Detection**:
   - Detects scanned documents with zero or negligible selectable text.
   - Raises ``PDFScannedError`` with specific affected page numbers instead of
     falsely reporting success on empty content.
"""

import logging
import re
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

try:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError
except ImportError:
    PdfReader = None
    PdfReadError = Exception

from app.config import MAX_PDF_PAGES
from app.text_preprocessor import check_page_quality

logger = logging.getLogger("lumio.pdf_extractor")


# ---------------------------------------------------------------------------
# Custom exceptions for document validation
# ---------------------------------------------------------------------------

class PDFPageLimitError(ValueError):
    """Raised when a PDF exceeds the configured maximum page count."""
    pass


class PDFEncryptedError(ValueError):
    """Raised when a PDF is password-protected or encrypted."""
    pass


class PDFCorruptedError(ValueError):
    """Raised when a PDF is malformed, truncated, or unreadable."""
    pass


class PDFScannedError(ValueError):
    """Raised when a PDF contains scanned images or photos with no digital text."""
    pass


# ---------------------------------------------------------------------------
# Helper: format tables as Markdown
# ---------------------------------------------------------------------------

def _table_to_markdown(rows: list[list[str | None]]) -> str:
    """Convert extracted 2D table cells into a clean Markdown table string."""
    if not rows or len(rows) < 1:
        return ""

    cleaned_rows = [
        [re.sub(r"\s+", " ", str(cell or "").strip()) for cell in row]
        for row in rows
    ]
    if not any(any(cell for cell in row) for row in cleaned_rows):
        return ""

    headers = cleaned_rows[0]
    col_count = len(headers)
    if col_count == 0:
        return ""

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * col_count) + " |",
    ]
    for row in cleaned_rows[1:]:
        padded_row = row + [""] * (col_count - len(row))
        lines.append("| " + " | ".join(padded_row[:col_count]) + " |")

    return "\n" + "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# PyMuPDF-based extraction with diagram and table understanding
# ---------------------------------------------------------------------------

def _extract_with_pymupdf(pdf_path: str) -> list[dict]:
    """Extract text, tables, diagrams, and drawings using PyMuPDF."""
    doc = fitz.open(pdf_path)
    try:
        if doc.is_encrypted:
            raise PDFEncryptedError("PDF is encrypted or password-protected. Please upload an unprotected file.")

        total_pages = len(doc)
        if total_pages > MAX_PDF_PAGES:
            raise PDFPageLimitError(
                f"PDF has {total_pages} pages, which exceeds the limit of {MAX_PDF_PAGES} pages."
            )

        pages = []
        scanned_candidate_pages = []

        for page_idx in range(total_pages):
            page = doc[page_idx]
            page_no = page_idx + 1

            raw_text = page.get_text("text") or ""
            images = page.get_images()
            drawings = page.get_drawings()

            # Check for figure/diagram captions
            figure_captions = []
            for line in raw_text.splitlines():
                line_str = line.strip()
                if re.match(r"^(?:Figure|Fig\.|Diagram|Scheme|Illustration|Chart|Plot)\s*[\d\.\-:]*\s*", line_str, re.IGNORECASE):
                    if len(line_str) > 3:
                        figure_captions.append(line_str)

            # Detect and extract structured tables
            table_markdown_blocks = []
            try:
                tabs = page.find_tables()
                if tabs and tabs.tables:
                    for t in tabs.tables:
                        md = _table_to_markdown(t.extract())
                        if md:
                            table_markdown_blocks.append(md)
            except Exception as e:
                logger.debug("Table detection skipped on page %d: %s", page_no, e)

            # Build page text content
            content_parts = []

            # If page has diagrams, drawings, or images, add explicit visual context markers
            if figure_captions:
                for cap in figure_captions:
                    content_parts.append(f"\n[FIGURE / DIAGRAM: {cap}]\n")
            elif images or drawings:
                visual_desc = []
                if len(images) > 0:
                    visual_desc.append(f"{len(images)} illustration(s)/diagram image(s)")
                if len(drawings) >= 4:
                    visual_desc.append(f"{len(drawings)} technical/chemical/vector drawing path(s)")
                if visual_desc:
                    content_parts.append(f"\n[VISUAL ELEMENTS DETECTED (Page {page_no}): {', '.join(visual_desc)}]\n")

            content_parts.append(raw_text)

            if table_markdown_blocks:
                content_parts.append("\n[STRUCTURED TABLES (Page " + str(page_no) + ")]:\n")
                content_parts.extend(table_markdown_blocks)

            full_page_text = "\n".join(content_parts).strip()

            # Evaluate extracted page quality
            quality = check_page_quality(raw_text)

            # Track scanned or low-quality candidate pages
            if not quality["is_valid"]:
                scanned_candidate_pages.append(page_no)

            pages.append({
                "page": page_no,
                "text": full_page_text,
                "raw_text": raw_text,
                "has_diagram": bool(figure_captions or images or len(drawings) >= 4),
                "image_count": len(images),
                "drawing_count": len(drawings),
                "quality": quality,
                "captions": figure_captions,
            })

        # Validate overall extraction quality against raw extracted text
        total_raw_text_chars = sum(len(doc[i].get_text("text").strip()) for i in range(total_pages))
        if total_raw_text_chars < 50 and scanned_candidate_pages:
            pages_str = ", ".join(map(str, scanned_candidate_pages[:10]))
            raise PDFScannedError(
                f"This PDF appears to contain scanned pages or photos without selectable digital text (pages: {pages_str}). "
                "Please upload a document with digital text or run OCR before uploading."
            )

        return pages
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# pypdf fallback extraction
# ---------------------------------------------------------------------------

def _extract_with_pypdf(pdf_path: str) -> list[dict]:
    """Fallback extraction using pypdf when PyMuPDF is not available."""
    try:
        reader = PdfReader(pdf_path)
    except Exception as exc:
        raise PDFCorruptedError(f"Could not parse PDF file: {exc}") from exc

    if reader.is_encrypted:
        raise PDFEncryptedError("PDF is encrypted or password-protected. Please upload an unprotected file.")

    if len(reader.pages) > MAX_PDF_PAGES:
        raise PDFPageLimitError(f"PDF exceeds the configured page limit ({len(reader.pages)} > {MAX_PDF_PAGES}).")

    pages = []
    scanned_pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""

        # Search for figure captions in extracted text
        captions = []
        for line in text.splitlines():
            line_str = line.strip()
            if re.match(r"^(?:Figure|Fig\.|Diagram|Scheme|Illustration|Chart)\s*[\d\.\-:]*\s*", line_str, re.IGNORECASE):
                captions.append(line_str)

        has_images = bool(page.images and len(page.images) > 0)
        content = text
        if captions:
            content = "\n" + "\n".join(f"[FIGURE / DIAGRAM: {c}]" for c in captions) + "\n" + content
        elif has_images:
            content = f"\n[VISUAL ELEMENTS DETECTED (Page {page_number})]\n" + content

        if len(text.strip()) < 15 and has_images:
            scanned_pages.append(page_number)

        pages.append({
            "page": page_number,
            "text": content,
            "raw_text": text,
            "has_diagram": bool(captions or has_images),
            "image_count": len(page.images) if page.images else 0,
            "drawing_count": 0,
        })

    total_raw_chars = sum(len(p.get("raw_text", "").strip()) for p in pages)
    if total_raw_chars < 50 and scanned_pages:
        raise PDFScannedError(
            f"This PDF appears to contain scanned pages without digital text (pages: {', '.join(map(str, scanned_pages[:10]))})."
        )

    return pages


# ---------------------------------------------------------------------------
# Main extraction entrypoint
# ---------------------------------------------------------------------------

def extract_text_from_pdf(pdf_path: str) -> list[dict]:
    """
    Open a PDF file and extract text, tables, and diagram annotations.

    Uses PyMuPDF for rich layout, table, drawing, and diagram extraction,
    falling back to pypdf if PyMuPDF encounters an unexpected error.

    Parameters
    ----------
    pdf_path : str
        Filesystem path to the PDF.

    Returns
    -------
    list[dict]
        List of ``{"page": int, "text": str, "has_diagram": bool, ...}``.

    Raises
    ------
    PDFPageLimitError
        If page count exceeds ``MAX_PDF_PAGES``.
    PDFEncryptedError
        If the document is password-protected.
    PDFScannedError
        If the document contains only scanned photos without text.
    PDFCorruptedError
        If the file cannot be parsed.
    """
    path_obj = Path(pdf_path)
    if not path_obj.exists() or path_obj.stat().st_size == 0:
        raise PDFCorruptedError("The uploaded file is empty or missing.")

    # Validate signature header
    with open(pdf_path, "rb") as f:
        header = f.read(1024)
        if b"%PDF-" not in header:
            raise PDFCorruptedError("The file does not contain a valid %PDF- header.")

    if fitz is not None:
        try:
            return _extract_with_pymupdf(pdf_path)
        except (PDFPageLimitError, PDFEncryptedError, PDFScannedError, PDFCorruptedError):
            raise
        except Exception as exc:
            logger.warning("PyMuPDF extraction encountered error (%s); trying pypdf fallback: %s", type(exc).__name__, exc)

    return _extract_with_pypdf(pdf_path)