"""Unit tests for brainstorm engine: DAG operations, session management, schemas."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Add parent paths so we can import the modules
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))

from brainstorm.brainstorm_schemas import (
    extract_dimensions,
    is_dimension_field,
    validate_graph_state,
    validate_node,
    validate_session,
)
from brainstorm.brainstorm_dag import (
    GRAPH_STATE_FILE,
    NODES_DIR,
    PROPOSALS_DIR,
    UMBRELLA_SUBGRAPH,
    create_node,
    delete_node_cascade,
    get_children,
    get_dimension_fields,
    get_head,
    get_node_lineage,
    get_parents,
    is_ancestor_subgraph,
    list_nodes,
    list_subgraphs,
    next_node_id,
    node_descendants_closure,
    read_node,
    read_proposal,
    set_head,
    update_node,
)
from brainstorm.brainstorm_session import (
    GROUPS_FILE,
    SESSION_FILE,
    archive_session,
    crew_worktree,
    finalize_session,
    init_session,
    list_sessions,
    load_session,
    save_session,
    session_exists,
)
from agentcrew.agentcrew_utils import AGENTCREW_DIR, read_yaml, write_yaml


class BrainstormTestBase(unittest.TestCase):
    """Base class that creates a temp dir simulating a crew worktree."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="brainstorm_test_")
        self.task_num = 999
        # Simulate crew worktree path: <tmpdir>/.aitask-crews/crew-brainstorm-999/
        self.wt_path = Path(self.tmpdir) / AGENTCREW_DIR / f"crew-brainstorm-{self.task_num}"
        self.wt_path.mkdir(parents=True)
        # Patch AGENTCREW_DIR to use our temp dir
        import brainstorm.brainstorm_session as bs_mod
        import agentcrew.agentcrew_utils as ac_mod
        self._orig_agentcrew_dir = ac_mod.AGENTCREW_DIR
        ac_mod.AGENTCREW_DIR = str(Path(self.tmpdir) / AGENTCREW_DIR)
        bs_mod.AGENTCREW_DIR = ac_mod.AGENTCREW_DIR

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        # Restore original AGENTCREW_DIR
        import brainstorm.brainstorm_session as bs_mod
        import agentcrew.agentcrew_utils as ac_mod
        ac_mod.AGENTCREW_DIR = self._orig_agentcrew_dir
        bs_mod.AGENTCREW_DIR = self._orig_agentcrew_dir

    def _init_session(self):
        """Helper: initialize a brainstorm session in the test worktree."""
        return init_session(
            self.task_num,
            task_file=f"aitasks/t{self.task_num}_test.md",
            user_email="test@example.com",
            initial_spec="Test brainstorm session.",
        )


class TestInitSession(BrainstormTestBase):

    def test_init_session_creates_structure(self):
        wt = self._init_session()
        self.assertTrue((wt / SESSION_FILE).is_file())
        self.assertTrue((wt / GRAPH_STATE_FILE).is_file())
        self.assertTrue((wt / GROUPS_FILE).is_file())
        self.assertTrue((wt / NODES_DIR).is_dir())
        self.assertTrue((wt / PROPOSALS_DIR).is_dir())

        session = read_yaml(str(wt / SESSION_FILE))
        self.assertEqual(session["task_id"], self.task_num)
        self.assertEqual(session["status"], "active")
        self.assertEqual(session["url_cache"], "enabled")

        gs = read_yaml(str(wt / GRAPH_STATE_FILE))
        self.assertEqual(gs["current_head"], "n000_init")
        # current_head is the legacy alias of the _umbrella subgraph HEAD; the
        # module-aware maps (t756) are seeded and back-fill _umbrella on set_head.
        self.assertEqual(gs["current_heads"], {"_umbrella": "n000_init"})
        self.assertEqual(gs["history"], {"_umbrella": ["n000_init"]})
        self.assertEqual(gs["module_tasks"], {})
        self.assertEqual(gs["last_synced_at"], {})
        self.assertEqual(gs["next_node_id"], 1)
        self.assertEqual(gs["active_dimensions"], [])

        # Verify auto-created root node and proposal
        self.assertTrue((wt / NODES_DIR / "n000_init.yaml").is_file())
        self.assertTrue((wt / PROPOSALS_DIR / "n000_init.md").is_file())

    def test_init_session_no_worktree(self):
        shutil.rmtree(str(self.wt_path))
        with self.assertRaises(FileNotFoundError):
            self._init_session()


