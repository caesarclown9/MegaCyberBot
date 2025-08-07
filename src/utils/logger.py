import logging
import sys
import os
from typing import Any, Dict
import structlog
from structlog.stdlib import LoggerFactory
from src.config import settings


def setup_logging() -> None:
    """Configure structured logging for the application."""
    
    # Force unbuffered output for real-time logs
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(line_buffering=True)
    
    # Set Python to unbuffered mode
    os.environ['PYTHONUNBUFFERED'] = '1'
    
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
        force=True  # Force reconfiguration
    )
    
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    if settings.log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


class LoggerMixin:
    """Mixin class to add logging capabilities to any class."""
    
    @property
    def logger(self) -> structlog.BoundLogger:
        if not hasattr(self, "_logger"):
            self._logger = get_logger(self.__class__.__name__)
        return self._logger
    
    def log_info(self, message: str, **kwargs: Any) -> None:
        self.logger.info(message, **kwargs)
        sys.stdout.flush()  # Force immediate output
    
    def log_error(self, message: str, **kwargs: Any) -> None:
        self.logger.error(message, **kwargs)
        sys.stdout.flush()  # Force immediate output
    
    def log_warning(self, message: str, **kwargs: Any) -> None:
        self.logger.warning(message, **kwargs)
        sys.stdout.flush()  # Force immediate output
    
    def log_debug(self, message: str, **kwargs: Any) -> None:
        self.logger.debug(message, **kwargs)
        sys.stdout.flush()  # Force immediate output