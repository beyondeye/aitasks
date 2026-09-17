"""Self-tests for the shared board fixture harness (t1354_1).

The harness in `tests/lib/board_fixture.py` is load-bearing: t1354_2 migrates
the remaining live-tree board modules onto it, so its invariants are pinned
here rather than discovered later.

Each guard ships with the negative control that proves it discriminates — a
guard whose negative control also passes is testing nothing.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m unittest tests.test_board_fixture_harness -v
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(REPO_ROOT / "tests" / "lib"),
           str(REPO_ROOT / ".aitask-scripts"),
           str(REPO_ROOT / ".aitask-scripts" / "board"),
           str(REPO_ROOT / ".aitask-scripts" / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import board_fixture as bf  # noqa: E402


class TaskDirInvariantTests(unittest.TestCase):
    """TASK_DIR must be the relative literal, and the modified marker proves why."""

    def _tree(self, **kw):
        tmp = tempfile.TemporaryDirectory(prefix="bf_inv_")
        self.addCleanup(tmp.cleanup)
        return bf.build_fixture_tree(Path(tmp.name), **kw)

    def _dirty_first_task(self, tree: Path) -> str:
        """Edit a committed fixture task; return its filename."""
        tasks = tree / ".aitask-data" / "aitasks"
        path = next(p for p in sorted(tasks.glob("t9*.md")))
        path.write_text(path.read_text(encoding="utf-8") + "\nedited\n", encoding="utf-8")
        return path.name

    def _modified_hits(self, tree: Path, task_dir, *, allow_absolute=False):
        original = os.getcwd()
        os.chdir(tree)
        self.addCleanup(os.chdir, original)
        ab = bf.load_board_module(task_dir, tag="inv", allow_absolute=allow_absolute)
        manager = ab.make_task_manager()
        manager.refresh_git_status()
        return (sorted(manager.modified_files),
                sorted(t.filename for t in manager.task_datas.values()
                       if manager.is_modified(t)))

    def test_relative_task_dir_reports_the_modified_marker(self):
        tree = self._tree()
        name = self._dirty_first_task(tree)
        git_seen, hits = self._modified_hits(tree, bf.TASK_DIR_VALUE)
        self.assertEqual(git_seen, [f"aitasks/{name}"])
        self.assertEqual(hits, [name],
                         "relative TASK_DIR must let is_modified match git's paths")

    def test_absolute_task_dir_silently_loses_the_modified_marker(self):
        """Negative control for the guard above.

        This is the exact failure the harness's absolute-path rejection exists
        to prevent: git still reports the dirty file, but `is_modified` matches
        nothing because `Task.filepath` is absolute while porcelain paths are
        repo-relative. If this test ever starts finding hits, the relative-path
        invariant has become unnecessary and both tests should be revisited.
        """
        tree = self._tree()
        name = self._dirty_first_task(tree)
        git_seen, hits = self._modified_hits(
            tree, str(tree / "aitasks"), allow_absolute=True)
        self.assertEqual(git_seen, [f"aitasks/{name}"],
                         "git must still see the dirty file")
        self.assertEqual(hits, [],
                         "an absolute TASK_DIR is expected to lose every modified marker")

    def test_absolute_task_dir_is_rejected_by_default(self):
        tree = self._tree()
        original = os.getcwd()
        os.chdir(tree)
        self.addCleanup(os.chdir, original)
        with self.assertRaises(ValueError) as ctx:
            bf.load_board_module(str(tree / "aitasks"), tag="reject")
        self.assertIn("relative literal", str(ctx.exception))

    def test_missing_tree_under_cwd_is_rejected(self):
        """Forgetting the chdir must fail loudly, not boot against the real repo."""
        original = os.getcwd()
        tmp = tempfile.TemporaryDirectory(prefix="bf_nocwd_")
        self.addCleanup(tmp.cleanup)
        os.chdir(tmp.name)
        self.addCleanup(os.chdir, original)
        with self.assertRaises(ValueError) as ctx:
            bf.load_board_module(tag="nocwd")
        self.assertIn("does not exist under cwd", str(ctx.exception))


class CleanupOrderingTests(unittest.TestCase):
    """A failure after the chdir must still restore cwd AND remove the tree.

    `addClassCleanup` runs LIFO, so `enter_fixture_tree` registers the tmpdir
    removal first and the cwd restore second. A green setUpClass cannot prove
    that ordering — only a forced failure can.
    """

    def _run_case(self, boom: bool):
        recorded = {}
        outer_cwd = os.getcwd()

        class Case(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                real_load = bf.load_board_module

                def exploding(*args, **kwargs):
                    recorded["cwd_at_failure"] = os.getcwd()
                    raise RuntimeError("forced failure after chdir")

                bf.load_board_module = exploding if boom else real_load
                try:
                    tree, _ = bf.enter_fixture_tree(cls.addClassCleanup, tag="cleanup")
                    recorded["tree"] = tree
                finally:
                    bf.load_board_module = real_load

            def test_noop(self):
                pass

        suite = unittest.TestLoader().loadTestsFromTestCase(Case)
        with open(os.devnull, "w") as devnull:
            result = unittest.TextTestRunner(stream=devnull).run(suite)
        return recorded, result, outer_cwd

    def test_forced_failure_after_chdir_restores_cwd_and_removes_tree(self):
        recorded, result, outer_cwd = self._run_case(boom=True)
        self.assertTrue(result.errors, "the forced failure must surface as an error")
        # The failure really did happen inside the fixture tree...
        self.assertNotEqual(recorded["cwd_at_failure"], outer_cwd)
        tree = Path(recorded["cwd_at_failure"])
        # ... and the cleanups still ran, in the right order.
        self.assertEqual(os.getcwd(), outer_cwd,
                         "cwd must be restored even when setUpClass raises")
        self.assertFalse(tree.exists(), "the fixture tree must be removed")

    def test_successful_setup_also_restores_cwd_and_removes_tree(self):
        recorded, result, outer_cwd = self._run_case(boom=False)
        self.assertTrue(result.wasSuccessful())
        self.assertEqual(os.getcwd(), outer_cwd)
        self.assertFalse(Path(recorded["tree"]).exists())


class FixtureContractTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """The default topology loads the tasks the migrated modules rely on."""

    def test_parents_and_children_load(self):
        manager = self.ab.make_task_manager()
        parents = sorted(manager.task_datas)
        children = sorted(manager.child_task_datas)
        self.assertIn("t9000_parent.md", parents)
        self.assertIn("t_unparseable.md", parents)
        self.assertEqual(children, ["t9000_1_childone.md", "t9000_2_childtwo.md"])

    def test_numberless_task_sits_in_the_column_under_test(self):
        """t1352: the filename filter only runs if the file is in that column."""
        manager = self.ab.make_task_manager()
        names = [t.filename for t in manager.get_column_tasks("c0")]
        self.assertIn("t_unparseable.md", names)
        self.assertIn("t9000_parent.md", names)

    def test_local_project_name_resolves(self):
        self.assertEqual(self.ab.load_local_project_name(self.ab.TASKS_DIR),
                         "aitasks")

    def test_no_trails_are_discoverable(self):
        """No `artifacts:` frontmatter anywhere — the explicit no-trails fixture.

        Discovery reads the tree from disk (t1365), so this now asserts the
        stronger property: no trail frontmatter on disk AND nothing skipped as
        unreadable (an unreadable file would also produce an empty list).
        """
        self.assertEqual(self.ab.discover_trails(), ([], []))

    def test_board_module_resolves_under_the_fixture_not_the_repo(self):
        resolved = Path(self.ab.TASKS_DIR).resolve()
        self.assertTrue(resolved.is_relative_to(self.tree.resolve()),
                        f"{resolved} is not inside the fixture tree {self.tree}")
        self.assertFalse(resolved.is_relative_to(REPO_ROOT / "aitasks"))


class InjectedManagerPathTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """C2/C3 pin (t1794_4): a `TaskManager` built the way the injection-mode
    files build it reads the tree its keywords name — not the process cwd's.

    The class's cwd is the fixture tree (DEFAULT_TOPOLOGY, `t9000_parent.md` …);
    a second tree with disjoint task ids is injected. A manager that still read
    ambient state would list the cwd tree, which the negative control shows is
    distinguishable, so the positive rows discriminate.
    """

    OTHER = (bf.FixtureTask(task_id="9701", col="c0", idx=10, slug="injected_a"),
             bf.FixtureTask(task_id="9702", col="c1", idx=10, slug="injected_b"))

    def _other_tasks_dir(self) -> Path:
        tmp = tempfile.TemporaryDirectory(prefix="bf_inject_")
        self.addCleanup(tmp.cleanup)
        return bf.build_fixture_tree(Path(tmp.name), self.OTHER) / "aitasks"

    def _manager_for(self, tasks_dir: Path):
        return self.ab.TaskManager(
            tasks_dir=tasks_dir,
            metadata_file=tasks_dir / "metadata" / "board_config.json",
            gates_registry_file=tasks_dir / "metadata" / "gates.yaml")

    def test_the_manager_lists_the_injected_tree_not_the_cwd(self):
        self.assertEqual(Path.cwd().resolve(), self.tree.resolve(), "precondition")
        other = self._other_tasks_dir()
        manager = self._manager_for(other)
        self.assertEqual(sorted(manager.task_datas),
                         ["t9701_injected_a.md", "t9702_injected_b.md"])
        for task in manager.task_datas.values():
            self.assertTrue(Path(task.filepath).resolve().is_relative_to(other.resolve()))

    def test_a_metadata_save_lands_in_the_injected_tree(self):
        other = self._other_tasks_dir()
        cwd_config = Path("aitasks") / "metadata" / "board_config.json"
        before = cwd_config.read_bytes()
        manager = self._manager_for(other)
        manager.columns.append({"id": "pin", "title": "Pin", "color": "#FFFFFF"})
        manager.column_order.append("pin")
        manager.save_metadata(commit=False)
        self.assertIn('"pin"', (other / "metadata" / "board_config.json")
                      .read_text(encoding="utf-8"))
        self.assertEqual(cwd_config.read_bytes(), before,
                         "the cwd tree's config must be untouched")

    def test_negative_control_a_cwd_relative_manager_lists_the_cwd_tree(self):
        manager = self._manager_for(Path("aitasks"))
        self.assertIn("t9000_parent.md", manager.task_datas)
        self.assertNotIn("t9701_injected_a.md", manager.task_datas)


class PristineRestoreTests(bf.FixtureBoardTestBase, bf.PristineTreeMixin,
                           unittest.TestCase):
    """`PristineTreeMixin` restores board CONFIG, not only task files (t1243_10).

    The restore is invisible while nothing persists config, which is exactly how
    it stayed missing until group collapse became durable. These cases make it
    load-bearing: each dirties one config layer and asserts the NEXT `setUp`
    put the committed bytes back. unittest sorts methods alphabetically, so
    `test_a_*` dirties and `test_b_*` observes — the ordering is the mechanism,
    and it is asserted rather than assumed.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._snapshot_pristine()

    def _config(self, name):
        return self.tasks_dir / "metadata" / name

    def test_a_dirty_both_config_layers(self):
        for name in ("board_config.json", "board_config.local.json"):
            path = self._config(name)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["_harness_canary"] = name
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            # Precondition: the dirtying actually landed, so a green
            # `test_b_*` cannot be explained by "nothing was ever written".
            self.assertIn("_harness_canary", path.read_text(encoding="utf-8"))

    def test_b_both_layers_were_restored(self):
        for name in ("board_config.json", "board_config.local.json"):
            self.assertNotIn("_harness_canary",
                             self._config(name).read_text(encoding="utf-8"),
                             f"{name} leaked from the previous test — "
                             "PristineTreeMixin is not restoring board config")

    def test_snapshot_covers_both_layers_and_the_task_files(self):
        """Negative control: the snapshot is not silently task-files-only.

        If `_snapshot_pristine` regressed to `rglob("*.md")`, `test_b_*` would
        still pass whenever `test_a_*` happened not to run first. This asserts
        the mechanism directly.
        """
        names = {p.name for p in self._pristine}
        self.assertIn("board_config.json", names)
        self.assertIn("board_config.local.json", names)
        self.assertTrue(any(n.endswith(".md") for n in names),
                        "task files must still be snapshotted")


