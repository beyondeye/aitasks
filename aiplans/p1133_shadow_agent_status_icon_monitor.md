---
Task: t1133_shadow_agent_status_icon_monitor.md
Base branch: main
plan_verified: []
---

# t1133 — Shadow-agent status icon in monitor/minimonitor

## Context

`ait monitor` and `ait minimonitor` classify each monitored code agent as
**active / idle / prompt** and render a colored dot `●` per agent row. A code
agent can have a **linked shadow agent** (spawned via minimonitor `e`), whose
pane carries the followed agent's pane id in the `@aitask_shadow_target` tmux
option. Today the shadow's own execution state is invisible: shadow panes are
deliberately dropped from monitor discovery (`monitor_core.py:1141`), so no
snapshot, no state, no display.

Goal: when an agent window has a linked shadow, render a **second colored
glyph `◆`** (magenta=prompt / yellow=idle / green=active — same mapping as the
agent dot) immediately after the agent's own dot, before the window name, in
both TUIs. Windows without a shadow are visually unchanged.

**Perf coordination (t1111):** shadow-state detection is per-tick capture +
regex work — exactly what t1111_4 moved off the UI thread. This feature must
ride the existing offloaded batch (`capture_all_classified_async` →
`commit_snapshots`, generation-guarded, invariants A–G in
`aiplans/p1111_monitor_ui_thread_offload_perf.md`), adding **no** synchronous
per-tick tmux calls or regex on the event loop. Note t1111_5 is concurrently
in-flight in `monitor_app.py`/`monitor_shared.py` (preview render offload) —
re-check those files at implementation time (main advances mid-session).

**User decisions (locked):**
- Shadow discovery **derived from existing discovery output** (the per-tick
  `list-panes` already returns `@aitask_shadow_target` as field 9) — zero
  extra tmux round-trips. NOT the AC's original "promote `match_shadow_pane`"
  approach; `match_shadow_pane`/`_find_shadow_pane_for` stay in
  `minimonitor_app.py` for their event-driven uses (launch guard, freshness,
  concerns). **Update the task AC accordingly** (explicit deviation, approved).
- Glyph: `◆` (U+25C6), colored `bold magenta` / `yellow` / `green`.
- Minimonitor docked followed-agent panel stays **fully static** (no icon
  there); the icon appears only in the general agent-list rows of both TUIs.

## Concurrency safety contract (binding — t1111 invariants)

- **A (pure workers):** shadow classification happens inside the existing
  `_classify_batch` off-loop call; no widget/`self.query`/DOM access added
  off-loop.
- **B (loop-only mutation):** the shadow-snapshot map is written **only** in
  `commit_snapshots` (loop-side), like `_last_content`.
- **E (one batch per cycle):** shadow panes join the SAME raw-capture gather
  and the SAME single `_classify_batch` — no per-shadow fan-out.
- **F (single offload seam):** no new `to_thread` call sites; everything runs
  through the existing `_run_offloaded` batch.
- **Generation guard:** unchanged protocol — a superseded cycle discards both
  agent and shadow results (no new re-entry paths, no token changes).

## Implementation

### 1. `monitor_core.py` — discovery carries shadows

