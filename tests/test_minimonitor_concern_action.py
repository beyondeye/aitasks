"""Tests for the minimonitor shadow concern-picker wiring (t1037_4).

Mock-based (no live tmux). Covers:
- the pure reverse-lookup matcher ``match_shadow_pane`` (bind, miss, empty
  target, newest-wins on multiple matches);
- the ``action_pick_concerns`` hotkey flow: capture -> parse -> modal ->
  clipboard, with no side effect before an explicit confirm;
- failure degradation (capture returns ``None``) and the "no shadow" / "empty
  parse" guards;
- the duplicate-shadow launch guard in ``action_launch_shadow`` (sync reader,
  no async query, spawns nothing);
- the auto-offer: strict ``has_concern_block`` trigger (an unclosed block does
  not fire) and per-parsed-block de-dup (surrounding pane churn does not
  re-hint; a changed concern does);
- the reject half of the dismiss contract (t1427_2): store pre-fetch, rejection
  and un-rejection persistence, the visible no-task-id refusal, and exit-code
  discrimination. The ``aitask_shadow_rejected.sh`` seam is spied via
  ``_run_rejected_cmd`` — no bash is ever executed here.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m unittest tests.test_minimonitor_concern_action
"""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

from monitor import minimonitor_app as mm  # noqa: E402
from monitor import monitor_core as mc  # noqa: E402
from monitor.concern_parser import (  # noqa: E402
    build_clipboard_payload, concern_marker_line,
)
from monitor.monitor_shared import (  # noqa: E402
    ConcernPickResult, format_stale_duration,
)


_CLOSED_BLOCK = (
    "some earlier pane output\n"
    "===AITASK-CONCERNS===\n"
    "- [high | Step 7 guard] The guard double-commits the lock.\n"
    "- [medium | parser] Multi-block accumulation is undefined.\n"
    "===END-CONCERNS===\n"
)
# Opening fence but no closing fence — a still-streaming block.
_UNCLOSED_BLOCK = (
    "===AITASK-CONCERNS===\n"
    "- [high | Step 7 guard] The guard double-commits the lock.\n"
)
# The capture window started INSIDE a block: items and the closing fence made it
# in, the opening fence did not. Reads as "no concerns" to both parser entry
# points, which is the silent false negative t1187 fixes.
_HEAD_TRUNCATED = (
    "- [high | Step 7 guard] The guard double-commits the lock.\n"
    "- [medium | parser] Multi-block accumulation is undefined.\n"
    "===END-CONCERNS===\n"
)
# A COMPLETE block whose every marker is malformed: no priority in the first,
# an unclosed bracket in the second. Nothing parses, so both the strict trigger
# and the forgiving path see an empty list — the block is real but entirely
# lost, and saying "no concerns" about it would be a false all-clear (t1274).
_MALFORMED_ONLY_BLOCK = (
    "===AITASK-CONCERNS===\n"
    "- [ | Step 7 guard] The guard double-commits the lock.\n"
    "- [medium | parser never closes\n"
    "===END-CONCERNS===\n"
)
# The SAME concerns as _CLOSED_BLOCK, round-headed (t1159_1). Round 2 differs
# from round 1 only in the header — that is the dedup-lift case.
_ROUND1_BLOCK = (
    "some earlier pane output\n"
    "===AITASK-CONCERNS===\n"
    "Round: 1 @ 2026-08-11T14:03:27Z\n"
    "- [high | Step 7 guard] The guard double-commits the lock.\n"
    "- [medium | parser] Multi-block accumulation is undefined.\n"
    "===END-CONCERNS===\n"
)
_ROUND2_BLOCK = _ROUND1_BLOCK.replace(
    "Round: 1 @ 2026-08-11T14:03:27Z", "Round: 2 @ 2026-08-11T14:09:41Z"
)
# A clean-round record: fences with only the round header between them. The
# strict trigger stays False (no items), so the auto-offer must stay silent;
# the `c` path names the round instead of claiming "no concerns detected".
_METADATA_ONLY_BLOCK = (
    "===AITASK-CONCERNS===\n"
    "Round: 3 @ 2026-08-11T14:12:05Z\n"
    "===END-CONCERNS===\n"
)
# Header plus silently-dropped prose, and a still-streaming header-only block:
# both read as meta by the forgiving parser, and NEITHER may be reported as a
# certified clean round (strict-predicate contract, t1159_1 review fix).
_HEADER_PLUS_PROSE_BLOCK = (
    "===AITASK-CONCERNS===\n"
    "Round: 3 @ 2026-08-11T14:12:05Z\n"
    "some stray prose the scanner drops\n"
    "===END-CONCERNS===\n"
)
_STREAMING_HEADER_ONLY = (
    "===AITASK-CONCERNS===\n"
    "Round: 3 @ 2026-08-11T14:12:05Z\n"
)
# A Round:-shaped header that fails the grammar (rounds are 1-based): meta
# reads None, but the producer TRIED to emit metadata — investigable, never
# the generic "no concerns" (t1159_1 review round 4).
_INVALID_ROUND_BLOCK = (
    "===AITASK-CONCERNS===\n"
    "Round: 0 @ 2026-08-11T14:12:05Z\n"
    "===END-CONCERNS===\n"
)


def _async_return(value):
    async def _coro(*args, **kwargs):
        return value
    return _coro


def _stub_capture(test, coro):
    """Bind minimonitor's module-level capture seam for one test (t1289).

    The delegating ``MiniMonitorApp`` method these tests used to stub is gone:
    the call sites resolve the shared capture helper from ``minimonitor_app``'s
    globals, so an instance attribute would intercept nothing. Replaces the
    module attribute instead, restoring the original at teardown (registered at
    first bind, so an early failure cannot leak it). Call again to re-stub
    mid-test.
    """
    if not hasattr(test, "_orig_capture"):
        test._orig_capture = mm.capture_shadow_text
        test.addCleanup(setattr, mm, "capture_shadow_text", test._orig_capture)
    mm.capture_shadow_text = coro


class _FakeMon:
    """Stub TmuxMonitor exposing only the gateway entries the lookups use."""

    def __init__(self, sync_list: str = "", async_list: str = "") -> None:
        self._sync_list = sync_list
        self._async_list = async_list
        self.sync_calls: list = []
        self.async_calls: list = []

    def tmux_run(self, args, timeout=5.0):
        self.sync_calls.append(args)
        return (0, self._sync_list)

    async def tmux_run_async(self, args, timeout=5.0):
        self.async_calls.append(args)
        return (0, self._async_list)


def _mk_app(monitor=None, task_id="1427_2", rejected_rc=0, rejected_out=""):
    # Custom spy attribute names (spy_*) avoid colliding with read-only Textual
    # App properties such as ``clipboard``.
    app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
    app._monitor = monitor
    app._last_concern_block_payload = {}
    app._truncation_warned = set()
    app._unparsed_warned = set()
    app.spy_notify: list = []
    app.spy_pushed: list = []
    app.spy_clipboard: list = []
    app.notify = lambda msg, **kw: app.spy_notify.append(
        (msg, kw.get("severity", "information"))
    )
    app.push_screen = lambda screen, callback=None: app.spy_pushed.append(
        (screen, callback)
    )
    app.copy_to_clipboard = lambda text: app.spy_clipboard.append(text)
    _install_rejection_spy(app, task_id, rejected_rc, rejected_out)
    return app


