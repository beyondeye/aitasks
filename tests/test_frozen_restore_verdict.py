#!/usr/bin/env python3
"""Contract for `agent_sessions.restore_verdict` / `drop_verdict` (t1705_7).

These two functions are a **shared API with three consumers** — the
`frozenagent` viewer and both monitor TUIs — so they get their own pin rather
than being covered incidentally by whichever consumer's suite happens to reach
them. `tests/test_frozenagent_restore_poll_characterization.py` is the other
half: it pins the viewer's *observable* verdicts across the extraction. This
module pins the surface itself — argument shape, return shape, and the
boundaries.

**Why the verdict exists at all.** A restore/drop coordinator is dispatched with
`tmux run-shell -b`, a detached job whose stdout no caller can read. Its
`RESTORED:` / `DROPPED:` / `RESTORE_FAILED:` wire lines never reach the UI that
started it, so the store record is the only channel and every UI must interpret
it identically.

Run: python3 tests/test_frozen_restore_verdict.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / ".aitask-scripts" / "lib"))

import agent_sessions  # noqa: E402

DISPATCH_GRACE = 10.0
SETTLE_TIMEOUT = 40.0
DROP_GRACE = 10.0


def _rec(**over) -> agent_sessions.SessionRecord:
    """A `SessionRecord` carrying only the fields the verdict reads."""
    base = {
        "id": "7f3a2c1d", "root": "/tmp/proj", "window": "w",
        "state": agent_sessions.STATE_FROZEN,
        "restore_attempts": 0, "ack": "", "last_error": "",
    }
    base.update(over)
    return agent_sessions.SessionRecord(**base)


def _restore(rec, prev_attempts=0, elapsed=0.0):
    return agent_sessions.restore_verdict(
        rec, prev_attempts, elapsed,
        dispatch_grace=DISPATCH_GRACE, settle_timeout=SETTLE_TIMEOUT,
    )


class ReturnShapeTests(unittest.TestCase):
    """Every path returns the same 3-tuple, and waiting carries no message."""

    def test_a_waiting_verdict_is_false_empty_false(self):
        self.assertEqual(_restore(_rec(restore_attempts=0), 0, 0.0),
                         (False, "", False))

    def test_every_terminal_verdict_carries_a_non_empty_message(self):
        terminal = [
            _restore(None),
            _restore(_rec(restore_attempts=0), 0, DISPATCH_GRACE),
            _restore(_rec(state=agent_sessions.STATE_LIVE, restore_attempts=1)),
            _restore(_rec(state=agent_sessions.STATE_FROZEN,
                          restore_attempts=1, last_error="n:boom")),
            _restore(_rec(state=agent_sessions.STATE_RESTORING,
                          restore_attempts=1), 0, SETTLE_TIMEOUT),
        ]
        for done, message, _warn in terminal:
            self.assertTrue(done)
            self.assertTrue(message, "a terminal verdict must say something")

    def test_drop_shares_the_same_shape(self):
        self.assertEqual(
            agent_sessions.drop_verdict(_rec(), 0.0, drop_grace=DROP_GRACE),
            (False, "", False))
        done, message, warn = agent_sessions.drop_verdict(
            None, 0.0, drop_grace=DROP_GRACE)
        self.assertEqual((done, warn), (True, False))
        self.assertTrue(message)


class PreBeginGateTests(unittest.TestCase):
    """The gate is `restore_attempts`, and it dominates every other field."""

    def test_a_stale_error_before_the_attempt_starts_is_ignored(self):
        """`restore-begin` clears `last_error`; anything present pre-begin
        belongs to an earlier attempt."""
        rec = _rec(restore_attempts=2, last_error="old:session_mismatch")
        self.assertEqual(_restore(rec, prev_attempts=2), (False, "", False))

    def test_a_transitional_state_before_the_attempt_starts_is_ignored(self):
        rec = _rec(state=agent_sessions.STATE_RESTORING, restore_attempts=2)
        self.assertEqual(_restore(rec, prev_attempts=2), (False, "", False))

    def test_equal_attempts_is_pre_begin_strictly_greater_is_started(self):
        """The boundary: `restore-begin` bumps by one, so `<=` is the gate."""
        self.assertFalse(_restore(_rec(restore_attempts=5), 5)[0])
        done, message, _ = _restore(
            _rec(state=agent_sessions.STATE_LIVE, restore_attempts=6), 5)
        self.assertTrue(done)
        self.assertEqual(message, "restored")

    def test_the_dispatch_grace_boundary_is_inclusive(self):
        rec = _rec(restore_attempts=0)
        self.assertFalse(_restore(rec, 0, DISPATCH_GRACE - 0.01)[0])
        self.assertTrue(_restore(rec, 0, DISPATCH_GRACE)[0])


class StaleNonceTrapTests(unittest.TestCase):
    """A cleared lease must not hide a preserved error."""

    def test_a_frozen_record_with_no_nonce_still_reports_its_error(self):
        """Recovery clears `op_nonce` while KEEPING `last_error`. Correlating
        the two would make this failure unreportable."""
        rec = _rec(state=agent_sessions.STATE_FROZEN, restore_attempts=1,
                   op_nonce="", last_error="abc12345:session_mismatch")
        done, message, warn = _restore(rec, prev_attempts=0)
        self.assertEqual(
            (done, message, warn),
            (True, "restore failed: session_mismatch — capture kept", True))

    def test_the_reason_is_the_tail_after_the_first_colon_only(self):
        rec = _rec(state=agent_sessions.STATE_FROZEN, restore_attempts=1,
                   last_error="nonce:a:b")
        self.assertEqual(_restore(rec, 0)[1],
                         "restore failed: a:b — capture kept")

    def test_an_uncolonned_error_is_used_whole(self):
        rec = _rec(state=agent_sessions.STATE_FROZEN, restore_attempts=1,
                   last_error="boom")
        self.assertEqual(_restore(rec, 0)[1],
                         "restore failed: boom — capture kept")


class SuccessTests(unittest.TestCase):

    def test_a_liveness_ack_is_a_success_and_must_not_warn(self):
        """The only outcome an interactive codex restore can reach. Styling it
        as an error would make the normal codex path look broken."""
        rec = _rec(state=agent_sessions.STATE_LIVE, restore_attempts=1,
                   ack="liveness")
        self.assertEqual(
            _restore(rec, 0),
            (True, "restored, unverified — capture kept", False))

    def test_a_hook_ack_is_a_plain_success(self):
        rec = _rec(state=agent_sessions.STATE_LIVE, restore_attempts=1,
                   ack="hook")
        self.assertEqual(_restore(rec, 0), (True, "restored", False))


class TimeoutTests(unittest.TestCase):

    def test_a_timeout_names_the_state_and_never_claims_success(self):
        for state in (agent_sessions.STATE_RESTORING,
                      agent_sessions.STATE_ABORTING):
            rec = _rec(state=state, restore_attempts=1)
            done, message, warn = _restore(rec, 0, SETTLE_TIMEOUT)
            self.assertEqual((done, warn), (True, True))
            self.assertIn(state, message)
            self.assertIn("reconcile", message)
            self.assertNotIn("restored", message)

    def test_a_transitional_record_inside_the_timeout_keeps_waiting(self):
        rec = _rec(state=agent_sessions.STATE_RESTORING, restore_attempts=1)
        self.assertEqual(_restore(rec, 0, SETTLE_TIMEOUT - 0.01),
                         (False, "", False))

    def test_a_vanished_record_is_terminal_and_warns(self):
        self.assertEqual(_restore(None), (True, "record vanished", True))


class DropVerdictTests(unittest.TestCase):

    def test_a_gone_record_is_the_success(self):
        self.assertEqual(
            agent_sessions.drop_verdict(None, 0.0, drop_grace=DROP_GRACE),
            (True, "dropped — capture removed", False))

    def test_the_drop_grace_boundary_is_inclusive(self):
        rec = _rec()
        self.assertFalse(agent_sessions.drop_verdict(
            rec, DROP_GRACE - 0.01, drop_grace=DROP_GRACE)[0])
        self.assertEqual(
            agent_sessions.drop_verdict(rec, DROP_GRACE,
                                        drop_grace=DROP_GRACE),
            (True, "drop failed — record kept", True))

    def test_drop_never_interprets_state(self):
        """A dropped record disappears; it never passes through `live` or
        `restoring`, which is why it cannot share the restore interpreter."""
        for state in (agent_sessions.STATE_LIVE,
                      agent_sessions.STATE_RESTORING,
                      agent_sessions.STATE_FROZEN):
            self.assertEqual(
                agent_sessions.drop_verdict(_rec(state=state), 0.0,
                                            drop_grace=DROP_GRACE),
                (False, "", False))


class TextlessTests(unittest.TestCase):
    """The verdict must stay usable from a non-Textual caller."""

    def test_the_module_does_not_import_a_ui_toolkit(self):
        source = (PROJECT_DIR / ".aitask-scripts" / "lib"
                  / "agent_sessions.py").read_text(encoding="utf-8")
        for banned in ("import textual", "from textual"):
            self.assertNotIn(
                banned, source,
                "agent_sessions hosts the shared verdict; importing a UI "
                "toolkit here would make it unusable from the engines")


if __name__ == "__main__":
    unittest.main(verbosity=2)