class TestCreateNode(BrainstormTestBase):

    def test_create_node_files(self):
        self._init_session()
        path = create_node(
            self.wt_path,
            node_id="n000_init",
            parents=[],
            description="Initial node",
            dimensions={"component_database": "PostgreSQL"},
            proposal_content="# Proposal: Init\n\nBase proposal.",
            group_name="explore_001",
            reference_files=["src/db/schema.ts"],
        )
        self.assertTrue(path.is_file())
        self.assertTrue((self.wt_path / PROPOSALS_DIR / "n000_init.md").is_file())

    def test_read_node_roundtrip(self):
        self._init_session()
        create_node(
            self.wt_path,
            node_id="n000_init",
            parents=[],
            description="Initial node",
            dimensions={
                "component_database": "PostgreSQL",
                "assumption_scale": "10k DAU",
                "tradeoff_pros": ["Fast reads"],
            },
            proposal_content="# Init",
            group_name="explore_001",
            reference_files=["src/db/schema.ts", "https://example.com/docs"],
        )
        data = read_node(self.wt_path, "n000_init")
        self.assertEqual(data["node_id"], "n000_init")
        self.assertEqual(data["parents"], [])
        self.assertEqual(data["description"], "Initial node")
        self.assertEqual(data["component_database"], "PostgreSQL")
        self.assertEqual(data["assumption_scale"], "10k DAU")
        self.assertEqual(data["tradeoff_pros"], ["Fast reads"])
        self.assertEqual(data["reference_files"], ["src/db/schema.ts", "https://example.com/docs"])
        self.assertEqual(data["created_by_group"], "explore_001")
        self.assertIn("created_at", data)


class TestSetHead(BrainstormTestBase):

    def test_set_head_updates_state(self):
        self._init_session()
        create_node(self.wt_path, "n000_init", [], "Init", {}, "# Init", "explore_001")

        # init_session already sets head to n000_init with _umbrella history
        # ["n000_init"]; history is now a per-module map (t756).
        set_head(self.wt_path, "n000_init")
        self.assertEqual(get_head(self.wt_path), "n000_init")

        gs = read_yaml(str(self.wt_path / GRAPH_STATE_FILE))
        self.assertEqual(gs["history"], {"_umbrella": ["n000_init", "n000_init"]})

        # Set another head
        create_node(self.wt_path, "n001_alt", ["n000_init"], "Alt", {}, "# Alt", "explore_001")
        set_head(self.wt_path, "n001_alt")
        self.assertEqual(get_head(self.wt_path), "n001_alt")

        gs = read_yaml(str(self.wt_path / GRAPH_STATE_FILE))
        self.assertEqual(
            gs["history"], {"_umbrella": ["n000_init", "n000_init", "n001_alt"]}
        )
        self.assertEqual(gs["current_head"], "n001_alt")
        self.assertEqual(gs["current_heads"]["_umbrella"], "n001_alt")


class TestGetChildren(BrainstormTestBase):

    def test_get_children_finds_reverse_refs(self):
        self._init_session()
        create_node(self.wt_path, "n000_root", [], "Root", {}, "# Root", "")
        create_node(self.wt_path, "n001_child_a", ["n000_root"], "Child A", {}, "# A", "")
        create_node(self.wt_path, "n002_child_b", ["n000_root"], "Child B", {}, "# B", "")
        create_node(self.wt_path, "n003_synth", ["n001_child_a", "n002_child_b"], "Synthesized", {}, "# S", "")

        children = get_children(self.wt_path, "n000_root")
        self.assertEqual(sorted(children), ["n001_child_a", "n002_child_b"])

        children_of_a = get_children(self.wt_path, "n001_child_a")
        self.assertEqual(children_of_a, ["n003_synth"])

        children_of_synth = get_children(self.wt_path, "n003_synth")
        self.assertEqual(children_of_synth, [])


