---
Task: t1216_2_monitor_shadow_zone.md
Parent Task: aitasks/t1216_monitor_shadow_pane_view_and_concern_picker.md
Sibling Tasks: aitasks/t1216/t1216_1_shared_shadow_seam.md, aitasks/t1216/t1216_3_monitor_concern_picker.md, aitasks/t1216/t1216_4_monitor_shadow_spawn.md
Base branch: main
Output branch: main
---

# p1216_2 — `SHADOW` zone: side-by-side shadow preview + key targeting

Depends on **t1216_1** (`TmuxMonitor.refresh_shadow_snapshot`,
`find_shadow_pane`, `compute_shadow_staleness`).

## Goal

From `ait monitor`: view the selected agent's shadow pane **live**, and direct
keystrokes at either the agent pane or its shadow, with an unambiguous visible
indication of the current target.

Shape (decided with the user): a third zone `SHADOW`, rendered as a
**horizontal split** of the existing preview area — agent left, shadow right —
with the shadow column sized to the **real shadow pane's width** so its content
renders unwrapped. Focused zone = key target.

## Step 1 — the zone

`monitor_app.py:80-85`:

```python
class Zone(Enum):
    PANE_LIST = "pane_list"
    PREVIEW = "preview"
    SHADOW = "shadow"

ZONE_ORDER = [Zone.PANE_LIST, Zone.PREVIEW, Zone.SHADOW]
```

- `_switch_zone` (L1341-1348) currently does `(idx + direction) % len(ZONE_ORDER)`.
  Make it **skip** `Zone.SHADOW` when the selected agent has no bound shadow, so
  `Tab` behaves exactly as today for non-shadowed agents. Loop rather than
  single-step so a skip cannot land on an invalid zone.
- `_focus_first_in_zone` (L1350-1368) gains a `SHADOW` branch focusing
  `#shadow-preview`.
- `_update_zone_indicators` (L1370-1387) toggles `zone-active` on `#shadow-col`
  as well as `#pane-list` / `#content-section`.
- `check_action` (L1417-1421) must treat `SHADOW` like `PREVIEW`:

```python
if self._active_zone in (Zone.PREVIEW, Zone.SHADOW):
    return action == "switch_zone"
return action != "switch_zone"
```

- `on_descendant_focus` (L1517-1527) sets `Zone.SHADOW` when the focused widget
  is the shadow preview panel.

## Step 2 — leaving an already-active invalid zone

Entry-time skipping is not enough. The shadow can vanish *while* `SHADOW` is
focused, and there are two different causes that must not be conflated:

- **Permanent** — the shadow pane died, so the followed pane no longer has a
  bound shadow.
- **Transient** — a one-tick capture failure. `tests/test_monitor_shadow_status.py::LifecycleTests`
  pins that this legitimately drops the snapshot with **no** stale preservation.
  Yanking the user out of the zone on a one-tick blip would be its own bug.

Transitions:

| State | Behaviour |
|---|---|
| Snapshot absent, shadow still bound | **hold** the zone; render `[dim](shadow unavailable)[/]` |
| Absent for `SHADOW_ABSENT_GRACE_TICKS = 2` consecutive **full** refreshes | fall back to `Zone.PREVIEW`, restore focus, notify once |
| Followed pane has no bound shadow at all | fall back immediately |
| Pane-list selection moves to an agent with no shadow | fall back (the selection drives which shadow is shown) |

**While the shadow is absent, keystrokes in `SHADOW` are dropped, never
forwarded.** They must not fall through to the agent pane — that would type a
user's shadow input into a working agent. This is a safety property with its own
test.

Count the grace ticks in `_refresh_data` (the 3 s full tick, L702-781), not in
the 0.3 s fast tick, so the grace window is a wall-clock ~6 s rather than 0.6 s.

## Step 3 — layout

`compose()` (L474-486) becomes:

```python
yield Container(
    Horizontal(
        Vertical(
            PreviewScrollContainer(PreviewPanel("", id="content-preview"),
                                   id="preview-scroll"),
            Static("[bold]Content Preview[/]", id="content-header"),
            id="agent-col",
        ),
        Vertical(
            PreviewScrollContainer(PreviewPanel("", id="shadow-preview"),
                                   id="shadow-scroll"),
            Static("[bold]Shadow[/]", id="shadow-header"),
            id="shadow-col",
        ),
        id="preview-row",
    ),
    id="content-section",
)
```

**Keep `#content-section`, `#preview-scroll`, `#content-preview` and
`#content-header` ids** — `_update_content_preview` (L1172-1177),
`_apply_preview_size` (L1563-1591) and the CSS all query them by id.
`#content-header` currently uses `dock: bottom` scoped to `#content-section`
(CSS L367-372); re-scope it to `#agent-col` so each column's header docks under
its own body, and give `#shadow-header` the mirrored rule.

CSS additions (the app uses an inline `CSS` class attr at L316-389; there are no
`.tcss` files in the repo):

```css
#preview-row  { height: 1fr; }
#agent-col    { width: 1fr; }
#shadow-col   { width: auto; display: none; border-left: solid $primary-darken-2; }
#shadow-col.zone-active { border-left: solid $warning; }
#shadow-scroll { height: 1fr; scrollbar-gutter: stable; }
```

Leave `#content-section { max-height: 24 }` and `#preview-scroll { max-height: 22 }`
as they are: the split is **horizontal**, so `PREVIEW_SIZES` (L97-104) and
`_apply_preview_size` (which sets only `max_height` on `#content-section` and
`#preview-scroll`) keep working untouched. Add `#shadow-scroll` to the
`max_height` assignments in `_apply_preview_size` so both columns resize together.

**Width.** `#shadow-col` is shown only when a shadow is bound, and then:

```python
w = shadow_snap.pane.width
shadow_col.styles.width = w + 1          # +1 for the stable scrollbar gutter
shadow_preview.styles.min_width = w
```

mirroring what the agent preview already does at L1240
(`preview.styles.min_width = snap.pane.width`). `TmuxPaneInfo.width` is
populated for shadow panes too — `_parse_list_panes` parses `#{pane_width}`
(field 6) for them before the shadow branch at L1185.

## Step 4 — narrow fallback

Decide on the **mounted row's usable content width**, not `self.size.width`.
`self.size.width` is the screen width and ignores `#content-section`'s border,
`scrollbar-gutter: stable`, padding, and the shadow column's own gutter; at the
boundary that error is several columns and would leave the agent column too
narrow or overflowing.

```python
def _shadow_split_fits(self, shadow_width: int) -> bool:
    try:
        row = self.query_one("#preview-row")
    except Exception:
        return False                      # not mounted yet — no split
    avail = row.content_region.width      # post-layout, chrome already excluded
    return (avail - (shadow_width + 1)) >= SHADOW_MIN_AGENT_COLS
```

`SHADOW_MIN_AGENT_COLS = 40`. When it does not fit, do **not** split: render
only the focused zone's column full-width (`display` toggled on the other).

Evaluate on mount, in `on_resize` (L1606-1610), and after `_apply_preview_size`
(L1563), each via `call_after_refresh` so the measurement happens **post-layout**
— `content_region` is meaningless before the first layout pass.

## Step 5 — `t` (Tail) must follow the active column

`action_scroll_preview_tail` (L1593-1604) is hard-wired to `#preview-scroll` and
`_preview_scroll_state`; left alone it would silently tail the agent preview
while the user is looking at the shadow.

The constraint that fixes its meaning: `check_action` (L1417) disables every
non-`switch_zone` binding while a preview zone is focused (keys there are
forwarded to tmux), so **`t` is only ever pressable from `PANE_LIST`** — "the
active column" cannot mean "the currently focused zone".

Define it as the **last-focused preview column**:

- `self._active_preview_zone: Zone = Zone.PREVIEW`, updated by `_switch_zone`
  and `on_descendant_focus` whenever focus lands on `PREVIEW` or `SHADOW`.
