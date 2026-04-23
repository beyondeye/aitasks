"""Unit tests for brainstorm_cli.py — CLI entry point for brainstorm sessions."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

# Add parent paths so we can import the modules
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))

from brainstorm.brainstorm_cli import main  # noqa: E402
from brainstorm.brainstorm_session import (  # noqa: E402
    SESSION_FILE,
    init_session,
    crew_worktree,
)
from brainstorm.brainstorm_dag import (  # noqa: E402
    GRAPH_STATE_FILE,
    NODES_DIR,
    PROPOSALS_DIR,
    PLANS_DIR,
    create_node,
    set_head,
)
from agentcrew.agentcrew_utils import (  # noqa: E402
    AGENTCREW_DIR,
    read_yaml,
    write_yaml,
)


class CLITestBase(unittest.TestCase):
    """Base class that creates a temp dir simulating crew worktrees."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="brainstorm_cli_test_")
        self.task_num = 999
        # Create the crew worktree directory
        self.wt_path = Path(self.tmpdir) / AGENTCREW_DIR / f"crew-brainstorm-{self.task_num}"
        self.wt_path.mkdir(parents=True)
        # Patch AGENTCREW_DIR
        import brainstorm.brainstorm_session as bs_mod
        import agentcrew.agentcrew_utils as ac_mod
        self._orig_agentcrew_dir = ac_mod.AGENTCREW_DIR
        ac_mod.AGENTCREW_DIR = str(Path(self.tmpdir) / AGENTCREW_DIR)
        bs_mod.AGENTCREW_DIR = ac_mod.AGENTCREW_DIR
        # Create a fake crew status file
        write_yaml(str(self.wt_path / "_crew_status.yaml"), {
            "status": "Initializing",
            "progress": 0,
        })

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        import brainstorm.brainstorm_session as bs_mod
        import agentcrew.agentcrew_utils as ac_mod
        ac_mod.AGENTCREW_DIR = self._orig_agentcrew_dir
        bs_mod.AGENTCREW_DIR = self._orig_agentcrew_dir

    def _init_session(self):
        """Helper: initialize a brainstorm session."""
        return init_session(
            self.task_num,
            task_file=f"aitasks/t{self.task_num}_test.md",
            user_email="test@example.com",
            initial_spec="Test spec content.",
        )

    def _capture_cli(self, argv: list[str]) -> tuple[str, str]:
        """Run CLI main() and capture stdout/stderr."""
        stdout = StringIO()
        stderr = StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            main(argv)
        return stdout.getvalue().strip(), stderr.getvalue().strip()


class TestExistsCommand(CLITestBase):

    def test_not_exists_before_init(self):
        out, _ = self._capture_cli(["exists", "--task-num", str(self.task_num)])
        self.assertEqual(out, "NOT_EXISTS")

    def test_exists_after_init(self):
        self._init_session()
        out, _ = self._capture_cli(["exists", "--task-num", str(self.task_num)])
        self.assertEqual(out, "EXISTS")


class TestInitCommand(CLITestBase):

    def test_init_creates_session(self):
        # Write spec to a temp file
        spec_file = Path(self.tmpdir) / "spec.md"
        spec_file.write_text("Test spec content.", encoding="utf-8")

        out, _ = self._capture_cli([
            "init",
            "--task-num", str(self.task_num),
            "--task-file", f"aitasks/t{self.task_num}_test.md",
            "--email", "test@example.com",
            "--spec-file", str(spec_file),
        ])

        self.assertTrue(out.startswith("SESSION_PATH:"))
        session_path = Path(out.split(":", 1)[1])
        self.assertTrue((session_path / SESSION_FILE).is_file())

    def test_init_without_spec_file(self):
        out, _ = self._capture_cli([
            "init",
            "--task-num", str(self.task_num),
            "--task-file", f"aitasks/t{self.task_num}_test.md",
            "--email", "test@example.com",
        ])
        self.assertTrue(out.startswith("SESSION_PATH:"))


class TestStatusCommand(CLITestBase):

    def test_status_shows_session_info(self):
        self._init_session()
        out, _ = self._capture_cli(["status", "--task-num", str(self.task_num)])
        self.assertIn("task_id:", out)
        self.assertIn("status: active", out)
        self.assertIn("nodes: 1", out)

    def test_status_nonexistent_exits(self):
        with self.assertRaises(SystemExit) as ctx:
            self._capture_cli(["status", "--task-num", "12345"])
        self.assertNotEqual(ctx.exception.code, 0)


class TestListCommand(CLITestBase):

    def test_list_empty(self):
        # Remove the worktree so there's nothing to list
        shutil.rmtree(str(self.wt_path))
        out, _ = self._capture_cli(["list"])
        self.assertIn("No brainstorm sessions", out)

    def test_list_shows_session(self):
        self._init_session()
        out, _ = self._capture_cli(["list"])
        self.assertIn(str(self.task_num), out)
        self.assertIn("init", out)


