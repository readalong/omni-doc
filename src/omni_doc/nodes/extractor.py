"""Extractor node for fetching PR diff and metadata."""

from omni_doc.github.client import GitHubClient
from omni_doc.github.pr_fetcher import PRFetcher
from omni_doc.models.state import OmniDocState
from omni_doc.utils.logging import get_logger, GitHubAPIError

logger = get_logger(__name__)


async def extract_pr_diff(state: OmniDocState) -> dict:
    """Extract PR diff and metadata from GitHub.

    This node:
    1. Parses the PR URL to get owner/repo/number
    2. Fetches PR metadata (title, author, branches, etc.)
    3. Fetches file changes with patches

    Args:
        state: Current workflow state with pr_url

    Returns:
        State update with pr_metadata and file_changes
    """
    pr_url = state["pr_url"]
    logger.info(f"Extracting PR data from: {pr_url}")

    try:
        # Parse PR URL
        owner, repo, pr_number = GitHubClient.parse_pr_url_sync(pr_url)
        logger.info(f"Parsed PR: {owner}/{repo}#{pr_number}")

        # Fetch PR details
        fetcher = PRFetcher()
        pr_metadata, file_changes = await fetcher.fetch_pr_details(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
        )

        logger.info(
            f"Extracted PR '{pr_metadata['title']}' with {len(file_changes)} file changes"
        )

        return {
            "pr_metadata": pr_metadata,
            "file_changes": file_changes,
        }

    except GitHubAPIError as e:
        logger.error(f"GitHub API error: {e}")
        return {
            "errors": [f"Failed to extract PR data: {e.message}"],
        }
    except Exception as e:
        logger.exception("Unexpected error extracting PR data")
        return {
            "errors": [f"Unexpected error extracting PR data: {str(e)}"],
        }
