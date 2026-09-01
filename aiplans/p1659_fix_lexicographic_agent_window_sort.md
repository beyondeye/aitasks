---
Task: t1659_fix_lexicographic_agent_window_sort.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1659 — Sort agent panes numerically, not lexicographically

## Context

`TmuxPaneInfo.window_index` and `.pane_index` are **strings** (they come straight
off the tmux gateway format `#{window_index}` / `#{pane_index}`), and every pane
ordering site compares them as strings. With ten or more agent windows the list
reads `…-9, -10, -11, …, -14, -1, -2, …` — it jumps back to low numbers
part-way down. Observed live in the t1653 40-agent fixture capture; t1653
deliberately left it alone because it changes visible ordering in **both**
monitor TUIs and needs its own tests.

Outcome: agent lists in `ait monitor` and `ait minimonitor` (and the discovery
order underneath them) are ordered `1, 2, … 9, 10, 11, 20` while the fields stay
strings for display, and the comparison stays **total** for a hypothetical
non-numeric index rather than raising.

## Scope — four sites, one shared key

The task names two `_rebuild_pane_list` sites. A sweep found the same defect
shape at a third, plus one already-correct duplicate of the idiom:

| # | Site | Today |
|---|---|---|
| 1 | `monitor/monitor_core.py:1999` `TmuxMonitor._PANE_SORT_KEY` (used at `:2021,2022,2054,2055`) | lexicographic |
| 2 | `monitor/monitor_app.py:1737,1740` `_rebuild_pane_list` | lexicographic |
| 3 | `monitor/minimonitor_app.py:2488` `_rebuild_pane_list` `sort_key` | lexicographic |
| 4 | `monitor/minimonitor_app.py:1758-1766` `_find_own_window_snapshot` `min()` | already numeric — a hand-rolled copy of the idiom, with its own `1 << 30` literal |

Site 1 is in scope because it is the same bug, feeds the same displayed order,
and leaving it lexicographic would leave the framework with two disagreeing
definitions of "pane order". Site 4 is folded in so the numeric idiom exists
**once** — and it is where the `1 << 30` sentinel bug below was found.

## Implementation

### 1. `.aitask-scripts/monitor/monitor_core.py` — the one authority

Add next to `TmuxPaneInfo` (before `PaneSnapshot`):

```python
#: Category ranks for the leading slot of `tmux_index_key`. The category is a
#: slot of its own rather than a large sentinel integer because **any** sentinel
#: is itself a reachable decimal index: `1 << 30` would tie with the literal
#: index "1073741824" and let every larger index sort *ahead* of non-numeric
#: text, which is exactly the guarantee this key exists to make.
INDEX_RANK_NUMERIC = 0
INDEX_RANK_NON_NUMERIC = 1


def tmux_index_key(value: object) -> tuple[int, int, str]:
    """Numeric-first ordering key for a tmux window/pane index.

    The indices are strings off the tmux gateway, so a plain comparison orders
    "10" before "2". `isdecimal()` (not `isdigit()`) is the predicate that
    matches exactly what `int()` accepts; the category slot keeps every
    non-numeric index after every numeric one **for all int values**, and the
    trailing text makes the order total and deterministic among them.
    """
    text = "" if value is None else str(value)
    if text.isdecimal():
        return (INDEX_RANK_NUMERIC, int(text), text)
    return (INDEX_RANK_NON_NUMERIC, 0, text)


def pane_sort_key(pane) -> tuple:
    """Display order for a discovered tmux pane: session, then window, then
    pane — the last two numerically. Duck-typed on `TmuxPaneInfo`'s three
    fields so it serves both `TmuxPaneInfo` and `PaneSnapshot.pane`.
    """
    return (
        pane.session_name,
        tmux_index_key(pane.window_index),
        tmux_index_key(pane.pane_index),
    )
```

Then replace the lambda at `:1999`:

```python
    _PANE_SORT_KEY = staticmethod(pane_sort_key)
```

### 2. `.aitask-scripts/monitor/tmux_monitor.py` — re-export

Add `pane_sort_key`, `tmux_index_key`, `INDEX_RANK_NUMERIC`,
`INDEX_RANK_NON_NUMERIC` to the existing
`from monitor.monitor_core import (…)` shim list. Both apps already import from
this module, so no new import path is introduced.

### 3. `.aitask-scripts/monitor/monitor_app.py`

Add `pane_sort_key` to the `from monitor.tmux_monitor import (…)` block at
`:26`. In `_rebuild_pane_list`, replace both lambdas with
`agents.sort(key=lambda s: pane_sort_key(s.pane))` / same for `others`, and
update the adjacent comment so it says the window/pane parts compare
numerically.

### 4. `.aitask-scripts/monitor/minimonitor_app.py`

- Add `pane_sort_key` and `tmux_index_key` to the `from monitor.tmux_monitor
  import (…)` block at `:29`.
