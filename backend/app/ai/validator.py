from typing import List, Tuple, Any, Dict
from app.ai.schemas import GeneratedQuestion, GeneratedPaper, SectionNotes, EvaluationResult
from app.math.validator import validate_math_text

class BusinessValidationError(Exception):
    def __init__(self, message: str, errors: List[str] = None):
        self.message = message
        self.errors = errors or [message]
        super().__init__(message)

def validate_section_notes_business(notes: SectionNotes) -> Tuple[bool, List[str]]:
    """Validates SectionNotes business constraints and math integrity."""
    errors = []
    
    # Invariant: Derivations must have at least 3 steps
    for d in notes.derivations:
        if len(d.steps) < 3:
            errors.append(f"Derivation '{d.title}' has {len(d.steps)} steps; at least 3 steps required.")
            
        # Math gate check on steps
        for idx, step in enumerate(d.steps):
            if "$" in step or "\\ce{" in step:
                ok, errs, _ = validate_math_text(step)
                if not ok:
                    errors.append(f"Math syntax error in derivation '{d.title}' step {idx+1}: {'; '.join(errs)}")

    # Check formulae
    for f in notes.formulae:
        if "$" in f.latex or "\\" in f.latex:
            ok, errs, _ = validate_math_text(f"${f.latex}$")
            if not ok:
                errors.append(f"Math syntax error in formula '{f.formula_name}': {'; '.join(errs)}")

    return len(errors) == 0, errors

def validate_question_business(q: GeneratedQuestion) -> Tuple[bool, List[str]]:
    """Validates question constraints: MCQ option count, marking scheme marks sum, math integrity."""
    errors = []
    
    # MCQ option count
    if q.q_type in ("mcq", "assertion_reason"):
        if not q.options or len(q.options) != 4:
            errors.append(f"Question {q.q_no} ({q.q_type}) must have exactly 4 options; got {len(q.options) if q.options else 0}.")

    # Marking scheme sum
    step_sum = sum(s.marks for s in q.marking_scheme.steps)
    if abs(step_sum - q.marks) > 0.05:
        errors.append(f"Question {q.q_no} step marks sum ({step_sum}) does not match question marks ({q.marks}).")

    # Math gate check
    for field_name, text_val in [("question_md", q.question_md), ("answer_md", q.answer_md)]:
        if "$" in text_val or "\\ce{" in text_val:
            ok, errs, _ = validate_math_text(text_val)
            if not ok:
                errors.append(f"Math syntax error in {field_name} (Q{q.q_no}): {'; '.join(errs)}")

    return len(errors) == 0, errors

def validate_evaluation_business(ev: EvaluationResult) -> Tuple[bool, List[str]]:
    """Validates that each awarded mark is <= max, and the sum equals awarded_total."""
    errors = []
    step_awarded_sum = sum(s.awarded for s in ev.steps)
    step_max_sum = sum(s.max for s in ev.steps)

    for idx, s in enumerate(ev.steps):
        if s.awarded < 0:
            errors.append(f"Step {idx+1} awarded marks cannot be negative ({s.awarded}).")
        if s.awarded > s.max:
            errors.append(f"Step {idx+1} awarded ({s.awarded}) exceeds step max ({s.max}).")

    if abs(step_awarded_sum - ev.awarded_total) > 0.05:
        errors.append(f"Sum of step awarded marks ({step_awarded_sum}) does not match awarded_total ({ev.awarded_total}).")

    if abs(step_max_sum - ev.max_total) > 0.05:
        errors.append(f"Sum of step max marks ({step_max_sum}) does not match max_total ({ev.max_total}).")

    return len(errors) == 0, errors
