---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [minimonitor, tui, shortcuts, layout]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
folded_tasks: [1574]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-11-05 08:38
updated_at: 2026-11-05 09:03
---

## Goal

Give `ait minimonitor`'s bottom key-hint band three states instead of one fixed band:

1. **Full** — today's band (`KEY_HINTS_TEXT`, ~10 lines), plus the two new keys below.
2. **Collapsed** — a single line that names only the toggle key and the help key (e.g. `x:keys  H:help`), giving ~9 rows back to the agent list.
3. **Full help** — a separate key opens a scrollable modal listing **every** minimonitor binding with a full, one-paragraph explanation of what it does.

## Decisions taken during exploration (user-confirmed)

- **One key toggles expand ↔ collapse** (same key both ways). Proposed: `x`. It is free in both minimonitor and the full monitor (the two apps keep identical keys where they overlap), and it echoes board's `X` = "Collapse Col". `z` is NOT available (full monitor: zoom).
- **Full-help key: `H`**, not `?`. `?` is bound framework-wide by `ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS` to the shortcut editor in every TUI (and is surfaced as `?:keys` in the band). `H` matches the existing precedent in brainstorm (`H` = "Op help", `brainstorm_app.py`, `brainstorm/modals.py OperationHelpModal`) and is free in minimonitor and monitor. Keep `?` as the shortcut editor; the help modal may point at it ("press ? to rebind").
- **The collapsed/expanded choice persists per user** in `aitasks/metadata/userconfig.yaml` (via the `userconfig_persist` helpers — `_load_full` / `_atomic_dump`; add a small getter/setter pair like `get_last_used_labels`/`set_last_used_labels`), so every newly auto-spawned minimonitor opens in the last-chosen mode. Fail-soft on a malformed / unwritable userconfig (toggle still works for the session).

## Where the code is

- `.aitask-scripts/monitor/minimonitor_app.py`
  - `KEY_HINTS_TEXT` (~line 1025) — the band's text, with a long comment block recording the measured row budget.
  - `_KEY_HINTS_ROWS = KEY_HINTS_TEXT.count("\n") + 1`, `_SHORT_HINT_ROWS = 2`, `_PANE_LIST_FLOOR_ROWS`, `_MAX_CHROME_ROWS`, `_TOP_CHROME` (~1080–1130).
  - CSS: `#mini-key-hints { dock: bottom; height: auto; ... }` and `MiniMonitorApp.short #mini-key-hints { max-height: 2; }` (~1369–1382).
  - `BINDINGS` (~1385) — all `show=False`; minimonitor renders no Footer, so the band is its only key surface (tui_conventions.md "surface the hint in the pane's own text" exception).
  - `compose()` yields `Static(KEY_HINTS_TEXT, id="mini-key-hints")` (~1621).
  - `_refresh_short_mode` (~1697) — automatic short mode (t1499) that compacts the band when the top chrome needs rows; must be made aware of the collapsed state (collapsed ⇒ short mode is moot; predicate must use the *current mode's* desired height and still never read its own output height — see the docstring's no-oscillation argument).
- `.aitask-scripts/lib/shortcuts_mixin.py` — `?` binding, `label()` / `resolve_key()` for override-aware rendering.
- `.aitask-scripts/lib/shortcut_editor_modal.py` — modal style reference (self-contained `DEFAULT_CSS`, `GuardedModalScreen` precedent in brainstorm modals).

## Design notes for planning

- **One table drives everything.** Introduce a single structured table (key action id → short hint label → long description) from which the full band, the collapsed line, and the help modal are all derived. The help modal must resolve keys through `resolve_key(self._shortcuts_scope, action)` so a user's rebinds show correctly. Today `KEY_HINTS_TEXT` is static and shows the *default* key even after a rebind (pre-existing gap) — decide in planning whether the band itself also becomes override-aware (preferred: "one constant drives binding + hint", and the key-override memory: test dispatch, not just render — a remapped key must be tested by pressing it).
- **Both new keys must be rebindable** (registered under the `minimonitor` scope like every other binding) and must be listed in the help modal itself.
- **Modal must work in a ~40-column, ~20-row companion pane** (and degrade down to the widths the other minimonitor modals support, ~24 cols). Scrollable; Esc / `H` / `q` closes. Probe the host Screen CSS when sizing (see `_apply_measured_width_tier` in `monitor_shared.py` for the measured-width tier pattern).
- **Row budget risk.** Adding `x:` and `H:` to the full band strains its tested budget: rendered height at (15, 30) must stay ≤ 29 (`test_own_header_names_the_session_without_clipping_at_any_width`), and the band is pinned to TEN rows at 40 columns (`test_key_hints_occupy_one_row_per_line`, `test_pane_list_keeps_a_row_at_every_pane_height`). MEASURE the rendered region, never eyeball; Rich word-wraps. Folding the new keys into the existing `?:keys` line (e.g. `?:rebind x:hide H:help`) is one candidate.
- **Full-monitor parity:** decide whether `ait monitor` gets `H` too (it has a Footer, so it needs the help modal less). At minimum keep `x` and `H` free there so the two apps don't diverge.

