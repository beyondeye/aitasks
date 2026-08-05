"""Textual-free, root-scoped board-column vocabulary and writer (t1377_1).

The board TUI owns column *semantics*; this module owns the parts that must be
readable and writable **without importing Textual** — so `monitor/` (and any
other headless caller) can list columns and move a task into one. It is the
seam `ait minimonitor` calls through `aitask_board_column.sh`.

Why it exists: `board/aitask_board.py` imports Textual at module scope and reads
module-level, cwd-relative `TASKS_DIR` / `METADATA_FILE`, so `TaskManager` cannot
be imported from `monitor/`. `aitask_update.sh --boardcol` could not fill the gap
either — it computes no `boardidx` and validated no column id.

Root-scoping
------------
**Every entry point takes an explicit ``root``.** Nothing here may call
``config_utils.task_dir()`` / ``metadata_dir()``: those read ``TASK_DIR`` and cwd
ambiently, while minimonitor's ``target_root`` may be a *different project*.

``task_dir`` is likewise an explicit parameter rather than an ambient read.
``TASK_DIR`` is an **env-only** override with no per-project source (every script
does ``TASK_DIR="${TASK_DIR:-aitasks}"``; nothing reads it from
``project_config.yaml``), so a foreign root's layout is undiscoverable — quietly
applying *this* process's ``TASK_DIR`` to another project would be actively
wrong. Callers that do know their own layout pass it (``aitask_update.sh``
forwards its ``$TASK_DIR``); everyone else gets the enforced default.

Both are validated, because ``root`` and ``task_dir`` together define a mutation
boundary and ``task_dir`` reaches this module from a CLI:

* ``Path.__truediv__`` **discards the left operand when the right is absolute**
  (``Path("/proj") / "/etc"`` is ``/etc``), and ``..`` traverses out — so an
  unchecked ``task_dir`` would defeat root-scoping entirely. See
  :func:`tasks_dir`.
* A layout that does not exist is refused (:class:`UnsupportedLayoutError`)
  rather than degraded: ``load_layered_config`` returns the stock defaults for a
  *missing* file, so a wrong layout would otherwise report a confident
  ``now``/``next``/``backlog`` board for a project that has neither.

Atomicity boundary
------------------
Writes go through ``lib/atomic_write.py``, which gives **reader-visible
atomicity, not writer serialization**: two concurrent read-modify-writes each
render from the same old text and the second replace discards the first.
``Task.reload_and_save_board_fields`` documents itself as "best-effort, not
atomic" for the same reason, so this seam *matches* the board rather than
regressing it. **No lock is taken here — do not claim one.**

Deletion is guarded but not eliminated. ``atomic_write.commit`` is an
unconditional ``os.replace``, so a task archived between parse and write would
otherwise be silently **recreated**. :func:`_assert_same_file` re-checks the
target's identity immediately before the rename and refuses ``vanished``. That is
a **best-effort TOCTOU narrowing, not a guarantee**: a deletion landing between
the check and the rename still recreates the file. The promise is "does not
recreate a file that was already gone when we checked" — nothing stronger.

Imports are restricted to ``lib/`` siblings; importing ``aitask_board`` is frozen
by ``tests/test_no_lib_to_tui_import.sh`` and would drag Textual back in.
"""

from __future__ import annotations

import dataclasses
import os
import re
from pathlib import Path

from atomic_write import commit as _atomic_commit
from atomic_write import discard as _atomic_discard
from atomic_write import prepare as _atomic_prepare
from board_ordering import index_for_append
from config_utils import load_layered_config
from task_yaml import (
    BOARD_KEYS,
    normalize_board_idx,
    parse_frontmatter,
    serialize_frontmatter,
)

__all__ = [
    "DEFAULT_COLUMNS", "DEFAULT_ORDER", "DEFAULT_TASK_DIR",
    "UNORDERED_ID", "UNORDERED_TITLE", "UNORDERED_COLOR",
    "BoardColumnsError", "ColumnIdError", "UnsafeTaskDirError",
    "UnsupportedLayoutError",
    "ColumnRecord", "ColumnQuery", "MoveOutcome",
    "tasks_dir", "board_config_path",
    "column_records", "column_records_at", "load_columns", "load_columns_at",
    "column_indices", "task_column", "move_task_to_column",
]

