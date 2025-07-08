"""
LLM Integration for Agents
"""
from typing import Optional, Dict, Any, Union
from abc import ABC, abstractmethod
import logging
from enum import Enum
import time
import random
from dataclasses import dataclass

from config.settings import Settings

@dataclass
class LLMUsage:
    """Tracks LLM usage statistics."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    response_time_ms: int = 0

try:
    import anthropic
except ImportError:
    anthropic = None

try:
    import openai
except ImportError:
    openai = None

try:
    import ollama
except ImportError:
    ollama = None

class LLMProvider(Enum):
    """Supported LLM providers."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OLLAMA = "ollama"

class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = logging.getLogger(self.__class__.__name__)
        self.usage_stats = LLMUsage()
        
        # Cost per 1k tokens (rough estimates)
        self.cost_per_1k_input = 0.0
        self.cost_per_1k_output = 0.0
    
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text using the LLM."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the LLM client is available."""
        pass
    
    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on token usage."""
        input_cost = (input_tokens / 1000) * self.cost_per_1k_input
        output_cost = (output_tokens / 1000) * self.cost_per_1k_output
        return input_cost + output_cost
    
    def _retry_with_backoff(self, func, max_retries: int = 3, initial_delay: float = 1.0):
        """Retry function with exponential backoff."""
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                
                delay = initial_delay * (2 ** attempt) + random.uniform(0, 1)
                self.logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s...")
                time.sleep(delay)
        
        raise Exception("Max retries exceeded")

class AnthropicClient(BaseLLMClient):
    """Anthropic Claude client."""
    
    def __init__(self, settings: Settings):
        super().__init__(settings)
        if not anthropic:
            raise ImportError("anthropic package not available")
        
        self.client = anthropic.Anthropic(
            api_key=settings.llm.anthropic_api_key
        )
        self.model = settings.llm.anthropic_model or "claude-3-haiku-20240307"
        
        # Set cost estimates (as of 2024)
        if "haiku" in self.model:
            self.cost_per_1k_input = 0.00025
            self.cost_per_1k_output = 0.00125
        elif "sonnet" in self.model:
            self.cost_per_1k_input = 0.003
            self.cost_per_1k_output = 0.015
        elif "opus" in self.model:
            self.cost_per_1k_input = 0.015
            self.cost_per_1k_output = 0.075
    
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text using Claude."""
        def _generate():
            start_time = time.time()
            response = self.client.messages.create(
                model=self.model,
                max_tokens=kwargs.get('max_tokens', self.settings.llm.max_tokens),
                messages=[{"role": "user", "content": prompt}],
                temperature=kwargs.get('temperature', self.settings.llm.temperature)
            )
            
            # Track usage
            usage = response.usage
            input_tokens = usage.input_tokens
            output_tokens = usage.output_tokens
            total_tokens = input_tokens + output_tokens
            
            cost = self._calculate_cost(input_tokens, output_tokens)
            response_time = int((time.time() - start_time) * 1000)
            
            # Update stats
            self.usage_stats.input_tokens += input_tokens
            self.usage_stats.output_tokens += output_tokens
            self.usage_stats.total_tokens += total_tokens
            self.usage_stats.cost_usd += cost
            self.usage_stats.response_time_ms += response_time
            
            self.logger.info(f"Generated {output_tokens} tokens in {response_time}ms (cost: ${cost:.4f})")
            return response.content[0].text
        
        try:
            return self._retry_with_backoff(_generate)
        except Exception as e:
            self.logger.error(f"Anthropic API error: {e}")
            raise
    
    def is_available(self) -> bool:
        """Check if Anthropic client is available."""
        return bool(anthropic and self.settings.llm.anthropic_api_key)

