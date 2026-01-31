"""Visual Architect Agent for generating Mermaid diagrams."""

import uuid
from typing import Any

from omni_doc.agents.base import BaseDocAgent
from omni_doc.models.output_models import DiagramOutput
from omni_doc.models.state import AgentOutputRecord, AnalysisFindingRecord, OmniDocState
from omni_doc.utils.logging import get_logger
from omni_doc.utils.mermaid import validate_and_sanitize

logger = get_logger(__name__)

VISUAL_ARCHITECT_PROMPT_INCREMENTAL = """You are a visual architect creating Mermaid diagrams for software documentation.

## Your Responsibilities:

1. **Identify Diagram Opportunities**
   - Complex workflows that need visualization
   - System architecture changes
   - Data flow patterns
   - State machines

2. **Create Clear Diagrams**
   - Use appropriate diagram types (flowchart, sequence, class, state, ER)
   - Keep diagrams focused and readable
   - Use descriptive labels
   - Follow consistent styling

## Mermaid Diagram Types:

### Flowchart (for processes/workflows)
```mermaid
flowchart TD
    A[Start] --> B{Decision}
    B -->|Yes| C[Action 1]
    B -->|No| D[Action 2]
    C --> E[End]
    D --> E
```

### Sequence (for interactions)
```mermaid
sequenceDiagram
    participant A as Client
    participant B as Server
    A->>B: Request
    B-->>A: Response
```

### Class (for object relationships)
```mermaid
classDiagram
    class Animal {
        +name: string
        +speak()
    }
    class Dog {
        +breed: string
        +bark()
    }
    Animal <|-- Dog
```

### State (for state machines)
```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Processing : start
    Processing --> Complete : success
    Processing --> Error : failure
    Complete --> [*]
    Error --> Idle : retry
```

## IMPORTANT: Mermaid Syntax Rules

**Node labels - use quotes for special characters:**
- CORRECT: `B["Data File (CSV)"]`
- WRONG: `B[Data File (CSV)]`

**Edge labels - NEVER use parentheses or brackets:**
- CORRECT: `-->|Save Report|`
- WRONG: `-->|Save Report (Markdown)|`
- CORRECT: `-->|Audio File|`
- WRONG: `-->|Output (WAV)|`

## Guidelines:

1. Choose the right diagram type for the concept
2. Keep diagrams simple (5-15 nodes maximum)
3. Use clear, concise labels (no special chars in edge labels)
4. Group related elements
5. Use consistent arrow styles

## Output Format:

Provide:
- diagram_type: The Mermaid diagram type used
- diagram_code: Valid Mermaid syntax
- description: What the diagram illustrates
- finding: Associated documentation finding
"""

