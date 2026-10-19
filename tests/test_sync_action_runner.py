#!/usr/bin/env python3
"""Tests for .aitask-scripts/lib/sync_action_runner.py — parser, the
repo-targeting command seam (no live git), the conflict modal and the
data-conflict agent prompt."""
from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


PROJECT_DIR = Path(__file__).resolve().parents[1]
LIB_SRC = PROJECT_DIR / ".aitask-scripts" / "lib"
sys.path.insert(0, str(LIB_SRC))

from textual.app import App, ComposeResult  # noqa: E402
from textual.widgets import Button, Label  # noqa: E402

import sync_action_runner  # noqa: E402
from sync_action_runner import (  # noqa: E402
    CONFLICT_CHOICE_AGENT,
    CONFLICT_CHOICE_INTERACTIVE,
    SyncConflictScreen,
    build_data_conflict_prompt,
    sync_batch_command,
    STATUS_AUTOMERGED,
    STATUS_CONFLICT,
    STATUS_ERROR,
    STATUS_MERGED,
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

    def test_merged(self):
        # t1731: a diverged branch converged by guarded merge and pushed. A plain
        # success token -- never a failure, and never a deferral.
        r = parse_sync_output("MERGED")
        self.assertEqual(r.status, STATUS_MERGED)
        self.assertIsNone(r.error_message)
        self.assertIsNone(r.deferred_reason)

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
            sync_action_runner, "_run_sync_process", self._spy(calls)
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
            sync_action_runner, "_run_sync_process", self._spy(calls)
        ):
            r = sync_action_runner.run_sync_batch()
        self.assertEqual(r.status, STATUS_NOTHING)
        argv, kwargs = calls[0]
        self.assertEqual(argv, ["./.aitask-scripts/aitask_sync.sh", "--batch"])
        self.assertIsNone(kwargs["cwd"])


class TokenContractTest(unittest.TestCase):
    """The wire protocol spans two languages; DERIVE it rather than restate it.

    `aitask_sync.sh` emits every status through `batch_out`, and
    `parse_sync_output` fails CLOSED — an unrecognised line becomes
    STATUS_ERROR, which the board renders red and the syncer escalates into an
    offer to spawn a code agent. So a token added to the shell and missed here
    degrades silently into a fake failure. These tests read the shell source and
    assert the two sides still agree.
    """

    SYNC_SH = PROJECT_DIR / ".aitask-scripts" / "aitask_sync.sh"

    @staticmethod
    def _code_only(source: str) -> str:
        """Drop whole-line shell comments before scanning for call sites.

        These scans mean to find literals that REACH `batch_out`, and a literal
        discussed in a comment reaches nothing. Without this, prose explaining
        the protocol is indistinguishable from an emission: a comment in
        aitask_sync.sh reading `batch_out "<literal>"` was picked up as a
        declared status token and failed the contract below. Narrowing to code
        makes the scan more accurate, not more permissive.
        """
        return "\n".join(
            ln for ln in source.split("\n") if not ln.lstrip().startswith("#")
        )

    @staticmethod
    def _emitted_tokens(source: str) -> set[str]:
        """Every literal reaching `batch_out`, reduced to its bare token."""
        import re
        out = set()
        for raw in re.findall(r'batch_out\s+"([^"]*)"',
                              TokenContractTest._code_only(source)):
            # Strip a `:<detail>` suffix and any shell interpolation.
            token = raw.split(":", 1)[0]
            if "$" in token or not token:
                continue
            out.add(token)
        return out

    def test_every_emitted_token_is_recognised(self):
        tokens = self._emitted_tokens(self.SYNC_SH.read_text())
        self.assertTrue(tokens, "found no batch_out literals — the scan broke")
        for token in sorted(tokens):
            # CONFLICT:/ERROR:/DEFERRED: are prefix forms; give them a suffix so
            # the bare word is not what gets parsed.
            if token == "DEFERRED":
                # Must be a declared reason now that the branch fails closed.
                probe = "DEFERRED:protected_dirty"
            elif token in {"CONFLICT", "ERROR"}:
                probe = f"{token}:x"
            else:
                probe = token
            result = sync_action_runner.parse_sync_output(probe)
            if token == "ERROR":
                self.assertEqual(result.status, STATUS_ERROR)
                continue
            self.assertNotEqual(
                result.status, STATUS_ERROR,
                f"{token!r} is emitted by aitask_sync.sh but parse_sync_output "
                f"does not recognise it (got {result.error_message!r})",
            )

    def test_a_bogus_token_still_fails(self):
        # Negative control: without this, the assertion above would also pass
        # against a parser that accepted anything.
        self.assertEqual(
            sync_action_runner.parse_sync_output("TOTALLY_MADE_UP").status,
            STATUS_ERROR,
        )

    def test_every_emitted_deferred_reason_is_declared(self):
        """`DEFERRED:<reason>` reasons are a closed set on both sides."""
        import re
        source = self.SYNC_SH.read_text()
        reasons = set()
        for raw in re.findall(r'batch_out\s+"DEFERRED:([^":$]*)',
                              self._code_only(source)):
            if raw:
                reasons.add(raw)
        self.assertTrue(reasons, "found no DEFERRED literals — the scan broke")
        unknown = reasons - sync_action_runner.DEFERRED_REASONS
        self.assertFalse(
            unknown,
            f"aitask_sync.sh emits DEFERRED reason(s) {sorted(unknown)} that "
            f"sync_action_runner.DEFERRED_REASONS does not declare",
        )

    def test_an_unknown_deferral_reason_fails_closed(self):
        """A shell-side typo must NOT become a benign warning.

        Both TUIs render STATUS_DEFERRED as `severity="warning"` and the syncer
        deliberately skips its failure capture for it, so a reason this side
        does not know about would silently suppress a real problem.
        """
        r = sync_action_runner.parse_sync_output("DEFERRED:misspelled_reason")
        self.assertEqual(r.status, STATUS_ERROR)
        self.assertIn("misspelled_reason", r.error_message or "")
        self.assertIsNone(r.deferred_reason)

    def test_an_empty_deferral_reason_fails_closed(self):
        r = sync_action_runner.parse_sync_output("DEFERRED:")
        self.assertEqual(r.status, STATUS_ERROR)
        r2 = sync_action_runner.parse_sync_output("DEFERRED::detail only")
        self.assertEqual(r2.status, STATUS_ERROR)

    def test_every_declared_reason_is_accepted(self):
        # The positive half: the closed set must actually round-trip, or the
        # guard above would be rejecting valid traffic.
        for reason in sorted(sync_action_runner.DEFERRED_REASONS):
            r = sync_action_runner.parse_sync_output(f"DEFERRED:{reason}:d")
            self.assertEqual(r.status, sync_action_runner.STATUS_DEFERRED, reason)
            self.assertEqual(r.deferred_reason, reason)

    def test_deferred_detail_may_contain_colons(self):
        r = sync_action_runner.parse_sync_output("DEFERRED:protected_dirty:a:b:c")
        self.assertEqual(r.deferred_reason, "protected_dirty")
        self.assertEqual(r.deferred_detail, "a:b:c")
        # A deferral is benign: it must never look like a failure to a consumer
        # inspecting the dataclass.
        self.assertIsNone(r.error_message)


