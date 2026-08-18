---
Task: t1566_minimonitor_chrome_order_own_panel_height_session_bar.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1566 — Minimonitor top chrome: order, own-panel height, session bar default

## Context

In the 40-column minimonitor companion pane the top chrome is wrong in three
ways, all regressions or leftovers from **t1499** (`8580112e4`, "Undock
minimonitor's top chrome so it renders at all"):

1. The two live banners (`#mini-shadow-stale`, `#mini-loop-status`) render
   **above** `#mini-own-agent`, pushing the pane's primary identity surface —
   the followed agent — down the screen. Their position was never chosen; it is
   whatever compose order the four docked widgets happened to have when t1499
   undocked them.
2. `#mini-own-agent` is capped at `max-height: 4` while its content needs more,
   so it paints a **scrollbar instead of the data**.
3. `#mini-session-bar` is on by default, costing a permanent row in a
   40-column companion pane.

**Reproduced live** at 40×30 against the current build (`fbb9d2644`):

```
PANEL region: Region(x=0, y=1, width=40, height=4)
virtual_size: Size(width=38, height=5)   container_size: Size(width=40, height=3)
show_vertical_scrollbar: True
 1| ── this agent ──                       |
 2| ★ agent-t1566-chrome                 ▁▁|   <- scrollbar glyph U+2581
 3|   chrome order own panel height and    |   <- title line 2 and the phase
 4|────────────────────────────────────────|      line are clipped away
```

Beyond the three stated defects, the chrome budget itself is the real problem:
the own panel has to grow, and it must not do so by eating the agent list. So
the governing constraint for this change is **the pane list keeps a row before
verbose advisory chrome does** — the banners yield, not the list.

Intended outcome: the followed agent sits at the top of the pane, its panel
renders every row with no scrollbar **at any pane width**, the banners flow
beneath it as one line each, and the pane list keeps its floor.

## Approach

### 1. Chrome order

`compose()` (`.aitask-scripts/monitor/minimonitor_app.py:778`) and `_TOP_CHROME`
(:448) both move to:

```
#mini-session-bar (hidden by default) → #mini-own-agent → #mini-shadow-stale
  → #mini-loop-status → #mini-pane-list
```

`_TOP_CHROME` feeds `_refresh_short_mode`, which only *sums* the four heights —
order there is documentation, not behaviour — but the stylesheet's block comment
(:490) and the budget comment above `_TOP_CHROME` (:443) both describe the order
explicitly and must move with it.

### 2. Own panel: width-independent content, then a derived cap

The current 8-row worst case is an artifact of 40 columns — the window name is
handed to Rich unwrapped, so at narrower widths it folds over three, four or
more rows and no fixed cap can hold. Bound the **content** first, and the cap
becomes true at every width.

In `_own_agent_identity_text` (:1579), pre-wrap the **name** the same way the
title is already wrapped, and drop the wrap floors that exceed what actually
fits:

```python
w = max(8, self._target_width - 4)          # == the "★ " budget: 36 at 40 cols
lines = textwrap.wrap(snap.pane.window_name, w)[:2] or [""]
# ellipsize line 2 when the name was truncated — mirrors the title branch
```

- `self._target_width - 4` is **exactly** the existing glyph budget (`padding: 0 1`
  ⇒ 38 usable at 40 columns, minus `"★ "` ⇒ 36), so
  `test_minimonitor_own_mark.CompositedWidthTests.test_a_36_char_name_still_fits_beside_the_glyph`
  keeps passing — **verified**: a 36-char name still composites as
  `★ agent-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` on one line.
- The title's `max(20, target_width - 4)` floor drops to `max(8, …)` for the same
  reason: at 22 columns a floor of 20 makes each title line wrap to two rows,
  which is what broke the guarantee there.

Row table, now **width-independent by construction**:

| rows | source |
|---|---|
| 1 | `── this agent ──` header (`.mini-own-header`, `height: 1`) |
| 2 | identity — name wrapped to ≤2 lines, glyph inline on line 1 |
| 2 | task title, `textwrap.wrap(info.title, w)[:2]` |
| 1 | advisory phase (`_own_phase_text`) |
| 1 | `border-bottom: solid $primary` — **`max-height` is border-box**, verified |

```python
_OWN_PANEL_MAX_ROWS = (
    1      # "── this agent ──" header
    + 2    # identity — name wrapped to at most two lines
    + 2    # task title, textwrap.wrap(...)[:2]
    + 1    # advisory phase line
    + 1    # border-bottom (max-height is border-box)
)          # == 7
```

Set it at the single reveal site in `_maybe_build_own_agent_panel` (:1743), one
line below the load-bearing `panel.display = True`, and drop `max-height` from
the `#mini-own-agent` CSS rule (leaving a comment pointing at the constant):

```python
panel.styles.max_height = _OWN_PANEL_MAX_ROWS
```

The CSS block has no `%` today, so `CSS = """…""" % (…)` would work — but a
future `width: 50%` would silently break it. Setting it in Python keeps the
derivation next to its comment and puts both lines under the same tests.

**Verified live** — no scrollbar, all rows, at every width tested:

| width | typical name | 126-char pathological name |
|---|---|---|
| 40 | 6 rows, no scrollbar | 7 rows, no scrollbar |
| 30 | 6 rows, no scrollbar | 7 rows, no scrollbar |
| 26 | 6 rows, no scrollbar | 7 rows, no scrollbar |
| 22 | 6 rows, no scrollbar | 7 rows, no scrollbar |

(The previous 8-row design scrolled the pathological name even at 40 columns.)

### 3. Advisory banners yield first

**`#mini-shadow-stale` → one row, one line.** Add a keyword-only
`narrow: bool = False` to `format_shadow_stale_banner`
(`.aitask-scripts/monitor/monitor_shared.py:1204`); both minimonitor call sites
(:2829, :3542) pass `narrow=True`. The `combine_staleness` ladder that *decides*
stays single-sourced — only the wording branches:

| combined verdict | narrow text | cells |
|---|---|---|
| `None` | `⚠ freshness unknown` | 19 |
| `False` | `""` | 0 |
| `True` | `⚠ shadow feedback is stale` | 26 |

The age / round detail is dropped from the banner. It remains available where it
belongs: `format_staleness_detail` already feeds the concern picker, and
`ait monitor` keeps the full wording. CSS cap `max-height: 1`.

**`#mini-loop-status` → `max-height: 2`** (from 3). Derived from its real
literals, not a guess: the four strings `_set_loop_banner` is ever called with
are 20, 27, 30 and 39 cells, and only the 39-cell
`⟳ recheck #N sent — waiting for shadow` exceeds the 38 usable columns — so two
rows is its true worst case and the third row was dead budget.

### 4. Hide the session bar by default

Hide the **widget only**. `monitor.multi_session` stays `True`, so agents from
other sessions keep appearing in the pane list and `M` keeps working.

- CSS `#mini-session-bar` gains `display: none`, joining the other collapsible
  chrome (an empty `height: auto` Static still costs one row — the reason the
  existing t1499 comment calls `display: none` load-bearing).
- New **class** attribute `_session_bar_enabled = False` — class-level, not an
  `__init__` assignment, following the `_list_scroll_lock` /
  `_pending_scroll_state` precedent already in this file (t1539):
  `tests/test_multi_session_minimonitor.sh` builds the app with
  `MiniMonitorApp.__new__(...)` and would `AttributeError` on an `__init__`-only
  default. `__init__` takes `session_bar: bool = False` and sets the instance
  value.
- `_rebuild_session_bar` (:1385) sets `bar.display = self._session_bar_enabled`
  alongside its existing `bar.update(...)`. Both existing stub call sites
  (`test_markup_colour_contract.py:374`, `test_multi_session_minimonitor.sh:293`)
  pass a plain object as `bar`, which accepts the attribute write unchanged.
- **`on_mount`'s "Not inside tmux" path (:795) must reveal the bar explicitly.**
  It is the only surface that error has, and it returns before
  `_start_monitoring()` ever reaches `_rebuild_session_bar`. Without the reveal a
  user launching outside tmux sees a blank pane.
  `test_not_inside_tmux_error_is_visible` already guards this.
- `main()` (:3925) reads the sibling of the existing `tmux.minimonitor.width`
  key: `session_bar` (default `false`), guarded with the same
  `isinstance(mm_cfg, dict) and "session_bar" in mm_cfg` shape `width` uses, so a
  malformed `minimonitor:` value falls back rather than raising.

`.aitask-scripts/lib/agent_launch_utils.py` is **not** touched — the spawner has
no use for a render-time flag.

**Config discoverability.** `seed/project_config.yaml` carries no `minimonitor:`
block at all (`width`, `auto_spawn`, `companion_window_prefixes` are all
undocumented there), so the task's own conditional — "seed the key *if* the
seeded config carries the sibling" — says skip it. Document the key instead as a
commented-out entry in the live `aitasks/metadata/project_config.yaml`, already
in the task's Files list.

## The floor this change is accountable to

With the capped banners the worst-case chrome is **9 rows**, and the pane list
keeps a row down to pane height **12** at 40 columns — verified end to end with
the full 7-row own panel *and* both banners live:

```
chrome = 0 session bar + 7 own panel + 1 shadow-stale + 1 loop-status  = 9
hints  = 2 (short mode)
       -----------------------------------------------------------------
         11  →  the pane list keeps its row at height 12
```

| pane height | 30 | 20 | 16 | 14 | 13 | 12 | 11 |
|---|---|---|---|---|---|---|---|
| list rows | 11 | 9 | 5 | 3 | 2 | **1** | 0 |

12 is a **proven bound**, stated rather than implied: below it there is nothing
left to give without a third layout tier, and a 12-row companion pane is far
below anything realistic. No cramped tier is added.

## Tests

### `tests/test_minimonitor_top_chrome_render.py`

The fixture writes the session bar with a raw
`query_one("#mini-session-bar").update(...)`, which cannot reveal a
`display: none` widget. Route it through the production seam instead: give
`_populate` / `_run` a three-state `session` parameter —

- `True` — enabled: `_session_bar_enabled = True` + the real
  `_rebuild_session_bar()`, then `update(SESSION_TEXT)` for a stable probe;
- `False` — production default: `_session_bar_enabled = False` +
  `_rebuild_session_bar()`, which **hides** the bar, undoing `on_mount`'s
  not-inside-tmux reveal and modelling the real in-tmux default;
- `None` — leave `on_mount`'s state alone (only `test_not_inside_tmux_error_is_visible`).

Everything asserts on **rendered geometry / composited text** per
`aidocs/framework/tui_conventions.md`.

Updated:

- `test_own_agent_panel_is_visible_and_flows_below_the_banners` → renamed and
  inverted: the panel now flows **above** both banners.
- `test_top_chrome_widgets_do_not_share_a_region` — `CHROME_IDS` follows the new
  `_TOP_CHROME`; runs with `session=True` so all four have height ≥ 1 and the
  ordering is not vacuous.
- `test_empty_chrome_costs_no_rows` — the bar joins the zero-row set; the pane
  list moves from `(y=1, h=19)` to `(y=0, h=20)`, hints stay at `y=20`.
- `test_collapsible_chrome_returns_to_zero_rows_when_cleared` — bar added to the
  both-directions toggle.
- `STALE_TEXT` now comes from `format_shadow_stale_banner(..., narrow=True)`;
  `SHORT_PROBE_HEIGHT = 20`'s comment re-derived (banners live → chrome 9,
  `9 + 10 + 3 > 20` → engages; own panel alone → chrome 3,
  `3 + 10 + 3 ≤ 20` → stays off — still discriminating).

