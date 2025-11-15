# Rivalry Research

A Python library for analyzing rivalrous relationships between people using Wikidata's knowledge graph.

## Overview

This library provides tools to:

- Search for people on Wikidata with disambiguation support
- Extract relationships between entities
- Analyze rivalries using AI-powered analysis
- Return structured facts about conflicts and drama

## Features

- **Entity Search**: Find Wikidata entities by name with disambiguation
- **Relationship Extraction**: Query relationships between two people using SPARQL
- **AI Analysis**: Use Pydantic-AI to identify and structure rivalry-related facts
- **Structured Output**: Get rivalry data as typed Pydantic models

## Installation

```bash
uv add rivalry-research
```

## Requirements

- Python 3.13+
- API key for AI provider (OpenAI, Anthropic, etc.)

## Usage

Coming soon...

## Development

This project uses `uv` for package management.

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest
```

## License

MIT
