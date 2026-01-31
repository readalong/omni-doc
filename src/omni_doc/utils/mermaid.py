"""Mermaid diagram validation and sanitization utilities."""

import re
from typing import Optional, Tuple

from omni_doc.utils.logging import get_logger

logger = get_logger(__name__)

# Characters that cause issues in Mermaid labels
PROBLEMATIC_IN_EDGE_LABELS = ['(', ')', '[', ']', '{', '}', '<', '>', '"', '#', ';', '|']
PROBLEMATIC_IN_NODE_LABELS = ['(', ')', '&', '#', '<', '>']

# Common Mermaid syntax patterns
FLOWCHART_PATTERN = re.compile(r'^(flowchart|graph)\s+(TD|TB|BT|RL|LR)', re.MULTILINE)
SEQUENCE_PATTERN = re.compile(r'^sequenceDiagram', re.MULTILINE)
CLASS_PATTERN = re.compile(r'^classDiagram', re.MULTILINE)
STATE_PATTERN = re.compile(r'^stateDiagram', re.MULTILINE)

# Edge label pattern: matches -->|label|, ---|label|, -.->|label|, ==>|label|, etc.
# Captures the edge operator, the label, and what follows
EDGE_LABEL_PATTERN = re.compile(
    r'(--?>|---|-\.->|==?>|~~>|--o|--x|<-->|<-\.->|<==?>)'  # Edge operators
    r'\|([^|]*)\|'  # Label between pipes
)

# Node definition patterns - captures node ID and label
# Matches: A[label], A(label), A{label}, A((label)), A>label], A[/label/], etc.
NODE_LABEL_PATTERN = re.compile(
    r'(\b[A-Za-z_][A-Za-z0-9_]*)\s*'  # Node ID
    r'(\[|\(|\{|\[\[|\(\(|\[\(|\[/|>\[?)'  # Opening bracket
    r'([^\]\)\}]+?)'  # Label content (non-greedy)
    r'(\]|\)|\}|\]\]|\)\)|\)\]|/\]|\])'  # Closing bracket
)


