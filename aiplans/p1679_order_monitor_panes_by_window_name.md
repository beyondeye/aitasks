---
Task: t1679_order_monitor_panes_by_window_name.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1679 — Order monitor/minimonitor panes by tmux window **name**

## Context

Agent panes in `ait minimonitor` (and `ait monitor`) are listed in tmux
**window-index** order — the order the windows happen to sit in the session,
which is just launch sequence. What the user actually reads on each card is the
**window name** (`agent-pick-1679`, `agent-qa-1642`, …), so the list looks
arbitrarily shuffled: agent 1642 can sit above agent 1201 purely because it was
launched first.

The fix is to order by window **name**, still grouped per session. The name
comparison must be **natural** (numeric-aware): a plain string compare puts
`agent-pick-10` before `agent-pick-2`, which is exactly the "jumps back to low
numbers part-way down the list" symptom t1659 was created to remove.

`monitor_core.pane_sort_key` is the single ordering authority (t1659) consumed
by four call sites across three files, so this is one small change in one
function plus its tests and docs.

## Design decisions

**1. Change the shared key, not a minimonitor-only fork.** `pane_sort_key` is
single-sourced by design and pinned by `cross_tui_order_parity` +
`test_discovery_and_the_tuis_share_one_key_object` (an `assertIs` on the key
object). Forking would break both. Both TUIs get name ordering.

**2. No `tmux.monitor.pane_order` config knob.** Rejected on cost/benefit:

- `pane_sort_key` is a module-level function with no config access. A knob needs
  a factory or an explicit parameter threaded to `TmuxMonitor._PANE_SORT_KEY`
  **and** both `_rebuild_pane_list` sites — and `_PANE_SORT_KEY` is currently
  `staticmethod(pane_sort_key)`, whose *identity* is what the parity test pins.
  A per-instance factory would force that invariant to be weakened.
- In this framework the window name *encodes the task id*; the window index is
  an artifact of launch order. Name order is the meaningful order, not a taste
  setting.

Consequence: **no config-table doc changes.** `seed/project_config.yaml`,
`website/content/docs/tuis/monitor/reference.md`'s configuration table and
minimonitor's inherited-keys list are untouched; the ordering rule is documented
as prose instead (see Step 5).

**3. Discovery order is safe to change** — surveyed every consumer.

The decisive property: **`window_name` is a property of the *window*, so every
pane in a window shares it.** Inserting it as the second key slot therefore
cannot reorder panes *within* a window; it only moves whole windows relative to
each other inside a session. That makes the highest-risk seam,
`minimonitor_app.py:1723 _find_own_agent_snapshot` (filters to one
`(window_index, session)` and takes the first — the resolution seam for `e`/`E`
and the review loop), **invariant** under this change.

Verified not order-sensitive: `count_other_real_agents` (a `sum`),
`applink/router.py:694 _discover_pane_ids` (feeds a `set`, replies
`sorted(accepted)`), `applink/pusher.py:153` (dict `.get` lookups over a `set`
of pane ids), `capture_all` / `commit_snapshots` (build dicts keyed by pane id),
both `_rebuild_pane_list` sites (re-sort with the same key).
`tests/test_multi_session_monitor.sh:106` ("sessA panes come first after sort")
is session-dominated and one pane per session — unaffected.

Two genuine but benign consequences, to be stated in the `pane_sort_key`
docstring rather than guarded against:

- `monitor_app.py:1436/1447` auto-switch — `awaiting.sort(key=idle_seconds)` is
  stable, so exact `idle_seconds` ties fall back to discovery order. Still fully
  deterministic; the tie-break just becomes name order.
- `minimonitor_app.py:2975 _find_running_agent_line` — which pane a duplicate
  task-id warning names, when the same id runs under two different prefixes
  (`agent-pick-42` / `agent-qa-42`). Deterministic either way.

## Implementation

### Pre-phase (risk mitigations)

