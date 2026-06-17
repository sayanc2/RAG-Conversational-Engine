"""
SQL Tools - Employee Database Query Interface

This module provides agents with tools to query the employee database using SQLAlchemy.
It implements async database access for performance and safety.

Tools Provided:
  1. sql_query_employee: Query by name, department, location, or ID
  2. semantic_location_mapper: Find employees by office location similarity

Database:
  - SQLite database (default: oracle.db in data/ directory)
  - Configurable via DATABASE_URL environment variable
  - Uses async SQLAlchemy for concurrent queries

Query Limits:
  - Default: 20 results per query
  - Configurable via limit parameter
  - Prevents accidental bulk data exposure
"""

import os
from typing import Optional

from agents import function_tool, RunContextWrapper
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from oracle.models import OracleSessionContext, EmployeeRecord, EmployeeQueryResult

# Base directory for default database location
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_URL = f"sqlite+aiosqlite:///{_BASE_DIR}/data/oracle.db"

# Singleton database engine and session factory (lazy initialized)
_engine = None
_SessionFactory = None


def _get_session_factory():
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


async def _sql_query_employee_fn(
    ctx: RunContextWrapper[OracleSessionContext],
    name: Optional[str] = None,
    department: Optional[str] = None,
    location: Optional[str] = None,
    employee_id: Optional[str] = None,
    limit: int = 20,
) -> EmployeeQueryResult:
    """
    Query the employee database with flexible filtering criteria.

    Supports multi-criteria queries:
      - name: Fuzzy match on employee name
      - department: Exact match on department code
      - location: Exact match on office location
      - employee_id: Exact match on ID

    Results are limited by default to prevent bulk data exposure.
    Updates session context with last queried location for follow-ups.

    Args:
        ctx (RunContextWrapper): Session context to update with location
        name (Optional[str]): Employee name filter (fuzzy search)
        department (Optional[str]): Department filter (exact match)
        location (Optional[str]): Office location filter (exact match)
        employee_id (Optional[str]): Employee ID filter (exact match)
        limit (int): Maximum results to return (default: 20)

    Returns:
        EmployeeQueryResult: Query results with employee records and SQL summary
    """
    from oracle.db.queries import build_employee_query

    # Get async database session factory
    SessionFactory = _get_session_factory()

    # Execute query in async context
    async with SessionFactory() as session:
        rows, sql_summary = await build_employee_query(
            session,
            name=name,
            department=department,
            location=location,
            employee_id=employee_id,
            limit=limit,
        )

    # Convert database rows to EmployeeRecord models
    employees = [EmployeeRecord(**row.to_dict()) for row in rows]

    # Update session context with the location of first result (for follow-ups)
    # Example: "Are there others at that location?"
    if employees and employees[0].office_location:
        ctx.context.last_queried_location = employees[0].office_location

    return EmployeeQueryResult(
        employees=employees,
        total_count=len(employees),
        query_sql=sql_summary,
    )


async def _semantic_location_mapper_fn(
    ctx: RunContextWrapper[OracleSessionContext],
    weather_location_string: str,
) -> list[EmployeeRecord]:
    """
    Find employees by semantic similarity between weather and office locations.

    Uses vector embeddings to match weather location strings (from API) with
    employee office locations. Useful for blended queries like:
      "What's the weather at our San Francisco engineers' offices?"

    Algorithm:
      1. Embed the weather location string (e.g., "San Francisco")
      2. Query Chroma vector DB for similar employee locations
      3. Filter by distance threshold (default 0.30)
      4. Return matching employee records

    Args:
        ctx (RunContextWrapper): Session context
        weather_location_string (str): Location from weather query (e.g., "San Francisco")

    Returns:
        list[EmployeeRecord]: Employees at semantically similar office locations
    """
    from oracle.tools.chroma_tools import get_or_create_collection, embed_document

    # Load configuration thresholds
    threshold = float(os.environ.get("SEMANTIC_LOCATION_DISTANCE_THRESHOLD", "0.30"))
    n = int(os.environ.get("CHROMA_N_RESULTS", "5"))

    # Get the employee location vector database collection
    collection = get_or_create_collection("employee_locations")
    if collection.count() == 0:
        return []

    # Embed the weather location string for similarity search
    embedding = embed_document(weather_location_string)

    # Query vector DB for semantically similar locations
    results = collection.query(
        query_embeddings=[embedding],
        n_results=min(n, collection.count()),
        include=["metadatas", "distances"],
    )

    # Process results and filter by distance threshold
    matched: list[EmployeeRecord] = []
    for i, meta in enumerate(results["metadatas"][0]):
        dist = results["distances"][0][i]
        # Include if distance is below threshold (lower = more similar)
        if dist <= threshold:
            matched.append(EmployeeRecord(
                employee_id=meta["employee_id"],
                name=meta["name"],
                age=0,
                department=meta["department"],
                office_location=meta["office_location"],
            ))

    # Update session context with weather location for follow-ups
    ctx.context.last_queried_location = weather_location_string
    return matched


# Export functions as tools for agent use
sql_query_employee = function_tool(_sql_query_employee_fn)
semantic_location_mapper = function_tool(_semantic_location_mapper_fn)
