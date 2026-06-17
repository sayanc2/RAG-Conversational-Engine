"""
Database Models - SQLAlchemy Table Definitions

This module defines the SQLAlchemy ORM models (table schemas) for the ORACLE database.
Maps Python classes to database tables for employee data and session persistence.

Tables:
  1. Employee - Employee records (static data)
  2. SessionMemory - Conversation sessions (persistent state)
"""

from sqlalchemy import Column, String, Integer
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.

    Declarative base that all model classes inherit from.
    Enables SQLAlchemy to track all table definitions.
    """
    pass


class Employee(Base):
    """
    Employee database record (table model).

    Represents a single employee record from the company database.
    Used by ARCHIVIST agent to answer employee-related questions.

    PII Fields:
      - name: Employee full name [Sensitive]
      - age: Employee age [Sensitive]
      - Should not be exposed in bulk, validated by SENTINEL

    ╔════════════════════════════════════════════════════════════════════════════╗
    ║                         TABLE: employees                                   ║
    ╠════════════════════════════════════════════════════════════════════════════╣
    ║ Column Name     │ Data Type      │ Constraints      │ Description          ║
    ╠═════════════════╪════════════════╪══════════════════╪══════════════════════╣
    ║ employee_id     │ VARCHAR(10)    │ PRIMARY KEY      │ Unique employee ID   ║
    ║                 │                │ UNIQUE           │ (e.g., "EMP001")     ║
    ║                 │                │ NOT NULL         │                      ║
    ╠─────────────────┼────────────────┼──────────────────┼──────────────────────╣
    ║ name            │ VARCHAR(100)   │ NOT NULL         │ Full name [PII]      ║
    ║                 │                │                  │ Sensitive field      ║
    ╠─────────────────┼────────────────┼──────────────────┼──────────────────────╣
    ║ age             │ INTEGER        │ NOT NULL         │ Employee age [PII]   ║
    ║                 │                │                  │ Sensitive field      ║
    ╠─────────────────┼────────────────┼──────────────────┼──────────────────────╣
    ║ department      │ VARCHAR(50)    │ NOT NULL         │ Department name      ║
    ║                 │                │                  │ (e.g., "Engineering")║
    ╠─────────────────┼────────────────┼──────────────────┼──────────────────────╣
    ║ office_location │ VARCHAR(100)   │ NOT NULL         │ Office location      ║
    ║                 │                │                  │ (e.g., "SF", "NYC")  ║
    ╚═════════════════╧════════════════╧══════════════════╧══════════════════════╝

    Row Count: Typically 100-1000 employee records
    Usage Pattern: Read-heavy (queries), write-rare (ETL updates)
    Indexing: Primary key on employee_id
    """
    __tablename__ = "employees"

    # Unique employee identifier (e.g., "EMP001")
    # Primary key ensures uniqueness and fast lookups
    employee_id = Column(String(10), primary_key=True)

    # Employee full name [PII - Sensitive]
    # VARCHAR(100): Allows names up to 100 characters
    # NOT NULL: Every employee must have a name
    name = Column(String(100), nullable=False)

    # Employee age [PII - Sensitive]
    # INTEGER: Whole number in range 0-150
    # NOT NULL: Age must be recorded for all employees
    age = Column(Integer, nullable=False)

    # Department assignment (e.g., "Engineering", "Sales")
    # VARCHAR(50): Typical department names are short
    # NOT NULL: Every employee belongs to a department
    department = Column(String(50), nullable=False)

    # Office location (e.g., "San Francisco", "New York")
    # VARCHAR(100): Location names can be descriptive
    # NOT NULL: Every employee has an assigned office
    office_location = Column(String(100), nullable=False)

    def to_dict(self) -> dict:
        """
        Convert Employee record to dictionary.

        Used for serialization and conversion to EmployeeRecord model.

        Returns:
            dict: Employee data as dictionary with all fields
        """
        return {
            "employee_id": self.employee_id,
            "name": self.name,
            "age": self.age,
            "department": self.department,
            "office_location": self.office_location,
        }


class SessionMemory(Base):
    """
    Conversation session persistence (table model).

    Stores serialized OracleSessionContext as JSON for session resumption.
    Enables users to resume conversations or access history.

    Table: session_memory
    Primary Key: session_id (UUID)

    Attributes:
        session_id (str): UUID of conversation session (UUID v4 - 36 chars)
        user_id (str): User identifier for multi-user systems
        context_json (str): Serialized OracleSessionContext (JSON blob)
        updated_at (str): ISO timestamp of last update (for resume ordering)
    """
    __tablename__ = "session_memory"

    # Session identifier (UUID v4 - 36 characters)
    session_id = Column(String(36), primary_key=True)

    # User identifier for session ownership
    user_id = Column(String(100), nullable=False)

    # Serialized OracleSessionContext as JSON string
    # Contains: conversation_history, HITL state, query results, etc.
    context_json = Column(String, nullable=False)

    # ISO timestamp of last update (for finding latest session)
    updated_at = Column(String, nullable=False)
