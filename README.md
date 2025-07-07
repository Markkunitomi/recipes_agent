# Recipe Agent System

Multi-agent system for recipe management with web scraping, parsing, normalization, and output generation.

## Features

- Web scraping from recipe websites
- Intelligent ingredient parsing with ML
- Recipe normalization and cleaning
- Unit conversion (metric/imperial/weight)
- HTML and LaTeX output generation
- LLM-powered processing (API + local via Ollama)

## Architecture

- **Scraper Agent**: Extracts recipe data from websites
- **Parser Agent**: Structures ingredients and instructions
- **Normalizer Agent**: Cleans and standardizes data
- **Converter Agent**: Handles unit conversions
- **Renderer Agent**: Generates HTML/LaTeX output
- **Orchestrator**: Coordinates the pipeline

## Dependencies

- recipe-scrapers: Web scraping
- ingredient-parser-nlp: ML-based ingredient parsing
- anthropic/openai: LLM APIs
- ollama: Local LLM integration
- pydantic: Data modeling
- rich: Enhanced CLI output

## Setup

```bash
source ~/auto_setup_env.sh
pip install -r requirements.txt
```

## Usage

```bash
# Process a single recipe
python main.py "https://example.com/recipe" --output-format html

# Run system tests
python tests/test_system.py

# Run batch processing
python scripts/batch_test.py

# See examples
python examples/example.py
```

## Directory Structure

```
recipes_agent/
├── main.py              # Main CLI entry point
├── orchestrator.py      # Multi-agent orchestrator
├── agents/              # Individual agent implementations
├── models/              # Data models and schemas
├── config/              # Configuration management
├── templates/           # Output templates (HTML, LaTeX)
├── tests/               # System tests
├── examples/            # Usage examples
├── scripts/             # Utility scripts
├── output/              # Generated recipe outputs
└── utils/               # Helper utilities
```