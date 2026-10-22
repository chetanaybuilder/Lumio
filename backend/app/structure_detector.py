"""
Structure Detector — Lumio Backend
===================================

Scans cleaned PDF pages line by line and groups content into logical
sections based on robust educational heading detection.

Recognized heading patterns:
1. Chapter / Unit / Module markers:
   - ``Chapter 1``, ``CHAPTER 12: Atomic Structure``
   - ``Unit 3``, ``Module 2``, ``Section 4``
2. Dotted numeric section prefixes:
   - ``1.1 Introduction``, ``2.3 Covalent Bonding``, ``4.2.1 Hess's Law``
3. Educational landmark headings:
   - ``Summary``, ``Key Concepts``, ``Important Formulas``, ``Exercises``
4. Diagram & Figure structural markers:
   - ``[FIGURE / DIAGRAM: ...]``
   - ``[STRUCTURED TABLES (Page ...)]``
"""

import re


# ---------------------------------------------------------------------------
# Heading detection heuristics
# ---------------------------------------------------------------------------

_LANDMARK_HEADINGS = {
    "summary",
    "key concepts",
    "core concepts",
    "review questions",
    "exercises",
    "important formulas",
    "glossary",
    "conclusions",
    "practice problems",
    "learning objectives",
}


def _is_heading(line: str) -> bool:
    """
    Return ``True`` if *line* matches a recognized textbook heading pattern.

    Heuristics:
    - Line length must be reasonable for a title (<= 140 characters).
    - Must not end with a sentence-ending period unless it's a short numbered prefix.
    """
    line_clean = line.strip()
    if not line_clean or len(line_clean) > 140:
        return False

    # Diagram or Table structural markers
    if line_clean.startswith("[FIGURE / DIAGRAM:") or line_clean.startswith("[STRUCTURED TABLES"):
        return True

    # Chapter, Unit, Module, Section markers
    if re.match(r"^(?:Chapter|Unit|Module|Section|Topic)\s+\d+[:\s\-]?", line_clean, re.IGNORECASE):
        return True

    # Dotted numeric section prefix (e.g. "1.1", "2.3.4 Title", but not a sentence ending in a period like "1. The dog ran.")
    if re.match(r"^\d+\.\d+(?:\.\d+)*\s+[A-Z]", line_clean):
        return True

    # Educational landmark sections
    if line_clean.lower() in _LANDMARK_HEADINGS:
        return True

    # Roman numeral parts (e.g. "PART I: MECHANICS")
    if re.match(r"^PART\s+[IVXLCDM]+[:\s]", line_clean, re.IGNORECASE):
        return True

    # Prominent all-caps short title (between 4 and 60 chars, no terminal period)
    if (
        len(line_clean) >= 4
        and len(line_clean) <= 60
        and line_clean.isupper()
        and not line_clean.endswith(".")
        and any(c.isalpha() for c in line_clean)
        and not line_clean.startswith("PAGE ")
    ):
        return True

    return False


# ---------------------------------------------------------------------------
# Main detection function
# ---------------------------------------------------------------------------

def detect_structure(pages: list) -> list:
    """
    Split page content into sections delimited by detected headings.

    Parameters
    ----------
    pages : list[dict]
        Cleaned pages, each containing ``"page"`` (int) and ``"text"`` (str).

    Returns
    -------
    list[dict]
        Sections, each with:
        - ``heading`` (str): the detected heading text.
        - ``start_page`` (int): the page where the section begins.
        - ``content`` (list[dict]): items with ``"page"`` and ``"text"``.
    """
    sections = []
    current_section = None

    for page in pages:
        page_number = page["page"]
        text = page["text"]

        for line in text.splitlines():
            line_str = line.strip()

            if not line_str:
                continue

            if _is_heading(line_str):
                current_section = {
                    "heading": line_str,
                    "start_page": page_number,
                    "content": [],
                }
                sections.append(current_section)
            else:
                if current_section is None:
                    current_section = {
                        "heading": "Document Overview",
                        "start_page": page_number,
                        "content": [],
                    }
                    sections.append(current_section)

                current_section["content"].append({
                    "page": page_number,
                    "text": line_str,
                })

    return sections