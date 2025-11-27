"""Logging utilities for rivalry research."""

import json
import logging
from typing import Any

from .models import WikidataEntity

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