class PhantomStubTests(unittest.TestCase):
    """A board-keys-only task is dropped — the vacuous-pass trap."""

    def test_board_keys_only_task_is_dropped(self):
        tmp = tempfile.TemporaryDirectory(prefix="bf_stub_")
        self.addCleanup(tmp.cleanup)
        spec = (bf.FixtureTask(task_id="9000", col="c0", idx=10, slug="real"),)
        tree = bf.build_fixture_tree(Path(tmp.name), spec)
        # A phantom stub, written by hand: board keys and nothing else.
        (tree / ".aitask-data" / "aitasks" / "t9500_stub.md").write_text(
            "---\nboardcol: c0\nboardidx: 5\n---\n\nbody\n", encoding="utf-8")
        original = os.getcwd()
        os.chdir(tree)
        self.addCleanup(os.chdir, original)
        ab = bf.load_board_module(tag="stub")
        manager = ab.make_task_manager()
        self.assertIn("t9000_real.md", manager.task_datas)
        self.assertNotIn("t9500_stub.md", manager.task_datas,
                         "a board-keys-only task must be dropped as a phantom stub")


class FixtureBootTests(bf.FixtureBoardTestBase, unittest.TestCase):
    """A full KanbanApp Pilot boot works against the fixture tree."""

    def test_app_boots_and_renders_only_fixture_cards(self):
        ab = self.ab

        async def go():
            app = ab.KanbanApp()
            async with app.run_test(size=(160, 48)) as pilot:
                await pilot.pause()
                names = {c.task_data.filename for c in app.query(ab.TaskCard)}
                self.assertTrue(names)
                self.assertTrue(
                    all(n.startswith("t9") or n == "t_unparseable.md" for n in names),
                    f"live-tree cards leaked into the fixture board: {sorted(names)}")

        asyncio.run(go())


#: The modules that reach the board ONLY through this harness (t1354_1 seeded
#: two, t1354_2 migrated the rest). Tier 2 below holds these to the strict rule:
#: no chdir of any kind and no canonical `aitask_board` import.
#:
#: `test_board_movement.py` and `test_board_persistence_seam.py` are deliberately
#: NOT here — both sit on the fixture but import `aitask_board` canonically on
#: purpose (patch mode). The tier-1 sweep still covers them; neither chdirs.
MIGRATED_MODULES = (
    "test_board_bytrail_view.py",
    "test_board_work_report.py",
    "test_board_detail_arrow_nav.py",
    "test_board_detail_collapsible.py",
    "test_board_detail_nested_actions.py",
    "test_board_dialog_run_dispatch.py",
    "test_board_dialog_subprocess_degrade.py",
    "test_board_empty_column_focus.py",
    "test_board_filter_row_layout.py",
    "test_board_footer_visibility.py",
    "test_board_inflight_view.py",
    "test_board_picker_tab_nav.py",
    "test_board_scroll_focus_jump.py",
    "test_board_toggle_children_gate.py",
    "test_board_topic_group.py",
    "test_board_topic_view.py",
    "test_board_view_filter.py",
    # t1794_1: the key-map characterization reaches the board only through the
    # harness too, so it is held to the strict tier from the start.
    "test_board_keymap_characterization.py",
    # t1794_2: the board_widgets re-export and host-protocol pins reach the
    # module only as `ab.board_widgets`, through the harness.
    "test_board_widgets.py",
    # t1794_3: the board_trail_view single-home, identity and CSS pins reach
    # the module only as `ab.board_trail_view` (or read its source).
    "test_board_trail_view.py",
    # t1794_4: the task-model/manager/phase single-home, identity and
    # constructor pins reach the modules only as `ab.<module>`.
    "test_board_task_manager.py",
)

