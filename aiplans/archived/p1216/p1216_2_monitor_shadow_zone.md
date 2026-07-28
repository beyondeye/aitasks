---
Task: t1216_2_monitor_shadow_zone.md
Parent Task: aitasks/t1216_monitor_shadow_pane_view_and_concern_picker.md
Sibling Tasks: aitasks/t1216/t1216_3_monitor_concern_picker.md, aitasks/t1216/t1216_4_monitor_shadow_spawn.md
Archived Sibling Plans: aiplans/archived/p1216/p1216_1_shared_shadow_seam.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-07-28 15:30
---

# p1216_2 — `SHADOW` zone: side-by-side shadow preview + key targeting

Depends on **t1216_1** (landed, `466d6d9c0`): `TmuxMonitor.refresh_shadow_snapshot`,
`get_shadow_snapshot`, `find_shadow_pane`, `compute_shadow_staleness`.

## Context

`ait monitor` is the best TUI for switching between sessions, but it is not
shadow-aware: it draws only the one-glyph `◆` status indicator landed by t1133,
so a shadow-heavy workflow must abandon multi-session switching and fall back to
`ait minimonitor`. This child delivers the parent's first two acceptance
criteria — **view** a selected agent's shadow pane live, and **direct
keystrokes** at either the agent or its shadow with an unambiguous visible
indication of the current target.

Shape (decided with the user in the parent plan): a third zone `SHADOW`,
rendered as a **horizontal split** of the existing preview area — agent left,
shadow right — with the shadow column sized to the **real shadow pane's width**
so its content renders unwrapped. Focused zone = key target, which makes the
targeting indication free: the active zone already draws a `zone-active` border
and a `LIVE` badge.

## Plan verification (2026-07-28)

Re-verified against current `main` (HEAD `6164fbe0b`). `monitor_app.py` is
**2070 lines**, last touched 2026-07-24 by `1596a078a` (t1240); it is **clean**
in the working tree. Most anchors held exactly. Corrections folded in below.

**Anchor drift (corrected throughout this plan):**

| Claim | Was | Actually |
|---|---|---|
| inline `CSS` class attr | L316-389 | **L317-389** |
| `preview.styles.min_width = snap.pane.width` | L1240 | **L1245** |
| `run_worker(... group="preview")` | L1259-1262 | **L1255-1261** |
| `_record_preview_scroll` | L651-684 | **L651-682** |
| `_apply_preview_render` | L1268-1339 | **L1268-1337** |
| `_format_agent_card_text` | L1019 | **L1022** |
| `_parse_list_panes` (monitor_core) | L1185 | **L1389**; shadow branch **1414-1431**, `width = int(parts[6])` at **1411** |
| `_make_monitor` (test fixture) | L78-110 | **L81-112**, and it is a module-level *helper function*, not a pytest fixture |
| `os.environ.pop("TMUX"…)` (test) | L33-35 | **L33-34** |

Exact and unchanged: `Zone`/`ZONE_ORDER` L80-85, `PREVIEW_SIZES` L97-104,
`PreviewPanel`/`PreviewScrollContainer` L128-178, `#content-header` CSS L367-372,
`BINDINGS` L391-410 (`c`/`e`/`E` free; `t`/`z`/`tab` taken), `compose()` L474-486,
scroll hook L616-620, `_locate_anchor` L633-649, `_refresh_data` L702-781 (prune
L733-744), `_fast_preview_refresh` L783-807, `_update_content_preview` L1171-1266
(gen bump L1188-1189), `_switch_zone` L1341-1348, `_focus_first_in_zone`
L1350-1368, `_update_zone_indicators` L1370-1386, `check_action` L1417-1421,
`_manage_preview_timer` L1429-1435, `on_key` L1457-1501 (PREVIEW catch-all
L1486), `_forward_key_to_tmux` L1503-1513, `on_descendant_focus` L1517-1527,
`_get_focused_pane_id` L1529-1534, `action_cycle_preview_size` L1558,
`_apply_preview_size` L1563-1591, `action_scroll_preview_tail` L1593-1604,
`on_resize` L1606-1610.

**Ten substantive corrections** found by verifying the plan against source
(7-9 were raised in review and confirmed against the file):

1. **`Horizontal` / `Vertical` are not imported.** L57 imports only
   `Container, ScrollableContainer, VerticalScroll`. The Step 3 `compose()`
   rewrite needs both added, or it is an immediate `NameError`.
2. **`#content-header` is a bare top-level ID selector** (L367-372), *not*
   scoped under `#content-section`. The prior plan's "re-scope it to
   `#agent-col`" rests on a false premise: `dock: bottom` docks to whatever the
   widget's parent is, so simply moving it inside `#agent-col` in `compose()`
   re-docks it with **no CSS change**. Only the new `#shadow-header` needs a rule.
3. **There is no `_start_monitoring` method.** The `scroll.on_user_scroll` hook
   at L616-620 lives inside `on_mount` (L488-~625). Wire `#shadow-scroll`'s hook
   there.
4. **`on_descendant_focus` disambiguation (trap).** It branches on
   `isinstance(widget, PreviewPanel)` — and `#shadow-preview` will *also* be a
   `PreviewPanel`, so focusing the shadow column would silently set
   `Zone.PREVIEW`. Must branch on `widget.id`. Own test.
5. **`on_resize` currently does nothing on the default preset.** L1606-1610 only
   calls `_apply_preview_size()` when the active spec is a dynamic `"agents:N"`
   string; presets S/M/L (default is `M`, idx 1) fall through. The narrow-fit
   re-evaluation must therefore be called **unconditionally** in `on_resize`, not
   tucked inside that `if` — otherwise resizing the terminal on the default
   preset never re-decides the split.
