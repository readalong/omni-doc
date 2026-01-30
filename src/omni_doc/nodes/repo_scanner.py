"""Repo Scanner node for finding documentation files in the repository."""

import fnmatch
from typing import Optional

from omni_doc.github.pr_fetcher import PRFetcher
from omni_doc.models.state import DocumentationFile, DocumentationStatus, OmniDocState, SourceFile
from omni_doc.utils.logging import get_logger, GitHubAPIError

logger = get_logger(__name__)

# Patterns for documentation files
DOC_PATTERNS = [
    # Markdown files
    "*.md",
    "*.markdown",
    # RST files
    "*.rst",
    # Text files
    "README*",
    "CHANGELOG*",
    "CHANGES*",
    "HISTORY*",
    "CONTRIBUTING*",
    "AUTHORS*",
    "LICENSE*",
    # Documentation directories
    "docs/*",
    "doc/*",
    "documentation/*",
    # API documentation
    "api/*",
    "reference/*",
    # Config files that document behavior
    "*.yaml",
    "*.yml",
    "*.toml",
    "*.json",
    # OpenAPI/Swagger
    "openapi.*",
    "swagger.*",
]

# Files to exclude
EXCLUDE_PATTERNS = [
    "node_modules/*",
    ".git/*",
    "__pycache__/*",
    "*.pyc",
    ".venv/*",
    "venv/*",
    "dist/*",
    "build/*",
    ".tox/*",
    ".pytest_cache/*",
    "*.egg-info/*",
    "poetry.lock",
    "package-lock.json",
    "yarn.lock",
]

# Maximum file size to fetch content (100KB)
MAX_CONTENT_SIZE = 100 * 1024

# Maximum source file size (50KB) - smaller to fit more files in context
MAX_SOURCE_FILE_SIZE = 50 * 1024

# Minimum README content length to be considered non-empty
MIN_README_CONTENT_LENGTH = 100

# Minimum total doc content for "present" status
MIN_DOC_CONTENT_FOR_PRESENT = 1000

# Source code file extensions to fetch for comprehensive analysis
SOURCE_CODE_EXTENSIONS = [
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".java", ".kt", ".scala",
    ".go", ".rs", ".c", ".cpp", ".h", ".hpp",
    ".rb", ".php", ".cs", ".swift",
    ".sh", ".bash", ".zsh",
]

# Maximum number of source files to fetch
MAX_SOURCE_FILES = 20


def _determine_documentation_status(
    documentation_files: list[DocumentationFile],
) -> DocumentationStatus:
    """Determine the documentation status of the repository.

    Args:
        documentation_files: List of documentation files found

    Returns:
        DocumentationStatus with status, has_readme, readme_is_empty, doc_file_count
    """
    has_readme = False
    readme_is_empty = True
    readme_content_length = 0
    total_doc_content_length = 0
    doc_file_count = len(documentation_files)

    for doc_file in documentation_files:
        path_lower = doc_file["path"].lower()
        content = doc_file.get("content") or ""
        content_length = len(content.strip())

        # Check for README files
        if "readme" in path_lower.split("/")[-1]:
            has_readme = True
            readme_content_length = max(readme_content_length, content_length)
            if content_length >= MIN_README_CONTENT_LENGTH:
                readme_is_empty = False

        # Sum up documentation content (excluding config files)
        if doc_file.get("doc_type") in ["readme", "guide", "api", "changelog"]:
            total_doc_content_length += content_length

    # Determine overall status
    if not has_readme or readme_is_empty:
        status = "missing"
    elif total_doc_content_length < MIN_DOC_CONTENT_FOR_PRESENT:
        status = "minimal"
    else:
        status = "present"

    return DocumentationStatus(
        status=status,
        has_readme=has_readme,
        readme_is_empty=readme_is_empty,
        doc_file_count=doc_file_count,
    )


