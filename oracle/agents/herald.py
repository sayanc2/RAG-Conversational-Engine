"""
HERALD Agent - Weather and News Specialist

HERALD is a specialist agent that handles weather forecasts, real-time news, and live location data.
It is invoked via handoff when the Conductor determines a query is primarily about:
  - Weather conditions, forecasts, severe weather
  - News and current events
  - Live location-based data (traffic, transit, etc.)

Capabilities:
  - Fetch real-time weather forecasts via Tavily API
  - Search current news articles via Tavily API
  - Embed query context into Chroma vector database
  - Retrieve similar context for multi-turn conversations
  - Tag results with source (weather, news, live) for traceability

Invocation Methods:
  1. HANDOFF: Conductor hands off when query is purely weather/news
  2. TOOL: Conductor calls fetch_live_context tool for blended queries (e.g., "weather + employee location")

Response Format: WeatherNewsResult (contains weather, news articles, sources)

Context Tracking:
  - Stores last_queried_location in session for follow-up queries
  - Embeds context for semantic search across turns
"""

import os
from agents import Agent, handoff, RunContextWrapper

from oracle.models import OracleSessionContext, WeatherNewsResult, HeraldHandoffInput
from oracle.tools.tavily_tools import tavily_news_search, tavily_weather_fetch
from oracle.tools.chroma_tools import embed_and_store_live_context, chroma_similarity_search


def _on_herald_handoff(ctx: RunContextWrapper[OracleSessionContext], input_data: HeraldHandoffInput):
    """
    Called when Conductor hands off to HERALD agent.

    Updates session context to track the location hint for follow-up queries.
    Enables contextual understanding across multiple turns.

    Args:
        ctx (RunContextWrapper): Session context to update
        input_data (HeraldHandoffInput): Handoff payload containing location_hint
    """
    # Store location hint for follow-up queries ("What's the weather tomorrow?" → remember the location)
    if input_data.location_hint:
        ctx.context.last_queried_location = input_data.location_hint


# Initialize HERALD weather/news specialist agent
herald_agent = Agent(
    name="HERALD",
    model=os.environ.get("PRIMARY_MODEL", "claude-sonnet-4-5"),

    # Load detailed reasoning instructions for weather/news queries
    instructions=open(
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts", "herald.md")
    ).read(),

    # Tools for fetching live data and managing context
    # - tavily_weather_fetch: Real-time weather API calls
    # - tavily_news_search: Current news article search
    # - embed_and_store_live_context: Store query context in vector DB
    # - chroma_similarity_search: Retrieve similar context for follow-ups
    tools=[
        tavily_weather_fetch,
        tavily_news_search,
        embed_and_store_live_context,
        chroma_similarity_search,
    ],

    # Structured response format for weather/news results
    output_type=WeatherNewsResult,

    # Description shown in Conductor's routing decision log
    handoff_description=(
        "HERALD specializes in live weather and news. "
        "Hand off here for pure weather queries, news searches, or location-based live data."
    ),
)

# HANDOFF configuration: Route from Conductor to HERALD for pure weather/news queries
handoff_to_herald = handoff(
    agent=herald_agent,
    input_type=HeraldHandoffInput,
    on_handoff=_on_herald_handoff,
    tool_name_override="escalate_to_herald",
    tool_description_override=(
        "Escalate to HERALD for pure weather or news queries. "
        "Provide the query and optional location_hint."
    ),
)

# TOOL configuration: Call HERALD as tool for blended queries
# Example: "What's the weather at John Smith's location?" (needs both employee + weather data)
herald_as_tool = herald_agent.as_tool(
    tool_name="fetch_live_context",
    tool_description=(
        "Fetch live weather and news for a location. "
        "Use for blended queries that need both employee and weather data."
    ),
)
