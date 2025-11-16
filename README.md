# Rivalry Research

Analyze rivalrous relationships between people using Wikidata's knowledge graph and AI.

## Features

- Search for people on Wikidata with disambiguation
- Extract relationships between entities using SPARQL
- AI-powered rivalry analysis with structured output
- Support for multiple AI providers (Gemini, OpenAI, Anthropic)

## Installation

```bash
uv add rivalry-research
```

## Requirements

- Python 3.13+
- AI provider API key

## Quick Start

```python
import os
from rivalry_research import search_person, analyze_rivalry

# Set API key
os.environ["GOOGLE_API_KEY"] = "your-api-key"

# Search for people
newton = search_person("Isaac Newton")[0]
leibniz = search_person("Gottfried Wilhelm Leibniz")[0]

# Analyze rivalry
analysis = analyze_rivalry(newton.id, leibniz.id)

print(f"Rivalry exists: {analysis.rivalry_exists}")
print(f"Score: {analysis.rivalry_score:.2f}")
print(f"\n{analysis.summary}")

for fact in analysis.facts:
    print(f"- {fact.fact}")
```

## CLI Commands

Monitor your File Search stores:

```bash
# List all stores
uv run rivalry-fs list-stores

# List documents in stores
uv run rivalry-fs list-docs

# Check store health
uv run rivalry-fs health-check
```

## Configuration

```bash
cp env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

Or export environment variables directly:

```bash
export GOOGLE_API_KEY="your-key"
export RIVALRY_MODEL="google-gla:gemini-2.5-flash"  # optional, this is the default
```

## Examples

```python
# Newton vs Leibniz - calculus priority dispute
analysis = analyze_rivalry("Q935", "Q9047")
```

## Development

```bash
uv sync
```

## License

MIT
