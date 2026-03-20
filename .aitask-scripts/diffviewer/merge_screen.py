"""Merge screen: hunk selection with live preview and save dialog."""
from __future__ import annotations

import os

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static
from textual import on

from rich.style import Style
from rich.table import Table
from rich.text import Text

from .diff_engine import DiffHunk, MultiDiffResult
from .merge_engine import (
    MergeSession,
    apply_merge,
    apply_merge_annotated,
    compute_hunk_preview_range,
    suggest_directory,
    suggest_filename,
)
from .plan_loader import load_plan


# Styles for hunk display
ACCEPTED_STYLE = Style(color="black", bgcolor="#50FA7B")
REJECTED_STYLE = Style(dim=True)
CURSOR_BG = Style(bgcolor="#444444", bold=True)
PLAN_HEADER_STYLE = Style(color="#8BE9FD", bold=True)


class _HunkEntry:
    """Metadata for one hunk in the list."""

    def __init__(self, plan_path: str, hunk_idx: int, hunk: DiffHunk):
        self.plan_path = plan_path
        self.hunk_idx = hunk_idx
        self.hunk = hunk

    @property
    def key(self) -> tuple[str, int]:
        return (self.plan_path, self.hunk_idx)


class SaveMergeDialog(ModalScreen):
    """Modal dialog for saving the merged plan file."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(
        self,
        suggested_name: str,
        suggested_dir: str,
        accepted_count: int,
        plan_count: int,
        merged_lines: list[str],
        main_metadata: dict,
        accepted_plans: list[str],
    ):
        super().__init__()
        self._suggested_name = suggested_name
        self._suggested_dir = suggested_dir
        self._accepted_count = accepted_count
        self._plan_count = plan_count
        self._merged_lines = merged_lines
        self._main_metadata = main_metadata
        self._accepted_plans = accepted_plans

    def compose(self) -> ComposeResult:
        with Vertical(id="save_merge_dialog"):
            yield Label("Save Merged Plan", id="save_merge_title")
            yield Label("")
            yield Label("Filename:")
            yield Input(value=self._suggested_name, id="merge_filename_input")
            yield Label("Directory:")
            yield Input(value=self._suggested_dir, id="merge_dir_input")
            yield Label("")
            yield Label(
                f"Accepted: {self._accepted_count} hunks from {self._plan_count} plans"
            )
            yield Label("")
            with Horizontal(id="save_merge_buttons"):
                yield Button("Save", variant="primary", id="btn_save_merge")
                yield Button("Cancel", variant="default", id="btn_cancel_merge")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.on_save()

    @on(Button.Pressed, "#btn_save_merge")
    def on_save(self) -> None:
        filename = self.query_one("#merge_filename_input", Input).value.strip()
        directory = self.query_one("#merge_dir_input", Input).value.strip()
        if not filename:
            self.notify("Filename cannot be empty", severity="error")
            return

        path = os.path.join(directory, filename)

        # Build frontmatter from main plan metadata
        merged_from = [os.path.basename(p) for p in self._accepted_plans]
        meta = dict(self._main_metadata)
        meta["merged_from"] = merged_from

        # Write file with frontmatter + merged body
        try:
            os.makedirs(directory, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write("---\n")
                for key, value in meta.items():
                    if isinstance(value, list):
                        f.write(f"{key}: [{', '.join(str(v) for v in value)}]\n")
                    else:
                        f.write(f"{key}: {value}\n")
                f.write("---\n\n")
                f.writelines(self._merged_lines)
            self.dismiss(path)
        except OSError as e:
            self.notify(f"Error saving: {e}", severity="error")

    @on(Button.Pressed, "#btn_cancel_merge")
    def on_cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class MergeScreen(Screen):
    """Screen for selective hunk acceptance with live preview."""

    BINDINGS = [
        Binding("a", "accept_hunk", "Accept"),
        Binding("r", "reject_hunk", "Reject"),
        Binding("A", "accept_all", "Accept all"),
        Binding("space", "toggle_hunk", "Toggle"),
        Binding("w", "write_merge", "Write"),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("pageup", "page_up", "PgUp", show=False),
        Binding("pagedown", "page_down", "PgDn", show=False),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, session: MergeSession, main_path: str, main_metadata: dict):
        super().__init__()
        self._session = session
        self._main_path = main_path
        self._main_metadata = main_metadata
        self._entries: list[_HunkEntry] = []
        self._cursor: int = 0
        self._build_entries()

    def _build_entries(self) -> None:
        """Build flat list of hunk entries from all comparisons."""
        self._entries = []
        for comp in self._session.multi_diff.comparisons:
            for i, hunk in enumerate(comp.hunks):
                if hunk.tag != "equal":
                    self._entries.append(_HunkEntry(comp.other_path, i, hunk))

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="merge_layout"):
            with VerticalScroll(id="merge_hunk_pane"):
                yield Static("", id="hunk_list_display")
            with VerticalScroll(id="merge_preview_pane"):
                yield Static("", id="merge_preview_display")
        yield Footer()

    def on_mount(self) -> None:
        self._render_hunk_list()
        self._render_preview()

    def _render_hunk_list(self) -> None:
        """Render the hunk list with acceptance indicators."""
        if not self._entries:
            self.query_one("#hunk_list_display", Static).update("No hunks to merge.")
            return

        lines: list[Text] = []
        current_plan = ""

        for idx, entry in enumerate(self._entries):
            # Plan header when switching to a new plan
            if entry.plan_path != current_plan:
                current_plan = entry.plan_path
                plan_name = os.path.basename(current_plan)
                header = Text(f"\n--- from {plan_name} ---\n", style=PLAN_HEADER_STYLE)
                lines.append(header)

            # Checkbox and hunk summary
            is_accepted = self._session.accepted.get(entry.key, False)
            checkbox = "[x]" if is_accepted else "[ ]"
            style = ACCEPTED_STYLE if is_accepted else REJECTED_STYLE

            # Build hunk preview (max 3 lines of context)
            preview_lines = self._hunk_preview(entry.hunk)
            label = f" {checkbox} hunk {entry.hunk_idx + 1} ({entry.hunk.tag})"

            line = Text()
            if idx == self._cursor:
                line.append(">", style=Style(bold=True, color="yellow"))
            else:
                line.append(" ")
            line.append(label, style=style)
            lines.append(line)

            # Show condensed diff preview
            for pline in preview_lines:
                indent = Text("     ")
                indent.append(pline)
                if idx == self._cursor:
                    indent.stylize(Style(bgcolor="#333333"))
                lines.append(indent)

        # Combine all lines
        result = Text()
        for i, line in enumerate(lines):
            result.append_text(line)
            if i < len(lines) - 1:
                result.append("\n")

        self.query_one("#hunk_list_display", Static).update(result)

    def _hunk_preview(self, hunk: DiffHunk, max_lines: int = 3) -> list[Text]:
        """Generate a condensed preview of a hunk."""
        preview: list[Text] = []
        shown = 0

        if hunk.tag in ("delete", "replace"):
            for line in hunk.main_lines[:max_lines]:
                t = Text(f"-{line.rstrip()}", style=Style(color="#FF5555"))
                preview.append(t)
                shown += 1

        if hunk.tag in ("insert", "replace"):
            remaining = max_lines - shown
            for line in hunk.other_lines[:max(1, remaining)]:
                t = Text(f"+{line.rstrip()}", style=Style(color="#50FA7B"))
                preview.append(t)

        if hunk.tag == "moved":
            preview.append(Text(f">{hunk.other_lines[0].rstrip()}" if hunk.other_lines else ">...", style=Style(color="#8BE9FD")))

        return preview

    def _render_preview(self) -> None:
        """Render the live merged preview with line numbers and hunk highlighting."""
        merged, annotations = apply_merge_annotated(self._session)
        if not merged:
            self.query_one("#merge_preview_display", Static).update("(empty)")
            return

        # Compute highlight range for current hunk
        entry = self._current_entry()
        hl_start, hl_end = (0, 0)
        if entry is not None:
            hl_start, hl_end = compute_hunk_preview_range(
                self._session, entry.plan_path, entry.hunk_idx
            )

        # Determine which lines are from accepted hunks (any annotation)
        accepted_style = Style(color="black", bgcolor="#50FA7B")
        highlight_style = Style(bgcolor="#FFB86C", color="black", bold=True)
        lineno_width = len(str(len(merged)))

        table = Table(
            show_header=False,
            show_edge=False,
            box=None,
            pad_edge=False,
        )
        table.add_column(style="dim", justify="right", width=max(4, lineno_width + 1), no_wrap=True)
        table.add_column(no_wrap=True)

        for i, line in enumerate(merged):
            lineno = Text(str(i + 1), style="dim")
            content = Text(line.rstrip())

            # Style: highlight current hunk range, then accepted hunks
            if hl_start <= i < hl_end:
                content.stylize(highlight_style)
            elif annotations[i] is not None:
                content.stylize(accepted_style)

            table.add_row(lineno, content)

        self.query_one("#merge_preview_display", Static).update(table)

        # Scroll preview pane to show highlighted region
        if entry is not None and hl_start > 0:
            preview_pane = self.query_one("#merge_preview_pane", VerticalScroll)
            # Center the highlight in the viewport
            viewport_h = preview_pane.size.height
            target_y = max(0, hl_start - viewport_h // 3)
            preview_pane.scroll_to(y=target_y, animate=False)

    def _current_entry(self) -> _HunkEntry | None:
        """Get the hunk entry at the cursor."""
        if 0 <= self._cursor < len(self._entries):
            return self._entries[self._cursor]
        return None

    # -- Actions ---------------------------------------------------------------

    def action_accept_hunk(self) -> None:
        entry = self._current_entry()
        if entry is None:
            return
        self._session.accept_hunk(entry.plan_path, entry.hunk_idx)
        self._handle_conflicts(entry)
        self._render_hunk_list()
        self._render_preview()

    def action_reject_hunk(self) -> None:
        entry = self._current_entry()
        if entry is None:
            return
        self._session.reject_hunk(entry.plan_path, entry.hunk_idx)
        self._render_hunk_list()
        self._render_preview()

    def action_toggle_hunk(self) -> None:
        entry = self._current_entry()
        if entry is None:
            return
        self._session.toggle_hunk(entry.plan_path, entry.hunk_idx)
        if self._session.accepted.get(entry.key, False):
            self._handle_conflicts(entry)
        self._render_hunk_list()
        self._render_preview()

    def action_accept_all(self) -> None:
        entry = self._current_entry()
        if entry is None:
            return
        self._session.accept_all_from(entry.plan_path)
        # Check conflicts for all newly accepted hunks from this plan
        for e in self._entries:
            if e.plan_path == entry.plan_path and self._session.accepted.get(e.key, False):
                self._handle_conflicts(e)
        self._render_hunk_list()
        self._render_preview()

    def action_write_merge(self) -> None:
        accepted_plans = self._session.get_accepted_plans()
        if not accepted_plans:
            self.notify("No hunks accepted — nothing to merge.", severity="warning")
            return

        merged_lines = apply_merge(self._session)
        suggested_name = suggest_filename(self._main_path, accepted_plans)
        suggested_dir = suggest_directory(self._main_path)

        dialog = SaveMergeDialog(
            suggested_name=suggested_name,
            suggested_dir=suggested_dir,
            accepted_count=self._session.accepted_count(),
            plan_count=len(accepted_plans),
            merged_lines=merged_lines,
            main_metadata=self._main_metadata,
            accepted_plans=accepted_plans,
        )
        self.app.push_screen(dialog, callback=self._on_save_result)

    def _on_save_result(self, path: str | None) -> None:
        if path is not None:
            self.notify(f"Saved to {path}")
            self.dismiss(path)  # Return saved path to DiffViewerScreen

    def action_cancel(self) -> None:
        self.dismiss(None)

    # -- Cursor navigation -----------------------------------------------------

    def action_cursor_up(self) -> None:
        if self._cursor > 0:
            self._cursor -= 1
            self._render_hunk_list()
            self._render_preview()

    def action_cursor_down(self) -> None:
        if self._cursor < len(self._entries) - 1:
            self._cursor += 1
            self._render_hunk_list()
            self._render_preview()

    def action_page_up(self) -> None:
        self._cursor = max(0, self._cursor - 10)
        self._render_hunk_list()
        self._render_preview()

    def action_page_down(self) -> None:
        self._cursor = min(len(self._entries) - 1, self._cursor + 10)
        self._render_hunk_list()
        self._render_preview()

    # -- Conflict handling -----------------------------------------------------

    def _handle_conflicts(self, entry: _HunkEntry) -> None:
        """Check for conflicts after accepting a hunk, auto-deselect conflicting ones."""
        conflicts = self._session.get_conflicts()
        for plan_a, idx_a, plan_b, idx_b in conflicts:
            # Deselect the other hunk (not the one just accepted)
            if plan_a == entry.plan_path and idx_a == entry.hunk_idx:
                other_plan = os.path.basename(plan_b)
                self._session.reject_hunk(plan_b, idx_b)
                self.notify(f"Conflict: deselected hunk from {other_plan} (overlapping range)")
            elif plan_b == entry.plan_path and idx_b == entry.hunk_idx:
                other_plan = os.path.basename(plan_a)
                self._session.reject_hunk(plan_a, idx_a)
                self.notify(f"Conflict: deselected hunk from {other_plan} (overlapping range)")
