from __future__ import annotations

import subprocess
from collections.abc import Iterable
from pathlib import Path

from textual import work
from textual.widgets import DirectoryTree


EXCLUDED_NAMES = {"__pycache__", "node_modules", ".git"}


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
                await self.reload_node(node)

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
                    # reload_node loads children AND expands the node
                    await self.reload_node(found)
                elif not found.is_expanded:
                    # Already loaded but collapsed — just expand
                    found.expand()
            node = found

        self.select_node(node)
        self.scroll_to_node(node)

    def __init__(self, path: str | Path, **kwargs) -> None:
        root = Path(path)
        result = subprocess.run(
            ["git", "ls-files"],
            capture_output=True,
            text=True,
            cwd=root,
        )
        self._tracked_files: set[str] = set()
        self._tracked_dirs: set[str] = set()
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                if line:
                    self._tracked_files.add(line)
                    p = Path(line)
                    for parent in p.parents:
                        parent_str = str(parent)
                        if parent_str == ".":
                            break
                        self._tracked_dirs.add(parent_str)
        super().__init__(path, **kwargs)

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
