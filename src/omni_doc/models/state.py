"""State schemas for the LangGraph workflow."""

import re
from typing import Annotated, Literal, Optional
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages


def merge_lists(left: list, right: list) -> list:
    """Reducer that merges two lists."""
    return left + right


# Stopwords for title normalization in deduplication
_STOPWORDS = {"the", "a", "an", "is", "are", "for", "to", "in", "of", "and", "or", "with", "this", "that", "new", "add", "update", "missing", "outdated", "needed", "needs", "document", "documentation", "section"}

# Key concepts that identify the semantic topic of a finding
_CONCEPT_SYNONYMS = {
    "contract": {"contract", "c2c", "contractor", "temporary"},
    "diagram": {"diagram", "architecture", "flowchart", "visual", "mermaid"},
    "config": {"config", "configuration", "parameter", "setting", "variable"},
    "feature": {"feature", "functionality", "capability"},
    "api": {"api", "endpoint", "route", "interface"},
    "readme": {"readme", "overview", "introduction"},
}


def _extract_concepts(text: str) -> set[str]:
    """Extract semantic concepts from text.

    Args:
        text: The text to analyze

    Returns:
        Set of canonical concept names found
    """
    text_lower = text.lower()
    concepts = set()

    for canonical, synonyms in _CONCEPT_SYNONYMS.items():
        if any(syn in text_lower for syn in synonyms):
            concepts.add(canonical)

    return concepts


def _normalize_title(title: str) -> str:
    """Normalize a title for deduplication comparison.

    Args:
        title: The finding title

    Returns:
        Normalized title (lowercase, no stopwords, no punctuation)
    """
    # Lowercase and remove punctuation
    normalized = re.sub(r'[^\w\s]', '', title.lower())
    # Remove stopwords
    words = [w for w in normalized.split() if w not in _STOPWORDS]
    return ' '.join(sorted(words))


def _generate_dedup_key(finding: dict) -> str:
    """Generate a deduplication key for a finding.

    Uses semantic concept extraction to group similar findings together.

    Args:
        finding: The finding dictionary

    Returns:
        Deduplication key string
    """
    finding_type = finding.get("finding_type", "")
    file_path = finding.get("file_path", "") or ""

    # Extract concepts from title and description
    title = finding.get("title", "")
    description = finding.get("description", "")
    concepts = _extract_concepts(title + " " + description)

    # Sort concepts for consistent key generation
    concepts_str = "|".join(sorted(concepts)) if concepts else _normalize_title(title)

    return f"{finding_type}|{file_path}|{concepts_str}"


_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def merge_findings(left: list, right: list) -> list:
    """Reducer that merges findings with deduplication.

    Deduplicates based on finding_type + file_path + semantic concepts.
    When duplicates are found, keeps the one with highest severity.

    Args:
        left: Existing findings list
        right: New findings to merge

    Returns:
        Merged list with duplicates removed
    """
    findings_by_key: dict[str, dict] = {}

    # Process all findings, keeping highest severity for each key
    for finding in left + right:
        key = _generate_dedup_key(finding)

        if key not in findings_by_key:
            findings_by_key[key] = finding
        else:
            # Keep the finding with higher severity (lower number = higher severity)
            existing = findings_by_key[key]
            existing_sev = _SEVERITY_ORDER.get(existing.get("severity", "info"), 4)
            new_sev = _SEVERITY_ORDER.get(finding.get("severity", "info"), 4)

            if new_sev < existing_sev:
                # New finding has higher severity, use it but preserve recommended_update if existing has one
                if existing.get("recommended_update") and not finding.get("recommended_update"):
                    finding = {**finding, "recommended_update": existing["recommended_update"]}
                findings_by_key[key] = finding
            elif existing.get("recommended_update") is None and finding.get("recommended_update"):
                # Existing doesn't have recommended_update but new one does, update it
                findings_by_key[key] = {**existing, "recommended_update": finding["recommended_update"]}

    return list(findings_by_key.values())


class DocumentationStatus(TypedDict):
    """Status of documentation in the repository."""

    status: Literal["missing", "minimal", "present"]
    has_readme: bool
    readme_is_empty: bool
    doc_file_count: int


class PRMetadata(TypedDict):
    """Metadata about a pull request."""

    owner: str
    repo: str
    pr_number: int
    title: str
    body: Optional[str]
    state: str
    base_branch: str
    head_branch: str
    author: str
    created_at: str
    updated_at: str
    commits_count: int
    comments_count: int


class FileChange(TypedDict):
    """Information about a file changed in a PR."""

    filename: str
    status: str  # added, modified, removed, renamed
    additions: int
    deletions: int
    patch: Optional[str]
    previous_filename: Optional[str]


class DocumentationFile(TypedDict):
    """Information about a documentation file in the repository."""

    path: str
    doc_type: str  # readme, api, guide, changelog, config, other
    content: Optional[str]
    size: int


class SourceFile(TypedDict):
    """Information about a source code file in the repository."""

    path: str
    content: str
    size: int


class AgentOutputRecord(TypedDict):
    """Record of an agent's output."""

    agent_name: str
    finding_type: str
    content: str
    metadata: dict


class AnalysisFindingRecord(TypedDict):
    """Record of a single analysis finding."""

    id: str
    finding_type: str  # discrepancy, missing_doc, outdated, diagram
    severity: str  # critical, high, medium, low, info
    title: str
    description: str
    file_path: Optional[str]
    line_number: Optional[int]
    target_section: Optional[str]  # Section in doc file where update should go
    recommended_update: Optional[str]  # Copy-paste ready documentation text
    diagram: Optional[str]  # Mermaid diagram if applicable


class OmniDocState(TypedDict):
    """Main state for the Omni-Doc LangGraph workflow."""

    # Input
    pr_url: str
    dry_run: bool
    enable_diagrams: bool

    # PR data (set by extractor)
    pr_metadata: Optional[PRMetadata]
    file_changes: Annotated[list[FileChange], merge_lists]

    # Repository context (set by repo_scanner)
    documentation_files: Annotated[list[DocumentationFile], merge_lists]
    documentation_status: Optional[DocumentationStatus]
    source_files: Annotated[list[SourceFile], merge_lists]  # Full source code for comprehensive analysis
    repo_structure: Optional[str]

    # Analysis results (set by auditor and agents)
    findings: Annotated[list[AnalysisFindingRecord], merge_findings]
    agent_outputs: Annotated[list[AgentOutputRecord], merge_lists]
    agents_needed: list[str]

    # Validation (set by critic)
    validation_passed: bool
    validation_feedback: Optional[str]
    retry_count: int

    # Output
    markdown_report: Optional[str]
    comment_url: Optional[str]

    # Error tracking
    errors: Annotated[list[str], merge_lists]


def create_initial_state(
    pr_url: str,
    dry_run: bool = False,
    enable_diagrams: bool = True,
) -> OmniDocState:
    """Create the initial state for a workflow run.

    Args:
        pr_url: GitHub PR URL to analyze.
        dry_run: If True, don't post comment to GitHub.
        enable_diagrams: If True, enable Mermaid diagram generation.

    Returns:
        OmniDocState: Initial state dictionary.
    """
    return OmniDocState(
        pr_url=pr_url,
        dry_run=dry_run,
        enable_diagrams=enable_diagrams,
        pr_metadata=None,
        file_changes=[],
        documentation_files=[],
        documentation_status=None,
        source_files=[],
        repo_structure=None,
        findings=[],
        agent_outputs=[],
        agents_needed=[],
        validation_passed=False,
        validation_feedback=None,
        retry_count=0,
        markdown_report=None,
        comment_url=None,
        errors=[],
    )