# The eleven-column record, as a helper so each test states only what it varies.
def _rec(sub_reason="live_lock", task="10", path="aitasks/t10.md",
         tree_state="tracked", holder="self", email="me@x.com",
         host="omg16", pid="4242", pane="", pane_state="", action="do the thing"):
    return "DEFERRED_FILE:" + "|".join([
        sub_reason, task, path, tree_state, holder,
        email, host, pid, pane, pane_state, action,
    ])


_STATUS = "DEFERRED:protected_dirty:1 file(s) block the rebase: live_lock=1"


class DeferredFileParsingTests(unittest.TestCase):
    """The per-file continuation records (t1725_3).

    These carry everything a consumer renders, so the parser must either produce
    a faithful record or fail closed. Silently dropping one is the worst
    outcome: it renders a deferral with files missing from it, which is the
    opaque behaviour this protocol replaced.
    """

    def test_records_are_collected_under_a_deferred_status(self):
        r = parse_sync_output(_STATUS + "\n" + _rec() + "\n")
        self.assertEqual(r.status, sync_action_runner.STATUS_DEFERRED)
        self.assertEqual(r.deferred_reason, "protected_dirty")
        self.assertEqual(len(r.deferred_files), 1)
        f = r.deferred_files[0]
        self.assertEqual(f.sub_reason, "live_lock")
        self.assertEqual(f.task, "10")
        self.assertEqual(f.path, "aitasks/t10.md")
        self.assertEqual(f.tree_state, "tracked")
        self.assertEqual(f.holder, "self")
        self.assertEqual(f.pid, "4242")

    def test_no_records_on_a_non_deferred_status(self):
        # Belt and braces for the shell-side rule that records are emitted only
        # alongside a DEFERRED status line: even if one leaked out after a
        # PUSHED, it must not be reported as a deferral's file list.
        r = parse_sync_output("PUSHED\n" + _rec() + "\n")
        self.assertEqual(r.status, STATUS_PUSHED)
        self.assertEqual(r.deferred_files, [])

    def test_a_record_as_the_first_line_is_an_unknown_status(self):
        r = parse_sync_output(_rec() + "\n")
        self.assertEqual(r.status, STATUS_ERROR)
        self.assertIn("unknown status", r.error_message or "")

    # --- fail-closed validation of the bare columns -----------------------

    def test_unknown_sub_reason_fails_closed(self):
        r = parse_sync_output(_STATUS + "\n" + _rec(sub_reason="misspelled") + "\n")
        self.assertEqual(r.status, STATUS_ERROR)
        self.assertIn("malformed DEFERRED_FILE", r.error_message or "")

    def test_bad_tree_state_fails_closed(self):
        r = parse_sync_output(_STATUS + "\n" + _rec(tree_state="sortof") + "\n")
        self.assertEqual(r.status, STATUS_ERROR)

    def test_bad_holder_fails_closed(self):
        r = parse_sync_output(_STATUS + "\n" + _rec(holder="mine") + "\n")
        self.assertEqual(r.status, STATUS_ERROR)

    def test_bad_pane_state_grammar_fails_closed(self):
        r = parse_sync_output(_STATUS + "\n" + _rec(pane_state="WAITING") + "\n")
        self.assertEqual(r.status, STATUS_ERROR)

    def test_pane_state_grammar_accepts_its_three_shapes(self):
        for value in ("", "active", "waiting_ask_user_question"):
            r = parse_sync_output(_STATUS + "\n" + _rec(pane_state=value) + "\n")
            self.assertEqual(r.status, sync_action_runner.STATUS_DEFERRED, value)

    def test_non_numeric_pid_fails_closed(self):
        r = parse_sync_output(_STATUS + "\n" + _rec(pid="12x") + "\n")
        self.assertEqual(r.status, STATUS_ERROR)

    def test_bad_task_id_fails_closed(self):
        r = parse_sync_output(_STATUS + "\n" + _rec(task="../etc") + "\n")
        self.assertEqual(r.status, STATUS_ERROR)

    def test_wrong_column_count_fails_closed(self):
        r = parse_sync_output(_STATUS + "\nDEFERRED_FILE:live_lock|10|a.md\n")
        self.assertEqual(r.status, STATUS_ERROR)

    # --- percent-decoding -------------------------------------------------

    def test_pipe_round_trips_in_every_textual_field(self):
        enc = "a%7Cb"
        r = parse_sync_output(_STATUS + "\n" + _rec(
            path=enc, email=enc, host=enc, pane=enc, action=enc) + "\n")
        self.assertEqual(r.status, sync_action_runner.STATUS_DEFERRED)
        f = r.deferred_files[0]
        for got in (f.path, f.email, f.host, f.pane, f.action):
            self.assertEqual(got, "a|b")

    def test_a_literal_percent_7c_does_not_double_decode(self):
        # The shell encodes `%` first, so a host that literally contained the
        # four characters "%7C" arrives as "%257C". Decoding %25 LAST is what
        # keeps it from becoming a delimiter.
        r = parse_sync_output(_STATUS + "\n" + _rec(host="a%257Cb") + "\n")
        self.assertEqual(r.deferred_files[0].host, "a%7Cb")

    def test_a_tmux_session_named_a_pipe_b_round_trips(self):
        r = parse_sync_output(_STATUS + "\n" + _rec(pane="a%7Cb:4.1") + "\n")
        self.assertEqual(r.deferred_files[0].pane, "a|b:4.1")


