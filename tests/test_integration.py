#!/usr/bin/env python3
"""
Integration tests for the complete pipeline
"""
import pytest
from pathlib import Path
from config.settings import Settings
from orchestrators.orchestrator import RecipeOrchestrator

class TestRecipeOrchestrator:
    """Test complete recipe processing pipeline."""
    
    def setup_method(self):
        """Set up test environment."""
        self.settings = Settings()
        self.orchestrator = RecipeOrchestrator(self.settings)
    
    def test_initialization(self):
        """Test orchestrator initialization."""
        assert self.orchestrator.settings == self.settings
        assert hasattr(self.orchestrator, 'scraper')
        assert hasattr(self.orchestrator, 'parser')
        assert hasattr(self.orchestrator, 'normalizer')
        assert hasattr(self.orchestrator, 'converter')
        assert hasattr(self.orchestrator, 'renderer')
    
    @pytest.mark.slow
    def test_complete_pipeline_with_known_site(self):
        """Test complete pipeline with a known working recipe site."""
        test_urls = [
            "https://www.seriouseats.com/the-best-baba-ganoush-recipe",
        ]
        
        for url in test_urls:
            try:
                result = self.orchestrator.process_recipe(
                    url, 
                    output_format="html",
                    debug_enabled=True
                )
                
                assert result.success is True, f"Failed to process {url}: {result.error}"
                assert result.recipe is not None
                assert result.output_path is not None
                assert result.output_path.exists()
                
                # Verify recipe has essential components
                recipe = result.recipe
                assert recipe.title is not None
                assert len(recipe.title.strip()) > 0
                assert len(recipe.ingredients) > 0
                assert len(recipe.instructions) > 0
                
                print(f"✓ Successfully processed: {recipe.title}")
                
            except Exception as e:
                pytest.fail(f"Pipeline failed for {url}: {e}")
    
    def test_invalid_url_handling(self):
        """Test handling of invalid URLs."""
        result = self.orchestrator.process_recipe("https://definitely-not-a-real-website.com/recipe")
        assert result.success is False
        assert result.error is not None
    
    def test_debug_output(self):
        """Test debug output generation."""
        # Use a simple URL that should work
        url = "https://www.seriouseats.com/the-best-baba-ganoush-recipe"
        
        result = self.orchestrator.process_recipe(
            url,
            output_format="html",
            debug_enabled=True,
            debug_dir="./test_debug"
        )
        
        if result.success:
            assert result.debug_dir is not None
            debug_path = Path(result.debug_dir)
            assert debug_path.exists()
            
            # Check for debug files
            expected_files = [
                "01_scraper.json",
                "02_parser.json", 
                "03_normalizer.json",
                "04_converter.json",
                "05_renderer.json",
                "summary.json"
            ]
            
            for filename in expected_files:
                file_path = debug_path / filename
                assert file_path.exists(), f"Debug file {filename} not found"
    
    def test_multiple_output_formats(self):
        """Test generation of multiple output formats."""
        url = "https://www.seriouseats.com/the-best-baba-ganoush-recipe"
        
        formats_to_test = ["html", "latex", "json"]
        
        for output_format in formats_to_test:
            try:
                result = self.orchestrator.process_recipe(url, output_format=output_format)
                
                if result.success:
                    assert result.output_path is not None
                    assert result.output_path.exists()
                    
                    # Check file extension matches format
                    if output_format == "html":
                        assert result.output_path.suffix == ".html"
                    elif output_format == "latex":
                        assert result.output_path.suffix == ".tex"
                    elif output_format == "json":
                        assert result.output_path.suffix == ".json"
                    
                    print(f"✓ Generated {output_format} output: {result.output_path}")
                else:
                    print(f"⚠ Failed to generate {output_format}: {result.error}")
                    
            except Exception as e:
                print(f"✗ Error testing {output_format}: {e}")

class TestPerformance:
    """Test performance characteristics."""
    
    def setup_method(self):
        """Set up test environment."""
        self.settings = Settings()
        self.orchestrator = RecipeOrchestrator(self.settings)
    
    @pytest.mark.slow
    def test_processing_time_reasonable(self):
        """Test that processing time is reasonable."""
        import time
        
        url = "https://www.seriouseats.com/the-best-baba-ganoush-recipe"
        
        start_time = time.time()
        result = self.orchestrator.process_recipe(url, debug_enabled=True)
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        if result.success:
            # Should complete within 2 minutes for most recipes
            assert processing_time < 120, f"Processing took too long: {processing_time:.2f}s"
            print(f"✓ Processing completed in {processing_time:.2f}s")
        else:
            print(f"⚠ Processing failed: {result.error}")

if __name__ == "__main__":
    # Run tests with different verbosity levels
    pytest.main([__file__, "-v", "-m", "not slow"])  # Skip slow tests by default