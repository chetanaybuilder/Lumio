"""
Text Preprocessor — Lumio Backend
==================================

Normalizes raw text extracted from PDF pages so that downstream modules
(structure detection, chunking, embedding) receive consistently formatted
input.  The cleaning pipeline:

1. Collapses runs of horizontal whitespace to single spaces.
2. Strips leading/trailing whitespace from every line.
3. Reduces three or more consecutive newlines to exactly two (preserving
   paragraph boundaries without excessive blank lines).

The preprocessor is intentionally conservative: it preserves words and
paragraph structure while removing the layout noise that PDF renderers
introduce (e.g., irregular spacing, trailing spaces, and blank-line runs).
"""

import re


# ---------------------------------------------------------------------------
# Single-text cleaning
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """
    Normalize whitespace in a single text string.

    Parameters
    ----------
    text : str
        Raw text extracted from one PDF page.

    Returns
    -------
    str
        The cleaned text with normalized whitespace and trimmed lines.
    """
    # Collapse horizontal whitespace (tabs, multiple spaces) to one space.
    text = re.sub(r"[^\S\n]+", " ", text)

    # Strip leading/trailing whitespace from each line independently.
    text = "\n".join(line.strip() for line in text.splitlines())

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
        A new list with the same page numbers and cleaned text.
    """
    cleaned_pages = []
    for page in pages:
        cleaned_pages.append({
            "page": page["page"],
            "text": clean_text(page["text"]),
        })
    return cleaned_pages


# Preserve extracted words while normalizing PDF layout noise.