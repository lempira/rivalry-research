# Source CMS Architecture Plan

## Overview

Extract source/content management from `rivalry-research` into a new `source-cms` repository. The CMS will own source storage, image management, RAG integration, and source fetching from external APIs.

**Source Repository:** `rivalry-research/backend/`
**Target Repository:** `source-cms/` (already created)

---

## Phase 1: API Project Setup

### 1.1 Initialize Python Project with uv

```bash
cd source-cms
mkdir api
cd api

# Initialize uv project
uv init --name source-cms-api

# Add core dependencies
uv add fastapi uvicorn[standard] pydantic pydantic-settings
uv add sqlalchemy aiosqlite alembic
uv add httpx python-multipart
uv add google-cloud-storage
uv add google-genai  # For RAG/File Search

# Add fetcher dependencies (from rivalry-research)
uv add beautifulsoup4 scholarly arxiv pymupdf

# Add dev dependencies
uv add --dev pytest pytest-asyncio httpx ruff
```

### 1.2 API Directory Structure

```
source-cms/
├── api/
│   ├── pyproject.toml
│   ├── src/
│   │   └── source_cms_api/
│   │       ├── __init__.py
│   │       ├── main.py              # FastAPI app entry
│   │       ├── config.py            # Settings (Pydantic Settings)
│   │       ├── database.py          # SQLite/SQLAlchemy setup
│   │       ├── dependencies.py      # FastAPI dependencies
│   │       ├── models/              # SQLAlchemy ORM models
│   │       │   ├── __init__.py
│   │       │   ├── entity.py
│   │       │   ├── source.py
│   │       │   ├── image.py
│   │       │   └── rag.py
│   │       ├── schemas/             # Pydantic schemas (request/response)
│   │       │   ├── __init__.py
│   │       │   ├── entity.py
│   │       │   ├── source.py
│   │       │   ├── image.py
│   │       │   └── rag.py
│   │       ├── routers/             # API route handlers
│   │       │   ├── __init__.py
│   │       │   ├── sources.py
│   │       │   ├── images.py
│   │       │   ├── entities.py
│   │       │   ├── search.py        # External source search
│   │       │   └── rag.py
│   │       ├── services/            # Business logic
│   │       │   ├── __init__.py
│   │       │   ├── source_service.py
│   │       │   ├── image_service.py
│   │       │   ├── rag_service.py
│   │       │   ├── pdf_extractor.py
│   │       │   ├── credibility.py
│   │       │   └── fetchers/
│   │       │       ├── __init__.py
│   │       │       ├── base.py
│   │       │       ├── wikipedia.py
│   │       │       ├── scholar.py
│   │       │       ├── arxiv.py
│   │       │       ├── mactutor.py
│   │       │       └── images.py
│   │       └── storage/             # File storage (GCS)
│   │           ├── __init__.py
│   │           └── gcs.py
│   ├── migrations/                  # Alembic migrations
│   │   ├── env.py
│   │   └── versions/
│   ├── tests/
│   └── alembic.ini
├── app/                             # SolidStart frontend (Phase 5)
├── .env.example
├── .gitignore
└── README.md
```

### 1.3 Files to Copy from rivalry-research

| Source File | Target Location | Notes |
|-------------|-----------------|-------|
| `backend/src/rivalry_research/models.py` | `api/src/source_cms_api/schemas/` | Extract Source, EntityImage as Pydantic schemas |
| `backend/src/rivalry_research/storage/source_db.py` | `api/src/source_cms_api/services/source_service.py` | Adapt to SQLAlchemy async |
| `backend/src/rivalry_research/rag/file_search_client.py` | `api/src/source_cms_api/services/rag_service.py` | Port File Search integration |
| `backend/src/rivalry_research/sources/wikipedia_fetcher.py` | `api/src/source_cms_api/services/fetchers/wikipedia.py` | Keep rate limiting |
| `backend/src/rivalry_research/sources/scholar_fetcher.py` | `api/src/source_cms_api/services/fetchers/scholar.py` | Keep rate limiting |
| `backend/src/rivalry_research/sources/arxiv_fetcher.py` | `api/src/source_cms_api/services/fetchers/arxiv.py` | Keep rate limiting |
| `backend/src/rivalry_research/sources/mactutor_fetcher.py` | `api/src/source_cms_api/services/fetchers/mactutor.py` | Keep rate limiting |
| `backend/src/rivalry_research/sources/image_fetcher.py` | `api/src/source_cms_api/services/fetchers/images.py` | Commons, LoC, Europeana |
| `backend/src/rivalry_research/sources/pdf_extractor.py` | `api/src/source_cms_api/services/pdf_extractor.py` | PDF → text extraction |
| `backend/src/rivalry_research/sources/credibility.py` | `api/src/source_cms_api/services/credibility.py` | Credibility scoring |
| `backend/src/rivalry_research/sources/source_fetcher_utils.py` | `api/src/source_cms_api/services/fetchers/utils.py` | Rate limiter, helpers |

