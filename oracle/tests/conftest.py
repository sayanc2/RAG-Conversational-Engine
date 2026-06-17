"""
Test Configuration - pytest Fixtures and Setup

This module configures pytest for the ORACLE test suite.
Sets up Python path resolution and environment variables for test execution.

Pytest Hook:
  - Runs before any tests
  - Ensures correct module imports
  - Configures environment for compatibility
"""

import sys
import os
import pytest

# Ensure project root is on sys.path so `agents` resolves to openai-agents package,
# NOT oracle.agents/ local directory. This prevents import conflicts.
# Path resolution: oracle/tests/conftest.py → oracle/ → project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Set protobuf implementation to Python mode for Python 3.14 compatibility
# Protobuf defaults to C extension which may not be available/compatible
# Force pure Python implementation for consistent test behavior
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
