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
2. **Layout-Aware Text & Reading Order**:
   - Preserves logical reading order across blocks and columns.
   - Detects and removes running headers, footers, and repeated page numbers.
   - Preserves both physical `pdf_page_index` and `printed_label`.
3. **Table Structure Preservation & Deduplication**:
   - Converts structured tabular data into clean Markdown tables.
   - Resolves table continuation across page boundaries with header inheritance.
   - Excludes table bounding boxes from raw text extraction so table cells are
     never duplicated in body prose.
4. **Diagram, Figure & Visual Understanding**:
   - Locates figure captions (e.g., "Figure 1.2: ...", "Fig. 3", "Scheme 4").
   - Synthesizes explicit visual context tags ``[FIGURE / DIAGRAM (Page X): ...]``.
5. **Scanned / Image-Only Document Detection**:
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
from app.text_preprocessor import check_page_quality, repair_chemistry_notation

logger = logging.getLogger("lumio.pdf_extractor")


# ---------------------------------------------------------------------------
# Custom exceptions for document validation
# ---------------------------------------------------------------------------

class PDFPageLimitError(ValueError):
    """Raised when a PDF exceeds the configured maximum page count."""


class PDFEncryptedError(ValueError):
    """Raised when a PDF is password-protected or encrypted."""


class PDFCorruptedError(ValueError):
    """Raised when a PDF is malformed, truncated, or unreadable."""


class PDFScannedError(ValueError):
    """Raised when a PDF contains scanned images or photos with no digital text."""


# ---------------------------------------------------------------------------
# Helper: format tables as Markdown with cell cleaning
# ---------------------------------------------------------------------------

