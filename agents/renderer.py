"""
Renderer Agent - Generates HTML and LaTeX output for recipes
"""
import os
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, Template
import json

from models.recipe import Recipe
from agents.base import BaseAgent, AgentResult
from config.settings import Settings

class RenderResult:
    """Result of rendering operation."""
    def __init__(self, output_path: Path, format_type: str, success: bool = True, error: str = None):
        self.output_path = output_path
        self.format_type = format_type
        self.success = success
        self.error = error

class RendererAgent(BaseAgent):
    """Agent responsible for rendering recipes to HTML and LaTeX formats."""
    
    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.output_dir = Path(settings.output.output_dir)
        self.templates_dir = Path(settings.output.templates_dir)
        self.jinja_env = self._setup_jinja_environment()
        self._ensure_directories()
        self._create_default_templates()
    
    def _setup_jinja_environment(self) -> Environment:
        """Setup Jinja2 template environment."""
        return Environment(
            loader=FileSystemLoader(self.templates_dir),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True
        )
    
    def _ensure_directories(self):
        """Ensure output and template directories exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "html").mkdir(exist_ok=True)
        (self.output_dir / "latex").mkdir(exist_ok=True)
        (self.output_dir / "json").mkdir(exist_ok=True)
        self.templates_dir.mkdir(parents=True, exist_ok=True)
    
    def render(self, recipe: Recipe, format_type: str, output_dir: Optional[Path] = None) -> AgentResult[RenderResult]:
        """
        Render recipe to specified format.
        
        Args:
            recipe: Recipe to render
            format_type: "html", "latex", "json", or "strangetom"
            output_dir: Optional output directory override
            
        Returns:
            AgentResult with RenderResult
        """
        try:
            self.logger.info(f"Rendering recipe '{recipe.title}' to {format_type}")
            
            output_base = output_dir or self.output_dir
            
            if format_type.lower() == "html":
                result = self._render_html(recipe, output_base)
            elif format_type.lower() == "latex":
                result = self._render_latex(recipe, output_base)
            elif format_type.lower() == "json":
                result = self._render_json(recipe, output_base)
            elif format_type.lower() == "strangetom":
                result = self._render_strangetom(recipe, output_base)
            elif format_type.lower() == "interactive":
                result = self._render_interactive(recipe, output_base)
            elif format_type.lower() == "cookbook":
                result = self._render_cookbook(recipe, output_base)
            else:
                return AgentResult(
                    success=False,
                    error=f"Unsupported format: {format_type}"
                )
            
            if result.success:
                self.logger.info(f"Successfully rendered to: {result.output_path}")
                return AgentResult(
                    success=True,
                    data=result,
                    metadata={
                        'format': format_type,
                        'output_path': str(result.output_path),
                        'file_size': result.output_path.stat().st_size if result.output_path.exists() else 0
                    }
                )
            else:
                return AgentResult(
                    success=False,
                    error=result.error
                )
                
        except Exception as e:
            return self._handle_error(e, f"Error rendering recipe to {format_type}")
    
    def render_from_json(self, json_path: Path, format_type: str, output_dir: Optional[Path] = None) -> AgentResult[RenderResult]:
        """
        Render recipe from JSON file to specified format.
        
        Args:
            json_path: Path to JSON file containing recipe data
            format_type: "html", "latex", "interactive", "strangetom", "cookbook"
            output_dir: Optional output directory override
            
        Returns:
            AgentResult with RenderResult
        """
        try:
            self.logger.info(f"Rendering recipe from JSON {json_path} to {format_type}")
            
            # Load recipe from JSON
            with open(json_path, 'r', encoding='utf-8') as f:
                recipe_data = json.load(f)
            
            # Convert JSON to Recipe object
            recipe = Recipe(**recipe_data)
            
            # Render using existing render method
            return self.render(recipe, format_type, output_dir)
            
        except Exception as e:
            return self._handle_error(e, f"Error rendering recipe from JSON {json_path} to {format_type}")
    
    def _render_html(self, recipe: Recipe, output_dir: Path) -> RenderResult:
        """Render recipe to HTML format."""
        try:
            # Load HTML template
            template = self.jinja_env.get_template("recipe_html.html")
            
            # Prepare template context
            context = {
                'recipe': recipe,
                'generated_date': datetime.now().strftime("%Y-%m-%d %H:%M"),
                'include_nutrition': self.settings.output.include_nutrition,
                'include_metadata': self.settings.output.include_metadata,
                'total_time_formatted': self._format_time(recipe.total_time),
                'prep_time_formatted': self._format_time(recipe.prep_time),
                'cook_time_formatted': self._format_time(recipe.cook_time),
                'difficulty_display': self._get_enum_display_value(recipe.difficulty),
                'cuisine_display': self._get_enum_display_value(recipe.cuisine)
            }
            
            # Render template
            html_content = template.render(**context)
            
            # Save to file
            safe_title = self._make_safe_filename(recipe.title)
            output_path = output_dir / "html" / f"{safe_title}.html"
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            return RenderResult(output_path, "html", True)
            
        except Exception as e:
            return RenderResult(None, "html", False, str(e))
    
    def _render_latex(self, recipe: Recipe, output_dir: Path) -> RenderResult:
        """Render recipe to LaTeX format."""
        try:
            # Load LaTeX template
            template = self.jinja_env.get_template("recipe_latex.tex")
            
            # Prepare template context
            context = {
                'recipe': recipe,
                'generated_date': datetime.now().strftime("%Y-%m-%d"),
                'escaped_title': self._escape_latex(recipe.title),
                'escaped_description': self._escape_latex(recipe.description) if recipe.description else None,
                'escaped_ingredients': [self._escape_latex(self._format_ingredient(ing)) for ing in recipe.ingredients],
                'escaped_instructions': [self._escape_latex(inst.instruction) for inst in recipe.instructions],
                'servings_display': f"{recipe.servings} servings" if recipe.servings else "Servings not specified",
                'time_display': self._format_recipe_times(recipe)
            }
            
            # Render template
            latex_content = template.render(**context)
            
            # Save to file
            safe_title = self._make_safe_filename(recipe.title)
            output_path = output_dir / "latex" / f"{safe_title}.tex"
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(latex_content)
            
            return RenderResult(output_path, "latex", True)
            
        except Exception as e:
            return RenderResult(None, "latex", False, str(e))
    
    def _render_json(self, recipe: Recipe, output_dir: Path) -> RenderResult:
        """Render recipe to JSON format."""
        try:
            # Convert recipe to dictionary
            recipe_dict = recipe.dict()
            
            # Remove unwanted fields
            unwanted_fields = [
                'yield_amount', 'difficulty', 'cuisine', 'meal_type', 
                'dietary_restrictions', 'source', 'equipment_needed'
            ]
            for field in unwanted_fields:
                recipe_dict.pop(field, None)
            
            # Process ingredients to round weight quantities to integers
            if 'ingredients' in recipe_dict:
                for ingredient in recipe_dict['ingredients']:
                    if ingredient.get('weight_quantity') is not None:
                        ingredient['weight_quantity'] = int(round(ingredient['weight_quantity']))
            
            # Add rendering metadata
            recipe_dict['rendered_at'] = datetime.now().isoformat()
            recipe_dict['format_version'] = "1.0"
            
            # Save to file
            safe_title = self._make_safe_filename(recipe.title)
            output_path = output_dir / "json" / f"{safe_title}.json"
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(recipe_dict, f, indent=2, ensure_ascii=False, default=str)
            
            return RenderResult(output_path, "json", True)
            
        except Exception as e:
            return RenderResult(None, "json", False, str(e))
    
    def _render_strangetom(self, recipe: Recipe, output_dir: Path) -> RenderResult:
        """Render recipe to strangetom-style HTML format."""
        try:
            # Load strangetom template
            template = self.jinja_env.get_template("strangetom_recipe.html")
            
            # Add custom filter for quantity formatting
            def format_quantity(value):
                if value is None:
                    return ""
                if isinstance(value, (int, float)):
                    if value == int(value):
                        return str(int(value))
                    # Handle fractions
                    if value < 1:
                        return self._decimal_to_fraction(value)
                    elif value < 10:
                        return f"{value:.2f}".rstrip('0').rstrip('.')
                    else:
                        return str(round(value, 1))
                return str(value)
            
            self.jinja_env.filters['format_quantity'] = format_quantity
            
            # Prepare template context
            context = {
                'recipe': recipe,
                'generated_date': datetime.now().strftime("%Y-%m-%d"),
                'generated_datetime': datetime.now().strftime("%Y-%m-%d %H:%M"),
                'prep_time_formatted': self._format_time(recipe.prep_time),
                'cook_time_formatted': self._format_time(recipe.cook_time),
                'total_time_formatted': self._format_time(recipe.total_time)
            }
            
            # Render template
            html_content = template.render(**context)
            
            # Save to file
            safe_title = self._make_safe_filename(recipe.title)
            output_path = output_dir / "html" / f"{safe_title}-strangetom.html"
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            return RenderResult(output_path, "strangetom", True)
            
        except Exception as e:
            return RenderResult(None, "strangetom", False, str(e))
    
    def _render_interactive(self, recipe: Recipe, output_dir: Path) -> RenderResult:
        """Render recipe to interactive HTML format with JavaScript features."""
        try:
            # Load interactive template
            template = self.jinja_env.get_template("interactive_recipe.html")
            
            # Add custom filters for the interactive template
            def replace_timers(text):
                """Replace timer patterns with interactive timer buttons."""
                import re
                # Find patterns like "10 minutes", "5 mins", "1 hour", etc.
                timer_pattern = r'(\d+)\s*(minute|minutes|min|mins|hour|hours|hr|hrs)(?:\s+(\w+))?'
                
                def make_timer_button(match):
                    time_num = int(match.group(1))
                    time_unit = match.group(2).lower()
                    label = match.group(3) or "Timer"
                    
                    # Convert to minutes
                    if time_unit in ['hour', 'hours', 'hr', 'hrs']:
                        time_minutes = time_num * 60
                    else:
                        time_minutes = time_num
                    
                    return f'<button class="timer-button" data-minutes="{time_minutes}" data-label="{label}" title="Start {time_num} {time_unit} timer">{time_num} {time_unit}</button>'
                
                return re.sub(timer_pattern, make_timer_button, text)
            
            def add_ingredient_tooltips(text):
                """Add tooltips for ingredients mentioned in instructions."""
                # This would be more sophisticated in practice, matching ingredients
                # to their quantities from the ingredients list
                return text
            
            self.jinja_env.filters['replace_timers'] = replace_timers
            self.jinja_env.filters['add_ingredient_tooltips'] = add_ingredient_tooltips
            
            # Process instructions with filters
            processed_instructions = []
            for instruction in recipe.instructions:
                instruction_text = str(instruction)
                instruction_text = replace_timers(instruction_text)
                instruction_text = add_ingredient_tooltips(instruction_text)
                processed_instructions.append(instruction_text)
            
            # Prepare template context
            context = {
                'title': recipe.title,
                'description': recipe.description,
                'ingredients': recipe.ingredients,
                'instructions': processed_instructions,
                'servings': recipe.servings,
                'prep_time': recipe.prep_time,
                'cook_time': recipe.cook_time,
                'total_time': recipe.total_time,
                'difficulty': self._get_enum_display_value(recipe.difficulty) if recipe.difficulty else None,
                'tags': self._extract_tags(recipe),
                'generation_date': datetime.now().strftime("%Y-%m-%d %H:%M"),
                'source_url': getattr(recipe, 'url', None)
            }
            
            # Render template
            html_content = template.render(**context)
            
            # Save to file
            safe_title = self._make_safe_filename(recipe.title)
            output_path = output_dir / "html" / f"{safe_title}-interactive.html"
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            return RenderResult(output_path, "interactive", True)
            
        except Exception as e:
            return RenderResult(None, "interactive", False, str(e))
    
    def _render_cookbook(self, recipe: Recipe, output_dir: Path) -> RenderResult:
        """Render recipe to cookbook-style LaTeX format."""
        try:
            # Load cookbook template
            template = self.jinja_env.get_template("cookbook_recipe.tex")
            
            # Add custom filters
            def format_quantity(value):
                if value is None or value == 0:
                    return ""
                if isinstance(value, (int, float)):
                    # Always use integer if it's a whole number
                    if value == int(value):
                        return str(int(value))
                    # Use fractions for common cooking fractions
                    if value < 1:
                        return self._decimal_to_fraction(value)
                    # For mixed numbers (e.g., 1.5 → 1 1/2)
                    elif value < 10 and value != int(value):
                        whole = int(value)
                        frac_part = value - whole
                        if frac_part > 0:
                            frac_str = self._decimal_to_fraction(frac_part)
                            return f"{whole} {frac_str}" if whole > 0 else frac_str
                        return str(whole)
                    else:
                        # For larger numbers, round to 1 decimal
                        return f"{value:.1f}".rstrip('0').rstrip('.')
                return str(value)

            def escape_latex(text):
                if not text:
                    return ""
                return self._escape_latex(str(text))
            
            self.jinja_env.filters['format_quantity'] = format_quantity
            self.jinja_env.filters['escape_latex'] = escape_latex
            
            # Prepare escaped content
            escaped_title = self._escape_latex(recipe.title)
            escaped_ingredients = []
            for ingredient in recipe.ingredients:
                ing_parts = []
                # Handle quantity with better formatting
                if ingredient.quantity is not None and ingredient.quantity > 0:
                    ing_parts.append(format_quantity(ingredient.quantity))
                elif ingredient.quantity is None and ingredient.unit:
                    # Try to extract quantity from original text if available
                    if hasattr(ingredient, 'original_text') and ingredient.original_text:
                        import re
                        qty_match = re.search(r'(\d+(?:\.\d+)?)\+?\s*' + re.escape(ingredient.unit), ingredient.original_text)
                        if qty_match:
                            ing_parts.append(qty_match.group(1))
                        else:
                            ing_parts.append("1")  # Default fallback quantity
                # Handle unit
                if ingredient.unit:
                    ing_parts.append(self._escape_latex(ingredient.unit))
                # Handle name (always present)
                ing_parts.append(self._escape_latex(ingredient.name))
                # Handle preparation
                if ingredient.preparation:
                    ing_parts.append(f"({self._escape_latex(ingredient.preparation)})")
                
                # Join parts with appropriate spacing
                escaped_ingredients.append(" ".join(filter(None, ing_parts)))
            
            escaped_instructions = []
            # Handle case where instructions are broken into individual characters
            if len(recipe.instructions) > 50:  # Too many steps, likely character-by-character
                # Combine all instruction text into a single paragraph
                combined_text = ""
                for inst in recipe.instructions:
                    if hasattr(inst, 'instruction'):
                        combined_text += inst.instruction
                    else:
                        combined_text += str(inst)
                
                # Split into sentences and create proper steps
                import re
                # First, try to identify where words should be separated
                # Look for common patterns where words run together
                text_with_spaces = combined_text
                
                # Add spaces between lowercase and uppercase letters
                text_with_spaces = re.sub(r'([a-z])([A-Z])', r'\1 \2', text_with_spaces)
                # Add spaces at sentence boundaries
                text_with_spaces = re.sub(r'([.!?])([A-Z])', r'\1 \2', text_with_spaces)
                # Add spaces between words and numbers
                text_with_spaces = re.sub(r'([a-z])([0-9])', r'\1 \2', text_with_spaces)
                text_with_spaces = re.sub(r'([0-9])([a-zA-Z])', r'\1 \2', text_with_spaces)
                
                # More aggressive word boundary detection
                # Add spaces before common cooking words
                cooking_words = ['the', 'and', 'with', 'into', 'over', 'until', 'then', 'flour', 'bowl', 'well', 'centre', 'back', 'spoon', 'break', 'egg', 'pour', 'half', 'milk', 'whisk', 'together', 'gradually', 'incorporating', 'make', 'smooth', 'thick', 'batter', 'beat', 'thoroughly', 'remove', 'lumps', 'stir', 'rest', 'heat', 'little', 'oil', 'butter', 'medium', 'frying', 'pan', 'tip', 'excess', 'about', 'tablespoons', 'tilt', 'thinly', 'coats', 'base', 'cook', 'moderate', 'seconds', 'minute', 'golden', 'brown', 'underside', 'flip', 'pancake', 'palette', 'knife', 'other', 'side', 'slide', 'out', 'onto', 'plate', 'more', 'remaining', 'pancakes', 'one', 'at', 'time', 'same', 'way', 'preparing', 'advance', 'stack', 'reheat', 'microwave', 'alternatively', 'oven', 'wrap', 'foil', 'warm', 'them', 'through', 'minutes']
                for word in cooking_words:
                    # Add space before the word if it's preceded by a letter
                    text_with_spaces = re.sub(rf'([a-z]){word}', rf'\1 {word}', text_with_spaces, flags=re.IGNORECASE)
                    # Add space after the word if it's followed by a letter
                    text_with_spaces = re.sub(rf'{word}([a-z])', rf'{word} \1', text_with_spaces, flags=re.IGNORECASE)
                
                # Fix common split word issues
                word_fixes = {
                    'b at ter': 'batter',
                    'the n': 'then',
                    'ab out': 'about',
                    'table spoon': 'tablespoon',
                    'table spoons': 'tablespoons',
                    'pan cake': 'pancake',
                    'pan cakes': 'pancakes',
                    'o the r': 'other',
                    'under side': 'underside',
                    'pl at e': 'plate',
                    'at ime': 'a time',
                    'moder at e': 'moderate',
                    'he at': 'heat',
                    'minute s': 'minutes',
                    'altern at ively': 'alternatively',
                    'co at s': 'coats',
                    'asyou': 'as you',
                    'toge the r': 'together',
                    'incorpor at ing': 'incorporating',
                    'tilt ing': 'tilting',
                    'ofa': 'of a',
                    'ina': 'in a',
                    'itis': 'it is',
                    'sinf oil': 's in foil',
                    'the m': 'them',
                    'themilk': 'the milk',
                    'timein': 'time in',
                    'themicrowave': 'the microwave',
                    'apinchofsalt': 'a pinch of salt',
                    'be at': 'beat',
                    'Re heat': 'Reheat',
                    'tablespoon sof': 'tablespoons of',
                    'Altern at ively': 'Alternatively'
                }
                
                for wrong, correct in word_fixes.items():
                    text_with_spaces = text_with_spaces.replace(wrong, correct)
                
                # Clean up multiple spaces
                text_with_spaces = re.sub(r'\s+', ' ', text_with_spaces)
                
                sentences = re.split(r'[.!?]+', text_with_spaces)
                for sentence in sentences:
                    sentence = sentence.strip()
                    # Filter out non-instructional content
                    if (sentence and len(sentence) > 10 and 
                        not sentence.lower().startswith(('yum', 'honestly', 'but honestly')) and
                        not sentence.upper() == sentence):  # Skip all-caps expressions
                        escaped_instructions.append(self._escape_latex(sentence + "."))
            else:
                # Normal case - process instructions normally
                for inst in recipe.instructions:
                    if hasattr(inst, 'instruction'):
                        # It's an instruction object
                        escaped_instructions.append(self._escape_latex(inst.instruction))
                    else:
                        # It's a string
                        escaped_instructions.append(self._escape_latex(str(inst)))
            
            # Prepare template context
            context = {
                'recipe': recipe,
                'generated_date': datetime.now().strftime("%Y-%m-%d"),
                'prep_time_formatted': self._format_time(recipe.prep_time),
                'cook_time_formatted': self._format_time(recipe.cook_time),
                'total_time_formatted': self._format_time(recipe.total_time),
                'escaped_title': escaped_title,
                'escaped_ingredients': escaped_ingredients,
                'escaped_instructions': escaped_instructions
            }
            
            # Render template
            latex_content = template.render(**context)
            
            # Save to file
            safe_title = self._make_safe_filename(recipe.title)
            output_path = output_dir / "latex" / f"{safe_title}-cookbook.tex"
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(latex_content)
            
            return RenderResult(output_path, "cookbook", True)
            
        except Exception as e:
            return RenderResult(None, "cookbook", False, str(e))
    
    def _create_default_templates(self):
        """Create default templates if they don't exist."""
        # HTML template (strangetom style)
        html_template_path = self.templates_dir / "recipe_html.html"
        if not html_template_path.exists():
            self._create_html_template(html_template_path)
        
        # LaTeX template (cookbook style)
        latex_template_path = self.templates_dir / "recipe_latex.tex"
        if not latex_template_path.exists():
            self._create_latex_template(latex_template_path)
    
    def _create_html_template(self, template_path: Path):
        """Create default HTML template inspired by strangetom style."""
        html_template = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ recipe.title }}</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f8f9fa;
        }
        .recipe-card {
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            overflow: hidden;
            margin-bottom: 2rem;
        }
        .recipe-header {
            padding: 2rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .recipe-title {
            font-size: 2.5rem;
            font-weight: 700;
            margin: 0 0 0.5rem 0;
        }
        .recipe-description {
            font-size: 1.1rem;
            opacity: 0.9;
            margin: 0;
        }
        .recipe-meta {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            padding: 1.5rem 2rem;
            background: #f8f9fa;
            border-bottom: 1px solid #e9ecef;
        }
        .meta-item {
            text-align: center;
        }
        .meta-label {
            font-size: 0.875rem;
            color: #6c757d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 0.25rem;
        }
        .meta-value {
            font-size: 1.25rem;
            font-weight: 600;
            color: #495057;
        }
        .recipe-content {
            padding: 2rem;
        }
        .section {
            margin-bottom: 2rem;
        }
        .section-title {
            font-size: 1.5rem;
            font-weight: 600;
            color: #495057;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid #e9ecef;
        }
        .ingredients-list {
            list-style: none;
            padding: 0;
        }
        .ingredient-item {
            padding: 0.75rem 0;
            border-bottom: 1px solid #f8f9fa;
            display: flex;
            align-items: center;
        }
        .ingredient-item:last-child {
            border-bottom: none;
        }
        .ingredient-quantity {
            font-weight: 600;
            color: #667eea;
            min-width: 80px;
            margin-right: 1rem;
        }
        .ingredient-name {
            flex: 1;
        }
        .instructions-list {
            counter-reset: step-counter;
        }
        .instruction-step {
            counter-increment: step-counter;
            margin-bottom: 1.5rem;
            padding: 1rem;
            background: #f8f9fa;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        .instruction-step::before {
            content: counter(step-counter);
            background: #667eea;
            color: white;
            width: 30px;
            height: 30px;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            margin-right: 1rem;
            float: left;
        }
        .instruction-text {
            margin-left: 46px;
        }
        .tags {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 1rem;
        }
        .tag {
            background: #e9ecef;
            color: #495057;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.875rem;
        }
        .footer {
            text-align: center;
            padding: 1rem;
            color: #6c757d;
            font-size: 0.875rem;
            border-top: 1px solid #e9ecef;
        }
    </style>
</head>
<body>
    <div class="recipe-card">
        <div class="recipe-header">
            <h1 class="recipe-title">{{ recipe.title }}</h1>
            {% if recipe.description %}
            <p class="recipe-description">{{ recipe.description }}</p>
            {% endif %}
        </div>
        
        <div class="recipe-meta">
            {% if recipe.servings %}
            <div class="meta-item">
                <div class="meta-label">Servings</div>
                <div class="meta-value">{{ recipe.servings }}</div>
            </div>
            {% endif %}
            {% if prep_time_formatted %}
            <div class="meta-item">
                <div class="meta-label">Prep Time</div>
                <div class="meta-value">{{ prep_time_formatted }}</div>
            </div>
            {% endif %}
            {% if cook_time_formatted %}
            <div class="meta-item">
                <div class="meta-label">Cook Time</div>
                <div class="meta-value">{{ cook_time_formatted }}</div>
            </div>
            {% endif %}
            {% if total_time_formatted %}
            <div class="meta-item">
                <div class="meta-label">Total Time</div>
                <div class="meta-value">{{ total_time_formatted }}</div>
            </div>
            {% endif %}
            {% if recipe.difficulty %}
            <div class="meta-item">
                <div class="meta-label">Difficulty</div>
                <div class="meta-value">{{ difficulty_display }}</div>
            </div>
            {% endif %}
        </div>
        
        <div class="recipe-content">
            {% if recipe.ingredients %}
            <div class="section">
                <h2 class="section-title">Ingredients</h2>
                <ul class="ingredients-list">
                    {% for ingredient in recipe.ingredients %}
                    <li class="ingredient-item">
                        <span class="ingredient-quantity">
                            {% if ingredient.quantity %}{{ ingredient.quantity }}{% endif %}
                            {% if ingredient.unit %} {{ ingredient.unit }}{% endif %}
                        </span>
                        <span class="ingredient-name">
                            {{ ingredient.name }}
                            {% if ingredient.preparation %}, {{ ingredient.preparation }}{% endif %}
                        </span>
                    </li>
                    {% endfor %}
                </ul>
            </div>
            {% endif %}
            
            {% if recipe.instructions %}
            <div class="section">
                <h2 class="section-title">Instructions</h2>
                <div class="instructions-list">
                    {% for instruction in recipe.instructions %}
                    <div class="instruction-step">
                        <div class="instruction-text">{{ instruction.instruction }}</div>
                    </div>
                    {% endfor %}
                </div>
            </div>
            {% endif %}
            
            {% if recipe.tags %}
            <div class="section">
                <h2 class="section-title">Tags</h2>
                <div class="tags">
                    {% for tag in recipe.tags %}
                    <span class="tag">{{ tag }}</span>
                    {% endfor %}
                </div>
            </div>
            {% endif %}
        </div>
        
        <div class="footer">
            Generated on {{ generated_date }}
            {% if recipe.source %} | Source: {{ recipe.source }}{% endif %}
        </div>
    </div>
</body>
</html>'''
        
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(html_template)
    
    def _create_latex_template(self, template_path: Path):
        """Create default LaTeX template inspired by cookbook style."""
        latex_template = r'''% Recipe: {{ recipe.title }}
% Generated on {{ generated_date }}

\begin{recipe}
    [{{ escaped_title }}]
    [{{ servings_display }}]
    [{{ time_display }}]

{% if recipe.description %}
{{ escaped_description }}

{% endif %}
\begin{ingredients}
{% for ingredient in escaped_ingredients %}
    \ingredient{{{ ingredient }}}
{% endfor %}
\end{ingredients}

\begin{steps}
{% for instruction in escaped_instructions %}
    \step {{ instruction }}
{% endfor %}
\end{steps}

{% if recipe.tags %}
\begin{center}
\textit{Tags: {{ recipe.tags|join(', ') }}}
\end{center}
{% endif %}

\end{recipe}
'''
        
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(latex_template)
    
    def _format_time(self, minutes: Optional[int]) -> Optional[str]:
        """Format time in minutes to human readable string."""
        if not minutes:
            return None
        
        if minutes < 60:
            return f"{minutes} min"
        else:
            hours = minutes // 60
            mins = minutes % 60
            if mins == 0:
                return f"{hours} hr"
            else:
                return f"{hours} hr {mins} min"
    
    def _format_recipe_times(self, recipe: Recipe) -> str:
        """Format recipe times for display."""
        times = []
        if recipe.prep_time:
            times.append(f"Prep: {self._format_time(recipe.prep_time)}")
        if recipe.cook_time:
            times.append(f"Cook: {self._format_time(recipe.cook_time)}")
        if recipe.total_time and not (recipe.prep_time and recipe.cook_time):
            times.append(f"Total: {self._format_time(recipe.total_time)}")
        
        return " | ".join(times) if times else "Time not specified"
    
    def _format_ingredient(self, ingredient) -> str:
        """Format ingredient for display."""
        parts = []
        if ingredient.quantity is not None:
            parts.append(str(ingredient.quantity))
        if ingredient.unit:
            parts.append(ingredient.unit)
        if ingredient.name:
            parts.append(ingredient.name)
        if ingredient.preparation:
            parts.append(f"({ingredient.preparation})")
        
        return " ".join(parts)
    
    def _get_enum_display_value(self, enum_field) -> str:
        """Get display value from enum field, handling both enum objects and strings."""
        if not enum_field:
            return 'Unknown'
        
        # If it's already a string (from serialization), use it directly
        if isinstance(enum_field, str):
            return enum_field.title()
        
        # If it's an enum object, get the value
        if hasattr(enum_field, 'value'):
            return enum_field.value.title()
        
        # Fallback to string representation
        return str(enum_field).title()
    
    def _make_safe_filename(self, title: str) -> str:
        """Create safe filename from recipe title."""
        import re
        # Remove or replace unsafe characters
        safe = re.sub(r'[^\w\s-]', '', title).strip()
        safe = re.sub(r'[-\s]+', '-', safe)
        return safe.lower()[:50]  # Limit length
    
    def _escape_latex(self, text: str) -> str:
        """Escape special LaTeX characters."""
        if not text:
            return ""
        
        # LaTeX special characters
        latex_chars = {
            '&': r'\&',
            '%': r'\%',
            '$': r'\$',
            '#': r'\#',
            '^': r'\textasciicircum{}',
            '_': r'\_',
            '{': r'\{',
            '}': r'\}',
            '~': r'\textasciitilde{}',
            '\\': r'\textbackslash{}',
        }
        
        escaped = text
        for char, replacement in latex_chars.items():
            escaped = escaped.replace(char, replacement)
        
        return escaped
    
    def _decimal_to_fraction(self, decimal: float) -> str:
        """Convert decimal to fraction string with cooking-friendly denominators."""
        from fractions import Fraction
        
        # For very awkward fractions, round to nearest common cooking fraction
        common_fractions = {
            0.125: "1/8", 0.25: "1/4", 0.333: "1/3", 0.375: "3/8",
            0.5: "1/2", 0.625: "5/8", 0.667: "2/3", 0.75: "3/4", 0.875: "7/8"
        }
        
        # Find the closest common fraction
        closest_decimal = min(common_fractions.keys(), key=lambda x: abs(x - decimal))
        if abs(closest_decimal - decimal) < 0.05:  # Within 5% tolerance
            return common_fractions[closest_decimal]
        
        # Otherwise use standard fraction conversion with reasonable limit
        frac = Fraction(decimal).limit_denominator(16)
        if frac.denominator == 1:
            return str(frac.numerator)
        
        # If denominator is still awkward, round to decimal
        if frac.denominator > 8:
            return f"{decimal:.1f}".rstrip('0').rstrip('.')
            
        return f"{frac.numerator}/{frac.denominator}"
    
    def render_multiple(self, recipes: List[Recipe], format_type: str, output_dir: Optional[Path] = None) -> AgentResult[List[RenderResult]]:
        """Render multiple recipes to specified format."""
        try:
            results = []
            failed_renders = []
            
            for recipe in recipes:
                result = self.render(recipe, format_type, output_dir)
                if result.success:
                    results.append(result.data)
                else:
                    failed_renders.append(recipe.title)
                    self.logger.warning(f"Failed to render recipe: {recipe.title}")
            
            return AgentResult(
                success=True,
                data=results,
                metadata={
                    'total_recipes': len(recipes),
                    'successful_renders': len(results),
                    'failed_renders': len(failed_renders),
                    'format': format_type
                }
            )
            
        except Exception as e:
            return self._handle_error(e, f"Error in batch rendering")
    
    def create_recipe_collection(self, recipes: List[Recipe], collection_name: str, format_type: str = "html") -> AgentResult[RenderResult]:
        """Create a collection/book of multiple recipes."""
        try:
            if format_type == "html":
                return self._create_html_collection(recipes, collection_name)
            elif format_type == "latex":
                return self._create_latex_cookbook(recipes, collection_name)
            else:
                return AgentResult(
                    success=False,
                    error=f"Collection format {format_type} not supported"
                )
                
        except Exception as e:
            return self._handle_error(e, f"Error creating recipe collection")
    
    def _create_html_collection(self, recipes: List[Recipe], collection_name: str) -> AgentResult[RenderResult]:
        """Create HTML collection of recipes."""
        # This would create an index page with links to individual recipe pages
        # Implementation details depend on specific requirements
        pass
    
    def _create_latex_cookbook(self, recipes: List[Recipe], cookbook_name: str) -> AgentResult[RenderResult]:
        """Create LaTeX cookbook from multiple recipes."""
        # This would create a complete cookbook document
        # Implementation details depend on specific LaTeX cookbook template
        pass
    
    def _extract_tags(self, recipe: Recipe) -> List[str]:
        """Extract tags from recipe for display."""
        tags = []
        
        # Add cuisine as a tag
        if recipe.cuisine:
            cuisine_display = self._get_enum_display_value(recipe.cuisine)
            if cuisine_display != 'Unknown':
                tags.append(cuisine_display.lower())
        
        # Add category if available
        if hasattr(recipe, 'category') and recipe.category:
            if isinstance(recipe.category, list):
                tags.extend([cat.lower() for cat in recipe.category])
            else:
                tags.append(recipe.category.lower())
        
        # Add difficulty as a tag
        if recipe.difficulty:
            difficulty_display = self._get_enum_display_value(recipe.difficulty)
            if difficulty_display != 'Unknown':
                tags.append(difficulty_display.lower())
        
        # Add time-based tags
        if recipe.total_time:
            if recipe.total_time <= 30:
                tags.append('quick')
            elif recipe.total_time <= 60:
                tags.append('medium-time')
            else:
                tags.append('long-cooking')
        
        # Add dietary tags (if available in the recipe model)
        if hasattr(recipe, 'dietary_tags') and recipe.dietary_tags:
            tags.extend([tag.lower() for tag in recipe.dietary_tags])
        
        return list(set(tags))  # Remove duplicates
    
    def process(self, recipe: Recipe, format_type: str = "html", output_dir: Optional[Path] = None) -> AgentResult[RenderResult]:
        """Process method required by BaseAgent."""
        return self.render(recipe, format_type, output_dir)