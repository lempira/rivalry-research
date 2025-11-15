"""Generic rivalry analysis - analyze any two people."""

import json
import os
import sys
from pathlib import Path

from rivalry_research import search_person, analyze_rivalry


def main():
    """Analyze rivalry between any two people provided as arguments."""
    
    if not os.getenv("GOOGLE_API_KEY"):
        print("⚠️  Set GOOGLE_API_KEY environment variable")
        return
    
    # Get person names from command line arguments
    if len(sys.argv) < 3:
        print("Usage: python analyze_rivalry_generic.py <person1> <person2>")
        print("\nExample:")
        print('  python analyze_rivalry_generic.py "Isaac Newton" "Gottfried Leibniz"')
        print('  python analyze_rivalry_generic.py "Steve Jobs" "Bill Gates"')
        print('  python analyze_rivalry_generic.py "Messi" "Ronaldo"')
        sys.exit(1)
    
    person1_name = sys.argv[1]
    person2_name = sys.argv[2]
    
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
        print(f"\n{analysis.entity1_label} vs {analysis.entity2_label}")
        print(f"Rivalry: {'YES' if analysis.rivalry_exists else 'NO'}")
        print(f"Score: {analysis.rivalry_score:.2f}/1.00")
        
        print(f"\n📝 Summary:\n{analysis.summary}")
        
        if analysis.facts:
            print(f"\n🔍 Facts ({len(analysis.facts)}):")
            for i, fact in enumerate(analysis.facts, 1):
                print(f"\n{i}. {fact.fact}")
                if fact.date:
                    print(f"   Date: {fact.date}")
                if fact.category:
                    print(f"   Category: {fact.category}")
        
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

