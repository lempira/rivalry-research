"""Fetch academic papers from arXiv."""

import logging
import tempfile
from pathlib import Path

import arxiv

from ..models import WikidataEntity, Source
from .utils import generate_source_id, get_iso_timestamp
from .pdf_extractor import extract_text_from_pdf

logger = logging.getLogger(__name__)


def _is_primary_source(paper: arxiv.Result, entity: WikidataEntity) -> bool:
    """
    Determine if a paper is a primary source (written by the entity).

    Args:
        paper: arXiv paper result
        entity: WikidataEntity being researched

    Returns:
        True if entity is an author
    """
    entity_name_lower = entity.label.lower()

    for author in paper.authors:
        author_lower = author.name.lower()
        if entity_name_lower in author_lower or author_lower in entity_name_lower:
            return True

    return False


def _format_paper_content(paper: arxiv.Result, entity: WikidataEntity, full_text: str) -> str:
    """
    Format arXiv paper with full text as a searchable document.

    Args:
        paper: arXiv paper result
        entity: WikidataEntity context
        full_text: Extracted full text from PDF

    Returns:
        Formatted document string
    """
    authors_str = ", ".join(author.name for author in paper.authors) or "Unknown"
    year_str = paper.published.strftime("%Y") if paper.published else "Unknown"
    categories = ", ".join(paper.categories) if paper.categories else "Unknown"

    metadata_header = f"""---
Source: arXiv
Type: Academic Paper (Preprint)
Title: {paper.title}
Authors: {authors_str}
Year: {year_str}
Categories: {categories}
arXiv ID: {paper.entry_id}
URL: {paper.pdf_url}
Related Entity: {entity.label} ({entity.id})
---

"""

    document = f"{metadata_header}# {paper.title}\n\n"
    document += f"**Authors:** {authors_str}\n\n"
    document += f"**Published:** {year_str}\n\n"
    document += f"**Categories:** {categories}\n\n"
    if paper.summary:
        document += f"**Abstract:** {paper.summary}\n\n"
    document += f"## Full Text\n\n{full_text}\n"

    return document


def fetch_arxiv_sources(
    entity: WikidataEntity, max_results: int = 5
) -> list[tuple[Source, str, bytes]]:
    """
    Fetch academic papers with full text from arXiv.

    arXiv papers are always open access, so PDF extraction should succeed
    for all results.

    Args:
        entity: WikidataEntity to search for
        max_results: Maximum number of papers to fetch (default: 5)

    Returns:
        List of (Source, content, pdf_bytes) tuples with full text and original PDF
    """
    logger.info(f"Searching arXiv for {entity.label} ({entity.id})")

    sources = []

    try:
        # Construct search query with biographical focus
        search_query = f'"{entity.label}"'
        if entity.description:
            search_query += f" {entity.description}"
        
        # Add biographical keywords to prioritize biographical/historical content
        search_query += " (biography OR life OR career OR history OR biographical)"

        logger.debug(f"arXiv search query: {search_query}")

        client = arxiv.Client()
        search = arxiv.Search(
            query=search_query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance,
        )

        for paper in client.results(search):
            try:
                logger.debug(f"Downloading PDF for '{paper.title}'")

                # Download PDF to temp file and extract text
                with tempfile.TemporaryDirectory() as tmpdir:
                    pdf_path = Path(tmpdir) / "paper.pdf"
                    paper.download_pdf(dirpath=tmpdir, filename="paper.pdf")

                    if not pdf_path.exists():
                        logger.warning(f"PDF download failed for '{paper.title}'")
                        continue

                    pdf_bytes = pdf_path.read_bytes()
                    pdf_result = extract_text_from_pdf(pdf_bytes)

                if not pdf_result.success:
                    logger.debug(f"Skipping '{paper.title}': PDF extraction failed")
                    continue

                # Skip if extracted text is too short
                if len(pdf_result.text.strip()) < 500:
                    logger.debug(f"Skipping '{paper.title}': extracted text too short")
                    continue

                is_primary = _is_primary_source(paper, entity)

                source = Source(
                    source_id=generate_source_id(paper.entry_id, "arxiv"),
                    type="arxiv_paper",
                    title=paper.title,
                    authors=[author.name for author in paper.authors],
                    publication="arXiv",
                    publication_date=paper.published.strftime("%Y-%m-%d") if paper.published else None,
                    url=paper.pdf_url,
                    retrieved_at=get_iso_timestamp(),
                    credibility_score=0.90,  # Preprints slightly lower than peer-reviewed
                    is_primary_source=is_primary,
                )

                content = _format_paper_content(paper, entity, pdf_result.text)
                sources.append((source, content, pdf_bytes))

                logger.info(
                    f"Fetched arXiv paper: {source.title} "
                    f"({paper.published.year if paper.published else 'Unknown'}, {pdf_result.page_count} pages)"
                )

            except Exception as e:
                logger.warning(f"Error processing arXiv paper '{paper.title}': {e}")
                continue

    except Exception as e:
        logger.error(f"Failed to search arXiv for {entity.label}: {e}")

    logger.info(f"Fetched {len(sources)} arXiv sources for {entity.label}")
    return sources