New:

- `test_own_agent_panel_renders_every_row_without_a_scrollbar` — **fails on the
  current build**. A followed agent with a 2-line wrapped title **and** a phase
  line renders all five content rows, with no glyph from `▁▂▃▄▅▆▇█`
  (U+2581–U+2588) inside the panel's region. Its positive control is the
  126-char name under a deliberately reverted cap, which **must** trip the same
  detector — otherwise the assertion is unfalsifiable.
- `test_own_panel_holds_seven_rows_at_every_pane_width` — the width-independence
  claim, parametrised over widths 22/26/30/40 × (typical, 126-char) names:
  height ≤ `_OWN_PANEL_MAX_ROWS`, no scrollbar glyph, and the full title text
  present in the frame.
- `test_pane_list_keeps_a_row_under_full_live_chrome` — **the floor the change is
  accountable to.** Full 7-row own panel + both banners live, at heights
  30/20/16/14/13/12: the list keeps ≥ 1 row and never runs into the docked hints.
  Pins 12 with the arithmetic in the docstring, so a future chrome growth fails
  here instead of silently costing the list its floor.
- `test_shadow_stale_banner_occupies_exactly_one_row` — height is exactly 1 at
  40 columns **and** the full narrow string is present uncut, so the cap is
  shown to be sized to the text rather than clipping it.
