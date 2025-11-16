"""Pydantic-AI agent for analyzing rivalrous relationships."""

import logging
import os
from typing import Any

from pydantic_ai import Agent, RunContext, InstrumentationSettings

from .logging_utils import format_entity_details, log_tool_usage
from .models import RivalryAnalysis, WikidataEntity, Relationship
from .rag.file_search_client import query_store

logger = logging.getLogger(__name__)

# System prompt for the rivalry analysis agent
SYSTEM_PROMPT = """You are a rivalry analysis expert that examines relationships between people using both structured Wikidata facts and biographical documents.

IMPORTANT: You have access to a 'search_biographical_documents' tool. You MUST use this tool to query biographical information about both people before completing your analysis.

Your task is to:
1. Use the 'search_biographical_documents' tool to query information about both people (make multiple queries as needed)
2. Analyze the provided entity data, direct relationships, and shared properties from Wikidata
3. Combine insights from biographical documents and Wikidata to determine if a rivalrous relationship exists
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

Using the search_biographical_documents Tool:
- Call this tool with queries about: timeline events, conflicts, disputes, controversies, achievements, publications
- Query for specific information like: "conflicts between [person1] and [person2]"
- Query for timeline information: "key dates in [person]'s career"
- Look for priority disputes or competing claims
- Make multiple tool calls to thoroughly investigate

Timeline Requirements:
- Extract chronological events for BOTH people and shared events
- For each event, specify: date, event_type, description, entity_id (entity1_id, entity2_id, or 'both')
- Event types: achievement, conflict, publication, meeting, award, controversy, etc.
- Include sources/citations where available
- Sort events chronologically

Return a structured analysis with:
- rivalry_exists, rivalry_score, summary (required)
- facts: specific rivalry facts with dates and categories (required)
- timeline: chronological events for both people (required)
- Base all information on BOTH Wikidata and biographical document searches"""

# Get model from environment variable, default to Gemini
MODEL = os.getenv("RIVALRY_MODEL", "google-gla:gemini-2.5-flash")

# Create the rivalry analysis agent
# The agent will return a RivalryAnalysis model with structured output
# Configure instrumentation for Logfire observability (console only)
rivalry_agent = Agent(
    MODEL,
    output_type=RivalryAnalysis,
    system_prompt=SYSTEM_PROMPT,
    deps_type=str,  # Store name passed as dependency
    instrument=InstrumentationSettings(
        include_content=True,  # Include tool args/responses
        version=3,             # OpenTelemetry GenAI v3
    ),
)


@rivalry_agent.tool
def search_biographical_documents(ctx: RunContext[str], query: str) -> str:
    """
    Search biographical documents for information about the people being analyzed.
    
    Use this tool to query biographical documents stored in the File Search store.
    You can make multiple queries to gather comprehensive information.
    
    Args:
        ctx: RunContext containing store_name as dependency
        query: Natural language search query about the people
    
    Returns:
        Search results from biographical documents
    """
    store_name = ctx.deps
    logger.debug(f"Tool 'search_biographical_documents' called with query: {query}")
    
    try:
        response = query_store(store_name, query)
        result_text = response.text
        
        # Add grounding metadata if available
        if hasattr(response, 'candidates') and response.candidates:
            grounding = response.candidates[0].grounding_metadata
            if grounding:
                logger.debug(f"Results include grounding from {len(grounding.grounding_chunks or [])} chunks")
        
        logger.debug(f"Tool returned {len(result_text)} characters")
        return result_text
    except Exception as e:
        logger.error(f"Tool search failed: {e}")
        return f"Error searching documents: {str(e)}"


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

    # Run agent with search tool
    logger.info(f"Using File Search store: {store_name}")
    logger.debug("Agent has access to search_biographical_documents tool")
    logger.debug(f"Agent prompt (first 500 chars): {context[:500]}...")
    logger.info("Running AI agent with biographical search tool...")
    
    result = rivalry_agent.run_sync(
        context,
        deps=store_name,  # Pass store name as dependency for tool
    )
    
    # Log tool usage at DEBUG level
    log_tool_usage(result)
    
    logger.info(
        f"Agent analysis complete: rivalry={result.output.rivalry_exists}, "
        f"score={result.output.rivalry_score:.2f}"
    )
    
    return result.output
