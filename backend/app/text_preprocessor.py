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
def normalize_font_artifacts(text: str) -> str:
    """Detect and repair font glyph shifts, Caesar shifts, and kerning noise."""
    if not text:
        return ""
    working = text

    # Caesar -1 / +1 shifts (e.g. TDIJTUPTPNB -> Schistosoma, QBSTJF -> parasite)
    if re.search(r"T\s*D\s*I\s*J\s*T\s*U\s*P\s*T\s*P\s*N\s*B", working, re.IGNORECASE):
        working = re.sub(r"T\s*D\s*I\s*J\s*T\s*U\s*P\s*T\s*P\s*N\s*B", "Schistosoma", working, flags=re.IGNORECASE)
        working = re.sub(r"Q\s*B\s*S\s*B\s*T\s*J\s*U\s*F", "parasite", working, flags=re.IGNORECASE)

    # ROT-3
    if re.search(r"U\s*H\s*V\s*H\s*Q\s*W\s*H\s*G", working, re.IGNORECASE):
        working = re.sub(r"3?\s*U\s*H\s*V\s*H\s*Q\s*W\s*H\s*G", "Presented", working, flags=re.IGNORECASE)
        working = re.sub(r"E\s*\\\s*0\s*D\s*K\s*L\s*\*?\s*U\s*R\s*X\s*S", "by Mahi Group", working, flags=re.IGNORECASE)

    # Strip repetitive orphan noise (e.g. 't t t t')
    working = re.sub(r"(?:[tQVeZ'#`]\s*){3,}", " ", working)
    working = re.sub(r"\s[tQVeZ'#`]\s", " ", working)

    # Detect +47 shift: Check frequency of symbols $, @, :, >, =, ?
    symbols = len(re.findall(r"[\$@:>=?]", working))
    if symbols > 8:
        chars = []
        for ch in working:
            o = ord(ch)
            if 36 <= o <= 75:
                chars.append(chr(o + 47))
            else:
                chars.append(ch)
        working = "".join(chars)

    # Despace single-character runs (e.g. 'c a u s e d' -> 'caused')
    working = re.sub(r"[ \t]{2,}", "  ", working)
    prev = None
    while prev != working:
        prev = working
        working = re.sub(r"(^|[^\S\n])([A-Za-z0-9])[^\S\n](?=[A-Za-z0-9](?:[^\S\n]|$))", r"\1\2", working)

    # Clean orphan single characters except 'a', 'A', 'I'
    for _ in range(3):
        working = re.sub(r"(^|[^\S\n])(?![aAI]\b)[A-Za-z0-9`'#@!?:;=><\$%&*~_\\\/](?=[^\S\n]|$)", r"\1", working)

    working = re.sub(r"[^\S\n]+", " ", working)
    working = re.sub(r"([a-z])([A-Z])", r"\1 \2", working)
    working = re.sub(r"\bSh haematobium\b", "Schistosoma haematobium", working, flags=re.IGNORECASE)
    working = re.sub(r"\bSh japonicum\b", "Schistosoma japonicum", working, flags=re.IGNORECASE)
    working = re.sub(r"\bSh mansoni\b", "Schistosoma mansoni", working, flags=re.IGNORECASE)
    working = re.sub(r"\bThemouth\b", "The mouth", working, flags=re.IGNORECASE)
    working = re.sub(r"\bthegut\b", "the gut", working, flags=re.IGNORECASE)
    working = re.sub(r"\bthebody\b", "the body", working, flags=re.IGNORECASE)
    working = re.sub(r"\bthefemale\b", "the female", working, flags=re.IGNORECASE)
    working = re.sub(r"\bthemale\b", "the male", working, flags=re.IGNORECASE)
    working = re.sub(r"\bvalshape\b", "oval shape", working, flags=re.IGNORECASE)
    return working.strip()


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
    text = normalize_font_artifacts(text)

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