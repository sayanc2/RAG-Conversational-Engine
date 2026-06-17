"""
Test Fixtures - Shared Mock Data for Tests

This module provides reusable test fixtures and mock data for the test suite.
Contains pre-built mock objects matching production data structures.

Provides:
  - Mock employee records
  - Mock weather data
  - Mock news articles
  - Mock responses from agents
  - Mock groundedness reports
  - Mock security checks
  - Context factory for test sessions
"""

from oracle.models import (
    OracleSessionContext, EmployeeRecord, WeatherResult, NewsItem,
    Source, ConductorResponse, GroundednessReport, SecurityCheck,
)
from datetime import datetime


# Mock employee record for testing
# Represents a typical employee that might be returned from database queries
MOCK_EMPLOYEE = EmployeeRecord(
    employee_id="EMP-0042",
    name="Raghav Sharma",
    age=34,
    department="Engineering",
    office_location="Austin, TX",
)

# Mock weather data for testing
# Represents typical current weather conditions from Tavily API
MOCK_WEATHER = WeatherResult(
    location="Austin, TX",
    normalized_location="austin_tx",  # Canonical form
    temperature_f=94.0,  # Current temperature
    conditions="Partly Cloudy, 94°F",  # Human-readable conditions
    forecast_summary="Continued warm temperatures through the weekend.",  # Short forecast
    fetched_at=datetime(2024, 6, 1, 12, 0, 0),  # When this was retrieved
    tavily_url="https://example.com/weather/austin",  # Source URL
)

# Mock news article for testing
# Represents a news article that might be returned from Tavily search
MOCK_NEWS = NewsItem(
    headline="Austin Tech Scene Booms",
    summary="Austin continues to attract major tech companies...",
    url="https://example.com/news/austin-tech",
    published_at="2024-06-01",
)

# Mock sources list for testing
# Represents the data sources backing an answer
MOCK_SOURCES = [
    # Source from SQL (employee database)
    Source(source_type="sql", reference_id="EMP-0042", excerpt="Raghav Sharma, Engineering, Austin TX", confidence=1.0),
    # Source from Tavily (weather API)
    Source(source_type="tavily", reference_id="weather_austin_tx", excerpt="94°F Partly Cloudy Austin TX", confidence=0.9),
]

# Mock Conductor response for testing
# Represents a typical structured response from Conductor agent
MOCK_CONDUCTOR_RESPONSE = ConductorResponse(
    answer="Raghav Sharma works in Austin, TX. Current weather: 94°F, Partly Cloudy.",
    sources=MOCK_SOURCES,
    confidence=0.95,  # High confidence in this answer
    query_type="blended",  # Needed both employee and weather data
    hitl_required=False,  # Confidence high enough, no HITL needed
    follow_up_suggestions=["What department does Raghav work in?", "What is tomorrow's forecast for Austin?"],
)

# Mock groundedness report for passing response
# Represents validation result when answer is well-grounded
MOCK_GROUNDEDNESS_PASS = GroundednessReport(
    score=0.97,  # 97% of claims are grounded (excellent)
    ungrounded_claims=[],  # No ungrounded claims
    verdict="pass",  # Passes validation threshold (>= 0.85)
    recommendation="Proceed.",  # Safe to deliver without HITL
)

# Mock groundedness report for failing response
# Represents validation result when answer has low confidence
MOCK_GROUNDEDNESS_FAIL = GroundednessReport(
    score=0.45,  # 45% of claims are grounded (poor)
    ungrounded_claims=["The temperature is 94°F"],  # This claim lacks support
    verdict="fail",  # Fails validation threshold (< 0.70)
    recommendation="HITL required.",  # Needs human review
)

# Mock security check for safe input/output
# Represents SENTINEL validation result when text is safe
MOCK_SECURITY_SAFE = SecurityCheck(is_safe=True, reason="Legitimate employee query.", severity="low")

# Mock security check for blocked input/output
# Represents SENTINEL validation result when text contains violations
MOCK_SECURITY_BLOCKED = SecurityCheck(
    is_safe=False,
    violation_type="prompt_injection",  # Specific violation type detected
    reason="Detected attempt to override system instructions.",  # Why it was blocked
    severity="high",  # Critical severity
)


def make_ctx() -> OracleSessionContext:
    """
    Factory function to create a test session context.

    Creates a new OracleSessionContext with test defaults:
      - session_id: "test-session-001"
      - user_id: "test_user"

    Used in tests to provide a clean session state without side effects.

    Returns:
        OracleSessionContext: Fresh test session context
    """
    return OracleSessionContext(session_id="test-session-001", user_id="test_user")
