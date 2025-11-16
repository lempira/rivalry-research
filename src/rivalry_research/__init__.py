"""Rivalry Research - Analyze rivalrous relationships using Wikidata and AI."""

import logging

from .models import (
    EntitySearchResult,
    Relationship,
    RivalryAnalysis,
    RivalryFact,
    WikidataEntity,
)
from .rag.file_search_client import (
    check_document_exists,
    get_or_create_store,
    upload_document,
)
from .relationships import get_direct_relationships, get_shared_properties
from .rivalry_agent import analyze_rivalry as analyze_rivalry_with_data
from .search import get_person_by_id, search_person
from .sources.wikipedia_fetcher import fetch_wikipedia_article

logger = logging.getLogger(__name__)

__version__ = "0.1.0"

__all__ = [
    # Search and retrieval
    "search_person",
    "get_person_by_id",
    "analyze_rivalry",
    # Models
    "EntitySearchResult",
    "WikidataEntity",
    "Relationship",
    "RivalryFact",
    "RivalryAnalysis",
    # Advanced functions
    "get_direct_relationships",
    "get_shared_properties",
]


def analyze_rivalry(entity_id1: str, entity_id2: str) -> RivalryAnalysis:
    """
    Analyze the rivalry between two people using Wikidata and RAG-enhanced AI.

    This high-level function orchestrates the complete workflow:
    1. Fetches both entities from Wikidata (with Wikipedia URLs)
    2. Extracts direct relationships and shared properties between them
    3. Fetches and uploads Wikipedia articles to File Search store
    4. Uses AI with File Search to analyze rivalry with biographical context

    The AI agent has access to both structured Wikidata facts and biographical
    narrative from Wikipedia articles, enabling richer timeline extraction and
    rivalry analysis.

    Args:
        entity_id1: First person's Wikidata entity ID (e.g., "Q935" for Newton)
        entity_id2: Second person's Wikidata entity ID (e.g., "Q9047" for Leibniz)

    Returns:
        RivalryAnalysis with structured rivalry data including facts, scores, and summary

    Raises:
        ValueError: If entities are not found or have no Wikipedia URLs
        httpx.HTTPError: If API requests fail
        Exception: If AI analysis or File Search operations fail

    Example:
        >>> # Newton vs Leibniz (calculus priority dispute)
        >>> analysis = analyze_rivalry("Q935", "Q9047")
        >>> print(f"Rivalry exists: {analysis.rivalry_exists}")
        >>> print(f"Rivalry score: {analysis.rivalry_score:.2f}")
        >>> print(f"Summary: {analysis.summary}")
        >>> for fact in analysis.facts:
        ...     print(f"[{fact.date}] {fact.fact}")
    """
    logger.info(f"Starting rivalry analysis: {entity_id1} vs {entity_id2}")

    # PHASE 1: Fetch Wikidata entities and relationships
    logger.info("Phase 1: Fetching Wikidata entities")
    entity1 = get_person_by_id(entity_id1)
    entity2 = get_person_by_id(entity_id2)

    logger.debug(f"Entity 1: {entity1.label} ({entity1.id})")
    logger.debug(f"  Description: {entity1.description}")
    logger.debug(f"  Wikipedia: {entity1.wikipedia_url}")

    logger.debug(f"Entity 2: {entity2.label} ({entity2.id})")
    logger.debug(f"  Description: {entity2.description}")
    logger.debug(f"  Wikipedia: {entity2.wikipedia_url}")

    logger.info("Fetching relationships and shared properties")
    relationships = get_direct_relationships(entity_id1, entity_id2)
    shared_props = get_shared_properties(entity_id1, entity_id2)

    logger.debug(f"Found {len(relationships)} direct relationships")
    logger.debug(f"Found {len(shared_props)} shared properties")

    # PHASE 2: Prepare biographical documents for File Search
    logger.info("Phase 2: Preparing biographical documents for File Search")
    store = get_or_create_store()

    logger.info("Fetching Wikipedia articles")
    content1 = fetch_wikipedia_article(entity1)
    content2 = fetch_wikipedia_article(entity2)

    logger.debug(f"Article 1 size: {len(content1)} characters")
    logger.debug(f"Article 2 size: {len(content2)} characters")

    # Upload documents if not already in store
    if not check_document_exists(store.name, entity1.id):
        logger.info(f"Uploading document for {entity1.label}")
        upload_document(store.name, entity1, content1)
    else:
        logger.info(f"Document already exists for {entity1.label}")

    if not check_document_exists(store.name, entity2.id):
        logger.info(f"Uploading document for {entity2.label}")
        upload_document(store.name, entity2, content2)
    else:
        logger.info(f"Document already exists for {entity2.label}")

    # PHASE 3: AI analysis with File Search
    logger.info("Phase 3: Running AI analysis with File Search RAG")
    analysis = analyze_rivalry_with_data(
        entity1, entity2, relationships, shared_props, store_name=store.name
    )

    logger.info(
        f"Analysis complete: rivalry={'YES' if analysis.rivalry_exists else 'NO'}, "
        f"score={analysis.rivalry_score:.2f}"
    )

    return analysis
