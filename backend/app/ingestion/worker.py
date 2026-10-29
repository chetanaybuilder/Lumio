import os
import sys
import asyncio
import uuid
import logging
from datetime import datetime, timezone
from app.db.engine import async_session, connect_with_retry
from app.ingestion.queue import claim_next_job, reap_stale_jobs, heartbeat_job
from app.ingestion.pipeline import process_document_ingestion

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("vexovault.worker")

class IngestionWorker:
    def __init__(self, worker_id: str = None):
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.running = False

    async def run_once(self) -> bool:
        """Processes one available job, returns True if job was processed."""
        async with async_session() as db:
            await reap_stale_jobs(db)
            job = await claim_next_job(db, self.worker_id)
            if not job:
                return False

            logger.info(f"Worker {self.worker_id} claimed job {job.id} for document {job.document_id}")
            
            # Start heartbeat task
            heartbeat_stop = asyncio.Event()
            async def _heartbeat_loop():
                while not heartbeat_stop.is_set():
                    try:
                        await asyncio.sleep(15)
                        async with async_session() as hdb:
                            await heartbeat_job(hdb, job.id)
                    except Exception:
                        pass

            hb_task = asyncio.create_task(_heartbeat_loop())
            try:
                success = await process_document_ingestion(db, job.id)
                logger.info(f"Job {job.id} finished with success={success}")
                return True
            finally:
                heartbeat_stop.set()
                hb_task.cancel()

    async def start(self, poll_interval: float = 2.0):
        """Worker loop continuously polling and claiming jobs."""
        self.running = True
        logger.info(f"Ingestion worker {self.worker_id} started. Connecting to database...")
        await connect_with_retry()
        while self.running:
            try:
                processed = await self.run_once()
                if not processed:
                    await asyncio.sleep(poll_interval)
            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(poll_interval)

    def stop(self):
        self.running = False

if __name__ == "__main__":
    worker = IngestionWorker()
    try:
        asyncio.run(worker.start())
    except KeyboardInterrupt:
        logger.info("Worker shutting down...")