class LineBoundaryTests(unittest.TestCase):
    """The parser splits on LF alone, and that is load-bearing.

    `str.splitlines()` also breaks on CR, VT, FF, FS, GS, RS, NEL and (after
    decoding) U+2028/U+2029 -- every one of which is a LEGAL byte in a git path
    and therefore reachable inside a percent-encoded field. Encoding all nine on
    the shell side would rest the guarantee on enumerating a CPython
    implementation detail correctly; splitting on LF is one rule that holds for
    every byte a path can contain.
    """

    #: Characters splitlines() treats as boundaries but "\n".split does not.
    EXTRA_BOUNDARIES = ["\r", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85",
                        "\u2028", "\u2029"]

    def test_control_these_characters_really_do_split_splitlines(self):
        # A negative control for the class docstring: if a future Python stopped
        # treating these as boundaries, the rule below would still be correct
        # but this reasoning would be stale, and we want to know.
        for ch in self.EXTRA_BOUNDARIES:
            self.assertEqual(len(("a" + ch + "b").splitlines()), 2, repr(ch))
            self.assertEqual(len(("a" + ch + "b").split("\n")), 1, repr(ch))

    def test_each_boundary_character_survives_inside_a_path(self):
        for ch in self.EXTRA_BOUNDARIES:
            payload = "aitasks/t10" + ch + "x.md"
            r = parse_sync_output(_STATUS + "\n" + _rec(path=payload) + "\n")
            self.assertEqual(r.status, sync_action_runner.STATUS_DEFERRED, repr(ch))
            self.assertEqual(len(r.deferred_files), 1, repr(ch))
            self.assertEqual(r.deferred_files[0].path, payload, repr(ch))

    def test_encoded_lf_and_cr_decode_back_to_the_real_bytes(self):
        r = parse_sync_output(_STATUS + "\n" + _rec(path="a%0Ab%0Dc") + "\n")
        self.assertEqual(r.deferred_files[0].path, "a\nb\rc")


class DeferredFileReasonContractTest(unittest.TestCase):
    """The sub-reason vocabulary spans two languages -- derive, do not restate."""

    SYNC_SH = PROJECT_DIR / ".aitask-scripts" / "aitask_sync.sh"

    def test_every_protect_reason_is_declared(self):
        import re
        source = TokenContractTest._code_only(self.SYNC_SH.read_text())
        # All three receivers: a per-task or per-group protection reaches the
        # record set through the expansion helpers, not through _protect.
        reasons = set(re.findall(
            r'_protect(?:_task_paths|_group_paths)?\s+"([a-z_]+)"', source))
        self.assertTrue(reasons, "found no _protect literals — the scan broke")
        unknown = reasons - sync_action_runner.DEFERRED_FILE_REASONS
        self.assertFalse(
            unknown,
            f"aitask_sync.sh emits sub-reason(s) {sorted(unknown)} that "
            f"sync_action_runner.DEFERRED_FILE_REASONS does not declare",
        )

    def test_the_scan_finds_the_reasons_that_actually_exist(self):
        # Guards the regex itself: if it stopped matching a receiver spelling
        # the set above would trivially satisfy the subset check with a handful
        # of reasons, exactly as it did when the expansion helpers landed.
        import re
        source = TokenContractTest._code_only(self.SYNC_SH.read_text())
        reasons = set(re.findall(
            r'_protect(?:_task_paths|_group_paths)?\s+"([a-z_]+)"', source))
        for expected in ("live_lock", "ownerless", "content_changed",
                         "commit_failed", "lock_acquired_during_scan"):
            self.assertIn(expected, reasons)


