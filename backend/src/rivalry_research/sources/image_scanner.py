"""Scan and manage images in entity directories."""

import logging
from pathlib import Path

from ..models import EntityImage
from .image_downloader import load_image_metadata, validate_image_file

logger = logging.getLogger(__name__)


def scan_entity_images(entity_dir: Path) -> list[dict]:
    """
    Scan the images directory within an entity folder.
    
    Args:
        entity_dir: Path to entity directory (e.g., data/raw_sources/Max_Planck_Q9021)
    
    Returns:
        List of image metadata dictionaries
    """
    images_dir = entity_dir / "images"
    
    if not images_dir.exists():
        logger.debug(f"No images directory found in {entity_dir}")
        return []
    
    image_list = []
    
    # Get all image source directories
    image_dirs = [d for d in images_dir.iterdir() if d.is_dir()]
    
    for image_dir in image_dirs:
        # Load metadata
        metadata = load_image_metadata(image_dir)
        
        if metadata:
            # Add directory info
            metadata["directory"] = str(image_dir)
            metadata["directory_name"] = image_dir.name
            
            # Determine source type from directory name
            if image_dir.name.startswith("manual_"):
                metadata["source"] = "manual"
            elif image_dir.name.startswith("commons_"):
                metadata["source"] = "commons"
            elif image_dir.name.startswith("wikipedia_"):
                metadata["source"] = "wikipedia"
            elif image_dir.name.startswith("loc_"):
                metadata["source"] = "loc"
            elif image_dir.name.startswith("europeana_"):
                metadata["source"] = "europeana"
            else:
                metadata["source"] = "unknown"
            
            image_list.append(metadata)
        else:
            logger.warning(f"No metadata found in {image_dir}")
    
    logger.debug(f"Found {len(image_list)} images in {entity_dir.name}")
    return image_list


def load_entity_images(entity_dir: Path, raw_sources_dir: Path) -> list[EntityImage]:
    """
    Load all images for an entity as EntityImage objects.
    
    Reads metadata from disk and constructs EntityImage objects.
    Useful for loading images without re-downloading.
    
    Args:
        entity_dir: Path to entity directory
        raw_sources_dir: Base raw sources directory (for relative paths)
    
    Returns:
        List of EntityImage objects with local_path populated
    """
    images_dir = entity_dir / "images"
    
    if not images_dir.exists():
        logger.debug(f"No images directory found in {entity_dir}")
        return []
    
    entity_images = []
    
    # Get all image source directories
    image_dirs = sorted([d for d in images_dir.iterdir() if d.is_dir()])
    
    for image_dir in image_dirs:
        try:
            # Load metadata
            metadata = load_image_metadata(image_dir)
            
            if not metadata:
                logger.warning(f"No metadata in {image_dir}, skipping")
                continue
            
            # Find the image file
            image_files = list(image_dir.glob("image.*"))
            if not image_files:
                logger.warning(f"No image file found in {image_dir}")
                continue
            
            image_file = image_files[0]
            
            # Construct EntityImage
            try:
                local_path_rel = image_file.relative_to(raw_sources_dir.parent)
            except ValueError:
                local_path_rel = image_file
            
            entity_image = EntityImage(
                url=metadata.get("original_url", f"file://{image_file.name}"),
                thumbnail_url=metadata.get("thumbnail_url"),
                source=metadata.get("source", "unknown"),
                title=metadata.get("title"),
                license=metadata.get("license", "unknown"),
                attribution=metadata.get("attribution"),
                local_path=str(local_path_rel)
            )
            
            entity_images.append(entity_image)
            logger.debug(f"Loaded image from {image_dir.name}")
            
        except Exception as e:
            logger.warning(f"Failed to load image from {image_dir}: {e}")
            continue
    
    logger.info(f"Loaded {len(entity_images)} images from {entity_dir.name}")
    return entity_images


