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
        app._shadow_feedback_stale = True  # a prior standing warning
        asyncio.run(app._maybe_offer_concerns())
        self.assertIsNone(app._shadow_feedback_stale)
        self.assertEqual(app._shadow_stale_banner_text, "")


class ShadowFreshnessTests(unittest.TestCase):
    """Shadow-feedback staleness compare + display (t1104, timestamp model)."""

    # eps = max(2, refresh_seconds=3) = 3 for these apps.
    def _fresh_app(self, analyzed_at, last_change, capture="",
                   async_list="%5\t%1"):
        app = _mk_app(_FakeMon(async_list=async_list))
        app._find_own_agent_snapshot = lambda: _snap("%1")
        _stub_capture(self, _async_return(capture))
        app._refresh_seconds = 3
        stamp = "" if analyzed_at is None else str(analyzed_at)
        app._monitor.get_pane_option = _async_return(stamp)
        # Spy the (sync) followed-pane last-change lookup so the cost gate and
        # the preserve-on-unobserved path are assertable.
        calls: list = []

        def _lcw(pane):
            calls.append(pane)
            return last_change

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
        app._shadow_feedback_stale = True
        app._shadow_stale_banner_text = "PRIOR-WARNING"
        asyncio.run(app._maybe_offer_concerns())
        self.assertIs(app._shadow_feedback_stale, True)
        self.assertEqual(app._shadow_stale_banner_text, "PRIOR-WARNING")

    def test_malformed_stamp_preserves_prior_stale(self):
        app = self._fresh_app("not-a-number", 1010.0)
        app._shadow_feedback_stale = True
        app._shadow_stale_banner_text = "PRIOR-WARNING"
        asyncio.run(app._maybe_offer_concerns())
        self.assertIs(app._shadow_feedback_stale, True)
        self.assertEqual(app._shadow_stale_banner_text, "PRIOR-WARNING")

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
