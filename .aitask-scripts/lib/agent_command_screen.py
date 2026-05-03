"""agent_command_screen - Shared modal dialog for displaying and launching code agent commands.

Provides a reusable Textual ModalScreen with two tabs:
- Direct: Copy command/prompt, run in new terminal
- tmux: Launch into tmux session/window/pane (only shown when tmux is installed)

Usage:
    from agent_command_screen import AgentCommandScreen
    from agent_launch_utils import TmuxLaunchConfig

    def callback(result):
        if result is None:
            pass  # cancelled
        elif result == "run":
            pass  # direct run in terminal
        elif isinstance(result, TmuxLaunchConfig):
            launch_in_tmux(command, result)

    screen = AgentCommandScreen(
        title="Pick Task t42",
        full_command="claude --model opus '/aitask-pick 42'",
        prompt_str="/aitask-pick 42",
        default_window_name="agent-pick-42",
    )
    app.push_screen(screen, callback)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from textual import on, work
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static, TabbedContent, TabPane
from textual.widgets._select import SelectOverlay

# Add lib dir to path for agent_launch_utils import
_LIB_DIR = str(Path(__file__).resolve().parent)
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from agent_launch_utils import (  # noqa: E402
    TmuxLaunchConfig,
    get_tmux_sessions,
    get_tmux_windows,
    is_tmux_available,
    load_tmux_defaults,
    resolve_dry_run_command,
)


_NEW_SESSION_SENTINEL = "__new_session__"
_NEW_WINDOW_SENTINEL = "__new_window__"


def pick_initial_session(
    sessions: list[str],
    default_from_config: str | None,
    last_for_project: str | None,
) -> str:
    """Resolve the initial session selection for the tmux tab.

    Priority:
    1. Last session chosen in THIS project (per-project memory).
    2. project_config.yaml's tmux.default_session, if live.
    3. First live session (fallback for legacy/unconfigured projects).
    4. _NEW_SESSION_SENTINEL when no sessions exist.
    """
    if last_for_project and last_for_project in sessions:
        return last_for_project
    if default_from_config and default_from_config in sessions:
        return default_from_config
    if sessions:
        return sessions[0]
    return _NEW_SESSION_SENTINEL


class AgentCommandScreen(ModalScreen):
    """Dialog showing an agent command for copying or running.

    Supports two modes via tabs:
    - Direct: copy command/prompt, run in new terminal
    - tmux: launch into a tmux session/window/pane
    """

    DEFAULT_CSS = """
    #agent_cmd_dialog {
        width: 80%;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #agent_cmd_title {
        text-align: center;
        padding: 0 0 1 0;
        text-style: bold;
    }
    #agent_cmd_input {
        margin: 0 0 1 0;
    }
    #agent_row {
        height: 3;
        width: 100%;
        align: left middle;
        margin: 0 0 1 0;
    }
    #agent_row Label {
        height: 3;
        padding: 0 1;
        content-align: left middle;
    }
    #agent_row Button {
        margin: 0 1;
        width: auto;
        min-width: 10;
    }
    #agent_cmd_tabs {
        height: auto;
        max-height: 20;
    }
    .agent-cmd-copy-row {
        height: 3;
        width: 100%;
        align: left middle;
    }
    .agent-cmd-copy-row Button {
        width: auto;
        min-width: 14;
    }
    #agent_cmd_prompt_label {
        padding: 0 1;
        width: 1fr;
    }
    .agent-cmd-buttons {
        height: 3;
        width: 100%;
        align: center middle;
        margin: 1 0 0 0;
    }
    .agent-cmd-buttons Button {
        margin: 0 1;
    }
    .tmux-field-row {
        height: 3;
        width: 100%;
        align: left middle;
        margin: 0 0 1 0;
    }
    .tmux-field-row Label {
        width: 12;
        padding: 0 1;
    }
    .tmux-field-row Select {
        width: 1fr;
    }
    .tmux-field-row Input {
        width: 1fr;
    }
    #tmux_new_session_row, #tmux_new_window_row {
        height: 3;
        width: 100%;
        align: left middle;
        margin: 0 0 1 0;
    }
    #tmux_new_session_row Label, #tmux_new_window_row Label {
        width: 12;
        padding: 0 1;
    }
    #tmux_new_session_input, #tmux_new_window_input {
        width: 1fr;
    }
    #tmux_split_row {
        height: 3;
        width: 100%;
        align: left middle;
        margin: 0 0 1 0;
    }
    #tmux_split_row Label {
        width: 12;
        padding: 0 1;
    }
    #tmux_split_row Button {
        width: auto;
        min-width: 20;
    }
    .hidden {
        display: none;
    }
    """

    AUTO_FOCUS = ""
    ESCAPE_TO_MINIMIZE = False

    BINDINGS = [
        Binding("c", "copy_command", "Copy Command", show=False),
        Binding("C", "copy_command", "Copy Command", show=False),
        Binding("p", "copy_prompt", "Copy Prompt", show=False),
        Binding("P", "copy_prompt", "Copy Prompt", show=False),
        Binding("r", "run", "Run", show=False),
        Binding("R", "run", "Run", show=False),
        Binding("d", "tab_direct", "Direct tab", show=False),
        Binding("D", "tab_direct", "Direct tab", show=False),
    ]

    # Per-project remembered selections, keyed by resolved project_root.
    # Class-level (process lifetime) but partitioned per project to prevent
    # cross-project leakage (see CLAUDE.md: one tmux session per project).
    _last_session_by_project: dict[Path, str] = {}
    _last_window_by_project: dict[Path, str] = {}
    # Per-operation remembered agent override (process lifetime).
    # Only populated when the user picks something other than the default,
    # so the (U)se previous button never recalls the default itself.
    _previous_agent_override: dict[str, str] = {}

    def __init__(
        self,
        title: str,
        full_command: str,
        prompt_str: str,
        default_window_name: str = "",
        project_root: Path | None = None,
        operation: str | None = None,
        operation_args: list[str] | None = None,
        default_agent_string: str | None = None,
        default_tmux_window: str | None = None,
    ):
        super().__init__()
        self.title_text = title
        self.full_command = full_command
        self.prompt_str = prompt_str
        self.default_window_name = default_window_name
        self._project_root = project_root or Path.cwd()
        self._project_key = self._project_root.resolve()
        self.operation = operation
        self.operation_args: list[str] = list(operation_args or [])
        self.current_agent_string: str | None = default_agent_string
        self._default_agent_string: str | None = default_agent_string
        self._default_tmux_window: str | None = default_tmux_window
        self._tmux_available = is_tmux_available()
        self._tmux_defaults = load_tmux_defaults(self._project_root)
        self._split_horizontal = self._tmux_defaults["default_split"] == "horizontal"
        self._selected_session: str | None = None
        self._selected_window: str | None = None

    def compose(self):
        with Container(id="agent_cmd_dialog"):
            yield Label(self.title_text, id="agent_cmd_title")
            if self.operation:
                with Horizontal(id="agent_row"):
                    yield Label(
                        f"Agent: {self.current_agent_string or '(unknown)'}",
                        id="agent_row_label",
                    )
                    yield Button(
                        "(A)gent", variant="primary", id="btn_change_agent",
                    )
                    yield Button(
                        "",
                        variant="default",
                        id="btn_use_last_agent",
                        classes="hidden",
                    )
            yield Label("Command:")
            yield Input(
                value=self.full_command,
                id="agent_cmd_input",
            )

            if self._tmux_available:
                with TabbedContent(id="agent_cmd_tabs"):
                    with TabPane("(D)irect", id="tab_direct"):
                        yield self._compose_direct_tab()
                    with TabPane("(T)mux", id="tab_tmux"):
                        yield self._compose_tmux_tab()
            else:
                yield self._compose_direct_tab()

    def _compose_direct_tab(self) -> Container:
        container = Container(id="direct_content")
        return container

    def _compose_tmux_tab(self) -> Container:
        container = Container(id="tmux_content")
        return container

    def handle_escape(self) -> None:
        """Custom escape: unfocus Input/Select if focused, otherwise dismiss."""
        focused = self.focused
        if isinstance(focused, (Input, Select)):
            self.set_focus(None)
        else:
            self.dismiss(None)

    def on_mount(self) -> None:
        # Populate direct tab
        direct = self.query_one("#direct_content")
        direct.mount(Label("Prompt only:"))
        row = Horizontal(classes="agent-cmd-copy-row")
        direct.mount(row)
        row.mount(Label(self.prompt_str, id="agent_cmd_prompt_label"))
        row.mount(Button("Copy (P)rompt", variant="primary", id="btn_copy_prompt"))
        buttons = Horizontal(classes="agent-cmd-buttons")
        direct.mount(buttons)
        buttons.mount(Button("(C)opy cmd", variant="primary", id="btn_copy_command"))
        buttons.mount(Button("(R)un in terminal", variant="warning", id="btn_run_terminal"))
        buttons.mount(Button("Cancel", variant="default", id="btn_cancel"))

        if self._tmux_available:
            self._populate_tmux_tab()
            # Pre-select tmux tab if prefer_tmux is enabled or running inside tmux
            if self._tmux_defaults.get("prefer_tmux") or os.environ.get("TMUX"):
                try:
                    self.query_one("#agent_cmd_tabs", TabbedContent).active = "tab_tmux"
                except Exception:
                    pass

        self._refresh_agent_row()

    def _populate_tmux_tab(self) -> None:
        tmux = self.query_one("#tmux_content")

        # Session selector
        sessions = get_tmux_sessions()
        session_options = [(s, s) for s in sessions]
        session_options.append(("+ Create new session", _NEW_SESSION_SENTINEL))

        initial_session = pick_initial_session(
            sessions,
            self._tmux_defaults.get("default_session"),
            AgentCommandScreen._last_session_by_project.get(self._project_key),
        )

        sess_row = Horizontal(classes="tmux-field-row")
        tmux.mount(sess_row)
        sess_row.mount(Label("(S)ession:"))
        sess_row.mount(Select(session_options, value=initial_session, id="tmux_session_select"))

        # New session name input (hidden by default)
        new_sess_row = Horizontal(id="tmux_new_session_row", classes="hidden")
        tmux.mount(new_sess_row)
        new_sess_row.mount(Label("Session (n)ame:"))
        new_sess_row.mount(Input(
            value=self._tmux_defaults["default_session"],
            id="tmux_new_session_input",
            placeholder="Session name",
        ))

        # Window selector — pre-populate options/value at construction time so
        # the Select widget does not have to mutate set_options or value after
        # mount. This avoids two timing races on Select internals: SelectOverlay
        # not-yet-mounted on Textual 8.0 (set_options) and SelectCurrent's
        # #label not-yet-mounted under fast reactive flow on 8.1.x (_watch_value).
        # Event-driven re-population still goes through _update_window_options.
        if initial_session != _NEW_SESSION_SENTINEL:
            win_options, win_value = self._compute_window_options(initial_session)
        else:
            win_options = []
            win_value = Select.NULL

        win_row = Horizontal(classes="tmux-field-row")
        tmux.mount(win_row)
        win_row.mount(Label("(W)indow:"))
        win_row.mount(Select(
            win_options,
            value=win_value,
            allow_blank=True,
            id="tmux_window_select",
        ))

        # New window name input
        new_win_row = Horizontal(id="tmux_new_window_row", classes="hidden")
        tmux.mount(new_win_row)
        new_win_row.mount(Label("Window na(m)e:"))
        new_win_row.mount(Input(
            value=self.default_window_name,
            id="tmux_new_window_input",
            placeholder="Window name",
        ))

        # Split direction toggle (hidden until existing window selected)
        split_row = Horizontal(id="tmux_split_row", classes="hidden")
        tmux.mount(split_row)
        split_row.mount(Label("Split:"))
        split_label = "\u27f7 Horizontal" if self._split_horizontal else "\u2195 Vertical"
        split_row.mount(Button(split_label, variant="default", id="btn_split_toggle"))

        # Buttons
        buttons = Horizontal(classes="agent-cmd-buttons")
        tmux.mount(buttons)
        buttons.mount(Button("(R)un in tmux", variant="warning", id="btn_run_tmux"))
        buttons.mount(Button("Cancel", variant="default", id="btn_tmux_cancel"))

        # The Select is already populated; defer only the post-mount visibility
        # toggles (and _on_window_changed side effects) until widgets in the
        # row containers are fully composed.
        if initial_session != _NEW_SESSION_SENTINEL:
            self._selected_session = initial_session
            self.call_after_refresh(self._on_window_changed, win_value)
        else:
            self.call_after_refresh(self._show_new_session_input)

    def _compute_window_options(self, session: str):
        """Compute (options, value) for the window selector for a given session.

        Default-window selection priority:
        1. Caller's tmux window (split-pane case), if it is a live window.
        2. Last window chosen in this project (per-project memory), if live.
        3. _NEW_WINDOW_SENTINEL.
        """
        windows = get_tmux_windows(session)
        options: list[tuple[str, str]] = [
            (f"\u2726 New window", _NEW_WINDOW_SENTINEL),
        ]
        options.extend(
            (f"{idx}: {name}", f"{idx}") for idx, name in windows
        )

        last_window_for_project = AgentCommandScreen._last_window_by_project.get(self._project_key)
        live_indices = {idx for idx, _name in windows}
        if self._default_tmux_window and self._default_tmux_window in live_indices:
            value = self._default_tmux_window
        elif last_window_for_project and last_window_for_project in live_indices:
            value = last_window_for_project
        else:
            value = _NEW_WINDOW_SENTINEL

        return options, value

    def _update_window_options(self, session: str) -> None:
        """Update window selector based on selected session (event-driven, post-mount)."""
        try:
            win_select = self.query_one("#tmux_window_select", Select)
        except Exception:
            return

        options, value = self._compute_window_options(session)
        win_select.set_options(options)
        win_select.value = value
        self._on_window_changed(value)

    def _show_new_session_input(self) -> None:
        try:
            self.query_one("#tmux_new_session_row").remove_class("hidden")
            # When creating new session, always create new window
            win_select = self.query_one("#tmux_window_select", Select)
            win_select.set_options([])
            win_select.clear()
            self._show_new_window_input()
            self.query_one("#tmux_split_row").add_class("hidden")
        except Exception:
            pass

    def _hide_new_session_input(self) -> None:
        try:
            self.query_one("#tmux_new_session_row").add_class("hidden")
        except Exception:
            pass

    def _show_new_window_input(self) -> None:
        try:
            self.query_one("#tmux_new_window_row").remove_class("hidden")
            self.query_one("#tmux_split_row").add_class("hidden")
        except Exception:
            pass

    def _hide_new_window_input(self) -> None:
        try:
            self.query_one("#tmux_new_window_row").add_class("hidden")
        except Exception:
            pass

    def _on_window_changed(self, value) -> None:
        if value == _NEW_WINDOW_SENTINEL:
            self._show_new_window_input()
            self._selected_window = None
        elif value and value != Select.NULL:
            self._hide_new_window_input()
            self._selected_window = value
            # Show split direction for existing windows
            try:
                self.query_one("#tmux_split_row").remove_class("hidden")
            except Exception:
                pass
        else:
            self._hide_new_window_input()
            try:
                self.query_one("#tmux_split_row").add_class("hidden")
            except Exception:
                pass

    # --- Event handlers ---

    @on(Select.Changed, "#tmux_session_select")
    def on_session_changed(self, event: Select.Changed) -> None:
        value = event.value
        if value == _NEW_SESSION_SENTINEL:
            self._selected_session = None
            self._show_new_session_input()
        elif value and value != Select.NULL:
            self._selected_session = value
            self._hide_new_session_input()
            self._update_window_options(value)
        else:
            self._selected_session = None

    @on(Select.Changed, "#tmux_window_select")
    def on_window_changed(self, event: Select.Changed) -> None:
        self._on_window_changed(event.value)

    @on(Button.Pressed, "#btn_split_toggle")
    def toggle_split(self) -> None:
        self._split_horizontal = not self._split_horizontal
        label = "\u27f7 Horizontal" if self._split_horizontal else "\u2195 Vertical"
        try:
            self.query_one("#btn_split_toggle", Button).label = label
        except Exception:
            pass

    @on(Button.Pressed, "#btn_copy_command")
    def copy_command(self) -> None:
        cmd = self._get_current_command()
        self.app.copy_to_clipboard(cmd)
        self.app.notify("Command copied to clipboard")

    @on(Button.Pressed, "#btn_copy_prompt")
    def copy_prompt(self) -> None:
        self.app.copy_to_clipboard(self.prompt_str)
        self.app.notify("Prompt copied to clipboard")

    @on(Button.Pressed, "#btn_run_terminal")
    def run_terminal(self) -> None:
        self._store_command()
        self.dismiss("run")

    @on(Button.Pressed, "#btn_run_tmux")
    def run_tmux(self) -> None:
        config = self._build_tmux_config()
        if config:
            self._store_command()
            # Remember selections for next dialog open in THIS project only.
            AgentCommandScreen._last_session_by_project[self._project_key] = config.session
            if config.new_window:
                AgentCommandScreen._last_window_by_project.pop(self._project_key, None)
            else:
                AgentCommandScreen._last_window_by_project[self._project_key] = f"{config.window}"
            self.dismiss(config)

    @on(Button.Pressed, "#btn_cancel")
    def cancel_direct(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#btn_tmux_cancel")
    def cancel_tmux(self) -> None:
        self.dismiss(None)

    # --- Actions ---

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_copy_command(self) -> None:
        self.copy_command()

    def action_copy_prompt(self) -> None:
        self.copy_prompt()

    def action_run(self) -> None:
        """Run dispatched based on active tab."""
        if self._is_tmux_tab_active():
            self.run_tmux()
        else:
            self.run_terminal()

    def action_tab_direct(self) -> None:
        if self._tmux_available:
            try:
                self.query_one("#agent_cmd_tabs", TabbedContent).active = "tab_direct"
            except Exception:
                pass

    def action_change_agent(self) -> None:
        if not self.operation:
            return
        from agent_model_picker import AgentModelPickerScreen, load_all_models
        all_models = load_all_models(self._project_root)
        current_agent, current_model = "", ""
        if self.current_agent_string and "/" in self.current_agent_string:
            current_agent, current_model = self.current_agent_string.split("/", 1)
        picker = AgentModelPickerScreen(
            self.operation,
            current_agent,
            current_model,
            all_models=all_models,
        )
        self.app.push_screen(picker, self._on_agent_picked)

    def _on_agent_picked(self, result) -> None:
        if not result or not isinstance(result, dict):
            return
        new_agent_string = result.get("value")
        if not new_agent_string:
            return
        self._apply_agent_override(new_agent_string)
        if self.operation and new_agent_string != self._default_agent_string:
            AgentCommandScreen._previous_agent_override[self.operation] = new_agent_string
        self._refresh_agent_row()

    def action_use_previous_agent(self) -> None:
        if not self.operation:
            return
        previous = AgentCommandScreen._previous_agent_override.get(self.operation)
        if previous and previous != self.current_agent_string:
            self._apply_agent_override(previous)
            self._refresh_agent_row()

    def _apply_agent_override(self, agent_string: str) -> None:
        self.current_agent_string = agent_string
        if not self.operation:
            return
        new_cmd = resolve_dry_run_command(
            self._project_root,
            self.operation,
            *self.operation_args,
            agent_string=agent_string,
        )
        if new_cmd:
            self.full_command = new_cmd
            try:
                self.query_one("#agent_cmd_input", Input).value = new_cmd
            except Exception:
                pass
        else:
            self.app.notify(
                f"Failed to resolve command for {agent_string}",
                severity="error",
            )

    def _refresh_agent_row(self) -> None:
        if not self.operation:
            return
        try:
            label = self.query_one("#agent_row_label", Label)
            label.update(
                f"Agent: {self.current_agent_string or '(unknown)'}"
            )
        except Exception:
            return
        try:
            use_last_btn = self.query_one("#btn_use_last_agent", Button)
        except Exception:
            return
        previous = AgentCommandScreen._previous_agent_override.get(self.operation)
        if previous and previous != self.current_agent_string:
            use_last_btn.label = f"(U)se previous: {previous}"
            use_last_btn.remove_class("hidden")
        else:
            use_last_btn.add_class("hidden")

    @on(Button.Pressed, "#btn_change_agent")
    def _btn_change_agent(self) -> None:
        self.action_change_agent()

    @on(Button.Pressed, "#btn_use_last_agent")
    def _btn_use_previous_agent(self) -> None:
        self.action_use_previous_agent()

    def on_key(self, event) -> None:
        focused = self.app.focused
        if isinstance(focused, (Input, Select, SelectOverlay)):
            return  # Let input/select/overlay handle the key
        # Agent override shortcuts — must run regardless of tmux availability
        if event.key in ("a", "A"):
            if self.operation:
                self.action_change_agent()
            event.prevent_default()
            return
        if event.key in ("u", "U"):
            if self.operation:
                self.action_use_previous_agent()
            event.prevent_default()
            return
        if not self._tmux_available:
            return
        # Tab navigation shortcuts (only when no Input/Select focused)
        if event.key == "t":
            try:
                self.query_one("#agent_cmd_tabs", TabbedContent).active = "tab_tmux"
            except Exception:
                pass
            event.prevent_default()
        elif event.key == "s":
            try:
                self.query_one("#tmux_session_select", Select).focus()
            except Exception:
                pass
            event.prevent_default()
        elif event.key == "n":
            try:
                self.query_one("#tmux_new_session_input", Input).focus()
            except Exception:
                pass
            event.prevent_default()
        elif event.key == "w":
            try:
                self.query_one("#tmux_window_select", Select).focus()
            except Exception:
                pass
            event.prevent_default()
        elif event.key == "m":
            try:
                self.query_one("#tmux_new_window_input", Input).focus()
            except Exception:
                pass
            event.prevent_default()

    # --- Helpers ---

    def _get_current_command(self) -> str:
        """Get command from the shared Input widget."""
        try:
            return self.query_one("#agent_cmd_input", Input).value
        except Exception:
            return self.full_command

    def _store_command(self) -> None:
        """Store edited command back to self.full_command."""
        self.full_command = self._get_current_command()

    def _is_tmux_tab_active(self) -> bool:
        if not self._tmux_available:
            return False
        try:
            tabs = self.query_one("#agent_cmd_tabs", TabbedContent)
            return tabs.active == "tab_tmux"
        except Exception:
            return False

    def _build_tmux_config(self) -> TmuxLaunchConfig | None:
        """Build TmuxLaunchConfig from current dialog state."""
        # Resolve session
        try:
            sess_select = self.query_one("#tmux_session_select", Select)
        except Exception:
            self.app.notify("Cannot read session selection", severity="error")
            return None

        if sess_select.value == _NEW_SESSION_SENTINEL:
            try:
                session = self.query_one("#tmux_new_session_input", Input).value.strip()
            except Exception:
                session = ""
            if not session:
                self.app.notify("Session name cannot be empty", severity="error")
                return None
            new_session = True
        elif sess_select.value and sess_select.value != Select.NULL:
            session = sess_select.value
            new_session = False
        else:
            self.app.notify("Please select a session", severity="error")
            return None

        # Resolve window
        try:
            win_select = self.query_one("#tmux_window_select", Select)
        except Exception:
            win_select = None

        if new_session or (win_select and win_select.value == _NEW_WINDOW_SENTINEL):
            try:
                window = self.query_one("#tmux_new_window_input", Input).value.strip()
            except Exception:
                window = ""
            if not window:
                window = self.default_window_name or "aitask"
            new_window = True
        elif win_select and win_select.value and win_select.value != Select.NULL:
            window = win_select.value
            new_window = False
        else:
            # Default to new window
            window = self.default_window_name or "aitask"
            new_window = True

        split_direction = "horizontal" if self._split_horizontal else "vertical"

        return TmuxLaunchConfig(
            session=session,
            window=window,
            new_session=new_session,
            new_window=new_window,
            split_direction=split_direction,
            cwd=str(self._project_root),
        )
