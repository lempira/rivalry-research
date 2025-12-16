"""SQLite database for source deduplication and management."""

import logging
import sqlite3
from pathlib import Path
from typing import Any

from ..models import Source

logger = logging.getLogger(__name__)


class SourceDatabase:
    """Manages SQLite database for source storage and deduplication."""

    def __init__(self, db_path: str | Path):
        """
        Initialize source database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_schema()

    def _create_schema(self) -> None:
        """Create database schema if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sources (
                    source_id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    authors TEXT,
                    publication TEXT,
                    publication_date TEXT,
                    url TEXT NOT NULL UNIQUE,
                    doi TEXT,
                    isbn TEXT,
                    retrieved_at TEXT NOT NULL,
                    credibility_score REAL DEFAULT 0.5,
                    is_primary_source INTEGER DEFAULT 0,
                    stored_content_path TEXT,
                    content_hash TEXT,
                    is_manual INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index on URL for fast deduplication checks
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sources_url ON sources(url)
            """)
            
            # Create index on content_hash for additional deduplication
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sources_hash ON sources(content_hash)
            """)
            
            conn.commit()
            logger.debug(f"Database schema initialized at {self.db_path}")

    def get_source_by_url(self, url: str) -> Source | None:
        """
        Check if a source with this URL already exists.

        Args:
            url: Source URL to check

        Returns:
            Source object if found, None otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM sources WHERE url = ?",
                (url,)
            )
            row = cursor.fetchone()
            
            if row:
                return self._row_to_source(row)
            return None

    def get_source_by_id(self, source_id: str) -> Source | None:
        """
        Retrieve a source by its ID.

        Args:
            source_id: Source identifier

        Returns:
            Source object if found, None otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM sources WHERE source_id = ?",
                (source_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return self._row_to_source(row)
            return None

    def get_sources_by_ids(self, source_ids: list[str]) -> dict[str, Source]:
        """
        Retrieve multiple sources by their IDs.

        Args:
            source_ids: List of source identifiers

        Returns:
            Dictionary mapping source_id to Source object
        """
        if not source_ids:
            return {}
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            placeholders = ",".join("?" * len(source_ids))
            cursor = conn.execute(
                f"SELECT * FROM sources WHERE source_id IN ({placeholders})",
                source_ids
            )
            
            return {
                row["source_id"]: self._row_to_source(row)
                for row in cursor.fetchall()
            }

    def add_source(self, source: Source) -> Source:
        """
        Add a new source to the database.

        Performs deduplication by URL. If URL exists, returns existing source.

        Args:
            source: Source object to add

        Returns:
            The added source (or existing source if URL duplicate)
        """
        # Check if URL already exists
        existing = self.get_source_by_url(source.url)
        if existing:
            logger.debug(f"Source URL already exists: {source.url} (ID: {existing.source_id})")
            return existing
        
        with sqlite3.connect(self.db_path) as conn:
            # Convert authors list to JSON string
            authors_json = ",".join(source.authors) if source.authors else ""
            
            conn.execute(
                """
                INSERT INTO sources (
                    source_id, type, title, authors, publication, publication_date,
                    url, doi, isbn, retrieved_at, credibility_score, is_primary_source,
                    stored_content_path, content_hash, is_manual
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source.source_id,
                    source.type,
                    source.title,
                    authors_json,
                    source.publication,
                    source.publication_date,
                    source.url,
                    source.doi,
                    source.isbn,
                    source.retrieved_at,
                    source.credibility_score,
                    1 if source.is_primary_source else 0,
                    source.stored_content_path,
                    source.content_hash,
                    1 if source.is_manual else 0,
                )
            )
            conn.commit()
            logger.debug(f"Added new source: {source.source_id} - {source.title}")
        
        return source

    def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about stored sources.

        Returns:
            Dictionary with counts and statistics
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM sources")
            total = cursor.fetchone()[0]
            
            cursor = conn.execute(
                "SELECT type, COUNT(*) as count FROM sources GROUP BY type"
            )
            by_type = {row[0]: row[1] for row in cursor.fetchall()}
            
            cursor = conn.execute(
                "SELECT COUNT(*) FROM sources WHERE is_primary_source = 1"
            )
            primary_count = cursor.fetchone()[0]
            
            return {
                "total_sources": total,
                "by_type": by_type,
                "primary_sources": primary_count,
                "secondary_sources": total - primary_count,
            }

    def _row_to_source(self, row: sqlite3.Row) -> Source:
        """
        Convert database row to Source model.

        Args:
            row: SQLite row object

        Returns:
            Source object
        """
        # Parse authors from comma-separated string
        authors_str = row["authors"] or ""
        authors = [a.strip() for a in authors_str.split(",") if a.strip()]
        
        return Source(
            source_id=row["source_id"],
            type=row["type"],
            title=row["title"],
            authors=authors,
            publication=row["publication"],
            publication_date=row["publication_date"],
            url=row["url"],
            doi=row["doi"],
            isbn=row["isbn"],
            retrieved_at=row["retrieved_at"],
            credibility_score=row["credibility_score"],
            is_primary_source=bool(row["is_primary_source"]),
            stored_content_path=row["stored_content_path"],
            content_hash=row["content_hash"],
            is_manual=bool(row.get("is_manual", 0)),
        )

