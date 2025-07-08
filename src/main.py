#!/usr/bin/env python3
"""
Recipe Agent System - Main Entry Point
"""
import typer
from rich.console import Console
from typing import Optional
from pathlib import Path

from .orchestrators.orchestrator_langgraph import LangGraphRecipeOrchestrator
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from config.settings import Settings

app = typer.Typer(
    name="recipes-agent",
    help="Multi-agent recipe management system",
    add_completion=False,
)
console = Console()

@app.command()
def process(
    url: Optional[str] = typer.Argument(None, help="Recipe URL to process"),
    file: Optional[Path] = typer.Option(None, "--file", help="Text file with URLs (one per line)"),
    output_format: str = typer.Option("json", help="Output format: json, html, latex"),
    output_dir: Optional[Path] = typer.Option(None, help="Output directory"),
    config_file: Optional[Path] = typer.Option(None, help="Configuration file"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug output files"),
    debug_dir: str = typer.Option("./debug", "--debug-dir", help="Debug output directory"),
):
    """Process a recipe URL or batch of URLs through the multi-agent pipeline."""
    
    # Validate input - must provide either URL or file, but not both
    if not url and not file:
        console.print(f"[bold red]✗ Must provide either a URL or --file option[/bold red]")
        console.print(f"[yellow]Examples:[/yellow]")
        console.print(f"  python -m src.main process https://example.com/recipe")
        console.print(f"  python -m src.main process --file data/recipe_urls.txt")
        return 1
    
    if url and file:
        console.print(f"[bold red]✗ Cannot provide both URL and --file option[/bold red]")
        console.print(f"[yellow]Use either:[/yellow] URL argument OR --file option")
        return 1
    
    # Validate output format
    valid_formats = ["json", "html", "latex"]
    if output_format not in valid_formats:
        console.print(f"[bold red]✗ Invalid output format:[/bold red] {output_format}")
        console.print(f"[yellow]Valid formats:[/yellow] {', '.join(valid_formats)}")
        return 1
    
    # Load configuration
    settings = Settings.load(config_file)
    
    # Determine processing mode
    if file:
        # Batch processing from file
        if not file.exists():
            console.print(f"[bold red]✗ File not found:[/bold red] {file}")
            return 1
        return _process_batch(file, output_format, output_dir, settings, verbose, debug, debug_dir)
    else:
        # Single URL processing
        return _process_single(url, output_format, output_dir, settings, verbose, debug, debug_dir)

def _process_single(url: str, output_format: str, output_dir: Optional[Path], settings: Settings, verbose: bool, debug: bool, debug_dir: str) -> int:
    """Process a single recipe URL."""
    if verbose:
        console.print(f"[bold blue]Processing recipe:[/bold blue] {url}")
        console.print(f"[bold blue]Output format:[/bold blue] {output_format}")
        console.print(f"[bold blue]Orchestrator:[/bold blue] LangGraph")
        if debug:
            console.print(f"[bold blue]Debug output:[/bold blue] {debug_dir}")
    
    # Initialize LangGraph orchestrator
    orchestrator = LangGraphRecipeOrchestrator(settings)
    
    try:
        # Process recipe
        result = orchestrator.process_recipe(url, output_format, output_dir, debug, debug_dir)
        
        if result.success:
            console.print(f"[bold green]✓ Recipe processed successfully![/bold green]")
            console.print(f"[bold green]Output saved to:[/bold green] {result.output_path}")
            if debug and hasattr(result, 'debug_dir'):
                console.print(f"[bold cyan]Debug files saved to:[/bold cyan] {result.debug_dir}")
            return 0
        else:
            console.print(f"[bold red]✗ Processing failed:[/bold red] {result.error}")
            return 1
            
    except Exception as e:
        console.print(f"[bold red]✗ Unexpected error:[/bold red] {str(e)}")
        if verbose:
            console.print_exception()
        return 1

def _process_batch(file_path: Path, output_format: str, output_dir: Optional[Path], settings: Settings, verbose: bool, debug: bool, debug_dir: str) -> int:
    """Process multiple recipe URLs from a text file."""
    try:
        # Read URLs from file
        with open(file_path, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
        
        if not urls:
            console.print(f"[bold red]✗ No URLs found in file:[/bold red] {file_path}")
            return 1
        
        console.print(f"[bold blue]Batch processing {len(urls)} URLs from:[/bold blue] {file_path}")
        console.print(f"[bold blue]Output format:[/bold blue] {output_format}")
        
        # Initialize orchestrator
        orchestrator = LangGraphRecipeOrchestrator(settings)
        
        # Track results
        successful = 0
        failed = 0
        failed_urls = []
        
        # Process each URL
        for i, url in enumerate(urls, 1):
            if verbose:
                console.print(f"\n[bold cyan]Processing {i}/{len(urls)}:[/bold cyan] {url}")
            else:
                console.print(f"[cyan]{i}/{len(urls)}[/cyan] {url[:60]}{'...' if len(url) > 60 else ''}")
            
            try:
                result = orchestrator.process_recipe(url, output_format, output_dir, debug, debug_dir)
                
                if result.success:
                    successful += 1
                    if verbose:
                        console.print(f"[green]✓ Success:[/green] {result.output_path}")
                else:
                    failed += 1
                    failed_urls.append((url, result.error))
                    console.print(f"[red]✗ Failed:[/red] {result.error}")
                    
            except Exception as e:
                failed += 1
                failed_urls.append((url, str(e)))
                console.print(f"[red]✗ Error:[/red] {str(e)}")
        
        # Summary
        console.print(f"\n[bold]Batch processing complete![/bold]")
        console.print(f"[green]Successful:[/green] {successful}")
        console.print(f"[red]Failed:[/red] {failed}")
        
        if failed_urls and verbose:
            console.print(f"\n[bold red]Failed URLs:[/bold red]")
            for url, error in failed_urls:
                console.print(f"  • {url}: {error}")
        
        return 0 if failed == 0 else 1
        
    except Exception as e:
        console.print(f"[bold red]✗ Error reading file:[/bold red] {str(e)}")
        return 1

@app.command()
def convert(
    json: Path = typer.Argument(..., help="JSON file or directory to convert"),
    output: Path = typer.Argument(..., help="Output file path (.html/.tex) or directory"),
    config_file: Optional[Path] = typer.Option(None, help="Configuration file"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
    html: bool = typer.Option(False, "--html", help="Force HTML output format"),
    latex: bool = typer.Option(False, "--latex", help="Force LaTeX output format"),
):
    """Convert existing JSON recipe file(s) to another format.
    
    Examples:
      Single file:     convert recipe.json recipe.html
      Batch HTML:      convert input_dir/ output_dir/ --html
      Batch LaTeX:     convert input_dir/ output_dir/ --latex
      Auto-detect:     convert input_dir/ output_dir/  (detects from existing files)
    """
    
    # Validate format flags
    if html and latex:
        console.print(f"[bold red]✗ Cannot specify both --html and --latex flags[/bold red]")
        return 1
    
    # Load configuration
    settings = Settings.load(config_file)
    
    # Check if input is directory for batch conversion
    if json.is_dir():
        # Determine format from flags or auto-detect
        format_override = None
        if html:
            format_override = 'html'
        elif latex:
            format_override = 'latex'
        return _convert_batch(json, output, settings, verbose, format_override)
    else:
        # Single file conversion - flags only apply to directory conversion
        if html or latex:
            console.print(f"[bold yellow]Warning: Format flags ignored for single file conversion[/bold yellow]")
            console.print(f"[yellow]Format determined by output file extension (.html or .tex)[/yellow]")
        return _convert_single(json, output, settings, verbose)

def _convert_single(json_file: Path, output_file: Path, settings: Settings, verbose: bool) -> int:
    """Convert a single JSON file to another format."""
    
    # Determine format from output file extension
    output_ext = output_file.suffix.lower()
    if output_ext == '.html':
        output_format = 'html'
    elif output_ext == '.tex':
        output_format = 'latex'
    else:
        console.print(f"[bold red]✗ Unsupported output file extension:[/bold red] {output_ext}")
        console.print(f"[yellow]Supported extensions:[/yellow] .html, .tex")
        return 1
    
    if verbose:
        console.print(f"[bold blue]Converting JSON file:[/bold blue] {json_file}")
        console.print(f"[bold blue]Output file:[/bold blue] {output_file}")
        console.print(f"[bold blue]Format:[/bold blue] {output_format}")
    
    # Check if JSON file exists
    if not json_file.exists():
        console.print(f"[bold red]✗ JSON file not found:[/bold red] {json_file}")
        return 1
    
    try:
        # Initialize renderer
        from .agents.renderer import RendererAgent
        renderer = RendererAgent(settings)
        
        # Map format names to internal renderer formats
        format_mapping = {
            "latex": "cookbook",  # latex output uses cookbook format
            "html": "strangetom"  # html output uses strangetom format
        }
        renderer_format = format_mapping.get(output_format.lower(), output_format)
        
        # Create output directory if it doesn't exist
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert JSON to requested format using output directory
        result = renderer.render_from_json(json_file, renderer_format, output_file.parent)
        
        # Move the generated file to the specific output path if needed
        if result.success and result.data.output_path != output_file:
            import shutil
            shutil.move(str(result.data.output_path), str(output_file))
            # Update the result path
            result.data.output_path = output_file
        
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

def _convert_batch(input_dir: Path, output_dir: Path, settings: Settings, verbose: bool, format_override: Optional[str] = None) -> int:
    """Convert all JSON files in a directory to another format."""
    
    if not input_dir.exists():
        console.print(f"[bold red]✗ Input directory not found:[/bold red] {input_dir}")
        return 1
    
    # Find all JSON files in input directory
    json_files = list(input_dir.glob("*.json"))
    if not json_files:
        console.print(f"[bold red]✗ No JSON files found in:[/bold red] {input_dir}")
        return 1
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine output format: explicit flag > auto-detect > default
    if format_override:
        detected_format = format_override
        console.print(f"[bold blue]Using specified format: {format_override}[/bold blue]")
    else:
        # Auto-detect format from existing files in output directory
        detected_format = None
        html_files = list(output_dir.glob("*.html"))
        tex_files = list(output_dir.glob("*.tex"))
        
        if html_files and not tex_files:
            detected_format = 'html'
            console.print(f"[bold blue]Detected HTML format from existing files[/bold blue]")
        elif tex_files and not html_files:
            detected_format = 'latex'
            console.print(f"[bold blue]Detected LaTeX format from existing files[/bold blue]")
        elif tex_files and html_files:
            # If both exist, prefer LaTeX for batch cookbook generation
            detected_format = 'latex'
            console.print(f"[bold blue]Found both formats, defaulting to LaTeX for cookbook generation[/bold blue]")
        else:
            # No existing files - default to HTML with helpful message
            console.print(f"[bold yellow]No existing files found in output directory.[/bold yellow]")
            console.print(f"[yellow]Tip: Use --html or --latex flags to specify format, or create sample files[/yellow]")
            detected_format = 'html'
            console.print(f"[bold blue]Defaulting to HTML format for batch conversion[/bold blue]")
    
    format_mapping = {
        "latex": "cookbook",
        "html": "strangetom"
    }
    renderer_format = format_mapping.get(detected_format, detected_format)
    file_extension = '.html' if detected_format == 'html' else '.tex'
    
    console.print(f"[bold blue]Batch converting {len(json_files)} JSON files[/bold blue]")
    console.print(f"[bold blue]Input directory:[/bold blue] {input_dir}")
    console.print(f"[bold blue]Output directory:[/bold blue] {output_dir}")
    console.print(f"[bold blue]Output format:[/bold blue] {detected_format}")
    
    # Initialize renderer
    try:
        from .agents.renderer import RendererAgent
        renderer = RendererAgent(settings)
    except Exception as e:
        console.print(f"[bold red]✗ Failed to initialize renderer:[/bold red] {str(e)}")
        return 1
    
    # Track results
    successful = 0
    failed = 0
    failed_files = []
    
    # Convert each JSON file
    for i, json_file in enumerate(json_files, 1):
        # Generate output filename
        output_filename = json_file.stem + file_extension
        output_file = output_dir / output_filename
        
        if verbose:
            console.print(f"\n[bold cyan]Converting {i}/{len(json_files)}:[/bold cyan] {json_file.name}")
        else:
            console.print(f"[cyan]{i}/{len(json_files)}[/cyan] {json_file.name}")
        
        try:
            # Create a temporary working directory for the renderer
            import tempfile
            import shutil
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Convert JSON to requested format using temp directory
                result = renderer.render_from_json(json_file, renderer_format, temp_path)
                
                # Move the generated file to the correct location in the batch output directory
                if result.success:
                    generated_path = result.data.output_path
                    # Move from temp directory to final output location
                    if output_file.exists():
                        output_file.unlink()  # Remove existing file
                    shutil.move(str(generated_path), str(output_file))
                    result.data.output_path = output_file
            
            if result.success:
                successful += 1
                if verbose:
                    console.print(f"[green]✓ Success:[/green] {output_file}")
            else:
                failed += 1
                failed_files.append((json_file.name, result.error))
                console.print(f"[red]✗ Failed:[/red] {result.error}")
                
        except Exception as e:
            failed += 1
            failed_files.append((json_file.name, str(e)))
            console.print(f"[red]✗ Error:[/red] {str(e)}")
    
    # Summary
    console.print(f"\n[bold]Batch conversion complete![/bold]")
    console.print(f"[green]Successful:[/green] {successful}")
    console.print(f"[red]Failed:[/red] {failed}")
    
    if failed_files and verbose:
        console.print(f"\n[bold red]Failed files:[/bold red]")
        for filename, error in failed_files:
            console.print(f"  • {filename}: {error}")
    
    return 0 if failed == 0 else 1

@app.command()
def compile(
    cookbook_dir: Optional[Path] = typer.Argument(None, help="Cookbook directory to compile (defaults to output/cookbook)"),
    output_name: str = typer.Option("cookbook", help="Output PDF name"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
    clean: bool = typer.Option(False, "--clean", help="Clean auxiliary files after compilation"),
):
    """Compile cookbook LaTeX files to PDF using XeLaTeX."""
    
    # Default to output/cookbook if not specified
    if cookbook_dir is None:
        cookbook_dir = Path("output/cookbook")
    
    if not cookbook_dir.exists():
        console.print(f"[bold red]✗ Cookbook directory not found:[/bold red] {cookbook_dir}")
        return 1
    
    main_tex = cookbook_dir / "main.tex"
    if not main_tex.exists():
        console.print(f"[bold red]✗ main.tex not found in:[/bold red] {cookbook_dir}")
        console.print("[yellow]Hint:[/yellow] Generate recipes with 'cookbook' format first")
        return 1
    
    if verbose:
        console.print(f"[bold blue]Compiling cookbook:[/bold blue] {cookbook_dir}")
        console.print(f"[bold blue]Output PDF:[/bold blue] {output_name}.pdf")
    
    try:
        import subprocess
        import shutil
        
        # Check if XeLaTeX is available
        if not shutil.which("xelatex"):
            console.print("[bold red]✗ XeLaTeX not found![/bold red]")
            console.print("Please install XeLaTeX (part of TeX Live or MiKTeX)")
            return 1
        
        # Change to cookbook directory for compilation
        original_cwd = Path.cwd()
        try:
            import os
            os.chdir(cookbook_dir)
            
            # Run XeLaTeX compilation (twice for proper cross-references)
            console.print("[bold yellow]Running XeLaTeX compilation...[/bold yellow]")
            
            for run_num in [1, 2]:
                if verbose:
                    console.print(f"[blue]XeLaTeX run {run_num}/2[/blue]")
                
                result = subprocess.run([
                    "xelatex", 
                    "-interaction=nonstopmode",
                    "-output-directory=.",
                    "main.tex"
                ], capture_output=not verbose, text=True)
                
                if result.returncode != 0:
                    console.print(f"[bold red]✗ XeLaTeX compilation failed on run {run_num}[/bold red]")
                    if not verbose and result.stderr:
                        console.print(f"Error: {result.stderr}")
                    return 1
            
            # Rename output PDF
            main_pdf = cookbook_dir / "main.pdf"
            output_pdf = cookbook_dir / f"{output_name}.pdf"
            
            if main_pdf.exists():
                if output_pdf.exists():
                    output_pdf.unlink()  # Remove existing file
                main_pdf.rename(output_pdf)
                
                console.print(f"[bold green]✓ Cookbook compiled successfully![/bold green]")
                console.print(f"[bold green]PDF saved as:[/bold green] {output_pdf}")
            else:
                console.print("[bold red]✗ PDF output not found![/bold red]")
                return 1
            
            # Clean auxiliary files if requested
            if clean:
                if verbose:
                    console.print("[blue]Cleaning auxiliary files...[/blue]")
                
                aux_extensions = ['.aux', '.log', '.fls', '.fdb_latexmk', '.synctex.gz', '.toc']
                for ext in aux_extensions:
                    aux_file = cookbook_dir / f"main{ext}"
                    if aux_file.exists():
                        aux_file.unlink()
                        if verbose:
                            console.print(f"Removed: {aux_file.name}")
                
                console.print("[green]Auxiliary files cleaned[/green]")
        
        finally:
            os.chdir(original_cwd)
            
    except Exception as e:
        console.print(f"[bold red]✗ Compilation error:[/bold red] {str(e)}")
        if verbose:
            console.print_exception()
        return 1

@app.command()
def add_recipes(
    json_dir: Path = typer.Argument(..., help="Directory containing JSON recipe files"),
    image_dir: Path = typer.Argument(..., help="Directory containing recipe images"),
    cookbook_dir: Path = typer.Argument(..., help="Existing cookbook directory to add recipes to"),
    max_pages: int = typer.Option(1, help="Maximum pages per recipe"),
    no_build: bool = typer.Option(False, "--no-build", help="Don't build PDF automatically"),
    validate_pdf: bool = typer.Option(False, "--validate-pdf", help="Enable actual PDF compilation for validation (slower but accurate)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
):
    """Add new recipes to an existing cookbook by comparing available JSON files with compiled recipes.
    
    This command identifies which recipes from the JSON directory are missing from the 
    existing cookbook and adds only those new recipes, preserving the existing cookbook
    structure and metadata.
    
    Examples:
      Basic add:         add-recipes output/json/ output/image/ existing_cookbook/
      With validation:   add-recipes recipes/ images/ cookbook/ --validate-pdf
      No auto-build:     add-recipes recipes/ images/ cookbook/ --no-build
    """
    
    # Import here to avoid circular imports
    from .agents.cookbook_compiler import CookbookCompilerAgent
    from config.settings import OutputSettings
    import json
    
    # Setup logging
    if verbose:
        import logging
        logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
    
    console.print(f"[bold blue]Adding recipes to existing cookbook:[/bold blue]")
    console.print(f"  JSON recipes: {json_dir}")
    console.print(f"  Images: {image_dir}")
    console.print(f"  Cookbook: {cookbook_dir}")
    
    # Validate input directories
    if not json_dir.exists() or not json_dir.is_dir():
        console.print(f"[bold red]✗ JSON directory not found:[/bold red] {json_dir}")
        return 1
    
    if not image_dir.exists() or not image_dir.is_dir():
        console.print(f"[bold red]✗ Image directory not found:[/bold red] {image_dir}")
        return 1
    
    if not cookbook_dir.exists() or not cookbook_dir.is_dir():
        console.print(f"[bold red]✗ Cookbook directory not found:[/bold red] {cookbook_dir}")
        return 1
    
    # Check for main.tex in cookbook directory
    main_tex = cookbook_dir / "main.tex"
    if not main_tex.exists():
        console.print(f"[bold red]✗ main.tex not found in cookbook directory:[/bold red] {cookbook_dir}")
        console.print("This doesn't appear to be a valid cookbook directory.")
        return 1
    
    # Find all available JSON files
    json_files = list(json_dir.glob("*.json"))
    if not json_files:
        console.print(f"[bold red]✗ No JSON files found in:[/bold red] {json_dir}")
        return 1
    
    # Find existing recipe files in cookbook
    recipes_dir = cookbook_dir / "recipes"
    existing_recipes = set()
    if recipes_dir.exists():
        for tex_file in recipes_dir.glob("*.tex"):
            existing_recipes.add(tex_file.stem)
    
    # Determine which recipes need to be added
    available_recipes = {json_file.stem for json_file in json_files}
    new_recipes = available_recipes - existing_recipes
    
    if not new_recipes:
        console.print(f"[bold green]✓ No new recipes to add![/bold green]")
        console.print(f"All {len(available_recipes)} recipes are already in the cookbook.")
        return 0
    
    console.print(f"[green]Found {len(available_recipes)} total recipes[/green]")
    console.print(f"[blue]Existing recipes: {len(existing_recipes)}[/blue]")
    console.print(f"[yellow]New recipes to add: {len(new_recipes)}[/yellow]")
    
    if verbose:
        console.print(f"[bold cyan]New recipes:[/bold cyan]")
        for recipe in sorted(new_recipes):
            console.print(f"  • {recipe}")
    
    try:
        # Create compiler agent with PDF validation if requested
        settings = OutputSettings()
        settings.validate_pdf_layout = validate_pdf
        compiler = CookbookCompilerAgent(settings)
        
        # Get existing cookbook metadata from main.tex
        metadata = compiler._extract_cookbook_metadata(main_tex)
        
        # Filter JSON files to only new recipes
        new_json_files = [f for f in json_files if f.stem in new_recipes]
        
        # Create a temporary directory with only new recipes
        import tempfile
        import shutil
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_json_dir = Path(temp_dir) / "json"
            temp_json_dir.mkdir()
            
            # Copy only new JSON files to temp directory
            for json_file in new_json_files:
                shutil.copy2(json_file, temp_json_dir)
            
            # Add new recipes to existing cookbook
            success = compiler.add_recipes_to_cookbook(
                new_json_dir=temp_json_dir,
                image_dir=image_dir,
                cookbook_dir=cookbook_dir,
                max_pages_per_recipe=max_pages,
                auto_build=not no_build
            )
        
        if success:
            console.print(f"[bold green]✓ Successfully added {len(new_recipes)} new recipes![/bold green]")
            console.print(f"[bold green]Updated cookbook:[/bold green] {cookbook_dir}")
            
            if not no_build:
                pdf_path = cookbook_dir / "main.pdf"
                if pdf_path.exists():
                    console.print(f"[bold green]PDF updated:[/bold green] {pdf_path}")
                else:
                    console.print("[bold yellow]⚠ LaTeX files updated but PDF generation failed[/bold yellow]")
                    console.print("You can try building manually with: python -m src.main compile")
            else:
                console.print("[blue]LaTeX files updated. Use 'python -m src.main compile' to build PDF[/blue]")
            
            return 0
        else:
            console.print(f"[bold red]✗ Failed to add new recipes to cookbook[/bold red]")
            return 1
            
    except Exception as e:
        console.print(f"[bold red]✗ Error adding recipes:[/bold red] {str(e)}")
        if verbose:
            console.print_exception()
        return 1

@app.command()
def cookbook(
    json_dir: Path = typer.Argument(..., help="Directory containing JSON recipe files"),
    image_dir: Path = typer.Argument(..., help="Directory containing recipe images"),
    output_dir: Path = typer.Argument(..., help="Output directory for cookbook"),
    title: str = typer.Option("Recipe Collection", help="Cookbook title"),
    author: str = typer.Option("Chef", help="Cookbook author"),
    description: str = typer.Option("A collection of delicious recipes", help="Cookbook description"),
    max_pages: int = typer.Option(1, help="Maximum pages per recipe"),
    no_build: bool = typer.Option(False, "--no-build", help="Don't build PDF automatically"),
    validate_pdf: bool = typer.Option(False, "--validate-pdf", help="Enable actual PDF compilation for validation (slower but accurate)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
):
    """Compile JSON recipes and images into a complete LaTeX cookbook.
    
    This command takes a directory of JSON recipe files and their corresponding
    images, validates the formatting, and compiles them into a complete cookbook
    with automatic page layout and PDF generation.
    
    Examples:
      Basic cookbook:    cookbook output/json/ output/image/ cookbook_output/
      Custom title:      cookbook recipes/ images/ my_cookbook/ --title "My Recipes"
      No auto-build:     cookbook recipes/ images/ cookbook/ --no-build
    """
    
    # Import here to avoid circular imports
    from .agents.cookbook_compiler import CookbookCompilerAgent, CookbookMetadata
    from config.settings import OutputSettings
    
    # Setup logging
    if verbose:
        import logging
        logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
    
    console.print(f"[bold blue]Compiling cookbook from:[/bold blue]")
    console.print(f"  JSON recipes: {json_dir}")
    console.print(f"  Images: {image_dir}")
    console.print(f"  Output: {output_dir}")
    console.print(f"  Title: {title}")
    console.print(f"  Max pages per recipe: {max_pages}")
    
    # Validate input directories
    if not json_dir.exists() or not json_dir.is_dir():
        console.print(f"[bold red]✗ JSON directory not found:[/bold red] {json_dir}")
        return 1
    
    if not image_dir.exists() or not image_dir.is_dir():
        console.print(f"[bold red]✗ Image directory not found:[/bold red] {image_dir}")
        return 1
    
    # Check for JSON files
    json_files = list(json_dir.glob("*.json"))
    if not json_files:
        console.print(f"[bold red]✗ No JSON files found in:[/bold red] {json_dir}")
        return 1
    
    console.print(f"[green]Found {len(json_files)} recipe files[/green]")
    
    try:
        # Create cookbook metadata
        metadata = CookbookMetadata(
            title=title,
            author=author,
            description=description
        )
        
        # Create compiler agent with PDF validation if requested
        settings = OutputSettings()
        settings.validate_pdf_layout = validate_pdf
        compiler = CookbookCompilerAgent(settings)
        
        # Compile cookbook
        success = compiler.compile_cookbook(
            json_dir=json_dir,
            image_dir=image_dir,
            output_dir=output_dir,
            metadata=metadata,
            max_pages_per_recipe=max_pages,
            auto_build=not no_build
        )
        
        if success:
            console.print(f"[bold green]✓ Cookbook compilation successful![/bold green]")
            console.print(f"[bold green]Output directory:[/bold green] {output_dir}")
            
            if not no_build:
                pdf_path = output_dir / "main.pdf"
                if pdf_path.exists():
                    console.print(f"[bold green]PDF created:[/bold green] {pdf_path}")
                else:
                    console.print("[bold yellow]⚠ LaTeX files created but PDF generation failed[/bold yellow]")
                    console.print("You can try building manually with: python -m src.main compile")
            else:
                console.print("[blue]LaTeX files created. Use 'python -m src.main compile' to build PDF[/blue]")
            
            return 0
        else:
            console.print(f"[bold red]✗ Cookbook compilation failed[/bold red]")
            return 1
            
    except Exception as e:
        console.print(f"[bold red]✗ Compilation error:[/bold red] {str(e)}")
        if verbose:
            console.print_exception()
        return 1


if __name__ == "__main__":
    app()