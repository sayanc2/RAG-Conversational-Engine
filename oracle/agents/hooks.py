"""
ORACLE Hooks System - Lifecycle Tracking

This module implements three-tier hook systems for comprehensive observability:
  1. Agent-level hooks: Individual agent lifecycle events
  2. Run-level hooks: Multi-agent pipeline execution tracking
  3. HITL-level hooks: Human-in-the-loop lifecycle and metrics

Hooks are called by the OpenAI Agents SDK at strategic points during query execution,
enabling detailed logging, metrics collection, and audit trails.
"""

import logging
import time
from datetime import datetime
from agents import AgentHooks, RunHooks, RunContextWrapper, Tool, Agent
from oracle.models import OracleSessionContext

logger = logging.getLogger("oracle.hooks")


class OracleAgentHooks(AgentHooks):
    """
    Agent-level lifecycle hooks for individual agent execution tracking.

    These hooks fire for each agent in the pipeline and track:
      - Agent start/end (with HITL awareness)
      - Tool invocations within agents
      - Handoffs between agents

    This provides fine-grained visibility into each agent's execution,
    useful for debugging and performance analysis.
    """

    async def on_start(self, ctx: RunContextWrapper, agent: Agent) -> None:
        """
        Called when an agent begins execution in the pipeline.

        Logs the agent name and turn number for tracking query progression.
        Also warns if HITL is already pending from a previous agent
        (indicates human review may override this agent's output).
        """
        logger.info(f"[AGENT START] {agent.name} | turn={ctx.context.turn_count}")
        if ctx.context.hitl_pending:
            logger.warning(f"[AGENT START] {agent.name} invoked while HITL pending (review may override output)")

    async def on_end(self, ctx: RunContextWrapper, agent: Agent, output) -> None:
        """
        Called when an agent completes execution.

        Logs the output type (e.g., ConductorResponse, WeatherNewsResult).
        Warns if this agent's output triggered HITL (groundedness check failed).
        """
        logger.info(f"[AGENT END]   {agent.name} | output_type={type(output).__name__}")
        if ctx.context.hitl_pending:
            logger.warning(f"[AGENT END] {agent.name} output flagged for HITL review")

    async def on_tool_start(self, ctx: RunContextWrapper, agent: Agent, tool: Tool) -> None:
        """
        Called when an agent invokes a tool (e.g., SQL query, Tavily API call).

        Logs which agent is calling which tool for detailed execution tracing.
        Useful for understanding query branching (which tools are used for this query?).
        """
        logger.info(f"[TOOL START]  {agent.name} -> {tool.name}")

    async def on_tool_end(self, ctx: RunContextWrapper, agent: Agent, tool: Tool, result) -> None:
        """
        Called when a tool returns its result.

        Logs tool result (first 120 chars for brevity).
        Helps identify tool failures or unexpected return types.
        """
        preview = str(result)[:120] if result else "None"
        logger.info(f"[TOOL END]    {agent.name} -> {tool.name} | result={preview}")

    async def on_handoff(self, ctx: RunContextWrapper, from_agent: Agent, to_agent: Agent) -> None:
        """
        Called when one agent hands off to another (e.g., Conductor to HERALD).

        Logs the handoff transition for understanding query routing decisions.
        Used by Conductor to escalate pure-domain queries to specialists.
        """
        logger.info(f"[HANDOFF]     {from_agent.name} -> {to_agent.name}")


