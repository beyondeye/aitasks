"""`TaskManager` — the board's task/column data layer (t1794_4).

Moved out of `aitask_board.py` together with the helpers it calls that the
board also uses (`_task_git_cmd`, the topic-grouping build, the merge error
type), which the board re-exports. The one non-verbatim change: the manager
no longer reads the board's task-dir constants at call time. Its paths are
REQUIRED keyword arguments (t1794, C2) —
`TaskManager(*, tasks_dir, metadata_file, gates_registry_file, on_warning=None)`
— and `aitask_board.make_task_manager()` is the board's binding of its own
constants.

Contract (t1794, C1): flat imports only, never `aitask_board`. A stub of a
name the manager calls through this module's namespace (`save_local_config`,
`save_project_config`, `project_columns_at`, `gate_ledger`, …) must patch it
HERE, reachable as `ab.board_task_manager` — a patch on the board's name is
not seen by the manager.
"""

from __future__ import annotations

import glob
import re
import subprocess
from pathlib import Path

import board_ordering
import dep_resolution
import gate_ledger
from archive_iter import find_archived_markdown_by_id
from board_columns import (
    DEFAULT_COLUMNS, DEFAULT_ORDER, UNORDERED_ID, project_columns_at,
)
from board_columns import PROJECT_KEYS as _PROJECT_KEYS
from board_columns import USER_KEYS as _USER_KEYS
from board_groups import (
    column_remap, group_key, remap_group_keys, task_group_slug,
)
from board_widgets import TaskCard, _plan_approved_marker
from config_utils import (
    load_layered_config, local_path_for, save_local_config,
    save_project_config, split_config,
)
from metadata_commit import commit_metadata
from task_yaml import BOARD_KEYS, normalize_board_idx
from topic_semantics import _task_id_sort_key, task_own_id, topic_key

from board_task_model import (
    MERGE_METADATA_KEY, MERGE_METADATA_LOCAL_KEY, MERGE_UNVERIFIABLE_KEY,
    MergeResult, MoveResult, Task,
)
from board_workflow_phase import (
    GateStateResult, InFlightItem, _failed_active_gates, _inflight_lane,
    _inflight_next_action, _pending_human_gates, _resolve_plan_path_for_task,
    derive_workflow_phase,
)


# "No digest resolved yet this refresh" — distinct from a resolved ``None``,
# which is the real answer "freshness is unverifiable" (t1416).
_DIGEST_UNSET = object()


def _task_git_cmd() -> list[str]:
    """Return git command prefix for task data operations.
    In branch mode: ["git", "-C", ".aitask-data"]
    In legacy mode: ["git"]

    The data worktree is resolved against the cwd at CALL time (t1794_4, C2):
    no board sibling binds a task-data path at import. The board keeps its own
    `DATA_WORKTREE` constant for `KanbanApp`.
    """
    data_worktree = Path(".aitask-data")
    if data_worktree.exists() and (data_worktree / ".git").exists():
        return ["git", "-C", str(data_worktree)]
    return ["git"]


# --- Topic grouping (group-by-anchor) ---
# Pure, import-testable core for the board's by-topic view. No widget
# dependencies — operates on Task objects via their filename + metadata, so it
# is unit-tested in isolation (tests/test_board_topic_group.py).

TOPIC_SORT_MODES = ("recency", "topic_id", "size", "alphabetical")


# (mode, human label) — drives the picker rows and the placeholder hint.
TOPIC_SORT_MODE_LABELS = [
    ("recency", "Recency (newest first)"),
    ("topic_id", "Topic id (newest first)"),
    ("size", "Size (largest first)"),
    ("alphabetical", "Alphabetical"),
]


def _topic_lane_label(key, members, tasks_by_id):
    """Lane label: the root task's title when the root is present, else the
    first member's title — the id ``key`` stays the stable lane key either way."""
    root = tasks_by_id.get(key)
    source = root if root is not None else (members[0] if members else None)
    if source is not None:
        _, name = TaskCard._parse_filename(source.filename)
        if name:
            return f"t{key} {name}"
    return f"t{key}"


def _task_recency(task):
    """Recency sort key for a task: the newest of updated_at / created_at, or
    '' when neither is set. Timestamps are 'YYYY-MM-DD HH:MM' strings, so a
    lexicographic comparison is chronological."""
    return str(task.metadata.get("updated_at")
               or task.metadata.get("created_at") or "")


def _lane_recency(members):
    """Recency of a lane = the newest recency among its members."""
    return max((_task_recency(m) for m in members), default="")


def _topic_id_sortkey(key):
    """Sortable key for a topic id ('1016', '130_2'): numeric segments compared
    as ints (so 't9' sorts before 't10') and negated for descending order.
    Non-numeric keys sort last, stringwise. Used by the 'topic_id' sort mode."""
    parts = str(key).split("_")
    try:
        return (0, tuple(-int(p) for p in parts))
    except ValueError:
        return (1, str(key))


def _sort_topic_lanes(lanes, sort_mode):
    """Sort (key, label, members) lane triples in place per mode. 'Ungrouped' is
    appended by the caller and is never in `lanes`, so it stays pinned last in
    every mode. Python's sort is stable → ties keep first-seen order."""
    if sort_mode == "topic_id":
        lanes.sort(key=lambda lane: _topic_id_sortkey(lane[0]))
    elif sort_mode == "size":
        lanes.sort(key=lambda lane: len(lane[2]), reverse=True)
    elif sort_mode == "alphabetical":
        lanes.sort(key=lambda lane: lane[1].casefold())
    else:  # "recency" (default)
        lanes.sort(key=lambda lane: _lane_recency(lane[2]), reverse=True)


def _topic_membership_signature(tasks):
    """Ordered signature of the inputs that affect topic *bucketing* (not sort
    ordering): each task's filename + anchor, in input order. NOT sorted —
    _build_topic_lanes preserves first-seen order for lane ties and Ungrouped
    members, so the signature must change when the input order changes.
    Sort-mode inputs (updated_at, size, label) are re-read live at sort time and
    are intentionally absent here."""
    return tuple(
        (t.filename, str(t.metadata.get("anchor") or "")) for t in tasks)


def _build_topic_lanes(tasks):
    """Bucket tasks into topic lanes. Returns ``(topic_lanes, ungrouped)`` where
    ``topic_lanes`` is an unsorted list of ``(key, label, members)`` triples in
    first-seen order and ``ungrouped`` is the collapsed singleton members. This
    is the sort-independent, cacheable heart of the by-topic view."""
    tasks_by_id = {}
    for task in tasks:
        own = task_own_id(task)
        if own:
            tasks_by_id.setdefault(own, task)

    buckets = {}
    order = []
    for task in tasks:
        key = topic_key(task, tasks_by_id)
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(task)

    topic_lanes = []   # (key, label, members)
    ungrouped = []
    for key in order:
        members = buckets[key]
        if len(members) >= 2:
            topic_lanes.append(
                (key, _topic_lane_label(key, members, tasks_by_id), members))
        else:
            ungrouped.extend(members)
    return topic_lanes, ungrouped


def _assemble_topic_lanes(topic_lanes, ungrouped, sort_mode):
    """Order the (possibly cached) lane triples per ``sort_mode`` and flatten to
    ``(label, members)`` pairs, pinning 'Ungrouped' last. Copies the triple list
    so a cached build is never reordered in place."""
    if sort_mode not in TOPIC_SORT_MODES:
        sort_mode = "recency"
    ordered = list(topic_lanes)
    _sort_topic_lanes(ordered, sort_mode)
    lanes = [(label, members) for _key, label, members in ordered]
    if ungrouped:
        lanes.append(("Ungrouped", ungrouped))
    return lanes


def group_tasks_by_topic(tasks, sort_mode="recency"):
    """Bucket tasks into per-anchor topic lanes, ordered by ``sort_mode`` (one of
    ``TOPIC_SORT_MODES``; unknown → 'recency').

    Returns an ordered list of ``(label, [tasks])`` lanes. A bucket with >= 2
    members becomes its own lane; singleton buckets collapse into a trailing
    ``("Ungrouped", [...])`` lane, which is always last regardless of mode.
    Uncached pure entry point — the board renders via
    ``TaskManager.grouped_topic_lanes()``, which caches the build.
    """
    topic_lanes, ungrouped = _build_topic_lanes(tasks)
    return _assemble_topic_lanes(topic_lanes, ungrouped, sort_mode)


class MetadataWriteError(OSError):
    """A `save_metadata` write that failed, tagged with WHICH half failed.

    `save_metadata` persists PROJECT keys (`columns`/`column_order`) and USER
    keys (`settings`) to two separate files, project first, with no cross-file
    transaction. A caller recovering from a failure needs to know which half
    landed — after the project write succeeds, a column removal is already
    durable and must NOT be rolled back.

    Subclasses `OSError` so every existing `except OSError` around a save keeps
    working unchanged; `.phase` is `"project"` or `"local"`.

    Reporting the phase from the site that performs the writes is what lets
    `merge_columns` discriminate without re-reading the config from disk — which
    would add a second `project_columns_at` call site and breach the
    save-path containment guard in `tests/test_board_columns_reconcile.py`.
    """

    def __init__(self, phase: str, cause: OSError):
        super().__init__(cause.errno, cause.strerror or str(cause))
        self.phase = phase
        self.__cause__ = cause


