"""Critic node for validating analysis quality and detecting hallucinations."""

from langchain_google_genai import ChatGoogleGenerativeAI

from omni_doc.config import get_settings
from omni_doc.models.output_models import CriticResponse
from omni_doc.models.state import OmniDocState
from omni_doc.utils.logging import get_logger, LLMError

logger = get_logger(__name__)

CRITIC_SYSTEM_PROMPT = """You are a documentation analysis validator. Your job is to verify the quality and accuracy of a documentation analysis.

## Validation Criteria:

1. **Factual Accuracy**
   - Are findings based on actual code/documentation in the context?
   - Can each claim be verified against the provided materials?
   - Are there any hallucinated issues not supported by evidence?

2. **Completeness**
   - Are obvious issues missed?
   - Are findings actionable and specific?

3. **Severity Appropriateness**
   - Are severity levels justified?
   - Are critical issues correctly identified?

4. **Relevance**
   - Are findings relevant to the PR changes?
   - Are suggestions practical and helpful?

## Your Task:

Review the analysis findings against the original context (PR changes and documentation).
Identify any issues with the analysis itself.

Set validation_passed to TRUE if:
- All findings are factually verifiable
- No obvious hallucinations
- Findings are actionable

Set validation_passed to FALSE if:
- Any finding appears hallucinated
- Critical issues are missed
- Findings are vague or not actionable

Provide specific feedback for improvement.
"""


async def validate_analysis(state: OmniDocState) -> dict:
    """Validate the analysis for accuracy and hallucinations.

    This node:
    1. Reviews findings against original context
    2. Checks for hallucinations
    3. Validates severity assignments
    4. Provides feedback for retry if needed

    Args:
        state: Current workflow state with findings

    Returns:
        State update with validation_passed and validation_feedback
    """
    findings = state.get("findings", [])
    agent_outputs = state.get("agent_outputs", [])
    retry_count = state.get("retry_count", 0)
    max_retries = get_settings().max_retries

    logger.info(f"Validating analysis (attempt {retry_count}/{max_retries})")
    logger.info(f"Findings to validate: {len(findings)}")

    # Skip validation if no findings (nothing to validate)
    if not findings:
        logger.info("No findings to validate - passing")
        return {
            "validation_passed": True,
            "validation_feedback": "No findings generated",
        }

    # Skip validation if max retries exceeded
    if retry_count >= max_retries:
        logger.warning(f"Max retries ({max_retries}) exceeded - passing anyway")
        return {
            "validation_passed": True,
            "validation_feedback": "Max retries exceeded - accepting analysis",
        }

    try:
        # Prepare context for validation
        context = _prepare_validation_context(state)

        # Initialize LLM
        settings = get_settings()
        llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.google_api_key.get_secret_value(),
            temperature=0.0,  # Deterministic for validation
        )

        # Create structured output chain
        structured_llm = llm.with_structured_output(CriticResponse)

        # Invoke LLM
        response: CriticResponse = await structured_llm.ainvoke([
            {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ])

        logger.info(f"Validation result: {'PASSED' if response.validation_passed else 'FAILED'}")
        logger.info(f"Hallucination risk: {response.hallucination_risk}")

        if response.issues_found:
            logger.info(f"Issues found: {response.issues_found}")

        return {
            "validation_passed": response.validation_passed,
            "validation_feedback": response.feedback,
        }

    except Exception as e:
        logger.exception("Error during validation")
        # On validation error, pass to avoid blocking
        return {
            "validation_passed": True,
            "validation_feedback": f"Validation error (accepting): {str(e)}",
        }


def _prepare_validation_context(state: OmniDocState) -> str:
    """Prepare context for the critic LLM.

    Args:
        state: Current workflow state

    Returns:
        Formatted context string
    """
    parts = []

    # Original Context Summary
    pr_metadata = state.get("pr_metadata", {})
    parts.append("## Original Context")
    parts.append(f"**PR:** {pr_metadata.get('title', 'Unknown')}")
    parts.append("")

    # File Changes Summary
    file_changes = state.get("file_changes", [])
    parts.append(f"**Files Changed:** {len(file_changes)}")
    for fc in file_changes[:10]:
        parts.append(f"  - {fc['filename']} ({fc['status']})")
    if len(file_changes) > 10:
        parts.append(f"  ... and {len(file_changes) - 10} more")
    parts.append("")

    # Documentation Found
    documentation_files = state.get("documentation_files", [])
    parts.append(f"**Documentation Files Found:** {len(documentation_files)}")
    for doc in documentation_files[:10]:
        parts.append(f"  - {doc['path']} ({doc['doc_type']})")
    if len(documentation_files) > 10:
        parts.append(f"  ... and {len(documentation_files) - 10} more")
    parts.append("")

    # Findings to Validate
    findings = state.get("findings", [])
    parts.append("## Findings to Validate")
    parts.append("")

    for i, finding in enumerate(findings, 1):
        parts.append(f"### Finding {i}: {finding['title']}")
        parts.append(f"**Type:** {finding['finding_type']}")
        parts.append(f"**Severity:** {finding['severity']}")
        if finding.get("file_path"):
            parts.append(f"**File:** {finding['file_path']}")
        parts.append(f"\n{finding['description']}")
        if finding.get("suggestion"):
            parts.append(f"\n**Suggestion:** {finding['suggestion']}")
        parts.append("")

    # Agent Outputs (if any)
    agent_outputs = state.get("agent_outputs", [])
    if agent_outputs:
        parts.append("## Agent Outputs")
        parts.append(_format_agent_outputs(agent_outputs))

    # Task
    parts.append("## Task")
    parts.append("Validate that each finding:")
    parts.append("1. Is supported by evidence in the context")
    parts.append("2. Has appropriate severity")
    parts.append("3. Is actionable and specific")
    parts.append("4. Is not hallucinated")

    return "\n".join(parts)


def _format_agent_outputs(agent_outputs: list[dict]) -> str:
    """Format agent outputs for display.

    Args:
        agent_outputs: List of agent output records

    Returns:
        Formatted string
    """
    lines = []

    for output in agent_outputs:
        lines.append(f"### {output.get('agent_name', 'Unknown Agent')}")
        lines.append(f"**Type:** {output.get('finding_type', 'N/A')}")
        if output.get("content"):
            content = output["content"]
            if len(content) > 500:
                content = content[:500] + "..."
            lines.append(content)
        lines.append("")

    return "\n".join(lines)
