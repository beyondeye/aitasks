---
Task: t1685_park_code_agents_tristate_mark_and_visibility_toggle.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1685 — Park code agents: tristate mark + visibility toggle

## Context

`ait monitor` and `ait minimonitor` list every agent window across every session.
The prioritized mark (`★`/`☆`, t1326/t1383) annotates that list but never shortens
it, and every listed agent is captured and classified on every refresh tick whether
or not the user still cares about it.

This task adds a third mark state — **parked** — so a user can declare "I am done
watching this one". A parked agent drops out of the pane list (behind a `P` filter),
renders an explicit placeholder when shown, and stops being captured and classified
altogether. The design was settled with the user during exploration and is recorded
in `aitasks/t1685_*.md`; this plan is the executable form of it.

Two decisions taken during planning (user-confirmed):

- **Implemented as a single task**, not decomposed. The layers are tightly coupled
  (nothing renders until the store carries `kind`) and the design is already settled.
- **The session bar gains an `N parked` term.** The three live counters continue to
  partition the *non-parked* agents exactly; parked agents leave that partition and
  get their own always-visible count, so a parked agent is never invisible on every
  surface at once.

---

---

### Pre-phase (risk mitigations)

1. `[characterize_capture_failure_drop]` Before touching `commit_snapshots`, add a
   characterization test (`tests/test_monitor_parked_capture.py`) that pins today's
   behaviour for a pane whose capture failed: `classified` carries `(pane, None,
   None)`, the returned snapshots dict has **no** entry for that pane id, the pane id
   is still passed to `_clean_stale`, and the monitor's `_last_content` for it is
   unchanged. Run it green against the unmodified `monitor_core.py` and commit it
   before the parked branch is written, so the new branch beside the `result is None`
   drop cannot silently alter the existing one.

2. `[own_panel_capture_negative_control]` Add a test in
   `tests/test_minimonitor_own_mark.py` asserting that when the followed agent is
   parked, `MiniMonitorApp._parked_agent_pairs()` does **not** contain that agent's
   `(session_name, window_name)`, and that the pane is therefore still present in the
   arguments handed to `capture_pane_content_async`. Pair it with an explicit
   **negative control** in the same test module: monkeypatch the subtraction away (or
   call the base `AgentMarksMixin._parked_agent_pairs` directly) and assert the pair
   *is* present — the control must fail the §7 assertion, or the assertion proves
   nothing. Cover the unconfirmed-identity path in the same phase: force
   `_update_own_window_info` to fail (`tmux_run_async` → `rc=1`) with a parked mark
   already on the followed agent and assert the published set is **empty** and the
   followed pane is still in the capture arguments; repeat with a truncated two-field
   tmux reply, which leaves `_own_window_name` stale rather than absent.

---

## 1. Store — `.aitask-scripts/lib/agent_marks.py`

### 1.1 Schema v2 + kind

- `SCHEMA_VERSION = 2`.
- New kind constants beside it:
  ```python
  KIND_PRIORITY = "priority"
  KIND_PARKED = "parked"
  KIND_NONE = ""          # not a stored value — the "unmarked" answer from lookups
  MARK_KINDS = (KIND_PRIORITY, KIND_PARKED)
  ```
- `MarkRecord` gains `kind: str = KIND_PRIORITY` (defaulted, so every existing
  positional construction in tests keeps working).
- `dump()` writes `"kind"` on **every** record, including priority ones — explicit
  output makes the round-trip assertion in AC7 crisp. Absent-on-read still means
  priority (the v1 rule), so a hand-edited file stays readable.

### 1.2 The v1→v2 read migration (replaces the "no migration exists" contract)

`_parse` currently rejects `version != SCHEMA_VERSION` and its comment says that is
deliberate *because no migration exists*. **Rewrite that comment** — do not work
around it — and accept `version in (1, SCHEMA_VERSION)`:

- `version > SCHEMA_VERSION` → still `MalformedMarksError` (a newer file must not be
  truncated to fields we do not understand).
- `version < 1` / non-int / bool → still `MalformedMarksError`.
- `version == 1` → migrate: no `kind` key exists in a v1 file by construction, so
  every record parses as `KIND_PRIORITY` through the same code path.
- The returned `MarksFile.version` is normalised to `SCHEMA_VERSION` after a
  successful parse — the in-memory generation *is* v2 regardless of what it was read
  from, and `dump()` already writes `SCHEMA_VERSION` unconditionally.
- `kind` validation: present-and-not-in-`MARK_KINDS` → `MalformedMarksError`
  (fail-closed, matching every other field check in `_parse`).

Update the module docstring's version paragraph to state that v1 is migrated on read
and that v2 files are invisible to a pre-t1685 `ait` in every project — fail-safe,
accepted, and now one-directional rather than mutual.

### 1.3 Policy functions

- **`toggle()` → `cycle()`** (rename; `ToggleResult` → `CycleResult`). A tristate
  cycle named `toggle` would be scope-dishonest. `CycleResult(kind: str | None,
  record: MarkRecord | None)` where `kind is None` means "now unmarked".
  Cycle order: unmarked → `KIND_PRIORITY` → `KIND_PARKED` → unmarked.
  Implementation: find the existing record; if absent append priority; if priority
  replace with a parked record (fresh `marked_at`); if parked remove.
- **`expire()`** skips parked records — parking is a long-lived intent and a 2-day
  TTL silently un-parking a background agent defeats the feature. Star marks keep
  the existing TTL. Document the asymmetry on the function.
