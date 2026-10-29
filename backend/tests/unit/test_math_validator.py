import json
from pathlib import Path
from app.math.validator import validate_math_text, validate_expressions_batch

def test_math_validator_on_corpus():
    corpus_path = Path("fixtures/math_corpus.json")
    assert corpus_path.exists(), "fixtures/math_corpus.json must exist"

    with open(corpus_path, encoding="utf-8") as f:
        data = json.load(f)

    expressions = [item["latex"] for item in data["corpus"]]
    assert len(expressions) >= 150, "Corpus must hold at least 150 expressions"

    results = validate_expressions_batch(expressions)
    valid_count = sum(1 for r in results if r["valid"])
    assert valid_count == len(expressions), f"Expected 100% valid, got {valid_count}/{len(expressions)}"

def test_markdown_math_validator():
    valid_md = "Let $E = mc^2$ and $$\\int_0^1 x\\,dx = \\frac{1}{2}$$."
    ok, errs, count = validate_math_text(valid_md)
    assert ok is True
    assert count == 2
    assert len(errs) == 0

    invalid_md = "Unclosed bracket $\\frac{a}{b$."
    ok_inv, errs_inv, count_inv = validate_math_text(invalid_md)
    assert ok_inv is False
    assert len(errs_inv) > 0
