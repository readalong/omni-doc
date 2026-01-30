"""Unit tests for LangGraph nodes."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any


class TestExtractorNode:
    """Tests for the extractor node."""

    @pytest.mark.asyncio
    async def test_extract_pr_diff_success(self, sample_pr_metadata, sample_file_changes):
        """Test successful PR extraction."""
        from omni_doc.nodes.extractor import extract_pr_diff

        # Mock the PRFetcher
        mock_fetcher = AsyncMock()
        mock_fetcher.fetch_pr_details = AsyncMock(
            return_value=(sample_pr_metadata, sample_file_changes)
        )

        state = {
            "pr_url": "https://github.com/test-owner/test-repo/pull/123",
            "dry_run": True,
            "enable_diagrams": True,
        }

        with patch("omni_doc.nodes.extractor.PRFetcher", return_value=mock_fetcher):
            result = await extract_pr_diff(state)

        assert "pr_metadata" in result
        assert "file_changes" in result
        assert result["pr_metadata"]["title"] == sample_pr_metadata["title"]
        assert len(result["file_changes"]) == len(sample_file_changes)

    @pytest.mark.asyncio
    async def test_extract_pr_diff_invalid_url(self):
        """Test extraction with invalid URL."""
        from omni_doc.nodes.extractor import extract_pr_diff

        state = {
            "pr_url": "https://gitlab.com/owner/repo/pull/123",
            "dry_run": True,
            "enable_diagrams": True,
        }

        result = await extract_pr_diff(state)

        assert "errors" in result
        assert len(result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_extract_pr_diff_api_error(self):
        """Test extraction with API error."""
        from omni_doc.nodes.extractor import extract_pr_diff
        from omni_doc.utils.logging import GitHubAPIError

        mock_fetcher = AsyncMock()
        mock_fetcher.fetch_pr_details = AsyncMock(
            side_effect=GitHubAPIError("API rate limit exceeded")
        )

        state = {
            "pr_url": "https://github.com/test-owner/test-repo/pull/123",
            "dry_run": True,
            "enable_diagrams": True,
        }

        with patch("omni_doc.nodes.extractor.PRFetcher", return_value=mock_fetcher):
            result = await extract_pr_diff(state)

        assert "errors" in result
        assert "API rate limit exceeded" in result["errors"][0]


class TestDiscoveryNode:
    """Tests for the discovery node."""

    @pytest.mark.asyncio
    async def test_discover_documentation_with_metadata(self, sample_pr_metadata, sample_file_changes):
        """Test discovery with PR metadata."""
        from omni_doc.nodes.discovery import discover_documentation

        state = {
            "pr_metadata": sample_pr_metadata,
            "file_changes": sample_file_changes,
        }

        result = await discover_documentation(state)

        # MVP always returns empty dict (routes via conditional edge)
        assert result == {}

    @pytest.mark.asyncio
    async def test_discover_documentation_no_metadata(self):
        """Test discovery without PR metadata."""
        from omni_doc.nodes.discovery import discover_documentation

        state = {}

        result = await discover_documentation(state)

        assert result == {}

    def test_is_doc_related_readme(self):
        """Test documentation detection for README."""
        from omni_doc.nodes.discovery import _is_doc_related

        assert _is_doc_related("README.md") is True
        assert _is_doc_related("readme.txt") is True

    def test_is_doc_related_docs_folder(self):
        """Test documentation detection for docs folder."""
        from omni_doc.nodes.discovery import _is_doc_related

        assert _is_doc_related("docs/api.md") is True
        assert _is_doc_related("documentation/guide.rst") is True

    def test_is_doc_related_code_file(self):
        """Test documentation detection for code files."""
        from omni_doc.nodes.discovery import _is_doc_related

        assert _is_doc_related("src/main.py") is False
        assert _is_doc_related("lib/utils.js") is False


class TestRepoScannerNode:
    """Tests for the repo scanner node."""

    @pytest.mark.asyncio
    async def test_scan_repository_success(self, sample_pr_metadata):
        """Test successful repository scan."""
        from omni_doc.nodes.repo_scanner import scan_repository

        mock_fetcher = AsyncMock()
        # get_repo_tree returns list[str], not RepoTreeOutput
        mock_fetcher.get_repo_tree = AsyncMock(return_value=[
            "README.md",
            "docs/api.md",
            "src/main.py",
        ])
        mock_fetcher.fetch_file_content = AsyncMock(return_value="# File content")

        state = {
            "pr_metadata": sample_pr_metadata,
            "file_changes": [],
        }

        with patch("omni_doc.nodes.repo_scanner.PRFetcher", return_value=mock_fetcher):
            result = await scan_repository(state)

        assert "documentation_files" in result
        assert "repo_structure" in result
        assert len(result["documentation_files"]) >= 1

    @pytest.mark.asyncio
    async def test_scan_repository_no_metadata(self):
        """Test scan without PR metadata."""
        from omni_doc.nodes.repo_scanner import scan_repository

        state = {}

        result = await scan_repository(state)

        assert "errors" in result


class TestAuditorNode:
    """Tests for the auditor node."""

    @pytest.mark.asyncio
    async def test_analyze_changes_success(
        self,
        sample_pr_metadata,
        sample_file_changes,
        sample_documentation_files,
        mock_settings,
    ):
        """Test successful analysis."""
        from omni_doc.nodes.auditor import analyze_changes
        from omni_doc.models.output_models import AuditorResponse, AnalysisFinding

        mock_response = AuditorResponse(
            summary="Analysis complete",
            findings=[
                AnalysisFinding(
                    finding_type="discrepancy",
                    severity="high",
                    title="API docs outdated",
                    description="The API documentation is outdated",
                    file_path="docs/api.md",
                    suggestion="Update API documentation",
                )
            ],
            agents_needed=["correction"],
        )

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

        state = {
            "pr_metadata": sample_pr_metadata,
            "file_changes": sample_file_changes,
            "documentation_files": sample_documentation_files,
            "enable_diagrams": True,
            "retry_count": 0,
        }

        with patch("omni_doc.nodes.auditor.get_settings", return_value=mock_settings):
            with patch("omni_doc.nodes.auditor.ChatGoogleGenerativeAI", return_value=mock_llm):
                result = await analyze_changes(state)

        assert "findings" in result
        assert "agents_needed" in result
        assert len(result["findings"]) == 1
        assert result["findings"][0]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_analyze_changes_no_metadata(self):
        """Test analysis without PR metadata."""
        from omni_doc.nodes.auditor import analyze_changes

        state = {}

        result = await analyze_changes(state)

        assert "errors" in result

    def test_determine_agents_needed_with_diagrams(self):
        """Test agent determination with diagrams enabled."""
        from omni_doc.nodes.auditor import _determine_agents_needed

        agents = _determine_agents_needed(
            ["correction", "visual_architect"],
            enable_diagrams=True,
        )

        assert "correction" in agents
        assert "visual_architect" in agents

    def test_determine_agents_needed_without_diagrams(self):
        """Test agent determination with diagrams disabled."""
        from omni_doc.nodes.auditor import _determine_agents_needed

        agents = _determine_agents_needed(
            ["correction", "visual_architect"],
            enable_diagrams=False,
        )

        assert "correction" in agents
        assert "visual_architect" not in agents


class TestCriticNode:
    """Tests for the critic node."""

    @pytest.mark.asyncio
    async def test_validate_analysis_pass(
        self,
        sample_state,
        mock_settings,
    ):
        """Test validation that passes."""
        from omni_doc.nodes.critic import validate_analysis
        from omni_doc.models.output_models import CriticResponse

        mock_response = CriticResponse(
            validation_passed=True,
            hallucination_risk="low",
            issues_found=[],
            feedback="All findings are valid",
        )

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

        with patch("omni_doc.nodes.critic.get_settings", return_value=mock_settings):
            with patch("omni_doc.nodes.critic.ChatGoogleGenerativeAI", return_value=mock_llm):
                result = await validate_analysis(sample_state)

        assert result["validation_passed"] is True

    @pytest.mark.asyncio
    async def test_validate_analysis_fail(
        self,
        sample_state,
        mock_settings,
    ):
        """Test validation that fails."""
        from omni_doc.nodes.critic import validate_analysis
        from omni_doc.models.output_models import CriticResponse

        mock_response = CriticResponse(
            validation_passed=False,
            hallucination_risk="high",
            issues_found=["Finding 1 not supported by evidence"],
            feedback="Review and correct findings",
        )

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

        with patch("omni_doc.nodes.critic.get_settings", return_value=mock_settings):
            with patch("omni_doc.nodes.critic.ChatGoogleGenerativeAI", return_value=mock_llm):
                result = await validate_analysis(sample_state)

        assert result["validation_passed"] is False
        assert result["validation_feedback"] == "Review and correct findings"

    @pytest.mark.asyncio
    async def test_validate_analysis_no_findings(self, mock_settings):
        """Test validation with no findings."""
        from omni_doc.nodes.critic import validate_analysis

        state = {
            "findings": [],
            "retry_count": 0,
        }

        with patch("omni_doc.nodes.critic.get_settings", return_value=mock_settings):
            result = await validate_analysis(state)

        assert result["validation_passed"] is True

    @pytest.mark.asyncio
    async def test_validate_analysis_max_retries(self, sample_state, mock_settings):
        """Test validation with max retries exceeded."""
        from omni_doc.nodes.critic import validate_analysis

        sample_state["retry_count"] = 5  # Exceeds max_retries of 3

        with patch("omni_doc.nodes.critic.get_settings", return_value=mock_settings):
            result = await validate_analysis(sample_state)

        assert result["validation_passed"] is True
        assert "Max retries exceeded" in result["validation_feedback"]


class TestAggregatorNode:
    """Tests for the aggregator node."""

    @pytest.mark.asyncio
    async def test_generate_markdown_success(self, sample_state):
        """Test markdown generation."""
        from omni_doc.nodes.aggregator import generate_markdown

        result = await generate_markdown(sample_state)

        assert "markdown_report" in result
        assert result["markdown_report"] is not None
        assert "Omni-Doc Analysis Report" in result["markdown_report"]

    @pytest.mark.asyncio
    async def test_generate_markdown_no_findings(self, sample_pr_metadata):
        """Test markdown generation with no findings."""
        from omni_doc.nodes.aggregator import generate_markdown

        state = {
            "pr_metadata": sample_pr_metadata,
            "findings": [],
            "agent_outputs": [],
            "enable_diagrams": True,
            # Set documentation_status to "present" to use incremental format
            "documentation_status": {
                "status": "present",
                "has_readme": True,
                "readme_is_empty": False,
                "doc_file_count": 5,
            },
        }

        result = await generate_markdown(state)

        assert "markdown_report" in result
        assert "No Documentation Issues Found" in result["markdown_report"]

    @pytest.mark.asyncio
    async def test_post_github_comment_dry_run(self, sample_state):
        """Test comment posting in dry run mode."""
        from omni_doc.nodes.aggregator import post_github_comment

        sample_state["dry_run"] = True
        sample_state["markdown_report"] = "# Test Report"

        result = await post_github_comment(sample_state)

        assert result.get("comment_url") is None or "dry-run" in str(result.get("comment_url", ""))

    @pytest.mark.asyncio
    async def test_post_github_comment_real(self, sample_state):
        """Test real comment posting."""
        from omni_doc.nodes.aggregator import post_github_comment

        sample_state["dry_run"] = False
        sample_state["markdown_report"] = "# Test Report"

        mock_commenter = AsyncMock()
        mock_commenter.update_or_create_comment = AsyncMock(
            return_value="https://github.com/owner/repo/pull/123#issuecomment-1"
        )

        with patch("omni_doc.nodes.aggregator.PRCommenter", return_value=mock_commenter):
            result = await post_github_comment(sample_state)

        assert "comment_url" in result
