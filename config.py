"""Central configuration for the document watcher/chat system."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent
WATCH_DIR = Path(os.environ.get("WATCH_DIR", BASE_DIR / "incoming"))
DOCS_DIR = Path(os.environ.get("DOCS_DIR", BASE_DIR / "docs"))
LOG_DIR = Path(os.environ.get("LOG_DIR", BASE_DIR / "logs"))
PROCESSED_LOG = LOG_DIR / "processed_files.json"

# --- Supported input extensions for conversion ---
SUPPORTED_EXTENSIONS = {".pdf", ".xlsx", ".xls", ".docx", ".pptx", ".csv"}

# --- Anthropic API ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MODEL_NAME = os.environ.get("MODEL_NAME", "claude-sonnet-4-6")
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "1000"))

# --- Watcher behavior ---
# Debounce: wait this many seconds after last write before treating a file as "settled"
SETTLE_SECONDS = float(os.environ.get("SETTLE_SECONDS", "2.0"))
POLL_INTERVAL = float(os.environ.get("POLL_INTERVAL", "1.0"))

# --- Retry behavior for API calls ---
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))
RETRY_BACKOFF_SECONDS = float(os.environ.get("RETRY_BACKOFF_SECONDS", "2.0"))

for d in (WATCH_DIR, DOCS_DIR, LOG_DIR):
    d.mkdir(parents=True, exist_ok=True)

if not ANTHROPIC_API_KEY:
    raise RuntimeError(
        "ANTHROPIC_API_KEY is not set. Add it to your .env file or environment variables."
    )
