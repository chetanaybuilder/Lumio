"""
Processing Tests — Lumio Backend
==================================

Deterministic unit tests for the text-processing pipeline.  These tests
run entirely offline — no external LLM calls, no remote APIs, no file I/O — so
they execute instantly and can be trusted in CI without secrets.

Covered modules:
- ``text_preprocessor`` — whitespace normalization.
- ``structure_detector`` — heading detection and section grouping.
- ``chunker``            — overlapping chunk creation with page tracking.
"""

from app.chunker import create_chunks
from app.structure_detector import detect_structure
from app.text_preprocessor import clean_pages, clean_text


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

def test_clean_text_preserves_content_and_normalizes_layout():
    """
    Verify that ``clean_text`` collapses excess whitespace and blank
    lines while keeping the original words and paragraph breaks.
    """
    assert clean_text("Photosynthesis   uses light." + "\n" * 3 + "It stores energy.") == (
        "Photosynthesis uses light.\n\nIt stores energy."
    )


# ---------------------------------------------------------------------------
# Structure detection and chunking
# ---------------------------------------------------------------------------

def test_sections_and_chunks_keep_local_page_references():
    """
    After structure detection and chunking, each chunk's ``source_pages``
    must reflect the actual pages whose words appear in that chunk.
    """
    sections = detect_structure([
        {"page": 1, "text": "Chapter 1: Energy\nCells transform energy."},
        {"page": 2, "text": "This process stores chemical energy."},
    ])
    # Use a small chunk size so the test exercises page-boundary behavior.
    chunks = create_chunks(sections, chunk_size=3, overlap=1)
    assert chunks
    assert chunks[0]["source_pages"] == [1]
    assert chunks[1]["source_pages"] == [1, 2]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_clean_pages_handles_empty_text():
    """Whitespace-only pages should be cleaned to empty strings."""
    assert clean_pages([{"page": 1, "text": "  "}]) == [{"page": 1, "text": ""}]


# Isolate deterministic processing checks from external infrastructure.