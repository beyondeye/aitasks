"""Tests for shadow concerns in the FULL monitor (t1216_3).

Covers the badge / toast / picker triad `ait monitor` gains on top of the
t1216_1 seam and the t1216_2 SHADOW zone: a per-tick signature scan that spawns
no subprocess, a card badge derived for every agent, a verified toast for the
selected one, and `c` -> ConcernPickerModal -> clipboard.

Several of these pin invariants that are easy to get wrong and silent when
broken -- they are the tests that fail on the un-fixed code:

* The trigger reads the raw `-p -e` capture while every marker is written from
  the `-J` one, so the same block hashes two ways whenever it wraps mid-word.
  Storing a single digest re-captures every tick AND leaves the badge stuck on
  forever after a successful pick.
* `_mark_concern_sig` must take its trigger signature as a PARAMETER: reading
  `_concern_sig_latest` after the capture await lets the 3s tick substitute a
  NEWER block, marking it seen without ever presenting it -- a silent miss.
* The toast pins a pane id across up to 5s of awaits; without a re-check it
  fires for an agent the user has already navigated away from.
* `_concern_pick_busy` must be held until the modal is DISMISSED, not released
  when `push_screen` returns -- app bindings resolve up the focus chain and the
  modal does not bind `c`.
* `concern_block_signature` requires a complete fence but not a parsed concern,
  so an all-malformed block would otherwise announce "Shadow raised concerns"
  and then report nothing forwardable.

All ordering is deterministic -- scripted coroutines, no sleeps.
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

# MonitorApp.on_mount takes the deterministic not-inside-tmux path only when the
# ambient tmux env is absent; scrub it before importing (mirrors
# test_monitor_shadow_zone.py).
os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from monitor import monitor_app as ma  # noqa: E402
from monitor.monitor_app import MonitorApp  # noqa: E402
from monitor.monitor_core import (  # noqa: E402
    PaneCategory,
    PaneSnapshot,
    TmuxMonitor,
    TmuxPaneInfo,
)
from monitor.concern_parser import (  # noqa: E402
    _SENTINEL_SAFE_COLS,
    build_clipboard_payload,
    concern_block_signature,
    parse_concerns,
)
from monitor.monitor_shared import (  # noqa: E402
    SHADOW_CONCERN_GLYPH,
    SHADOW_GLYPH,
)
from monitor.prompt_patterns import all_patterns  # noqa: E402

# -- Fixtures ------------------------------------------------------------------

_CLOSED_BLOCK = (
    "some earlier pane output\n"
    "===AITASK-CONCERNS===\n"
    "- [high | Step 7 guard] The guard double-commits the lock.\n"
    "- [medium | parser] Multi-block accumulation is undefined.\n"
    "===END-CONCERNS===\n"
)
# A DIFFERENT complete block -- used for "the shadow re-issues another block".
_SECOND_BLOCK = (
    "===AITASK-CONCERNS===\n"
    "- [low | docs] The reference table omits the new key.\n"
    "===END-CONCERNS===\n"
)
# Capture window started INSIDE a block: items and the closing fence made it in,
# the opening fence did not (t1187).
_HEAD_TRUNCATED = (
    "- [high | Step 7 guard] The guard double-commits the lock.\n"
    "===END-CONCERNS===\n"
)
# A COMPLETE block whose every marker is malformed. Nothing parses, so saying
# "no concerns" about it would be a false all-clear (t1274).
_MALFORMED_ONLY_BLOCK = (
    "===AITASK-CONCERNS===\n"
    "- [ | Step 7 guard] The guard double-commits the lock.\n"
    "- [medium | parser never closes\n"
    "===END-CONCERNS===\n"
)
# A block with one informational concern alongside an actionable one, so the
# toast's "(+N informational)" suffix has something to report.
_MIXED_BLOCK = (
    "===AITASK-CONCERNS===\n"
    "- [high | Step 7 guard] The guard double-commits the lock.\n"
    "- [low | style] Naming nit. Disposition: informational.\n"
    "===END-CONCERNS===\n"
)

# The mid-word-wrap pair: ONE logical block, captured two ways. The raw tick
# capture (`-p -e`, no -J) breaks a wrapped row with a hard newline; whitespace
# normalisation turns that into a space the `-J` join never had. Asserted to
# hash differently by MidWordWrapDedupTests -- if that precondition ever stops
# holding, those tests would pass vacuously.
_WRAP_J = (
    "===AITASK-CONCERNS===\n"
    "- [high | parser] The guard doublecommits the lock.\n"
    "===END-CONCERNS===\n"
)
_WRAP_RAW = (
    "===AITASK-CONCERNS===\n"
    "- [high | parser] The guard double\n"
    "commits the lock.\n"
    "===END-CONCERNS===\n"
)


def _async_return(value):
    async def _coro(*args, **kwargs):
        return value
    return _coro


def _pane(
    pane_id: str,
    window_name: str = "agent-1",
    category: PaneCategory = PaneCategory.AGENT,
    shadow_target: str = "",
    width: int = 80,
) -> TmuxPaneInfo:
    idx = int(pane_id.lstrip("%"))
    return TmuxPaneInfo(
        window_index=str(idx), window_name=window_name, pane_index="0",
        pane_id=pane_id, pane_pid=1000 + idx, current_command="bash",
        width=width, height=24, category=category, session_name="demo",
        shadow_target=shadow_target,
    )


def _snap(pane: TmuxPaneInfo, content: str = "idle output") -> PaneSnapshot:
    return PaneSnapshot(
        pane=pane, content=content, timestamp=0.0, idle_seconds=0.0,
        is_idle=False,
    )


class _FakeMon:
    """Duck-typed monitor: the shadow lookup plus the compare-mode surface the
    card renderer touches. No tmux."""

    multi_session = False

    def __init__(self, shadow_by_followed=None):
        self._shadow_by_followed = dict(shadow_by_followed or {})
        self.stale_calls: list = []

    def get_compare_mode(self, pane_id):
        return "stripped"

    def is_compare_mode_overridden(self, pane_id):
        return False

    def get_shadow_snapshot(self, followed_pane_id):
        return self._shadow_by_followed.get(followed_pane_id)


def _mk_app(monitor=None, focused="%1"):
    """A MonitorApp with __init__ bypassed and only the fields under test set.

    `spy_`-prefixed attribute names avoid colliding with read-only Textual App
    properties. The clipboard spy hooks Textual's `copy_to_clipboard`, NOT
    `copy_to_system_clipboard` -- so the real seam in lib/tui_clipboard.py runs
    and is observed through its own inner call.
    """
    app = MonitorApp.__new__(MonitorApp)
    app._monitor = monitor if monitor is not None else _FakeMon()
    app._snapshots = {}
    app._focused_pane_id = focused
    app._tick_shadow_snaps = {}
    app._concern_sig_latest = {}
    app._concern_sig_offered = {}
    app._concern_sig_examined = {}
    app._concern_tick = 0
    app._offer_busy = False
    app._concern_pick_busy = False
    app._refresh_seconds = 3
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
    return app


class _CaptureScript:
    """Stands in for the module-level `capture_shadow_text`, recording argv."""

    def __init__(self, *returns, on_call=None):
        self._returns = list(returns)
        self.calls: list = []
        self._on_call = on_call

    async def __call__(self, shadow_pane, *, lines=None):
        self.calls.append((shadow_pane, lines))
        if self._on_call is not None:
            self._on_call(len(self.calls))
        return self._returns.pop(0) if self._returns else None


def _install_capture(test, script):
    """Swap the module-level capture for `script` for the test's duration."""
    original = ma.capture_shadow_text
    ma.capture_shadow_text = script
    test.addCleanup(lambda: setattr(ma, "capture_shadow_text", original))
    return script


