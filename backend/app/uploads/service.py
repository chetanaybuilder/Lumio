import math
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Document, IngestionJob, User
from app.uploads.r2 import storage_service

PART_SIZE = 8 * 1024 * 1024  # 8MB per part
MAX_SIZE_BYTES = 52428800    # 50MB

async def init_upload(
    db: AsyncSession,
    user: User,
    filename: str,
    size_bytes: int,
    subject: str = "Mathematics",
    class_level: int = 12
) -> Dict[str, Any]:
    if size_bytes > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size {size_bytes} exceeds maximum allowed size of 50MB"
        )

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF documents are supported"
        )

    doc_id = uuid.uuid4()
    # Scoped key prefix: u/{user_id}/{document_id}/filename
    r2_key = f"u/{user.id}/{doc_id}/{filename}"
    upload_id = storage_service.create_multipart_upload(r2_key)

    doc = Document(
        id=doc_id,
        user_id=user.id,
        title=Path(filename).stem.replace("_", " ").title(),
        subject=subject,
        class_level=class_level,
        original_filename=filename,
        r2_key=r2_key,
        r2_upload_id=upload_id,
        size_bytes=size_bytes,
        status="uploading"
    )
    db.add(doc)
    await db.commit()

    num_parts = max(1, math.ceil(size_bytes / PART_SIZE))
    parts = []
    for part_num in range(1, num_parts + 1):
        url = storage_service.generate_presigned_part_url(r2_key, upload_id, part_num)
        parts.append({"part_number": part_num, "url": url})

    return {
        "document_id": str(doc_id),
        "upload_id": upload_id,
        "key": r2_key,
        "parts": parts,
        "part_size": PART_SIZE
    }

async def complete_upload(
    db: AsyncSession,
    user: User,
    document_id: uuid.UUID,
    upload_id: str,
    parts: List[Dict[str, Any]]
) -> Dict[str, Any]:
    # Query document with per-user authorization
    stmt = select(Document).where(Document.id == document_id, Document.user_id == user.id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Complete multipart upload in R2
    s3_parts = [{"PartNumber": p["part_number"], "ETag": p["etag"]} for p in parts]
    storage_service.complete_multipart_upload(doc.r2_key, upload_id, s3_parts)

    # Magic byte verification: first 1KB must begin with %PDF-
    header_bytes = storage_service.get_first_kb(doc.r2_key)
    if not header_bytes.startswith(b"%PDF-"):
        doc.status = "failed"
        doc.error_code = "CORRUPT_PDF"
        doc.error_detail = "Missing %PDF- header magic bytes"
        await db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is not a valid PDF")

    now = datetime.now(timezone.utc)
    # In one transaction: set status = uploaded, insert ingestion_jobs row
    doc.status = "uploaded"
    doc.updated_at = now

    job = IngestionJob(
        id=uuid.uuid4(),
        document_id=doc.id,
        kind="ingest",
        status="queued",
        stage="queued",
        attempts=0,
        max_attempts=3,
        progress_pct=0,
        run_after=now,
        created_at=now
    )
    db.add(job)
    await db.commit()

    return {
        "document_id": str(doc.id),
        "job_id": str(job.id),
        "status": "queued"
    }
