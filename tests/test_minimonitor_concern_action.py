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
from monitor.prompt_patterns import agent_key_from_command  # noqa: E402
from monitor import monitor_core as mc  # noqa: E402
from monitor.concern_parser import (  # noqa: E402
    Concern,
    build_clipboard_payload, concern_marker_line,
)
from monitor.monitor_shared import (  # noqa: E402
    ConcernPickResult, format_stale_duration, _no_task_id_msg,
    build_spinoff_name,
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
    # Review-loop state normally set by __init__ (t1159_2): the loop service
    # runs on every _maybe_offer_concerns tick, so every app needs it.
    app._review_loop = mm.review_loop.ReviewLoopController()
    app._loop_banner_text = ""
    app._loop_baseline = None
    app._loop_shadow_hash = None
    app._loop_shadow_hash_streak = 0
    # Post-interaction settle latch + injectable clock (t1509).
    app._loop_shadow_settle_until = None
    app._loop_clock = [1000.0]
    app._loop_now = lambda: app._loop_clock[0]
    app._loop_last_service_at = None
    app._loop_stale_false_pending = False
    app._session = "s"
    app._own_window_name = "agent-x"
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
        app.spy_workers.append((coro, kwargs))
        asyncio.run(coro)

    app.spy_workers: list = []
    app.run_worker = _run_worker


def _draft_path_for(args) -> str:
    """The path the real script would print for this argv's ``--name``."""
    name = args[args.index("--name") + 1]
    return f"aitasks/new/draft_20260813_1042_{name}.md"


def install_create_spy(app, rc=0, out=None, raises=False):
    """Bind the task-creation seam so no bash ever runs (t1159_3).

    Mirrors :func:`_install_rejection_spy`. ``out=None`` synthesizes the
    single stdout line the real ``--silent`` draft path emits, derived from the
    ``--name`` in argv — so path-reporting assertions see realistic, distinct
    paths rather than one canned constant.
    """
    app.spy_created: list = []

    async def _fake_create(args, stdin_text=""):
        app.spy_created.append((list(args), stdin_text))
        if raises:
            raise RuntimeError("create blew up")
        return (rc, _draft_path_for(args) if out is None else out)

    app._run_create_cmd = _fake_create


def _writes(app):
    """Only the MUTATING helper calls — the picker also pre-fetches with `list`.

    Asserting on the raw spy would conflate "wrote nothing" with "never even
    read the store", which is the distinction several of these tests turn on.
    """
    return [c for c in app.spy_rejected if c[0][0] in ("add", "remove")]


def _snap(pane_id="%1", *, content="", awaiting_input=False,
          awaiting_input_kind="", current_command="claude",
          history_size=None, agent_key=None):
    # `agent_key` mirrors what the real classify path stamps on the snapshot
    # (t1467): consumers read it instead of re-deriving from current_command, so
    # a fixture lacking it would exercise a shape that cannot occur in
    # production. Derived from the command by default, overridable for the
    # unresolvable-pane cases.
    resolved = (agent_key if agent_key is not None
                else agent_key_from_command(current_command))
    return SimpleNamespace(
        pane=SimpleNamespace(pane_id=pane_id,
                             current_command=current_command,
                             session_name="s",
                             history_size=history_size,
                             width=100, height=30),
        content=content,
        awaiting_input=awaiting_input,
        awaiting_input_kind=awaiting_input_kind,
        agent_key=resolved,
        scoped=bool(resolved),
    )


def _pick_result(forwarded=(), rejected=(), unrejected=(), spun_off=()):
    return ConcernPickResult(
        forwarded=list(forwarded),
        rejected=list(rejected),
        unrejected=tuple(unrejected),
        spun_off=list(spun_off),
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


# ===========================================================================
# Auto-recheck loop wiring (t1159_2)
# ===========================================================================

import os as _os

sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

import review_loop_fixtures as _rlfx  # noqa: E402
from monitor import review_loop as _rl  # noqa: E402
from monitor.monitor_shared import workflow_phase as _wp  # noqa: E402


class _LoopFakeMon(_FakeMon):
    """Gateway stub for the loop tests: dispatches on the tmux verb.

    ``list-panes`` serves the shadow lookup; ``capture-pane`` serves the raw
    readiness tail (a per-call queue whose last value sticks, so a test can
    change what the FIRE-time fresh capture sees). ``send_keys`` records every
    delivery and pops programmable results (default success). Discovery
    liveness facts are settable sets.
    """

    def __init__(self, async_list="", raw_tail="", list_rc=0, capture_rc=0):
        super().__init__(async_list=async_list)
        self.raw_tails = [raw_tail]
        self.list_rc = list_rc
        self.capture_rc = capture_rc
        self.sent: list = []
        self.send_results: list = []
        self.on_capture = None
        self.discovered: set = set()
        self.enumerated: set = set()

    async def tmux_run_async(self, args, timeout=5.0):
        self.async_calls.append(args)
        await asyncio.sleep(0)  # a real await, so gather() interleaves here
        if args[0] == "list-panes":
            return (self.list_rc, self._async_list)
        if args[0] == "capture-pane":
            if self.on_capture is not None:
                self.on_capture()
            tail = (self.raw_tails.pop(0) if len(self.raw_tails) > 1
                    else self.raw_tails[0])
            return (self.capture_rc, tail)
        return (0, "")

    def send_keys(self, pane_id, keys, literal=False):
        self.sent.append((pane_id, keys, literal))
        return self.send_results.pop(0) if self.send_results else True

    def last_discovered_agents(self):
        return self.discovered

    def last_enumerated_sessions(self):
        return self.enumerated


_SHADOW_LIST_CLAUDE = "%5\t%1\tclaude\t4242\n%6\t\tzsh\t7\n"
_SHADOW_LIST_CODEX = "%5\t%1\tcodex\t4243\n"
# The agent that still has NO readiness detector after t1509 — it is what
# keeps the arm-time refusal reachable now that Codex is supported.
_SHADOW_LIST_OPENCODE = "%5\t%1\topencode\t4244\n"
# The measured wrapper shape: Codex reports `node`, so only the pid-driven
# second rung can resolve it (t1509).
_SHADOW_LIST_NODE = "%5\t%1\tnode\t4245\n"
_SHADOW_LIST_NONE = "%6\t\tzsh\n"


def _loop_app(test, *, async_list=_SHADOW_LIST_CLAUDE,
              raw_tail=None, tick_text=_ROUND1_BLOCK, stale=True,
              awaiting=True, capture_rc=0, list_rc=0):
    """An app whose followed agent satisfies the trigger by default."""
    mon = _LoopFakeMon(
        async_list=async_list,
        raw_tail=raw_tail if raw_tail is not None else _rlfx.CLAUDE_AT_REST_RAW,
        list_rc=list_rc, capture_rc=capture_rc)
    app = _mk_app(monitor=mon)
    snap = _snap("%1", content="agent output", awaiting_input=awaiting)
    app._find_own_agent_snapshot = lambda: snap
    app._shadow_read_recency = mm.ReadRecency(stale, 100.0)
    _stub_capture(test, _async_return(tick_text))
    return app, mon, snap


def _tick(app, n=1):
    for _ in range(n):
        app._loop_last_service_at = None  # each call = its own refresh tick
        asyncio.run(app._maybe_offer_concerns())


def _advance_past_settle(app):
    """Move the injected loop clock past the post-interaction settle deadline
    (t1509). Explicit rather than folded into `_tick` so that every test which
    depends on the hold expiring says so."""
    app._loop_clock[0] += _rl.SHADOW_SETTLE_SECONDS + 0.1


class ShadowInfoLookupTests(unittest.TestCase):
    def test_three_field_format_resolves_pane_and_command(self):
        self.assertEqual(
            mc.match_shadow_pane_info(_SHADOW_LIST_CLAUDE, "%1"),
            ("%5", "claude", 4242))
        self.assertEqual(mc.match_shadow_pane(_SHADOW_LIST_CLAUDE, "%1"), "%5")

    def test_two_field_backcompat_resolves_with_empty_command(self):
        self.assertEqual(mc.match_shadow_pane_info("%5\t%1\n", "%1"),
                         ("%5", "", 0))
        self.assertEqual(mc.match_shadow_pane("%5\t%1\n", "%1"), "%5")

    def test_newest_wins_carries_its_own_command(self):
        out = "%5\t%1\tcodex\n%9\t%1\tclaude\n"
        self.assertEqual(mc.match_shadow_pane_info(out, "%1"),
                         ("%9", "claude", 0))

    def test_status_paths(self):
        async def run(mon):
            return await mc.find_shadow_pane_info_async(mon, "%1")
        self.assertEqual(asyncio.run(run(None)), (False, None, "", 0))
        self.assertEqual(
            asyncio.run(run(_LoopFakeMon(async_list="x", list_rc=1))),
            (False, None, "", 0))
        self.assertEqual(
            asyncio.run(run(_LoopFakeMon(async_list=_SHADOW_LIST_NONE))),
            (True, None, "", 0))
        self.assertEqual(
            asyncio.run(run(_LoopFakeMon(async_list=_SHADOW_LIST_CLAUDE))),
            (True, "%5", "claude", 4242))


class ShadowSeamArityTests(unittest.TestCase):
    """Every consumer that DESTRUCTURES a shadow-seam result, in one place.

    `match_shadow_pane_info` and `find_shadow_pane_info_async` return tuples
    that several callers unpack positionally, so widening either one is a
    silent-at-import, loud-at-runtime change: a missed site raises inside a
    live minimonitor tick rather than failing a test. This class exercises
    each unpack path — the pure indexers, both async wrappers, the sync
    fail-open pair, and the two `minimonitor_app` call sites — so that a
    widening either updates every consumer or fails here.

    Written and confirmed green against the PRE-widening helpers (t1509
    pre-phase), so it is a genuine characterization baseline rather than a
    shape the widening authored.
    """

    def test_pure_indexers_unpack(self):
        # match_shadow_pane_info -> direct consumer
        info = mc.match_shadow_pane_info(_SHADOW_LIST_CLAUDE, "%1")
        self.assertEqual(info[0], "%5")
        self.assertEqual(info[1], "claude")
        # match_shadow_pane -> indexes [0] of the same result
        self.assertEqual(mc.match_shadow_pane(_SHADOW_LIST_CLAUDE, "%1"), "%5")

    def test_sync_lookup_pair_unpacks(self):
        mon = _FakeMon(sync_list=_SHADOW_LIST_CLAUDE)
        ok, pane = mc.find_shadow_pane_status(mon, "%1")
        self.assertTrue(ok)
        self.assertEqual(pane, "%5")
        # find_shadow_pane collapses the same pair fail-open.
        self.assertEqual(mc.find_shadow_pane(mon, "%1"), "%5")

    def test_async_wrapper_unpacks_the_info_tuple(self):
        mon = _LoopFakeMon(async_list=_SHADOW_LIST_CLAUDE)
        # find_shadow_pane_async destructures find_shadow_pane_info_async.
        self.assertEqual(
            asyncio.run(mc.find_shadow_pane_async(mon, "%1")), "%5")

    def test_app_arm_site_unpacks(self):
        """minimonitor_app's arm gate destructures the async info tuple."""
        app, _mon, _snap_ = _loop_app(self)
        asyncio.run(app.action_toggle_review_loop())
        self.assertTrue(app._review_loop.armed)

    def test_app_mid_loop_site_unpacks(self):
        """The armed service tick destructures it again, every tick."""
        app, _mon, _snap_ = _loop_app(self)
        asyncio.run(app.action_toggle_review_loop())
        self.assertTrue(app._review_loop.armed)
        _tick(app)          # must not raise
        self.assertTrue(app._review_loop.armed)


class ReviewLoopArmTests(unittest.TestCase):
    def test_refuses_without_followed_agent(self):
        app, mon, _ = _loop_app(self)
        app._find_own_agent_snapshot = lambda: None
        asyncio.run(app.action_toggle_review_loop())
        self.assertIn("no followed agent", app.spy_notify[-1][0])
        self.assertFalse(app._review_loop.armed)

    def test_refuses_followed_agent_the_loop_does_not_support(self):
        """Retargeted in t1467. OpenCode now HAS prompt detection, so the
        refusal reason changed: the recheck loop INJECTS into the shadow pane,
        so it stays Claude-only until each agent's boundary strategy has its own
        live evidence. The invariant — a non-Claude followed pane cannot arm the
        loop, and the message names it — is unchanged.
        """
        for command in ("opencode", "codex"):
            app, mon, _ = _loop_app(self)
            snap = _snap("%1", current_command=command)
            app._find_own_agent_snapshot = lambda: snap
            asyncio.run(app.action_toggle_review_loop())
            self.assertIn("Claude-only", app.spy_notify[-1][0], command)
            self.assertIn(command, app.spy_notify[-1][0], command)
            self.assertFalse(app._review_loop.armed, command)

    def test_refuses_unresolvable_followed_pane(self):
        """The measured `node` case: a Codex pane whose command resolves to no
        agent at all must be refused too, and named by what tmux reports."""
        app, mon, _ = _loop_app(self)
        snap = _snap("%1", current_command="node")
        app._find_own_agent_snapshot = lambda: snap
        asyncio.run(app.action_toggle_review_loop())
        self.assertIn("node", app.spy_notify[-1][0])
        self.assertFalse(app._review_loop.armed)

    def test_refuses_shadow_agent_without_detector_naming_it(self):
        # Retargeted in t1509 to `opencode`: Codex now HAS a detector, so it no
        # longer reaches this branch. The refusal must stay REACHABLE and must
        # still name the agent — losing its only subject would silently delete
        # the guard rather than the need for it.
        app, mon, _ = _loop_app(self, async_list=_SHADOW_LIST_OPENCODE)
        asyncio.run(app.action_toggle_review_loop())
        self.assertIn("opencode", app.spy_notify[-1][0])
        self.assertIn("no readiness detection", app.spy_notify[-1][0])
        self.assertFalse(app._review_loop.armed)

    def test_codex_shadow_of_a_claude_pane_now_arms(self):
        """The pairing t1509 exists to unblock (t1493/t1498 live evidence)."""
        app, mon, _ = _loop_app(self, async_list=_SHADOW_LIST_CODEX)
        asyncio.run(app.action_toggle_review_loop())
        self.assertTrue(app._review_loop.armed)

    def test_codex_shadow_reporting_node_resolves_via_the_pid_rung(self):
        """The ACTUAL blocker: Codex installs as a node wrapper, so rung 1
        answers "" and only the pid-driven second rung reaches `codex`. Without
        the pid in the seam this arm is refused no matter what detectors exist.
        """
        app, mon, _ = _loop_app(self, async_list=_SHADOW_LIST_NODE)
        seen = {}

        async def _resolve(command, pid, pane_id):
            seen.update(command=command, pid=pid, pane_id=pane_id)
            return "codex" if command == "node" and pid == 4245 else ""

        app._resolve_shadow_agent_key = _resolve
        asyncio.run(app.action_toggle_review_loop())
        self.assertEqual(seen, {"command": "node", "pid": 4245,
                                "pane_id": "%5"})
        self.assertTrue(app._review_loop.armed)

    def test_unresolvable_shadow_refuses_without_claiming_no_detector(self):
        """"" is "could not resolve", never "unsupported" (agent_keys
        contract), and it is frequently a TIMING answer. The message must not
        accuse the agent of lacking a detector."""
        app, mon, _ = _loop_app(self, async_list=_SHADOW_LIST_NODE)

        async def _resolve(command, pid, pane_id):
            return ""

        app._resolve_shadow_agent_key = _resolve
        asyncio.run(app.action_toggle_review_loop())
        self.assertIn("could not resolve", app.spy_notify[-1][0])
        self.assertNotIn("no readiness detection", app.spy_notify[-1][0])
        self.assertFalse(app._review_loop.armed)

    def test_refuses_on_lookup_failure_without_arming(self):
        app, mon, _ = _loop_app(self, list_rc=1)
        asyncio.run(app.action_toggle_review_loop())
        self.assertIn("could not query", app.spy_notify[-1][0])
        self.assertFalse(app._review_loop.armed)

    def test_refuses_without_shadow_suggesting_e(self):
        app, mon, _ = _loop_app(self, async_list=_SHADOW_LIST_NONE)
        asyncio.run(app.action_toggle_review_loop())
        self.assertIn("press 'e'", app.spy_notify[-1][0])
        self.assertFalse(app._review_loop.armed)

    def test_arm_seeds_baseline_and_banner_and_latch(self):
        app, mon, snap = _loop_app(self, stale=False)
        asyncio.run(app.action_toggle_review_loop())
        self.assertTrue(app._review_loop.armed)
        self.assertEqual(app._loop_baseline,
                         (snap.content, snap.awaiting_input_kind,
                          "%1", None, (100, 30)))
        self.assertIn("ARMED", app._loop_banner_text)
        # Fresh arm (stale False at arm): latch closed (hardening 6/9).
        self.assertFalse(app._review_loop.work_seen)
        # Toggle again disarms and clears the banner.
        asyncio.run(app.action_toggle_review_loop())
        self.assertFalse(app._review_loop.armed)
        self.assertEqual(app._loop_banner_text, "")

    def test_arm_into_pending_staleness_opens_the_latch(self):
        app, mon, _ = _loop_app(self, stale=True)
        asyncio.run(app.action_toggle_review_loop())
        self.assertTrue(app._review_loop.work_seen)


class ShadowAgentResolutionGenerationTests(unittest.TestCase):
    """The agent-key lookup is now an await (t1509), so it is a suspension
    point and needs the same generation guard the capture already had.

    Both tests resolve the key by calling back into the controller mid-await,
    simulating a disarm/re-arm that lands while the lookup is in flight.
    """

    def test_mid_loop_abandons_a_superseded_lifecycle(self):
        app, mon, snap = _loop_app(self)
        app._review_loop.arm(pending_work=True)
        app._loop_baseline = (snap.content, snap.awaiting_input_kind,
                              "%1", None, (100, 30))
        mon._async_list = _SHADOW_LIST_OPENCODE   # unsupported => would disarm

        async def _resolve(command, pid, pane_id):
            # A re-arm lands while we are off-loop: NEW lifecycle.
            app._review_loop.arm(pending_work=False)
            return "opencode"

        app._resolve_shadow_agent_key = _resolve
        _tick(app, 1)
        # The disarm decided on the OLD lifecycle's evidence must not fire.
        self.assertTrue(app._review_loop.armed)
        self.assertFalse(any("disarmed" in m for m, _s in app.spy_notify))

    def test_arm_abandons_when_the_lifecycle_moved_during_the_lookup(self):
        app, mon, _ = _loop_app(self, async_list=_SHADOW_LIST_CODEX)

        async def _resolve(command, pid, pane_id):
            app._review_loop.arm(pending_work=False)   # someone else armed
            return "codex"

        app._resolve_shadow_agent_key = _resolve
        before = len(app.spy_notify)
        asyncio.run(app.action_toggle_review_loop())
        # It must NOT re-arm on top of the other lifecycle, nor announce one.
        self.assertEqual(len(app.spy_notify), before)


class ShadowSettleLatchTests(unittest.TestCase):
    """Post-interaction settle latch (t1509).

    Driven through the injected `_loop_now` clock — no sleeps, so the cadence
    assertions are deterministic rather than timing-dependent.
    """

    def _app(self):
        app, mon, _ = _loop_app(self)
        self.clock = [1000.0]
        app._loop_now = lambda: self.clock[0]
        return app

    def _advance(self, seconds):
        self.clock[0] += seconds

    def _latch(self, app, state, ready=True):
        return app._apply_shadow_settle_latch(state, ready)

    def test_ready_passes_through_when_no_interaction_was_seen(self):
        app = self._app()
        self.assertIs(self._latch(app, mm.review_loop.SHADOW_READY), True)

    def test_working_clears_the_latch_early(self):
        app = self._app()
        self._latch(app, mm.review_loop.SHADOW_DIALOG)
        self.assertIs(self._latch(app, mm.review_loop.SHADOW_WORKING), True)
        # Cleared: the very next ready tick is allowed, deadline or not.
        self.assertIs(self._latch(app, mm.review_loop.SHADOW_READY), True)

    def test_a_dialog_holds_ready_until_the_deadline_passes(self):
        app = self._app()
        self._latch(app, mm.review_loop.SHADOW_DIALOG)
        self._advance(mm.review_loop.SHADOW_SETTLE_SECONDS - 0.1)
        self.assertIs(self._latch(app, mm.review_loop.SHADOW_READY), False)
        self._advance(0.2)
        self.assertIs(self._latch(app, mm.review_loop.SHADOW_READY), True)

    def test_the_unpatterned_update_prompt_arms_the_latch_too(self):
        """End-to-end for the interaction NO prompt pattern matches. A latch
        armed from a pattern match would never arm here, and the whole window
        would reopen for it — so this drives the real fixture through the real
        classifier, not a hand-passed state string."""
        app = self._app()
        state = mm.review_loop.shadow_state(
            _rlfx.CODEX_UPDATE_PROMPT_RAW, "codex")
        self.assertEqual(state, mm.review_loop.SHADOW_DIALOG)
        self._latch(app, state)
        self._advance(mm.review_loop.SHADOW_SETTLE_SECONDS - 0.1)
        self.assertIs(self._latch(app, mm.review_loop.SHADOW_READY), False)
        self._advance(0.2)
        self.assertIs(self._latch(app, mm.review_loop.SHADOW_READY), True)

    def test_it_never_wedges_when_no_work_ever_follows(self):
        """The measured pathological case: after the update prompt no WORKING
        observation EVER arrives (15s / 56 identical captures, live). A latch
        clearable only by WORKING would hold the loop forever; the deadline is
        the escape hatch and must always expire."""
        app = self._app()
        self._latch(app, mm.review_loop.SHADOW_DIALOG)
        released = None
        for i in range(40):                      # 40 ready ticks, no WORKING
            if self._latch(app, mm.review_loop.SHADOW_READY) is True:
                released = i
                break
            self._advance(0.25)
        self.assertIsNotNone(released, "latch never released without WORKING")

    def test_busy_and_unknown_arm_the_latch_as_well(self):
        """The predicate is "not READY and not WORKING", not "is a dialog":
        typed text in the shadow's composer would be concatenated by an
        injection, and an unreadable capture is not evidence of idleness."""
        for state in (mm.review_loop.SHADOW_BUSY,
                      mm.review_loop.SHADOW_UNKNOWN):
            app = self._app()
            self._latch(app, state)
            self.assertIs(
                self._latch(app, mm.review_loop.SHADOW_READY), False, state)

    def test_release_depends_on_ELAPSED_TIME_not_on_tick_count(self):
        """Concern B, executable — and stated as the property that actually
        discriminates. The committed-evidence cadence is
        `max(1.0, 0.5 * refresh_seconds)` with `refresh_seconds` configurable
        from `--interval` and project_config.yaml, so it floors at 1.0s rather
        than the 1.5s default. Merely comparing two cadences does NOT
        discriminate: a tick-counted R=2 sized for 1.5s happens to satisfy the
        deadline at 1.0s too. What separates the implementations is whether the
        release is a function of elapsed time or of how many ready
        OBSERVATIONS arrived.
        """
        # (a) ONE ready observation, long after the deadline, releases.
        #     A tick-counted R>1 returns False here.
        app = self._app()
        self._latch(app, mm.review_loop.SHADOW_DIALOG)
        self._advance(mm.review_loop.SHADOW_SETTLE_SECONDS + 5.0)
        self.assertIs(self._latch(app, mm.review_loop.SHADOW_READY), True)

        # (b) MANY ready observations inside the window release nothing.
        #     A tick-counted R=2 releases on the second one.
        app = self._app()
        self._latch(app, mm.review_loop.SHADOW_DIALOG)
        for _ in range(10):
            self._advance(0.05)          # 0.5s total, well inside the window
            self.assertIs(
                self._latch(app, mm.review_loop.SHADOW_READY), False)

    def test_the_deadline_is_never_early_at_any_configured_cadence(self):
        """The safety half, at both the default cadence and the 1.0s floor."""
        for refresh in (3, 1):
            cadence = max(1.0, 0.5 * refresh)
            app = self._app()
            app._refresh_seconds = refresh
            t0 = self.clock[0]
            self._latch(app, mm.review_loop.SHADOW_DIALOG)
            ticks = 0
            while True:
                self._advance(cadence)
                ticks += 1
                if self._latch(app, mm.review_loop.SHADOW_READY) is True:
                    break
                self.assertLess(ticks, 50, "latch never released")
            held = self.clock[0] - t0
            self.assertGreaterEqual(
                held, mm.review_loop.SHADOW_SETTLE_SECONDS,
                f"released early at refresh={refresh}")
            # ...and not absurdly late: within one evidence tick of the
            # deadline, which is the best any sampled release can do.
            self.assertLess(
                held, mm.review_loop.SHADOW_SETTLE_SECONDS + cadence)

    def test_arming_and_auto_disarm_clear_a_standing_deadline(self):
        app = self._app()
        self._latch(app, mm.review_loop.SHADOW_DIALOG)
        self.assertIsNotNone(app._loop_shadow_settle_until)
        app._loop_auto_disarm("test")
        self.assertIsNone(app._loop_shadow_settle_until)


class ReviewLoopFireTests(unittest.TestCase):
    def _armed(self, **kwargs):
        app, mon, snap = _loop_app(self, **kwargs)
        app._review_loop.arm(pending_work=True)
        app._loop_baseline = (snap.content, snap.awaiting_input_kind,
                              "%1", None, (100, 30))
        return app, mon, snap

    def test_fire_sends_exactly_two_keys_to_the_shadow_only(self):
        app, mon, _ = self._armed()
        _tick(app, 3)
        self.assertEqual(len(mon.sent), 2, mon.sent)
        (pane1, prompt, literal1), (pane2, key2, literal2) = mon.sent
        self.assertEqual(pane1, "%5")
        self.assertEqual(pane2, "%5")
        self.assertTrue(literal1)
        self.assertEqual((key2, literal2), ("Enter", False))
        # The followed pane appears in NO send call (safety contract 1).
        self.assertNotIn("%1", [p for p, _k, _l in mon.sent])
        # The prompt leads with the t1493 routing trigger and carries the
        # machine-derived round (previous block was round 1).
        self.assertTrue(prompt.startswith("refetch and recheck round 2"))
        self.assertNotIn("\n", prompt)
        self.assertIn("recheck #1 sent", app._loop_banner_text)
        self.assertEqual(app._review_loop.state, _rl.FIRED)

    def test_round_is_omitted_when_the_block_has_no_meta(self):
        app, mon, _ = self._armed(tick_text=_CLOSED_BLOCK)
        _tick(app, 3)
        self.assertTrue(mon.sent)
        self.assertNotIn("round", mon.sent[0][1].split(":")[0])

    def test_advisory_negative_control_any_phase_fires(self):
        # Force every phase value — including a WRONG one and UNKNOWN —
        # through the fire path: it must fire in every case, nothing refused.
        # A loop that gates on phase must fail this (t1311/t1420 contract).
        for phase in (*_wp.PHASES, "garbage"):
            app, mon, snap = self._armed()
            app._task_cache = SimpleNamespace(
                get_task_id_for_pane=lambda pane: "42",
                get_task_info=lambda tid, sess: SimpleNamespace())
            app._phase_for_snap = (
                lambda s, i, _p=phase: SimpleNamespace(phase=_p))
            _tick(app, 3)
            self.assertEqual(len(mon.sent), 2, phase)

    def test_prompt_write_failure_sends_no_enter_and_disarms(self):
        app, mon, _ = self._armed()
        mon.send_results = [False]
        _tick(app, 3)
        self.assertEqual(len(mon.sent), 1, mon.sent)  # Enter NEVER sent
        self.assertFalse(app._review_loop.armed)
        self.assertEqual(app._loop_banner_text, "")
        self.assertTrue(any("disarmed" in m for m, _s in app.spy_notify))

    def test_enter_failure_names_the_leftover_text_and_disarms(self):
        app, mon, _ = self._armed()
        mon.send_results = [True, False]
        _tick(app, 3)
        self.assertEqual(len(mon.sent), 2)
        self.assertFalse(app._review_loop.armed)
        self.assertTrue(any("left in the shadow composer" in m
                            for m, _s in app.spy_notify), app.spy_notify)

    def test_presend_revalidation_refuses_a_changed_shadow(self):
        app, mon, _ = self._armed()
        # Service captures see the at-rest tail; the FIRE-time fresh capture
        # sees typed composer text (the queue's last value sticks afterwards).
        rest = _rlfx.CLAUDE_AT_REST_RAW
        mon.raw_tails = [rest, rest, rest, _rlfx.CLAUDE_TYPED_RAW, rest]
        _tick(app, 3)
        self.assertEqual(mon.sent, [])  # zero sends — no partial delivery
        self.assertTrue(app._review_loop.armed)
        self.assertEqual(app._review_loop.state, _rl.WAITING)
        # t1509: the delivery-time observation (typed composer text) now ARMS
        # the settle latch, so the aborted episode no longer completes on the
        # very next tick — it waits out the settle window first. Injecting
        # straight after seeing text in the shadow's composer would concatenate
        # onto what the user typed.
        _tick(app, 1)
        self.assertEqual(mon.sent, [])
        _advance_past_settle(app)
        _tick(app, 1)
        self.assertEqual(len(mon.sent), 2)

    def test_a_dialog_seen_only_at_delivery_arms_the_settle_latch(self):
        """The between-tick interaction race (t1509 review).

        The service tick sees an at-rest shadow and the controller grants a
        fire; by the time the pre-send capture runs, an interaction is on
        screen. Refusing the send is not enough on its own: before this fix the
        refusing observation was discarded, so the episode completed on the
        NEXT clean tick — ~one evidence tick after a dialog was seen, with no
        settle hold at all. The delivery capture must feed the latch.
        """
        app, mon, _ = self._armed()
        rest = _rlfx.CLAUDE_AT_REST_RAW
        mon.raw_tails = [rest, rest, rest, _rlfx.CLAUDE_DIALOG_RAW, rest]
        _tick(app, 3)
        self.assertEqual(mon.sent, [])                       # refused
        self.assertTrue(app._review_loop.armed)              # not disarmed
        # The refusing observation ARMED the latch...
        self.assertIsNotNone(app._loop_shadow_settle_until)
        # ...so the next clean tick must NOT complete the episode.
        _tick(app, 1)
        self.assertEqual(mon.sent, [], "fired inside the settle window")
        _tick(app, 1)
        self.assertEqual(mon.sent, [], "fired inside the settle window")
        # Only after the wall-clock deadline does it deliver.
        _advance_past_settle(app)
        _tick(app, 1)
        self.assertEqual(len(mon.sent), 2)

    def test_shadow_busy_holds_with_banner(self):
        app, mon, _ = self._armed(raw_tail=_rlfx.CLAUDE_TYPED_RAW)
        _tick(app, 4)
        self.assertEqual(mon.sent, [])
        self.assertTrue(app._review_loop.armed)
        self.assertIn("waiting for shadow to settle", app._loop_banner_text)

    def test_overlapping_ticks_deliver_exactly_once(self):
        app, mon, _ = self._armed()
        _tick(app, 2)  # streak at 2; the next tick fires

        async def overlap():
            await asyncio.gather(app._maybe_offer_concerns(),
                                 app._maybe_offer_concerns())
        app._loop_last_service_at = None
        asyncio.run(overlap())
        self.assertEqual(len(mon.sent), 2, mon.sent)  # ONE delivery

    def test_overlapping_services_count_as_one_evidence_tick(self):
        # Review round 2 reproduction: one ordinary refresh followed by TWO
        # overlapping services must NOT complete the 3-tick debounce — the
        # concurrent invocations collapse to one committed evidence tick.
        app, mon, _ = self._armed()
        _tick(app, 1)

        async def overlap():
            await asyncio.gather(app._maybe_offer_concerns(),
                                 app._maybe_offer_concerns())
        app._loop_last_service_at = None
        asyncio.run(overlap())
        self.assertEqual(mon.sent, [])
        self.assertEqual(app._review_loop.state, mm.review_loop.WAITING)
        # Positive control: one more genuine tick completes the debounce.
        _tick(app, 1)
        self.assertEqual(len(mon.sent), 2)

    def test_disarm_during_fire_capture_sends_nothing(self):
        app, mon, snap = self._armed()
        ctrl = app._review_loop
        _tick(app, 2)
        # Reserve the delivery at controller level, then have the fire-time
        # capture race a disarm: the token re-check must yield zero sends.
        action = ctrl.tick(
            agent_present=True, shadow_present=True, awaiting_input=True,
            stale=True, work_signal=_rl.NO_CHANGE, shadow_ready=True,
            modal_open=False, now=10_000.0)
        self.assertEqual(action, _rl.ACTION_FIRE)
        token = ctrl.delivery_token
        mon.on_capture = ctrl.disarm
        outcome, _detail = asyncio.run(app._fire_shadow_recheck(
            "%5", snap, "claude", _rlfx.CLAUDE_AT_REST_RAW,
            _ROUND1_BLOCK, token))
        self.assertEqual(outcome, "not_ready")
        self.assertEqual(mon.sent, [])


class ReviewLoopPresenceTests(unittest.TestCase):
    def _armed(self, **kwargs):
        app, mon, snap = _loop_app(self, **kwargs)
        app._review_loop.arm(pending_work=True)
        return app, mon, snap

    def test_lookup_failure_keeps_the_loop_armed(self):
        app, mon, _ = self._armed()
        mon.list_rc = 1  # transient tmux failure on the shadow lookup
        _tick(app, 3)
        self.assertTrue(app._review_loop.armed)
        self.assertFalse(any("disarmed" in m for m, _s in app.spy_notify))

    def test_verified_shadow_absence_disarms_visibly(self):
        app, mon, _ = self._armed()
        mon._async_list = _SHADOW_LIST_NONE  # verified: no shadow bound
        _tick(app, 1)
        self.assertFalse(app._review_loop.armed)
        self.assertTrue(any("disarmed" in m for m, _s in app.spy_notify))

    def test_mid_loop_swap_to_undetectable_shadow_disarms_naming_it(self):
        # Retargeted to `opencode` in t1509 (see the arm-side test): a RESOLVED
        # agent with no detector is a definitive capability gap and still
        # auto-disarms.
        app, mon, _ = self._armed()
        mon._async_list = _SHADOW_LIST_OPENCODE
        _tick(app, 1)
        self.assertFalse(app._review_loop.armed)
        self.assertTrue(any("opencode" in m for m, _s in app.spy_notify))

    def test_mid_loop_swap_to_a_codex_shadow_keeps_the_loop_armed(self):
        app, mon, _ = self._armed()
        mon._async_list = _SHADOW_LIST_CODEX
        _tick(app, 1)
        self.assertTrue(app._review_loop.armed)

    def test_mid_loop_unresolvable_shadow_holds_instead_of_disarming(self):
        """"" is a TIMING answer as often as a permanent one (the wrapper
        spawns its child asynchronously and misses are retried on a backoff).
        Disarming on it would destroy the user's armed state over a
        process-table race, so the loop HOLDS, exactly as for a transient tmux
        failure."""
        app, mon, _ = self._armed()
        mon._async_list = _SHADOW_LIST_NODE

        async def _resolve(command, pid, pane_id):
            return ""

        app._resolve_shadow_agent_key = _resolve
        _tick(app, 3)
        self.assertTrue(app._review_loop.armed)
        self.assertFalse(any("disarmed" in m for m, _s in app.spy_notify))

    def test_agent_capture_failure_pauses_and_preserves_baseline(self):
        app, mon, snap = self._armed(stale=True)
        app._review_loop.work_seen = False  # make the latch observable
        base_content = "prompt A content"
        app._loop_baseline = (base_content, "", "%1", None, (100, 30))
        # Capture-failure tick: no snapshot, but discovery still lists the
        # agent — the loop pauses and the baseline survives (hardening 8).
        mon.discovered = {("s", "agent-x")}
        app._find_own_agent_snapshot = lambda: None
        _tick(app, 1)
        self.assertTrue(app._review_loop.armed)
        self.assertEqual(app._loop_baseline[0], base_content)
        # The response produced during the gap classifies as WORK against
        # the pre-gap baseline (content changed while not at a prompt).
        snap2 = _snap("%1", content="revised output", awaiting_input=False)
        app._find_own_agent_snapshot = lambda: snap2
        _tick(app, 1)
        self.assertTrue(app._review_loop.work_seen)

    def test_throttled_invocation_never_consumes_a_work_observation(self):
        # Review round 3 reproduction: the OVERLAPPING (throttled) invocation
        # is the first to contain the new output. It must not advance the
        # baseline — the next committed tick must still classify the work.
        app, mon, snap = self._armed(stale=True)
        app._review_loop.work_seen = False  # make the latch observable
        _tick(app, 1)  # committed tick: baseline = snap.content
        # New output lands; this invocation is throttled (stamp just set).
        snap2 = _snap("%1", content="revised output", awaiting_input=False)
        app._find_own_agent_snapshot = lambda: snap2
        asyncio.run(app._maybe_offer_concerns())  # NO stamp reset: throttled
        self.assertFalse(app._review_loop.work_seen)
        self.assertNotEqual(app._loop_baseline[0], "revised output")
        # The next committed tick sees the same output and classifies WORK.
        _tick(app, 1)
        self.assertTrue(app._review_loop.work_seen)

    def test_verified_agent_departure_disarms(self):
        app, mon, _ = self._armed()
        mon.discovered = set()
        mon.enumerated = {"s"}  # session seen; agent verifiably gone
        app._find_own_agent_snapshot = lambda: None
        _tick(app, 1)
        self.assertFalse(app._review_loop.armed)

    def test_recency_writer_latches_a_false_verdict(self):
        # Prove the WRITER (review round 4): a False verdict recorded by
        # _update_shadow_freshness must set the sticky pending flag.
        app, mon, _ = self._armed()

        async def get_pane_option(pane_id, option, timeout=2.0):
            return (True, "1000")  # shadow stamp: epoch 1000

        mon.get_pane_option = get_pane_option
        mon.get_last_change_wall = lambda pane_id: 900.0  # older change
        app._refresh_seconds = 3
        asyncio.run(app._update_shadow_freshness("%5", "%1"))
        self.assertIs(app._shadow_feedback_stale, False)
        self.assertTrue(app._loop_stale_false_pending)

    def test_missed_false_edge_still_rearms_a_fired_controller(self):
        # Review round 4 reproduction: the ONLY stale=False lands in a
        # throttled window and the cache is True again by the next committed
        # tick — the pending flag must deliver the edge so FIRED re-arms.
        app, mon, _ = self._armed()
        _tick(app, 3)  # fire
        self.assertEqual(app._review_loop.state, mm.review_loop.FIRED)
        # The throttled window recorded False (writer latched it), then the
        # agent moved again: cache back to True before the committed tick.
        app._loop_stale_false_pending = True
        app._shadow_read_recency = mm.ReadRecency(True, 100.0)
        _tick(app, 1)
        self.assertEqual(app._review_loop.state, mm.review_loop.WAITING)
        self.assertFalse(app._loop_stale_false_pending)

    def test_replayed_false_does_not_consume_newer_work(self):
        # Review round 5 reproduction: while FIRED, the shadow reads the
        # PRIOR episode (False latched in a throttled window), the agent then
        # emits NEW output and the verdict is True again by the committed
        # tick. The replayed old False must re-arm WITHOUT consuming the
        # newer episode's work — and the loop must go on to deliver it.
        import time as _time
        app, mon, snap = self._armed()
        _tick(app, 3)  # first delivery
        self.assertEqual(app._review_loop.state, mm.review_loop.FIRED)
        self.assertEqual(len(mon.sent), 2)
        app._loop_stale_false_pending = True
        app._shadow_read_recency = mm.ReadRecency(True, 100.0)
        app._review_loop.fired_at = _time.monotonic() - 60  # cooldown spent
        # The new output lands while the agent is producing (not at a prompt).
        snap2 = _snap("%1", content="brand new output", awaiting_input=False)
        app._find_own_agent_snapshot = lambda: snap2
        _tick(app, 1)
        self.assertEqual(app._review_loop.state, mm.review_loop.WAITING)
        self.assertTrue(app._review_loop.work_seen,
                        "replayed False consumed the newer episode's work")
        # The agent settles at a prompt; the episode completes end to end.
        snap3 = _snap("%1", content="brand new output", awaiting_input=True)
        app._find_own_agent_snapshot = lambda: snap3
        _tick(app, 3)
        self.assertEqual(len(mon.sent), 4, mon.sent)  # second delivery

    def test_indeterminate_presence_preserves_the_pending_edge(self):
        # Review round 6 reproduction: the pending False must survive a
        # capture-failure tick (agent discovered, snapshot missing) — the
        # controller's presence guard returns before observations, so
        # consuming the flag there would lose the only edge and wedge FIRED.
        app, mon, snap = self._armed()
        _tick(app, 3)  # fire
        self.assertEqual(app._review_loop.state, mm.review_loop.FIRED)
        app._loop_stale_false_pending = True
        app._shadow_read_recency = mm.ReadRecency(True, 100.0)
        mon.discovered = {("s", "agent-x")}
        app._find_own_agent_snapshot = lambda: None  # capture failed
        _tick(app, 1)
        self.assertTrue(app._loop_stale_false_pending)  # NOT discarded
        self.assertEqual(app._review_loop.state, mm.review_loop.FIRED)
        # Recovery: the snapshot returns, verdict currently True — the
        # preserved edge is delivered and FIRED re-arms.
        app._find_own_agent_snapshot = lambda: snap
        _tick(app, 1)
        self.assertFalse(app._loop_stale_false_pending)
        self.assertEqual(app._review_loop.state, mm.review_loop.WAITING)

    def test_rearm_during_readiness_await_abandons_old_evidence(self):
        # Review round 7 reproduction: lifecycle A classifies pre-arm output,
        # the user disarms and re-arms (lifecycle B, fresh) while A's
        # readiness capture is in flight — A must abandon, never injecting
        # its WORK into B's latch.
        app, mon, snap = self._armed(stale=True)
        _tick(app, 1)  # baseline committed for lifecycle A
        snap2 = _snap("%1", content="pre-arm output", awaiting_input=False)
        app._find_own_agent_snapshot = lambda: snap2

        def rearm():
            mon.on_capture = None  # only the first capture races
            app._review_loop.disarm()
            app._review_loop.arm(pending_work=False)
            app._loop_baseline = (snap2.content, "", "%1", None, (100, 30))

        mon.on_capture = rearm
        _tick(app, 1)  # lifecycle A's invocation races the re-arm
        self.assertFalse(app._review_loop.work_seen,
                         "pre-arm evidence leaked into the new lifecycle")
        # And the fresh lifecycle cannot fire from selection churn alone.
        _tick(app, 3)
        self.assertEqual(len(mon.sent), 0)

    def test_key_hints_surface_every_binding(self):
        # Executable audit for the recorded show=False exception (review
        # rounds 5+7): minimonitor has no Footer, so EVERY binding — mixin
        # included — must appear in the #mini-key-hints text.
        hints = mm.KEY_HINTS_TEXT
        keys = {b.key for b in mm.MiniMonitorApp.BINDINGS}
        self.assertIn("?", keys)  # the mixin binding is part of the surface
        for key in sorted(keys):
            forms = (f"{key}:", f"{key}/", f"/{key}")
            self.assertTrue(any(f in hints for f in forms),
                            f"binding '{key}' not surfaced in key hints")

    def test_pane_replacement_resets_the_baseline(self):
        app, mon, _ = self._armed()
        app._loop_baseline = ("old", "", "%99", None, (100, 30))
        _tick(app, 1)
        self.assertEqual(app._loop_baseline[2], "%1")


# ---------------------------------------------------------------------------
# Spin-off triage arm (t1159_3)
# ---------------------------------------------------------------------------

def _spin_concerns(*regions):
    """One actionable concern per region, in input order."""
    return [
        Concern("high", region, f"Body for {region}.")
        for region in regions
    ]


def _spin_app(rejected_rc=0, rejected_out="", create_rc=0, create_out=None,
              create_raises=False, task_id="1427_2"):
    app = _mk_app(_FakeMon(async_list="%5\t%1"), task_id=task_id,
                  rejected_rc=rejected_rc, rejected_out=rejected_out)
    install_create_spy(app, rc=create_rc, out=create_out, raises=create_raises)
    return app


def _adds(app):
    """Only the store WRITES, dropping the pre-creation `list` read."""
    return [c for c in app.spy_rejected if c[0][0] == "add"]


class SpinoffCreateTests(unittest.TestCase):
    """The picker's spin-off arm creates drafts and suppresses them (t1159_3)."""

    def test_one_create_per_concern_with_the_pinned_argv(self):
        app = _spin_app()
        concerns = _spin_concerns("monitor_shared.py:2048", "parser")
        app.apply_concern_pick_result(_pick_result(spun_off=concerns), "1427_2")

        self.assertEqual(len(app.spy_created), 2)
        for (args, stdin), concern in zip(app.spy_created, concerns):
            self.assertIn("--batch", args)
            self.assertIn("--silent", args)
            self.assertEqual(args[args.index("--desc-file") + 1], "-")
            self.assertEqual(args[args.index("--followup-of") + 1], "1427_2")
            self.assertEqual(
                args[args.index("--followup-kind") + 1], "review_finding"
            )
            self.assertEqual(args[args.index("--priority") + 1], "high")
            # Drafts only — a --commit would claim an id and need the network.
            self.assertNotIn("--commit", args)
            # The canonical FORWARD rendering, byte for byte: the store match
            # next round and the receiving agent both depend on this exact text.
            self.assertIn(concern_marker_line(concern), stdin)

    def test_a_spinoff_only_result_still_dispatches(self):
        """The pre-t1159_3 early return keyed on rejections alone would have
        swallowed this entirely."""
        app = _spin_app()
        app.apply_concern_pick_result(
            _pick_result(spun_off=_spin_concerns("x")), "1427_2"
        )
        self.assertEqual(len(app.spy_created), 1)

    def test_draft_paths_are_reported_and_never_ids(self):
        app = _spin_app()
        app.apply_concern_pick_result(
            _pick_result(spun_off=_spin_concerns("alpha", "beta")), "1427_2"
        )
        message = "\n".join(m for m, _ in app.spy_notify)
        # Both drafts named individually — a count plus a directory could not
        # identify them in a shared, minute-stamped drop directory.
        self.assertIn("shadow_alpha_", message)
        self.assertIn("shadow_beta_", message)
        self.assertIn("aitasks/new/", message)
        # The batch selector, so the set stays recoverable when the list caps.
        self.assertIn("ls aitasks/new/*", message)
        # Drafts have NO ids until `ait create` finalizes them.
        self.assertNotIn("t1427_2:", message)
        self.assertIn("ait create", message)

    def test_store_add_is_one_batched_call_carrying_every_marker(self):
        app = _spin_app()
        concerns = _spin_concerns("alpha", "beta", "gamma")
        app.apply_concern_pick_result(_pick_result(spun_off=concerns), "1427_2")

        adds = _adds(app)
        self.assertEqual(len(adds), 1, "one mutex acquisition, not N")
        args, stdin = adds[0]
        self.assertEqual(args[:2], ["add", "1427_2"])
        self.assertEqual(args[args.index("--producer") + 1], "spinoff")
        self.assertEqual(
            stdin, "".join(concern_marker_line(c) + "\n" for c in concerns)
        )

    def test_a_failed_create_writes_nothing_to_the_store(self):
        """Suppressing a concern whose draft does not exist would lose it."""
        app = _spin_app(create_rc=1, create_out="ERROR:boom")
        app.apply_concern_pick_result(
            _pick_result(spun_off=_spin_concerns("alpha")), "1427_2"
        )
        self.assertEqual(_adds(app), [])
        self.assertTrue(
            any(sev == "error" for _, sev in app.spy_notify),
            "a failed creation must be visible",
        )

    def test_no_task_id_warns_and_runs_no_subprocess(self):
        app = _spin_app()
        app.apply_concern_pick_result(
            _pick_result(spun_off=_spin_concerns("alpha")), None
        )
        self.assertEqual(app.spy_created, [])
        self.assertEqual(app.spy_rejected, [])
        message, severity = app.spy_notify[0]
        self.assertEqual(severity, "warning")
        self.assertIn("spin-off skipped", message.lower())
        self.assertIn("no task id", message.lower())


class NoTaskIdMessageTests(unittest.TestCase):
    """`_no_task_id_msg` names exactly what was dropped (t1159_3)."""

    def test_rejections_only_keeps_the_pre_t1159_3_wording(self):
        msg = _no_task_id_msg(
            _pick_result(rejected=_spin_concerns("a"))
        )
        self.assertEqual(
            msg, "Rejections not persisted — no task id for this pane"
        )

    def test_spinoff_only(self):
        msg = _no_task_id_msg(
            _pick_result(spun_off=_spin_concerns("a"))
        )
        self.assertEqual(msg, "Spin-off skipped — no task id for this pane")

    def test_both_name_both(self):
        msg = _no_task_id_msg(
            _pick_result(rejected=_spin_concerns("a"),
                         spun_off=_spin_concerns("b"))
        )
        self.assertIn("Rejections not persisted", msg)
        self.assertIn("spin-off skipped", msg)


class SpinoffSerializationTests(unittest.TestCase):
    """Every store-touching effect of one confirmation runs in ONE worker.

    The store's mutex is per-task and NOT producer-scoped, and a LOCK_BUSY
    means nothing was written — which for a spin-off would leave the draft on
    disk unsuppressed. `_persist_concern_dispositions` is already sequential
    for this reason; a second worker would reintroduce the contention.
    """

    def test_a_mixed_confirmation_takes_exactly_one_worker(self):
        app = _spin_app(rejected_out="ADDED:1")
        app.apply_concern_pick_result(
            _pick_result(
                forwarded=_spin_concerns("fwd"),
                rejected=_spin_concerns("rej"),
                spun_off=_spin_concerns("spin"),
            ),
            "1427_2",
        )
        # The harness runs each worker coroutine to completion synchronously,
        # so wall-clock overlap can never be observed here. The COUNT is the
        # guard: two workers would be two chances to contend.
        self.assertEqual(len(app.spy_workers), 1)

    def test_store_writes_are_strictly_ordered_within_that_worker(self):
        app = _spin_app(rejected_out="ADDED:1")
        app.apply_concern_pick_result(
            _pick_result(
                rejected=_spin_concerns("rej"),
                spun_off=_spin_concerns("spin"),
            ),
            "1427_2",
        )
        producers = [
            args[args.index("--producer") + 1]
            for args, _ in _adds(app) if "--producer" in args
        ]
        self.assertEqual(producers, ["picker", "spinoff"])


class SpinoffPartialFailureTests(unittest.TestCase):
    """Created-but-unsuppressed is its own reported state (t1159_3)."""

    def _drive(self, rejected_rc, rejected_out):
        app = _spin_app(rejected_rc=rejected_rc, rejected_out=rejected_out)
        app.apply_concern_pick_result(
            _pick_result(spun_off=_spin_concerns("alpha")), "1427_2"
        )
        return app

    def test_lock_busy_after_creation_says_not_suppressed_and_lists_paths(self):
        app = self._drive(3, "LOCK_BUSY")
        message, severity = app.spy_notify[-1]
        self.assertEqual(severity, "warning")
        self.assertIn("NOT suppressed", message)
        self.assertIn("duplicate", message.lower())
        # The user still needs to know WHICH drafts exist.
        self.assertIn("shadow_alpha_", message)

    def test_the_reason_comes_from_the_shared_outcome_vocabulary(self):
        """Not hardcoded to LOCK_BUSY: a structurally unusable store (4) must
        report its own distinct reason."""
        app = self._drive(4, "store unusable")
        message, _ = app.spy_notify[-1]
        self.assertIn("NOT suppressed", message)
        self.assertIn("unusable", message.lower())

    def test_a_clean_store_write_claims_success_instead(self):
        app = self._drive(0, "ADDED:1")
        message, severity = app.spy_notify[-1]
        self.assertEqual(severity, "information")
        self.assertIn("parked as drafts", message)
        self.assertNotIn("NOT suppressed", message)


class SpinoffAlreadyParkedTests(unittest.TestCase):
    """The store closes the window the in-flight guard cannot reach.

    The picker lists concerns unfiltered and t1427's suppression only lands
    producer-side at the NEXT shadow round, so re-confirming an unchanged block
    would otherwise spin the same concern off a second time.
    """

    def _app_with_store(self, entries):
        app = _spin_app()

        async def _fake_rejected(args, stdin_text=""):
            app.spy_rejected.append((list(args), stdin_text))
            if args[0] == "list":
                return (0, "\n".join(entries))
            return (0, "ADDED:1")

        app._run_rejected_cmd = _fake_rejected
        return app

    def test_a_concern_already_spun_off_is_skipped(self):
        concern = _spin_concerns("alpha")[0]
        app = self._app_with_store([
            f"REJECTED:r1|2026-08-13 10:00|spinoff|{concern_marker_line(concern)}"
        ])
        app.apply_concern_pick_result(
            _pick_result(spun_off=[concern]), "1427_2"
        )
        self.assertEqual(app.spy_created, [], "duplicate draft created")
        self.assertEqual(_adds(app), [])
        self.assertTrue(
            any("already spun off" in m for m, _ in app.spy_notify)
        )

    def test_a_merely_rejected_concern_is_still_creatable(self):
        """Positive control for the producer filter: `picker` means the user
        rejected it, which is not the same as having parked it as a task."""
        concern = _spin_concerns("alpha")[0]
        app = self._app_with_store([
            f"REJECTED:r1|2026-08-13 10:00|picker|{concern_marker_line(concern)}"
        ])
        app.apply_concern_pick_result(
            _pick_result(spun_off=[concern]), "1427_2"
        )
        self.assertEqual(len(app.spy_created), 1)

    def test_an_unreadable_store_creates_anyway(self):
        """Fail-open: `_fetch_rejected_entries` returns [] for every non-success
        outcome, so a store that cannot be read must not silently drop the
        user's request."""
        app = _spin_app()

        async def _unreadable(args, stdin_text=""):
            app.spy_rejected.append((list(args), stdin_text))
            return (4, "store unusable") if args[0] == "list" else (0, "ADDED:1")

        app._run_rejected_cmd = _unreadable
        app.apply_concern_pick_result(
            _pick_result(spun_off=_spin_concerns("alpha")), "1427_2"
        )
        self.assertEqual(len(app.spy_created), 1)


class SpinoffNamingTests(unittest.TestCase):
    """Names are collision-safe and survive `sanitize_name` (t1159_3)."""

    def test_two_same_region_concerns_get_distinct_names(self):
        app = _spin_app()
        app.apply_concern_pick_result(
            _pick_result(spun_off=_spin_concerns("same", "same")), "1427_2"
        )
        names = [
            args[args.index("--name") + 1] for args, _ in app.spy_created
        ]
        self.assertEqual(len(set(names)), 2, f"collision: {names}")

    def test_two_confirmations_in_the_same_minute_get_distinct_names(self):
        """`get_draft_filename` is minute-precision and `ait_atomic_render`
        overwrites silently, so the per-batch nonce is the whole guard."""
        first, second = _spin_app(), _spin_app()
        for app in (first, second):
            app.apply_concern_pick_result(
                _pick_result(spun_off=_spin_concerns("same")), "1427_2"
            )
        name_of = lambda app: app.spy_created[0][0][
            app.spy_created[0][0].index("--name") + 1
        ]
        self.assertNotEqual(name_of(first), name_of(second))

    def test_an_over_long_region_keeps_the_nonce_and_index_suffix(self):
        name = build_spinoff_name("x" * 200, "a1b2c3d4", 7)
        self.assertLessEqual(len(name), 60)
        self.assertTrue(name.endswith("_a1b2c3d4_7"), name)

    def test_punctuation_only_region_degrades_to_a_readable_stem(self):
        # `sanitize_name` DELETES these characters rather than replacing them,
        # so the region contributes nothing and must not leave `shadow__nonce`.
        name = build_spinoff_name(".../:", "a1b2c3d4", 1)
        self.assertEqual(name, "shadow_concern_a1b2c3d4_1")

    def test_region_is_reduced_exactly_as_sanitize_name_would(self):
        name = build_spinoff_name(
            "authoring-conv.md:103", "a1b2c3d4", 1
        )
        self.assertEqual(name, "shadow_authoringconvmd103_a1b2c3d4_1")


class SpinoffReentrancyTests(unittest.TestCase):
    """The in-flight EFFECT guard, which no app owned before t1159_3.

    `MonitorApp._concern_pick_busy` guards *modal stacking* and is released on
    dismissal — one line before the effects are even dispatched — and
    minimonitor had no equivalent at all. So a second confirmation could land
    while the first was still creating drafts, and the per-batch nonce would
    give it a fresh set of paths rather than deduping it.
    """

    def _deferred_app(self, **kwargs):
        """An app whose worker is captured instead of run, so the guard can be
        observed while it is genuinely held.

        Captured-but-unrun coroutines are closed at teardown: leaving one
        un-awaited emits a RuntimeWarning that would pollute the suite and
        could mask a real one. Closing an already-completed coroutine is a
        no-op, so this is safe for the ones the test does run.
        """
        app = _spin_app(**kwargs)
        app.spy_workers = []
        app.run_worker = lambda coro, **kw: app.spy_workers.append(coro)
        self.addCleanup(
            lambda: [coro.close() for coro in app.spy_workers]
        )
        return app

    def _confirm(self, app, task_id="1427_2"):
        app.apply_concern_pick_result(
            _pick_result(spun_off=_spin_concerns("alpha")), task_id
        )

    def test_a_second_confirmation_while_in_flight_is_refused(self):
        app = self._deferred_app()
        self._confirm(app)
        self.assertEqual(len(app.spy_workers), 1)

        self._confirm(app)
        self.assertEqual(len(app.spy_workers), 1, "a second worker was started")
        message, severity = app.spy_notify[-1]
        self.assertEqual(severity, "warning")
        self.assertIn("still running", message)

        asyncio.run(app.spy_workers[0])
        self.assertEqual(len(app.spy_created), 1, "only one batch ran")

    def test_the_guard_is_released_on_completion(self):
        """A guard, not a wedge."""
        app = self._deferred_app()
        self._confirm(app)
        asyncio.run(app.spy_workers[0])

        self._confirm(app)
        self.assertEqual(len(app.spy_workers), 2)

    def test_the_guard_is_released_when_the_worker_raises(self):
        """The `finally` negative control. The worker runs with
        exit_on_error=False, so a raise is swallowed — releasing only on the
        success path would wedge every later confirmation for this task."""
        app = self._deferred_app(create_raises=True)

        self._confirm(app)
        with self.assertRaises(RuntimeError):
            asyncio.run(app.spy_workers[0])

        self._confirm(app)
        self.assertEqual(
            len(app.spy_workers), 2, "the guard leaked after a raise"
        )

    def test_a_different_task_id_proceeds_concurrently(self):
        """The key is per-task: two panes on different tasks touch different
        store mutexes and must not block each other."""
        app = self._deferred_app()
        self._confirm(app, task_id="1427_2")
        self._confirm(app, task_id="9999_1")
        self.assertEqual(len(app.spy_workers), 2)


class SpinoffEndToEndTests(unittest.TestCase):
    """`c` -> `t` -> confirm reaches a real create call (t1159_3).

    The other spin-off tests call `apply_concern_pick_result` directly, which
    leaves the wiring between the picker's dismiss value and the mixin
    unproven: a `_result()` that forgot `spun_off=` would keep every one of
    them green. This drives the outermost surface the user actually touches.
    """

    def test_the_picker_result_carries_spun_off_into_a_create_call(self):
        app = _spin_app()
        app._find_own_agent_snapshot = lambda: _snap("%1")
        _stub_capture(self, _async_return(_CLOSED_BLOCK))
        asyncio.run(app.action_pick_concerns())
        modal, callback = app.spy_pushed[0]

        # Mark the first row spun-off through the modal's own state machine,
        # then dismiss exactly as Textual would, with the modal's OWN result.
        rows_state = modal._concerns
        modal._concerns_in_state = lambda state: (
            [rows_state[0]] if state == "spinoff" else []
        )
        callback(modal._result())

        self.assertEqual(len(app.spy_created), 1)
        args, stdin = app.spy_created[0]
        self.assertEqual(args[args.index("--followup-of") + 1], "1427_2")
        self.assertIn(concern_marker_line(rows_state[0]), stdin)


class SpinoffFailureReasonTests(unittest.TestCase):
    """A failed creation surfaces its ROOT CAUSE, readably (t1159_3)."""

    #: Verbatim shape of the real script's failure, captured from
    #: `aitask_create.sh --followup-of <missing>`: coloured, and preceded by a
    #: warning when a label needed normalizing.
    REAL_DIE = "\x1b[0;31mError: anchor target '999999' not found.\x1b[0m"

    def _reason_shown(self, out, rc=1):
        app = _spin_app(create_rc=rc, create_out=out)
        app.apply_concern_pick_result(
            _pick_result(spun_off=_spin_concerns("alpha")), "1427_2"
        )
        return next(m for m, sev in app.spy_notify if sev == "error")

    def test_ansi_escapes_never_reach_the_notification(self):
        message = self._reason_shown(self.REAL_DIE)
        self.assertNotIn("\x1b", message)
        self.assertIn("anchor target '999999' not found.", message)

    def test_a_preceding_warning_does_not_mask_the_real_cause(self):
        """stderr is merged into stdout, so a `warn` lands BEFORE the terminal
        `die`. Reporting the first line would hide the actual failure."""
        message = self._reason_shown(
            "\x1b[1;33mWarning: dropped invalid label(s)\x1b[0m\n" + self.REAL_DIE
        )
        self.assertIn("anchor target", message)
        self.assertNotIn("dropped invalid label", message)

    def test_an_empty_capture_still_names_the_exit_status(self):
        message = self._reason_shown("", rc=7)
        self.assertIn("exit 7", message)
