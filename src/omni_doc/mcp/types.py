"""MCP-specific type definitions for Omni-Doc.

For GitHub API types, see the official GitHub MCP Server:
https://github.com/github/github-mcp-server
"""

from typing import Optional
from pydantic import BaseModel, Field


# Omni-Doc MCP Server Input/Output Types

class AnalyzePRInput(BaseModel):
    """Input for analyzing a PR."""

    pr_url: str = Field(..., description="Full GitHub PR URL to analyze")
    dry_run: bool = Field(default=False, description="If true, don't post comment to GitHub")
    enable_diagrams: bool = Field(default=True, description="Enable Mermaid diagram generation")


class AnalysisStatusOutput(BaseModel):
    """Output for analysis status check."""

    analysis_id: str = Field(..., description="Analysis ID")
    status: str = Field(..., description="Status (pending, running, completed, failed)")
    progress: float = Field(default=0.0, description="Progress percentage (0-100)")
    current_step: Optional[str] = Field(default=None, description="Current processing step")
    error: Optional[str] = Field(default=None, description="Error message if failed")


class FindingSummary(BaseModel):
    """Summary of a single finding."""

    id: str = Field(..., description="Finding ID")
    type: str = Field(..., description="Finding type")
    severity: str = Field(..., description="Severity level")
    title: str = Field(..., description="Finding title")
    file_path: Optional[str] = Field(default=None, description="Related file path")


class ListFindingsOutput(BaseModel):
    """Output for listing findings."""

    analysis_id: str = Field(..., description="Analysis ID")
    findings: list[FindingSummary] = Field(default_factory=list, description="List of findings")
    total_count: int = Field(default=0, description="Total number of findings")


class AnalysisResultOutput(BaseModel):
    """Complete analysis result output."""

    analysis_id: str = Field(..., description="Analysis ID")
    pr_url: str = Field(..., description="Analyzed PR URL")
    status: str = Field(..., description="Analysis status")
    markdown_report: Optional[str] = Field(default=None, description="Full markdown report")
    findings_count: int = Field(default=0, description="Number of findings")
    comment_url: Optional[str] = Field(default=None, description="GitHub comment URL if posted")
