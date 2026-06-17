"""
Embedding Service - Vector Generation for Documents

This module provides document embedding functionality using OpenAI's embedding models.
Embeddings are used for semantic search in Chroma vector database.

Embedding Models:
  - Default: text-embedding-3-small (256-dimensional, cost-efficient)
  - Alternative: text-embedding-3-large (3072-dimensional, higher quality)
  - Configurable via EMBEDDING_MODEL environment variable

Cost & Performance:
  - text-embedding-3-small: $0.02 per 1M tokens (recommended)
  - text-embedding-3-large: $0.13 per 1M tokens

API Configuration:
  - API key: OPENAI_API_KEY environment variable
  - Uses singleton client for connection pooling
"""

import os
from openai import OpenAI

# Singleton OpenAI client (lazy initialized)
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """
    Get or create the singleton OpenAI client.

    Uses lazy initialization for connection pooling and efficiency.
    API key is loaded from OPENAI_API_KEY environment variable.

    Returns:
        OpenAI: Configured OpenAI client for API calls
    """
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
    return _client


def get_embedding(text: str, model: str | None = None) -> list[float]:
    """
    Generate vector embedding for text using OpenAI Embeddings API.

    Converts text document into a high-dimensional vector for semantic search.
    Used by Chroma to store and retrieve documents based on similarity.

    Preprocessing:
      - Replaces newlines with spaces (flattens multi-line text)
      - Strips leading/trailing whitespace

    Args:
        text (str): Document text to embed
        model (str | None): Embedding model (default: text-embedding-3-small)

    Returns:
        list[float]: Embedding vector (1536 dims for small, 3072 for large)
    """
    # Use specified model or fall back to environment/default
    model = model or os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")

    # Get singleton OpenAI client
    client = _get_client()

    # Normalize text: remove newlines and strip whitespace
    text = text.replace("\n", " ").strip()

    # Call OpenAI Embeddings API
    response = client.embeddings.create(input=[text], model=model)

    # Extract embedding vector from response
    return response.data[0].embedding