def _install_rejection_spy(app, task_id, rc=0, out=""):
    """Bind the rejection-store seam so no bash ever runs (t1427_2).

    ``_run_rejected_cmd`` is the single overridable seam on
    ``ShadowRejectionsMixin``; replacing it here records ``(args, stdin)`` and
    returns a canned ``(rc, out)``. ``run_worker`` is driven to completion so a
    persistence call is observable in the same test that triggers it.
    """
    app.spy_rejected: list = []
    app._task_cache = SimpleNamespace(get_task_id_for_pane=lambda pane: task_id)

    async def _fake_cmd(args, stdin_text=""):
        app.spy_rejected.append((list(args), stdin_text))
        return (rc, out)

    app._run_rejected_cmd = _fake_cmd

    def _run_worker(coro, **kwargs):
        asyncio.run(coro)

    app.run_worker = _run_worker


def _writes(app):
    """Only the MUTATING helper calls — the picker also pre-fetches with `list`.

    Asserting on the raw spy would conflate "wrote nothing" with "never even
    read the store", which is the distinction several of these tests turn on.
    """
    return [c for c in app.spy_rejected if c[0][0] in ("add", "remove")]


def _snap(pane_id="%1"):
    return SimpleNamespace(pane=SimpleNamespace(pane_id=pane_id))


def _pick_result(forwarded=(), rejected=(), unrejected=()):
    return ConcernPickResult(
        forwarded=list(forwarded),
        rejected=list(rejected),
        unrejected=tuple(unrejected),
    )


class MatchShadowPaneTests(unittest.TestCase):
    def test_returns_bound_shadow(self):
        out = "%1\t\n%5\t%1\n%6\t%2\n"
        self.assertEqual(mc.match_shadow_pane(out, "%1"), "%5")

    def test_none_when_no_match(self):
        out = "%1\t\n%6\t%2\n"
        self.assertIsNone(mc.match_shadow_pane(out, "%1"))

    def test_empty_target_ignored(self):
        out = "%1\t\n%2\t   \n"
        self.assertIsNone(mc.match_shadow_pane(out, "%1"))

    def test_multiple_matches_returns_newest(self):
        out = "%5\t%1\n%8\t%1\n%3\t%1\n"
        self.assertEqual(mc.match_shadow_pane(out, "%1"), "%8")


