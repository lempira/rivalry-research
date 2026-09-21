# Rivalry Research

A monorepo project for analyzing rivalrous relationships between people using Wikidata's knowledge graph and AI.

## Project Structure

This project is organized as a monorepo with two main directories:

- `backend/`: A Python-based library and CLI for data fetching, analysis, and storage.
- `app/`: An Astro-based frontend application for visualizing the research.

## Backend (`backend/`)

The backend is a Python package managed with `uv`. It handles the core logic of fetching data from Wikidata, arXiv, Google Scholar, and Wikipedia, processing it with LLMs (via PydanticAI), and storing the results.

### Key Technologies

- **Language:** Python 3.13+
- **Dependency Manager:** `uv`
- **AI Framework:** PydanticAI, Google GenAI
- **CLI:** Typer
- **Storage:** SQLite (`data/sources.db`) and File System (`data/raw_sources/`, `data/analyses/`)

### Setup & Usage

1.  Navigate to the directory: `cd backend`
2.  Install dependencies: `uv sync`
3.  Set up environment:
    - Copy `.env.example` to `.env`.
    - Set `GOOGLE_API_KEY`.
4.  Run the CLI:
    - The CLI is available as `rivalry` (configured in `pyproject.toml`).
    - Example: `uv run rivalry --help`

### Common Commands

- **Analyze a rivalry:** `uv run python -m rivalry_research analyze <ID1> <ID2>` (e.g., Q935 Q9047)
- **Manage sources:** `uv run rivalry sources --help`
- **Manage images:** `uv run rivalry images --help`
- **Check File Search health:** `uv run rivalry fs health-check`

## Frontend (`app/`)

The frontend is a web application built with Astro, designed to present the analyzed rivalries.

### Key Technologies

- **Framework:** Astro 5
- **Styling:** TailwindCSS 4
- **Package Manager:** `pnpm`

### Setup & Usage

1.  Navigate to the directory: `cd app`
2.  Install dependencies: `pnpm install`
3.  Start development server: `pnpm dev`
4.  Build for production: `pnpm build`

## Data Management

Data is stored in the `backend/data/` directory, which is shared concept but physically located in the backend folder.

- `sources.db`: SQLite database for deduplicated sources.
- `raw_sources/`: Raw content (PDFs, HTML, Images).
- `analyses/`: JSON output of AI analyses.

## Development Workflow

1.  **Backend Development:** Work in `backend/`. Use `uv` for all python commands.
2.  **Frontend Development:** Work in `app/`. Use `pnpm` for all node commands.
3.  **Integration:** The frontend likely consumes the JSON output from `backend/data/analyses/`.

## Important Notes

- **Hybrid Source Management:** The backend supports both automatically fetched sources and manually added ones (PDFs, images).
- **Image Handling:** Images are automatically downloaded from Commons/Wikipedia but can also be manually added and validated.

## Project Context & Constraints

- **Repo Type:** Monorepo.
- **Backend:** Python 3.13+, `uv`, PydanticAI, SQLite.
- **Frontend:** Astro 5, TailwindCSS 4.
- **Purpose:** Analyzing and visualizing rivalrous relationships between people.
- **Purpose:** Analyzing and visualizing rivalrous relationships between people.