- In `_rebuild_pane_list`, `sort_key = lambda s: pane_sort_key(s.pane)`; update
  the block comment above it the same way.
- In `_find_own_window_snapshot`, collapse the hand-rolled key to
  `key=lambda s: tmux_index_key(s.pane.pane_index)` and drop the local `1 << 30`
  literal and its two-line comment (the helper's docstring now carries it, and
  the category slot removes the sentinel-collision the literal had).
  Behaviour is unchanged except that `isdigit()` tightens to `isdecimal()`,
  which only removes a latent `int()` crash on e.g. `"²"`.

Comments/docstrings that currently say the key "degrades to the legacy
(window_index, pane_index) order" stay true and are kept.

### Post-phase (risk mitigations)

1. `[cross_tui_order_parity]` In `tests/test_monitor_pane_sort_order.py`, add a
   test that builds **one** pane fixture (windows `1,2,9,10,11,20` in a single
   session), drives it through `MonitorApp._rebuild_pane_list` (real app under
   `run_test`) **and** `MiniMonitorApp._rebuild_pane_list` (`__new__` +
   `_FakeContainer`), extracts each TUI's mounted card `pane_id` sequence, and
   asserts the two sequences are **equal to each other** — not only that each
   is numeric. A single-TUI assertion cannot catch the two drifting apart.
2. `[discriminating_fixture_control]` In the same file, add a negative control
   that sorts the *same* fixture by the pre-fix key
   `lambda s: (s.pane.session_name, s.pane.window_index, s.pane.pane_index)`
   and asserts the resulting order **differs** from `pane_sort_key`'s. This
   fails if the fixture is ever narrowed to single-digit indices, i.e. it pins
   that the fixture actually discriminates on the changed dimension.

## Tests — `tests/test_monitor_pane_sort_order.py` (new)

Modelled on `tests/test_monitor_session_divider.py`, which already has both
harnesses this needs: `_FakeContainer` + `_mk_list_app` (real `MiniMonitorApp`
via `__new__`) and the real `MonitorApp` under `app.run_test()` with
`_FakeMonitor`. Scrub `TMUX`/`TMUX_PANE` from the env at import, as that file
does.

1. **Key unit** — `sorted(["1","10","2","20","9"], key=tmux_index_key)` is
   `["1","2","9","10","20"]`.
2. **Totality** — a non-numeric index (`"x"`, `""`) sorts last and raises
   nothing; `tmux_index_key(0)` (an int, as `test_multi_session_minimonitor.sh`
   passes) does not raise.
3. **Sentinel-collision boundary** — pin the exact failure a large-integer
   sentinel would have caused, so a future "simplification" back to one cannot
   pass:
   `sorted(["1073741824", "1073741825", "1073741823", "x", ""], key=tmux_index_key)`
   is `["1073741823", "1073741824", "1073741825", "", "x"]` — i.e. `1 << 30`
   and everything above it still sort **before** every non-numeric index, and
   `"1073741824"` is not conflated with them. Also assert
   `tmux_index_key("1073741824") != tmux_index_key("x")`.
4. **`pane_sort_key` precedence** — session dominates window, window dominates
   pane; `sB/w1` sorts after `sA/w10`.
5. `[discriminating_fixture_control]` **Negative control** — the same fixture
   sorted by the *pre-fix* lambda `(session, window_index, pane_index)` yields a
   *different* order. Without this the fixture could silently stop
   discriminating. (Post-phase step 2.)
6. **Core** — a list of `TmuxPaneInfo` with window indices `1,2,10,11,20` sorted
   by `TmuxMonitor._PANE_SORT_KEY` comes out numeric.
7. **minimonitor render** — `_rebuild_pane_list` over snapshots at windows
   `1,2,9,10,11,20` mounts `MiniPaneCard`s in numeric order (assert the mounted
   `pane_id` sequence).
8. **monitor render** — same fixture through the real `MonitorApp` under
   `run_test`, asserting the `PaneCard` order in `#pane-list`.
9. `[cross_tui_order_parity]` **Cross-TUI parity** — assert both TUIs' orders
   are *equal* for one shared fixture, so the two can never drift apart again.
   (Post-phase step 1.)
10. **Own-window seam** — `_find_own_window_snapshot` still prefers pane_index
   `"2"` over `"10"` after the refactor (this also keeps
   `test_minimonitor_other_section.py::test_window_seam_is_deterministic_and_numeric`
   honest as the pre-existing guard).

## Verification

```bash
python3 tests/test_monitor_pane_sort_order.py          # new
python3 tests/test_monitor_session_divider.py          # shared harness / ordering
python3 tests/test_minimonitor_other_section.py        # own-window seam guard
python3 tests/test_monitor_focus_switch.py
python3 tests/test_minimonitor_pick_by_number.py       # numbering derives from list order
bash    tests/test_multi_session_monitor.sh
bash    tests/test_multi_session_minimonitor.sh
bash    tests/run_all_python_tests.sh                  # read ONLY the last line
```

