"""Minimonitor status/phase filter and project jump (t2217).

Two features share this module because they share one fixture — the REAL
`MiniMonitorApp` with only its tmux-facing data sources stubbed (the
`_RefreshHost` pattern of tests/test_minimonitor_scroll_preservation.py), so
`_refresh_data`, `_build_list_entries`, the scroll lock, `_rebuild_pane_list` and
the restore all run for real.

* **shift+left / shift+right** cycle `_status_filter` through
  `all → PLAN → IMPLEMENT → POSTIMPL → parked → frozen → all`. A filter change
  is NAVIGATION, not a passive refresh: `FilterTransitionTests` drives two
  disjoint, overflowing result sets and pins that the first result is selected
  AND on screen. `test_the_passive_restore_alone_loses_the_selection` is the
  negative control — with the navigation path patched out, the very same
  scenario leaves the selected card outside the viewport (the defect the review
  of the plan found: `_restore_list_scroll` falls back to `max_scroll_y` when no
  anchor survives, and `_restore_focus` never scrolls).
* **shift+up / shift+down** scroll the previous / next project's session group
  to the top. `JumpVersusRestoreTests` is the plan's post-phase risk
  mitigation: a jump while a restore is pending must retire it, and its
  negative control forces the jump through `force=True` (the restore's own
  bypass) to prove the case discriminates.

Run: python3 tests/test_minimonitor_filter_and_jump.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

# Nothing here may touch the pane the suite runs in (t1240): with TMUX unset the
# app's on_mount takes its "Not inside tmux" early return, so no refresh timer.
os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from textual.binding import Binding  # noqa: E402

from monitor import minimonitor_app as mm  # noqa: E402
from monitor.monitor_core import PaneCategory  # noqa: E402
import workflow_phase  # noqa: E402

TmuxControlState = mm.TmuxControlState


def _snap(pane_id, *, session="s1", index="2", task=None, parked=False,
          frozen=False, category=PaneCategory.AGENT):
    pane = SimpleNamespace(
        pane_id=pane_id,
        session_name=session,
        window_index=index,
        pane_index="0",
        window_name=f"agent-pick-{task or index}",
        category=category,
        current_command="python",
    )
    return SimpleNamespace(
        pane=pane, is_idle=False, idle_seconds=0.0, parked=parked,
        frozen=frozen, frozen_record_id="", content="", awaiting_input=False,
        awaiting_input_kind="", agent_key="", _task=task,
    )


async def _async_empty_mapping():
    return {}


async def _settle(pilot, frames=12):
    for _ in range(frames):
        await pilot.pause()


class _Host(mm.MiniMonitorApp):
    """The real app, data sources stubbed (see the module docstring).

    ``phases`` maps a task id to the phase its agent reports; a pane whose
    task is absent from it resolves UNKNOWN. ``phase_calls`` counts every
    `_phase_for_snap` call, for the once-per-tick pin.
    """

    # Wall-clock out of the fixture (t1774): the fail-safe would otherwise
    # race the restore under a loaded pool.
    _SCROLL_LOCK_TIMEOUT = 3600.0
    _IN_PLACE_LIST_UPDATES = False

    def __init__(self, snaps, phases=None) -> None:
        super().__init__(session="s1", project_root=REPO_ROOT)
        self.snaps = list(snaps)
        self.phases = dict(phases or {})
        self.phase_calls = 0
        self._monitor = SimpleNamespace(
            multi_session=True,
            capture_all_async=self._capture_all_async,
            get_session_to_project_mapping_async=_async_empty_mapping,
            get_compare_mode=lambda pid: "stripped",
            is_compare_mode_overridden=lambda pid: False,
            get_shadow_snapshot=lambda pid: None,
            control_state=lambda: TmuxControlState.CONNECTED,
        )
        by_pane = {s.pane.pane_id: s for s in self.snaps}
        self.info_calls = 0

        def get_task_info(t, s=None):
            # Production's cache hit still stats the task file once per call.
            self.info_calls += 1
            return SimpleNamespace(title=f"task {t}", task_file_abs="")

        self._task_cache = SimpleNamespace(
            get_task_id=lambda w: None,
            get_task_id_for_pane=lambda p: by_pane[p.pane_id]._task,
            get_task_info=get_task_info,
            update_session_mapping=lambda m: None,
        )
        self._gate_cache = SimpleNamespace(summary_for=lambda i: None,
                                           clear=lambda: None)

    async def _capture_all_async(self):
        return {s.pane.pane_id: s for s in self.snaps}

    def _phase_for_snap(self, snap, info):
        self.phase_calls += 1
        return workflow_phase.PhaseSignal(
            phase=self.phases.get(snap._task, "UNKNOWN"))

    # Tmux-facing no-ops.
    def _refresh_marks(self): return None
    def _compute_completed_panes(self): return frozenset()
    async def _update_own_window_info(self): return None
    async def _check_auto_close(self): return None
    def _find_own_window_snapshot(self): return None
    async def _maybe_offer_concerns(self): return None
    async def _maybe_purge_marks(self): return None
    async def _maybe_build_own_agent_panel(self): return None
    def _refresh_own_live_state(self): return None
    def _is_marked(self, snap): return False
    def _mark_kind(self, snap): return mm.agent_marks.KIND_NONE


def _run(snaps, scenario, *, phases=None, size=(40, 14), multi=True):
    async def go():
        app = _Host(snaps, phases)
        app._multi_session = multi
        async with app.run_test(size=size) as pilot:
            await app._refresh_data()
            await _settle(pilot)
            return await scenario(app, pilot)
    return asyncio.run(go())


async def _focus_first(app, pilot):
    """Focus the list's first card and let the deferred focus land."""
    list(_container(app).query(mm.MiniPaneCard))[0].focus(scroll_visible=False)
    await _settle(pilot, 3)


