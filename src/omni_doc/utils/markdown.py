"""Markdown formatting utilities for Omni-Doc output."""

from typing import Optional


def format_table(headers: list[str], rows: list[list[str]]) -> str:
    """Format data as a markdown table.

    Args:
        headers: List of column headers.
        rows: List of row data (each row is a list of cell values).

    Returns:
        str: Formatted markdown table.
    """
    if not headers:
        return ""

    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(str(cell)))

    # Build header row
    header_row = "| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |"
    separator = "| " + " | ".join("-" * w for w in widths) + " |"

    # Build data rows
    data_rows = []
    for row in rows:
        padded = [str(cell).ljust(widths[i]) if i < len(widths) else str(cell) for i, cell in enumerate(row)]
        data_rows.append("| " + " | ".join(padded) + " |")

    return "\n".join([header_row, separator] + data_rows)


def format_code_block(code: str, language: str = "") -> str:
    """Format code as a markdown code block.

    Args:
        code: The code content.
        language: Optional language identifier for syntax highlighting.

    Returns:
        str: Formatted markdown code block.
    """
    return f"```{language}\n{code}\n```"


def format_collapsible(summary: str, content: str) -> str:
    """Format content as a collapsible details section.

    Args:
        summary: The summary text shown when collapsed.
        content: The content shown when expanded.

    Returns:
        str: Formatted HTML details element for markdown.
    """
    return f"<details>\n<summary>{summary}</summary>\n\n{content}\n\n</details>"


def format_mermaid_diagram(diagram: str) -> str:
    """Format a Mermaid diagram as a markdown code block.

    Args:
        diagram: The Mermaid diagram definition.

    Returns:
        str: Formatted markdown Mermaid code block.
    """
    return format_code_block(diagram.strip(), "mermaid")


def get_severity_icon(severity: str) -> str:
    """Get the appropriate icon for a severity level.

    Args:
        severity: Severity level (critical, high, medium, low, info).

    Returns:
        str: Emoji icon for the severity.
    """
    icons = {
        "critical": ":red_circle:",
        "high": ":orange_circle:",
        "medium": ":yellow_circle:",
        "low": ":white_circle:",
        "info": ":blue_circle:",
    }
    return icons.get(severity.lower(), ":white_circle:")


def format_finding(
    finding_type: str,
    title: str,
    description: str,
    severity: str,
    file_path: Optional[str] = None,
    target_section: Optional[str] = None,
    recommended_update: Optional[str] = None,
) -> str:
    """Format a single finding as markdown.

    Args:
        finding_type: Type of finding (discrepancy, missing_doc, diagram, etc.).
        title: Finding title.
        description: Finding description.
        severity: Severity level.
        file_path: Optional file path related to the finding.
        target_section: Optional target section in the documentation file.
        recommended_update: Optional copy-paste ready documentation text.

    Returns:
        str: Formatted markdown for the finding.
    """
    icon = get_severity_icon(severity)
    parts = [f"### {icon} {title}"]

    # Location info on one line
    location_parts = []
    if file_path:
        location_parts.append(f"`{file_path}`")
    if target_section:
        location_parts.append(f"→ **{target_section}**")
    if location_parts:
        parts.append(" ".join(location_parts))

    parts.append("")
    parts.append(description)

    if recommended_update:
        parts.append("")
        parts.append("**Recommended Update:**")
        parts.append(format_code_block(recommended_update.strip(), "markdown"))

    return "\n".join(parts)
