"""Pydantic-AI agent for analyzing rivalrous relationships."""

import os

from pydantic_ai import Agent

from .models import RivalryAnalysis, WikidataEntity, Relationship

# System prompt for the rivalry analysis agent
SYSTEM_PROMPT = """You are a rivalry analysis expert that examines relationships between people using factual data from Wikidata.

Your task is to:
1. Analyze the provided entity data and relationships
2. Determine if a rivalrous relationship exists (competition, conflict, controversy)
3. Extract specific factual incidents or events that demonstrate the rivalry
4. Be conservative - only mark rivalry_exists=True if there's clear evidence

Guidelines:
- Focus on factual, verifiable information from the provided data
- Look for indicators: sports rivalries, business competition, political opposition, artistic/cultural conflicts
- Extract temporal information when available (dates, time periods)
- Assign rivalry_score based on intensity: 0.0-0.3 (weak/indirect), 0.4-0.6 (moderate), 0.7-1.0 (intense/well-documented)
- If no rivalry is evident, set rivalry_exists=False and explain why in the summary
- Each fact should be concise and specific

Return a structured analysis with rivalry determination, score, summary, and specific facts."""

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
) -> RivalryAnalysis:
    """
    Analyze the rivalry between two entities using AI.

    This function takes entity data and relationships from Wikidata and uses
    an AI agent to determine if a rivalry exists, rate its intensity, and
    extract specific facts about the rivalry.

    The AI model used can be configured via the RIVALRY_MODEL environment variable.
    Defaults to "google-gla:gemini-2.5-flash" if not set.

    Args:
        entity1: First entity (person) data from Wikidata
        entity2: Second entity (person) data from Wikidata
        relationships: List of direct relationships between the entities

    Returns:
        RivalryAnalysis with structured rivalry data

    Raises:
        Exception: If the AI model fails or returns invalid data

    Example:
        >>> entity1 = get_entity("Q41421")  # Michael Jordan
        >>> entity2 = get_entity("Q134183")  # Magic Johnson
        >>> rels = get_direct_relationships("Q41421", "Q134183")
        >>> analysis = analyze_rivalry(entity1, entity2, rels)
        >>> print(analysis.rivalry_exists)
        True
    """
    # Prepare context for the AI agent
    context = f"""
Entity 1:
- ID: {entity1.id}
- Name: {entity1.label}
- Description: {entity1.description or 'N/A'}

Entity 2:
- ID: {entity2.id}
- Name: {entity2.label}
- Description: {entity2.description or 'N/A'}

Direct Relationships Found:
"""

    if relationships:
        for rel in relationships:
            context += f"\n- {rel.source_entity_label} --[{rel.property_label}]--> {rel.target_entity_label or rel.value}"
    else:
        context += "\nNo direct relationships found in Wikidata."

    context += "\n\nBased on this data, analyze if a rivalry exists between these two people."

    # Run the agent
    result = rivalry_agent.run_sync(context)
    return result.output
