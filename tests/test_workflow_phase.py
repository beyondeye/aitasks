"""Unit tests for the advisory workflow-phase seam (t1420).

The load-bearing properties, each with a positive control so a green run cannot
be vacuous:

- ``UNKNOWN`` vs ``PLAN``: no ledger is "I cannot tell", NOT "in planning" —
  and the phase never depends on the profile, only the ``recording`` provenance
  does;
- currency: an answered checkpoint survives in scrollback, so a Tier A anchor
  only counts when the pane is blocked on a *question widget* and the anchor is
  inside the current widget's bound;
- absence-safety: an agent with no prompt markers, and a generic confirmation,
  contribute nothing and can never yield a guessed phase;
- one canonical vocabulary, validated on the way out and degraded on the way in.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / ".aitask-scripts"
sys.path.insert(0, str(SCRIPTS_DIR / "lib"))

import workflow_phase as wp  # noqa: E402

FM = ("---\npriority: medium\neffort: low\nstatus: Implementing\n"
      "issue_type: feature\n{extra}---\n\n# Demo\n\n")

PLAN_RUN = ("> **✅ gate:plan_approved** run=2026-01-01T00:00:00Z "
            "status=pass attempt=1 type=human\n")
REVIEW_RUN = ("> **✅ gate:review_approved** run=2026-01-01T00:01:00Z "
              "status=pass attempt=1 type=human\n")


def task_text(*runs: str, profile: str = "") -> str:
    extra = f"active_gates_profile: {profile}\n" if profile else ""
    body = FM.format(extra=extra)
    if runs:
        body += "## Gate Runs\n\n" + "\n".join(runs)
    return body


# A tail shaped like the measured live AskUserQuestion: question text 14 lines
# above the bottom, option list below it, help bar last.
def question_screen(question: str, *, gap: int = 14, preamble: str = "") -> str:
    """The measured AskUserQuestion shape: top rule, header chip, question,
    options, help bar. The chip is what `current_question_block` keys off."""
    filler = "\n".join(f"  {i}. option line" for i in range(gap - 1))
    return (f"{preamble}"
            "\u2500" * 40 + "\n"
            " \u2610 Proceed \n"
            "\n"
            f"{question}\n"
            f"{filler}\n"
            f"Enter to select · ↑/↓ to navigate · Esc to cancel")


PLAN_Q = "Plan saved to `aiplans/p1_demo.md`. How would you like to proceed?"
REVIEW_Q = ("Implementation complete. Please review and test the changes. "
            "When ready, select an option:")


class LedgerHalfTest(unittest.TestCase):
    def test_no_ledger_is_unknown_not_plan(self):
        phase, detail = wp.phase_from_ledger_text(task_text())
        self.assertEqual(phase, "UNKNOWN")
        self.assertIn("no ## Gate Runs", detail)

    def test_recorded_states(self):
        self.assertEqual(wp.phase_from_ledger_text(task_text(PLAN_RUN))[0],
                         "IMPLEMENT")
        self.assertEqual(
            wp.phase_from_ledger_text(task_text(PLAN_RUN, REVIEW_RUN))[0],
            "POSTIMPL")

    def test_phase_is_profile_independent_recording_is_not(self):
        """The weakest surface: an empty ledger must report UNKNOWN under BOTH a
        recording and a non-recording profile — only `recording` may differ."""
        with tempfile.TemporaryDirectory() as d:
            profiles = Path(d) / "profiles"
            profiles.mkdir()
            (profiles / "fast.yaml").write_text("name: fast\nrecord_gates: true\n")
            (profiles / "default.yaml").write_text("name: default\n")
            for prof, expected_rec in (("fast", "on"), ("default", "off")):
                sig = wp.phase_signal(task_text=task_text(profile=prof),
                                      agent="claude", profiles_dir=str(profiles))
                self.assertEqual(sig.phase, "UNKNOWN", prof)
                self.assertEqual(sig.recording, expected_rec, prof)
            # Positive control: with a ledger, both profiles agree on the phase.
            for prof in ("fast", "default"):
                sig = wp.phase_signal(task_text=task_text(PLAN_RUN, profile=prof),
                                      agent="claude", profiles_dir=str(profiles))
                self.assertEqual(sig.phase, "IMPLEMENT", prof)


class CurrencyGateTest(unittest.TestCase):
    """An answered checkpoint survives in scrollback (`capture-pane -S` reads
    history), so `awaiting_input` alone is not evidence that the *matched*
    prompt is the live one."""

    def _sig(self, screen, **kw):
        kw.setdefault("agent", "claude")
        return wp.phase_signal(task_text=task_text(PLAN_RUN),
                               screen_text=screen, **kw)

    def test_live_question_wins_over_ledger(self):
        """Positive control for the whole suppression family."""
        sig = self._sig(question_screen(PLAN_Q), awaiting_input=True,
                        awaiting_input_kind="claude_askuserquestion")
        self.assertEqual((sig.phase, sig.waiting, sig.source),
                         ("PLAN", "WAITING", "workflow-prompt"))

    def test_stale_anchor_not_awaiting(self):
        sig = self._sig(question_screen(PLAN_Q), awaiting_input=False)
        self.assertEqual((sig.phase, sig.source), ("IMPLEMENT", "ledger"))
        self.assertEqual(sig.waiting, "RUNNING")

    def test_stale_anchor_unverifiable_awaiting(self):
        """`None` is not a licence to override."""
        sig = self._sig(question_screen(PLAN_Q), awaiting_input=None)
        self.assertEqual((sig.phase, sig.source), ("IMPLEMENT", "ledger"))
        self.assertEqual(sig.waiting, "UNKNOWN")

    def test_stale_anchor_with_live_tool_permission(self):
        """THE discriminating case: a prompt IS live, but it is a tool-permission
        dialog, not the workflow question whose text is still on screen. A
        build gated only on `awaiting_input` would answer PLAN/WAITING here."""
        sig = self._sig(question_screen(PLAN_Q), awaiting_input=True,
                        awaiting_input_kind="claude_help_bar")
        self.assertEqual((sig.phase, sig.waiting, sig.source),
                         ("IMPLEMENT", "WAITING", "ledger"))
        self.assertIn("suppressed", sig.detail)

    def test_stale_anchor_above_a_later_unrelated_question(self):
        """The case a distance bound cannot catch: an answered checkpoint's text
        is still on screen, and a DIFFERENT question is now live underneath it.
        `awaiting_input` is True and the kind IS a question widget, so only the
        block boundary can tell them apart."""
        screen = (f"  ⎿  · {PLAN_Q} → Start implementation\n"
                  "\n"
                  + question_screen("Which files should I look at first?"))
        sig = self._sig(screen, awaiting_input=True,
                        awaiting_input_kind="claude_askuserquestion")
        self.assertEqual((sig.phase, sig.source), ("IMPLEMENT", "ledger"))
        self.assertIn("no workflow anchor inside the current question block",
                      sig.detail)

    def test_anchor_above_the_block_start_is_ignored(self):
        """Same shape, minimal: an anchor ABOVE the header chip is out of block."""
        screen = (f"{PLAN_Q}\n" + question_screen("Something else entirely?"))
        sig = self._sig(screen, awaiting_input=True,
                        awaiting_input_kind="claude_askuserquestion")
        self.assertEqual(sig.source, "ledger")

    def test_no_question_block_suppresses(self):
        """A question kind but no renderable block ⇒ ambiguity ⇒ ledger."""
        sig = self._sig("Plan saved to somewhere\nEnter to select · ↑/↓ to navigate",
                        awaiting_input=True,
                        awaiting_input_kind="claude_askuserquestion")
        self.assertEqual(sig.source, "ledger")

    def test_last_anchor_wins(self):
        """Both an old and the current checkpoint visible → the later one."""
        screen = question_screen(REVIEW_Q, preamble=f"{PLAN_Q}\n\n")
        sig = self._sig(screen, awaiting_input=True,
                        awaiting_input_kind="claude_askuserquestion")
        self.assertEqual((sig.phase, sig.source), ("IMPLEMENT", "workflow-prompt"))


class AbsenceSafetyTest(unittest.TestCase):
    """A missing native pattern must degrade to the ledger, never guess."""

    def _cases(self):
        return (
            ("codex", "codex_yes_proceed"),
            ("claude", "claude_proceed"),
            ("opencode", "some_unknown_kind"),
        )

    def test_generic_confirmations_carry_no_phase(self):
        for agent, kind in self._cases():
            for runs, expected in (((), "UNKNOWN"), ((PLAN_RUN,), "IMPLEMENT")):
                sig = wp.phase_signal(
                    task_text=task_text(*runs),
                    screen_text=question_screen(PLAN_Q),
                    awaiting_input=True, awaiting_input_kind=kind, agent=agent)
                self.assertEqual(sig.phase, expected, f"{agent}/{kind}/{runs}")
                self.assertIn(sig.source, ("ledger", "none"), f"{agent}/{kind}")

    def test_opencode_live_tiers_unavailable(self):
        self.assertFalse(wp.live_tiers_available("opencode"))
        self.assertFalse(wp.live_tiers_available("codex"))
        self.assertTrue(wp.live_tiers_available("claude"))
        sig = wp.phase_signal(task_text=task_text(PLAN_RUN),
                              screen_text=question_screen(PLAN_Q),
                              awaiting_input=True,
                              awaiting_input_kind="claude_askuserquestion",
                              agent="opencode")
        self.assertEqual(sig.phase, "IMPLEMENT")
        self.assertNotIn("screen", sig.consulted)
        self.assertIn("t1467", sig.detail)

    def test_no_agent_supplied_is_not_blamed_on_t1467(self):
        sig = wp.phase_signal(task_text=task_text(PLAN_RUN), agent="")
        self.assertNotIn("t1467", sig.detail)
        self.assertIn("no agent supplied", sig.detail)

    def test_native_positive_control(self):
        """Without this, the three negatives above would pass against a build
        that simply never consults Tier B."""
        sig = wp.phase_signal(task_text=task_text(PLAN_RUN),
                              screen_text="nothing relevant here",
                              awaiting_input=True,
                              awaiting_input_kind="claude_plan_approval",
                              agent="claude")
        self.assertEqual((sig.phase, sig.waiting, sig.source),
                         ("PLAN", "WAITING", "native-prompt"))


class VocabularyTest(unittest.TestCase):
    def test_sets_are_pinned(self):
        self.assertEqual(wp.PHASES, ("PLAN", "IMPLEMENT", "POSTIMPL", "UNKNOWN"))
        self.assertEqual(wp.LIVENESS, ("WAITING", "RUNNING", "UNKNOWN"))
        self.assertEqual(wp.SOURCES,
                         ("workflow-prompt", "native-prompt", "ledger", "none"))

    def test_round_trip_every_source(self):
        for source in wp.SOURCES:
            sig = wp.PhaseSignal(phase="PLAN", waiting="WAITING", source=source,
                                 consulted=["ledger", "screen"], recording="on",
                                 detail="some detail")
            back = wp.parse_signal(wp.format_signal(sig))
            self.assertEqual(back, sig, source)

    def test_formatter_refuses_non_members(self):
        line = wp.format_signal(wp.PhaseSignal(phase="BOGUS", waiting="NOPE",
                                               source="invented"))
        self.assertIn("PHASE:UNKNOWN", line)
        self.assertIn("WAITING:UNKNOWN", line)
        self.assertIn("SOURCE:none", line)

    def test_parser_is_total(self):
        for junk in ("", "garbage", "PHASE:|WAITING:", "\x00\x01",
                     "PHASE:PLAN|SOURCE:not-a-source"):
            sig = wp.parse_signal(junk)
            self.assertIn(sig.phase, wp.PHASES)
            self.assertIn(sig.waiting, wp.LIVENESS)
            self.assertIn(sig.source, wp.SOURCES)

    def test_delimiter_sanitized_at_write_site(self):
        sig = wp.PhaseSignal(detail="has | a delim\nand a newline")
        line = wp.format_signal(sig)
        self.assertEqual(line.count("\n"), 0)
        self.assertEqual(wp.parse_signal(line).detail, "has / a delim and a newline")

    def test_every_composed_signal_is_in_vocabulary(self):
        for aw in (True, False, None):
            for kind in ("claude_askuserquestion", "claude_help_bar",
                         "claude_plan_approval", ""):
                for agent in ("claude", "codex", "opencode", ""):
                    sig = wp.phase_signal(
                        task_text=task_text(PLAN_RUN),
                        screen_text=question_screen(PLAN_Q),
                        awaiting_input=aw, awaiting_input_kind=kind, agent=agent)
                    self.assertIn(sig.phase, wp.PHASES)
                    self.assertIn(sig.waiting, wp.LIVENESS)
                    self.assertIn(sig.source, wp.SOURCES)


class MiscTest(unittest.TestCase):
    def test_unreadable_task_file_is_not_fatal(self):
        sig = wp.phase_signal("/nonexistent/dir/t1.md", agent="claude")
        self.assertEqual(sig.phase, "UNKNOWN")

    def test_default_profiles_dir_from_supplied_path(self):
        got = wp.default_profiles_dir("/proj/aitasks/t1_demo.md")
        self.assertEqual(got, os.path.join("/proj/aitasks", "metadata", "profiles"))
        self.assertEqual(
            wp.default_profiles_dir("/proj/aitasks/t1/t1_2_demo.md"),
            os.path.join("/proj/aitasks", "metadata", "profiles"))
        self.assertIsNone(wp.default_profiles_dir("/tmp/loose.md"))


if __name__ == "__main__":
    unittest.main()
