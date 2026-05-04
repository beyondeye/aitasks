"""ait syncer — TUI for tracking remote desync state.

Polls `lib/desync_state.snapshot()` for the project's `main` and
`aitask-data` refs and displays ahead/behind counts plus per-row detail
(commit subjects and changed paths). Action handlers (pull/push/sync)
land in sibling task t713_3 once the shared sync runner is extracted by
t713_8.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from desync_state import snapshot  # noqa: E402
from tui_switcher import TuiSwitcherMixin  # noqa: E402
from agent_launch_utils import (  # noqa: E402
    TmuxLaunchConfig,
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


REFRESH_TICK_DEFAULT = 30
DETAIL_MAX_COMMITS = 20
DETAIL_MAX_PATHS = 50
GIT_TIMEOUT_SECONDS = 30
FAILURE_TAIL_LINES = 30


def _format_clock(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S")


class SyncerApp(TuiSwitcherMixin, App):
    """Textual TUI for the syncer."""

    TITLE = "aitasks syncer"

    CSS = """
    Screen {
        layout: vertical;
    }
    #branches {
        height: auto;
        max-height: 12;
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
        self._last_snapshot: dict[str, Any] = {"refs": []}
        self._row_keys: list[str] = ["main", "aitask-data"]
        self._last_failure: SyncFailureContext | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            table = DataTable(id="branches", cursor_type="row", zebra_stripes=True)
            table.add_column("Branch", key="branch")
            table.add_column("Status", key="status")
            table.add_column("Ahead", key="ahead")
            table.add_column("Behind", key="behind")
            table.add_column("Last refresh", key="last")
            yield table
            with VerticalScroll(id="detail_scroll"):
                yield Static("Loading…", id="detail")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#branches", DataTable)
        for name in self._row_keys:
            table.add_row(name, "loading…", "", "", "", key=name)
        self.set_interval(self._interval, self.action_refresh)
        self.call_later(self.action_refresh)
        self._update_subtitle()

    def _update_subtitle(self) -> None:
        fetch_state = "on" if self._fetch else "off"
        self.sub_title = f"interval={self._interval}s  fetch={fetch_state}"

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        selected = self._selected_ref_name()
        if action == "sync_data" and selected != "aitask-data":
            return None
        if action in ("pull", "push") and selected != "main":
            return None
        return True

    def _set_busy(self, busy: bool) -> None:
        try:
            self.query_one("#branches", DataTable).loading = busy
        except Exception:
            pass

    def action_refresh(self) -> None:
        self._refresh_worker()

    def action_toggle_fetch(self) -> None:
        self._fetch = not self._fetch
        self._update_subtitle()
        self.notify(f"Fetch {'enabled' if self._fetch else 'disabled'}")
        self.call_later(self.action_refresh)

    @work(thread=True, exclusive=True, group="syncer-refresh")
    def _refresh_worker(self) -> None:
        try:
            data = snapshot(None, self._fetch)
        except Exception as exc:  # pragma: no cover — defensive
            self.call_from_thread(self._notify_refresh_error, str(exc))
            return
        ts = time.time()
        self.call_from_thread(self._apply_snapshot, data, ts)

    def _notify_refresh_error(self, message: str) -> None:
        self.notify(f"Refresh failed: {message}", severity="error")

    def _apply_snapshot(self, data: dict[str, Any], ts: float) -> None:
        self._last_snapshot = data
        clock = _format_clock(ts)
        table = self.query_one("#branches", DataTable)

        by_name = {ref["name"]: ref for ref in data.get("refs", [])}
        for name in self._row_keys:
            ref = by_name.get(name)
            if ref is None:
                table.update_cell(name, "status", "missing")
                table.update_cell(name, "ahead", "")
                table.update_cell(name, "behind", "")
                table.update_cell(name, "last", clock)
                continue
            status = ref["status"]
            if status == "ok":
                ahead = str(ref.get("ahead", 0))
                behind = str(ref.get("behind", 0))
            else:
                ahead = ""
                behind = ""
            table.update_cell(name, "status", status)
            table.update_cell(name, "ahead", ahead)
            table.update_cell(name, "behind", behind)
            table.update_cell(name, "last", clock)

        self._refresh_detail()

    def _selected_ref_name(self) -> str:
        table = self.query_one("#branches", DataTable)
        if table.cursor_row is None or table.row_count == 0:
            return self._row_keys[0]
        try:
            row_key, _ = table.coordinate_to_cell_key((table.cursor_row, 0))
            if row_key.value:
                return str(row_key.value)
        except Exception:
            pass
        idx = max(0, min(table.cursor_row, len(self._row_keys) - 1))
        return self._row_keys[idx]

    def _find_ref(self, name: str) -> dict[str, Any] | None:
        for ref in self._last_snapshot.get("refs", []):
            if ref.get("name") == name:
                return ref
        return None

    def _refresh_detail(self) -> None:
        detail = self.query_one("#detail", Static)
        name = self._selected_ref_name()
        ref = self._find_ref(name)
        if ref is None:
            detail.update(f"[b]{name}[/b]\nNo data yet.")
            return

        lines: list[str] = [f"[b]{ref['name']}[/b]  [dim]({ref.get('worktree', '?')})[/dim]"]
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

    def action_sync_data(self) -> None:
        self._set_busy(True)
        self._sync_data_worker()

    def action_pull(self) -> None:
        self._set_busy(True)
        self._main_pull_worker()

    def action_push(self) -> None:
        self._set_busy(True)
        self._main_push_worker()

    def action_agent_resolve(self) -> None:
        if self._last_failure is None:
            self.notify("No recent failure to resolve.", severity="information")
            return
        self._open_failure_screen(self._last_failure)

    # ------------------------------------------------- aitask-data sync flow

    @work(thread=True, exclusive=True, group="syncer-action")
    def _sync_data_worker(self) -> None:
        try:
            result = run_sync_batch()
            self.call_from_thread(self._on_data_sync_done, result)
        finally:
            self.call_from_thread(self._set_busy, False)

    def _on_data_sync_done(self, result: SyncResult) -> None:
        status = result.status
        sync_cmd = "./.aitask-scripts/aitask_sync.sh --batch"

        if status == STATUS_CONFLICT:
            self.push_screen(
                SyncConflictScreen(result.conflicted_files),
                self._on_conflict_resolved,
            )
            return

        if status == STATUS_TIMEOUT:
            self._capture_failure(
                "aitask-data", "sync", sync_cmd, status,
                result.error_message or "timeout", result.raw_output,
            )
            self.notify("Sync timed out", severity="warning")
            self.action_refresh()
            return

        if status == STATUS_NOT_FOUND:
            self.notify("Sync script not found", severity="error")
            return

        if status == STATUS_ERROR:
            self._capture_failure(
                "aitask-data", "sync", sync_cmd, status,
                result.error_message or "", result.raw_output,
            )
            self.notify(f"Sync error: {result.error_message}", severity="error")
        elif status == STATUS_NO_NETWORK:
            self.notify("Sync: No network", severity="warning")
        elif status == STATUS_NO_REMOTE:
            self.notify("Sync: No remote configured", severity="warning")
        elif status == STATUS_NOTHING:
            self.notify("Already up to date", severity="information")
        elif status == STATUS_AUTOMERGED:
            self.notify("Sync: Auto-merged conflicts", severity="information")
        elif status in (STATUS_PUSHED, STATUS_PULLED, STATUS_SYNCED):
            self.notify(f"Sync: {status.capitalize()}", severity="information")

        self.action_refresh()

    def _on_conflict_resolved(self, resolve: bool) -> None:
        if resolve:
            self._run_interactive_sync_shared()
        self.action_refresh()

    @work(exclusive=True, group="syncer-action")
    async def _run_interactive_sync_shared(self) -> None:
        run_interactive_sync(
            self.app,
            on_done=lambda: self.call_from_thread(self.action_refresh),
        )

    # ---------------------------------------------------- main pull / push

    def _main_worktree(self) -> str | None:
        ref = self._find_ref("main")
        return ref.get("worktree") if ref else None

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
    def _main_pull_worker(self) -> None:
        try:
            cwd = self._main_worktree()
            if not cwd:
                self.call_from_thread(
                    self.notify, "main worktree not available", severity="error"
                )
                return

            rc, head, _ = self._git(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
            head_name = head.strip() if rc == 0 else "?"
            if head_name != "main":
                self.call_from_thread(
                    self.notify,
                    f"Switch to main to pull (currently on {head_name}).",
                    severity="warning",
                )
                return

            rc, status_out, _ = self._git(["status", "--porcelain"], cwd)
            if rc == 0 and status_out.strip():
                self.call_from_thread(
                    self.notify,
                    "Working tree dirty — stash or commit before pulling.",
                    severity="warning",
                )
                return

            rc, out, err = self._git(["pull", "--ff-only"], cwd)
            cmd = "git -C <main> pull --ff-only"
            if rc != 0:
                tail = "\n".join((err or out).splitlines()[-FAILURE_TAIL_LINES:])
                self.call_from_thread(
                    self._fail, "main", "pull", cmd, "ERROR", tail, out + err,
                )
                return
            self.call_from_thread(self.notify, "main: Pulled.", severity="information")
            self.call_from_thread(self.action_refresh)
        finally:
            self.call_from_thread(self._set_busy, False)

    @work(thread=True, exclusive=True, group="syncer-action")
    def _main_push_worker(self) -> None:
        try:
            cwd = self._main_worktree()
            if not cwd:
                self.call_from_thread(
                    self.notify, "main worktree not available", severity="error"
                )
                return

            rc, out, err = self._git(["push", "origin", "main:main"], cwd)
            cmd = "git -C <main> push origin main:main"
            if rc != 0:
                tail = "\n".join((err or out).splitlines()[-FAILURE_TAIL_LINES:])
                self.call_from_thread(
                    self._fail, "main", "push", cmd, "ERROR", tail, out + err,
                )
                return
            self.call_from_thread(self.notify, "main: Pushed.", severity="information")
            self.call_from_thread(self.action_refresh)
        finally:
            self.call_from_thread(self._set_busy, False)

    # ---------------------------------------------------- failure escape hatch

    def _capture_failure(
        self,
        ref_name: str,
        action: str,
        command: str,
        status: str,
        stderr_tail: str,
        raw_output: str,
    ) -> None:
        self._last_failure = SyncFailureContext(
            ref_name=ref_name,
            action=action,
            command=command,
            status=status,
            stderr_tail=stderr_tail,
            raw_output=raw_output,
        )

    def _fail(
        self,
        ref_name: str,
        action: str,
        command: str,
        status: str,
        stderr_tail: str,
        raw_output: str,
    ) -> None:
        self._capture_failure(ref_name, action, command, status, stderr_tail, raw_output)
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
        project_root = Path(".")
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
            default_window_name=f"agent-syncfix-{ctx.ref_name}",
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
            self.action_refresh()

        self.push_screen(screen, on_launch)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ait syncer",
        description="TUI for tracking remote desync state of main and aitask-data refs.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=REFRESH_TICK_DEFAULT,
        help=f"Polling interval in seconds (default: {REFRESH_TICK_DEFAULT}).",
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
