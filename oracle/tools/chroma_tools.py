"""
Chroma Vector Database Tools - Semantic Search and Context Storage

This module provides tools for vector storage and semantic search using Chromadb.
It enables multi-turn conversation context retrieval and live data embedding.

Features:
  - Persistent vector database (default: data/chroma directory)
  - Multiple collections for different data types (live_context, employee_locations)
  - Semantic similarity search with configurable result limits
  - Document embedding via OpenAI API
  - Session-aware metadata tagging

Collections:
  1. live_context: Real-time data from weather/news API calls
  2. employee_locations: Pre-embedded office locations for similarity matching

Embeddings:
  - Generated via OpenAI's embedding model (text-embedding-3-small or similar)
  - Configured in embedding.py module
"""

import os
import hashlib
from datetime import datetime
from typing import Any

import chromadb
from agents import function_tool, RunContextWrapper

from oracle.models import OracleSessionContext

# Singleton Chroma client and database path
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_CHROMA_DIR = os.path.join(_BASE_DIR, "data", "chroma")

_chroma_client: chromadb.PersistentClient | None = None


def get_chroma_client() -> chromadb.PersistentClient:
    """
    Get or create the singleton Chroma persistent client.

    Uses lazy initialization to connect to the vector database.
    Persistence directory is configured via CHROMA_PERSIST_DIR environment variable.

    Returns:
        chromadb.PersistentClient: Connected client for database operations
    """
    global _chroma_client
    if _chroma_client is None:
        # Load persistence directory from environment or use default
        persist_dir = os.environ.get("CHROMA_PERSIST_DIR", _DEFAULT_CHROMA_DIR)
        os.makedirs(persist_dir, exist_ok=True)
        # Create persistent client (survives restarts)
        _chroma_client = chromadb.PersistentClient(path=persist_dir)
    return _chroma_client


def get_or_create_collection(name: str) -> chromadb.Collection:
    """
    Get or create a named collection in Chroma.

    Collections are lazy-created on first access.
    Useful for organizing data by type (live_context, employee_locations).

    Args:
        name (str): Collection name (auto-created if doesn't exist)

    Returns:
        chromadb.Collection: The collection object for queries/upserts
    """
    client = get_chroma_client()
    return client.get_or_create_collection(name=name)


def embed_document(text: str) -> list[float]:
    """
    Generate vector embedding for a document.

    Delegates to embedding.py module which handles OpenAI API calls.
    Results are cached for efficiency.

    Args:
        text (str): Text to embed

    Returns:
        list[float]: Embedding vector (typically 1536-dimensional)
    """
    from oracle.tools.embedding import get_embedding
    return get_embedding(text)


def _embed_and_store_live_context_fn(
    ctx: RunContextWrapper[OracleSessionContext],
    text: str,
    metadata: dict[str, Any],
) -> str:
    """
    Embed and store a document in the live_context collection.

    Used by HERALD to persist weather/news results for semantic search in follow-ups.
    Automatically tags with session_id and fetch timestamp for traceability.

    Document ID Strategy:
      - Generated from SHA256 hash of text (ensures deduplication)
      - Prefixed with "tavily_" for source tracking
      - Hash truncated to 16 chars for brevity

    Args:
        ctx (RunContextWrapper): Session context with session_id
        text (str): Document text to embed and store
        metadata (dict): Additional metadata (e.g., source, url)

    Returns:
        str: Document ID (for later reference/updates)
    """
    # Generate deterministic doc ID from text hash (deduplicates identical content)
    doc_id = f"tavily_{hashlib.sha256(text.encode()).hexdigest()[:16]}"

    # Get or create live_context collection
    collection = get_or_create_collection("live_context")

    # Generate embedding for semantic search
    embedding = embed_document(text)

    # Add session and timestamp metadata
    metadata["session_id"] = ctx.context.session_id
    metadata["fetched_at"] = datetime.utcnow().isoformat()

    # Upsert (insert or update) document with embedding
    collection.upsert(
        ids=[doc_id],
        embeddings=[embedding],
        documents=[text],
        metadatas=[metadata],
    )
    return doc_id


def _chroma_similarity_search_fn(
    ctx: RunContextWrapper[OracleSessionContext],
    query: str,
    collection_name: str,
    n_results: int = 5,
) -> list[dict]:
    """
    Perform semantic similarity search over a Chroma collection.

    Converts query to embedding and finds most similar documents in collection.
    Returns documents with metadata and distance scores.

    Args:
        ctx (RunContextWrapper): Session context (unused, for agent tool compatibility)
        query (str): Natural language query to search for
        collection_name (str): Name of collection to search (live_context, employee_locations)
        n_results (int): Maximum results to return (default: 5)

    Returns:
        list[dict]: Search results, each with:
          - id: Document ID
          - document: Document text
          - metadata: Associated metadata
          - distance: Similarity distance (lower = more similar)
    """
    # Get collection (auto-creates if doesn't exist)
    collection = get_or_create_collection(collection_name)

    # Embed the query for similarity search
    embedding = embed_document(query)

    try:
        # Query vector DB for similar documents
        results = collection.query(
            query_embeddings=[embedding],
            n_results=min(n_results, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        # Format results into list of dicts
        output = []
        for i, doc_id in enumerate(results["ids"][0]):
            output.append({
                "id": doc_id,
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            })
        return output
    except Exception:
        # Return empty list on any error (network, empty collection, etc.)
        return []


# Export functions as tools for agent use
embed_and_store_live_context = function_tool(_embed_and_store_live_context_fn, strict_mode=False)
chroma_similarity_search = function_tool(_chroma_similarity_search_fn)


def embed_employee_locations(employees: list[dict]) -> None:
    """
    Batch-embed all employee office locations into the vector database.

    Called during system initialization to pre-populate employee_locations collection.
    Enables efficient semantic search when matching weather locations to employee offices.

    Args:
        employees (list[dict]): List of employee records with office_location field
    """
    # Get or create employee_locations collection
    collection = get_or_create_collection("employee_locations")

    # Batch collect IDs, embeddings, documents, and metadata
    ids, embeddings, documents, metadatas = [], [], [], []

    # For each employee, create a location document for semantic search
    for emp in employees:
        # Doc ID format: emp_{employee_id}
        doc_id = f"emp_{emp['employee_id']}"

        # Create searchable text from location and department
        text = f"{emp['office_location']}, {emp['department']} office"

        # Generate embedding for this location
        embedding = embed_document(text)

        # Collect for batch upsert
        ids.append(doc_id)
        embeddings.append(embedding)
        documents.append(text)
        metadatas.append({
            "employee_id": emp["employee_id"],
            "name": emp["name"],
            "office_location": emp["office_location"],
            "department": emp["department"],
        })

    # Batch insert/update all embeddings at once (more efficient than individual inserts)
    if ids:
        collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
    print(f"Embedded {len(ids)} employee locations into ChromaDB.")
