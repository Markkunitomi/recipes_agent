"""
LangGraph-based Recipe Processing Orchestrator
"""
import time
from typing import Dict, Any, Optional, TypedDict, Annotated
from pathlib import Path
from dataclasses import dataclass

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from config.settings import Settings
from models.recipe import Recipe
from agents.scraper import ScraperAgent
from agents.parser import ParserAgent
from agents.normalizer import NormalizerAgent
from agents.converter import ConverterAgent
from agents.renderer import RendererAgent
from utils.debug_output import create_debug_directory, save_agent_debug, save_debug_summary

# Define the state structure for the graph
class RecipeProcessingState(TypedDict):
    """State object for recipe processing workflow."""
    # Input parameters
    url: str
    output_format: str
    output_dir: Optional[Path]
    debug_enabled: bool
    debug_dir: Optional[Path]
    
    # Processing state
    current_step: str
    recipe_data: Optional[Recipe]
    
    # Results and metadata
    success: bool
    error: Optional[str]
    output_path: Optional[Path]
    
    # Debug and timing
    debug_path: Optional[Path]
    agent_results: Dict[str, Dict[str, Any]]
    start_time: float
    
    # Messages for LangGraph
    messages: Annotated[list, add_messages]

@dataclass
class LangGraphProcessingResult:
    """Result of LangGraph-based recipe processing."""
    success: bool
    recipe: Optional[Recipe] = None
    output_path: Optional[Path] = None
    error: Optional[str] = None
    debug_dir: Optional[Path] = None
    agent_results: Optional[Dict[str, Dict[str, Any]]] = None
    total_time: Optional[float] = None

