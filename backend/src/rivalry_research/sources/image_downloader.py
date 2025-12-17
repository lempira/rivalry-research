"""Download and store images locally with metadata."""

import json
import logging
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

logger = logging.getLogger(__name__)

# Download settings
DOWNLOAD_TIMEOUT = 30.0
MAX_IMAGE_SIZE_MB = 25
USER_AGENT = "RivalryResearch/0.1.0 (https://github.com/user/rivalry-research)"

# Thumbnail settings
THUMBNAIL_SIZE = (300, 300)


def download_and_store_image(
    image_url: str,
    entity_dir: Path,
    source_type: str,
    metadata: dict[str, Any],
    generate_thumbnail: bool = True,
) -> tuple[Path, Path | None, dict[str, Any]]:
    """
    Download an image and store it locally with metadata.
    
    If download fails, still saves metadata with error info so we know what was attempted.
    If both download and metadata save fail, no directory is created.
    
    Args:
        image_url: URL of the image to download
        entity_dir: Entity directory (e.g., data/raw_sources/Max_Planck_Q9021)
        source_type: Type of source (e.g., "commons", "wikipedia", "manual")
        metadata: Metadata dictionary to save alongside image
        generate_thumbnail: Whether to generate a thumbnail
    
    Returns:
        Tuple of (image_path, thumbnail_path, updated_metadata)
    
    Raises:
        Exception: If download or save fails
    """
    logger.info(f"Downloading image from {image_url}")
    
    # Prepare directory paths (don't create yet)
    images_dir = entity_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    
    # Find next available directory number for this source type
    source_dir = _get_next_image_directory(images_dir, source_type)
    
    # Try to download image first (before creating directory)
    download_error = None
    image_bytes = None
    try:
        image_bytes = _download_image(image_url)
    except Exception as e:
        download_error = str(e)
        logger.warning(f"Download failed: {e}")
    
    # Create directory only if we have something to save
    source_dir.mkdir(parents=True, exist_ok=True)
    
    # If download succeeded, save image and thumbnail
    image_path = None
    thumbnail_path = None
    if image_bytes is not None:
        # Determine format and save
        image_format = _detect_image_format(image_bytes)
        image_filename = f"image.{image_format}"
        image_path = source_dir / image_filename
        
        image_path.write_bytes(image_bytes)
        logger.debug(f"Saved image to {image_path}")
        
        # Generate thumbnail if requested
        if generate_thumbnail:
            try:
                thumbnail_path = _generate_thumbnail(image_path, source_dir)
                logger.debug(f"Generated thumbnail at {thumbnail_path}")
            except Exception as e:
                logger.warning(f"Failed to generate thumbnail: {e}")
        
        # Update metadata with file info
        metadata.update({
            "file_size_bytes": len(image_bytes),
            "image_format": image_format,
            "local_filename": image_filename,
        })
    else:
        # Download failed - save error info in metadata
        metadata.update({
            "download_failed": True,
            "error": download_error,
            "attempted_url": image_url,
        })
    
    # Save metadata (even if download failed)
    try:
        metadata_path = source_dir / "metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        logger.debug(f"Saved metadata to {metadata_path}")
    except Exception as e:
        # If metadata save also fails, remove the directory and re-raise
        logger.error(f"Failed to save metadata: {e}")
        try:
            if source_dir.exists():
                import shutil
                shutil.rmtree(source_dir)
                logger.debug(f"Removed directory {source_dir} after metadata save failed")
        except Exception as cleanup_error:
            logger.warning(f"Failed to cleanup directory: {cleanup_error}")
        raise Exception(f"Failed to save metadata: {e}")
    
    # If download failed, re-raise the original exception
    if download_error:
        raise Exception(f"Failed to download image: {download_error}")
    
    return image_path, thumbnail_path, metadata


