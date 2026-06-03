"""Tests for the derived per-module fluid status (UC-2, §4.7, t756_5).

Exercises the pure ``brainstorm_status`` computation over seeded graph state:
all six §4.7 states, the orthogonal ``deferred`` overlay, the live-vs-archived
linked-task resolution, the cross-subgraph ``merged`` parents-walk, and the
``module_deferred`` persistence round-trip.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))

from brainstorm.brainstorm_dag import (  # noqa: E402
    GRAPH_STATE_FILE,
    NODES_DIR,
    PROPOSALS_DIR,
    UMBRELLA_SUBGRAPH,
    create_node,
    set_head,
)
from brainstorm.brainstorm_session import (  # noqa: E402
    _module_deferred_map,
    _write_module_deferred,
)
from brainstorm.brainstorm_status import (  # noqa: E402
    STATUS_IMPLEMENTED,
    STATUS_IN_DESIGN,
    STATUS_IN_IMPLEMENTATION,
    STATUS_MERGED,
    STATUS_UNSTARTED,
    compute_module_status,
    is_module_merged,
    module_status_rows,
)


def _seed_state(wt: Path, **maps) -> None:
    """Seed br_graph_state.yaml + dirs with the given module maps."""
    (wt / NODES_DIR).mkdir(parents=True, exist_ok=True)
    (wt / PROPOSALS_DIR).mkdir(parents=True, exist_ok=True)
    state = {
        "current_head": None,
        "current_heads": {},
        "history": {},
        "next_node_id": 1,
        "active_dimensions": [],
        "module_tasks": {},
        "last_synced_at": {},
        "module_deferred": {},
    }
    state.update(maps)
    (wt / GRAPH_STATE_FILE).write_text(yaml.safe_dump(state), encoding="utf-8")


def _node(wt: Path, node_id: str, parents, module=None) -> None:
    create_node(
        wt, node_id, parents, f"{node_id} desc",
        {"component_x": "x"}, "## p\n", "bootstrap", module_label=module,
    )


def _write_task(root: Path, task_id: str, status: str, archived: bool = False) -> None:
    """Write a minimal task file under aitasks/ (live or archived)."""
    if "_" in task_id:
        parent = task_id.split("_", 1)[0]
        sub = (Path("aitasks/archived") if archived else Path("aitasks")) / f"t{parent}"
    else:
        sub = Path("aitasks/archived") if archived else Path("aitasks")
    d = root / sub
    d.mkdir(parents=True, exist_ok=True)
    (d / f"t{task_id}_thing.md").write_text(
        f"---\nstatus: {status}\nissue_type: feature\n---\n\nbody\n",
        encoding="utf-8",
    )


class ModuleStatusComputeTests(unittest.TestCase):
    def test_unstarted_only_root(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_state(wt, current_heads={"auth": "n001_auth"})
            _node(wt, "n001_auth", [], module="auth")
            set_head(wt, "n001_auth", module="auth")
            self.assertEqual(
                compute_module_status(wt, "auth"), STATUS_UNSTARTED
            )

    def test_in_design_no_linked_task(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_state(wt, current_heads={"auth": "n002_auth"})
            _node(wt, "n001_auth", [], module="auth")
            _node(wt, "n002_auth", ["n001_auth"], module="auth")
            set_head(wt, "n002_auth", module="auth")
            self.assertEqual(
                compute_module_status(wt, "auth"), STATUS_IN_DESIGN
            )

    def test_in_design_linked_task_ready(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            cwd = os.getcwd()
            try:
                os.chdir(td)
                _seed_state(
                    wt,
                    current_heads={"auth": "n002_auth"},
                    module_tasks={"auth": "905"},
                )
                _node(wt, "n001_auth", [], module="auth")
                _node(wt, "n002_auth", ["n001_auth"], module="auth")
                _write_task(wt, "905", "Ready")
                self.assertEqual(
                    compute_module_status(wt, "auth"), STATUS_IN_DESIGN
                )
            finally:
                os.chdir(cwd)

    def test_in_implementation_linked_task_implementing(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            cwd = os.getcwd()
            try:
                os.chdir(td)
                _seed_state(
                    wt,
                    current_heads={"auth": "n002_auth"},
                    module_tasks={"auth": "905_2"},
                )
                _node(wt, "n001_auth", [], module="auth")
                _node(wt, "n002_auth", ["n001_auth"], module="auth")
                _write_task(wt, "905_2", "Implementing")
                self.assertEqual(
                    compute_module_status(wt, "auth"),
                    STATUS_IN_IMPLEMENTATION,
                )
            finally:
                os.chdir(cwd)

    def test_implemented_archived_task(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            cwd = os.getcwd()
            try:
                os.chdir(td)
                _seed_state(
                    wt,
                    current_heads={"auth": "n002_auth"},
                    module_tasks={"auth": "905_2"},
                )
                _node(wt, "n001_auth", [], module="auth")
                _node(wt, "n002_auth", ["n001_auth"], module="auth")
                # archived-only hit => implemented, regardless of frontmatter
                _write_task(wt, "905_2", "Done", archived=True)
                self.assertEqual(
                    compute_module_status(wt, "auth"), STATUS_IMPLEMENTED
                )
            finally:
                os.chdir(cwd)

    def test_merged_overrides_base(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            # auth subgraph with a HEAD; a umbrella node lists that HEAD as parent.
            _seed_state(wt, current_heads={"auth": "n002_auth"})
            _node(wt, "n000_init", [], module=None)
            _node(wt, "n001_auth", ["n000_init"], module="auth")
            _node(wt, "n002_auth", ["n001_auth"], module="auth")
            set_head(wt, "n002_auth", module="auth")
            # Destination (umbrella) node carrying the merge edge.
            _node(wt, "n003_merge", ["n002_auth"], module=None)
            self.assertTrue(is_module_merged(wt, "auth"))
            self.assertEqual(compute_module_status(wt, "auth"), STATUS_MERGED)

    def test_not_merged_when_head_only_in_own_subgraph(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_state(wt, current_heads={"auth": "n002_auth"})
            _node(wt, "n001_auth", [], module="auth")
            _node(wt, "n002_auth", ["n001_auth"], module="auth")
            set_head(wt, "n002_auth", module="auth")
            self.assertFalse(is_module_merged(wt, "auth"))


class ModuleDeferredTests(unittest.TestCase):
    def test_deferred_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_state(wt)
            self.assertEqual(_module_deferred_map(wt), {})
            _write_module_deferred(wt, "auth", True)
            self.assertTrue(_module_deferred_map(wt).get("auth"))
            _write_module_deferred(wt, "auth", False)
            self.assertFalse(_module_deferred_map(wt).get("auth"))

    def test_deferred_is_orthogonal_to_base_status(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_state(wt, current_heads={"auth": "n002_auth"})
            _node(wt, "n001_auth", [], module="auth")
            _node(wt, "n002_auth", ["n001_auth"], module="auth")
            _write_module_deferred(wt, "auth", True)
            # Base status is still in_design; deferred is an overlay flag.
            self.assertEqual(
                compute_module_status(wt, "auth"), STATUS_IN_DESIGN
            )
            rows = {r["module"]: r for r in module_status_rows(wt)}
            self.assertTrue(rows["auth"]["deferred"])
            self.assertEqual(rows["auth"]["status"], STATUS_IN_DESIGN)


class ModuleStatusRowsTests(unittest.TestCase):
    def test_rows_cover_all_subgraphs_with_counts(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_state(
                wt,
                current_heads={"auth": "n002_auth", UMBRELLA_SUBGRAPH: "n000_init"},
                last_synced_at={"auth": "2026-06-03 09:00"},
            )
            _node(wt, "n000_init", [], module=None)
            _node(wt, "n001_auth", ["n000_init"], module="auth")
            _node(wt, "n002_auth", ["n001_auth"], module="auth")
            rows = {r["module"]: r for r in module_status_rows(wt)}
            self.assertIn("auth", rows)
            self.assertIn(UMBRELLA_SUBGRAPH, rows)
            self.assertEqual(rows["auth"]["node_count"], 2)
            self.assertEqual(rows["auth"]["last_synced"], "2026-06-03 09:00")
            self.assertTrue(rows[UMBRELLA_SUBGRAPH]["is_umbrella"])


if __name__ == "__main__":
    unittest.main()
