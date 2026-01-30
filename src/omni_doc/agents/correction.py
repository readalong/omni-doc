"""Correction Agent for generating fixes for outdated documentation."""

import uuid
from typing import Any

from omni_doc.agents.base import BaseDocAgent
from omni_doc.models.output_models import CorrectionOutput
from omni_doc.models.state import AgentOutputRecord, AnalysisFindingRecord, OmniDocState
from omni_doc.utils.logging import get_logger

logger = get_logger(__name__)

CORRECTION_PROMPT = """You are a documentation correction specialist. Generate EXACT, copy-paste ready corrections.

## Your Task:

For each outdated/incorrect documentation, provide:
- **finding_type**: Always "discrepancy" for corrections
- **severity**: Based on user impact
- **title**: Brief description (under 80 chars)
- **description**: ONE sentence explaining what's wrong
- **file_path**: Target documentation file
- **target_section**: Exact section heading where correction goes
- **recommended_update**: The EXACT replacement markdown text (copy-paste ready)

## Rules:

1. **ONE finding per correction** - Don't duplicate
2. **Exact text only** - recommended_update must be valid markdown
3. **Match style** - Follow the existing documentation style
4. **Be concise** - Description is 1 sentence max

Provide corrections as findings + combined suggested_updates for the full corrected sections.
"""


class CorrectionAgent(BaseDocAgent[CorrectionOutput]):
    """Agent that generates corrections for outdated documentation."""

    @property
    def name(self) -> str:
        return "correction"

    @property
    def system_prompt(self) -> str:
        return CORRECTION_PROMPT

    @property
    def output_model(self) -> type[CorrectionOutput]:
        return CorrectionOutput

    async def process(self, state: OmniDocState) -> dict[str, Any]:
        """Process state and generate corrections.

        Args:
            state: Current workflow state

        Returns:
            State updates with findings and agent_outputs
        """
        logger.info(f"Running {self.name} agent")

        # Build context with focus on discrepancies
        context = self._build_correction_context(state)

        # Invoke LLM
        response = await self._invoke(context)

        # Convert to state format
        findings: list[AnalysisFindingRecord] = []
        for correction in response.corrections:
            findings.append(AnalysisFindingRecord(
                id=str(uuid.uuid4()),
                finding_type="discrepancy",
                severity=correction.severity,
                title=correction.title,
                description=correction.description,
                file_path=correction.file_path,
                line_number=None,
                target_section=correction.target_section,
                recommended_update=correction.recommended_update,
                diagram=None,
            ))

        # Create agent output record
        agent_output = AgentOutputRecord(
            agent_name=self.name,
            finding_type="correction",
            content=response.suggested_updates,
            metadata={"corrections_count": len(response.corrections)},
        )

        logger.info(f"Generated {len(findings)} corrections")

        return {
            "findings": findings,
            "agent_outputs": [agent_output],
        }

    def _build_correction_context(self, state: OmniDocState) -> str:
        """Build context focused on corrections.

        Args:
            state: Current workflow state

        Returns:
            Context string
        """
        parts = []

        # PR info
        pr_metadata = state.get("pr_metadata", {})
        parts.append(f"# PR: {pr_metadata.get('title', 'Unknown')}")
        parts.append(f"Author: @{pr_metadata.get('author', 'unknown')}")
        if pr_metadata.get("body"):
            parts.append(f"\nDescription:\n{pr_metadata['body'][:500]}")
        parts.append("")

        # Code changes with patches
        parts.append("## Code Changes")
        file_changes = state.get("file_changes", [])
        for fc in file_changes[:20]:
            parts.append(f"\n### {fc['filename']} ({fc['status']})")
            if fc.get("patch"):
                patch = fc["patch"]
                if len(patch) > 2000:
                    patch = patch[:2000] + "\n... (truncated)"
                parts.append(f"```diff\n{patch}\n```")
        parts.append("")

        # Documentation that needs correction
        parts.append("## Documentation to Review")
        documentation_files = state.get("documentation_files", [])

        # Filter to docs that might need correction
        relevant_docs = [
            d for d in documentation_files
            if d.get("doc_type") in ["readme", "api", "guide", "config"]
        ]

        for doc in relevant_docs[:10]:
            parts.append(f"\n### {doc['path']}")
            if doc.get("content"):
                content = doc["content"]
                if len(content) > 3000:
                    content = content[:3000] + "\n... (truncated)"
                parts.append(f"```\n{content}\n```")
        parts.append("")

        # Existing findings that need correction
        parts.append("## Findings Requiring Correction")
        findings = state.get("findings", [])
        correction_findings = [
            f for f in findings
            if f.get("finding_type") in ["discrepancy", "outdated"]
        ]

        for f in correction_findings:
            parts.append(f"- **{f['title']}** ({f['severity']})")
            parts.append(f"  {f['description'][:200]}")
        parts.append("")

        # Task
        parts.append("## Task")
        parts.append("Generate corrections for the documentation issues above.")
        parts.append("Provide specific fixes and updated documentation content.")

        return "\n".join(parts)


async def run_correction_agent(state: OmniDocState) -> dict[str, Any]:
    """Node function to run the correction agent.

    Args:
        state: Current workflow state

    Returns:
        State updates
    """
    agent = CorrectionAgent(temperature=0.2)
    return await agent.process(state)
