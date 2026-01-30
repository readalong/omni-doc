"""CLI interface for Omni-Doc using Typer."""

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from omni_doc import __version__
from omni_doc.config import get_settings
from omni_doc.utils.logging import setup_logging, get_logger


def is_ci_environment() -> bool:
    """Detect if running in CI environment."""
    return any([
        os.environ.get("CI") == "true",
        os.environ.get("GITHUB_ACTIONS") == "true",
        os.environ.get("GITLAB_CI") == "true",
        os.environ.get("JENKINS_URL") is not None,
        os.environ.get("CIRCLECI") == "true",
    ])


def set_github_output(name: str, value: str) -> None:
    """Set GitHub Actions output variable."""
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"{name}={value}\n")


app = typer.Typer(
    name="omni-doc",
    help="AI-powered documentation analysis for GitHub pull requests.",
    add_completion=False,
)

# Use simple console in CI, rich console otherwise
_is_ci = is_ci_environment()
console = Console(force_terminal=not _is_ci, no_color=_is_ci)
logger = get_logger(__name__)


@app.command()
def analyze(
    pr_url: str = typer.Argument(
        ...,
        help="GitHub PR URL to analyze (e.g., https://github.com/owner/repo/pull/123)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-d",
        help="Don't post comment to GitHub, just output the report",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Write markdown report to file",
    ),
    no_diagrams: bool = typer.Option(
        False,
        "--no-diagrams",
        help="Disable Mermaid diagram generation",
    ),
) -> None:
    """Analyze a GitHub pull request for documentation issues.

    This command fetches the PR, scans the repository for documentation,
    and generates a report identifying discrepancies, missing docs, and
    opportunities for improvement.
    """
    # Setup logging
    log_level = "DEBUG" if verbose else get_settings().log_level
    setup_logging(log_level)

    # CI-friendly output
    if _is_ci:
        print(f"::group::Omni-Doc Analysis v{__version__}")
        print(f"Analyzing: {pr_url}")
    else:
        console.print()
        console.print(Panel.fit(
            f"[bold blue]Omni-Doc[/bold blue] v{__version__}\n"
            f"[dim]Analyzing: {pr_url}[/dim]",
            border_style="blue",
        ))
        console.print()

    # Run the analysis
    try:
        # Import here to avoid circular imports
        from omni_doc.graph import run_analysis

        # Run the async analysis
        if _is_ci:
            print("Running analysis...")
        else:
            console.print("[dim]Running analysis...[/dim]")

        final_state = asyncio.run(
            run_analysis(
                pr_url=pr_url,
                dry_run=dry_run,
                enable_diagrams=not no_diagrams,
            )
        )

        # Save report immediately if requested (before any display that might fail)
        markdown_report = final_state.get("markdown_report")
        if output and markdown_report:
            output.write_text(markdown_report, encoding="utf-8")
            if _is_ci:
                print(f"Report saved to: {output}")
            else:
                console.print(f"[green]Report saved to: {output}[/green]")

        # Check for errors
        errors = final_state.get("errors", [])
        if errors:
            if _is_ci:
                print("::endgroup::")
                for error in errors:
                    print(f"::error::{error}")
            else:
                console.print()
                console.print("[bold red]Errors occurred during analysis:[/bold red]")
                for error in errors:
                    console.print(f"  [red]- {error}[/red]")
            raise typer.Exit(1)

        # Get the report
        comment_url = final_state.get("comment_url")
        findings = final_state.get("findings", [])

        # Set GitHub Actions outputs
        if _is_ci:
            set_github_output("findings-count", str(len(findings)))
            if comment_url and comment_url != "[dry-run]":
                set_github_output("comment-url", comment_url)

        # Severity breakdown
        severity_counts = {}
        for f in findings:
            sev = f.get("severity", "info")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        # Summary output
        if _is_ci:
            print(f"Analysis complete! Total Findings: {len(findings)}")
            for sev in ["critical", "high", "medium", "low", "info"]:
                count = severity_counts.get(sev, 0)
                if count > 0:
                    print(f"  {sev}: {count}")
            if comment_url and comment_url != "[dry-run]":
                print(f"Comment URL: {comment_url}")
            elif dry_run:
                print("Dry run - comment not posted")
            print("::endgroup::")
        else:
            console.print()
            console.print(f"[bold green]Analysis complete![/bold green]")
            console.print(f"  Findings: {len(findings)}")

            if severity_counts:
                console.print("  Severity breakdown:")
                for sev in ["critical", "high", "medium", "low", "info"]:
                    count = severity_counts.get(sev, 0)
                    if count > 0:
                        console.print(f"    {sev}: {count}")

            if comment_url:
                if comment_url == "[dry-run]":
                    console.print("  [yellow]Dry run - comment not posted[/yellow]")
                else:
                    console.print(f"  Comment: {comment_url}")

        # Print report preview if dry-run (skip in CI to reduce noise)
        if dry_run and markdown_report and not _is_ci:
            console.print()
            console.print("[bold]Report Preview:[/bold]")
            console.print("-" * 60)
            # Truncate long reports
            preview = markdown_report[:2000]
            if len(markdown_report) > 2000:
                preview += "\n\n... [truncated] ..."
            console.print(preview)

        if not _is_ci:
            console.print()

    except KeyboardInterrupt:
        console.print("\n[yellow]Analysis cancelled by user[/yellow]")
        raise typer.Exit(130)
    except Exception as e:
        logger.exception("Analysis failed")
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


