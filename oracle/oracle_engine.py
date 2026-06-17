"""
ORACLE Engine - Core Orchestration Module

This module contains the main coordination logic for ORACLE's query execution pipeline.
It manages the flow from user query → agent processing → guardrail validation → HITL feedback.

Key Responsibilities:
  - Orchestrate multi-agent query execution via OpenAI Agents SDK
  - Manage exception handling and graceful degradation
  - Track Human-In-The-Loop (HITL) lifecycle events
  - Persist session state across turns
  - Capture metrics and audit trails
"""

import os
import logging
from typing import Optional

from agents import (
    Runner, RunConfig,
    InputGuardrailTripwireTriggered,
    OutputGuardrailTripwireTriggered,
    MaxTurnsExceeded,
)

from oracle.models import OracleSessionContext, ConductorResponse, ConversationTurn
from oracle.agents.conductor import conductor_agent
from oracle.agents.hooks import OracleRunHooks, OracleHITLHooks

logger = logging.getLogger("oracle.engine")


def _build_run_config() -> RunConfig:
    """
    Factory function to create RunConfig for agent orchestration.

    The RunConfig specifies:
      - workflow_name: Identifier for this orchestration session
      - model: Fallback LLM (Claude fails over to GPT-4o)
      - trace_include_sensitive_data: False for privacy (never log API keys)
      - tracing_disabled: False to enable full tracing for debugging

    Returns:
        RunConfig: Configuration for OpenAI Agents SDK Runner
    """
    return RunConfig(
        workflow_name="oracle_rag_session",
        model=os.environ.get("OPENAI_DEFAULT_MODEL", "gpt-4o"),
        trace_include_sensitive_data=False,
        tracing_disabled=False,
    )


