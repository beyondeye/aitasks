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
import sys
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
#: The machine name a lock taken in the ``board_locks`` dataset records.
LOCK_HOSTNAME = "lumen-laptop"
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
    # Some framework scripts call a bare ``python3``. On the user's PATH that
    # is the framework's own wrapper, which runs ``$HOME/.aitask/venv`` and so
    # cannot work under a session's scratch HOME; this one runs the pinned
    # interpreter instead.
    for name in ("python3", "python"):
        shim = bin_dir / name
        shim.write_text('#!/usr/bin/env bash\nexec "${AIT_PYTHON:?AIT_PYTHON is not set}" "$@"\n',
                        encoding="utf-8")
        shim.chmod(0o755)
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


def _build_board_locks(root: Path) -> None:
    """``base`` plus a local ``origin``, so the real ``./ait lock`` works
    offline. A recipe takes the lock with ``setup`` commands
    (``./ait lock --init``, ``./ait lock <id> --email ...``); without a remote
    the lock commands are silent no-ops and the board shows no lock."""
    _build_base(root)
    add_local_origin(root)
    # `ait lock` records `hostname` in the lock, and the board prints it. The
    # machine's real name is not an invented name; in this dataset the command
    # answers with a sample one. (Only here: other parts of the framework ask
    # Python for the host name, and a lock that disagreed with them would read
    # as held on another machine.)
    shim = root / STANDIN_BIN / "hostname"
    shim.write_text(f"#!/usr/bin/env bash\necho {LOCK_HOSTNAME}\n", encoding="utf-8")
    shim.chmod(0o755)