6. **`_forward_key_to_tmux` also schedules the refresh.** L1512 does
   `self.call_later(self._fast_preview_refresh)`. Adding a `target_pane_id`
   parameter is not enough — the *scheduled refresh* must match the targeted
   column, or typing into the shadow re-captures the agent.
7. **`_restore_focus` steals focus out of `SHADOW` every 3 s (high).**
   `_restore_focus` (L897-936) early-returns **only** for `zone == Zone.PREVIEW`
   (L901-909). Every other zone falls through to the PaneCard restoration path
   (L913-925), which calls `card.focus()` and rewrites `_focused_pane_id` — and
   `card.focus()` fires `on_descendant_focus` → `Zone.PANE_LIST`. Since
   `_refresh_data` saves the zone at L707 and calls `_restore_focus` at L779-781
   on **every** full refresh, a user typing into the shadow would be ejected to
   the pane list once per 3 s tick. Needs its own `SHADOW` branch (Step 6b).
8. **Nothing renders the shadow column on the full-refresh path (medium).**
   `_refresh_data` calls `self._update_content_preview()` (L776) and
   `_restore_focus` calls it twice more (L907, L932), but there is no
   `_update_shadow_preview()` anywhere on that path. The 0.3 s fast tick only
   runs **while `SHADOW` is focused**, so a visible shadow column would sit
   stale — or still showing the *previous* agent's shadow — for as long as the
   user stays in `PANE_LIST`. Shadow-column visibility/width also has no defined
   recompute point on this path. Both fixed by the ordering in Step 6a.
9. **The 0.3 s timer never rebinds its callback (medium).**
   `_manage_preview_timer` (L1429-1435) creates the interval **once**
   (`set_interval(0.3, self._fast_preview_refresh)`, L1432) and guards on
   `self._preview_timer is None`. Naively widening the guard to
   `in (Zone.PREVIEW, Zone.SHADOW)` means a `PREVIEW → SHADOW` transition takes
   *neither* branch — the live timer stays bound to `_fast_preview_refresh` and
   the shadow column never fast-refreshes. Fixed by a dispatcher (Step 7).
10. **`refresh_shadow_snapshot` never creates an entry.** Verified against
   monitor_core.py:1763 (`prev is None → return None`). The 0.3 s fast tick can
   only refresh a key the 3 s full refresh already established. This is correct
   and load-bearing, but means the fast tick can never bootstrap or resurrect —
   stated explicitly so nobody "fixes" it later.

**Design gap resolved with the user.** The prior Step 2 table asked to
distinguish *"snapshot absent but shadow still bound"* (hold) from *"no bound
shadow at all"* (leave immediately). Those are **not distinguishable** from
`_shadow_snapshots`: `commit_snapshots` produces no entry both when the shadow
died and when its capture blipped, and
`test_monitor_shadow_status.py::LifecycleTests::test_transient_capture_failure_hides_icon_for_the_tick`
(L295-308) pins exactly that. Resolution chosen: **event-based, no tmux probe**
(Step 2 below) — zero extra tmux traffic, and the undecidable third rule is
dropped rather than papered over.

**Concurrency note.** A concurrent session (t1274) holds uncommitted edits to
`concern_parser.py`, `minimonitor_app.py`, `monitor_shared.py` and three test
files. This task's file set — `monitor_app.py`, the two `tuis/monitor/` doc
pages, one new test file — has **zero overlap**, so the Step 8 commit can stage
its paths directly without hunk extraction.

---

## Step 1 — the zone

`monitor_app.py:80-85`:

```python
class Zone(Enum):
    PANE_LIST = "pane_list"
    PREVIEW = "preview"
    SHADOW = "shadow"

ZONE_ORDER = [Zone.PANE_LIST, Zone.PREVIEW, Zone.SHADOW]
```

- **L57 import:** add `Horizontal, Vertical` to
  `from textual.containers import Container, ScrollableContainer, VerticalScroll`.
- `_switch_zone` (L1341-1348) currently does
  `(idx + direction) % len(ZONE_ORDER)`. Make it **loop** (not single-step) past
  `Zone.SHADOW` when the selected agent has no bound shadow *or* the split is
  hidden by the narrow fallback, so `Tab` behaves exactly as today for
  non-shadowed agents and a skip can never land on an invalid zone.
- `_focus_first_in_zone` (L1350-1368) gains a `SHADOW` branch focusing
  `#shadow-preview` (same `try/except` shape as the `PREVIEW` branch).
- `_update_zone_indicators` (L1370-1386) adds `("#shadow-col", Zone.SHADOW)` to
  its list, and must **also call `self._update_shadow_preview()`** alongside the
  existing `_update_content_preview()` at L1382 so the shadow header's
  `LIVE` badge tracks the active zone. It already calls `refresh_bindings()`
  (L1384), which is what actually relabels the footer — `check_action` alone
  never does.
- `check_action` (L1417-1421) must treat `SHADOW` like `PREVIEW`:

```python
if self._active_zone in (Zone.PREVIEW, Zone.SHADOW):
    return action == "switch_zone"
return action != "switch_zone"
```

- `on_descendant_focus` (L1517-1527) — **branch on id, not type** (correction 4):

```python
elif isinstance(widget, PreviewPanel):
    self._active_zone = (
        Zone.SHADOW if widget.id == "shadow-preview" else Zone.PREVIEW
    )
    self._active_preview_zone = self._active_zone      # Step 5
    self._manage_preview_timer()
    self._update_zone_indicators()
```

## Step 2 — leaving an already-active invalid zone

Two causes make the shadow snapshot vanish and they are **indistinguishable**
from `_shadow_snapshots` (see Plan verification): the shadow pane died, or a
single-tick capture failed. Yanking the user out on a one-tick blip would be its
own bug, so the exit is decided by **event**, never by probing tmux:

