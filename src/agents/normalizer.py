"""
Normalizer Agent - Cleans and normalizes recipe data using LLM assistance
"""
import re
from typing import Dict, Any, List, Optional, Tuple
from ..models.recipe import Recipe, Ingredient, InstructionStep
from ..agents.base import BaseAgent, AgentResult
from ..agents.llm_integration import LLMManager
from config.settings import Settings

class NormalizerAgent(BaseAgent):
    """Agent responsible for cleaning and normalizing recipe data."""
    
    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.llm_manager = LLMManager(settings)
        self.common_ingredient_names = self._load_common_ingredients()
        self.cooking_verbs = self._load_cooking_verbs()
    
    def _load_common_ingredients(self) -> Dict[str, str]:
        """Load common ingredient name mappings for normalization."""
        return {
            # Vegetables
            'green onions': 'scallions',
            'spring onions': 'scallions',
            'roma tomatoes': 'plum tomatoes',
            'bell peppers': 'bell pepper',
            'sweet peppers': 'bell pepper',
            
            # Proteins
            'ground beef': 'ground beef',
            'hamburger': 'ground beef',
            'chicken breast': 'chicken breast',
            'boneless chicken breast': 'chicken breast',
            
            # Dairy
            'heavy cream': 'heavy cream',
            'heavy whipping cream': 'heavy cream',
            'half and half': 'half-and-half',
            
            # Spices & Seasonings
            'kosher salt': 'salt',
            'table salt': 'salt',
            'sea salt': 'salt',
            'black pepper': 'black pepper',
            'ground black pepper': 'black pepper',
            
            # Oils & Fats
            'vegetable oil': 'vegetable oil',
            'canola oil': 'vegetable oil',
            'olive oil': 'olive oil',
            'extra virgin olive oil': 'olive oil',
            
            # Flour & Grains
            'all-purpose flour': 'all-purpose flour',
            'plain flour': 'all-purpose flour',
            'white rice': 'white rice',
            'long-grain white rice': 'white rice',
        }
    
    def _load_cooking_verbs(self) -> List[str]:
        """Load common cooking verbs for instruction normalization."""
        return [
            'heat', 'cook', 'boil', 'simmer', 'fry', 'sauté', 'bake', 'roast', 'grill',
            'steam', 'poach', 'braise', 'stew', 'mix', 'stir', 'whisk', 'beat', 'fold',
            'chop', 'dice', 'slice', 'mince', 'julienne', 'grate', 'shred', 'peel',
            'season', 'marinate', 'chill', 'freeze', 'thaw', 'serve', 'garnish'
        ]
    
    def normalize(self, recipe: Recipe) -> AgentResult[Recipe]:
        """
        Normalize and clean recipe data.
        
        Args:
            recipe: Parsed recipe to normalize
            
        Returns:
            AgentResult with normalized Recipe object
        """
        try:
            self.logger.info(f"Normalizing recipe: {recipe.title}")
            
            # Create a copy to avoid modifying original
            normalized_recipe = recipe.copy(deep=True)
            
            # Normalize ingredients
            if self.settings.processing.enable_ingredient_normalization:
                normalized_recipe.ingredients = self._normalize_ingredients(recipe.ingredients)
                normalized_recipe.add_processing_note("Ingredients normalized")
            
            # Normalize instructions
            if self.settings.processing.enable_instruction_enhancement:
                normalized_recipe.instructions = self._normalize_instructions(recipe.instructions)
                normalized_recipe.add_processing_note("Instructions normalized")
            
            # Clean and normalize text fields
            normalized_recipe.title = self._clean_text(recipe.title)
            normalized_recipe.description = self._clean_text(recipe.description) if recipe.description else None
            
            # Normalize servings
            normalized_recipe.servings = self._normalize_servings(recipe.servings)
            
            # Validate and fix timing
            normalized_recipe = self._validate_timing(normalized_recipe)
            
            # Calculate quality score
            quality_score = self._calculate_quality_score(normalized_recipe)
            normalized_recipe.confidence_score = quality_score
            
            # Add normalization metadata
            normalized_recipe.add_processing_note(f"Normalization completed with quality score: {quality_score:.2f}")
            
            self.logger.info(f"Recipe normalized successfully. Quality score: {quality_score:.2f}")
            
            return AgentResult(
                success=True,
                data=normalized_recipe,
                metadata={
                    'quality_score': quality_score,
                    'ingredients_normalized': len(normalized_recipe.ingredients),
                    'instructions_normalized': len(normalized_recipe.instructions)
                }
            )
            
        except Exception as e:
            return self._handle_error(e, f"Error normalizing recipe")
    
    def _normalize_ingredients(self, ingredients: List[Ingredient]) -> List[Ingredient]:
        """Normalize ingredient names and measurements."""
        normalized = []
        
        for ingredient in ingredients:
            try:
                # Normalize ingredient name
                normalized_name = self._normalize_ingredient_name(ingredient.name)
                
                # Clean preparation text
                normalized_preparation = self._clean_text(ingredient.preparation) if ingredient.preparation else None
                
                # Normalize units
                normalized_unit = self._normalize_unit(ingredient.unit)
                
                # Create normalized ingredient
                normalized_ingredient = ingredient.copy(deep=True)
                normalized_ingredient.name = normalized_name
                normalized_ingredient.preparation = normalized_preparation
                normalized_ingredient.unit = normalized_unit
                
                # Enhanced normalization with LLM for complex cases
                if self._needs_llm_normalization(ingredient):
                    enhanced = self._enhance_ingredient_with_llm(normalized_ingredient)
                    if enhanced:
                        normalized_ingredient = enhanced
                
                normalized.append(normalized_ingredient)
                
            except Exception as e:
                self.logger.warning(f"Failed to normalize ingredient '{ingredient.name}': {e}")
                normalized.append(ingredient)
        
        return normalized
    
    def _normalize_ingredient_name(self, name: str) -> str:
        """Normalize ingredient name using mappings and rules."""
        if not name:
            return name
        
        # Clean the name
        cleaned = self._clean_text(name).lower()
        
        # Check common mappings
        if cleaned in self.common_ingredient_names:
            return self.common_ingredient_names[cleaned]
        
        # Apply normalization rules
        # Remove brand names in parentheses
        cleaned = re.sub(r'\([^)]*brand[^)]*\)', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\([^)]*®[^)]*\)', '', cleaned)
        
        # Remove excessive adjectives
        cleaned = re.sub(r'\b(fresh|dried|organic|free-range|grass-fed)\b', '', cleaned)
        
        # Normalize plurals
        if cleaned.endswith('es'):
            singular = cleaned[:-2]
            if singular in self.common_ingredient_names:
                return self.common_ingredient_names[singular]
        elif cleaned.endswith('s') and not cleaned.endswith('ss'):
            singular = cleaned[:-1]
            if singular in self.common_ingredient_names:
                return self.common_ingredient_names[singular]
        
        return cleaned.strip()
    
    def _normalize_unit(self, unit: str) -> str:
        """Normalize measurement units."""
        if not unit:
            return unit
        
        unit = unit.lower().strip()
        
        # Common unit mappings
        unit_mappings = {
            'cups': 'cup',
            'c': 'cup',
            'tablespoons': 'tbsp',
            'tablespoon': 'tbsp',
            'T': 'tbsp',
            'teaspoons': 'tsp',
            'teaspoon': 'tsp',
            't': 'tsp',
            'pounds': 'lb',
            'pound': 'lb',
            'lbs': 'lb',
            'ounces': 'oz',
            'ounce': 'oz',
            'fluid ounces': 'fl oz',
            'fluid ounce': 'fl oz',
            'pints': 'pint',
            'quarts': 'quart',
            'gallons': 'gallon',
            'liters': 'l',
            'liter': 'l',
            'milliliters': 'ml',
            'milliliter': 'ml',
            'grams': 'g',
            'gram': 'g',
            'kilograms': 'kg',
            'kilogram': 'kg',
        }
        
        return unit_mappings.get(unit, unit)
    
    def _normalize_instructions(self, instructions: List[InstructionStep]) -> List[InstructionStep]:
        """Normalize instruction text and structure."""
        normalized = []
        
        for instruction in instructions:
            try:
                # Clean instruction text
                normalized_text = self._clean_instruction_text(instruction.instruction)
                
                # Create normalized instruction
                normalized_instruction = instruction.copy(deep=True)
                normalized_instruction.instruction = normalized_text
                
                # Enhance with LLM if needed
                if self._needs_instruction_enhancement(instruction):
                    enhanced = self._enhance_instruction_with_llm(normalized_instruction)
                    if enhanced:
                        normalized_instruction = enhanced
                
                normalized.append(normalized_instruction)
                
            except Exception as e:
                self.logger.warning(f"Failed to normalize instruction: {e}")
                normalized.append(instruction)
        
        return normalized
    
    def _clean_instruction_text(self, text: str) -> str:
        """Clean and normalize instruction text."""
        if not text:
            return text
        
        # Clean basic text
        cleaned = self._clean_text(text)
        
        # Normalize cooking verbs to standard forms
        for verb in self.cooking_verbs:
            # Make sure cooking verbs are in standard form
            pattern = r'\b' + re.escape(verb) + r'(?:ing|ed|s)?\b'
            cleaned = re.sub(pattern, verb, cleaned, flags=re.IGNORECASE)
        
        # Fix common instruction patterns
        cleaned = re.sub(r'\btil\b', 'until', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\bthru\b', 'through', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\b&\b', 'and', cleaned)
        
        return cleaned
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text fields."""
        if not text:
            return text
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Fix common encoding issues
        text = text.replace('â€™', "'")
        text = text.replace('â€œ', '"')
        text = text.replace('â€\x9d', '"')
        
        # Normalize quotes
        text = re.sub(r'["â€œâ€\x9d]', '"', text)
        text = re.sub(r"['â€™]", "'", text)
        
        return text.strip()
    
    def _normalize_servings(self, servings: Optional[int]) -> Optional[int]:
        """Normalize servings to reasonable range."""
        if servings is None:
            return None
        
        # Ensure servings is in reasonable range
        if servings < 1:
            return 1
        elif servings > 100:
            return 100
        
        return servings
    
    def _validate_timing(self, recipe: Recipe) -> Recipe:
        """Validate and fix recipe timing."""
        # Ensure total_time is consistent
        if recipe.prep_time and recipe.cook_time:
            calculated_total = recipe.prep_time + recipe.cook_time
            if not recipe.total_time or abs(recipe.total_time - calculated_total) > 5:
                recipe.total_time = calculated_total
                recipe.add_processing_note("Total time recalculated")
        
        # Validate reasonable timing
        if recipe.total_time and recipe.total_time > 24 * 60:  # More than 24 hours
            self.logger.warning(f"Total time seems excessive: {recipe.total_time} minutes")
        
        return recipe
    
    def _needs_llm_normalization(self, ingredient: Ingredient) -> bool:
        """Check if ingredient needs LLM-based normalization."""
        # Use LLM for complex ingredients with low confidence
        if ingredient.confidence and ingredient.confidence < 0.8:
            return True
        
        # Use LLM for ingredients with complex preparation
        if ingredient.preparation and len(ingredient.preparation) > 50:
            return True
        
        # Use LLM for ingredients with unclear names
        if len(ingredient.name.split()) > 4:
            return True
        
        return False
    
    def _needs_instruction_enhancement(self, instruction: InstructionStep) -> bool:
        """Check if instruction needs LLM enhancement."""
        # Enhance instructions that are very long or complex
        if len(instruction.instruction) > 200:
            return True
        
        # Enhance instructions with unclear timing
        if not instruction.time_minutes and any(word in instruction.instruction.lower() 
                                                for word in ['cook', 'bake', 'simmer', 'boil']):
            return True
        
        return False
    
    def _enhance_ingredient_with_llm(self, ingredient: Ingredient) -> Optional[Ingredient]:
        """Use LLM to enhance ingredient normalization."""
        prompt = f"""
        Normalize this ingredient information:
        
        Original: "{ingredient.original_text}"
        Current name: "{ingredient.name}"
        Current preparation: "{ingredient.preparation or 'None'}"
        
        Please provide normalized information in JSON format:
        {{
            "name": "standardized ingredient name",
            "preparation": "cleaned preparation method or null",
            "notes": "any additional notes or null"
        }}
        
        Rules:
        - Use common, standardized ingredient names
        - Remove brand names
        - Simplify preparation descriptions
        - Return only valid JSON
        """
        
        try:
            response = self.llm_manager.generate(prompt, max_tokens=200)
            
            import json
            enhanced_data = json.loads(response)
            
            # Update ingredient with enhanced data
            enhanced_ingredient = ingredient.copy(deep=True)
            enhanced_ingredient.name = enhanced_data.get('name', ingredient.name)
            enhanced_ingredient.preparation = enhanced_data.get('preparation', ingredient.preparation)
            if enhanced_data.get('notes'):
                enhanced_ingredient.notes = enhanced_data['notes']
            
            return enhanced_ingredient
            
        except Exception as e:
            self.logger.debug(f"LLM ingredient enhancement failed: {e}")
            return None
    
    def _enhance_instruction_with_llm(self, instruction: InstructionStep) -> Optional[InstructionStep]:
        """Use LLM to enhance instruction normalization."""
        prompt = f"""
        Enhance this cooking instruction:
        
        Original: "{instruction.instruction}"
        
        Please provide enhanced information in JSON format:
        {{
            "instruction": "cleaned and improved instruction text",
            "estimated_time_minutes": integer or null,
            "key_techniques": ["technique1", "technique2"] or []
        }}
        
        Rules:
        - Clean up grammar and clarity
        - Estimate time if cooking/baking involved
        - Identify key cooking techniques
        - Return only valid JSON
        """
        
        try:
            response = self.llm_manager.generate(prompt, max_tokens=300)
            
            import json
            enhanced_data = json.loads(response)
            
            # Update instruction with enhanced data
            enhanced_instruction = instruction.copy(deep=True)
            enhanced_instruction.instruction = enhanced_data.get('instruction', instruction.instruction)
            
            if enhanced_data.get('estimated_time_minutes'):
                enhanced_instruction.time_minutes = enhanced_data['estimated_time_minutes']
            
            if enhanced_data.get('key_techniques'):
                enhanced_instruction.techniques = enhanced_data['key_techniques']
            
            return enhanced_instruction
            
        except Exception as e:
            self.logger.debug(f"LLM instruction enhancement failed: {e}")
            return None
    
    def _calculate_quality_score(self, recipe: Recipe) -> float:
        """Calculate quality score for normalized recipe."""
        score = 0.0
        max_score = 1.0
        
        # Title quality (10%)
        if recipe.title and len(recipe.title) > 5:
            score += 0.1
        
        # Description quality (10%)
        if recipe.description and len(recipe.description) > 20:
            score += 0.1
        
        # Ingredients quality (30%)
        if recipe.ingredients:
            ingredient_score = 0.0
            for ingredient in recipe.ingredients:
                if ingredient.name and len(ingredient.name) > 2:
                    ingredient_score += 0.5
                if ingredient.quantity is not None:
                    ingredient_score += 0.3
                if ingredient.unit:
                    ingredient_score += 0.2
            
            ingredient_score = min(ingredient_score / len(recipe.ingredients), 1.0)
            score += ingredient_score * 0.3
        
        # Instructions quality (30%)
        if recipe.instructions:
            instruction_score = 0.0
            for instruction in recipe.instructions:
                if instruction.instruction and len(instruction.instruction) > 10:
                    instruction_score += 0.7
                if instruction.time_minutes:
                    instruction_score += 0.2
                if instruction.equipment:
                    instruction_score += 0.1
            
            instruction_score = min(instruction_score / len(recipe.instructions), 1.0)
            score += instruction_score * 0.3
        
        # Metadata quality (20%)
        metadata_score = 0.0
        if recipe.prep_time:
            metadata_score += 0.2
        if recipe.cook_time:
            metadata_score += 0.2
        if recipe.servings:
            metadata_score += 0.2
        if recipe.difficulty:
            metadata_score += 0.2
        if recipe.cuisine:
            metadata_score += 0.2
        
        score += metadata_score * 0.2
        
        return min(score, max_score)
    
    def process(self, recipe: Recipe) -> AgentResult[Recipe]:
        """Process method required by BaseAgent."""
        return self.normalize(recipe)