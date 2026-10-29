import uuid
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.engine import get_db
from app.db.models import User, Document, IngestionJob, DocumentChunk, StudyNote, Quiz, UserMistake
from app.deps import get_current_user
from app.uploads.service import init_upload, complete_upload

router = APIRouter(tags=["documents"])

class InitUploadRequest(BaseModel):
    filename: str
    size_bytes: int
    subject: Optional[str] = "Mathematics"
    class_level: Optional[int] = 12

class PartETag(BaseModel):
    part_number: int
    etag: str

class CompleteUploadRequest(BaseModel):
    document_id: str
    upload_id: str
    parts: List[PartETag]

@router.post("/uploads/init")
async def api_init_upload(
    payload: InitUploadRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await init_upload(
        db=db,
        user=user,
        filename=payload.filename,
        size_bytes=payload.size_bytes,
        subject=payload.subject or "Mathematics",
        class_level=payload.class_level or 12
    )

@router.post("/uploads/complete")
async def api_complete_upload(
    payload: CompleteUploadRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        doc_uuid = uuid.UUID(payload.document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    return await complete_upload(
        db=db,
        user=user,
        document_id=doc_uuid,
        upload_id=payload.upload_id,
        parts=[p.model_dump() for p in payload.parts]
    )

@router.get("/documents/{doc_id}/status")
async def get_document_status(
    doc_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        d_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    stmt = select(Document).where(Document.id == d_uuid, Document.user_id == user.id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    job_stmt = select(IngestionJob).where(IngestionJob.document_id == d_uuid).order_by(IngestionJob.created_at.desc())
    job_res = await db.execute(job_stmt)
    job = job_res.scalars().first()

    return {
        "document_id": str(doc.id),
        "status": doc.status,
        "page_count": doc.page_count,
        "ocr_page_count": doc.ocr_page_count,
        "job": {
            "status": job.status if job else None,
            "stage": job.stage if job else None,
            "progress_pct": job.progress_pct if job else 0,
            "last_completed_page": job.last_completed_page if job else 0,
            "error": job.error if job else None
        } if job else None
    }

@router.get("/documents/{doc_id}")
async def get_document(
    doc_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        d_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    stmt = select(Document).where(Document.id == d_uuid, Document.user_id == user.id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    chunk_count_stmt = select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == d_uuid)
    chunk_count = (await db.execute(chunk_count_stmt)).scalar() or 0

    return {
        "id": str(doc.id),
        "title": doc.title,
        "subject": doc.subject,
        "class_level": doc.class_level,
        "original_filename": doc.original_filename,
        "size_bytes": doc.size_bytes,
        "page_count": doc.page_count,
        "chunk_count": chunk_count,
        "status": doc.status,
        "created_at": doc.created_at.isoformat() if doc.created_at else None
    }

@router.get("/vault")
async def get_study_vault(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Study Vault overview returning documents, study notes, and mistake summary."""
    docs_stmt = select(Document).where(Document.user_id == user.id).order_by(Document.created_at.desc()).limit(20)
    docs = (await db.execute(docs_stmt)).scalars().all()

    notes_stmt = select(StudyNote).where(StudyNote.user_id == user.id).order_by(StudyNote.created_at.desc()).limit(10)
    notes = (await db.execute(notes_stmt)).scalars().all()

    quizzes_stmt = select(Quiz).where(Quiz.user_id == user.id).order_by(Quiz.created_at.desc()).limit(10)
    quizzes = (await db.execute(quizzes_stmt)).scalars().all()

    mistakes_count_stmt = select(func.count(UserMistake.id)).where(
        UserMistake.user_id == user.id,
        UserMistake.resolved.is_(False)
    )
    unresolved_mistakes = (await db.execute(mistakes_count_stmt)).scalar() or 0

    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "class_level": user.class_level,
            "board": user.board
        },
        "documents": [
            {
                "id": str(d.id),
                "title": d.title,
                "subject": d.subject,
                "class_level": d.class_level,
                "page_count": d.page_count,
                "status": d.status,
                "created_at": d.created_at.isoformat() if d.created_at else None
            } for d in docs
        ],
        "notes": [
            {
                "id": str(n.id),
                "document_id": str(n.document_id),
                "title": n.title,
                "created_at": n.created_at.isoformat() if n.created_at else None
            } for n in notes
        ],
        "quizzes": [
            {
                "id": str(q.id),
                "subject": q.subject,
                "mode": q.mode,
                "total_marks": q.total_marks,
                "created_at": q.created_at.isoformat() if q.created_at else None
            } for q in quizzes
        ],
        "unresolved_mistakes": unresolved_mistakes
    }
