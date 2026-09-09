#!/usr/bin/env python3
"""Characterization pins for the frozenagent viewer's restore/drop poll (t1705_7).

**This is a control, not a feature test.** t1705_7 extracts the verdict logic of
``FrozenAgentApp._poll_restore`` / ``_poll_drop`` into a pure, Textual-free
``agent_frozen_ops.restore_verdict`` so the two monitor TUIs can reuse it instead
of growing a fourth copy. This module pins the verdicts as they behave *before*
that extraction, is run green against the unmodified code, and must stay green
afterwards with **no assertion edited**. A refactor that looks faithful and is
not fails here.

Two of the pinned behaviours are the ones worth losing sleep over, because both
read as "obviously simplifiable" to someone who has not hit them:

``PreBeginTests``
    ``run-shell -b`` returns no nonce, and ``restore-begin`` is what clears
    ``last_error``. A poll firing before the coordinator starts therefore reads
    the *previous* attempt's error. The gate is ``restore_attempts`` — the only
    field ``restore-begin`` bumps monotonically — **not** ``state`` and never
    ``last_error``.

``StaleNonceTrapTests``
    Recovery (``restore-abort`` -> ``standin-respawned``) returns the record to
    ``frozen`` and **clears the lease while preserving the error**. So by the
    time the poll observes it, ``op_nonce`` is ``""`` and any attempt to
    correlate ``last_error`` against a freshly-read nonce can never match —
    which silently turns a failed restore into a reported timeout. The
    correlation is the ``restore_attempts`` gate above, already passed.

Everything runs against a temp store (``AITASKS_AGENT_SESSIONS_FILE`` /
``AITASKS_FROZEN_DIR``). Nothing touches tmux: the poll paths read the store and
call ``_finish``, which is stubbed here so no mounted app is required.

Run: python3 tests/test_frozenagent_restore_poll_characterization.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / ".aitask-scripts"))
sys.path.insert(0, str(PROJECT_DIR / ".aitask-scripts" / "lib"))

RECORD_ID = "7f3a2c1d"


def _record(rid: str, **over) -> dict:
    """A schema-v1 record with every field the parser requires.

    Mirrors ``tests/test_frozenagent_app.py::_record``; kept local so this
    control module has no dependency on the suite it is a control for.
    """
    base = {
        "id": rid, "root": "/tmp/proj", "window": "agent-pick-1705",
        "window_slot": 0, "pane_id": "%9", "pane_pid": 4242,
        "session": "aitasks", "operation": "pick", "task_id": "1705",
        "agent_string": "claudecode/opus5", "agent_kind": "claudecode",
        "codeagent_session_id": "", "transcript_path": "",
        "started_at": "2026-09-04T09:12:03Z", "state": "frozen",
        "state_at": "2026-09-04T09:20:00Z",
        "op_nonce": "", "op_owner_pid": 0, "op_started_at": "",
        "frozen_at": "2026-09-04T09:20:00Z",
        "capture_ansi": "", "capture_txt": "", "capture_lines": 6,
        "last_phase": "", "standin_pid": 0, "launch_pid": 0,
        "restore_attempts": 0, "restore_mode": "", "ack": "", "last_error": "",
    }
    base.update(over)
    # The store REFUSES an incoherent lease (nonce / owner_pid / started_at must
    # be all set or all empty), so a fixture setting only the nonce is
    # unparseable and `by_id` returns None — which looks like an app bug.
    if base["op_nonce"]:
        base["op_owner_pid"] = base["op_owner_pid"] or 999999
        base["op_started_at"] = base["op_started_at"] or "2026-09-04T09:21:00Z"
    return base


class _PollCase(unittest.TestCase):
    """A temp store plus an unmounted app whose `_finish` is captured.

    The app is constructed but never mounted: both poll methods need only
    ``self._view`` (built in ``__init__``) and ``_finish``, so a real Textual
    run loop would add nothing but flake.
    """

    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="ait_fa_char_"))
        self.store = self.dir / "agent_sessions.json"
        os.environ["AITASKS_AGENT_SESSIONS_FILE"] = str(self.store)
        os.environ["AITASKS_FROZEN_DIR"] = str(self.dir / "frozen")
        self.addCleanup(self._cleanup)

        import frozenagent.frozenagent_app as app_mod
        self.app_mod = app_mod
        self.app = app_mod.FrozenAgentApp(RECORD_ID)

        #: Every `_finish(rid, note, warn=…)` this tick produced.
        self.finished: list[tuple[str, str, bool]] = []
        self.app._finish = (                      # type: ignore[method-assign]
            lambda rid, note, *, warn=False:
                self.finished.append((rid, note, warn))
        )

    def _cleanup(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)
        os.environ.pop("AITASKS_AGENT_SESSIONS_FILE", None)
        os.environ.pop("AITASKS_FROZEN_DIR", None)

    def write(self, records: list[dict]) -> None:
        self.store.write_text(json.dumps({"version": 1, "sessions": records}))

    def poll_restore(self, *, prev_attempts: int, prev_nonce: str = "",
                     elapsed_before: float = 0.0) -> None:
        """One `_poll_restore` tick. `elapsed_before` is the time *before* it."""
        self.app._poll_restore(
            RECORD_ID, (prev_attempts, prev_nonce), {"t": elapsed_before},
        )

    def poll_drop(self, *, elapsed_before: float = 0.0) -> None:
        self.app._poll_drop(RECORD_ID, {"t": elapsed_before})

    # --- assertions -------------------------------------------------------

    def assertStillWaiting(self) -> None:
        self.assertEqual(
            self.finished, [],
            "this tick reached a terminal verdict; it must still be waiting",
        )

    def assertFinished(self, note: str, warn: bool) -> None:
        self.assertEqual(len(self.finished), 1,
                         f"expected exactly one verdict, got {self.finished!r}")
        rid, got_note, got_warn = self.finished[0]
        self.assertEqual(rid, RECORD_ID)
        self.assertEqual(got_note, note)
        self.assertEqual(got_warn, warn)


# ───────────────────────── pre-begin (the attempts gate) ──────────────────


class PreBeginTests(_PollCase):
    """Before `restore-begin` lands, the poll must report nothing at all."""

    def test_pre_begin_within_grace_is_still_waiting(self):
        self.write([_record(RECORD_ID, restore_attempts=0)])
        self.poll_restore(prev_attempts=0, elapsed_before=0.0)
        self.assertStillWaiting()

    def test_pre_begin_past_dispatch_grace_reports_never_started(self):
        self.write([_record(RECORD_ID, restore_attempts=0)])
        self.poll_restore(
            prev_attempts=0,
            elapsed_before=self.app_mod.DISPATCH_GRACE
            - self.app_mod.POLL_INTERVAL,
        )
        self.assertFinished(
            "restore did not start — run 'ait frozenagent' or reconcile",
            warn=True,
        )

    def test_a_stale_error_pre_begin_is_not_reported_as_this_attempt_failing(self):
        """THE pin. `restore-begin` clears `last_error`; before it runs, any
        error present belongs to an EARLIER attempt. Reading it here would
        report a restore as failed before it had started."""
        self.write([_record(
            RECORD_ID, restore_attempts=3,
            last_error="deadbeef:session_mismatch",
        )])
        self.poll_restore(prev_attempts=3, elapsed_before=0.0)
        self.assertStillWaiting()

    def test_the_gate_is_attempts_not_state(self):
        """A record already sitting in `restoring` from somebody else's attempt
        must not be read as ours having started."""
        self.write([_record(RECORD_ID, state="restoring", restore_attempts=2,
                            op_nonce="abcd1234")])
        self.poll_restore(prev_attempts=2, elapsed_before=0.0)
        self.assertStillWaiting()


# ───────────────────────── success verdicts ───────────────────────────────


class RestoreSuccessTests(_PollCase):

    def test_live_with_hook_ack_is_a_plain_restore(self):
        self.write([_record(RECORD_ID, state="live", restore_attempts=1,
                            ack="hook")])
        self.poll_restore(prev_attempts=0)
        self.assertFinished("restored", warn=False)

    def test_live_with_liveness_ack_says_capture_kept_and_does_not_warn(self):
        """A SUCCESS, and the only outcome a codex record can reach — never
        styled as an error."""
        self.write([_record(RECORD_ID, state="live", restore_attempts=1,
                            ack="liveness")])
        self.poll_restore(prev_attempts=0)
        self.assertFinished("restored, unverified — capture kept", warn=False)


# ───────────────────────── failure verdicts ───────────────────────────────


class StaleNonceTrapTests(_PollCase):
    """Back at `frozen` after the attempt started ⇒ the restore failed."""

    def test_preserved_error_with_cleared_nonce_is_still_reported(self):
        """THE other pin. Recovery clears the lease but KEEPS `last_error`, so
        `op_nonce` is `""` here. Correlating the error against a freshly-read
        nonce can never match, and would silently downgrade this failure to a
        timeout ("restored elsewhere")."""
        self.write([_record(
            RECORD_ID, state="frozen", restore_attempts=1,
            op_nonce="", last_error="abc12345:session_mismatch",
        )])
        self.poll_restore(prev_attempts=0)
        self.assertFinished(
            "restore failed: session_mismatch — capture kept", warn=True)

    def test_the_reason_is_the_tail_after_the_first_colon(self):
        self.write([_record(RECORD_ID, state="frozen", restore_attempts=1,
                            last_error="abc12345:agent_exited")])
        self.poll_restore(prev_attempts=0)
        self.assertFinished(
            "restore failed: agent_exited — capture kept", warn=True)

    def test_an_error_with_no_colon_is_used_whole(self):
        self.write([_record(RECORD_ID, state="frozen", restore_attempts=1,
                            last_error="boom")])
        self.poll_restore(prev_attempts=0)
        self.assertFinished("restore failed: boom — capture kept", warn=True)

    def test_frozen_with_no_error_still_warns_that_it_ended(self):
        self.write([_record(RECORD_ID, state="frozen", restore_attempts=1,
                            last_error="")])
        self.poll_restore(prev_attempts=0)
        self.assertFinished("restore ended — capture kept", warn=True)


class VanishedAndTimeoutTests(_PollCase):

    def test_a_vanished_record_is_terminal(self):
        self.write([])
        self.poll_restore(prev_attempts=0)
        self.assertFinished("record vanished", warn=True)

    def test_still_transitional_within_the_grace_keeps_waiting(self):
        self.write([_record(RECORD_ID, state="restoring", restore_attempts=1,
                            op_nonce="abcd1234")])
        self.poll_restore(prev_attempts=0, elapsed_before=0.0)
        self.assertStillWaiting()

    def test_a_timeout_names_the_state_and_never_implies_success(self):
        """The record is still transitional and only reconcile can settle it;
        the note must say so rather than implying the restore worked."""
        self.write([_record(RECORD_ID, state="restoring", restore_attempts=1,
                            op_nonce="abcd1234")])
        self.poll_restore(
            prev_attempts=0,
            elapsed_before=self.app_mod.DISPATCH_GRACE + 30.0
            - self.app_mod.POLL_INTERVAL,
        )
        self.assertFinished(
            "restore still restoring after the grace — "
            "run reconcile; capture kept", warn=True)


# ───────────────────────── drop has its own path ──────────────────────────


class DropVerdictTests(_PollCase):
    """`drop` never passes through `restoring` or `live` — it disappears."""

    def test_a_gone_record_is_a_successful_drop(self):
        self.write([])
        self.poll_drop()
        self.assertFinished("dropped — capture removed", warn=False)

    def test_a_surviving_record_within_the_grace_keeps_waiting(self):
        self.write([_record(RECORD_ID)])
        self.poll_drop(elapsed_before=0.0)
        self.assertStillWaiting()

    def test_a_surviving_record_past_the_grace_is_a_failed_drop(self):
        """The coordinator's `DROP_FAILED:` line goes to a detached `run-shell`
        job whose stdout is unreadable, so the record's survival IS the
        observable."""
        self.write([_record(RECORD_ID)])
        self.poll_drop(
            elapsed_before=self.app_mod.DROP_GRACE
            - self.app_mod.POLL_INTERVAL,
        )
        self.assertFinished("drop failed — record kept", warn=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