- `test_loop_banner_longest_literal_fits_two_rows` — the 39-cell
  `⟳ recheck #N sent …` renders in ≤ 2 rows, pinning the tightened cap against
  the real string rather than a replica.

### `tests/test_minimonitor_session_bar_config.py` (new)

The rendered tests set `_session_bar_enabled` **directly**, so on their own they
never exercise `main()` reading `tmux.minimonitor.session_bar`, its default, or
forwarding it through `MiniMonitorApp.__init__`. A typo in the key, or an omitted
constructor argument, would leave the new user-facing config **silently
ineffective while every rendered test still passes**.

`main()` is drivable end to end through its module-level seams — **verified**:
patch `load_project_tmux_config`, `load_monitor_config`, `_detect_tmux_session`,
`sys.argv` and `MiniMonitorApp` (a capture stub whose `run()` is a no-op), then
call `mm.main()` and read the captured kwargs. Nothing touches tmux or the real
config file. Against the current build the harness already returns a kwargs list
with **no `session_bar`** — a working positive control.

| `tmux_config` | expected `session_bar` kwarg |
|---|---|
| `{}` (no `minimonitor:` block) | `False` |
| `{"minimonitor": {"width": 40}}` (block present, key absent) | `False` |
| `{"minimonitor": {"session_bar": False}}` | `False` |
| `{"minimonitor": {"session_bar": True}}` | `True` |
| `{"minimonitor": "oops"}` (malformed) | `False` — must not raise |

