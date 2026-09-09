#!/usr/bin/env python3
"""`agent_freeze.main()`'s freeze grammar, and the `--dry-run` listing (t1705_7).

**Why this exists.** `main()` used to dispatch on its first argument and
silently ignore every trailing one, so `freeze --all --dry-rnu` performed a REAL
freeze of every agent on the machine and `freeze <pane> --dry-run` really froze
that pane. Nothing in Python rejected them — the only thing that did was
`aitask_frozen.sh`'s `[ $# -eq 2 ]` arity gate, and adding `--dry-run` requires
that gate relaxed. So the rejection moved into `main()`, and it has to cover the
whole grammar rather than just recognising one new spelling.

**The assertion that matters is the mutation spy, not the exit code.** A grammar
test that only checked statuses would pass while a mutator ran underneath it, so
every rejected form here asserts that NEITHER `freeze_pane` NOR `freeze_all` was
called.

**Nothing here touches tmux.** `discover_aitasks_sessions` /
`_agent_panes_for` are replaced with a fake two-session enumeration. That
matters more than usual: `AITASKS_AGENT_SESSIONS_FILE` isolates only the JSON
store, while session discovery queries the CURRENT tmux server — so a test that
ran the real enumeration would act on whatever agents the developer has open.
Safety must hold even when the dry-run dispatch is broken, which is precisely
what this module is checking.

The wrapper's forwarding — that `freeze --all --dry-run` even reaches the engine
— is `tests/test_frozen_dry_run_wrapper.sh`.

Run: python3 tests/test_freeze_argument_grammar.py
"""

from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / ".aitask-scripts"))
sys.path.insert(0, str(PROJECT_DIR / ".aitask-scripts" / "lib"))

import agent_freeze  # noqa: E402
from monitor.monitor_core import PaneCategory  # noqa: E402


def _pane(pane_id, session, window, *, category=PaneCategory.AGENT,
          frozen_record=""):
    return SimpleNamespace(
        pane_id=pane_id, session_name=session, window_name=window,
        category=category, frozen_record=frozen_record,
    )


#: Two sessions — the point of the fixture. A monitor in single-session mode
#: sees at most one of them, so a confirmation count derived from its own
#: snapshots would understate the operation.
FAKE_PANES = {
    "aitasks": [
        _pane("%1", "aitasks", "agent-pick-1705"),
        # PARKED is invisible here on purpose: parking is a concept a TUI
        # publishes to its own TmuxMonitor, and the one `freeze_all` builds has
        # no parked set. A parked agent IS eligible, and the count must say so.
        _pane("%2", "aitasks", "agent-pick-1700"),
        _pane("%3", "aitasks", "agent-pick-1690", frozen_record="7f3a2c1d"),
        _pane("%4", "aitasks", "minimonitor", category=PaneCategory.TUI),
    ],
    "otherproj": [
        _pane("%9", "otherproj", "agent-pick-42"),
    ],
}


