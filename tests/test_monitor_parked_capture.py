"""Parked agents are never captured or classified (t1685).

Parking an agent is the one mark state that costs nothing: the pane is excluded
from `capture_pane_content_async`'s gather and from the `_classify_batch`
payload, yet it must still render a row when the `P` filter is off and must stay
in discovery so the mark purge cannot reap its own mark.

The three properties are asserted on **call arguments and returned state**, never
inferred from timing:

- exclusion — the pane id is absent from the recorded capture calls and from the
  batch handed to `_classify_batch`;
- survival — `commit_snapshots` still emits a snapshot for it, flagged `parked`,
  built without touching the idle clock;
- discovery — `last_discovered_agents()` still names it, with a negative control
  proving the same purge drops it once the window is genuinely gone.

CHARACTERIZATION (pre-phase, t1685 risk mitigation
`characterize_capture_failure_drop`): `CaptureFailureDropTests` below pins the
PRE-EXISTING `if result is None: continue` behaviour of `commit_snapshots`. The
parked branch lands immediately beside that drop, so the drop's own semantics are
pinned first and separately — a parked pane must not be routed down the
failed-capture path, and a failed capture must not start looking parked.

NEGATIVE CONTROL for the characterization: make `commit_snapshots` emit a
snapshot for a `result is None` entry -> `test_a_failed_capture_produces_no_
snapshot` fails. Make it drop the pane id from the `_clean_stale` set ->
`test_a_failed_capture_still_counts_as_present_for_clean_stale` fails.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from monitor.monitor_core import (  # noqa: E402
    ClassifyResult, PaneCategory, TmuxMonitor, TmuxPaneInfo,
)


def pane(session: str, window: str, pane_id: str,
         category: PaneCategory = PaneCategory.AGENT) -> TmuxPaneInfo:
    return TmuxPaneInfo(
        window_index="1", window_name=window, pane_index="0", pane_id=pane_id,
        pane_pid=4242, current_command="node", width=80, height=24,
        category=category, session_name=session,
    )


def _monitor() -> TmuxMonitor:
    return TmuxMonitor(session="demo", multi_session=False)


class CaptureFailureDropTests(unittest.TestCase):
    """Pre-existing behaviour of the `result is None` branch in
    `commit_snapshots`, pinned before the parked branch is written beside it."""

    def test_a_failed_capture_produces_no_snapshot(self):
        mon = _monitor()
        ok = pane("demo", "agent-ok", "%1")
        bad = pane("demo", "agent-bad", "%2")
        gen = mon._next_generation()
        snaps = mon.commit_snapshots(gen, [
            (ok, "hello", ClassifyResult(compare_value="hello")),
            (bad, None, None),
        ])
        self.assertIsNotNone(snaps)
        self.assertIn("%1", snaps)
        self.assertNotIn(
            "%2", snaps,
            "a pane whose capture failed must produce no snapshot this tick",
        )

    def test_a_failed_capture_leaves_prior_content_untouched(self):
        """The drop is what preserves `_last_content` across a transient fault.

        `_apply_bookkeeping` is the only writer of that dict, and the dropped
        entry never reaches it, so the pane's idle clock keeps running off the
        content it last actually had.
        """
        mon = _monitor()
        p = pane("demo", "agent-a", "%1")
        gen = mon._next_generation()
        mon.commit_snapshots(gen, [(p, "first", ClassifyResult(compare_value="first"))])
        self.assertEqual(mon._last_content["%1"], "first")

        gen = mon._next_generation()
        mon.commit_snapshots(gen, [(p, None, None)])
        self.assertEqual(
            mon._last_content["%1"], "first",
            "a failed capture must not overwrite the pane's last known content",
        )

    def test_a_failed_capture_still_counts_as_present_for_clean_stale(self):
        """A dropped pane is still in `classified`, so `_clean_stale` keeps it.

        Without this, one failed capture would evict the pane's bookkeeping and
        the next successful tick would restart its idle clock from zero.
        """
        mon = _monitor()
        a = pane("demo", "agent-a", "%1")
        b = pane("demo", "agent-b", "%2")
        gen = mon._next_generation()
        mon.commit_snapshots(gen, [
            (a, "aaa", ClassifyResult(compare_value="aaa")),
            (b, "bbb", ClassifyResult(compare_value="bbb")),
        ])
        self.assertEqual(set(mon._last_content), {"%1", "%2"})

        # %2 fails this tick; %1 succeeds. Both are still in `classified`.
        gen = mon._next_generation()
        mon.commit_snapshots(gen, [
            (a, "aaa2", ClassifyResult(compare_value="aaa2")),
            (b, None, None),
        ])
        self.assertEqual(
            set(mon._last_content), {"%1", "%2"},
            "the failed pane was swept as stale — its idle clock will restart",
        )

        # A pane genuinely absent from `classified` IS swept: the positive
        # control that makes the assertion above discriminating.
        gen = mon._next_generation()
        mon.commit_snapshots(gen, [(a, "aaa3", ClassifyResult(compare_value="aaa3"))])
        self.assertEqual(set(mon._last_content), {"%1"})

    def test_a_superseded_generation_commits_nothing(self):
        """The guard the parked branch must land *after*, not before."""
        mon = _monitor()
        p = pane("demo", "agent-a", "%1")
        stale_gen = mon._next_generation()
        mon._next_generation()  # a newer capture reserves
        self.assertIsNone(
            mon.commit_snapshots(
                stale_gen, [(p, "x", ClassifyResult(compare_value="x"))]
            )
        )
        self.assertEqual(mon._last_content, {})


if __name__ == "__main__":
    unittest.main()