class ActionPickConcernsTests(unittest.TestCase):
    def test_happy_path_modal_then_clipboard(self):
        app = _mk_app(_FakeMon(async_list="%5\t%1"))
        app._find_own_agent_snapshot = lambda: _snap("%1")
        _stub_capture(self, _async_return(_CLOSED_BLOCK))

        asyncio.run(app.action_pick_concerns())

        # Modal pushed with the two parsed concerns; nothing on clipboard yet.
        self.assertEqual(len(app.spy_pushed), 1)
        modal, callback = app.spy_pushed[0]
        self.assertEqual(len(modal._concerns), 2)
        self.assertEqual(app.spy_clipboard, [])  # no side effect before confirm

        # Simulate confirm with a forwarded subset -> real callback runs.
        selected = [modal._concerns[0]]
        callback(_pick_result(forwarded=selected))
        self.assertEqual(app.spy_clipboard, [build_clipboard_payload(selected)])
        self.assertTrue(any("copied" in m.lower() for m, _ in app.spy_notify))
        # Forwarding alone must not touch the rejection store.
        self.assertEqual(_writes(app), [])

    def test_cancel_writes_nothing(self):
        app = _mk_app(_FakeMon(async_list="%5\t%1"))
        app._find_own_agent_snapshot = lambda: _snap("%1")
        _stub_capture(self, _async_return(_CLOSED_BLOCK))
        asyncio.run(app.action_pick_concerns())
        _, callback = app.spy_pushed[0]
        callback(None)
        self.assertEqual(app.spy_clipboard, [])
        self.assertEqual(_writes(app), [])

    def test_no_shadow_pane_notifies_nothing_pushed(self):
        app = _mk_app(_FakeMon(async_list="%1\t\n%6\t%2"))  # no shadow for %1
        app._find_own_agent_snapshot = lambda: _snap("%1")
        _stub_capture(self, _async_return(_CLOSED_BLOCK))
        asyncio.run(app.action_pick_concerns())
        self.assertEqual(app.spy_pushed, [])
        self.assertEqual(app.spy_clipboard, [])
        self.assertTrue(any("shadow" in m.lower() for m, _ in app.spy_notify))

    def test_capture_failure_degrades(self):
        app = _mk_app(_FakeMon(async_list="%5\t%1"))
        app._find_own_agent_snapshot = lambda: _snap("%1")
        _stub_capture(self, _async_return(None))  # timeout / nonzero exit
        asyncio.run(app.action_pick_concerns())
        self.assertEqual(app.spy_pushed, [])
        self.assertEqual(app.spy_clipboard, [])
        self.assertTrue(any(sev == "warning" for _, sev in app.spy_notify))

    def test_empty_parse_no_modal(self):
        app = _mk_app(_FakeMon(async_list="%5\t%1"))
        app._find_own_agent_snapshot = lambda: _snap("%1")
        _stub_capture(self, _async_return("no concern block here"))
        asyncio.run(app.action_pick_concerns())
        # Negative control for test_malformed_only_block_opens_the_raw_view: a
        # pane with genuinely no block must open nothing at all (t1293).
        self.assertEqual(app.spy_pushed, [])
        self.assertEqual(app.spy_clipboard, [])
        # A pane with genuinely no block says exactly that — no scare warning.
        self.assertEqual(
            app.spy_notify, [("No concerns detected on the shadow pane", "information")]
        )

    def test_pushed_modal_carries_the_block_meta(self):
        """Caller wiring (t1159_1): the pushed modal INSTANCE has the meta.

        Isolated parser/helper/modal tests all stay green if this caller drops
        the ``block_meta=`` argument — only inspecting the pushed instance
        catches that.
        """
        from monitor.concern_parser import parse_block_meta

        app = _mk_app(_FakeMon(async_list="%5\t%1"))
        app._find_own_agent_snapshot = lambda: _snap("%1")
        _stub_capture(self, _async_return(_ROUND2_BLOCK))
        asyncio.run(app.action_pick_concerns())
        modal, _ = app.spy_pushed[0]
        self.assertEqual(modal._block_meta, parse_block_meta(_ROUND2_BLOCK))
        self.assertIsNotNone(modal._block_meta)

    def test_pushed_modal_meta_is_none_for_a_headerless_block(self):
        app = _mk_app(_FakeMon(async_list="%5\t%1"))
        app._find_own_agent_snapshot = lambda: _snap("%1")
        _stub_capture(self, _async_return(_CLOSED_BLOCK))
        asyncio.run(app.action_pick_concerns())
        modal, _ = app.spy_pushed[0]
        self.assertIsNone(modal._block_meta)

    def test_metadata_only_block_names_the_clean_round(self):
        """A clean-round record is not "no concerns detected" — it is a
        machine-readable statement that round N ran clean (t1159_1)."""
        app = _mk_app(_FakeMon(async_list="%5\t%1"))
        app._find_own_agent_snapshot = lambda: _snap("%1")
        _stub_capture(self, _async_return(_METADATA_ONLY_BLOCK))
        asyncio.run(app.action_pick_concerns())
        self.assertEqual(app.spy_pushed, [])
        self.assertEqual(
            app.spy_notify,
            [("Clean review (round 3) — no concerns", "information")],
        )

    def test_header_with_dropped_prose_warns_and_shows_the_raw_block(self):
        """Strict certification (t1159_1 review fix, round 3): header plus
        silently-dropped prose is malformed output — warn and expose the raw
        block instead of a false "no concerns" all-clear."""
        app = _mk_app(_FakeMon(async_list="%5\t%1"))
        app._find_own_agent_snapshot = lambda: _snap("%1")
        _stub_capture(self, _async_return(_HEADER_PLUS_PROSE_BLOCK))
        asyncio.run(app.action_pick_concerns())
        msg, severity = app.spy_notify[0]
        self.assertNotIn("Clean review", msg)
        self.assertNotIn("No concerns detected", msg)
        self.assertIn("not a clean-round record", msg)
        self.assertEqual(severity, "warning")
        modal, _ = app.spy_pushed[0]
        self.assertIsInstance(modal, mm.ConcernBlockInspectModal)
        self.assertIn("stray prose", modal._raw_block)

    def test_invalid_round_header_warns_and_shows_the_raw_block(self):
        """A grammar-invalid header (`Round: 0`) reads meta=None, but the
        block must NOT be handled as headerless — the producer tried to emit
        metadata and got it wrong, which is investigable (round 4 fix)."""
        app = _mk_app(_FakeMon(async_list="%5\t%1"))
        app._find_own_agent_snapshot = lambda: _snap("%1")
        _stub_capture(self, _async_return(_INVALID_ROUND_BLOCK))
        asyncio.run(app.action_pick_concerns())
        msg, severity = app.spy_notify[0]
        self.assertNotIn("Clean review", msg)
        self.assertNotIn("No concerns detected", msg)
        self.assertIn("invalid round header", msg)
        self.assertEqual(severity, "warning")
        modal, _ = app.spy_pushed[0]
        self.assertIsInstance(modal, mm.ConcernBlockInspectModal)
        self.assertIn("Round: 0", modal._raw_block)

    def test_streaming_header_only_block_is_not_reported_clean(self):
        """An unclosed header-only stream may be about to emit items — warn
        and show the raw block, never the clean-round message."""
        app = _mk_app(_FakeMon(async_list="%5\t%1"))
        app._find_own_agent_snapshot = lambda: _snap("%1")
        _stub_capture(self, _async_return(_STREAMING_HEADER_ONLY))
        asyncio.run(app.action_pick_concerns())
        msg, severity = app.spy_notify[0]
        self.assertNotIn("Clean review", msg)
        self.assertIn("not a clean-round record", msg)
        self.assertEqual(severity, "warning")
        modal, _ = app.spy_pushed[0]
        self.assertIsInstance(modal, mm.ConcernBlockInspectModal)

    def test_malformed_only_block_warns_instead_of_no_concerns(self):
        """A block that parsed to nothing must not be reported as "no concerns".

        `parse_concerns` returns [] for a malformed-only block, so the hotkey
        used to exit on the bland message before the unrecovered-marker count was
        ever consulted — the shadow's whole review vanished silently (t1274).
        """
        app = _mk_app(_FakeMon(async_list="%5\t%1"))
        app._find_own_agent_snapshot = lambda: _snap("%1")
        _stub_capture(self, _async_return(_MALFORMED_ONLY_BLOCK))

        asyncio.run(app.action_pick_concerns())

        self.assertEqual(app.spy_clipboard, [])
        self.assertEqual(len(app.spy_notify), 1)
        message, severity = app.spy_notify[0]
        self.assertEqual(severity, "warning")
        self.assertIn("2 line(s) could not be parsed", message)
        self.assertNotIn("No concerns detected", message)

    def test_malformed_only_block_opens_the_raw_view(self):
        """With no picker there is no banner to hang `u` off (t1293).

        The user pressed `c` deliberately and every marker was lost, so the raw
        block IS the answer — showing it is the only way they can tell an
        over-bound split from a producer typo.
        """
        app = _mk_app(_FakeMon(async_list="%5\t%1"))
        app._find_own_agent_snapshot = lambda: _snap("%1")
        _stub_capture(self, _async_return(_MALFORMED_ONLY_BLOCK))

        asyncio.run(app.action_pick_concerns())

        self.assertEqual(len(app.spy_pushed), 1)
        modal, _callback = app.spy_pushed[0]
        self.assertIsInstance(modal, mm.ConcernBlockInspectModal)
        self.assertEqual(len(modal._unrecovered), 2)
        # The raw region travels with it, not just the offending lines.
        for line in modal._unrecovered:
            self.assertIn(line, modal._raw_block)

    def test_retries_deeper_on_truncated_head(self):
        """A clipped opening fence buys ONE much deeper re-capture (t1187)."""
        app = _mk_app(_FakeMon(async_list="%5\t%1"))
        app._find_own_agent_snapshot = lambda: _snap("%1")
        captures: list = []

        async def _capture(pane, *, lines=None):
            captures.append(lines)
            return _CLOSED_BLOCK if lines else _HEAD_TRUNCATED

        _stub_capture(self, _capture)
        asyncio.run(app.action_pick_concerns())

        # Second call asked for the deeper window; the block was recovered.
        self.assertEqual(captures, [None, mm._SHADOW_DEEP_RETRY_LINES])
        self.assertEqual(len(app.spy_pushed), 1)
        self.assertEqual(len(app.spy_pushed[0][0]._concerns), 2)

    def test_warns_when_deeper_retry_still_truncated(self):
        app = _mk_app(_FakeMon(async_list="%5\t%1"))
        app._find_own_agent_snapshot = lambda: _snap("%1")
        captures: list = []

        async def _capture(pane, *, lines=None):
            captures.append(lines)
            return _HEAD_TRUNCATED

        _stub_capture(self, _capture)
        asyncio.run(app.action_pick_concerns())

        self.assertEqual(captures, [None, mm._SHADOW_DEEP_RETRY_LINES])
        self.assertEqual(app.spy_pushed, [])  # no modal on an unusable block
        self.assertEqual(
            app.spy_notify, [(mm._SHADOW_TRUNCATED_MSG, "warning")]
        )

    def test_genuinely_no_block_keeps_the_plain_message(self):
        """Negative control: absence must not be reported as truncation."""
        app = _mk_app(_FakeMon(async_list="%5\t%1"))
        app._find_own_agent_snapshot = lambda: _snap("%1")
        captures: list = []

        async def _capture(pane, *, lines=None):
            captures.append(lines)
            return "just some agent output\n"

        _stub_capture(self, _capture)
        asyncio.run(app.action_pick_concerns())

        self.assertEqual(captures, [None])  # no pointless deeper re-capture
        self.assertEqual(app.spy_notify, [("No concerns detected on the shadow pane", "information")])