- **`sweep_liveness()`** unchanged: it applies to both kinds, so a parked agent whose
  tmux window is gone is still reaped.
- **`visible_marks()`** returns `dict[tuple[str, str], str]` (key → kind) instead of a
  key set, applying the TTL filter to priority marks only.

### 1.4 `MarksView`

- `_keys: set[...]` → `_kinds: dict[..., str]`.
- `is_marked(root, window)` keeps working (`kind_for(...) == KIND_PRIORITY`).
- New `kind_for(root, window) -> str` returning `KIND_NONE` when absent, and
  `is_parked(root, window) -> bool`.

### 1.5 CLI

- Verb `toggle` → `cycle`, printing `MARKED:`, `PARKED:` or `UNMARKED:` with the
  existing `<root>|<window>` payload.
- `list` prints `MARK:<root>|<window>|<marked_at>|<kind>`.

## 2. Locked writer — `.aitask-scripts/aitask_agent_marks.sh`

Rename the `toggle` verb to `cycle` (same two positional args, same 2 s
`TOGGLE_LOCK_TIMEOUT`, renamed `CYCLE_LOCK_TIMEOUT`), and update the header comment
block: the store now records `{root, window, marked_at, kind}`, and the verb list
must describe the three outputs. Nothing else about the lock protocol changes.

## 3. Glyph + coverage manifest

### 3.1 `monitor_shared.py`

- New `PARK_GLYPH = "P"` beside `MARK_GLYPH` / `MARK_EMPTY_GLYPH`, with the same
  shape of evidence comment the star pair already carries.
- `format_mark_glyph(marked: bool)` → **`format_mark_glyph(kind: str)`** taking
  `KIND_NONE` / `KIND_PRIORITY` / `KIND_PARKED` and returning
  `[dim]☆[/]` / `[bold white]★[/]` / `[bold white]P[/]`.
  Bold white for `P` for the same reason the star is bold white: the state ladder
  owns magenta/blue/yellow/green, so white reads as *user intent*. `★` and `P` share
  the colour but not the glyph, and a parked row carries no state dot at all.

### 3.2 `tests/tools/regen_font_coverage.py` + `tests/data/font_coverage.json`

- Rename `REJECTED_CODEPOINTS` → `EXTRA_MEASURED_CODEPOINTS`. The tuple no longer
  holds only rejections: `0x0050` is the *chosen* glyph and must be measured by the
  same generator. Update its comment to a per-codepoint verdict list.
- Add `0x0050` (`P`, chosen), `0x23F8` (`⏸`, rejected — emoji-capable) and `0x25A0`
  (`■`, rejected — collides with the state dot `●`).
- Regenerate with `python tests/tools/regen_font_coverage.py`, then `--check`.
- Update every reference to the old tuple name in
  `tests/test_mark_glyphs_single_source.py`.
- **If the generator's measurement disagrees with the task's table** (e.g. `⏸` turns
  out to be covered), report the discrepancy rather than editing the manifest by
  hand — the manifest is measured evidence, not a claim.

## 4. `monitor_core.py` — parked agents are not captured

### 4.1 Publishing the parked set down (mirrors `_set_session_root_map`)

`monitor_core` knows nothing about marks and must not do a blocking tmux round-trip
to learn about them (`tests/test_monitor_refresh_no_sync_tmux.py` guards that). So
the App publishes the set once per tick:

```python
# TmuxMonitor
_parked_agents: frozenset = frozenset()      # class-level floor, __new__-built tests

def set_parked_agents(self, pairs) -> None:
    """Publish the (session_name, window_name) pairs to skip capturing."""
    self._parked_agents = frozenset(pairs or ())
```

Identity is `(session_name, window_name)` — the pane-side spelling of the store's
`(root, window)`.

**Derived from the marks store, never from `_snapshots`.** `_parked_agent_pairs()`
inverts `_session_root_map` (session → root) and emits `(session, window)` for every
parked entry in `MarksView`. It therefore has **no snapshot dependency** and is
computable before any capture has ever run — which is what makes the startup case
below correct rather than lagged. (Two sessions sharing a root each get a pair; a
pane matches only when both fields match, so the extra pair is inert.)

**Publication point: `_refresh_data`, BEFORE `capture_all_classified_async()`.**
This requires reordering the head of `_refresh_data` in both apps — a required part
of this change, not an optimisation:

- `monitor_app._refresh_data` (:998-1017): move
  `get_session_to_project_mapping_async()` + `update_session_mapping(session_roots)` +
  `_set_session_root_map(session_roots)` + `_refresh_marks()` **above** the
  `capture_all_classified_async()` await, then publish the parked pairs, then
  capture. None of those four depend on `snaps`. `_compute_completed_panes()` **does**
  and stays exactly where it is, after `self._snapshots = snaps`.
- `minimonitor_app._refresh_data` (:1518-1544): the same reordering, and additionally
  move `await self._update_own_window_info()` (:1544) above the capture so
  `_own_window_name` is fresh before the subtraction below runs. Its relative order
  with `_maybe_build_own_agent_panel` (:1567) is unchanged.

Without this reordering a monitor opened while a mark is already parked captures and
classifies that agent once on every launch — a permanent per-launch leak that
violates AC5 and the feature's "stop paying for its status entirely" promise. The
reorder also removes the one-tick lag entirely, so no "republish after a cycle"
special case is needed beyond the one `_cycle_mark_for` already performs.

