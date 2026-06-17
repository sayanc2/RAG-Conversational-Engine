"""
Security Models - SENTINEL Guardrail Results

This module defines the result format for SENTINEL security checks.
Used to communicate security validation results from input/output guardrails.

Models:
  1. SecurityCheck - Result of security classification
"""

from pydantic import BaseModel
from typing import Optional, Literal


class SecurityCheck(BaseModel):
    """
    Result of a security classification check by SENTINEL.

    Captures whether a piece of text (input or output) contains security violations
    and the severity level. Used by guardrails to decide whether to trigger tripwire.

    Violation Types:
      Input Violations:
        - "prompt_injection": Attempt to override agent instructions
        - "off_topic": Query unrelated to system purpose
        - "pii_request": Request to extract PII from employees
        - "jailbreak": Attempt to bypass safety measures

      Output Violations:
        - "pii_leak": Response contains multiple employees' personal data
        - "data_exfiltration": Response appears to be bulk data dump

    Severity Levels:
      - "low": Minor issue, allowed through (logged)
      - "medium": Moderate concern, blocked on input, allowed on output
      - "high": Critical issue, always blocked

    Tripwire Logic:
      Input guardrail:  Tripwire if unsafe AND severity in (medium, high)
      Output guardrail: Tripwire if unsafe AND severity == high (more lenient)

    Attributes:
        is_safe (bool): Whether this passed security validation
        violation_type (Optional[Literal]): What security issue was detected (if any)
        reason (str): Human-readable explanation of classification
        severity (Literal): How serious the issue is (low, medium, high)
    """
    is_safe: bool  # Passed security checks
    violation_type: Optional[Literal[
        "prompt_injection",    # Attempt to override instructions
        "off_topic",          # Query outside system scope
        "pii_request",        # Request to extract PII
        "pii_leak",           # Response contains PII leak
        "jailbreak",          # Attempt to bypass safety
        "data_exfiltration",  # Bulk data dump attempt
    ]] = None  # Specific violation if is_safe=False
    reason: str  # Explanation of security classification
    severity: Literal["low", "medium", "high"] = "low"  # Issue severity
