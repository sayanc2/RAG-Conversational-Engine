"""
Tavily Tools - Live Weather and News API Integration

This module provides agents with tools to fetch live weather and news data using Tavily API.
Tavily provides real-time web search capabilities for current weather forecasts and news articles.

Tools Provided:
  1. tavily_weather_fetch: Get current weather for a location
  2. tavily_news_search: Search for live news articles

API Configuration:
  - API key via TAVILY_API_KEY environment variable
  - Retry logic for resilience (3 attempts with exponential backoff)
  - Search depth: "basic" (faster, sufficient for news/weather)

Rate Limiting:
  - Default: 5 results per weather query, 5 per news query
  - Configurable via max_results parameter
"""

import os
from datetime import datetime
from typing import Optional

from agents import function_tool, RunContextWrapper
from tenacity import retry, stop_after_attempt, wait_exponential

from oracle.models import OracleSessionContext, WeatherResult, NewsItem


def _get_tavily():
    """
    Get or create Tavily API client.

    Loads API key from environment variable TAVILY_API_KEY.
    Returns a configured TavilyClient for API calls.

    Returns:
        TavilyClient: Configured client for API calls
    """
    from tavily import TavilyClient
    return TavilyClient(api_key=os.environ.get("TAVILY_API_KEY", ""))


def _normalize_location(location: str) -> str:
    """
    Normalize location string for use as a canonical location key.

    Converts "San Francisco, CA" → "san_francisco_ca" for consistent storage.

    Args:
        location (str): Raw location string

    Returns:
        str: Normalized location (lowercase, underscores)
    """
    return location.lower().replace(", ", "_").replace(" ", "_")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
def _tavily_search(client, query: str, max_results: int) -> list[dict]:
    """
    Execute a Tavily search with retry logic.

    Retries up to 3 times with exponential backoff on failure.
    Uses "basic" search depth for speed and cost efficiency.

    Args:
        client: TavilyClient instance
        query (str): Search query string
        max_results (int): Maximum results to return

    Returns:
        list[dict]: List of search result dictionaries
    """
    response = client.search(query=query, max_results=max_results, search_depth="basic")
    return response.get("results", [])


def _tavily_news_search_fn(
    ctx: RunContextWrapper[OracleSessionContext],
    query: str,
    max_results: int = 5,
) -> list[NewsItem]:
    """
    Search for live news articles related to a query.

    Uses Tavily API to fetch current news articles matching the search query.
    Results include headline, summary, URL, and publication date.

    Args:
        ctx (RunContextWrapper): Session context (unused, for agent tool compatibility)
        query (str): News search query (e.g., "tech industry layoffs")
        max_results (int): Maximum articles to return (default: 5)

    Returns:
        list[NewsItem]: List of news articles with metadata
    """
    client = _get_tavily()
    # Execute search with retry logic
    results = _tavily_search(client, query, max_results)

    # Convert Tavily results to NewsItem models
    items = []
    for r in results:
        items.append(NewsItem(
            headline=r.get("title", ""),
            summary=r.get("content", "")[:500],  # Truncate to 500 chars
            url=r.get("url", ""),
            published_at=r.get("published_date"),
        ))
    return items


def _tavily_weather_fetch_fn(
    ctx: RunContextWrapper[OracleSessionContext],
    location: str,
) -> WeatherResult:
    """
    Fetch current weather conditions for a location.

    Uses Tavily API to search for current weather, temperature, and forecast information.
    Extracts temperature in Fahrenheit from search results using regex.

    Search Query:
      "current weather {location} temperature conditions forecast"

    Updates session context with queried location for follow-up queries.

    Args:
        ctx (RunContextWrapper): Session context to update with location
        location (str): Location to fetch weather for (e.g., "San Francisco, CA")

    Returns:
        WeatherResult: Current conditions, temperature, forecast, and fetch timestamp
    """
    client = _get_tavily()

    # Build natural language weather query
    query = f"current weather {location} temperature conditions forecast"
    # Execute search with retry logic
    results = _tavily_search(client, query, max_results=3)

    # Get best result (first/most relevant)
    best = results[0] if results else {}
    content = best.get("content", "")

    # Extract temperature in Fahrenheit using regex (e.g., "72 F", "72°F")
    temp_f: Optional[float] = None
    import re
    temp_match = re.search(r"(\d{2,3})\s*[°]?\s*F", content)
    if temp_match:
        temp_f = float(temp_match.group(1))

    # Update session context for follow-up queries ("What about tomorrow's weather?")
    ctx.context.last_queried_location = location

    return WeatherResult(
        location=location,
        normalized_location=_normalize_location(location),
        temperature_f=temp_f,
        conditions=content[:300] if content else "Data unavailable",  # First 300 chars: conditions
        forecast_summary=content[300:600] if len(content) > 300 else None,  # Next 300: forecast
        fetched_at=datetime.utcnow(),
        tavily_url=best.get("url", ""),
    )


# Export functions as tools for agent use
tavily_news_search = function_tool(_tavily_news_search_fn)
tavily_weather_fetch = function_tool(_tavily_weather_fetch_fn)