class OracleRunHooks(RunHooks):
    """
    Run-level lifecycle hooks for full pipeline execution tracking.

    These hooks fire at higher-level points in the multi-agent orchestration:
      - Pipeline start/end
      - HITL trigger detection
      - Total elapsed time

    Tracks the overall query execution performance and when (if any) HITL was triggered.
    Used for performance monitoring and analytics.

    Attributes:
        _start_time (float): When the pipeline started (for elapsed time calculation)
        _hitl_triggered_at (str): ISO timestamp when HITL was activated (or None)
        _hitl_triggered_by_agent (str): Which agent triggered HITL (e.g., "VALIDATOR")
    """

    def __init__(self):
        """Initialize run tracking state."""
        self._start_time = None
        self._hitl_triggered_at = None
        self._hitl_triggered_by_agent = None

    async def on_agent_start(self, ctx: RunContextWrapper, agent: Agent) -> None:
        """
        Called when first agent starts pipeline execution.

        Records start time for elapsed calculation.
        Only fires once per run (when _start_time is None).
        """
        if self._start_time is None:
            self._start_time = time.time()
        logger.info(f"[RUN] Agent started: {agent.name}")

    async def on_agent_end(self, ctx: RunContextWrapper, agent: Agent, output) -> None:
        """
        Called when an agent completes in the pipeline.

        Tracks total elapsed time since pipeline start.
        Detects HITL activation: if ctx.hitl_pending just became True,
        records timestamp and triggering agent name.

        This is the key hook that detects when HITL gets triggered mid-pipeline.
        """
        # Calculate elapsed time since pipeline start
        elapsed = round(time.time() - self._start_time, 2) if self._start_time else 0

        # HITL lifecycle tracking: detect when validation tripwire fires
        if ctx.context.hitl_pending and not self._hitl_triggered_at:
            # Record HITL activation with timestamp and source agent
            self._hitl_triggered_at = datetime.now().isoformat()
            self._hitl_triggered_by_agent = agent.name
            logger.warning(
                f"[HITL TRIGGERED] Agent: {agent.name} | "
                f"Score: {ctx.context.groundedness_score:.2f} | "
                f"Time: {self._hitl_triggered_at}"
            )

        logger.info(f"[RUN] Agent ended: {agent.name} | elapsed={elapsed}s " +
                   (f"| HITL_PENDING" if ctx.context.hitl_pending else ""))

    async def on_tool_start(self, ctx: RunContextWrapper, agent: Agent, tool: Tool) -> None:
        """
        Called when a tool is invoked during pipeline.

        Debug-level logging for detailed execution traces.
        """
        logger.debug(f"[RUN TOOL]    {tool.name}")

    async def on_tool_end(self, ctx: RunContextWrapper, agent: Agent, tool: Tool, result) -> None:
        """
        Called when a tool completes during pipeline.

        Debug-level logging for detailed execution traces.
        """
        logger.debug(f"[RUN TOOL]    {tool.name} complete")

    async def on_handoff(self, ctx: RunContextWrapper, from_agent: Agent, to_agent: Agent) -> None:
        """
        Called when one agent hands off to another during pipeline.

        Logs inter-agent handoffs for understanding query routing.
        Example: Conductor hands off to HERALD for weather-only queries.
        """
        logger.info(f"[RUN HANDOFF] {from_agent.name} -> {to_agent.name}")

    def get_hitl_metadata(self) -> dict:
        """
        Return HITL lifecycle metadata captured during this pipeline execution.

        Called at end of execution to gather metrics for session tracking.

        Returns:
            dict: Contains:
              - hitl_triggered (bool): Whether HITL was activated
              - hitl_triggered_at (str | None): ISO timestamp of activation
              - hitl_triggered_by_agent (str | None): Agent name that triggered it
        """
        return {
            "hitl_triggered": self._hitl_triggered_at is not None,
            "hitl_triggered_at": self._hitl_triggered_at,
            "hitl_triggered_by_agent": self._hitl_triggered_by_agent,
        }


