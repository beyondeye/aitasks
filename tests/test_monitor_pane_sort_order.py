"""Pane ordering is numeric, not lexicographic, in both monitor TUIs (t1659).

`TmuxPaneInfo.window_index` / `.pane_index` are **strings** — they come straight
off the tmux gateway's `#{window_index}` / `#{pane_index}` format — and every
pane-ordering site used to compare them as strings. With ten or more agent
windows the list read `…-9, -10, -11, …, -14, -1, -2, …`: it jumped back to low
numbers part-way down (seen live in t1653's 40-agent fixture capture).

The fix is one shared key, `monitor_core.pane_sort_key`, used by tmux discovery
(`TmuxMonitor._PANE_SORT_KEY`) and by BOTH TUIs' `_rebuild_pane_list`. Two
properties of that key are load-bearing and both are pinned here:

* the window/pane slots compare numerically, and
* the order stays **total** for a non-numeric index rather than raising — via a
  category slot, NOT a large sentinel integer. A sentinel is itself a reachable
  decimal index, so `1 << 30` would tie with the literal index "1073741824" and
  let everything larger sort *ahead* of non-numeric text. `SentinelBoundaryTests`
  pins that, so a future "simplification" back to a sentinel cannot pass.

Two of the cases here are the plan's confirmed inline risk mitigations:
`cross_tui_order_parity` (the two TUIs' orders must be equal to EACH OTHER, not
merely each numeric) and `discriminating_fixture_control` (a negative control
proving the fixture separates the new key from the old one — a fixture narrowed
to single-digit indices would pass every other case while proving nothing).

Run: python3 tests/test_monitor_pane_sort_order.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

# MiniMonitorApp/MonitorApp only rename their tmux window when constructed by
# the production launcher, but scrub the ambient tmux env anyway so nothing here
# can touch the pane the suite is running in (t1240).
os.environ.pop("TMUX", None)
os.environ.pop("TMUX_PANE", None)

from monitor import minimonitor_app as mm  # noqa: E402
from monitor.monitor_app import MonitorApp, PaneCard  # noqa: E402
from monitor.tmux_control import TmuxControlState  # noqa: E402
from monitor.tmux_monitor import (  # noqa: E402
    INDEX_RANK_NON_NUMERIC,
    INDEX_RANK_NUMERIC,
    PaneCategory,
    PaneSnapshot,
    TmuxMonitor,
    TmuxPaneInfo,
    pane_sort_key,
    tmux_index_key,
)

#: The one fixture every render case shares. Deliberately spans the single→double
#: digit boundary in both directions: 9 < 10 separates the numeric order from the
#: lexicographic one, and 2 < 20 separates it again with a different prefix.
#: `discriminating_fixture_control` fails if this is ever narrowed to one digit.
WINDOW_INDICES = ["1", "2", "9", "10", "11", "20"]

#: The order the pre-fix key produced for `WINDOW_INDICES` — kept as a literal so
#: the negative control states the old behaviour instead of recomputing it.
LEXICOGRAPHIC_ORDER = ["1", "10", "11", "2", "20", "9"]

#: The key exactly as it read before t1659, for the negative control.
PRE_FIX_KEY = (
    lambda s: (s.pane.session_name, s.pane.window_index, s.pane.pane_index)
)


# --- key units --------------------------------------------------------------


class IndexKeyTests(unittest.TestCase):
    def test_double_digit_indices_sort_after_single_digit_ones(self):
        self.assertEqual(
            sorted(["1", "10", "2", "20", "9"], key=tmux_index_key),
            ["1", "2", "9", "10", "20"],
        )

    def test_a_non_numeric_index_sorts_last_and_raises_nothing(self):
        self.assertEqual(
            sorted(["x", "2", "", "10"], key=tmux_index_key),
            ["2", "10", "", "x"],
        )

    def test_a_non_string_index_does_not_raise(self):
        """`test_multi_session_minimonitor.sh` builds a pane with `pane_index=0`
        (an int), so `str`-only handling would `AttributeError` there."""
        self.assertEqual(tmux_index_key(0), (INDEX_RANK_NUMERIC, 0, "0"))
        self.assertEqual(tmux_index_key(None), (INDEX_RANK_NON_NUMERIC, 0, ""))

    def test_the_two_category_ranks_are_distinct_and_ordered(self):
        self.assertLess(INDEX_RANK_NUMERIC, INDEX_RANK_NON_NUMERIC)


class SentinelBoundaryTests(unittest.TestCase):
    """A large-integer sentinel is not a valid implementation of this key.

    `1 << 30` == 1073741824 is a perfectly legal decimal index string, so a
    sentinel-based key conflates it with non-numeric text and inverts the
    category order for everything above it. These cases fail loudly if anyone
    "simplifies" `tmux_index_key` back to that shape.
    """

    BOUNDARY = str(1 << 30)          # "1073741824"
    ABOVE = str((1 << 30) + 1)
    BELOW = str((1 << 30) - 1)

    def test_indices_at_and_above_the_old_sentinel_still_sort_before_text(self):
        self.assertEqual(
            sorted([self.BOUNDARY, self.ABOVE, self.BELOW, "x", ""],
                   key=tmux_index_key),
            [self.BELOW, self.BOUNDARY, self.ABOVE, "", "x"],
        )

    def test_the_old_sentinel_value_is_not_conflated_with_a_non_numeric_index(self):
        self.assertNotEqual(tmux_index_key(self.BOUNDARY), tmux_index_key("x"))
        self.assertEqual(tmux_index_key(self.BOUNDARY)[0], INDEX_RANK_NUMERIC)


class PaneSortKeyTests(unittest.TestCase):
    def test_session_dominates_the_window_index(self):
        a = _snap("%1", window_index="10", session="sA")
        b = _snap("%2", window_index="1", session="sB")
        self.assertLess(pane_sort_key(a.pane), pane_sort_key(b.pane))

    def test_window_dominates_the_pane_index(self):
        a = _snap("%1", window_index="2", pane_index="9", session="sA")
        b = _snap("%2", window_index="10", pane_index="0", session="sA")
        self.assertLess(pane_sort_key(a.pane), pane_sort_key(b.pane))

    def test_the_pane_index_also_compares_numerically(self):
        a = _snap("%1", window_index="2", pane_index="2", session="sA")
        b = _snap("%2", window_index="2", pane_index="10", session="sA")
        self.assertLess(pane_sort_key(a.pane), pane_sort_key(b.pane))


class DiscoverySortKeyTests(unittest.TestCase):
    """Site 1: the discovery order underneath both TUIs."""

    def test_the_monitor_sorts_discovered_panes_numerically(self):
        panes = [_pane_info(w) for w in ["11", "2", "20", "1", "10", "9"]]
        panes.sort(key=TmuxMonitor._PANE_SORT_KEY)
        self.assertEqual([p.window_index for p in panes], WINDOW_INDICES)

    def test_discovery_and_the_tuis_share_one_key_object(self):
        """Cross-surface parity at the seam: not "both are numeric", but "both
        resolve to the same callable", so the two cannot drift apart."""
        self.assertIs(TmuxMonitor._PANE_SORT_KEY, pane_sort_key)


