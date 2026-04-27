"""Unit tests for brainstorm_crew: input assembly, reference formatting, agent types."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Add parent paths so we can import the modules
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))

from agentcrew.agentcrew_utils import AGENTCREW_DIR, read_yaml, write_yaml
from brainstorm.brainstorm_dag import (
    GRAPH_STATE_FILE,
    NODES_DIR,
    PLANS_DIR,
    PROPOSALS_DIR,
    create_node,
)
from brainstorm.brainstorm_session import (
    GROUPS_FILE,
    SESSION_FILE,
    init_session,
)
from brainstorm.brainstorm_crew import (
    BRAINSTORM_AGENT_TYPES,
    TEMPLATE_DIR,
    _assemble_input_comparator,
    _assemble_input_detailer,
    _assemble_input_explorer,
    _assemble_input_patcher,
    _assemble_input_synthesizer,
    _format_reference_files,
    _group_seq,
    _run_addwork,
    get_agent_types,
)


class BrainstormCrewTestBase(unittest.TestCase):
    """Base class that creates a temp dir simulating a crew worktree."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="brainstorm_crew_test_")
        self.task_num = 888
        self.wt_path = Path(self.tmpdir) / AGENTCREW_DIR / f"crew-brainstorm-{self.task_num}"
        self.wt_path.mkdir(parents=True)
        # Patch AGENTCREW_DIR
        import brainstorm.brainstorm_session as bs_mod
        import agentcrew.agentcrew_utils as ac_mod
        self._orig_agentcrew_dir = ac_mod.AGENTCREW_DIR
        ac_mod.AGENTCREW_DIR = str(Path(self.tmpdir) / AGENTCREW_DIR)
        bs_mod.AGENTCREW_DIR = ac_mod.AGENTCREW_DIR

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        import brainstorm.brainstorm_session as bs_mod
        import agentcrew.agentcrew_utils as ac_mod
        ac_mod.AGENTCREW_DIR = self._orig_agentcrew_dir
        bs_mod.AGENTCREW_DIR = self._orig_agentcrew_dir

    def _init_session(self):
        """Initialize a brainstorm session in the test worktree."""
        return init_session(
            self.task_num,
            task_file=f"aitasks/t{self.task_num}_test.md",
            user_email="test@example.com",
            initial_spec="Test brainstorm session.",
        )

    def _create_test_node(self, node_id, parents=None, description="Test node",
                          dimensions=None, proposal="# Proposal", group="",
                          reference_files=None):
        """Create a test node with sane defaults."""
        return create_node(
            self.wt_path,
            node_id=node_id,
            parents=parents or [],
            description=description,
            dimensions=dimensions or {},
            proposal_content=proposal,
            group_name=group,
            reference_files=reference_files,
        )


class TestFormatReferenceFiles(unittest.TestCase):

    def test_local_files_only(self):
        result = _format_reference_files(["src/db/schema.ts", "src/api/router.ts"])
        self.assertIn("### Local", result)
        self.assertIn("- src/db/schema.ts", result)
        self.assertIn("- src/api/router.ts", result)
        self.assertNotIn("### Remote", result)

    def test_remote_urls_only(self):
        url = "https://redis.io/docs/latest/develop/data-types/"
        result = _format_reference_files([url])
        self.assertIn("### Remote (cached)", result)
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        self.assertIn(f"br_url_cache/{url_hash}.md", result)
        self.assertIn(f"(source: {url})", result)
        self.assertNotIn("### Local", result)

    def test_mixed_local_and_remote(self):
        refs = [
            "src/db/schema.ts",
            "https://www.postgresql.org/docs/current/ddl.html",
        ]
        result = _format_reference_files(refs)
        self.assertIn("### Local", result)
        self.assertIn("### Remote (cached)", result)
        # Local section comes before Remote
        local_pos = result.index("### Local")
        remote_pos = result.index("### Remote")
        self.assertLess(local_pos, remote_pos)

    def test_empty_list(self):
        result = _format_reference_files([])
        self.assertEqual(result, "")


