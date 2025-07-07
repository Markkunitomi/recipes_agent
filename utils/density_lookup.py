"""
Density lookup utility for ingredient matching and conversions
"""
import pandas as pd
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import re
from difflib import SequenceMatcher
import logging
from .usda_api import USDAFoodAPI

class DensityLookup:
    """Utility for looking up ingredient densities and performing conversions."""
    
    def __init__(self, densities_file: str = None, use_usda_api: bool = True):
        """Initialize with densities database."""
        if densities_file is None:
            densities_file = Path(__file__).parent.parent / "data" / "ingredient" / "densities_cleaned.tsv"
        
        self.logger = logging.getLogger(__name__)
        self.densities_df = self._load_densities(densities_file)
        self._build_search_index()
        
        # Initialize USDA API for fallback lookups
        self.usda_api = USDAFoodAPI() if use_usda_api else None
        self.usda_cache = {}  # Cache USDA results locally
        
    def _load_densities(self, file_path: Path) -> pd.DataFrame:
        """Load and prepare the densities database."""
        try:
            df = pd.read_csv(file_path, sep='\t')
            
            # Clean density values - handle ranges and convert to float
            df['density_g_ml'] = df['Density in g/ml (including mass and bulk density)'].apply(
                self._parse_density_value
            )
            
            # Create normalized search names
            df['search_name'] = df['Food name and description'].apply(self._normalize_ingredient_name)
            
            # Filter out rows with no valid density
            df = df[df['density_g_ml'].notna()]
            
            self.logger.info(f"Loaded {len(df)} ingredients with density data")
            return df
            
        except Exception as e:
            self.logger.error(f"Error loading densities file: {e}")
            return pd.DataFrame()
    
    def _parse_density_value(self, density_str: str) -> Optional[float]:
        """Parse density value, handling ranges and different formats."""
        if pd.isna(density_str):
            return None
            
        density_str = str(density_str).strip()
        
        # Handle ranges like "0.56-0.72"
        if '-' in density_str:
            try:
                parts = density_str.split('-')
                if len(parts) == 2:
                    low = float(parts[0])
                    high = float(parts[1])
                    return (low + high) / 2
            except ValueError:
                pass
        
        # Handle single values
        try:
            return float(density_str)
        except ValueError:
            return None
    
    def _normalize_ingredient_name(self, name: str) -> str:
        """Normalize ingredient name for matching."""
        if pd.isna(name):
            return ""
            
        # Convert to lowercase
        name = str(name).lower()
        
        # Remove common descriptors that don't affect density
        descriptors_to_remove = [
            r'\b(fresh|dried|frozen|canned|bottled|raw|cooked|boiled|steamed)\b',
            r'\b(organic|natural|pure)\b',
            r'\b(with|without|added|no)\s+\w+',
            r'\b(unsweetened|sweetened)\b',
            r'\s*\([^)]*\)',  # Remove parenthetical content
            r'\s*,.*$',       # Remove everything after first comma
        ]
        
        for pattern in descriptors_to_remove:
            name = re.sub(pattern, '', name)
        
        # Clean up extra spaces
        name = re.sub(r'\s+', ' ', name).strip()
        
        return name
    
    def _build_search_index(self):
        """Build search index for faster lookups."""
        if self.densities_df.empty:
            self.search_index = {}
            return
            
        self.search_index = {}
        
        for _, row in self.densities_df.iterrows():
            search_name = row['search_name']
            if search_name:
                # Add full name
                self.search_index[search_name] = row
                
                # Add individual words for partial matching
                words = search_name.split()
                for word in words:
                    if len(word) > 2:  # Skip very short words
                        if word not in self.search_index:
                            self.search_index[word] = []
                        if not isinstance(self.search_index[word], list):
                            self.search_index[word] = [self.search_index[word]]
                        self.search_index[word].append(row)
    
    def find_density(self, ingredient_name: str, threshold: float = 0.6) -> Optional[Dict[str, Any]]:
        """
        Find density for an ingredient name.
        
        Args:
            ingredient_name: Name of ingredient to look up
            threshold: Minimum similarity score for matching
            
        Returns:
            Dictionary with density info or None if not found
        """
        if not ingredient_name:
            return None
        
        # First try local database
        local_result = self._find_density_local(ingredient_name, threshold)
        if local_result:
            return local_result
        
        # If not found locally and USDA API is available, try USDA
        if self.usda_api:
            return self._find_density_usda(ingredient_name)
        
        return None
    
    def _find_density_local(self, ingredient_name: str, threshold: float = 0.6) -> Optional[Dict[str, Any]]:
        """Find density in local database."""
        if self.densities_df.empty:
            return None
            
        normalized_name = self._normalize_ingredient_name(ingredient_name)
        
        # Try exact match first
        if normalized_name in self.search_index:
            row = self.search_index[normalized_name]
            if not isinstance(row, list):
                return self._format_density_result(row, 1.0)
        
        # Try fuzzy matching
        best_match = None
        best_score = 0
        
        for search_name, row in self.search_index.items():
            if isinstance(row, list):
                continue  # Skip word-based entries for fuzzy matching
                
            similarity = SequenceMatcher(None, normalized_name, search_name).ratio()
            if similarity > best_score and similarity >= threshold:
                best_score = similarity
                best_match = row
        
        if best_match is not None:
            return self._format_density_result(best_match, best_score)
        
        # Try partial word matching
        words = normalized_name.split()
        for word in words:
            if word in self.search_index and isinstance(self.search_index[word], list):
                # Find best match among word matches
                for row in self.search_index[word]:
                    similarity = SequenceMatcher(None, normalized_name, row['search_name']).ratio()
                    if similarity > best_score and similarity >= threshold:
                        best_score = similarity
                        best_match = row
        
        if best_match is not None:
            return self._format_density_result(best_match, best_score)
        
        return None
    
    def _find_density_usda(self, ingredient_name: str) -> Optional[Dict[str, Any]]:
        """Find density using USDA API."""
        # Check USDA cache first
        if ingredient_name in self.usda_cache:
            return self.usda_cache[ingredient_name]
        
        self.logger.info(f"Querying USDA API for density: {ingredient_name}")
        
        try:
            density_info = self.usda_api.find_density_info(ingredient_name)
            
            # Cache the result (even if None)
            self.usda_cache[ingredient_name] = density_info
            
            if density_info:
                self.logger.info(f"Found USDA density {density_info['density_g_ml']:.3f} g/ml for {ingredient_name}")
            else:
                self.logger.debug(f"No USDA density found for {ingredient_name}")
            
            return density_info
            
        except Exception as e:
            self.logger.error(f"Error querying USDA API for {ingredient_name}: {e}")
            return None
    
    def _format_density_result(self, row: pd.Series, score: float) -> Dict[str, Any]:
        """Format density lookup result."""
        return {
            'name': row['Food name and description'],
            'category': row['category'],
            'density_g_ml': row['density_g_ml'],
            'specific_gravity': row.get('Specific gravity'),
            'source': row.get('BiblioID'),
            'match_score': score,
            'search_name': row['search_name']
        }
    
    def calculate_weight_from_volume(self, volume_ml: float, density_g_ml: float) -> float:
        """Calculate weight in grams from volume in ml and density."""
        return volume_ml * density_g_ml
    
    def calculate_volume_from_weight(self, weight_g: float, density_g_ml: float) -> float:
        """Calculate volume in ml from weight in grams and density."""
        return weight_g / density_g_ml
    
    def convert_volume_units_to_ml(self, quantity: float, unit: str) -> Optional[float]:
        """Convert volume units to milliliters."""
        unit = unit.lower().strip()
        
        conversions = {
            'ml': 1,
            'milliliter': 1,
            'milliliters': 1,
            'l': 1000,
            'liter': 1000,
            'liters': 1000,
            'litre': 1000,
            'litres': 1000,
            'cup': 236.588,
            'cups': 236.588,
            'tbsp': 14.787,
            'tablespoon': 14.787,
            'tablespoons': 14.787,
            'tsp': 4.929,
            'teaspoon': 4.929,
            'teaspoons': 4.929,
            'fl oz': 29.574,
            'fluid ounce': 29.574,
            'fluid ounces': 29.574,
            'pint': 473.176,
            'pints': 473.176,
            'quart': 946.353,
            'quarts': 946.353,
            'gallon': 3785.41,
            'gallons': 3785.41
        }
        
        return conversions.get(unit, None) * quantity if unit in conversions else None
    
    def get_ingredient_suggestions(self, partial_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get ingredient name suggestions for partial matches."""
        if not partial_name or self.densities_df.empty:
            return []
            
        normalized_partial = self._normalize_ingredient_name(partial_name)
        suggestions = []
        
        for _, row in self.densities_df.iterrows():
            search_name = row['search_name']
            if normalized_partial in search_name:
                suggestions.append({
                    'name': row['Food name and description'],
                    'category': row['category'],
                    'density_g_ml': row['density_g_ml']
                })
                
        return suggestions[:limit]