class TestNextNodeId(BrainstormTestBase):

    def test_next_node_id_increments(self):
        self._init_session()
        # init_session already consumed ID 0 for n000_init
        self.assertEqual(next_node_id(self.wt_path), 1)
        self.assertEqual(next_node_id(self.wt_path), 2)
        self.assertEqual(next_node_id(self.wt_path), 3)


class TestListNodes(BrainstormTestBase):

    def test_list_nodes_sorted(self):
        self._init_session()
        create_node(self.wt_path, "n002_c", [], "C", {}, "# C", "")
        create_node(self.wt_path, "n000_a", [], "A", {}, "# A", "")
        create_node(self.wt_path, "n001_b", [], "B", {}, "# B", "")

        # init_session auto-creates n000_init
        self.assertEqual(list_nodes(self.wt_path), ["n000_a", "n000_init", "n001_b", "n002_c"])


class TestGetNodeLineage(BrainstormTestBase):

    def test_lineage_traces_to_root(self):
        self._init_session()
        create_node(self.wt_path, "n000_root", [], "Root", {}, "# Root", "")
        create_node(self.wt_path, "n001_mid", ["n000_root"], "Mid", {}, "# Mid", "")
        create_node(self.wt_path, "n002_leaf", ["n001_mid"], "Leaf", {}, "# Leaf", "")

        lineage = get_node_lineage(self.wt_path, "n002_leaf")
        self.assertEqual(lineage, ["n000_root", "n001_mid", "n002_leaf"])

    def test_lineage_root_only(self):
        self._init_session()
        create_node(self.wt_path, "n000_root", [], "Root", {}, "# Root", "")
        self.assertEqual(get_node_lineage(self.wt_path, "n000_root"), ["n000_root"])