### 1.4 Core Implementation Files

#### `api/src/source_cms_api/config.py`
```python
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite+aiosqlite:///./data/sources.db"

    # Google Cloud Storage
    gcs_bucket: str = "source-cms-dev"
    gcs_project: str | None = None

    # Google AI (for RAG)
    google_api_key: str

    # API
    api_prefix: str = "/api/v1"
    debug: bool = False

    class Config:
        env_file = ".env"

settings = Settings()
```

#### `api/src/source_cms_api/database.py`
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from .config import settings

engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with async_session() as session:
        yield session
```

#### `api/src/source_cms_api/main.py`
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import sources, images, entities, search, rag

app = FastAPI(
    title="Source CMS API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # SolidStart dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(sources.router, prefix=f"{settings.api_prefix}/sources", tags=["sources"])
app.include_router(images.router, prefix=f"{settings.api_prefix}/images", tags=["images"])
app.include_router(entities.router, prefix=f"{settings.api_prefix}/entities", tags=["entities"])
app.include_router(search.router, prefix=f"{settings.api_prefix}/search", tags=["search"])
app.include_router(rag.router, prefix=f"{settings.api_prefix}/rag", tags=["rag"])

@app.get("/health")
async def health():
    return {"status": "ok"}
```

### 1.5 Run API Development Server

```bash
cd api
uv run uvicorn source_cms_api.main:app --reload --port 8000
```

---

## Phase 2: Database Schema (SQLite)

### 2.1 Initialize Alembic

```bash
cd api
uv run alembic init migrations
```

### 2.2 SQLAlchemy Models

#### `api/src/source_cms_api/models/entity.py`
```python
from sqlalchemy import Column, String, Text
from sqlalchemy.orm import relationship
from ..database import Base
import uuid

class Entity(Base):
    __tablename__ = "entities"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    wikidata_id = Column(String(20), unique=True, nullable=False, index=True)
    label = Column(String(255), nullable=False)
    description = Column(Text)
    wikipedia_url = Column(String(500))
    claims = Column(Text, default="{}")  # JSON as text
    created_at = Column(String(30), server_default="(datetime('now'))")

    sources = relationship("Source", back_populates="entity")
    images = relationship("Image", back_populates="entity")
```

#### `api/src/source_cms_api/models/source.py`
```python
from sqlalchemy import Column, String, Text, Float, Integer, ForeignKey
from sqlalchemy.orm import relationship
from ..database import Base
import uuid

class Source(Base):
    __tablename__ = "sources"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id = Column(String(50), unique=True, nullable=False, index=True)
    type = Column(String(50), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    authors = Column(Text)  # JSON array as string
    publication = Column(String(255))
    publication_date = Column(String(20))
    url = Column(String(2000), unique=True, nullable=False, index=True)
    doi = Column(String(100))
    credibility_score = Column(Float, default=0.5)
    is_primary_source = Column(Integer, default=0)
    stored_content_path = Column(String(500))
    content_hash = Column(String(64))
    is_manual = Column(Integer, default=0)
    entity_id = Column(String(36), ForeignKey("entities.id"), index=True)
    created_at = Column(String(30), server_default="(datetime('now'))")

    entity = relationship("Entity", back_populates="sources")
    rag_documents = relationship("RAGDocument", back_populates="source")
```

