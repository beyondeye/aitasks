from __future__ import annotations

import subprocess
from collections.abc import Iterable
from pathlib import Path

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
