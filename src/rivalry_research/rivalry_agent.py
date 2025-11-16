"""Pydantic-AI agent for analyzing rivalrous relationships."""

import os
from typing import Any

from google.genai import types
from pydantic_ai import Agent

from .models import RivalryAnalysis, WikidataEntity, Relationship


def extract_claim_values(claims: dict[str, Any], property_id: str, limit: int = 5) -> list[str]:
    """
    Extract human-readable values from Wikidata claims for a specific property.
    
    Args:
        claims: The claims dictionary from a WikidataEntity
        property_id: The property ID to extract (e.g., 'P106' for occupation)
        limit: Maximum number of values to return
    
    Returns:
        List of string values (labels or formatted values)
    """
    if property_id not in claims:
        return []
    
    values = []
    for claim in claims[property_id][:limit]:
        try:
            mainsnak = claim.get('mainsnak', {})
            datavalue = mainsnak.get('datavalue', {})
            datatype = datavalue.get('type')
            
            if datatype == 'wikibase-entityid':
                # Entity reference - try to get label
                value_data = datavalue.get('value', {})
                entity_id = value_data.get('id')
                if entity_id:
                    values.append(entity_id)  # We don't have labels, just use ID for now
            elif datatype == 'time':
                # Date value
                time_value = datavalue.get('value', {}).get('time', '')
                # Format: +1643-01-04T00:00:00Z -> 1643
                if time_value:
                    year = time_value.split('-')[0].replace('+', '')
                    values.append(year)
            elif datatype == 'string':
                # String value
                string_value = datavalue.get('value', '')
                if string_value:
                    values.append(string_value)
        except (KeyError, AttributeError, IndexError):
            continue
    
    return values


def format_entity_details(entity: WikidataEntity) -> str:
    """
    Format key details from a WikidataEntity for AI context.
    
    Args:
        entity: WikidataEntity with claims data
    
    Returns:
        Formatted string with key biographical/professional details
    """
    details = []
    
    # Birth/death dates
    birth_dates = extract_claim_values(entity.claims, 'P569', limit=1)
    if birth_dates:
        details.append(f"Born: {birth_dates[0]}")
    
    death_dates = extract_claim_values(entity.claims, 'P570', limit=1)
    if death_dates:
        details.append(f"Died: {death_dates[0]}")
    
    # Occupations
    occupations = extract_claim_values(entity.claims, 'P106', limit=3)
    if occupations:
        details.append(f"Occupation(s): {', '.join(occupations)}")
    
    # Field of work
    fields = extract_claim_values(entity.claims, 'P101', limit=3)
    if fields:
        details.append(f"Field(s): {', '.join(fields)}")
    
    # Notable works or discoveries
    notable_works = extract_claim_values(entity.claims, 'P800', limit=3)
    if notable_works:
        details.append(f"Notable work(s): {', '.join(notable_works)}")
    
    discoveries = extract_claim_values(entity.claims, 'P61', limit=3)
    if discoveries:
        details.append(f"Discovered/Invented: {', '.join(discoveries)}")
    
    return '\n- '.join([''] + details) if details else ''

# System prompt for the rivalry analysis agent
SYSTEM_PROMPT = """You are a rivalry analysis expert that examines relationships between people using both structured Wikidata facts and biographical documents.

Your task is to:
1. Analyze the provided entity data, direct relationships, and shared properties from Wikidata
2. Query biographical documents (when available) for timeline events, interactions, and narrative context
3. Determine if a rivalrous relationship exists (competition, conflict, controversy)
4. Extract specific factual incidents or events with dates that demonstrate the rivalry
5. Be conservative - only mark rivalry_exists=True if there's clear evidence

Guidelines:
- Focus on factual, verifiable information from Wikidata and biographical sources
- Look for indicators: sports rivalries, business competition, political opposition, artistic/cultural conflicts, priority disputes
- Extract temporal information when available (dates, time periods) from both sources
- Assign rivalry_score based on intensity: 0.0-0.3 (weak/indirect), 0.4-0.6 (moderate), 0.7-1.0 (intense/well-documented)
- If no rivalry is evident, set rivalry_exists=False and explain why in the summary
- Each fact should be concise and specific, with dates when available

Using Wikidata Structured Data:
- Shared properties reveal implicit connections even without direct relationships
- Look for competitive overlap: same field of work, same achievements, same era
- Similar accomplishments in the same domain often indicate rivalry (e.g., both invented calculus)
- Temporal overlap (same time period) establishes they were contemporaries
- Shared institutions/awards/fields provide context for potential conflict

Using Biographical Documents (File Search):
- Query for timeline events, key dates, achievements, publications
- Look for mentions of conflicts, competitions, disputes, controversies
- Extract context about interactions or lack thereof
- Find evidence of priority disputes or competing claims
- Use document sources to support facts with citations

Return a structured analysis with rivalry determination, score, summary, and specific dated facts."""

