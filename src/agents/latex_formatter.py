"""
LaTeX Formatter Agent - Optimizes recipes for LaTeX cookbook layout
"""
from typing import List, Dict, Any, Optional
import re
import math

from ..agents.base import BaseAgent, AgentResult
from ..agents.llm_integration import LLMManager
from config.settings import Settings
from ..models.recipe import Recipe, InstructionStep

class LaTeXFormatterAgent(BaseAgent):
    """Agent responsible for formatting recipes to fit LaTeX cookbook pages."""
    
    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.llm_manager = LLMManager(settings)
        
        # LaTeX cookbook page constraints
        self.MAX_INGREDIENTS_LINES = 15  # Max lines for ingredients section
        self.MAX_INSTRUCTIONS_LINES = 20  # Max lines for instructions section
        self.CHARS_PER_LINE = 65  # Average characters per line in LaTeX
    
    def process(self, recipe: Recipe) -> AgentResult[Recipe]:
        """Process method required by BaseAgent - delegates to format_recipe."""
        return self.format_recipe(recipe)
        
    def format_recipe(self, recipe: Recipe) -> AgentResult[Recipe]:
        """
        Format recipe to fit LaTeX cookbook page constraints.
        
        Args:
            recipe: Recipe to format
            
        Returns:
            AgentResult with formatted Recipe
        """
        try:
            self.logger.info(f"Formatting recipe '{recipe.title}' for LaTeX")
            
            # Format ingredients
            formatted_ingredients = self._format_ingredients(recipe.ingredients)
            
            # Format instructions to fit page
            formatted_instructions = self._format_instructions(recipe.instructions)
            
            # Create new recipe with formatted content
            formatted_recipe = Recipe(
                title=recipe.title,
                description=recipe.description,
                url=recipe.url,
                image_url=recipe.image_url,
                prep_time=recipe.prep_time,
                cook_time=recipe.cook_time,
                total_time=recipe.total_time,
                servings=recipe.servings,
                yield_amount=recipe.yield_amount,
                difficulty=recipe.difficulty,
                cuisine=recipe.cuisine,
                meal_type=recipe.meal_type,
                dietary_restrictions=recipe.dietary_restrictions,
                ingredients=formatted_ingredients,
                instructions=formatted_instructions,
                nutrition=recipe.nutrition,
                tags=recipe.tags,
                equipment_needed=recipe.equipment_needed,
                source=recipe.source,
                author=recipe.author,
                date_created=recipe.date_created,
                date_scraped=recipe.date_scraped,
                processing_notes=recipe.processing_notes + ["LaTeX formatted for cookbook layout"],
                confidence_score=recipe.confidence_score
            )
            
            self.logger.info(f"Formatted recipe with {len(formatted_instructions)} instruction steps")
            
            return AgentResult(
                success=True,
                data=formatted_recipe,
                metadata={
                    'original_steps': len(recipe.instructions),
                    'formatted_steps': len(formatted_instructions),
                    'estimated_lines': self._estimate_instruction_lines(formatted_instructions)
                }
            )
            
        except Exception as e:
            return self._handle_error(e, f"Error formatting recipe '{recipe.title}' for LaTeX")
    
    def _format_ingredients(self, ingredients) -> List:
        """Format ingredients for optimal LaTeX display."""
        # For now, just return ingredients as-is
        # Could add ingredient line optimization here if needed
        return ingredients
    
    def _format_instructions(self, instructions: List[InstructionStep]) -> List[InstructionStep]:
        """Format instructions to fit within LaTeX page constraints."""
        if not instructions:
            return instructions
        
        # Estimate current line usage
        estimated_lines = self._estimate_instruction_lines(instructions)
        
        if estimated_lines <= self.MAX_INSTRUCTIONS_LINES:
            # Instructions already fit
            return instructions
        
        self.logger.info(f"Instructions need condensing: {estimated_lines} lines -> {self.MAX_INSTRUCTIONS_LINES} max")
        
        # Use LLM to condense instructions
        return self._condense_instructions_with_llm(instructions)
    
    def _estimate_instruction_lines(self, instructions: List[InstructionStep]) -> int:
        """Estimate number of lines the instructions will take in LaTeX."""
        total_lines = 0
        
        for instruction in instructions:
            text_length = len(instruction.instruction)
            # Each step has overhead (step number, spacing)
            step_overhead = 1
            # Calculate text lines based on character count
            text_lines = math.ceil(text_length / self.CHARS_PER_LINE)
            total_lines += step_overhead + text_lines
        
        return total_lines
    
    def _condense_instructions_with_llm(self, instructions: List[InstructionStep]) -> List[InstructionStep]:
        """Use LLM to condense instructions while preserving essential information."""
        try:
            # Convert instructions to text for LLM processing
            instructions_text = []
            for i, step in enumerate(instructions, 1):
                instructions_text.append(f"{i}. {step.instruction}")
            
            combined_text = "\n".join(instructions_text)
            
            prompt = f"""
            Please condense these cooking instructions to fit within {self.MAX_INSTRUCTIONS_LINES} lines while preserving all essential cooking information.
            
            Current instructions:
            {combined_text}
            
            Requirements:
            - Combine similar steps where logical
            - Keep all important timing, temperature, and technique details
            - Maintain cooking order and food safety
            - Aim for {self.MAX_INSTRUCTIONS_LINES} or fewer concise steps
            - Each step should be clear and actionable
            
            Return as a numbered list with each step on a new line.
            """
            
            # Use LLM to condense instructions
            response = self.llm_manager.generate(
                prompt=prompt,
                max_tokens=1000,
                temperature=0.1
            )
            
            if response:
                return self._parse_condensed_instructions(response)
            else:
                self.logger.warning("LLM condensing failed, using truncation fallback")
                return self._truncate_instructions(instructions)
                
        except Exception as e:
            self.logger.warning(f"Error condensing instructions with LLM: {e}")
            return self._truncate_instructions(instructions)
    
    def _parse_condensed_instructions(self, condensed_text: str) -> List[InstructionStep]:
        """Parse LLM-condensed instructions back into InstructionStep objects."""
        instructions = []
        
        # Split by numbered steps
        lines = condensed_text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Remove step numbers (1., 2., etc.)
            instruction_text = re.sub(r'^\d+\.\s*', '', line)
            
            if instruction_text:
                step = InstructionStep(
                    step_number=len(instructions) + 1,
                    instruction=instruction_text
                )
                instructions.append(step)
        
        return instructions
    
    def _truncate_instructions(self, instructions: List[InstructionStep]) -> List[InstructionStep]:
        """Fallback: truncate instructions to fit page limits."""
        # Simple truncation - take first N steps that fit
        truncated = []
        current_lines = 0
        
        for instruction in instructions:
            step_lines = 1 + math.ceil(len(instruction.instruction) / self.CHARS_PER_LINE)
            
            if current_lines + step_lines <= self.MAX_INSTRUCTIONS_LINES:
                truncated.append(instruction)
                current_lines += step_lines
            else:
                break
        
        # Ensure we have at least a few key steps
        if len(truncated) < 3 and len(instructions) >= 3:
            # Take first 3 steps regardless of length
            truncated = instructions[:3]
        
        return truncated
    
    def _escape_latex_special_chars(self, text: str) -> str:
        """Escape special LaTeX characters."""
        if not text:
            return text
        
        # LaTeX special characters that need escaping
        replacements = {
            '&': '\\&',
            '%': '\\%',
            '$': '\\$',
            '#': '\\#',
            '^': '\\textasciicircum{}',
            '_': '\\_',
            '{': '\\{',
            '}': '\\}',
            '~': '\\textasciitilde{}',
            '\\': '\\textbackslash{}'
        }
        
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)
        
        # Handle common HTML entities
        html_entities = {
            '&amp;': '\\&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&#39;': "'",
            '&nbsp;': ' '
        }
        
        for entity, replacement in html_entities.items():
            text = text.replace(entity, replacement)
        
        return text