class LangGraphRecipeOrchestrator:
    """LangGraph-based orchestrator for recipe processing pipeline."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        
        # Initialize agents
        self.scraper = ScraperAgent(settings)
        self.parser = ParserAgent(settings)
        self.normalizer = NormalizerAgent(settings)
        self.converter = ConverterAgent(settings)
        self.renderer = RendererAgent(settings)
        
        # Build the workflow graph
        self.workflow = self._build_workflow()
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow."""
        
        # Create state graph
        workflow = StateGraph(RecipeProcessingState)
        
        # Add nodes for each processing step
        workflow.add_node("initialize", self._initialize_processing)
        workflow.add_node("scrape", self._scrape_recipe)
        workflow.add_node("parse", self._parse_recipe)
        workflow.add_node("normalize", self._normalize_recipe)
        workflow.add_node("convert", self._convert_units)
        workflow.add_node("render", self._render_output)
        workflow.add_node("finalize", self._finalize_processing)
        
        # Define the workflow edges
        workflow.add_edge(START, "initialize")
        workflow.add_edge("initialize", "scrape")
        
        # Conditional routing: if scraping fails, end workflow
        workflow.add_conditional_edges(
            "scrape",
            self._should_continue_after_scrape,
            {
                "continue": "parse",
                "end": "finalize"
            }
        )
        
        workflow.add_conditional_edges(
            "parse",
            self._should_continue_after_parse,
            {
                "continue": "normalize",
                "end": "finalize"
            }
        )
        
        workflow.add_conditional_edges(
            "normalize",
            self._should_continue_after_normalize,
            {
                "continue": "convert",
                "end": "finalize"
            }
        )
        
        workflow.add_conditional_edges(
            "convert",
            self._should_continue_after_convert,
            {
                "continue": "render",
                "end": "finalize"
            }
        )
        
        workflow.add_edge("render", "finalize")
        workflow.add_edge("finalize", END)
        
        return workflow.compile()
    
    def _initialize_processing(self, state: RecipeProcessingState) -> RecipeProcessingState:
        """Initialize the processing workflow."""
        state["current_step"] = "initialize"
        state["start_time"] = time.time()
        state["agent_results"] = {}
        state["success"] = True
        state["messages"] = []
        
        # Initialize debug directory if enabled
        if state["debug_enabled"]:
            state["debug_path"] = create_debug_directory(
                state["debug_dir"] or "./debug", 
                state["url"]
            )
        
        state["messages"].append({
            "role": "system",
            "content": f"Starting recipe processing for URL: {state['url']}"
        })
        
        return state
    
    def _scrape_recipe(self, state: RecipeProcessingState) -> RecipeProcessingState:
        """Scrape recipe from URL."""
        state["current_step"] = "scrape"
        step_start = time.time()
        
        try:
            # Run scraper agent
            scrape_result = self.scraper.scrape(state["url"])
            step_time = time.time() - step_start
            
            # Record results
            state["agent_results"]["scraper"] = {
                "success": scrape_result.success,
                "processing_time_ms": round(step_time * 1000),
                "error": scrape_result.error
            }
            
            if scrape_result.success:
                state["recipe_data"] = scrape_result.data
                recipe_title = scrape_result.data.get('title', 'Unknown Recipe')
                state["messages"].append({
                    "role": "system",
                    "content": f"Successfully scraped recipe: {recipe_title}"
                })
            else:
                state["success"] = False
                state["error"] = f"Scraping failed: {scrape_result.error}"
                state["messages"].append({
                    "role": "system",
                    "content": f"Scraping failed: {scrape_result.error}"
                })
            
            # Save debug info
            if state["debug_enabled"]:
                save_agent_debug(
                    state["debug_path"], "scraper", 1, state["url"],
                    scrape_result.success, scrape_result.data,
                    scrape_result.metadata, scrape_result.error, step_time
                )
                
        except Exception as e:
            state["success"] = False
            state["error"] = f"Scraping error: {str(e)}"
            state["agent_results"]["scraper"] = {
                "success": False,
                "processing_time_ms": round((time.time() - step_start) * 1000),
                "error": str(e)
            }
        
        return state
    
    def _parse_recipe(self, state: RecipeProcessingState) -> RecipeProcessingState:
        """Parse recipe ingredients and instructions."""
        state["current_step"] = "parse"
        step_start = time.time()
        
        try:
            parse_result = self.parser.parse(state["recipe_data"])
            step_time = time.time() - step_start
            
            state["agent_results"]["parser"] = {
                "success": parse_result.success,
                "processing_time_ms": round(step_time * 1000),
                "error": parse_result.error
            }
            
            if parse_result.success:
                state["recipe_data"] = parse_result.data
                state["messages"].append({
                    "role": "system",
                    "content": f"Successfully parsed {len(parse_result.data.ingredients)} ingredients"
                })
            else:
                state["success"] = False
                state["error"] = f"Parsing failed: {parse_result.error}"
            
            # Save debug info
            if state["debug_enabled"]:
                save_agent_debug(
                    state["debug_path"], "parser", 2, state["url"],
                    parse_result.success, parse_result.data,
                    parse_result.metadata, parse_result.error, step_time
                )
                
        except Exception as e:
            state["success"] = False
            state["error"] = f"Parsing error: {str(e)}"
            state["agent_results"]["parser"] = {
                "success": False,
                "processing_time_ms": round((time.time() - step_start) * 1000),
                "error": str(e)
            }
        
        return state
    
    def _normalize_recipe(self, state: RecipeProcessingState) -> RecipeProcessingState:
        """Normalize and enhance recipe data."""
        state["current_step"] = "normalize"
        step_start = time.time()
        
        try:
            normalize_result = self.normalizer.normalize(state["recipe_data"])
            step_time = time.time() - step_start
            
            state["agent_results"]["normalizer"] = {
                "success": normalize_result.success,
                "processing_time_ms": round(step_time * 1000),
                "error": normalize_result.error
            }
            
            if normalize_result.success:
                state["recipe_data"] = normalize_result.data
                quality_score = normalize_result.metadata.get("quality_score", 0)
                state["messages"].append({
                    "role": "system",
                    "content": f"Recipe normalized with quality score: {quality_score:.2f}"
                })
            else:
                state["success"] = False
                state["error"] = f"Normalization failed: {normalize_result.error}"
            
            # Save debug info
            if state["debug_enabled"]:
                save_agent_debug(
                    state["debug_path"], "normalizer", 3, state["url"],
                    normalize_result.success, normalize_result.data,
                    normalize_result.metadata, normalize_result.error, step_time
                )
                
        except Exception as e:
            state["success"] = False
            state["error"] = f"Normalization error: {str(e)}"
            state["agent_results"]["normalizer"] = {
                "success": False,
                "processing_time_ms": round((time.time() - step_start) * 1000),
                "error": str(e)
            }
        
        return state
    
    def _convert_units(self, state: RecipeProcessingState) -> RecipeProcessingState:
        """Convert recipe units."""
        state["current_step"] = "convert"
        step_start = time.time()
        
        try:
            convert_result = self.converter.convert(state["recipe_data"])
            step_time = time.time() - step_start
            
            state["agent_results"]["converter"] = {
                "success": convert_result.success,
                "processing_time_ms": round(step_time * 1000),
                "error": convert_result.error
            }
            
            if convert_result.success:
                state["recipe_data"] = convert_result.data
                conversions = convert_result.metadata.get("conversions_made", 0)
                state["messages"].append({
                    "role": "system",
                    "content": f"Converted {conversions} ingredient units"
                })
            else:
                state["success"] = False
                state["error"] = f"Unit conversion failed: {convert_result.error}"
            
            # Save debug info
            if state["debug_enabled"]:
                save_agent_debug(
                    state["debug_path"], "converter", 4, state["url"],
                    convert_result.success, convert_result.data,
                    convert_result.metadata, convert_result.error, step_time
                )
                
        except Exception as e:
            state["success"] = False
            state["error"] = f"Conversion error: {str(e)}"
            state["agent_results"]["converter"] = {
                "success": False,
                "processing_time_ms": round((time.time() - step_start) * 1000),
                "error": str(e)
            }
        
        return state
    
    def _render_output(self, state: RecipeProcessingState) -> RecipeProcessingState:
        """Render final output - always JSON first, then derive other formats."""
        state["current_step"] = "render"
        step_start = time.time()
        
        try:
            # Step 1: Always generate JSON first (canonical format)
            json_result = self.renderer.render(
                state["recipe_data"],
                "json",
                state["output_dir"]
            )
            step_time = time.time() - step_start
            
            state["agent_results"]["renderer_json"] = {
                "success": json_result.success,
                "processing_time_ms": round(step_time * 1000),
                "error": json_result.error
            }
            
            if not json_result.success:
                state["success"] = False
                state["error"] = f"JSON rendering failed: {json_result.error}"
                return state
            
            # Save debug info for JSON
            if state["debug_enabled"]:
                save_agent_debug(
                    state["debug_path"], "renderer_json", 5, state["url"],
                    json_result.success, json_result.data,
                    json_result.metadata, json_result.error, step_time
                )
            
            # Step 2: If a different format is requested, derive it from JSON
            final_output_path = json_result.data.output_path
            if state["output_format"].lower() != "json":
                step_start = time.time()
                format_result = self.renderer.render_from_json(
                    json_result.data.output_path,
                    state["output_format"],
                    state["output_dir"]
                )
                step_time = time.time() - step_start
                
                state["agent_results"][f"renderer_{state['output_format']}"] = {
                    "success": format_result.success,
                    "processing_time_ms": round(step_time * 1000),
                    "error": format_result.error
                }
                
                if not format_result.success:
                    state["success"] = False
                    state["error"] = f"{state['output_format']} rendering failed: {format_result.error}"
                    return state
                
                final_output_path = format_result.data.output_path
                
                # Save debug info for format
                if state["debug_enabled"]:
                    save_agent_debug(
                        state["debug_path"], f"renderer_{state['output_format']}", 6, state["url"],
                        format_result.success, format_result.data,
                        format_result.metadata, format_result.error, step_time
                    )
            
            # Success
            state["output_path"] = final_output_path
            state["messages"].append({
                "role": "system",
                "content": f"Successfully rendered {state['output_format']} output (derived from JSON)"
            })
                
        except Exception as e:
            state["success"] = False
            state["error"] = f"Rendering error: {str(e)}"
            state["agent_results"]["renderer"] = {
                "success": False,
                "processing_time_ms": round((time.time() - step_start) * 1000),
                "error": str(e)
            }
        
        return state
    
    def _finalize_processing(self, state: RecipeProcessingState) -> RecipeProcessingState:
        """Finalize processing and save debug summary."""
        state["current_step"] = "finalize"
        total_time = time.time() - state["start_time"]
        
        if state["debug_enabled"]:
            save_debug_summary(
                state["debug_path"], 
                state["url"], 
                state["success"], 
                total_time, 
                state["agent_results"]
            )
        
        state["messages"].append({
            "role": "system",
            "content": f"Processing completed in {total_time:.2f}s. Success: {state['success']}"
        })
        
        return state
    
    # Conditional edge functions
    def _should_continue_after_scrape(self, state: RecipeProcessingState) -> str:
        """Determine if workflow should continue after scraping."""
        return "continue" if state["success"] else "end"
    
    def _should_continue_after_parse(self, state: RecipeProcessingState) -> str:
        """Determine if workflow should continue after parsing."""
        return "continue" if state["success"] else "end"
    
    def _should_continue_after_normalize(self, state: RecipeProcessingState) -> str:
        """Determine if workflow should continue after normalization."""
        return "continue" if state["success"] else "end"
    
    def _should_continue_after_convert(self, state: RecipeProcessingState) -> str:
        """Determine if workflow should continue after conversion."""
        return "continue" if state["success"] else "end"
    
    def process_recipe(
        self, 
        url: str, 
        output_format: str = "html",
        output_dir: Optional[Path] = None,
        debug_enabled: bool = False,
        debug_dir: str = "./debug"
    ) -> LangGraphProcessingResult:
        """Process a recipe through the LangGraph workflow."""
        
        # Initialize state
        initial_state = RecipeProcessingState(
            url=url,
            output_format=output_format,
            output_dir=output_dir,
            debug_enabled=debug_enabled,
            debug_dir=Path(debug_dir) if debug_dir else None,
            current_step="",
            recipe_data=None,
            success=True,
            error=None,
            output_path=None,
            debug_path=None,
            agent_results={},
            start_time=0.0,
            messages=[]
        )
        
        try:
            # Run the workflow
            final_state = self.workflow.invoke(initial_state)
            
            # Extract results
            return LangGraphProcessingResult(
                success=final_state["success"],
                recipe=final_state["recipe_data"],
                output_path=final_state["output_path"],
                error=final_state["error"],
                debug_dir=final_state["debug_path"],
                agent_results=final_state["agent_results"],
                total_time=time.time() - final_state["start_time"]
            )
            
        except Exception as e:
            return LangGraphProcessingResult(
                success=False,
                error=f"Workflow execution failed: {str(e)}"
            )
    
    def get_workflow_graph(self):
        """Get the workflow graph for visualization."""
        return self.workflow