Plus the second link, against the **real** constructor: default leaves
`_session_bar_enabled` `False`; `session_bar=True` sets it `True`.

Together with the render module this closes the chain with no gap: config value →
`main()` → constructor kwarg → `_session_bar_enabled` → `bar.display` (via the
real `_rebuild_session_bar`) → rows occupied on screen.

### `tests/test_shadow_seam.py`

Extend the existing `format_shadow_stale_banner` ladder coverage with the
`narrow=True` arm: same four verdict rows, asserting the short strings and that
`False` still yields `""`.

## Pre-phase (risk mitigation)

1. **`wire_session_bar_config_end_to_end`** — build
   `tests/test_minimonitor_session_bar_config.py` *alongside* the `main()` /
   `__init__` edit rather than after it, so the config key is proven live from
   the moment it exists.

## Post-phase (risk mitigations)

1. **`guard_own_panel_cap_is_applied`** — assert the panel's rendered height
   never exceeds `_OWN_PANEL_MAX_ROWS` for a pathological name at every tested
   width. This is what makes the `panel.styles.max_height` line load-bearing now
   that the cap no longer lives in the stylesheet; verify by deleting the line
   and confirming this case fails.
2. **`pin_worst_case_chrome_ceiling`** — sum the four chrome maxima (session bar
   `1` + `_OWN_PANEL_MAX_ROWS` + shadow-stale `1` + loop-status `2`) and assert
   the total against a named ceiling constant with the derivation commented, so a
   future cap bump fails at review rather than by eating the list's floor.

