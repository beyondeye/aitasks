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
    launch_in_tmux,
    maybe_spawn_minimonitor,
    resolve_agent_string,
    resolve_dry_run_command,
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

from textual import work  # noqa: E402
from textual.app import App, ComposeResult  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.containers import Vertical, VerticalScroll  # noqa: E402
from textual.widgets import DataTable, Footer, Header, Static  # noqa: E402
from textual.worker import get_current_worker  # noqa: E402


REFRESH_TICK_DEFAULT = 60
AGE_TICK_SECONDS = 5
DETAIL_MAX_COMMITS = 20
DETAIL_MAX_PATHS = 50
GIT_TIMEOUT_SECONDS = 30
FAILURE_TAIL_LINES = 30

TRACKED_REFS = ("main", "aitask-data")

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
        Binding("q", "quit", "Quit"),
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
        yield Header()
        with Vertical():
            table = DataTable(id="branches", cursor_type="row", zebra_stripes=True)
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

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action in ("sync_data", "pull", "push"):
            if not action_allowed_for_ref(action, self._selected_row().ref_name):
                return None
        return True

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