# --- Column vocabulary -------------------------------------------------------
#
# Single source of truth. These used to exist byte-identically in BOTH
# board/aitask_board.py and lib/work_report_gather.py, the latter carrying a
# comment declaring the manual-sync obligation — the drift hazard this removes.
# Both now import from here.

DEFAULT_COLUMNS = [
    {"id": "now", "title": "Now ⚡", "color": "#FF5555"},
    {"id": "next", "title": "Next Week 📅", "color": "#50FA7B"},
    {"id": "backlog", "title": "Backlog 🗄️", "color": "#BD93F9"},
]
DEFAULT_ORDER = ["now", "next", "backlog"]

#: The synthetic column. It is NOT in `columns` / `column_order`: the board
#: hand-injects it and it exists only while some task has no column of its own
#: (aitask_board.py:8193-8196). A task with no `boardcol` reads as this id
#: (aitask_board.py:357).
UNORDERED_ID = "unordered"
UNORDERED_TITLE = "Unsorted / Inbox"
UNORDERED_COLOR = "gray"

#: The only task-directory layout this framework ships. See the module docstring
#: for why it is a parameter rather than an ambient `TASK_DIR` read.
DEFAULT_TASK_DIR = "aitasks"

_BOARD_CONFIG_NAME = "board_config.json"

#: Characters that cannot round-trip the `|`-delimited report/CLI protocols.
_RECORD_BREAKING = ("|", "\r", "\n")

# A task id is untrusted input that reaches a glob, so it is matched, never
# quoted. `^\d+$` is what makes `*`, `1*`, `../x` and `t42` inert.
_PARENT_ID_RE = re.compile(r"^\d+$")
_CHILD_ID_RE = re.compile(r"^\d+_\d+$")


# --- Errors ------------------------------------------------------------------

class BoardColumnsError(ValueError):
    """Base for this module's refusals. Carries a stable machine `reason`."""

    reason = "board_columns_error"


class ColumnIdError(BoardColumnsError):
    """A configured column id carries '|', CR or LF.

    Raised rather than exited: `work_report_gather.load_columns()` catches this
    and re-emits through its own `_die(..., EXIT_INFRA)` so the report
    protocol's fail-closed behaviour and message prefix are unchanged, while the
    library path stays importable into a TUI (a `sys.exit` in a render path
    would kill the app).
    """

    reason = "invalid_column_id"


class UnsafeTaskDirError(BoardColumnsError):
    """`task_dir` is absolute, traverses out of `root`, or is empty."""

    reason = "unsafe_task_dir"


class UnsupportedLayoutError(BoardColumnsError):
    """The composed task directory does not exist under `root`."""

    reason = "unsupported_layout"


# --- Value objects -----------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class ColumnRecord:
    """One board column as configured. `color` is cosmetic and may be absent."""

    id: str
    title: str
    color: str | None = None


@dataclasses.dataclass(frozen=True)
class ColumnQuery:
    """Which column a task currently sits in, or why that could not be told."""

    col_id: str | None = None
    filename: str | None = None
    refused: tuple[tuple[str, str], ...] = ()

    @property
    def ok(self) -> bool:
        return not self.refused


@dataclasses.dataclass(frozen=True)
class MoveOutcome:
    """Outcome of a single move.

    A bare bool cannot tell a caller WHICH item was refused or why, and
    minimonitor has to name that back to the user — so refusals are
    `(task_id, reason)` pairs. `refused` non-empty always means NOTHING was
    written.

    Reasons are finer-grained than the board's: `TaskManager._resolve_parents`
    conflates a child id and an unknown filename into one `not_a_parent_task`,
    whereas a headless caller needs to tell "you named a child" from "no such
    task" from "that id matches two files".
    """

    moved: str | None = None
    col_id: str | None = None
    board_idx: int | None = None
    refused: tuple[tuple[str, str], ...] = ()

    @property
    def ok(self) -> bool:
        return not self.refused


