"""
Processing Tests — Lumio Backend
==================================

Deterministic unit tests for the text-processing and RAG pipeline:
- ``text_preprocessor`` — whitespace normalization, degree symbols, scientific encoding.
- ``structure_detector`` — heading detection, diagram/table markers, and section grouping.
- ``chunker``            — overlapping chunk creation with page tracking and visual metadata.
- ``vector_store``       — hybrid keyword & diagram reranking.
- ``pdf_extractor``      — error handling and scanned PDF detection.
"""

import pymupdf
import pytest
from app.chunker import create_chunks
from app.embedding_generator import EMBEDDING_DIMENSIONS
from app.pdf_extractor import (
    PDFCorruptedError,
    PDFScannedError,
    extract_text_from_pdf,
)
from app.structure_detector import detect_structure
from app.text_preprocessor import clean_pages, clean_text
from app.vector_store import clear_all_chunks, query_chunks, store_chunks

# ---------------------------------------------------------------------------
# Text cleaning and scientific symbol normalization
# ---------------------------------------------------------------------------

def test_clean_text_preserves_content_and_normalizes_layout():
    """Verify that clean_text collapses excess whitespace while preserving paragraphs."""
    assert clean_text("Photosynthesis   uses light." + "\n" * 3 + "It stores energy.") == (
        "Photosynthesis uses light.\n\nIt stores energy."
    )


def test_clean_text_normalizes_scientific_symbols_and_encoding():
    """Verify normalization of degree signs, superscripts, smart quotes, and dashes."""
    raw = "Bond angle is 109.5\ufffd for sp\ufffd hybrid orbitals in \u2018methane\u2019."
    cleaned = clean_text(raw)
    assert "109.5°" in cleaned
    assert "sp²" in cleaned
    assert "'methane'" in cleaned


# ---------------------------------------------------------------------------
# Structure detection and chunking
# ---------------------------------------------------------------------------

def test_sections_and_chunks_keep_local_page_references():
    """Each chunk's source_pages must reflect the actual pages represented in that chunk."""
    sections = detect_structure([
        {"page": 1, "text": "Chapter 1: Energy\nCells transform energy."},
        {"page": 2, "text": "This process stores chemical energy."},
    ])
    chunks = create_chunks(sections, chunk_size=3, overlap=1)
    assert chunks
    assert chunks[0]["source_pages"] == [1]
    assert chunks[1]["source_pages"] == [1, 2]


def test_structure_detector_recognizes_diagrams_tables_and_landmarks():
    """Structure detector must recognize diagram markers, tables, and textbook headings."""
    pages = [
        {
            "page": 1,
            "text": "Chapter 1: Atomic Structure\nAtoms consist of protons, neutrons, and electrons.",
        },
        {
            "page": 2,
            "text": "[FIGURE / DIAGRAM: Figure 1.2: Cathode Ray Tube Setup]\nThe cathode ray experiment proved electrons have negative charge.",
        },
        {
            "page": 3,
            "text": "KEY CONCEPTS\nElectrons occupy quantized orbitals.\n| Subshell | Capacity |\n| --- | --- |\n| s | 2 |",
        },
    ]
    sections = detect_structure(pages)
    headings = [s["heading"] for s in sections]
    assert any("Chapter 1" in h for h in headings)
    assert any("[FIGURE / DIAGRAM:" in h for h in headings)
    assert any("KEY CONCEPTS" in h for h in headings)


def test_chunker_flags_diagrams_and_tables():
    """Chunks with diagrams or tables must have metadata flags for RAG reranking."""
    sections = [
        {
            "heading": "Cathode Ray Analysis",
            "content": [
                {"page": 2, "text": "[FIGURE / DIAGRAM: Figure 1.2 Cathode Ray Tube with high voltage]"},
                {"page": 2, "text": "Electrons travel from cathode to anode."},
            ],
        },
        {
            "heading": "Electron Orbitals",
            "content": [
                {"page": 3, "text": "| Orbit | Max e |"},
                {"page": 3, "text": "| --- | --- |"},
                {"page": 3, "text": "| 1 | 2 |"},
            ],
        },
    ]
    chunks = create_chunks(sections, chunk_size=50, overlap=5)
    assert len(chunks) == 2
    assert chunks[0]["has_diagram"] is True
    assert chunks[1]["has_table"] is True


# ---------------------------------------------------------------------------
# Hybrid vector retrieval with diagram bonus
# ---------------------------------------------------------------------------

def test_hybrid_vector_retrieval_diagram_bonus():
    """Querying about diagrams should prioritize chunks marked with diagram content."""
    clear_all_chunks()
    dummy_vec = [0.1] * EMBEDDING_DIMENSIONS
    chunks = [
        {"text": "General introductory text without any visuals.", "section": "Intro", "source_pages": [1], "has_diagram": False, "has_table": False},
        {"text": "[FIGURE / DIAGRAM: Figure 2.1 Aufbau Principle Energy Diagram showing 1s, 2s, 2p orbitals]", "section": "Energy Diagram", "source_pages": [2], "has_diagram": True, "has_table": False},
    ]
    store_chunks("doc_diag_test", chunks, [dummy_vec, dummy_vec], "session_diag_test")

    # When query specifically mentions diagram, the diagram chunk should rank first
    results = query_chunks(
        session_id="session_diag_test",
        document_id="doc_diag_test",
        embedding=dummy_vec,
        limit=2,
        query_text="Explain the Aufbau principle energy diagram",
    )
    assert len(results) == 2
    assert "[FIGURE / DIAGRAM:" in results[0]["text"]
    clear_all_chunks()


# ---------------------------------------------------------------------------
# PDF extraction error handling and edge cases
# ---------------------------------------------------------------------------

def test_clean_pages_handles_empty_text():
    """Whitespace-only pages should be cleaned to empty strings."""
    assert clean_pages([{"page": 1, "text": "  "}]) == [{"page": 1, "text": ""}]


def test_pdf_extractor_handles_missing_file():
    """Non-existent file must raise PDFCorruptedError."""
    with pytest.raises(PDFCorruptedError):
        extract_text_from_pdf("non_existent_file_12345.pdf")


def test_pdf_extractor_scanned_pdf_detection(tmp_path):
    """PDF with scanned images and zero text must raise PDFScannedError."""
    scanned_pdf = tmp_path / "scanned_doc.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=800)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 50, 50), 1)
    page.insert_image(pymupdf.Rect(50, 50, 200, 200), pixmap=pix)
    doc.save(str(scanned_pdf))
    doc.close()

    with pytest.raises(PDFScannedError) as exc_info:
        extract_text_from_pdf(str(scanned_pdf))
    assert "scanned" in str(exc_info.value).lower()