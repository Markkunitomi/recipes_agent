"""
Recipe Data Models
"""
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timedelta
from enum import Enum
from pydantic import BaseModel, Field, validator
from decimal import Decimal

class DifficultyLevel(Enum):
    """Recipe difficulty levels."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"

class CuisineType(Enum):
    """Cuisine types."""
    AMERICAN = "american"
    ITALIAN = "italian"
    MEXICAN = "mexican"
    ASIAN = "asian"
    FRENCH = "french"
    MEDITERRANEAN = "mediterranean"
    INDIAN = "indian"
    OTHER = "other"

class UnitType(Enum):
    """Unit measurement types."""
    VOLUME = "volume"
    WEIGHT = "weight"
    COUNT = "count"
    TEMPERATURE = "temperature"
    TIME = "time"

class MeasurementUnit(BaseModel):
    """Measurement unit with conversion support."""
    name: str
    abbreviation: str
    unit_type: UnitType
    metric_equivalent: Optional[float] = None  # For conversion
    
    class Config:
        use_enum_values = True

class ParsedIngredient(BaseModel):
    """Parsed ingredient from ingredient-parser."""
    name: str
    quantity: Optional[Union[str, float]] = None
    unit: Optional[str] = None
    preparation: Optional[str] = None
    comment: Optional[str] = None
    original_text: str
    confidence: Optional[float] = None
    
    @validator('quantity', pre=True)
    def convert_quantity(cls, v):
        """Convert quantity to float if possible."""
        if isinstance(v, str):
            try:
                # Handle fractions like "1/2"
                if '/' in v:
                    parts = v.split('/')
                    if len(parts) == 2:
                        return float(parts[0]) / float(parts[1])
                return float(v)
            except (ValueError, ZeroDivisionError):
                return v
        return v

class Ingredient(BaseModel):
    """Processed ingredient with normalization."""
    name: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_type: Optional[UnitType] = None
    preparation: Optional[str] = None
    notes: Optional[str] = None
    alternatives: List[str] = Field(default_factory=list)
    optional: bool = False
    
    # Conversion support
    metric_quantity: Optional[float] = None
    metric_unit: Optional[str] = None
    imperial_quantity: Optional[float] = None
    imperial_unit: Optional[str] = None
    weight_quantity: Optional[float] = None
    weight_unit: Optional[str] = None
    
    # Metadata
    original_text: str
    confidence: Optional[float] = None
    
    class Config:
        use_enum_values = True

class InstructionStep(BaseModel):
    """Individual instruction step."""
    step_number: int
    instruction: str
    time_minutes: Optional[int] = None
    temperature: Optional[int] = None
    temperature_unit: str = "F"
    equipment: List[str] = Field(default_factory=list)
    ingredients_used: List[str] = Field(default_factory=list)
    techniques: List[str] = Field(default_factory=list)
    notes: Optional[str] = None

class NutritionInfo(BaseModel):
    """Nutritional information."""
    calories: Optional[int] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    fiber_g: Optional[float] = None
    sugar_g: Optional[float] = None
    sodium_mg: Optional[float] = None
    
    # Per serving
    per_serving: bool = True

class Recipe(BaseModel):
    """Complete recipe model."""
    # Basic Information
    title: str
    description: Optional[str] = None
    url: Optional[str] = None
    image_url: Optional[str] = None
    
    # Timing
    prep_time: Optional[int] = None  # minutes
    cook_time: Optional[int] = None  # minutes
    total_time: Optional[int] = None  # minutes
    
    # Servings
    servings: Optional[int] = None
    yield_amount: Optional[str] = None
    
    # Classification
    difficulty: Optional[DifficultyLevel] = None
    cuisine: Optional[CuisineType] = None
    meal_type: List[str] = Field(default_factory=list)  # breakfast, lunch, dinner, etc.
    dietary_restrictions: List[str] = Field(default_factory=list)  # vegetarian, gluten-free, etc.
    
    # Content
    ingredients: List[Ingredient] = Field(default_factory=list)
    instructions: List[InstructionStep] = Field(default_factory=list)
    
    # Additional Information
    nutrition: Optional[NutritionInfo] = None
    tags: List[str] = Field(default_factory=list)
    equipment_needed: List[str] = Field(default_factory=list)
    
    # Metadata
    source: Optional[str] = None
    author: Optional[str] = None
    date_created: Optional[datetime] = None
    date_scraped: datetime = Field(default_factory=datetime.now)
    
    # Processing metadata
    processing_notes: List[str] = Field(default_factory=list)
    confidence_score: Optional[float] = None
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    @validator('total_time', pre=True, always=True)
    def calculate_total_time(cls, v, values):
        """Calculate total time if not provided."""
        if v is None:
            prep = values.get('prep_time', 0) or 0
            cook = values.get('cook_time', 0) or 0
            return prep + cook if prep or cook else None
        return v
    
    def add_processing_note(self, note: str):
        """Add a processing note."""
        self.processing_notes.append(note)
    
    def get_ingredient_by_name(self, name: str) -> Optional[Ingredient]:
        """Get ingredient by name."""
        for ingredient in self.ingredients:
            if ingredient.name.lower() == name.lower():
                return ingredient
        return None
    
    def get_total_ingredients_count(self) -> int:
        """Get total number of ingredients."""
        return len(self.ingredients)
    
    def get_total_steps_count(self) -> int:
        """Get total number of instruction steps."""
        return len(self.instructions)
    
    def is_vegetarian(self) -> bool:
        """Check if recipe is vegetarian."""
        return "vegetarian" in [d.lower() for d in self.dietary_restrictions]
    
    def is_vegan(self) -> bool:
        """Check if recipe is vegan."""
        return "vegan" in [d.lower() for d in self.dietary_restrictions]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.dict()
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return self.json(indent=2)