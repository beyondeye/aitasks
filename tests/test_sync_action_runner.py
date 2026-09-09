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

    The failure is inside subprocess.run, BEFORE parse_sync_output runs and past
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

        with mock.patch.object(sync_action_runner.subprocess, "run", fake_run):
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

        with mock.patch.object(sync_action_runner.subprocess, "run", spy):
            sync_action_runner.run_sync_batch()
        self.assertEqual(calls[0]["encoding"], "utf-8")
        self.assertEqual(calls[0]["errors"], "surrogateescape")


if __name__ == "__main__":
    unittest.main()
