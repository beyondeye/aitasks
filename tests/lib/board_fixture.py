"""Shared board fixture harness — boot `KanbanApp` against a temp task tree (t1354_1).

Why this exists
---------------
The board TUI test modules used to `os.chdir(REPO_ROOT)` in `setUpClass` and
boot the real `KanbanApp` against the **live** `aitasks/` tree (213 parent cards
and growing). Measured on this checkout, boot + one `pilot.pause()`:

    live tree,   cwd=REPO_ROOT                        2.437s   (213 cards)
    fixture,     cwd=REPO_ROOT, absolute TASK_DIR     0.620s   (8 cards)
    fixture,     cwd=tree,      relative TASK_DIR     0.190s   (8 cards)

so a fixture tree entered with `cwd=tree` is ~12.8x cheaper per boot. That is
the mode this harness implements.

Two seams, and when to use which
--------------------------------
* **boot mode** — `load_board_module()`. Imports `aitask_board.py` under a
  *unique synthetic module name* with `TASK_DIR` set, so the module-load
  constants (`TASKS_DIR` and everything derived from it: `METADATA_FILE`,
  `TASK_TYPES_FILE`, `GATES_REGISTRY_FILE`, `USERCONFIG_FILE`, `EMAILS_FILE`)
  resolve under the fixture. Required whenever a test constructs `KanbanApp`.
  The synthetic name is what keeps the *canonical* `aitask_board` module
  untouched — `test_board_movement.IsolationNegativeControlTests` asserts
  `aitask_board.TASKS_DIR == Path("aitasks")`, and that stays true.
* **patch mode** — `mock.patch.object(aitask_board, "TASKS_DIR", ...)`. Cheaper,
  but it does **not** update the derived constants above, so it is valid only
  for non-boot tests that touch `TASKS_DIR` alone. See
  `tests/test_board_persistence_seam.py`'s module docstring.

The TASK_DIR invariant (do not "fix" this to an absolute path)
--------------------------------------------------------------
`TASK_DIR` must be the **relative literal** ``"aitasks"`` with cwd inside the
fixture tree. `TaskManager.is_modified` compares `str(task.filepath)` against
`git status --porcelain` paths like `aitasks/tN.md`. Measured: with the relative
value a dirtied fixture task is reported (`['t9000_fixture.md']`); with an
absolute `TASK_DIR` git still reports `aitasks/t9000_fixture.md` but
`is_modified` returns `[]` — every modified marker silently disappears and any
test asserting on one passes vacuously. `load_board_module` rejects an absolute
value for that reason.

cwd-relative dependencies (why cwd=tree is safe, and what it costs)
-------------------------------------------------------------------
These board paths resolve relative to the process cwd, so under `cwd=tree` they
point at files that do not exist:

    DATA_WORKTREE            aitask_board.py:71   -> _task_git_cmd/refresh_git_status
    ./.aitask-scripts/aitask_lock.sh --list       :1084  refresh_lock_map
    ARTIFACT_SCRIPT                               :490   load_trail_blob
    TRAIL_GATHER_SCRIPT                           :491   run_trail_drift/_trail_versions
    CODEAGENT_SCRIPT / CREATE_SCRIPT              :74/:75
    BRAINSTORM_TUI_SCRIPT                         :76
    agent_command_screen.py:999   ./.aitask-scripts/aitask_skill_rerender.sh
    sync_action_runner.py:76      ./.aitask-scripts/aitask_sync.sh

Every one is wrapped in `except (..., FileNotFoundError, OSError)`, so they
degrade silently rather than raise. **That silence is a hazard**: a test can
reach a fallback branch and pass for the wrong reason. Measured per phase under
cwd=tree:

    boot (on_mount -> refresh_board(refresh_locks=True))
        git -C .aitask-data status --porcelain -- aitasks/   (works)
        ./.aitask-scripts/aitask_lock.sh --list              (ABSENT -> degrades)
    By-Trail entry + local refresh
        git -C .aitask-data status --porcelain -- aitasks/   (works)

So **every** board boot on this harness runs with an empty `lock_map` — the lock
helper does not exist under the fixture cwd and is swallowed. That is the
deliberate trade (staging it back costs ~0.43s per boot), and
`FixtureCwdDependencyTests` in test_board_bytrail_view.py pins both the spawn
set *and* the empty-`lock_map` consequence, per phase, so a test that ever needs
real lock state fails loudly instead of quietly asserting against an empty map.

A test that exercises any other branch above must stub its helper explicitly
(`patch.object` / `patch("subprocess.run")`) **and** assert the intended verb was
reached, so an absent script cannot masquerade as a pass.

Deliberately NOT symlinking `.aitask-scripts` into the fixture tree: that would
re-enable the real `aitask_lock.sh --list` subprocess and hand back the 0.43s
that cwd=tree buys.

Fixture contract
----------------
`project_config.yaml` carrying `project.name` is **required** for any trail
test. `load_local_project_name` (aitask_board.py:544) returns `""` when it is
missing, `trail_ref_to_local_id` then returns `None`, and every `aitasks#<id>`
trail member renders as an unresolvable *cross-repo ghost*. Measured with a
trail doc referencing `aitasks#9000` and `aitasks#9000_1`: without the file
0 `TrailTaskCard` / 2 ghosts; with it 2 / 0.

`metadata/gates.yaml` is staged from the shipped reference for the same reason
(t1354_2). `GATES_REGISTRY_FILE` (aitask_board.py:77) derives from `TASKS_DIR`,
and a tree without it does not merely lose gate cosmetics — it **reclassifies**.
Measured: a task declaring `gates: [review_approved]` with a pending human run
lands in the ``agent`` group instead of ``human``, its In-Flight card loses the
``[s sign-off]`` op, and `unresolved_local_deps` fails closed and reports a
gate-satisfied upstream as still blocking. Nothing raises. Pass
`gates_registry=False` only to prove that dependence.

Every fixture task carries at least one non-board metadata key. A task whose
keys are a subset of `BOARD_KEYS` is dropped by `TaskManager._is_phantom_stub`
(aitask_board.py:921), which would load zero tasks and pass every assertion
vacuously.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m unittest tests.test_board_fixture_harness -v
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_BOARD = REPO_ROOT / ".aitask-scripts" / "board"
_LIB = REPO_ROOT / ".aitask-scripts" / "lib"
for _p in (str(_BOARD), str(_LIB)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from task_yaml import serialize_frontmatter  # noqa: E402

BOARD_PATH = _BOARD / "aitask_board.py"

#: Canonical shipped gate registry (t1147). Staged into every fixture tree as
#: `metadata/gates.yaml`, because `GATES_REGISTRY_FILE` (aitask_board.py:77) is
#: derived from `TASKS_DIR` and a tree without it does NOT merely lose gate
#: cosmetics — it silently reclassifies. Measured on a tree without it: a task
#: declaring `gates: [review_approved]` with a pending human run lands in the
#: ``agent`` group instead of ``human``, its card loses the ``[s sign-off]`` op,
#: and `unresolved_local_deps` fails closed and reports the upstream as
#: unresolved. Same trap shape as the `project_config.yaml` one above: nothing
#: raises, the assertions just quietly measure the degraded branch.
#: Read by path (not cwd), so it resolves from inside the fixture tree.
GATES_REFERENCE = REPO_ROOT / ".aitask-scripts" / "gates_reference.yaml"

#: The only `TASK_DIR` value this harness accepts — see the module docstring.
TASK_DIR_VALUE = "aitasks"

# --- Fixture vocabulary ------------------------------------------------------

COLUMNS = [
    {"id": "c0", "title": "Col 0", "color": "#FF5555"},
    {"id": "c1", "title": "Col 1", "color": "#50FA7B"},
    {"id": "c2", "title": "Col 2", "color": "#BD93F9"},
    {"id": "c3", "title": "Col 3", "color": "#8BE9FD"},
    {"id": "c4", "title": "Col 4", "color": "#FFB86C"},
]
COLUMN_ORDER = [c["id"] for c in COLUMNS]

# Non-board frontmatter keys. At least one is REQUIRED: TaskManager._is_phantom_stub
# drops any task whose keys are a subset of BOARD_KEYS, so a fixture carrying only
# boardcol/boardidx would load ZERO tasks and every scenario would pass vacuously.
_META_ORDER = ["priority", "effort", "issue_type", "status"]
_META_BASE = {
    "priority": "medium",
    "effort": "low",
    "issue_type": "chore",
    "status": "Ready",
}


def fixture_name(i: int) -> str:
    return f"t{9000 + i}_fixture.md"


def _fixture_body(i: int) -> str:
    return f"\n## Context\n\nSynthetic fixture task {i}.\n\n## Notes\n\nBody line {i}.\n"


def _fixture_text(i: int, col: str, idx: int) -> str:
    """Build a task file through the canonical serializer.

    Hand-written YAML would be re-normalized by `Task.save()` on the very first
    write, so the byte differ would report a change caused by formatting rather
    than by the move. Board keys are emitted last here, which is also where
    `serialize_frontmatter` puts them on re-save, making an unchanged-value write
    byte-identical.
    """
    meta = dict(_META_BASE)
    meta["boardcol"] = col
    meta["boardidx"] = idx
    return serialize_frontmatter(meta, _fixture_body(i), list(_META_ORDER))


def expected_nonboard(i: int) -> tuple[dict, str]:
    return dict(_META_BASE), _fixture_body(i)


_GIT_ENV = {
    "GIT_AUTHOR_NAME": "aitask test",
    "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "aitask test",
    "GIT_COMMITTER_EMAIL": "test@example.invalid",
}

PROJECT_CONFIG_TEXT = "project:\n  name: aitasks\n"


# --- Declarative topology ----------------------------------------------------


@dataclasses.dataclass(frozen=True)
class FixtureTask:
    """One task file in a fixture tree.

    `task_id` is the bare id the board resolves refs against: ``"9000"`` for a
    parent (written to ``<tasks>/t9000_<slug>.md``) or ``"9000_1"`` for a child
    (written to ``<tasks>/t9000/t9000_1_<slug>.md`` — the path
    `TaskManager.load_child_tasks` globs).

    `filename` overrides the derived name; it is how a deliberately *numberless*
    file is placed. Such a file MUST still be given a `col`/`idx`, otherwise it
    lands in the ``unordered`` column instead of the one under test and the
    production filename filter (`action_work_report`, aitask_board.py:7271)
    never runs against it.
    """

    task_id: str = ""
    col: str = "c0"
    idx: int = 0
    status: str = "Ready"
    filename: str = ""
    slug: str = "fixture"
    extra: dict | None = None

    def path_in(self, tasks_dir: Path) -> Path:
        if self.filename:
            return tasks_dir / self.filename
        if "_" in self.task_id:
            parent = self.task_id.split("_", 1)[0]
            return tasks_dir / f"t{parent}" / f"t{self.task_id}_{self.slug}.md"
        return tasks_dir / f"t{self.task_id}_{self.slug}.md"

    def text(self) -> str:
        meta = dict(_META_BASE)
        meta["status"] = self.status
        meta.update(self.extra or {})
        meta["boardcol"] = self.col
        meta["boardidx"] = self.idx
        label = self.task_id or (self.filename or "anonymous")
        body = f"\n## Context\n\nSynthetic fixture task {label}.\n"
        return serialize_frontmatter(meta, body, list(_META_ORDER))


#: Default topology. Five parents spanning every column, two children under
#: t9000, and one deliberately numberless file parked in ``c0`` so the
#: `action_work_report` filename filter is exercised rather than merely present.
DEFAULT_TOPOLOGY = (
    FixtureTask(task_id="9000", col="c0", idx=10, status="Ready", slug="parent"),
    FixtureTask(task_id="9001", col="c1", idx=10, status="Implementing", slug="alpha"),
    FixtureTask(task_id="9002", col="c2", idx=10, status="Done", slug="beta"),
    FixtureTask(task_id="9003", col="c3", idx=10, slug="gamma"),
    FixtureTask(task_id="9004", col="c4", idx=10, slug="delta"),
    FixtureTask(task_id="9000_1", col="c0", idx=20, slug="childone"),
    FixtureTask(task_id="9000_2", col="c1", idx=20, slug="childtwo"),
    FixtureTask(filename="t_unparseable.md", col="c0", idx=99),
)

#: Richer topology for modules whose assertions need metadata the default tree
#: does not carry: a **second** topic lane, `issue:`-bearing tasks for the git
#: view-set, and a `depends:` edge.
#:
#: `DEFAULT_TOPOLOGY` is deliberately NOT extended to cover these — it is pinned
#: by two green files (`test_board_work_report` asserts exact `c0` counts, and
#: `test_board_movement` byte-differs the file set it produces), so widening it
#: would break both silently. Additive names only.
#:
#: Two lanes, because `_build_topic_lanes` only forms a lane at **>=2 members**
#: sharing a `topic_key` (aitask_board.py:441):
#:   * ``"9000"`` — the parent plus its two children. Children need no `anchor:`;
#:     `topic_key` falls back to the parent id for them (topic_semantics.py:69).
#:   * ``"9002"`` — an explicit `anchor:` group: two followups pointing at 9002.
#: t9001 / t9004 / the numberless file stay singletons (ungrouped) on purpose,
#: so "grouped" and "ungrouped" are both represented.
RICH_TOPOLOGY = (
    FixtureTask(task_id="9000", col="c0", idx=10, slug="parent",
                extra={"issue": "https://example.invalid/issues/1"}),
    FixtureTask(task_id="9000_1", col="c0", idx=20, slug="childone"),
    FixtureTask(task_id="9000_2", col="c1", idx=20, slug="childtwo"),
    FixtureTask(task_id="9002", col="c2", idx=10, status="Done", slug="beta"),
    FixtureTask(task_id="9003", col="c3", idx=10, slug="gamma",
                extra={"anchor": 9002,
                       "issue": "https://example.invalid/issues/2"}),
    FixtureTask(task_id="9005", col="c2", idx=20, slug="epsilon",
                extra={"anchor": 9002}),
    FixtureTask(task_id="9001", col="c1", idx=10, status="Implementing", slug="alpha"),
    FixtureTask(task_id="9004", col="c4", idx=10, slug="delta",
                extra={"depends": [9000]}),
    FixtureTask(filename="t_unparseable.md", col="c0", idx=99),
)


#: A slug long enough that the rendered card title wraps to several rows even in
#: a ~95-cell-wide column. Measured under the Tall|Side two-column layout at
#: width 200: card height 13 rows, against viewports of 5 (term height 12) and
#: 11 (term height 18) — comfortably taller than both, which is what
#: "a card exceeds the viewport" and "no card is fully visible" need. 28 words
#: keeps the filename at 194 bytes, well inside the 255-byte component limit
#: (40 words overflows it and `write_text` raises ENAMETOOLONG).
_TALL_SLUG = "_".join(f"word{i}" for i in range(28))


def wide_topology(n_parents: int, *, with_children: bool = False,
                  tall_titles: bool = False):
    """``n_parents`` parent tasks spread round-robin across the fixture columns.

    For tests whose property depends on card **volume** rather than on any
    particular task — a column tall enough to scroll, a board with more cards
    than fit on screen. Those tests used to `skipTest` when the live tree was
    too sparse; on a fixture the tree must *reproduce* the volume instead, or
    the assertion silently becomes vacuous (a skip at least stayed visible).

    `with_children` adds two children under the first parent for the cases that
    also need a parent/child relationship.

    `tall_titles` additionally reproduces card **height**. Real task titles are
    long and wrap; a default `wide0`-style slug renders a 5-row card, which is
    shorter than a short viewport and quietly breaks the two scroll assertions
    that require a card taller than the pane. Volume alone is not the whole
    shape — see `_TALL_SLUG`.
    """
    slug_for = (lambda i: _TALL_SLUG) if tall_titles else (lambda i: f"wide{i}")
    tasks = [
        FixtureTask(task_id=str(9000 + i),
                    col=COLUMN_ORDER[i % len(COLUMN_ORDER)],
                    idx=(i + 1) * 10,
                    slug=slug_for(i))
        for i in range(n_parents)
    ]
    if with_children:
        tasks += [
            FixtureTask(task_id="9000_1", col=COLUMN_ORDER[0], idx=15, slug="childone"),
            FixtureTask(task_id="9000_2", col=COLUMN_ORDER[0], idx=16, slug="childtwo"),
        ]
    return tuple(tasks)


# --- Tree construction -------------------------------------------------------


def _write_common(tasks: Path, *, settings=None, project_name: str | None,
                  gates_registry: bool = False) -> None:
    (tasks / "metadata").mkdir(parents=True, exist_ok=True)
    (tasks / "metadata" / "board_config.json").write_text(
        json.dumps({"columns": COLUMNS, "column_order": COLUMN_ORDER}, indent=2) + "\n",
        encoding="utf-8",
    )
    local = {
        "settings": {
            # The auto-refresh timer must never fire mid-benchmark, and a collapsed
            # column would make lateral ping-pong skip past its neighbour.
            "auto_refresh_minutes": 0,
            "collapsed_columns": [],
            "sync_on_refresh": False,
            **(settings or {}),
        }
    }
    (tasks / "metadata" / "board_config.local.json").write_text(
        json.dumps(local, indent=2) + "\n", encoding="utf-8"
    )
    if project_name is not None:
        (tasks / "metadata" / "project_config.yaml").write_text(
            f"project:\n  name: {project_name}\n", encoding="utf-8"
        )
    if gates_registry:
        (tasks / "metadata" / "gates.yaml").write_text(
            GATES_REFERENCE.read_text(encoding="utf-8"), encoding="utf-8"
        )


def _git_init(git_root: Path) -> None:
    env = {**os.environ, **_GIT_ENV}
    subprocess.run(["git", "init", "-q", "-b", "main", "."], cwd=git_root, env=env, check=True)
    subprocess.run(["git", "add", "-A", "."], cwd=git_root, env=env, check=True)
    subprocess.run(
        ["git", "commit", "-q", "--no-verify", "-m", "fixture"],
        cwd=git_root, env=env, check=True,
    )


def _layout(tree: Path, branch_mode: bool):
    if branch_mode:
        tasks = tree / ".aitask-data" / "aitasks"
        return tasks, tree / ".aitask-data"
    return tree / "aitasks", tree


def build_tree(root: Path, cards, *, branch_mode: bool = True, settings=None,
               project_name: str | None = None) -> Path:
    """Materialise a synthetic TASK_DIR and return the tree root (the child's cwd).

    `cards` is a list of (index, col_id, board_idx). `branch_mode=True` reproduces
    production: real files under `.aitask-data/aitasks`, a git repo there, and an
    `aitasks` symlink at the tree root, so `_task_git_cmd()` yields
    `git -C .aitask-data`. `branch_mode=False` is the legacy topology used only by
    the git-cost comparison.

    `project_name` defaults to ``None`` (no `project_config.yaml`) so the byte
    differ in `test_board_movement` sees exactly the file set it always saw.
    Trail-resolving callers must pass it — see the module docstring.
    """
    tree = root / "tree"
    tasks, git_root = _layout(tree, branch_mode)
    _write_common(tasks, settings=settings, project_name=project_name)

    for i, col, idx in cards:
        (tasks / fixture_name(i)).write_text(_fixture_text(i, col, idx), encoding="utf-8")

    if branch_mode:
        (tree / "aitasks").symlink_to(Path(".aitask-data") / "aitasks")

    _git_init(git_root)
    return tree


def build_fixture_tree(root: Path, tasks_spec=DEFAULT_TOPOLOGY, *,
                       branch_mode: bool = True, settings=None,
                       project_name: str | None = "aitasks",
                       gates_registry: bool = True) -> Path:
    """Materialise a declarative fixture tree and return its root.

    Unlike `build_tree` this writes `project_config.yaml` and the shipped
    `gates.yaml` by default, and supports child tasks, because the board
    surfaces it feeds (By-Trail, work report, In-Flight) resolve `aitasks#<id>`
    refs, glob `t*/t*_*.md`, and classify gates by registry `type`.

    `gates_registry=False` exists for the negative control that proves the
    registry is load-bearing rather than decorative — see `GATES_REFERENCE`.
    """
    tree = root / "tree"
    tasks, git_root = _layout(tree, branch_mode)
    _write_common(tasks, settings=settings, project_name=project_name,
                  gates_registry=gates_registry)

    for spec in tasks_spec:
        path = spec.path_in(tasks)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(spec.text(), encoding="utf-8")

    if branch_mode:
        (tree / "aitasks").symlink_to(Path(".aitask-data") / "aitasks")

    _git_init(git_root)
    return tree


# --- Board module loading ----------------------------------------------------


def load_board_module(task_dir=TASK_DIR_VALUE, *, tag: str = "fixture",
                      allow_absolute: bool = False):
    """Import `aitask_board.py` under a unique synthetic name, bound to `task_dir`.

    The synthetic name is what makes this safe in the one-interpreter suite: the
    canonical `aitask_board` module keeps `TASKS_DIR == Path("aitasks")`, which
    `test_board_movement.IsolationNegativeControlTests` pins.

    `allow_absolute` exists only for tests that deliberately probe the broken
    absolute-`TASK_DIR` behaviour (the modified-marker negative control).
    """
    task_dir = str(task_dir)
    if os.path.isabs(task_dir) and not allow_absolute:
        raise ValueError(
            "board_fixture: TASK_DIR must be the relative literal "
            f"{TASK_DIR_VALUE!r} with cwd inside the fixture tree; got absolute "
            f"{task_dir!r}. An absolute TASK_DIR silently breaks "
            "TaskManager.is_modified — git reports 'aitasks/tN.md' while "
            "Task.filepath is absolute, so no card renders its modified marker. "
            "See the board_fixture module docstring."
        )
    if not os.path.isabs(task_dir) and not (Path.cwd() / task_dir).exists():
        raise ValueError(
            f"board_fixture: {task_dir!r} does not exist under cwd {os.getcwd()!r} — "
            "chdir into the fixture tree before loading the board module "
            "(use enter_fixture_tree / FixtureBoardTestBase)."
        )

    module_name = f"aitask_board_fixture_{tag}_{id(task_dir)}"
    previous = os.environ.get("TASK_DIR")
    os.environ["TASK_DIR"] = task_dir
    try:
        spec = importlib.util.spec_from_file_location(module_name, BOARD_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        if previous is None:
            os.environ.pop("TASK_DIR", None)
        else:
            os.environ["TASK_DIR"] = previous


def enter_fixture_tree(add_cleanup, *, tasks_spec=DEFAULT_TOPOLOGY, tag: str = "fixture",
                       branch_mode: bool = True, settings=None,
                       project_name: str | None = "aitasks", load_module: bool = True,
                       gates_registry: bool = True):
    """Build a fixture tree, chdir into it, and load a board module bound to it.

    `add_cleanup` is `cls.addClassCleanup` or `self.addCleanup`. **Registration
    order is load-bearing:** cleanups run LIFO, so the tmpdir removal is
    registered FIRST and the cwd restore SECOND — that way cwd is restored
    *before* the tree is deleted. Both are registered immediately after the
    corresponding acquisition, so a failure anywhere below (including inside
    `load_board_module`) still restores cwd and removes the tree rather than
    contaminating the rest of the single-process suite.

    Returns `(tree, module)`; `module` is None when `load_module=False`.
    """
    tmp = tempfile.TemporaryDirectory(prefix="aitask_board_fixture_")
    add_cleanup(tmp.cleanup)                     # registered 1st -> runs LAST
    tree = build_fixture_tree(Path(tmp.name), tasks_spec, branch_mode=branch_mode,
                              settings=settings, project_name=project_name,
                              gates_registry=gates_registry)
    original_cwd = os.getcwd()
    os.chdir(tree)
    add_cleanup(os.chdir, original_cwd)          # registered 2nd -> runs FIRST
    module = load_board_module(TASK_DIR_VALUE, tag=tag) if load_module else None
    return tree, module


class FixtureBoardTestBase:
    """Mixin: class-level fixture tree + board module, entered once per class.

    Mix into a `unittest.TestCase`. Override `FIXTURE_TASKS` to reshape the tree.
    `cls.ab` is the board module (named to match the migrated modules' idiom) and
    `cls.tree` is the tree root, which is also the process cwd for the class.
    """

    FIXTURE_TASKS = DEFAULT_TOPOLOGY
    FIXTURE_SETTINGS = None
    FIXTURE_PROJECT_NAME = "aitasks"
    FIXTURE_GATES_REGISTRY = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tree, cls.ab = enter_fixture_tree(
            cls.addClassCleanup,
            tasks_spec=cls.FIXTURE_TASKS,
            tag=cls.__name__,
            settings=cls.FIXTURE_SETTINGS,
            project_name=cls.FIXTURE_PROJECT_NAME,
            gates_registry=cls.FIXTURE_GATES_REGISTRY,
        )

    @property
    def tasks_dir(self) -> Path:
        return self.tree / "aitasks"


class PristineTreeMixin:
    """Restore the fixture tree's task files AND board config before every test.

    `FixtureBoardTestBase` builds ONE tree per class, so a movement test mutates
    the tree the next test starts from — positions drift and a later move can
    early-return, turning its assertions vacuous. Restoring the committed bytes
    also restores `git status` cleanliness, which the marking oracle depends on.

    **`metadata/board_config*.json` is part of the tree**, not a separate concern
    — `snapshot()` below has always treated it that way, and this mixin was the
    outlier until t1243_10. Two independent leaks made restoring it mandatory
    rather than tidy, and both are silently self-concealing:

    - a class that mutates COLUMNS (add / delete / merge) leaks
      `board_config.json`. With `c1` already dropped from the config,
      `merge_columns` refuses it as `unknown_column` and writes nothing, while a
      "source column was removed" assertion still passes — because the *previous*
      test removed it.
    - a class that collapses a group or a column leaks
      `board_config.local.json`, because collapse state persists (t1243_10). A
      later test asserting `collapsed_groups == set()` then fails, or worse boots
      with members unmounted and quietly stops testing what it names.

    Restoring is a no-op when nothing changed, so a class that touches no config
    pays only the byte comparison. Mix in AFTER `FixtureBoardTestBase` and call
    `cls._snapshot_pristine()` at the end of `setUpClass`, once the tree exists.
    """

    @classmethod
    def _snapshot_pristine(cls):
        base = (cls.tree / ".aitask-data" / "aitasks").resolve()
        cls._pristine = {p: p.read_bytes() for p in sorted(base.rglob("*.md"))}
        assert cls._pristine, "fixture tree produced no task files"
        meta = base / "metadata"
        cls._pristine.update({p: p.read_bytes()
                              for p in sorted(meta.glob("board_config*.json"))})
        assert any(p.name.startswith("board_config") for p in cls._pristine), \
            "fixture tree produced no board config"

    def setUp(self):
        super().setUp()
        for path, data in self._pristine.items():
            if path.read_bytes() != data:
                path.write_bytes(data)


# --- Differ (shared with the movement characterization harness) --------------
#
# An explicit allowlist, never the whole tree. Snapshotting the tree root would
# pick up `.git/index` (git status refreshes its stat cache) and any IPC file,
# making the exact changed-path set noisy and platform-dependent. IPC lives
# outside the tree by construction; this allowlist covers only the logical task
# and board-config files.


def snapshot(tree: Path) -> dict[str, str]:
    base = tree / "aitasks"  # traverses the symlink in branch mode
    out: dict[str, str] = {}
    paths = list(base.rglob("*.md")) + list((base / "metadata").glob("board_config*.json"))
    for p in sorted(paths):
        rel = p.relative_to(tree).as_posix()
        out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def diff_snapshots(before: dict, after: dict) -> dict[str, set]:
    return {
        "changed": {k for k in before.keys() & after.keys() if before[k] != after[k]},
        "added": set(after) - set(before),
        "removed": set(before) - set(after),
    }
