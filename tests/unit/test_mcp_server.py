"""Unit tests for MCP servers."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any


class TestOmniDocMCPServer:
    """Tests for the Omni-Doc MCP server."""

    def test_server_created(self):
        """Test that MCP server is created."""
        from omni_doc.mcp.server import mcp

        assert mcp is not None
        assert mcp.name == "omni-doc-server"

    @pytest.mark.asyncio
    async def test_analyze_pr_starts_analysis(self):
        """Test analyze_pr tool starts analysis."""
        from omni_doc.mcp.server import analyze_pr, _analyses

        # Clear any existing analyses
        _analyses.clear()

        # Access the underlying function from the FunctionTool
        result = await analyze_pr.fn(
            pr_url="https://github.com/owner/repo/pull/123",
            dry_run=True,
            enable_diagrams=True,
        )

        assert result.analysis_id is not None
        assert result.status == "pending"
        assert result.progress == 0.0

    @pytest.mark.asyncio
    async def test_get_analysis_status_not_found(self):
        """Test get_analysis_status for non-existent analysis."""
        from omni_doc.mcp.server import get_analysis_status, _analyses

        _analyses.clear()

        result = await get_analysis_status.fn("non-existent-id")

        assert result.status == "not_found"
        assert result.error == "Analysis not found"

    @pytest.mark.asyncio
    async def test_get_analysis_status_found(self):
        """Test get_analysis_status for existing analysis."""
        from omni_doc.mcp.server import get_analysis_status, _analyses

        # Add a mock analysis
        _analyses.clear()
        _analyses["test-id"] = {
            "id": "test-id",
            "pr_url": "https://github.com/owner/repo/pull/123",
            "status": "running",
            "progress": 50.0,
            "current_step": "analyzing",
        }

        result = await get_analysis_status.fn("test-id")

        assert result.analysis_id == "test-id"
        assert result.status == "running"
        assert result.progress == 50.0

    @pytest.mark.asyncio
    async def test_list_findings_empty(self):
        """Test list_findings for analysis with no results."""
        from omni_doc.mcp.server import list_findings, _analyses

        _analyses.clear()
        _analyses["test-id"] = {
            "id": "test-id",
            "pr_url": "https://github.com/owner/repo/pull/123",
            "status": "completed",
            "progress": 100.0,
            "result": {"findings": []},
        }

        result = await list_findings.fn("test-id")

        assert result.analysis_id == "test-id"
        assert result.total_count == 0
        assert result.findings == []

    @pytest.mark.asyncio
    async def test_list_findings_with_results(self):
        """Test list_findings with findings."""
        from omni_doc.mcp.server import list_findings, _analyses

        _analyses.clear()
        _analyses["test-id"] = {
            "id": "test-id",
            "pr_url": "https://github.com/owner/repo/pull/123",
            "status": "completed",
            "progress": 100.0,
            "result": {
                "findings": [
                    {
                        "id": "f1",
                        "finding_type": "discrepancy",
                        "severity": "high",
                        "title": "Test finding",
                        "file_path": "docs/api.md",
                    }
                ]
            },
        }

        result = await list_findings.fn("test-id")

        assert result.total_count == 1
        assert len(result.findings) == 1
        assert result.findings[0].type == "discrepancy"

    @pytest.mark.asyncio
    async def test_get_analysis_result(self):
        """Test get_analysis_result."""
        from omni_doc.mcp.server import get_analysis_result, _analyses

        _analyses.clear()
        _analyses["test-id"] = {
            "id": "test-id",
            "pr_url": "https://github.com/owner/repo/pull/123",
            "status": "completed",
            "progress": 100.0,
            "result": {
                "findings": [{"id": "f1"}],
                "markdown_report": "# Report",
                "comment_url": "https://github.com/owner/repo/pull/123#comment-1",
            },
        }

        result = await get_analysis_result.fn("test-id")

        assert result.status == "completed"
        assert result.findings_count == 1
        assert result.markdown_report == "# Report"

    def test_doc_review_prompt(self):
        """Test doc_review_prompt generation."""
        from omni_doc.mcp.server import doc_review_prompt

        # Access the underlying function from the prompt decorator
        result = doc_review_prompt.fn("https://github.com/owner/repo/pull/123")

        assert "https://github.com/owner/repo/pull/123" in result
        assert "documentation" in result.lower()


class TestMCPTypes:
    """Tests for MCP type definitions."""

    def test_analysis_status_output_model(self):
        """Test AnalysisStatusOutput model."""
        from omni_doc.mcp.types import AnalysisStatusOutput

        result = AnalysisStatusOutput(
            analysis_id="test-id",
            status="running",
            progress=50.0,
            current_step="analyzing",
        )

        assert result.analysis_id == "test-id"
        assert result.status == "running"

    def test_finding_summary_model(self):
        """Test FindingSummary model."""
        from omni_doc.mcp.types import FindingSummary

        result = FindingSummary(
            id="f1",
            type="discrepancy",
            severity="high",
            title="Test finding",
            file_path="test.md",
        )

        assert result.id == "f1"
        assert result.type == "discrepancy"

    def test_list_findings_output_model(self):
        """Test ListFindingsOutput model."""
        from omni_doc.mcp.types import ListFindingsOutput, FindingSummary

        finding = FindingSummary(
            id="f1",
            type="missing_doc",
            severity="medium",
            title="Missing docs",
        )
        result = ListFindingsOutput(
            analysis_id="test-id",
            findings=[finding],
            total_count=1,
        )

        assert result.analysis_id == "test-id"
        assert len(result.findings) == 1

    def test_analysis_result_output_model(self):
        """Test AnalysisResultOutput model."""
        from omni_doc.mcp.types import AnalysisResultOutput

        result = AnalysisResultOutput(
            analysis_id="test-id",
            pr_url="https://github.com/owner/repo/pull/123",
            status="completed",
            markdown_report="# Report",
            findings_count=2,
            comment_url="https://github.com/...",
        )

        assert result.analysis_id == "test-id"
        assert result.status == "completed"
        assert result.findings_count == 2
