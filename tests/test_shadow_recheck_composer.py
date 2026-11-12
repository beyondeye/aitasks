"""The composer-payload proof at the shadow pane widths (t2280).

``review_loop.composer_payload`` + ``agent_request_delivery.payload_matches``
were measured at 120 columns (``tests/sitrep_request_fixtures.py``, t2211_4).
A shadow pane is ``shadow_pane_width`` (default 60) wide, so the recheck
prompt wraps there. These tests pin the proof against real captures at 60 and
44 columns (``tests/shadow_recheck_fixtures.py``): every genuine composer is
proved, appended text and a foreign draft never are, and each width rule is
tied to captured evidence rather than restated from the parser.

Run: python3 -m unittest tests/test_shadow_recheck_composer.py
"""

from __future__ import annotations

import dataclasses
import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / ".aitask-scripts"
for _p in (str(Path(__file__).resolve().parent), str(SCRIPTS), str(SCRIPTS / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from shadow_recheck_fixtures import FIXTURES, UNMEASURED, WIDTHS  # noqa: E402

from monitor import agent_request_delivery as d  # noqa: E402
from monitor import review_loop as rl  # noqa: E402
from monitor.ansi_utils import strip_ansi  # noqa: E402

MEASURED = tuple(a for a in rl.PAYLOAD_GRAMMAR_AGENTS if a not in UNMEASURED)
PHASES = {"recheck_plan": "PLAN", "recheck_impl": "IMPLEMENT", "recheck_generic": None}
REQUIRED = (*PHASES, "appended", "history_draft", "post_enter", "midtoken")
REJECTED = ("_appended", "_history_draft")

#: The measured rules, as functions of the pane width W: (content, wrap, hyphen).
RULES = {
    "claude": lambda w: (w - 4, w - 4, False),
    "codex": lambda w: (w - 3, w - 3, True),
    "opencode": lambda w: (w - 9, w - 10, True),
}
_EDGE_RE = re.compile(r"_edge_(\d+)_(\d+)$")
_HYPHEN_RE = re.compile(r"_hyphen_(\d+)_(\d+)$")
_END_RE = re.compile(r"_end(word|hyphen)_(\d+)_(\d+)$")


def fx(name):
    agent, width, state, request, raw = FIXTURES[name]
    return agent, width, state, request, raw


def payload(name):
    agent, width, _state, _request, raw = fx(name)
    return rl.composer_payload(raw, agent, width)


def names(agent, width, pattern):
    prefix = f"{agent}_w{width}_"
    return sorted(n for n in FIXTURES if n.startswith(prefix) and pattern.search(n))


def genuine():
    """Composers holding exactly their request (the end-of-text probes have their own test)."""
    return sorted(n for n in FIXTURES
                  if not n.endswith((*REJECTED, "_post_enter")) and not _END_RE.search(n))


class CoverageTests(unittest.TestCase):
    def test_every_measured_agent_and_width_is_covered(self):
        self.assertEqual(MEASURED, ("claude", "codex", "opencode"),
                         "an agent was declared unmeasured: t2275 must treat it as unprovable")
        for agent in MEASURED:
            for width in WIDTHS:
                with self.subTest(agent=agent, width=width):
                    for variant in REQUIRED:
                        self.assertIn(f"{agent}_w{width}_{variant}", FIXTURES)
                    self.assertEqual(len(names(agent, width, _EDGE_RE)), 3)
                    self.assertGreaterEqual(len(names(agent, width, _HYPHEN_RE)), 3)
                    self.assertEqual(len(names(agent, width, _END_RE)), 6)

    def test_every_entry_is_well_formed(self):
        for name, (agent, width, state, request, raw) in FIXTURES.items():
            with self.subTest(name):
                self.assertTrue(name.startswith(f"{agent}_w{width}_"))
                self.assertIn(width, (*WIDTHS, 120))    # 120: the opencode end-of-text supplement
                self.assertTrue(request and raw)
                self.assertEqual(rl.shadow_state(raw, agent), state)

    def test_the_recheck_requests_are_the_real_prompts(self):
        """Red here means the prompt wording changed: measure the widths again."""
        for agent in MEASURED:
            for width in WIDTHS:
                for variant, phase in PHASES.items():
                    with self.subTest(agent=agent, width=width, variant=variant):
                        request = fx(f"{agent}_w{width}_{variant}")[3]
                        self.assertEqual(request, rl.compose_recheck_prompt(phase, 1))
                with self.subTest(agent=agent, width=width, variant="appended"):
                    self.assertEqual(fx(f"{agent}_w{width}_appended")[3],
                                     rl.compose_recheck_prompt("PLAN", 1))


class ComposerProofTests(unittest.TestCase):
    def test_every_genuine_capture_is_proved(self):
        self.assertEqual(len(genuine()), 62)
        for name in genuine():
            agent, width, state, request, raw = fx(name)
            with self.subTest(name):
                self.assertEqual(state, rl.SHADOW_BUSY)
                p = rl.composer_payload(raw, agent, width)
                self.assertIsNotNone(p)
                self.assertTrue(d.payload_matches(p, request), p.lines)

    def test_the_recheck_prompt_really_wraps_at_these_widths(self):
        for agent in MEASURED:
            for width in WIDTHS:
                for variant in PHASES:
                    with self.subTest(agent=agent, width=width, variant=variant):
                        self.assertGreaterEqual(len(payload(f"{agent}_w{width}_{variant}").lines), 2)

    def test_appended_text_and_a_foreign_draft_never_match(self):
        rejected = sorted(n for n in FIXTURES if n.endswith(REJECTED))
        self.assertEqual(len(rejected), 2 * len(MEASURED) * len(WIDTHS))
        for name in rejected:
            agent, width, _state, request, raw = fx(name)
            with self.subTest(name):
                p = rl.composer_payload(raw, agent, width)
                self.assertIsNotNone(p, "a delimited composer, just not ours")
                self.assertFalse(d.payload_matches(p, request))
                if name.endswith("_history_draft"):     # a plain search WOULD find it
                    self.assertIn(request, strip_ansi(raw))

    def test_a_post_enter_capture_is_never_the_prompt(self):
        for name in sorted(n for n in FIXTURES if n.endswith("_post_enter")):
            agent, width, state, request, raw = fx(name)
            with self.subTest(name):
                self.assertNotEqual(state, rl.SHADOW_BUSY)
                self.assertFalse(d.payload_matches(rl.composer_payload(raw, agent, width), request))


class WidthRuleTests(unittest.TestCase):
    """Each rule is tied to captured rows, not just restated from the parser."""

    def test_the_width_rules(self):
        for name in genuine():
            agent, width = fx(name)[:2]
            with self.subTest(name):
                p = payload(name)
                self.assertEqual((p.content_width, p.wrap_width, p.hyphen_breaks),
                                 RULES[agent](width))

    def test_the_content_width_is_measured_by_the_hard_breaks(self):
        """Only a hard break consults content_width, so the midtoken rows are its evidence."""
        for agent in MEASURED:
            for width in WIDTHS:
                name = f"{agent}_w{width}_midtoken"
                request = fx(name)[3]
                p = payload(name)
                with self.subTest(name):
                    self.assertTrue(d.payload_matches(p, request))
                    full = [r for r in p.lines[:-1] if d.display_width(r) == p.content_width]
                    self.assertGreaterEqual(len(full), 2, p.lines)
                    for delta in (-1, 1):
                        bent = dataclasses.replace(p, content_width=p.content_width + delta)
                        self.assertFalse(d.payload_matches(bent, request), delta)

    def test_the_wrap_width_is_measured_by_the_edges(self):
        """Both sides of the word-wrap threshold, read from the captured layout.

        A matcher perturbation is used only where the contract rejects: with
        ``wrap_width + 1`` the wrapped capture's break is no longer justified.
        ``wrap_width - 1`` only ever accepts more breaks (a fit is never
        checked), so that side is pinned by the layout assertions alone.
        """
        for agent in MEASURED:
            for width in WIDTHS:
                ww = RULES[agent](width)[1]
                edges = names(agent, width, _EDGE_RE)
                totals = sorted(int(_EDGE_RE.search(n).group(2)) for n in edges)
                self.assertEqual(totals, [ww - 1, ww, ww + 1], (agent, width))
                for name in edges:
                    k, total = map(int, _EDGE_RE.search(name).groups())
                    bw = total - k - 1
                    request = fx(name)[3]
                    p = payload(name)
                    with self.subTest(name):
                        self.assertTrue(d.payload_matches(p, request))
                        if total <= ww:
                            self.assertEqual(p.lines[0], "a" * k + " " + "b" * bw)
                        else:
                            self.assertEqual(p.lines[0], "a" * k)
                            self.assertTrue(p.lines[1].startswith("b" * bw))
                            bent = dataclasses.replace(p, wrap_width=p.wrap_width + 1)
                            self.assertFalse(d.payload_matches(bent, request))


class HyphenBreakTests(unittest.TestCase):
    """codex and opencode break right after a hyphen; claude never does (t2280)."""

    def test_the_hyphen_bound_is_read_from_the_captured_layout(self):
        for agent in MEASURED:
            content, _wrap, breaks = RULES[agent](0)
            for width in WIDTHS:
                bound = RULES[agent](width)[0]          # a hyphen-ended prefix fits up to cw
                probes = names(agent, width, _HYPHEN_RE)
                prefixes = [int(_HYPHEN_RE.search(n).group(2)) for n in probes]
                self.assertIn(bound + 1, prefixes, "the bound is crossed")
                self.assertTrue(any(pp <= bound for pp in prefixes), "and approached")
                for name in probes:
                    k, prefix = map(int, _HYPHEN_RE.search(name).groups())
                    head = "a" * k + " " + "b" * (prefix - k - 2) + "-"
                    p = payload(name)
                    with self.subTest(name):
                        if breaks and prefix <= bound:
                            self.assertEqual(p.lines[0], head)
                            self.assertTrue(p.lines[1].startswith("c" * 10))
                        else:
                            self.assertEqual(p.lines[0], "a" * k)
                            self.assertTrue(p.lines[1].startswith(head[k + 1:]))

    def test_the_real_recheck_prompt_breaks_at_a_hyphen_in_opencode(self):
        for width in WIDTHS:
            name = f"opencode_w{width}_recheck_plan"
            p = payload(name)
            with self.subTest(name):
                self.assertTrue(any(r.endswith("-") for r in p.lines[:-1]), p.lines)

    def test_the_hyphen_rule_is_load_bearing(self):
        """Without it the genuine opencode recheck prompts are unprovable (pre-fix state)."""
        for width in WIDTHS:
            for variant in ("recheck_plan", "recheck_impl"):
                name = f"opencode_w{width}_{variant}"
                request = fx(name)[3]
                bent = dataclasses.replace(payload(name), hyphen_breaks=False)
                with self.subTest(name):
                    self.assertFalse(d.payload_matches(bent, request))

    def test_an_unjustified_hyphen_break_is_rejected(self):
        """A break after a hyphen where the next fragment would have fitted."""
        P = rl.ComposerPayload
        text = "aaa re-run the rest"
        self.assertTrue(d.payload_matches(P(("aaa re-", "run the rest"), 10, 9, True), text))
        self.assertFalse(d.payload_matches(P(("aaa re-", "run the rest"), 12, 11, True), text),
                         "'run' fitted after 'aaa re-'")
        self.assertFalse(d.payload_matches(P(("aaa re-", "run the rest"), 10, 9, False), text),
                         "an agent without hyphen breaks")
        self.assertTrue(d.payload_matches(P(("aaa re-", "run the rest"), 7, 9, False), text),
                        "a full row is still a hard break")
        self.assertFalse(d.payload_matches(P(("aaa re-", "-run"), 10, 9, True), "aaa re--run"),
                         "the one-hyphen piece fitted")

    @staticmethod
    def _retype_opencode(name, rows):
        """A real opencode composer (ANSI stripped) with its text rows replaced."""
        plain = strip_ansi(fx(name)[4]).split("\n")
        old = payload(name).lines
        idx = [next(i for i, ln in enumerate(plain) if ln.lstrip().startswith("\u2503  " + r))
               for r in old]
        assert len(idx) == len(rows) and idx == list(range(idx[0], idx[0] + len(idx)))
        for i, (o, r) in zip(idx, zip(old, rows)):
            plain[i] = plain[i].replace("\u2503  " + o, "\u2503  " + r.ljust(len(o)), 1)
        return "\n".join(plain)

    def test_a_typed_newline_after_a_hyphen_is_rejected(self):
        """Review regression: a hyphen-ended next piece fits up to the content width
        (measured), so breaking before one that fitted is a typed newline."""
        cw = RULES["opencode"](60)[0]                        # 51
        typed = self._retype_opencode("opencode_w60_hyphen_25_49",
                                      ("a" * 42 + "-", "b" * 7 + "-" + "c" * 10))
        p = rl.composer_payload(typed, "opencode", 60)
        self.assertEqual(p.lines, ("a" * 42 + "-", "b" * 7 + "-" + "c" * 10))
        self.assertEqual(43 + 8, cw, "the piece fitted exactly")
        self.assertFalse(d.payload_matches(p, "a" * 42 + "-" + "b" * 7 + "-" + "c" * 10))
        wrapped = self._retype_opencode("opencode_w60_hyphen_25_49",
                                        ("a" * 43 + "-", "b" * 7 + "-" + "c" * 9))
        self.assertTrue(d.payload_matches(rl.composer_payload(wrapped, "opencode", 60),
                                          "a" * 43 + "-" + "b" * 7 + "-" + "c" * 9),
                        "one column more and the break is justified")

    def test_a_newline_before_a_compound_whose_first_piece_fitted_is_rejected(self):
        """A hyphen-breaking agent would have kept ``b..b-`` on the row; claude would not."""
        P = rl.ComposerPayload
        text = "a" * 20 + " " + "b" * 10 + "-" + "c" * 40
        rows = ("a" * 20, "b" * 10 + "-" + "c" * 40)
        self.assertFalse(d.payload_matches(P(rows, 51, 50, True), text))
        self.assertTrue(d.payload_matches(P(rows, 51, 51, False), text))


class EndOfTextTests(unittest.TestCase):
    """A text that ENDS in the piece that may move (measured at 60, 44 and 120)."""

    def test_a_final_piece_fits_up_to_the_content_width(self):
        ends = sorted(n for n in FIXTURES if _END_RE.search(n))
        self.assertEqual(len(ends), 6 * len(MEASURED) * len(WIDTHS) + 6)
        for name in ends:
            agent, width, _state, request, raw = fx(name)
            _kind, _k, total = _END_RE.search(name).groups()
            total = int(total)
            cw = payload(name).content_width if payload(name) else RULES[agent](width)[0]
            p = rl.composer_payload(raw, agent, width)
            with self.subTest(name):
                if total < cw or (total == cw and agent != "codex"):
                    self.assertEqual(p.lines, (request,), "kept on the row")
                    self.assertTrue(d.payload_matches(p, request))
                elif total == cw:
                    # codex: the cursor wraps onto an empty row -- indistinguishable
                    # from a typed blank line, so unprovable (fail closed).
                    self.assertIsNone(p)
                else:
                    self.assertEqual(len(p.lines), 2)
                    self.assertTrue(d.payload_matches(p, request))
                    bent = dataclasses.replace(p, content_width=p.content_width + 1)
                    self.assertFalse(d.payload_matches(bent, request),
                                     "the end-of-text limit is the content width")


if __name__ == "__main__":
    unittest.main()