1. `[characterize_within_window_order_invariance]` In
   `tests/test_monitor_pane_sort_order.py`, **before** touching
   `pane_sort_key`, add a characterization case pinning that the key never
   reorders panes *within* one session+window: two panes sharing
   `session_name` and `window_index` (and therefore, by tmux's data model,
   `window_name`) but differing in `pane_index` always come out in
   pane-index order, whatever the window name is — including a name that
   would sort the other way if it were compared per-pane. Run the module and
   confirm it passes against the **current** (pre-change) key; it must still
   pass after Step 2. This is the executable form of the invariant the whole
   "discovery order is safe to change" argument rests on (Design decision 3),
   and it is what keeps `_find_own_agent_snapshot` — the `e` / `E` and
   review-loop resolution seam — provably unaffected.

### Step 1 — `natural_name_key()` in `.aitask-scripts/monitor/monitor_core.py`

Insert immediately after `tmux_index_key` (currently ends at line ~914), before
`pane_sort_key`:

```python
#: Category ranks for one run of :func:`natural_name_key`. Same discipline as
#: `INDEX_RANK_*` above and for the same reason: the slot is a category, never a
#: sentinel integer, because any sentinel is itself a reachable digit run.
NAME_RANK_NUMERIC = 0
NAME_RANK_TEXT = 1

#: One run of a window name: digits, or everything that is not digits.
_NAME_RUN_RE = re.compile(r"\d+|\D+")


def natural_name_key(value: object) -> tuple[tuple[int, int, str], ...]:
    """Natural (numeric-aware) ordering key for a tmux window name.

    Agent windows are named ``agent-(pick|qa|resume|explore|raw)-<id>``, so a
    plain string compare orders ``agent-pick-10`` before ``agent-pick-2`` — the
    same "jumps back to low numbers" symptom t1659 removed from the indices.
    The name is split into digit / non-digit runs and each run becomes a
    ``(rank, number, text)`` triple, so digit runs compare **numerically**.

    The rank slot is load-bearing, not decoration: the runs of two names need
    not align by kind (``"10a"`` yields digits-then-text, ``"a10"`` the
    reverse), and it is what orders a digit run against a text run at the same
    position without ever comparing an ``int`` to a ``str``. It is a category —
    never a large sentinel integer — for the reason `tmux_index_key` states.

    ``isdecimal()`` (not ``isdigit()``) is the predicate that matches exactly
    what ``int()`` accepts, so the key never raises on any input; a name that is
    empty or non-string yields a key that is still totally ordered.
    """
    text = "" if value is None else str(value)
    return tuple(
        (NAME_RANK_NUMERIC, int(run), run) if run.isdecimal()
        else (NAME_RANK_TEXT, 0, run)
        for run in _NAME_RUN_RE.findall(text)
    )
```

Ordering properties this gives, all pinned by tests in Step 4:

| Input | Result |
|---|---|
| `agent-pick-2` / `agent-pick-9` / `agent-pick-10` / `agent-pick-20` | natural order |
| `agent-pick-100` vs `agent-pick-100_1` | parent first (shorter run tuple is a prefix) |
| `agent-pick-100_1` vs `agent-pick-101` | `100_1` first (run 2: 100 &lt; 101) |
| `agent-pick-7` vs `agent-pick-007` | distinct keys (raw text is the third slot) |
| `""`, a non-string | `()` / stringified — total, never raises |

### Step 2 — `pane_sort_key` gains the name slot (same file, ~line 916)

```python
    return (
        pane.session_name,
        natural_name_key(pane.window_name),
        tmux_index_key(pane.window_index),
        tmux_index_key(pane.pane_index),
    )
```

`session_name` still leads (per-session grouping and minimonitor's session
dividers are unchanged); `window_index` then `pane_index` remain as the
deterministic tiebreak for two windows that share a name. Rewrite the docstring
to say "session, then window **name** (naturally), then window index and pane
index as tiebreaks", and record the two benign discovery-order consequences from
Design decision 3.

### Step 3 — Re-export + comment sync

- `.aitask-scripts/monitor/tmux_monitor.py` — add `natural_name_key`,
  `NAME_RANK_NUMERIC`, `NAME_RANK_TEXT` to the re-export list beside
  `tmux_index_key` / `INDEX_RANK_*` (the test module imports from this shim).
