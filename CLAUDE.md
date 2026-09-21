# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A monorepo for analyzing rivalrous relationships between historical figures using Wikidata's knowledge graph and AI. The system fetches biographical data from multiple sources (Wikipedia, Google Scholar, arXiv, MacTutor), stores and deduplicates content, uploads to Google's File Search for RAG, and uses PydanticAI for structured rivalry analysis.

## Repository Structure

- **backend/**: Python library and CLI for data fetching, analysis, and storage (uv-managed)
- **app/**: Astro frontend for visualizing rivalries (pnpm-managed)

## Backend Commands

All backend commands run from the `backend/` directory:

```bash
# Install dependencies
uv sync

# Run CLI
uv run rivalry --help

# Analyze a rivalry (e.g., Newton vs Leibniz)
uv run python -m rivalry_research analyze Q935 Q9047

# Source management
uv run rivalry sources scan
uv run rivalry sources process --all
uv run rivalry sources add Q9021 path/to/file.pdf --title "Title"

# Image management
uv run rivalry images list --entity Q9021
uv run rivalry images add Q9021 photo.jpg --title "Title"

# File Search store management
uv run rivalry fs list-stores
uv run rivalry fs health-check
```

## Frontend Commands

All frontend commands run from the `app/` directory:

```bash
pnpm install
pnpm dev      # Start dev server
pnpm build    # Production build
```

## Backend Architecture

### Core Pipeline (`__init__.py`)
The `analyze_rivalry(entity_id1, entity_id2)` function orchestrates:
1. Fetches Wikidata entities via SPARQL
2. Extracts relationships and shared properties
3. Fetches sources (Wikipedia, Scholar, arXiv, MacTutor) with deduplication
4. Uploads content to Google File Search store
5. Runs PydanticAI agent with RAG access
6. Saves analysis to JSON

### Key Modules
- **models.py**: Pydantic models (`WikidataEntity`, `Source`, `RivalryAnalysis`, `TimelineEvent`)
- **rivalry_agent.py**: PydanticAI agent with File Search tool
- **sources/**: Fetchers for each source type, plus aggregation and validation
  - `source_aggregator.py`: Orchestrates multi-source fetching
  - `source_scanner.py`: Filesystem operations for manual sources
  - `*_fetcher.py`: Individual source fetchers
- **storage/**: SQLite database (`SourceDatabase`) for source deduplication
- **rag/**: Google File Search client
- **cli/**: Typer-based commands (sources, images, fs, clean)

### Data Storage
```
backend/data/
├── sources.db              # SQLite - deduplicated sources
├── raw_sources/            # Content files organized by entity
│   └── Entity_Name_Q12345/
│       ├── wikipedia/
│       ├── scholar_001/
│       ├── manual_001/
│       └── images/
└── analyses/               # JSON output per rivalry pair
    └── Q935_Q9047/
```

## Environment Setup

Backend requires:
- Python 3.13+
- `GOOGLE_API_KEY` environment variable (for Gemini and File Search)

Copy `backend/.env.example` to `backend/.env` and add your API key.

## Key Patterns

- Sources support both auto-fetch and manual addition (tracked via `is_manual` flag)
- Deduplication uses content hash and URL
- File Search stores are per-analysis, not persistent across runs
- CLI uses Typer with subcommand groups (sources, images, fs, clean)
- Logfire configured for console-only observability (no web service)