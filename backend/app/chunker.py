"""
Chunker — Lumio Backend
========================

Splits structured sections into overlapping text windows ("chunks") that
are small enough for effective embedding and retrieval.

Each section's content lines are flattened into a word list, then a
sliding window of ``chunk_size`` words advances by ``chunk_size - overlap``
words on each step.  The overlap ensures that sentences near chunk
boundaries appear in at least two adjacent chunks, reducing the chance of
a retrieval miss when relevant context straddles a boundary.

Every chunk records:
- ``text`` (str): the reassembled text for embedding.
- ``section`` (str): the heading of the section it belongs to.
- ``source_pages`` (list[int]): deduplicated, order-preserving page
  numbers of the words in the chunk.
"""


# ---------------------------------------------------------------------------
# Main chunking function
# ---------------------------------------------------------------------------

def create_chunks(
    sections: list,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list:
    """
    Convert structured sections into overlapping text chunks.

    Parameters
    ----------
    sections : list[dict]
        Sections produced by ``detect_structure``.  Each must contain
        ``"heading"`` (str) and ``"content"`` (list of ``{"page", "text"}``
        dicts).
    chunk_size : int, optional
        Maximum number of words per chunk (default 500).
    overlap : int, optional
        Number of words shared between consecutive chunks (default 50).

    Returns
    -------
    list[dict]
        Chunks with ``"text"``, ``"section"``, and ``"source_pages"``.
    """
    chunks = []

    for section in sections:
        heading = section["heading"]

        # Flatten every content line into a list of (word, page_number) tuples.
        words = [
            (word, item["page"])
            for item in section["content"]
            for word in item["text"].split()
        ]

        start = 0

        while start < len(words):
            end = start + chunk_size
            chunk_words = words[start:end]

            # Deduplicate page numbers while preserving the order of appearance.
            source_pages = list(dict.fromkeys(page for _, page in chunk_words))

            chunks.append({
                "text": " ".join(word for word, _ in chunk_words),
                "section": heading,
                "source_pages": source_pages,
            })

            # Stop if this chunk reached the end of the section.
            if end >= len(words):
                break

            # Advance the window, keeping `overlap` words from the current chunk.
            start = end - overlap

    return chunks


# Chunk-level citations reflect the pages actually represented in each span.