def _download_image(url: str) -> bytes:
    """
    Download image from URL.
    
    Args:
        url: Image URL
    
    Returns:
        Image bytes
    
    Raises:
        Exception: If download fails or image too large
    """
    headers = {"User-Agent": USER_AGENT}
    
    try:
        with httpx.Client(follow_redirects=True, timeout=DOWNLOAD_TIMEOUT) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            
            # Check size
            content_length = len(response.content)
            max_bytes = MAX_IMAGE_SIZE_MB * 1024 * 1024
            
            if content_length > max_bytes:
                raise Exception(
                    f"Image too large: {content_length / 1024 / 1024:.1f}MB "
                    f"(max: {MAX_IMAGE_SIZE_MB}MB)"
                )
            
            logger.debug(f"Downloaded {content_length} bytes")
            return response.content
            
    except httpx.TimeoutException:
        raise Exception(f"Timeout downloading image from {url}")
    except httpx.HTTPStatusError as e:
        raise Exception(f"HTTP error {e.response.status_code} downloading {url}")
    except Exception as e:
        raise Exception(f"Failed to download image: {e}")


def _detect_image_format(image_bytes: bytes) -> str:
    """
    Detect image format from bytes.
    
    Args:
        image_bytes: Image file bytes
    
    Returns:
        Format string (e.g., "jpg", "png", "webp")
    """
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            format_lower = img.format.lower() if img.format else "jpg"
            # Normalize format names
            if format_lower == "jpeg":
                return "jpg"
            return format_lower
    except Exception as e:
        logger.warning(f"Failed to detect image format: {e}, defaulting to jpg")
        return "jpg"


def _generate_thumbnail(image_path: Path, output_dir: Path) -> Path:
    """
    Generate a thumbnail for an image.
    
    Args:
        image_path: Path to original image
        output_dir: Directory to save thumbnail
    
    Returns:
        Path to generated thumbnail
    
    Raises:
        Exception: If thumbnail generation fails
    """
    thumbnail_path = output_dir / "thumbnail.jpg"
    
    try:
        with Image.open(image_path) as img:
            # Convert to RGB if necessary (for transparency)
            if img.mode in ("RGBA", "LA", "P"):
                # Create white background
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                img = background
            
            # Generate thumbnail
            img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            img.save(thumbnail_path, "JPEG", quality=85, optimize=True)
            
        return thumbnail_path
        
    except Exception as e:
        raise Exception(f"Failed to generate thumbnail: {e}")


def _get_next_image_directory(images_dir: Path, source_type: str) -> Path:
    """
    Get the next available directory for a source type.
    
    Args:
        images_dir: Images directory
        source_type: Source type (e.g., "commons", "manual")
    
    Returns:
        Path to next available directory
    """
    # Find existing directories for this source type
    existing_dirs = [
        d for d in images_dir.iterdir()
        if d.is_dir() and d.name.startswith(f"{source_type}_")
    ]
    
    # Find next number
    if not existing_dirs:
        next_num = 1
    else:
        # Extract numbers from directory names
        numbers = []
        for d in existing_dirs:
            try:
                num_str = d.name.split("_")[-1]
                numbers.append(int(num_str))
            except ValueError:
                continue
        next_num = max(numbers) + 1 if numbers else 1
    
    return images_dir / f"{source_type}_{next_num:03d}"


def load_image_metadata(image_dir: Path) -> dict[str, Any] | None:
    """
    Load metadata from an image directory.
    
    Args:
        image_dir: Path to image directory
    
    Returns:
        Metadata dictionary or None if not found
    """
    metadata_path = image_dir / "metadata.json"
    
    if not metadata_path.exists():
        return None
    
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load metadata from {metadata_path}: {e}")
        return None


def validate_image_file(image_path: Path) -> tuple[bool, str]:
    """
    Validate that an image file is readable and valid.
    
    Args:
        image_path: Path to image file
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not image_path.exists():
        return False, "Image file does not exist"
    
    if not image_path.is_file():
        return False, "Path is not a file"
    
    # Check file size
    file_size = image_path.stat().st_size
    if file_size == 0:
        return False, "Image file is empty"
    
    max_bytes = MAX_IMAGE_SIZE_MB * 1024 * 1024
    if file_size > max_bytes:
        return False, f"Image too large: {file_size / 1024 / 1024:.1f}MB (max: {MAX_IMAGE_SIZE_MB}MB)"
    
    # Try to open with PIL
    try:
        with Image.open(image_path) as img:
            img.verify()  # Verify it's a valid image
        return True, "Valid"
    except Exception as e:
        return False, f"Invalid image file: {e}"