| Event | Behaviour |
|---|---|
| Pane-list selection moves to an agent whose `get_shadow_snapshot(...)` is `None` | **Leave `SHADOW` immediately**, restore focus to `PREVIEW`, reset `_active_preview_zone`. Unambiguous — we never had a snapshot for that agent. |
| Same agent, snapshot absent on a **full** refresh | **Hold** the zone; render `[dim](shadow unavailable)[/]` |
| Same agent, absent for `SHADOW_ABSENT_GRACE_TICKS = 2` consecutive **full** refreshes | Fall back to `Zone.PREVIEW`, restore focus, `notify()` **once** |
| Snapshot returns while holding | Reset the grace counter to 0 |

**While the shadow is absent, keystrokes in `SHADOW` are dropped, never
forwarded.** They must not fall through to the agent pane — that would type a
user's shadow input into a working agent. Safety property, own test.

Count the grace ticks in `_refresh_data` (the 3 s full tick, L702-781), **not**
in the 0.3 s fast tick, so the window is a wall-clock ~6 s rather than 0.6 s.
The counter is a single `self._shadow_absent_ticks: int`; it is reset to 0
whenever a snapshot is present or the selection changes.

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
`#content-header` ids** — `_update_content_preview` (L1172-1174),
`_apply_preview_size` (L1578-1579), `action_scroll_preview_tail` (L1595) and the
CSS all query them by id. `#content-header`'s existing `dock: bottom` rule
(L367-372) needs **no change**: moving the widget inside `#agent-col` re-docks it
to that parent automatically (correction 2).

CSS additions to the inline `CSS` attr (**L317-389**; there are no `.tcss` files
anywhere under `.aitask-scripts/`):

```css
#preview-row  { height: 1fr; }
#agent-col    { width: 1fr; }
#shadow-col   { width: auto; display: none; border-left: solid $primary-darken-2; }
#shadow-col.zone-active { border-left: solid $warning; }
#shadow-scroll { height: 1fr; scrollbar-gutter: stable; }
#shadow-header { dock: bottom; height: 1; }
```

Leave `#content-section { max-height: 24 }` and `#preview-scroll
{ max-height: 22 }` alone: the split is **horizontal**, so `PREVIEW_SIZES`
(L97-104) and `_apply_preview_size` (which sets only `max_height` on
`#content-section` and `#preview-scroll`) keep working. Add `#shadow-scroll` to
the `max_height` assignment at L1579 so both columns resize together.

**Width.** `#shadow-col` is shown only when a shadow is bound and the split
fits, and then:

```python
w = shadow_snap.pane.width
shadow_col.styles.width = w + 1          # +1 for the stable scrollbar gutter
shadow_preview.styles.min_width = w
```

mirroring what the agent preview does at **L1245**. `TmuxPaneInfo.width` is a
real field (monitor_core.py:530) populated for shadow panes —
`_parse_list_panes` parses `width = int(parts[6])` at L1411, *before* the shadow
branch at L1414-1431.

## Step 4 — narrow fallback

Decide on the **mounted row's usable content width**, not `self.size.width`.
`self.size.width` is the screen width and ignores `#content-section`'s border,
`scrollbar-gutter: stable`, padding, and the shadow column's own gutter; at the
boundary that error is several columns and would leave the agent column too
narrow or overflowing.

```python
SHADOW_MIN_AGENT_COLS = 40

def _shadow_split_fits(self, shadow_width: int) -> bool:
    try:
        row = self.query_one("#preview-row")
    except Exception:
        return False                      # not mounted yet — no split
    avail = row.content_region.width      # post-layout, chrome already excluded
    return (avail - (shadow_width + 1)) >= SHADOW_MIN_AGENT_COLS
```

When it does not fit, do **not** split: render only the focused zone's column
full-width (`display` toggled on the other), and reset `_active_preview_zone` to
`Zone.PREVIEW` (Step 5).

Evaluate on mount, in `on_resize`, and after `_apply_preview_size` (L1563), each
via `call_after_refresh` so the measurement happens **post-layout** —
`content_region` is meaningless before the first layout pass.

**`on_resize` must call it unconditionally** (correction 5). Today L1606-1610 is:

```python
def on_resize(self, event) -> None:
    section_spec, _, _ = PREVIEW_SIZES[self._preview_size_idx]
    if isinstance(section_spec, str) and section_spec.startswith("agents:"):
        self._apply_preview_size()
```

The shadow-fit re-evaluation goes **outside** that `if` — otherwise, on the
default `M` preset, narrowing the terminal never re-decides the split.

## Step 5 — `t` (Tail) must follow the active column

`action_scroll_preview_tail` (L1593-1604) is hard-wired to `#preview-scroll`,
`_preview_scroll_state[self._focused_pane_id]` and `_fast_preview_refresh`; left
alone it would silently tail the agent preview while the user looks at the
shadow.

The constraint that fixes its meaning: `check_action` (L1417) disables every
non-`switch_zone` binding while a preview zone is focused (keys there are
forwarded to tmux), so **`t` is only ever pressable from `PANE_LIST`** — "the
active column" cannot mean "the currently focused zone".

Define it as the **last-focused preview column**:

- `self._active_preview_zone: Zone = Zone.PREVIEW`, updated by `_switch_zone`
  and `on_descendant_focus` whenever focus lands on `PREVIEW` or `SHADOW`.
- **Reset to `Zone.PREVIEW`** whenever the shadow column is hidden by the narrow
  fallback, the shadow is absent past its grace, or the selection moves to an
  agent with no shadow.
