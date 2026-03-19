"""File browser widget for selecting plan files."""
from __future__ import annotations

import json
import os
from pathlib import Path

from textual.containers import VerticalScroll
from textual.message import Message
from textual.widgets import Static


# Maximum number of history entries to persist
MAX_HISTORY = 10

HISTORY_FILE = os.path.join("aitasks", "metadata", "diffviewer_history.json")


class _BrowserEntry(Static):
    """A single focusable entry in the file browser."""

    can_focus = True

    def __init__(self, label: str, path: str, is_dir: bool = False, **kwargs):
        super().__init__(label, **kwargs)
        self.entry_path = path
        self.is_dir = is_dir

    def on_focus(self) -> None:
        self.add_class("browser-focused")

    def on_blur(self) -> None:
        self.remove_class("browser-focused")

    def _find_browser(self) -> PlanBrowser:
        """Walk ancestors to find the parent PlanBrowser."""
        for ancestor in self.ancestors:
            if isinstance(ancestor, PlanBrowser):
                return ancestor
        raise LookupError("PlanBrowser not found in ancestors")

    def on_key(self, event) -> None:
        if event.key == "enter":
            browser = self._find_browser()
            if self.is_dir:
                browser.navigate_to(self.entry_path)
            else:
                browser.select_plan(self.entry_path)
            event.prevent_default()
            event.stop()

    def on_click(self) -> None:
        browser = self._find_browser()
        if self.is_dir:
            browser.navigate_to(self.entry_path)
        else:
            browser.select_plan(self.entry_path)


class PlanBrowser(VerticalScroll):
    """List-based file browser for .md plan files."""

    class PlanSelected(Message):
        """Posted when a plan file is selected."""

        def __init__(self, path: str) -> None:
            super().__init__()
            self.path = path

    def __init__(self, root_dir: str = ".aitask-scripts/diffviewer/test_plans/", **kwargs):
        super().__init__(**kwargs)
        self._root_dir = root_dir
        self._current_dir = root_dir
        self._history: list[str] = []

    def on_mount(self) -> None:
        self._load_history()
        self._refresh_listing()

    def navigate_to(self, directory: str) -> None:
        """Navigate into a directory."""
        self._current_dir = directory
        self._refresh_listing()

    def select_plan(self, path: str) -> None:
        """Select a plan file and post the message."""
        # Update history
        abs_path = os.path.abspath(path)
        if abs_path in self._history:
            self._history.remove(abs_path)
        self._history.insert(0, abs_path)
        self._history = self._history[:MAX_HISTORY]
        self._save_history()
        self._refresh_listing()

        self.post_message(self.PlanSelected(abs_path))

    def _refresh_listing(self) -> None:
        """Rebuild the browser contents for the current directory."""
        # Remove existing entries
        for child in list(self.children):
            child.remove()

        # Breadcrumb
        crumb = self._build_breadcrumb()
        self.mount(Static(crumb, classes="browser-breadcrumb"))

        # History section (only at root level)
        valid_history = [p for p in self._history if os.path.isfile(p)]
        self._history = valid_history  # prune stale entries
        if valid_history:
            self.mount(Static("Recent:", classes="browser-section-header"))
            for hist_path in valid_history[:MAX_HISTORY]:
                display = os.path.basename(hist_path)
                entry = _BrowserEntry(
                    f"  {display}",
                    hist_path,
                    is_dir=False,
                    classes="browser-history-entry",
                )
                self.mount(entry)
            self.mount(Static("─" * 30, classes="browser-separator"))

        # Directory listing
        try:
            items = sorted(os.listdir(self._current_dir))
        except OSError:
            self.mount(Static("  (cannot read directory)", classes="browser-error"))
            return

        # Parent directory entry (always shown)
        parent = os.path.dirname(os.path.normpath(self._current_dir)) or "."
        entry = _BrowserEntry(
            "  [..] Parent directory",
            parent,
            is_dir=True,
            classes="browser-dir-entry",
        )
        self.mount(entry)

        # Directories first, then .md files
        dirs = []
        files = []
        for item in items:
            full = os.path.join(self._current_dir, item)
            if os.path.isdir(full) and not item.startswith("__"):
                dirs.append((item, full))
            elif item.endswith(".md") and os.path.isfile(full):
                files.append((item, full))

        for name, full in dirs:
            entry = _BrowserEntry(
                f"  [DIR] {name}/",
                full,
                is_dir=True,
                classes="browser-dir-entry",
            )
            self.mount(entry)

        for name, full in files:
            entry = _BrowserEntry(
                f"  {name}",
                full,
                is_dir=False,
                classes="browser-file-entry",
            )
            self.mount(entry)

        if not dirs and not files:
            self.mount(Static("  (empty directory)", classes="browser-empty"))

    def _build_breadcrumb(self) -> str:
        """Build a breadcrumb path string."""
        root = os.path.normpath(self._root_dir)
        current = os.path.normpath(self._current_dir)

        if current == root:
            return f"  📂 {self._root_dir}"

        try:
            rel = os.path.relpath(current, root)
        except ValueError:
            rel = current

        parts = [self._root_dir.rstrip("/")]
        for part in Path(rel).parts:
            parts.append(part)
        return "  📂 " + " > ".join(parts)

    def _navigate_up(self) -> None:
        """Navigate to parent directory (stop at root)."""
        root = os.path.normpath(self._root_dir)
        current = os.path.normpath(self._current_dir)
        if current != root:
            parent = os.path.dirname(current)
            if os.path.normpath(parent).startswith(root) or os.path.normpath(parent) == root:
                self._current_dir = parent
                self._refresh_listing()

    def _load_history(self) -> None:
        """Load history from persistent JSON file."""
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._history = data.get("recent", [])[:MAX_HISTORY]
        except (OSError, json.JSONDecodeError, KeyError):
            self._history = []

    def _save_history(self) -> None:
        """Save history to persistent JSON file."""
        try:
            os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump({"recent": self._history[:MAX_HISTORY]}, f, indent=2)
        except OSError:
            pass
