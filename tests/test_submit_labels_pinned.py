#!/usr/bin/env python3
"""Characterization of both agent-submit callers' result labels (t2275).

``monitor/agent_submit.py`` owns the one submit sequence (drain, the pre-Enter
composer proof, the pane-mode read as the last read before every Enter, the
Enter, the post-Enter verification, the bounded retry). Its two callers keep
their OWN result vocabularies:

* the minimonitor's ``_submit_shadow_prompt`` returns ``('sent' | 'not_ready' |
  'failed', code)`` and re-checks its delivery token after the attempt's last
  await;
* ``agent_request_delivery.deliver_sitrep_request`` returns a
  ``DeliveryResult`` (``code``, ``detail``).

This table pins every outcome branch of both, one row per branch, over a
scripted fake that is independent of the big ``_LoopFakeMon`` in
``test_minimonitor_concern_action.py`` (so a change to that fake cannot mask a
behaviour change here). It was run green on the pre-refactor HEAD and stays
green through the refactor; the ONLY rows whose labels changed are the t2274
rows (the minimonitor gained the composer payload proof the sitrep path already
had). Each such row carries its pre-refactor label in ``old``; the plan
(aiplans/archived/p2275_*.md) records the HEAD run.

Run: python3 tests/test_submit_labels_pinned.py
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from typing import NamedTuple

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent / ".aitask-scripts"
for _p in (str(_HERE), str(_SCRIPTS), str(_SCRIPTS / "lib"), str(_SCRIPTS / "board")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import review_loop_fixtures as rlf  # noqa: E402
from shadow_recheck_fixtures import FIXTURES as SHADOW_FX  # noqa: E402
from sitrep_request_fixtures import FIXTURES as SITREP_FX  # noqa: E402
import test_sitrep_request_delivery as srd  # noqa: E402  (its FakeMon / target)

from monitor import agent_request_delivery as d  # noqa: E402
from monitor import minimonitor_app as mm  # noqa: E402
from monitor import review_loop as rl  # noqa: E402


# -- minimonitor --------------------------------------------------------------------

SHADOW = "%5"
W = 60
PROMPT = rl.compose_recheck_prompt("PLAN", 1)
TYPED = SHADOW_FX["claude_w60_recheck_plan"][4]          # exactly PROMPT
APPENDED = SHADOW_FX["claude_w60_appended"][4]           # PROMPT + user words
DRAFT = SHADOW_FX["claude_w60_history_draft"][4]         # a foreign draft
POST = SHADOW_FX["claude_w60_post_enter"][4]             # working
NARROW = SHADOW_FX["claude_w44_recheck_plan"][4]         # BUSY, unprovable at 60
REST = rlf.CLAUDE_AT_REST_RAW
DIALOG = rlf.CLAUDE_DIALOG_RAW
WORKING = rlf.CLAUDE_STREAMING_RAW
FAIL = None                                              # a failed capture

assert SHADOW_FX["claude_w60_recheck_plan"][3] == PROMPT


class _Ctrl:
    def __init__(self):
        self.valid = True

    def delivery_valid(self, token):
        return self.valid and token == "tok"


class _Host:
    """The ``self`` ``_submit_shadow_prompt`` needs: the controller, the
    delivery-detail slot and ``notify``."""

    def __init__(self):
        self._review_loop = _Ctrl()
        self._loop_delivery_detail = {}
        self.notes = []

    def notify(self, msg, severity="information"):
        self.notes.append((severity, msg))


class _MmFake:
    """Scripted shadow pane: ``tails`` per capture, ``modes`` per mode read
    (True / False / None = unreadable), ``sends`` per send_keys result."""

    def __init__(self, tails, modes, sends=(), width=W, invalidate=None, host=None):
        self.tails = list(tails)
        self.modes = list(modes)
        self.sends = list(sends)
        self.width = width
        self.invalidate = invalidate      # ("capture" | "mode", n): disarm at the n-th
        self.host = host
        self.counts = {"capture": 0, "mode": 0}
        self.enters = 0

    def _tick(self, kind):
        self.counts[kind] += 1
        if self.invalidate == (kind, self.counts[kind]):
            self.host._review_loop.valid = False

    async def tmux_run_async(self, args, timeout=5.0):
        await asyncio.sleep(0)
        if args[0] == "capture-pane":
            self._tick("capture")
            tail = self.tails.pop(0) if self.tails else FAIL
            return (1, "") if tail is None else (0, tail)
        fmt = args[-1]
        if "pane_in_mode" in fmt:
            self._tick("mode")
            m = self.modes.pop(0) if self.modes else None
            return (1, "") if m is None else (0, f"{SHADOW}\t{1 if m else 0}\tcopy-mode\n")
        if "pane_width" in fmt:
            return 0, f"{SHADOW}\t{self.width}\n"
        return 1, ""

    def send_keys(self, pane, keys, literal=False):
        assert pane == SHADOW and keys == "Enter" and not literal
        self.enters += 1
        return self.sends.pop(0) if self.sends else True


class MmRow(NamedTuple):
    name: str
    tails: tuple
    modes: tuple
    expect: tuple                 # (outcome, code, enters, warned)
    sends: tuple = ()
    width: int = W
    invalidate: object = None
    old: object = None            # t2274 rows: the pre-refactor label


SENT = ("sent", "<prompt>")

MM_ROWS = (
    MmRow("submitted", (TYPED, POST), (False,), (*SENT, 1, False)),
    MmRow("swallowed_then_submitted", (TYPED, TYPED, TYPED, POST), (False, False),
          (*SENT, 2, False)),
    MmRow("exhausted", (TYPED,) * 4, (False, False),
          ("failed", rl.DISARM_SUBMIT_UNCONFIRMED, 2, False)),
    MmRow("pre_dialog", (DIALOG,), (False,), ("not_ready", rl.HOLD_PRE_ENTER_DIALOG, 0, False)),
    MmRow("pre_unreadable", (FAIL,), (False,),
          ("not_ready", rl.HOLD_PRE_ENTER_UNREADABLE, 0, False)),
    MmRow("pre_ready", (REST,), (False,), ("failed", rl.DISARM_TEXT_NOT_IN_COMPOSER, 0, False)),
    MmRow("pre_working", (WORKING,), (False,),
          ("failed", rl.DISARM_TEXT_NOT_IN_COMPOSER, 0, False)),
    MmRow("pre_mode_unreadable", (TYPED,), (None,),
          ("not_ready", rl.HOLD_PRE_ENTER_MODE_UNREADABLE, 0, False)),
    MmRow("pre_in_mode", (TYPED,), (True,), ("not_ready", rl.HOLD_PRE_ENTER_IN_MODE, 0, False)),
    MmRow("enter_send_failed", (TYPED,), (False,),
          ("failed", rl.DISARM_ENTER_SEND_FAILED, 1, False), sends=(False,)),
    MmRow("post_dialog", (TYPED, DIALOG), (False,), (*SENT, 1, True)),
    MmRow("post_unreadable", (TYPED, FAIL), (False,), (*SENT, 1, True)),
    MmRow("retry_pre_ready", (TYPED, TYPED, REST), (False, False),
          ("failed", rl.DISARM_TEXT_NOT_IN_COMPOSER, 1, False)),
    MmRow("retry_in_mode", (TYPED, TYPED, TYPED), (False, True),
          ("not_ready", rl.HOLD_PRE_ENTER_IN_MODE, 1, False)),
    # supersession (t2001 / t2009)
    MmRow("superseded_during_pre_enter_reads", (TYPED, POST), (False,),
          ("not_ready", rl.HOLD_DELIVERY_SUPERSEDED, 0, False), invalidate=("mode", 1)),
    MmRow("superseded_during_last_post_capture", (TYPED,) * 4, (False, False),
          ("not_ready", rl.HOLD_DELIVERY_SUPERSEDED, 2, False), invalidate=("capture", 4)),
    MmRow("non_busy_post_read_after_disarm_is_sent", (TYPED, POST), (False,),
          (*SENT, 1, False), invalidate=("capture", 2)),
    # t2274: the composer payload proof
    MmRow("t2274_appended_text", (APPENDED, POST), (False,),
          ("not_ready", rl.HOLD_PRE_ENTER_COMPOSER_CHANGED
           if hasattr(rl, "HOLD_PRE_ENTER_COMPOSER_CHANGED") else "?", 0, False),
          old=(*SENT, 1, False)),
    MmRow("t2274_unprovable_composer", (NARROW, POST), (False,),
          ("not_ready", rl.HOLD_PRE_ENTER_COMPOSER_UNPROVABLE
           if hasattr(rl, "HOLD_PRE_ENTER_COMPOSER_UNPROVABLE") else "?", 0, False),
          old=(*SENT, 1, False)),
    MmRow("t2274_foreign_draft_after_enter", (TYPED, DRAFT, DRAFT, POST), (False, False),
          (*SENT, 1, True), old=(*SENT, 2, False)),
    MmRow("t2274_unprovable_after_enter", (TYPED, NARROW, NARROW, POST), (False, False),
          (*SENT, 1, True), old=(*SENT, 2, False)),
    # The RETRY's pre-Enter read, after a swallowed-looking Enter: one Enter is
    # already out, so this is never a "nothing submitted" pre-submission hold.
    MmRow("t2274_retry_pre_read_changed", (TYPED, TYPED, DRAFT, POST), (False, False),
          (*SENT, 1, True), old=(*SENT, 2, False)),
    MmRow("t2274_retry_pre_read_unprovable", (TYPED, TYPED, NARROW, POST), (False, False),
          (*SENT, 1, True), old=(*SENT, 2, False)),
)


async def _no_drain(_seconds):
    return None


def run_mm(row: MmRow):
    """``(outcome, code, enters, warned)`` plus the delivery-detail keys."""
    host = _Host()
    mon = _MmFake(row.tails, row.modes, row.sends, row.width, row.invalidate, host)
    orig = mm._composer_drain
    mm._composer_drain = _no_drain
    try:
        outcome, code = asyncio.run(mm.MiniMonitorApp._submit_shadow_prompt(
            host, mon, SHADOW, "claude", PROMPT, "tok"))
    finally:
        mm._composer_drain = orig
    if outcome == "sent" and code == PROMPT:
        code = "<prompt>"
    warned = any(sev == "warning" for sev, _m in host.notes)
    return (outcome, code, mon.enters, warned), set(host._loop_delivery_detail)


DETAIL_KEYS = {"pane_in_mode", "pane_mode", "pre_enter_verdict"}


class MinimonitorLabelTests(unittest.TestCase):
    def test_every_branch(self):
        for row in MM_ROWS:
            with self.subTest(row.name):
                got, keys = run_mm(row)
                self.assertEqual(got, row.expect)
                self.assertEqual(keys, DETAIL_KEYS, "every outcome carries the mode reading")

    def test_only_the_t2274_rows_changed(self):
        for row in MM_ROWS:
            self.assertEqual(row.old is not None, row.name.startswith("t2274_"), row.name)
            if row.old is not None:
                self.assertNotEqual(row.old, row.expect, row.name)


# -- sitrep delivery -----------------------------------------------------------------

S_REST = srd.REST
SHORT = srd.SHORT
S_POST = srd.POST_ENTER
S_APPENDED = srd.APPENDED
S_DRAFT = SITREP_FX["claude_history_draft"][4]


class SrRow(NamedTuple):
    name: str
    tails: tuple
    modes: tuple
    acks: tuple
    expect: tuple                 # (code, detail, enters)
    width: int = 120
    reason_line: object = None


# Readiness: two REST captures + one mode read (False); the paste ack "sent".
_R = (S_REST, S_REST)
SR_ROWS = (
    SrRow("submitted", _R + (SHORT, S_POST), (False, False), ("sent", "sent"),
          (d.SUBMITTED, "", 1)),
    SrRow("swallowed_then_submitted", _R + (SHORT, SHORT, SHORT, S_POST),
          (False, False, False), ("sent",) * 3, (d.SUBMITTED, "", 2)),
    SrRow("exhausted", _R + (SHORT,) * 4, (False,) * 3, ("sent",) * 3,
          (d.TYPED, "submit_unconfirmed", 2)),
    SrRow("pre_dialog", _R + (rlf.CLAUDE_DIALOG_RAW,), (False,), ("sent",),
          (d.UNKNOWN, "pre_enter_dialog", 0)),
    SrRow("pre_unreadable", _R, (False,), ("sent",), (d.UNKNOWN, "pre_enter_unreadable", 0)),
    SrRow("pre_ready", _R + (S_REST,), (False,), ("sent",),
          (d.UNKNOWN, "text_not_in_composer", 0)),
    SrRow("pre_unprovable", _R + (SHORT,), (False,), ("sent",),
          (d.UNKNOWN, "composer_unprovable", 0), width=100),
    SrRow("pre_changed", _R + (S_APPENDED,), (False, False), ("sent",),
          (d.TYPED, "composer_changed", 0)),
    SrRow("retry_changed", _R + (SHORT, SHORT, S_DRAFT), (False,) * 3, ("sent",) * 3,
          (d.UNKNOWN, "composer_changed_after_enter", 1)),
    SrRow("pre_mode_unreadable", _R + (SHORT,), (False, None), ("sent",),
          (d.TYPED_MODE_UNREADABLE, "", 0)),
    SrRow("pre_in_mode", _R + (SHORT,), (False, True), ("sent",), (d.TYPED_IN_MODE, "", 0)),
    SrRow("enter_skipped_in_mode", _R + (SHORT,), (False, False), ("sent", "skipped"),
          (d.TYPED_IN_MODE, "enter_skipped", 1)),
    SrRow("enter_skipped_identity", _R + (SHORT,), (False, False), ("sent", "skipped"),
          (f"refused:{d.R_IDENTITY_CHANGED}", "enter_skipped", 1),
          reason_line=f"{srd.PANE}\t5\t{srd.SERVER}\t\t0\n"),
    SrRow("enter_unacknowledged", _R + (SHORT,), (False, False), ("sent", "unknown"),
          (d.UNKNOWN, "enter_unacknowledged", 1)),
    SrRow("post_dialog", _R + (SHORT, rlf.CLAUDE_DIALOG_RAW), (False, False), ("sent",) * 2,
          (d.UNKNOWN, "post_enter_dialog", 1)),
    SrRow("post_unreadable", _R + (SHORT,), (False, False), ("sent",) * 2,
          (d.UNKNOWN, "post_enter_unknown", 1)),
    SrRow("post_changed", _R + (SHORT, S_DRAFT), (False, False), ("sent",) * 2,
          (d.UNKNOWN, "composer_changed_after_enter", 1)),
)


async def _nosleep(_s):
    return None


def run_sr(row: SrRow):
    mon = srd.FakeMon(list(row.tails), modes=list(row.modes), acks=list(row.acks),
                      width=row.width, reason_line=row.reason_line)
    counter = iter(range(1, 100))

    async def go():
        return await d.deliver_sitrep_request(
            mon, srd.ROOT, srd.REQ, roles=lambda m, r: (True, srd.PANE, None),
            resolve_agent=lambda t: "claude", sleep=_nosleep,
            nonce=lambda: f"{next(counter):016x}")

    res = asyncio.run(go())
    return (res.code, res.detail, mon.events.count("enter"))


class SitrepLabelTests(unittest.TestCase):
    def test_every_branch(self):
        for row in SR_ROWS:
            with self.subTest(row.name):
                self.assertEqual(run_sr(row), row.expect)


if __name__ == "__main__":
    unittest.main()
