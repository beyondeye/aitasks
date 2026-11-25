---
Task: t2359_minimonitor_docked_frozen_card_line_overflow.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2359 — Budget the docked frozen card's second line

## Context

When the agent a minimonitor follows is frozen, the docked own-agent card
(`MiniMonitorApp._own_card_text`, frozen branch,
`.aitask-scripts/monitor/minimonitor_app.py:3353-3367`) renders

```
<mark>F <identity>
  frozen 2026-11-24T18:52:00Z drop ok, triaged
```

The second line's content is `frozen`(6) + ` `(1) + the full `_TS_FMT` stamp (20)
+ the sitrep badge suffix (up to 1+16) = 44 cells, against the 36-cell
`_own_phase_budget(40)`. Static wraps it, and `_OWN_PANEL_MAX_ROWS` reserves ONE
row for this line, so the badge (the actionable part: is it safe to drop?) lands
on a hidden continuation row or pushes the border. Any badge of ≥ 7 cells
already overflows. Pre-existing from t2337; t2354 fixed only the list rows.

## Approach (decided)

Keep the word `frozen` on this line — unlike the list rows there is no name to
protect here, and the word is what labels the stamp ("frozen <when>"). Instead:

1. **Shorten the stamp** to `MM-DD HH:MMZ` (12 cells, still UTC-labelled by the
   `Z`, locale-free), parsed from the canonical `agent_sessions._TS_FMT`. An
   unparseable value falls back to the raw string (still clipped below), and
   `""` (record unreadable) keeps rendering just `frozen`.
   Widest case at width 40: `frozen 11-24 18:52Z drop ok, triaged` = 6+1+12+1+16
   = **36 = budget exactly**.
