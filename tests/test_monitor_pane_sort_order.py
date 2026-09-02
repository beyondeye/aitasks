"""Pane ordering is by window NAME, compared naturally, in both monitor TUIs.

Two changes, one shared key — `monitor_core.pane_sort_key`, used by tmux
discovery (`TmuxMonitor._PANE_SORT_KEY`) and by BOTH TUIs' `_rebuild_pane_list`:

**t1659 — numeric, not lexicographic.** `TmuxPaneInfo.window_index` /
`.pane_index` are **strings** (straight off the tmux gateway's
`#{window_index}` / `#{pane_index}` format) and every pane-ordering site used to
compare them as strings. With ten or more agent windows the list read
`…-9, -10, -11, …, -14, -1, -2, …`: it jumped back to low numbers part-way down
(seen live in t1653's 40-agent fixture capture).

**t1679 — the window NAME leads the window slot.** The index is only the order
windows happen to sit in the session (launch order); the name is what the cards
show and what carries the task id. The key is now
`(session_name, natural_name_key(window_name), tmux_index_key(window_index),
tmux_index_key(pane_index))` — `session_name` still leads, so per-session
grouping is untouched, and the two indices survive as the tiebreak that keeps
the order total when two windows share a name.

Properties of that key that are load-bearing, all pinned here:

* the window-name slot compares digit runs **numerically** (`agent-pick-2`
  before `agent-pick-10`) — the same failure mode as above, one level up;
* the index slots still compare numerically, as the tiebreak;
* the order stays **total** for a non-numeric index or an odd name rather than
  raising — via a category slot, NOT a large sentinel integer. A sentinel is
  itself a reachable decimal index, so `1 << 30` would tie with the literal
  index "1073741824" and let everything larger sort *ahead* of non-numeric
  text. `SentinelBoundaryTests` / `NaturalNameKeyTests` pin that, so a future
  "simplification" back to a sentinel cannot pass.

Four of the cases here are confirmed inline risk mitigations:
`cross_tui_order_parity` (the two TUIs' orders must be equal to EACH OTHER, not
merely each numeric), `discriminating_fixture_control` and its t1679 sibling
`NameFixtureControlTests` (negative controls proving each fixture separates the
new key from the old one — a fixture narrowed to single-digit values would pass
every other case while proving nothing), and t1679's
`characterize_within_window_order_invariance` (`WithinWindowOrderInvarianceTests`
— the key must never reorder panes *within* a window, which is what lets the
name slot change discovery order safely).

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
    NAME_RANK_NUMERIC,
    NAME_RANK_TEXT,
    PaneCategory,
    PaneSnapshot,
    TmuxMonitor,
    TmuxPaneInfo,
    natural_name_key,
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

#: t1679's own fixture — window NAMES, and the ONE fixture whose order is
#: decided by the name rather than by the index. Deliberately spans the
#: single→double digit boundary in both directions, exactly as `WINDOW_INDICES`
#: does one level down: 9 < 10 separates natural from lexicographic order, and
#: 2 < 20 separates it again with a different prefix.
#: `NameFixtureControlTests` fails if this is ever narrowed to one digit.
WINDOW_NAMES = ["agent-pick-2", "agent-pick-9", "agent-pick-10", "agent-pick-20"]

#: The order a plain string compare of the names produces — a literal, so the
#: negative control states the wrong behaviour instead of recomputing it.
LEXICOGRAPHIC_NAME_ORDER = [
    "agent-pick-10", "agent-pick-2", "agent-pick-20", "agent-pick-9",
]

#: Window index per name, running OPPOSITE to name order. This is what makes the
#: fixture discriminate on the *changed* dimension: a key that still leads with
#: the index cannot produce name order from it, and vice versa.
NAME_FIXTURE_INDICES = {
    "agent-pick-2": "4",
    "agent-pick-9": "3",
    "agent-pick-10": "2",
    "agent-pick-20": "1",
}

#: The key exactly as it read before t1679 (i.e. the t1659 key), for the name
#: fixture's negative control.
PRE_NAME_KEY = (
    lambda s: (s.pane.session_name,
               tmux_index_key(s.pane.window_index),
               tmux_index_key(s.pane.pane_index))
)

#: A window-name key that is NOT numeric-aware — the naive implementation the
#: natural key exists to rule out.
LEXICOGRAPHIC_NAME_KEY = (
    lambda s: (s.pane.session_name, s.pane.window_name)
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


class NaturalNameKeyTests(unittest.TestCase):
    """The window-name slot (t1679), mirroring `IndexKeyTests` one level up."""

    def test_double_digit_names_sort_after_single_digit_ones(self):
        self.assertEqual(
            sorted(LEXICOGRAPHIC_NAME_ORDER, key=natural_name_key),
            WINDOW_NAMES,
        )

    def test_a_child_task_window_follows_its_parents_and_precedes_the_next(self):
        """`agent-pick-100_1` must order sensibly against `agent-pick-100`."""
        self.assertEqual(
            sorted(["agent-pick-101", "agent-pick-100_2", "agent-pick-100",
                    "agent-pick-100_1"], key=natural_name_key),
            ["agent-pick-100", "agent-pick-100_1", "agent-pick-100_2",
             "agent-pick-101"],
        )

    def test_a_digit_run_sorts_before_a_text_run_at_the_same_position(self):
        """The case the rank slot exists for: the runs need not align by kind.

        `"10a"` is digits-then-text and `"a10"` the reverse, so position 0
        compares a digit run against a text run. Without the category the two
        would be an `int` against a `str`.
        """
        self.assertEqual(sorted(["a10", "10a"], key=natural_name_key),
                         ["10a", "a10"])

    def test_the_two_name_ranks_are_distinct_and_ordered(self):
        self.assertLess(NAME_RANK_NUMERIC, NAME_RANK_TEXT)

    def test_odd_names_raise_nothing_and_stay_totally_ordered(self):
        """An empty, digit-free, all-digit or non-string name must not raise.

        tmux always reports a string, but nothing in `TmuxPaneInfo` enforces it
        and hand-built stubs exist across the suite (`pane_index=0` as an int is
        already in `test_multi_session_minimonitor.sh`).
        """
        names = ["zzz", "", "42", "agent-pick-2", None, 7]
        self.assertEqual(natural_name_key(""), ())
        self.assertEqual(natural_name_key(None), natural_name_key(""))
        # A total order over the whole mixed bag: every pair is comparable, and
        # both directions of input produce the same sequence of keys. Compared
        # as KEYS, not as elements — `None` and `""` key equally, so a stable
        # sort legitimately keeps them in input order.
        self.assertEqual(
            [natural_name_key(n) for n in sorted(names, key=natural_name_key)],
            [natural_name_key(n)
             for n in sorted(reversed(names), key=natural_name_key)],
        )

    def test_a_zero_padded_run_is_not_conflated_with_its_bare_form(self):
        self.assertNotEqual(natural_name_key("agent-pick-007"),
                            natural_name_key("agent-pick-7"))

    def test_a_name_embedding_the_old_sentinel_is_not_conflated_with_text(self):
        """`SentinelBoundaryTests`' argument, restated for the name key.

        `1 << 30` is a perfectly legal window-name digit run, so a sentinel
        would conflate `agent-1073741824` with a text run and invert the
        category order for everything above it.
        """
        boundary = f"agent-{1 << 30}"
        self.assertNotEqual(natural_name_key(boundary), natural_name_key("agent-x"))
        self.assertEqual(natural_name_key(boundary)[-1][0], NAME_RANK_NUMERIC)
        self.assertEqual(
            sorted([f"agent-{(1 << 30) + 1}", boundary,
                    f"agent-{(1 << 30) - 1}", "agent-x"], key=natural_name_key),
            [f"agent-{(1 << 30) - 1}", boundary, f"agent-{(1 << 30) + 1}",
             "agent-x"],
        )


class PaneSortKeyTests(unittest.TestCase):
    def test_the_window_name_dominates_the_window_index(self):
        """t1679's core swap: the name decides, the index only breaks ties."""
        a = _snap("%1", window_index="10", window_name="agent-pick-2",
                  session="sA")
        b = _snap("%2", window_index="2", window_name="agent-pick-10",
                  session="sA")
        self.assertLess(pane_sort_key(a.pane), pane_sort_key(b.pane))

    def test_the_session_still_dominates_the_window_name(self):
        """Per-session grouping (and the session dividers) must be untouched."""
        a = _snap("%1", window_name="agent-pick-99", session="sA")
        b = _snap("%2", window_name="agent-pick-1", session="sB")
        self.assertLess(pane_sort_key(a.pane), pane_sort_key(b.pane))

    def test_a_duplicate_name_falls_back_to_the_window_index(self):
        a = _snap("%1", window_index="2", window_name="scratch", session="sA")
        b = _snap("%2", window_index="10", window_name="scratch", session="sA")
        self.assertLess(pane_sort_key(a.pane), pane_sort_key(b.pane))

    def test_a_duplicate_name_and_index_falls_back_to_the_pane_index(self):
        a = _snap("%1", window_index="2", pane_index="2",
                  window_name="scratch", session="sA")
        b = _snap("%2", window_index="2", pane_index="10",
                  window_name="scratch", session="sA")
        self.assertLess(pane_sort_key(a.pane), pane_sort_key(b.pane))

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