def _has_record_breaking(value: str) -> bool:
    return any(ch in value for ch in _RECORD_BREAKING)


# --- Path resolution ---------------------------------------------------------

def tasks_dir(root, task_dir: str = DEFAULT_TASK_DIR) -> Path:
    """`<root>/<task_dir>`, proven to stay inside `root`.

    Three checks, cheapest first. The third is deliberately resolve-based rather
    than lexical-only, and must keep passing for the **branch-mode** layout,
    where `aitasks/` is a symlink to `.aitask-data/aitasks` — that target still
    resolves beneath `root`, so production passes. Do not "fix" a failure here
    by dropping the check.

    Raises `UnsafeTaskDirError`; does NOT check existence (see `_require_tree`).
    """
    root_path = Path(root)
    if not task_dir or not str(task_dir).strip():
        raise UnsafeTaskDirError("task_dir must be a non-empty relative path")

    candidate = Path(task_dir)
    # `.drive`/`.root` also catch Windows drive- and UNC-relative forms, which
    # `is_absolute()` alone reports as False on POSIX.
    if candidate.is_absolute() or candidate.drive or candidate.root:
        raise UnsafeTaskDirError(
            f"task_dir must be relative to the project root, got {task_dir!r}")
    if ".." in candidate.parts:
        raise UnsafeTaskDirError(
            f"task_dir must not traverse outside the project root, got {task_dir!r}")

    composed = root_path / candidate
    try:
        resolved_root = root_path.resolve()
        resolved = composed.resolve()
    except OSError as exc:  # unreadable/looping symlink on the way down
        raise UnsafeTaskDirError(f"task_dir could not be resolved: {exc}") from exc
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise UnsafeTaskDirError(
            f"task_dir {task_dir!r} resolves outside the project root")
    return composed


def board_config_path(root, task_dir: str = DEFAULT_TASK_DIR) -> Path:
    """Path to this project's `board_config.json`."""
    return tasks_dir(root, task_dir) / "metadata" / _BOARD_CONFIG_NAME


def _require_tree(root, task_dir: str) -> Path:
    """`tasks_dir` plus an existence assertion (fail loud, never degrade)."""
    path = tasks_dir(root, task_dir)
    if not path.is_dir():
        raise UnsupportedLayoutError(
            f"no task directory at {path} — this seam supports the standard "
            f"'<root>/{DEFAULT_TASK_DIR}' layout unless task_dir is given")
    return path


# --- Readers -----------------------------------------------------------------

def column_records_at(config_path, *, include_unordered: bool = False):
    """Configured columns, in board order, read from an explicit config path.

    Preserves three behaviours of the reader this replaces:

    * `.get(key, default)` rather than `or default` — a board deliberately
      configured with **no** columns must stay empty, exactly as
      `TaskManager.load_metadata` leaves it. Falling back on a falsy-but-present
      `[]` would invent the stock board the user never sees.
    * a `column_order` entry with no matching `columns` definition is dropped,
      because the board's renderer skips it too.
    * a configured id carrying `|`, CR or LF is fatal.

    Unlike the board, this never writes the config file when it is absent.

    `include_unordered` prepends the synthetic row **unconditionally** — it is
    the *validation vocabulary* (which ids may be moved to). That differs on
    purpose from `aitask_work_report_gather.sh --list-columns`, which prepends
    only when a task actually sits there because it is describing a *rendering*.
    """
    config = load_layered_config(
        str(config_path),
        defaults={"columns": DEFAULT_COLUMNS, "column_order": DEFAULT_ORDER},
    )
    columns = config.get("columns", DEFAULT_COLUMNS)
    order = config.get("column_order", DEFAULT_ORDER)

    defined: dict[str, ColumnRecord] = {}
    for entry in columns:
        if isinstance(entry, dict) and isinstance(entry.get("id"), str):
            cid = entry["id"]
            color = entry.get("color")
            defined[cid] = ColumnRecord(
                id=cid,
                title=str(entry.get("title", cid)),
                color=str(color) if isinstance(color, str) else None,
            )

    records = [defined[cid] for cid in order
               if isinstance(cid, str) and cid in defined]
    for rec in records:
        if _has_record_breaking(rec.id):
            raise ColumnIdError(
                f"{_BOARD_CONFIG_NAME}: column id {rec.id!r} contains '|', CR "
                "or LF, which cannot round-trip through the report protocol")

    if include_unordered:
        records.insert(0, ColumnRecord(UNORDERED_ID, UNORDERED_TITLE,
                                       UNORDERED_COLOR))
    return records


