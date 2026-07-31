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
        manager = ab.TaskManager()
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
        manager = self.ab.TaskManager()
        parents = sorted(manager.task_datas)
        children = sorted(manager.child_task_datas)
        self.assertIn("t9000_parent.md", parents)
        self.assertIn("t_unparseable.md", parents)
        self.assertEqual(children, ["t9000_1_childone.md", "t9000_2_childtwo.md"])

    def test_numberless_task_sits_in_the_column_under_test(self):
        """t1352: the filename filter only runs if the file is in that column."""
        manager = self.ab.TaskManager()
        names = [t.filename for t in manager.get_column_tasks("c0")]
        self.assertIn("t_unparseable.md", names)
        self.assertIn("t9000_parent.md", names)

    def test_local_project_name_resolves(self):
        self.assertEqual(self.ab.load_local_project_name(), "aitasks")

    def test_no_trails_are_discoverable(self):
        """No `artifacts:` frontmatter anywhere — the explicit no-trails fixture."""
        manager = self.ab.TaskManager()
        self.assertEqual(self.ab.discover_trails(manager), [])

    def test_board_module_resolves_under_the_fixture_not_the_repo(self):
        resolved = Path(self.ab.TASKS_DIR).resolve()
        self.assertTrue(resolved.is_relative_to(self.tree.resolve()),
                        f"{resolved} is not inside the fixture tree {self.tree}")
        self.assertFalse(resolved.is_relative_to(REPO_ROOT / "aitasks"))


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
        manager = ab.TaskManager()
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


#: The modules t1354_1 migrated off the live tree. t1354_2 extends this list as
#: it migrates the rest; `test_board_persistence_seam.py` is deliberately NOT
#: here — it imports `aitask_board` canonically on purpose (patch mode).
MIGRATED_MODULES = (
    "test_board_bytrail_view.py",
    "test_board_work_report.py",
)


def _live_tree_couplings(source: str) -> list[str]:
    """AST findings that would put a module back on the live tree.

    Structural, not substring: a docstring or comment mentioning `os.chdir`
    must not trip the guard, and a real call must not hide behind one.
    """
    import ast

    findings = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            func = ast.unparse(node.func)
            if func in ("os.chdir", "chdir"):
                findings.append(f"chdir call: {ast.unparse(node)}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "aitask_board":
                    findings.append(f"canonical import: {ast.unparse(node)}")
        elif isinstance(node, ast.ImportFrom):
            if node.module == "aitask_board":
                findings.append(f"canonical import: {ast.unparse(node)}")
    return findings


class MigratedModuleGuardTests(unittest.TestCase):
    """The migrated modules must not drift back onto the live repo tree.

    Deliberately structural rather than a timing ceiling: a wall-clock
    assertion would be flaky under load and would not say *why* it regressed.
    """

    def test_migrated_modules_have_no_live_tree_coupling(self):
        for name in MIGRATED_MODULES:
            with self.subTest(module=name):
                source = (REPO_ROOT / "tests" / name).read_text(encoding="utf-8")
                self.assertEqual(
                    _live_tree_couplings(source), [],
                    f"{name} must reach the board through board_fixture, not by "
                    "chdir'ing to the repo root or importing aitask_board")

    def test_guard_detects_a_reintroduced_coupling(self):
        """Negative control — a guard that cannot fail is testing nothing.

        The mutation is applied to an in-memory copy of the real source, so
        nothing on disk changes and no restore is needed.
        """
        source = (REPO_ROOT / "tests" / MIGRATED_MODULES[0]).read_text(encoding="utf-8")
        self.assertEqual(_live_tree_couplings(source), [])

        regressed_chdir = source + "\n\ndef _regression():\n    os.chdir(REPO_ROOT)\n"
        self.assertTrue(
            any("chdir" in f for f in _live_tree_couplings(regressed_chdir)),
            "the guard failed to flag a reintroduced os.chdir(REPO_ROOT)")

        regressed_import = source + "\n\nimport aitask_board\n"
        self.assertTrue(
            any("canonical import" in f for f in _live_tree_couplings(regressed_import)),
            "the guard failed to flag a reintroduced canonical import")

        # A mention inside a comment/docstring must NOT trip it.
        benign = source + '\n\n_NOTE = "os.chdir(REPO_ROOT) is what we removed"\n'
        self.assertEqual(_live_tree_couplings(benign), [],
                         "the guard must be structural, not substring-based")


if __name__ == "__main__":
    unittest.main()