def _listed(app) -> list[str]:
    return [e.key for e in app._build_list_entries() if e.kind == "card"]


def _container(app):
    return app.query_one("#mini-pane-list", mm.MiniPaneList)


def _visible(container, card) -> bool:
    top = container.scroll_y
    region = card.virtual_region
    return region.y >= top and region.bottom <= top + container.size.height


#: One of each kind the filter distinguishes.
MIXED = [
    _snap("%plan", index="2", task="11"),
    _snap("%impl", index="3", task="12"),
    _snap("%post", index="4", task="13"),
    _snap("%unk", index="5", task="14"),
    _snap("%notask", index="6"),
    _snap("%parked", index="7", task="15", parked=True),
    _snap("%frozen", index="8", task="16", frozen=True),
    _snap("%both", index="9", task="17", parked=True, frozen=True),
    _snap("%shell", index="10", category=PaneCategory.OTHER),
]
MIXED_PHASES = {"11": "PLAN", "12": "IMPLEMENT", "13": "POSTIMPL"}


class FilterCycleTests(unittest.TestCase):
    def test_cycle_wraps_both_ways(self):
        async def scenario(app, pilot):
            seen = []
            for _ in range(len(mm._STATUS_FILTERS)):
                await pilot.press("shift+right")
                seen.append(app._status_filter)
            back = []
            await pilot.press("shift+left")
            back.append(app._status_filter)
            return seen, back

        seen, back = _run(MIXED, scenario, phases=MIXED_PHASES)
        self.assertEqual(
            seen, ["PLAN", "IMPLEMENT", "POSTIMPL", "parked", "frozen", "all"])
        self.assertEqual(back, ["frozen"], "shift+left from `all` must wrap")


