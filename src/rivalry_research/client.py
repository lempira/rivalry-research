"""Wikidata API client for SPARQL and REST API interactions."""

import time
from typing import Any

import httpx

from .models import EntitySearchResult, WikidataEntity

# API endpoints
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
MEDIAWIKI_API = "https://www.wikidata.org/w/api.php"
ENTITY_DATA_URL = "https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json"

# User agent for Wikidata compliance
USER_AGENT = "RivalryResearch/0.1.0 (https://github.com/user/rivalry-research)"

# Rate limiting
_last_request_time = 0.0
_min_request_interval = 0.1  # 100ms between requests


def _rate_limit() -> None:
    """Enforce rate limiting between requests."""
    global _last_request_time
    now = time.time()
    time_since_last = now - _last_request_time
    if time_since_last < _min_request_interval:
        time.sleep(_min_request_interval - time_since_last)
    _last_request_time = time.time()


def execute_sparql_query(query: str, timeout: float = 30.0) -> list[dict[str, Any]]:
    """
    Execute a SPARQL query against Wikidata Query Service.

    Args:
        query: SPARQL query string
        timeout: Request timeout in seconds

    Returns:
        List of result bindings as dictionaries

    Raises:
        httpx.HTTPError: If the request fails
        ValueError: If the response format is invalid
    """
    _rate_limit()

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/sparql-results+json",
    }

    params = {"query": query, "format": "json"}

    with httpx.Client(timeout=timeout) as client:
        response = client.get(SPARQL_ENDPOINT, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()
        if "results" not in data or "bindings" not in data["results"]:
            raise ValueError("Invalid SPARQL response format")

        return data["results"]["bindings"]


def search_entities(
    search_term: str,
    entity_type: str | None = None,
    language: str = "en",
    limit: int = 10,
    timeout: float = 10.0,
) -> list[EntitySearchResult]:
    """
    Search for Wikidata entities by name.

    Args:
        search_term: The search query (e.g., person's name)
        entity_type: Optional filter by entity type (e.g., "Q5" for humans)
        language: Language code for results (default: "en")
        limit: Maximum number of results to return
        timeout: Request timeout in seconds

    Returns:
        List of EntitySearchResult objects for disambiguation

    Raises:
        httpx.HTTPError: If the request fails
    """
    _rate_limit()

    headers = {"User-Agent": USER_AGENT}

    params: dict[str, Any] = {
        "action": "wbsearchentities",
        "search": search_term,
        "language": language,
        "limit": limit,
        "format": "json",
    }

    if entity_type:
        params["type"] = "item"

    with httpx.Client(timeout=timeout) as client:
        response = client.get(MEDIAWIKI_API, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()

        if "search" not in data:
            return []

        results = []
        for item in data["search"]:
            result = EntitySearchResult(
                id=item["id"],
                label=item.get("label", ""),
                description=item.get("description"),
                match_score=item.get("match", {}).get("score") if "match" in item else None,
            )
            results.append(result)

        return results


def get_entity(entity_id: str, timeout: float = 10.0) -> WikidataEntity:
    """
    Fetch full entity data from Wikidata.

    Args:
        entity_id: Wikidata entity ID (e.g., "Q42")
        timeout: Request timeout in seconds

    Returns:
        WikidataEntity with full entity data

    Raises:
        httpx.HTTPError: If the request fails
        ValueError: If entity not found or invalid response
    """
    _rate_limit()

    headers = {"User-Agent": USER_AGENT}

    params = {
        "action": "wbgetentities",
        "ids": entity_id,
        "format": "json",
        "languages": "en",
    }

    with httpx.Client(timeout=timeout) as client:
        response = client.get(MEDIAWIKI_API, headers=headers, params=params)
        response.raise_for_status()

        data = response.json()

        if "entities" not in data or entity_id not in data["entities"]:
            raise ValueError(f"Entity {entity_id} not found")

        entity_data = data["entities"][entity_id]

        if "missing" in entity_data:
            raise ValueError(f"Entity {entity_id} does not exist")

        # Extract label
        label = ""
        if "labels" in entity_data and "en" in entity_data["labels"]:
            label = entity_data["labels"]["en"]["value"]

        # Extract description
        description = None
        if "descriptions" in entity_data and "en" in entity_data["descriptions"]:
            description = entity_data["descriptions"]["en"]["value"]

        # Extract aliases
        aliases = []
        if "aliases" in entity_data and "en" in entity_data["aliases"]:
            aliases = [alias["value"] for alias in entity_data["aliases"]["en"]]

        # Get all claims
        claims = entity_data.get("claims", {})
        
        return WikidataEntity(
            id=entity_id,
            label=label,
            description=description,
            aliases=aliases,
            claims=claims,
        )
