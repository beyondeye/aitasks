"""Tests for the shadow-agent status glyph in monitor/minimonitor (t1133).

Covers the discovery parse split (shadow panes returned separately, agent list
unchanged), the cache-boundary invariant (shadow panes never enter
``_pane_cache`` — applink's ``get_pane``/``capture_pane`` stay shadow-blind),
the offloaded shadow classification (golden equivalence vs a direct
synchronous ``classify_content``), lifecycle/staleness semantics, the
duplicate-shadow newest-wins rule, generation-guarded supersession (with a
negative control), and row-level rendering in BOTH TUIs (plain-text order +
markup color proof — ``.plain`` alone cannot prove color).

All ordering is deterministic through the injectable ``_run_offloaded`` seam —
no sleep-based timing (per ``aidocs/framework/testing_conventions.md``).
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

from rich.text import Text  # noqa: E402

from monitor.minimonitor_app import MiniMonitorApp  # noqa: E402
from monitor.monitor_app import MonitorApp  # noqa: E402
from monitor.monitor_core import (  # noqa: E402
    COMPARE_MODE_STRIPPED,
    PaneCategory,
    PaneSnapshot,
    TmuxMonitor,
    TmuxPaneInfo,
    classify_content,
)
from monitor.monitor_shared import (  # noqa: E402
    SHADOW_GLYPH,
    format_shadow_glyph,
    format_state_dot,
)
from monitor.prompt_patterns import all_patterns  # noqa: E402

# Real claude prompt wording (matches the `claude_proceed` pattern) so the
# golden-equivalence test exercises a genuine `all_patterns()` entry.
_PROMPT_CONTENT = "some output\nDo you want to proceed?\n> "
_ACTIVE_CONTENT = "agent output line\nworking..."


def _pane(
    pane_id: str,
    window_name: str = "agent-1",
    category: PaneCategory = PaneCategory.AGENT,
    shadow_target: str = "",
) -> TmuxPaneInfo:
    idx = int(pane_id.lstrip("%"))
    return TmuxPaneInfo(
        window_index=str(idx), window_name=window_name, pane_index="0",
        pane_id=pane_id, pane_pid=1000 + idx, current_command="bash",
        width=80, height=24, category=category, session_name="demo",
        shadow_target=shadow_target,
    )


async def _sync_offloaded(fn):
    """Run the offloaded fn synchronously (deterministic seam override)."""
    return fn()


def _make_monitor(panes, shadows, content, *, patterns=None, idle_threshold=5.0):
    """A TmuxMonitor wired to scripted panes/shadows/content, no real tmux.

    Mirrors ``test_monitor_finalize_offload._make_monitor``, extended with a
    scripted shadow list. Agent panes go into ``_pane_cache`` (as the real
    ``_parse_list_panes`` does); shadow panes deliberately do NOT
    (cache-boundary invariant).
    """
    mon = TmuxMonitor(
        session="demo", multi_session=False, agent_prefixes=["agent-"],
        prompt_patterns=all_patterns() if patterns is None else patterns,
        idle_threshold=idle_threshold,
    )
    mon._run_offloaded = _sync_offloaded
    for p in panes:
        mon._pane_cache[p.pane_id] = p

    async def discover_with_shadows():
        return list(panes), list(shadows)

    async def cap_content(pane_id, capture_lines=None, pane=None):
        if pane_id not in content:
            return None
        if pane is None:
            pane = mon._pane_cache.get(pane_id)
        if pane is None:
            return None
        return pane, content[pane_id]

    mon.discover_panes_with_shadows_async = discover_with_shadows
    mon.capture_pane_content_async = cap_content
    return mon


def _list_panes_line(
    pane_id: str, window_name: str, *, shadow_target: str = "", pid: int = 99999999
) -> str:
    idx = pane_id.lstrip("%")
    return "\t".join([
        idx, window_name, "0", pane_id, str(pid), "bash", "80", "24",
        shadow_target,
    ])


class ParseSplitTests(unittest.TestCase):
    """`_parse_list_panes` returns (agents, shadows); agent list unchanged."""

    def _mon(self):
        return TmuxMonitor(
            session="demo", multi_session=False, agent_prefixes=["agent-"],
            prompt_patterns=[],
        )

    def test_shadow_split_and_negative_control(self):
        mon = self._mon()
        stdout = "\n".join([
            _list_panes_line("%1", "agent-t42"),
            _list_panes_line("%9", "agent-t42", shadow_target="%1"),
            _list_panes_line("%3", "editor"),
        ])
        panes, shadows = mon._parse_list_panes(stdout, "demo")

        # Negative control: the agent-facing list is exactly what the
        # pre-t1133 parse returned — the shadow pane is still excluded.
        self.assertEqual([p.pane_id for p in panes], ["%1", "%3"])
        self.assertTrue(all(p.shadow_target == "" for p in panes))

        # The shadow comes back separately, AGENT-classified, target recorded.
        self.assertEqual(len(shadows), 1)
        shadow = shadows[0]
        self.assertEqual(shadow.pane_id, "%9")
        self.assertEqual(shadow.shadow_target, "%1")
        self.assertEqual(shadow.category, PaneCategory.AGENT)

    def test_cache_boundary_only_agents_enter_pane_cache(self):
        mon = self._mon()
        stdout = "\n".join([
            _list_panes_line("%1", "agent-t42"),
            _list_panes_line("%9", "agent-t42", shadow_target="%1"),
        ])
        mon._parse_list_panes(stdout, "demo")
        self.assertIn("%1", mon._pane_cache)
        self.assertNotIn("%9", mon._pane_cache)


class CacheBoundaryTests(unittest.IsolatedAsyncioTestCase):
    """Cache-backed consumers (applink router/pusher surfaces) stay shadow-blind."""

    async def test_get_pane_and_capture_pane_shadow_blind(self):
        agent = _pane("%1")
        shadow = _pane("%9", shadow_target="%1")
        mon = _make_monitor(
            [agent], [shadow],
            {"%1": _ACTIVE_CONTENT, "%9": _ACTIVE_CONTENT},
        )
        snaps = await mon.capture_all_async()
        self.assertIsNotNone(snaps)
        # Shadow state IS available through the dedicated accessor…
        self.assertIsNotNone(mon.get_shadow_snapshot("%1"))
        # …but every cache-backed surface stays shadow-blind
        # (applink/router.py capture_pane, applink/pusher.py get_pane).
        self.assertNotIn("%9", mon._pane_cache)
        self.assertIsNone(mon.get_pane("%9"))
        self.assertIsNone(mon.capture_pane("%9"))

    async def test_pre_marker_race_evicts_stale_cache_entry(self):
        """A pane discovered BEFORE its shadow marker was stamped (the spawner
        sets `@aitask_shadow_target` after the pane exists) gets cached as a
        normal agent on that tick. The next commit that classifies it as a
        shadow must EVICT that entry — `_clean_stale` alone keeps it because
        the shadow id is in the classified keep-set."""
        agent = _pane("%1")
        shadow = _pane("%9", shadow_target="%1")
        mon = _make_monitor(
            [agent], [shadow],
            {"%1": _ACTIVE_CONTENT, "%9": _ACTIVE_CONTENT},
        )
        # Simulate the pre-marker tick: %9 was cached as a normal agent, with
        # idle bookkeeping and a compare-mode override in place.
        pre_marker = _pane("%9")  # no shadow_target yet
        mon._pane_cache["%9"] = pre_marker
        mon._last_content["%9"] = "old"
        mon._compare_mode_overrides["%9"] = "raw"

        snaps = await mon.capture_all_async()
        self.assertIsNotNone(snaps)
        # Cache-backed maps evicted; shadow-blind again.
        self.assertNotIn("%9", mon._pane_cache)
        self.assertIsNone(mon.get_pane("%9"))
        self.assertIsNone(mon.capture_pane("%9"))
        self.assertNotIn("%9", mon._compare_mode_overrides)
        # Idle bookkeeping deliberately kept (shadow idle detection).
        self.assertIn("%9", mon._last_content)
        self.assertIsNotNone(mon.get_shadow_snapshot("%1"))


class ShadowBatchTests(unittest.IsolatedAsyncioTestCase):
    """Offloaded shadow classification == direct synchronous classify_content."""

    async def test_golden_equivalence_prompt_state(self):
        agent = _pane("%1")
        shadow = _pane("%9", shadow_target="%1")
        mon = _make_monitor(
            [agent], [shadow],
            {"%1": _ACTIVE_CONTENT, "%9": _PROMPT_CONTENT},
        )
        snaps = await mon.capture_all_async()
        self.assertIsNotNone(snaps)

        snap = mon.get_shadow_snapshot("%1")
        self.assertIsNotNone(snap)
        # Independent ground truth: classify the same content directly.
        expected = classify_content(
            _PROMPT_CONTENT, COMPARE_MODE_STRIPPED, all_patterns(),
            PaneCategory.AGENT,
        )
        self.assertTrue(expected.awaiting_input)  # sanity: pattern really fires
        self.assertEqual(snap.awaiting_input, expected.awaiting_input)
        self.assertEqual(snap.awaiting_input_kind, expected.awaiting_input_kind)
        self.assertEqual(snap.pane.pane_id, "%9")

    async def test_active_and_idle_states(self):
        agent = _pane("%1")
        shadow = _pane("%9", shadow_target="%1")
        content = {"%1": _ACTIVE_CONTENT, "%9": _ACTIVE_CONTENT}

        # Active: default threshold, first capture ⇒ idle_seconds ≈ 0.
        mon = _make_monitor([agent], [shadow], content)
        await mon.capture_all_async()
        snap = mon.get_shadow_snapshot("%1")
        self.assertFalse(snap.is_idle)
        self.assertFalse(snap.awaiting_input)

        # Idle: negative threshold makes idle_seconds (0) exceed it — the
        # deterministic seam used across the offload tests (no sleeps).
        mon = _make_monitor([agent], [shadow], content, idle_threshold=-1.0)
        await mon.capture_all_async()
        snap = mon.get_shadow_snapshot("%1")
        self.assertTrue(snap.is_idle)

    async def test_agent_snapshots_never_contain_shadow(self):
        agent = _pane("%1")
        shadow = _pane("%9", shadow_target="%1")
        mon = _make_monitor(
            [agent], [shadow],
            {"%1": _ACTIVE_CONTENT, "%9": _ACTIVE_CONTENT},
        )
        snaps = await mon.capture_all_async()
        self.assertEqual(set(snaps), {"%1"})


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_dead_shadow_disappears_and_bookkeeping_cleaned(self):
        agent = _pane("%1")
        shadow = _pane("%9", shadow_target="%1")
        shadows = [shadow]
        content = {"%1": _ACTIVE_CONTENT, "%9": _ACTIVE_CONTENT}
        mon = _make_monitor([agent], shadows, content)

        # Scripted discover reads the mutable `shadows` list each cycle.
        async def discover_with_shadows():
            return [agent], list(shadows)

        mon.discover_panes_with_shadows_async = discover_with_shadows

        await mon.capture_all_async()
        self.assertIsNotNone(mon.get_shadow_snapshot("%1"))
        self.assertIn("%9", mon._last_content)

        shadows.clear()  # shadow pane died
        await mon.capture_all_async()
        self.assertIsNone(mon.get_shadow_snapshot("%1"))
        self.assertNotIn("%9", mon._last_content)  # idle bookkeeping cleaned

    async def test_transient_capture_failure_hides_icon_for_the_tick(self):
        agent = _pane("%1")
        shadow = _pane("%9", shadow_target="%1")
        content = {"%1": _ACTIVE_CONTENT, "%9": _ACTIVE_CONTENT}
        mon = _make_monitor([agent], [shadow], content)

        await mon.capture_all_async()
        self.assertIsNotNone(mon.get_shadow_snapshot("%1"))

        del content["%9"]  # raw fetch fails this tick
        await mon.capture_all_async()
        # Mirrors failed-agent-pane semantics: no entry this tick (hidden),
        # rather than a preserved snapshot with a frozen idle clock.
        self.assertIsNone(mon.get_shadow_snapshot("%1"))

    async def test_sync_capture_all_clears_shadow_state(self):
        agent = _pane("%1")
        shadow = _pane("%9", shadow_target="%1")
        mon = _make_monitor(
            [agent], [shadow],
            {"%1": _ACTIVE_CONTENT, "%9": _ACTIVE_CONTENT},
        )
        await mon.capture_all_async()
        self.assertIsNotNone(mon.get_shadow_snapshot("%1"))

        # A sync cycle produces no shadow info — the map must be cleared
        # (absent, never stale), not left holding the async-path value.
        mon.discover_panes = lambda: []
        mon.capture_all()
        self.assertIsNone(mon.get_shadow_snapshot("%1"))


class DuplicateShadowTests(unittest.IsolatedAsyncioTestCase):
    async def test_newest_shadow_wins(self):
        agent = _pane("%1")
        old_shadow = _pane("%8", shadow_target="%1")
        new_shadow = _pane("%9", shadow_target="%1")
        mon = _make_monitor(
            [agent], [old_shadow, new_shadow],
            {"%1": _ACTIVE_CONTENT, "%8": _ACTIVE_CONTENT,
             "%9": _ACTIVE_CONTENT},
        )
        await mon.capture_all_async()
        snap = mon.get_shadow_snapshot("%1")
        self.assertEqual(snap.pane.pane_id, "%9")


class SupersessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_stale_commit_leaves_shadow_map_untouched(self):
        agent = _pane("%1")
        shadow = _pane("%9", shadow_target="%1")
        mon = _make_monitor(
            [agent], [shadow],
            {"%1": _ACTIVE_CONTENT, "%9": _ACTIVE_CONTENT},
        )
        gen, classified = await mon.capture_all_classified_async()
        mon._next_generation()  # a newer capture reserved after our produce
        self.assertIsNone(mon.commit_snapshots(gen, classified))
        self.assertIsNone(mon.get_shadow_snapshot("%1"))  # nothing written

    async def test_negative_control_current_commit_lands(self):
        # Identical sequence WITHOUT the superseding reservation: the write
        # lands — proving the guard (not the fixture) is what blocked above.
        agent = _pane("%1")
        shadow = _pane("%9", shadow_target="%1")
        mon = _make_monitor(
            [agent], [shadow],
            {"%1": _ACTIVE_CONTENT, "%9": _ACTIVE_CONTENT},
        )
        gen, classified = await mon.capture_all_classified_async()
        self.assertIsNotNone(mon.commit_snapshots(gen, classified))
        self.assertIsNotNone(mon.get_shadow_snapshot("%1"))


def _snapshot(pane: TmuxPaneInfo, *, awaiting=False, idle=False) -> PaneSnapshot:
    return PaneSnapshot(
        pane=pane, content="x", timestamp=0.0,
        idle_seconds=10.0 if idle else 0.0, is_idle=idle,
        awaiting_input=awaiting,
        awaiting_input_kind="claude_proceed" if awaiting else "",
    )


class _FakeShadowLookupMonitor:
    """Duck-typed monitor for row-render tests: compare-mode + shadow lookup."""

    multi_session = False

    def __init__(self, shadow_by_followed: dict[str, PaneSnapshot]) -> None:
        self._shadow_by_followed = shadow_by_followed

    def get_compare_mode(self, pane_id: str) -> str:
        return "stripped"

    def is_compare_mode_overridden(self, pane_id: str) -> bool:
        return False

    def get_shadow_snapshot(self, followed_pane_id: str):
        return self._shadow_by_followed.get(followed_pane_id)


class FormatterTests(unittest.TestCase):
    def test_shadow_glyph_states_and_absence(self):
        pane = _pane("%9", shadow_target="%1")
        self.assertEqual(format_shadow_glyph(None), "")
        self.assertEqual(
            format_shadow_glyph(_snapshot(pane, awaiting=True)),
            f"[bold magenta]{SHADOW_GLYPH}[/]",
        )
        self.assertEqual(
            format_shadow_glyph(_snapshot(pane, idle=True)),
            f"[yellow]{SHADOW_GLYPH}[/]",
        )
        self.assertEqual(
            format_shadow_glyph(_snapshot(pane)),
            f"[green]{SHADOW_GLYPH}[/]",
        )

    def test_state_dot_matches_pre_refactor_colors(self):
        pane = _pane("%1")
        self.assertEqual(format_state_dot(_snapshot(pane, awaiting=True)),
                         "[bold magenta]●[/]")
        self.assertEqual(format_state_dot(_snapshot(pane, idle=True)),
                         "[yellow]●[/]")
        self.assertEqual(format_state_dot(_snapshot(pane)), "[green]●[/]")


class RowRenderTests(unittest.TestCase):
    """Row-level assertions for both TUIs: plain-text order + markup color.

    ``.plain`` strips Rich styles, so it proves glyph presence/ordering only;
    the color mapping is proven on the raw markup string.
    """

    def _monitor_app(self, shadow_by_followed) -> MonitorApp:
        app = MonitorApp(session="demo", project_root=REPO_ROOT)
        app._monitor = _FakeShadowLookupMonitor(shadow_by_followed)
        return app

    def _mini_app(self, shadow_by_followed) -> MiniMonitorApp:
        app = MiniMonitorApp(session="demo", project_root=REPO_ROOT)
        app._monitor = _FakeShadowLookupMonitor(shadow_by_followed)
        return app

    def test_monitor_row_shadowed_vs_not(self):
        agent_pane = _pane("%1", window_name="agent-t42")
        shadow_snap = _snapshot(_pane("%9", shadow_target="%1"), awaiting=True)
        app = self._monitor_app({"%1": shadow_snap})

        row = app._format_agent_card_text(_snapshot(agent_pane))
        # Color proof (markup): shadow prompt state renders bold magenta.
        self.assertIn(f"[bold magenta]{SHADOW_GLYPH}[/]", row)
        # Order proof (plain): agent dot, then shadow glyph, before the name.
        plain = Text.from_markup(row).plain
        self.assertLess(plain.index("●"), plain.index(SHADOW_GLYPH))
        self.assertLess(plain.index(SHADOW_GLYPH), plain.index("agent-t42"))

        # Non-shadowed row: byte-identical to a no-shadow-map render.
        bare = self._monitor_app({})._format_agent_card_text(
            _snapshot(agent_pane)
        )
        self.assertNotIn(SHADOW_GLYPH, bare)
        other_pane = _pane("%2", window_name="agent-other")
        self.assertEqual(
            app._format_agent_card_text(_snapshot(other_pane)),
            self._monitor_app({})._format_agent_card_text(
                _snapshot(other_pane)
            ),
        )

    def test_minimonitor_row_shadowed_vs_not(self):
        agent_pane = _pane("%1", window_name="agent-t42")
        shadow_snap = _snapshot(_pane("%9", shadow_target="%1"), idle=True)
        app = self._mini_app({"%1": shadow_snap})

        row = app._agent_card_text(_snapshot(agent_pane))
        self.assertIn(f"[yellow]{SHADOW_GLYPH}[/]", row)
        plain = Text.from_markup(row).plain
        self.assertLess(plain.index("●"), plain.index(SHADOW_GLYPH))
        self.assertLess(plain.index(SHADOW_GLYPH), plain.index("agent-t42"))

        bare = self._mini_app({})._agent_card_text(_snapshot(agent_pane))
        self.assertNotIn(SHADOW_GLYPH, bare)

    def test_minimonitor_docked_panel_has_no_shadow_glyph(self):
        # The docked followed-agent panel is static by design — the shadow
        # glyph must never appear there, even when a shadow is bound.
        agent_pane = _pane("%1", window_name="agent-t42")
        shadow_snap = _snapshot(_pane("%9", shadow_target="%1"), awaiting=True)
        app = self._mini_app({"%1": shadow_snap})
        panel = app._own_agent_identity_text(_snapshot(agent_pane))
        self.assertNotIn(SHADOW_GLYPH, panel)
        self.assertNotIn("●", panel)  # no live status at all


class MountedCardRenderTests(unittest.TestCase):
    """Mount the real full-monitor card list and assert the rendered row."""

    def test_mounted_pane_card_shows_two_glyphs(self):
        async def runner():
            agent_pane = _pane("%1", window_name="agent-t42")
            shadow_snap = _snapshot(
                _pane("%9", shadow_target="%1"), awaiting=True
            )
            snapshots = {"%1": _snapshot(agent_pane)}

            app = MonitorApp(session="demo", project_root=REPO_ROOT)
            async with app.run_test(size=(100, 30)) as pilot:
                app._monitor = _FakeShadowLookupMonitor({"%1": shadow_snap})
                app._snapshots = snapshots
                app._focused_pane_id = "%1"
                app._rebuild_pane_list()
                await pilot.pause()
                cards = list(app.query("#pane-list PaneCard"))
                self.assertEqual(len(cards), 1)
                rendered = cards[0].render()
                plain = getattr(
                    rendered, "plain", Text.from_markup(str(rendered)).plain
                )
                self.assertIn(SHADOW_GLYPH, plain)
                self.assertLess(plain.index("●"), plain.index(SHADOW_GLYPH))

        asyncio.run(runner())


if __name__ == "__main__":
    unittest.main(verbosity=1)