def _install_staleness(test, value=(False, None)):
    original = ma.compute_shadow_staleness
    calls: list = []

    async def _fake(monitor, shadow_pane, followed_pane, eps):
        calls.append((shadow_pane, followed_pane, eps))
        return value

    ma.compute_shadow_staleness = _fake
    test.addCleanup(lambda: setattr(ma, "compute_shadow_staleness", original))
    return calls


def _run(coro):
    return asyncio.run(coro)


# -- The `c` hotkey ------------------------------------------------------------


class ActionPickConcernsTests(unittest.TestCase):
    def _app_with_shadow(self, shadow_content="idle"):
        shadow = _snap(_pane("%9", shadow_target="%1"), shadow_content)
        mon = _FakeMon({"%1": shadow})
        app = _mk_app(mon)
        app._snapshots = {"%1": _snap(_pane("%1"))}
        return app

    def test_modal_pushed_and_confirm_writes_clipboard(self):
        app = self._app_with_shadow()
        _install_capture(self, _CaptureScript(_CLOSED_BLOCK))
        _install_staleness(self)
        _run(app.action_pick_concerns())

        self.assertEqual(len(app.spy_pushed), 1)
        screen, callback = app.spy_pushed[0]
        self.assertEqual(len(screen._concerns), 2)
        self.assertFalse(screen._narrow, "the full monitor is not the 40-col sidebar")
        # Nothing on the clipboard before an explicit confirm.
        self.assertEqual(app.spy_clipboard, [])

        selected = list(screen._concerns)[:1]
        callback(selected)
        self.assertEqual(app.spy_clipboard, [build_clipboard_payload(selected)])

    def test_cancel_writes_nothing(self):
        app = self._app_with_shadow()
        _install_capture(self, _CaptureScript(_CLOSED_BLOCK))
        _install_staleness(self)
        _run(app.action_pick_concerns())
        _, callback = app.spy_pushed[0]
        callback(None)
        self.assertEqual(app.spy_clipboard, [])

    def test_no_focused_agent_warns(self):
        app = _mk_app(focused=None)
        _run(app.action_pick_concerns())
        self.assertIn("Focus an agent pane first", app.spy_notify[0][0])
        self.assertEqual(app.spy_pushed, [])

    def test_no_shadow_bound_warns_and_points_at_the_launch_key(self):
        app = _mk_app()
        app._snapshots = {"%1": _snap(_pane("%1"))}
        _run(app.action_pick_concerns())
        msg = app.spy_notify[0][0]
        self.assertIn("No shadow agent bound", msg)
        # t1216_4 bound `e` in the monitor, so naming it is now actionable rather
        # than a promise of a key that does nothing. Guard that the key named here
        # actually exists, so the message can never drift back into a false offer.
        self.assertIn("'e'", msg)
        self.assertIn(
            "e", [b.key for b in MonitorApp.BINDINGS
                  if getattr(b, "action", None) == "launch_shadow"],
        )
        self.assertEqual(app.spy_pushed, [])

    def test_capture_failure_warns_and_pushes_nothing(self):
        app = self._app_with_shadow()
        _install_capture(self, _CaptureScript(None))
        _run(app.action_pick_concerns())
        self.assertIn("Could not read the shadow pane", app.spy_notify[0][0])
        self.assertEqual(app.spy_pushed, [])

    def test_deep_retry_on_head_truncation(self):
        app = self._app_with_shadow()
        script = _install_capture(
            self, _CaptureScript(_HEAD_TRUNCATED, _CLOSED_BLOCK)
        )
        _install_staleness(self)
        _run(app.action_pick_concerns())
        self.assertEqual(
            [lines for _, lines in script.calls],
            [None, ma._SHADOW_DEEP_RETRY_LINES],
        )
        self.assertEqual(len(app.spy_pushed), 1)

    def test_still_truncated_after_retry_warns(self):
        app = self._app_with_shadow()
        _install_capture(self, _CaptureScript(_HEAD_TRUNCATED, _HEAD_TRUNCATED))
        _run(app.action_pick_concerns())
        self.assertIn("cut off above the capture window", app.spy_notify[0][0])
        self.assertEqual(app.spy_pushed, [])

    def test_malformed_only_block_reports_unparsed_not_no_concerns(self):
        app = self._app_with_shadow()
        _install_capture(self, _CaptureScript(_MALFORMED_ONLY_BLOCK))
        _run(app.action_pick_concerns())
        msg, severity = app.spy_notify[0]
        self.assertIn("could not be parsed", msg)
        self.assertEqual(severity, "warning")
        self.assertEqual(app.spy_pushed, [])

    def test_genuinely_no_block_keeps_the_plain_message_and_no_recapture(self):
        """Negative control for the deep retry: absence is not truncation."""
        app = self._app_with_shadow()
        script = _install_capture(self, _CaptureScript("just some output\n"))
        _run(app.action_pick_concerns())
        self.assertIn("No concerns detected", app.spy_notify[0][0])
        self.assertEqual(len(script.calls), 1, "must not pay for a deep retry")

    def test_unrecovered_count_forwarded_to_the_modal(self):
        """t1274 parity: the picker shows how much of the block was lost."""
        mixed = (
            "===AITASK-CONCERNS===\n"
            "- [high | parser] A real one.\n"
            "- [medium | parser never closes\n"
            "===END-CONCERNS===\n"
        )
        app = self._app_with_shadow()
        _install_capture(self, _CaptureScript(mixed))
        _install_staleness(self)
        _run(app.action_pick_concerns())
        screen, _ = app.spy_pushed[0]
        self.assertEqual(screen._unrecovered, 1)

    def test_stale_flag_forwarded_to_the_modal(self):
        app = self._app_with_shadow()
        _install_capture(self, _CaptureScript(_CLOSED_BLOCK))
        _install_staleness(self, value=(True, 123.0))
        _run(app.action_pick_concerns())
        screen, _ = app.spy_pushed[0]
        self.assertTrue(screen._stale)