class TestModuleSubgraphs(BrainstormTestBase):
    """Module-decomposition data model (t756): per-subgraph HEADs, module_label,
    module-scoped lineage, and the merge ancestry guard."""

    def _module_node(self, node_id, parents, module, group="explore_001"):
        """Create a node and tag it with a module_label subgraph membership."""
        create_node(self.wt_path, node_id, parents, node_id, {}, f"# {node_id}", group)
        update_node(self.wt_path, node_id, {"module_label": module})

    def test_per_module_heads_are_independent(self):
        self._init_session()
        # _umbrella head is seeded by init_session.
        self._module_node("n010_p", ["n000_init"], "parser")
        set_head(self.wt_path, "n010_p", module="parser")

        # Each subgraph tracks its own HEAD.
        self.assertEqual(get_head(self.wt_path, module="parser"), "n010_p")
        self.assertEqual(get_head(self.wt_path, module=UMBRELLA_SUBGRAPH), "n000_init")
        # Default arg resolves the _umbrella subgraph.
        self.assertEqual(get_head(self.wt_path), "n000_init")

        gs = read_yaml(str(self.wt_path / GRAPH_STATE_FILE))
        self.assertEqual(gs["current_heads"]["parser"], "n010_p")
        self.assertEqual(gs["history"]["parser"], ["n010_p"])

    def test_umbrella_head_aliases_legacy_current_head(self):
        self._init_session()
        create_node(self.wt_path, "n001_u", ["n000_init"], "U", {}, "# U", "explore_001")
        set_head(self.wt_path, "n001_u")  # default _umbrella

        gs = read_yaml(str(self.wt_path / GRAPH_STATE_FILE))
        # Writing the _umbrella HEAD keeps the legacy current_head alias in sync.
        self.assertEqual(gs["current_head"], "n001_u")
        self.assertEqual(gs["current_heads"][UMBRELLA_SUBGRAPH], "n001_u")

    def test_get_head_falls_back_to_legacy_current_head(self):
        """A legacy single-head state (no current_heads map) still resolves."""
        self._init_session()
        # Simulate a pre-module session on disk: only current_head + list history.
        write_yaml(
            str(self.wt_path / GRAPH_STATE_FILE),
            {
                "current_head": "n000_init",
                "history": ["n000_init"],
                "next_node_id": 1,
                "active_dimensions": [],
            },
        )
        self.assertEqual(get_head(self.wt_path), "n000_init")
        # First set_head migrates the legacy list into the per-module map.
        create_node(self.wt_path, "n001_u", ["n000_init"], "U", {}, "# U", "explore_001")
        set_head(self.wt_path, "n001_u")
        gs = read_yaml(str(self.wt_path / GRAPH_STATE_FILE))
        self.assertEqual(gs["history"], {UMBRELLA_SUBGRAPH: ["n000_init", "n001_u"]})

    def test_lineage_is_scoped_to_subgraph(self):
        self._init_session()
        # _umbrella: n000_init -> n001_u ; parser subgraph roots at n010_p.
        create_node(self.wt_path, "n001_u", ["n000_init"], "U", {}, "# U", "explore_001")
        self._module_node("n010_p", ["n001_u"], "parser")
        self._module_node("n011_p", ["n010_p"], "parser")

        # Module-scoped lineage stops at the subgraph root (does not cross into
        # the _umbrella ancestor).
        self.assertEqual(
            get_node_lineage(self.wt_path, "n011_p", module="parser"),
            ["n010_p", "n011_p"],
        )

    def test_is_ancestor_subgraph_up_only(self):
        self._init_session()
        # _umbrella spine.
        create_node(self.wt_path, "n001_u", ["n000_init"], "U", {}, "# U", "explore_001")
        # parser branches off _umbrella; auth branches off parser (nested).
        self._module_node("n010_p", ["n001_u"], "parser")
        self._module_node("n020_a", ["n010_p"], "auth")

        # Ancestors → True.
        self.assertTrue(
            is_ancestor_subgraph(self.wt_path, "parser", UMBRELLA_SUBGRAPH)
        )
        self.assertTrue(is_ancestor_subgraph(self.wt_path, "auth", "parser"))
        self.assertTrue(
            is_ancestor_subgraph(self.wt_path, "auth", UMBRELLA_SUBGRAPH)
        )
        # Descendant, sibling, and self → False.
        self.assertFalse(is_ancestor_subgraph(self.wt_path, UMBRELLA_SUBGRAPH, "parser"))
        self.assertFalse(is_ancestor_subgraph(self.wt_path, "parser", "auth"))
        self.assertFalse(is_ancestor_subgraph(self.wt_path, "parser", "parser"))

    def test_create_node_writes_module_label_only_for_non_umbrella(self):
        self._init_session()
        # Non-umbrella subgraph → module_label persisted.
        create_node(
            self.wt_path, "n010_p", ["n000_init"], "P", {}, "# P",
            "explore_001", module_label="parser",
        )
        self.assertEqual(read_node(self.wt_path, "n010_p").get("module_label"), "parser")
        # _umbrella default → field omitted (legacy/umbrella nodes byte-identical).
        create_node(
            self.wt_path, "n001_u", ["n000_init"], "U", {}, "# U",
            "explore_001", module_label=UMBRELLA_SUBGRAPH,
        )
        self.assertNotIn("module_label", read_node(self.wt_path, "n001_u"))

    def test_list_subgraphs_orders_by_head_recency_umbrella_last(self):
        self._init_session()
        # Only _umbrella seeded by init.
        self.assertEqual(list_subgraphs(self.wt_path), [UMBRELLA_SUBGRAPH])
        # parser HEAD n010 (ord 10), cache HEAD n014 (ord 14 → most recent).
        self._module_node("n010_p", ["n000_init"], "parser")
        set_head(self.wt_path, "n010_p", module="parser")
        self._module_node("n014_c", ["n000_init"], "cache")
        set_head(self.wt_path, "n014_c", module="cache")
        self.assertEqual(
            list_subgraphs(self.wt_path), ["cache", "parser", UMBRELLA_SUBGRAPH]
        )

    def test_list_subgraphs_legacy_state_returns_umbrella(self):
        self._init_session()
        # Pre-module on-disk state: no current_heads map.
        write_yaml(
            str(self.wt_path / GRAPH_STATE_FILE),
            {
                "current_head": "n000_init",
                "history": ["n000_init"],
                "next_node_id": 1,
                "active_dimensions": [],
            },
        )
        self.assertEqual(list_subgraphs(self.wt_path), [UMBRELLA_SUBGRAPH])


