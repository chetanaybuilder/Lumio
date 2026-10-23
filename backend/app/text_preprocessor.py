"""
Text Preprocessor — Lumio Backend
==================================

Normalizes raw text extracted from PDF pages so that downstream modules
(structure detection, chunking, embedding, LLM prompting) receive clean,
consistently formatted input while strictly preserving scientific notation.

Pipeline:
1. Normalizes unicode characters, scientific notation, and encoding artifacts
   (preserves Greek letters α, β, π, λ, Δ; superscripts ² ³, subscripts ₂ ₃,
   arrows → ⇌, relations ≥ ≤ ≈, units, standardizes smart quotes and dashes).
2. Reconstructs damaged chemistry and math font encoding artifacts.
3. Fixes hyphenated line-breaks and soft wraps while keeping paragraph boundaries.
4. Collapses excessive horizontal whitespace while preserving Markdown tables.
5. Limits vertical blank lines while preserving paragraph boundaries.
"""

import re

# ---------------------------------------------------------------------------
# Scientific symbol and encoding normalization
# ---------------------------------------------------------------------------

def _normalize_symbols(text: str) -> str:
    """Normalize common OCR/PDF encoding glitches and scientific symbols."""
    # Convert degree replacement characters like 180 or 109.5 into °
    text = re.sub(r"(\d+(?:\.\d+)?)\s*\ufffd", r"\1°", text)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*\?", r"\1°", text)

    # Normalize hybrid orbital notations like sp -> sp² or sp³
    text = re.sub(r"sp\ufffd", "sp²", text)
    text = re.sub(r"sp\^([0-9])", r"sp^\1", text)

    # Standardize curly quotes and unicode dashes
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2013", "-").replace("\u2014", "--")
    text = text.replace("\u2022", "* ")  # Bullet point
    text = text.replace("\u00a0", " ")   # Non-breaking space

    # Mathematical minus sign (\u2212) -> standardize to hyphen-minus or keep for display
    text = text.replace("\u2212", "-")

    # Normalize any remaining unprintable control characters (except \n, \r, \t)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    return text


# ---------------------------------------------------------------------------
# Chemistry and mathematical notation repair
# ---------------------------------------------------------------------------

def repair_chemistry_notation(text: str) -> str:
    """
    Reconstruct chemical and mathematical formulas affected by font-encoding
    artifacts (e.g. Type 1 ZapfDingbats/Symbol fallbacks in legacy PDF generators).
    Preserves true subscripts, superscripts, arrows, and charges.
    """
    replacements = [
        # Tables and electron pairs
        (r"\bTotal\s*eI\s*pairs\b", "Total e⁻ pairs"),
        (r"\bTotaleIpairs\b", "Total e⁻ pairs"),
        (r"\bBondingpairs\b", "Bonding pairs"),
        (r"\bLonepairs\b", "Lone pairs"),
        (r"\bTrigonalplanar\b", "Trigonal planar"),
        (r"\bTrigonalpyramidal\b", "Trigonal pyramidal"),
        (r"\bTrigonalbipyramidal\b", "Trigonal bipyramidal"),
        (r"\bBondAngle\b", "Bond Angle"),

        # Common molecular formulas with subscript artifacts
        (r"\bBeClI\b", "BeCl₂"),
        (r"\bBFI\b", "BF₃"),
        (r"\bCHI\b", "CH₄"),
        (r"\bNHI\b", "NH₃"),
        (r"\bHIO\b", "H₂O"),
        (r"\bPClI\b", "PCl₅"),
        (r"\bSFI\b", "SF₆"),
        (r"\bSOI\b", "SO₂"),
        (r"\bOI\b", "O₂"),
        (r"\bNI\b", "N₂"),
        (r"\bCOI\b", "CO₂"),
        (r"\bCIHI\b", "C₂H₄"),
        (r"\bCIHIIOI\b", "C₆H₁₂O₆"),

        # Ions, electrons, and coefficients
        (r"\beI\b", "e⁻"),
        (r"\bNaI\b", "Na⁺"),
        (r"\bClI\b", "Cl⁻"),
        (r"\bOHI\b", "OH⁻"),
        (r"\bMnOII\b", "MnO₄⁻"),
        (r"(\d+)?\s*Fe²I\b", lambda m: f"{m.group(1) or ''}Fe²⁺"),
        (r"(\d+)?\s*Fe³I\b", lambda m: f"{m.group(1) or ''}Fe³⁺"),
        (r"(\d+)?\s*Mn²I\b", lambda m: f"{m.group(1) or ''}Mn²⁺"),
        (r"(\d+)?\s*Zn²I\b", lambda m: f"{m.group(1) or ''}Zn²⁺"),
        (r"(\d+)?\s*Cu²I\b", lambda m: f"{m.group(1) or ''}Cu²⁺"),
        (r"(\d+)?\s*HIO\b", lambda m: f"{m.group(1) or ''}H₂O"),
        (r"\bAI\b", "A⁻"),

        # Acid/base notation
        (r"\[HI\]", "[H⁺]"),
        (r"\[OHI\]", "[OH⁻]"),
        (r"\[AI\]", "[A⁻]"),
        (r"\bCHICOOH\b", "CH₃COOH"),
        (r"\bCHICOOI\b", "CH₃COO⁻"),
        (r"\bHNOI\b", "HNO₃"),
        (r"\bHISOI\b", "H₂SO₄"),

        # Powers of 10 and scientific notation
        (r"10II\b", "10⁻⁷"),
        (r"10I¹I\b", "10⁻¹⁴"),
        (r"10I²³\b", "10⁻²³"),
        (r"10I\s*m/s", "10⁷ m/s"),
        (r"J\s*molI¹\s*KI¹", "J mol⁻¹ K⁻¹"),

        # Gas law subscripts
        (r"PIVI\s*=\s*PIVI", "P₁V₁ = P₂V₂"),
        (r"VI/TI\s*=\s*VI/TI", "V₁/T₁ = V₂/T₂"),

        # Equilibrium and quantum mechanics
        (r"aA\s*\+\s*bB\s*I\s*cC\s*\+\s*dD", "aA + bB ⇌ cC + dD"),
        (r"∆x\s*·\s*∆p\s*≥\s*I/2", "∆x · ∆p ≥ ħ/2"),
        (r"∆x\s*\.\s*∆p\s*≥\s*I/2", "∆x · ∆p ≥ ħ/2"),
        (r"2pI\b", "2p⁶"),
        (r"3pI\b", "3p⁶"),
        (r"3dI\b", "3d⁶"),
        (r"3d¹I\b", "3d¹⁰"),
        (r"HI\b(?=\s*\+)", "H⁺"),
        (r"HI\b(?=\s*\(acidic\))", "H⁺"),
        (r"(\b\w+)I\b(?=\s*\([a-z]+\))", r"\1⁺"),
    ]

    for pattern, repl in replacements:
        if callable(repl):
            text = re.sub(pattern, repl, text)
        else:
            text = re.sub(pattern, repl, text)

    return text


