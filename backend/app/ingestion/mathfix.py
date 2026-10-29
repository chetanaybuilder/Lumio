import re
import fitz
from typing import Dict, Any, List

MATH_FONT_RE = re.compile(r'(CM(MI|SY|EX|R)|Symbol|MathematicalPi|Cambria Math|STIX)', re.IGNORECASE)

def classify_page(page: fitz.Page) -> str:
    """
    Classifies a PDF page into: 'scanned', 'math_heavy', or 'text'.
    Heuristics:
    1. Scanned: fewer than 25 characters and an image covering > 60% of page area.
    2. Math-heavy: > 3% math/arrow/Greek characters, or math font, or stacked fractions.
    3. Text: everything else.
    """
    text = page.get_text()
    char_count = len(text.strip())
    page_area = page.rect.width * page.rect.height

    # Check scanned heuristic
    image_list = page.get_images()
    if char_count < 25 and len(image_list) > 0:
        for img_info in image_list:
            try:
                rects = page.get_image_rects(img_info[0])
                for r in rects:
                    if (r.width * r.height) / page_area > 0.60:
                        return "scanned"
            except Exception:
                pass

    if char_count == 0:
        return "scanned" if len(image_list) > 0 else "text"

    # Check math characters
    math_chars = 0
    for ch in text:
        cp = ord(ch)
        # Unicode math blocks: U+2200-U+22FF, arrows: U+2190-U+21FF, Greek: U+0370-U+03FF
        if (0x2200 <= cp <= 0x22FF) or (0x2190 <= cp <= 0x21FF) or (0x0370 <= cp <= 0x03FF):
            math_chars += 1

    if (math_chars / max(1, char_count)) > 0.03:
        return "math_heavy"

    # Check font names using page.get_text('dict')
    page_dict = page.get_text('dict')
    for block in page_dict.get('blocks', []):
        if block.get('type') == 0:  # text block
            for line in block.get('lines', []):
                for span in line.get('spans', []):
                    font = span.get('font', '')
                    if MATH_FONT_RE.search(font):
                        return "math_heavy"

    return "text"

def render_page_to_png_bytes(page: fitz.Page, dpi: int = 150) -> bytes:
    """Renders a PDF page to PNG at 150 dpi for Gemini vision transcription."""
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    return pix.tobytes("png")