def validate_mermaid(diagram_code: str) -> Tuple[bool, Optional[str]]:
    """Validate Mermaid diagram syntax.

    Performs syntax validation to catch common issues that would
    prevent the diagram from rendering.

    Args:
        diagram_code: The Mermaid diagram code

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not diagram_code or not diagram_code.strip():
        return False, "Empty diagram code"

    code = diagram_code.strip()

    # Check for valid diagram type
    has_valid_type = (
        FLOWCHART_PATTERN.search(code) or
        SEQUENCE_PATTERN.search(code) or
        CLASS_PATTERN.search(code) or
        STATE_PATTERN.search(code)
    )

    if not has_valid_type:
        return False, "No valid diagram type found (flowchart, sequenceDiagram, classDiagram, stateDiagram)"

    # Check for unbalanced brackets (excluding edge labels)
    is_balanced, bracket_error = _check_bracket_balance(code)
    if not is_balanced:
        return False, bracket_error

    # Check for problematic edge labels
    edge_issues = _check_edge_labels(code)
    if edge_issues:
        return False, edge_issues

    # Check for problematic node labels
    node_issues = _check_node_labels(code)
    if node_issues:
        return False, node_issues

    return True, None


def _check_bracket_balance(code: str) -> Tuple[bool, Optional[str]]:
    """Check for unbalanced brackets in code.

    Args:
        code: Mermaid diagram code

    Returns:
        Tuple of (is_balanced, error_message)
    """
    brackets = {'[': ']', '(': ')', '{': '}'}
    stack = []
    in_string = False
    in_edge_label = False
    string_char = None

    for i, char in enumerate(code):
        # Track edge labels (|...|) - skip bracket checking inside them
        if char == '|' and not in_string:
            in_edge_label = not in_edge_label
            continue

        if in_edge_label:
            continue

        # Handle string literals
        if char in ['"', "'"] and (i == 0 or code[i-1] != '\\'):
            if not in_string:
                in_string = True
                string_char = char
            elif char == string_char:
                in_string = False
                string_char = None
            continue

        if in_string:
            continue

        if char in brackets:
            stack.append((char, i))
        elif char in brackets.values():
            if not stack:
                return False, f"Unbalanced bracket '{char}' at position {i}"
            expected_open, _ = stack.pop()
            expected_close = brackets[expected_open]
            if char != expected_close:
                return False, f"Mismatched bracket: expected '{expected_close}', got '{char}' at position {i}"

    if stack:
        unclosed = [b[0] for b in stack]
        return False, f"Unclosed brackets: {unclosed}"

    return True, None


def _check_edge_labels(code: str) -> Optional[str]:
    """Check for problematic characters in edge labels.

    Args:
        code: Mermaid diagram code

    Returns:
        Error message if issues found, None otherwise
    """
    for match in EDGE_LABEL_PATTERN.finditer(code):
        label = match.group(2)
        # Check for problematic characters in edge labels
        for char in PROBLEMATIC_IN_EDGE_LABELS:
            if char in label and char != '|':  # | is the delimiter, already handled
                return f"Edge label contains problematic character '{char}': |{label}|"

    return None


def _check_node_labels(code: str) -> Optional[str]:
    """Check for problematic characters in node labels.

    Args:
        code: Mermaid diagram code

    Returns:
        Error message if issues found, None otherwise
    """
    for match in NODE_LABEL_PATTERN.finditer(code):
        label = match.group(3)
        node_id = match.group(1)

        # Check if label has problematic chars and isn't quoted
        if '"' not in match.group(0):  # Not already quoted
            for char in PROBLEMATIC_IN_NODE_LABELS:
                if char in label:
                    return f"Node '{node_id}' has unquoted special character '{char}' in label: {label}"

    return None


def sanitize_mermaid(diagram_code: str) -> str:
    """Sanitize Mermaid diagram code to fix common issues.

    Fixes:
    - Problematic characters in edge labels (removes parentheses, brackets, etc.)
    - Unquoted labels with special characters in node definitions

    Args:
        diagram_code: The Mermaid diagram code

    Returns:
        Sanitized diagram code
    """
    if not diagram_code:
        return diagram_code

    code = diagram_code

    # First pass: sanitize edge labels
    code = _sanitize_edge_labels(code)

    # Second pass: sanitize node labels
    code = _sanitize_node_labels(code)

    return code


def _sanitize_edge_labels(code: str) -> str:
    """Sanitize edge labels by removing problematic characters.

    Args:
        code: Mermaid diagram code

    Returns:
        Code with sanitized edge labels
    """
    def clean_edge_label(match):
        edge_op = match.group(1)
        label = match.group(2)

        # Remove problematic characters from edge labels
        # Replace parentheses content like "(Markdown)" with just the word
        cleaned = re.sub(r'\s*\([^)]*\)', '', label)

        # Remove any remaining problematic characters
        for char in ['[', ']', '{', '}', '<', '>', '#', ';']:
            cleaned = cleaned.replace(char, '')

        # Clean up extra whitespace
        cleaned = ' '.join(cleaned.split())

        return f'{edge_op}|{cleaned}|'

    return EDGE_LABEL_PATTERN.sub(clean_edge_label, code)


def _sanitize_node_labels(code: str) -> str:
    """Sanitize node labels in the code.

    Args:
        code: Mermaid diagram code

    Returns:
        Code with sanitized node labels
    """
    lines = code.split('\n')
    sanitized_lines = []

    for line in lines:
        # Skip empty lines and comments
        if not line.strip() or line.strip().startswith('%%'):
            sanitized_lines.append(line)
            continue

        sanitized_line = _sanitize_node_labels_in_line(line)
        sanitized_lines.append(sanitized_line)

    return '\n'.join(sanitized_lines)


def _sanitize_node_labels_in_line(line: str) -> str:
    """Sanitize node labels in a single line.

    Args:
        line: A single line of Mermaid code

    Returns:
        Line with sanitized node labels
    """
    result = line

    # Pattern for square bracket nodes: ID[label]
    square_pattern = re.compile(r'(\b[A-Za-z_][A-Za-z0-9_]*)\[([^\]"]+)\]')

    def quote_square_if_needed(match):
        node_id = match.group(1)
        label = match.group(2)

        # Check if label needs quoting
        needs_quoting = any(c in label for c in PROBLEMATIC_IN_NODE_LABELS)

        if needs_quoting:
            escaped_label = label.replace('"', '\\"')
            return f'{node_id}["{escaped_label}"]'

        return match.group(0)

    result = square_pattern.sub(quote_square_if_needed, result)

    # Pattern for round bracket nodes: ID(label)
    # Be careful not to match function calls or edge labels
    round_pattern = re.compile(r'(\b[A-Za-z_][A-Za-z0-9_]*)\(([^\)"]+)\)(?!\|)')

    def quote_round_if_needed(match):
        node_id = match.group(1)
        label = match.group(2)

        # Skip if this looks like a function call (followed by certain patterns)
        if node_id.lower() in ['subgraph', 'end', 'click', 'style', 'class', 'linkstyle']:
            return match.group(0)

        # Check if label needs quoting
        needs_quoting = any(c in label for c in PROBLEMATIC_IN_NODE_LABELS)

        if needs_quoting:
            escaped_label = label.replace('"', '\\"')
            return f'{node_id}("{escaped_label}")'

        return match.group(0)

    result = round_pattern.sub(quote_round_if_needed, result)

    return result


def extract_diagram_code(text: str) -> Optional[str]:
    """Extract Mermaid diagram code from markdown code block.

    Args:
        text: Text that may contain a mermaid code block

    Returns:
        The diagram code without markdown fences, or None
    """
    # Look for ```mermaid ... ``` block
    pattern = re.compile(r'```mermaid\s*\n(.*?)\n```', re.DOTALL)
    match = pattern.search(text)

    if match:
        return match.group(1).strip()

    # If no code block, assume the entire text is diagram code
    if text.strip().startswith(('flowchart', 'graph', 'sequenceDiagram', 'classDiagram', 'stateDiagram')):
        return text.strip()

    return None


def validate_and_sanitize(diagram_code: str) -> Tuple[str, bool, Optional[str]]:
    """Validate and sanitize a Mermaid diagram in one call.

    This is the recommended function to use - it validates, sanitizes,
    and re-validates to ensure the output is clean.

    Args:
        diagram_code: The Mermaid diagram code

    Returns:
        Tuple of (sanitized_code, is_valid, error_message)
    """
    if not diagram_code:
        return "", False, "Empty diagram code"

    # First validation
    is_valid, error = validate_mermaid(diagram_code)

    if not is_valid:
        logger.debug(f"Initial validation failed: {error}")

    # Always sanitize
    sanitized = sanitize_mermaid(diagram_code)

    # Re-validate
    is_valid_after, error_after = validate_mermaid(sanitized)

    if is_valid_after:
        return sanitized, True, None
    else:
        logger.warning(f"Diagram still invalid after sanitization: {error_after}")
        return sanitized, False, error_after
