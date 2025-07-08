"""
Website Generator Agent - Converts JSON recipes to strangetom-style HTML pages
"""
import json
import shutil
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, Template

from ..models.recipe import Recipe
from ..agents.base import BaseAgent, AgentResult
from config.settings import Settings

class WebsiteGeneratorAgent(BaseAgent):
    """Agent responsible for generating a complete website from JSON recipes."""
    
    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.website_dir = Path("/Users/kunim2/bin/recipes_agent/website")
        self.recipes_dir = self.website_dir / "recipes"
        self.images_dir = self.website_dir / "images"
        self.json_dir = Path(settings.output.output_dir) / "json"
        self.source_images_dir = Path(settings.output.output_dir) / "image"
        
    def generate_website(self, json_recipes_dir: Optional[Path] = None) -> AgentResult[Dict[str, Any]]:
        """
        Generate complete website from JSON recipes.
        
        Args:
            json_recipes_dir: Directory containing JSON recipe files
            
        Returns:
            AgentResult with generation summary
        """
        try:
            self.logger.info("**WEBSITE GENERATION** - Starting website generation")
            
            # Use default JSON directory if not specified
            if json_recipes_dir is None:
                json_recipes_dir = self.json_dir
            
            # Load all JSON recipes
            recipes = self._load_json_recipes(json_recipes_dir)
            self.logger.info(f"**WEBSITE GENERATION** - Loaded {len(recipes)} recipes")
            
            # Generate individual recipe pages
            generated_pages = []
            for recipe_data in recipes:
                page_result = self._generate_recipe_page(recipe_data)
                if page_result:
                    generated_pages.append(page_result)
            
            # Copy images
            self._copy_recipe_images()
            
            # Generate index page
            self._generate_index_page(recipes)
            
            # Generate recipe list pages
            self._generate_all_recipes_page(recipes)
            
            self.logger.info(f"**WEBSITE GENERATION** - Generated {len(generated_pages)} recipe pages")
            
            return AgentResult(
                success=True,
                data={
                    'recipes_generated': len(generated_pages),
                    'website_dir': str(self.website_dir),
                    'pages': generated_pages
                },
                metadata={
                    'total_recipes': len(recipes),
                    'successful_pages': len(generated_pages),
                    'website_url': f"file://{self.website_dir}/index.html"
                }
            )
            
        except Exception as e:
            return self._handle_error(e, "Error generating website")
    
    def _load_json_recipes(self, json_dir: Path) -> List[Dict[str, Any]]:
        """Load all JSON recipe files from directory."""
        recipes = []
        
        for json_file in json_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    recipe_data = json.load(f)
                    recipe_data['filename'] = json_file.stem
                    recipes.append(recipe_data)
            except Exception as e:
                self.logger.warning(f"Failed to load {json_file}: {e}")
        
        return recipes
    
    def _generate_recipe_page(self, recipe_data: Dict[str, Any]) -> Optional[str]:
        """Generate individual recipe HTML page."""
        try:
            filename = recipe_data.get('filename', 'unknown-recipe')
            safe_filename = self._make_safe_filename(recipe_data.get('title', filename))
            
            # Create HTML content
            html_content = self._create_recipe_html(recipe_data)
            
            # Save HTML file
            output_path = self.recipes_dir / f"{safe_filename}.html"
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            self.logger.info(f"**WEBSITE GENERATION** - Generated page: {safe_filename}.html")
            return safe_filename
            
        except Exception as e:
            self.logger.error(f"Failed to generate page for {recipe_data.get('title', 'unknown')}: {e}")
            return None
    
    def _create_recipe_html(self, recipe_data: Dict[str, Any]) -> str:
        """Create HTML content for a recipe."""
        title = recipe_data.get('title', 'Unknown Recipe')
        description = recipe_data.get('description', title)
        
        # Calculate times
        prep_time = recipe_data.get('prep_time') or 0
        cook_time = recipe_data.get('cook_time') or 0
        total_time = recipe_data.get('total_time') or (prep_time + cook_time)
        
        # Format ingredients
        ingredients_html = self._format_ingredients(recipe_data.get('ingredients', []))
        
        # Format instructions
        instructions_html = self._format_instructions(recipe_data.get('instructions', []))
        
        # Generate image path
        image_filename = self._get_image_filename(recipe_data)
        
        # Create HTML template
        html_template = f'''<!DOCTYPE html>
<html lang="en">
    <head>
        <meta charset="utf-8"/>
        <meta name="Description" content="{description}"/>
        <meta name="viewport" content="width=device-width"/>
        <meta name="theme-color" content="#292d33"/>
        <meta property="og:type" content="website"/>
        <meta property="og:title" content="{title} | Kuni-Recipes"/>
        <meta property="og:description" content="{description}"/>
        <meta property="og:image" content="/images/{image_filename}"/>
        <meta property="og:site_name" content="Kuni-Recipes"/>
        <meta name="twitter:card" content="summary_large_image"/>
        <meta name="twitter:title" content="{title} | Kuni-Recipes"/>
        <meta name="twitter:description" content="{description}"/>
        <meta http-equiv="Content-Security-Policy" content="default-src 'self'; style-src 'self' 'sha256-/bXh1pan0r20HBZrnPN+vDirN0r5YwePxsSH+3nm3oo='; script-src 'self';"/>
        <title>{title} | Kuni-Recipes</title>
        <link rel="preload" href="/fonts/quattrocento-latin.woff2" as="font" type="font/woff2" crossorigin/>
        <link rel="preload" href="/fonts/quattrocento-latin-ext.woff2" as="font" type="font/woff2" crossorigin/>
        <link rel="preload" href="/css/colours.min.css" as="style"/>
        <link rel="stylesheet" type="text/css" href="/css/recipe.min.css"/>
        <link rel="icon" href="/favicon.svg" type="image/svg+xml"/>
        <script defer src="/js/menu.min.js"></script>
        <script src="/js/scale_timers.min.js"></script>
        <noscript><style type="text/css">.scale-controls,.unit-controls,.temp-controls,.inline-amount-controls,.toast-btn{{display: none;}}</style></noscript>
    </head>
    <body itemscope itemtype="https://schema.org/Recipe">
        <main>
            <header>
                <a href="/">Kuni-Recipes</a>
                <button type="button" id="sidebar" aria-label="Menu">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
                    </svg>
                </button>
            </header>

            <meta itemprop="datePublished" content="{datetime.now().strftime('%Y-%m-%d')}"/>
            {f'<meta itemprop="totalTime" content="PT{total_time}M"/>' if total_time else ''}
            {f'<meta itemprop="prepTime" content="PT{prep_time}M"/>' if prep_time else ''}
            {f'<meta itemprop="performTime" content="PT{cook_time}M"/>' if cook_time else ''}
            <meta itemprop="recipeYield" content="{recipe_data.get('servings', 4)} servings"/>
            
            <img itemprop="image" class="recipe-image" src="/images/{image_filename}" alt="Photograph of {title}." width="512" height="288"/>
            
            <div class="recipe-icons">
                <div></div>
                <div>
                    <span class="recipe-icon hidden" id="wakelock">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                          <path d="M10.5 8a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0"/>
                          <path d="M0 8s3-5.5 8-5.5S16 8 16 8s-3 5.5-8 5.5S0 8 0 8m8 3.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7"/>
                        </svg>
                    </span>
                    <span class="recipe-icon hidden", id="share">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                            <path d="M11 2.5a2.5 2.5 0 1 1 .603 1.628l-6.718 3.12a2.5 2.5 0 0 1 0 1.504l6.718 3.12a2.5 2.5 0 1 1-.488.876l-6.718-3.12a2.5 2.5 0 1 1 0-3.256l6.718-3.12A2.5 2.5 0 0 1 11 2.5"/>
                        </svg>
                    </span>
                </div>
            </div>

            <section class="recipe">
                <h1><span itemprop="name">{title}</span></h1>

                <div class="recipe-metadata">
                    <span id="serves">Serves <span id="servings" data-default="{recipe_data.get('servings', 4)}">{recipe_data.get('servings', 4)}</span></span>
                    <span>&nbsp;&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;&nbsp;</span>
                    {f'<span>Prep {prep_time} mins</span>' if prep_time else ''}
                    {f'<span>&nbsp;&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;&nbsp;</span><span>Cook {cook_time} mins</span>' if cook_time else ''}
                </div>
                
                <hr/>
                <h2>Ingredients</h2>
                
                <div class="unit-controls">
                    <div class="cntrl">
                        <input type="radio" name="units" value="metric" id="metric" checked/>
                        <label for="metric">Metric</label>
                    </div>
                    <span>&nbsp;&nbsp;&nbsp;&nbsp;/&nbsp;&nbsp;&nbsp;&nbsp;</span>
                    <div class="cntrl">
                        <input type="radio" name="units" value="imperial" id="imperial" />
                        <label for="imperial">Imperial</label>
                    </div>
                </div>

                <div class="scale-controls">
                    <div class="cntrl">
                        <input type="radio" name="scale" value="x0.5" id="x0.5"/>
                        <label for="x0.5">x0.5</label>
                    </div>
                    <span>&nbsp;&nbsp;&nbsp;&nbsp;/&nbsp;&nbsp;&nbsp;&nbsp;</span>
                    <div class="cntrl">
                        <input type="radio" name="scale" value="x1" id="x1" checked/>
                        <label for="x1">x1</label>
                    </div>
                    <span>&nbsp;&nbsp;&nbsp;&nbsp;/&nbsp;&nbsp;&nbsp;&nbsp;</span>
                    <div class="cntrl">
                        <input type="radio" name="scale" value="x2" id="x2"/>
                        <label for="x2">x2</label>
                    </div>
                    <span>&nbsp;&nbsp;&nbsp;&nbsp;/&nbsp;&nbsp;&nbsp;&nbsp;</span>
                    <div class="cntrl">
                        <input type="radio" name="scale" value="x3" id="x3"/>
                        <label for="x3">x3</label>
                    </div>
                </div>

                <ul>
                    {ingredients_html}
                </ul>

                <hr/>
                <h2>Method</h2>

                <ol>
                    {instructions_html}
                </ol>

            </section>
        </main>
    </body>
</html>'''
        
        return html_template
    
    def _format_ingredients(self, ingredients: List[Dict[str, Any]]) -> str:
        """Format ingredients list as HTML."""
        html_parts = []
        
        for ingredient in ingredients:
            name = ingredient.get('name', 'Unknown ingredient')
            quantity = ingredient.get('quantity')
            unit = ingredient.get('unit', '')
            preparation = ingredient.get('preparation', '')
            
            # Format quantity display
            quantity_display = ""
            if quantity:
                if quantity == int(quantity):
                    quantity_display = str(int(quantity))
                else:
                    quantity_display = self._decimal_to_fraction(quantity)
            
            # Build ingredient text
            ingredient_parts = []
            if quantity_display:
                ingredient_parts.append(f'<span data-default="{quantity_display}">{quantity_display}</span>')
            if unit:
                ingredient_parts.append(unit)
            
            quantity_text = " ".join(ingredient_parts)
            
            # Format preparation
            prep_text = f", {preparation}" if preparation else ""
            
            html_parts.append(f'''
                    <li itemprop="recipeIngredient">
                        <span data-default="{quantity_text}">{quantity_text}</span> {name}{prep_text}
                    </li>''')
        
        return "\n".join(html_parts)
    
    def _format_instructions(self, instructions: List[Dict[str, Any]]) -> str:
        """Format instructions list as HTML."""
        html_parts = []
        
        for instruction in instructions:
            if isinstance(instruction, dict):
                text = instruction.get('instruction', 'Step instruction missing')
                time_minutes = instruction.get('time_minutes')
            else:
                text = str(instruction)
                time_minutes = None
            
            # Add timer functionality if time is specified
            timer_attr = f' data-timer="{time_minutes}"' if time_minutes else ''
            
            html_parts.append(f'''
                    <li{timer_attr}>
                        <input type="checkbox" id="step-{len(html_parts) + 1}"/>
                        <label for="step-{len(html_parts) + 1}">{text}</label>
                    </li>''')
        
        return "\n".join(html_parts)
    
    def _get_image_filename(self, recipe_data: Dict[str, Any]) -> str:
        """Get image filename for recipe."""
        filename = recipe_data.get('filename', 'unknown-recipe')
        # Convert filename to match image naming pattern
        image_name = filename.replace('-', '').replace('_', '') + '.jpg'
        return image_name
    
    def _copy_recipe_images(self):
        """Copy recipe images from source to website images directory."""
        if not self.source_images_dir.exists():
            self.logger.warning("Source images directory not found")
            return
        
        # Copy all images from source to website
        for image_file in self.source_images_dir.glob("*.jpg"):
            dest_path = self.images_dir / image_file.name
            try:
                shutil.copy2(image_file, dest_path)
                self.logger.debug(f"Copied image: {image_file.name}")
            except Exception as e:
                self.logger.warning(f"Failed to copy {image_file.name}: {e}")
    
    def _generate_index_page(self, recipes: List[Dict[str, Any]]):
        """Generate homepage with recent recipes."""
        recent_recipes = recipes[:15]  # Show 15 most recent
        
        recipe_cards = []
        for recipe_data in recent_recipes:
            title = recipe_data.get('title', 'Unknown Recipe')
            filename = self._make_safe_filename(title)
            cook_time = recipe_data.get('cook_time', 0)
            servings = recipe_data.get('servings', 4)
            image_filename = self._get_image_filename(recipe_data)
            
            recipe_cards.append(f'''
                <a href="/recipes/{filename}.html">
                    <img src="/images/{image_filename}" alt="{title}" width="150" height="150"/>
                    <div>{title}</div>
                    <div>{cook_time} mins • {servings} servings</div>
                </a>''')
        
        index_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width"/>
    <title>Kuni-Recipes</title>
    <link rel="stylesheet" type="text/css" href="/css/index.min.css"/>
