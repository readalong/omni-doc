"""LangGraph nodes for Omni-Doc workflow."""

from omni_doc.nodes.extractor import extract_pr_diff
from omni_doc.nodes.discovery import discover_documentation
from omni_doc.nodes.repo_scanner import scan_repository
from omni_doc.nodes.auditor import analyze_changes
from omni_doc.nodes.critic import validate_analysis
from omni_doc.nodes.aggregator import generate_markdown, post_github_comment

__all__ = [
    "extract_pr_diff",
    "discover_documentation",
    "scan_repository",
    "analyze_changes",
    "validate_analysis",
    "generate_markdown",
    "post_github_comment",
]
