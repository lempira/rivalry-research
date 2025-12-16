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
    get_or_create_store,
    upload_document,
)
from .relationships import get_direct_relationships, get_shared_properties
from .rivalry_agent import analyze_rivalry as analyze_rivalry_with_data
from .search import get_person_by_id, search_person
from .sources import fetch_sources_for_entity
from .storage import save_analysis, SourceDatabase

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
    3. Fetches all sources (Wiki, Scholar, arXiv) for both entities
    4. Uploads ALL source content to File Search store for agent tool access
    5. Uses AI with File Search to analyze rivalry with comprehensive context
    6. Saves analysis to disk with full source catalog

    The AI agent has access to both structured Wikidata facts and the full text of
    all collected documents (Wikipedia + academic papers), enabling deeper analysis.
    Sources are automatically deduplicated and tracked.

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

    # PHASE 2: Fetch Sources & Prepare File Search
    logger.info("Phase 2: Fetching sources and preparing File Search")
    settings = get_settings()
    store = get_or_create_store()
    db = SourceDatabase(settings.sources_db_path)

    # Fetch all sources for both entities
    logger.info("Fetching comprehensive sources (Wiki, Scholar, arXiv)")
    sources_1_tuples = fetch_sources_for_entity(db, settings.raw_sources_dir, entity1)
    sources_2_tuples = fetch_sources_for_entity(db, settings.raw_sources_dir, entity2)
    
    all_source_tuples = sources_1_tuples + sources_2_tuples
    all_sources_list = [t[0] for t in all_source_tuples]
    
    # Count sources by origin
    manual_count = sum(1 for s in all_sources_list if s.is_manual)
    auto_count = len(all_sources_list) - manual_count
    
    logger.info(f"Collected {len(all_sources_list)} total sources")
    logger.info(f"Source breakdown: {manual_count} manual, {auto_count} auto-fetched")
    
    # Upload content to File Search
    logger.info("Uploading source content to File Search store")
    for source, content in all_source_tuples:
        # Check if already uploaded (using source ID or URL hash might be better, 
        # but here we use a simple check or just allow update)
        # Note: check_document_exists is currently a stub that returns False
        # We'll use the source title + ID as display name
        display_name = f"{source.title} ({source.source_id})"
        
        # Build custom metadata from source attributes
        custom_metadata = {
            "source_id": source.source_id,
            "source_type": source.type,
            "is_manual": source.is_manual,
            "title": source.title,
            "url": source.url,
        }
        
        # Add optional metadata fields if available
        if source.authors:
            custom_metadata["authors"] = ", ".join(source.authors)
        if source.publication:
            custom_metadata["publication"] = source.publication
        if source.publication_date:
            custom_metadata["publication_date"] = source.publication_date
        if source.doi:
            custom_metadata["doi"] = source.doi
        
        # Upload with metadata
        try:
            upload_document(
                store.name,
                display_name,
                content,
                custom_metadata=custom_metadata,
            )
        except Exception as e:
            logger.warning(f"Failed to upload {display_name} to File Search: {e}")

    # PHASE 3: AI analysis with File Search
    logger.info("Phase 3: Running AI analysis with pre-fetched sources")
    analysis = analyze_rivalry_with_data(
        entity1, entity2, relationships, shared_props, 
        store_name=store.name,
        sources=all_sources_list
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
