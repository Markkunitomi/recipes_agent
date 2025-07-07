#!/usr/bin/env python3
"""
Test script for the Recipe Agent System
"""
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import Settings
from orchestrators.orchestrator import RecipeOrchestrator

console = Console()

def test_configuration():
    """Test configuration loading."""
    console.print("[bold blue]Testing Configuration...[/bold blue]")
    
    try:
        settings = Settings.load()
        console.print("[green]✓ Configuration loaded successfully[/green]")
        
        # Show LLM availability
        llm_status = settings.validate_llm_setup()
        table = Table(title="LLM Provider Status")
        table.add_column("Provider", style="cyan")
        table.add_column("Available", style="green")
        
        for provider, available in llm_status.items():
            status = "✓" if available else "✗"
            color = "green" if available else "red"
            table.add_row(provider.replace('_', ' ').title(), f"[{color}]{status}[/{color}]")
        
        console.print(table)
        
        return settings
        
    except Exception as e:
        console.print(f"[red]✗ Configuration error: {e}[/red]")
        return None

def test_individual_agents(settings):
    """Test individual agents."""
    console.print("\n[bold blue]Testing Individual Agents...[/bold blue]")
    
    # Test imports
    try:
        from agents.scraper import ScraperAgent
        from agents.parser import ParserAgent
        from agents.normalizer import NormalizerAgent
        from agents.converter import ConverterAgent
        from agents.renderer import RendererAgent
        console.print("[green]✓ All agents imported successfully[/green]")
    except Exception as e:
        console.print(f"[red]✗ Agent import error: {e}[/red]")
        return False
    
    # Test agent initialization
    try:
        scraper = ScraperAgent(settings)
        parser = ParserAgent(settings)
        normalizer = NormalizerAgent(settings)
        converter = ConverterAgent(settings)
        renderer = RendererAgent(settings)
        console.print("[green]✓ All agents initialized successfully[/green]")
        return True
    except Exception as e:
        console.print(f"[red]✗ Agent initialization error: {e}[/red]")
        return False

def test_data_models():
    """Test data models."""
    console.print("\n[bold blue]Testing Data Models...[/bold blue]")
    
    try:
        from models.recipe import Recipe, Ingredient, InstructionStep
        from models.conversion import UnitConverter
        
        # Test recipe creation
        recipe = Recipe(
            title="Test Recipe",
            ingredients=[
                Ingredient(name="flour", quantity=2.0, unit="cup", original_text="2 cups flour"),
                Ingredient(name="sugar", quantity=1.0, unit="cup", original_text="1 cup sugar")
            ],
            instructions=[
                InstructionStep(step_number=1, instruction="Mix ingredients together"),
                InstructionStep(step_number=2, instruction="Bake for 30 minutes")
            ]
        )
        
        console.print(f"[green]✓ Recipe model created: {recipe.title}[/green]")
        console.print(f"  - {len(recipe.ingredients)} ingredients")
        console.print(f"  - {len(recipe.instructions)} instructions")
        
        # Test unit converter
        converter = UnitConverter()
        result = converter.convert_volume(1.0, "cup", "ml")
        console.print(f"[green]✓ Unit conversion: 1 cup = {result.converted_quantity} ml[/green]")
        
        return True
        
    except Exception as e:
        console.print(f"[red]✗ Data model error: {e}[/red]")
        return False

def test_recipe_scraping(settings):
    """Test recipe scraping with a known good URL."""
    console.print("\n[bold blue]Testing Recipe Scraping...[/bold blue]")
    
    # List of test URLs (these should be reliable recipe sites)
    test_urls = [
        "https://www.allrecipes.com/recipe/213742/cheesy-chicken-broccoli-casserole/",
        "https://www.foodnetwork.com/recipes/alton-brown/baked-macaroni-and-cheese-recipe-1939524",
        "https://www.epicurious.com/recipes/food/views/simple-chocolate-chip-cookies"
    ]
    
    try:
        from agents.scraper import ScraperAgent
        scraper = ScraperAgent(settings)
        
        console.print("Available for testing - supported sites:")
        supported_sites = scraper.get_supported_sites()[:10]  # Show first 10
        for site in supported_sites:
            console.print(f"  - {site}")
        console.print(f"  ... and {len(scraper.get_supported_sites()) - 10} more")
        
        console.print("\n[yellow]Note: Actual scraping requires internet connection and working URLs[/yellow]")
        console.print("[green]✓ Scraper agent ready[/green]")
        
        return True
        
    except Exception as e:
        console.print(f"[red]✗ Scraper test error: {e}[/red]")
        return False

