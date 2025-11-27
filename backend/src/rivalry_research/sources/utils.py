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


def get_iso_timestamp() -> str:
    """
    Get current timestamp in ISO format.
    
    Returns:
        ISO 8601 timestamp string
    """
    return datetime.now(timezone.utc).isoformat()

