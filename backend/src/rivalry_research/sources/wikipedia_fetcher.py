"""Fetch Wikipedia article content for entities."""

import logging
from urllib.parse import unquote, urlparse

import httpx

from ..models import WikidataEntity, Source
from .utils import generate_source_id, get_iso_timestamp
from .source_fetcher_utils import (
    RateLimiter,
    build_metadata_header,
    clean_html_to_text,
)

logger = logging.getLogger(__name__)

# Wikipedia API endpoint
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"

# User agent for Wikipedia compliance
USER_AGENT = "RivalryResearch/0.1.0 (https://github.com/user/rivalry-research)"

# Rate limiting
_rate_limiter = RateLimiter(0.5, "Wikipedia")


def _extract_article_title_from_url(wikipedia_url: str) -> str:
    """
    Extract the article title from a Wikipedia URL.
    
    Args:
        wikipedia_url: Full Wikipedia URL (e.g., "https://en.wikipedia.org/wiki/Isaac_Newton")
    
    Returns:
        Article title (e.g., "Isaac_Newton")
    """
    parsed = urlparse(wikipedia_url)
    path_parts = parsed.path.split("/")
    if len(path_parts) >= 3 and path_parts[1] == "wiki":
        return unquote(path_parts[2])
    raise ValueError(f"Invalid Wikipedia URL format: {wikipedia_url}")


def fetch_wikipedia_content(
    wikipedia_url: str, timeout: float = 30.0
) -> tuple[str, str, str]:
    """
    Fetch Wikipedia article content.
    
    Args:
        wikipedia_url: Full Wikipedia URL
        timeout: Request timeout in seconds
    
    Returns:
        Tuple of (article_title, article_text, html_content)
    
    Raises:
        httpx.HTTPError: If the request fails
        ValueError: If the URL is invalid or article not found
    """
    _rate_limiter.wait()
    
    article_title = _extract_article_title_from_url(wikipedia_url)
    
    headers = {"User-Agent": USER_AGENT}
    
    params = {
        "action": "parse",
        "page": article_title,
        "format": "json",
        "prop": "text",
        "disableeditsection": "1",
        "disabletoc": "1",
    }
    
    with httpx.Client(timeout=timeout) as client:
        response = client.get(WIKIPEDIA_API, headers=headers, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if "error" in data:
            raise ValueError(f"Wikipedia API error: {data['error'].get('info', 'Unknown error')}")
        
        if "parse" not in data or "text" not in data["parse"]:
            raise ValueError(f"Invalid Wikipedia API response for article: {article_title}")
        
        html_content = data["parse"]["text"]["*"]
        clean_text = clean_html_to_text(
            html_content,
            remove_tags=["sup"],
            remove_classes=["reference-text"]
        )
        
        return article_title, clean_text, html_content


def format_as_document(
    article_title: str, article_text: str, entity: WikidataEntity
) -> str:
    """
    Format Wikipedia article with metadata header for File Search ingestion.
    
    Args:
        article_title: Wikipedia article title
        article_text: Clean article text
        entity: WikidataEntity with metadata
    
    Returns:
        Formatted document with metadata header
    """
    header = build_metadata_header(
        "Wikipedia",
        entity,
        {
            "Article": article_title,
            "Entity ID": entity.id,
            "Entity Name": entity.label,
            "URL": entity.wikipedia_url or 'N/A',
            "Description": entity.description or 'N/A',
        }
    )
    
    return header + article_text


def fetch_wikipedia_source(entity: WikidataEntity, timeout: float = 30.0) -> tuple[Source, str, bytes]:
    """
    Fetch Wikipedia article as a Source object with content.
    
    Args:
        entity: WikidataEntity with wikipedia_url populated
        timeout: Request timeout in seconds
    
    Returns:
        Tuple of (Source object, article_content, html_bytes)
    
    Raises:
        ValueError: If entity has no Wikipedia URL
        httpx.HTTPError: If the request fails
    """
    logger.info(f"Fetching Wikipedia source for {entity.label} ({entity.id})")
    
    if not entity.wikipedia_url:
        raise ValueError(f"Entity {entity.id} has no Wikipedia URL")
    
    article_title, article_text, html_content = fetch_wikipedia_content(entity.wikipedia_url, timeout)
    
    source = Source(
        source_id=generate_source_id(entity.wikipedia_url, "wiki"),
        type="wikipedia",
        title=article_title,
        authors=["Wikipedia contributors"],
        publication="Wikipedia",
        publication_date=None,  # Wikipedia doesn't have a single publication date
        url=entity.wikipedia_url,
        retrieved_at=get_iso_timestamp(),
        credibility_score=0.75,  # Wikipedia is generally credible but not primary
        is_primary_source=False,
    )
    
    # Format content with metadata header
    content = format_as_document(article_title, article_text, entity)
    
    # Convert HTML to bytes for storage
    html_bytes = html_content.encode('utf-8')
    
    logger.info(f"Created Wikipedia source: {source.source_id} - {article_title}")
    
    return source, content, html_bytes

