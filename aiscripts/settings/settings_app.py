#!/usr/bin/env python3
"""aitasks Settings TUI — centralized config viewer/editor.

Browse and edit all aitasks configuration: code agent defaults, board
settings, model lists, and execution profiles.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml

# Add aiscripts/lib to path for config_utils
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

from config_utils import (  # noqa: E402
    _load_json,
    deep_merge,
    export_all_configs,
    import_all_configs,
    load_layered_config,
    local_path_for,
    save_local_config,
    save_project_config,
    split_config,
)

from textual import on  # noqa: E402
from textual.app import App, ComposeResult  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.containers import Container, Horizontal, VerticalScroll  # noqa: E402
from textual.message import Message  # noqa: E402
from textual.screen import ModalScreen  # noqa: E402
from textual.widgets import (  # noqa: E402
    Button,
    Footer,
    Header,
    Input,
    Label,
    Static,
    TabbedContent,
    TabPane,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
METADATA_DIR = Path("aitasks") / "metadata"
CODEAGENT_CONFIG = METADATA_DIR / "codeagent_config.json"
BOARD_CONFIG = METADATA_DIR / "board_config.json"
MODEL_FILES = {
    "claude": METADATA_DIR / "models_claude.json",
    "codex": METADATA_DIR / "models_codex.json",
    "gemini": METADATA_DIR / "models_gemini.json",
    "opencode": METADATA_DIR / "models_opencode.json",
}
PROFILES_DIR = METADATA_DIR / "profiles"

_BOARD_PROJECT_KEYS = {"columns", "column_order"}
_BOARD_USER_KEYS = {"settings"}

DEFAULT_REFRESH_OPTIONS = ["0", "1", "2", "5", "10", "15", "30"]

# Profile schema: key -> (type, options)
# type: "bool", "enum", "string"
PROFILE_SCHEMA: dict[str, tuple[str, list[str] | None]] = {
    "name": ("string", None),
    "description": ("string", None),
    "skip_task_confirmation": ("bool", None),
    "default_email": ("enum", ["userconfig", "first"]),
    "create_worktree": ("bool", None),
    "base_branch": ("string", None),
    "plan_preference": ("enum", ["use_current", "verify", "create_new"]),
    "plan_preference_child": ("enum", ["use_current", "verify", "create_new"]),
    "post_plan_action": ("enum", ["start_implementation"]),
    "explore_auto_continue": ("bool", None),
    "force_unlock_stale": ("bool", None),
    "done_task_action": ("enum", ["archive", "skip"]),
    "orphan_parent_action": ("enum", ["archive", "skip"]),
    "complexity_action": ("enum", ["single_task", "create_children"]),
    "review_action": ("enum", ["commit", "need_changes", "abort"]),
    "issue_action": ("enum", ["close_with_notes", "comment_only", "close_silently", "skip"]),
    "abort_plan_action": ("enum", ["keep", "discard"]),
    "abort_revert_status": ("enum", ["Ready", "Editing"]),
}

_UNSET = "(unset)"


def _safe_id(name: str) -> str:
    """Sanitize a string for use as a Textual widget ID."""
    return name.replace(".", "_").replace(" ", "_")


# ---------------------------------------------------------------------------
# ConfigManager
# ---------------------------------------------------------------------------
class ConfigManager:
    """Load and save all aitasks config files."""

    def __init__(self):
        self.codeagent: dict = {}
        self.codeagent_project: dict = {}
        self.codeagent_local: dict = {}
        self.board: dict = {}
        self.board_project: dict = {}
        self.board_local: dict = {}
        self.models: dict[str, dict] = {}
        self.profiles: dict[str, dict] = {}
        self.load_all()

    def load_all(self):
        # Codeagent config
        self.codeagent = load_layered_config(str(CODEAGENT_CONFIG), defaults={"defaults": {}})
        self.codeagent_project = _load_json(CODEAGENT_CONFIG)
        self.codeagent_local = _load_json(local_path_for(str(CODEAGENT_CONFIG)))

        # Board config
        defaults = {
            "columns": [],
            "column_order": [],
            "settings": {"auto_refresh_minutes": 5},
        }
        self.board = load_layered_config(str(BOARD_CONFIG), defaults=defaults)
        self.board_project = _load_json(BOARD_CONFIG)
        self.board_local = _load_json(local_path_for(str(BOARD_CONFIG)))

        # Model files (read-only)
        self.models = {}
        for provider, path in MODEL_FILES.items():
            data = _load_json(path)
            if data:
                self.models[provider] = data

        # Profiles
        self.load_profiles()

    def load_profiles(self):
        self.profiles = {}
        if PROFILES_DIR.is_dir():
            for f in sorted(PROFILES_DIR.glob("*.yaml")):
                try:
                    with open(f, "r", encoding="utf-8") as fh:
                        data = yaml.safe_load(fh)
                    if isinstance(data, dict):
                        self.profiles[f.name] = data
                except Exception:
                    pass

    def save_codeagent(self, project_data: dict, local_data: dict):
        save_project_config(str(CODEAGENT_CONFIG), project_data)
        if local_data:
            save_local_config(str(local_path_for(str(CODEAGENT_CONFIG))), local_data)
        else:
            # Remove local file if empty
            lp = local_path_for(str(CODEAGENT_CONFIG))
            if lp.is_file():
                lp.unlink()

    def save_board(self, merged: dict):
        project_data, user_data = split_config(
            merged, project_keys=_BOARD_PROJECT_KEYS, user_keys=_BOARD_USER_KEYS
        )
        save_project_config(str(BOARD_CONFIG), project_data)
        if user_data:
            save_local_config(str(local_path_for(str(BOARD_CONFIG))), user_data)

    def save_profile(self, filename: str, data: dict):
        path = PROFILES_DIR / filename
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        self.profiles[filename] = data


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------
class CycleField(Static):
    """Focusable widget that cycles through options with Left/Right keys."""

    can_focus = True

    class Changed(Message):
        def __init__(self, field: "CycleField", value: str):
            super().__init__()
            self.field = field
            self.value = value

    def __init__(self, label: str, options: list, current: str, field_key: str,
                 id: str | None = None):
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


class ConfigRow(Static):
    """Focusable config key-value display with layer badge."""

    can_focus = True

    def __init__(self, key: str, value: str, config_layer: str = "project",
                 row_key: str = "", id: str | None = None):
        super().__init__(id=id)
        self.key = key
        self.value = value
        self.config_layer = config_layer
        self.row_key = row_key or key

    def render(self) -> str:
        if self.config_layer == "user":
            badge = "[#FFB86C][USER][/]"
        else:
            badge = "[#50FA7B][PROJECT][/]"
        return f"  {badge}  [bold]{self.key}:[/bold]  {self.value}"

    def on_focus(self):
        self.add_class("row-focused")

    def on_blur(self):
        self.remove_class("row-focused")


# ---------------------------------------------------------------------------
# Modal Screens
# ---------------------------------------------------------------------------
class EditValueScreen(ModalScreen):
    """Modal for editing a single config value."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, key: str, current_value: str, layer: str = "project"):
        super().__init__()
        self.key = key
        self.current_value = current_value
        self.initial_layer = layer

    def compose(self) -> ComposeResult:
        with Container(id="edit_dialog"):
            yield Label(f"Edit: [bold]{self.key}[/bold]", id="edit_title")
            yield Label("Value:", classes="edit-label")
            yield Input(value=self.current_value, id="edit_input")
            yield Label("Save to:", classes="edit-label")
            yield CycleField("Layer", ["project", "user"], self.initial_layer,
                             "layer", id="cf_layer")
            with Horizontal(id="edit_buttons"):
                yield Button("Save", variant="success", id="btn_edit_save")
                yield Button("Cancel", variant="default", id="btn_edit_cancel")

    @on(Button.Pressed, "#btn_edit_save")
    def do_save(self):
        value = self.query_one("#edit_input", Input).value
        layer = self.query_one("#cf_layer", CycleField).current_value
        self.dismiss({"key": self.key, "value": value, "layer": layer})

    @on(Button.Pressed, "#btn_edit_cancel")
    def do_cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class ImportScreen(ModalScreen):
    """Modal for importing config from a bundle file."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def compose(self) -> ComposeResult:
        with Container(id="import_dialog"):
            yield Label("Import Config Bundle", id="import_title")
            yield Label("File path:", classes="edit-label")
            yield Input(placeholder="path/to/export.json", id="import_path")
            yield CycleField("Overwrite existing", ["no", "yes"], "no",
                             "overwrite", id="cf_overwrite")
            with Horizontal(id="edit_buttons"):
                yield Button("Import", variant="success", id="btn_import_ok")
                yield Button("Cancel", variant="default", id="btn_import_cancel")

    @on(Button.Pressed, "#btn_import_ok")
    def do_import(self):
        path = self.query_one("#import_path", Input).value
        overwrite = self.query_one("#cf_overwrite", CycleField).current_value == "yes"
        self.dismiss({"path": path, "overwrite": overwrite})

    @on(Button.Pressed, "#btn_import_cancel")
    def do_cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class EditStringScreen(ModalScreen):
    """Modal for editing a single string value (profile fields)."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, key: str, current_value: str):
        super().__init__()
        self.key = key
        self.current_value = current_value

    def compose(self) -> ComposeResult:
        with Container(id="edit_dialog"):
            yield Label(f"Edit: [bold]{self.key}[/bold]", id="edit_title")
            yield Input(value=self.current_value, id="edit_input")
            with Horizontal(id="edit_buttons"):
                yield Button("Save", variant="success", id="btn_edit_save")
                yield Button("Cancel", variant="default", id="btn_edit_cancel")

    @on(Button.Pressed, "#btn_edit_save")
    def do_save(self):
        value = self.query_one("#edit_input", Input).value
        self.dismiss({"key": self.key, "value": value})

    @on(Button.Pressed, "#btn_edit_cancel")
    def do_cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------
