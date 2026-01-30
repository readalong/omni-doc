"""Unit tests for specialized documentation agents."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any


class TestBaseDocAgent:
    """Tests for the base agent class."""

    def test_base_agent_is_abstract(self):
        """Test that BaseDocAgent cannot be instantiated directly."""
        from omni_doc.agents.base import BaseDocAgent

        with pytest.raises(TypeError):
            BaseDocAgent()

    def test_base_agent_requires_name(self):
        """Test that subclasses must implement name."""
        from omni_doc.agents.base import BaseDocAgent
        from pydantic import BaseModel

        class TestOutput(BaseModel):
            result: str

        class IncompleteAgent(BaseDocAgent[TestOutput]):
            @property
            def system_prompt(self) -> str:
                return "test"

            @property
            def output_model(self) -> type[TestOutput]:
                return TestOutput

            async def process(self, state):
                return {}

        with pytest.raises(TypeError):
            IncompleteAgent()

    def test_build_context(self, sample_state):
        """Test context building from state."""
        from omni_doc.agents.base import BaseDocAgent
        from pydantic import BaseModel

        class TestOutput(BaseModel):
            result: str

        class TestAgent(BaseDocAgent[TestOutput]):
            @property
            def name(self) -> str:
                return "test_agent"

            @property
            def system_prompt(self) -> str:
                return "Test system prompt"

            @property
            def output_model(self) -> type[TestOutput]:
                return TestOutput

            async def process(self, state):
                return {}

        agent = TestAgent()
        context = agent._build_context(sample_state)

        assert "Add new feature" in context  # PR title
        assert "testuser" in context  # Author
        assert "src/main.py" in context  # File change


class TestCorrectionAgent:
    """Tests for the correction agent."""

    @pytest.mark.asyncio
    async def test_correction_agent_process(
        self,
        sample_state,
        mock_settings,
    ):
        """Test correction agent processing."""
        from omni_doc.agents.correction import CorrectionAgent
        from omni_doc.models.output_models import CorrectionOutput, AnalysisFinding

        mock_response = CorrectionOutput(
            corrections=[
                AnalysisFinding(
                    finding_type="discrepancy",
                    severity="high",
                    title="API documentation needs update",
                    description="The API docs need to be updated for the new changes",
                    file_path="docs/api.md",
                    suggestion="Update the main() documentation",
                )
            ],
            suggested_updates="## Updated API Documentation\n\nNew content here.",
        )

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

        agent = CorrectionAgent()
        agent._llm = mock_llm

        # _llm is already set, so get_settings won't be called
        result = await agent.process(sample_state)

        assert "agent_outputs" in result
        assert len(result["agent_outputs"]) == 1
        assert result["agent_outputs"][0]["agent_name"] == "correction"

    def test_correction_agent_name(self):
        """Test correction agent name property."""
        from omni_doc.agents.correction import CorrectionAgent

        agent = CorrectionAgent()
        assert agent.name == "correction"

    def test_correction_agent_system_prompt(self):
        """Test correction agent has system prompt."""
        from omni_doc.agents.correction import CorrectionAgent

        agent = CorrectionAgent()
        assert len(agent.system_prompt) > 0
        assert "correction" in agent.system_prompt.lower() or "documentation" in agent.system_prompt.lower()


class TestTechnicalWriterAgent:
    """Tests for the technical writer agent."""

    @pytest.mark.asyncio
    async def test_technical_writer_process(
        self,
        sample_state,
        mock_settings,
    ):
        """Test technical writer agent processing."""
        from omni_doc.agents.technical_writer import TechnicalWriterAgent
        from omni_doc.models.output_models import TechnicalWriterOutput, AnalysisFinding

        mock_response = TechnicalWriterOutput(
            new_documentation="# New API Documentation\n\nDocumentation for new feature.",
            findings=[
                AnalysisFinding(
                    finding_type="missing_doc",
                    severity="medium",
                    title="Missing API documentation",
                    description="The new process_data function lacks documentation",
                    file_path="docs/api.md",
                    suggestion="Add documentation for the new function",
                )
            ],
            style_notes="Match the existing API documentation style.",
        )

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

        agent = TechnicalWriterAgent()
        agent._llm = mock_llm

        # _llm is already set, so get_settings won't be called
        result = await agent.process(sample_state)

        assert "agent_outputs" in result
        assert len(result["agent_outputs"]) == 1
        assert result["agent_outputs"][0]["agent_name"] == "technical_writer"

    def test_technical_writer_name(self):
        """Test technical writer agent name property."""
        from omni_doc.agents.technical_writer import TechnicalWriterAgent

        agent = TechnicalWriterAgent()
        assert agent.name == "technical_writer"

    def test_technical_writer_system_prompt(self):
        """Test technical writer agent has system prompt."""
        from omni_doc.agents.technical_writer import TechnicalWriterAgent

        agent = TechnicalWriterAgent()
        assert len(agent.system_prompt) > 0


class TestVisualArchitectAgent:
    """Tests for the visual architect agent."""

    @pytest.mark.asyncio
    async def test_visual_architect_process(
        self,
        sample_state,
        mock_settings,
    ):
        """Test visual architect agent processing."""
        from omni_doc.agents.visual_architect import VisualArchitectAgent
        from omni_doc.models.output_models import DiagramOutput, AnalysisFinding

        mock_response = DiagramOutput(
            diagram_type="flowchart",
            diagram_code="graph TD\n    A[Start] --> B[Process]\n    B --> C[End]",
            description="Shows the data processing flow",
            finding=AnalysisFinding(
                finding_type="diagram_needed",
                severity="low",
                title="Data Flow Diagram",
                description="A diagram showing the data flow would help understanding",
                suggestion="Add this diagram to the documentation",
            ),
        )

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

        agent = VisualArchitectAgent()
        agent._llm = mock_llm

        # _llm is already set, so get_settings won't be called
        result = await agent.process(sample_state)

        assert "agent_outputs" in result
        assert len(result["agent_outputs"]) == 1
        assert result["agent_outputs"][0]["agent_name"] == "visual_architect"

    def test_visual_architect_name(self):
        """Test visual architect agent name property."""
        from omni_doc.agents.visual_architect import VisualArchitectAgent

        agent = VisualArchitectAgent()
        assert agent.name == "visual_architect"

    def test_visual_architect_higher_temperature(self):
        """Test visual architect uses higher temperature for creativity."""
        from omni_doc.agents.visual_architect import VisualArchitectAgent

        agent = VisualArchitectAgent()
        # Visual architect should use temperature around 0.4 for creativity
        assert agent._temperature >= 0.3

    def test_visual_architect_system_prompt_has_mermaid(self):
        """Test visual architect prompt includes Mermaid examples."""
        from omni_doc.agents.visual_architect import VisualArchitectAgent

        agent = VisualArchitectAgent()
        # System prompt should include Mermaid diagram guidance
        assert "mermaid" in agent.system_prompt.lower() or "diagram" in agent.system_prompt.lower()


class TestRunAgentFunctions:
    """Tests for the node wrapper functions that run agents."""

    @pytest.mark.asyncio
    async def test_run_correction_agent(self, sample_state, mock_settings):
        """Test run_correction_agent wrapper."""
        from omni_doc.agents.correction import run_correction_agent
        from omni_doc.models.output_models import CorrectionOutput

        mock_response = CorrectionOutput(
            corrections=[],
            suggested_updates="No corrections needed",
        )

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

        with patch("omni_doc.agents.base.get_settings", return_value=mock_settings):
            with patch("omni_doc.agents.base.ChatGoogleGenerativeAI", return_value=mock_llm):
                result = await run_correction_agent(sample_state)

        assert "agent_outputs" in result

    @pytest.mark.asyncio
    async def test_run_technical_writer(self, sample_state, mock_settings):
        """Test run_technical_writer wrapper."""
        from omni_doc.agents.technical_writer import run_technical_writer
        from omni_doc.models.output_models import TechnicalWriterOutput

        mock_response = TechnicalWriterOutput(
            new_documentation="No new documentation needed",
            findings=[],
        )

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

        with patch("omni_doc.agents.base.get_settings", return_value=mock_settings):
            with patch("omni_doc.agents.base.ChatGoogleGenerativeAI", return_value=mock_llm):
                result = await run_technical_writer(sample_state)

        assert "agent_outputs" in result

    @pytest.mark.asyncio
    async def test_run_visual_architect(self, sample_state, mock_settings):
        """Test run_visual_architect wrapper."""
        from omni_doc.agents.visual_architect import run_visual_architect
        from omni_doc.models.output_models import DiagramOutput, AnalysisFinding

        mock_response = DiagramOutput(
            diagram_type="flowchart",
            diagram_code="graph TD\n    A --> B",
            description="Simple flow",
            finding=AnalysisFinding(
                finding_type="diagram_needed",
                severity="info",
                title="Simple diagram",
                description="A simple flow diagram",
                suggestion="Add to docs",
            ),
        )

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=mock_response)
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

        with patch("omni_doc.agents.base.get_settings", return_value=mock_settings):
            with patch("omni_doc.agents.base.ChatGoogleGenerativeAI", return_value=mock_llm):
                result = await run_visual_architect(sample_state)

        assert "agent_outputs" in result
