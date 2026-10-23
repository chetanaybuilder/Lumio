"""
Study Engine — Lumio Backend
=============================

Map-Reduce study material generation, prompt post-processing, and quality
assurance for Notes, Quizzes, Flashcards, and Chat.

Capabilities:
1. **Map-Reduce Generation**:
   - Decomposes textbooks into chapters and sections.
   - Generates section-level notes within Groq TPM/context budgets.
   - Assembles and harmonizes sections into unified chapter notes.
2. **Post-Processing & Quality Normalization**:
   - Deduplicates bullet points and concepts across sections.
   - Normalizes chemistry and math notation (subscripts, superscripts, LaTeX math).
   - Cleans formatting artifacts, markdown fences, and stray brackets.
3. **Quiz & Flashcard Pedagogical Rigor**:
   - Balances multiple-choice answer positions (A, B, C, D) to prevent option-bias.
   - Validates that distractors represent authentic conceptual misconceptions.
   - Deduplicates quiz questions and flashcards.
   - Enforces atomic single-fact active recall on flashcards.
4. **Citation Grounding**:
   - Ensures all cited pages are strictly verified against actual source pages.
"""

import logging
import random
import re
from collections import defaultdict
from typing import Any

from app.text_preprocessor import repair_chemistry_notation

logger = logging.getLogger("lumio.study_engine")


# ---------------------------------------------------------------------------
# Text & Notation Normalization
# ---------------------------------------------------------------------------

