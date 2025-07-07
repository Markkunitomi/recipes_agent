"""
Scraper Agent - Extracts recipe data from websites
"""
import time
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from recipe_scrapers import scrape_me, scrape_html
try:
    from recipe_scrapers._exceptions import RecipeScrapersException
except ImportError:
    # Fallback for different versions
    try:
        from recipe_scrapers._exceptions import RecipeScrapersExceptions as RecipeScrapersException
    except ImportError:
        # Create a generic exception if none available
        class RecipeScrapersException(Exception):
            pass

from agents.base import BaseAgent, AgentResult
from config.settings import Settings

class ScrapeResult:
    """Result of scraping operation."""
    def __init__(self, data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None):
        self.data = data
        self.metadata = metadata or {}
        self.success = True
        self.error = None

class ScraperAgent(BaseAgent):
    """Agent responsible for scraping recipes from websites."""
    
    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.session = self._create_session()
        self.supported_sites = []
        self._load_supported_sites()
    
    def _create_session(self) -> requests.Session:
        """Create requests session with retry strategy."""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.settings.scraping.max_retries,
            backoff_factor=self.settings.scraping.retry_delay,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set headers
        session.headers.update({
            'User-Agent': self.settings.scraping.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
        
        return session
    
    def _load_supported_sites(self):
        """Load list of supported sites from recipe-scrapers."""
        try:
            from recipe_scrapers import SCRAPERS
            self.supported_sites = list(SCRAPERS.keys())
            self.logger.info(f"Loaded {len(self.supported_sites)} supported sites")
        except Exception as e:
            self.logger.warning(f"Could not load supported sites: {e}")
    
    def scrape(self, url: str) -> AgentResult[Dict[str, Any]]:
        """
        Scrape recipe from URL.
        
        Args:
            url: Recipe URL to scrape
            
        Returns:
            AgentResult with scraped recipe data
        """
        try:
            self.logger.info(f"Scraping recipe from: {url}")
            
            # Validate URL
            if not self._is_valid_url(url):
                return AgentResult(
                    success=False,
                    error=f"Invalid URL: {url}"
                )
            
            # Check if site is supported
            domain = self._extract_domain(url)
            is_supported = self._is_supported_site(domain)
            
            if not is_supported:
                self.logger.warning(f"Domain {domain} not in supported sites list")
            
            # Attempt to scrape using recipe-scrapers
            recipe_data = self._scrape_with_library(url)
            
            if recipe_data:
                self.logger.info(f"Successfully scraped recipe: {recipe_data.get('title', 'Unknown')}")
                return AgentResult(
                    success=True,
                    data=recipe_data,
                    metadata={
                        'url': url,
                        'domain': domain,
                        'is_supported_site': is_supported,
                        'scraping_method': 'recipe-scrapers'
                    }
                )
            
            # Fallback to manual HTML scraping
            self.logger.info("Falling back to manual HTML scraping")
            recipe_data = self._scrape_manual(url)
            
            if recipe_data:
                return AgentResult(
                    success=True,
                    data=recipe_data,
                    metadata={
                        'url': url,
                        'domain': domain,
                        'is_supported_site': is_supported,
                        'scraping_method': 'manual'
                    }
                )
            
            return AgentResult(
                success=False,
                error=f"Failed to scrape recipe from {url}"
            )
            
        except Exception as e:
            return self._handle_error(e, f"Error scraping {url}")
    
    def _scrape_with_library(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape using recipe-scrapers library."""
        try:
            # Use recipe-scrapers library
            scraper = scrape_me(url)
            
            # Extract recipe data
            recipe_data = {
                'title': scraper.title(),
                'description': getattr(scraper, 'description', lambda: None)(),
                'ingredients': scraper.ingredients(),
                'instructions': self._normalize_instructions(scraper.instructions()),
                'prep_time': getattr(scraper, 'prep_time', lambda: None)(),
                'cook_time': getattr(scraper, 'cook_time', lambda: None)(),
                'total_time': getattr(scraper, 'total_time', lambda: None)(),
                'servings': getattr(scraper, 'yields', lambda: None)(),
                'image_url': getattr(scraper, 'image', lambda: None)(),
                'nutrition': getattr(scraper, 'nutrition', lambda: None)(),
                'author': getattr(scraper, 'author', lambda: None)(),
                'category': getattr(scraper, 'category', lambda: None)(),
                'cuisine': getattr(scraper, 'cuisine', lambda: None)(),
                'rating': getattr(scraper, 'rating', lambda: None)(),
                'review_count': getattr(scraper, 'review_count', lambda: None)(),
                'url': url
            }
            
            # Clean up None values and empty strings
            recipe_data = {k: v for k, v in recipe_data.items() if v is not None and v != ''}
            
            # Validate minimum required fields
            if not recipe_data.get('title') or not recipe_data.get('ingredients'):
                self.logger.warning("Missing required fields in scraped data")
                return None
            
            return recipe_data
            
        except RecipeScrapersException as e:
            self.logger.warning(f"Recipe scrapers failed: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error in recipe scraping: {e}")
            return None
    
    def _scrape_manual(self, url: str) -> Optional[Dict[str, Any]]:
        """Manual scraping fallback using HTML parsing."""
        try:
            # Fetch HTML content
            response = self.session.get(
                url, 
                timeout=self.settings.scraping.timeout,
                stream=True
            )
            
            # Check content length
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > self.settings.scraping.max_content_length:
                self.logger.warning(f"Content too large: {content_length} bytes")
                return None
            
            response.raise_for_status()
            html_content = response.text
            
            # Try to use recipe-scrapers with raw HTML first
            try:
                scraper = scrape_html(html_content, org_url=url)
                
                if scraper:
                    recipe_data = {
                        'title': scraper.title(),
                        'ingredients': scraper.ingredients(),
                        'instructions': scraper.instructions(),
                        'url': url
                    }
                    
                    # Add optional fields if available
                    optional_fields = ['description', 'prep_time', 'cook_time', 'total_time', 
                                     'yields', 'image', 'nutrition', 'author', 'category', 'cuisine']
                    
                    for field in optional_fields:
                        try:
                            value = getattr(scraper, field, lambda: None)()
                            if value:
                                recipe_data[field] = value
                        except:
                            pass
                    
                    return recipe_data
            except Exception as e:
                self.logger.info(f"Recipe-scrapers HTML parsing failed: {e}")
            
            # Fall back to "wild mode" - aggressive HTML parsing
            self.logger.info("Entering wild mode - aggressive HTML parsing")
            return self._scrape_wild_mode(html_content, url)
            
        except Exception as e:
            self.logger.error(f"Manual scraping failed: {e}")
            return None
    
    def _scrape_wild_mode(self, html_content: str, url: str) -> Optional[Dict[str, Any]]:
        """Wild mode: aggressive HTML parsing for unsupported sites."""
        try:
            from bs4 import BeautifulSoup
            import re
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            recipe_data = {
                'url': url,
                'title': self._extract_title_wild(soup),
                'description': self._extract_description_wild(soup),
                'ingredients': self._extract_ingredients_wild(soup),
                'instructions': self._extract_instructions_wild(soup),
                'image_url': self._extract_image_wild(soup, url),
                'servings': self._extract_servings_wild(soup),
                'prep_time': self._extract_time_wild(soup, 'prep'),
                'cook_time': self._extract_time_wild(soup, 'cook'),
                'total_time': self._extract_time_wild(soup, 'total')
            }
            
            # Only return if we found at least a title and some ingredients or instructions
            if (recipe_data['title'] and 
                (recipe_data['ingredients'] or recipe_data['instructions'])):
                
                # Clean up None values
                recipe_data = {k: v for k, v in recipe_data.items() if v is not None}
                self.logger.info(f"Wild mode success: {recipe_data['title']}")
                return recipe_data
            
            return None
            
        except Exception as e:
            self.logger.error(f"Wild mode scraping failed: {e}")
            return None
    
    def _extract_title_wild(self, soup) -> Optional[str]:
        """Extract recipe title using multiple strategies."""
        strategies = [
            # Schema.org structured data
            lambda: self._extract_from_json_ld(soup, 'name'),
            # Common recipe title selectors
            lambda: self._get_text_from_selectors(soup, [
                'h1.recipe-title', 'h1.entry-title', 'h1.post-title',
                '.recipe-header h1', '.recipe-title', '.entry-title',
                'h1', '[itemprop="name"]', '.wp-block-heading'
            ]),
            # Meta tags
            lambda: soup.find('meta', property='og:title'),
            lambda: soup.find('title')
        ]
        
        for strategy in strategies:
            try:
                result = strategy()
                if result:
                    text = result.get('content') if hasattr(result, 'get') else result.get_text() if hasattr(result, 'get_text') else str(result)
                    if text and len(text.strip()) > 0:
                        return text.strip()
            except:
                continue
        
        return None
    
    def _extract_description_wild(self, soup) -> Optional[str]:
        """Extract recipe description."""
        strategies = [
            lambda: self._extract_from_json_ld(soup, 'description'),
            lambda: self._get_text_from_selectors(soup, [
                '.recipe-description', '.recipe-summary', '.entry-summary',
                '[itemprop="description"]', '.recipe-intro', '.description'
            ]),
            lambda: soup.find('meta', property='og:description')
        ]
        
        for strategy in strategies:
            try:
                result = strategy()
                if result:
                    text = result.get('content') if hasattr(result, 'get') else result.get_text() if hasattr(result, 'get_text') else str(result)
                    if text and len(text.strip()) > 20:  # Reasonable description length
                        return text.strip()
            except:
                continue
        
        return None
    
    def _extract_ingredients_wild(self, soup) -> List[str]:
        """Extract ingredients list."""
        ingredients = []
        
        strategies = [
            lambda: self._extract_from_json_ld(soup, 'recipeIngredient'),
            lambda: self._extract_list_from_selectors(soup, [
                '.recipe-ingredients li', '.ingredients li', '[itemprop="recipeIngredient"]',
                '.recipe-ingredient', '.ingredient', '.wp-block-list li'
            ])
        ]
        
        for strategy in strategies:
            try:
                result = strategy()
                if result and len(result) > 0:
                    ingredients = [ing.strip() for ing in result if ing.strip()]
                    if len(ingredients) >= 2:  # At least 2 ingredients for a valid recipe
                        break
            except:
                continue
        
        return ingredients
    
    def _extract_instructions_wild(self, soup) -> List[str]:
        """Extract cooking instructions."""
        instructions = []
        
        strategies = [
            lambda: self._extract_instructions_from_json_ld(soup),
            lambda: self._extract_jetpack_instructions_complete(soup),
            lambda: self._extract_list_from_selectors(soup, [
                '.recipe-instructions li', '.instructions li', '[itemprop="recipeInstructions"]',
                '.recipe-instruction', '.instruction', '.directions li', '.method li',
                '.recipe-directions li', '.wp-block-list li'
            ]),
            lambda: self._extract_list_from_selectors(soup, [
                '.recipe-instructions p', '.instructions p', '.directions p',
                '.method p', '.recipe-directions p', '.jetpack-recipe-directions p', 
                '.e-instructions p'
            ])
        ]
        
        for strategy in strategies:
            try:
                result = strategy()
                if result and len(result) > 0:
                    instructions = [inst.strip() for inst in result if inst.strip() and len(inst.strip()) > 10]
                    if len(instructions) >= 2:  # At least 2 steps for a valid recipe
                        break
            except:
                continue
        
        return instructions
    
    def _extract_instructions_from_json_ld(self, soup) -> List[str]:
        """Extract and properly parse instructions from JSON-LD data."""
        raw_data = self._extract_from_json_ld(soup, 'recipeInstructions')
        if not raw_data:
            return []
        
        instructions = []
        
        try:
            # Case 1: Array of HowToStep objects
            if isinstance(raw_data, list):
                for item in raw_data:
                    if isinstance(item, dict):
                        # HowToStep with text property
                        if 'text' in item:
                            instructions.append(item['text'])
                        # HowToStep with name property
                        elif 'name' in item:
                            instructions.append(item['name'])
                        # Other structured step formats
                        elif '@type' in item and item['@type'] == 'HowToStep':
                            text = item.get('text') or item.get('name') or str(item)
                            instructions.append(text)
                    elif isinstance(item, str):
                        # Simple string instruction
                        instructions.append(item)
            
            # Case 2: Single string (split on sentence boundaries)
            elif isinstance(raw_data, str):
                # Split on common instruction separators
                import re
                # Split on periods followed by capital letters, or numbered steps
                split_patterns = [
                    r'\.(?=\s*[A-Z0-9])',  # Period followed by capital letter/number
                    r'(?<=\.)\s*(?=\d+\.)',  # Period followed by numbered step
                    r'\n+',  # Newlines
                ]
                
                text = raw_data.strip()
                for pattern in split_patterns:
                    split_text = re.split(pattern, text)
                    if len(split_text) > 1:
                        instructions = [step.strip() for step in split_text if step.strip()]
                        break
                
                # If no good splits found, treat as single instruction
                if not instructions:
                    instructions = [text]
            
            # Case 3: Single HowToStep object
            elif isinstance(raw_data, dict):
                if 'text' in raw_data:
                    instructions.append(raw_data['text'])
                elif 'name' in raw_data:
                    instructions.append(raw_data['name'])
                else:
                    instructions.append(str(raw_data))
        
        except Exception as e:
            self.logger.debug(f"Error parsing JSON-LD instructions: {e}")
            return []
        
        # Clean and filter instructions
        cleaned_instructions = []
        for instruction in instructions:
            if isinstance(instruction, str):
                cleaned = instruction.strip()
                if cleaned and len(cleaned) > 10:  # Filter out very short instructions
                    cleaned_instructions.append(cleaned)
        
        return cleaned_instructions
    
    def _normalize_instructions(self, raw_instructions) -> List[str]:
        """Normalize instructions from recipe-scrapers library."""
        if not raw_instructions:
            return []
        
        instructions = []
        
        try:
            # Case 1: Already a list of strings
            if isinstance(raw_instructions, list):
                for item in raw_instructions:
                    if isinstance(item, str) and item.strip():
                        instructions.append(item.strip())
                    elif hasattr(item, 'text'):  # Object with text property
                        instructions.append(item.text.strip())
                    else:
                        instructions.append(str(item).strip())
            
            # Case 2: Single string (need to split into steps)
            elif isinstance(raw_instructions, str):
                # Split on common instruction separators
                import re
                text = raw_instructions.strip()
                
                # Try different splitting strategies
                split_patterns = [
                    r'\d+\.\s+',  # Numbered steps like "1. Mix..."
                    r'Step\s+\d+[:\.\s]+',  # "Step 1: Mix..."
                    r'(?<=\.)\s*(?=[A-Z])',  # Period followed by capital letter
                    r'\n\s*\n',  # Double newlines
                    r'\n(?=[A-Z])',  # Newline followed by capital letter
                ]
                
                for pattern in split_patterns:
                    split_text = re.split(pattern, text)
                    if len(split_text) > 1:
                        # Clean and filter the split instructions
                        for step in split_text:
                            cleaned = step.strip()
                            if cleaned and len(cleaned) > 10:  # Filter short fragments
                                instructions.append(cleaned)
                        break
                
                # If no good splits found, treat as single instruction
                if not instructions and len(text) > 10:
                    instructions = [text]
            
            # Case 3: Other types (try to convert to string)
            else:
                instructions = [str(raw_instructions)]
        
        except Exception as e:
            self.logger.debug(f"Error normalizing instructions: {e}")
            # Fallback to treating as single instruction
            if isinstance(raw_instructions, str):
                instructions = [raw_instructions]
            else:
                instructions = [str(raw_instructions)]
        
        # Final validation and cleaning
        final_instructions = []
        for instruction in instructions:
            if isinstance(instruction, str):
                cleaned = instruction.strip()
                # Filter out single characters and very short text
                if cleaned and len(cleaned) > 10:
                    final_instructions.append(cleaned)
        
        return final_instructions
    
    def _extract_jetpack_instructions_complete(self, soup) -> List[str]:
        """Extract all instructions from Jetpack recipe including first step as text node."""
        instructions = []
        
        # Find the jetpack recipe directions container
        containers = soup.select('.jetpack-recipe-directions, .e-instructions')
        if not containers:
            return []
        
        container = containers[0]
        
        # Get all the text content
        full_text = container.get_text().strip()
        
        # Find all paragraph elements
        paragraphs = container.find_all('p')
        
        if paragraphs and full_text:
            # Extract text that comes before the first paragraph
            first_p_text = paragraphs[0].get_text().strip()
            
            # Find where the first paragraph starts in the full text
            first_p_start = full_text.find(first_p_text)
            
            if first_p_start > 0:
                # Extract the text before the first paragraph
                before_first_p = full_text[:first_p_start].strip()
                
                # Clean up the extracted text
                if before_first_p and len(before_first_p) > 10:
                    # Remove any trailing whitespace and normalize
                    import re
                    cleaned = re.sub(r'\s+', ' ', before_first_p).strip()
                    instructions.append(cleaned)
        
        # Add all paragraph instructions
        for p in paragraphs:
            text = p.get_text().strip()
            if text and len(text) > 10:
                # Clean up whitespace
                import re
                cleaned = re.sub(r'\s+', ' ', text).strip()
                instructions.append(cleaned)
        
        return instructions
    
    def _extract_image_wild(self, soup, base_url: str) -> Optional[str]:
        """Extract recipe image URL."""
        strategies = [
            lambda: self._extract_from_json_ld(soup, 'image'),
            lambda: soup.find('meta', property='og:image'),
            lambda: self._get_image_from_selectors(soup, [
                '.recipe-image img', '.recipe-photo img', '.featured-image img',
                '.entry-content img', '.recipe-header img'
            ])
        ]
        
        for strategy in strategies:
            try:
                result = strategy()
                if result:
                    if isinstance(result, dict) and 'url' in result:
                        url = result['url']
                    elif hasattr(result, 'get'):
                        url = result.get('content') or result.get('src')
                    elif hasattr(result, 'get_text'):
                        url = result.get('src')
                    else:
                        url = str(result)
                    
                    if url and url.startswith(('http', '//')):
                        return url
                    elif url and url.startswith('/'):
                        from urllib.parse import urljoin
                        return urljoin(base_url, url)
            except:
                continue
        
        return None
    
    def _extract_servings_wild(self, soup) -> Optional[int]:
        """Extract serving size."""
        strategies = [
            lambda: self._extract_from_json_ld(soup, 'recipeYield'),
            lambda: self._get_text_from_selectors(soup, [
                '[itemprop="recipeYield"]', '.recipe-yield', '.servings',
                '.recipe-servings', '.serves'
            ])
        ]
        
        for strategy in strategies:
            try:
                result = strategy()
                if result:
                    text = result.get_text() if hasattr(result, 'get_text') else str(result)
                    import re
                    numbers = re.findall(r'\d+', text)
                    if numbers:
                        return int(numbers[0])
            except:
                continue
        
        return None
    
    def _extract_time_wild(self, soup, time_type: str) -> Optional[int]:
        """Extract cooking times (prep, cook, total)."""
        selectors = {
            'prep': ['[itemprop="prepTime"]', '.prep-time', '.recipe-prep-time'],
            'cook': ['[itemprop="cookTime"]', '.cook-time', '.recipe-cook-time'],
            'total': ['[itemprop="totalTime"]', '.total-time', '.recipe-total-time']
        }
        
        try:
            elements = self._get_text_from_selectors(soup, selectors.get(time_type, []))
            if elements:
                text = elements.get_text() if hasattr(elements, 'get_text') else str(elements)
                return self._parse_time_string(text)
        except:
            pass
        
        return None
    
    def _extract_from_json_ld(self, soup, field: str):
        """Extract data from JSON-LD structured data."""
        try:
            import json
            scripts = soup.find_all('script', type='application/ld+json')
            
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    
                    # Handle array of objects
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get('@type') == 'Recipe':
                                if field in item:
                                    return item[field]
                    
                    # Handle single object
                    elif isinstance(data, dict):
                        if data.get('@type') == 'Recipe' and field in data:
                            return data[field]
                        
                        # Look for nested recipe data
                        if '@graph' in data:
                            for item in data['@graph']:
                                if isinstance(item, dict) and item.get('@type') == 'Recipe':
                                    if field in item:
                                        return item[field]
                
                except json.JSONDecodeError:
                    continue
        except:
            pass
        
        return None
    
    def _get_text_from_selectors(self, soup, selectors: List[str]):
        """Get text content from CSS selectors."""
        for selector in selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    return element
            except:
                continue
        return None
    
    def _extract_list_from_selectors(self, soup, selectors: List[str]) -> List[str]:
        """Extract list of items from CSS selectors."""
        for selector in selectors:
            try:
                elements = soup.select(selector)
                if elements and len(elements) > 1:  # At least 2 items for a valid list
                    items = []
                    for element in elements:
                        text = element.get_text().strip()
                        if text:
                            items.append(text)
                    if len(items) >= 2:
                        return items
            except:
                continue
        return []
    
    def _get_image_from_selectors(self, soup, selectors: List[str]):
        """Get image element from CSS selectors."""
        for selector in selectors:
            try:
                element = soup.select_one(selector)
                if element and element.get('src'):
                    return element
            except:
                continue
        return None
    
    def _parse_time_string(self, time_str: str) -> Optional[int]:
        """Parse time string to minutes."""
        import re
        
        # Look for patterns like "30 minutes", "1 hour 30 minutes", "1h 30m"
        time_str = time_str.lower()
        
        # Extract hours and minutes
        hours = 0
        minutes = 0
        
        hour_match = re.search(r'(\d+)\s*(?:hour|hr|h)', time_str)
        if hour_match:
            hours = int(hour_match.group(1))
        
        minute_match = re.search(r'(\d+)\s*(?:minute|min|m)', time_str)
        if minute_match:
            minutes = int(minute_match.group(1))
        
        # If no specific units found, assume first number is minutes
        if hours == 0 and minutes == 0:
            number_match = re.search(r'(\d+)', time_str)
            if number_match:
                minutes = int(number_match.group(1))
        
        total_minutes = hours * 60 + minutes
        return total_minutes if total_minutes > 0 else None
    
    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc.lower()
        except Exception:
            return ""
    
    def _is_supported_site(self, domain: str) -> bool:
        """Check if domain is in supported sites list."""
        return any(domain in site or site in domain for site in self.supported_sites)
    
    def get_supported_sites(self) -> list[str]:
        """Get list of supported sites."""
        return self.supported_sites.copy()
    
    def test_scraping(self, url: str) -> Dict[str, Any]:
        """Test scraping a URL and return diagnostic information."""
        start_time = time.time()
        
        result = self.scrape(url)
        
        diagnostic = {
            'url': url,
            'success': result.success,
            'error': result.error,
            'duration': time.time() - start_time,
            'domain': self._extract_domain(url),
            'is_supported_site': self._is_supported_site(self._extract_domain(url))
        }
        
        if result.success and result.data:
            diagnostic.update({
                'title': result.data.get('title', 'No title'),
                'ingredients_count': len(result.data.get('ingredients', [])),
                'instructions_count': len(result.data.get('instructions', [])),
                'has_image': bool(result.data.get('image_url')),
                'has_nutrition': bool(result.data.get('nutrition')),
                'scraping_method': result.metadata.get('scraping_method', 'unknown')
            })
        
        return diagnostic
    
    def process(self, url: str) -> AgentResult[Dict[str, Any]]:
        """Process method required by BaseAgent."""
        return self.scrape(url)