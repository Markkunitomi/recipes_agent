"""
Converter Agent - Handles unit conversions for recipes
"""
from typing import Dict, Any, List, Optional, Union
from models.recipe import Recipe, Ingredient
from models.conversion import UnitConverter, ConversionRequest, ConversionResult
from agents.base import BaseAgent, AgentResult
from agents.llm_integration import LLMManager
from config.settings import Settings

class ConverterAgent(BaseAgent):
    """Agent responsible for converting recipe units between metric, imperial, and weight."""
    
    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.llm_manager = LLMManager(settings)
        self.unit_converter = UnitConverter()
        self.conversion_cache = {}
    
    def convert(self, recipe: Recipe, target_system: str = "preferred") -> AgentResult[Recipe]:
        """
        Convert recipe units to target measurement system.
        
        Args:
            recipe: Recipe to convert
            target_system: "metric", "imperial", "weight", or "preferred" (uses settings)
            
        Returns:
            AgentResult with converted Recipe object
        """
        try:
            self.logger.info(f"Converting recipe units: {recipe.title}")
            
            # Determine target system
            if target_system == "preferred":
                target_system = self._determine_preferred_system()
            
            # Create converted recipe copy
            converted_recipe = recipe.copy(deep=True)
            
            # Convert ingredients
            conversion_results = []
            for i, ingredient in enumerate(converted_recipe.ingredients):
                if ingredient.quantity is not None and ingredient.unit:
                    result = self._convert_ingredient(ingredient, target_system)
                    if result:
                        converted_recipe.ingredients[i] = result.ingredient
                        conversion_results.append(result)
            
            # Convert temperatures in instructions
            self._convert_instruction_temperatures(converted_recipe, target_system)
            
            # Add conversion notes
            converted_recipe.add_processing_note(f"Units converted to {target_system} system")
            if conversion_results:
                approx_count = sum(1 for r in conversion_results if r.is_approximation)
                if approx_count > 0:
                    converted_recipe.add_processing_note(f"{approx_count} conversions are approximations")
            
            self.logger.info(f"Converted {len(conversion_results)} ingredients to {target_system}")
            
            return AgentResult(
                success=True,
                data=converted_recipe,
                metadata={
                    'target_system': target_system,
                    'conversions_made': len(conversion_results),
                    'approximations': sum(1 for r in conversion_results if r.is_approximation)
                }
            )
            
        except Exception as e:
            return self._handle_error(e, f"Error converting recipe units")
    
    def _determine_preferred_system(self) -> str:
        """Determine preferred measurement system from settings."""
        # Use settings to determine preference
        if hasattr(self.settings.processing, 'preferred_measurement_system'):
            return self.settings.processing.preferred_measurement_system
        
        # Default logic based on units
        preferred_volume = self.settings.processing.preferred_volume_unit
        if preferred_volume in ['ml', 'l']:
            return 'metric'
        elif preferred_volume in ['cup', 'tbsp', 'tsp']:
            return 'imperial'
        else:
            return 'metric'  # Default to metric
    
    def _convert_ingredient(self, ingredient: Ingredient, target_system: str) -> Optional['IngredientConversionResult']:
        """Convert a single ingredient to target system."""
        try:
            # Cache key for conversion
            cache_key = f"{ingredient.quantity}_{ingredient.unit}_{ingredient.name}_{target_system}"
            if cache_key in self.conversion_cache:
                cached_result = self.conversion_cache[cache_key]
                return IngredientConversionResult(
                    ingredient=self._apply_conversion_to_ingredient(ingredient, cached_result),
                    conversion_result=cached_result,
                    is_approximation=cached_result.is_approximation
                )
            
            # Determine best conversion approach
            conversion_result = None
            
            if target_system == "metric":
                conversion_result = self._convert_to_metric(ingredient)
            elif target_system == "imperial":
                conversion_result = self._convert_to_imperial(ingredient)
            elif target_system == "weight":
                conversion_result = self._convert_to_weight(ingredient)
            
            if conversion_result:
                # Cache the result
                self.conversion_cache[cache_key] = conversion_result
                
                # Apply conversion to ingredient
                converted_ingredient = self._apply_conversion_to_ingredient(ingredient, conversion_result)
                
                return IngredientConversionResult(
                    ingredient=converted_ingredient,
                    conversion_result=conversion_result,
                    is_approximation=conversion_result.is_approximation
                )
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Failed to convert ingredient '{ingredient.name}': {e}")
            return None
    
    def _convert_to_metric(self, ingredient: Ingredient) -> Optional[ConversionResult]:
        """Convert ingredient to metric units."""
        if not ingredient.quantity or not ingredient.unit:
            return None
        
        unit = ingredient.unit.lower()
        
        # Volume conversions to ml/l
        if unit in ['cup', 'tbsp', 'tsp', 'fl oz', 'pint', 'quart', 'gallon']:
            result = self.unit_converter.convert_volume(ingredient.quantity, unit, 'ml')
            
            # Convert to liters if quantity is large
            if result.converted_quantity >= 1000:
                result = self.unit_converter.convert_volume(ingredient.quantity, unit, 'l')
            
            return result
        
        # Weight conversions to g/kg
        elif unit in ['oz', 'lb']:
            result = self.unit_converter.convert_weight(ingredient.quantity, unit, 'g')
            
            # Convert to kg if quantity is large
            if result.converted_quantity >= 1000:
                result = self.unit_converter.convert_weight(ingredient.quantity, unit, 'kg')
            
            return result
        
        # Try volume to weight conversion for metric
        elif unit in ['cup', 'tbsp', 'tsp'] and ingredient.name:
            result = self.unit_converter.volume_to_weight(ingredient.quantity, unit, ingredient.name)
            if result:
                # Convert to kg if quantity is large
                if result.converted_quantity >= 1000:
                    kg_result = self.unit_converter.convert_weight(result.converted_quantity, 'g', 'kg')
                    result.converted_quantity = kg_result.converted_quantity
                    result.converted_unit = 'kg'
                return result
        
        return None
    
    def _convert_to_imperial(self, ingredient: Ingredient) -> Optional[ConversionResult]:
        """Convert ingredient to imperial units."""
        if not ingredient.quantity or not ingredient.unit:
            return None
        
        unit = ingredient.unit.lower()
        
        # Volume conversions to imperial
        if unit in ['ml', 'l']:
            # Choose best imperial unit based on quantity
            if unit == 'ml':
                if ingredient.quantity <= 15:
                    return self.unit_converter.convert_volume(ingredient.quantity, unit, 'tsp')
                elif ingredient.quantity <= 60:
                    return self.unit_converter.convert_volume(ingredient.quantity, unit, 'tbsp')
                else:
                    return self.unit_converter.convert_volume(ingredient.quantity, unit, 'cup')
            else:  # liters
                return self.unit_converter.convert_volume(ingredient.quantity, unit, 'cup')
        
        # Weight conversions to imperial
        elif unit in ['g', 'kg']:
            if unit == 'g' and ingredient.quantity < 454:
                return self.unit_converter.convert_weight(ingredient.quantity, unit, 'oz')
            else:
                return self.unit_converter.convert_weight(ingredient.quantity, unit, 'lb')
        
        # Try weight to volume conversion for imperial
        elif unit in ['g', 'kg'] and ingredient.name:
            result = self.unit_converter.weight_to_volume(ingredient.quantity, unit, ingredient.name)
            if result and result.converted_unit == 'ml':
                # Convert ml to appropriate imperial unit
                if result.converted_quantity <= 15:
                    imperial_result = self.unit_converter.convert_volume(result.converted_quantity, 'ml', 'tsp')
                elif result.converted_quantity <= 60:
                    imperial_result = self.unit_converter.convert_volume(result.converted_quantity, 'ml', 'tbsp')
                else:
                    imperial_result = self.unit_converter.convert_volume(result.converted_quantity, 'ml', 'cup')
                
                result.converted_quantity = imperial_result.converted_quantity
                result.converted_unit = imperial_result.converted_unit
                return result
        
        return None
    
    def _convert_to_weight(self, ingredient: Ingredient) -> Optional[ConversionResult]:
        """Convert ingredient to weight units."""
        if not ingredient.quantity or not ingredient.unit or not ingredient.name:
            return None
        
        unit = ingredient.unit.lower()
        
        # Volume to weight conversion
        if unit in ['cup', 'tbsp', 'tsp', 'ml', 'l', 'fl oz']:
            result = self.unit_converter.volume_to_weight(ingredient.quantity, unit, ingredient.name)
            if result:
                # Choose appropriate weight unit
                if result.converted_quantity >= 1000:
                    kg_result = self.unit_converter.convert_weight(result.converted_quantity, 'g', 'kg')
                    result.converted_quantity = kg_result.converted_quantity
                    result.converted_unit = 'kg'
                return result
        
        # Already weight units - just normalize
        elif unit in ['oz', 'lb']:
            if unit == 'oz' and ingredient.quantity >= 16:
                return self.unit_converter.convert_weight(ingredient.quantity, unit, 'lb')
            elif unit == 'lb':
                return self.unit_converter.convert_weight(ingredient.quantity, unit, 'kg')
        
        return None
    
    def _apply_conversion_to_ingredient(self, ingredient: Ingredient, conversion: ConversionResult) -> Ingredient:
        """Apply conversion result to ingredient."""
        converted = ingredient.copy(deep=True)
        
        # Update primary unit
        converted.quantity = conversion.converted_quantity
        converted.unit = conversion.converted_unit
        
        # Store original values
        converted.metric_quantity = conversion.converted_quantity if 'metric' in str(conversion.converted_unit) else None
        converted.metric_unit = conversion.converted_unit if 'metric' in str(conversion.converted_unit) else None
        
        converted.imperial_quantity = conversion.converted_quantity if conversion.converted_unit in ['cup', 'tbsp', 'tsp', 'oz', 'lb'] else None
        converted.imperial_unit = conversion.converted_unit if conversion.converted_unit in ['cup', 'tbsp', 'tsp', 'oz', 'lb'] else None
        
        converted.weight_quantity = conversion.converted_quantity if conversion.converted_unit in ['g', 'kg', 'oz', 'lb'] else None
        converted.weight_unit = conversion.converted_unit if conversion.converted_unit in ['g', 'kg', 'oz', 'lb'] else None
        
        # Add notes about approximation
        if conversion.is_approximation:
            note = f"Converted from {conversion.original_quantity} {conversion.original_unit}"
            if conversion.notes:
                note += f" ({conversion.notes})"
            converted.notes = note
        
        return converted
    
    def _convert_instruction_temperatures(self, recipe: Recipe, target_system: str):
        """Convert temperatures in cooking instructions."""
        for instruction in recipe.instructions:
            if instruction.temperature:
                if target_system == "metric" and instruction.temperature_unit == "F":
                    # Convert F to C
                    celsius = self.unit_converter.convert_temperature(
                        instruction.temperature, "F", "C"
                    )
                    instruction.temperature = celsius.converted_quantity
                    instruction.temperature_unit = "C"
                    
                elif target_system == "imperial" and instruction.temperature_unit == "C":
                    # Convert C to F
                    fahrenheit = self.unit_converter.convert_temperature(
                        instruction.temperature, "C", "F"
                    )
                    instruction.temperature = fahrenheit.converted_quantity
                    instruction.temperature_unit = "F"
    
    def convert_batch(self, recipes: List[Recipe], target_system: str = "preferred") -> AgentResult[List[Recipe]]:
        """Convert multiple recipes in batch."""
        try:
            converted_recipes = []
            failed_conversions = []
            
            for recipe in recipes:
                result = self.convert(recipe, target_system)
                if result.success:
                    converted_recipes.append(result.data)
                else:
                    failed_conversions.append(recipe.title)
                    self.logger.warning(f"Failed to convert recipe: {recipe.title}")
            
            return AgentResult(
                success=True,
                data=converted_recipes,
                metadata={
                    'total_recipes': len(recipes),
                    'successful_conversions': len(converted_recipes),
                    'failed_conversions': len(failed_conversions),
                    'target_system': target_system
                }
            )
            
        except Exception as e:
            return self._handle_error(e, "Error in batch conversion")
    
    def get_conversion_suggestions(self, ingredient: Ingredient) -> List[Dict[str, Any]]:
        """Get conversion suggestions for an ingredient."""
        suggestions = []
        
        if not ingredient.quantity or not ingredient.unit:
            return suggestions
        
        try:
            # Try different conversion targets
            targets = ['metric', 'imperial', 'weight']
            
            for target in targets:
                result = None
                if target == 'metric':
                    result = self._convert_to_metric(ingredient)
                elif target == 'imperial':
                    result = self._convert_to_imperial(ingredient)
                elif target == 'weight':
                    result = self._convert_to_weight(ingredient)
                
                if result:
                    suggestions.append({
                        'target_system': target,
                        'original': f"{ingredient.quantity} {ingredient.unit}",
                        'converted': f"{result.converted_quantity} {result.converted_unit}",
                        'is_approximation': result.is_approximation,
                        'notes': result.notes
                    })
        
        except Exception as e:
            self.logger.warning(f"Error getting conversion suggestions: {e}")
        
        return suggestions
    
    def process(self, recipe: Recipe, target_system: str = "preferred") -> AgentResult[Recipe]:
        """Process method required by BaseAgent."""
        return self.convert(recipe, target_system)

class IngredientConversionResult:
    """Result of ingredient conversion."""
    def __init__(self, ingredient: Ingredient, conversion_result: ConversionResult, is_approximation: bool = False):
        self.ingredient = ingredient
        self.conversion_result = conversion_result
        self.is_approximation = is_approximation