# -- Badge lifecycle -----------------------------------------------------------


class BadgeLifecycleTests(unittest.TestCase):
    """One test per row of the task's PINNED badge-lifecycle table."""

    def _app(self, shadow_content=_CLOSED_BLOCK, width=80, focused="%1"):
        shadow = _snap(_pane("%9", shadow_target="%1", width=width), shadow_content)
        mon = _FakeMon({"%1": shadow})
        app = _mk_app(mon, focused=focused)
        app._snapshots = {"%1": _snap(_pane("%1"))}
        app._tick_shadow_snaps = {"%1": shadow}
        return app, shadow

    def test_new_block_raises_the_badge(self):
        app, _ = self._app()
        app._scan_concern_signatures()
        self.assertTrue(app._has_fresh_concerns("%1"))

    def test_no_block_no_badge(self):
        app, _ = self._app(shadow_content="just output\n")
        app._scan_concern_signatures()
        self.assertFalse(app._has_fresh_concerns("%1"))

    def test_unclosed_block_does_not_raise_the_badge(self):
        app, _ = self._app(
            shadow_content="===AITASK-CONCERNS===\n- [high | x] streaming...\n"
        )
        app._scan_concern_signatures()
        self.assertFalse(app._has_fresh_concerns("%1"))

    def test_push_with_concerns_clears_the_badge(self):
        app, _ = self._app()
        app._scan_concern_signatures()
        _install_capture(self, _CaptureScript(_CLOSED_BLOCK))
        _install_staleness(self)
        _run(app.action_pick_concerns())
        self.assertFalse(app._has_fresh_concerns("%1"))

    def test_cancelled_picker_leaves_the_badge_off(self):
        app, _ = self._app()
        app._scan_concern_signatures()
        _install_capture(self, _CaptureScript(_CLOSED_BLOCK))
        _install_staleness(self)
        _run(app.action_pick_concerns())
        _, callback = app.spy_pushed[0]
        callback(None)
        self.assertFalse(app._has_fresh_concerns("%1"))

    def test_capture_failure_leaves_the_marker_untouched(self):
        app, _ = self._app()
        app._scan_concern_signatures()
        before = dict(app._concern_sig_offered)
        _install_capture(self, _CaptureScript(None))
        _run(app.action_pick_concerns())
        self.assertEqual(app._concern_sig_offered, before)
        self.assertTrue(app._has_fresh_concerns("%1"))

    def test_still_truncated_leaves_the_marker_untouched(self):
        app, _ = self._app()
        app._scan_concern_signatures()
        before = dict(app._concern_sig_offered)
        _install_capture(self, _CaptureScript(_HEAD_TRUNCATED, _HEAD_TRUNCATED))
        _run(app.action_pick_concerns())
        self.assertEqual(app._concern_sig_offered, before)
        self.assertTrue(app._has_fresh_concerns("%1"))

    def test_definitive_negative_clears_the_badge(self):
        """A COMPLETE block yielding nothing forwardable is a definitive answer:
        the user has been told exactly that and it will never parse, so the badge
        must not stay lit forever."""
        app, _ = self._app(shadow_content=_MALFORMED_ONLY_BLOCK)
        app._scan_concern_signatures()
        self.assertTrue(app._has_fresh_concerns("%1"))
        _install_capture(self, _CaptureScript(_MALFORMED_ONLY_BLOCK))
        _run(app.action_pick_concerns())
        self.assertFalse(app._has_fresh_concerns("%1"))

    def test_no_complete_block_in_the_capture_is_not_definitive(self):
        """Discriminating counterpart to the test above: when the -J capture
        shows no complete block we learned nothing about the badged one."""
        app, _ = self._app()
        app._scan_concern_signatures()
        before = dict(app._concern_sig_offered)
        _install_capture(self, _CaptureScript("scrolled away\n"))
        _run(app.action_pick_concerns())
        self.assertEqual(app._concern_sig_offered, before)
        self.assertTrue(app._has_fresh_concerns("%1"))

    def test_a_different_block_raises_the_badge_again(self):
        app, shadow = self._app()
        app._scan_concern_signatures()
        _install_capture(self, _CaptureScript(_CLOSED_BLOCK))
        _install_staleness(self)
        _run(app.action_pick_concerns())
        self.assertFalse(app._has_fresh_concerns("%1"))
        app._tick_shadow_snaps = {
            "%1": _snap(_pane("%9", shadow_target="%1"), _SECOND_BLOCK)
        }
        app._scan_concern_signatures()
        self.assertTrue(app._has_fresh_concerns("%1"))

    def test_scroll_out_then_back_does_not_re_offer(self):
        app, _ = self._app()
        app._scan_concern_signatures()
        _install_capture(self, _CaptureScript(_CLOSED_BLOCK))
        _install_staleness(self)
        _run(app.action_pick_concerns())
        offered = dict(app._concern_sig_offered)

        # Scrolls out: no complete block on a WIDE pane is real evidence.
        app._tick_shadow_snaps = {
            "%1": _snap(_pane("%9", shadow_target="%1"), "later output\n")
        }
        app._scan_concern_signatures()
        self.assertFalse(app._has_fresh_concerns("%1"))
        self.assertEqual(app._concern_sig_offered, offered, "marker retained")

        # Scrolls back in: same block, still offered.
        app._tick_shadow_snaps = {
            "%1": _snap(_pane("%9", shadow_target="%1"), _CLOSED_BLOCK)
        }
        app._scan_concern_signatures()
        self.assertFalse(app._has_fresh_concerns("%1"))

    def test_shadow_death_and_respawn_retains_the_marker(self):
        """Decided with the user: eviction on shadow loss would re-offer an
        identical block when the shadow respawns, which the task's own sibling
        note forbids. `get_shadow_snapshot` cannot tell a dead shadow from a
        one-tick capture blip, so retention is also the only implementable rule
        without a per-agent grace counter."""
        app, _ = self._app()
        app._scan_concern_signatures()
        _install_capture(self, _CaptureScript(_CLOSED_BLOCK))
        _install_staleness(self)
        _run(app.action_pick_concerns())
        offered = dict(app._concern_sig_offered)

        app._tick_shadow_snaps = {}          # shadow died
        app._scan_concern_signatures()
        self.assertFalse(app._has_fresh_concerns("%1"))
        self.assertEqual(app._concern_sig_offered, offered)

        # Respawned, same block: must NOT re-offer.
        app._tick_shadow_snaps = {
            "%1": _snap(_pane("%12", shadow_target="%1"), _CLOSED_BLOCK)
        }
        app._scan_concern_signatures()
        self.assertFalse(app._has_fresh_concerns("%1"))

    def test_agent_leaving_the_snapshot_map_evicts(self):
        """The counterpart: the AGENT going away is unambiguous, so the entry is
        reclaimed. Without this the maps would grow for the session's life."""
        app, _ = self._app()
        app._scan_concern_signatures()
        _install_capture(self, _CaptureScript(_CLOSED_BLOCK))
        _install_staleness(self)
        _run(app.action_pick_concerns())
        self.assertIn("%1", app._concern_sig_offered)

        app._snapshots = {}
        app._tick_shadow_snaps = {}
        app._scan_concern_signatures()
        self.assertNotIn("%1", app._concern_sig_offered)
        self.assertNotIn("%1", app._concern_sig_examined)

    def test_agent_exit_evicts_an_examined_only_entry(self):
        """A block that verified to nothing forwardable leaves an `_examined`
        entry and NO `_offered` one, so an eviction sweep over `_offered` alone
        never visits it and it outlives the agent.

        Distinct from test_agent_leaving_the_snapshot_map_evicts, which reaches
        the agent through `c` and therefore populates BOTH maps — that path
        cannot see this leak.
        """
        app, _ = self._app(shadow_content=_MALFORMED_ONLY_BLOCK)
        app._scan_concern_signatures()
        _install_capture(self, _CaptureScript(_MALFORMED_ONLY_BLOCK))
        _install_staleness(self)
        _run(app._offer_concerns())
        self.assertIn("%1", app._concern_sig_examined)
        self.assertNotIn(
            "%1", app._concern_sig_offered,
            "precondition: only the examined map is populated here",
        )

        app._snapshots = {}
        app._tick_shadow_snaps = {}
        app._scan_concern_signatures()
        self.assertNotIn("%1", app._concern_sig_examined)

    def test_newer_block_between_badge_and_keypress_stores_the_captured_sig(self):
        """The shadow emitted more since the badge went up: the marker must
        cover what the picker actually showed, or the newer block is left
        permanently un-offered."""
        app, _ = self._app()
        app._scan_concern_signatures()
        _install_capture(self, _CaptureScript(_SECOND_BLOCK))
        _install_staleness(self)
        _run(app.action_pick_concerns())
        self.assertIn(
            concern_block_signature(_SECOND_BLOCK),
            app._concern_sig_offered["%1"],
        )


