"""Origin risk facts for the background-work roadmap (t1569_5).

The IMPURE half of the roadmap's origin layer: it reads task frontmatter --
active files and archived bundles -- and emits one ``ORIGIN_FACT:`` record per
``(task, origin)`` pair. ``roadmap_policy`` consumes those records and never
touches a filesystem, exactly the split ``parallel_admission.py`` /
``parallel_admission_collect.py`` already uses.

WHY THIS EXISTS AT ALL. Origin risk (``risk_code_health:`` /
``risk_goal_achievement:``) is the roadmap's primary value signal, and it lives
on the *origin*, which is usually archived: measured 2026-08-31, 8 active task
files carry ``risk_code_health:`` against 203 archived ones. t1569_1's gatherer
emits ``MEMBER_EXT:`` only for members in scope, so an archived origin has no
producer anywhere in the landed siblings. This is that producer.

ONE ROW PER (TASK, ORIGIN) -- NEVER ONE ROW PER TASK. 25 of 89 exact follow-ups
carry more than one origin (up to 11), 13 of those disagree on a risk level, and
6 span mixed sources. Collapsing them here would bake a *policy* decision into a
*facts* producer, and a "first origin wins" reduction silently reports t1064 as
`low` while one of its origins is `medium`. The reduction rule lives in
``roadmap_policy``, where it is purely testable.

NEVER INFER FROM AN ABSENT LINE. A task whose quality is ``unknown`` still gets
exactly one row, with ``origin_id`` = ``-``. Every field has a sentinel, so a
missing fact and a missing task are distinguishable.

Record (fields ``%``-then-``|`` encoded, free-ish field last)::

    ORIGIN_FACT:<task_id>|<origin_id>|<quality>|<rch>|<rga>|<source>

``quality`` is ``followup_origin``'s ``exact|topic|unknown`` and is a property
of the TASK, repeated on each of its rows. ``source`` is a property of the
ORIGIN: ``active`` | ``archived`` | ``absent``.

Every content state exits 0; CLI misuse exits 2 -- the same split
``aitask_verification_stale.sh`` and ``parallel_admission_collect.py`` use.
"""

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import followup_origin as fo  # noqa: E402
import parallel_admission_vocab as vocab  # noqa: E402
from archive_iter import find_archived_markdown_by_id  # noqa: E402
from task_yaml import parse_frontmatter  # noqa: E402

EXIT_OK = 0
EXIT_USAGE = 2

SOURCES = ("active", "archived", "absent")
SENTINEL = "-"

_TASK_FILE_RE = re.compile(r"^t(\d+(?:_\d+)?)_.*\.md$")


def _dirs():
    """(task_dir, archived_dir), env-aware -- the same knobs trail_gather reads."""
    task_dir = Path(os.environ.get("TASK_DIR", "aitasks"))
    archived = Path(os.environ.get("ARCHIVED_DIR", str(task_dir / "archived")))
    return task_dir, archived


def active_frontmatter(task_dir):
    """``{task_id: metadata}`` for every active parent and child task file."""
    out = {}
    candidates = (sorted(task_dir.glob("t*_*.md"))
                  + sorted(task_dir.glob("t*/t*_*.md")))
    for path in candidates:
        match = _TASK_FILE_RE.match(path.name)
        if not match:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        parsed = parse_frontmatter(text)
        if parsed:
            out[match.group(1)] = parsed[0]
    return out


def origin_facts(task_id, metadata, active, archived_dir):
    """One ``(task_id, origin_id, quality, rch, rga, source)`` tuple per origin.

    A task with no resolvable origin yields exactly one tuple whose origin is the
    sentinel -- absence is reported, never inferred from a missing line.
    """
    origins, quality = fo.resolve(metadata)
    if not origins:
        return [(task_id, SENTINEL, quality, SENTINEL, SENTINEL, "absent")]

    rows = []
    for origin in origins:
        source, risk = _lookup(origin, active, archived_dir)
        rows.append((task_id, origin, quality, risk[0], risk[1], source))
    return rows