def _framework(root: Path, *argv: str) -> str:
    """Run a real framework command in the sample project, as a dataset's
    data preparation. The environment is the one a session's ``setup`` command
    gets: the sample person as git identity, a scratch ``HOME`` (the user's
    project registry and git config never reach the data) and the interpreter
    this tool runs on."""
    home = root / ".standin" / "home"
    home.mkdir(parents=True, exist_ok=True)
    env = {**os.environ,
           "PATH": f"{root / STANDIN_BIN}{os.pathsep}{os.environ.get('PATH', '')}",
           "HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config"),
           # The framework caches under XDG_CACHE_HOME (the artifact cache links
           # into the project). An inherited one would leave entries in the
           # user's cache that dangle once the sample project is removed.
           "XDG_CACHE_HOME": str(home / ".cache"),
           "AIT_PYTHON": os.environ.get("AIT_PYTHON") or sys.executable,
           # The built project stays a clean repository.
           "PYTHONDONTWRITEBYTECODE": "1",
           "GIT_AUTHOR_NAME": PERSON_NAME, "GIT_AUTHOR_EMAIL": PERSON_EMAIL,
           "GIT_COMMITTER_NAME": PERSON_NAME, "GIT_COMMITTER_EMAIL": PERSON_EMAIL,
           "GIT_AUTHOR_DATE": "2026-03-02T09:00:00", "GIT_COMMITTER_DATE": "2026-03-02T09:00:00",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    for name in ("TMUX", "TMUX_PANE", "AITASKS_TMUX_SOCKET", "AITASK_AGENT_STRING"):
        env.pop(name, None)
    try:
        done = subprocess.run(list(argv), cwd=root, env=env, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DatasetError(f"{' '.join(argv)} failed in the sample project: {exc}") from exc
    if done.returncode != 0:
        detail = " ".join((done.stderr or done.stdout).split())[:400]
        raise DatasetError(f"{' '.join(argv)} exited {done.returncode} in the sample "
                           f"project: {detail}")
    return done.stdout


#: The handle and label of the sample trail (``trails`` dataset).
TRAIL_HANDLE = "art:trail-checkout-launch"
TRAIL_NAME = "Checkout launch"
TRAIL_STAMP = "2026-03-02T09:00:00Z"


#: The tasks the trail's snapshot is taken over. The parent stands for its
#: children; it is an input too, or the TUI reports it as a new related task.
TRAIL_SCOPE = ("12", "14", "15", "9")


def _trail_snapshot(root: Path) -> tuple[str, list[str]]:
    """``(digest, input refs)`` from the framework's own gatherer, as the trail
    workflow records them. With the real digest over the real task files the
    TUI reports the trail as current; an invented digest would read as stale,
    and an input kind without a live resolver as "drift unavailable"."""
    out = _framework(root, "./.aitask-scripts/aitask_trail_gather.sh", "snapshot",
                     "--scope", "task", "--owner", "12", *TRAIL_SCOPE)
    digest, refs = "", []
    for line in out.splitlines():
        if line.startswith("DIGEST:"):
            digest = line.split(":", 1)[1].strip()
        elif line.startswith("INPUT:task_file|"):
            refs.append(line.rsplit("|", 1)[1].strip())
    if not digest or not refs:
        raise DatasetError(f"trail snapshot gave no usable digest / inputs: {out[:300]!r}")
    return digest, refs


def _trail_document(digest: str, input_refs: list[str]) -> dict:
    """One invented implementation trail over the ``base`` tasks: three waves
    that lead to the checkout page. Every timestamp is fixed."""
    def ref(task_id: str) -> str:
        return f"{PROJECT_NAME}#{task_id}"

    def entry(number, task_id, classification, status, rationale, confidence, outcome):
        return {"entry_id": f"e_{task_id}", "task": ref(task_id), "topic": ref("12"),
                "position": number, "classification": classification,
                "snapshot": {"status": status}, "rationale": rationale,
                "confidence": confidence, "expected_outcome": outcome,
                "evidence_refs": ["ev1"]}

    return {
        "schema_version": "1.1.0",
        "trail_id": "trail-checkout-launch",
        "title": "Checkout launch",
        "owner": ref("12"),
        "scope": {"kind": "task", "topics": [ref("12"), ref("14"), ref("15"), ref("9")]},
        "generation": {"generated_at": TRAIL_STAMP,
                       "generator": {"agent_string": "claudecode/opus5_5"},
                       "input_digest": digest,
                       "inputs": [{"ref": r, "kind": "task_file"} for r in input_refs]},
        "freshness": {"state": "current", "checked_at": TRAIL_STAMP},
        "narrative": {
            "problem_statement": (
                "The checkout page cannot ship while sign-in sends shoppers into a "
                "redirect loop, and its three parts build on each other."),
            "recommendation_summary": (
                "Fix the login redirect first, then build the checkout in order: cart "
                "summary, payment form, confirmation email. Image caching and search "
                "pagination can follow once checkout is live."),
        },
        "waves": [
            {"wave_id": "w1", "ordinal": 1, "title": "Unblock sign-in",
             "purpose": "Shoppers must be able to sign in before they can pay.",
             "why_now": "Every checkout test starts with a signed-in shopper.",
             "entries": [
                 entry(1, "14", "hard_prerequisite", "Ready",
                       "Checkout needs a working sign-in.", "high",
                       "Sign-in returns to the page the shopper came from."),
             ]},
            {"wave_id": "w2", "ordinal": 2, "title": "Build the checkout",
             "purpose": "The three parts of the checkout page, in dependency order.",
             "entries": [
                 entry(1, "12_1", "core", "Ready",
                       "The payment form reads its total from the cart summary.", "high",
                       "The cart summary shows items, shipping and total."),
                 entry(2, "12_2", "core", "Ready",
                       "Validation rules depend on the cart total.", "medium",
                       "Invalid card details are rejected before submit."),
                 entry(3, "12_3", "core", "Ready",
                       "The email is sent only after a valid payment.", "medium",
                       "Shoppers receive a confirmation email."),
             ]},
            {"wave_id": "w3", "ordinal": 3, "title": "Polish after launch",
             "purpose": "Improvements that are safer once checkout is live.",
             "entries": [
                 entry(1, "15", "preferred_predecessor", "Ready",
                       "Cached images make the cart summary load faster.", "medium",
                       "Product images load from the cache."),
                 entry(2, "9", "optional", "Ready",
                       "Independent of checkout; it only shares the catalog code.", "low",
                       "Search results are split into pages."),
             ]},
        ],
        "evidence": [{"evidence_id": "ev1", "source_type": "board_state", "ref": "board",
                      "observed_at": TRAIL_STAMP,
                      "summary": "Task dependencies and labels on the board."}],
    }


def _build_trails(root: Path) -> None:
    """``base`` plus one stored implementation trail, for ``ait trails`` and
    the board's By-Trail view.

    The trail is stored the way the framework stores one: the document is
    validated by the framework's own schema checker and written with the real
    ``ait artifact create`` (local backend, no remote), which commits the
    blob, the manifest and the owner task's ``artifacts:`` entry. Its member
    references use the project's own name, so the TUI draws them as local
    task cards."""
    _build_base(root)
    document = root / ".standin" / "trail_checkout_launch.json"
    document.write_text(json.dumps(_trail_document(*_trail_snapshot(root)), indent=2) + "\n",
                        encoding="utf-8")
    python = os.environ.get("AIT_PYTHON") or sys.executable
    _framework(root, python, ".aitask-scripts/lib/trail_schema.py", "validate", str(document))
    _framework(root, "./ait", "artifact", "create", "12", str(document),
               "--kind", "implementation_trail", "--handle", TRAIL_HANDLE,
               "--name", TRAIL_NAME)


#: The task the sample brainstorm session belongs to (``brainstorm`` dataset).
BRAINSTORM_TASK = "9"
#: The agent types ``ait brainstorm init`` refuses to run without.
BRAINSTORM_AGENT_TYPES = ("explorer", "comparator", "synthesizer", "initializer")


def _node_output(node_id: str, parents: list[str], description: str,
                 dimensions: dict[str, str], proposal: str) -> str:
    """One agent output file in the format the brainstorm apply step reads:
    a NODE_YAML block and a PROPOSAL block. ``created_at`` is given, so the
    apply step does not stamp the day the dataset was built."""
    lines = [f"node_id: {node_id}",
             "parents: [" + ", ".join(parents) + "]",
             f"description: {json.dumps(description)}",
             f"created_at: {json.dumps(FIXED_STAMP)}"]
    lines += [f"{key}: {json.dumps(value)}" for key, value in dimensions.items()]
    return ("--- NODE_YAML_START ---\n" + "\n".join(lines) + "\n--- NODE_YAML_END ---\n"
            "--- PROPOSAL_START ---\n" + proposal.strip() + "\n--- PROPOSAL_END ---\n"
            "--- NEW_DIMENSIONS ---\n" + ", ".join(dimensions) + "\n")


#: The operations that produced the nodes after the root, as the studio records
#: one when it starts: ``group -> (operation, agents, head at creation)``.
BRAINSTORM_GROUPS = {
    "explore_001": ("explore", ["explorer_001a", "explorer_001b"], "n000_init"),
    "synthesize_002": ("synthesize", ["synthesizer_002"], "n002_load_more"),
}

#: ``(apply verb, agent name, output text)`` for each node after the root:
#: two explorations of the seed proposal and one hybrid of the two.
BRAINSTORM_NODES = (
    ("apply-explorer", "explorer_001a", _node_output(
        "n001_numbered_pages", ["n000_init"],
        "Numbered pages with an offset query",
        {"requirements_navigation": "Shoppers can jump to any page of the results",
         "component_query": "OFFSET / LIMIT on the existing search query",
         "tradeoff_deep_pages": "Deep pages get slower as the offset grows"},
        """## Overview

Classic numbered pagination: 24 results per page, with page links under the
grid. The search query gains an offset and a limit.

## Why

It is what shoppers expect from a catalog, and every page has a stable URL
that can be shared.

## Risks

Deep pages are slow, and results shift between pages while stock changes.
""")),
    ("apply-explorer", "explorer_001b", _node_output(
        "n002_load_more", ["n000_init"],
        "Load more with a cursor",
        {"requirements_navigation": "Shoppers keep scrolling without a page reload",
         "component_query": "Keyset cursor on (relevance, product id)",
         "tradeoff_deep_pages": "Constant speed, but no way to jump to a page"},
        """## Overview

A "Load more" button appends the next 24 results. The query continues from a
cursor made of the last result's relevance and product id.

## Why

Every request costs the same, however far the shopper scrolls, and results
never repeat or skip while stock changes.

## Risks

No page numbers, so a position in the results cannot be shared as a link.
""")),
    ("apply-synthesizer", "synthesizer_002", _node_output(
        "n003_hybrid", ["n001_numbered_pages", "n002_load_more"],
        "Cursor pages with numbered links",
        {"requirements_navigation": "Numbered links for the first ten pages, then load more",
         "component_query": "Keyset cursor, with cached cursors for the numbered pages",
         "tradeoff_deep_pages": "Constant speed; direct jumps only within the first ten pages"},
        """## Overview

Keyset pagination underneath, numbered links on top: the first ten pages have
links backed by cached cursors, and later results come through "Load more".

## Why

It keeps shareable page links where shoppers use them and constant query cost
everywhere else.

## Risks

Cached cursors must be refreshed when the catalog is re-indexed.
""")),
)


def _build_brainstorm(root: Path) -> None:
    """``base`` plus the code-agent configuration and one brainstorm session
    with a small proposal graph, for ``ait brainstorm``.

    The session is created by the real ``ait brainstorm init`` (without
    ``--proposal-file``, so no agent is started) and each further node by the
    real apply step (``ait brainstorm apply-explorer`` / ``apply-synthesizer``)
    reading an output file in the agents' own format. Nothing here writes the
    node files directly. Afterwards the timestamps ``init`` stamped with the
    build day (the session's and the root node's ``created_at`` /
    ``updated_at``) are rewritten to the fixed sample date, so the picture
    does not depend on the day it is taken."""
    write_project_shell(root)
    write_tasks(root, BASE_COLUMNS, BASE_TASKS)
    write_agent_metadata(root)
    config_path = root / "aitasks" / "metadata" / "codeagent_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    for agent_type in BRAINSTORM_AGENT_TYPES:
        config["defaults"][f"brainstorm-{agent_type}"] = config["defaults"]["pick"]
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    write_standin(root)
    with open(root / ".gitignore", "a", encoding="utf-8") as fh:
        fh.write(".aitask-crews/\n")
    _git_commit_all(root, "Sample project")
    _framework(root, "./ait", "brainstorm", "init", BRAINSTORM_TASK)
    session = root / ".aitask-crews" / f"crew-brainstorm-{BRAINSTORM_TASK}"
    if not (session / "br_session.yaml").is_file():
        raise DatasetError(f"ait brainstorm init left no session at {session}")
    _record_brainstorm_groups(session)
    for verb, agent, text in BRAINSTORM_NODES:
        (session / f"{agent}_output.md").write_text(text, encoding="utf-8")
        _framework(root, "./ait", "brainstorm", verb, BRAINSTORM_TASK, agent)
    _pin_brainstorm_dates(session)


def _record_brainstorm_groups(session: Path) -> None:
    """The operation records an agent run starts from (``br_groups.yaml``,
    status ``Waiting``). Starting an operation in the studio writes these and
    launches its agents; here only the record is written, and the apply step
    then completes it (agents, created nodes, status) as it does for a real
    run. Without it a node reads "Generated by: ?"."""
    import yaml

    path = session / "br_groups.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    for name, (operation, agents, head) in BRAINSTORM_GROUPS.items():
        data["groups"][name] = {"operation": operation, "agents": list(agents),
                                "status": "Waiting", "created_at": FIXED_STAMP,
                                "head_at_creation": head, "nodes_created": [],
                                "subgraph": "_umbrella"}
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _pin_brainstorm_dates(session: Path) -> None:
    """Set every ``created_at`` / ``updated_at`` key in the session's files to
    the fixed sample date. The files are loaded and written back as YAML: the
    session file quotes the task text, which has lines of the same shape."""
    import yaml

    def pin(value):
        if isinstance(value, dict):
            return {key: FIXED_STAMP if key in ("created_at", "updated_at") else pin(item)
                    for key, item in value.items()}
        if isinstance(value, list):
            return [pin(item) for item in value]
        return value

    for path in [session / "br_session.yaml", session / "br_groups.yaml",
                 *sorted((session / "br_nodes").glob("*.yaml"))]:
        if path.is_file():
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            path.write_text(yaml.safe_dump(pin(data), sort_keys=False, allow_unicode=True),
                            encoding="utf-8")


#: name -> builder(root). A builder creates ``root`` and everything in it.
DATASETS: dict[str, Callable[[Path], None]] = {
    "base": _build_base,
    "agents": _build_agents,
    "board_locks": _build_board_locks,
    "trails": _build_trails,
    "brainstorm": _build_brainstorm,
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
