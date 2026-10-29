from app.ingestion.chunk import detect_headings_and_sections, chunk_sections, estimate_tokens

def test_derivation_integrity_under_1200_tokens():
    """
    Blueprint Invariant: Worked example or derivation under 1200 tokens is kept whole:
    exceeding the target is better than cutting a derivation in half.
    """
    deriv_text = (
        "Worked Derivation: Axial field of a dipole.\n"
        "Step 1: Compute field due to positive charge.\n"
        "Step 2: Compute field due to negative charge.\n"
        "Step 3: Vector difference.\n"
        "Result: E = 2p / (4 pi epsilon_0 r^3)."
    )
    pages_data = [{"page_num": 1, "text": deriv_text}]
    sections = detect_headings_and_sections(pages_data)
    assert len(sections) >= 1
    assert sections[0]["is_derivation"] is True

    chunks = chunk_sections(sections, target_tokens=700, max_tokens=1000)
    assert len(chunks) == 1  # Kept intact in a single chunk
    assert "Axial field" in chunks[0]["content"]

def test_token_estimator():
    text = "A" * 36
    tokens = estimate_tokens(text)
    assert tokens == 10
