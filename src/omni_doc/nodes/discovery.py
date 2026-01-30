"""Discovery node for determining documentation context sources."""

from omni_doc.models.state import OmniDocState
from omni_doc.utils.logging import get_logger

logger = get_logger(__name__)


async def discover_documentation(state: OmniDocState) -> dict:
    """Discover documentation sources and context to gather.

    This node analyzes the PR metadata to determine what documentation
    context needs to be gathered. In the MVP, it always routes to
    the repo_scanner to scan the repository.

    Future enhancements could:
    - Check for external documentation links in PR description
    - Identify linked documentation sites
    - Check for documentation configs (mkdocs.yml, etc.)

    Args:
        state: Current workflow state with pr_metadata

    Returns:
        State update (currently empty, routes via conditional edge)
    """
    pr_metadata = state.get("pr_metadata")

    if not pr_metadata:
        logger.warning("No PR metadata available for discovery")
        return {}

    logger.info(f"Discovering documentation for PR: {pr_metadata['title']}")

    # Analyze PR body for documentation hints
    pr_body = pr_metadata.get("body") or ""

    # Look for documentation-related keywords
    doc_keywords = [
        "documentation",
        "docs",
        "readme",
        "changelog",
        "api reference",
        "getting started",
        "installation",
        "configuration",
    ]

    found_keywords = [
        kw for kw in doc_keywords
        if kw.lower() in pr_body.lower()
    ]

    if found_keywords:
        logger.info(f"Found documentation keywords in PR body: {found_keywords}")

    # Check file changes for documentation files
    file_changes = state.get("file_changes", [])
    doc_files_changed = [
        fc["filename"] for fc in file_changes
        if _is_doc_related(fc["filename"])
    ]

    if doc_files_changed:
        logger.info(f"Documentation files in PR: {doc_files_changed}")

    # In MVP, we always scan the repository
    # Future: Could return hints about external doc sources here
    return {}


def _is_doc_related(filename: str) -> bool:
    """Check if a filename is documentation-related.

    Args:
        filename: File path

    Returns:
        True if file appears to be documentation
    """
    lower = filename.lower()

    # Check for common doc file patterns
    doc_patterns = [
        "readme",
        "changelog",
        "contributing",
        "license",
        "authors",
        "history",
        "api",
        "docs/",
        "documentation/",
        ".md",
        ".rst",
        ".txt",
    ]

    return any(pattern in lower for pattern in doc_patterns)
