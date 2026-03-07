"""Shared YAML utilities for aitask frontmatter parsing and serialization.

Extracted from aitask_board.py for reuse by aitask_merge.py and other tools.
"""
from __future__ import annotations

import copy
import re

import yaml

# --- YAML Loader ---

class _TaskSafeLoader(yaml.SafeLoader):
    """Custom YAML loader that preserves digit_digit patterns as strings.

    PyYAML (YAML 1.1) treats underscores as digit separators, so '85_2'
    becomes integer 852.  We add a higher-priority string resolver for
    the \\d+_\\d+ pattern to prevent this coercion.
    """
    pass

_TaskSafeLoader.yaml_implicit_resolvers = copy.deepcopy(
    yaml.SafeLoader.yaml_implicit_resolvers
)
for _ch in list('0123456789'):
    _resolvers = _TaskSafeLoader.yaml_implicit_resolvers.get(_ch, [])
    _resolvers.insert(0, ('tag:yaml.org,2002:str', re.compile(r'^\d+_\d+$')))
    _TaskSafeLoader.yaml_implicit_resolvers[_ch] = _resolvers


# --- YAML Dumper ---

class _FlowListDumper(yaml.SafeDumper):
    """Dumper that writes lists in flow style [a, b] but dicts in block style."""
    pass

_FlowListDumper.add_representer(list, lambda dumper, data:
    dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True))


# --- Constants ---

BOARD_KEYS = ("boardcol", "boardidx")

FRONTMATTER_RE = re.compile(r'\A---\n(.*?)\n---\n(.*)', re.DOTALL)


# --- Helper Functions ---

def _normalize_task_ids(ids_list):
    """Normalize task IDs: ensure child task refs (with underscore) have 't' prefix.

    Plain numbers (parent refs like 16, 77) are left as-is.
    Entries already prefixed (t85_2) pass through unchanged.
    """
    if not ids_list:
        return ids_list
    return [f"t{s}" if re.match(r'^\d+_\d+$', s := str(item)) else s
            for item in ids_list]


def parse_frontmatter(raw_text: str):
    """Parse YAML frontmatter from raw task file text.

    Returns:
        tuple[dict, str, list]: (metadata, body, original_key_order) if
            frontmatter is found.
        None: if no frontmatter delimiter is found.
    """
    m = FRONTMATTER_RE.match(raw_text)
    if not m:
        return None

    metadata = yaml.load(m.group(1), Loader=_TaskSafeLoader) or {}
    original_key_order = list(metadata.keys())
    body = m.group(2)

    # Normalize child task ID references to always have 't' prefix
    for key in ('depends', 'children_to_implement', 'folded_tasks'):
        if key in metadata:
            metadata[key] = _normalize_task_ids(metadata[key])

    return (metadata, body, original_key_order)


def serialize_frontmatter(metadata: dict, body: str, original_key_order: list) -> str:
    """Serialize metadata and body back into a task file string.

    Keys are ordered: original order first, then new non-board keys,
    board keys (boardcol, boardidx) always last.

    Returns:
        str: Complete file content with ``---`` delimited frontmatter.
    """
    ordered = {}
    # Original keys first
    for key in original_key_order:
        if key in metadata:
            ordered[key] = metadata[key]
    # Any new non-board keys
    for key in metadata:
        if key not in ordered and key not in BOARD_KEYS:
            ordered[key] = metadata[key]
    # Board keys always last
    for key in BOARD_KEYS:
        if key in metadata:
            ordered[key] = metadata[key]

    frontmatter = yaml.dump(ordered, Dumper=_FlowListDumper,
                            default_flow_style=False, sort_keys=False)
    return f"---\n{frontmatter}---\n{body}"
