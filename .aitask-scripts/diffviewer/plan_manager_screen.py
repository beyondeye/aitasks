"""Plan manager screen: file browser + loaded plans list + diff launch dialog."""
from __future__ import annotations

import os
import sys

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Checkbox, Footer, Header, Label, RadioButton, RadioSet, Static
from textual import on

# Import plan_loader for extracting headings
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from diffviewer.plan_browser import PlanBrowser
from diffviewer.plan_loader import load_plan


class _LoadedPlanEntry(Horizontal):
    """A single loaded plan displayed in the right pane."""

    def __init__(self, path: str, display_name: str, heading: str, **kwargs):
        super().__init__(**kwargs)
        self.plan_path = path
        self.display_name = display_name
        self.heading = heading

    def compose(self) -> ComposeResult:
        with Vertical(classes="plan-entry-info"):
            yield Label(self.display_name, classes="plan-entry-name")
            yield Label(self.heading, classes="plan-entry-heading")
        yield Button("Remove", variant="error", classes="plan-remove")
        yield Button("Diff as Main", variant="primary", classes="plan-diff")


class DiffLaunchDialog(ModalScreen):
    """Modal dialog for configuring and launching a diff."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, main_path: str, main_name: str, other_plans: list[tuple[str, str]], **kwargs):
        super().__init__(**kwargs)
        self._main_path = main_path
        self._main_name = main_name
        self._other_plans = other_plans  # list of (path, display_name)

    def compose(self) -> ComposeResult:
        with Vertical(id="diff_launch_dialog"):
            yield Label(f"Configure Diff: {self._main_name}", id="diff_launch_title")
            yield Label("")
            yield Label("Compare against:", classes="diff-section-label")
            with VerticalScroll(id="diff_targets"):
                for path, name in self._other_plans:
                    yield Checkbox(name, value=True, id=f"chk_{_safe_id(path)}")
            yield Label("")
            yield Label("Diff mode:", classes="diff-section-label")
            with RadioSet(id="diff_mode_set"):
                yield RadioButton("Classical", value=True, id="mode_classical")
                yield RadioButton("Structural", id="mode_structural")
            yield Label("")
            with Horizontal(id="diff_launch_buttons"):
                yield Button("Start Diff", variant="success", id="btn_start_diff")
                yield Button("Cancel", variant="default", id="btn_cancel_diff")

    @on(Button.Pressed, "#btn_start_diff")
    def on_start_diff(self) -> None:
        # Gather selected targets
        selected_paths: list[str] = []
        for path, _name in self._other_plans:
            chk_id = f"chk_{_safe_id(path)}"
            try:
                checkbox = self.query_one(f"#{chk_id}", Checkbox)
                if checkbox.value:
                    selected_paths.append(path)
            except Exception:
                pass

        if not selected_paths:
            self.notify("Select at least one plan to compare against", severity="warning")
            return

        # Determine mode
        mode = "classical"
        try:
            radio_set = self.query_one("#diff_mode_set", RadioSet)
            if radio_set.pressed_index == 1:
                mode = "structural"
        except Exception:
            pass

        self.dismiss((self._main_path, selected_paths, mode))

    @on(Button.Pressed, "#btn_cancel_diff")
    def on_cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class PlanManagerScreen(Screen):
    """Home screen with file browser and loaded plans management."""

    BINDINGS = [
        Binding("r", "remove_focused", "Remove", show=True),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._loaded_plans: list[dict] = []  # [{path, display_name, heading}]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="manager_container"):
            yield PlanBrowser(id="browser")
            with Vertical(id="loaded_pane"):
                yield Label("Loaded Plans", id="loaded_title")
                with VerticalScroll(id="loaded_list"):
                    yield Static("No plans loaded yet. Select files from the browser.",
                                 id="empty_placeholder")
        yield Footer()

    @on(PlanBrowser.PlanSelected)
    def on_plan_selected(self, event: PlanBrowser.PlanSelected) -> None:
        """Handle plan file selection from the browser."""
        path = event.path

        # Prevent duplicates
        for loaded in self._loaded_plans:
            if loaded["path"] == path:
                self.notify("Plan already loaded", severity="warning")
                return

        # Extract display info
        display_name = os.path.basename(path)
        heading = ""
        try:
            _meta, body, _lines = load_plan(path)
            # Find first heading
            for line in body.splitlines():
                stripped = line.strip()
                if stripped.startswith("#"):
                    heading = stripped.lstrip("#").strip()
                    break
        except Exception:
            heading = "(could not read)"

        plan_info = {"path": path, "display_name": display_name, "heading": heading}
        self._loaded_plans.append(plan_info)
        self._refresh_loaded_list()
        self.notify(f"Loaded: {display_name}")

    def _refresh_loaded_list(self) -> None:
        """Rebuild the loaded plans list."""
        loaded_list = self.query_one("#loaded_list", VerticalScroll)

        # Remove existing children
        for child in list(loaded_list.children):
            child.remove()

        if not self._loaded_plans:
            loaded_list.mount(
                Static("No plans loaded yet. Select files from the browser.",
                       id="empty_placeholder")
            )
            return

        for plan_info in self._loaded_plans:
            entry = _LoadedPlanEntry(
                path=plan_info["path"],
                display_name=plan_info["display_name"],
                heading=plan_info["heading"] or "(no heading)",
                classes="loaded-plan-entry",
            )
            loaded_list.mount(entry)

    @on(Button.Pressed, ".plan-remove")
    def on_remove_plan(self, event: Button.Pressed) -> None:
        """Remove a plan from the loaded list."""
        entry = _find_ancestor(event.button, _LoadedPlanEntry)
        if entry is None:
            return
        self._loaded_plans = [p for p in self._loaded_plans if p["path"] != entry.plan_path]
        self._refresh_loaded_list()
        self.notify(f"Removed: {entry.display_name}")

    @on(Button.Pressed, ".plan-diff")
    def on_diff_as_main(self, event: Button.Pressed) -> None:
        """Open diff launch dialog with this plan as main."""
        entry = _find_ancestor(event.button, _LoadedPlanEntry)
        if entry is None:
            return
        main_path = entry.plan_path
        main_name = entry.display_name

        # Build list of other loaded plans
        other_plans = [
            (p["path"], p["display_name"])
            for p in self._loaded_plans
            if p["path"] != main_path
        ]

        if not other_plans:
            self.notify("Load at least one more plan to compare against", severity="warning")
            return

        def handle_result(result) -> None:
            if result is None:
                return
            _main, _targets, _mode = result
            # t417_6 will implement DiffViewerScreen — for now show notification
            self.notify(
                f"Diff ready: {os.path.basename(_main)} vs {len(_targets)} plan(s) ({_mode})",
                severity="information",
            )

        self.app.push_screen(
            DiffLaunchDialog(main_path, main_name, other_plans),
            handle_result,
        )

    def action_remove_focused(self) -> None:
        """Remove the currently focused loaded plan entry."""
        focused = self.focused
        if focused is None:
            return
        entry = focused if isinstance(focused, _LoadedPlanEntry) else \
            _find_ancestor(focused, _LoadedPlanEntry)
        if entry is not None:
            self._loaded_plans = [p for p in self._loaded_plans if p["path"] != entry.plan_path]
            self._refresh_loaded_list()


def _find_ancestor(widget, ancestor_type):
    """Walk ancestors to find the first instance of ancestor_type, or None."""
    for ancestor in widget.ancestors:
        if isinstance(ancestor, ancestor_type):
            return ancestor
    return None


def _safe_id(path: str) -> str:
    """Convert a path to a safe CSS id fragment."""
    return path.replace("/", "_").replace(".", "_").replace(" ", "_").replace("-", "_")
