"""Utility functions."""
import logging
import sys
from pathlib import Path


def setup_logging(level="INFO"):
    """Configure logging for the application."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)


def ensure_dir(path):
    """Ensure a directory exists."""
    Path(path).mkdir(parents=True, exist_ok=True)
    return path


def sanitize_symbol(symbol):
    """Sanitize symbol for filename use."""
    return symbol.replace(".", "_").replace("/", "_").replace("\\", "_")

