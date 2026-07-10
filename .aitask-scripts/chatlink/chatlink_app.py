"""Minimal chatlink TUI (t1120_6) — read-only gateway status view.

The ONLY chatlink module that may import Textual (the headless daemon's
no-Textual contract is guard-tested). Launched by ``aitask_chatlink.sh``
when ``--headless`` is absent; registered in ``lib/tui_registry.py`` as
``chatlink``.

Read-only by design: it observes the persisted ``SessionsStore`` records
and the audit-log tail on a polling interval. It never commands the daemon
and never touches tmux — daemon control stays with
``ait chatlink --headless`` (typically under a process manager).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Repo lib path — pulls in TuiSwitcherMixin alongside the other TUIs.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from tui_switcher import TuiSwitcherMixin  # noqa: E402
from shortcuts_mixin import ShortcutsMixin  # noqa: E402

from textual.app import App, ComposeResult  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.containers import Vertical  # noqa: E402
from textual.widgets import DataTable, Footer, Log, Static  # noqa: E402

# Absolute imports: the shortcut-scope sweep loads this file as a top-level
# module (no parent package), so relative imports would break there.
from chatlink.audit import AUDIT_FILENAME  # noqa: E402
from chatlink.sessions_store import SessionsStore  # noqa: E402

REFRESH_INTERVAL_S = 2.0
AUDIT_TAIL_LINES = 50
#: Audit-log mtime younger than this reads as "gateway active".
ACTIVE_WINDOW_S = 30.0


def _tag(user_id: str) -> str:
    return f"{user_id[:8]}…" if len(user_id) > 8 else user_id


def _age(created_at: float, now: float) -> str:
    secs = max(0, int(now - created_at)) if created_at else 0
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m"
    return f"{secs // 3600}h{(secs % 3600) // 60:02d}m"


class ChatlinkApp(TuiSwitcherMixin, ShortcutsMixin, App):
    """Single-screen status view: daemon activity, sessions, audit tail."""

    _shortcuts_scope = "chatlink"

    TITLE = "Chat Link"
    BINDINGS = [
        *TuiSwitcherMixin.SWITCHER_BINDINGS,
        *ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS,
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "refresh", "Refresh", show=True),
    ]

    CSS = """
    #status_line {
        height: 1;
        padding: 0 1;
        background: $surface;
        color: $text;
    }
    #sessions_table {
        height: 1fr;
    }
    #audit_log {
        height: 12;
        border-top: solid $primary;
    }
    """

    def __init__(self, *, sessions_dir: str | Path | None = None,
                 clock=time.time):
        super().__init__()
        self.current_tui_name = "chatlink"
        # No I/O in the constructor (--smoke contract); resolve lazily.
        self._sessions_dir = Path(sessions_dir) if sessions_dir else None
        self._clock = clock
        self._store: SessionsStore | None = None

    def _resolve(self) -> Path:
        if self._sessions_dir is None:
            from chatlink import paths

            self._sessions_dir = paths.sessions_dir()
        return self._sessions_dir

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("chatlink", id="status_line")
            yield DataTable(id="sessions_table", cursor_type="row")
            yield Log(id="audit_log", auto_scroll=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#sessions_table", DataTable)
        table.add_columns("session", "state", "initiator", "age")
        sessions_dir = self._resolve()
        self._store = SessionsStore(sessions_dir)
        self._refresh_view()
        self.set_interval(REFRESH_INTERVAL_S, self._refresh_view)

    def action_refresh(self) -> None:
        self._refresh_view()

    # ------------------------------------------------------------------ #
    # Polling refresh (read-only; all failures degrade to placeholders)
    # ------------------------------------------------------------------ #

    def _refresh_view(self) -> None:
        now = self._clock()
        self.query_one("#status_line", Static).update(
            self._status_text(now))
        self._refresh_table(now)
        self._refresh_audit()

    def _status_text(self, now: float) -> str:
        audit_path = self._resolve() / AUDIT_FILENAME
        try:
            age = now - audit_path.stat().st_mtime
        except OSError:
            return "chatlink — no audit log yet (gateway never started?)"
        state = "active" if age <= ACTIVE_WINDOW_S else "quiet"
        return f"chatlink — gateway {state} (last audit {_age(now - age, now)} ago)"

    def _refresh_table(self, now: float) -> None:
        table = self.query_one("#sessions_table", DataTable)
        try:
            records, corrupt = self._store.list_records()
        except OSError:
            return
        table.clear()
        for rec in sorted(records, key=lambda r: r.created_at, reverse=True):
            table.add_row(
                rec.session_id[:16],
                rec.state,
                _tag(rec.initiator_id),
                _age(rec.created_at, now),
                key=rec.session_id,
            )
        for sid in corrupt:
            table.add_row(sid[:16], "corrupt", "?", "?", key=sid)

    def _refresh_audit(self) -> None:
        log = self.query_one("#audit_log", Log)
        audit_path = self._resolve() / AUDIT_FILENAME
        try:
            lines = audit_path.read_text(encoding="utf-8",
                                         errors="replace").splitlines()
        except OSError:
            return
        tail = lines[-AUDIT_TAIL_LINES:]
        log.clear()
        for line in tail:
            log.write_line(line)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ait chatlink", description="Chatlink gateway status TUI")
    parser.add_argument(
        "--smoke", action="store_true",
        help="Headless smoke test: construct the app and exit 0 without "
             "entering the event loop.")
    args = parser.parse_args(list(argv) if argv is not None else sys.argv[1:])
    if args.smoke:
        # Construct without running the event loop or any runtime I/O.
        app = ChatlinkApp()
        del app
        return 0
    ChatlinkApp().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