class TestAssembleInputExplorer(BrainstormCrewTestBase):

    def test_basic_explorer_input(self):
        self._init_session()
        self._create_test_node(
            "n000_init", description="Initial node",
            dimensions={"component_database": "PostgreSQL"},
            reference_files=["src/db/schema.ts"],
        )
        # Set active dimensions in graph state
        gs = read_yaml(str(self.wt_path / GRAPH_STATE_FILE))
        gs["active_dimensions"] = ["database", "cache"]
        write_yaml(str(self.wt_path / GRAPH_STATE_FILE), gs)

        result = _assemble_input_explorer(
            self.wt_path, "n000_init",
            "Explore a serverless approach",
            ["database", "cache"],
        )
        self.assertIn("# Explorer Input", result)
        self.assertIn("## Exploration Mandate", result)
        self.assertIn("Explore a serverless approach", result)
        self.assertIn("## Baseline Node", result)
        self.assertIn(f"{NODES_DIR}/n000_init.yaml", result)
        self.assertIn(f"{PROPOSALS_DIR}/n000_init.md", result)
        self.assertIn("## Reference Files", result)
        self.assertIn("src/db/schema.ts", result)
        self.assertIn("## Active Dimensions", result)
        self.assertIn("database, cache", result)

    def test_explorer_input_with_plan(self):
        self._init_session()
        self._create_test_node("n000_init")
        # Create a plan file
        plan_dir = self.wt_path / PLANS_DIR
        plan_file = plan_dir / "n000_init_plan.md"
        plan_file.write_text("# Plan", encoding="utf-8")

        result = _assemble_input_explorer(
            self.wt_path, "n000_init", "Explore", [],
        )
        self.assertIn(f"{PLANS_DIR}/n000_init_plan.md", result)

    def test_explorer_input_no_refs(self):
        self._init_session()
        self._create_test_node("n000_init", reference_files=[])

        result = _assemble_input_explorer(
            self.wt_path, "n000_init", "Explore", [],
        )
        self.assertIn("No reference files.", result)


class TestAssembleInputComparator(BrainstormCrewTestBase):

    def test_basic_comparator_input(self):
        self._init_session()
        self._create_test_node("n001_rel")
        self._create_test_node("n002_nosql")

        result = _assemble_input_comparator(
            self.wt_path,
            ["n001_rel", "n002_nosql"],
            ["component_database", "assumption_scale"],
        )
        self.assertIn("# Comparator Input", result)
        self.assertIn("Nodes: n001_rel, n002_nosql", result)
        self.assertIn("## Node Files", result)
        self.assertIn(f"{NODES_DIR}/n001_rel.yaml", result)
        self.assertIn(f"{NODES_DIR}/n002_nosql.yaml", result)

    def test_dimensions_listed(self):
        self._init_session()
        self._create_test_node("n001_rel")

        result = _assemble_input_comparator(
            self.wt_path,
            ["n001_rel"],
            ["component_database", "tradeoff_pros", "assumption_scale"],
        )
        self.assertIn("Dimensions: component_database, tradeoff_pros, assumption_scale", result)


class TestAssembleInputSynthesizer(BrainstormCrewTestBase):

    def test_basic_synthesizer_input(self):
        self._init_session()
        self._create_test_node(
            "n001_rel", reference_files=["src/db/schema.ts", "src/api/router.ts"],
        )
        self._create_test_node(
            "n002_nosql", reference_files=["src/db/mongo.ts", "src/api/router.ts"],
        )

        result = _assemble_input_synthesizer(
            self.wt_path,
            ["n001_rel", "n002_nosql"],
            "Take database from n001, cache from n002",
        )
        self.assertIn("# Synthesizer Input", result)
        self.assertIn("## Merge Rules", result)
        self.assertIn("Take database from n001, cache from n002", result)
        self.assertIn("## Source Nodes", result)
        self.assertIn("### n001_rel", result)
        self.assertIn("### n002_nosql", result)
        self.assertIn(f"{NODES_DIR}/n001_rel.yaml", result)
        self.assertIn(f"{PROPOSALS_DIR}/n002_nosql.md", result)
        self.assertIn("## Reference Files (merged from all source nodes, deduplicated)", result)

    def test_deduplication(self):
        self._init_session()
        shared_ref = "src/api/router.ts"
        self._create_test_node("n001_rel", reference_files=[shared_ref, "src/db.ts"])
        self._create_test_node("n002_nosql", reference_files=[shared_ref, "src/mongo.ts"])

        result = _assemble_input_synthesizer(
            self.wt_path, ["n001_rel", "n002_nosql"], "merge",
        )
        # Count occurrences of the shared ref in the Reference Files section
        ref_section = result.split("## Reference Files")[1]
        self.assertEqual(ref_section.count(shared_ref), 1)