# --- shared fixture / harnesses ---------------------------------------------


def _snap(
    pane_id: str,
    *,
    window_index: str = "1",
    pane_index: str = "0",
    window_name: str = "agent-pick-42",
    category=PaneCategory.AGENT,
    session: str = "s1",
    command: str = "python",
):
    """Duck-typed snapshot, same shape as `test_monitor_session_divider.py`."""
    pane = SimpleNamespace(
        pane_id=pane_id,
        session_name=session,
        window_index=window_index,
        pane_index=pane_index,
        window_name=window_name,
        category=category,
        current_command=command,
    )
    return SimpleNamespace(pane=pane, is_idle=False, idle_seconds=0.0)


def _mini_fixture():
    """One agent per window in `WINDOW_INDICES`, deliberately mounted in the
    lexicographic order so a no-op sort would reproduce the bug."""
    return [
        _snap(f"%{w}", window_index=w, window_name=f"agent-pick-{w}")
        for w in LEXICOGRAPHIC_ORDER
    ]


def _pane_info(window_index: str, session: str = "s1") -> TmuxPaneInfo:
    return TmuxPaneInfo(
        window_index=window_index,
        window_name=f"agent-pick-{window_index}",
        pane_index="0",
        pane_id=f"%{window_index}",
        pane_pid=10_000 + int(window_index),
        current_command="bash",
        width=80,
        height=24,
        category=PaneCategory.AGENT,
        session_name=session,
    )


