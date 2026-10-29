from app.ingestion.clean import (
    clean_extracted_text,
    convert_super_subscripts,
    convert_operators_and_greek,
    detect_chemistry_formulas,
    escape_currency
)

def test_rule_1_unicode_and_hyphenation():
    raw = "elec-\ntrostatics and soft\xadhyphen"
    cleaned = clean_extracted_text(raw)
    assert "electrostatics" in cleaned
    assert "\xad" not in cleaned

def test_rule_2_superscripts_and_subscripts():
    raw = "x² + y³ = r² and H₂O with 10⁻⁶"
    cleaned = convert_super_subscripts(raw)
    assert "x^{2}" in cleaned
    assert "y^{3}" in cleaned
    assert "H_{2}O" in cleaned
    assert "10^{-6}" in cleaned

def test_rule_3_operators_and_greek():
    raw = "a × b ÷ c ± d ≤ e ≥ f ≠ g ≈ h ∞ α + β = γ"
    cleaned = convert_operators_and_greek(raw)
    assert r"\times" in cleaned
    assert r"\div" in cleaned
    assert r"\pm" in cleaned
    assert r"\leq" in cleaned
    assert r"\geq" in cleaned
    assert r"\neq" in cleaned
    assert r"\approx" in cleaned
    assert r"\infty" in cleaned
    assert r"\alpha" in cleaned
    assert r"\beta" in cleaned
    assert r"\gamma" in cleaned

def test_rule_4_chemistry_detection():
    raw = "2H2 + O2 -> 2H2O"
    cleaned = detect_chemistry_formulas(raw)
    assert r"\ce{" in cleaned

def test_rule_6_escape_currency():
    raw = "The cost is Rs. $500 or ₹ $1000."
    cleaned = escape_currency(raw)
    assert r"\$" in cleaned

def test_rule_7_preserve_markdown_tables():
    raw = (
        "| Head 1 | Head 2 |\n"
        "| :--- | :--- |\n"
        "| Value 1 | Value 2 |\n"
    )
    cleaned = clean_extracted_text(raw)
    assert "| Head 1 | Head 2 |" in cleaned
    assert "| Value 1 | Value 2 |" in cleaned