class RejectionPersistenceTests(unittest.TestCase):
    """The reject half of the dismiss contract (t1427_2)."""

    def _picked(self, app, result):
        """Drive one full pick and hand ``result`` to the real callback."""
        app._find_own_agent_snapshot = lambda: _snap("%1")
        _stub_capture(self, _async_return(_CLOSED_BLOCK))
        asyncio.run(app.action_pick_concerns())
        _, callback = app.spy_pushed[0]
        callback(result)

    def test_rejections_only_result_still_persists(self):
        """[rejections_only_result_negative_control]

        Both callbacks used to early-return on ``if not selected:`` — "nothing
        picked, nothing to do". Carrying that shortcut across to the new result
        (``if not result.forwarded: return``) silently discards every
        rejections-only confirm, and the user gets no feedback at all.

        **Verified reachable.** A plain ``if not result`` is NOT the hazard: a
        ``NamedTuple`` with fields is always truthy, so only ``None`` is falsy
        and that mutation is a no-op. The reachable mutation is the one keyed on
        ``forwarded``, and this test was confirmed to fail under it.
        """
        app = _mk_app(_FakeMon(async_list="%5\t%1"), rejected_out="ADDED:1")
        concern = None

        def _run():
            nonlocal concern
            app._find_own_agent_snapshot = lambda: _snap("%1")
            _stub_capture(self, _async_return(_CLOSED_BLOCK))
            asyncio.run(app.action_pick_concerns())
            modal, callback = app.spy_pushed[0]
            concern = modal._concerns[0]
            callback(_pick_result(forwarded=[], rejected=[concern]))

        _run()
        writes = _writes(app)
        self.assertEqual(len(writes), 1, "the rejection was swallowed")
        args, stdin = writes[0]
        self.assertEqual(args[:2], ["add", "1427_2"])
        self.assertIn("--producer", args)
        self.assertEqual(stdin, concern_marker_line(concern) + "\n")
        # Nothing was forwarded, so the clipboard must be untouched.
        self.assertEqual(app.spy_clipboard, [])
        self.assertTrue(any("reject" in m.lower() for m, _ in app.spy_notify))

    def test_forward_and_reject_in_one_confirm_do_both(self):
        app = _mk_app(_FakeMon(async_list="%5\t%1"), rejected_out="ADDED:1")
        app._find_own_agent_snapshot = lambda: _snap("%1")
        _stub_capture(self, _async_return(_CLOSED_BLOCK))
        asyncio.run(app.action_pick_concerns())
        modal, callback = app.spy_pushed[0]
        fwd, rej = modal._concerns[0], modal._concerns[1]
        callback(_pick_result(forwarded=[fwd], rejected=[rej]))

        self.assertEqual(app.spy_clipboard, [build_clipboard_payload([fwd])])
        writes = _writes(app)
        self.assertEqual(len(writes), 1)
        # The REJECTED concern is stored — not the forwarded one.
        self.assertEqual(writes[0][1], concern_marker_line(rej) + "\n")

    def test_unrejected_ids_are_removed(self):
        app = _mk_app(_FakeMon(async_list="%5\t%1"), rejected_out="REMOVED:r1,r3")
        self._picked(app, _pick_result(unrejected=("r1", "r3")))
        writes = _writes(app)
        self.assertEqual(len(writes), 1)
        args, stdin = writes[0]
        self.assertEqual(args, ["remove", "1427_2", "r1", "r3"])
        self.assertEqual(stdin, "")

    def test_no_task_id_is_a_visible_refusal(self):
        """[task_id_refusal_is_visible]

        Asserting only "nothing was written" would pass for a silent no-op, so
        the notify is asserted too — the task requires this be visible.
        """
        app = _mk_app(_FakeMon(async_list="%5\t%1"), task_id=None)
        app._find_own_agent_snapshot = lambda: _snap("%1")
        _stub_capture(self, _async_return(_CLOSED_BLOCK))
        asyncio.run(app.action_pick_concerns())
        modal, callback = app.spy_pushed[0]
        # The picker was told the store is unreachable, before any confirm.
        self.assertTrue(modal._store_unavailable)
        callback(_pick_result(rejected=[modal._concerns[0]]))

        self.assertEqual(_writes(app), [], "wrote without a task id")
        message, severity = app.spy_notify[-1]
        self.assertIn("no task id", message.lower())
        self.assertIn("not persisted", message.lower())
        self.assertEqual(severity, "warning")

    def test_exit_codes_are_discriminated(self):
        """[exit_code_discrimination]

        rc 3 (transient contention), rc 4 (store unusable — never retry) and
        rc 2 (bad request) must reach the user as three DIFFERENT outcomes.
        t1427_1 recorded that conflating 3 and 4 turns a permanent
        misconfiguration into an endless retry.
        """
        seen = {}
        for rc, out in ((3, "LOCK_BUSY"), (4, "store unusable"), (2, "bad id")):
            app = _mk_app(
                _FakeMon(async_list="%5\t%1"), rejected_rc=rc, rejected_out=out
            )
            app._find_own_agent_snapshot = lambda: _snap("%1")
            _stub_capture(self, _async_return(_CLOSED_BLOCK))
            asyncio.run(app.action_pick_concerns())
            modal, callback = app.spy_pushed[0]
            callback(_pick_result(rejected=[modal._concerns[0]]))
            seen[rc] = app.spy_notify[-1]

        self.assertEqual(len(set(m for m, _ in seen.values())), 3, seen)
        self.assertIn("busy", seen[3][0].lower())
        self.assertEqual(seen[3][1], "warning")
        self.assertIn("not retrying", seen[4][0].lower())
        self.assertEqual(seen[4][1], "error")
        self.assertEqual(seen[2][1], "error")
        self.assertNotIn("busy", seen[4][0].lower())

    def test_store_is_prefetched_and_passed_to_the_picker(self):
        app = _mk_app(
            _FakeMon(async_list="%5\t%1"),
            rejected_out=(
                "REJECTED:r1|2026-08-05T14:02:11Z|plan-challenge|"
                "- [high | a] body with | a pipe"
            ),
        )
        app._find_own_agent_snapshot = lambda: _snap("%1")
        _stub_capture(self, _async_return(_CLOSED_BLOCK))
        asyncio.run(app.action_pick_concerns())

        self.assertEqual(app.spy_rejected[0][0], ["list", "1427_2", "--machine"])
        modal, _ = app.spy_pushed[0]
        self.assertFalse(modal._store_unavailable)
        self.assertEqual(len(modal._rejected_entries), 1)
        entry = modal._rejected_entries[0]
        self.assertEqual(entry.id, "r1")
        # The marker line is last on the wire BECAUSE it contains `|`.
        self.assertEqual(entry.marker_line, "- [high | a] body with | a pipe")

    def test_empty_store_sentinel_yields_no_entries(self):
        app = _mk_app(_FakeMon(async_list="%5\t%1"), rejected_out="NO_REJECTIONS")
        app._find_own_agent_snapshot = lambda: _snap("%1")
        _stub_capture(self, _async_return(_CLOSED_BLOCK))
        asyncio.run(app.action_pick_concerns())
        modal, _ = app.spy_pushed[0]
        self.assertEqual(modal._rejected_entries, [])
        self.assertFalse(modal._store_unavailable)


class CaptureArgvTests(unittest.TestCase):
    """What ``capture_shadow_text`` actually runs (t1187).

    Every other test in this file stubs the helper out, so nothing sees the real
    CLI invocation — and the whole t1187 capture fix lives in that argv. Driven
    through ``mm.`` rather than ``mc.`` on purpose: that is the exact binding
    minimonitor's own call sites resolve.
    """

    def _run_capture(self, **kwargs):
        recorded: dict = {}

        class _FakeProc:
            returncode = 0

            async def communicate(self):
                return (b"captured text", b"")

        async def _fake_exec(*argv, **kw):
            recorded["argv"] = list(argv)
            recorded["env"] = kw.get("env")
            return _FakeProc()

        orig = asyncio.create_subprocess_exec
        asyncio.create_subprocess_exec = _fake_exec
        try:
            out = asyncio.run(mm.capture_shadow_text("%5", **kwargs))
        finally:
            asyncio.create_subprocess_exec = orig
        return out, recorded

    def test_uses_plan_review_depth(self):
        out, rec = self._run_capture()
        self.assertEqual(out, "captured text")
        # `--any-pane` opts this reader out of the helper's wrong-pane refusal
        # (t1319) — see the rationale docstring on the matching test in
        # tests/test_shadow_seam.py. Do not copy it to a model-supplied caller.
        self.assertEqual(rec["argv"][1:], ["--deep", "--any-pane", "%5"])
        self.assertTrue(rec["argv"][0].endswith("aitask_shadow_capture.sh"))
        # No override => inherit the ambient environment.
        self.assertIsNone(rec["env"])

    def test_lines_override_sets_plan_capture_lines(self):
        _, rec = self._run_capture(lines=mm._SHADOW_DEEP_RETRY_LINES)
        # The deeper retry changes the depth, never the target or the flags.
        self.assertEqual(rec["argv"][1:], ["--deep", "--any-pane", "%5"])
        self.assertEqual(
            rec["env"]["SHADOW_PLAN_CAPTURE_LINES"],
            str(mm._SHADOW_DEEP_RETRY_LINES),
        )
        self.assertIn("PATH", rec["env"])  # inherited, not replaced