## Tests to update / add

- `tests/test_minimonitor_concern_action.py::test_key_hints_surface_every_binding` — every binding key must appear in the hint text; extend to the new keys and to the help-table (every binding has a long description; no table row without a binding).
- `tests/test_minimonitor_top_chrome_render.py` — height pins, short-mode engage/release, floor tests; add: collapsed mode renders exactly 1 row, frees the rows for the pane list, survives a short-mode transition, and the toggle round-trips.
- Other suites assert substrings of `mm.KEY_HINTS_TEXT` (`test_minimonitor_scratchpad_spawn.py`, `test_monitor_parked_filter.py`, `test_monitor_frozen_filter.py`, `test_minimonitor_own_task_info.py`, `test_minimonitor_shadow_pick.py`, `test_monitor_agent_marks.py`, `test_minimonitor_own_mark.py`, `test_minimonitor_pick_by_number.py`) — keep `KEY_HINTS_TEXT` (or its derived equivalent) importable or update every consumer (whole-file grep of old-literal assertions).
- Persistence: toggle writes userconfig; a fresh app instance starts collapsed when userconfig says so; malformed userconfig falls back to full. Tests must use a scratch userconfig path, never the real one.
- Keypress tests for `x` and `H`, including under a key override.

## Docs

- `website/content/docs/tuis/minimonitor/how-to.md` — add a "How to collapse the key hints / open full key help" section and add `x`, `H` to **Key Bindings Quick Reference**. That table is also missing the existing `h` (harvest followed agent) and `S` (sitrep window) rows from t2175_5 — add them. Note the persistence in userconfig.
- Run `python3 check_links.py --build` in `website/` after editing.

## Merged from t1574: minimonitor key hints rendered height


## Origin

Spawned from t1566 during Step 8b review. Pre-existing; not caused by t1566 and
not fixable by its caps.

## Upstream defect

- `.aitask-scripts/monitor/minimonitor_app.py:489 — _KEY_HINTS_ROWS is a newline
  count, not a rendered height, so below ~24 columns _refresh_short_mode
  under-measures the docked hints (22 rendered rows at width 18 against a
  believed 10) and the pane-list floor breaks there;
  tests/test_minimonitor_top_chrome_render.py:456 only pins the equality at 40
  columns`

## Diagnostic context

t1566 made the minimonitor's own-agent panel width-independent and proved the
pane-list floor holds at 40 columns down to pane height 14. Sweeping the same
fixture across narrower panes showed the floor still breaking at width 18 — but
**not** because of the own panel, which holds its 7-row cap with no scrollbar at
22, 26, 30 and 40 columns. Measured at width 18: `#mini-key-hints` composites
**22 rows** while `_refresh_short_mode`'s predicate believes `_KEY_HINTS_ROWS`
== 10, so it never engages short mode and the pane list is squeezed to a
1-row-overlapping region.

The constant is derived as `KEY_HINTS_TEXT.count("\n") + 1` — a count of
authored lines, which equals the rendered height only while no hint line wraps.
`test_key_hints_occupy_one_row_per_line` pins that equality, but only at 40
columns, so the divergence at narrow widths is invisible to the suite.

This is the same defect class the constant's own comment warns about ("a line
long enough to wrap invalidates this loudly instead of silently shifting the
threshold") — the guard just does not cover the axis that actually breaks it,
which is pane width rather than hint-text length.

## Suggested fix

Measure the hints' desired height at the current width instead of counting
newlines — e.g. have `_refresh_short_mode` read the widget's own rendered
height, or compute the wrapped line count against `self.size.width`. Beware the
feedback loop the current design deliberately avoids: the predicate must not
consume the hints' *current* height (which short mode itself changes), so a
width-aware **desired** height is the value to derive. Extend
`test_key_hints_occupy_one_row_per_line` into a width sweep, and add the floor
case at widths 18/22 that fails today.

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t1574** (`t1574_minimonitor_key_hints_rendered_height.md`)
