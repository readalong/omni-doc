"""PR Fetcher for extracting PR diff and metadata."""

from typing import Optional

from omni_doc.github.client import GitHubClient, get_github_client
from omni_doc.models.state import FileChange, PRMetadata
from omni_doc.utils.logging import get_logger, GitHubAPIError

logger = get_logger(__name__)


class PRFetcher:
    """Fetches PR data from GitHub using the GitHub API client."""

    def __init__(self, github_client: Optional[GitHubClient] = None) -> None:
        """Initialize the PR fetcher.

        Args:
            github_client: Optional GitHub client. If not provided,
                          will use the global client.
        """
        self._client = github_client

    async def _get_client(self) -> GitHubClient:
        """Get the GitHub client."""
        if self._client is None:
            self._client = await get_github_client()
        return self._client

    async def fetch_pr_details(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> tuple[PRMetadata, list[FileChange]]:
        """Fetch PR metadata and file changes.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            Tuple of (PRMetadata, list of FileChange)

        Raises:
            GitHubAPIError: If fetch fails
        """
        client = await self._get_client()

        try:
            logger.info(f"Fetching PR details: {owner}/{repo}#{pr_number}")
            pr_details = await client.get_pr_details(owner, repo, pr_number)

            # Convert to state types
            pr_metadata: PRMetadata = {
                "owner": owner,
                "repo": repo,
                "pr_number": pr_number,
                "title": pr_details["title"],
                "body": pr_details["body"],
                "state": pr_details["state"],
                "base_branch": pr_details["base_branch"],
                "head_branch": pr_details["head_branch"],
                "author": pr_details["author"],
                "created_at": pr_details["created_at"],
                "updated_at": pr_details["updated_at"],
                "commits_count": pr_details["commits_count"],
                "comments_count": pr_details["comments_count"],
            }

            file_changes: list[FileChange] = []
            for file in pr_details["files"]:
                file_changes.append({
                    "filename": file["filename"],
                    "status": file["status"],
                    "additions": file["additions"],
                    "deletions": file["deletions"],
                    "patch": file["patch"],
                    "previous_filename": file["previous_filename"],
                })

            logger.info(f"Fetched {len(file_changes)} file changes")
            return pr_metadata, file_changes

        except Exception as e:
            logger.error(f"Failed to fetch PR details: {e}")
            raise GitHubAPIError(
                f"Failed to fetch PR {owner}/{repo}#{pr_number}: {e}"
            ) from e

    async def fetch_file_content(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: Optional[str] = None,
    ) -> Optional[str]:
        """Fetch content of a file from the repository.

        Args:
            owner: Repository owner
            repo: Repository name
            path: File path
            ref: Git ref (optional)

        Returns:
            File content as string, or None if file not found

        Raises:
            GitHubAPIError: If fetch fails (except 404)
        """
        client = await self._get_client()

        try:
            result = await client.get_file_content(owner, repo, path, ref)
            return result["content"]
        except GitHubAPIError as e:
            if "not found" in str(e).lower() or "404" in str(e):
                logger.debug(f"File not found: {path}")
                return None
            raise

    async def get_repo_tree(
        self,
        owner: str,
        repo: str,
        ref: Optional[str] = None,
    ) -> list[str]:
        """Get list of all file paths in repository.

        Args:
            owner: Repository owner
            repo: Repository name
            ref: Git ref (optional)

        Returns:
            List of file paths

        Raises:
            GitHubAPIError: If fetch fails
        """
        client = await self._get_client()

        try:
            logger.info(f"Fetching repo tree: {owner}/{repo}")
            tree = await client.get_repo_tree(owner, repo, ref)

            # Filter to only blob (file) entries
            file_paths = [
                entry["path"]
                for entry in tree["entries"]
                if entry["type"] == "blob"
            ]

            logger.info(f"Found {len(file_paths)} files in repository")
            return file_paths

        except Exception as e:
            logger.error(f"Failed to fetch repo tree: {e}")
            raise GitHubAPIError(f"Failed to fetch repo tree: {e}") from e


# Global fetcher instance
_pr_fetcher: Optional[PRFetcher] = None


async def get_pr_fetcher() -> PRFetcher:
    """Get or create the global PR fetcher.

    Returns:
        PRFetcher instance
    """
    global _pr_fetcher
    if _pr_fetcher is None:
        _pr_fetcher = PRFetcher()
    return _pr_fetcher
