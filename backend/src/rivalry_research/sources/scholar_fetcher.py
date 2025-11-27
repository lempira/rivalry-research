"""Fetch academic papers from Google Scholar."""

import logging
import time
from typing import Any

from scholarly import scholarly

from ..models import WikidataEntity, Source
from .utils import generate_source_id, get_iso_timestamp

logger = logging.getLogger(__name__)

# Rate limiting for Scholar
_last_request_time = 0.0
_min_request_interval = 2.0  # 2 seconds between requests to avoid rate limiting


def _rate_limit() -> None:
    """Enforce rate limiting between Scholar requests."""
    global _last_request_time
    now = time.time()
    time_since_last = now - _last_request_time
    if time_since_last < _min_request_interval:
        time.sleep(_min_request_interval - time_since_last)
    _last_request_time = time.time()


def _extract_paper_metadata(paper: dict[str, Any]) -> dict[str, Any]:
    """
    Extract standardized metadata from a Scholar paper result.
    
    Args:
        paper: Raw paper data from scholarly
    
    Returns:
        Dictionary with standardized fields
    """
    # Extract authors
    authors = []
    if "bib" in paper and "author" in paper["bib"]:
        author_data = paper["bib"]["author"]
        if isinstance(author_data, list):
            authors = author_data
        elif isinstance(author_data, str):
            authors = [author_data]
    
    # Extract publication info
    title = paper.get("bib", {}).get("title", "Unknown Title")
    year = paper.get("bib", {}).get("pub_year")
    venue = paper.get("bib", {}).get("venue")
    abstract = paper.get("bib", {}).get("abstract", "")
    
    # Get URL - prefer direct link, fallback to Scholar link
    url = paper.get("pub_url") or paper.get("eprint_url")
    if not url:
        # Generate Scholar citation URL from paper ID
        pub_id = paper.get("url_scholarbib", "")
        if pub_id:
            url = f"https://scholar.google.com/scholar?{pub_id}"
        else:
            # Last resort: use title-based search URL
            title_encoded = title.replace(" ", "+")
            url = f"https://scholar.google.com/scholar?q={title_encoded}"
    
    # Check for primary source indicators (entity is author)
    num_citations = paper.get("num_citations", 0)
    
    return {
        "title": title,
        "authors": authors,
        "year": year,
        "venue": venue,
        "abstract": abstract,
        "url": url,
        "num_citations": num_citations,
    }


def _is_primary_source(paper_metadata: dict[str, Any], entity: WikidataEntity) -> bool:
    """
    Determine if a paper is a primary source (written by the entity).
    
    Args:
        paper_metadata: Extracted paper metadata
        entity: WikidataEntity being researched
    
    Returns:
        True if entity is an author
    """
    entity_name_lower = entity.label.lower()
    
    for author in paper_metadata["authors"]:
        author_lower = author.lower()
        # Check if entity name appears in author name
        if entity_name_lower in author_lower or author_lower in entity_name_lower:
            return True
    
    return False


def _format_paper_content(
    paper_metadata: dict[str, Any], entity: WikidataEntity
) -> str:
    """
    Format paper metadata as a searchable document.
    
    Args:
        paper_metadata: Extracted paper metadata
        entity: WikidataEntity context
    
    Returns:
        Formatted document string
    """
    year_str = paper_metadata["year"] or "Unknown"
    venue_str = paper_metadata["venue"] or "Unknown"
    authors_str = ", ".join(paper_metadata["authors"]) if paper_metadata["authors"] else "Unknown"
    
    metadata_header = f"""---
Source: Google Scholar
Type: Academic Paper
Title: {paper_metadata["title"]}
Authors: {authors_str}
Year: {year_str}
Venue: {venue_str}
URL: {paper_metadata["url"]}
Citations: {paper_metadata["num_citations"]}
Related Entity: {entity.label} ({entity.id})
---

"""
    
    abstract = paper_metadata["abstract"] or "No abstract available."
    
    document = f"{metadata_header}# {paper_metadata['title']}\n\n"
    document += f"**Authors:** {authors_str}\n\n"
    document += f"**Published:** {year_str}"
    if venue_str != "Unknown":
        document += f" in {venue_str}"
    document += "\n\n"
    document += f"**Abstract:**\n\n{abstract}\n"
    
    return document


def fetch_scholar_sources(
    entity: WikidataEntity, max_results: int = 5
) -> list[tuple[Source, str]]:
    """
    Fetch academic papers about an entity from Google Scholar.
    
    Args:
        entity: WikidataEntity to search for
        max_results: Maximum number of papers to fetch (default: 5)
    
    Returns:
        List of (Source, content) tuples
    """
    logger.info(f"Searching Google Scholar for {entity.label} ({entity.id})")
    
    sources = []
    
    try:
        # Construct search query
        # Focus on biographical/historical papers about the person
        search_query = f'"{entity.label}"'
        if entity.description:
            # Add field/occupation for context (e.g., "physicist", "mathematician")
            search_query += f" {entity.description}"
        
        logger.debug(f"Scholar search query: {search_query}")
        
        # Search for papers
        _rate_limit()
        search_results = scholarly.search_pubs(search_query)
        
        # Process up to max_results papers
        for i in range(max_results):
            try:
                _rate_limit()
                paper = next(search_results)
                
                # Extract metadata
                metadata = _extract_paper_metadata(paper)
                
                # Create Source object
                is_primary = _is_primary_source(metadata, entity)
                
                source = Source(
                    source_id=generate_source_id(metadata["url"], "scholar"),
                    type="academic_paper",
                    title=metadata["title"],
                    authors=metadata["authors"],
                    publication=metadata["venue"],
                    publication_date=str(metadata["year"]) if metadata["year"] else None,
                    url=metadata["url"],
                    retrieved_at=get_iso_timestamp(),
                    credibility_score=0.95,  # Academic papers are highly credible
                    is_primary_source=is_primary,
                )
                
                # Format content
                content = _format_paper_content(metadata, entity)
                
                sources.append((source, content))
                
                logger.info(
                    f"Fetched Scholar paper: {source.title} "
                    f"({metadata['year']}, {metadata['num_citations']} citations)"
                )
                
            except StopIteration:
                logger.info(f"No more Scholar results (found {len(sources)} papers)")
                break
            except Exception as e:
                logger.warning(f"Error fetching Scholar paper {i+1}: {e}")
                continue
    
    except Exception as e:
        logger.error(f"Failed to search Google Scholar for {entity.label}: {e}")
    
    logger.info(f"Fetched {len(sources)} Scholar sources for {entity.label}")
    return sources