Call the publisher through a `getattr(self._monitor, "set_parked_agents", None)`
probe — several test doubles (`_FakeRefreshMonitor`) implement only part of the
monitor API, and an unconditional call would break them.

### 4.2 `capture_all_classified_async`

After `_record_discovery_facts(...)` — which stays **exactly** where it is, so a
parked agent remains in discovery and its mark survives `sweep_liveness` (the
load-bearing correctness fact of the whole feature) — split the pane set:

```python
parked = [p for p in panes
          if p.category == PaneCategory.AGENT
          and (p.session_name, p.window_name) in self._parked_agents]
parked_ids = {p.pane_id for p in parked}
live = [p for p in panes if p.pane_id not in parked_ids]
all_panes = live + shadows
```

Parked panes therefore enter neither the `capture_pane_content_async` gather nor the
`_classify_batch` payload. They are re-appended to the returned `classified` list as
`(pane, None, ClassifyResult(compare_value="", parked=True))` so `_clean_stale` still
counts them.

- `ClassifyResult` gains `parked: bool = False`.
- Shadow panes are **not** filtered: a shadow is its own pane, and §7 needs the
  shadow of a followed agent to keep working.

### 4.3 `commit_snapshots` — the explicit parked branch

The `if result is None: continue` drop means a parked pane cannot be routed down the
failed-capture path or it disappears even with the filter off. Add the branch
**before** the `None` check:

```python
for pane, content, result in classified:
    if result is not None and result.parked:
        snapshots[pane.pane_id] = _parked_snapshot(pane, now)
        continue
    if result is None:
        continue
    ...
```

`_parked_snapshot` constructs a `PaneSnapshot` **directly**, bypassing
`_apply_bookkeeping` — that function is documented as the only writer of
`_last_content` / `_last_change_time`, and a parked pane has no content to compare,
so it must not touch the idle clock:

```python
PaneSnapshot(pane=pane, content="", timestamp=now, idle_seconds=0.0,
             is_idle=False, awaiting_input=False, parked=True)
```

- `PaneSnapshot` gains `parked: bool = False` (defaulted — safe for the doubles that
  build it with five keyword args).

## 5. Both TUIs — `AgentMarksMixin` (`monitor_shared.py`)

- Class-level floors + `_init_agent_marks` seeds: `_hide_parked: bool = False`.
- `_mark_kind(snap) -> str` beside `_is_marked`, returning `KIND_NONE` when the strict
  root is unresolvable (same fail-closed answer `_is_marked` gives today).
  `_is_marked` becomes `self._mark_kind(snap) == KIND_PRIORITY`.
- `_is_parked(snap) -> bool`.
- `_parked_agent_pairs() -> frozenset[tuple[str, str]]` — the per-tick
  `(session_name, window_name)` set published to core, computed from
  `_session_root_map` + `MarksView` alone. **It must not read `_snapshots`**: it is
  published before the first capture, when there are none (§4.1).
- `_toggle_mark_for` → **`_cycle_mark_for`**; argv becomes `["cycle", root, window]`.
  Toast matrix extends to:
  - `MARKED:` → `Prioritized <window>`
  - `PARKED:` → `Parked <window>` — and, when `self._hide_parked` is true, the longer
    form `Parked <window> — hidden. Press P to show parked, then space to unpark.`
    (the task requires the unpark path be stated in the toast)
  - `UNMARKED:` → `Unmarked <window>`
  - `LOCK_BUSY` / error branches unchanged.
  After the successful write it keeps `invalidate()` + `_refresh_marks()`, then
  republishes the parked set, then `call_later(self._refresh_data)`.
- New `action_toggle_parked_visibility()`: flips `_hide_parked`, hands off focus if
  the focused card is about to be hidden (monitor only, §6.3), notifies
  `Parked agents hidden` / `Parked agents shown`, and calls `_refresh_data`.

**Do not rename the `toggle_mark` *action* id.** Shortcut action ids are persisted in
`userconfig.yaml` under `shortcuts:`; renaming it would silently drop every user's
rebinding. Only the internal helper is renamed.

## 6. `ait monitor` — `monitor_app.py`

### 6.1 Binding

`Binding("P", "toggle_parked_visibility", "Parked")` in `BINDINGS`. No `check_action`
change is needed — the existing zone rule already hides every non-`switch_zone`
binding in the preview zones, which is the same gating `space` gets. `p`/`P` are both
currently unbound in this app.

### 6.2 Per-tick parked set (the `_completed_pane_ids` precedent, t1322)

- `self._parked_pane_ids: frozenset[str] = frozenset()` in `__init__`, with the same
  "starts empty so a keypress-driven rebuild reuses the last tick's set" comment.
- Computed in `_refresh_data` right after `_refresh_marks()` and **before**
  `_compute_completed_panes()` and `_maybe_auto_switch()`, both of which read it.

### 6.3 Consumers

| site | change |
|---|---|
| `_compute_completed_panes` (:1376) | skip parked panes — keeps `done_count` honest and skips their `os.stat` |
| `_maybe_auto_switch` (:1398) | exclude parked from the "keep current focus" guard, from `awaiting`, and from `idle_agents` (AC10) |
| `_rebuild_session_bar` (:1544) | partition `agents` into parked / live; the three counters run over **live only**; new always-shown `parked_str = f"  [dim]{n} parked[/]"` when `n > 0`. Rewrite the partition docstring to state the four-way split and that the `parked` term is independent of the `P` filter |
| `_rebuild_pane_list` (:1723) | filter parked out of `agents` **before** `desired_ids` is built when `_hide_parked` — otherwise a park does not trigger a rebuild. The `CODE AGENTS (N)` header then counts visible agents |
| `_format_agent_card_text` (:1631) | parked branch (§6.4) |
| `_refresh_data` focus-request block (:1048) | ignore a focus request naming a parked-and-hidden window — there is no card to focus |
| `_offer_concerns` (:1126) / `_scan_concern_signatures` (:2169) | skip panes in `_parked_pane_ids`; a parked agent must not raise an auto-offer |

