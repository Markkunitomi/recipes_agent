"""
USDA FoodData Central API integration for ingredient density lookup
"""
import os
import requests
import logging
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

class USDAFoodAPI:
    """Interface to USDA FoodData Central API for ingredient data."""
    
    def __init__(self, api_key: str = None):
        """Initialize with API key."""
        self.api_key = api_key or os.getenv('USDA')
        self.base_url = "https://api.nal.usda.gov/fdc/v1"
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        self.cache = {}  # Simple in-memory cache
        
        if not self.api_key:
            self.logger.warning("No USDA API key found. Set USDA environment variable.")
    
    def search_food(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search for foods by name.
        
        Args:
            query: Food name to search for
            max_results: Maximum number of results to return
            
        Returns:
            List of food items with basic info
        """
        if not self.api_key:
            return []
        
        # Check cache first
        cache_key = f"search_{query}_{max_results}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        url = f"{self.base_url}/foods/search"
        params = {
            "api_key": self.api_key,
            "query": query,
            "pageSize": max_results,
            "dataType": ["Survey (FNDDS)", "SR Legacy", "Foundation"]  # Prioritize FNDDS for portion data
        }
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            foods = response.json().get("foods", [])
            
            # Cache result
            self.cache[cache_key] = foods
            
            self.logger.debug(f"Found {len(foods)} foods for query: {query}")
            return foods
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error searching USDA API for '{query}': {e}")
            return []
    
    def get_food_details(self, fdc_id: int) -> Optional[Dict[str, Any]]:
        """
        Get detailed food information including portions and nutrients.
        
        Args:
            fdc_id: FoodData Central ID
            
        Returns:
            Detailed food information or None if not found
        """
        if not self.api_key:
            return None
        
        # Check cache first
        cache_key = f"details_{fdc_id}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        url = f"{self.base_url}/food/{fdc_id}"
        params = {"api_key": self.api_key}
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            details = response.json()
            
            # Cache result
            self.cache[cache_key] = details
            
            return details
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error getting USDA food details for ID {fdc_id}: {e}")
            return None
    
    def find_density_info(self, ingredient_name: str) -> Optional[Dict[str, Any]]:
        """
        Find density information for an ingredient using USDA API.
        
        Args:
            ingredient_name: Name of ingredient to look up
            
        Returns:
            Dictionary with density info or None if not found
        """
        if not ingredient_name:
            return None
        
        # Search for the ingredient
        foods = self.search_food(ingredient_name, max_results=3)
        
        if not foods:
            return None
        
        # Look for the best match with portion data
        for food in foods:
            fdc_id = food.get('fdcId')
            description = food.get('description', '')
            
            if not fdc_id:
                continue
            
            # Get detailed information
            details = self.get_food_details(fdc_id)
            
            if not details:
                continue
            
            # Extract portion data for density calculation
            portions = details.get('foodPortions', [])
            
            for portion in portions:
                portion_description = portion.get('portionDescription', '').lower()
                gram_weight = portion.get('gramWeight')
                
                if not gram_weight or not portion_description:
                    continue
                
                # Parse portion description for volume measurements
                # Examples: "1 cup", "2 tablespoons", "1 fluid ounce"
                volume_info = self._parse_portion_description(portion_description)
                
                if volume_info:
                    amount, unit_name = volume_info
                    # Calculate density from volume portion
                    density_info = self._calculate_density_from_portion(
                        amount, unit_name, gram_weight, description, fdc_id
                    )
                    
                    if density_info:
                        return density_info
        
        return None
    
    def _calculate_density_from_portion(self, amount: float, unit_name: str, 
                                       gram_weight: float, description: str, 
                                       fdc_id: int) -> Optional[Dict[str, Any]]:
        """
        Calculate density from a volume portion.
        
        Args:
            amount: Amount in the unit
            unit_name: Name of the unit
            gram_weight: Weight in grams for this portion
            description: Food description
            fdc_id: FoodData Central ID
            
        Returns:
            Density information dictionary
        """
        # Convert unit to milliliters
        volume_ml = self._convert_to_ml(amount, unit_name)
        
        if not volume_ml or volume_ml <= 0:
            return None
        
        # Calculate density
        density_g_ml = gram_weight / volume_ml
        
        # Sanity check - density should be reasonable for food
        if density_g_ml < 0.1 or density_g_ml > 3.0:
            self.logger.warning(f"Unusual density {density_g_ml} g/ml for {description}")
            return None
        
        return {
            'name': description,
            'category': 'USDA FoodData Central',
            'density_g_ml': density_g_ml,
            'specific_gravity': None,
            'source': f'USDA FDC ID: {fdc_id}',
            'match_score': 0.8,  # Lower than exact local matches
            'search_name': description.lower(),
            'calculation_details': {
                'amount': amount,
                'unit': unit_name,
                'weight_g': gram_weight,
                'volume_ml': volume_ml
            }
        }
    
    def _parse_portion_description(self, description: str) -> Optional[tuple[float, str]]:
        """
        Parse portion description to extract amount and volume unit.
        
        Examples:
        - "1 cup" -> (1.0, "cup")
        - "2 tablespoons" -> (2.0, "tablespoon")
        - "1 fluid ounce" -> (1.0, "fluid ounce")
        
        Args:
            description: Portion description string
            
        Returns:
            Tuple of (amount, unit_name) or None if not a volume measurement
        """
        description = description.lower().strip()
        
        # Define volume units we're looking for
        volume_patterns = [
            (r'(\d+(?:\.\d+)?)\s*cups?', 'cup'),
            (r'(\d+(?:\.\d+)?)\s*tablespoons?', 'tablespoon'),
            (r'(\d+(?:\.\d+)?)\s*tbsps?', 'tablespoon'),
            (r'(\d+(?:\.\d+)?)\s*teaspoons?', 'teaspoon'),
            (r'(\d+(?:\.\d+)?)\s*tsps?', 'teaspoon'),
            (r'(\d+(?:\.\d+)?)\s*fluid\s*ounces?', 'fluid ounce'),
            (r'(\d+(?:\.\d+)?)\s*fl\s*ozs?', 'fluid ounce'),
            (r'(\d+(?:\.\d+)?)\s*milliliters?', 'ml'),
            (r'(\d+(?:\.\d+)?)\s*mls?', 'ml'),
            (r'(\d+(?:\.\d+)?)\s*liters?', 'liter'),
            (r'(\d+(?:\.\d+)?)\s*pints?', 'pint'),
            (r'(\d+(?:\.\d+)?)\s*quarts?', 'quart'),
            (r'(\d+(?:\.\d+)?)\s*gallons?', 'gallon'),
        ]
        
        import re
        
        for pattern, unit in volume_patterns:
            match = re.search(pattern, description)
            if match:
                try:
                    amount = float(match.group(1))
                    return (amount, unit)
                except ValueError:
                    continue
        
        return None
    
    def _convert_to_ml(self, amount: float, unit_name: str) -> Optional[float]:
        """Convert various volume units to milliliters."""
        unit_name = unit_name.lower().strip()
        
        # Standard conversions to ml
        conversions = {
            'cup': 236.588,
            'cups': 236.588,
            'tablespoon': 14.787,
            'tablespoons': 14.787,
            'tbsp': 14.787,
            'teaspoon': 4.929,
            'teaspoons': 4.929,
            'tsp': 4.929,
            'fluid ounce': 29.574,
            'fluid ounces': 29.574,
            'fl oz': 29.574,
            'fl. oz.': 29.574,
            'ml': 1,
            'milliliter': 1,
            'milliliters': 1,
            'liter': 1000,
            'liters': 1000,
            'l': 1000,
            'pint': 473.176,
            'pints': 473.176,
            'quart': 946.353,
            'quarts': 946.353,
            'gallon': 3785.41,
            'gallons': 3785.41
        }
        
        # Look for exact match first
        if unit_name in conversions:
            return amount * conversions[unit_name]
        
        # Look for partial matches
        for unit, factor in conversions.items():
            if unit in unit_name or unit_name in unit:
                return amount * factor
        
        return None
    
    def get_ingredient_suggestions(self, partial_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get ingredient suggestions from USDA API.
        
        Args:
            partial_name: Partial ingredient name
            limit: Maximum number of suggestions
            
        Returns:
            List of suggested ingredients
        """
        foods = self.search_food(partial_name, max_results=limit)
        
        suggestions = []
        for food in foods:
            suggestions.append({
                'name': food.get('description', ''),
                'category': food.get('dataType', 'USDA'),
                'fdc_id': food.get('fdcId'),
                'brand': food.get('brandOwner', ''),
                'source': 'USDA FoodData Central'
            })
        
        return suggestions
    
    def clear_cache(self):
        """Clear the API response cache."""
        self.cache.clear()
        self.logger.info("USDA API cache cleared")