class WithinWindowOrderInvarianceTests(unittest.TestCase):
    """Confirmed inline pre-phase mitigation `characterize_within_window_order_invariance` (t1679).

    The key orders panes ACROSS windows; it must never reorder the panes
    *within* one. That invariance is what every discovery-order consumer
    silently relies on — above all `MiniMonitorApp._find_own_agent_snapshot`,
    which filters `self._snapshots` to one `(window_index, session)` and takes
    the FIRST match. It is the resolution seam for the `e` / `E` shadow triggers
    and the review loop, and "first" only means "lowest pane index" because
    discovery is sorted.

    A window name is a property of the WINDOW in tmux, so every pane in a window
    carries the same one — which is exactly why t1679 could move the name into
    the key's second slot without disturbing this. These cases are the
    executable form of that argument: written before the key changed, they pass
    on the pre-t1679 key and must keep passing after it.
    """

    #: All three panes live in one window, so they share its name. The name is
    #: deliberately one whose per-pane comparison would invert the pane order if
    #: anything ever compared it per pane instead of per window.
    WINDOW = {"session": "sA", "window_index": "3",
              "window_name": "agent-pick-1679"}

    def _panes(self, pane_indices):
        return [
            _snap(f"%{p}", pane_index=p, **self.WINDOW).pane
            for p in pane_indices
        ]

    def test_panes_in_one_window_keep_pane_index_order(self):
        panes = self._panes(["10", "2", "0", "9", "1"])
        self.assertEqual(
            [p.pane_index for p in sorted(panes, key=pane_sort_key)],
            ["0", "1", "2", "9", "10"],
        )

    def test_the_lowest_pane_index_is_first_whatever_the_window_name(self):
        """`_find_own_agent_snapshot`'s "first match" contract, per name.

        Every name here is shared by both panes of its own window (that is what
        a window name is), so none of them may change which pane leads.
        """
        for name in ("agent-pick-2", "agent-pick-10", "zzz", "1", "", "a10"):
            with self.subTest(window_name=name):
                window = dict(self.WINDOW, window_name=name)
                hi = _snap("%hi", pane_index="10", **window).pane
                lo = _snap("%lo", pane_index="2", **window).pane
                self.assertEqual(
                    min([hi, lo], key=pane_sort_key).pane_id, "%lo")

    def test_two_panes_of_one_window_are_never_split_by_another_window(self):
        """No third window may sort BETWEEN two panes of the same window.

        Interleaving would break the "first match wins" contract just as surely
        as reordering within the window does, since the filter walks the whole
        snapshot dict in discovery order.
        """
        mine = self._panes(["0", "1"])
        other = _snap("%other", pane_index="0", session="sA",
                      window_index="4", window_name="agent-pick-1").pane
        order = [p.pane_id for p in sorted(mine + [other], key=pane_sort_key)]
        self.assertEqual(abs(order.index("%0") - order.index("%1")), 1)


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
    return SimpleNamespace(pane=pane, is_idle=False, idle_seconds=0.0,
                           # `parked` is a real PaneSnapshot field (t1685); a
                           # double that omits it raises rather than ignoring it.
                           parked=False)


