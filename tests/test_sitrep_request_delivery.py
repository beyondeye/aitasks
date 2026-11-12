#!/usr/bin/env python3
"""Guarded request delivery into the sitrep agent (t2211_4) — pure / FakeMon.

What is pinned here, without a tmux server (the live counterpart is
``tests/test_sitrep_request_delivery_live.sh``):

``ReadinessVerdictTests``
    The refusal table per ``shadow_state`` verdict, over the review_loop
    fixture captures (dialog, typed draft, streaming, failed capture), plus an
    unstable hash and an unreadable / active mode.

``DispatchAckTests`` / ``GuardedDispatchTests``
    ``dispatch_ack_state`` is ``sent`` only for the same pane, server and
    nonce; every mismatch is ``unknown``. The built condition carries the
    identity terms AND the ``pane_in_mode`` conjunct, the payload travels only
    on stdin, the guarded branches hold controlled tokens only, and no buffer
    survives a non-``sent`` dispatch.

``ComposerProofTests``
    The pre-Enter proof is the current composer's COMPLETE payload, over the
    real captures in ``tests/sitrep_request_fixtures.py``: every genuine
    request (wrapped or not) matches; the request with user text appended,
    and the request echoed in history beside a foreign draft, never match.
    A pre-fix control shows the rejected design (an occurrence count over the
    capture) accepting both — the fixtures exercise the hazard.

``OrchestratorTests``
    ``deliver_sitrep_request`` over a recording FakeMon: the phase order, every
    result branch, the per-attempt proof (no Enter on changed text, exactly one
    Enter when a foreign draft follows a submit), and the agent + identity
    re-read on every call.

Run: python3 tests/test_sitrep_request_delivery.py
"""

from __future__ import annotations

