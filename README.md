# Omni-Doc

AI-powered documentation analysis for GitHub pull requests. Omni-Doc automatically analyzes code changes against existing documentation to identify discrepancies, missing documentation, and improvement opportunities.

## Features

- **Automated PR Analysis**: Analyze GitHub pull requests for documentation issues
- **MCP Integration**: Expose analysis as MCP tools for LLM clients
- **Smart Detection**: Identifies discrepancies, missing docs, and outdated content
- **Semantic Deduplication**: Consolidates similar findings to avoid redundant reports
- **Copy-Paste Ready Updates**: Provides exact documentation text ready to insert
- **Mermaid Diagrams**: Generates architectural diagrams for complex flows
- **GitHub Comments**: Posts analysis reports directly to PRs
- **GitHub Actions**: Automatic analysis on PR merge (no server needed)

## Quick Start: GitHub Actions

The easiest way to use Omni-Doc is via GitHub Actions. Add this workflow to your repository:

**1. Create `.github/workflows/omni-doc.yml`:**

```yaml
name: Documentation Analysis

on:
  pull_request:
    types: [closed]

jobs:
  omni-doc:
    if: github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write

    steps:
      - uses: readalong/omni-doc@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          google-api-key: ${{ secrets.GOOGLE_API_KEY }}
```

  Quick Reference
                                                                                                                                               
  For users to add omni-doc to their repo:

  # 1. Create workflow file
  ```
  mkdir -p .github/workflows
  curl -o .github/workflows/omni-doc.yml \
    https://raw.githubusercontent.com/readalong/omni-doc/main/.github/workflows/examples/basic.yml
```

  # 2. Add GOOGLE_API_KEY secret in GitHub repo settings

**2. Add your Google API key:**