def _mini_fixture():
    """One agent per window in `WINDOW_INDICES`, deliberately mounted in the
    lexicographic order so a no-op sort would reproduce the bug."""
    return [
        _snap(f"%{w}", window_index=w, window_name=f"agent-pick-{w}")
        for w in LEXICOGRAPHIC_ORDER
    ]


def _name_fixture():
    """t1679's fixture: one agent per name in `WINDOW_NAMES`, each mounted at
    the window index that runs OPPOSITE to its name order, and inserted in
    lexicographic name order so a no-op sort reproduces the bug.

    Pane ids are the names' natural positions, so an expected order reads
    `["%0", "%1", "%2", "%3"]` however the names are later reworded.
    """
    return [
        _snap(
            f"%{WINDOW_NAMES.index(name)}",
            window_index=NAME_FIXTURE_INDICES[name],
            window_name=name,
        )
        for name in LEXICOGRAPHIC_NAME_ORDER
    ]


#: The order `_name_fixture()` must render in — natural name order.
NAME_FIXTURE_ORDER = [f"%{i}" for i in range(len(WINDOW_NAMES))]


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


def _name_pane_info(name: str, session: str = "s1") -> TmuxPaneInfo:
    """`_pane_info`'s name-fixture sibling — a real `TmuxPaneInfo`."""
    idx = WINDOW_NAMES.index(name)
    return TmuxPaneInfo(
        window_index=NAME_FIXTURE_INDICES[name],
        window_name=name,
        pane_index="0",
        pane_id=f"%{idx}",
        pane_pid=20_000 + idx,
        current_command="bash",
        width=80,
        height=24,
        category=PaneCategory.AGENT,
        session_name=session,
    )


