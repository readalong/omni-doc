"""Test fixtures for Omni-Doc."""

import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent


def load_sample_pr_response() -> dict:
    """Load sample PR response fixture."""
    with open(FIXTURES_DIR / "sample_pr_response.json") as f:
        return json.load(f)


def load_sample_pr_files() -> list[dict]:
    """Load sample PR files fixture."""
    with open(FIXTURES_DIR / "sample_pr_files.json") as f:
        return json.load(f)


def load_sample_diff() -> str:
    """Load sample diff fixture."""
    with open(FIXTURES_DIR / "sample_diff.patch") as f:
        return f.read()