#: Tier-1 exemptions, scoped to **specific chdir expressions** — never to a whole
#: module. A module-wide exemption would re-open the very hole this guard exists
#: to close: a future accidental `os.chdir(REPO_ROOT)` inside an exempt file
#: would be waved through. Anything not listed here is a finding, so an unknown
#: or novel spelling fails loudly instead of passing silently.
#:
#: Renaming a local in one of these files trips the guard. That is intended: the
#: fix is a one-line update to the pinned set, and the failure message says so.
CHDIR_ALLOWED = {
    # This file: chdirs into fixture trees / a bare tmpdir, never REPO_ROOT.
    "test_board_fixture_harness.py": frozenset({
        "os.chdir(tree)",
        "os.chdir(tmp.name)",
        "self.addCleanup(os.chdir, original)",
    }),
    # Chdirs into its own TemporaryDirectory and restores the saved cwd.
    "test_board_refresh_degrade.py": frozenset({
        "os.chdir(cls._tmp.name)",
        "os.chdir(cls._cwd)",
    }),
}

#: Canonical-import exemptions, also scoped to exact expressions.
#:
#: A canonical `import aitask_board` is live-tree coupling even WITHOUT a chdir:
#: `TASKS_DIR` resolves against the process cwd, which during a suite run is the
#: repo root. (That is precisely how `test_board_inflight_view`'s model tests
#: reached the live tree before t1354_2 — they had no chdir at all.) So tier 1
#: flags it, and the three modules that import canonically *by design* pin their
#: exact import statements here:
#:   * test_board_persistence_seam.py — injection mode (formerly patch mode). It
#:     never boots an app; since t1794_4 it constructs `TaskManager` with
#:     explicit `tasks_dir` / `metadata_file` / `gates_registry_file` over a
#:     temp tree and patches no module global of the canonical board.
#:   * test_board_manager_moves.py — the same injection mode, for the
#:     gap-indexing move API (t1243_3). It constructs `TaskManager` with the
#:     paths of a `build_fixture_tree` root, never boots `KanbanApp` and never
#:     chdirs.
#:   * test_board_movement.py — its IsolationNegativeControlTests asserts the
#:     canonical module still has `TASKS_DIR == Path("aitasks")`, i.e. that the
#:     harness did not contaminate it. Importing canonically IS the control.
#:   * test_board_column_manage.py — the same injection mode again, for the
#:     column merge engine (t1377_4). Identical shape to
#:     test_board_manager_moves.py: explicit paths over a `build_fixture_tree`
#:     root, no `KanbanApp`, no chdir. Because the paths are constructor
#:     arguments, no patch lifecycle can re-point the manager at the live tree
#:     (`InjectedManagerPathTests` below pins that the injected tree is read).
CANONICAL_IMPORT_ALLOWED = {
    "test_board_persistence_seam.py": frozenset({
        "canonical import: import aitask_board as B",
    }),
    "test_board_manager_moves.py": frozenset({
        "canonical import: import aitask_board as B",
    }),
    "test_board_movement.py": frozenset({
        "canonical import: import aitask_board as B",
        "canonical import: import aitask_board",
    }),
    "test_board_column_manage.py": frozenset({
        "canonical import: import aitask_board as B",
    }),
}

#: NOTE ON SCOPE (deliberately narrow, stated so it is not over-read): this
#: guard prevents the *chdir + canonical-import* coupling. It does not claim to
#: catch every conceivable route to live data. `tests/test_board_header_row_live.py`
#: reaches the real repo on purpose, via tmux's own `-c str(REPO_ROOT)` with a
#: per-PID socket — it has no chdir and no `aitask_board` import, so it needs no
#: entry above. Its absence is a policy decision, not an oversight.


def _chdir_expressions(source: str) -> list[str]:
    """Every chdir the module performs, as unparsed expressions. Fail-closed.

    The rule is deny-by-default rather than "flag `chdir(REPO_ROOT)`", because
    an argument-matching rule cannot deliver the "or equivalent" promise:
    ``os.chdir(str(REPO_ROOT))``, ``os.chdir(REPO_ROOT.resolve())``,
    ``root = REPO_ROOT; os.chdir(root)`` and ``import os as _os;
    _os.chdir(REPO_ROOT)`` all reach the live tree while evading it. So no
    argument is inspected at all — every chdir is reported and the caller
    decides via `CHDIR_ALLOWED`.

    The rule is **any mention of a `chdir` reference in executable position**,
    however it is spelled or routed:

      * a call whose callee ends with ``chdir`` — `os.chdir(...)`,
        `_os.chdir(...)`, `pathlib.os.chdir(...)`, a bare `chdir(...)`;
      * a `chdir` reference used as a **value** rather than called. This covers
        both `self.addCleanup(os.chdir, original)` (passed as an argument) and
        the alias route `move = os.chdir` … `move(REPO_ROOT)` — the latter is a
        complete bypass of any callee-name rule, because the eventual callee is
        named `move`. Rather than trying to follow the alias, the *construction*
        is rejected at the point the reference is taken, which is conservative
        and needs no dataflow analysis;
      * `getattr(os, "chdir")(...)`, where the name never appears as an
        identifier at all;
      * `from os import chdir`, reported as the import itself.

    A reference is reported as its nearest enclosing **call** (so
    `self.addCleanup(os.chdir, original)` stays pinnable exactly as written),
    else its nearest enclosing **statement** (so `move = os.chdir` is pinnable).
    A reference that is already the callee of a reported call is not reported
    twice.

    Structural, not substring: a docstring or comment mentioning `os.chdir`
    must not trip it, and a real call must not hide behind one.
    """
    import ast

    tree = ast.parse(source)
    parents: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node

    def _is_getattr_chdir(node) -> bool:
        return (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name) and node.func.id == "getattr"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == "chdir")

    def _enclosing(node):
        """Nearest enclosing Call, else nearest enclosing statement."""
        cur = node
        while id(cur) in parents:
            cur = parents[id(cur)]
            if isinstance(cur, (ast.Call, ast.stmt)):
                return cur
        return node

    findings: list[str] = []
    seen: set[int] = set()

    def add(node):
        if id(node) not in seen:
            seen.add(id(node))
            findings.append(ast.unparse(node))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if ast.unparse(node.func).split(".")[-1] == "chdir":
                add(node)
            elif _is_getattr_chdir(node.func):
                add(node)              # getattr(os, "chdir")(...)
            elif _is_getattr_chdir(node):
                add(_enclosing(node))  # the reference taken but not called here
        elif isinstance(node, (ast.Attribute, ast.Name)):
            name = node.attr if isinstance(node, ast.Attribute) else node.id
            if name != "chdir":
                continue
            parent = parents.get(id(node))
            if isinstance(parent, ast.Call) and parent.func is node:
                continue               # already reported as that call
            add(_enclosing(node))
        elif isinstance(node, ast.ImportFrom):
            if node.module == "os" and any(a.name == "chdir" for a in node.names):
                add(node)
    return findings


def _canonical_board_imports(source: str) -> list[str]:
    """Canonical imports of ANY board module (`bf.BOARD_MODULE_NAMES`).

    `import aitask_board` and, since the t1794 split, a sibling such as
    `import board_task_manager` alike: a canonically imported sibling holds the
    shared `sys.modules` copy, never the fixture's, so it is the same live-tree
    coupling. `board_columns` / `board_groups` are flat lib/ modules, not board
    modules, and stay importable.
    """
    import ast

    findings = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in bf.BOARD_MODULE_NAMES:
                    findings.append(f"canonical import: {ast.unparse(node)}")
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module in bf.BOARD_MODULE_NAMES:
                findings.append(f"canonical import: {ast.unparse(node)}")
    return findings