def _clean_table_cell(cell: str | None) -> str:
    """Normalize whitespace, repair chemistry notation, and fix broken decimal points in table cells."""
    if not cell:
        return ""
    text = repair_chemistry_notation(str(cell).strip())
    # Fix broken decimal points from layout line breaks, e.g. "1095°\n." -> "109.5°"
    text = re.sub(r"(\d+)5°\s*\n?\s*\.", r"\1.5°", text)
    text = re.sub(r"(\d+)°\s*\n?\s*\.", r"\1.°", text)
    text = re.sub(r"(\d+)\s*\n?\s*\.", r"\1.", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _table_to_markdown(rows: list[list[str | None]], inherited_headers: list[str] | None = None) -> tuple[str, list[str]]:
    """
    Convert extracted 2D table cells into a clean Markdown table string.
    Returns (markdown_table_string, table_header_columns).
    """
    if not rows or len(rows) < 1:
        return "", []

    cleaned_rows = [
        [_clean_table_cell(cell) for cell in row]
        for row in rows
    ]
    if not any(any(cell for cell in row) for row in cleaned_rows):
        return "", []

    first_row = cleaned_rows[0]
    col_count = len(first_row)
    if col_count == 0:
        return "", []

    # Detect if first row is a header or data row
    is_continuation = False
    if inherited_headers and len(inherited_headers) == col_count:
        num_numeric_or_short = sum(1 for c in first_row if c.isdigit() or len(c) <= 2)
        if num_numeric_or_short >= max(1, col_count // 3):
            is_continuation = True

    if is_continuation:
        headers = inherited_headers
        data_rows = cleaned_rows
    else:
        headers = first_row
        data_rows = cleaned_rows[1:]

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in data_rows:
        padded_row = row + [""] * (len(headers) - len(row))
        lines.append("| " + " | ".join(padded_row[:len(headers)]) + " |")

    return "\n" + "\n".join(lines) + "\n", headers


# ---------------------------------------------------------------------------
# Recurring Header & Footer Detection
# ---------------------------------------------------------------------------

def _detect_recurring_headers_footers(doc) -> set[str]:
    """
    Identify lines that recur across 30%+ of pages near page margins
    (e.g. running headers, book titles, page number stamps).
    """
    line_counts = {}
    total_pages = len(doc)
    if total_pages < 3:
        return set()

    for page_idx in range(total_pages):
        page = doc[page_idx]
        rect = page.rect
        blocks = page.get_text("blocks")
        seen_on_page = set()
        for b in blocks:
            bx0, by0, bx1, by1, btext, bno, btype = b
            if btype != 0:
                continue
            # Look in top 12% and bottom 12%
            if by1 <= rect.height * 0.12 or by0 >= rect.height * 0.88:
                for line in btext.splitlines():
                    clean_line = line.strip()
                    if clean_line and len(clean_line) < 80 and clean_line not in seen_on_page:
                        seen_on_page.add(clean_line)
                        line_counts[clean_line] = line_counts.get(clean_line, 0) + 1

    threshold = max(2, int(total_pages * 0.30))
    recurring = {line for line, count in line_counts.items() if count >= threshold}
    return recurring


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

        # 1. Document Table of Contents
        doc_toc = doc.get_toc() or []

        # 2. Detect recurring running headers/footers to filter out
        recurring_lines = _detect_recurring_headers_footers(doc)

        pages = []
        scanned_candidate_pages = []
        prev_table_headers = None

        for page_idx in range(total_pages):
            page = doc[page_idx]
            page_no = page_idx + 1

            # Printed page label (e.g. "1", "2", "iv")
            try:
                printed_label = page.get_label() or str(page_no)
            except Exception:
                printed_label = str(page_no)

            images = page.get_images()
            drawings = page.get_drawings()

            # 3. Layout-aware Table Extraction
            table_rects = []
            table_items = []
            current_page_headers = None

            try:
                tabs = page.find_tables()
                if tabs and tabs.tables:
                    for t in tabs.tables:
                        extracted = t.extract()
                        if not extracted:
                            continue
                        table_md, headers = _table_to_markdown(extracted, inherited_headers=prev_table_headers)
                        if table_md:
                            table_rects.append(t.bbox)
                            table_items.append((t.bbox[1], t.bbox[0], table_md))
                            if headers:
                                current_page_headers = headers
            except Exception as e:
                logger.debug("Table detection skipped on page %d: %s", page_no, e)

            if current_page_headers:
                prev_table_headers = current_page_headers

            # 4. Extract Text Blocks outside table bounding boxes in reading order
            blocks = page.get_text("blocks")
            block_items = []
            figure_captions = []
            raw_text_parts = []

            for b in blocks:
                bx0, by0, bx1, by1, btext, bno, btype = b
                if btype != 0:
                    continue

                btext_clean = btext.strip()
                if not btext_clean:
                    continue

                raw_text_parts.append(btext_clean)

                # Check if block overlaps significantly with any extracted table
                overlaps_table = False
                for tx0, ty0, tx1, ty1 in table_rects:
                    v_overlap = max(0, min(by1, ty1) - max(by0, ty0))
                    if v_overlap > (by1 - by0) * 0.40:
                        overlaps_table = True
                        break

                if overlaps_table:
                    continue

                # Filter out recurring headers and footers
                lines = btext_clean.splitlines()
                filtered_lines = [ln.strip() for ln in lines if ln.strip() not in recurring_lines]
                if not filtered_lines:
                    continue

                block_text = "\n".join(filtered_lines)

                # Check for figure/diagram captions
                for line_str in filtered_lines:
                    if re.match(r"^(?:Figure|Fig\.|Diagram|Scheme|Illustration|Chart|Plot)\s*[\d\.\-:]*\s*", line_str, re.IGNORECASE):
                        if len(line_str) > 3:
                            figure_captions.append(line_str)

                block_items.append((by0, bx0, block_text))

            # 5. Combine block items and tables in true vertical reading order
            all_content_items = sorted(block_items + table_items, key=lambda item: (item[0], item[1]))

            content_parts = []
            if figure_captions:
                for cap in figure_captions:
                    content_parts.append(f"\n[FIGURE / DIAGRAM: {cap}]\n")
            elif (len(images) > 0 or len(drawings) >= 4) and not table_items:
                visual_desc = []
                if len(images) > 0:
                    visual_desc.append(f"{len(images)} illustration(s)/diagram image(s)")
                if len(drawings) >= 4:
                    visual_desc.append(f"{len(drawings)} technical/chemical/vector drawing path(s)")
                if visual_desc:
                    content_parts.append(f"\n[VISUAL ELEMENTS DETECTED (Page {page_no}): {', '.join(visual_desc)}]\n")

            for item in all_content_items:
                content_parts.append(item[2])

            full_page_text = "\n\n".join(content_parts).strip()
            raw_page_text = "\n".join(raw_text_parts).strip()

            # Evaluate extracted page quality
            quality = check_page_quality(raw_page_text or full_page_text)
            if not quality["is_valid"]:
                scanned_candidate_pages.append(page_no)

            pages.append({
                "page": page_no,
                "printed_label": printed_label,
                "text": full_page_text,
                "raw_text": raw_page_text,
                "has_diagram": bool(figure_captions or images or len(drawings) >= 4),
                "image_count": len(images),
                "drawing_count": len(drawings),
                "quality": quality,
                "captions": figure_captions,
                "toc": doc_toc if page_idx == 0 else None,
            })

        # Validate overall extraction quality against raw extracted text
        total_raw_text_chars = sum(len(p.get("raw_text", "")) for p in pages)
        if total_raw_text_chars < 50 or (len(scanned_candidate_pages) == total_pages and total_pages > 0):
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

        captions = []
        for line in text.splitlines():
            line_str = line.strip()
            if re.match(r"^(?:Figure|Fig\.|Diagram|Scheme|Illustration|Chart)\s*[\d\.\-:]*\s*", line_str, re.IGNORECASE):
                captions.append(line_str)

        content_parts = []
        if captions:
            for cap in captions:
                content_parts.append(f"\n[FIGURE / DIAGRAM: {cap}]\n")
        content_parts.append(text)

        full_text = "\n".join(content_parts).strip()
        quality = check_page_quality(text)
        if not quality["is_valid"]:
            scanned_pages.append(page_number)

        pages.append({
            "page": page_number,
            "printed_label": str(page_number),
            "text": full_text,
            "raw_text": text,
            "has_diagram": bool(captions),
            "image_count": len(getattr(page, "images", [])),
            "drawing_count": 0,
            "quality": quality,
            "captions": captions,
            "toc": [],
        })

    total_chars = sum(len(p["raw_text"]) for p in pages)
    if total_chars < 50 or (len(scanned_pages) == len(pages) and len(pages) > 0):
        pages_str = ", ".join(map(str, scanned_pages[:10]))
        raise PDFScannedError(
            f"This PDF appears to contain scanned pages or photos without selectable digital text (pages: {pages_str}). "
            "Please upload a document with digital text or run OCR before uploading."
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
    """
    path_obj = Path(pdf_path)
    if not path_obj.exists() or path_obj.stat().st_size == 0:
        raise PDFCorruptedError("The uploaded file is empty or missing.")

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