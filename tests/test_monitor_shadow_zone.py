"""Tests for the monitor's SHADOW zone (t1216_2).

Covers the third zone added to ``ait monitor``: side-by-side shadow preview,
key targeting, the narrow-split fallback, tail-follow per column, and the
zone-exit state machine.

Four of these pin *lifecycle* assumptions that predate the zone and are the
easiest thing to get wrong when adding one — they are the tests that fail on
the un-fixed code:

* ``_restore_focus`` early-returned only for PREVIEW, so SHADOW fell through to
  the PaneCard path and focus was stolen back on every 3s refresh.
* ``_refresh_data`` rendered only the agent column, so the shadow column went
  stale (or kept showing the previous agent's shadow) while focus sat in the
  pane list.
* ``saved_zone`` is captured before the grace fallback can fire, so handing it
  unchanged to the deferred restore undid the fallback.
* ``set_interval`` binds its callback once, so widening the ``is None`` guard
  left PREVIEW→SHADOW refreshing the wrong column.

All ordering is deterministic through the injectable ``_run_offloaded`` seam —
no sleep-based timing (per ``aidocs/framework/testing_conventions.md``).
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

# Belt-and-braces for t1240: MonitorApp only renames its tmux window when
# constructed with rename_window=True (production launcher), but scrub the
# ambient tmux env too so on_mount takes the deterministic not-inside-tmux
# path regardless of where the suite runs.
os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from monitor.monitor_app import (  # noqa: E402
    SHADOW_ABSENT_GRACE_TICKS,
    SHADOW_MIN_AGENT_COLS,
    ZONE_ORDER,
    MonitorApp,
    Zone,
)
from monitor.monitor_core import (  # noqa: E402
    PaneCategory,
    PaneSnapshot,
    TmuxMonitor,
    TmuxPaneInfo,
)
from monitor.prompt_patterns import all_patterns  # noqa: E402

_AGENT_CONTENT = "agent output line\nworking..."
_SHADOW_CONTENT = "shadow analysis line\nthinking..."


def _pane(
    pane_id: str,
    window_name: str = "agent-1",
    category: PaneCategory = PaneCategory.AGENT,
    shadow_target: str = "",
    width: int = 80,
) -> TmuxPaneInfo:
    idx = int(pane_id.lstrip("%"))
    return TmuxPaneInfo(
        window_index=str(idx), window_name=window_name, pane_index="0",
        pane_id=pane_id, pane_pid=1000 + idx, current_command="bash",
        width=width, height=24, category=category, session_name="demo",
        shadow_target=shadow_target,
    )


def _snap(pane: TmuxPaneInfo, content: str = _AGENT_CONTENT) -> PaneSnapshot:
    return PaneSnapshot(
        pane=pane, content=content, timestamp=0.0, idle_seconds=0.0,
        is_idle=False,
    )


async def _sync_offloaded(fn):
    """Run the offloaded fn synchronously (deterministic seam override)."""
    return fn()


def _make_monitor(panes, shadows, content):
    """A TmuxMonitor wired to scripted panes/shadows/content, no real tmux.

    Mirrors ``test_monitor_shadow_status._make_monitor``. Agent panes go into
    ``_pane_cache`` (as the real ``_parse_list_panes`` does); shadow panes
    deliberately do NOT (cache-boundary invariant).
    """
    mon = TmuxMonitor(
        session="demo", multi_session=False, agent_prefixes=["agent-"],
        prompt_patterns=all_patterns(), idle_threshold=5.0,
    )
    mon._run_offloaded = _sync_offloaded
    for p in panes:
        mon._pane_cache[p.pane_id] = p

    async def discover_with_shadows(*, enum_sink=None):
        # Accepts the real seam's enumeration sink (t1326).
        if enum_sink is not None:
            enum_sink.append(frozenset(
                p.session_name for p in list(panes) + list(shadows)
                if p.session_name))
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


def _make_app(mon) -> MonitorApp:
    """A MonitorApp wired to `mon`, with the tmux-touching seams stubbed."""
    app = MonitorApp(session="demo", project_root=REPO_ROOT)
    app._monitor = mon

    async def _no_focus_request():
        return None

    async def _no_attached():
        return None

    async def _no_mapping():
        return {}

    app._consume_focus_request = _no_focus_request
    app._read_attached_session = _no_attached
    mon.get_session_to_project_mapping_async = _no_mapping
    return app


def _run_mounted(check, *, panes, shadows, content, size=(120, 30)):
    """Mount a MonitorApp over the scripted monitor and run `check`.

    Mounting is required for anything that touches the DOM: `on_key` reads
    `self.screen` (ScreenStackError when unmounted) and every `query_one`
    early-returns on an unmounted app, which would make a test pass vacuously.
    """

    async def runner():
        mon = _make_monitor(panes, shadows, content)
        app = _make_app(mon)
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            await check(app, pilot, mon)

    asyncio.run(runner())


def _one_agent_one_shadow(shadow_width: int = 40):
    agent = _pane("%1", window_name="agent-1")
    shadow = _pane("%9", window_name="agent-1", shadow_target="%1",
                   width=shadow_width)
    content = {"%1": _AGENT_CONTENT, "%9": _SHADOW_CONTENT}
    return [agent], [shadow], content


class _ForwardSpy:
    """Records forward_key calls and which fast refresh got scheduled."""

    def __init__(self, app, mon):
        self.calls: list[tuple[str, str]] = []
        self.scheduled: list[str] = []
        mon.forward_key = self._forward
        app.call_later = self._call_later

    def _forward(self, pane_id, key, character=None):
        self.calls.append((pane_id, key))
        return True

    def _call_later(self, cb, *a, **kw):
        self.scheduled.append(getattr(cb, "__name__", repr(cb)))


class _KeyEvent:
    def __init__(self, key="a", character="a"):
        self.key = key
        self.character = character
        self.stopped = False
        self.prevented = False

    def stop(self):
        self.stopped = True

    def prevent_default(self):
        self.prevented = True


# -- Zone model ---------------------------------------------------------------


class ZoneOrderTests(unittest.TestCase):
    def test_shadow_is_in_zone_order(self):
        self.assertEqual(
            ZONE_ORDER, [Zone.PANE_LIST, Zone.PREVIEW, Zone.SHADOW]
        )

    def test_check_action_disables_bindings_in_shadow_like_preview(self):
        app = MonitorApp(session="demo", project_root=REPO_ROOT)
        app._active_zone = Zone.SHADOW
        # Every non-switch_zone binding is disabled (keys go to tmux).
        self.assertFalse(app.check_action("scroll_preview_tail", ()))
        self.assertTrue(app.check_action("switch_zone", ()))
        app._active_zone = Zone.PANE_LIST
        self.assertTrue(app.check_action("scroll_preview_tail", ()))


class ZoneSkipTests(unittest.TestCase):
    """Tab must skip SHADOW unless a shadow is bound AND the split fits."""

    def _app(self, *, shadow: bool, fits: bool) -> MonitorApp:
        agent = _pane("%1")
        shadow_pane = _pane("%9", shadow_target="%1", width=40)
        mon = _make_monitor([agent], [shadow_pane] if shadow else [], {})
        if shadow:
            mon._shadow_snapshots["%1"] = _snap(shadow_pane, _SHADOW_CONTENT)
        app = _make_app(mon)
        app._focused_pane_id = "%1"
        app._shadow_split_ok = fits
        # Focus/indicator work needs a DOM; not mounted here.
        app._focus_first_in_zone = lambda: None
        app._manage_preview_timer = lambda: None
        app._update_zone_indicators = lambda: None
        return app

    def test_tab_reaches_shadow_when_bound_and_fitting(self):
        app = self._app(shadow=True, fits=True)
        app._active_zone = Zone.PREVIEW
        app._switch_zone(1)
        self.assertEqual(app._active_zone, Zone.SHADOW)

    def test_tab_skips_shadow_when_no_shadow_bound(self):
        app = self._app(shadow=False, fits=True)
        app._active_zone = Zone.PREVIEW
        app._switch_zone(1)
        self.assertEqual(app._active_zone, Zone.PANE_LIST)

    def test_tab_skips_shadow_when_split_does_not_fit(self):
        app = self._app(shadow=True, fits=False)
        app._active_zone = Zone.PREVIEW
        app._switch_zone(1)
        self.assertEqual(app._active_zone, Zone.PANE_LIST)

    def test_shift_tab_cycles_backwards_through_shadow(self):
        app = self._app(shadow=True, fits=True)
        app._active_zone = Zone.PANE_LIST
        app._switch_zone(-1)
        self.assertEqual(app._active_zone, Zone.SHADOW)
        app._switch_zone(-1)
        self.assertEqual(app._active_zone, Zone.PREVIEW)

    def test_shift_tab_skips_shadow_when_unavailable(self):
        app = self._app(shadow=False, fits=True)
        app._active_zone = Zone.PANE_LIST
        app._switch_zone(-1)
        self.assertEqual(app._active_zone, Zone.PREVIEW)


# -- Key targeting ------------------------------------------------------------


class KeyTargetingTests(unittest.TestCase):
    def _run(self, check):
        panes, shadows, content = _one_agent_one_shadow()

        async def wrapped(app, pilot, mon):
            app._focused_pane_id = "%1"
            await app._refresh_data()
            await pilot.pause()
            spy = _ForwardSpy(app, mon)
            await check(app, pilot, mon, spy)

        _run_mounted(wrapped, panes=panes, shadows=shadows, content=content)

    def test_shadow_zone_forwards_to_shadow_pane(self):
        async def check(app, pilot, mon, spy):
            app._active_zone = Zone.SHADOW
            app.on_key(_KeyEvent("a", "a"))
            self.assertEqual(spy.calls, [("%9", "a")])
            # The SCHEDULED refresh must match the targeted column.
            self.assertEqual(spy.scheduled, ["_fast_shadow_refresh"])

        self._run(check)

    def test_preview_zone_forwards_to_agent_pane(self):
        async def check(app, pilot, mon, spy):
            app._active_zone = Zone.PREVIEW
            app.on_key(_KeyEvent("b", "b"))
            self.assertEqual(spy.calls, [("%1", "b")])
            self.assertEqual(spy.scheduled, ["_fast_preview_refresh"])

        self._run(check)

    def test_absent_shadow_drops_keys_and_never_hits_the_agent(self):
        """Safety property: a key typed at a vanished shadow must NOT reach the
        agent pane. Asserted against the agent pane id specifically — a bare
        "not called" check would also pass if forwarding were simply broken."""

        async def check(app, pilot, mon, spy):
            mon._shadow_snapshots.clear()  # shadow gone
            app._active_zone = Zone.SHADOW
            event = _KeyEvent("x", "x")
            app.on_key(event)
            self.assertEqual(spy.calls, [])
            self.assertNotIn("%1", [c[0] for c in spy.calls])
            # Swallowed, not fallen through.
            self.assertTrue(event.stopped)
            self.assertTrue(event.prevented)

        self._run(check)

    def test_current_shadow_pane_id_uses_focused_pane_not_focused_widget(self):
        async def check(app, pilot, mon, spy):
            app._active_zone = Zone.SHADOW
            # _get_focused_pane_id() reads self.focused and returns None
            # whenever focus is off a PaneCard — which is ALWAYS the case in a
            # preview zone. Pin that the resolver does not consult it: force it
            # to None and the shadow must still resolve. An implementation
            # built on _get_focused_pane_id() returns None here.
            app._get_focused_pane_id = lambda: None
            self.assertEqual(app._current_shadow_pane_id(), "%9")

        self._run(check)


class FocusDisambiguationTests(unittest.TestCase):
    """Both columns are PreviewPanel instances — the zone must come from the id."""

    def _app(self):
        agent = _pane("%1")
        shadow_pane = _pane("%9", shadow_target="%1")
        mon = _make_monitor([agent], [shadow_pane], {})
        mon._shadow_snapshots["%1"] = _snap(shadow_pane, _SHADOW_CONTENT)
        app = _make_app(mon)
        app._focused_pane_id = "%1"
        app._manage_preview_timer = lambda: None
        app._update_zone_indicators = lambda: None
        return app

    def test_focusing_shadow_panel_sets_shadow_zone(self):
        from monitor.monitor_app import PreviewPanel

        app = self._app()
        widget = PreviewPanel("", id="shadow-preview")
        app.on_descendant_focus(type("E", (), {"widget": widget})())
        self.assertEqual(app._active_zone, Zone.SHADOW)
        self.assertEqual(app._active_preview_zone, Zone.SHADOW)

    def test_focusing_agent_panel_sets_preview_zone(self):
        from monitor.monitor_app import PreviewPanel

        app = self._app()
        widget = PreviewPanel("", id="content-preview")
        app.on_descendant_focus(type("E", (), {"widget": widget})())
        self.assertEqual(app._active_zone, Zone.PREVIEW)
        self.assertEqual(app._active_preview_zone, Zone.PREVIEW)


# -- Tail-follow per column ---------------------------------------------------


class TailFollowTests(unittest.TestCase):
    def _run(self, check):
        panes, shadows, content = _one_agent_one_shadow()

        async def wrapped(app, pilot, mon):
            app._focused_pane_id = "%1"
            await app._refresh_data()
            await pilot.pause()
            app.notify = lambda *a, **kw: None
            scheduled: list[str] = []
            app.call_later = lambda cb, *a, **kw: scheduled.append(
                getattr(cb, "__name__", repr(cb))
            )
            await check(app, pilot, mon, scheduled)

        _run_mounted(wrapped, panes=panes, shadows=shadows, content=content)

    def test_tail_targets_agent_column_and_leaves_shadow_untouched(self):
        async def check(app, pilot, mon, scheduled):
            app._active_preview_zone = Zone.PREVIEW
            app._shadow_scroll_state["%9"] = (False, "anchor")
            app.action_scroll_preview_tail()
            self.assertEqual(app._preview_scroll_state.get("%1"), (True, None))
            self.assertEqual(app._shadow_scroll_state.get("%9"), (False, "anchor"))
            self.assertEqual(scheduled, ["_fast_preview_refresh"])

        self._run(check)

    def test_tail_targets_shadow_column_and_leaves_agent_untouched(self):
        async def check(app, pilot, mon, scheduled):
            app._active_preview_zone = Zone.SHADOW
            app._preview_scroll_state["%1"] = (False, "anchor")
            app.action_scroll_preview_tail()
            self.assertEqual(app._shadow_scroll_state.get("%9"), (True, None))
            self.assertEqual(app._preview_scroll_state.get("%1"), (False, "anchor"))
            self.assertEqual(scheduled, ["_fast_shadow_refresh"])

        self._run(check)

    def test_tail_target_resets_to_agent_when_shadow_column_hidden(self):
        async def check(app, pilot, mon, scheduled):
            app._active_preview_zone = Zone.SHADOW
            app._apply_shadow_visibility(None)  # no shadow → hide
            self.assertEqual(app._active_preview_zone, Zone.PREVIEW)
            self.assertFalse(app.query_one("#shadow-col").display)

        self._run(check)


# -- Zone exit state machine --------------------------------------------------


class ZoneExitTests(unittest.TestCase):
    def _app(self):
        agent = _pane("%1")
        shadow_pane = _pane("%9", shadow_target="%1")
        mon = _make_monitor([agent], [shadow_pane], {})
        mon._shadow_snapshots["%1"] = _snap(shadow_pane, _SHADOW_CONTENT)
        app = _make_app(mon)
        app._focused_pane_id = "%1"
        app._snapshots = {"%1": _snap(agent)}
        app._active_zone = Zone.SHADOW
        app._shadow_zone_agent_id = "%1"
        self.notices: list[str] = []
        app.notify = lambda msg, *a, **kw: self.notices.append(msg)
        app.call_after_refresh = lambda *a, **kw: None
        app._focus_first_in_zone = lambda: None
        app._manage_preview_timer = lambda: None
        return app

    def test_one_absent_tick_holds_the_zone(self):
        app = self._app()
        app._monitor._shadow_snapshots.clear()
        zone = app._reconcile_shadow_state()
        self.assertEqual(zone, Zone.SHADOW)
        self.assertEqual(app._shadow_absent_ticks, 1)
        self.assertEqual(self.notices, [])

    def test_grace_exhausted_falls_back_and_notifies_once(self):
        app = self._app()
        app._monitor._shadow_snapshots.clear()
        for _ in range(SHADOW_ABSENT_GRACE_TICKS):
            zone = app._reconcile_shadow_state()
        self.assertEqual(zone, Zone.PREVIEW)
        self.assertEqual(len(self.notices), 1)

    def test_snapshot_returning_mid_grace_resets_the_counter(self):
        app = self._app()
        saved = app._monitor._shadow_snapshots["%1"]
        app._monitor._shadow_snapshots.clear()
        app._reconcile_shadow_state()
        self.assertEqual(app._shadow_absent_ticks, 1)
        app._monitor._shadow_snapshots["%1"] = saved
        app._reconcile_shadow_state()
        self.assertEqual(app._shadow_absent_ticks, 0)
        self.assertEqual(app._active_zone, Zone.SHADOW)

    def test_selection_moving_to_shadowless_agent_exits_immediately(self):
        app = self._app()
        app._focused_pane_id = "%2"  # a different agent, no shadow bound
        zone = app._reconcile_shadow_state()
        self.assertEqual(zone, Zone.PREVIEW)
        # Immediate — not after the grace window.
        self.assertEqual(len(self.notices), 1)

    def test_reconcile_returns_the_zone_for_saved_zone_rebinding(self):
        """_refresh_data rebinds saved_zone from this return value; without it
        the deferred _restore_focus would undo the fallback."""
        app = self._app()
        app._monitor._shadow_snapshots.clear()
        for _ in range(SHADOW_ABSENT_GRACE_TICKS):
            zone = app._reconcile_shadow_state()
        self.assertEqual(zone, app._active_zone)
        self.assertEqual(zone, Zone.PREVIEW)


# -- Timer handoff ------------------------------------------------------------


class TimerHandoffTests(unittest.IsolatedAsyncioTestCase):
    """set_interval binds its callback ONCE — the dispatcher is what makes a
    PREVIEW<->SHADOW transition change which column refreshes."""

    def _app(self):
        agent = _pane("%1")
        shadow_pane = _pane("%9", shadow_target="%1")
        mon = _make_monitor([agent], [shadow_pane], {})
        mon._shadow_snapshots["%1"] = _snap(shadow_pane, _SHADOW_CONTENT)
        app = _make_app(mon)
        app._focused_pane_id = "%1"
        self.ran: list[str] = []

        async def _fake_preview():
            self.ran.append("preview")

        async def _fake_shadow():
            self.ran.append("shadow")

        app._fast_preview_refresh = _fake_preview
        app._fast_shadow_refresh = _fake_shadow
        return app

    async def test_dispatch_follows_the_active_zone_in_both_directions(self):
        app = self._app()
        app._active_zone = Zone.PREVIEW
        await app._fast_zone_refresh()
        app._active_zone = Zone.SHADOW
        await app._fast_zone_refresh()
        app._active_zone = Zone.PREVIEW
        await app._fast_zone_refresh()
        self.assertEqual(self.ran, ["preview", "shadow", "preview"])

    async def test_dispatch_is_inert_outside_the_preview_zones(self):
        app = self._app()
        app._active_zone = Zone.PANE_LIST
        await app._fast_zone_refresh()
        self.assertEqual(self.ran, [])

    async def test_negative_control_a_bound_callback_cannot_switch_columns(self):
        """The rejected design: one interval bound directly to
        _fast_preview_refresh. Calling it under Zone.SHADOW still refreshes the
        AGENT column — which is exactly the bug the dispatcher prevents."""
        app = self._app()
        bound = app._fast_preview_refresh  # what set_interval would capture
        app._active_zone = Zone.SHADOW
        await bound()
        self.assertEqual(self.ran, ["preview"])  # wrong column, as predicted

    async def test_timer_is_created_with_the_dispatcher_not_a_column(self):
        """Discriminating: set_interval binds ONCE, so it must receive the
        zone-reading dispatcher. Binding _fast_preview_refresh (or
        _fast_shadow_refresh) directly is the bug — the interval could then
        never change columns."""
        app = self._app()
        created: list[object] = []

        def _set_interval(delay, callback, *a, **kw):
            created.append(callback)
            return object()

        app.set_interval = _set_interval
        app._active_zone = Zone.SHADOW
        app._manage_preview_timer()
        self.assertEqual(len(created), 1)
        # Bound methods are re-created on each attribute access, so compare the
        # underlying function rather than object identity.
        self.assertIs(created[0].__func__, MonitorApp._fast_zone_refresh)
        self.assertIsNotNone(app._preview_timer)

    async def test_timer_stopped_outside_the_preview_zones(self):
        app = self._app()
        app.set_interval = lambda *a, **kw: object()
        app._active_zone = Zone.SHADOW
        app._manage_preview_timer()
        self.assertIsNotNone(app._preview_timer)
        stopped = []
        app._preview_timer = type("T", (), {"stop": lambda s: stopped.append(1)})()
        app._active_zone = Zone.PANE_LIST
        app._manage_preview_timer()
        self.assertEqual(stopped, [1])
        self.assertIsNone(app._preview_timer)


# -- Fast shadow refresh ------------------------------------------------------


class FastShadowRefreshTests(unittest.IsolatedAsyncioTestCase):
    async def test_none_result_never_hides_or_clears(self):
        """refresh_shadow_snapshot returns None for four reasons and all mean
        'no update this tick' — the full refresh owns deletion (t1216_1 rule 5).
        """
        agent = _pane("%1")
        shadow_pane = _pane("%9", shadow_target="%1")
        mon = _make_monitor([agent], [shadow_pane], {})
        mon._shadow_snapshots["%1"] = _snap(shadow_pane, _SHADOW_CONTENT)
        app = _make_app(mon)
        app._focused_pane_id = "%1"
        rendered = []
        app._update_shadow_preview = lambda: rendered.append(1)

        async def _none(pane_id):
            return None

        mon.refresh_shadow_snapshot = _none
        await app._fast_shadow_refresh()
        # Snapshot untouched, nothing re-rendered.
        self.assertIsNotNone(mon.get_shadow_snapshot("%1"))
        self.assertEqual(rendered, [])

    async def test_refresh_shadow_snapshot_never_bumps_capture_generation(self):
        agent = _pane("%1")
        shadow_pane = _pane("%9", shadow_target="%1")
        content = {"%1": _AGENT_CONTENT, "%9": _SHADOW_CONTENT}
        mon = _make_monitor([agent], [shadow_pane], content)
        await mon.capture_all_async()
        before = mon.capture_generation
        await mon.refresh_shadow_snapshot("%1")
        self.assertEqual(mon.capture_generation, before)


# -- Discovery-drop negative control ------------------------------------------


class DiscoveryDropTests(unittest.IsolatedAsyncioTestCase):
    async def test_adding_the_zone_leaves_shadows_out_of_agent_state(self):
        """The zone must not un-hide shadows from the pane list / _snapshots /
        _pane_cache — t1118 depends on the discovery-drop invariant."""
        agent = _pane("%1")
        shadow_pane = _pane("%9", shadow_target="%1")
        content = {"%1": _AGENT_CONTENT, "%9": _SHADOW_CONTENT}
        mon = _make_monitor([agent], [shadow_pane], content)
        snaps = await mon.capture_all_async()
        self.assertIn("%1", snaps)
        self.assertNotIn("%9", snaps)
        self.assertNotIn("%9", mon._pane_cache)
        self.assertIsNotNone(mon.get_shadow_snapshot("%1"))


# -- Mounted (real DOM) tests -------------------------------------------------


class MountedShadowColumnTests(unittest.TestCase):
    """Mounted-pilot tests: layout, visibility, focus survival, refresh path."""

    def _run(self, coro_factory, size=(120, 30)):
        async def runner():
            agent = _pane("%1", window_name="agent-1")
            agent2 = _pane("%2", window_name="agent-2")
            shadow1 = _pane("%9", window_name="agent-1",
                            shadow_target="%1", width=40)
            shadow2 = _pane("%12", window_name="agent-2",
                            shadow_target="%2", width=40)
            content = {
                "%1": _AGENT_CONTENT, "%2": _AGENT_CONTENT,
                "%9": _SHADOW_CONTENT, "%12": "shadow TWO content\nsecond",
            }
            mon = _make_monitor(
                [agent, agent2], [shadow1, shadow2], content
            )
            app = _make_app(mon)
            async with app.run_test(size=size) as pilot:
                await pilot.pause()
                await coro_factory(app, pilot, mon)

        asyncio.run(runner())

    def test_shadow_column_shown_and_sized_from_real_pane_width(self):
        async def check(app, pilot, mon):
            app._focused_pane_id = "%1"
            await app._refresh_data()
            await pilot.pause()
            col = app.query_one("#shadow-col")
            self.assertTrue(col.display)
            # width == shadow pane width + 1 gutter
            self.assertEqual(col.styles.width.value, 41)

        self._run(check)

    def test_shadow_column_hidden_when_agent_has_no_shadow(self):
        async def check(app, pilot, mon):
            mon._shadow_snapshots.clear()
            app._focused_pane_id = "%1"
            app._apply_shadow_visibility(None)
            await pilot.pause()
            self.assertFalse(app.query_one("#shadow-col").display)

        self._run(check)

    def test_agent_column_ids_survive_the_restructure(self):
        async def check(app, pilot, mon):
            for wid in ("#content-section", "#preview-scroll",
                        "#content-preview", "#content-header",
                        "#preview-row", "#agent-col", "#shadow-col",
                        "#shadow-scroll", "#shadow-preview", "#shadow-header"):
                self.assertIsNotNone(app.query_one(wid), wid)

        self._run(check)

    def test_focus_survives_a_full_refresh_in_the_shadow_zone(self):
        """Without a SHADOW branch in _restore_focus this fails: focus lands on
        a PaneCard and the zone reverts to PANE_LIST on every 3s tick."""

        async def check(app, pilot, mon):
            app._focused_pane_id = "%1"
            await app._refresh_data()
            await pilot.pause()
            app._active_zone = Zone.SHADOW
            app._shadow_zone_agent_id = "%1"
            app.query_one("#shadow-preview").focus()
            await pilot.pause()
            await app._refresh_data()
            await pilot.pause()
            self.assertEqual(app._active_zone, Zone.SHADOW)
            self.assertEqual(app.focused.id, "shadow-preview")

        self._run(check)

    def test_full_refresh_renders_the_shadow_column_from_the_pane_list(self):
        """Focus never leaves PANE_LIST, so the 0.3s tick never runs — the 3s
        refresh must render the column, and must follow the selection."""

        async def check(app, pilot, mon):
            app._focused_pane_id = "%1"
            await app._refresh_data()
            await pilot.pause()
            preview = app.query_one("#shadow-preview")
            self.assertIn("shadow analysis line", preview.render().plain)

            # Move the selection to the second agent by focusing its real card,
            # so _restore_focus does not revert _focused_pane_id underneath us.
            app._pane_cards["%2"].focus()
            await pilot.pause()
            await app._refresh_data()
            await pilot.pause()
            await pilot.pause()
            self.assertEqual(app._focused_pane_id, "%2")
            self.assertIn("shadow TWO content", preview.render().plain)

        self._run(check)

    def test_hold_keeps_focus_and_column_up_for_the_first_absent_tick(self):
        """The grace window is only meaningful if the column stays up and keeps
        focus while holding — otherwise a one-tick capture blip ejects the user,
        which is the bug the grace window exists to prevent."""

        async def check(app, pilot, mon):
            app._focused_pane_id = "%1"
            await app._refresh_data()
            await pilot.pause()
            app._active_zone = Zone.SHADOW
            app._shadow_zone_agent_id = "%1"
            app.query_one("#shadow-preview").focus()
            await pilot.pause()

            async def _no_shadows(*, enum_sink=None):
                if enum_sink is not None:
                    enum_sink.append(frozenset(
                        p.session_name for p in mon._pane_cache.values()
                        if p.session_name))
                return list(mon._pane_cache.values()), []

            mon.discover_panes_with_shadows_async = _no_shadows
            await app._refresh_data()  # first absent tick → HOLD
            await pilot.pause()

            self.assertEqual(app._active_zone, Zone.SHADOW)
            self.assertTrue(app.query_one("#shadow-col").display)
            self.assertEqual(app.focused.id, "shadow-preview")
            self.assertIn(
                "shadow unavailable",
                app.query_one("#shadow-preview").render().plain,
            )

        self._run(check)

    def test_resize_during_the_grace_hold_does_not_collapse_it(self):
        """A terminal resize mid-hold must not end the grace window early.

        The resize-driven fit check and the 3s reconcile both feed
        _apply_shadow_visibility. If the resize path derives width=None while
        the snapshot is momentarily absent (instead of reusing the last known
        width), it hides the column and _leave_shadow_zone fires — so the
        two-refresh hold would last only until the user happened to resize.
        """

        async def check(app, pilot, mon):
            app._focused_pane_id = "%1"
            await app._refresh_data()
            await pilot.pause()
            app._active_zone = Zone.SHADOW
            app._shadow_zone_agent_id = "%1"
            app.query_one("#shadow-preview").focus()
            await pilot.pause()

            async def _no_shadows(*, enum_sink=None):
                if enum_sink is not None:
                    enum_sink.append(frozenset(
                        p.session_name for p in mon._pane_cache.values()
                        if p.session_name))
                return list(mon._pane_cache.values()), []

            mon.discover_panes_with_shadows_async = _no_shadows

            # ONE absent full refresh — inside the grace window.
            await app._refresh_data()
            await pilot.pause()
            self.assertEqual(app._active_zone, Zone.SHADOW)

            # Resize while still holding, staying comfortably wide enough that
            # the split itself still fits.
            await pilot.resize_terminal(118, 30)
            await pilot.pause()
            await pilot.pause()

            self.assertEqual(
                app._active_zone, Zone.SHADOW,
                "resize during the grace hold must not end the hold",
            )
            self.assertTrue(app.query_one("#shadow-col").display)

        self._run(check)

    def test_restore_focus_refuses_a_hidden_shadow_column(self):
        """_restore_focus is QUEUED with a zone; the deferred visibility check
        can hide the column before it runs (e.g. the terminal narrowed past the
        split threshold). Restoring focus into a hidden column would resurrect
        a zone that was just left."""

        async def check(app, pilot, mon):
            app._focused_pane_id = "%1"
            await app._refresh_data()
            await pilot.pause()
            # Column hidden after the restore was queued.
            app._apply_shadow_visibility(None)
            await pilot.pause()
            self.assertFalse(app._shadow_split_ok)

            app._restore_focus("%1", Zone.SHADOW, False)
            await pilot.pause()

            self.assertEqual(app._active_zone, Zone.PREVIEW)
            self.assertNotEqual(app.focused.id, "shadow-preview")

        self._run(check)

    def test_grace_fallback_hands_the_post_fallback_zone_to_restore_focus(self):
        """`saved_zone` is captured at the TOP of _refresh_data, before the
        grace fallback can fire. It must be rebound from
        _reconcile_shadow_state's return value, or the deferred _restore_focus
        is handed SHADOW and re-focuses the column it just left.

        Discriminating on the ARGUMENT rather than the end state: the end state
        is also protected by the visibility hide (a display:none widget cannot
        take focus), so asserting only "focus is not in the shadow column"
        would pass with the rebind removed.
        """

        async def check(app, pilot, mon):
            app._focused_pane_id = "%1"
            await app._refresh_data()
            await pilot.pause()
            app._active_zone = Zone.SHADOW
            app._shadow_zone_agent_id = "%1"

            zones: list[Zone] = []
            real_restore = app._restore_focus

            def spy(pane_id, zone, pane_list_rebuilt=True):
                zones.append(zone)
                return real_restore(pane_id, zone, pane_list_rebuilt)

            app._restore_focus = spy

            # Shadow disappears from discovery entirely.
            async def _no_shadows(*, enum_sink=None):
                if enum_sink is not None:
                    enum_sink.append(frozenset(
                        p.session_name for p in mon._pane_cache.values()
                        if p.session_name))
                return list(mon._pane_cache.values()), []

            mon.discover_panes_with_shadows_async = _no_shadows
            for _ in range(SHADOW_ABSENT_GRACE_TICKS):
                await app._refresh_data()
                await pilot.pause()

            self.assertEqual(app._active_zone, Zone.PREVIEW)
            # The LAST refresh is the one whose reconcile fired the fallback.
            self.assertEqual(zones[-1], Zone.PREVIEW)
            self.assertNotIn(Zone.SHADOW, zones[-1:])

        self._run(check)


class NarrowFallbackTests(unittest.TestCase):
    """The split decision must read the mounted ROW's content width, not the
    screen width. W is derived from measured live chrome — a hardcoded width
    would pass under either implementation and prove nothing."""

    def _probe(self):
        """Return (chrome, shadow_width): chrome = screen width - row width."""
        result = {}

        async def runner():
            agent = _pane("%1")
            shadow1 = _pane("%9", shadow_target="%1", width=40)
            content = {"%1": _AGENT_CONTENT, "%9": _SHADOW_CONTENT}
            mon = _make_monitor([agent], [shadow1], content)
            app = _make_app(mon)
            async with app.run_test(size=(200, 30)) as pilot:
                await pilot.pause()
                row = app.query_one("#preview-row")
                result["chrome"] = 200 - row.content_region.width

        asyncio.run(runner())
        return result["chrome"], 40

    def test_split_flips_at_the_derived_boundary(self):
        chrome, shadow_w = self._probe()
        # avail - (shadow_w + 1) >= SHADOW_MIN_AGENT_COLS
        # avail = W - chrome  =>  W = MIN + shadow_w + 1 + chrome
        threshold = SHADOW_MIN_AGENT_COLS + shadow_w + 1 + chrome
        observed = {}

        async def runner(width, key):
            agent = _pane("%1")
            shadow1 = _pane("%9", shadow_target="%1", width=shadow_w)
            content = {"%1": _AGENT_CONTENT, "%9": _SHADOW_CONTENT}
            mon = _make_monitor([agent], [shadow1], content)
            app = _make_app(mon)
            async with app.run_test(size=(width, 30)) as pilot:
                await pilot.pause()
                app._focused_pane_id = "%1"
                await app._refresh_data()
                await pilot.pause()
                observed[key] = (
                    app.query_one("#shadow-col").display,
                    app.query_one("#agent-col").size.width,
                )

        for width, key in (
            (threshold - 1, "below"), (threshold, "at"), (threshold + 1, "above")
        ):
            asyncio.run(runner(width, key))

        self.assertFalse(observed["below"][0], "must not split below threshold")
        self.assertTrue(observed["at"][0], "must split at threshold")
        self.assertTrue(observed["above"][0], "must split above threshold")
        # The agent column never gets squeezed below the floor while split.
        for key in ("at", "above"):
            self.assertGreaterEqual(observed[key][1], SHADOW_MIN_AGENT_COLS)

    def test_on_resize_re_evaluates_on_a_fixed_preset(self):
        """on_resize only called _apply_preview_size for dynamic 'agents:N'
        presets; the shadow-fit check must run on EVERY resize or narrowing the
        terminal on the default preset never re-decides the split."""
        chrome, shadow_w = self._probe()
        threshold = SHADOW_MIN_AGENT_COLS + shadow_w + 1 + chrome
        seen = {}

        async def runner():
            agent = _pane("%1")
            shadow1 = _pane("%9", shadow_target="%1", width=shadow_w)
            content = {"%1": _AGENT_CONTENT, "%9": _SHADOW_CONTENT}
            mon = _make_monitor([agent], [shadow1], content)
            app = _make_app(mon)
            async with app.run_test(size=(threshold + 20, 30)) as pilot:
                await pilot.pause()
                app._focused_pane_id = "%1"
                # Default preset is a FIXED one, not "agents:N".
                spec = app._preview_size_idx
                self.assertFalse(
                    str(spec).startswith("agents:"),
                )
                await app._refresh_data()
                await pilot.pause()
                seen["wide"] = app.query_one("#shadow-col").display
                # Narrow past the threshold — no _refresh_data in between, so
                # only on_resize can flip it.
                await pilot.resize_terminal(threshold - 5, 30)
                await pilot.pause()
                await pilot.pause()
                seen["narrow"] = app.query_one("#shadow-col").display

        asyncio.run(runner())
        self.assertTrue(seen["wide"])
        self.assertFalse(seen["narrow"], "resize must re-decide the split")


if __name__ == "__main__":
    unittest.main()
