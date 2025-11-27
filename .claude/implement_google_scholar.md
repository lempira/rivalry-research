# Implementation Guide: Add Google Scholar Source Fetcher

## Overview

This document provides all context needed to add Google Scholar as a source for the rivalry research pipeline. The system already has Wikipedia sources working - we need to add Scholar following the same pattern.

---

## Current Architecture

### How Source Fetching Works

1. **Source Fetchers** - Individual modules that fetch from specific sources (e.g., `wikipedia_fetcher.py`)
2. **Source Aggregator** - Orchestrates fetchers and handles deduplication (`source_aggregator.py`)
3. **SQLite Database** - Stores all sources with URL-based deduplication (`source_db.py`)
4. **Raw Content Storage** - Saves original content to `data/raw_sources/` filesystem
5. **Agent Integration** - Agent receives source IDs and references them in timeline events

### Source Model Structure

```python
class Source(BaseModel):
    source_id: str          # Unique ID (URL-based hash)
    type: str              # e.g., "academic_paper", "wikipedia", "news_article"
    title: str
    authors: list[str]
    publication: str | None
    publication_date: str | None
    url: str               # Used for deduplication
    doi: str | None
    isbn: str | None
    retrieved_at: str      # ISO timestamp
    credibility_score: float  # 0.0-1.0
    is_primary_source: bool
    stored_content_path: str | None
    content_hash: str | None
```

### Credibility Scores (from `credibility.py`)

Already defined:

- `academic_paper`: 0.95
- `peer_reviewed_journal`: 0.95
- `book`: 0.85
- `wikipedia`: 0.75

---

## Reference Implementation: Wikipedia Fetcher

Here's the existing `wikipedia_fetcher.py` structure to follow:

```python
from ..models import WikidataEntity, Source
from .utils import generate_source_id, get_iso_timestamp

def fetch_wikipedia_source(entity: WikidataEntity, timeout: float = 30.0) -> tuple[Source, str]:
    """
    Fetch Wikipedia article as a Source object with content.

    Returns:
        Tuple of (Source object, article_content)
    """
    # 1. Fetch content from Wikipedia API
    article_title, article_text = fetch_wikipedia_content(entity.wikipedia_url, timeout)

    # 2. Create Source object
    source = Source(
        source_id=generate_source_id(entity.wikipedia_url, "wiki"),
        type="wikipedia",
        title=article_title,
        authors=["Wikipedia contributors"],
        publication="Wikipedia",
        publication_date=None,
        url=entity.wikipedia_url,
        retrieved_at=get_iso_timestamp(),
        credibility_score=0.75,
        is_primary_source=False,
    )

    # 3. Format content with metadata header
    content = format_as_document(article_title, article_text, entity)

    return source, content
```

### Key Functions in `utils.py`

```python
def generate_source_id(url: str, prefix: str = "src") -> str:
    """Generate unique source ID based on URL hash."""
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:12]
    return f"{prefix}_{url_hash}"

def get_iso_timestamp() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()

def get_content_path(base_dir: Path, url: str, extension: str = "txt") -> Path:
    """Generate storage path for source content based on URL hash."""
    url_hash = hash_url(url)
    content_dir = base_dir / url_hash
    content_dir.mkdir(parents=True, exist_ok=True)
    return content_dir / f"content.{extension}"
```

---

## Implementation: Google Scholar Fetcher

### File: `src/rivalry_research/sources/scholar_fetcher.py`

Create a new file following the Wikipedia pattern:

```python
"""Fetch academic papers from Google Scholar."""

import logging
from typing import Any

from ..models import WikidataEntity, Source
from .utils import generate_source_id, get_iso_timestamp

logger = logging.getLogger(__name__)

def fetch_scholar_sources(entity: WikidataEntity, max_results: int = 5) -> list[tuple[Source, str]]:
    """
    Fetch academic papers about an entity from Google Scholar.

    Args:
        entity: WikidataEntity to search for
        max_results: Maximum number of papers to fetch

    Returns:
        List of (Source, content) tuples
    """
    logger.info(f"Searching Google Scholar for {entity.label}")

    # TODO: Implement Scholar API/scraping
    # Search query: entity.label + keywords like "biography", "life", "work"
    # For each paper result:
    #   1. Extract metadata (title, authors, year, DOI, abstract, URL)
    #   2. Create Source object
    #   3. Format content (title + abstract + metadata)
    #   4. Return list of (source, content) tuples

    sources = []
    # ... implementation here

    return sources
```

