from pathlib import Path
from typing import Generator, List, Dict, Any, Tuple
import fitz

class ExtractionError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(detail)

def inspect_and_open_pdf(file_path: Path) -> fitz.Document:
    """
    Opens PDF with strict integrity checks:
    - Checks file existence and minimum size
    - Checks for encryption (ENCRYPTED)
    - Checks page count (0 pages or > 1500 pages: TOO_MANY_PAGES)
    - Catches corrupt xrefs (CORRUPT_PDF)
    """
    if not file_path.exists():
        raise ExtractionError("NOT_FOUND", "File not found on disk")

    if file_path.stat().st_size == 0:
        raise ExtractionError("CORRUPT_PDF", "File is empty")

    try:
        doc = fitz.open(str(file_path))
    except Exception as e:
        raise ExtractionError("CORRUPT_PDF", f"PyMuPDF failed to open PDF: {str(e)}")

    if doc.is_encrypted:
        doc.close()
        raise ExtractionError("ENCRYPTED", "Password-protected or encrypted PDFs are not supported")

    total_pages = len(doc)
    if total_pages == 0:
        doc.close()
        raise ExtractionError("ZERO_PAGES", "PDF contains zero pages")

    if total_pages > 1500:
        doc.close()
        raise ExtractionError("TOO_MANY_PAGES", f"PDF has {total_pages} pages, which exceeds the limit of 1500")

    return doc

def stream_pdf_batches(doc: fitz.Document, batch_size: int = 10, start_page: int = 0) -> Generator[List[Dict[str, Any]], None, None]:
    """
    Iterates through PDF pages in batches of 10.
    Releases page objects after each batch to keep memory bounded under 600MB RSS.
    """
    total_pages = len(doc)
    for i in range(start_page, total_pages, batch_size):
        batch = []
        end_idx = min(i + batch_size, total_pages)
        for page_idx in range(i, end_idx):
            page = doc[page_idx]
            text = page.get_text()
            page_dict = page.get_text('dict')
            batch.append({
                "page_num": page_idx + 1,
                "text": text,
                "dict": page_dict,
                "rect": (page.rect.width, page.rect.height)
            })
        yield batch