- **`TmuxPaneInfo`** (line ~312): add field `shadow_target: str = ""`
  (non-empty ⇒ this pane is a shadow; value = followed pane's id).
- **`_parse_list_panes`** (line ~1126): instead of `continue`-dropping a pane
  whose `parts[8]` is a shadow marker, build its `TmuxPaneInfo` with
  `shadow_target=parts[8].strip()` and `category=PaneCategory.AGENT` (forced —
  so the prompt scan and idle bookkeeping apply; a same-window shadow shares
  the agent window name anyway) and collect it into a **separate shadows
  list**. Companion-process filtering still applies first. Return changes to
  `tuple[list[TmuxPaneInfo], list[TmuxPaneInfo]]` (agents, shadows).

  **Cache-boundary invariant (binding):** shadow panes are **never registered
  in `self._pane_cache`**. Real cache-backed consumers exist outside the
  render path — `applink/router.py:572` (`capture_pane`), `applink/pusher.py:211`
  (`get_pane`), plus compare-mode state — and a cached AGENT-category shadow
  would make them treat a shadow like a normal agent. Instead, the capture
  pipeline passes the shadow's `TmuxPaneInfo` (already in hand from discovery)
  directly: extend `capture_pane_content_async` with an optional
  `pane: TmuxPaneInfo | None = None` parameter that skips the cache lookup
  when provided. Consequences pinned by tests: `get_pane(shadow_id) is None`,
  `capture_pane(shadow_id) is None`, `shadow_id not in mon._pane_cache` after
  a full discovery+capture cycle. (`_last_content`/`_last_change_time` DO get
  shadow ids — that's the idle bookkeeping, internal-only, cleaned by
  `_clean_stale` like any pane.)
- **Discovery wrappers**: adapt `discover_panes`, `discover_panes_async`,
  `_discover_panes_multi`, `_discover_panes_multi_async` internally. Public
  behavior of `discover_panes(_async)` is unchanged (returns agents only);
  add `discover_panes_with_shadows_async() -> (agents, shadows)` used by the
  capture pipeline. Shadows sorted with the same key.
  (Every other consumer — kill/sibling logic, applink, agent lists — keeps
  seeing agents only; the shadow-exclusion invariant is preserved.)
- **`capture_all_classified_async`** (line ~1535): discover via
  `discover_panes_with_shadows_async()`; raw-capture `agents + shadows` in the
  SAME `asyncio.gather` (shadows captured via the new `pane=` parameter, no
  cache dependency); include shadows in the SAME `_classify_batch` items.
  Return shape unchanged (`(gen, classified)` — shadow entries are ordinary
  `(pane, content, result)` tuples distinguishable by `pane.shadow_target`).
- **`commit_snapshots`** (line ~1579): after the generation check, split:
  entries with `pane.shadow_target` non-empty go into a fresh
  `dict[followed_pane_id, PaneSnapshot]` assigned to
  `self._shadow_snapshots` (rebuilt every commit → a dead shadow disappears
  next tick); the rest build the returned agent dict as today.
  `_clean_stale` keep-set includes shadow pane ids (they're in `classified`),
  so shadow idle bookkeeping survives across ticks and is cleaned on death.
  Duplicate shadows for one followed pane (orphan escape): keep the newest
  (largest numeric `%N`) — mirror `match_shadow_pane`'s defense; add a small
  module-level pure helper for the numeric key (or reuse a local copy of
  `_pane_id_sort_key` logic).

  **Transient-failure semantics (explicit decision):** a shadow whose raw
  fetch failed arrives as `(pane, None, None)` and is skipped by the rebuild —
  the icon disappears for that tick. This deliberately **mirrors the existing
  failed-agent-pane behavior** (a failed agent's row also vanishes for the
  tick, "matching the pre-split behaviour"); no stale-state preservation,
  which would show a snapshot with a frozen idle clock. Documented in the
  `commit_snapshots` docstring + pinned by a test.
- **New accessor** on `TmuxMonitor`:
  `get_shadow_snapshot(followed_pane_id: str) -> PaneSnapshot | None`
  reading `self._shadow_snapshots` (init `{}` in `__init__`).
- **Sync `capture_all`** (used only by the `tmux_monitor.py` CLI debug tool):
  stays agent-only for capture, but **clears `self._shadow_snapshots`** so a
  sync cycle can never leave stale shadow state visible behind
  `get_shadow_snapshot` (fail-safe: icon absent rather than stale). Docstring
  documents that shadow state is produced only by the async live path.

### 2. `monitor_shared.py` — single-site glyph formatters

Define the state→color mapping ONCE:

```python
def _state_color(snap: PaneSnapshot) -> str:
    if getattr(snap, "awaiting_input", False): return "bold magenta"
    if snap.is_idle: return "yellow"
    return "green"

def format_state_dot(snap: PaneSnapshot) -> str:          # ●, existing convention
    return f"[{_state_color(snap)}]●[/]"

SHADOW_GLYPH = "◆"
def format_shadow_glyph(shadow_snap: PaneSnapshot | None) -> str:
    if shadow_snap is None: return ""
    return f"[{_state_color(shadow_snap)}]{SHADOW_GLYPH}[/]"
```

Refactor the two duplicated dot if/elif blocks
(`monitor_app.py:1013-1018`, `minimonitor_app.py:614-619`) to call
`format_state_dot` — the color mapping is then defined once (task AC).

### 3. `monitor_app.py` — row rendering

`_format_agent_card_text` (line ~1012): resolve
`shadow_snap = self._monitor.get_shadow_snapshot(snap.pane.pane_id)` (None
when `self._monitor is None`), build `shadow = format_shadow_glyph(shadow_snap)`,
and render the two glyphs adjacently before the name:

```
f" {dot}{(' ' + shadow) if shadow else ''} {glyph} {window_index}:{window_name} ..."
```

Non-shadowed rows produce the exact same string as today (no placeholder).

### 4. `minimonitor_app.py` — row rendering

`_agent_card_text` (line ~607): same insertion into `line1`
(`f"{dot}{(' ' + shadow) if shadow else ''} {glyph} {name}  {status}"`).
**Fix the stale docstring while here:** it still claims the function is
"Shared by the docked followed-agent panel (`_rebuild_own_agent_panel`)" —
in reality the docked panel renders via `_own_agent_identity_text`
(line 695) and `_agent_card_text`'s only caller is the general list
(line 735). Rewrite it to say it renders general-list rows only and that the
docked panel is static by design (no live status, no shadow glyph) — so a
later edit can't be misled into adding `◆` there.
Docked `_own_agent_identity_text` / `_maybe_build_own_agent_panel`: untouched.
Minimonitor's refresh uses `capture_all_async` → shadow map fills for free.

### 5. Task AC update (before implementing)

Edit `aitasks/t1133_shadow_agent_status_icon_monitor.md` AC bullet 3 to:
"Shadow pane discovery is derived from the monitor's existing per-tick
discovery output (`@aitask_shadow_target` field in `_LIST_PANES_FORMAT`),
adding zero tmux round-trips; `match_shadow_pane` remains minimonitor's
event-driven lookup." Commit via `./ait git` with the `updated_at` bump.

### 6. Tests — `tests/test_monitor_shadow_status.py`

Follow `tests/test_monitor_finalize_offload.py` patterns (scripted
`TmuxMonitor`, injectable `_run_offloaded`, no sleeps):

1. **Parse split:** feed 9-field `list-panes` lines (agent, shadow, other,
   companion) through `_parse_list_panes`; assert shadows returned separately
   with `shadow_target` set, and — **negative control** — the agent list is
   byte-identical to today's (shadow still excluded).
2. **Cache-boundary invariant:** after a full discovery+capture cycle with a
   bound shadow, assert the cache-backed consumers stay shadow-blind:
   `shadow_id not in mon._pane_cache`, `mon.get_pane(shadow_id) is None`,
   `mon.capture_pane(shadow_id) is None` — the exact surfaces
   `applink/router.py` / `applink/pusher.py` call.
3. **Batch + golden equivalence:** scripted monitor with agent + bound shadow;
   run `capture_all_async`; assert `get_shadow_snapshot(followed_id)` state
   (prompt via a real `all_patterns()` claude pattern, idle via threshold,
   active) equals a direct synchronous `classify_content` on the same content
   (independent ground truth).
4. **Lifecycle & staleness:** shadow present → snapshot; remove shadow from
   scripted panes → next async cycle `get_shadow_snapshot` returns `None`;
   shadow idle bookkeeping id cleaned from `_last_content`. **Transient
   failure:** shadow raw-fetch returns `None` for one tick → icon state absent
   that tick (mirrors failed-agent behavior). **Sync-path staleness guard:**
   populate shadow state via the async path, then run sync `capture_all()` →
   `get_shadow_snapshot` returns `None` (map cleared, never stale).
5. **Duplicate shadows:** two shadows targeting one pane → newest `%N` wins.
6. **Supersession:** stale-generation commit leaves `_shadow_snapshots`
   untouched (negative control: with guard bypassed, the stale write DOES
   land — proves the guard is load-bearing).
7. **Render-level (both TUIs):** two layers, because `.plain` strips styles
   and cannot prove color:
   - *Order/presence on plain text:* `Text.from_markup(row).plain` shows
     `● ◆ ≈ name` ordering for a shadowed row; no `◆` anywhere in a
     non-shadowed row (string unchanged vs today); no `◆` in the docked-panel
     text (`_own_agent_identity_text` output asserted directly).
   - *Color proof on the markup/spans:* assert the raw markup string contains
     `[bold magenta]◆[/]` / `[yellow]◆[/]` / `[green]◆[/]` for the three
     shadow states (or equivalently inspect `Text.from_markup(...).spans`
     style at the `◆` offset) — the magenta/yellow/green mapping is proven at
     row level, not just in the pure formatter.
8. **Pure formatter:** `format_shadow_glyph(None) == ""`; three states → three
   colors; `format_state_dot` mapping matches pre-refactor colors.

## Verification

- `python tests/test_monitor_shadow_status.py` (new) and the existing
  `tests/test_monitor_finalize_offload.py`, `tests/test_monitor_focus_switch.py`,
  `tests/test_monitor_preview_offload.py`, `tests/test_monitor_refresh_no_sync_tmux.py`
  all pass (no regression in the offload/generation protocol).
- Live smoke: in a tmux session run `ait monitor` + an agent window, spawn a
  shadow via minimonitor `e`; observe `◆` appear beside the agent's `●`,
  change color as the shadow works/idles/prompts, and disappear when the
  shadow pane is killed. (This is behavioral/TUI — offer a follow-up
  manual-verification task at Step 8c.)

## Step 9 reference

Post-implementation: gates run (`risk_evaluated` declared), archive via
`aitask_archive.sh 1133`, push. No worktree (fast profile, current branch).

## Risk

### Code-health risk: medium
- Shadow panes entering the discovery/capture pipeline could leak into
  agent-facing surfaces (kill/sibling logic, applink `get_pane`/`capture_pane`,
  agent lists, compare-mode state) if the exclusion split regresses ·
  severity: medium · → mitigation: **structural** — shadows are never
  registered in `_pane_cache` (capture passes the pane object directly), so
  cache-backed consumers cannot see them; pinned by the cache-boundary test
  (test 2) + parse-split negative control (test 1).
- Stale shadow state after a sync `capture_all()` cycle, or a frozen icon on
  transient capture failure · severity: low · → mitigation: sync path clears
  `_shadow_snapshots` (fail-safe: absent, never stale); transient failure
  drops the icon for one tick, mirroring failed-agent-pane semantics; both
  pinned by test 4.
- `_parse_list_panes` return-signature change ripples through 4 internal
  discovery wrappers on a load-bearing per-tick path · severity: low ·
  → mitigation: public `discover_panes(_async)` contract preserved; existing
  offload/generation tests re-run.
- t1111_5 is concurrently editing `monitor_app.py` / `monitor_shared.py`
  (preview offload) — mid-session drift could produce conflicts or stale-file
  edits · severity: medium · → mitigation: re-read both files immediately
  before editing (main advances mid-session); touched functions are disjoint
  from t1111_5's (`_format_agent_card_text` / formatter block vs
  `_update_content_preview` / `_ansi_to_rich_text`).

### Goal-achievement risk: low
None identified. — Detection semantics are reused verbatim (`classify_content`
with forced AGENT category), render sites are pinned to exact lines, and the
glyph/color mapping is shared with the existing dot convention.
