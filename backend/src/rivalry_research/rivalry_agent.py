"""Pydantic-AI agent for analyzing rivalrous relationships."""

import logging
from typing import Any

from pydantic_ai import Agent, RunContext, InstrumentationSettings

from .config import get_settings
from .logging_utils import format_entity_details, log_tool_usage
from .models import RivalryAnalysis, WikidataEntity, Relationship, RivalryEntity, Source
from .rag.file_search_client import query_store
from .sources import fetch_sources_for_entity, validate_event_sources, compute_sources_summary, fetch_all_images
from .storage import SourceDatabase

logger = logging.getLogger(__name__)


def extract_date_from_claims(claims: dict[str, Any], property_id: str) -> str | None:
    """
    Extract date value from Wikidata claims for a given property.
    
    Args:
        claims: Wikidata claims dictionary
        property_id: Property ID (e.g., 'P569' for birth date)
    
    Returns:
        Date string in YYYY or YYYY-MM-DD format, or None if not found
    """
    if property_id not in claims:
        return None
    
    claim_list = claims[property_id]
    if not claim_list:
        return None
    
    # Get first claim's value
    try:
        mainsnak = claim_list[0].get('mainsnak', {})
        datavalue = mainsnak.get('datavalue', {})
        value = datavalue.get('value', {})
        
        if isinstance(value, dict) and 'time' in value:
            # Wikidata time format: +1834-02-08T00:00:00Z
            time_str = value['time']
            # Remove leading + and timezone info
            time_str = time_str.lstrip('+').split('T')[0]
            return time_str
    except (KeyError, IndexError, AttributeError):
        pass
    
    return None


def extract_list_from_claims(claims: dict[str, Any], property_id: str) -> list[str]:
    """
    Extract list of string values from Wikidata claims for a given property.
    
    Args:
        claims: Wikidata claims dictionary
        property_id: Property ID (e.g., 'P106' for occupation)
    
    Returns:
        List of label strings
    """
    if property_id not in claims:
        return []
    
    claim_list = claims[property_id]
    results = []
    
    for claim in claim_list:
        try:
            mainsnak = claim.get('mainsnak', {})
            datavalue = mainsnak.get('datavalue', {})
            value = datavalue.get('value', {})
            
            # For entity references, try to get the label
            if isinstance(value, dict) and 'id' in value:
                # We'd need to look up the label, but for now just use the ID
                # In a real implementation, you might cache these or make additional queries
                entity_id = value['id']
                results.append(entity_id)
        except (KeyError, AttributeError):
            continue
    
    return results


def create_rivalry_entity(wikidata_entity: WikidataEntity) -> RivalryEntity:
    """
    Create a RivalryEntity from a WikidataEntity by extracting relevant biographical data.
    
    Args:
        wikidata_entity: Full Wikidata entity with all claims
    
    Returns:
        RivalryEntity with biographical context
    """
    claims = wikidata_entity.claims
    
    # Extract biographical data
    birth_date = extract_date_from_claims(claims, 'P569')  # date of birth
    death_date = extract_date_from_claims(claims, 'P570')  # date of death
    occupations = extract_list_from_claims(claims, 'P106')  # occupation
    
    # Extract nationality (P27 - country of citizenship)
    nationality = None
    if 'P27' in claims and claims['P27']:
        try:
            country_claim = claims['P27'][0]
            mainsnak = country_claim.get('mainsnak', {})
            datavalue = mainsnak.get('datavalue', {})
            value = datavalue.get('value', {})
            if isinstance(value, dict) and 'id' in value:
                nationality = value['id']
        except (KeyError, IndexError, AttributeError):
            pass
    
    return RivalryEntity(
        id=wikidata_entity.id,
        label=wikidata_entity.label,
        description=wikidata_entity.description,
        birth_date=birth_date,
        death_date=death_date,
        occupation=occupations,
        nationality=nationality,
    )

