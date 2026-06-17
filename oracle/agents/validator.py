"""
VALIDATOR Groundedness Guardrail - Answer Confidence Checking

The VALIDATOR module implements output validation to ensure agent responses are grounded
in provided sources and factually accurate.

Groundedness Checking Flow:
  1. Extract factual claims from agent's answer
  2. For each claim: check if it is supported by sources
  3. Calculate aggregate grounded percentage (score 0.0-1.0)
  4. Apply thresholds:
     - Score >= 0.85: PASS (high confidence, no review needed)
     - Score 0.70-0.85: WARN (marginal confidence, human review may help)
     - Score < 0.70: FAIL (low confidence, HITL required)

Thresholds:
  - GROUNDEDNESS_TRIPWIRE_THRESHOLD: 0.70 (default) - minimum acceptable score
  - GROUNDEDNESS_WARN_THRESHOLD: 0.85 (default) - confident enough to skip HITL

When Score < 0.70:
  - validator_guardrail triggers tripwire
  - OutputGuardrailTripwireTriggered exception raised
  - HITL panel activated with ungrounded claims highlighted

Uses GPT-4o for semantic claim verification against sources via JSON classification.
"""

import os
import json
from agents import (
    Agent, RunContextWrapper, GuardrailFunctionOutput, output_guardrail,
)
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


def _run_groundedness_check(answer_text: str, sources: list[dict]) -> GroundednessReport:
    """
    Verify that answer claims are supported by provided sources using semantic analysis.

    Algorithm:
      1. Use GPT-4o to extract factual claims from the answer
      2. For each claim, check if it's supported by sources (is_grounded)
      3. Calculate score: (grounded_claims / total_claims)
      4. Apply verdicts based on score and thresholds
      5. Track ungrounded claims for user review

    Score Interpretation:
      - 1.0: All claims are grounded in sources
      - 0.85+: Highly grounded, safe to show
      - 0.70-0.85: Marginal grounding, human review recommended
      - <0.70: Low confidence, HITL activation required

    Args:
        answer_text (str): The agent's answer to verify
        sources (list[dict]): List of source dicts from search/tools (e.g., Tavily results)

    Returns:
        GroundednessReport: Contains:
          - score (0.0-1.0): Percentage of grounded claims
          - verdict: "pass" (>=0.85), "warn" (0.70-0.85), "fail" (<0.70)
          - claim_verifications: Per-claim analysis with sources
          - ungrounded_claims: List of claims lacking support
          - recommendation: Human-readable guidance
    """
    # Load thresholds from environment with sensible defaults
    tripwire = float(os.environ.get("GROUNDEDNESS_TRIPWIRE_THRESHOLD", "0.70"))
    warn_thresh = float(os.environ.get("GROUNDEDNESS_WARN_THRESHOLD", "0.85"))

    client = _get_openai()

    # Truncate sources to first 2000 chars to keep prompt reasonable
    sources_str = json.dumps(sources, indent=1)[:2000]

    # System prompt for GPT-4o: act as groundedness critic
    system = (
        "You are a groundedness critic. Identify each factual claim in the answer "
        "and verify if it is supported by the sources. "
        "Respond ONLY with valid JSON: "
        "{\"claims\": [{\"claim\": str, \"is_grounded\": bool, \"reason\": str, \"source_ref\": str|null}]}"
    )

    # Call GPT-4o for semantic claim verification
    response = client.chat.completions.create(
        model=os.environ.get("OPENAI_DEFAULT_MODEL", "gpt-4o"),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"ANSWER:\n{answer_text}\n\nSOURCES:\n{sources_str}"},
        ],
        response_format={"type": "json_object"},
        max_tokens=800,
    )

    # Parse claim verification response
    data = json.loads(response.choices[0].message.content)
    claims_raw = data.get("claims", [])

    # Edge case: answer has no verifiable claims (e.g., greeting)
    if not claims_raw:
        return GroundednessReport(
            score=1.0, verdict="pass",
            recommendation="No verifiable claims — auto-pass.",
        )

    # Build ClaimVerification objects with source references
    verifications = []
    for c in claims_raw:
        # Create Source object if this claim references a source
        src = None
        if c.get("source_ref"):
            src = Source(
                source_type="tavily",
                reference_id=c["source_ref"],
                excerpt=c.get("reason", "")[:200],
                confidence=0.9 if c["is_grounded"] else 0.1,
            )

        # Build verification record for this claim
        verifications.append(ClaimVerification(
            claim=c["claim"],
            is_grounded=c["is_grounded"],
            supporting_source=src,
            reason=c.get("reason", ""),
        ))

    # Calculate aggregate groundedness score
    grounded = sum(1 for v in verifications if v.is_grounded)
    score = grounded / len(verifications)
    ungrounded = [v.claim for v in verifications if not v.is_grounded]

    # Determine verdict and recommendation based on score thresholds
    if score >= warn_thresh:
        # High confidence: safe to proceed without review
        verdict, rec = "pass", "Proceed."
    elif score >= tripwire:
        # Marginal confidence: human review may help but not required
        verdict, rec = "warn", f"Score {score:.2f} — review ungrounded claims."
    else:
        # Low confidence: must trigger HITL for human review
        verdict, rec = "fail", f"Score {score:.2f} below tripwire — HITL required."

    return GroundednessReport(
        score=score,
        claim_verifications=verifications,
        ungrounded_claims=ungrounded,
        verdict=verdict,
        recommendation=rec,
    )


