"""Extract and analyze relationships between Wikidata entities."""

from typing import Any

from .client import execute_sparql_query, get_entity
from .models import Relationship


def get_direct_relationships(
    entity_id1: str,
    entity_id2: str,
    timeout: float = 30.0,
) -> list[Relationship]:
    """
    Find direct relationships between two Wikidata entities.

    This function queries Wikidata for properties that directly connect
    the two entities in either direction (entity1 -> entity2 or entity2 -> entity1).

    Args:
        entity_id1: First entity ID (e.g., "Q41421")
        entity_id2: Second entity ID (e.g., "Q134183")
        timeout: Request timeout in seconds

    Returns:
        List of Relationship objects connecting the two entities

    Raises:
        httpx.HTTPError: If the request fails
        ValueError: If the query fails or returns invalid data
    """
    # Fetch entity labels for context
    entity1 = get_entity(entity_id1)
    entity2 = get_entity(entity_id2)

    # SPARQL query to find direct relationships between the two entities
    # SPARQL query explanation:
    # - Find all properties (?prop) that directly connect the two entities
    # - Check both directions: entity1 -> entity2 AND entity2 -> entity1
    # - UNION combines both directions into a single result set
    # - BIND marks direction as "forward" or "reverse" to track relationship direction
    # - FILTER ensures we only get actual properties (not metadata/system properties)
    # - SERVICE wikibase:label automatically fetches human-readable labels
    query = f"""
    SELECT ?prop ?propLabel ?direction WHERE {{
      {{
        # Forward direction: entity1 has property pointing to entity2
        wd:{entity_id1} ?prop wd:{entity_id2} .
        BIND("forward" AS ?direction)
      }}
      UNION
      {{
        # Reverse direction: entity2 has property pointing to entity1
        wd:{entity_id2} ?prop wd:{entity_id1} .
        BIND("reverse" AS ?direction)
      }}
      
      # Filter to only direct property namespace (exclude metadata/system properties)
      FILTER(STRSTARTS(STR(?prop), "http://www.wikidata.org/prop/direct/"))
      
      # Fetch English labels for properties
      SERVICE wikibase:label {{ 
        bd:serviceParam wikibase:language "en". 
      }}
    }}
    """

    results = execute_sparql_query(query, timeout=timeout)

    relationships = []
    for result in results:
        # Extract property ID from URI (e.g., http://www.wikidata.org/prop/direct/P1327 -> P1327)
        prop_uri = result.get("prop", {}).get("value", "")
        property_id = prop_uri.split("/")[-1] if "/" in prop_uri else ""

        property_label = result.get("propLabel", {}).get("value", property_id)
        direction = result.get("direction", {}).get("value", "forward")

        # Determine source and target based on direction
        if direction == "forward":
            source_id = entity_id1
            source_label = entity1.label
            target_id = entity_id2
            target_label = entity2.label
        else:
            source_id = entity_id2
            source_label = entity2.label
            target_id = entity_id1
            target_label = entity1.label

        relationship = Relationship(
            source_entity_id=source_id,
            source_entity_label=source_label,
            property_id=property_id,
            property_label=property_label,
            target_entity_id=target_id,
            target_entity_label=target_label,
        )

        relationships.append(relationship)

    return relationships


def get_shared_properties(
    entity_id1: str,
    entity_id2: str,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """
    Find properties that both entities share (e.g., both participated in same event).

    This is useful for finding indirect connections like shared competitions,
    shared workplaces, or shared time periods.

    Args:
        entity_id1: First entity ID
        entity_id2: Second entity ID
        timeout: Request timeout in seconds

    Returns:
        Dictionary of shared properties and their values

    Raises:
        httpx.HTTPError: If the request fails
    """
    # SPARQL query explanation:
    # - Find properties where BOTH entities share the SAME value
    # - Example: Both competed in "NBA Finals 1991" or both have occupation "basketball player"
    # - This reveals indirect connections (shared events, categories, locations, etc.)
    # - Only returns entity values (Q-items), not literal strings or dates
    # - Useful for context: "they competed in the same league", "they won the same award"
    query = f"""
    SELECT ?prop ?propLabel ?value ?valueLabel WHERE {{
      # Both entities must have the same property pointing to the same value
      wd:{entity_id1} ?prop ?value .
      wd:{entity_id2} ?prop ?value .
      
      # Filter to only direct property namespace
      FILTER(STRSTARTS(STR(?prop), "http://www.wikidata.org/prop/direct/"))
      
      # Filter to entity values only (Q-items), excludes strings/dates/coordinates
      FILTER(STRSTARTS(STR(?value), "http://www.wikidata.org/entity/Q"))
      
      # Fetch English labels for properties and values
      SERVICE wikibase:label {{ 
        bd:serviceParam wikibase:language "en". 
      }}
    }}
    LIMIT 50
    """

    results = execute_sparql_query(query, timeout=timeout)

    shared_props: dict[str, Any] = {}
    for result in results:
        prop_uri = result.get("prop", {}).get("value", "")
        property_id = prop_uri.split("/")[-1] if "/" in prop_uri else ""
        property_label = result.get("propLabel", {}).get("value", property_id)

        value_uri = result.get("value", {}).get("value", "")
        value_id = value_uri.split("/")[-1] if "/" in value_uri else ""
        value_label = result.get("valueLabel", {}).get("value", value_id)

        if property_id not in shared_props:
            shared_props[property_id] = {
                "label": property_label,
                "values": [],
            }

        shared_props[property_id]["values"].append(
            {"id": value_id, "label": value_label}
        )

    return shared_props
