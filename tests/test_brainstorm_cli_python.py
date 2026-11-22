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
    _legacy_root_brief,
    display_node_description,
    init_session,
    crew_worktree,
    root_brief,
    spec_brief_lines,
)
from brainstorm.brainstorm_dag import (  # noqa: E402
    GRAPH_STATE_FILE,
    NODES_DIR,
    PROPOSALS_DIR,
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
        # Create a node with a proposal so finalize can export it (t891_4:
        # finalize exports the HEAD node's proposal, not a plan).
        wt = crew_worktree(self.task_num)
        node_id = "0"
        create_node(
            wt, node_id, [], "Test node", {},
            "Test proposal", "test_group",
        )
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


# ---------------------------------------------------------------------------
# t2339 — brief derivation skips YAML frontmatter; legacy root briefs display
# corrected.
# ---------------------------------------------------------------------------

TASK_SPEC = (
    "---\n"
    "priority: medium\n"
    "effort: low\n"
    "labels: [brainstorm]\n"
    "---\n"
    "\n"
    "## Origin\n"
    "\n"
    "Fix the widget brief.\n"
)


class TestSpecBriefLines(unittest.TestCase):

    def test_task_frontmatter_is_skipped(self):
        self.assertEqual(spec_brief_lines(TASK_SPEC),
                         ["## Origin", "Fix the widget brief."])

    def test_plain_markdown_between_rules_is_kept(self):
        # Two `---` rules around prose are NOT frontmatter: the block is not a
        # YAML mapping, so the instruction must survive.
        spec = "---\nFix the widget.\n---\nmore\n"
        self.assertEqual(spec_brief_lines(spec), ["Fix the widget.", "more"])

    def test_indented_delimiter_inside_block_scalar_does_not_close(self):
        spec = "---\ndesc: |\n  a\n  ---\n  b\nprio: x\n---\nBody\n"
        self.assertEqual(spec_brief_lines(spec), ["Body"])

    def test_unconstructible_yaml_value_keeps_old_filtering(self):
        # yaml.safe_load raises ValueError (not YAMLError) for an impossible
        # date; the documented fallback must still apply, never an exception.
        spec = "---\nreview_on: 2026-02-29\n---\nBody\n"
        self.assertEqual(spec_brief_lines(spec),
                         ["review_on: 2026-02-29", "Body"])
        self.assertEqual(root_brief(spec), "review_on: 2026-02-29")

    def test_unclosed_block_keeps_old_filtering(self):
        spec = "---\npriority: high\nno closing delimiter\n"
        self.assertEqual(spec_brief_lines(spec),
                         ["priority: high", "no closing delimiter"])

    def test_invalid_yaml_keeps_old_filtering(self):
        spec = "---\nkey: [unclosed\n---\nBody\n"
        self.assertEqual(spec_brief_lines(spec), ["key: [unclosed", "Body"])

    def test_no_frontmatter_unchanged(self):
        spec = "Test spec content.\n\nsecond line\n"
        self.assertEqual(spec_brief_lines(spec),
                         ["Test spec content.", "second line"])

    def test_body_rules_still_dropped(self):
        spec = TASK_SPEC + "\n---\n\nAfter the rule.\n"
        self.assertNotIn("---", spec_brief_lines(spec))
        self.assertIn("After the rule.", spec_brief_lines(spec))

    def test_frontmatter_only_is_empty(self):
        self.assertEqual(spec_brief_lines("---\npriority: low\n---\n"), [])
        self.assertEqual(root_brief("---\npriority: low\n---\n"),
                         "Initial specification")

    def test_legacy_brief_reproduces_the_old_bug(self):
        # The frozen derivation must still produce what pre-t2339 init wrote,
        # or existing sessions are never recognised.
        self.assertEqual(_legacy_root_brief(TASK_SPEC), "priority: medium")


class TestInitSessionRootBrief(CLITestBase):

    def test_root_description_is_the_body(self):
        init_session(self.task_num, task_file="aitasks/t999_test.md",
                     user_email="t@example.com", initial_spec=TASK_SPEC)
        node = read_yaml(str(self.wt_path / NODES_DIR / "n000_init.yaml"))
        self.assertEqual(node["description"], "## Origin")

    def test_unconstructible_date_spec_initialises_fully(self):
        spec = "---\nreview_on: 2026-02-29\n---\nBody\n"
        init_session(self.task_num, task_file="aitasks/t999_test.md",
                     user_email="t@example.com", initial_spec=spec)
        self.assertTrue((self.wt_path / SESSION_FILE).is_file())
        node = read_yaml(str(self.wt_path / NODES_DIR / "n000_init.yaml"))
        self.assertEqual(node["description"], "review_on: 2026-02-29")

    def test_brief_failure_writes_no_session_files(self):
        # The root brief is derived before any write: if derivation ever
        # fails, no half-written session (br_session.yaml without n000_init)
        # is left behind.
        import brainstorm.brainstorm_session as bs_mod
        with patch.object(bs_mod, "root_brief",
                          side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                init_session(self.task_num, task_file="aitasks/t999_test.md",
                             user_email="t@example.com",
                             initial_spec=TASK_SPEC)
        self.assertFalse((self.wt_path / SESSION_FILE).exists())
        self.assertFalse((self.wt_path / NODES_DIR).exists())

    def test_frontmatter_only_spec_falls_back(self):
        init_session(self.task_num, task_file="aitasks/t999_test.md",
                     user_email="t@example.com",
                     initial_spec="---\npriority: low\n---\n")
        node = read_yaml(str(self.wt_path / NODES_DIR / "n000_init.yaml"))
        self.assertEqual(node["description"], "Initial specification")


class TestDisplayNodeDescription(unittest.TestCase):

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.session = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def _session(self, **fields):
        data = {"initial_spec": TASK_SPEC}
        data.update(fields)
        write_yaml(str(self.session / SESSION_FILE), data)
        return data

    def test_legacy_root_brief_is_shown_corrected(self):
        self._session()
        node = {"description": "priority: medium"}
        self.assertEqual(
            display_node_description(self.session, "n000_init", node),
            "## Origin")

    def test_unconstructible_date_spec_displays_without_raising(self):
        # An older session whose spec has an impossible date: the legacy brief
        # is the date line, the new derivation falls back to the same text,
        # and display never raises.
        spec = "---\nreview_on: 2026-02-29\n---\nBody\n"
        self._session(initial_spec=spec)
        node = {"description": _legacy_root_brief(spec)}
        self.assertEqual(
            display_node_description(self.session, "n000_init", node),
            "review_on: 2026-02-29")

    def test_passed_session_data_is_used_without_reading(self):
        node = {"description": "priority: medium"}
        self.assertEqual(
            display_node_description(self.session, "n000_init", node,
                                     {"initial_spec": TASK_SPEC}),
            "## Origin")

    def test_imported_proposal_is_never_rewritten(self):
        self._session(initial_proposal_file="/abs/x.md")
        for desc in ("Imported proposal (awaiting reformat): x.md",
                     "priority: medium"):
            node = {"description": desc}
            self.assertEqual(
                display_node_description(self.session, "n000_init", node),
                desc)

    def test_hand_edited_description_unchanged(self):
        self._session()
        node = {"description": "priority: medium (edited)"}
        self.assertEqual(
            display_node_description(self.session, "n000_init", node),
            "priority: medium (edited)")

    def test_non_root_node_unchanged(self):
        self._session()
        node = {"description": "priority: medium"}
        self.assertEqual(
            display_node_description(self.session, "n001_x", node),
            "priority: medium")

    def test_missing_session_file_returns_stored(self):
        node = {"description": "priority: medium"}
        self.assertEqual(
            display_node_description(self.session, "n000_init", node),
            "priority: medium")

    def test_malformed_session_file_returns_stored(self):
        (self.session / SESSION_FILE).write_text(
            "initial_spec: [unclosed\n", encoding="utf-8")
        node = {"description": "priority: medium"}
        self.assertEqual(
            display_node_description(self.session, "n000_init", node),
            "priority: medium")

    def test_non_str_spec_or_description_returns_stored(self):
        self._session(initial_spec=["not", "a", "string"])
        node = {"description": "priority: medium"}
        self.assertEqual(
            display_node_description(self.session, "n000_init", node),
            "priority: medium")
        self.assertEqual(
            display_node_description(self.session, "n000_init",
                                     {"description": 42}, {"initial_spec": TASK_SPEC}),
            42)
        self.assertEqual(
            display_node_description(self.session, "n000_init", None,
                                     {"initial_spec": TASK_SPEC}),
            "")


if __name__ == "__main__":
    unittest.main()
