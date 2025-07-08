"""
Debug Output Utilities
"""
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse
import re


def sanitize_filename(text: str) -> str:
    """Convert text to safe filename."""
    # Remove or replace unsafe characters
    safe_text = re.sub(r'[<>:"/\\|?*]', '', text)
    safe_text = re.sub(r'\s+', '-', safe_text)
    safe_text = safe_text.strip('-').lower()
    # Limit length
    return safe_text[:50] if len(safe_text) > 50 else safe_text


def get_recipe_name_from_url(url: str) -> str:
    """Extract recipe name from URL for debug directory naming."""
    try:
        parsed = urlparse(url)
        path_parts = [part for part in parsed.path.split('/') if part]
        
        # Use the last meaningful part of the path
        if path_parts:
            recipe_name = path_parts[-1]
            # Remove file extensions
            recipe_name = re.sub(r'\.(html?|php|aspx?)$', '', recipe_name)
            return sanitize_filename(recipe_name)
        else:
            return sanitize_filename(parsed.netloc)
    except Exception:
        return "unknown-recipe"


def create_debug_directory(base_dir: str, url: str) -> Path:
    """Create timestamped debug directory for a recipe."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    recipe_name = get_recipe_name_from_url(url)
    
    debug_dir = Path(base_dir) / f"{timestamp}_{recipe_name}"
    debug_dir.mkdir(parents=True, exist_ok=True)
    
    return debug_dir


def save_agent_debug(
    debug_dir: Path,
    agent_name: str,
    step_number: int,
    url: str,
    success: bool,
    output_data: Any,
    metadata: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    processing_time: Optional[float] = None
) -> None:
    """Save agent output to debug file."""
    try:
        debug_data = {
            "agent": agent_name,
            "step": step_number,
            "timestamp": datetime.now().isoformat(),
            "url": url,
            "success": success,
            "processing_time_ms": round(processing_time * 1000) if processing_time else None,
            "output": _serialize_for_json(output_data),
            "metadata": metadata or {},
            "error": error
        }
        
        filename = f"{step_number:02d}_{agent_name}.json"
        filepath = debug_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(debug_data, f, indent=2, ensure_ascii=False, default=str)
            
    except Exception as e:
        # Don't let debug failures break the main processing
        print(f"Warning: Failed to save debug output for {agent_name}: {e}")


def save_debug_summary(
    debug_dir: Path,
    url: str,
    total_success: bool,
    total_time: float,
    agent_results: Dict[str, Any]
) -> None:
    """Save overall processing summary."""
    try:
        summary = {
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "total_success": total_success,
            "total_processing_time_ms": round(total_time * 1000),
            "agent_results": {
                agent: {
                    "success": result.get("success", False),
                    "processing_time_ms": result.get("processing_time_ms"),
                    "error": result.get("error")
                }
                for agent, result in agent_results.items()
            }
        }
        
        filepath = debug_dir / "summary.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
            
    except Exception as e:
        print(f"Warning: Failed to save debug summary: {e}")


def _serialize_for_json(obj: Any) -> Any:
    """Convert objects to JSON-serializable format."""
    try:
        # For complex objects, try to convert to dict
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        # For Pydantic models
        elif hasattr(obj, 'model_dump'):
            return obj.model_dump()
        elif hasattr(obj, 'dict'):
            return obj.dict()
        else:
            return obj
    except Exception:
        return str(obj)