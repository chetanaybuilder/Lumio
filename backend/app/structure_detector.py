"""
Structure Detector — Lumio Backend
===================================

Scans cleaned PDF pages line by line and groups content into logical
sections based on heuristic heading detection.  Two patterns are
currently recognized as headings:

1. Lines starting with ``Chapter <number>`` (case-insensitive).
2. Lines starting with a dotted numeric prefix like ``1.2.3 ...``.

Any content that appears before the first detected heading is placed
into a default section titled "Document Content".

Each section records its heading text, the page where it begins, and a
list of ``(page, text)`` content entries.  These sections feed into the
chunker, which splits them into overlapping windows for embedding.

Limitations
-----------
The detector is purely heuristic.  Headings that do not match the two
patterns above remain ordinary content lines.  Complex layouts, multi-
column documents, or non-standard numbering schemes may not be detected.
"""

import re


# ---------------------------------------------------------------------------
# Heading detection heuristics
# ---------------------------------------------------------------------------

def _is_heading(line: str) -> bool:
    """
    Return ``True`` if *line* matches a recognized heading pattern.

    Recognized patterns:
    - ``Chapter 1``, ``CHAPTER 12``, etc. (case-insensitive).
    - ``1.2``, ``3.4.5 Title Text``, or any dotted numeric prefix.
    """
    return bool(
        re.match(r"^Chapter\s+\d+", line, re.IGNORECASE)
        or re.match(r"^\d+(\.\d+)*\s+", line)
    )


# ---------------------------------------------------------------------------
# Main detection function
# ---------------------------------------------------------------------------

def detect_structure(pages: list) -> list:
    """
    Split page content into sections delimited by detected headings.

    Parameters
    ----------
    pages : list[dict]
        Cleaned pages, each containing ``"page"`` (int) and ``"text"``
        (str).

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
            line = line.strip()

            # Skip blank lines — they carry no structural information.
            if not line:
                continue

            if _is_heading(line):
                # Start a new section whenever a heading is found.
                current_section = {
                    "heading": line,
                    "start_page": page_number,
                    "content": [],
                }
                sections.append(current_section)
            else:
                # Create a default section for content before any heading.
                if current_section is None:
                    current_section = {
                        "heading": "Document Content",
                        "start_page": page_number,
                        "content": [],
                    }
                    sections.append(current_section)

                # Append the content line to the active section.
                current_section["content"].append({
                    "page": page_number,
                    "text": line,
                })

    return sections


# Structure detection is heuristic; unrecognized headings stay as content.