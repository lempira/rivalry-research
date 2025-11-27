"""Rivalry Research - Analyze rivalrous relationships using Wikidata and AI."""

import logging

import logfire

from .models import (
    EntitySearchResult,
    Relationship,
    RivalryAnalysis,
    RivalryEntity,
    TimelineEvent,
    WikidataEntity,
)
from .config import get_settings
from .rag.file_search_client import (
    check_document_exists,
    get_or_create_store,
    upload_document,
)
from .relationships import get_direct_relationships, get_shared_properties
from .rivalry_agent import analyze_rivalry as analyze_rivalry_with_data
from .search import get_person_by_id, search_person
from .sources import fetch_wikipedia_source
from .storage import save_analysis

logger = logging.getLogger(__name__)

# Configure Logfire for console-only observability (no web service)
logfire.configure(
    send_to_logfire='never',  # Console only, don't send to web
    console=logfire.ConsoleOptions(span_style='simple'),
)
logfire.instrument_pydantic_ai()

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
    "RivalryEntity",
    "RivalryAnalysis",
    "TimelineEvent",
    # Advanced functions
    "get_direct_relationships",
    "get_shared_properties",
]


def analyze_rivalry(entity_id1: str, entity_id2: str, save_output: bool = True) -> RivalryAnalysis:
    """
    Analyze the rivalry between two people using Wikidata and RAG-enhanced AI.

    This high-level function orchestrates the complete workflow:
    1. Fetches both entities from Wikidata (with Wikipedia URLs)
    2. Extracts direct relationships and shared properties between them
    3. Fetches Wikipedia sources and stores them in SQLite (automatic deduplication)
    4. Uploads Wikipedia content to File Search store for agent tool access
    5. Uses AI with File Search to analyze rivalry with biographical context
    6. Saves analysis to disk with full source catalog

    The AI agent has access to both structured Wikidata facts and biographical
    narrative from Wikipedia articles, enabling richer timeline extraction and
    rivalry analysis. Sources are automatically deduplicated and tracked.

    Args:
        entity_id1: First person's Wikidata entity ID (e.g., "Q935" for Newton)
        entity_id2: Second person's Wikidata entity ID (e.g., "Q9047" for Leibniz)
        save_output: Whether to save analysis to disk (default: True)

    Returns:
        RivalryAnalysis with structured rivalry data including source catalog

    Raises:
        ValueError: If entities are not found or have no Wikipedia URLs
        httpx.HTTPError: If API requests fail
        Exception: If AI analysis or File Search operations fail

    Example:
        >>> # Newton vs Leibniz (calculus priority dispute)
        >>> analysis = analyze_rivalry("Q935", "Q9047")
        >>> print(f"Rivalry exists: {analysis.rivalry_exists}")
        >>> print(f"Rivalry score: {analysis.rivalry_score:.2f}")
        >>> print(f"Sources: {len(analysis.sources)} total")
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

    logger.info("Fetching Wikipedia articles for File Search")
    
    # Fetch Wikipedia sources (for content to upload to File Search)
    # The analyze_rivalry_with_data will also fetch sources, but we need content here
    # for File Search upload
    if entity1.wikipedia_url:
        source1, content1 = fetch_wikipedia_source(entity1)
        if not check_document_exists(store.name, entity1.id):
            logger.info(f"Uploading document for {entity1.label}")
            upload_document(store.name, entity1, content1)
        else:
            logger.info(f"Document already exists for {entity1.label}")
    
    if entity2.wikipedia_url:
        source2, content2 = fetch_wikipedia_source(entity2)
        if not check_document_exists(store.name, entity2.id):
            logger.info(f"Uploading document for {entity2.label}")
            upload_document(store.name, entity2, content2)
        else:
            logger.info(f"Document already exists for {entity2.label}")

    # PHASE 3: AI analysis with File Search (fetches sources internally)
    logger.info("Phase 3: Running AI analysis with source fetching")
    analysis = analyze_rivalry_with_data(
        entity1, entity2, relationships, shared_props, store_name=store.name
    )

    logger.info(
        f"Analysis complete: rivalry={'YES' if analysis.rivalry_exists else 'NO'}, "
        f"score={analysis.rivalry_score:.2f}, sources={len(analysis.sources)}"
    )

    # PHASE 4: Save analysis
    if save_output:
        settings = get_settings()
        output_path = save_analysis(analysis, settings.analyses_dir)
        logger.info(f"Saved analysis to {output_path}")

    return analysis
