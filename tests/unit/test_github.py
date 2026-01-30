"""Unit tests for GitHub client module."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from omni_doc.github.client import GitHubClient
from omni_doc.utils.logging import GitHubAPIError


class TestGitHubClient:
    """Tests for GitHubClient class."""

    def test_parse_pr_url_sync_valid(self):
        """Test parsing a valid GitHub PR URL."""
        owner, repo, pr_number = GitHubClient.parse_pr_url_sync(
            "https://github.com/owner/repo/pull/123"
        )
        assert owner == "owner"
        assert repo == "repo"
        assert pr_number == 123

    def test_parse_pr_url_sync_http(self):
        """Test parsing HTTP URL (not HTTPS)."""
        owner, repo, pr_number = GitHubClient.parse_pr_url_sync(
            "http://github.com/owner/repo/pull/456"
        )
        assert owner == "owner"
        assert repo == "repo"
        assert pr_number == 456

    def test_parse_pr_url_sync_complex_names(self):
        """Test parsing URL with complex owner/repo names."""
        owner, repo, pr_number = GitHubClient.parse_pr_url_sync(
            "https://github.com/my-org/my-cool-repo/pull/1"
        )
        assert owner == "my-org"
        assert repo == "my-cool-repo"
        assert pr_number == 1

    def test_parse_pr_url_sync_invalid_format(self):
        """Test parsing invalid URL raises error."""
        with pytest.raises(GitHubAPIError):
            GitHubClient.parse_pr_url_sync("https://gitlab.com/owner/repo/pull/123")

    def test_parse_pr_url_sync_not_pr_url(self):
        """Test parsing non-PR URL raises error."""
        with pytest.raises(GitHubAPIError):
            GitHubClient.parse_pr_url_sync("https://github.com/owner/repo/issues/123")

    def test_parse_pr_url_sync_missing_number(self):
        """Test parsing URL without PR number raises error."""
        with pytest.raises(GitHubAPIError):
            GitHubClient.parse_pr_url_sync("https://github.com/owner/repo/pull/")


class TestPRFetcher:
    """Tests for PRFetcher class."""

    @pytest.mark.asyncio
    async def test_fetch_pr_details_converts_to_state_types(self, sample_pr_metadata):
        """Test that fetch_pr_details converts API output to state types."""
        from omni_doc.github.pr_fetcher import PRFetcher

        # Create mock API response (dict format from new GitHubClient)
        mock_pr_details = {
            "title": sample_pr_metadata["title"],
            "body": sample_pr_metadata["body"],
            "state": sample_pr_metadata["state"],
            "base_branch": sample_pr_metadata["base_branch"],
            "head_branch": sample_pr_metadata["head_branch"],
            "author": sample_pr_metadata["author"],
            "created_at": sample_pr_metadata["created_at"],
            "updated_at": sample_pr_metadata["updated_at"],
            "commits_count": sample_pr_metadata["commits_count"],
            "comments_count": sample_pr_metadata["comments_count"],
            "files": [
                {
                    "filename": "test.py",
                    "status": "modified",
                    "additions": 5,
                    "deletions": 2,
                    "patch": "@@ -1,2 +1,5 @@\n test\n",
                    "previous_filename": None,
                }
            ],
        }

        # Mock the client
        mock_client = AsyncMock()
        mock_client.get_pr_details = AsyncMock(return_value=mock_pr_details)

        fetcher = PRFetcher()
        fetcher._client = mock_client

        # Call the method
        pr_metadata, file_changes = await fetcher.fetch_pr_details("owner", "repo", 123)

        # Verify the result
        assert pr_metadata["title"] == sample_pr_metadata["title"]
        assert pr_metadata["owner"] == "owner"
        assert pr_metadata["repo"] == "repo"
        assert pr_metadata["pr_number"] == 123
        assert len(file_changes) == 1
        assert file_changes[0]["filename"] == "test.py"


class TestPRCommenter:
    """Tests for PRCommenter class."""

    @pytest.mark.asyncio
    async def test_post_comment_adds_marker(self):
        """Test that post_comment adds the Omni-Doc marker."""
        from omni_doc.github.commenter import PRCommenter, OMNI_DOC_MARKER

        mock_client = AsyncMock()
        mock_client.post_comment = AsyncMock(
            return_value={
                "comment_id": 1,
                "url": "https://github.com/owner/repo/pull/123#issuecomment-1",
                "created": True,
            }
        )

        commenter = PRCommenter(github_client=mock_client)
        url = await commenter.post_comment("owner", "repo", 123, "Test body")

        # Verify marker was added
        call_args = mock_client.post_comment.call_args
        body = call_args.kwargs["body"]
        assert OMNI_DOC_MARKER in body
        assert "Test body" in body
        assert url == "https://github.com/owner/repo/pull/123#issuecomment-1"

    @pytest.mark.asyncio
    async def test_update_or_create_comment_updates_existing(self):
        """Test that existing comment is updated."""
        from omni_doc.github.commenter import PRCommenter

        mock_client = AsyncMock()
        mock_client.find_comment_by_marker = AsyncMock(return_value=42)
        mock_client.post_comment = AsyncMock(
            return_value={
                "comment_id": 42,
                "url": "https://github.com/owner/repo/pull/123#issuecomment-42",
                "created": False,
            }
        )

        commenter = PRCommenter(github_client=mock_client)
        await commenter.update_or_create_comment("owner", "repo", 123, "Updated body")

        # Verify update was called with existing ID
        call_args = mock_client.post_comment.call_args
        assert call_args.kwargs["comment_id"] == 42

    @pytest.mark.asyncio
    async def test_update_or_create_comment_creates_new(self):
        """Test that new comment is created when none exists."""
        from omni_doc.github.commenter import PRCommenter

        mock_client = AsyncMock()
        mock_client.find_comment_by_marker = AsyncMock(return_value=None)
        mock_client.post_comment = AsyncMock(
            return_value={
                "comment_id": 1,
                "url": "https://github.com/owner/repo/pull/123#issuecomment-1",
                "created": True,
            }
        )

        commenter = PRCommenter(github_client=mock_client)
        await commenter.update_or_create_comment("owner", "repo", 123, "New body")

        # Verify create was called without ID
        call_args = mock_client.post_comment.call_args
        assert call_args.kwargs.get("comment_id") is None