### Required Functionality

1. **Search Query Construction**

   - Use `entity.label` (person's name)
   - Add search terms: "biography", "life and work", entity's field
   - Example: "Albert Einstein physics biography"

2. **Paper Metadata Extraction**

   - Title
   - Authors (list)
   - Publication year
   - Journal/Conference name
   - DOI (if available)
   - Abstract/snippet
   - Scholar URL

3. **Content Formatting**

   - Include: Title, Authors, Year, Abstract
   - Add metadata header similar to Wikipedia
   - Make it searchable by the agent

4. **Error Handling**
   - Handle rate limiting
   - Handle missing metadata gracefully
   - Log failures but don't crash

### Suggested Library: `scholarly`

```python
from scholarly import scholarly

# Search for papers
search_query = scholarly.search_pubs(f"{entity.label} biography")

# Get first N results
papers = []
for i in range(max_results):
    try:
        paper = next(search_query)
        papers.append(paper)
    except StopIteration:
        break
```

---

## Integration: Update `source_aggregator.py`

### Current Code (Wikipedia only):

```python
def fetch_sources_for_entity(
    db: SourceDatabase,
    raw_sources_dir: Path,
    entity: WikidataEntity,
) -> list[Source]:
    sources = []

    # Fetch Wikipedia
    if entity.wikipedia_url:
        try:
            wiki_source = _fetch_and_store_wikipedia(db, raw_sources_dir, entity)
            if wiki_source:
                sources.append(wiki_source)
        except Exception as e:
            logger.error(f"Failed to fetch Wikipedia for {entity.label}: {e}")

    return sources
```

### Updated Code (Wikipedia + Scholar):

```python
from .scholar_fetcher import fetch_scholar_sources

def fetch_sources_for_entity(
    db: SourceDatabase,
    raw_sources_dir: Path,
    entity: WikidataEntity,
) -> list[Source]:
    sources = []

    # Fetch Wikipedia
    if entity.wikipedia_url:
        try:
            wiki_source = _fetch_and_store_wikipedia(db, raw_sources_dir, entity)
            if wiki_source:
                sources.append(wiki_source)
        except Exception as e:
            logger.error(f"Failed to fetch Wikipedia for {entity.label}: {e}")

    # Fetch Google Scholar (NEW)
    try:
        scholar_sources = _fetch_and_store_scholar(db, raw_sources_dir, entity)
        sources.extend(scholar_sources)
    except Exception as e:
        logger.error(f"Failed to fetch Scholar for {entity.label}: {e}")

    return sources


def _fetch_and_store_scholar(
    db: SourceDatabase,
    raw_sources_dir: Path,
    entity: WikidataEntity,
    max_results: int = 5,
) -> list[Source]:
    """
    Fetch Scholar sources with deduplication and storage.

    Returns:
        List of Source objects
    """
    scholar_results = fetch_scholar_sources(entity, max_results)
    stored_sources = []

    for source, content in scholar_results:
        # Check if URL already exists in database
        existing = db.get_source_by_url(source.url)
        if existing:
            logger.info(f"Scholar source already exists: {existing.source_id}")
            stored_sources.append(existing)
            continue

        # Calculate content hash
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        source.content_hash = content_hash

        # Save raw content to disk
        content_path = get_content_path(raw_sources_dir, source.url, "txt")
        content_path.write_text(content, encoding="utf-8")
        source.stored_content_path = str(content_path.relative_to(raw_sources_dir.parent))

        # Add to database
        source = db.add_source(source)
        stored_sources.append(source)

        logger.info(f"Stored Scholar source: {source.source_id} - {source.title}")

    return stored_sources
```

---

## Update Exports

### `src/rivalry_research/sources/__init__.py`

Add Scholar fetcher to exports:

```python
from .scholar_fetcher import fetch_scholar_sources
from .source_aggregator import fetch_sources_for_entity
from .wikipedia_fetcher import fetch_wikipedia_source

__all__ = [
    "fetch_wikipedia_source",
    "fetch_scholar_sources",  # NEW
    "fetch_sources_for_entity",
    # ... other exports
]
```

---

## Dependencies

### Add to `pyproject.toml`:

```toml
dependencies = [
    # ... existing dependencies
    "scholarly>=1.7.11",  # Google Scholar scraper
]
```

Then run:

```bash
uv sync
```

---

## Testing

### Manual Test Script

```python
from rivalry_research import get_person_by_id
from rivalry_research.sources.scholar_fetcher import fetch_scholar_sources

# Test with Einstein
entity = get_person_by_id("Q937")  # Albert Einstein
sources = fetch_scholar_sources(entity, max_results=3)

print(f"Found {len(sources)} Scholar sources")
for source, content in sources:
    print(f"- {source.title}")
    print(f"  Authors: {', '.join(source.authors)}")
    print(f"  URL: {source.url}")
    print(f"  Credibility: {source.credibility_score}")
```

### Integration Test

```python
from rivalry_research import analyze_rivalry

# This should now fetch both Wikipedia AND Scholar sources
analysis = analyze_rivalry("Q937", "Q38033")  # Einstein vs Bohr

print(f"Total sources: {len(analysis.sources)}")
print("\nSources by type:")
for source in analysis.sources.values():
    print(f"  {source.type}: {source.title}")
```

---

## Expected Outcome

After implementation:

1. **For each entity**, the system will fetch:

   - 1 Wikipedia article (existing)
   - Up to 5 Google Scholar papers (new)

2. **Sources are deduplicated** in SQLite by URL

3. **Agent receives** all sources and can reference Scholar papers in timeline events

4. **Analysis output** includes both Wikipedia and Scholar sources in the `sources` catalog

5. **Higher confidence events** when corroborated by academic papers

---

## File Structure Summary

```
src/rivalry_research/sources/
├── __init__.py              # Update exports
├── wikipedia_fetcher.py     # Existing (reference)
├── scholar_fetcher.py       # NEW - implement this
├── source_aggregator.py     # Update to call Scholar
├── utils.py                 # Existing (use these utilities)
├── credibility.py           # Existing (scores already defined)
└── validation.py            # Existing (no changes needed)
```

---

## Notes

- **Rate Limiting**: Scholar has rate limits - add delays between requests
- **Error Handling**: Some entities may not have Scholar results - this is OK
- **Content Quality**: Abstracts are often better than full text for agent processing
- **URL Format**: Use Scholar's citation URL or DOI for deduplication
- **Primary Source Detection**: Published papers by the entity themselves should be marked `is_primary_source=True`

---

## Questions to Consider

1. Should we fetch papers **by** the entity or papers **about** the entity? (Suggest: papers about)
2. How to handle papers that mention both entities? (Include in both)
3. Should we prioritize highly-cited papers? (Yes, if available)
4. What if entity name is ambiguous? (Use entity.description for disambiguation)

---

## Success Criteria

✅ Can fetch Scholar papers for any entity with `fetch_scholar_sources()`  
✅ Sources stored in SQLite with proper metadata  
✅ No duplicate sources (URL-based deduplication works)  
✅ Agent receives Scholar sources in available sources list  
✅ Timeline events can reference Scholar papers  
✅ Analysis output shows Scholar sources in sources catalog

---

## Reference: Existing Working Flow

1. User calls `analyze_rivalry("Q935", "Q9047")`
2. System calls `fetch_sources_for_entity(db, raw_sources_dir, entity1)`
3. Fetches Wikipedia via `_fetch_and_store_wikipedia()`
4. Checks SQLite: if URL exists, returns existing; else stores new
5. Saves content to `data/raw_sources/{url_hash}/content.txt`
6. Returns list of Source objects
7. Agent receives sources in context with IDs
8. Agent references sources in timeline events
9. Analysis saved with full source catalog

**Your task: Add Scholar to step 3, following the same pattern.**