def _monitor_name_fixture(session: str = "s1") -> dict[str, PaneSnapshot]:
    """`_name_fixture` as real `PaneSnapshot`s, inserted lexicographically."""
    out: dict[str, PaneSnapshot] = {}
    for name in LEXICOGRAPHIC_NAME_ORDER:
        pane = _name_pane_info(name, session)
        out[pane.pane_id] = PaneSnapshot(
            pane=pane,
            content=f"{name}\nready",
            timestamp=0.0,
            idle_seconds=0.0,
            is_idle=False,
        )
    return out


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


    def test_the_agent_list_is_ordered_by_window_name(self):
        """t1679 at render level, on the fixture whose indices run the other
        way — so only the name can produce this order."""
        self.assertEqual(_mini_card_order(_name_fixture()), NAME_FIXTURE_ORDER)


class MonitorOrderTests(unittest.TestCase):
    def test_the_agent_list_runs_numerically(self):
        self.assertEqual(
            _monitor_card_order(_monitor_fixture()),
            [f"%{w}" for w in WINDOW_INDICES],
        )

    def test_the_agent_list_is_ordered_by_window_name(self):
        self.assertEqual(
            _monitor_card_order(_monitor_name_fixture()), NAME_FIXTURE_ORDER)


class SessionGroupingUnderInterleavingNamesTests(unittest.TestCase):
    """Session grouping must survive names that interleave across sessions.

    `session_name` leads the key, so a name that sorts FIRST globally must still
    render after every pane of an earlier session. Pinned at both levels: the
    key itself, and the real minimonitor's multi-session render (where breaking
    it would also emit a session's divider more than once).
    """

    #: `sB`'s name sorts before every `sA` name; `sA`'s sorts after every `sB`
    #: name. Both directions, so neither is passing by accident.
    SA_NAMES = ["agent-pick-90", "agent-pick-9"]
    SB_NAMES = ["agent-pick-1", "agent-pick-100"]

    def _snaps(self):
        return [
            _snap(f"%{sess}{i}", window_index=str(i), window_name=name,
                  session=sess)
            for sess, names in (("sA", self.SA_NAMES), ("sB", self.SB_NAMES))
            for i, name in enumerate(names)
        ]

    def test_the_key_groups_by_session_before_name(self):
        order = [s.pane.session_name
                 for s in sorted(self._snaps(),
                                 key=lambda s: pane_sort_key(s.pane))]
        self.assertEqual(order, ["sA", "sA", "sB", "sB"])

    def test_the_key_still_orders_naturally_inside_each_session(self):
        by_session = [
            (s.pane.session_name, s.pane.window_name)
            for s in sorted(self._snaps(), key=lambda s: pane_sort_key(s.pane))
        ]
        self.assertEqual(by_session, [
            ("sA", "agent-pick-9"), ("sA", "agent-pick-90"),
            ("sB", "agent-pick-1"), ("sB", "agent-pick-100"),
        ])

    def test_the_minimonitor_renders_one_divider_per_session_in_order(self):
        app, container = _mk_list_app(self._snaps(), multi_session=True)
        asyncio.run(app._rebuild_pane_list())
        kinds = [
            "card" if isinstance(w, mm.MiniPaneCard) else "divider"
            for w in container.mounted
        ]
        self.assertEqual(kinds, ["divider", "card", "card",
                                 "divider", "card", "card"])
        cards = [w.pane_id for w in container.mounted
                 if isinstance(w, mm.MiniPaneCard)]
        self.assertEqual(cards, ["%sA1", "%sA0", "%sB0", "%sB1"])


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

    def test_both_tuis_render_the_name_fixture_in_the_same_order(self):
        """The same parity claim under t1679's key, on the fixture whose order
        the window NAME decides."""
        mini = _mini_card_order(_name_fixture())
        full = _monitor_card_order(_monitor_name_fixture())
        self.assertEqual(mini, full)
        self.assertEqual(mini, NAME_FIXTURE_ORDER)


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


