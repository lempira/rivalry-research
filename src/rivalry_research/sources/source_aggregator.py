"""Orchestrates source fetching from multiple sources with deduplication."""

import hashlib
import logging
from pathlib import Path

from ..models import WikidataEntity, Source
from ..storage import SourceDatabase
from .wikipedia_fetcher import fetch_wikipedia_source
from .scholar_fetcher import fetch_scholar_sources
from .utils import get_content_path

logger = logging.getLogger(__name__)


def fetch_sources_for_entity(
    db: SourceDatabase,
    raw_sources_dir: Path,
    entity: WikidataEntity,
    max_scholar_results: int = 5,
) -> list[Source]:
    """
    Fetch all available sources for an entity.

    Currently fetches from:
    - Wikipedia
    - Google Scholar

    Args:
        db: SourceDatabase instance for deduplication
        raw_sources_dir: Directory to store raw source content
        entity: WikidataEntity to fetch sources for
        max_scholar_results: Maximum number of Scholar papers to fetch (default: 5)

    Returns:
        List of Source objects (deduplicated)
    """
    raw_sources_dir = Path(raw_sources_dir)
    raw_sources_dir.mkdir(parents=True, exist_ok=True)
    
    sources = []

    # Fetch Wikipedia
    if entity.wikipedia_url:
        try:
            wiki_source = _fetch_and_store_wikipedia(db, raw_sources_dir, entity)
            if wiki_source:
                sources.append(wiki_source)
        except Exception as e:
            logger.error(f"Failed to fetch Wikipedia for {entity.label}: {e}")

    # Fetch Google Scholar
    try:
        scholar_sources = _fetch_and_store_scholar(
            db, raw_sources_dir, entity, max_scholar_results
        )
        sources.extend(scholar_sources)
    except Exception as e:
        logger.error(f"Failed to fetch Scholar for {entity.label}: {e}")

    logger.info(f"Fetched {len(sources)} sources for {entity.label}")
    return sources


def _fetch_and_store_wikipedia(
    db: SourceDatabase,
    raw_sources_dir: Path,
    entity: WikidataEntity,
) -> Source | None:
    """
    Fetch Wikipedia source with deduplication and storage.

    Args:
        db: SourceDatabase instance
        raw_sources_dir: Directory to store raw source content
        entity: WikidataEntity with wikipedia_url

    Returns:
        Source object if successful, None otherwise
    """
    # Check if already in database
    existing = db.get_source_by_url(entity.wikipedia_url)
    if existing:
        logger.info(f"Wikipedia source already exists: {existing.source_id}")
        return existing

    # Fetch new source
    source, content = fetch_wikipedia_source(entity)

    # Calculate content hash
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    source.content_hash = content_hash

    # Save raw content to disk
    content_path = get_content_path(raw_sources_dir, source.url, "txt")
    content_path.write_text(content, encoding="utf-8")
    source.stored_content_path = str(content_path.relative_to(raw_sources_dir.parent))

    logger.debug(f"Saved content to {content_path}")

    # Add to database
    source = db.add_source(source)

    return source


def _fetch_and_store_scholar(
    db: SourceDatabase,
    raw_sources_dir: Path,
    entity: WikidataEntity,
    max_results: int = 5,
) -> list[Source]:
    """
    Fetch Scholar sources with deduplication and storage.

    Args:
        db: SourceDatabase instance
        raw_sources_dir: Directory to store raw source content
        entity: WikidataEntity to search for
        max_results: Maximum number of papers to fetch

    Returns:
        List of Source objects
    """
    scholar_results = fetch_scholar_sources(entity, max_results)
    stored_sources = []

    for source, content in scholar_results:
        # Check if URL already exists in database
        existing = db.get_source_by_url(source.url)
        if existing:
            logger.info(f"Scholar source already exists: {existing.source_id}")
            stored_sources.append(existing)
            continue

        # Calculate content hash
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        source.content_hash = content_hash

        # Save raw content to disk
        content_path = get_content_path(raw_sources_dir, source.url, "txt")
        content_path.write_text(content, encoding="utf-8")
        source.stored_content_path = str(content_path.relative_to(raw_sources_dir.parent))

        logger.debug(f"Saved Scholar content to {content_path}")

        # Add to database
        source = db.add_source(source)
        stored_sources.append(source)

        logger.info(f"Stored Scholar source: {source.source_id} - {source.title}")

    return stored_sources

