"""Logging configuration and custom exceptions for Omni-Doc."""

import logging
import sys
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler


class OmniDocError(Exception):
    """Base exception for Omni-Doc errors."""

    def __init__(self, message: str, details: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class GitHubAPIError(OmniDocError):
    """Exception raised for GitHub API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        details: Optional[str] = None,
    ) -> None:
        super().__init__(message, details)
        self.status_code = status_code


class LLMError(OmniDocError):
    """Exception raised for LLM/Gemini errors."""

    def __init__(
        self,
        message: str,
        model: Optional[str] = None,
        details: Optional[str] = None,
    ) -> None:
        super().__init__(message, details)
        self.model = model


class MCPError(OmniDocError):
    """Exception raised for MCP communication errors."""

    def __init__(
        self,
        message: str,
        tool_name: Optional[str] = None,
        details: Optional[str] = None,
    ) -> None:
        super().__init__(message, details)
        self.tool_name = tool_name


class ValidationError(OmniDocError):
    """Exception raised when validation fails."""

    pass


def setup_logging(level: str = "INFO") -> None:
    """Configure application logging with Rich handler.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR).
    """
    console = Console(stderr=True)

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                console=console,
                rich_tracebacks=True,
                tracebacks_show_locals=True,
                show_path=False,
            )
        ],
    )

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)
    logging.getLogger("langgraph").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name.

    Args:
        name: Logger name, typically __name__ of the calling module.

    Returns:
        logging.Logger: Configured logger instance.
    """
    return logging.getLogger(name)
