"""Main LangGraph workflow assembly for Omni-Doc."""

from langgraph.graph import END, START, StateGraph

from omni_doc.agents.correction import run_correction_agent
from omni_doc.agents.technical_writer import run_technical_writer
from omni_doc.agents.visual_architect import run_visual_architect
from omni_doc.graph.routing import (
    route_after_discovery,
    route_after_technical_writer,
    route_after_visual_architect,
    route_agents,
    should_retry_analysis,
)
from omni_doc.models.state import OmniDocState
from omni_doc.nodes import (
    analyze_changes,
    discover_documentation,
    extract_pr_diff,
    generate_markdown,
    post_github_comment,
    scan_repository,
    validate_analysis,
)
from omni_doc.utils.logging import get_logger

logger = get_logger(__name__)


def build_main_graph() -> StateGraph:
    """Build the main Omni-Doc LangGraph workflow.

    The workflow follows this structure:

    START
      |
    extractor (fetch PR data)
      |
    discovery (analyze PR for doc hints)
      |
    [conditional: route_after_discovery]
      |
    repo_scanner (scan repo for docs)
      |
    auditor (analyze documentation gaps)
      |
    [conditional: should_run_agents]
      |
    [agents] (run specialized agents in parallel)
      |
    critic (validate analysis)
      |
    [conditional: should_retry_analysis]
      |
    aggregator (generate markdown report)
      |
    post_comment (post to GitHub)
      |
    END

    Returns:
        Compiled StateGraph workflow
    """
    logger.info("Building Omni-Doc workflow graph")

    # Create the graph with our state type
    workflow = StateGraph(OmniDocState)

    # Add all nodes
    workflow.add_node("extractor", extract_pr_diff)
    workflow.add_node("discovery", discover_documentation)
    workflow.add_node("repo_scanner", scan_repository)
    workflow.add_node("auditor", analyze_changes)
    workflow.add_node("correction_agent", run_correction_agent)
    workflow.add_node("technical_writer_agent", run_technical_writer)
    workflow.add_node("visual_architect_agent", run_visual_architect)
    workflow.add_node("critic", validate_analysis)
    workflow.add_node("aggregator", generate_markdown)
    workflow.add_node("post_comment", post_github_comment)

    # Define the flow
    # START -> extractor -> discovery
    workflow.add_edge(START, "extractor")
    workflow.add_edge("extractor", "discovery")

    # discovery -> repo_scanner or auditor (conditional)
    workflow.add_conditional_edges(
        "discovery",
        route_after_discovery,
        {
            "repo_scanner": "repo_scanner",
            "auditor": "auditor",
        },
    )

    # repo_scanner -> auditor
    workflow.add_edge("repo_scanner", "auditor")

    # auditor -> route to first needed agent or critic
    workflow.add_conditional_edges(
        "auditor",
        route_agents,
        {
            "technical_writer_agent": "technical_writer_agent",
            "visual_architect_agent": "visual_architect_agent",
            "correction_agent": "correction_agent",
            "critic": "critic",
        },
    )

    # technical_writer -> visual_architect or correction or critic
    workflow.add_conditional_edges(
        "technical_writer_agent",
        route_after_technical_writer,
        {
            "visual_architect_agent": "visual_architect_agent",
            "correction_agent": "correction_agent",
            "critic": "critic",
        },
    )

    # visual_architect -> correction or critic
    workflow.add_conditional_edges(
        "visual_architect_agent",
        route_after_visual_architect,
        {
            "correction_agent": "correction_agent",
            "critic": "critic",
        },
    )

    # correction -> critic (always)
    workflow.add_edge("correction_agent", "critic")

    # critic -> auditor (retry) or aggregator (conditional)
    workflow.add_conditional_edges(
        "critic",
        should_retry_analysis,
        {
            "auditor": "auditor",
            "aggregator": "aggregator",
        },
    )

    # aggregator -> post_comment -> END
    workflow.add_edge("aggregator", "post_comment")
    workflow.add_edge("post_comment", END)

    # Compile the graph
    compiled = workflow.compile()
    logger.info("Workflow graph compiled successfully")

    return compiled


async def run_analysis(
    pr_url: str,
    dry_run: bool = False,
    enable_diagrams: bool = True,
) -> dict:
    """Run the full Omni-Doc analysis workflow.

    Args:
        pr_url: GitHub PR URL to analyze
        dry_run: If True, don't post comment to GitHub
        enable_diagrams: If True, generate Mermaid diagrams

    Returns:
        Final workflow state
    """
    from omni_doc.models.state import create_initial_state

    logger.info(f"Starting analysis for: {pr_url}")
    logger.info(f"Options: dry_run={dry_run}, diagrams={enable_diagrams}")

    # Build the graph
    graph = build_main_graph()

    # Create initial state
    initial_state = create_initial_state(
        pr_url=pr_url,
        dry_run=dry_run,
        enable_diagrams=enable_diagrams,
    )

    # Run the graph
    final_state = await graph.ainvoke(initial_state)

    logger.info("Analysis complete")
    return final_state
