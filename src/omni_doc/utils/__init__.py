"""Utility functions for Omni-Doc."""

from omni_doc.utils.logging import setup_logging, get_logger, OmniDocError, GitHubAPIError, LLMError
from omni_doc.utils.markdown import format_table, format_code_block, format_collapsible

__all__ = [
    "setup_logging",
    "get_logger",
    "OmniDocError",
    "GitHubAPIError",
    "LLMError",
    "format_table",
    "format_code_block",
    "format_collapsible",
]