- **Reset to `Zone.PREVIEW`** whenever the shadow column is hidden (narrow
  fallback), the shadow is absent, or the selection moves to an agent with no
  shadow.
- `t` resets that column's scroll state to `(True, None)`, calls `scroll_end` on
  that column's scroller, and schedules the matching fast refresh
  (`_fast_preview_refresh` or `_fast_shadow_refresh`).

`z` (`action_cycle_preview_size`, L1558) needs no such treatment — the split is
horizontal, so the height presets apply to both columns unchanged.

## Step 6 — rendering

`_update_shadow_preview` mirrors `_update_content_preview` (L1171-1266) with a
**separate** `_shadow_render_gen` counter (bumped on **every** entry, including
the no-shadow / frozen / empty branches — the agent version does this at
L1188-1189 precisely so a slow in-flight render can never clobber a newer
state), plus:

- header text on `#shadow-header`: the shadow pane id and its followed agent,
  with `[bold green]LIVE[/]` when `_active_zone is Zone.SHADOW`,
  `[bold yellow]PAUSED[/]` when its scroll state says paused, else nothing;
- the frozen branch (`same_pane and (is_paused or scroll.user_is_scrolling)`);
- `_shadow_scroll_state: dict[str, tuple[bool, str | None]]` keyed by **shadow**
  pane id, pruned alongside `_preview_scroll_state` in `_refresh_data`
  (L734-745);
- `run_worker(..., exclusive=True, group="shadow-preview")` — a **different**
  group from the agent preview's `group="preview"` (L1259-1262), or the two
  columns would cancel each other's renders.

**Reuse, do not clone:** `_locate_anchor` (L633-649, a `@staticmethod`) works as
is; parameterise `_record_preview_scroll` (L651-684) on which
scroller/state-map/rendered-lines it is recording for, and wire
`scroll.on_user_scroll` for `#shadow-scroll` in `_start_monitoring` next to the
existing hook at L616-620.

## Step 7 — the fast tick

`_manage_preview_timer` (L1429-1435) starts the 0.3 s timer when entering
`PREVIEW`; extend it to `SHADOW`, dispatching to `_fast_shadow_refresh`:

```python
async def _fast_shadow_refresh(self) -> None:
    pane_id = self._focused_pane_id          # pin before the await
    if not pane_id or not self._monitor:
        return
    snap = await self._monitor.refresh_shadow_snapshot(pane_id)
    if snap is None:
        return                                # no update this tick (see below)
    if pane_id == self._focused_pane_id:
        self._update_shadow_preview()
```

`refresh_shadow_snapshot` returns `None` both for a failed capture and for a
followed pane with no known shadow (t1216_1 rule 3 — it never resurrects). Treat
both as "no update this tick"; **the full refresh owns deletion**, and Step 2's
grace counter is driven from `_refresh_data`, not from here.

Because the timer only runs while `SHADOW` is focused, users with no shadows pay
nothing.

## Step 8 — key targeting

In `on_key` (L1457-1501), insert a `SHADOW` branch **above** the PREVIEW
catch-all at L1486:

```python
if self._active_zone == Zone.SHADOW:
    shadow = self._current_shadow_pane_id()      # None when absent
    if shadow and self._monitor:
        self._forward_key_to_tmux(event, target_pane_id=shadow)
    event.stop(); event.prevent_default(); return
```

`_forward_key_to_tmux` (L1503-1515) gains an optional `target_pane_id`
defaulting to `self._focused_pane_id`, so the PREVIEW path is unchanged.

`_current_shadow_pane_id()` resolves `self._focused_pane_id` →
`self._monitor.get_shadow_snapshot(...)` → `.pane.pane_id`. Use
`self._focused_pane_id` — **never** `_get_focused_pane_id()` (L1529-1535), which
returns `None` whenever focus is off a `PaneCard`, i.e. always in this branch.