## Risk

### Code-health risk: medium
- The chrome-order, cap and banner edits land on a layout surface with a
  two-regression history (t1499 undocked it; this task fixes what its cap broke),
  and they change the very heights `_refresh_short_mode`'s measured predicate
  consumes · severity: medium · → mitigation: inline post-phase
  pin_worst_case_chrome_ceiling
- `max-height` moves out of the stylesheet into `panel.styles.max_height`, so
  layout for this widget is decided in two places and a dropped line would
  silently unbound the chrome rather than fail · severity: medium · → mitigation:
  inline post-phase guard_own_panel_cap_is_applied
- Pre-wrapping the window name changes a rendering path pinned by
  `test_minimonitor_own_mark.CompositedWidthTests` · severity: medium · →
  mitigation: none needed — the `target_width - 4` budget was chosen to equal the
  existing one and the 36-char case is **verified** still composited on one line
- `_session_bar_enabled` must be a class attribute or the `__new__`-built stub
  apps break · severity: low · → mitigation: none needed — hazard verified,
  precedent (`_list_scroll_lock`, t1539) already in this file

### Goal-achievement risk: low
- The new `session_bar` config key is the only way to restore the bar, and the
  rendered tests set `_session_bar_enabled` directly — a misspelt key would ship
  the option **inert** with the suite green · severity: medium · → mitigation:
  inline pre-phase wire_session_bar_config_end_to_end
- All three defects were reproduced live and every fix measured before planning
  (cap knee, width sweep 22–40, floor sweep to height 11), so the approach is
  evidence-backed rather than inferred · severity: low · → mitigation: none needed
- Dropping the age/round detail loses the t1493 read-recency vs block-age
  distinction from this banner · severity: low · → mitigation: none needed —
  explicitly chosen by the user; the detail stays in the concern picker
  (`format_staleness_detail`) and in `ait monitor`

### Planned mitigations
- timing: pre-phase | name: wire_session_bar_config_end_to_end | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — the `session_bar` key could ship inert | desc: new `tests/test_minimonitor_session_bar_config.py` driving `main()` through its patched config seams for all five config shapes plus the constructor default/forwarding pair
- timing: post-phase | name: guard_own_panel_cap_is_applied | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — `max-height` decided in two places | desc: rendered-geometry case pinning that the panel never exceeds `_OWN_PANEL_MAX_ROWS` at any tested width, so dropping `panel.styles.max_height` fails instead of silently unbounding the chrome
- timing: post-phase | name: pin_worst_case_chrome_ceiling | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — chrome growth eats the pane-list floor | desc: pin the summed worst-case chrome against a documented ceiling constant so a future cap increase fails at review

**Reassessment** (per `risk-evaluation.md`, run once against the augmented plan):
levels unchanged — **code-health medium**, **goal-achievement low**. The three
guards close the "two places", "chrome ceiling" and "inert config key" bullets,
but the chrome-order edit still lands on the measured short-mode budget, which is
what holds code-health at medium.

## Known bounds (stated, not absorbed)

- **Pane list floor: height ≥ 12 at 40 columns**, proven by the sweep above. No
  third layout tier.
