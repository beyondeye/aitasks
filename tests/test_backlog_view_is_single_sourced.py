"""Drift guard for the t1586 backlog-view extraction.

`lib/backlog_view.py` exists because the CLI text report and the stats TUI panes
had each grown their own copy of the same row axis, ordering rule, column order
and exclusion-reason tuple. Extracting it fixed the duplication once; this test
is what stops it coming back — a later edit that adds a local `_aggregate_all`
"just for this surface" re-forks the seam silently, and every value assertion in
the suite keeps passing while the two copies drift.

## Detection scope (documented on purpose — a guard that overclaims is worse
## than one with a known boundary)

Scanned: the two consumer surfaces only, via `ast`, at MODULE level.

  * Detected: a module-level `def` bearing one of the lifted names, and a
    module-level assignment to one of the lifted constant names. `ast` is used
    rather than a text scan so a name inside a docstring, a comment or an
    `import` line cannot trip it, and so formatting cannot hide a real one.
  * NOT detected: a re-fork under a *different* name (`_my_aggregate`), a copy
    nested inside a function or class body, or one built dynamically. The names
    are the contract this guard pins, not the semantics.
  * Also asserted, as the positive half: both surfaces really do import the
    lifted names from `backlog_view`. Without it, deleting every local copy AND
    every use would pass the negative half vacuously.

Run: `python tests/test_backlog_view_is_single_sourced.py`
(also collected by `tests/run_all_python_tests.sh`).
"""

from __future__ import annotations

import ast
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import List

PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_DIR / ".aitask-scripts"

#: The module `lib/backlog_view.py` owns. A surface that defines any of these
#: has re-forked the seam.
LIFTED_DEFS = ("_aggregate_all", "_backlog_columns", "_columns", "_derive_levels")

#: Constant names the surfaces must import rather than restate. Both spellings
#: are listed because the TUI's local copy used the private one.
LIFTED_CONSTANTS = ("BACKLOG_TASK_EXCLUSION_REASONS", "_TASK_EXCLUSION_REASONS")

#: The two consumers, relative to `.aitask-scripts/`.
SURFACES = ("aitask_stats.py", "stats/panes/backlog.py")


def scan_file(path: Path) -> List[str]:
    """Violations in one surface file, as `<name>:<kind>` strings."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: List[str] = []
    for node in tree.body:                      # module level only, by construction
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in LIFTED_DEFS:
                found.append(f"{node.name}:def")
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in LIFTED_CONSTANTS:
                    found.append(f"{target.id}:assign")
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id in LIFTED_CONSTANTS:
                found.append(f"{node.target.id}:assign")
    return found


def scan_tree(root: Path) -> List[str]:
    """`<file>:<violation>` for every surface under `root`. Missing files are
    skipped rather than silently passing — see `test_scanner_sees_both_surfaces`,
    which pins that both are actually present."""
    out: List[str] = []
    for rel in SURFACES:
        path = root / rel
        if not path.exists():
            continue
        out.extend(f"{rel}:{v}" for v in scan_file(path))
    return sorted(out)


def imported_from_backlog_view(path: Path) -> List[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "backlog_view":
            names.extend(a.name for a in node.names)
    return names


class TestBacklogViewIsSingleSourced(unittest.TestCase):
    def test_neither_surface_redeclares_a_lifted_name(self):
        violations = scan_tree(SCRIPTS)
        self.assertEqual(
            violations, [],
            msg=("a backlog surface re-declares logic that lives in "
                 "lib/backlog_view.py; import it instead of re-forking it"),
        )

    def test_scanner_sees_both_surfaces(self):
        """Guards against the whole test going vacuous on a file rename."""
        for rel in SURFACES:
            self.assertTrue((SCRIPTS / rel).exists(), rel)

    def test_both_surfaces_import_the_shared_axis(self):
        """The positive half: the names are not merely absent, they are used."""
        cli = imported_from_backlog_view(SCRIPTS / "aitask_stats.py")
        pane = imported_from_backlog_view(SCRIPTS / "stats/panes/backlog.py")
        for name in ("build_backlog_axis", "backlog_columns", "order_categories",
                     "BACKLOG_TASK_EXCLUSION_REASONS"):
            self.assertIn(name, cli, f"aitask_stats.py does not import {name}")
        for name in ("build_backlog_axis", "backlog_columns", "order_categories",
                     "BACKLOG_TASK_EXCLUSION_REASONS"):
            self.assertIn(name, pane, f"stats/panes/backlog.py does not import {name}")

    # --- Negative controls: prove the scanner can actually fail --------------
    # Without these, a scanner whose match never fires would pass the test above
    # forever and pin nothing.

    def _temp_copy(self) -> Path:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        for rel in SURFACES:
            dest = tmp / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SCRIPTS / rel, dest)
        return tmp

    def test_negative_a_reforked_def_is_flagged(self):
        tmp = self._temp_copy()
        target = tmp / "stats/panes/backlog.py"
        with target.open("a", encoding="utf-8") as fh:
            fh.write("\n\ndef _aggregate_all(flow):\n    return flow\n")

        violations = scan_tree(tmp)
        self.assertIn("stats/panes/backlog.py:_aggregate_all:def", violations)
        # Exactly one file flagged — the scanner is not matching indiscriminately.
        self.assertEqual({v.split(":")[0] for v in violations}, {"stats/panes/backlog.py"})

    def test_negative_a_restated_constant_is_flagged(self):
        tmp = self._temp_copy()
        target = tmp / "aitask_stats.py"
        with target.open("a", encoding="utf-8") as fh:
            fh.write('\n\n_TASK_EXCLUSION_REASONS = ("folded",)\n')

        self.assertIn("aitask_stats.py:_TASK_EXCLUSION_REASONS:assign", scan_tree(tmp))

    def test_negative_a_nested_copy_is_outside_the_documented_scope(self):
        """Pins the boundary the header claims, so the claim cannot rot.

        A copy nested inside a function is NOT detected. Asserting it explicitly
        is what keeps the documented scope honest rather than aspirational."""
        tmp = self._temp_copy()
        target = tmp / "aitask_stats.py"
        with target.open("a", encoding="utf-8") as fh:
            fh.write("\n\ndef _outer():\n    def _aggregate_all(flow):\n        return flow\n    return _aggregate_all\n")

        self.assertEqual(scan_tree(tmp), [])

    def test_negative_an_import_of_the_constant_is_not_a_redeclaration(self):
        """The real files import `BACKLOG_TASK_EXCLUSION_REASONS`; if that alone
        tripped the guard, `test_neither_surface_redeclares_a_lifted_name` would
        be failing for the wrong reason."""
        tmp = self._temp_copy()
        target = tmp / "aitask_stats.py"
        with target.open("a", encoding="utf-8") as fh:
            fh.write("\n\nfrom backlog_view import BACKLOG_TASK_EXCLUSION_REASONS  # noqa: F811,E402\n")

        self.assertEqual(scan_tree(tmp), [])


if __name__ == "__main__":
    unittest.main()