class LaunchShadowGuardTests(unittest.TestCase):
    def test_refuses_duplicate_shadow_via_sync_reader(self):
        mon = _FakeMon(sync_list="%5\t%1")  # an existing shadow bound to %1
        app = _mk_app(mon)
        app._find_own_agent_snapshot = lambda: _snap("%1")

        calls: list = []
        # Rebind on monitor_core: the spawn body was lifted there (t1216_4), so a
        # rebind on `mm` would intercept nothing and reach real tmux.
        orig = mc.launch_in_tmux
        mc.launch_in_tmux = lambda *a, **k: (calls.append((a, k)), (None, None))[1]
        try:
            app.action_launch_shadow()
        finally:
            mc.launch_in_tmux = orig

        self.assertEqual(calls, [])  # never spawned a shadow
        self.assertTrue(
            any("already running" in m.lower() for m, _ in app.spy_notify)
        )
        # Guard used the SYNC reader — no async query issued (no await trap).
        self.assertTrue(mon.sync_calls)
        self.assertEqual(mon.async_calls, [])


class AutoOfferTests(unittest.TestCase):
    def _app(self, capture_value, async_list="%5\t%1"):
        app = _mk_app(_FakeMon(async_list=async_list))
        app._find_own_agent_snapshot = lambda: _snap("%1")
        _stub_capture(self, _async_return(capture_value))
        return app

    def test_unclosed_block_does_not_fire(self):
        app = self._app(_UNCLOSED_BLOCK)
        asyncio.run(app._maybe_offer_concerns())
        self.assertEqual(app.spy_notify, [])
        self.assertEqual(app._last_concern_block_payload, {})

    def test_closed_block_fires_once(self):
        app = self._app(_CLOSED_BLOCK)
        asyncio.run(app._maybe_offer_concerns())
        asyncio.run(app._maybe_offer_concerns())  # same block, second tick
        self.assertEqual(len(app.spy_notify), 1)

    def test_surrounding_churn_does_not_refire(self):
        app = self._app(_CLOSED_BLOCK)
        asyncio.run(app._maybe_offer_concerns())
        self.assertEqual(len(app.spy_notify), 1)
        # Same concern block, different surrounding pane text -> still one hint.
        _stub_capture(self, _async_return(
            "NEW PROMPT LINE\n" + _CLOSED_BLOCK + "\n$ "
        ))
        asyncio.run(app._maybe_offer_concerns())
        self.assertEqual(len(app.spy_notify), 1)

    def test_changed_concern_refires(self):
        app = self._app(_CLOSED_BLOCK)
        asyncio.run(app._maybe_offer_concerns())
        changed = _CLOSED_BLOCK.replace(
            "double-commits the lock", "leaks a file handle"
        )
        _stub_capture(self, _async_return(changed))
        asyncio.run(app._maybe_offer_concerns())
        self.assertEqual(len(app.spy_notify), 2)

    def test_repeat_round_with_identical_concerns_refires(self):
        """The dedup lift (t1159_1): a round-2 review re-raising the SAME
        concerns is news — the shadow re-reviewed and stands by them. The
        payload-keyed dedup alone would silently swallow it."""
        app = self._app(_ROUND1_BLOCK)
        asyncio.run(app._maybe_offer_concerns())
        self.assertEqual(len(app.spy_notify), 1)
        _stub_capture(self, _async_return(_ROUND2_BLOCK))
        asyncio.run(app._maybe_offer_concerns())
        self.assertEqual(len(app.spy_notify), 2)
        # The toast names the round of the re-offer.
        self.assertIn("(round 2)", app.spy_notify[1][0])

    def test_identical_round_still_fires_once(self):
        """Same round, same concerns, re-captured → one notify, as today."""
        app = self._app(_ROUND1_BLOCK)
        asyncio.run(app._maybe_offer_concerns())
        asyncio.run(app._maybe_offer_concerns())
        self.assertEqual(len(app.spy_notify), 1)

    def test_metadata_only_block_stays_silent(self):
        """A clean-round record has no items ⇒ the strict trigger stays False
        and the auto-offer neither toasts nor warns (t1159_1)."""
        app = self._app(_METADATA_ONLY_BLOCK)
        asyncio.run(app._maybe_offer_concerns())
        self.assertEqual(app.spy_notify, [])

    def test_no_shadow_skips_silently(self):
        app = self._app(_CLOSED_BLOCK, async_list="%1\t\n%6\t%2")  # no shadow
        asyncio.run(app._maybe_offer_concerns())
        self.assertEqual(app.spy_notify, [])

    def test_truncated_head_warns_once_per_pane(self):
        """A clipped block is reported, not swallowed — but only once (t1187).

        The auto-offer never retries deeper (it runs every tick); it names the
        capture window so the user can deepen it or press 'c', which does retry.
        """
        app = self._app(_HEAD_TRUNCATED)
        asyncio.run(app._maybe_offer_concerns())
        asyncio.run(app._maybe_offer_concerns())  # still truncated, second tick
        self.assertEqual(
            app.spy_notify, [(mm._SHADOW_TRUNCATED_MSG, "warning")]
        )
        self.assertEqual(app._truncation_warned, {"%5"})

    def test_malformed_only_block_warns_once_per_pane(self):
        """A complete-but-unparseable block is the same silent false negative.

        `has_concern_block` is false because nothing parsed, so without this the
        auto-offer stays completely quiet about a review the shadow did emit
        (t1274).
        """
        app = self._app(_MALFORMED_ONLY_BLOCK)
        asyncio.run(app._maybe_offer_concerns())
        asyncio.run(app._maybe_offer_concerns())  # same block, second tick
        self.assertEqual(len(app.spy_notify), 1)
        message, severity = app.spy_notify[0]
        self.assertEqual(severity, "warning")
        self.assertIn("could not be parsed", message)
        self.assertEqual(app._unparsed_warned, {"%5"})
        self.assertEqual(app._truncation_warned, set())

    def test_block_free_pane_never_warns_about_unparsed_lines(self):
        """Negative control: the warning is about a BLOCK, not any pane text."""
        app = self._app("just some agent output\n- [not a marker] prose\n")
        asyncio.run(app._maybe_offer_concerns())
        self.assertEqual(app.spy_notify, [])
        self.assertEqual(app._unparsed_warned, set())

    def test_complete_block_rearms_the_unparsed_warning(self):
        app = self._app(_MALFORMED_ONLY_BLOCK)
        asyncio.run(app._maybe_offer_concerns())
        self.assertEqual(app._unparsed_warned, {"%5"})
        # A parseable block arrives: normal hint, and the pane is re-armed.
        _stub_capture(self, _async_return(_CLOSED_BLOCK))
        asyncio.run(app._maybe_offer_concerns())
        self.assertEqual(app._unparsed_warned, set())
        # Malformed again later -> warns again rather than staying silent.
        _stub_capture(self, _async_return(_MALFORMED_ONLY_BLOCK))
        asyncio.run(app._maybe_offer_concerns())
        self.assertEqual(app._unparsed_warned, {"%5"})
        self.assertEqual(
            sum(1 for _, sev in app.spy_notify if sev == "warning"), 2
        )

    def test_complete_block_rearms_the_truncation_warning(self):
        app = self._app(_HEAD_TRUNCATED)
        asyncio.run(app._maybe_offer_concerns())
        # A complete block arrives: normal hint, and the pane is re-armed.
        _stub_capture(self, _async_return(_CLOSED_BLOCK))
        asyncio.run(app._maybe_offer_concerns())
        self.assertEqual(app._truncation_warned, set())
        # Truncated again later -> warns again rather than staying silent.
        _stub_capture(self, _async_return(_HEAD_TRUNCATED))
        asyncio.run(app._maybe_offer_concerns())
        self.assertEqual(
            [m for m, _ in app.spy_notify].count(mm._SHADOW_TRUNCATED_MSG), 2
        )

    def test_no_block_at_all_stays_silent(self):
        """Negative control: silence is still correct when there is no block."""
        app = self._app("just some agent output\n")
        asyncio.run(app._maybe_offer_concerns())
        self.assertEqual(app.spy_notify, [])
        self.assertEqual(app._truncation_warned, set())

    def test_no_shadow_clears_stale_banner(self):
        app = self._app(_CLOSED_BLOCK, async_list="%1\t\n%6\t%2")  # no shadow
        app._shadow_read_recency = mm.ReadRecency(True, 1000.0)  # prior warning
        asyncio.run(app._maybe_offer_concerns())
        self.assertIsNone(app._shadow_feedback_stale)
        self.assertEqual(app._shadow_stale_banner_text, "")


