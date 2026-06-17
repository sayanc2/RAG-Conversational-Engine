"""
Response Models - Agent Output Schemas

This module defines Pydantic models for structured responses from agents.
Ensures consistent output format across the ORACLE pipeline.

Models:
  1. Source - Individual source reference (where data came from)
  2. ConductorResponse - Main orchestrator output
  3. WeatherResult - Current weather data
  4. NewsItem - News article reference
  5. WeatherNewsResult - HERALD agent output
  6. HeraldHandoffInput - Handoff parameters for HERALD
"""

from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime


class Source(BaseModel):
    """
    Reference to a data source used in the answer.

    Tracks where information came from for traceability and validator groundedness checking.
    Used by VALIDATOR to verify claims are actually supported by sources.

    Attributes:
        source_type (Literal): Origin of this data
          - "sql": Employee database query result
          - "chroma_live": Real-time data from vector DB
          - "chroma_employee": Employee location vector DB
          - "tavily": External API (weather, news)
        reference_id (str): Identifier within the source (e.g., Tavily URL, employee ID, query hash)
        excerpt (str): Short snippet from source (for user reference)
        confidence (float): How confident we are this supports the claim (0.0-1.0)
    """
    source_type: Literal["sql", "chroma_live", "chroma_employee", "tavily"]  # Data origin
    reference_id: str  # ID within source (URL, employee_id, etc.)
    excerpt: str  # Preview text from source
    confidence: float  # 0.0-1.0: How well this supports the answer


class ConductorResponse(BaseModel):
    """
    Structured response from the Conductor (main orchestrator).

    The primary output format for user queries. Contains answer, sources, and metadata.
    Used by ORACLE Engine to deliver response to user or route to HITL.

    Attributes:
        answer (str): The main answer to user's query
        sources (list[Source]): Data sources backing the answer
        confidence (float): Conductor's confidence in this answer (0.0-1.0)
        query_type (Literal): Classification of query
          - "employee_only": Only employee data needed
          - "weather_only": Only weather/news needed
          - "blended": Both employee and weather
          - "general": Doesn't fit above categories
        hitl_required (bool): Conductor flagged this for human review
          (e.g., sensitive PII context, high-risk response)
        follow_up_suggestions (list[str]): Recommended follow-up questions for user
    """
    answer: str  # Main response to user query
    sources: list[Source] = []  # Data sources backing this answer
    confidence: float = 0.0  # Conductor's confidence (0.0-1.0)
    query_type: Literal["employee_only", "weather_only", "blended", "general"] = "general"  # Query classification
    hitl_required: bool = False  # Conductor flagged sensitive PII/high-risk content
    follow_up_suggestions: list[str] = []  # Suggested next questions for user


class WeatherResult(BaseModel):
    """
    Current weather conditions for a location.

    Returned by HERALD weather fetch tool. Contains current conditions, temperature,
    and forecast summary from Tavily API.

    Attributes:
        location (str): Original location string (e.g., "San Francisco, CA")
        normalized_location (str): Canonical location (lowercase, underscores)
        temperature_f (Optional[float]): Current temperature in Fahrenheit
        conditions (str): Current weather description
        forecast_summary (Optional[str]): Short forecast for next hours/days
        fetched_at (datetime): When this data was retrieved (for staleness checking)
        tavily_url (str): URL to Tavily search result (for user reference)
    """
    location: str  # Original location name
    normalized_location: str  # Canonical form (san_francisco_ca)
    temperature_f: Optional[float] = None  # Current temp in Fahrenheit
    conditions: str  # Current conditions description
    forecast_summary: Optional[str] = None  # Short forecast
    fetched_at: datetime = None  # When this was fetched
    tavily_url: str = ""  # Link to source


class NewsItem(BaseModel):
    """
    Single news article reference.

    Returned by HERALD news search tool. Contains article metadata for user review.

    Attributes:
        headline (str): Article title
        summary (str): First 500 chars of article
        url (str): Link to full article
        published_at (Optional[str]): Publication date (if available)
    """
    headline: str  # Article title
    summary: str  # Article preview/summary
    url: str  # Link to source
    published_at: Optional[str] = None  # Publication date


class WeatherNewsResult(BaseModel):
    """
    Combined weather and news result from HERALD agent.

    Returned by HERALD after processing weather/news queries.
    Includes weather data, news articles, and vector DB metadata.

    Attributes:
        weather (Optional[WeatherResult]): Current weather (if requested)
        news_items (list[NewsItem]): News articles matching query
        embedding_ids (list[str]): IDs of vectors stored in Chroma for retrieval
        location_matched (bool): Whether provided location was successfully matched
    """
    weather: Optional[WeatherResult] = None  # Current weather data
    news_items: list[NewsItem] = []  # News articles
    embedding_ids: list[str] = []  # Vector DB IDs for storage/retrieval
    location_matched: bool = False  # Was location found/matched


class HeraldHandoffInput(BaseModel):
    """
    Input parameters for handing off to HERALD agent.

    Used when Conductor decides to escalate to HERALD for pure weather/news queries.
    Defines what HERALD should search for.

    Attributes:
        query (str): The user's weather/news query
        location_hint (Optional[str]): Specific location to search for
          (e.g., "San Francisco" from "What's the weather in SF?")
    """
    query: str  # User's weather/news question
    location_hint: Optional[str] = None  # Geographic hint if explicitly mentioned
