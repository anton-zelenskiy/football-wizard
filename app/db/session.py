"""
Database session management for SQLAlchemy async operations
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
import structlog


logger = structlog.get_logger()

# Global database engine and session factory
_async_engine = None
_async_session_local = None


def get_async_engine():
    """Get or create async database engine"""
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine(
            'sqlite+aiosqlite:///football.db', echo=False
        )
        logger.info('Async database engine created')
    return _async_engine


def get_async_session_local():
    """Get or create async session factory"""
    global _async_session_local
    if _async_session_local is None:
        engine = get_async_engine()
        _async_session_local = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        logger.info('Async session factory created')
    return _async_session_local


def get_async_db_session() -> AsyncSession:
    """Get async database session for repository operations"""
    session_local = get_async_session_local()
    return session_local()


async def close_async_engine():
    """Close the async database engine"""
    global _async_engine
    if _async_engine:
        await _async_engine.dispose()
        _async_engine = None
        logger.info('Async database engine closed')
