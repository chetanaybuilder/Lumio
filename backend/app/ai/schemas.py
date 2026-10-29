from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# Deep Notes Schemas
class DefinitionItem(BaseModel):
    term: str
    definition: str
    source_chunk_ids: List[str] = Field(default_factory=list)

class LawStatementItem(BaseModel):
    law_name: str
    statement: str
    mathematical_form: Optional[str] = None
    source_chunk_ids: List[str] = Field(default_factory=list)

class DerivationItem(BaseModel):
    title: str
    given: str
    steps: List[str] = Field(description="Sequential derivation steps with justification. Must have at least 3 steps.")
    result: str
    source_chunk_ids: List[str] = Field(default_factory=list)

class ReactionItem(BaseModel):
    reaction_name: str
    reactants: str
    conditions: str
    steps: List[str] = Field(default_factory=list)
    products: str

class FormulaItem(BaseModel):
    formula_name: str
    latex: str
    symbol_meanings: Dict[str, str] = Field(default_factory=dict)
    si_unit: str

class WorkedExampleItem(BaseModel):
    question: str
    solution_steps: List[str] = Field(default_factory=list)
    final_answer: str

class SectionNotes(BaseModel):
    section_title: str
    overview: str
    definitions: List[DefinitionItem] = Field(default_factory=list)
    laws_and_statements: List[LawStatementItem] = Field(default_factory=list)
    derivations: List[DerivationItem] = Field(default_factory=list)
    reaction_mechanisms: List[ReactionItem] = Field(default_factory=list)
    formulae: List[FormulaItem] = Field(default_factory=list)
    worked_examples: List[WorkedExampleItem] = Field(default_factory=list)
    exam_tips: List[str] = Field(default_factory=list)
    common_errors: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)

# Flashcard Schemas
class GeneratedCard(BaseModel):
    card_type: str = Field(description="definition, law, formula, reaction, difference, why")
    front: str
    back: str
    tags: List[str] = Field(default_factory=list)
    source_chunk_id: Optional[str] = None

class FlashcardsList(BaseModel):
    cards: List[GeneratedCard]

# Quiz & CBSE Paper Schemas
class MarkingStep(BaseModel):
    step_description: str
    marks: float

class MarkingScheme(BaseModel):
    steps: List[MarkingStep]
    total_marks: float

class GeneratedQuestion(BaseModel):
    q_no: int
    section: str = Field(description="A, B, C, D, or E")
    q_type: str = Field(description="mcq, assertion_reason, vsa, sa, la, case_based")
    marks: float
    question_md: str
    options: Optional[List[str]] = None
    answer_md: str
    marking_scheme: MarkingScheme
    difficulty: str = Field(default="medium", description="easy, medium, hard")
    competency_tested: Optional[str] = None
    source_chunk_ids: List[str] = Field(default_factory=list)

class GeneratedPaper(BaseModel):
    subject: str
    class_level: int
    total_marks: float
    sections: List[str]
    questions: List[GeneratedQuestion]

# Evaluation Schemas
class StepEvaluation(BaseModel):
    expected_step: str
    awarded: float
    max: float
    matched_evidence: Optional[str] = None
    missing_or_wrong: Optional[str] = None

class EvaluationResult(BaseModel):
    awarded_total: float
    max_total: float
    steps: List[StepEvaluation]
    feedback_md: str
    model_answer_md: str
    how_to_gain_marks: List[str] = Field(default_factory=list)
    identified_mistake_category: Optional[str] = Field(
        default=None,
        description="concept_gap, formula_recall, calculation_error, unit_error, misread_question, incomplete_steps, diagram_error"
    )

# Micro-Drill Schemas
class DrillQuestion(BaseModel):
    q_no: int
    question_md: str
    options: Optional[List[str]] = None
    answer_md: str
    explanation_md: str

class DrillSpec(BaseModel):
    mistake_category: str
    concept_summary: str
    questions: List[DrillQuestion]

# Coverage Verification Schema
class TopicVerification(BaseModel):
    topic_title: str
    covered: bool
    evidence_quote: Optional[str] = None
    gaps_description: Optional[str] = None

class CoverageBatchResult(BaseModel):
    verifications: List[TopicVerification]
