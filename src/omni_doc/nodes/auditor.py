"""Auditor node for analyzing documentation against code changes."""

import uuid
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from omni_doc.config import get_settings
from omni_doc.models.output_models import AnalysisFinding, AuditorResponse
from omni_doc.models.state import AnalysisFindingRecord, OmniDocState
from omni_doc.utils.logging import get_logger, LLMError

logger = get_logger(__name__)

AUDITOR_SYSTEM_PROMPT_DOCS_PRESENT = """You are an expert documentation auditor analyzing a GitHub pull request.

Your task is to identify documentation issues and provide EXACT, copy-paste ready fixes.

## Your Analysis Should Cover:

1. **Discrepancies**: Documentation doesn't match the code
2. **Missing Documentation**: New features/APIs not documented
3. **Outdated Content**: Old behavior still documented
4. **Diagram Opportunities**: Complex flows needing visualization

## Output Format:

For each finding, provide:
- **finding_type**: discrepancy, missing_doc, outdated, diagram_needed, improvement
- **severity**: critical (broken), high (misleading), medium (incomplete), low (minor), info (nice-to-have)
- **title**: Brief description (under 80 chars)
- **description**: ONE sentence explaining what needs to change
- **file_path**: Target documentation file (e.g., README.md)
- **target_section**: Exact section heading where the update goes (e.g., "Key Features", "Configuration")
- **recommended_update**: The EXACT markdown text to add/replace. This must be copy-paste ready!

## CRITICAL RULES:

1. **ONE finding per concept** - Do NOT create multiple findings about the same feature
2. **Be specific** - Use exact section names from the documentation
3. **Provide exact text** - The recommended_update must be valid markdown that can be directly inserted
4. **Be concise** - Description should be 1-2 sentences max
5. **No vague suggestions** - Every finding must have a concrete recommended_update

## Example of a GOOD finding:

```json
{
  "finding_type": "missing_doc",
  "severity": "high",
  "title": "Contract role filtering not documented",
  "description": "The new CONTRACT_KEYWORDS filter is not mentioned in the Key Features section.",
  "file_path": "README.md",
  "target_section": "Key Features",
  "recommended_update": "- **Contract Role Filtering**: Identifies contract, C2C, and temporary positions using keyword matching and categorizes them in a dedicated email section."
}
```

Do NOT make up issues - only report what you can verify from the provided context.
"""

AUDITOR_SYSTEM_PROMPT_DOCS_MISSING = """You are an expert documentation auditor analyzing a GitHub pull request.

## CRITICAL: This repository lacks documentation

The repository has missing or empty documentation. Instead of generating many individual findings,
you should generate ONE consolidated finding requesting comprehensive documentation.

## Your Task:

Generate exactly ONE finding that:
1. Acknowledges the repository needs comprehensive documentation
2. Requests the technical_writer agent to create a complete README with:
   - Project overview and purpose
   - Installation/setup instructions
   - Configuration options
   - Usage examples
3. Requests the visual_architect agent to create architecture diagrams

## Output:

Provide exactly ONE finding:
- **finding_type**: missing_doc
- **severity**: high
- **title**: "Repository needs comprehensive documentation"
- **description**: Brief summary of what the repository does (based on code) and what documentation is needed
- **file_path**: README.md
- **suggestion**: "Generate comprehensive README and architecture diagrams"

## Agents Needed:

Always include both agents:
- **technical_writer**: To generate the README
- **visual_architect**: To generate architecture diagrams

Do NOT generate multiple separate findings for missing docs, empty README, etc.
Generate ONE consolidated finding that covers all documentation needs.
"""

# Default prompt (backward compatibility)
AUDITOR_SYSTEM_PROMPT = AUDITOR_SYSTEM_PROMPT_DOCS_PRESENT


async def analyze_changes(state: OmniDocState) -> dict:
    """Analyze code changes against documentation.

    This node:
    1. Prepares context from PR data and documentation
    2. Invokes the LLM to analyze discrepancies
    3. Determines which specialized agents are needed
    4. Returns findings and agent routing

    Args:
        state: Current workflow state

    Returns:
        State update with findings and agents_needed
    """
    pr_metadata = state.get("pr_metadata")
    file_changes = state.get("file_changes", [])
    documentation_files = state.get("documentation_files", [])
    documentation_status = state.get("documentation_status")
    validation_feedback = state.get("validation_feedback")
    retry_count = state.get("retry_count", 0)

    if not pr_metadata:
        return {"errors": ["No PR metadata available for analysis"]}

    logger.info(f"Analyzing changes for PR: {pr_metadata['title']}")
    logger.info(f"Files changed: {len(file_changes)}, Docs found: {len(documentation_files)}")

    # Determine which prompt to use based on documentation status
    docs_missing = (
        documentation_status is None
        or documentation_status.get("status") == "missing"
    )
    if docs_missing:
        logger.info("Documentation missing - using comprehensive prompt")
        system_prompt = AUDITOR_SYSTEM_PROMPT_DOCS_MISSING
    else:
        logger.info(f"Documentation status: {documentation_status.get('status')} - using standard prompt")
        system_prompt = AUDITOR_SYSTEM_PROMPT_DOCS_PRESENT

    if validation_feedback:
        logger.info(f"Retry attempt {retry_count} with feedback: {validation_feedback[:100]}...")

    try:
        # Prepare context for the LLM
        context = _prepare_auditor_context(
            pr_metadata=pr_metadata,
            file_changes=file_changes,
            documentation_files=documentation_files,
            validation_feedback=validation_feedback,
        )

        # Initialize LLM
        settings = get_settings()
        llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.google_api_key.get_secret_value(),
            temperature=0.1,
        )

        # Create structured output chain
        structured_llm = llm.with_structured_output(AuditorResponse)

        # Invoke LLM
        response: AuditorResponse = await structured_llm.ainvoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": context},
        ])

        logger.info(f"Analysis complete: {len(response.findings)} findings")
        logger.info(f"Agents needed: {response.agents_needed}")

        # Convert findings to state format
        findings: list[AnalysisFindingRecord] = []
        for finding in response.findings:
            findings.append(_finding_to_record(finding))

        # Determine agents based on findings and state
        agents_needed = _determine_agents_needed(
            response.agents_needed,
            state.get("enable_diagrams", True),
            docs_missing,
        )

        return {
            "findings": findings,
            "agents_needed": agents_needed,
            "retry_count": retry_count + 1,
        }

    except Exception as e:
        logger.exception("Error during analysis")
        raise LLMError(f"Analysis failed: {e}", model=get_settings().gemini_model) from e


