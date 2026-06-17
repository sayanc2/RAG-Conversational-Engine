"""
Database Engine - SQLAlchemy Async Setup

This module configures the async SQLAlchemy database engine for the ORACLE application.
It provides database connection management, session factory, and initialization utilities.

Database:
  - Default: SQLite (oracle.db in data/ directory)
  - Configurable via DATABASE_URL environment variable
  - Async operations for non-blocking database access
  - Supports concurrent queries without blocking

Configuration:
  - ENGINE: Async engine for database operations
  - ASYNC_SESSION_FACTORY: Factory for creating database sessions
  - check_same_thread=False: Allow SQLite use in async context
"""

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import event

# Resolve database path relative to oracle/ directory
# Points to data/oracle.db by default
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_URL = f"sqlite+aiosqlite:///{_BASE_DIR}/data/oracle.db"

# Load database URL from environment or use default SQLite
DATABASE_URL = os.environ.get("DATABASE_URL", _DEFAULT_URL)

# Create async engine with SQLAlchemy
# - echo=False: Don't log SQL statements (save output)
# - check_same_thread=False: Required for SQLite in async context
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

# Create session factory for generating async database sessions
# - expire_on_commit=False: Keep objects valid after commit
AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncSession:
    """
    Get a database session from the factory.

    Async context manager for database operations.
    Usage:

        ```python
        async with get_session() as session:
            result = await session.execute(select(EmployeeRecord))
        ```

    Yields:
        AsyncSession: Active database session
    """
    async with AsyncSessionFactory() as session:
        yield session


async def init_db() -> None:
    """
    Initialize database schema.

    Creates all tables defined in models.Base.metadata.
    Called at application startup to set up tables if they don't exist.

    Tables created:
      - employees: Employee records
      - session_memory: Conversation session state

    Called once at startup to ensure schema exists.
    """
    from oracle.db.models import Base
    # Create all tables from SQLAlchemy models
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
