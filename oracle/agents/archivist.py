"""
ARCHIVIST Agent - Employee Database Specialist

ARCHIVIST is a specialist agent that handles employee database queries including:
  - Employee lookups by name, ID, department
  - Department/team information
  - Office location and reporting structure
  - Employee-location mapping for context queries

It is invoked via handoff when the Conductor determines a query is primarily about employee/HR data.

Capabilities:
  - Query employee database via SQL tools
  - Map semantic location names to canonical office locations
  - Retrieve similar employee context from vector database
  - Tag results with data source (rows returned, matching criteria)

Invocation Methods:
  1. HANDOFF: Conductor hands off when query is purely employee-focused
  2. TOOL: Conductor calls lookup_employee_data tool for blended queries (e.g., "employee + weather")

Response Format: EmployeeQueryResult (contains employees, departments, query results)

Data Privacy:
  - Implements PII awareness for sensitive fields (email, phone, salary)
  - SENTINEL guardrail validates output to prevent accidental bulk exposure
  - VALIDATOR checks groundedness of claims about employee data
"""

import os
from agents import Agent, handoff, RunContextWrapper, HandoffInputData

from oracle.models import OracleSessionContext, EmployeeQueryResult, ArchivistHandoffInput
from oracle.tools.sql_tools import sql_query_employee, semantic_location_mapper
from oracle.tools.chroma_tools import chroma_similarity_search


def _on_archivist_handoff(
    ctx: RunContextWrapper[OracleSessionContext],
    input_data: ArchivistHandoffInput,
):
    """
    Called when Conductor hands off to ARCHIVIST agent.

    Updates session context to track the location hint for follow-up queries.
    Enables contextual understanding across multiple turns.

    Args:
        ctx (RunContextWrapper): Session context to update
        input_data (ArchivistHandoffInput): Handoff payload containing location_hint
    """
    # Store location hint for follow-up queries (e.g., "Are there any other employees there?")
    if input_data.location_hint:
        ctx.context.last_queried_location = input_data.location_hint


def _archivist_input_filter(data: HandoffInputData) -> HandoffInputData:
    """
    Filter conversation history before handing to ARCHIVIST.

    Removes weather-only turns from history to avoid noise when ARCHIVIST
    is processing a blended query. Reduces context bloat and improves focus.

    Example: In "What's the weather + where is John?", filters out prior weather queries
    from history so ARCHIVIST focuses on employee lookup context.

    Args:
        data (HandoffInputData): Original conversation history with metadata

    Returns:
        HandoffInputData: Filtered history with weather-only turns removed
    """
    filtered = []
    for item in data.input_history:
        # Extract text content from dict or string items
        if isinstance(item, dict):
            content = str(item.get("content", ""))
        else:
            content = str(item)

        # Detect weather-only turns by checking for weather-related keywords
        weather_only = any(w in content.lower() for w in ["temperature", "forecast", "tavily", "weather"])

        # Keep non-weather turns in the filtered history
        if not weather_only:
            filtered.append(item)

    return HandoffInputData(
        input_history=filtered,
        pre_handoff_items=data.pre_handoff_items,
        new_items=data.new_items,
    )


# Initialize ARCHIVIST employee database specialist agent
archivist_agent = Agent(
    name="ARCHIVIST",
    model=os.environ.get("PRIMARY_MODEL", "claude-sonnet-4-5"),

    # Load detailed reasoning instructions for employee queries
    instructions=open(
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts", "archivist.md")
    ).read(),

    # Tools for querying employee database and managing context
    # - sql_query_employee: Execute SQL queries for employee lookups
    # - semantic_location_mapper: Map location names to canonical office locations
    # - chroma_similarity_search: Retrieve similar employee context
    tools=[
        sql_query_employee,
        semantic_location_mapper,
        chroma_similarity_search,
    ],

    # Structured response format for employee query results
    output_type=EmployeeQueryResult,

    # Description shown in Conductor's routing decision log
    handoff_description=(
        "ARCHIVIST specializes in employee database queries. "
        "Hand off here for any query about employees, departments, or office locations."
    ),
)

# HANDOFF configuration: Route from Conductor to ARCHIVIST for employee queries
handoff_to_archivist = handoff(
    agent=archivist_agent,
    input_type=ArchivistHandoffInput,
    on_handoff=_on_archivist_handoff,
    input_filter=_archivist_input_filter,  # Remove weather noise from conversation history
    tool_name_override="escalate_to_archivist",
    tool_description_override=(
        "Escalate to ARCHIVIST for employee/HR queries. "
        "Provide query and optional name, department, location hints."
    ),
)

# TOOL configuration: Call ARCHIVIST as tool for blended queries
# Example: "What's the weather at John Smith's office?" (needs both employee location + weather)
archivist_as_tool = archivist_agent.as_tool(
    tool_name="lookup_employee_data",
    tool_description=(
        "Look up employee data from the database. "
        "Use for blended queries needing employee info alongside weather."
    ),
)