Manual (optional, matches how the defect was seen): open `ait monitor` in a
session with ≥11 agent windows and confirm the list runs `1 … 9, 10, 11` with no
jump back to low numbers.

## Post-Implementation

Step 9 of the task workflow (cleanup, archival, merge) applies as usual.

## Risk

### Code-health risk: low
- Four call sites across three files in a load-bearing display path; a mistake
  in one leaves the two TUIs disagreeing about pane order · severity: low
  (residual — addressed by inline post-phase `cross_tui_order_parity`) ·
  → mitigation: inline post-phase cross_tui_order_parity
- Folding `_find_own_window_snapshot` into the shared helper touches code that
  is already correct, so the change could regress a working seam ·
  severity: low · → mitigation: none (covered by the pre-existing guard
  `test_minimonitor_other_section.py::test_window_seam_is_deterministic_and_numeric`,
  re-run in Verification, plus new test 9)

### Goal-achievement risk: low
- The ordering change is only visible with ≥10 windows, so a fixture that
  accidentally uses single digits would pass while proving nothing · severity:
  low (residual — addressed by inline post-phase
  `discriminating_fixture_control`) ·
  → mitigation: inline post-phase discriminating_fixture_control

### Planned mitigations
- timing: post-phase | name: cross_tui_order_parity | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — four sort sites can drift apart | desc: One shared fixture through both TUIs' _rebuild_pane_list, asserting the two mounted card orders are equal to each other.
- timing: post-phase | name: discriminating_fixture_control | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — a single-digit fixture would prove nothing | desc: Negative control asserting the pre-fix lexicographic key yields a different order for the same fixture.

## Final Implementation Notes

- **Actual work done:** Added `INDEX_RANK_NUMERIC` / `INDEX_RANK_NON_NUMERIC`,
  `tmux_index_key()` and `pane_sort_key()` to
  `.aitask-scripts/monitor/monitor_core.py` (between `TmuxPaneInfo` and
  `PaneSnapshot`); re-exported all four through the `tmux_monitor.py` shim;
  replaced `TmuxMonitor._PANE_SORT_KEY`'s lambda with
  `staticmethod(pane_sort_key)`; swapped both lambdas in
  `MonitorApp._rebuild_pane_list` and the `sort_key` in
  `MiniMonitorApp._rebuild_pane_list` for `pane_sort_key(s.pane)`; and collapsed
  `MiniMonitorApp._find_own_window_snapshot`'s hand-rolled numeric `min()` key
  onto the shared `tmux_index_key`, deleting its local `1 << 30` literal. Added
  `tests/test_monitor_pane_sort_order.py` — 17 cases across 8 classes.
- **Deviations from plan:** None to the design. One test-harness correction
  during implementation: `app.query("#pane-list").results(PaneCard)` filters the
  *matched* node (the container) by type and therefore returns nothing; the
  monitor's card order is read with
  `app.query_one("#pane-list").query(PaneCard)` instead.
- **Issues encountered:** The plan's first draft used a large-integer sentinel
  (`1 << 30`, copied from the pre-existing `_find_own_window_snapshot` idiom) as
  the non-numeric rank. That is not total: `1 << 30` is itself a legal decimal
  index, so `"1073741824"` tied with non-numeric text and every larger index
  sorted *ahead* of it. Caught in plan review and replaced with a category-first
  key `(rank, int, text)`; `SentinelBoundaryTests` pins the boundary so the
  sentinel shape cannot be reintroduced.
- **Key decisions:**
  - Scope widened from the two `_rebuild_pane_list` sites named in the task to
    four: `TmuxMonitor._PANE_SORT_KEY` carries the identical defect and feeds the
    same displayed order, and `_find_own_window_snapshot` was folded in so the
    numeric idiom and its fallback exist exactly once.
  - `isdecimal()` rather than `isdigit()` — it is the predicate that matches
    exactly what `int()` accepts, so the key cannot raise on e.g. `"²"`.
  - `tmux_index_key` accepts any object (`str(value)`, `None` → `""`) because
    `tests/test_multi_session_minimonitor.sh` constructs a pane with an **int**
    `pane_index=0`.
  - Both inline risk mitigations landed as planned:
    `CrossTuiOrderParityTests` drives one fixture through both TUIs and compares
    the two rendered orders **to each other**;
    `DiscriminatingFixtureControlTests` is the negative control proving the
    fixture separates the new key from the old one.
  - Test discrimination was verified by mutation: reverting `pane_sort_key` to
    the pre-fix tuple made 7 of the 17 cases fail; restoring it made all 17 pass.
- **Upstream defects identified:** None
