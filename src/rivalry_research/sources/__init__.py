"""Source fetchers for biographical content."""

from .source_aggregator import fetch_sources_for_entity
from .wikipedia_fetcher import fetch_wikipedia_source

__all__ = ["fetch_wikipedia_source", "fetch_sources_for_entity"]