# -- The mid-word-wrap dedup contract -----------------------------------------


class MidWordWrapDedupTests(unittest.TestCase):
    """The raw tick capture and the -J capture hash the SAME block differently
    whenever it wraps mid-word. Storing one digest re-captures every tick and
    never clears the badge."""

    def test_precondition_the_two_digests_really_differ(self):
        raw = concern_block_signature(_WRAP_RAW)
        joined = concern_block_signature(_WRAP_J)
        self.assertIsNotNone(raw)
        self.assertIsNotNone(joined)
        self.assertNotEqual(
            raw, joined,
            "fixture no longer exercises the residual; the tests below would "
            "pass vacuously",
        )
        self.assertEqual(len(parse_concerns(_WRAP_J)), 1)

    def _wrapped_app(self):
        shadow = _snap(_pane("%9", shadow_target="%1"), _WRAP_RAW)
        app = _mk_app(_FakeMon({"%1": shadow}))
        app._snapshots = {"%1": _snap(_pane("%1"))}
        app._tick_shadow_snaps = {"%1": shadow}
        return app

    def test_badge_clears_after_a_pick_and_stays_clear(self):
        app = self._wrapped_app()
        app._scan_concern_signatures()
        self.assertTrue(app._has_fresh_concerns("%1"))
        _install_capture(self, _CaptureScript(_WRAP_J))
        _install_staleness(self)
        _run(app.action_pick_concerns())
        self.assertFalse(app._has_fresh_concerns("%1"))
        for _ in range(3):
            app._scan_concern_signatures()
            self.assertFalse(
                app._has_fresh_concerns("%1"),
                "badge stuck on: the raw digest never matches a lone -J digest",
            )

    def test_offer_pass_captures_once_across_several_ticks(self):
        app = self._wrapped_app()
        script = _install_capture(self, _CaptureScript(_WRAP_J, _WRAP_J, _WRAP_J))
        _install_staleness(self)
        for _ in range(3):
            app._scan_concern_signatures()
            _run(app._offer_concerns())
        self.assertEqual(
            len(script.calls), 1,
            "each block must be authoritatively checked once, not once per tick",
        )

    def test_single_digest_storage_fails_both_guarantees(self):
        """Negative control: with only the captured digest stored (the pre-fix
        behaviour) the badge sticks and the capture repeats -- proving the PAIR,
        not the fixture, is what makes the tests above pass."""
        original = MonitorApp._mark_concern_sig

        @staticmethod
        def _captured_only(store, pane_id, trigger_sig, captured_sig):
            store[pane_id] = frozenset({captured_sig})

        MonitorApp._mark_concern_sig = _captured_only
        # Re-wrap: reading a staticmethod off the class yields the plain
        # function, and assigning that back would rebind it as an instance
        # method (self would be prepended on every later call).
        self.addCleanup(
            lambda: setattr(
                MonitorApp, "_mark_concern_sig", staticmethod(original)
            )
        )

        app = self._wrapped_app()
        app._scan_concern_signatures()
        _install_capture(self, _CaptureScript(_WRAP_J))
        _install_staleness(self)
        _run(app.action_pick_concerns())
        app._scan_concern_signatures()
        self.assertTrue(
            app._has_fresh_concerns("%1"),
            "control did not reproduce the stuck badge",
        )

        app2 = self._wrapped_app()
        script = _install_capture(self, _CaptureScript(_WRAP_J, _WRAP_J, _WRAP_J))
        for _ in range(3):
            app2._scan_concern_signatures()
            _run(app2._offer_concerns())
        self.assertGreater(
            len(script.calls), 1, "control did not reproduce the repeat capture"
        )


