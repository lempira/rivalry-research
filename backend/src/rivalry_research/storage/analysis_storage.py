"""Storage and retrieval for rivalry analyses."""

import json
import logging
from datetime import datetime
from pathlib import Path

from ..models import RivalryAnalysis, Source
from .source_db import SourceDatabase

logger = logging.getLogger(__name__)


def save_analysis(
    analysis: RivalryAnalysis,
    analyses_dir: Path,
) -> Path:
    """
    Save a rivalry analysis to disk as JSON.
    
    Creates directory structure: analyses/{entity1_id}_{entity2_id}/analysis.json
    Datetime objects are serialized to ISO format strings.
    
    Args:
        analysis: RivalryAnalysis to save
        analyses_dir: Base directory for analyses storage
    
    Returns:
        Path to saved analysis file
    """
    analyses_dir = Path(analyses_dir)
    
    # Create analysis directory
    analysis_id = f"{analysis.entity1.id}_{analysis.entity2.id}"
    analysis_path = analyses_dir / analysis_id
    analysis_path.mkdir(parents=True, exist_ok=True)
    
    # Save as JSON
    output_file = analysis_path / "analysis.json"
    
    # Convert to dict and handle datetime serialization
    analysis_dict = analysis.model_dump(mode="json")
    
    # Write with formatting
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(analysis_dict, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved analysis to {output_file}")
    return output_file


def load_analysis(analysis_id: str, analyses_dir: Path) -> RivalryAnalysis:
    """
    Load a rivalry analysis from disk.
    
    Args:
        analysis_id: Analysis identifier (e.g., "Q935_Q9047")
        analyses_dir: Base directory for analyses storage
    
    Returns:
        RivalryAnalysis object
    
    Raises:
        FileNotFoundError: If analysis file doesn't exist
    """
    analyses_dir = Path(analyses_dir)
    analysis_file = analyses_dir / analysis_id / "analysis.json"
    
    if not analysis_file.exists():
        raise FileNotFoundError(f"Analysis not found: {analysis_file}")
    
    with open(analysis_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    logger.info(f"Loaded analysis from {analysis_file}")
    return RivalryAnalysis.model_validate(data)


def get_analysis_with_sources(
    analysis_id: str,
    analyses_dir: Path,
    db: SourceDatabase,
) -> RivalryAnalysis:
    """
    Load analysis and hydrate sources from SQLite database.
    
    This is useful if the analysis JSON only has source IDs
    and you need the full Source objects.
    
    Args:
        analysis_id: Analysis identifier (e.g., "Q935_Q9047")
        analyses_dir: Base directory for analyses storage
        db: SourceDatabase instance
    
    Returns:
        RivalryAnalysis with fully populated sources
    """
    analysis = load_analysis(analysis_id, analyses_dir)
    
    # If sources dict is empty or missing source details, hydrate from DB
    if analysis.sources:
        source_ids = list(analysis.sources.keys())
        hydrated_sources = db.get_sources_by_ids(source_ids)
        
        # Replace with hydrated sources
        analysis.sources = hydrated_sources
        logger.debug(f"Hydrated {len(hydrated_sources)} sources from database")
    
    return analysis


def list_analyses(analyses_dir: Path) -> list[dict]:
    """
    List all saved analyses.
    
    Args:
        analyses_dir: Base directory for analyses storage
    
    Returns:
        List of dicts with analysis metadata:
        - analysis_id: ID of the analysis
        - entity1_id: First entity ID
        - entity2_id: Second entity ID
        - path: Path to analysis file
        - analyzed_at: Timestamp of analysis
    """
    analyses_dir = Path(analyses_dir)
    
    if not analyses_dir.exists():
        return []
    
    analyses = []
    
    for analysis_dir in analyses_dir.iterdir():
        if not analysis_dir.is_dir():
            continue
        
        analysis_file = analysis_dir / "analysis.json"
        if not analysis_file.exists():
            continue
        
        # Parse analysis_id (e.g., "Q935_Q9047")
        analysis_id = analysis_dir.name
        parts = analysis_id.split("_")
        
        if len(parts) != 2:
            logger.warning(f"Unexpected analysis directory format: {analysis_id}")
            continue
        
        entity1_id, entity2_id = parts
        
        # Get timestamp from file
        try:
            with open(analysis_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                analyzed_at = data.get("analyzed_at")
        except Exception as e:
            logger.warning(f"Could not read analysis metadata for {analysis_id}: {e}")
            analyzed_at = None
        
        analyses.append({
            "analysis_id": analysis_id,
            "entity1_id": entity1_id,
            "entity2_id": entity2_id,
            "path": str(analysis_file),
            "analyzed_at": analyzed_at,
        })
    
    # Sort by analyzed_at (most recent first)
    analyses.sort(key=lambda x: x["analyzed_at"] or "", reverse=True)
    
    logger.info(f"Found {len(analyses)} saved analyses")
    return analyses

