"""Generic rivalry analysis - analyze any two people."""

import argparse
import json
import logging
import os
from pathlib import Path

from rivalry_research import search_person, analyze_rivalry

LOG_LEVEL = "DEBUG"

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
        print("⚠️  Set GOOGLE_API_KEY environment variable")
        return
    
    person1_name = args.person1
    person2_name = args.person2
    
    print(f"🔍 Rivalry Research - {person1_name} vs {person2_name}\n")
    
    # Search for first person
    print(f"Searching for '{person1_name}'...")
    results1 = search_person(person1_name)
    if not results1:
        print(f"❌ No results found for '{person1_name}'")
        return
    
    person1 = results1[0]
    print(f"✓ {person1.label} ({person1.id})")
    if person1.description:
        print(f"  {person1.description}")
    
    # Show disambiguation options if multiple results
    if len(results1) > 1:
        print(f"\n  Other matches found ({len(results1) - 1}):")
        for i, result in enumerate(results1[1:4], 2):
            print(f"    {i}. {result.label} - {result.description}")
    print()
    
    # Search for second person
    print(f"Searching for '{person2_name}'...")
    results2 = search_person(person2_name)
    if not results2:
        print(f"❌ No results found for '{person2_name}'")
        return
    
    person2 = results2[0]
    print(f"✓ {person2.label} ({person2.id})")
    if person2.description:
        print(f"  {person2.description}")
    
    # Show disambiguation options if multiple results
    if len(results2) > 1:
        print(f"\n  Other matches found ({len(results2) - 1}):")
        for i, result in enumerate(results2[1:4], 2):
            print(f"    {i}. {result.label} - {result.description}")
    print()
    
    # Analyze rivalry
    print("Analyzing rivalry...\n")
    
    try:
        analysis = analyze_rivalry(person1.id, person2.id)
        
        print("=" * 70)
        print("RIVALRY ANALYSIS")
        print("=" * 70)
        print(f"\n{analysis.entity1.label} vs {analysis.entity2.label}")
        print(f"Rivalry: {'YES' if analysis.rivalry_exists else 'NO'}")
        print(f"Score: {analysis.rivalry_score:.2f}/1.00")
        
        if analysis.rivalry_period_start or analysis.rivalry_period_end:
            period_start = analysis.rivalry_period_start or "?"
            period_end = analysis.rivalry_period_end or "ongoing"
            print(f"Period: {period_start} - {period_end}")
        
        print(f"\n📝 Summary:\n{analysis.summary}")
        
        # Show entity biographical info
        print(f"\n👤 {analysis.entity1.label}:")
        if analysis.entity1.birth_date:
            print(f"   Born: {analysis.entity1.birth_date}")
        if analysis.entity1.death_date:
            print(f"   Died: {analysis.entity1.death_date}")
        
        print(f"\n👤 {analysis.entity2.label}:")
        if analysis.entity2.birth_date:
            print(f"   Born: {analysis.entity2.birth_date}")
        if analysis.entity2.death_date:
            print(f"   Died: {analysis.entity2.death_date}")
        
        if analysis.timeline:
            print(f"\n📅 Rivalry Timeline ({len(analysis.timeline)} events):")
            for event in analysis.timeline:
                print(f"\n  {event.date} [{event.rivalry_relevance.upper()}]")
                print(f"    {event.description}")
                
                # Display direct quotes if present
                if event.direct_quotes:
                    for quote in event.direct_quotes:
                        print(f"    💬 {quote}")
                
                print(f"    Entity: {event.entity_id}")
        
        if analysis.relationships:
            print(f"\n🔗 Wikidata Relationships ({len(analysis.relationships)}):")
            for rel in analysis.relationships:
                target = rel.target_entity_label or rel.value
                print(f"  • {rel.property_label}: {target}")
        
        print("\n" + "=" * 70)
        
        # Save output to JSON file
        output_dir = Path(__file__).parent / "output"
        output_dir.mkdir(exist_ok=True)
        
        output_file = output_dir / f"{person1.id}_{person2.id}_rivalry_analysis.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(analysis.model_dump(), f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n💾 Analysis saved to: {output_file}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()

