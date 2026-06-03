"""Contract / edge-case tests for the per-module fluid status (§4.7, t922).

Risk-mitigation ("after") follow-up for t756_5. The in-task suite
(``test_brainstorm_module_status.py``, 10 tests) covers each of the six §4.7
states, the deferred-overlay orthogonality at ``in_design``, the archived
``implemented`` resolution, and the ``module_deferred`` round-trip. This module
HARDENS the two computations t756_5's risk evaluation flagged as the most
likely to be silently wrong — the cross-subgraph ``merged`` parents-walk
(``is_module_merged``) and the live-vs-archived linked-task resolution
(``_resolve_task_state``) — plus the ``_node_module`` → dashboard render wiring.
It does **not** duplicate the in-task suite; only the edge / combinatoric cases
that suite omits:

  * ``is_module_merged`` precision — a same-subgraph node referencing the HEAD
    does NOT count as merged; merge detection across more than two subgraphs.
  * linked-task resolution against missing / malformed task files (graceful
    ``in_design``), and ``_resolve_task_state`` for parent vs child ids.
  * the deferred overlay paired with the terminal ``merged`` base state.
  * two subgraphs carrying distinct statuses in one session.
  * a render-layer regression guard driving ``_update_module_status`` through a
    Textual pilot so ``module_status_rows`` actually runs.

Seed / ``_node`` / ``_write_task`` / chdir patterns mirror
``test_brainstorm_module_status.py``; the standalone-file + pilot structure
mirrors the sibling contract test ``test_brainstorm_module_sync_apply_contract.py``
(t913). Run via ``bash tests/run_all_python_tests.sh`` or directly with unittest.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from textual.app import App, ComposeResult  # noqa: E402
from textual.widgets import Label  # noqa: E402

from brainstorm.brainstorm_dag import (  # noqa: E402
    GRAPH_STATE_FILE,
    NODES_DIR,
    PROPOSALS_DIR,
    UMBRELLA_SUBGRAPH,
    create_node,
    set_head,
)
from brainstorm.brainstorm_session import (  # noqa: E402
    _write_module_deferred,
)
from brainstorm.brainstorm_status import (  # noqa: E402
    STATUS_IN_DESIGN,
    STATUS_IN_IMPLEMENTATION,
    STATUS_MERGED,
    STATUS_UNSTARTED,
    _resolve_task_state,
    compute_module_status,
    is_module_merged,
    module_status_rows,
)
from brainstorm.brainstorm_app import BrainstormApp  # noqa: E402


# --------------------------------------------------------------------------- #
# Shared seed helpers (mirrors test_brainstorm_module_status.py)
# --------------------------------------------------------------------------- #
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


def _write_task_raw(root: Path, task_id: str, frontmatter_body: str) -> None:
    """Write a task file with caller-controlled frontmatter (malformed cases)."""
    d = root / "aitasks"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"t{task_id}_thing.md").write_text(
        f"---\n{frontmatter_body}\n---\n\nbody\n", encoding="utf-8"
    )


# --------------------------------------------------------------------------- #
# is_module_merged precision (cross-subgraph parents walk)
# --------------------------------------------------------------------------- #
class MergedPrecisionTests(unittest.TestCase):
    def test_same_subgraph_child_referencing_head_not_merged(self):
        """A SAME-subgraph node listing the HEAD as a parent must not count.

        The HEAD is pinned to an older node (n001_auth) while a same-module
        child (n002_auth) references it. ``is_module_merged`` skips same-module
        nodes, so this is NOT a merge — guarding the ``_node_module(...) ==
        module: continue`` line that the in-task suite never forces.
        """
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_state(wt)
            _node(wt, "n001_auth", [], module="auth")
            _node(wt, "n002_auth", ["n001_auth"], module="auth")
            # Pin the HEAD to the OLDER node so its child references it.
            set_head(wt, "n001_auth", module="auth")
            self.assertFalse(is_module_merged(wt, "auth"))
            # Base status is unaffected: 2 auth nodes, no linked task → in_design.
            self.assertEqual(
                compute_module_status(wt, "auth"), STATUS_IN_DESIGN
            )

    def test_merged_across_more_than_two_subgraphs(self):
        """Merge edge into a THIRD subgraph (not the umbrella) still detected."""
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_state(wt)
            _node(wt, "n000_init", [], module=None)            # umbrella
            _node(wt, "n001_auth", ["n000_init"], module="auth")
            _node(wt, "n002_auth", ["n001_auth"], module="auth")
            _node(wt, "n003_db", ["n000_init"], module="db")
            # db node absorbs auth's HEAD (merge into a sibling, not umbrella).
            _node(wt, "n004_db_merge", ["n003_db", "n002_auth"], module="db")
            set_head(wt, "n000_init")
            set_head(wt, "n002_auth", module="auth")
            set_head(wt, "n004_db_merge", module="db")
            self.assertTrue(is_module_merged(wt, "auth"))
            self.assertEqual(compute_module_status(wt, "auth"), STATUS_MERGED)


# --------------------------------------------------------------------------- #
# Linked-task resolution against missing / malformed task files
# --------------------------------------------------------------------------- #
class LinkedTaskResolutionEdgeTests(unittest.TestCase):
    def _seed_two_node_auth(self, wt: Path, task_id: str) -> None:
        _seed_state(
            wt, current_heads={"auth": "n002_auth"},
            module_tasks={"auth": task_id},
        )
        _node(wt, "n001_auth", [], module="auth")
        _node(wt, "n002_auth", ["n001_auth"], module="auth")

    def test_missing_linked_task_file_is_in_design(self):
        """module_tasks points at a task with no file on disk → in_design."""
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            cwd = os.getcwd()
            try:
                os.chdir(td)
                self._seed_two_node_auth(wt, "905")  # no t905_*.md written
                self.assertEqual(
                    compute_module_status(wt, "auth"), STATUS_IN_DESIGN
                )
            finally:
                os.chdir(cwd)

    def test_malformed_frontmatter_no_status_is_in_design(self):
        """Linked task file lacks a `status:` key → graceful in_design."""
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            cwd = os.getcwd()
            try:
                os.chdir(td)
                self._seed_two_node_auth(wt, "905")
                _write_task_raw(wt, "905", "issue_type: feature")
                self.assertEqual(
                    compute_module_status(wt, "auth"), STATUS_IN_DESIGN
                )
            finally:
                os.chdir(cwd)

    def test_unparseable_yaml_frontmatter_is_in_design(self):
        """Linked task file with invalid YAML frontmatter → graceful in_design."""
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            cwd = os.getcwd()
            try:
                os.chdir(td)
                self._seed_two_node_auth(wt, "905")
                # Unterminated quote → yaml.safe_load raises YAMLError.
                _write_task_raw(wt, "905", 'status: "Ready')
                self.assertEqual(
                    compute_module_status(wt, "auth"), STATUS_IN_DESIGN
                )
            finally:
                os.chdir(cwd)


# --------------------------------------------------------------------------- #
# _resolve_task_state direct unit coverage (parent vs child id)
# --------------------------------------------------------------------------- #
class ResolveTaskStateUnitTests(unittest.TestCase):
    def test_parent_id_resolves_top_level(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            cwd = os.getcwd()
            try:
                os.chdir(td)
                _write_task(wt, "905", "Ready")
                self.assertEqual(_resolve_task_state("905"), ("Ready", False))
            finally:
                os.chdir(cwd)

    def test_child_id_resolves_parent_subdir(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            cwd = os.getcwd()
            try:
                os.chdir(td)
                _write_task(wt, "905_2", "Implementing")
                self.assertEqual(
                    _resolve_task_state("905_2"), ("Implementing", False)
                )
            finally:
                os.chdir(cwd)

    def test_archived_only_hit_reports_archived(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            cwd = os.getcwd()
            try:
                os.chdir(td)
                _write_task(wt, "905", "Done", archived=True)
                self.assertEqual(_resolve_task_state("905"), ("Done", True))
            finally:
                os.chdir(cwd)

    def test_live_preferred_over_archived(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            cwd = os.getcwd()
            try:
                os.chdir(td)
                _write_task(wt, "905", "Ready")               # live
                _write_task(wt, "905", "Done", archived=True)  # archived
                # Live location wins; archived flag stays False.
                self.assertEqual(_resolve_task_state("905"), ("Ready", False))
            finally:
                os.chdir(cwd)

    def test_missing_returns_none_false(self):
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            cwd = os.getcwd()
            try:
                os.chdir(td)
                self.assertEqual(_resolve_task_state("905"), (None, False))
            finally:
                os.chdir(cwd)


# --------------------------------------------------------------------------- #
# Deferred overlay paired with a terminal base state
# --------------------------------------------------------------------------- #
class DeferredOverlayCombinatoricTests(unittest.TestCase):
    def test_deferred_and_merged_simultaneously(self):
        """A module can be both ``merged`` (base) and ``deferred`` (overlay).

        The in-task suite only pairs deferred with ``in_design``; this confirms
        the orthogonality holds at the terminal ``merged`` base state too.
        """
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            _seed_state(wt)
            _node(wt, "n000_init", [], module=None)
            _node(wt, "n001_auth", ["n000_init"], module="auth")
            _node(wt, "n002_auth", ["n001_auth"], module="auth")
            _node(wt, "n003_merge", ["n002_auth"], module=None)  # umbrella absorbs
            set_head(wt, "n003_merge")
            set_head(wt, "n002_auth", module="auth")
            _write_module_deferred(wt, "auth", True)

            self.assertEqual(compute_module_status(wt, "auth"), STATUS_MERGED)
            rows = {r["module"]: r for r in module_status_rows(wt)}
            self.assertEqual(rows["auth"]["status"], STATUS_MERGED)
            self.assertTrue(rows["auth"]["deferred"])


# --------------------------------------------------------------------------- #
# Two subgraphs carrying distinct statuses in one session
# --------------------------------------------------------------------------- #
class MultiModuleStatusTests(unittest.TestCase):
    def test_two_subgraphs_distinct_statuses(self):
        """auth → in_implementation while db → unstarted, simultaneously."""
        with tempfile.TemporaryDirectory() as td:
            wt = Path(td)
            cwd = os.getcwd()
            try:
                os.chdir(td)
                _seed_state(
                    wt,
                    current_heads={
                        "auth": "n002_auth",
                        "db": "n003_db",
                        UMBRELLA_SUBGRAPH: "n000_init",
                    },
                    module_tasks={"auth": "905_2"},
                )
                _node(wt, "n000_init", [], module=None)
                _node(wt, "n001_auth", ["n000_init"], module="auth")
                _node(wt, "n002_auth", ["n001_auth"], module="auth")
                _node(wt, "n003_db", ["n000_init"], module="db")  # root only
                _write_task(wt, "905_2", "Implementing")

                self.assertEqual(
                    compute_module_status(wt, "auth"), STATUS_IN_IMPLEMENTATION
                )
                self.assertEqual(
                    compute_module_status(wt, "db"), STATUS_UNSTARTED
                )
                rows = {r["module"]: r for r in module_status_rows(wt)}
                self.assertEqual(rows["auth"]["status"], STATUS_IN_IMPLEMENTATION)
                self.assertEqual(rows["auth"]["node_count"], 2)
                self.assertEqual(rows["db"]["status"], STATUS_UNSTARTED)
                self.assertEqual(rows["db"]["node_count"], 1)
            finally:
                os.chdir(cwd)


# --------------------------------------------------------------------------- #
# Render-layer regression guard (Textual pilot) — guards _node_module wiring
# --------------------------------------------------------------------------- #
class _StatusHostApp(App):
    """Mounts the ``#module_status_info`` Label that ``_update_module_status``
    targets, so the real render path (incl. ``module_status_rows`` →
    ``_node_module``) runs against a seeded session."""

    def __init__(self, session_path: Path) -> None:
        super().__init__()
        self.session_path = session_path

    def compose(self) -> ComposeResult:
        yield Label("", id="module_status_info")


class ModuleStatusRenderGuardTests(unittest.TestCase):
    def _run(self, coro):
        return asyncio.run(coro)

    def test_umbrella_only_session_renders_placeholder(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                wt = Path(td)
                _seed_state(wt, current_heads={UMBRELLA_SUBGRAPH: "n000_init"})
                _node(wt, "n000_init", [], module=None)
                app = _StatusHostApp(wt)
                async with app.run_test(size=(80, 24)) as pilot:
                    await pilot.pause()
                    # Real render path; must not raise on the umbrella-only case.
                    BrainstormApp._update_module_status(app)
                    await pilot.pause()
                    label = app.query_one("#module_status_info", Label)
                    self.assertIn("no modules", str(label.render()))

        self._run(runner())

    def test_multi_module_session_renders_rows(self):
        async def runner():
            with tempfile.TemporaryDirectory() as td:
                wt = Path(td)
                _seed_state(wt)
                _node(wt, "n000_init", [], module=None)
                _node(wt, "n001_auth", ["n000_init"], module="auth")
                _node(wt, "n002_db", ["n000_init"], module="db")
                set_head(wt, "n000_init")
                set_head(wt, "n001_auth", module="auth")
                set_head(wt, "n002_db", module="db")
                app = _StatusHostApp(wt)
                async with app.run_test(size=(80, 24)) as pilot:
                    await pilot.pause()
                    BrainstormApp._update_module_status(app)
                    await pilot.pause()
                    label = app.query_one("#module_status_info", Label)
                    text = str(label.render())
                    # A status line per module subgraph was rendered.
                    self.assertIn("auth", text)
                    self.assertIn("db", text)

        self._run(runner())


if __name__ == "__main__":
    unittest.main()