class OracleHITLHooks:
    """
    Specialized hooks for Human-In-The-Loop (HITL) workflow lifecycle events.

    Tracks the complete HITL journey:
      1. Panel activation (triggered)
      2. Human decision (approved/rejected/timeout)
      3. Review metrics (time spent, action taken)

    This hook system enables compliance logging and HITL analytics.

    Attributes:
        _review_start_time (float): When human review started (for duration calc)
        _review_end_time (float): When human made decision (for duration calc)
        _human_action (str): Decision made ("approved" | "rejected" | "timeout" | None)
    """

    def __init__(self):
        """Initialize HITL review tracking."""
        self._review_start_time = None
        self._review_end_time = None
        self._human_action = None

    async def on_hitl_triggered(
        self,
        ctx: OracleSessionContext,
        reason: str,
        draft_answer: str,
        groundedness_score: float,
    ) -> None:
        """
        Called when HITL panel is activated in Streamlit UI.

        Fires when validator score < 0.70 OR conductor flags sensitive PII.
        Marks the start of human review window.
        Logs reason, groundedness score, and draft answer (first 200 chars).

        Args:
            ctx (OracleSessionContext): Session with HITL state
            reason (str): Why HITL was triggered ("Validator" or "Conductor")
            draft_answer (str): The answer awaiting human review
            groundedness_score (float): Confidence score (0.0-1.0)
        """
        logger.warning(
            f"[HITL PANEL ACTIVATED] "
            f"Session: {ctx.session_id[:8]} | "
            f"Turn: {ctx.turn_count} | "
            f"Reason: {reason} | "
            f"Score: {groundedness_score:.2f}"
        )
        logger.debug(f"[HITL DRAFT] {draft_answer[:200]}…")
        # Start timer for review duration metric
        self._review_start_time = time.time()

    async def on_hitl_approved(
        self,
        ctx: OracleSessionContext,
        final_answer: str,
        was_edited: bool,
        groundedness_score: float,
    ) -> None:
        """
        Called when human clicks "Approve" or "Edit & Approve" button.

        Records the approval decision, review duration, and whether human edited the answer.
        Used for compliance auditing and HITL effectiveness metrics.

        Args:
            ctx (OracleSessionContext): Session with final decision
            final_answer (str): The answer as approved (may be edited)
            was_edited (bool): True if human modified answer before approving
            groundedness_score (float): Original groundedness score
        """
        # Calculate time human spent reviewing
        review_duration = round(time.time() - self._review_start_time, 2) if self._review_start_time else 0
        edit_indicator = " (EDITED)" if was_edited else ""

        logger.warning(
            f"[HITL APPROVED{edit_indicator}] "
            f"Session: {ctx.session_id[:8]} | "
            f"Turn: {ctx.turn_count} | "
            f"Review time: {review_duration}s | "
            f"Score: {groundedness_score:.2f}"
        )
        # Record decision and end time
        self._human_action = "approved"
        self._review_end_time = time.time()

    async def on_hitl_rejected(
        self,
        ctx: OracleSessionContext,
        reason: str,
        groundedness_score: float,
    ) -> None:
        """
        Called when human clicks "Regenerate" button.

        Records the rejection decision and human's reasoning.
        Query will be re-run with rejection context.

        Args:
            ctx (OracleSessionContext): Session with rejection state
            reason (str): Human-provided reason for rejection
            groundedness_score (float): Score of rejected answer
        """
        # Calculate time human spent reviewing
        review_duration = round(time.time() - self._review_start_time, 2) if self._review_start_time else 0

        logger.warning(
            f"[HITL REJECTED] "
            f"Session: {ctx.session_id[:8]} | "
            f"Turn: {ctx.turn_count} | "
            f"Review time: {review_duration}s | "
            f"Reason: {reason} | "
            f"Score: {groundedness_score:.2f}"
        )
        # Record decision and end time
        self._human_action = "rejected"
        self._review_end_time = time.time()

    async def on_hitl_timeout(
        self,
        ctx: OracleSessionContext,
        timeout_seconds: int,
    ) -> None:
        """
        Called if HITL review window expires without human action (Phase 2).

        Phase 2 feature for auto-rejection after timeout period.

        Args:
            ctx (OracleSessionContext): Session that timed out
            timeout_seconds (int): The timeout threshold (e.g., 300 seconds)
        """
        logger.warning(
            f"[HITL TIMEOUT] "
            f"Session: {ctx.session_id[:8]} | "
            f"Turn: {ctx.turn_count} | "
            f"Timeout: {timeout_seconds}s"
        )
        # Record timeout as the action taken
        self._human_action = "timeout"

    def get_review_metrics(self) -> dict:
        """
        Return aggregate HITL review metrics for this pipeline execution.

        Called at end of run to capture HITL lifecycle data.

        Returns:
            dict: Contains:
              - human_action: "approved" | "rejected" | "timeout" | None
              - review_duration_seconds: seconds human spent reviewing (or None)
              - review_start_time: Unix timestamp when review started
              - review_end_time: Unix timestamp when review ended
        """
        # Calculate review duration if human made a decision
        review_duration = None
        if self._review_start_time and self._review_end_time:
            review_duration = round(self._review_end_time - self._review_start_time, 2)

        return {
            "human_action": self._human_action,
            "review_duration_seconds": review_duration,
            "review_start_time": self._review_start_time,
            "review_end_time": self._review_end_time,
        }
