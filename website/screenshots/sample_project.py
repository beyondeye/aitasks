"""Sample projects for docs screenshots: named, repeatable datasets.

A screenshot shows the real TUI running on one of these projects, never on the
real repository. A dataset is a function that writes project *data* into a
fresh directory: task files, metadata, a git repository. It never imports,
patches or stubs TUI code; whatever it writes, the real TUI reads through its
normal code paths.

A recipe (``scenes/<id>.yaml``) names its dataset. Together with the recipe's
recorded ``setup`` commands, that is the whole state a replay starts from.

Every name on screen is invented (documentation rule): the project is
``lumen``, an online shop. Dates are fixed, so nothing here depends on the day
a capture runs.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The project name shown on screen.
PROJECT_NAME = "lumen"
#: The one person who appears in the sample data.
PERSON_NAME = "Alex Rivera"
PERSON_EMAIL = "alex@example.com"
#: Every timestamp written into sample files.
FIXED_STAMP = "2026-03-02 09:00"


class DatasetError(Exception):
    """An unknown dataset, or a dataset that could not be built."""


@dataclass(frozen=True)
class SampleTask:
    task_id: str          # "12" or "12_1"
    slug: str
    col: str
    idx: int
    meta: tuple[tuple[str, str], ...]   # ordered frontmatter (value is YAML text)

    def path_in(self, tasks: Path) -> Path:
        if "_" in self.task_id:
            parent = self.task_id.split("_", 1)[0]
            return tasks / f"t{parent}" / f"t{self.task_id}_{self.slug}.md"
        return tasks / f"t{self.task_id}_{self.slug}.md"

    def text(self) -> str:
        lines = ["---"]
        lines += [f"{key}: {value}" for key, value in self.meta]
        lines += [f"boardcol: {self.col}", f"boardidx: {self.idx}",
                  f"created_at: {FIXED_STAMP}", f"updated_at: {FIXED_STAMP}", "---", ""]
        title = self.slug.replace("_", " ")
        lines += ["## Context", "", f"{title[0].upper()}{title[1:]} for the {PROJECT_NAME} shop.", ""]
        return "\n".join(lines)


def _task(task_id, slug, col, idx, *, priority, effort, issue_type, labels,
          status="Ready", **extra) -> SampleTask:
    meta = [("priority", priority), ("effort", effort)]
    if "depends" in extra:
        meta.append(("depends", extra.pop("depends")))
    meta += [("issue_type", issue_type), ("status", status), ("labels", labels)]
    meta += list(extra.items())
    return SampleTask(task_id, slug, col, idx, tuple(meta))


BASE_COLUMNS = (
    {"id": "now", "title": "Now", "color": "#FF5555"},
    {"id": "next", "title": "Next", "color": "#50FA7B"},
    {"id": "backlog", "title": "Backlog", "color": "#BD93F9"},
)

#: One parent with three children (two of them blocked by a sibling), and
#: ordinary tasks of several types across the three columns.
BASE_TASKS = (
    _task("12", "add_checkout_page", "now", 10, priority="high", effort="high",
          issue_type="feature", labels="[checkout, ui]",
          children_to_implement="[t12_1, t12_2, t12_3]"),
    _task("12_1", "cart_summary_widget", "now", 20, priority="high", effort="medium",
          issue_type="feature", labels="[checkout, ui]"),
    _task("12_2", "payment_form_validation", "now", 30, priority="high", effort="medium",
          issue_type="feature", labels="[checkout]", depends="[t12_1]"),
    _task("12_3", "order_confirmation_email", "now", 40, priority="medium", effort="low",
          issue_type="feature", labels="[checkout, email]", depends="[t12_2]"),
    _task("14", "fix_login_redirect_loop", "now", 50, priority="high", effort="low",
          issue_type="bug", labels="[auth]"),
    _task("9", "search_results_pagination", "next", 10, priority="medium", effort="medium",
          issue_type="feature", labels="[search]"),
    _task("15", "cache_product_images", "next", 20, priority="medium", effort="medium",
          issue_type="performance", labels="[catalog]"),
    _task("7", "document_api_rate_limits", "backlog", 10, priority="low", effort="low",
          issue_type="documentation", labels="[api, docs]"),
    _task("11", "refactor_price_formatter", "backlog", 20, priority="low", effort="medium",
          issue_type="refactor", labels="[catalog]"),
)


def _git_commit_all(root: Path, message: str) -> None:
    env = {**os.environ,
           "GIT_AUTHOR_NAME": PERSON_NAME, "GIT_AUTHOR_EMAIL": PERSON_EMAIL,
           "GIT_COMMITTER_NAME": PERSON_NAME, "GIT_COMMITTER_EMAIL": PERSON_EMAIL,
           "GIT_AUTHOR_DATE": "2026-03-02T09:00:00", "GIT_COMMITTER_DATE": "2026-03-02T09:00:00",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    for argv in (["git", "init", "-q", "-b", "main", "."],
                 ["git", "add", "-A", "."],
                 ["git", "commit", "-q", "--no-verify", "-m", message]):
        try:
            subprocess.run(argv, cwd=root, env=env, check=True, capture_output=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise DatasetError(f"{' '.join(argv)} failed in the sample project: {exc}") from exc


def write_project_shell(root: Path) -> None:
    """A standalone ``ait`` project: the dispatcher beside a symlink to the
    framework scripts. ``ait`` changes to its own directory, so the relative
    ``TASK_DIR="aitasks"`` resolves inside this tree."""
    root.mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "ait", root / "ait")
    (root / "ait").chmod(0o755)
    (root / ".aitask-scripts").symlink_to(REPO_ROOT / ".aitask-scripts")


def write_tasks(root: Path, columns, tasks) -> None:
    meta = root / "aitasks" / "metadata"
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "board_config.json").write_text(
        json.dumps({"columns": list(columns),
                    "column_order": [c["id"] for c in columns]}, indent=2) + "\n",
        encoding="utf-8")
    # No auto-refresh: a timer must not repaint the board while it is captured.
    (meta / "board_config.local.json").write_text(
        json.dumps({"settings": {"auto_refresh_minutes": 0, "collapsed_columns": [],
                                 "sync_on_refresh": False}}, indent=2) + "\n",
        encoding="utf-8")
    (meta / "project_config.yaml").write_text(
        f"project:\n  name: {PROJECT_NAME}\n", encoding="utf-8")
    (meta / "userconfig.yaml").write_text(f"email: {PERSON_EMAIL}\n", encoding="utf-8")
    # A missing gate registry silently reclassifies gate-bearing tasks.
    shutil.copy2(REPO_ROOT / ".aitask-scripts" / "gates_reference.yaml", meta / "gates.yaml")
    types = REPO_ROOT / "seed" / "task_types.txt"
    if types.is_file():
        shutil.copy2(types, meta / "task_types.txt")
    for task in tasks:
        path = task.path_in(root / "aitasks")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(task.text(), encoding="utf-8")


def _build_base(root: Path) -> None:
    write_project_shell(root)
    write_tasks(root, BASE_COLUMNS, BASE_TASKS)
    _git_commit_all(root, "Sample project")


#: name -> builder(root). A builder creates ``root`` and everything in it.
DATASETS: dict[str, Callable[[Path], None]] = {
    "base": _build_base,
}


def build(root: Path, dataset: str = "base") -> Path:
    """Build ``dataset`` at ``root`` (which must not exist) and return it."""
    builder = DATASETS.get(dataset)
    if builder is None:
        known = ", ".join(sorted(DATASETS))
        raise DatasetError(f"unknown dataset {dataset!r}; known datasets: {known}")
    root = Path(root)
    if root.exists():
        raise DatasetError(f"sample project root already exists: {root}")
    builder(root)
    return root