@output_guardrail
async def validator_guardrail(
    ctx: RunContextWrapper[OracleSessionContext],
    agent,
    output,
) -> GuardrailFunctionOutput:
    """
    Validate answer groundedness and trigger HITL if confidence is low.

    This output guardrail is applied AFTER Conductor completes execution.
    It checks if the answer's claims are supported by the sources provided.

    Tripwire Logic:
      - Triggers (requests HITL) if: groundedness_score < TRIPWIRE_THRESHOLD (default 0.70)
      - Allows (shows response) if: groundedness_score >= TRIPWIRE_THRESHOLD
      - Always stores score in context for HITL metadata

    When tripwire triggers:
      - OutputGuardrailTripwireTriggered exception raised
      - ORACLE Engine catches and activates HITL panel
      - User sees: "⚠️ This response requires human review before being shown"
      - Human can approve, edit+approve, or regenerate the response

    Validation Steps:
      1. Extract answer and sources from ConductorResponse
      2. Run groundedness check (claims vs sources)
      3. Store score in session context for HITL metadata
      4. Return GuardrailFunctionOutput with tripwire status

    Args:
        ctx (RunContextWrapper): Session context - score stored in ctx.context.groundedness_score
        agent: The Conductor agent whose output is being validated
        output: Conductor's output (usually has .final_output with ConductorResponse)

    Returns:
        GuardrailFunctionOutput: Contains GroundednessReport and tripwire status
    """
    # Load tripwire threshold from environment
    tripwire = float(os.environ.get("GROUNDEDNESS_TRIPWIRE_THRESHOLD", "0.70"))

    # Extract output from nested structure (RunResult.final_output wrapper)
    conductor_output = output.final_output if hasattr(output, "final_output") else output

    # Extract answer and sources from ConductorResponse object
    if hasattr(conductor_output, "answer"):
        answer_text = conductor_output.answer
        # Convert Source objects to dicts for groundedness check
        sources_dicts = [s.model_dump() for s in conductor_output.sources]
    else:
        # Fallback for non-structured output
        answer_text = str(conductor_output)
        sources_dicts = []

    # Run groundedness verification against sources
    report = _run_groundedness_check(answer_text, sources_dicts)

    # Store score in session context for HITL tracking and metrics
    ctx.context.groundedness_score = report.score

    # Determine if tripwire should trigger based on groundedness verdict
    should_trip = report.verdict == "fail"

    # If tripwire triggers: set HITL pending flags for ORACLE Engine to detect
    if should_trip:
        ctx.context.hitl_pending = True
        ctx.context.hitl_draft_answer = answer_text

    return GuardrailFunctionOutput(
        output_info=report,
        tripwire_triggered=should_trip,
    )


# Initialize the VALIDATOR agent for reference/on-demand use
# (Actual validation happens via validator_guardrail function above)
validator_agent = Agent(
    name="VALIDATOR",
    model=os.environ.get("OPENAI_DEFAULT_MODEL", "gpt-4o"),
    instructions=open(
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts", "validator.md")
    ).read(),
    output_type=GroundednessReport,
)

# Export validator as a tool that agents can call for on-demand re-validation
# Useful if Conductor wants to double-check groundedness of a specific claim
validator_as_tool = validator_agent.as_tool(
    tool_name="validate_groundedness",
    tool_description="Re-validate answer groundedness against source chunks.",
)