class TestValidateNode(BrainstormTestBase):

    def test_valid_node(self):
        errors = validate_node({
            "node_id": "n000_init",
            "parents": [],
            "description": "Init",
            "proposal_file": "br_proposals/n000_init.md",
            "created_at": "2026-03-19 10:00",
            "created_by_group": "explore_001",
        })
        self.assertEqual(errors, [])

    def test_missing_required_fields(self):
        errors = validate_node({"node_id": "n000_init"})
        self.assertTrue(len(errors) >= 4)
        field_names = " ".join(errors)
        self.assertIn("parents", field_names)
        self.assertIn("description", field_names)

    def test_parents_must_be_list(self):
        errors = validate_node({
            "node_id": "n000",
            "parents": "n001",
            "description": "X",
            "proposal_file": "br_proposals/n000.md",
            "created_at": "now",
            "created_by_group": "",
        })
        self.assertTrue(any("parents" in e and "list" in e for e in errors))


class TestValidateGraphState(unittest.TestCase):
    """Graph-state validation, incl. the additive module-decomposition maps (t756)."""

    def _legacy(self):
        return {
            "current_head": "n000_init",
            "history": ["n000_init"],
            "next_node_id": 1,
            "active_dimensions": [],
        }

    def test_legacy_single_head_state_is_valid(self):
        self.assertEqual(validate_graph_state(self._legacy()), [])

    def test_module_aware_state_is_valid(self):
        data = {
            "current_head": "n005",
            "current_heads": {"_umbrella": "n005", "parser": "n012"},
            "history": {"_umbrella": ["n001", "n005"], "parser": ["n010", "n012"]},
            "next_node_id": 13,
            "active_dimensions": ["component_parser"],
            "module_tasks": {"parser": "754_1"},
            "last_synced_at": {"parser": "2026-05-04 14:30"},
        }
        self.assertEqual(validate_graph_state(data), [])

    def test_history_may_be_list_or_map_but_not_scalar(self):
        data = self._legacy()
        data["history"] = 5
        self.assertTrue(any("history" in e for e in validate_graph_state(data)))

    def test_history_map_values_must_be_lists(self):
        data = self._legacy()
        data["history"] = {"_umbrella": "n000_init"}
        self.assertTrue(any("history" in e for e in validate_graph_state(data)))

    def test_module_maps_must_be_dicts(self):
        for field in ("current_heads", "module_tasks", "last_synced_at"):
            data = self._legacy()
            data[field] = ["not", "a", "map"]
            self.assertTrue(
                any(field in e for e in validate_graph_state(data)),
                f"{field} list shape should be rejected",
            )

    def test_active_dimensions_stays_a_list(self):
        data = self._legacy()
        data["active_dimensions"] = {"parser": ["component_parser"]}
        self.assertTrue(
            any("active_dimensions" in e for e in validate_graph_state(data))
        )


class TestValidateSession(BrainstormTestBase):

    def test_invalid_status(self):
        data = {
            "task_id": 1, "task_file": "t1.md", "status": "bogus",
            "crew_id": "c1", "created_at": "now", "updated_at": "now",
            "created_by": "x@x.com", "initial_spec": "test",
        }
        errors = validate_session(data)
        self.assertTrue(any("status" in e for e in errors))

    def test_valid_session(self):
        data = {
            "task_id": 1, "task_file": "t1.md", "status": "active",
            "crew_id": "c1", "created_at": "now", "updated_at": "now",
            "created_by": "x@x.com", "initial_spec": "test",
        }
        self.assertEqual(validate_session(data), [])


