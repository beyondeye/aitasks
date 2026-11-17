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
#: Where a dataset's stand-in agent lives, relative to the project. The
#: session puts this directory first on every pane's PATH (``session.py``).
STANDIN_BIN = ".standin/bin"


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
    """A standalone ``ait`` project: the dispatcher beside a COPY of the
    framework scripts. ``ait`` changes to its own directory, so the relative
    ``TASK_DIR="aitasks"`` resolves inside this tree.

    A copy, not a symlink: several TUIs find their project as
    ``Path(__file__).resolve().parents[2]`` (the monitor reads its config and
    the sitrep list from there), and resolving a symlink would lead them back
    into the real repository and put its data on screen.
    """
    root.mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "ait", root / "ait")
    (root / "ait").chmod(0o755)
    shutil.copytree(REPO_ROOT / ".aitask-scripts", root / ".aitask-scripts", symlinks=True,
                    ignore=shutil.ignore_patterns("__pycache__"))


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
    # The tmux session is named after the project (``session.TMUX_SESSION``);
    # without this the monitor offers to rename it.
    (meta / "project_config.yaml").write_text(
        f"project:\n  name: {PROJECT_NAME}\ntmux:\n  default_session: {PROJECT_NAME}\n",
        encoding="utf-8")
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
    # Every dataset ships the stand-in, so `claude` on a session's pinned PATH
    # is never the user's real agent, whatever the agent presses.
    write_standin(root)
    _git_commit_all(root, "Sample project")


def write_standin(root: Path) -> None:
    """Install the stand-in agent (``standin_agent.py``) as ``claude``.

    Every dataset has it: the framework launches agents by bare name, and the
    session puts this directory first on every pane's PATH and refuses to start
    when ``claude`` resolves anywhere else (``session.check_standin``). A small
    shell wrapper runs it on the pinned interpreter. The directory is ignored
    by the sample repository, so it never shows as project content.
    """
    bin_dir = root / STANDIN_BIN
    bin_dir.mkdir(parents=True)
    shutil.copy2(Path(__file__).with_name("standin_agent.py"), bin_dir.parent / "standin_agent.py")
    wrapper = bin_dir / "claude"
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        "# Stand-in code agent for docs screenshots (website/screenshots/standin_agent.py).\n"
        'here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        # argv[0] "claude": tmux reports a pane's command from argv[0], and the
        # monitor family recognises an agent's kind by that name.
        'exec -a claude "${AIT_PYTHON:-python3}" "$here/../standin_agent.py" "$@"\n',
        encoding="utf-8")
    wrapper.chmod(0o755)
    with open(root / ".gitignore", "a", encoding="utf-8") as fh:
        fh.write(".standin/\n")


#: Seed metadata the agent launch path reads (``aitask_codeagent.sh`` resolves
#: the agent and model; the launch dialog shows the skill profile).
AGENT_SEED_FILES = ("models_claudecode.json",)


def write_agent_metadata(root: Path) -> None:
    """The code-agent configuration, with EVERY operation on the agent the seed
    uses for ``pick``: the stand-in answers only as ``claude``, so an operation
    routed to another agent (the seed sends ``shadow`` to codex) would fail to
    launch, or reach a real agent of that name."""
    meta = root / "aitasks" / "metadata"
    for name in AGENT_SEED_FILES:
        shutil.copy2(REPO_ROOT / "seed" / name, meta / name)
    shutil.copytree(REPO_ROOT / "seed" / "profiles", meta / "profiles")
    seed = json.loads((REPO_ROOT / "seed" / "codeagent_config.json").read_text(encoding="utf-8"))
    pick = seed["defaults"]["pick"]
    if not pick.startswith("claudecode/"):
        raise DatasetError(f"seed pick agent {pick!r} is not claudecode; the stand-in is `claude`")
    config = {**seed, "defaults": {op: pick for op in seed["defaults"]}}
    (meta / "codeagent_config.json").write_text(json.dumps(config, indent=2) + "\n",
                                                encoding="utf-8")


def _build_agents(root: Path) -> None:
    """``base`` plus the code-agent configuration and a local ``origin``, for
    the TUIs that launch and watch agents (monitor, minimonitor, sitrep).

    The tasks keep their ``base`` status: a task an agent was just started on
    is still ``Ready`` (the stand-in claims nothing), and an ``Implementing``
    task with no live lock holder is what sitrep's crash recovery reports.
    Recipes give an agent's task a gate ledger with ``setup`` commands, which
    is what the monitor family shows its workflow phase from.
    """
    write_project_shell(root)
    write_tasks(root, BASE_COLUMNS, BASE_TASKS)
    write_agent_metadata(root)
    write_standin(root)
    _git_commit_all(root, "Sample project")
    add_local_origin(root)


def add_local_origin(root: Path) -> None:
    """A bare ``origin`` inside the (ignored) stand-in directory, holding
    ``main``: the framework's lock branch and sync code need a remote, and this
    one needs no network. ``./ait lock --init`` (a recipe setup command)
    creates the lock branch on it."""
    remote = root / ".standin" / "origin.git"
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    for argv in (["git", "init", "-q", "--bare", "-b", "main", str(remote)],
                 ["git", "remote", "add", "origin", str(remote)],
                 ["git", "push", "-q", "-u", "origin", "main"]):
        try:
            subprocess.run(argv, cwd=root, env=env, check=True, capture_output=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise DatasetError(f"{' '.join(argv)} failed in the sample project: {exc}") from exc


#: name -> builder(root). A builder creates ``root`` and everything in it.
DATASETS: dict[str, Callable[[Path], None]] = {
    "base": _build_base,
    "agents": _build_agents,
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
