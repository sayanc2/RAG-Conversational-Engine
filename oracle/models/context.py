"""
Session Context Models - State Management for Conversations

This module defines Pydantic models for managing conversational state across turns.
Used by ORACLE Engine to track session data, conversation history, and query results.

Models:
  1. ConversationTurn - Single message in conversation (user or assistant)
  2. OracleSessionContext - Complete session state and context
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
import uuid


class ConversationTurn(BaseModel):
    """
    Single turn in a conversation (message exchange).

    Represents one message from either user or agent. Used to build conversation
    history for context in multi-turn interactions.

    Attributes:
        role (Literal["user", "assistant"]): Who sent this message
        content (str): The actual message text
        timestamp (datetime): When this message was created (auto-set to UTC now)
        agent_name (Optional[str]): Which agent sent it (if assistant, e.g., "HERALD", "CONDUCTOR")
    """
    role: Literal["user", "assistant"]  # Message origin: user input or agent response
    content: str  # The actual message text
    timestamp: datetime = Field(default_factory=datetime.utcnow)  # Auto-set to current UTC time
    agent_name: Optional[str] = None  # Which agent generated this (for assistant messages)


class OracleSessionContext(BaseModel):
    """
    Complete session state and context for a conversation.

    Tracks session ID, conversation history, query results, HITL state, and confidence scores.
    Passed through entire ORACLE pipeline to coordinate multi-agent execution.

    Lifecycle:
      1. Session starts: session_id generated, turn_count = 0
      2. Each query: turn_count incremented, message added to history
      3. Agent execution: results stored (last_employee_lookup, last_weather_lookup)
      4. HITL activation: hitl_pending set to True, draft_answer stored
      5. Human decision: context cleared or updated for next query

    Attributes:
        session_id (str): Unique UUID for this conversation session
        user_id (str): Identifier of user running query (for multi-user systems)
        conversation_history (list[ConversationTurn]): All messages in this session
        last_employee_lookup (Optional[dict]): Results from most recent employee query
        last_weather_lookup (Optional[dict]): Results from most recent weather query
        last_queried_location (Optional[str]): Location used in last query (for follow-ups)
        hitl_pending (bool): Whether human review is waiting (HITL activated)
        hitl_draft_answer (Optional[str]): Answer awaiting human approval
        groundedness_score (Optional[float]): Confidence score of last answer (0.0-1.0)
        turn_count (int): Number of queries in this session (for rate limiting, debugging)
    """
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))  # Unique ID per session
    user_id: str = "default_user"  # User identifier
    conversation_history: list[ConversationTurn] = []  # All messages in this session
    last_employee_lookup: Optional[dict] = None  # Cache results for context
    last_weather_lookup: Optional[dict] = None  # Cache results for context
    last_queried_location: Optional[str] = None  # For follow-up questions ("What about tomorrow?")
    hitl_pending: bool = False  # Human-in-the-loop review active
    hitl_draft_answer: Optional[str] = None  # Answer waiting for human decision
    groundedness_score: Optional[float] = None  # VALIDATOR confidence (0.0-1.0)
    turn_count: int = 0  # Query counter (for analytics, rate limiting)