- **Narrow-banner text fits at ≥ 28 columns.** `⚠ shadow feedback is stale` is 26
  cells and a 26-column pane has 24 usable, so below 28 the `max-height: 1` cap
  clips it. Honouring the one-row contract is the deliberate trade;
  `text-overflow: ellipsis` is **not available** in the pinned Textual 8.2.7
  (verified), so the clip is a hard cut.
- **Pre-existing defect found, not fixed here:** `_KEY_HINTS_ROWS` is a newline
  count, not a rendered height, so below ~24 columns the hints occupy far more
  rows than `_refresh_short_mode` believes (22 rows at 18 columns) and the floor
  breaks there — from the *hints*, not the own panel.
  `test_key_hints_occupy_one_row_per_line` only pins the equality at 40 columns.
  Out of scope for t1566; worth its own task.

## Files

- `.aitask-scripts/monitor/minimonitor_app.py` — `compose()`, `CSS`,
  `_TOP_CHROME`, `_OWN_PANEL_MAX_ROWS` (new), `__init__`, `on_mount`,
  `_rebuild_session_bar`, `_own_agent_identity_text`,
  `_maybe_build_own_agent_panel`, the two `format_shadow_stale_banner` call
  sites, `main()`
- `.aitask-scripts/monitor/monitor_shared.py` — `format_shadow_stale_banner`
  gains `narrow`
- `tests/test_minimonitor_top_chrome_render.py`
- `tests/test_minimonitor_session_bar_config.py` — **new**
- `tests/test_shadow_seam.py` — `narrow=True` ladder arm
- `aitasks/metadata/project_config.yaml` — commented `session_bar` key

## Verification

1. `~/.aitask/venv/bin/python -m pytest tests/test_minimonitor_top_chrome_render.py
   tests/test_minimonitor_session_bar_config.py tests/test_shadow_seam.py -v`
2. Negative controls, one mutation each, checking the named case fails on **its
   own** assertion rather than an earlier one:
   - revert `panel.styles.max_height` to `4` → the scrollbar case fails;
   - delete the `panel.styles.max_height` line → `guard_own_panel_cap_is_applied` fails;
   - restore `#mini-shadow-stale`'s `max-height: 3` and the verbose text →
     `test_pane_list_keeps_a_row_under_full_live_chrome` fails at height 12;
   - misspell the config key in `main()` → only the config module's
     `explicit true` row fails, every rendered test still passes.
3. Regression sweep of every module touching the bar, the panel or the banner:
   `tests/test_minimonitor_own_mark.py` (the 36-char budget),
   `tests/test_markup_colour_contract.py`, `tests/test_textual_markup_structure.py`,
   `tests/test_monitor_completed_status.py`,
   `tests/test_minimonitor_scroll_preservation.py`, and
   `bash tests/test_multi_session_minimonitor.sh`.
4. `bash tests/run_all_python_tests.sh` — read only the last line for the verdict.
5. Live: `ait minimonitor` in a 40-column companion pane — followed agent at the
   top with name + both title lines + phase and no scrollbar, one-line banners
   beneath it, no session bar; then set `tmux.minimonitor.session_bar: true` and
   confirm the bar returns.

---

## Implementation notes (what landed, and where it deviated)

All plan steps landed. Seven deviations, each forced by something measured
during implementation rather than chosen:

1. **`#mini-own-agent` gained `overflow-y: hidden`** — not in the plan. At 22
   columns the panel still scrolled: a visible scrollbar reserves two columns,
   which re-wraps the name, which makes the panel taller, which keeps the
   scrollbar. Reserving nothing breaks that loop. Independently justified — the
   panel mounts plain Statics and sits outside the focus ring
   (`action_show_own_task_info`), so a thumb advertised rows the user could
   never reach, which *is* the defect rather than a mitigation of it.
2. **`_OWN_PANEL_MAX_ROWS` is 7, not 8.** Pre-wrapping the window name bounds
   the identity block to two rows, so the "glyph folds onto a line of its own
   plus two name lines" worst case the plan budgeted three rows for cannot
   happen.