def _assert_warning_still_standing(test, app):
    """The preserved-warning invariant, probed by MEANING not by a sentinel.

    Since t1493 the banner is re-rendered from the recorded verdict on every
    tick (it must also reflect block age, which the throttled read-recency
    compare never sees), so a "the literal string was not touched" assertion no
    longer describes the architecture. What must remain true is that an
    indeterminate read never *clears* a standing warning — so this asserts the
    verdict survived AND the banner still warns. Both fail if the code clears:
    the verdict would be False and the banner "".
    """
    test.assertIs(app._shadow_feedback_stale, True)
    test.assertTrue(
        app._shadow_stale_banner_text,
        "an indeterminate read CLEARED the standing staleness banner",
    )
    test.assertIn("stale", app._shadow_stale_banner_text.lower())


class ShadowFreshnessTests(unittest.TestCase):
    """Shadow-feedback staleness compare + display (t1104, timestamp model)."""

    # eps = max(2, refresh_seconds=3) = 3 for these apps.
    def _fresh_app(self, analyzed_at, last_change, capture="",
                   async_list="%5\t%1", option_ok=True, prior_recency=None):
        """Build an app whose shadow timeline can be advanced mid-test.

        `_shadow_feedback_stale` is a read-only property since t1493 (verdict
        and its `analyzed_at` are written as one `ReadRecency` tuple, so they
        cannot desync). Tests that need a prior standing warning pass
        `prior_recency=` rather than poking the attribute, which is what stops
        the direct assignment coming back.

        The stamp / last-change values live in one-element holders so a test can
        walk T0 -> T1 -> T2 on a SINGLE app, which is the only way to exercise
        the transition the live defect showed.
        """
        app = _mk_app(_FakeMon(async_list=async_list))
        app._find_own_agent_snapshot = lambda: _snap("%1")
        _stub_capture(self, _async_return(capture))
        app._refresh_seconds = 3
        if prior_recency is not None:
            app._shadow_read_recency = prior_recency
        # `(ok, value)` per the real contract (t1451): `option_ok=False` is
        # "tmux could not answer", NOT a verified-unset option.
        app._stamp = ["" if analyzed_at is None else str(analyzed_at)]
        app._ok = [option_ok]
        app._opt_calls: list = []

        async def _opt(pane, option):
            app._opt_calls.append((pane, option))
            return (app._ok[0], app._stamp[0])

        app._monitor.get_pane_option = _opt
        # Spy the (sync) followed-pane last-change lookup so the cost gate and
        # the preserve-on-unobserved path are assertable.
        calls: list = []
        app._lcw = [last_change]

        def _lcw(pane):
            calls.append(pane)
            return app._lcw[0]

        app._monitor.get_last_change_wall = _lcw
        app._lcw_calls = calls
        return app

    def test_change_after_analysis_marks_stale(self):
        # Followed changed 10s after the shadow read it (> eps) ⇒ stale.
        app = self._fresh_app(1000.0, 1010.0)
        asyncio.run(app._maybe_offer_concerns())
        self.assertIs(app._shadow_feedback_stale, True)
        self.assertIn("stale", app._shadow_stale_banner_text.lower())
        self.assertIn("analyzed", app._shadow_stale_banner_text.lower())
        self.assertEqual(app._lcw_calls, ["%1"])

    def test_no_change_since_analysis_is_current(self):
        # Followed last changed before the shadow read it ⇒ current.
        app = self._fresh_app(1000.0, 995.0)
        asyncio.run(app._maybe_offer_concerns())
        self.assertIs(app._shadow_feedback_stale, False)
        self.assertEqual(app._shadow_stale_banner_text, "")

    def test_within_epsilon_not_stale(self):
        # A change 2s after the read is inside eps (3s) — detection-lag jitter,
        # NOT a genuine move-on (this is the idle-render-settle false positive).
        app = self._fresh_app(1000.0, 1002.0)
        asyncio.run(app._maybe_offer_concerns())
        self.assertIs(app._shadow_feedback_stale, False)

    def test_no_stamp_skips_last_change_lookup(self):
        # Shadow never analyzed — no warning, and the followed lookup is skipped.
        app = self._fresh_app(None, 1010.0)
        asyncio.run(app._maybe_offer_concerns())
        self.assertIs(app._shadow_feedback_stale, False)
        self.assertEqual(app._shadow_stale_banner_text, "")
        self.assertEqual(app._lcw_calls, [])  # cost gate: never looked up

    def test_unobserved_followed_preserves_prior_stale(self):
        # Followed pane not observed yet (last-change None) must NOT clear a
        # standing 'stale' warning.
        app = self._fresh_app(1000.0, None)
        app._shadow_read_recency = mm.ReadRecency(True, 1000.0)
        app._shadow_stale_combined = True
        app._shadow_stale_banner_text = "PRIOR-WARNING"
        asyncio.run(app._maybe_offer_concerns())
        _assert_warning_still_standing(self, app)

    def test_malformed_stamp_preserves_prior_stale(self):
        app = self._fresh_app("not-a-number", 1010.0)
        app._shadow_read_recency = mm.ReadRecency(True, 1000.0)
        app._shadow_stale_combined = True
        app._shadow_stale_banner_text = "PRIOR-WARNING"
        asyncio.run(app._maybe_offer_concerns())
        _assert_warning_still_standing(self, app)

    def test_option_read_failure_preserves_prior_stale(self):
        """t1451, on the user-visible surface. `get_pane_option` used to return
        `""` on `rc != 0`, which `compute_shadow_staleness` read as "the shadow
        has never analyzed anything: nothing to warn about" — so a tmux timeout
        WIPED a standing staleness banner. An unverifiable read must preserve
        whatever the user is already being shown.

        Note the stamp is deliberately empty, exactly as the old failure path
        produced it: this fails against the pre-fix code (the banner clears)
        rather than merely re-asserting the fixed shape.
        """
        app = self._fresh_app(None, 1010.0, option_ok=False)
        app._shadow_read_recency = mm.ReadRecency(True, 1000.0)
        app._shadow_stale_combined = True
        app._shadow_stale_banner_text = "PRIOR-WARNING"
        asyncio.run(app._maybe_offer_concerns())
        _assert_warning_still_standing(self, app)
        self.assertEqual(app._lcw_calls, [])  # cost gate holds on this path too

    def test_auto_offer_notify_carries_stale_marker(self):
        app = self._fresh_app(1000.0, 1010.0, capture=_CLOSED_BLOCK)
        asyncio.run(app._maybe_offer_concerns())
        self.assertEqual(len(app.spy_notify), 1)
        self.assertIn("STALE", app.spy_notify[0][0])

    def test_format_stale_duration(self):
        f = format_stale_duration
        self.assertEqual(f(5), "5s")
        self.assertEqual(f(65), "1m05s")
        self.assertEqual(f(3720), "1h02m")

    def test_freshness_throttled_to_every_other_tick(self):
        # Two ticks ⇒ the compare (and its pane lookups) runs only once.
        app = self._fresh_app(1000.0, 1010.0)
        asyncio.run(app._maybe_offer_concerns())  # tick 1 — runs
        asyncio.run(app._maybe_offer_concerns())  # tick 2 — skipped
        self.assertEqual(len(app._lcw_calls), 1)
        asyncio.run(app._maybe_offer_concerns())  # tick 3 — runs
        self.assertEqual(len(app._lcw_calls), 2)


