#!/usr/bin/env python3
"""
Batch test script for processing multiple recipe URLs
"""
import sys
import time
from pathlib import Path
from typing import List, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, TaskID
from rich.panel import Panel

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import Settings
from orchestrators.orchestrator import RecipeOrchestrator

console = Console()

class BatchTestResult:
    """Result of batch testing."""
    def __init__(self):
        self.total_urls = 0
        self.successful = []
        self.failed = []
        self.results = []
        self.start_time = None
        self.end_time = None

def load_urls(file_path) -> List[str]:
    """Load URLs from file."""
    try:
        with open(file_path, 'r') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        return urls
    except FileNotFoundError:
        console.print(f"[red]Error: File {file_path} not found[/red]")
        return []

def test_single_url(orchestrator: RecipeOrchestrator, url: str, formats: List[str] = None) -> Dict[str, Any]:
    """Test a single URL."""
    if formats is None:
        formats = ['json', 'html']  # Skip LaTeX for speed
    
    start_time = time.time()
    result = {
        'url': url,
        'domain': url.split('/')[2] if url.count('/') >= 2 else url,
        'success': False,
        'error': None,
        'recipe_title': None,
        'ingredients_count': 0,
        'instructions_count': 0,
        'processing_time': 0,
        'outputs': {},
        'confidence_score': None
    }
    
    try:
        # Test JSON format first (fastest)
        json_result = orchestrator.process_recipe(url, "json")
        
        if json_result.success:
            result['success'] = True
            result['recipe_title'] = json_result.recipe.title
            result['ingredients_count'] = len(json_result.recipe.ingredients)
            result['instructions_count'] = len(json_result.recipe.instructions)
            result['confidence_score'] = json_result.recipe.confidence_score
            result['outputs']['json'] = str(json_result.output_path)
            
            # Test HTML format if JSON succeeded
            if 'html' in formats:
                html_result = orchestrator.process_recipe(url, "html")
                if html_result.success:
                    result['outputs']['html'] = str(html_result.output_path)
            
            # Test LaTeX format if requested
            if 'latex' in formats:
                latex_result = orchestrator.process_recipe(url, "latex")
                if latex_result.success:
                    result['outputs']['latex'] = str(latex_result.output_path)
        else:
            result['error'] = json_result.error
            
    except Exception as e:
        result['error'] = str(e)
    
    result['processing_time'] = time.time() - start_time
    return result

def run_batch_test(urls: List[str], output_formats: List[str] = None) -> BatchTestResult:
    """Run batch test on all URLs."""
    batch_result = BatchTestResult()
    batch_result.total_urls = len(urls)
    batch_result.start_time = time.time()
    
    # Load configuration
    try:
        settings = Settings.load()
        orchestrator = RecipeOrchestrator(settings)
    except Exception as e:
        console.print(f"[red]Failed to initialize system: {e}[/red]")
        return batch_result
    
    # Process URLs with progress bar
    with Progress() as progress:
        task = progress.add_task("[green]Processing recipes...", total=len(urls))
        
        for url in urls:
            console.print(f"\n[cyan]Testing:[/cyan] {url}")
            
            result = test_single_url(orchestrator, url, output_formats)
            batch_result.results.append(result)
            
            if result['success']:
                batch_result.successful.append(url)
                console.print(f"[green]✓ Success:[/green] {result['recipe_title']}")
                console.print(f"  Ingredients: {result['ingredients_count']}, Instructions: {result['instructions_count']}")
                console.print(f"  Time: {result['processing_time']:.2f}s")
            else:
                batch_result.failed.append(url)
                console.print(f"[red]✗ Failed:[/red] {result['error']}")
            
            progress.update(task, advance=1)
    
    batch_result.end_time = time.time()
    return batch_result