async def scan_repository(state: OmniDocState) -> dict:
    """Scan repository for documentation files.

    This node:
    1. Fetches the repository file tree
    2. Identifies documentation files by pattern
    3. Fetches content for relevant files
    4. Builds a repo structure summary

    Args:
        state: Current workflow state with pr_metadata

    Returns:
        State update with documentation_files and repo_structure
    """
    pr_metadata = state.get("pr_metadata")

    if not pr_metadata:
        logger.error("No PR metadata available for repo scan")
        return {"errors": ["No PR metadata available for repo scan"]}

    owner = pr_metadata["owner"]
    repo = pr_metadata["repo"]
    base_branch = pr_metadata["base_branch"]

    logger.info(f"Scanning repository: {owner}/{repo} (branch: {base_branch})")

    try:
        fetcher = PRFetcher()

        # Get repository file tree
        all_files = await fetcher.get_repo_tree(
            owner=owner,
            repo=repo,
            ref=base_branch,
        )

        # Filter for documentation files
        doc_files = _find_documentation_files(all_files)
        logger.info(f"Found {len(doc_files)} documentation files")

        # Fetch content for documentation files
        documentation_files: list[DocumentationFile] = []
        for file_path in doc_files[:50]:  # Limit to 50 files to avoid rate limits
            doc_file = await _fetch_doc_file(
                fetcher=fetcher,
                owner=owner,
                repo=repo,
                path=file_path,
                ref=base_branch,
            )
            if doc_file:
                documentation_files.append(doc_file)

        # Build repo structure summary
        repo_structure = _build_repo_structure(all_files)

        # Determine documentation status
        documentation_status = _determine_documentation_status(documentation_files)

        logger.info(f"Processed {len(documentation_files)} documentation files")
        logger.info(f"Documentation status: {documentation_status['status']}")

        # If documentation is missing, fetch source code files for comprehensive analysis
        source_files: list[SourceFile] = []
        if documentation_status["status"] == "missing":
            logger.info("Documentation missing - fetching source code for comprehensive analysis")
            source_file_paths = _find_source_files(all_files)
            logger.info(f"Found {len(source_file_paths)} source code files")

            for file_path in source_file_paths[:MAX_SOURCE_FILES]:
                source_file = await _fetch_source_file(
                    fetcher=fetcher,
                    owner=owner,
                    repo=repo,
                    path=file_path,
                    ref=base_branch,
                )
                if source_file:
                    source_files.append(source_file)

            logger.info(f"Fetched {len(source_files)} source files for analysis")

        return {
            "documentation_files": documentation_files,
            "documentation_status": documentation_status,
            "source_files": source_files,
            "repo_structure": repo_structure,
        }

    except GitHubAPIError as e:
        logger.error(f"GitHub API error during scan: {e}")
        return {"errors": [f"Failed to scan repository: {e.message}"]}
    except Exception as e:
        logger.exception("Unexpected error scanning repository")
        return {"errors": [f"Unexpected error scanning repository: {str(e)}"]}


def _find_documentation_files(all_files: list[str]) -> list[str]:
    """Filter file list to find documentation files.

    Args:
        all_files: List of all file paths in repo

    Returns:
        List of documentation file paths
    """
    doc_files = []

    for file_path in all_files:
        # Skip excluded patterns
        if _matches_any_pattern(file_path, EXCLUDE_PATTERNS):
            continue

        # Check if it matches documentation patterns
        if _is_documentation_file(file_path):
            doc_files.append(file_path)

    return doc_files


def _is_documentation_file(path: str) -> bool:
    """Check if a file path is a documentation file.

    Args:
        path: File path

    Returns:
        True if file appears to be documentation
    """
    lower_path = path.lower()

    # Check explicit doc directories
    if any(d in lower_path for d in ["docs/", "doc/", "documentation/"]):
        return True

    # Check file patterns
    if _matches_any_pattern(path, DOC_PATTERNS):
        return True

    # Check common documentation filenames
    filename = path.split("/")[-1].lower()
    doc_names = [
        "readme",
        "changelog",
        "changes",
        "history",
        "contributing",
        "authors",
        "license",
        "api",
        "index",
        "getting-started",
        "installation",
        "configuration",
        "usage",
        "faq",
        "troubleshooting",
    ]

    name_without_ext = filename.rsplit(".", 1)[0] if "." in filename else filename
    return name_without_ext in doc_names


def _matches_any_pattern(path: str, patterns: list[str]) -> bool:
    """Check if path matches any of the given patterns.

    Args:
        path: File path
        patterns: List of glob patterns

    Returns:
        True if path matches any pattern
    """
    for pattern in patterns:
        if fnmatch.fnmatch(path.lower(), pattern.lower()):
            return True
        # Also check if pattern is in the path (for directory patterns)
        if pattern.endswith("/*") and pattern[:-2].lower() in path.lower():
            return True
    return False


def _classify_doc_type(path: str) -> str:
    """Classify the type of documentation file.

    Args:
        path: File path

    Returns:
        Documentation type string
    """
    lower_path = path.lower()
    filename = lower_path.split("/")[-1]

    if "readme" in filename:
        return "readme"
    if "changelog" in filename or "changes" in filename or "history" in filename:
        return "changelog"
    if "api" in lower_path or "reference" in lower_path:
        return "api"
    if "contributing" in filename:
        return "guide"
    if any(ext in filename for ext in [".yaml", ".yml", ".toml", ".json"]):
        return "config"
    if "docs/" in lower_path or "doc/" in lower_path:
        return "guide"

    return "other"


