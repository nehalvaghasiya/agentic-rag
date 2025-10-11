"""
Logging configuration module.

Initializes Loguru with settings from config.yaml. Provides structured logging
throughout the application with file rotation, retention, and custom formatting.

This module follows SRP by handling only logging setup and configuration.
"""

from pathlib import Path

from loguru import logger

from rag.config import Config


def setup_logging(config: Config) -> None:
    """
    Configure Loguru logger with settings from configuration.

    Sets up file logging with rotation and retention policies, and configures
    the log format. This should be called once at application startup.

    Args:
        config: Application configuration containing logging settings.

    Example:
        >>> from rag.config import load_config
        >>> from rag.logging_config import setup_logging
        >>> config = load_config()
        >>> setup_logging(config)
        >>> logger.info("Logging is configured")
    """
    # Remove default handler
    logger.remove()

    # Create logs directory if it doesn't exist
    log_path = Path(config.logging.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Add file handler with rotation and retention
    logger.add(
        config.logging.log_file,
        level=config.logging.level,
        format=config.logging.format,
        rotation=config.logging.rotation,
        retention=config.logging.retention,
        enqueue=True,  # Thread-safe logging
        backtrace=True,  # Include full traceback
        diagnose=True,  # Include variable values in tracebacks
    )

    # Add console handler for development
    if config.app.debug:
        logger.add(
            sink=lambda msg: print(msg, end=""),
            level="DEBUG",
            format=config.logging.format,
            colorize=True,
        )

    logger.info(f"Logging initialized: {config.logging.log_file} (level: {config.logging.level})")