class NonUtf8PathTests(unittest.TestCase):
    """A git path may contain any byte but NUL, including invalid UTF-8.

    The failure is inside the subprocess read, BEFORE parse_sync_output runs and past
    run_sync_batch's two excepts, so it escapes and crashes the calling TUI.
    That is why these drive run_sync_batch rather than the parser.
    """

    RAW = b"aitasks/t10_\xff.md"

    def _script_output(self):
        return (_STATUS + "\n").encode() + b"DEFERRED_FILE:live_lock|10|" \
            + self.RAW + b"|tracked|self|me@x.com|omg16|42|||act\n"

    def test_a_non_utf8_path_reaches_deferredfile_and_round_trips(self):
        payload = self._script_output()

        def fake_run(argv, **kwargs):
            # Decode exactly as the real subprocess would, with the kwargs
            # run_sync_batch actually passed.
            return SimpleNamespace(stdout=payload.decode(
                kwargs["encoding"], kwargs["errors"]))

        with mock.patch.object(sync_action_runner, "_run_sync_process", fake_run):
            r = sync_action_runner.run_sync_batch()

        self.assertEqual(r.status, sync_action_runner.STATUS_DEFERRED)
        self.assertEqual(len(r.deferred_files), 1)
        self.assertEqual(
            r.deferred_files[0].path.encode("utf-8", "surrogateescape"),
            b"aitasks/t10_\xff.md",
        )

    def test_control_a_strict_decode_would_have_raised(self):
        # Documents what the surrogateescape choice buys. If this ever stops
        # raising, the kwargs above are no longer load-bearing.
        with self.assertRaises(UnicodeDecodeError):
            self._script_output().decode("utf-8")

    def test_run_sync_batch_asks_for_a_byte_preserving_decode(self):
        calls: list = []

        def spy(argv, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(stdout="NOTHING\n")

        with mock.patch.object(sync_action_runner, "_run_sync_process", spy):
            sync_action_runner.run_sync_batch()
        self.assertEqual(calls[0]["encoding"], "utf-8")
        self.assertEqual(calls[0]["errors"], "surrogateescape")


# A delayed descendant: records its pid, optionally leaves the process group
# (what coreutils `timeout` does to the git it runs), optionally ignores
# SIGTERM (a stubborn transport), sleeps, writes a marker.
_WRITER = """\
import os, signal, sys, time
pidfile, marker, delay, own_group = sys.argv[1:5]
if len(sys.argv) > 5 and sys.argv[5] == "1":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
if own_group == "1":
    os.setpgid(0, 0)
with open(pidfile, "a") as fh:
    fh.write(f"{os.getpid()}\\n")
time.sleep(float(delay))
with open(marker, "w") as fh:
    fh.write("late")
"""

# Leaves the group, drops every inherited fd and hands the delayed write to a
# grandchild started with Popen's default close_fds=True, then exits.
_DROPPER = """\
import os, subprocess, sys
os.setpgid(0, 0)
writer, pidfile, marker, delay = sys.argv[1:5]
subprocess.Popen([sys.executable, writer, pidfile, marker, delay, "0"],
                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                 stderr=subprocess.DEVNULL, close_fds=True)
"""


# A sync that will not stop. It starts the given command at once with
# AIT_BOUNDED_RUN_GRACE=<grace>, records SIGTERM instead of dying, and then keeps
# spawning short-lived SIGTERM-ignoring children: some member was always
# signalled under a second ago, so no member's grace ever completes and the
# stop runs to its cap.
_TERM_RESISTANT_SPAWNER = """\
import os, signal, subprocess, sys, time
grace = sys.argv[1]
cmd = sys.argv[2:]
got = []
signal.signal(signal.SIGTERM, lambda *_: got.append(time.monotonic()))
quiet = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
             stderr=subprocess.DEVNULL)
subprocess.Popen(cmd, env=dict(os.environ, AIT_BOUNDED_RUN_GRACE=grace), **quiet)
while not got:
    time.sleep(0.02)
while True:
    subprocess.Popen(["sh", "-c", "trap '' TERM; sleep 0.6"], **quiet)
    time.sleep(0.25)
"""


@unittest.skipIf(sys.platform == "win32", "POSIX sessions and signals")
class TimeoutContainmentTests(unittest.TestCase):
    """A timed-out sync is stopped as a whole session before it returns (t1947).

    Real processes: a stand-in aitask_sync.sh under a temp repo root starts a
    descendant that writes a marker ~1 s in, after the 0.5 s timeout. A marker
    that appears after run_sync_batch returned is a sync process that outlived
    the result the caller was given.
    """

    TIMEOUT = 0.5

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.pidfile = self.root / "pids"
        self.marker = self.root / "marker"
        self.writer = self.root / "writer.py"
        self.writer.write_text(_WRITER)
        self.dropper = self.root / "dropper.py"
        self.dropper.write_text(_DROPPER)
        (self.root / ".aitask-scripts").mkdir()
        self.script = self.root / ".aitask-scripts" / "aitask_sync.sh"

    def tearDown(self):
        import os
        import signal
        if self.pidfile.exists():
            for pid in self.pidfile.read_text().split():
                try:
                    os.kill(int(pid), signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
        self._tmp.cleanup()

    def _write_script(self, body: str) -> None:
        self.script.write_text("#!/bin/sh\n" + body + "\n")
        self.script.chmod(0o755)

    def _writer_cmd(self, delay: float, own_group: bool) -> str:
        import shlex
        return " ".join(shlex.quote(a) for a in (
            sys.executable, str(self.writer), str(self.pidfile),
            str(self.marker), str(delay), "1" if own_group else "0"))

    def _sync(self) -> "sync_action_runner.SyncResult":
        return sync_action_runner.run_sync_batch(
            timeout=self.TIMEOUT, repo_root=self.root)

    def _assert_stopped(self, result) -> None:
        import time
        self.assertEqual(result.status, sync_action_runner.STATUS_TIMEOUT)
        self.assertIsNone(result.stray_session)
        time.sleep(1.5)
        self.assertFalse(self.marker.exists(),
                         "a sync descendant outlived the timeout result")

    def test_control_plain_subprocess_run_leaves_a_survivor(self):
        # Proves the fixture makes a real survivor: subprocess.run(timeout=)
        # kills only the direct sh, as run_sync_batch used to.
        import subprocess
        import time
        self._write_script(self._writer_cmd(1.0, own_group=False)
                           + " >/dev/null 2>&1")
        with self.assertRaises(subprocess.TimeoutExpired):
            subprocess.run([str(self.script)], capture_output=True,
                           timeout=self.TIMEOUT)
        time.sleep(1.5)
        self.assertTrue(self.marker.exists())

    def test_timeout_stops_a_same_group_child(self):
        # The pull/rebase shape: a foreground git in the script's own group.
        self._write_script(self._writer_cmd(1.0, own_group=False)
                           + " >/dev/null 2>&1")
        self._assert_stopped(self._sync())

    def test_timeout_stops_a_child_in_its_own_process_group(self):
        # The `timeout 10 git fetch` shape, out of killpg's reach.
        self._write_script(self._writer_cmd(1.0, own_group=True)
                           + " >/dev/null 2>&1")
        self._assert_stopped(self._sync())

    def test_timeout_stops_an_fd_dropping_descendant(self):
        # Out of the group AND holding no inherited fd: only the session
        # still ties it to the sync.
        import shlex
        launch = " ".join(shlex.quote(a) for a in (
            sys.executable, str(self.dropper), str(self.writer),
            str(self.pidfile), str(self.marker), "1.0"))
        self._write_script(launch + " >/dev/null 2>&1\nsleep 5")
        self._assert_stopped(self._sync())

    # --- A nested bounded runner (t2035) ---------------------------------
    # aitask_sync.sh runs fetch/push through lib/bounded_run.py, which puts git
    # in a session of its own that this runner can neither see nor signal. The
    # stand-in below runs the REAL bounded_run CLI around a transport parent
    # (sh) whose distinct child ignores SIGTERM and writes the marker 4s in:
    # only the inner runner's own SIGKILL can stop it, and only if the inner
    # runner is still alive to send it.

    NESTED_DELAY = 4.0

    def _nested_runner_argv(self, delay: float) -> list[str]:
        """The real bounded_run CLI around a transport parent (sh) and its
        distinct SIGTERM-ignoring writer, which writes the marker ``delay`` s in."""
        import shlex
        writer = " ".join(shlex.quote(a) for a in (
            sys.executable, str(self.writer), str(self.pidfile),
            str(self.marker), str(delay), "0", "1"))
        transport = f'{writer} & echo $$ >> {shlex.quote(str(self.pidfile))}; wait'
        return [sys.executable, str(LIB_SRC / "bounded_run.py"), "--timeout",
                "30", "--noninteractive", "--", "sh", "-c", transport]

    def _write_nested_script(self) -> None:
        import shlex
        runner = " ".join(shlex.quote(a)
                          for a in self._nested_runner_argv(self.NESTED_DELAY))
        self._write_script(runner + " >/dev/null 2>&1")

    def _nested_survivors(self) -> list[int]:
        import os
        alive = []
        for pid in (self.pidfile.read_text().split()
                    if self.pidfile.exists() else []):
            try:
                os.kill(int(pid), 0)
            except ProcessLookupError:
                continue
            except PermissionError:
                pass
            alive.append(int(pid))
        return alive

    def _wait_for_both_pids(self) -> None:
        # Fixture guard: the transport parent AND its stubborn child started.
        import time
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if (self.pidfile.exists()
                    and len(self.pidfile.read_text().split()) >= 2):
                return
            time.sleep(0.02)
        self.fail("the nested transport never started both processes")

    def _run_nested(self):
        import threading
        result = {}
        worker = threading.Thread(
            target=lambda: result.setdefault("r", self._sync()))
        worker.start()
        self._wait_for_both_pids()
        worker.join(30)
        self.assertFalse(worker.is_alive(), "run_sync_batch never returned")
        return result["r"]

    def test_timeout_stops_a_nested_bounded_runner(self):
        import time
        self._write_nested_script()
        with mock.patch.dict(os.environ):
            os.environ.pop("AIT_BOUNDED_RUN_GRACE", None)
            started = time.monotonic()
            result = self._run_nested()
        returned = time.monotonic() - started
        self.assertEqual(result.status, sync_action_runner.STATUS_TIMEOUT)
        self.assertIsNone(result.stray_session)
        self.assertEqual(self._nested_survivors(), [],
                         "a transport process outlived the timeout result")
        # Orderly: the runner reaped its own group inside the TERM window, so
        # the stop never needed its SIGKILL rounds.
        self.assertLess(returned, self.TIMEOUT
                        + sync_action_runner._TERM_GRACE_SECONDS)
        time.sleep(max(0.0, started + self.NESTED_DELAY + 1.0 - time.monotonic()))
        self.assertFalse(self.marker.exists(),
                         "the nested transport wrote after the timeout result")

    def test_control_an_uncoordinated_grace_falls_to_the_kill_rounds(self):
        # Without the exported grace the runner keeps bounded_run's 5s default
        # and outlives the 3s TERM window, so the cleanup is the SIGKILL rounds'
        # rather than its own -- proving the grace ordering is what makes it
        # orderly. Nothing escapes even so: bounded_run kept the transport in
        # the sync's session (no controlling terminal), where the rounds reach it.
        import time
        self._write_nested_script()
        with mock.patch.dict(os.environ), \
                mock.patch.object(sync_action_runner, "_sync_child_env",
                                  lambda: dict(os.environ)):
            os.environ.pop("AIT_BOUNDED_RUN_GRACE", None)
            started = time.monotonic()
            result = self._run_nested()
        returned = time.monotonic() - started
        self.assertEqual(result.status, sync_action_runner.STATUS_TIMEOUT)
        self.assertGreaterEqual(returned, sync_action_runner._TERM_GRACE_SECONDS)
        self.assertIsNone(result.stray_session)
        self.assertEqual(self._nested_survivors(), [])
        time.sleep(max(0.0, started + self.NESTED_DELAY + 1.0 - time.monotonic()))
        self.assertFalse(self.marker.exists())

    def test_a_stopped_runner_is_resumed_to_clean_up(self):
        # A SIGSTOPped runner cannot run its SIGTERM handler: without SIGCONT
        # it sits out the whole TERM window and only the kill rounds end it.
        # With SIGCONT it reaps its own group inside the window.
        import shlex
        import signal as sig
        import threading
        import time
        runner_pid_file = self.root / "runner.pid"
        runner = " ".join(shlex.quote(a)
                          for a in self._nested_runner_argv(self.NESTED_DELAY))
        self._write_script(
            f"{runner} >/dev/null 2>&1 &\n"
            f"echo $! > {shlex.quote(str(runner_pid_file))}\nwait")
        timeout = 1.5
        result = {}
        with mock.patch.dict(os.environ):
            os.environ.pop("AIT_BOUNDED_RUN_GRACE", None)
            worker = threading.Thread(target=lambda: result.setdefault(
                "r", sync_action_runner.run_sync_batch(timeout=timeout,
                                                       repo_root=self.root)))
            started = time.monotonic()
            worker.start()
            self._wait_for_both_pids()
            os.kill(int(runner_pid_file.read_text()), sig.SIGSTOP)
            worker.join(30)
        returned = time.monotonic() - started
        self.assertFalse(worker.is_alive())
        r = result["r"]
        self.assertEqual(r.status, sync_action_runner.STATUS_TIMEOUT)
        self.assertIsNone(r.stray_session)
        self.assertEqual(self._nested_survivors(), [])
        self.assertLess(returned, timeout + sync_action_runner._TERM_GRACE_SECONDS,
                        "the stopped runner was not resumed to clean up")
        time.sleep(max(0.0, started + self.NESTED_DELAY + 1.0 - time.monotonic()))
        self.assertFalse(self.marker.exists())

    def test_a_runner_cut_down_by_the_term_cap_leaves_no_transport(self):
        # Real processes. A SIGTERM-resistant sync keeps the TERM window open
        # until its cap, and its bounded runner carries a 30s cleanup grace, so
        # the cap's SIGKILL rounds cut that runner down MID-CLEANUP, before it
        # ever SIGKILLs its own TERM-ignoring transport. The transport must die
        # anyway -- possible only because it is a member of the sync's session
        # rather than of a session of its own the stop cannot see.
        import shlex
        import time
        spawner = self.root / "spawner.py"
        spawner.write_text(_TERM_RESISTANT_SPAWNER)
        writer_delay = 8.0
        argv = [sys.executable, str(spawner), "30"] + \
            self._nested_runner_argv(writer_delay)
        self._write_script("exec " + " ".join(shlex.quote(a) for a in argv))
        with mock.patch.dict(os.environ):
            os.environ.pop("AIT_BOUNDED_RUN_GRACE", None)
            started = time.monotonic()
            result = self._sync()
        returned = time.monotonic() - started
        self.assertEqual(result.status, sync_action_runner.STATUS_TIMEOUT)
        self.assertTrue(self.pidfile.exists()
                        and len(self.pidfile.read_text().split()) >= 2,
                        "fixture: the runner never started its transport")
        self.assertGreaterEqual(returned, self.TIMEOUT
                                + 2 * sync_action_runner._TERM_GRACE_SECONDS,
                                "fixture: the stop did not reach the cap")
        self.assertIsNone(result.stray_session)
        self.assertEqual(self._nested_survivors(), [],
                         "the capped runner's transport outlived the result")
        time.sleep(max(0.0, started + writer_delay + 1.5 - time.monotonic()))
        self.assertFalse(self.marker.exists(),
                         "the capped runner's transport wrote after the result")

    def test_a_runner_started_after_the_first_listing_is_still_stopped(self):
        # The snapshot-versus-spawn interleaving: the sync launches its bounded
        # runner AFTER the stop took its first membership listing, so a stop
        # that signals only that listing never asks the runner to stop and
        # SIGKILLs it mid-cleanup later. Deterministic: the first listing is
        # held (and returned stale) until the runner and both transport
        # processes exist; the stand-in only launches once released.
        import shlex
        import time
        go = self.root / "go"
        self._write_nested_script()
        runner = self.script.read_text().split("\n", 1)[1]
        self._write_script(
            f"while [ ! -e {shlex.quote(str(go))} ]; do sleep 0.02; done\n"
            + runner)
        real_members = sync_action_runner._session_members
        calls = {"n": 0}

        def held_first_listing(sid):
            calls["n"] += 1
            members = real_members(sid)
            if calls["n"] == 1:
                go.touch()
                self._wait_for_both_pids()
            return members

        with mock.patch.dict(os.environ), \
                mock.patch.object(sync_action_runner, "_session_members",
                                  held_first_listing):
            os.environ.pop("AIT_BOUNDED_RUN_GRACE", None)
            started = time.monotonic()
            result = self._sync()
        self.assertGreater(calls["n"], 1)
        self.assertEqual(result.status, sync_action_runner.STATUS_TIMEOUT)
        self.assertIsNone(result.stray_session)
        self.assertEqual(self._nested_survivors(), [],
                         "a late-started runner's transport outlived the result")
        time.sleep(max(0.0, started + self.NESTED_DELAY + 1.0 - time.monotonic()))
        self.assertFalse(self.marker.exists(),
                         "the late runner's transport wrote after the result")

    def test_term_window_is_capped_for_a_session_that_keeps_spawning(self):
        # Escalation waits for each member's own grace, but never forever: a
        # stream of new members still reaches the SIGKILL rounds.
        import itertools
        import time
        pids = itertools.count(10_000_000)
        with mock.patch.object(sync_action_runner, "_session_members",
                               lambda sid: [next(pids)]), \
                mock.patch.object(sync_action_runner, "_signal_members",
                                  lambda members, sig: None), \
                mock.patch.object(sync_action_runner, "_TERM_GRACE_SECONDS", 0.2):
            started = time.monotonic()
            emptied = sync_action_runner._term_session(1, [9_999_999])
        self.assertFalse(emptied)
        self.assertLess(time.monotonic() - started, 1.0)

    def test_child_grace_fits_inside_the_outer_term_window(self):
        from bounded_run import GRACE_ENV, NESTING_MARGIN_SECONDS
        with mock.patch.dict(os.environ):
            os.environ.pop(GRACE_ENV, None)
            grace = float(sync_action_runner._sync_child_env()[GRACE_ENV])
        self.assertLessEqual(grace + NESTING_MARGIN_SECONDS,
                             sync_action_runner._TERM_GRACE_SECONDS)

    def test_a_smaller_inherited_grace_is_kept(self):
        from bounded_run import GRACE_ENV
        with mock.patch.dict(os.environ, {GRACE_ENV: "0.5"}):
            self.assertEqual(sync_action_runner._sync_child_env()[GRACE_ENV],
                             "0.5")

    def test_unprovable_stop_reports_the_session(self):
        import os
        import signal
        import time
        self._write_script(self._writer_cmd(30, own_group=False)
                           + " >/dev/null 2>&1")
        with mock.patch.object(sync_action_runner, "_signal_members",
                               lambda members, sig: None), \
                mock.patch.object(sync_action_runner, "_TERM_GRACE_SECONDS", 0.2), \
                mock.patch.object(sync_action_runner, "_KILL_DEADLINE_SECONDS", 0.3):
            result = self._sync()
        self.assertEqual(result.status, sync_action_runner.STATUS_TIMEOUT)
        sid = result.stray_session
        self.assertIsNotNone(sid)
        self.assertIn("could not be confirmed stopped", result.error_message)
        self.assertTrue(sync_action_runner.sync_session_running(sid))
        # Recovery: once the survivor is gone the probe releases.
        for pid in self.pidfile.read_text().split():
            os.kill(int(pid), signal.SIGKILL)
        deadline = time.monotonic() + 5
        while (sync_action_runner.sync_session_running(sid)
               and time.monotonic() < deadline):
            time.sleep(0.05)
        self.assertFalse(sync_action_runner.sync_session_running(sid))

    def test_unavailable_membership_query_fails_closed(self):
        self._write_script(self._writer_cmd(30, own_group=False)
                           + " >/dev/null 2>&1")
        with mock.patch.object(sync_action_runner, "_session_members",
                               lambda sid: None):
            result = self._sync()
            self.assertIsNotNone(result.stray_session)
            self.assertTrue(
                sync_action_runner.sync_session_running(result.stray_session))

    def _probe_with_stat_error(self, exc: OSError):
        """Membership of a live session while every /proc stat read raises."""
        import builtins
        real_open = builtins.open

        def failing_open(path, *args, **kwargs):
            if str(path).startswith("/proc/") and str(path).endswith("/stat") \
                    and path != "/proc/self/stat":
                raise exc
            return real_open(path, *args, **kwargs)

        with mock.patch.object(sync_action_runner, "open", failing_open,
                               create=True):
            return (sync_action_runner._session_members(os.getsid(0)),
                    sync_action_runner.sync_session_running(os.getsid(0)))

    @unittest.skipUnless(Path("/proc/self/stat").exists(), "/proc backend")
    def test_unreadable_proc_entry_is_unknown_not_gone(self):
        # The probe runs against this test's own (live) session: an
        # unreadable stat must never read as an empty session.
        import errno
        for exc in (PermissionError(errno.EACCES, "denied"),
                    OSError(errno.EIO, "I/O error")):
            with self.subTest(exc=type(exc).__name__):
                members, running = self._probe_with_stat_error(exc)
                self.assertIsNone(members)
                self.assertTrue(running)

    @unittest.skipUnless(Path("/proc/self/stat").exists(), "/proc backend")
    def test_vanished_proc_entry_is_skipped(self):
        # Control: a process that exited between listing and reading is
        # genuinely gone, so it is skipped rather than poisoning the probe.
        import errno
        for exc in (FileNotFoundError(errno.ENOENT, "gone"),
                    ProcessLookupError(errno.ESRCH, "gone")):
            with self.subTest(exc=type(exc).__name__):
                members, running = self._probe_with_stat_error(exc)
                self.assertEqual(members, [])
                self.assertFalse(running)

    def test_normal_exit_does_not_wait_for_session_helpers(self):
        # A helper left in the session after a clean exit (credential-cache,
        # fsmonitor) is not task-data work; waiting on it would stall syncs.
        import time
        self._write_script(self._writer_cmd(5, own_group=True)
                           + " >/dev/null 2>&1 &\necho NOTHING")
        started = time.monotonic()
        result = sync_action_runner.run_sync_batch(timeout=10,
                                                   repo_root=self.root)
        self.assertEqual(result.status, STATUS_NOTHING)
        self.assertIsNone(result.stray_session)
        self.assertLess(time.monotonic() - started, 3)


class _ConflictHost(App):
    """Minimal host that pushes a SyncConflictScreen and records its result."""

    def __init__(self, files: list[str], repo_label: str = "") -> None:
        super().__init__()
        self._files = files
        self._repo_label = repo_label
        self.result: object = "UNSET"

    def compose(self) -> ComposeResult:
        yield Label("host")

    def on_mount(self) -> None:
        self.push_screen(
            SyncConflictScreen(self._files, repo_label=self._repo_label),
            self._record,
        )

    def _record(self, result) -> None:
        self.result = result


class SyncConflictScreenTests(unittest.TestCase):
    """The modal's dismiss value is a CLOSED set (t1911): the two callers
    dispatch on it by equality, so each button must yield exactly its value."""

    FILES = ["aitasks/t1_a.md", "aiplans/p1_a.md"]

    def _dismiss_via(self, action) -> object:
        async def runner():
            app = _ConflictHost(self.FILES)
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()
                await action(pilot)
                await pilot.pause()
            return app.result

        return asyncio.run(runner())

    def test_agent_button_dismisses_with_agent(self):
        result = self._dismiss_via(lambda p: p.click("#btn_sync_agent"))
        self.assertEqual(result, CONFLICT_CHOICE_AGENT)

    def test_interactive_button_dismisses_with_interactive(self):
        result = self._dismiss_via(lambda p: p.click("#btn_sync_resolve"))
        self.assertEqual(result, CONFLICT_CHOICE_INTERACTIVE)

    def test_dismiss_button_dismisses_with_none(self):
        result = self._dismiss_via(lambda p: p.click("#btn_sync_dismiss"))
        self.assertIsNone(result)

    def test_escape_dismisses_with_none(self):
        result = self._dismiss_via(lambda p: p.press("escape"))
        self.assertIsNone(result)

    def test_files_and_repo_label_render(self):
        async def runner():
            app = _ConflictHost(self.FILES, repo_label="proj2")
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()
                title = str(app.screen.query_one("#sync_conflict_title", Label).render())
                body = str(app.screen.query_one("#sync_conflict_files", Label).render())
            return title, body

        title, body = asyncio.run(runner())
        self.assertIn("proj2", title)
        for f in self.FILES:
            self.assertIn(f, body)

    def test_three_buttons_fit_inside_the_dialog(self):
        # Checked against the dialog's CONTENT region, not its outer box. 80
        # columns is the regression case: a percentage width alone leaves 51
        # content columns there and clips "Dismiss" entirely (measured).
        async def runner(width):
            app = _ConflictHost(self.FILES)
            async with app.run_test(size=(width, 30)) as pilot:
                await pilot.pause()
                content = app.screen.query_one("#sync_conflict_dialog").content_region
                buttons = [
                    app.screen.query_one(f"#{bid}", Button).region
                    for bid in ("btn_sync_agent", "btn_sync_resolve", "btn_sync_dismiss")
                ]
            return content, buttons

        for width in (80, 100, 120):
            with self.subTest(width=width):
                content, buttons = asyncio.run(runner(width))
                for region in buttons:
                    self.assertGreater(region.width, 0)
                    self.assertTrue(
                        content.contains_region(region),
                        f"button {region} is clipped by the dialog content {content}",
                    )
                ordered = sorted(buttons, key=lambda r: r.x)
                for left, right in zip(ordered, ordered[1:]):
                    self.assertLessEqual(left.right, right.x, "buttons overlap")


class BuildDataConflictPromptTests(unittest.TestCase):
    """The prompt gives context, the outcome and one constraint — not a recipe
    (t1911). These tests check that each of those is present by intent; they
    deliberately do not pin any Git command sequence."""

    ROOT = Path("/work/projA")
    FILES = ["aitasks/t12_alpha.md", "aiplans/p12_alpha.md", "notes.txt"]

    def setUp(self):
        self.prompt = build_data_conflict_prompt(self.FILES, self.ROOT)
        self.lower = self.prompt.lower()

    def assertMentions(self, *phrases: str) -> None:
        for phrase in phrases:
            self.assertIn(phrase.lower(), self.lower, f"prompt lacks {phrase!r}")

    # -- launch context ---------------------------------------------------
    def test_names_every_conflicted_file_and_the_repo_root(self):
        for f in self.FILES:
            self.assertIn(f"  - {f}", self.prompt)
        self.assertIn(str(self.ROOT), self.prompt)

    def test_bare_conflict_names_no_empty_file(self):
        prompt = build_data_conflict_prompt([""], self.ROOT)
        self.assertNotIn("  - \n", prompt)
        self.assertIn("did not name the conflicted files", prompt)

    def test_describes_the_state_sync_left_and_that_it_may_have_moved(self):
        self.assertMentions("aborts its rebase", "may have moved since")

    # -- isolation requirement ------------------------------------------
    def test_requires_a_separate_worktree_and_says_why(self):
        self.assertMentions(
            "separate git worktree",
            "never in `.aitask-data`",
            "shared by every session",
            "task writes fail",
        )

    # -- intended outcomes ----------------------------------------------
    def test_states_the_integrated_published_outcome(self):
        self.assertMentions(
            "integrated with the remote and published",
            "checkout up to date",
            "merged, not superseded",
            "keep both sides' intent",
            "remove any worktree you created",
        )

    def test_states_the_end_state_for_other_sessions(self):
        self.assertMentions(
            "other sessions' ongoing work must be preserved",
            "uncommitted edits",
            "commits they made there",
            "no unresolved merge or rebase in progress",
        )

    def test_requires_verifying_the_final_result_with_the_method_left_open(self):
        self.assertMentions(
            "verify",
            "by whatever method you choose",
            "published on the remote",
            "live `.aitask-data` checkout",
        )

    # -- pitfalls and autonomy ------------------------------------------
    def test_names_both_pitfalls(self):
        self.assertMentions("rebase drops merge commits", "aitask_merge.py")
        self.assertRegex(self.prompt, r"`labels`.*`depends`")
        self.assertRegex(self.prompt, r"`Implementing` win\s+over `Done`")

    def test_leaves_the_approach_to_the_agent_and_asks_on_ambiguity(self):
        self.assertMentions("choose your own approach", "ask the user when")


if __name__ == "__main__":
    unittest.main()
