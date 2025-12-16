"""Fetch academic papers from Google Scholar."""

import logging
import time
from typing import Any

from scholarly import scholarly

from ..models import WikidataEntity, Source
from .utils import generate_source_id, get_iso_timestamp
from .pdf_extractor import fetch_pdf_content

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

    # Get PDF URL (eprint_url is typically direct PDF link)
    pdf_url = paper.get("eprint_url")

    # Get display URL - prefer pub_url, fallback to eprint_url
    url = paper.get("pub_url") or pdf_url
    if not url:
        # Generate Scholar citation URL from paper ID
        pub_id = paper.get("url_scholarbib", "")
        if pub_id:
            url = f"https://scholar.google.com/scholar?{pub_id}"
        else:
            # Last resort: use title-based search URL
            title_encoded = title.replace(" ", "+")
            url = f"https://scholar.google.com/scholar?q={title_encoded}"

    num_citations = paper.get("num_citations", 0)

    return {
        "title": title,
        "authors": authors,
        "year": year,
        "venue": venue,
        "abstract": abstract,
        "url": url,
        "pdf_url": pdf_url,
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
    paper_metadata: dict[str, Any], entity: WikidataEntity, full_text: str
) -> str:
    """
    Format paper with full text as a searchable document.

    Args:
        paper_metadata: Extracted paper metadata
        entity: WikidataEntity context
        full_text: Extracted full text from PDF

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

    document = f"{metadata_header}# {paper_metadata['title']}\n\n"
    document += f"**Authors:** {authors_str}\n\n"
    document += f"**Published:** {year_str}"
    if venue_str != "Unknown":
        document += f" in {venue_str}"
    document += "\n\n"
    document += f"## Full Text\n\n{full_text}\n"

    return document


def fetch_scholar_sources(
    entity: WikidataEntity, max_results: int = 5, max_candidates: int = 20
) -> list[tuple[Source, str, bytes]]:
    """
    Fetch academic papers with full text PDFs about an entity from Google Scholar.

    Only includes papers where the full text PDF is available and can be extracted.
    Papers with only abstracts are skipped.

    Args:
        entity: WikidataEntity to search for
        max_results: Maximum number of papers with full text to fetch (default: 5)
        max_candidates: Maximum papers to check for PDFs (default: 20)

    Returns:
        List of (Source, content, pdf_bytes) tuples with full text and original PDF
    """
    logger.info(f"Searching Google Scholar for {entity.label} ({entity.id})")

    sources = []
    candidates_checked = 0

    try:
        # Construct search query
        search_query = f'"{entity.label}"'
        if entity.description:
            search_query += f" {entity.description}"

        logger.debug(f"Scholar search query: {search_query}")

        _rate_limit()
        search_results = scholarly.search_pubs(search_query)

        # Check candidates until we have max_results with full text
        while len(sources) < max_results and candidates_checked < max_candidates:
            try:
                _rate_limit()
                paper = next(search_results)
                candidates_checked += 1

                metadata = _extract_paper_metadata(paper)

                # Skip if no PDF URL available
                if not metadata["pdf_url"]:
                    logger.debug(f"Skipping '{metadata['title']}': no PDF URL")
                    continue

                # Try to download and extract PDF
                logger.debug(f"Downloading PDF for '{metadata['title']}'")
                pdf_data = fetch_pdf_content(metadata["pdf_url"])

                if pdf_data is None:
                    logger.debug(f"Skipping '{metadata['title']}': PDF download failed")
                    continue
                
                pdf_result, pdf_bytes = pdf_data

                if not pdf_result.success:
                    logger.debug(f"Skipping '{metadata['title']}': PDF extraction failed")
                    continue

                # Skip if extracted text is too short (likely failed extraction)
                if len(pdf_result.text.strip()) < 500:
                    logger.debug(f"Skipping '{metadata['title']}': extracted text too short")
                    continue

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
                    credibility_score=0.95,
                    is_primary_source=is_primary,
                )

                content = _format_paper_content(metadata, entity, pdf_result.text)
                sources.append((source, content, pdf_bytes))

                logger.info(
                    f"Fetched Scholar paper with full text: {source.title} "
                    f"({metadata['year']}, {pdf_result.page_count} pages)"
                )

            except StopIteration:
                logger.info(f"No more Scholar results (checked {candidates_checked})")
                break
            except Exception as e:
                logger.warning(f"Error processing Scholar paper: {e}")
                continue

    except Exception as e:
        logger.error(f"Failed to search Google Scholar for {entity.label}: {e}")

    logger.info(
        f"Fetched {len(sources)} Scholar sources with full text for {entity.label} "
        f"(checked {candidates_checked} candidates)"
    )
    return sources

