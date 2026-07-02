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
  re-hint; a changed concern does).

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
from monitor.concern_parser import build_clipboard_payload  # noqa: E402


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


def _async_return(value):
    async def _coro(*args, **kwargs):
        return value
    return _coro


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


def _mk_app(monitor=None):
    # Custom spy attribute names (spy_*) avoid colliding with read-only Textual
    # App properties such as ``clipboard``.
    app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
    app._monitor = monitor
    app._last_concern_block_payload = {}
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


def _snap(pane_id="%1"):
    return SimpleNamespace(pane=SimpleNamespace(pane_id=pane_id))


class MatchShadowPaneTests(unittest.TestCase):
    def test_returns_bound_shadow(self):
        out = "%1\t\n%5\t%1\n%6\t%2\n"
        self.assertEqual(mm.match_shadow_pane(out, "%1"), "%5")

    def test_none_when_no_match(self):
        out = "%1\t\n%6\t%2\n"
        self.assertIsNone(mm.match_shadow_pane(out, "%1"))

    def test_empty_target_ignored(self):
        out = "%1\t\n%2\t   \n"
        self.assertIsNone(mm.match_shadow_pane(out, "%1"))

    def test_multiple_matches_returns_newest(self):
        out = "%5\t%1\n%8\t%1\n%3\t%1\n"
        self.assertEqual(mm.match_shadow_pane(out, "%1"), "%8")


class ActionPickConcernsTests(unittest.TestCase):
    def test_happy_path_modal_then_clipboard(self):
        app = _mk_app(_FakeMon(async_list="%5\t%1"))
        app._find_own_agent_snapshot = lambda: _snap("%1")
        app._capture_shadow_text = _async_return(_CLOSED_BLOCK)

        asyncio.run(app.action_pick_concerns())

        # Modal pushed with the two parsed concerns; nothing on clipboard yet.
        self.assertEqual(len(app.spy_pushed), 1)
        modal, callback = app.spy_pushed[0]
        self.assertEqual(len(modal._concerns), 2)
        self.assertEqual(app.spy_clipboard, [])  # no side effect before confirm

        # Simulate confirm with a selected subset -> real callback runs.
        selected = [modal._concerns[0]]
        callback(selected)
        self.assertEqual(app.spy_clipboard, [build_clipboard_payload(selected)])
        self.assertTrue(any("copied" in m.lower() for m, _ in app.spy_notify))

    def test_cancel_writes_nothing(self):
        app = _mk_app(_FakeMon(async_list="%5\t%1"))
        app._find_own_agent_snapshot = lambda: _snap("%1")
        app._capture_shadow_text = _async_return(_CLOSED_BLOCK)
        asyncio.run(app.action_pick_concerns())
        _, callback = app.spy_pushed[0]
        callback(None)
        self.assertEqual(app.spy_clipboard, [])

    def test_no_shadow_pane_notifies_nothing_pushed(self):
        app = _mk_app(_FakeMon(async_list="%1\t\n%6\t%2"))  # no shadow for %1
        app._find_own_agent_snapshot = lambda: _snap("%1")
        app._capture_shadow_text = _async_return(_CLOSED_BLOCK)
        asyncio.run(app.action_pick_concerns())
        self.assertEqual(app.spy_pushed, [])
        self.assertEqual(app.spy_clipboard, [])
        self.assertTrue(any("shadow" in m.lower() for m, _ in app.spy_notify))

    def test_capture_failure_degrades(self):
        app = _mk_app(_FakeMon(async_list="%5\t%1"))
        app._find_own_agent_snapshot = lambda: _snap("%1")
        app._capture_shadow_text = _async_return(None)  # timeout / nonzero exit
        asyncio.run(app.action_pick_concerns())
        self.assertEqual(app.spy_pushed, [])
        self.assertEqual(app.spy_clipboard, [])
        self.assertTrue(any(sev == "warning" for _, sev in app.spy_notify))

    def test_empty_parse_no_modal(self):
        app = _mk_app(_FakeMon(async_list="%5\t%1"))
        app._find_own_agent_snapshot = lambda: _snap("%1")
        app._capture_shadow_text = _async_return("no concern block here")
        asyncio.run(app.action_pick_concerns())
        self.assertEqual(app.spy_pushed, [])
        self.assertEqual(app.spy_clipboard, [])


class LaunchShadowGuardTests(unittest.TestCase):
    def test_refuses_duplicate_shadow_via_sync_reader(self):
        mon = _FakeMon(sync_list="%5\t%1")  # an existing shadow bound to %1
        app = _mk_app(mon)
        app._find_own_agent_snapshot = lambda: _snap("%1")

        calls: list = []
        orig = mm.launch_in_tmux
        mm.launch_in_tmux = lambda *a, **k: (calls.append((a, k)), (None, None))[1]
        try:
            app.action_launch_shadow()
        finally:
            mm.launch_in_tmux = orig

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
        app._capture_shadow_text = _async_return(capture_value)
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
        app._capture_shadow_text = _async_return(
            "NEW PROMPT LINE\n" + _CLOSED_BLOCK + "\n$ "
        )
        asyncio.run(app._maybe_offer_concerns())
        self.assertEqual(len(app.spy_notify), 1)

    def test_changed_concern_refires(self):
        app = self._app(_CLOSED_BLOCK)
        asyncio.run(app._maybe_offer_concerns())
        changed = _CLOSED_BLOCK.replace(
            "double-commits the lock", "leaks a file handle"
        )
        app._capture_shadow_text = _async_return(changed)
        asyncio.run(app._maybe_offer_concerns())
        self.assertEqual(len(app.spy_notify), 2)

    def test_no_shadow_skips_silently(self):
        app = self._app(_CLOSED_BLOCK, async_list="%1\t\n%6\t%2")  # no shadow
        asyncio.run(app._maybe_offer_concerns())
        self.assertEqual(app.spy_notify, [])

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
        app._capture_shadow_text = _async_return(capture)
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
        f = mm.MiniMonitorApp._format_stale_duration
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
