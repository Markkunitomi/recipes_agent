"""
Graph Visualization Utility for LangGraph Workflows
"""
from pathlib import Path
from typing import Optional
import sys

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.settings import Settings
from src.orchestrators.orchestrator_langgraph import LangGraphRecipeOrchestrator


def generate_mermaid_diagram(save_path: Optional[Path] = None) -> str:
    """
    Generate Mermaid diagram code for the LangGraph recipe processing workflow.
    
    Args:
        save_path: Optional path to save the Mermaid code to a file
        
    Returns:
        str: Mermaid diagram code
    """
    # Initialize settings and orchestrator
    settings = Settings.load()
    orchestrator = LangGraphRecipeOrchestrator(settings)
    
    # Get the compiled workflow graph
    workflow_graph = orchestrator.workflow.get_graph()
    
    # Generate Mermaid diagram code
    mermaid_code = workflow_graph.draw_mermaid()
    
    # Save to file if path provided
    if save_path:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(mermaid_code)
        print(f"Mermaid diagram saved to: {save_path}")
    
    return mermaid_code


def generate_workflow_diagram(output_dir: Optional[Path] = None) -> dict:
    """
    Generate complete workflow diagram in multiple formats.
    
    Args:
        output_dir: Directory to save outputs (defaults to ./output)
        
    Returns:
        dict: Paths to generated files
    """
    if output_dir is None:
        output_dir = Path("output")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate Mermaid code
    mermaid_path = output_dir / "workflow_diagram.mmd"
    mermaid_code = generate_mermaid_diagram(mermaid_path)
    
    results = {
        "mermaid_file": mermaid_path,
        "mermaid_code": mermaid_code
    }
    
    # Try to generate PNG using mermaid-cli if available
    try:
        import subprocess
        png_path = output_dir / "workflow_diagram.png"
        result = subprocess.run([
            "mmdc", "-i", str(mermaid_path), "-o", str(png_path)
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            results["png_file"] = png_path
            print(f"PNG diagram saved to: {png_path}")
        else:
            print("mermaid-cli not available or failed. Install with: npm install -g @mermaid-js/mermaid-cli")
            
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("mermaid-cli not found. Install with: npm install -g @mermaid-js/mermaid-cli")
    
    # Try to generate SVG
    try:
        svg_path = output_dir / "workflow_diagram.svg"
        result = subprocess.run([
            "mmdc", "-i", str(mermaid_path), "-o", str(svg_path)
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            results["svg_file"] = svg_path
            print(f"SVG diagram saved to: {svg_path}")
            
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    return results


def print_workflow_info():
    """Print information about the workflow structure."""
    settings = Settings.load()
    orchestrator = LangGraphRecipeOrchestrator(settings)
    
    print("Recipe Processing Workflow Structure")
    print("=" * 40)
    
    # Get graph structure
    graph = orchestrator.workflow.get_graph()
    
    print(f"Nodes: {len(graph.nodes)}")
    for node_id in graph.nodes:
        print(f"  - {node_id}")
    
    print(f"\nEdges: {len(graph.edges)}")
    for edge in graph.edges:
        print(f"  - {edge}")
    
    print("\nWorkflow Description:")
    print("This workflow processes recipes through the following stages:")
    print("1. Initialize - Set up processing state and debug")
    print("2. Scrape - Extract recipe from URL")
    print("3. Parse - Parse ingredients and instructions")
    print("4. Normalize - Enhance and normalize recipe data")
    print("5. Convert - Convert units between systems")
    print("6. LaTeX Format - Format for cookbook layout (conditional)")
    print("7. Render - Generate final output (JSON + derived formats)")
    print("8. Finalize - Complete processing and save debug info")
    print("\nEach step includes error handling that routes to finalization on failure.")


if __name__ == "__main__":
    print("Generating LangGraph workflow diagram...")
    
    # Generate all diagram formats
    results = generate_workflow_diagram()
    
    print("\nGenerated files:")
    for file_type, path in results.items():
        if isinstance(path, Path):
            print(f"  {file_type}: {path}")
    
    print("\nWorkflow Information:")
    print_workflow_info()
    
    print(f"\nMermaid Code Preview:")
    print("-" * 50)
    print(results["mermaid_code"][:500] + "..." if len(results["mermaid_code"]) > 500 else results["mermaid_code"])