class OpenAIClient(BaseLLMClient):
    """OpenAI GPT client."""
    
    def __init__(self, settings: Settings):
        super().__init__(settings)
        if not openai:
            raise ImportError("openai package not available")
        
        self.client = openai.OpenAI(
            api_key=settings.llm.openai_api_key
        )
        self.model = settings.llm.openai_model or "gpt-3.5-turbo"
        
        # Set cost estimates (as of 2024)
        if "gpt-3.5-turbo" in self.model:
            self.cost_per_1k_input = 0.0015
            self.cost_per_1k_output = 0.002
        elif "gpt-4" in self.model:
            self.cost_per_1k_input = 0.01
            self.cost_per_1k_output = 0.03
        elif "gpt-4-turbo" in self.model:
            self.cost_per_1k_input = 0.01
            self.cost_per_1k_output = 0.03
    
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text using GPT."""
        def _generate():
            start_time = time.time()
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=kwargs.get('max_tokens', self.settings.llm.max_tokens),
                temperature=kwargs.get('temperature', self.settings.llm.temperature)
            )
            
            # Track usage
            usage = response.usage
            input_tokens = usage.prompt_tokens
            output_tokens = usage.completion_tokens
            total_tokens = usage.total_tokens
            
            cost = self._calculate_cost(input_tokens, output_tokens)
            response_time = int((time.time() - start_time) * 1000)
            
            # Update stats
            self.usage_stats.input_tokens += input_tokens
            self.usage_stats.output_tokens += output_tokens
            self.usage_stats.total_tokens += total_tokens
            self.usage_stats.cost_usd += cost
            self.usage_stats.response_time_ms += response_time
            
            self.logger.info(f"Generated {output_tokens} tokens in {response_time}ms (cost: ${cost:.4f})")
            return response.choices[0].message.content
        
        try:
            return self._retry_with_backoff(_generate)
        except Exception as e:
            self.logger.error(f"OpenAI API error: {e}")
            raise
    
    def is_available(self) -> bool:
        """Check if OpenAI client is available."""
        return bool(openai and self.settings.llm.openai_api_key)

class OllamaClient(BaseLLMClient):
    """Ollama local LLM client."""
    
    def __init__(self, settings: Settings):
        super().__init__(settings)
        if not ollama:
            raise ImportError("ollama package not available")
        
        self.client = ollama.Client(host=settings.llm.ollama_host)
        self.model = settings.llm.ollama_model or "llama3.1:8b"
    
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text using Ollama."""
        try:
            response = self.client.generate(
                model=self.model,
                prompt=prompt,
                stream=False,
                options={
                    'temperature': kwargs.get('temperature', 0.7),
                    'num_predict': kwargs.get('max_tokens', 1000)
                }
            )
            return response['response']
        except Exception as e:
            self.logger.error(f"Ollama API error: {e}")
            raise
    
    def is_available(self) -> bool:
        """Check if Ollama client is available."""
        try:
            if not ollama:
                return False
            # Try to connect to Ollama
            models = self.client.list()
            return True
        except Exception:
            return False

class LLMManager:
    """Manages LLM clients and provides unified interface."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = logging.getLogger(self.__class__.__name__)
        self.clients: Dict[LLMProvider, BaseLLMClient] = {}
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize available LLM clients."""
        try:
            if self.settings.llm.anthropic_api_key:
                self.clients[LLMProvider.ANTHROPIC] = AnthropicClient(self.settings)
        except Exception as e:
            self.logger.warning(f"Failed to initialize Anthropic client: {e}")
        
        try:
            if self.settings.llm.openai_api_key:
                self.clients[LLMProvider.OPENAI] = OpenAIClient(self.settings)
        except Exception as e:
            self.logger.warning(f"Failed to initialize OpenAI client: {e}")
        
        try:
            self.clients[LLMProvider.OLLAMA] = OllamaClient(self.settings)
        except Exception as e:
            self.logger.warning(f"Failed to initialize Ollama client: {e}")
    
    def get_client(self, provider: Union[LLMProvider, str, None] = None) -> BaseLLMClient:
        """Get LLM client by provider."""
        if provider is None:
            provider = LLMProvider(self.settings.llm.default_provider)
        elif isinstance(provider, str):
            provider = LLMProvider(provider)
        
        if provider not in self.clients:
            raise ValueError(f"LLM provider {provider.value} not available")
        
        return self.clients[provider]
    
    def generate(self, prompt: str, provider: Union[LLMProvider, str, None] = None, **kwargs) -> str:
        """Generate text using specified or default provider."""
        client = self.get_client(provider)
        return client.generate(prompt, **kwargs)
    
    def get_available_providers(self) -> list[LLMProvider]:
        """Get list of available LLM providers."""
        return [provider for provider, client in self.clients.items() if client.is_available()]
    
    def get_usage_stats(self) -> Dict[str, LLMUsage]:
        """Get usage statistics for all providers."""
        return {
            provider.value: client.usage_stats 
            for provider, client in self.clients.items()
        }
    
    def get_total_cost(self) -> float:
        """Get total cost across all providers."""
        return sum(client.usage_stats.cost_usd for client in self.clients.values())
    
    def reset_usage_stats(self):
        """Reset usage statistics for all providers."""
        for client in self.clients.values():
            client.usage_stats = LLMUsage()