Note the `event.stop()` is unconditional (as in the PREVIEW branch): when the
shadow is absent the key is **swallowed**, which is exactly the required
drop-never-forward behaviour.

## Step 9 — docs

- `website/content/docs/tuis/monitor/_index.md` — "Understanding the Layout"
  says "four stacked areas" then lists five; fix the count and add the shadow
  column. Extend "Navigating the Monitor" with the third zone and what `Tab`
  does when no shadow is bound.
- `website/content/docs/tuis/monitor/reference.md` — the zone table at L65-66,
  and note that `t` targets the last-focused preview column.

## Verification

New `tests/test_monitor_shadow_zone.py`, following
`tests/test_monitor_shadow_status.py`'s `_make_monitor` fixture (L78-110: real
`TmuxMonitor`, scripted `discover_panes_with_shadows_async` /
`capture_pane_content_async` coroutines, `_run_offloaded` overridden to run
synchronously — no tmux, no sleeps) and its `MountedCardRenderTests` pilot idiom
(L490: `async with app.run_test(size=(W, H)) as pilot`).

Note the module-level `os.environ.pop("TMUX"/"TMUX_PANE")` at L33-35 of that
file — replicate it so `MonitorApp.on_mount` takes the deterministic
not-in-tmux path.

- Zone skipping with and without a bound shadow; `ZONE_ORDER` cycling both
  directions.
- Shadow column width derived from `pane.width`; `#shadow-col` hidden when no
  shadow is bound.
- Key forwarding targets the shadow pane in `SHADOW` and the agent pane in
  `PREVIEW` (spy on `TmuxMonitor.forward_key`).
- **Negative control** — adding the zone leaves the shadow out of `_snapshots`,
  out of the rendered pane list, and out of kill / next-sibling targeting.
- **Narrow-fallback boundary** — mounted pilot at `W` = threshold−1 / threshold
  / threshold+1, asserting `#shadow-col.display` flips at exactly the intended
  column and the agent column's laid-out width never drops below
  `SHADOW_MIN_AGENT_COLS`. **Derive `W` from the measured chrome** rather than
  hardcoding it — that is what proves the decision is not being made on the raw
  screen width (a test with a hardcoded `W` passes under either implementation).
- **`t` targets the active column, independently for each** — focus the agent
  preview, return to the pane list, press `t`: the agent column's scroll state
  resets and the shadow column's anchor is **untouched**; then focus the shadow
  column and repeat for the reverse. Assert on both `_preview_scroll_state` and
  `_shadow_scroll_state` **and** on which fast refresh was scheduled, so a
  helper that tails "both" or the wrong one fails. Plus the reset cases: no
  shadow bound, and after the shadow disappears.
- **Zone invalidation while focused** — absent 1 tick holds the zone and renders
  the placeholder; absent for `SHADOW_ABSENT_GRACE_TICKS` falls back to
  `PREVIEW`; unbound entirely falls back immediately; and a key pressed while
  `SHADOW` is focused-but-absent produces **zero** `forward_key` calls, asserted
  against the agent pane id specifically (a plain "not called" assertion would
  also pass if forwarding were simply broken).

```bash
bash tests/run_all_python_tests.sh
bash tests/test_no_raw_tmux.sh
```

Manual, **from a shell outside the main aitasks tmux session** (see the
"Tmux-stress tasks" section of `aidocs/framework/tui_conventions.md`): spawn a
shadow from minimonitor, open `ait monitor`, `Tab` into the shadow column,
confirm the content renders unwrapped at the real pane width, that the active
column is visually obvious, and that typing lands in the shadow and not the
agent.

## Notes for sibling tasks

- `_current_shadow_pane_id()` is the resolution helper t1216_3 and t1216_4
  should reuse for "the selected agent's shadow".
- The `SHADOW_ABSENT_GRACE_TICKS` counter lives on the full-refresh path;
  t1216_3's per-tick signature scan runs there too, so both read the same
  `get_shadow_snapshot` result — resolve it once per agent per tick.
