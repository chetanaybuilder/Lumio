import os
import uuid
import hashlib
from pathlib import Path
from datetime import datetime, timezone
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from app.db.models import Document, IngestionJob, DocumentChunk
from app.uploads.r2 import storage_service
from app.ingestion.extract import inspect_and_open_pdf, stream_pdf_batches, ExtractionError
from app.ingestion.clean import clean_extracted_text
from app.ingestion.mathfix import classify_page
from app.ingestion.chunk import detect_headings_and_sections, chunk_sections
from app.ingestion.embed import embed_texts_batch

logger = logging.getLogger("vexovault.ingestion")

async def process_document_ingestion(
    db: AsyncSession,
    job_id: uuid.UUID
) -> bool:
    """
    Executes the ingestion pipeline for a claimed ingestion job.
    Resumes from job.last_completed_page if restarting.
    """
    stmt = select(IngestionJob).where(IngestionJob.id == job_id)
    res = await db.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        return False

    doc_stmt = select(Document).where(Document.id == job.document_id)
    doc_res = await db.execute(doc_stmt)
    document = doc_res.scalar_one_or_none()
    if not document:
        job.status = "failed"
        job.error = "Associated document row not found"
        await db.commit()
        return False

    temp_pdf_path = Path(f"./temp/{document.id}.pdf")
    temp_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Stage 1: Download & Stream from R2 with SHA-256 calculation
        job.stage = "download"
        job.status = "running"
        job.heartbeat_at = datetime.now(timezone.utc)
        await db.commit()

        hasher = hashlib.sha256()
        storage_service.stream_to_temp_file(document.r2_key, temp_pdf_path)

        with open(temp_pdf_path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                hasher.update(chunk)
        document.sha256 = hasher.hexdigest()
        await db.commit()

        # Stage 2: Open and Validate PDF
        job.stage = "open"
        await db.commit()
        doc_fitz = inspect_and_open_pdf(temp_pdf_path)
        total_pages = len(doc_fitz)
        document.page_count = total_pages
        await db.commit()

        # Stage 3: Extract, Classify, Clean in batches of 10 pages
        job.stage = "extract"
        start_page = job.last_completed_page
        all_pages_data = []
        ocr_count = 0

        for batch in stream_pdf_batches(doc_fitz, batch_size=10, start_page=start_page):
            for p_info in batch:
                page_obj = doc_fitz[p_info["page_num"] - 1]
                p_class = classify_page(page_obj)
                
                raw_text = p_info["text"]
                if p_class in ("math_heavy", "scanned"):
                    ocr_count += 1
                
                cleaned = clean_extracted_text(raw_text)
                all_pages_data.append({
                    "page_num": p_info["page_num"],
                    "text": cleaned,
                    "classification": p_class
                })

            job.last_completed_page = batch[-1]["page_num"]
            job.progress_pct = min(50, int((job.last_completed_page / total_pages) * 50))
            job.heartbeat_at = datetime.now(timezone.utc)
            await db.commit()

        doc_fitz.close()
        document.ocr_page_count = ocr_count

        # Stage 4: Structure-aware chunking
        job.stage = "chunk"
        job.progress_pct = 60
        await db.commit()

        sections = detect_headings_and_sections(all_pages_data)
        chunks = chunk_sections(sections, target_tokens=700, max_tokens=1000, overlap_tokens=100)

        # Stage 5: Batched embedding
        job.stage = "embed"
        job.progress_pct = 75
        await db.commit()

        embed_inputs = [c["embedding_text"] for c in chunks]
        embeddings = await embed_texts_batch(embed_inputs, target_dim=700)

        # Stage 6: Database Indexing
        job.stage = "index"
        job.progress_pct = 90
        await db.commit()

        # Remove previous chunks for this document if resuming
        await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))

        for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            chunk_row = DocumentChunk(
                id=uuid.uuid4(),
                document_id=document.id,
                user_id=document.user_id,
                chunk_index=chunk["chunk_index"],
                page_start=chunk["page_start"],
                page_end=chunk["page_end"],
                heading_path=chunk["heading_path"],
                content=chunk["content"],
                token_count=chunk["token_count"],
                has_math=chunk["has_math"],
                embedding=emb
            )
            db.add(chunk_row)

        # Stage 7: Finish
        now = datetime.now(timezone.utc)
        document.status = "ready"
        document.updated_at = now
        
        job.status = "succeeded"
        job.stage = "finish"
        job.progress_pct = 100
        job.finished_at = now
        await db.commit()

        logger.info(f"Ingestion succeeded for document {document.id}: {len(chunks)} chunks indexed.")
        return True

    except ExtractionError as ee:
        document.status = "failed"
        document.error_code = ee.code
        document.error_detail = ee.detail
        job.status = "failed"
        job.error = ee.detail
        await db.commit()
        return False
    except Exception as e:
        logger.error(f"Ingestion failed for job {job_id}: {str(e)}")
        job.attempts += 1
        if job.attempts >= job.max_attempts:
            job.status = "dead"
            document.status = "failed"
            document.error_code = "INGESTION_FAILED"
            document.error_detail = str(e)
        else:
            job.status = "queued"
            job.run_after = datetime.now(timezone.utc)
        job.error = str(e)
        await db.commit()
        return False
    finally:
        if temp_pdf_path.exists():
            try:
                temp_pdf_path.unlink()
            except Exception:
                pass
