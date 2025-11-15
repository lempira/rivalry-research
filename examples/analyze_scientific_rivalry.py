"""Example: Analyze the Newton-Leibniz calculus priority dispute."""

import json
import os
from pathlib import Path

from rivalry_research import search_person, analyze_rivalry


def main():
    """Analyze the famous rivalry between Newton and Leibniz over calculus."""
    
    if not os.getenv("GOOGLE_API_KEY"):
        print("⚠️  Set GOOGLE_API_KEY environment variable")
        return
    
    print("🔬 Rivalry Research - Newton vs Leibniz\n")
    
    # Search for Newton
    print("Searching for 'Isaac Newton'...")
    results1 = search_person("Isaac Newton")
    if not results1:
        print("No results found")
        return
    
    newton = results1[0]
    print(f"✓ {newton.label} ({newton.id})")
    print(f"  {newton.description}\n")
    
    # Search for Leibniz
    print("Searching for 'Gottfried Wilhelm Leibniz'...")
    results2 = search_person("Gottfried Wilhelm Leibniz")
    if not results2:
        print("No results found")
        return
    
    leibniz = results2[0]
    print(f"✓ {leibniz.label} ({leibniz.id})")
    print(f"  {leibniz.description}\n")
    
    # Analyze rivalry
    print("Analyzing rivalry...\n")
    
    try:
        analysis = analyze_rivalry(newton.id, leibniz.id)
        
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
        
        if analysis.relationships:
            print(f"\n🔗 Wikidata Relationships ({len(analysis.relationships)}):")
            for rel in analysis.relationships:
                target = rel.target_entity_label or rel.value
                print(f"  • {rel.property_label}: {target}")
        
        print("\n" + "=" * 70)
        
        # Save output to JSON file
        output_dir = Path(__file__).parent / "output"
        output_dir.mkdir(exist_ok=True)
        
        output_file = output_dir / f"{newton.id}_{leibniz.id}_rivalry_analysis.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(analysis.model_dump(), f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n💾 Analysis saved to: {output_file}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()