# -- Supersession: a newer block arriving during the capture -------------------


class NewerBlockDuringCaptureTests(unittest.TestCase):
    """`_mark_concern_sig` must take its trigger as a parameter. Re-reading
    `_concern_sig_latest` at write time lets the 3s tick substitute a NEWER
    block, marking it seen without ever verifying or presenting it."""

    def _app(self):
        shadow = _snap(_pane("%9", shadow_target="%1"), _CLOSED_BLOCK)
        app = _mk_app(_FakeMon({"%1": shadow}))
        app._snapshots = {"%1": _snap(_pane("%1"))}
        app._tick_shadow_snaps = {"%1": shadow}
        app._scan_concern_signatures()
        return app

    def test_pick_does_not_swallow_a_block_that_arrived_mid_capture(self):
        app = self._app()
        sig_a = app._concern_sig_latest["%1"]
        sig_b = concern_block_signature(_SECOND_BLOCK)

        def _advance_tick(_n):
            # The refresh tick lands while the capture is in flight.
            app._concern_sig_latest["%1"] = sig_b

        _install_capture(
            self, _CaptureScript(_CLOSED_BLOCK, on_call=_advance_tick)
        )
        _install_staleness(self)
        _run(app.action_pick_concerns())

        stored = app._concern_sig_offered["%1"]
        self.assertIn(sig_a, stored)
        self.assertNotIn(sig_b, stored, "the newer block was silently swallowed")
        self.assertTrue(
            app._has_fresh_concerns("%1"), "B must still badge and be offerable"
        )

    def test_offer_does_not_swallow_a_block_that_arrived_mid_capture(self):
        app = self._app()
        sig_b = concern_block_signature(_SECOND_BLOCK)

        def _advance_tick(_n):
            app._concern_sig_latest["%1"] = sig_b

        _install_capture(
            self, _CaptureScript(_CLOSED_BLOCK, on_call=_advance_tick)
        )
        _install_staleness(self)
        _run(app._offer_concerns())

        self.assertNotIn(sig_b, app._concern_sig_examined["%1"])
        self.assertTrue(app._has_fresh_concerns("%1"))

    def test_ambient_read_control_swallows_it(self):
        """Negative control: restore the ambient read and the miss reappears."""
        original = MonitorApp._mark_concern_sig

        def _ambient(self_, store, pane_id, trigger_sig, captured_sig):
            store[pane_id] = frozenset(
                s for s in (self_._concern_sig_latest.get(pane_id), captured_sig)
                if s is not None
            )

        MonitorApp._mark_concern_sig = _ambient
        # Re-wrap: reading a staticmethod off the class yields the plain
        # function, and assigning that back would rebind it as an instance
        # method (self would be prepended on every later call).
        self.addCleanup(
            lambda: setattr(
                MonitorApp, "_mark_concern_sig", staticmethod(original)
            )
        )

        app = self._app()
        sig_b = concern_block_signature(_SECOND_BLOCK)

        def _advance_tick(_n):
            app._concern_sig_latest["%1"] = sig_b

        _install_capture(
            self, _CaptureScript(_CLOSED_BLOCK, on_call=_advance_tick)
        )
        _install_staleness(self)
        _run(app.action_pick_concerns())
        self.assertIn(
            sig_b, app._concern_sig_offered["%1"],
            "control did not reproduce the swallow",
        )


# -- The offer pass: toast, throttle, narrow probe -----------------------------


