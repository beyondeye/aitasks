"""Tests for lib/module_shadow_guard.py — fail fast on a lib/ module shadow (t1926).

t1217 moved ``board/task_yaml.py`` to ``lib/task_yaml.py``. Upgrades left the
old ``board/`` copy behind, and because ``aitask_board.py`` puts ``board/`` ahead
of ``lib/`` on ``sys.path`` the stale copy won the import: every fresh
``ait board`` died with ``ImportError: cannot import name 'normalize_board_idx'``.
The guard turns that into a named diagnostic and a clean exit. These tests run
it in subprocesses against a synthetic tree (never the real one — the worktree
is shared), plus structural checks that keep the real tree collision-free.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m pytest tests/test_lib_shadow_guard.py -v
"""
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / ".aitask-scripts"
GUARD = SCRIPTS / "lib" / "module_shadow_guard.py"

# The TUIs whose own directory precedes lib/ on sys.path, i.e. the ones a
# shadow can actually reach. Each must call the guard.
OWN_DIR_FIRST_TUIS = [
    "board/aitask_board.py",
    "board/trails_app.py",
    "syncer/syncer_app.py",
    "settings/settings_app.py",
]


class GuardBehaviourTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.lib = self.tmp / ".aitask-scripts" / "lib"
        self.board = self.tmp / ".aitask-scripts" / "board"
        self.lib.mkdir(parents=True)
        self.board.mkdir(parents=True)
        shutil.copy(GUARD, self.lib / GUARD.name)
        (self.lib / "task_yaml.py").write_text("def normalize_board_idx():\n    return 0\n")

    def run_entry(self, path_order):
        """Run a tiny 'TUI entry' with the given sys.path prefix order."""
        prefix = ", ".join(repr(str(p)) for p in path_order)
        code = textwrap.dedent(f"""
            import sys
            sys.path[:0] = [{prefix}]
            from module_shadow_guard import assert_lib_not_shadowed
            assert_lib_not_shadowed({str(self.lib)!r})
            from task_yaml import normalize_board_idx
            print("IMPORTED_OK")
        """)
        return subprocess.run([sys.executable, "-c", code], capture_output=True,
                              text=True, cwd=str(self.tmp), timeout=60)

    def test_stale_board_copy_ahead_of_lib_exits_with_named_diagnostic(self):
        stale = self.board / "task_yaml.py"
        stale.write_text("def parse():\n    return {}\n")   # lacks normalize_board_idx
        res = self.run_entry([self.board, self.lib])
        self.assertEqual(res.returncode, 1, res.stderr)
        self.assertIn(str(stale), res.stderr)
        self.assertIn("shadows", res.stderr)
        self.assertIn("ait setup", res.stderr)
        self.assertNotIn("ImportError", res.stderr)
        self.assertNotIn("IMPORTED_OK", res.stdout)

    def test_control_without_guard_reproduces_the_opaque_importerror(self):
        # Negative control: the fixture really reproduces the t1926 defect.
        (self.board / "task_yaml.py").write_text("def parse():\n    return {}\n")
        code = textwrap.dedent(f"""
            import sys
            sys.path[:0] = [{str(self.board)!r}, {str(self.lib)!r}]
            from task_yaml import normalize_board_idx
        """)
        res = subprocess.run([sys.executable, "-c", code], capture_output=True,
                             text=True, cwd=str(self.tmp), timeout=60)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("ImportError", res.stderr)
        self.assertIn("normalize_board_idx", res.stderr)

    def test_package_shadow_is_caught(self):
        pkg = self.board / "task_yaml"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        res = self.run_entry([self.board, self.lib])
        self.assertEqual(res.returncode, 1, res.stderr)
        self.assertIn(str(pkg / "__init__.py"), res.stderr)

    def test_cached_stale_module_is_caught_even_with_lib_first(self):
        # The stale copy was imported while board/ led; lib/ was moved ahead
        # afterwards. Python reuses the cached module, so the path scan alone
        # would pass and the next import would raise the opaque ImportError.
        stale = self.board / "task_yaml.py"
        stale.write_text("def parse():\n    return {}\n")
        code = textwrap.dedent(f"""
            import sys
            sys.path[:0] = [{str(self.board)!r}, {str(self.lib)!r}]
            import task_yaml
            sys.path.remove({str(self.lib)!r})
            sys.path.insert(0, {str(self.lib)!r})
            from module_shadow_guard import assert_lib_not_shadowed
            assert_lib_not_shadowed({str(self.lib)!r})
            from task_yaml import normalize_board_idx
            print("IMPORTED_OK")
        """)
        res = subprocess.run([sys.executable, "-c", code], capture_output=True,
                             text=True, cwd=str(self.tmp), timeout=60)
        self.assertEqual(res.returncode, 1, res.stderr)
        self.assertIn(str(stale), res.stderr)
        self.assertNotIn("ImportError", res.stderr)
        self.assertNotIn("IMPORTED_OK", res.stdout)

    def test_cached_module_from_another_framework_lib_is_not_a_shadow(self):
        # A test process may have imported the same framework module from a
        # fixture copy's lib/ first; that is not a stale leftover.
        other_lib = self.tmp / "other" / ".aitask-scripts" / "lib"
        other_lib.mkdir(parents=True)
        shutil.copy(GUARD, other_lib / GUARD.name)
        (other_lib / "task_yaml.py").write_text("def normalize_board_idx():\n    return 1\n")
        code = textwrap.dedent(f"""
            import sys
            sys.path.insert(0, {str(other_lib)!r})
            import task_yaml
            sys.path[:0] = [{str(self.board)!r}, {str(self.lib)!r}]
            sys.path.insert(0, {str(self.lib)!r})
            from module_shadow_guard import assert_lib_not_shadowed
            assert_lib_not_shadowed({str(self.lib)!r})
            print("GUARD_OK")
        """)
        res = subprocess.run([sys.executable, "-c", code], capture_output=True,
                             text=True, cwd=str(self.tmp), timeout=60)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("GUARD_OK", res.stdout)

    def test_lib_first_is_not_a_shadow(self):
        (self.board / "task_yaml.py").write_text("def parse():\n    return {}\n")
        res = self.run_entry([self.lib, self.board])
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("IMPORTED_OK", res.stdout)

    def test_no_collision_passes(self):
        (self.board / "board_widgets.py").write_text("X = 1\n")
        res = self.run_entry([self.board, self.lib])
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("IMPORTED_OK", res.stdout)

    def test_another_framework_lib_ahead_is_not_a_shadow(self):
        # A test process can hold two checkouts at once; the other tree's lib/
        # carries the same module names and must not be flagged.
        other_lib = self.tmp / "other" / ".aitask-scripts" / "lib"
        other_lib.mkdir(parents=True)
        shutil.copy(GUARD, other_lib / GUARD.name)
        (other_lib / "task_yaml.py").write_text("def normalize_board_idx():\n    return 1\n")
        res = self.run_entry([self.board, other_lib, self.lib])
        self.assertEqual(res.returncode, 0, res.stderr)


