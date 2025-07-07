#!/usr/bin/env python3
"""
Recipe Agent System - Main Entry Point
"""
import typer
from rich.console import Console
from typing import Optional
from pathlib import Path

from orchestrators.orchestrator import RecipeOrchestrator
try:
    from orchestrators.orchestrator_langgraph import LangGraphRecipeOrchestrator
    LANGGRAPH_AVAILABLE = True
except Exception:
    LANGGRAPH_AVAILABLE = False
from config.settings import Settings

app = typer.Typer(
    name="recipes-agent",
    help="Multi-agent recipe management system",
    add_completion=False,
)
console = Console()

@app.command()
def process(
    url: str = typer.Argument(..., help="Recipe URL to process"),
    output_format: str = typer.Option("json", help="Output format: json, html, interactive, latex, strangetom, cookbook"),
    output_dir: Optional[Path] = typer.Option(None, help="Output directory"),
    config_file: Optional[Path] = typer.Option(None, help="Configuration file"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug output files"),
    debug_dir: str = typer.Option("./debug", "--debug-dir", help="Debug output directory"),
    use_langgraph: bool = typer.Option(False, "--langgraph", help="Use LangGraph orchestrator"),
):
    """Process a recipe URL through the multi-agent pipeline."""
    
    # Load configuration
    settings = Settings.load(config_file)
    
    if verbose:
        console.print(f"[bold blue]Processing recipe:[/bold blue] {url}")
        console.print(f"[bold blue]Output format:[/bold blue] {output_format}")
        console.print(f"[bold blue]Orchestrator:[/bold blue] {'LangGraph' if use_langgraph else 'Original'}")
        if debug:
            console.print(f"[bold blue]Debug output:[/bold blue] {debug_dir}")
    
    # Initialize orchestrator
    if use_langgraph:
        if LANGGRAPH_AVAILABLE:
            orchestrator = LangGraphRecipeOrchestrator(settings)
        else:
            console.print(f"[bold red]LangGraph orchestrator not available - using original orchestrator[/bold red]")
            orchestrator = RecipeOrchestrator(settings)
    else:
        orchestrator = RecipeOrchestrator(settings)
    
    try:
        # Process recipe
        result = orchestrator.process_recipe(url, output_format, output_dir, debug, debug_dir)
        
        if result.success:
            console.print(f"[bold green]✓ Recipe processed successfully![/bold green]")
            console.print(f"[bold green]Output saved to:[/bold green] {result.output_path}")
            if debug and hasattr(result, 'debug_dir'):
                console.print(f"[bold cyan]Debug files saved to:[/bold cyan] {result.debug_dir}")
        else:
            console.print(f"[bold red]✗ Processing failed:[/bold red] {result.error}")
            return 1
            
    except Exception as e:
        console.print(f"[bold red]✗ Unexpected error:[/bold red] {str(e)}")
        if verbose:
            console.print_exception()
        return 1

@app.command()
def convert(
    json_file: Path = typer.Argument(..., help="JSON file to convert"),
    output_format: str = typer.Argument(..., help="Output format: html, interactive, latex, strangetom, cookbook"),
    output_dir: Optional[Path] = typer.Option(None, help="Output directory"),
    config_file: Optional[Path] = typer.Option(None, help="Configuration file"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
):
    """Convert existing JSON recipe file to another format."""
    
    # Load configuration
    settings = Settings.load(config_file)
    
    if verbose:
        console.print(f"[bold blue]Converting JSON file:[/bold blue] {json_file}")
        console.print(f"[bold blue]Output format:[/bold blue] {output_format}")
    
    # Check if JSON file exists
    if not json_file.exists():
        console.print(f"[bold red]✗ JSON file not found:[/bold red] {json_file}")
        return 1
    
    try:
        # Initialize renderer
        from agents.renderer import RendererAgent
        renderer = RendererAgent(settings)
        
        # Convert JSON to requested format
        result = renderer.render_from_json(json_file, output_format, output_dir)
        
        if result.success:
            console.print(f"[bold green]✓ Conversion successful![/bold green]")
            console.print(f"[bold green]Output saved to:[/bold green] {result.data.output_path}")
        else:
            console.print(f"[bold red]✗ Conversion failed:[/bold red] {result.error}")
            return 1
            
    except Exception as e:
        console.print(f"[bold red]✗ Unexpected error:[/bold red] {str(e)}")
        if verbose:
            console.print_exception()
        return 1


if __name__ == "__main__":
    app()