from app.chunker import create_chunks
from app.structure_detector import detect_structure
from app.text_preprocessor import clean_pages, clean_text


def test_clean_text_preserves_content_and_normalizes_layout():
    assert clean_text("Photosynthesis   uses light." + "\n" * 3 + "It stores energy.") == (
        "Photosynthesis uses light.\n\nIt stores energy."
    )


def test_sections_and_chunks_keep_local_page_references():
    sections = detect_structure([
        {"page": 1, "text": "Chapter 1: Energy\nCells transform energy."},
        {"page": 2, "text": "This process stores chemical energy."},
    ])
    chunks = create_chunks(sections, chunk_size=3, overlap=1)
    assert chunks
    assert chunks[0]["source_pages"] == [1]
    assert chunks[1]["source_pages"] == [1, 2]


def test_clean_pages_handles_empty_text():
    assert clean_pages([{"page": 1, "text": "  "}]) == [{"page": 1, "text": ""}]


# Isolate deterministic processing checks from external infrastructure.