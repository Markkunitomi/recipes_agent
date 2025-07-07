"""
Unit Conversion Models and Constants
"""
from typing import Dict, Optional, Tuple
from enum import Enum
from pydantic import BaseModel
from decimal import Decimal

class VolumeUnit(Enum):
    """Volume units."""
    # Metric
    MILLILITER = "ml"
    LITER = "l"
    
    # Imperial
    TEASPOON = "tsp"
    TABLESPOON = "tbsp"
    FLUID_OUNCE = "fl oz"
    CUP = "cup"
    PINT = "pint"
    QUART = "quart"
    GALLON = "gallon"

class WeightUnit(Enum):
    """Weight units."""
    # Metric
    GRAM = "g"
    KILOGRAM = "kg"
    
    # Imperial
    OUNCE = "oz"
    POUND = "lb"

class TemperatureUnit(Enum):
    """Temperature units."""
    CELSIUS = "C"
    FAHRENHEIT = "F"

# Conversion factors to base units (ml for volume, g for weight)
VOLUME_CONVERSIONS = {
    VolumeUnit.MILLILITER: 1.0,
    VolumeUnit.LITER: 1000.0,
    VolumeUnit.TEASPOON: 4.92892,
    VolumeUnit.TABLESPOON: 14.7868,
    VolumeUnit.FLUID_OUNCE: 29.5735,
    VolumeUnit.CUP: 236.588,
    VolumeUnit.PINT: 473.176,
    VolumeUnit.QUART: 946.353,
    VolumeUnit.GALLON: 3785.41,
}

WEIGHT_CONVERSIONS = {
    WeightUnit.GRAM: 1.0,
    WeightUnit.KILOGRAM: 1000.0,
    WeightUnit.OUNCE: 28.3495,
    WeightUnit.POUND: 453.592,
}

# Common ingredient density approximations (g/ml)
INGREDIENT_DENSITIES = {
    'flour': 0.54,
    'sugar': 0.85,
    'brown sugar': 0.95,
    'butter': 0.91,
    'oil': 0.92,
    'honey': 1.42,
    'milk': 1.03,
    'water': 1.0,
    'salt': 1.2,
    'baking powder': 0.9,
    'baking soda': 2.2,
    'vanilla': 0.88,
    'cocoa powder': 0.41,
    'powdered sugar': 0.56,
    'rice': 0.75,
    'oats': 0.41,
}

class ConversionRequest(BaseModel):
    """Request for unit conversion."""
    quantity: float
    from_unit: str
    to_unit: str
    ingredient_name: Optional[str] = None

class ConversionResult(BaseModel):
    """Result of unit conversion."""
    original_quantity: float
    original_unit: str
    converted_quantity: float
    converted_unit: str
    ingredient_name: Optional[str] = None
    conversion_factor: float
    is_approximation: bool = False
    notes: Optional[str] = None

def smart_round(value: float, unit: str) -> float:
    """Round conversion values to sensible precision based on unit and magnitude."""
    if unit in ['ml', 'g']:
        # For metric units, round to sensible whole numbers
        if value < 1:
            return round(value, 1)  # 0.5 ml
        elif value < 10:
            return round(value)     # 5 ml
        elif value < 100:
            return round(value)     # 25 ml
        else:
            return round(value)     # 250 ml
    elif unit in ['kg', 'l']:
        # For larger metric units, use 1-2 decimal places
        return round(value, 2)
    else:
        # For imperial units, use 2 decimal places
        return round(value, 2)

