"""Tests for the monitor UI-thread offload of refresh classify work (t1111_4).

Covers the pure ``classify_content`` extraction, the two-phase
``capture_all_classified_async`` / ``commit_snapshots`` split, and the
reservation-time generation protocol that keeps overlapping / out-of-order
captures from corrupting ``_last_content`` or handing back stale snapshots.

All ordering is driven deterministically through the injectable ``_run_offloaded``
seam and gated ``asyncio.Event``s — no sleep-based timing (per
``aidocs/framework/testing_conventions.md``).
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

import monitor.monitor_core as monitor_core  # noqa: E402
from monitor.monitor_app import MonitorApp  # noqa: E402
from monitor.monitor_core import (  # noqa: E402
    COMPARE_MODE_RAW,
    COMPARE_MODE_STRIPPED,
    ClassifyResult,
    PaneCategory,
    PaneSnapshot,
    TmuxMonitor,
    TmuxPaneInfo,
    classify_content,
)
from monitor.prompt_patterns import all_patterns  # noqa: E402


def _pane(pane_id: str, window_name: str = "agent-1",
          category: PaneCategory = PaneCategory.AGENT) -> TmuxPaneInfo:
    idx = int(pane_id.lstrip("%"))
    return TmuxPaneInfo(
        window_index=str(idx), window_name=window_name, pane_index="0",
        pane_id=pane_id, pane_pid=1000 + idx, current_command="bash",
        width=80, height=24, category=category, session_name="demo",
    )


async def _sync_offloaded(fn):
    """Run the offloaded fn synchronously (deterministic seam override)."""
    return fn()


def _make_monitor(panes, content, *, patterns=None):
    """A TmuxMonitor wired to scripted panes/content, no real tmux.

    ``content`` is a mutable ``{pane_id: str}`` holder so a test can change a
    pane's captured content between capture cycles.
    """
    mon = TmuxMonitor(
        session="demo", multi_session=False, agent_prefixes=["agent-"],
        prompt_patterns=[] if patterns is None else patterns,
    )
    for p in panes:
        mon._pane_cache[p.pane_id] = p

    async def discover(*, include_registered: bool = False):
        return list(panes)

    async def discover_with_shadows():
        # No shadow panes in these fixtures (shadow coverage lives in
        # test_monitor_shadow_status.py, t1133).
        return list(panes), []

    async def cap_content(pane_id, capture_lines=None, pane=None):
        if pane_id not in content:
            return None
        if pane is None:
            pane = mon._pane_cache[pane_id]
        return pane, content[pane_id]

    mon.discover_panes_async = discover
    mon.discover_panes_with_shadows_async = discover_with_shadows
    mon.capture_pane_content_async = cap_content
    return mon


def _gate():
    """Return (offload_fn, release_event, calls) where the FIRST offload call
    blocks on the event and later calls run immediately."""
    release = asyncio.Event()
    calls = {"n": 0}

    async def offload(fn):
        calls["n"] += 1
        if calls["n"] == 1:
            await release.wait()
        return fn()

    return offload, release, calls


class ClassifyContentTests(unittest.TestCase):
    """(a) The pure classifier, headless."""

    def test_strip_prompt_and_category_gate(self):
        patterns = all_patterns()
        # ANSI stripped in stripped mode, kept in raw mode.
        r = classify_content("\x1b[31mhello\x1b[0m", COMPARE_MODE_STRIPPED,
                             patterns, PaneCategory.AGENT)
        self.assertEqual(r.compare_value, "hello")
        r_raw = classify_content("\x1b[31mhello\x1b[0m", COMPARE_MODE_RAW,
                                patterns, PaneCategory.AGENT)
        self.assertIn("\x1b", r_raw.compare_value)
        # Prompt detected for an AGENT pane.
        r_agent = classify_content("Do you want to proceed?", COMPARE_MODE_STRIPPED,
                                  patterns, PaneCategory.AGENT)
        self.assertTrue(r_agent.awaiting_input)
        self.assertTrue(r_agent.awaiting_input_kind)
        # Same text on a non-AGENT pane never triggers the prompt scan.
        r_other = classify_content("Do you want to proceed?", COMPARE_MODE_STRIPPED,
                                  patterns, PaneCategory.OTHER)
        self.assertFalse(r_other.awaiting_input)
        # No-match returns clean.
        r_clean = classify_content("just running\nline2", COMPARE_MODE_STRIPPED,
                                  patterns, PaneCategory.AGENT)
        self.assertFalse(r_clean.awaiting_input)


class TwoPhaseCaptureTests(unittest.IsolatedAsyncioTestCase):
    async def test_golden_equivalence_with_sync_finalize(self):
        """(b) Two-phase capture yields snapshots identical to the sync finalize."""
        patterns = all_patterns()
        panes = [_pane("%1"), _pane("%2", "agent-2")]
        content = {"%1": "\x1b[32malpha\x1b[0m\nrun", "%2": "Do you want to proceed?"}

        ref = _make_monitor(panes, dict(content), patterns=patterns)
        ref_snaps = {p.pane_id: ref._finalize_capture(p, content[p.pane_id]) for p in panes}

        mon = _make_monitor(panes, dict(content), patterns=patterns)
        mon._run_offloaded = _sync_offloaded
        gen, classified = await mon.capture_all_classified_async()
        snaps = mon.commit_snapshots(gen, classified)

        self.assertEqual(set(snaps), {"%1", "%2"})
        for pid in ("%1", "%2"):
            self.assertEqual(snaps[pid].content, ref_snaps[pid].content)
            self.assertEqual(snaps[pid].awaiting_input, ref_snaps[pid].awaiting_input)
            self.assertEqual(snaps[pid].awaiting_input_kind,
                            ref_snaps[pid].awaiting_input_kind)
            self.assertEqual(snaps[pid].is_idle, ref_snaps[pid].is_idle)
        # Compare-value bookkeeping matches the sync reference exactly.
        self.assertEqual(mon._last_content, ref._last_content)

    async def test_idle_bookkeeping_updates_on_change(self):
        """(c) _last_change_time updates on content change; a discarded stale
        cycle does not touch bookkeeping."""
        panes = [_pane("%1")]
        content = {"%1": "A\nx"}
        mon = _make_monitor(panes, content)
        mon._run_offloaded = _sync_offloaded

        g1, c1 = await mon.capture_all_classified_async()
        mon.commit_snapshots(g1, c1)
        t_first = mon._last_change_time["%1"]

        content["%1"] = "B\nx"
        g2, c2 = await mon.capture_all_classified_async()
        mon.commit_snapshots(g2, c2)
        self.assertTrue(mon._last_content["%1"].startswith("B"))
        self.assertGreaterEqual(mon._last_change_time["%1"], t_first)

        # A stale (older-gen) commit must be refused and leave bookkeeping intact.
        content["%1"] = "C\nx"
        g3, c3 = await mon.capture_all_classified_async()  # captured C, gen3
        g4, c4 = await mon.capture_all_classified_async()  # newer gen4, also C
        mon.commit_snapshots(g4, c4)
        t_after = mon._last_change_time["%1"]
        self.assertIsNone(mon.commit_snapshots(g3, c3))
        self.assertEqual(mon._last_change_time["%1"], t_after)


class GenerationOrderingTests(unittest.IsolatedAsyncioTestCase):
    async def test_out_of_order_discarded_with_negative_control(self):
        """(d) Out-of-order resolution: the older cycle's commit is refused; a
        negative control (bypassing the guard) reproduces the corruption."""
        panes = [_pane("%1")]
        mon = _make_monitor(panes, {"%1": "OLD\nx"})
        mon._run_offloaded = _sync_offloaded

        genA, cA = await mon.capture_all_classified_async()   # captured OLD
        # A newer cycle reserves genB and carries NEW content.
        genB, _ = await mon.capture_all_classified_async()    # reserves genB (> genA)
        cB = [(panes[0], "NEW\nx",
               classify_content("NEW\nx", COMPARE_MODE_STRIPPED, mon.prompt_patterns,
                                panes[0].category))]
        self.assertIsNotNone(mon.commit_snapshots(genB, cB))
        self.assertTrue(mon._last_content["%1"].startswith("NEW"))
        # A resolves late, out of order → refused.
        self.assertIsNone(mon.commit_snapshots(genA, cA))
        self.assertTrue(mon._last_content["%1"].startswith("NEW"))

        # Negative control: apply A's OLD result WITHOUT the generation guard.
        pane, cont, result = cA[0]
        mon._apply_bookkeeping(pane, cont, result, 0.0)
        self.assertTrue(mon._last_content["%1"].startswith("OLD"))

    async def test_overlapping_capture_all_async_returns_none(self):
        """(e) Two overlapping capture_all_async on the SAME monitor: the earlier
        (older-reservation) one returns None; a caller that guards on None keeps
        the newer snapshots. Guards minimonitor's own overlapping refresh loop."""
        panes = [_pane("%1")]
        content = {"%1": "OLD\nx"}
        mon = _make_monitor(panes, content)
        offload, release, calls = _gate()
        mon._run_offloaded = offload

        task_a = asyncio.create_task(mon.capture_all_async())  # reserves genA, blocks
        while calls["n"] == 0:
            await asyncio.sleep(0)
        content["%1"] = "NEW\nx"
        res_b = await mon.capture_all_async()  # genB, runs + commits NEW
        self.assertIsNotNone(res_b)
        self.assertTrue(mon._last_content["%1"].startswith("NEW"))

        release.set()
        res_a = await task_a
        self.assertIsNone(res_a)  # stale → None, caller must skip applying it
        self.assertTrue(mon._last_content["%1"].startswith("NEW"))

    async def test_fast_preview_supersedes_full_refresh(self):
        """(f) A fast preview started after a full refresh supersedes it: when the
        older full refresh resolves, its commit is refused. Negative control shows
        the clobber without the guard."""
        panes = [_pane("%1")]
        content = {"%1": "OLD\nx"}
        mon = _make_monitor(panes, content)
        offload, release, calls = _gate()
        mon._run_offloaded = offload

        full = asyncio.create_task(mon.capture_all_classified_async())  # genN, OLD, blocks
        while calls["n"] == 0:
            await asyncio.sleep(0)
        content["%1"] = "NEW\nx"
        gen_p, pane, cont, result = await mon.capture_pane_classified_async("%1")  # genN+1
        self.assertIsNotNone(mon.commit_snapshot(gen_p, pane, cont, result))
        self.assertTrue(mon._last_content["%1"].startswith("NEW"))

        release.set()
        gen_f, classified_f = await full
        self.assertIsNone(mon.commit_snapshots(gen_f, classified_f))  # refused
        self.assertTrue(mon._last_content["%1"].startswith("NEW"))

        # Negative control: apply the full refresh's OLD result unguarded.
        p2, c2, r2 = classified_f[0]
        mon._apply_bookkeeping(p2, c2, r2, 0.0)
        self.assertTrue(mon._last_content["%1"].startswith("OLD"))

    async def test_sync_finalize_supersedes_inflight_offload(self):
        """(g2) A sync capture_pane finalize (router scrollback) during an
        in-flight offloaded refresh bumps the token and writes NEW; the older
        refresh's commit is then refused. Negative control reproduces the clobber."""
        panes = [_pane("%1")]
        mon = _make_monitor(panes, {"%1": "OLD\nx"})
        offload, release, calls = _gate()
        mon._run_offloaded = offload

        full = asyncio.create_task(mon.capture_all_classified_async())  # genN, OLD, blocks
        while calls["n"] == 0:
            await asyncio.sleep(0)
        # sync finalize (bumps + writes atomically)
        mon._finalize_capture(panes[0], "NEW\nx")
        self.assertTrue(mon._last_content["%1"].startswith("NEW"))

        release.set()
        gen_f, classified_f = await full
        self.assertIsNone(mon.commit_snapshots(gen_f, classified_f))  # refused
        self.assertTrue(mon._last_content["%1"].startswith("NEW"))

        p2, c2, r2 = classified_f[0]
        mon._apply_bookkeeping(p2, c2, r2, 0.0)  # negative control
        self.assertTrue(mon._last_content["%1"].startswith("OLD"))

    async def test_capture_pane_async_reserve_before_await(self):
        """(g3) capture_pane_async reserves its gen BEFORE the tmux await, so a
        stale-but-late return can't clobber a newer-reserved refresh. Negative
        control shows reserve-after-await (bump at write) would clobber."""
        panes = [_pane("%1")]
        content = {"%1": "OLD\nx"}
        mon = _make_monitor(panes, content)

        release = asyncio.Event()

        async def blocking_tmux(args, timeout=5.0):
            await release.wait()          # capture-pane blocks
            return 0, "OLD\nx"

        mon._tmux_async = blocking_tmux
        task = asyncio.create_task(mon.capture_pane_async("%1"))  # reserves genA before await
        await asyncio.sleep(0)            # let it reserve + reach the tmux await

        # A newer full refresh reserves genB > genA and commits NEW.
        mon._run_offloaded = _sync_offloaded
        content["%1"] = "NEW\nx"
        genB, cB = await mon.capture_all_classified_async()
        cB = [(panes[0], "NEW\nx",
               classify_content("NEW\nx", COMPARE_MODE_STRIPPED, mon.prompt_patterns,
                                panes[0].category))]
        mon.commit_snapshots(genB, cB)
        self.assertTrue(mon._last_content["%1"].startswith("NEW"))

        release.set()
        snap = await task
        self.assertIsNone(snap)           # older reservation → refused
        self.assertTrue(mon._last_content["%1"].startswith("NEW"))

        # Negative control: reserve-after-await (bump at write) → stale wins.
        mon._next_generation()
        p = panes[0]
        mon._apply_bookkeeping(
            p, "OLD\nx",
            classify_content("OLD\nx", COMPARE_MODE_STRIPPED, mon.prompt_patterns, p.category),
            0.0,
        )
        self.assertTrue(mon._last_content["%1"].startswith("OLD"))

    async def test_per_pane_fail_closed(self):
        """(h) One pane's classify raising degrades only that pane to raw content;
        the other panes classify normally and the refresh is not dropped."""
        panes = [_pane("%1"), _pane("%2", "agent-2")]
        content = {"%1": "good\nx", "%2": "boom\nx"}
        mon = _make_monitor(panes, content)
        mon._run_offloaded = _sync_offloaded

        orig = monitor_core.classify_content

        def flaky(c, mode, patterns, category):
            if c.startswith("boom"):
                raise RuntimeError("bad pane")
            return orig(c, mode, patterns, category)

        monitor_core.classify_content = flaky
        try:
            gen, classified = await mon.capture_all_classified_async()
            snaps = mon.commit_snapshots(gen, classified)
        finally:
            monitor_core.classify_content = orig

        self.assertEqual(set(snaps), {"%1", "%2"})
        self.assertEqual(mon._last_content["%1"], "good\nx")
        self.assertEqual(mon._last_content["%2"], "boom\nx")  # raw fail-closed fallback


