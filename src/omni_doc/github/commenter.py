"""PR Commenter for posting analysis results to GitHub."""

from typing import Optional

from omni_doc.github.client import GitHubClient, get_github_client
from omni_doc.utils.logging import get_logger, GitHubAPIError

logger = get_logger(__name__)

# Hidden marker for identifying Omni-Doc comments
OMNI_DOC_MARKER = "<!-- omni-doc-analysis -->"


class PRCommenter:
    """Posts and manages PR comments on GitHub."""

    def __init__(self, github_client: Optional[GitHubClient] = None) -> None:
        """Initialize the PR commenter.

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

    async def post_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
    ) -> str:
        """Post a new comment on a PR.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            body: Comment body in markdown

        Returns:
            Comment URL

        Raises:
            GitHubAPIError: If posting fails
        """
        client = await self._get_client()

        try:
            # Add marker to comment body
            marked_body = f"{OMNI_DOC_MARKER}\n{body}"

            result = await client.post_comment(
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                body=marked_body,
            )

            logger.info(f"Posted comment: {result['url']}")
            return result["url"]

        except Exception as e:
            logger.error(f"Failed to post comment: {e}")
            raise GitHubAPIError(f"Failed to post comment: {e}") from e

    async def update_or_create_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
    ) -> str:
        """Update existing Omni-Doc comment or create a new one.

        Looks for an existing comment with the Omni-Doc marker and updates it.
        If no existing comment is found, creates a new one.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            body: Comment body in markdown

        Returns:
            Comment URL

        Raises:
            GitHubAPIError: If operation fails
        """
        client = await self._get_client()

        try:
            # Look for existing comment
            existing_id = await client.find_comment_by_marker(
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                marker=OMNI_DOC_MARKER,
            )

            marked_body = f"{OMNI_DOC_MARKER}\n{body}"

            if existing_id:
                logger.info(f"Updating existing comment: {existing_id}")
                result = await client.post_comment(
                    owner=owner,
                    repo=repo,
                    pr_number=pr_number,
                    body=marked_body,
                    comment_id=existing_id,
                )
                logger.info(f"Updated comment: {result['url']}")
            else:
                logger.info("Creating new comment")
                result = await client.post_comment(
                    owner=owner,
                    repo=repo,
                    pr_number=pr_number,
                    body=marked_body,
                )
                logger.info(f"Created comment: {result['url']}")

            return result["url"]

        except Exception as e:
            logger.error(f"Failed to update/create comment: {e}")
            raise GitHubAPIError(f"Failed to update/create comment: {e}") from e

    async def delete_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> bool:
        """Delete the Omni-Doc comment from a PR if it exists.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            True if comment was deleted, False if no comment found

        Raises:
            GitHubAPIError: If deletion fails
        """
        client = await self._get_client()

        try:
            # Look for existing comment
            existing_id = await client.find_comment_by_marker(
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                marker=OMNI_DOC_MARKER,
            )

            if existing_id:
                await client.delete_comment(
                    owner=owner,
                    repo=repo,
                    comment_id=existing_id,
                )
                logger.info(f"Deleted comment: {existing_id}")
                return True

            logger.info("No existing comment to delete")
            return False

        except Exception as e:
            logger.error(f"Failed to delete comment: {e}")
            raise GitHubAPIError(f"Failed to delete comment: {e}") from e


# Global commenter instance
_pr_commenter: Optional[PRCommenter] = None


async def get_pr_commenter() -> PRCommenter:
    """Get or create the global PR commenter.

    Returns:
        PRCommenter instance
    """
    global _pr_commenter
    if _pr_commenter is None:
        _pr_commenter = PRCommenter()
    return _pr_commenter
