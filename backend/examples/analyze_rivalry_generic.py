"""Generic rivalry analysis - analyze any two people."""

import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from rivalry_research import search_person, analyze_rivalry

LOG_LEVEL = "DEBUG"

logger = logging.getLogger(__name__)

def setup_logging(level: str):
    """
    Configure logging to show only rivalry_research logs.
    
    The root logger is set to WARNING to silence third-party libraries
    (httpx, httpcore, etc.), while rivalry_research is set to the requested level.
    
    Args:
        level: Logging level for rivalry_research (DEBUG, INFO, WARNING, ERROR)
    
    Note:
        To see ALL loggers including third-party libraries, change:
            level=logging.WARNING  # Current (shows only rivalry_research)
        to:
            level=getattr(logging, level.upper())  # Shows all loggers
    """
    # Set root logger to WARNING to silence third-party libraries
    logging.basicConfig(
        level=logging.WARNING,  # Only show warnings/errors from third-party libs
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    
    # Set rivalry_research to the requested level (includes all submodules)
    logging.getLogger('rivalry_research').setLevel(
        getattr(logging, level.upper())
    )


def add_file_logging(entity1_id: str, entity2_id: str, level: str) -> Path:
    """
    Add file handler to log to a file with entity IDs and timestamp.
    
    Args:
        entity1_id: First entity's Wikidata ID (e.g., 'Q935')
        entity2_id: Second entity's Wikidata ID (e.g., 'Q9047')
        level: Logging level for the file handler
    
    Returns:
        Path to the created log file
    """
    # Create logs directory
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    # Create filename with entities and ISO timestamp
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    log_file = log_dir / f"{entity1_id}_{entity2_id}_{timestamp}.log"
    
    # Create file handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(getattr(logging, level.upper()))
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    
    # Add file handler to root logger (captures everything)
    logging.getLogger().addHandler(file_handler)
    
    return log_file


def main():
    """Analyze rivalry between any two people provided as arguments."""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Analyze rivalry between two people using Wikidata and RAG",
        epilog="Examples:\n"
               '  python analyze_rivalry_generic.py "Isaac Newton" "Gottfried Leibniz"\n'
               '  python analyze_rivalry_generic.py "Steve Jobs" "Bill Gates" --log-level DEBUG\n'
               '  python analyze_rivalry_generic.py "Messi" "Ronaldo"',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("person1", help="First person's name")
    parser.add_argument("person2", help="Second person's name")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=LOG_LEVEL,
        help="Set logging level (default: INFO)"
    )
    
    args = parser.parse_args()
    
    # Setup logging BEFORE importing/using the library
    setup_logging(args.log_level)
    
    if not os.getenv("GOOGLE_API_KEY"):
        logger.error("⚠️  Set GOOGLE_API_KEY environment variable")
        return
    
    person1_name = args.person1
    person2_name = args.person2
    
    logger.info(f"🔍 Rivalry Research - {person1_name} vs {person2_name}\n")
    
    # Search for first person
    logger.info(f"Searching for '{person1_name}'...")
    results1 = search_person(person1_name)
    if not results1:
        logger.error(f"❌ No results found for '{person1_name}'")
        return
    
    person1 = results1[0]
    logger.info(f"✓ {person1.label} ({person1.id})")
    if person1.description:
        logger.info(f"  {person1.description}")
    
    # Show disambiguation options if multiple results
    if len(results1) > 1:
        logger.info(f"\n  Other matches found ({len(results1) - 1}):")
        for i, result in enumerate(results1[1:4], 2):
            logger.info(f"    {i}. {result.label} - {result.description}")
    logger.info("")
    
    # Search for second person
    logger.info(f"Searching for '{person2_name}'...")
    results2 = search_person(person2_name)
    if not results2:
        logger.error(f"❌ No results found for '{person2_name}'")
        return
    
    person2 = results2[0]
    logger.info(f"✓ {person2.label} ({person2.id})")
    if person2.description:
        logger.info(f"  {person2.description}")
    
    # Show disambiguation options if multiple results
    if len(results2) > 1:
        logger.info(f"\n  Other matches found ({len(results2) - 1}):")
        for i, result in enumerate(results2[1:4], 2):
            logger.info(f"    {i}. {result.label} - {result.description}")
    logger.info("")
    
    # Add file logging now that we have both entity IDs
    log_file = add_file_logging(person1.id, person2.id, args.log_level)
    logger.info(f"📝 Logging to: {log_file}\n")
    
    # Analyze rivalry
    logger.info("Analyzing rivalry...\n")
    
    try:
        analysis = analyze_rivalry(person1.id, person2.id)
        
        logger.info("=" * 70)
        logger.info("RIVALRY ANALYSIS")
        logger.info("=" * 70)
        logger.info(f"\n{analysis.entity1.label} vs {analysis.entity2.label}")
        logger.info(f"Rivalry: {'YES' if analysis.rivalry_exists else 'NO'}")
        logger.info(f"Score: {analysis.rivalry_score:.2f}/1.00")
        
        if analysis.rivalry_period_start or analysis.rivalry_period_end:
            period_start = analysis.rivalry_period_start or "?"
            period_end = analysis.rivalry_period_end or "ongoing"
            logger.info(f"Period: {period_start} - {period_end}")
        
        logger.info(f"\n📝 Summary:\n{analysis.summary}")
        
        # Show source information
        if analysis.sources:
            logger.info(f"\n📚 Sources ({len(analysis.sources)} total):")
            for source in analysis.sources[:5]:  # Show first 5
                logger.info(f"  • {source.title}")
                logger.info(f"    Type: {source.type}, Credibility: {source.credibility_score:.2f}")
            if len(analysis.sources) > 5:
                logger.info(f"  ... and {len(analysis.sources) - 5} more sources")
        
        # Show entity biographical info
        logger.info(f"\n👤 {analysis.entity1.label}:")
        if analysis.entity1.birth_date:
            logger.info(f"   Born: {analysis.entity1.birth_date}")
        if analysis.entity1.death_date:
            logger.info(f"   Died: {analysis.entity1.death_date}")
        
        logger.info(f"\n👤 {analysis.entity2.label}:")
        if analysis.entity2.birth_date:
            logger.info(f"   Born: {analysis.entity2.birth_date}")
        if analysis.entity2.death_date:
            logger.info(f"   Died: {analysis.entity2.death_date}")
        
        if analysis.timeline:
            logger.info(f"\n📅 Rivalry Timeline ({len(analysis.timeline)} events):")
            for event in analysis.timeline:
                logger.info(f"\n  {event.date} [{event.rivalry_relevance.upper()}]")
                logger.info(f"    {event.description}")
                
                # Display direct quotes if present
                if event.direct_quotes:
                    for quote in event.direct_quotes:
                        logger.info(f"    💬 {quote}")
                
                # Display source information
                if event.sources:
                    logger.info(f"    📖 Sources: {event.source_count} (Confidence: {event.confidence:.2f})")
                
                logger.info(f"    Entity: {event.entity_id}")
        
        if analysis.relationships:
            logger.info(f"\n🔗 Wikidata Relationships ({len(analysis.relationships)}):")
            for rel in analysis.relationships:
                target = rel.target_entity_label or rel.value
                logger.info(f"  • {rel.property_label}: {target}")
        
        logger.info("\n" + "=" * 70)
        
        # Analysis is automatically saved to data/analyses/ by the pipeline
        logger.info(f"\n💾 Analysis automatically saved to: data/analyses/{person1.id}_{person2.id}/analysis.json")
        
        # Also save a copy to examples/output for convenience
        output_dir = Path(__file__).parent / "output"
        output_dir.mkdir(exist_ok=True)
        
        output_file = output_dir / f"{person1.id}_{person2.id}_rivalry_analysis.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(analysis.model_dump(mode="json"), f, indent=2, ensure_ascii=False)
        
        logger.info(f"   Copy saved to: {output_file}")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()