class UnitConverter:
    """Handles unit conversions for recipes."""
    
    def __init__(self):
        self.volume_conversions = VOLUME_CONVERSIONS
        self.weight_conversions = WEIGHT_CONVERSIONS
        self.ingredient_densities = INGREDIENT_DENSITIES
    
    def convert_volume(self, quantity: float, from_unit: str, to_unit: str) -> ConversionResult:
        """Convert between volume units."""
        try:
            from_enum = VolumeUnit(from_unit.lower())
            to_enum = VolumeUnit(to_unit.lower())
        except ValueError:
            raise ValueError(f"Invalid volume units: {from_unit} or {to_unit}")
        
        # Convert to base unit (ml), then to target unit
        base_quantity = quantity * self.volume_conversions[from_enum]
        converted_quantity = base_quantity / self.volume_conversions[to_enum]
        
        return ConversionResult(
            original_quantity=quantity,
            original_unit=from_unit,
            converted_quantity=smart_round(converted_quantity, to_unit),
            converted_unit=to_unit,
            conversion_factor=self.volume_conversions[from_enum] / self.volume_conversions[to_enum]
        )
    
    def convert_weight(self, quantity: float, from_unit: str, to_unit: str) -> ConversionResult:
        """Convert between weight units."""
        try:
            from_enum = WeightUnit(from_unit.lower())
            to_enum = WeightUnit(to_unit.lower())
        except ValueError:
            raise ValueError(f"Invalid weight units: {from_unit} or {to_unit}")
        
        # Convert to base unit (g), then to target unit
        base_quantity = quantity * self.weight_conversions[from_enum]
        converted_quantity = base_quantity / self.weight_conversions[to_enum]
        
        return ConversionResult(
            original_quantity=quantity,
            original_unit=from_unit,
            converted_quantity=smart_round(converted_quantity, to_unit),
            converted_unit=to_unit,
            conversion_factor=self.weight_conversions[from_enum] / self.weight_conversions[to_enum]
        )
    
    def convert_temperature(self, temperature: float, from_unit: str, to_unit: str) -> ConversionResult:
        """Convert between temperature units."""
        from_unit = from_unit.upper()
        to_unit = to_unit.upper()
        
        if from_unit == to_unit:
            return ConversionResult(
                original_quantity=temperature,
                original_unit=from_unit,
                converted_quantity=temperature,
                converted_unit=to_unit,
                conversion_factor=1.0
            )
        
        if from_unit == "F" and to_unit == "C":
            converted = (temperature - 32) * 5/9
        elif from_unit == "C" and to_unit == "F":
            converted = (temperature * 9/5) + 32
        else:
            raise ValueError(f"Invalid temperature units: {from_unit} or {to_unit}")
        
        return ConversionResult(
            original_quantity=temperature,
            original_unit=from_unit,
            converted_quantity=round(converted, 1),
            converted_unit=to_unit,
            conversion_factor=0.0  # Not applicable for temperature
        )
    
    def volume_to_weight(self, quantity: float, volume_unit: str, ingredient_name: str) -> Optional[ConversionResult]:
        """Convert volume to weight using ingredient density."""
        ingredient_key = self._find_ingredient_key(ingredient_name)
        if not ingredient_key:
            return None
        
        density = self.ingredient_densities[ingredient_key]
        
        # Convert volume to ml first
        try:
            volume_enum = VolumeUnit(volume_unit.lower())
            volume_ml = quantity * self.volume_conversions[volume_enum]
        except ValueError:
            return None
        
        # Convert to grams using density
        weight_g = volume_ml * density
        
        return ConversionResult(
            original_quantity=quantity,
            original_unit=volume_unit,
            converted_quantity=smart_round(weight_g, "g"),
            converted_unit="g",
            ingredient_name=ingredient_name,
            conversion_factor=density,
            is_approximation=True,
            notes=f"Approximation based on typical density of {ingredient_name}"
        )
    
    def weight_to_volume(self, quantity: float, weight_unit: str, ingredient_name: str) -> Optional[ConversionResult]:
        """Convert weight to volume using ingredient density."""
        ingredient_key = self._find_ingredient_key(ingredient_name)
        if not ingredient_key:
            return None
        
        density = self.ingredient_densities[ingredient_key]
        
        # Convert weight to grams first
        try:
            weight_enum = WeightUnit(weight_unit.lower())
            weight_g = quantity * self.weight_conversions[weight_enum]
        except ValueError:
            return None
        
        # Convert to ml using density
        volume_ml = weight_g / density
        
        return ConversionResult(
            original_quantity=quantity,
            original_unit=weight_unit,
            converted_quantity=smart_round(volume_ml, "ml"),
            converted_unit="ml",
            ingredient_name=ingredient_name,
            conversion_factor=1/density,
            is_approximation=True,
            notes=f"Approximation based on typical density of {ingredient_name}"
        )
    
    def _find_ingredient_key(self, ingredient_name: str) -> Optional[str]:
        """Find ingredient key in density database."""
        ingredient_lower = ingredient_name.lower()
        
        # Direct match
        if ingredient_lower in self.ingredient_densities:
            return ingredient_lower
        
        # Partial match
        for key in self.ingredient_densities:
            if key in ingredient_lower or ingredient_lower in key:
                return key
        
        return None
    
    def get_best_unit_for_quantity(self, quantity: float, current_unit: str) -> str:
        """Suggest best unit for a given quantity."""
        # For very small quantities, use smaller units
        if quantity < 1:
            if current_unit in ["cup", "l"]:
                return "ml"
            elif current_unit in ["lb", "kg"]:
                return "g"
        
        # For large quantities, use larger units
        elif quantity > 1000:
            if current_unit in ["ml", "g"]:
                return "l" if current_unit == "ml" else "kg"
        
        return current_unit