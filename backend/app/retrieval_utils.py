"""
Retrieval Utilities — Lumio Backend
====================================

Helpers for conversational query reformulation, context expansion,
and citation entailment/grounding verification.
"""

import re
from typing import Any

# Common English stopwords to ignore during citation span verification
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
    "by", "from", "is", "are", "was", "were", "be", "been", "being", "have", "has",
    "had", "do", "does", "did", "can", "could", "will", "would", "shall", "should",
    "may", "might", "must", "it", "its", "this", "that", "these", "those", "they",
    "them", "their", "we", "us", "our", "you", "your", "he", "him", "his", "she",
    "her", "as", "if", "than", "then", "so", "such", "no", "not", "only", "own",
    "same", "too", "very", "also", "into", "which", "what", "where", "when", "how",
}


def rewrite_query_with_history(question: str, history: list[dict[str, str]]) -> str:
    """
    Reformulate conversational follow-up questions (e.g. 'What is its formula?',
    'Give an example of it') into standalone self-contained search queries
    using recent conversation history.
    """
    if not history:
        return question

    q_lower = question.lower().strip()
    pronouns = {"it", "its", "this", "that", "these", "those", "they", "them", "their", "such", "the above", "itself"}
    words = set(re.findall(r"\b[a-z]+\b", q_lower))

    # If the question contains pronouns or is very short (< 5 words), reformulate with prior subject
    needs_rewrite = bool(words.intersection(pronouns)) or len(q_lower.split()) <= 4

    if not needs_rewrite:
        return question

    # Extract focal noun phrase / subject from the last user question or assistant response
    last_user_turn = ""
    for turn in reversed(history):
        if turn.get("role") == "student":
            last_user_turn = turn.get("content", "")
            break

    if not last_user_turn:
        return question

    # Extract prominent technical keywords (length >= 4, non-stopword)
    prior_keywords = [
        w for w in re.findall(r"\b[A-Za-z0-9_\-\.\u0370-\u03ff]+\b", last_user_turn)
        if w.lower() not in _STOPWORDS and len(w) >= 3
    ]

    if prior_keywords:
        context_anchor = " ".join(prior_keywords[:4])
        # Formulate standalone query
        return f"{context_anchor} {question}"

    return question


def verify_citations(
    answer: str,
    cited_pages: list[int],
    retrieved_chunks: list[dict[str, Any]],
    min_keyword_overlap: int = 2,
) -> list[int]:
    """
    Verify that each page cited by the LLM is genuinely supported by retrieved chunk content.
    Prevents hallucinated page references that happen to be within document range.

    Parameters
    ----------
    answer : str
        The generated answer text from the LLM.
    cited_pages : list[int]
        The list of page numbers claimed in LLM output.
    retrieved_chunks : list[dict]
        The chunks retrieved for this question.
    min_keyword_overlap : int
        Minimum matching substantive words required between answer and chunk.

    Returns
    -------
    list[int]
        Filtered list of verified page numbers supported by evidence.
    """
    if not cited_pages or not retrieved_chunks:
        return []

    # Map page -> combined text of retrieved chunks for that page
    page_to_chunk_texts: dict[int, list[str]] = {}
    for chunk in retrieved_chunks:
        meta = chunk.get("metadata", {})
        raw_pages = meta.get("source_pages", "")
        pages_in_chunk = []
        if isinstance(raw_pages, list):
            pages_in_chunk = [int(p) for p in raw_pages if str(p).isdigit()]
        elif isinstance(raw_pages, str):
            pages_in_chunk = [int(p) for p in raw_pages.split(",") if p.strip().isdigit()]

        text = chunk.get("text", "")
        for p in pages_in_chunk:
            page_to_chunk_texts.setdefault(p, []).append(text)

    # Extract substantive answer terms (alphanumerics, chemical symbols, numbers)
    answer_terms = set(
        w.lower() for w in re.findall(r"\b[A-Za-z0-9_\-\.\u0370-\u03ff\u2070-\u209f]+\b", answer)
        if w.lower() not in _STOPWORDS and len(w) >= 3
    )

    verified = []
    for page in cited_pages:
        chunk_texts = page_to_chunk_texts.get(page)
        if not chunk_texts:
            # Page was not even in the retrieved chunks
            continue

        combined_chunk_text = " ".join(chunk_texts).lower()
        chunk_terms = set(
            w.lower() for w in re.findall(r"\b[A-Za-z0-9_\-\.\u0370-\u03ff\u2070-\u209f]+\b", combined_chunk_text)
            if w.lower() not in _STOPWORDS and len(w) >= 3
        )

        overlap = answer_terms.intersection(chunk_terms)

        # Check if any distinctive term matches (e.g. chemical formula, formula name, or multiple terms)
        has_formula_or_number = any(re.search(r"\d", term) for term in overlap)
        if len(overlap) >= min_keyword_overlap or has_formula_or_number:
            verified.append(page)

    return sorted(list(dict.fromkeys(verified)))