The **review loop is not touched** — it is minimonitor-only and bound to the followed
agent, which §7 explicitly keeps live.

### 6.4 Parked row render

```python
if snap.parked:
    return (f" {format_mark_glyph(KIND_PARKED)} "
            f"{snap.pane.window_index}:{snap.pane.window_name} "
            f"({snap.pane.pane_index})  [dim]parked[/]")
```

No state dot, no shadow glyph, no compare-mode glyph, no status badge, no gate
summary, no phase, no title row. A frozen `●` would read as a live verdict that is in
fact arbitrarily stale, and every other element on the row is either capture-derived
or a live verdict; the placeholder is deliberately the whole row.

### 6.5 Focus handoff (AC4 — the confirmed defect)

`_restore_focus` (:1450) restores via `self._pane_cards.get(pane_id)` after a guard on
`focused.pane_id in self._snapshots`. A filtered-out card is absent from `_pane_cards`
and a parked pane's snapshot is the minimal one, so both paths can miss and focus
silently leaves the pane list. Two changes, deliberately both:

1. **Explicit handoff** — new `_focus_next_visible_card(hidden_pane_id)` picks the
   next `PaneCard` after the hidden one in the container's child order, falling back
   to the previous one, sets `_focused_pane_id` and focuses it.
   Called from a `MonitorApp.action_toggle_mark` override — capture the focused pane
   id, `await super().action_toggle_mark()`, then hand off if the pane is now parked
   and `_hide_parked` — and from `action_toggle_parked_visibility` when the filter is
   switched on over a focused parked card. Both run before the deferred rebuild.
2. **Zero-visible-card branch (reachable: park the only agent with the filter on).**
   When no `PaneCard` will remain, the handoff must not merely return — it must
   *clear*, or `_focused_pane_id` keeps naming a pane with no card while `space`,
   `k`, `n`, `e` and the preview all still resolve against it. Concretely:
   `self._focused_pane_id = None`; `self._selected_card_pane_id = None`;
   `self._active_zone` stays `Zone.PANE_LIST` (so `P` remains dispatchable — it is
   `check_action`-gated on the zone); `self.set_focus(None)` so no removed widget
   holds focus; then `_update_content_preview()` / `_update_shadow_preview()`, whose
   existing `not (self._focused_pane_id and … in self._snapshots)` guard
   (`monitor_app.py:1848`) then renders the "Focus an agent or pane to see its output"
   empty state. `space` is safe in this state: `_get_focused_pane_id()` returns
   falsy and `action_toggle_mark` already returns silently.
3. **Parked panes get their own preview, not a blank one.** A parked pane **is** in
   `_snapshots` (the minimal snapshot), so the `:1848` empty-state guard passes and
   the preview would render its empty `content` as if it were captured output.
   Extend the guard: when the focused snapshot has `parked=True`, render
   `[dim]This agent is parked — press Space to unpark[/]` and return. Without this,
   focusing a parked row with the filter **off** shows a blank pane indistinguishable
   from a broken capture.
4. **Structural fallback** — in `_restore_focus`, when `pane_id` resolves to no card,
   focus the first `PaneCard` in the container; when the container holds **no** cards
   at all, take the clearing branch from (2) rather than leaving focus wherever it
   landed. This is the invariant that cannot be forgotten at a future call site.
   Apply the same no-card tolerance to `MiniMonitorApp._restore_focus` (:1983) — its
   list rows are read-only so it needs no handoff, but it can equally end up with an
   empty list once parked rows are hidden.

## 7. `ait minimonitor` — `minimonitor_app.py`

- `Binding("P", "toggle_parked_visibility", "Parked", show=False)` and an **11th**
  `KEY_HINTS_TEXT` row `"P:hide/show parked"` (18 cells, inside the 38-column budget;
  the existing `"space:mark ★ (followed agent)"` line is left intact because
  `test_minimonitor_own_mark.py` pins both `"space:mark"` and `"followed agent"`).
  `_KEY_HINTS_ROWS` is derived from the text, so nothing else needs editing — but
  `_refresh_short_mode`'s threshold shifts by one row and
  `tests/test_minimonitor_top_chrome_render.py` must be re-run.
- `_rebuild_pane_list` (:2455): filter parked out of the `agents` section when
  `_hide_parked`.
- `_agent_card_text` (:2115): parked branch — `P`, the name, dim `parked`, no dot.
- `_rebuild_session_bar` (:2023) and `_compute_completed_panes` (:2102): same parked
  exclusion + `N parked` term as the full monitor.
