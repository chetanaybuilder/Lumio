"""
Evaluation Runner — Lumio
=========================
Measures retrieval metrics (Hit@1, Hit@5, MRR) and extraction fidelity
on the sample textbook Chemistry_Textbook_CBSE.pdf.

Usage:
    python evals/eval_retrieval.py [--baseline]
"""

import sys
import time
from pathlib import Path

# Add project root and backend to python path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.pdf_extractor import extract_text_from_pdf
from app.text_preprocessor import clean_pages
from app.structure_detector import detect_structure
from app.chunker import create_chunks
from app.embedding_generator import generate_embeddings, generate_embedding
from app.vector_store import clear_all_chunks, store_chunks, query_chunks

from evals.dataset import EXTRACTION_SPOT_CHECKS, RETRIEVAL_QUESTIONS



def run_extraction_eval(pdf_path: str) -> dict:
    """Evaluate extraction completeness and fidelity on 10 spot-check pages."""
    raw_pages = extract_text_from_pdf(pdf_path)
    pages_dict = {p["page"]: p["text"] for p in raw_pages}

    total_checks = 0
    passed_checks = 0
    spot_results = []

    for item in EXTRACTION_SPOT_CHECKS:
        target_page = item["page"]
        text = pages_dict.get(target_page, "")
        matched = []
        missing = []
        for snippet in item["required_snippets"]:
            total_checks += 1
            if snippet.lower() in text.lower():
                passed_checks += 1
                matched.append(snippet)
            else:
                missing.append(snippet)

        spot_results.append({
            "page": target_page,
            "title": item["title"],
            "matched": len(matched),
            "total": len(item["required_snippets"]),
            "missing": missing,
        })

    fidelity = passed_checks / max(1, total_checks)
    return {
        "page_count": len(raw_pages),
        "fidelity": fidelity,
        "passed": passed_checks,
        "total": total_checks,
        "details": spot_results,
    }


def run_retrieval_eval(pdf_path: str) -> dict:
    """Ingest textbook and evaluate Hit@1, Hit@5, and MRR across 42 questions."""
    clear_all_chunks()

    session_id = "eval_session"
    document_id = "eval_chemistry_doc"

    t0 = time.time()
    pages = extract_text_from_pdf(pdf_path)
    cleaned = clean_pages(pages)
    sections = detect_structure(cleaned)
    chunks = create_chunks(sections)
    embeddings = generate_embeddings([c["text"] for c in chunks])
    store_chunks(document_id, chunks, embeddings, session_id)
    indexing_time = time.time() - t0

    hit1_count = 0
    hit5_count = 0
    rr_total = 0.0

    query_details = []

    for q in RETRIEVAL_QUESTIONS:
        q_text = q["question"]
        expected = set(q["expected_pages"])

        q_vec = generate_embedding(q_text, task_type="RETRIEVAL_QUERY")
        results = query_chunks(
            session_id=session_id,
            document_id=document_id,
            embedding=q_vec,
            limit=5,
            query_text=q_text,
        )

        # Map top-5 results to retrieved source pages
        retrieved_ranks = []
        for idx, res in enumerate(results, start=1):
            raw_pages = res["metadata"].get("source_pages", "")
            pages_list = [int(p) for p in str(raw_pages).split(",") if p.strip().isdigit()]
            if any(p in expected for p in pages_list):
                retrieved_ranks.append(idx)

        first_rank = retrieved_ranks[0] if retrieved_ranks else None

        if first_rank == 1:
            hit1_count += 1
        if first_rank and first_rank <= 5:
            hit5_count += 1

        reciprocal_rank = (1.0 / first_rank) if first_rank else 0.0
        rr_total += reciprocal_rank

        query_details.append({
            "id": q["id"],
            "question": q_text,
            "expected": list(expected),
            "first_rank": first_rank,
            "rr": reciprocal_rank,
        })

    total_q = len(RETRIEVAL_QUESTIONS)
    hit1 = hit1_count / total_q
    hit5 = hit5_count / total_q
    mrr = rr_total / total_q

    clear_all_chunks()

    return {
        "total_queries": total_q,
        "hit@1": hit1,
        "hit@5": hit5,
        "mrr": mrr,
        "indexing_time_sec": round(indexing_time, 2),
        "chunk_count": len(chunks),
        "details": query_details,
    }


def main():
    pdf_path = str(ROOT / "Chemistry_Textbook_CBSE.pdf")
    if not Path(pdf_path).exists():
        print(f"Error: {pdf_path} not found.")
        sys.exit(1)

    print("=" * 60)
    print("RUNNING LUMIO QUALITY EVALUATION HARNESS")
    print(f"Dataset: {pdf_path}")
    print("=" * 60)

    # 1. Extraction Evaluation
    ext_results = run_extraction_eval(pdf_path)
    print(f"\n[EXTRACTION FIDELITY]")
    print(f"Pages: {ext_results['page_count']}")
    print(f"Fidelity Score: {ext_results['fidelity'] * 100:.2f}% ({ext_results['passed']}/{ext_results['total']} snippets matched)")

    # 2. Retrieval Evaluation
    ret_results = run_retrieval_eval(pdf_path)
    print(f"\n[RETRIEVAL METRICS]")
    print(f"Total Chunks: {ret_results['chunk_count']}")
    print(f"Hit@1:  {ret_results['hit@1'] * 100:.2f}%")
    print(f"Hit@5:  {ret_results['hit@5'] * 100:.2f}%  (Target: >= 92.00%)")
    print(f"MRR:    {ret_results['mrr']:.4f}       (Target: >= 0.7500)")
    print(f"Index Time: {ret_results['indexing_time_sec']}s")
    print("\nNon-Hit@1 Queries:")
    for d in ret_results['details']:
        if d['first_rank'] != 1:
            print(f"  Rank {d['first_rank']}: [{d['id']}] Expected {d['expected']} -> {d['question']}")
    print("=" * 60)

    return ext_results, ret_results


if __name__ == "__main__":
    main()