class OfferConcernsTests(unittest.TestCase):
    def _app(self, content=_CLOSED_BLOCK, width=80, focused="%1", agents=("%1",)):
        shadows = {}
        tick = {}
        snaps = {}
        for a in agents:
            snaps[a] = _snap(_pane(a))
            sh = _snap(
                _pane(f"%{int(a.lstrip('%')) + 100}", shadow_target=a, width=width),
                content,
            )
            shadows[a] = sh
            tick[a] = sh
        app = _mk_app(_FakeMon(shadows), focused=focused)
        app._snapshots = snaps
        app._tick_shadow_snaps = tick
        app._scan_concern_signatures()
        return app

    def test_toast_carries_the_real_counts(self):
        app = self._app(content=_MIXED_BLOCK)
        _install_capture(self, _CaptureScript(_MIXED_BLOCK))
        _install_staleness(self)
        _run(app._offer_concerns())
        msg = app.spy_notify[0][0]
        self.assertIn("Shadow raised 1 concern(s)", msg)
        self.assertIn("(+1 informational)", msg)
        self.assertIn("press 'c' to pick", msg)

    def test_toast_fires_once_per_signature(self):
        app = self._app()
        _install_capture(self, _CaptureScript(_CLOSED_BLOCK, _CLOSED_BLOCK))
        _install_staleness(self)
        _run(app._offer_concerns())
        _run(app._offer_concerns())
        self.assertEqual(len(app.spy_notify), 1)

    def test_stale_suffix(self):
        app = self._app()
        _install_capture(self, _CaptureScript(_CLOSED_BLOCK))
        _install_staleness(self, value=(True, 100.0))
        _run(app._offer_concerns())
        self.assertIn("STALE", app.spy_notify[0][0])

    def test_indeterminate_staleness_adds_no_suffix(self):
        """`compute_shadow_staleness` is tri-state; None means 'preserve', and a
        one-shot toast has no prior state to preserve."""
        app = self._app()
        _install_capture(self, _CaptureScript(_CLOSED_BLOCK))
        _install_staleness(self, value=(None, None))
        _run(app._offer_concerns())
        self.assertNotIn("STALE", app.spy_notify[0][0])

    def test_only_the_selected_agent_toasts(self):
        app = self._app(agents=("%1", "%2"), focused="%1")
        _install_capture(self, _CaptureScript(_CLOSED_BLOCK, _CLOSED_BLOCK))
        _install_staleness(self)
        _run(app._offer_concerns())
        self.assertEqual(len(app.spy_notify), 1)
        # ...but the non-selected agent still carries a badge.
        self.assertTrue(app._has_fresh_concerns("%2"))

    def test_malformed_block_badges_without_toasting(self):
        """`concern_block_signature` signs a complete FENCE, not a parsed
        concern -- announcing "Shadow raised concerns" for a block that yields
        nothing forwardable would be contradicted by `c` moments later."""
        app = self._app(content=_MALFORMED_ONLY_BLOCK)
        _install_capture(self, _CaptureScript(_MALFORMED_ONLY_BLOCK))
        _install_staleness(self)
        _run(app._offer_concerns())
        self.assertEqual(app.spy_notify, [])
        self.assertTrue(app._has_fresh_concerns("%1"))

    def test_malformed_block_is_verified_only_once(self):
        app = self._app(content=_MALFORMED_ONLY_BLOCK)
        script = _install_capture(
            self, _CaptureScript(*([_MALFORMED_ONLY_BLOCK] * 4))
        )
        _install_staleness(self)
        for _ in range(4):
            app._scan_concern_signatures()
            _run(app._offer_concerns())
        self.assertEqual(len(script.calls), 1)

    def test_focus_change_during_capture_suppresses_the_toast(self):
        app = self._app(agents=("%1", "%2"), focused="%1")

        def _move_focus(_n):
            app._focused_pane_id = "%2"

        _install_capture(
            self, _CaptureScript(_CLOSED_BLOCK, on_call=_move_focus)
        )
        _install_staleness(self)
        _run(app._offer_concerns())
        self.assertEqual(app.spy_notify, [], "toasted for a deselected agent")
        # The check really did run, so it is not repeated...
        self.assertIn("%1", app._concern_sig_examined)
        # ...and the durable signal is untouched.
        self.assertTrue(app._has_fresh_concerns("%1"))

    def test_focus_unchanged_does_toast(self):
        """Positive control for the test above: a broken offer path would pass
        the negative assertion vacuously."""
        app = self._app()
        _install_capture(self, _CaptureScript(_CLOSED_BLOCK))
        _install_staleness(self)
        _run(app._offer_concerns())
        self.assertEqual(len(app.spy_notify), 1)

    def test_same_pane_advancing_to_a_new_block_suppresses_the_toast(self):
        """Identity is not freshness.

        The shadow pane is unchanged and focus has not moved, but the SAME pane
        has advanced from the block we verified (A) to a newer one (B) while we
        were awaiting staleness. Announcing A's count would disagree with the
        badge (tracking B) and with the picker a keypress later.
        """
        app = self._app()
        sig_b = concern_block_signature(_SECOND_BLOCK)

        original = ma.compute_shadow_staleness

        async def _advance_then_answer(monitor, shadow_pane, followed_pane, eps):
            app._concern_sig_latest[followed_pane] = sig_b
            return (False, None)

        ma.compute_shadow_staleness = _advance_then_answer
        self.addCleanup(
            lambda: setattr(ma, "compute_shadow_staleness", original)
        )
        _install_capture(self, _CaptureScript(_CLOSED_BLOCK))
        _run(app._offer_concerns())

        self.assertEqual(
            app.spy_notify, [], "toasted a count for a block already superseded"
        )
        # B was never verified, so the next pass still owns it.
        self.assertNotIn(sig_b, app._concern_sig_examined["%1"])
        self.assertTrue(app._has_fresh_concerns("%1"))

    def test_shadow_rebound_during_capture_suppresses_the_toast(self):
        app = self._app()

        def _rebind(_n):
            app._monitor._shadow_by_followed["%1"] = _snap(
                _pane("%77", shadow_target="%1"), _CLOSED_BLOCK
            )

        _install_capture(self, _CaptureScript(_CLOSED_BLOCK, on_call=_rebind))
        _install_staleness(self)
        _run(app._offer_concerns())
        self.assertEqual(app.spy_notify, [])

    def test_no_subprocess_when_nothing_is_new(self):
        """The steady state costs nothing, for any N."""
        app = self._app(agents=("%1", "%2", "%3"), content="plain output\n")
        script = _install_capture(self, _CaptureScript())
        _install_staleness(self)
        for _ in range(5):
            app._scan_concern_signatures()
            _run(app._offer_concerns())
        self.assertEqual(script.calls, [])

    def test_exactly_one_capture_for_a_new_block_regardless_of_n(self):
        app = self._app(agents=("%1", "%2", "%3"), focused="%1")
        script = _install_capture(self, _CaptureScript(_CLOSED_BLOCK))
        _install_staleness(self)
        _run(app._offer_concerns())
        self.assertEqual(len(script.calls), 1)

    def test_busy_latch_blocks_a_second_pass(self):
        app = self._app()
        app._offer_busy = True
        script = _install_capture(self, _CaptureScript(_CLOSED_BLOCK))
        _run(app._offer_concerns())
        self.assertEqual(script.calls, [])

    def test_worker_dispatch_is_not_exclusive(self):
        """Cancelling the pass would orphan `capture_shadow_text`'s subprocess,
        which is killed only on its OWN timeout. Pinned so re-adding
        `exclusive=True` -- or folding it into a render group -- fails here."""
        import inspect
        src = inspect.getsource(MonitorApp._refresh_data)
        idx = src.index('group="concerns"')
        call = src[src.rindex("self.run_worker(", 0, idx):idx]
        self.assertNotIn("exclusive", call)