Go to **Settings → Secrets → Actions → New repository secret**
- Name: `GOOGLE_API_KEY`
- Value: Your [Google AI API key](https://makersuite.google.com/app/apikey)

That's it! Omni-Doc will now analyze every merged PR and post documentation recommendations.

### Skip Analysis

Add any of these labels to a PR to skip analysis:
- `skip-docs`
- `dependencies`
- `dependabot`

### Advanced Configuration

See [`.github/workflows/examples/`](.github/workflows/examples/) for more options:
- Path filters (only analyze certain file types)
- Branch filters (only analyze PRs to main)
- Custom skip labels

## Architecture

Omni-Doc uses a LangGraph-based workflow with specialized agents:

```
START -> Extractor -> Discovery -> Scanner -> Auditor -> Critic -> Aggregator -> END
                                                 ^         |
                                                 |_________|
                                                  (retry loop)
```

- **Extractor**: Fetches PR diff and metadata from GitHub
- **Discovery**: Analyzes PR for documentation context hints
- **Scanner**: Scans repository for existing documentation
- **Auditor**: Analyzes code changes against documentation
- **Critic**: Validates analysis for accuracy and hallucinations
- **Aggregator**: Generates markdown report and posts to GitHub

## Installation

### Prerequisites

- Python 3.11+
- Poetry for dependency management
- GitHub token with repo access
- Google AI API key (for Gemini)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/readalong/omni-doc.git
cd omni-doc
```

2. Install dependencies:
```bash
poetry install
```

3. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your credentials
```

## Configuration

Create a `.env` file with the following variables:

```bash
# Required
GITHUB_TOKEN=ghp_your_github_token
GOOGLE_API_KEY=your_google_api_key

# Optional
GEMINI_MODEL=gemini-2.5-flash      # Default model
MAX_RETRIES=3                       # Max validation retries
ENABLE_DIAGRAMS=true                # Enable Mermaid diagrams
LOG_LEVEL=INFO                      # Logging level
MCP_SERVER_PORT=8080                # MCP server port
```

## Usage

### CLI

Analyze a pull request:
```bash
# Basic analysis
poetry run omni-doc analyze https://github.com/owner/repo/pull/123

# Dry run (don't post comment)
poetry run omni-doc analyze https://github.com/owner/repo/pull/123 --dry-run

# Save report to file
poetry run omni-doc analyze https://github.com/owner/repo/pull/123 --output report.md

# Disable diagrams
poetry run omni-doc analyze https://github.com/owner/repo/pull/123 --no-diagrams

# Verbose output
poetry run omni-doc analyze https://github.com/owner/repo/pull/123 -v
```

Other commands:
```bash
# Show current configuration
poetry run omni-doc config

# Show version
poetry run omni-doc version

# Start MCP server
poetry run omni-doc serve --port 8080
```

### MCP Server

Omni-Doc exposes its functionality as MCP tools:

```bash
# Start the MCP server
poetry run omni-doc serve
```

#### Available Tools

- `analyze_pr`: Start documentation analysis for a PR
- `get_analysis_status`: Check analysis progress
- `list_findings`: Get findings from completed analysis
- `get_analysis_result`: Get complete analysis results

#### Resources

- `analysis://{analysis_id}`: Access analysis results as a resource

#### Prompts

- `doc_review_prompt`: Generate a documentation review prompt

### Python API

```python
import asyncio
from omni_doc.graph.main_graph import run_analysis

async def main():
    result = await run_analysis(
        pr_url="https://github.com/owner/repo/pull/123",
        dry_run=True,
        enable_diagrams=True,
    )
    print(result["markdown_report"])

asyncio.run(main())
```

## GitHub Integration

Omni-Doc uses direct GitHub API access via `httpx` for fetching PR details, repository files, and posting comments. This provides a simple and efficient integration without additional dependencies.

### For AI Agents: Official GitHub MCP Server

If you're building AI agents that need broader GitHub integration, we recommend using the official **GitHub MCP Server**:

- **Repository**: https://github.com/github/github-mcp-server
- **Features**: Full GitHub API access including issues, PRs, actions, code security, and more
- **Installation**: Can run as a remote service or locally via Docker

To use the official GitHub MCP server alongside Omni-Doc:

1. Configure the GitHub MCP server (see their documentation)
2. Use Omni-Doc's MCP server for documentation analysis
3. The two servers complement each other - GitHub MCP for general GitHub operations, Omni-Doc for specialized documentation analysis

## Development

### Setup Development Environment

```bash
# Install dev dependencies
poetry install --with dev

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
poetry run pytest -v

# Run with coverage
poetry run pytest --cov=omni_doc --cov-report=term-missing

# Run specific test file
poetry run pytest tests/unit/test_nodes.py -v

# Run integration tests
poetry run pytest tests/integration/ -v
```

### Code Quality

```bash
# Run linter
poetry run ruff check src/

# Run formatter
poetry run ruff format src/

# Run type checker
poetry run mypy src/

# Run all checks
pre-commit run --all-files
```

### Project Structure

```
omni-doc/
├── src/omni_doc/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py              # CLI commands
│   ├── config.py           # Configuration management
│   ├── agents/             # Specialized documentation agents
│   │   ├── base.py
│   │   ├── correction.py
│   │   ├── technical_writer.py
│   │   └── visual_architect.py
│   ├── github/             # GitHub API integration
│   │   ├── client.py       # Direct GitHub API client (httpx)
│   │   ├── pr_fetcher.py   # PR data fetching
│   │   └── commenter.py    # PR comment management
│   ├── graph/              # LangGraph workflow
│   │   ├── main_graph.py
│   │   └── routing.py
│   ├── mcp/                # MCP server for documentation analysis
│   │   ├── server.py       # Omni-Doc MCP server
│   │   └── types.py        # MCP type definitions
│   ├── models/             # Data models
│   │   ├── state.py        # Workflow state with semantic deduplication
│   │   └── output_models.py # Finding models with recommended_update field
│   ├── nodes/              # LangGraph nodes
│   │   ├── extractor.py
│   │   ├── discovery.py
│   │   ├── repo_scanner.py
│   │   ├── auditor.py
│   │   ├── critic.py
│   │   └── aggregator.py
│   └── utils/
│       ├── logging.py
│       ├── markdown.py     # Report formatting with recommended updates
│       └── mermaid.py      # Mermaid diagram validation
└── tests/
    ├── unit/
    ├── integration/
    └── fixtures/
```

## Analysis Report Format

Omni-Doc generates concise, actionable markdown reports with:

1. **Summary**: Overview of findings by severity and type
2. **Findings**: Deduplicated list of documentation issues, each containing:
   - Target file and section for the update
   - Concise description of what needs to change
   - **Recommended Update**: Copy-paste ready markdown text
3. **Diagrams**: Mermaid diagrams for complex architectures (when enabled)

### Finding Types

- **discrepancy**: Code doesn't match documentation
- **missing_doc**: New features/APIs not documented
- **outdated**: Old behavior still documented
- **diagram_needed**: Complex flows needing visualization
- **improvement**: Optional enhancements

### Severity Levels

- **Critical**: Broken or misleading documentation
- **High**: Significant discrepancy affecting users
- **Medium**: Incomplete or outdated information
- **Low**: Minor inconsistencies
- **Info**: Nice-to-have suggestions

### Example Finding Output

```markdown
### :orange_circle: Contract role filtering not documented
`README.md` → **Key Features**

The new CONTRACT_KEYWORDS filter is not mentioned in the Key Features section.

**Recommended Update:**

- **Contract Role Filtering**: Identifies contract, C2C, and temporary positions
  using keyword matching and categorizes them in a dedicated email section.
```

The recommended update can be directly copied and inserted into the target file/section.

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run tests: `poetry run pytest`
5. Commit: `git commit -m "Add my feature"`
6. Push: `git push origin feature/my-feature`
7. Create a Pull Request

## License

MIT License - see LICENSE for details.

## Acknowledgments

- Built with [LangGraph](https://github.com/langchain-ai/langgraph)
- Powered by [Google Gemini](https://ai.google.dev/)
- MCP integration via [FastMCP](https://github.com/jlowin/fastmcp)
- For GitHub API access in AI agents, see [GitHub MCP Server](https://github.com/github/github-mcp-server)

To verify the implementation, run:
```bash
poetry install
poetry run pytest -v
poetry run omni-doc --help
```