def _sweep_findings(name: str, source: str, allowed=None,
                    import_allowed=None) -> list[str]:
    """Tier-1 findings for one module: unexempted chdirs + unexempted imports."""
    allowed = CHDIR_ALLOWED if allowed is None else allowed
    import_allowed = (CANONICAL_IMPORT_ALLOWED if import_allowed is None
                      else import_allowed)
    permitted_chdir = allowed.get(name, frozenset())
    permitted_import = import_allowed.get(name, frozenset())
    return ([f"chdir: {expr}" for expr in _chdir_expressions(source)
             if expr not in permitted_chdir]
            + [f for f in _canonical_board_imports(source)
               if f not in permitted_import])


def _live_tree_couplings(source: str) -> list[str]:
    """Tier-2 (strict) rule for the migrated set: ANY chdir + canonical import."""
    return ([f"chdir: {expr}" for expr in _chdir_expressions(source)]
            + _canonical_board_imports(source))


#: The equivalent forms a literal `chdir(REPO_ROOT)` matcher would miss. Every
#: one must be flagged; (e)-(g) are the ones that evaded the pre-t1354_2 scanner.
_EQUIVALENT_CHDIR_FORMS = {
    "a_literal": "import os\ndef f():\n    os.chdir(REPO_ROOT)\n",
    "b_str": "import os\ndef f():\n    os.chdir(str(REPO_ROOT))\n",
    "c_resolve": "import os\ndef f():\n    os.chdir(REPO_ROOT.resolve())\n",
    "d_via_local": "import os\ndef f():\n    root = REPO_ROOT\n    os.chdir(root)\n",
    "e_aliased_os": "import os as _os\ndef f():\n    _os.chdir(REPO_ROOT)\n",
    "f_from_import": "from os import chdir\ndef f():\n    chdir(REPO_ROOT)\n",
    "g_reference": "import os\ndef f(self):\n    self.addCleanup(os.chdir, REPO_ROOT)\n",
    # --- alias routes: the eventual callee is not named `chdir` at all, so a
    # --- callee-name rule (however clever about arguments) cannot see these.
    "h_alias_assign": "import os\nmove = os.chdir\ndef f():\n    move(REPO_ROOT)\n",
    "i_getattr": "import os\ndef f():\n    getattr(os, 'chdir')(REPO_ROOT)\n",
    "j_getattr_alias": "import os\nmove = getattr(os, 'chdir')\ndef f():\n    move(REPO_ROOT)\n",
    "k_from_import_alias": ("from os import chdir\nmove = chdir\n"
                            "def f():\n    move(REPO_ROOT)\n"),
    "l_dict_dispatch": "import os\nOPS = {'go': os.chdir}\ndef f():\n    OPS['go'](REPO_ROOT)\n",
}


class LiveTreeSweepTests(unittest.TestCase):
    """Tier 1 — every `tests/test_board_*.py`, fail-closed.

    Deliberately structural rather than a timing ceiling: a wall-clock assertion
    would be flaky under load and would not say *why* it regressed.
    """

    @staticmethod
    def _board_test_sources():
        for path in sorted((REPO_ROOT / "tests").glob("test_board_*.py")):
            yield path.name, path.read_text(encoding="utf-8")

    def test_sweep_covers_more_than_the_migrated_set(self):
        """The glob must actually be a sweep, not a rename of MIGRATED_MODULES."""
        names = [n for n, _ in self._board_test_sources()]
        self.assertGreater(
            len(names), len(MIGRATED_MODULES),
            "tier-1 must scan more modules than tier 2, or it guards nothing new")

    def test_no_board_test_module_reaches_the_live_tree(self):
        for name, source in self._board_test_sources():
            with self.subTest(module=name):
                self.assertEqual(
                    _sweep_findings(name, source), [],
                    f"{name} must reach the board through board_fixture. If a "
                    f"chdir here is genuinely fixture-local, pin its exact "
                    f"expression in CHDIR_ALLOWED[{name!r}].")

    def test_every_allowlist_entry_refers_to_a_real_module(self):
        """A stale entry would silently exempt nothing — or worse, a new file."""
        for label, table in (("CHDIR_ALLOWED", CHDIR_ALLOWED),
                             ("CANONICAL_IMPORT_ALLOWED", CANONICAL_IMPORT_ALLOWED)):
            for name in table:
                with self.subTest(table=label, module=name):
                    self.assertTrue(
                        (REPO_ROOT / "tests" / name).is_file(),
                        f"{label} names {name}, which does not exist")

    def test_import_allowlist_entries_are_load_bearing(self):
        """4.3, import half — removing an entry must break the sweep."""
        for name in CANONICAL_IMPORT_ALLOWED:
            with self.subTest(module=name):
                source = (REPO_ROOT / "tests" / name).read_text(encoding="utf-8")
                self.assertEqual(
                    _sweep_findings(name, source), [],
                    f"{name} should pass with its import exemption")
                without = {k: v for k, v in CANONICAL_IMPORT_ALLOWED.items()
                           if k != name}
                self.assertTrue(
                    _sweep_findings(name, source, import_allowed=without),
                    f"removing CANONICAL_IMPORT_ALLOWED[{name!r}] changed "
                    "nothing — the entry is decorative and untested")

    def test_import_exemption_does_not_cover_other_import_forms(self):
        """4.4, import half — the exemption is per-EXPRESSION, not per-module.

        Exempting `import aitask_board as B` must not silently also permit
        `from aitask_board import KanbanApp` in the same file.
        """
        injected = "\n\nfrom aitask_board import KanbanApp\n"
        for name in CANONICAL_IMPORT_ALLOWED:
            with self.subTest(module=name):
                source = (REPO_ROOT / "tests" / name).read_text(encoding="utf-8")
                findings = _sweep_findings(name, source + injected)
                self.assertTrue(
                    any("KanbanApp" in f for f in findings),
                    f"{name} is import-exempt as a whole — an injected "
                    f"`from aitask_board import KanbanApp` was not flagged")

    # --- negative controls ------------------------------------------------

    def test_guard_flags_every_equivalent_chdir_form(self):
        """4.1 — the "or equivalent" promise, one synthetic module per form."""
        for label, source in _EQUIVALENT_CHDIR_FORMS.items():
            with self.subTest(form=label):
                findings = _sweep_findings("synthetic_probe.py", source)
                self.assertTrue(
                    findings,
                    f"form {label} reached the live tree unflagged — this is "
                    "exactly what an argument-matching rule would miss")
                self.assertTrue(
                    any(f.startswith("chdir: ") for f in findings),
                    f"form {label} was flagged, but not as a chdir: {findings}")

    def test_guard_flags_a_canonical_board_import(self):
        """4.1(h)."""
        for source in ("import aitask_board\n",
                       "from aitask_board import KanbanApp\n"):
            with self.subTest(source=source.strip()):
                findings = _sweep_findings("synthetic_probe.py", source)
                self.assertTrue(
                    any("canonical import" in f for f in findings),
                    f"canonical import not flagged: {findings}")

    def test_guard_is_structural_not_substring(self):
        """4.2 — a mention in a string/docstring must NOT trip it."""
        benign = '_NOTE = "os.chdir(REPO_ROOT) is what we removed"\n'
        self.assertEqual(
            _sweep_findings("synthetic_probe.py", benign), [],
            "the guard must be structural, not substring-based")

    def test_allowlist_entries_are_load_bearing(self):
        """4.3 — removing either entry must break the sweep, naming that module.

        An allowlist entry no control can trip is a decorative lie.
        """
        for name in CHDIR_ALLOWED:
            with self.subTest(module=name):
                source = (REPO_ROOT / "tests" / name).read_text(encoding="utf-8")
                self.assertEqual(
                    _sweep_findings(name, source), [],
                    f"{name} should pass with its allowlist entry")
                without = {k: v for k, v in CHDIR_ALLOWED.items() if k != name}
                self.assertTrue(
                    _sweep_findings(name, source, allowed=without),
                    f"removing CHDIR_ALLOWED[{name!r}] changed nothing — the "
                    "entry is decorative and the exemption is untested")

    def test_exemption_cannot_hide_a_repo_root_chdir(self):
        """4.4 — the exemption is per-EXPRESSION, never per-module.

        This is the control for the last hole: a whole-module exemption would
        wave through a future accidental `os.chdir(REPO_ROOT)` in one of the two
        allowlisted files.
        """
        injections = (
            "\n\ndef _regression():\n    os.chdir(REPO_ROOT)\n",
            "\n\ndef _regression(self):\n    self.addCleanup(os.chdir, REPO_ROOT)\n",
        )
        for name in CHDIR_ALLOWED:
            source = (REPO_ROOT / "tests" / name).read_text(encoding="utf-8")
            for i, injected in enumerate(injections):
                with self.subTest(module=name, injection=i):
                    findings = _sweep_findings(name, source + injected)
                    self.assertTrue(
                        findings,
                        f"{name} is exempt as a whole — an injected REPO_ROOT "
                        "chdir was not flagged, so the allowlist is a hole")
                    self.assertTrue(
                        any("REPO_ROOT" in f for f in findings),
                        f"flagged, but not the injected REPO_ROOT chdir: {findings}")

    def test_each_pinned_expression_is_individually_exempt(self):
        """4.4 converse — the exemption is real, not "everything is flagged"."""
        for name, exprs in CHDIR_ALLOWED.items():
            for expr in exprs:
                with self.subTest(module=name, expr=expr):
                    # Reconstruct a minimal module containing just that call.
                    body = expr if expr.startswith("self.") else expr
                    source = f"import os\ndef f(self):\n    {body}\n"
                    self.assertEqual(
                        _sweep_findings(name, source), [],
                        f"pinned expression {expr!r} is still flagged for "
                        f"{name} — CHDIR_ALLOWED and the scanner disagree")