- `t` resets that column's scroll state to `(True, None)`, calls `scroll_end` on
  that column's scroller, and schedules the matching fast refresh
  (`_fast_preview_refresh` or `_fast_shadow_refresh`). Note the agent column
  keys `_preview_scroll_state` by `_focused_pane_id` (the **agent** pane id)
  while the shadow column keys `_shadow_scroll_state` by the **shadow** pane id.

`z` (`action_cycle_preview_size`, L1558) needs no such treatment — the split is
horizontal, so the height presets apply to both columns unchanged.

## Step 6 — rendering

`_update_shadow_preview` mirrors `_update_content_preview` (L1171-1266) with a
**separate** `_shadow_render_gen` counter, bumped on **every** entry including
the no-shadow / frozen / empty branches — the agent version does this at
L1188-1189 precisely so a slow in-flight render can never clobber a newer state.
Plus:

- header text on `#shadow-header`: the shadow pane id and its followed agent,
  with `[bold green]LIVE[/]` when `_active_zone is Zone.SHADOW`,
  `[bold yellow]PAUSED[/]` when its scroll state says paused, else nothing;
- the frozen branch (`same_pane and (is_paused or scroll.user_is_scrolling)`),
  mirroring L1230-1232;
- `_shadow_scroll_state: dict[str, tuple[bool, str | None]]` keyed by **shadow**
  pane id, pruned alongside `_preview_scroll_state` in `_refresh_data`
  (L733-744);
- `run_worker(..., exclusive=True, group="shadow-preview")` — a **different**
  group from the agent preview's `group="preview"` (L1255-1261), or the two
  columns would cancel each other's renders.

**Reuse, do not clone:** `_locate_anchor` (L633-649, a `@staticmethod`) works as
is; parameterise `_record_preview_scroll` (L651-682) and `_apply_preview_render`
(L1268-1337) on which scroller / state-map / render-gen they act for, and wire
`scroll.on_user_scroll` for `#shadow-scroll` in **`on_mount`** next to the
existing hook at L616-620 (correction 3).

## Step 6a — the full-refresh path (`_refresh_data`)

The shadow column is visible whenever a shadow is bound and the split fits —
including while focus is in `PANE_LIST` — but the 0.3 s tick only runs while
`SHADOW` is focused. So the 3 s full refresh **must** own shadow rendering,
visibility and the Step 2 state machine. Add a single
`_reconcile_shadow_state()` to `_refresh_data`, called **after**
`self._snapshots = snaps` (L717) and the existing scroll-state prune (L733-744),
and **before** the `call_after_refresh(self._restore_focus, ...)` at L779.

Fixed order (each step depends on the previous):

1. **Resolve once.** `shadow_snap = self._monitor.get_shadow_snapshot(self._focused_pane_id)`
   — one lookup per tick, reused by every step below and by t1216_3's signature
   scan (see Notes for sibling tasks).
2. **Grace counter (Step 2).** Present → `_shadow_absent_ticks = 0`. Absent →
   increment.
3. **Zone fallback.** If the selection moved to an agent with no shadow, or
   `_shadow_absent_ticks >= SHADOW_ABSENT_GRACE_TICKS`, set
   `_active_zone = Zone.PREVIEW`, reset `_active_preview_zone`, and `notify()`
   once.
4. **Re-derive the local `saved_zone`.** `saved_zone` was captured at L707,
   *before* step 3 could change it. If it is still handed to `_restore_focus`
   unchanged, the deferred restore re-focuses `#shadow-preview` and **undoes the
   fallback that just fired**. So `_reconcile_shadow_state()` returns the
   (possibly changed) zone and `_refresh_data` rebinds `saved_zone` to it before
   the `call_after_refresh`. This coupling is the whole reason the reconcile
   runs before L779 rather than after.
5. **Visibility + width (Steps 3/4).** Toggle `#shadow-col.display` and set its
   width from `shadow_snap.pane.width`; schedule `_shadow_split_fits` via
   `call_after_refresh` so the measurement is post-layout.
6. **Prune `_shadow_scroll_state`** for shadow pane ids no longer present,
   mirroring the `_preview_scroll_state` prune at L733-744.

Then, next to the existing `self._update_content_preview()` at L776, add
`self._update_shadow_preview()`.

## Step 6b — focus restoration (`_restore_focus`)

`_restore_focus` (L897-936) early-returns only for `Zone.PREVIEW`. Add a
`SHADOW` branch **beside** it — before the fall-through PaneCard path, which
would otherwise call `card.focus()` and eject the user to the pane list on every
full refresh (correction 7):

```python
if zone == Zone.SHADOW:
    try:
        self.query_one("#shadow-preview", PreviewPanel).focus()
    except Exception:
        pass
    self._update_content_preview()
    self._update_shadow_preview()
    if pane_list_rebuilt:
        self._update_selected_card_indicator(full=True)
    return
```

Also add `self._update_shadow_preview()` next to the existing
`_update_content_preview()` in the `PREVIEW` branch (L907) and on the
fall-through path (L932), so the shadow column tracks the **final** settled
`_focused_pane_id` — which `_restore_focus` may itself have changed at L917/L925.

## Step 7 — the fast tick

`_manage_preview_timer` (L1429-1435) creates the interval **once** and guards on
`self._preview_timer is None`. Simply widening the guard is a bug (correction 9):
on `PREVIEW → SHADOW` the timer is non-`None` and the zone is still in the
allowed set, so **neither** branch runs and the live interval stays bound to
`_fast_preview_refresh` — the shadow column would never fast-refresh.

Fix with a **dispatcher** rather than stop/recreate: one interval whose callback
reads `_active_zone` live, so a zone change needs no timer churn and there is no
stop/recreate window:

```python
async def _fast_zone_refresh(self) -> None:
    """Dispatch the 0.3s tick to the column the active zone owns."""
    if self._active_zone == Zone.SHADOW:
        await self._fast_shadow_refresh()
    elif self._active_zone == Zone.PREVIEW:
        await self._fast_preview_refresh()

def _manage_preview_timer(self) -> None:
    active = self._active_zone in (Zone.PREVIEW, Zone.SHADOW)
    if active and self._preview_timer is None:
        self._preview_timer = self.set_interval(0.3, self._fast_zone_refresh)
    elif not active and self._preview_timer is not None:
        self._preview_timer.stop()
        self._preview_timer = None
```

The dispatcher governs **only** the interval. The one-shot `call_later(...)`
schedules in `action_scroll_preview_tail` (Step 5) and `_forward_key_to_tmux`
(Step 8) must keep calling `_fast_preview_refresh` / `_fast_shadow_refresh`
**directly** — `t` is pressed from `PANE_LIST`, where the dispatcher would
correctly refresh nothing.

The shadow leg of the dispatch is `_fast_shadow_refresh`:

```python
async def _fast_shadow_refresh(self) -> None:
    pane_id = self._focused_pane_id          # pin before the await
    if not pane_id or not self._monitor:
        return
    snap = await self._monitor.refresh_shadow_snapshot(pane_id)
    if snap is None:
        return                                # no update this tick
    if pane_id == self._focused_pane_id:
        self._update_shadow_preview()
```

`refresh_shadow_snapshot` returns `None` for **four** reasons — key absent
(it never creates one), capture failed, stale write seq, or the shadow was
rebound to a different pane. All four mean **"no update this tick"**, never
"shadow gone": the 3 s full refresh owns deletion, and Step 2's grace counter is
driven from `_refresh_data`, not from here. The fast tick therefore cannot
bootstrap a shadow the full refresh has not yet seen (correction 7).

Because the timer only runs while `SHADOW` is focused, users with no shadows pay
nothing per tick.

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

`_forward_key_to_tmux` (L1503-1513) gains an optional `target_pane_id`
defaulting to `self._focused_pane_id`, **and must schedule the refresh matching
that target** (correction 6) — today it unconditionally does
`self.call_later(self._fast_preview_refresh)` at L1512:

```python
def _forward_key_to_tmux(self, event, target_pane_id: str | None = None) -> None:
    target = target_pane_id or self._focused_pane_id
    if self._monitor.forward_key(target, event.key, event.character):
        self.call_later(
            self._fast_shadow_refresh if target_pane_id
            else self._fast_preview_refresh
        )
```

`_current_shadow_pane_id()` resolves `self._focused_pane_id` →
`self._monitor.get_shadow_snapshot(...)` → `.pane.pane_id`. Use
`self._focused_pane_id` — **never** `_get_focused_pane_id()` (L1529-1534), which
reads `self.focused` and returns `None` whenever focus is off a `PaneCard`, i.e.
always in this branch.

The `event.stop()` is unconditional (as in the PREVIEW branch): when the shadow
is absent the key is **swallowed**, which is exactly the required
drop-never-forward behaviour.

## Step 9 — docs

