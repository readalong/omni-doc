"""GitHub API client for interacting with GitHub.

This module provides direct GitHub API access using httpx.
For AI agents needing GitHub integration, use the official GitHub MCP Server:
https://github.com/github/github-mcp-server
"""

import base64
import re
from typing import Any, Optional

import httpx

from omni_doc.config import get_settings
from omni_doc.utils.logging import get_logger, GitHubAPIError

logger = get_logger(__name__)

# GitHub API base URL
GITHUB_API_BASE = "https://api.github.com"


class GitHubClient:
    """GitHub API client using httpx.

    This provides direct GitHub API access for fetching PR details,
    file contents, and repository structure.

    For AI agents needing GitHub integration, consider using the official
    GitHub MCP Server: https://github.com/github/github-mcp-server
    """

    def __init__(self) -> None:
        """Initialize the GitHub client."""
        self._client: Optional[httpx.AsyncClient] = None

    def _get_headers(self) -> dict[str, str]:
        """Get headers for GitHub API requests."""
        settings = get_settings()
        return {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"Bearer {settings.github_token.get_secret_value()}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers=self._get_headers(),
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def parse_pr_url_sync(url: str) -> tuple[str, str, int]:
        """Parse a GitHub PR URL synchronously.

        Args:
            url: Full GitHub PR URL

        Returns:
            Tuple of (owner, repo, pr_number)

        Raises:
            GitHubAPIError: If URL format is invalid
        """
        pattern = r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)"
        match = re.match(pattern, url)
        if not match:
            raise GitHubAPIError(f"Invalid GitHub PR URL format: {url}")
        return match.group(1), match.group(2), int(match.group(3))

    async def get_pr_details(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> dict[str, Any]:
        """Get PR details including metadata and file changes.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            Dict with PR information including:
            - title, body, state, base_branch, head_branch
            - author, created_at, updated_at
            - commits_count, comments_count
            - files: list of file changes with patches

        Raises:
            GitHubAPIError: If API request fails
        """
        try:
            client = await self._get_client()

            # Fetch PR metadata
            pr_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}"
            pr_response = await client.get(pr_url)
            pr_response.raise_for_status()
            pr_data = pr_response.json()

            # Fetch PR files
            files_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files"
            files_response = await client.get(files_url)
            files_response.raise_for_status()
            files_data = files_response.json()

            # Build file changes list
            file_changes = []
            for file in files_data:
                file_changes.append({
                    "filename": file["filename"],
                    "status": file["status"],
                    "additions": file.get("additions", 0),
                    "deletions": file.get("deletions", 0),
                    "patch": file.get("patch"),
                    "previous_filename": file.get("previous_filename"),
                })

            return {
                "title": pr_data["title"],
                "body": pr_data.get("body"),
                "state": pr_data["state"],
                "base_branch": pr_data["base"]["ref"],
                "head_branch": pr_data["head"]["ref"],
                "author": pr_data["user"]["login"],
                "created_at": pr_data["created_at"],
                "updated_at": pr_data["updated_at"],
                "commits_count": pr_data.get("commits", 0),
                "comments_count": pr_data.get("comments", 0),
                "files": file_changes,
            }

        except httpx.HTTPStatusError as e:
            raise GitHubAPIError(
                f"GitHub API error: {e.response.status_code}",
                details=f"owner={owner}, repo={repo}, pr={pr_number}",
            ) from e
        except Exception as e:
            raise GitHubAPIError(
                f"Failed to fetch PR details: {e}",
                details=f"owner={owner}, repo={repo}, pr={pr_number}",
            ) from e

    async def get_file_content(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get file content from repository.

        Args:
            owner: Repository owner
            repo: Repository name
            path: File path
            ref: Git ref (branch, tag, commit) - optional

        Returns:
            Dict with:
            - path: file path
            - content: decoded file content
            - encoding: always "utf-8"
            - size: file size
            - sha: file sha

        Raises:
            GitHubAPIError: If file not found or API request fails
        """
        try:
            client = await self._get_client()
            url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
            params = {}
            if ref:
                params["ref"] = ref

            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # Decode base64 content
            content = ""
            if data.get("encoding") == "base64" and data.get("content"):
                content = base64.b64decode(data["content"]).decode("utf-8")
            elif data.get("content"):
                content = data["content"]

            return {
                "path": data["path"],
                "content": content,
                "encoding": "utf-8",
                "size": data.get("size", len(content)),
                "sha": data["sha"],
            }

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise GitHubAPIError(
                    f"File not found: {path}",
                    details=f"path={path}",
                ) from e
            raise GitHubAPIError(
                f"GitHub API error: {e.response.status_code}",
                details=f"path={path}",
            ) from e
        except Exception as e:
            raise GitHubAPIError(
                f"Failed to fetch file content: {e}",
                details=f"path={path}",
            ) from e

    async def get_repo_tree(
        self,
        owner: str,
        repo: str,
        ref: Optional[str] = None,
        recursive: bool = True,
    ) -> dict[str, Any]:
        """Get repository file tree.

        Args:
            owner: Repository owner
            repo: Repository name
            ref: Git ref (branch, tag, commit) - optional, defaults to default branch
            recursive: Whether to fetch recursively

        Returns:
            Dict with:
            - entries: list of tree entries (path, type, size, sha)
            - truncated: whether results were truncated

        Raises:
            GitHubAPIError: If API request fails
        """
        try:
            client = await self._get_client()

            # If no ref provided, get default branch
            if not ref:
                repo_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
                repo_response = await client.get(repo_url)
                repo_response.raise_for_status()
                ref = repo_response.json()["default_branch"]

            # Fetch tree
            tree_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/{ref}"
            params = {"recursive": "1"} if recursive else {}
            tree_response = await client.get(tree_url, params=params)
            tree_response.raise_for_status()
            tree_data = tree_response.json()

            entries = []
            for item in tree_data.get("tree", []):
                entries.append({
                    "path": item["path"],
                    "type": item["type"],
                    "size": item.get("size"),
                    "sha": item["sha"],
                })

            return {
                "entries": entries,
                "truncated": tree_data.get("truncated", False),
            }

        except httpx.HTTPStatusError as e:
            raise GitHubAPIError(
                f"GitHub API error: {e.response.status_code}",
                details=f"owner={owner}, repo={repo}",
            ) from e
        except Exception as e:
            raise GitHubAPIError(f"Failed to fetch repo tree: {e}") from e

    async def post_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
        comment_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """Post or update a PR comment.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: PR number
            body: Comment body in markdown
            comment_id: Existing comment ID to update (optional)

        Returns:
            Dict with:
            - comment_id: int
            - url: comment URL
            - created: True if new, False if updated

        Raises:
            GitHubAPIError: If API request fails
        """
        try:
            client = await self._get_client()

            if comment_id:
                # Update existing comment
                url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/comments/{comment_id}"
                response = await client.patch(url, json={"body": body})
                response.raise_for_status()
                data = response.json()
                return {
                    "comment_id": data["id"],
                    "url": data["html_url"],
                    "created": False,
                }
            else:
                # Create new comment
                url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{pr_number}/comments"
                response = await client.post(url, json={"body": body})
                response.raise_for_status()
                data = response.json()
                return {
                    "comment_id": data["id"],
                    "url": data["html_url"],
                    "created": True,
                }

        except httpx.HTTPStatusError as e:
            raise GitHubAPIError(
                f"GitHub API error: {e.response.status_code}",
                details=f"owner={owner}, repo={repo}, pr={pr_number}",
            ) from e
        except Exception as e:
            raise GitHubAPIError(f"Failed to post comment: {e}") from e

    async def find_comment_by_marker(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        marker: str,
    ) -> Optional[int]:
        """Find a comment by a hidden marker in its body.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            marker: Marker string to search for (e.g., <!-- omni-doc-analysis -->)

        Returns:
            Comment ID if found, None otherwise

        Raises:
            GitHubAPIError: If API request fails
        """
        try:
            client = await self._get_client()
            url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{pr_number}/comments"
            response = await client.get(url)
            response.raise_for_status()
            comments = response.json()

            for comment in comments:
                if marker in comment.get("body", ""):
                    return comment["id"]

            return None

        except httpx.HTTPStatusError as e:
            raise GitHubAPIError(
                f"GitHub API error: {e.response.status_code}",
            ) from e
        except Exception as e:
            raise GitHubAPIError(f"Failed to search comments: {e}") from e

    async def delete_comment(
        self,
        owner: str,
        repo: str,
        comment_id: int,
    ) -> bool:
        """Delete a comment.

        Args:
            owner: Repository owner
            repo: Repository name
            comment_id: Comment ID to delete

        Returns:
            True if deleted successfully

        Raises:
            GitHubAPIError: If API request fails
        """
        try:
            client = await self._get_client()
            url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/comments/{comment_id}"
            response = await client.delete(url)
            response.raise_for_status()
            return True

        except httpx.HTTPStatusError as e:
            raise GitHubAPIError(
                f"GitHub API error: {e.response.status_code}",
            ) from e
        except Exception as e:
            raise GitHubAPIError(f"Failed to delete comment: {e}") from e

    async def __aenter__(self) -> "GitHubClient":
        """Async context manager entry."""
        await self._get_client()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()


# Global client instance
_github_client: Optional[GitHubClient] = None


async def get_github_client() -> GitHubClient:
    """Get or create the global GitHub client.

    Returns:
        GitHubClient instance
    """
    global _github_client
    if _github_client is None:
        _github_client = GitHubClient()
    return _github_client