#### `api/src/source_cms_api/models/image.py`
```python
from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from ..database import Base
import uuid

class Image(Base):
    __tablename__ = "images"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    url = Column(String(2000), nullable=False)
    thumbnail_url = Column(String(2000))
    source = Column(String(50), nullable=False)  # commons, wikipedia, loc, europeana, manual
    title = Column(String(500))
    license = Column(String(50), nullable=False)
    attribution = Column(String(500))
    local_path = Column(String(500))
    thumbnail_path = Column(String(500))
    entity_id = Column(String(36), ForeignKey("entities.id"), index=True)
    created_at = Column(String(30), server_default="(datetime('now'))")

    entity = relationship("Entity", back_populates="images")
```

#### `api/src/source_cms_api/models/rag.py`
```python
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from ..database import Base
import uuid

class RAGStore(Base):
    __tablename__ = "rag_stores"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    store_name = Column(String(255), unique=True, nullable=False)
    created_at = Column(String(30), server_default="(datetime('now'))")

    documents = relationship("RAGDocument", back_populates="store")

class RAGDocument(Base):
    __tablename__ = "rag_documents"

    store_id = Column(String(36), ForeignKey("rag_stores.id"), primary_key=True)
    source_id = Column(String(36), ForeignKey("sources.id"), primary_key=True)
    uploaded_at = Column(String(30), server_default="(datetime('now'))")

    store = relationship("RAGStore", back_populates="documents")
    source = relationship("Source", back_populates="rag_documents")
```

### 2.3 Create Initial Migration

```bash
cd api
uv run alembic revision --autogenerate -m "Initial schema"
uv run alembic upgrade head
```

---

## Phase 3: API Endpoints

### 3.1 Sources Router

#### `api/src/source_cms_api/routers/sources.py`
```python
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from ..database import get_db
from ..schemas.source import SourceCreate, SourceUpdate, SourceResponse, SourceList
from ..services.source_service import SourceService

router = APIRouter()

@router.get("", response_model=SourceList)
async def list_sources(
    type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    is_manual: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    service = SourceService(db)
    return await service.list_sources(type=type, entity_id=entity_id, is_manual=is_manual, page=page, per_page=per_page)

@router.post("", response_model=SourceResponse, status_code=201)
async def create_source(source: SourceCreate, db: AsyncSession = Depends(get_db)):
    service = SourceService(db)
    return await service.create_source(source)

@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(source_id: str, db: AsyncSession = Depends(get_db)):
    service = SourceService(db)
    source = await service.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source

@router.put("/{source_id}", response_model=SourceResponse)
async def update_source(source_id: str, source: SourceUpdate, db: AsyncSession = Depends(get_db)):
    service = SourceService(db)
    return await service.update_source(source_id, source)

@router.delete("/{source_id}", status_code=204)
async def delete_source(source_id: str, db: AsyncSession = Depends(get_db)):
    service = SourceService(db)
    await service.delete_source(source_id)

@router.post("/{source_id}/content")
async def upload_content(
    source_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    service = SourceService(db)
    return await service.upload_content(source_id, file)

@router.get("/{source_id}/content")
async def get_content(source_id: str, db: AsyncSession = Depends(get_db)):
    service = SourceService(db)
    return await service.get_content(source_id)

@router.post("/by-ids", response_model=list[SourceResponse])
async def get_sources_by_ids(source_ids: list[str], db: AsyncSession = Depends(get_db)):
    service = SourceService(db)
    return await service.get_sources_by_ids(source_ids)
```

### 3.2 Search Router (External Sources)

#### `api/src/source_cms_api/routers/search.py`
```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..schemas.search import SearchResult, FetchRequest, FetchResponse
from ..services.fetchers import WikipediaFetcher, ScholarFetcher, ArxivFetcher, MacTutorFetcher

router = APIRouter()

@router.get("/wikipedia", response_model=list[SearchResult])
async def search_wikipedia(q: str = Query(..., min_length=2)):
    fetcher = WikipediaFetcher()
    return await fetcher.search(q)

@router.get("/scholar", response_model=list[SearchResult])
async def search_scholar(q: str = Query(..., min_length=2), max_results: int = Query(10, le=20)):
    fetcher = ScholarFetcher()
    return await fetcher.search(q, max_results=max_results)

@router.get("/arxiv", response_model=list[SearchResult])
async def search_arxiv(q: str = Query(..., min_length=2), max_results: int = Query(10, le=20)):
    fetcher = ArxivFetcher()
    return await fetcher.search(q, max_results=max_results)

@router.get("/mactutor", response_model=list[SearchResult])
async def search_mactutor(q: str = Query(..., min_length=2)):
    fetcher = MacTutorFetcher()
    return await fetcher.search(q)

@router.post("/fetch", response_model=FetchResponse)
async def fetch_and_save(
    request: FetchRequest,
    db: AsyncSession = Depends(get_db)
):
    """Fetch a search result and save it as a source."""
    # Get appropriate fetcher based on source type
    # Fetch full content, extract text, save to GCS, create source record
    pass
```

