"""GitHub integration for Omni-Doc."""

from omni_doc.github.client import GitHubClient, get_github_client
from omni_doc.github.pr_fetcher import PRFetcher
from omni_doc.github.commenter import PRCommenter

__all__ = ["GitHubClient", "get_github_client", "PRFetcher", "PRCommenter"]
