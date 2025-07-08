"""
Renderer Agent - Generates HTML and LaTeX output for recipes
"""
import os
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, Template
import json

from ..models.recipe import Recipe
from ..agents.base import BaseAgent, AgentResult
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
            self.logger.info(f"**RENDERING** - Rendering recipe '{recipe.title}' to {format_type}")
            
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
                self.logger.info(f"**RENDERING** - Successfully rendered to: {result.output_path}")
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
            
            # Download and reference local image
            images_dir = output_dir / "image"
            images_dir.mkdir(parents=True, exist_ok=True)
            
            if recipe.image_url:
                try:
                    # Download image and get local filename
                    local_image_filename = self._ensure_recipe_image(recipe, images_dir)
                    # Update JSON to reference local image file instead of URL
                    recipe_dict['image_url'] = f"./image/{local_image_filename}"
                    recipe_dict['original_image_url'] = recipe.image_url  # Keep original for reference
                except Exception as e:
                    self.logger.warning(f"Failed to download image for {recipe.title}: {e}")
                    # Keep original URL if download fails
            
            # Add rendering metadata
            recipe_dict['rendered_at'] = datetime.now().isoformat()
            recipe_dict['format_version'] = "1.0"
            
            # Ensure JSON directory exists
            json_dir = output_dir / "json"
            json_dir.mkdir(parents=True, exist_ok=True)
            
            # Save to file
            safe_title = self._make_safe_filename(recipe.title)
            output_path = json_dir / f"{safe_title}.json"
            
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
            
            # Ensure the html subdirectory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
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
                if hasattr(instruction, 'instruction'):
                    instruction_text = instruction.instruction
                else:
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
        """Render recipe to cookbook-style LaTeX format (itakurah format)."""
        try:
            # Load cookbook template
            template = self.jinja_env.get_template("cookbook_recipe.tex")
            
            # Format ingredients according to itakurah style
            formatted_ingredients = []
            for ingredient in recipe.ingredients:
                parts = []
                
                # Quantity - use smart formatting
                if ingredient.quantity is not None and ingredient.quantity > 0:
                    qty = ingredient.quantity
                    formatted_qty = self._format_quantity_for_display(qty)
                    parts.append(formatted_qty)
                
                # Unit
                if ingredient.unit:
                    parts.append(ingredient.unit)
                
                # Name
                parts.append(ingredient.name)
                
                # Preparation in parentheses
                if ingredient.preparation:
                    parts.append(f"({ingredient.preparation})")
                
                # Join with spaces and escape for LaTeX
                ingredient_str = " ".join(parts)
                formatted_ingredients.append(self._escape_latex(ingredient_str))
            
            # Format instructions according to itakurah style
            formatted_instructions = []
            for instruction in recipe.instructions:
                if hasattr(instruction, 'instruction'):
                    text = instruction.instruction
                else:
                    text = str(instruction)
                formatted_instructions.append(self._escape_latex(text))
            
            # Prepare template variables
            escaped_title = self._escape_latex(recipe.title)
            
            # Format servings display
            servings_display = str(recipe.servings) if recipe.servings else "4"
            
            # Format time displays
            prep_time_display = f"{recipe.prep_time} MIN" if recipe.prep_time else "15 MIN"
            cook_time_display = f"{recipe.cook_time} MIN" if recipe.cook_time else "30 MIN"
            
            # Generate image path (following itakurah naming convention)
            safe_name = recipe.title.lower()
            safe_name = safe_name.replace(' ', '').replace(',', '').replace('&', 'and').replace("'", '')
            safe_name = ''.join(c for c in safe_name if c.isalnum())
            image_path = f"./images/{safe_name}.jpg"
            
            # Prepare template context
            context = {
                'escaped_title': escaped_title,
                'servings_display': servings_display,
                'prep_time_display': prep_time_display,
                'cook_time_display': cook_time_display,
                'image_path': image_path,
                'formatted_ingredients': formatted_ingredients,
                'formatted_instructions': formatted_instructions
            }
            
            # Render template
            latex_content = template.render(**context)
            
            # Create cookbook directory structure
            cookbook_dir = output_dir / "cookbook"
            recipes_dir = cookbook_dir / "recipes"
            images_dir = cookbook_dir / "images"
            
            recipes_dir.mkdir(parents=True, exist_ok=True)
            images_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate or download placeholder image
            image_filename = self._ensure_recipe_image(recipe, images_dir)
            
            # Update image path in context to match actual generated file
            context['image_path'] = f"./images/{image_filename}"
            
            # Re-render template with updated image path
            latex_content = template.render(**context)
            
            # Save recipe file to cookbook/recipes/
            safe_title = self._make_safe_filename(recipe.title)
            output_path = recipes_dir / f"{safe_title}.tex"
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(latex_content)
            
            # Copy or create necessary cookbook files
            self._setup_cookbook_files(cookbook_dir)
            
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
        
        # First handle HTML entities that might be in the text
        html_entities = {
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&#39;': "'",
            '&####39;': "'",  # Sometimes appears as malformed entity
            '&#x27;': "'",
            '&apos;': "'",
            '&nbsp;': ' ',
            '&ndash;': '-',
            '&mdash;': '--',
            '&hellip;': '...'
        }
        
        escaped = text
        for entity, replacement in html_entities.items():
            escaped = escaped.replace(entity, replacement)
        
        # Handle remaining numeric HTML entities with regex
        import re
        # Match &#number; patterns (like &#39; or &#x27;)
        escaped = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), escaped)
        escaped = re.sub(r'&#x([0-9a-fA-F]+);', lambda m: chr(int(m.group(1), 16)), escaped)
        
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
    
    def _format_quantity_for_display(self, quantity: float) -> str:
        """Format quantity for HTML display with proper fractions."""
        if quantity == int(quantity):
            return str(int(quantity))
        else:
            return self._decimal_to_fraction(quantity)
    
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
    
    def _ensure_recipe_image(self, recipe: Recipe, images_dir: Path) -> str:
        """Ensure recipe has an image, generate placeholder if needed."""
        # Generate safe filename for image
        safe_name = recipe.title.lower()
        safe_name = safe_name.replace(' ', '').replace(',', '').replace('&', 'and').replace("'", '')
        safe_name = ''.join(c for c in safe_name if c.isalnum())
        image_filename = f"{safe_name}.jpg"
        image_path = images_dir / image_filename
        
        # If image already exists, use it
        if image_path.exists():
            return image_filename
        
        # Try to download from recipe URL if available
        if recipe.image_url:
            try:
                import requests
                from PIL import Image
                import io
                
                response = requests.get(recipe.image_url, timeout=10)
                response.raise_for_status()
                
                # Convert to PIL Image and save as JPEG
                img = Image.open(io.BytesIO(response.content))
                img = img.convert('RGB')  # Ensure RGB for JPEG
                img.save(image_path, 'JPEG', quality=85)
                
                self.logger.info(f"Downloaded recipe image: {image_filename}")
                return image_filename
                
            except Exception as e:
                self.logger.warning(f"Failed to download image from {recipe.image_url}: {e}")
        
        # Generate placeholder image
        return self._generate_placeholder_image(recipe, images_dir, image_filename)
    
    def _generate_placeholder_image(self, recipe: Recipe, images_dir: Path, filename: str) -> str:
        """Generate a placeholder image for the recipe. Prioritize local generation over unreliable external services."""
        # First, try local placeholder generation (more reliable)
        self.logger.info(f"Generating local placeholder image for: {recipe.title}")
        local_result = self._generate_local_placeholder_image(recipe, images_dir, filename)
        
        # If local generation succeeded, return it
        if local_result == filename:  # Success returns the original filename
            return local_result
        
        # If local generation failed, try external sources as backup
        try:
            import requests
            from urllib.parse import quote
            
            # Extract main food item from recipe for search
            food_keywords = self._extract_food_keywords(recipe)
            search_query = f"{food_keywords} food dish"
            
            # Try different food-specific image sources with multiple search strategies
            # Encode search terms properly for URLs
            encoded_keywords = quote(food_keywords.encode('utf-8'))
            encoded_query = quote(search_query.encode('utf-8'))
            encoded_title = quote(' '.join(recipe.title.split()[:2]).encode('utf-8'))
            
            image_sources = [
                # Unsplash with specific food queries
                f"https://source.unsplash.com/600x400/?{encoded_keywords}",
                f"https://source.unsplash.com/600x400/?{encoded_query}",
                f"https://source.unsplash.com/600x400/?food,{encoded_keywords}",
                # Lorem Flickr with food focus
                f"https://loremflickr.com/600/400/{encoded_keywords},food",
                f"https://loremflickr.com/600/400/{encoded_query}",
                # Fallback to recipe title
                f"https://source.unsplash.com/600x400/?{encoded_title}",
            ]
            
            for source_url in image_sources:
                try:
                    self.logger.info(f"Trying external image source with keywords '{food_keywords}' from {source_url}")
                    response = requests.get(source_url, timeout=5, stream=True)  # Reduced timeout
                    response.raise_for_status()
                    
                    # Check if we got an actual image (not an error page)
                    if response.headers.get('content-type', '').startswith('image/'):
                        # Save the image
                        image_path = images_dir / filename
                        with open(image_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        
                        self.logger.info(f"Downloaded external placeholder image: {filename}")
                        return filename
                    
                except Exception as e:
                    self.logger.debug(f"External image source failed {source_url}: {e}")
                    continue
            
            # All external sources failed - this is fine, we prioritize local generation
            self.logger.info("External image sources unavailable, using local placeholder")
                
        except Exception as e:
            self.logger.debug(f"External image download failed: {e}")
        
        # Return the local result (even if it was a txt fallback)
        return local_result
    
    def _extract_food_keywords(self, recipe: Recipe) -> str:
        """Extract main food keywords from recipe for image search."""
        import re
        
        # Remove common recipe words and keep main food items
        common_words = {
            'recipe', 'easy', 'best', 'homemade', 'simple', 'quick', 'perfect',
            'delicious', 'amazing', 'ultimate', 'classic', 'traditional', 'authentic',
            'healthy', 'low', 'fat', 'gluten', 'free', 'vegan', 'vegetarian',
            'how', 'to', 'make', 'bake', 'cook', 'prepare', 'with', 'and', 'or',
            'the', 'a', 'an', 'for', 'in', 'on', 'of', 'style', 'minute', 'hour',
            'from', 'using', 'scratch', 'step', 'by', 'home', 'made'
        }
        
        # Food-specific keywords to prioritize
        food_categories = {
            'proteins': ['chicken', 'beef', 'pork', 'fish', 'salmon', 'tuna', 'turkey', 'lamb', 'shrimp', 'crab', 'eggs'],
            'vegetables': ['tomato', 'potato', 'onion', 'carrot', 'broccoli', 'spinach', 'mushroom', 'pepper', 'eggplant'],
            'grains': ['pasta', 'rice', 'bread', 'noodles', 'quinoa', 'oats', 'flour'],
            'dairy': ['cheese', 'milk', 'butter', 'cream', 'yogurt'],
            'desserts': ['cake', 'cookie', 'pie', 'chocolate', 'vanilla', 'strawberry', 'banana', 'apple'],
            'dishes': ['soup', 'salad', 'sandwich', 'pizza', 'burger', 'taco', 'curry', 'stir-fry', 'pancakes']
        }
        
        # Extract words from title
        title_words = re.findall(r'\b\w+\b', recipe.title.lower())
        title_keywords = [word for word in title_words if word not in common_words and len(word) > 2]
        
        # Extract main ingredients (first 3)
        ingredient_keywords = []
        if recipe.ingredients:
            for ingredient in recipe.ingredients[:3]:
                name_words = re.findall(r'\b\w+\b', ingredient.name.lower())
                ingredient_keywords.extend([word for word in name_words if word not in common_words and len(word) > 2])
        
        # Combine and prioritize keywords
        all_keywords = title_keywords + ingredient_keywords[:3]  # Limit to avoid too many keywords
        
        # Prioritize food category words
        prioritized_keywords = []
        for keyword in all_keywords:
            for category, words in food_categories.items():
                if keyword in words:
                    prioritized_keywords.insert(0, keyword)  # Add to front
                    break
            else:
                prioritized_keywords.append(keyword)
        
        # Remove duplicates while preserving order
        unique_keywords = []
        for keyword in prioritized_keywords:
            if keyword not in unique_keywords:
                unique_keywords.append(keyword)
        
        # Take top 3 keywords
        final_keywords = unique_keywords[:3]
        
        return ' '.join(final_keywords) if final_keywords else recipe.title.split()[0]
    
    def _generate_local_placeholder_image(self, recipe: Recipe, images_dir: Path, filename: str) -> str:
        """Generate a local placeholder image for the recipe."""
        try:
            from PIL import Image, ImageDraw, ImageFont
            import textwrap
            
            # Ensure images directory exists
            images_dir.mkdir(parents=True, exist_ok=True)
            
            # Create a 600x400 image with a nice gradient background
            width, height = 600, 400
            img = Image.new('RGB', (width, height), '#f5f5f5')
            draw = ImageDraw.Draw(img)
            
            # Create gradient background
            for y in range(height):
                color_value = int(245 - (y / height) * 30)  # Subtle gradient
                draw.line([(0, y), (width, y)], fill=(color_value, color_value, color_value))
            
            # Try to load fonts with multiple fallback options
            font_large = None
            font_small = None
            
            # Try different font paths for better compatibility
            font_paths = [
                "Arial.ttf",  # Windows
                "/System/Library/Fonts/Arial.ttf",  # macOS
                "/System/Library/Fonts/Helvetica.ttc",  # macOS alternative
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
                "/usr/share/fonts/TTF/arial.ttf",  # Some Linux distros
            ]
            
            for font_path in font_paths:
                try:
                    font_large = ImageFont.truetype(font_path, 36)
                    font_small = ImageFont.truetype(font_path, 20)
                    break
                except:
                    continue
            
            # Final fallback to default font
            if not font_large:
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()
            
            # Add recipe title (wrapped)
            title = recipe.title if recipe.title else "Recipe"
            wrapped_title = textwrap.fill(title, width=20)  # Wrap long titles
            
            # Calculate text size and position
            lines = wrapped_title.split('\n')
            total_height = len(lines) * 40
            start_y = max(50, (height - total_height) // 2 - 40)  # Ensure positive position
            
            # Draw title with error handling
            for i, line in enumerate(lines):
                try:
                    bbox = draw.textbbox((0, 0), line, font=font_large)
                    text_width = bbox[2] - bbox[0]
                    x = max(10, (width - text_width) // 2)  # Ensure positive position
                    y = start_y + i * 40
                    draw.text((x, y), line, fill='#333333', font=font_large)
                except:
                    # Fallback for older PIL versions or font issues
                    x = 50
                    y = start_y + i * 40
                    draw.text((x, y), line, fill='#333333', font=font_large)
            
            # Add subtitle
            subtitle = "Recipe Placeholder"
            try:
                bbox = draw.textbbox((0, 0), subtitle, font=font_small)
                subtitle_width = bbox[2] - bbox[0]
                subtitle_x = max(10, (width - subtitle_width) // 2)
                subtitle_y = start_y + len(lines) * 40 + 20
            except:
                # Fallback for older PIL versions
                subtitle_x = 200
                subtitle_y = start_y + len(lines) * 40 + 20
            
            draw.text((subtitle_x, subtitle_y), subtitle, fill='#666666', font=font_small)
            
            # Add decorative border
            border_color = '#cccccc'
            draw.rectangle([10, 10, width-10, height-10], outline=border_color, width=3)
            
            # Save image with proper error handling
            image_path = images_dir / filename
            img.save(image_path, 'JPEG', quality=85)
            
            # Verify the file was created and has reasonable size
            if image_path.exists() and image_path.stat().st_size > 1000:
                self.logger.info(f"Generated local placeholder image: {filename} ({image_path.stat().st_size} bytes)")
                return filename
            else:
                raise Exception("Generated image file is too small or doesn't exist")
            
        except Exception as e:
            self.logger.error(f"Failed to generate local placeholder image: {e}")
            
            # Enhanced fallback: Try simple image generation
            try:
                from PIL import Image
                
                # Create very simple placeholder
                img = Image.new('RGB', (600, 400), '#f0f0f0')
                image_path = images_dir / filename
                img.save(image_path, 'JPEG', quality=75)
                
                if image_path.exists() and image_path.stat().st_size > 500:
                    self.logger.info(f"Generated simple placeholder image: {filename}")
                    return filename
                    
            except Exception as e2:
                self.logger.error(f"Even simple image generation failed: {e2}")
            
            # Return the jpg filename even if we can't create the image
            self.logger.warning(f"Failed to generate image for {recipe.title}, returning jpg filename anyway")
            return filename
    
    def _setup_cookbook_files(self, cookbook_dir: Path):
        """Set up necessary cookbook files (main.tex, class files, etc.)."""
        try:
            # Create main.tex if it doesn't exist
            main_tex_path = cookbook_dir / "main.tex"
            if not main_tex_path.exists():
                self._create_main_tex(main_tex_path, cookbook_dir)
            
            # Check if we need to copy itakurah files
            class_file = cookbook_dir / "recipebook.cls"
            if not class_file.exists():
                self._copy_itakurah_files(cookbook_dir)
            
        except Exception as e:
            self.logger.warning(f"Failed to setup cookbook files: {e}")
    
    def _copy_itakurah_files(self, cookbook_dir: Path):
        """Copy necessary files from itakurah repository if available."""
        try:
            import tempfile
            import subprocess
            import shutil
            
            # Clone itakurah repo to temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                repo_path = temp_path / "LaTeX-Cookbook"
                
                self.logger.info("Downloading itakurah/LaTeX-Cookbook files...")
                result = subprocess.run([
                    "git", "clone", 
                    "https://github.com/itakurah/LaTeX-Cookbook.git",
                    str(repo_path)
                ], capture_output=True, text=True)
                
                if result.returncode != 0:
                    self.logger.warning("Failed to clone itakurah repository")
                    return
                
                # Copy essential files
                files_to_copy = [
                    "recipebook.cls",
                    "recipebook.cfg", 
                    "recipebook-lang.sty",
                    "titlepage.tex"
                ]
                
                for file_name in files_to_copy:
                    src = repo_path / file_name
                    dst = cookbook_dir / file_name
                    if src.exists():
                        shutil.copy2(src, dst)
                        self.logger.debug(f"Copied {file_name}")
                
                # Copy fonts directory
                fonts_src = repo_path / "fonts"
                fonts_dst = cookbook_dir / "fonts"
                if fonts_src.exists():
                    shutil.copytree(fonts_src, fonts_dst, dirs_exist_ok=True)
                    self.logger.debug("Copied fonts directory")
                
                self.logger.info("Successfully copied itakurah LaTeX-Cookbook files")
                
        except Exception as e:
            self.logger.warning(f"Failed to copy itakurah files: {e}")
            # Create basic fallback files if needed
            self._create_fallback_class_file(cookbook_dir)
    
    def _create_main_tex(self, main_tex_path: Path, cookbook_dir: Path):
        """Create a main.tex file for the cookbook."""
        recipes_dir = cookbook_dir / "recipes"
        
        # Find all recipe .tex files
        recipe_files = []
        if recipes_dir.exists():
            for tex_file in recipes_dir.glob("*.tex"):
                recipe_files.append(tex_file.stem)
        
        main_content = f"""\\documentclass{{recipebook}}

\\begin{{document}}
\\input{{titlepage}}
\\customtableofcontents
"""
        
        # Add input statements for each recipe
        for recipe_file in sorted(recipe_files):
            main_content += f"\\input{{recipes/{recipe_file}}}\n"
        
        main_content += "\\end{document}\n"
        
        with open(main_tex_path, 'w', encoding='utf-8') as f:
            f.write(main_content)
        
        self.logger.info(f"Created main.tex with {len(recipe_files)} recipes")
    
    def _create_fallback_class_file(self, cookbook_dir: Path):
        """Create a basic fallback class file if itakurah files are not available."""
        class_content = """\\NeedsTeXFormat{LaTeX2e}
\\ProvidesClass{recipebook}[2025/01/01 v1.0 Basic recipe book class]

\\LoadClass[a4paper]{article}

\\RequirePackage{graphicx}
\\RequirePackage{geometry}
\\RequirePackage{enumitem}

% Set page margins
\\geometry{margin=2cm}

% Define basic commands
\\newcommand{\\recipeName}{}
\\newcommand{\\servings}{}
\\newcommand{\\prepTime}{}
\\newcommand{\\cookTime}{}
\\newcommand{\\recipeImage}{}

\\newcommand{\\setRecipeMeta}[5]{%
    \\renewcommand{\\recipeName}{#1}%
    \\renewcommand{\\servings}{#2}%
    \\renewcommand{\\prepTime}{#3}%
    \\renewcommand{\\cookTime}{#4}%
    \\renewcommand{\\recipeImage}{#5}%
}

\\newcommand{\\customtableofcontents}{\\tableofcontents\\clearpage}

% Basic recipe environment
\\newenvironment{recipe}{%
    \\clearpage
    \\section*{\\recipeName}
    \\textbf{Servings:} \\servings \\quad
    \\textbf{Prep:} \\prepTime \\quad  
    \\textbf{Cook:} \\cookTime
    \\par\\medskip
}{}

% Basic ingredients environment  
\\newenvironment{ingredients}{%
    \\subsection*{Ingredients}
    \\begin{itemize}[label={}]
}{%
    \\end{itemize}
}

% Basic steps environment
\\newenvironment{steps}{%
    \\subsection*{Instructions}
    \\begin{enumerate}
}{%
    \\end{enumerate}
}

\\newcommand{\\ingredient}[1]{\\item #1}
\\newcommand{\\step}[1]{\\item #1}
"""
        
        class_file = cookbook_dir / "recipebook.cls"
        with open(class_file, 'w', encoding='utf-8') as f:
            f.write(class_content)
        
        # Create basic titlepage
        titlepage_content = """\\begin{titlepage}
\\begin{center}
\\vspace*{1cm}
{\\Huge\\bfseries Recipe Cookbook}
\\vspace{2cm}
\\end{center}
\\end{titlepage}
"""
        titlepage_file = cookbook_dir / "titlepage.tex"
        with open(titlepage_file, 'w', encoding='utf-8') as f:
            f.write(titlepage_content)
        
        self.logger.info("Created fallback class files")
    
    def process(self, recipe: Recipe, format_type: str = "html", output_dir: Optional[Path] = None) -> AgentResult[RenderResult]:
        """Process method required by BaseAgent."""
        return self.render(recipe, format_type, output_dir)