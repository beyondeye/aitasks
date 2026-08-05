"""Save-time reconciliation of externally-added board columns (t1377_3).

`TaskManager.load_metadata()` runs exactly once, at construction. Without the
reconciliation this file tests, the board would write its startup-era
`self.columns` on every `save_metadata()` and silently destroy a column created
meanwhile by `lib/board_columns.create_column` — the headless writer `ait
minimonitor` reaches through `aitask_board_column.sh`.

Four groups, and it is worth saying why each exists:

* **survival** — the point of the feature: an external addition must reach disk
  through an ordinary board gesture, not a synthetic `save_metadata()` call;
* **discrimination** — merging must not resurrect a column the board deliberately
  deleted. `_known_col_ids` is the discriminator, and the negative control clears
  it to prove the deletion comes back without it;
* **isolation** — the user layer is never read and never rewritten, so the
  project/local split `create_column` establishes survives the round trip;
* **containment** — an AST scan proving the reload is reachable from
  `save_metadata` ALONE. That is a hard performance constraint, not tidiness: the
  board must not gain file I/O on `refresh_board`, the auto-refresh timer, or any
  render path.
"""

from __future__ import annotations

import ast
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(REPO_ROOT / "tests" / "lib"),
           str(REPO_ROOT / ".aitask-scripts" / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import board_columns as bc  # noqa: E402
import board_fixture as bf  # noqa: E402

BOARD_PATH = REPO_ROOT / ".aitask-scripts" / "board" / "aitask_board.py"

TOPOLOGY = (
    bf.FixtureTask(task_id="9000", col="c0", idx=10, slug="parent"),
    bf.FixtureTask(task_id="9001", col="c1", idx=10, slug="alpha"),
)


class _ReconcileCase(unittest.TestCase):
    """One fixture tree + one real board module per test.

    Per-test rather than per-class: every case mutates `board_config.json`, and a
    shared tree would let one test's columns leak into the next one's baseline —
    which is exactly the state this feature is about, so cross-contamination
    would be indistinguishable from the behaviour under test.
    """

    def setUp(self):
        self.tree, self.ab = bf.enter_fixture_tree(
            self.addCleanup, tasks_spec=TOPOLOGY, tag="reconcile")
        self.config = self.tree / "aitasks" / "metadata" / "board_config.json"
        self.local = self.tree / "aitasks" / "metadata" / "board_config.local.json"

    def written(self):
        """`(columns, column_order)` as actually persisted to the project file."""
        return bc.project_columns_at(self.config)

    def written_ids(self):
        cols, _order = self.written()
        return [c["id"] for c in cols]


class ExternalAdditionTests(_ReconcileCase):
    def test_external_column_survives_an_ordinary_board_save(self):
        """Case 1 — the whole point of the phase.

        The save is triggered by a real gesture (`toggle_column_collapsed`), not
        by calling `save_metadata()` directly: a direct call would prove the
        reconciliation runs, but not that any user-reachable path reaches it.
        """
        manager = self.ab.TaskManager()
        out = bc.create_column(self.tree, "Spikes", "#8BE9FD")
        self.assertTrue(out.ok, out.refused)

        manager.toggle_column_collapsed("c0")

        cols, order = self.written()
        by_id = {c["id"]: c for c in cols}
        self.assertIn("spikes", by_id)
        self.assertEqual(by_id["spikes"]["title"], "Spikes")
        self.assertEqual(by_id["spikes"]["color"], "#8BE9FD")
        self.assertEqual(order[-1], "spikes")

    def test_negative_control_without_reconciliation_the_column_is_lost(self):
        """The control that proves the row above is not vacuous.

        Disabling only the reconciliation must lose the column — if this passes
        with it disabled, the test above was measuring something else.
        """
        manager = self.ab.TaskManager()
        bc.create_column(self.tree, "Spikes", "#8BE9FD")

        with mock.patch.object(self.ab.TaskManager,
                               "_reconcile_external_columns",
                               lambda self: None):
            manager.toggle_column_collapsed("c0")

        self.assertNotIn("spikes", self.written_ids())

    def test_multiple_external_additions_keep_their_on_disk_order(self):
        manager = self.ab.TaskManager()
        for title in ("First", "Second", "Third"):
            self.assertTrue(bc.create_column(self.tree, title).ok)

        manager.toggle_column_collapsed("c0")

        ids = self.written_ids()
        self.assertEqual(ids[-3:], ["first", "second", "third"])
        _cols, order = self.written()
        self.assertEqual(order[-3:], ["first", "second", "third"])


class DeletionDiscriminationTests(_ReconcileCase):
    def test_board_side_deletion_is_not_resurrected(self):
        """Case 2 — the discriminator that makes merging safe."""
        manager = self.ab.TaskManager()
        self.assertIn("c1", [c["id"] for c in manager.columns])

        manager.delete_column("c1")  # deletes and saves

        self.assertNotIn("c1", self.written_ids())

    def test_negative_control_without_known_ids_the_deletion_comes_back(self):
        """Clearing `_known_col_ids` must resurrect it.

        One mutation, and it targets the discriminator specifically: with the set
        empty, a column that is on disk but absent from `self.columns` reads as
        an external addition rather than as our own deletion.
        """
        manager = self.ab.TaskManager()
        manager._known_col_ids = set()

        manager.delete_column("c1")

        self.assertIn("c1", self.written_ids())

    def test_deletion_then_external_recreation_is_merged(self):
        """After a delete, the id leaves `_known_col_ids`, so a later external
        creation of the same id is a genuine addition again."""
        manager = self.ab.TaskManager()
        manager.delete_column("c1")
        self.assertNotIn("c1", manager._known_col_ids)

        bc.create_column(self.tree, "C1")   # slugs to "c1"
        manager.toggle_column_collapsed("c0")

        self.assertIn("c1", self.written_ids())


class BoardSideEditTests(_ReconcileCase):
    def test_reorder_and_edit_survive_an_external_append(self):
        """Case 3 — merging appends; it never rewrites what the board holds."""
        manager = self.ab.TaskManager()
        manager.update_column("c0", "c0", "Renamed Zero", "#BD93F9")
        manager.column_order = ["c1", "c0"]
        bc.create_column(self.tree, "Extern", "#FF79C6")

        manager.save_metadata()

        cols, order = self.written()
        by_id = {c["id"]: c for c in cols}
        self.assertEqual(by_id["c0"]["title"], "Renamed Zero")
        self.assertEqual(by_id["c0"]["color"], "#BD93F9")
        self.assertEqual(order, ["c1", "c0", "extern"])

    def test_board_edit_wins_over_a_concurrent_external_edit_of_a_known_column(self):
        """A column we already knew is ours to define — an external *edit* of it
        is not an addition and is deliberately not merged."""
        manager = self.ab.TaskManager()
        manager.update_column("c0", "c0", "Mine", "#50FA7B")

        raw = json.loads(self.config.read_text(encoding="utf-8"))
        for entry in raw["columns"]:
            if entry["id"] == "c0":
                entry["title"] = "Theirs"
        self.config.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")

        manager.save_metadata()

        by_id = {c["id"]: c for c in self.written()[0]}
        self.assertEqual(by_id["c0"]["title"], "Mine")


class CollisionTests(_ReconcileCase):
    def test_identical_definition_merges_silently(self):
        manager = self.ab.TaskManager()
        entry = {"id": "dup", "title": "Dup", "color": "#FF5555"}
        manager.columns.append(dict(entry))
        manager.column_order.append("dup")
        # Same id, byte-equal definition, written externally.
        raw = json.loads(self.config.read_text(encoding="utf-8"))
        raw["columns"].append(dict(entry))
        raw["column_order"].append("dup")
        self.config.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")

        manager.save_metadata()

        self.assertEqual(manager.reconcile_warnings, [])
        self.assertEqual(self.written_ids().count("dup"), 1)

    def test_differing_definition_warns_and_keeps_the_boards_version(self):
        warnings = []
        manager = self.ab.TaskManager(
            on_warning=lambda msg, **kw: warnings.append((msg, kw)))
        manager.columns.append({"id": "dup", "title": "Mine", "color": "#FF5555"})
        manager.column_order.append("dup")
        raw = json.loads(self.config.read_text(encoding="utf-8"))
        raw["columns"].append({"id": "dup", "title": "Theirs", "color": "#50FA7B"})
        raw["column_order"].append("dup")
        self.config.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")

        manager.save_metadata()

        self.assertEqual(len(manager.reconcile_warnings), 1)
        message = manager.reconcile_warnings[0]
        self.assertIn("dup", message)
        self.assertIn("Mine", message)
        self.assertIn("Theirs", message)      # both sides named — never silent
        self.assertEqual(len(warnings), 1)    # the app sink fired too
        self.assertFalse(warnings[0][1].get("markup", True))
        by_id = {c["id"]: c for c in self.written()[0]}
        self.assertEqual(by_id["dup"]["title"], "Mine")


class LayerIsolationTests(_ReconcileCase):
    def test_local_config_is_never_read_by_the_reconciliation(self):
        """Case 4a — the reader must not touch the user layer.

        Asserted on the *argument*, not on the file's bytes: `save_metadata`
        legitimately rewrites the local file afterwards, so byte-identity alone
        cannot tell "never read" from "read and rewritten identically".
        """
        manager = self.ab.TaskManager()
        seen = []
        real = bc.project_columns_at

        def spy(path):
            seen.append(str(path))
            return real(path)

        with mock.patch.object(self.ab, "project_columns_at", spy):
            manager.toggle_column_collapsed("c0")

        self.assertTrue(seen)
        for path in seen:
            self.assertNotIn(".local.json", path)

    def test_external_creation_leaves_the_local_layer_byte_identical(self):
        """Case 4b — `create_column`'s own promise, verified end to end."""
        before = self.local.read_bytes()
        self.assertTrue(bc.create_column(self.tree, "Spikes").ok)
        self.assertEqual(self.local.read_bytes(), before)
        # And `settings` never reached the tracked file.
        raw = json.loads(self.config.read_text(encoding="utf-8"))
        self.assertNotIn("settings", raw)


class UnreadableConfigTests(_ReconcileCase):
    def test_corrupt_project_config_does_not_break_the_save(self):
        """Losing the *merge* is safe; losing the *save* is not."""
        manager = self.ab.TaskManager()
        self.config.write_text("{ not json", encoding="utf-8")

        manager.toggle_column_collapsed("c0")   # must not raise

        self.assertIn("c0", self.written_ids())

    def test_missing_project_config_does_not_break_the_save(self):
        manager = self.ab.TaskManager()
        self.config.unlink()

        manager.toggle_column_collapsed("c0")

        self.assertIn("c0", self.written_ids())


# --- Containment: the hard performance constraint ----------------------------

#: Who may call what, per callee. Containment is a **chain**, not a flat rule:
#: the raw reader is reached only through the reconciliation, which is reached
#: only through `save_metadata`. Asserting per-callee is what makes the chain
#: explicit — a flat allowlist would have to permit `_reconcile_external_columns`
#: as a caller of everything, and would then no longer notice if the reader grew
#: a second, unrelated call site.
#:
#: `save_metadata` is the root because every one of its call sites is a discrete
#: user gesture, so the cost is per-gesture. Anything on the refresh / render /
#: timer path would put file I/O in front of every frame.
ALLOWED_CALLERS = {
    "_reconcile_external_columns": {"save_metadata"},
    "project_columns_at": {"_reconcile_external_columns"},
}

#: The transitive closure of the chain above — nothing outside this set may
#: reach the reload, however indirectly.
REACHABLE_ROOTS = {"save_metadata", "_reconcile_external_columns"}

#: Enclosing functions that must NEVER reach it, named explicitly so a failure
#: message says which continuous path was breached rather than just "not allowed".
FORBIDDEN_CALLERS = {
    "refresh_board", "action_refresh_board", "_recompose_column",
    "compose", "render", "on_mount", "_auto_refresh", "load_tasks",
}

WATCHED_CALLEES = {"_reconcile_external_columns", "project_columns_at"}


def _callers_of(tree: ast.AST) -> dict[str, set[str]]:
    """`{callee: {enclosing function names}}` for the watched callees."""
    found: dict[str, set[str]] = {name: set() for name in WATCHED_CALLEES}
    stack: list[str] = []

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            stack.append(node.name)
            self.generic_visit(node)
            stack.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Call(self, node):
            func = node.func
            name = (func.attr if isinstance(func, ast.Attribute)
                    else func.id if isinstance(func, ast.Name) else None)
            if name in found and stack:
                found[name].add(stack[-1])
            self.generic_visit(node)

    Visitor().visit(tree)
    return found


class CallSiteContainmentTests(unittest.TestCase):
    """Case 5 — the reload stays off every continuous board path."""

    @classmethod
    def setUpClass(cls):
        cls.source = BOARD_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_reload_is_reachable_only_from_save_metadata(self):
        callers = _callers_of(self.tree)
        for callee, sites in callers.items():
            allowed = ALLOWED_CALLERS[callee]
            self.assertTrue(
                sites, f"{callee} is never called — the scan would pass vacuously")
            self.assertLessEqual(
                sites, allowed,
                f"{callee} is called from {sorted(sites - allowed)}; expected "
                f"only {sorted(allowed)}. The save-time reload must not reach a "
                f"continuous board path")

    def test_the_whole_call_chain_stays_inside_save_metadata(self):
        """The transitive form of the row above.

        Checking each edge separately would still pass if the chain were rooted
        somewhere new — e.g. if `_reconcile_external_columns` gained a second
        caller that is itself on the render path. This closes that by asserting
        the union of everything that can reach the reload.
        """
        callers = _callers_of(self.tree)
        reaching = set().union(*callers.values())
        self.assertLessEqual(
            reaching, REACHABLE_ROOTS,
            f"the reload chain is rooted outside save_metadata: "
            f"{sorted(reaching - REACHABLE_ROOTS)}")

    def test_no_forbidden_caller_reaches_the_reload(self):
        callers = _callers_of(self.tree)
        for callee, sites in callers.items():
            breached = sites & FORBIDDEN_CALLERS
            self.assertFalse(
                breached,
                f"{callee} is reachable from {sorted(breached)} — that path runs "
                f"per frame / per refresh and must never do file I/O")

    def test_negative_control_a_refresh_path_call_is_detected(self):
        """Inject the call the constraint forbids and assert the scan catches it.

        Without this, a scan that silently matched nothing (a renamed helper, a
        broken visitor) would report success forever.
        """
        injected = self.source.replace(
            "    def refresh_board(self",
            "    def refresh_board_probe(self):\n"
            "        self._reconcile_external_columns()\n"
            "\n"
            "    def refresh_board(self",
            1,
        )
        self.assertNotEqual(injected, self.source, "injection anchor not found")
        sites = _callers_of(ast.parse(injected))["_reconcile_external_columns"]
        self.assertIn("refresh_board_probe", sites)
        self.assertFalse(sites <= ALLOWED_CALLERS["_reconcile_external_columns"])


class BenchmarkTests(unittest.TestCase):
    """The measured budget from the plan, asserted rather than merely recorded.

    One denominator: milliseconds added per `save_metadata()` call — which is
    milliseconds per discrete user gesture, not per frame. The budget is 1 ms;
    the real config measures ~0.02 ms, so this fails only on a genuine
    regression (e.g. someone routing the reader through a full layered load or a
    task scan), not on ordinary machine noise.
    """

    def test_project_columns_at_stays_under_the_per_save_budget(self):
        import timeit

        config = REPO_ROOT / "aitasks" / "metadata" / "board_config.json"
        if not config.is_file():                      # pragma: no cover
            self.skipTest("no live board_config.json in this checkout")
        n = 200
        elapsed = timeit.timeit(lambda: bc.project_columns_at(config), number=n)
        per_call_ms = elapsed / n * 1000
        self.assertLess(
            per_call_ms, 1.0,
            f"reload costs {per_call_ms:.4f} ms per save_metadata() call, over "
            f"the 1 ms budget — `ait board` must not get slower")


if __name__ == "__main__":
    unittest.main(verbosity=2)