class TestFinalizeSession(BrainstormTestBase):

    def test_finalize_exports_proposal(self):
        # t891_4: finalize exports the HEAD node's *proposal* to aiplans/
        # (the plan-export path was retired with the plan layer).
        self._init_session()
        create_node(
            self.wt_path, "n000_init", [], "Init", {},
            "# Proposal: Init\n\nDesign details.", "",
        )
        set_head(self.wt_path, "n000_init")

        dest_dir = os.path.join(self.tmpdir, "aiplans")
        dest = finalize_session(self.task_num, plan_dest_dir=dest_dir)
        self.assertTrue(os.path.isfile(dest))
        self.assertIn("Design details.", Path(dest).read_text())

        # Check session status updated
        session = load_session(self.task_num)
        self.assertEqual(session["status"], "completed")

    def test_finalize_blocked_by_unsynced_module(self):
        # t891_4: finalize must refuse to export the umbrella proposal while a
        # fast-tracked module is in implementation but not yet synced — its real
        # plan lives in the linked aitask. After a module_sync stamp, it exports.
        from brainstorm.brainstorm_session import (
            _write_last_synced,
            _write_module_task,
        )
        self._init_session()
        wt = self.wt_path
        # Umbrella head with the proposal that would be exported once unblocked.
        create_node(wt, "n000_init", [], "Init", {}, "# Proposal body", "")
        set_head(wt, "n000_init")
        # A fast-tracked module subgraph: >1 node + a linked task.
        create_node(wt, "n001_auth", [], "Auth root", {}, "## auth\n", "g",
                    module_label="auth")
        create_node(wt, "n002_auth", ["n001_auth"], "Auth refine", {},
                    "## auth2\n", "g", module_label="auth")
        set_head(wt, "n002_auth", module="auth")
        _write_module_task(wt, "auth", f"{self.task_num}_2")

        cwd = os.getcwd()
        os.chdir(self.tmpdir)
        try:
            # Linked task Implementing → module in_implementation, unsynced.
            task_dir = Path("aitasks") / f"t{self.task_num}"
            task_dir.mkdir(parents=True, exist_ok=True)
            (task_dir / f"t{self.task_num}_2_auth.md").write_text(
                "---\nstatus: Implementing\nissue_type: feature\n---\n\nbody\n",
                encoding="utf-8",
            )
            dest_dir = os.path.join(self.tmpdir, "aiplans")
            with self.assertRaises(ValueError) as ctx:
                finalize_session(self.task_num, plan_dest_dir=dest_dir)
            self.assertIn("auth", str(ctx.exception))
            self.assertIn("module_sync", str(ctx.exception))

            # After a sync stamp, the export proceeds.
            _write_last_synced(wt, "auth", "2026-06-11 12:00")
            dest = finalize_session(self.task_num, plan_dest_dir=dest_dir)
            self.assertTrue(os.path.isfile(dest))
            self.assertIn("# Proposal body", Path(dest).read_text())
        finally:
            os.chdir(cwd)


class TestDimensionFields(BrainstormTestBase):

    def test_extract_dimensions(self):
        data = {
            "node_id": "n000",
            "parents": [],
            "component_database": "PostgreSQL",
            "assumption_scale": "10k",
            "tradeoff_pros": ["Fast"],
            "requirements_fixed": ["Sub-100ms"],
            "description": "should not appear",
        }
        dims = get_dimension_fields(data)
        self.assertEqual(set(dims.keys()), {
            "component_database", "assumption_scale",
            "tradeoff_pros", "requirements_fixed",
        })
        self.assertNotIn("node_id", dims)
        self.assertNotIn("description", dims)

    def test_is_dimension_field(self):
        self.assertTrue(is_dimension_field("component_database"))
        self.assertTrue(is_dimension_field("assumption_scale"))
        self.assertTrue(is_dimension_field("tradeoff_cons"))
        self.assertTrue(is_dimension_field("requirements_mutable"))
        self.assertFalse(is_dimension_field("node_id"))
        self.assertFalse(is_dimension_field("parents"))


