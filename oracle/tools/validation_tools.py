"""
Validation Tools - On-Demand Groundedness Checking

This module provides agent-callable tools for validating answer groundedness.
Unlike VALIDATOR guardrails (automatic on every query), these tools allow agents
to manually verify specific answers during reasoning or refinement.

Tools:
  1. extract_and_verify_claims: Agent can verify answer against sources
"""

import os
import json
from agents import function_tool, RunContextWrapper
from openai import OpenAI

from oracle.models import OracleSessionContext, GroundednessReport, ClaimVerification, Source


def _get_openai():
    """
    Get or create OpenAI client instance.

    Loads API key from environment variable OPENAI_API_KEY.
    Returns a configured OpenAI client for API calls.

    Returns:
        OpenAI: Configured client for making API calls
    """
    return OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))


def _extract_and_verify_claims_fn(
    ctx: RunContextWrapper[OracleSessionContext],
    answer_text: str,
    retrieved_sources: list[dict],
) -> GroundednessReport:
    """
    Verify factual claims in an answer against source material.

    Extracts each factual claim from the answer and checks if it's supported by
    the provided source chunks. Returns detailed groundedness report.

    Used as optional tool: Agents can call this to verify their working hypothesis
    or double-check an answer before finalizing.

    Algorithm:
      1. Extract factual claims from answer text
      2. For each claim, check against source chunks
      3. Calculate score: (grounded / total), 0.0-1.0
      4. Apply thresholds (pass/warn/fail)
      5. Return detailed report

    Thresholds:
      - warn_threshold: 0.85 (default) - high confidence, pass
      - tripwire: 0.70 (default) - minimum acceptable

    Args:
        ctx (RunContextWrapper): Session context to update with score
        answer_text (str): The answer to verify
        retrieved_sources (list[dict]): Source chunks to verify against

    Returns:
        GroundednessReport: Detailed verification with per-claim breakdown
    """
    # Load thresholds from environment
    tripwire = float(os.environ.get("GROUNDEDNESS_TRIPWIRE_THRESHOLD", "0.70"))
    warn = float(os.environ.get("GROUNDEDNESS_WARN_THRESHOLD", "0.85"))

    client = _get_openai()

    # Truncate sources to first 3000 chars to keep prompt reasonable
    sources_str = json.dumps(retrieved_sources, indent=2)[:3000]

    # System prompt for GPT-4o: act as groundedness critic
    system = (
        "You are a groundedness critic. Given an answer and source chunks, "
        "identify every factual claim in the answer and check if it is supported by the sources. "
        "Respond ONLY with valid JSON matching: "
        '{"claims": [{"claim": str, "is_grounded": bool, "reason": str, "source_ref": str|null}]}'
    )

    # Build user message with answer and sources
    user_msg = f"ANSWER:\n{answer_text}\n\nSOURCES:\n{sources_str}"

    # Call GPT-4o for semantic claim verification
    response = client.chat.completions.create(
        model=os.environ.get("OPENAI_DEFAULT_MODEL", "gpt-4o"),
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
        response_format={"type": "json_object"},
        max_tokens=800,
    )

    # Parse claim verification response
    data = json.loads(response.choices[0].message.content)
    claims_raw = data.get("claims", [])

    # Edge case: answer has no verifiable claims (e.g., greeting)
    if not claims_raw:
        score = 1.0
        verdict = "pass"
        return GroundednessReport(
            score=score,
            claim_verifications=[],
            ungrounded_claims=[],
            verdict=verdict,
            recommendation="No verifiable claims found — treated as pass.",
        )

    # Build ClaimVerification objects with source references
    verifications: list[ClaimVerification] = []
    for c in claims_raw:
        # Create Source object if this claim references a source
        src = None
        if c.get("source_ref"):
            src = Source(
                source_type="tavily",
                reference_id=c["source_ref"],
                excerpt=c["reason"][:200],
                confidence=0.9 if c["is_grounded"] else 0.0,
            )

        # Build verification record for this claim
        verifications.append(ClaimVerification(
            claim=c["claim"],
            is_grounded=c["is_grounded"],
            supporting_source=src,
            reason=c["reason"],
        ))

    # Calculate aggregate groundedness score
    grounded = sum(1 for v in verifications if v.is_grounded)
    score = grounded / len(verifications)
    ungrounded = [v.claim for v in verifications if not v.is_grounded]

    # Determine verdict and recommendation based on score thresholds
    if score >= warn:
        # High confidence: safe to proceed
        verdict = "pass"
        recommendation = "All claims adequately grounded. Proceed."
    elif score >= tripwire:
        # Marginal confidence: human review may help
        verdict = "warn"
        recommendation = f"Some claims weakly grounded (score={score:.2f}). Review before publishing."
    else:
        # Low confidence: must get human review
        verdict = "fail"
        recommendation = f"Score {score:.2f} below tripwire {tripwire}. Human review required."

    # Update session context with score for tracking
    ctx.context.groundedness_score = score

    return GroundednessReport(
        score=score,
        claim_verifications=verifications,
        ungrounded_claims=ungrounded,
        verdict=verdict,
        recommendation=recommendation,
    )


# Export function as tool for agent use
extract_and_verify_claims = function_tool(_extract_and_verify_claims_fn, strict_mode=False)
