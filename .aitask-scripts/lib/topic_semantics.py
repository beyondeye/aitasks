"""topic_semantics.py - the board's by-topic (group-by-anchor) key semantics.

Extracted verbatim from board/aitask_board.py (t1210_2) so non-board
consumers (lib/trail_gather.py) can resolve topic membership without
importing the Textual board. The board imports these functions back and
remains the SEMANTIC OWNER of the by-topic rules: any future change here
must keep tests/test_board_topic_group.py AND the trail_gather matrix-A
parity fixtures green in the same commit.

Functions are duck-typed over task objects exposing ``.filename`` (the
task file's basename) and ``.metadata`` (parsed frontmatter dict) — the
board's ``Task`` and trail_gather's row type both qualify.
"""

import re


def parse_task_filename(filename):
    """Parse task filenames into (task_num, task_name).
    Child: 't47_1_desc.md' -> ('t47_1', 'desc')
    Parent: 't47_playlists_support.md' -> ('t47', 'playlists support')
    """
    name = filename.removesuffix(".md")
    # Try child pattern first (more specific: second segment is pure digits)
    m = re.match(r'^(t\d+_\d+)_(.+)$', name)
    if m:
        return m.group(1), m.group(2).replace("_", " ")
    # Fall back to parent pattern
    m = re.match(r'^(t\d+)_(.+)$', name)
    if m:
        return m.group(1), m.group(2).replace("_", " ")
    return "", name.replace("_", " ")


def _bare_topic_id(value):
    """Canonicalize a task-id / anchor value to bare string form (leading 't'
    stripped). Returns None for empty/None so 'no anchor' reads uniformly."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return s.lstrip("t")


def task_own_id(task):
    """Bare own id from a task's filename ('1016' or '1016_4'); '' if unparseable."""
    num, _ = parse_task_filename(task.filename)
    return num.lstrip("t")


def task_anchor_id(task):
    """Bare anchor id of a task, or None when the task is its own topic root."""
    return _bare_topic_id(task.metadata.get("anchor"))


def topic_key(task, tasks_by_id):
    """Topic-group key for a task.

    ``anchor`` if set; elif the task is a child → its parent's topic key
    (parent.anchor or parent id) as a *display-time* fallback so legacy
    parent+children trees cluster with no file migration; else the task's
    own id. ``tasks_by_id`` maps bare own id → Task (for the parent lookup).
    """
    anchor = task_anchor_id(task)
    if anchor:
        return anchor
    own = task_own_id(task)
    if own and "_" in own:
        parent = own.split("_", 1)[0]
        parent_task = tasks_by_id.get(parent)
        if parent_task is not None:
            return task_anchor_id(parent_task) or parent
        return parent  # parent not loaded → still cluster under its id
    return own
