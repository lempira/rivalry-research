"""Scans and detects sources in the raw_sources directory."""

import logging
from pathlib import Path

from ..models import Source
from ..storage import SourceDatabase
from .pdf_extractor import extract_pdf_text
from .utils import extract_entity_id_from_path

logger = logging.getLogger(__name__)


class SourceScanResult:
    """Result of scanning the raw_sources directory."""

    def __init__(self):
        self.sources_in_db: list[Source] = []
        self.sources_not_in_db: list[dict] = []
        self.invalid_sources: list[dict] = []


def scan_raw_sources_directory(
    raw_sources_dir: Path,
    db: SourceDatabase,
    entity_filter: str | None = None,
) -> SourceScanResult:
    """
    Scan raw_sources directory and categorize all sources.

    Args:
        raw_sources_dir: Path to raw_sources directory
        db: SourceDatabase instance
        entity_filter: Optional entity ID to scan only that entity's sources (e.g., "Q9021")

    Returns:
        SourceScanResult with categorized sources
    """
    result = SourceScanResult()
    raw_sources_dir = Path(raw_sources_dir)

    if not raw_sources_dir.exists():
        logger.warning(f"Raw sources directory does not exist: {raw_sources_dir}")
        return result

    logger.info(f"Scanning raw sources directory: {raw_sources_dir}")

    # Get all entity directories
    entity_dirs = [d for d in raw_sources_dir.iterdir() if d.is_dir()]

    for entity_dir in entity_dirs:
        # Extract entity ID from directory name (e.g., "Max_Planck_Q9021" -> "Q9021")
        entity_id = extract_entity_id_from_path(entity_dir)
        
        # Skip if entity filter is set and doesn't match
        if entity_filter and entity_id != entity_filter:
            continue

        logger.debug(f"Scanning entity directory: {entity_dir.name}")

        # Get all source directories within this entity
        source_dirs = [d for d in entity_dir.iterdir() if d.is_dir()]

        for source_dir in source_dirs:
            _scan_source_directory(source_dir, db, result, entity_dir.name, entity_id)

    logger.info(
        f"Scan complete: {len(result.sources_in_db)} in DB, "
        f"{len(result.sources_not_in_db)} not in DB, "
        f"{len(result.invalid_sources)} invalid"
    )

    return result


def _scan_source_directory(
    source_dir: Path,
    db: SourceDatabase,
    result: SourceScanResult,
    entity_name: str,
    entity_id: str,
) -> None:
    """
    Scan a single source directory and categorize it.

    Args:
        source_dir: Path to source directory (e.g., manual_001, wikipedia, scholar_002)
        db: SourceDatabase instance
        result: SourceScanResult to populate
        entity_name: Entity directory name
        entity_id: Entity ID (e.g., "Q9021")
    """
    # Look for original file (PDF or HTML)
    original_pdf = source_dir / "original.pdf"
    original_html = source_dir / "original.html"
    content_txt = source_dir / "content.txt"

    # Determine which original file exists
    if original_pdf.exists():
        original_file = original_pdf
        file_type = "pdf"
    elif original_html.exists():
        original_file = original_html
        file_type = "html"
    else:
        logger.warning(f"No original file found in {source_dir}")
        result.invalid_sources.append({
            "path": str(source_dir),
            "reason": "No original.pdf or original.html found",
            "entity_id": entity_id,
        })
        return

    # Check if this source is already in the database
    # For manual sources, we use a pseudo-URL based on the file path
    pseudo_url = _generate_pseudo_url(entity_id, source_dir.name, file_type)
    
    existing_source = db.get_source_by_url(pseudo_url)

    if existing_source:
        logger.debug(f"Source already in DB: {existing_source.source_id}")
        result.sources_in_db.append(existing_source)
    else:
        # Source not in DB - needs processing
        logger.debug(f"Source not in DB: {source_dir}")
        
        # Store metadata about unprocessed source
        metadata = {
            "source_dir": str(source_dir),
            "original_file": str(original_file),
            "file_type": file_type,
            "entity_name": entity_name,
            "entity_id": entity_id,
            "has_content_txt": content_txt.exists(),
            "pseudo_url": pseudo_url,
        }
        result.sources_not_in_db.append(metadata)


def _generate_pseudo_url(entity_id: str, source_dir_name: str, file_type: str) -> str:
    """
    Generate a pseudo-URL for sources without a real URL (e.g., manual sources).

    Args:
        entity_id: Entity ID (e.g., "Q9021")
        source_dir_name: Source directory name (e.g., "manual_001")
        file_type: File type ("pdf" or "html")

    Returns:
        Pseudo-URL string
    """
    return f"file://local/{entity_id}/{source_dir_name}/original.{file_type}"


def detect_unprocessed_sources(
    raw_sources_dir: Path,
    db: SourceDatabase,
    entity_filter: str | None = None,
) -> list[dict]:
    """
    Detect sources that exist on disk but are not in the database.

    Args:
        raw_sources_dir: Path to raw_sources directory
        db: SourceDatabase instance
        entity_filter: Optional entity ID to scan only that entity's sources

    Returns:
        List of metadata dictionaries for unprocessed sources
    """
    result = scan_raw_sources_directory(raw_sources_dir, db, entity_filter)
    return result.sources_not_in_db


def validate_manual_source(source_dir: Path) -> tuple[bool, str]:
    """
    Validate a manually added source directory.

    Args:
        source_dir: Path to source directory

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not source_dir.exists():
        return False, "Directory does not exist"

    if not source_dir.is_dir():
        return False, "Path is not a directory"

    # Check for original file
    original_pdf = source_dir / "original.pdf"
    original_html = source_dir / "original.html"

    if not original_pdf.exists() and not original_html.exists():
        return False, "No original.pdf or original.html found"

    # Check if file is readable
    original_file = original_pdf if original_pdf.exists() else original_html

    try:
        with open(original_file, "rb") as f:
            # Try to read first 100 bytes
            f.read(100)
    except Exception as e:
        return False, f"File is not readable: {e}"

    # If PDF, try to extract content
    if original_file.suffix == ".pdf":
        try:
            content = extract_pdf_text(original_file)
            if not content or len(content.strip()) < 50:
                return False, "PDF appears to be empty or unreadable"
        except Exception as e:
            return False, f"Failed to extract text from PDF: {e}"

    return True, "Valid"


def get_source_statistics(raw_sources_dir: Path, db: SourceDatabase) -> dict:
    """
    Get statistics about sources in the raw_sources directory.

    Args:
        raw_sources_dir: Path to raw_sources directory
        db: SourceDatabase instance

    Returns:
        Dictionary with statistics
    """
    result = scan_raw_sources_directory(raw_sources_dir, db)

    # Count by is_manual flag
    manual_count = 0
    auto_count = 0
    for source in result.sources_in_db:
        if source.is_manual:
            manual_count += 1
        else:
            auto_count += 1

    return {
        "total_sources": len(result.sources_in_db),
        "unprocessed_sources": len(result.sources_not_in_db),
        "invalid_sources": len(result.invalid_sources),
        "manual_sources": manual_count,
        "auto_sources": auto_count,
    }

