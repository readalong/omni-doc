"""Omni-Doc MCP Server exposing documentation analysis as tools."""

import asyncio
import uuid
from typing import Any, Optional

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from omni_doc.mcp.types import (
    AnalysisResultOutput,
    AnalysisStatusOutput,
    AnalyzePRInput,
    FindingSummary,
    ListFindingsOutput,
)
from omni_doc.utils.logging import get_logger

logger = get_logger(__name__)

# Create the FastMCP server
mcp = FastMCP("omni-doc-server")

# In-memory storage for analysis results (would use a proper store in production)
_analyses: dict[str, dict[str, Any]] = {}


class AnalysisState(BaseModel):
    """Internal state for tracking an analysis."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pr_url: str
    status: str = "pending"
    progress: float = 0.0
    current_step: Optional[str] = None
    error: Optional[str] = None
    result: Optional[dict[str, Any]] = None


@mcp.tool()
async def analyze_pr(
    pr_url: str,
    dry_run: bool = False,
    enable_diagrams: bool = True,
) -> AnalysisStatusOutput:
    """Start documentation analysis for a GitHub pull request.

    This initiates an asynchronous analysis of the PR's documentation impact.
    Use get_analysis_status to check progress.

    Args:
        pr_url: Full GitHub PR URL (e.g., https://github.com/owner/repo/pull/123)
        dry_run: If true, don't post comment to GitHub
        enable_diagrams: If true, generate Mermaid diagrams for complex flows

    Returns:
        AnalysisStatusOutput with analysis ID and initial status
    """
    analysis_id = str(uuid.uuid4())
    analysis = AnalysisState(
        id=analysis_id,
        pr_url=pr_url,
        status="pending",
        current_step="initializing",
    )
    _analyses[analysis_id] = analysis.model_dump()

    # Start analysis in background
    asyncio.create_task(_run_analysis(analysis_id, pr_url, dry_run, enable_diagrams))

    return AnalysisStatusOutput(
        analysis_id=analysis_id,
        status="pending",
        progress=0.0,
        current_step="initializing",
    )


async def _run_analysis(
    analysis_id: str,
    pr_url: str,
    dry_run: bool,
    enable_diagrams: bool,
) -> None:
    """Run the actual analysis workflow.

    Args:
        analysis_id: Analysis ID
        pr_url: PR URL to analyze
        dry_run: Whether to skip posting comment
        enable_diagrams: Whether to generate diagrams
    """
    try:
        _update_analysis(analysis_id, status="running", progress=10.0, current_step="extracting PR data")

        # Import here to avoid circular imports
        from omni_doc.graph.main_graph import build_main_graph
        from omni_doc.models.state import create_initial_state

        # Build the graph
        graph = build_main_graph()

        # Create initial state
        initial_state = create_initial_state(
            pr_url=pr_url,
            dry_run=dry_run,
            enable_diagrams=enable_diagrams,
        )

        # Run the graph with progress updates
        _update_analysis(analysis_id, status="running", progress=20.0, current_step="running analysis workflow")

        # Execute the graph
        final_state = await graph.ainvoke(initial_state)

        # Extract results
        findings = final_state.get("findings", [])
        markdown_report = final_state.get("markdown_report")
        comment_url = final_state.get("comment_url")
        errors = final_state.get("errors", [])

        if errors:
            _update_analysis(
                analysis_id,
                status="failed",
                progress=100.0,
                error="; ".join(errors),
            )
        else:
            _update_analysis(
                analysis_id,
                status="completed",
                progress=100.0,
                current_step="done",
                result={
                    "findings": findings,
                    "markdown_report": markdown_report,
                    "comment_url": comment_url,
                },
            )

    except Exception as e:
        logger.exception("Analysis failed")
        _update_analysis(
            analysis_id,
            status="failed",
            progress=100.0,
            error=str(e),
        )


def _update_analysis(
    analysis_id: str,
    status: Optional[str] = None,
    progress: Optional[float] = None,
    current_step: Optional[str] = None,
    error: Optional[str] = None,
    result: Optional[dict[str, Any]] = None,
) -> None:
    """Update analysis state."""
    if analysis_id not in _analyses:
        return

    if status is not None:
        _analyses[analysis_id]["status"] = status
    if progress is not None:
        _analyses[analysis_id]["progress"] = progress
    if current_step is not None:
        _analyses[analysis_id]["current_step"] = current_step
    if error is not None:
        _analyses[analysis_id]["error"] = error
    if result is not None:
        _analyses[analysis_id]["result"] = result


@mcp.tool()
async def get_analysis_status(analysis_id: str) -> AnalysisStatusOutput:
    """Check the status of a running or completed analysis.

    Args:
        analysis_id: Analysis ID from analyze_pr

    Returns:
        AnalysisStatusOutput with current status and progress
    """
    if analysis_id not in _analyses:
        return AnalysisStatusOutput(
            analysis_id=analysis_id,
            status="not_found",
            error="Analysis not found",
        )

    analysis = _analyses[analysis_id]
    return AnalysisStatusOutput(
        analysis_id=analysis_id,
        status=analysis["status"],
        progress=analysis["progress"],
        current_step=analysis.get("current_step"),
        error=analysis.get("error"),
    )


@mcp.tool()
async def list_findings(analysis_id: str) -> ListFindingsOutput:
    """List findings from a completed analysis.

    Args:
        analysis_id: Analysis ID from analyze_pr

    Returns:
        ListFindingsOutput with findings summary
    """
    if analysis_id not in _analyses:
        return ListFindingsOutput(
            analysis_id=analysis_id,
            findings=[],
            total_count=0,
        )

    analysis = _analyses[analysis_id]
    result = analysis.get("result", {})
    findings_data = result.get("findings", [])

    findings = []
    for i, f in enumerate(findings_data):
        findings.append(
            FindingSummary(
                id=f.get("id", str(i)),
                type=f.get("finding_type", "unknown"),
                severity=f.get("severity", "info"),
                title=f.get("title", "Untitled"),
                file_path=f.get("file_path"),
            )
        )

    return ListFindingsOutput(
        analysis_id=analysis_id,
        findings=findings,
        total_count=len(findings),
    )


@mcp.tool()
async def get_analysis_result(analysis_id: str) -> AnalysisResultOutput:
    """Get complete results from a finished analysis.

    Args:
        analysis_id: Analysis ID from analyze_pr

    Returns:
        AnalysisResultOutput with full analysis results
    """
    if analysis_id not in _analyses:
        return AnalysisResultOutput(
            analysis_id=analysis_id,
            pr_url="",
            status="not_found",
        )

    analysis = _analyses[analysis_id]
    result = analysis.get("result", {})

    return AnalysisResultOutput(
        analysis_id=analysis_id,
        pr_url=analysis["pr_url"],
        status=analysis["status"],
        markdown_report=result.get("markdown_report"),
        findings_count=len(result.get("findings", [])),
        comment_url=result.get("comment_url"),
    )


@mcp.resource("analysis://{analysis_id}")
async def get_analysis_resource(analysis_id: str) -> str:
    """Access analysis results as a resource.

    Args:
        analysis_id: Analysis ID

    Returns:
        Markdown report or status message
    """
    if analysis_id not in _analyses:
        return f"Analysis {analysis_id} not found"

    analysis = _analyses[analysis_id]
    if analysis["status"] != "completed":
        return f"Analysis {analysis_id} status: {analysis['status']}"

    result = analysis.get("result", {})
    return result.get("markdown_report", "No report generated")


@mcp.prompt()
def doc_review_prompt(pr_url: str) -> str:
    """Generate a documentation review prompt for a PR.

    Args:
        pr_url: GitHub PR URL

    Returns:
        Prompt text for documentation review
    """
    return f"""Please analyze the documentation impact of this pull request:

PR URL: {pr_url}

Tasks:
1. Extract the PR diff and identify code changes
2. Find all relevant documentation files in the repository
3. Identify discrepancies between code changes and documentation
4. Suggest documentation updates or new documentation needed
5. Generate diagrams for complex flows if applicable

Focus on:
- API documentation accuracy
- README updates needed
- Configuration documentation
- Code comments and docstrings
- Architectural documentation

Report any issues found with severity levels (critical, high, medium, low, info).
"""


def run_server() -> None:
    """Run the Omni-Doc MCP server."""
    logger.info("Starting Omni-Doc MCP Server...")
    mcp.run()


if __name__ == "__main__":
    run_server()