class FixtureFactControlTests(unittest.TestCase):
    """4.6 — every non-default fixture fact, shrunk until the property vanishes.

    A migrated module that declares `FIXTURE_TASKS = RICH_TOPOLOGY` (or
    `wide_topology(..., tall_titles=True)`) is claiming the default tree is not
    enough. These controls prove that claim: shrink the differing fact and the
    property the module's assertions rest on disappears. A fact whose removal
    changes nothing was never needed and should be deleted rather than kept as
    an unexercised claim.
    """

    def _lanes(self, ab):
        mgr = ab.make_task_manager()
        mgr.load_tasks()
        lanes = ab.group_tasks_by_topic(
            list(mgr.task_datas.values()) + list(mgr.child_task_datas.values()))
        return [label for label, _ in lanes if label != "Ungrouped"]

    def test_default_topology_forms_too_few_topic_lanes(self):
        """test_board_topic_view needs >=2 lanes; DEFAULT_TOPOLOGY yields 1."""
        _tree, ab = bf.enter_fixture_tree(self.addCleanup, tag="ctl_lanes_default")
        self.assertLess(
            len(self._lanes(ab)), 2,
            "DEFAULT_TOPOLOGY unexpectedly forms >=2 topic lanes — then "
            "test_board_topic_view's RICH_TOPOLOGY is an unexercised claim")

        _tree2, ab2 = bf.enter_fixture_tree(
            self.addCleanup, tasks_spec=bf.RICH_TOPOLOGY, tag="ctl_lanes_rich")
        self.assertGreaterEqual(len(self._lanes(ab2)), 2)

    def test_default_topology_carries_no_issue_metadata(self):
        """test_board_view_filter's git filter needs issue:/pull_request:."""
        def git_set(ab):
            mgr = ab.make_task_manager()
            mgr.load_tasks()
            return [f for f, t in list(mgr.task_datas.items())
                                + list(mgr.child_task_datas.items())
                    if t.metadata.get("issue") or t.metadata.get("pull_request")]

        _tree, ab = bf.enter_fixture_tree(self.addCleanup, tag="ctl_git_default")
        self.assertEqual(
            git_set(ab), [],
            "DEFAULT_TOPOLOGY unexpectedly carries issue metadata — then "
            "test_board_view_filter's RICH_TOPOLOGY is an unexercised claim")

        _t2, ab2 = bf.enter_fixture_tree(
            self.addCleanup, tasks_spec=bf.RICH_TOPOLOGY, tag="ctl_git_rich")
        self.assertTrue(git_set(ab2))

    def test_short_slugs_render_cards_that_do_not_exceed_a_short_viewport(self):
        """test_board_scroll_focus_jump needs `tall_titles=True`.

        Volume alone is not the whole shape: 40 short-slug cards still render
        5 rows each, which fits inside the pane the scroll cases require a card
        to overflow.
        """
        async def max_card_height(ab):
            # Reproduce the Tall|Side two-column layout the real module imposes:
            # column WIDTH drives title wrapping, so measuring under the default
            # five narrow columns would answer a different question.
            #
            # Height 14, not 12 (t1418): the board's multi-row footer is 2 rows
            # tall at 200 columns, so a 12-row terminal leaves a 4-row column
            # viewport and the 5-row short-slug cards no longer fit — which would
            # fail this control for a reason that has nothing to do with slug
            # length. 14 restores headroom on both halves: short cards (5) fit a
            # 6-row viewport, tall ones (13) still overflow it decisively.
            app = ab.KanbanApp()
            async with app.run_test(size=(200, 14)) as pilot:
                await pilot.pause()
                mgr = app.manager
                mgr.save_metadata = lambda: None
                mgr.settings = dict(mgr.settings)
                mgr.settings["collapsed_columns"] = []
                mgr.columns = [{"id": "zz_tall", "title": "T", "color": "gray"},
                               {"id": "zz_side", "title": "S", "color": "gray"}]
                mgr.column_order = ["zz_tall", "zz_side"]
                for i, t in enumerate(sorted(mgr.task_datas.values(),
                                             key=lambda t: t.filename)):
                    t.board_col = "zz_tall" if i < 30 else "zz_side"
                    t.board_idx = i * 10
                app.refresh_board()
                for _ in range(3):
                    await pilot.pause()
                cards = [c for c in app.query(ab.TaskCard)
                         if c.column_id == "zz_tall" and c.region.area]
                cols = [c for c in app.query(ab.KanbanColumn)
                        if c.col_id == "zz_tall"]
                return (max(c.region.height for c in cards),
                        cols[0].scrollable_content_region.height)

        _t, ab_short = bf.enter_fixture_tree(
            self.addCleanup, tasks_spec=bf.wide_topology(40), tag="ctl_short")
        h, vp = asyncio.run(max_card_height(ab_short))
        self.assertLessEqual(
            h, vp,
            "short-slug cards already exceed the viewport — then "
            "tall_titles=True is an unexercised claim")

        _t2, ab_tall = bf.enter_fixture_tree(
            self.addCleanup, tasks_spec=bf.wide_topology(40, tall_titles=True),
            tag="ctl_tall")
        h2, vp2 = asyncio.run(max_card_height(ab_tall))
        self.assertGreater(h2, vp2, "tall_titles must overflow the viewport")

    def test_missing_gates_registry_reclassifies_a_human_gate(self):
        """The staged `metadata/gates.yaml` is load-bearing, not cosmetic.

        Without it a task declaring `gates: [review_approved]` with a pending
        human run is grouped as ``agent`` instead of ``human`` — silently, with
        nothing raising. This is what made three test_board_inflight_view cases
        fail during the t1354_2 migration before the registry was staged.
        """
        ledger = ("\n## Gate Runs\n\n> **⏸ gate:review_approved** "
                  "run=2026-01-01T00:00:00Z status=pending type=human\n")
        spec = (bf.FixtureTask(task_id="9000", col="c0", idx=10, slug="gated",
                               status="Implementing",
                               extra={"gates": ["review_approved"]}),)

        def group_for(gates_registry):
            tag = f"ctl_gates_{gates_registry}"
            tree, ab = bf.enter_fixture_tree(
                self.addCleanup, tasks_spec=spec, tag=tag,
                gates_registry=gates_registry)
            path = tree / "aitasks" / "t9000_gated.md"
            path.write_text(path.read_text(encoding="utf-8") + ledger,
                            encoding="utf-8")
            mgr = ab.make_task_manager()
            mgr.load_tasks()
            items = mgr.get_inflight_items()
            self.assertTrue(items, "the gated task must be in flight")
            return items[0].group

        self.assertEqual(group_for(True), "human",
                         "with the registry, review_approved is a human gate")
        self.assertEqual(group_for(False), "agent",
                         "without the registry the gate silently reclassifies — "
                         "if this ever equals 'human', staging gates.yaml is an "
                         "unexercised claim and the fixture contract is wrong")


