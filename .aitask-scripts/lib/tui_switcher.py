"""tui_switcher - Reusable TUI switcher widget for quick-switching between aitask TUIs in tmux.

Provides a ModalScreen overlay showing all known TUIs with their running status,
plus any other tmux windows (agents, shells) grouped by type, and a mixin that
any Textual App can use to add the switcher with a single keybinding.

When multiple aitasks tmux sessions are detected on the current server, the
overlay grows a top "Session:" row — use Left/Right to select another session;
the list below refreshes to that session's windows. Enter (or any shortcut
key) acts on the SELECTED session; a `switch-client` teleport fires
automatically when the selected session differs from the attached one. When
only one aitasks session exists, the UI is bit-identical to single-session
behavior.

Usage:
    from tui_switcher import TuiSwitcherMixin

    class MyApp(TuiSwitcherMixin, App):
        BINDINGS = [
            *TuiSwitcherMixin.SWITCHER_BINDINGS,
            Binding("q", "quit", "Quit"),
            # ... other bindings
        ]

        def __init__(self):
            super().__init__()
            self.current_tui_name = "board"  # name of this TUI
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from textual.binding import Binding
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView, Static

# Add lib dir to path for agent_launch_utils import
_LIB_DIR = str(Path(__file__).resolve().parent)
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from agent_launch_utils import (  # noqa: E402
    AitasksSession,
    discover_aitasks_sessions,
    get_tmux_windows,
    load_tmux_defaults,
    tmux_session_target,
    tmux_window_target,
)
from stale_entry_modal import RegistryRefresh, StaleEntryModal  # noqa: E402
from tmux_exec import TmuxClient  # noqa: E402
from tui_registry import BRAINSTORM_PREFIX as _BRAINSTORM_PREFIX, TUI_NAMES as _TUI_NAMES, switcher_tuis  # noqa: E402
from keybinding_registry import register_app_bindings, resolve_key  # noqa: E402
from shortcut_labels import display_form, render_label  # noqa: E402

# Single Python gateway for raw tmux spawning (t952). Socket args cached once
# at construction from AITASKS_TMUX_SOCKET (unset today → default socket).
_TMUX = TmuxClient()


def _format_desync_lines(lines_output: str) -> str:
    """Format `desync_state.py snapshot --format lines` output as one line.

    Returns markup like ``main: 1↑/0↓ · aitask-data: 0↑/3↓`` or ``clean``
    when both refs are at zero. Refs with non-ok status are surfaced as
    e.g. ``main: missing_remote``.
    """
    refs: list[tuple[str, str, int, int]] = []  # (name, status, ahead, behind)
    cur_name: str | None = None
    cur_status: str = "ok"
    cur_ahead: int = 0
    cur_behind: int = 0
    for raw in lines_output.splitlines():
        line = raw.strip()
        if not line:
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if key == "REF":
            if cur_name is not None:
                refs.append((cur_name, cur_status, cur_ahead, cur_behind))
            cur_name = val
            cur_status = "ok"
            cur_ahead = 0
            cur_behind = 0
        elif key == "STATUS":
            cur_status = val
        elif key == "AHEAD":
            try:
                cur_ahead = int(val)
            except ValueError:
                cur_ahead = 0
        elif key == "BEHIND":
            try:
                cur_behind = int(val)
            except ValueError:
                cur_behind = 0
    if cur_name is not None:
        refs.append((cur_name, cur_status, cur_ahead, cur_behind))

    if not refs:
        return "[dim]desync: unavailable[/]"

    parts: list[str] = []
    any_drift = False
    for name, status, ahead, behind in refs:
        if status != "ok":
            parts.append(f"{name}: [dim]{status}[/]")
            continue
        if ahead == 0 and behind == 0:
            parts.append(f"[dim]{name}: clean[/]")
        else:
            parts.append(f"{name}: {ahead}↑/{behind}↓")
            any_drift = True
    if not any_drift:
        return "[dim]all refs clean[/]"
    return " · ".join(parts)


def _detect_current_session() -> str | None:
    """Auto-detect the current tmux session name, or None if not inside tmux."""
    if not os.environ.get("TMUX"):
        return None
    try:
        rc, out = _TMUX.run(["display-message", "-p", "#S"])
        if rc == 0 and out.strip():
            return out.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


# Switcher-visible TUIs sourced from the central registry. See tui_registry.py
# for the authoritative list and the non-switcher entries (brainstorm, minimonitor)
# that classify as TUI windows but are not user-launchable from the switcher.
KNOWN_TUIS = switcher_tuis()


def _build_tui_list(project_root: Path | None = None):
    """Build TUI list including dynamic git TUI entry from config.

    ``project_root`` selects which project's ``project_config.yaml`` is read
    for the dynamic ``git_tui`` entry. Defaults to ``Path.cwd()`` for legacy
    callers; the cross-session switcher passes the SELECTED session's
    project_root so the displayed Git tool matches what would actually launch.
    """
    tuis = list(KNOWN_TUIS)
    try:
        defaults = load_tmux_defaults(project_root or Path.cwd())
        git_tui = defaults.get("git_tui", "")
        if git_tui and git_tui != "none":
            tuis.insert(2, ("git", f"Git ({git_tui})", git_tui))
    except Exception:
        pass
    return tuis

# Classification constants shared with tmux_monitor.py via tui_registry.
_AGENT_PREFIXES = ["agent-"]

# Customizable-shortcuts scope for the switcher overlay's quick-jump keys
# (t876). Distinct from the module-level "shared" scope that registers the
# `j` key that *opens* the switcher (see bottom of file). The quick-jumps are
# registered at class body (see TuiSwitcherOverlay.BINDINGS) — the pattern that
# actually wires user overrides into Textual's live key map, mirroring
# brainstorm_dag_display.py. The structural keys (escape/enter/←/→) stay fixed
# literals and are intentionally NOT registered (not user-customizable).
_TUI_SWITCHER_SCOPE = "shared.tui_switcher"

# Default quick-jump keys per switchable TUI. These are the registration
# defaults; the live key (and the hint/list rendering) resolve through
# `resolve_key(_TUI_SWITCHER_SCOPE, "shortcut_<name>", default)` so a rebind is
# reflected without going stale.
_TUI_SHORTCUTS = {
    "board": "b",
    "monitor": "m",
    "codebrowser": "c",
    "settings": "s",
    "stats": "t",
    "syncer": "y",
    "git": "g",
    "applink": "a",
}


def _resolve_tui_shortcut(tui_name: str) -> str | None:
    """Active quick-jump key for ``tui_name`` (override-aware), or None.

    The action id is ``shortcut_<tui_name>`` for every entry in
    ``_TUI_SHORTCUTS``; falls back to the hardcoded default when no override or
    recorded default exists yet.
    """
    default = _TUI_SHORTCUTS.get(tui_name)
    if default is None:
        return None
    return resolve_key(_TUI_SWITCHER_SCOPE, f"shortcut_{tui_name}", default) or default


# Ordered (action_id, label, default_key) for the overlay's bottom hint row.
# Omits applink (the hint historically does not advertise the App Linker key).
_HINT_ITEMS = [
    ("shortcut_board", "board", "b"),
    ("shortcut_monitor", "monitor", "m"),
    ("shortcut_codebrowser", "code", "c"),
    ("shortcut_settings", "settings", "s"),
    ("shortcut_stats", "stats", "t"),
    ("shortcut_syncer", "syncer", "y"),
    ("shortcut_brainstorm", "brainstorm", "r"),
    ("shortcut_git", "git", "g"),
    ("shortcut_explore", "explore", "x"),
    ("shortcut_create", "new task", "n"),
]

_KEY_PAREN_RE = re.compile(r"\(([^)]*)\)")


def _hint_segment(action_id: str, label: str, default_key: str) -> str:
    """Render one bottom-hint segment with its live key highlighted in cyan.

    ``render_label`` inlines the key into the word where possible
    (``board`` + ``b`` -> ``(B)oard``) or prefixes it otherwise
    (``stats`` + ``z`` -> ``(Z) stats``); the regex re-applies the existing
    cyan markup to whichever ``(K)`` group it produced.
    """
    key = resolve_key(_TUI_SWITCHER_SCOPE, action_id, default_key) or default_key
    rendered = render_label(label, key)
    return _KEY_PAREN_RE.sub(r"[bold bright_cyan](\1)[/]", rendered, count=1)


def _discover_brainstorm_sessions(project_root: Path | None = None) -> list[str]:
    """Scan a project's .aitask-crews/crew-brainstorm-*/ for brainstorm sessions.

    ``project_root`` selects which project's ``.aitask-crews/`` is scanned.
    Defaults to ``Path.cwd()`` for legacy callers; the cross-session switcher
    passes the SELECTED session's project_root so the listed brainstorm
    sessions match that session's project — not whichever project the
    attached session's Python process happens to run from.

    Returns list of task numbers with existing sessions.
    """
    crews_dir = (project_root or Path.cwd()) / ".aitask-crews"
    if not crews_dir.is_dir():
        return []
    prefix = "crew-brainstorm-"
    sessions = []
    for entry in sorted(crews_dir.iterdir()):
        if entry.is_dir() and entry.name.startswith(prefix):
            session_file = entry / "br_session.yaml"
            if session_file.is_file():
                sessions.append(entry.name[len(prefix):])
    return sessions


def _classify_window(name: str) -> str:
    """Classify a tmux window name as 'tui', 'agent', or 'other'."""
    if name in _TUI_NAMES:
        return "tui"
    if name.startswith(_BRAINSTORM_PREFIX):
        return "tui"
    for prefix in _AGENT_PREFIXES:
        if name.startswith(prefix):
            return "agent"
    return "other"


class _WrappingListView(ListView):
    """ListView that wraps cursor around when reaching edges."""

    def action_cursor_down(self) -> None:
        old = self.index
        super().action_cursor_down()
        if self.index == old and old is not None:
            # At bottom — wrap to first selectable item
            for i, child in enumerate(self.children):
                if isinstance(child, ListItem) and not child.disabled:
                    self.index = i
                    return

    def action_cursor_up(self) -> None:
        old = self.index
        super().action_cursor_up()
        if self.index == old and old is not None:
            # At top — wrap to last selectable item
            items = list(self.children)
            for i in range(len(items) - 1, -1, -1):
                if isinstance(items[i], ListItem) and not items[i].disabled:
                    self.index = i
                    return


class _GroupHeader(ListItem):
    """Non-selectable group separator in the switcher list."""

    def __init__(self, title: str) -> None:
        super().__init__()
        self._title = title
        self.disabled = True

    def compose(self):
        yield Static(f"[bold dim]\u2500\u2500 {self._title} \u2500\u2500[/]")


class _TuiListItem(ListItem):
    """A list item representing a TUI entry in the switcher."""

    def __init__(self, name: str, label: str, running: bool, is_current: bool) -> None:
        super().__init__()
        self.tui_name = name
        self.tui_label = label
        self.running = running
        self.is_current = is_current

    def compose(self):
        if self.is_current:
            indicator = "[bold cyan]\u25b6[/]"
            style = "bold cyan"
        elif self.running:
            indicator = "[bright_green]\u25cf[/]"
            style = "bright_green"
        else:
            indicator = "[dim]\u25cb[/]"
            style = "dim"
        # Show shortcut hint if this TUI has one (resolved so a rebind shows).
        shortcut = _resolve_tui_shortcut(self.tui_name)
        hint = (
            f" [bold bright_cyan]({display_form(shortcut)})[/]"
            if shortcut and not self.is_current
            else ""
        )
        yield Static(f" {indicator}  [{style}]{self.tui_label}[/]{hint}")


class _WindowListItem(ListItem):
    """A list item representing a non-TUI tmux window."""

    def __init__(self, window_name: str, window_index: str) -> None:
        super().__init__()
        self.window_name = window_name
        self.window_index = window_index

    def compose(self):
        yield Static(f" [bright_green]\u25cf[/]  {self.window_name}")


# Quick-jump bindings, registered under `shared.tui_switcher` so they surface
# in the in-TUI `?` editor and the Settings \u2192 Shortcuts tab and pick up user
# overrides. Only these are customizable; see TuiSwitcherOverlay.BINDINGS.
_QUICK_JUMP_BINDINGS = [
    Binding("a", "shortcut_applink", "App Linker", show=False),
    Binding("b", "shortcut_board", "Board", show=False),
    Binding("m", "shortcut_monitor", "Monitor", show=False),
    Binding("c", "shortcut_codebrowser", "Code Browser", show=False),
    Binding("s", "shortcut_settings", "Settings", show=False),
    Binding("t", "shortcut_stats", "Statistics", show=False),
    Binding("y", "shortcut_syncer", "Syncer", show=False),
    Binding("r", "shortcut_brainstorm", "Brainstorm", show=False),
    Binding("x", "shortcut_explore", "Explore", show=False),
    Binding("g", "shortcut_git", "Git", show=False),
    Binding("n", "shortcut_create", "New Task", show=False),
]

# The overlay closes on the same key that opens it (a toggle). Resolve the
# shared "open switcher" key at import so a rebind of the open key carries over
# to the close key; skip it when it collides with a fixed/quick-jump key
# (escape always closes regardless).
_OVERLAY_OPEN_KEY = resolve_key("shared", "tui_switcher", "j") or "j"
_OVERLAY_RESERVED_KEYS = {
    "escape", "enter", "left", "right",
    *(b.key for b in _QUICK_JUMP_BINDINGS),
}


class TuiSwitcherOverlay(ModalScreen):
    """Modal overlay listing known TUIs with status and quick-switch capability."""

    DEFAULT_CSS = """
    TuiSwitcherOverlay {
        align: center middle;
    }
    #switcher_dialog {
        width: 44;
        height: 100%;
        max-height: 30;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #switcher_title {
        text-align: center;
        text-style: bold;
        padding: 0 0 1 0;
        width: 100%;
    }
    #switcher_session_row {
        text-align: center;
        padding: 0 0 1 0;
        color: $text;
        width: 100%;
    }
    #switcher_desync {
        text-align: center;
        padding: 0 0 1 0;
        color: $text-muted;
        width: 100%;
    }
    #switcher_list {
        height: 1fr;
        min-height: 3;
    }
    #switcher_hint {
        dock: bottom;
        text-align: center;
        padding: 1 0 0 0;
        color: $text-muted;
        width: 100%;
    }
    """

    # Structural keys stay fixed literals; only the quick-jumps are registered
    # (customizable). The class-body register_app_bindings() call is what wires
    # user overrides into Textual's live key map AND records the defaults for
    # the editor — mirroring brainstorm_dag_display.py. The `j`→close toggle
    # tracks the resolved open key (_OVERLAY_OPEN_KEY).
    BINDINGS = [
        Binding("escape", "dismiss_overlay", "Close", show=False),
        Binding("enter", "select_tui", "Switch", show=False),
        Binding("left", "prev_session", "Prev session", show=False, priority=True),
        Binding("right", "next_session", "Next session", show=False, priority=True),
        *(
            [Binding(_OVERLAY_OPEN_KEY, "dismiss_overlay", "Close", show=False)]
            if _OVERLAY_OPEN_KEY not in _OVERLAY_RESERVED_KEYS
            else []
        ),
        *register_app_bindings(_TUI_SWITCHER_SCOPE, _QUICK_JUMP_BINDINGS),
    ]

    def __init__(
        self,
        session: str,
        current_tui: str = "",
        selected_session: str | None = None,
    ) -> None:
        super().__init__()
        # _session is the OPERATING / SELECTED session — what the overlay
        # currently points at. Mutated by Left/Right. All shortcuts,
        # _switch_to, and _launch_git_with_companion read this. Callers can
        # pre-select a non-attached session via ``selected_session`` (e.g.
        # monitor / minimonitor opening the switcher with the focused
        # agent's session already selected — t836).
        self._session = selected_session or session
        # _attached_session is the tmux client's current session — used only
        # by _render_session_row (to mark the attached session with ▶) and
        # _teleport_if_cross (to decide whether switch-client is needed).
        self._attached_session = session
        self._current_tui = current_tui
        self._running_names: set[str] = set()
        # Multi-session state. Populated in on_mount via
        # discover_aitasks_sessions(); remains empty / False when only one
        # aitasks session is running on the server.
        self._all_sessions: list[AitasksSession] = []
        self._multi_mode: bool = False

    def compose(self):
        with Container(id="switcher_dialog"):
            yield Label("TUI Switcher", id="switcher_title")
            yield Label("", id="switcher_session_row")
            yield Label("", id="switcher_desync")
            yield _WrappingListView(id="switcher_list")
            yield Label("", id="switcher_hint")

    def on_mount(self) -> None:
        # include_registered=True surfaces projects from the per-user
        # registry (~/.config/aitasks/projects.yaml) even when no live
        # tmux session exists for them. Selecting one bootstraps its
        # session on-demand (see _ensure_session_live below).
        self._init_multi_state(discover_aitasks_sessions(include_registered=True))
        self._render_hint()
        self._render_session_row()
        self._render_desync_line(self._project_root_for_session(self._session))
        self._populate_list_for(self._session)

    def _project_root_for_session(self, session: str) -> Path:
        """Return the absolute project root associated with ``session``.

        Looks up the session in ``self._all_sessions`` (populated by
        ``discover_aitasks_sessions()``). Falls back to ``Path.cwd()`` when
        the session is unknown (e.g. single-session mode where
        ``_all_sessions`` may be empty, or an exotic session that did not
        match either discovery heuristic). The fallback preserves the
        legacy single-session behavior — calling pane's cwd already equals
        the project root in that case.
        """
        for s in self._all_sessions:
            if s.session == session:
                return s.project_root
        return Path.cwd()

    def _handle_stale_selection(self) -> bool:
        """If the SELECTED session is a STALE registry entry, push the
        StaleEntryModal and return True so the caller short-circuits
        and does NOT proceed with bootstrap/spawn. Returns False when
        the entry is not stale (or not tracked) so the caller proceeds
        normally.
        """
        idx = next(
            (i for i, s in enumerate(self._all_sessions)
             if s.session == self._session),
            None,
        )
        if idx is None:
            return False
        entry = self._all_sessions[idx]
        if not entry.is_stale:
            return False
        self._push_stale_modal(entry.project_name, entry.project_root)
        return True

    def _push_stale_modal(self, name: str, project_root: Path) -> None:
        self.app.push_screen(StaleEntryModal(name, project_root))

    def on_registry_refresh(self, event: RegistryRefresh) -> None:
        """Re-run session discovery and rebuild the Session: row after
        the StaleEntryModal mutates the registry (prune or repoint).
        """
        event.stop()
        self._all_sessions = discover_aitasks_sessions(include_registered=True)
        # Selected session may have been removed (prune); fall back to
        # the attached session so subsequent actions are well-defined.
        if not any(s.session == self._session for s in self._all_sessions):
            self._session = self._attached_session
        self._render_session_row()
        self._render_desync_line(self._project_root_for_session(self._session))
        self._populate_list_for(self._session)

    def _ensure_session_live(self) -> bool:
        """Bootstrap the selected session if it is registered-but-inactive.

        Called before any action that would spawn a window in
        ``self._session``. Looks up the entry in ``self._all_sessions``;
        when ``is_live=False``, shells out to ``tmux_bootstrap.sh`` to
        create the session, then flips the cached entry's ``is_live``
        flag. No-op for live entries and for sessions not tracked in
        ``self._all_sessions`` (legacy single-session fallback).

        Returns True on success or no-op; False if the bootstrap helper
        failed (a user-facing notification is emitted in that case).
        """
        idx = next(
            (i for i, s in enumerate(self._all_sessions)
             if s.session == self._session),
            None,
        )
        if idx is None or self._all_sessions[idx].is_live:
            return True
        entry = self._all_sessions[idx]
        script = str(Path(__file__).resolve().parent / "tmux_bootstrap.sh")
        try:
            result = subprocess.run(
                ["bash", script, str(entry.project_root)],
                capture_output=True, text=True, timeout=15,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            self.app.notify(
                f"Failed to bootstrap session for {entry.project_name}: {exc}",
                severity="error",
            )
            return False
        if result.returncode != 0:
            stderr_text = (result.stderr or "").strip()
            if "BOOTSTRAP_FAILED:stale_path" in stderr_text:
                # Race: entry was OK at switcher mount but went STALE
                # before bootstrap. Push the same modal as the up-front
                # guard so the user can prune/repoint inline.
                self._push_stale_modal(
                    entry.project_name, entry.project_root,
                )
                return False
            err = stderr_text.splitlines()[-1:] or ["unknown error"]
            self.app.notify(
                f"Failed to bootstrap session for {entry.project_name}: {err[0]}",
                severity="error",
            )
            return False
        # Flip the cached entry to live so _teleport_if_cross and any
        # follow-up actions in this overlay session no longer re-trigger
        # the bootstrap. Dataclass is frozen so we replace the tuple slot.
        self._all_sessions[idx] = AitasksSession(
            session=entry.session,
            project_root=entry.project_root,
            project_name=entry.project_name,
            is_live=True,
        )
        return True

    def _spawn_in_session(
        self,
        window_name: str,
        cmd: str,
        *,
        capture_pane_id: bool = False,
    ):
        """Run ``tmux new-window`` in the SELECTED session with the right cwd.

        Centralizes the ``-c <project_root>`` flag so cross-session spawns
        land in the SELECTED session's project directory (not the attached
        session's cwd). When ``capture_pane_id`` is True, runs synchronously
        through the gateway and returns the ``(returncode, stdout)`` tuple so
        callers can read the pane id; otherwise returns the async ``Popen``
        for fire-and-forget use.
        """
        project_root = self._project_root_for_session(self._session)
        argv = ["new-window", "-t",
                tmux_window_target(self._session, ""),
                "-c", str(project_root),
                "-n", window_name]
        if capture_pane_id:
            argv += ["-P", "-F", "#{pane_id}", cmd]
            return _TMUX.run(argv)
        argv += [cmd]
        return _TMUX.spawn(
            argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    def _init_multi_state(self, sessions: list[AitasksSession]) -> None:
        """Decide `_multi_mode` from the discovered sessions.

        True iff at least two aitasks sessions exist (live OR registered
        but inactive) AND the attached session is one of them. If the
        overlay was opened from a non-aitasks session (no live entry
        matches the attached session), fall back to single-session view
        — even if the registry has entries, since the user is not
        currently working in an aitasks project context.
        """
        self._all_sessions = sessions
        self._multi_mode = (
            len(sessions) >= 2
            and any(s.session == self._attached_session for s in sessions)
        )
        # If the caller pre-selected a session that does not appear in the
        # discovered list (e.g. the agent's session died between focus and
        # overlay push), fall back to the attached session so the
        # session-row markers and _cycle_session indexing stay consistent.
        if sessions and not any(s.session == self._session for s in sessions):
            self._session = self._attached_session

    def _render_hint(self) -> None:
        hint = self.query_one("#switcher_hint", Label)
        text = "  ".join(
            _hint_segment(action_id, label, default_key)
            for action_id, label, default_key in _HINT_ITEMS
        ) + "\n"
        close = f"[bold bright_cyan]{display_form(_OVERLAY_OPEN_KEY)}/Esc[/] close"
        if self._multi_mode:
            text += (
                "[bold bright_cyan]Enter[/] switch  "
                "[bold bright_cyan]←/→[/] session  "
                + close
            )
        else:
            text += "[bold bright_cyan]Enter[/] switch  " + close
        hint.update(text)

    def _render_session_row(self) -> None:
        """Render the top session row; hidden in single-session mode.

        `display = False` so the row contributes zero rows (its
        `padding: 0 0 1 0` would otherwise consume one row even when the
        text is empty, stealing space the docked footer needs in small
        panes — see t789).
        """
        row = self.query_one("#switcher_session_row", Label)
        if not self._multi_mode:
            row.update("")
            row.display = False
            return
        row.display = True
        parts = []
        for s in self._all_sessions:
            name = s.session
            attached = name == self._attached_session
            selected = name == self._session
            prefix = "▶ " if attached else "  "
            suffix = " (stale)" if s.is_stale else ""
            label = f"{prefix}{name}{suffix}"
            if s.is_stale:
                # STALE rows render dimmed regardless of selection so
                # the status remains unambiguous; selection still shows
                # via reverse on the dimmed text.
                if selected:
                    parts.append(f"[reverse][dim]{label}[/][/]")
                else:
                    parts.append(f"[dim]{label}[/]")
            elif selected:
                parts.append(f"[reverse]{label}[/]")
            else:
                parts.append(f"[dim]{label}[/]")
        row.update("Session: " + "  ".join(parts))

    def _render_desync_line(self, project_root: Path) -> None:
        """Render a compact desync summary line for the selected session's project.

        Invokes ``desync_state.py snapshot --format lines`` as a subprocess
        with ``cwd=project_root`` so the result reflects the SELECTED
        session's project (not whichever project owns this Python file).
        Result is cached on the class for ~30 seconds keyed on project_root
        to avoid re-invoking on every Left/Right cycle.
        """
        line_widgets = self.query("#switcher_desync")
        if not line_widgets:
            return
        line_widget = line_widgets.first(Label)
        text = self._compute_desync_summary(project_root)
        line_widget.update(text)

    _DESYNC_TTL_SECONDS = 30
    _desync_cache: dict[str, tuple[float, str]] = {}

    @classmethod
    def _compute_desync_summary(cls, project_root: Path) -> str:
        import time
        key = str(project_root)
        now = time.monotonic()
        cached = cls._desync_cache.get(key)
        if cached and (now - cached[0]) < cls._DESYNC_TTL_SECONDS:
            return cached[1]
        text = cls._fetch_desync_summary(project_root)
        cls._desync_cache[key] = (now, text)
        return text

    @staticmethod
    def _fetch_desync_summary(project_root: Path) -> str:
        helper = (
            Path(__file__).resolve().parent / "desync_state.py"
        )
        try:
            proc = subprocess.run(
                [sys.executable, str(helper), "snapshot", "--format", "lines"],
                cwd=str(project_root),
                capture_output=True, text=True, timeout=3,
            )
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            return "[dim]desync: unavailable[/]"
        if proc.returncode != 0:
            return "[dim]desync: unavailable[/]"
        return _format_desync_lines(proc.stdout)

    def _populate_list_for(self, session: str) -> None:
        """Fill the ListView with TUIs and windows from the given session.

        Called on_mount and on every Left/Right session cycle. Clears the
        ListView first so re-renders are clean. The "current TUI" disabled
        marker only applies when `session == self._attached_session`
        (otherwise the user is browsing a different session and no item
        in that session is "the one I'm attached to right now").
        """
        running_windows = get_tmux_windows(session)
        self._running_names = {name for _, name in running_windows}
        is_attached_session = session == self._attached_session

        list_view = self.query_one("#switcher_list", _WrappingListView)
        list_view.clear()
        item_idx = 0
        first_selectable_idx = None

        # --- TUI Group ---
        list_view.append(_GroupHeader("TUIs"))
        item_idx += 1

        session_project_root = self._project_root_for_session(session)
        for name, label, _cmd in _build_tui_list(session_project_root):
            is_current = is_attached_session and name == self._current_tui
            running = name in self._running_names
            item = _TuiListItem(name, label, running, is_current)
            if is_current:
                item.disabled = True
            elif first_selectable_idx is None:
                first_selectable_idx = item_idx
            list_view.append(item)
            item_idx += 1

        # --- Dynamic brainstorm session entries ---
        # Scan the SELECTED session's project (session_project_root, set
        # above) so on-disk brainstorm sessions follow Left/Right cycling
        # instead of always reflecting the attached session's project (t814).
        brainstorm_sessions = _discover_brainstorm_sessions(session_project_root)
        all_brainstorm_nums = set(brainstorm_sessions)
        for name in self._running_names:
            if name.startswith(_BRAINSTORM_PREFIX):
                all_brainstorm_nums.add(name[len(_BRAINSTORM_PREFIX):])
        for task_num in sorted(all_brainstorm_nums):
            win_name = f"{_BRAINSTORM_PREFIX}{task_num}"
            label = f"Brainstorm (t{task_num})"
            running = win_name in self._running_names
            is_current = is_attached_session and win_name == self._current_tui
            item = _TuiListItem(win_name, label, running, is_current)
            if is_current:
                item.disabled = True
            elif first_selectable_idx is None:
                first_selectable_idx = item_idx
            list_view.append(item)
            item_idx += 1

        # --- Classify non-TUI windows ---
        agents = []
        others = []
        for win_idx, win_name in running_windows:
            if win_name in _TUI_NAMES:
                continue
            cat = _classify_window(win_name)
            if cat == "agent":
                agents.append((win_idx, win_name))
            else:
                others.append((win_idx, win_name))

        # --- Agent Group ---
        if agents:
            list_view.append(_GroupHeader("Code Agents"))
            item_idx += 1
            for win_idx, win_name in agents:
                if first_selectable_idx is None:
                    first_selectable_idx = item_idx
                list_view.append(_WindowListItem(win_name, win_idx))
                item_idx += 1

        # --- Other Group ---
        if others:
            list_view.append(_GroupHeader("Other"))
            item_idx += 1
            for win_idx, win_name in others:
                if first_selectable_idx is None:
                    first_selectable_idx = item_idx
                list_view.append(_WindowListItem(win_name, win_idx))
                item_idx += 1

        if first_selectable_idx is not None:
            list_view.index = first_selectable_idx

    def action_dismiss_overlay(self) -> None:
        self.dismiss(None)

    def action_prev_session(self) -> None:
        self._cycle_session(-1)

    def action_next_session(self) -> None:
        self._cycle_session(+1)

    def _cycle_session(self, step: int) -> None:
        # Priority-binding guard (CLAUDE.md "Priority bindings + App.query_one"):
        # scope the guard to this screen via self.screen.query_one and
        # SkipAction on miss so underlying screens don't have their Left/Right
        # consumed. Same pattern as board's action_focus_minimap.
        from textual.actions import SkipAction
        try:
            self.screen.query_one("#switcher_list", _WrappingListView)
        except Exception:
            raise SkipAction()
        if not self._multi_mode or len(self._all_sessions) < 2:
            raise SkipAction()
        names = [s.session for s in self._all_sessions]
        try:
            idx = names.index(self._session)
        except ValueError:
            idx = 0
        self._session = names[(idx + step) % len(names)]
        self._render_session_row()
        self._render_desync_line(self._project_root_for_session(self._session))
        self._populate_list_for(self._session)

    def action_select_tui(self) -> None:
        list_view = self.query_one("#switcher_list", _WrappingListView)
        if list_view.highlighted_child is None:
            return
        item = list_view.highlighted_child
        if isinstance(item, _TuiListItem):
            if item.is_current:
                return
            self._switch_to(item.tui_name, item.running)
        elif isinstance(item, _WindowListItem):
            self._switch_to(item.window_name, True, item.window_index)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, _TuiListItem):
            if item.is_current:
                return
            self._switch_to(item.tui_name, item.running)
        elif isinstance(item, _WindowListItem):
            self._switch_to(item.window_name, True, item.window_index)

    def _shortcut_switch(self, target_name: str) -> None:
        """Switch directly to a specific TUI by name, launching if not running.

        Shortcuts act on the SELECTED (operating) session — `self._session`
        is mutated by Left/Right. The `is-current` no-op guard only applies
        when the selected session IS the attached session; otherwise the
        user is targeting a TUI in a different session and we should always
        route through `_switch_to`.
        """
        if (self._session == self._attached_session
                and target_name == self._current_tui):
            return
        self._switch_to(target_name, target_name in self._running_names)

    def action_shortcut_applink(self) -> None:
        self._shortcut_switch("applink")

    def action_shortcut_board(self) -> None:
        self._shortcut_switch("board")

    def action_shortcut_monitor(self) -> None:
        self._shortcut_switch("monitor")

    def action_shortcut_codebrowser(self) -> None:
        self._shortcut_switch("codebrowser")

    def action_shortcut_settings(self) -> None:
        self._shortcut_switch("settings")

    def action_shortcut_stats(self) -> None:
        self._shortcut_switch("stats")

    def action_shortcut_syncer(self) -> None:
        self._shortcut_switch("syncer")

    def action_shortcut_brainstorm(self) -> None:
        """Switch to first running brainstorm window in the SELECTED session."""
        for name in sorted(self._running_names):
            if name.startswith(_BRAINSTORM_PREFIX):
                # No-op only when already on this brainstorm window in the
                # attached session; otherwise teleport via _switch_to.
                if (self._session == self._attached_session
                        and name == self._current_tui):
                    return
                self._switch_to(name, True)
                return
        self.app.notify("No brainstorm session running", severity="warning")

    def action_shortcut_git(self) -> None:
        """Switch to git TUI if configured, no-op otherwise."""
        if not any(name == "git" for name, _, _ in _build_tui_list()):
            return
        self._shortcut_switch("git")

    def action_shortcut_explore(self) -> None:
        """Launch a new explore agent session (always new window) in the SELECTED session."""
        if self._handle_stale_selection():
            return
        if not self._ensure_session_live():
            return
        n = 1
        while f"agent-explore-{n}" in self._running_names:
            n += 1
        window_name = f"agent-explore-{n}"
        project_root = self._project_root_for_session(self._session)
        try:
            self._spawn_in_session(window_name, "ait codeagent invoke explore")
            from agent_launch_utils import maybe_spawn_minimonitor
            maybe_spawn_minimonitor(
                self._session, window_name, project_root=project_root,
            )
            self._teleport_if_cross()
        except (FileNotFoundError, OSError):
            self.app.notify("Failed to launch explore", severity="error")
            return
        self.dismiss(window_name)

    def action_shortcut_create(self) -> None:
        """Launch ait create in a new tmux window in the SELECTED session."""
        if self._handle_stale_selection():
            return
        if not self._ensure_session_live():
            return
        project_root = self._project_root_for_session(self._session)
        try:
            proc = self._spawn_in_session("create-task", "ait create")
            proc.wait()
            from agent_launch_utils import maybe_spawn_minimonitor
            maybe_spawn_minimonitor(
                self._session, "create-task", project_root=project_root,
            )
            self._teleport_if_cross()
        except (FileNotFoundError, OSError):
            self.app.notify("Failed to launch create", severity="error")
            return
        self.dismiss("create-task")

    def _switch_to(self, name: str, running: bool, window_index: str | None = None) -> None:
        # If the selected entry is a STALE registry row (t826_10), push
        # the StaleEntryModal up-front so the user can prune/repoint
        # without burning a failing bootstrap subprocess first.
        if self._handle_stale_selection():
            return
        # Bootstrap the selected session if it is registered-but-inactive
        # (t826_2). No-op for live sessions.
        if not self._ensure_session_live():
            return
        try:
            if running:
                target = tmux_window_target(
                    self._session, window_index if window_index else name
                )
                _TMUX.spawn(
                    ["select-window", "-t", target],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            elif name == "git":
                self._launch_git_with_companion()
            else:
                project_root = self._project_root_for_session(self._session)
                cmd = self._get_launch_command(name, project_root)
                self._spawn_in_session(name, cmd)
            # Cross-session: teleport the attached client to the selected
            # session. Per agent_launch_utils.switch_to_pane_anywhere's
            # precedent, the target-window operation runs first (setting the
            # selected session's active window or creating it), then the
            # switch-client call lands the client there.
            self._teleport_if_cross()
        except (FileNotFoundError, OSError):
            self.app.notify(f"Failed to switch to {name}", severity="error")
            return
        self.dismiss(name)

    def _teleport_if_cross(self) -> None:
        """Issue `tmux switch-client` when the selected session differs from attached."""
        if self._session == self._attached_session:
            return
        try:
            _TMUX.spawn(
                ["switch-client", "-t", tmux_session_target(self._session)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except (FileNotFoundError, OSError):
            # Best-effort — if the client detached between selection and
            # this call, switch-client fails silently; the overlay still
            # dismisses cleanly.
            pass

    def _launch_git_with_companion(self) -> None:
        """Launch the git TUI in a new window with a companion minimonitor.

        Wires a pane-scoped `pane-died` hook on the git pane so that when the
        git tool exits, the companion is despawned only if no other sibling
        pane (user-added shell, codeagent sharing the companion, etc.) is
        still using the window.
        """
        project_root = self._project_root_for_session(self._session)
        cmd = self._get_launch_command("git", project_root)
        rc, stdout = self._spawn_in_session("git", cmd, capture_pane_id=True)
        if rc != 0:
            self.app.notify("Failed to launch git TUI", severity="error")
            return
        primary_pane = stdout.strip()
        if not primary_pane:
            return

        from agent_launch_utils import maybe_spawn_minimonitor
        companion_pane = maybe_spawn_minimonitor(
            self._session, "git", force_companion=True,
            project_root=project_root,
        )

        if companion_pane:
            # Pane-scoped verbs: -t is a %pane id, passed through untouched
            # (no session_target wrapping). Routed via the gateway for socket
            # consistency.
            _TMUX.spawn(
                ["set-option", "-p", "-t", primary_pane,
                 "remain-on-exit", "on"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            script_path = str(
                Path(__file__).resolve().parent.parent / "aitask_companion_cleanup.sh"
            )
            hook_cmd = f"run-shell '{script_path} {primary_pane} {companion_pane}'"
            _TMUX.spawn(
                ["set-hook", "-p", "-t", primary_pane,
                 "pane-died", hook_cmd],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )

        # Cross-session teleport is handled by `_switch_to` after this
        # helper returns — do not issue an additional `switch-client` here.

    @staticmethod
    def _get_launch_command(name: str, project_root: Path | None = None) -> str:
        for tui_name, _, cmd in _build_tui_list(project_root):
            if tui_name == name:
                return cmd
        if name.startswith(_BRAINSTORM_PREFIX):
            task_num = name[len(_BRAINSTORM_PREFIX):]
            return f"ait brainstorm {task_num}"
        return f"ait {name}"


class TuiSwitcherMixin:
    """Mixin for Textual Apps to add TUI switcher support.

    Usage:
        class MyApp(TuiSwitcherMixin, App):
            BINDINGS = [
                *TuiSwitcherMixin.SWITCHER_BINDINGS,
                ...
            ]
            def __init__(self):
                super().__init__()
                self.current_tui_name = "board"
    """

    SWITCHER_BINDINGS = [
        Binding("j", "tui_switcher", "TUI switcher", show=False),
    ]

    def _switcher_selected_session(self) -> str | None:
        """Return a tmux session name to pre-select in the switcher overlay.

        Override in subclasses (e.g. monitor / minimonitor) to open the
        switcher with the focused agent's session already selected.
        Default ``None`` means use the attached session — the original
        single-session behavior.
        """
        return None

    def action_tui_switcher(self) -> None:
        if not os.environ.get("TMUX"):
            self.notify("TUI switcher requires tmux", severity="warning")
            return
        # Prefer auto-detecting current tmux session, fall back to config
        session = _detect_current_session()
        if session is None:
            defaults = load_tmux_defaults(Path.cwd())
            session = defaults.get("default_session", "aitasks")
        current = getattr(self, "current_tui_name", "")
        selected = self._switcher_selected_session()
        self.push_screen(TuiSwitcherOverlay(
            session=session, current_tui=current, selected_session=selected,
        ))


# Register the switcher binding under a synthetic "shared" scope so the
# t848_4 shortcuts editor can surface it from every TUI (the `j` key is
# bound in every host App via the mixin, but the editor enumerates by
# scope, not by host).
register_app_bindings("shared", TuiSwitcherMixin.SWITCHER_BINDINGS)