def _prepare_auditor_context(
    pr_metadata: dict,
    file_changes: list[dict],
    documentation_files: list[dict],
    validation_feedback: Optional[str] = None,
) -> str:
    """Prepare context string for the auditor LLM.

    Args:
        pr_metadata: PR metadata
        file_changes: List of file changes
        documentation_files: List of documentation files
        validation_feedback: Optional feedback from critic

    Returns:
        Formatted context string
    """
    parts = []

    # PR Info
    parts.append("## Pull Request Information")
    parts.append(f"**Title:** {pr_metadata['title']}")
    parts.append(f"**Author:** {pr_metadata['author']}")
    parts.append(f"**Branch:** {pr_metadata['head_branch']} -> {pr_metadata['base_branch']}")
    if pr_metadata.get("body"):
        parts.append(f"\n**Description:**\n{pr_metadata['body']}")
    parts.append("")

    # File Changes
    parts.append("## Code Changes")
    for fc in file_changes[:30]:  # Limit to 30 files
        parts.append(f"\n### {fc['filename']} ({fc['status']})")
        parts.append(f"+{fc['additions']} / -{fc['deletions']} lines")
        if fc.get("patch"):
            patch = fc["patch"]
            # Truncate very long patches
            if len(patch) > 3000:
                patch = patch[:3000] + "\n... (truncated)"
            parts.append(f"```diff\n{patch}\n```")
    parts.append("")

    # Documentation Files
    parts.append("## Existing Documentation")
    if not documentation_files:
        parts.append("*No documentation files found in repository*")
    else:
        for doc in documentation_files[:20]:  # Limit to 20 docs
            parts.append(f"\n### {doc['path']} ({doc['doc_type']})")
            if doc.get("content"):
                content = doc["content"]
                # Truncate very long docs
                if len(content) > 5000:
                    content = content[:5000] + "\n... (truncated)"
                parts.append(f"```\n{content}\n```")
            else:
                parts.append(f"*File too large: {doc['size']} bytes*")
    parts.append("")

    # Validation Feedback (if retry)
    if validation_feedback:
        parts.append("## Previous Analysis Feedback")
        parts.append("The previous analysis was rejected. Please address these issues:")
        parts.append(validation_feedback)
        parts.append("")

    # Task
    parts.append("## Task")
    parts.append("Analyze the code changes and identify documentation issues.")
    parts.append("Compare the changes against existing documentation and report:")
    parts.append("1. Discrepancies between code and docs")
    parts.append("2. Missing documentation for new features")
    parts.append("3. Outdated documentation")
    parts.append("4. Opportunities for diagrams")

    return "\n".join(parts)


def _finding_to_record(finding: AnalysisFinding) -> AnalysisFindingRecord:
    """Convert AnalysisFinding to state record format.

    Args:
        finding: Pydantic finding model

    Returns:
        TypedDict finding record
    """
    return AnalysisFindingRecord(
        id=str(uuid.uuid4()),
        finding_type=finding.finding_type,
        severity=finding.severity,
        title=finding.title,
        description=finding.description,
        file_path=finding.file_path,
        line_number=None,
        target_section=finding.target_section,
        recommended_update=finding.recommended_update,
        diagram=None,
    )


def _determine_agents_needed(
    llm_suggested: list[str],
    enable_diagrams: bool,
    docs_missing: bool = False,
) -> list[str]:
    """Determine which specialized agents should run.

    Args:
        llm_suggested: Agents suggested by LLM
        enable_diagrams: Whether diagrams are enabled
        docs_missing: Whether documentation is missing (triggers comprehensive mode)

    Returns:
        List of agent names to run
    """
    agents = []

    # When docs are missing, always include technical_writer and visual_architect
    if docs_missing:
        agents.append("technical_writer")
        if enable_diagrams:
            agents.append("visual_architect")
        return agents

    # Always include correction if suggested
    if "correction" in llm_suggested:
        agents.append("correction")

    # Include technical writer if suggested
    if "technical_writer" in llm_suggested:
        agents.append("technical_writer")

    # Include visual architect only if enabled and suggested
    if enable_diagrams and "visual_architect" in llm_suggested:
        agents.append("visual_architect")

    return agents
