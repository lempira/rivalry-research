"""Shared utilities for source fetchers."""

import logging
import re
import time
from typing import Any

from bs4 import BeautifulSoup

from ..models import WikidataEntity

logger = logging.getLogger(__name__)


# ============================================================================
# Rate Limiting
# ============================================================================

class RateLimiter:
    """
    Per-source rate limiter with configurable intervals.
    
    Each source gets its own rate limiter instance to track timing independently.
    """
    
    def __init__(self, min_interval: float, name: str = "source"):
        """
        Initialize rate limiter.
        
        Args:
            min_interval: Minimum seconds between requests
            name: Name of the source (for logging)
        """
        self.min_interval = min_interval
        self.name = name
        self._last_request_time = 0.0
    
    def wait(self) -> None:
        """Enforce rate limit by sleeping if needed."""
        now = time.time()
        time_since_last = now - self._last_request_time
        
        if time_since_last < self.min_interval:
            sleep_time = self.min_interval - time_since_last
            logger.debug(f"Rate limiting {self.name}: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        self._last_request_time = time.time()
    
    def __call__(self) -> None:
        """Allow using as decorator or direct call."""
        self.wait()


# ============================================================================
# Primary Source Detection
# ============================================================================

def is_entity_author(
    entity: WikidataEntity,
    authors: list[str],
) -> bool:
    """
    Check if entity is an author in the list of authors.
    
    Uses fuzzy matching: checks if entity name appears in author name
    or vice versa (handles "Isaac Newton" vs "Newton, Isaac").
    
    Args:
        entity: WikidataEntity to check
        authors: List of author names
    
    Returns:
        True if entity appears to be an author
    
    Examples:
        >>> entity = WikidataEntity(label="Isaac Newton", ...)
        >>> is_entity_author(entity, ["Newton, I.", "Hooke, R."])
        True
        >>> is_entity_author(entity, ["Einstein, A.", "Planck, M."])
        False
    """
    entity_name_lower = entity.label.lower()
    
    for author in authors:
        author_lower = author.lower()
        # Bidirectional substring match handles name variations
        if entity_name_lower in author_lower or author_lower in entity_name_lower:
            return True
    
    return False


# ============================================================================
# Document Formatting
# ============================================================================

def build_metadata_header(
    source_name: str,
    entity: WikidataEntity,
    fields: dict[str, Any],
) -> str:
    """
    Build standardized YAML-style metadata header for source documents.
    
    Args:
        source_name: Name of the source (e.g., "Wikipedia", "Google Scholar")
        entity: WikidataEntity being researched
        fields: Additional metadata fields specific to this source
    
    Returns:
        Formatted metadata header with triple-dash delimiters
    
    Examples:
        >>> build_metadata_header(
        ...     "Wikipedia",
        ...     entity,
        ...     {"Article": "Isaac_Newton", "URL": "https://..."}
        ... )
        ---
        Source: Wikipedia
        Article: Isaac_Newton
        URL: https://...
        Related Entity: Isaac Newton (Q935)
        ---
        
    """
    lines = ["---", f"Source: {source_name}"]
    
    # Add source-specific fields in order
    for key, value in fields.items():
        lines.append(f"{key}: {value}")
    
    # Always include related entity
    lines.append(f"Related Entity: {entity.label} ({entity.id})")
    lines.append("---")
    lines.append("")  # Blank line after header
    
    return "\n".join(lines)


# ============================================================================
# HTML Cleaning
# ============================================================================

def clean_html_to_text(
    html: str,
    remove_tags: list[str] | None = None,
    remove_classes: list[str] | None = None,
) -> str:
    """
    Convert HTML to clean plain text with configurable element removal.
    
    Args:
        html: Raw HTML content
        remove_tags: Additional HTML tags to remove (beyond script/style)
        remove_classes: CSS class names to remove
    
    Returns:
        Clean plain text
    
    Examples:
        >>> # Wikipedia-style cleaning
        >>> clean_html_to_text(
        ...     html,
        ...     remove_tags=["sup"],
        ...     remove_classes=["reference-text"]
        ... )
        
        >>> # MacTutor-style cleaning (navigation, sidebars)
        >>> clean_html_to_text(
        ...     html,
        ...     remove_tags=["nav", "aside"],
        ...     remove_classes=["sidebar", "navigation"]
        ... )
    """
    soup = BeautifulSoup(html, "html.parser")
    
    # Always remove script and style
    default_remove = ["script", "style"]
    all_remove_tags = default_remove + (remove_tags or [])
    
    for tag in all_remove_tags:
        for element in soup.find_all(tag):
            element.decompose()
    
    # Remove elements with specific classes
    if remove_classes:
        for class_name in remove_classes:
            for element in soup.find_all(class_=class_name):
                element.decompose()
    
    # Get text
    text = soup.get_text()
    
    # Clean up citation brackets [1], [2], etc.
    text = re.sub(r"\[\d+\]", "", text)
    
    # Clean up excessive whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)  # Max 2 newlines
    text = re.sub(r" {2,}", " ", text)       # Single spaces
    text = re.sub(r"\t+", " ", text)         # Tabs to spaces
    
    return text.strip()


# ============================================================================
# Search Query Building
# ============================================================================

# Keyword sets for different search types
RIVALRY_KEYWORDS = (
    "dispute OR controversy OR conflict OR debate OR priority dispute OR "
    "disagreement OR rivalry OR criticism OR opposition"
)

BIOGRAPHICAL_KEYWORDS = (
    "biography OR life OR career OR obituary OR biographical"
)


def build_search_query(
    entity: WikidataEntity,
    keywords: str = RIVALRY_KEYWORDS,
    include_description: bool = True,
) -> str:
    """
    Build search query for entity with optional keywords.
    
    Args:
        entity: WikidataEntity to search for
        keywords: Boolean query keywords to append (OR-separated)
        include_description: Include entity description in query
    
    Returns:
        Formatted search query string
    
    Examples:
        >>> build_search_query(entity, RIVALRY_KEYWORDS)
        '"Isaac Newton" physicist (dispute OR controversy OR ...)'
        
        >>> build_search_query(entity, BIOGRAPHICAL_KEYWORDS)
        '"Isaac Newton" physicist (biography OR life OR ...)'
    """
    query = f'"{entity.label}"'
    
    if include_description and entity.description:
        query += f" {entity.description}"
    
    if keywords:
        query += f" ({keywords})"
    
    return query


# ============================================================================
# Entity Occupation Filtering
# ============================================================================

# Wikidata occupation IDs for different domains
MATHEMATICIAN_OCCUPATIONS = {
    'Q170790',    # mathematician
    'Q169470',    # physicist (often has math)
    'Q11063',     # astronomer (often has math)
    'Q18714441',  # logician
    'Q22988604',  # statistician
}

PHILOSOPHER_OCCUPATIONS = {
    'Q4964182',   # philosopher
    'Q11165895',  # political philosopher
    'Q15978133',  # moral philosopher
    'Q16266196',  # analytic philosopher
}

SCIENTIST_OCCUPATIONS = {
    'Q901',       # scientist
    'Q169470',    # physicist
    'Q11063',     # astronomer
    'Q593644',    # chemist
    'Q864503',    # biologist
}


def has_occupation(
    entity: WikidataEntity,
    occupation_ids: set[str],
) -> bool:
    """
    Check if entity has any of the specified occupations.
    
    Args:
        entity: WikidataEntity to check
        occupation_ids: Set of Wikidata occupation IDs
    
    Returns:
        True if entity has at least one matching occupation
    
    Examples:
        >>> has_occupation(newton_entity, MATHEMATICIAN_OCCUPATIONS)
        True
        >>> has_occupation(obama_entity, MATHEMATICIAN_OCCUPATIONS)
        False
    """
    if not entity.occupation:
        return False
    
    return any(occ_id in occupation_ids for occ_id in entity.occupation)


def is_mathematician(entity: WikidataEntity) -> bool:
    """Check if entity is a mathematician or related profession."""
    return has_occupation(entity, MATHEMATICIAN_OCCUPATIONS)


def is_philosopher(entity: WikidataEntity) -> bool:
    """Check if entity is a philosopher."""
    return has_occupation(entity, PHILOSOPHER_OCCUPATIONS)


def is_scientist(entity: WikidataEntity) -> bool:
    """Check if entity is a scientist."""
    return has_occupation(entity, SCIENTIST_OCCUPATIONS)