class MigratedModuleGuardTests(unittest.TestCase):
    """Tier 2 — the migrated set, held to the strict rule (any chdir at all)."""

    def test_migrated_modules_have_no_live_tree_coupling(self):
        for name in MIGRATED_MODULES:
            with self.subTest(module=name):
                source = (REPO_ROOT / "tests" / name).read_text(encoding="utf-8")
                self.assertEqual(
                    _live_tree_couplings(source), [],
                    f"{name} must reach the board through board_fixture, not by "
                    "chdir'ing to the repo root or importing aitask_board")

    def test_migrated_modules_all_exist(self):
        """A typo here would silently guard nothing."""
        for name in MIGRATED_MODULES:
            with self.subTest(module=name):
                self.assertTrue((REPO_ROOT / "tests" / name).is_file(),
                                f"MIGRATED_MODULES names {name}, which is missing")

    def test_guard_detects_a_reintroduced_coupling(self):
        """4.5 — negative control on the strict tier.

        The mutation is applied to an in-memory copy of the real source, so
        nothing on disk changes and no restore is needed.
        """
        source = (REPO_ROOT / "tests" / MIGRATED_MODULES[0]).read_text(encoding="utf-8")
        self.assertEqual(_live_tree_couplings(source), [])

        regressed_chdir = source + "\n\ndef _regression():\n    os.chdir(REPO_ROOT)\n"
        self.assertTrue(
            any(f.startswith("chdir: ") and "REPO_ROOT" in f
                for f in _live_tree_couplings(regressed_chdir)),
            "the guard failed to flag a reintroduced os.chdir(REPO_ROOT)")

        regressed_import = source + "\n\nimport aitask_board\n"
        self.assertTrue(
            any("canonical import" in f for f in _live_tree_couplings(regressed_import)),
            "the guard failed to flag a reintroduced canonical import")

        # Tier 2 is stricter than tier 1: even a tmpdir chdir is a finding here.
        tmpdir_chdir = source + "\n\ndef _r():\n    os.chdir(tmp.name)\n"
        self.assertTrue(
            any(f.startswith("chdir: ") for f in _live_tree_couplings(tmpdir_chdir)),
            "tier 2 must flag ANY chdir in a migrated module")

        # A mention inside a comment/docstring must NOT trip it.
        benign = source + '\n\n_NOTE = "os.chdir(REPO_ROOT) is what we removed"\n'
        self.assertEqual(_live_tree_couplings(benign), [],
                         "the guard must be structural, not substring-based")


# --- C2: only aitask_board.py resolves the task directory (t1794_1) ---------
#
# `load_board_module()` re-execs ONLY aitask_board.py with `TASK_DIR` set, and
# restores the env in `finally`. A sibling board module that resolves the task
# dir itself is wrong both ways, and silent both ways:
#   * bound at import  -> it keeps whatever the FIRST import of it saw (sibling
#     modules come from the shared `sys.modules`, they are not re-executed);
#   * looked up lazily -> it reads the env the loader has already restored.
# So the rule is position-independent: board modules receive resolved paths as
# parameters (parent plan C2: `TaskManager(*, tasks_dir, …)`,
# `load_local_project_name(tasks_dir, …)`).
#
# Boundary, deliberately: this covers DIRECT resolution in board modules. lib/
# functions that resolve the task dir internally — trail_discovery._tasks_dir
# (behind discover_trails, the pinned trail seam), config_utils.load_all_models
# and its import-time MODEL_FILES, work_report_gather.scan_tasks/load_columns,
# trail_gather._local_dirs, roadmap_origin_facts._dirs,
# userconfig_persist._userconfig_path — are a pre-existing lib-layer property
# the canonical board already relies on. A moved function may keep calling them
# exactly where aitask_board.py did; changing that layer is outside t1794.

#: aitask_board.py's TASKS_DIR-derived module constants; no sibling may name one.
_BOARD_PATH_CONSTANTS = frozenset({
    "TASKS_DIR", "METADATA_FILE", "GATES_REGISTRY_FILE", "USERCONFIG_FILE",
    "EMAILS_FILE", "TASK_TYPES_FILE",
})

#: The direct ambient resolvers (lib/config_utils.py).
_TASK_DIR_RESOLVERS = frozenset({"task_dir", "metadata_dir"})

#: Exact-finding exemptions from `_ambient_task_path_reads`, keyed by `board/`
#: filename. Empty: no board module but aitask_board.py resolves the task dir.
C2_AMBIENT_ALLOWED: dict[str, frozenset[str]] = {}

#: Sentinel TASK_DIR for the fresh-load check. It must differ from the default
#: ("aitasks" == bf.TASK_DIR_VALUE), or a stale binding and a lazy read would
#: be indistinguishable from a correct one.
_C2_SENTINEL = "c2_sentinel_tasks"


def _c2_scanned_modules() -> list[Path]:
    """Every board/*.py the C2 rule binds: all but aitask_board.py and non-members."""
    skip = {"aitask_board"} | bf.BOARD_NON_MEMBERS
    return sorted(p for p in (REPO_ROOT / ".aitask-scripts" / "board").glob("*.py")
                  if p.stem not in skip)


def _ambient_task_path_reads(source: str) -> list[str]:
    """Every way a module can resolve the task dir itself, in ANY position.

    Reported as ``"<import-time|runtime> <kind>: <expression>"``. The position
    is for the message only — both are failures. Rejecting the *reference*
    (not just the call) catches `resolve = config_utils.task_dir` and
    `getattr(config_utils, "task_dir")` without dataflow, the same rationale as
    `_chdir_expressions` above. Name the resolved-path parameter `tasks_dir`
    (plural): a local literally called `task_dir` is flagged like the resolver.
    """
    import ast

    tree = ast.parse(source)
    parents: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node

    def runtime(node) -> bool:
        """Inside a function/lambda BODY (defaults and decorators run at import)."""
        child = node
        while id(child) in parents:
            parent = parents[id(child)]
            if (isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and any(child is stmt for stmt in parent.body)):
                return True
            if isinstance(parent, ast.Lambda) and child is parent.body:
                return True
            child = parent
        return False

    def enclosing(node):
        cur = node
        while id(cur) in parents:
            cur = parents[id(cur)]
            if isinstance(cur, (ast.Call, ast.stmt)):
                return cur
        return node

    watched = _TASK_DIR_RESOLVERS | _BOARD_PATH_CONSTANTS
    findings: list[str] = []
    seen: set[str] = set()

    def add(node, kind):
        where = "runtime" if runtime(node) else "import-time"
        text = f"{where} {kind}: {ast.unparse(enclosing(node))}"
        if text not in seen:
            seen.add(text)
            findings.append(text)

    def kind_of(name):
        return ("board path constant" if name in _BOARD_PATH_CONSTANTS
                else "task-dir resolver")

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in watched:
                    add(node, f"{kind_of(alias.name)} import")
        elif isinstance(node, ast.Name) and node.id in watched:
            add(node, kind_of(node.id))
        elif isinstance(node, ast.Attribute) and node.attr in watched:
            add(node, kind_of(node.attr))
        elif isinstance(node, ast.Call):
            if (isinstance(node.func, ast.Name) and node.func.id == "getattr"
                    and len(node.args) >= 2
                    and isinstance(node.args[1], ast.Constant)
                    and node.args[1].value in watched):
                add(node, kind_of(node.args[1].value))
            if any(isinstance(a, ast.Constant) and a.value == "TASK_DIR"
                   for a in node.args):
                add(node, "TASK_DIR env read")
        elif (isinstance(node, ast.Subscript)
              and isinstance(node.slice, ast.Constant)
              and node.slice.value == "TASK_DIR"):
            add(node, "TASK_DIR env read")
    return findings