# System prompt for the rivalry analysis agent
SYSTEM_PROMPT = """You are a rivalry analysis expert that examines relationships between people using both structured Wikidata facts and biographical documents.

IMPORTANT: You have access to a 'search_biographical_documents' tool. You MUST use this tool extensively to query biographical information about both people before completing your analysis.

Your task is to:
1. Use the 'search_biographical_documents' tool to query information about both people (make multiple targeted queries)
2. Analyze the provided entity data, direct relationships, and shared properties from Wikidata
3. Combine insights from biographical documents and Wikidata to determine if a rivalrous relationship exists
4. Extract specific factual incidents or events with dates that demonstrate the rivalry
5. CAPTURE THE DRAMA: Focus on direct interactions, confrontations, insults, and heated exchanges
6. Be conservative - only mark rivalry_exists=True if there's clear evidence

Guidelines:
- Focus on factual, verifiable information from Wikidata and biographical sources
- Look for indicators: sports rivalries, business competition, political opposition, artistic/cultural conflicts, priority disputes
- Extract temporal information when available (dates, time periods) from both sources
- Assign rivalry_score based on intensity: 0.0-0.3 (weak/indirect), 0.4-0.6 (moderate), 0.7-1.0 (intense/well-documented)
- If no rivalry is evident, set rivalry_exists=False and explain why in the summary
- Each fact should be concise and specific, with dates when available

DRAMA AND INTERACTION REQUIREMENTS:
- CAPTURE SPECIFIC INTERACTIONS: Document face-to-face meetings, public debates, published responses, letters
- EXTRACT DIRECT QUOTES: When people insulted, criticized, or challenged each other, include their EXACT WORDS with attribution
- HIGHLIGHT DRAMA: Look for heated exchanges, public humiliations, professional sabotage, personal attacks, priority disputes
- DOCUMENT INSULTS: Any derogatory language, dismissive comments, or personal attacks should be captured verbatim
- PROVIDE CONTEXT: For each interaction, explain the setting, what led to it, and what resulted from it
- EMOTIONAL DETAILS: Describe the tone and intensity of interactions (cordial, tense, hostile, bitter, heated)
- RESPONSES AND REACTIONS: Document how each person responded to the other's actions or statements
- WITNESSES: Note if interactions were public, who was present, or how widely known they became

Using Wikidata Structured Data:
- Shared properties reveal implicit connections even without direct relationships
- Look for competitive overlap: same field of work, same achievements, same era
- Similar accomplishments in the same domain often indicate rivalry (e.g., both invented calculus)
- Temporal overlap (same time period) establishes they were contemporaries
- Shared institutions/awards/fields provide context for potential conflict

Using the search_biographical_documents Tool:
MAKE MULTIPLE TARGETED QUERIES to extract dramatic interactions:
- "conflicts between [person1] and [person2]"
- "disputes between [person1] and [person2]"
- "what [person1] said about [person2]" (and reverse)
- "criticisms by [person1] of [person2]" (and reverse)
- "meetings between [person1] and [person2]"
- "public confrontations" + both names
- "published attacks" or "published criticisms" + both names
- "personal animosity" or "hostility" + both names
- "insults" or "verbal attacks" + both names
- "[person1] response to [person2]"
- "relationship between [person1] and [person2]"
- "rivalry" or "feud" + both names
- Look for biography sections labeled: "Controversy", "Dispute", "Rivalry", "Conflict", "Relationship with X"
- Query for correspondence, published papers that reference each other, public statements
- Make 5-10 targeted queries minimum to thoroughly investigate the dramatic aspects

Entity Data Requirements:
- Populate entity1 and entity2 objects with biographical data (birth_date, death_date already provided)
- Use the entity IDs provided in the context for entity_id fields

Timeline Requirements (RIVALRY-FOCUSED WITH DRAMATIC DETAIL):
- Extract ONLY rivalry-relevant events (DO NOT include full biographical timelines)
- Include events with rivalry_relevance:
  * 'direct': Head-to-head conflicts, disputes, public disagreements, face-to-face confrontations
  * 'parallel': Competing publications, simultaneous discoveries, overlapping achievements
  * 'context': Entry into same field or establishing competitive overlap (minimal, only if essential)
  * 'resolution': Joint awards, acknowledgments, reconciliation
- EXCLUDE: births, deaths, general education, unrelated achievements, routine career milestones

For EACH event provide:
- date: Specific date or time period
- event_type: achievement, conflict, debate, meeting, publication, correspondence, etc.
- description: RICH NARRATIVE including:
  * Setting and circumstances (where, when, who was present)
  * What happened in detail (actions, statements, reactions)
  * Emotional tone (cordial, tense, hostile, bitter)
  * How each person responded or reacted
  * Immediate and longer-term impact on their relationship
  * Any dramatic elements (public humiliation, escalation, reconciliation)
  * INLINE CITATIONS: Embed source references using {source_id} markers directly in the text where claims are made.
    Example: "Koch published his findings on anthrax.{scholar_f5d757f49e6b} This marked the beginning of modern bacteriology."
    Place markers immediately after the specific claim they support, not at the end of sentences or paragraphs.
- direct_quotes: Array of verbatim quotes WITH ATTRIBUTION
  * Format: "Person Name: 'exact quote here'"
  * PRIORITIZE: insults, criticisms, dismissive comments, challenges, defenses
  * Include both the attack and any response if available
- entity_id: Use entity1.id, entity2.id, or 'both'
- rivalry_relevance: direct/parallel/context/resolution
- sources: Array of EventSource objects with:
  * source_id: Reference to one of the available source IDs provided in context
  * supporting_text: The specific text from the source that supports this event
  * page_reference: Page number or section (if applicable)
- Sort events chronologically

IMPORTANT SOURCE REQUIREMENTS:
- You will be provided with available sources (with source_ids) for both entities
- For EACH event, reference sources using their source_id from the provided list
- Include the specific supporting_text that evidences the event
- An event can reference multiple sources if multiple sources confirm it
- The sources field must use the EventSource structure, NOT plain strings

Rivalry Period:
- Specify rivalry_period_start: when the rivalry/competition began (YYYY format)
- Specify rivalry_period_end: when it ended or was resolved (YYYY format, or null if ongoing/unresolved)

Summary Requirements (CAPTURE THE DRAMA):
- Length: 200-300 words to accommodate rich narrative
- Opening: Lead with the most dramatic or defining aspect of their rivalry
- Include: 1-2 specific examples of their most hostile or significant interactions
- Quotes: Weave in the most cutting or revealing quotes (briefly, full quotes go in timeline)
- Evolution: Describe how the rivalry evolved (e.g., cordial → competitive → hostile)
- Tone: Note whether it was professional competition, personal animosity, or both
- Context: Mention any external factors (national pride, priority disputes, professional jealousy)
- Impact: How the rivalry influenced their work or their field
- Resolution: How it ended (if it did) - reconciliation, death, fading away

Return a structured analysis with:
- entity1, entity2: RivalryEntity objects with biographical data (required)
- rivalry_exists, rivalry_score, rivalry_period_start, rivalry_period_end, summary (required)
- timeline: rivalry-relevant events ONLY with rich descriptions, quotes, and EventSource references (required)
- sources: Dictionary mapping source_id to Source objects (will be populated from available sources)
- Base all information on BOTH Wikidata and biographical document searches

NOTE: The sources dictionary and sources_summary will be populated automatically from the available sources.
You only need to reference sources by their source_id in the timeline events."""