class SettingsApp(App):
    """aitasks Settings TUI."""

    CSS = """
    /* Tab panes */
    TabPane { padding: 1 2; }

    /* Config rows */
    ConfigRow { height: 1; width: 100%; padding: 0 1; }
    ConfigRow.row-focused { background: $primary 20%; }

    /* Cycle fields */
    CycleField { height: 1; width: 100%; padding: 0 1; }
    CycleField.cycle-focused { background: $primary 20%; }

    /* Section headers */
    .section-header {
        text-style: bold;
        padding: 1 0 0 1;
        color: $accent;
    }
    .section-hint {
        padding: 0 0 0 3;
        color: $text-muted;
    }

    /* Model rows */
    .model-row { height: auto; padding: 0 2; }
    .model-header { text-style: bold underline; padding: 0 2; }

    /* Profile section */
    .profile-header {
        text-style: bold;
        padding: 1 0 0 1;
        color: #50FA7B;
    }
    .profile-sep { color: $text-muted; padding: 0 1; }

    /* Modal dialogs */
    #edit_dialog, #import_dialog {
        width: 60%;
        height: auto;
        max-height: 60%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    .edit-label { padding: 1 0 0 1; }
    #edit_buttons { padding: 1 0 0 0; height: auto; }
    #edit_buttons Button { margin: 0 1; }

    /* Buttons in tabs */
    .tab-buttons { padding: 1 0 0 0; height: auto; }
    .tab-buttons Button { margin: 0 1; }
    """

    TITLE = "aitasks settings"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("e", "export_configs", "Export"),
        Binding("i", "import_configs", "Import"),
        Binding("r", "reload_configs", "Reload"),
    ]

    def __init__(self):
        super().__init__()
        self.config_mgr = ConfigManager()
        self._profile_id_map: dict[str, str] = {}  # safe_id -> filename

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent("Agent Defaults", "Board", "Models", "Profiles"):
            with TabPane("Agent Defaults", id="tab_agent"):
                yield VerticalScroll(id="agent_content")
            with TabPane("Board", id="tab_board"):
                yield VerticalScroll(id="board_content")
            with TabPane("Models", id="tab_models"):
                yield VerticalScroll(id="models_content")
            with TabPane("Profiles", id="tab_profiles"):
                yield VerticalScroll(id="profiles_content")
        yield Footer()

    def on_mount(self):
        self._populate_agent_tab()
        self._populate_board_tab()
        self._populate_models_tab()
        self._populate_profiles_tab()

    # -------------------------------------------------------------------
    # Agent Defaults tab
    # -------------------------------------------------------------------
    def _populate_agent_tab(self):
        container = self.query_one("#agent_content", VerticalScroll)
        container.remove_children()

        container.mount(Label("Code Agent Default Models", classes="section-header"))
        container.mount(Label("[dim]Press Enter on a row to edit. "
                              "Left/Right arrows unavailable here — use Enter.[/dim]",
                              classes="section-hint"))

        defaults = self.config_mgr.codeagent.get("defaults", {})
        local_defaults = self.config_mgr.codeagent_local.get("defaults", {})

        for key, value in defaults.items():
            layer = "user" if key in local_defaults else "project"
            row = ConfigRow(key, str(value), config_layer=layer, row_key=key,
                            id=f"agent_row_{key}")
            container.mount(row)

    def on_config_row_key(self, event) -> None:
        """Handle key press on ConfigRow for editing (agent tab)."""
        # This is handled via on_key on the app level
        pass

    def on_key(self, event) -> None:
        if event.key == "enter":
            focused = self.focused
            if isinstance(focused, ConfigRow) and focused.id and focused.id.startswith("agent_row_"):
                key = focused.row_key
                value = focused.value
                layer = focused.config_layer
                self.push_screen(
                    EditValueScreen(key, value, layer),
                    callback=self._handle_agent_edit,
                )
                event.prevent_default()
                event.stop()
            elif isinstance(focused, ConfigRow) and focused.id and focused.id.startswith("profile_str_"):
                # Profile string editing
                parts = focused.id.split("__", 1)
                if len(parts) == 2:
                    safe_fn = parts[1]
                    profile_filename = self._profile_id_map.get(safe_fn, safe_fn)
                    key = focused.row_key
                    value = focused.value
                    self.push_screen(
                        EditStringScreen(key, value),
                        callback=lambda result, pf=profile_filename: self._handle_profile_string_edit(result, pf),
                    )
                    event.prevent_default()
                    event.stop()

    def _handle_agent_edit(self, result):
        if result is None:
            return
        key = result["key"]
        value = result["value"]
        layer = result["layer"]

        if layer == "user":
            # Add to local overrides
            local_data = dict(self.config_mgr.codeagent_local)
            if "defaults" not in local_data:
                local_data["defaults"] = {}
            local_data["defaults"][key] = value
            # Keep project data unchanged
            self.config_mgr.save_codeagent(self.config_mgr.codeagent_project, local_data)
        else:
            # Save to project, remove from local if present
            project_data = dict(self.config_mgr.codeagent_project)
            if "defaults" not in project_data:
                project_data["defaults"] = {}
            project_data["defaults"][key] = value
            local_data = dict(self.config_mgr.codeagent_local)
            if "defaults" in local_data and key in local_data["defaults"]:
                del local_data["defaults"][key]
                if not local_data["defaults"]:
                    del local_data["defaults"]
            self.config_mgr.save_codeagent(project_data, local_data)

        self.config_mgr.load_all()
        self._populate_agent_tab()
        self.notify(f"Saved {key} = {value} ({layer})")

    # -------------------------------------------------------------------
    # Board tab
    # -------------------------------------------------------------------
    def _populate_board_tab(self):
        container = self.query_one("#board_content", VerticalScroll)
        container.remove_children()

        # Columns (read-only)
        container.mount(Label("Columns [dim](read-only — edit via board TUI)[/dim]",
                              classes="section-header"))
        columns = self.board_columns
        for col in columns:
            cid = col.get("id", "?")
            title = col.get("title", "?")
            color = col.get("color", "?")
            container.mount(Static(f"    {cid}: {title}  ({color})", classes="model-row"))

        # User settings (editable)
        container.mount(Label("User Settings", classes="section-header"))

        settings = self.config_mgr.board.get("settings", {})
        current_refresh = str(settings.get("auto_refresh_minutes", 5))
        if current_refresh not in DEFAULT_REFRESH_OPTIONS:
            current_refresh = "5"
        container.mount(CycleField("Auto-refresh (min)", DEFAULT_REFRESH_OPTIONS,
                                   current_refresh, "auto_refresh_minutes",
                                   id="board_cf_refresh"))
        container.mount(Label("  [dim]0 = disabled[/dim]", classes="section-hint"))

        current_sync = "yes" if settings.get("sync_on_refresh", False) else "no"
        container.mount(CycleField("Sync on refresh", ["no", "yes"], current_sync,
                                   "sync_on_refresh", id="board_cf_sync"))
        container.mount(Label("  [dim]Push/pull task data on each auto-refresh[/dim]",
                              classes="section-hint"))

        container.mount(Button("Save Board Settings", variant="success",
                               id="btn_board_save"))

    @property
    def board_columns(self) -> list:
        return self.config_mgr.board.get("columns", [])

    @on(Button.Pressed, "#btn_board_save")
    def save_board_settings(self):
        refresh_field = self.query_one("#board_cf_refresh", CycleField)
        sync_field = self.query_one("#board_cf_sync", CycleField)

        merged = dict(self.config_mgr.board)
        if "settings" not in merged:
            merged["settings"] = {}
        merged["settings"]["auto_refresh_minutes"] = int(refresh_field.current_value)
        merged["settings"]["sync_on_refresh"] = sync_field.current_value == "yes"

        self.config_mgr.save_board(merged)
        self.config_mgr.load_all()
        self.notify("Board settings saved")

    # -------------------------------------------------------------------
    # Models tab (read-only)
    # -------------------------------------------------------------------
    def _populate_models_tab(self):
        container = self.query_one("#models_content", VerticalScroll)
        container.remove_children()

        if not self.config_mgr.models:
            container.mount(Label("No model files found.", classes="section-header"))
            return

        for provider, data in sorted(self.config_mgr.models.items()):
            container.mount(Label(f"{provider.capitalize()} Models",
                                  classes="section-header"))
            models = data.get("models", [])
            if not models:
                container.mount(Static("    (no models)", classes="model-row"))
                continue

            # Header
            container.mount(Static(
                f"    {'Name':<16} {'CLI ID':<30} {'Notes'}",
                classes="model-header",
            ))

            for m in models:
                name = m.get("name", "?")
                cli_id = m.get("cli_id", "?")
                notes = m.get("notes", "")
                verified = m.get("verified", {})
                scores = ", ".join(f"{k}:{v}" for k, v in verified.items() if v)
                score_str = f"  [dim]verified: {scores}[/dim]" if scores else ""
                container.mount(Static(
                    f"    {name:<16} {cli_id:<30} {notes}{score_str}",
                    classes="model-row",
                ))

        container.mount(Label(""))
        container.mount(Label(
            "[dim]Model lists are managed by 'ait codeagent refresh'. "
            "Edit model files directly for manual changes.[/dim]",
            classes="section-hint",
        ))

    # -------------------------------------------------------------------
    # Profiles tab (editable)
    # -------------------------------------------------------------------
    def _populate_profiles_tab(self):
        container = self.query_one("#profiles_content", VerticalScroll)
        container.remove_children()

        self._profile_id_map = {}

        if not self.config_mgr.profiles:
            container.mount(Label("No profiles found in profiles/",
                                  classes="section-header"))
            return

        for filename, data in sorted(self.config_mgr.profiles.items()):
            safe_fn = _safe_id(filename)
            self._profile_id_map[safe_fn] = filename
            profile_name = data.get("name", filename)
            desc = data.get("description", "")
            container.mount(Label(
                f"{profile_name} [dim]({filename})[/dim]  {desc}",
                classes="profile-header",
            ))

            # Render each known key as an editable widget
            for key, (ktype, options) in PROFILE_SCHEMA.items():
                current_raw = data.get(key)
                widget_id = f"profile_{key}__{safe_fn}"

                if ktype == "bool":
                    if current_raw is True:
                        current = "true"
                    elif current_raw is False:
                        current = "false"
                    else:
                        current = _UNSET
                    container.mount(CycleField(
                        key, ["true", "false", _UNSET], current,
                        key, id=widget_id,
                    ))
                elif ktype == "enum":
                    opts = list(options or []) + [_UNSET]
                    current = str(current_raw) if current_raw is not None else _UNSET
                    if current not in opts:
                        # Value not in known options — treat as custom, add it
                        opts.insert(0, current)
                    container.mount(CycleField(
                        key, opts, current, key, id=widget_id,
                    ))
                elif ktype == "string":
                    current = str(current_raw) if current_raw is not None else ""
                    row = ConfigRow(
                        key, current, config_layer="project", row_key=key,
                        id=f"profile_str_{key}__{safe_fn}",
                    )
                    container.mount(row)

            # Save button for this profile
            container.mount(Button(
                f"Save {profile_name}", variant="success",
                id=f"btn_profile_save__{_safe_id(filename)}",
            ))
            container.mount(Label("", classes="profile-sep"))

    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed):
        btn_id = event.button.id or ""
        if btn_id.startswith("btn_profile_save__"):
            safe_fn = btn_id.replace("btn_profile_save__", "")
            filename = self._profile_id_map.get(safe_fn, safe_fn)
            self._save_profile(filename)

    def _save_profile(self, filename: str):
        data = dict(self.config_mgr.profiles.get(filename, {}))
        safe_fn = _safe_id(filename)

        for key, (ktype, options) in PROFILE_SCHEMA.items():
            widget_id = f"profile_{key}__{safe_fn}"
            str_widget_id = f"profile_str_{key}__{safe_fn}"

            if ktype in ("bool", "enum"):
                try:
                    field = self.query_one(f"#{widget_id}", CycleField)
                    val = field.current_value
                    if val == _UNSET:
                        data.pop(key, None)
                    elif ktype == "bool":
                        data[key] = val == "true"
                    else:
                        data[key] = val
                except Exception:
                    pass
            elif ktype == "string":
                try:
                    row = self.query_one(f"#{str_widget_id}", ConfigRow)
                    val = row.value
                    if val:
                        data[key] = val
                    else:
                        data.pop(key, None)
                except Exception:
                    pass

        self.config_mgr.save_profile(filename, data)
        self.notify(f"Profile '{filename}' saved")

    def _handle_profile_string_edit(self, result, profile_filename: str):
        if result is None:
            return
        key = result["key"]
        value = result["value"]

        # Update the ConfigRow display immediately
        str_widget_id = f"profile_str_{key}__{_safe_id(profile_filename)}"
        try:
            row = self.query_one(f"#{str_widget_id}", ConfigRow)
            row.value = value
            row.refresh()
        except Exception:
            pass
        self.notify(f"Updated {key} — press Save to persist")

    # -------------------------------------------------------------------
    # Actions: Export, Import, Reload
    # -------------------------------------------------------------------
    def action_export_configs(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = f"aitasks_config_export_{timestamp}.json"
        try:
            bundle = export_all_configs(out_path, str(METADATA_DIR))
            count = bundle.get("_export_meta", {}).get("file_count", 0)
            self.notify(f"Exported {count} files to {out_path}")
        except Exception as exc:
            self.notify(f"Export failed: {exc}", severity="error")

    def action_import_configs(self):
        self.push_screen(ImportScreen(), callback=self._handle_import)

    def _handle_import(self, result):
        if result is None:
            return
        try:
            written = import_all_configs(
                result["path"], str(METADATA_DIR),
                overwrite=result.get("overwrite", False),
            )
            self.config_mgr.load_all()
            self._populate_agent_tab()
            self._populate_board_tab()
            self._populate_models_tab()
            self._populate_profiles_tab()
            self.notify(f"Imported {len(written)} files")
        except Exception as exc:
            self.notify(f"Import failed: {exc}", severity="error")

    def action_reload_configs(self):
        self.config_mgr.load_all()
        self._populate_agent_tab()
        self._populate_board_tab()
        self._populate_models_tab()
        self._populate_profiles_tab()
        self.notify("Configs reloaded from disk")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app = SettingsApp()
    app.run()