if __name__ == "__main__":
    unittest.main()


# Epoch of `_ROUND1_BLOCK`'s header (2026-08-11T14:03:27Z) and of
# `_ROUND2_BLOCK`'s (14:09:41Z). Pinned so a timeline can be built around them.
_R1_EPOCH = 1786457007.0
_R2_EPOCH = 1786457381.0


class BlockAgeStalenessTests(unittest.TestCase):
    """The third freshness signal, end to end through the app (t1493).

    The live defect: after round 1, three `refetch and recheck` rounds each
    re-read the pane and answered in PROSE — no block. Every refetch restamped
    `@aitask_shadow_analyzed_at`, so read recency said "current" and the picker
    re-offered round 1's concerns with no stale warning.
    """

    def _app(self, capture, analyzed_at, last_change, option_ok=True):
        app = _mk_app(_FakeMon(async_list="%5\t%1"))
        app._find_own_agent_snapshot = lambda: _snap("%1")
        _stub_capture(self, _async_return(capture))
        app._refresh_seconds = 3
        app._stamp = ["" if analyzed_at is None else str(analyzed_at)]
        app._ok = [option_ok]
        app._opt_calls: list = []

        async def _opt(pane, option):
            app._opt_calls.append((pane, option))
            return (app._ok[0], app._stamp[0])

        app._monitor.get_pane_option = _opt
        app._lcw = [last_change]
        app._monitor.get_last_change_wall = lambda pane: app._lcw[0]
        return app

    # -- the reported chronology, on ONE app ---------------------------------

    def test_prose_only_refetch_keeps_the_block_stale(self):
        """T0 offer -> T1 agent moves on -> T2 shadow re-reads, emits nothing.

        At T2 read recency flips to *current* (the shadow really did look), so
        pre-t1493 the banner cleared and `c` showed round 1 as fresh. Block age
        must hold the verdict at stale, because the BLOCK still predates T1.
        """
        # T0: round 1 emitted; agent last changed before it; shadow read it.
        app = self._app(_ROUND1_BLOCK, _R1_EPOCH, _R1_EPOCH - 10)
        asyncio.run(app._maybe_offer_concerns())
        self.assertEqual(len(app.spy_notify), 1)          # announced once
        self.assertIs(app._shadow_stale_combined, False)  # genuinely current
        self.assertEqual(app._shadow_stale_banner_text, "")

        # T1: the followed agent moves on. Shadow has not looked since.
        app._lcw[0] = _R1_EPOCH + 300
        asyncio.run(app._maybe_offer_concerns())
        self.assertIs(app._shadow_stale_combined, True)
        self.assertIn("stale", app._shadow_stale_banner_text.lower())

        # T2: the shadow refetches (restamping) and answers in prose — the pane
        # still carries the SAME round-1 block. Read recency now says current.
        app._stamp[0] = str(_R1_EPOCH + 400)
        app._shadow_freshness_tick = 0  # ensure the throttled compare runs
        asyncio.run(app._maybe_offer_concerns())
        self.assertIs(
            app._shadow_feedback_stale, False,
            "read recency should read 'current' here — that is the trap",
        )
        self.assertIs(
            app._shadow_stale_combined, True,
            "block age must hold the verdict at stale after a prose-only "
            "refetch (t1493)",
        )
        self.assertIn("predates", app._shadow_stale_banner_text)
        # The toast must NOT re-fire: the block is unchanged, so the dedup
        # return is correct and the BANNER owns this transition.
        self.assertEqual(len(app.spy_notify), 1)

        # ...and pressing `c` now must label the concerns stale.
        asyncio.run(app.action_pick_concerns())
        modal, _ = app.spy_pushed[0]
        self.assertIs(modal._stale, True)

    # -- applicability: a pane with no block must behave as it always did ----

    def test_no_block_pane_is_not_dragged_into_unknown(self):
        """An explain-only shadow has no feedback whose age could be unknown."""
        app = self._app("just agent prose\n$ ", _R1_EPOCH, _R1_EPOCH - 10)
        asyncio.run(app._maybe_offer_concerns())
        self.assertIs(app._shadow_stale_combined, False)
        self.assertEqual(app._shadow_stale_banner_text, "")

    def test_no_block_pane_still_reports_read_recency_staleness(self):
        app = self._app("just agent prose\n$ ", _R1_EPOCH, _R1_EPOCH + 300)
        asyncio.run(app._maybe_offer_concerns())
        self.assertIs(app._shadow_stale_combined, True)
        self.assertIn("moved on", app._shadow_stale_banner_text)

    def test_a_pre_header_block_arriving_on_a_clean_pane_escalates(self):
        """The same-app transition, and the sharpest form of the applicability
        rule: no block (verdict False) -> a pre-round-header block appears.

        `False` is not a standing warning, so the move to `None` is an
        ESCALATION and must be recorded. A preserve rule that kept any prior
        non-None verdict would swallow it and keep presenting an unverifiable
        block as current — this task's own defect, one tick later.
        """
        app = self._app("just agent prose\n$ ", _R1_EPOCH, _R1_EPOCH - 10)
        asyncio.run(app._maybe_offer_concerns())
        self.assertIs(app._shadow_stale_combined, False)
        self.assertEqual(app._shadow_stale_banner_text, "")

        _stub_capture(self, _async_return(_CLOSED_BLOCK))  # pre-header block
        app._shadow_freshness_tick = 0
        asyncio.run(app._maybe_offer_concerns())
        self.assertIsNone(app._shadow_stale_combined)
        self.assertIn("unknown", app._shadow_stale_banner_text.lower())

    def test_a_standing_warning_survives_a_drop_to_unknown(self):
        """The other side of the same rule: True must NOT be cleared.

        Paired with the test above so neither direction can be satisfied by a
        blanket policy — "always preserve" fails the escalation, "never
        preserve" fails this one.
        """
        # The warning must be BLOCK-AGE driven for this to be reachable: while
        # read recency is True the join returns True regardless, so combined
        # could never drop to None. Here the shadow has read recently
        # (analyzed_at is after the change) and only the block is old.
        app = self._app(_ROUND1_BLOCK, _R1_EPOCH + 400, _R1_EPOCH + 300)
        asyncio.run(app._maybe_offer_concerns())
        self.assertIs(app._shadow_feedback_stale, False)   # read recency: current
        self.assertIs(app._shadow_stale_combined, True)    # ...block age: stale
        standing = app._shadow_stale_banner_text
        self.assertIn("predates", standing)

        # The round header is lost (capture degrades / an older block scrolls
        # into the window), so block age becomes unknowable: combined -> None.
        _stub_capture(self, _async_return(_CLOSED_BLOCK))
        app._shadow_freshness_tick = 0
        asyncio.run(app._maybe_offer_concerns())
        self.assertIs(app._shadow_stale_combined, True)
        self.assertEqual(app._shadow_stale_banner_text, standing)

    def test_pre_header_block_reads_unknown_not_current(self):
        """Requirement 3's negative control, one fixture away from the case
        above: a block IS present, so its unknown age is real uncertainty."""
        app = self._app(_CLOSED_BLOCK, _R1_EPOCH, _R1_EPOCH - 10)
        asyncio.run(app._maybe_offer_concerns())
        self.assertIsNone(app._shadow_stale_combined)
        self.assertIsNot(app._shadow_stale_combined, False)
        self.assertIn("unknown", app._shadow_stale_banner_text.lower())

    def test_pre_header_block_reaches_the_picker_as_unknown(self):
        app = self._app(_CLOSED_BLOCK, _R1_EPOCH, _R1_EPOCH - 10)
        asyncio.run(app.action_pick_concerns())
        modal, _ = app.spy_pushed[0]
        self.assertIsNone(modal._stale)
        self.assertIsNot(modal._stale, False)

    # -- picker snapshot coherence -------------------------------------------

    def test_picker_uses_its_own_capture_not_the_tick_cache(self):
        """A newer round arriving between the tick and the keypress.

        Reusing `_shadow_stale_combined` would label round 2's concerns with
        round 1's freshness — confidently and wrongly.
        """
        app = self._app(_ROUND1_BLOCK, _R1_EPOCH, _R1_EPOCH + 300)
        asyncio.run(app._maybe_offer_concerns())
        self.assertIs(app._shadow_stale_combined, True)  # cached: stale

        # Round 2 lands, produced AFTER the agent's last change — and the
        # shadow necessarily re-read the pane to produce it, so its stamp
        # advances too. Both signals are now genuinely current.
        app._stamp[0] = str(_R2_EPOCH)
        _stub_capture(self, _async_return(_ROUND2_BLOCK))
        asyncio.run(app.action_pick_concerns())
        modal, _ = app.spy_pushed[0]
        self.assertEqual(modal._block_meta.round, 2)
        self.assertIs(
            modal._stale, False,
            "the picker labelled round 2 with the cached round-1 verdict",
        )

    def test_picker_sees_a_staleness_that_arrived_after_the_tick(self):
        """The inverse: cached fresh, stale by the time `c` is pressed."""
        app = self._app(_ROUND1_BLOCK, _R1_EPOCH, _R1_EPOCH - 10)
        asyncio.run(app._maybe_offer_concerns())
        self.assertIs(app._shadow_stale_combined, False)

        app._lcw[0] = _R1_EPOCH + 300  # agent moves on, no new tick
        asyncio.run(app.action_pick_concerns())
        modal, _ = app.spy_pushed[0]
        self.assertIs(modal._stale, True)

    def test_picker_recomputes_read_recency_on_every_press(self):
        """Not only when the cache is indeterminate — proven by call count."""
        app = self._app(_ROUND1_BLOCK, _R1_EPOCH, _R1_EPOCH - 10)
        asyncio.run(app._maybe_offer_concerns())
        before = len(app._opt_calls)
        asyncio.run(app.action_pick_concerns())
        self.assertEqual(len(app._opt_calls), before + 1)

    def test_picker_carries_a_detail_naming_the_round_and_the_gap(self):
        app = self._app(_ROUND1_BLOCK, _R1_EPOCH, _R1_EPOCH + 300)
        asyncio.run(app.action_pick_concerns())
        modal, _ = app.spy_pushed[0]
        self.assertIn("round 1", modal._stale_detail)
        self.assertIn("5m00s", modal._stale_detail)  # 300s, not now-reviewed

    # -- write-back: one rule per value --------------------------------------

    def test_block_age_alone_establishes_stale_despite_unreadable_stamp(self):
        """The case a blanket `read_stale is not None` gate would discard."""
        app = self._app(_ROUND1_BLOCK, None, _R1_EPOCH + 300, option_ok=False)
        asyncio.run(app.action_pick_concerns())
        modal, _ = app.spy_pushed[0]
        self.assertIs(modal._stale, True)
        self.assertIs(app._shadow_stale_combined, True)
        # Read recency itself was NOT written — it stayed indeterminate.
        # Probed with the same default the property uses: `_mk_app` builds via
        # __new__, so "never written" shows up as the attribute being absent.
        self.assertIsNone(
            getattr(app, "_shadow_read_recency", mm._UNKNOWN_RECENCY).stale
        )

    def test_indeterminate_everything_preserves_a_standing_warning(self):
        """Exercises the combined-None preserve branch specifically."""
        app = self._app(_CLOSED_BLOCK, None, _R1_EPOCH + 300, option_ok=False)
        app._shadow_stale_combined = True
        app._shadow_stale_banner_text = "PRIOR-WARNING"
        asyncio.run(app._maybe_offer_concerns())
        self.assertIs(app._shadow_stale_combined, True)
        self.assertEqual(app._shadow_stale_banner_text, "PRIOR-WARNING")

    # -- the banner step runs unthrottled ------------------------------------

    def test_banner_updates_on_a_tick_the_throttled_compare_skips(self):
        """The read-recency compare costs a tmux read and runs every OTHER
        tick; block age is free and must be re-evaluated every tick, or the
        became-stale transition waits up to two ticks to appear."""
        app = self._app(_ROUND1_BLOCK, _R1_EPOCH, _R1_EPOCH - 10)
        asyncio.run(app._maybe_offer_concerns())   # tick 1 (odd): compare runs
        opt_after_first = len(app._opt_calls)
        self.assertEqual(app._shadow_stale_banner_text, "")

        app._lcw[0] = _R1_EPOCH + 300              # agent moves on
        asyncio.run(app._maybe_offer_concerns())   # tick 2 (even): SKIPPED
        self.assertEqual(
            len(app._opt_calls), opt_after_first,
            "the throttled read-recency compare should not have run",
        )
        self.assertIs(app._shadow_stale_combined, True)
        self.assertIn("stale", app._shadow_stale_banner_text.lower())

    # -- toast tri-state ------------------------------------------------------

    def test_toast_marks_a_new_block_that_is_already_stale(self):
        app = self._app(_ROUND1_BLOCK, _R1_EPOCH, _R1_EPOCH + 300)
        asyncio.run(app._maybe_offer_concerns())
        self.assertIn("STALE", app.spy_notify[0][0])

    def test_toast_marks_unknown_freshness(self):
        app = self._app(_CLOSED_BLOCK, _R1_EPOCH, _R1_EPOCH - 10)
        asyncio.run(app._maybe_offer_concerns())
        self.assertIn("freshness unknown", app.spy_notify[0][0])

    def test_toast_is_clean_when_the_block_is_genuinely_current(self):
        app = self._app(_ROUND2_BLOCK, _R2_EPOCH, _R2_EPOCH - 10)
        asyncio.run(app._maybe_offer_concerns())
        self.assertNotIn("STALE", app.spy_notify[0][0])
        self.assertNotIn("unknown", app.spy_notify[0][0])