class NarrowPaneProbeTests(unittest.TestCase):
    """Below `_SENTINEL_SAFE_COLS` the fences themselves can wrap, so the cheap
    detector's silence is not evidence of absence."""

    def _app(self, width, focused="%1", agents=("%1",)):
        shadows, tick, snaps = {}, {}, {}
        for a in agents:
            snaps[a] = _snap(_pane(a))
            sh = _snap(
                _pane(f"%{int(a.lstrip('%')) + 100}", shadow_target=a, width=width),
                "wrapped junk without visible fences\n",
            )
            shadows[a] = sh
            tick[a] = sh
        app = _mk_app(_FakeMon(shadows), focused=focused)
        app._snapshots = snaps
        app._tick_shadow_snaps = tick
        app._scan_concern_signatures()
        return app

    def test_probe_fires_for_a_narrow_selected_shadow(self):
        app = self._app(width=_SENTINEL_SAFE_COLS - 1)
        script = _install_capture(self, _CaptureScript(_CLOSED_BLOCK))
        _install_staleness(self)
        _run(app._offer_concerns())
        self.assertEqual(len(script.calls), 1)
        self.assertTrue(app._has_fresh_concerns("%1"))

    def test_probe_is_throttled_to_every_other_tick(self):
        app = self._app(width=_SENTINEL_SAFE_COLS - 1)
        script = _install_capture(self, _CaptureScript(None, None, None, None))
        _install_staleness(self)
        for _ in range(4):
            _run(app._offer_concerns())
        self.assertEqual(len(script.calls), 2)

    def test_exactly_sentinel_safe_width_never_probes(self):
        """Boundary negative control: 24 is the SAFE width, not a narrow one."""
        app = self._app(width=_SENTINEL_SAFE_COLS)
        script = _install_capture(self, _CaptureScript(_CLOSED_BLOCK))
        _run(app._offer_concerns())
        self.assertEqual(script.calls, [])

    def test_non_selected_narrow_agent_never_probes(self):
        app = self._app(
            width=_SENTINEL_SAFE_COLS - 1, agents=("%1", "%2"), focused="%1"
        )
        script = _install_capture(self, _CaptureScript(None))
        _run(app._offer_concerns())
        self.assertEqual([p for p, _ in script.calls], ["%101"])

    def test_narrow_badge_does_not_flicker(self):
        """The probe's signature must survive the wholesale rebuild each tick,
        or a narrow-pane badge blinks on and off every other tick."""
        app = self._app(width=_SENTINEL_SAFE_COLS - 1)
        _install_capture(self, _CaptureScript(_CLOSED_BLOCK))
        _install_staleness(self)
        _run(app._offer_concerns())
        self.assertTrue(app._has_fresh_concerns("%1"))
        for _ in range(3):
            app._scan_concern_signatures()
            self.assertTrue(app._has_fresh_concerns("%1"))

    def test_carry_forward_boundary_is_exactly_sentinel_safe_cols(self):
        """Discriminating test for the OTHER `_SENTINEL_SAFE_COLS` site.

        `_offer_concerns` decides whether to probe; `_scan_concern_signatures`
        decides whether absence is evidence. At exactly the safe width the
        fences cannot wrap, so a vanished block MUST drop the badge — a `<=`
        here would carry the signature forward forever and strand it lit.
        """
        for width, expect_badge in ((_SENTINEL_SAFE_COLS - 1, True),
                                    (_SENTINEL_SAFE_COLS, False)):
            with self.subTest(width=width):
                sh = _snap(
                    _pane("%9", shadow_target="%1", width=width), _CLOSED_BLOCK
                )
                app = _mk_app(_FakeMon({"%1": sh}))
                app._snapshots = {"%1": _snap(_pane("%1"))}
                app._tick_shadow_snaps = {"%1": sh}
                app._scan_concern_signatures()
                self.assertTrue(app._has_fresh_concerns("%1"))

                app._tick_shadow_snaps = {
                    "%1": _snap(
                        _pane("%9", shadow_target="%1", width=width),
                        "block gone\n",
                    )
                }
                app._scan_concern_signatures()
                self.assertEqual(app._has_fresh_concerns("%1"), expect_badge)

    def test_wide_pane_absence_still_drops_the_badge(self):
        """Negative control for the carry-forward: it is scoped to sub-sentinel
        widths, not 'never forget'."""
        shadow = _snap(_pane("%9", shadow_target="%1", width=80), _CLOSED_BLOCK)
        app = _mk_app(_FakeMon({"%1": shadow}))
        app._snapshots = {"%1": _snap(_pane("%1"))}
        app._tick_shadow_snaps = {"%1": shadow}
        app._scan_concern_signatures()
        self.assertTrue(app._has_fresh_concerns("%1"))
        app._tick_shadow_snaps = {
            "%1": _snap(_pane("%9", shadow_target="%1", width=80), "gone\n")
        }
        app._scan_concern_signatures()
        self.assertFalse(app._has_fresh_concerns("%1"))


# -- Re-entrancy ---------------------------------------------------------------


class PickReentrancyTests(unittest.TestCase):
    def _app(self):
        shadow = _snap(_pane("%9", shadow_target="%1"), _CLOSED_BLOCK)
        app = _mk_app(_FakeMon({"%1": shadow}))
        app._snapshots = {"%1": _snap(_pane("%1"))}
        return app

    def test_second_press_while_the_modal_is_open_is_a_no_op(self):
        """App bindings resolve up the focus chain and ConcernPickerModal does
        not bind `c`, so releasing the guard when push_screen returns would let
        a second press stack another picker."""
        app = self._app()
        _install_capture(self, _CaptureScript(_CLOSED_BLOCK, _CLOSED_BLOCK))
        _install_staleness(self)
        _run(app.action_pick_concerns())
        self.assertEqual(len(app.spy_pushed), 1)
        self.assertTrue(app._concern_pick_busy, "guard released too early")

        _run(app.action_pick_concerns())
        self.assertEqual(len(app.spy_pushed), 1, "a second picker was stacked")

        # Dismissal hands the guard back.
        _, callback = app.spy_pushed[0]
        callback(None)
        self.assertFalse(app._concern_pick_busy)
        _run(app.action_pick_concerns())
        self.assertEqual(len(app.spy_pushed), 2)

    def test_guard_released_on_every_early_return(self):
        app = self._app()
        _install_capture(self, _CaptureScript(None))
        _run(app.action_pick_concerns())
        self.assertFalse(app._concern_pick_busy)


