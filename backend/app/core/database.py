"""
FileForge Backend - Database Connection
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from fastapi import Depends
from typing import AsyncGenerator

from app.core.config import settings
from app.models.database import Base

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    echo=settings.DEBUG,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables with retry logic"""
    import asyncio
    import logging
    logger = logging.getLogger(__name__)

    max_retries = 10
    for attempt in range(1, max_retries + 1):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database initialized successfully!")
            return
        except Exception as exc:
            if attempt == max_retries:
                logger.error(f"Failed to connect to database after {max_retries} attempts: {exc}")
                raise
            logger.warning(f"Database connection attempt {attempt}/{max_retries} failed ({exc}). Retrying in 2s...")
            await asyncio.sleep(2)


async def close_db():
    """Close database connection"""
    await engine.dispose()