class _GrammarCase(unittest.TestCase):
    """Fake enumeration plus spies on both mutators."""

    def setUp(self) -> None:
        self.froze_panes: list[str] = []
        self.froze_all = 0

        def fake_freeze_pane(pane_id, **kw):
            self.froze_panes.append(pane_id)
            return agent_freeze.FreezeResult(pane_id, True, "", f"FROZEN:{pane_id}")

        def fake_freeze_all():
            self.froze_all += 1
            return []

        def fake_sessions(**kw):
            return [SimpleNamespace(session=name) for name in FAKE_PANES]

        for target, repl in (
            ("freeze_pane", fake_freeze_pane),
            ("freeze_all", fake_freeze_all),
            ("discover_aitasks_sessions", fake_sessions),
            ("_agent_panes_for", lambda s: list(FAKE_PANES[s])),
        ):
            p = patch.object(agent_freeze, target, repl)
            p.start()
            self.addCleanup(p.stop)

    def run_main(self, argv: list[str]) -> tuple[int, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = agent_freeze.main(argv)
        return rc, out.getvalue()

    def assertNothingMutated(self) -> None:
        self.assertEqual(
            (self.froze_panes, self.froze_all), ([], 0),
            "a rejected or read-only form reached a real freeze",
        )


class RejectedFormsTests(_GrammarCase):
    """Every form the old `[ $# -eq 2 ]` gate used to reject, still rejected —
    now in Python, where the wrapper can no longer do it."""

    REJECTED = [
        ["freeze", "--all", "--dry-rnu"],      # the typo that froze everything
        ["freeze", "%5", "--dry-run"],         # --dry-run is --all-only
        ["freeze", "--all", "--dry-run", "x"],  # trailing junk
        ["freeze", "%5", "%6"],                # two panes
        ["freeze", "--every"],                 # unknown flag
        ["freeze", "-%5"],                     # flag-shaped pane id
        ["freeze"],                            # no argument
        ["freeze", "--dry-run"],               # dry-run with no target
    ]

    def test_each_rejected_form_exits_two_and_mutates_nothing(self):
        for argv in self.REJECTED:
            with self.subTest(argv=argv):
                self.setUp()          # fresh spies per form
                rc, out = self.run_main(argv)
                self.assertEqual(rc, 2, f"{argv} was not rejected")
                self.assertEqual(out, "", "a rejected form printed wire lines")
                self.assertNothingMutated()

    def test_a_typo_is_not_silently_treated_as_the_flag_it_resembles(self):
        """The specific regression: `--dry-rnu` must not fall through to a real
        `--all` freeze the way it did when `main` read only `rest[0]`."""
        rc, _ = self.run_main(["freeze", "--all", "--dry-rnu"])
        self.assertEqual(rc, 2)
        self.assertEqual(self.froze_all, 0,
                         "a mistyped flag reached freeze_all()")


class AcceptedFormsTests(_GrammarCase):

    def test_freeze_one_pane_still_works(self):
        rc, out = self.run_main(["freeze", "%5"])
        self.assertEqual(rc, 0)
        self.assertEqual(self.froze_panes, ["%5"])
        self.assertEqual(self.froze_all, 0)
        self.assertIn("FROZEN:%5", out)

    def test_freeze_all_still_works(self):
        rc, _ = self.run_main(["freeze", "--all"])
        self.assertEqual(rc, 0)
        self.assertEqual(self.froze_all, 1)
        self.assertEqual(self.froze_panes, [])


class DryRunTests(_GrammarCase):
    """`--dry-run` lists the eligible population and mutates nothing."""

    def test_it_freezes_nothing(self):
        self.run_main(["freeze", "--all", "--dry-run"])
        self.assertNothingMutated()

    def test_it_spans_every_session_not_just_one(self):
        """A single-session monitor view cannot see `otherproj`, which is why
        the count must come from the operation rather than from snapshots."""
        _rc, out = self.run_main(["freeze", "--all", "--dry-run"])
        self.assertIn("WOULD_FREEZE:%1|aitasks|agent-pick-1705", out)
        self.assertIn("WOULD_FREEZE:%9|otherproj|agent-pick-42", out)

    def test_a_parked_agent_is_eligible_and_counted(self):
        """`freeze --all` stops parked agents too — the confirmation must not
        understate that by reusing the display's live set."""
        _rc, out = self.run_main(["freeze", "--all", "--dry-run"])
        self.assertIn("WOULD_FREEZE:%2|aitasks|agent-pick-1700", out)

    def test_an_already_frozen_standin_and_a_helper_pane_are_excluded(self):
        _rc, out = self.run_main(["freeze", "--all", "--dry-run"])
        self.assertNotIn("%3", out, "an already-frozen stand-in was listed")
        self.assertNotIn("%4", out, "a non-agent pane was listed")

    def test_the_count_line_is_last_and_matches_the_listing(self):
        rc, out = self.run_main(["freeze", "--all", "--dry-run"])
        self.assertEqual(rc, 0)
        lines = out.strip().splitlines()
        self.assertEqual(lines[-1], "FREEZE_ELIGIBLE:3")
        self.assertEqual(
            sum(1 for ln in lines if ln.startswith("WOULD_FREEZE:")), 3)

    def test_the_listing_reuses_freeze_alls_own_eligibility_rule(self):
        """The anti-drift pin: the dry-run must not restate the rule, or a
        confirmation count could disagree with what confirming does."""
        eligible = agent_freeze.freeze_all_eligible()
        self.assertEqual([p.pane_id for p in eligible], ["%1", "%2", "%9"])

    def test_a_session_that_vanishes_mid_scan_is_skipped_not_fatal(self):
        def boom(session):
            if session == "aitasks":
                raise OSError("session vanished")
            return list(FAKE_PANES[session])

        with patch.object(agent_freeze, "_agent_panes_for", boom):
            rc, out = self.run_main(["freeze", "--all", "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip().splitlines()[-1], "FREEZE_ELIGIBLE:1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
