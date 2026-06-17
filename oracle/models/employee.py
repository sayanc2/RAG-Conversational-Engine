"""
Employee Models - Employee Database Schemas

This module defines Pydantic models for employee records and queries.
Used by ARCHIVIST agent for querying the employee database.

Models:
  1. EmployeeRecord - Single employee with PII fields
  2. EmployeeQueryResult - Query results with metadata
  3. ArchivistHandoffInput - Handoff parameters for ARCHIVIST
"""

from pydantic import BaseModel
from typing import Optional


class EmployeeRecord(BaseModel):
    """
    Single employee record from database.

    Contains employee information for display and context in answers.
    PII (Personally Identifiable Information) fields are tracked for SENTINEL validation.

    Note: All fields including name, age are sensitive PII. SENTINEL validates responses
    containing multiple records to prevent accidental bulk data exposure.

    Attributes:
        employee_id (str): Unique employee identifier
        name (str): Employee full name [PII]
        age (int): Employee age [PII]
        department (str): Department assignment (e.g., "Engineering", "Sales")
        office_location (str): Office location (e.g., "San Francisco", "New York")
    """
    employee_id: str  # Unique identifier
    name: str  # Employee name [PII - sensitive]
    age: int  # Employee age [PII - sensitive]
    department: str  # Department name
    office_location: str  # Office location


class EmployeeQueryResult(BaseModel):
    """
    Result of an employee database query.

    Contains query results, source SQL, and metadata about execution.
    Used to track what data was retrieved and how for audit trails.

    Attributes:
        employees (list[EmployeeRecord]): Employees matching query
        total_count (int): Number of employees returned (limited by query)
        location_embedding_match (Optional[str]): If query used location matching,
          which location was matched (e.g., "San Francisco" from semantic search)
        query_sql (str): Actual SQL query executed (for debugging, audit trails)
    """
    employees: list[EmployeeRecord]  # Query results
    total_count: int  # Number of results returned
    location_embedding_match: Optional[str] = None  # Semantic location match if used
    query_sql: str  # Actual SQL executed (for debugging/compliance)


class ArchivistHandoffInput(BaseModel):
    """
    Input parameters for handing off to ARCHIVIST agent.

    Used when Conductor decides to escalate to ARCHIVIST for employee queries.
    Provides filtering hints to narrow down search.

    Attributes:
        query (str): The user's employee-related question
        employee_name_hint (Optional[str]): Employee name if mentioned
          (e.g., "John Smith" from "Where does John Smith work?")
        department_hint (Optional[str]): Department if mentioned
          (e.g., "Engineering" from "Who's on the Engineering team?")
        location_hint (Optional[str]): Office location if mentioned
          (e.g., "San Francisco" from "Employees at SF office?")
    """
    query: str  # User's employee question
    employee_name_hint: Optional[str] = None  # Employee name if mentioned
    department_hint: Optional[str] = None  # Department if mentioned
    location_hint: Optional[str] = None  # Office location if mentioned
