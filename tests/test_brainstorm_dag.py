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
    PLANS_DIR,
    PROPOSALS_DIR,
    UMBRELLA_SUBGRAPH,
    create_node,
    get_children,
    get_dimension_fields,
    get_head,
    get_node_lineage,
    get_parents,
    is_ancestor_subgraph,
    list_nodes,
    list_subgraphs,
    next_node_id,
    read_node,
    read_plan,
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
        self.assertTrue((wt / PLANS_DIR).is_dir())

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

    def test_finalize_copies_plan(self):
        self._init_session()
        # Create a node with a plan
        create_node(self.wt_path, "n000_init", [], "Init", {}, "# Init", "")
        # Write plan file
        plan_dir = self.wt_path / PLANS_DIR
        plan_file = plan_dir / "n000_init_plan.md"
        plan_file.write_text("# Plan: Init\n\nStep 1: Do stuff.", encoding="utf-8")
        # Update node to reference plan
        update_node(self.wt_path, "n000_init", {
            "plan_file": f"{PLANS_DIR}/n000_init_plan.md"
        })
        set_head(self.wt_path, "n000_init")

        # Finalize
        dest_dir = os.path.join(self.tmpdir, "aiplans")
        dest = finalize_session(self.task_num, plan_dest_dir=dest_dir)
        self.assertTrue(os.path.isfile(dest))
        self.assertIn("Step 1: Do stuff.", Path(dest).read_text())

        # Check session status updated
        session = load_session(self.task_num)
        self.assertEqual(session["status"], "completed")


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


if __name__ == "__main__":
    unittest.main()