#: Runs in a FRESH interpreter so no sibling module is already in
#: `sys.modules`: in-process, a flat `import sibling` reuses the cached module
#: and the check would pass without exercising anything.
_FRESH_LOAD_SCRIPT = """\
import json, sys
from pathlib import Path, PurePath
args = json.loads(sys.argv[1])
import board_fixture as bf
names = args["names"]
dragged = sorted(set(names) & set(sys.modules))
if args["board_path"]:
    bf.BOARD_PATH = Path(args["board_path"])
    stand_in = str(Path(args["board_path"]).parent)
    if stand_in not in sys.path:
        sys.path.insert(0, stand_in)
for name in args["preimport"]:
    __import__(name)
before = set(sys.modules)
board = bf.load_board_module(args["task_dir"], tag="c2fresh")
cwd = Path.cwd()
roots = [PurePath(args["task_dir"]), PurePath(bf.TASK_DIR_VALUE), PurePath(".aitask-data")]

def derived(value):
    if isinstance(value, str):
        return any(value == str(r) or value.startswith(str(r) + "/") for r in roots)
    if not isinstance(value, PurePath):
        return False
    for r in roots:
        if not value.is_absolute() and value.parts[:len(r.parts)] == r.parts:
            return True
        try:
            if Path(value).resolve().is_relative_to((cwd / r).resolve()):
                return True
        except (OSError, ValueError):
            pass
    return False

modules = {}
for name in names:
    mod = sys.modules.get(name)
    if mod is None:
        continue
    modules[name] = {
        "fresh": name not in before,
        "bound": sorted(k for k, v in vars(mod).items()
                        if not k.startswith("__") and derived(v)),
    }
calls = []
for spec, pass_tasks_dir in args["calls"]:
    mod_name, fn_name = spec.split(":")
    fn = getattr(sys.modules[mod_name], fn_name)
    result = fn(board.TASKS_DIR) if pass_tasks_dir else fn()
    calls.append({"call": spec, "result": str(result)})
print(json.dumps({
    "board_tasks_dir": str(board.TASKS_DIR),
    "honoured_sentinel": board.TASKS_DIR == Path(args["task_dir"]),
    "dragged": dragged,
    "modules": modules,
    "calls": calls,
}))
"""