3. **`#mini-loop-status` capped 3 → 2 rows.** Derived from the four literals
   `_set_loop_banner` is actually called with (20/27/30/39 cells); only the
   39-cell one needs a second row, so the third was dead budget the pane list
   wanted.
4. **`_target_width` promoted to a class attribute.** It used to be read only
   inside `_own_agent_identity_text`'s has-a-task branch; wrapping the name made
   the read unconditional, which broke every `__new__`-built stub. Same
   precedent as `_list_scroll_lock` (t1539).
5. **`FLOOR_HEIGHT` is 14, not the planned 12.** The plan's 12 was measured with
   the session bar hidden and a non-folding name — not the worst case. The test
   now sweeps the true worst case (bar enabled + folding name) and derives the
   constant as `_MAX_CHROME_ROWS + _SHORT_HINT_ROWS + 1`, with a negative
   control at `FLOOR_HEIGHT - 1` proving it is the real boundary.
6. **Four test modules had incomplete panel stubs.** `_FakePanel` /
   `_FakeContainer` in `test_minimonitor_own_mark.py`,
   `test_minimonitor_other_section.py`, `test_monitor_session_divider.py` and
   `test_multi_session_minimonitor.sh` modelled only the mount surface; they now
   carry `display` and `styles`, because `_maybe_build_own_agent_panel` writes
   both. An incomplete stub raises on the extra write rather than ignoring it.
7. **`test_minimonitor_concern_action.py` banner assertions retargeted.** Four
   cases asserted `"analyzed"` / `"predates"` / `"moved on"` on
   `_shadow_stale_banner_text`, which the narrow arm collapses. They now assert
   the exact `SHADOW_STALE_NARROW` constant. **The guard is preserved, not
   weakened**: each case already pinned *which* branch fired through
   `_shadow_feedback_stale` / `_shadow_stale_combined`, and the per-branch
   wording is covered where it is produced, in
   `test_shadow_seam.FormatShadowStaleBannerTests`.

**Seed config: deliberately skipped**, per the task's own conditional —
`seed/project_config.yaml` carries no `minimonitor:` block at all (`width`,
`auto_spawn` and `companion_window_prefixes` are equally undocumented there), so
there is no sibling to seed alongside. The key is documented in the live
`aitasks/metadata/project_config.yaml` instead.

### Verification performed

- `tests/test_minimonitor_top_chrome_render.py` — 23 passed (10 new).
- `tests/test_minimonitor_session_bar_config.py` — 9 passed (new module).
- `tests/test_shadow_seam.py` — 92 passed (5 new, the `narrow=True` arm).
- `bash tests/test_multi_session_minimonitor.sh` — 43/43.
- `bash tests/run_all_python_tests.sh` — **PYTHON SUITE: PASSED (runner=pytest,
  exit=0)**.
- Four negative controls, each failing on its own assertion: cap 7→4 loses the
  phase row; cap line deleted overruns at width 22 and nulls `max_height`;
  verbose 3-row banner breaks the floor at height 15 and the one-row pin;
  misspelt config key fails **only** `test_explicit_true_reaches_the_constructor`
  while all 23 rendered tests stay green — the divergence that justifies the
  separate config module.
- `main()` driven over the **real** `aitasks/metadata/project_config.yaml` in
  both directions: `session_bar: false` → `False`, `session_bar: true` → `True`.

**Not performed:** a live `ait minimonitor` boot in a real tmux pane. Verification
is at the compositor level (`app.screen._compositor.render_strips`), which is
what `aidocs/framework/tui_conventions.md` prescribes and what every case in
these modules asserts on; no tmux-facing code was changed.

## Final Implementation Notes