def load_columns_at(config_path):
    """`(configured ids in board order, {col_id: title})` from a config path.

    Note the asymmetry, preserved verbatim from the reader this replaces: the
    id list holds only *configured* columns, while the title map additionally
    carries `unordered`. That is what makes `col_id in titles` the single
    membership test for "is this a legal move target".
    """
    records = column_records_at(config_path)
    titles = {rec.id: rec.title for rec in records}
    titles[UNORDERED_ID] = UNORDERED_TITLE
    return [rec.id for rec in records], titles


def column_records(root, *, task_dir: str = DEFAULT_TASK_DIR,
                   include_unordered: bool = False):
    """Root-scoped :func:`column_records_at`."""
    _require_tree(root, task_dir)
    return column_records_at(board_config_path(root, task_dir),
                             include_unordered=include_unordered)


def load_columns(root, *, task_dir: str = DEFAULT_TASK_DIR):
    """Root-scoped :func:`load_columns_at`."""
    _require_tree(root, task_dir)
    return load_columns_at(board_config_path(root, task_dir))


# --- Task-file scanning ------------------------------------------------------

def _eligible(metadata) -> bool:
    """Board parity: is this file a card the board actually renders?

    Mirrors `TaskManager._is_phantom_stub` (aitask_board.py:1097) and the
    identical probe in `work_report_gather.scan_tasks`. An unparseable file
    lands here too, because `Task.load()` swallows the failure and leaves the
    metadata empty.

    This matters for index arithmetic, not just tidiness: an invisible file
    carrying the destination `boardcol` and a large `boardidx` would inflate the
    computed maximum, and the seam would append past a card the board does not
    draw.
    """
    return bool(metadata) and not set(metadata.keys()) <= set(BOARD_KEYS)