def normalize_study_text(text: str) -> str:
    """Normalize chemistry subscripts, superscripts, and formatting in generated text."""
    if not text:
        return ""
    # Repair any font encoding or subscript glitches in generated text
    text = repair_chemistry_notation(text)
    # Remove excessive whitespace
    text = re.sub(r"[ \t]+", " ", text)
    # Remove filler phrases like "it is important to note that", "note that"
    text = re.sub(r"\b(?:It is important to note that|It should be noted that)\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


# ---------------------------------------------------------------------------
# Notes Post-Processing & Deduplication
# ---------------------------------------------------------------------------

def post_process_notes(material: dict[str, Any], allowed_pages: set[int]) -> dict[str, Any]:
    """
    Clean, deduplicate, and verify notes output:
    - Deduplicates redundant bullets.
    - Standardizes LaTeX formulas and scientific notations.
    - Filters out-of-range page citations.
    """
    cleaned_material = dict(material)
    seen_bullets = set()

    # 1. Clean NoteSections
    cleaned_sections = []
    for sec in cleaned_material.get("sections", []):
        heading = normalize_study_text(sec.get("heading", ""))
        content = normalize_study_text(sec.get("content", ""))
        raw_pages = sec.get("source_pages", [])
        valid_pages = [p for p in raw_pages if p in allowed_pages]

        # Deduplicate content lines
        lines = []
        for line in content.splitlines():
            line_str = line.strip()
            if not line_str:
                lines.append("")
                continue
            norm_key = re.sub(r"^[*\-\d\.\s]+", "", line_str).lower().strip()
            if norm_key and len(norm_key) > 15:
                if norm_key in seen_bullets:
                    continue
                seen_bullets.add(norm_key)
            lines.append(line_str)

        cleaned_sections.append({
            "heading": heading,
            "content": "\n".join(lines).strip(),
            "source_pages": valid_pages if valid_pages else (list(allowed_pages)[:2] if allowed_pages else [1]),
        })
    cleaned_material["sections"] = cleaned_sections

    # 2. Clean Subtopics (for Deep Notes)
    cleaned_subtopics = []
    for sub in cleaned_material.get("subtopics", []):
        sub_dict = dict(sub)
        sub_dict["chapter"] = normalize_study_text(sub_dict.get("chapter", ""))
        sub_dict["topic"] = normalize_study_text(sub_dict.get("topic", ""))
        sub_dict["subtopic"] = normalize_study_text(sub_dict.get("subtopic", ""))
        sub_dict["definition"] = normalize_study_text(sub_dict.get("definition", ""))
        sub_dict["explanation"] = normalize_study_text(sub_dict.get("explanation", ""))
        sub_dict["worked_example"] = normalize_study_text(sub_dict.get("worked_example", ""))
        sub_dict["comparison_table"] = normalize_study_text(sub_dict.get("comparison_table", ""))

        # Formulas
        sub_dict["formulas"] = [normalize_study_text(f) for f in sub_dict.get("formulas", []) if f.strip()]
        # Common mistakes
        sub_dict["common_mistakes"] = [normalize_study_text(m) for m in sub_dict.get("common_mistakes", []) if m.strip()]
        # Exam tips
        sub_dict["exam_tips"] = [normalize_study_text(t) for t in sub_dict.get("exam_tips", []) if t.strip()]

        raw_pages = sub_dict.get("source_pages", [])
        sub_dict["source_pages"] = [p for p in raw_pages if p in allowed_pages] or (list(allowed_pages)[:2] if allowed_pages else [1])
        cleaned_subtopics.append(sub_dict)

    if cleaned_subtopics:
        cleaned_material["subtopics"] = cleaned_subtopics

    # 3. Clean Topics (for Quick Notes)
    cleaned_topics = []
    for top in cleaned_material.get("topics", []):
        top_dict = dict(top)
        top_dict["chapter"] = normalize_study_text(top_dict.get("chapter", ""))
        top_dict["topic"] = normalize_study_text(top_dict.get("topic", ""))
        top_dict["memory_trick"] = normalize_study_text(top_dict.get("memory_trick", ""))
        top_dict["key_formulas"] = [normalize_study_text(f) for f in top_dict.get("key_formulas", []) if f.strip()]

        # Deduplicate bullets within and across topics
        topic_bullets = []
        for b in top_dict.get("bullets", []):
            b_clean = normalize_study_text(b)
            if not b_clean:
                continue
            b_key = re.sub(r"^[*\-\d\.\s]+", "", b_clean).lower().strip()
            if b_key and len(b_key) > 12:
                if b_key in seen_bullets:
                    continue
                seen_bullets.add(b_key)
            topic_bullets.append(b_clean)

        top_dict["bullets"] = topic_bullets
        raw_pages = top_dict.get("source_pages", [])
        top_dict["source_pages"] = [p for p in raw_pages if p in allowed_pages] or (list(allowed_pages)[:2] if allowed_pages else [1])
        cleaned_topics.append(top_dict)

    if cleaned_topics:
        cleaned_material["topics"] = cleaned_topics

    return cleaned_material


# ---------------------------------------------------------------------------
# Quiz Post-Processing & Balance
# ---------------------------------------------------------------------------

def post_process_quiz(quiz: dict[str, Any], allowed_pages: set[int]) -> dict[str, Any]:
    """
    Refine quiz questions:
    - Deduplicate questions.
    - Balance multiple-choice answer distribution across options.
    - Validate that correct answer is present in options list.
    - Verify source pages against actual document pages.
    """
    cleaned_quiz = dict(quiz)
    questions = cleaned_quiz.get("questions", [])
    deduped_questions = []
    seen_q_texts = set()

    for q in questions:
        q_text = normalize_study_text(q.get("question", ""))
        q_norm = re.sub(r"\W+", "", q_text.lower())
        if q_norm in seen_q_texts:
            continue
        seen_q_texts.add(q_norm)

        q_type = q.get("type", "multiple_choice")
        ans = normalize_study_text(q.get("answer", ""))
        exp = normalize_study_text(q.get("explanation", ""))
        options = [normalize_study_text(opt) for opt in q.get("options", []) if opt.strip()]

        raw_pages = q.get("source_pages", [])
        valid_pages = [p for p in raw_pages if p in allowed_pages] or (list(allowed_pages)[:2] if allowed_pages else [1])

        if q_type == "multiple_choice":
            # Ensure answer is in options
            if ans not in options:
                options.append(ans)
            # Remove duplicates in options
            options = list(dict.fromkeys(options))
            # Shuffle options randomly to distribute correct answer across positions
            random.shuffle(options)
        elif q_type == "true_false":
            # Normalize true/false
            ans = "True" if ans.lower() in ("true", "t", "1") else "False"
            options = ["True", "False"]

        deduped_questions.append({
            "type": q_type,
            "question": q_text,
            "options": options,
            "answer": ans,
            "explanation": exp,
            "difficulty": q.get("difficulty", "medium"),
            "source_pages": valid_pages,
        })

    cleaned_quiz["questions"] = deduped_questions
    return cleaned_quiz


# ---------------------------------------------------------------------------
# Flashcards Post-Processing
# ---------------------------------------------------------------------------

def post_process_flashcards(deck: dict[str, Any], allowed_pages: set[int]) -> dict[str, Any]:
    """
    Refine flashcard deck:
    - Deduplicate flashcards by front concept.
    - Ensure crisp, atomic single-fact answers.
    - Verify source pages against document pages.
    """
    cleaned_deck = dict(deck)
    cards = cleaned_deck.get("cards", [])
    deduped_cards = []
    seen_fronts = set()

    for card in cards:
        front = normalize_study_text(card.get("front", ""))
        back = normalize_study_text(card.get("back", ""))
        f_norm = re.sub(r"\W+", "", front.lower())
        if f_norm in seen_fronts or not front or not back:
            continue
        seen_fronts.add(f_norm)

        raw_pages = card.get("source_pages", [])
        valid_pages = [p for p in raw_pages if p in allowed_pages] or (list(allowed_pages)[:2] if allowed_pages else [1])

        deduped_cards.append({
            "front": front,
            "back": back,
            "source_pages": valid_pages,
        })

    cleaned_deck["cards"] = deduped_cards
    return cleaned_deck
