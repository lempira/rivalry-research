"""Source fetchers for biographical content."""

from .credibility import calculate_credibility_score, is_primary_source
from .source_aggregator import fetch_sources_for_entity
from .validation import (
    calculate_event_confidence,
    compute_sources_summary,
    validate_event_sources,
)
from .wikipedia_fetcher import fetch_wikipedia_source

__all__ = [
    "fetch_wikipedia_source",
    "fetch_sources_for_entity",
    "calculate_credibility_score",
    "is_primary_source",
    "calculate_event_confidence",
    "validate_event_sources",
    "compute_sources_summary",
]