2. **Shed ladder** for narrower configured widths, budget =
   `_own_phase_budget(self._target_width)`:
   - full `frozen <stamp><badge>` if it fits;
   - else drop the stamp (`frozen<badge>`) — the badge is the actionable signal,
     the stamp is informational;
   - else, **when a badge is present**, drop the word `frozen` too and show the
     badge alone (the t2354 rule — line 1's cyan `F` already says frozen).
     Measured: without this rung Textual's truncate yields `frozen drop ok, t…`
     at width 22 (budget 18, where the whole 16-cell badge fits) and
     `frozen drop …` at width 17. With `None` (no verdict) the word IS the
     state and is never shed;
   - else truncate what is left to the budget with an ellipsis
     (`Content.truncate(budget, ellipsis=True)`, Textual 8.2.7 — verified; it
     keeps styled spans): at width 17 the badge alone clips to
     `drop ok, tri…`, keeping the verdict readable.

**Scope of the no-wrap claim.** Like every minimonitor budget, this one reads the
*configured* `target_width`. When the real pane is narrower than that (tmux
cannot fit the target; `_maybe_pin_width` only shrinks), the line can still wrap
— measured headless: a 38-column pane given the 40-column line wraps and hides
`triaged`. That is t2007's (`budget_actual_pane_width`) scope, not this task's:
the comments and docs here claim "fits its configured width", not "never wraps",
and t2007 gets a note (Step 4) adding the docked frozen line to its
actual-width/resize coverage.

### Step 1 — `minimonitor_app.py`

- Add a small module-level helper near `_own_phase_budget`:

  ```python
  def _short_frozen_stamp(frozen_at: str) -> str:
      """`frozen_at` (`agent_sessions._TS_FMT`) as `MM-DD HH:MMZ` (t2359) …"""
      if not frozen_at:
          return ""
      try:
          dt = datetime.strptime(frozen_at, agent_sessions._TS_FMT)
      except ValueError:
          return frozen_at      # shown as-is; the ladder/clip bounds it
      return dt.strftime("%m-%d %H:%MZ")
  ```
  (`from datetime import datetime` added to the imports; no tz conversion — the
  stored stamp is already UTC and keeps its `Z`.)

- In `_own_card_text`'s frozen branch, replace the single
  `Content.from_markup("\n  [dim]frozen$stamp[/]", stamp=stamp) + badge` with a
  helper method `_own_frozen_line(frozen_at, sitrep_state) -> Content` that
  builds the content (stamp still passed as a `$stamp` variable, never parsed as
  markup — t2017), applies the ladder above using `cell_len` of the plain parts
  and `frozen_state_width(state)` for the badge, and returns the line (without
  the `"\n  "`, which the caller prepends as framework markup).
- Extend the budget comment block (~line 279) with the docked frozen line's
  arithmetic: `frozen␠<MM-DD HH:MMZ><␠badge ≤ 17>` = 36 at width 40, and what
  gives way (stamp first, then clip).
- Update `_own_card_text`'s frozen-branch comment.

### Step 2 — Tests

- `tests/test_minimonitor_row_budget.py`: new `DockedFrozenLineBudgetTests`
  - over every `ms.FROZEN_SITREP_BADGES` key plus `None`, with the widest stamp
    (`2026-12-31T23:59:59Z`) at width 40: the second line's plain text is ≤
    `mm._own_phase_budget(40)`, contains the short stamp `12-31 23:59Z`, starts
    with `frozen`, and ends with the full badge text (nothing shed at the
    default width);
  - at narrow widths (30, 22, 17, 10, 4): ≤ budget for every state; at 30
    `frozen drop ok, triaged` (stamp shed); at 22 the complete badge
    `drop ok, triaged` alone (word shed, no `…`); at 17 a readable verdict —
    starts with `drop ok` and ends with `…`; `None` at 22 still reads
    `frozen`;
  - `""` stamp → `frozen` + badge; unparseable stamp → raw, still ≤ budget.
  - red proof: write the test first and run it against the unchanged code —
    the old line renders 44 cells for `TRIAGED`, so the ≤-budget assertion must
    fail there; record that failure, then implement (no stash, no restore).
- `tests/test_minimonitor_top_chrome_render.py`: a rendered check through the
  real docked panel (`_ChromeFixture`, `own="full"` so the two-row title is in
  play), with a **naturally two-line name that leaves room for the 3-cell
  frozen prefix**: `"agent-pick-" + "very-long-window-name-" * 2 + "end"`
  (the `OWN_LONG_NAME` shape from `test_monitor_markup_literal_sinks.py` —
  line 1 `agent-pick-very-long-window-name-` = 33 cells + `☆F ` = 36 ≤ 38).
  **Not** `OWN_WINDOW_PATHOLOGICAL`: its 36-cell first fold plus `☆F ` is 39
  cells against 38, so the prefix forces an extra row and the height cap hides
  the detail line whatever this task does — a separate, pre-existing defect
  (below). With that name,
  `app._own_frozen_at` stubbed to `2026-12-31T23:59:59Z` and
  `app._frozen_sitrep_state` to `TRIAGED` before the panel builds: at a 40×30
  screen with target 40, exactly one composited row inside `#mini-own-agent`'s
  region contains `frozen 12-31 23:59Z drop ok, triaged` whole, and the
  panel's height stays ≤ `mm._OWN_PANEL_MAX_ROWS`. This catches what the
  Content-level matrix cannot: padding, the height cap and the two-row name and
  title together. Red proof: with the old full stamp the same render clips
  `triaged`.
- Update pins that encode the old full stamp:
  - `tests/test_monitor_markup_literal_sinks.py` `OWN_PANEL_CASES["frozen"]`
    expected text `  frozen 09-04 09:20Z` and its dim span end (86 + 20 = 106).
  - `tests/test_monitor_frozen_filter.py`
    `MinimonitorOwnPanelTests.test_it_shows_the_marker_and_the_stamp` →
    asserts `09-04 09:20Z`.
  - grep for any other `frozen 20…T…Z` own-card pins (e.g.
    `tests/test_minimonitor_own_mark.py`, `tests/test_monitor_frozen_sitrep_badge.py`)
    and update.

### Step 3 — Docs

- `website/content/docs/tuis/minimonitor/how-to.md:178`: the second line reads a
  dim `frozen`, the month-day and UTC time it was frozen at (`frozen 11-24
  18:52Z`), and the sitrep state once read; when the configured width is too
  narrow for all of it the time goes first, then the word `frozen` (the **F**
  still says it), so the state stays visible where it fits; on a very narrow
  width the state itself is shortened with `…`, and it can disappear entirely
  when almost no space is left. No unconditional "never wraps" claim. Run `python3 check_links.py --build` in `website/`.
- `aidocs/framework/sitrep.md:684`: "keeps `frozen <MM-DD HH:MMZ>` and appends
  the badge, budgeted to the configured width: the stamp is shed first, then
  the word (t2359); a pane narrower than its configured width is t2007's".

### Step 4 — Note to t2007

`./ait note 2007 --from 2359 --with-live --file -`: the docked own-agent card's
frozen line (`_own_frozen_line`, budget `_own_phase_budget(self._target_width)`)
now fits its configured width exactly at 40 and sheds stamp → word → clip, but
like the other budgets reads `target_width`; headless, a 38-column pane given
the 40-column line wraps and hides `triaged`. Include it (and the phase line,
same budget) in the actual-width + resize rebuild and its tests.

### Step 5 — Record the pre-existing identity overflow separately

`_own_agent_identity_text` folds the window name at `wrap_width =
target_width - 4` (36 at 40), which budgets the 2-cell `★ ` glyph; a frozen
card's prefix is `<mark>F ` = 3 cells, so a first fold of 36 cells renders 39
against 38 usable, the name takes an extra row, and `_OWN_PANEL_MAX_ROWS`' cap
hides the frozen detail line. Not fixed here (different code, different budget
— the identity is built once, before freezing is known). Recorded at Step 8b as
an upstream-defect follow-up task (`aitask_create.sh --batch`, labels
`aitask_monitormini, frozen_agents, tui`), with the measured case, and not
claimed as covered by this task's tests.

## Verification

- `python3 -m pytest` (venv) on `tests/test_minimonitor_row_budget.py`,
  `tests/test_monitor_markup_literal_sinks.py`, `tests/test_monitor_frozen_filter.py`,
  `tests/test_monitor_frozen_sitrep_badge.py`, `tests/test_minimonitor_own_mark.py`.
- Then `bash tests/run_all_python_tests.sh --test-dir tests` is not needed in
  full; run the monitor/minimonitor subset above plus
  `tests/test_minimonitor_*` via pytest `-k` free glob.
- `cd website && python3 check_links.py --build`.

## Step 9

Post-implementation: commit code (`bug: … (t2359)`), plan via
`aitask_task_commit.sh`, archival per Step 9 of task-workflow.

## Risk

### Code-health risk: low
None identified. (One function's frozen branch plus a pure helper; the only
other effect is the intended change to characterization pins that encode the
old full stamp.)

### Goal-achievement risk: low
- The no-wrap guarantee holds only when the pane reaches its configured width;
  a narrower real pane still wraps · severity: low · → mitigation: out of scope
  here, owned by existing t2007 (note sent in Step 4); claims scoped accordingly.
- A frozen name whose first fold is 36 cells still pushes the detail line under
  the panel cap (3-cell frozen prefix vs the 2-cell identity budget) ·
  severity: low · → mitigation: pre-existing, recorded as a separate follow-up
  (Step 5); the render test uses a name that does not trigger it.
Otherwise: the widest badge fits exactly at the default width. At narrower
configured widths the ladder keeps the verdict whole where it fits (e.g. the
full badge at 22) and clips it once space runs out (`drop ok, tri…` at 17,
`drop o…` at 11, nothing at 4). Both the all-states string matrix and a
composited render pin this.