class FilterSelectionTests(unittest.TestCase):
    """What each stop lists, on `_build_list_entries` directly."""

    def _listing(self, status_filter, hide_inactive=False):
        async def scenario(app, pilot):
            app._hide_inactive = hide_inactive
            app._status_filter = status_filter
            return _listed(app), app._build_list_entries()
        return _run(MIXED, scenario, phases=MIXED_PHASES)

    def test_each_phase_stop_lists_only_matching_live_agents(self):
        for status_filter, expected in (("PLAN", ["%plan"]),
                                        ("IMPLEMENT", ["%impl"]),
                                        ("POSTIMPL", ["%post"])):
            with self.subTest(status_filter=status_filter):
                self.assertEqual(self._listing(status_filter)[0], expected)

    def test_unknown_and_taskless_agents_match_no_phase(self):
        for status_filter in ("PLAN", "IMPLEMENT", "POSTIMPL"):
            listed = self._listing(status_filter)[0]
            self.assertNotIn("%unk", listed)
            self.assertNotIn("%notask", listed)

    def test_parked_and_frozen_stops_are_exclusive_frozen_wins(self):
        self.assertEqual(self._listing("parked")[0], ["%parked"])
        self.assertEqual(self._listing("frozen")[0], ["%frozen", "%both"])

    def test_explicit_parked_frozen_stops_override_P(self):
        self.assertEqual(self._listing("parked", hide_inactive=True)[0],
                         ["%parked"])
        self.assertEqual(self._listing("frozen", hide_inactive=True)[0],
                         ["%frozen", "%both"])

    def test_all_keeps_P_semantics(self):
        listed = self._listing("all", hide_inactive=True)[0]
        self.assertNotIn("%parked", listed)
        self.assertNotIn("%frozen", listed)
        self.assertIn("%unk", listed)
        self.assertIn("%shell", listed)   # OTHER section under `all`

    def test_other_section_hidden_under_any_filter(self):
        for status_filter in mm._STATUS_FILTERS[1:]:
            with self.subTest(status_filter=status_filter):
                listed, entries = self._listing(status_filter)
                self.assertNotIn("%shell", listed)
                self.assertFalse(
                    any(e.kind == "header" for e in entries),
                    "the `other (N)` header survived a filter")

    def test_phase_is_computed_once_per_live_agent_per_build(self):
        async def scenario(app, pilot):
            counts = []
            for status_filter in ("all", "IMPLEMENT"):
                app._status_filter = status_filter
                app.phase_calls = 0
                app._build_list_entries()
                counts.append(app.phase_calls)
            return counts
        counts = _run(MIXED, scenario, phases=MIXED_PHASES)
        # Four live agents carry a task (%plan %impl %post %unk); %notask has
        # none, parked/frozen rows are never captured. Under `all` the card
        # text reuses the filter's value rather than computing it again.
        self.assertEqual(counts, [4, 4])

    def test_task_info_is_resolved_once_per_live_agent_per_build(self):
        """Review finding: the card reuses the filter's task info, so a
        displayed agent costs ONE task-file stat per tick, not two."""
        async def scenario(app, pilot):
            app._status_filter = "all"
            app.info_calls = 0
            entries = app._build_list_entries()
            texts = {e.key: e.text for e in entries if e.kind == "card"}
            return app.info_calls, texts

        calls, texts = _run(MIXED, scenario, phases=MIXED_PHASES)
        # Live task-bearing agents: %plan %impl %post %unk. The two frozen rows
        # (%frozen, %both) resolve their title in the frozen branch, as before.
        self.assertEqual(calls, 4 + 2)
        self.assertIn("task 12", texts["%impl"], "the reused info lost the title")
        self.assertIn("IMPLEMENT", texts["%impl"], "the reused phase was lost")


class FilterIndicatorTests(unittest.TestCase):
    def test_hidden_at_all_and_named_otherwise(self):
        async def scenario(app, pilot):
            line = app.query_one("#mini-filter-status")
            out = [(line.display, line.region.height)]
            await pilot.press("shift+right", "shift+right")
            await _settle(pilot)
            out.append((line.display, line.region.height,
                        str(app._filter_banner_text())))
            await pilot.press("shift+left", "shift+left")
            await _settle(pilot)
            out.append((line.display, line.region.height))
            return out

        hidden, shown, again = _run(MIXED, scenario, phases=MIXED_PHASES)
        self.assertEqual(hidden, (False, 0))
        self.assertEqual(shown, (True, 1, "filter: IMPLEMENT  ⇧←→"))
        self.assertEqual(again, (False, 0))

    def test_shows_the_keys_actually_bound(self):
        app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
        app.BINDINGS = [Binding("ctrl+l", "filter_prev", ""),
                        Binding("ctrl+r", "filter_next", "")]
        app._status_filter = "POSTIMPL"
        self.assertEqual(str(app._filter_banner_text()),
                         "filter: POSTIMPL  ^l/^r")
        app._status_filter = "all"
        self.assertEqual(app._filter_banner_text(), "")


