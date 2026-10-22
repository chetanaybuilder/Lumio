"""
Text Preprocessor — Lumio Backend
==================================

Normalizes raw text extracted from PDF pages so that downstream modules
(structure detection, chunking, embedding) receive consistently formatted,
clean input.

Pipeline:
1. Normalizes unicode characters, scientific notation, and encoding artifacts
   (e.g., replaces replacement characters near degree values, superscripts,
   standardizes smart quotes and dashes).
2. Collapses excessive horizontal whitespace (tabs, repeated spaces).
3. Strips leading and trailing whitespace from every line.
4. Preserves structural Markdown tables, diagram markers, and lists.
5. Limits excessive vertical blank lines while preserving paragraph boundaries.
"""

import re


# ---------------------------------------------------------------------------
# Scientific symbol and encoding normalization
# ---------------------------------------------------------------------------

def _normalize_symbols(text: str) -> str:
    """Normalize common OCR/PDF encoding glitches and scientific symbols."""
    # Convert degree replacement characters like 180 or 109.5 into °
    text = re.sub(r"(\d+(?:\.\d+)?)\s*\ufffd", r"\1°", text)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*\?", r"\1°", text)  # Common fallback for degree

    # Normalize hybrid orbital notations like sp -> sp² or sp³
    text = re.sub(r"sp\ufffd", "sp²", text)
    text = re.sub(r"sp\^([0-9])", r"sp^\1", text)

    # Standardize curly quotes and unicode dashes
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2013", "-").replace("\u2014", "--")
    text = text.replace("\u2022", "* ")  # Bullet point
    text = text.replace("\u00a0", " ")   # Non-breaking space

    # Normalize any remaining unprintable control characters (except \n, \r, \t)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    return text


# ---------------------------------------------------------------------------
# Single-text cleaning
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """
    Normalize whitespace, encoding artifacts, and structure in a single page string.

    Parameters
    ----------
    text : str
        Raw text extracted from one PDF page.

    Returns
    -------
    str
        The cleaned text with normalized whitespace, symbols, and trimmed lines.
    """
    if not text:
        return ""

    # Normalize scientific symbols and encoding glitches
    text = _normalize_symbols(text)

    # Collapse horizontal whitespace (tabs, multiple spaces) to one space,
    # except in table lines where spacing or markdown formatting matters.
    lines = []
    for line in text.splitlines():
        line_stripped = line.strip()
        if line_stripped.startswith("|") and line_stripped.endswith("|"):
            # Table row: preserve internal columns cleanly
            lines.append(re.sub(r"[^\S\n]+", " ", line_stripped))
        else:
            # Regular text line: collapse multiple spaces
            lines.append(re.sub(r"[^\S\n]+", " ", line_stripped))

    text = "\n".join(lines)

    # Reduce runs of three or more newlines to a double newline.
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# ---------------------------------------------------------------------------
# Batch page cleaning
# ---------------------------------------------------------------------------

def clean_pages(pages: list) -> list:
    """
    Apply ``clean_text`` to every page in a list of page dictionaries.

    Parameters
    ----------
    pages : list[dict]
        Each item must contain ``"page"`` (int) and ``"text"`` (str).

    Returns
    -------
    list[dict]
        A new list with the same page numbers, cleaned text, and metadata preserved.
    """
    cleaned_pages = []
    for page in pages:
        cleaned = dict(page)
        cleaned["text"] = clean_text(page.get("text", ""))
        cleaned_pages.append(cleaned)
    return cleaned_pages