- **The followed agent keeps being captured (§7 of the task).** `MiniMonitorApp`
  overrides `_parked_agent_pairs()` to subtract `(self._session, self._own_window_name)`
  — the snapshot-free identity already maintained by `_update_own_window_info` (:1690)
  and seeded at mount, **not** `_find_own_window_snapshot()`, which needs snapshots
  that do not exist before the first capture.

  **The subtraction is only valid against an identity confirmed by *this* tick.**
  `_update_own_window_info` returns silently on every failure path — no `TMUX_PANE`,
  no monitor, `rc != 0`, empty stdout, or a reply with fewer than three tab fields —
  and in each case the **previous** `_own_window_name` survives. A stale name (a
  window renamed since the last successful query) subtracts the wrong pair, so the
  real followed agent stays in the parked set and core skips exactly the pane this
  companion exists to watch, with no error anywhere. `None` is not the only unsafe
  state; *unconfirmed* is.

  So:
  - `_update_own_window_info()` returns `bool` — `True` only when this call's tmux
    query succeeded **and** yielded a window name. Update its docstring accordingly.
  - `self._own_identity_confirmed: bool = False` (class-level floor, `__new__`-built
    tests) is **reset to `False` at the top of every `_refresh_data`** and set from
    that return value. The mount-time seed does **not** set it — the seed only fills
    `None` fields and can race the first refresh, which is one of the two failure
    modes this guard exists to close.
  - `_parked_agent_pairs()` returns `frozenset()` — publishing **no** parked pairs at
    all — unless `_own_identity_confirmed` is true and `_own_window_name` is set.

  Fail-safe, not fail-closed-on-`None`: an unconfirmed identity costs one tick of
  capture for every parked agent in this pane's view (recoverable, invisible except
  as CPU), whereas a wrong or missing subtraction silently freezes the docked panel —
  the failure a user would not report as a bug. The full monitor needs none of this:
  it follows nothing, so it makes no subtraction. Parking the agent
  a minimonitor follows is a signal to *other* monitors' lists, not an instruction to
  this one to stop working — `L`, `c` and shadow readiness are all bound to that agent
  and all need live capture. Without this subtraction the own panel goes stale, which
  is the single easiest way to get this feature wrong.
- Own panel: `_own_mark_state` becomes `str | None` — `None` still means "not
  markable" (renamed-off-`agent-` window, no glyph at all), otherwise one of
  `KIND_NONE` / `KIND_PRIORITY` / `KIND_PARKED`. `_own_card_text` and
  `_refresh_own_live_state` thread the kind instead of the bool; the panel shows `P`
  when parked and keeps its live phase line, because it is still being captured.
  `_OWN_PANEL_MAX_ROWS` is unchanged — no row is added, only the glyph changes.
- No focus handoff is needed here: the followed agent lives in the docked panel and
  was never in the list, and list rows stay read-only.

## 8. Documentation

- `website/content/docs/tuis/monitor/how-to.md` — the mark bullet (:64) and the
  "How to Mark an Agent as Prioritized" section (:226): the tristate cycle, the `P`
  filter, the parked placeholder, and the `N parked` bar term. The line "Marks are
  purely visual — they do not reorder the list or change the session-bar counters" is
  now false and must be rewritten. State that with the filter on, unparking requires
  revealing parked agents first (`P`, then `Space`). Note that parked marks are exempt
  from the age TTL but not from the departed-agent sweep.
- `website/content/docs/tuis/monitor/reference.md` — amend the `Space` row (:38) and
  add a `P` row to the pane-list-zone table.
- `website/content/docs/tuis/minimonitor/how-to.md` — the mark bullet (:43), the
  "note you left yourself" passage (:150), the marking section (:284) and the
  keybinding table (:380). Say explicitly that parking the *followed* agent does not
  stop this minimonitor from watching it.
- `.aitask-scripts/monitor/minimonitor_app.py` `KEY_HINTS_TEXT` (covered in §7).

## 9. Tests

New/extended, mapped to the acceptance criteria:

| AC | test |
|---|---|
| 1 | `tests/test_agent_marks.py` — `cycle()` order over three calls; `tests/test_monitor_agent_marks_action.py` — argv is `["cycle", root, window]` and the three toasts, on the focused card (monitor) and the followed agent (minimonitor) |
| 2 | `tests/test_monitor_agent_marks.py` — parked row renders `P` + dim `parked` and contains **no** `●`, asserted on the mounted widget in both apps and in minimonitor's own panel |
| 3 | new `tests/test_monitor_parked_filter.py` — `P` hides and re-shows parked rows in both apps; state is per-instance and in-memory |
| 4 | same file — three cases: (a) park the focused card with the filter on among several agents, assert `app.focused` is a still-mounted `PaneCard`; (b) **single visible agent** — park it with the filter on, assert `_focused_pane_id is None`, `_selected_card_pane_id is None`, `_active_zone is Zone.PANE_LIST`, and the preview shows the empty-state text; (c) **negative control** — revert the handoff and assert focus leaves the pane list, so (a) and (b) are falsifiable |
| 4 | same file — focus a parked card with the filter **off** and assert the preview reads `This agent is parked`, not an empty content pane |
| 5 | new `tests/test_monitor_parked_capture.py` — **startup case**: seed a parked record in the store *before* the app's first `_refresh_data`, run one refresh, and assert the parked pane id never appears in the `capture_pane_content_async` call arguments or the `_classify_batch` payload on that first tick. This is the case the pre-reorder ordering leaks, so it is also the control for §4.1's reordering |
| 5 | new `tests/test_monitor_parked_capture.py` — assert on the *call arguments*: the parked pane id is absent from the `capture_pane_content_async` calls and from the `_classify_batch` payload, and present with the filter off in `commit_snapshots`' output with `parked=True` |
| 6 | same file — a parked agent is still in `last_discovered_agents()`; a purge run while parked keeps its mark; **negative control**: the same purge with the window absent from discovery drops it |
| 7 | `tests/test_agent_marks.py` — a v1 fixture loads with every mark `kind == KIND_PRIORITY`, `MarksFile.version == 2`, and `dump()` produces `"version": 2` with `"kind": "priority"` written |
| 8 | `tests/test_agent_marks.py` — `expire()` drops an over-TTL priority mark and keeps an over-TTL parked one; `sweep_liveness()` drops a parked mark whose window is gone |
| 9 | `tests/test_monitor_parked_filter.py` — the three counters sum to the non-parked agent count and the bar carries `N parked` |
| 10 | `tests/test_monitor_parked_capture.py` / filter suite — `_maybe_auto_switch` never selects a parked pane, in both the awaiting and the idle branch |
| 11 | `tests/test_mark_glyphs_single_source.py` — the manifest records `0050`, `23F8`, `25A0` with the measured per-font results; non-vacuity still holds |
| §7 | `tests/test_minimonitor_own_mark.py` — parking the followed agent leaves it **out** of the published parked set, so its own panel keeps being captured |
| §7 | same file — **unconfirmed own identity**: with a parked mark on the followed agent, force `_update_own_window_info` to fail (`rc=1`, then a truncated two-field reply that leaves a *stale* name) and assert `_parked_agent_pairs()` is empty and the followed pane still reaches `capture_pane_content_async`; plus a rename case where the query succeeds with a new name and the subtraction follows it |