- `.aitask-scripts/monitor/minimonitor_app.py` ~2470-2475 and
  `.aitask-scripts/monitor/monitor_app.py` ~1737-1741 — both carry a comment
  saying "Sort by (session_name, window_index, pane_index)". Update both to the
  new key. Two copies of the same sentence; they must not drift.

### Step 4 — Extend `tests/test_monitor_pane_sort_order.py`

The pre-phase characterization case already landed in this module — do not
re-add it; the cases below are additive to it.

Extend, never replace: all 17 existing cases stay and keep passing unchanged
(verified — the existing fixtures name each window `agent-pick-<window_index>`,
so name order and index order coincide there, and the `PaneSortKeyTests` cases
all share one default `window_name` so they still exercise the index slots).

New module-level fixture, deliberately **decoupling name order from index
order** so the render cases prove the name is what orders the list:

```python
#: Names that separate natural from lexicographic order in BOTH directions
#: (2 < 9 < 10 crosses the digit boundary once, 2 < 20 again with a different
#: prefix). `NameFixtureControlTests` fails if this is narrowed to one digit.
WINDOW_NAMES = ["agent-pick-2", "agent-pick-9", "agent-pick-10", "agent-pick-20"]
LEXICOGRAPHIC_NAME_ORDER = ["agent-pick-10", "agent-pick-2",
                            "agent-pick-20", "agent-pick-9"]
#: The window index each name is mounted at, running OPPOSITE to name order, so
#: a key that still leads with the index cannot produce the expected order.
NAME_FIXTURE_INDICES = {"agent-pick-2": "4", "agent-pick-9": "3",
                        "agent-pick-10": "2", "agent-pick-20": "1"}
```

Add `_name_fixture()` / `_monitor_name_fixture()` builders alongside the
existing `_mini_fixture()` / `_monitor_fixture()`, and:

1. **`NaturalNameKeyTests`** (unit, mirroring `IndexKeyTests`):
   - `WINDOW_NAMES` shuffled sorts to natural order.
   - `agent-pick-100` &lt; `agent-pick-100_1` &lt; `agent-pick-100_2` &lt; `agent-pick-101`.
   - digits-first at a misaligned run: `"10a"` &lt; `"a10"`, and the two ranks are
     distinct and ordered (`NAME_RANK_NUMERIC < NAME_RANK_TEXT`).
   - `""`, `None`, a non-string and a digit-free name raise nothing and stay
     totally ordered.
   - **Sentinel-boundary analogue** of `SentinelBoundaryTests`: a name embedding
     `str(1 << 30)` is not conflated with a text run and keeps
     `NAME_RANK_NUMERIC`.

2. **`PaneSortKeyTests` additions:**
   - `test_the_window_name_dominates_the_window_index` — `agent-pick-2` at
     window index `10` sorts before `agent-pick-10` at window index `2`.
   - `test_the_session_still_dominates_the_window_name` — session `sA` holding
     the last-sorting name precedes session `sB` holding the first-sorting one.
   - `test_a_duplicate_name_falls_back_to_the_window_index` and
     `…_then_to_the_pane_index` — the deterministic total-order tiebreak.

3. **Session-grouping under interleaving names** (the case the requirement
   names): sessions `sA` = `agent-pick-90`, `sB` = `agent-pick-1`. Assert both
   at key level (`sorted(..., key=pane_sort_key)`) and at render level through
   the real minimonitor in multi-session mode (`_mk_list_app(...,
   multi_session=True)`, already available here) — `sB`'s first-sorting name
   must not surface above `sA`'s panes, and the dividers must stay one per
   session.

4. **Render-level + parity on the name fixture:** a `MiniMonitorOrderTests` case,
   a `MonitorOrderTests` case, and a new `CrossTuiOrderParityTests` case driving
   the one name fixture through both TUIs and comparing the two rendered orders
   to **each other** (the existing index-fixture parity case stays).