# Two DISJOINT result sets, each overflowing a (40, 14) pane on its own: the
# PLAN agents live in s1/s2 and the IMPLEMENT agents in s3/s4, so no PLAN card
# survives into the IMPLEMENT view and no scroll anchor can carry over.
DISJOINT = (
    [_snap(f"%p{i}", session=f"s{1 + i // 4}", index=str(i + 2), task=f"1{i:02d}")
     for i in range(8)]
    + [_snap(f"%i{i}", session=f"s{3 + i // 4}", index=str(i + 20),
             task=f"2{i:02d}") for i in range(8)]
)
DISJOINT_PHASES = {**{f"1{i:02d}": "PLAN" for i in range(8)},
                   **{f"2{i:02d}": "IMPLEMENT" for i in range(8)}}


class FilterTransitionTests(unittest.TestCase):
    """A filter change selects the first result AND shows it (review finding)."""

    async def _to_plan_bottom(self, app, pilot, *, pin):
        await pilot.press("shift+right")            # all -> PLAN
        await app._refresh_data()
        await _settle(pilot)
        container = _container(app)
        if container.max_scroll_y <= 0:
            raise AssertionError("PLAN view does not overflow — vacuous")
        if pin:
            container.anchor()                      # the user's bottom pin
        else:
            container.scroll_to(y=container.max_scroll_y, animate=False,
                                immediate=True, force=True)
        await _settle(pilot)
        return container

    async def _switch(self, app, pilot):
        await pilot.press("shift+right")            # PLAN -> IMPLEMENT
        await app._refresh_data()
        await _settle(pilot, 20)
        container = _container(app)
        if container.max_scroll_y <= 0:
            raise AssertionError("IMPLEMENT view does not overflow — vacuous")
        cards = list(container.query(mm.MiniPaneCard))
        return {
            "focused": getattr(app.focused, "pane_id", None),
            "first": cards[0].pane_id,
            "visible": _visible(container, app.focused)
            if isinstance(app.focused, mm.MiniPaneCard) else False,
            "scroll_y": container.scroll_y,
            "pending": app._pending_scroll_state,
            "locked": app._list_scroll_lock,
            "pinned": container.is_bottom_pinned,
            "nav": app._filter_nav_target,
        }

    #: List height 9 at (40, 20): the first result fits from the top, so the
    #: view lands at 0 with the project's divider in view.
    ROOMY = (40, 20)
    #: List height 3 at (40, 14) with the filter line: divider + a 3-row card
    #: do not fit, so the view lands on the card's own row instead.
    TIGHT = (40, 14)

    def _scenario(self, pin, size=ROOMY):
        async def scenario(app, pilot):
            await self._to_plan_bottom(app, pilot, pin=pin)
            out = await self._switch(app, pilot)
            card = list(_container(app).query(mm.MiniPaneCard))[0]
            out["card_y"] = card.virtual_region.y
            out["list_h"] = _container(app).size.height
            return out
        return _run(DISJOINT, scenario, phases=DISJOINT_PHASES, size=size)

    def _assert_navigated(self, out, expected_scroll=0):
        self.assertEqual(out["focused"], "%i0")
        self.assertEqual(out["first"], "%i0")
        self.assertTrue(out["visible"],
                        f"the selected first result is off-screen: {out}")
        self.assertEqual(out["scroll_y"], expected_scroll)
        self.assertIsNone(out["pending"])
        self.assertFalse(out["locked"])
        self.assertIsNone(out["nav"], "the navigation was never consumed")

    def test_from_a_scrolled_view_the_first_result_is_selected_and_visible(self):
        self._assert_navigated(self._scenario(pin=False))

    def test_a_tight_pane_lands_on_the_card_itself(self):
        out = self._scenario(pin=False, size=self.TIGHT)
        self.assertLess(out["list_h"], out["card_y"] + 3,
                        "fixture fits divider + card — not the tight case")
        self._assert_navigated(out, expected_scroll=out["card_y"])

    def test_from_a_pinned_view_the_pin_is_released(self):
        out = self._scenario(pin=True)
        self._assert_navigated(out)
        self.assertFalse(out["pinned"],
                         "the old view's bottom pin carried into the results")

    def test_the_passive_restore_alone_loses_the_selection(self):
        """NEGATIVE CONTROL: navigation patched out ⇒ the reported defect."""
        with mock.patch.object(_Host, "_consume_filter_navigation",
                               lambda self: False):
            out = self._scenario(pin=False)
        self.assertEqual(out["focused"], "%i0")
        self.assertFalse(
            out["visible"],
            "the passive restore kept the selection visible on its own — this "
            "fixture no longer reproduces the defect the navigation fixes")

    def test_a_tick_built_under_the_old_filter_does_not_consume(self):
        app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
        app._filter_nav_target = "IMPLEMENT"
        app._entries_filter = "PLAN"          # an in-flight tick's entries
        self.assertFalse(app._consume_filter_navigation())
        self.assertEqual(app._filter_nav_target, "IMPLEMENT")
        app._entries_filter = "IMPLEMENT"     # the next tick's entries
        self.assertTrue(app._consume_filter_navigation())
        self.assertIsNone(app._filter_nav_target)
        self.assertFalse(app._consume_filter_navigation(), "consumed twice")

    def test_a_missed_change_re_ticks_once(self):
        app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
        calls = []
        app.call_later = lambda fn: calls.append(fn)
        app._filter_nav_target = "IMPLEMENT"
        app._entries_filter = "PLAN"
        app._maybe_retick_for_filter()
        app._maybe_retick_for_filter()
        self.assertEqual(len(calls), 1, "a missed change must re-tick ONCE")
        app._entries_filter = "IMPLEMENT"
        app._filter_retick_for = None
        app._maybe_retick_for_filter()
        self.assertEqual(len(calls), 1, "nothing missed ⇒ no re-tick")