def validate_image_directory(image_dir: Path) -> tuple[bool, str]:
    """
    Validate an image directory has proper structure.
    
    Checks for:
    - Directory exists
    - Image file exists (image.*)
    - Metadata.json exists and is valid
    - Image file is valid
    
    Args:
        image_dir: Path to image directory
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not image_dir.exists():
        return False, "Directory does not exist"
    
    if not image_dir.is_dir():
        return False, "Path is not a directory"
    
    # Check for image file
    image_files = list(image_dir.glob("image.*"))
    if not image_files:
        return False, "No image file found (expected image.jpg, image.png, etc.)"
    
    image_file = image_files[0]
    
    # Validate image file
    is_valid, error_msg = validate_image_file(image_file)
    if not is_valid:
        return False, f"Invalid image file: {error_msg}"
    
    # Check for metadata
    metadata_file = image_dir / "metadata.json"
    if not metadata_file.exists():
        return False, "No metadata.json found"
    
    # Try to load metadata
    metadata = load_image_metadata(image_dir)
    if not metadata:
        return False, "Failed to load metadata.json"
    
    # Check for required metadata fields
    required_fields = ["source", "license"]
    missing_fields = [f for f in required_fields if f not in metadata]
    
    if missing_fields:
        return False, f"Missing required metadata fields: {', '.join(missing_fields)}"
    
    return True, "Valid"


def get_image_statistics(entity_dir: Path) -> dict:
    """
    Get statistics about images in an entity directory.
    
    Args:
        entity_dir: Path to entity directory
    
    Returns:
        Dictionary with image statistics
    """
    images = scan_entity_images(entity_dir)
    
    # Count by source
    by_source = {}
    has_thumbnail = 0
    manual_count = 0
    
    for img in images:
        source = img.get("source", "unknown")
        by_source[source] = by_source.get(source, 0) + 1
        
        # Check for thumbnail
        image_dir = Path(img["directory"])
        if (image_dir / "thumbnail.jpg").exists():
            has_thumbnail += 1
        
        if source == "manual":
            manual_count += 1
    
    return {
        "total": len(images),
        "by_source": by_source,
        "with_thumbnails": has_thumbnail,
        "manual": manual_count,
        "auto": len(images) - manual_count,
    }


def detect_manual_images(entity_dir: Path) -> list[dict]:
    """
    Specifically detect manually added images.
    
    Args:
        entity_dir: Path to entity directory
    
    Returns:
        List of manual image metadata dictionaries
    """
    all_images = scan_entity_images(entity_dir)
    manual_images = [img for img in all_images if img.get("source") == "manual"]
    
    logger.debug(f"Found {len(manual_images)} manual images in {entity_dir.name}")
    return manual_images


def list_entities_with_images(raw_sources_dir: Path) -> list[dict]:
    """
    List all entities that have images.
    
    Args:
        raw_sources_dir: Base raw sources directory
    
    Returns:
        List of entity info with image counts
    """
    raw_sources_dir = Path(raw_sources_dir)
    
    if not raw_sources_dir.exists():
        return []
    
    entities = []
    
    # Get all entity directories
    entity_dirs = [d for d in raw_sources_dir.iterdir() if d.is_dir()]
    
    for entity_dir in entity_dirs:
        images_dir = entity_dir / "images"
        
        if not images_dir.exists():
            continue
        
        stats = get_image_statistics(entity_dir)
        
        if stats["total"] > 0:
            entities.append({
                "entity_dir": str(entity_dir),
                "entity_name": entity_dir.name,
                "image_count": stats["total"],
                "manual_count": stats["manual"],
                "auto_count": stats["auto"],
            })
    
    return entities


def validate_all_images(entity_dir: Path) -> dict:
    """
    Validate all images in an entity directory.
    
    Args:
        entity_dir: Path to entity directory
    
    Returns:
        Dictionary with validation results
    """
    images_dir = entity_dir / "images"
    
    if not images_dir.exists():
        return {
            "total": 0,
            "valid": 0,
            "invalid": 0,
            "errors": []
        }
    
    image_dirs = [d for d in images_dir.iterdir() if d.is_dir()]
    
    valid_count = 0
    invalid_count = 0
    errors = []
    
    for image_dir in image_dirs:
        is_valid, error_msg = validate_image_directory(image_dir)
        
        if is_valid:
            valid_count += 1
        else:
            invalid_count += 1
            errors.append({
                "directory": image_dir.name,
                "error": error_msg
            })
    
    return {
        "total": len(image_dirs),
        "valid": valid_count,
        "invalid": invalid_count,
        "errors": errors
    }

