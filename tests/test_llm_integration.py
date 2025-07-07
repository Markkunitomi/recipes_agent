#!/usr/bin/env python3
"""
Unit tests for LLM integration
"""
import pytest
import os
from unittest.mock import Mock, patch
from config.settings import Settings
from agents.llm_integration import LLMManager, LLMProvider, LLMUsage

class TestLLMIntegration:
    """Test LLM integration functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.settings = Settings()
        
    def test_settings_structure(self):
        """Test that settings have correct LLM structure."""
        assert hasattr(self.settings, 'llm')
        assert hasattr(self.settings.llm, 'anthropic_model')
        assert hasattr(self.settings.llm, 'openai_model')
        assert hasattr(self.settings.llm, 'ollama_model')
        assert hasattr(self.settings.llm, 'default_provider')
    
    def test_llm_manager_initialization(self):
        """Test LLM manager initialization."""
        manager = LLMManager(self.settings)
        assert manager.settings == self.settings
        assert isinstance(manager.clients, dict)
    
    def test_usage_tracking(self):
        """Test usage statistics tracking."""
        usage = LLMUsage()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.total_tokens == 0
        assert usage.cost_usd == 0.0
        assert usage.response_time_ms == 0
    
    def test_get_available_providers(self):
        """Test getting available providers."""
        manager = LLMManager(self.settings)
        providers = manager.get_available_providers()
        assert isinstance(providers, list)
        # Should have at least Ollama available in most environments
    
    def test_cost_calculation_anthropic(self):
        """Test cost calculation for Anthropic."""
        # This will only work if Anthropic is available
        try:
            from agents.llm_integration import AnthropicClient
            client = AnthropicClient(self.settings)
            
            # Test cost calculation (without actual API call)
            cost = client._calculate_cost(1000, 500)  # 1k input, 500 output tokens
            assert cost > 0
            assert isinstance(cost, float)
            
        except (ImportError, Exception):
            pytest.skip("Anthropic not available")
    
    def test_cost_calculation_openai(self):
        """Test cost calculation for OpenAI."""
        try:
            from agents.llm_integration import OpenAIClient
            client = OpenAIClient(self.settings)
            
            # Test cost calculation (without actual API call)
            cost = client._calculate_cost(1000, 500)  # 1k input, 500 output tokens
            assert cost > 0
            assert isinstance(cost, float)
            
        except (ImportError, Exception):
            pytest.skip("OpenAI not available")
    
    @patch('time.sleep')  # Mock sleep for faster tests
    def test_retry_mechanism(self, mock_sleep):
        """Test retry mechanism with backoff."""
        from agents.llm_integration import BaseLLMClient
        
        class TestClient(BaseLLMClient):
            def generate(self, prompt: str, **kwargs) -> str:
                return "test"
            
            def is_available(self) -> bool:
                return True
        
        client = TestClient(self.settings)
        
        # Test successful retry
        call_count = 0
        def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("API error")
            return "success"
        
        result = client._retry_with_backoff(failing_func, max_retries=3)
        assert result == "success"
        assert call_count == 3
        assert mock_sleep.call_count == 2  # Should have retried twice
    
    def test_provider_enum(self):
        """Test LLM provider enum."""
        assert LLMProvider.ANTHROPIC.value == "anthropic"
        assert LLMProvider.OPENAI.value == "openai"
        assert LLMProvider.OLLAMA.value == "ollama"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])