class TestSessionHelpers(BrainstormTestBase):

    def test_session_exists(self):
        self.assertFalse(session_exists(self.task_num))
        self._init_session()
        self.assertTrue(session_exists(self.task_num))

    def test_save_and_load_session(self):
        self._init_session()
        save_session(self.task_num, {"status": "active"})
        data = load_session(self.task_num)
        self.assertEqual(data["status"], "active")

    def test_archive_session(self):
        self._init_session()
        archive_session(self.task_num)
        data = load_session(self.task_num)
        self.assertEqual(data["status"], "archived")

    def test_list_sessions(self):
        self._init_session()
        sessions = list_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["task_num"], str(self.task_num))

    def test_read_proposal(self):
        self._init_session()
        content = "# Proposal\n\nDetailed content."
        create_node(self.wt_path, "n000_init", [], "Init", {}, content, "")
        self.assertEqual(read_proposal(self.wt_path, "n000_init"), content)

    def test_update_node(self):
        self._init_session()
        create_node(self.wt_path, "n000_init", [], "Init", {}, "# Init", "")
        update_node(self.wt_path, "n000_init", {"description": "Updated"})
        data = read_node(self.wt_path, "n000_init")
        self.assertEqual(data["description"], "Updated")
        # Original fields preserved
        self.assertEqual(data["node_id"], "n000_init")