def _monitor_fixture(session: str = "s1") -> dict[str, PaneSnapshot]:
    """The same fixture as `_mini_fixture`, as real `PaneSnapshot`s, inserted in
    lexicographic order (dicts preserve insertion order)."""
    out: dict[str, PaneSnapshot] = {}
    for w in LEXICOGRAPHIC_ORDER:
        pane = _pane_info(w, session)
        out[pane.pane_id] = PaneSnapshot(
            pane=pane,
            content=f"agent-pick-{w}\nready",
            timestamp=0.0,
            idle_seconds=0.0,
            is_idle=False,
        )
    return out


class _FakeContainer:
    """Captures what `_rebuild_pane_list` mounts. Also stands in for
    `#mini-own-agent`, so it carries the `display`/`styles` that
    `_maybe_build_own_agent_panel` writes."""

    def __init__(self) -> None:
        self.mounted: list = []
        self.display = False
        self.styles = SimpleNamespace(max_height=None)

    async def remove_children(self):
        pass

    async def mount_all(self, widgets):
        self.mounted = list(widgets)


def _mk_list_app(snapshots, *, own_window_index=None, multi_session=False):
    """Real `MiniMonitorApp`, stubbed down to what `_rebuild_pane_list` touches.

    Same harness shape as `tests/test_monitor_session_divider.py`.
    """
    container = _FakeContainer()
    app = mm.MiniMonitorApp.__new__(mm.MiniMonitorApp)
    app.query_one = lambda *a, **k: container
    app._own_window_index = own_window_index
    app._session = "s1"
    app._snapshots = {s.pane.pane_id: s for s in snapshots}
    app._task_cache = SimpleNamespace(
        get_task_id=lambda w: None,
        get_task_id_for_pane=lambda p: None,
        get_task_info=lambda t, s=None: None,
    )
    app._monitor = SimpleNamespace(
        multi_session=multi_session,
        get_compare_mode=lambda pid: "stripped",
        is_compare_mode_overridden=lambda pid: False,
        get_shadow_snapshot=lambda pid: None,
        get_session_to_project_mapping=lambda: {},
    )
    app._completed_pane_ids = frozenset()
    app._gate_cache = SimpleNamespace(summary_for=lambda i: None, clear=lambda: None)
    app._init_agent_marks()
    return app, container


class _FakeMonitor:
    """Same shape as `tests/test_monitor_session_divider.py::_FakeMonitor`."""

    multi_session = False

    def __init__(self, snapshots: dict[str, PaneSnapshot]) -> None:
        self.snapshots = snapshots
        self._gen = 0

    @property
    def capture_generation(self) -> int:
        return self._gen

    async def _run_offloaded(self, fn):
        return fn()

    def get_shadow_snapshot(self, followed_pane_id):
        return None

    async def capture_all_classified_async(self):
        self._gen += 1
        return self._gen, [(s.pane, s.content, None) for s in self.snapshots.values()]

    def commit_snapshots(self, gen, classified):
        return None if gen != self._gen else dict(self.snapshots)

    async def capture_all_async(self) -> dict[str, PaneSnapshot] | None:
        gen, classified = await self.capture_all_classified_async()
        return self.commit_snapshots(gen, classified)

    def get_session_to_project_mapping(self) -> dict[str, Path]:
        return {}

    async def get_session_to_project_mapping_async(self) -> dict[str, Path]:
        return {}

    def control_state(self) -> TmuxControlState:
        return TmuxControlState.CONNECTED

    def get_compare_mode(self, pane_id: str) -> str:
        return "stripped"

    def is_compare_mode_overridden(self, pane_id: str) -> bool:
        return False


