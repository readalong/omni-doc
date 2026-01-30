"""Routing functions for conditional edges in the LangGraph workflow."""

from typing import Literal

from omni_doc.config import get_settings
from omni_doc.models.state import OmniDocState
from omni_doc.utils.logging import get_logger

logger = get_logger(__name__)


def route_after_discovery(state: OmniDocState) -> Literal["repo_scanner", "auditor"]:
    """Route after discovery node based on state.

    In the MVP, always routes to repo_scanner.
    Future: Could route to external doc fetchers.

    Args:
        state: Current workflow state

    Returns:
        Next node name
    """
    # Check for errors
    if state.get("errors"):
        logger.warning("Errors present, routing to auditor")
        return "auditor"

    # MVP: Always scan repository
    logger.info("Routing to repo_scanner")
    return "repo_scanner"


def should_retry_analysis(state: OmniDocState) -> Literal["auditor", "aggregator"]:
    """Determine whether to retry analysis or proceed to aggregation.

    Args:
        state: Current workflow state

    Returns:
        "auditor" to retry, "aggregator" to proceed
    """
    validation_passed = state.get("validation_passed", False)
    retry_count = state.get("retry_count", 0)
    settings = get_settings()
    max_retries = settings.max_retries

    if validation_passed:
        logger.info("Validation passed, routing to aggregator")
        return "aggregator"

    if retry_count >= max_retries:
        logger.warning(f"Max retries ({max_retries}) reached, routing to aggregator")
        return "aggregator"

    logger.info(f"Validation failed, retrying analysis (attempt {retry_count + 1}/{max_retries})")
    return "auditor"


def route_agents(
    state: OmniDocState,
) -> Literal["correction_agent", "technical_writer_agent", "visual_architect_agent", "critic"]:
    """Determine the first specialized agent to run.

    Routes to the first needed agent in priority order:
    1. technical_writer (for generating documentation)
    2. visual_architect (for generating diagrams)
    3. correction (for fixing existing docs)

    Args:
        state: Current workflow state

    Returns:
        First agent node name to run, or "critic" if none needed
    """
    agents_needed = state.get("agents_needed", [])
    enable_diagrams = state.get("enable_diagrams", True)

    # Priority order: technical_writer first (generates docs), then visual_architect, then correction
    if "technical_writer" in agents_needed:
        logger.info("Routing to technical_writer_agent")
        return "technical_writer_agent"

    if enable_diagrams and "visual_architect" in agents_needed:
        logger.info("Routing to visual_architect_agent")
        return "visual_architect_agent"

    if "correction" in agents_needed:
        logger.info("Routing to correction_agent")
        return "correction_agent"

    logger.info("No agents needed, routing to critic")
    return "critic"


def route_after_technical_writer(
    state: OmniDocState,
) -> Literal["visual_architect_agent", "correction_agent", "critic"]:
    """Route after technical writer completes.

    Args:
        state: Current workflow state

    Returns:
        Next node to run
    """
    agents_needed = state.get("agents_needed", [])
    enable_diagrams = state.get("enable_diagrams", True)

    if enable_diagrams and "visual_architect" in agents_needed:
        logger.info("Routing to visual_architect_agent")
        return "visual_architect_agent"

    if "correction" in agents_needed:
        logger.info("Routing to correction_agent")
        return "correction_agent"

    logger.info("No more agents, routing to critic")
    return "critic"


def route_after_visual_architect(
    state: OmniDocState,
) -> Literal["correction_agent", "critic"]:
    """Route after visual architect completes.

    Args:
        state: Current workflow state

    Returns:
        Next node to run
    """
    agents_needed = state.get("agents_needed", [])

    if "correction" in agents_needed:
        logger.info("Routing to correction_agent")
        return "correction_agent"

    logger.info("No more agents, routing to critic")
    return "critic"
