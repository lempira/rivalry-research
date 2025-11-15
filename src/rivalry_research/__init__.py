"""Rivalry Research - Analyze rivalrous relationships using Wikidata and AI."""

from .models import (
    EntitySearchResult,
    Relationship,
    RivalryAnalysis,
    RivalryFact,
    WikidataEntity,
)
from .relationships import get_direct_relationships, get_shared_properties
from .rivalry_agent import analyze_rivalry as analyze_rivalry_with_data
from .search import get_person_by_id, search_person

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
    "RivalryFact",
    "RivalryAnalysis",
    # Advanced functions
    "get_direct_relationships",
    "get_shared_properties",
]


def analyze_rivalry(entity_id1: str, entity_id2: str) -> RivalryAnalysis:
    """
    Analyze the rivalry between two people using Wikidata and AI.

    This is a high-level convenience function that orchestrates the entire workflow:
    1. Fetches both entities from Wikidata
    2. Extracts direct relationships between them
    3. Uses AI to analyze and structure rivalry information

    Args:
        entity_id1: First person's Wikidata entity ID (e.g., "Q41421")
        entity_id2: Second person's Wikidata entity ID (e.g., "Q134183")

    Returns:
        RivalryAnalysis with structured rivalry data including facts, scores, and summary

    Raises:
        ValueError: If entities are not found
        httpx.HTTPError: If API requests fail
        Exception: If AI analysis fails

    Example:
        >>> # Michael Jordan vs Magic Johnson
        >>> analysis = analyze_rivalry("Q41421", "Q134183")
        >>> print(f"Rivalry exists: {analysis.rivalry_exists}")
        >>> print(f"Rivalry score: {analysis.rivalry_score}")
        >>> for fact in analysis.facts:
        ...     print(f"- {fact.fact}")
    """
    # Fetch both entities
    entity1 = get_person_by_id(entity_id1)
    entity2 = get_person_by_id(entity_id2)

    # Get direct relationships
    relationships = get_direct_relationships(entity_id1, entity_id2)

    # Analyze with AI
    return analyze_rivalry_with_data(entity1, entity2, relationships)