- `website/content/docs/tuis/monitor/_index.md` — L40 says "four stacked areas"
  and then lists **five** (L42-46): fix the count and add the shadow column.
  L60-69 "Navigating the Monitor" hard-codes two zones ("focus lives in either
  the pane list zone or the preview zone, and `Tab` cycles between them") —
  extend to the third zone and say what `Tab` does when no shadow is bound.
- `website/content/docs/tuis/monitor/reference.md` — L61 says "Monitor uses a
  two-zone model"; the zone table is L63-66 and L68 describes `Tab`. Add the
  `SHADOW` row. The earlier "Zone Navigation" table at L12-20 (L16: "pane list ↔
  preview") needs the same update, and L44's `t` entry must say it targets the
  last-focused preview column.

## Step 10 — coordination edge for t1288

`t1288` (`shadow_refresh_concurrency_soak`) was created as a t1216_1 "after"
mitigation with `depends: []`, but its own description states the soak only
becomes meaningful once a production consumer wires the 0.3 s fast tick — which
is **this** task. During Step 8, wire the edge and its reverse pointer:

```bash
./.aitask-scripts/aitask_update.sh --batch 1288 --deps 1216_2
```

The flag is `--deps` (verified — there is no `--depends`), and it **replaces**
the whole list. That is safe here only because t1288 currently has
`depends: []`; re-read its frontmatter before running and include any existing
ids if that has changed.

and add a `## Coordination` note to `aitasks/t1288_shadow_refresh_concurrency_soak.md`
naming t1216_2 as the consumer, committed with `./ait git`. This is a
task-metadata edit, not a code change — keep it out of the `(t1216_2)` code
commit.

## Verification

New `tests/test_monitor_shadow_zone.py`. It must do its own
`sys.path.insert(0, REPO_ROOT / ".aitask-scripts")` — `run_all_python_tests.sh`
seeds `PYTHONPATH` with only `board` and `lib`. Replicate the module-level
`os.environ.pop("TMUX"/"TMUX_PANE", None)` at **L33-34** of
`test_monitor_shadow_status.py` so `MonitorApp.on_mount` takes the deterministic
not-in-tmux path. Follow that file's `_make_monitor` **module-level helper**
(**L81-112**: real `TmuxMonitor`, scripted `discover_panes_with_shadows_async` /
`capture_pane_content_async`, `_run_offloaded` replaced by `_sync_offloaded` at
L76-78 — no tmux, no sleeps) and its `MountedCardRenderTests` pilot idiom
(L490-507: `app = MonitorApp(session="demo", project_root=REPO_ROOT)` then
`async with app.run_test(size=(100, 30)) as pilot`). Post-t1240 the constructor
defaults `rename_window=False`, so a mounted test can never rename a live window.

- Zone skipping with and without a bound shadow; `ZONE_ORDER` cycling in **both**
  directions; skip also when the narrow fallback hides the column.
- **`on_descendant_focus` id disambiguation** — focusing `#shadow-preview` sets
  `Zone.SHADOW`, focusing `#content-preview` sets `Zone.PREVIEW`. A test that
  would pass under the naive `isinstance`-only branch is not sufficient: assert
  the shadow case explicitly.
- Shadow column width derived from `pane.width`; `#shadow-col` hidden when no
  shadow is bound.
- Key forwarding targets the shadow pane in `SHADOW` and the agent pane in
  `PREVIEW` — spy on `TmuxMonitor.forward_key` (it is a **method** on the
  monitor, monitor_core.py:2186, signature
  `forward_key(pane_id, key, character=None) -> bool`) — **and** assert which
  fast refresh was scheduled, so correction 6 is pinned.
- **Negative control** — adding the zone leaves the shadow out of `_snapshots`,
  out of the rendered pane list, and out of kill / next-sibling targeting.
- **Narrow-fallback boundary** — mounted pilot at `W` = threshold−1 / threshold
  / threshold+1, asserting `#shadow-col.display` flips at exactly the intended
  column and the agent column's laid-out width never drops below
  `SHADOW_MIN_AGENT_COLS`. **Derive `W` from the measured live chrome**
  (`#preview-row`'s `content_region.width` at a known screen width) rather than
  hardcoding — a hardcoded `W` passes under either implementation and so proves
  nothing about *which* width the decision reads.
- **`on_resize` re-evaluates on the default preset** — the discriminating test
  for correction 5: with `_preview_size_idx` on a fixed preset (`M`), resize the
  pilot across the threshold and assert `#shadow-col.display` flipped. Under the
  current `agents:`-only guard this fails.
- **`t` targets the active column, independently for each** — focus the agent
  preview, return to the pane list, press `t`: the agent column's scroll state
  resets and the shadow column's anchor is **untouched**; then focus the shadow
  column and repeat for the reverse. Assert on both `_preview_scroll_state` and
  `_shadow_scroll_state` **and** on which fast refresh was scheduled, so a helper
  that tails "both" or the wrong one fails. Plus the reset cases: no shadow
  bound, shadow disappeared, and narrow fallback active.
- **Zone invalidation while focused** (Step 2's event model, one test per row) —
  selection moves to a shadow-less agent → leaves `SHADOW` **immediately**;
  absent 1 full tick on the same agent → holds the zone and renders the
  placeholder; absent for `SHADOW_ABSENT_GRACE_TICKS` → falls back to `PREVIEW`
  and notifies **once**; a snapshot returning mid-grace resets the counter; and a
  key pressed while `SHADOW` is focused-but-absent produces **zero**
  `forward_key` calls, asserted **against the agent pane id specifically** (a
  bare "not called" assertion would also pass if forwarding were simply broken).
- **Focus survives a full refresh (correction 7)** — mounted pilot: enter
  `SHADOW`, run a complete `_refresh_data` cycle, assert `self.focused` is still
  `#shadow-preview` and `_active_zone is Zone.SHADOW`. Under the current
  PREVIEW-only `_restore_focus` this fails (focus lands on a `PaneCard`), which
  is what makes the test discriminating.
- **The grace fallback is not undone by the deferred restore** — force the
  Step 2 fallback to fire *during* a refresh and assert focus ends in `PREVIEW`,
  not back in `SHADOW`. This is the `saved_zone` rebind in Step 6a step 4; a
  version that leaves `saved_zone` at its L707 value fails here.
- **Shadow column tracks the selection on the full-refresh path (correction 8)**
  — mounted selection-change test with focus never leaving `PANE_LIST`: with
  agents A (shadow `%9`) and B (shadow `%12`), move the selection A → B, run a
  full refresh, and assert `#shadow-preview` renders **B's** shadow content
  (`render().plain`), not A's. Then move to an agent with no shadow and assert
  `#shadow-col.display` is off. Both fail if `_update_shadow_preview` is only
  reachable from the focused fast tick.
- **Timer handoff in both directions (correction 9)** — spy on which coroutine
  the interval actually invokes. `PANE_LIST → PREVIEW` runs
  `_fast_preview_refresh`; `PREVIEW → SHADOW` (without leaving via `PANE_LIST`)
  runs `_fast_shadow_refresh`; `SHADOW → PREVIEW` runs `_fast_preview_refresh`
  again; leaving to `PANE_LIST` stops the timer. **Negative control:** the naive
  `if active and self._preview_timer is None` widening must fail the
  `PREVIEW → SHADOW` leg — assert it does, so the test is shown to discriminate
  the dispatcher rather than merely pass.
- **Render-level assertions** use `widget.render().plain` per the repo's TUI
  convention, not internal state alone.

**Prove the harness can fail.** Before relying on the new file, invert each
guard in turn — the id disambiguation, the `on_resize` unconditional call, the
grace counter, the drop-never-forward branch, the `_restore_focus` SHADOW
branch, the `saved_zone` rebind, the full-refresh `_update_shadow_preview` call,
and the timer dispatcher — and confirm the suite exits non-zero. A passing test pins nothing until its failure path is demonstrated;
and a negative control that *passes* means some other guard did the rejecting.

```bash
bash tests/run_all_python_tests.sh
bash tests/test_no_raw_tmux.sh
```

(`tests/` is not scanned by `test_no_raw_tmux.sh`, and `monitor_app.py` is
already allowlisted there at L53 — so neither the new test nor the edits can
trip it. Run it anyway as the regression net.)

Manual, **from a shell outside the main aitasks tmux session** (see "Tmux-stress
tasks", `aidocs/framework/tui_conventions.md:442-467`): spawn a shadow from
minimonitor, open `ait monitor`, `Tab` into the shadow column, confirm the
content renders unwrapped at the real pane width, that the active column is
visually obvious, and that typing lands in the shadow and not the agent.

## Notes for sibling tasks

- `_current_shadow_pane_id()` is the resolution helper t1216_3 and t1216_4
  should reuse for "the selected agent's shadow".
- The `SHADOW_ABSENT_GRACE_TICKS` counter lives on the full-refresh path;
  t1216_3's per-tick signature scan runs there too, so both read the same
  `get_shadow_snapshot` result — resolve it **once per agent per tick**.
- `refresh_shadow_snapshot` cannot bootstrap a key. Any sibling adding a
  shadow read path must let the 3 s full refresh establish existence first.
- `_forward_key_to_tmux` now takes `target_pane_id`; t1216_4 should reuse it
  rather than adding a parallel forwarder.

## Risk

### Code-health risk: medium
- The zone model, `on_key` and `check_action` are load-bearing for **all**
  monitor interaction; a mistake in the `SHADOW` branch can swallow or misroute
  every keystroke, and the failure is silent (keys just stop working) ·
  severity: high · → mitigation: the key-routing tests plus the
  drop-never-forward test asserted against the agent pane id specifically, and
  the `on_descendant_focus` id-disambiguation test
- **Adding a zone touches four pre-existing single-zone assumptions that are
  spread across the refresh cycle** — `_restore_focus`'s PREVIEW-only early
  return, `_refresh_data`'s single `_update_content_preview` call, the
  `saved_zone` captured before the zone can change, and the create-once preview
  timer. Review found three of these after the first plan draft looked complete,
  which is evidence the cycle has more of them than reading any single method
  reveals; each failure is silent and only visible in live use · severity: high
  · → mitigation: the four discriminating tests in Verification (focus survives
  a refresh, fallback not undone, selection tracked from `PANE_LIST`, timer
  handoff both ways), each paired with a negative control, plus t1216_5's live
  walkthrough
- `compose()` is restructured from a flat `Container` to a nested
  `Horizontal`/`Vertical` tree while four ids (`#content-section`,
  `#preview-scroll`, `#content-preview`, `#content-header`) must keep resolving
  for `_update_content_preview`, `_apply_preview_size`,
  `action_scroll_preview_tail` and the CSS · severity: medium · → mitigation:
  ids preserved by construction; the existing mounted-pilot render tests in
  `test_monitor_shadow_status.py` exercise the same DOM and must stay green
- `_update_shadow_preview` / `_apply_preview_render` parameterisation duplicates
  a subtle render-generation + scroll-anchor protocol; getting the second
  worker group or the gen bump wrong reintroduces the exact clobbering t1111_5
  fixed · severity: medium · → mitigation: distinct `group="shadow-preview"`,
  separate `_shadow_render_gen` bumped on every entry, and reuse (not cloning)
  of `_locate_anchor` / `_record_preview_scroll`
- Blast radius is one source file, two doc pages and one new test file, with
  zero overlap against the concurrent t1274 edits · severity: low · →
  mitigation: none needed

### Goal-achievement risk: medium
- The side-by-side layout is unproven at real terminal widths: a wide shadow
  column may leave the agent preview too narrow to be useful, and
  `SHADOW_MIN_AGENT_COLS = 40` is a guess. Rendering the split is not the same
  as it being *readable* · severity: medium · → mitigation: t1216_5 (aggregate
  manual verification) is the deciding surface; the boundary test derives its
  width from live chrome so the threshold can be retuned in one constant
- The Step 2 exit model deliberately cannot tell a dead shadow from a
  6-second-long capture failure, so a genuinely dead shadow holds the zone for
  ~6 s before falling back · severity: low · → mitigation: accepted and stated;
  the alternative (a tmux probe per absent tick) was rejected with the user as
  not worth the traffic
- Everything else (preview render, key forwarding, the t1216_1 seam) is reuse of
  code already proven in production · severity: low · → mitigation: none needed

**No new mitigation tasks** — reviewed with the user and declined: the
decomposition already carries the mitigating work. **t1216_5** is the aggregate
live manual verification that decides the layout question, and **t1288**
(`shadow_refresh_concurrency_soak`, created as a t1216_1 "after") covers the
concurrency soak. This mirrors the parent plan, which declined mitigation
follow-ups for the same reason.

## Post-Review Changes

### Change Request 1 (2026-07-28 16:30)

- **Requested by user:** Review of the implementation flagged, as *blocking*,
  that a terminal resize during the SHADOW absent-snapshot grace window
  bypasses the intended two-full-refresh hold.
  `_schedule_shadow_fit_check()` (monitor_app.py:2213) derived
  `width = None` whenever `get_shadow_snapshot()` was temporarily absent and
  queued `_apply_shadow_visibility(None)`. Unlike `_reconcile_shadow_state()`
  it did **not** reuse `_last_shadow_width`, so the queued callback hid
  `#shadow-col` and `_leave_shadow_zone()` ran immediately.

- **Verified:** CONFIRMED against the source. The width derivation existed in
  **two** places with different hold semantics — `_reconcile_shadow_state`
  had the fallback (added late, when the hold/visibility conflict was first
  found) and `_schedule_shadow_fit_check` did not. Since
  `PreviewRow.on_row_resize` is bound to the latter, any resize mid-hold
  collapsed the grace window. The duplication itself was the defect.

- **Changes made:** Extracted the single source of truth
  `_shadow_visibility_width()` — resolve the snapshot; if present, record and
  return `pane.width`; if absent **and** the SHADOW zone is active, return
  `_last_shadow_width` (holding); otherwise `None`. Both
  `_schedule_shadow_fit_check()` and `_reconcile_shadow_state()` now call it,
  and `_reconcile_shadow_state()` delegates its whole visibility scheduling to
  `_schedule_shadow_fit_check()` so the two paths can no longer diverge.

- **Test added:** `test_resize_during_the_grace_hold_does_not_collapse_it` —
  one absent full refresh (inside the grace window), then
  `pilot.resize_terminal` at a width where the split still fits; asserts the
  zone is still `SHADOW` and `#shadow-col` is still displayed. Negative
  control: removing the hold branch from `_shadow_visibility_width()` fails
  this test **and** `test_hold_keeps_focus_and_column_up_for_the_first_absent_tick`,
  proving both the new and the pre-existing hold path run through the helper.

- **Files affected:** `.aitask-scripts/monitor/monitor_app.py`,
  `tests/test_monitor_shadow_zone.py`.

## Final Implementation Notes

- **Actual work done:** All ten plan steps landed. `Zone.SHADOW` joins the enum
  and `ZONE_ORDER`; `compose()` splits `#content-section` into `#preview-row` >
  `#agent-col` / `#shadow-col` (all four pre-existing ids preserved);
  `_update_shadow_preview` / `_apply_shadow_render` mirror the agent renderer
  with their own `_shadow_render_gen` and a distinct `group="shadow-preview"`;
  `_fast_shadow_refresh` drives the 0.3s tick via a new `_fast_zone_refresh`
  dispatcher; `on_key` gains a SHADOW branch above the PREVIEW catch-all and
  `_forward_key_to_tmux` takes `target_pane_id` plus a matching refresh;
  `action_scroll_preview_tail` follows `_active_preview_zone`;
  `_reconcile_shadow_state` owns the grace/visibility state machine on the 3s
  tick. New `tests/test_monitor_shadow_zone.py` (39 tests). Docs updated in
  `tuis/monitor/_index.md` and `reference.md`.

- **Deviations from plan:** Five, all found while implementing and each with a
  negative control:
  1. **`on_mount` early-returns when `$TMUX` is unset**, so every preview hook
     the plan added was unreachable (and untestable). Extracted
     `_wire_preview_hooks()` and moved it ABOVE that guard — it is pure DOM
     wiring with no tmux dependency.
  2. **The App-level `on_resize` measures a stale row.** The plan called for an
     unconditional fit check there; verified that on a 120→70 resize the App
     handler still reads a 120-column `#preview-row`. Added a small
     `PreviewRow(Horizontal)` subclass whose OWN Resize drives the check
     (same hook pattern as `PreviewScrollContainer`), and the App handler
     deliberately does not.
  3. **The grace counter could never expire.** `_restore_focus` re-focuses the
     column each tick → `on_descendant_focus` → `_enter_shadow_zone()` → counter
     reset. Made entry idempotent per bound agent.
  4. **`on_descendant_focus` unbinding `_shadow_zone_agent_id`** made every
     re-entry look fresh (pane-list rebuilds fire card-focus events). The
     binding is now owned solely by `_enter_shadow_zone` / `_leave_shadow_zone`.
  5. **The visibility rule defeated the grace hold** — hiding the column on any
     absent snapshot collapsed the window to one tick. The column now stays up
     at `_last_shadow_width` while holding, and `_restore_focus` validates on
     the column being SHOWN rather than on a snapshot existing.

- **Issues encountered:**
  - Three negative controls initially **passed**, meaning those tests were not
    discriminating — another guard was doing the rejecting. Rewrote them to
    assert the actual mechanism (the `zone` argument handed to
    `_restore_focus`; the callback handed to `set_interval`) instead of an end
    state. Deviations 3-5 were found precisely because of that re-check.
  - `assertIs` on bound methods always fails (a new object per attribute
    access); compare `__func__` against the class attribute.
  - Mounted tests must drive selection by focusing the real `PaneCard`, not by
    assigning `_focused_pane_id` — the deferred `_restore_focus` reverts it.

- **Key decisions:**
  - One interval with a zone-reading **dispatcher** rather than stop/recreate on
    every zone change: no timer churn and no stop/recreate window.
  - The SHADOW exit is decided by **event, not by probing tmux**: a selection
    change onto a shadowless agent exits at once (unambiguous), while a
    same-agent absence uses the grace window, because "died" and "capture
    blipped" are genuinely indistinguishable from `_shadow_snapshots`.
  - `_shadow_visibility_width()` is the single source of truth for column
    visibility (see Post-Review Changes) — the two-place derivation it replaced
    was itself the defect the review found.

- **Upstream defects identified:** None.

- **Notes for sibling tasks:**
  - `_current_shadow_pane_id()` is the "selected agent's shadow" resolver
    t1216_3 / t1216_4 should reuse. It resolves from `_focused_pane_id`, never
    `_get_focused_pane_id()` (which is None whenever focus is off a PaneCard).
  - `_reconcile_shadow_state` resolves `get_shadow_snapshot` once per tick on
    the full-refresh path; t1216_3's per-tick signature scan belongs there and
    should reuse that single resolution rather than re-fetching per agent.
  - `_forward_key_to_tmux` now takes `target_pane_id` — reuse it rather than
    adding a parallel forwarder.
  - **Adding a fourth zone would hit the same class of bug.** Four
    pre-existing single-zone assumptions had to be fixed: `_restore_focus`'s
    zone-specific early return, `_refresh_data`'s single render call, a
    `saved_zone` captured before the zone can change, and a create-once timer.
    Audit those four sites first.
  - `refresh_shadow_snapshot` cannot bootstrap a key — the 3s full refresh must
    establish existence first.
