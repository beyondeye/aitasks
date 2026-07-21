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
from chatlink import preflight  # noqa: E402
from chatlink import preflight_render  # noqa: E402
from chatlink import wizard  # noqa: E402
from chatlink.audit import AUDIT_FILENAME  # noqa: E402
from chatlink.sessions_store import SessionsStore  # noqa: E402

REFRESH_INTERVAL_S = 2.0
AUDIT_TAIL_LINES = 50
#: Audit-log mtime younger than this reads as "gateway active".
ACTIVE_WINDOW_S = 30.0
#: Expensive checks are a FIXED panel row set: always rendered (cached /
#: checking / not-yet-checked), never disappearing on a cache miss or a
#: worker failure. Cheap checks render from live results each poll tick.
EXPENSIVE_IDS = ("docker_binary", "docker_image",
                 "explore_relay_agent_command")
_EXPENSIVE_CATEGORY = {
    "docker_binary": preflight.RUNTIME,
    "docker_image": preflight.RUNTIME,
    "explore_relay_agent_command": preflight.OPERATION,
}
_EXPENSIVE_LABELS = {
    "docker_binary": "docker binary",
    "docker_image": f"sandbox image {preflight.DOCKER_IMAGE}",
    "explore_relay_agent_command": "explore-relay agent command",
}
_CATEGORY_ORDER = (preflight.TRANSPORT, preflight.RUNTIME,
                   preflight.OPERATION)


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
        Binding("w", "wizard", "Configure", show=True),
    ]

    CSS = """
    #status_line {
        height: 1;
        padding: 0 1;
        background: $surface;
        color: $text;
    }
    #preflight_panel {
        height: auto;
        padding: 0 1;
        border-bottom: solid $primary;
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
                 clock=time.time, cheap_runner=None, expensive_runner=None,
                 wizard_config_path=None, token_reader=None,
                 token_writer=None, live_runner=None,
                 allowlist_fetch_runner=None):
        super().__init__()
        self.current_tui_name = "chatlink"
        # No I/O in the constructor (--smoke contract); resolve lazily.
        self._sessions_dir = Path(sessions_dir) if sessions_dir else None
        self._clock = clock
        self._store: SessionsStore | None = None
        # Preflight seams (stored callables only — no I/O here). ``None``
        # resolves to the preflight module functions at call time, so
        # module-level monkeypatching also keeps working.
        self._cheap_runner = cheap_runner
        self._expensive_runner = expensive_runner
        # Wizard seams (t1149_3) — stored as-is, resolved by the wizard's
        # ``resolve_seams`` at launch time (no I/O here).
        self._wizard_config_path = wizard_config_path
        self._token_reader = token_reader
        self._token_writer = token_writer
        self._live_runner = live_runner
        self._allowlist_fetch_runner = allowlist_fetch_runner
        # Expensive-check cache: {check_id: (CheckResult, clock timestamp)}.
        # Mutated ONLY on the UI thread (_apply_expensive).
        self._expensive_cache: dict[
            str, tuple[preflight.CheckResult, float]] = {}
        self._expensive_running = False
        self._expensive_error = False

    def _resolve(self) -> Path:
        if self._sessions_dir is None:
            from chatlink import paths

            self._sessions_dir = paths.sessions_dir()
        return self._sessions_dir

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("chatlink", id="status_line")
            yield Static("", id="preflight_panel", markup=False)
            yield DataTable(id="sessions_table", cursor_type="row")
            yield Log(id="audit_log", auto_scroll=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#sessions_table", DataTable)
        table.add_columns("session", "state", "initiator", "age")
        sessions_dir = self._resolve()
        self._store = SessionsStore(sessions_dir)
        # Kick the expensive probes BEFORE the first render so the panel
        # shows "checking" state immediately, not on the next poll tick.
        self._kick_expensive()
        self._refresh_view()
        self.set_interval(REFRESH_INTERVAL_S, self._refresh_view)

    def action_refresh(self) -> None:
        self._kick_expensive()
        self._refresh_view()

    def action_wizard(self) -> None:
        wizard.start_wizard(self, wizard.WizardSeams(
            config_path=self._wizard_config_path,
            token_reader=self._token_reader,
            token_writer=self._token_writer,
            cheap_runner=self._cheap_runner,
            expensive_runner=self._expensive_runner,
            live_runner=self._live_runner,
            allowlist_fetch_runner=self._allowlist_fetch_runner,
        ))

    # ------------------------------------------------------------------ #
    # Polling refresh (read-only; all failures degrade to placeholders)
    # ------------------------------------------------------------------ #

    def _refresh_view(self) -> None:
        now = self._clock()
        self.query_one("#status_line", Static).update(
            self._status_text(now))
        self._refresh_preflight(now)
        self._refresh_table(now)
        self._refresh_audit()

    # ------------------------------------------------------------------ #
    # Preflight panel (t1149_2). Cost boundary: the poll tick runs ONLY
    # the cheap checks (file/YAML/in-memory); the expensive probes (agent
    # dry-run, docker) run on a thread worker, on-demand (mount + `r`),
    # and render from the cache.
    # ------------------------------------------------------------------ #

    def _refresh_preflight(self, now: float | None = None) -> None:
        if now is None:
            now = self._clock()
        runner = self._cheap_runner or preflight.run_cheap_checks
        try:
            cheap = runner()
        except OSError:
            return
        self.query_one("#preflight_panel", Static).update(
            self._render_preflight(cheap.results, now))

    def _render_preflight(self, cheap_results, now: float) -> str:
        """Plain-text checklist, grouped by category bucket. The three
        EXPENSIVE_IDS rows are always present — cached (+age), checking,
        or not-yet-checked — so a cache miss or worker failure never makes
        a check disappear."""
        by_cat: dict[str, list[str]] = {c: [] for c in _CATEGORY_ORDER}
        for res in cheap_results:
            by_cat.setdefault(res.category, []).append(self._format_row(res))
        for check_id in EXPENSIVE_IDS:
            by_cat[_EXPENSIVE_CATEGORY[check_id]].append(
                self._format_expensive_row(check_id, now))
        lines = ["config checks — bug-report intake / explore-relay"]
        for cat in list(_CATEGORY_ORDER) + [
                c for c in by_cat if c not in _CATEGORY_ORDER]:
            rows = by_cat.get(cat)
            if not rows:
                continue
            lines.append(f"[{cat}]")
            lines.extend(f"  {row}" for row in rows)
        if self._expensive_error:
            lines.append("! expensive checks failed — press r to retry")
        return "\n".join(lines)

    @staticmethod
    def _format_row(res: preflight.CheckResult) -> str:
        # Shared with the wizard's summary screen (t1149_3) — the actual
        # formatting lives in the Textual-free preflight_render module.
        return preflight_render.format_row(res)

    def _format_expensive_row(self, check_id: str, now: float) -> str:
        cached = self._expensive_cache.get(check_id)
        if cached is not None:
            res, ts = cached
            line = f"{self._format_row(res)} ({_age(ts, now)} ago)"
            if self._expensive_running:
                line += " (re-checking…)"
            return line
        label = _EXPENSIVE_LABELS[check_id]
        if self._expensive_running:
            return f"… {label}: checking"
        return f"· {label}: not checked yet"

    def _kick_expensive(self) -> None:
        """Start the expensive-probe worker (debounced: no-op while one is
        already in flight). Re-renders immediately so the checking state is
        visible the moment the kick happens."""
        if self._expensive_running:
            return
        self._expensive_running = True
        self._refresh_preflight()
        self.run_worker(self._run_expensive, thread=True)

    def _run_expensive(self) -> None:
        """Worker thread body — pure (no widget access): run the probes,
        post the results back to the UI thread. ``None`` signals failure."""
        runner = self._expensive_runner or preflight.run_expensive_checks
        try:
            results = list(runner())
        except Exception:
            results = None
        self.call_from_thread(self._apply_expensive, results)

    def _apply_expensive(
            self, results: list[preflight.CheckResult] | None) -> None:
        """UI thread — the ONLY cache/flag mutation site. On failure the
        previous cache is kept (a transient probe failure must never erase
        useful cached results)."""
        if results is None:
            self._expensive_error = True
        else:
            now = self._clock()
            for res in results:
                self._expensive_cache[res.id] = (res, now)
            self._expensive_error = False
        self._expensive_running = False
        self._refresh_preflight()

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
