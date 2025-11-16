"""Pydantic-AI agent for analyzing rivalrous relationships."""

import json
import logging
import os
from typing import Any

from google.genai import types
from pydantic_ai import Agent

from .models import RivalryAnalysis, WikidataEntity, Relationship

logger = logging.getLogger(__name__)


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


def log_tool_usage(result: Any) -> None:
    """
    Log whether the agent used any tools during execution.
    Only logs at DEBUG level.
    
    Args:
        result: The result object from rivalry_agent.run_sync()
    """
    try:
        # Decode binary JSON and parse it
        messages_data = result.all_messages_json()
        messages = json.loads(messages_data.decode('utf-8'))
        
        tool_used = False
        tool_call_count = 0
        tool_queries = []
        
        for msg in messages:
            # Check for tool calls in the message
            if 'tool_calls' in msg and msg['tool_calls']:
                tool_used = True
                for tool_call in msg['tool_calls']:
                    tool_call_count += 1
                    # Try to extract query information if available
                    if isinstance(tool_call, dict):
                        # Look for function/query parameters
                        if 'function' in tool_call:
                            func_data = tool_call['function']
                            if isinstance(func_data, dict) and 'arguments' in func_data:
                                tool_queries.append(func_data.get('arguments', ''))
                        # Direct query field
                        elif 'query' in tool_call:
                            tool_queries.append(tool_call['query'])
                logger.debug(f"Tool call found: {tool_call}")
            
            # Check if message role is 'tool' (tool response)
            elif msg.get('role') == 'tool':
                tool_used = True
                logger.debug(f"Tool response found: {msg.get('content', '')[:200]}...")
        
        if tool_used:
            logger.debug(f"✓ File search tool USED ({tool_call_count} call(s))")
            for i, query in enumerate(tool_queries, 1):
                if query:
                    logger.debug(f"  Tool call {i}: {query}")
        else:
            logger.debug("✗ File search tool NOT USED")
    except Exception as e:
        logger.debug(f"Could not determine tool usage: {e}")


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
    store_name: str,
) -> RivalryAnalysis:
    """
    Analyze the rivalry between two entities using AI.

    This function takes entity data, relationships, and shared properties from Wikidata
    and uses an AI agent to determine if a rivalry exists, rate its intensity, and
    extract specific facts about the rivalry.
    
    The agent queries biographical documents via File Search to enrich the analysis
    with timeline events and narrative context.

    The AI model used can be configured via the RIVALRY_MODEL environment variable.
    Defaults to "google-gla:gemini-2.5-flash" if not set.

    Args:
        entity1: First entity (person) data from Wikidata
        entity2: Second entity (person) data from Wikidata
        relationships: List of direct relationships between the entities
        shared_properties: Dictionary of properties both entities share
        store_name: File Search store name for biographical document access

    Returns:
        RivalryAnalysis with structured rivalry data

    Raises:
        Exception: If the AI model fails or returns invalid data

    Example:
        >>> entity1 = get_entity("Q41421")
        >>> entity2 = get_entity("Q134183")
        >>> rels = get_direct_relationships("Q41421", "Q134183")
        >>> shared = get_shared_properties("Q41421", "Q134183")
        >>> analysis = analyze_rivalry(entity1, entity2, rels, shared, store_name="fileSearchStores/abc")
        >>> print(analysis.rivalry_exists)
        True
    """
    logger.info(f"Analyzing rivalry: {entity1.label} vs {entity2.label}")
    logger.debug(f"Entity 1 details: {format_entity_details(entity1)}")
    logger.debug(f"Entity 2 details: {format_entity_details(entity2)}")
    logger.debug(f"Found {len(relationships)} direct relationships")
    logger.debug(f"Found {len(shared_properties)} shared properties")
    
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

    # Add instruction about biographical documents
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
    
    context += "Based on this data, analyze if a rivalry exists between these two people."

    # Run agent with File Search tool
    logger.info(f"Using File Search store: {store_name}")
    logger.debug("Agent will query biographical documents via File Search")
    logger.debug(f"Agent prompt (first 500 chars): {context[:500]}...")
    logger.info("Running AI agent with File Search...")
    
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
    
    # Log tool usage at DEBUG level
    log_tool_usage(result)
    
    logger.info(
        f"Agent analysis complete: rivalry={result.output.rivalry_exists}, "
        f"score={result.output.rivalry_score:.2f}"
    )
    
    return result.output