def _mini_card_order(snapshots) -> list[str]:
    """Mounted `MiniPaneCard` pane ids, in mount order."""
    app, container = _mk_list_app(snapshots)
    asyncio.run(app._rebuild_pane_list())
    return [w.pane_id for w in container.mounted
            if isinstance(w, mm.MiniPaneCard)]


def _monitor_card_order(snapshots: dict[str, PaneSnapshot]) -> list[str]:
    """Mounted `PaneCard` pane ids, through the REAL `MonitorApp`."""
    captured: dict[str, list[str]] = {}

    async def runner():
        app = MonitorApp(session="s1", project_root=REPO_ROOT)
        async with app.run_test(size=(100, 30)) as pilot:
            app._monitor = _FakeMonitor(snapshots)
            app._snapshots = snapshots
            app._focused_pane_id = next(iter(snapshots))

            async def no_focus_request():
                return None

            app._consume_focus_request = no_focus_request
            app._rebuild_pane_list()
            await pilot.pause()
            captured["ids"] = [
                w.pane_id
                for w in app.query_one("#pane-list").query(PaneCard)
            ]

    asyncio.run(runner())
    return captured["ids"]


# --- render-level cases ------------------------------------------------------


class MiniMonitorOrderTests(unittest.TestCase):
    def test_the_agent_list_runs_numerically(self):
        self.assertEqual(
            _mini_card_order(_mini_fixture()),
            [f"%{w}" for w in WINDOW_INDICES],
        )

    def test_the_own_window_seam_still_prefers_the_lowest_pane_index(self):
        """The `_find_own_window_snapshot` min() now shares `tmux_index_key`.
        Guards the refactor of code that was ALREADY correct — "10" must not
        win over "2"."""
        app, _ = _mk_list_app(
            [
                _snap("%10", window_index="7", pane_index="10",
                      window_name="scratch", category=PaneCategory.OTHER),
                _snap("%2", window_index="7", pane_index="2",
                      window_name="scratch", category=PaneCategory.OTHER),
            ],
            own_window_index="7",
        )
        self.assertEqual(app._find_own_window_snapshot().pane.pane_id, "%2")


class MonitorOrderTests(unittest.TestCase):
    def test_the_agent_list_runs_numerically(self):
        self.assertEqual(
            _monitor_card_order(_monitor_fixture()),
            [f"%{w}" for w in WINDOW_INDICES],
        )


# --- confirmed inline risk mitigations --------------------------------------


class CrossTuiOrderParityTests(unittest.TestCase):
    """Inline post-phase mitigation `cross_tui_order_parity`.

    Four call sites across three files feed these two lists. Asserting only that
    each is numeric would still let them drift apart, so drive ONE fixture
    through both and compare the two rendered orders to each other.
    """

    def test_both_tuis_render_the_same_fixture_in_the_same_order(self):
        mini = _mini_card_order(_mini_fixture())
        full = _monitor_card_order(_monitor_fixture())
        self.assertEqual(mini, full)
        self.assertEqual(mini, [f"%{w}" for w in WINDOW_INDICES])


class DiscriminatingFixtureControlTests(unittest.TestCase):
    """Inline post-phase mitigation `discriminating_fixture_control`.

    The bug is only observable with a fixture that separates numeric order from
    lexicographic order. Pin that the shared fixture does — otherwise a later
    narrowing to single-digit indices would leave every case above green while
    proving nothing.
    """

    def test_the_pre_fix_key_orders_the_shared_fixture_differently(self):
        snaps = _mini_fixture()
        old = [s.pane.pane_id for s in sorted(snaps, key=PRE_FIX_KEY)]
        new = [s.pane.pane_id for s in
               sorted(snaps, key=lambda s: pane_sort_key(s.pane))]
        self.assertNotEqual(old, new)

    def test_the_pre_fix_key_reproduces_the_reported_symptom(self):
        snaps = _mini_fixture()
        self.assertEqual(
            [s.pane.pane_id for s in sorted(snaps, key=PRE_FIX_KEY)],
            [f"%{w}" for w in LEXICOGRAPHIC_ORDER],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