</head>
<body>
    <header>
        <h1>Kuni-Recipes</h1>
        <nav>
            <a href="/all-recipes.html">All Recipes</a>
        </nav>
    </header>
    
    <main>
        <section id="recent">
            <h2>Recent Recipes</h2>
            <div class="recipe-grid">
                {''.join(recipe_cards)}
            </div>
        </section>
    </main>
</body>
</html>'''
        
        with open(self.website_dir / "index.html", 'w', encoding='utf-8') as f:
            f.write(index_html)
    
    def _generate_all_recipes_page(self, recipes: List[Dict[str, Any]]):
        """Generate page listing all recipes."""
        recipe_list = []
        for recipe_data in recipes:
            title = recipe_data.get('title', 'Unknown Recipe')
            filename = self._make_safe_filename(title)
            cook_time = recipe_data.get('cook_time', 0)
            servings = recipe_data.get('servings', 4)
            
            recipe_list.append(f'''
                <li>
                    <a href="/recipes/{filename}.html">
                        {title} - {cook_time} mins, {servings} servings
                    </a>
                </li>''')
        
        all_recipes_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width"/>
    <title>All Recipes | Kuni-Recipes</title>
    <link rel="stylesheet" type="text/css" href="/css/all.min.css"/>
</head>
<body>
    <header>
        <a href="/">Kuni-Recipes</a>
        <h1>All Recipes</h1>
    </header>
    
    <main>
        <ul class="recipe-list">
            {''.join(recipe_list)}
        </ul>
    </main>
</body>
</html>'''
        
        with open(self.website_dir / "all-recipes.html", 'w', encoding='utf-8') as f:
            f.write(all_recipes_html)
    
    def _decimal_to_fraction(self, decimal: float) -> str:
        """Convert decimal to fraction string."""
        from fractions import Fraction
        
        # Common cooking fractions
        common_fractions = {
            0.125: "1/8", 0.25: "1/4", 0.333: "1/3", 0.375: "3/8",
            0.5: "1/2", 0.625: "5/8", 0.667: "2/3", 0.75: "3/4", 0.875: "7/8"
        }
        
        # Find closest common fraction
        closest_decimal = min(common_fractions.keys(), key=lambda x: abs(x - decimal))
        if abs(closest_decimal - decimal) < 0.05:
            return common_fractions[closest_decimal]
        
        # Use standard fraction conversion
        frac = Fraction(decimal).limit_denominator(16)
        if frac.denominator == 1:
            return str(frac.numerator)
        
        if frac.denominator > 8:
            return f"{decimal:.1f}".rstrip('0').rstrip('.')
            
        return f"{frac.numerator}/{frac.denominator}"
    
    def _make_safe_filename(self, title: str) -> str:
        """Create safe filename from recipe title."""
        import re
        safe = re.sub(r'[^\w\s-]', '', title).strip()
        safe = re.sub(r'[-\s]+', '-', safe)
        return safe.lower()[:50]
    
    def process(self, json_recipes_dir: Optional[Path] = None) -> AgentResult[Dict[str, Any]]:
        """Process method required by BaseAgent."""
        return self.generate_website(json_recipes_dir)