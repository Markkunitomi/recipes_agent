"""
Base Agent Class and Common Functionality
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TypeVar, Generic
from dataclasses import dataclass
import logging
from enum import Enum

from config.settings import Settings

T = TypeVar('T')

class AgentStatus(Enum):
    """Agent execution status."""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"

@dataclass
class AgentResult(Generic[T]):
    """Standard result format for all agents."""
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    status: AgentStatus = AgentStatus.SUCCESS
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if not self.success:
            self.status = AgentStatus.FAILED

class BaseAgent(ABC):
    """Abstract base class for all agents."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = logging.getLogger(self.__class__.__name__)
        self._setup_logging()
    
    def _setup_logging(self):
        """Configure logging for the agent."""
        log_level = getattr(logging, self.settings.log_level.upper(), logging.INFO)
        self.logger.setLevel(log_level)
        
        # Prevent duplicate logging by not adding handlers if they already exist
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        
        # Prevent propagation to avoid duplicate messages
        self.logger.propagate = False
    
    @abstractmethod
    def process(self, *args, **kwargs) -> AgentResult:
        """
        Main processing method for the agent.
        Must be implemented by subclasses.
        """
        pass
    
    def _handle_error(self, error: Exception, context: str = "") -> AgentResult:
        """Standard error handling for agents."""
        error_msg = f"{context}: {str(error)}" if context else str(error)
        self.logger.error(error_msg)
        return AgentResult(
            success=False, 
            error=error_msg,
            status=AgentStatus.FAILED
        )
    
    def _log_success(self, message: str, data: Any = None) -> None:
        """Log successful operation."""
        self.logger.info(message)
        if data and self.settings.log_level.upper() == "DEBUG":
            self.logger.debug(f"Result data: {data}")
    
    def _validate_input(self, input_data: Any, required_fields: list = None) -> bool:
        """Validate input data."""
        if input_data is None:
            return False
        
        if required_fields and hasattr(input_data, '__dict__'):
            for field in required_fields:
                if not hasattr(input_data, field) or getattr(input_data, field) is None:
                    return False
        
        return True