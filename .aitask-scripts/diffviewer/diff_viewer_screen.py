"""Diff viewer screen: displays diffs with navigation, mode switching, and summary."""
from __future__ import annotations

import os

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Header, Label, Static
from textual import on, work

from .diff_display import DiffDisplay
from .diff_engine import MultiDiffResult, compute_multi_diff
from .merge_engine import MergeSession
from .merge_screen import MergeScreen
from .plan_loader import load_plan


class SummaryScreen(ModalScreen):
    """Modal overlay showing unique line counts per plan."""

    BINDINGS = [
        Binding("escape", "dismiss_summary", "Close", show=False),
    ]

    def __init__(self, result: MultiDiffResult, mode: str, **kwargs):
        super().__init__(**kwargs)
        self._result = result
        self._mode = mode

    def compose(self) -> ComposeResult:
        result = self._result
        main_name = os.path.basename(result.main_path)

        with Vertical(id="summary_container"):
            yield Label("Diff Summary", id="summary_title")
            yield Label("")
            yield Label(f"Mode: {self._mode.capitalize()}")
            yield Label(f"Main plan: {main_name}")
            yield Label("")

            # Unique to main
            main_lines = sum(len(h.main_lines) for h in result.unique_to_main)
            yield Label(f"Unique to main: {main_lines} lines")

            # Unique to each other plan
            for other_path, hunks in result.unique_to_others.items():
                other_name = os.path.basename(other_path)
                other_lines = sum(len(h.other_lines) for h in hunks)
                yield Label(f"Unique to {other_name}: {other_lines} lines")

            yield Label("")
            yield Button("Close", variant="primary", id="btn_close_summary")

    @on(Button.Pressed, "#btn_close_summary")
    def on_close(self) -> None:
        self.dismiss()

    def action_dismiss_summary(self) -> None:
        self.dismiss()