class NameFixtureControlTests(unittest.TestCase):
    """`discriminating_fixture_control`'s t1679 sibling — two negative controls.

    The name fixture has to separate the new key from the two keys it replaces,
    in both of the ways a weaker fixture would hide:

    * from the **index-led** key (t1659's), or the render cases would pass on a
      fixture whose names merely happen to agree with its indices; and
    * from a **lexicographic** name key, or a fixture narrowed to single-digit
      ids would leave every case above green while proving nothing about the
      numeric-awareness that is the whole point.
    """

    def test_the_index_led_key_orders_the_name_fixture_by_index_instead(self):
        snaps = _name_fixture()
        self.assertEqual(
            [s.pane.pane_id for s in sorted(snaps, key=PRE_NAME_KEY)],
            list(reversed(NAME_FIXTURE_ORDER)),
        )
        self.assertNotEqual(
            [s.pane.pane_id for s in sorted(snaps, key=PRE_NAME_KEY)],
            [s.pane.pane_id for s in
             sorted(snaps, key=lambda s: pane_sort_key(s.pane))],
        )

    def test_a_lexicographic_name_key_orders_the_name_fixture_differently(self):
        snaps = _name_fixture()
        self.assertEqual(
            [s.pane.window_name
             for s in sorted(snaps, key=LEXICOGRAPHIC_NAME_KEY)],
            LEXICOGRAPHIC_NAME_ORDER,
        )
        self.assertEqual(
            [s.pane.window_name for s in
             sorted(snaps, key=lambda s: pane_sort_key(s.pane))],
            WINDOW_NAMES,
        )
        self.assertNotEqual(LEXICOGRAPHIC_NAME_ORDER, WINDOW_NAMES)


if __name__ == "__main__":
    unittest.main(verbosity=2)
