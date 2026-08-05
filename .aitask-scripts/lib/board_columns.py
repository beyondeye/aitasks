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
import json
import os
import re
from pathlib import Path

from atomic_write import commit as _atomic_commit
from atomic_write import discard as _atomic_discard
from atomic_write import prepare as _atomic_prepare
from board_ordering import index_for_append
from config_utils import load_layered_config, save_project_config, split_config
from record_protocol import (
    has_record_breaking,
    sanitize_last_field,
    sanitize_middle_field,
)
from task_yaml import (
    BOARD_KEYS,
    normalize_board_idx,
    parse_frontmatter,
    serialize_frontmatter,
)

__all__ = [
    "DEFAULT_COLUMNS", "DEFAULT_ORDER", "DEFAULT_TASK_DIR",
    "UNORDERED_ID", "UNORDERED_TITLE", "UNORDERED_COLOR",
    "PALETTE_COLORS", "PROJECT_KEYS", "USER_KEYS",
    "BoardColumnsError", "ColumnIdError", "UnsafeTaskDirError",
    "UnsupportedLayoutError",
    "ColumnRecord", "ColumnQuery", "MoveOutcome", "CreateOutcome",
    "tasks_dir", "board_config_path",
    "column_records", "column_records_at", "load_columns", "load_columns_at",
    "project_columns_at",
    "column_indices", "task_column", "move_task_to_column",
    "generate_col_id", "next_palette_color", "create_column",
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

#: The board's colour palette, moved here from `ColumnEditScreen` so the board
#: TUI and the headless writer offer the same eight choices (t1377_3). The board
#: imports it back; it stays the semantic owner.
PALETTE_COLORS = [
    ("#FF5555", "Red"),
    ("#FFB86C", "Orange"),
    ("#F1FA8C", "Yellow"),
    ("#50FA7B", "Green"),
    ("#8BE9FD", "Cyan"),
    ("#BD93F9", "Purple"),
    ("#FF79C6", "Pink"),
    ("#6272A4", "Gray"),
]

#: How `board_config.json` splits across its two layers. Single source of truth
#: (t1377_3): these were duplicated byte-for-byte in `board/aitask_board.py` and
#: `settings/settings_app.py` (as `_BOARD_PROJECT_KEYS` / `_BOARD_USER_KEYS`),
#: and both now import from here.
#:
#: NOT related to `stats/stats_config.py`'s `_USER_KEYS`, which is a *different*
#: key set for a different config file and merely shares the name — do not
#: "unify" them.
PROJECT_KEYS = {"columns", "column_order"}
USER_KEYS = {"settings"}

#: The only task-directory layout this framework ships. See the module docstring
#: for why it is a parameter rather than an ambient `TASK_DIR` read.
DEFAULT_TASK_DIR = "aitasks"

_BOARD_CONFIG_NAME = "board_config.json"

# A task id is untrusted input that reaches a glob, so it is matched, never
# quoted. `^\d+$` is what makes `*`, `1*`, `../x` and `t42` inert.
_PARENT_ID_RE = re.compile(r"^\d+$")
_CHILD_ID_RE = re.compile(r"^\d+_\d+$")

# A colour supplied to `create_column` is validated, NOT sanitized (t1377_3),
# because it cannot round-trip the way a title can:
#
#   * it is the MIDDLE field of a `COLUMN:` record, so a stored `|` is silently
#     stripped on emit — undecidable for the reader, hence prevented on write;
#   * it is interpolated as a rich-markup *tag* (`[{color}]██[/]`) by
#     `monitor_shared._ColumnRow` (guarded) and by the board's
#     `ColumnSelectItem` / `ColorSwatch` (NOT guarded), where a `]` closes the
#     tag early and `[/]` raises `MarkupError` inside a render path.
#
# Deliberately regex-based rather than `rich.Color.parse`: this module imports
# only stdlib and lib/ siblings, and rich would reject this module's own
# `UNORDERED_COLOR = "gray"` (rich has grey0..grey100, no bare gray).
#
# READERS STAY TOLERANT. `column_records_at` still returns whatever a
# hand-edited config holds, and `_safe_column_color` degrades it at render time.
# Writers refuse, readers degrade — both stances are pinned by tests.
_COLOR_RE = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$"
                       r"|^[a-z][a-z0-9_]{0,31}$")


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


class EmptyTitleError(BoardColumnsError):
    """A column title was blank or whitespace-only."""

    reason = "empty_title"


class InvalidColorError(BoardColumnsError):
    """A supplied colour is not a hex triple/sextet or a style-name token."""

    reason = "invalid_color"


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


@dataclasses.dataclass(frozen=True)
class CreateOutcome:
    """Outcome of a single column creation (t1377_3).

    Mirrors :class:`MoveOutcome`: a rich return naming what was refused and why,
    never a bare bool. `refused` non-empty always means NOTHING was written. The
    refusal key is the *title* the caller supplied, since no id exists yet.

    `color` is `None` when the caller explicitly asked for a colourless column
    (`color=""`), which is distinct from omitting it — see :func:`create_column`.
    """

    col_id: str | None = None
    title: str | None = None
    color: str | None = None
    refused: tuple[tuple[str, str], ...] = ()

    @property
    def ok(self) -> bool:
        return not self.refused


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
        if has_record_breaking(rec.id):
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