- **Actual work done:** All three scoped defects fixed, plus the pane-list floor
  constraint the user added at plan review. Chrome reordered to
  `#mini-session-bar → #mini-own-agent → #mini-shadow-stale → #mini-loop-status`
  in `compose()`, `_TOP_CHROME` and the stylesheet comment. The own panel is
  sized by a derived `_OWN_PANEL_MAX_ROWS` (7) applied at the reveal site, with
  the window name pre-wrapped to at most two lines so the budget is
  width-independent. `#mini-shadow-stale` is a one-row surface fed by a new
  `narrow=True` arm on `format_shadow_stale_banner`; `#mini-loop-status` was
  tightened 3 → 2 rows. The session bar ships hidden behind
  `tmux.minimonitor.session_bar`, read in `main()` and threaded through a new
  constructor kwarg onto a class-attribute-defaulted `_session_bar_enabled`.
- **Deviations from plan:** Seven, all recorded in full under "Implementation
  notes (what landed, and where it deviated)" above. The load-bearing ones:
  `overflow-y: hidden` on the own panel (unplanned — a scrollbar-reservation
  feedback loop kept the panel scrolling at 22 columns, and the panel is
  non-focusable so a thumb advertised unreachable rows); `_OWN_PANEL_MAX_ROWS`
  came out 7 rather than 8; and `FLOOR_HEIGHT` came out 14 rather than the
  planned 12 because the plan's figure was measured in a configuration that was
  not the worst case.
- **Issues encountered:**
  - *Scrollbar feedback loop at narrow widths.* A visible scrollbar reserves two
    columns → the name re-wraps → the panel grows → the scrollbar stays.
    Resolved by removing the reservation entirely (`overflow-y: hidden`).
  - *`min-height: 1` on the pane list looked like an elegant floor guarantee and
    is a fake one.* Textual reports the list at height 1 while placing it
    underneath the docked hints — the DOM looks right and the compositor paints
    over it, the same failure mode as t1499. Rejected on measurement.
  - *Four test modules carried incomplete panel stubs* that modelled only the
    mount surface and raised on the new `styles` write. Completed rather than
    worked around; suppressing the write would have made a load-bearing line
    fail silently.
  - *Operator error:* `git checkout --` on `tests/test_minimonitor_top_chrome_render.py`
    to undo a temporary negative-control mutation also discarded that file's
    uncommitted t1566 work. Rebuilt and all four negative controls re-run
    against the rebuilt file.
- **Key decisions:**
  - The cap lives in Python (`panel.styles.max_height`) rather than the
    stylesheet so the number sits beside its row-by-row derivation; a literal in
    the CSS would be a second, silently-drifting copy. Because nothing in the CSS
    then fails if the line is dropped, `test_the_cap_is_applied_at_the_reveal_site`
    exists to make it load-bearing.
  - The narrow banner is a `narrow=True` **arm** of the existing formatter, not a
    sibling function: only the wording branches, and the `combine_staleness`
    ladder that decides the verdict stays single-sourced, so the two forms can
    never disagree about whether to warn.
  - Config wiring got its own test module. The rendered tests set
    `_session_bar_enabled` directly, so a misspelt key would ship the option
    inert with the whole suite green — verified as a negative control, where only
    the config module fails and all 23 rendered tests still pass.
  - `FLOOR_HEIGHT` is derived from `_MAX_CHROME_ROWS + _SHORT_HINT_ROWS + 1` and
    paired with a boundary negative control, so a raised cap moves the floor
    automatically instead of leaving a stale literal that stops probing the real
    edge.
- **Upstream defects identified:**
  - `.aitask-scripts/monitor/minimonitor_app.py:489 — _KEY_HINTS_ROWS is a newline count, not a rendered height, so below ~24 columns _refresh_short_mode under-measures the docked hints (22 rendered rows at width 18 against a believed 10) and the pane-list floor breaks there; tests/test_minimonitor_top_chrome_render.py:456 only pins the equality at 40 columns`
