"""Utility functions for source management."""

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path


def generate_source_id(url: str, prefix: str = "src") -> str:
    """
    Generate a unique source identifier based on URL.
    
    Uses URL hash to ensure the same source always gets the same ID,
    which aids in deduplication and debugging.
    
    Args:
        url: Source URL (used for generating unique hash)
        prefix: Prefix for the ID (default: "src")
    
    Returns:
        Unique source ID (e.g., "src_a3f2b1c4d5e6")
    """
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:12]
    return f"{prefix}_{url_hash}"


def hash_url(url: str) -> str:
    """
    Create a hash from a URL for use in file paths.
    
    Args:
        url: Source URL
    
    Returns:
        SHA256 hash (first 16 characters)
    """
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def sanitize_filename(filename: str, max_length: int = 200) -> str:
    """
    Sanitize a filename for safe filesystem storage.
    
    Args:
        filename: Original filename
        max_length: Maximum length for the filename
    
    Returns:
        Safe filename
    """
    # Remove or replace invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove control characters
    sanitized = re.sub(r'[\x00-\x1f\x7f]', '', sanitized)
    # Replace multiple underscores/spaces with single underscore
    sanitized = re.sub(r'[_\s]+', '_', sanitized)
    # Trim and limit length
    sanitized = sanitized.strip('._')[:max_length]
    return sanitized or "unnamed"


def get_content_path(base_dir: Path, url: str, extension: str = "txt") -> Path:
    """
    Generate a storage path for source content based on URL hash.
    
    Args:
        base_dir: Base directory for raw sources
        url: Source URL
        extension: File extension (default: "txt")
    
    Returns:
        Path for storing the content
    """
    url_hash = hash_url(url)
    content_dir = base_dir / url_hash
    content_dir.mkdir(parents=True, exist_ok=True)
    return content_dir / f"content.{extension}"


def get_original_file_path(base_dir: Path, url: str, extension: str) -> Path:
    """
    Generate a storage path for the original source file based on URL hash.
    
    Args:
        base_dir: Base directory for raw sources
        url: Source URL
        extension: File extension (e.g., "pdf", "html")
    
    Returns:
        Path for storing the original file
    """
    url_hash = hash_url(url)
    content_dir = base_dir / url_hash
    content_dir.mkdir(parents=True, exist_ok=True)
    return content_dir / f"original.{extension}"


def sanitize_entity_name(name: str, max_length: int = 50) -> str:
    """
    Sanitize entity name for use in directory names.
    
    Args:
        name: Entity name (e.g., "Isaac Newton")
        max_length: Maximum length for the name
    
    Returns:
        Sanitized name safe for filesystem
    """
    # Replace spaces with underscores
    sanitized = name.replace(' ', '_')
    # Remove or replace invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', sanitized)
    # Remove control characters
    sanitized = re.sub(r'[\x00-\x1f\x7f]', '', sanitized)
    # Replace multiple underscores with single underscore
    sanitized = re.sub(r'_+', '_', sanitized)
    # Trim and limit length
    sanitized = sanitized.strip('._')[:max_length]
    return sanitized or "unknown"


def get_entity_directory(base_dir: Path, entity_name: str, entity_id: str) -> Path:
    """
    Get directory for an entity's sources.
    
    Args:
        base_dir: Base directory for raw sources
        entity_name: Entity name (e.g., "Isaac Newton")
        entity_id: Entity Wikidata ID (e.g., "Q935")
    
    Returns:
        Path to entity directory (e.g., "Isaac_Newton_Q935/")
    """
    safe_name = sanitize_entity_name(entity_name)
    entity_folder = f"{safe_name}_{entity_id}"
    entity_dir = base_dir / entity_folder
    entity_dir.mkdir(parents=True, exist_ok=True)
    return entity_dir


def get_source_directory(entity_dir: Path, source_type: str) -> tuple[Path, int]:
    """
    Get directory for a specific source within an entity directory.
    
    For wikipedia: returns entity_dir/wikipedia/
    For scholar/arxiv: returns entity_dir/scholar_NNN/ with auto-incrementing counter
    
    Args:
        entity_dir: Entity directory path
        source_type: Source type ("wikipedia", "scholar", "arxiv")
    
    Returns:
        Tuple of (source_dir, counter) where counter is 0 for wikipedia
    """
    # Wikipedia gets its own single directory
    if source_type == "wikipedia":
        source_dir = entity_dir / "wikipedia"
        source_dir.mkdir(parents=True, exist_ok=True)
        return source_dir, 0
    
    # Scholar and arXiv get numbered directories
    # Find next available number
    counter = 1
    while True:
        source_dir = entity_dir / f"{source_type}_{counter:03d}"
        if not source_dir.exists():
            source_dir.mkdir(parents=True, exist_ok=True)
            return source_dir, counter
        counter += 1


def get_iso_timestamp() -> str:
    """
    Get current timestamp in ISO format.
    
    Returns:
        ISO 8601 timestamp string
    """
    return datetime.now(timezone.utc).isoformat()


def extract_entity_id_from_path(path: Path) -> str:
    """
    Extract entity ID from a directory path.
    
    Expects directory names like "Max_Planck_Q9021" or "Ernst_Mach_Q93996"
    
    Args:
        path: Path to entity directory
    
    Returns:
        Entity ID (e.g., "Q9021") or "unknown" if not found
    """
    dir_name = path.name
    # Match pattern like Q followed by digits at the end
    match = re.search(r'_(Q\d+)$', dir_name)
    if match:
        return match.group(1)
    
    # Try without underscore prefix (in case dir is just "Q9021")
    match = re.search(r'^(Q\d+)$', dir_name)
    if match:
        return match.group(1)
    
    return "unknown"