def _read_project_config(config_path) -> dict:
    """The PROJECT layer's raw dict, or `{}` when absent/unreadable.

    Total by contract — see :func:`project_columns_at` for why the callers need
    that.
    """
    try:
        with open(config_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def project_columns_at(config_path) -> tuple[list[dict], list[str]]:
    """Raw `(columns, column_order)` from the PROJECT layer alone (t1377_3).

    Deliberately **not** `load_layered_config`: this is the input to the board's
    save-time reconciliation, which must compare against what is actually in the
    tracked file. Merging `board_config.local.json` back in would reintroduce the
    user layer the project/local split exists to keep out, and could promote a
    user-local `columns` override into the tracked file on the next save.

    Entries are returned as **raw dicts**, not `ColumnRecord`s, because the
    consumer merges them verbatim — normalizing here would silently rewrite a
    hand-authored entry on a path whose whole job is to preserve one.

    Total by contract: a missing or unparseable file yields `([], [])` rather
    than raising. This runs inside a write path, where losing the *merge* (the
    pre-existing behaviour) is strictly safer than losing the *save*.
    """
    data = _read_project_config(config_path)
    columns = data.get("columns")
    order = data.get("column_order")
    return (columns if isinstance(columns, list) else [],
            order if isinstance(order, list) else [])


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


def generate_col_id(title: str, existing_ids) -> str:
    """A unique, protocol-safe column id derived from a display title.

    Lifted verbatim from `ColumnEditScreen._generate_col_id` (t1377_3) so the
    board dialog and the headless writer cannot drift; the board now delegates
    here. Its quirks are preserved deliberately, including that the uniquifying
    `_2` suffix is appended AFTER the 20-character truncation (so a collided id
    may exceed 20).

    The `[^a-z0-9]+ -> _` step is load-bearing beyond cosmetics: it makes it
    impossible for this function to emit `|`, CR or LF, which is exactly what
    `record_protocol.has_record_breaking` treats as fatal for a `COLUMN:` record.
    Do not relax it.
    """
    slug = re.sub(r'[^\x00-\x7F]+', '', title)  # strip non-ASCII (emojis)
    slug = slug.strip().lower()
    slug = re.sub(r'[^a-z0-9]+', '_', slug)  # replace non-alnum with _
    slug = slug.strip('_')  # trim leading/trailing underscores
    slug = slug[:20]  # limit length
    if not slug:
        slug = "column"
    base = slug
    counter = 2
    while slug in existing_ids:
        slug = f"{base}_{counter}"
        counter += 1
    return slug


def next_palette_color(existing_colors) -> str:
    """The first palette colour not already in use, else one chosen by count.

    Pure and deterministic, so a caller that creates several columns gets
    visually distinct ones without any UI. Once all eight are taken the fallback
    indexes by how many columns exist, which simply cycles the palette.
    """
    used = {c for c in existing_colors if isinstance(c, str)}
    for hex_value, _label in PALETTE_COLORS:
        if hex_value not in used:
            return hex_value
    return PALETTE_COLORS[len(list(existing_colors)) % len(PALETTE_COLORS)][0]


def _validate_color(color):
    """Normalize and validate a caller-supplied colour.

    Three-way, mirroring the `--task` precedent in `main()` (`is None` != `""`):
    `None` means "pick one for me" and returns `None` for the caller to fill;
    `""` means "explicitly colourless"; anything else is validated.

    Raises `InvalidColorError`. See `_COLOR_RE` for why this validates rather
    than sanitizes, and why it is not `rich.Color.parse`.
    """
    if color is None:
        return None
    text = str(color).strip()
    if not text:
        return ""
    if not _COLOR_RE.match(text):
        raise InvalidColorError(
            f"colour {color!r} is neither a hex value (#abc / #aabbcc) nor a "
            f"lowercase style-name token")
    return text


def create_column(root, title: str, color=None, *,
                  task_dir: str = DEFAULT_TASK_DIR) -> CreateOutcome:
    """Append a new column to this project's `board_config.json` (t1377_3).

    The first write to a *tracked project config* from outside `ait board`, so
    the layering is the load-bearing part. `load_layered_config` returns the
    MERGED dict (defaults <- project <- local), which invites three mistakes:

    * writing that merged dict back **leaks user-level keys into the tracked
      file** — `settings`, and in fact any other key the local layer holds;
    * mirroring `TaskManager.save_metadata`, which writes BOTH layers,
      **clobbers `board_config.local.json`** (collapsed columns, refresh interval);
    * a user-local `columns` override is **promoted** into the tracked file.

    So the merged view is used only to *decide* (slug collisions and the palette
    must reflect what the user actually sees), while the **write** reads, mutates
    and stores the project layer itself. Nothing from the local layer is in the
    dict that reaches disk, which makes the first mistake structurally impossible
    rather than guarded by a key allowlist; and the local file is never opened
    for writing at all, not even to rewrite it identically.

    The third point is board parity (`save_metadata` promotes the same way) and
    is documented rather than fixed here — but note it is narrower now: only a
    local `columns` override changes what a *reader* sees, and this writer never
    copies it across.

    `title` is stored verbatim: `|` is legal in it because the emitter puts the
    title LAST precisely so it survives. `color` is validated instead — it cannot
    round-trip (see `_COLOR_RE`). Omitting it auto-assigns from the palette.

    Concurrency: `save_project_config` is atomic for readers but takes no lock.
    A board that loaded earlier reconciles this addition at its next save
    (`TaskManager._reconcile_external_columns`); two *simultaneous* writers still
    resolve last-writer-wins.
    """
    title = "" if title is None else str(title)
    try:
        _require_tree(root, task_dir)
        color = _validate_color(color)
        if not title.strip():
            raise EmptyTitleError("a column title cannot be blank")
        config_path = board_config_path(root, task_dir)
        # Raises ColumnIdError if an id already in the file breaks the protocol —
        # surfaced rather than allowed to escape a writer.
        column_records_at(config_path)
    except BoardColumnsError as exc:
        return CreateOutcome(title=title, refused=((title, exc.reason),))

    # DECIDE from the merged view: the id must not collide with a column the
    # user can see, and the palette should avoid a colour already on screen.
    merged = load_layered_config(
        str(config_path),
        defaults={"columns": DEFAULT_COLUMNS, "column_order": DEFAULT_ORDER},
    )
    visible = [c for c in merged.get("columns", DEFAULT_COLUMNS)
               if isinstance(c, dict)]
    col_id = generate_col_id(title, [c.get("id") for c in visible])
    if color is None:
        color = next_palette_color([c.get("color") for c in visible])

    entry = {"id": col_id, "title": title}
    if color:
        entry["color"] = color

    # WRITE the project layer only. Reading it back raw (rather than splitting
    # the merged dict) is what preserves every unrelated PROJECT key verbatim
    # while making it impossible for any LOCAL key to ride along.
    project = _read_project_config(config_path)
    columns = project.get("columns")
    order = project.get("column_order")
    if not isinstance(columns, list):
        columns = [dict(c) for c in DEFAULT_COLUMNS]
    if not isinstance(order, list):
        order = list(DEFAULT_ORDER)
    project["columns"] = list(columns) + [entry]
    project["column_order"] = list(order) + [col_id]
    save_project_config(str(config_path), project)

    return CreateOutcome(col_id=col_id, title=title, color=color or None)


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


# The field sanitizers (`sanitize_last_field` / `sanitize_middle_field`) and the
# record-breaking predicate live in lib/record_protocol.py (t1433). This module
# used to carry private copies under the names `_line_safe` / `_field_safe` /
# `_has_record_breaking`; the reasoning they documented — write-site
# sanitization, and why a `|` must survive the LAST field — moved with them.
# What stays here is this module's own *reaction*: a bad colour degrades, a bad
# id is fatal (`ColumnIdError`), and the `board_columns:` stderr prefix is ours.


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
                        choices=("list-columns", "current-column", "move",
                                 "create"))
    parser.add_argument("--root", required=True,
                        help="project root that owns the task tree")
    parser.add_argument("--task-dir", default=DEFAULT_TASK_DIR,
                        help=f"task directory relative to --root "
                             f"(default: {DEFAULT_TASK_DIR})")
    parser.add_argument("--task", help="parent task id (digits only)")
    parser.add_argument("--column", help="destination column id")
    parser.add_argument("--include-unordered", action="store_true",
                        help="also list the synthetic 'unordered' column")
    parser.add_argument("--title", help="display title for a new column")
    parser.add_argument("--color",
                        help="colour for a new column: #abc / #aabbcc or a "
                             "lowercase style name (default: next unused "
                             "palette entry; '' for none)")
    args = parser.parse_args(argv)

    try:
        if args.command == "list-columns":
            for rec in column_records(args.root, task_dir=args.task_dir,
                                      include_unordered=args.include_unordered):
                # Title LAST: titles may legitimately contain '|', so only the
                # final field can absorb one. Split on the first two separators.
                print(f"COLUMN:{rec.id}|{sanitize_middle_field(rec.color or '')}"
                      f"|{sanitize_last_field(rec.title)}")
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

        if args.command == "create":
            # As for `--task`: an omitted flag is a USAGE error, an empty value
            # is a malformed *title*, which the seam names.
            if args.title is None:
                parser.error("create requires --title")
            outcome = create_column(args.root, args.title, args.color,
                                    task_dir=args.task_dir)
            if not outcome.ok:
                return _emit_refusal(outcome.refused)
            # Title LAST — it may legitimately contain '|'.
            print(f"CREATED:{outcome.col_id}"
                  f"|{sanitize_middle_field(outcome.color or '')}"
                  f"|{sanitize_last_field(outcome.title)}")
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
