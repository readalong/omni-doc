"""Pydantic output models for structured LLM responses."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class AnalysisFinding(BaseModel):
    """A single finding from the documentation analysis."""

    finding_type: Literal["discrepancy", "missing_doc", "outdated", "diagram_needed", "improvement"] = Field(
        ...,
        description="Type of documentation issue found",
    )
    severity: Literal["critical", "high", "medium", "low", "info"] = Field(
        ...,
        description="Severity level of the finding",
    )
    title: str = Field(
        ...,
        min_length=5,
        max_length=200,
        description="Brief title describing the finding",
    )
    description: str = Field(
        ...,
        min_length=10,
        max_length=300,
        description="Concise description of what needs to change (1-2 sentences max)",
    )
    file_path: Optional[str] = Field(
        default=None,
        description="Path to the file related to this finding",
    )
    target_section: Optional[str] = Field(
        default=None,
        description="The specific section/heading in the doc file where the update should go (e.g., 'Key Features', 'Configuration')",
    )
    recommended_update: Optional[str] = Field(
        default=None,
        description="The EXACT text to add/replace in the documentation. This should be copy-paste ready markdown that can be directly inserted into the target file/section.",
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence score for this finding (0.0-1.0)",
    )

    def to_state_dict(self) -> dict:
        """Convert to state dictionary format."""
        return {
            "finding_type": self.finding_type,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "file_path": self.file_path,
            "target_section": self.target_section,
            "recommended_update": self.recommended_update,
            "confidence": self.confidence,
        }


class AgentOutput(BaseModel):
    """Output from a specialized documentation agent."""

    agent_name: str = Field(
        ...,
        description="Name of the agent that produced this output",
    )
    findings: list[AnalysisFinding] = Field(
        default_factory=list,
        description="List of findings from the agent",
    )
    suggested_content: Optional[str] = Field(
        default=None,
        description="Suggested documentation content",
    )
    diagram: Optional[str] = Field(
        default=None,
        description="Mermaid diagram if applicable",
    )
    raw_response: Optional[str] = Field(
        default=None,
        description="Raw LLM response for debugging",
    )

    def to_state_dict(self) -> dict:
        """Convert to state dictionary format."""
        return {
            "agent_name": self.agent_name,
            "findings": [f.to_state_dict() for f in self.findings],
            "suggested_content": self.suggested_content,
            "diagram": self.diagram,
            "raw_response": self.raw_response,
        }


class AuditorResponse(BaseModel):
    """Structured output from the Auditor node."""

    summary: str = Field(
        ...,
        description="High-level summary of the documentation analysis",
    )
    findings: list[AnalysisFinding] = Field(
        default_factory=list,
        description="List of documentation findings",
    )
    agents_needed: list[Literal["correction", "technical_writer", "visual_architect"]] = Field(
        default_factory=list,
        description="Specialized agents needed for further analysis",
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Overall confidence in the analysis",
    )


class CriticResponse(BaseModel):
    """Structured output from the Critic node."""

    validation_passed: bool = Field(
        ...,
        description="Whether the analysis passed validation",
    )
    feedback: str = Field(
        ...,
        description="Detailed feedback on the analysis",
    )
    issues_found: list[str] = Field(
        default_factory=list,
        description="List of specific issues found in the analysis",
    )
    hallucination_risk: Literal["none", "low", "medium", "high"] = Field(
        default="low",
        description="Risk level of hallucinated content",
    )


class CorrectionOutput(BaseModel):
    """Output from the Correction Agent."""

    corrections: list[AnalysisFinding] = Field(
        default_factory=list,
        description="Corrections for outdated documentation",
    )
    suggested_updates: str = Field(
        ...,
        description="Suggested documentation updates in markdown",
    )


class TechnicalWriterOutput(BaseModel):
    """Output from the Technical Writer Agent."""

    new_documentation: str = Field(
        ...,
        description="New documentation content in markdown",
    )
    findings: list[AnalysisFinding] = Field(
        default_factory=list,
        description="Findings about missing documentation",
    )
    style_notes: Optional[str] = Field(
        default=None,
        description="Notes about documentation style consistency",
    )


class DiagramOutput(BaseModel):
    """Output from the Visual Architect Agent."""

    diagram_type: Literal["flowchart", "sequence", "class", "state", "er"] = Field(
        ...,
        description="Type of Mermaid diagram generated",
    )
    diagram_code: str = Field(
        ...,
        description="Mermaid diagram code",
    )
    description: str = Field(
        ...,
        description="Description of what the diagram represents",
    )
    finding: AnalysisFinding = Field(
        ...,
        description="Finding associated with this diagram",
    )
