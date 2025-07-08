#!/usr/bin/env python3
"""
Standalone script to generate LangGraph workflow visualization.

Usage:
    python scripts/generate_graph.py [output_directory]
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.visualize_graph import generate_workflow_diagram, print_workflow_info


def main():
    """Main function to generate workflow diagram."""
    # Parse command line arguments
    output_dir = Path("output")
    if len(sys.argv) > 1:
        output_dir = Path(sys.argv[1])
    
    print("🔄 Generating LangGraph Recipe Processing Workflow Diagram...")
    print(f"📁 Output directory: {output_dir.absolute()}")
    print()
    
    try:
        # Generate the diagram
        results = generate_workflow_diagram(output_dir)
        
        print("\n✅ Successfully generated workflow diagram!")
        print("\n📄 Generated files:")
        for file_type, path in results.items():
            if isinstance(path, Path) and path.exists():
                size = path.stat().st_size
                print(f"   {file_type.replace('_', ' ').title()}: {path} ({size:,} bytes)")
        
        print("\n📊 Workflow Structure Information:")
        print_workflow_info()
        
        if "mermaid_code" in results:
            print(f"\n📝 Mermaid Code Preview (first 300 chars):")
            print("-" * 60)
            preview = results["mermaid_code"][:300]
            print(preview + "..." if len(results["mermaid_code"]) > 300 else preview)
            print("-" * 60)
        
        print(f"\n🎯 To view the diagram:")
        if "png_file" in results:
            print(f"   • Open PNG: {results['png_file']}")
        if "svg_file" in results:
            print(f"   • Open SVG: {results['svg_file']}")
        if "mermaid_file" in results:
            print(f"   • Copy Mermaid code from: {results['mermaid_file']}")
            print(f"   • Paste into Mermaid Live Editor: https://mermaid.live/")
        
        print(f"\n💡 To install mermaid-cli for PNG/SVG generation:")
        print(f"   npm install -g @mermaid-js/mermaid-cli")
        
    except Exception as e:
        print(f"❌ Error generating diagram: {e}")
        if "--debug" in sys.argv:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()