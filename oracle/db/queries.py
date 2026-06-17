"""
Database Queries - Employee Data Query Building

This module provides SQL query builders for employee database access.
Constructs flexible multi-criteria queries with safe parameter handling.

Functions:
  1. build_employee_query - Build multi-criteria query with filters
  2. batch_fetch_by_ids - Fetch multiple employees by ID
"""

from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from oracle.db.models import Employee


async def build_employee_query(
    session: AsyncSession,
    name: Optional[str] = None,
    department: Optional[str] = None,
    location: Optional[str] = None,
    employee_id: Optional[str] = None,
    limit: int = 20,
) -> tuple[list[Employee], str]:
    """
    Build and execute a flexible multi-criteria employee query.

    Constructs a SQL query based on provided filter criteria.
    All string filters use ILIKE (case-insensitive) for fuzzy matching.
    Results are limited by default to prevent accidental bulk exposure.

    Query Building:
      - Combines multiple conditions with AND logic
      - Each filter is optional (empty filters are ignored)
      - Safe parameter handling via SQLAlchemy ORM

    Args:
        session (AsyncSession): Active database session
        name (Optional[str]): Employee name (fuzzy match, case-insensitive)
        department (Optional[str]): Department filter
        location (Optional[str]): Office location filter
        employee_id (Optional[str]): Exact employee ID match (converted to uppercase)
        limit (int): Maximum results to return (default: 20)

    Returns:
        tuple[list[Employee], str]: (Query results, SQL summary string)
          - Results: List of matching Employee records
          - SQL summary: Human-readable query representation (safe to log)
    """
    # Build WHERE clause conditions based on filters
    conditions = []

    # Name filter: case-insensitive fuzzy match
    if name:
        conditions.append(Employee.name.ilike(f"%{name}%"))

    # Department filter: case-insensitive partial match
    if department:
        conditions.append(Employee.department.ilike(f"%{department}%"))

    # Location filter: case-insensitive partial match
    if location:
        conditions.append(Employee.office_location.ilike(f"%{location}%"))

    # Employee ID filter: exact match (normalized to uppercase)
    if employee_id:
        conditions.append(Employee.employee_id == employee_id.upper())

    # Build base query with limit
    stmt = select(Employee).limit(limit)

    # Add WHERE clause conditions if any filters provided
    if conditions:
        stmt = stmt.where(and_(*conditions))

    # Execute query asynchronously
    result = await session.execute(stmt)
    rows = result.scalars().all()

    # Build human-readable SQL summary for logging/audit trails
    # (Not actual SQL — safe to include in logs)
    filters = []
    if name:
        filters.append(f"name ILIKE '%{name}%'")
    if department:
        filters.append(f"department ILIKE '%{department}%'")
    if location:
        filters.append(f"office_location ILIKE '%{location}%'")
    if employee_id:
        filters.append(f"employee_id = '{employee_id.upper()}'")

    # Build WHERE clause string, default to "1=1" if no filters
    where_clause = " AND ".join(filters) if filters else "1=1"
    sql_summary = f"SELECT * FROM employees WHERE {where_clause} LIMIT {limit}"

    return list(rows), sql_summary


async def batch_fetch_by_ids(session: AsyncSession, ids: list[str]) -> list[Employee]:
    """
    Fetch multiple employees by their IDs efficiently.

    Fetches employees with IDs in the provided list.
    Uses SQL IN clause for efficient batch retrieval.
    Employee IDs are normalized to uppercase.

    Args:
        session (AsyncSession): Active database session
        ids (list[str]): List of employee IDs to fetch

    Returns:
        list[Employee]: Employees matching the provided IDs
    """
    # Guard: return empty list if no IDs provided
    if not ids:
        return []

    # Build query: fetch employees with IDs in the list
    # Normalize all IDs to uppercase for comparison
    stmt = select(Employee).where(Employee.employee_id.in_([i.upper() for i in ids]))

    # Execute query
    result = await session.execute(stmt)

    # Return all matching records as list
    return list(result.scalars().all())
