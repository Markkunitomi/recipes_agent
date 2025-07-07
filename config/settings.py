"""
Configuration Management
"""
import os
from typing import Optional, Dict, Any
from pathlib import Path
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings
import json
from dotenv import load_dotenv

class LLMSettings(BaseModel):
    """LLM configuration."""
    # API Keys
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    
    # Model Configuration
    anthropic_model: str = "claude-3-haiku-20240307"
    openai_model: str = "gpt-3.5-turbo"
    
    # Ollama Configuration
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    
    # Default Provider
    default_provider: str = "anthropic"
    
    # Generation Parameters
    temperature: float = 0.7
    max_tokens: int = 1000
    timeout: int = 30

class ScrapingSettings(BaseModel):
    """Web scraping configuration."""
    user_agent: str = "RecipeAgent/1.0 (Educational Use)"
    timeout: int = 10
    max_retries: int = 3
    retry_delay: float = 1.0
    max_content_length: int = 10 * 1024 * 1024  # 10MB

class ProcessingSettings(BaseModel):
    """Recipe processing configuration."""
    # Ingredient parsing
    min_ingredient_confidence: float = 0.7
    
    # Normalization
    enable_ingredient_normalization: bool = True
    enable_instruction_enhancement: bool = True
    
    # Unit conversion
    preferred_volume_unit: str = "cup"
    preferred_weight_unit: str = "g"
    preferred_temperature_unit: str = "F"
    
    # Quality control
    min_recipe_quality_score: float = 0.6
    require_ingredients: bool = True
    require_instructions: bool = True

class OutputSettings(BaseModel):
    """Output configuration."""
    # Directories
    output_dir: Path = Field(default_factory=lambda: Path("./output"))
    templates_dir: Path = Field(default_factory=lambda: Path("./templates"))
    
    # HTML settings
    html_template: str = "strangetom_style.html"
    include_nutrition: bool = True
    include_metadata: bool = True
    
    # LaTeX settings
    latex_template: str = "cookbook_style.tex"
    latex_compiler: str = "xelatex"
    
    # Image settings
    download_images: bool = True
    image_quality: int = 80
    max_image_size: int = 800

class Settings(BaseSettings):
    """Main application settings."""
    
    # Core settings
    app_name: str = "Recipe Agent System"
    version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"
    
    # Component settings
    llm: LLMSettings = Field(default_factory=LLMSettings)
    scraping: ScrapingSettings = Field(default_factory=ScrapingSettings)
    processing: ProcessingSettings = Field(default_factory=ProcessingSettings)
    output: OutputSettings = Field(default_factory=OutputSettings)
    
    # Environment variables mapping
    anthropic_api_key: Optional[str] = Field(None, env="ANTHROPIC_API_KEY")
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
    ollama_host: Optional[str] = Field(None, env="OLLAMA_HOST")
    ollama_model: Optional[str] = Field(None, env="OLLAMA_MODEL")
    default_llm_provider: str = Field("anthropic", env="DEFAULT_LLM_PROVIDER")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"
    
    def __init__(self, **data):
        super().__init__(**data)
        # Sync environment variables with LLM settings
        if self.anthropic_api_key:
            self.llm.anthropic_api_key = self.anthropic_api_key
        if self.openai_api_key:
            self.llm.openai_api_key = self.openai_api_key
        if self.ollama_host:
            self.llm.ollama_host = self.ollama_host
        if self.ollama_model:
            self.llm.ollama_model = self.ollama_model
        if self.default_llm_provider:
            self.llm.default_provider = self.default_llm_provider
    
    @validator('log_level')
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()
    
    @validator('output')
    def create_output_dirs(cls, v):
        """Create output directories if they don't exist."""
        v.output_dir.mkdir(parents=True, exist_ok=True)
        v.templates_dir.mkdir(parents=True, exist_ok=True)
        return v
    
    @classmethod
    def load(cls, config_file: Optional[Path] = None) -> 'Settings':
        """Load settings from file and environment."""
        # Load environment variables
        load_dotenv()
        
        # Load from config file if provided
        if config_file and config_file.exists():
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            return cls(**config_data)
        
        # Load from default locations
        default_config_paths = [
            Path(".env"),
            Path("config/settings.json"),
            Path("settings.json")
        ]
        
        for config_path in default_config_paths:
            if config_path.exists():
                if config_path.suffix == '.json':
                    with open(config_path, 'r') as f:
                        config_data = json.load(f)
                    return cls(**config_data)
        
        # Return with environment variables and defaults
        return cls()
    
    def save(self, config_file: Path):
        """Save settings to file."""
        config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file, 'w') as f:
            json.dump(self.dict(), f, indent=2, default=str)
    
    def validate_llm_setup(self) -> Dict[str, bool]:
        """Validate LLM configuration."""
        validation = {
            'anthropic_available': bool(self.llm.anthropic_api_key),
            'openai_available': bool(self.llm.openai_api_key),
            'ollama_available': self._check_ollama_availability(),
            'default_provider_valid': self.llm.default_provider in ['anthropic', 'openai', 'ollama']
        }
        return validation
    
    def _check_ollama_availability(self) -> bool:
        """Check if Ollama is available."""
        try:
            import ollama
            client = ollama.Client(host=self.llm.ollama_host)
            models = client.list()
            return True
        except Exception:
            return False
    
    def get_active_llm_provider(self) -> str:
        """Get the active LLM provider based on availability."""
        validation = self.validate_llm_setup()
        
        # Check if default provider is available
        if self.llm.default_provider == 'anthropic' and validation['anthropic_available']:
            return 'anthropic'
        elif self.llm.default_provider == 'openai' and validation['openai_available']:
            return 'openai'
        elif self.llm.default_provider == 'ollama' and validation['ollama_available']:
            return 'ollama'
        
        # Fall back to first available provider
        for provider in ['anthropic', 'openai', 'ollama']:
            if validation[f'{provider}_available']:
                return provider
        
        raise ValueError("No LLM provider available")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.dict()
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return self.json(indent=2, default=str)