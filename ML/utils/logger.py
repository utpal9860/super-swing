"""
Logging utilities for ML Pattern Trading System
"""
import logging
import sys
from pathlib import Path
from config import LOGGING_CONFIG, LOGS_DIR

def setup_logger(name: str, log_file: str = None, level: str = None) -> logging.Logger:
    """
    Setup logger with file and console handlers
    
    Args:
        name: Logger name
        log_file: Log file path (optional)
        level: Logging level (optional)
    
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level or LOGGING_CONFIG["level"])
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger
    
    # Create formatters
    formatter = logging.Formatter(LOGGING_CONFIG["format"])
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        file_path = Path(log_file)
    else:
        file_path = LOGS_DIR / f"{name}.log"
    
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(file_path)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger

# Create default logger
default_logger = setup_logger("ml_system")

