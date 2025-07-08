#!/usr/bin/env python3
"""
Recipe Agent System - Main Entry Point
"""
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.main import app

if __name__ == "__main__":
    app()