# Get settings (loads from .env or environment)
settings = get_settings()

# Create the rivalry analysis agent
# The agent will return a RivalryAnalysis model with structured output
# Configure instrumentation for Logfire observability (console only)
rivalry_agent = Agent(
    settings.rivalry_model,
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
    
    Fetches Wikipedia sources for both entities, stores them in SQLite database,
    and passes source metadata to the agent for proper citation.

    The AI model used can be configured via the RIVALRY_MODEL environment variable.
    Defaults to "google-gla:gemini-2.5-flash" if not set.

    Args:
        entity1: First entity (person) data from Wikidata
        entity2: Second entity (person) data from Wikidata
        relationships: List of direct relationships between the entities
        shared_properties: Dictionary of properties both entities share
        store_name: File Search store name for biographical document access

    Returns:
        RivalryAnalysis with structured rivalry data including source catalog

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
    
    # Initialize source database and fetch sources
    settings = get_settings()
    db = SourceDatabase(settings.sources_db_path)
    
    logger.info("Fetching Wikipedia sources for both entities")
    sources_entity1 = fetch_sources_for_entity(db, settings.raw_sources_dir, entity1)
    sources_entity2 = fetch_sources_for_entity(db, settings.raw_sources_dir, entity2)
    
    # Combine sources into a catalog
    all_sources: dict[str, Source] = {}
    for source in sources_entity1 + sources_entity2:
        all_sources[source.source_id] = source
    
    logger.info(f"Fetched {len(all_sources)} total sources ({len(sources_entity1)} for {entity1.label}, {len(sources_entity2)} for {entity2.label})")
    
    # Create RivalryEntity objects with biographical data from Wikidata
    rivalry_entity1 = create_rivalry_entity(entity1)
    rivalry_entity2 = create_rivalry_entity(entity2)

    logger.debug(f"Entity 1 biographical data: birth={rivalry_entity1.birth_date}, death={rivalry_entity1.death_date}")
    logger.debug(f"Entity 2 biographical data: birth={rivalry_entity2.birth_date}, death={rivalry_entity2.death_date}")

    # Fetch images for both entities from multiple sources
    logger.info("Fetching images for both entities")
    rivalry_entity1.images = fetch_all_images(entity1)
    rivalry_entity2.images = fetch_all_images(entity2)
    logger.info(f"Found {len(rivalry_entity1.images)} images for {entity1.label}, {len(rivalry_entity2.images)} images for {entity2.label}")
    
    # Prepare context for the AI agent
    entity1_details = format_entity_details(entity1)
    entity2_details = format_entity_details(entity2)
    
    context = f"""
Entity 1:
- ID: {entity1.id}
- Name: {entity1.label}
- Description: {entity1.description or 'N/A'}
- Birth Date: {rivalry_entity1.birth_date or 'Unknown'}
- Death Date: {rivalry_entity1.death_date or 'Unknown'}
- Occupation: {', '.join(rivalry_entity1.occupation) if rivalry_entity1.occupation else 'N/A'}
- Nationality: {rivalry_entity1.nationality or 'N/A'}{entity1_details}

Entity 2:
- ID: {entity2.id}
- Name: {entity2.label}
- Description: {entity2.description or 'N/A'}
- Birth Date: {rivalry_entity2.birth_date or 'Unknown'}
- Death Date: {rivalry_entity2.death_date or 'Unknown'}
- Occupation: {', '.join(rivalry_entity2.occupation) if rivalry_entity2.occupation else 'N/A'}
- Nationality: {rivalry_entity2.nationality or 'N/A'}{entity2_details}

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

    # Add available sources information
    context += "\n\nAvailable Sources (for citation in timeline events):"
    if all_sources:
        context += "\n"
        for source in all_sources.values():
            context += f"""
- Source ID: {source.source_id}
  - Type: {source.type}
  - Title: {source.title}
  - URL: {source.url}
  - Credibility: {source.credibility_score:.2f}
  - Primary Source: {source.is_primary_source}
"""
    else:
        context += "\nNo sources available."
    
    # Add instruction about biographical documents
    context += """

Biographical Documents Available:
You have access to biographical documents for both people via File Search.
Query these documents to find:
- Timeline events with specific dates
- Publications, achievements, and milestones
- Evidence of conflicts, disputes, or competitive interactions
- Context about their relationship or lack thereof

When creating timeline events, reference the sources above using their source_id.
Include the supporting_text from the source that evidences the event.
Combine insights from both Wikidata and biographical documents for a comprehensive analysis.
"""
    
    context += "\nBased on this data, analyze if a rivalry exists between these two people."

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
    
    analysis = result.output

    # Post-process: Copy images from our fetched entities to the analysis output
    analysis.entity1.images = rivalry_entity1.images
    analysis.entity2.images = rivalry_entity2.images

    # Post-process: Populate sources catalog
    analysis.sources = all_sources
    
    # Post-process: Validate and enrich timeline events
    logger.info("Validating and enriching timeline event sources")
    for event in analysis.timeline:
        validation = validate_event_sources(event.sources, all_sources)
        event.source_count = validation["source_count"]
        event.has_multiple_sources = validation["has_multiple_sources"]
        event.has_primary_source = validation["has_primary_source"]
        event.confidence = validation["confidence"]
    
    # Compute sources summary
    analysis.sources_summary = compute_sources_summary(all_sources)
    
    # Add analysis metadata
    analysis.analysis_metadata = {
        "pipeline_version": "2.0",
        "model_used": settings.rivalry_model,
        "sources_searched": ["wikipedia"],
        "total_sources": len(all_sources),
    }
    
    logger.info(
        f"Analysis complete with {len(all_sources)} sources, "
        f"{len(analysis.timeline)} events"
    )
    
    return analysis
