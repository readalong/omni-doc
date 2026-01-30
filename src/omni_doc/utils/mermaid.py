"""Mermaid diagram validation and sanitization utilities."""

import re
from typing import Optional, Tuple

from omni_doc.utils.logging import get_logger

logger = get_logger(__name__)

# Characters that need special handling in Mermaid node labels
SPECIAL_CHARS = ['(', ')', '[', ']', '{', '}', '<', '>', '"', "'", '&', '#', ';']

# Common Mermaid syntax patterns
FLOWCHART_PATTERN = re.compile(r'^(flowchart|graph)\s+(TD|TB|BT|RL|LR)', re.MULTILINE)
SEQUENCE_PATTERN = re.compile(r'^sequenceDiagram', re.MULTILINE)
CLASS_PATTERN = re.compile(r'^classDiagram', re.MULTILINE)
STATE_PATTERN = re.compile(r'^stateDiagram', re.MULTILINE)

# Node definition patterns - captures node ID and label
# Matches: A[label], A(label), A{label}, A((label)), A>label], A[/label/], etc.
NODE_PATTERN = re.compile(
    r'([A-Za-z_][A-Za-z0-9_]*)\s*'  # Node ID
    r'(\[|\(|\{|\[\[|\(\(|\[\(|\[/|>\[?)'  # Opening bracket
    r'([^\]\)\}]+?)'  # Label content (non-greedy)
    r'(\]|\)|\}|\]\]|\)\)|\)\]|/\]|\])'  # Closing bracket
)


def validate_mermaid(diagram_code: str) -> Tuple[bool, Optional[str]]:
    """Validate Mermaid diagram syntax.

    Performs basic syntax validation without actually rendering.

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

    # Check for unbalanced brackets in the overall code
    brackets = {'[': ']', '(': ')', '{': '}'}
    stack = []
    in_string = False
    string_char = None

    for i, char in enumerate(code):
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
            stack.append(char)
        elif char in brackets.values():
            if not stack:
                return False, f"Unbalanced bracket '{char}' at position {i}"
            expected = brackets[stack.pop()]
            if char != expected:
                return False, f"Mismatched bracket: expected '{expected}', got '{char}' at position {i}"

    if stack:
        return False, f"Unclosed brackets: {stack}"

    # Check for problematic patterns in node labels
    for match in NODE_PATTERN.finditer(code):
        label = match.group(3)
        # Check for unquoted special characters
        if any(c in label for c in ['(', ')']) and '"' not in match.group(0):
            # Parentheses in unquoted labels can cause issues
            node_id = match.group(1)
            return False, f"Node '{node_id}' has parentheses in label without quotes: {label}"

    return True, None


def sanitize_mermaid(diagram_code: str) -> str:
    """Sanitize Mermaid diagram code to fix common issues.

    Fixes:
    - Unquoted labels with special characters
    - Common syntax errors

    Args:
        diagram_code: The Mermaid diagram code

    Returns:
        Sanitized diagram code
    """
    if not diagram_code:
        return diagram_code

    lines = diagram_code.split('\n')
    sanitized_lines = []

    for line in lines:
        # Skip empty lines and comments
        if not line.strip() or line.strip().startswith('%%'):
            sanitized_lines.append(line)
            continue

        # Fix node labels with special characters
        sanitized_line = _sanitize_node_labels(line)
        sanitized_lines.append(sanitized_line)

    return '\n'.join(sanitized_lines)


def _sanitize_node_labels(line: str) -> str:
    """Sanitize node labels in a single line.

    Args:
        line: A single line of Mermaid code

    Returns:
        Line with sanitized node labels
    """
    # Simpler approach: find patterns like X[text with (parens)] and quote them
    # Pattern matches node definitions: ID[label], ID(label), ID{label}
    result = line

    # Find all node labels that need quoting
    # Pattern: word followed by [ then content then ]
    import re
    node_pattern = re.compile(r'(\b[A-Za-z_][A-Za-z0-9_]*)\[([^\]"]+)\]')

    def quote_if_needed(match):
        node_id = match.group(1)
        label = match.group(2)

        # Check if label needs quoting (has special chars and isn't already quoted)
        needs_quoting = any(c in label for c in ['(', ')', '&', '#', '<', '>'])

        if needs_quoting:
            # Quote the label
            escaped_label = label.replace('"', '\\"')
            return f'{node_id}["{escaped_label}"]'

        return match.group(0)

    result = node_pattern.sub(quote_if_needed, result)

    # Also handle round brackets () which are used for rounded nodes
    round_pattern = re.compile(r'(\b[A-Za-z_][A-Za-z0-9_]*)\(([^\)"]+)\)')

    def quote_round_if_needed(match):
        node_id = match.group(1)
        label = match.group(2)

        # Check if label needs quoting
        needs_quoting = any(c in label for c in ['(', ')', '&', '#', '<', '>'])

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