def _lookup(origin_id, active, archived_dir):
    """Where an origin's frontmatter lives, and its two risk axes.

    Active wins over archived: a task present in both is mid-archival, and the
    active copy is the one the rest of the framework treats as current.
    """
    metadata = active.get(origin_id)
    if metadata is not None:
        return "active", _risk(metadata)

    found = find_archived_markdown_by_id(origin_id, Path(archived_dir))
    if found:
        parsed = parse_frontmatter(found[1])
        # An archived file that will not parse is still ARCHIVED -- reporting it
        # as `absent` would blame the lookup for a malformed file.
        return "archived", _risk(parsed[0]) if parsed else (SENTINEL, SENTINEL)
    return "absent", (SENTINEL, SENTINEL)


def _risk(metadata):
    def axis(key):
        value = str(metadata.get(key, "") or "").strip()
        return value or SENTINEL
    return axis("risk_code_health"), axis("risk_goal_achievement")


def render(rows):
    """Tuples -> ``ORIGIN_FACT:`` lines, every field encoded."""
    return ["ORIGIN_FACT:" + "|".join(vocab.encode_path(f) for f in row)
            for row in rows]


def collect(task_ids=None, task_dir=None, archived_dir=None):
    """``ORIGIN_FACT:`` lines for every follow-up (or just ``task_ids``).

    With NO ids, the sweep is narrowed to tasks carrying a ``followup_kind:`` --
    they are the ones with an origin to resolve.

    With EXPLICIT ids, every named task is reported whether or not it is a
    follow-up, and one that is not simply resolves to whatever its metadata
    supports (usually ``unknown`` quality and an ``absent`` origin). A caller who
    asked about a task always gets a row back for it. Absence from the output
    NEVER means "not a follow-up" -- nothing in this protocol may be inferred
    from a missing line, which is why even an id with no task file at all gets a
    row (plus a stderr warning).
    """
    default_task, default_archived = _dirs()
    task_dir = Path(task_dir) if task_dir else default_task
    archived_dir = Path(archived_dir) if archived_dir else default_archived

    active = active_frontmatter(task_dir)
    wanted = set(task_ids) if task_ids else None

    rows = []
    for task_id in sorted(active, key=_sort_key):
        if wanted is not None and task_id not in wanted:
            continue
        metadata = active[task_id]
        if wanted is None and "followup_kind" not in metadata:
            continue
        rows.extend(origin_facts(task_id, metadata, active, archived_dir))

    # An id the caller named that has no active task file still gets a row.
    # Returning silence would make "no origin facts for this task" and "you
    # asked about a task that does not exist" indistinguishable from each
    # other AND from a task that was simply filtered out -- the exact
    # infer-from-an-absent-line hazard the record format exists to prevent.
    # The row reports the fact; stderr reports the anomaly, so the line
    # protocol stays clean and a caller bug is still visible.
    for task_id in sorted(wanted - set(active), key=_sort_key) if wanted else ():
        print("Warning: no active task file for %s — reporting absent origin"
              % task_id, file=sys.stderr)
        rows.append((task_id, SENTINEL, fo.UNKNOWN, SENTINEL, SENTINEL, "absent"))
    return render(rows)


def _sort_key(task_id):
    parent, _, child = task_id.partition("_")
    return (int(parent), int(child) if child else -1)


def main(argv):
    task_ids, task_dir, archived_dir = [], None, None
    args = list(argv)
    while args:
        arg = args.pop(0)
        if arg == "--task-dir":
            if not args:
                return _usage("--task-dir requires a value")
            task_dir = args.pop(0)
        elif arg == "--archived-dir":
            if not args:
                return _usage("--archived-dir requires a value")
            archived_dir = args.pop(0)
        elif arg.startswith("-"):
            return _usage("unknown option: %s" % arg)
        else:
            task_ids.append(arg)

    for line in collect(task_ids or None, task_dir, archived_dir):
        print(line)
    return EXIT_OK


def _usage(message):
    print("usage: roadmap_origin_facts.py [--task-dir <d>] "
          "[--archived-dir <d>] [<task_id> ...]", file=sys.stderr)
    print("error: %s" % message, file=sys.stderr)
    return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