class TestAssembleInputDetailer(BrainstormCrewTestBase):

    def test_basic_detailer_input(self):
        self._init_session()
        self._create_test_node(
            "n003_hybrid",
            reference_files=["src/db/schema.ts", "https://redis.io/docs"],
        )

        result = _assemble_input_detailer(
            self.wt_path, "n003_hybrid",
            ["CLAUDE.md", "package.json"],
        )
        self.assertIn("# Detailer Input", result)
        self.assertIn("## Target Node", result)
        self.assertIn(f"{NODES_DIR}/n003_hybrid.yaml", result)
        self.assertIn(f"{PROPOSALS_DIR}/n003_hybrid.md", result)
        self.assertIn("## Reference Files", result)
        self.assertIn("src/db/schema.ts", result)
        self.assertIn("## Project Context", result)
        self.assertIn("- CLAUDE.md", result)
        self.assertIn("- package.json", result)


class TestAssembleInputPatcher(BrainstormCrewTestBase):

    def test_basic_patcher_input(self):
        self._init_session()
        self._create_test_node("n003_hybrid")
        # Create a plan file
        plan_dir = self.wt_path / PLANS_DIR
        plan_file = plan_dir / "n003_hybrid_plan.md"
        plan_file.write_text("# Plan", encoding="utf-8")

        result = _assemble_input_patcher(
            self.wt_path, "n003_hybrid",
            "Rename variable X to Y in step 3",
        )
        self.assertIn("# Patcher Input", result)
        self.assertIn("## Patch Request", result)
        self.assertIn("Rename variable X to Y in step 3", result)
        self.assertIn("## Current Node", result)
        self.assertIn(f"{NODES_DIR}/n003_hybrid.yaml", result)
        self.assertIn("this is what the patcher modifies", result)
        self.assertIn("read-only, for impact analysis", result)

    def test_patcher_input_no_plan(self):
        self._init_session()
        self._create_test_node("n003_hybrid")

        result = _assemble_input_patcher(
            self.wt_path, "n003_hybrid", "Fix step 2",
        )
        self.assertNotIn("_plan.md", result)
        self.assertIn(f"{PROPOSALS_DIR}/n003_hybrid.md", result)


class TestBrainstormAgentTypes(unittest.TestCase):

    def test_agent_types_keys(self):
        expected = {
            "explorer", "comparator", "synthesizer",
            "detailer", "patcher", "initializer",
        }
        self.assertEqual(set(BRAINSTORM_AGENT_TYPES.keys()), expected)

    def test_agent_types_structure(self):
        for name, config in BRAINSTORM_AGENT_TYPES.items():
            self.assertNotIn("agent_string", config, f"{name} should not have agent_string (comes from config)")
            self.assertIn("max_parallel", config, f"{name} missing max_parallel")
            self.assertIn("launch_mode", config, f"{name} missing launch_mode")
            self.assertIsInstance(config["max_parallel"], int)

    def test_template_files_exist(self):
        for agent_type in BRAINSTORM_AGENT_TYPES:
            template_path = TEMPLATE_DIR / f"{agent_type}.md"
            self.assertTrue(
                template_path.is_file(),
                f"Template missing: {template_path}",
            )


class TestAgentNaming(unittest.TestCase):

    def test_group_seq_with_underscore(self):
        self.assertEqual(_group_seq("explore_001"), "001")

    def test_group_seq_without_underscore(self):
        self.assertEqual(_group_seq("001"), "001")

    def test_explorer_name_with_suffix(self):
        seq = _group_seq("explore_001")
        self.assertEqual(f"explorer_{seq}a", "explorer_001a")

    def test_comparator_name(self):
        seq = _group_seq("compare_002")
        self.assertEqual(f"comparator_{seq}", "comparator_002")

    def test_explorer_name_no_suffix(self):
        seq = _group_seq("explore_001")
        self.assertEqual(f"explorer_{seq}", "explorer_001")


