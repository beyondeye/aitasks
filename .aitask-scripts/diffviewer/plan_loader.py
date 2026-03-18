"""Plan file I/O: frontmatter parsing and body extraction."""
from __future__ import annotations

import os
import sys

# Import task_yaml from board directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'board'))
from task_yaml import parse_frontmatter


def load_plan(path: str) -> tuple[dict, str, list[str]]:
    """Load a plan file, returning (frontmatter_dict, body_text, body_lines).

    Raises FileNotFoundError if path doesn't exist.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Plan file not found: {path}")

    with open(path, 'r', encoding='utf-8') as f:
        raw = f.read()

    result = parse_frontmatter(raw)
    if result is None:
        # No frontmatter — treat entire content as body
        lines = raw.splitlines(keepends=True)
        return {}, raw, lines

    metadata, body, _key_order = result
    body_lines = body.splitlines(keepends=True)
    return metadata, body, body_lines