### 3.3 RAG Router

#### `api/src/source_cms_api/routers/rag.py`
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..schemas.rag import StoreCreate, StoreResponse, QueryRequest, QueryResponse, UploadRequest
from ..services.rag_service import RAGService

router = APIRouter()

@router.get("/stores", response_model=list[StoreResponse])
async def list_stores(db: AsyncSession = Depends(get_db)):
    service = RAGService(db)
    return await service.list_stores()

@router.post("/stores", response_model=StoreResponse, status_code=201)
async def create_store(store: StoreCreate, db: AsyncSession = Depends(get_db)):
    service = RAGService(db)
    return await service.create_store(store.name)

@router.delete("/stores/{store_name}", status_code=204)
async def delete_store(store_name: str, db: AsyncSession = Depends(get_db)):
    service = RAGService(db)
    await service.delete_store(store_name)

@router.get("/stores/{store_name}/health")
async def store_health(store_name: str, db: AsyncSession = Depends(get_db)):
    service = RAGService(db)
    return await service.health_check(store_name)

@router.post("/stores/{store_name}/documents")
async def upload_document(
    store_name: str,
    request: UploadRequest,
    db: AsyncSession = Depends(get_db)
):
    service = RAGService(db)
    return await service.upload_source_to_store(store_name, request.source_id)

@router.post("/stores/{store_name}/query", response_model=QueryResponse)
async def query_store(
    store_name: str,
    request: QueryRequest,
    db: AsyncSession = Depends(get_db)
):
    service = RAGService(db)
    return await service.query(store_name, request.query)

@router.post("/stores/{store_name}/retrieve")
async def retrieve_chunks(
    store_name: str,
    request: QueryRequest,
    db: AsyncSession = Depends(get_db)
):
    service = RAGService(db)
    return await service.retrieve(store_name, request.query)
```

---

## Phase 4: File Storage (GCS)

### 4.1 GCS Setup

```bash
# Create buckets
gsutil mb -l us-central1 gs://source-cms-dev
gsutil mb -l us-central1 gs://source-cms-prod

# Set lifecycle policy for dev bucket (auto-delete after 30 days)
cat > lifecycle.json << 'EOF'
{
  "rule": [
    {
      "action": {"type": "Delete"},
      "condition": {"age": 30}
    }
  ]
}
EOF
gsutil lifecycle set lifecycle.json gs://source-cms-dev

# Local development auth
gcloud auth application-default login
```

### 4.2 GCS Storage Service

#### `api/src/source_cms_api/storage/gcs.py`
```python
from google.cloud import storage
from google.cloud.exceptions import NotFound
from ..config import settings

class GCSStorage:
    def __init__(self):
        self.client = storage.Client(project=settings.gcs_project)
        self.bucket = self.client.bucket(settings.gcs_bucket)

    async def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        blob = self.bucket.blob(key)
        blob.upload_from_string(data, content_type=content_type)
        return f"gs://{self.bucket.name}/{key}"

    async def get(self, key: str) -> bytes:
        blob = self.bucket.blob(key)
        return blob.download_as_bytes()

    async def delete(self, key: str) -> None:
        blob = self.bucket.blob(key)
        try:
            blob.delete()
        except NotFound:
            pass

    async def exists(self, key: str) -> bool:
        blob = self.bucket.blob(key)
        return blob.exists()

    def get_signed_url(self, key: str, expires_in: int = 3600) -> str:
        blob = self.bucket.blob(key)
        return blob.generate_signed_url(expiration=expires_in)

    def get_public_url(self, key: str) -> str:
        return f"https://storage.googleapis.com/{self.bucket.name}/{key}"