Existing suites that must be updated for the renames / signature changes:
`tests/test_agent_marks.py`, `tests/test_agent_marks_liveness.py`,
`tests/test_agent_marks_concurrency.sh`, `tests/test_monitor_agent_marks.py`,
`tests/test_monitor_agent_marks_action.py`, `tests/test_minimonitor_own_mark.py`,
`tests/test_monitor_modal_space_dispatch.py`, `tests/test_multi_session_monitor.sh`,
`tests/test_multi_session_minimonitor.sh`,
`tests/test_minimonitor_concern_action.py` (the hints/BINDINGS parity audit).

---

### Post-phase (risk mitigations)

1. `[fail_loud_on_unknown_mark_kind]` Once every call site is converted, make
   `format_mark_glyph(kind)` reject anything that is not one of `KIND_NONE` /
   `KIND_PRIORITY` / `KIND_PARKED` with `raise ValueError(f"unknown mark kind:
   {kind!r}")` rather than falling through to the unmarked glyph. A stray `bool` from
   a missed call site then fails loudly instead of rendering `☆`. Add a test in
   `tests/test_monitor_agent_marks.py` covering both an unknown string and `True`.
   **Pair the raise with its reachability argument in the docstring:** every
   production caller passes a `_mark_kind()` / `MarksView.kind_for()` result, and both
   are total over the three kinds, so the raise is a programming-error guard and not a
   new way for advisory data to break a refresh tick. Do not add a `try/except` around
   the call sites to "make it safe" — that would restore exactly the silent
   wrong-glyph fallthrough this guard exists to remove.

---

## Verification

```bash
# store + policy
bash tests/run_all_python_tests.sh --test-dir tests   # full suite; read the LAST line
bash tests/test_agent_marks_concurrency.sh
bash tests/test_multi_session_monitor.sh
bash tests/test_multi_session_minimonitor.sh

# glyph manifest
python tests/tools/regen_font_coverage.py --check     # must print FRESH

# binding registry + hints parity
bash tests/test_shortcuts_registry_coverage.sh

# docs (required after editing anything under website/content/)
cd website && python3 check_links.py --build
```

Then drive it live in a scratch tmux session (never the user's main one — see
`aidocs/framework/tui_conventions.md`, "Tmux-stress tasks"): launch two agent windows,
open `ait monitor`, press `Space` twice on one to park it, confirm the placeholder row
and the `N parked` bar term, press `P` to hide it and confirm focus stays on a visible
card, then `P` + `Space` to unpark. Repeat the followed-agent half in `ait minimonitor`
and confirm its own panel keeps updating while parked.

## Risk

### Code-health risk: high
- The parked branch in `commit_snapshots` lands beside the `if result is None: continue` drop, inside the most invariant-laden function in the monitor (generation guard, discovery-facts promotion, shadow-seq merge). Ordered wrong it either drops parked rows entirely or lets a parked pane reach `_apply_bookkeeping` and corrupt the idle clock. · severity: high (residual — the pre-change behaviour is pinned by inline pre-phase characterize_capture_failure_drop) · → mitigation: inline pre-phase characterize_capture_failure_drop
- `format_mark_glyph(bool)` → `format_mark_glyph(str)` and the `toggle` → `cycle` rename touch 5 production call sites and ~12 existing test files. Python formats a stray `bool` into the new signature without complaint, so a missed call site renders the wrong glyph silently rather than raising. · severity: low (residual — an unknown kind now raises, per inline post-phase fail_loud_on_unknown_mark_kind) · → mitigation: inline post-phase fail_loud_on_unknown_mark_kind
- The App→core parked-set publication now depends on a specific ordering at the head of `_refresh_data` in **both** apps (mapping + marks + publish strictly before the capture await), reached through a `getattr` probe for partial test doubles. A future edit that moves the publish site back below the capture, or a double that grows the method without honouring it, degrades to "nothing is parked" with no error — silently, and only on the tick that matters. The AC5 startup test is the executable guard for the ordering half. · severity: medium · → mitigation: none
- **New (introduced by the augmented plan).** `fail_loud_on_unknown_mark_kind` puts a `raise` on a render helper, in a module whose stated posture is that advisory mark data must never be able to crash a refresh tick. Bounded by the reachability argument recorded on the post-phase step — both producers of the argument are total over the three kinds — but it is a real new failure mode if a future caller bypasses them. · severity: low · → mitigation: none
- Blast radius: 5 production modules, the coverage generator and its manifest, 4 documentation pages and ~12 test files in one commit series. · severity: medium · → mitigation: none

