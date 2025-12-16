"""Orchestrates source fetching from multiple sources with deduplication."""

import hashlib
import logging
from pathlib import Path

from ..models import WikidataEntity, Source
from ..storage import SourceDatabase
from .wikipedia_fetcher import fetch_wikipedia_source
from .scholar_fetcher import fetch_scholar_sources
from .arxiv_fetcher import fetch_arxiv_sources
from .utils import (
    get_original_file_path,
    get_entity_directory,
    get_source_directory,
)

logger = logging.getLogger(__name__)


def fetch_sources_for_entity(
    db: SourceDatabase,
    raw_sources_dir: Path,
    entity: WikidataEntity,
    max_scholar_results: int = 3,
    max_arxiv_results: int = 3,
) -> list[tuple[Source, str]]:
    """
    Fetch all available sources for an entity.

    Fetches from:
    - Wikipedia (full text)
    - Google Scholar (full text PDFs only)
    - arXiv (full text PDFs)

    Args:
        db: SourceDatabase instance for deduplication
        raw_sources_dir: Directory to store raw source content
        entity: WikidataEntity to fetch sources for
        max_scholar_results: Maximum number of Scholar papers to fetch (default: 5)
        max_arxiv_results: Maximum number of arXiv papers to fetch (default: 5)

    Returns:
        List of (Source, content) tuples
    """
    raw_sources_dir = Path(raw_sources_dir)
    raw_sources_dir.mkdir(parents=True, exist_ok=True)

    sources_with_content: list[tuple[Source, str]] = []

    # Fetch Wikipedia
    if entity.wikipedia_url:
        try:
            wiki_result = _fetch_and_store_wikipedia(db, raw_sources_dir, entity)
            if wiki_result:
                sources_with_content.append(wiki_result)
        except Exception as e:
            logger.error(f"Failed to fetch Wikipedia for {entity.label}: {e}")

    # Fetch Google Scholar (full text PDFs only)
    try:
        scholar_results = _fetch_and_store_scholar(
            db, raw_sources_dir, entity, max_scholar_results
        )
        sources_with_content.extend(scholar_results)
    except Exception as e:
        logger.error(f"Failed to fetch Scholar for {entity.label}: {e}")

    # Fetch arXiv
    try:
        arxiv_results = _fetch_and_store_arxiv(
            db, raw_sources_dir, entity, max_arxiv_results
        )
        sources_with_content.extend(arxiv_results)
    except Exception as e:
        logger.error(f"Failed to fetch arXiv for {entity.label}: {e}")

    logger.info(f"Fetched {len(sources_with_content)} sources for {entity.label}")
    return sources_with_content


def _fetch_and_store_wikipedia(
    db: SourceDatabase,
    raw_sources_dir: Path,
    entity: WikidataEntity,
) -> tuple[Source, str] | None:
    """
    Fetch Wikipedia source with deduplication and storage.

    Args:
        db: SourceDatabase instance
        raw_sources_dir: Directory to store raw source content
        entity: WikidataEntity with wikipedia_url

    Returns:
        Tuple of (Source, content) if successful, None otherwise
    """
    # Check if already in database
    existing = db.get_source_by_url(entity.wikipedia_url)
    if existing:
        logger.info(f"Wikipedia source already exists: {existing.source_id}")
        
        # Check if original HTML file exists
        html_path = get_original_file_path(raw_sources_dir, existing.url, "html")
        if not html_path.exists():
            logger.info(f"Original HTML missing for {existing.source_id}, will save it")
            # Fetch to get the HTML bytes
            source, content, html_bytes = fetch_wikipedia_source(entity)
            # Save the original HTML
            html_path.write_bytes(html_bytes)
            logger.debug(f"Saved original HTML to {html_path}")
            return existing, content
        
        # We need the content, so read it from disk if available
        if existing.stored_content_path:
            try:
                content_path = raw_sources_dir.parent / existing.stored_content_path
                content = content_path.read_text(encoding="utf-8")
                return existing, content
            except Exception as e:
                logger.warning(f"Failed to read stored content for {existing.source_id}: {e}")
                # Fall through to re-fetch if content missing
        
        # If content missing or not stored path, re-fetch
    
    # Fetch new source
    source, content, html_bytes = fetch_wikipedia_source(entity)

    # Calculate content hash
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    source.content_hash = content_hash
    
    # Mark as auto-fetched
    source.is_manual = False

    # Get entity-organized directory structure
    entity_dir = get_entity_directory(raw_sources_dir, entity.label, entity.id)
    source_dir, _ = get_source_directory(entity_dir, "wikipedia")

    # Save extracted text content to disk
    content_path = source_dir / "content.txt"
    content_path.write_text(content, encoding="utf-8")
    source.stored_content_path = str(content_path.relative_to(raw_sources_dir.parent))

    logger.debug(f"Saved content to {content_path}")

    # Save original HTML file
    html_path = source_dir / "original.html"
    html_path.write_bytes(html_bytes)
    logger.debug(f"Saved original HTML to {html_path}")

    # Add to database
    source = db.add_source(source)

    return source, content


