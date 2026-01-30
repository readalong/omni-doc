"""Technical Writer Agent for creating new documentation."""

import uuid
from typing import Any

from omni_doc.agents.base import BaseDocAgent
from omni_doc.models.output_models import TechnicalWriterOutput
from omni_doc.models.state import AgentOutputRecord, AnalysisFindingRecord, OmniDocState
from omni_doc.utils.logging import get_logger

logger = get_logger(__name__)

TECHNICAL_WRITER_PROMPT_INCREMENTAL = """You are a technical writer creating EXACT, copy-paste ready documentation updates.

## Your Task:

For each missing documentation, provide a finding with:
- **finding_type**: "missing_doc"
- **severity**: Based on importance
- **title**: Brief description (under 80 chars)
- **description**: ONE sentence explaining what's missing
- **file_path**: Target documentation file
- **target_section**: Exact section heading where new content goes
- **recommended_update**: The EXACT markdown text to add (copy-paste ready)

## Rules:

1. **ONE finding per missing item** - Don't create duplicates
2. **Exact text only** - recommended_update must be valid markdown ready to insert
3. **Match existing style** - Follow the repo's documentation patterns
4. **Be concise** - Focus on what's needed, not verbose explanations
5. **Include examples** - Code examples where helpful

Also provide combined new_documentation for larger sections that need creation.
"""

TECHNICAL_WRITER_PROMPT_COMPREHENSIVE = """You are an expert technical writer creating COMPREHENSIVE documentation for a repository that lacks documentation.

## CRITICAL REQUIREMENTS

This repository has NO documentation. You MUST generate a COMPLETE, DETAILED README.md.

**MINIMUM LENGTH: 2000+ words. Do NOT generate a short or sparse document.**

## MANDATORY Sections (ALL required):

### 1. Project Title and Overview (minimum 150 words)
- Clear, descriptive project name as H1 heading
- Detailed paragraph explaining what the project does and WHY it exists
- Bulleted list of ALL key features (at least 5-7 features)

### 2. Installation / Setup (minimum 200 words)
- **Prerequisites** subsection with specific version requirements
- **Step-by-step Installation** subsection with numbered steps and code blocks
- **Environment Setup** subsection explaining ALL environment variables with examples for Linux/macOS AND Windows

### 3. Configuration (minimum 400 words)
- Document EVERY configuration variable found in the source code
- For EACH variable include:
  - Variable name in bold
  - Description of what it does
  - Data type
  - Default value or example
- Use a consistent format for all variables
- Include code examples showing how to modify configuration

### 4. Usage (minimum 300 words)
- **Basic Usage** subsection with command examples
- Step-by-step explanation of what happens when the script runs
- Include at least one complete code example
- Explain expected output

### 5. Architecture (minimum 200 words)
- **High-Level Description** explaining the overall flow
- **Key Functions/Modules** subsection listing important functions with their purposes
- Explain how data flows through the system

## Formatting Requirements:

- Use proper markdown: H1 (#), H2 (##), H3 (###)
- Use bullet points (*) for lists
- Use numbered lists (1. 2. 3.) for sequential steps
- Use code blocks with language hints (```bash, ```python)
- Use **bold** for emphasis on important terms
- Use `inline code` for variable names, file names, commands

## Output:

The `new_documentation` field MUST contain the FULL, DETAILED README content.
DO NOT truncate or abbreviate. Write the complete documentation.
"""

# Default prompt (backward compatibility)
TECHNICAL_WRITER_PROMPT = TECHNICAL_WRITER_PROMPT_INCREMENTAL


# Minimum documentation length for comprehensive mode (characters)
MIN_COMPREHENSIVE_DOC_LENGTH = 4000  # ~800-1000 words


