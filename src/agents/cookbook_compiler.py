"""
Cookbook Compilation Agent

This agent takes JSON recipes and their images and compiles them into a
properly formatted LaTeX cookbook, with validation and automatic formatting.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from jinja2 import Environment, FileSystemLoader

import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.models.recipe import Recipe
from config.settings import OutputSettings


@dataclass
class CookbookMetadata:
    """Metadata for the cookbook."""
    title: str = "Recipe Collection"
    author: str = "Chef"
    description: str = "A collection of delicious recipes"
    language: str = "english"


@dataclass
class RecipeValidationResult:
    """Result of recipe validation."""
    is_valid: bool
    estimated_pages: float
    issues: List[str]
    shortened_instructions: Optional[List[str]] = None


class CookbookCompilerAgent:
    """Agent for compiling JSON recipes into LaTeX cookbook format."""
    
    def __init__(self, settings: OutputSettings = None):
        self.settings = settings or OutputSettings()
        self.logger = self._setup_logger()
        
        # Setup Jinja2 environment for LaTeX templates
        template_dir = Path(__file__).parent.parent / "outputs" / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            variable_start_string='{{',
            variable_end_string='}}',
            block_start_string='{%',
            block_end_string='%}',
            comment_start_string='{#',
            comment_end_string='#}'
        )
        
        # Page estimation constants (rough estimates)
        self.chars_per_page = 2000  # Approximate characters per page
        self.lines_per_page = 50    # Approximate lines per page for ingredients/steps
        
    def _setup_logger(self):
        """Setup logger for the agent."""
        import logging
        logger = logging.getLogger("CookbookCompilerAgent")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def compile_cookbook(
        self,
        json_dir: Path,
        image_dir: Path,
        output_dir: Path,
        metadata: CookbookMetadata = None,
        max_pages_per_recipe: int = 1,
        auto_build: bool = True
    ) -> bool:
        """
        Compile a complete cookbook from JSON recipes and images.
        
        Args:
            json_dir: Directory containing JSON recipe files
            image_dir: Directory containing recipe images
            output_dir: Output directory for the cookbook
            metadata: Cookbook metadata
            max_pages_per_recipe: Maximum pages allowed per recipe
            auto_build: Whether to automatically build PDF
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.logger.info(f"Compiling cookbook from {json_dir}")
            
            metadata = metadata or CookbookMetadata()
            
            # Create output directory structure
            self._setup_cookbook_structure(output_dir)
            
            # Load and validate all recipes
            recipes = self._load_recipes(json_dir)
            validated_recipes = []
            
            for recipe in recipes:
                validation = self._validate_recipe_formatting(recipe, max_pages_per_recipe)
                if validation.is_valid:
                    validated_recipes.append((recipe, validation))
                    self.logger.info(f"✓ Recipe '{recipe.title}' validated ({validation.estimated_pages:.1f} pages)")
                else:
                    self.logger.warning(f"⚠ Recipe '{recipe.title}' needs optimization: {', '.join(validation.issues)}")
                    # Try to fix the recipe
                    fixed_recipe = self._fix_recipe_formatting(recipe, validation)
                    if fixed_recipe:
                        # Re-validate the fixed recipe
                        fixed_validation = self._validate_recipe_formatting(fixed_recipe, max_pages_per_recipe)
                        validated_recipes.append((fixed_recipe, fixed_validation))
                        self.logger.info(f"✓ Recipe '{recipe.title}' optimized ({fixed_validation.estimated_pages:.1f} pages)")
                    else:
                        self.logger.error(f"✗ Could not optimize recipe '{recipe.title}', skipping")
            
            # Copy and organize images
            self._organize_images(image_dir, output_dir / "images")
            
            # Create placeholder images for recipes that don't have images
            self._create_missing_recipe_images(validated_recipes, output_dir / "images")
            
            # Generate individual recipe LaTeX files
            self._generate_recipe_tex_files(validated_recipes, output_dir)
            
            # Generate main cookbook file
            self._generate_main_cookbook(validated_recipes, output_dir, metadata)
            
            # Copy cookbook class and supporting files
            self._copy_cookbook_resources(output_dir, metadata)
            
            # Build PDF if requested
            if auto_build:
                self._build_cookbook_pdf(output_dir)
            
            self.logger.info(f"✓ Cookbook compilation complete: {output_dir}")
            return True
            
        except Exception as e:
            self.logger.error(f"Cookbook compilation failed: {e}")
            return False
    
    def _setup_cookbook_structure(self, output_dir: Path):
        """Create the necessary directory structure for the cookbook."""
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "recipes").mkdir(exist_ok=True)
        (output_dir / "images").mkdir(exist_ok=True)
        (output_dir / "fonts").mkdir(exist_ok=True)
    
    def _load_recipes(self, json_dir: Path) -> List[Recipe]:
        """Load all JSON recipes from directory."""
        recipes = []
        
        for json_file in json_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    recipe_data = json.load(f)
                
                # Convert to Recipe object
                recipe = Recipe(**recipe_data)
                recipes.append(recipe)
                
            except Exception as e:
                self.logger.warning(f"Failed to load recipe from {json_file}: {e}")
        
        # Sort recipes alphabetically by title
        recipes.sort(key=lambda r: r.title.lower())
        return recipes
    
    def _sort_ingredients_by_type(self, ingredients: List[Any]) -> List[Any]:
        """Sort ingredients by type (meat, dairy, dry ingredients, etc.) without category labels."""
        
        def get_ingredient_category_priority(ingredient):
            """Return priority number for ingredient sorting (lower = appears first)."""
            name = getattr(ingredient, 'name', '').lower()
            
            # Meat and protein (1)
            if any(word in name for word in ['chicken', 'beef', 'pork', 'lamb', 'turkey', 'fish', 'salmon', 'tuna', 'shrimp', 'egg', 'eggs']):
                return 1
            
            # Dairy (2)
            if any(word in name for word in ['milk', 'cream', 'butter', 'cheese', 'yogurt', 'sour cream']):
                return 2
            
            # Produce/Fresh (3)
            if any(word in name for word in ['onion', 'garlic', 'tomato', 'pepper', 'mushroom', 'carrot', 'celery', 'lettuce', 'spinach', 'herbs', 'parsley', 'cilantro', 'basil', 'lemon', 'lime', 'apple', 'banana', 'berries', 'blueberries']):
                return 3
            
            # Dry ingredients/Pantry (4)
            if any(word in name for word in ['flour', 'sugar', 'salt', 'pepper', 'baking powder', 'baking soda', 'vanilla', 'oil', 'vinegar', 'mustard', 'soy sauce', 'honey', 'syrup']):
                return 4
            
            # Liquids (5)
            if any(word in name for word in ['water', 'broth', 'stock', 'wine', 'juice']):
                return 5
            
            # Default (6)
            return 6
        
        return sorted(ingredients, key=get_ingredient_category_priority)
    
    def _validate_recipe_formatting(self, recipe: Recipe, max_pages: int) -> RecipeValidationResult:
        """
        Validate if a recipe fits within the page constraints.
        
        Args:
            recipe: Recipe to validate
            max_pages: Maximum pages allowed
            
        Returns:
            RecipeValidationResult with validation details
        """
        issues = []
        
        # Use estimation only (PDF validation too unreliable with font issues)
        pages_count = self._estimate_recipe_pages(recipe)
        validation_method = "estimation"
        
        # Check if recipe exceeds page limit
        if pages_count > max_pages:
            issues.append(f"Recipe at {pages_count:.1f} pages via {validation_method} (limit: {max_pages})")
        
        # Check for overly long instructions
        long_instructions = [
            i for i, instr in enumerate(recipe.instructions) 
            if len(instr.instruction) > 120  # Lowered threshold
        ]
        if long_instructions:
            issues.append(f"Instructions {long_instructions} are too long")
        
        # Check for too many steps
        if len(recipe.instructions) > 8:
            issues.append(f"Too many steps: {len(recipe.instructions)} (recommended: ≤8)")
        
        # Check for missing essential data
        if not recipe.ingredients:
            issues.append("No ingredients found")
        
        if not recipe.instructions:
            issues.append("No instructions found")
        
        # Check for image availability
        if not recipe.image_url or recipe.image_url == "null":
            issues.append("No image available")
        
        return RecipeValidationResult(
            is_valid=len(issues) == 0,
            estimated_pages=pages_count,
            issues=issues
        )
    
    def _estimate_recipe_pages(self, recipe: Recipe) -> float:
        """Conservative algorithm to estimate how many pages a recipe will take."""
        
        # More conservative constants
        chars_per_page = 1200  # Smaller to be more conservative
        lines_per_page = 30    # Fewer lines per page assumption
        
        # Count title and metadata space
        title_space = 0.2  # More space for title/metadata
        
        # Count ingredients more conservatively
        ingredient_lines = len(recipe.ingredients)
        ingredient_chars = sum(len(self._format_ingredient_for_tex(ing)) for ing in recipe.ingredients)
        
        # Count instructions with conservative weighting
        instruction_lines = len(recipe.instructions)
        instruction_chars = sum(len(instr.instruction) for instr in recipe.instructions)
        
        # Be more aggressive about long instructions
        long_instruction_penalty = sum(
            1.0 for instr in recipe.instructions if len(instr.instruction) > 80
        )
        
        # Conservative space calculations
        ingredient_space = max(
            ingredient_chars / chars_per_page,
            ingredient_lines / lines_per_page
        ) * 1.3  # 30% overhead
        
        instruction_space = max(
            instruction_chars / chars_per_page,
            (instruction_lines + long_instruction_penalty) / lines_per_page
        ) * 1.4  # 40% overhead
        
        # Image space
        image_space = 0.3 if recipe.image_url and recipe.image_url != "null" else 0
        
        # Total page estimation with conservative bias
        total_space = title_space + ingredient_space + instruction_space + image_space
        
        # Higher formatting overhead
        formatting_overhead = 0.2
        estimated_pages = total_space + formatting_overhead
        
        # Conservative minimum - if >8 steps, assume needs optimization
        if len(recipe.instructions) > 8:
            estimated_pages = max(1.1, estimated_pages)
        
        return max(0.5, estimated_pages)
    
    def _fix_recipe_formatting(self, recipe: Recipe, validation: RecipeValidationResult) -> Optional[Recipe]:
        """
        Fix recipe formatting by applying aggressive optimization.
        
        Args:
            recipe: Recipe to fix
            validation: Validation result with issues
            
        Returns:
            Fixed recipe or None if unfixable
        """
        try:
            recipe_dict = recipe.model_dump()
            
            # Apply all optimization strategies aggressively
            if len(recipe.instructions) > 8 or any("too many steps" in issue.lower() for issue in validation.issues):
                # Step 1: Remove redundant steps
                recipe_dict['instructions'] = self._remove_redundant_steps(recipe_dict['instructions'])
                
                # Step 2: Combine related steps if still too many
                if len(recipe_dict['instructions']) > 8:
                    recipe_dict['instructions'] = self._combine_related_steps(recipe_dict['instructions'])
                
                # Step 3: Aggressive shortening of remaining steps
                if len(recipe_dict['instructions']) > 8:
                    recipe_dict['instructions'] = self._aggressive_instruction_shortening(recipe_dict['instructions'])
                
                # Step 4: Hard limit to 8 essential steps
                if len(recipe_dict['instructions']) > 8:
                    recipe_dict['instructions'] = recipe_dict['instructions'][:8]
            
            # Shorten long instructions
            if any("too long" in issue.lower() for issue in validation.issues):
                shortened_instructions = self._shorten_instructions([
                    type('obj', (object,), {'instruction': instr['instruction']})() 
                    for instr in recipe_dict['instructions']
                ])
                for i, shortened in enumerate(shortened_instructions):
                    if i < len(recipe_dict['instructions']):
                        recipe_dict['instructions'][i]['instruction'] = shortened
            
            # Add processing note
            if 'processing_notes' not in recipe_dict:
                recipe_dict['processing_notes'] = []
            recipe_dict['processing_notes'].append("Recipe optimized for cookbook formatting")
            
            return Recipe(**recipe_dict)
            
        except Exception as e:
            self.logger.error(f"Failed to fix recipe formatting: {e}")
            return None
    
    def _shorten_instructions(self, instructions: List[Any]) -> List[str]:
        """Intelligently shorten recipe instructions while preserving meaning."""
        shortened = []
        
        for instruction in instructions:
            text = instruction.instruction
            
            # If instruction is short enough, keep it
            if len(text) <= 150:
                shortened.append(text)
                continue
            
            # Apply intelligent shortening techniques
            original_text = text
            
            # 1. Remove redundant phrases and filler words
            redundant_phrases = {
                "Make sure to": "",
                "Be sure to": "",
                "It's important to": "",
                "Remember to": "",
                "You will want to": "",
                "You should": "",
                "Don't forget to": "",
                "Take care to": "",
                "Try to": "",
                "Carefully": "",
                "Gently": "",
                "slowly": "",
                "carefully": "",
                "very": "",
                "really": "",
                "quite": "",
                "rather": "",
                "pretty": "",
                "definitely": "",
                "absolutely": "",
                "completely": ""
            }
            
            for phrase, replacement in redundant_phrases.items():
                text = text.replace(phrase, replacement)
            
            # 2. Simplify cooking terminology with better context
            cooking_simplifications = {
                "until the mixture is": "until",
                "continuing to stir": "stirring",
                "making sure that": "ensuring",
                "in order to": "to",
                "at this point": "",
                "for best results": "",
                "for optimal flavor": "",
                "to ensure": "to",
                "to make sure": "to",
                "in a large": "in a",
                "in a medium": "in a", 
                "in a small": "in a",
                "heavy-bottomed": "",
                "non-stick": "",
                "over medium heat": "over medium",
                "over high heat": "over high",
                "over low heat": "over low",
                "degrees Fahrenheit": "°F",
                "degrees Celsius": "°C",
                "tablespoons": "tbsp",
                "tablespoon": "tbsp",
                "teaspoons": "tsp",
                "teaspoon": "tsp"
            }
            
            for phrase, replacement in cooking_simplifications.items():
                text = text.replace(phrase, replacement)
            
            # 3. Combine related actions
            if "," in text and len(text) > 150:
                # Try to keep the most important action (usually the first)
                main_action = text.split(',')[0].strip()
                if len(main_action) <= 150 and main_action:
                    text = main_action + "."
            
            # 4. Clean up extra spaces and punctuation
            text = ' '.join(text.split())  # Remove extra whitespace
            text = text.replace(" .", ".")
            text = text.replace(" ,", ",")
            
            # 5. Smart truncation with sentence preservation
            if len(text) > 150:
                # First try: Cut at sentence boundary
                sentences = text.split('. ')
                if len(sentences) > 1:
                    first_sentence = sentences[0]
                    if 50 <= len(first_sentence) <= 150:  # Reasonable length
                        text = first_sentence + '.'
                    else:
                        # Try combining first two sentences if first is too short
                        if len(first_sentence) < 50 and len(sentences) > 1:
                            combined = first_sentence + '. ' + sentences[1]
                            if len(combined) <= 150:
                                text = combined + '.'
                            else:
                                text = first_sentence + '.'
                        else:
                            text = first_sentence + '.'
                
                # Still too long? Try cutting at clause boundary
                if len(text) > 150:
                    clause_markers = [' and ', ' but ', ' or ', ' so ', ' then ', ' when ']
                    best_cut = None
                    for marker in clause_markers:
                        pos = text.find(marker)
                        if 50 <= pos <= 140:  # Good cutting position
                            best_cut = pos
                            break
                    
                    if best_cut:
                        text = text[:best_cut] + '.'
                    else:
                        # Last resort: Hard truncate at word boundary
                        words = text[:140].split()
                        text = ' '.join(words[:-1]) + '...'
            
            # Ensure the result is meaningful and properly formatted
            text = text.strip()
            if text and not text.endswith(('.', '!', '?', '...')):
                text += '.'
            
            # Capitalize first letter
            if text:
                text = text[0].upper() + text[1:]
            
            shortened.append(text)
        
        return shortened
    
    def _apply_length_optimization(self, recipe: Recipe, iteration: int) -> Optional[Recipe]:
        """Apply progressive length optimization strategies."""
        
        try:
            recipe_dict = recipe.model_dump()
            
            if iteration == 1:
                # First attempt: Shorten overly long instructions
                self.logger.info(f"Iteration {iteration}: Shortening long instructions")
                shortened_instructions = self._shorten_instructions(recipe.instructions)
                recipe_dict['instructions'] = [
                    {**instr.model_dump(), 'instruction': shortened_instructions[i]}
                    for i, instr in enumerate(recipe.instructions)
                ]
            
            elif iteration == 2:
                # Second attempt: Remove redundant steps
                self.logger.info(f"Iteration {iteration}: Removing redundant steps")
                recipe_dict['instructions'] = self._remove_redundant_steps(recipe_dict['instructions'])
            
            elif iteration == 3:
                # Third attempt: Combine related steps
                self.logger.info(f"Iteration {iteration}: Combining related steps")
                recipe_dict['instructions'] = self._combine_related_steps(recipe_dict['instructions'])
            
            elif iteration == 4:
                # Fourth attempt: Limit to essential steps only
                self.logger.info(f"Iteration {iteration}: Limiting to essential steps")
                max_steps = min(8, len(recipe_dict['instructions']))
                recipe_dict['instructions'] = recipe_dict['instructions'][:max_steps]
            
            elif iteration == 5:
                # Final attempt: Aggressive shortening
                self.logger.info(f"Iteration {iteration}: Aggressive shortening")
                recipe_dict['instructions'] = self._aggressive_instruction_shortening(recipe_dict['instructions'])
            
            # Add processing note
            if 'processing_notes' not in recipe_dict:
                recipe_dict['processing_notes'] = []
            recipe_dict['processing_notes'].append(f"Recipe optimized for cookbook formatting (iteration {iteration})")
            
            return Recipe(**recipe_dict)
            
        except Exception as e:
            self.logger.error(f"Failed to apply optimization iteration {iteration}: {e}")
            return None
    
    def _remove_redundant_steps(self, instructions: List[Dict]) -> List[Dict]:
        """Remove redundant or non-essential cooking steps."""
        
        redundant_patterns = [
            "enjoy", "serve immediately", "yum", "delicious", "taste and adjust",
            "season to taste", "let cool", "transfer to", "remove from heat",
            "but honestly", "sometimes i just", "serve with", "garnish with"
        ]
        
        filtered_instructions = []
        for instr in instructions:
            instruction_text = instr.get('instruction', '').lower()
            
            # Skip very short instructions
            if len(instruction_text.strip()) < 15:
                continue
            
            # Skip instructions that are just commentary or serving suggestions
            if any(pattern in instruction_text for pattern in redundant_patterns):
                continue
            
            # Skip pure commentary instructions
            if instruction_text in ["yum, yum, yum.", "but honestly, sometimes i just like to eat these plain.", "yum, yum, yum"]:
                continue
            
            # Skip serving instructions that aren't essential
            if instruction_text.startswith("serve with") or instruction_text.startswith("garnish with"):
                continue
            
            filtered_instructions.append(instr)
        
        return filtered_instructions
    
    def _combine_related_steps(self, instructions: List[Dict]) -> List[Dict]:
        """Combine related cooking steps into single instructions."""
        
        if len(instructions) <= 3:
            return instructions  # Don't combine if already short
        
        combined_instructions = []
        i = 0
        
        while i < len(instructions):
            current_instr = instructions[i]
            current_text = current_instr.get('instruction', '')
            
            # Look for opportunities to combine with next step
            if i + 1 < len(instructions):
                next_instr = instructions[i + 1]
                next_text = next_instr.get('instruction', '')
                
                # Combine if both are short and related
                if (len(current_text) < 80 and len(next_text) < 80 and 
                    len(current_text + " " + next_text) < 150):
                    
                    # Combine the instructions
                    combined_text = current_text.rstrip('.') + ", then " + next_text.lower()
                    combined_instr = current_instr.copy()
                    combined_instr['instruction'] = combined_text
                    combined_instructions.append(combined_instr)
                    i += 2  # Skip next instruction since we combined it
                    continue
            
            # Add instruction as-is if no combination
            combined_instructions.append(current_instr)
            i += 1
        
        return combined_instructions
    
    def _aggressive_instruction_shortening(self, instructions: List[Dict]) -> List[Dict]:
        """Apply aggressive shortening to all instructions."""
        
        shortened_instructions = []
        
        for instr in instructions:
            text = instr.get('instruction', '')
            
            # Apply aggressive shortening
            shortened_text = self._aggressive_shorten_text(text)
            
            if len(shortened_text) > 20:  # Keep if still meaningful
                shortened_instr = instr.copy()
                shortened_instr['instruction'] = shortened_text
                shortened_instructions.append(shortened_instr)
        
        return shortened_instructions
    
    def _aggressive_shorten_text(self, text: str) -> str:
        """Apply aggressive text shortening techniques."""
        
        # Remove all unnecessary words
        aggressive_removals = {
            "Make sure to": "",
            "Be sure to": "",
            "You will want to": "",
            "You should": "",
            "It's important to": "",
            "Remember to": "",
            "Don't forget to": "",
            "Take care to": "",
            "Carefully": "",
            "Gently": "",
            "slowly": "",
            "carefully": "",
            "very": "",
            "really": "",
            "quite": "",
            "rather": "",
            "pretty": "",
            "definitely": "",
            "absolutely": "",
            "completely": "",
            "until the mixture is": "until",
            "continuing to stir": "stirring",
            "making sure that": "ensuring",
            "in order to": "to",
            "at this point": "",
            "for best results": "",
            "for optimal flavor": "",
            "to ensure": "to",
            "to make sure": "to",
            "over medium heat": "over medium",
            "over high heat": "over high",
            "over low heat": "over low",
            "degrees Fahrenheit": "°F",
            "degrees Celsius": "°C",
            "tablespoons": "tbsp",
            "tablespoon": "tbsp",
            "teaspoons": "tsp",
            "teaspoon": "tsp",
            "minutes": "min",
            "minute": "min"
        }
        
        for phrase, replacement in aggressive_removals.items():
            text = text.replace(phrase, replacement)
        
        # Remove extra spaces
        text = ' '.join(text.split())
        
        # Take only the first sentence if still too long
        if len(text) > 100:
            sentences = text.split('. ')
            if len(sentences) > 1:
                text = sentences[0] + '.'
        
        # Final hard truncation if still too long
        if len(text) > 120:
            words = text[:110].split()
            text = ' '.join(words[:-1]) + '...'
        
        return text.strip()
    
    def _organize_images(self, source_image_dir: Path, target_image_dir: Path):
        """Copy and organize recipe images with better handling of missing images."""
        target_image_dir.mkdir(parents=True, exist_ok=True)
        
        if not source_image_dir.exists():
            self.logger.warning(f"Source image directory not found: {source_image_dir}")
            # Create a default placeholder image
            self._create_default_placeholder(target_image_dir)
            return
        
        # Track copied images for validation
        copied_images = set()
        
        # Copy all valid images
        for image_file in source_image_dir.iterdir():
            if image_file.is_file() and image_file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif']:
                try:
                    target_path = target_image_dir / image_file.name
                    
                    # Verify the image is valid before copying
                    if self._validate_image_file(image_file):
                        shutil.copy2(image_file, target_path)
                        copied_images.add(image_file.name)
                        self.logger.debug(f"Copied valid image: {image_file.name}")
                    else:
                        self.logger.warning(f"Invalid image file skipped: {image_file.name}")
                        
                except Exception as e:
                    self.logger.warning(f"Failed to copy image {image_file.name}: {e}")
            
            elif image_file.suffix.lower() == '.txt':
                # Handle text placeholder files by creating proper image placeholders
                self.logger.info(f"Converting text placeholder to image: {image_file.name}")
                recipe_name = image_file.stem
                self._create_recipe_placeholder_image(target_image_dir, recipe_name)
        
        # Create default placeholder if no images were copied
        if not copied_images:
            self._create_default_placeholder(target_image_dir)
            
        self.logger.info(f"Organized {len(copied_images)} images in cookbook")
    
    def _generate_recipe_tex_files(self, validated_recipes: List[Tuple[Recipe, RecipeValidationResult]], output_dir: Path):
        """Generate individual LaTeX files for each recipe."""
        recipes_dir = output_dir / "recipes"
        
        # Load the cookbook recipe template
        template = self.jinja_env.get_template("cookbook_recipe.tex")
        
        for recipe, validation in validated_recipes:
            try:
                # Format recipe data for LaTeX
                formatted_data = self._format_recipe_for_latex(recipe)
                
                # Render the template
                tex_content = template.render(**formatted_data)
                
                # Generate safe filename
                safe_title = self._make_safe_filename(recipe.title)
                tex_file = recipes_dir / f"{safe_title}.tex"
                
                # Write the file
                with open(tex_file, 'w', encoding='utf-8') as f:
                    f.write(tex_content)
                
                self.logger.debug(f"Generated LaTeX file: {tex_file.name}")
                
            except Exception as e:
                self.logger.error(f"Failed to generate LaTeX for recipe '{recipe.title}': {e}")
    
    def _format_recipe_for_latex(self, recipe: Recipe) -> Dict[str, Any]:
        """Format recipe data for LaTeX template."""
        
        # Sort and format ingredients
        sorted_ingredients = self._sort_ingredients_by_type(recipe.ingredients)
        formatted_ingredients = []
        for ingredient in sorted_ingredients:
            formatted_ingredients.append(self._format_ingredient_for_tex(ingredient))
        
        # Format instructions
        formatted_instructions = []
        for instruction in recipe.instructions:
            formatted_instructions.append(self._escape_latex(instruction.instruction))
        
        # Format times and servings
        servings_display = str(recipe.servings) if recipe.servings else ""
        prep_time_display = f"{recipe.prep_time} MIN" if recipe.prep_time else ""
        cook_time_display = f"{recipe.cook_time} MIN" if recipe.cook_time else ""
        
        # Handle image path with better fallback handling
        image_path = ""
        if recipe.image_url and recipe.image_url != "null":
            if recipe.image_url.startswith("./image/"):
                # Convert from JSON format to cookbook format
                image_filename = recipe.image_url.replace("./image/", "")
                image_path = f"./images/{image_filename}"
            elif recipe.image_url.startswith("./images/"):
                image_path = recipe.image_url
            else:
                # External URL, might need placeholder
                image_path = ""
        
        # If no image path found, try to use a recipe-specific placeholder
        if not image_path:
            safe_title = self._make_safe_filename(recipe.title)
            potential_placeholders = [
                f"./images/{safe_title}.jpg",
                f"./images/{safe_title}.png",
                "./images/default_placeholder.jpg"
            ]
            # Use the first potential placeholder (LaTeX will handle missing files gracefully)
            image_path = potential_placeholders[0]
        
        return {
            'escaped_title': self._escape_latex(recipe.title),
            'servings_display': servings_display,
            'prep_time_display': prep_time_display,
            'cook_time_display': cook_time_display,
            'image_path': image_path,
            'formatted_ingredients': formatted_ingredients,
            'formatted_instructions': formatted_instructions
        }
    
    def _format_ingredient_for_tex(self, ingredient: Any) -> str:
        """Format a single ingredient for LaTeX with both imperial and metric units."""
        parts = []
        
        # Get original imperial values
        original_quantity = getattr(ingredient, 'quantity', None)
        original_unit = getattr(ingredient, 'unit', None) or ""
        
        # Apply smart unit conversion for primary display
        converted_quantity, converted_unit = self._convert_to_preferred_units(ingredient)
        
        # Check if we should show dual units
        show_dual_units = (original_quantity and original_unit and 
                          original_unit.lower() in ['cup', 'cups', 'tbsp', 'tablespoon', 'tablespoons', 'tsp', 'teaspoon', 'teaspoons'] and
                          converted_unit not in ['cup', 'cups', 'tbsp', 'tsp'] and
                          converted_unit != original_unit)
        
        if show_dual_units:
            # Format original imperial quantity (primary)
            if original_quantity == int(original_quantity):
                parts.append(str(int(original_quantity)))
            else:
                if original_quantity < 1:
                    parts.append(self._format_fraction(original_quantity))
                else:
                    parts.append(f"{original_quantity:.1f}".rstrip('0').rstrip('.'))
            
            # Imperial unit (primary)
            parts.append(original_unit)
            
            # Add metric equivalent in parentheses
            if converted_quantity == int(converted_quantity):
                metric_qty = str(int(converted_quantity))
            else:
                metric_qty = f"{converted_quantity:.1f}".rstrip('0').rstrip('.')
            
            parts.append(f"({metric_qty} {converted_unit})")
        else:
            # Format converted quantity (when not showing dual units)
            if converted_quantity:
                if converted_quantity == int(converted_quantity):
                    parts.append(str(int(converted_quantity)))
                else:
                    # Format decimal quantities nicely
                    if converted_quantity < 1:
                        # Handle fractions for small quantities
                        parts.append(self._format_fraction(converted_quantity))
                    else:
                        # Round to reasonable precision
                        parts.append(f"{converted_quantity:.1f}".rstrip('0').rstrip('.'))
            
            # Primary unit (converted)
            if converted_unit:
                parts.append(converted_unit)
        
        # Name
        if hasattr(ingredient, 'name') and ingredient.name:
            parts.append(ingredient.name)
        
        # Preparation
        if hasattr(ingredient, 'preparation') and ingredient.preparation:
            parts.append(f"({ingredient.preparation})")
        
        result = " ".join(parts)
        return self._escape_latex(result)
    
    def _escape_latex(self, text: str) -> str:
        """Escape special LaTeX characters in text."""
        if not text:
            return ""
        
        # Define LaTeX special characters and their escaped versions
        latex_escapes = {
            '&': r'\&',
            '%': r'\%',
            '$': r'\$',
            '#': r'\#',
            '^': r'\textasciicircum{}',
            '_': r'\_',
            '{': r'\{',
            '}': r'\}',
            '~': r'\textasciitilde{}',
            '\\': r'\textbackslash{}'
        }
        
        for char, escape in latex_escapes.items():
            text = text.replace(char, escape)
        
        return text
    
    def _generate_main_cookbook(self, validated_recipes: List[Tuple[Recipe, RecipeValidationResult]], output_dir: Path, metadata: CookbookMetadata):
        """Generate the main cookbook LaTeX file."""
        
        # Create input statements for each recipe
        recipe_inputs = []
        for recipe, _ in validated_recipes:
            safe_title = self._make_safe_filename(recipe.title)
            recipe_inputs.append(f"\\input{{recipes/{safe_title}}}")
        
        # Generate main.tex content
        main_content = f"""\\documentclass{{recipebook}}

\\settitle{{{self._escape_latex(metadata.title)}}}
\\setauthor{{{self._escape_latex(metadata.author)}}}

\\begin{{document}}
\\input{{titlepage}}
\\customtableofcontents

{chr(10).join(recipe_inputs)}

\\end{{document}}
"""
        
        # Write main.tex
        with open(output_dir / "main.tex", 'w', encoding='utf-8') as f:
            f.write(main_content)
        
        # Generate titlepage.tex
        titlepage_content = f"""\\begin{{titlepage}}
\\centering
\\vspace*{{2cm}}

{{\\Huge\\textbf{{{self._escape_latex(metadata.title)}}}}}

\\vspace{{1cm}}

{{\\Large by {self._escape_latex(metadata.author)}}}

\\vspace{{2cm}}

{{\\large {self._escape_latex(metadata.description)}}}

\\vfill

{{\\small Compiled on \\today}}

\\end{{titlepage}}
"""
        
        with open(output_dir / "titlepage.tex", 'w', encoding='utf-8') as f:
            f.write(titlepage_content)
    
    def _copy_cookbook_resources(self, output_dir: Path, metadata: CookbookMetadata):
        """Copy cookbook class file and other resources."""
        
        # Find existing cookbook resources
        source_cookbook_dir = None
        for existing_dir in [
            Path("output/cookbook"),
            Path("output/latex/cookbook"),
            Path(__file__).parent.parent.parent / "output" / "cookbook"
        ]:
            if existing_dir.exists() and (existing_dir / "recipebook.cls").exists():
                source_cookbook_dir = existing_dir
                break
        
        if source_cookbook_dir:
            # Copy recipebook.cls
            shutil.copy2(source_cookbook_dir / "recipebook.cls", output_dir / "recipebook.cls")
            
            # Copy or create recipebook.cfg with custom metadata
            self._create_recipebook_config(output_dir, metadata)
            
            # Copy recipebook-lang.sty if it exists
            if (source_cookbook_dir / "recipebook-lang.sty").exists():
                shutil.copy2(source_cookbook_dir / "recipebook-lang.sty", output_dir / "recipebook-lang.sty")
            
            # Copy fonts if they exist
            source_fonts = source_cookbook_dir / "fonts"
            if source_fonts.exists():
                target_fonts = output_dir / "fonts"
                if target_fonts.exists():
                    shutil.rmtree(target_fonts)
                shutil.copytree(source_fonts, target_fonts)
        else:
            # No existing cookbook resources found - try to download them
            self.logger.info("No existing cookbook resources found, downloading LaTeX class files...")
            self._download_cookbook_class_files(output_dir, metadata)
    
    def _download_cookbook_class_files(self, output_dir: Path, metadata: CookbookMetadata):
        """Download LaTeX cookbook class files from itakurah repository or create fallbacks."""
        try:
            # Try to download from itakurah repository
            self._copy_itakurah_files(output_dir)
            
            # Always create/update the config file with custom metadata
            self._create_recipebook_config(output_dir, metadata)
            
        except Exception as e:
            self.logger.warning(f"Failed to download itakurah files: {e}")
            # Fall back to creating minimal class files
            self._create_fallback_class_files(output_dir, metadata)
    
    def _copy_itakurah_files(self, output_dir: Path):
        """Copy necessary files from itakurah repository."""
        import tempfile
        import subprocess
        
        # Clone itakurah repo to temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            repo_path = temp_path / "LaTeX-Cookbook"
            
            self.logger.info("Downloading itakurah/LaTeX-Cookbook files...")
            result = subprocess.run([
                "git", "clone", 
                "https://github.com/itakurah/LaTeX-Cookbook.git",
                str(repo_path)
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                raise Exception(f"Git clone failed: {result.stderr}")
            
            # Copy necessary files
            files_to_copy = [
                "recipebook.cls",
                "recipebook-lang.sty", 
                "titlepage.tex"
            ]
            
            for filename in files_to_copy:
                source_file = repo_path / filename
                if source_file.exists():
                    shutil.copy2(source_file, output_dir / filename)
                    self.logger.info(f"Copied {filename}")
            
            # Copy fonts directory
            source_fonts = repo_path / "fonts"
            target_fonts = output_dir / "fonts"
            if source_fonts.exists():
                if target_fonts.exists():
                    shutil.rmtree(target_fonts)
                shutil.copytree(source_fonts, target_fonts)
                self.logger.info("Copied fonts directory")
            
            self.logger.info("Successfully downloaded itakurah cookbook files")
    
    def _create_fallback_class_files(self, output_dir: Path, metadata: CookbookMetadata):
        """Create minimal LaTeX class files when itakurah files are unavailable."""
        self.logger.info("Creating fallback LaTeX class files...")
        
        # Create minimal recipebook.cls
        class_content = """\\NeedsTeXFormat{LaTeX2e}
\\ProvidesClass{recipebook}[2025/01/01 Simple Recipe Book Class]

% Load base class
\\LoadClass[11pt,a4paper]{book}

% Required packages
\\RequirePackage[utf8]{inputenc}
\\RequirePackage[T1]{fontenc}
\\RequirePackage{geometry}
\\RequirePackage{graphicx}
\\RequirePackage{xcolor}
\\RequirePackage{fancyhdr}
\\RequirePackage{titlesec}
\\RequirePackage{enumitem}

% Page setup
\\geometry{margin=2cm}

% Colors
\\definecolor{primarycolor}{RGB}{139, 69, 19}

% Recipe environment
\\newenvironment{recipe}[1]{%
    \\section{#1}
}{%
    \\vspace{1em}
}

% Ingredients environment
\\newenvironment{ingredients}{%
    \\subsection*{Ingredients}
    \\begin{itemize}[leftmargin=1em]
}{%
    \\end{itemize}
}

% Instructions environment
\\newenvironment{instructions}{%
    \\subsection*{Instructions}
    \\begin{enumerate}[leftmargin=1em]
}{%
    \\end{enumerate}
}

% Recipe info command
\\newcommand{\\recipeinfo}[4]{%
    \\begin{tabular}{ll}
    Prep Time: & #1 \\\\
    Cook Time: & #2 \\\\
    Total Time: & #3 \\\\
    Servings: & #4
    \\end{tabular}
    \\vspace{1em}
}

% Recipe image command
\\newcommand{\\recipeimage}[1]{%
    \\includegraphics[width=\\textwidth,height=6cm,keepaspectratio]{#1}
}
"""
        
        with open(output_dir / "recipebook.cls", 'w', encoding='utf-8') as f:
            f.write(class_content)
        
        # Create minimal recipebook-lang.sty
        lang_content = """\\NeedsTeXFormat{LaTeX2e}
\\ProvidesPackage{recipebook-lang}[2025/01/01 Recipe Book Language Support]

% English labels (default)
\\newcommand{\\recipebooklang}{english}
"""
        
        with open(output_dir / "recipebook-lang.sty", 'w', encoding='utf-8') as f:
            f.write(lang_content)
        
        # Create simple titlepage.tex
        titlepage_content = f"""\\begin{{titlepage}}
\\centering
\\vspace*{{2cm}}

{{\\Huge\\bfseries {self._escape_latex(metadata.title)}}}

\\vspace{{1cm}}

{{\\Large by {self._escape_latex(metadata.author)}}}

\\vspace{{2cm}}

{{\\large {self._escape_latex(metadata.description)}}}

\\vfill

{{\\today}}

\\end{{titlepage}}
"""
        
        with open(output_dir / "titlepage.tex", 'w', encoding='utf-8') as f:
            f.write(titlepage_content)
        
        self.logger.info("Created fallback LaTeX class files")
    
    def _create_recipebook_config(self, output_dir: Path, metadata: CookbookMetadata):
        """Create recipebook.cfg with custom metadata."""
        
        config_content = f"""% recipebook.cfg
\\ProvidesFile{{recipebook.cfg}}[2025/06/01 User config for recipebook]

% Set the main language of the cookbook.
% Change this to 'german', 'french', 'spanish', etc. to localize labels and babel.
\\newcommand{{\\recipebooklang}}{{{metadata.language}}}

% Set the title of your cookbook.
\\renewcommand{{\\title}}{{{self._escape_latex(metadata.title)}}}

% Set the author name of your cookbook.
\\renewcommand{{\\author}}{{{self._escape_latex(metadata.author)}}}

% PDF metadata fields used by hyperref package

% Subject of the PDF document.
\\newcommand{{\\pdfsubject}}{{{self._escape_latex(metadata.description)}}}

% Keywords for the PDF document to improve searchability.
\\newcommand{{\\pdfkeywords}}{{cooking, recipes, cookbook}}

% PDF producer software metadata.
\\newcommand{{\\pdfproducer}}{{XeLaTeX}}

% PDF creator software metadata.
\\newcommand{{\\pdfcreator}}{{XeLaTeX}}
"""
        
        with open(output_dir / "recipebook.cfg", 'w', encoding='utf-8') as f:
            f.write(config_content)
    
    def _build_cookbook_pdf(self, output_dir: Path) -> bool:
        """Build the cookbook PDF using XeLaTeX."""
        try:
            self.logger.info("Building cookbook PDF...")
            
            # Change to cookbook directory
            import os
            original_cwd = os.getcwd()
            os.chdir(output_dir)
            
            try:
                # Run XeLaTeX twice for proper cross-references
                for run in range(2):
                    result = subprocess.run(
                        ['xelatex', '-interaction=nonstopmode', 'main.tex'],
                        capture_output=True,
                        text=True,
                        timeout=300  # 5 minute timeout
                    )
                    
                    if result.returncode != 0:
                        self.logger.error(f"XeLaTeX failed (run {run+1}):")
                        self.logger.error(result.stderr)
                        return False
                
                # Check if PDF was created (we're already in output_dir)
                pdf_path = Path("main.pdf")
                if pdf_path.exists():
                    full_pdf_path = output_dir / "main.pdf"
                    self.logger.info(f"✓ Cookbook PDF created: {full_pdf_path}")
                    return True
                else:
                    self.logger.error("PDF was not created despite successful XeLaTeX run")
                    # List files for debugging
                    files = list(Path(".").glob("*.pdf"))
                    self.logger.error(f"Available PDF files: {files}")
                    return False
                
            finally:
                os.chdir(original_cwd)
                
        except subprocess.TimeoutExpired:
            self.logger.error("XeLaTeX compilation timed out")
            return False
        except Exception as e:
            self.logger.error(f"PDF compilation failed: {e}")
            return False
    
    def _make_safe_filename(self, title: str) -> str:
        """Convert recipe title to safe filename."""
        safe = title.lower()
        safe = safe.replace(' ', '-').replace(',', '').replace('&', 'and').replace("'", '')
        safe = ''.join(c for c in safe if c.isalnum() or c in '-_')
        return safe[:50]  # Limit length
    
    def _validate_image_file(self, image_path: Path) -> bool:
        """Validate that an image file is readable and valid."""
        try:
            from PIL import Image
            
            # Check file size (avoid empty files)
            if image_path.stat().st_size < 100:  # Less than 100 bytes is suspicious
                return False
            
            # Try to open and verify the image
            with Image.open(image_path) as img:
                img.verify()  # Check if the image is valid
                return True
                
        except Exception:
            return False
    
    def _create_default_placeholder(self, target_image_dir: Path):
        """Create a default placeholder image for missing recipes."""
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            # Create a simple placeholder
            width, height = 400, 300
            img = Image.new('RGB', (width, height), '#f8f9fa')
            draw = ImageDraw.Draw(img)
            
            # Add a border
            border_color = '#dee2e6'
            draw.rectangle([10, 10, width-10, height-10], outline=border_color, width=3)
            
            # Add text
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 24)
            except:
                font = ImageFont.load_default()
            
            text = "Recipe Image\nNot Available"
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            x = (width - text_width) // 2
            y = (height - text_height) // 2
            
            draw.multiline_text((x, y), text, fill='#6c757d', font=font, align='center')
            
            # Save the placeholder
            placeholder_path = target_image_dir / "default_placeholder.jpg"
            img.save(placeholder_path, 'JPEG', quality=85)
            
            self.logger.info(f"Created default placeholder image: {placeholder_path.name}")
            
        except Exception as e:
            self.logger.warning(f"Failed to create default placeholder: {e}")
    
    def _create_recipe_placeholder_image(self, target_image_dir: Path, recipe_name: str):
        """Create a specific placeholder image for a recipe."""
        try:
            from PIL import Image, ImageDraw, ImageFont
            import textwrap
            
            # Create recipe-specific placeholder
            width, height = 600, 400
            img = Image.new('RGB', (width, height), '#f8f9fa')
            draw = ImageDraw.Draw(img)
            
            # Add gradient background
            for y in range(height):
                color_value = int(248 - (y / height) * 20)
                draw.line([(0, y), (width, y)], fill=(color_value, color_value, color_value + 5))
            
            # Add border
            border_color = '#adb5bd'
            draw.rectangle([15, 15, width-15, height-15], outline=border_color, width=2)
            
            # Format recipe name
            display_name = recipe_name.replace('_', ' ').replace('-', ' ').title()
            wrapped_name = textwrap.fill(display_name, width=25)
            
            # Add text with better fonts
            try:
                title_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 32)
                subtitle_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 18)
            except:
                title_font = ImageFont.load_default()
                subtitle_font = ImageFont.load_default()
            
            # Draw recipe name
            lines = wrapped_name.split('\n')
            total_height = len(lines) * 40
            start_y = (height - total_height) // 2 - 30
            
            for i, line in enumerate(lines):
                bbox = draw.textbbox((0, 0), line, font=title_font)
                line_width = bbox[2] - bbox[0]
                x = (width - line_width) // 2
                y = start_y + i * 40
                draw.text((x, y), line, fill='#495057', font=title_font)
            
            # Add subtitle
            subtitle = "Recipe Placeholder"
            bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
            subtitle_width = bbox[2] - bbox[0]
            subtitle_x = (width - subtitle_width) // 2
            subtitle_y = start_y + len(lines) * 40 + 30
            draw.text((subtitle_x, subtitle_y), subtitle, fill='#6c757d', font=subtitle_font)
            
            # Save the image
            safe_name = self._make_safe_filename(recipe_name)
            image_path = target_image_dir / f"{safe_name}.jpg"
            img.save(image_path, 'JPEG', quality=85)
            
            self.logger.info(f"Created recipe placeholder: {image_path.name}")
            
        except Exception as e:
            self.logger.warning(f"Failed to create recipe placeholder for {recipe_name}: {e}")
    
    def _convert_to_preferred_units(self, ingredient: Any) -> Tuple[Optional[float], Optional[str]]:
        """Convert ingredient to preferred units based on smart rules."""
        
        if not hasattr(ingredient, 'quantity') or not ingredient.quantity:
            return None, getattr(ingredient, 'unit', None)
        
        quantity = float(ingredient.quantity)
        unit = getattr(ingredient, 'unit', None) or ""
        name = getattr(ingredient, 'name', "").lower()
        
        # Rule 1: Keep piece units for countable items
        piece_units = ['', 'piece', 'pieces', 'whole', 'item', 'items', 'clove', 'cloves', 
                      'slice', 'slices', 'strip', 'strips', 'stick', 'sticks']
        countable_items = ['egg', 'eggs', 'onion', 'onions', 'apple', 'apples', 'banana', 'bananas',
                          'potato', 'potatoes', 'tomato', 'tomatoes', 'lemon', 'lemons', 'lime', 'limes',
                          'orange', 'oranges', 'carrot', 'carrots', 'garlic', 'bell pepper', 'peppers',
                          'avocado', 'avocados', 'cucumber', 'cucumbers', 'zucchini', 'mushroom', 'mushrooms']
        
        if unit.lower() in piece_units or any(item in name for item in countable_items):
            return quantity, unit if unit else ""
        
        # Rule 2: Special handling for butter - convert to tablespoons/sticks
        if 'butter' in name:
            return self._convert_butter_units(quantity, unit)
        
        # Rule 3: Convert everything to grams first for easier calculation
        grams = self._convert_to_grams(quantity, unit, name)
        
        if grams is None:
            # Can't convert, keep original
            return quantity, unit
        
        # Rule 4: Keep imperial units (tsp/tbsp) for small quantities (≤7g)
        if grams <= 7:
            # Convert back to appropriate small units
            if grams <= 1.5:  # ~1/4 tsp
                return quantity, unit  # Keep original if very small
            elif grams <= 6:  # Up to ~1 tsp  
                tsp_quantity = grams / 2.84  # 1 tsp ≈ 2.84g for spices
                return round(tsp_quantity * 4) / 4, "tsp"  # Round to quarters
            else:  # 6-7g range, use fractional tbsp
                tbsp_quantity = grams / 8.5  # 1 tbsp ≈ 8.5g for spices
                return round(tbsp_quantity * 4) / 4, "tbsp"
        
        # Rule 5: Use grams for everything else, rounded to nearest 5g
        if grams < 1:
            return round(grams, 1), "g"
        elif grams < 5:
            return round(grams), "g"  # Keep single grams for very small amounts
        elif grams < 1000:
            return round(grams / 5) * 5, "g"  # Round to nearest 5g
        else:
            # Use kg for large quantities
            kg = grams / 1000
            if kg < 2:
                return round(kg, 1), "kg"
            else:
                return round(kg * 4) / 4, "kg"  # Round to quarters
    
    def _convert_to_grams(self, quantity: float, unit: str, ingredient_name: str) -> Optional[float]:
        """Convert quantity to grams based on unit and ingredient type."""
        
        unit = unit.lower().strip()
        
        # Volume to weight conversions (approximate)
        volume_conversions = {
            # Liquid conversions (assuming water density ~1g/ml)
            'ml': 1.0,
            'milliliter': 1.0,
            'milliliters': 1.0,
            'l': 1000.0,
            'liter': 1000.0,
            'liters': 1000.0,
            
            # Imperial liquid
            'fl oz': 29.57,
            'fluid ounce': 29.57,
            'fluid ounces': 29.57,
            'cup': 240.0,
            'cups': 240.0,
            'pint': 473.0,
            'pints': 473.0,
            'quart': 946.0,
            'quarts': 946.0,
            'gallon': 3785.0,
            'gallons': 3785.0,
            
            # Cooking spoons (approximate for typical ingredients)
            'tsp': 2.84,
            'teaspoon': 2.84,
            'teaspoons': 2.84,
            'tbsp': 8.5,
            'tablespoon': 8.5,
            'tablespoons': 8.5,
        }
        
        # Weight conversions
        weight_conversions = {
            'g': 1.0,
            'gram': 1.0,
            'grams': 1.0,
            'kg': 1000.0,
            'kilogram': 1000.0,
            'kilograms': 1000.0,
            'oz': 28.35,
            'ounce': 28.35,
            'ounces': 28.35,
            'lb': 453.6,
            'pound': 453.6,
            'pounds': 453.6,
        }
        
        # Direct weight conversion
        if unit in weight_conversions:
            return quantity * weight_conversions[unit]
        
        # Volume conversion with ingredient-specific density adjustments
        if unit in volume_conversions:
            base_grams = quantity * volume_conversions[unit]
            
            # Adjust for ingredient density
            density_multiplier = self._get_ingredient_density_multiplier(ingredient_name)
            return base_grams * density_multiplier
        
        # Can't convert
        return None
    
    def _get_ingredient_density_multiplier(self, ingredient_name: str) -> float:
        """Get density multiplier for ingredient (relative to water = 1.0)."""
        
        name = ingredient_name.lower()
        
        # Dense ingredients (heavier than water)
        if any(word in name for word in ['honey', 'syrup', 'molasses', 'jam']):
            return 1.4
        elif any(word in name for word in ['sugar', 'brown sugar', 'salt']):
            return 0.85
        elif any(word in name for word in ['flour', 'all-purpose flour', 'bread flour']):
            return 0.52
        elif any(word in name for word in ['butter', 'margarine']):
            return 0.91
        elif any(word in name for word in ['oil', 'olive oil', 'vegetable oil']):
            return 0.92
        elif any(word in name for word in ['milk', 'cream', 'buttermilk']):
            return 1.03
        elif any(word in name for word in ['cocoa powder', 'cocoa']):
            return 0.48
        elif any(word in name for word in ['baking powder', 'baking soda']):
            return 0.65
        elif any(word in name for word in ['vanilla extract', 'extract']):
            return 0.87
        
        # Light/fluffy ingredients
        elif any(word in name for word in ['lettuce', 'spinach', 'herbs', 'parsley']):
            return 0.3
        elif any(word in name for word in ['breadcrumbs', 'panko']):
            return 0.35
        
        # Default: assume water density
        return 1.0
    
    def _format_fraction(self, decimal: float) -> str:
        """Convert decimal to readable fraction."""
        
        # Common cooking fractions
        fractions = {
            0.125: "1/8",
            0.25: "1/4", 
            0.33: "1/3",
            0.375: "3/8",
            0.5: "1/2",
            0.67: "2/3",
            0.625: "5/8",
            0.75: "3/4",
            0.875: "7/8"
        }
        
        # Find closest fraction
        closest = min(fractions.keys(), key=lambda x: abs(x - decimal))
        if abs(closest - decimal) < 0.05:  # Close enough
            return fractions[closest]
        
        # Return decimal with reasonable precision
        return f"{decimal:.2f}".rstrip('0').rstrip('.')
    
    def _create_missing_recipe_images(self, validated_recipes: List[Tuple[Recipe, RecipeValidationResult]], images_dir: Path):
        """Create placeholder images for recipes that don't have corresponding image files."""
        
        for recipe, validation in validated_recipes:
            safe_title = self._make_safe_filename(recipe.title)
            
            # Check if recipe has an image
            expected_image_files = [
                images_dir / f"{safe_title}.jpg",
                images_dir / f"{safe_title}.jpeg", 
                images_dir / f"{safe_title}.png"
            ]
            
            # Also check for the image referenced in the recipe JSON
            if recipe.image_url and recipe.image_url.startswith("./image/"):
                json_image_name = recipe.image_url.replace("./image/", "")
                expected_image_files.append(images_dir / json_image_name)
            
            # Check if any of the expected images exist
            has_image = any(img_path.exists() for img_path in expected_image_files)
            
            if not has_image:
                self.logger.info(f"Creating placeholder image for recipe: {recipe.title}")
                self._create_recipe_placeholder_image(images_dir, safe_title)
    
    def _validate_recipe_pdf_layout(self, recipe: Recipe, max_pages: int) -> Optional[float]:
        """Validate recipe by actually compiling to PDF and checking page count."""
        
        import tempfile
        import os
        import subprocess
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Copy necessary resources
                self._setup_test_environment(temp_path)
                
                # Generate recipe LaTeX file
                recipe_data = self._format_recipe_for_latex(recipe)
                template = self.jinja_env.get_template("cookbook_recipe.tex")
                recipe_content = template.render(**recipe_data)
                
                # Create test document
                test_doc = f"""\\documentclass{{recipebook}}
\\begin{{document}}
{recipe_content}
\\end{{document}}"""
                
                # Write test files
                with open(temp_path / "test_recipe.tex", 'w', encoding='utf-8') as f:
                    f.write(test_doc)
                
                # Compile to PDF
                original_cwd = os.getcwd()
                os.chdir(temp_path)
                
                try:
                    # Run XeLaTeX
                    result = subprocess.run(
                        ['xelatex', '-interaction=nonstopmode', 'test_recipe.tex'],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if result.returncode != 0:
                        self.logger.warning(f"LaTeX compilation failed for recipe '{recipe.title}': {result.stderr}")
                        return None
                    
                    # Check if PDF was created
                    pdf_path = temp_path / "test_recipe.pdf"
                    if not pdf_path.exists():
                        return None
                    
                    # Count pages in PDF
                    page_count = self._count_pdf_pages(pdf_path)
                    self.logger.debug(f"Recipe '{recipe.title}' compiles to {page_count} pages")
                    return page_count
                    
                finally:
                    os.chdir(original_cwd)
                    
        except Exception as e:
            self.logger.warning(f"PDF validation failed for recipe '{recipe.title}': {e}")
            return None
    
    def _setup_test_environment(self, temp_path: Path):
        """Set up minimal LaTeX environment for testing."""
        
        # Find and copy recipebook.cls and other necessary files
        source_cookbook_dir = None
        for existing_dir in [
            Path("output/cookbook"),
            Path("output/latex/cookbook"),
            Path(__file__).parent.parent.parent / "output" / "cookbook"
        ]:
            if existing_dir.exists() and (existing_dir / "recipebook.cls").exists():
                source_cookbook_dir = existing_dir
                break
        
        if source_cookbook_dir:
            # Copy essential files
            shutil.copy2(source_cookbook_dir / "recipebook.cls", temp_path / "recipebook.cls")
            
            if (source_cookbook_dir / "recipebook-lang.sty").exists():
                shutil.copy2(source_cookbook_dir / "recipebook-lang.sty", temp_path / "recipebook-lang.sty")
            
            # Create minimal config
            config_content = """% recipebook.cfg
\\ProvidesFile{recipebook.cfg}
\\newcommand{\\recipebooklang}{english}
"""
            with open(temp_path / "recipebook.cfg", 'w') as f:
                f.write(config_content)
            
            # Copy fonts directory if it exists
            source_fonts = source_cookbook_dir / "fonts"
            if source_fonts.exists():
                shutil.copytree(source_fonts, temp_path / "fonts")
    
    def _count_pdf_pages(self, pdf_path: Path) -> int:
        """Count the number of pages in a PDF file."""
        
        try:
            # Try using PyPDF2 if available
            try:
                import PyPDF2
                with open(pdf_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    return len(reader.pages)
            except ImportError:
                pass
            
            # Fallback: use pdfinfo command if available
            try:
                result = subprocess.run(
                    ['pdfinfo', str(pdf_path)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if line.startswith('Pages:'):
                            return int(line.split(':')[1].strip())
            except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
                pass
            
            # Last resort: assume 1 page if file exists and has reasonable size
            if pdf_path.stat().st_size > 1000:  # At least 1KB
                return 1
            
            return 0
            
        except Exception as e:
            self.logger.warning(f"Failed to count PDF pages: {e}")
            return 1  # Assume 1 page as fallback
    
    def _convert_butter_units(self, quantity: float, unit: str) -> Tuple[float, str]:
        """Convert butter to tablespoons or sticks instead of grams."""
        
        # Convert to grams first
        grams = self._convert_to_grams(quantity, unit, 'butter')
        
        if grams is None:
            # Can't convert, keep original
            return quantity, unit
        
        # 1 stick of butter = 8 tablespoons = 113g
        # 1 tablespoon of butter = 14g
        
        if grams >= 56:  # Half stick or more
            sticks = grams / 113
            if sticks >= 1:
                # Use sticks for large quantities
                if sticks == int(sticks):
                    return int(sticks), "stick" if int(sticks) == 1 else "sticks"
                else:
                    # Use fractions for partial sticks
                    return round(sticks * 4) / 4, "sticks"
            else:
                # Less than 1 stick, use tablespoons
                tbsp = grams / 14
                return round(tbsp * 2) / 2, "tbsp"  # Round to halves
        else:
            # Small quantities, use tablespoons
            tbsp = grams / 14
            if tbsp < 1:
                return round(tbsp * 4) / 4, "tbsp"  # Round to quarters
            else:
                return round(tbsp * 2) / 2, "tbsp"  # Round to halves
    
    def _extract_cookbook_metadata(self, main_tex_path: Path) -> CookbookMetadata:
        """Extract cookbook metadata from existing main.tex file."""
        
        metadata = CookbookMetadata()
        
        try:
            with open(main_tex_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract title
            title_match = re.search(r'\\settitle\{([^}]+)\}', content)
            if title_match:
                metadata.title = title_match.group(1).strip()
            
            # Extract author
            author_match = re.search(r'\\setauthor\{([^}]+)\}', content)
            if author_match:
                metadata.author = author_match.group(1).strip()
            
            # Try to extract description from titlepage.tex if it exists
            titlepage_path = main_tex_path.parent / "titlepage.tex"
            if titlepage_path.exists():
                with open(titlepage_path, 'r', encoding='utf-8') as f:
                    titlepage_content = f.read()
                
                # Look for description in titlepage
                desc_match = re.search(r'\\large\s+([^}]+)\}', titlepage_content)
                if desc_match:
                    metadata.description = desc_match.group(1).strip()
            
            self.logger.info(f"Extracted metadata: title='{metadata.title}', author='{metadata.author}'")
            
        except Exception as e:
            self.logger.warning(f"Failed to extract metadata from {main_tex_path}: {e}")
            # Keep default values
        
        return metadata
    
    def add_recipes_to_cookbook(self, new_json_dir: Path, image_dir: Path, cookbook_dir: Path, 
                               max_pages_per_recipe: int = 1, auto_build: bool = True) -> bool:
        """Add new recipes to an existing cookbook."""
        
        self.logger.info(f"Adding recipes from {new_json_dir} to existing cookbook {cookbook_dir}")
        
        try:
            # Load existing cookbook metadata
            main_tex_path = cookbook_dir / "main.tex"
            metadata = self._extract_cookbook_metadata(main_tex_path)
            
            # Load new recipes
            new_recipes = self._load_recipes(new_json_dir)
            if not new_recipes:
                self.logger.warning("No new recipes found to add")
                return False
            
            self.logger.info(f"Adding {len(new_recipes)} new recipes to cookbook")
            
            # Validate and optimize new recipes
            validated_recipes = []
            for recipe in new_recipes:
                validation_result = self._validate_recipe_formatting(recipe, max_pages_per_recipe)
                validated_recipes.append((recipe, validation_result))
                
                if validation_result.is_valid:
                    self.logger.info(f"✓ Recipe '{recipe.title}' validated successfully")
                else:
                    self.logger.warning(f"⚠ Recipe '{recipe.title}' validation issues: {validation_result.issues}")
            
            # Organize images for new recipes
            images_dir = cookbook_dir / "images"
            self._organize_new_recipe_images(new_recipes, image_dir, images_dir)
            
            # Generate LaTeX files for new recipes
            self._generate_recipe_tex_files(validated_recipes, cookbook_dir)
            
            # Update main.tex to include new recipes
            self._update_main_tex_with_new_recipes(cookbook_dir, new_recipes)
            
            # Build PDF if requested
            if auto_build:
                return self._build_cookbook_pdf(cookbook_dir)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to add recipes to cookbook: {e}")
            return False
    
    def _organize_new_recipe_images(self, new_recipes: List[Recipe], source_image_dir: Path, target_image_dir: Path):
        """Organize images for new recipes only."""
        
        # Get list of new recipe image names
        new_recipe_names = set()
        for recipe in new_recipes:
            safe_title = self._make_safe_filename(recipe.title)
            new_recipe_names.add(safe_title)
        
        if not source_image_dir.exists():
            self.logger.warning(f"Source image directory not found: {source_image_dir}")
            # Create placeholder images for new recipes
            for recipe in new_recipes:
                safe_title = self._make_safe_filename(recipe.title)
                self._create_recipe_placeholder_image(target_image_dir, safe_title)
            return
        
        # Copy images for new recipes only
        copied_count = 0
        for image_file in source_image_dir.iterdir():
            if image_file.is_file() and image_file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif']:
                image_name = image_file.stem
                
                # Check if this image corresponds to a new recipe
                if image_name in new_recipe_names:
                    try:
                        target_path = target_image_dir / image_file.name
                        
                        if self._validate_image_file(image_file):
                            shutil.copy2(image_file, target_path)
                            copied_count += 1
                            self.logger.debug(f"Copied image for new recipe: {image_file.name}")
                        else:
                            self.logger.warning(f"Invalid image file skipped: {image_file.name}")
                            
                    except Exception as e:
                        self.logger.warning(f"Failed to copy image {image_file.name}: {e}")
        
        # Create placeholder images for new recipes that don't have images
        for recipe in new_recipes:
            safe_title = self._make_safe_filename(recipe.title)
            expected_image_files = [
                target_image_dir / f"{safe_title}.jpg",
                target_image_dir / f"{safe_title}.jpeg", 
                target_image_dir / f"{safe_title}.png"
            ]
            
            has_image = any(img_path.exists() for img_path in expected_image_files)
            if not has_image:
                self.logger.info(f"Creating placeholder image for new recipe: {recipe.title}")
                self._create_recipe_placeholder_image(target_image_dir, safe_title)
        
        self.logger.info(f"Organized {copied_count} images for new recipes")
    
    def _update_main_tex_with_new_recipes(self, cookbook_dir: Path, new_recipes: List[Recipe]):
        """Update main.tex to include new recipes while preserving existing ones."""
        
        main_tex_path = cookbook_dir / "main.tex"
        
        try:
            # Read existing main.tex
            with open(main_tex_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find the existing recipe inputs
            existing_inputs = []
            input_pattern = r'\\input\{recipes/([^}]+)\}'
            for match in re.finditer(input_pattern, content):
                existing_inputs.append(match.group(1))
            
            # Generate input statements for new recipes
            new_inputs = []
            for recipe in new_recipes:
                safe_title = self._make_safe_filename(recipe.title)
                new_inputs.append(f"\\input{{recipes/{safe_title}}}")
            
            # Find where to insert new inputs (before \end{document})
            end_doc_match = re.search(r'\\end\{document\}', content)
            if end_doc_match:
                # Insert new inputs before \end{document}
                insert_pos = end_doc_match.start()
                new_content = (content[:insert_pos] + 
                              "\n".join(new_inputs) + "\n\n" + 
                              content[insert_pos:])
                
                # Write updated main.tex
                with open(main_tex_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                self.logger.info(f"Updated main.tex with {len(new_inputs)} new recipe inputs")
                
            else:
                self.logger.error("Could not find \\end{document} in main.tex")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update main.tex: {e}")
            return False