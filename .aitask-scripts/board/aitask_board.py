from __future__ import annotations

import os
import re
import sys
import json
import glob
import shlex
import subprocess
from datetime import datetime
from dataclasses import field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
# Own directory too (t1794, C1): sibling board modules are imported by bare
# name, and not every loader (the fixture's spec_from_file_location, the
# shortcut sweep, subprocess probes) has put board/ on sys.path first.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from rich.cells import cell_len
from rich.markup import escape
from rich.text import Text
from mark_glyphs import MARK_CHECKED, MARK_UNCHECKED, mark_markup
from config_utils import task_dir
from agent_command_screen import AgentCommandScreen, resolve_skill_profile
from agent_launch_utils import find_terminal, spawn_in_terminal, find_window_by_name, resolve_dry_run_command, resolve_agent_string, TmuxLaunchConfig, launch_in_tmux, launch_or_focus_codebrowser, load_tmux_defaults, maybe_spawn_minimonitor, _lookup_window_name, tmux_window_target
from sync_action_runner import (
    SyncConflictScreen,
    run_sync_batch,
    run_interactive_sync,
    STATUS_AUTOMERGED,
    STATUS_MERGED,
    STATUS_CONFLICT,
    STATUS_DEFERRED,
    STATUS_ERROR,
    STATUS_NOTHING,
    STATUS_NO_NETWORK,
    STATUS_NO_REMOTE,
    STATUS_NOT_FOUND,
    STATUS_PULLED,
    STATUS_PUSHED,
    STATUS_SYNCED,
    STATUS_TIMEOUT,
)
from tui_switcher import TuiSwitcherMixin, TuiSwitcherOverlay
from shortcuts_mixin import ShortcutsMixin, get_label
from keybinding_registry import resolve_key
from multirow_footer import MultiRowFooter
from cross_repo_notation import parse as parse_cross_repo_notation
from task_levels import LEVELS_ASCENDING
from archive_iter import find_archived_markdown_by_id, iter_archived_frontmatter
import trail_schema
# Trail discovery/dedup/overlap/load moved to lib/trail_discovery.py (t1647_1) so
# the merge surfaces can reuse them; the board keeps rendering ownership. The
# names below are RE-EXPORTS: inside trail_discovery these functions call each
# other through THAT module's namespace, so a test stubbing one of them (or
# ARTIFACT_SCRIPT) for a caller that also lives there must patch it on
# `trail_discovery`, not here — rebinding the board's name would not be seen.
import trail_discovery
from trail_discovery import (
    TRAIL_ARTIFACT_KIND, ARTIFACT_SCRIPT, TrailInfo, trail_entry_refs,
    compute_trail_overlaps, _trail_owner_rank, dedupe_trail_records,
    _iter_active_task_frontmatter, _iter_trail_frontmatter_records,
    _trail_versions, load_trail_blob, discover_trails,
)
from metadata_commit import remedy_command
from task_commit import commit_task_paths
from task_commit import remedy_command as task_remedy_command
from task_yaml import (
    FRONTMATTER_RE, _FlowListDumper, _TaskSafeLoader, _normalize_task_ids,
    normalize_board_idx, parse_frontmatter,
)
# The board is the SEMANTIC OWNER of grouping (see lib/board_groups.py); it
# consumes the INV-R derivation rather than re-deriving it. Never read
# `boardgroup` raw — `task_group_slug` is the totality boundary that keeps an
# unhashable hand-edited value (`boardgroup: []`) from taking the board down.
from board_groups import (
    build_column_units, group_display_title, group_key, group_members,
    task_group_slug,
)
# The ONE authority for follow-up glyphs and colours (t1468_1). Imported, never
# mirrored: a second map in this file — or a `.fk-<kind>` colour class in the
# CSS, which cannot read a Python dict — would be an unsynchronisable copy.
# `board_widgets._followup_marker` is the render boundary over it.
from followup_kinds import (
    FOLLOWUP_KINDS, UNKNOWN_GLYPH, label_for, marker_for,
    normalize_followup_kind,
)
# Board-generic widgets and render helpers live in board_widgets.py (t1794_2)
# so trail code can reuse them without importing this module (t1794, C1). The
# names below are RE-EXPORTS: `ab.TaskCard`, `ab._status_badge_text` … keep
# resolving for tests and for the subclasses defined here. Inside
# board_widgets these helpers call each other through THAT module's
# namespace, so a test stubbing one of them must patch it on `board_widgets`
# (reachable as `ab.board_widgets`), not here.
import board_widgets
from board_widgets import (
    CollapseToggleButton, ColumnEditButton, ColumnHeader, LoadingOverlay,
    MarkedSelection, PickerItem, TaskCard,
    _followup_colour_hex, _followup_glyph_text, _followup_marker,
    _issue_indicator, _plan_approved_marker, _pr_indicator, _status_badge_text,
)

# The By-Trail view's pure rendering half lives in board_trail_view.py
# (t1794_3). Same re-export contract as board_widgets above: `ab.TrailColumn`,
# `ab.build_trail_lanes` … keep resolving for tests and for KanbanApp. Inside
# board_trail_view the helpers call each other through THAT module's namespace,
# so a stub of one of them must patch `board_trail_view` (reachable as
# `ab.board_trail_view`). The By-Trail App half that CALLS them (drift, reload,
# discovery, launch) lives in board_trail_screen.py below — stub those callees
# there, not here.
import board_trail_view
from board_trail_view import (
    TRAIL_CLASSIFICATION_GLYPHS, TRAIL_CSS, TRAIL_GATHER_SCRIPT,
    TRAIL_WATCH_INTERVAL, TRAIL_WATCH_MAX_TICKS, _TRAIL_GHOST_LABELS,
    TrailColumn, TrailDetailScreen, TrailEntryView, TrailGhostCard,
    TrailSelectItem, TrailSelectScreen, TrailSummaryScreen, TrailTaskCard,
    TrailWaveLane, _GhostTaskStub, _trail_badge_text, _trail_drift_text,
    _trail_stored_freshness, build_trail_lanes, canonical_trail_ref,
    load_local_project_name, run_trail_drift, trail_drift_by_ref,
    trail_ref_to_local_id, trail_summary_text,
)

# The By-Trail view's App half — session state, workers, trail actions, the
# /aitask-trail launch and the shared `run_dialog_command` — lives on
# `TrailScreenMixin` in board_trail_screen.py (t1794_5); `KanbanApp` mixes it
# in and supplies the `TrailHost` surface. Same re-export contract as above.
# The trail paths read `discover_trails`, `_trail_versions`, `load_trail_blob`,
# `run_trail_drift`, `find_terminal`, `resolve_dry_run_command`,
# `AgentCommandScreen`, `launch_in_tmux` … from THAT module's namespace, so a
# stub for a trail launch/drift/discovery or dialog dispatch must patch
# `ab.board_trail_screen`; the board's own re-exports would be inert there.
import board_trail_screen
from board_trail_screen import (
    CODEAGENT_FAILURE_NOTICE, CODEAGENT_SCRIPT, TRAIL_ACTION_CAPABILITIES,
    TRAIL_BINDING, TRAIL_BINDINGS, TrailHost, TrailScreenMixin,
)

# The task data layer lives in three modules (t1794_4): board_task_model.py
# (`Task`, move/merge results), board_workflow_phase.py (phase derivation, the
# in-flight row model) and board_task_manager.py (`TaskManager`, the topic
# build, `_task_git_cmd`). Same re-export contract as above: `ab.TaskManager`,
# `ab.derive_workflow_phase` … keep resolving, but a stub of a name the MANAGER
# calls (`save_local_config`, `project_columns_at`, `datetime` in `Task`) must
# patch the owning module — `ab.board_task_manager` / `ab.board_task_model`.
# `TaskManager` takes its paths as required keywords; `make_task_manager()`
# below binds this module's constants.
import board_task_model
import board_workflow_phase
import board_task_manager
from board_task_model import (
    MERGE_METADATA_KEY, MERGE_METADATA_LOCAL_KEY, MERGE_UNVERIFIABLE_KEY,
    MergeResult, MoveResult, Task,
)
from board_workflow_phase import (
    GateStateResult, INFLIGHT_LANES, InFlightItem, LANE_FOR_PHASE,
    PHASE_LABELS, WORKFLOW_PHASES, WORKFLOW_PROVENANCES, WorkflowPhase,
    _failed_active_gates, _gate_progress, _inflight_lane,
    _inflight_next_action, _pending_human_gates, _pending_procedure_gates,
    _resolve_plan_path_for_task, derive_workflow_phase, phase_chip_text,
)
from board_task_manager import (
    MetadataWriteError, TOPIC_SORT_MODES,
    TOPIC_SORT_MODE_LABELS, TaskManager, _DIGEST_UNSET, _assemble_topic_lanes,
    _build_topic_lanes, _lane_recency, _sort_topic_lanes, _task_git_cmd,
    _task_recency, _topic_id_sortkey, _topic_lane_label,
    _topic_membership_signature, group_tasks_by_topic,
)

from textual.app import App
from textual.content import Content
from textual.containers import Container, Horizontal, HorizontalScroll, VerticalScroll
from textual.widgets import Header, Static, Label, Markdown, Input, Button, SelectionList, DataTable, Collapsible
from textual.widgets.selection_list import Selection
from textual.screen import Screen, ModalScreen
from textual.binding import Binding
from textual.message import Message
from textual import on, work
from textual.compose import compose as _compose_widgets
from textual.command import Provider, Hit, Hits, DiscoveryHit

# --- Configuration & Constants ---

TASKS_DIR = task_dir()
METADATA_FILE = TASKS_DIR / "metadata" / "board_config.json"
TASK_TYPES_FILE = TASKS_DIR / "metadata" / "task_types.txt"
DATA_WORKTREE = Path(".aitask-data")
USERCONFIG_FILE = TASKS_DIR / "metadata" / "userconfig.yaml"
EMAILS_FILE = TASKS_DIR / "metadata" / "emails.txt"
CREATE_SCRIPT = Path(".aitask-scripts") / "aitask_create.sh"
BRAINSTORM_TUI_SCRIPT = Path(".aitask-scripts") / "aitask_brainstorm_tui.sh"
GATES_REGISTRY_FILE = TASKS_DIR / "metadata" / "gates.yaml"


def make_task_manager(**kwargs) -> TaskManager:
    """The board's `TaskManager`, bound to THIS module's task-dir constants.

    `TaskManager` takes its paths as required keywords (t1794_4, C2) because no
    sibling board module may resolve the task directory. This is the one place
    the board binds them, read at CALL time — so a fixture-loaded board binds its
    fixture tree. `KanbanApp` and fixture-mode tests construct through here.
    """
    return TaskManager(tasks_dir=TASKS_DIR, metadata_file=METADATA_FILE,
                       gates_registry_file=GATES_REGISTRY_FILE, **kwargs)


def _task_file_paths_for_ids(ids) -> list[str]:
    """Resolve bare task ids ('10', '10_2', 't10_2') to their on-disk task files.

    Globs rather than reading `TaskManager.task_datas`, so it is valid from
    inside a thread worker and independent of what the board has loaded. A
    parent id cannot match its own children: parents live in `aitasks/` and
    children in `aitasks/t<parent>/`, so the two globs are disjoint.

    Used to widen a scoped commit's pathspec to files the operation wrote as a
    SIDE EFFECT — a parent's `children_to_implement`, a revived folded task —
    which a pathspec naming only the doomed files would leave ownerless (t1702).
    """
    out: list[str] = []
    for tid in ids or []:
        bare = str(tid).lstrip("t")
        if not bare:
            continue
        out.extend(sorted(glob.glob(str(TASKS_DIR / f"t{bare}_*.md"))))
        out.extend(sorted(glob.glob(str(TASKS_DIR / "t*" / f"t{bare}_*.md"))))
    return out


def _task_commit_notice(result, message, paths, *, success_text, failure_lead):
    """Map a `commit_task_paths` result to (text, severity) for a notification.

    A failed commit is NEVER silent (t1677's rule, inherited here): the files are
    already written or deleted on disk, so swallowing the failure recreates the
    ownerless-dirty-file state `ait sync`'s pre-sync sweep quarantines. The error
    text therefore always names the remedy command.
    """
    if result.status == "committed":
        return success_text, "information"
    if result.status in ("nochange", "skipped"):
        return "Nothing to commit", "warning"
    return (
        f"{failure_lead} ({result.detail}). "
        f"Clear it with: {task_remedy_command(message, paths)}",
        "error",
    )


def _dedup_paths(*groups) -> list[str]:
    """Flatten path groups, dropping repeats but preserving first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for group in groups:
        for p in group or []:
            sp = str(p)
            if sp not in seen:
                seen.add(sp)
                out.append(sp)
    return out


def _sanitize_name(name: str) -> str:
    """Sanitize task name: lowercase, underscores, alphanumeric only, max 60 chars."""
    name = name.lower().replace(" ", "_")
    name = re.sub(r'[^a-z0-9_]', '', name)
    name = re.sub(r'_+', '_', name)
    name = name.strip("_")
    return name[:60]


def _load_task_types() -> list:
    """Load valid task types from task_types.txt, with fallback defaults."""
    try:
        if TASK_TYPES_FILE.exists():
            types = sorted(set(
                line.strip() for line in TASK_TYPES_FILE.read_text().splitlines()
                if line.strip()
            ))
            if types:
                return types
    except OSError:
        pass
    return ["bug", "feature", "refactor"]

def _get_user_email() -> str:
    """Read the current user's email from userconfig.yaml, falling back to emails.txt."""
    try:
        if USERCONFIG_FILE.exists():
            for line in USERCONFIG_FILE.read_text().splitlines():
                if line.startswith("email:"):
                    email = line.split(":", 1)[1].strip()
                    if email:
                        return email
    except OSError:
        pass
    try:
        if EMAILS_FILE.exists():
            for line in EMAILS_FILE.read_text().splitlines():
                if line.strip():
                    return line.strip()
    except OSError:
        pass
    return ""


# --- Data Models & Logic ---
# `Task`, `TaskManager`, the move/merge result types, the topic-grouping build
# and the workflow-phase derivation live in board_task_model.py,
# board_task_manager.py and board_workflow_phase.py (t1794_4), re-exported at
# the top of this file.


# --- Filter primitives (t1243_4) ---
# The match decision is separated from the widget that displays it, because
# t1243_10 has to evaluate collapsed-group members that mount NO widget at all.
# Both helpers are module-level and app-free so they are unit-testable without
# booting a KanbanApp (tests/test_board_render_scoping.py).


def task_matches_filter(task, visible, search: str) -> bool:
    """Whether one task passes the active filter — decided from DATA, not a widget.

    `visible` is the board's precomputed eligible-filename set, or `None` for the
    "all cards eligible" sentinel. `search` must already be lowercased (the board
    lowercases at input time, `on_search`).

    Kept callable per individual task so a caller can *count* how many members of a
    group match, not merely ask whether a mounted card should be shown.
    """
    if visible is not None and task.filename not in visible:
        return False
    if search and search not in task.search_haystack:
        return False
    return True


def set_unit_display(unit, is_visible: bool) -> None:
    """Show or hide one filter unit, skipping no-op assignments.

    Assigning `styles.display` schedules a Textual refresh even when the value is
    unchanged, and on a typical pass most units do not change — so the equality
    guard, not the assignment, is the point of this helper.

    `is_child` is read with `getattr` so a future unit that is not a `TaskCard`
    (t1243_10's collapsed-group header) needs no branch added here.
    """
    display = "block" if is_visible else "none"
    if unit.styles.display != display:
        unit.styles.display = display
    # An expanded child card lives inside a `.child-wrapper` Horizontal that also
    # holds the "↳" connector Static; hiding only the card would leave a bare
    # connector row behind.
    wrapper = unit.parent
    if (getattr(unit, "is_child", False) and isinstance(wrapper, Horizontal)
            and wrapper.has_class("child-wrapper")
            and wrapper.styles.display != display):
        wrapper.styles.display = display


# Topic-key semantics (bare-id canonicalization, anchor resolution, child
# fallback) live in lib/topic_semantics.py so non-board consumers (e.g.
# lib/trail_gather.py) share the exact same rule (t1210_2). The board stays
# the semantic owner — see that module's docstring.
from topic_semantics import (  # noqa: E402
    _bare_topic_id, task_anchor_id, task_own_id, topic_key,
)


# The column vocabulary (stock columns + the synthetic `unordered` id) lives in
# lib/board_columns.py so the board, lib/work_report_gather.py and the headless
# move seam share one definition (t1377_1). It was duplicated byte-for-byte here
# and in the gatherer under a "keep in sync" comment. The board stays the
# semantic owner — see that module's docstring.
from board_columns import (  # noqa: E402
    PALETTE_COLORS, UNORDERED_COLOR, UNORDERED_ID, UNORDERED_TITLE,
    generate_col_id,
)


# --- Implementation trails (By-Trail view) ---
# The pure rendering half — projection model, wave cards and columns, the trail
# modals and TRAIL_CSS — lives in board_trail_view.py (t1794_3) and is
# re-exported at the top of this file. KanbanApp keeps the view state, workers
# and key handling.


# --- UI Components ---

class CollapsedColumnPlaceholder(Static):
    """A focusable placeholder inside collapsed columns, enabling keyboard expand."""

    can_focus = True

    def __init__(self, col_id: str):
        super().__init__("···", classes="collapsed-placeholder")
        self.column_id = col_id


class EmptyColumnPlaceholder(Static):
    """A focusable placeholder inside columns that show no cards.

    Covers a column with no tasks at all *and* one whose cards are all hidden
    by the active filter/search: either way there is no TaskCard to anchor
    focus on, so column-scoped actions (reorder, collapse) would be
    unreachable. `apply_filter` owns the show/hide decision.
    """

    can_focus = True

    #: The two states this placeholder can report. They used to render
    #: identically, and that is how a stray search filter came to be read as
    #: "the board rendered no cards" for a whole verification run (t1491).
    EMPTY_LABEL = "(empty)"
    FILTERED_LABEL = "(hidden by filter)"

    def __init__(self, col_id: str):
        super().__init__(self.EMPTY_LABEL, classes="empty-placeholder")
        self.column_id = col_id

    def set_filtered(self, filtered: bool) -> None:
        """Say WHY the column body is blank: filtered out, or genuinely empty.

        Deliberately carries no count. "Rendered rows" and "hidden tasks"
        diverge across column shapes — an expanded group contributes its members
        AND its header, a collapsed group contributes only a header for N
        members, and an expanded parent contributes one card per child — and
        none of those match `ColumnHeader`'s count, which counts parent tasks.
        The only number that would be correct here is the one the header already
        shows one row above, since this widget is shown only when NOTHING in the
        column is visible.

        Label only: identity, `column_id` and focusability are untouched, so
        every path that anchors focus on this widget is unaffected.
        """
        self.update(self.FILTERED_LABEL if filtered else self.EMPTY_LABEL)


class GroupHeader(Static):
    """A focusable in-column task-group header: `▾ perf work (3)` (t1243_9).

    Carries `column_id` — NOT `col_id` like `ColumnHeader` below — because it is
    a first-class focus and filter UNIT: `apply_filter`'s visible-content
    accumulator, the focus rescue, `_column_focus_target` and
    `_get_focused_col_id` all key off `column_id`, exactly as `TaskCard` and the
    two placeholders do. Naming it `col_id` here would make a header invisible to
    every one of them.

    `members` is a list of `Task` DATA, not widgets, and that is load-bearing: a
    COLLAPSED group mounts no member cards at all, so a filter pass has nothing
    to evaluate unless the header carries its members itself. t1243_10 reads the
    same list to count matches for its `· 2 match` badge, and t1468_3 reads it
    again for the `· ▲2 ◈1` follow-up roll-up — same reason both times.
    """

    can_focus = True

    def __init__(self, col_id: str, slug: str, members: list, collapsed: bool):
        super().__init__(classes="group-header")
        self.column_id = col_id
        self.slug = slug
        self.members = members
        self.collapsed = collapsed
        # `· N match` badge (t1243_10); None = no badge. A freshly composed
        # header always starts without one, and every recompose path
        # (`refresh_column` / `refresh_columns` / `refresh_board`) queues an
        # `apply_filter` through `call_after_refresh` whose header loop re-sets
        # this for every header in scope — so a stale badge cannot survive a
        # recompose and a missing one cannot outlive the next pass.
        self.match_count: int | None = None
        self.update(self._label())

    def _followup_rollup(self) -> list:
        """`▲2 ◈1` — per-kind follow-up tally over `self.members` (t1468_3).

        Returns `Content.assemble` parts (a `(text, style)` tuple per coloured
        run, bare `str` otherwise), empty when the group holds no follow-ups.

        A COLLAPSED group mounts no member cards at all, so a per-card glyph is
        invisible there; this header is the only place the provenance can
        surface. Counts are emitted in canonical `FOLLOWUP_KINDS` declaration
        order so the roll-up is deterministic whatever order the members are
        in, each in its own colour, with unrecognised kinds tallied under `·`
        and placed last.

        `members` is task DATA (see the class docstring), so `m.metadata` is
        read directly — no `getattr` fallback, which would mask a real `Task`
        arriving without metadata.
        """
        tally: dict = {}
        for m in self.members:
            marker = _followup_marker(m.metadata)
            if marker:
                tally[marker] = tally.get(marker, 0) + 1
        if not tally:
            return []
        parts: list = []
        known = [(glyph, colour) for glyph, colour, _ in FOLLOWUP_KINDS.values()]
        for marker in known + [(UNKNOWN_GLYPH, None)]:
            count = tally.get(marker)
            if not count:
                continue
            if parts:
                parts.append(" ")
            glyph, colour = marker
            # A `(text, style)` pair IS an assemble part — so a marker with a
            # colour needs no conversion at all; an unknown one degrades to the
            # bare glyph, uncoloured.
            parts.append(marker if colour else glyph)
            parts.append(str(count))
        return parts

    def _label(self):
        """The header's rendered line, rebuilt from scratch on every repaint.

        Returns a Textual `Content`, not a `str`, because the roll-up carries
        per-kind colour. `Content` is deliberate over a Rich `Text`: it is a
        `Visual`, so `Static.update()` takes it as-is, whereas a Rich `Text`
        routes through `Content.from_rich_text(..., console=widget.app.console)`
        and would require a running app — breaking the app-free header harness
        (`tests/test_board_group_filtering.py::GroupHeaderLabelTests`) that
        exists precisely so this formatter can be tested without booting a board.

        Assembled from literal parts, so the user-authored group title is never
        markup-parsed: a hand-edited `boardgroup: "a[/]b"` renders literally
        instead of being interpreted as Rich markup, which the f-string this
        replaced could not promise.
        """
        glyph = "▸" if self.collapsed else "▾"
        parts: list = [
            f"{glyph} {group_display_title(self.slug)} ({len(self.members)})"]
        # No pluralisation branch: "2 match" and "1 match" both read as a verb.
        if self.match_count is not None:
            parts.append(f" · {self.match_count} match")
        rollup = self._followup_rollup()
        if rollup:
            parts.append(" · ")
            parts.extend(rollup)
        return Content.assemble(*parts)

    def set_collapsed(self, collapsed: bool) -> None:
        """Flip the glyph in place — no recompose.

        The same in-place repaint idiom `_repaint_card_mark` uses for the ✓/□:
        one widget's content changes, so rebuilding the column would be pure
        waste. (Collapse itself DOES recompose, because members mount/unmount;
        this is for a header whose glyph alone is stale.)

        Repaints through `_label()`, so it preserves the badge rather than
        erasing it — which is why the badge must live in `_label()` and not be
        appended by whoever sets it.
        """
        if self.collapsed != collapsed:
            self.collapsed = collapsed
            self.update(self._label())

    def set_match_count(self, count: int | None) -> None:
        """Set or clear the `· N match` badge in place — no recompose.

        Same idiom as `set_collapsed`. The no-op guard is the point, not the
        assignment: the filter pass calls this for EVERY header in scope, and on
        a board with no filter active every call is `None -> None` and repaints
        nothing.
        """
        if self.match_count != count:
            self.match_count = count
            self.update(self._label())


#: The board's NAVIGATION STOPS: every focusable content widget, in DOM order.
#: A Textual comma selector matches any of its selector sets and `query()` walks
#: the DOM in order, so one query returns headers and cards correctly
#: interleaved — which two separate queries could not. Type selectors match the
#: whole MRO, so the `TaskCard` half also covers InFlightTaskCard / TrailTaskCard
#: / TrailGhostCard, exactly as the pre-existing `query(TaskCard)` did.
#:
#: Distinct from a MOVEMENT unit: a movement key acts on a header (the whole
#: group), a parent card (its `_card_block()`), or refuses a child card. See
#: `_move_focused_group`.
_UNIT_SELECTOR = "TaskCard, GroupHeader"


class ViewSelector(Static):
    """Shows the current filter state with clickable keyboard shortcuts.

    Layout: ``[a All | l Locked | f Free | i In-Flight]   g Git   t Type``
    - Four mutually-exclusive base filters in brackets (radio).
    - Two independent add-on toggles to the right.
    """

    # (action_id, label, target_id). action_id is the App-level Binding action;
    # target_id is the radio/toggle identifier used by hit-test + click handlers.
    BASES = [
        ("view_all", "All", "all"),
        ("view_locked", "Locked", "locked"),
        ("view_free", "Free", "free"),
        ("view_inflight", "In-Flight", "inflight"),
        ("view_bytopic", "By-Topic", "bytopic"),
        ("view_bytrail", "By-Trail", "bytrail"),
    ]
    ADDONS = [
        ("view_git", "Git", "git"),
        ("view_type", "Type", "type"),
    ]
    BASE_SEP = " | "
    ADDON_GAP = "   "

    def __init__(self, base: str = "all", git_on: bool = False, type_on: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.active_base = base
        self.git_on = git_on
        self.type_on = type_on
        # Populated by render(): list of (start_col, end_col, target_id) where
        # target_id is one of the base ids ("all"/"locked"/"free") or addon
        # ids ("git"/"type"). Drives on_click() hit-testing.
        self._click_targets: list[tuple[int, int, str]] = []

    def _build(self) -> tuple[str, list[tuple[int, int, str]], int]:
        """Lay out the selector once: markup, click targets, and total width.

        Single source of truth — ``render()`` takes the markup and targets,
        ``content_width()`` takes the width. Keeping both on one pass is what
        stops the layout from drifting away from click hit-testing (t1247).

        Widths are counted in terminal *cells* (``cell_len``), not codepoints,
        so a future wide glyph in a label cannot desync the two consumers.
        """
        parts: list[str] = []
        targets: list[tuple[int, int, str]] = []
        col = 0

        # Opening bracket (dim).
        parts.append(r"[dim]\[[/]")
        col += 1

        # Base radio segments.
        for i, (action_id, label, base_id) in enumerate(self.BASES):
            if i > 0:
                parts.append(f"[dim]{self.BASE_SEP}[/]")
                col += cell_len(self.BASE_SEP)
            seg_text = get_label("board", action_id, label, style="leading")
            seg_w = cell_len(seg_text)
            if self.active_base == base_id:
                parts.append(f"[bold cyan]{seg_text}[/]")
            else:
                parts.append(f"[dim]{seg_text}[/]")
            targets.append((col, col + seg_w, base_id))
            col += seg_w

        # Closing bracket (dim). Rich only requires escaping `[` (with `\[`),
        # not `]` — emit it literally.
        parts.append("[dim]][/]")
        col += 1

        # Add-on toggle segments.
        for action_id, label, addon_id in self.ADDONS:
            parts.append(f"[dim]{self.ADDON_GAP}[/]")
            col += cell_len(self.ADDON_GAP)
            seg_text = get_label("board", action_id, label, style="leading")
            seg_w = cell_len(seg_text)
            active = (addon_id == "git" and self.git_on) or (addon_id == "type" and self.type_on)
            if active:
                parts.append(f"[bold cyan]{seg_text}[/]")
            else:
                parts.append(f"[dim]{seg_text}[/]")
            targets.append((col, col + seg_w, addon_id))
            col += seg_w

        return "".join(parts), targets, col

    def content_width(self) -> int:
        """Rendered width in terminal cells.

        Pure — needs no running app, so the board can size `#view_col` from it
        and tests can assert on it directly. Grows automatically when a base
        filter is added or a shortcut is rebound to a longer leading form,
        which is what keeps the filter row from being truncated (t1247).
        """
        return self._build()[2]

    def render(self) -> str:
        markup, targets, _ = self._build()
        self._click_targets = targets
        return markup

    def on_click(self, event):
        # CSS padding 0 1 shifts content by 1 column on the left.
        x = event.x - 1
        for start, end, target in self._click_targets:
            if start <= x < end:
                if target in ("all", "locked", "free", "inflight", "bytopic",
                              "bytrail"):
                    self.app._set_base_filter(target)
                elif target == "git":
                    self.app._toggle_git_filter()
                elif target == "type":
                    self.app._toggle_type_filter()
                return


class InFlightTaskCard(TaskCard):
    """Task card variant for the action-grouped In-Flight view."""

    def __init__(self, item: InFlightItem, manager: "TaskManager", column_id: str):
        super().__init__(item.task, manager, is_child="_" in item.task_id, column_id=column_id)
        self.item = item

    def compose(self):
        with Horizontal(classes="task-title-row"):
            # `self.task_data` IS `item.task` (passed to super().__init__), so
            # every card surface reads follow-up provenance off the same
            # attribute — no In-Flight-specific plumbing.
            followup = _followup_marker(self.task_data.metadata)
            if followup:
                yield Label(_followup_glyph_text(followup),
                            classes="task-followup-glyph")
            yield Label(self.item.task_id, classes="task-number")
            yield Label(self.item.title, classes="task-title")
        yield Label(self.item.next_action, classes="task-info inflight-action")
        # The workflow-phase chip, on EVERY card including Planned ones
        # (t1603_3) — a chip that disappears on some cards makes its absence
        # ambiguous, and the same chip value one lane over is not redundant.
        # It replaces the raw per-run `gate_summary` dump, which a 44-column
        # card has no budget for; the full list lands on the detail screen.
        # markup=False: the error text and gate names are free-form prose and
        # Rich would eat a bracket.
        yield Label(
            phase_chip_text(self.item.phase, self.item.provenance,
                            self.item.progress, error=self.item.state_error,
                            compact=True),
            classes="task-info inflight-phase", markup=False)
        if self.item.blockers:
            yield Label(f"blocked by: {', '.join(self.item.blockers)}", classes="task-info")

        # markup=False: the bracketed shortcut hints are literal UI text, not
        # Rich console markup — otherwise Rich parses "[p pick]" as a tag and
        # swallows it, leaving the hint line blank.
        yield Label(self._ops_hint(self.item), classes="task-info inflight-ops", markup=False)

    @staticmethod
    def _ops_hint(item: InFlightItem) -> str:
        """Assemble the literal operation-hint text for an In-Flight card.

        Both conditionals are gated on `approved_unstarted`, NOT on
        `has_ledger` and NOT on the lane (t1603_3). An approved-but-unstarted
        task DOES carry a ledger — `plan-approved-stop.md` records
        `plan_approved: pass` before reverting the status, and nothing strips
        `## Gate Runs` — whose `review_approved` is still pending, so a
        `has_ledger` test advertises a resume that bypasses the planning
        checkpoint and a sign-off on code that does not exist. A
        `group == "planned"` test fails the same way one step later: a blocking
        dependency puts such a task in the Blocked lane. This is the
        advertisement only; `action_gate_resume` and
        `_record_focused_human_gate` carry the matching refusals.
        """
        ops = ["p pick"]
        if item.has_ledger and not item.approved_unstarted:
            ops.append("g resume")
        if item.human_gates and not item.approved_unstarted:
            ops.append("s sign-off")
            ops.append("f fail")
        return "  ".join(f"[{op}]" for op in ops)

    def _priority_border_color(self):
        if self.item.group == "blocked":
            return "red"
        if self.item.group == "planned":
            return "magenta"
        if self.item.group == "human":
            return "yellow"
        return "green"


class InFlightColumn(VerticalScroll):
    """A column in the In-Flight action view."""

    TITLES = {
        "planned": "Planned",
        "human": "Needs your action",
        "agent": "Agent can continue",
        "blocked": "Blocked",
    }
    COLORS = {
        "planned": "#BD93F9",
        "human": "#FFB86C",
        "agent": "#50FA7B",
        "blocked": "#FF5555",
    }

    def __init__(self, group: str, items: list[InFlightItem], manager: TaskManager):
        super().__init__()
        self.col_id = f"inflight-{group}"
        self.group = group
        self.items = items
        self.manager = manager

    def compose(self):
        title = self.TITLES[self.group]
        color = self.COLORS[self.group]
        header = ColumnHeader(self.col_id, title, len(self.items), is_collapsed=False, editable=False)
        header.styles.background = color
        header.styles.color = "black"
        header.styles.width = "100%"
        header.styles.text_align = "center"
        yield header
        if not self.items:
            yield Static("No tasks", classes="inflight-empty")
        for item in self.items:
            yield InFlightTaskCard(item, self.manager, column_id=self.col_id)

    def on_mount(self):
        self.styles.width = 44
        self.styles.min_width = 34
        self.styles.border = ("round", self.COLORS[self.group])
        self.styles.margin = (0, 1)


class TopicColumn(VerticalScroll):
    """A swimlane in the by-topic (group-by-anchor) view.

    Models InFlightColumn: a non-collapsible, non-editable column header over a
    set of ordinary TaskCards. The lane label carries the topic root's id+title;
    cards keep their priority borders (lane membership is conveyed by the column).
    """

    def __init__(self, label: str, tasks: list, manager: "TaskManager"):
        super().__init__()
        slug = re.sub(r"[^0-9A-Za-z_]+", "-", label).strip("-").lower()
        self.col_id = f"topic-{slug}" if slug else "topic-lane"
        self.label = label
        self.tasks = tasks
        self.manager = manager

    def compose(self):
        header = ColumnHeader(self.col_id, self.label, len(self.tasks),
                              is_collapsed=False, editable=False)
        header.styles.width = "100%"
        header.styles.text_align = "center"
        yield header
        for task in self.tasks:
            yield TaskCard(task, self.manager, is_child=("_" in task_own_id(task)),
                           column_id=self.col_id)

    def on_mount(self):
        self.styles.width = 44
        self.styles.min_width = 34
        self.styles.border = ("round", "#6272A4")
        self.styles.margin = (0, 1)


class TopicSortModeItem(Static):
    """One selectable row in the by-topic sort picker. A click moves the
    selection but does NOT apply it — the screen owns arrow keys and the Confirm
    button applies. Not individually focusable; selection state lives on the
    screen so ↑/↓ and clicks stay in sync."""

    can_focus = False

    def __init__(self, index: int, mode: str, label: str):
        super().__init__()
        self.index = index
        self.mode = mode
        self._label = label
        self.selected = False

    def render(self):
        glyph = "◉" if self.selected else "○"   # ◉ selected, ○ others
        text = f"{glyph} {self._label}"
        return f"[reverse]{text}[/]" if self.selected else text

    def on_click(self, event):
        self.screen.select_index(self.index)


class TopicSortModeScreen(ModalScreen):
    """Single-select picker for the by-topic lane sort order.

    ↑/↓ move the selection (the board's priority arrow bindings fall through for
    this screen — see ``check_action``); a click moves the selection without
    applying it; Enter or the Confirm button applies; Esc / Cancel dismisses
    with no change."""

    BINDINGS = [
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("enter", "confirm", "Confirm", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, current: str):
        super().__init__()
        self._modes = [mode for mode, _label in TOPIC_SORT_MODE_LABELS]
        self.selected = self._modes.index(current) if current in self._modes else 0

    def compose(self):
        # No `picker-dialog` marker (t1366): TopicSortModeItem.can_focus is
        # False and selection lives on the screen, so Textual's focus-driven
        # scroll-into-view never fires here — the scroll would be inert. Only
        # four modes exist, so the list cannot overflow today.
        with Container(id="dep_picker_dialog"):
            yield Label(
                "Topic sort order — [dim]↑/↓ to move, Enter to apply, "
                "Esc to cancel[/]",
                id="dep_picker_title",
            )
            for i, (mode, label) in enumerate(TOPIC_SORT_MODE_LABELS):
                yield TopicSortModeItem(i, mode, label)
            with Horizontal(id="detail_buttons"):
                yield Button("Confirm", variant="primary", id="btn_sort_confirm")
                yield Button("Cancel", variant="default", id="btn_sort_cancel")

    def on_mount(self):
        self._sync_selection()

    def _sync_selection(self):
        for item in self.query(TopicSortModeItem):
            item.selected = (item.index == self.selected)
            item.refresh()

    def select_index(self, idx: int):
        self.selected = idx
        self._sync_selection()

    def action_cursor_up(self):
        self.selected = (self.selected - 1) % len(self._modes)
        self._sync_selection()

    def action_cursor_down(self):
        self.selected = (self.selected + 1) % len(self._modes)
        self._sync_selection()

    def action_confirm(self):
        self.dismiss(self._modes[self.selected])

    def action_cancel(self):
        self.dismiss(None)

    @on(Button.Pressed, "#btn_sort_confirm")
    def _btn_confirm(self):
        self.action_confirm()

    @on(Button.Pressed, "#btn_sort_cancel")
    def _btn_cancel(self):
        self.dismiss(None)


class GateChoiceItem(PickerItem):
    """Focusable row for selecting a human gate."""

    def __init__(self, gate_name: str):
        super().__init__(gate_name)
        self.gate_name = gate_name

    def on_key(self, event):
        if event.key == "enter":
            self.screen.dismiss(self.gate_name)
            event.prevent_default()
            event.stop()

    def on_click(self, event):
        self.screen.dismiss(self.gate_name)


class GateChoiceScreen(ModalScreen):
    """Modal used when sign-off/fail has more than one possible gate."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, task_id: str, gates: list[str], action_label: str):
        super().__init__()
        self.task_id = task_id
        self.gates = gates
        self.action_label = action_label

    def compose(self):
        with Container(id="dep_picker_dialog", classes="picker-dialog"):
            yield Label(
                f"Select human gate to {self.action_label} for {self.task_id}:",
                id="dep_picker_title",
            )
            for gate in self.gates:
                yield GateChoiceItem(gate)
            yield Button("Cancel", id="btn_dep_cancel")

    def on_mount(self):
        items = list(self.query(GateChoiceItem))
        if items:
            items[0].focus()

    @on(Button.Pressed, "#btn_dep_cancel")
    def cancel_button(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class KanbanColumn(VerticalScroll):
    """A vertical column of tasks."""

    def __init__(self, col_id: str, title: str, color: str, manager: TaskManager,
                 expanded_tasks: set = None, collapsed: bool = False,
                 collapsed_groups: set = None):
        super().__init__()
        self.col_id = col_id
        self.col_title = title
        self.col_color = color
        self.manager = manager
        self.expanded_tasks = expanded_tasks if expanded_tasks is not None else set()
        self.collapsed = collapsed
        # Held BY REFERENCE, exactly like `expanded_tasks` above: the app mutates
        # its own set and every column sees it, so a collapse toggle needs no
        # per-column propagation — `_recompose_column` re-composes THIS instance,
        # which still points at the app's set. `collapsed_groups` is appended
        # last so no existing positional argument shifts (t1243_9).
        self.collapsed_groups = collapsed_groups if collapsed_groups is not None else set()

    def is_group_collapsed(self, slug: str) -> bool:
        """Whether `(this column, slug)` is collapsed.

        Key built by `board_groups.group_key`, never a local f-string (t1243_10):
        the same key is persisted to `settings["collapsed_groups"]` and rewritten
        by six lifecycle owners, so a second spelling here is how the runtime set
        and the on-disk list would drift apart.
        """
        return group_key(self.col_id, slug) in self.collapsed_groups

    def compose(self):
        # Header
        task_count = len(self.manager.get_column_tasks(self.col_id))
        editable = self.col_id != "unordered"
        header = ColumnHeader(self.col_id, self.col_title, task_count,
                              is_collapsed=self.collapsed, editable=editable)
        header.styles.background = self.col_color
        header.styles.color = "black"
        header.styles.width = "100%"
        header.styles.text_align = "center"
        yield header

        # Task Cards — only render when not collapsed
        if self.collapsed:
            yield CollapsedColumnPlaceholder(self.col_id)
        else:
            tasks = self.manager.get_column_tasks(self.col_id)
            # Always composed so a column emptied by the filter has a focus
            # anchor too; seeded with the right display so there is no
            # one-frame flash before apply_filter runs.
            placeholder = EmptyColumnPlaceholder(self.col_id)
            if tasks:
                placeholder.styles.display = "none"
            yield placeholder
            # Units, not bare tasks (t1243_9). `build_column_units` is the INV-R
            # derivation: it sorts by (boardidx, filename) itself, so the render
            # order is a pure function of the persisted state however this caller
            # ordered its input. Never re-derive grouping here.
            for slug, members in build_column_units(tasks):
                # A single-member group renders as a plain card. board_groups
                # deliberately KEEPS its slug (so a member moving away never
                # silently dissolves the group) and leaves the draw-a-header
                # decision to us — mirroring how `_build_topic_lanes` collapses
                # singleton lanes.
                if slug and len(members) > 1:
                    yield GroupHeader(self.col_id, slug, members,
                                      self.is_group_collapsed(slug))
                    if self.is_group_collapsed(slug):
                        # Members AND their `.child-wrapper` rows stay unmounted:
                        # `task_block` emits both, so skipping it drops both.
                        continue
                for task in members:
                    yield from self.task_block(task)

    def task_block(self, task):
        """The widgets one task contributes to this column.

        Its `TaskCard`, plus — when the parent is expanded — one
        `.child-wrapper` row per child task.

        Shared with the lateral / to-edge DOM transplant
        (`KanbanApp._transplant_block`), which mounts it through
        `mount_compose` so a moved block is built by exactly the code that
        composed it in the first place. Keeping ONE generator is what stops a
        transplanted card from drifting from a composed one.
        """
        # The ONE markable construction site in the file (t1243_6): a parent card
        # in a persistent kanban column. TopicColumn's cards, the child card
        # below, and the Trail/In-Flight subclasses all leave markable=False.
        yield TaskCard(task, self.manager, column_id=self.col_id, markable=True)
        # Render children if parent is expanded
        if task.filename in self.expanded_tasks:
            task_num, _ = TaskCard._parse_filename(task.filename)
            children = self.manager.get_child_tasks_for_parent(task_num)
            for child in children:
                with Horizontal(classes="child-wrapper"):
                    yield Static("↳", classes="child-connector")
                    yield TaskCard(child, self.manager, is_child=True, column_id=self.col_id)

    def on_mount(self):
        if self.collapsed:
            self.styles.width = 12
            self.styles.min_width = 10
        else:
            self.styles.width = 40
            self.styles.min_width = 30
        self.styles.border = ("round", self.col_color)
        self.styles.margin = (0, 1)

class CycleField(Static):
    """A focusable widget that cycles through predefined options with Left/Right keys."""

    can_focus = True

    class Changed(Message):
        """Posted when the cycle field value changes."""
        def __init__(self, field: "CycleField", value: str):
            super().__init__()
            self.field = field
            self.value = value

    def __init__(self, label: str, options: list, current: str, field_key: str,
                 id: str = None):
        super().__init__(id=id)
        self.label = label
        self.options = options
        self.field_key = field_key
        self.current_index = options.index(current) if current in options else 0

    @property
    def current_value(self) -> str:
        return self.options[self.current_index]

    def render(self) -> str:
        parts = []
        for i, opt in enumerate(self.options):
            if i == self.current_index:
                parts.append(f"[bold reverse] {opt} [/]")
            else:
                parts.append(f" {opt} ")
        options_str = " | ".join(parts)
        return f"  {self.label}:  [dim]\u25c0[/] {options_str} [dim]\u25b6[/]"

    def cycle_prev(self):
        self.current_index = (self.current_index - 1) % len(self.options)
        self.refresh()
        self.post_message(self.Changed(self, self.current_value))

    def cycle_next(self):
        self.current_index = (self.current_index + 1) % len(self.options)
        self.refresh()
        self.post_message(self.Changed(self, self.current_value))

    def _option_index_at(self, cx):
        """Map content x-coordinate to option index, -1 for left arrow, -2 for right arrow."""
        prefix_len = len(f"  {self.label}:  \u25c0 ")
        if cx == prefix_len - 2:
            return -1
        pos = prefix_len
        for i, opt in enumerate(self.options):
            opt_width = len(opt) + 2
            if pos <= cx < pos + opt_width:
                return i
            pos += opt_width
            if i < len(self.options) - 1:
                pos += 3
        if cx == pos + 1:
            return -2
        return None

    def on_click(self, event):
        """Select option directly when clicked."""
        content_offset = event.get_content_offset(self)
        if content_offset is None:
            return
        idx = self._option_index_at(content_offset.x)
        if idx == -1:
            self.cycle_prev()
        elif idx == -2:
            self.cycle_next()
        elif idx is not None and idx != self.current_index:
            self.current_index = idx
            self.refresh()
            self.post_message(self.Changed(self, self.current_value))

    def on_key(self, event):
        if event.key == "left":
            self.cycle_prev()
            event.prevent_default()
            event.stop()
        elif event.key == "right":
            self.cycle_next()
            event.prevent_default()
            event.stop()

    def on_focus(self):
        self.add_class("cycle-focused")

    def on_blur(self):
        self.remove_class("cycle-focused")


class ReadOnlyField(Static):
    """A focusable read-only metadata field with highlight on focus."""

    can_focus = True

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")


class DependsField(Static):
    """Focusable depends field. Enter opens dependency detail."""

    can_focus = True

    def __init__(self, deps: list, manager: "TaskManager", owner_task: "Task", **kwargs):
        super().__init__(**kwargs)
        self.deps = deps
        self.manager = manager
        self.owner_task = owner_task

    def render(self) -> str:
        dep_str = ", ".join(str(d) for d in self.deps)
        return f"  [b]Depends:[/b] {dep_str}"

    def on_key(self, event):
        if event.key == "enter":
            self._open_dep()
            event.prevent_default()
            event.stop()

    def _find_task_by_number(self, num):
        num_str = str(num)
        task_id = num_str if num_str.startswith('t') else f"t{num_str}"
        return self.manager.find_task_including_archived(task_id)

    def _open_dep(self):
        if len(self.deps) == 1:
            task = self._find_task_by_number(self.deps[0])
            if task:
                self.app.open_task_detail(task)
            else:
                self._ask_remove_dep(self.deps[0])
        else:
            dep_items = []
            for dep_num in self.deps:
                task = self._find_task_by_number(dep_num)
                dep_label = str(dep_num) if str(dep_num).startswith('t') else f"t{dep_num}"
                if task:
                    _, name = TaskCard._parse_filename(task.filename)
                    dep_items.append((dep_num, task, f"{dep_label} {name}"))
                else:
                    dep_items.append((dep_num, None, f"{dep_label} (not found)"))
            self.app.push_screen(
                DependencyPickerScreen(dep_items, self.manager, self.owner_task),
            )

    def _ask_remove_dep(self, dep_num):
        def on_result(remove):
            if remove:
                _remove_dep_from_task(self.owner_task, dep_num)
                _reload_detail_screen(self.app, self.owner_task, self.manager)
        self.app.push_screen(
            RemoveDepConfirmScreen(dep_num),
            on_result,
        )

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")


def _remove_dep_from_task(task, dep_num):
    """Remove a dependency number from a task's metadata and save."""
    if not task.load():  # Reload from disk to pick up external changes
        return  # File gone (archived/deleted)
    deps = task.metadata.get("depends", [])
    task.metadata["depends"] = [d for d in deps if d != dep_num]
    task.save_with_timestamp()


class VerifiesField(Static):
    """Focusable verifies field. Enter opens verified-task detail."""

    can_focus = True

    def __init__(self, verifies: list, manager: "TaskManager", owner_task: "Task", **kwargs):
        super().__init__(**kwargs)
        self.verifies = verifies
        self.manager = manager
        self.owner_task = owner_task

    def render(self) -> str:
        v_str = ", ".join(str(v) for v in self.verifies)
        return f"  [b]Verifies:[/b] {v_str}"

    def on_key(self, event):
        if event.key == "enter":
            self._open_verify()
            event.prevent_default()
            event.stop()

    def _find_task_by_number(self, num):
        num_str = str(num)
        task_id = num_str if num_str.startswith('t') else f"t{num_str}"
        return self.manager.find_task_including_archived(task_id)

    def _open_verify(self):
        if len(self.verifies) == 1:
            task = self._find_task_by_number(self.verifies[0])
            if task:
                self.app.open_task_detail(task)
            else:
                self._ask_remove_verify(self.verifies[0])
        else:
            items = []
            for v_num in self.verifies:
                task = self._find_task_by_number(v_num)
                v_label = str(v_num) if str(v_num).startswith('t') else f"t{v_num}"
                if task:
                    _, name = TaskCard._parse_filename(task.filename)
                    items.append((v_num, task, f"{v_label} {name}"))
                else:
                    items.append((v_num, None, f"{v_label} (not found)"))
            self.app.push_screen(
                DependencyPickerScreen(items, self.manager, self.owner_task),
            )

    def _ask_remove_verify(self, v_num):
        def on_result(remove):
            if remove:
                _remove_verify_from_task(self.owner_task, v_num)
                _reload_detail_screen(self.app, self.owner_task, self.manager)
        self.app.push_screen(
            RemoveDepConfirmScreen(v_num),
            on_result,
        )

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")


def _remove_verify_from_task(task, v_num):
    """Remove a verifies entry from a task's metadata and save."""
    if not task.load():
        return
    verifies = task.metadata.get("verifies", [])
    task.metadata["verifies"] = [v for v in verifies if v != v_num]
    task.save_with_timestamp()


class CrossRepoDepsField(Static):
    """Focusable cross-repo dependency field. Enter opens refs read-only."""

    can_focus = True

    def __init__(self, repo: str, xdeps: list, manager: "TaskManager", **kwargs):
        super().__init__(**kwargs)
        self.repo = repo
        self.refs = [(repo, str(xd).lstrip("t")) for xd in (xdeps or [])]
        self.manager = manager

    def render(self) -> str:
        refs = ", ".join(self._format_ref(repo, task_id) for repo, task_id in self.refs)
        return f"  [b]Cross-repo deps:[/b] ↗ {refs}"

    def _format_ref(self, repo: str, task_id: str) -> str:
        ref = f"{repo}#{task_id}"
        status = self.manager.get_xdep_status(repo, task_id)
        if status == "Done":
            return ref
        if not status or status == "NOT_FOUND":
            return f"{ref} (UNREACHABLE)"
        return f"{ref} [{status}]"

    def on_key(self, event):
        if event.key == "enter":
            self._open_ref()
            event.prevent_default()
            event.stop()

    def _open_ref(self):
        if not self.refs:
            return
        if len(self.refs) == 1:
            repo, task_id = self.refs[0]
            self.app._open_cross_repo_task(repo, task_id)
        else:
            self.app.push_screen(CrossRepoRefPickerScreen(self.refs))

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")


def _reload_detail_screen(app, task, manager):
    """Dismiss the current detail screen and re-push it with updated task data."""
    task.load()
    app.replace_screen_with_detail(task)


class ChildrenField(Static):
    """Focusable children field. Enter opens child task detail."""

    can_focus = True

    def __init__(self, children_ids: list, manager: "TaskManager",
                 owner_task: "Task", **kwargs):
        super().__init__(**kwargs)
        self.children_ids = children_ids
        self.manager = manager
        self.owner_task = owner_task

    def render(self) -> str:
        children_str = ", ".join(str(c) for c in self.children_ids)
        return f"  [b]Children:[/b] {children_str}"

    def on_key(self, event):
        if event.key == "enter":
            self._open_child()
            event.prevent_default()
            event.stop()

    def _find_task_by_number(self, num):
        num_str = str(num)
        task_id = num_str if num_str.startswith('t') else f"t{num_str}"
        return self.manager.find_task_including_archived(task_id)

    def _open_child(self):
        if len(self.children_ids) == 1:
            task = self._find_task_by_number(self.children_ids[0])
            if task:
                self.app.open_task_detail(task)
        else:
            child_items = []
            for child_id in self.children_ids:
                child_id_str = str(child_id)
                task = self._find_task_by_number(child_id_str)
                if task:
                    _, name = TaskCard._parse_filename(task.filename)
                    child_items.append((child_id_str, task, f"{child_id_str} {name}"))
                else:
                    child_items.append((child_id_str, None, f"{child_id_str} (not found)"))
            self.app.push_screen(
                ChildPickerScreen(child_items, self.manager),
            )

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")


class FoldedTasksField(Static):
    """Focusable folded tasks field. Enter opens folded task detail (read-only)."""

    can_focus = True

    def __init__(self, folded_ids: list, manager: "TaskManager",
                 owner_task: "Task", **kwargs):
        super().__init__(**kwargs)
        self.folded_ids = folded_ids
        self.manager = manager
        self.owner_task = owner_task

    def render(self) -> str:
        folded_str = ", ".join(str(f) for f in self.folded_ids)
        return f"  [b]Folded Tasks:[/b] {folded_str}"

    def on_key(self, event):
        if event.key == "enter":
            self._open_folded()
            event.prevent_default()
            event.stop()

    def _open_folded(self):
        if len(self.folded_ids) == 1:
            task_id = str(self.folded_ids[0])
            tid = task_id if task_id.startswith('t') else f"t{task_id}"
            task = self.manager.find_task_including_archived(tid)
            if task:
                self.app.open_task_detail(task, read_only=True)
        else:
            folded_items = []
            for fid in self.folded_ids:
                fid_str = str(fid)
                tid = fid_str if fid_str.startswith('t') else f"t{fid_str}"
                task = self.manager.find_task_including_archived(tid)
                if task:
                    _, name = TaskCard._parse_filename(task.filename)
                    folded_items.append((fid_str, task, f"{tid} {name}"))
                else:
                    folded_items.append((fid_str, None, f"{tid} (not found)"))
            self.app.push_screen(
                FoldedTaskPickerScreen(folded_items, self.manager),
            )

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")


class AnchorEditScreen(ModalScreen):
    """Modal to edit a task's topic anchor (group key). Empty value clears it.

    Models RenameTaskScreen — reuses the shared #rename_dialog / #detail_buttons
    styling. Dismisses with the typed value (possibly empty) or None on cancel.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, task_num: str, current_anchor: str):
        super().__init__()
        self.task_num = task_num
        self.current_anchor = current_anchor

    def compose(self):
        with Container(id="rename_dialog"):
            yield Label(f"Set topic anchor for {self.task_num}", id="rename_title")
            yield Label("Root task id (e.g. 130 or 130_2). Empty clears the anchor.")
            yield Input(value=self.current_anchor, id="anchor_input",
                        placeholder="topic root id", select_on_focus=False)
            with Horizontal(id="detail_buttons"):
                yield Button("Save", variant="success", id="btn_do_anchor")
                yield Button("Cancel", variant="default", id="btn_anchor_cancel")

    @on(Button.Pressed, "#btn_do_anchor")
    def do_anchor(self):
        self.dismiss(self.query_one("#anchor_input", Input).value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.do_anchor()

    @on(Button.Pressed, "#btn_anchor_cancel")
    def cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class AnchorField(Static):
    """Focusable, editable topic-anchor field. Enter edits the anchor (group key).

    Persists by shelling out to ``aitask_update.sh --batch <id> --anchor <val>``
    (the mandated new-field board pattern, NOT the CycleField save_with_timestamp
    path), then reloads the detail screen. Shown even when unset so a root task
    can be given an anchor; rendered read-only via the screen's read_only flag.
    """

    can_focus = True

    def __init__(self, anchor, manager: "TaskManager", owner_task: "Task",
                 read_only: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.anchor = anchor  # bare id string, or None when unset
        self.manager = manager
        self.owner_task = owner_task
        self.read_only = read_only

    def render(self) -> str:
        shown = f"t{self.anchor}" if self.anchor else "[dim](none)[/dim]"
        hint = "" if self.read_only else "  [dim](enter to edit)[/dim]"
        return f"  [b]Anchor:[/b] {shown}{hint}"

    def on_key(self, event):
        if event.key == "enter" and not self.read_only:
            self._edit()
            event.prevent_default()
            event.stop()

    def _edit(self):
        task_num, _ = TaskCard._parse_filename(self.owner_task.filename)

        def on_result(new_value):
            if new_value is None:
                return  # cancelled
            self._apply(task_num.lstrip("t"), new_value.strip())

        self.app.push_screen(
            AnchorEditScreen(task_num, self.anchor or ""), on_result)

    def _apply(self, task_num_bare: str, new_anchor: str):
        result = subprocess.run(
            ["./.aitask-scripts/aitask_update.sh", "--batch", task_num_bare,
             "--anchor", new_anchor, "--silent"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            error = (result.stderr.strip() or result.stdout.strip()
                     or "anchor update failed")
            self.app.notify(error, severity="error")
            return
        _reload_detail_screen(self.app, self.owner_task, self.manager)

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")


class FollowupKindPickerItem(PickerItem):
    """Focusable row for one follow-up kind -- or for clearing the field.

    ``kind`` is the value that will be persisted: a vocabulary key, or ``""``
    for the clear row. Dismisses the SCREEN, not itself (mirrors
    ``GateChoiceItem``) -- a row that dismissed itself would leave the modal
    standing.

    Deliberately does NOT define ``on_focus`` / ``on_blur``: ``PickerItem``
    owns the focus-visibility contract and Textual dispatches handlers down the
    MRO, so both would fire.
    """

    def __init__(self, kind: str, current: bool):
        super().__init__()
        self.kind = kind
        self.current = current

    def render(self) -> Text:
        out = Text("✓ " if self.current else "  ")
        if not self.kind:
            out.append("(none) — not a follow-up")
            return out
        out.append_text(_followup_glyph_text(marker_for(self.kind)))
        out.append(f" {label_for(self.kind)}  ")
        out.append(self.kind, style="dim")   # raw key, for CLI correlation
        return out

    def on_key(self, event):
        if event.key == "enter":
            self.screen.dismiss(self.kind)
            event.prevent_default()
            event.stop()

    def on_click(self, event):
        self.screen.dismiss(self.kind)


class FollowupKindPickerScreen(ModalScreen):
    """Pick a task's follow-up kind, or clear it (t1468_8).

    Dismisses with the value to persist -- a vocabulary key, or ``""`` to clear
    (key removal; there is no tombstone) -- or ``None`` on cancel. ``""`` and
    ``None`` are therefore NOT interchangeable: the caller must test
    ``is None``, not falsiness, or every cancel would silently clear the field.

    **An unrecognised current value focuses Cancel, not a row.** A hand-edited
    or future-vocabulary kind matches no row, and the clear row would otherwise
    take default focus -- making one reflexive `Enter` delete the very value the
    user opened this dialog to diagnose. The title names the value instead.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, task_num: str, current_kind: str):
        super().__init__()
        self.task_num = task_num
        self.current_kind = current_kind
        # Present but outside the vocabulary. A direct membership test against
        # the canonical map -- not a second copy of the rule.
        self.unrecognised = bool(current_kind) and current_kind not in FOLLOWUP_KINDS

    def compose(self):
        with Container(id="dep_picker_dialog", classes="picker-dialog"):
            # A `Text`, never a markup string: `current_kind` is hand-editable
            # frontmatter, so `followup_kind: "[bold]x"` would otherwise be
            # markup-parsed by Label (markup=True is the default) -- silently
            # swallowed at best, a markup error at worst.
            title = Text(f"Set follow-up kind for {self.task_num}:")
            if self.unrecognised:
                title.append("  current value ")
                title.append(self.current_kind, style="bold")
                title.append(" is not a recognised kind")
            yield Label(title, id="dep_picker_title")
            # Clear row first: the common correction after the t1468_6
            # heuristic backfill is "this isn't a follow-up at all".
            yield FollowupKindPickerItem("", not self.current_kind)
            for kind in FOLLOWUP_KINDS:          # canonical declaration order
                yield FollowupKindPickerItem(kind, kind == self.current_kind)
            yield Button("Cancel", id="btn_dep_cancel")

    def on_mount(self):
        if self.unrecognised:
            # Safe default: Enter presses Cancel -> dismiss(None) -> no write.
            self.query_one("#btn_dep_cancel", Button).focus()
            return
        items = list(self.query(FollowupKindPickerItem))
        current = [it for it in items if it.current]
        (current[0] if current else items[0]).focus()

    @on(Button.Pressed, "#btn_dep_cancel")
    def cancel_button(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class FollowupKindField(Static):
    """Focusable follow-up-provenance field. Enter opens the kind picker.

    Persists by shelling out to
    ``aitask_update.sh --batch <id> --followup-kind <val> --silent`` -- the
    mandated new-field board pattern (see ``AnchorField``), NOT the CycleField
    ``save_with_timestamp`` path. Three consequences, all load-bearing:

    * **Clearing is key removal.** ``--followup-kind ""`` makes the shell's
      emit skip the line; there is no tombstone. ``save_changes`` can only ever
      *assign*, and an assigned ``""`` would round-trip back through
      ``normalize_followup_kind`` as a present-but-unrecognised kind, painting
      the `·` fallback on every task the user had just cleared.
    * **The screen cannot go dirty on open.** This field is deliberately absent
      from ``TaskDetailScreen._original_values`` / ``_current_values``, so
      opening a task that has no ``followup_kind`` cannot light up the Save
      button. A seeded default in that dict -- the shape the other four
      editable fields use -- would do exactly that, because this field is
      legitimately absent on most tasks.
    * **The write is immediate, so it is blocked while the screen is dirty.**
      Success calls ``_reload_detail_screen``, which REPLACES the screen with a
      fresh instance and therefore discards any pending CycleField edit.
      ``blocked`` is pushed in by ``TaskDetailScreen._update_save_button``; when
      set, the hint says so and ``Enter`` notifies the remedy instead of
      opening the picker.

    The ``manual_verification`` cross-field invariant (that kind requires
    ``issue_type: manual_verification``) is enforced by the shell and its
    message surfaced verbatim. It is deliberately NOT re-declared here: a copy
    in the board would be a second authority over a rule the CLI already owns.
    """

    can_focus = True

    def __init__(self, kind, manager: "TaskManager", owner_task: "Task",
                 read_only: bool = False, **kwargs):
        super().__init__(**kwargs)
        # Normalised once: frontmatter is type-honest, so a hand-edited list,
        # int or bool arrives here verbatim. "" means "not a follow-up".
        self.kind = normalize_followup_kind(kind)
        self.manager = manager
        self.owner_task = owner_task
        self.read_only = read_only
        self.blocked = False

    def set_blocked(self, blocked: bool) -> None:
        """Called by the screen when its unsaved-edit state changes."""
        if blocked != self.blocked:
            self.blocked = blocked
            self.refresh()

    def render(self) -> Text:
        out = Text("  ")
        out.append("Follow-up:", style="bold")
        out.append(" ")
        marker = marker_for(self.kind)
        if not marker:
            out.append("(none)", style="dim")
        else:
            out.append_text(_followup_glyph_text(marker))
            out.append(" ")
            # `label_for` answers "" for an unrecognised kind; show the raw
            # value then, so a typo is diagnosable from the screen that can fix
            # it. The glyph is already the `·` fallback -- the same
            # degradation the card shows.
            out.append(label_for(self.kind) or self.kind)
        if self.read_only:
            return out
        if self.blocked:
            out.append("  (save or revert pending edits first)", style="dim")
        else:
            out.append("  (enter to change)" if marker else "  (enter to set)",
                       style="dim")
        return out

    def on_key(self, event):
        if event.key != "enter" or self.read_only:
            return
        event.prevent_default()
        event.stop()
        if self.blocked:
            self.app.notify(
                "Save or revert your pending changes first — setting a "
                "follow-up kind writes immediately and reloads this screen.",
                severity="warning")
            return
        self._edit()

    def _edit(self):
        task_num, _ = TaskCard._parse_filename(self.owner_task.filename)

        def on_result(new_kind):
            # `is None` is cancel; `""` is an intentional clear. Testing
            # falsiness here would turn every Escape into a clear.
            if new_kind is None or new_kind == self.kind:
                return
            self._apply(task_num.lstrip("t"), new_kind)

        self.app.push_screen(
            FollowupKindPickerScreen(task_num, self.kind), on_result)

    def _apply(self, task_num_bare: str, new_kind: str):
        result = subprocess.run(
            ["./.aitask-scripts/aitask_update.sh", "--batch", task_num_bare,
             "--followup-kind", new_kind, "--silent"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            error = (result.stderr.strip() or result.stdout.strip()
                     or "followup_kind update failed")
            self.app.notify(error, severity="error")
            return
        _reload_detail_screen(self.app, self.owner_task, self.manager)

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")


def _current_tmux_session() -> str | None:
    """Return the current tmux session name, or None if not in tmux."""
    try:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "#S"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            name = result.stdout.strip()
            return name or None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


class FileReferencesField(Static):
    """Focusable, read-only file_references field.

    Enter navigates to the entry in codebrowser (picker if multi).
    No add/remove keybindings — use aitask_update.sh --file-ref /
    --remove-file-ref or the codebrowser create-task flow instead.
    """

    can_focus = True

    def __init__(self, file_refs: list, manager: "TaskManager",
                 owner_task: "Task", **kwargs):
        super().__init__(**kwargs)
        self.file_refs = list(file_refs or [])
        self.manager = manager
        self.owner_task = owner_task

    def render(self) -> str:
        if not self.file_refs:
            return "  [b]File Refs:[/b] [dim](none)[/dim]"
        return f"  [b]File Refs:[/b] {', '.join(self.file_refs)}"

    def on_key(self, event):
        if event.key == "enter":
            self._navigate()
            event.prevent_default()
            event.stop()

    def _navigate(self):
        if not self.file_refs:
            return
        if len(self.file_refs) == 1:
            self._launch_codebrowser(self.file_refs[0])
        else:
            def on_picked(entry):
                if entry:
                    self._launch_codebrowser(entry)
            self.app.push_screen(
                FileReferencePickerScreen(self.file_refs),
                on_picked,
            )

    def _launch_codebrowser(self, entry: str):
        session = _current_tmux_session()
        if not session:
            self.app.notify(
                "Codebrowser focus requires tmux", severity="warning")
            return
        ok, err = launch_or_focus_codebrowser(session, entry)
        if not ok:
            self.app.notify(
                f"Codebrowser launch failed: {err}", severity="error")

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")


class FoldedIntoField(Static):
    """Focusable folded_into field. Enter opens the target task detail."""

    can_focus = True

    def __init__(self, target_num: str, manager: "TaskManager", **kwargs):
        super().__init__(**kwargs)
        self.target_num = target_num
        self.manager = manager

    def render(self) -> str:
        return f"  [b]Folded Into:[/b] t{self.target_num}"

    def on_key(self, event):
        if event.key == "enter":
            self._open_target()
            event.prevent_default()
            event.stop()

    def _open_target(self):
        tid = f"t{self.target_num}" if not str(self.target_num).startswith('t') else str(self.target_num)
        task = self.manager.find_task_including_archived(tid)
        if task:
            self.app.open_task_detail(task)

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")


class ParentField(Static):
    """Focusable parent field. Enter opens parent task detail."""

    can_focus = True

    def __init__(self, parent_num: str, manager: "TaskManager", **kwargs):
        super().__init__(**kwargs)
        self.parent_num = parent_num
        self.manager = manager

    def render(self) -> str:
        return f"  [b]Parent:[/b] {self.parent_num}"

    def on_key(self, event):
        if event.key == "enter":
            self._open_parent()
            event.prevent_default()
            event.stop()

    def _open_parent(self):
        task = self.manager.find_task_including_archived(self.parent_num)
        if task:
            self.app.open_task_detail(task)

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")


class IssueField(Static):
    """Focusable issue URL field. Press Enter to open in browser."""

    can_focus = True

    def __init__(self, url: str, **kwargs):
        super().__init__(**kwargs)
        self.url = url

    def render(self) -> str:
        return f"  [b]Issue:[/b] {self.url}  [dim](Enter to open)[/dim]"

    def on_key(self, event):
        if event.key == "enter":
            import webbrowser
            webbrowser.open(self.url)
            event.prevent_default()
            event.stop()

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")


class PullRequestField(Static):
    """Focusable pull request URL field. Press Enter to open in browser."""

    can_focus = True

    def __init__(self, url: str, **kwargs):
        super().__init__(**kwargs)
        self.url = url

    def render(self) -> str:
        indicator = _pr_indicator(self.url)
        return f"  [b]Pull Request:[/b] {indicator} {self.url}  [dim](Enter to open)[/dim]"

    def on_key(self, event):
        if event.key == "enter":
            import webbrowser
            webbrowser.open(self.url)
            event.prevent_default()
            event.stop()

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")


class RemoveDepConfirmScreen(ModalScreen):
    """Confirmation dialog to remove a missing dependency."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, dep_num):
        super().__init__()
        self.dep_num = dep_num

    def compose(self):
        dep_label = str(self.dep_num) if str(self.dep_num).startswith('t') else f"t{self.dep_num}"
        with Container(id="dep_picker_dialog"):
            yield Label(
                f"Task {dep_label} not found (may be archived).\n"
                f"Remove this dependency?",
                id="dep_picker_title",
            )
            with Horizontal(id="detail_buttons"):
                yield Button("Remove", variant="warning", id="btn_remove_dep")
                yield Button("Cancel", variant="default", id="btn_cancel_dep")

    @on(Button.Pressed, "#btn_remove_dep")
    def confirm_remove(self):
        self.dismiss(True)

    @on(Button.Pressed, "#btn_cancel_dep")
    def cancel_remove(self):
        self.dismiss(False)

    def action_cancel(self):
        self.dismiss(False)


class DeleteConfirmScreen(ModalScreen):
    """Confirmation dialog to delete a task and associated files."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, files_to_delete: list):
        super().__init__()
        self.files_to_delete = files_to_delete

    def compose(self):
        file_list = "\n".join(f"  - {f}" for f in self.files_to_delete)
        with Container(id="dep_picker_dialog"):
            yield Label(
                f"Delete these files?\n{file_list}\n\nThis cannot be undone.",
                id="dep_picker_title",
            )
            with Horizontal(id="detail_buttons"):
                yield Button("Delete", variant="error", id="btn_confirm_delete")
                yield Button("Cancel", variant="default", id="btn_cancel_delete")

    @on(Button.Pressed, "#btn_confirm_delete")
    def confirm_delete(self):
        self.dismiss(True)

    @on(Button.Pressed, "#btn_cancel_delete")
    def cancel_delete(self):
        self.dismiss(False)

    def action_cancel(self):
        self.dismiss(False)


class DeleteArchiveConfirmScreen(ModalScreen):
    """Confirmation dialog offering Delete or Archive for a task.

    Renders explicit ARCHIVED / DELETED sections so the user can see exactly
    what each button will do — never just a flat "files affected" list.
    Disables the Archive button when blocking children prevent a cascade.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, task_name: str,
                 delete_files: list,
                 archive_kept: list,
                 archive_deleted: list,
                 dep_warnings: list,
                 related_tasks: list,
                 is_child: bool,
                 blocking_files: list = None,
                 blocked_reason: str | None = None):
        super().__init__()
        self.task_name = task_name
        self.delete_files = delete_files or []
        self.archive_kept = archive_kept or []
        self.archive_deleted = archive_deleted or []
        self.dep_warnings = dep_warnings or []
        self.related_tasks = related_tasks or []
        self.is_child = is_child
        self.blocking_files = blocking_files or []
        self.blocked_reason = blocked_reason

    @staticmethod
    def _format_section(title: str, items: list) -> list[str]:
        if not items:
            return []
        out = [title]
        for path, annotation in items:
            if annotation:
                out.append(f"    {path}    [{annotation}]")
            else:
                out.append(f"    {path}")
        return out

    def compose(self):
        lines: list[str] = []

        if self.blocked_reason:
            lines.append(f"[!] {self.blocked_reason}")
            lines.append("")

        if self.dep_warnings:
            lines.append("[!] Explicit dependencies found:")
            for w in self.dep_warnings:
                lines.append(f"    {w}")
        else:
            lines.append("[ok] No explicit dependencies found.")
        lines.append("")

        if self.related_tasks:
            label = "Sibling" if self.is_child else "Related"
            lines.append(f"{label} tasks — please verify no implicit dependencies:")
            for t in self.related_tasks:
                lines.append(f"    {t}")
            lines.append("")

        lines.append("On Delete:")
        if self.delete_files:
            lines.extend(self._format_section("  Files to remove:", self.delete_files))
        else:
            lines.append("  (nothing to remove)")
        lines.append("")

        lines.append("On Archive:")
        if self.blocked_reason:
            lines.append(f"  [!] {self.blocked_reason}")
            if self.blocking_files:
                lines.extend(self._format_section("  Blocking children:", self.blocking_files))
        else:
            if self.archive_kept:
                lines.extend(self._format_section(
                    "  Will be ARCHIVED (moved to archived/):", self.archive_kept))
            if self.archive_deleted:
                lines.extend(self._format_section(
                    "  Will be DELETED (cascade cleanup):", self.archive_deleted))
            if not self.archive_kept and not self.archive_deleted:
                lines.append("  (nothing to archive)")

        with Container(id="dep_picker_dialog"):
            yield Label(
                f"Delete or Archive '{self.task_name}'?\n\n" + "\n".join(lines),
                id="delarch_label",
            )
            with Horizontal(id="detail_buttons"):
                yield Button("Delete", variant="error", id="btn_do_delete")
                archive_btn = Button("Archive", variant="warning", id="btn_do_archive")
                if self.blocked_reason:
                    archive_btn.disabled = True
                yield archive_btn
                yield Button("Cancel", variant="default", id="btn_do_cancel")

    @on(Button.Pressed, "#btn_do_delete")
    def do_delete(self):
        self.dismiss("delete")

    @on(Button.Pressed, "#btn_do_archive")
    def do_archive(self):
        if self.blocked_reason:
            self.app.notify(self.blocked_reason, severity="warning")
            return
        self.dismiss("archive")

    @on(Button.Pressed, "#btn_do_cancel")
    def do_cancel(self):
        self.dismiss("cancel")

    def action_cancel(self):
        self.dismiss("cancel")


class OrphanParentArchiveScreen(ModalScreen):
    """Prompt to archive a parent task that has just become orphaned (its
    last pending child was deleted). Lists the parent file and plan that
    will be moved to archived/."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, parent_name: str, parent_status: str,
                 archive_kept: list):
        super().__init__()
        self.parent_name = parent_name
        self.parent_status = parent_status
        self.archive_kept = archive_kept or []

    def compose(self):
        lines = [
            f"Parent '{self.parent_name}' has no more pending children.",
            "",
            "Will be ARCHIVED (moved to archived/):",
        ]
        for path, annotation in self.archive_kept:
            if annotation:
                lines.append(f"    {path}    [{annotation}]")
            else:
                lines.append(f"    {path}")
        lines.append("")
        lines.append("Archive it as completed now?")

        with Container(id="dep_picker_dialog"):
            yield Label("\n".join(lines), id="orphan_parent_label")
            with Horizontal(id="detail_buttons"):
                yield Button("Yes, archive parent", variant="warning", id="btn_orphan_yes")
                yield Button("No, leave it", variant="default", id="btn_orphan_no")

    @on(Button.Pressed, "#btn_orphan_yes")
    def confirm(self):
        self.dismiss(True)

    @on(Button.Pressed, "#btn_orphan_no")
    def decline(self):
        self.dismiss(False)

    def action_cancel(self):
        self.dismiss(False)


class DepPickerItem(PickerItem):
    """A selectable dependency item in the picker."""

    def __init__(self, dep_num, task, display_name, manager, owner_task, **kwargs):
        super().__init__(**kwargs)
        self.dep_num = dep_num
        self.dep_task = task
        self.display_name = display_name
        self.manager = manager
        self.owner_task = owner_task

    def render(self) -> str:
        return f"  {self.display_name}"

    def on_key(self, event):
        if event.key == "enter":
            if self.dep_task:
                self.app.replace_screen_with_detail(self.dep_task)
            else:
                self._ask_remove_dep()
            event.prevent_default()
            event.stop()

    def _ask_remove_dep(self):
        def on_result(remove):
            if remove:
                _remove_dep_from_task(self.owner_task, self.dep_num)
                # Close picker, then reload the detail screen
                self.screen.dismiss()
                _reload_detail_screen(self.app, self.owner_task, self.manager)
        self.app.push_screen(
            RemoveDepConfirmScreen(self.dep_num),
            on_result,
        )


class DependencyPickerScreen(ModalScreen):
    """Popup to select which dependency to open."""

    BINDINGS = [
        Binding("escape", "close_picker", "Close", show=False),
    ]

    def __init__(self, dep_items, manager, owner_task):
        super().__init__()
        self.dep_items = dep_items
        self.manager = manager
        self.owner_task = owner_task

    def compose(self):
        with Container(id="dep_picker_dialog", classes="picker-dialog"):
            yield Label("Select dependency to open:", id="dep_picker_title")
            for dep_num, task, display_name in self.dep_items:
                yield DepPickerItem(dep_num, task, display_name, self.manager, self.owner_task)
            yield Button("Cancel", variant="default", id="btn_dep_cancel")

    @on(Button.Pressed, "#btn_dep_cancel")
    def cancel(self):
        self.dismiss()

    def action_close_picker(self):
        self.dismiss()


def _read_cross_repo_task_content(root: Path, tid: str) -> str | None:
    """Return the task text for ``tid`` under ``root`` — active tasks first,
    then the repo's archive store — or ``None`` if absent.

    Mirrors ``TaskManager.find_task_including_archived`` (the same-repo path
    fixed in t992) so an archived cross-repo dependency resolves too. Raises
    ``OSError`` only when an existing *active* file cannot be read; archive
    misses are swallowed by ``find_archived_markdown_by_id`` (returns None).
    """
    if "_" in tid:
        parent = tid.split("_")[0]
        matches = sorted((root / "aitasks" / f"t{parent}").glob(f"t{tid}_*.md"))
    else:
        matches = sorted((root / "aitasks").glob(f"t{tid}_*.md"))
    if matches:
        return matches[0].read_text(encoding="utf-8")
    archived = find_archived_markdown_by_id(tid, root / "aitasks" / "archived")
    if archived:
        return archived[1]
    return None


def _resolve_cross_repo_task(repo: str, task_id: str):
    """Resolve a ``<repo>#<id>`` reference to ``(title, content, is_error)``.

    Read-only: resolves the project root via ``aitask_project_resolve.sh``
    and reads the task file directly — it acquires NO lock and runs no pick
    flow. On any failure (unregistered/stale project, missing task, read
    error) it returns ``is_error=True`` with a human-readable message so the
    popup shows the error instead of crashing the board.
    """
    tid = task_id.lstrip("t")
    title = f"↗ {repo}#{tid}"
    try:
        result = subprocess.run(
            ["./.aitask-scripts/aitask_project_resolve.sh", repo],
            capture_output=True, text=True, timeout=10
        )
        out = result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return (title, f"Could not resolve project '{repo}': {e}", True)

    if out.startswith("RESOLVED:"):
        root = Path(out[len("RESOLVED:"):])
    elif out.startswith("STALE:"):
        return (title,
                f"Project '{repo}' is registered but its path is stale "
                f"(missing aitasks/metadata). Fix it with `ait projects`.",
                True)
    elif out.startswith("NOT_FOUND:"):
        return (title,
                f"Project '{repo}' is not registered. Add it with "
                f"`ait projects add`.",
                True)
    else:
        return (title, f"Unexpected resolver output for '{repo}': {out}", True)

    # Locate the task file under the resolved root: active tasks first, then
    # the repo's archive store (mirrors find_task_including_archived for
    # same-repo deps, t992 — so an archived cross-repo dep resolves instead of
    # showing UNREACHABLE).
    try:
        content = _read_cross_repo_task_content(root, tid)
    except OSError as e:
        return (title, f"Could not read task file: {e}", True)
    if content is None:
        return (title, f"Task t{tid} not found in project '{repo}'.", True)
    return (title, content, False)


class CrossRepoRefItem(Static):
    """A selectable cross-repo reference in the picker."""

    can_focus = True

    def __init__(self, repo, task_id, **kwargs):
        super().__init__(**kwargs)
        self.repo = repo
        self.task_id = task_id

    def render(self) -> str:
        return f"  ↗ {self.repo}#{self.task_id}"

    def on_key(self, event):
        if event.key == "enter":
            repo, task_id, app = self.repo, self.task_id, self.app
            self.screen.dismiss()
            app._open_cross_repo_task(repo, task_id)
            event.prevent_default()
            event.stop()

    def on_focus(self):
        self.add_class("xrepo-item-focused")

    def on_blur(self):
        self.remove_class("xrepo-item-focused")


class CrossRepoRefPickerScreen(ModalScreen):
    """Popup to select which cross-repo reference to open (read-only)."""

    DEFAULT_CSS = """
    CrossRepoRefPickerScreen { align: center middle; }
    #xrepo_picker_dialog {
        width: 60%;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #xrepo_picker_title { text-align: center; padding: 0 0 1 0; }
    CrossRepoRefItem { height: 1; width: 100%; padding: 0 1; }
    CrossRepoRefItem.xrepo-item-focused {
        background: $primary 20%;
        border-left: thick $accent;
    }
    #btn_xrepo_cancel { margin: 1 0 0 0; }
    """

    BINDINGS = [
        Binding("escape", "close_picker", "Close", show=False),
    ]

    def __init__(self, refs):
        super().__init__()
        self._refs = refs

    def compose(self):
        with Container(id="xrepo_picker_dialog"):
            yield Label("Select cross-repo reference to open:", id="xrepo_picker_title")
            for repo, task_id in self._refs:
                yield CrossRepoRefItem(repo, task_id)
            yield Button("Cancel", variant="default", id="btn_xrepo_cancel")

    @on(Button.Pressed, "#btn_xrepo_cancel")
    def cancel(self):
        self.dismiss()

    def action_close_picker(self):
        self.dismiss()


class CrossRepoTaskScreen(ModalScreen):
    """Read-only popup showing a cross-repo task's content (no lock).

    Self-contained DEFAULT_CSS so it renders consistently regardless of the
    App-level stylesheet.
    """

    DEFAULT_CSS = """
    CrossRepoTaskScreen { align: center middle; }
    #xrepo_dialog {
        width: 80%;
        height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #xrepo_title {
        dock: top;
        text-align: center;
        background: $secondary;
        color: $text;
        padding: 1;
    }
    #xrepo_view { margin: 1 0; border: solid $secondary-background; }
    #xrepo_meta {
        padding: 0 1 1 1;
        color: $text-muted;
        border-bottom: solid $secondary-background;
    }
    #xrepo_error { padding: 1 2; color: $warning; }
    #xrepo_buttons { dock: bottom; height: 3; align: center middle; }
    """

    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
        Binding("c", "close", "Close", show=False),
        Binding("C", "close", "Close", show=False),
    ]

    def __init__(self, title: str, content: str, is_error: bool = False):
        super().__init__()
        self._title = title
        self._content = content
        self._is_error = is_error
        self._metadata = {}
        self._metadata_order = []
        self._body = content
        if not is_error:
            parsed = parse_frontmatter(content)
            if parsed:
                self._metadata, self._body, self._metadata_order = parsed

    def _format_metadata(self) -> str:
        lines = []
        for key in self._metadata_order:
            value = self._metadata.get(key)
            if value in (None, "", []):
                continue
            if isinstance(value, list):
                value = ", ".join(str(item) for item in value)
            lines.append(f"[b]{escape(str(key))}:[/b] {escape(str(value))}")
        return "\n".join(lines)

    def compose(self):
        with Container(id="xrepo_dialog"):
            yield Label(self._title, id="xrepo_title")
            with VerticalScroll(id="xrepo_view"):
                if self._is_error:
                    yield Static(self._content, id="xrepo_error")
                else:
                    if self._metadata:
                        yield Static(self._format_metadata(), id="xrepo_meta")
                    yield Markdown(self._body)
            with Horizontal(id="xrepo_buttons"):
                yield Button("Close", variant="default", id="btn_xrepo_close")

    @on(Button.Pressed, "#btn_xrepo_close")
    def _on_close(self):
        self.dismiss()

    def action_close(self):
        self.dismiss()


class ChildPickerItem(PickerItem):
    """A selectable child task item in the picker."""

    def __init__(self, child_id, task, display_name, manager, **kwargs):
        super().__init__(**kwargs)
        self.child_id = child_id
        self.child_task = task
        self.display_name = display_name
        self.manager = manager

    def render(self) -> str:
        return f"  {self.display_name}"

    def on_key(self, event):
        if event.key == "enter":
            if self.child_task:
                self.app.replace_screen_with_detail(self.child_task)
            event.prevent_default()
            event.stop()


class ChildPickerScreen(ModalScreen):
    """Popup to select which child task to open."""

    BINDINGS = [
        Binding("escape", "close_picker", "Close", show=False),
    ]

    def __init__(self, child_items, manager):
        super().__init__()
        self.child_items = child_items
        self.manager = manager

    def compose(self):
        with Container(id="dep_picker_dialog", classes="picker-dialog"):
            yield Label("Select child task to open:", id="dep_picker_title")
            for child_id, task, display_name in self.child_items:
                yield ChildPickerItem(child_id, task, display_name, self.manager)
            yield Button("Cancel", variant="default", id="btn_dep_cancel")

    @on(Button.Pressed, "#btn_dep_cancel")
    def cancel(self):
        self.dismiss()

    def action_close_picker(self):
        self.dismiss()


class FoldedTaskPickerItem(PickerItem):
    """A selectable folded task item in the picker."""

    def __init__(self, folded_id, task, display_name, manager, **kwargs):
        super().__init__(**kwargs)
        self.folded_id = folded_id
        self.folded_task = task
        self.display_name = display_name
        self.manager = manager

    def render(self) -> str:
        return f"  {self.display_name}"

    def on_key(self, event):
        if event.key == "enter":
            if self.folded_task:
                self.app.replace_screen_with_detail(self.folded_task, read_only=True)
            event.prevent_default()
            event.stop()


class FoldedTaskPickerScreen(ModalScreen):
    """Popup to select which folded task to open."""

    BINDINGS = [
        Binding("escape", "close_picker", "Close", show=False),
    ]

    def __init__(self, folded_items, manager):
        super().__init__()
        self.folded_items = folded_items
        self.manager = manager

    def compose(self):
        with Container(id="dep_picker_dialog", classes="picker-dialog"):
            yield Label("Select folded task to open:", id="dep_picker_title")
            for folded_id, task, display_name in self.folded_items:
                yield FoldedTaskPickerItem(folded_id, task, display_name,
                                           self.manager)
            yield Button("Cancel", variant="default", id="btn_dep_cancel")

    @on(Button.Pressed, "#btn_dep_cancel")
    def cancel(self):
        self.dismiss()

    def action_close_picker(self):
        self.dismiss()


class FileReferenceItem(PickerItem):
    """A selectable file-reference entry in the picker."""

    def __init__(self, entry: str, **kwargs):
        super().__init__(**kwargs)
        self.entry = entry

    def render(self) -> str:
        return f"  {self.entry}"

    def on_key(self, event):
        if event.key == "enter":
            self.screen.dismiss(self.entry)
            event.prevent_default()
            event.stop()


class FileReferencePickerScreen(ModalScreen):
    """Popup to select which file_references entry to open."""

    BINDINGS = [
        Binding("escape", "close_picker", "Close", show=False),
    ]

    def __init__(self, entries: list):
        super().__init__()
        self.entries = list(entries)

    def compose(self):
        with Container(id="dep_picker_dialog", classes="picker-dialog"):
            yield Label(
                "Select file reference to open:", id="dep_picker_title")
            for entry in self.entries:
                yield FileReferenceItem(entry)
            yield Button("Cancel", variant="default", id="btn_dep_cancel")

    @on(Button.Pressed, "#btn_dep_cancel")
    def cancel(self):
        self.dismiss(None)

    def action_close_picker(self):
        self.dismiss(None)


class IssueTypeFilterScreen(ModalScreen):
    """Modal dialog to multi-select which issue types to show on the board."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, task_types: list, initial: list):
        super().__init__()
        self.task_types = list(task_types)
        self.initial = set(initial)

    def compose(self):
        with Container(id="dep_picker_dialog"):
            yield Label(
                "Filter by issue type — [dim]space to toggle, Enter to confirm, Esc to cancel[/]",
                id="dep_picker_title",
            )
            yield SelectionList[str](
                *(
                    Selection(t, value=t, initial_state=(t in self.initial))
                    for t in self.task_types
                ),
                id="issue_type_filter_list",
            )
            with Horizontal(id="detail_buttons"):
                yield Button("Confirm", variant="primary", id="btn_type_filter_save")
                yield Button("Cancel", variant="default", id="btn_type_filter_cancel")

    def on_mount(self):
        self.query_one("#issue_type_filter_list", SelectionList).focus()

    def _selected(self) -> list:
        sl = self.query_one("#issue_type_filter_list", SelectionList)
        checked = set(sl.selected)
        return [t for t in self.task_types if t in checked]

    @on(Button.Pressed, "#btn_type_filter_save")
    def _btn_save(self):
        self.dismiss(self._selected())

    @on(Button.Pressed, "#btn_type_filter_cancel")
    def _btn_cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)

    def on_key(self, event):
        # SelectionList uses space for toggle and consumes it. Enter is free,
        # so treat it as "confirm selection".
        if event.key == "enter":
            self.dismiss(self._selected())
            event.stop()


class ColumnMultiSelectScreen(ModalScreen):
    """Modal dialog to multi-select board columns.

    Used by the work report (which columns feed it) and by the column-merge flow
    (which columns are the merge sources). Parameterised by ``prompt`` rather
    than forked: t1377's AC7 forbids a second column picker inside the board, and
    a `SelectionList` over ``(col_id, title)`` pairs is exactly what both need.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, columns: list, initial: str | None,
                 prompt: str = "Work report columns"):
        """``columns``: ordered (col_id, title) pairs; ``initial``: pre-checked col_id."""
        super().__init__()
        self.columns = list(columns)
        self.initial = initial
        self.prompt = prompt

    def compose(self):
        with Container(id="dep_picker_dialog"):
            yield Label(
                f"{self.prompt} — [dim]space to toggle, Enter to confirm, "
                "Esc to cancel[/]",
                id="dep_picker_title",
            )
            yield SelectionList[str](
                *(
                    Selection(title, value=col_id,
                              initial_state=(col_id == self.initial))
                    for col_id, title in self.columns
                ),
                id="work_report_column_list",
            )
            with Horizontal(id="detail_buttons"):
                yield Button("Confirm", variant="primary", id="btn_wr_cols_save")
                yield Button("Cancel", variant="default", id="btn_wr_cols_cancel")

    def on_mount(self):
        self.query_one("#work_report_column_list", SelectionList).focus()

    def _selected(self) -> list:
        sl = self.query_one("#work_report_column_list", SelectionList)
        checked = set(sl.selected)
        return [col_id for col_id, _ in self.columns if col_id in checked]

    @on(Button.Pressed, "#btn_wr_cols_save")
    def _btn_save(self):
        self.dismiss(self._selected())

    @on(Button.Pressed, "#btn_wr_cols_cancel")
    def _btn_cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)

    def on_key(self, event):
        # SelectionList uses space for toggle and consumes it. Enter is free,
        # so treat it as "confirm selection".
        if event.key == "enter":
            self.dismiss(self._selected())
            event.stop()


class TaskSelectScreenBase(ModalScreen):
    """Review a list of tasks in a SelectionList; confirm in DISPLAYED order.

    ``space`` toggles (SelectionList owns and consumes it), ``Enter`` confirms
    via ``on_key``, Esc / Cancel dismiss ``None``. The ``None`` (cancelled
    cleanly) vs ``[]`` (confirmed with nothing checked) distinction is
    load-bearing for every caller — they mean different things and neither
    writes.

    Subclasses supply ``TITLE_TEXT`` / ``LIST_ID`` and the three row adapters.
    Extracted in t1243_7: the move-to-column command needs this exact widget
    with a different row shape, and a third hand-copied
    SelectionList-in-``#dep_picker_dialog`` screen in one file is the
    duplication that task exists to stop adding to.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    #: Dialog heading (the keybinding hint is appended by `compose`).
    TITLE_TEXT = ""
    #: DOM id of the SelectionList — distinct per subclass so a test can query
    #: the concrete screen it means.
    LIST_ID = ""

    def __init__(self, rows: list):
        super().__init__()
        self.rows = list(rows)

    # --- row adapters ---------------------------------------------------

    def _row_key(self, row):
        """The SelectionList `value` for `row` (must be hashable + unique)."""
        raise NotImplementedError

    def _row_label(self, row):
        """What the user reads for `row`."""
        raise NotImplementedError

    def _row_value(self, row):
        """What `dismiss` hands back for `row`."""
        raise NotImplementedError

    # --- widget ---------------------------------------------------------

    def compose(self):
        with Container(id="dep_picker_dialog"):
            yield Label(
                f"{self.TITLE_TEXT} — [dim]space to toggle, Enter to confirm, "
                f"Esc to cancel[/]",
                id="dep_picker_title",
            )
            yield SelectionList[str](
                *(
                    Selection(self._row_label(row), value=self._row_key(row),
                              initial_state=True)
                    for row in self.rows
                ),
                id=self.LIST_ID,
            )
            with Horizontal(id="detail_buttons"):
                yield Button("Confirm", variant="primary", id="btn_task_select_save")
                yield Button("Cancel", variant="default", id="btn_task_select_cancel")

    def on_mount(self):
        self.query_one(f"#{self.LIST_ID}", SelectionList).focus()

    def _selected(self) -> list:
        sl = self.query_one(f"#{self.LIST_ID}", SelectionList)
        checked = set(sl.selected)
        return [self._row_value(row) for row in self.rows
                if self._row_key(row) in checked]

    @on(Button.Pressed, "#btn_task_select_save")
    def _btn_save(self):
        self.dismiss(self._selected())

    @on(Button.Pressed, "#btn_task_select_cancel")
    def _btn_cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)

    def on_key(self, event):
        # SelectionList uses space for toggle and consumes it. Enter is free,
        # so treat it as "confirm selection".
        if event.key == "enter":
            self.dismiss(self._selected())
            event.stop()


class WorkReportTaskSelectScreen(TaskSelectScreenBase):
    """Modal dialog to review/exclude the tasks feeding a work report.

    ``rows``: ordered (col_id, task_id, label) triples grouped by column in
    board order. The displayed sequence IS the reviewed order the launch must
    preserve — confirm dismisses the still-selected (col_id, task_id) pairs in
    exactly that order.
    """

    TITLE_TEXT = "Work report tasks"
    LIST_ID = "work_report_task_list"

    @property
    def tasks(self):
        """Historic alias for `rows`, kept so existing callers/tests read the
        same attribute they did before the base class was extracted."""
        return self.rows

    def _row_key(self, row):
        return row[1]                    # task_id

    def _row_label(self, row):
        return row[2]

    def _row_value(self, row):
        return (row[0], row[1])          # (col_id, task_id)


class MoveTaskSelectScreen(TaskSelectScreenBase):
    """Review which tasks a bulk column move will act on (t1243_7).

    ``rows``: ordered (filename, label) pairs in board order. Confirm dismisses
    the still-checked FILENAMES in that same order, which is what
    ``move_tasks_to_column`` consumes — it preserves input order, so the
    destination sequence matches the sequence the user reviewed.
    """

    TITLE_TEXT = "Move tasks to column"
    LIST_ID = "move_task_list"

    def _row_key(self, row):
        return row[0]                    # filename

    def _row_label(self, row):
        return row[1]

    def _row_value(self, row):
        return row[0]


class LockEmailScreen(ModalScreen):
    """Modal dialog to enter email for locking a task."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, task_id: str, default_email: str = ""):
        super().__init__()
        self.task_id = task_id
        self.default_email = default_email

    def compose(self):
        with Container(id="dep_picker_dialog"):
            yield Label(f"Lock task t{self.task_id}", id="dep_picker_title")
            yield Label("Enter email for lock ownership:")
            yield Input(
                value=self.default_email,
                placeholder="user@example.com",
                id="lock_email_input",
            )
            with Horizontal(id="detail_buttons"):
                yield Button("Lock", variant="warning", id="btn_confirm_lock")
                yield Button("Cancel", variant="default", id="btn_cancel_lock")

    @on(Button.Pressed, "#btn_confirm_lock")
    def confirm_lock(self):
        email = self.query_one("#lock_email_input", Input).value.strip()
        if email:
            self.dismiss(email)
        else:
            self.app.notify("Email is required", severity="warning")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.confirm_lock()

    @on(Button.Pressed, "#btn_cancel_lock")
    def cancel_lock(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class UnlockConfirmScreen(ModalScreen):
    """Confirmation dialog to unlock a task locked by another user."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, task_id: str, locked_by: str, locked_at: str, hostname: str):
        super().__init__()
        self.task_id = task_id
        self.locked_by = locked_by
        self.locked_at = locked_at
        self.hostname = hostname

    def compose(self):
        with Container(id="dep_picker_dialog"):
            yield Label(
                f"Task t{self.task_id} is locked by another user",
                id="dep_picker_title",
            )
            yield Label(
                f"Locked by: {self.locked_by}\n"
                f"Hostname: {self.hostname}\n"
                f"Since: {self.locked_at}\n\n"
                f"Force unlock?"
            )
            with Horizontal(id="detail_buttons"):
                yield Button("Force Unlock", variant="error", id="btn_confirm_unlock")
                yield Button("Cancel", variant="default", id="btn_cancel_unlock")

    @on(Button.Pressed, "#btn_confirm_unlock")
    def confirm_unlock(self):
        self.dismiss(True)

    @on(Button.Pressed, "#btn_cancel_unlock")
    def cancel_unlock(self):
        self.dismiss(False)

    def action_cancel(self):
        self.dismiss(False)


class ResetTaskConfirmScreen(ModalScreen):
    """Confirmation dialog to reset task status and assignment after unlock."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, task_id: str, assigned_to: str):
        super().__init__()
        self.task_id = task_id
        self.assigned_to = assigned_to

    def compose(self):
        with Container(id="dep_picker_dialog"):
            yield Label(
                f"Reset task t{self.task_id}?",
                id="dep_picker_title",
            )
            yield Label(
                f"This task is currently:\n"
                f"  Status: Implementing\n"
                f"  Assigned to: {self.assigned_to}\n\n"
                f"Reset status to Ready and clear assignment?"
            )
            with Horizontal(id="detail_buttons"):
                yield Button("Reset to Ready", variant="warning", id="btn_confirm_reset")
                yield Button("Keep current", variant="default", id="btn_cancel_reset")

    @on(Button.Pressed, "#btn_confirm_reset")
    def confirm_reset(self):
        self.dismiss(True)

    @on(Button.Pressed, "#btn_cancel_reset")
    def cancel_reset(self):
        self.dismiss(False)

    def action_cancel(self):
        self.dismiss(False)


class TaskDetailScreen(ShortcutsMixin, ModalScreen):
    """Popup to view/edit task details with metadata editing."""

    _shortcuts_scope = "board.detail"

    BINDINGS = [
        Binding("escape", "close_modal", "Close", show=False),
        Binding("p", "pick", "Pick", show=False),
        Binding("P", "pick", "Pick", show=False),
        Binding("l", "lock", "Lock", show=False),
        Binding("L", "lock", "Lock", show=False),
        Binding("u", "unlock", "Unlock", show=False),
        Binding("U", "unlock", "Unlock", show=False),
        Binding("c", "close", "Close", show=False),
        Binding("C", "close", "Close", show=False),
        Binding("s", "save", "Save", show=False),
        Binding("S", "save", "Save", show=False),
        Binding("r", "revert", "Revert", show=False),
        Binding("R", "revert", "Revert", show=False),
        Binding("e", "edit", "Edit", show=False),
        Binding("E", "edit", "Edit", show=False),
        Binding("d", "delete", "Delete", show=False),
        Binding("D", "delete", "Delete", show=False),
        Binding("n", "rename", "Rename", show=False),
        Binding("N", "rename", "Rename", show=False),
        Binding("v", "toggle_view", "Toggle View", show=False),
        Binding("V", "fullscreen_plan", "Fullscreen plan", show=False),
        Binding("b", "brainstorm", "Brainstorm", show=False),
        Binding("B", "brainstorm", "Brainstorm", show=False),
        Binding("tab", "focus_minimap", "Minimap", show=False),
    ]

    def __init__(self, task: Task, manager: TaskManager = None, read_only: bool = False):
        super().__init__()
        self.task_data = task
        self.manager = manager
        self.read_only = read_only
        self._lock_info = None
        self._original_values = {
            "priority": task.metadata.get("priority", "medium"),
            "effort": task.metadata.get("effort", "medium"),
            "status": task.metadata.get("status", "Ready"),
            "issue_type": task.metadata.get("issue_type", "feature"),
        }
        self._current_values = dict(self._original_values)
        self._showing_plan = False
        self._plan_path = self._resolve_plan_path() if manager else None
        self._plan_parsed = None
        self._plan_text = ""

    def _resolve_plan_path(self):
        """Resolve the plan file path for this task."""
        return _resolve_plan_path_for_task(self.task_data, self.manager)

    def _build_risk_fields(self, meta):
        """Read-only risk widgets — shown only when explicitly set in metadata.

        Risk has no default: an absent field means unset, so nothing is shown.
        Risk levels are decided by the task workflow / plan, not edited here.
        """
        out = []
        if meta.get("risk_code_health"):
            out.append(ReadOnlyField(
                f"[b]Code-health risk:[/b] {meta.get('risk_code_health')}", classes="meta-ro"))
        if meta.get("risk_goal_achievement"):
            out.append(ReadOnlyField(
                f"[b]Goal risk:[/b] {meta.get('risk_goal_achievement')}", classes="meta-ro"))
        return out

    def _build_gate_fields(self):
        """``(rows, fraction)`` for the Gates section — the expanded gate
        surface (t1603_4). ``rows`` empty means no section is mounted.

        The compact chip on an In-Flight card and this list must never describe
        the same ledger differently, so **nothing here is derived locally**: the
        fraction comes from `derive_workflow_phase`, the degraded and error
        strings from `phase_chip_text`, the failed set from
        `_failed_active_gates` and the attended-agent set from
        `_pending_procedure_gates`. Satisfied-vs-pending is decided by
        membership in ``archive_pending`` — the list the archival guard reads —
        and a gate's raw ``current`` run only chooses the glyph *within* each
        side. A count computed here instead would be a second implementation of
        `_gate_progress`, which is what its docstring exists to forbid.
        """
        if self.manager is None:
            return [], None
        result = self.manager.gate_state_for(self.task_data)
        state = result.state

        # An unreadable ledger is ONE row and nothing else — no phase row
        # beside it. This must run BEFORE the phase row: `derive_workflow_phase`
        # branch B0 returns `error` provenance for an `Implementing` task, and
        # `phase_chip_text` renders that as this very string, so ordering the
        # phase row first would print it twice.
        if result.error:
            return [ReadOnlyField(
                escape(phase_chip_text("implementing", "error", None,
                                       error=result.error)),
                classes="meta-ro")], None

        has_gates = bool(state and (state.active_gates or state.filtered_gates))
        if not (has_gates or result.has_ledger):
            return [], None

        registry = self.manager.gate_registry()
        phase = derive_workflow_phase(
            self.task_data, result, registry,
            # Already resolved in __init__ — no new disk access, and the
            # laziness t1656 introduced is preserved.
            plan_exists_probe=lambda: self._plan_path is not None)

        # A fraction is a progress claim, so it requires a ledger. Deferring to
        # `phase.progress` inherits that rule from `derive_workflow_phase` for
        # free: it is None on the no-ledger branch and on the marker branch, and
        # the card prints no fraction in either. Recomputing here would print
        # `0/N` beside "No gate ledger", the fabricated fraction `WorkflowPhase`
        # documents as never a stand-in for `None`.
        if phase is not None:
            fraction = phase.progress
        elif result.has_ledger and state is not None:
            fraction = _gate_progress(state)[0]
        else:
            fraction = None

        out = []
        if phase is not None:
            out.append(ReadOnlyField(
                escape(phase_chip_text(phase.phase, phase.provenance,
                                       phase.progress)),
                classes="meta-ro"))
        if state is None:
            return out, fraction

        pending = set(state.archive_pending)
        failed = set(_failed_active_gates(state))
        procedure = set(_pending_procedure_gates(state, registry))
        for gate in state.active_gates:
            run = state.current.get(gate)   # may be None: a declared gate that
            status = run.status if run else None   # never ran has no entry
            name = escape(gate)
            if gate in pending:
                if gate in state.stale_signed:
                    # BOTH facts, never one without the other: the ledger really
                    # does say `pass`, and the signature no longer binds the
                    # code (gate_ledger.py:167-174).
                    row = f"⚠ {name} — pass, signature stale; needs re-sign"
                elif gate in failed:
                    row = f"✗ {name} — failed"
                elif gate in procedure:
                    row = f"◈ {name} — pending; needs attended agent"
                else:
                    # The ordinary state of a freshly claimed task, not a
                    # fallback: every declared gate lands here until it runs.
                    row = f"· {name} — pending"
            elif status == "skip":
                # Terminal-satisfied, but distinct from pass, as in the ledger.
                row = f"⊘ {name} — skipped (not applicable)"
            else:
                row = f"✓ {name} — passed"
            out.append(ReadOnlyField(row, classes="meta-ro"))

        if state.filtered_gates:
            out.append(ReadOnlyField(
                "[dim]filtered by profile (audit only)[/dim]", classes="meta-ro"))
            for gate in state.filtered_gates:
                out.append(ReadOnlyField(
                    f"[dim]· {escape(gate)}[/dim]", classes="meta-ro"))
        return out, fraction

    def _build_relations_fields(self, meta):
        """Dependencies & hierarchy metadata widgets (in display order)."""
        out = []
        if meta.get("depends"):
            deps = meta["depends"]
            if deps and self.manager:
                out.append(DependsField(deps, self.manager, self.task_data, classes="meta-ro"))
            elif deps:
                dep_str = ", ".join(str(d) for d in deps)
                out.append(ReadOnlyField(f"[b]Depends:[/b] {dep_str}", classes="meta-ro"))
        xdeprepo = meta.get("xdeprepo")
        xdeps = meta.get("xdeps", []) or []
        if xdeprepo and xdeps:
            if self.manager:
                out.append(CrossRepoDepsField(xdeprepo, xdeps, self.manager,
                                              classes="meta-ro"))
            else:
                xdep_str = ", ".join(
                    f"{xdeprepo}#{str(xd).lstrip('t')}" for xd in xdeps
                )
                out.append(ReadOnlyField(
                    f"[b]Cross-repo deps:[/b] ↗ {xdep_str}", classes="meta-ro"))
        if meta.get("verifies"):
            verifies = meta["verifies"]
            if verifies and self.manager:
                out.append(VerifiesField(verifies, self.manager, self.task_data, classes="meta-ro"))
            elif verifies:
                v_str = ", ".join(str(v) for v in verifies)
                out.append(ReadOnlyField(f"[b]Verifies:[/b] {v_str}", classes="meta-ro"))
        # Parent field for child tasks
        if self.task_data.filepath.parent != TASKS_DIR and self.manager:
            parent_num = self.manager.get_parent_num_for_child(self.task_data)
            if parent_num:
                out.append(ParentField(parent_num, self.manager, classes="meta-ro"))
        # Children field for parent tasks
        if meta.get("children_to_implement"):
            children_ids = meta["children_to_implement"]
            if children_ids and self.manager:
                out.append(ChildrenField(children_ids, self.manager, self.task_data,
                                         classes="meta-ro"))
            elif children_ids:
                children = ", ".join(str(c) for c in children_ids)
                out.append(ReadOnlyField(f"[b]Children:[/b] {children}", classes="meta-ro"))
        # Folded tasks field
        if meta.get("folded_tasks"):
            folded_ids = meta["folded_tasks"]
            if folded_ids and self.manager:
                out.append(FoldedTasksField(folded_ids, self.manager,
                                            self.task_data, classes="meta-ro"))
            elif folded_ids:
                folded_str = ", ".join(str(f) for f in folded_ids)
                out.append(ReadOnlyField(
                    f"[b]Folded Tasks:[/b] {folded_str}", classes="meta-ro"))
        # Folded into field
        if meta.get("folded_into"):
            folded_into_num = str(meta["folded_into"])
            if self.manager:
                out.append(FoldedIntoField(folded_into_num, self.manager, classes="meta-ro"))
            else:
                out.append(ReadOnlyField(
                    f"[b]Folded Into:[/b] t{folded_into_num}", classes="meta-ro"))
        # Topic anchor (group key) — editable; shown even when unset so a root
        # task can be given an anchor. Read-only screens (archived) show a plain
        # line only when an anchor is actually set.
        anchor_val = _bare_topic_id(meta.get("anchor"))
        if self.manager and not self.read_only:
            out.append(AnchorField(anchor_val, self.manager, self.task_data,
                                   read_only=False, classes="meta-ro"))
        elif anchor_val:
            out.append(ReadOnlyField(f"[b]Anchor:[/b] t{anchor_val}", classes="meta-ro"))
        return out

    def _build_tracking_fields(self, meta):
        """Tracking & provenance metadata widgets (in display order)."""
        out = []
        if meta.get("labels"):
            out.append(ReadOnlyField(f"[b]Labels:[/b] {', '.join(meta['labels'])}", classes="meta-ro"))
        if meta.get("assigned_to"):
            out.append(ReadOnlyField(f"[b]Assigned to:[/b] {meta['assigned_to']}", classes="meta-ro"))
        if meta.get("issue"):
            out.append(IssueField(meta["issue"], classes="meta-ro"))
        if meta.get("pull_request"):
            out.append(PullRequestField(meta["pull_request"], classes="meta-ro"))
        if meta.get("contributor"):
            contributor_text = meta["contributor"]
            if meta.get("contributor_email"):
                contributor_text += f" ({meta['contributor_email']})"
            out.append(ReadOnlyField(f"  [b]Contributor:[/b] @{contributor_text}", classes="meta-ro"))
        if meta.get("implemented_with"):
            out.append(ReadOnlyField(f"[b]Implemented with:[/b] {meta['implemented_with']}", classes="meta-ro"))
        # Deferred-plan marker (t1603_1). Read-only by design: the field is
        # written and cleared exclusively by the task-workflow, so the board
        # offers no affordance to edit it. Absent marker => no row at all, and
        # the collapsible's `(<n>)` count adjusts for free. `escape` because
        # ReadOnlyField parses Rich markup: a hand-edited value containing `[`
        # would otherwise be swallowed. Wording matches `ait ls`, which renders
        # `Plan: approved <ts>` (aitask_ls.sh:853).
        plan_marker = _plan_approved_marker(meta)
        if plan_marker:
            out.append(ReadOnlyField(
                f"[b]Plan approved:[/b] {escape(plan_marker)}", classes="meta-ro"))
        dates = []
        if meta.get("created_at"):
            dates.append(f"[b]Created:[/b] {meta['created_at']}")
        if meta.get("updated_at"):
            dates.append(f"[b]Updated:[/b] {meta['updated_at']}")
        if dates:
            out.append(ReadOnlyField("  |  ".join(dates), classes="meta-ro"))
        return out

    def _build_lockfiles_fields(self, meta):
        """File references + lock status widgets. Side effect: sets self._lock_info."""
        out = []
        # File references field (read-only, navigate via enter)
        if self.manager:
            file_refs = meta.get("file_references") or []
            out.append(FileReferencesField(
                file_refs, self.manager, self.task_data,
                classes="meta-ro"))
        # Lock status (computes self._lock_info, consumed by compose for buttons)
        if self.manager:
            task_num, _ = TaskCard._parse_filename(self.task_data.filename)
            lock_id = task_num.lstrip("t")
            self._lock_info = self.manager.lock_map.get(lock_id)
        if self._lock_info:
            locked_by = self._lock_info["locked_by"]
            locked_at = self._lock_info["locked_at"]
            hostname = self._lock_info.get("hostname", "")
            stale_marker = ""
            try:
                lock_time = datetime.strptime(locked_at, "%Y-%m-%d %H:%M")
                hours_ago = (datetime.now() - lock_time).total_seconds() / 3600
                if hours_ago > 24:
                    stale_marker = " [yellow](may be stale)[/yellow]"
            except (ValueError, TypeError):
                pass
            host_str = f" on {hostname}" if hostname else ""
            out.append(ReadOnlyField(
                f"[b]\U0001f512 Locked:[/b] {locked_by}{host_str} since {locked_at}{stale_marker}",
                classes="meta-ro"))
        else:
            out.append(ReadOnlyField(
                "[b]\U0001f513 Lock:[/b] [dim]Unlocked[/dim]",
                classes="meta-ro"))
        return out

    def compose(self):
        task_num, task_name = TaskCard._parse_filename(self.task_data.filename)
        display_title = f"{task_num} {task_name}".strip()
        meta = self.task_data.metadata

        with Container(id="detail_dialog"):
            with Horizontal(id="detail_title_bar"):
                yield Label(f"\U0001f4c4 {display_title}", id="detail_title")
                # View-mode indicator lives at the end of the title line; its
                # background changes between Task and Plan (see toggle_view).
                yield Label("Task", id="view_indicator", classes="viewing-task")

            is_done = meta.get("status", "") == "Done"
            is_folded = meta.get("status", "") == "Folded"
            is_done_or_ro = is_done or is_folded or self.read_only
            with Container(id="meta_editable"):
                if is_done_or_ro:
                    yield ReadOnlyField(f"[b]Priority:[/b] {meta.get('priority', 'medium')}", classes="meta-ro")
                    yield ReadOnlyField(f"[b]Effort:[/b] {meta.get('effort', 'medium')}", classes="meta-ro")
                    yield ReadOnlyField(f"[b]Status:[/b] {meta.get('status', 'Ready')}", classes="meta-ro")
                    yield ReadOnlyField(f"[b]Type:[/b] {meta.get('issue_type', 'feature')}", classes="meta-ro")
                else:
                    yield CycleField("Priority", list(LEVELS_ASCENDING),
                                     meta.get("priority", "medium"), "priority",
                                     id="cf_priority")
                    yield CycleField("Effort", list(LEVELS_ASCENDING),
                                     meta.get("effort", "medium"), "effort",
                                     id="cf_effort")
                    status_options = ["Ready", "Editing", "Implementing", "Postponed"]
                    yield CycleField("Status", status_options,
                                     meta.get("status", "Ready"), "status",
                                     id="cf_status")
                    yield CycleField("Type", _load_task_types(),
                                     meta.get("issue_type", "feature"), "issue_type",
                                     id="cf_issue_type")
                # Follow-up provenance (t1468_8) -- the 5th row of the primary
                # block in BOTH modes, so a card's glyph is decodable the
                # moment the task is opened. Editable only on a live screen
                # with a manager (the post-write reload needs one); a
                # read-only screen shows the row ONLY when a kind is actually
                # set, since it offers no way to set one. Mirrors AnchorField.
                #
                # One widget class in both modes rather than a ReadOnlyField
                # for the read-only case: one render implementation, so the
                # read-only line cannot drift from the editable one.
                fk_read_only = is_done_or_ro or self.manager is None
                if not fk_read_only or _followup_marker(meta):
                    yield FollowupKindField(
                        meta.get("followup_kind"), self.manager,
                        self.task_data, read_only=fk_read_only,
                        id="ff_followup_kind", classes="meta-ro")

            # --- Grouped, collapsible secondary metadata ---
            # Risk (read-only) — only present when explicitly set in metadata.
            risk = self._build_risk_fields(meta)
            if risk:
                with Collapsible(title=f"Risk ({len(risk)})",
                                 collapsed=True, id="sec_risk", classes="meta-section"):
                    yield from risk

            # Gates (read-only) — the expanded counterpart to the In-Flight
            # card's compact chip. The title's fraction is the chip's fraction,
            # not a row count: filtered gates are listed but never counted, and
            # a task with no ledger gets no fraction at all rather than `0/N`.
            gates, gate_fraction = self._build_gate_fields()
            if gates:
                gate_title = ("Gates" if gate_fraction is None
                              else f"Gates ({gate_fraction[0]}/{gate_fraction[1]})")
                with Collapsible(title=gate_title,
                                 collapsed=True, id="sec_gates", classes="meta-section"):
                    yield from gates

            relations = self._build_relations_fields(meta)
            if relations:
                with Collapsible(title=f"Dependencies & hierarchy ({len(relations)})",
                                 collapsed=True, id="sec_relations", classes="meta-section"):
                    yield from relations

            tracking = self._build_tracking_fields(meta)
            if tracking:
                with Collapsible(title=f"Tracking & provenance ({len(tracking)})",
                                 collapsed=True, id="sec_tracking", classes="meta-section"):
                    yield from tracking

            lockfiles = self._build_lockfiles_fields(meta)
            if lockfiles:
                with Collapsible(title="Lock & files",
                                 collapsed=True, id="sec_lockfiles", classes="meta-section"):
                    yield from lockfiles

            has_plan = self._plan_path is not None

            with VerticalScroll(id="md_view"):
                yield Markdown(self.task_data.content)

            # Button rows
            is_locked = self._lock_info is not None
            with Container(id="detail_buttons_area"):
                with Horizontal(id="detail_buttons_workflow"):
                    yield Button(self.label("pick", "Pick"), variant="warning", id="btn_pick", disabled=is_done_or_ro)
                    yield Button(self.label("brainstorm", "Brainstorm"), variant="primary", id="btn_brainstorm", disabled=is_done_or_ro or is_locked)
                    yield Button("\U0001f512 " + self.label("lock", "Lock"), variant="primary", id="btn_lock",
                                 disabled=is_done_or_ro or is_locked)
                    yield Button("\U0001f513 " + self.label("unlock", "Unlock"), variant="warning", id="btn_unlock",
                                 disabled=not is_locked)
                    yield Button(self.label("close", "Close"), variant="default", id="btn_close")
                with Horizontal(id="detail_buttons_file"):
                    yield Button(self.label("toggle_view", "View Plan"), variant="primary", id="btn_view",
                                 disabled=not has_plan)
                    yield Button(self.label("save", "Save Changes"), variant="success", id="btn_save",
                                 disabled=True)
                    is_modified = self.manager.is_modified(self.task_data) if self.manager else False
                    yield Button(self.label("revert", "Revert"), variant="error", id="btn_revert",
                                 disabled=is_done_or_ro or not is_modified)
                    yield Button(self.label("edit", "Edit"), variant="primary", id="btn_edit", disabled=is_done_or_ro)
                    yield Button(self.label("rename", "Name"), variant="primary", id="btn_rename", disabled=is_done_or_ro or is_locked)
                    can_delete = (not is_done and not is_folded and not self.read_only
                                  and self.task_data.metadata.get("status", "") != "Implementing")
                    yield Button(self.label("delete", "Delete/Archive"), variant="error", id="btn_delete",
                                 disabled=not can_delete)

    @on(CycleField.Changed)
    def on_cycle_changed(self, event: CycleField.Changed):
        self._current_values[event.field.field_key] = event.value
        self._update_save_button()
        self._update_delete_button()

    def has_unsaved_edits(self) -> bool:
        """True when a CycleField edit is pending an explicit Save.

        Named and field-agnostic on purpose: any field that persists
        IMMEDIATELY must consult it, because its post-write
        ``_reload_detail_screen`` REPLACES this screen with a fresh instance
        that re-seeds ``_original_values`` from disk -- silently dropping the
        pending values. ``AnchorField`` has the same exposure and should adopt
        this (tracked as an upstream defect; not fixed by t1468_8).
        """
        return self._current_values != self._original_values

    def _update_save_button(self):
        is_dirty = self.has_unsaved_edits()
        btn_save = self.query_one("#btn_save", Button)
        btn_save.disabled = not is_dirty
        # Immediate-write fields must not fire while a deferred edit is
        # pending. `query`, not `query_one`: the field is absent on a read-only
        # screen whose task carries no followup_kind.
        for field in self.query(FollowupKindField):
            field.set_blocked(is_dirty)

    def _update_delete_button(self):
        status = self._current_values.get("status", "")
        btn_delete = self.query_one("#btn_delete", Button)
        btn_delete.disabled = (status == "Implementing")

    @on(Button.Pressed, "#btn_save")
    def save_changes(self):
        # Determine which fields the user actually changed
        changed_fields = {
            key: value for key, value in self._current_values.items()
            if value != self._original_values.get(key)
        }
        if not changed_fields:
            return
        # Reload from disk to pick up external changes (e.g. Claude Code)
        if not self.task_data.load():
            self.app.notify("Task file no longer exists", severity="error")
            return
        # Apply only the changed fields
        for key, value in changed_fields.items():
            self.task_data.metadata[key] = value
        self.task_data.save_with_timestamp()
        # Update originals to reflect saved state
        for key in self._current_values:
            self._original_values[key] = self.task_data.metadata.get(key, self._current_values[key])
        self._current_values = dict(self._original_values)
        self._update_save_button()

    @on(Button.Pressed, "#btn_revert")
    def revert_task(self):
        """Revert task file to last committed version in git."""
        try:
            result = subprocess.run(
                [*_task_git_cmd(), "checkout", "--", str(self.task_data.filepath)],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                self.task_data.load()
                self.app.notify("Reverted to last committed version", severity="information")
                self.dismiss("reverted")
            else:
                error = result.stderr.strip() or result.stdout.strip()
                self.app.notify(f"Revert failed: {error}", severity="error")
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            self.app.notify(f"Revert failed: {e}", severity="error")

    @on(Button.Pressed, "#btn_close")
    def close_dialog(self):
        self.dismiss()

    @on(Button.Pressed, "#btn_edit")
    def edit_task(self):
        if self._showing_plan:
            self.dismiss("edit_plan")
        else:
            self.dismiss("edit")

    def _read_plan_content(self):
        """Return plan content for the current task with YAML frontmatter stripped, or None."""
        if not self._plan_path:
            return None
        content = self._plan_path.read_text(encoding="utf-8")
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2].strip()
        return content

    @on(Button.Pressed, "#btn_view")
    def toggle_view(self):
        """Toggle between task content and plan content."""
        if not self._plan_path:
            self.app.notify("No plan file found", severity="warning")
            return
        self._showing_plan = not self._showing_plan
        md_widget = self.query_one("#md_view Markdown", Markdown)
        indicator = self.query_one("#view_indicator", Label)
        btn_view = self.query_one("#btn_view", Button)

        md_view = self.query_one("#md_view", VerticalScroll)

        if self._showing_plan:
            content = self._read_plan_content() or ""
            md_widget.update(content)
            indicator.update("Plan")
            indicator.remove_class("viewing-task")
            indicator.add_class("viewing-plan")
            btn_view.label = "(V)iew Task"
            md_view.styles.border = ("solid", "#FFB86C")
            self._mount_or_update_minimap(md_view, content)
        else:
            md_widget.update(self.task_data.content)
            indicator.update("Task")
            indicator.remove_class("viewing-plan")
            indicator.add_class("viewing-task")
            btn_view.label = "(V)iew Plan"
            md_view.styles.border = None
            self._remove_minimap(md_view)

    def _mount_or_update_minimap(self, md_view, plan_content):
        """Mount or repopulate #board_minimap inside #md_view based on plan sections."""
        try:
            from section_viewer import SectionMinimap, parse_sections
        except Exception as exc:
            self.app.notify(f"Section viewer unavailable: {exc}", severity="warning")
            return
        parsed = parse_sections(plan_content)
        if not parsed.sections:
            self._plan_parsed = None
            self._plan_text = ""
            self._remove_minimap(md_view)
            return
        self._plan_parsed = parsed
        self._plan_text = plan_content
        existing = md_view.query("#board_minimap")
        if not existing:
            minimap = SectionMinimap(id="board_minimap")
            md_view.mount(minimap, before="Markdown")
        md_view.query_one("#board_minimap", SectionMinimap).populate(parsed)

    def _remove_minimap(self, md_view):
        """Remove #board_minimap from #md_view if present."""
        for w in list(md_view.query("#board_minimap")):
            w.remove()

    def on_section_minimap_section_selected(self, event):
        """Scroll the plan Markdown to the selected section."""
        if self._plan_parsed is None or not self._plan_text:
            return
        try:
            from section_viewer import estimate_section_y
        except Exception:
            return
        md_view = self.query_one("#md_view", VerticalScroll)
        total = self._plan_text.count("\n") + 1
        y = estimate_section_y(
            self._plan_parsed, event.section_name, total, md_view.virtual_size.height
        )
        if y is not None:
            md_view.scroll_to(y=y, animate=False)
        event.stop()

    def on_section_minimap_toggle_focus(self, event):
        """Minimap Tab -> focus plan Markdown."""
        try:
            md = self.query_one("#md_view Markdown", Markdown)
        except Exception:
            event.stop()
            return
        md.focus()
        event.stop()

    def action_fullscreen_plan(self):
        """Push the full-screen SectionViewerScreen for the current plan."""
        plan_content = self._read_plan_content()
        if not plan_content:
            self.app.notify("No plan file found", severity="warning")
            return
        try:
            from section_viewer import SectionViewerScreen
        except Exception as exc:
            self.app.notify(f"Section viewer unavailable: {exc}", severity="warning")
            return
        task_num, _ = TaskCard._parse_filename(self.task_data.filename)
        self.app.push_screen(
            SectionViewerScreen(plan_content, title=f"Plan for {task_num}")
        )

    def action_focus_minimap(self):
        """Tab from plan Markdown -> focus minimap. SkipAction guard keeps form Tab-nav intact."""
        from textual.actions import SkipAction
        try:
            md = self.screen.query_one("#md_view Markdown", Markdown)
        except Exception:
            raise SkipAction()
        minimaps = self.screen.query("#board_minimap")
        if self.screen.focused is not md or not minimaps:
            raise SkipAction()
        minimaps.first().focus_first_row()

    @on(Button.Pressed, "#btn_rename")
    def rename_task(self):
        self.dismiss("rename")

    @on(Button.Pressed, "#btn_delete")
    def delete_task(self):
        self.dismiss("delete_archive")

    @on(Button.Pressed, "#btn_pick")
    def pick_task(self):
        self.dismiss("pick")

    @on(Button.Pressed, "#btn_brainstorm")
    def brainstorm_task(self):
        self.dismiss("brainstorm")

    @on(Button.Pressed, "#btn_lock")
    def lock_task(self):
        """Lock this task via aitask_lock.sh."""
        task_num, _ = TaskCard._parse_filename(self.task_data.filename)
        task_id = task_num.lstrip("t")
        default_email = _get_user_email()

        def on_email(email):
            if email is None:
                return
            self.app.push_screen(LoadingOverlay("Locking task..."))
            self._do_lock(task_id, email)

        self.app.push_screen(LockEmailScreen(task_id, default_email), on_email)

    @work(thread=True)
    def _do_lock(self, task_id: str, email: str):
        """Run lock subprocess in a thread worker."""
        try:
            try:
                result = subprocess.run(
                    ["./.aitask-scripts/aitask_lock.sh", "--lock", task_id, "--email", email],
                    capture_output=True, text=True, timeout=15
                )
            finally:
                # Dismiss LoadingOverlay. Scoped to the subprocess call, not the
                # whole body: pop_screen removes the TOP screen, so it must run
                # before any later push (see _do_unlock's ResetTaskConfirmScreen).
                # `finally` — not the `except` below — is what keeps the overlay
                # off-screen for an exception type this handler does not name.
                self.app.call_from_thread(self.app.pop_screen)
            if result.returncode == 0:
                self.app.call_from_thread(self.app.notify, f"Locked t{task_id}", severity="information")
                self.app.call_from_thread(self.dismiss, "locked")
            else:
                error = result.stderr.strip() or result.stdout.strip()
                self.app.call_from_thread(self.app.notify, f"Lock failed: {error}", severity="error")
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            self.app.call_from_thread(self.app.notify, f"Lock failed: {e}", severity="error")

    @on(Button.Pressed, "#btn_unlock")
    def unlock_task(self):
        """Unlock this task via aitask_lock.sh."""
        task_num, _ = TaskCard._parse_filename(self.task_data.filename)
        task_id = task_num.lstrip("t")

        def do_unlock():
            self.app.push_screen(LoadingOverlay("Unlocking task..."))
            self._do_unlock(task_id)

        if self._lock_info:
            my_email = _get_user_email()
            locked_by = self._lock_info["locked_by"]
            if my_email and locked_by != my_email:
                def on_confirm(confirmed):
                    if confirmed:
                        do_unlock()
                self.app.push_screen(
                    UnlockConfirmScreen(
                        task_id, locked_by,
                        self._lock_info.get("locked_at", "?"),
                        self._lock_info.get("hostname", "?"),
                    ),
                    on_confirm,
                )
                return

        do_unlock()

    @work(thread=True)
    def _do_unlock(self, task_id: str):
        """Run unlock subprocess in a thread worker."""
        try:
            try:
                result = subprocess.run(
                    ["./.aitask-scripts/aitask_lock.sh", "--unlock", task_id],
                    capture_output=True, text=True, timeout=15
                )
            finally:
                # Dismiss LoadingOverlay before the ResetTaskConfirmScreen push
                # below — pop_screen removes the TOP screen, so a body-wide
                # `finally` here would pop the confirm dialog instead. See
                # _do_lock for the full rationale.
                self.app.call_from_thread(self.app.pop_screen)
            if result.returncode == 0:
                self.app.call_from_thread(self.app.notify, f"Unlocked t{task_id}", severity="information")
                meta = self.task_data.metadata
                if meta.get("status") == "Implementing" and meta.get("assigned_to"):
                    assigned_to = meta["assigned_to"]
                    def on_reset_confirmed(confirmed):
                        if confirmed:
                            if not self.task_data.load():
                                self.app.notify("Task file no longer exists", severity="error")
                                self.dismiss("unlocked")
                                return
                            self.task_data.metadata["status"] = "Ready"
                            self.task_data.metadata["assigned_to"] = ""
                            self.task_data.save_with_timestamp()
                        self.dismiss("unlocked")
                    self.app.call_from_thread(
                        self.app.push_screen,
                        ResetTaskConfirmScreen(task_id, assigned_to),
                        on_reset_confirmed,
                    )
                    return
                self.app.call_from_thread(self.dismiss, "unlocked")
            else:
                error = result.stderr.strip() or result.stdout.strip()
                self.app.call_from_thread(self.app.notify, f"Unlock failed: {error}", severity="error")
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            self.app.call_from_thread(self.app.notify, f"Unlock failed: {e}", severity="error")

    def action_close_modal(self):
        self.dismiss()

    def action_pick(self):
        btn = self.query_one("#btn_pick", Button)
        if not btn.disabled:
            self.pick_task()

    def action_brainstorm(self):
        btn = self.query_one("#btn_brainstorm", Button)
        if not btn.disabled:
            self.brainstorm_task()

    def action_lock(self):
        btn = self.query_one("#btn_lock", Button)
        if not btn.disabled:
            self.lock_task()

    def action_unlock(self):
        btn = self.query_one("#btn_unlock", Button)
        if not btn.disabled:
            self.unlock_task()

    def action_close(self):
        self.close_dialog()

    def action_save(self):
        btn = self.query_one("#btn_save", Button)
        if not btn.disabled:
            self.save_changes()

    def action_revert(self):
        btn = self.query_one("#btn_revert", Button)
        if not btn.disabled:
            self.revert_task()

    def action_edit(self):
        btn = self.query_one("#btn_edit", Button)
        if not btn.disabled:
            self.edit_task()

    def action_toggle_view(self):
        btn = self.query_one("#btn_view", Button)
        if not btn.disabled:
            self.toggle_view()

    def action_rename(self):
        btn = self.query_one("#btn_rename", Button)
        if not btn.disabled:
            self.rename_task()

    def action_delete(self):
        btn = self.query_one("#btn_delete", Button)
        if not btn.disabled:
            self.delete_task()

class RenameTaskScreen(ModalScreen):
    """Modal dialog to rename a task (change the description part of the filename)."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, task_filename: str):
        super().__init__()
        self.task_filename = task_filename
        self.task_num, self.current_name = TaskCard._parse_filename(task_filename)

    def compose(self):
        with Container(id="rename_dialog"):
            yield Label(f"Rename Task {self.task_num}", id="rename_title")
            yield Label(f"Prefix: [b]{self.task_num}_[/b] (fixed)")
            yield Input(value=self.current_name.replace(" ", "_"), id="rename_input",
                        placeholder="new_task_name", select_on_focus=False)
            with Horizontal(id="detail_buttons"):
                yield Button("Rename", variant="success", id="btn_do_rename")
                yield Button("Cancel", variant="default", id="btn_rename_cancel")

    @on(Button.Pressed, "#btn_do_rename")
    def do_rename(self):
        new_name = self.query_one("#rename_input", Input).value.strip()
        if not new_name:
            return
        self.dismiss(("rename", new_name))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.do_rename()

    @on(Button.Pressed, "#btn_rename_cancel")
    def cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class CommitMessageScreen(ModalScreen):
    """Modal dialog to enter a commit message and confirm git commit."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, tasks_to_commit: list[Task], manager: TaskManager):
        super().__init__()
        self.tasks_to_commit = tasks_to_commit
        self.manager = manager

    def compose(self):
        if len(self.tasks_to_commit) == 1:
            task = self.tasks_to_commit[0]
            task_num, task_name = TaskCard._parse_filename(task.filename)
            default_msg = f"ait: Update {task_num}: {task_name}"
        else:
            task_nums = []
            for t in self.tasks_to_commit:
                num, _ = TaskCard._parse_filename(t.filename)
                task_nums.append(num)
            default_msg = f"ait: Update tasks: {', '.join(task_nums)}"

        with Container(id="commit_dialog"):
            yield Label("Git Commit", id="commit_title")
            file_list = "\n".join(f"  {str(t.filepath)}" for t in self.tasks_to_commit)
            yield Label(f"Files to commit:\n{file_list}", id="commit_files")
            yield Label("Commit message:")
            yield Input(value=default_msg, id="commit_msg_input")
            with Horizontal(id="detail_buttons"):
                yield Button("Commit", variant="success", id="btn_commit")
                yield Button("Cancel", variant="default", id="btn_commit_cancel")

    @on(Button.Pressed, "#btn_commit")
    def do_commit(self):
        msg = self.query_one("#commit_msg_input", Input).value.strip()
        if not msg:
            return
        self.dismiss(("commit", msg))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.do_commit()

    @on(Button.Pressed, "#btn_commit_cancel")
    def cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)

# --- Column Customization Screens ---

class ColorSwatch(Static):
    """A clickable color swatch for the palette."""

    can_focus = True

    class Selected(Message):
        def __init__(self, color: str):
            super().__init__()
            self.color = color

    def __init__(self, color: str, label: str, selected: bool = False):
        super().__init__()
        self.color = color
        self.label = label
        self.is_selected = selected

    def render(self) -> str:
        marker = "\u25cf" if self.is_selected else "\u25cb"
        return f"[{self.color}]{marker} \u2588\u2588[/]"

    def on_click(self):
        self.post_message(self.Selected(self.color))

    def on_key(self, event):
        if event.key in ("enter", "space"):
            self.post_message(self.Selected(self.color))
            event.prevent_default()
            event.stop()

    def on_focus(self):
        self.styles.border = ("round", self.color)

    def on_blur(self):
        self.styles.border = None


class ColumnEditScreen(ModalScreen):
    """Modal dialog for adding or editing a kanban column."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, manager: TaskManager, col_id: str = None, mode: str = "add"):
        super().__init__()
        self.manager = manager
        self.col_id = col_id
        self.mode = mode
        self.col_conf = manager.get_column_conf(col_id) if col_id else None
        self.selected_color = self.col_conf["color"] if self.col_conf else PALETTE_COLORS[0][0]

    @staticmethod
    def _generate_col_id(name: str, existing_ids: list) -> str:
        """Generate a unique column ID from a display name.

        Thin delegate: the implementation moved to `lib/board_columns.py`
        (t1377_3) so the headless writer and this dialog slug identically. The
        board stays the semantic owner — see that module's docstring.
        """
        return generate_col_id(name, existing_ids)

    def compose(self):
        title = "Add New Column" if self.mode == "add" else f"Edit Column: {self.col_conf['title']}"
        with Container(id="column_edit_dialog"):
            yield Label(title, id="column_edit_title")
            yield Input(
                value=self.col_conf["title"] if self.col_conf else "",
                placeholder="Column name",
                id="col_title_input",
            )
            with Horizontal(id="color_palette"):
                yield Label("Color ", id="color_label")
                for color, label in PALETTE_COLORS:
                    yield ColorSwatch(color, label, selected=(color == self.selected_color))
            with Horizontal(id="detail_buttons"):
                yield Button("Save", variant="success", id="btn_col_save")
                yield Button("Cancel", variant="default", id="btn_col_cancel")

    @on(ColorSwatch.Selected)
    def on_color_selected(self, event: ColorSwatch.Selected):
        self.selected_color = event.color
        for swatch in self.query(ColorSwatch):
            swatch.is_selected = (swatch.color == event.color)
            swatch.refresh()

    @on(Button.Pressed, "#btn_col_save")
    def save(self):
        title = self.query_one("#col_title_input", Input).value.strip()
        if not title:
            self.app.notify("Title is required", severity="warning")
            return
        color = self.selected_color
        if self.mode == "add":
            existing_ids = [c["id"] for c in self.manager.columns]
            col_id = self._generate_col_id(title, existing_ids)
            self.dismiss(("add", col_id, title, color))
        else:
            self.dismiss(("edit", self.col_id, title, color))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.save()

    @on(Button.Pressed, "#btn_col_cancel")
    def cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class DeleteColumnConfirmScreen(ModalScreen):
    """Confirmation dialog to delete a column."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, col_conf: dict, task_count: int):
        super().__init__()
        self.col_conf = col_conf
        self.task_count = task_count

    def compose(self):
        msg = f"Delete column '{self.col_conf['title']}'?"
        if self.task_count > 0:
            msg += f"\n\n{self.task_count} task(s) will be moved to Unsorted / Inbox."
        with Container(id="dep_picker_dialog"):
            yield Label(msg, id="dep_picker_title")
            with Horizontal(id="detail_buttons"):
                yield Button("Delete", variant="error", id="btn_confirm_col_delete")
                yield Button("Cancel", variant="default", id="btn_cancel_col_delete")

    @on(Button.Pressed, "#btn_confirm_col_delete")
    def confirm(self):
        self.dismiss(True)

    @on(Button.Pressed, "#btn_cancel_col_delete")
    def cancel(self):
        self.dismiss(False)

    def action_cancel(self):
        self.dismiss(False)


DEFAULT_REFRESH_OPTIONS = ["0", "1", "2", "5", "10", "15", "30"]


class SettingsScreen(ModalScreen):
    """Modal dialog for editing board settings."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, manager: TaskManager):
        super().__init__()
        self.manager = manager

    def compose(self):
        current_minutes = str(self.manager.auto_refresh_minutes)
        if current_minutes not in DEFAULT_REFRESH_OPTIONS:
            current_minutes = "5"
        with Container(id="settings_dialog"):
            yield Label("Board Settings", id="settings_title")
            yield CycleField(
                "Auto-refresh (min)",
                DEFAULT_REFRESH_OPTIONS,
                current_minutes,
                "auto_refresh_minutes",
                id="cf_auto_refresh",
            )
            yield Label("  [dim]0 = disabled[/dim]", classes="settings-hint")
            current_sync = "yes" if self.manager.settings.get("sync_on_refresh", False) else "no"
            yield CycleField(
                "Sync on refresh",
                ["no", "yes"],
                current_sync,
                "sync_on_refresh",
                id="cf_sync_on_refresh",
            )
            yield Label("  [dim]Push/pull task data on each auto-refresh[/dim]", classes="settings-hint")
            with Horizontal(id="detail_buttons"):
                yield Button("Save", variant="success", id="btn_settings_save")
                yield Button("Cancel", variant="default", id="btn_settings_cancel")

    @on(Button.Pressed, "#btn_settings_save")
    def save_settings(self):
        refresh_field = self.query_one("#cf_auto_refresh", CycleField)
        new_minutes = int(refresh_field.current_value)
        sync_field = self.query_one("#cf_sync_on_refresh", CycleField)
        new_sync = sync_field.current_value == "yes"
        self.dismiss({"auto_refresh_minutes": new_minutes, "sync_on_refresh": new_sync})

    @on(Button.Pressed, "#btn_settings_cancel")
    def cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class ColumnSelectItem(PickerItem):
    """A selectable column item in the picker."""

    def __init__(self, col_conf: dict):
        super().__init__()
        self.col_conf = col_conf

    def render(self) -> str:
        return f"  [{self.col_conf['color']}]\u2588\u2588[/] {self.col_conf['title']} ({self.col_conf['id']})"

    def on_key(self, event):
        if event.key == "enter":
            self.screen.dismiss(self.col_conf["id"])
            event.prevent_default()
            event.stop()

    def on_click(self):
        self.screen.dismiss(self.col_conf["id"])


class ColumnSelectScreen(ModalScreen):
    """Select a column from the list for editing/deleting/collapsing/expanding."""

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=False),
    ]

    def __init__(self, manager: TaskManager, action_label: str, columns: list[dict] = None):
        super().__init__()
        self.manager = manager
        self.action_label = action_label
        self.columns_list = columns if columns is not None else manager.columns

    def compose(self):
        with Container(id="dep_picker_dialog", classes="picker-dialog"):
            yield Label(f"Select column to {self.action_label.lower()}:", id="dep_picker_title")
            for col in self.columns_list:
                yield ColumnSelectItem(col)

    def action_cancel(self):
        self.dismiss(None)


class ColumnManageItem(PickerItem):
    """One column row inside :class:`ColumnManageScreen`."""

    def __init__(self, col_conf: dict, position: int, task_count: int):
        super().__init__()
        self.col_conf = col_conf
        self.position = position
        self.task_count = task_count

    @property
    def col_id(self) -> str:
        return self.col_conf["id"]

    def render(self) -> str:
        n = self.task_count
        return (f"  {self.position:>2}. [{self.col_conf['color']}]██[/] "
                f"{self.col_conf['title']} ({self.col_id}) "
                f"— {n} task{'' if n == 1 else 's'}")

    def on_key(self, event):
        if event.key == "enter":
            self.screen.edit_column(self.col_id)
            event.prevent_default()
            event.stop()

    def on_click(self):
        self.focus()


class MergeColumnsConfirmScreen(ModalScreen):
    """Confirmation for an N->1 column merge, naming what actually moves."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, source_titles: list, dest_title: str, task_count: int):
        super().__init__()
        self.source_titles = list(source_titles)
        self.dest_title = dest_title
        self.task_count = task_count

    def compose(self):
        sources = ", ".join(f"'{t}'" for t in self.source_titles)
        n = self.task_count
        msg = (f"Merge {sources} into '{self.dest_title}'?\n\n"
               f"{n} task{'' if n == 1 else 's'} will move to the bottom of "
               f"'{self.dest_title}'.\n"
               f"The source column{'' if len(self.source_titles) == 1 else 's'} "
               "will be removed.")
        with Container(id="dep_picker_dialog"):
            yield Label(msg, id="dep_picker_title")
            with Horizontal(id="detail_buttons"):
                yield Button("Merge", variant="warning", id="btn_confirm_col_merge")
                yield Button("Cancel", variant="default", id="btn_cancel_col_merge")

    @on(Button.Pressed, "#btn_confirm_col_merge")
    def confirm(self):
        self.dismiss(True)

    @on(Button.Pressed, "#btn_cancel_col_merge")
    def cancel(self):
        self.dismiss(False)

    def action_cancel(self):
        self.dismiss(False)


class ColumnManageScreen(ModalScreen):
    """One dialog behind one key for every column operation (t1377_5).

    Add / edit / delete / reorder / collapse all existed before this screen, but
    **no key was bound to any of them** — they were reachable only through the
    Ctrl+P palette or the column-header pencil button. Merge did not exist at all
    until t1377_4 landed the engine (with zero call sites; this screen is its
    first consumer).

    Every sub-flow reuses an existing modal — `ColumnEditScreen`,
    `DeleteColumnConfirmScreen`, `ColumnMultiSelectScreen`, `ColumnSelectScreen`
    — because t1377's AC7 forbids a second column picker inside the board.

    Mutations are applied without refreshing the board per operation: the screen
    tracks `_changed` and dismisses it, so the caller recomposes exactly once on
    close instead of once per edit under a live modal.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=False),
        Binding("shift+up", "shift_up", "Move column up", show=False),
        Binding("shift+down", "shift_down", "Move column down", show=False),
    ]

    def __init__(self, manager: TaskManager, start_in_merge: bool = False):
        super().__init__()
        self.manager = manager
        self._changed = False
        self._start_in_merge = start_in_merge

    # --- composition -----------------------------------------------------

    def compose(self):
        with Container(id="column_manage_dialog", classes="picker-dialog"):
            yield Label(
                "Manage columns — [dim]shift+↑/↓ reorder, "
                "Enter edit, Esc close[/]",
                id="dep_picker_title",
            )
            yield VerticalScroll(id="column_manage_list")
            # Four buttons, not five: `#detail_buttons` centers without
            # wrapping, so anything past the dialog width is clipped rather
            # than reflowed. A fifth "Close" button pushed the row over the
            # edge at 100 columns — a visible control the user cannot click.
            # Esc closes, `action_cancel` handles it, and the hint line above
            # says so, matching every other modal in this file.
            with Horizontal(id="detail_buttons"):
                yield Button("Add", variant="primary", id="btn_colmgr_add")
                yield Button("Edit", variant="default", id="btn_colmgr_edit")
                yield Button("Delete", variant="error", id="btn_colmgr_delete")
                yield Button("Merge", variant="warning", id="btn_colmgr_merge")

    def on_mount(self):
        self._rebuild()
        if self._start_in_merge:
            self.call_after_refresh(self.action_merge)

    def _rows(self) -> list:
        """`(col_conf, task_count)` for every column actually on the board.

        A `column_order` entry with no matching `columns` definition is dropped
        silently by both the renderer and `load_columns()`, so it is not offered
        here either — listing it would let the user "reorder" a column that does
        not render.
        """
        rows = []
        for col_id in self.manager.column_order:
            conf = self.manager.get_column_conf(col_id)
            if conf:
                rows.append((conf, len(self.manager.get_column_tasks(col_id))))
        return rows

    def _rebuild(self, focus_col_id: str = None):
        listing = self.query_one("#column_manage_list", VerticalScroll)
        listing.remove_children()
        items = [ColumnManageItem(conf, pos, count)
                 for pos, (conf, count) in enumerate(self._rows(), start=1)]
        if items:
            listing.mount_all(items)
            target = focus_col_id or items[0].col_id
            self.call_after_refresh(self._focus_col, target)

    def _focus_col(self, col_id: str):
        for item in self.query(ColumnManageItem):
            if item.col_id == col_id:
                item.focus()
                return

    def _focused_item(self):
        focused = self.screen.focused
        return focused if isinstance(focused, ColumnManageItem) else None

    def _title_of(self, col_id: str) -> str:
        """Display title, delegating so the synthetic lane is named correctly.

        `get_column_conf` returns None for `unordered` (it is not in `columns`),
        so a local fallback to the raw id would confirm and report a merge as
        "unordered" while the picker the user just clicked said "Unsorted /
        Inbox". `KanbanApp._column_title` already owns that mapping.
        """
        return self.app._column_title(col_id)

    # --- reorder ---------------------------------------------------------

    def _shift(self, direction: int):
        item = self._focused_item()
        if item is None:
            return
        visible = [conf["id"] for conf, _ in self._rows()]
        pos = visible.index(item.col_id)
        new_pos = pos + direction
        if not (0 <= new_pos < len(visible)):
            return
        # Swap the two ids WHERE THEY SIT in column_order rather than swapping
        # adjacent order slots: a stale (conf-less) entry can sit between two
        # visible columns, and swapping raw slots would move the stale entry
        # instead of the column the user is looking at.
        order = self.manager.column_order
        a, b = order.index(item.col_id), order.index(visible[new_pos])
        order[a], order[b] = order[b], order[a]
        self.manager.save_metadata()
        self._changed = True
        self._rebuild(focus_col_id=item.col_id)

    def action_shift_up(self):
        self._shift(-1)

    def action_shift_down(self):
        self._shift(1)

    # --- add / edit / delete ---------------------------------------------

    def _on_edit_result(self, result):
        if self.app._apply_column_edit(result):
            self._changed = True
            col_id = result[1] if len(result) > 1 else None
            self._rebuild(focus_col_id=col_id)

    def action_add(self):
        self.app.push_screen(
            ColumnEditScreen(self.manager, mode="add"), self._on_edit_result)

    def edit_column(self, col_id: str):
        self.app.push_screen(
            ColumnEditScreen(self.manager, col_id=col_id, mode="edit"),
            self._on_edit_result)

    def action_edit(self):
        item = self._focused_item()
        if item is None:
            self.app.notify("Select a column to edit", severity="warning")
            return
        self.edit_column(item.col_id)

    def action_delete(self):
        item = self._focused_item()
        if item is None:
            self.app.notify("Select a column to delete", severity="warning")
            return
        col_id = item.col_id
        conf = self.manager.get_column_conf(col_id)
        count = len(self.manager.get_column_tasks(col_id))

        def on_confirmed(confirmed):
            if confirmed:
                self.manager.delete_column(col_id)
                self.app.notify(f"Deleted column: {conf['title']}",
                                severity="information")
                self._changed = True
                self._rebuild()

        self.app.push_screen(DeleteColumnConfirmScreen(conf, count), on_confirmed)

    # --- merge -----------------------------------------------------------

    def action_merge(self):
        """sources (multi-select) -> destination -> confirm -> merge_columns."""
        sources = self.app._merge_source_columns()
        if len(sources) < 2:
            self.app.notify(
                "Merging needs at least two columns to choose from",
                severity="warning")
            return

        def on_sources(chosen):
            if not chosen:
                return
            self._pick_destination(chosen)

        self.app.push_screen(
            ColumnMultiSelectScreen(sources, None, prompt="Merge FROM"),
            on_sources)

    def _pick_destination(self, source_ids: list):
        remaining = [conf for conf, _ in self._rows()
                     if conf["id"] not in source_ids]
        if UNORDERED_ID not in source_ids:
            # Same hand-injection idiom as `action_collapse_column`: the lane is
            # synthetic and absent from `columns`, but `merge_columns` accepts it
            # as a destination (it is what `delete_column` already does).
            remaining.append({"id": UNORDERED_ID, "title": UNORDERED_TITLE,
                              "color": UNORDERED_COLOR})
        if not remaining:
            self.app.notify("No destination column left to merge into",
                            severity="warning")
            return

        def on_destination(dest_id):
            if dest_id:
                self._confirm_merge(source_ids, dest_id)

        self.app.push_screen(
            ColumnSelectScreen(self.manager, "Merge into", columns=remaining),
            on_destination)

    def _confirm_merge(self, source_ids: list, dest_id: str):
        attempted = sum(len(self.manager.get_column_tasks(c)) for c in source_ids)
        titles = [self._title_of(c) for c in source_ids]

        def on_confirmed(confirmed):
            if not confirmed:
                return
            result = self.manager.merge_columns(source_ids, dest_id)
            self.app._report_merge(result, self._title_of(dest_id), attempted)
            if result.merged or result.sources_removed:
                self._changed = True
            self._rebuild()

        self.app.push_screen(
            MergeColumnsConfirmScreen(titles, self._title_of(dest_id), attempted),
            on_confirmed)

    # --- buttons / close --------------------------------------------------

    @on(Button.Pressed, "#btn_colmgr_add")
    def _btn_add(self):
        self.action_add()

    @on(Button.Pressed, "#btn_colmgr_edit")
    def _btn_edit(self):
        self.action_edit()

    @on(Button.Pressed, "#btn_colmgr_delete")
    def _btn_delete(self):
        self.action_delete()

    @on(Button.Pressed, "#btn_colmgr_merge")
    def _btn_merge(self):
        self.action_merge()

    def handle_escape(self):
        """Escape hook honoured by `KanbanApp.action_focus_board`.

        The app binds `escape` with `priority=True`, so it wins over this
        screen's own binding and closes any active modal with a bare
        `self.screen.dismiss()` — i.e. a `None` result. Every other board modal
        treats `None` as "cancelled", so the discarded value is harmless there;
        here it is not, because the dismiss value is the "did anything change?"
        flag the caller uses to decide whether to recompose. Without this hook a
        merge or reorder closed with Escape left the board rendering the removed
        column until the next manual refresh.
        """
        self.dismiss(self._changed)

    def action_cancel(self):
        self.dismiss(self._changed)


# --- Command Palette Provider ---

class KanbanCommandProvider(Provider):
    """Provide board commands to the Textual command palette."""

    #: Single source for the palette: (display, action attribute, help).
    #: `discover()` and `search()` used to repeat this list verbatim, so a
    #: command added to one and not the other went missing from either
    #: discovery or search with nothing failing (t1243_7). t1377_5 adds its
    #: column-management entries HERE rather than re-splitting the list.
    _COMMANDS = (
        ("Add Column", "action_add_column",
         "Add a new column to the board"),
        ("Edit Column", "action_edit_column",
         "Edit a column's title and color"),
        ("Delete Column", "action_delete_column",
         "Delete a column (tasks move to Unsorted)"),
        ("Collapse Column", "action_collapse_column",
         "Collapse a column to minimize its width"),
        ("Expand Column", "action_expand_column",
         "Expand a collapsed column to full width"),
        ("Move Tasks to Column", "action_move_to_column",
         "Move the marked task(s) — or the focused card — to a column"),
        ("Move Wave to Column", "action_trail_move_wave",
         "Move the focused By-Trail wave's tasks to a column, in wave order"),
        ("Clear Selection", "action_clear_marks",
         "Unmark every marked task"),
        ("Manage Columns", "action_column_manage",
         "Reorder, add, edit, delete or merge columns"),
        ("Merge Columns", "action_merge_columns",
         "Merge one or more columns into another"),
        ("Settings", "action_open_settings",
         "Configure board settings (auto-refresh interval)"),
        ("Sync with Remote", "action_sync_remote",
         "Push local changes and pull remote changes"),
    )

    def _resolved(self):
        """(display, bound callback, help) for every command.

        The ONE place `_COMMANDS` is turned into callables — both surfaces go
        through it, which is what keeps them from drifting apart.
        """
        app = self.app
        return [(display, getattr(app, attr), help_text)
                for display, attr, help_text in self._COMMANDS]

    async def discover(self) -> Hits:
        for display, command, help_text in self._resolved():
            yield DiscoveryHit(display=display, command=command, help=help_text)

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        for display, command, help_text in self._resolved():
            score = matcher.match(display)
            if score > 0:
                yield Hit(
                    score=score,
                    match_display=matcher.highlight(display),
                    command=command,
                    help=help_text,
                )


# --- Main Application ---

class BoardScreen(Screen):
    """The board's default screen, with Textual's auto-focus disabled (t1491).

    `Screen._update_auto_focus` runs inside `Screen._compose` — before the app's
    `on_mount` — and focuses the first focusable widget matching the selector.
    In this app that is `Input#search_box`, which made a freshly launched board
    swallow every non-`priority` single-key binding (`q` included) as search
    text until the user pressed Tab/Esc or clicked.

    `""` is what actually disables it: `None` means "inherit `App.AUTO_FOCUS`"
    (i.e. `"*"`), while an empty selector is falsy and skips the loop. Scoped to
    THIS screen deliberately — modal screens are pushed separately and keep the
    app-level `"*"`, so every dialog still focuses its first control.

    With auto-focus off, the board is briefly focus-less until
    `KanbanApp._claim_startup_focus` anchors focus on a card. That interval is
    safe by construction: an unfocused screen routes keys straight to the App
    bindings, so `q` quits throughout it. Leaving auto-focus on and merely
    correcting it afterwards would instead leave a real window in which the
    Input still owned the keyboard.
    """

    AUTO_FOCUS = ""


class KanbanApp(TuiSwitcherMixin, ShortcutsMixin, TrailScreenMixin, App):
    _shortcuts_scope = "board"

    # Minimum column allocation for the search box before the filter row
    # reflows. Includes the Input's own chrome (2 border + 4 padding), so ~24
    # cells of text remain visible. Sole source of truth for that floor — it is
    # enforced by the reflow threshold in _apply_filter_reflow, deliberately not
    # duplicated as a CSS `min-width` (t1247).
    FILTER_SEARCH_MIN_WIDTH = 30

    CSS = """
    Screen { align: center middle; }
    #detail_dialog {
        width: 80%;
        height: 96%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #detail_title_bar {
        dock: top;
        height: 3;
        background: $secondary;
    }
    #detail_title {
        width: 1fr;
        height: 100%;
        content-align: center middle;
        text-align: center;
        color: $text;
    }
    #detail_buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }
    #detail_buttons_area {
        dock: bottom;
        height: auto;
        max-height: 7;
    }
    #detail_buttons_workflow {
        height: 3;
        align: center middle;
    }
    #detail_buttons_file {
        height: 3;
        align: center middle;
    }
    #meta_editable { height: auto; padding: 0 1; }
    #detail_dialog .meta-section { padding-bottom: 0; border-top: hkey $secondary-background; }
    #detail_dialog .meta-section Contents { padding: 0 0 0 3; }
    CycleField { height: 1; width: 100%; padding: 0 1; }
    CycleField.cycle-focused { background: $primary 20%; border-left: thick $accent; }
    .meta-ro { height: 1; width: 100%; padding: 0 2; color: $text-muted; }
    .meta-ro.ro-focused { background: $primary 20%; border-left: thick $accent; }
    #btn_save:disabled { opacity: 50%; }
    #btn_delete:disabled { opacity: 50%; }
    #view_indicator { width: auto; height: 100%; content-align: center middle; padding: 0 2; text-style: bold; }
    #view_indicator.viewing-task { background: $primary; color: $text; }
    #view_indicator.viewing-plan { background: #FFB86C; color: $background; }
    #md_view { margin: 1 0; border: solid $secondary-background; }
    .task-title-row { height: auto; }
    /* Layout and state ONLY — no `color:`, mirroring `.task-followup-glyph`
       below. The colour is Rich markup from `mark_glyphs.mark_markup()`; a
       `color:` here would be a second authority that CSS cannot keep in sync
       with the Python constant, and CSS cannot express the glyph at all, so the
       two halves of one mark would live in two files. `.task-marked` survives
       as a STATE HOOK with no declarations — `_repaint_card_mark` and the tests
       key off it. (t1638; the `color: yellow` this replaces resolved to
       #ffff00, which was not the Dracula yellow the other surfaces intended.) */
    .task-mark { width: auto; margin: 0 1 0 0; }
    .task-marked { }
    /* Layout ONLY — no `color:`, and no per-kind classes. The colour is a
       literal Rich style from FOLLOWUP_KINDS (see `_followup_marker`); a
       `.fk-<kind>` rule here would be a second authority that CSS cannot keep
       in sync with a Python dict. */
    .task-followup-glyph { width: auto; margin: 0 1 0 0; }
    .task-number { color: $accent; text-style: bold; width: auto; margin: 0 1 0 0; }
    .task-modified { color: #FFB86C; }
    .task-title { text-style: bold; width: 1fr; }

    /* `.markable-card` is set in TaskCard.__init__ — without that assignment
       these two rules match nothing. Scoped to the class, NOT to the bare
       `TaskCard` type: a Textual type selector matches the whole MRO, so
       `TaskCard:hover` would also restyle InFlightTaskCard, TrailTaskCard and
       the read-only TrailGhostCard — a hover affordance in three views this
       change does not touch. Focus keeps its imperative double-cyan border
       (on_focus), so no :focus background rule is added here. */
    TaskCard.markable-card:hover { background: $surface-lighten-1; }
    /* Focused + hovered stays in the focus family, never the gray hover
       (:hover would otherwise override :focus at equal specificity).
       $primary 30% is the board's own idiom — .collapsed-placeholder:focus. */
    TaskCard.markable-card:focus:hover { background: $primary 30%; }
    .task-info { color: $text-muted; }
    .inflight-action { color: $text; }
    .inflight-phase { color: $text-muted; }
    .inflight-ops { color: $accent; }
    .inflight-empty { height: 1; padding: 0 1; color: $text-muted; }
    .child-wrapper { height: auto; }
    .child-wrapper TaskCard { width: 1fr; }
    .child-connector { width: auto; height: auto; padding: 0; margin: 1 0 0 0; color: $text-muted; }
    /* Filter row. #view_col is sized from the ViewSelector's own rendered
       width (auto), never a hardcoded column count — a fixed number silently
       truncates the row whenever a base filter is added or a key is rebound
       (t1247). `.narrow` reflows the search box onto its own line instead of
       letting it squeeze the filters.

       NEVER re-add `dock: top` here (t1278). Textual places two same-edge
       docked siblings at the SAME offset rather than stacking them, so a
       docked #filter_area lands on y=0 on top of the docked Header and paints
       over it — silently, because the Header still reports display=True,
       visible=True and a correct region, and still appears in the
       compositor's visible_widgets. That hid every sub_title write (the
       By-Trail freshness banner and `Auto-refresh: …`) for the app's whole
       history. Undocked, the Header owns y=0 and this row flows below it.
       The bottom margin is gone deliberately: it was a second blank
       separator row, and dropping it pays for the header row, so
       #board_container still starts at y=4 with an unchanged height. */
    #filter_area { height: auto; }
    #filter_area.narrow { layout: vertical; }
    #view_col { width: auto; height: auto; }
    #filter_area.narrow #view_col { width: 100%; }
    #view_label { height: 1; padding: 0 1; color: $text-muted; }
    #view_selector { height: 1; padding: 0 1; width: auto; }
    .type-filter-summary { height: auto; padding: 0 1; color: $text-muted; }
    .type-filter-summary.hidden { display: none; }
    Input { width: 1fr; }
    .col-header-btn { width: auto; height: 1; padding: 0 1; }
    .col-header-edit-btn { width: auto; height: 1; padding: 0 1; background: black; color: white; }
    .col-header-row { height: auto; width: 100%; }
    .col-header-title { text-align: center; width: 100%; }
    .col-header-title-expanded { width: 1fr; text-align: center; }
    .col-header-count { text-align: center; width: 100%; color: $text-muted; }
    .collapsed-placeholder { height: 1; width: 100%; text-align: center; color: $text-muted; }
    .collapsed-placeholder:focus { background: $primary 30%; }
    .empty-placeholder { height: 1; width: 100%; text-align: center; color: $text-muted; }
    .empty-placeholder:focus { background: $primary 30%; }
    /* In-column task-group header (t1243_9). `$primary 30%` on :focus is the
       board's own idiom, shared with the two placeholders above. `:focus:hover`
       must repeat the focus colour: :hover would otherwise override :focus at
       equal specificity and drop a focused header into the gray hover family —
       the same rule TaskCard.markable-card:focus:hover exists for. */
    .group-header { height: 1; width: 100%; padding: 0 1; color: $accent; text-style: bold; }
    .group-header:focus { background: $primary 30%; }
    .group-header:hover { background: $surface-lighten-1; }
    .group-header:focus:hover { background: $primary 30%; }
    #dep_picker_dialog {
        width: 60%;
        height: auto;
        max-height: 50%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #dep_picker_title {
        text-align: center;
        padding: 0 0 1 0;
        text-style: bold;
    }
    #delarch_label {
        text-align: left;
        padding: 0 0 1 0;
    }
    /* t1366 — the `picker-dialog` marker scopes scrolling + a pinned title to
       the focus-driven pickers. #dep_picker_dialog is shared by 19 modals and
       they do NOT all want this: applying `dock: top` globally collapses the
       label-only confirm dialogs (their title is their only flow child, so
       `height: auto` resolves to 0 and the body renders below the buttons),
       and `overflow-y: auto` gives the SelectionList screens a nested double
       scrollbar. Scroll-into-view on focus is then free — Textual's
       Screen.set_focus scrolls the focused widget into view whenever the
       container permits scrolling. */
    #dep_picker_dialog.picker-dialog { overflow-y: auto; }
    .picker-dialog #dep_picker_title { width: 100%; dock: top; }
    /* One focus rule for all seven picker row types (they share the PickerItem
       base). `outline-left`, NOT `border-left`: an outline paints over the
       content area without resizing it, so a focused multi-line row does not
       reflow or change height. `padding: 0 1` is load-bearing — it gives the
       outline a blank column to land on instead of covering the first glyph.
       The `height: 1` overrides below MUST stay after this rule: both are bare
       type selectors of equal specificity, so source order decides. */
    PickerItem { height: auto; width: 100%; padding: 0 1; }
    PickerItem.dep-item-focused { background: $primary 20%; outline-left: thick $accent; }
    DepPickerItem { height: 1; }
    ChildPickerItem { height: 1; }
    #commit_dialog {
        width: 70%;
        height: auto;
        max-height: 60%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #commit_title {
        text-align: center;
        padding: 0 0 1 0;
        text-style: bold;
    }
    #commit_files {
        padding: 0 1;
        color: $text-muted;
    }
    #rename_dialog {
        width: 60%;
        height: auto;
        max-height: 40%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #rename_title {
        text-align: center;
        padding: 0 0 1 0;
        text-style: bold;
    }
    #column_edit_dialog {
        width: 60%;
        height: auto;
        max-height: 60%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    /* t1377_5 — the column-management dialog. Same chrome as the edit dialog;
       the row list scrolls on its own so a board with many columns keeps the
       button row docked and reachable. `.picker-dialog` supplies the t1366
       focus/scroll contract for the ColumnManageItem rows. */
    #column_manage_dialog {
        width: 70%;
        height: auto;
        max-height: 70%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #column_manage_list {
        height: auto;
        max-height: 20;
        width: 100%;
    }
    #column_edit_title {
        text-align: center;
        padding: 0 0 1 0;
        text-style: bold;
    }
    #color_palette {
        height: 3;
        width: 100%;
    }
    #color_label {
        width: auto;
        height: 3;
        content-align: left middle;
        padding: 0 1 0 0;
    }
    ColorSwatch {
        width: auto;
        height: 3;
        padding: 0 1;
        content-align: center middle;
    }
    #settings_dialog {
        width: 50%;
        height: auto;
        max-height: 40%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #settings_title {
        text-align: center;
        padding: 0 0 1 0;
        text-style: bold;
    }
    .settings-hint {
        height: 1;
        padding: 0 2;
    }
    #loading_dialog {
        width: 40;
        height: 7;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
        align: center middle;
    }
    #loading_message {
        text-align: center;
        width: 100%;
        height: 1;
        padding: 0 0 1 0;
    }
    #loading_dialog LoadingIndicator {
        height: 3;
    }
    """ + TRAIL_CSS

    TITLE = "aitasks board"

    COMMANDS = App.COMMANDS | {KanbanCommandProvider}

    BINDINGS = [
        *TuiSwitcherMixin.SWITCHER_BINDINGS,
        *ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS,
        Binding("q", "quit", "Quit"),
        Binding("tab", "focus_search", "Search", show=False, priority=True),
        Binding("escape", "focus_board", "Board", show=False, priority=True),
        # Card Navigation (priority=True to override scroll container bindings)
        Binding("up", "nav_up", "Up", show=False, priority=True),
        Binding("down", "nav_down", "Down", show=False, priority=True),
        Binding("left", "nav_left", "Left", show=False, priority=True),
        Binding("right", "nav_right", "Right", show=False, priority=True),
        # Task Movement
        Binding("shift+right", "move_task_right", "Task >"),
        Binding("shift+left", "move_task_left", "< Task"),
        Binding("shift+up", "move_task_up", "Task Up"),
        Binding("shift+down", "move_task_down", "Task Down"),
        Binding("ctrl+up", "move_task_top", "Task Top"),
        Binding("ctrl+down", "move_task_bottom", "Task Btm"),
        TRAIL_BINDING["view_details"],
        # Topic lane sort order — footer-visible only in the By-Topic view
        # (gated in check_action), placed here so it reads near the front.
        Binding("o", "sort_topic", "Sort Order"),
        # By-Trail rebinds `r` / `s` and adds `d` / `R` / `S` (t1268).
        # Textual resolves a repeated key by walking every binding for it in
        # declaration order and skipping the ones check_action rejects — for
        # dispatch (App._check_bindings -> run_action) and for the footer
        # (Screen.active_bindings). check_action makes each pair mutually
        # exclusive on base_filter, so exactly one is live at a time and the
        # footer shows that one's description. The trail duplicate follows its
        # generic partner so the pair is unambiguous at a glance.
        #
        # Footer ORDER follows each key's FIRST declaration (BindingsMap keys
        # on the key and yields its bindings together), so the uppercase
        # siblings are declared next to their lowercase primaries to satisfy
        # the adjacency rule in aidocs/framework/tui_conventions.md
        # ("keep uppercase sibling adjacent to its lowercase primary").
        Binding("r", "refresh_board", "Refresh"),
        TRAIL_BINDING["trail_refresh_local"],
        TRAIL_BINDING["trail_refresh_agent"],
        TRAIL_BINDING["trail_refresh_drift"],
        Binding("s", "sync_remote", "Sync"),
        TRAIL_BINDING["trail_select"],
        TRAIL_BINDING["trail_sync"],
        # By-Trail summary expand (t1505_1). `v` is free at App level — the
        # `v`/`u` keys live on TaskDetailScreen under the `board.detail` scope.
        TRAIL_BINDING["trail_summary_expand"],
        # Git Commit (shown conditionally via check_action)
        Binding("c", "commit_selected", "Commit"),
        Binding("C", "commit_all", "Commit All"),
        # Task Creation
        Binding("n", "create_task", "New Task"),
        # Pick task (shown conditionally via check_action)
        Binding("p", "pick_task", "Pick"),
        # Work report (shown conditionally via check_action)
        Binding("w", "work_report", "Work Report"),
        # Brainstorm task (shown conditionally via check_action)
        Binding("b", "brainstorm_task", "Brainstorm"),
        # Implementation-trail create/refresh launch (shown via check_action)
        TRAIL_BINDING["trail_task"],
        # Open cross-repo reference (shown conditionally via check_action)
        Binding("#", "open_cross_repo", "Cross-repo"),
        # Expand/Collapse children (shown conditionally via check_action)
        Binding("x", "toggle_children", "Toggle Children"),
        # Duplicate-key pair on `x` (t1243_9), the same shape the By-Trail `r`/`s`
        # pairs use: `check_action` cannot RELABEL a binding, so a truthful footer
        # ("Toggle Group" on a header, "Toggle Children" on a card) needs two
        # bindings gated mutually exclusively rather than one relabelled binding.
        Binding("x", "toggle_group", "Toggle Group"),
        # Multi-select marking (t1243_6; hidden in the derived views by check_action)
        Binding("space", "toggle_mark", "Mark"),
        # Bulk move to a column (t1243_7). This was `show=False` because the
        # single-row footer was already full at 200 columns, so a shown `m`
        # rendered as a bare key with its label clipped off. t1418's multi-row
        # footer removed that constraint — the board now shows every declared
        # binding down to ~160 columns — so `m` is footer-visible, as are the
        # other three keys hidden for the same reason (ctrl+up / ctrl+down / X).
        # check_action still gates it: hidden actions must not dispatch in the
        # derived views either.
        Binding("m", "move_to_column", "Move to Col"),
        # By-Trail wave move (t1210_5). Declared adjacent to its lowercase
        # primary per the uppercase-sibling rule in tui_conventions.md.
        # NOT a duplicate-key pair like the By-Trail `r`/`s`: `m` keeps ONE
        # meaning in every view ("move the selected task(s) to a column") and
        # its label is already truthful there, so only the wave command needs
        # a key of its own.
        TRAIL_BINDING["trail_move_wave"],
        # Column Movement
        Binding("ctrl+right", "move_col_right", "Move Col >"),
        Binding("ctrl+left", "move_col_left", "< Move Col"),
        # Column Collapse
        Binding("X", "toggle_column_collapsed", "Collapse Col"),
        # Column management (t1377_5): add / edit / delete / reorder / merge.
        # These all existed but had no key at all — only the Ctrl+P palette and
        # the header pencil button reached them.
        Binding("e", "column_manage", "Columns"),
        # Settings
        Binding("O", "open_settings", "Options"),
        # View filters: base radio (a/l/f/i) + add-on toggles (g/t)
        Binding("a", "view_all", "All", show=False),
        Binding("l", "view_locked", "Locked", show=False),
        Binding("f", "view_free", "Free", show=False),
        Binding("i", "view_inflight", "In-Flight", show=False),
        Binding("y", "view_bytopic", "By-Topic", show=False),
        Binding("z", "view_bytrail", "By-Trail", show=False),
        Binding("g", "view_git", "Git", show=False),
        Binding("t", "view_type", "Type", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.current_tui_name = "board"
        # `notify` is the single sink for save-time reconciliation warnings
        # (t1377_3); TaskManager has no screen of its own to raise them on.
        self.manager = make_task_manager(on_warning=self.notify)
        # One wiring point for every board_config.json commit (t1677).
        self.manager.on_metadata_commit = self._notify_metadata_commit
        self.search_filter = ""
        self.base_filter = "all"          # "all" | "locked" | "free" | "inflight" | "bytopic" | "bytrail"
        self.git_filter_active = False
        self.type_filter_active = False
        self._view_auto_expanded: set = set()
        self.expanded_tasks: set = set()
        # Collapsed in-column task groups, keyed "<col_id>/<slug>" (t1243_9),
        # PERSISTED since t1243_10 in `settings.collapsed_groups` (USER layer of
        # board_config, alongside `collapsed_columns`) — unlike the session-only
        # `expanded_tasks` above.
        #
        # An ALIAS, not a copy: `TaskManager` owns the object and mutates it IN
        # PLACE, so a lifecycle op that re-points keys (column rename / delete /
        # merge, and later a group move or rename) is seen here and by every
        # mounted `KanbanColumn` with no propagation step and no rebinding. Never
        # assign to this name — see `TaskManager._reset_collapsed_groups`.
        self.collapsed_groups: set = self.manager.collapsed_groups
        # Multi-select marks (t1243_6), keyed by task filename like the two sets
        # above. Session-only; cleared on view switch, pruned on refresh.
        self.marked = MarkedSelection()
        self._auto_refresh_timer = None
        # By-Trail session state lives on TrailScreenMixin (t1794_5).
        self._init_trail_state()

    def _notify_metadata_commit(self, result, paths):
        """Surface the outcome of a board_config.json commit.

        A swallowed failure is the whole defect this closes: the column change
        landed on disk but nothing committed it, and an ownerless dirty file
        blocks task-data sync until a human clears it. So a failure always names
        the remedy. Success is quiet — a commit per column edit is expected, and
        a toast for each would be noise.
        """
        if result.status in ("failed", "refused"):
            self.notify(
                f"Columns saved but NOT committed ({result.detail}). "
                f"Clear it with: {remedy_command(paths, allow_new=result.allow_new)}",
                severity="error", timeout=10,
            )

    def check_action(self, action: str, parameters) -> bool | None:
        """Control visibility of conditional actions in the footer bar."""
        # Textual hides footer bindings only when this returns False; None
        # leaves the binding visible but disabled.
        # A modal/overlay screen on top may own its own arrow-key navigation.
        # The board binds arrows with priority=True, which Textual checks before
        # the focused widget, so we selectively disable board nav while a screen
        # is pushed and let the arrow key fall through to the focused widget.
        #
        # Lateral nav (left/right) always falls through to the focused modal
        # widget — e.g. CycleField.on_key cycles its options, and Input moves
        # its text cursor. The board's column nav is board-only.
        if action in ("nav_left", "nav_right") and len(self.screen_stack) > 1:
            return False
        # Vertical nav (up/down) falls through only when the focused modal
        # widget owns row/line navigation itself — currently the shortcut
        # editor's DataTable. For every other modal (TaskDetailScreen metadata
        # fields, the task/dep/child pickers built from focusable Static items,
        # AgentCommandScreen buttons) up/down must reach action_nav_up/down,
        # which moves focus between widgets via focus_previous/next. Widget- and
        # screen-specific fall-throughs (Input, SelectionList, SelectOverlay,
        # TuiSwitcherOverlay, SectionViewerScreen) are handled by the guards
        # below.
        if action in ("nav_up", "nav_down") and len(self.screen_stack) > 1 \
                and isinstance(self.app.focused, DataTable):
            return False
        # Tab normally jumps to the board search box. While a modal is on the
        # stack that yanks focus out of the modal (e.g. the cross-repo ref
        # picker, which then only exposes its first item to the keyboard). Gate
        # it so Tab falls through to default widget focus-cycling inside the
        # modal. Escape is left App-level: action_focus_board is already
        # modal-aware and dismisses the active modal.
        if action == "focus_search" and len(self.screen_stack) > 1:
            return False
        # Let TuiSwitcherOverlay's ListView handle arrow keys natively
        if action in ("nav_up", "nav_down", "nav_left", "nav_right") and isinstance(self.screen, TuiSwitcherOverlay):
            return False
        # Let Input widgets handle arrow keys natively
        if action in ("nav_up", "nav_down", "nav_left", "nav_right") and isinstance(self.app.focused, Input):
            return False
        # Let SelectionList (used by IssueTypeFilterScreen) handle arrow keys
        if action in ("nav_up", "nav_down", "nav_left", "nav_right") and isinstance(self.app.focused, SelectionList):
            return False
        # Let Select dropdown overlay handle arrow keys natively
        if action in ("nav_up", "nav_down"):
            from textual.widgets._select import SelectOverlay
            if isinstance(self.app.focused, SelectOverlay):
                return False
        # SectionViewerScreen owns its own Tab and arrow keys (cycles minimap <-> content,
        # scrolls content, moves between minimap rows). Using type-name to avoid a circular
        # import with section_viewer.
        if type(self.screen).__name__ == "SectionViewerScreen":
            if action in ("focus_search", "nav_up", "nav_down", "nav_left", "nav_right"):
                return False
        # TopicSortModeScreen owns ↑/↓ (its own cursor bindings move the
        # selection); let them fall through instead of navigating the board.
        if type(self.screen).__name__ == "TopicSortModeScreen":
            if action in ("nav_up", "nav_down"):
                return False
        # Ghost trail cards are read-only projections (RFC §9.1): hide every
        # task-only action while one is focused. This is the primary safety —
        # the gates below reach into task_data (is_modified reads .filepath,
        # open_cross_repo reads metadata), and a ghost's synthetic stub must
        # never feed them. view_details stays visible (trail detail modal).
        if action in ("commit_selected", "toggle_children", "pick_task",
                      "brainstorm_task", "open_cross_repo", "trail_task",
                      "work_report",
                      # NOTE: the By-Trail move commands (`move_to_column`,
                      # `trail_move_wave`) are deliberately NOT listed here
                      # (t1210_5). This pre-gate calls `_focused_card()` for
                      # every action in the tuple, unconditionally — which
                      # would both double the call for `move_to_column` (its
                      # own branch reads focus too) and defeat the marked-set
                      # short-circuit that returns before any focus read.
                      # Both are pinned by MoveGatingTests. They do their own
                      # is_ghost check inside their branches instead, on the
                      # `_focused_card()` they already fetch.
                      "move_task_right", "move_task_left", "move_task_up",
                      "move_task_down", "move_task_top", "move_task_bottom"):
            focused = self._focused_card()
            if focused is not None and getattr(focused, "is_ghost", False):
                return False
        if action == "commit_selected":
            focused = self._focused_card()
            if not focused or not self.manager.is_modified(focused.task_data):
                return False
        elif action == "commit_all":
            # By-Trail lanes are a read-only projection, not an ownership
            # boundary: get_modified_tasks() scans task_datas +
            # child_task_datas repo-wide, so `C` here would commit modified
            # tasks that are not trail members. Hidden rather than scoped to
            # the trail's members — a trail is a reading view, and hiding
            # matches every other bytrail gate below (t1268).
            if self.base_filter == "bytrail":
                return False
            if not self.manager.get_modified_tasks():
                return False
        elif action in ("refresh_board", "sync_remote"):
            # By-Trail rebinds `r` and `s` to trail-specific actions with
            # truthful footer labels; the generic pair is hidden there so the
            # duplicate-key fall-through reaches them (t1268).
            if self.base_filter == "bytrail":
                return False
        elif action in ("trail_refresh_local", "trail_refresh_drift",
                        "trail_refresh_agent", "trail_select", "trail_sync"):
            # The By-Trail half of the duplicate-key pairs — live only there.
            if self.base_filter != "bytrail":
                return False
            # Every refresh key needs a trail to act on: with none selected
            # each is an immediate no-op, and advertising it would break the
            # same truthful-footer contract this change exists to fix. `s`
            # (select) and `S` (sync) stay — they are how you get a trail, and
            # a remote sync is meaningful regardless (t1268).
            if (action in ("trail_refresh_local", "trail_refresh_drift",
                           "trail_refresh_agent")
                    and not self.active_trail_handle):
                return False
            # A confirmed launch is mid-baseline: `R` would spawn a second
            # agent for the same refresh, so it stops advertising itself.
            if action == "trail_refresh_agent" and self._trail_launch_pending:
                return False
        elif action == "trail_summary_expand":
            # Live only in By-Trail, and only when there is a summary to
            # expand — advertising `v` with nothing behind it would break the
            # truthful-footer contract the trail keys above follow. This gate
            # controls the footer and dispatch; `action_trail_summary_expand`
            # re-checks the same condition, because the action stays reachable
            # via the command palette, a remap, or a race with a view switch.
            if self.base_filter != "bytrail":
                return False
            if not trail_summary_text(self._trail_doc):
                return False
        elif action == "toggle_children":
            # The In-Flight, By-Topic and By-Trail views render every relevant
            # card (including children) directly — there is nothing to
            # expand/collapse — so hide the action there.
            if self.base_filter in ("inflight", "bytopic", "bytrail"):
                return False
            focused = self._focused_card()
            if not focused:
                # This also hides the action on a focused `GroupHeader`, which is
                # what makes the `x` duplicate-key pair exclusive: `_focused_card`
                # is a `TaskCard` isinstance read, so a header yields None here.
                # An explicit `isinstance(..., GroupHeader)` check above would be
                # dead code — a negative control proved it never changes the
                # answer (t1243_9). The `toggle_group` branch below owns the
                # positive half.
                return False
            if focused.is_child:
                return True  # Always show for child cards (they have a parent)
            task_num, _ = TaskCard._parse_filename(focused.task_data.filename)
            if not self.manager.get_child_tasks_for_parent(task_num):
                return False
        elif action == "toggle_group":
            # The GroupHeader half of the `x` duplicate-key pair (t1243_9). Live
            # ONLY on a header, so exactly one of the two is ever shown. The
            # derived views render no group headers, but gate them anyway so the
            # exclusion does not depend on that staying true.
            if self.base_filter in ("inflight", "bytopic", "bytrail"):
                return False
            return isinstance(self._focused_unit(), GroupHeader)
        elif action == "pick_task":
            focused = self._focused_card()
            if not focused:
                return False
        elif action == "work_report":
            # Work Report is column-scoped: only in persistent kanban views
            # (In-Flight / By-Topic / By-Trail render derived, non-column
            # lanes), and only when a focused card or column placeholder
            # (collapsed OR empty) identifies a column.
            if self.base_filter in ("inflight", "bytopic", "bytrail"):
                return False
            if self._get_focused_col_id() is None:
                return False
        elif action == "brainstorm_task":
            focused = self._focused_card()
            if not focused:
                return False
        elif action == "open_cross_repo":
            focused = self._focused_card()
            if not focused or not self._gather_cross_repo_refs(focused.task_data):
                return False  # Hide unless the focused task has cross-repo refs
        elif action in ("move_task_right", "move_task_left", "move_task_up", "move_task_down",
                        "move_task_top", "move_task_bottom"):
            # NOTE: Textual's Footer hides a binding only when check_action returns
            # False; None leaves it *shown but greyed*. Task movement only applies
            # to the persistent kanban columns — the In-Flight, By-Topic and
            # By-Trail views render derived, non-reorderable lanes — so return
            # False to hide it. (By-Trail move-to-column commands are t1210_5.)
            if self.base_filter in ("inflight", "bytopic", "bytrail"):
                return False
            focused = self._focused_card()
            if focused and focused.is_child:
                return False  # Hide movement actions for child cards
        elif action == "toggle_mark":
            # Marking feeds bulk column moves (t1243_7) and group membership
            # (t1243_12) — both parent-level column operations. In-Flight,
            # By-Topic and By-Trail render derived, non-reorderable lanes, so
            # there is nothing there to mark. False (not None) so the footer
            # HIDES it, matching the movement gate above.
            #
            # Deliberately NOT gated on focused.is_child, unlike movement: a
            # child card keeps the binding so action_toggle_mark can EXPLAIN the
            # refusal instead of the key silently doing nothing.
            #
            # Also deliberately absent from the ghost pre-gate above: ghosts are
            # mounted only by TrailColumn, which only the By-Trail path mounts,
            # so is_ghost implies base_filter == "bytrail" and this branch
            # already covers them. Adding it there would be unreachable code.
            if self.base_filter in ("inflight", "bytopic", "bytrail"):
                return False
        elif action == "move_to_column":
            # By-Trail is resolved ENTIRELY on focus, and deliberately BEFORE
            # the marked-set early return below (t1210_5): `toggle_mark` is
            # hidden in this view and `_set_base_filter` clears the set on
            # entry, so a mark cannot exist here. Gating first STATES that
            # invariant rather than depending on it holding forever. There is
            # no column-placeholder fallback either — a wave lane is not a
            # column. The ghost check rides on the SAME `_focused_card()` this
            # branch already fetches, rather than on the pre-gate above, which
            # would read focus a second time and on every view.
            if self.base_filter == "bytrail":
                focused = self._focused_card()
                return (focused is not None and not focused.is_child
                        and not getattr(focused, "is_ghost", False))
            # Hidden wherever movement is hidden — the remaining derived views
            # render non-reorderable lanes.
            if self.base_filter in ("inflight", "bytopic"):
                return False
            # Deliberately returns True EARLY on a non-empty marked set, unlike
            # every other gate here (which only ever return False): `m` acts on
            # the marked set regardless of what currently holds focus, so the
            # focus checks below must not veto it. Do not "normalize" this away
            # — MoveGatingTests pins the focused-child-with-marks case. It is
            # also the cheap path: it returns before any DOM query runs.
            if self.marked:
                return True
            # ONE `_focused_card()` call, deliberately not `_get_focused_col_id()`
            # followed by `_focused_card()`: that pair issues the whole-board
            # `query("TaskCard:focus")` TWICE, and check_action runs once per
            # binding on every refresh_bindings() — i.e. on every focus change
            # during a move. `_focused_placeholder()` reads `screen.focused`
            # and costs nothing, so the fallback stays free.
            focused = self._focused_card()
            if focused is not None:
                # Matches the movement gate: a child is not movable, and with
                # no marks there is nothing else for `m` to act on.
                return not focused.is_child
            # No card, but a collapsed/empty column placeholder still names a
            # source column to scope the review to.
            return self._focused_placeholder() is not None
        elif action == "trail_move_wave":
            # `M` (t1210_5): live only in By-Trail, on a live card. Like the
            # `move_to_column` branch above, the ghost check rides on this
            # branch's own `_focused_card()` rather than on the pre-gate — one
            # focus read, and none at all outside By-Trail.
            #
            # Deliberately NOT gated on `focused.is_child`, unlike `m`: `M`
            # acts on the WAVE, and a focused child still names a wave whose
            # parent entries are perfectly movable. The "wave holds nothing
            # movable" case is reported BY THE ACTION, not hidden here — it
            # needs the lane's entry list, and a DOM walk in check_action would
            # undo the measured hot-path fix t1243_7 made (this runs once per
            # binding on every refresh_bindings()).
            if self.base_filter != "bytrail":
                return False
            focused = self._focused_card()
            return (focused is not None
                    and not getattr(focused, "is_ghost", False))
        elif action in ("move_col_right", "move_col_left", "toggle_column_collapsed"):
            if self.base_filter in ("inflight", "bytopic", "bytrail"):
                return False
        elif action in ("column_manage", "merge_columns"):
            # Board-scoped, not card-scoped: In-Flight / By-Topic / By-Trail
            # render derived lanes rather than columns, so column management is
            # meaningless there. Deliberately NOT `work_report`'s gate — that
            # one ALSO demands a focused column because it reports on one,
            # whereas this dialog edits the column LIST. Gating on focus would
            # make it dead on an empty or filter-emptied board, which is exactly
            # when the user needs "Add". It also keeps this branch free of any
            # DOM query: check_action runs once per binding on every
            # refresh_bindings(), and that path is measured (t1243_7).
            if self.base_filter in ("inflight", "bytopic", "bytrail"):
                return False
        elif action == "trail_task":
            # Trail create/refresh launch: needs a focused task card in a view
            # where the card identifies a scope (normal views: the task itself;
            # By-Topic: the focused card's lane root). Hidden in In-Flight and
            # in By-Trail itself (there `r` is the refresh launch).
            if self.base_filter in ("inflight", "bytrail"):
                return False
            if not self._focused_card():
                return False
        elif action == "sort_topic":
            # Lane sort order only applies to the by-topic swimlane view. Return
            # False (not None) so the key is hidden — not greyed — elsewhere.
            if self.base_filter != "bytopic":
                return False
        return True

    def compose(self):
        header = Header()
        header.can_focus = False
        yield header
        with Horizontal(id="filter_area"):
            with Container(id="view_col"):
                yield Static("Task filter", id="view_label")
                yield ViewSelector(
                    self.base_filter,
                    self.git_filter_active,
                    self.type_filter_active,
                    id="view_selector",
                )
                yield Static("", id="type_filter_summary", classes="type-filter-summary hidden")
            yield Input(placeholder="Search tasks... (Tab to focus, Esc to return to board)", id="search_box")
        yield HorizontalScroll(id="board_container")
        # By-Trail summary pane (t1505_1). A fixed-height FLOW child yielded
        # between the lanes and the footer — NEVER `dock: bottom`. Textual's
        # Footer sets that dock and MultiRowFooter overrides only layout/height
        # without unsetting it, so a docked pane would land at the footer's
        # offset and silently paint over it while both still reported
        # display=True, visible=True and a correct region (t1278).
        #
        # Starts hidden: `display` and the body text are owned solely by
        # _refresh_trail_summary(), so the pane costs the board no height in any
        # view but By-Trail. Not focusable — the board anchors startup focus on
        # a TaskCard (t1491) and every card-navigation query is
        # "TaskCard:focus"; a focusable container here would join the tab order
        # and strand that model. The full text stays reachable via `v`.
        # markup=False: the body carries FREE-FORM trail prose. Static defaults
        # to markup=True, and Textual's Content parser silently deletes an
        # unrecognised tag — a literal "[blocked]" or "[risk_mitigation]"
        # vanishes — while a bracketed URL raises MarkupError out of
        # _refresh_subtitle and breaks the whole By-Trail refresh. The flag is
        # belt-and-braces with the Text() in _refresh_trail_summary: either
        # alone is sufficient, together no future caller can reintroduce it.
        summary = VerticalScroll(
            Static("", id="trail_summary_body", markup=False),
            id="trail_summary")
        summary.display = False
        summary.can_focus = False
        yield summary
        # Multi-row footer (t1418): the board declares more shown bindings than
        # one row holds, and stock Textual clips the overflow into a
        # mouse-wheel-only scroll region. `hint_action` (not a literal key) lets
        # the "+N more" affordance name whatever key is bound to the shortcuts
        # editor, including after a user remap.
        footer = MultiRowFooter(hint_action="open_shortcuts_editor")
        footer.can_focus = False
        yield footer

    def get_default_screen(self) -> Screen:
        """Use `BoardScreen`, whose auto-focus is off — see that class (t1491)."""
        return BoardScreen()

    def on_mount(self):
        self.refresh_board(refresh_locks=True)
        self._start_auto_refresh_timer()
        self._update_subtitle()
        self._apply_filter_reflow()
        # Anchor focus on a card (t1491). `BoardScreen` has already stopped
        # `#search_box` from taking it; this gives the keyboard a real board
        # target so card navigation and the focus-gated bindings work from the
        # first keystroke. Deferred for the same reason `apply_filter` is:
        # `refresh_board` mounts the columns asynchronously, so their focus
        # anchors are not queryable yet.
        self.call_after_refresh(self._claim_startup_focus)

    def _apply_filter_reflow(self, width: int | None = None):
        """Reflow the filter row when the terminal is too narrow for both parts.

        The filter segments are never truncated (`#view_col` is auto-width); the
        search box is what yields, dropping onto its own line below the
        threshold. The threshold is derived from the ViewSelector's own rendered
        width, so adding a base filter or rebinding a key moves it automatically
        (t1247).
        """
        try:
            selector = self.query_one("#view_selector", ViewSelector)
            area = self.query_one("#filter_area")
        except Exception:
            return
        width = self.size.width if width is None else width
        if width <= 0:
            # Pre-layout size; on_resize will fire again with the real width.
            return
        # +2 for #view_selector's `padding: 0 1`.
        needed = selector.content_width() + 2 + self.FILTER_SEARCH_MIN_WIDTH
        area.set_class(width < needed, "narrow")

    def on_resize(self, event):
        self._apply_filter_reflow(event.size.width)
        # The banner is composed against the header's available width, so a
        # resize invalidates it: without this a board dragged narrower keeps a
        # banner budgeted for the old width and clips the freshness marker
        # again (t1278).
        self._refresh_subtitle()

    def _start_auto_refresh_timer(self):
        """Start or restart the auto-refresh timer based on current settings."""
        self._stop_auto_refresh_timer()
        minutes = self.manager.auto_refresh_minutes
        if minutes > 0:
            self._auto_refresh_timer = self.set_interval(
                minutes * 60, self._auto_refresh_tick, name="auto_refresh"
            )

    def _stop_auto_refresh_timer(self):
        """Stop the current auto-refresh timer if one is running."""
        if self._auto_refresh_timer is not None:
            self._auto_refresh_timer.stop()
            self._auto_refresh_timer = None

    def _auto_refresh_tick(self):
        """Called by the timer. Refresh only if no modal is active.

        Routes to the passive data path — never action_refresh_board, whose
        By-Trail branch opens an agent-launch dialog (keyboard-only)."""
        if self._modal_is_active():
            return
        if self.manager.settings.get("sync_on_refresh", False) and DATA_WORKTREE.exists():
            self._run_sync(show_notification=False)
        else:
            self._refresh_board_data()

    def _update_subtitle(self):
        """Update the app subtitle (delegates to the single composer)."""
        self._refresh_subtitle()

    def _banner_budget(self) -> int:
        """Cells available to `sub_title` on the header row (0 = unknown).

        Read off the live HeaderTitle rather than a hardcoded inset: the inset
        is Textual's (header icon plus the clock reservation) and would drift
        on upgrade, or if `show_clock` were ever enabled. Queried by CSS type
        selector so no private `textual.widgets._header` import is needed.

        Returns 0 before the first layout (and if the Header is ever removed),
        which callers treat as "cannot budget" and skip elision — degrading to
        the untruncated string rather than guessing a width."""
        try:
            usable = self.query_one("HeaderTitle").content_region.width
        except Exception:
            return 0
        # " — " is the separator HeaderTitle puts between title and sub_title.
        return max(0, usable - cell_len(str(self.title)) - 3)

    def _refresh_board_data(self):
        """Reload task files from disk and refresh the board.

        The passive data path shared by the `r` key (outside By-Trail), the
        auto-refresh timer, and programmatic callers — never opens dialogs."""
        focused = self._focused_card()
        refocus = focused.task_data.filename if focused else ""
        self.manager.load_tasks()
        if self.base_filter == "locked":
            self._auto_expand_locked()
        self.refresh_board(refocus_filename=refocus, refresh_locks=True)

    def action_refresh_board(self):
        """`r` outside By-Trail: refresh board data.

        In By-Trail this action is hidden by check_action and the key falls
        through to action_trail_refresh_local (t1268)."""
        self._refresh_board_data()

    def refresh_board(self, refocus_filename: str = "", refresh_locks: bool = False,
                      refocus_col_id: str = ""):
        # Default the column fallback to whatever holds focus right now, so every
        # caller (manual `r`, the auto-refresh tick, view switches) preserves an
        # empty / collapsed column without opting in. Must be read HERE: the
        # teardown below removes the focused widget, and Textual drops focus with it.
        refocus_col_id = refocus_col_id or self._get_focused_col_id() or ""
        self.manager.refresh_git_status()
        if refresh_locks:
            self.manager.refresh_lock_map()
        self.manager.clear_gate_cache()
        # New refresh cycle: drop cached cross-repo dep statuses so cards
        # re-probe live status (cards repopulate the cache on render).
        self.manager.xdep_status_cache.clear()

        # Prune marks to tasks still on the board — never clear (t1243_6). This
        # runs on the auto-refresh tick too, so wholesale clearing would let an
        # unattended timer silently discard the user's selection. Report what was
        # dropped for the same reason: a mark vanishing because another session
        # archived the task must not be invisible. Fires only when something was
        # actually removed, so a stable board stays quiet; a view switch clears
        # first, so it never fires for that.
        dropped = self.marked.retain(self.manager.task_datas.keys())
        if dropped:
            shown = ", ".join(sorted(dropped)[:3])
            self.notify(
                f"Unmarked {len(dropped)} task(s) no longer on the board: "
                f"{shown}" + ("…" if len(dropped) > 3 else ""),
                severity="warning")

        container = self.query_one("#board_container")
        container.remove_children()

        if self.base_filter == "inflight":
            # Both the buckets and the render order come from INFLIGHT_LANES
            # (t1603_3) — a second literal tuple here is how a lane ends up
            # grouped but never mounted.
            grouped = {lane: [] for lane in INFLIGHT_LANES}
            for item in self.manager.get_inflight_items():
                grouped[item.group].append(item)
            for group in INFLIGHT_LANES:
                container.mount(InFlightColumn(group, grouped[group], self.manager))
            self.call_after_refresh(self.apply_filter)
            self._queue_refocus(refocus_filename, refocus_col_id)
            return

        if self.base_filter == "bytopic":
            all_tasks = (list(self.manager.task_datas.values())
                         + list(self.manager.child_task_datas.values()))
            for label, members in self.manager.grouped_topic_lanes(
                    all_tasks, self._topic_sort_mode()):
                container.mount(TopicColumn(label, members, self.manager))
            self.call_after_refresh(self.apply_filter)
            self._queue_refocus(refocus_filename, refocus_col_id)
            return

        if self.base_filter == "bytrail":
            self._render_bytrail(container)
            self.call_after_refresh(self.apply_filter)
            self._queue_refocus(refocus_filename, refocus_col_id)
            return

        # 1. Unordered/Backlog Column (Dynamic)
        unordered_tasks = self.manager.get_column_tasks("unordered")
        if unordered_tasks:
            is_collapsed = self.manager.is_column_collapsed("unordered")
            container.mount(KanbanColumn(
                "unordered", "Unsorted / Inbox", "gray", self.manager,
                self.expanded_tasks, collapsed=is_collapsed,
                collapsed_groups=self.collapsed_groups,
            ))

        # 2. Configured Columns
        for col_id in self.manager.column_order:
            conf = next((c for c in self.manager.columns if c["id"] == col_id), None)
            if conf:
                is_collapsed = self.manager.is_column_collapsed(col_id)
                container.mount(KanbanColumn(
                    conf["id"], conf["title"], conf["color"], self.manager,
                    self.expanded_tasks, collapsed=is_collapsed,
                    collapsed_groups=self.collapsed_groups,
                ))

        # Defer until after Textual processes pending mounts so the freshly
        # composed TaskCards are queryable; otherwise view-mode filters silently
        # no-op and every card stays visible.
        self.call_after_refresh(self.apply_filter)

        # Restore focus by task filename, else by column identity
        self._queue_refocus(refocus_filename, refocus_col_id)

    def _refocus_card(self, filename: str, fallback_col_id: str = ""):
        """Focus the card for `filename`; fall back to its column if it is gone.

        A refresh can drop the card entirely (task archived/deleted) or hide it
        (filtered out), in which case focus would otherwise be lost.
        """
        for card in self.query(TaskCard):
            if card.task_data.filename == filename and card.styles.display != "none":
                card.focus()
                # `TaskCard.on_focus` scrolls synchronously (t1248), but
                # `scroll_visible` silently does nothing for a widget with no
                # size — and a card MOUNTED IN THIS CYCLE has none yet, so the
                # transplant's card would end up focused but off-screen
                # (t1243_5). Guarded on the missing layout, so every path whose
                # card is already laid out is untouched.
                if not card.region.area:
                    self._scroll_into_view_after_layout(card)
                return
        if fallback_col_id:
            self._refocus_column(fallback_col_id)

    #: Refresh hops to wait for a just-mounted card's layout before giving up on
    #: scrolling it into view. Measured need is 2 (the size lands on the third
    #: callback); the margin absorbs a slower frame without ever spinning.
    _SCROLL_LAYOUT_HOPS = 5

    def _scroll_into_view_after_layout(self, card, hops: int = _SCROLL_LAYOUT_HOPS):
        """Scroll `card` into view once the layout pass has given it a size.

        A card mounted by `_transplant_block` has no size until the screen's
        next layout, and `scroll_visible` is a silent no-op until then. The
        recompose path never hit this: it drops its mount awaitables, so its
        deferred refocus naturally lands after the pump has done the layout.
        Awaiting the mount inside the action instead BLOCKS that pump, so the
        refocus runs two hops early.

        Re-queues until the card is laid out, bounded so a card that never gets
        a size — filtered out, or its column removed underneath it — cannot spin.
        """
        if card.region.area:
            card.scroll_visible(animate=False, immediate=True)
            return
        if hops > 0 and card.is_attached:
            self.call_after_refresh(self._scroll_into_view_after_layout,
                                    card, hops - 1)

    def _queue_refocus(self, refocus_filename: str = "", refocus_col_id: str = ""):
        """Queue a post-refresh focus restore: by task filename, else by column."""
        if refocus_filename:
            self.call_after_refresh(self._refocus_card, refocus_filename, refocus_col_id)
        elif refocus_col_id:
            self.call_after_refresh(self._refocus_column, refocus_col_id)

    def _recompose_column(self, col_widget: KanbanColumn):
        """Replace a column's children in-place using textual.compose.

        Keeps the KanbanColumn shell in the DOM (no layout shift) and only
        swaps its inner content (header + task cards).
        """
        col_widget.collapsed = self.manager.is_column_collapsed(col_widget.col_id)
        col_widget.remove_children()
        new_children = _compose_widgets(col_widget)
        col_widget.mount_all(new_children)

    def refresh_column(self, col_id: str, refocus_filename: str = "",
                       refocus_col_id: str = ""):
        """Re-render a single column's contents without layout changes."""
        # See refresh_board: read the focused column before the recompose.
        refocus_col_id = refocus_col_id or self._get_focused_col_id() or ""
        old_col = None
        for col in self.query(KanbanColumn):
            if col.col_id == col_id:
                old_col = col
                break

        if old_col is None:
            # Column not on screen — check if it should appear
            if col_id == "unordered" and self.manager.get_column_tasks("unordered"):
                self.refresh_board(refocus_filename=refocus_filename,
                                   refocus_col_id=refocus_col_id)
            return

        # Check if unordered column should disappear
        if col_id == "unordered" and not self.manager.get_column_tasks("unordered"):
            old_col.remove()
            self._queue_refocus(refocus_filename, refocus_col_id)
            return

        self._recompose_column(old_col)

        # Defer (see refresh_board for rationale): _recompose_column remounts
        # cards, so applying the filter synchronously here would race compose.
        # Scoped: only this column was recomposed, so only its units need deciding.
        self.call_after_refresh(self.apply_filter, {col_id})
        self._queue_refocus(refocus_filename, refocus_col_id)

    def refresh_columns(self, col_ids: set, refocus_filename: str = "",
                        refocus_col_id: str = ""):
        """Re-render multiple columns. Falls back to full refresh for structural changes."""
        # See refresh_board: read the focused column before the recompose.
        refocus_col_id = refocus_col_id or self._get_focused_col_id() or ""
        # Check if unordered needs structural add/remove
        if "unordered" in col_ids:
            has_widget = any(c.col_id == "unordered" for c in self.query(KanbanColumn))
            has_tasks = bool(self.manager.get_column_tasks("unordered"))
            if has_widget != has_tasks:
                self.refresh_board(refocus_filename=refocus_filename,
                                   refocus_col_id=refocus_col_id)
                return

        for col_id in col_ids:
            for col in self.query(KanbanColumn):
                if col.col_id == col_id:
                    self._recompose_column(col)
                    break

        # Defer (see refresh_board for rationale): _recompose_column remounts
        # cards, so applying the filter synchronously here would race compose.
        # Scoped: only these columns were recomposed.
        self.call_after_refresh(self.apply_filter, set(col_ids))
        self._queue_refocus(refocus_filename, refocus_col_id)

    @on(Input.Changed, "#search_box")
    def on_search(self, event: Input.Changed):
        self.search_filter = event.value.lower()
        self.apply_filter()

    def _filter_units(self, cols):
        """The widgets whose visibility a filter pass decides (t1243_4).

        Yields `TaskCard`s today. t1243_10 adds its collapsed-group header HERE, as a
        second query filtered the same way — `apply_filter`'s accumulator reads only
        `.column_id`, so neither the loop nor the scoping needs rewriting.

        **Scoping filters one whole-DOM query rather than resolving column widgets.**
        The obvious implementation — `self._column_widget(col_id).query(TaskCard)` per
        column — is a pessimization on Textual 8.2.7, because `query()` walks the whole
        tree whatever it is rooted at. Measured on a 200-card board: `_column_widgets()`
        is four full-tree class queries at ~25 ms, against ~7 ms for the single
        `query(TaskCard)` used here and ~13 ms for the entire unscoped pass. Resolving
        columns made a "scoped" pass cost 128 ms — an order of magnitude MORE than the
        whole-board pass it replaced. The saving that is actually available is the
        per-unit work (predicate + display write), not the traversal.
        """
        for card in self.query(TaskCard):
            if cols is None or card.column_id in cols:
                yield card

    def _filter_placeholders(self, cols):
        """`EmptyColumnPlaceholder`s a filter pass may flip, scoped like `_filter_units`."""
        for placeholder in self.query(EmptyColumnPlaceholder):
            if cols is None or placeholder.column_id in cols:
                yield placeholder

    def _filter_group_headers(self, cols):
        """`GroupHeader`s a filter pass may flip, scoped like `_filter_units` (t1243_9).

        A SEPARATE generator rather than an extension of `_filter_units`, because
        `apply_filter`'s unit loop reads `unit.task_data` and a header has no
        such attribute — it carries `members` instead. Same single-query,
        filter-by-`column_id` shape, so the scoping rules are identical.
        """
        for header in self.query(GroupHeader):
            if cols is None or header.column_id in cols:
                yield header

    def _children_by_parent(self) -> dict:
        """`{parent_num: [child Task, …]}` for the whole board, built in ONE pass.

        Deliberately not `TaskManager.get_child_tasks_for_parent` per parent:
        that helper re-scans `child_task_datas`, regex-matches every child
        against an f-string-built pattern and `sorted()`s the result — and the
        sort is meaningless for a membership test. Calling it once per
        non-matching grouped member would make a filter pass
        O(members x children) with a regex per pair, on a path that runs on every
        search keystroke. `get_parent_num_for_child` is an O(1)
        `filepath.parent.name`, so the whole index costs one linear walk.

        Keyed by the same form `TaskCard._parse_filename(parent.filename)[0]`
        yields — the pairing `KanbanColumn.task_block` already relies on.
        """
        index = {}
        for child in self.manager.child_task_datas.values():
            index.setdefault(
                self.manager.get_parent_num_for_child(child), []).append(child)
        return index

    def _any_child_matches(self, task, visible, search: str,
                           child_index) -> bool:
        """Whether ANY child of `task` passes the filter (t1469).

        THE single child-aware primitive: the group-header rule
        (`_group_header_matches`) and the parent-card rule (`apply_filter`'s unit
        loop) are both "matches itself OR this returns True", so a change here
        moves them together instead of letting them diverge — which is exactly
        how the ungrouped case was left broken when t1243_9 fixed the header.

        The FULL `task_matches_filter` predicate is applied to the child — base
        set AND search, not search alone. A parent is therefore re-admitted only
        by a child the current view would actually show, which is what makes
        "a visible `↳` row always has a visible parent above it" hold for every
        filter dimension rather than for search alone.

        `child_index` is the per-pass `_children_by_parent()` map. The empty-map
        fast path is what keeps a childless board from paying a filename parse
        per card on the per-keystroke path.
        """
        if not child_index:
            return False
        num, _ = TaskCard._parse_filename(task.filename)
        if not num:
            return False
        return any(task_matches_filter(c, visible, search)
                   for c in child_index.get(num, ()))

    def _group_header_matches(self, header, visible, search: str,
                              child_index) -> bool:
        """A header is visible iff >= 1 member — or >= 1 member's CHILD — matches.

        ONE formula for both states, which is what keeps a collapsed group
        findable by exactly the text that would find it expanded: an expanded
        group's members mount cards (decided in the unit loop) and a collapsed
        group's mount none, but the member DATA answers either way.

        CHILD-AWARE because `Task.search_haystack` is `"<filename> <metadata>"` —
        a parent's corpus does NOT contain its children's text. The child half is
        delegated to `_any_child_matches`, which `apply_filter`'s parent-card
        rule also calls: since t1469 a header and the parent card underneath it
        answer to the same formula, so neither can be made child-aware without
        the other.

        `child_index` is a ZERO-ARG CALLABLE that builds the per-pass index on
        first use and memoizes it (t1469). Members are tested first and
        short-circuit, so it is invoked only for a group whose own members all
        failed — which is what keeps a header-bearing board with no filter
        active from paying for the walk at all.
        """
        members = header.members
        if any(task_matches_filter(m, visible, search) for m in members):
            return True
        index = child_index()
        return any(self._any_child_matches(m, visible, search, index)
                   for m in members)

    def _group_match_count(self, header, visible, search: str,
                           child_index) -> int:
        """How many members the EXPANDED group would show — the `· N match` badge.

        NOT a second visibility predicate: it composes the SAME two primitives
        the rest of the pass does (`task_matches_filter`, then
        `_any_child_matches`), member by member, so it answers per member exactly
        what `apply_filter`'s unit loop answers for a mounted parent card. The
        badge therefore promises "this many cards appear if you expand", not some
        private notion of matching, and `count > 0` is equivalent to
        `_group_header_matches` by construction.

        Kept SEPARATE from `_group_header_matches` because that rule
        short-circuits on the first matching member and never reaches the child
        index for a group that matched cheaply — the early exit that keeps a
        per-keystroke pass off the child walk. Counting cannot short-circuit, so
        it is confined by the caller to the narrow path: an actually narrowing
        filter, a COLLAPSED header, and a header the pass is keeping visible.
        With no filter active it is never called.

        `child_index` is the pass's memoized zero-arg builder, shared with both
        loops, so a pass still builds the index at most once.
        """
        matched = 0
        for member in header.members:
            if task_matches_filter(member, visible, search):
                matched += 1
            elif self._any_child_matches(member, visible, search, child_index()):
                matched += 1
        return matched

    def apply_filter(self, cols: set | None = None):
        """Apply base filter ∩ active add-ons ∩ search.

        `cols is None` is the whole-board pass every view / filter toggle needs: a
        filter-state change is global, so every card must be re-decided.

        A `cols` set restricts the pass to those columns — their units, their
        placeholders and their focus rescue (t1243_4). Movement paths use it, because
        a move can only change what the columns it touched display. A scoped pass must
        never flip a placeholder in an untouched column: the cards backing that
        decision were not re-evaluated, so `cols_with_visible` says nothing about it.

        **A parent card is CHILD-AWARE (t1469):** it is shown when it matches
        itself *or* when any of its children passes the composed predicate. That
        overrides EVERY dimension, base filters included — a parent
        `_free_visible_set` excluded is re-admitted by a child that view would
        show. The four `_*_visible_set` helpers therefore compute membership but
        no longer decide alone what renders.

        **Scope of the invariant this buys.** What becomes derivable is *a
        visible `.child-wrapper` row always has a visible parent card above it*,
        and that row shape exists only in `KanbanColumn.task_block`. By-Topic and
        By-Trail mount a child as an ordinary top-level card whose parent may not
        be in the lane or wave at all; the rescue still shows a parent that IS
        mounted there, but no parent-visibility invariant is claimed for them.
        """
        if self.base_filter in ("inflight", "bytopic", "bytrail"):
            visible = None
        elif self.base_filter == "locked":
            visible = self._locked_visible_set()
        elif self.base_filter == "free":
            visible = self._free_visible_set()
        else:  # "all"
            visible = None  # sentinel — all cards eligible

        if self.git_filter_active:
            git_set = self._git_visible_set()
            visible = git_set if visible is None else visible & git_set

        if self.type_filter_active:
            type_set = self._type_visible_set()
            visible = type_set if visible is None else visible & type_set

        # `_children_by_parent()` is built AT MOST ONCE per pass and only when a
        # decision needs it: a unit that matched its own corpus never reaches a
        # child lookup, so a board with no filter active still pays nothing.
        index_cache = []

        def child_index():
            if not index_cache:
                index_cache.append(self._children_by_parent())
            return index_cache[0]

        cols_with_visible = set()
        # Columns that mounted at least one unit this pass, visible or not. It is
        # what separates "a filter emptied this column" from "this column holds
        # nothing" for the placeholder label below (t1491) — one bit, immune to
        # the row-vs-task counting ambiguity a number would carry.
        cols_with_units = set()
        for unit in self._filter_units(cols):
            cols_with_units.add(unit.column_id)
            v = task_matches_filter(unit.task_data, visible, self.search_filter)
            # A child unit is never rescued: children have no children, and in
            # By-Topic / By-Trail child tasks mount as top-level cards. Read with
            # `getattr` for the same reason `set_unit_display` does — a future
            # non-TaskCard unit needs no branch added here.
            if not v and not getattr(unit, "is_child", False):
                v = self._any_child_matches(unit.task_data, visible,
                                            self.search_filter, child_index())
            set_unit_display(unit, v)
            if v:
                cols_with_visible.add(unit.column_id)

        # Group headers (t1243_9). MUST run before the placeholder loop below,
        # which reads `cols_with_visible`: a collapsed group mounts a header and
        # no member cards, so without this a column holding only collapsed groups
        # would contribute nothing, wrongly show its EmptyColumnPlaceholder, and
        # end up with TWO focus anchors.
        #
        # Shares the unit loop's lazy index (t1469) — the builder is passed in
        # rather than its result, so a header whose own members match never
        # triggers the walk, and a grouped board pays for at most one.
        #
        # A filter only NARROWS when something can be excluded: `visible is None`
        # is the all-eligible sentinel and an empty search matches every corpus.
        # Computed once per pass — it is what keeps an idle board from walking a
        # single member for the badge, since the count cannot short-circuit.
        narrowing = visible is not None or bool(self.search_filter)
        headers = list(self._filter_group_headers(cols))
        for header in headers:
            # Counted as a unit for the same reason it feeds `cols_with_visible`:
            # a COLLAPSED group mounts a header and no member cards, so without
            # this a column holding only collapsed groups would look unpopulated
            # to the placeholder label and read "(empty)" while holding tasks.
            cols_with_units.add(header.column_id)
            v = self._group_header_matches(header, visible, self.search_filter,
                                           child_index)
            set_unit_display(header, v)
            if v:
                cols_with_visible.add(header.column_id)
            # The badge is a COLLAPSED group's substitute for the member cards it
            # does not mount: an expanded group hides its non-matching members
            # individually, so the count is already on screen there. Shown only
            # when PARTIAL — `· 3 match` under `(3)` repeats what the header
            # already says. `n >= 1` whenever `v` is True, because both rules read
            # the same members through the same primitives and the same index.
            count = None
            if narrowing and v and header.collapsed:
                n = self._group_match_count(header, visible, self.search_filter,
                                            child_index)
                if n < len(header.members):
                    count = n
            header.set_match_count(count)

        # A column showing no content falls back to its focusable placeholder,
        # labelled with WHY it is blank (t1491). The label is set before the
        # display flip so a placeholder never becomes visible carrying the
        # previous pass's reason.
        for placeholder in self._filter_placeholders(cols):
            show = placeholder.column_id not in cols_with_visible
            if show:
                placeholder.set_filtered(placeholder.column_id in cols_with_units)
            set_unit_display(placeholder, show)

        # Focus must never rest on a widget this pass just hid. Textual does not
        # move it for us: Screen.set_focus gates on `visible` (the visibility
        # rule), not on `display`. A scoped pass can only have hidden something in
        # `cols`; anything already hidden elsewhere was rescued by the pass that
        # hid it.
        focused = self.screen.focused if self.screen else None
        if (isinstance(focused, (TaskCard, GroupHeader, EmptyColumnPlaceholder))
                and (cols is None or focused.column_id in cols)
                and focused.styles.display == "none"):
            self._refocus_column(focused.column_id)

    def _is_busy(self, filename: str, task) -> bool:
        """A task is busy when status==Implementing OR present in lock_map."""
        if task.metadata.get('status') == 'Implementing':
            return True
        task_num, _ = TaskCard._parse_filename(filename)
        return task_num.lstrip('t') in self.manager.lock_map

    def _locked_visible_set(self) -> set:
        """Tasks visible in locked view: busy tasks plus context grouping.

        A task is busy when status==Implementing OR present in lock_map.
        When a *child* is busy, also include the parent and all siblings —
        preserves the existing context-view UX (see what's in flight + its
        surrounding work). Inverse of `_free_visible_set()` at the leaf level.

        Membership only: `apply_filter`'s child-aware rule can still SHOW a
        parent this set excludes, when one of its children is in it — see
        `_any_child_matches` (t1469).
        """
        visible = set()

        # Parent tasks that are themselves busy.
        for filename, task in self.manager.task_datas.items():
            if self._is_busy(filename, task):
                visible.add(filename)

        # Busy children + parent + sibling grouping.
        for filename, task in self.manager.child_task_datas.items():
            if self._is_busy(filename, task):
                visible.add(filename)
                parent_num = self.manager.get_parent_num_for_child(task)
                parent = self.manager.find_task_by_id(parent_num)
                if parent:
                    visible.add(parent.filename)
                for sib in self.manager.get_child_tasks_for_parent(parent_num):
                    visible.add(sib.filename)

        return visible

    def _free_visible_set(self) -> set:
        """Tasks visible in free view: not busy, with parent cascade.

        Children: shown when the child itself is not busy.
        Parents: shown only when the parent itself is not busy AND no child
        is busy.

        Membership only: `apply_filter`'s child-aware rule can still SHOW a
        parent this set excludes, when one of its children is in it — see
        `_any_child_matches` (t1469). A busy parent whose children are free
        therefore does render in this view, above those children.
        """
        visible = set()

        for filename, task in self.manager.child_task_datas.items():
            if not self._is_busy(filename, task):
                visible.add(filename)

        for filename, task in self.manager.task_datas.items():
            if self._is_busy(filename, task):
                continue
            task_num, _ = TaskCard._parse_filename(filename)
            children = self.manager.get_child_tasks_for_parent(task_num)
            if any(self._is_busy(c.filename, c) for c in children):
                continue
            visible.add(filename)

        return visible

    def _git_visible_set(self) -> set:
        """Tasks visible in git/integration view.

        Membership only: `apply_filter`'s child-aware rule can still SHOW a
        parent this set excludes, when one of its children is in it — see
        `_any_child_matches` (t1469).
        """
        visible = set()
        for filename, task in self.manager.task_datas.items():
            if task.metadata.get('issue') or task.metadata.get('pull_request'):
                visible.add(filename)
        for filename, task in self.manager.child_task_datas.items():
            if task.metadata.get('issue') or task.metadata.get('pull_request'):
                visible.add(filename)
        return visible

    def _type_visible_set(self) -> set:
        """Tasks visible in issue-type view (matches selected types).

        Membership only: `apply_filter`'s child-aware rule can still SHOW a
        parent this set excludes, when one of its children is in it — see
        `_any_child_matches` (t1469).
        """
        selected = set(self.manager.settings.get("filter_issue_types", []))
        if not selected:
            return set()
        visible = set()
        for filename, task in self.manager.task_datas.items():
            if task.metadata.get('issue_type', 'feature') in selected:
                visible.add(filename)
        for filename, task in self.manager.child_task_datas.items():
            if task.metadata.get('issue_type', 'feature') in selected:
                visible.add(filename)
        return visible

    def _refresh_type_filter_summary(self):
        """Show selected types under the ViewSelector when type add-on is on."""
        try:
            summary = self.query_one("#type_filter_summary", Static)
        except Exception:
            return
        selected = self.manager.settings.get("filter_issue_types", [])
        if self.type_filter_active and selected:
            summary.update(f"types: {', '.join(sorted(selected))}")
            summary.remove_class("hidden")
        else:
            summary.update("")
            summary.add_class("hidden")

    # --- View Filters: base radio + add-on toggles ---

    def action_view_all(self):
        self._set_base_filter("all")

    def action_view_locked(self):
        self._set_base_filter("locked")

    def action_view_free(self):
        if self.base_filter == "inflight" and isinstance(self._focused_card(), InFlightTaskCard):
            self._record_focused_human_gate("fail")
            return
        self._set_base_filter("free")

    def action_view_inflight(self):
        self._set_base_filter("inflight")

    def action_view_bytopic(self):
        self._set_base_filter("bytopic")

    def action_view_bytrail(self):
        self._set_base_filter("bytrail")

    def _topic_sort_mode(self) -> str:
        """The persisted by-topic lane sort mode, validated against the known
        set (unknown/missing → 'recency')."""
        mode = self.manager.settings.get("topic_sort_mode", "recency")
        return mode if mode in TOPIC_SORT_MODES else "recency"

    def action_sort_topic(self):
        """Open the by-topic sort-order picker (By-Topic view only). Persists the
        choice and re-renders (a cache hit → re-sort, no rebuild)."""
        if self.base_filter != "bytopic":
            return

        def on_dismiss(mode):
            if mode is None or mode == self._topic_sort_mode():
                return
            self.manager.settings["topic_sort_mode"] = mode
            self.manager.save_settings()   # settings-only — never the project layer
            focused = self._focused_card()
            refocus = focused.task_data.filename if focused else ""
            self.refresh_board(refocus_filename=refocus)

        self.push_screen(TopicSortModeScreen(self._topic_sort_mode()), on_dismiss)

    def action_view_git(self):
        if self.base_filter == "inflight" and isinstance(self._focused_card(), InFlightTaskCard):
            self.action_gate_resume()
            return
        self._toggle_git_filter()

    def action_view_type(self):
        self._toggle_type_filter()

    def _open_type_filter_dialog(self):
        """Open the type-picker modal. Used both when toggling type on and
        when the user wants to reconfirm/edit the type selection."""
        types = _load_task_types()
        initial = self.manager.settings.get("filter_issue_types", [])

        def on_dismiss(result):
            if result is None:
                # Cancel / Esc — keep current state & selection unchanged.
                return
            if not result:
                # Empty confirm → clear selection and disable the add-on.
                self.manager.settings["filter_issue_types"] = []
                self.manager.save_settings()   # settings-only
                self.type_filter_active = False
                self._refresh_selector()
                self._refresh_type_filter_summary()
                self._update_search_placeholder()
                self.apply_filter()
                return
            self.manager.settings["filter_issue_types"] = sorted(result)
            self.manager.save_settings()   # settings-only
            self.type_filter_active = True
            self._refresh_selector()
            self._refresh_type_filter_summary()
            self._update_search_placeholder()
            self.apply_filter()

        self.push_screen(IssueTypeFilterScreen(types, initial), on_dismiss)

    def _set_base_filter(self, name: str):
        """Switch the base radio (a/l/f). No-op when already active."""
        if name == self.base_filter:
            return
        old = self.base_filter
        self.base_filter = name

        # A view switch discards the selection (t1243_6). Cleared BEFORE the
        # refresh_board below so re-mounted cards paint unmarked — and so that
        # refresh's prune sees an empty set and never notifies for a view change.
        self.marked.clear()

        # Manage auto-expansion for the locked context-view.
        if old == "locked":
            self.expanded_tasks -= self._view_auto_expanded
            self._view_auto_expanded.clear()
        if name == "locked":
            self._auto_expand_locked()

        # The inflight view reads live on-disk gate state, so entering it should
        # re-read task files + refresh the lock map (refresh_board already
        # refreshes git status and clears the gate cache). This is the same data
        # refresh as pressing 'r'. Only the transition INTO the view refreshes —
        # re-selecting it is a no-op via the early return above.
        #
        # By-topic deliberately does NOT force a disk reload: it builds from the
        # in-memory tasks like all/locked/free (anchor edits already update them
        # in-memory; 'r' / auto-refresh pick up external changes). Forcing a
        # full re-read here made entering the view noticeably slow.
        refresh_locks = False
        if name == "inflight":
            self.manager.load_tasks()
            refresh_locks = True

        # By-Trail supersession token: entering AND leaving are re-entry
        # points — in-flight discovery/drift results from the previous
        # generation must not mutate the new view's state.
        if name == "bytrail" or old == "bytrail":
            self._trail_gen += 1
        if old == "bytrail" and name != "bytrail":
            # Leaving the view: nothing left to reload into (t1268).
            self._stop_trail_watch()
        if name == "bytrail":
            # Entering the view invalidates the discovery cache. The auto-open
            # below passes rescan=False, so without this a user who opened the
            # selector, pressed Esc, left and came back would be served the
            # stale handle list — the t1365 symptom reached without ever
            # pressing `s`. Costs a scan only when the selector actually opens.
            self._trail_infos = None
            if self.active_trail_handle is None:
                # Entering with no active trail opens the selection flow
                # (RFC §9.1) once the empty-state board has rendered.
                self.call_after_refresh(self._open_trail_select)
            elif self._trail_doc is not None and not self._trail_error:
                self._start_trail_drift()

        self._refresh_selector()
        self._update_search_placeholder()

        # Re-render board with new expansion state, then filter.
        focused = self._focused_card()
        refocus = focused.task_data.filename if focused else ""
        self.refresh_board(refocus_filename=refocus, refresh_locks=refresh_locks)
        self._refresh_subtitle()
        # The By-Trail duplicate-key bindings carry view-specific footer
        # labels; Textual's Footer only relabels on the bindings_updated
        # signal, which refresh_bindings() publishes (t1268).
        self.refresh_bindings()

    def _toggle_git_filter(self):
        """Flip the git add-on. No board re-render needed."""
        self.git_filter_active = not self.git_filter_active
        self._refresh_selector()
        self._update_search_placeholder()
        self.apply_filter()

    def _toggle_type_filter(self):
        """Flip the type add-on.

        Turning ON always re-opens the type-picker dialog so the user can
        reconfirm or edit the selection. Turning OFF requires no dialog.
        """
        if self.type_filter_active:
            self.type_filter_active = False
            self._refresh_selector()
            self._refresh_type_filter_summary()
            self._update_search_placeholder()
            self.apply_filter()
        else:
            self._open_type_filter_dialog()

    def _refresh_selector(self):
        """Push current filter state into the ViewSelector widget."""
        try:
            selector = self.query_one("#view_selector", ViewSelector)
        except Exception:
            return
        selector.active_base = self.base_filter
        selector.git_on = self.git_filter_active
        selector.type_on = self.type_filter_active
        selector.refresh()
        # Label widths can change under a shortcut rebind — re-evaluate the
        # reflow threshold against the selector's current width (t1247).
        self._apply_filter_reflow()

    def _compute_search_placeholder(self) -> str:
        if self.base_filter == "inflight":
            base = "Search in-flight tasks"
        elif self.base_filter == "locked":
            base = "Search locked tasks"
        elif self.base_filter == "free":
            base = "Search free tasks"
        elif self.base_filter == "bytopic":
            base = f"Search topics · sort: {self._topic_sort_mode()}"
        elif self.base_filter == "bytrail":
            base = "Search trail entries"
        else:
            base = "Search tasks..."
        addons = []
        if self.git_filter_active:
            addons.append("git")
        if self.type_filter_active:
            addons.append("type")
        if addons:
            base += " + " + " + ".join(addons)
        if self.base_filter == "all" and not addons:
            base += " (Tab to focus, Esc to return to board)"
        else:
            # Derived from the same table the selector renders, so a rebind or a
            # new base filter can't leave this hint stale (t1247).
            keys = "/".join(
                k for k in (resolve_key("board", action_id)
                            for action_id, _, _ in ViewSelector.BASES) if k
            )
            base += f" ({keys} to switch base)" if keys else " (see filter row to switch base)"
        return base

    def _update_search_placeholder(self):
        try:
            search_box = self.query_one("#search_box", Input)
        except Exception:
            return
        search_box.placeholder = self._compute_search_placeholder()

    def _auto_expand_locked(self):
        """Auto-expand parents that have busy (locked or Implementing) children."""
        self._view_auto_expanded.clear()
        for filename, task in self.manager.task_datas.items():
            task_num, _ = TaskCard._parse_filename(filename)
            children = self.manager.get_child_tasks_for_parent(task_num)
            has_busy = any(self._is_busy(c.filename, c) for c in children)
            if has_busy and filename not in self.expanded_tasks:
                self._view_auto_expanded.add(filename)
                self.expanded_tasks.add(filename)

    # --- Focus & Navigation ---

    def action_focus_search(self):
        """Toggle focus between search box and board."""
        search_box = self.query_one("#search_box", Input)
        if search_box.has_focus:
            self.action_focus_board()
        else:
            search_box.focus()

    def _first_board_focus_target(self):
        """Leftmost column's focus anchor (card / group header / placeholder).

        Returns None when no column has one — an empty board. Shared by the
        Escape action and the startup claim below so the "which widget IS the
        board" rule lives in one place.
        """
        for col_id in self._get_visible_col_ids():
            target = self._column_focus_target(col_id)
            if target is not None:
                return target
        return None

    def action_focus_board(self):
        """Escape: close modal if active, otherwise return to board from search."""
        if self._modal_is_active():
            if hasattr(self.screen, "handle_escape"):
                self.screen.handle_escape()
            else:
                self.screen.dismiss()
            return
        target = self._first_board_focus_target()
        if target is not None:
            target.focus()

    def _claim_startup_focus(self) -> None:
        """Anchor startup focus on the board's leftmost card (t1491).

        `BoardScreen.AUTO_FOCUS` already stops `#search_box` from claiming the
        keyboard; this is the positive half — giving focus a real board target
        so card navigation and the focus-gated bindings (`m`, `x`, `enter`, …)
        work from the first keystroke instead of after a click.

        Unconditional apart from the modal guard: nothing else has legitimately
        claimed focus this early. A board with no anchor at all is left
        focus-less, which is safe — an unfocused screen routes keys to the App
        bindings, so `q` still quits.
        """
        if self._modal_is_active():
            return
        target = self._first_board_focus_target()
        if target is not None:
            target.focus()
        elif self.screen is not None:
            self.screen.set_focus(None)

    def _focused_card(self):
        """Return the currently focused TaskCard, or None.

        An attribute read, not a query: the `:focus` pseudo-class matches
        exactly one widget — the screen's focused one — so
        `query("TaskCard:focus")` walked the whole board to find something
        `screen.focused` already names. Same idiom `_focused_placeholder`
        has always used.

        This is a hot path, not a micro-optimisation: `check_action` runs once
        per binding on every `refresh_bindings()` — i.e. on every focus change
        during a move — and roughly ten of its gates call this helper, most of
        them twice (once in the ghost pre-gate, once in their own branch).
        Measured on a 60-card fixture board: **27 whole-board walks per footer
        sweep**, 59 ms, now zero. t1243_7 added the 28th and tipped
        `test_board_movement`'s attribution benchmark over its 25 ms
        cross-run threshold, which is what surfaced this.
        """
        focused = self.screen.focused if self.screen else None
        return focused if isinstance(focused, TaskCard) else None

    def _focused_unit(self):
        """The focused navigation UNIT — a `TaskCard` or a `GroupHeader` (t1243_9).

        An attribute read, NOT a query, for exactly the reason `_focused_card`
        documents above: `check_action` runs its gates once per binding on every
        `refresh_bindings()`, i.e. on every focus change during a move. The
        obvious `query("TaskCard:focus, GroupHeader:focus").first()` would walk
        the whole board to find what `screen.focused` already names, undoing
        t1243_7's measured 27-walks-per-sweep fix.

        `_focused_card()` survives as the narrow "focused *task*" accessor that
        the task-level gates genuinely need; this is its unit-level sibling.
        """
        focused = self.screen.focused if self.screen else None
        return focused if isinstance(focused, (TaskCard, GroupHeader)) else None

    def _get_column_cards(self, col_id: str) -> list:
        """Return TaskCard widgets belonging to a column, in DOM order."""
        return [c for c in self.query(TaskCard) if c.column_id == col_id]

    def _visible_column_cards(self, col_id: str) -> list:
        """`_get_column_cards` filtered to cards the active filter left visible."""
        return [c for c in self._get_column_cards(col_id)
                if c.styles.display != "none"]

    def _get_column_units(self, col_id: str) -> list:
        """`TaskCard`s AND `GroupHeader`s of a column, in DOM order (t1243_9).

        ONE union query rather than two: a comma selector yields nodes in DOM
        order, which is what makes header -> member -> its children a single
        walk. Two separate queries would lose the relative order between headers
        and cards, and vertical navigation is exactly that order.

        Filtered on the `column_id` ATTRIBUTE, not DOM containment — the same
        rule `_get_column_cards` uses, which is why an expanded child card
        (mounted inside a `.child-wrapper`) is included here too. That is
        deliberate: children are navigation stops today and must stay so.
        """
        return [w for w in self.query(_UNIT_SELECTOR) if w.column_id == col_id]

    def _visible_column_units(self, col_id: str) -> list:
        """`_get_column_units` filtered to units the active filter left visible."""
        return [w for w in self._get_column_units(col_id)
                if w.styles.display != "none"]

    def _column_widgets(self) -> list:
        """Every board column widget currently mounted, in board order.

        Single source for the column-class union so `_get_visible_col_ids` and
        `_column_widget` cannot drift apart when a new column class is added.
        """
        return (list(self.query(KanbanColumn))
                + list(self.query(InFlightColumn))
                + list(self.query(TopicColumn))
                + list(self.query(TrailColumn)))

    def _column_widget(self, col_id: str):
        """Return the scroll container for `col_id`, or None.

        Resolved by identity rather than by walking a card's DOM ancestry: an
        expanded child card sits inside a `Horizontal(classes="child-wrapper")`,
        and `VerticalScroll` is also used for modal bodies, so a parent walk
        would bake in assumptions this does not.
        """
        return next((c for c in self._column_widgets() if c.col_id == col_id), None)

    @staticmethod
    def _rows_inside(viewport, region) -> bool:
        """True when `region`'s rows lie wholly within `viewport`'s rows.

        Vertical axis only, and deliberately so: `scrollable_content_region`
        shrinks by one column on the right the moment the vertical scrollbar
        appears, and a `width: 1fr` child card can round a cell wide, so testing
        x yields permanent false negatives. The columns scroll vertically, so
        horizontal containment carries no information here.
        """
        return viewport.y <= region.y and region.bottom <= viewport.bottom

    def _card_fully_visible(self, card) -> bool:
        """True when `card` lies wholly inside its column's viewport (t1248).

        Fails OPEN (True) for an unlaid-out card or column, so a pre-layout or
        hidden card never triggers a re-anchor.
        """
        column = self._column_widget(card.column_id)
        if column is None:
            return True
        viewport = column.scrollable_content_region
        region = card.region
        if not region.area or not viewport.area:
            return True
        return self._rows_inside(viewport, region)

    def _viewport_anchor(self, cards: list, focused):
        """The card to re-anchor focus onto when `focused` scrolled out of view.

        Candidates are the cards fully inside the viewport; when there are NONE
        — a pane too short to show one whole card — fall back to the cards
        merely overlapping it. Without that fallback there would be no anchor,
        the caller would step from the off-screen index, and the snap-back this
        exists to prevent would return.

        The side the focus fell off picks the end, not the key direction: with
        focus above the viewport an `up` key must still land on the topmost
        visible card, not the bottom one. Returns None when the side cannot be
        determined or no candidate exists.
        """
        column = self._column_widget(focused.column_id)
        if column is None:
            return None
        viewport = column.scrollable_content_region
        focus_region = focused.region
        if not focus_region.area or not viewport.area:
            return None
        laid_out = [c for c in cards if c.region.area]
        inside = [c for c in laid_out if self._rows_inside(viewport, c.region)]
        candidates = inside or [c for c in laid_out if c.region.overlaps(viewport)]
        if not candidates:
            return None
        return candidates[0] if focus_region.y < viewport.y else candidates[-1]

    def _reanchor_to_viewport(self, focused, cards) -> bool:
        """Pull the cursor back to what is on screen; True when focus moved.

        When the viewport has scrolled away from the focused card, one nav key
        brings the cursor to the viewport instead of dragging the view back to
        the cursor. Returns False — so the caller steps normally — when the card
        is already visible, when the anchor resolves to the focused card itself
        (a card taller than the viewport), or when no anchor exists, so a nav
        key is never a dead end.
        """
        if self._card_fully_visible(focused):
            return False
        anchor = self._viewport_anchor(cards, focused)
        if anchor is None or anchor is focused:
            return False
        anchor.focus()
        return True

    def _focused_placeholder(self):
        """Return the focused column placeholder (collapsed or empty), or None."""
        focused = self.screen.focused if self.screen else None
        if isinstance(focused, (CollapsedColumnPlaceholder, EmptyColumnPlaceholder)):
            return focused
        return None

    def _column_placeholder(self, col_id: str):
        """Return a column's placeholder widget (collapsed or empty), or None."""
        for cls in (CollapsedColumnPlaceholder, EmptyColumnPlaceholder):
            for widget in self.query(cls):
                if widget.column_id == col_id:
                    return widget
        return None

    def _column_focus_target(self, col_id: str, preferred_pos: int = 0):
        """Return the widget to focus when entering `col_id`, or None.

        Every board column owns exactly one focus anchor: a placeholder when it
        shows no UNITS, otherwise its first visible unit. The `display` checks
        are load-bearing — `Widget.focus()` does not refuse a hidden widget.

        Restated over units by t1243_9. It previously read "cards", and a column
        of only COLLAPSED GROUPS — which mounts headers and no cards at all —
        therefore returned `None`: `_refocus_column` then silently did nothing
        and focus was lost. That case is why the unit abstraction exists.
        """
        placeholder = self._column_placeholder(col_id)
        if placeholder is not None and placeholder.styles.display != "none":
            return placeholder
        units = self._visible_column_units(col_id)
        if units:
            return units[min(preferred_pos, len(units) - 1)]
        return None

    def _refocus_column(self, col_id: str):
        """Restore focus to a column by identity (used after a refresh)."""
        target = self._column_focus_target(col_id)
        if target is not None:
            target.focus()

    def _get_visible_col_ids(self) -> list:
        """Return ordered list of column IDs currently on the board."""
        return [col.col_id for col in self._column_widgets()]

    def _modal_is_active(self):
        return isinstance(self.screen, ModalScreen)

    def _repaint_card_mark(self, card) -> None:
        """Repaint ONE card's ✓/□ in place — no recompose, no board-wide query.

        Scoped to the card's own subtree deliberately: t1243_4 measured a
        whole-board `query(TaskCard)` at ~6.8 ms, and exactly one card changes
        per keypress. The other direction (a card rebuilt by a transplant or a
        refresh) is handled at construction by `TaskCard._is_marked`.
        """
        labels = card.query(".task-mark")
        if not labels:
            return
        marked = card.task_data.filename in self.marked
        label = labels.first()
        label.update(mark_markup(marked))
        label.set_class(marked, "task-marked")

    def action_toggle_mark(self) -> None:
        """`space`: toggle the focused parent card's mark (t1243_6)."""
        # Textual does not dispatch App BINDINGS while a ModalScreen is active
        # (see monitor/monitor_shared.py), and the SelectionList modals own
        # `space` for their own toggling — but this is the house idiom and a
        # test pins it.
        if self._modal_is_active():
            return
        # Re-check the view gate inside the action, not only in check_action:
        # a binding gate is not an action guard.
        if self.base_filter in ("inflight", "bytopic", "bytrail"):
            return
        card = self._focused_card()
        if card is None:
            return
        if card.is_child:
            # Refuse with a reason — never a silent nothing. This is the ONE
            # reachable non-markable card in the kanban views.
            self.notify("Child tasks move with their parent — mark the parent instead.",
                        severity="warning")
            return
        if not getattr(card, "markable", False):
            # Unreachable today: every non-child card KanbanColumn mounts is
            # markable, and the derived views (the only source of In-Flight /
            # Trail / ghost cards) returned above. Fail closed rather than
            # marking something the parent-only persistence API would refuse.
            return
        self.marked.toggle(card.task_data.filename)
        self._repaint_card_mark(card)

    def action_clear_marks(self) -> None:
        """Palette 'Clear Selection': unmark everything and repaint (t1243_7)."""
        if self._modal_is_active():
            return
        if not self.marked:
            self.notify("Nothing marked")
            return
        cleared = set(self.marked.marked)
        self.marked.clear()
        # Scoped to the cards that actually changed: only these need a repaint,
        # and t1243_4 measured a whole-board TaskCard query at ~6.8 ms.
        for card in self.query(TaskCard):
            if card.task_data.filename in cleared:
                self._repaint_card_mark(card)
        self.notify(f"Cleared {len(cleared)} mark(s)")

    def _reject_stale(self, filenames) -> bool:
        """True (and notifies) when a name no longer resolves to a parent task.

        **Fail closed — never drop the dead names and proceed.** Silently
        omitting them would move the surviving subset of what the user
        selected: exactly the partial application `move_tasks_to_column`'s
        all-or-nothing contract exists to prevent, and the review dialog would
        not even show what went missing.

        Marks are deliberately **retained**: `r` (`refresh_board`) prunes them
        and reports which ones went, which is what t1243_6 gave
        `MarkedSelection.retain()` a return value for. Clearing here would
        destroy a selection the user may still want after a refresh.
        """
        stale = [n for n in filenames if n not in self.manager.task_datas]
        if not stale:
            return False
        if all(n in self.manager.child_task_datas for n in stale):
            # Structurally unreachable today (every source is parent-only — see
            # `_review_then`), but if a child ever arrives, say the true reason.
            self.notify("Child tasks move with their parent — move the parent instead.",
                        severity="warning")
            return True
        self.notify("Selection is stale — no longer on the board: "
                    + ", ".join(stale[:3]) + ("…" if len(stale) > 3 else "")
                    + ". Press r to refresh, then retry.", severity="error")
        return True

    def _review_then(self, filenames, on_confirm) -> None:
        """Show `filenames` in MoveTaskSelectScreen, then hand the kept ones on.

        Every name is resolvable past `_reject_stale`, so no row is silently
        dropped — what the dialog lists IS the selection. Child rows are
        excluded **structurally**, by the three sources rather than by a filter
        here: `action_toggle_mark` refuses to mark a child, the focused-card
        path gates on `is_child`, and `get_column_tasks` reads `task_datas`
        (parents only).
        """
        if self._reject_stale(filenames):
            return
        rows = []
        for name in filenames:
            task = self.manager.task_datas[name]
            task_num, task_name = TaskCard._parse_filename(name)
            label = (f"[{self._column_title(task.board_col)}] "
                     f"{task_num or name} {task_name}").rstrip()
            rows.append((name, label))
        # No `if not rows` guard: past `_reject_stale` the row count EQUALS the
        # input count, and every caller already rejects an empty selection. A
        # guard here could never fire, and one that reads like a live check is
        # worse than none.

        def on_tasks(selected):
            if selected is None:
                return                              # Esc — cancelled cleanly
            if not selected:
                self.notify("No tasks selected")    # confirmed with none checked
                return
            on_confirm(selected)

        self.push_screen(MoveTaskSelectScreen(rows), on_tasks)

    def _choose_move_destination(self, filenames) -> None:
        """Offer the destination columns for `filenames`, then apply the move.

        A METHOD, not the local closure it grew from (t1210_5):
        `action_trail_move_wave` hands it to `_review_then` as the confirm
        callback, and a closure defined inside `action_move_to_column` is not
        reachable from there. Both move commands therefore drive ONE
        implementation of the destination chain rather than two copies that
        could drift.
        """
        # Built AFTER the review: the redundant-column filter depends on
        # the confirmed target set, not on the pre-review one.
        dests = self._move_destination_columns(filenames)
        if not dests:
            self.notify("Nowhere to move to — every other column is "
                        "collapsed, and the selection already sits where "
                        "it is.", severity="warning")
            return
        self.push_screen(
            ColumnSelectScreen(self.manager, "Move to", columns=dests),
            lambda col_id: self._apply_move_to_column(filenames, col_id),
        )

    def action_move_to_column(self) -> None:
        """`m`: move the marked task(s) — or the focused card — to a column.

        In By-Trail (t1210_5) it acts on the focused card alone: no marks can
        exist there, and a wave lane has no column placeholder to fall back to.
        """
        if self._modal_is_active():
            return
        # Re-check the view gate INSIDE the action, not only in check_action:
        # the command palette invokes action_* directly and never consults it.
        if self.base_filter in ("inflight", "bytopic"):
            return

        focused = self._focused_card()
        # Ghost guard — BEFORE any target derivation, and unconditional
        # (is_ghost is False on every non-trail card, so this costs nothing
        # elsewhere and cannot be missed if ghosts ever render in another
        # view). check_action hides `m` on a ghost, but that is only the
        # BINDING gate — the palette calls action_* directly, the same reason
        # the view gate above is re-checked. Without this, `_GhostTaskStub`'s
        # synthetic `trail-ghost-<ref>.md` flows into `_reject_stale`, which
        # would blame a stale selection and tell the user to press `r` — about
        # a member that is simply read-only, and that no refresh can ever make
        # movable.
        if focused is not None and getattr(focused, "is_ghost", False):
            self.notify("Archived, missing and cross-repo trail members are "
                        "read-only — there is no local task file to move.",
                        severity="warning")
            return
        if focused is not None and focused.is_child and not self.marked:
            # Refuse with a reason — never a silent nothing (t1243_6 idiom).
            self.notify("Child tasks move with their parent — move the parent instead.",
                        severity="warning")
            return
        focused_name = (focused.task_data.filename
                        if focused is not None and not focused.is_child else None)
        targets = self.marked.effective(focused_name)

        if self.base_filter == "bytrail":
            # Focused card only. The marked-set and column-placeholder paths
            # below have no meaning in a wave lane, so this branch skips them
            # rather than letting `targets` fall through into them.
            if not focused_name:
                return
            if self._reject_stale([focused_name]):
                return
            self._choose_move_destination([focused_name])
            return

        if self.marked:
            # Marks survive a filter pass (t1243_6), so a marked card may be
            # hidden right now. REVIEW before acting — never move what the user
            # cannot see. This is the hidden-but-marked risk t1243_6 left here.
            self._review_then(self._board_order(targets),
                              self._choose_move_destination)
        elif targets:
            # One focused card: unambiguous, and visible by construction.
            if self._reject_stale(targets):
                return
            self._choose_move_destination(targets)
        else:
            # A column placeholder is focused (collapsed, or every card hidden
            # by the filter). Scope the review to that column, read straight
            # from task_datas so filtered-away tasks are exactly what becomes
            # visible again.
            #
            # A `GroupHeader` also names a column since t1243_9, but pointing at
            # a GROUP is not pointing at the column — acting on every task in it
            # would be a destructive surprise. `check_action` already hides `m`
            # here, yet that is only the BINDING gate: the command palette calls
            # `action_*` directly (see the view-gate re-check at the top of this
            # method), so the guard has to live in the action body.
            if isinstance(self._focused_unit(), GroupHeader):
                self.notify("Select tasks, or a column, to move — moving a whole "
                            "group as a block is not implemented yet (t1243_11).",
                            severity="warning")
                return
            col_id = self._get_focused_col_id()
            if col_id is None:
                return
            names = [t.filename for t in self.manager.get_column_tasks(col_id)]
            if not names:
                self.notify(f"No tasks in {self._column_title(col_id)}",
                            severity="warning")
                return
            self._review_then(names, self._choose_move_destination)

    def _apply_move_to_column(self, filenames, col_id) -> None:
        """Run the batch move and repaint. K writes, input order, K files."""
        if not col_id:
            return                              # Esc at the column picker
        # Snapshot the SOURCE columns before the move mutates board_col.
        src_cols = {t.board_col for t in
                    (self.manager.task_datas.get(n) for n in filenames) if t}
        result = self.manager.move_tasks_to_column(filenames, col_id)
        if result.refused:
            # All-or-nothing: NOTHING was written. `_reject_stale` already
            # screened the selection, so this is the POST-REVIEW window: the
            # user sits in the two modals while the auto-refresh timer (or
            # another session) removes a task, and the confirmed filename list
            # was captured in the closure before that happened.
            names = ", ".join(name for name, _ in result.refused)
            self.notify(f"Move refused, nothing written — no longer on the "
                        f"board: {names}. Press r to refresh.", severity="error")
            return
        # Clear BEFORE the refresh: refresh_board prunes-and-notifies, and an
        # already-empty set drops nothing, so no spurious warning fires. Same
        # ordering rationale as _set_base_filter in t1243_6.
        self.marked.clear()
        if self.base_filter == "bytrail":
            # By-Trail mounts TrailColumns, not KanbanColumns, and `src_cols`
            # names columns this view does not render — `refresh_columns` would
            # be looking for widgets that are not there. Nor is a re-render
            # needed: no By-Trail surface reads board_col/board_idx (the cards
            # show classification, status and drift), so the lanes cannot
            # change. `move_tasks_to_column` mutated the manager's Task objects
            # in place, so a later view switch renders the move with no reload
            # (t1210_5).
            self.notify(f"Moved {len(result.moved)} task(s) to "
                        f"{self._column_title(col_id)}")
            return
        self.refresh_columns(src_cols | {col_id},
                             refocus_filename=result.moved[-1],
                             refocus_col_id=col_id)
        self.notify(f"Moved {len(result.moved)} task(s) to "
                    f"{self._column_title(col_id)}")

    def action_nav_up(self):
        if self._modal_is_active():
            self.screen.focus_previous()
            return
        # Units, not cards (t1243_9): `↑`/`↓` step through every navigation stop
        # — group headers, parent cards and expanded child cards — in DOM order.
        focused = self._focused_unit()
        if not focused:
            # If on a column placeholder, up/down is a no-op
            if self._focused_placeholder():
                return
            self.action_focus_board()
            return
        units = self._visible_column_units(focused.column_id)
        if self._reanchor_to_viewport(focused, units):
            return
        idx = next((i for i, c in enumerate(units) if c is focused), -1)
        if idx > 0:
            units[idx - 1].focus()

    def action_nav_down(self):
        if self._modal_is_active():
            self.screen.focus_next()
            return
        focused = self._focused_unit()
        if not focused:
            if self._focused_placeholder():
                return
            self.action_focus_board()
            return
        units = self._visible_column_units(focused.column_id)
        if self._reanchor_to_viewport(focused, units):
            return
        idx = next((i for i, c in enumerate(units) if c is focused), -1)
        if idx < len(units) - 1:
            units[idx + 1].focus()

    def action_nav_left(self):
        if self._modal_is_active():
            focused = self.screen.focused
            # Duck-type: any widget exposing cycle_prev() qualifies.
            # The board defines its own CycleField; modal screens pushed by
            # the board (e.g. ProfileEditScreen from lib/profile_editor.py)
            # define a separate CycleField with the same API. isinstance
            # against the board-local class would miss the modal's.
            cycle_prev = getattr(focused, "cycle_prev", None)
            if callable(cycle_prev):
                cycle_prev()
            return
        self._nav_lateral(-1)

    def action_nav_right(self):
        if self._modal_is_active():
            focused = self.screen.focused
            cycle_next = getattr(focused, "cycle_next", None)
            if callable(cycle_next):
                cycle_next()
            return
        self._nav_lateral(1)

    def _get_focused_col_id(self):
        """Return the column ID of the focused element (unit or placeholder).

        Unit-level since t1243_9, so a focused `GroupHeader` names its column
        instead of returning `None`. Every caller inherits that: lateral nav,
        `_shift_column`, the column-collapse actions, the work-report flow and
        the refresh refocus fallbacks all become reachable from a header, which
        is intended. The ONE caller for which it is not is
        `action_move_to_column`, whose no-card branch means "a column
        PLACEHOLDER is focused" — it carries its own explicit guard.
        """
        focused = self._focused_unit()
        if focused:
            return focused.column_id
        placeholder = self._focused_placeholder()
        if placeholder:
            return placeholder.column_id
        return None

    def _nav_lateral(self, direction: int):
        cur_col = self._get_focused_col_id()
        if not cur_col:
            self.action_focus_board()
            return
        col_ids = self._get_visible_col_ids()
        if cur_col not in col_ids:
            return
        cur_idx = col_ids.index(cur_col)
        focused = self._focused_unit()
        # Try to land on the same vertical position in the target column —
        # measured from what is ON SCREEN. After a wheel scroll the focused card
        # can be far off-screen, and carrying its index across would teleport the
        # target column to a position the user never looked at (t1248).
        # Indexed over NAVIGATION STOPS (t1243_9), so a group header occupies a
        # position like any other unit and `←`/`→` preserve it unchanged.
        old_units = self._visible_column_units(cur_col)
        source = focused
        if source is not None and not self._card_fully_visible(source):
            source = self._viewport_anchor(old_units, source) or source
        old_pos = next((i for i, c in enumerate(old_units) if c is source), 0) if source else 0
        # Find the next column with a focus anchor
        new_idx = cur_idx + direction
        while 0 <= new_idx < len(col_ids):
            target = self._column_focus_target(col_ids[new_idx], old_pos)
            if target is not None:
                target.focus()
                return
            new_idx += direction

    # --- Actions ---

    def action_view_details(self):
        focused = self._focused_card()
        if not focused:
            return
        # By-Trail cards (live and ghost) open the trail detail projection,
        # not the task editor (RFC §9.1).
        if self._open_trail_entry_detail(focused):
            return
        self.open_task_detail(focused.task_data, source_card=focused)

    def open_task_detail(self, task, read_only=None, source_card=None):
        """Push a TaskDetailScreen wired to the shared result handler.

        This is the ONLY sanctioned way to open a task detail screen. Every
        nested navigation (dependency / parent / child / verifies / folded
        pickers) routes through here so the screen's dismiss-result (pick,
        edit, rename, …) is always acted on. Pushing a TaskDetailScreen
        without this callback silently drops the action (t1062).

        ``read_only`` defaults to the task's archived state. ``source_card`` is
        the originating board TaskCard when the detail is opened from the board
        (None for nested opens); it keeps the post-action refresh identical to
        the board's historical behavior.
        """
        if read_only is None:
            read_only = getattr(task, "archived", False)
        self.push_screen(
            TaskDetailScreen(task, self.manager, read_only=read_only),
            lambda result: self._on_detail_result(task, result, source_card),
        )

    def replace_screen_with_detail(self, task, read_only=None):
        """Dismiss the current screen (a picker) and open ``task``'s detail in
        its place.

        Picker items select a task and then want to swap the picker for that
        task's detail. Doing ``self.screen.dismiss()`` immediately followed by a
        ``push_screen(..., callback)`` *within the item's key handler* pushes the
        screen but drops the result callback (Textual processes the dismiss and
        the push in the same message, and the new screen's callback is lost).
        Deferring the open with ``call_later`` lets the dismiss settle first, so
        ``open_task_detail`` attaches the result callback correctly and actions
        (pick, edit, …) fire from a picker-opened detail (t1062).
        """
        self.screen.dismiss()
        self.call_later(self.open_task_detail, task, read_only)

    def _on_detail_result(self, task_data, result, source_card=None):
        if result == "edit":
            self.run_editor(task_data.filepath)
        elif result == "edit_plan":
            plan_path = self._resolve_plan_path_for(task_data)
            if plan_path:
                self.run_editor(plan_path)
        elif result == "pick":
            task_num, _ = TaskCard._parse_filename(task_data.filename)
            if task_num:
                full_cmd = self._resolve_pick_command(task_num)
                if full_cmd:
                    num = task_num.lstrip("t")
                    prompt_str = f"/aitask-pick {num}"
                    agent_string = resolve_agent_string(Path("."), "pick")
                    screen = AgentCommandScreen(
                        f"Pick Task t{num}", full_cmd, prompt_str,
                        default_window_name=f"agent-pick-{num}",
                        project_root=Path("."),
                        operation="pick",
                        operation_args=[num],
                        default_agent_string=agent_string,
                        skill_name="pick",
                        default_profile=self._resolve_pick_profile(),
                    )
                    def on_pick_result(pick_result):
                        if pick_result == "run":
                            self.run_dialog_command(
                                screen.full_command,
                                refocus_filename=task_data.filename)
                        elif isinstance(pick_result, TmuxLaunchConfig):
                            _, err = launch_in_tmux(screen.full_command, pick_result)
                            if err:
                                self.notify(err, severity="error")
                            elif pick_result.new_window:
                                maybe_spawn_minimonitor(pick_result.session, pick_result.window)
                        self.refresh_board(refocus_filename=task_data.filename)
                    self.push_screen(screen, on_pick_result)
                    return
            self.run_aitask_pick(task_data.filename)
        elif result == "brainstorm":
            task_num, _ = TaskCard._parse_filename(task_data.filename)
            if task_num:
                num = task_num.lstrip("t")
                self._launch_brainstorm(num, task_data.filename)
                return
        elif result == "rename":
            def on_rename_result(rename_result):
                if rename_result and rename_result[0] == "rename":
                    new_name = rename_result[1]
                    self._rename_task(task_data, new_name)
            self.push_screen(
                RenameTaskScreen(task_data.filename), on_rename_result)
            return
        elif result == "delete_archive":
            task_num, _ = TaskCard._parse_filename(task_data.filename)
            is_child = task_data.filepath.parent.name.startswith("t")
            _, paths = self._collect_delete_files(task_data)
            dep_warnings, related = self._check_task_dependencies(task_data, is_child)
            fate = self._build_fate_buckets(task_data)
            cascade_children = fate["cascade_children"]
            captured_task = task_data

            def on_action_chosen(action):
                if action == "delete":
                    self._execute_delete(task_num, paths, captured_task)
                elif action == "archive":
                    self._execute_archive(task_num, captured_task,
                                          cascade_children=cascade_children)
                else:
                    self.apply_filter()
                    self.call_after_refresh(self._refocus_card, captured_task.filename)

            self.push_screen(
                DeleteArchiveConfirmScreen(
                    task_data.filename,
                    delete_files=fate["delete_files"],
                    archive_kept=fate["archive_kept"],
                    archive_deleted=fate["archive_deleted"],
                    dep_warnings=dep_warnings,
                    related_tasks=related,
                    is_child=is_child,
                    blocking_files=fate["blocking_files"],
                    blocked_reason=fate["blocked_reason"],
                ),
                on_action_chosen,
            )
            return
        # Granular refresh: reload single task + refresh affected column(s).
        # Reached for edit / edit_plan / reverted / locked / unlocked / None.
        if not result and source_card is None:
            # Bare Back/Escape from a nested detail: stay passive. The screen has
            # already popped; just return to the parent detail (t1062).
            return
        needs_locks = result in ("locked", "unlocked")
        filename = task_data.filename
        self.manager.reload_task(filename)
        self.manager.refresh_git_status()
        if needs_locks:
            self.manager.refresh_lock_map()
        if source_card is not None:
            # Board path: refresh the originating card's visible column. Uses the
            # card's column_id (correct for expanded child cards) — unchanged from
            # the historical board behavior.
            old_col = source_card.column_id
            task = self.manager.task_datas.get(filename) or self.manager.child_task_datas.get(filename)
            new_col = task.board_col if task else old_col
            if new_col != old_col:
                self.refresh_columns({old_col, new_col}, refocus_filename=filename,
                                     refocus_col_id=new_col)
            else:
                self.refresh_column(old_col, refocus_filename=filename,
                                    refocus_col_id=old_col)
        else:
            # Nested/cardless action (e.g. revert/lock/unlock from a dependency
            # detail): the task may be filtered/off-board, so rebuild the whole
            # board; _refocus_card no-ops when no matching card exists.
            self.refresh_board(refocus_filename=filename)

    def _gather_cross_repo_refs(self, task):
        """Collect ordered, de-duplicated (repo, id) cross-repo references for
        a task: its xdeps/xdeprepo frontmatter (canonical) plus any
        ``<repo>#<id>`` notation found in the task body."""
        refs = []
        seen = set()
        meta = task.metadata
        xdeprepo = meta.get('xdeprepo')
        xdeps = meta.get('xdeps', []) or []
        if xdeprepo and xdeps:
            for xd in xdeps:
                key = (xdeprepo, str(xd).lstrip('t'))
                if key not in seen:
                    seen.add(key)
                    refs.append(key)
        for repo, task_id in parse_cross_repo_notation(task.content or ""):
            key = (repo, task_id)
            if key not in seen:
                seen.add(key)
                refs.append(key)
        return refs

    def _open_cross_repo_task(self, repo, task_id):
        """Resolve a cross-repo reference read-only and show it in a popup."""
        title, content, is_error = _resolve_cross_repo_task(repo, task_id)
        self.push_screen(CrossRepoTaskScreen(title, content, is_error))

    def action_open_cross_repo(self):
        """Open a cross-repo reference from the focused task (read-only).

        Gathers references from the task's xdeps frontmatter and body
        notation. Opens directly when there is exactly one; otherwise shows
        a picker. Never acquires a lock on the cross-repo task.
        """
        if self._modal_is_active():
            return
        focused = self._focused_card()
        if not focused:
            return
        refs = self._gather_cross_repo_refs(focused.task_data)
        if not refs:
            self.notify("No cross-repo references in this task.",
                        severity="information")
            return
        if len(refs) == 1:
            repo, task_id = refs[0]
            self._open_cross_repo_task(repo, task_id)
        else:
            self.push_screen(CrossRepoRefPickerScreen(refs))

    def action_pick_task(self):
        """Open pick command dialog for the focused task."""
        if self._modal_is_active():
            return
        focused = self._focused_card()
        if not focused:
            return
        task_num, _ = TaskCard._parse_filename(focused.task_data.filename)
        if not task_num:
            return
        num = task_num.lstrip("t")
        if self._focus_existing_agent_window(num):
            self.refresh_board(refocus_filename=focused.task_data.filename)
            return
        full_cmd = self._resolve_pick_command(task_num)
        if full_cmd:
            prompt_str = f"/aitask-pick {num}"
            agent_string = resolve_agent_string(Path("."), "pick")
            screen = AgentCommandScreen(
                f"Pick Task t{num}", full_cmd, prompt_str,
                default_window_name=f"agent-pick-{num}",
                project_root=Path("."),
                operation="pick",
                operation_args=[num],
                default_agent_string=agent_string,
                skill_name="pick",
                default_profile=self._resolve_pick_profile(),
            )
            def on_pick_result(pick_result):
                if pick_result == "run":
                    self.run_dialog_command(
                        screen.full_command,
                        refocus_filename=focused.task_data.filename)
                elif isinstance(pick_result, TmuxLaunchConfig):
                    _, err = launch_in_tmux(screen.full_command, pick_result)
                    if err:
                        self.notify(err, severity="error")
                    elif pick_result.new_window:
                        maybe_spawn_minimonitor(pick_result.session, pick_result.window)
                self.refresh_board(refocus_filename=focused.task_data.filename)
            self.push_screen(screen, on_pick_result)
        else:
            self.run_aitask_pick(focused.task_data.filename)

    def _work_report_columns(self) -> list:
        """Ordered (col_id, title) options for the work-report column picker.

        Mirrors the renderer's intersection (see refresh_board): Unsorted
        first when it has tasks, then only the column_order ids that have a
        columns definition — a stale order entry is not on the board and the
        gatherer would reject it as unknown_column.
        """
        cols = []
        if self.manager.get_column_tasks("unordered"):
            cols.append(("unordered", "Unsorted / Inbox"))
        for col_id in self.manager.column_order:
            conf = next((c for c in self.manager.columns if c["id"] == col_id), None)
            if conf:
                cols.append((conf["id"], conf["title"]))
        return cols

    # --- Move to column (t1243_7) ---

    def _move_destination_columns(self, filenames=()) -> list:
        """Col-conf dicts offered as a move destination for `filenames`.

        `ColumnSelectScreen` renders `id`/`title`/`color` dicts, so this returns
        confs — not the `(id, title)` pairs `_work_report_columns` builds for a
        SelectionList. Three filters, each matching an existing board contract:

        * `unordered` is hand-injected (it is not in `manager.columns`) and only
          while it holds tasks, exactly as `_move_task_lateral` and
          `action_collapse_column` build it. The column exists only while some
          task has no `boardcol`.
        * **Collapsed columns are excluded**, matching `_move_task_lateral`,
          which steps OVER a collapsed column and never lands in one. A
          collapsed destination would also swallow the cards on arrival,
          leaving `refresh_columns` a refocus target that is not rendered.
        * A column **every** target already sits in is excluded — picking it
          would be a pure "send to bottom" reorder, not a move. A column only
          SOME targets sit in stays: that is a real consolidation.
        """
        current = {self.manager.task_datas[n].board_col
                   for n in filenames if n in self.manager.task_datas}
        redundant = current if len(current) == 1 else set()

        cols = []
        if (self.manager.get_column_tasks("unordered")
                and not self.manager.is_column_collapsed("unordered")):
            cols.append({"id": "unordered", "title": "Unsorted / Inbox",
                         "color": "gray"})
        for col_id in self.manager.column_order:
            conf = self.manager.get_column_conf(col_id)  # None = stale entry
            if conf and not self.manager.is_column_collapsed(col_id):
                cols.append(conf)
        return [c for c in cols if c["id"] not in redundant]

    def _column_title(self, col_id: str) -> str:
        """Display title for a column, including the synthetic `unordered`."""
        if col_id == "unordered":
            return "Unsorted / Inbox"
        conf = self.manager.get_column_conf(col_id)
        return conf["title"] if conf else col_id

    def _board_order(self, filenames) -> list:
        """Sort filenames into rendered board order: column, then board index.

        `MarkedSelection.effective()` returns a FILENAME-sorted list precisely
        because it knows nothing about board geometry (t1243_6) — this is the
        re-sort its docstring instructs callers to do. Ordering is part of the
        contract: the destination sequence must match the presented sequence,
        and `move_tasks_to_column` preserves input order.

        The within-column key is `(normalize_board_idx, filename)` — the SAME
        key `get_column_tasks` sorts by, so a reviewed sequence cannot disagree
        with the rendered one.

        Ranks EVERY column, deliberately not `_move_destination_columns()`: a
        target can sit in a collapsed column, or in the one column that list
        filters out as redundant, and it must still sort where it renders.
        """
        rank = {"unordered": 0}
        rank.update({col_id: i + 1
                     for i, col_id in enumerate(self.manager.column_order)})
        last = len(rank)

        def key(name):
            task = self.manager.task_datas.get(name)
            if task is None:
                # Unresolvable sorts last; `_reject_stale` stops the flow
                # before such a name can reach a move.
                return (last, 0, name)
            return (rank.get(task.board_col, last),
                    normalize_board_idx(task.board_idx), name)

        return sorted(filenames, key=key)

    def action_work_report(self):
        """Open the work-report flow: columns → tasks → agent command dialog."""
        if self._modal_is_active():
            return
        focused_col = self._get_focused_col_id()
        if not focused_col:
            return
        columns = self._work_report_columns()

        def on_columns(col_ids):
            if col_ids is None:
                return  # Escape — cancelled cleanly
            if not col_ids:
                self.notify("No columns selected")
                return
            # Full column contents regardless of search/board filters —
            # get_column_tasks reads task_datas directly, in board order.
            entries = []
            for col_id in col_ids:
                for task in self.manager.get_column_tasks(col_id):
                    task_num, task_name = TaskCard._parse_filename(task.filename)
                    if not task_num:
                        continue
                    entries.append((col_id, task_num.lstrip("t"),
                                    f"[{col_id}] {task_num} {task_name}"))
            if not entries:
                self.notify("No tasks in the selected columns")
                return

            def on_tasks(selected):
                if selected is None:
                    return  # Escape — cancelled cleanly
                if not selected:
                    self.notify("No tasks selected")
                    return
                # The displayed grouped order is the reviewed sequence the
                # gatherer's task_order_changed check defends — never re-sort.
                cols_csv = ",".join(col_ids)
                tasks_csv = ",".join(task_id for _, task_id in selected)
                self._launch_work_report(cols_csv, tasks_csv)

            self.push_screen(WorkReportTaskSelectScreen(entries), on_tasks)

        self.push_screen(
            ColumnMultiSelectScreen(columns, focused_col), on_columns)

    def _launch_work_report(self, cols_csv: str, tasks_csv: str):
        """Resolve and launch /aitask-work-report with the reviewed selection."""
        op_args = ["--columns", cols_csv, "--tasks", tasks_csv]
        full_cmd = resolve_dry_run_command(Path("."), "work-report", *op_args)
        if not full_cmd:
            # Wrapper/config/timeout failure — never build a dialog around a
            # missing command; launch the reviewed selection directly instead.
            self.notify("Could not resolve agent command — launching directly")
            self.run_dialog_command(shlex.join(
                [str(CODEAGENT_SCRIPT), "invoke", "work-report", *op_args]))
            return
        prompt_str = f"/aitask-work-report --columns {cols_csv} --tasks {tasks_csv}"
        agent_string = resolve_agent_string(Path("."), "work-report")
        screen = AgentCommandScreen(
            "Work Report", full_cmd, prompt_str,
            default_window_name="agent-work-report",
            project_root=Path("."),
            operation="work-report",
            operation_args=op_args,
            default_agent_string=agent_string,
            skill_name="work-report",
        )

        def on_work_report_result(result):
            if result == "run":
                # Column-scoped: no task filename exists, so no refocus.
                self.run_dialog_command(screen.full_command)
            elif isinstance(result, TmuxLaunchConfig):
                _, err = launch_in_tmux(screen.full_command, result)
                if err:
                    self.notify(err, severity="error")
                elif result.new_window:
                    maybe_spawn_minimonitor(result.session, result.window)
            self.refresh_board()
        self.push_screen(screen, on_work_report_result)

    def _trail_task_target(self):
        """`T` policy for the board (t1794, C10): the task id to launch
        /aitask-trail for, or None to launch nothing.

        The focused task — in By-Topic, the focused card's lane root (RFC §9.3
        J2/J3). None under a modal, in the In-Flight and By-Trail views (where
        `check_action` also hides the key), on a ghost card, or with no
        parseable focused task."""
        if self._modal_is_active():
            return None
        if self.base_filter in ("inflight", "bytrail"):
            return None
        focused = self._focused_card()
        if not focused or getattr(focused, "is_ghost", False):
            return None
        task_num, _ = TaskCard._parse_filename(focused.task_data.filename)
        if not task_num:
            return None
        target = task_num.lstrip("t")
        if self.base_filter == "bytopic":
            all_tasks = (list(self.manager.task_datas.values())
                         + list(self.manager.child_task_datas.values()))
            tasks_by_id = {}
            for task in all_tasks:
                own = task_own_id(task)
                if own:
                    tasks_by_id.setdefault(own, task)
            root = topic_key(focused.task_data, tasks_by_id)
            if root:
                target = str(root)
        return target

    # --- TrailHost policy and hooks (t1794_5) ---

    @property
    def tasks_dir(self) -> Path:
        """The task directory the By-Trail mixin resolves project names from.

        Read at call time, so a fixture-loaded board answers its fixture tree."""
        return TASKS_DIR

    def _after_dialog_command(self, refocus_filename: str = "") -> None:
        """`run_dialog_command` suspend-path hook: reload tasks and refresh."""
        self.manager.load_tasks()
        self.refresh_board(refocus_filename=refocus_filename)

    def _launch_brainstorm(self, num: str, filename: str):
        """Launch brainstorm, switching to existing tmux window if found."""
        window_name = f"brainstorm-{num}"
        session = (
            _current_tmux_session()
            or load_tmux_defaults(Path.cwd())["default_session"]
        )
        existing = find_window_by_name(window_name, session)
        if existing:
            sess, idx = existing
            subprocess.Popen(
                ["tmux", "select-window", "-t", tmux_window_target(sess, idx)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            self.notify(f"Switched to existing brainstorm for t{num}")
            self.refresh_board(refocus_filename=filename)
            return
        full_cmd = f"./{BRAINSTORM_TUI_SCRIPT} {num}"
        prompt_str = f"ait brainstorm {num}"
        screen = AgentCommandScreen(
            f"Brainstorm Task t{num}", full_cmd, prompt_str,
            default_window_name=window_name,
        )
        def on_brainstorm_result(brainstorm_result):
            if brainstorm_result == "run":
                # Not a code agent: a non-zero exit is an ordinary TUI quit,
                # so no failure notice.
                self.run_dialog_command(
                    screen.full_command, refocus_filename=filename,
                    error_notice=None)
            elif isinstance(brainstorm_result, TmuxLaunchConfig):
                _, err = launch_in_tmux(screen.full_command, brainstorm_result)
                if err:
                    self.notify(err, severity="error")
            self.refresh_board(refocus_filename=filename)
        self.push_screen(screen, on_brainstorm_result)

    def action_brainstorm_task(self):
        """Open brainstorm command dialog for the focused task."""
        if self._modal_is_active():
            return
        focused = self._focused_card()
        if not focused:
            return
        task_num, _ = TaskCard._parse_filename(focused.task_data.filename)
        if not task_num:
            return
        num = task_num.lstrip("t")
        if num in self.manager.lock_map:
            self.notify("Task is locked — brainstorm disabled", severity="warning")
            return
        self._launch_brainstorm(num, focused.task_data.filename)

    @work(exclusive=True)
    async def run_editor(self, filepath):
        """Suspend app and run system editor."""
        editor = os.environ.get("EDITOR", "nano")
        if sys.platform == "win32":
            editor = os.environ.get("EDITOR", "notepad")

        filename = Path(filepath).name
        with self.suspend():
            subprocess.call([editor, str(filepath)])

        self.manager.load_tasks()
        self.refresh_board(refocus_filename=filename)

    def action_sync_remote(self):
        """Manually trigger a sync with remote."""
        if self._modal_is_active():
            return
        if self.base_filter == "inflight" and isinstance(self._focused_card(), InFlightTaskCard):
            self._record_focused_human_gate("pass")
            return
        # By-Trail has its own `s` (action_trail_select) and `S`
        # (action_trail_sync); this action is hidden there by check_action.
        self.push_screen(LoadingOverlay("Syncing with remote..."))
        self._run_sync(show_notification=True, show_overlay=True)

    @work(exclusive=True, thread=True)
    def _run_sync(self, show_notification: bool = True, show_overlay: bool = False):
        """Run ait sync --batch in background and handle the result."""
        result = run_sync_batch()

        if show_overlay:
            self.app.call_from_thread(self.pop_screen)

        status = result.status

        if status == STATUS_CONFLICT:
            self.app.call_from_thread(self._show_conflict_dialog, result.conflicted_files)
            return
        if status == STATUS_TIMEOUT:
            if show_notification:
                self.app.call_from_thread(self.notify, "Sync timed out", severity="warning")
            return
        if status == STATUS_NOT_FOUND:
            self.app.call_from_thread(self.notify, "Sync script not found", severity="error")
            return

        if status == STATUS_NO_NETWORK:
            if show_notification:
                self.app.call_from_thread(self.notify, "Sync: No network", severity="warning")
        elif status == STATUS_NO_REMOTE:
            if show_notification:
                self.app.call_from_thread(self.notify, "Sync: No remote configured", severity="warning")
        elif status == STATUS_NOTHING:
            if show_notification:
                self.app.call_from_thread(self.notify, "Already up to date", severity="information")
        elif status == STATUS_AUTOMERGED:
            if show_notification:
                self.app.call_from_thread(self.notify, "Sync: Auto-merged conflicts", severity="information")
        elif status == STATUS_MERGED:
            # A diverged branch converged by guarded merge (t1731): the files
            # another live session holds were left dirty and uncommitted.
            if show_notification:
                self.app.call_from_thread(
                    self.notify, "Sync: Merged — protected files left uncommitted",
                    severity="information",
                )
        elif status in (STATUS_PUSHED, STATUS_PULLED, STATUS_SYNCED):
            if show_notification:
                self.app.call_from_thread(self.notify, f"Sync: {status.capitalize()}", severity="information")
        elif status == STATUS_DEFERRED:
            # A deferral is deliberate, not a failure: sync did less than a full
            # cycle to avoid committing or publishing another session's
            # in-flight work. "warning" (visible but benign) rather than
            # "error", which would also arm the syncer's failure capture.
            # Always notified, even when show_notification is False: the user
            # needs to know a sync did not fully happen.
            _msg = result.deferred_reason or "deferred"
            if result.deferred_detail:
                _msg = f"{_msg} ({result.deferred_detail})"
            self.app.call_from_thread(self.notify, f"Sync deferred: {_msg}", severity="warning")
        elif status == STATUS_ERROR:
            self.app.call_from_thread(self.notify, f"Sync error: {result.error_message}", severity="error")

        self.app.call_from_thread(self.manager.load_tasks)
        self.app.call_from_thread(self.refresh_board, refresh_locks=True)
        # A sync that pulled new task data can change the drift verdict, so
        # re-check freshness for the active trail (t1268).
        if self.base_filter == "bytrail" and self.active_trail_handle:
            self.app.call_from_thread(self._start_trail_drift)

    def _show_conflict_dialog(self, files: list[str]):
        """Show the conflict resolution dialog (must be called on main thread)."""
        def on_result(resolve):
            if resolve:
                self._run_interactive_sync_shared()
            else:
                self.manager.load_tasks()
                self.refresh_board()
        self.push_screen(SyncConflictScreen(files), on_result)

    @work(exclusive=True)
    async def _run_interactive_sync_shared(self):
        """Run shared interactive sync helper, then refresh board state."""
        def reload():
            self.manager.load_tasks()
            self.refresh_board(refresh_locks=True)
        run_interactive_sync(self.app, on_done=reload)

    def _resolve_pick_command(self, task_num: str):
        """Resolve the full pick command via --dry-run, return command string or None."""
        num = task_num.lstrip("t")
        return resolve_dry_run_command(Path("."), "pick", num)

    def _resolve_pick_profile(self) -> str:
        """Resolve the active profile name for the pick skill."""
        return resolve_skill_profile("pick")

    def _resolve_resume_command(self, task_num: str):
        """Resolve the full resume command via --dry-run, return command string or None."""
        num = task_num.lstrip("t")
        return resolve_dry_run_command(Path("."), "resume", num)

    def _resolve_resume_profile(self) -> str:
        """Resolve the active profile name for the resume skill."""
        return resolve_skill_profile("resume")

    def _focus_existing_agent_window(self, num: str) -> bool:
        session = (
            _current_tmux_session()
            or load_tmux_defaults(Path.cwd())["default_session"]
        )
        for window_name in (f"agent-pick-{num}", f"agent-resume-{num}"):
            existing = find_window_by_name(window_name, session)
            if existing:
                sess, idx = existing
                subprocess.Popen(
                    ["tmux", "select-window", "-t", tmux_window_target(sess, idx)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                self.notify(f"Switched to existing agent window for t{num}")
                return True
        return False

    def action_gate_resume(self):
        """Open resume command dialog for the focused In-Flight task."""
        if self._modal_is_active():
            return
        focused = self._focused_card()
        if not isinstance(focused, InFlightTaskCard):
            return
        # Visibility, not routing (t1595, aidocs/gates/ledger-driven-reentry.md).
        # An approved-but-unstarted task is `Ready` and carries a ledger, so
        # resuming it would start implementation without the planning
        # checkpoint or its remote drift check. The refusal lives HERE, not
        # only in `_ops_hint`: `g` stays reachable through its binding, a
        # remap, or the command palette. Keyed on `approved_unstarted`, never
        # on the lane — a blocking dependency moves such a task to Blocked.
        if focused.item.approved_unstarted:
            self.notify(
                f"{focused.item.task_id} has an approved plan but has not "
                "started — press p to pick it (resume would bypass the "
                "planning checkpoint).",
                severity="warning")
            return
        task_num, _ = TaskCard._parse_filename(focused.task_data.filename)
        if not task_num:
            return
        num = task_num.lstrip("t")
        if self._focus_existing_agent_window(num):
            self.refresh_board(refocus_filename=focused.task_data.filename)
            return
        full_cmd = self._resolve_resume_command(task_num)
        if full_cmd:
            prompt_str = f"/aitask-resume {num}"
            agent_string = resolve_agent_string(Path("."), "resume")
            screen = AgentCommandScreen(
                f"Resume Task t{num}", full_cmd, prompt_str,
                default_window_name=f"agent-resume-{num}",
                project_root=Path("."),
                operation="resume",
                operation_args=[num],
                default_agent_string=agent_string,
                skill_name="resume",
                default_profile=self._resolve_resume_profile(),
            )
            def on_resume_result(resume_result):
                if resume_result == "run":
                    self.run_dialog_command(
                        screen.full_command,
                        refocus_filename=focused.task_data.filename)
                elif isinstance(resume_result, TmuxLaunchConfig):
                    _, err = launch_in_tmux(screen.full_command, resume_result)
                    if err:
                        self.notify(err, severity="error")
                    elif resume_result.new_window:
                        maybe_spawn_minimonitor(resume_result.session, resume_result.window)
                self.refresh_board(refocus_filename=focused.task_data.filename)
            self.push_screen(screen, on_resume_result)
        else:
            self.run_codeagent_operation("resume", focused.task_data.filename)

    def _record_focused_human_gate(self, status: str):
        focused = self._focused_card()
        if not isinstance(focused, InFlightTaskCard):
            return
        # Same refusal as `action_gate_resume`, and for a sharper reason: an
        # approved-but-unstarted task's ledger has `review_approved` PENDING,
        # so without this `s` would record a review sign-off on code that was
        # never written (t1603_3). Before the `human_gates` read, so the
        # message names the real reason rather than "no pending human gate".
        if focused.item.approved_unstarted:
            self.notify(
                f"{focused.item.task_id} has not started — no gate can be "
                "signed on an approved-but-unimplemented task.",
                severity="warning")
            return
        gates = focused.item.human_gates
        if not gates:
            self.notify("No pending human gate for this task.", severity="warning")
            return
        if len(gates) == 1:
            self._append_human_gate(focused, gates[0], status)
            return

        action_label = "sign off" if status == "pass" else "fail"
        def on_gate(gate):
            if gate:
                self._append_human_gate(focused, gate, status)
        self.push_screen(GateChoiceScreen(focused.item.task_id, gates, action_label), on_gate)

    def _append_human_gate(self, focused: InFlightTaskCard, gate: str, status: str):
        task_id = focused.item.task_id.lstrip("t")
        try:
            result = subprocess.run(
                [
                    "./.aitask-scripts/aitask_gate.sh",
                    "append",
                    task_id,
                    gate,
                    status,
                    "type=human",
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            self.notify(f"Gate update failed: {exc}", severity="error")
            return
        if result.returncode != 0:
            msg = result.stderr.strip() or result.stdout.strip() or "unknown error"
            self.notify(f"Gate update failed: {msg}", severity="error")
            return
        self.notify(f"Recorded {status} for {gate} on {focused.item.task_id}")
        self.manager.reload_task(focused.task_data.filename)
        self.refresh_board(refocus_filename=focused.task_data.filename)

    @work(exclusive=True)
    async def run_aitask_pick(self, filename):
        """Launch code agent with /aitask-pick for the task."""
        task_num, _ = TaskCard._parse_filename(filename)
        if not task_num:
            return
        num = task_num.lstrip("t")
        wrapper = str(CODEAGENT_SCRIPT)
        terminal = find_terminal()
        if terminal:
            spawn_in_terminal(terminal, [wrapper, "invoke", "pick", num])
        else:
            with self.suspend():
                ret = subprocess.call([wrapper, "invoke", "pick", num])
            if ret != 0:
                self.notify(CODEAGENT_FAILURE_NOTICE, severity="error")
            self.manager.load_tasks()
            self.refresh_board(refocus_filename=filename)

    @work(exclusive=True)
    async def run_codeagent_operation(self, operation: str, filename: str):
        """Launch code agent operation for a task in a terminal or suspended app."""
        task_num, _ = TaskCard._parse_filename(filename)
        if not task_num:
            return
        num = task_num.lstrip("t")
        wrapper = str(CODEAGENT_SCRIPT)
        terminal = find_terminal()
        if terminal:
            spawn_in_terminal(terminal, [wrapper, "invoke", operation, num])
        else:
            with self.suspend():
                ret = subprocess.call([wrapper, "invoke", operation, num])
            if ret != 0:
                self.notify(CODEAGENT_FAILURE_NOTICE, severity="error")
            self.manager.load_tasks()
            self.refresh_board(refocus_filename=filename)

    def action_create_task(self):
        """Open create task dialog with terminal/tmux options."""
        if self._modal_is_active():
            return
        full_cmd = f"./{CREATE_SCRIPT}"
        prompt_str = "ait create"
        screen = AgentCommandScreen(
            "Create Task", full_cmd, prompt_str,
            default_window_name="create-task",
        )
        def on_create_result(create_result):
            if create_result == "run":
                # Not a code agent: a non-zero exit is an ordinary cancel of
                # `ait create`, so no failure notice.
                self.run_dialog_command(
                    screen.full_command, error_notice=None)
            elif isinstance(create_result, TmuxLaunchConfig):
                _, err = launch_in_tmux(screen.full_command, create_result)
                if err:
                    self.notify(err, severity="error")
                elif create_result.new_window:
                    maybe_spawn_minimonitor(create_result.session, create_result.window)
                else:
                    win_name = _lookup_window_name(create_result.session, create_result.window)
                    if win_name:
                        maybe_spawn_minimonitor(
                            create_result.session, win_name,
                            window_index=create_result.window,
                        )
            self.manager.load_tasks()
            self.refresh_board()
        self.push_screen(screen, on_create_result)

    # --- Expand/Collapse Children ---

    def _toggle_expand(self):
        """Toggle showing child tasks under the focused parent task."""
        focused = self._focused_card()
        if not focused:
            return
        if focused.is_child:
            # Child card: find parent and toggle parent's expansion
            parent_num = self.manager.get_parent_num_for_child(focused.task_data)
            parent_task = self.manager.find_task_by_id(parent_num)
            if not parent_task:
                return
            fn = parent_task.filename
        else:
            # Parent card: toggle own expansion
            task_num, _ = TaskCard._parse_filename(focused.task_data.filename)
            children = self.manager.get_child_tasks_for_parent(task_num)
            if not children:
                return
            fn = focused.task_data.filename
        if fn in self.expanded_tasks:
            self.expanded_tasks.discard(fn)
        else:
            self.expanded_tasks.add(fn)
        col_id = focused.column_id
        self.refresh_column(col_id, refocus_filename=fn, refocus_col_id=col_id)

    def action_toggle_children(self):
        # Every dispatch surface routes through here — the footer/keyboard
        # binding (which Textual already gates) and TaskCard's double-click.
        # Re-assert the gate so no caller can bypass the derived-view exclusion
        # (In-Flight / By-Topic / By-Trail render children directly, so there is
        # nothing to expand there). `is not True` matches Textual's binding
        # dispatch: None means "shown but disabled", i.e. not runnable.
        if self.check_action("toggle_children", None) is not True:
            return
        self._toggle_expand()

    def _refocus_group_header(self, col_id: str, slug: str) -> None:
        """Focus the `(col_id, slug)` header if it is mounted and visible.

        Deferred through `call_after_refresh` by every caller: a recompose
        replaces the header WIDGET, so the instance that was focused before is
        gone and focus must be re-resolved by identity, never by reference.
        """
        header = next((h for h in self.query(GroupHeader)
                       if h.column_id == col_id and h.slug == slug), None)
        if header is not None and header.styles.display != "none":
            header.focus()

    def action_toggle_group(self):
        """`x` on a `GroupHeader`: collapse / expand the group (t1243_9).

        The GroupHeader half of the `x` duplicate-key pair. Re-asserts its own
        gate for the same reason `action_toggle_children` does — the command
        palette calls `action_*` directly and never consults `check_action`.
        """
        if self.check_action("toggle_group", None) is not True:
            return
        header = self._focused_unit()
        if not isinstance(header, GroupHeader):
            # Re-resolve, do not trust the gate. A binding gate is not an action
            # guard: `action_*` is reachable directly (command palette, tests),
            # and a `TaskCard` reaching the `header.column_id` below would raise
            # AttributeError straight into Textual's message pump.
            return
        # The model owns the key and the persistence (t1243_10). It mutates the
        # very set this app aliases, so the recompose below still sees the flip
        # with no propagation step.
        try:
            self.manager.toggle_group_collapsed(header.column_id, header.slug)
        except MetadataWriteError as exc:
            # NARROW: only a user-layer write failure. The in-memory toggle has
            # already happened and the recompose below honours it — refusing a
            # view keystroke because a gitignored file is unwritable would be
            # worse than not persisting it. But it must not be silent, or the
            # collapse would simply be gone at next launch with no explanation.
            self.notify(f"Collapse state not saved: {exc}", severity="warning")
        # Recompose: members and their `.child-wrapper` rows mount/unmount
        # together, which only `compose` can express. The column widget holds the
        # app's `collapsed_groups` BY REFERENCE, so it reads the mutation above
        # with no propagation step.
        col_id, slug = header.column_id, header.slug
        self.refresh_column(col_id, refocus_col_id=col_id)
        # Land focus back on the header — never leave it on an unmounted member.
        # Queued after the recompose for the same reason `_refocus_card` is.
        self.call_after_refresh(self._refocus_group_header, col_id, slug)

    # --- Task Movement ---

    async def _dispatch_group_move(self, axis: str, direction: int) -> bool:
        """Route a movement key to the group block move; True when handled.

        Dispatch lives in the six ACTIONS rather than inside the three
        `_move_task_*` helpers (t1243_9). Two reasons, both structural:

        * the helpers stay pure task-movers — with a header focused
          `_focused_card()` is already `None`, so each early-returns harmlessly
          and needs no group branch at all; and
        * `_move_task_vertical` stays SYNCHRONOUS. `test_board_movement`'s probe
          reads `iscoroutinefunction` off each helper to decide where to stamp
          `sync_end`, and the recorded vertical baseline (t1243_1) depends on
          that shape.
        """
        unit = self._focused_unit()
        if not isinstance(unit, GroupHeader):
            return False
        await self._move_focused_group(unit, axis, direction)
        return True

    async def _move_focused_group(self, header, axis: str, direction: int):
        """Move a whole group as a block.

        t1243_9 owns the DISPATCH and the focus contract; the model write and the
        DOM placement are t1243_11's (`Block moves`: N writes, relative order
        preserved, the neighbouring unit never touched). `_apply_group_move` is
        that seam.
        """
        members = group_members(
            self.manager.get_column_tasks(header.column_id), header.slug)
        if not members:
            return
        moved_to = await self._apply_group_move(header, members, axis, direction)
        if moved_to is None:
            return
        # Focus lands on the header in the DESTINATION column. Deferred because
        # the move recomposes, replacing the header widget.
        self.call_after_refresh(self._refocus_group_header, moved_to, header.slug)

    async def _apply_group_move(self, header, members, axis: str, direction: int):
        """Commit a group block move; return the destination `col_id`, or None.

        SEAM — t1243_11 implements the model write and the DOM placement, and
        returns the destination column so the caller can refocus the header
        there. Until then the move is REPORTED rather than silently dropped, so
        `shift`/`ctrl` + arrow on a header is never a dead key.

        **A lateral move must also carry the group's collapse key** (t1243_10):
        after the member writes land, and in the same synchronous block, call

            self.manager.remap_collapsed_groups(
                lambda c, s: (dest_col, s) if (c, s) == (src_col, header.slug)
                else (c, s))

        The member writes must come first — a reload between them and the remap
        would see the new key with no members and prune it. Coalescing onto a
        same-slug group already in the destination needs no extra code: the
        remap is a set union (see `board_groups.remap_group_keys`).
        """
        self.notify(
            f"Moving the group '{group_display_title(header.slug)}' as a block "
            f"is not implemented yet (t1243_11).", severity="information")
        return None

    async def action_move_task_right(self):
        if await self._dispatch_group_move("lateral", 1): return
        await self._move_task_lateral(1)

    async def action_move_task_left(self):
        if await self._dispatch_group_move("lateral", -1): return
        await self._move_task_lateral(-1)

    async def _move_task_lateral(self, direction):
        focused = self._focused_card()
        if not focused: return
        if focused.is_child: return

        filename = focused.task_data.filename
        current_col_id = focused.task_data.board_col
        # Build list of active columns including 'unordered'
        cols = ["unordered"] if self.manager.get_column_tasks("unordered") else []
        cols.extend(self.manager.column_order)

        if current_col_id not in cols: return

        idx = cols.index(current_col_id)
        # Skip over collapsed columns
        new_idx = idx + direction
        while 0 <= new_idx < len(cols):
            if not self.manager.is_column_collapsed(cols[new_idx]):
                break
            new_idx += direction
        else:
            return

        if 0 <= new_idx < len(cols):
            new_col = cols[new_idx]
            task = focused.task_data
            # One write, in the destination only. The source column still needs
            # a repaint below, but no longer a rewrite (t1243_3). The dirty marker
            # comes from the write itself (`_mark_written`) rather than from a
            # `git status` subprocess per keypress (t1243_4).
            self.manager.move_task_to_column(filename, new_col)

            def _full_refresh():
                self.refresh_columns({current_col_id, new_col},
                                     refocus_filename=filename,
                                     refocus_col_id=new_col)

            # `unordered` appears and disappears with its tasks, and only
            # `refresh_columns` can express "the column is gone" (it escalates
            # to a full `refresh_board`). A transplant cannot, so decline the
            # fast path rather than desynchronise the board. Rare by
            # construction: `unordered` exists only while some task has no
            # `boardcol`.
            if "unordered" in (current_col_id, new_col):
                _full_refresh()
                return

            src_col = dst_col = None
            for col in self.query(KanbanColumn):
                if col.col_id == current_col_id:
                    src_col = col
                if col.col_id == new_col:
                    dst_col = col
            if src_col is None or dst_col is None:
                _full_refresh()
                return

            # A grouped move joins `unordered` on the recompose path (t1243_9):
            # a transplant cannot express "this card belongs inside that group's
            # block", and only a recompose re-derives the column's unit order.
            # Checked HERE, after the widgets are resolved, so the test costs a
            # scan of two already-held children lists rather than a model lookup.
            if self._move_needs_recompose(task, src_col, dst_col):
                _full_refresh()
                return

            # Append: `move_task_to_column` places past the destination maximum,
            # so the task sorts last there.
            if await self._transplant_block(task, src_col, dst_col,
                                            refocus_col_id=new_col):
                self._sync_header_count(src_col)
                self._sync_header_count(dst_col)
                # Synchronous: the awaits above settled the DOM, so the deferral
                # `refresh_columns` needs (to avoid racing compose) does not
                # apply. Same shape `_swap_adjacent_cards` already uses.
                self.apply_filter({current_col_id, new_col})
                self.call_after_refresh(self._refocus_card, filename, new_col)

    async def action_move_task_up(self):
        if await self._dispatch_group_move("vertical", -1): return
        self._move_task_vertical(-1)

    async def action_move_task_down(self):
        if await self._dispatch_group_move("vertical", 1): return
        self._move_task_vertical(1)

    @staticmethod
    def _column_widget_has_group(col_widget) -> bool:
        """True when this column WIDGET currently renders a `GroupHeader`.

        Reads the DOM the move is about to mutate — no model lookup, no
        derivation, no sort. Deliberately not `build_column_units(get_column_tasks(...))`:
        that filters every task on the board and then sorts TWICE (once in
        `get_column_tasks`, once inside the derivation), which would put real
        work on the card-only movement hot path this fallback exists to leave
        alone. And deliberately not `query(GroupHeader)`: Textual 8.2.7 walks the
        whole tree wherever a query is rooted (see `_filter_units`), while a
        movement path already holds the column widget — the same reasoning
        `_find_parent_card` documents.

        Headers are DIRECT children of `KanbanColumn` (flat siblings of the
        cards), so scanning `children` is exact, not an approximation.
        """
        return any(isinstance(w, GroupHeader) for w in col_widget.children)

    def _move_needs_recompose(self, task, *col_widgets) -> bool:
        """True when a single-task move touches grouping (t1243_9).

        The in-place DOM paths (`_swap_adjacent_cards`, `_transplant_block`)
        assume a card-only column: they swap or append CARD blocks, while a
        grouped column's DOM has to follow INV-R's unit order — and a member
        moved laterally CARRIES its `boardgroup`, so it must land inside a
        same-slug group in the destination rather than at the end. Recomposing
        re-derives the column from `build_column_units`, which is correct by
        construction.

        Both tests are cheap by construction: `task_group_slug` is one dict get,
        and the column check is one pass over a column's direct children. No
        board renders a group until some task carries `boardgroup`, so on an
        ungrouped board this is a slug miss plus a short isinstance scan — the
        movement path already iterates the same list in `_find_parent_card` — and
        t1243_5's measured lateral win is untouched.

        Takes column WIDGETS, not ids: every caller already holds them, and
        taking ids would force a lookup this must not pay for.

        t1243_11 removes the fallback by generalising `_card_block` to group
        blocks; it must keep BOTH directions of this predicate tested.
        """
        if task_group_slug(task):
            return True
        return any(self._column_widget_has_group(w) for w in col_widgets)

    def _card_block(self, col_widget, card) -> list:
        """A parent card plus the `.child-wrapper` rows that belong to it.

        An expanded parent's child rows are SIBLINGS that follow its card, so
        every DOM operation on a card has to carry them along. `ColumnHeader`
        and `EmptyColumnPlaceholder` only ever precede the first card, so
        "stop at the first non-wrapper" is a complete rule.

        Shared by the vertical swap below and the lateral / to-edge transplant.
        """
        children = list(col_widget.children)
        idx = children.index(card)
        block = [card]
        for widget in children[idx + 1:]:
            if isinstance(widget, Horizontal) and widget.has_class("child-wrapper"):
                block.append(widget)
            else:
                break
        return block

    def _find_parent_card(self, col_widget, filename: str):
        """The non-child `TaskCard` for `filename` among a column's DIRECT children.

        Deliberately not `query()`: Textual 8.2.7 walks the whole tree wherever
        a query is rooted (see `_filter_units`), and a movement path already
        holds the column widget.
        """
        for widget in col_widget.children:
            if (isinstance(widget, TaskCard) and not widget.is_child
                    and widget.task_data.filename == filename):
                return widget
        return None

    def _swap_adjacent_cards(self, col_widget, card_above, card_below):
        """Swap two adjacent TaskCard blocks in the DOM without rebuilding."""
        below_block = self._card_block(col_widget, card_below)
        anchor = card_above
        for widget in below_block:
            col_widget.move_child(widget, before=anchor)

        # Scoped: a DOM reorder inside one column cannot change what any other
        # column displays.
        self.apply_filter({col_widget.col_id})

    def _sync_header_count(self, col_widget) -> None:
        """Repaint a column header's task count after an in-place DOM change.

        `ColumnHeader` bakes `task_count` in at construction, so a transplant
        that skips the recompose would leave both headers stale — the recompose
        used to refresh them for free. Reads the manager (unfiltered), matching
        what `KanbanColumn.compose` puts there.
        """
        header = next((w for w in col_widget.children
                       if isinstance(w, ColumnHeader)), None)
        if header is None:
            return
        count = len(self.manager.get_column_tasks(col_widget.col_id))
        if header.task_count != count:
            header.task_count = count
            header.refresh(recompose=True)

    async def _transplant_block(self, task, src_col, dst_col, *, before=None,
                                refocus_col_id: str = "") -> bool:
        """Move one task's DOM block between (or within) columns, no recompose.

        Textual 8.2.7 offers no cross-parent widget move: `move_child` refuses a
        foreign child, and `mount()` on a live widget is a SILENT no-op because
        `App._register` short-circuits on the app registry. So the old widgets
        are pruned and the block is rebuilt from `KanbanColumn.task_block`.
        Rebuilding is not a workaround — it is what keeps `column_id` (read at
        17 sites) and the dirty `*` marker correct by construction.

        **The caller has ALREADY committed the model write.** So this helper owns
        its recovery: on any failure it recomposes the affected columns from the
        committed model and returns False, rather than leaving a task the model
        says exists and the board renders nowhere. It never propagates either —
        an exception escaping an async action reaches Textual's message pump and
        takes the app down.

        Returns True only on a clean transplant. False means "already recovered
        by recompose": the caller must NOT then run the scoped follow-ups,
        because `refresh_columns` has done the filter pass and the refocus.
        """
        affected = {src_col.col_id, dst_col.col_id}

        def _recover():
            self.refresh_columns(affected, refocus_filename=task.filename,
                                 refocus_col_id=refocus_col_id or dst_col.col_id)

        card = self._find_parent_card(src_col, task.filename)
        if card is None:
            _recover()
            return False
        try:
            block = self._card_block(src_col, card)
            await src_col.remove_children(block)
            await dst_col.mount_compose(dst_col.task_block(task), before=before)
        except Exception as exc:
            # Everything past the write is inside this guard because the write
            # is already on disk: `_card_block` raises on a card that is not a
            # direct child, and the mount raises MountError / DuplicateIds, or
            # anything `task_block` raises. Past `remove_children` the old
            # widgets are gone, so without this the board renders the task
            # NOWHERE. Broad by intent: rebuilding from the committed model is
            # the correct remedy for every failure, and enumerating the raisable
            # types would only let an unforeseen one through. `BaseException`
            # (notably `CancelledError`) still propagates — that is app
            # teardown, where a repaint is meaningless.
            self.log.error("board: block transplant failed; recomposing", exc)
            self.notify(f"Board repaint failed ({type(exc).__name__}: {exc}) — "
                        "affected columns were rebuilt.", severity="error")
            _recover()
            return False
        return True

    def _move_task_vertical(self, direction):
        focused = self._focused_card()
        if focused and focused.is_child: return
        if not focused: return

        filename = focused.task_data.filename
        col_id = focused.task_data.board_col
        tasks = self.manager.get_column_tasks(col_id)

        try:
            current_idx = next(i for i, t in enumerate(tasks) if t.filename == filename)
        except StopIteration:
            return

        swap_idx = current_idx + direction
        if 0 <= swap_idx < len(tasks):
            target_task = tasks[swap_idx]
            # Insert between the neighbours of the destination slot — one write
            # instead of a swap plus a column renumber (t1243_3). Bounds are
            # explicit: `tasks[current_idx - 2]` at index 1 would silently yield
            # the LAST card rather than "no neighbour".
            if direction == 1:
                before = target_task
                after = (tasks[current_idx + 2]
                         if current_idx + 2 < len(tasks) else None)
            else:
                before = tasks[current_idx - 2] if current_idx >= 2 else None
                after = target_task
            self.manager.reposition_task(filename, before, after)

            # DOM swap: reorder widgets in-place instead of rebuilding column
            col_widget = None
            for col in self.query(KanbanColumn):
                if col.col_id == col_id:
                    col_widget = col
                    break

            target_card = None
            if col_widget is not None:
                for card in col_widget.query(TaskCard):
                    if not card.is_child and card.task_data.filename == target_task.filename:
                        target_card = card
                        break

            # A grouped column takes the recompose path (t1243_9): the in-place
            # swap reorders CARD blocks, but the DOM has to follow INV-R's unit
            # order, which only a recompose re-derives.
            if (col_widget is not None and target_card is not None
                    and not self._move_needs_recompose(focused.task_data, col_widget)):
                if direction == -1:  # moving up: focused was below, target above
                    self._swap_adjacent_cards(col_widget, target_card, focused)
                else:  # moving down: focused was above, target below
                    self._swap_adjacent_cards(col_widget, focused, target_card)
                self.call_after_refresh(self._refocus_card, filename, col_id)
            else:
                self.refresh_column(col_id, refocus_filename=filename,
                                    refocus_col_id=col_id)

    async def action_move_task_top(self):
        if await self._dispatch_group_move("extreme", -1): return
        await self._move_task_to_extreme(-1)

    async def action_move_task_bottom(self):
        if await self._dispatch_group_move("extreme", 1): return
        await self._move_task_to_extreme(1)

    async def _move_task_to_extreme(self, direction):
        """Move focused task to top (direction=-1) or bottom (direction=1) of its column."""
        focused = self._focused_card()
        if not focused or focused.is_child:
            return
        filename = focused.task_data.filename
        col_id = focused.task_data.board_col
        tasks = self.manager.get_column_tasks(col_id)
        if len(tasks) <= 1:
            return
        try:
            current_idx = next(i for i, t in enumerate(tasks) if t.filename == filename)
        except StopIteration:
            return
        if direction == -1 and current_idx == 0:
            return
        if direction == 1 and current_idx == len(tasks) - 1:
            return
        task = focused.task_data
        # One write past the column extremum — the old raw `±10` arithmetic
        # bypassed normalize_board_idx and raised TypeError on a quoted
        # boardidx sitting next to ints (t1243_3).
        self.manager.move_task_to_edge(filename, col_id, to_top=(direction == -1))

        col_widget = next((c for c in self.query(KanbanColumn)
                           if c.col_id == col_id), None)
        # A grouped column takes the recompose path (t1243_9) — see
        # `_move_needs_recompose`.
        if col_widget is None or self._move_needs_recompose(task, col_widget):
            self.refresh_column(col_id, refocus_filename=filename,
                                refocus_col_id=col_id)
            return

        # Resolve the anchor BEFORE the removal. Moving to the top mounts before
        # the column's first FOCUS UNIT — a different widget, guaranteed by the
        # `current_idx == 0` early return above, and one that sits after the
        # header and the placeholder. Moving to the bottom appends.
        #
        # `GroupHeader` is in the isinstance tuple as defence in depth: a grouped
        # column already recomposed above, but anchoring on the first *card*
        # would otherwise mount the moved task BETWEEN a header and its members,
        # splitting the block, if that guard were ever narrowed.
        before = None
        if direction == -1:
            before = next((w for w in col_widget.children
                           if isinstance(w, (GroupHeader, TaskCard))
                           and not getattr(w, "is_child", False)), None)

        # A same-column move: `move_child` would be cheaper, but it preserves
        # the widget and so would leave the dirty `*` that this write just
        # turned on unpainted — a regression against the recompose it replaces.
        # Rebuilding one block gets the marker right by construction.
        if await self._transplant_block(task, col_widget, col_widget,
                                        before=before, refocus_col_id=col_id):
            # No header sync: a same-column move does not change the count.
            self.apply_filter({col_id})
            self.call_after_refresh(self._refocus_card, filename, col_id)

    # --- Column Reordering ---

    def action_move_col_right(self):
        self._shift_column(1)
        
    def action_move_col_left(self):
        self._shift_column(-1)

    def _shift_column(self, direction):
        # Resolve by column identity, not by focused card: an empty,
        # filter-emptied, or collapsed column has no card to resolve through.
        col_id = self._get_focused_col_id()
        if not col_id or col_id == "unordered": return

        order = self.manager.column_order
        if col_id not in order: return

        idx = order.index(col_id)
        new_idx = idx + direction
        if not (0 <= new_idx < len(order)): return

        focused = self._focused_card()
        filename = focused.task_data.filename if focused else ""

        order[idx], order[new_idx] = order[new_idx], order[idx]
        self.manager.save_metadata()
        self.refresh_board(refocus_filename=filename,
                           refocus_col_id="" if filename else col_id)

    # --- Column Customization ---

    def _apply_column_edit(self, result) -> bool:
        """Apply a ColumnEditScreen result. Returns True if anything changed.

        Split out of `_handle_column_edit_result` (t1377_5) so `ColumnManageScreen`
        can reuse the mutation without triggering `refresh_board()` per edit — a
        recompose under a live modal, once per operation, when one refresh on
        close is enough. The pencil-button and palette paths keep the wrapper
        below, so all three entry points still run identical mutation code.

        `update_column` is called with the id TWICE: column ids are auto-slugged,
        so re-slugging on a title edit would rewrite every member task's
        `boardcol` as a side effect of a cosmetic change. That keeps the rename
        branch (and its collapsed-state migration, t1377_4 §4) dormant by
        decision, not by oversight.
        """
        if not result:
            return False
        action = result[0]
        if action == "add":
            _, col_id, title, color = result
            self.manager.add_column(col_id, title, color)
            self.notify(f"Added column: {title}", severity="information")
        elif action == "edit":
            _, col_id, title, color = result
            self.manager.update_column(col_id, col_id, title, color)
            self.notify(f"Updated column: {title}", severity="information")
        else:
            return False
        return True

    def _handle_column_edit_result(self, result):
        """Callback for ColumnEditScreen dismiss."""
        if self._apply_column_edit(result):
            self.refresh_board()

    def action_add_column(self):
        """Open the Add Column dialog."""
        self.push_screen(
            ColumnEditScreen(self.manager, mode="add"),
            self._handle_column_edit_result,
        )

    def action_edit_column(self):
        """Open column picker, then edit dialog."""
        def on_col_selected(col_id):
            if col_id:
                self.push_screen(
                    ColumnEditScreen(self.manager, col_id=col_id, mode="edit"),
                    self._handle_column_edit_result,
                )
        self.push_screen(ColumnSelectScreen(self.manager, "Edit"), on_col_selected)

    def action_delete_column(self):
        """Open column picker, then confirm deletion."""
        def on_col_selected(col_id):
            if not col_id:
                return
            col_conf = self.manager.get_column_conf(col_id)
            task_count = len(self.manager.get_column_tasks(col_id))
            def on_confirmed(confirmed):
                if confirmed:
                    self.manager.delete_column(col_id)
                    self.notify(f"Deleted column: {col_conf['title']}", severity="information")
                    self.refresh_board()
            self.push_screen(
                DeleteColumnConfirmScreen(col_conf, task_count),
                on_confirmed,
            )
        self.push_screen(ColumnSelectScreen(self.manager, "Delete"), on_col_selected)

    def open_column_edit(self, col_id: str):
        """Open the edit dialog for a specific column (called from header click)."""
        self.push_screen(
            ColumnEditScreen(self.manager, col_id=col_id, mode="edit"),
            self._handle_column_edit_result,
        )

    # --- Column management dialog (t1377_5) ---

    def _merge_source_columns(self) -> list:
        """Ordered `(col_id, title)` options for the merge-source picker.

        Reuses `_work_report_columns`, which already prepends the synthetic
        Unsorted lane **only when it holds tasks** — exactly the rule merge needs
        (an empty inbox is not a meaningful merge source) — and already drops a
        stale `column_order` entry that has no `columns` definition.
        """
        return self._work_report_columns()

    def _report_merge(self, result, dest_title: str, attempted: int) -> None:
        """Turn a `MergeResult` into one honest toast.

        Branching on `complete` alone is not enough: `refused` means NOTHING was
        written (input validation), while `failed` means partial progress — and
        two of the reserved sentinels change what the *retry* is. Reporting all
        three the same way is the specific failure this method exists to prevent.
        """
        if result.refused:
            reasons = ", ".join(f"{cid or '(none)'}: {why}"
                                for cid, why in result.refused)
            self.notify(f"Merge refused — nothing changed ({reasons})",
                        severity="error")
            return
        landed = len(result.merged)
        if result.complete:
            self.notify(f"Merged {landed} task{'' if landed == 1 else 's'} "
                        f"into {dest_title}", severity="information")
            return
        keys = dict(result.failed)
        if MERGE_METADATA_LOCAL_KEY in keys:
            # The merge LANDED and the sources are durably gone; only the
            # user-local collapsed-state prune is pending. Re-running the merge
            # would refuse with unknown_column, so never suggest it here.
            msg = (f"Merged {landed} into {dest_title}; columns removed, but "
                   "collapsed state was not saved — it self-heals on next launch.")
        elif MERGE_METADATA_KEY in keys:
            msg = (f"Merged {landed} task{'' if landed == 1 else 's'} into "
                   f"{dest_title}, but the column list was not saved — "
                   "re-run the merge to finish.")
        elif MERGE_UNVERIFIABLE_KEY in keys:
            msg = (f"Merged {landed} into {dest_title}; source columns kept "
                   f"because {keys[MERGE_UNVERIFIABLE_KEY]} — fix those "
                   "file(s) and re-run the merge to finish.")
        else:
            msg = (f"Merged {landed} of {attempted} into {dest_title} — "
                   f"{len(result.failed)} failed, re-run to finish.")
        self.notify(msg, severity="warning")

    def _open_column_manage(self, start_in_merge: bool = False):
        if self._modal_is_active():
            return
        # Re-check the view gate INSIDE the action, not only in check_action:
        # the command palette resolves `action_*` by name and never consults it,
        # so `check_action` hiding `e` in the derived views would otherwise leave
        # Ctrl+P as an unguarded back door into the persistent-column editor.
        # Same rule as `action_move_to_column` (t1243_7) — but this one explains
        # itself rather than returning silently, because the palette entry is a
        # thing the user deliberately clicked, and a no-op reads as a bug.
        if self.base_filter in ("inflight", "bytopic", "bytrail"):
            self.notify(
                "Column management is unavailable in In-Flight / By-Topic / "
                "By-Trail — those views render derived lanes, not columns.",
                severity="warning")
            return

        def on_closed(changed):
            if changed:
                self.refresh_board()

        self.push_screen(
            ColumnManageScreen(self.manager, start_in_merge=start_in_merge),
            on_closed,
        )

    def action_column_manage(self):
        """`e` / palette: open the column-management dialog."""
        self._open_column_manage()

    def action_merge_columns(self):
        """Palette shortcut: open the dialog straight into the merge sub-flow."""
        self._open_column_manage(start_in_merge=True)

    # --- Column Collapse/Expand ---

    def toggle_column_collapse(self, col_id: str):
        """Toggle collapse/expand state for a column."""
        focused = self._focused_card()
        focused_col = self._get_focused_col_id()
        self.manager.toggle_column_collapsed(col_id)
        refocus, refocus_col = "", ""
        if focused and focused.column_id != col_id:
            refocus = focused.task_data.filename
        elif focused_col == col_id:
            # Focus was inside the toggled column, whose cards vanish (collapse)
            # or appear (expand) — re-anchor by column identity.
            refocus_col = col_id
        self.refresh_board(refocus_filename=refocus, refocus_col_id=refocus_col)

    def action_toggle_column_collapsed(self):
        """Toggle collapse for the currently focused column (Shift+X)."""
        if self._modal_is_active():
            return
        col_id = self._get_focused_col_id()
        if col_id:
            self.toggle_column_collapse(col_id)
            return
        self.notify("No column selected", severity="warning")

    def action_collapse_column(self):
        """Open column picker to collapse a column (command palette)."""
        if self._modal_is_active():
            return
        expanded_cols = [c for c in self.manager.columns
                         if not self.manager.is_column_collapsed(c["id"])]
        # Include unordered if it has tasks and is not collapsed
        unordered_tasks = self.manager.get_column_tasks("unordered")
        if unordered_tasks and not self.manager.is_column_collapsed("unordered"):
            expanded_cols.insert(0, {"id": "unordered", "title": "Unsorted / Inbox", "color": "gray"})
        if not expanded_cols:
            self.notify("No columns to collapse", severity="warning")
            return

        def on_col_selected(col_id):
            if col_id:
                self.toggle_column_collapse(col_id)
                conf = self.manager.get_column_conf(col_id)
                title = conf["title"] if conf else col_id
                self.notify(f"Collapsed: {title}", severity="information")

        self.push_screen(
            ColumnSelectScreen(self.manager, "Collapse", columns=expanded_cols),
            on_col_selected,
        )

    def action_expand_column(self):
        """Open column picker to expand a collapsed column (command palette)."""
        if self._modal_is_active():
            return
        collapsed_cols = [c for c in self.manager.columns
                          if self.manager.is_column_collapsed(c["id"])]
        # Include unordered if collapsed
        if self.manager.is_column_collapsed("unordered"):
            collapsed_cols.insert(0, {"id": "unordered", "title": "Unsorted / Inbox", "color": "gray"})
        if not collapsed_cols:
            self.notify("No columns to expand", severity="warning")
            return

        def on_col_selected(col_id):
            if col_id:
                self.toggle_column_collapse(col_id)
                conf = self.manager.get_column_conf(col_id)
                title = conf["title"] if conf else col_id
                self.notify(f"Expanded: {title}", severity="information")

        self.push_screen(
            ColumnSelectScreen(self.manager, "Expand", columns=collapsed_cols),
            on_col_selected,
        )

    # --- Settings ---

    def action_open_settings(self):
        """Open the settings dialog."""
        if self._modal_is_active():
            return
        self.push_screen(
            SettingsScreen(self.manager),
            self._handle_settings_result,
        )

    def _handle_settings_result(self, result):
        """Callback for SettingsScreen dismiss."""
        if result is None:
            return
        self.manager.settings.update(result)
        # `SettingsScreen` returns only settings keys (auto_refresh_minutes,
        # sync_on_refresh), so the USER layer is the complete write (t1243_10).
        self.manager.save_settings()
        self._start_auto_refresh_timer()
        self._update_subtitle()
        minutes = result["auto_refresh_minutes"]
        if minutes > 0:
            self.notify(f"Auto-refresh: {minutes}min", severity="information")
        else:
            self.notify("Auto-refresh: disabled", severity="information")

    # --- Git Commit ---

    def action_commit_selected(self):
        """Commit the currently selected task if it has git modifications."""
        if self._modal_is_active():
            return
        focused = self._focused_card()
        if not focused:
            self.notify("No task selected", severity="warning")
            return
        if not self.manager.is_modified(focused.task_data):
            self.notify("Selected task has no modifications", severity="warning")
            return

        def handle_commit_result(result):
            if result and result[0] == "commit":
                self._git_commit_tasks([focused.task_data], result[1])

        self.push_screen(
            CommitMessageScreen([focused.task_data], self.manager),
            handle_commit_result
        )

    def action_commit_all(self):
        """Commit all tasks with git modifications."""
        if self._modal_is_active():
            return
        modified_tasks = self.manager.get_modified_tasks()
        if not modified_tasks:
            self.notify("No modified tasks to commit", severity="warning")
            return

        def handle_commit_result(result):
            if result and result[0] == "commit":
                self._git_commit_tasks(modified_tasks, result[1])

        self.push_screen(
            CommitMessageScreen(modified_tasks, self.manager),
            handle_commit_result
        )

    def _resolve_plan_path_for(self, task: Task):
        """Resolve the plan file path for a given task."""
        return _resolve_plan_path_for_task(task, self.manager)

    def _categorize_pending_children(self, parent_num: str) -> dict:
        """Bucket a parent's pending children by status.

        Returns a dict with keys:
          - "disposable":      Ready / Postponed / Editing (safe to cascade-delete)
          - "blocking":        Implementing (cascade refused)
          - "unarchived_done": Done but not yet archived (cascade refused)
        """
        buckets = {"disposable": [], "blocking": [], "unarchived_done": []}
        for child in self.manager.get_child_tasks_for_parent(parent_num):
            status = child.metadata.get("status", "Ready")
            if status in ("Ready", "Postponed", "Editing"):
                buckets["disposable"].append(child)
            elif status == "Implementing":
                buckets["blocking"].append(child)
            elif status == "Done":
                buckets["unarchived_done"].append(child)
            else:
                buckets["blocking"].append(child)
        return buckets

    def _build_fate_buckets(self, task: Task):
        """Build (delete_files, archive_kept, archive_deleted, blocking_files) for
        a task as labelled (path, annotation) tuples. Used by DeleteArchiveConfirmScreen
        and by the cascade execution path so they share one source of truth.

        Returns a dict with:
          - delete_files:   files removed when user clicks Delete
          - archive_kept:   files moved to archived/ when user clicks Archive
          - archive_deleted: files removed when user clicks Archive (cascade)
          - blocking_files: blocking children that prevent archive
          - cascade_children: list[Task] of disposable children for the cascade executor
          - blocked_reason: str | None — reason archive is blocked, or None
        """
        task_num, _ = TaskCard._parse_filename(task.filename)
        is_child = task.filepath.parent.name.startswith("t")
        status = task.metadata.get("status", "Ready")

        delete_files = []
        archive_kept = []
        archive_deleted = []
        blocking_files = []
        cascade_children = []
        blocked_reason = None

        if is_child:
            # Self
            self_annot = f"child — {status}"
            delete_files.append((str(task.filepath), self_annot))
            archive_kept.append((str(task.filepath), self_annot))
            plan_path = self._resolve_plan_path_for(task)
            if plan_path:
                delete_files.append((str(plan_path), ""))
                archive_kept.append((str(plan_path), ""))
        else:
            # Parent self
            self_annot = f"parent — {status}"
            delete_files.append((str(task.filepath), self_annot))
            archive_kept.append((str(task.filepath), self_annot))
            parent_plan = self._resolve_plan_path_for(task)
            if parent_plan:
                delete_files.append((str(parent_plan), ""))
                archive_kept.append((str(parent_plan), ""))

            # Pending children
            buckets = self._categorize_pending_children(task_num)
            for child in buckets["disposable"]:
                child_status = child.metadata.get("status", "Ready")
                delete_files.append((str(child.filepath), child_status))
                archive_deleted.append((str(child.filepath), child_status))
                child_plan = self._resolve_plan_path_for(child)
                if child_plan:
                    delete_files.append((str(child_plan), ""))
                    archive_deleted.append((str(child_plan), ""))
                cascade_children.append(child)
            for child in buckets["blocking"]:
                child_status = child.metadata.get("status", "Ready")
                delete_files.append((str(child.filepath), child_status))
                blocking_files.append((str(child.filepath), child_status))
            for child in buckets["unarchived_done"]:
                delete_files.append((str(child.filepath), "Done — archive it first"))
                blocking_files.append((str(child.filepath), "Done — archive it first"))

            n_blocking = len(buckets["blocking"])
            n_done = len(buckets["unarchived_done"])
            if n_blocking or n_done:
                parts = []
                if n_blocking:
                    parts.append(f"{n_blocking} child(ren) Implementing")
                if n_done:
                    parts.append(f"{n_done} child(ren) Done but unarchived (archive them first)")
                blocked_reason = "Cannot archive parent: " + "; ".join(parts) + "."

        return {
            "delete_files": delete_files,
            "archive_kept": archive_kept,
            "archive_deleted": archive_deleted,
            "blocking_files": blocking_files,
            "cascade_children": cascade_children,
            "blocked_reason": blocked_reason,
        }

    def _collect_delete_files(self, task: Task):
        """Collect files to delete for a task (including children and plans).
        Returns (display_names, paths_to_delete)."""
        display_names = []
        paths = []
        task_num, _ = TaskCard._parse_filename(task.filename)

        # Task file itself
        display_names.append(task.filename)
        paths.append(task.filepath)

        is_child = task.filepath.parent.name.startswith("t")

        if is_child:
            # Child task: plan is in aiplans/p<parent>/p<parent>_<child>_<name>.md
            parent_num = self.manager.get_parent_num_for_child(task)
            plan_name = "p" + task.filename[1:]
            plan_path = Path("aiplans") / parent_num.replace("t", "p", 1) / plan_name
            if plan_path.exists():
                display_names.append(str(plan_path))
                paths.append(plan_path)
        else:
            # Parent task: plan is in aiplans/p<N>_<name>.md
            plan_name = "p" + task.filename[1:]
            plan_path = Path("aiplans") / plan_name
            if plan_path.exists():
                display_names.append(str(plan_path))
                paths.append(plan_path)

            # Child tasks and their plans
            children = self.manager.get_child_tasks_for_parent(task_num)
            for child in children:
                display_names.append(child.filename)
                paths.append(child.filepath)
                child_plan_name = "p" + child.filename[1:]
                child_plan_path = Path("aiplans") / task_num.replace("t", "p", 1) / child_plan_name
                if child_plan_path.exists():
                    display_names.append(str(child_plan_path))
                    paths.append(child_plan_path)

        return display_names, paths

    def _check_task_dependencies(self, task: Task, is_child: bool):
        """Check if other tasks depend on this task.
        Returns (dep_warnings: list[str], related_summaries: list[str])."""
        task_num_str, _ = TaskCard._parse_filename(task.filename)
        dep_warnings = []
        related_summaries = []

        if is_child:
            # Check sibling dependencies
            # Depends may use bare number (1), full ID (t398_1), or number-only ID (398_1)
            parent_num = self.manager.get_parent_num_for_child(task)
            siblings = self.manager.get_child_tasks_for_parent(parent_num)
            child_local = task_num_str.split("_")[-1]
            match_variants = {child_local, task_num_str, task_num_str.lstrip("t")}

            for sib in siblings:
                if sib.filepath == task.filepath:
                    continue
                sib_status = sib.metadata.get("status", "Ready")
                sib_depends = {str(d) for d in sib.metadata.get("depends", [])}
                if match_variants & sib_depends:
                    dep_warnings.append(
                        f"{sib.filename} ({sib_status}) explicitly depends on this task"
                    )
                else:
                    related_summaries.append(f"{sib.filename} [{sib_status}]")
        else:
            # Check all parent tasks for dependencies on this task number
            # Depends may use bare number (42) or with prefix (t42)
            task_local = task_num_str.lstrip("t")
            match_variants = {task_local, task_num_str}
            for fname, other in self.manager.task_datas.items():
                if other.filepath == task.filepath:
                    continue
                other_status = other.metadata.get("status", "Ready")
                other_depends = {str(d) for d in other.metadata.get("depends", [])}
                if match_variants & other_depends:
                    dep_warnings.append(
                        f"{other.filename} ({other_status}) explicitly depends on this task"
                    )

        return dep_warnings, related_summaries

    def _execute_archive(self, task_num: str, task: Task,
                         cascade_children: list = None):
        """Archive a task as superseded (shows loading overlay).

        If cascade_children is non-empty, those disposable children are
        removed from the parent's children_to_implement and their files
        deleted before the archive script runs (so the archived parent has
        a clean children_to_implement and the deletions land in the same
        archive commit).
        """
        cascade_paths = []
        cascade_ids = []
        for child in cascade_children or []:
            child_id, _ = TaskCard._parse_filename(child.filename)
            cascade_ids.append(child_id)
            cascade_paths.append(str(child.filepath))
            child_plan = self._resolve_plan_path_for(child)
            if child_plan:
                cascade_paths.append(str(child_plan))
        self.push_screen(LoadingOverlay("Archiving task..."))
        self._do_archive(task_num, cascade_ids, cascade_paths)

    @work(thread=True)
    def _do_archive(self, task_num: str,
                    cascade_ids: list[str], cascade_paths: list[str]):
        """Run archive subprocess in a thread worker.

        cascade_ids:   child task IDs (with 't' prefix, e.g. 't475_3') to remove
                       from the parent's children_to_implement before archiving.
        cascade_paths: child task/plan file paths to git-rm before archiving.
        """
        try:
            parent_num_bare = task_num.lstrip("t")

            # Remove disposable children from parent's children_to_implement
            # (does not commit — runs without --commit; the archive script's
            #  commit will pick up the staged changes).
            for child_id in cascade_ids:
                subprocess.run(
                    ["./.aitask-scripts/aitask_update.sh", "--batch", parent_num_bare,
                     "--remove-child", child_id, "--silent"],
                    capture_output=True, text=True, timeout=10
                )

            # git rm the disposable child files (task + plan)
            for path in cascade_paths:
                rm_result = subprocess.run(
                    [*_task_git_cmd(), "rm", "-f", path],
                    capture_output=True, text=True, timeout=10
                )
                if rm_result.returncode != 0:
                    try:
                        os.remove(path)
                    except OSError:
                        pass

            # Best-effort cleanup of empty child directories
            if cascade_paths:
                child_task_dir = TASKS_DIR / task_num
                if child_task_dir.is_dir():
                    try:
                        os.rmdir(child_task_dir)
                    except OSError:
                        pass
                child_plan_dir = Path("aiplans") / task_num.replace("t", "p", 1)
                if child_plan_dir.is_dir():
                    try:
                        os.rmdir(child_plan_dir)
                    except OSError:
                        pass

            result = subprocess.run(
                ["./.aitask-scripts/aitask_archive.sh", "--superseded", task_num],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                msg = f"Archived {task_num} as superseded"
                if cascade_ids:
                    msg += f" (cascade-deleted {len(cascade_ids)} child(ren))"
                self.app.call_from_thread(self.notify, msg, severity="information")
            else:
                error = result.stderr.strip() or result.stdout.strip()
                self.app.call_from_thread(self.notify, f"Archive failed: {error}", severity="error")
        except subprocess.TimeoutExpired:
            self.app.call_from_thread(self.notify, "Archive operation timed out", severity="error")
        except FileNotFoundError:
            self.app.call_from_thread(self.notify, "Archive script not found", severity="error")
        finally:
            self.app.call_from_thread(self.pop_screen)

        self.app.call_from_thread(self.manager.load_tasks)
        self.app.call_from_thread(self.refresh_board)

    @staticmethod
    def _doomed_attachment_ids(paths) -> list[str]:
        """Bare task ids (parent + cascade children) whose attachments must be
        decref'd when their files are hard-deleted. Plan files and non-task
        paths are excluded by ROOT (not a substring check), and the canonical
        TaskCard._parse_filename derives the id so parent-vs-child is never
        mis-read. t1093"""
        ids = []
        for p in paths:
            parts = Path(p).parts
            name = Path(p).name
            if TASKS_DIR.name not in parts:        # plan files live under aiplans/
                continue
            if not (name.startswith("t") and name.endswith(".md")):
                continue
            tid, _ = TaskCard._parse_filename(name)
            ids.append(tid.lstrip("t"))
        return ids

    def _decref_doomed_attachments(self, paths, folded_ids):
        """Decref the attachments of every doomed task via the bash helper, so a
        hard-deleted task's id leaves each blob's refs set (else the blob never
        reaches zero-refcount and `ait attach gc` can never reclaim it). t1093

        `folded_ids` are tasks the delete REVIVES (unfolds); they are passed as
        --protect-task so the helper REBINDS each blob a revived task still lists
        from the deleted primary to that revived task (incref survivor + decref
        primary), instead of orphaning the ref onto the deleted primary. t1096

        Returns (ok: bool, msg: str). On a non-zero helper exit the caller MUST
        fail closed (abort the delete) — the leak is recreated otherwise."""
        ids = self._doomed_attachment_ids(paths)
        if not ids:
            return True, ""
        cmd = ["./.aitask-scripts/aitask_attach.sh", "decref-deleted"]
        for fid in folded_ids or []:
            cmd += ["--protect-task", str(fid)]
        cmd += ids
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        except subprocess.TimeoutExpired:
            return False, "attachment decref timed out"
        if r.returncode != 0:
            return False, (r.stderr.strip() or r.stdout.strip() or "unknown error")
        return True, ""

    def _unfold_deleted_primary_children(self, folded_ids):
        """Revive folded tasks before deleting their primary.

        A failed unfold must abort the hard-delete; otherwise a folded task can
        remain pointed at a primary that is about to be removed. t1102
        """
        for fid_str in folded_ids or []:
            try:
                result = subprocess.run(
                    ["./.aitask-scripts/aitask_update.sh", "--batch", fid_str,
                     "--status", "Ready", "--folded-into", ""],
                    capture_output=True, text=True, timeout=10
                )
            except subprocess.TimeoutExpired:
                return False, f"unfold t{fid_str} timed out"
            if result.returncode != 0:
                err = result.stderr.strip() or result.stdout.strip() or "unknown error"
                return False, f"unfold t{fid_str} failed: {err}"
        return True, ""

    def _execute_delete(self, task_num: str, paths: list, task: Task = None):
        """Delete task files (shows loading overlay)."""
        paths_str = [str(p) for p in paths]
        folded_ids = []
        parent_num = None
        if task:
            folded_ids = [str(fid).lstrip("t") for fid in task.metadata.get("folded_tasks", [])]
            if task.filepath.parent.name.startswith("t"):
                parent_num = task.filepath.parent.name
        # Files this delete WRITES rather than removes: the parent's
        # children_to_implement edit and each revived folded task. They must be in
        # the commit's pathspec or the writes are left ownerless — measured: today
        # they are left dirty-and-unstaged, because the index-wide commit only
        # ever carried what `git rm` had staged (t1702).
        extra_paths = _task_file_paths_for_ids(
            ([parent_num] if parent_num else []) + list(folded_ids))
        self.push_screen(LoadingOverlay("Deleting task..."))
        self._do_delete(task_num, paths_str, folded_ids, parent_num, extra_paths)

    @work(thread=True)
    def _do_delete(self, task_num: str, paths: list[str], folded_ids: list[str],
                   parent_num: str | None, extra_paths: list[str] | None = None):
        """Run delete subprocess in a thread worker.

        If parent_num is set, this is a child-task delete: the child is
        first removed from the parent's children_to_implement (so the
        parent's metadata stays consistent), and after the commit lands
        the parent is checked for orphan status to prompt archival.

        `extra_paths` are files this delete WROTE (the parent, revived folded
        tasks); they join the doomed paths in the scoped commit's pathspec.
        """
        try:
            # Decref the doomed tasks' attachments BEFORE any mutation, so a
            # helper error aborts the delete cleanly (fail-closed) rather than
            # leaving an orphaned-blob leak. Files must still exist to read their
            # frontmatter. folded_ids are revived by the unfold below; they are
            # passed as --protect-task so the helper REBINDS each blob they still
            # list from the primary to them (t1096), not merely skips decref. t1093
            ok, err = self._decref_doomed_attachments(paths, folded_ids)
            if not ok:
                self.app.call_from_thread(
                    self.notify,
                    f"Attachment decref failed — task NOT deleted (retry): {err}",
                    severity="error",
                )
                return  # the `finally` pops the LoadingOverlay; nothing deleted

            # Unfold folded tasks before deleting
            ok, err = self._unfold_deleted_primary_children(folded_ids)
            if not ok:
                self.app.call_from_thread(
                    self.notify,
                    f"Folded-task unfold failed - task NOT deleted (retry): {err}",
                    severity="error",
                )
                return  # the `finally` pops the LoadingOverlay; nothing deleted

            # If deleting a child task, remove its reference from the parent's
            # children_to_implement list before the file disappears.
            if parent_num:
                parent_bare = parent_num.lstrip("t")
                subprocess.run(
                    ["./.aitask-scripts/aitask_update.sh", "--batch", parent_bare,
                     "--remove-child", task_num, "--silent"],
                    capture_output=True, text=True, timeout=10
                )

            # Unlink, deliberately NOT `git rm`. `git rm` removes from the working
            # tree AND FROM THE INDEX, parking staged deletions in the shared
            # .aitask-data index for the whole window before this operation's own
            # commit — where any concurrent index-wide commit publishes them under
            # a foreign message. Scoping our commit closes the swallow in one
            # direction; dropping the staging closes it in the other. The scoped
            # `commit -o` records a tracked path's deletion straight from worktree
            # state (verified), and an untracked one has nothing to commit and is
            # dropped by the helper's classification. t1702
            for path in paths:
                try:
                    os.remove(path)
                except OSError:
                    pass

            # Remove empty child directories
            child_task_dir = TASKS_DIR / task_num
            if child_task_dir.is_dir():
                try:
                    os.rmdir(child_task_dir)
                except OSError:
                    pass
            child_plan_dir = Path("aiplans") / task_num.replace("t", "p", 1)
            if child_plan_dir.is_dir():
                try:
                    os.rmdir(child_plan_dir)
                except OSError:
                    pass

            message = f"ait: Delete task {task_num} and associated files"
            commit_paths = _dedup_paths(paths, extra_paths)
            result = commit_task_paths(message, commit_paths)
            text, severity = _task_commit_notice(
                result, message, commit_paths,
                success_text=f"Deleted task {task_num}",
                failure_lead=f"Task {task_num} deleted but NOT committed",
            )
            self.app.call_from_thread(self.notify, text, severity=severity)
        except subprocess.TimeoutExpired:
            self.app.call_from_thread(self.notify, "Git operation timed out", severity="error")
        except FileNotFoundError:
            self.app.call_from_thread(self.notify, "git not found", severity="error")
        finally:
            self.app.call_from_thread(self.pop_screen)

        self.app.call_from_thread(self.manager.load_tasks)
        self.app.call_from_thread(self.refresh_board)

        # After the parent has been reloaded, check for orphan-archive prompt.
        if parent_num:
            self.app.call_from_thread(self._maybe_prompt_orphan_parent_archive, parent_num)

    def _maybe_prompt_orphan_parent_archive(self, parent_num: str):
        """If the parent has no more pending children and is not Done,
        offer to archive it as completed."""
        parent_task = self.manager.find_task_by_id(parent_num)
        if parent_task is None:
            return
        children_to_implement = parent_task.metadata.get("children_to_implement") or []
        if children_to_implement:
            return
        if parent_task.metadata.get("status") == "Done":
            return
        # Also skip if there are still discoverable child files on disk
        # (defensive — children_to_implement may be stale)
        if self.manager.get_child_tasks_for_parent(parent_num):
            return

        parent_status = parent_task.metadata.get("status", "Ready")
        archive_kept = [(str(parent_task.filepath), f"parent — {parent_status}")]
        parent_plan = self._resolve_plan_path_for(parent_task)
        if parent_plan:
            archive_kept.append((str(parent_plan), ""))

        def on_orphan_decision(confirmed):
            if confirmed:
                self._execute_archive(parent_num, parent_task, cascade_children=None)

        self.push_screen(
            OrphanParentArchiveScreen(parent_task.filename, parent_status, archive_kept),
            on_orphan_decision,
        )

    def _rename_task(self, task: Task, new_name: str):
        """Rename a task (and its plan file if present), commit, and sync."""
        sanitized = _sanitize_name(new_name)
        if not sanitized:
            self.notify("Invalid name after sanitization", severity="error")
            return

        task_num, _ = TaskCard._parse_filename(task.filename)
        new_task_filename = f"{task_num}_{sanitized}.md"

        if new_task_filename == task.filename:
            self.notify("Name unchanged", severity="warning")
            return

        # Compute new task path (preserving parent directory for child tasks)
        new_task_path = task.filepath.parent / new_task_filename

        # Compute plan paths
        old_plan_path = self._resolve_plan_path_for(task)
        new_plan_path = None
        if old_plan_path and old_plan_path.exists():
            new_plan_filename = "p" + new_task_filename[1:]
            new_plan_path = old_plan_path.parent / new_plan_filename

        self.push_screen(LoadingOverlay("Renaming..."))
        self._do_rename_task(
            task.filepath, new_task_path,
            old_plan_path, new_plan_path,
            task_num, sanitized.replace("_", " "),
            new_task_filename,
        )

    @work(thread=True)
    def _do_rename_task(self, old_task: Path, new_task: Path,
                        old_plan: Path | None, new_plan: Path | None,
                        task_num: str, humanized_name: str,
                        new_filename: str):
        """Rename task/plan files, commit, and sync in a background thread."""
        try:
            # Rename task file (and the plan file if present). No `git add` here:
            # the scoped commit stages the untracked NEW paths itself, and the
            # tracked-and-now-missing OLD paths need no index entry — `commit -o`
            # records their deletion from worktree state. Staging a tracked path
            # would replace whatever a concurrent session had staged for it in the
            # shared .aitask-data index. t1702
            old_task.rename(new_task)
            commit_paths = [str(old_task), str(new_task)]

            if old_plan and new_plan:
                old_plan.rename(new_plan)
                commit_paths += [str(old_plan), str(new_plan)]

            # Commit
            commit_msg = f"ait: Rename {task_num}: {humanized_name}"
            result = commit_task_paths(commit_msg, commit_paths)
            text, severity = _task_commit_notice(
                result, commit_msg, commit_paths,
                success_text=f"Renamed to {new_filename}",
                failure_lead=f"Renamed to {new_filename} but NOT committed",
            )
            self.app.call_from_thread(self.notify, text, severity=severity)
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            self.app.call_from_thread(
                self.notify, f"Rename failed: {e}", severity="error")
        finally:
            self.app.call_from_thread(self.pop_screen)  # dismiss LoadingOverlay

        # Sync
        self._run_sync(show_notification=True)

        # Reload and refresh board
        self.app.call_from_thread(self.manager.load_tasks)
        self.app.call_from_thread(self.refresh_board, refocus_filename=new_filename)

    def _git_commit_tasks(self, tasks: list[Task], message: str):
        """Stage and commit specific task files (shows loading overlay)."""
        focused = self._focused_card()
        refocus = focused.task_data.filename if focused else ""
        filepaths = [str(t.filepath) for t in tasks]
        count = len(tasks)
        self.push_screen(LoadingOverlay("Committing..."))
        self._do_git_commit_tasks(filepaths, count, message, refocus)

    @work(thread=True)
    def _do_git_commit_tasks(self, filepaths: list[str], count: int, message: str, refocus: str):
        """Run the scoped task-file commit in a thread worker.

        Scoped to the task files the dialog listed, so a dirty PLAN file no
        longer rides along — that is the intended bystander exclusion, and the
        message names tasks. No `git add` loop: the seam stages an untracked new
        task file and leaves tracked ones alone. t1702
        """
        try:
            result = commit_task_paths(message, filepaths)
            text, severity = _task_commit_notice(
                result, message, filepaths,
                success_text=f"Committed {count} file(s)",
                failure_lead="Changes NOT committed",
            )
            self.app.call_from_thread(self.notify, text, severity=severity)
        except subprocess.TimeoutExpired:
            self.app.call_from_thread(self.notify, "Git commit timed out", severity="error")
        except FileNotFoundError:
            self.app.call_from_thread(self.notify, "git not found", severity="error")
        finally:
            self.app.call_from_thread(self.pop_screen)

        self.app.call_from_thread(self.manager.refresh_git_status)
        self.app.call_from_thread(self.refresh_board, refocus_filename=refocus)

if __name__ == "__main__":
    app = KanbanApp()
    app.run()