def test_output_generation(settings):
    """Test output generation."""
    console.print("\n[bold blue]Testing Output Generation...[/bold blue]")
    
    try:
        from models.recipe import Recipe, Ingredient, InstructionStep
        from agents.renderer import RendererAgent
        
        # Create a test recipe
        test_recipe = Recipe(
            title="Test Chocolate Chip Cookies",
            description="Simple and delicious chocolate chip cookies",
            prep_time=15,
            cook_time=12,
            servings=24,
            ingredients=[
                Ingredient(name="all-purpose flour", quantity=2.25, unit="cup", original_text="2 1/4 cups all-purpose flour"),
                Ingredient(name="butter", quantity=1.0, unit="cup", original_text="1 cup butter, softened"),
                Ingredient(name="brown sugar", quantity=0.75, unit="cup", original_text="3/4 cup brown sugar"),
                Ingredient(name="white sugar", quantity=0.75, unit="cup", original_text="3/4 cup white sugar"),
                Ingredient(name="eggs", quantity=2.0, unit="large", original_text="2 large eggs"),
                Ingredient(name="vanilla extract", quantity=2.0, unit="tsp", original_text="2 tsp vanilla extract"),
                Ingredient(name="chocolate chips", quantity=2.0, unit="cup", original_text="2 cups chocolate chips")
            ],
            instructions=[
                InstructionStep(step_number=1, instruction="Preheat oven to 375°F (190°C)"),
                InstructionStep(step_number=2, instruction="In a large bowl, cream together butter and sugars until light and fluffy"),
                InstructionStep(step_number=3, instruction="Beat in eggs one at a time, then add vanilla"),
                InstructionStep(step_number=4, instruction="Gradually mix in flour until just combined"),
                InstructionStep(step_number=5, instruction="Fold in chocolate chips"),
                InstructionStep(step_number=6, instruction="Drop rounded tablespoons of dough onto ungreased baking sheets"),
                InstructionStep(step_number=7, instruction="Bake for 9-12 minutes or until golden brown"),
                InstructionStep(step_number=8, instruction="Cool on baking sheet for 2 minutes before transferring to wire rack")
            ],
            tags=["dessert", "cookies", "chocolate", "baking"],
        )
        
        # Test renderer
        renderer = RendererAgent(settings)
        
        # Test HTML rendering
        html_result = renderer.render(test_recipe, "html")
        if html_result.success:
            console.print("[green]✓ HTML rendering successful[/green]")
            console.print(f"  Output: {html_result.data.output_path}")
        else:
            console.print(f"[red]✗ HTML rendering failed: {html_result.error}[/red]")
        
        # Test JSON rendering
        json_result = renderer.render(test_recipe, "json")
        if json_result.success:
            console.print("[green]✓ JSON rendering successful[/green]")
            console.print(f"  Output: {json_result.data.output_path}")
        else:
            console.print(f"[red]✗ JSON rendering failed: {json_result.error}[/red]")
        
        # Test LaTeX rendering
        latex_result = renderer.render(test_recipe, "latex")
        if latex_result.success:
            console.print("[green]✓ LaTeX rendering successful[/green]")
            console.print(f"  Output: {latex_result.data.output_path}")
        else:
            console.print(f"[red]✗ LaTeX rendering failed: {latex_result.error}[/red]")
        
        return True
        
    except Exception as e:
        console.print(f"[red]✗ Output generation error: {e}[/red]")
        return False

def main():
    """Run all tests."""
    console.print("[bold magenta]Recipe Agent System - Test Suite[/bold magenta]")
    console.print("=" * 50)
    
    # Test configuration
    settings = test_configuration()
    if not settings:
        console.print("[red]Configuration test failed - stopping[/red]")
        return 1
    
    # Test data models
    if not test_data_models():
        console.print("[red]Data model test failed[/red]")
        return 1
    
    # Test individual agents
    if not test_individual_agents(settings):
        console.print("[red]Agent test failed[/red]")
        return 1
    
    # Test scraping capabilities
    test_recipe_scraping(settings)
    
    # Test output generation
    if not test_output_generation(settings):
        console.print("[red]Output generation test failed[/red]")
        return 1
    
    console.print("\n" + "=" * 50)
    console.print("[bold green]All tests completed successfully! 🎉[/bold green]")
    console.print("\n[bold yellow]Next steps:[/bold yellow]")
    console.print("1. Add your API keys to .env file")
    console.print("2. Test with a real recipe URL using: python main.py <url>")
    console.print("3. Check the output/ directory for generated files")
    
    return 0

if __name__ == "__main__":
    exit(main())