# Three projects (sessions), each overflowing-sized group of four agents.
THREE_PROJECTS = [
    _snap(f"%{s}{i}", session=s, index=str(10 * n + i), task=f"{n}{i}")
    for n, s in enumerate(("a", "b", "c"), start=1) for i in range(4)
]


class ProjectJumpTests(unittest.TestCase):
    @staticmethod
    def _groups(app):
        return [(d, [c.pane_id for c in cards])
                for d, cards in app._agent_groups(_container(app))]

    def test_jump_puts_the_next_divider_on_top_and_selects_its_first_card(self):
        async def scenario(app, pilot):
            groups = self._groups(app)
            await _focus_first(app, pilot)
            await pilot.press("shift+down")
            await _settle(pilot)
            return (groups[1][0].virtual_region.y, _container(app).scroll_y,
                    app.focused.pane_id, groups[1][1][0])

        divider_y, scroll_y, focused, expected = _run(THREE_PROJECTS, scenario)
        self.assertEqual(scroll_y, divider_y)
        self.assertEqual(focused, expected)

    def test_jump_wraps_both_ways(self):
        async def scenario(app, pilot):
            groups = self._groups(app)
            firsts = [cards[0] for _d, cards in groups]
            await _focus_first(app, pilot)
            seen = []
            for key in ("shift+up", "shift+down", "shift+down", "shift+down",
                        "shift+down"):
                await pilot.press(key)
                await _settle(pilot, 4)
                seen.append(app.focused.pane_id)
            return firsts, seen

        firsts, seen = _run(THREE_PROJECTS, scenario)
        a, b, c = firsts
        # From a: up wraps to c; then down walks c -> a -> b -> c.
        self.assertEqual(seen, [c, a, b, c, a])

    def test_current_group_comes_from_the_viewport_when_nothing_is_focused(self):
        async def scenario(app, pilot):
            groups = self._groups(app)
            container = _container(app)
            app.set_focus(None)
            container.scroll_to(y=groups[1][0].virtual_region.y, animate=False,
                                immediate=True, force=True)
            await _settle(pilot, 4)
            await pilot.press("shift+down")
            await _settle(pilot)
            return app.focused.pane_id, groups[2][1][0]

        focused, expected = _run(THREE_PROJECTS, scenario)
        self.assertEqual(focused, expected)

    def test_no_op_when_the_list_fits(self):
        async def scenario(app, pilot):
            container = _container(app)
            if container.max_scroll_y > 0:
                raise AssertionError("fixture overflows — not the fits case")
            await _focus_first(app, pilot)
            before = (container.scroll_y, app.focused.pane_id)
            await pilot.press("shift+down")
            await _settle(pilot)
            return before, (container.scroll_y, app.focused.pane_id)

        small = [_snap("%a0", session="a", index="1", task="1"),
                 _snap("%b0", session="b", index="2", task="2")]
        before, after = _run(small, scenario, size=(40, 40))
        self.assertEqual(before, after)

    def test_no_op_in_single_session_mode(self):
        async def scenario(app, pilot):
            container = _container(app)
            self.assertGreater(container.max_scroll_y, 0)
            self.assertEqual(app._agent_groups(container), [])
            await _focus_first(app, pilot)
            before = (container.scroll_y, app.focused.pane_id)
            await pilot.press("shift+down")
            await _settle(pilot)
            return before, (container.scroll_y, app.focused.pane_id)

        # Single-session mode lists only this minimonitor's own session.
        own = [_snap(f"%s{i}", session="s1", index=str(i + 2), task=f"9{i}")
               for i in range(12)]
        before, after = _run(own, scenario, multi=False)
        self.assertEqual(before, after)