class OracleEngine:
    """
    Main orchestration engine for ORACLE query execution.

    Manages the complete lifecycle of a user query:
      1. Input validation (SENTINEL: security check)
      2. Agent orchestration (Conductor + specialists)
      3. Output validation (SENTINEL: PII check, VALIDATOR: groundedness)
      4. Human-in-the-loop (if confidence < 70%)
      5. Response delivery

    Attributes:
        _run_hooks (OracleRunHooks): Tracks agent execution lifecycle events
        _hitl_hooks (OracleHITLHooks): Tracks human review decisions and metrics
    """

    def __init__(self):
        """Initialize ORACLE Engine with lifecycle tracking hooks."""
        self._run_hooks = OracleRunHooks()
        self._hitl_hooks = OracleHITLHooks()

    async def run(
        self,
        user_query: str,
        ctx: OracleSessionContext,
    ) -> dict:
        """
        Execute one turn of the ORACLE conversational pipeline.

        This is the main entry point for processing user queries. It orchestrates:
          - Agent selection and execution
          - Exception handling and guardrail triggers
          - HITL activation if needed
          - Metrics and audit trail capture

        Args:
            user_query (str): The user's natural language question
            ctx (OracleSessionContext): Session state including conversation history

        Returns:
            dict: Result object containing:
              - answer (str): Final answer or error message
              - response (ConductorResponse | None): Structured agent response
              - error (str | None): Error type if exception occurred
              - hitl_triggered (bool): Whether human review was activated
              - security_blocked (bool): Whether SENTINEL rejected input
              - groundedness_score (float | None): VALIDATOR confidence (0.0-1.0)
              - hitl_metadata (dict): Lifecycle tracking data
        """
        ctx.turn_count += 1
        ctx.conversation_history.append(
            ConversationTurn(role="user", content=user_query)
        )

        result_dict = {
            "answer": "",
            "response": None,
            "error": None,
            "hitl_triggered": False,
            "security_blocked": False,
            "groundedness_score": None,
            "hitl_metadata": None,
        }

        try:
            # Execute the multi-agent orchestration pipeline
            # Runner.run() handles:
            #   - Routing to Conductor agent
            #   - Executing specialized agents (HERALD, ARCHIVIST) via tools
            #   - Applying guardrails (SENTINEL input, VALIDATOR output)
            #   - Managing handoffs between agents
            result = await Runner.run(
                starting_agent=conductor_agent,
                input=user_query,
                context=ctx,
                run_config=_build_run_config(),
                max_turns=int(os.environ.get("MAX_TURNS", "15")),
                hooks=self._run_hooks,
            )

            # Extract and process the final agent output
            output = result.final_output
            if isinstance(output, ConductorResponse):
                # Structured response from Conductor: extract answer and metadata
                answer = output.answer
                result_dict["response"] = output
                result_dict["groundedness_score"] = ctx.groundedness_score

                # Check if Conductor flagged this as needing human review (e.g., sensitive PII)
                if output.hitl_required:
                    result_dict["hitl_triggered"] = True
                    ctx.hitl_pending = True
                    ctx.hitl_draft_answer = answer
                    # Fire HITL hook to track that human review was triggered by conductor
                    await self._hitl_hooks.on_hitl_triggered(
                        ctx, "Conductor flagged sensitive PII context",
                        answer, ctx.groundedness_score or 0.0
                    )
            else:
                # Fallback: convert non-structured output to string
                answer = str(output)

            # Store assistant response in conversation history
            result_dict["answer"] = answer
            ctx.conversation_history.append(
                ConversationTurn(role="assistant", content=answer, agent_name="ORACLE Conductor")
            )

        except InputGuardrailTripwireTriggered as e:
            # SENTINEL input guardrail detected a security threat
            # (prompt injection, off-topic, PII extraction attempt, etc.)
            logger.warning(f"Input guardrail triggered: {e}")
            msg = (
                "I'm unable to process that request. "
                "It appears to violate safety guidelines. "
                "Please rephrase your query."
            )
            result_dict["answer"] = msg
            result_dict["security_blocked"] = True
            ctx.conversation_history.append(
                ConversationTurn(role="assistant", content=msg, agent_name="SENTINEL")
            )

        except OutputGuardrailTripwireTriggered as e:
            # VALIDATOR output guardrail detected low groundedness (score < 0.70)
            # Activate human-in-the-loop for review
            logger.warning(f"Output guardrail triggered: {e}")
            ctx.hitl_pending = True
            result_dict["hitl_triggered"] = True
            result_dict["groundedness_score"] = ctx.groundedness_score

            # Fire HITL hook to track that human review was triggered by validator
            await self._hitl_hooks.on_hitl_triggered(
                ctx, "Validator groundedness check failed",
                ctx.hitl_draft_answer or "(no draft)",
                ctx.groundedness_score or 0.0
            )

            result_dict["answer"] = (
                "⚠️ This response requires human review before being shown. "
                "Please use the review panel below."
            )

        except MaxTurnsExceeded:
            # Agent reasoning exceeded maximum turn limit (default: 15 turns)
            # Return graceful degradation message
            logger.error("Max turns exceeded")
            result_dict["answer"] = (
                "I reached the maximum reasoning depth for this query. "
                "Please try a simpler or more specific question."
            )
            result_dict["error"] = "MaxTurnsExceeded"

        except Exception as e:
            # Catch-all for unexpected errors (API failures, network issues, etc.)
            # Log full traceback for debugging
            logger.exception(f"Unexpected error in oracle_engine: {e}")
            result_dict["answer"] = (
                "An unexpected error occurred. Please try again."
            )
            result_dict["error"] = str(e)

        # Capture HITL lifecycle metrics from both hook systems
        result_dict["hitl_metadata"] = {
            **self._run_hooks.get_hitl_metadata(),
            **self._hitl_hooks.get_review_metrics(),
        }

        return result_dict

    async def process_hitl_approval(
        self,
        ctx: OracleSessionContext,
        final_answer: str,
        was_edited: bool,
    ) -> None:
        """
        Process human approval of a HITL-flagged answer.

        Called when user clicks "Approve" or "Edit & Approve" in the HITL panel.
        Fires the on_hitl_approved hook to track the human decision and review time.

        Args:
            ctx (OracleSessionContext): Session context with HITL state
            final_answer (str): The answer as approved (or edited) by human
            was_edited (bool): Whether human modified the answer before approving
        """
        # Fire hook to log approval event with metrics
        await self._hitl_hooks.on_hitl_approved(
            ctx, final_answer, was_edited,
            ctx.groundedness_score or 0.0
        )
        # Clear HITL state: answer approved, ready for delivery
        ctx.hitl_pending = False
        ctx.hitl_draft_answer = None

    async def process_hitl_rejection(
        self,
        ctx: OracleSessionContext,
        reason: str,
    ) -> None:
        """
        Process human rejection of a HITL-flagged answer.

        Called when user clicks "Regenerate" in the HITL panel.
        Fires the on_hitl_rejected hook to track the rejection and review time.
        The query will be re-run with rejection context prepended.

        Args:
            ctx (OracleSessionContext): Session context with HITL state
            reason (str): Human-provided reason for rejection
        """
        # Fire hook to log rejection event with metrics
        await self._hitl_hooks.on_hitl_rejected(
            ctx, reason,
            ctx.groundedness_score or 0.0
        )
        # Clear HITL state: query will be re-run
        ctx.hitl_pending = False
        ctx.hitl_draft_answer = None


# Singleton instance of OracleEngine
_engine_instance: Optional[OracleEngine] = None


def get_engine() -> OracleEngine:
    """
    Get or create the singleton OracleEngine instance.

    Uses lazy initialization to ensure only one engine exists for the session.
    Hooks are shared across all queries in the session.

    Returns:
        OracleEngine: The singleton engine instance
    """
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = OracleEngine()
    return _engine_instance
