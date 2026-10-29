import uuid
from typing import Dict, Any, List
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.engine import get_db
from app.db.models import User, Document, DocumentChunk, StudyNote, UsageLedger
from app.deps import get_current_user
from app.ai.client import ai_client
from app.ai.schemas import SectionNotes
from app.ai.validator import validate_section_notes_business
from app.ai.retrieval import retrieve_chapter_chunks
from app.math.validator import validate_math_text

router = APIRouter(tags=["study_notes"])

PROMPT_FILE = Path(__file__).resolve().parent.parent / "ai" / "prompts" / "notes.v1.md"
PROMPT_VERSION = "notes.v1"

def render_section_to_markdown(sec: SectionNotes) -> str:
    """Deterministically renders SectionNotes into rich Markdown."""
    lines = [f"## {sec.section_title}\n\n{sec.overview}\n"]
    
    if sec.definitions:
        lines.append("### Key Definitions\n")
        for d in sec.definitions:
            lines.append(f"- **{d.term}**: {d.definition}")
        lines.append("")

    if sec.laws_and_statements:
        lines.append("### Laws and Principles\n")
        for l in sec.laws_and_statements:
            math_line = f" ({l.mathematical_form})" if l.mathematical_form else ""
            lines.append(f"- **{l.law_name}**: {l.statement}{math_line}")
        lines.append("")

    if sec.derivations:
        lines.append("### Rigorous Derivations\n")
        for d in sec.derivations:
            lines.append(f"#### {d.title}\n")
            lines.append(f"**Given:** {d.given}\n")
            lines.append("**Steps:**")
            for s in d.steps:
                lines.append(f"1. {s}")
            lines.append(f"\n**Result:** {d.result}\n")

    if sec.formulae:
        lines.append("### Essential Formulae & SI Units\n")
        lines.append("| Formula | LaTeX Equation | Symbol Meanings | SI Unit |")
        lines.append("| :--- | :--- | :--- | :--- |")
        for f in sec.formulae:
            syms = ", ".join([f"{k}: {v}" for k, v in f.symbol_meanings.items()]) or "-"
            lines.append(f"| {f.formula_name} | ${f.latex}$ | {syms} | ${f.si_unit}$ |")
        lines.append("")

    if sec.worked_examples:
        lines.append("### CBSE Worked Examples\n")
        for we in sec.worked_examples:
            lines.append(f"**Problem:** {we.question}\n")
            lines.append("**Solution:**")
            for st in we.solution_steps:
                lines.append(f"- {st}")
            lines.append(f"**Answer:** {we.final_answer}\n")

    if sec.exam_tips:
        lines.append("### Examiner Tips\n")
        for tip in sec.exam_tips:
            lines.append(f"- 💡 {tip}")
        lines.append("")

    if sec.common_errors:
        lines.append("### Common Mistakes to Avoid\n")
        for err in sec.common_errors:
            lines.append(f"- ⚠️ {err}")
        lines.append("")

    return "\n".join(lines)

@router.post("/documents/{doc_id}/notes")
async def generate_deep_notes(
    doc_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        d_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    # Verify document ownership
    stmt = select(Document).where(Document.id == d_uuid, Document.user_id == user.id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Retrieve all chunks in chunk_index sequence (chapter-wide map-reduce)
    chunks = await retrieve_chapter_chunks(db, d_uuid, user.id)
    if not chunks:
        raise HTTPException(status_code=400, detail="Document has no indexed text chunks yet")

    prompt_template = PROMPT_FILE.read_text(encoding="utf-8")
    system_instruction = prompt_template.replace("{{class}}", str(doc.class_level or 12)).replace("{{subject}}", doc.subject or "Science")

    # Map: Group chunks by primary heading or batches of 4 chunks
    heading_groups: Dict[str, List[DocumentChunk]] = {}
    for c in chunks:
        h_key = c.heading_path[0] if c.heading_path else "Main Chapter Content"
        heading_groups.setdefault(h_key, []).append(c)

    sections_md = []
    has_math_invalid = False

    for heading, grp_chunks in list(heading_groups.items())[:5]: # Generate for chapters
        context_text = "\n\n".join([f"Chunk [{c.chunk_index}] (Pages {c.page_start}-{c.page_end}):\n{c.content}" for c in grp_chunks])
        user_content = f"Generate comprehensive SectionNotes for heading: {heading}\n\nSOURCE CHUNKS:\n{context_text}"

        section_obj = await ai_client.generate_structured(
            schema=SectionNotes,
            system_instruction=system_instruction,
            contents=user_content,
            temperature=0.2,
            user_id=str(user.id)
        )

        valid_bus, bus_errs = validate_section_notes_business(section_obj)
        if not valid_bus:
            has_math_invalid = True

        rendered_sec = render_section_to_markdown(section_obj)
        sections_md.append(rendered_sec)

    final_content_md = f"# {doc.title}: Deep Study Notes\n\n" + "\n\n---\n\n".join(sections_md)

    # Check overall math validity
    math_ok, math_errs, _ = validate_math_text(final_content_md)
    if not math_ok:
        has_math_invalid = True

    note = StudyNote(
        id=uuid.uuid4(),
        user_id=user.id,
        document_id=doc.id,
        title=f"{doc.title} - Comprehensive Notes",
        scope={"chapters": list(heading_groups.keys())},
        content_md=final_content_md,
        math_invalid=has_math_invalid,
        model=ai_client.model_name,
        prompt_version=PROMPT_VERSION
    )
    db.add(note)

    # Log usage in usage_ledger
    ledger = UsageLedger(
        user_id=user.id,
        feature="deep_notes",
        model=ai_client.model_name,
        input_tokens=len(chunks) * 500,
        output_tokens=len(final_content_md) // 4
    )
    db.add(ledger)
    await db.commit()

    return {
        "id": str(note.id),
        "document_id": str(doc.id),
        "title": note.title,
        "math_invalid": note.math_invalid,
        "created_at": note.created_at.isoformat()
    }

@router.get("/notes/{note_id}")
async def get_study_note(
    note_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        n_uuid = uuid.UUID(note_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid note ID")

    stmt = select(StudyNote).where(StudyNote.id == n_uuid, StudyNote.user_id == user.id)
    res = await db.execute(stmt)
    note = res.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Study note not found")

    return {
        "id": str(note.id),
        "document_id": str(note.document_id),
        "title": note.title,
        "content_md": note.content_md,
        "math_invalid": note.math_invalid,
        "created_at": note.created_at.isoformat()
    }