# -- Constructed-app path ------------------------------------------------------


async def _sync_offloaded(fn):
    return fn()


def _make_monitor(panes, shadows, content):
    mon = TmuxMonitor(
        session="demo", multi_session=False, agent_prefixes=["agent-"],
        prompt_patterns=all_patterns(), idle_threshold=5.0,
    )
    mon._run_offloaded = _sync_offloaded
    for p in panes:
        mon._pane_cache[p.pane_id] = p

    async def discover_with_shadows(*, enum_sink=None):
        # Accepts the real seam's enumeration sink (t1326).
        if enum_sink is not None:
            enum_sink.append(frozenset(
                p.session_name for p in list(panes) + list(shadows) if p.session_name))
        return list(panes), list(shadows)

    async def cap_content(pane_id, capture_lines=None, pane=None):
        if pane_id not in content:
            return None
        if pane is None:
            pane = mon._pane_cache.get(pane_id)
            if pane is None:
                pane = next((s for s in shadows if s.pane_id == pane_id), None)
        if pane is None:
            return None
        return pane, content[pane_id]

    mon.discover_panes_with_shadows_async = discover_with_shadows
    mon.capture_pane_content_async = cap_content
    return mon


class ConstructedAppTests(unittest.TestCase):
    """Drives a REAL MonitorApp with nothing hand-set.

    Every other test here builds the app with `__new__` and assigns the concern
    fields itself, so a missing `__init__` initializer would pass the entire
    suite and raise AttributeError only in live use. This test is what closes
    that hole.
    """

    def test_init_provides_every_concern_field(self):
        app = MonitorApp(session="demo", project_root=REPO_ROOT)
        for name in (
            "_tick_shadow_snaps", "_concern_sig_latest", "_concern_sig_offered",
            "_concern_sig_examined", "_concern_tick", "_offer_busy",
            "_concern_pick_busy",
        ):
            self.assertTrue(hasattr(app, name), f"__init__ never set {name}")

    def test_full_refresh_badges_then_c_pushes_the_picker(self):
        agent = _pane("%1", "agent-t42")
        shadow = _pane("%9", "agent-t42", shadow_target="%1")
        mon = _make_monitor(
            [agent], [shadow], {"%1": "working\n", "%9": _CLOSED_BLOCK}
        )
        app = MonitorApp(session="demo", project_root=REPO_ROOT)
        app._monitor = mon

        async def _none():
            return None

        async def _mapping():
            return {}

        app._consume_focus_request = _none
        app._read_attached_session = _none
        mon.get_session_to_project_mapping_async = _mapping

        async def scenario():
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()
                app._focused_pane_id = "%1"
                await app._refresh_data()
                await pilot.pause()

                # The badge is derived from state __init__ created and
                # _refresh_data populated -- nothing was hand-set.
                self.assertTrue(app._has_fresh_concerns("%1"))
                row = app._format_agent_card_text(app._snapshots["%1"])
                self.assertIn(SHADOW_GLYPH + SHADOW_CONCERN_GLYPH, row)

                pushed: list = []
                app.push_screen = lambda s, callback=None: pushed.append(s)
                _install_capture(self, _CaptureScript(_CLOSED_BLOCK))
                _install_staleness(self)
                await app.action_pick_concerns()
                self.assertEqual(len(pushed), 1)
                self.assertEqual(len(pushed[0]._concerns), 2)

        asyncio.run(scenario())

    def test_rendered_row_carries_the_marker_only_when_concerns_are_fresh(self):
        """Render-level, both directions. Asserting `_has_fresh_concerns` alone
        would not notice a card renderer that passed a constant through."""
        agent = _snap(_pane("%1"))

        def _row(shadow_content):
            sh = _snap(_pane("%9", shadow_target="%1"), shadow_content)
            app = MonitorApp(session="demo", project_root=REPO_ROOT)
            app._monitor = _FakeMon({"%1": sh})
            app._snapshots = {"%1": agent}
            app._tick_shadow_snaps = {"%1": sh}
            app._scan_concern_signatures()
            return app._format_agent_card_text(agent)

        with_block = _row(_CLOSED_BLOCK)
        without = _row("just working\n")
        self.assertIn(SHADOW_GLYPH + SHADOW_CONCERN_GLYPH, with_block)
        self.assertIn(SHADOW_GLYPH, without)
        self.assertNotIn(
            SHADOW_CONCERN_GLYPH, without,
            "a shadowed row with no fresh block must not carry the marker",
        )

    def test_non_shadowed_row_is_unchanged_by_the_feature(self):
        """The t1133 / RowRenderTests invariant: a row with no shadow renders
        byte-identically whether or not any shadow state exists."""
        agent = _pane("%2", "agent-other")
        app = MonitorApp(session="demo", project_root=REPO_ROOT)
        shadow_snap = _snap(_pane("%9", shadow_target="%1"), _CLOSED_BLOCK)
        app._monitor = _FakeMon({"%1": shadow_snap})
        app._tick_shadow_snaps = {"%1": shadow_snap}
        app._snapshots = {"%1": _snap(_pane("%1")), "%2": _snap(agent)}
        app._scan_concern_signatures()
        self.assertTrue(app._has_fresh_concerns("%1"))

        bare = MonitorApp(session="demo", project_root=REPO_ROOT)
        bare._monitor = _FakeMon({})
        self.assertEqual(
            app._format_agent_card_text(_snap(agent)),
            bare._format_agent_card_text(_snap(agent)),
        )


if __name__ == "__main__":
    unittest.main()
