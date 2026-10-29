import asyncio
import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from app.config import settings
from app.db.models import Base

logger = logging.getLogger("vexovault.db")

import urllib.parse

from sqlalchemy.pool import NullPool

def get_engine_and_args():
    url = settings.DATABASE_URL
    connect_args = {}
    engine_kwargs = {
        "echo": False,
        "pool_pre_ping": True,
    }
    
    if "postgresql" in url or "postgres" in url or "asyncpg" in url:
        if url.startswith("postgres://"):
            url = "postgresql+asyncpg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://"):]
        
        parsed = urllib.parse.urlparse(url)
        clean_url = urllib.parse.urlunparse(parsed._replace(query=""))

        connect_args = {
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            "command_timeout": 30,
            "ssl": True,
            "server_settings": {
                "application_name": "vexovault_api"
            }
        }
        engine_kwargs["connect_args"] = connect_args
        if "-pooler" in url or settings.ENV == "test":
            engine_kwargs["poolclass"] = NullPool
        else:
            engine_kwargs["pool_size"] = 10
            engine_kwargs["max_overflow"] = 5
            engine_kwargs["pool_recycle"] = 300
        return clean_url, engine_kwargs
    return url, engine_kwargs

_db_url, _engine_kwargs = get_engine_and_args()
engine = create_async_engine(_db_url, **_engine_kwargs)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()

async def connect_with_retry(max_retries: int = 3, delays: tuple = (1, 2, 4)):
    """Neon compute suspends when idle: retry connection with exponential delays (1s, 2s, 4s)."""
    for attempt, delay in enumerate(delays, start=1):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                logger.info("Database connection established successfully.")
                return True
        except Exception as e:
            logger.warning(f"Database connection attempt {attempt}/{len(delays)} failed: {e}. Retrying in {delay}s...")
            if attempt == len(delays):
                logger.error("All database connection retries exhausted.")
                raise e
            await asyncio.sleep(delay)
    return False

async def init_db():
    """Initializes tables for SQLite / development or verification."""
    await connect_with_retry()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified.")