### Goal-achievement risk: medium
- §7 ("the followed agent keeps being monitored") rests entirely on one subtraction in `MiniMonitorApp._parked_agent_pairs`. Getting it wrong produces no error and no crash — just a docked panel showing frozen data, which is exactly the failure mode a user would not report as a bug. The subtraction now depends on an own-window identity confirmed by the current tick — an unconfirmed or stale name publishes no parked pairs at all. · severity: low (residual — pinned with a falsifiable negative control and forced identity-resolution failures by inline pre-phase own_panel_capture_negative_control) · → mitigation: inline pre-phase own_panel_capture_negative_control
- The task's "roughly eight `PaneCategory.AGENT` sites per app" was resolved by exhaustive enumeration, but three sites are deliberately left unchanged (`_resolve_shadow_target`, `_switcher_selected_session`, the minimonitor review loop). If one is in fact reachable for a parked agent, a hidden agent stays actionable in a way the user did not expect. · severity: medium (residual — deferred, not closed, by the spawned audit) · → mitigation: t1695
- AC11 asserts measured `cmap` coverage for `⏸` (U+23F8) and `■` (U+25A0) taken from a prior run. If this machine's font files disagree, the acceptance criterion cannot be satisfied as written and the discrepancy must be reported rather than papered over. · severity: low · → mitigation: none

### Planned mitigations
- timing: pre-phase | name: characterize_capture_failure_drop | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 1 (parked branch beside the `result is None` drop) | desc: Characterization test pinning today's capture-failure behaviour in `commit_snapshots`, committed green before the parked branch is added.
- timing: pre-phase | name: own_panel_capture_negative_control | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal risk 1 (§7 rests on one subtraction; silent stale panel) | desc: Assert the followed agent is excluded from the published parked set and still captured, including under a forced own-identity resolution failure and a stale post-rename name, with a negative control that fails when the subtraction is removed.
- timing: post-phase | name: fail_loud_on_unknown_mark_kind | type: enhancement | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 2 (bool→str signature widening across 5 call sites) | desc: `format_mark_glyph` raises on an unrecognised kind instead of falling through to the unmarked glyph.
- timing: after | name: residual_agent_site_audit | type: chore | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: goal risk 2 (consumer-enumeration completeness) | desc: Re-audit `_resolve_shadow_target`, `_switcher_selected_session` and the minimonitor review loop against a parked agent and close any that turn out to be reachable. | created: t1695

---

## Implementation notes (t1685)

Every section of the plan landed. Deviations and decisions taken during
implementation, recorded here rather than silently:

1. **`MarksFile.is_marked` was narrowed too** (not called out in the plan).
   `MarksView.is_marked` became priority-only, and leaving the same-named
   `MarksFile` method meaning "carries any mark" would have been a trap: two
   methods with one name disagreeing about whether a parked agent is "marked".
   Both now answer priority-only; `kind_of` / `kind_for` is the "any mark"
   question.

2. **The minimonitor hint went on the `p:pick task` line, not an 11th row.**
   The plan proposed an 11th `KEY_HINTS_TEXT` row. Measured: the hints band is
   docked bottom, so an extra row costs the pane list a row at every pane height
   — `test_minimonitor_top_chrome_render.test_empty_chrome_costs_no_rows` caught
   it (list height 20 → 19). Folding `P:parked` onto the existing
   `c:concerns  p:pick task` line keeps ten rows, stays inside the 38-column
   budget at 33 cells, and has the side benefit of putting `p` and `P` side by
   side where the case distinction is visible.

3. **The parked-set publisher is `_publish_parked_agents`**, a mixin method that
   `getattr`-probes `set_parked_agents` — as planned — and is called from BOTH
   `_refresh_data` (before the capture) and `_cycle_mark_for` (immediately after
   a successful write), so a park takes effect on the very next capture rather
   than the one after it.

4. **`_hand_off_focus_before_hiding` is a mixin hook with a no-op default**,
   overridden only by `MonitorApp`. Minimonitor list rows are read-only and its
   followed agent lives in a docked panel, so it has nothing to hand off — that
   is asserted rather than assumed (`test_minimonitor_needs_no_focus_handoff`).

5. **Test doubles built with `SimpleNamespace` needed `parked=False`.**
   `tests/test_multi_session_{monitor,minimonitor}.sh` build snapshot doubles by
   hand; `parked` is a real defaulted `PaneSnapshot` field, so the doubles were
   completed rather than making the renderer defensive with `getattr`.

6. **Font measurement agreed with the task's table exactly** — `P` U+0050
   covered by both supported families, `⏸` U+23F8 by neither (and emoji-capable),
   `■` U+25A0 by both. No discrepancy to report.

7. **`REJECTED_CODEPOINTS` → `EXTRA_MEASURED_CODEPOINTS`** in the generator: the
   tuple stopped being all-rejections when `P` joined it.

### Cross-session staging (raised at Step 8 review, addressed)

**The working tree held two tasks' uncommitted work.** `t1686`
(`companion_pane_filter_misses_shell_hosted_monitor`) was `Implementing` in a
concurrent session and shares two files with this task:

| file | t1685 hunks | t1686 hunks |
|---|---|---|
| `.aitask-scripts/monitor/monitor_core.py` | 8 | 10 |
| `tests/test_multi_session_monitor.sh` | 2 | 3 |

No hunk mixes the two tasks. Staging either file wholesale would have shipped
another task's in-progress work under the `(t1685)` commit — wrong ownership,
unreliable rollback, and possibly a half-finished behaviour landed on main.

**Resolution — isolated build, staged as a blob, working tree untouched.** For
each mixed file: copy the working-tree version into the scratchpad, **reverse**-
apply a patch containing only the t1686 hunks, and stage the resulting blob with
`git hash-object -w` + `git update-index --cacheinfo`. Nothing is written back to
the shared checkout — no `git checkout`, `restore`, `stash` or `add -p` — so the
other session cannot lose work to this commit.

Verified before staging: each isolated file differs from `HEAD` by exactly the
expected hunk count (8 and 2), contains **zero** added lines mentioning any t1686
marker, still carries every t1685 symbol, and passes `py_compile` / `bash -n`.
Verified after committing by running the parked suites in a throwaway
`git worktree` checked out at the commit — i.e. against the committed content,
not the composite working tree.

Five further files carry t1686 work only and were deliberately **not** staged:
`tests/test_agent_marks_generation.py`, `tests/test_monitor_companion_filter.py`,
`tests/test_monitor_refresh_no_sync_tmux.py`, `tests/test_monitor_shadow_status.py`,
`tests/test_multi_agent_window_substrate.sh`.

## Final Implementation Notes

- **Actual work done:** Every section of the plan landed, plus both inline
  pre-phases and the inline post-phase. Store schema v2 with a real v1→v2 read
  migration; `toggle` → `cycle` through the Python API, the CLI verb and the
  locked shell writer; `PARK_GLYPH = "P"` with `format_mark_glyph` retyped from
  `bool` to a mark kind; `TmuxMonitor.set_parked_agents` publish-down with the
  capture/classify exclusion and an explicit `commit_snapshots` parked branch;
  the `P` filter, parked row render, focus handoff, parked preview, session-bar
  `N parked` term and consumer exclusions in both TUIs; the font-coverage
  manifest extended and regenerated; three website pages rewritten.

- **Deviations from plan:**
  1. `MarksFile.is_marked` was narrowed to priority-only as well. The plan only
     narrowed `MarksView.is_marked`; leaving two same-named methods disagreeing
     about whether a parked agent is "marked" would have been a trap.
  2. The minimonitor hint went onto the existing `c:concerns  p:pick task` line
     rather than becoming an 11th `KEY_HINTS_TEXT` row. The plan proposed the
     extra row and flagged the height budget for re-checking; the re-check found
     a real cost — `test_minimonitor_top_chrome_render` measured the pane list
     dropping from 20 rows to 19 at every pane height, because the hints band is
     docked bottom. Folding `P:parked` in keeps ten rows, sits at 33 of the 38
     available columns, and puts `p` and `P` side by side where the case
     distinction is legible.
  3. `MonitorApp._parked_pane_ids` needed a **class-level floor**, not just an
     `__init__` default. Its consumers include the concern offer and the
     signature scan, which are exercised by `__new__`-built test apps nowhere
     near this feature — same rationale the mixin already records for
     `_session_root_map`.

- **Issues encountered:**
  - Hand-rolled `SimpleNamespace` snapshot doubles in seven test modules raised
    on the new `PaneSnapshot.parked` field. Resolved by completing the doubles
    rather than making the renderer defensive with `getattr` — an incomplete
    double does not "ignore" a field the code reads, it raises on it, and a
    `getattr` default would also have silently tolerated a real snapshot missing
    the field.
  - `test_minimonitor_startup_input_latency`'s `_Boom` monitor double needed
    `get_session_to_project_mapping_async` once that call moved above the
    capture. Answered in the double so its `RuntimeError` still originates from
    the capture, which is what that test is actually about.
  - A dead `#auto-switch` anchor was introduced in the monitor how-to and caught
    by `check_links.py --build` (`hugo build` never fails a dead fragment).

- **Key decisions:**
  - `_parked_agent_pairs()` is derived from the mark store and the session→root
    map, with **no snapshot dependency**, so it is computable before the first
    capture. This is what makes the startup case correct rather than one tick
    late, and it is why the head of `_refresh_data` was reordered in both apps.
  - The minimonitor subtraction is gated on an own-window identity **confirmed
    by the current tick**, not on the name merely being non-`None`:
    `_update_own_window_info` returns silently on five failure paths and each
    leaves the previous name standing, so a post-rename stale name would
    subtract the wrong pair and freeze the very panel the pane exists to show.
    Unconfirmed publishes nothing — one tick of extra capture instead.
  - The parked snapshot is built directly rather than through
    `_apply_bookkeeping`, which owns `_last_content` / `_last_change_time` and
    must never see a pane with no content.
  - `format_mark_glyph` raises on an unrecognised kind instead of falling
    through to `☆`; the reachability argument (both producers are total over the
    three kinds) is recorded on the function so nobody "makes it safe" with a
    `try/except` and restores the silent wrong-glyph fallthrough.
  - The two mixed files were staged as isolated blobs — see "Cross-session
    staging" above.

- **Upstream defects identified:** None

- **Manual-verification failure:** item "Press `P` in `ait monitor` to hide parked agents, then `P` again to show them; confirm the list shrinks and grows" failed; follow-up task t1697.