class TestDeleteNodeCascade(BrainstormTestBase):
    """Cascade node-delete over synthetic (dummy-data) sessions (t925)."""

    def setUp(self):
        super().setUp()
        for d in (NODES_DIR, PROPOSALS_DIR):
            (self.wt_path / d).mkdir(parents=True, exist_ok=True)

    def _node(self, nid, parents, module=None):
        create_node(
            self.wt_path, nid, parents, nid, {}, f"# {nid}",
            module_label=module,
        )

    def _set_gs(self, **fields):
        write_yaml(str(self.wt_path / GRAPH_STATE_FILE), fields)

    def _gs(self):
        return read_yaml(str(self.wt_path / GRAPH_STATE_FILE))

    def _node_exists(self, nid):
        return (self.wt_path / NODES_DIR / f"{nid}.yaml").is_file()

    def test_linear_chain_cascade_and_head_repoint(self):
        self._node("n000_a", [])
        self._node("n001_b", ["n000_a"])
        self._node("n002_c", ["n001_b"])
        self._set_gs(
            current_head="n002_c",
            current_heads={"_umbrella": "n002_c"},
            history={"_umbrella": ["n000_a", "n001_b", "n002_c"]},
            module_tasks={}, last_synced_at={},
        )

        report = delete_node_cascade(self.wt_path, "n001_b")

        self.assertFalse(report["missing_root"])
        self.assertEqual(set(report["deleted"]), {"n001_b", "n002_c"})
        # Root survives; deleted nodes and their files are gone.
        self.assertTrue(self._node_exists("n000_a"))
        self.assertFalse(self._node_exists("n001_b"))
        self.assertFalse(self._node_exists("n002_c"))
        self.assertFalse((self.wt_path / PROPOSALS_DIR / "n002_c.md").is_file())
        # HEAD re-points to the surviving parent (both maps consistent).
        gs = self._gs()
        self.assertEqual(gs["current_heads"]["_umbrella"], "n000_a")
        self.assertEqual(gs["current_head"], "n000_a")
        self.assertEqual(report["head_repoints"], {"_umbrella": "n000_a"})
        # History pruned to surviving ids.
        self.assertEqual(gs["history"]["_umbrella"], ["n000_a"])

    def test_delete_non_root_parentless_head_clears_head(self):
        self._node("n000_root", [])
        self._node("n010_a", [])
        self._set_gs(
            current_head="n010_a",
            current_heads={"_umbrella": "n010_a"},
            history={"_umbrella": ["n000_root", "n010_a"]},
        )

        report = delete_node_cascade(self.wt_path, "n010_a")

        self.assertEqual(report["deleted"], ["n010_a"])
        self.assertEqual(report["head_repoints"], {"_umbrella": None})
        gs = self._gs()
        self.assertNotIn("_umbrella", gs.get("current_heads", {}))
        self.assertIsNone(gs.get("current_head"))
        self.assertTrue(self._node_exists("n000_root"))

    def test_root_delete_is_refused_without_mutation(self):
        self._node("n000_root", [])
        self._node("n001_child", ["n000_root"])
        self._set_gs(
            current_head="n001_child",
            current_heads={"_umbrella": "n001_child"},
            history={"_umbrella": ["n000_root", "n001_child"]},
        )

        before = self._gs()
        report = delete_node_cascade(self.wt_path, "n000_root")

        self.assertFalse(report["missing_root"])
        self.assertTrue(report["refused_root"])
        self.assertEqual(report["deleted"], [])
        self.assertTrue(self._node_exists("n000_root"))
        self.assertTrue(self._node_exists("n001_child"))
        self.assertEqual(self._gs(), before)

    def test_linked_module_task_preserved(self):
        # Umbrella root + a 'parser' module subgraph linked to a task.
        self._node("n000_init", [])
        self._node("n010_p", ["n000_init"], module="parser")
        self._node("n011_p", ["n010_p"], module="parser")
        self._set_gs(
            current_head="n000_init",
            current_heads={"_umbrella": "n000_init", "parser": "n011_p"},
            history={"_umbrella": ["n000_init"],
                     "parser": ["n010_p", "n011_p"]},
            module_tasks={"parser": 123}, last_synced_at={"parser": "2026-01-01"},
        )

        report = delete_node_cascade(self.wt_path, "n010_p")

        self.assertEqual(set(report["deleted"]), {"n010_p", "n011_p"})
        gs = self._gs()
        # Linked task + sync metadata are untouched.
        self.assertEqual(gs["module_tasks"], {"parser": 123})
        self.assertEqual(gs["last_synced_at"], {"parser": "2026-01-01"})
        # parser history fully pruned; umbrella untouched.
        self.assertEqual(gs["history"]["parser"], [])
        self.assertEqual(gs["history"]["_umbrella"], ["n000_init"])

    def test_multiparent_overdelete_pulls_in_synth(self):
        self._node("n000_a", [])
        self._node("n001_b", ["n000_a"])
        self._node("n002_x", ["n000_a"])
        self._node("n003_synth", ["n001_b", "n002_x"])
        self._set_gs(current_heads={"_umbrella": "n003_synth"})

        report = delete_node_cascade(self.wt_path, "n001_b")

        self.assertIn("n003_synth", report["deleted"])
        self.assertTrue(self._node_exists("n000_a"))
        self.assertTrue(self._node_exists("n002_x"))
        self.assertFalse(self._node_exists("n003_synth"))

    def test_legacy_list_history_and_alias(self):
        # Pre-module session: legacy current_head + linear history list.
        self._node("n000_a", [])
        self._node("n001_b", ["n000_a"])
        self._node("n002_c", ["n001_b"])
        self._set_gs(
            current_head="n002_c",
            history=["n000_a", "n001_b", "n002_c"],
        )

        report = delete_node_cascade(self.wt_path, "n001_b")

        gs = self._gs()
        self.assertEqual(gs["current_head"], "n000_a")
        self.assertEqual(gs["history"], {"_umbrella": ["n000_a"]})
        self.assertEqual(report["head_repoints"], {"_umbrella": "n000_a"})

    def test_missing_root(self):
        self._set_gs(current_heads={"_umbrella": "n000_a"})
        report = delete_node_cascade(self.wt_path, "nope")
        self.assertTrue(report["missing_root"])
        self.assertFalse(report["refused_root"])
        self.assertEqual(report["deleted"], [])

    def test_closure_parity_with_report(self):
        self._node("n000_a", [])
        self._node("n001_b", ["n000_a"])
        self._node("n002_c", ["n001_b"])
        self._set_gs(current_heads={"_umbrella": "n002_c"})

        closure = node_descendants_closure(self.wt_path, "n001_b")
        report = delete_node_cascade(self.wt_path, "n001_b")
        self.assertEqual(closure, report["deleted"])


if __name__ == "__main__":
    unittest.main()