def _fresh_load_report(workdir: Path, *, board_path=None, names=None,
                       preimport=(), calls=()) -> dict:
    """Load the board with the sentinel TASK_DIR in a fresh interpreter.

    `calls` holds ``("module:function", pass_tasks_dir)`` pairs invoked AFTER
    the load returned — i.e. after the env was restored, as in every fixture
    test — with the board's own `TASKS_DIR` as argument when `pass_tasks_dir`.
    """
    import subprocess

    (workdir / _C2_SENTINEL).mkdir(exist_ok=True)
    if names is None:
        names = sorted(bf.BOARD_MODULE_NAMES - {"aitask_board"})
    scripts = REPO_ROOT / ".aitask-scripts"
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "TASK_DIR")}
    env["PYTHONPATH"] = os.pathsep.join(
        str(p) for p in (REPO_ROOT / "tests" / "lib", scripts,
                         scripts / "board", scripts / "lib"))
    args = json.dumps({"task_dir": _C2_SENTINEL, "names": list(names),
                       "board_path": str(board_path) if board_path else "",
                       "preimport": list(preimport),
                       "calls": [list(c) for c in calls]})
    proc = subprocess.run([sys.executable, "-c", _FRESH_LOAD_SCRIPT, args],
                          cwd=str(workdir), env=env, capture_output=True,
                          text=True, timeout=180)
    if proc.returncode != 0:
        raise AssertionError(f"fresh-load probe failed:\n{proc.stderr[-3000:]}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _c2_findings(report: dict) -> list[str]:
    """Fail closed: a check that exercised nothing is a finding, not a pass."""
    findings = []
    if not report["honoured_sentinel"]:
        findings.append("the loader did not honour the sentinel TASK_DIR — "
                        "the check exercised nothing")
    for name in report["dragged"]:
        findings.append(f"{name}: imported by board_fixture itself, before any load")
    for name, info in sorted(report["modules"].items()):
        if not info["fresh"]:
            findings.append(f"{name}: imported before the fixture load — the "
                            "check did not exercise it")
        for attr in info["bound"]:
            findings.append(f"{name}.{attr}: task-dir path bound at import")
    for call in report["calls"]:
        if call["result"] != report["board_tasks_dir"]:
            findings.append(
                f"{call['call']}: resolved {call['result']!r} after the load, "
                f"while the board resolved {report['board_tasks_dir']!r}")
    return findings


class CanonicalSiblingImportTests(unittest.TestCase):
    """The canonical-import sweep covers every board module name (t1794_1)."""

    def test_guard_flags_a_canonical_sibling_import(self):
        for source in ("import board_task_manager\n",
                       "from board_trail_view import TrailColumn\n",
                       "import trails_app as ta\n"):
            with self.subTest(source=source.strip()):
                self.assertTrue(
                    any("canonical import" in f
                        for f in _sweep_findings("synthetic_probe.py", source)),
                    "a canonical import of a board sibling bypasses the fixture")

    def test_flat_lib_names_are_not_board_modules(self):
        """`board_columns` & co. live in lib/ — importing them is not coupling."""
        self.assertEqual(
            _canonical_board_imports("import board_columns\nimport board_groups\n"),
            [])


class AmbientTaskPathStaticTests(unittest.TestCase):
    """C2 static half — no board module resolves the task dir, anywhere."""

    FLAGGED = {
        "module_level": "from config_utils import task_dir\nROOT = task_dir()\n",
        "class_body": "import config_utils\nclass C:\n    ROOT = config_utils.task_dir()\n",
        "default_arg": "import config_utils\ndef f(root=config_utils.task_dir()):\n    return root\n",
        "decorator": ("import config_utils\n@register(config_utils.metadata_dir())\n"
                      "def f():\n    pass\n"),
        "in_function": "import config_utils\ndef f():\n    return config_utils.task_dir()\n",
        "lambda_body": "import config_utils\nROOT = lambda: config_utils.task_dir()\n",
        "from_import_alias": "from config_utils import task_dir as td\n",
        "value_alias": "import config_utils\nresolve = config_utils.task_dir\n",
        "getattr": "import config_utils\nroot = getattr(config_utils, 'task_dir')()\n",
        "environ_subscript": "import os\ndef f():\n    return os.environ['TASK_DIR']\n",
        "environ_get": "import os\ndef f():\n    return os.environ.get('TASK_DIR', 'aitasks')\n",
        "getenv": "import os\nROOT = os.getenv('TASK_DIR')\n",
        "board_constant_attr": "def f(ab):\n    return ab.TASKS_DIR / 'x'\n",
        "board_constant_name": "def f():\n    return METADATA_FILE\n",
    }

    CLEAN = {
        "parameter": ("from pathlib import Path\n"
                      "def load(tasks_dir: Path):\n    return tasks_dir / 'metadata'\n"),
        "docstring": '"""Callers pass what task_dir() resolved; never read TASK_DIR here."""\n',
        "other_env": "import os\nHOME = os.environ.get('HOME')\n",
    }

    def test_board_modules_resolve_no_task_dir(self):
        for path in _c2_scanned_modules():
            with self.subTest(module=path.name):
                allowed = C2_AMBIENT_ALLOWED.get(path.name, frozenset())
                found = [f for f in _ambient_task_path_reads(
                    path.read_text(encoding="utf-8")) if f not in allowed]
                self.assertEqual(
                    found, [],
                    f"{path.name} must receive resolved paths as parameters (C2)")

    def test_board_task_manager_takes_its_paths_by_parameter(self):
        """The documented example of C2 (t1794_4). `TaskManager` used to read the
        board's `TASKS_DIR` / `METADATA_FILE` / `GATES_REGISTRY_FILE` at call time;
        in its own module every such read is an attribute of the constructor's
        arguments, and reverting a single one is flagged."""
        src = (REPO_ROOT / ".aitask-scripts" / "board" / "board_task_manager.py"
               ).read_text(encoding="utf-8")
        self.assertEqual(_ambient_task_path_reads(src), [])
        for attr in ("self.tasks_dir", "self.metadata_file", "self.gates_registry_file"):
            self.assertIn(attr, src, "anti-vacuity: the injected reads are present")
        reverted = src.replace("self.metadata_file", "METADATA_FILE", 1)
        self.assertNotEqual(reverted, src)
        self.assertTrue(_ambient_task_path_reads(reverted),
                        "one reverted global read must be flagged")

    def test_scope_excludes_only_the_board_and_non_members(self):
        stems = {p.stem for p in _c2_scanned_modules()}
        self.assertNotIn("aitask_board", stems)
        self.assertTrue(stems.isdisjoint(bf.BOARD_NON_MEMBERS))
        self.assertIn("__init__", stems, "the package marker is in scope too")

    def test_every_allowlist_entry_is_still_real(self):
        board = REPO_ROOT / ".aitask-scripts" / "board"
        for name, exprs in C2_AMBIENT_ALLOWED.items():
            found = set(_ambient_task_path_reads((board / name).read_text(encoding="utf-8")))
            for expr in exprs:
                with self.subTest(module=name, expr=expr):
                    self.assertIn(expr, found, "stale exemption")

    def test_every_resolution_form_is_flagged(self):
        for label, source in self.FLAGGED.items():
            with self.subTest(form=label):
                self.assertTrue(_ambient_task_path_reads(source),
                                f"{label} escaped the C2 static rule")

    def test_runtime_position_is_flagged_not_exempted(self):
        """The lazy read is a failure mode in its own right (the task names it)."""
        self.assertTrue(all(f.startswith("import-time ")
                            for f in _ambient_task_path_reads(self.FLAGGED["module_level"])
                            if "ROOT" in f))
        runtime = _ambient_task_path_reads(self.FLAGGED["in_function"])
        self.assertTrue(any(f.startswith("runtime ") for f in runtime), runtime)
        lam = _ambient_task_path_reads(self.FLAGGED["lambda_body"])
        self.assertTrue(any(f.startswith("runtime ") for f in lam), lam)

    def test_compliant_forms_are_not_flagged(self):
        for label, source in self.CLEAN.items():
            with self.subTest(form=label):
                self.assertEqual(_ambient_task_path_reads(source), [],
                                 f"{label} is a false positive")


_STAND_IN_BOARD = """\
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config_utils import task_dir
TASKS_DIR = task_dir()
import board_c2_probe  # noqa: E402,F401
"""


class FreshLoadC2Tests(unittest.TestCase):
    """C2 runtime half — a fresh interpreter, a sentinel TASK_DIR, fail closed.

    For the real tree the report covers every sibling the board imports —
    `board_widgets` since t1794_2, `board_trail_view` since t1794_3 — and the
    real-tree test asserts each was executed fresh, so the check cannot quietly
    exercise nothing. Lazy reads are
    enforced by the static half; negative control (iv) below proves both that
    they are a real, silent failure and that the static rule catches them.
    """

    def _workdir(self) -> Path:
        tmp = tempfile.TemporaryDirectory(prefix="bf_c2_")
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)

    def _probe(self, probe_source: str, **kwargs) -> dict:
        root = self._workdir()
        stand_in = root / "fakeboard"
        stand_in.mkdir()
        (stand_in / "aitask_board.py").write_text(_STAND_IN_BOARD, encoding="utf-8")
        (stand_in / "board_c2_probe.py").write_text(probe_source, encoding="utf-8")
        return _fresh_load_report(root, board_path=stand_in / "aitask_board.py",
                                  names=["board_c2_probe"], **kwargs)

    def test_real_board_loads_fresh_with_no_bound_sibling_paths(self):
        report = _fresh_load_report(self._workdir())
        self.assertEqual(_c2_findings(report), [])
        self.assertEqual(report["board_tasks_dir"], _C2_SENTINEL,
                         "the real board must have honoured the sentinel")
        # Anti-vacuity: the board imports board_widgets (t1794_2),
        # board_trail_view (t1794_3) and the three t1794_4 data-layer modules,
        # so the real load must have executed each, freshly, under the sentinel.
        for sibling in ("board_widgets", "board_trail_view", "board_task_model",
                        "board_workflow_phase", "board_task_manager"):
            with self.subTest(sibling=sibling):
                self.assertIn(sibling, report["modules"])
                self.assertTrue(report["modules"][sibling]["fresh"])

    def test_i_import_time_binding_is_flagged(self):
        report = self._probe("from config_utils import task_dir\nTASKS_DIR = task_dir()\n")
        self.assertTrue(report["modules"]["board_c2_probe"]["fresh"])
        self.assertIn("board_c2_probe.TASKS_DIR: task-dir path bound at import",
                      _c2_findings(report))

    def test_ii_stale_sibling_is_flagged(self):
        report = self._probe("VALUE = 1\n", preimport=("board_c2_probe",))
        self.assertEqual(
            _c2_findings(report),
            ["board_c2_probe: imported before the fixture load — the check did "
             "not exercise it"])

    def test_iii_unrelated_relative_path_is_not_flagged(self):
        report = self._probe(
            "from pathlib import Path\nSCRIPT = Path('.aitask-scripts') / 'x.sh'\n")
        self.assertEqual(_c2_findings(report), [])

    def test_iv_deferred_read_diverges_silently_and_is_statically_flagged(self):
        source = ("from config_utils import task_dir\n"
                  "def tasks_root():\n    return task_dir()\n")
        report = self._probe(source, calls=[("board_c2_probe:tasks_root", False)])
        self.assertEqual(report["board_tasks_dir"], _C2_SENTINEL)
        self.assertEqual(report["calls"][0]["result"], bf.TASK_DIR_VALUE,
                         "after the restore the lazy read sees the default tree")
        self.assertTrue(any("resolved 'aitasks' after the load" in f
                            for f in _c2_findings(report)))
        self.assertTrue(
            any(f.startswith("runtime ") for f in _ambient_task_path_reads(source)),
            "the static rule must flag the same deferred read")

    def test_v_resolved_path_parameter_is_clean(self):
        source = "def tasks_root(tasks_dir):\n    return tasks_dir\n"
        report = self._probe(source, calls=[("board_c2_probe:tasks_root", True)])
        self.assertEqual(_c2_findings(report), [])
        self.assertEqual(_ambient_task_path_reads(source), [])

    def test_a_sentinel_the_loader_ignored_is_a_finding(self):
        """`_c2_findings` fails closed on a report that proves nothing."""
        report = {"board_tasks_dir": "aitasks", "honoured_sentinel": False,
                  "dragged": [], "modules": {}, "calls": []}
        self.assertTrue(_c2_findings(report))


if __name__ == "__main__":
    unittest.main()