# Get model from environment variable, default to Gemini
MODEL = os.getenv("RIVALRY_MODEL", "google-gla:gemini-2.5-flash")

# Create the rivalry analysis agent
# The agent will return a RivalryAnalysis model with structured output
rivalry_agent = Agent(
    MODEL,
    output_type=RivalryAnalysis,
    system_prompt=SYSTEM_PROMPT,
)


def analyze_rivalry(
    entity1: WikidataEntity,
    entity2: WikidataEntity,
    relationships: list[Relationship],
    shared_properties: dict[str, Any],
    store_name: str | None = None,
) -> RivalryAnalysis:
    """
    Analyze the rivalry between two entities using AI.

    This function takes entity data, relationships, and shared properties from Wikidata
    and uses an AI agent to determine if a rivalry exists, rate its intensity, and
    extract specific facts about the rivalry.
    
    When store_name is provided, the agent can query biographical documents via File Search
    to enrich the analysis with timeline events and narrative context.

    The AI model used can be configured via the RIVALRY_MODEL environment variable.
    Defaults to "google-gla:gemini-2.5-flash" if not set.

    Args:
        entity1: First entity (person) data from Wikidata
        entity2: Second entity (person) data from Wikidata
        relationships: List of direct relationships between the entities
        shared_properties: Dictionary of properties both entities share
        store_name: Optional File Search store name for biographical document access

    Returns:
        RivalryAnalysis with structured rivalry data

    Raises:
        Exception: If the AI model fails or returns invalid data

    Example:
        >>> # Wikidata only
        >>> entity1 = get_entity("Q41421")
        >>> entity2 = get_entity("Q134183")
        >>> rels = get_direct_relationships("Q41421", "Q134183")
        >>> shared = get_shared_properties("Q41421", "Q134183")
        >>> analysis = analyze_rivalry(entity1, entity2, rels, shared)
        >>> print(analysis.rivalry_exists)
        True
        
        >>> # With File Search for enriched analysis
        >>> analysis = analyze_rivalry(entity1, entity2, rels, shared, store_name="fileSearchStores/abc")
    """
    # Prepare context for the AI agent
    entity1_details = format_entity_details(entity1)
    entity2_details = format_entity_details(entity2)
    
    context = f"""
Entity 1:
- ID: {entity1.id}
- Name: {entity1.label}
- Description: {entity1.description or 'N/A'}{entity1_details}

Entity 2:
- ID: {entity2.id}
- Name: {entity2.label}
- Description: {entity2.description or 'N/A'}{entity2_details}

Direct Relationships Found:
"""

    if relationships:
        for rel in relationships:
            context += f"\n- {rel.source_entity_label} --[{rel.property_label}]--> {rel.target_entity_label or rel.value}"
    else:
        context += "\nNo direct relationships found in Wikidata."

    # Add shared properties section
    context += "\n\nShared Properties (Common Connections):"
    
    if shared_properties:
        context += "\n"
        # Limit to top 15 properties to avoid token bloat
        for i, (prop_id, data) in enumerate(list(shared_properties.items())[:15]):
            prop_label = data.get('label', prop_id)
            values = data.get('values', [])
            
            # Show first 3 values for each property
            value_labels = [v.get('label', v.get('id', '?')) for v in values[:3]]
            value_str = ', '.join(value_labels)
            
            if len(values) > 3:
                value_str += f' (and {len(values) - 3} more)'
            
            context += f"- Both: {prop_label} = {value_str}\n"
    else:
        context += "\nNo shared properties found."

    # Add instruction about biographical documents if File Search is available
    if store_name:
        context += """

Biographical Documents Available:
You have access to biographical documents for both people via File Search.
Query these documents to find:
- Timeline events with specific dates
- Publications, achievements, and milestones
- Evidence of conflicts, disputes, or competitive interactions
- Context about their relationship or lack thereof

Combine insights from both Wikidata and biographical documents for a comprehensive analysis.
"""
    else:
        context += "\n\n"
    
    context += "Based on this data, analyze if a rivalry exists between these two people."

    # Configure agent with File Search if store provided
    if store_name:
        # Run agent with File Search tool
        result = rivalry_agent.run_sync(
            context,
            model_settings={
                "tools": [
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=[store_name]
                        )
                    )
                ]
            },
        )
    else:
        # Run agent with Wikidata data only
        result = rivalry_agent.run_sync(context)
    
    return result.output
