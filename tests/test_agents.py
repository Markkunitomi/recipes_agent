#!/usr/bin/env python3
"""
Unit tests for individual agents
"""
import pytest
from unittest.mock import Mock, patch
from config.settings import Settings
from models.recipe import Recipe, Ingredient, NutritionInfo
from agents.scraper import ScraperAgent
from agents.parser import ParserAgent
from agents.normalizer import NormalizerAgent
from agents.converter import ConverterAgent
from agents.renderer import RendererAgent

class TestScraperAgent:
    """Test scraper agent functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.settings = Settings()
        self.agent = ScraperAgent(self.settings)
    
    def test_initialization(self):
        """Test agent initialization."""
        assert self.agent.settings == self.settings
        assert hasattr(self.agent, 'session')
        assert hasattr(self.agent, 'supported_sites')
    
    @patch('recipe_scrapers.scrape_me')
    def test_successful_scraping(self, mock_scrape):
        """Test successful recipe scraping."""
        # Mock successful scraping
        mock_recipe = Mock()
        mock_recipe.title.return_value = "Test Recipe"
        mock_recipe.ingredients.return_value = ["1 cup flour", "2 eggs"]
        mock_recipe.instructions.return_value = "Mix ingredients"
        mock_recipe.total_time.return_value = 30
        mock_recipe.prep_time.return_value = 10
        mock_recipe.cook_time.return_value = 20
        mock_recipe.yields.return_value = "4 servings"
        
        mock_scrape.return_value = mock_recipe
        
        result = self.agent.scrape("https://example.com/recipe")
        
        assert result.success is True
        assert result.data is not None
        assert result.data.title == "Test Recipe"
    
    def test_invalid_url(self):
        """Test handling of invalid URLs."""
        result = self.agent.scrape("not-a-url")
        assert result.success is False
        assert result.error is not None

class TestParserAgent:
    """Test parser agent functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.settings = Settings()
        self.agent = ParserAgent(self.settings)
    
    def test_initialization(self):
        """Test agent initialization."""
        assert self.agent.settings == self.settings
        # ParserAgent should have LLM manager
        assert hasattr(self.agent, 'llm_manager')
    
    def test_ingredient_parsing(self):
        """Test ingredient parsing functionality."""
        # Create test recipe
        recipe = Recipe(
            title="Test Recipe",
            ingredients_raw=["1 cup all-purpose flour", "2 large eggs", "1/2 tsp salt"],
            instructions_raw=["Mix ingredients", "Bake for 20 minutes"]
        )
        
        result = self.agent.parse(recipe)
        
        # Should successfully parse even without LLM (fallback parsing)
        assert result.success is True
        assert result.data is not None

class TestNormalizerAgent:
    """Test normalizer agent functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.settings = Settings()
        self.agent = NormalizerAgent(self.settings)
    
    def test_initialization(self):
        """Test agent initialization."""
        assert self.agent.settings == self.settings
        # NormalizerAgent should have LLM manager
        assert hasattr(self.agent, 'llm_manager')
    
    def test_normalization(self):
        """Test recipe normalization."""
        # Create test recipe with parsed ingredients
        recipe = Recipe(
            title="Test Recipe",
            ingredients=[
                Ingredient(quantity=1.0, unit="cup", name="flour", original_text="1 cup flour"),
                Ingredient(quantity=2.0, unit="", name="eggs", original_text="2 eggs")
            ],
            instructions=["Mix ingredients", "Bake for 20 minutes"]
        )
        
        result = self.agent.normalize(recipe)
        
        assert result.success is True
        assert result.data is not None

class TestConverterAgent:
    """Test converter agent functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.settings = Settings()
        self.agent = ConverterAgent(self.settings)
    
    def test_initialization(self):
        """Test agent initialization."""
        assert self.agent.settings == self.settings
        # ConverterAgent uses density lookup, not LLM
    
    def test_unit_conversion(self):
        """Test unit conversion functionality."""
        # Create test recipe
        recipe = Recipe(
            title="Test Recipe",
            ingredients=[
                Ingredient(quantity=250.0, unit="ml", name="milk", original_text="250ml milk"),
                Ingredient(quantity=500.0, unit="g", name="flour", original_text="500g flour")
            ],
            instructions=["Mix ingredients"]
        )
        
        result = self.agent.convert(recipe)
        
        assert result.success is True
        assert result.data is not None

class TestRendererAgent:
    """Test renderer agent functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.settings = Settings()
        self.agent = RendererAgent(self.settings)
    
    def test_initialization(self):
        """Test agent initialization."""
        assert self.agent.settings == self.settings
        # RendererAgent uses templates, not LLM
    
    def test_html_rendering(self):
        """Test HTML rendering."""
        # Create test recipe
        recipe = Recipe(
            title="Test Recipe",
            description="A simple test recipe",
            ingredients=[
                Ingredient(quantity=1.0, unit="cup", name="flour", original_text="1 cup flour"),
                Ingredient(quantity=2.0, unit="", name="eggs", original_text="2 eggs")
            ],
            instructions=["Mix ingredients", "Bake for 20 minutes"],
            prep_time=10,
            cook_time=20,
            servings=4
        )
        
        result = self.agent.render(recipe, "html")
        
        assert result.success is True
        assert result.data is not None
        assert result.data.output_path is not None
    
    def test_latex_rendering(self):
        """Test LaTeX rendering."""
        # Create test recipe
        recipe = Recipe(
            title="Test Recipe",
            description="A simple test recipe",
            ingredients=[
                Ingredient(quantity=1.0, unit="cup", name="flour", original_text="1 cup flour"),
                Ingredient(quantity=2.0, unit="", name="eggs", original_text="2 eggs")
            ],
            instructions=["Mix ingredients", "Bake for 20 minutes"],
            prep_time=10,
            cook_time=20,
            servings=4
        )
        
        result = self.agent.render(recipe, "latex")
        
        assert result.success is True
        assert result.data is not None
        assert result.data.output_path is not None

if __name__ == "__main__":
    pytest.main([__file__, "-v"])