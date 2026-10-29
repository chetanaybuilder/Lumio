import asyncio
import json
import logging
import random
import uuid
from typing import Type, TypeVar, Optional, Any, Dict, AsyncGenerator
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.config import settings
from app.ai.validator import BusinessValidationError
from app.ai.schemas import (
    SectionNotes, FlashcardsList, GeneratedPaper, EvaluationResult, DrillSpec, CoverageBatchResult
)

logger = logging.getLogger("vexovault.ai")

T = TypeVar("T", bound=BaseModel)

class AIOutputError(Exception):
    def __init__(self, message: str, retry_hint: str = "Please try again with a more specific scope"):
        self.message = message
        self.retry_hint = retry_hint
        super().__init__(message)

class GeminiClient:
    def __init__(self):
        self.model_name = settings.GEMINI_MODEL
        self.api_key = settings.GEMINI_API_KEY
        self.worker_semaphore = asyncio.Semaphore(4)  # Max 4 concurrent calls per worker
        self._user_semaphores: Dict[str, asyncio.Semaphore] = {}
        
        if self.api_key:
            try:
                from google import genai
                self.sdk_client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize google-genai client: {e}")
                self.sdk_client = None
        else:
            self.sdk_client = None

    def _get_user_semaphore(self, user_id: str) -> asyncio.Semaphore:
        if user_id not in self._user_semaphores:
            self._user_semaphores[user_id] = asyncio.Semaphore(2)  # Max 2 concurrent calls per user
        return self._user_semaphores[user_id]

    async def generate_structured(
        self,
        schema: Type[T],
        system_instruction: str,
        contents: str,
        temperature: float = 0.2,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        max_repairs: int = 2
    ) -> T:
        """
        Calls Gemini in JSON mode with Pydantic schema validation.
        Performs up to max_repairs retries including exact validation errors.
        Enforces concurrency caps and 90s timeout.
        """
        req_id = request_id or str(uuid.uuid4())
        u_sem = self._get_user_semaphore(user_id or "global")

        async with self.worker_semaphore, u_sem:
            if not self.sdk_client:
                # Deterministic fallback for offline testing
                return self._generate_mock_structured(schema, contents)

            current_prompt = contents
            last_error = None

            for attempt in range(max_repairs + 1):
                try:
                    raw_text, in_tok, out_tok = await self._call_gemini_api(
                        system_instruction=system_instruction,
                        contents=current_prompt,
                        temperature=temperature,
                        response_schema=schema,
                        request_id=req_id
                    )

                    # Parse into Pydantic schema
                    parsed = schema.model_validate_json(raw_text)
                    return parsed
                except Exception as e:
                    last_error = str(e)
                    logger.warning(f"[{req_id}] Validation attempt {attempt + 1} failed: {last_error}")
                    if attempt < max_repairs:
                        # Repair prompt including exact validation error
                        current_prompt = (
                            f"{contents}\n\n"
                            f"CRITICAL FIX REQUIRED: Your previous response produced this error:\n"
                            f"{last_error}\n"
                            f"Correct this error strictly adhering to the JSON schema and math rules."
                        )
                        await asyncio.sleep(0.5 * (attempt + 1))

            raise AIOutputError(
                f"Model failed to produce valid structured output after {max_repairs} repair attempts: {last_error}"
            )

    @retry(
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def _call_gemini_api(
        self,
        system_instruction: str,
        contents: str,
        temperature: float,
        response_schema: Type[BaseModel],
        request_id: str
    ):
        """Internal call to google-genai SDK with exponential backoff on 429/503."""
        loop = asyncio.get_running_loop()
        def _invoke():
            return self.sdk_client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config={
                    "system_instruction": system_instruction,
                    "temperature": temperature,
                    "response_mime_type": "application/json",
                    "response_schema": response_schema,
                }
            )
        
        response = await asyncio.wait_for(loop.run_in_executor(None, _invoke), timeout=90.0)
        input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) if hasattr(response, "usage_metadata") else 0
        output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) if hasattr(response, "usage_metadata") else 0
        return response.text, input_tokens, output_tokens

    async def stream_chat(
        self,
        system_instruction: str,
        history: list,
        user_message: str,
        temperature: float = 0.5,
        user_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Streams tutoring conversation turn by turn."""
        u_sem = self._get_user_semaphore(user_id or "global")
        async with self.worker_semaphore, u_sem:
            if not self.sdk_client:
                # Mock streaming response
                sample_tokens = [
                    "Let's think ", "about Coulomb's Law. ",
                    "What happens to the electrostatic force ",
                    "when you double the distance between ",
                    "the charges? ",
                    "Recall that $F \\propto \\frac{1}{r^2}$."
                ]
                for tok in sample_tokens:
                    await asyncio.sleep(0.05)
                    yield tok
                return

            loop = asyncio.get_running_loop()
            # Prepare contents
            contents = []
            for h in history:
                contents.append(f"{h['role']}: {h['content']}")
            contents.append(f"user: {user_message}")
            full_prompt = "\n".join(contents)

            def _stream_call():
                return self.sdk_client.models.generate_content_stream(
                    model=self.model_name,
                    contents=full_prompt,
                    config={
                        "system_instruction": system_instruction,
                        "temperature": temperature,
                    }
                )

            stream = await loop.run_in_executor(None, _stream_call)
            for chunk in stream:
                if chunk.text:
                    yield chunk.text

    def _generate_mock_structured(self, schema: Type[T], contents: str) -> T:
        """Provides realistic mock data conforming to schemas for testing when offline."""
        if schema == SectionNotes:
            return SectionNotes(
                section_title="Electrostatics & Electric Fields",
                overview="Study of electric charges at rest, electric fields, and Coulomb's Law.",
                definitions=[
                    {
                        "term": "Electric Field",
                        "definition": "Force per unit positive test charge placed at that point: $\\vec{E} = \\frac{\\vec{F}}{q_0}$.",
                        "source_chunk_ids": ["mock-chunk-1"]
                    }
                ],
                laws_and_statements=[
                    {
                        "law_name": "Coulomb's Law",
                        "statement": "The electrostatic force between two point charges is inversely proportional to the square of separation distance.",
                        "mathematical_form": "$F = \\frac{1}{4\\pi\\varepsilon_0} \\frac{q_1 q_2}{r^2}$",
                        "source_chunk_ids": ["mock-chunk-1"]
                    }
                ],
                derivations=[
                    {
                        "title": "Electric Field on the Axial Line of a Dipole",
                        "given": "An electric dipole of dipole moment $p = 2aq$ along x-axis.",
                        "steps": [
                            "Step 1: Compute electric field due to $+q$: $E_1 = \\frac{q}{4\\pi\\varepsilon_0 (r-a)^2}$.",
                            "Step 2: Compute electric field due to $-q$: $E_2 = \\frac{q}{4\\pi\\varepsilon_0 (r+a)^2}$.",
                            "Step 3: Subtract opposite vectors and take limit $r \\gg a$: $E_{axial} = \\frac{2p}{4\\pi\\varepsilon_0 r^3}$."
                        ],
                        "result": "The electric field varies inversely with $r^3$ in axial orientation.",
                        "source_chunk_ids": ["mock-chunk-1"]
                    }
                ],
                formulae=[
                    {
                        "formula_name": "Electrostatic Force",
                        "latex": "F = \\frac{1}{4\\pi\\varepsilon_0} \\frac{q_1 q_2}{r^2}",
                        "symbol_meanings": {"F": "Force", "r": "Distance", "\\varepsilon_0": "Permittivity"},
                        "si_unit": "\\mathrm{N}"
                    }
                ],
                worked_examples=[
                    {
                        "question": "Calculate the force between two charges of $2\\,\\mathrm{\\mu C}$ and $3\\,\\mathrm{\\mu C}$ separated by $0.1\\,\\mathrm{m}$.",
                        "solution_steps": [
                            "Given: $q_1 = 2 \\times 10^{-6}\\,\\mathrm{C}$, $q_2 = 3 \\times 10^{-6}\\,\\mathrm{C}$, $r = 0.1\\,\\mathrm{m}$.",
                            "Formula: $F = \\frac{1}{4\\pi\\varepsilon_0} \\frac{q_1 q_2}{r^2}$ where $\\frac{1}{4\\pi\\varepsilon_0} = 9 \\times 10^9\\,\\mathrm{N\\cdot m^2/C^2}$.",
                            "Calculation: $F = 9 \\times 10^9 \\times \\frac{6 \\times 10^{-12}}{0.01} = 5.4\\,\\mathrm{N}$."
                        ],
                        "final_answer": "$5.4\\,\\mathrm{N}$"
                    }
                ],
                exam_tips=["Always write SI units in final answers to avoid losing 0.5 marks."],
                common_errors=["Forgetting that dipole field falls off as $1/r^3$ not $1/r^2$."],
                gaps=[]
            )
        elif schema == FlashcardsList:
            return FlashcardsList(
                cards=[
                    {
                        "card_type": "formula",
                        "front": "State Coulomb's Law formula and SI units of permittivity.",
                        "back": "$F = \\frac{1}{4\\pi\\varepsilon_0}\\frac{q_1 q_2}{r^2}$. SI unit of $\\varepsilon_0$ is $\\mathrm{C^2 N^{-1} m^{-2}}$.",
                        "tags": ["Physics", "Electrostatics"],
                        "source_chunk_id": "mock-chunk-1"
                    },
                    {
                        "card_type": "difference",
                        "front": "Distinguish between Electric Field $E$ and Electric Potential $V$.",
                        "back": "Electric field $E = -\\frac{dV}{dr}$ is a vector (N/C); Potential $V = \\frac{W}{q}$ is a scalar (Volt).",
                        "tags": ["Physics", "Concepts"],
                        "source_chunk_id": "mock-chunk-1"
                    }
                ]
            )
        elif schema == GeneratedPaper:
            return GeneratedPaper(
                subject="Mathematics",
                class_level=12,
                total_marks=80.0,
                sections=["A", "B", "C", "D", "E"],
                questions=[
                    {
                        "q_no": 1,
                        "section": "A",
                        "q_type": "mcq",
                        "marks": 1.0,
                        "question_md": "If $A$ is a square matrix of order 3 such that $|A| = 4$, then $|2A|$ is equal to:",
                        "options": ["A) 8", "B) 16", "C) 32", "D) 64"],
                        "answer_md": "C) 32",
                        "marking_scheme": {
                            "steps": [{"step_description": "Use formula $|kA| = k^n |A|$ with $n=3, k=2$: $2^3 \\times 4 = 32$", "marks": 1.0}],
                            "total_marks": 1.0
                        },
                        "difficulty": "easy"
                    }
                ]
            )
        elif schema == EvaluationResult:
            return EvaluationResult(
                awarded_total=2.0,
                max_total=3.0,
                steps=[
                    {"expected_step": "State Coulomb formula", "awarded": 1.0, "max": 1.0, "matched_evidence": "F = k q1 q2 / r^2"},
                    {"expected_step": "Substitute values correctly", "awarded": 1.0, "max": 1.0, "matched_evidence": "substituted numbers"},
                    {"expected_step": "Final answer with SI unit N", "awarded": 0.0, "max": 1.0, "missing_or_wrong": "Omitted unit N in final answer"}
                ],
                feedback_md="Good algebraic application, but always remember to append the SI unit in the final numerical line.",
                model_answer_md="$$F = 5.4\\,\\mathrm{N}$$",
                how_to_gain_marks=["Always write units with final numerical answers."],
                identified_mistake_category="unit_error"
            )
        elif schema == DrillSpec:
            return DrillSpec(
                mistake_category="unit_error",
                concept_summary="Ensuring correct SI unit attachment to physical quantities in CBSE questions.",
                questions=[
                    {
                        "q_no": 1,
                        "question_md": "State the SI unit of electric dipole moment.",
                        "options": ["A) $\\mathrm{C/m}$", "B) $\\mathrm{C\\cdot m}$", "C) $\\mathrm{N/C}$", "D) $\\mathrm{J/C}$"],
                        "answer_md": "B) $\\mathrm{C\\cdot m}$",
                        "explanation_md": "Dipole moment $p = q \\times 2a$, so unit is Coulomb $\\times$ metre."
                    }
                ]
            )
        elif schema == CoverageBatchResult:
            return CoverageBatchResult(
                verifications=[
                    {
                        "topic_title": "Coulomb's Law",
                        "covered": True,
                        "evidence_quote": "Coulomb's Law states that..."
                    }
                ]
            )
        
        # Generic fallback instance
        return schema.model_validate({})

ai_client = GeminiClient()
