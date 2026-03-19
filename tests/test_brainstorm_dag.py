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
    create_node,
    get_children,
    get_dimension_fields,
    get_head,
    get_node_lineage,
    get_parents,
    list_nodes,
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
        self.assertEqual(session["status"], "init")
        self.assertEqual(session["url_cache"], "enabled")

        gs = read_yaml(str(wt / GRAPH_STATE_FILE))
        self.assertIsNone(gs["current_head"])
        self.assertEqual(gs["history"], [])
        self.assertEqual(gs["next_node_id"], 0)
        self.assertEqual(gs["active_dimensions"], [])

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

        set_head(self.wt_path, "n000_init")
        self.assertEqual(get_head(self.wt_path), "n000_init")

        gs = read_yaml(str(self.wt_path / GRAPH_STATE_FILE))
        self.assertEqual(gs["history"], ["n000_init"])

        # Set another head
        create_node(self.wt_path, "n001_alt", ["n000_init"], "Alt", {}, "# Alt", "explore_001")
        set_head(self.wt_path, "n001_alt")
        self.assertEqual(get_head(self.wt_path), "n001_alt")

        gs = read_yaml(str(self.wt_path / GRAPH_STATE_FILE))
        self.assertEqual(gs["history"], ["n000_init", "n001_alt"])


class TestGetChildren(BrainstormTestBase):

    def test_get_children_finds_reverse_refs(self):
        self._init_session()
        create_node(self.wt_path, "n000_root", [], "Root", {}, "# Root", "")
        create_node(self.wt_path, "n001_child_a", ["n000_root"], "Child A", {}, "# A", "")
        create_node(self.wt_path, "n002_child_b", ["n000_root"], "Child B", {}, "# B", "")
        create_node(self.wt_path, "n003_hybrid", ["n001_child_a", "n002_child_b"], "Hybrid", {}, "# H", "")

        children = get_children(self.wt_path, "n000_root")
        self.assertEqual(sorted(children), ["n001_child_a", "n002_child_b"])

        children_of_a = get_children(self.wt_path, "n001_child_a")
        self.assertEqual(children_of_a, ["n003_hybrid"])

        children_of_hybrid = get_children(self.wt_path, "n003_hybrid")
        self.assertEqual(children_of_hybrid, [])


class TestNextNodeId(BrainstormTestBase):

    def test_next_node_id_increments(self):
        self._init_session()
        self.assertEqual(next_node_id(self.wt_path), 0)
        self.assertEqual(next_node_id(self.wt_path), 1)
        self.assertEqual(next_node_id(self.wt_path), 2)


class TestListNodes(BrainstormTestBase):

    def test_list_nodes_sorted(self):
        self._init_session()
        create_node(self.wt_path, "n002_c", [], "C", {}, "# C", "")
        create_node(self.wt_path, "n000_a", [], "A", {}, "# A", "")
        create_node(self.wt_path, "n001_b", [], "B", {}, "# B", "")

        self.assertEqual(list_nodes(self.wt_path), ["n000_a", "n001_b", "n002_c"])


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
