import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.engine import get_db
from app.db.models import User, StudyNote, SyllabusTopic, CoverageReport, Document
from app.deps import get_current_user
from app.ai.client import ai_client
from app.ai.schemas import CoverageBatchResult, TopicVerification
from app.ai.retrieval import cosine_similarity
from app.ingestion.embed import embed_texts_batch

router = APIRouter(tags=["coverage_checker"])

@router.post("/notes/{note_id}/coverage")
async def check_note_coverage(
    note_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        n_uuid = uuid.UUID(note_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid note ID")

    stmt = select(StudyNote).where(StudyNote.id == n_uuid, StudyNote.user_id == user.id)
    note = (await db.execute(stmt)).scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Study note not found")

    # Load associated document
    doc_stmt = select(Document).where(Document.id == note.document_id)
    doc = (await db.execute(doc_stmt)).scalar_one_or_none()
    class_lvl = doc.class_level if doc else 12
    subject = doc.subject if doc else "Mathematics"

    # Load syllabus topics (leaf topics: parent_id IS NOT NULL)
    top_stmt = select(SyllabusTopic).where(
        SyllabusTopic.class_level == class_lvl,
        SyllabusTopic.subject == subject,
        SyllabusTopic.parent_id.is_not(None)
    ).limit(30)
    leaf_topics = (await db.execute(top_stmt)).scalars().all()

    if not leaf_topics:
        # Fallback to standard topics if seed topics not populated for this specific subject
        top_stmt2 = select(SyllabusTopic).where(SyllabusTopic.parent_id.is_not(None)).limit(15)
        leaf_topics = (await db.execute(top_stmt2)).scalars().all()

    total_count = max(1, len(leaf_topics))
    note_text = note.content_md.lower()

    covered_topics = []
    missing_topics = []

    for top in leaf_topics:
        # Check if topic title or key terms appear in note text
        title_words = [w.lower() for w in top.title.split() if len(w) > 3]
        match_count = sum(1 for w in title_words if w in note_text)
        is_covered = (match_count >= max(1, len(title_words) // 2))

        if is_covered:
            covered_topics.append({
                "topic_key": top.topic_key,
                "title": top.title,
                "weightage_marks": float(top.weightage_marks or 1.0)
            })
        else:
            missing_topics.append({
                "topic_key": top.topic_key,
                "title": top.title,
                "weightage_marks": float(top.weightage_marks or 1.0)
            })

    score = round((len(covered_topics) / total_count) * 100, 1)

    report = CoverageReport(
        id=uuid.uuid4(),
        note_id=note.id,
        user_id=user.id,
        syllabus_year="2024-25",
        total_topics=total_count,
        covered_topics=len(covered_topics),
        missing=missing_topics,
        score=score,
        created_at=datetime.now(timezone.utc)
    )
    db.add(report)
    await db.commit()

    return {
        "report_id": str(report.id),
        "note_id": str(note.id),
        "score": float(report.score),
        "total_topics": total_count,
        "covered_count": len(covered_topics),
        "missing_count": len(missing_topics),
        "covered_topics": covered_topics,
        "missing_topics": missing_topics
    }

@router.get("/notes/{note_id}/coverage")
async def get_coverage_report(
    note_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        n_uuid = uuid.UUID(note_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid note ID")

    stmt = select(CoverageReport).where(
        CoverageReport.note_id == n_uuid,
        CoverageReport.user_id == user.id
    ).order_by(CoverageReport.created_at.desc())

    rep = (await db.execute(stmt)).scalars().first()
    if not rep:
        raise HTTPException(status_code=404, detail="Coverage report not found")

    return {
        "id": str(rep.id),
        "score": float(rep.score),
        "total_topics": rep.total_topics,
        "covered_topics": rep.covered_topics,
        "missing": rep.missing,
        "created_at": rep.created_at.isoformat()
    }
