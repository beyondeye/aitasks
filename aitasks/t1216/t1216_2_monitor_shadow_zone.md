---
priority: high
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: [t1216_1]
issue_type: feature
status: Implementing
labels: [aitask_monitor, shadow, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1111
implemented_with: claudecode/opus5
created_at: 2026-07-27 22:21
updated_at: 2026-07-28 15:33
---

## Context

Second child of **t1216** (make `ait monitor` shadow-aware). Depends on
**t1216_1**, which lifts the shadow lookup/capture/refresh seams into
`monitor_core.py`.

This child delivers the first two acceptance criteria of the parent: from
`ait monitor` the shadow pane bound to a selected agent can be **viewed live**
(content, not just the `◆` status glyph landed by t1133), and keystrokes can be
**directed at either the agent pane or its shadow pane** with an unambiguous,
visible indication of the current target.

**Shape decided with the user:** a third zone, `SHADOW`, rendered as a
**horizontal split of the existing preview area** — agent preview on the left,
shadow preview on the right, with the shadow column's width matching the
**real shadow pane's width** so its content renders unwrapped. Focused zone =
key target, which is what makes the targeting indication free: the active zone
already draws a `zone-active` border and a `LIVE` badge.

Parent plan: `aiplans/p1216_monitor_shadow_pane_view_and_concern_picker.md`.

## Key files to modify

- `.aitask-scripts/monitor/monitor_app.py` (2070 lines) — all of it here.
- `website/content/docs/tuis/monitor/_index.md` — "Understanding the Layout"
  currently says "four stacked areas" then lists five; add the shadow column.
- `website/content/docs/tuis/monitor/reference.md` — the zone table (L65-66).

## Reference points in `monitor_app.py` (verified live)

| Line | What |
|---|---|
| 80-85 | `Zone` enum (`PANE_LIST`, `PREVIEW`) and `ZONE_ORDER` |
| 92-105 | `PREVIEW_SIZES`, `PREVIEW_DEFAULT_SIZE`, layout constants |
| 128-178 | `PreviewPanel(Static, can_focus=True)`, `PreviewScrollContainer` |
| 316-389 | The app's inline `CSS` class attr (no `.tcss` files exist) |
| 391-410 | `BINDINGS` (`c`, `e`, `E` are free; `t`, `z`, `Tab` are taken) |
| 474-486 | `compose()` — `#content-section` > `#preview-scroll` > `#content-preview`, plus `#content-header` **docked bottom** |
| 625-649 | `_locate_anchor` (static), scroll plumbing |
| 651-684 | `_record_preview_scroll` |
| 702-781 | `_refresh_data` — the 3 s tick |
| 783-807 | `_fast_preview_refresh` — the 0.3 s tick |
| 1171-1266 | `_update_content_preview` (render-gen guard, PAUSED/LIVE badge, frozen branch) |
| 1268-1339 | `_apply_preview_render` (offloaded `_ansi_to_rich_text`, guarded scroll restore) |
| 1341-1387 | `_switch_zone`, `_focus_first_in_zone`, `_update_zone_indicators` |
| 1417-1421 | `check_action` — disables every non-`switch_zone` binding in PREVIEW |
| 1429-1435 | `_manage_preview_timer` |
| 1457-1515 | `on_key` (PREVIEW catch-all at 1486) and `_forward_key_to_tmux` |
| 1517-1535 | `on_descendant_focus`, `_get_focused_pane_id` |
| 1558-1610 | `action_cycle_preview_size`, `_apply_preview_size`, `action_scroll_preview_tail`, `on_resize` |

## Implementation

### 1. Zone

Add `Zone.SHADOW` to the enum and `ZONE_ORDER`. `_switch_zone` (L1341) **skips**
`SHADOW` when the selected agent has no bound shadow, so `Tab` behaves exactly
as today for non-shadowed agents. `check_action` (L1417) must treat `SHADOW`
like `PREVIEW`.

### 2. Leaving an already-active invalid zone (NON-OPTIONAL)

Entry-time skipping is not enough — the shadow can vanish *while* `SHADOW` is
focused, either permanently or for a single tick (t1133's `LifecycleTests` pin
that a transient capture failure legitimately drops the snapshot with no stale
preservation). Yanking the user out on a one-tick blip would be its own bug:

- Snapshot absent, shadow still bound → **hold** the zone, render a
  `[dim](shadow unavailable)[/]` placeholder.
- Absent for `SHADOW_ABSENT_GRACE_TICKS = 2` consecutive **full** refreshes, or
  the followed pane has no bound shadow at all → fall back to `Zone.PREVIEW`,
  restore focus there, notify once.
- **While the shadow is absent, keystrokes in `SHADOW` are dropped, never
  forwarded.** They must not fall through to the agent pane — that would type a
  user's shadow input into a working agent. Safety property; own test.
- Switch away from `SHADOW` when the pane-list selection moves to an agent with
  no shadow (the selection drives which shadow is shown).

### 3. Layout

`compose()` gains a `Horizontal(id="preview-row")` inside `#content-section`
holding two columns:

- `#agent-col` — the existing `#preview-scroll` > `#content-preview` (**keep
  both ids**, plus `#content-header`, so nothing else breaks).
- `#shadow-col` — `#shadow-scroll` > `#shadow-preview`, plus `#shadow-header`.
  `display: none` unless a shadow is bound.

**Width:** `#shadow-col.styles.width = shadow_snap.pane.width` (+ scrollbar
gutter) and `#shadow-preview.styles.min_width = shadow_snap.pane.width`,
mirroring what the agent preview already does at L1240. `TmuxPaneInfo.width` is
populated for shadow panes too (`_parse_list_panes` parses `#{pane_width}` for
them). Heights are untouched, so `PREVIEW_SIZES` / `_apply_preview_size` keep
working unchanged — this is a benefit of splitting horizontally.

**Narrow fallback:** decide on the **mounted row's usable content width**, NOT
`self.size.width`. `self.size.width` is the screen width and ignores
`#content-section`'s border, `scrollbar-gutter: stable`, padding, and the shadow
column's own gutter; at the boundary that error is several columns and would
leave the agent column too narrow or overflowing. Measure
`self.query_one("#preview-row").content_region.width` and subtract the shadow
column's full occupied width including its gutter; if the remainder is below
`SHADOW_MIN_AGENT_COLS = 40`, do not split — render only the focused zone's
column full-width. Evaluate on mount, in `on_resize` (L1606), and after
`_apply_preview_size` (L1563), each via `call_after_refresh` so the measurement
happens post-layout.

### 4. `t` (Tail) must follow the active column

`action_scroll_preview_tail` (L1593-1604) is hard-wired to `#preview-scroll` and
`_preview_scroll_state`; left alone it would silently tail the agent preview
while the user looks at the shadow.

Note the constraint that fixes its meaning: `check_action` (L1417) disables
every non-`switch_zone` binding while a preview zone is focused (keys there are
forwarded to tmux), so **`t` is only ever pressable from `PANE_LIST`** — "the
active column" cannot mean "the focused zone". Define it as the **last-focused
preview column**: track `_active_preview_zone` (`PREVIEW` | `SHADOW`), updated
by `_switch_zone` and `on_descendant_focus`, defaulting to `PREVIEW` and
**reset to `PREVIEW` whenever the shadow column is hidden, absent, or the
selection moves to an agent with no shadow**. `t` resumes tail-follow for that
column, resetting its scroll state to `(True, None)` and scheduling the matching
fast refresh.

`z` (`action_cycle_preview_size`) needs no such treatment — the split is
horizontal, so the height presets apply to both columns unchanged.

### 5. Rendering and the fast tick

`_update_shadow_preview` mirrors `_update_content_preview`: its **own**
render-generation counter, PAUSED/LIVE badge, frozen branch, per-shadow-pane
scroll anchors in a `_shadow_scroll_state` map, and the offloaded
`_ansi_to_rich_text` via `_run_offloaded`. **Reuse** `_locate_anchor` and a
`_record_preview_scroll` parameterised by target rather than cloning them.

`_manage_preview_timer` (L1429) also starts the 0.3 s timer for `Zone.SHADOW`,
driving `TmuxMonitor.refresh_shadow_snapshot` from t1216_1. It runs **only**
while the shadow zone is focused, so users with no shadows pay nothing per tick.

### 6. Key targeting

In `on_key`, add a `Zone.SHADOW` branch **above** the existing PREVIEW catch-all
at L1486, forwarding to the shadow pane id. Resolve it from
`self._focused_pane_id` → `get_shadow_snapshot(...)` — **never**
`_get_focused_pane_id()` (L1529), which returns `None` whenever focus is off a
`PaneCard`.

## Verification

New `tests/test_monitor_shadow_zone.py`, following
`tests/test_monitor_shadow_status.py`'s `_make_monitor` fixture (L78-110; real
`TmuxMonitor`, scripted coroutines, `_sync_offloaded`, no tmux, no sleeps) and
its `MountedCardRenderTests` pilot idiom (L490) for render assertions:

- Zone skipping with and without a bound shadow.
- Shadow column width derived from `pane.width`.
- Key forwarding targets the shadow pane in `SHADOW` and the agent pane in
  `PREVIEW` (spy on `forward_key`).
- **Negative control:** adding the zone leaves the shadow out of `_snapshots`,
  the pane list, and kill / next-sibling targeting.
- **Narrow-fallback boundary** — mounted pilot `run_test(size=(W, 30))` driven
  at `W` = threshold−1 / threshold / threshold+1, asserting `#shadow-col.display`
  flips at exactly the intended column and the agent column's laid-out width
  never drops below `SHADOW_MIN_AGENT_COLS`. Derive `W` from the measured chrome
  rather than hardcoding — that is what proves the decision is not made on the
  raw screen width.
- **`t` targets the active column, independently for each** — after focusing the
  agent preview and returning to the pane list, `t` restores tail-follow on the
  agent column and leaves the shadow column's anchor untouched; after focusing
  the shadow column, the reverse. Assert on both `_preview_scroll_state` and
  `_shadow_scroll_state` entries **and** on which fast refresh was scheduled, so
  a helper that tails "both" or the wrong one fails. Plus the reset cases (no
  shadow bound; shadow disappeared).
- **Zone invalidation while focused** — absent 1 tick holds the zone and renders
  the placeholder; absent for `SHADOW_ABSENT_GRACE_TICKS` falls back to
  `PREVIEW`; unbound entirely falls back immediately; a key pressed while
  `SHADOW` is focused-but-absent produces **zero** `forward_key` calls (asserted
  against the agent pane id specifically).

```bash
bash tests/run_all_python_tests.sh
bash tests/test_no_raw_tmux.sh
```

Manual (from a shell **outside** the main aitasks tmux session — see
`aidocs/framework/tui_conventions.md`): spawn a shadow from minimonitor, open
`ait monitor`, Tab into the shadow column, confirm content renders unwrapped at
the real pane width and typing lands in the shadow.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-28T12:33:25Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-28T15:06:02Z status=pass attempt=1 type=human