# Singleton
gcs_storage = GCSStorage()
```

### 4.3 Storage Path Structure

```
gs://source-cms-{env}/
├── sources/
│   └── {entity_wikidata_id}/           # e.g., Q935
│       └── {source_type}_{index}/      # e.g., wikipedia_001, scholar_002
│           ├── original.pdf            # or original.html
│           └── content.txt             # Extracted text
├── images/
│   └── {entity_wikidata_id}/
│       └── {source}_{index}/           # e.g., commons_001, manual_002
│           ├── image.jpg               # Full resolution
│           └── thumbnail.jpg           # Resized thumbnail
└── temp/
    └── uploads/                        # Temporary upload staging
```

---

## Phase 5: SolidStart Admin UI

### 5.1 Initialize SolidStart Project

```bash
cd source-cms

# Create SolidStart app
pnpm create solid@latest app
# Select: SolidStart, TypeScript, Tailwind CSS

cd app

# Add dependencies
pnpm add @tanstack/solid-query
pnpm add @solidjs/router
pnpm add solid-icons
```

### 5.2 App Directory Structure

```
source-cms/
└── app/
    ├── package.json
    ├── src/
    │   ├── app.tsx
    │   ├── entry-client.tsx
    │   ├── entry-server.tsx
    │   ├── routes/
    │   │   ├── index.tsx              # Dashboard
    │   │   ├── sources/
    │   │   │   ├── index.tsx          # Source list
    │   │   │   ├── [id].tsx           # Source detail/edit
    │   │   │   └── new.tsx            # Add source form
    │   │   ├── images/
    │   │   │   ├── index.tsx          # Image gallery
    │   │   │   └── new.tsx            # Add image
    │   │   ├── search/
    │   │   │   └── index.tsx          # External source search
    │   │   └── rag/
    │   │       ├── index.tsx          # Store list
    │   │       └── [name].tsx         # Store detail + query test
    │   ├── components/
    │   │   ├── layout/
    │   │   │   ├── Sidebar.tsx
    │   │   │   └── Header.tsx
    │   │   ├── sources/
    │   │   │   ├── SourceTable.tsx
    │   │   │   ├── SourceForm.tsx
    │   │   │   └── SourceCard.tsx
    │   │   ├── images/
    │   │   │   ├── ImageGrid.tsx
    │   │   │   └── ImageUpload.tsx
    │   │   ├── search/
    │   │   │   ├── SearchBar.tsx
    │   │   │   ├── ResultCard.tsx
    │   │   │   └── SourcePreview.tsx
    │   │   └── ui/
    │   │       ├── Button.tsx
    │   │       ├── Input.tsx
    │   │       ├── Modal.tsx
    │   │       └── Table.tsx
    │   ├── lib/
    │   │   ├── api.ts                 # API client
    │   │   └── utils.ts
    │   └── styles/
    │       └── app.css
    ├── tailwind.config.js
    └── vite.config.ts