class TaskManager:
    def __init__(self, *, tasks_dir: Path, metadata_file: Path,
                 gates_registry_file: Path, on_warning=None):
        # The resolved task-dir paths, injected (t1794_4, C2). This module never
        # resolves the task directory itself: a manager reads exactly the tree its
        # constructor names. `aitask_board.make_task_manager` passes the board's
        # own constants; tests pass a fixture tree.
        self.tasks_dir = Path(tasks_dir)
        self.metadata_file = Path(metadata_file)
        self.gates_registry_file = Path(gates_registry_file)
        # Optional sink for user-visible warnings raised outside a screen (the
        # save-time column reconciliation, t1377_3). The app passes `self.notify`;
        # tests leave it None and read `reconcile_warnings` instead.
        self._on_warning = on_warning
        # Called with (CommitResult, paths) after each board_config.json commit
        # (t1677). The app wires it to a notifier; tests leave it None or read it.
        self.on_metadata_commit = None
        self.reconcile_warnings: list[str] = []
        # Column ids this board instance has already seen. Seeded by
        # load_metadata, refreshed by save_metadata. It is what distinguishes an
        # external ADDITION from a board-side DELETION at reconcile time.
        self._known_col_ids: set[str] = set()
        # Task files that EXIST but could not be read (t1377_4). A failed load
        # leaves `metadata == {}`, which `_is_phantom_stub` drops — so such a
        # file is invisible to `task_datas` while its on-disk `boardcol` still
        # claims a column. `merge_columns` refuses to remove any column while
        # this is non-empty: it cannot prove the column is empty, and removing
        # it would strand that file on a column that no longer exists.
        # "Cannot verify" is its own state, distinct from "verified empty".
        self.unreadable_files: set[str] = set()
        self.task_datas: dict[str, Task] = {} # Filename -> Task (parents)
        self.child_task_datas: dict[str, Task] = {} # Filename -> Task (children)
        self.archived_task_cache: dict[str, Task | None] = {}
        self.columns: list[dict] = []
        self.column_order: list[str] = []
        self.modified_files: set = set()  # Relative paths of git-modified .md files
        self.lock_map: dict[str, dict] = {}  # task_id -> {locked_by, locked_at, hostname}
        # Cross-repo dependency status cache: (repo, task_id) -> status string.
        # Populated lazily during card render and cleared each full refresh so
        # the task-status probe does not fire per redraw.
        self.xdep_status_cache: dict[tuple[str, str], str] = {}
        self.gate_state_cache: dict[str, GateStateResult] = {}
        self.gate_registry_cache: dict[str, dict] | None = None
        self.gate_registry_error = ""
        # Repo-global code digest, computed at most once per refresh cycle and
        # ONLY if some task actually carries a signed gate witness (t1416).
        # Shares clear_gate_cache() with gate_state_cache deliberately: a second,
        # independent lifetime is how a digest ends up pinned for the whole
        # process, which would make a stale approval read valid until restart.
        self.gate_digest_cache: object | str | None = _DIGEST_UNSET
        # (signature, topic_lanes, ungrouped) for the by-topic build; None = cold.
        # Sort-mode switches and refocus refreshes re-sort this cached build
        # instead of re-bucketing every task. Invalidated by content signature
        # (see grouped_topic_lanes) and explicitly at the reload seams below.
        self.topic_lane_cache = None
        self.settings: dict = {}
        # Collapsed in-column task groups, keys `"<col_id>/<slug>"` (t1243_10).
        # THE in-memory truth: `KanbanApp.collapsed_groups` aliases this exact
        # object and every mounted `KanbanColumn` holds it by reference, which is
        # what lets a lifecycle op here update the board's rendering source with
        # no propagation step. `settings["collapsed_groups"]` is its persisted
        # projection, not a second owner. Created before load_metadata(), which
        # fills it.
        self.collapsed_groups: set = set()
        self._ensure_paths()
        self.load_metadata()
        self.load_tasks()

    def _reset_collapsed_groups(self, keys) -> None:
        """Replace the live set's CONTENTS. NEVER rebind the attribute.

        `KanbanApp.collapsed_groups` and every mounted `KanbanColumn` hold THIS
        exact set object (t1243_9 — that by-reference flow is what lets a
        collapse toggle recompose one column with no propagation step).
        Rebinding would leave all of them pointing at the previous object: the
        board would keep rendering the pre-change state until the next full
        `refresh_board`, and `action_toggle_group` would write into a set the
        model no longer reads. Silent, and invisible to any assertion that reads
        through the manager.

        Load, every lifecycle remap and the `merge_columns` rollback all go
        through here.
        """
        self.collapsed_groups.clear()
        self.collapsed_groups.update(keys)

    def _ensure_paths(self):
        self.tasks_dir.mkdir(exist_ok=True)
        self.metadata_file.parent.mkdir(exist_ok=True)

    def load_metadata(self):
        defaults = {
            "columns": DEFAULT_COLUMNS,
            "column_order": DEFAULT_ORDER,
            "settings": {"auto_refresh_minutes": 0},
        }
        config = load_layered_config(str(self.metadata_file), defaults=defaults)
        self.columns = config.get("columns", DEFAULT_COLUMNS)
        self.column_order = config.get("column_order", DEFAULT_ORDER)
        self.settings = config.get("settings", {"auto_refresh_minutes": 0})
        self._refresh_known_col_ids()
        self._prune_orphan_collapsed_columns()
        # The LOAD END of the collapse set (t1243_10). `remap_group_keys` with no
        # rule is pure normalization, so junk hygiene shares one implementation
        # with every lifecycle remap. `isinstance` guard for the same reason
        # `_prune_orphan_collapsed_columns` has one: a hand-edited scalar would
        # otherwise be iterated character by character.
        raw = self.settings.get("collapsed_groups")
        self._reset_collapsed_groups(
            remap_group_keys(raw) if isinstance(raw, list) else ())
        if not self.metadata_file.exists():
            # Startup first-ship, not a user gesture: create the file, commit
            # nothing. Launching the board must never produce a commit.
            self.save_metadata(commit=False)

    def _prune_orphan_collapsed_columns(self):
        """Drop `collapsed_columns` entries naming a column that no longer exists.

        The durable recovery record for a half-written merge (t1377_4): the two
        halves of `save_metadata` are separate files, and the PROJECT half
        (`columns` / `column_order`) is written first. If the USER half then
        fails, the column removal is already durable while the collapsed entry
        naming it is not yet pruned — leaving an orphan on disk. That orphan is
        self-describing, so no journal is needed: any later session converges by
        pruning it here. It also heals the identical orphan class left by
        `update_column`'s pre-t1377_4 rename path.

        In-memory only — the next natural `save_metadata()` persists it. Forcing
        a write on every board open would cost a save per launch and race
        concurrent writers for no benefit, since the in-memory value is what
        governs rendering.

        **`unordered` is whitelisted.** It is collapsible (the board calls
        `is_column_collapsed("unordered")` for its synthetic lane) but is
        deliberately absent from `columns`, so an unguarded "prune ids not in
        `columns`" would silently drop a legitimate collapse.
        """
        collapsed = self.settings.get("collapsed_columns")
        if not isinstance(collapsed, list):
            return
        live = {c["id"] for c in self.columns
                if isinstance(c, dict) and isinstance(c.get("id"), str)}
        live.update(cid for cid in self.column_order if isinstance(cid, str))
        live.add(UNORDERED_ID)
        kept = [cid for cid in collapsed if cid in live]
        if len(kept) != len(collapsed):
            self.settings["collapsed_columns"] = kept

    def _refresh_known_col_ids(self):
        """Snapshot the column ids this instance knows about (t1377_3)."""
        self._known_col_ids = {
            c["id"] for c in self.columns
            if isinstance(c, dict) and isinstance(c.get("id"), str)
        }

    def _warn_reconcile(self, message: str):
        """Record a reconciliation warning and surface it if the app wired a sink."""
        self.reconcile_warnings.append(message)
        if self._on_warning is not None:
            try:
                self._on_warning(message, severity="warning", markup=False)
            except Exception:  # noqa: BLE001 - a notify failure must not lose the save
                pass

    def _reconcile_external_columns(self):
        """Merge columns another process added since this board loaded (t1377_3).

        `load_metadata` runs exactly once, at construction, so without this the
        board would write its startup-era `self.columns` over the file and
        silently destroy a column created meanwhile through the headless writer
        (`lib/board_columns.create_column`, reached from `ait minimonitor`).

        **Called from `save_metadata` ONLY.** It must never be reached from
        `refresh_board`, the auto-refresh timer, or any render path — that is a
        hard performance constraint, enforced by an AST call-site scan in
        `tests/test_board_columns_reconcile.py`. It is affordable precisely
        because every `save_metadata` call sits behind a discrete user gesture.

        Per on-disk column id:

        =========  ==============  ================  ==============================
        on disk    known to us     in self.columns   action
        =========  ==============  ================  ==============================
        X          yes             yes               ours wins (board-side edit)
        X          yes             no                board DELETED it - leave gone
        X          no              no                external addition - merge
        X          no              yes               id collision - warn, keep ours
        =========  ==============  ================  ==============================

        This narrows the stale-reader window; it does **not** serialize writers.
        Two processes whose read-modify-write cycles interleave still lose one
        update — `save_project_config` gives reader-visible atomicity, not writer
        serialization, and no lock is taken here.
        """
        disk_cols, disk_order = project_columns_at(self.metadata_file)
        if not disk_cols:
            return
        mine = {
            c["id"]: c for c in self.columns
            if isinstance(c, dict) and isinstance(c.get("id"), str)
        }
        additions: dict[str, dict] = {}
        for entry in disk_cols:
            if not isinstance(entry, dict):
                continue
            cid = entry.get("id")
            if not isinstance(cid, str) or cid in self._known_col_ids:
                continue  # we knew it: our edit wins, our deletion sticks
            if cid in mine:
                if mine[cid] != entry:
                    self._warn_reconcile(
                        f"Column '{cid}' was created both here and by another "
                        f"process with a different definition "
                        f"({mine[cid].get('title')!r} vs {entry.get('title')!r}). "
                        f"Keeping this board's version — reconcile manually."
                    )
                continue
            additions[cid] = entry
        if not additions:
            return
        # On-disk order first, then any addition absent from column_order.
        ordered = [cid for cid in disk_order
                   if isinstance(cid, str) and cid in additions]
        ordered += [cid for cid in additions if cid not in ordered]
        for cid in ordered:
            self.columns.append(additions[cid])
            if cid not in self.column_order:
                self.column_order.append(cid)

    def _settings_for_save(self) -> dict:
        """`self.settings` with live view state materialized into persisted form.

        `collapsed_groups` is a SET in memory (shared by reference with the app
        and every KanbanColumn) and a sorted list on disk. This is the ONLY
        projection site, so no save path can persist a stale list — including a
        save issued by an unrelated caller such as `toggle_column_collapsed`.

        Sorted for byte-stability: an unordered dump would rewrite
        `board_config.local.json` with a different key order on every save. The
        key is REMOVED when the set is empty, so a board that never collapses a
        group never grows it and a collapse→expand round-trip returns the file to
        its original bytes.
        """
        if self.collapsed_groups:
            self.settings["collapsed_groups"] = sorted(self.collapsed_groups)
        else:
            self.settings.pop("collapsed_groups", None)
        return self.settings

    def _config_layers(self) -> tuple[dict, dict]:
        """`(project_data, user_data)` for the current in-memory config.

        ONE split site for both save paths, so the user-layer-only save derives
        which keys are per-user from `_USER_KEYS` exactly as `save_metadata`
        does, instead of hardcoding "settings goes local" a second time.
        """
        data = {
            "columns": self.columns,
            "column_order": self.column_order,
            "settings": self._settings_for_save(),
        }
        return split_config(data, project_keys=_PROJECT_KEYS, user_keys=_USER_KEYS)

    def _write_user_layer(self, user_data: dict) -> None:
        """Write `board_config.local.json`; tag a failure `local`.

        Writes UNCONDITIONALLY — there is no "nothing to write" short-circuit.
        A guard on an empty payload used to sit here (t1480); it could never
        fire, and it read as "the local file is written only sometimes", which
        is false.
        """
        try:
            save_local_config(str(local_path_for(str(self.metadata_file))), user_data)
        except OSError as exc:
            raise MetadataWriteError("local", exc) from exc

    def save_settings(self) -> None:
        """Persist ONLY the USER layer (`board_config.local.json`) — t1243_10.

        The runtime save path for per-user VIEW state. It deliberately does NOT
        call `_reconcile_external_columns` and does NOT write the git-tracked
        `board_config.json`: `aidocs/framework/tui_conventions.md` ("No
        auto-commit/push of project-level config from runtime TUIs") makes
        project files read-only at runtime, and reconciliation can legitimately
        change `self.columns` and raise a warning — which would turn a collapse
        keystroke into a column-config edit.

        Use this for any mutation confined to `self.settings`; use
        `save_metadata` when `columns` / `column_order` changed. The AST guard in
        `tests/test_board_columns_reconcile.py` enforces that split, because it
        is invisible at the call site.

        Error contract is `save_metadata`'s local half verbatim —
        `MetadataWriteError("local", …)`, an `OSError` subclass — so one handler
        covers both. `_refresh_known_col_ids()` is NOT called: it tracks column
        config, which this path does not touch.
        """
        _, user_data = self._config_layers()
        self._write_user_layer(user_data)

    def save_metadata(self, commit: bool = True):
        """Persist both config layers; commit the project one by default.

        `board_config.json` has no derivable task id, so `ait sync` refuses to
        attribute it and nothing else committed it — 8 of its 9 commits landed
        under unrelated tasks' messages, and a dirty copy blocks task-data sync
        outright. Every caller of this method is an explicit column gesture
        (add / rename / delete / merge / reorder), which is the user-initiated
        carve-out `aidocs/framework/tui_conventions.md` permits.

        `commit=False` is for the ONE caller that is not a gesture: the startup
        first-ship in `load_metadata`, where the file is created because it did
        not exist. That is the "first-time ship is a one-time implementation
        commit" case, and launching the board must not produce a commit.

        Settings-only writes go through `save_settings`, which touches the
        gitignored user layer only and still commits nothing.
        """
        self._reconcile_external_columns()
        project_data, user_data = self._config_layers()
        # Two files, no cross-file transaction: tag each failure with its phase so
        # a caller can tell "nothing landed" from "columns landed, settings did
        # not" without re-reading config from disk (t1377_4).
        try:
            save_project_config(str(self.metadata_file), project_data)
        except OSError as exc:
            raise MetadataWriteError("project", exc) from exc
        self._write_user_layer(user_data)
        self._refresh_known_col_ids()
        if commit:
            self._commit_metadata_file()

    def _commit_metadata_file(self):
        """Commit `board_config.json` path-scoped and report via `on_commit`.

        Synchronous rather than a `@work(thread=True)` worker: a worker would
        have to be started by the App, so each of the six column-gesture call
        sites would need to drain a queue — precisely the "a caller can forget
        it" failure that putting the commit in `save_metadata` avoids. One
        path-scoped commit of one small JSON is on par with the subprocess calls
        (`aitask_lock.sh --list`, `git status`) the refresh path already makes
        inline.

        `on_commit` keeps TaskManager Textual-free; `KanbanApp` wires it once.
        """
        paths = [str(self.metadata_file)]
        result = commit_metadata(paths)
        if self.on_metadata_commit is not None:
            self.on_metadata_commit(result, paths)

    @property
    def auto_refresh_minutes(self) -> int:
        """Read-only view of `settings["auto_refresh_minutes"]`.

        Deliberately has no setter (t1480 retired a dead one). Settings writes
        arrive as whole-payload updates into `self.settings` — the settings
        dialog dismisses with several keys at once, not all of which have
        properties — so a per-key setter would be a second, partial write path.
        """
        return self.settings.get("auto_refresh_minutes", 0)

    def grouped_topic_lanes(self, tasks, sort_mode):
        """Cached by-topic lanes: rebuild buckets only when the membership/anchor
        signature changes; otherwise re-sort the cached build (cheap). This makes
        sort-mode switches and refocus refreshes re-sort the existing lanes
        instead of re-bucketing every task."""
        sig = _topic_membership_signature(tasks)
        if self.topic_lane_cache is None or self.topic_lane_cache[0] != sig:
            topic_lanes, ungrouped = _build_topic_lanes(tasks)
            self.topic_lane_cache = (sig, topic_lanes, ungrouped)
        _sig, topic_lanes, ungrouped = self.topic_lane_cache
        return _assemble_topic_lanes(topic_lanes, ungrouped, sort_mode)

    def _is_phantom_stub(self, task):
        """Check if a task file is a phantom stub (only board layout keys)."""
        return not task.metadata or set(task.metadata.keys()) <= set(BOARD_KEYS)

    def load_tasks(self):
        # Task objects are rebuilt here; drop the by-topic build cache so it
        # cannot serve stale (replaced) Task references (see topic_lane_cache).
        self.topic_lane_cache = None
        self.task_datas.clear()
        self.archived_task_cache.clear()
        self.clear_gate_cache()
        self.unreadable_files.clear()
        for f in glob.glob(str(self.tasks_dir / "*.md")):
            path = Path(f)
            task = Task(path)
            if not task.load_ok:
                # Present but unreadable. Still dropped from task_datas as
                # before, but no longer silently: it may claim any column.
                self.unreadable_files.add(path.name)
            if self._is_phantom_stub(task):
                continue
            self.task_datas[path.name] = task
        self.load_child_tasks()
        # Membership is a fact about TASKS, so the group sweep lives here rather
        # than beside `_prune_orphan_collapsed_columns` in `load_metadata` —
        # which runs BEFORE any task exists (t1243_10).
        self._prune_orphan_collapsed_groups()

    def load_child_tasks(self):
        self.topic_lane_cache = None
        self.child_task_datas.clear()
        for f in glob.glob(str(self.tasks_dir / "t*" / "t*_*.md")):
            path = Path(f)
            task = Task(path)
            if self._is_phantom_stub(task):
                continue
            self.child_task_datas[path.name] = task

    def reload_task(self, filename: str) -> bool:
        """Reload a single task from disk. Returns True if present after reload."""
        # A reloaded task is a fresh object; drop the by-topic build cache.
        self.topic_lane_cache = None
        if filename in self.task_datas:
            task = self.task_datas[filename]
            if not task.filepath.exists() or not task.load() or self._is_phantom_stub(task):
                del self.task_datas[filename]
                return False
            return True
        if filename in self.child_task_datas:
            task = self.child_task_datas[filename]
            if not task.filepath.exists() or not task.load() or self._is_phantom_stub(task):
                del self.child_task_datas[filename]
                return False
            return True
        # Not in memory — try to discover and load as parent
        path = self.tasks_dir / filename
        if path.exists():
            task = Task(path)
            if not self._is_phantom_stub(task):
                self.task_datas[filename] = task
                return True
        # Try child path pattern: t47_1_desc.md → aitasks/t47/t47_1_desc.md
        m = re.match(r'^(t\d+)_\d+_', filename)
        if m:
            child_path = self.tasks_dir / m.group(1) / filename
            if child_path.exists():
                task = Task(child_path)
                if not self._is_phantom_stub(task):
                    self.child_task_datas[filename] = task
                    return True
        return False

    def find_task_by_id(self, task_id: str):
        """Find a task (parent or child) by its ID like 't47' or 't47_1'."""
        prefix = f"{task_id}_"
        for filename, task in self.task_datas.items():
            if filename.startswith(prefix):
                return task
        # Only a child ID (e.g. 't47_1') may match a child file. A parent ID
        # ('t47') must NOT prefix-match its own children ('t47_1_*'), or an
        # active child shadows the archived-parent fallback in
        # find_task_including_archived (t1026).
        if "_" in str(task_id).lstrip("t"):
            for filename, task in self.child_task_datas.items():
                if filename.startswith(prefix):
                    return task
        return None

    def find_task_including_archived(self, task_id: str):
        """Find an active task first, then lazily resolve archived tasks."""
        active = self.find_task_by_id(task_id)
        if active:
            return active

        normalized = str(task_id).lstrip("t")
        if normalized not in self.archived_task_cache:
            self.archived_task_cache[normalized] = self._load_archived_task(normalized)
        return self.archived_task_cache[normalized]

    def _load_archived_task(self, normalized_task_id: str):
        archived = find_archived_markdown_by_id(
            normalized_task_id,
            self.tasks_dir / "archived",
        )
        if not archived:
            return None
        filename, raw = archived
        if "_" in normalized_task_id:
            parent = normalized_task_id.split("_", 1)[0]
            path = self.tasks_dir / "archived" / f"t{parent}" / filename
        else:
            path = self.tasks_dir / "archived" / filename
        task = Task.from_text(path, raw, archived=True)
        if self._is_phantom_stub(task):
            return None
        return task

    def get_child_tasks_for_parent(self, parent_num: str) -> list[Task]:
        """Get all child tasks for a parent like 't47'."""
        prefix = f"{parent_num}_"
        children = []
        for filename, task in self.child_task_datas.items():
            if filename.startswith(prefix):
                children.append(task)

        def child_sort_key(task: Task):
            match = re.match(rf"^{re.escape(parent_num)}_(\d+)_", task.filename)
            if match:
                return (0, int(match.group(1)), task.filename)
            return (1, 0, task.filename)

        return sorted(children, key=child_sort_key)

    def get_parent_num_for_child(self, child_task: Task) -> str:
        """Determine parent task number from child task filepath.
        e.g., aitasks/t47/t47_1_desc.md -> 't47'"""
        return child_task.filepath.parent.name

    def get_column_tasks(self, col_id: str) -> list[Task]:
        # Filter tasks by column and sort by index. Two guarantees beyond the
        # raw board_idx: normalize_board_idx() makes a hand-quoted "10" sort
        # numerically (and stops a quoted/int mix raising TypeError), and
        # filename breaks ties — load_tasks() fills task_datas in glob order,
        # so sorting on the index alone left ties in directory-enumeration
        # order, which is not durable between two processes reading the same
        # tree. work_report_gather.py imports the same key so a board-reviewed
        # task sequence still validates when the gatherer re-derives it.
        tasks = [t for t in self.task_datas.values() if t.board_col == col_id]
        return sorted(tasks, key=lambda t: (normalize_board_idx(t.board_idx), t.filename))

    def refresh_git_status(self):
        """Query git for modified files in aitasks/ directory."""
        self.modified_files.clear()
        try:
            result = subprocess.run(
                [*_task_git_cmd(), "status", "--porcelain", "--", "aitasks/"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if not line or len(line) < 4:
                        continue
                    # Porcelain format: XY <space> filepath
                    # XY is 2 chars (index + worktree status), then a space
                    filepath = line[3:]
                    if filepath.startswith('"') and filepath.endswith('"'):
                        filepath = filepath[1:-1]
                    if filepath.endswith('.md'):
                        self.modified_files.add(filepath)
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

    def refresh_lock_map(self):
        """Query aitask_lock.sh --list to build a map of locked tasks."""
        self.lock_map.clear()
        try:
            result = subprocess.run(
                ["./.aitask-scripts/aitask_lock.sh", "--list"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    m = re.match(
                        r'^t(\S+): locked by (.+?) on (.+?) since (.+)$',
                        line.strip()
                    )
                    if m:
                        self.lock_map[m.group(1)] = {
                            "locked_by": m.group(2),
                            "hostname": m.group(3),
                            "locked_at": m.group(4),
                        }
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

    def clear_gate_cache(self):
        self.gate_state_cache.clear()
        self.gate_registry_cache = None
        self.gate_registry_error = ""
        # The local-dependency resolver starts a new CYCLE here rather than being
        # dropped (t1527): its id->path and parsed-facts caches are file-identity
        # keyed and self-invalidating, but the gate evaluator behind them memoizes
        # the registry and the code digest — the same two values the digest cache
        # below is cleared for, and for the same reason. A resolver cycle that
        # outlived a refresh would keep a gate-released dependency SATISFIED after
        # the code changed or gates.yaml was edited. Renew both here or neither.
        if self._dep_resolver is not None:
            self._dep_resolver.begin_cycle(
                digest_provider=self.code_digest_for_refresh)
        # MUST stay in this method (t1416). The digest is repo-global rather than
        # per-task, so a lifetime longer than one refresh cycle is not a cache
        # miss — it silently freezes every signature verdict until the process
        # restarts. Keeping it here means it can only outlive the gate state it
        # is derived alongside if someone deletes this line.
        self.gate_digest_cache = _DIGEST_UNSET

    def code_digest_for_refresh(self) -> str | None:
        """Repo code digest, computed once per refresh; ``None`` if unavailable.

        Passed to ``read_task_gate_state`` as a **callable** so it is invoked
        lazily — only when some task's cheap no-git pre-filter finds a stamped
        witness. A board rendering 300 tasks with no signed gates never shells
        out to git; one with signed gates shells out exactly once per refresh.

        Total by contract: ``gate_ledger._resolve_digest`` deliberately does not
        catch, so a raising provider would propagate into the render. Mirrors
        :meth:`gate_registry`'s fail-closed shape — an unavailable digest becomes
        ``None``, which the classifier resolves to *accept* (never a guessed
        stale).
        """
        if self.gate_digest_cache is not _DIGEST_UNSET:
            return self.gate_digest_cache  # type: ignore[return-value]
        try:
            self.gate_digest_cache = gate_ledger.code_digest()
        except Exception:
            self.gate_digest_cache = None
        return self.gate_digest_cache  # type: ignore[return-value]

    def gate_registry(self) -> dict[str, dict]:
        """Read gates.yaml once per refresh; missing/invalid registry is safe."""
        if self.gate_registry_cache is not None:
            return self.gate_registry_cache
        try:
            self.gate_registry_cache = gate_ledger.read_registry(str(self.gates_registry_file))
            self.gate_registry_error = ""
        except Exception as exc:
            self.gate_registry_cache = {}
            self.gate_registry_error = str(exc)
        return self.gate_registry_cache

    def gate_state_for(self, task: Task) -> GateStateResult:
        """Return cached gate derivation for a task, failing closed on errors."""
        key = str(task.filepath)
        cached = self.gate_state_cache.get(key)
        if cached is not None:
            return cached
        has_ledger = False
        try:
            has_ledger = gate_ledger.has_gate_markers(task.content or "")
            # The BOUND METHOD, not its value: passing the memo itself keeps the
            # digest lazy (never computed for a board with no signed witnesses)
            # while capping it at one computation per refresh (t1416).
            state = gate_ledger.read_task_gate_state(
                str(task.filepath), str(self.gates_registry_file),
                self.code_digest_for_refresh
            )
            result = GateStateResult(state=state, has_ledger=has_ledger)
        except Exception as exc:
            result = GateStateResult(error=str(exc), has_ledger=has_ledger)
        self.gate_state_cache[key] = result
        return result

    #: Local-dependency decision core (t1527), built lazily by dep_resolver().
    #: Declared at CLASS level rather than assigned in __init__ so "not built
    #: yet" is the default for any instance — including the several test
    #: harnesses that construct a TaskManager via __new__ and populate only the
    #: fields they need. `dep_resolver()` shadows it with an instance attribute
    #: on first use; nothing ever mutates it at class level.
    _dep_resolver: dep_resolution.LocalDepResolver | None = None

    def dep_resolver(self) -> dep_resolution.LocalDepResolver:
        """The local-dependency resolver, built once and kept.

        Its two caches are file-identity keyed and therefore self-invalidating;
        what is NOT safe to keep is the gate evaluator behind them, so
        :meth:`clear_gate_cache` starts a new cycle on it every refresh — see
        the note there.
        """
        if self._dep_resolver is None:
            self._dep_resolver = dep_resolution.LocalDepResolver(
                str(self.tasks_dir), str(self.gates_registry_file))
            self._dep_resolver.begin_cycle(
                digest_provider=self.code_digest_for_refresh)
        return self._dep_resolver

    def local_dep_verdicts(self, task: Task) -> list[dep_resolution.DepVerdict]:
        """Every non-satisfied local dep of ``task``, verdict included (t1527).

        The decision is `lib/dep_resolution`'s, shared verbatim with `ait ls` and
        the minimonitor picker. Two things change versus the old inline test:

        * resolution reaches `aitasks/archived/` as well as the loaded active
          tasks, so an archived (Done) dep is satisfied *because it resolves to a
          Done task* rather than by accident of `find_task_by_id` returning None;
        * an id that resolves to NOTHING now BLOCKS and is rendered
          `(UNRESOLVED)`, instead of being silently treated as satisfied by the
          old `if dep_task and ...` fail-open.
        """
        return [v for v in self.dep_resolver().classify(
            task.metadata.get('depends', []) or []) if v.blocking]

    def unresolved_local_deps(self, task: Task) -> list[str]:
        """Display strings for :meth:`local_dep_verdicts` — `t42`, `t2 (UNRESOLVED)`."""
        return [v.display(prefix='t') for v in self.local_dep_verdicts(task)]

    def cross_repo_dep_display(self, task: Task) -> tuple[list[str], bool]:
        xdep_display = []
        xdep_blocked = False
        xdeprepo = task.metadata.get('xdeprepo')
        xdeps = task.metadata.get('xdeps', []) or []
        if xdeprepo and xdeps:
            for xd in xdeps:
                xid = str(xd).lstrip('t')
                ref = f"{xdeprepo}#{xid}"
                xstatus = self.get_xdep_status(xdeprepo, xid)
                if xstatus == 'Done':
                    xdep_display.append(ref)
                elif not xstatus or xstatus == 'NOT_FOUND':
                    xdep_display.append(f"{ref} (UNREACHABLE)")
                    xdep_blocked = True
                else:
                    xdep_display.append(f"{ref} [{xstatus}]")
                    xdep_blocked = True
        return xdep_display, xdep_blocked

    def _gate_summary(self, result: GateStateResult) -> str:
        state = result.state
        if result.error:
            return "gate state unavailable"
        if not result.has_ledger:
            # The next_action line already carries the friendly
            # "No gate information yet" copy; omit a duplicate summary line.
            return ""
        if not state or not state.current:
            return "no recorded gates"
        parts = []
        stale = set(state.stale_signed)
        for run in state.current.values():
            if run.name in stale:
                # Both facts, never one without the other (t1416): the ledger
                # really does read `pass`, AND that signature no longer binds
                # the current code. Showing only the ledger is the disagreement
                # this surface exists to remove; showing only "stale" would hide
                # that it was ever approved.
                parts.append(f"⚠ {run.name}:{run.status} (stale signature)")
                continue
            parts.append(f"{run.icon} {run.name}:{run.status}")
        return "  ".join(parts)

    def _human_pending_gates(self, result: GateStateResult) -> list[str]:
        """Pending human gates for the In-Flight view — the SAME predicate the
        phase axis uses (t1642); see `_pending_human_gates`.

        The body is kept free of gate logic on purpose: re-deriving it here is
        exactly the drift this task removed, and
        `SharedGatePredicateContractTest` fails if any reappears.
        """
        if result.state is None:
            return []
        return _pending_human_gates(result.state, self.gate_registry())

    def _has_failed_gate(self, result: GateStateResult) -> bool:
        """Whether an ACTIVE gate's current run failed (t1642); see
        `_failed_active_gates`. Same no-gate-logic contract as above."""
        return bool(_failed_active_gates(result.state))

    def _inflight_item_for(self, task: Task) -> InFlightItem | None:
        status = task.metadata.get("status")
        # Cheap pre-filter FIRST (t1603_3). `derive_workflow_phase` below is
        # the actual admission rule — its `None` is exactly "not in a workflow
        # phase" — but `gate_state_for` reads and parses the task file, and
        # this method runs for every task on the board on every refresh. This
        # only avoids paying for that on tasks `status` alone rejects.
        if status not in ("Implementing", "Ready"):
            return None
        approved_unstarted = status == "Ready" and bool(
            _plan_approved_marker(task.metadata))
        if status == "Ready" and not approved_unstarted:
            return None
        task_id, title = TaskCard._parse_filename(task.filename)
        if not task_id:
            return None
        result = self.gate_state_for(task)
        phase = derive_workflow_phase(
            task, result, self.gate_registry(),
            # The CALLABLE, not its value (t1656) — the same shape
            # `gate_state_for` uses for `code_digest_for_refresh`. Exactly one
            # of `derive_workflow_phase`'s branches reads it (the no-ledger
            # degradation), so an in-flight item in any other state now pays no
            # `Path.exists()` at all. Do NOT hoist the decision here by testing
            # `result.error` / `result.has_ledger`: that restates the ladder's
            # branch conditions in the caller and drifts the moment their order
            # changes. The laziness belongs in the seam.
            plan_exists_probe=lambda: _resolve_plan_path_for_task(
                task, self) is not None)
        if phase is None:
            return None
        blockers = self.unresolved_local_deps(task)
        xdep_display, xdep_blocked = self.cross_repo_dep_display(task)
        if xdep_blocked:
            blockers.extend(xdep_display)

        human_gates = self._human_pending_gates(result)
        failed = self._has_failed_gate(result)
        state = result.state
        stale_signed = list(state.stale_signed) if state else []

        # Both axes come off the SAME `WorkflowPhase` (t1603_3). No branch below
        # re-reads `resume_point` / `archive_decision` / `stale_signed` to
        # decide a lane; that parallel ladder is what let a card's lane and its
        # chip contradict each other.
        group = _inflight_lane(phase.phase, phase.progress,
                               approved_unstarted=approved_unstarted,
                               blocked=bool(blockers))
        next_action = _inflight_next_action(
            phase, blockers=blockers, approved_unstarted=approved_unstarted,
            stale_signed=stale_signed, failed=failed, human_gates=human_gates)

        return InFlightItem(
            task=task,
            task_id=task_id,
            title=title,
            group=group,
            next_action=next_action,
            gate_summary=self._gate_summary(result),
            human_gates=human_gates,
            blockers=blockers,
            state_error=result.error,
            has_ledger=result.has_ledger,
            stale_signed=stale_signed,
            phase=phase.phase,
            provenance=phase.provenance,
            progress=phase.progress,
            approved_unstarted=approved_unstarted,
        )

    def get_inflight_items(self) -> list[InFlightItem]:
        items = []
        for task in self.task_datas.values():
            item = self._inflight_item_for(task)
            if item:
                items.append(item)
        for task in self.child_task_datas.values():
            item = self._inflight_item_for(task)
            if item:
                items.append(item)
        return sorted(items, key=lambda item: _task_id_sort_key(item.task_id))

    def get_xdep_status(self, repo: str, task_id: str) -> str:
        """Live status of a cross-repo dependency, cached per refresh cycle.

        Shells out to ``aitask_query_files.sh --project <repo> task-status
        <id>`` (cross-repo re-exec resolves <repo> via the registry). Returns
        the cross-repo task's status (e.g. ``Implementing``, ``Done``),
        ``NOT_FOUND`` when the project resolves but the task is missing, or
        ``""`` (empty) when the project is unreachable (stale/unregistered)
        or the probe fails — callers treat both empty and ``NOT_FOUND`` as
        UNREACHABLE. Results are cached in ``self.xdep_status_cache`` keyed
        by ``(repo, task_id)`` so the probe does not fire per redraw.
        """
        key = (repo, task_id)
        if key in self.xdep_status_cache:
            return self.xdep_status_cache[key]
        status = ""
        try:
            result = subprocess.run(
                ["./.aitask-scripts/aitask_query_files.sh",
                 "--project", repo, "task-status", task_id],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if line.startswith("STATUS:"):
                        status = line[len("STATUS:"):].strip()
                        break
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            status = ""
        self.xdep_status_cache[key] = status
        return status

    def _mark_written(self, task: Task) -> None:
        """Record a file this session just wrote as modified, without a `git status`.

        Movement used to re-run `refresh_git_status()` — a blocking subprocess — on
        every keypress just to learn something it already knew: a move writes exactly
        the files it produced. Marking happens at the WRITE SITE rather than in the
        movement action so a caller cannot forget it, and so compaction is covered:
        `reposition_task` may respace a whole column, writing N files that its
        `MoveResult.moved` does not name.

        Add-only by construction. A file that becomes clean again (committed from
        another terminal, or an exact round-trip back to its indexed content) keeps
        its marker until the next full scan — which still runs on `refresh_board`
        (manual `r`, view switches, the auto-refresh tick), on the detail-screen
        return, and after the board's own commit.

        The key must match `is_modified`, i.e. `str(task.filepath)`.
        """
        self.modified_files.add(str(task.filepath))

    def is_modified(self, task: Task) -> bool:
        """Check if a task file is modified vs git."""
        return str(task.filepath) in self.modified_files

    def get_modified_tasks(self) -> list[Task]:
        """Get all tasks (parent and child) that have git modifications."""
        modified = []
        for filename, task in self.task_datas.items():
            if self.is_modified(task):
                modified.append(task)
        for filename, task in self.child_task_datas.items():
            if self.is_modified(task):
                modified.append(task)
        return modified

    # --- Gap indexing (t1243_3) ------------------------------------------
    #
    # A single move writes EXACTLY ONE task file and never a file outside the
    # move; a multi-hop transit A->B->C writes the moved task once per hop and
    # nothing in A or B. The one bounded exception is compaction, reachable
    # from `reposition_task` alone (see its docstring).
    #
    # Every index is read through `normalize_board_idx`, so a hand-quoted
    # `boardidx: "20"` sitting next to ints can never raise TypeError here.

    def _column_indices(self, col_id: str, exclude: str = ""):
        """Normalized indices of a column, excluding one task by filename.

        The exclusion is what lets a card already holding the column extremum
        still move strictly past it: an append that counted the mover would
        return `self + STEP` and the card would not move at all.
        """
        return [normalize_board_idx(t.board_idx)
                for t in self.get_column_tasks(col_id) if t.filename != exclude]

    def _resolve_parents(self, task_names):
        """Split names into (tasks, refusals), preserving input order.

        Only parent tasks are resolvable: `task_datas` holds parents, and board
        movement is a parent-level operation (every movement action early-returns
        on a child card). A child id or an unknown filename is REFUSED with a
        reason rather than skipped, so a caller can report which items failed.
        Duplicates resolve once — a repeat must not consume two indices.
        """
        tasks, refused, seen = [], [], set()
        for name in task_names:
            task = self.task_datas.get(name)
            if task is None:
                refused.append((name, "not_a_parent_task"))
            elif name not in seen:
                seen.add(name)
                tasks.append(task)
        return tasks, refused

    def move_task_to_column(self, task_name: str, new_col: str) -> MoveResult:
        """Move one task to the bottom of `new_col`. One write, source untouched."""
        return self.move_tasks_to_column([task_name], new_col)

    def move_tasks_to_column(self, task_names, new_col: str) -> MoveResult:
        """Move K tasks to the bottom of `new_col`, preserving input order.

        **All-or-nothing:** if ANY name fails to resolve, nothing is written and
        the returned report names every offender. Resolving the whole batch
        before the first write is what makes that true — a loop that wrote as it
        went would leave the batch half-applied on the first bad id.

        Appends past the destination maximum, an unbounded region, so this can
        never exhaust an interval and never compacts.

        The whole run is computed from ONE scan of the destination (t1369), so
        the batch costs O(N + K) rather than the O(K x (N + K)) a re-scan per
        task would: each appended value is by construction the new maximum, so
        the run is plain `start + i * STEP` arithmetic.
        """
        tasks, refused = self._resolve_parents(task_names)
        if refused:
            return MoveResult(refused=tuple(refused))
        if not tasks:
            return MoveResult()

        run = board_ordering.indices_for_append_run(
            self._column_indices(new_col), len(tasks))
        moved = []
        for task, idx in zip(tasks, run):
            task.board_col = new_col
            task.board_idx = idx
            task.reload_and_save_board_fields(("boardcol", "boardidx"))
            self._mark_written(task)
            moved.append(task.filename)
        return MoveResult(moved=tuple(moved))

    def move_task_to_edge(self, task_name: str, col_id: str,
                          to_top: bool) -> MoveResult:
        """Move a task to the top or bottom of its column. One write.

        Places past a column extremum, so like the column moves it can never
        compact. "Top" produces a negative index once the column starts at or
        below STEP — that is intended and legal.
        """
        tasks, refused = self._resolve_parents([task_name])
        if refused:
            return MoveResult(refused=tuple(refused))
        task = tasks[0]
        indices = self._column_indices(col_id, exclude=task.filename)
        task.board_idx = (board_ordering.index_for_prepend(indices) if to_top
                          else board_ordering.index_for_append(indices))
        task.reload_and_save_board_fields(("boardidx",))
        self._mark_written(task)
        return MoveResult(moved=(task.filename,))

    def reposition_task(self, task_name: str, before, after) -> MoveResult:
        """Place a task between two neighbours in rendered order. One write.

        `before` is the task that will sit immediately ABOVE it and `after` the
        one immediately BELOW; `None` means "no neighbour on that side", i.e.
        the task becomes first (prepend) or last (append). Callers must pass
        `None` explicitly rather than relying on negative list indexing —
        `tasks[i - 2]` at `i == 1` silently yields the LAST card.

        This replaces the old index swap: one write instead of two, and it fixes
        the equal-index no-op (two cards sharing an index are ordered by
        filename, so exchanging their indices moved nothing).

        **The only compaction site.** When the interval between the neighbours
        is exhausted (`index_between` returns None — a gap of 1, a tie, or an
        inversion), the column is respaced ONCE at `stride_for(1)` and the
        placement retried. Post-respace every gap is `stride` wide, so the retry
        cannot fail and there is never a second compaction.
        """
        tasks, refused = self._resolve_parents([task_name])
        if refused:
            return MoveResult(refused=tuple(refused))
        task = tasks[0]
        col_id = task.board_col

        idx, compacted = self._index_for_slot(task, col_id, before, after), False
        if idx is None:
            self.respace_column(col_id, stride=board_ordering.stride_for(1))
            compacted = True
            idx = self._index_for_slot(task, col_id, before, after)
            if idx is None:                     # unreachable: gaps are `stride` wide
                raise AssertionError(
                    f"board_ordering: retry after respace of {col_id!r} still has "
                    f"no room between {getattr(before, 'board_idx', None)!r} and "
                    f"{getattr(after, 'board_idx', None)!r} — stride_for(1)="
                    f"{board_ordering.stride_for(1)}")

        task.board_idx = idx
        task.reload_and_save_board_fields(("boardidx",))
        self._mark_written(task)
        return MoveResult(moved=(task.filename,), compacted=compacted)

    def _index_for_slot(self, task, col_id, before, after):
        """Index for `task` between `before`/`after`, or None if exhausted.

        Re-reads the neighbours' `board_idx` on every call, so it returns a
        fresh answer after a respace has renumbered them in place.
        """
        if before is None:
            return board_ordering.index_for_prepend(
                self._column_indices(col_id, exclude=task.filename))
        if after is None:
            return board_ordering.index_for_append(
                self._column_indices(col_id, exclude=task.filename))
        return board_ordering.index_between(normalize_board_idx(before.board_idx),
                                            normalize_board_idx(after.board_idx))

    def respace_column(self, col_id: str, stride: int = board_ordering.STEP):
        """Re-number a whole column to `stride`, 2*stride, ... — N writes.

        THE EXHAUSTION REMEDY ONLY. Never call this from a movement path: doing
        so reinstates exactly the write amplification t1243_3 removed (see the
        `respace_after_move` negative control in tests/test_board_movement.py).
        """
        tasks = self.get_column_tasks(col_id)
        for task, new_idx in zip(tasks, board_ordering.respace_indices(len(tasks), stride)):
            if normalize_board_idx(task.board_idx) != new_idx:
                task.board_idx = new_idx
                task.reload_and_save_board_fields(("boardidx",))
                self._mark_written(task)

    def add_column(self, col_id: str, title: str, color: str):
        """Add a new column to the board configuration."""
        self.columns.append({"id": col_id, "title": title, "color": color})
        self.column_order.append(col_id)
        self.save_metadata()

    def update_column(self, col_id: str, new_id: str, new_title: str, new_color: str):
        """Update id, title, and color of an existing column."""
        for col in self.columns:
            if col["id"] == col_id:
                col["id"] = new_id
                col["title"] = new_title
                col["color"] = new_color
                break
        if col_id != new_id:
            # Update column_order
            idx = self.column_order.index(col_id) if col_id in self.column_order else -1
            if idx >= 0:
                self.column_order[idx] = new_id
            # Migrate collapsed state: a rename that moved column_order and every
            # member's boardcol but left `collapsed_columns` pointing at the old id
            # orphaned the entry, so the renamed column silently lost its collapse
            # (t1377_4).
            #
            # This whole `col_id != new_id` branch is DORMANT BY DECISION, not by
            # oversight (t1377_5): column ids are auto-slugged, so re-slugging on
            # a title edit would rewrite every member task's `boardcol` as a side
            # effect of a cosmetic change — and ids are also referenced by the
            # work-report protocol. Both `_apply_column_edit` and the headless
            # writer therefore pass the id unchanged. Keep the migration correct
            # for the day a deliberate rename flow (with its own confirmation)
            # wants it; do not treat it as an unfinished handoff.
            collapsed = list(self.collapsed_columns)
            if col_id in collapsed:
                collapsed[collapsed.index(col_id)] = new_id
                self.collapsed_columns = collapsed
            # Same migration for the composite GROUP keys (t1243_10): a group is
            # `(column, slug)`, so renaming the column renames the identity of
            # every group in it. Union semantics means a rename onto a column
            # that already holds a same-slug group coalesces with no branch here.
            self.remap_collapsed_groups(column_remap({col_id: new_id}))
            # Reassign tasks from old ID to new ID
            for task in self.get_column_tasks(col_id):
                task.board_col = new_id
                task.reload_and_save_board_fields(("boardcol",))
        self.save_metadata()

    @property
    def collapsed_columns(self) -> list[str]:
        """Return list of currently collapsed column IDs."""
        return self.settings.get("collapsed_columns", [])

    @collapsed_columns.setter
    def collapsed_columns(self, value: list[str]):
        self.settings["collapsed_columns"] = value

    def toggle_column_collapsed(self, col_id: str):
        """Toggle collapse state for a column and persist the USER layer.

        `collapsed_columns` lives in `settings`, so `save_settings()` persists it
        completely — and a per-user view toggle must not rewrite the git-tracked
        `board_config.json` (t1243_10, `tui_conventions.md`).
        """
        collapsed = list(self.collapsed_columns)
        if col_id in collapsed:
            collapsed.remove(col_id)
        else:
            collapsed.append(col_id)
        self.collapsed_columns = collapsed
        self.save_settings()

    def is_column_collapsed(self, col_id: str) -> bool:
        return col_id in self.collapsed_columns

    # --- Group collapse (t1243_10) -------------------------------------------

    def is_group_collapsed(self, col_id: str, slug: str) -> bool:
        """Whether `(col_id, slug)` is collapsed — the model-side twin of
        `KanbanColumn.is_group_collapsed`, which asks the same question from the
        widget's own `col_id`."""
        return group_key(col_id, slug) in self.collapsed_groups

    def toggle_group_collapsed(self, col_id: str, slug: str) -> bool:
        """Toggle `(col_id, slug)` and persist. Returns the NEW collapsed state.

        Mirrors `toggle_column_collapsed` (mutate, then save) with one deliberate
        difference: it saves through `save_settings()`, so a per-user view
        keystroke never rewrites the git-tracked project file.
        """
        key = group_key(col_id, slug)
        collapsed = key not in self.collapsed_groups
        if collapsed:
            self.collapsed_groups.add(key)
        else:
            self.collapsed_groups.discard(key)
        self.save_settings()
        return collapsed

    def remap_collapsed_groups(self, remap) -> None:
        """Re-point / drop collapse keys — THE lifecycle seam (t1243_10).

        Every owner of the composite `"<col>/<slug>"` key calls this with one
        pure rule instead of open-coding a rewrite:

        - `update_column` (column renamed) — `column_remap({old: new})`
        - `delete_column` (column deleted) — `column_remap({col: UNORDERED_ID})`
        - `merge_columns` (columns merged) — `column_remap({src: dest, ...})`
        - t1243_11's `_apply_group_move` (group moved to another column), called
          AFTER the member writes land
        - t1243_12's group rename (slug half) and group dissolve (rule returns
          `None`)

        See `board_groups.remap_group_keys` for the rule shapes and for why
        coalescing is a set union — which is what makes "merge onto an existing
        same-slug group" need no special case here.

        IN-MEMORY ONLY, exactly like `_prune_orphan_collapsed_columns`: every
        owner already ends in a save, and saving here would double-write. A
        caller that also moves member tasks must call this AFTER the member
        writes, in the same synchronous block, so no reload can observe the new
        key with no members and prune it.
        """
        if not self.collapsed_groups:
            return
        self._reset_collapsed_groups(remap_group_keys(self.collapsed_groups, remap))

    def _prune_orphan_collapsed_groups(self):
        """Drop collapse keys whose `(column, slug)` has NO members (t1243_10).

        The accumulation backstop for states no lifecycle owner saw: an external
        `aitask_update.sh --boardgroup` edit, a task archived from another
        checkout, a hand-edited `boardcol`. Runs at the end of `load_tasks`
        because `load_metadata` — where the COLUMN sweep lives — runs before any
        task is loaded, so a member-based sweep there would see zero members for
        every key and wipe the whole list on every boot.

        "No members" is LITERAL: a group that has dropped to exactly ONE member
        keeps its key. `build_column_units` deliberately keeps a single member's
        slug so a member moving away never dissolves the group, and the renderer
        merely stops drawing a header while `len(members) == 1` — which makes the
        key inert, not stale. Pruning at one would silently discard the user's
        collapse the first time a sync moved a member out.

        Column liveness is deliberately NOT a second criterion. A key naming a
        column that no longer exists is kept while its members still claim that
        column — those tasks render nowhere, so the key is inert, and it becomes
        correct again the moment the column returns. Deriving liveness from one
        source (membership) is what stops two criteria from ever disagreeing.

        IN-MEMORY ONLY, like the column sweep: forcing a write on every board
        open would cost a save per launch and race concurrent writers for no
        benefit, since the in-memory value governs rendering.

        SKIPPED while any task file is unreadable. A failed `Task.load()` wipes
        that task's metadata, so its membership is invisible — the same "cannot
        prove it is empty" state `merge_columns` refuses to act on. Sweeping then
        would prune a live group's key on the strength of a transient parse error.
        """
        if not self.collapsed_groups or self.unreadable_files:
            return
        live = set()
        for task in self.task_datas.values():   # parents only — children never
            slug = task_group_slug(task)        # carry group membership
            if slug:
                live.add(group_key(task.board_col, slug))
        if not live.issuperset(self.collapsed_groups):
            self._reset_collapsed_groups(self.collapsed_groups & live)

    def delete_column(self, col_id: str):
        """Delete a column and reassign its tasks to 'unordered'."""
        for task in self.get_column_tasks(col_id):
            task.board_col = "unordered"
            task.board_idx = 0
            task.reload_and_save_board_fields(("boardcol", "boardidx"))
        self.columns = [c for c in self.columns if c["id"] != col_id]
        if col_id in self.column_order:
            self.column_order.remove(col_id)
        # Clean up collapsed state
        collapsed = list(self.collapsed_columns)
        if col_id in collapsed:
            collapsed.remove(col_id)
            self.collapsed_columns = collapsed
        # The GROUPS survive the delete: their members were re-pointed to
        # `unordered` above, so the column half of their collapse keys follows
        # them (t1243_10). A same-slug group already in `unordered` coalesces by
        # union — the same derivation that makes the two sets of members one
        # group once they share a column.
        self.remap_collapsed_groups(column_remap({col_id: UNORDERED_ID}))
        self.save_metadata()

    def merge_columns(self, source_ids, dest_id: str) -> MergeResult:
        """Merge N source columns into `dest_id`, then remove the sources.

        Composes `move_tasks_to_column` per source rather than reimplementing the
        index arithmetic, so members get fresh appended indices from its
        single-scan `indices_for_append_run` (t1369) and this adds no
        `reload_and_save_board_fields` call site.

        **Pass filenames, not `Task` objects.** `move_tasks_to_column` routes
        through `_resolve_parents`, which looks names up in `task_datas` — a dict
        keyed by FILENAME. Handing it the `Task` objects `get_column_tasks`
        returns makes every lookup miss, refusing the whole batch as
        `not_a_parent_task` and writing nothing: a silent no-op merge, not a
        crash. `update_column`'s rename path assigns `task.board_col` directly and
        never touches `_resolve_parents`, so the object shape is right there and
        wrong here.

        All-or-nothing on INPUTS only: every id is resolved and validated before
        the first write. See `MergeResult` for the partial-progress contract and
        the per-failure retry paths.

        `unordered` is accepted on both sides. As a destination it is what
        `delete_column` already does; as a source it is "empty the inbox", and its
        config removal is skipped because the synthetic lane has no config entry —
        a blind `column_order.remove(UNORDERED_ID)` would raise `ValueError`.
        """
        self._revalidate_unreadable()
        srcs = list(source_ids)
        refused: list[tuple[str, str]] = []
        if not srcs:
            refused.append(("", "no_source_columns"))
        seen = set()
        for src in srcs:
            if src in seen:
                refused.append((src, "duplicate_source"))
                continue                      # one refusal per offending id
            seen.add(src)
            if src == dest_id:
                refused.append((src, "source_is_destination"))
            elif src != UNORDERED_ID and self.get_column_conf(src) is None:
                refused.append((src, "unknown_column"))
        if dest_id != UNORDERED_ID and self.get_column_conf(dest_id) is None:
            refused.append((dest_id, "unknown_destination"))
        if refused:
            # Nothing written — not even save_metadata (the byte-identical tree
            # assertion in tests/test_board_column_manage.py covers config files).
            return MergeResult(refused=tuple(refused))

        # Deterministic destination sequence: configured columns in column_order
        # order, then `unordered` last. It is synthetic and absent from
        # column_order, so `column_order.index()` would raise on a mixed merge.
        order = self.column_order
        srcs.sort(key=lambda c: order.index(c) if c in order else len(order))

        merged: list[str] = []
        failed: list[tuple[str, str]] = []
        drained: list[str] = []
        for src in srcs:
            names = [t.filename for t in self.get_column_tasks(src)]
            if not names:
                drained.append(src)
                continue
            exc = None
            try:
                self.move_tasks_to_column(names, dest_id)
            except OSError as raised:
                exc = raised
            # Verify against disk on BOTH paths. "No exception" does not mean
            # "written": reload_and_save_board_fields returns early and silently
            # when its reload fails, and move_tasks_to_column still counts that
            # task as moved. Trusting the nominal path would drain a source whose
            # member never landed.
            landed = self._classify_members(names, dest_id, exc, failed)
            merged.extend(landed)
            if exc is None and len(landed) == len(names):
                drained.append(src)            # else: keep the source

        # An unreadable task file may claim ANY column, so while one exists we
        # cannot prove a source is empty and must not remove it — on this run or
        # on a retry. Without this, the retry path is where the orphan happens:
        # the failed `Task.load()` wiped the member's metadata, so
        # `get_column_tasks(src)` no longer lists it, the source looks empty, and
        # it gets removed while the file on disk still names it.
        if self.unreadable_files and drained:
            failed.append((MERGE_UNVERIFIABLE_KEY,
                           "unreadable task file(s), cannot verify a column is "
                           f"empty: {', '.join(sorted(self.unreadable_files))}"))
            drained = []

        if not drained:
            return MergeResult(merged=tuple(merged), failed=tuple(failed))

        before = (list(self.columns), list(self.column_order),
                  list(self.collapsed_columns), set(self.collapsed_groups))
        self.columns = [c for c in self.columns if c.get("id") not in drained]
        self.column_order = [c for c in self.column_order if c not in drained]
        collapsed = [c for c in self.collapsed_columns if c not in drained]
        if collapsed != self.collapsed_columns:
            self.collapsed_columns = collapsed
        # The SIXTH collapse-key lifecycle owner (t1243_10). Placed with the
        # other config removals, and keyed on `drained` rather than on `merged`:
        # the column half of a group key states WHICH COLUMN HOLDS THE GROUP, so
        # it must change exactly where column membership does. A partially merged
        # source still exists and still holds members, so its key is still true;
        # the convergent retry that finally drains it re-points then.
        self.remap_collapsed_groups(column_remap({s: dest_id for s in drained}))
        try:
            self.save_metadata()
        except OSError as exc:
            # save_metadata tags which of its two files failed. An untagged
            # OSError (raised before either write) means nothing landed, so
            # "project" is the fail-safe default: it rolls back.
            if getattr(exc, "phase", "project") == "project":
                # Project write did not land: nothing durable. Restore, so
                # in-memory matches disk and re-running merge_columns converges.
                self.columns, self.column_order, self.collapsed_columns = before[:3]
                # Restored IN PLACE: the app and every mounted KanbanColumn alias
                # this set, so `self.collapsed_groups = before[3]` would orphan
                # all of them (see `_reset_collapsed_groups`). The re-point is
                # not durable either — the project half is written first, so a
                # project-phase failure means the local half never ran — and
                # leaving it applied would let the next unrelated save persist a
                # merge that never happened.
                self._reset_collapsed_groups(before[3])
                failed.append((MERGE_METADATA_KEY, f"config_write_failed: {exc}"))
                return MergeResult(merged=tuple(merged), failed=tuple(failed))
            # Project write LANDED; the local half is pending. Do NOT roll back:
            # save_metadata writes self.columns wholesale, so restoring the
            # sources would resurrect them on the next save. The merge itself
            # succeeded; the retry is save_metadata(), never merge_columns().
            failed.append((MERGE_METADATA_LOCAL_KEY, f"local_cleanup_pending: {exc}"))
            return MergeResult(merged=tuple(merged), failed=tuple(failed),
                               sources_removed=tuple(drained))
        return MergeResult(merged=tuple(merged), failed=tuple(failed),
                           sources_removed=tuple(drained))

    def _revalidate_unreadable(self):
        """Re-check tracked unreadable files and release the ones that now parse.

        `unreadable_files` is otherwise cleared only by `load_tasks`, so without
        this a same-manager retry after the file is repaired stays blocked on a
        stale entry forever — a permanent refusal to merge, which is worse than
        the orphan the block exists to prevent. A fresh manager hides the bug
        because it re-runs `load_tasks`.

        A repaired file is also restored to `task_datas`: the failed load wiped
        its metadata, so it is invisible in its real column until re-read, and
        the retry must actually move it rather than merely stop refusing.

        Runs at the start of every merge. It iterates only the tracked set, which
        is empty in the normal case, so it costs nothing when nothing is broken.

        Scope: parents only, matching `load_tasks`. Column membership is a
        parent-level property (`get_column_tasks` reads `task_datas`), so an
        unreadable child cannot be stranded by removing a column.
        """
        for name in sorted(self.unreadable_files):
            path = self.tasks_dir / name
            if not path.exists():
                self.unreadable_files.discard(name)   # gone: nothing to strand
                self.task_datas.pop(name, None)
                continue
            task = Task(path)
            if not task.load_ok:
                continue                              # still unreadable
            self.unreadable_files.discard(name)
            if self._is_phantom_stub(task):
                self.task_datas.pop(name, None)
            else:
                self.task_datas[name] = task

    def _classify_members(self, names, dest_id, exc, failed):
        """Re-read `names` from disk and return those that actually landed.

        Runs after EVERY source's move, not only after an `OSError`, because a
        nominal return does not prove a write happened.
        `reload_and_save_board_fields` skips its save and returns normally when
        its reload fails — a deleted file, but equally a permission or decode
        error on a file that still exists. `move_tasks_to_column` marks that task
        written and reports it in `moved` regardless. Believing it would let
        `merge_columns` drain a source whose member still carries the source
        column on disk, orphaning it onto a column that no longer exists.

        Disk is the independent ground truth here: asking the same in-memory
        objects that the failed write already corrupted (a failed `Task.load()`
        wipes `metadata`) would be checking the answer against itself.

        `move_tasks_to_column` sets `task.board_col`/`board_idx` BEFORE the write,
        and `reload_and_save_board_fields` re-applies those values after its own
        reload — so when the save raises, the in-memory copy claims the
        destination while disk still says the source. `get_column_tasks` filters
        on that in-memory value, so without this reconcile a same-manager retry
        would not see the task in `src`, would find the source "empty", and would
        remove the column — orphaning the task onto a column that no longer
        exists. The raising call also returns no `MoveResult`, so which members
        landed is recovered from disk rather than from a return value.

        Appends to `failed`: the first non-moved member carries the OSError (it is
        the I/O casualty), the rest are `not_attempted`. A member whose file
        vanished mid-merge cannot be reloaded, so its in-memory value is
        untrustworthy and it is reported `file_missing` rather than counted either
        way.
        """
        moved, unreadable = [], set()
        for name in names:
            task = self.task_datas.get(name)
            if task is None:
                continue
            if not task.load():
                # Deleted and unreadable are NOT the same state. A file that is
                # gone cannot be orphaned by removing its column; one that still
                # exists carries a `boardcol` we cannot read and must block the
                # removal until it becomes readable.
                unreadable.add(name)
                if task.filepath.exists():
                    self.unreadable_files.add(name)
                continue
            if task.board_col == dest_id:
                moved.append(name)

        # Derive the attempt boundary from SOURCE ORDER, not from a filtered
        # list. `move_tasks_to_column` writes in `names` order and raises on
        # exactly one member, so the first member that did not move IS the
        # casualty and everything after it was never attempted. Filtering
        # vanished members out first would shift that boundary: a casualty whose
        # file also disappeared would drop out of the list, promoting the next
        # (untouched) member to position 0 and blaming it for the I/O error.
        moved_set = set(moved)
        # With no OSError there is no I/O casualty to attribute, so start past
        # the boundary: a non-landed member is a silent skip, not a write error.
        casualty_seen = exc is None
        for name in names:
            if name in moved_set:
                continue
            if name in unreadable:
                failed.append((name, "unreadable" if name in self.unreadable_files
                               else "file_missing"))
                casualty_seen = True
                continue
            if not casualty_seen:
                casualty_seen = True
                failed.append((name, f"write_failed: {exc}"))
            else:
                failed.append((name, "not_attempted" if exc is not None
                               else "not_written"))
        return moved

    def get_column_conf(self, col_id: str):
        """Return the config dict for a column, or None."""
        return next((c for c in self.columns if c["id"] == col_id), None)
