"""
Configuration settings for LLM Guard Bench.
Database paths, result directories, and runtime constants.
"""

from pathlib import Path
import os

# Root project directory (the inner llm-guard-bench folder)
PROJECT_ROOT = Path(__file__).parent.parent

# Database configuration
DB_PATH = PROJECT_ROOT / "results" / "guard_bench.db"

# Results export directory
RESULTS_DIR = PROJECT_ROOT / "results"

# Configuration defaults
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_CONCURRENCY = 1
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_JUDGE_MODEL = "llama-3.1-8b-instant"

# API endpoints
OLLAMA_ENDPOINT = os.getenv("OLLAMA_ENDPOINT", DEFAULT_OLLAMA_BASE_URL)
GROQ_API_ENDPOINT = "https://api.groq.com/openai/v1"

# Ensure paths exist
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