class TestGetAgentTypes(unittest.TestCase):
    """Test that get_agent_types reads agent_string from codeagent config."""

    FULL_DEFAULTS = {
        "brainstorm-explorer": "claudecode/opus4_7_1m",
        "brainstorm-comparator": "claudecode/sonnet4_6",
        "brainstorm-synthesizer": "claudecode/opus4_7_1m",
        "brainstorm-detailer": "claudecode/opus4_7_1m",
        "brainstorm-patcher": "claudecode/sonnet4_6",
        "brainstorm-initializer": "claudecode/sonnet4_6",
    }

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="brainstorm_config_test_")
        self.config_dir = Path(self.tmpdir) / "aitasks" / "metadata"
        self.config_dir.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_full_config(self, overrides=None):
        defaults = dict(self.FULL_DEFAULTS)
        if overrides:
            defaults.update(overrides)
        (self.config_dir / "codeagent_config.json").write_text(
            json.dumps({"defaults": defaults})
        )

    def test_missing_config_raises(self):
        """Raises RuntimeError when codeagent_config.json is missing."""
        with self.assertRaises(RuntimeError) as ctx:
            get_agent_types(config_root=Path(self.tmpdir))
        self.assertIn("codeagent_config.json", str(ctx.exception))

    def test_partial_config_raises_for_missing_type(self):
        """Raises RuntimeError when config is missing a brainstorm-<type> key."""
        config = {"defaults": {"brainstorm-explorer": "claudecode/opus4_6"}}
        (self.config_dir / "codeagent_config.json").write_text(json.dumps(config))
        with self.assertRaises(RuntimeError) as ctx:
            get_agent_types(config_root=Path(self.tmpdir))
        self.assertIn("brainstorm-comparator", str(ctx.exception))

    def test_reads_project_config(self):
        """Reads brainstorm-* keys from project codeagent_config.json."""
        self._write_full_config({"brainstorm-explorer": "geminicli/gemini_2_5_pro"})
        result = get_agent_types(config_root=Path(self.tmpdir))
        self.assertEqual(result["explorer"]["agent_string"], "geminicli/gemini_2_5_pro")
        self.assertEqual(result["comparator"]["agent_string"], "claudecode/sonnet4_6")

    def test_local_overrides_project(self):
        """Local config overrides project config for brainstorm agents."""
        self._write_full_config()
        local = {"defaults": {"brainstorm-explorer": "codex/o3"}}
        (self.config_dir / "codeagent_config.local.json").write_text(json.dumps(local))
        result = get_agent_types(config_root=Path(self.tmpdir))
        self.assertEqual(result["explorer"]["agent_string"], "codex/o3")

    def test_full_config_populates_all_types(self):
        """All five agent types get agent_string from config."""
        self._write_full_config()
        result = get_agent_types(config_root=Path(self.tmpdir))
        for agent_type in BRAINSTORM_AGENT_TYPES:
            self.assertIn("agent_string", result[agent_type])

    def test_max_parallel_preserved(self):
        """Config only changes agent_string, not max_parallel."""
        self._write_full_config({"brainstorm-explorer": "codex/o3"})
        result = get_agent_types(config_root=Path(self.tmpdir))
        self.assertEqual(result["explorer"]["max_parallel"], 2)

    def test_non_brainstorm_keys_ignored(self):
        """Non-brainstorm keys in config don't affect agent types."""
        self._write_full_config({"pick": "claudecode/opus4_7_1m", "brainstorm-detailer": "codex/o3"})
        result = get_agent_types(config_root=Path(self.tmpdir))
        self.assertEqual(result["detailer"]["agent_string"], "codex/o3")
        self.assertNotIn("pick", result)

    def test_launch_mode_override_from_project(self):
        """Project config overlays brainstorm-<type>-launch-mode."""
        self._write_full_config({"brainstorm-detailer-launch-mode": "headless"})
        result = get_agent_types(config_root=Path(self.tmpdir))
        self.assertEqual(result["detailer"]["launch_mode"], "headless")
        self.assertEqual(result["explorer"]["launch_mode"], "interactive")

    def test_launch_mode_local_overrides_project(self):
        """Local launch_mode overrides project layer."""
        self._write_full_config({"brainstorm-explorer-launch-mode": "headless"})
        local = {"defaults": {"brainstorm-explorer-launch-mode": "interactive"}}
        (self.config_dir / "codeagent_config.local.json").write_text(json.dumps(local))
        result = get_agent_types(config_root=Path(self.tmpdir))
        self.assertEqual(result["explorer"]["launch_mode"], "interactive")

    def test_launch_mode_invalid_value_falls_back(self):
        """Invalid launch_mode value warns and falls back to framework default."""
        self._write_full_config({"brainstorm-explorer-launch-mode": "bogus"})
        import io
        import contextlib
        stderr_buf = io.StringIO()
        with contextlib.redirect_stderr(stderr_buf):
            result = get_agent_types(config_root=Path(self.tmpdir))
        self.assertEqual(result["explorer"]["launch_mode"], "interactive")
        stderr_text = stderr_buf.getvalue()
        self.assertIn("brainstorm-explorer-launch-mode", stderr_text)
        self.assertIn("bogus", stderr_text)

    def test_launch_mode_default_when_config_present(self):
        """Framework launch_mode defaults are preserved when config has no overrides."""
        self._write_full_config()
        result = get_agent_types(config_root=Path(self.tmpdir))
        self.assertEqual(result["detailer"]["launch_mode"], "interactive")
        self.assertEqual(result["explorer"]["launch_mode"], "interactive")
        self.assertEqual(result["comparator"]["launch_mode"], "interactive")
        self.assertEqual(result["synthesizer"]["launch_mode"], "interactive")
        self.assertEqual(result["patcher"]["launch_mode"], "interactive")
        self.assertEqual(result["initializer"]["launch_mode"], "interactive")

    def test_launch_mode_does_not_clobber_agent_string(self):
        """Setting launch_mode in config doesn't affect agent_string."""
        self._write_full_config({"brainstorm-explorer-launch-mode": "interactive"})
        result = get_agent_types(config_root=Path(self.tmpdir))
        self.assertEqual(result["explorer"]["agent_string"], "claudecode/opus4_7_1m")
        self.assertEqual(result["explorer"]["launch_mode"], "interactive")


