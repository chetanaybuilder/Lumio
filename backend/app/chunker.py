"""
Chunker — Lumio Backend
========================

Splits structured sections into overlapping text windows ("chunks") that
are optimal for vector embedding and context retrieval.

Enhancements:
1. Heading and Section preservation: Every chunk retains its chapter/section context.
2. Diagram & Table preservation: Chunks containing diagram markers
   (``[FIGURE / DIAGRAM: ...]``) or markdown tables (``| --- |``) are flagged
   with metadata so retrieval algorithms can prioritize visual elements when
   students ask about figures or tables.
3. Sentence/Boundary awareness: Avoids creating empty chunks and preserves
   multi-page citations across chunk boundaries.
"""

from typing import Any


def create_chunks(
    sections: list[dict[str, Any]],
    chunk_size: int = 500,
    overlap: int = 60,
) -> list[dict[str, Any]]:
    """
    Convert structured sections into overlapping text chunks with rich metadata.

    Parameters
    ----------
    sections : list[dict]
        Sections produced by ``detect_structure``. Each must contain
        ``"heading"`` (str) and ``"content"`` (list of ``{"page", "text"}`` dicts).
    chunk_size : int, optional
        Maximum number of words per chunk (default 500).
    overlap : int, optional
        Number of words shared between consecutive chunks (default 60).

    Returns
    -------
    list[dict]
        Chunks with ``"text"``, ``"section"``, ``"source_pages"``, ``"has_diagram"``,
        and ``"has_table"``.
    """
    chunks = []

    for section in sections:
        heading = section.get("heading", "Document Content")
        content_items = section.get("content", [])

        if not content_items:
            continue

        # Flatten section lines into a list of (word, page_number) tuples
        words = [
            (word, item["page"])
            for item in content_items
            for word in item["text"].split()
            if word
        ]

        if not words:
            continue

        start = 0

        while start < len(words):
            end = start + chunk_size
            chunk_words = words[start:end]

            # Deduplicate source page numbers while preserving chronological order
            source_pages = list(dict.fromkeys(page for _, page in chunk_words))
            chunk_text = " ".join(word for word, _ in chunk_words).strip()

            if not chunk_text:
                break

            has_diagram = (
                "[FIGURE / DIAGRAM:" in chunk_text
                or "[VISUAL ELEMENTS" in chunk_text
                or "Fig." in chunk_text
                or "Figure " in chunk_text
            )
            has_table = "| --- |" in chunk_text or "[STRUCTURED TABLES" in chunk_text

            chunks.append({
                "text": chunk_text,
                "section": heading,
                "source_pages": source_pages,
                "has_diagram": has_diagram,
                "has_table": has_table,
            })

            # If we reached the end of the section, stop chunking this section
            if end >= len(words):
                break

            # Slide window forward by (chunk_size - overlap)
            start = end - overlap

    return chunks
