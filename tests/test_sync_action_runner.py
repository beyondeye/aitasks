#!/usr/bin/env python3
"""Tests for .aitask-scripts/lib/sync_action_runner.py — parser and the
repo-targeting command seam (no live git)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


PROJECT_DIR = Path(__file__).resolve().parents[1]
LIB_SRC = PROJECT_DIR / ".aitask-scripts" / "lib"
sys.path.insert(0, str(LIB_SRC))

import sync_action_runner  # noqa: E402
from sync_action_runner import (  # noqa: E402
    sync_batch_command,
    STATUS_AUTOMERGED,
    STATUS_CONFLICT,
    STATUS_ERROR,
    STATUS_NOTHING,
    STATUS_NO_NETWORK,
    STATUS_NO_REMOTE,
    STATUS_PULLED,
    STATUS_PUSHED,
    STATUS_SYNCED,
    parse_sync_output,
)


class ParseSyncOutputTests(unittest.TestCase):
    def test_synced(self):
        r = parse_sync_output("SYNCED")
        self.assertEqual(r.status, STATUS_SYNCED)
        self.assertEqual(r.conflicted_files, [])
        self.assertIsNone(r.error_message)

    def test_pushed(self):
        self.assertEqual(parse_sync_output("PUSHED").status, STATUS_PUSHED)

    def test_pulled(self):
        self.assertEqual(parse_sync_output("PULLED").status, STATUS_PULLED)

    def test_nothing(self):
        self.assertEqual(parse_sync_output("NOTHING").status, STATUS_NOTHING)

    def test_automerged(self):
        self.assertEqual(parse_sync_output("AUTOMERGED").status, STATUS_AUTOMERGED)

    def test_no_network(self):
        self.assertEqual(parse_sync_output("NO_NETWORK").status, STATUS_NO_NETWORK)

    def test_no_remote(self):
        self.assertEqual(parse_sync_output("NO_REMOTE").status, STATUS_NO_REMOTE)

    def test_conflict_multi(self):
        r = parse_sync_output("CONFLICT:a.md,b.md")
        self.assertEqual(r.status, STATUS_CONFLICT)
        self.assertEqual(r.conflicted_files, ["a.md", "b.md"])

    def test_conflict_single(self):
        r = parse_sync_output("CONFLICT:single.md")
        self.assertEqual(r.status, STATUS_CONFLICT)
        self.assertEqual(r.conflicted_files, ["single.md"])

    def test_conflict_bare_preserves_legacy_split(self):
        # Pure extraction: "".split(",") returns [""] in Python.
        # We preserve the historical board behavior verbatim.
        r = parse_sync_output("CONFLICT:")
        self.assertEqual(r.status, STATUS_CONFLICT)
        self.assertEqual(r.conflicted_files, [""])

    def test_error(self):
        r = parse_sync_output("ERROR:something bad happened")
        self.assertEqual(r.status, STATUS_ERROR)
        self.assertEqual(r.error_message, "something bad happened")

    def test_empty_string(self):
        r = parse_sync_output("")
        self.assertEqual(r.status, STATUS_ERROR)
        self.assertIn("empty", r.error_message or "")

    def test_only_whitespace(self):
        r = parse_sync_output("\n\n   \n")
        self.assertEqual(r.status, STATUS_ERROR)
        self.assertIn("empty", r.error_message or "")

    def test_unknown_status(self):
        r = parse_sync_output("WEIRDSTATUS")
        self.assertEqual(r.status, STATUS_ERROR)
        self.assertIn("unknown status", r.error_message or "")
        self.assertIn("WEIRDSTATUS", r.error_message or "")

    def test_first_line_only_with_trailing_noise(self):
        r = parse_sync_output("PUSHED\nextra debug noise\n")
        self.assertEqual(r.status, STATUS_PUSHED)

    def test_leading_blank_lines_stripped(self):
        r = parse_sync_output("\n\nPUSHED\n")
        self.assertEqual(r.status, STATUS_PUSHED)

    def test_per_line_whitespace_stripped(self):
        r = parse_sync_output("  PUSHED  ")
        self.assertEqual(r.status, STATUS_PUSHED)

    def test_raw_output_preserved(self):
        raw = "PUSHED\ntrailing\n"
        r = parse_sync_output(raw)
        self.assertEqual(r.raw_output, raw)


class SyncBatchCommandTests(unittest.TestCase):
    """Pure command-resolution seam for repo targeting (t1138)."""

    def test_legacy_none_is_cwd_relative(self):
        argv, cwd = sync_batch_command(None)
        self.assertEqual(argv, ["./.aitask-scripts/aitask_sync.sh", "--batch"])
        self.assertIsNone(cwd)

    def test_rooted_targets_repo_own_script(self):
        root = Path("/some/other/repo")
        argv, cwd = sync_batch_command(root)
        self.assertEqual(
            argv, [str(root / ".aitask-scripts" / "aitask_sync.sh"), "--batch"]
        )
        self.assertEqual(cwd, str(root))


class RunSyncBatchTargetingTests(unittest.TestCase):
    """Construction spy: the subprocess actually targets the selected repo
    (cwd + argv), not the launch CWD — the primary targeting guarantee."""

    def _spy(self, calls):
        def fake_run(argv, **kwargs):
            calls.append((argv, kwargs))
            return SimpleNamespace(stdout="NOTHING\n")
        return fake_run

    def test_rooted_subprocess_receives_target_cwd_and_argv(self):
        calls: list = []
        with mock.patch.object(
            sync_action_runner.subprocess, "run", self._spy(calls)
        ):
            r = sync_action_runner.run_sync_batch(repo_root=Path("/target/repo"))
        self.assertEqual(r.status, STATUS_NOTHING)
        self.assertEqual(len(calls), 1)
        argv, kwargs = calls[0]
        self.assertEqual(argv[0], "/target/repo/.aitask-scripts/aitask_sync.sh")
        self.assertEqual(argv[1], "--batch")
        self.assertEqual(kwargs["cwd"], "/target/repo")

    def test_none_root_preserves_legacy_board_invocation(self):
        # Regression pin for the board caller: default stays CWD-relative.
        calls: list = []
        with mock.patch.object(
            sync_action_runner.subprocess, "run", self._spy(calls)
        ):
            r = sync_action_runner.run_sync_batch()
        self.assertEqual(r.status, STATUS_NOTHING)
        argv, kwargs = calls[0]
        self.assertEqual(argv, ["./.aitask-scripts/aitask_sync.sh", "--batch"])
        self.assertIsNone(kwargs["cwd"])


if __name__ == "__main__":
    unittest.main()