def generate_report(batch_result: BatchTestResult):
    """Generate detailed test report."""
    console.print("\n" + "="*80)
    console.print("[bold magenta]BATCH TEST REPORT[/bold magenta]")
    console.print("="*80)
    
    # Summary statistics
    success_rate = (len(batch_result.successful) / batch_result.total_urls) * 100 if batch_result.total_urls > 0 else 0
    total_time = batch_result.end_time - batch_result.start_time if batch_result.start_time else 0
    avg_time = total_time / batch_result.total_urls if batch_result.total_urls > 0 else 0
    
    summary_table = Table(title="Summary Statistics")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="green")
    
    summary_table.add_row("Total URLs", str(batch_result.total_urls))
    summary_table.add_row("Successful", str(len(batch_result.successful)))
    summary_table.add_row("Failed", str(len(batch_result.failed)))
    summary_table.add_row("Success Rate", f"{success_rate:.1f}%")
    summary_table.add_row("Total Time", f"{total_time:.2f}s")
    summary_table.add_row("Average Time per Recipe", f"{avg_time:.2f}s")
    
    console.print(summary_table)
    
    # Detailed results table
    if batch_result.results:
        results_table = Table(title="Detailed Results")
        results_table.add_column("Domain", style="cyan")
        results_table.add_column("Status", style="green")
        results_table.add_column("Recipe Title", style="yellow", max_width=40)
        results_table.add_column("Ingredients", justify="right")
        results_table.add_column("Instructions", justify="right")
        results_table.add_column("Time (s)", justify="right")
        results_table.add_column("Confidence", justify="right")
        
        for result in batch_result.results:
            status = "✓" if result['success'] else "✗"
            status_color = "green" if result['success'] else "red"
            title = result['recipe_title'] or result['error'] or "Unknown"
            if len(title) > 40:
                title = title[:37] + "..."
            
            confidence = f"{result['confidence_score']:.2f}" if result['confidence_score'] else "N/A"
            
            results_table.add_row(
                result['domain'],
                f"[{status_color}]{status}[/{status_color}]",
                title,
                str(result['ingredients_count']) if result['success'] else "-",
                str(result['instructions_count']) if result['success'] else "-",
                f"{result['processing_time']:.2f}",
                confidence if result['success'] else "-"
            )
        
        console.print(results_table)
    
    # Failed URLs details
    if batch_result.failed:
        console.print("\n[bold red]Failed URLs:[/bold red]")
        for i, url in enumerate(batch_result.failed):
            result = next(r for r in batch_result.results if r['url'] == url)
            console.print(f"{i+1}. {url}")
            console.print(f"   Error: {result['error']}")
    
    # Output files generated
    successful_results = [r for r in batch_result.results if r['success']]
    if successful_results:
        console.print("\n[bold green]Output Files Generated:[/bold green]")
        for result in successful_results:
            console.print(f"\n[cyan]{result['recipe_title']}:[/cyan]")
            for format_type, path in result['outputs'].items():
                console.print(f"  - {format_type.upper()}: {path}")

def main():
    """Main function."""
    console.print("[bold blue]Recipe Agent System - Batch Testing[/bold blue]")
    
    # Load URLs
    urls_file = "recipe_urls.txt"
    urls = load_urls(urls_file)
    
    if not urls:
        console.print("[red]No URLs found to test[/red]")
        return 1
    
    console.print(f"[green]Loaded {len(urls)} URLs from {urls_file}[/green]")
    
    # Show URLs to be tested
    console.print("\n[bold]URLs to test:[/bold]")
    for i, url in enumerate(urls, 1):
        console.print(f"{i}. {url}")
    
    # Ask for output formats
    console.print("\n[bold]Output formats to test:[/bold] JSON, HTML (LaTeX skipped for speed)")
    
    # Run batch test
    batch_result = run_batch_test(urls, ['json', 'html'])
    
    # Generate report
    generate_report(batch_result)
    
    # Save detailed results to file
    import json
    results_file = Path("batch_test_results.json")
    with open(results_file, 'w') as f:
        json.dump({
            'summary': {
                'total_urls': batch_result.total_urls,
                'successful': len(batch_result.successful),
                'failed': len(batch_result.failed),
                'success_rate': (len(batch_result.successful) / batch_result.total_urls) * 100,
                'total_time': batch_result.end_time - batch_result.start_time,
            },
            'results': batch_result.results
        }, f, indent=2, default=str)
    
    console.print(f"\n[bold]Detailed results saved to: {results_file}[/bold]")
    
    return 0 if len(batch_result.successful) > 0 else 1

if __name__ == "__main__":
    exit(main())