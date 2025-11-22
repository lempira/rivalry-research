"""Source credibility scoring and classification."""

import logging

logger = logging.getLogger(__name__)

# Credibility scores by source type (0.0 - 1.0)
SOURCE_CREDIBILITY_SCORES = {
    "academic_paper": 0.95,
    "peer_reviewed_journal": 0.95,
    "book": 0.85,
    "news_article": 0.80,
    "encyclopedia": 0.85,
    "wikipedia": 0.75,
    "archive": 0.80,
    "government": 0.90,
    "biography": 0.80,
    "interview": 0.85,
    "letter": 0.90,
    "publication": 0.85,
    "web": 0.50,
    "unknown": 0.50,
}


def calculate_credibility_score(source_type: str, publication: str | None = None) -> float:
    """
    Calculate credibility score for a source.
    
    Args:
        source_type: Type of source (academic_paper, news_article, etc.)
        publication: Publication venue (optional, can boost score for reputable venues)
    
    Returns:
        Credibility score between 0.0 and 1.0
    """
    base_score = SOURCE_CREDIBILITY_SCORES.get(source_type.lower(), 0.50)
    
    # Boost for reputable publications
    if publication:
        publication_lower = publication.lower()
        reputable_publications = [
            "nature", "science", "cell", "lancet", "nejm",
            "new york times", "washington post", "guardian", "bbc",
            "oxford", "cambridge", "harvard", "mit press",
            "britannica", "stanford"
        ]
        if any(pub in publication_lower for pub in reputable_publications):
            base_score = min(1.0, base_score + 0.05)
    
    return base_score


def is_primary_source(source_type: str, authors: list[str] | None = None) -> bool:
    """
    Determine if a source is a primary source.
    
    Primary sources are firsthand accounts or original works (letters, interviews,
    original publications, etc.). Secondary sources analyze/interpret primary sources.
    
    Args:
        source_type: Type of source
        authors: List of authors (can help determine if autobiographical)
    
    Returns:
        True if primary source, False otherwise
    """
    primary_types = {
        "letter",
        "interview",
        "autobiography",
        "diary",
        "manuscript",
        "original_publication",
        "speech",
        "memoir",
    }
    
    return source_type.lower() in primary_types


def rank_sources_by_credibility(sources: list[dict]) -> list[dict]:
    """
    Sort sources by credibility score (highest first).
    
    Args:
        sources: List of source dictionaries with 'credibility_score' field
    
    Returns:
        Sorted list of sources
    """
    return sorted(sources, key=lambda s: s.get("credibility_score", 0.0), reverse=True)