async def _fetch_doc_file(
    fetcher: PRFetcher,
    owner: str,
    repo: str,
    path: str,
    ref: str,
) -> Optional[DocumentationFile]:
    """Fetch a documentation file and its content.

    Args:
        fetcher: PR fetcher instance
        owner: Repository owner
        repo: Repository name
        path: File path
        ref: Git ref

    Returns:
        DocumentationFile or None if fetch fails
    """
    try:
        content = await fetcher.fetch_file_content(
            owner=owner,
            repo=repo,
            path=path,
            ref=ref,
        )

        if content is None:
            return None

        # Skip very large files
        size = len(content.encode("utf-8"))
        if size > MAX_CONTENT_SIZE:
            logger.debug(f"Skipping large file: {path} ({size} bytes)")
            return DocumentationFile(
                path=path,
                doc_type=_classify_doc_type(path),
                content=None,  # Don't store large content
                size=size,
            )

        return DocumentationFile(
            path=path,
            doc_type=_classify_doc_type(path),
            content=content,
            size=size,
        )

    except Exception as e:
        logger.debug(f"Failed to fetch {path}: {e}")
        return None


def _build_repo_structure(all_files: list[str]) -> str:
    """Build a tree-like summary of repository structure.

    Args:
        all_files: List of all file paths

    Returns:
        String representation of repo structure
    """
    # Build directory tree
    dirs: set[str] = set()
    for path in all_files:
        parts = path.split("/")
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]))

    # Get top-level structure (max 3 levels deep)
    top_dirs = sorted([d for d in dirs if d.count("/") <= 2])

    # Count files per top-level directory
    file_counts: dict[str, int] = {}
    for path in all_files:
        top = path.split("/")[0]
        file_counts[top] = file_counts.get(top, 0) + 1

    # Build summary
    lines = ["Repository Structure:", ""]

    # Show top-level directories with file counts
    shown_dirs = set()
    for d in top_dirs:
        top = d.split("/")[0]
        if top not in shown_dirs:
            count = file_counts.get(top, 0)
            lines.append(f"  {top}/ ({count} files)")
            shown_dirs.add(top)

    # Add total
    lines.append("")
    lines.append(f"Total: {len(all_files)} files")

    return "\n".join(lines)


def _find_source_files(all_files: list[str]) -> list[str]:
    """Find source code files for comprehensive documentation analysis.

    Prioritizes main entry points and important files.

    Args:
        all_files: List of all file paths in repo

    Returns:
        List of source file paths, sorted by importance
    """
    source_files = []
    priority_files = []  # Files that should come first

    for file_path in all_files:
        # Skip excluded patterns
        if _matches_any_pattern(file_path, EXCLUDE_PATTERNS):
            continue

        # Skip test files
        lower_path = file_path.lower()
        if any(skip in lower_path for skip in ["test", "spec", "__pycache__", ".git"]):
            continue

        # Check if it's a source code file
        if _is_source_code_file(file_path):
            # Prioritize certain files
            filename = file_path.split("/")[-1].lower()
            if filename in ["main.py", "app.py", "index.js", "index.ts", "main.go", "main.rs", "main.java"]:
                priority_files.append(file_path)
            elif filename.startswith("__init__") or filename == "mod.rs":
                priority_files.append(file_path)
            else:
                source_files.append(file_path)

    # Return priority files first, then others
    return priority_files + source_files


def _is_source_code_file(path: str) -> bool:
    """Check if a file path is a source code file.

    Args:
        path: File path

    Returns:
        True if file appears to be source code
    """
    lower_path = path.lower()

    for ext in SOURCE_CODE_EXTENSIONS:
        if lower_path.endswith(ext):
            return True

    return False


async def _fetch_source_file(
    fetcher: PRFetcher,
    owner: str,
    repo: str,
    path: str,
    ref: str,
) -> Optional[SourceFile]:
    """Fetch a source code file and its content.

    Args:
        fetcher: PR fetcher instance
        owner: Repository owner
        repo: Repository name
        path: File path
        ref: Git ref

    Returns:
        SourceFile or None if fetch fails
    """
    try:
        content = await fetcher.fetch_file_content(
            owner=owner,
            repo=repo,
            path=path,
            ref=ref,
        )

        if content is None:
            return None

        # Skip very large files
        size = len(content.encode("utf-8"))
        if size > MAX_SOURCE_FILE_SIZE:
            logger.debug(f"Skipping large source file: {path} ({size} bytes)")
            return None

        return SourceFile(
            path=path,
            content=content,
            size=size,
        )

    except Exception as e:
        logger.debug(f"Failed to fetch source file {path}: {e}")
        return None
