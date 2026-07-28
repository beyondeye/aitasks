"""ait syncer — TUI for tracking remote desync state.

Polls `lib/desync_state.snapshot()` for the tracked `main` and `aitask-data`
refs and displays ahead/behind counts plus per-row detail (commit subjects and
changed paths). With two or more discovered aitasks repos (live tmux sessions
plus the per-user registry, via `discover_aitasks_sessions`), the table grows
a Project column with one row per repo×ref and actions (sync/pull/push) target
the highlighted row's repo. Automatic refresh fetches ONE repo per tick — the
least-recently-fetched — while every repo gets a local-only snapshot; the
Fetched column shows each repo's age since its last successful fetch.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from desync_state import physical_main_branch, snapshot  # noqa: E402
from tui_switcher import TuiSwitcherMixin  # noqa: E402
from shortcuts_mixin import ShortcutsMixin  # noqa: E402
from agent_launch_utils import (  # noqa: E402
    AitasksSession,
    TmuxLaunchConfig,
    compact_root,
    disambiguate_labels,
    discover_aitasks_sessions,
    get_tmux_sessions,
    get_tmux_windows_result,
    is_tmux_available,
    launch_in_tmux,
    maybe_spawn_minimonitor,
    resolve_agent_string,
    resolve_dry_run_command,
    resolve_pane_id_by_pid,
    unique_window_name,
)
# Imported by name (not via the module) so tests can patch these seams on
# `syncer_app` itself — every one of them is impure (network, tmux, spawn).
from framework_version import (  # noqa: E402
    build_handoff_request,
    build_upgrade_command,
    detect_target_activity,
    is_self_target,
    read_installed_version,
    resolve_latest_version,
    version_status,
    write_handoff_request,
)
# Cross-repo settings seam (t1223_4). Imported by name for the same reason as
# framework_version above: every one of these shells a subprocess or writes a
# file, so tests patch them on `syncer_app` itself.
from cross_repo_settings import (  # noqa: E402
    PROVENANCE_BUILTIN,
    PROVENANCE_CONFLICT,
    PROVENANCE_LOCAL,
    DestConfigUnreadable,
    OperationValue,
    PushPartialError,
    apply_push,
    diff_across_repos,
    plan_push,
    read_operation_defaults,
)
from agent_command_screen import AgentCommandScreen  # noqa: E402
from sync_action_runner import (  # noqa: E402
    STATUS_AUTOMERGED,
    STATUS_CONFLICT,
    STATUS_ERROR,
    STATUS_NO_NETWORK,
    STATUS_NO_REMOTE,
    STATUS_NOT_FOUND,
    STATUS_NOTHING,
    STATUS_PULLED,
    STATUS_PUSHED,
    STATUS_SYNCED,
    STATUS_TIMEOUT,
    SyncConflictScreen,
    SyncResult,
    run_interactive_sync,
    run_sync_batch,
)
from sync_failure_screen import SyncFailureContext, SyncFailureScreen  # noqa: E402
from upgrade_screens import (  # noqa: E402
    ForceConfirmScreen,
    HandoffConfirmScreen,
    UpgradeConfirmScreen,
    UpgradeRefusalScreen,
    UpgradeTargetScreen,
)
from settings_screens import (  # noqa: E402
    BACK,
    SettingsDestinationsScreen,
    SettingsLayerScreen,
    SettingsMaskedScreen,
    SettingsPushResultScreen,
    SettingsSourceScreen,
)

from textual import work  # noqa: E402
from textual.actions import SkipAction  # noqa: E402
from textual.app import App, ComposeResult, ScreenStackError  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.containers import Vertical, VerticalScroll  # noqa: E402
from textual.css.query import NoMatches, WrongType  # noqa: E402
from textual.widgets import (  # noqa: E402
    DataTable,
    Footer,
    Header,
    Static,
    TabbedContent,
    TabPane,
    Tabs,
)
from textual.worker import get_current_worker  # noqa: E402


REFRESH_TICK_DEFAULT = 60
AGE_TICK_SECONDS = 5
DETAIL_MAX_COMMITS = 20
DETAIL_MAX_PATHS = 50
GIT_TIMEOUT_SECONDS = 30
FAILURE_TAIL_LINES = 30

TRACKED_REFS = ("main", "aitask-data")

# Actions that only make sense on the Branches tab. Gated off every other tab
# by SyncerApp.check_action. `q`, the TUI switcher (`j`) and the shortcuts
# editor (`?`) stay available everywhere.
BRANCH_TAB_ACTIONS = (
    "sync_data",
    "pull",
    "push",
    "refresh",
    "toggle_fetch",
    "agent_resolve",
)

# Actions that only make sense on the Versions tab. A sibling tuple to the one
# above rather than a second bespoke branch in check_action. Note the gate
# fails CLOSED for these: `_active_tab()` degrades to "tab_branches", so a
# pre-mount check makes the framework-rewriting action inert.
VERSION_TAB_ACTIONS = (
    "upgrade",
    "recheck_version",
)

# Actions that only make sense on the Settings tab. Third sibling of the two
# tuples above. `push_setting` carries a SECOND, row-level gate in
# check_action: the tab gate alone would leave it live before the lazy load's
# first apply, on an empty matrix, and on a row where no repo holds a value
# that can be copied — states in which no push target can be built at all.
SETTINGS_TAB_ACTIONS = (
    "push_setting",
    "reload_settings",
)

# Arrow-key navigation actions (t1266). Bound App-level with priority=True so
# they beat the focused DataTable's own cursor bindings; each action re-raises
# SkipAction when it is not the one that should handle the key, so ordinary
# cursor / scroll movement is untouched. Blanket-gated off in check_action while
# any screen is pushed — see the "Priority bindings + App.query_one gotcha"
# section of aidocs/framework/tui_conventions.md.
NAV_ACTIONS = (
    "nav_up",
    "nav_down",
    "prev_tab",
    "next_tab",
)

# Active TabPane -> the id of the list that `down` from the tab bar enters.
# Every tab now maps to a list (t1223_5 replaced the Settings placeholder with
# a real table), which is what keeps the t1266 priority arrows working there —
# see t1267. The "no list for this tab" branches downstream are kept as
# defensive guards for a future non-list pane; no current tab reaches them.
TAB_LIST_IDS = {
    "tab_branches": "branches",
    "tab_versions": "versions",
    "tab_settings": "settings",
}

# upgrade_state values (contract G). There is deliberately no "succeeded"
# state: launch_in_tmux returns as soon as the pane exists, `ait setup` may sit
# at a prompt for minutes, and nothing reports back — so the UI can only ever
# say what it observed.
UPGRADE_IDLE = "idle"
UPGRADE_LAUNCHED = "launched"
UPGRADE_FINISHED = "finished"

# Marks a version cell whose value predates a launched upgrade.
STALE_MARKER = "*"

# Empty pending-refresh slot sentinel (a pending fetch key may legitimately be
# None, so the slot needs a distinct "unset" marker).
PENDING_UNSET = object()


def _format_clock(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S")


# ─── Pure multi-repo model helpers (unit-tested in tests/test_syncer_rows.py) ──


@dataclass(frozen=True)
class RowSpec:
    """One table row = one (repo, ref) pair.

    ``row_key`` is an OPAQUE Textual row id — positional (``r0``, ``r1``, …)
    in multi-repo mode, the literal legacy ref names in single-repo mode. It
    is never parsed; ``(session_key, ref_name)`` are recovered exclusively via
    the app's ``_rows_by_key`` map, so key validity never depends on
    filesystem-path content.
    """

    row_key: str
    session_key: str    # "" in single-repo mode
    ref_name: str       # "main" | "aitask-data"
    project_label: str  # "" in single-repo mode


@dataclass(frozen=True)
class ActionTarget:
    """Resolved target for a sync/pull/push action.

    ``root is None`` means legacy CWD-relative semantics (single-repo mode).
    """

    root: Path | None
    branch: str | None
    label: str


def discover_syncer_sessions() -> list[AitasksSession]:
    """Live + registered aitasks repos, current repo always present and FIRST.

    Mirrors the stats TUI's discovery (``include_registered=True``, STALE
    registry rows dropped). Discovery failures degrade to a cwd-only list so
    the TUI falls back to single-repo mode instead of crashing. The launch
    repo is synthesized if unregistered/non-tmux so actions on it always work.
    """
    try:
        sessions = [
            s
            for s in discover_aitasks_sessions(include_registered=True)
            if not s.is_stale
        ]
    except Exception:
        sessions = []
    cwd = Path.cwd().resolve()
    try:
        cwd_key = os.path.realpath(cwd)
    except OSError:
        cwd_key = str(cwd)
    current = next((s for s in sessions if s.key == cwd_key), None)
    if current is None:
        current = AitasksSession(
            session="", project_root=cwd, project_name=cwd.name
        )
    others = [s for s in sessions if s.key != current.key]
    return [current, *others]


def build_labels(sessions: list[AitasksSession]) -> dict[str, str]:
    """Collision-safe project labels keyed by session key (t1099 pattern)."""
    labels = disambiguate_labels(
        [s.project_name for s in sessions],
        [compact_root(s.project_root) for s in sessions],
        [compact_root(s.project_root) for s in sessions],
    )
    return {s.key: lbl for s, lbl in zip(sessions, labels)}


def build_rows(
    sessions: list[AitasksSession], labels: dict[str, str]
) -> list[RowSpec]:
    """Multi-repo row model: one row per repo×ref, opaque positional keys."""
    rows: list[RowSpec] = []
    idx = 0
    for sess in sessions:
        label = labels.get(sess.key, sess.project_name)
        for ref in TRACKED_REFS:
            rows.append(RowSpec(f"r{idx}", sess.key, ref, label))
            idx += 1
    return rows


def single_repo_rows() -> list[RowSpec]:
    """Legacy single-repo rows (literal ref-name row keys, no project)."""
    return [RowSpec(ref, "", ref, "") for ref in TRACKED_REFS]


CELL_UNAVAILABLE = "unavailable"
CELL_CONFLICT = "conflict"
DIVERGE_MARKER = "≠"


@dataclass(frozen=True)
class SettingsRow:
    """One Settings-tab row = one operation across every repo column.

    ``row_key`` is opaque and positional (``s0``, ``s1``, …), recovered through
    the app's ``_settings_rows_by_key`` map exactly like :class:`RowSpec` and
    :class:`VersionRow`. Unlike those two this row set is REBUILT on every
    refresh, so nothing may hold a row across a modal — see :class:`PushTarget`.

    ``cells`` is display text; ``sources`` is the parallel machine-readable
    answer to "may this repo's value be copied?". They are deliberately
    separate: a cell reading ``conflict`` still has an underlying effective
    value, and rendering is not the place to decide it must not be propagated.
    """

    row_key: str
    operation: str
    cells: tuple[str, ...]
    sources: tuple[str | None, ...]
    divergent: bool

    @property
    def has_source(self) -> bool:
        return any(s is not None for s in self.sources)


def settings_cell(value: OperationValue | None, unreadable: bool) -> str:
    """Render one matrix cell: effective value plus a provenance marker.

    There is no ``seed`` marker — t1223_4 established that the resolver has no
    seed tier, so rendering one would display a value the repo does not use.
    A ``conflict`` renders the literal word and NEVER a value: the layers and
    the resolver disagree, and the contract is to never guess.
    """
    if unreadable or value is None:
        return CELL_UNAVAILABLE
    if value.provenance == PROVENANCE_CONFLICT or value.effective is None:
        return CELL_CONFLICT
    if value.provenance == PROVENANCE_LOCAL:
        return f"{value.effective} (local)"
    if value.provenance == PROVENANCE_BUILTIN:
        return f"{value.effective} (default)"
    return value.effective


def settings_source(value: OperationValue | None, unreadable: bool) -> str | None:
    """The repo's value IF it can truthfully be copied, else None.

    Eligibility is derived here, once, rather than re-decided inside the push
    flow. An unreadable repo has no value at all, and a ``conflict`` repo's
    effective value is not a coherent thing to propagate. Handing either to
    ``plan_push`` would not raise — it matches against ``value or ""`` — it
    would return ``malformed_agent_string`` for every destination, blaming the
    value the user picked instead of reporting that none existed.
    """
    if unreadable or value is None:
        return None
    if value.provenance == PROVENANCE_CONFLICT:
        return None
    return value.effective


def build_settings_matrix(
    diff: dict[str, dict[str, OperationValue]],
    session_keys: list[str],
    unreadable: frozenset[str] = frozenset(),
) -> list[SettingsRow]:
    """Settings row model: one row per operation, one cell per repo column.

    Divergence is computed over the READABLE repos only — an unreadable repo's
    agreement is unknowable, and flagging every row because one repo is broken
    would be noise rather than signal. A ``conflict`` cell always flags its row:
    something in that repo is genuinely wrong.
    """
    rows: list[SettingsRow] = []
    for idx, operation in enumerate(sorted(diff)):
        per_repo = diff[operation]
        cells: list[str] = []
        sources: list[str | None] = []
        effectives: list[str | None] = []
        conflicted = False
        for key in session_keys:
            broken = key in unreadable
            value = per_repo.get(key)
            cells.append(settings_cell(value, broken))
            sources.append(settings_source(value, broken))
            if broken:
                continue
            if value is None or value.provenance == PROVENANCE_CONFLICT:
                conflicted = True
            else:
                effectives.append(value.effective)
        divergent = conflicted or len(set(effectives)) > 1
        rows.append(
            SettingsRow(
                row_key=f"s{idx}",
                operation=operation,
                cells=tuple(cells),
                sources=tuple(sources),
                divergent=divergent,
            )
        )
    return rows


@dataclass(frozen=True)
class PushTarget:
    """Everything the settings push needs, captured once when it starts.

    The same frozen-capture rule as :class:`UpgradeTarget`, and here it is not
    theoretical: the settings row set really is rebuilt on every refresh, so a
    callback that re-read the table could act on a different operation than the
    user chose.

    ``repos`` holds EVERY repo and ``sources`` the parallel eligibility, rather
    than one pre-filtered list, because source and destination are different
    questions. A ``conflict`` repo cannot be a source but is a perfectly good
    destination — arguably the one most worth fixing.
    """

    operation: str
    repos: tuple[tuple[str, str], ...]   # (session_key, label), column order
    sources: tuple[str | None, ...]

    def source_options(self) -> list[tuple[str, str, str]]:
        """(session_key, label, value) for every repo eligible as a source."""
        return [
            (key, label, value)
            for (key, label), value in zip(self.repos, self.sources)
            if value is not None
        ]

    def destinations_excluding(self, source_key: str) -> list[tuple[str, str]]:
        """Every repo except the chosen source — never filtered by eligibility."""
        return [(key, label) for key, label in self.repos if key != source_key]


@dataclass(frozen=True)
class VersionRow:
    """One Versions-tab row = one repo (not one repo×ref).

    ``row_key`` is opaque and positional (``v0``, ``v1``, …), recovered through
    the app's ``_version_rows_by_key`` map exactly like :class:`RowSpec`. Never
    parse a filesystem path out of it.
    """

    row_key: str
    session_key: str
    project_label: str


def build_version_rows(
    sessions: list[AitasksSession], labels: dict[str, str]
) -> list[VersionRow]:
    """Version row model: one row per repo, opaque positional keys."""
    return [
        VersionRow(f"v{idx}", sess.key, labels.get(sess.key, sess.project_name))
        for idx, sess in enumerate(sessions)
    ]


@dataclass(frozen=True)
class UpgradeTarget:
    """Everything the upgrade flow needs, captured once when it starts.

    The flow spans up to four modal screens, each resuming in an async
    ``push_screen`` callback. Between them the user can move the table cursor,
    and a future change could rebuild the row model outright — so re-resolving
    the target in a later callback risks upgrading a *different* repository
    than the one the user chose. Everything downstream reads this frozen record
    instead: the table, ``_version_rows_by_key`` and the originating
    ``AitasksSession`` are all touched exactly once, at capture time.
    """

    session_key: str
    session_name: str   # tmux session; populated even for registry-only repos
    is_live: bool       # False = registry-synthesized; no tmux to interrogate
    root: Path
    label: str
    installed: str | None


@dataclass(frozen=True)
class UpgradeRun:
    """Observed state of one launched upgrade (contract G).

    ``session_name`` is stored rather than looked up again so the liveness
    re-poll never has to reach back for a session object.
    """

    state: str
    session_name: str = ""
    pane_pid: int | None = None
    pane_id: str | None = None
    started_at: float = 0.0

    @property
    def in_flight(self) -> bool:
        return self.state == UPGRADE_LAUNCHED


def upgrade_state_cell(run: UpgradeRun | None) -> str:
    """Render the State column. Never claims an upgrade succeeded."""
    if run is None or run.state == UPGRADE_IDLE:
        return ""
    if run.state == UPGRADE_LAUNCHED:
        return "upgrading…"
    return "re-check needed"


def action_allowed_for_ref(action: str, ref_name: str) -> bool:
    """Per-row action gating: sync targets the data ref, pull/push main."""
    if action == "sync_data":
        return ref_name == "aitask-data"
    if action in ("pull", "push"):
        return ref_name == "main"
    return True


def least_recent_fetch_key(
    sessions: list[AitasksSession], stamps: dict[str, float]
) -> str | None:
    """Pick the session whose stamp is OLDEST (unstamped sessions first).

    Unstamped sessions win in session-list order (so the current repo is
    fetched first on startup); ties break deterministically by list order.
    Returns ``None`` for an empty list. The stamp map is the entire scheduling
    state — a manual/post-action fetch defers that repo simply by updating its
    stamp. The app feeds this the **attempt**-stamp map (every tried fetch,
    success or not), never the success-stamp map — a repo whose fetch keeps
    failing must still advance the rotation, not starve the other repos.
    """
    best_key: str | None = None
    best_ts: float | None = None
    for sess in sessions:
        ts = stamps.get(sess.key)
        if ts is None:
            return sess.key
        if best_ts is None or ts < best_ts:
            best_key, best_ts = sess.key, ts
    return best_key


def format_age(seconds: float | None) -> str:
    """Compact relative age for the Fetched column (— / 32s / 5m / 1h5m)."""
    if seconds is None:
        return "—"
    total = max(0, int(seconds))
    if total < 60:
        return f"{total}s"
    if total < 3600:
        return f"{total // 60}m"
    hours, minutes = total // 3600, (total % 3600) // 60
    return f"{hours}h{minutes}m" if minutes else f"{hours}h"


def should_stamp_fetch(fetched: bool, statuses: list[str]) -> bool:
    """Whether a refresh pass updates a repo's last-fetch stamp.

    Only a pass that actually fetched may stamp (a passive local-only poll
    must never refresh the displayed age — negative-controlled in tests), and
    only when at least one ref actually reached origin (`fetch_error`,
    `no_remote`, and `missing_worktree` refs never talked to the remote).
    """
    if not fetched:
        return False
    return any(
        st not in ("fetch_error", "no_remote", "missing_worktree")
        for st in statuses
    )


def coalesce_request(
    active: bool, pending: object, new_key: str | None, new_explicit: bool
) -> tuple[bool, object]:
    """Refresh-request coalescing decision: ``(start_now, new_pending_slot)``.

    Idle → start a worker now (slot untouched). Active → defer into the single
    pending slot, which holds ``(fetch_key, explicit)``. Replacement policy:
    an **automatic tick never overwrites a pending explicit request** (the
    tick recurs anyway; a manual `r` / post-action target must not be silently
    dropped); an explicit request replaces anything (latest explicit wins);
    automatic replaces automatic. At most one worker runs at a time and at
    most one follow-up is queued — rapid requests cannot accumulate background
    git passes.
    """
    if not active:
        return True, pending
    if pending is not PENDING_UNSET:
        _, pending_explicit = pending  # type: ignore[misc]
        if pending_explicit and not new_explicit:
            return False, pending
    return False, (new_key, new_explicit)


def resolve_action_target(
    row: RowSpec,
    session_by_key: dict[str, AitasksSession],
    snapshots: dict[str, dict[str, Any]],
    need_branch: bool,
) -> ActionTarget | str:
    """Preflight an action against the selected row's repo.

    Returns an :class:`ActionTarget`, or an error string naming the project.
    Runs BEFORE any subprocess is constructed. ``need_branch`` is True for
    pull/push (which also require a status snapshot so the branch is derived
    from the SELECTED repo's snapshot, never another repo's); sync does not
    need a branch.
    """
    if row.session_key == "":
        # Single-repo mode: legacy CWD-relative semantics.
        if not need_branch:
            return ActionTarget(root=None, branch=None, label="")
        snap = snapshots.get("")
        worktree = None
        if snap:
            for ref in snap.get("refs", []):
                if ref.get("name") == "main":
                    worktree = ref.get("worktree")
                    break
        if not worktree:
            return "main worktree not available"
        return ActionTarget(
            root=Path(worktree), branch=physical_main_branch(snap), label=""
        )

    sess = session_by_key.get(row.session_key)
    if sess is None:
        return f"{row.project_label}: project no longer discovered — refresh (r) first"
    if not sess.project_root.is_dir():
        return (
            f"{row.project_label}: project root missing or not a directory "
            f"({sess.project_root})"
        )
    if not need_branch:
        return ActionTarget(root=sess.project_root, branch=None, label=row.project_label)
    snap = snapshots.get(row.session_key)
    if not snap or not snap.get("refs"):
        return f"{row.project_label}: no status snapshot yet — refresh (r) first"
    return ActionTarget(
        root=sess.project_root,
        branch=physical_main_branch(snap),
        label=row.project_label,
    )


class SyncerApp(TuiSwitcherMixin, ShortcutsMixin, App):
    """Textual TUI for the syncer."""

    _shortcuts_scope = "syncer"

    TITLE = "aitasks syncer"

    CSS = """
    Screen {
        layout: vertical;
    }
    TabPane {
        padding: 0 1;
    }
    #branches {
        height: auto;
        max-height: 14;
    }
    #detail_scroll {
        height: 1fr;
        border-top: solid $accent-darken-2;
    }
    #detail {
        padding: 0 1;
    }
    #versions {
        height: auto;
        max-height: 20;
    }
    #settings {
        height: auto;
        max-height: 20;
    }
    """

    BINDINGS = [
        *TuiSwitcherMixin.SWITCHER_BINDINGS,
        *ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS,
        Binding("r", "refresh", "Refresh"),
        Binding("s", "sync_data", "Sync (data)"),
        Binding("u", "pull", "Pull"),
        Binding("p", "push", "Push"),
        Binding("a", "agent_resolve", "Resolve with agent", show=False),
        Binding("f", "toggle_fetch", "Fetch on/off"),
        # Versions tab. Upgrade is uppercase on purpose: it rewrites another
        # repo's framework files, so it should not share the muscle memory of
        # the lowercase Branches keys (`u` is Pull).
        Binding("U", "upgrade", "Upgrade"),
        Binding("c", "recheck_version", "Re-check"),
        # Settings tab. Both keys are deliberately SHARED with a Branches /
        # Versions action: `p` is git-push, `c` is recheck_version, and both are
        # gated off this tab, so the per-tab check leaves exactly one binding
        # per key live. Textual falls through to the next binding for a key
        # whose check_action returns False, and
        # on_tabbed_content_tab_activated calls refresh_bindings() so the footer
        # relabels on the switch. Sharing beats inventing an uppercase variant
        # here: "push" is the right verb on both tabs, and unlike `U`/`u`
        # (Upgrade vs Pull) there is no same-tab collision to disambiguate.
        Binding("p", "push_setting", "Push setting"),
        Binding("c", "reload_settings", "Reload"),
        Binding("q", "quit", "Quit"),
        # Tab bar <-> content navigation (t1266). priority=True is required: a
        # focused DataTable binds all four arrows itself and consumes them at
        # the clamped boundary, so a non-priority binding (or an App-level
        # on_key handler) would never observe them.
        Binding("up", "nav_up", "Row up / leave list", show=False, priority=True),
        Binding(
            "down", "nav_down", "Row down / enter list", show=False, priority=True
        ),
        Binding("left", "prev_tab", "Previous tab", show=False, priority=True),
        Binding("right", "next_tab", "Next tab", show=False, priority=True),
    ]

    def __init__(self, cli_args: argparse.Namespace) -> None:
        super().__init__()
        self.cli_args = cli_args
        self.current_tui_name = "syncer"
        self._interval = max(1, int(getattr(cli_args, "interval", None) or REFRESH_TICK_DEFAULT))
        self._fetch = not getattr(cli_args, "no_fetch", False)
        self.sessions: list[AitasksSession] = discover_syncer_sessions()
        self.multi_repo: bool = len(self.sessions) >= 2
        self._session_by_key: dict[str, AitasksSession] = {
            s.key: s for s in self.sessions
        }
        if self.multi_repo:
            self._rows: list[RowSpec] = build_rows(
                self.sessions, build_labels(self.sessions)
            )
        else:
            self._rows = single_repo_rows()
        self._rows_by_key: dict[str, RowSpec] = {r.row_key: r for r in self._rows}
        # Versions tab: one row per repo, always (there is no single-repo
        # degradation here — a lone repo still has a version).
        self._version_rows: list[VersionRow] = build_version_rows(
            self.sessions, build_labels(self.sessions)
        )
        self._version_rows_by_key: dict[str, VersionRow] = {
            r.row_key: r for r in self._version_rows
        }
        # Settings tab: columns are one per repo (known now); rows are
        # data-derived and therefore rebuilt on every apply.
        self._settings_labels: dict[str, str] = build_labels(self.sessions)
        self._settings_col_keys: list[str] = [
            f"c{idx}" for idx in range(len(self.sessions))
        ]
        self._settings_rows: list[SettingsRow] = []
        self._settings_rows_by_key: dict[str, SettingsRow] = {}
        self._settings_unreadable: dict[str, str] = {}
        self._settings_unattributed: str | None = None
        self._settings_loaded = False
        self._settings_gen = 0
        self._settings_active = False
        self._pending_settings: object = PENDING_UNSET
        self._installed: dict[str, str | None] = {}
        self._latest: str | None = None
        self._latest_error: str | None = None
        self._latest_stale = False
        self._upgrades: dict[str, UpgradeRun] = {}
        # Loaded lazily on first Versions-tab activation: opening the syncer
        # must not cost a GitHub round-trip for a user who never looks at it.
        self._versions_loaded = False
        self._versions_gen = 0
        self._versions_active = False
        self._pending_versions: object = PENDING_UNSET
        # Per-repo state, keyed by session key ("" in single-repo mode).
        self._snapshots: dict[str, dict[str, Any]] = {}
        # Success stamps drive the Fetched age DISPLAY; attempt stamps drive
        # the LRU SCHEDULER. Kept separate so a repo whose fetch keeps failing
        # (no_remote / fetch_error) still advances the rotation instead of
        # being re-picked every tick and starving the other repos.
        self._last_fetch_ts: dict[str, float] = {}
        self._last_fetch_attempt_ts: dict[str, float] = {}
        self._last_refresh_clock: str = ""
        # Refresh request model: at most one worker; single latest-wins
        # pending slot; generation token as the apply-discard backstop.
        self._refresh_gen = 0
        self._refresh_active = False
        self._pending_fetch: object = PENDING_UNSET
        self._last_failure: SyncFailureContext | None = None

    def compose(self) -> ComposeResult:
        # Widget ids (#branches, #detail_scroll, #detail) are unchanged by the
        # tab wrap so every existing query_one() call site keeps resolving.
        # Textual ignores TabbedContent's positional titles when TabPane
        # children are composed, so the TabPane title is the single source of
        # truth (same convention as settings_app).
        yield Header()
        with TabbedContent():
            with TabPane("Branches", id="tab_branches"):
                with Vertical():
                    table = DataTable(
                        id="branches", cursor_type="row", zebra_stripes=True
                    )
                    if self.multi_repo:
                        table.add_column("Project", key="project")
                    table.add_column("Branch", key="branch")
                    table.add_column("Status", key="status")
                    table.add_column("Ahead", key="ahead")
                    table.add_column("Behind", key="behind")
                    if self.multi_repo:
                        table.add_column("Fetched", key="last")
                    else:
                        table.add_column("Last refresh", key="last")
                    yield table
                    with VerticalScroll(id="detail_scroll"):
                        yield Static("Loading…", id="detail")
            with TabPane("Versions", id="tab_versions"):
                versions = DataTable(
                    id="versions", cursor_type="row", zebra_stripes=True
                )
                versions.add_column("Project", key="project")
                versions.add_column("Installed", key="installed")
                versions.add_column("Latest", key="latest")
                versions.add_column("Status", key="vstatus")
                versions.add_column("State", key="state")
                yield versions
            with TabPane("Settings", id="tab_settings"):
                settings = DataTable(
                    id="settings", cursor_type="row", zebra_stripes=True
                )
                # Row cursor, not cell: the t1266 arrows are App-level and
                # priority, so a cell cursor could never be moved horizontally
                # by keyboard anyway. The divergence marker lives in its own
                # narrow column so every cell stays plain, assertable text.
                settings.add_column(DIVERGE_MARKER, key="diverge")
                settings.add_column("Operation", key="operation")
                for idx, sess in enumerate(self.sessions):
                    settings.add_column(
                        self._settings_labels.get(sess.key, sess.project_name),
                        key=self._settings_col_keys[idx],
                    )
                yield settings
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#branches", DataTable)
        for row in self._rows:
            if self.multi_repo:
                table.add_row(
                    row.project_label, row.ref_name, "loading…", "", "", "—",
                    key=row.row_key,
                )
            else:
                table.add_row(row.ref_name, "loading…", "", "", "", key=row.row_key)
        versions = self.query_one("#versions", DataTable)
        for vrow in self._version_rows:
            versions.add_row(
                vrow.project_label, "—", "—", "—", "", key=vrow.row_key
            )
        # Without this the tab bar (ContentTabs) takes boot focus and ↑/↓ no
        # longer moves the branch cursor on open. Tab reaches the detail pane,
        # a second Tab the bar, where ←/→ switch tabs.
        table.focus()
        self.set_interval(self._interval, self._tick_refresh)
        if self.multi_repo:
            self.set_interval(AGE_TICK_SECONDS, self._update_age_cells)
        self.call_later(self._tick_refresh)
        self._update_subtitle()

    def _update_subtitle(self) -> None:
        fetch_state = "on" if self._fetch else "off"
        parts = [f"interval={self._interval}s", f"fetch={fetch_state}"]
        if self.multi_repo:
            parts.insert(0, f"repos={len(self.sessions)}")
        self.sub_title = "  ".join(parts)

    def _active_tab(self) -> str:
        """Id of the active TabPane, degrading to Branches pre-mount.

        ``check_action`` runs before mount (and in unit tests without a running
        app), where the TabbedContent query raises. Falling back to the Branches
        pane keeps those calls from crashing; the fail-open direction is covered
        by the tab-gating tests in ``tests/test_syncer_rows.py``.
        """
        try:
            return self.query_one(TabbedContent).active
        except Exception:
            return "tab_branches"

    # Narrow on purpose: pre-mount, App.query_one resolves self.screen first and
    # raises ScreenStackError (NOT NoMatches); a missing or retyped widget raises
    # NoMatches / WrongType. Anything else is a real bug and must surface —
    # swallowing it would turn every arrow key into a silent no-op.
    _QUERY_MISS = (ScreenStackError, NoMatches, WrongType)

    def _tab_bar(self) -> Tabs | None:
        """The TabbedContent's Tabs bar, or None pre-mount / when not composed."""
        try:
            return self.query_one(TabbedContent).query_one(Tabs)
        except self._QUERY_MISS:
            return None

    def _active_list(self) -> DataTable | None:
        """The active pane's DataTable, or None.

        `None` has two distinct causes and callers must not conflate them: the
        active tab maps to no list at all, or it maps to one that the query
        could not resolve (pre-mount, or the widget is gone — a degraded
        lookup). Callers test membership in ``TAB_LIST_IDS`` for the former
        before consulting this for the latter.

        Since t1223_5 every tab maps to a list, so the first case is currently
        unreachable; the branch is kept for a future non-list pane.
        """
        list_id = TAB_LIST_IDS.get(self._active_tab())
        if list_id is None:
            return None
        try:
            return self.query_one(f"#{list_id}", DataTable)
        except self._QUERY_MISS:
            return None

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        # Arrow nav is main-screen-only. Returning False for a priority binding
        # makes Textual treat it as inactive, so the key falls through to the
        # focused modal widget (the upgrade RadioSet/Input, the shortcut
        # editor's table, the TUI switcher's list). Blanket rather than
        # per-class so a future modal is covered without enumeration.
        #
        # No try/except: App.__init__ seeds the screen stack, so screen_stack is
        # exception-free even pre-mount (it returns []). Guarding it could only
        # ever fail OPEN and let a priority arrow hijack a modal widget.
        if action in NAV_ACTIONS:
            return len(self.screen_stack) <= 1
        # Tab gate first: a Branches-only action is not part of another tab's
        # vocabulary, so `False` drops it from the footer entirely. The row gate
        # below keeps `None` (dimmed) — same tab, just a non-applicable row.
        if action in BRANCH_TAB_ACTIONS:
            if self._active_tab() != "tab_branches":
                return False
        if action in VERSION_TAB_ACTIONS:
            if self._active_tab() != "tab_versions":
                return False
        if action in SETTINGS_TAB_ACTIONS:
            if self._active_tab() != "tab_settings":
                return False
        if action == "push_setting":
            # Second gate: the tab gate says "right tab", this says "there is
            # something to push". `False` above drops the key from the footer
            # entirely; `None` here dims it, the same split the ref gate below
            # uses. Pure in-memory — it reads the applied matrix, no I/O — so
            # it is safe on every refresh_bindings().
            if not self.multi_repo:
                return False
            row = self._selected_settings_row()
            if row is None or not row.has_source:
                return None
        if action in ("sync_data", "pull", "push"):
            if not action_allowed_for_ref(action, self._selected_row().ref_name):
                return None
        return True

    def on_tabbed_content_tab_activated(
        self, event: TabbedContent.TabActivated
    ) -> None:
        """Re-evaluate bindings after a tab switch.

        ←/→ on the tab bar changes no focus, so Textual never fires its
        focus-change bindings refresh — without this the footer keeps
        advertising the Branches keys that check_action has just made inert.

        Also the lazy-load trigger for the Versions tab: the shared "latest
        release" lookup is a network call, so it is paid on first sight of the
        tab rather than at boot.
        """
        self.refresh_bindings()
        if event.pane.id == "tab_versions" and not self._versions_loaded:
            self._versions_loaded = True
            self._request_versions()
        if event.pane.id == "tab_settings" and not self._settings_loaded:
            # Same lazy rule as Versions: reading the matrix shells one
            # `resolve_agent_string` per (repo, operation), so a user who never
            # opens the tab pays none of it.
            self._settings_loaded = True
            self._request_settings()

    # ---------------------------------------------------- tab bar <-> content

    def action_nav_down(self) -> None:
        """`down`: from the tab bar, enter the active pane's list at row 0."""
        bar = self._tab_bar()
        if bar is None or self.focused is not bar:
            # Not our key: ordinary DataTable cursor / VerticalScroll movement.
            raise SkipAction()
        if self._active_tab() not in TAB_LIST_IDS:
            # A pane with no list: consume and stay on the bar rather than
            # throwing on a query that was never going to match. Unreachable
            # since t1223_5 gave Settings a real table — kept for a future
            # non-list pane.
            return
        table = self._active_list()
        if table is None:
            # Mapped but not composed — hand the key back instead of eating it.
            raise SkipAction()
        table.focus()
        if table.row_count:
            table.move_cursor(row=0)

    def action_nav_up(self) -> None:
        """`up`: on the list's first row, hand focus back to the tab bar."""
        table = self._active_list()
        if table is None or self.focused is not table or table.cursor_row > 0:
            # Mid-list, or a widget that owns its own vertical movement.
            raise SkipAction()
        bar = self._tab_bar()
        if bar is None:
            raise SkipAction()
        bar.focus()

    def _switch_tab(self, direction: int) -> None:
        """Move one tab, from anywhere. Delegates to Tabs so wrap matches the bar.

        Focus must leave the current pane *first*: activating another tab while a
        widget inside the current pane holds focus is silently reverted (t1060).
        Focus then stays on the bar, from which `down` re-enters content — the
        same convention as brainstorm's `_select_tab`.
        """
        bar = self._tab_bar()
        if bar is None:
            raise SkipAction()
        bar.focus()
        if direction > 0:
            bar.action_next_tab()
        else:
            bar.action_previous_tab()

    def action_prev_tab(self) -> None:
        """`left`: previous tab, regardless of what holds focus."""
        self._switch_tab(-1)

    def action_next_tab(self) -> None:
        """`right`: next tab, regardless of what holds focus."""
        self._switch_tab(+1)

    def _set_busy(self, busy: bool) -> None:
        try:
            self.query_one("#branches", DataTable).loading = busy
        except Exception:
            pass

    # ------------------------------------------------------------- refresh

    def action_refresh(self) -> None:
        """Manual refresh (`r`): fetch the highlighted row's repo on demand."""
        if self.multi_repo:
            self._request_refresh(self._selected_row().session_key, explicit=True)
        else:
            self._request_refresh(None, explicit=True)

    def _tick_refresh(self) -> None:
        """Automatic tick: fetch the least-recently-fetched repo."""
        if self.multi_repo:
            self._request_refresh(
                least_recent_fetch_key(self.sessions, self._last_fetch_attempt_ts)
            )
        else:
            self._request_refresh(None)

    def action_toggle_fetch(self) -> None:
        self._fetch = not self._fetch
        self._update_subtitle()
        self.notify(f"Fetch {'enabled' if self._fetch else 'disabled'}")
        self.call_later(self._tick_refresh)

    def _request_refresh(self, fetch_key: str | None, explicit: bool = False) -> None:
        start, self._pending_fetch = coalesce_request(
            self._refresh_active, self._pending_fetch, fetch_key, explicit
        )
        if not start:
            return
        self._refresh_gen += 1
        self._refresh_active = True
        self._refresh_worker(self._refresh_gen, fetch_key)

    @work(thread=True, exclusive=True, group="syncer-refresh")
    def _refresh_worker(self, gen: int, fetch_key: str | None) -> None:
        worker = get_current_worker()
        results: dict[str, dict[str, Any]] = {}
        fetched_keys: list[str] = []
        try:
            if not self.multi_repo:
                results[""] = snapshot(None, self._fetch)
                if self._fetch:
                    fetched_keys.append("")
            else:
                for sess in self.sessions:
                    if worker is not None and worker.is_cancelled:
                        # Cancellation must still finish, or _refresh_active
                        # stays stuck true and refreshing halts forever.
                        try:
                            self.call_from_thread(self._finish_refresh_cancelled)
                        except Exception:
                            pass  # app tearing down — nothing left to unstick
                        return
                    do_fetch = self._fetch and sess.key == fetch_key
                    results[sess.key] = snapshot(
                        None, do_fetch, root=sess.project_root
                    )
                    if do_fetch:
                        fetched_keys.append(sess.key)
        except Exception as exc:  # pragma: no cover — defensive
            self.call_from_thread(self._on_refresh_error, str(exc))
            return
        self.call_from_thread(
            self._apply_refresh, gen, results, fetched_keys, time.time()
        )

    def _on_refresh_error(self, message: str) -> None:
        self.notify(f"Refresh failed: {message}", severity="error")
        self._finish_refresh()

    def _apply_refresh(
        self,
        gen: int,
        results: dict[str, dict[str, Any]],
        fetched_keys: list[str],
        ts: float,
    ) -> None:
        # Supersession backstop: only the newest generation may mutate state
        # (no cell writes, no stamp writes for a superseded pass).
        if gen == self._refresh_gen:
            self._snapshots.update(results)
            for key in fetched_keys:
                # Attempt stamp: every tried fetch advances the LRU scheduler
                # (retry cooldown for failing repos = one full cycle).
                self._last_fetch_attempt_ts[key] = ts
                statuses = [
                    str(ref.get("status", ""))
                    for ref in results.get(key, {}).get("refs", [])
                ]
                # Success stamp: only a fetch that reached origin refreshes
                # the displayed age.
                if should_stamp_fetch(True, statuses):
                    self._last_fetch_ts[key] = ts
            self._last_refresh_clock = _format_clock(ts)
            self._update_table(ts)
            self._refresh_detail()
        self._finish_refresh()

    def _finish_refresh(self) -> None:
        self._refresh_active = False
        if self._pending_fetch is not PENDING_UNSET:
            key, explicit = self._pending_fetch  # type: ignore[misc]
            self._pending_fetch = PENDING_UNSET
            self._request_refresh(key, explicit=explicit)

    def _finish_refresh_cancelled(self) -> None:
        """Cancellation-specific finish: unstick the active flag WITHOUT
        dispatching the pending slot (cancellation normally means shutdown;
        dispatching here could respawn a worker loop). A queued pending
        request still fires after the next completed refresh."""
        self._refresh_active = False

    def _update_table(self, now: float) -> None:
        table = self.query_one("#branches", DataTable)
        for row in self._rows:
            snap = self._snapshots.get(row.session_key)
            ref = self._find_ref(row) if snap else None
            if ref is None:
                table.update_cell(row.row_key, "status", "missing" if snap else "loading…")
                table.update_cell(row.row_key, "ahead", "")
                table.update_cell(row.row_key, "behind", "")
            else:
                status = ref["status"]
                if status == "ok":
                    ahead = str(ref.get("ahead", 0))
                    behind = str(ref.get("behind", 0))
                else:
                    ahead = ""
                    behind = ""
                table.update_cell(row.row_key, "status", status)
                table.update_cell(row.row_key, "ahead", ahead)
                table.update_cell(row.row_key, "behind", behind)
            table.update_cell(row.row_key, "last", self._last_cell(row, now))

    def _last_cell(self, row: RowSpec, now: float) -> str:
        if not self.multi_repo:
            return self._last_refresh_clock
        stamp = self._last_fetch_ts.get(row.session_key)
        return format_age(None if stamp is None else now - stamp)

    def _update_age_cells(self) -> None:
        """Display-only tick: recompute Fetched ages from stamps (no git)."""
        try:
            table = self.query_one("#branches", DataTable)
        except Exception:
            return
        now = time.time()
        for row in self._rows:
            table.update_cell(row.row_key, "last", self._last_cell(row, now))

    # ------------------------------------------------------------ versions

    def action_recheck_version(self) -> None:
        """Re-read the targets' VERSION files (and, if fetching, the latest)."""
        self._versions_loaded = True
        self._request_versions(explicit=True)

    def _request_versions(self, explicit: bool = False) -> None:
        """Coalesced versions refresh.

        Reuses the same pure ``coalesce_request`` policy as the branches
        refresh (single worker, single latest-wins pending slot) with its own
        generation counter, so a 10s-bounded GitHub call can never delay — or
        be delayed by — the git-sync tick.
        """
        start, self._pending_versions = coalesce_request(
            self._versions_active, self._pending_versions, None, explicit
        )
        if not start:
            return
        self._versions_gen += 1
        self._versions_active = True
        self._versions_worker(self._versions_gen, self._fetch)

    @work(thread=True, exclusive=True, group="syncer-versions")
    def _versions_worker(self, gen: int, do_fetch: bool) -> None:
        installed = {
            sess.key: read_installed_version(sess.project_root)
            for sess in self.sessions
        }
        # ONE shared resolution for every row. Resolving per repo would make
        # network cost scale with repo count for a value that is identical
        # across them.
        latest: str | None = None
        latest_error: str | None = None
        if do_fetch:
            latest, latest_error = resolve_latest_version()
        # Liveness of any launched upgrade, off the UI thread.
        finished: list[str] = []
        for key, run in list(self._upgrades.items()):
            if not run.in_flight:
                continue
            if run.pane_pid is None or resolve_pane_id_by_pid(
                run.session_name, run.pane_pid
            ) is None:
                finished.append(key)
        self.call_from_thread(
            self._apply_versions, gen, installed, latest, latest_error,
            do_fetch, finished,
        )

    def _apply_versions(
        self,
        gen: int,
        installed: dict[str, str | None],
        latest: str | None,
        latest_error: str | None,
        did_fetch: bool,
        finished: list[str],
    ) -> None:
        if gen == self._versions_gen:
            self._installed = installed
            if did_fetch and latest is not None:
                self._latest = latest
                self._latest_error = None
                self._latest_stale = False
            elif did_fetch:
                # Keep the last known value rather than blanking it, but say so.
                self._latest_error = latest_error
                self._latest_stale = self._latest is not None
            else:
                self._latest_stale = self._latest is not None
            for key in finished:
                run = self._upgrades.get(key)
                if run is not None:
                    self._upgrades[key] = UpgradeRun(
                        state=UPGRADE_FINISHED,
                        session_name=run.session_name,
                        pane_pid=run.pane_pid,
                        pane_id=run.pane_id,
                        started_at=run.started_at,
                    )
            self._update_versions_table()
        self._finish_versions()

    def _finish_versions(self) -> None:
        self._versions_active = False
        if self._pending_versions is not PENDING_UNSET:
            _, explicit = self._pending_versions  # type: ignore[misc]
            self._pending_versions = PENDING_UNSET
            self._request_versions(explicit=explicit)

    def _update_versions_table(self) -> None:
        try:
            table = self.query_one("#versions", DataTable)
        except Exception:
            return
        for row in self._version_rows:
            run = self._upgrades.get(row.session_key)
            installed = self._installed.get(row.session_key)
            # While an upgrade is in flight the version cells show the last
            # value actually READ, marked stale — never the version we asked
            # for. The UI must not render a success it did not observe.
            in_flight = run is not None and run.in_flight
            installed_cell = installed or "—"
            if in_flight and installed:
                installed_cell = f"{installed}{STALE_MARKER}"
            latest_cell = self._latest or "—"
            if self._latest and (self._latest_stale or in_flight):
                latest_cell = f"{self._latest}{STALE_MARKER}"
            table.update_cell(row.row_key, "installed", installed_cell)
            table.update_cell(row.row_key, "latest", latest_cell)
            table.update_cell(
                row.row_key, "vstatus", version_status(installed, self._latest)
            )
            table.update_cell(row.row_key, "state", upgrade_state_cell(run))

    # -------------------------------------------------------------- upgrade

    def _selected_version_row(self) -> VersionRow | None:
        try:
            table = self.query_one("#versions", DataTable)
        except Exception:
            return self._version_rows[0] if self._version_rows else None
        if table.cursor_row is not None and table.row_count > 0:
            try:
                row_key, _ = table.coordinate_to_cell_key((table.cursor_row, 0))
                if row_key.value and row_key.value in self._version_rows_by_key:
                    return self._version_rows_by_key[str(row_key.value)]
            except Exception:
                pass
            idx = max(0, min(table.cursor_row, len(self._version_rows) - 1))
            return self._version_rows[idx]
        return self._version_rows[0] if self._version_rows else None

    def _capture_target(self) -> UpgradeTarget | None:
        """Freeze the highlighted repo into an immutable upgrade target.

        This is the ONLY point in the whole flow that reads the table, the row
        map, or the session list. Everything after it works from the returned
        record, so a cursor move (or a future row rebuild) while a modal is
        open cannot redirect the upgrade at another repository.
        """
        row = self._selected_version_row()
        if row is None:
            return None
        sess = self._session_by_key.get(row.session_key)
        if sess is None:
            self.notify(
                f"{row.project_label}: project no longer discovered",
                severity="error",
            )
            return None
        if not sess.project_root.is_dir():
            self.notify(
                f"{row.project_label}: project root missing ({sess.project_root})",
                severity="error",
            )
            return None
        return UpgradeTarget(
            session_key=row.session_key,
            session_name=sess.session,
            is_live=sess.is_live,
            root=sess.project_root,
            label=row.project_label,
            installed=self._installed.get(row.session_key),
        )

    def _probe_activity(self, target: UpgradeTarget) -> str:
        """Classify framework activity in the target repo's tmux session.

        Fail-closed at BOTH layers. ``detect_target_activity`` already refuses
        to report a possibly-busy target idle when its classifier is degraded;
        this wrapper covers the other half — a failed *enumeration*. The plain
        ``get_tmux_windows`` reports a tmux timeout, a vanished session and a
        genuinely window-less session all as ``[]``, which the classifier would
        read as ``idle``, so the checked variant is used and a failure becomes
        an explicit unknown rather than a silent green light.
        """
        if not target.is_live:
            # Registry-synthesized: there is no session to interrogate, and
            # asking would be a tmux call for a guaranteed-empty answer.
            return "idle"
        windows, err = get_tmux_windows_result(target.session_name)
        if err is not None:
            return "unknown:tmux-enumeration-failed"
        return detect_target_activity(target.session_name, windows)

    def action_upgrade(self) -> None:
        """Upgrade the highlighted repo's framework (`U`)."""
        target = self._capture_target()
        if target is None:
            return

        def on_version(version: str | None) -> None:
            if version:
                self._begin_upgrade(target, version)

        self.push_screen(
            UpgradeTargetScreen(target.label, target.installed), on_version
        )

    def _begin_upgrade(self, target: UpgradeTarget, version: str) -> None:
        """Route to the self-repo handoff or the cross-repo activity gate.

        Self-target is checked FIRST and is never force-gated. The syncer's own
        repo is where the user works, so it nearly always has live framework
        windows; refusing on that basis would leave the exit-then-upgrade
        handoff — the one path that is actually safe for this repo — reachable
        only through the destructive force override.
        """
        if is_self_target(target.root, Path.cwd()):
            self._begin_self_upgrade(target, version)
            return
        activity = self._probe_activity(target)
        if activity == "idle":
            self._confirm_spawn(target, version)
            return
        self._refuse_upgrade(target, version, activity)

    def _begin_self_upgrade(self, target: UpgradeTarget, version: str) -> None:
        handoff_path = os.environ.get("AIT_SYNCER_HANDOFF")
        if not handoff_path:
            # Fail closed: never spawn into our own repo, never no-op silently.
            self.notify(
                "Cannot upgrade this repo: the syncer was not launched via "
                "`ait syncer`. Relaunch it that way, or run `ait upgrade` "
                "from a shell.",
                severity="error",
                timeout=10,
            )
            return
        activity = self._probe_activity(target)

        def on_confirm(ok: bool | None) -> None:
            if not ok:
                return
            try:
                write_handoff_request(
                    handoff_path, build_handoff_request(target.root, version)
                )
            except Exception as exc:
                self.notify(f"Could not write handoff request: {exc}", severity="error")
                return
            self.exit()

        self.push_screen(
            HandoffConfirmScreen(
                target.label, str(target.root), version, activity
            ),
            on_confirm,
        )

    def _refuse_upgrade(
        self, target: UpgradeTarget, version: str, activity: str
    ) -> None:
        def on_choice(choice: str | None) -> None:
            if choice != "force":
                return
            # Re-probe immediately before offering the destructive confirm, so
            # what the user accepts is the CURRENT state, not what the refusal
            # happened to show a few seconds ago.
            fresh = self._probe_activity(target)
            if fresh == "idle":
                self._confirm_spawn(target, version)
                return
            if fresh != activity:
                self.notify("Target activity changed — re-checking.")
                self._refuse_upgrade(target, version, fresh)
                return

            def on_force(ok: bool | None) -> None:
                if ok:
                    self._spawn_upgrade(target, version)

            self.push_screen(
                ForceConfirmScreen(
                    target.label, str(target.root), version, fresh
                ),
                on_force,
            )

        self.push_screen(UpgradeRefusalScreen(target.label, activity), on_choice)

    def _confirm_spawn(self, target: UpgradeTarget, version: str) -> None:
        def on_confirm(ok: bool | None) -> None:
            if ok:
                self._spawn_upgrade(target, version)

        self.push_screen(
            UpgradeConfirmScreen(target.label, str(target.root), version),
            on_confirm,
        )

    def _spawn_upgrade(self, target: UpgradeTarget, version: str) -> None:
        if not is_tmux_available():
            self.notify(
                "tmux is not available — run `ait upgrade` in that repo from a "
                "shell instead.",
                severity="error",
            )
            return
        try:
            command, _ = build_upgrade_command(target.root, version)
        except ValueError as exc:  # pragma: no cover — dialog already validated
            self.notify(f"Refusing to upgrade: {exc}", severity="error")
            return
        existing = {name for _idx, name in get_tmux_windows_result(
            target.session_name
        )[0]}
        window = unique_window_name(existing, f"upgrade-{target.label}")
        pane_pid, err = launch_in_tmux(
            command,
            TmuxLaunchConfig(
                session=target.session_name,
                window=window,
                new_session=target.session_name not in get_tmux_sessions(),
                new_window=True,
                cwd=str(target.root),
            ),
        )
        if err:
            self.notify(err, severity="error")
            return
        pane_id = (
            resolve_pane_id_by_pid(target.session_name, pane_pid)
            if pane_pid
            else None
        )
        # No pane pid means we can never observe this run, so it goes straight
        # to "result unknown" rather than sitting in a state we cannot leave.
        state = UPGRADE_LAUNCHED if pane_pid else UPGRADE_FINISHED
        self._upgrades[target.session_key] = UpgradeRun(
            state=state,
            session_name=target.session_name,
            pane_pid=pane_pid,
            pane_id=pane_id,
            started_at=time.time(),
        )
        self._update_versions_table()
        self.notify(f"Upgrade launched for {target.label} in window {window}.")

    # ------------------------------------------------------------- settings

    def action_reload_settings(self) -> None:
        """Re-read the cross-repo settings matrix (`c` on the Settings tab)."""
        self._settings_loaded = True
        self._request_settings(explicit=True)

    def _request_settings(self, explicit: bool = False) -> None:
        """Coalesced settings refresh — same policy as branches and versions."""
        start, self._pending_settings = coalesce_request(
            self._settings_active, self._pending_settings, None, explicit
        )
        if not start:
            return
        self._settings_gen += 1
        self._settings_active = True
        self._settings_worker(self._settings_gen)

    @work(thread=True, exclusive=True, group="syncer-settings")
    def _settings_worker(self, gen: int) -> None:
        try:
            diff, unreadable, unattributed = self._read_settings_matrix()
        except Exception as exc:  # pragma: no cover — defensive
            # Same hazard the branches worker documents: an escaping exception
            # never reaches _finish_settings, so _settings_active stays true
            # and every later request parks in the pending slot forever —
            # `c` would silently stop working for the rest of the session.
            self.call_from_thread(self._on_settings_error, str(exc))
            return
        self.call_from_thread(
            self._apply_settings, gen, diff, unreadable, unattributed
        )

    def _on_settings_error(self, message: str) -> None:
        self.notify(f"Settings read failed: {message}", severity="error")
        self._finish_settings()

    def _read_settings_matrix(
        self,
    ) -> tuple[dict[str, dict[str, OperationValue]], dict[str, str], str | None]:
        """Read the matrix, degrading per repo when one is unreadable.

        ``diff_across_repos`` aborts GLOBALLY on the first corrupt repo — it
        reads every root's layers in one unguarded loop — so a single call
        cannot give the per-repo degradation this tab promises. Hence a
        shrink-and-retry loop:

        * The happy path costs exactly one call; the extra sweeps are paid only
          when something is actually broken (and a broken root fails its probe
          before spawning any subprocess).
        * Each round either removes at least one attributable offender or spends
          the single non-attributable retry, so the loop is bounded at
          ``len(sessions) + 2`` attempts.
        * A repo that breaks BETWEEN the sweep and the retry costs only its own
          column — the repos that passed keep theirs. Marking everything
          unreadable on a raced failure would destroy exactly the guarantee this
          method exists to provide.
        * A failure the sweep cannot attribute to any repo blames NO repo: we
          did not establish that, so it is surfaced as a tab-level reason
          instead of invented per-repo blame.
        """
        good = list(self.sessions)
        unreadable: dict[str, str] = {}
        unattributed: str | None = None
        for _ in range(len(self.sessions) + 2):
            if not good:
                return {}, unreadable, None
            try:
                return (
                    diff_across_repos([s.project_root for s in good]),
                    unreadable,
                    None,
                )
            except DestConfigUnreadable as exc:
                still_good: list[AitasksSession] = []
                newly_bad = False
                for sess in good:
                    try:
                        read_operation_defaults(sess.project_root)
                        still_good.append(sess)
                    except DestConfigUnreadable as probe_exc:
                        unreadable[sess.key] = str(probe_exc)
                        newly_bad = True
                if not newly_bad:
                    if unattributed is not None:
                        return {}, unreadable, unattributed
                    unattributed = str(exc)
                    continue
                good = still_good
                unattributed = None
        return {}, unreadable, unattributed

    def _apply_settings(
        self,
        gen: int,
        diff: dict[str, dict[str, OperationValue]],
        unreadable: dict[str, str],
        unattributed: str | None,
    ) -> None:
        if gen == self._settings_gen:
            self._settings_unreadable = unreadable
            self._settings_unattributed = unattributed
            self._settings_rows = build_settings_matrix(
                diff,
                [s.key for s in self.sessions],
                frozenset(unreadable),
            )
            self._settings_rows_by_key = {
                r.row_key: r for r in self._settings_rows
            }
            self._update_settings_table()
            if unattributed:
                self.notify(
                    f"Settings could not be read ({unattributed}) — press `c` "
                    "to retry.",
                    severity="warning",
                )
            self.refresh_bindings()
        self._finish_settings()

    def _finish_settings(self) -> None:
        self._settings_active = False
        if self._pending_settings is not PENDING_UNSET:
            _, explicit = self._pending_settings  # type: ignore[misc]
            self._pending_settings = PENDING_UNSET
            self._request_settings(explicit=explicit)

    def _update_settings_table(self) -> None:
        try:
            table = self.query_one("#settings", DataTable)
        except Exception:
            return
        # The row set is data-derived, so it is rebuilt rather than updated in
        # place — which is exactly why the push flow captures a frozen target.
        table.clear()
        for row in self._settings_rows:
            table.add_row(
                DIVERGE_MARKER if row.divergent else "",
                row.operation,
                *row.cells,
                key=row.row_key,
            )

    def _selected_settings_row(self) -> SettingsRow | None:
        if not self._settings_rows:
            return None
        try:
            table = self.query_one("#settings", DataTable)
        except Exception:
            return self._settings_rows[0]
        if table.cursor_row is not None and table.row_count > 0:
            try:
                row_key, _ = table.coordinate_to_cell_key((table.cursor_row, 0))
                if row_key.value and row_key.value in self._settings_rows_by_key:
                    return self._settings_rows_by_key[str(row_key.value)]
            except Exception:
                pass
            idx = max(0, min(table.cursor_row, len(self._settings_rows) - 1))
            return self._settings_rows[idx]
        return self._settings_rows[0]

    def _capture_push_target(self) -> PushTarget | None:
        """Freeze the highlighted operation into an immutable push target.

        The only point in the flow that reads the settings table or its row
        map. Everything downstream works from the returned record, so a cursor
        move — or the row rebuild that every refresh performs — while a modal is
        open cannot redirect the push at another operation.
        """
        row = self._selected_settings_row()
        if row is None:
            return None
        return PushTarget(
            operation=row.operation,
            repos=tuple(
                (s.key, self._settings_labels.get(s.key, s.project_name))
                for s in self.sessions
            ),
            sources=row.sources,
        )

    def action_push_setting(self) -> None:
        """Propagate one operation's value to other repos (`P`).

        Guards itself rather than relying on ``check_action``: that gates the
        key binding, not the method, and actions are also invoked directly (the
        test suite does exactly this). Without the re-check an unloaded or
        all-conflict matrix would walk into a flow with no target.
        """
        if not self.multi_repo:
            self.notify(
                "Only one repository discovered — nothing to push to.",
                severity="warning",
            )
            return
        target = self._capture_push_target()
        if target is None:
            self.notify(
                "Settings are not loaded yet — press `c` to load them.",
                severity="warning",
            )
            return
        options = target.source_options()
        if not options:
            self.notify(
                f"No repository holds a usable value for `{target.operation}` "
                "(unreadable or conflicting).",
                severity="warning",
            )
            return

        self._pick_source(target)

    # The three wizard steps below are mutually recursive on purpose: Esc (or
    # the Back button) dismisses BACK, and the caller re-pushes the PREVIOUS
    # step with the earlier choice still selected. Every step reads only its
    # arguments and the frozen `target`, never the table, so going back and
    # forward cannot redirect the push at another operation.

    def _pick_source(
        self, target: PushTarget, initial: str | None = None
    ) -> None:
        def on_source(source_key: str | None) -> None:
            if source_key is None:      # step 1: back == cancel the push
                return
            self._choose_destinations(target, source_key)

        self.push_screen(
            SettingsSourceScreen(target.operation, target.source_options(), initial),
            on_source,
        )

    def _source_value(self, target: PushTarget, source_key: str) -> str:
        for (key, _label), value in zip(target.repos, target.sources):
            if key == source_key and value is not None:
                return value
        # Unreachable through the UI: the picker only offers eligible repos.
        raise KeyError(source_key)

    def _choose_destinations(
        self, target: PushTarget, source_key: str,
        initial: tuple[str, ...] = (),
    ) -> None:
        value = self._source_value(target, source_key)
        # The source is removed HERE, at construction: destinations are "the
        # other repos", and leaving it in would guarantee a self-targeted noop
        # row in the summary that reads as a defect. Note the list is NOT
        # filtered by source-eligibility — a conflicted repo is a legitimate
        # (and valuable) destination.
        dests = target.destinations_excluding(source_key)

        def on_dests(chosen) -> None:
            if chosen == BACK:
                self._pick_source(target, initial=source_key)
                return
            if not chosen:
                return
            self._choose_layer(target, source_key, value, chosen)

        self.push_screen(
            SettingsDestinationsScreen(
                target.operation, value, dests, initial=initial
            ),
            on_dests,
        )

    def _choose_layer(
        self, target: PushTarget, source_key: str, value: str,
        dests: tuple[str, ...],
    ) -> None:
        labels = dict(target.repos)

        def on_layer(layer: str | None) -> None:
            if layer == BACK:
                self._choose_destinations(target, source_key, initial=dests)
                return
            if layer is None:
                return
            self._plan_pushes(target, value, dests, layer)

        self.push_screen(
            SettingsLayerScreen(
                target.operation, value, [labels[k] for k in dests]
            ),
            on_layer,
        )

    def _plan_pushes(
        self, target: PushTarget, value: str, dests: tuple[str, ...], layer: str
    ) -> None:
        self._push_plan_worker(target.operation, value, dests, layer)

    @work(thread=True, group="syncer-settings-push")
    def _push_plan_worker(
        self, operation: str, value: str, dests: tuple[str, ...], layer: str
    ) -> None:
        """Plan every destination off the UI thread; never let one kill the run.

        Each ``plan_push`` shells the destination's resolver with a 10s timeout,
        so this cannot run on the UI thread. The per-destination boundary is the
        same discipline the apply phase uses: an unhandled exception here would
        terminate the worker, so the summary would never open and every later
        destination would be silently unconsidered.
        """
        try:
            planned = self._plan_each(operation, value, dests, layer)
        except Exception as exc:  # pragma: no cover — defensive
            # The per-destination boundary below already absorbs plan_push
            # failures; this covers everything around it, so choosing a layer
            # can never end in silence with no summary.
            self.call_from_thread(
                self.notify, f"Push planning failed: {exc}", severity="error"
            )
            return
        self.call_from_thread(
            self._resolve_masked, operation, value, layer, planned, []
        )

    def _plan_each(
        self, operation: str, value: str, dests: tuple[str, ...], layer: str
    ) -> list[tuple[str, str, str | None]]:
        planned: list[tuple[str, str, str | None]] = []
        for key in dests:
            sess = self._session_by_key.get(key)
            if sess is None:
                planned.append((key, "missing", "project no longer discovered"))
                continue
            try:
                outcome = plan_push(value, sess.project_root, operation, layer)
            except Exception as exc:  # planning must not kill the worker
                planned.append((key, "planning_failed", f"could not be planned: {exc}"))
                continue
            if outcome.kind == "masked":
                planned.append((key, "masked", outcome.masking_value))
            elif outcome.kind == "rejected":
                planned.append((key, "rejected", outcome.reason))
            else:
                planned.append((key, outcome.kind, None))
        return planned

    def _resolve_masked(
        self,
        operation: str,
        value: str,
        layer: str,
        pending: list[tuple[str, str, str | None]],
        decided: list[tuple[str, str, str | None]],
    ) -> None:
        """Drain the masked destinations one modal at a time, then apply.

        Recursive rather than a loop: each prompt resumes in a callback, so the
        remaining queue is carried forward explicitly.
        """
        labels = dict(
            (s.key, self._settings_labels.get(s.key, s.project_name))
            for s in self.sessions
        )
        queue = list(pending)
        while queue:
            key, kind, extra = queue.pop(0)
            if kind != "masked":
                decided.append((key, kind, extra))
                continue

            def on_choice(
                choice: str | None,
                _key: str = key,
                _extra: str | None = extra,
                _rest: list[tuple[str, str, str | None]] = queue,
            ) -> None:
                resolved = choice or "cancel"
                if resolved == "cancel":
                    decided.append((_key, "cancelled", _extra))
                elif resolved == "local":
                    decided.append((_key, "apply_local", None))
                else:
                    decided.append((_key, "apply_clear", None))
                self._resolve_masked(operation, value, layer, _rest, decided)

            self.push_screen(
                SettingsMaskedScreen(
                    labels.get(key, key), operation, value, extra
                ),
                on_choice,
            )
            return
        self._apply_pushes(operation, value, layer, decided)

    def _apply_pushes(
        self,
        operation: str,
        value: str,
        layer: str,
        decided: list[tuple[str, str, str | None]],
    ) -> None:
        self._push_apply_worker(operation, value, layer, decided)

    @work(thread=True, group="syncer-settings-push")
    def _push_apply_worker(
        self,
        operation: str,
        value: str,
        layer: str,
        decided: list[tuple[str, str, str | None]],
    ) -> None:
        results: list[tuple[str, str]] = []
        for key, kind, extra in decided:
            sess = self._session_by_key.get(key)
            label = self._settings_labels.get(key, key)
            if kind == "noop":
                results.append((label, "already matches — nothing written"))
                continue
            if kind == "cancelled":
                results.append((label, "skipped"))
                continue
            if kind == "rejected":
                results.append((label, f"rejected: {extra}"))
                continue
            if kind in ("planning_failed", "missing"):
                results.append((label, str(extra)))
                continue
            if sess is None:
                results.append((label, "project no longer discovered"))
                continue
            write_layer = "local" if kind == "apply_local" else layer
            clear_mask = kind == "apply_clear"
            try:
                apply_push(
                    value, sess.project_root, operation, write_layer,
                    clear_mask=clear_mask,
                )
                results.append((label, f"applied to the {write_layer} layer"))
            except PushPartialError as exc:
                # Neither success nor plain failure: the project layer landed
                # but the mask is still in place, so the repo's EFFECTIVE value
                # is unchanged and a retry converges.
                results.append((
                    label,
                    "partial — project written but the local override still "
                    f"sets {exc.masking_value!r}; retry to finish",
                ))
            except Exception as exc:
                results.append((label, f"failed: {exc}"))
        self.call_from_thread(self._report_pushes, operation, results)

    def _report_pushes(
        self, operation: str, results: list[tuple[str, str]]
    ) -> None:
        self.push_screen(SettingsPushResultScreen(operation, results))
        self._request_settings(explicit=True)

    # ----------------------------------------------------------- selection

    def _selected_row(self) -> RowSpec:
        try:
            table = self.query_one("#branches", DataTable)
        except Exception:
            return self._rows[0]
        if table.cursor_row is not None and table.row_count > 0:
            try:
                row_key, _ = table.coordinate_to_cell_key((table.cursor_row, 0))
                if row_key.value and row_key.value in self._rows_by_key:
                    return self._rows_by_key[str(row_key.value)]
            except Exception:
                pass
            idx = max(0, min(table.cursor_row, len(self._rows) - 1))
            return self._rows[idx]
        return self._rows[0]

    def _find_ref(self, row: RowSpec) -> dict[str, Any] | None:
        snap = self._snapshots.get(row.session_key) or {}
        for ref in snap.get("refs", []):
            if ref.get("name") == row.ref_name:
                return ref
        return None

    def _refresh_detail(self) -> None:
        detail = self.query_one("#detail", Static)
        row = self._selected_row()
        ref = self._find_ref(row)
        title = f"[b]{row.ref_name}[/b]"
        if self.multi_repo:
            title = f"[b]{row.project_label}[/b] · {title}"
        if ref is None:
            detail.update(f"{title}\nNo data yet.")
            return

        lines: list[str] = [f"{title}  [dim]({ref.get('worktree', '?')})[/dim]"]
        status = ref.get("status", "?")
        lines.append(f"Status: {status}")
        if status == "ok":
            lines.append(f"Ahead: {ref.get('ahead', 0)}    Behind: {ref.get('behind', 0)}")
        if ref.get("error"):
            lines.append(f"[red]Error:[/red] {ref['error']}")

        commits = ref.get("remote_commits") or []
        if commits:
            lines.append("")
            lines.append("[b]Remote commits not yet pulled:[/b]")
            for subject in commits[:DETAIL_MAX_COMMITS]:
                lines.append(f"  • {subject}")
            if len(commits) > DETAIL_MAX_COMMITS:
                lines.append(f"  [dim]… {len(commits) - DETAIL_MAX_COMMITS} more[/dim]")

        paths = ref.get("remote_changed_paths") or []
        if paths:
            lines.append("")
            lines.append("[b]Changed paths:[/b]")
            for path in paths[:DETAIL_MAX_PATHS]:
                lines.append(f"  • {path}")
            if len(paths) > DETAIL_MAX_PATHS:
                lines.append(f"  [dim]… {len(paths) - DETAIL_MAX_PATHS} more[/dim]")

        detail.update("\n".join(lines))

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self._refresh_detail()
        self.refresh_bindings()

    # ---------------------------------------------------------------- actions

    def _prefix(self, label: str, message: str) -> str:
        return f"{label}: {message}" if label else message

    def action_sync_data(self) -> None:
        row = self._selected_row()
        target = resolve_action_target(
            row, self._session_by_key, self._snapshots, need_branch=False
        )
        if isinstance(target, str):
            self.notify(target, severity="error")
            return
        self._set_busy(True)
        self._sync_data_worker(row, target)

    def action_pull(self) -> None:
        row = self._selected_row()
        target = resolve_action_target(
            row, self._session_by_key, self._snapshots, need_branch=True
        )
        if isinstance(target, str):
            self.notify(target, severity="error")
            return
        self._set_busy(True)
        self._main_pull_worker(row, target)

    def action_push(self) -> None:
        row = self._selected_row()
        target = resolve_action_target(
            row, self._session_by_key, self._snapshots, need_branch=True
        )
        if isinstance(target, str):
            self.notify(target, severity="error")
            return
        self._set_busy(True)
        self._main_push_worker(row, target)

    def action_agent_resolve(self) -> None:
        if self._last_failure is None:
            self.notify("No recent failure to resolve.", severity="information")
            return
        self._open_failure_screen(self._last_failure)

    def _post_action_refresh(self, row: RowSpec) -> None:
        """Fetch the acted-on repo so the action's result shows immediately."""
        self._request_refresh(
            row.session_key if self.multi_repo else None, explicit=True
        )

    # ------------------------------------------------- aitask-data sync flow

    @work(thread=True, exclusive=True, group="syncer-action")
    def _sync_data_worker(self, row: RowSpec, target: ActionTarget) -> None:
        try:
            result = run_sync_batch(repo_root=target.root)
            self.call_from_thread(self._on_data_sync_done, row, target, result)
        finally:
            self.call_from_thread(self._set_busy, False)

    def _on_data_sync_done(
        self, row: RowSpec, target: ActionTarget, result: SyncResult
    ) -> None:
        status = result.status
        label = target.label
        if target.root is None:
            sync_cmd = "./.aitask-scripts/aitask_sync.sh --batch"
        else:
            sync_cmd = f"{target.root}/.aitask-scripts/aitask_sync.sh --batch"

        if status == STATUS_CONFLICT:
            self.push_screen(
                SyncConflictScreen(result.conflicted_files),
                lambda resolve: self._on_conflict_resolved(resolve, target),
            )
            return

        if status == STATUS_TIMEOUT:
            self._capture_failure(
                row, "sync", sync_cmd, status,
                result.error_message or "timeout", result.raw_output,
            )
            self.notify(self._prefix(label, "Sync timed out"), severity="warning")
            self._post_action_refresh(row)
            return

        if status == STATUS_NOT_FOUND:
            self.notify(self._prefix(label, "Sync script not found"), severity="error")
            return

        if status == STATUS_ERROR:
            self._capture_failure(
                row, "sync", sync_cmd, status,
                result.error_message or "", result.raw_output,
            )
            self.notify(
                self._prefix(label, f"Sync error: {result.error_message}"),
                severity="error",
            )
        elif status == STATUS_NO_NETWORK:
            self.notify(self._prefix(label, "Sync: No network"), severity="warning")
        elif status == STATUS_NO_REMOTE:
            self.notify(self._prefix(label, "Sync: No remote configured"), severity="warning")
        elif status == STATUS_NOTHING:
            self.notify(self._prefix(label, "Already up to date"), severity="information")
        elif status == STATUS_AUTOMERGED:
            self.notify(self._prefix(label, "Sync: Auto-merged conflicts"), severity="information")
        elif status in (STATUS_PUSHED, STATUS_PULLED, STATUS_SYNCED):
            self.notify(self._prefix(label, f"Sync: {status.capitalize()}"), severity="information")

        self._post_action_refresh(row)

    def _on_conflict_resolved(self, resolve: bool, target: ActionTarget) -> None:
        if resolve:
            self._run_interactive_sync_shared(target)
        self._tick_refresh()

    @work(exclusive=True, group="syncer-action")
    async def _run_interactive_sync_shared(self, target: ActionTarget) -> None:
        run_interactive_sync(
            self.app,
            on_done=lambda: self.call_from_thread(self._tick_refresh),
            repo_root=target.root,
        )

    # ---------------------------------------------------- main pull / push

    def _git(self, args: list[str], cwd: str) -> tuple[int, str, str]:
        try:
            proc = subprocess.run(
                ["git", *args],
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=GIT_TIMEOUT_SECONDS,
            )
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return 124, "", f"git timed out after {GIT_TIMEOUT_SECONDS}s"
        except FileNotFoundError:
            return 127, "", "git executable not found"

    @work(thread=True, exclusive=True, group="syncer-action")
    def _main_pull_worker(self, row: RowSpec, target: ActionTarget) -> None:
        try:
            cwd = str(target.root)
            branch = target.branch or "main"
            label = target.label
            rc, head, _ = self._git(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
            head_name = head.strip() if rc == 0 else "?"
            if head_name != branch:
                self.call_from_thread(
                    self.notify,
                    self._prefix(
                        label,
                        f"Switch to {branch} to pull (currently on {head_name}).",
                    ),
                    severity="warning",
                )
                return

            rc, status_out, _ = self._git(["status", "--porcelain"], cwd)
            if rc == 0 and status_out.strip():
                self.call_from_thread(
                    self.notify,
                    self._prefix(
                        label, "Working tree dirty — stash or commit before pulling."
                    ),
                    severity="warning",
                )
                return

            rc, out, err = self._git(["pull", "--ff-only"], cwd)
            cmd = f"git -C {cwd} pull --ff-only"
            if rc != 0:
                tail = "\n".join((err or out).splitlines()[-FAILURE_TAIL_LINES:])
                self.call_from_thread(
                    self._fail, row, "pull", cmd, "ERROR", tail, out + err,
                )
                return
            self.call_from_thread(
                self.notify, self._prefix(label, "main: Pulled."), severity="information"
            )
            self.call_from_thread(self._post_action_refresh, row)
        finally:
            self.call_from_thread(self._set_busy, False)

    @work(thread=True, exclusive=True, group="syncer-action")
    def _main_push_worker(self, row: RowSpec, target: ActionTarget) -> None:
        try:
            cwd = str(target.root)
            branch = target.branch or "main"
            label = target.label
            rc, out, err = self._git(["push", "origin", f"{branch}:{branch}"], cwd)
            cmd = f"git -C {cwd} push origin {branch}:{branch}"
            if rc != 0:
                tail = "\n".join((err or out).splitlines()[-FAILURE_TAIL_LINES:])
                self.call_from_thread(
                    self._fail, row, "push", cmd, "ERROR", tail, out + err,
                )
                return
            self.call_from_thread(
                self.notify, self._prefix(label, "main: Pushed."), severity="information"
            )
            self.call_from_thread(self._post_action_refresh, row)
        finally:
            self.call_from_thread(self._set_busy, False)

    # ---------------------------------------------------- failure escape hatch

    def _capture_failure(
        self,
        row: RowSpec,
        action: str,
        command: str,
        status: str,
        stderr_tail: str,
        raw_output: str,
    ) -> None:
        display_ref = row.ref_name
        if self.multi_repo and row.project_label:
            display_ref = f"{row.project_label} {row.ref_name}"
        sess = self._session_by_key.get(row.session_key)
        self._last_failure = SyncFailureContext(
            ref_name=display_ref,
            action=action,
            command=command,
            status=status,
            stderr_tail=stderr_tail,
            raw_output=raw_output,
            repo_root=str(sess.project_root) if sess is not None else None,
        )

    def _fail(
        self,
        row: RowSpec,
        action: str,
        command: str,
        status: str,
        stderr_tail: str,
        raw_output: str,
    ) -> None:
        self._capture_failure(row, action, command, status, stderr_tail, raw_output)
        self._open_failure_screen(self._last_failure)  # type: ignore[arg-type]

    def _open_failure_screen(self, ctx: SyncFailureContext) -> None:
        def on_choice(launch: bool | None) -> None:
            if launch:
                self._launch_resolution_agent(ctx)

        self.push_screen(SyncFailureScreen(ctx), on_choice)

    def _launch_resolution_agent(self, ctx: SyncFailureContext) -> None:
        prompt = (
            "A sync action failed in the ait syncer TUI. Please investigate and "
            "resolve interactively with the user.\n\n"
            f"Branch: {ctx.ref_name}\n"
            f"Action: {ctx.action}\n"
            f"Command: {ctx.command}\n"
            f"Status: {ctx.status}\n\n"
            f"Output (tail):\n{ctx.stderr_tail or '(empty)'}\n"
        )
        project_root = Path(ctx.repo_root) if ctx.repo_root else Path(".")
        full_cmd = resolve_dry_run_command(project_root, "raw", prompt)
        if not full_cmd:
            self.notify(
                "Could not resolve agent command — check model configuration.",
                severity="error",
            )
            return
        agent_string = resolve_agent_string(project_root, "raw")
        screen = AgentCommandScreen(
            f"Resolve {ctx.action} failure on {ctx.ref_name}",
            full_cmd,
            prompt,
            default_window_name=f"agent-syncfix-{ctx.action}",
            project_root=project_root,
            operation="raw",
            operation_args=[prompt],
            default_agent_string=agent_string,
        )

        def on_launch(result: Any) -> None:
            if isinstance(result, TmuxLaunchConfig):
                _, err = launch_in_tmux(screen.full_command, result)
                if err:
                    self.notify(err, severity="error")
                elif result.new_window:
                    maybe_spawn_minimonitor(result.session, result.window)
            self._tick_refresh()

        self.push_screen(screen, on_launch)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ait syncer",
        description=(
            "TUI for tracking remote desync state of main and aitask-data refs "
            "across all discovered aitasks repos."
        ),
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=REFRESH_TICK_DEFAULT,
        help=(
            "Automatic refresh interval in seconds; each tick fetches the "
            f"least-recently-fetched repo (default: {REFRESH_TICK_DEFAULT})."
        ),
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Skip 'git fetch' before computing state (offline mode).",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    SyncerApp(args).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