VISUAL_ARCHITECT_PROMPT_COMPREHENSIVE = """You are a visual architect creating Mermaid diagrams for a repository that LACKS documentation.

## CRITICAL: Generate High-Level Architecture Diagram

This repository has no documentation. Your job is to create a clear, informative architecture diagram that helps developers understand the system at a glance.

## MANDATORY: Mermaid Syntax Rules

**Node labels - ALWAYS use quotes for special characters:**
- CORRECT: `B["Historical Job URLs (CSV)"]`
- WRONG: `B[Historical Job URLs (CSV)]`

**Edge labels - NEVER use parentheses, brackets, or special characters:**
- CORRECT: `-->|Save Report|`
- WRONG: `-->|Save Report (Markdown)|`
- CORRECT: `-->|Audio Output|`
- WRONG: `-->|Save Audio (WAV)|`

**Special characters in node labels that REQUIRE quotes:** `( ) [ ] { } < > & # ; ,`
**Characters FORBIDDEN in edge labels:** `( ) [ ] { } < > # ;`

**Other rules:**
- Use `subgraph Name` ... `end` for grouping
- Use `-->` for arrows, `-->|label|` for labeled arrows
- Node IDs must be alphanumeric (A, B, C or Config, Input, etc.)
- Keep edge labels simple: 2-4 words, no special characters

## Your Task:

Create a SINGLE comprehensive flowchart showing:
1. **Input sources** - Where data comes from (files, APIs, user input)
2. **Processing steps** - Main functions/operations
3. **Output destinations** - Where results go (files, emails, displays)
4. **Data flow** - How information moves between components

## EXACT Template to Follow:

```mermaid
flowchart TD
    subgraph Configuration
        A[Config Parameters]
    end

    subgraph Data Input
        B["Input Source 1"]
        C["Input Source 2"]
    end

    subgraph Core Processing
        D[Process Step 1]
        E[Process Step 2]
        F[Process Step 3]
    end

    subgraph Output
        G["Output 1"]
        H["Output 2"]
    end

    A --> D
    B --> D
    C --> D
    D -->|processed data| E
    E -->|filtered data| F
    F --> G
    F --> H
```

## Requirements:

1. Use **subgraph** to group related components (minimum 3 subgraphs)
2. Include **8-15 nodes** (not more, not fewer)
3. Use **labeled arrows** (`-->|label|`) for important data flows
4. Make node labels **descriptive but concise** (2-4 words)
5. **Quote ALL labels** with parentheses, commas, or special chars

## Output Format:

- diagram_type: "flowchart"
- diagram_code: Valid Mermaid syntax (test it mentally - no syntax errors!)
- description: 2-3 sentences explaining the architecture
- finding: title="System Architecture Diagram", severity="critical"
"""

# Default prompt (backward compatibility)
VISUAL_ARCHITECT_PROMPT = VISUAL_ARCHITECT_PROMPT_INCREMENTAL


