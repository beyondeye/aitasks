#!/usr/bin/env python3
"""The shared agent-submit loop, driven directly (t2275).

``monitor/agent_submit.submit_typed_text`` is the one implementation of the
pre-Enter proof / mode gate / bounded retry used by the minimonitor's shadow
recheck and the sitrep request delivery. Pinned here, over a scripted fake:

``OutcomeTests``
    Every neutral outcome kind, the read order (capture, width, mode -- the mode
    is the last read before every Enter), the checkpoint stopping ahead of every
    verdict and before ``EXHAUSTED``, ``before_retry`` only on later attempts, no
    retry after a BUSY post-Enter read that is not exactly the text, and the
    ``send_enter`` contract (a coroutine function, refused before any read).

``LookupSiteTests``
    The loop resolves its collaborators at call time, so patching
    ``agent_submit.payload_matches`` reaches the decision -- the unit twin of
    the occurrence-count mutant in ``tests/test_sitrep_request_delivery_live.sh``.

``RecheckPromptShapeTests``
    Every recheck prompt is one single-spaced line, so the proof can match it.

``ComposerRenderTests``
    ``tests/composer_render.py`` -- the minimonitor test fake's composer --
    reproduces every genuine capture in ``tests/shadow_recheck_fixtures.py``.

Run: python3 tests/test_agent_submit.py
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest import mock

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent / ".aitask-scripts"
for _p in (str(_HERE), str(_SCRIPTS), str(_SCRIPTS / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import composer_render  # noqa: E402
import review_loop_fixtures as rlf  # noqa: E402
from shadow_recheck_fixtures import FIXTURES, WIDTHS  # noqa: E402

from monitor import agent_submit as s  # noqa: E402
from monitor import monitor_core as mc  # noqa: E402
from monitor import review_loop as rl  # noqa: E402

PANE = "%5"
W = 60
TEXT = rl.compose_recheck_prompt("PLAN", 1)
TYPED = FIXTURES["claude_w60_recheck_plan"][4]
APPENDED = FIXTURES["claude_w60_appended"][4]
DRAFT = FIXTURES["claude_w60_history_draft"][4]
POST = FIXTURES["claude_w60_post_enter"][4]
NARROW = FIXTURES["claude_w44_recheck_plan"][4]          # BUSY, unprovable at 60
REST = rlf.CLAUDE_AT_REST_RAW
DIALOG = rlf.CLAUDE_DIALOG_RAW


class Fake:
    """``tails`` per capture (None = failed), ``modes`` per mode read (True /
    False / None = unreadable). ``events`` records every read and Enter."""

    def __init__(self, tails, modes=(), width=W):
        self.tails = list(tails)
        self.modes = list(modes)
        self.width = width
        self.events = []

    async def tmux_run_async(self, args, timeout=5.0):
        if args[0] == "capture-pane":
            self.events.append("capture")
            tail = self.tails.pop(0) if self.tails else None
            return (1, "") if tail is None else (0, tail)
        fmt = args[-1]
        if "pane_in_mode" in fmt:
            self.events.append("mode")
            m = self.modes.pop(0) if self.modes else None
            return (1, "") if m is None else (0, f"{PANE}\t{1 if m else 0}\t\n")
        if "pane_width" in fmt:
            self.events.append("width")
            return 0, f"{PANE}\t{self.width}\n"
        return 1, ""


async def _nosleep(_s):
    return None


class OutcomeTests(unittest.TestCase):
    def run_(self, fake, *, acks=None, checkpoint=None, before_retry=None, text=TEXT):
        acks = list(acks if acks is not None else [mc.DISPATCH_SENT] * 3)

        async def send_enter():
            fake.events.append("enter")
            state = acks.pop(0) if acks else mc.DISPATCH_UNKNOWN
            return state, ("reason" if state != mc.DISPATCH_SENT else "")

        return asyncio.run(s.submit_typed_text(
            fake, PANE, "claude", text, send_enter=send_enter, sleep=_nosleep,
            checkpoint=checkpoint, before_retry=before_retry))

    def test_every_outcome_kind(self):
        cases = {
            s.POST_SUBMITTED: (Fake([TYPED, POST], [False]), {}),
            s.PRE_NOT_BUSY: (Fake([REST], [False]), {}),
            s.PRE_UNPROVABLE: (Fake([NARROW], [False]), {}),
            s.PRE_CHANGED: (Fake([APPENDED], [False]), {}),
            s.PRE_MODE_UNREADABLE: (Fake([TYPED], [None]), {}),
            s.PRE_IN_MODE: (Fake([TYPED], [True]), {}),
            s.ENTER_NOT_SENT: (Fake([TYPED], [False]), {"acks": [mc.DISPATCH_SKIPPED]}),
            s.POST_UNVERIFIED: (Fake([TYPED, DIALOG], [False]), {}),
            s.POST_UNPROVABLE: (Fake([TYPED, NARROW], [False]), {}),
            s.POST_CHANGED: (Fake([TYPED, DRAFT], [False]), {}),
            s.EXHAUSTED: (Fake([TYPED] * 4, [False, False]), {}),
            s.STOPPED: (Fake([TYPED], [False]), {"checkpoint": lambda w, o: "stop"}),
        }
        self.assertEqual(set(cases), set(s.OUTCOME_KINDS))
        for kind, (fake, kw) in cases.items():
            with self.subTest(kind):
                self.assertEqual(self.run_(fake, **kw).kind, kind)

    def test_outcome_detail(self):
        out = self.run_(Fake([DIALOG], [False]))
        self.assertEqual((out.kind, out.state, out.attempt), (s.PRE_NOT_BUSY, rl.SHADOW_DIALOG, 0))
        out = self.run_(Fake([TYPED], [False]), acks=[mc.DISPATCH_SKIPPED])
        self.assertEqual(out.enter, (mc.DISPATCH_SKIPPED, "reason"))
        out = self.run_(Fake([TYPED, None], [False]))
        self.assertEqual((out.kind, out.state), (s.POST_UNVERIFIED, rl.SHADOW_UNKNOWN))
        out = self.run_(Fake([TYPED, TYPED, APPENDED], [False, False]))
        self.assertEqual((out.kind, out.attempt), (s.PRE_CHANGED, 1))
        self.assertEqual((out.obs.attempt, out.obs.in_mode), (1, False))

    def test_the_mode_is_the_last_read_before_every_enter(self):
        fake = Fake([TYPED, TYPED, TYPED, POST], [False, False])
        self.assertEqual(self.run_(fake).kind, s.POST_SUBMITTED)
        self.assertEqual(fake.events, ["capture", "width", "mode", "enter", "capture", "width",
                                       "capture", "width", "mode", "enter", "capture"])

    def test_the_checkpoint_stops_ahead_of_every_verdict(self):
        for tail in (REST, DIALOG, APPENDED, NARROW, TYPED):
            with self.subTest(state=rl.shadow_state(tail, "claude")):
                seen = []
                fake = Fake([tail], [False])
                out = self.run_(fake, checkpoint=lambda w, o: seen.append((w, o)) or "stop")
                self.assertEqual((out.kind, out.stop), (s.STOPPED, "stop"))
                self.assertNotIn("enter", fake.events)
                self.assertEqual(seen[0][0], "pre_enter")
                self.assertEqual(fake.events[-1], "mode", "after the attempt's last read")

    def test_the_checkpoint_runs_before_exhausted(self):
        wheres = []

        def checkpoint(where, obs):
            wheres.append(where)
            return "late" if where == "exhausted" else None
        out = self.run_(Fake([TYPED] * 4, [False, False]), checkpoint=checkpoint)
        self.assertEqual((out.kind, out.stop), (s.STOPPED, "late"))
        self.assertEqual(wheres, ["pre_enter", "pre_enter", "exhausted"])

    def test_before_retry_only_on_later_attempts(self):
        calls = []

        async def before_retry():
            calls.append("retry")
        self.run_(Fake([TYPED, POST], [False]), before_retry=before_retry)
        self.assertEqual(calls, [])
        self.run_(Fake([TYPED, TYPED, TYPED, POST], [False, False]), before_retry=before_retry)
        self.assertEqual(calls, ["retry"])

    def test_no_retry_after_a_busy_read_that_is_not_the_text(self):
        for after, kind in ((DRAFT, s.POST_CHANGED), (NARROW, s.POST_UNPROVABLE)):
            with self.subTest(kind):
                fake = Fake([TYPED, after, TYPED, POST], [False, False])
                self.assertEqual(self.run_(fake).kind, kind)
                self.assertEqual(fake.events.count("enter"), 1)

    def test_send_enter_must_be_a_coroutine_function(self):
        fake = Fake([TYPED, POST], [False])

        def sync_enter():
            fake.events.append("enter")
            return mc.DISPATCH_SENT, ""
        with self.assertRaises(TypeError):
            asyncio.run(s.submit_typed_text(fake, PANE, "claude", TEXT,
                                            send_enter=sync_enter, sleep=_nosleep))
        self.assertEqual(fake.events, [], "refused before any read or key")


class LookupSiteTests(unittest.TestCase):
    def test_patching_the_matcher_reaches_the_decision(self):
        async def send_enter():
            return mc.DISPATCH_SENT, ""

        def go():
            return asyncio.run(s.submit_typed_text(
                Fake([APPENDED, POST], [False]), PANE, "claude", TEXT,
                send_enter=send_enter, sleep=_nosleep)).kind
        self.assertEqual(go(), s.PRE_CHANGED)
        with mock.patch.object(s, "payload_matches", lambda p, e: True):
            self.assertEqual(go(), s.POST_SUBMITTED, "a weaker matcher lets the Enter go")

    def test_the_sitrep_module_re_exports_the_same_objects(self):
        from monitor import agent_request_delivery as d
        for name in ("display_width", "payload_matches", "_moved_piece",
                     "_hyphen_justified", "_WORD_RE", "_FRAGMENT_RE"):
            self.assertIs(getattr(d, name), getattr(s, name), name)
        self.assertIs(d._pane_width, s.pane_width)


class RecheckPromptShapeTests(unittest.TestCase):
    def test_every_recheck_prompt_is_one_provable_line(self):
        """The proof matches the composer against the prompt exactly, and a
        display wrap consumes exactly one space: the prompt must be one
        single-spaced line (the sitrep request-line rule)."""
        from monitor import agent_request_delivery as d
        for phase in ("PLAN", "IMPLEMENT", "POSTIMPL", None, "bogus"):
            for rnd in (None, 0, 1, 2, 99):
                prompt = rl.compose_recheck_prompt(phase, rnd)
                with self.subTest(phase=phase, round=rnd):
                    self.assertEqual(d.request_line_error(prompt), "")


class ComposerRenderTests(unittest.TestCase):
    def test_the_wrap_reproduces_every_genuine_capture(self):
        checked = 0
        for name, (agent, width, _state, request, raw) in sorted(FIXTURES.items()):
            payload = rl.composer_payload(raw, agent, width)
            if payload is None or not s.payload_matches(payload, request):
                continue
            checked += 1
            with self.subTest(name):
                rows = composer_render.wrap_rows(
                    request, payload.content_width, payload.wrap_width,
                    payload.hyphen_breaks, composer_render.FILL_LONG.get(agent, False))
                self.assertEqual(tuple(rows), payload.lines)
        self.assertGreaterEqual(checked, 90, "the fixture set shrank")

    def test_a_rendered_composer_is_provably_the_text(self):
        for agent in rl.PAYLOAD_GRAMMAR_AGENTS:
            for width in WIDTHS:
                for phase in ("PLAN", "IMPLEMENT", None):
                    for rnd in (1, 2, 12):
                        text = rl.compose_recheck_prompt(phase, rnd)
                        with self.subTest(agent=agent, width=width, phase=phase, round=rnd):
                            raw = composer_render.render(agent, width, text)
                            self.assertEqual(rl.shadow_state(raw, agent), rl.SHADOW_BUSY)
                            self.assertTrue(s.payload_matches(
                                rl.composer_payload(raw, agent, width), text))
                            self.assertFalse(s.payload_matches(
                                rl.composer_payload(raw, agent, width), text + " x"))


if __name__ == "__main__":
    unittest.main()