class FastPreviewFocusIdentityTests(unittest.IsolatedAsyncioTestCase):
    async def test_focus_change_during_offload_no_cross_pane_ui(self):
        """(g) If focus moves from A to B during the fast-preview offload await,
        the snapshot is committed under A's pinned id and the preview UI is NOT
        updated (focus is now B)."""
        class _FocusFlipMonitor:
            multi_session = False

            def __init__(self, app_ref):
                self._app = app_ref
                self._gen = 0
                self._committed = {}

            @property
            def capture_generation(self):
                return self._gen

            async def capture_pane_classified_async(self, pane_id, capture_lines=None):
                self._gen += 1
                # Simulate a focus change to %2 DURING the offload await.
                self._app["app"]._focused_pane_id = "%2"
                pane = _pane(pane_id)
                return self._gen, pane, f"{pane_id}\ncontent", None

            def commit_snapshot(self, gen, pane, content, result):
                if gen != self._gen:
                    return None
                snap = PaneSnapshot(pane=pane, content=content, timestamp=0.0,
                                    idle_seconds=0.0, is_idle=False)
                self._committed[pane.pane_id] = snap
                return snap

        holder = {}
        app = MonitorApp(session="demo", project_root=REPO_ROOT)
        async with app.run_test(size=(100, 30)):
            holder["app"] = app
            preview_calls = []
            app._update_content_preview = lambda: preview_calls.append(app._focused_pane_id)
            app._monitor = _FocusFlipMonitor(holder)
            app._focused_pane_id = "%1"

            await app._fast_preview_refresh()

            # Snapshot committed under the PINNED id %1 …
            self.assertIn("%1", app._snapshots)
            # … but focus moved to %2 during the await, so no preview UI write.
            self.assertEqual(app._focused_pane_id, "%2")
            self.assertEqual(preview_calls, [])


if __name__ == "__main__":
    unittest.main()