def _fetch_and_store_scholar(
    db: SourceDatabase,
    raw_sources_dir: Path,
    entity: WikidataEntity,
    max_results: int = 5,
) -> list[tuple[Source, str]]:
    """
    Fetch Scholar sources with deduplication and storage.

    Args:
        db: SourceDatabase instance
        raw_sources_dir: Directory to store raw source content
        entity: WikidataEntity to search for
        max_results: Maximum number of papers to fetch

    Returns:
        List of (Source, content) tuples
    """
    scholar_results = fetch_scholar_sources(entity, max_results)
    stored_results = []

    for source, content, pdf_bytes in scholar_results:
        # Check if URL already exists in database
        existing = db.get_source_by_url(source.url)
        if existing:
            logger.info(f"Scholar source already exists: {existing.source_id}")
            
            # Check if original PDF file exists, save it if missing
            pdf_path = get_original_file_path(raw_sources_dir, existing.url, "pdf")
            if not pdf_path.exists():
                logger.info(f"Original PDF missing for {existing.source_id}, saving it")
                pdf_path.write_bytes(pdf_bytes)
                logger.debug(f"Saved original PDF to {pdf_path}")
            
            # If exists, we use the existing source metadata but the fetched content
            # (or we could read from disk, but we already have the content here from fetch)
            stored_results.append((existing, content))
            continue

        # Calculate content hash
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        source.content_hash = content_hash
        
        # Mark as auto-fetched
        source.is_manual = False

        # Get entity-organized directory structure
        entity_dir = get_entity_directory(raw_sources_dir, entity.label, entity.id)
        source_dir, counter = get_source_directory(entity_dir, "scholar")

        # Save extracted text content to disk
        content_path = source_dir / "content.txt"
        content_path.write_text(content, encoding="utf-8")
        source.stored_content_path = str(content_path.relative_to(raw_sources_dir.parent))

        logger.debug(f"Saved Scholar content to {content_path}")

        # Save original PDF file
        pdf_path = source_dir / "original.pdf"
        pdf_path.write_bytes(pdf_bytes)
        logger.debug(f"Saved original PDF to {pdf_path}")

        # Add to database
        source = db.add_source(source)
        stored_results.append((source, content))

        logger.info(f"Stored Scholar source: {source.source_id} - {source.title}")

    return stored_results


def _fetch_and_store_arxiv(
    db: SourceDatabase,
    raw_sources_dir: Path,
    entity: WikidataEntity,
    max_results: int = 5,
) -> list[tuple[Source, str]]:
    """
    Fetch arXiv sources with deduplication and storage.

    Args:
        db: SourceDatabase instance
        raw_sources_dir: Directory to store raw source content
        entity: WikidataEntity to search for
        max_results: Maximum number of papers to fetch

    Returns:
        List of (Source, content) tuples
    """
    arxiv_results = fetch_arxiv_sources(entity, max_results)
    stored_results = []

    for source, content, pdf_bytes in arxiv_results:
        # Check if URL already exists in database
        existing = db.get_source_by_url(source.url)
        if existing:
            logger.info(f"arXiv source already exists: {existing.source_id}")
            
            # Check if original PDF file exists, save it if missing
            pdf_path = get_original_file_path(raw_sources_dir, existing.url, "pdf")
            if not pdf_path.exists():
                logger.info(f"Original PDF missing for {existing.source_id}, saving it")
                pdf_path.write_bytes(pdf_bytes)
                logger.debug(f"Saved original PDF to {pdf_path}")
            
            stored_results.append((existing, content))
            continue

        # Calculate content hash
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        source.content_hash = content_hash
        
        # Mark as auto-fetched
        source.is_manual = False

        # Get entity-organized directory structure
        entity_dir = get_entity_directory(raw_sources_dir, entity.label, entity.id)
        source_dir, counter = get_source_directory(entity_dir, "arxiv")

        # Save extracted text content to disk
        content_path = source_dir / "content.txt"
        content_path.write_text(content, encoding="utf-8")
        source.stored_content_path = str(content_path.relative_to(raw_sources_dir.parent))

        logger.debug(f"Saved arXiv content to {content_path}")

        # Save original PDF file
        pdf_path = source_dir / "original.pdf"
        pdf_path.write_bytes(pdf_bytes)
        logger.debug(f"Saved original PDF to {pdf_path}")

        # Add to database
        source = db.add_source(source)
        stored_results.append((source, content))

        logger.info(f"Stored arXiv source: {source.source_id} - {source.title}")

    return stored_results