5. **`NameFixtureControlTests`** — the required negative controls, proving the
   fixture discriminates in both ways a weaker fixture would hide:
   - `test_the_index_only_key_orders_the_name_fixture_differently` — the t1659
     key (`session, tmux_index_key(window_index), tmux_index_key(pane_index)`,
     kept as a `PRE_NAME_KEY` literal beside the existing `PRE_FIX_KEY`) orders
     the fixture into the index order, not the name order.
   - `test_a_lexicographic_name_key_orders_the_name_fixture_differently` — a
     plain `s.pane.window_name` key yields `LEXICOGRAPHIC_NAME_ORDER`, so a
     single-digit-only fixture would pass every case above while proving nothing.

Also refresh the module docstring: it currently describes only the t1659 index
fix; it must state that the second slot is now the natural window-name key and
that the index slots survive as the tiebreak.

### Step 5 — Docs (prose ordering rule; no config key)

- `website/content/docs/tuis/minimonitor/how-to.md`, **How to Read the Agent
  List** — one paragraph after the first: agents are ordered by tmux **window
  name** within each session, compared naturally so `agent-pick-2` precedes
  `agent-pick-10`; a child task's window (`agent-pick-100_1`) follows its
  parent's; two windows sharing a name fall back to window then pane index.
- `website/content/docs/tuis/monitor/reference.md` — a short **Pane Order**
  subsection after **Pane Classification**, stating the same rule once for both
  TUIs (they share one key, so their lists cannot differ) and noting that
  session grouping leads the order.

## Verification

### Automated

```bash
# 1. The targeted module — 17 existing cases + the new ones, all green.
python3 tests/test_monitor_pane_sort_order.py

# 2. The Python suite, which covers every other module that stubs a pane list
#    (session divider, minimonitor other-section, …). Read the LAST line only.
bash tests/run_all_python_tests.sh --test-dir tests

# 3. The two shell modules the suite does not run; the second pins discovery order.
bash tests/test_multi_session_minimonitor.sh
bash tests/test_multi_session_monitor.sh

# 4. Docs build (subshell — do not leave the shell in website/).
( cd website && hugo build --gc --minify )
```

### Manual

Worth one look, since this is a visual ordering change. With several `agent-*`
windows open whose ids cross the digit boundary, run `ait minimonitor` and
confirm the list reads `…-2, -9, -10, -20`, and that a window launched last but
named low sorts high.

---

Post-implementation cleanup, archival and merge follow **Step 9
(Post-Implementation)** of the task workflow.

## Risk

Levels reassessed after the inline mitigation below was confirmed: code-health
moved medium → low, because the load-bearing invariance is now pinned
executably rather than argued.

### Code-health risk: low
- Changing `pane_sort_key` also changes **discovery** order. The safety argument
  rests on `window_name` being a *per-window* property — so the new slot cannot
  reorder panes within a window, keeping `_find_own_agent_snapshot` (the `e`/`E`
  and review-loop resolution seam) invariant — and that invariant is asserted
  nowhere today. · severity: medium · → mitigation: inline pre-phase
  characterize_within_window_order_invariance
- Two downstream seams break exact ties on discovery order —
  `monitor_app.py:1436/1447` (auto-switch, stable sort on `idle_seconds`) and
  `minimonitor_app.py:2975` (duplicate task-id warning). Both stay fully
  deterministic; only *which* pane wins a tie shifts, to name order.
  · severity: low · → mitigation: accepted, not mitigated — recorded in the
  `pane_sort_key` docstring (Step 2); a proposed `pin_autoswitch_tiebreak_determinism`
  regression case was considered and dropped as disproportionate
- ~19 other test modules stub pane lists that flow through this key. They were
  cleared by inspection (names and indices coincide, or session/category
  dominates), not by execution. · severity: low · → mitigation: covered by
  Verification step 2, which executes them

### Planned mitigations
- timing: pre-phase | name: characterize_within_window_order_invariance | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — discovery-order change is only safe because the key cannot reorder panes within a window | desc: Characterization case pinning that pane_sort_key preserves pane-index order within one session+window, passing on both the pre-change and post-change key.

### Goal-achievement risk: low
- None identified. The requirement is a precise second-slot swap with a named
  comparison discipline; every clause (natural comparison, category slot, child
  suffix, deterministic ties, session grouping, the four test additions, the
  knob decision) is addressed explicitly, and the approach was validated against
  a green baseline run of the existing 17 cases.