@app.command()
def config() -> None:
    """Display current configuration settings."""
    try:
        settings = get_settings()
    except Exception as e:
        console.print(f"[bold red]Error loading config:[/bold red] {e}")
        console.print("\nMake sure you have a .env file with required variables.")
        console.print("See .env.example for template.")
        raise typer.Exit(1)

    console.print()
    console.print("[bold]Current Configuration[/bold]")
    console.print()

    # Display settings (mask sensitive values)
    config_items = [
        ("GitHub Token", "***" + settings.github_token.get_secret_value()[-4:] if settings.github_token else "Not set"),
        ("Google API Key", "***" + settings.google_api_key.get_secret_value()[-4:] if settings.google_api_key else "Not set"),
        ("Gemini Model", settings.gemini_model),
        ("Max Retries", str(settings.max_retries)),
        ("Enable Diagrams", str(settings.enable_diagrams)),
        ("Log Level", settings.log_level),
        ("MCP Server Port", str(settings.mcp_server_port)),
    ]

    for name, value in config_items:
        console.print(f"  {name}: [cyan]{value}[/cyan]")

    console.print()


@app.command()
def version() -> None:
    """Display version information."""
    console.print(f"omni-doc version {__version__}")


@app.command()
def serve(
    port: Optional[int] = typer.Option(
        None,
        "--port",
        "-p",
        help="Port for HTTP transport (default from config)",
    ),
    stdio: bool = typer.Option(
        False,
        "--stdio",
        help="Use stdio transport instead of HTTP",
    ),
) -> None:
    """Start the Omni-Doc MCP server.

    The MCP server exposes documentation analysis as tools that can be
    called by LLM clients like Claude Desktop.

    Tools exposed:
    - analyze_pr: Start analysis for a PR
    - get_analysis_status: Check analysis progress
    - list_findings: Get findings from completed analysis
    - get_analysis_result: Get full analysis results
    """
    setup_logging(get_settings().log_level)

    console.print()
    console.print(Panel.fit(
        f"[bold blue]Omni-Doc MCP Server[/bold blue] v{__version__}",
        border_style="blue",
    ))

    if stdio:
        console.print("Starting in stdio mode...")
    else:
        actual_port = port or get_settings().mcp_server_port
        console.print(f"Starting on port {actual_port}...")

    console.print()

    try:
        from omni_doc.mcp.server import mcp

        # Run the MCP server
        mcp.run()

    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped[/yellow]")
    except Exception as e:
        logger.exception("Server error")
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