class JumpVersusRestoreTests(unittest.TestCase):
    """Post-phase risk mitigation `jump_restore_regression_test` (t2217)."""

    def _pending_restore_scenario(self, app, pilot):
        async def scenario():
            container = _container(app)
            groups = self._groups(app)
            await _focus_first(app, pilot)
            # A restore armed by a tick, aimed at the bottom of the list, not
            # yet run — exactly the state a keypress can land in.
            last = list(container.query(mm.MiniPaneCard))[-1]
            app._pending_scroll_state = (False, last.pane_id, 0, [last.pane_id])
            gen = app._scroll_restore_gen = app._scroll_restore_gen + 1
            app._list_scroll_lock = True
            await pilot.press("shift+down")
            await _settle(pilot, 4)
            # The late restore now runs, as a queued callback would.
            app._restore_list_scroll(gen, 0)
            await _settle(pilot)
            return (container.scroll_y, groups[1][0].virtual_region.y,
                    app._pending_scroll_state, app._list_scroll_lock)
        return scenario()

    @staticmethod
    def _groups(app):
        return ProjectJumpTests._groups(app)

    def test_a_jump_retires_a_pending_restore(self):
        async def scenario(app, pilot):
            return await self._pending_restore_scenario(app, pilot)

        scroll_y, divider_y, pending, locked = _run(THREE_PROJECTS, scenario)
        self.assertEqual(scroll_y, divider_y,
                         "the late restore overwrote the user's jump")
        self.assertIsNone(pending)
        self.assertFalse(locked)

    def test_a_forced_jump_would_be_overwritten(self):
        """NEGATIVE CONTROL: the restore's own bypass does not retire it."""
        real = mm.MiniPaneList.scroll_to

        def forced(self, *args, **kwargs):
            kwargs["force"] = True
            return real(self, *args, **kwargs)

        async def scenario(app, pilot):
            with mock.patch.object(mm.MiniPaneList, "scroll_to", forced):
                return await self._pending_restore_scenario(app, pilot)

        scroll_y, divider_y, _pending, _locked = _run(THREE_PROJECTS, scenario)
        self.assertNotEqual(
            scroll_y, divider_y,
            "a forced jump survived the late restore — the retirement case "
            "above does not discriminate")

    def test_a_jump_releases_the_bottom_pin(self):
        async def scenario(app, pilot):
            container = _container(app)
            container.anchor()
            await _settle(pilot, 4)
            pinned_before = container.is_bottom_pinned
            await _focus_first(app, pilot)
            await pilot.press("shift+up")
            await _settle(pilot)
            return pinned_before, container.is_bottom_pinned

        before, after = _run(THREE_PROJECTS, scenario)
        self.assertTrue(before, "fixture never pinned")
        self.assertFalse(after, "the jump left the list pinned to the bottom")


if __name__ == "__main__":
    unittest.main()
