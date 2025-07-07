"""
Recipe Processing Orchestrator
"""
import time
from typing import Optional
from pathlib import Path
from dataclasses import dataclass

from config.settings import Settings
from models.recipe import Recipe
from agents.scraper import ScraperAgent
from agents.parser import ParserAgent
from agents.normalizer import NormalizerAgent
from agents.converter import ConverterAgent
from agents.renderer import RendererAgent
from utils.debug_output import create_debug_directory, save_agent_debug, save_debug_summary

@dataclass
class ProcessingResult:
    """Result of recipe processing."""
    success: bool
    recipe: Optional[Recipe] = None
    output_path: Optional[Path] = None
    error: Optional[str] = None
    debug_dir: Optional[Path] = None

class RecipeOrchestrator:
    """Orchestrates the multi-agent recipe processing pipeline."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.scraper = ScraperAgent(settings)
        self.parser = ParserAgent(settings)
        self.normalizer = NormalizerAgent(settings)
        self.converter = ConverterAgent(settings)
        self.renderer = RendererAgent(settings)
    
    def process_recipe(
        self, 
        url: str, 
        output_format: str = "html",
        output_dir: Optional[Path] = None,
        debug_enabled: bool = False,
        debug_dir: str = "./debug"
    ) -> ProcessingResult:
        """Process a recipe through the complete pipeline."""
        
        start_time = time.time()
        debug_path = None
        agent_results = {}
        
        try:
            # Initialize debug directory if enabled
            if debug_enabled:
                debug_path = create_debug_directory(debug_dir, url)
            
            # Step 1: Scrape recipe from URL
            step_start = time.time()
            scrape_result = self.scraper.scrape(url)
            step_time = time.time() - step_start
            
            if debug_enabled:
                save_agent_debug(
                    debug_path, "scraper", 1, url, scrape_result.success,
                    scrape_result.data, scrape_result.metadata, 
                    scrape_result.error, step_time
                )
                agent_results["scraper"] = {
                    "success": scrape_result.success,
                    "processing_time_ms": round(step_time * 1000),
                    "error": scrape_result.error
                }
            
            if not scrape_result.success:
                if debug_enabled:
                    save_debug_summary(debug_path, url, False, time.time() - start_time, agent_results)
                return ProcessingResult(False, error=f"Scraping failed: {scrape_result.error}", debug_dir=debug_path)
            
            # Step 2: Parse structured data
            step_start = time.time()
            parse_result = self.parser.parse(scrape_result.data)
            step_time = time.time() - step_start
            
            if debug_enabled:
                save_agent_debug(
                    debug_path, "parser", 2, url, parse_result.success,
                    parse_result.data, parse_result.metadata,
                    parse_result.error, step_time
                )
                agent_results["parser"] = {
                    "success": parse_result.success,
                    "processing_time_ms": round(step_time * 1000),
                    "error": parse_result.error
                }
            
            if not parse_result.success:
                if debug_enabled:
                    save_debug_summary(debug_path, url, False, time.time() - start_time, agent_results)
                return ProcessingResult(False, error=f"Parsing failed: {parse_result.error}", debug_dir=debug_path)
            
            # Step 3: Normalize and clean data
            step_start = time.time()
            normalize_result = self.normalizer.normalize(parse_result.data)
            step_time = time.time() - step_start
            
            if debug_enabled:
                save_agent_debug(
                    debug_path, "normalizer", 3, url, normalize_result.success,
                    normalize_result.data, normalize_result.metadata,
                    normalize_result.error, step_time
                )
                agent_results["normalizer"] = {
                    "success": normalize_result.success,
                    "processing_time_ms": round(step_time * 1000),
                    "error": normalize_result.error
                }
            
            if not normalize_result.success:
                if debug_enabled:
                    save_debug_summary(debug_path, url, False, time.time() - start_time, agent_results)
                return ProcessingResult(False, error=f"Normalization failed: {normalize_result.error}", debug_dir=debug_path)
            
            # Step 4: Convert units as needed
            step_start = time.time()
            convert_result = self.converter.convert(normalize_result.data)
            step_time = time.time() - step_start
            
            if debug_enabled:
                save_agent_debug(
                    debug_path, "converter", 4, url, convert_result.success,
                    convert_result.data, convert_result.metadata,
                    convert_result.error, step_time
                )
                agent_results["converter"] = {
                    "success": convert_result.success,
                    "processing_time_ms": round(step_time * 1000),
                    "error": convert_result.error
                }
            
            if not convert_result.success:
                if debug_enabled:
                    save_debug_summary(debug_path, url, False, time.time() - start_time, agent_results)
                return ProcessingResult(False, error=f"Conversion failed: {convert_result.error}", debug_dir=debug_path)
            
            # Step 5: Always generate JSON first (canonical format)
            step_start = time.time()
            json_result = self.renderer.render(
                convert_result.data, 
                "json", 
                output_dir
            )
            step_time = time.time() - step_start
            
            if debug_enabled:
                save_agent_debug(
                    debug_path, "renderer_json", 5, url, json_result.success,
                    json_result.data, json_result.metadata,
                    json_result.error, step_time
                )
                agent_results["renderer_json"] = {
                    "success": json_result.success,
                    "processing_time_ms": round(step_time * 1000),
                    "error": json_result.error
                }
            
            if not json_result.success:
                if debug_enabled:
                    save_debug_summary(debug_path, url, False, time.time() - start_time, agent_results)
                return ProcessingResult(False, error=f"JSON rendering failed: {json_result.error}", debug_dir=debug_path)
            
            # Step 6: If a different format is requested, derive it from JSON
            final_output_path = json_result.data.output_path
            if output_format.lower() != "json":
                step_start = time.time()
                format_result = self.renderer.render_from_json(
                    json_result.data.output_path,
                    output_format,
                    output_dir
                )
                step_time = time.time() - step_start
                
                if debug_enabled:
                    save_agent_debug(
                        debug_path, f"renderer_{output_format}", 6, url, format_result.success,
                        format_result.data, format_result.metadata,
                        format_result.error, step_time
                    )
                    agent_results[f"renderer_{output_format}"] = {
                        "success": format_result.success,
                        "processing_time_ms": round(step_time * 1000),
                        "error": format_result.error
                    }
                
                if not format_result.success:
                    if debug_enabled:
                        save_debug_summary(debug_path, url, False, time.time() - start_time, agent_results)
                    return ProcessingResult(False, error=f"{output_format} rendering failed: {format_result.error}", debug_dir=debug_path)
                
                final_output_path = format_result.data.output_path
            
            # Success - save debug summary
            total_time = time.time() - start_time
            if debug_enabled:
                save_debug_summary(debug_path, url, True, total_time, agent_results)
            
            return ProcessingResult(
                success=True,
                recipe=convert_result.data,
                output_path=final_output_path,
                debug_dir=debug_path
            )
            
        except Exception as e:
            total_time = time.time() - start_time
            if debug_enabled:
                save_debug_summary(debug_path, url, False, total_time, agent_results)
            return ProcessingResult(False, error=str(e), debug_dir=debug_path)