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
# ---------------------------------------------------------------------------
# Scientific symbol, subscript, and Greek letter normalization
# ---------------------------------------------------------------------------

_GREEK_AND_MATH_MAP = {
    # Greek letters
    "\u03b1": "alpha", "\u03b2": "beta", "\u03b3": "gamma", "\u03b4": "delta",
    "\u0394": "Delta", "\u03b5": "epsilon", "\u03b8": "theta", "\u03bb": "lambda",
    "\u03bc": "mu", "\u03bd": "nu", "\u03c0": "pi", "\u03c1": "rho",
    "\u03c3": "sigma", "\u03c4": "tau", "\u03c6": "phi", "\u03c8": "psi", "\u03c9": "omega",
    # Arrows and relations
    "\u2192": " -> ", "\u21cc": " <=> ", "\u2194": " <-> ", "\u21d2": " => ",
    "\u2264": " <= ", "\u2265": " >= ", "\u2260": " != ", "\u2248": " ~= ",
    "\u00b1": " +/- ", "\u00d7": " x ", "\u2212": "-",
    # Common superscripts & subscripts
    "\u2070": "^0", "\u00b9": "^1", "\u00b2": "^2", "\u00b3": "^3",
    "\u2074": "^4", "\u2075": "^5", "\u2076": "^6", "\u2077": "^7", "\u2078": "^8", "\u2079": "^9",
    "\u207a": "^+", "\u207b": "^-",
    "\u2080": "_0", "\u2081": "_1", "\u2082": "_2", "\u2083": "_3",
    "\u2084": "_4", "\u2085": "_5", "\u2086": "_6", "\u2087": "_7", "\u2088": "_8", "\u2089": "_9",
}

# Core dictionary of common English words + STEM academic terminology for quality verification
_COMMON_VOCAB = {
    "the", "of", "and", "a", "to", "in", "is", "you", "that", "it", "he", "was", "for", "on", "are",
    "as", "with", "his", "they", "i", "at", "be", "this", "have", "from", "or", "one", "had", "by",
    "word", "but", "not", "what", "all", "were", "we", "when", "your", "can", "said", "there", "use",
    "an", "each", "which", "she", "do", "how", "their", "if", "will", "up", "other", "about", "out",
    "many", "then", "them", "these", "so", "some", "her", "would", "make", "like", "him", "into",
    "time", "has", "look", "two", "more", "write", "go", "see", "number", "no", "way", "could",
    "people", "my", "than", "first", "water", "been", "call", "who", "oil", "its", "now", "find",
    "atom", "atomic", "electron", "proton", "neutron", "nucleus", "orbit", "orbital", "energy",
    "level", "quantum", "mass", "charge", "ratio", "experiment", "model", "structure",
    "bond", "bonding", "chemical", "covalent", "ionic", "molecule", "molecular", "compound",
    "reaction", "equilibrium", "thermodynamics", "enthalpy", "entropy", "free", "gibbs",
    "state", "gas", "liquid", "solid", "pressure", "volume", "temperature", "equation",
    "acid", "base", "solution", "concentration", "molar", "solubility", "buffer", "redox",
    "oxidation", "reduction", "electrode", "potential", "cell", "current", "hybrid", "hybridization",
    "resonance", "organic", "carbon", "isomer", "nomenclature", "formula", "law", "constant",
    "table", "figure", "diagram", "process", "rule", "theory", "discovery", "particles",
    "principal", "momentum", "magnetic", "spin", "geometry", "shape", "linear", "trigonal",
    "tetrahedral", "octahedral", "pyramidal", "bent", "dipole", "polar", "nonpolar",
    "boiling", "melting", "point", "vapour", "colligative", "osmotic", "factor", "catalyst",
    "rate", "half", "life", "second", "zero", "order", "activation", "mechanism",
    "chapter", "section", "topic", "summary", "exercise", "example", "problem",
}


def check_page_quality(text: str) -> dict:
    """
    Evaluate the quality of extracted text on a page.
    Detects whether a page has authentic text or requires OCR / vision fallback.

    Returns
    -------
    dict
        - ``is_valid`` (bool): True if quality meets standards.
        - ``dictionary_ratio`` (float): Share of recognized words.
        - ``weird_symbol_ratio`` (float): Ratio of abnormal characters.
        - ``char_count`` (int): Length of non-whitespace text.
    """
    if not text:
        return {"is_valid": False, "dictionary_ratio": 0.0, "weird_symbol_ratio": 1.0, "char_count": 0, "reason": "empty"}

    raw_clean = re.sub(r"\s+", "", text)
    char_count = len(raw_clean)
    if char_count < 30:
        return {"is_valid": False, "dictionary_ratio": 0.0, "weird_symbol_ratio": 0.0, "char_count": char_count, "reason": "too_short"}

    # Extract all alphabetical words of length 2+
    words = [w.lower() for w in re.findall(r"[A-Za-z]{2,}", text)]
    if not words:
        return {"is_valid": False, "dictionary_ratio": 0.0, "weird_symbol_ratio": 1.0, "char_count": char_count, "reason": "no_words"}

    valid_words = sum(1 for w in words if w in _COMMON_VOCAB or len(w) > 4)
    dictionary_ratio = valid_words / len(words)

    # Weird symbols (replacement \ufffd, control characters, bizarre non-ascii)
    weird_chars = len(re.findall(r"[\ufffd\x00-\x08\x0b\x0c\x0e-\x1f]", text))
    weird_symbol_ratio = weird_chars / max(1, char_count)

    # Check for excessive unspaced letter chains or bizarre bracket density
    unbalanced_brackets = abs(text.count("[") - text.count("]")) + abs(text.count("(") - text.count(")"))
    bracket_anomaly = (text.count("[") + text.count("]")) > 30 and (text.count(".") + text.count(",")) < 5

    is_valid = (
        dictionary_ratio >= 0.55
        and weird_symbol_ratio <= 0.10
        and not bracket_anomaly
    )

    return {
        "is_valid": is_valid,
        "dictionary_ratio": round(dictionary_ratio, 3),
        "weird_symbol_ratio": round(weird_symbol_ratio, 3),
        "char_count": char_count,
        "reason": "ok" if is_valid else "low_quality_text",
    }


# ---------------------------------------------------------------------------
# Single-text cleaning
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """
    Normalize whitespace, encoding artifacts, and structure in a single page string.
    Preserves all real text, variables, formulas, and headings without destructive shifting.

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

    # Map Greek letters, math symbols, superscripts/subscripts
    for orig, repl in _GREEK_AND_MATH_MAP.items():
        if orig in text:
            text = text.replace(orig, repl)

    # Normalize scientific symbols and encoding glitches
    text = _normalize_symbols(text)

    # Collapse horizontal whitespace (tabs, multiple spaces) to one space,
    # preserving table rows and markdown structure cleanly.
    lines = []
    for line in text.splitlines():
        line_stripped = line.strip()
        if not line_stripped:
            lines.append("")
        elif line_stripped.startswith("|") and line_stripped.endswith("|"):
            # Table row: collapse redundant inner spaces
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