# ---------------------------------------------------------------------------
# Hyphenation and soft line wrap repair
# ---------------------------------------------------------------------------

def _fix_hyphenation_and_wraps(text: str) -> str:
    """
    Join hyphenated words broken across line breaks (e.g. 'struc-\\nture' -> 'structure')
    and combine soft-wrapped lines belonging to the same paragraph without disturbing
    Markdown tables, headings, or bulleted lists.
    """
    # 1. Fix explicit hyphenated line breaks: 'chemi-\ncal' -> 'chemical'
    text = re.sub(r"([A-Za-z]{2,})-\n\s*([A-Za-z]{2,})", r"\1\2", text)

    # 2. Join lines that don't end in sentence-ending punctuation or structural tokens
    processed_lines = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            processed_lines.append("")
            i += 1
            continue

        # Check if current line is a table, heading, diagram tag, or list bullet
        is_structural = (
            line.startswith("|")
            or line.startswith("#")
            or line.startswith("* ")
            or line.startswith("- ")
            or line.startswith("[")
            or re.match(r"^\d+\.\s+", line)
            or re.match(r"^(?:Chapter|Section|Unit|PART)\b", line, re.IGNORECASE)
            or line.endswith(":")
        )

        if is_structural:
            processed_lines.append(line)
            i += 1
            continue

        # Accumulate paragraph text
        para_parts = [line]
        while i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if not next_line:
                break
            # Check if next line starts a new structure
            next_is_structural = (
                next_line.startswith("|")
                or next_line.startswith("#")
                or next_line.startswith("* ")
                or next_line.startswith("- ")
                or next_line.startswith("[")
                or re.match(r"^\d+\.\s+", next_line)
                or re.match(r"^(?:Chapter|Section|Unit|PART)\b", next_line, re.IGNORECASE)
                or (len(para_parts[-1]) > 0 and para_parts[-1][-1] in (".", "?", "!"))
            )
            if next_is_structural:
                break

            para_parts.append(next_line)
            i += 1

        processed_lines.append(" ".join(para_parts))
        i += 1

    return "\n".join(processed_lines)


# ---------------------------------------------------------------------------
# Core vocabulary for quality check
# ---------------------------------------------------------------------------

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
    """
    if not text:
        return {"is_valid": False, "dictionary_ratio": 0.0, "weird_symbol_ratio": 1.0, "char_count": 0, "reason": "empty"}

    raw_clean = re.sub(r"\s+", "", text)
    char_count = len(raw_clean)
    if char_count < 30:
        return {"is_valid": False, "dictionary_ratio": 0.0, "weird_symbol_ratio": 0.0, "char_count": char_count, "reason": "too_short"}

    words = [w.lower() for w in re.findall(r"[A-Za-z]{2,}", text)]
    if not words:
        return {"is_valid": False, "dictionary_ratio": 0.0, "weird_symbol_ratio": 1.0, "char_count": char_count, "reason": "no_words"}

    valid_words = sum(1 for w in words if w in _COMMON_VOCAB or len(w) > 4)
    dictionary_ratio = valid_words / len(words)

    weird_chars = len(re.findall(r"[\ufffd\x00-\x08\x0b\x0c\x0e-\x1f]", text))
    weird_symbol_ratio = weird_chars / max(1, char_count)

    bracket_anomaly = (text.count("[") + text.count("]")) > 30 and (text.count(".") + text.count(",")) < 5

    is_valid = (
        dictionary_ratio >= 0.50
        and weird_symbol_ratio <= 0.15
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
    """
    if not text:
        return ""

    # 1. Normalize encoding and scientific symbols
    text = _normalize_symbols(text)

    # 2. Repair damaged chemistry notation (font encoding artifacts)
    text = repair_chemistry_notation(text)

    # 3. Fix hyphenated line breaks and soft wraps into clean paragraphs
    text = _fix_hyphenation_and_wraps(text)

    # 4. Collapse horizontal whitespace (tabs, multiple spaces) to one space,
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
    """Apply ``clean_text`` to every page in a list of page dictionaries."""
    cleaned_pages = []
    for page in pages:
        cleaned = dict(page)
        cleaned["text"] = clean_text(page.get("text", ""))
        cleaned_pages.append(cleaned)
    return cleaned_pages