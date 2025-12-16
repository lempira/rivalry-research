# Rivalry Research

Analyze rivalrous relationships between people using Wikidata's knowledge graph and AI.

## Features

- Search for people on Wikidata with disambiguation
- Extract relationships between entities using SPARQL
- AI-powered rivalry analysis with structured output
- Automatic source fetching and deduplication (SQLite)
- Source credibility scoring and validation
- Persistent analysis storage with full citation tracking
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
print(f"Sources: {len(analysis.sources)}")
print(f"\n{analysis.summary}")

# Timeline events with sources
for event in analysis.timeline:
    print(f"[{event.date}] {event.description}")
    print(f"  Sources: {event.source_count}, Confidence: {event.confidence:.2f}")
```

## CLI Commands

### Source Management

Manage sources with the hybrid workflow:

```bash
# Scan sources to see what's processed
rivalry sources scan

# Process unprocessed sources (e.g., manually added)
rivalry sources process --all

# Add a manual source
rivalry sources add Q9021 path/to/biography.pdf --title "Biography"

# Validate manual sources
rivalry sources validate

# View source statistics
rivalry sources stats
```

### File Search Management

Monitor File Search stores:

```bash
# Show sources available for indexing
rivalry fs show-sources

# List all stores
rivalry fs list-stores

# List documents in stores
rivalry fs list-docs

# Check store health
rivalry fs health-check
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

## Data Storage

Analyses and sources are saved with support for both auto-fetched and manual sources:

```
data/
├── sources.db              # SQLite - deduplicated sources with is_manual flag
├── raw_sources/            # Original content (HTML, PDF, text)
│   └── Max_Planck_Q9021/
│       ├── wikipedia/      # Auto-fetched Wikipedia content
│       ├── scholar_001/    # Auto-fetched Scholar papers
│       ├── arxiv_001/      # Auto-fetched arXiv papers
│       └── manual_001/     # Manually added sources
│           ├── original.pdf
│           ├── content.txt (auto-generated)
│           └── metadata.json (optional)
└── analyses/               # Analysis outputs (JSON)
    └── Q935_Q9047/
        └── analysis.json
```

## Workflows

### Automatic Workflow (Default)

```python
# Automatically fetches Wikipedia, Scholar, arXiv
analysis = analyze_rivalry("Q935", "Q9047")
# Analysis auto-saved to data/analyses/Q935_Q9047/analysis.json
```

### Hybrid Workflow (Auto + Manual)

```bash
# 1. Run automatic analysis
python -m rivalry_research analyze Q9021 Q93996

# 2. Add manual sources
rivalry sources add Q9021 biography.pdf --title "Max Planck Biography"

# 3. Process manual sources
rivalry sources process --entity Q9021

# 4. Re-run analysis (includes manual sources)
python -m rivalry_research analyze Q9021 Q93996
```

### Manual-Only Workflow

```bash
# 1. Add sources manually
mkdir -p data/raw_sources/Entity_Q9021/manual_001
cp biography.pdf data/raw_sources/Entity_Q9021/manual_001/original.pdf

# 2. Process sources
rivalry sources process --all

# 3. Run analysis
python -m rivalry_research analyze Q9021 Q93996
```

## Development

```bash
uv sync
```

## License

MIT