class TestArchiveCommand(CLITestBase):

    def test_archive_sets_crew_status(self):
        self._init_session()
        # Create a node with a plan so finalize can work
        wt = crew_worktree(self.task_num)
        node_id = "0"
        create_node(
            wt, node_id, [], "Test node", {},
            "Test proposal", "test_group",
        )
        # Create a plan file for the node
        plan_path = wt / PLANS_DIR / f"{node_id}_plan.md"
        plan_path.write_text("# Test plan", encoding="utf-8")
        # Update node to reference the plan
        from brainstorm.brainstorm_dag import update_node
        update_node(wt, node_id, {"plan_file": f"{PLANS_DIR}/{node_id}_plan.md"})
        # Set HEAD
        set_head(wt, node_id)

        # Create aiplans directory
        aiplans = Path(self.tmpdir) / "aiplans"
        aiplans.mkdir(exist_ok=True)

        # We need to change to tmpdir for finalize_session to find aiplans/
        old_cwd = os.getcwd()
        os.chdir(self.tmpdir)
        try:
            # Run finalize first, then archive
            self._capture_cli(["finalize", "--task-num", str(self.task_num)])
            self._capture_cli(["archive", "--task-num", str(self.task_num)])
        finally:
            os.chdir(old_cwd)

        # Verify crew status was set to Completed
        crew_status = read_yaml(str(wt / "_crew_status.yaml"))
        self.assertEqual(crew_status["status"], "Completed")

    def test_archive_nonexistent_exits(self):
        with self.assertRaises(SystemExit) as ctx:
            self._capture_cli(["archive", "--task-num", "12345"])
        self.assertNotEqual(ctx.exception.code, 0)


class TestInitWithProposalFile(CLITestBase):
    """Tests for --proposal-file flag on `brainstorm_cli init`."""

    def _make_proposal(self, body: str = "# Example proposal\n\nBody line.\n") -> Path:
        """Auto-generate a test proposal markdown file in the scratch tmpdir."""
        p = Path(self.tmpdir) / "imported_proposal.md"
        p.write_text(body, encoding="utf-8")
        return p

    def test_happy_path_emits_markers_and_records_path(self):
        proposal = self._make_proposal()

        with patch("brainstorm.brainstorm_crew.register_initializer",
                   return_value="initializer_bootstrap") as mock_reg, \
             patch("agentcrew.agentcrew_runner_control.start_runner",
                   return_value=True) as mock_start:
            out, _ = self._capture_cli([
                "init",
                "--task-num", str(self.task_num),
                "--task-file", f"aitasks/t{self.task_num}_test.md",
                "--email", "test@example.com",
                "--proposal-file", str(proposal),
            ])

        self.assertIn("SESSION_PATH:", out)
        self.assertIn("INITIALIZER_AGENT:initializer_bootstrap", out)
        self.assertIn(f"RUNNER_STARTED:brainstorm-{self.task_num}", out)

        session = read_yaml(str(self.wt_path / SESSION_FILE))
        self.assertEqual(session["initial_proposal_file"], str(proposal.resolve()))

        placeholder = (self.wt_path / PROPOSALS_DIR / "n000_init.md").read_text()
        self.assertIn(proposal.name, placeholder)
        self.assertIn("Awaiting initializer agent output", placeholder)

        mock_reg.assert_called_once()
        reg_kwargs = mock_reg.call_args.kwargs
        self.assertEqual(reg_kwargs["imported_path"], str(proposal.resolve()))
        self.assertEqual(reg_kwargs["crew_id"], f"brainstorm-{self.task_num}")
        mock_start.assert_called_once_with(f"brainstorm-{self.task_num}")

    def test_runner_start_failure_emits_stderr_warning(self):
        proposal = self._make_proposal()
        with patch("brainstorm.brainstorm_crew.register_initializer",
                   return_value="initializer_bootstrap"), \
             patch("agentcrew.agentcrew_runner_control.start_runner",
                   return_value=False):
            out, err = self._capture_cli([
                "init",
                "--task-num", str(self.task_num),
                "--task-file", f"aitasks/t{self.task_num}_test.md",
                "--proposal-file", str(proposal),
            ])
        self.assertIn("INITIALIZER_AGENT:initializer_bootstrap", out)
        self.assertNotIn("RUNNER_STARTED:", out)
        self.assertIn(f"RUNNER_START_FAILED:brainstorm-{self.task_num}", err)

    def test_missing_proposal_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            self._capture_cli([
                "init",
                "--task-num", str(self.task_num),
                "--task-file", f"aitasks/t{self.task_num}_test.md",
                "--proposal-file", "/does/not/exist.md",
            ])

    def test_backward_compat_no_flag(self):
        """Without --proposal-file, no new markers and no agent registration."""
        with patch("brainstorm.brainstorm_crew.register_initializer") as mock_reg, \
             patch("agentcrew.agentcrew_runner_control.start_runner") as mock_start:
            out, _ = self._capture_cli([
                "init",
                "--task-num", str(self.task_num),
                "--task-file", f"aitasks/t{self.task_num}_test.md",
            ])

        self.assertIn("SESSION_PATH:", out)
        self.assertNotIn("INITIALIZER_AGENT:", out)
        self.assertNotIn("RUNNER_STARTED:", out)

        session = read_yaml(str(self.wt_path / SESSION_FILE))
        self.assertNotIn("initial_proposal_file", session)

        mock_reg.assert_not_called()
        mock_start.assert_not_called()


if __name__ == "__main__":
    unittest.main()
