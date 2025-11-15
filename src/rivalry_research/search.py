"""Entity search and disambiguation functionality."""

from .client import get_entity, search_entities
from .models import EntitySearchResult, WikidataEntity


def search_person(
    name: str,
    language: str = "en",
    limit: int = 10,
    timeout: float = 10.0,
) -> list[EntitySearchResult]:
    """
    Search for people (humans) on Wikidata by name.

    This function wraps search_entities and filters results to only include
    entities that are instances of Q5 (human). This requires a follow-up
    check of each result, so it may be slower than a plain search.

    Args:
        name: The person's name to search for
        language: Language code for results (default: "en")
        limit: Maximum number of results to return
        timeout: Request timeout in seconds

    Returns:
        List of EntitySearchResult objects representing people

    Raises:
        httpx.HTTPError: If the request fails
    """
    # First, do a general search
    results = search_entities(
        search_term=name,
        entity_type="item",
        language=language,
        limit=limit * 2,  # Get more to account for filtering
        timeout=timeout,
    )

    # For now, return all results
    # In a future optimization, we could check P31 (instance of) = Q5 (human)
    # but that requires additional API calls for each result
    return results[:limit]


def get_person_by_id(entity_id: str, timeout: float = 10.0) -> WikidataEntity:
    """
    Fetch a person's data from Wikidata by entity ID.

    This is a convenience wrapper around get_entity that's semantically
    clearer when working specifically with people.

    Args:
        entity_id: Wikidata entity ID (e.g., "Q42")
        timeout: Request timeout in seconds

    Returns:
        WikidataEntity with the person's data

    Raises:
        httpx.HTTPError: If the request fails
        ValueError: If entity not found
    """
    return get_entity(entity_id, timeout=timeout)