import asyncio
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / ".aitask-scripts"
for _p in (str(Path(__file__).resolve().parent), str(SCRIPTS), str(SCRIPTS / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import review_loop_fixtures as rlf  # noqa: E402
from sitrep_request_fixtures import FIXTURES  # noqa: E402

from monitor import agent_request_delivery as d  # noqa: E402
from monitor import monitor_core as mc  # noqa: E402
from monitor import review_loop as rl  # noqa: E402
from monitor.ansi_utils import strip_ansi  # noqa: E402

PANE = "%7"
PID = "4242"
SERVER = "999"
ROOT = "/tmp/fake-root"

REST = rlf.CLAUDE_AT_REST_RAW
SHORT = FIXTURES["claude_short"][4]           # ">t c12" in the composer, width 120
POST_ENTER = FIXTURES["claude_post_enter"][4]  # working
APPENDED = FIXTURES["claude_appended"][4]      # ">t c12 plus my own words"
HISTORY_DRAFT = FIXTURES["claude_history_draft"][4]
REQ = ">t c12"


def fx(name):
    agent, width, _state, request, raw = FIXTURES[name]
    return agent, width, request, raw


# -- readiness ---------------------------------------------------------------------

class ReadinessVerdictTests(unittest.TestCase):
    def v(self, t1, t2=None, agent="claude", mode=False):
        return d.readiness_verdict(t1, t1 if t2 is None else t2, agent, mode)

    def test_the_refusal_table(self):
        self.assertEqual(self.v(REST), d.READY)
        self.assertEqual(self.v(rlf.CLAUDE_DIALOG_RAW), d.NOT_READY_DIALOG)
        self.assertEqual(self.v(rlf.CLAUDE_TYPED_RAW), d.NOT_READY_DRAFT)
        self.assertEqual(self.v(rlf.CLAUDE_STREAMING_RAW), d.NOT_READY_WORKING)
        self.assertEqual(self.v(""), d.NOT_READY_UNKNOWN)

    def test_a_failed_capture_or_an_agent_without_a_detector_is_unknown(self):
        self.assertEqual(d.readiness_verdict(None, REST, "claude", False), d.NOT_READY_UNKNOWN)
        self.assertEqual(d.readiness_verdict(REST, None, "claude", False), d.NOT_READY_UNKNOWN)
        self.assertEqual(self.v(REST, agent="gemini"), d.NOT_READY_UNKNOWN)

    def test_either_tail_decides_and_a_dialog_outranks_a_draft(self):
        self.assertEqual(self.v(REST, rlf.CLAUDE_DIALOG_RAW), d.NOT_READY_DIALOG)
        self.assertEqual(self.v(rlf.CLAUDE_TYPED_RAW, REST), d.NOT_READY_DRAFT)
        self.assertEqual(self.v(rlf.CLAUDE_TYPED_RAW, rlf.CLAUDE_DIALOG_RAW),
                         d.NOT_READY_DIALOG)

    def test_an_unstable_hash_is_working(self):
        moved = REST.replace("23%", "24%")
        self.assertNotEqual(moved, REST)
        self.assertEqual(rl.shadow_state(moved, "claude"), rl.SHADOW_READY)
        self.assertEqual(self.v(REST, moved), d.NOT_READY_WORKING)

    def test_the_mode(self):
        self.assertEqual(self.v(REST, mode=True), d.NOT_READY_IN_MODE)
        self.assertEqual(self.v(REST, mode=None), d.NOT_READY_MODE_UNREADABLE)


# -- dispatch ack + guarded dispatch --------------------------------------------------

NONCE = "abcdef0123456789"


class DispatchAckTests(unittest.TestCase):
    def s(self, out, rc=0, pane=PANE, server=SERVER, nonce=NONCE):
        return mc.dispatch_ack_state(rc, out, pane, server, nonce)

    def test_sent_and_skipped(self):
        self.assertEqual(self.s(f"{PANE}\t{SERVER}\t{NONCE}:sent"), mc.DISPATCH_SENT)
        self.assertEqual(self.s(f"{PANE}\t{SERVER}\t{NONCE}:skipped\n"), mc.DISPATCH_SKIPPED)

    def test_every_mismatch_is_unknown_never_sent(self):
        good = f"{PANE}\t{SERVER}\t{NONCE}:sent"
        cases = {
            "rc": (good, 1, PANE, SERVER, NONCE),
            "transport": (good, -1, PANE, SERVER, NONCE),
            "another pane": (f"%8\t{SERVER}\t{NONCE}:sent", 0, PANE, SERVER, NONCE),
            "pane gone": (f"\t{SERVER}\t", 0, PANE, SERVER, NONCE),
            "another server": (f"{PANE}\t1000\t{NONCE}:sent", 0, PANE, SERVER, NONCE),
            "another nonce": (f"{PANE}\t{SERVER}\tffff0000ffff0000:sent", 0, PANE, SERVER, NONCE),
            "no ack": (f"{PANE}\t{SERVER}\t", 0, PANE, SERVER, NONCE),
            "short read": (f"{PANE}\t{SERVER}", 0, PANE, SERVER, NONCE),
            "long read": (good + "\textra", 0, PANE, SERVER, NONCE),
            "garbled ack": (f"{PANE}\t{SERVER}\t{NONCE}:sentx", 0, PANE, SERVER, NONCE),
            "bad nonce": (f"{PANE}\t{SERVER}\t:sent", 0, PANE, SERVER, ""),
        }
        for name, (out, rc, pane, server, nonce) in cases.items():
            with self.subTest(name):
                self.assertEqual(mc.dispatch_ack_state(rc, out, pane, server, nonce),
                                 mc.DISPATCH_UNKNOWN)


class FakeRun:
    """A `monitor` for the guarded dispatch alone: records argv, answers the
    read-backs with a scripted branch."""

    def __init__(self, branch="sent", load_rc=0, reason_line=None):
        self.branch = branch
        self.load_rc = load_rc
        self.calls = []
        self.stdin = []
        self.reason_line = reason_line
        self._nonce = ""

    def tmux_run(self, args, timeout=5.0):
        self.calls.append(list(args))
        if args[0] == "if-shell":
            m = re.search(r"@aitask_dispatch_ack ([0-9a-f]+):sent", args[5])
            self._nonce = m.group(1) if m else ""
            return 0, ""
        if args[0] == "display-message" and args[-1] == mc.DISPATCH_ACK_FORMAT:
            if self.branch == "unknown":
                return 1, ""
            return 0, f"{args[3]}\t{SERVER}\t{self._nonce}:{self.branch}\n"
        if args[0] == "display-message":
            return 0, self.reason_line or f"{args[3]}\t{PID}\t{SERVER}\t\t1\n"
        return 0, ""

    def tmux_run_input(self, args, data, timeout=5.0):
        self.calls.append(list(args))
        self.stdin.append(data)
        return self.load_rc, ""

    def verbs(self):
        return [c[0] for c in self.calls]


HOSTILE = ">q c1 a;b \"d\" 'e' #{pane_id} $(echo x) \\; ; set-buffer -b ait-injected x;"
IDENT = mc.RunIdentity(PANE, PID, SERVER, "")


class GuardedDispatchTests(unittest.TestCase):
    def test_the_condition_carries_the_identity_and_the_mode_conjunct(self):
        cond = mc.dispatch_condition(IDENT)
        for term in ("#{==:#{@aitask_frozen},}", f"#{{==:#{{pane_pid}},{PID}}}",
                     f"#{{==:#{{pid}},{SERVER}}}", "#{==:#{pane_in_mode},0}"):
            self.assertIn(term, cond)
        with self.assertRaises(ValueError):
            mc.dispatch_condition(mc.RunIdentity(PANE, "12; kill", SERVER, ""))

    def test_the_text_travels_on_stdin_only_and_the_branches_hold_controlled_tokens(self):
        run = FakeRun()
        self.assertEqual(mc.guarded_paste_text(run, IDENT, HOSTILE, NONCE),
                         (mc.DISPATCH_SENT, ""))
        self.assertEqual(run.stdin, [HOSTILE])
        for argv in run.calls:
            for arg in argv:
                self.assertNotIn("ait-injected", arg, argv)
        self.assertEqual(run.calls[0], ["load-buffer", "-b", f"aitask-sitrep-{NONCE}", "-"])
        ifs = run.calls[1]
        self.assertEqual(ifs[:5], ["if-shell", "-F", "-t", PANE, mc.dispatch_condition(IDENT)])
        self.assertRegex(ifs[5], r"^paste-buffer -d -b aitask-sitrep-[0-9a-f]+ -t %[0-9]+ ; "
                                 r"set-option -p -t %[0-9]+ @aitask_dispatch_ack [0-9a-f]+:sent$")
        self.assertRegex(ifs[6], r"^delete-buffer -b aitask-sitrep-[0-9a-f]+ ; "
                                 r"set-option -p -t %[0-9]+ @aitask_dispatch_ack "
                                 r"[0-9a-f]+:skipped$")
        self.assertIn(["set-option", "-pu", "-t", PANE, mc.DISPATCH_ACK_OPTION], run.calls)
        self.assertNotIn("delete-buffer", run.verbs())       # the paste deleted it

    def test_no_buffer_survives_a_skip_or_an_unknown(self):
        for branch in ("skipped", "unknown"):
            with self.subTest(branch):
                run = FakeRun(branch)
                state, _ = mc.guarded_paste_text(run, IDENT, "hello", NONCE)
                self.assertEqual(state, branch)
                self.assertIn(["delete-buffer", "-b", f"aitask-sitrep-{NONCE}"], run.calls)

    def test_the_skip_reason(self):
        run = FakeRun("skipped")                              # same identity, in a mode
        self.assertEqual(mc.guarded_paste_text(run, IDENT, "hi", NONCE),
                         (mc.DISPATCH_SKIPPED, mc.SKIP_IN_MODE))
        run = FakeRun("skipped", reason_line=f"{PANE}\t5555\t{SERVER}\t\t0\n")
        self.assertEqual(mc.guarded_paste_text(run, IDENT, "hi", NONCE),
                         (mc.DISPATCH_SKIPPED, mc.SKIP_IDENTITY_CHANGED))
        run = FakeRun("skipped", reason_line=f"{PANE}\t{PID}\t{SERVER}\t3\t0\n")
        self.assertEqual(mc.guarded_send_key(run, IDENT, "Enter", NONCE),
                         (mc.DISPATCH_SKIPPED, mc.SKIP_IDENTITY_CHANGED))

    def test_nothing_is_dispatched_for_malformed_input(self):
        for ident, text, nonce in ((mc.RunIdentity("5", PID, SERVER, ""), "x", NONCE),
                                   (mc.RunIdentity(PANE, "x", SERVER, ""), "x", NONCE),
                                   (IDENT, "x", "NOT-HEX!"), (IDENT, "", NONCE)):
            run = FakeRun()
            self.assertEqual(mc.guarded_paste_text(run, ident, text, nonce)[0],
                             mc.DISPATCH_FAILED)
            self.assertEqual(run.calls, [])
        run = FakeRun()
        self.assertEqual(mc.guarded_send_key(run, IDENT, "C-c", NONCE)[0], mc.DISPATCH_FAILED)
        self.assertEqual(run.calls, [])

    def test_a_failed_buffer_load_dispatches_nothing_and_cleans_up(self):
        run = FakeRun(load_rc=1)
        self.assertEqual(mc.guarded_paste_text(run, IDENT, "hi", NONCE),
                         (mc.DISPATCH_FAILED, "buffer_failed"))
        self.assertNotIn("if-shell", run.verbs())
        self.assertIn(["delete-buffer", "-b", f"aitask-sitrep-{NONCE}"], run.calls)

    def test_the_enter_dispatch(self):
        run = FakeRun()
        self.assertEqual(mc.guarded_send_key(run, IDENT, "Enter", NONCE), (mc.DISPATCH_SENT, ""))
        ifs = next(c for c in run.calls if c[0] == "if-shell")
        self.assertEqual(ifs[4], mc.dispatch_condition(IDENT))
        self.assertRegex(ifs[5], r"^send-keys -t %[0-9]+ Enter ; set-option -p -t %[0-9]+ "
                                 r"@aitask_dispatch_ack [0-9a-f]+:sent$")
        self.assertRegex(ifs[6], r"^set-option -p -t %[0-9]+ @aitask_dispatch_ack "
                                 r"[0-9a-f]+:skipped$")

    def test_the_monitor_methods_delegate(self):
        mon = mc.TmuxMonitor("s")
        run = FakeRun()
        mon.tmux_run = run.tmux_run
        mon.tmux_run_input = run.tmux_run_input
        self.assertEqual(mon.dispatch_text_guarded(IDENT, "hi", NONCE), (mc.DISPATCH_SENT, ""))
        self.assertEqual(mon.dispatch_key_guarded(IDENT, "Enter", NONCE), (mc.DISPATCH_SENT, ""))
        self.assertEqual(run.stdin, ["hi"])

    def test_run_with_input_sends_the_data_on_stdin(self):
        from tmux_exec import TmuxClient
        client = TmuxClient(socket_args=["-L", "nope"])
        done = mock.Mock(returncode=0, stdout="ok")
        with mock.patch("tmux_exec.subprocess.run", return_value=done) as run:
            self.assertEqual(client.run_with_input(["load-buffer", "-b", "x", "-"], "a;"),
                             (0, "ok"))
        kwargs = run.call_args.kwargs
        self.assertEqual(kwargs["input"], "a;")
        self.assertEqual(kwargs["encoding"], "utf-8")
        self.assertNotIn("a;", run.call_args.args[0])


# -- the target -----------------------------------------------------------------------

def target_line(pane=PANE, pid=PID, frozen="", tui="", stamp=ROOT, dead="0", cmd="claude"):
    return f"{pane}\t{pid}\t{SERVER}\t{frozen}\t{tui}\t{stamp}\t{dead}\t{cmd}\n"


class ParseTargetTests(unittest.TestCase):
    def test_a_stamped_live_pane_is_the_target(self):
        t = d.parse_target(0, target_line(), PANE, ROOT)
        self.assertEqual(t.refusal, "")
        self.assertEqual(t.identity, mc.RunIdentity(PANE, PID, SERVER, "", ""))
        self.assertEqual(t.command, "claude")

    def test_every_other_pane_is_refused(self):
        cases = {
            "frozen": (target_line(frozen="rec1"), d.R_FROZEN),
            "the TUI": (target_line(tui=ROOT), d.R_NO_AGENT),
            "unstamped (name+cwd fallback)": (target_line(stamp=""), d.R_NO_AGENT),
            "another root": (target_line(stamp="/elsewhere"), d.R_NO_AGENT),
            "dead": (target_line(dead="1"), d.R_NO_AGENT),
            "vanished": (target_line(pane=""), d.R_NO_AGENT),
            "short": (f"{PANE}\t{PID}\t{SERVER}\n", d.R_NO_AGENT),
            "bad pid": (target_line(pid="x"), d.R_NO_AGENT),
        }
        for name, (line, want) in cases.items():
            with self.subTest(name):
                self.assertEqual(d.parse_target(0, line, PANE, ROOT).refusal, want)
        self.assertEqual(d.parse_target(1, target_line(), PANE, ROOT).refusal, d.R_NO_AGENT)


# -- the composer proof ----------------------------------------------------------------

GENUINE = sorted(n for n in FIXTURES
                 if not n.endswith(("_appended", "_history_draft", "_post_enter", "_at_end")))
REJECTED = sorted(n for n in FIXTURES if n.endswith(("_appended", "_history_draft")))


def _occurrence_count_proof(after, before, text):
    """The REJECTED design (pre-fix control): the request occurs more often in
    the whole capture than before the paste."""
    def squash(s):
        return re.sub(r"[\s│┃]+", "", strip_ansi(s or ""))
    needle = squash(text)
    return squash(after).count(needle) > squash(before).count(needle)


class ComposerProofTests(unittest.TestCase):
    def test_every_genuine_capture_matches_its_request(self):
        self.assertGreaterEqual(len(GENUINE), 30)
        for name in GENUINE:
            agent, width, request, raw = fx(name)
            with self.subTest(name):
                payload = rl.composer_payload(raw, agent, width)
                self.assertIsNotNone(payload)
                self.assertTrue(d.payload_matches(payload, request), payload)

    def test_appended_text_and_a_foreign_draft_never_match(self):
        self.assertEqual(len(REJECTED), 7)
        for name in REJECTED:
            agent, width, request, raw = fx(name)
            with self.subTest(name):
                payload = rl.composer_payload(raw, agent, width)
                self.assertIsNotNone(payload, "a delimited composer, just not ours")
                self.assertFalse(d.payload_matches(payload, request))
                # the request IS on screen in the history case: a search would find it
                if name.endswith("_history_draft"):
                    self.assertIn(request, strip_ansi(raw))

    def test_pre_fix_control_the_occurrence_count_accepts_both(self):
        self.assertTrue(_occurrence_count_proof(APPENDED, REST, REQ))
        _a, _w, req, raw = fx("claude_history_draft")
        self.assertTrue(_occurrence_count_proof(raw, REST, req))
        _a, _w, req, raw = fx("codex_history_draft")
        self.assertTrue(_occurrence_count_proof(raw, rlf.CODEX_AT_REST_RAW, req))

    def test_wraps_must_be_justified(self):
        P = rl.ComposerPayload
        words = ">q c12 " + " ".join(f"word{i:02d}" for i in range(30))
        ok = rl.composer_payload(FIXTURES["claude_wordwrap"][4], "claude", 120)
        self.assertTrue(d.payload_matches(ok, words))
        early = P((">q c12 word00", words[len(">q c12 word00 "):]), 116, 116)
        self.assertFalse(d.payload_matches(early, words), "a break the next word fitted in")
        self.assertFalse(d.payload_matches(P((">q c12 ab", "cd"), 116, 116), ">q c12 abcd"),
                         "a mid-token break on a short row")
        self.assertTrue(d.payload_matches(P(("a" * 116, "bc"), 116, 116), "a" * 116 + "bc"))
        self.assertFalse(d.payload_matches(P(("a" * 115, "bc"), 116, 116), "a" * 115 + "bc"))
        self.assertFalse(d.payload_matches(P((">t c12",), 116, 116), ">t c1"), "leftover row")
        self.assertFalse(d.payload_matches(P((">t c1",), 116, 116), ">t c12"), "leftover text")
        self.assertFalse(d.payload_matches(P((">t", "c12", "x"), 4, 4), ">t c12"), "extra row")
        self.assertFalse(d.payload_matches(None, ">t c12"))

    def test_opencode_wraps_one_column_short_of_a_hard_break(self):
        """...for a word followed by a space (edge_50_69/70 shape). A FINAL word
        keeps to the row up to the content width itself -- measured live at
        60, 44 and 120 columns (t2280, opencode_w*_endword_*) -- so a break
        before it at 70 is a typed newline, not a wrap."""
        P = rl.ComposerPayload
        text = "a" * 50 + " " + "b" * 18 + " tail"      # 50 + 1 + 18 = 69 = wrap width
        self.assertFalse(d.payload_matches(P(("a" * 50, "b" * 18 + " tail"), 70, 69), text))
        text = "a" * 50 + " " + "b" * 19 + " tail"      # 70 > 69: justified
        self.assertTrue(d.payload_matches(P(("a" * 50, "b" * 19 + " tail"), 70, 69), text))
        text = "a" * 50 + " " + "b" * 19                # final word: 70 = content width, fits
        self.assertFalse(d.payload_matches(P(("a" * 50, "b" * 19), 70, 69), text))
        text = "a" * 50 + " " + "b" * 20                # 71 > 70: justified
        self.assertTrue(d.payload_matches(P(("a" * 50, "b" * 20), 70, 69), text))

    def test_the_payload_is_unprovable_unless_the_region_is_exact(self):
        claude_short = FIXTURES["claude_short"][4]
        plain = strip_ansi(claude_short).splitlines()
        idx = next(i for i, ln in enumerate(plain) if ln.startswith("❯ "))
        no_close = "\n".join(plain[:idx + 1])
        stray = "\n".join(plain[:idx + 1] + ["x stray row"] + plain[idx + 1:])
        cases = {
            "the dim hint (an empty composer)": (REST, "claude", 100),
            "a dialog": (rlf.CLAUDE_DIALOG_RAW, "claude", 100),
            "no closing rule": (no_close, "claude", 120),
            "a stray row inside": (stray, "claude", 120),
            "a resize (rule != pane width)": (claude_short, "claude", 100),
            "codex without a pane width": (FIXTURES["codex_short"][4], "codex", None),
            "an agent with no measured grammar": (claude_short, "gemini", 120),
            "opencode's file suggestions": (FIXTURES["opencode_at_end"][4], "opencode", 120),
            "a working pane": (POST_ENTER, "claude", 120),
        }
        for name, (raw, agent, width) in cases.items():
            with self.subTest(name):
                self.assertIsNone(rl.composer_payload(raw, agent, width))
        with mock.patch.object(rl, "PAYLOAD_GRAMMAR_AGENTS", ("codex",)):
            self.assertIsNone(rl.composer_payload(claude_short, "claude", 120))

    def test_a_blank_row_typed_into_the_composer_is_never_its_end(self):
        """Review regression: a multi-line edit (the request, a blank input row,
        more text) must not read as "the request, then the footer"."""
        for name, mutate in self.BLANK_EDITS.items():
            agent, width, request, raw = fx(name.split(":")[0])
            edited = mutate(raw)
            with self.subTest(name):
                self.assertEqual(rl.shadow_state(edited, agent), rl.SHADOW_BUSY)
                payload = rl.composer_payload(edited, agent, width)
                self.assertFalse(d.payload_matches(payload, request),
                                 payload and payload.lines)

    @staticmethod
    def _after_composer(raw, extra, glyph):
        rows = raw.split("\n")
        plain = strip_ansi(raw).split("\n")
        idx = max(i for i, ln in enumerate(plain) if ln.startswith(glyph))
        return "\n".join(rows[:idx + 1] + extra + rows[idx + 1:])

    @staticmethod
    def _opencode_text_row(raw, extra_bodies):
        rows = raw.split("\n")
        plain = strip_ansi(raw).split("\n")
        idx = next(i for i, ln in enumerate(plain) if ln.strip().startswith("\u2503  >t c12"))
        gutter = plain[idx][:plain[idx].index("\u2503") + 1]
        return "\n".join(rows[:idx + 1] + [gutter + b for b in extra_bodies] + rows[idx + 1:])

    BLANK_EDITS = {
        "codex_short:blank+text": lambda raw: ComposerProofTests._after_composer(
            raw, ["", "  an unrelated input line"], "\u203a "),
        "codex_short:blank+text+blank": lambda raw: ComposerProofTests._after_composer(
            raw, ["", "  an unrelated input line", ""], "\u203a "),
        "codex_short:two blanks": lambda raw: ComposerProofTests._after_composer(
            raw, [""], "\u203a "),
        "claude_short:blank+text": lambda raw: ComposerProofTests._after_composer(
            raw, ["", "  an unrelated input line"], "\u276f\u00a0"),
        "opencode_conv_short:blank+text": lambda raw: ComposerProofTests._opencode_text_row(
            raw, ["", "  an unrelated input line"]),
        "opencode_conv_short:trailing blank": lambda raw: ComposerProofTests._opencode_text_row(
            raw, [""]),
    }


class RequestLineTests(unittest.TestCase):
    def test_refused_lines(self):
        cases = {"": "empty", "a\nb": "control_character", "a\rb": "control_character",
                 "a\x85b": "control_character", "a b": "control_character",
                 "a\tb": "control_character", "a b": "control_character",
                 "a​b": "control_character", "x" * 401: "too_long",
                 "a  b": "spacing", " a": "spacing", "a ": "spacing",
                 "/model": "special_prefix", "!ls": "special_prefix",
                 "#note": "special_prefix", ">q c1 see @tests/x": "trailing_mention",
                 ">q c1 a@b": "trailing_mention"}
        for text, want in cases.items():
            with self.subTest(repr(text)):
                self.assertEqual(d.request_line_error(text), want)

    def test_accepted_lines(self):
        for text in (">t c12", ">q c1 is @tests/foo.py related", ">p",
                     ">q c3 ünïcödé and 漢字 are fine", ">q c1 a;b \"d\" 'e' $(x)"):
            with self.subTest(text):
                self.assertEqual(d.request_line_error(text), "")

    def test_the_prefix_rule_is_for_the_whole_line_only(self):
        for text in ("/tmp/report.md is this related?", "#2211 is this the same issue?",
                     "$PATH looks wrong here", "!important or not"):
            with self.subTest(text):
                self.assertEqual(d.request_line_error(text), "special_prefix")
                self.assertEqual(d.request_line_error(text, check_prefix=False), "")
                self.assertEqual(d.request_line_error(f">q c12 {text}"), "")
        self.assertEqual(d.request_line_error("a\nb", check_prefix=False), "control_character")
        self.assertEqual(d.request_line_error("see @x", check_prefix=False), "trailing_mention")

    def test_display_width(self):
        self.assertEqual(d.display_width("abc"), 3)
        self.assertEqual(d.display_width("漢字"), 4)
        self.assertEqual(d.display_width("é"), 1)


# -- the orchestrator -------------------------------------------------------------------

class FakeMon:
    """A recording `monitor` for ``deliver_sitrep_request``.

    ``tails`` are the successive ``capture-pane`` answers, ``modes`` the
    successive ``#{pane_in_mode}`` reads (True / False / None = unreadable),
    ``acks`` the branch each guarded dispatch takes (``sent`` / ``skipped`` /
    ``unknown``), in order."""

    def __init__(self, tails, modes=(), acks=(), *, width=120, target=None,
                 load_rc=0, reason_line=None):
        self.tails = list(tails)
        self.modes = list(modes)
        self.acks = list(acks)
        self.width = width
        self.target = target if target is not None else target_line()
        self.load_rc = load_rc
        self.reason_line = reason_line
        self.events = []
        self.stdin = []
        self._nonce = ""
        self._branch = ""

    # sync -------------------------------------------------------------------
    def tmux_run(self, args, timeout=5.0):
        if args[0] == "display-message" and args[-1] == d.TARGET_FORMAT:
            self.events.append("identity")
            return 0, self.target
        if args[0] == "if-shell":
            m = re.search(r"@aitask_dispatch_ack ([0-9a-f]+):sent", args[5])
            self._nonce = m.group(1) if m else ""
            self._branch = self.acks.pop(0) if self.acks else "unknown"
            self.events.append("paste" if args[5].startswith("paste-buffer") else "enter")
            return 0, ""
        if args[0] == "display-message" and args[-1] == mc.DISPATCH_ACK_FORMAT:
            if self._branch == "unknown":
                return 0, f"{PANE}\t{SERVER}\t\n"
            return 0, f"{PANE}\t{SERVER}\t{self._nonce}:{self._branch}\n"
        if args[0] == "display-message":                      # the skip reason
            return 0, self.reason_line or f"{PANE}\t{PID}\t{SERVER}\t\t1\n"
        if args[0] == "delete-buffer":
            self.events.append("delete-buffer")
        return 0, ""

    def tmux_run_input(self, args, data, timeout=5.0):
        self.events.append("load-buffer")
        self.stdin.append(data)
        return self.load_rc, ""

    # async ------------------------------------------------------------------
    async def tmux_run_async(self, args, timeout=5.0):
        if args[0] == "capture-pane":
            self.events.append("capture")
            return (0, self.tails.pop(0)) if self.tails else (1, "")
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


class OrchestratorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.roles_calls = 0
        self.pauses = []

    def roles(self, ok=True, agent=PANE):
        def probe(monitor, root):
            self.roles_calls += 1
            self.assertEqual(root, ROOT)
            return ok, agent, None
        return probe

    async def pause(self, phase):
        self.pauses.append(phase)

    async def run_(self, mon, text=REQ, *, roles=None, agent="claude", pause=None):
        counter = iter(range(1, 100))
        return await d.deliver_sitrep_request(
            mon, ROOT, text, roles=roles or self.roles(), resolve_agent=lambda t: agent,
            pause=pause or self.pause, sleep=_nosleep,
            nonce=lambda: f"{next(counter):016x}")

    async def test_a_ready_agent_gets_the_request_submitted(self):
        mon = FakeMon([REST, REST, SHORT, POST_ENTER], modes=[False, False],
                      acks=["sent", "sent"])
        res = await self.run_(mon)
        self.assertEqual((res.code, res.request), (d.SUBMITTED, REQ))
        self.assertEqual(mon.stdin, [REQ])
        self.assertEqual(mon.events, ["identity", "capture", "capture", "mode",
                                      "load-buffer", "paste", "capture", "width", "mode",
                                      "enter", "capture"])
        self.assertEqual(self.pauses, ["after_readiness", "after_paste"])

    async def test_readiness_refusals_type_nothing(self):
        cases = {
            d.NOT_READY_DIALOG: [rlf.CLAUDE_DIALOG_RAW] * 2,
            d.NOT_READY_DRAFT: [rlf.CLAUDE_TYPED_RAW] * 2,
            d.NOT_READY_WORKING: [rlf.CLAUDE_STREAMING_RAW] * 2,
            d.NOT_READY_UNKNOWN: [],                           # both captures fail
        }
        for reason, tails in cases.items():
            with self.subTest(reason):
                mon = FakeMon(tails, modes=[False])
                res = await self.run_(mon)
                self.assertEqual(res.code, f"refused:{reason}")
                self.assertNotIn("load-buffer", mon.events)
                self.assertNotIn("paste", mon.events)
        for mode, reason in ((True, d.NOT_READY_IN_MODE), (None, d.NOT_READY_MODE_UNREADABLE)):
            with self.subTest(mode=mode):
                mon = FakeMon([REST, REST], modes=[mode])
                res = await self.run_(mon)
                self.assertEqual(res.code, f"refused:{reason}")
                self.assertNotIn("load-buffer", mon.events)

    async def test_target_refusals(self):
        res = await self.run_(FakeMon([]), roles=self.roles(ok=False))
        self.assertEqual((res.code, res.detail), ("refused:no_agent", "roles_query_failed"))
        res = await self.run_(FakeMon([]), roles=self.roles(agent=None))
        self.assertEqual(res.code, "refused:no_agent")
        mon = FakeMon([], target=target_line(frozen="r1"))
        self.assertEqual((await self.run_(mon)).code, "refused:frozen")
        mon = FakeMon([], target=target_line(stamp=""))
        self.assertEqual((await self.run_(mon)).code, "refused:no_agent")
        self.assertNotIn("capture", mon.events)

    async def test_an_agent_without_a_detector_or_grammar_is_refused_before_typing(self):
        mon = FakeMon([REST, REST], modes=[False])
        res = await self.run_(mon, agent="")
        self.assertEqual(res.code, f"refused:{d.NOT_READY_UNKNOWN}")
        self.assertEqual(mon.events, ["identity"])
        with mock.patch.object(rl, "PAYLOAD_GRAMMAR_AGENTS", ("codex",)):
            mon = FakeMon([REST, REST], modes=[False])
            res = await self.run_(mon)
        self.assertEqual(res.code, f"refused:{d.NOT_READY_UNKNOWN}")
        self.assertNotIn("load-buffer", mon.events)

    async def test_an_invalid_line_is_refused_before_anything(self):
        mon = FakeMon([])
        res = await self.run_(mon, text=">q c1 a\nb")
        self.assertEqual(res.code, f"refused:{d.R_INVALID_REQUEST}")
        self.assertEqual((mon.events, self.roles_calls), ([], 0))

    async def test_text_dispatch_outcomes(self):
        mon = FakeMon([REST, REST], modes=[False], acks=["skipped"])
        res = await self.run_(mon)
        self.assertEqual((res.code, res.detail), (d.SKIPPED, mc.SKIP_IN_MODE))
        self.assertIn("delete-buffer", mon.events)
        mon = FakeMon([REST, REST], modes=[False], acks=["unknown"])
        self.assertEqual((await self.run_(mon)).code, d.UNKNOWN)
        mon = FakeMon([REST, REST], modes=[False], load_rc=1)
        res = await self.run_(mon)
        self.assertEqual(res.code, f"refused:{d.R_DISPATCH_FAILED}")
        self.assertNotIn("paste", mon.events)

    async def test_appended_text_withholds_the_first_enter(self):
        mon = FakeMon([REST, REST, APPENDED], modes=[False, False], acks=["sent"])
        res = await self.run_(mon)
        self.assertEqual((res.code, res.detail), (d.TYPED, "composer_changed"))
        self.assertNotIn("enter", mon.events)

    async def test_a_foreign_draft_after_a_submit_gets_no_second_enter(self):
        # The first Enter looked swallowed (still BUSY); by the retry the request
        # sits in history and the composer holds the user's new draft.
        _a, _w, req, draft = fx("claude_history_draft")
        busy = rl.composer_payload(SHORT, "claude", 120)
        self.assertIsNotNone(busy)
        mon = FakeMon([REST, REST, SHORT, SHORT, draft], modes=[False, False, False],
                      acks=["sent", "sent", "sent"])
        res = await self.run_(mon)
        self.assertEqual((res.code, res.detail), (d.UNKNOWN, "composer_changed_after_enter"))
        self.assertEqual(mon.events.count("enter"), 1)
        self.assertEqual(self.pauses, ["after_readiness", "after_paste", "before_retry"])

    async def test_a_foreign_draft_right_after_the_enter_is_unknown_not_typed(self):
        """Review regression: a BUSY read after an Enter is a swallowed Enter
        ONLY when the composer still holds exactly the request."""
        _a, _w, _req, draft = fx("claude_history_draft")
        mon = FakeMon([REST, REST, SHORT, draft], modes=[False, False], acks=["sent", "sent"])
        res = await self.run_(mon)
        self.assertEqual((res.code, res.detail), (d.UNKNOWN, "composer_changed_after_enter"))
        self.assertEqual(mon.events.count("enter"), 1)
        # ... and on the LAST attempt it is not "typed_not_submitted" either.
        mon = FakeMon([REST, REST, SHORT, SHORT, SHORT, draft], modes=[False, False, False],
                      acks=["sent", "sent", "sent"])
        res = await self.run_(mon)
        self.assertEqual((res.code, res.detail), (d.UNKNOWN, "composer_changed_after_enter"))
        self.assertEqual(mon.events.count("enter"), 1 + rl.SHADOW_SUBMIT_RETRIES)
        # an unprovable composer after the Enter is unknown too
        stray = ComposerProofTests._after_composer(SHORT, ["", "  more"], "\u276f\u00a0")
        mon = FakeMon([REST, REST, SHORT, stray], modes=[False, False], acks=["sent", "sent"])
        res = await self.run_(mon)
        self.assertEqual((res.code, res.detail), (d.UNKNOWN, "composer_unprovable_after_enter"))

    async def test_a_blank_line_edit_in_a_codex_composer_gets_no_enter(self):
        _a, width, req, raw = fx("codex_short")
        edited = ComposerProofTests._after_composer(raw, ["", "  an unrelated input line"],
                                                    "\u203a ")
        mon = FakeMon([rlf.CODEX_AT_REST_RAW] * 2 + [edited], modes=[False, False],
                      acks=["sent"], width=width)
        res = await self.run_(mon, text=req, agent="codex")
        self.assertEqual(res.code, d.UNKNOWN)
        self.assertNotIn("enter", mon.events)
        # control: the same capture without the edit is submitted
        _a, _w, _r, post = fx("codex_post_enter")
        mon = FakeMon([rlf.CODEX_AT_REST_RAW] * 2 + [raw, post], modes=[False, False],
                      acks=["sent", "sent"], width=width)
        self.assertEqual((await self.run_(mon, text=req, agent="codex")).code, d.SUBMITTED)

    async def test_a_composer_that_never_empties(self):
        mon = FakeMon([REST, REST] + [SHORT] * 4, modes=[False, False, False],
                      acks=["sent", "sent", "sent"])
        res = await self.run_(mon)
        self.assertEqual((res.code, res.detail), (d.TYPED, "submit_unconfirmed"))
        self.assertEqual(mon.events.count("enter"), 1 + rl.SHADOW_SUBMIT_RETRIES)

    async def test_the_mode_is_read_before_every_enter(self):
        for mode, code in ((True, d.TYPED_IN_MODE), (None, d.TYPED_MODE_UNREADABLE)):
            with self.subTest(mode=mode):
                mon = FakeMon([REST, REST, SHORT], modes=[False, mode], acks=["sent"])
                res = await self.run_(mon)
                self.assertEqual(res.code, code)
                self.assertNotIn("enter", mon.events)
        # the retry passes the gate again: copy-mode entered after a swallowed Enter
        mon = FakeMon([REST, REST, SHORT, SHORT, SHORT], modes=[False, False, True],
                      acks=["sent", "sent"])
        res = await self.run_(mon)
        self.assertEqual(res.code, d.TYPED_IN_MODE)
        self.assertEqual(mon.events.count("enter"), 1)
        enter_at = [i for i, e in enumerate(mon.events) if e == "enter"]
        for i in enter_at:
            self.assertEqual(mon.events[i - 1], "mode", "the mode is the last read")

    async def test_enter_dispatch_outcomes(self):
        mon = FakeMon([REST, REST, SHORT], modes=[False, False], acks=["sent", "skipped"])
        self.assertEqual((await self.run_(mon)).code, d.TYPED_IN_MODE)
        mon = FakeMon([REST, REST, SHORT], modes=[False, False], acks=["sent", "skipped"],
                      reason_line=f"{PANE}\t5\t{SERVER}\t\t0\n")
        self.assertEqual((await self.run_(mon)).code, f"refused:{d.R_IDENTITY_CHANGED}")
        mon = FakeMon([REST, REST, SHORT], modes=[False, False], acks=["sent", "unknown"])
        self.assertEqual((await self.run_(mon)).code, d.UNKNOWN)

    async def test_pre_and_post_enter_reads_that_prove_nothing(self):
        cases = {
            "text_not_in_composer": [REST],
            "pre_enter_dialog": [rlf.CLAUDE_DIALOG_RAW],
            "pre_enter_unreadable": [],
        }
        for detail, after in cases.items():
            with self.subTest(detail):
                mon = FakeMon([REST, REST] + after, modes=[False], acks=["sent"])
                res = await self.run_(mon)
                self.assertEqual((res.code, res.detail), (d.UNKNOWN, detail))
                self.assertNotIn("enter", mon.events)
        mon = FakeMon([REST, REST, SHORT, rlf.CLAUDE_DIALOG_RAW], modes=[False, False],
                      acks=["sent", "sent"])
        res = await self.run_(mon)
        self.assertEqual((res.code, res.detail), (d.UNKNOWN, "post_enter_dialog"))

    async def test_a_resize_makes_the_composer_unprovable(self):
        mon = FakeMon([REST, REST, SHORT], modes=[False], acks=["sent"], width=100)
        res = await self.run_(mon)
        self.assertEqual((res.code, res.detail), (d.UNKNOWN, "composer_unprovable"))
        self.assertNotIn("enter", mon.events)

    async def test_the_agent_and_identity_are_re_read_on_every_request(self):
        for _ in range(2):
            mon = FakeMon([REST, REST, SHORT, POST_ENTER], modes=[False, False],
                          acks=["sent", "sent"])
            self.assertEqual((await self.run_(mon)).code, d.SUBMITTED)
            self.assertEqual(mon.events.count("identity"), 1)
        self.assertEqual(self.roles_calls, 2)


class ResultMessageTests(unittest.TestCase):
    def test_unknown_never_reads_as_sent(self):
        msg = d.DeliveryResult(d.UNKNOWN).message().lower()
        self.assertNotIn("sent to", msg)
        self.assertIn("look at", msg)
        self.assertTrue(d.DeliveryResult(d.SUBMITTED).submitted)
        self.assertIn("waiting in its composer", d.DeliveryResult(d.TYPED_IN_MODE).message())
        self.assertTrue(d.DeliveryResult("refused:not_ready:dialog").message()
                        .startswith("Not sent: the agent is waiting"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
