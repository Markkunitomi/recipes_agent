"""
Parser Agent - Structures raw recipe data using ML and LLM
"""
from typing import Dict, Any, List, Optional
import re
from ingredient_parser import parse_ingredient

from agents.base import BaseAgent, AgentResult
from agents.llm_integration import LLMManager
from config.settings import Settings
from models.recipe import Recipe, Ingredient, InstructionStep, ParsedIngredient, NutritionInfo
from models.recipe import DifficultyLevel, CuisineType
from models.conversion import smart_round
from utils.density_lookup import DensityLookup

class ParserAgent(BaseAgent):
    """Agent responsible for parsing and structuring recipe data."""
    
    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.llm_manager = LLMManager(settings)
        self.density_lookup = DensityLookup()
        self.difficulty_keywords = {
            'easy': ['easy', 'simple', 'quick', 'beginner', 'basic'],
            'medium': ['medium', 'intermediate', 'moderate'],
            'hard': ['hard', 'difficult', 'advanced', 'complex', 'challenging'],
            'expert': ['expert', 'professional', 'master', 'gourmet']
        }
    
    def parse(self, raw_data: Dict[str, Any]) -> AgentResult[Recipe]:
        """
        Parse raw scraped data into structured Recipe object.
        
        Args:
            raw_data: Raw recipe data from scraper
            
        Returns:
            AgentResult with parsed Recipe object
        """
        try:
            self.logger.info(f"Parsing recipe: {raw_data.get('title', 'Unknown')}")
            
            # Parse ingredients
            ingredients = self._parse_ingredients(raw_data.get('ingredients', []))
            
            # Parse instructions
            instructions = self._parse_instructions(raw_data.get('instructions', []))
            
            # Parse metadata
            metadata = self._parse_metadata(raw_data)
            
            # Create Recipe object
            recipe = Recipe(
                title=raw_data.get('title', 'Unknown Recipe'),
                description=raw_data.get('description'),
                url=raw_data.get('url'),
                image_url=raw_data.get('image_url'),
                
                # Timing
                prep_time=self._parse_time(raw_data.get('prep_time')),
                cook_time=self._parse_time(raw_data.get('cook_time')),
                total_time=self._parse_time(raw_data.get('total_time')),
                
                # Servings
                servings=self._parse_servings(raw_data.get('servings')),
                yield_amount=raw_data.get('yield_amount'),
                
                # Classification
                difficulty=metadata.get('difficulty'),
                cuisine=metadata.get('cuisine'),
                meal_type=metadata.get('meal_type', []),
                dietary_restrictions=metadata.get('dietary_restrictions', []),
                
                # Content
                ingredients=ingredients,
                instructions=instructions,
                
                # Additional info
                nutrition=self._parse_nutrition(raw_data.get('nutrition')),
                tags=metadata.get('tags', []),
                equipment_needed=metadata.get('equipment', []),
                
                # Metadata
                source=raw_data.get('url'),
                author=raw_data.get('author'),
                
                # Processing metadata
                processing_notes=[],
                confidence_score=self._calculate_confidence_score(ingredients, instructions)
            )
            
            self.logger.info(f"Successfully parsed recipe with {len(ingredients)} ingredients and {len(instructions)} steps")
            
            return AgentResult(
                success=True,
                data=recipe,
                metadata={
                    'ingredients_parsed': len(ingredients),
                    'instructions_parsed': len(instructions),
                    'confidence_score': recipe.confidence_score
                }
            )
            
        except Exception as e:
            return self._handle_error(e, f"Error parsing recipe data")
    
    def _parse_ingredients(self, raw_ingredients: List[str]) -> List[Ingredient]:
        """Parse ingredient strings into structured Ingredient objects."""
        ingredients = []
        
        for i, ingredient_text in enumerate(raw_ingredients):
            if not ingredient_text or not ingredient_text.strip():
                continue
                
            try:
                # Use ingredient-parser library for ML-based parsing
                parsed = parse_ingredient(ingredient_text)
                
                # Extract structured data
                name = self._extract_ingredient_name(parsed.name)
                quantity, unit = self._extract_ingredient_amount(parsed.amount)
                preparation = self._extract_ingredient_text(parsed.preparation)
                notes = self._extract_ingredient_text(parsed.comment)
                
                # Convert to our Ingredient model
                ingredient = Ingredient(
                    name=name or "Unknown",
                    quantity=quantity,
                    unit=unit,
                    preparation=preparation,
                    notes=notes,
                    original_text=ingredient_text,
                    confidence=self._calculate_ingredient_confidence(parsed)
                )
                
                # Additional processing
                ingredient.optional = self._is_optional_ingredient(ingredient_text)
                ingredient.alternatives = self._extract_alternatives(ingredient_text)
                
                # Density lookup and metric/weight calculations
                self._enhance_ingredient_with_density(ingredient)
                
                ingredients.append(ingredient)
                
            except Exception as e:
                self.logger.warning(f"Failed to parse ingredient '{ingredient_text}': {e}")
                # Create basic ingredient as fallback
                ingredient = Ingredient(
                    name=ingredient_text,
                    original_text=ingredient_text,
                    confidence=0.5
                )
                ingredients.append(ingredient)
        
        return ingredients
    
    def _parse_instructions(self, raw_instructions: List[str]) -> List[InstructionStep]:
        """Parse instruction strings into structured InstructionStep objects."""
        instructions = []
        
        for i, instruction_text in enumerate(raw_instructions):
            if not instruction_text or not instruction_text.strip():
                continue
            
            try:
                # Use LLM to enhance instruction parsing
                enhanced_instruction = self._enhance_instruction_with_llm(instruction_text)
                
                step = InstructionStep(
                    step_number=i + 1,
                    instruction=instruction_text,
                    time_minutes=enhanced_instruction.get('time_minutes'),
                    temperature=enhanced_instruction.get('temperature'),
                    temperature_unit=enhanced_instruction.get('temperature_unit', 'F'),
                    equipment=enhanced_instruction.get('equipment', []),
                    ingredients_used=enhanced_instruction.get('ingredients_used', []),
                    techniques=enhanced_instruction.get('techniques', []),
                    notes=enhanced_instruction.get('notes')
                )
                
                instructions.append(step)
                
            except Exception as e:
                self.logger.warning(f"Failed to parse instruction '{instruction_text}': {e}")
                # Create basic instruction as fallback
                step = InstructionStep(
                    step_number=i + 1,
                    instruction=instruction_text
                )
                instructions.append(step)
        
        return instructions
    
    def _enhance_instruction_with_llm(self, instruction: str) -> Dict[str, Any]:
        """Use LLM to extract structured information from instruction text."""
        prompt = f"""
        Analyze this cooking instruction and extract structured information:
        
        Instruction: "{instruction}"
        
        Please extract and return in JSON format:
        - time_minutes: estimated time for this step (integer, null if none)
        - temperature: cooking temperature (integer, null if none)
        - temperature_unit: "F" or "C" (default "F")
        - equipment: list of equipment/tools needed (list of strings)
        - ingredients_used: list of ingredients mentioned (list of strings)
        - techniques: list of cooking techniques used (list of strings)
        - notes: any additional notes or tips (string, null if none)
        
        Return only valid JSON, no additional text.
        """
        
        try:
            response = self.llm_manager.generate(prompt, max_tokens=300)
            
            # Parse JSON response
            import json
            enhanced_data = json.loads(response)
            
            # Validate and clean the data
            return {
                'time_minutes': enhanced_data.get('time_minutes'),
                'temperature': enhanced_data.get('temperature'),
                'temperature_unit': enhanced_data.get('temperature_unit', 'F'),
                'equipment': enhanced_data.get('equipment', []),
                'ingredients_used': enhanced_data.get('ingredients_used', []),
                'techniques': enhanced_data.get('techniques', []),
                'notes': enhanced_data.get('notes')
            }
            
        except Exception as e:
            self.logger.debug(f"LLM enhancement failed for instruction: {e}")
            return {}
    
    def _parse_metadata(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse recipe metadata like difficulty, cuisine, etc."""
        metadata = {}
        
        # Parse difficulty
        difficulty = self._determine_difficulty(raw_data)
        if difficulty:
            metadata['difficulty'] = difficulty
        
        # Parse cuisine
        cuisine = self._determine_cuisine(raw_data)
        if cuisine:
            metadata['cuisine'] = cuisine
        
        # Parse meal type
        meal_type = self._determine_meal_type(raw_data)
        if meal_type:
            metadata['meal_type'] = meal_type
        
        # Parse dietary restrictions
        dietary_restrictions = self._determine_dietary_restrictions(raw_data)
        if dietary_restrictions:
            metadata['dietary_restrictions'] = dietary_restrictions
        
        # Parse tags
        tags = self._extract_tags(raw_data)
        if tags:
            metadata['tags'] = tags
        
        # Parse equipment
        equipment = self._extract_equipment(raw_data)
        if equipment:
            metadata['equipment'] = equipment
        
        return metadata
    
    def _determine_difficulty(self, raw_data: Dict[str, Any]) -> Optional[DifficultyLevel]:
        """Determine recipe difficulty level."""
        text_to_analyze = " ".join([
            raw_data.get('title', ''),
            raw_data.get('description', ''),
            " ".join(raw_data.get('instructions', []))
        ]).lower()
        
        for difficulty, keywords in self.difficulty_keywords.items():
            if any(keyword in text_to_analyze for keyword in keywords):
                return DifficultyLevel(difficulty)
        
        # Use instruction complexity as fallback
        instructions = raw_data.get('instructions', [])
        if len(instructions) > 15:
            return DifficultyLevel.HARD
        elif len(instructions) > 10:
            return DifficultyLevel.MEDIUM
        else:
            return DifficultyLevel.EASY
    
    def _determine_cuisine(self, raw_data: Dict[str, Any]) -> Optional[CuisineType]:
        """Determine cuisine type."""
        cuisine_keywords = {
            'italian': ['italian', 'pasta', 'pizza', 'risotto', 'marinara', 'parmesan'],
            'mexican': ['mexican', 'tacos', 'salsa', 'guacamole', 'tortilla', 'cilantro'],
            'asian': ['asian', 'soy sauce', 'sesame', 'ginger', 'rice vinegar', 'miso'],
            'french': ['french', 'butter', 'wine', 'herbs', 'cream', 'roux'],
            'american': ['american', 'barbecue', 'burger', 'fries', 'ranch'],
            'mediterranean': ['mediterranean', 'olive oil', 'lemon', 'herbs', 'feta'],
            'indian': ['indian', 'curry', 'turmeric', 'cumin', 'coriander', 'garam masala']
        }
        
        # Check explicit cuisine field first
        if raw_data.get('cuisine'):
            cuisine_text = raw_data['cuisine'].lower()
            for cuisine_type in CuisineType:
                if cuisine_type.value in cuisine_text:
                    return cuisine_type
        
        # Analyze recipe text
        text_to_analyze = " ".join([
            raw_data.get('title', ''),
            raw_data.get('description', ''),
            " ".join(raw_data.get('ingredients', []))
        ]).lower()
        
        for cuisine, keywords in cuisine_keywords.items():
            if any(keyword in text_to_analyze for keyword in keywords):
                return CuisineType(cuisine)
        
        return CuisineType.OTHER
    
    def _determine_meal_type(self, raw_data: Dict[str, Any]) -> List[str]:
        """Determine meal type (breakfast, lunch, dinner, etc.)."""
        meal_keywords = {
            'breakfast': ['breakfast', 'morning', 'cereal', 'eggs', 'pancakes', 'toast'],
            'lunch': ['lunch', 'sandwich', 'salad', 'soup'],
            'dinner': ['dinner', 'supper', 'main course', 'entree'],
            'dessert': ['dessert', 'cake', 'cookie', 'sweet', 'chocolate'],
            'snack': ['snack', 'appetizer', 'finger food'],
            'brunch': ['brunch']
        }
        
        text_to_analyze = " ".join([
            raw_data.get('title', ''),
            raw_data.get('description', ''),
            raw_data.get('category', '')
        ]).lower()
        
        meal_types = []
        for meal_type, keywords in meal_keywords.items():
            if any(keyword in text_to_analyze for keyword in keywords):
                meal_types.append(meal_type)
        
        return meal_types
    
    def _determine_dietary_restrictions(self, raw_data: Dict[str, Any]) -> List[str]:
        """Determine dietary restrictions."""
        restriction_keywords = {
            'vegetarian': ['vegetarian', 'veggie'],
            'vegan': ['vegan'],
            'gluten-free': ['gluten-free', 'gluten free'],
            'dairy-free': ['dairy-free', 'dairy free', 'lactose free'],
            'keto': ['keto', 'ketogenic', 'low carb'],
            'paleo': ['paleo', 'paleolithic'],
            'low-sodium': ['low sodium', 'low-sodium'],
            'sugar-free': ['sugar-free', 'sugar free', 'no sugar']
        }
        
        text_to_analyze = " ".join([
            raw_data.get('title', ''),
            raw_data.get('description', ''),
            raw_data.get('category', ''),
            " ".join(raw_data.get('tags', []))
        ]).lower()
        
        restrictions = []
        for restriction, keywords in restriction_keywords.items():
            if any(keyword in text_to_analyze for keyword in keywords):
                restrictions.append(restriction)
        
        return restrictions
    
    def _extract_tags(self, raw_data: Dict[str, Any]) -> List[str]:
        """Extract tags from recipe data."""
        tags = []
        
        # Add existing tags
        if raw_data.get('tags'):
            tags.extend(raw_data['tags'])
        
        # Add category as tag
        if raw_data.get('category'):
            tags.append(raw_data['category'])
        
        # Add cuisine as tag
        if raw_data.get('cuisine'):
            tags.append(raw_data['cuisine'])
        
        # Clean and deduplicate
        tags = [tag.strip().lower() for tag in tags if tag and tag.strip()]
        return list(set(tags))
    
    def _extract_equipment(self, raw_data: Dict[str, Any]) -> List[str]:
        """Extract equipment from instructions."""
        equipment_keywords = [
            'oven', 'stove', 'pan', 'pot', 'skillet', 'bowl', 'mixer', 'whisk',
            'spatula', 'knife', 'cutting board', 'baking sheet', 'casserole dish',
            'blender', 'food processor', 'grill', 'microwave', 'slow cooker',
            'pressure cooker', 'dutch oven', 'saucepan', 'stockpot'
        ]
        
        instructions_text = " ".join(raw_data.get('instructions', [])).lower()
        
        equipment = []
        for keyword in equipment_keywords:
            if keyword in instructions_text:
                equipment.append(keyword)
        
        return equipment
    
    def _parse_nutrition(self, raw_nutrition: Any) -> Optional[NutritionInfo]:
        """Parse nutrition information."""
        if not raw_nutrition:
            return None
        
        try:
            if isinstance(raw_nutrition, dict):
                return NutritionInfo(
                    calories=raw_nutrition.get('calories'),
                    protein_g=raw_nutrition.get('protein'),
                    carbs_g=raw_nutrition.get('carbs'),
                    fat_g=raw_nutrition.get('fat'),
                    fiber_g=raw_nutrition.get('fiber'),
                    sugar_g=raw_nutrition.get('sugar'),
                    sodium_mg=raw_nutrition.get('sodium')
                )
        except Exception as e:
            self.logger.warning(f"Failed to parse nutrition data: {e}")
        
        return None
    
    def _parse_time(self, time_str: Any) -> Optional[int]:
        """Parse time string to minutes."""
        if not time_str:
            return None
        
        if isinstance(time_str, int):
            return time_str
        
        if isinstance(time_str, str):
            # Extract numbers from time string
            numbers = re.findall(r'\d+', time_str)
            if numbers:
                time_value = int(numbers[0])
                # Convert hours to minutes if needed
                if 'hour' in time_str.lower():
                    time_value *= 60
                return time_value
        
        return None
    
    def _parse_servings(self, servings_str: Any) -> Optional[int]:
        """Parse servings string to integer."""
        if not servings_str:
            return None
        
        if isinstance(servings_str, int):
            return servings_str
        
        if isinstance(servings_str, str):
            # Extract first number from servings string
            numbers = re.findall(r'\d+', servings_str)
            if numbers:
                return int(numbers[0])
        
        return None
    
    def _parse_quantity(self, quantity_str: Any) -> Optional[float]:
        """Parse quantity string to float."""
        if not quantity_str:
            return None
        
        if isinstance(quantity_str, (int, float)):
            return float(quantity_str)
        
        if isinstance(quantity_str, str):
            # Handle fractions
            if '/' in quantity_str:
                parts = quantity_str.split('/')
                if len(parts) == 2:
                    try:
                        return float(parts[0]) / float(parts[1])
                    except (ValueError, ZeroDivisionError):
                        pass
            
            # Extract first number
            numbers = re.findall(r'\d+\.?\d*', quantity_str)
            if numbers:
                return float(numbers[0])
        
        return None
    
    def _is_optional_ingredient(self, ingredient_text: str) -> bool:
        """Check if ingredient is optional."""
        optional_keywords = ['optional', 'to taste', 'if desired', 'garnish']
        return any(keyword in ingredient_text.lower() for keyword in optional_keywords)
    
    def _extract_alternatives(self, ingredient_text: str) -> List[str]:
        """Extract alternative ingredients."""
        alternatives = []
        
        # Look for "or" alternatives
        if ' or ' in ingredient_text.lower():
            parts = ingredient_text.lower().split(' or ')
            if len(parts) > 1:
                alternatives.append(parts[1].strip())
        
        return alternatives
    
    def _extract_ingredient_name(self, name_field) -> Optional[str]:
        """Extract ingredient name from parsed field."""
        if not name_field:
            return None
        
        if isinstance(name_field, list) and len(name_field) > 0:
            first_item = name_field[0]
            if hasattr(first_item, 'text'):
                return first_item.text
            elif isinstance(first_item, str):
                return first_item
        
        if hasattr(name_field, 'text'):
            return name_field.text
        
        if isinstance(name_field, str):
            return name_field
        
        return str(name_field) if name_field else None
    
    def _extract_ingredient_amount(self, amount_field) -> tuple[Optional[float], Optional[str]]:
        """Extract quantity and unit from parsed amount field."""
        if not amount_field:
            return None, None
        
        if isinstance(amount_field, list) and len(amount_field) > 0:
            first_amount = amount_field[0]
            
            # Extract quantity
            quantity = None
            if hasattr(first_amount, 'quantity'):
                try:
                    # Handle Fraction objects
                    if hasattr(first_amount.quantity, 'numerator') and hasattr(first_amount.quantity, 'denominator'):
                        quantity = float(first_amount.quantity.numerator) / float(first_amount.quantity.denominator)
                    else:
                        quantity = float(first_amount.quantity)
                except (ValueError, TypeError, AttributeError):
                    pass
            
            # Extract unit
            unit = None
            if hasattr(first_amount, 'unit'):
                unit_obj = first_amount.unit
                if hasattr(unit_obj, 'name'):
                    unit = unit_obj.name
                elif hasattr(unit_obj, 'symbol'):
                    unit = unit_obj.symbol
                else:
                    unit = str(unit_obj)
            
            return quantity, unit
        
        return None, None
    
    def _extract_ingredient_text(self, text_field) -> Optional[str]:
        """Extract text from parsed ingredient field."""
        if not text_field:
            return None
        
        if isinstance(text_field, str):
            return text_field
        
        if isinstance(text_field, list) and len(text_field) > 0:
            first_item = text_field[0]
            if hasattr(first_item, 'text'):
                return first_item.text
            elif isinstance(first_item, str):
                return first_item
            else:
                return str(first_item)
        
        if hasattr(text_field, 'text'):
            return text_field.text
        
        return str(text_field) if text_field else None
    
    def _calculate_ingredient_confidence(self, parsed_ingredient) -> float:
        """Calculate confidence score for parsed ingredient."""
        confidences = []
        
        # Name confidence
        if parsed_ingredient.name and isinstance(parsed_ingredient.name, list):
            for name_item in parsed_ingredient.name:
                if hasattr(name_item, 'confidence'):
                    confidences.append(name_item.confidence)
        
        # Amount confidence
        if parsed_ingredient.amount and isinstance(parsed_ingredient.amount, list):
            for amount_item in parsed_ingredient.amount:
                if hasattr(amount_item, 'confidence'):
                    confidences.append(amount_item.confidence)
        
        # Return average confidence or 0.5 as fallback
        return sum(confidences) / len(confidences) if confidences else 0.5
    
    def _calculate_confidence_score(self, ingredients: List[Ingredient], instructions: List[InstructionStep]) -> float:
        """Calculate overall confidence score for the recipe."""
        scores = []
        
        # Ingredient confidence
        ingredient_confidences = [ing.confidence for ing in ingredients if ing.confidence]
        if ingredient_confidences:
            scores.append(sum(ingredient_confidences) / len(ingredient_confidences))
        
        # Recipe completeness
        completeness_score = 0.0
        if ingredients:
            completeness_score += 0.3
        if instructions:
            completeness_score += 0.3
        if len(instructions) >= 3:
            completeness_score += 0.2
        if len(ingredients) >= 3:
            completeness_score += 0.2
        
        scores.append(completeness_score)
        
        return sum(scores) / len(scores) if scores else 0.5
    
    def _enhance_ingredient_with_density(self, ingredient: Ingredient):
        """Enhance ingredient with density lookup and metric/weight calculations."""
        if not ingredient.name or not ingredient.quantity:
            return
        
        # Look up density for this ingredient
        density_info = self.density_lookup.find_density(ingredient.name)
        
        if not density_info:
            self.logger.debug(f"No density found for ingredient: {ingredient.name}")
            return
        
        density_g_ml = density_info['density_g_ml']
        self.logger.debug(f"Found density {density_g_ml} g/ml for {ingredient.name} (match: {density_info['match_score']:.2f})")
        
        # Convert volume units to metric and calculate weight
        if ingredient.unit and self._is_volume_unit(ingredient.unit):
            # Convert to milliliters
            volume_ml = self.density_lookup.convert_volume_units_to_ml(ingredient.quantity, ingredient.unit)
            
            if volume_ml:
                # Calculate weight in grams
                weight_g = self.density_lookup.calculate_weight_from_volume(volume_ml, density_g_ml)
                
                # Set metric volume (prefer liters for large volumes)
                if volume_ml >= 1000:
                    ingredient.metric_quantity = smart_round(volume_ml / 1000, "l")
                    ingredient.metric_unit = "l"
                else:
                    ingredient.metric_quantity = smart_round(volume_ml, "ml")
                    ingredient.metric_unit = "ml"
                
                # Set weight
                if weight_g >= 1000:
                    ingredient.weight_quantity = smart_round(weight_g / 1000, "kg")
                    ingredient.weight_unit = "kg"
                else:
                    ingredient.weight_quantity = smart_round(weight_g, "g")
                    ingredient.weight_unit = "g"
                
                self.logger.debug(f"Calculated: {volume_ml}ml = {weight_g}g for {ingredient.name}")
        
        # Convert weight units to metric and calculate volume
        elif ingredient.unit and self._is_weight_unit(ingredient.unit):
            # Convert to grams
            weight_g = self._convert_weight_to_grams(ingredient.quantity, ingredient.unit)
            
            if weight_g:
                # Calculate volume in milliliters
                volume_ml = self.density_lookup.calculate_volume_from_weight(weight_g, density_g_ml)
                
                # Set metric volume (prefer liters for large volumes)
                if volume_ml >= 1000:
                    ingredient.metric_quantity = smart_round(volume_ml / 1000, "l")
                    ingredient.metric_unit = "l"
                else:
                    ingredient.metric_quantity = smart_round(volume_ml, "ml")
                    ingredient.metric_unit = "ml"
                
                # Set metric weight (prefer kg for large weights)
                if weight_g >= 1000:
                    ingredient.weight_quantity = smart_round(weight_g / 1000, "kg")
                    ingredient.weight_unit = "kg"
                else:
                    ingredient.weight_quantity = smart_round(weight_g, "g")
                    ingredient.weight_unit = "g"
                
                self.logger.debug(f"Calculated: {weight_g}g = {volume_ml}ml for {ingredient.name}")
    
    def _is_volume_unit(self, unit: str) -> bool:
        """Check if unit is a volume measurement."""
        volume_units = ['ml', 'l', 'cup', 'cups', 'tbsp', 'tsp', 'fl oz', 'pint', 'quart', 'gallon',
                       'milliliter', 'milliliters', 'liter', 'liters', 'litre', 'litres',
                       'tablespoon', 'tablespoons', 'teaspoon', 'teaspoons', 'fluid ounce', 'fluid ounces']
        return unit.lower().strip() in volume_units
    
    def _is_weight_unit(self, unit: str) -> bool:
        """Check if unit is a weight measurement."""
        weight_units = ['g', 'kg', 'oz', 'lb', 'gram', 'grams', 'kilogram', 'kilograms', 
                       'ounce', 'ounces', 'pound', 'pounds']
        return unit.lower().strip() in weight_units
    
    def _convert_weight_to_grams(self, quantity: float, unit: str) -> Optional[float]:
        """Convert weight units to grams."""
        unit = unit.lower().strip()
        
        conversions = {
            'g': 1,
            'gram': 1,
            'grams': 1,
            'kg': 1000,
            'kilogram': 1000,
            'kilograms': 1000,
            'oz': 28.3495,
            'ounce': 28.3495,
            'ounces': 28.3495,
            'lb': 453.592,
            'pound': 453.592,
            'pounds': 453.592
        }
        
        return conversions.get(unit, None) * quantity if unit in conversions else None
    
    def process(self, raw_data: Dict[str, Any]) -> AgentResult[Recipe]:
        """Process method required by BaseAgent."""
        return self.parse(raw_data)