```

### 5.3 API Client

#### `app/src/lib/api.ts`
```typescript
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export const api = {
  sources: {
    list: (params?: Record<string, string>) =>
      fetchAPI<SourceList>(`/sources?${new URLSearchParams(params)}`),
    get: (id: string) => fetchAPI<Source>(`/sources/${id}`),
    create: (data: SourceCreate) =>
      fetchAPI<Source>('/sources', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: string, data: SourceUpdate) =>
      fetchAPI<Source>(`/sources/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id: string) =>
      fetchAPI<void>(`/sources/${id}`, { method: 'DELETE' }),
  },
  search: {
    wikipedia: (q: string) => fetchAPI<SearchResult[]>(`/search/wikipedia?q=${q}`),
    scholar: (q: string) => fetchAPI<SearchResult[]>(`/search/scholar?q=${q}`),
    arxiv: (q: string) => fetchAPI<SearchResult[]>(`/search/arxiv?q=${q}`),
    mactutor: (q: string) => fetchAPI<SearchResult[]>(`/search/mactutor?q=${q}`),
    fetch: (data: FetchRequest) =>
      fetchAPI<Source>('/search/fetch', { method: 'POST', body: JSON.stringify(data) }),
  },
  rag: {
    stores: () => fetchAPI<Store[]>('/rag/stores'),
    createStore: (name: string) =>
      fetchAPI<Store>('/rag/stores', { method: 'POST', body: JSON.stringify({ name }) }),
    query: (storeName: string, query: string) =>
      fetchAPI<QueryResponse>(`/rag/stores/${storeName}/query`, {
        method: 'POST', body: JSON.stringify({ query })
      }),
  },
  images: {
    list: (entityId?: string) =>
      fetchAPI<Image[]>(`/images${entityId ? `?entity_id=${entityId}` : ''}`),
  },
};
```

### 5.4 Run Frontend Development Server

```bash
cd app
pnpm dev  # Runs on http://localhost:3000
```

---

## Phase 6: Generate Python Client

### 6.1 Generate Client from OpenAPI

```bash
# In source-cms repo
pip install openapi-python-client

# Generate client from running API
openapi-python-client generate --url http://localhost:8000/openapi.json --output-path ./clients/python

# Or save spec and generate
curl http://localhost:8000/openapi.json > openapi.json
openapi-python-client generate --path openapi.json --output-path ./clients/python
```

### 6.2 Use Client in rivalry-research

```bash
# In rivalry-research repo
cd backend
uv add git+https://github.com/yourusername/source-cms.git#subdirectory=clients/python
```

#### Updated rivalry-research code
```python
# Old imports (remove these)
# from rivalry_research.storage import SourceDatabase
# from rivalry_research.rag import file_search_client
# from rivalry_research.sources import fetch_sources_for_entity

# New imports
from source_cms_client import Client
from source_cms_client.api.sources import list_sources, get_sources_by_ids
from source_cms_client.api.rag import query_store, retrieve_chunks

# Initialize client
cms_client = Client(base_url="https://cms.example.com")

# Fetch sources
sources = list_sources.sync(client=cms_client, entity_id="Q935")

# Query RAG
response = query_store.sync(
    client=cms_client,
    store_name="rivalry_research",
    query="Newton vs Leibniz calculus dispute"
)
```

---

## Environment Configuration

### `.env.example`
```bash
# Database
DATABASE_URL=sqlite+aiosqlite:///./data/sources.db

# Google Cloud
GCS_BUCKET=source-cms-dev
GCS_PROJECT=your-gcp-project-id
GOOGLE_API_KEY=your-google-api-key

# API
API_PREFIX=/api/v1
DEBUG=true

# Frontend
VITE_API_URL=http://localhost:8000/api/v1
```

### `.env.production`
```bash
DATABASE_URL=sqlite+aiosqlite:///./data/sources.db
GCS_BUCKET=source-cms-prod
GCS_PROJECT=your-gcp-project-id
GOOGLE_API_KEY=your-google-api-key
API_PREFIX=/api/v1
DEBUG=false
VITE_API_URL=https://api.your-domain.com/api/v1
```

---

## Tech Stack Summary

| Component | Technology | Version |
|-----------|------------|---------|
| **API Framework** | FastAPI | latest |
| **Validation** | Pydantic | v2 |
| **ORM** | SQLAlchemy | 2.0+ |
| **Database** | SQLite | (aiosqlite for async) |
| **Migrations** | Alembic | latest |
| **HTTP Client** | httpx | latest |
| **File Storage** | Google Cloud Storage | latest |
| **RAG** | Google GenAI (File Search) | latest |
| **Frontend** | SolidJS + SolidStart | latest |
| **Styling** | Tailwind CSS | v4 |
| **Data Fetching** | @tanstack/solid-query | latest |
| **Python Pkg Mgr** | uv | latest |
| **Node Pkg Mgr** | pnpm | latest |

---

## Deployment

### API (Cloud Run)

```bash
# Build and deploy
cd api
gcloud run deploy source-cms-api \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "GCS_BUCKET=source-cms-prod,GCS_PROJECT=your-project"
```

### Frontend (Vercel/Cloudflare Pages)

```bash
cd app
pnpm build
# Deploy dist/ to hosting platform
```

---

## API Documentation

Once API is running:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json