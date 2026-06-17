"""
ORACLE Conductor Agent - Main Query Orchestrator

The Conductor is the primary agent that receives user queries and coordinates the multi-agent
response generation pipeline. It is responsible for:

1. Understanding user intent and query classification
2. Routing to specialist agents (HERALD for weather/news, ARCHIVIST for employee data)
3. Executing specialized tools as needed (SQL queries, web searches, document retrieval)
4. Aggregating results from multiple sources
5. Generating a comprehensive, well-sourced answer

Guardrails Applied:
  - Input: SENTINEL checks for security threats (prompt injection, off-topic, PII requests)
  - Output: SENTINEL validates for data leaks; VALIDATOR checks answer groundedness (must be >= 0.70)

Response Format: ConductorResponse (contains answer, sources, confidence, and control flags)

Lifecycle:
  - Starts with user query processed by OracleEngine.run()
  - Applies input security checks via SENTINEL guardrail
  - Executes tools or hands off to specialists
  - Outputs ConductorResponse structure
  - Undergoes output validation (SENTINEL for PII, VALIDATOR for groundedness)
  - May trigger HITL if confidence is low or PII detected
"""

import os
from agents import Agent

from oracle.models import OracleSessionContext, ConductorResponse
from oracle.agents.herald import handoff_to_herald, herald_as_tool
from oracle.agents.archivist import handoff_to_archivist, archivist_as_tool
from oracle.agents.sentinel import sentinel_input_guardrail, sentinel_output_guardrail
from oracle.agents.validator import validator_guardrail
from oracle.agents.hooks import OracleAgentHooks


# Initialize the Conductor agent with full orchestration capabilities
conductor_agent = Agent(
    # Agent identifier and primary model configuration
    name="ORACLE Conductor",
    model=os.environ.get("PRIMARY_MODEL", "claude-sonnet-4-5"),

    # Load system instructions from conductor.md prompt template
    # This file contains detailed reasoning patterns and decision trees for routing queries
    instructions=open(
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts", "conductor.md")
    ).read(),

    # Tools available to Conductor for direct execution
    # - herald_as_tool: Query weather/news APIs
    # - archivist_as_tool: Query employee database
    tools=[herald_as_tool, archivist_as_tool],

    # Handoff routes for escalating queries to specialist agents
    # - handoff_to_herald: For weather/news focused queries
    # - handoff_to_archivist: For employee/HR focused queries
    handoffs=[handoff_to_herald, handoff_to_archivist],

    # Structured response format ensures consistent output schema
    # Contains: answer (str), sources (list), confidence (float), hitl_required (bool)
    output_type=ConductorResponse,

    # Input security checks: Detect prompt injections, off-topic queries, PII extraction attempts
    input_guardrails=[sentinel_input_guardrail],

    # Output validation: Check for PII leaks and verify answer groundedness score >= 0.70
    # If any check fails, tripwire is triggered and HITL activation is requested
    output_guardrails=[sentinel_output_guardrail, validator_guardrail],

    # Agent-level lifecycle tracking for debugging and metrics collection
    hooks=OracleAgentHooks(),
)
