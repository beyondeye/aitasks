"""Frozen stand-ins are never captured or classified (t1705_7).

The frozen twin of `test_monitor_parked_capture.py`, mirroring it case for case
because the two features share every partition site. One pane, two sources of
truth: parked comes from an App-published set, frozen from the `@aitask_frozen`
pane option already carried on the discovery row — which is why frozen needs no
publish-down and is stable for a whole generation.

Properties asserted on **call arguments and returned state**, never inferred
from timing:

- exclusion — the pane id is absent from the recorded capture calls and from the
  batch handed to `_classify_batch`;
- survival — `commit_snapshots` still emits a snapshot for it, flagged `frozen`
  with the record id carried through, built without touching the idle clock;
- discovery — it stays in `last_discovered_agents()`, so the session-store purge
  cannot reap the record of an agent that is merely frozen.

Two things here are NOT mirror images of the parked suite, and both were defects
found while re-verifying the plan:

`PartitionPrecedenceTests`
    Frozen deliberately COEXISTS with the parked mark, so one pane can satisfy
    both predicates. The partitions must be mutually exclusive with frozen
    first; a parked-first split hands such a pane a `parked=True, frozen=False`
    snapshot and no renderer can recover the lost flag. This is driven through
    the REAL capture path, because constructing a frozen snapshot directly would
    pass while the partition is broken.

`FastPreviewRouteTests`
    There are TWO capture routes. `_fast_preview_refresh` uses
    `capture_pane_classified_async` + `commit_snapshot` (singular), which had no
    state branch at all — so focusing a frozen pane captured it and overwrote its
    snapshot. The guard lives in `monitor_core`, not in the app, so every caller
    inherits it.

Run: python3 tests/test_monitor_frozen_capture.py
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

from unittest.mock import patch  # noqa: E402

from monitor import monitor_core  # noqa: E402
from monitor.monitor_core import (  # noqa: E402
    ClassifyResult, PaneCategory, TmuxMonitor, TmuxPaneInfo,
)

RECORD = "7f3a2c1d"


def pane(session: str, window: str, pane_id: str,
         category: PaneCategory = PaneCategory.AGENT,
         frozen_record: str = "") -> TmuxPaneInfo:
    return TmuxPaneInfo(
        window_index="1", window_name=window, pane_index="0", pane_id=pane_id,
        pane_pid=4242, current_command="node", width=80, height=24,
        category=category, session_name=session, frozen_record=frozen_record,
    )


def _monitor() -> TmuxMonitor:
    return TmuxMonitor(session="demo", multi_session=False)


class FrozenPanePredicateTests(unittest.TestCase):
    """`_is_frozen_pane` reads the pane option, and only for agents."""

    def test_a_stamped_agent_pane_is_frozen(self):
        mon = _monitor()
        self.assertTrue(
            mon._is_frozen_pane(pane("demo", "agent-a", "%1",
                                     frozen_record=RECORD)))

    def test_an_unstamped_agent_pane_is_not(self):
        mon = _monitor()
        self.assertFalse(mon._is_frozen_pane(pane("demo", "agent-a", "%1")))

    def test_a_stamped_non_agent_pane_is_not_frozen(self):
        """The AGENT guard is kept for the reason parked keeps it: a companion
        or shadow pane is never an agent slot, whatever it carries."""
        mon = _monitor()
        self.assertFalse(
            mon._is_frozen_pane(pane("demo", "minimonitor", "%9",
                                     category=PaneCategory.TUI,
                                     frozen_record=RECORD)))

    def test_it_needs_no_publish_down(self):
        """Unlike parked, nothing has to be told about frozen first — which is
        what makes it stable between capture and commit."""
        mon = _monitor()
        p = pane("demo", "agent-a", "%1", frozen_record=RECORD)
        self.assertTrue(mon._is_frozen_pane(p))   # no set_frozen_agents call


class CaptureExclusionTests(unittest.IsolatedAsyncioTestCase):
    """A frozen stand-in reaches neither the capture gather nor the batch."""

    def _monitor(self, panes, shadows=()):
        mon = _monitor()
        self.captured: list[str] = []
        self.batched: list[str] = []

        async def fake_discover(enum_sink=None):
            if enum_sink is not None:
                enum_sink.append(frozenset({"demo"}))
            return list(panes), list(shadows)

        async def fake_capture(pane_id, pane=None):
            self.captured.append(pane_id)
            return (pane_id, f"content-of-{pane_id}")

        async def run_offloaded(fn):
            return fn()

        mon.discover_panes_with_shadows_async = fake_discover
        mon.capture_pane_content_async = fake_capture
        mon._run_offloaded = run_offloaded
        return mon

    async def _run(self, mon):
        real_batch = monitor_core._classify_batch

        def spy(items, patterns):
            self.batched.extend(p.pane_id for p, _, _ in items)
            return real_batch(items, patterns)

        with patch.object(monitor_core, "_classify_batch", spy):
            return await mon.capture_all_classified_async()

    async def test_a_frozen_pane_is_never_captured_or_classified(self):
        live = pane("demo", "agent-live", "%1")
        frozen = pane("demo", "agent-frozen", "%2", frozen_record=RECORD)
        mon = self._monitor([live, frozen])

        await self._run(mon)

        self.assertEqual(self.captured, ["%1"])
        self.assertEqual(self.batched, ["%1"])
        self.assertNotIn("%2", self.captured)
        self.assertNotIn("%2", self.batched)

    async def test_the_control_shows_the_stamp_is_what_removes_it(self):
        """NEGATIVE CONTROL: the same pane, unstamped, IS captured — so the
        assertions above discriminate on `@aitask_frozen` and nothing else."""
        live = pane("demo", "agent-live", "%1")
        other = pane("demo", "agent-frozen", "%2")     # no frozen_record
        mon = self._monitor([live, other])

        await self._run(mon)

        self.assertEqual(sorted(self.captured), ["%1", "%2"])
        self.assertEqual(sorted(self.batched), ["%1", "%2"])

    async def test_a_frozen_pane_still_commits_a_snapshot(self):
        """It must render when the filter is off, so it cannot be routed down
        the `result is None` path that means "the capture failed"."""
        live = pane("demo", "agent-live", "%1")
        frozen = pane("demo", "agent-frozen", "%2", frozen_record=RECORD)
        mon = self._monitor([live, frozen])

        gen, classified = await self._run(mon)
        snaps = mon.commit_snapshots(gen, classified)

        self.assertIn("%2", snaps)
        self.assertTrue(snaps["%2"].frozen)
        self.assertEqual(snaps["%2"].content, "")
        self.assertEqual(snaps["%2"].frozen_record_id, RECORD)

    async def test_the_snapshot_bypasses_the_idle_clock(self):
        """`_apply_bookkeeping` owns `_last_content` and must never see a pane
        with no content: it would reset the change time every tick and make the
        agent look permanently busy the moment it is restored."""
        frozen = pane("demo", "agent-frozen", "%2", frozen_record=RECORD)
        mon = self._monitor([frozen])

        gen, classified = await self._run(mon)
        snaps = mon.commit_snapshots(gen, classified)

        self.assertNotIn("%2", mon._last_content)
        self.assertFalse(snaps["%2"].is_idle)
        self.assertEqual(snaps["%2"].idle_seconds, 0.0)

    async def test_a_frozen_pane_stays_in_discovery(self):
        """Freezing skips only the CAPTURE. The record's own liveness purge
        keys on discovery, so a frozen agent dropping out of it would have its
        record retired while the stand-in is still on screen."""
        frozen = pane("demo", "agent-frozen", "%2", frozen_record=RECORD)
        mon = self._monitor([frozen])

        # The facts are staged per generation and published by the commit, so
        # the commit is part of the observation, not incidental setup.
        gen, classified = await self._run(mon)
        mon.commit_snapshots(gen, classified)

        self.assertIn(("demo", "agent-frozen"), mon.last_discovered_agents())

    async def test_a_shadow_pane_is_never_filtered(self):
        """A shadow is its own pane: a minimonitor following a frozen agent
        keeps its shadow working."""
        frozen = pane("demo", "agent-frozen", "%2", frozen_record=RECORD)
        shadow = pane("demo", "agent-frozen", "%3")
        shadow.shadow_target = "%2"
        mon = self._monitor([frozen], shadows=[shadow])

        await self._run(mon)

        self.assertIn("%3", self.captured)


class PartitionPrecedenceTests(unittest.IsolatedAsyncioTestCase):
    """Frozen and parked are mutually exclusive partitions, frozen first.

    Driven through the REAL capture path on purpose: a renderer test that builds
    a frozen snapshot by hand would pass while the partition silently produced
    a parked one.
    """

    def _monitor(self, panes):
        mon = _monitor()

        async def fake_discover(enum_sink=None):
            if enum_sink is not None:
                enum_sink.append(frozenset({"demo"}))
            return list(panes), []

        async def fake_capture(pane_id, pane=None):
            return (pane_id, "content")

        async def run_offloaded(fn):
            return fn()

        mon.discover_panes_with_shadows_async = fake_discover
        mon.capture_pane_content_async = fake_capture
        mon._run_offloaded = run_offloaded
        return mon

    async def _snaps(self, mon):
        gen, classified = await mon.capture_all_classified_async()
        return mon.commit_snapshots(gen, classified)

    async def test_a_pane_that_is_both_commits_as_frozen(self):
        """THE pin. Frozen coexists with the parked mark by design, and frozen
        is the stronger fact — there is no agent process at all."""
        both = pane("demo", "agent-both", "%1", frozen_record=RECORD)
        mon = self._monitor([both])
        mon.set_parked_agents({("demo", "agent-both")})

        snaps = await self._snaps(mon)

        self.assertTrue(snaps["%1"].frozen)
        self.assertFalse(
            snaps["%1"].parked,
            "the pane was routed down the parked branch; its frozen flag is "
            "gone and no renderer can recover it",
        )
        self.assertEqual(snaps["%1"].frozen_record_id, RECORD)

    async def test_parked_only_still_commits_as_parked(self):
        """NEGATIVE CONTROL: frozen taking precedence must not swallow the
        parked branch for panes that are only parked."""
        parked = pane("demo", "agent-parked", "%1")
        mon = self._monitor([parked])
        mon.set_parked_agents({("demo", "agent-parked")})

        snaps = await self._snaps(mon)

        self.assertTrue(snaps["%1"].parked)
        self.assertFalse(snaps["%1"].frozen)

    async def test_neither_partition_captures_the_other_pane(self):
        """A frozen-and-parked pane must be excluded exactly once, not twice or
        zero times — the `skipped_ids` union is what guarantees that."""
        both = pane("demo", "agent-both", "%1", frozen_record=RECORD)
        parked = pane("demo", "agent-parked", "%2")
        live = pane("demo", "agent-live", "%3")
        mon = self._monitor([both, parked, live])
        mon.set_parked_agents({("demo", "agent-both"), ("demo", "agent-parked")})

        snaps = await self._snaps(mon)

        self.assertEqual(set(snaps), {"%1", "%2", "%3"})
        self.assertTrue(snaps["%1"].frozen)
        self.assertTrue(snaps["%2"].parked)
        self.assertFalse(snaps["%3"].frozen or snaps["%3"].parked)


class FastPreviewRouteTests(unittest.IsolatedAsyncioTestCase):
    """The SECOND capture route — `capture_pane_classified_async` +
    `commit_snapshot` — must honour the same no-capture rule.

    `monitor_app._fast_preview_refresh` uses it and then overwrites
    `_snapshots[pane_id]`, so an unguarded route means focusing a frozen pane
    captures it and replaces its snapshot with an ordinary one.
    """

    def _monitor(self, p):
        mon = _monitor()
        self.captured: list[str] = []

        async def fake_capture(pane_id, capture_lines=None, pane=None):
            self.captured.append(pane_id)
            return (p, "content")

        async def run_offloaded(fn):
            return fn()

        mon._pane_cache[p.pane_id] = p
        mon.capture_pane_content_async = fake_capture
        mon._run_offloaded = run_offloaded
        return mon

    async def test_a_frozen_pane_is_not_captured_on_the_fast_route(self):
        p = pane("demo", "agent-frozen", "%2", frozen_record=RECORD)
        mon = self._monitor(p)

        gen, got, content, result = await mon.capture_pane_classified_async("%2")

        self.assertEqual(self.captured, [],
                         "the frozen pane reached capture_pane_content_async")
        self.assertIs(got, p)
        self.assertEqual(content, "")
        self.assertTrue(result.frozen)

    async def test_the_control_shows_a_live_pane_is_still_captured(self):
        """NEGATIVE CONTROL: without the stamp the fast route behaves exactly
        as before, so the assertion above is about frozen and nothing else."""
        p = pane("demo", "agent-live", "%1")
        mon = self._monitor(p)

        await mon.capture_pane_classified_async("%1")

        self.assertEqual(self.captured, ["%1"])

    async def test_the_single_pane_commit_returns_a_frozen_snapshot(self):
        p = pane("demo", "agent-frozen", "%2", frozen_record=RECORD)
        mon = self._monitor(p)

        gen, got, content, result = await mon.capture_pane_classified_async("%2")
        snap = mon.commit_snapshot(gen, got, content, result)

        self.assertTrue(snap.frozen)
        self.assertEqual(snap.frozen_record_id, RECORD)
        self.assertEqual(snap.content, "")

    async def test_the_single_pane_commit_bypasses_the_idle_clock(self):
        p = pane("demo", "agent-frozen", "%2", frozen_record=RECORD)
        mon = self._monitor(p)

        gen, got, content, result = await mon.capture_pane_classified_async("%2")
        mon.commit_snapshot(gen, got, content, result)

        self.assertNotIn("%2", mon._last_content)

    async def test_a_superseded_generation_still_commits_nothing(self):
        """The frozen branch lands after the generation guard, not before it."""
        p = pane("demo", "agent-frozen", "%2", frozen_record=RECORD)
        mon = self._monitor(p)

        gen, got, content, result = await mon.capture_pane_classified_async("%2")
        mon._next_generation()          # a newer capture reserves
        self.assertIsNone(mon.commit_snapshot(gen, got, content, result))


if __name__ == "__main__":
    unittest.main(verbosity=2)