def _parse_task(path: Path):
    """`(metadata, body, key_order)` for an eligible task file, else `None`."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        parsed = parse_frontmatter(raw)
    except Exception:
        # Board parity: a malformed top-level file is simply absent from the
        # board. Letting the YAML error escape would abort the whole scan.
        return None
    if not parsed or not _eligible(parsed[0]):
        return None
    return parsed


def _column_of(metadata) -> str:
    """The column a task renders in. Missing `boardcol` reads as `unordered`."""
    raw = metadata.get("boardcol", UNORDERED_ID)
    # A non-string boardcol matches no column on the board either.
    return raw if isinstance(raw, str) else ""


def column_indices(root, col_id: str, exclude: str = "", *,
                   task_dir: str = DEFAULT_TASK_DIR) -> list[int]:
    """Normalized `boardidx` values of `col_id`, excluding one task by filename.

    The exclusion is load-bearing: an append that counted the mover would return
    `self + STEP` for a card already holding the column maximum, and the card
    would not actually move.
    """
    tree = _require_tree(root, task_dir)
    indices: list[int] = []
    for path in sorted(tree.glob("t*.md")):
        if path.name == exclude:
            continue
        parsed = _parse_task(path)
        if parsed is None:
            continue
        metadata = parsed[0]
        if _column_of(metadata) != col_id:
            continue
        indices.append(normalize_board_idx(metadata.get("boardidx", 0)))
    return indices


# --- Task resolution ---------------------------------------------------------

def _resolve_task(tree: Path, task_id: str):
    """`(path, None)` for a resolvable parent task, else `(None, reason)`.

    The one resolution rule, shared by :func:`task_column` and
    :func:`move_task_to_column` so a caller cannot get two different answers
    about the same id. Every refusal happens **before** any filesystem access
    except the final glob, and the glob is only reached by an id already proven
    to be digits — which is what makes shell/glob metacharacters inert. Do not
    replace this with quoting.
    """
    if not isinstance(task_id, str) or not _PARENT_ID_RE.match(task_id):
        if isinstance(task_id, str) and _CHILD_ID_RE.match(task_id):
            # Children are not board cards; the board early-returns on them.
            return None, "not_a_parent_task"
        return None, "malformed_task_id"

    matches = sorted(tree.glob(f"t{task_id}_*.md"))
    if not matches:
        return None, "not_found"
    if len(matches) > 1:
        # Genuinely undecidable. `aitask_query_files.sh cmd_resolve` emits a
        # multi-line TASK_FILE: here instead — a bug to avoid, not a precedent.
        return None, "ambiguous_task_id"
    return matches[0], None


def task_column(root, task_id: str, *, task_dir: str = DEFAULT_TASK_DIR):
    """Which column `task_id` currently sits in."""
    try:
        tree = _require_tree(root, task_dir)
    except BoardColumnsError as exc:
        return ColumnQuery(refused=((str(task_id), exc.reason),))

    path, reason = _resolve_task(tree, task_id)
    if reason:
        return ColumnQuery(refused=((str(task_id), reason),))

    parsed = _parse_task(path)
    if parsed is None:
        # Present but not a card the board draws — same class as "not found"
        # from the caller's point of view, and it must not be movable either.
        return ColumnQuery(refused=((str(task_id), "not_found"),))
    return ColumnQuery(col_id=_column_of(parsed[0]), filename=path.name)


# --- Writer ------------------------------------------------------------------

def _assert_same_file(path: str, st_before) -> None:
    """Raise `OSError` unless `path` is still the file we parsed.

    `atomic_write.commit` is an unconditional `os.replace`, so without this a
    task deleted or archived after parsing would be **recreated**. Best-effort
    only — see the module docstring's honest statement of the residual race.
    """
    st_now = os.stat(path)  # FileNotFoundError when it was deleted
    if (st_now.st_dev, st_now.st_ino) != (st_before.st_dev, st_before.st_ino):
        raise FileNotFoundError(path)


def move_task_to_column(root, task_id: str, col_id: str, *,
                        task_dir: str = DEFAULT_TASK_DIR) -> MoveOutcome:
    """Move a parent task to the bottom of `col_id`.

    Writes **only** `boardcol` and `boardidx`. Both are in `BOARD_LAYOUT_KEYS`,
    so this is a *layout* write: `updated_at` is deliberately NOT stamped and
    merge conflicts on these keys resolve silently local-wins.
    """
    task_id = str(task_id)
    try:
        tree = _require_tree(root, task_dir)
        _, titles = load_columns_at(board_config_path(root, task_dir))
    except BoardColumnsError as exc:
        return MoveOutcome(refused=((task_id, exc.reason),))

    # One membership test: `titles` already carries the synthetic `unordered`.
    if col_id not in titles:
        return MoveOutcome(refused=((task_id, "unknown_column"),))

    path, reason = _resolve_task(tree, task_id)
    if reason:
        return MoveOutcome(refused=((task_id, reason),))

    parsed = _parse_task(path)
    if parsed is None:
        return MoveOutcome(refused=((task_id, "not_found"),))
    metadata, body, key_order = parsed

    board_idx = index_for_append(
        column_indices(root, col_id, exclude=path.name, task_dir=task_dir))
    metadata["boardcol"] = col_id
    metadata["boardidx"] = board_idx
    text = serialize_frontmatter(metadata, body, key_order)

    resolved = os.path.realpath(str(path))
    try:
        st_before = os.stat(resolved)
    except OSError:
        return MoveOutcome(refused=((task_id, "vanished"),))

    tmp = _atomic_prepare(resolved, lambda fh: fh.write(text))
    try:
        _assert_same_file(resolved, st_before)
        _atomic_commit(tmp, resolved)
    except OSError:
        _atomic_discard(tmp)
        return MoveOutcome(refused=((task_id, "vanished"),))

    return MoveOutcome(moved=path.name, col_id=col_id, board_idx=board_idx)


# --- CLI ---------------------------------------------------------------------
#
# Driven by aitask_board_column.sh. The protocol is line-oriented `KEY:value`
# with `|`-separated fields, matching the work-report gatherer's shape so a
# caller parses both the same way.
#
# EXIT_REFUSED is distinct from EXIT_USAGE so a caller can tell "you asked for
# something impossible" from "you called me wrong".

EXIT_REFUSED = 1
EXIT_USAGE = 2


def _line_safe(value: str) -> str:
    """Sanitize the **last** field of a record: CR/LF only.

    A `|` is harmless here and must be preserved — column *titles* legitimately
    contain one, and putting the title last is exactly what buys that. Mirrors
    `work_report_gather._free_text`, which lets `|` survive for the same reason.
    CR/LF would break the line protocol itself, so they go.
    """
    return value.replace("\r", " ").replace("\n", " ")


def _field_safe(value: str) -> str:
    """Sanitize a **middle** field: `|` as well as CR/LF.

    Sanitizing happens **here, at the write site**, because a delimited encoding
    is undecidable on read: once a stray `|` is in the stream, no reader can
    tell it from a separator. Colour is cosmetic, so a bad value degrades
    rather than failing the run — a bad *id* stays fatal (`ColumnIdError`).
    """
    out = _line_safe(value)
    return out.replace("|", "")


def _emit_refusal(refused) -> int:
    for _task, reason in refused:
        print(f"ERROR:{reason}")
    return EXIT_REFUSED


def main(argv=None) -> int:
    import argparse  # local: keeps the library-import path light for the TUIs

    parser = argparse.ArgumentParser(
        prog="aitask_board_column.sh",
        description="Headless board-column reader/writer (t1377_1).")
    parser.add_argument("command",
                        choices=("list-columns", "current-column", "move"))
    parser.add_argument("--root", required=True,
                        help="project root that owns the task tree")
    parser.add_argument("--task-dir", default=DEFAULT_TASK_DIR,
                        help=f"task directory relative to --root "
                             f"(default: {DEFAULT_TASK_DIR})")
    parser.add_argument("--task", help="parent task id (digits only)")
    parser.add_argument("--column", help="destination column id")
    parser.add_argument("--include-unordered", action="store_true",
                        help="also list the synthetic 'unordered' column")
    args = parser.parse_args(argv)

    try:
        if args.command == "list-columns":
            for rec in column_records(args.root, task_dir=args.task_dir,
                                      include_unordered=args.include_unordered):
                # Title LAST: titles may legitimately contain '|', so only the
                # final field can absorb one. Split on the first two separators.
                print(f"COLUMN:{rec.id}|{_field_safe(rec.color or '')}"
                      f"|{_line_safe(rec.title)}")
            return 0

        if args.command == "current-column":
            # `is None` (flag omitted) is a USAGE error; an empty value is a
            # malformed *id*, which the seam names. Collapsing the two would
            # report `--task ''` as "you forgot --task".
            if args.task is None:
                parser.error("current-column requires --task")
            query = task_column(args.root, args.task, task_dir=args.task_dir)
            if not query.ok:
                return _emit_refusal(query.refused)
            print(f"CURRENT:{args.task}|{query.col_id}")
            return 0

        if args.task is None or args.column is None:
            parser.error("move requires --task and --column")
        outcome = move_task_to_column(args.root, args.task, args.column,
                                      task_dir=args.task_dir)
        if not outcome.ok:
            return _emit_refusal(outcome.refused)
        print(f"MOVED:{outcome.moved}|{outcome.col_id}|{outcome.board_idx}")
        return 0
    except BoardColumnsError as exc:
        # Readers raise where the outcome-returning verbs refuse; both surface
        # as one ERROR: line so a caller has a single thing to parse.
        print(f"ERROR:{exc.reason}")
        print(f"board_columns: {exc}", file=__import__("sys").stderr)
        return EXIT_REFUSED


if __name__ == "__main__":
    import sys as _sys

    _sys.exit(main())