class VisualArchitectAgent(BaseDocAgent[DiagramOutput]):
    """Agent that creates Mermaid diagrams for complex flows."""

    def __init__(self) -> None:
        """Initialize with moderate temperature."""
        super().__init__(temperature=0.3)
        self._comprehensive_mode = False

    @property
    def name(self) -> str:
        return "visual_architect"

    @property
    def system_prompt(self) -> str:
        if self._comprehensive_mode:
            return VISUAL_ARCHITECT_PROMPT_COMPREHENSIVE
        return VISUAL_ARCHITECT_PROMPT_INCREMENTAL

    @property
    def output_model(self) -> type[DiagramOutput]:
        return DiagramOutput

    async def process(self, state: OmniDocState) -> dict[str, Any]:
        """Process state and generate diagrams.

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
            # Use lower temperature for more deterministic output
            self.temperature = 0.1
        else:
            logger.info(f"Running {self.name} agent in incremental mode")
            self.temperature = 0.3

        # Build context focused on diagram opportunities
        context = self._build_diagram_context(state)

        # Invoke LLM
        response = await self._invoke(context)

        # Validate and sanitize the generated diagram
        diagram_code, is_valid, error = validate_and_sanitize(response.diagram_code)

        if not is_valid:
            logger.warning(f"Diagram validation issues after sanitization: {error}")
        else:
            logger.debug("Diagram validated and sanitized successfully")

        # Convert finding to state format
        finding = AnalysisFindingRecord(
            id=str(uuid.uuid4()),
            finding_type="diagram_needed",
            severity=response.finding.severity,
            title=response.finding.title,
            description=response.finding.description,
            file_path=response.finding.file_path,
            line_number=None,
            target_section=response.finding.target_section,
            recommended_update=response.finding.recommended_update,
            diagram=diagram_code,
        )

        # Create agent output record - DON'T duplicate diagram here
        # The diagram is already in the finding, no need to add to agent_outputs
        agent_output = AgentOutputRecord(
            agent_name=self.name,
            finding_type="diagram",
            content=response.description,
            metadata={
                "diagram_type": response.diagram_type,
                "diagram_title": response.finding.title,
                # Note: Not including "diagram" here to avoid duplication
            },
        )

        logger.info(f"Generated {response.diagram_type} diagram")

        return {
            "findings": [finding],
            "agent_outputs": [agent_output],
        }

    def _build_diagram_context(self, state: OmniDocState) -> str:
        """Build context focused on diagram opportunities.

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

        # Repository structure context (important for comprehensive mode)
        repo_structure = state.get("repo_structure")
        if repo_structure:
            parts.append("## Repository Structure")
            parts.append(repo_structure)
            parts.append("")

        if self._comprehensive_mode:
            # For comprehensive mode, use full source files to understand architecture
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
                code_files = [
                    fc for fc in file_changes
                    if not any(ext in fc["filename"].lower() for ext in [".md", ".txt", ".json", ".yaml", ".yml", ".toml"])
                ]
                for fc in code_files[:15]:
                    parts.append(f"\n### {fc['filename']}")
                    if fc.get("patch"):
                        patch = fc["patch"]
                        if len(patch) > 3000:
                            patch = patch[:3000] + "\n... (truncated)"
                        parts.append(f"```diff\n{patch}\n```")
            parts.append("")

            # Task for comprehensive mode
            parts.append("## Task")
            parts.append("Create a HIGH-LEVEL ARCHITECTURE DIAGRAM for this repository.")
            parts.append("Show the main components and how they interact.")
            parts.append("Use a flowchart with subgraphs to group related components.")
            parts.append("Make it immediately useful for understanding the codebase.")
        else:
            # For incremental mode, focus on changes that need diagrams
            parts.append("## Code Changes to Visualize")
            file_changes = state.get("file_changes", [])

            # Look for complex files that might benefit from diagrams
            interesting_changes = [
                fc for fc in file_changes
                if self._might_need_diagram(fc)
            ]

            for fc in interesting_changes[:10]:
                parts.append(f"\n### {fc['filename']} ({fc['status']})")
                if fc.get("patch"):
                    patch = fc["patch"]
                    if len(patch) > 2500:
                        patch = patch[:2500] + "\n... (truncated)"
                    parts.append(f"```diff\n{patch}\n```")
            parts.append("")

            # Findings suggesting diagrams
            parts.append("## Diagram Opportunities Identified")
            findings = state.get("findings", [])
            diagram_findings = [
                f for f in findings
                if f.get("finding_type") == "diagram_needed"
                or "diagram" in f.get("description", "").lower()
                or "flow" in f.get("description", "").lower()
                or "architecture" in f.get("description", "").lower()
            ]

            for f in diagram_findings:
                parts.append(f"- **{f['title']}**")
                parts.append(f"  {f['description'][:200]}")
            parts.append("")

            # Task for incremental mode
            parts.append("## Task")
            parts.append("Create a Mermaid diagram to visualize the changes.")
            parts.append("Choose the most appropriate diagram type.")
            parts.append("Focus on clarity and usefulness for developers.")

        return "\n".join(parts)

    def _might_need_diagram(self, file_change: dict) -> bool:
        """Check if a file change might benefit from a diagram.

        Args:
            file_change: File change record

        Returns:
            True if file might benefit from visualization
        """
        filename = file_change.get("filename", "").lower()
        patch = file_change.get("patch", "").lower()

        # Files that often need diagrams
        interesting_patterns = [
            "router",
            "controller",
            "handler",
            "middleware",
            "workflow",
            "pipeline",
            "flow",
            "state",
            "machine",
            "graph",
            "tree",
            "service",
            "client",
            "api",
            "schema",
            "model",
        ]

        # Check filename
        for pattern in interesting_patterns:
            if pattern in filename:
                return True

        # Check patch content for complexity indicators
        complexity_indicators = [
            "async def",
            "class ",
            "def __init__",
            "state =",
            "->",
            "switch",
            "match ",
            "elif",
        ]

        indicator_count = sum(1 for ind in complexity_indicators if ind in patch)
        return indicator_count >= 2


async def run_visual_architect(state: OmniDocState) -> dict[str, Any]:
    """Node function to run the visual architect agent.

    Args:
        state: Current workflow state

    Returns:
        State updates
    """
    agent = VisualArchitectAgent()
    return await agent.process(state)
