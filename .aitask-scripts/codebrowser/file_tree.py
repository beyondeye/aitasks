from __future__ import annotations

import asyncio
import json
import subprocess
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from textual import work
from textual.containers import Container, VerticalScroll
from textual.message import Message
from textual.widgets import DirectoryTree, Static
from textual.widgets._directory_tree import DirEntry


EXCLUDED_NAMES = {"__pycache__", "node_modules", ".git"}

RECENT_FILES_HISTORY = ".aitask-history/recently_opened_files.json"
MAX_RECENT_FILES = 15


def get_project_root() -> Path:
    """Get the git project root directory."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("Not inside a git repository")
    return Path(result.stdout.strip())


def compute_tracked_sets(root: Path) -> tuple[set[str], set[str]]:
    """Run `git ls-files` at root; return (tracked_files, tracked_dirs).

    Both sets contain project-root-relative POSIX paths. Tracked dirs are all
    parent directories of tracked files (excluding ".").
    """
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        cwd=root,
    )
    files: set[str] = set()
    dirs: set[str] = set()
    if result.returncode == 0:
        for line in result.stdout.strip().splitlines():
            if line:
                files.add(line)
                p = Path(line)
                for parent in p.parents:
                    parent_str = str(parent)
                    if parent_str == ".":
                        break
                    dirs.add(parent_str)
    return files, dirs


class TrackedFilesRefreshed(Message):
    """Posted by ProjectFileTree after re-running git ls-files."""
    pass


class ProjectFileTree(DirectoryTree):
    """Directory tree filtered to show only git-tracked files."""

    def select_path(self, target: Path) -> None:
        """Expand tree to the target file and select/highlight it.

        Schedules async work to walk the tree, expanding and loading
        intermediate directories as needed before selecting the file node.
        If the target is not found (e.g. not git-tracked), does nothing.
        """
        self._do_select_path(target)

    @work(exclusive=True, group="select_path")
    async def _do_select_path(self, target: Path) -> None:
        """Async worker that expands directories and selects the target node."""
        try:
            rel_parts = target.relative_to(Path(self.path)).parts
        except ValueError:
            return

        node = self.root
        for i, part in enumerate(rel_parts):
            # Ensure this directory's children are loaded
            if node.data and not node.data.loaded:
                await self._add_to_load_queue(node)

            found = None
            for child in node.children:
                if child.data and child.data.path.name == part:
                    found = child
                    break
            if found is None:
                return

            if i < len(rel_parts) - 1:
                # Intermediate directory — ensure expanded and loaded
                if found.data and not found.data.loaded:
                    await self._add_to_load_queue(found)
                    if not found.is_expanded:
                        found.expand()
                elif not found.is_expanded:
                    # Already loaded but collapsed — just expand
                    found.expand()
            node = found

        self.select_node(node)
        self.scroll_to_node(node)

    def __init__(self, path: str | Path, **kwargs) -> None:
        root = Path(path)
        self._tracked_files, self._tracked_dirs = compute_tracked_sets(root)
        super().__init__(path, **kwargs)

    def refresh_tracked_files(self) -> None:
        """Re-run git ls-files and notify listeners."""
        self._tracked_files, self._tracked_dirs = compute_tracked_sets(
            Path(self.path)
        )
        self.post_message(TrackedFilesRefreshed())

    def _populate_node(self, node, content):
        """Populate children; skip re-firing NodeExpanded when already expanded.

        The base DirectoryTree._populate_node unconditionally calls
        node.expand() after adding children. That posts NodeExpanded even when
        the node was already expanded by the user's click, which would re-fire
        our refresh handler and loop. node.add() already invalidates the tree,
        so skipping the redundant expand still renders correctly.
        """
        node.remove_children()
        for path in content:
            node.add(
                path.name,
                data=DirEntry(path),
                allow_expand=self._safe_is_dir(path),
            )
        if not node.is_expanded:
            node.expand()

    async def _on_tree_node_expanded(self, event):
        """Force a refresh when a previously-loaded directory is re-expanded.

        First-time expansion: dir_entry.loaded is False → fall through to the
        normal load path. Second time (user collapsed then re-expanded): loaded
        is True → re-run git ls-files, clear cached children, mark unloaded,
        and re-queue the load.
        """
        event.stop()
        dir_entry = event.node.data
        if dir_entry is None:
            return
        if not await asyncio.to_thread(self._safe_is_dir, dir_entry.path):
            if event.node.data is not None:
                self.post_message(self.FileSelected(event.node, dir_entry.path))
            return
        if dir_entry.loaded:
            self.refresh_tracked_files()
            event.node.remove_children()
            dir_entry.loaded = False
        await self._add_to_load_queue(event.node)

    async def action_reset_tree(self) -> None:
        """Refresh git ls-files, clear all cached children, reload root."""
        self.refresh_tracked_files()
        self.root.remove_children()
        if self.root.data:
            self.root.data.loaded = False
        self.cursor_line = 0
        await self._add_to_load_queue(self.root)

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        root = Path(self.path)
        result = []
        for path in paths:
            if path.name in EXCLUDED_NAMES:
                continue
            try:
                rel = str(path.relative_to(root))
            except ValueError:
                continue
            if path.is_dir():
                if rel in self._tracked_dirs:
                    result.append(path)
            else:
                if rel in self._tracked_files:
                    result.append(path)
        return result


# ---------------------------------------------------------------------------
# Recently opened files
# ---------------------------------------------------------------------------


class RecentFilesStore:
    """Persistent store of recently opened file paths, project-root relative."""

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        self._path = project_root / RECENT_FILES_HISTORY

    def load_and_prune(self) -> list[dict]:
        """Load history, drop entries whose files no longer exist, persist pruned list."""
        raw = self._read_raw()
        pruned: list[dict] = []
        seen: set[str] = set()
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            rel = entry.get("path")
            if not isinstance(rel, str) or not rel or rel in seen:
                continue
            if not (self._project_root / rel).is_file():
                continue
            seen.add(rel)
            pruned.append({"path": rel, "timestamp": entry.get("timestamp", "")})
            if len(pruned) >= MAX_RECENT_FILES:
                break
        if pruned != raw:
            self._write(pruned)
        return pruned

    def save(self, history: list[dict]) -> None:
        self._write(history)

    def _read_raw(self) -> list[dict]:
        if not self._path.exists():
            return []
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        return data if isinstance(data, list) else []

    def _write(self, history: list[dict]) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(history, indent=2), encoding="utf-8"
            )
        except OSError:
            pass


class RecentFileSelected(Message):
    """Posted when a recent file row is activated (Enter or click)."""

    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path


def _focus_neighbor(widget, direction: int) -> None:
    """Move focus to next (+1) or previous (-1) visible focusable sibling."""
    parent = widget.parent
    if parent is None:
        return
    focusable = [
        w for w in parent.children
        if w.can_focus and w.display and w.styles.display != "none"
    ]
    try:
        idx = focusable.index(widget)
    except ValueError:
        return
    target = idx + direction
    if 0 <= target < len(focusable):
        focusable[target].focus()
        focusable[target].scroll_visible()


class RecentFileItem(Static):
    """Focusable row representing one recently opened file."""

    can_focus = True

    DEFAULT_CSS = """
    RecentFileItem {
        height: 1;
        padding: 0 1;
    }
    RecentFileItem:focus {
        background: $accent 20%;
    }
    RecentFileItem:hover {
        background: $accent 10%;
    }
    """

    def __init__(self, rel_path: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._rel_path = rel_path

    def render(self) -> str:
        try:
            avail = max(self.size.width - 2, 10)
        except Exception:
            avail = 40
        text = self._rel_path
        if len(text) > avail:
            text = "\u2026" + text[-(avail - 1):]
        return text

    def on_key(self, event) -> None:
        if event.key == "enter":
            self.post_message(RecentFileSelected(self._rel_path))
            event.prevent_default()
            event.stop()
        elif event.key == "down":
            _focus_neighbor(self, 1)
            event.prevent_default()
            event.stop()
        elif event.key == "up":
            _focus_neighbor(self, -1)
            event.prevent_default()
            event.stop()

    def on_click(self) -> None:
        self.post_message(RecentFileSelected(self._rel_path))


class RecentFilesList(VerticalScroll):
    """Scrollable list of recently opened files, persisted to disk."""

    DEFAULT_CSS = """
    RecentFilesList {
        max-height: 10;
    }
    RecentFilesList:focus, RecentFilesList:focus-within {
        border-left: thick $accent;
    }
    """

    def __init__(self, project_root: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self._project_root = project_root
        self._store = RecentFilesStore(project_root)
        self._history: list[dict] = []

    def on_mount(self) -> None:
        self._history = self._store.load_and_prune()
        self._refresh_display()

    def record(self, abs_path: Path) -> None:
        """Record a file open: move-to-top, persist, refresh."""
        try:
            rel = str(abs_path.relative_to(self._project_root))
        except ValueError:
            return
        if not abs_path.is_file():
            return
        self._history = [h for h in self._history if h.get("path") != rel]
        self._history.insert(
            0, {"path": rel, "timestamp": datetime.now().isoformat()}
        )
        self._history = self._history[:MAX_RECENT_FILES]
        self._store.save(self._history)
        self._refresh_display()

    def _refresh_display(self) -> None:
        for item in self.query(RecentFileItem):
            item.remove()
        for entry in self._history:
            rel = entry.get("path", "")
            if rel:
                self.mount(RecentFileItem(rel))


class LeftSidebar(Container):
    """Left sidebar composing the recent-files pane and the project file tree."""

    DEFAULT_CSS = """
    LeftSidebar {
        width: 35;
        border-right: thick $primary;
        background: $surface;
    }
    LeftSidebar .section-header {
        height: 1;
        background: $surface-lighten-1;
        padding: 0 1;
        text-style: bold;
    }
    LeftSidebar #project_files_header {
        margin-top: 1;
    }
    LeftSidebar ProjectFileTree {
        height: 1fr;
    }
    """

    def __init__(self, project_root: Path, **kwargs) -> None:
        super().__init__(**kwargs)
        self._project_root = project_root

    def compose(self):
        yield Static("Recent Files", id="recent_files_header", classes="section-header")
        yield RecentFilesList(self._project_root, id="recent_files")
        yield Static("Project Files", id="project_files_header", classes="section-header")
        yield ProjectFileTree(self._project_root, id="file_tree")
