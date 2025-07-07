# Scripts

Utility scripts for batch processing and testing.

## Running Scripts

```bash
# Run batch testing on recipe URLs
python scripts/batch_test.py

# Run from main directory
cd /path/to/recipes_agent
python scripts/batch_test.py
```

## Script Files

- `batch_test.py` - Batch process multiple recipe URLs and generate reports
- `batch_test_results.json` - Latest batch test results

## Requirements

Scripts expect a `recipe_urls.txt` file in the main directory with one URL per line.