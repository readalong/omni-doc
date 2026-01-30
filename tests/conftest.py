"""Pytest configuration and shared fixtures for Omni-Doc tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any


@pytest.fixture
def sample_pr_metadata() -> dict[str, Any]:
    """Sample PR metadata fixture."""
    return {
        "owner": "test-owner",
        "repo": "test-repo",
        "pr_number": 123,
        "title": "Add new feature",
        "body": "This PR adds a new feature.\n\nRelated to documentation.",
        "state": "open",
        "base_branch": "main",
        "head_branch": "feature/new-feature",
        "author": "testuser",
        "created_at": "2024-01-15T10:00:00Z",
        "updated_at": "2024-01-15T12:00:00Z",
        "commits_count": 3,
        "comments_count": 1,
    }


@pytest.fixture
def sample_file_changes() -> list[dict[str, Any]]:
    """Sample file changes fixture."""
    return [
        {
            "filename": "src/main.py",
            "status": "modified",
            "additions": 10,
            "deletions": 2,
            "patch": "@@ -1,5 +1,13 @@\n def main():\n-    print('hello')\n+    print('hello world')\n+    # New feature\n+    process_data()\n",
            "previous_filename": None,
        },
        {
            "filename": "src/utils.py",
            "status": "added",
            "additions": 25,
            "deletions": 0,
            "patch": "@@ -0,0 +1,25 @@\n+def process_data():\n+    '''Process data.'''\n+    return True\n",
            "previous_filename": None,
        },
        {
            "filename": "README.md",
            "status": "modified",
            "additions": 5,
            "deletions": 1,
            "patch": "@@ -1,3 +1,7 @@\n # Project\n\n-Basic description.\n+Updated description.\n+\n+## New Feature\n+\n+Documentation for new feature.\n",
            "previous_filename": None,
        },
    ]


@pytest.fixture
def sample_documentation_files() -> list[dict[str, Any]]:
    """Sample documentation files fixture."""
    return [
        {
            "path": "README.md",
            "doc_type": "readme",
            "content": "# Project\n\nBasic description.\n",
            "size": 30,
        },
        {
            "path": "docs/api.md",
            "doc_type": "api",
            "content": "# API Reference\n\n## Functions\n\n### main()\n\nThe main entry point.\n",
            "size": 75,
        },
        {
            "path": "CHANGELOG.md",
            "doc_type": "changelog",
            "content": "# Changelog\n\n## v1.0.0\n\n- Initial release\n",
            "size": 50,
        },
    ]


@pytest.fixture
def sample_findings() -> list[dict[str, Any]]:
    """Sample analysis findings fixture."""
    return [
        {
            "id": "finding-1",
            "finding_type": "discrepancy",
            "severity": "high",
            "title": "API documentation outdated",
            "description": "The API docs for main() don't reflect the new parameters.",
            "file_path": "docs/api.md",
            "line_number": None,
            "suggestion": "Update the main() documentation to include the new feature.",
            "diagram": None,
        },
        {
            "id": "finding-2",
            "finding_type": "missing_doc",
            "severity": "medium",
            "title": "New function undocumented",
            "description": "process_data() is a new function without API documentation.",
            "file_path": "src/utils.py",
            "line_number": None,
            "suggestion": "Add documentation for process_data() to the API reference.",
            "diagram": None,
        },
    ]


@pytest.fixture
def sample_state(
    sample_pr_metadata: dict[str, Any],
    sample_file_changes: list[dict[str, Any]],
    sample_documentation_files: list[dict[str, Any]],
    sample_findings: list[dict[str, Any]],
) -> dict[str, Any]:
    """Complete sample state fixture."""
    return {
        "pr_url": "https://github.com/test-owner/test-repo/pull/123",
        "dry_run": True,
        "enable_diagrams": True,
        "pr_metadata": sample_pr_metadata,
        "file_changes": sample_file_changes,
        "documentation_files": sample_documentation_files,
        "repo_structure": "Repository Structure:\n\nsrc/ (10 files)\ndocs/ (3 files)\n\nTotal: 13 files",
        "findings": sample_findings,
        "agent_outputs": [],
        "agents_needed": ["correction"],
        "validation_passed": False,
        "validation_feedback": None,
        "retry_count": 0,
        "markdown_report": None,
        "comment_url": None,
        "errors": [],
    }


@pytest.fixture
def mock_settings():
    """Mock settings fixture."""
    settings = MagicMock()
    settings.github_token.get_secret_value.return_value = "test-github-token"
    settings.google_api_key.get_secret_value.return_value = "test-google-api-key"
    settings.gemini_model = "gemini-2.0-flash"
    settings.max_retries = 3
    settings.enable_diagrams = True
    settings.log_level = "INFO"
    settings.mcp_server_port = 8080
    return settings


@pytest.fixture
def mock_github_client():
    """Mock GitHub MCP client fixture."""
    client = AsyncMock()
    client.parse_pr_url = AsyncMock()
    client.fetch_pr_details = AsyncMock()
    client.fetch_file_content = AsyncMock()
    client.get_repo_tree = AsyncMock()
    client.post_comment = AsyncMock()
    client.find_comment_by_marker = AsyncMock()
    client.delete_comment = AsyncMock()
    return client


@pytest.fixture
def mock_llm():
    """Mock LLM fixture."""
    llm = MagicMock()
    llm.with_structured_output = MagicMock(return_value=AsyncMock())
    return llm


@pytest.fixture(autouse=True)
def reset_global_clients():
    """Reset global client instances between tests."""
    yield
    # Clear any cached clients after each test
    import omni_doc.github.client as github_client
    import omni_doc.github.pr_fetcher as pr_fetcher
    import omni_doc.github.commenter as commenter

    github_client._github_client = None
    pr_fetcher._pr_fetcher = None
    commenter._pr_commenter = None
