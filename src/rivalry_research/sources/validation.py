"""Source validation and confidence calculation."""

import logging
from datetime import datetime

from ..models import Source, EventSource, SourcesSummary

logger = logging.getLogger(__name__)


def calculate_event_confidence(
    sources: list[Source],
    has_multiple_sources: bool,
    has_primary_source: bool,
) -> float:
    """
    Calculate confidence score for an event based on its sources.
    
    Confidence is higher when:
    - Multiple independent sources agree
    - At least one primary source exists
    - Sources have high credibility scores
    
    Args:
        sources: List of Source objects supporting the event
        has_multiple_sources: Whether event has multiple sources
        has_primary_source: Whether event has at least one primary source
    
    Returns:
        Confidence score between 0.0 and 1.0
    """
    if not sources:
        return 0.0
    
    # Base confidence on average credibility
    avg_credibility = sum(s.credibility_score for s in sources) / len(sources)
    
    # Boost for multiple sources
    multi_source_boost = 0.1 if has_multiple_sources else 0.0
    
    # Boost for primary source
    primary_boost = 0.1 if has_primary_source else 0.0
    
    confidence = min(1.0, avg_credibility + multi_source_boost + primary_boost)
    
    return round(confidence, 2)


def validate_event_sources(event_sources: list[EventSource], sources_catalog: dict[str, Source]) -> dict:
    """
    Validate sources for an event and return validation metadata.
    
    Args:
        event_sources: List of EventSource references
        sources_catalog: Dictionary mapping source_id to Source objects
    
    Returns:
        Dictionary with validation metadata:
        - source_count: Number of sources
        - has_multiple_sources: Boolean
        - has_primary_source: Boolean
        - confidence: Confidence score
    """
    if not event_sources:
        return {
            "source_count": 0,
            "has_multiple_sources": False,
            "has_primary_source": False,
            "confidence": 0.0,
        }
    
    # Resolve sources
    resolved_sources = []
    for event_source in event_sources:
        source = sources_catalog.get(event_source.source_id)
        if source:
            resolved_sources.append(source)
        else:
            logger.warning(f"Source {event_source.source_id} not found in catalog")
    
    has_multiple = len(resolved_sources) > 1
    has_primary = any(s.is_primary_source for s in resolved_sources)
    
    confidence = calculate_event_confidence(resolved_sources, has_multiple, has_primary)
    
    return {
        "source_count": len(resolved_sources),
        "has_multiple_sources": has_multiple,
        "has_primary_source": has_primary,
        "confidence": confidence,
    }


def compute_sources_summary(sources: dict[str, Source]) -> SourcesSummary:
    """
    Compute summary statistics for a collection of sources.
    
    Args:
        sources: Dictionary mapping source_id to Source objects
    
    Returns:
        SourcesSummary with aggregate statistics
    """
    if not sources:
        return SourcesSummary(
            total_sources=0,
            by_type={},
            primary_sources=0,
            secondary_sources=0,
            average_credibility=0.0,
        )
    
    sources_list = list(sources.values())
    
    # Count by type
    by_type = {}
    for source in sources_list:
        by_type[source.type] = by_type.get(source.type, 0) + 1
    
    # Count primary vs secondary
    primary_count = sum(1 for s in sources_list if s.is_primary_source)
    secondary_count = len(sources_list) - primary_count
    
    # Average credibility
    avg_credibility = sum(s.credibility_score for s in sources_list) / len(sources_list)
    
    # Date range (if publication_date available)
    dates = [s.publication_date for s in sources_list if s.publication_date]
    date_range = None
    if dates:
        try:
            # Sort dates (handles YYYY and YYYY-MM-DD formats)
            sorted_dates = sorted(dates)
            date_range = {
                "earliest": sorted_dates[0],
                "latest": sorted_dates[-1],
            }
        except Exception as e:
            logger.debug(f"Could not compute date range: {e}")
    
    return SourcesSummary(
        total_sources=len(sources_list),
        by_type=by_type,
        primary_sources=primary_count,
        secondary_sources=secondary_count,
        average_credibility=round(avg_credibility, 2),
        date_range=date_range,
    )