class TechnicalWriterAgent(BaseDocAgent[TechnicalWriterOutput]):
    """Agent that creates documentation for undocumented code."""

    def __init__(self, temperature: float = 0.3) -> None:
        """Initialize the technical writer agent.

        Args:
            temperature: LLM temperature
        """
        super().__init__(temperature=temperature)
        self._comprehensive_mode = False
        self._base_temperature = temperature

    @property
    def name(self) -> str:
        return "technical_writer"

    @property
    def system_prompt(self) -> str:
        if self._comprehensive_mode:
            return TECHNICAL_WRITER_PROMPT_COMPREHENSIVE
        return TECHNICAL_WRITER_PROMPT_INCREMENTAL

    @property
    def output_model(self) -> type[TechnicalWriterOutput]:
        return TechnicalWriterOutput

    async def process(self, state: OmniDocState) -> dict[str, Any]:
        """Process state and generate new documentation.

        Args:
            state: Current workflow state

        Returns:
            State updates with findings and agent_outputs
        """
        # Determine if we're in comprehensive mode based on documentation status
        documentation_status = state.get("documentation_status")
        self._comprehensive_mode = (
            documentation_status is None
            or documentation_status.get("status") == "missing"
        )

        if self._comprehensive_mode:
            logger.info(f"Running {self.name} agent in COMPREHENSIVE mode")
            # Use lower temperature for comprehensive mode for more deterministic output
            self.temperature = 0.1
        else:
            logger.info(f"Running {self.name} agent in incremental mode")
            self.temperature = self._base_temperature

        # Build context with focus on missing docs
        context = self._build_writer_context(state)

        # Invoke LLM with retry for insufficient output in comprehensive mode
        max_attempts = 2 if self._comprehensive_mode else 1
        response = None

        for attempt in range(max_attempts):
            response = await self._invoke(context)

            # Validate output length in comprehensive mode
            if self._comprehensive_mode:
                doc_length = len(response.new_documentation or "")
                if doc_length < MIN_COMPREHENSIVE_DOC_LENGTH:
                    logger.warning(
                        f"Documentation too short ({doc_length} chars, need {MIN_COMPREHENSIVE_DOC_LENGTH}). "
                        f"Attempt {attempt + 1}/{max_attempts}"
                    )
                    if attempt < max_attempts - 1:
                        # Add instruction to expand
                        context = self._build_writer_context(state) + (
                            "\n\n## IMPORTANT: Your previous response was too short. "
                            "Generate a LONGER, more DETAILED documentation with at least 2000 words. "
                            "Include ALL configuration variables, detailed usage examples, and architecture explanation."
                        )
                        continue
                else:
                    logger.info(f"Documentation length: {doc_length} characters")
                    break
            else:
                break

        # Convert to state format
        findings: list[AnalysisFindingRecord] = []
        for finding in response.findings:
            findings.append(AnalysisFindingRecord(
                id=str(uuid.uuid4()),
                finding_type="missing_doc",
                severity=finding.severity,
                title=finding.title,
                description=finding.description,
                file_path=finding.file_path,
                line_number=None,
                target_section=finding.target_section,
                recommended_update=finding.recommended_update,
                diagram=None,
            ))

        # Create agent output record
        metadata = {}
        if response.style_notes:
            metadata["style_notes"] = response.style_notes

        agent_output = AgentOutputRecord(
            agent_name=self.name,
            finding_type="new_documentation",
            content=response.new_documentation,
            metadata=metadata,
        )

        logger.info(f"Generated documentation with {len(findings)} findings")

        return {
            "findings": findings,
            "agent_outputs": [agent_output],
        }

    def _build_writer_context(self, state: OmniDocState) -> str:
        """Build context focused on documentation gaps.

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

        # Repository structure (important for comprehensive mode)
        repo_structure = state.get("repo_structure")
        if repo_structure:
            parts.append("## Repository Structure")
            parts.append(repo_structure)
            parts.append("")

        if self._comprehensive_mode:
            # For comprehensive mode, use full source files (not just PR diffs)
            parts.append("## Full Source Code")
            source_files = state.get("source_files", [])

            if source_files:
                for sf in source_files:
                    parts.append(f"\n### {sf['path']}")
                    content = sf.get("content", "")
                    # Truncate if needed but show as much as possible
                    if len(content) > 4000:
                        content = content[:4000] + "\n... (truncated)"
                    # Detect language for syntax highlighting
                    ext = sf["path"].rsplit(".", 1)[-1] if "." in sf["path"] else ""
                    lang = {"py": "python", "js": "javascript", "ts": "typescript", "go": "go", "rs": "rust"}.get(ext, ext)
                    parts.append(f"```{lang}\n{content}\n```")
            else:
                # Fallback to PR changes if no source files fetched
                file_changes = state.get("file_changes", [])
                code_changes = [
                    fc for fc in file_changes
                    if not self._is_non_code_file(fc["filename"])
                ]
                for fc in code_changes[:20]:
                    parts.append(f"\n### {fc['filename']} ({fc['status']})")
                    if fc.get("patch"):
                        patch = fc["patch"]
                        if len(patch) > 3000:
                            patch = patch[:3000] + "\n... (truncated)"
                        parts.append(f"```diff\n{patch}\n```")
            parts.append("")

            # Also include config files for documentation
            parts.append("## Configuration Files")
            documentation_files = state.get("documentation_files", [])
            config_files = [
                d for d in documentation_files
                if d.get("doc_type") == "config" and d.get("content")
            ][:5]

            if config_files:
                for doc in config_files:
                    parts.append(f"\n### {doc['path']}")
                    content = doc["content"][:2000]
                    parts.append(f"```\n{content}\n```")
            else:
                parts.append("*No configuration files found*")
            parts.append("")

            # Task for comprehensive mode
            parts.append("## Task")
            parts.append("Generate a COMPLETE README.md for this repository.")
            parts.append("Include: Overview, Installation, Configuration, Usage, and Architecture sections.")
            parts.append("Document ALL configuration options and environment variables found in the code.")
            parts.append("Provide practical examples based on the code.")
        else:
            # Incremental mode - show PR changes
            parts.append("## Code Changes")
            file_changes = state.get("file_changes", [])

            # Filter to code files (not docs, tests, configs)
            code_changes = [
                fc for fc in file_changes
                if not self._is_non_code_file(fc["filename"])
            ]

            for fc in code_changes[:15]:
                parts.append(f"\n### {fc['filename']} ({fc['status']})")
                if fc.get("patch"):
                    patch = fc["patch"]
                    if len(patch) > 2000:
                        patch = patch[:2000] + "\n... (truncated)"
                    parts.append(f"```diff\n{patch}\n```")
            parts.append("")

            # Existing documentation style reference (for incremental mode)
            parts.append("## Existing Documentation Style Reference")
            documentation_files = state.get("documentation_files", [])

            # Get a few docs as style reference
            style_refs = [
                d for d in documentation_files
                if d.get("content") and d.get("doc_type") in ["readme", "guide"]
            ][:3]

            if style_refs:
                for doc in style_refs:
                    parts.append(f"\n### {doc['path']} (Style Reference)")
                    content = doc["content"][:1500]
                    parts.append(f"```markdown\n{content}\n```")
            else:
                parts.append("*No existing documentation style reference available*")
            parts.append("")

            # Findings about missing documentation
            parts.append("## Documentation Gaps Identified")
            findings = state.get("findings", [])
            missing_doc_findings = [
                f for f in findings
                if f.get("finding_type") == "missing_doc"
            ]

            for f in missing_doc_findings:
                parts.append(f"- **{f['title']}**")
                parts.append(f"  {f['description'][:200]}")
            parts.append("")

            # Task for incremental mode
            parts.append("## Task")
            parts.append("Write documentation for the identified gaps.")
            parts.append("Match the existing documentation style.")
            parts.append("Include practical examples and clear explanations.")

        return "\n".join(parts)

    def _is_non_code_file(self, filename: str) -> bool:
        """Check if file is not source code.

        Args:
            filename: File path

        Returns:
            True if file is test, doc, or config (not primary code)
        """
        lower = filename.lower()

        non_code_patterns = [
            "test",
            "spec",
            ".md",
            ".rst",
            ".txt",
            "docs/",
            "doc/",
            ".yaml",
            ".yml",
            ".json",
            ".toml",
            ".ini",
            ".cfg",
            "readme",
            "changelog",
            "license",
        ]

        return any(p in lower for p in non_code_patterns)


async def run_technical_writer(state: OmniDocState) -> dict[str, Any]:
    """Node function to run the technical writer agent.

    Args:
        state: Current workflow state

    Returns:
        State updates
    """
    agent = TechnicalWriterAgent(temperature=0.3)
    return await agent.process(state)
