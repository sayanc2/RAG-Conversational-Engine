"""
Session Store - Persistent Session Memory

This module provides async storage and retrieval of conversation sessions.
Enables multi-turn conversations to persist across restarts and allows users
to resume sessions or access conversation history.

Features:
  - Async database access (non-blocking)
  - JSON serialization of session state
  - Per-user session tracking
  - Latest session retrieval for resume functionality

Database:
  - Uses same database as employee data (oracle.db by default)
  - SessionMemory table stores session_id, user_id, and context JSON
  - Indexes on session_id and user_id for fast lookups
"""

import os
import json
import asyncio
from datetime import datetime

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, delete

from oracle.db.models import Base, SessionMemory
from oracle.models import OracleSessionContext

# Database configuration
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_URL = f"sqlite+aiosqlite:///{_BASE_DIR}/data/oracle.db"

# Singleton database engine and session factory (lazy initialized)
_engine = None
_SessionFactory = None


def _get_factory():
    """
    Get or create the async SQLAlchemy session factory.

    Uses lazy initialization for the database connection.
    Database URL can be overridden via DATABASE_URL environment variable.

    Returns:
        async_sessionmaker: Factory for creating database sessions
    """
    global _engine, _SessionFactory
    if _SessionFactory is None:
        # Load database URL from environment or use default SQLite
        url = os.environ.get("DATABASE_URL", _DEFAULT_URL)
        # Create async engine (non-blocking database access)
        _engine = create_async_engine(url, echo=False)
        # Create session factory for this engine
        _SessionFactory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    return _SessionFactory


async def save_session(ctx: OracleSessionContext) -> None:
    """
    Persist a session context to the database.

    Saves or updates the session state so it can be resumed later.
    JSON-encodes the OracleSessionContext for storage.
    Tracks update timestamp for latest-session lookups.

    Upsert Logic:
      - If session exists: Update context_json and updated_at timestamp
      - If session doesn't exist: Insert new SessionMemory row

    Args:
        ctx (OracleSessionContext): Session state to save
    """
    factory = _get_factory()
    async with factory() as session:
        # Get current timestamp in ISO format
        now = datetime.utcnow().isoformat()

        # Check if this session already exists
        existing = await session.get(SessionMemory, ctx.session_id)

        if existing:
            # Update existing session (upsert)
            existing.context_json = ctx.model_dump_json()
            existing.updated_at = now
        else:
            # Create new session record
            session.add(SessionMemory(
                session_id=ctx.session_id,
                user_id=ctx.user_id,
                context_json=ctx.model_dump_json(),
                updated_at=now,
            ))

        # Commit changes to database
        await session.commit()


async def load_session(session_id: str) -> OracleSessionContext | None:
    """
    Load a specific session from the database.

    Retrieves the session context by ID and deserializes from JSON.
    Used when a user resumes a previous conversation.

    Args:
        session_id (str): The session ID to retrieve

    Returns:
        OracleSessionContext | None: Session context if found, None otherwise
    """
    factory = _get_factory()
    async with factory() as session:
        # Query for this session ID
        row = await session.get(SessionMemory, session_id)
        if row:
            # Deserialize JSON back to OracleSessionContext
            return OracleSessionContext.model_validate_json(row.context_json)
    return None


async def load_latest_for_user(user_id: str) -> OracleSessionContext | None:
    """
    Load the most recently updated session for a user.

    Enables "resume" functionality: Returns the user's latest session so they
    can continue their conversation from where they left off.

    Algorithm:
      1. Query SessionMemory table for all sessions by this user_id
      2. Order by updated_at descending (newest first)
      3. Take first result
      4. Deserialize and return

    Args:
        user_id (str): The user's identifier

    Returns:
        OracleSessionContext | None: Most recent session if found, None otherwise
    """
    factory = _get_factory()
    async with factory() as session:
        # Build query: Find sessions for this user, ordered by newest first
        stmt = (
            select(SessionMemory)
            .where(SessionMemory.user_id == user_id)
            .order_by(SessionMemory.updated_at.desc())
            .limit(1)
        )

        # Execute query
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()

        # Deserialize if found
        if row:
            return OracleSessionContext.model_validate_json(row.context_json)

    return None
