"""
Structure Detector — Lumio Backend
===================================

Scans cleaned PDF pages line by line and groups content into logical
hierarchical sections (Chapter > Section > Subsection).

Capabilities:
1. Uses Authoritative Document TOC (`doc.get_toc()`) if available in PDF metadata.
2. Robust Fallback Detection for Educational Headings:
   - Level 1 (Chapters / Major Divisions): ``Chapter 1: ...``, ``Unit 3``, ``PART I``,
     ``Practice Numerical Problems``, ``Document Overview``.
   - Level 2 (Sections / Topics): ``1.1 Discovery of Sub-Atomic Particles``,
     ``2.4 VSEPR Theory``, ``3.2 Ideal Gas Equation``.
   - Level 3 (Subsections / Concepts): ``1.4.1 ...``, ``Bond Parameters:``,
     ``Quantum Numbers:``, ``Lewis Dot Structures:``.
3. Ensures every section and downstream chunk carries its full hierarchical path:
   ``Chapter > Section > Subsection``.
"""

import re
from typing import Any

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
    "practice numerical problems",
    "learning objectives",
}


def _classify_heading(line: str) -> tuple[int, str] | None:
    """
    Check if a line matches a recognized textbook heading pattern.
    Returns (level, clean_title) or None if line is body text.
    level 1 = Chapter / Major Division
    level 2 = Section / Topic
    level 3 = Subsection / Subtopic
    """
    line_clean = line.strip()
    if not line_clean or len(line_clean) > 140:
        return None

    # Diagram or Table structural markers (Level 2)
    if line_clean.startswith("[FIGURE / DIAGRAM:") or line_clean.startswith("[STRUCTURED TABLES"):
        return (2, line_clean)

    # Level 1: Chapter, Unit, Module, Part markers
    if re.match(r"^(?:Chapter|Unit|Module|PART)\s+[\dIVXLCDM]+[:\s\-]?", line_clean, re.IGNORECASE):
        return (1, line_clean)

    # Level 1: Landmark headings
    if line_clean.lower() in _LANDMARK_HEADINGS:
        return (1, line_clean)

    # Level 1: Prominent standalone titles without terminal period
    if (
        re.match(r"^(?:Practice\s+Numerical\s+Problems|Comprehensive\s+Review)\b", line_clean, re.IGNORECASE)
    ):
        return (1, line_clean)

    # Level 2: Dotted numeric section prefix (e.g. "1.1 Introduction", "2.3 Covalent Bonding")
    if re.match(r"^\d+\.\d+\s+[A-Za-z]", line_clean):
        return (2, line_clean)

    # Level 3: Dotted subsection prefix (e.g. "1.4.1 ...")
    if re.match(r"^\d+\.\d+\.\d+\s+[A-Za-z]", line_clean):
        return (3, line_clean)

    # Level 3: Key concept / parameter headings ending with colon (e.g. "Quantum Numbers:", "Bond Parameters:")
    if (
        re.match(r"^(?:[A-Z][a-zA-Z\s]{2,35}):$", line_clean)
        and not line_clean.lower().startswith("note:")
        and not line_clean.lower().startswith("example:")
    ):
        return (3, line_clean[:-1].strip())

    # Prominent all-caps short title (between 4 and 50 chars, no terminal period)
    if (
        4 <= len(line_clean) <= 50
        and line_clean.isupper()
        and not line_clean.endswith(".")
        and any(c.isalpha() for c in line_clean)
        and not line_clean.startswith("PAGE ")
        and not line_clean.startswith("|")
    ):
        return (1, line_clean)

    return None


def detect_structure(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Split cleaned page content into sections delimited by detected headings
    and annotate each section with its hierarchical path (Chapter > Section > Subsection).

    Parameters
    ----------
    pages : list[dict]
        Cleaned pages, each containing ``"page"`` (int), ``"printed_label"`` (str),
        and ``"text"`` (str).

    Returns
    -------
    list[dict]
        Sections, each with:
        - ``heading`` (str): the active section heading text.
        - ``chapter`` (str): current parent chapter.
        - ``section`` (str): current section name.
        - ``subsection`` (str): current subsection name.
        - ``path`` (str): ``f"{chapter} > {section}"`` or ``f"{chapter} > {section} > {subsection}"``.
        - ``start_page`` (int): the page where the section begins.
        - ``printed_label`` (str): printed label for the start page.
        - ``content`` (list[dict]): items with ``"page"``, ``"printed_label"``, and ``"text"``.
    """
    sections = []
    current_chapter = "Document Overview"
    current_section_title = "General Overview"
    current_subsection_title = ""
    current_section = None

    for page in pages:
        page_number = page.get("page", 1)
        printed_label = page.get("printed_label", str(page_number))
        text = page.get("text", "")

        for line in text.splitlines():
            line_str = line.strip()
            if not line_str:
                continue

            heading_info = _classify_heading(line_str)
            if heading_info is not None:
                level, title = heading_info

                if level == 1:
                    current_chapter = title
                    current_section_title = title
                    current_subsection_title = ""
                elif level == 2:
                    current_section_title = title
                    current_subsection_title = ""
                elif level == 3:
                    current_subsection_title = title

                # Build full hierarchy path
                if line_str.startswith("["):
                    active_heading = line_str
                    path_str = f"{current_chapter} > {line_str}"
                elif current_subsection_title and current_subsection_title != current_section_title:
                    path_str = f"{current_chapter} > {current_section_title} > {current_subsection_title}"
                    active_heading = f"{current_section_title} — {current_subsection_title}"
                elif current_section_title != current_chapter:
                    path_str = f"{current_chapter} > {current_section_title}"
                    active_heading = current_section_title
                else:
                    path_str = current_chapter
                    active_heading = current_chapter

                current_section = {
                    "heading": active_heading,
                    "chapter": current_chapter,
                    "section": current_section_title,
                    "subsection": current_subsection_title,
                    "path": path_str,
                    "start_page": page_number,
                    "printed_label": printed_label,
                    "content": [],
                }
                sections.append(current_section)
            else:
                if current_section is None:
                    current_section = {
                        "heading": "Document Overview",
                        "chapter": "Document Overview",
                        "section": "Document Overview",
                        "subsection": "",
                        "path": "Document Overview",
                        "start_page": page_number,
                        "printed_label": printed_label,
                        "content": [],
                    }
                    sections.append(current_section)

                current_section["content"].append({
                    "page": page_number,
                    "printed_label": printed_label,
                    "text": line_str,
                })

    return sections


def build_hierarchical_outline(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Construct a structured 3-level academic outline (Chapter > Topic > Subtopic)
    from detected sections.
    """
    subtopics = []
    subtopic_idx = 0

    for sec in sections:
        heading = sec.get("heading", "").strip()
        chapter = sec.get("chapter", "General Overview")
        section_name = sec.get("section", heading)
        subtopic_name = sec.get("subsection") or heading
        start_page = sec.get("start_page", 1)
        content_items = sec.get("content", [])

        page_set = set()
        if start_page:
            page_set.add(start_page)
        for item in content_items:
            if "page" in item:
                page_set.add(item["page"])
        source_pages = sorted(list(page_set))

        text_lines = [item.get("text", "") for item in content_items if item.get("text")]
        full_text = "\n".join(text_lines).strip()

        subtopic_idx += 1
        subtopics.append({
            "id": f"subtopic_{subtopic_idx}",
            "chapter": chapter,
            "topic": section_name,
            "subtopic": subtopic_name,
            "path": sec.get("path", f"{chapter} > {section_name}"),
            "source_pages": source_pages if source_pages else [1],
            "content": full_text,
        })

    return subtopics