class RealTreeStructureTest(unittest.TestCase):
    def lib_names(self):
        lib = SCRIPTS / "lib"
        names = {p.stem for p in lib.glob("*.py") if p.name != "__init__.py"}
        names |= {p.parent.name for p in lib.glob("*/__init__.py")}
        return names

    def test_no_tracked_module_outside_lib_shares_a_lib_name(self):
        out = subprocess.run(
            ["git", "-C", str(REPO), "ls-files", ".aitask-scripts/"],
            capture_output=True, text=True, check=True).stdout.split()
        names = self.lib_names()
        clashes = []
        for rel in out:
            p = Path(rel)
            if p.suffix != ".py" or p.parts[1] == "lib":
                continue
            stem = p.parent.name if p.name == "__init__.py" else p.stem
            if stem in names:
                clashes.append(rel)
        self.assertEqual(clashes, [], "a module here shadows lib/ for any TUI "
                         "that puts its own dir first — rename it")

    def test_no_lib_module_takes_a_stdlib_name(self):
        stdlib = getattr(sys, "stdlib_module_names", None)
        if stdlib is None:
            self.skipTest("sys.stdlib_module_names needs Python 3.10+")
        self.assertEqual(sorted(self.lib_names() & set(stdlib)), [])

    def test_own_dir_first_tuis_call_the_guard(self):
        for rel in OWN_DIR_FIRST_TUIS:
            src = (SCRIPTS / rel).read_text()
            self.assertIn("assert_lib_not_shadowed(", src, rel)
            # ...and before the first bare import of a sibling/lib module, i.e.
            # right after the sys.path block.
            guard_at = src.index("assert_lib_not_shadowed(")
            last_insert = src.rindex("sys.path.insert(0", 0, guard_at)
            between = src[last_insert:guard_at]
            self.assertNotIn("\nfrom tui_switcher", between, rel)
            self.assertNotIn("\nfrom config_utils", between, rel)

    def test_guard_passes_on_the_real_tree(self):
        code = textwrap.dedent(f"""
            import sys
            sys.path[:0] = [{str(SCRIPTS / 'board')!r}, {str(SCRIPTS / 'lib')!r}]
            sys.path.insert(0, {str(SCRIPTS)!r})
            sys.path.insert(0, {str(SCRIPTS / 'syncer')!r})
            from module_shadow_guard import find_lib_shadows
            print(find_lib_shadows({str(SCRIPTS / 'lib')!r}))
        """)
        res = subprocess.run([sys.executable, "-c", code], capture_output=True,
                             text=True, cwd=str(REPO), timeout=60)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), "[]")


if __name__ == "__main__":
    unittest.main()
