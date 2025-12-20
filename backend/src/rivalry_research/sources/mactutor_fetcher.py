"""Fetch biographies from MacTutor History of Mathematics Archive."""

import logging

import httpx
from bs4 import BeautifulSoup

from ..models import WikidataEntity, Source
from .utils import generate_source_id, get_iso_timestamp
from .source_fetcher_utils import (
    RateLimiter,
    build_metadata_header,
    clean_html_to_text,
    is_mathematician,
)

logger = logging.getLogger(__name__)

# MacTutor base URLs
MACTUTOR_BASE = "https://mathshistory.st-andrews.ac.uk"
MACTUTOR_SEARCH = f"{MACTUTOR_BASE}/Search/historysearch.cgi"

# User agent
USER_AGENT = "RivalryResearch/0.1.0 (https://github.com/user/rivalry-research)"

# Rate limiting
_rate_limiter = RateLimiter(2.0, "MacTutor")


def _search_biography(entity_name: str, timeout: float = 30.0) -> str | None:
    """
    Search MacTutor for a mathematician's biography page.
    
    Args:
        entity_name: Name of mathematician to search for
        timeout: Request timeout in seconds
    
    Returns:
        Biography URL if found, None otherwise
    """
    _rate_limiter.wait()
    
    headers = {"User-Agent": USER_AGENT}
    
    try:
        params = {
            "CATEGORY": "FullAlpha",
            "WORDS": entity_name,
        }
        
        with httpx.Client(timeout=timeout) as client:
            response = client.get(MACTUTOR_SEARCH, headers=headers, params=params, follow_redirects=True)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Look for biography links in search results
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                if "/Biographies/" in href and entity_name.split()[0].lower() in link.text.lower():
                    # Construct full URL
                    if href.startswith("http"):
                        return href
                    elif href.startswith("/"):
                        return f"{MACTUTOR_BASE}{href}"
                    else:
                        return f"{MACTUTOR_BASE}/Biographies/{href}"
            
    except Exception as e:
        logger.debug(f"MacTutor search failed for {entity_name}: {e}")
    
    return None


def _fetch_biography_content(url: str, timeout: float = 30.0) -> tuple[str, str, str]:
    """
    Fetch and parse MacTutor biography page.
    
    Args:
        url: Biography page URL
        timeout: Request timeout in seconds
    
    Returns:
        Tuple of (title, clean_text, html_content)
    
    Raises:
        httpx.HTTPError: If request fails
        ValueError: If page cannot be parsed
    """
    _rate_limiter.wait()
    
    headers = {"User-Agent": USER_AGENT}
    
    with httpx.Client(timeout=timeout) as client:
        response = client.get(url, headers=headers, follow_redirects=True)
        response.raise_for_status()
        
        html_content = response.text
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Extract title (usually in h2 or title tag)
        title_elem = soup.find("h2") or soup.find("h1") or soup.find("title")
        title = title_elem.get_text().strip() if title_elem else "MacTutor Biography"
        
        # Clean HTML to text, removing navigation and non-content elements
        clean_text = clean_html_to_text(
            html_content,
            remove_tags=["nav", "aside", "header", "footer"],
            remove_classes=["navigation", "sidebar", "menu"]
        )
        
        if len(clean_text.strip()) < 100:
            raise ValueError("Biography content too short or extraction failed")
        
        return title, clean_text, html_content


def format_as_document(
    title: str, biography_text: str, entity: WikidataEntity, url: str
) -> str:
    """
    Format MacTutor biography with metadata header.
    
    Args:
        title: Biography title
        biography_text: Clean biography text
        entity: WikidataEntity with metadata
        url: Biography URL
    
    Returns:
        Formatted document with metadata header
    """
    header = build_metadata_header(
        "MacTutor History of Mathematics Archive",
        entity,
        {
            "Type": "Biographical Entry",
            "Title": title,
            "URL": url,
        }
    )
    
    return header + biography_text


def fetch_mactutor_source(
    entity: WikidataEntity, timeout: float = 30.0
) -> tuple[Source, str, bytes] | None:
    """
    Fetch MacTutor biography for a mathematician entity.
    
    Only fetches for entities with mathematics-related occupations.
    
    Args:
        entity: WikidataEntity to search for
        timeout: Request timeout in seconds
    
    Returns:
        Tuple of (Source object, content, html_bytes) or None if not found
    
    Examples:
        >>> source, content, html = fetch_mactutor_source(newton_entity)
        >>> print(source.title)
        'Isaac Newton'
    """
    logger.info(f"Searching MacTutor for {entity.label} ({entity.id})")
    
    # Only fetch for mathematicians
    if not is_mathematician(entity):
        logger.debug(f"Entity {entity.label} is not math-related, skipping MacTutor")
        return None
    
    # Search for biography
    biography_url = _search_biography(entity.label, timeout)
    if not biography_url:
        logger.info(f"No MacTutor biography found for {entity.label}")
        return None
    
    # Fetch and parse biography
    try:
        title, clean_text, html_content = _fetch_biography_content(biography_url, timeout)
    except Exception as e:
        logger.warning(f"Failed to fetch MacTutor biography for {entity.label}: {e}")
        return None
    
    # Create Source object
    source = Source(
        source_id=generate_source_id(biography_url, "mactutor"),
        type="mactutor_biography",
        title=title,
        authors=["MacTutor History of Mathematics Archive"],
        publication="MacTutor History of Mathematics Archive",
        publication_date=None,
        url=biography_url,
        retrieved_at=get_iso_timestamp(),
        credibility_score=0.90,  # Scholarly but secondary source
        is_primary_source=False,
    )
    
    # Format content
    content = format_as_document(title, clean_text, entity, biography_url)
    html_bytes = html_content.encode('utf-8')
    
    logger.info(f"Fetched MacTutor biography: {source.title}")
    return source, content, html_bytes