class DiffViewerScreen(Screen):
    """Screen for viewing diffs between plans with navigation and mode switching."""

    BINDINGS = [
        Binding("n", "next_comparison", "Next"),
        Binding("p", "prev_comparison", "Prev"),
        Binding("m", "toggle_mode", "Mode"),
        Binding("u", "unified_view", "Unified"),
        Binding("v", "toggle_layout", "Layout"),
        Binding("s", "summary", "Summary"),
        Binding("e", "enter_merge", "Merge"),
        Binding("escape", "back", "Back"),
    ]

    def __init__(self, main_path: str, other_paths: list[str], mode: str = "classical"):
        super().__init__()
        self._main_path = main_path
        self._other_paths = other_paths
        self._initial_mode = mode
        self._current_mode = mode
        self._active_idx = 0
        self._classical_result: MultiDiffResult | None = None
        self._structural_result: MultiDiffResult | None = None
        self._unified_mode = False
        self._side_by_side = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Computing diffs...", id="info_bar")
        yield DiffDisplay(id="diff_viewer")
        yield Footer()

    def on_mount(self) -> None:
        self._compute_diffs()

    @work(exclusive=True, thread=True)
    def _compute_diffs(self) -> None:
        """Compute both classical and structural diffs in a background thread."""
        classical = compute_multi_diff(self._main_path, self._other_paths, mode="classical")
        structural = compute_multi_diff(self._main_path, self._other_paths, mode="structural")
        self.app.call_from_thread(self._on_diffs_ready, classical, structural)

    def _on_diffs_ready(self, classical: MultiDiffResult, structural: MultiDiffResult) -> None:
        """Handle computed diffs — cache results and load the initial view."""
        self._classical_result = classical
        self._structural_result = structural
        self._load_current_view()

    def _get_active_result(self) -> MultiDiffResult | None:
        """Return the cached result for the current mode."""
        if self._current_mode == "structural":
            return self._structural_result
        return self._classical_result

    def _load_current_view(self) -> None:
        """Load the appropriate comparison into the DiffDisplay widget."""
        result = self._get_active_result()
        if result is None or not result.comparisons:
            return

        display = self.query_one("#diff_viewer", DiffDisplay)

        if self._unified_mode:
            display.load_unified_diff(result)
        else:
            # Clamp index
            self._active_idx = self._active_idx % len(result.comparisons)
            display.load_multi_diff(result, self._active_idx)
            display.set_layout(self._side_by_side)

        self._update_info_bar()

    def _update_info_bar(self) -> None:
        """Update the info bar text with current state."""
        result = self._get_active_result()
        if result is None or not result.comparisons:
            return

        main_name = os.path.basename(self._main_path)
        total = len(result.comparisons)
        mode_label = self._current_mode.capitalize()
        layout_label = "Side-by-side" if self._side_by_side else "Interleaved"

        if self._unified_mode:
            if self._side_by_side:
                text = f"Unified view ({total} comparisons, {mode_label}, {layout_label})"
            else:
                text = f"Main: {main_name} \u2014 Unified view ({total} comparisons, {mode_label}, {layout_label})"
        else:
            idx = self._active_idx % total
            if self._side_by_side:
                text = f"{mode_label}, {idx + 1}/{total}, {layout_label}"
            else:
                other_name = os.path.basename(result.comparisons[idx].other_path)
                text = f"Main: {main_name} vs {other_name} ({mode_label}, {idx + 1}/{total}, {layout_label})"

        self.query_one("#info_bar", Static).update(text)

    # -- Navigation actions ---------------------------------------------------

    def action_next_comparison(self) -> None:
        result = self._get_active_result()
        if result is None or not result.comparisons:
            return
        if self._unified_mode:
            self._jump_to_section(forward=True)
            return
        self._active_idx = (self._active_idx + 1) % len(result.comparisons)
        self._load_current_view()

    def action_prev_comparison(self) -> None:
        result = self._get_active_result()
        if result is None or not result.comparisons:
            return
        if self._unified_mode:
            self._jump_to_section(forward=False)
            return
        self._active_idx = (self._active_idx - 1) % len(result.comparisons)
        self._load_current_view()

    def _jump_to_section(self, forward: bool) -> None:
        """Jump cursor to the next/previous comparison header in unified mode."""
        display = self.query_one("#diff_viewer", DiffDisplay)
        headers = [
            i for i, dl in enumerate(display._flat_lines)
            if dl.tag == "header"
        ]
        if not headers:
            return
        cur = display._cursor_line
        if forward:
            target = next((h for h in headers if h > cur), headers[0])
        else:
            target = next((h for h in reversed(headers) if h < cur), headers[-1])
        display._move_cursor(target)

    def action_toggle_mode(self) -> None:
        if self._current_mode == "classical":
            self._current_mode = "structural"
        else:
            self._current_mode = "classical"
        self._load_current_view()

    def action_unified_view(self) -> None:
        self._unified_mode = not self._unified_mode
        self._load_current_view()

    def action_toggle_layout(self) -> None:
        """Toggle between interleaved and side-by-side layout."""
        if self._unified_mode:
            self.notify("Side-by-side not available in unified mode", severity="warning")
            return
        self._side_by_side = not self._side_by_side
        display = self.query_one("#diff_viewer", DiffDisplay)
        display.set_layout(self._side_by_side)
        self._update_info_bar()

    def action_summary(self) -> None:
        result = self._get_active_result()
        if result is None:
            self.notify("Diffs not yet computed", severity="warning")
            return
        self.app.push_screen(SummaryScreen(result, self._current_mode))

    def action_enter_merge(self) -> None:
        """Enter merge mode: create a MergeSession from current diffs."""
        result = self._get_active_result()
        if result is None or not result.comparisons:
            self.notify("Diffs not yet computed", severity="warning")
            return
        try:
            main_meta, _body, main_lines = load_plan(self._main_path)
        except FileNotFoundError:
            self.notify(f"Main plan not found: {self._main_path}", severity="error")
            return
        session = MergeSession(main_lines, result)
        self.app.push_screen(
            MergeScreen(session, self._main_path, main_meta),
            callback=self._on_merge_result,
        )

    def _on_merge_result(self, saved_path: str | None) -> None:
        """Handle merge result: merged file becomes main, original main joins others."""
        if saved_path is None:
            return
        # The merged file becomes the new main plan
        old_main = self._main_path
        self._main_path = saved_path
        # Add the original main to the comparison set (if not already there)
        if old_main not in self._other_paths:
            self._other_paths.append(old_main)
        # Start showing the first comparison
        self._active_idx = 0
        # Recompute diffs with the new main
        self._classical_result = None
        self._structural_result = None
        self._compute_diffs()

    def action_back(self) -> None:
        self.app.pop_screen()