class TestRunAddwork(unittest.TestCase):
    """`_run_addwork` must always forward `--launch-mode` to ait crew addwork.

    Regression: the previous delta-only optimization (`if launch_mode !=
    type_default: cmd.extend(...)`) caused the flag to be dropped when the
    caller-passed value matched the brainstorm-internal type default. But
    `aitask_crew_addwork.sh` defaults to `headless` regardless of agent
    type, so agents (notably `initializer_bootstrap`) ended up registered
    as headless and hung at the first tool call (no permission UI).
    """

    def _capture_subprocess_call(self, launch_mode):
        from unittest.mock import patch

        captured = {}

        def fake_run(cmd, capture_output=False, text=False, **kwargs):
            captured["cmd"] = list(cmd)
            class Result:
                returncode = 0
                stdout = "ADDED:agent_under_test\n"
                stderr = ""
            return Result()

        with patch(
            "brainstorm.brainstorm_crew.subprocess.run", side_effect=fake_run
        ):
            _run_addwork(
                crew_id="brainstorm-999",
                agent_name="agent_under_test",
                agent_type="initializer",
                group_name="bootstrap",
                work2do_path=TEMPLATE_DIR / "initializer.md",
                launch_mode=launch_mode,
            )
        return captured["cmd"]

    def test_forwards_launch_mode_when_equal_to_type_default(self):
        """initializer's type default is 'interactive' — flag must still be passed."""
        self.assertEqual(
            BRAINSTORM_AGENT_TYPES["initializer"]["launch_mode"], "interactive"
        )
        cmd = self._capture_subprocess_call("interactive")
        self.assertIn("--launch-mode", cmd)
        idx = cmd.index("--launch-mode")
        self.assertEqual(cmd[idx + 1], "interactive")

    def test_forwards_launch_mode_when_differs_from_type_default(self):
        """Explicit override differing from the type default is forwarded."""
        cmd = self._capture_subprocess_call("headless")
        self.assertIn("--launch-mode", cmd)
        idx = cmd.index("--launch-mode")
        self.assertEqual(cmd[idx + 1], "headless")


if __name__ == "__main__":
    unittest.main()
