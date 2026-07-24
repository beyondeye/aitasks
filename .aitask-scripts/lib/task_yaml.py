"""Shared YAML utilities for aitask frontmatter parsing and serialization.

Base-layer module: the single parser/serializer for task-file frontmatter,
used by the board, the merge tool, the report/trail gatherers and the
codebrowser / diffviewer / monitor TUIs. It originated as an extraction from
aitask_board.py and lived under ``board/`` for that historical reason; it sits
in ``lib/`` because every layer above depends on it and it depends on none of
them (t1217). ``tests/test_no_lib_to_tui_import.sh`` freezes that direction.
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


def normalize_board_idx(raw):
    """Coerce a ``boardidx`` frontmatter value into a sortable int.

    Single source of truth for board-column ordering, shared by the board
    itself and lib/work_report_gather.py so the two can never disagree about
    where a card sits.

    Sorting on the raw YAML value was unsafe in two ways: a hand-quoted
    ``boardidx: "10"`` sorted lexically (so "10" preceded "2"), and mixing a
    quoted value with a plain int raised ``TypeError: '<' not supported
    between instances of 'str' and 'int'`` — crashing the board. An index is
    numeric by intent, so quoted digits are coerced and anything genuinely
    non-numeric sorts first as 0.
    """
    if isinstance(raw, bool):
        return 0
    if isinstance(raw, int):
        return raw
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return 0


# --- Helper Functions ---

def _normalize_task_id(item):
    """Normalize a single task ID reference (scalar analog of _normalize_task_ids).

    A bare child ref (e.g. 85_2) gets a 't' prefix; a plain parent number
    (16, 77) is left as-is (preserving int type); an already-prefixed id
    (t85_2) passes through unchanged. Empty / None pass through untouched.
    Used for the scalar ``anchor`` field.
    """
    if item is None or item == "":
        return item
    s = str(item)
    if re.match(r'^\d+_\d+$', s):
        return f"t{s}"
    return item  # preserve original type (int stays int)


def _normalize_task_ids(ids_list):
    """Normalize task IDs: ensure child task refs (with underscore) have 't' prefix.

    Plain numbers (parent refs like 16, 77) are left as-is (preserving int type).
    Entries already prefixed (t85_2) pass through unchanged.

    A non-list value (hand-edited ``children_to_implement: oops``, a mapping,
    an int) passes through untouched rather than being iterated: comprehending
    over a str yielded a list of its characters and over a dict a list of its
    keys, so callers saw a plausible-looking list and silently counted 4
    "children" for the string "oops". Malformed input stays malformed and
    type-honest, and consumers can detect it.
    """
    if not ids_list or not isinstance(ids_list, list):
        return ids_list
    return [_normalize_task_id(item) for item in ids_list]


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

    # Normalize the scalar topic-anchor id the same way (semantic field,
    # NOT a board-layout key — kept out of BOARD_KEYS).
    if 'anchor' in metadata:
        metadata['anchor'] = _normalize_task_id(metadata['anchor'])

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

    # width=4096 keeps flow lists on a single physical line. PyYAML's
    # default (80) wraps a long list (e.g. children_to_implement) across
    # lines, and the bash frontmatter parsers match line-by-line — a
    # wrapped list would lose its continuation entries on the next edit.
    frontmatter = yaml.dump(ordered, Dumper=_FlowListDumper,
                            default_flow_style=False, sort_keys=False,
                            width=4096)
    return f"---\n{frontmatter}---\n{body}"
