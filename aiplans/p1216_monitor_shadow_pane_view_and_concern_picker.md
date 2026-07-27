---
Task: t1216_monitor_shadow_pane_view_and_concern_picker.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1216 — Make `ait monitor` shadow-aware (parent plan / decomposition)

## Context

The user's workflow shifted to heavy **shadow agent** use. Today the shadow
companion is only reachable from `ait minimonitor` — the full `ait monitor`,
which is the best tool for switching between many sessions/agents, shows only a
one-glyph shadow indicator (`◆`, landed by t1133) and understands nothing about
shadow concerns. That forces a choice between "good session switching"
(monitor) and "shadow access" (minimonitor).

This task removes that forced choice: from `ait monitor` you will be able to
**see** a selected agent's shadow pane live, **type into** either the agent or
its shadow, **pick and forward** the shadow's concerns, and **spawn** a shadow —
without leaving the monitor.

Nearly all the machinery already exists; this is predominantly a **lift-and-wire**
job, not new capability. The single biggest constraint is that every piece being
reused is currently shaped around minimonitor's "there is exactly one followed
agent" assumption, while the monitor has N agents and a moving selection.

### Decisions taken with the user

| Question | Decision |
|---|---|
| Shadow display shape | **Third zone (`SHADOW`)**, rendered as a **horizontal split of the existing preview area** — agent preview left, shadow preview right. The shadow column's width matches the **real shadow pane's width** (`shadow_snap.pane.width`) so content renders unwrapped. |
| Key targeting | Focused zone = key target (`Tab` cycles list → preview → shadow). Active zone already draws a `zone-active` border and a `LIVE` badge; both are applied per column. |
| Auto-offer with N agents | **Card badge + toast for the selected agent only.** Every agent whose shadow has a fresh concern block gets a marker on its pane-list card; a toast fires only for the currently selected agent. |
| Spawn keys `e` / `E` | **In scope** — ported to the monitor. |
| Structure | **Decompose into child tasks.** |

## Architecture

### The one hard constraint: two capture paths, not one

- The **tick capture** (`monitor_core._capture_args`, L1452-1459) is
  `capture-pane -p -e` with **no `-J`** — ANSI-laden and soft-wrap-split. That
  is exactly what `_ansi_to_rich_text` wants for the **preview render**.
- `concern_parser` requires **wrap-joined, ANSI-free** text (module docstring
  L11-15). Minimonitor gets it by shelling out to `aitask_shadow_capture.sh`
  (`capture-pane -p -J`, `--deep`) in `_capture_shadow_text`.

These cannot be served from one capture. The tick snapshot feeds the **shadow
preview**; an on-demand `-J` capture feeds the **picker**.

### Shadow snapshot concurrency contract

`_shadow_snapshots` is rebuilt **wholesale** by `commit_snapshots`
(monitor_core.py:1743), and `capture_pane_classified_async` reserves a new
global generation *before* its await (L1572) — which is why today's 0.3 s
`_fast_preview_refresh` can already supersede an in-flight full
`capture_all_classified_async`. Adding a second 0.3 s ticker naively would
widen that starvation window **and** let a single-shadow refresh clobber every
other agent's shadow entry. Three binding rules:

1. **The shadow refresh never touches the global capture generation.** It uses
   a separate monotonic `_shadow_capture_generation`, reserved before its await.
   It therefore cannot invalidate a full refresh — the agent-facing
   `_pane_cache` / snapshot path is untouched by it.
2. **`_shadow_snapshots` entries are stamped and merged per key, never rebuilt
   by the fast path.** Each entry carries the shadow generation it was fetched
   at; a write lands only if its stamp is **newer** than the entry it would
   replace. Both the full rebuild and the single-shadow merge obey this, so the
   two are order-independent in either interleaving.
3. **Only the full refresh may delete.** Discovery is authoritative for
   existence: `commit_snapshots` drops keys absent from its own discovery, and
   a single-shadow merge is **dropped** if its key is no longer present (it can
   never resurrect a shadow the full refresh just removed). Fail-closed.

**Tests (t1216_1)** — deterministic overlap tests using the
`test_monitor_shadow_status.py` scripted-coroutine fixture (no sleeps): a
shadow refresh interleaved *inside* a full refresh in both orders leaves the
newer content for the refreshed key and every other key intact; a shadow
refresh commit is dropped after its shadow is removed by a full refresh; and a
**negative control** proving a shadow refresh never bumps `capture_generation`
(the pre-existing `SupersessionTests` remain green).

### The perf problem the badge policy creates, and its fix

Minimonitor runs the expensive `-J` subprocess capture **every tick** in
`_maybe_offer_concerns`. With N agents on screen that is N subprocess spawns per
tick — unacceptable, and it would violate the acceptance criterion on per-tick
cost.

Fix: a **cheap trigger on data we already have.** The shadow's tick content is
already in `shadow_snap.content` at zero extra tmux traffic. The block sentinels
(`===AITASK-CONCERNS===` / `===END-CONCERNS===`, 21 and 18 chars) never soft-wrap
at any realistic pane width, and a marker row always *begins* with `- [` even
when its body wraps. So an ANSI-stripped scan of the tick content is a reliable
**trigger**.

To honour the acceptance criterion *"no second implementation of concern
parsing"*, this detector is **added to `concern_parser.py` as a third strictness
tier**, alongside the existing `parse_concerns` (forgiving) / `has_concern_block`
(strict) pair the module already documents:

```python
def concern_block_signature(raw_text: str) -> str | None:
    """Cheap freshness trigger over a NON-wrap-joined, ANSI-bearing tick
    capture. Returns a REFLOW-STABLE digest of the last block region, or None
    when no complete block is present. Trigger only — never parse its input
    into forwardable concerns; the picker re-captures with -J."""
```

**Reflow stability is a contract, with a stated residual.** A digest of the raw
block region would change whenever the shadow pane is resized, the scrollbar
gutter appears, or ANSI rendering shifts — making an unchanged block look fresh
again. `tmux capture-pane` without `-J` breaks a wrapped row by inserting a
**newline** and pads rows with trailing spaces; it never inserts other
characters. So the digest is taken over the block region after stripping ANSI
and **normalising whitespace runs to a single space, then stripping**
(`re.sub(r"\s+", " ", ...).strip()`).

Collapsing whitespace to *nothing* was considered and rejected: it is fully
reflow-proof but erases token boundaries, so `"needs review"` and
`"needsreview"` collide — a genuinely changed concern would be silently missed.
Normalising to one space keeps those distinct.

The residual, stated rather than hidden: normalisation is exact for trailing
row padding and for wraps at a word boundary, but a wrap landing **mid-word**
injects a space that was not in the source, so re-rendering the *same* block at
a different pane width can change the digest. The consequence is bounded and
deliberately chosen to fail in the safe direction — **at most one spurious
re-offer** (a badge and, if selected, one toast; nothing is lost or forwarded),
never a missed real change. Both halves are pinned by tests.

**Narrow-pane fallback.** The sentinels are 21 and 18 chars, so a shadow pane
narrower than `_SENTINEL_SAFE_COLS = 24` can wrap them and hide a block from the
cheap detector entirely. In that case (`shadow_snap.pane.width <
_SENTINEL_SAFE_COLS` and the cheap detector reports no block) the monitor falls
back to the authoritative `-J` capture **for the selected agent only**, throttled
to the shadow-freshness cadence (every other tick). That bounds the cost to at
most one subprocess per tick — the same as minimonitor today — and never scales
with N.

Per-followed-pane the monitor keeps `sig -> last offered sig`; a change means
"fresh block" → badge + (if selected) toast. The authoritative `-J` capture runs
**only** when the user presses `c` (or via the narrow fallback above).

### Where lifted code goes

Per the acceptance criteria, ported logic is **shared**, not copy-pasted.
`monitor_app.py` and `minimonitor_app.py` already carry a known duplication set;
this task must not grow it.

- `monitor_core.py` — tmux-touching shadow seams (lookup, capture, refresh,
  staleness inputs). It already owns `SHADOW_TARGET_OPTION`,
  `SHADOW_ANALYZED_AT_OPTION`, `get_shadow_snapshot`, `get_pane_option`,
  `get_last_change_wall`, `_pane_id_num`, `_strip_ansi`.
- `monitor_shared.py` — UI-side shared pieces (`ConcernPickerModal` already
  lives here and its docstring already claims both apps push it;
  `format_shadow_glyph`).
- `concern_parser.py` — the grammar, including the new trigger tier.

### Invariant that must survive untouched

Shadow panes stay **out of** `_pane_cache`, agent snapshots, the pane list,
kill/sibling/next-sibling logic. `_parse_list_panes` (L1185-1201) and
`commit_snapshots` (L1724-1727) enforce this today and t1118 depends on it for
applink. Every child that adds a shadow read path must go through
`get_shadow_snapshot` / the new seam, never through `get_pane` / `capture_pane`.

---

## Child decomposition

Ordered so the headless, testable core lands first and each child owns its tests.

### t1216_1 — Shared shadow seam (headless, no UI)

Extract every minimonitor shadow helper that is pure or depends only on
`TmuxMonitor`, rewire minimonitor onto it (behaviour-identical), and add the new
trigger tier. **Nothing about the monitor changes in this child** — its proof is
that the whole existing minimonitor/shadow suite still passes against the lifted
implementations.

- `monitor_core.py`:
  - Promote `_strip_ansi` (L149) to public `strip_ansi`.
  - Move `match_shadow_pane` (minimonitor L116-142) here; delete
    `_pane_id_sort_key` (L104-113) and use the existing `_pane_id_num` (L294) —
    collapses a duplication the t1133 notes already flagged.
  - `TmuxMonitor.find_shadow_pane(followed_pane_id)` and
    `find_shadow_pane_async(...)` from `_shadow_query_args` (L1275) +
    `_find_shadow_pane_for_sync` (L1283) / `_find_shadow_pane_for` (L1298).
  - `TmuxMonitor.capture_shadow_text(shadow_pane, *, lines=None)` from
    `_capture_shadow_text` (L1309) — keeps `--deep`, the 3 s timeout, the
    `SHADOW_PLAN_CAPTURE_LINES` env override, and the `OSError`/timeout/rc
    guards verbatim. **The `-J` join in `aitask_shadow_capture.sh` is the
    parser's contract — do not route this through the tick capture.**
  - `TmuxMonitor.refresh_shadow_snapshot(followed_pane_id)` — re-capture one
    bound shadow and **merge** it into `_shadow_snapshots` per the three rules
    in "Shadow snapshot concurrency contract" above: reserve from
    `_shadow_capture_generation` (**not** `_next_generation`), pass `pane=` to
    `capture_pane_content_async` (the t1133 kwarg that bypasses `_pane_cache`),
    and commit only if the stamp is newer *and* the key still exists. Needed by
    t1216_2's fast tick. `commit_snapshots` is amended to stamp the entries it
    rebuilds and to keep a newer-stamped entry for keys present in both.
  - `compute_shadow_staleness(monitor, shadow_pane, followed_pane, eps)` →
    tri-state `True | False | None` plus the analyzed-at epoch, lifted from
    `_update_shadow_freshness` (L1368-1418) with its failure-safe semantics
    intact (unreadable / malformed stamp / unobserved pane **preserve** the
    prior state and never clear a standing warning).
  - `format_stale_duration` (from the `@staticmethod` at L1420) → `monitor_shared`.
- `concern_parser.py`: add `concern_block_signature` (see above), documented in
  the module docstring's strictness table as **trigger-only**.
- `minimonitor_app.py`: delete the moved bodies, import the shared ones. Keep
  `_find_own_agent_snapshot` (L525) local — it is intrinsically
  minimonitor-shaped. `_set_shadow_stale_banner` stays local (it is hard-wired
  to `#mini-shadow-stale`), but takes its text from the shared formatter.
- Update `.claude/skills/aitask-shadow/concern-format.md` with the new trigger
  tier row in its "Trigger vs. action contract" table.

**Tests** — new `tests/test_shadow_seam.py` (unit; `_FakeMon` idiom from
`test_minimonitor_concern_action.py`) covering `match_shadow_pane` newest-wins,
`find_shadow_pane` sync/async, `capture_shadow_text` argv + env, staleness
tri-state incl. the preserve-on-failure cases, and
`concern_block_signature`. The signature tests must pin the contract as a
property, not a fixture:

- **Stable** — the same block with trailing row padding, ANSI colour runs, and
  word-boundary wraps at several pane widths yields an identical digest.
- **Discriminating** — `"needs review"` vs `"needsreview"` (the collision that
  rules out whitespace-elimination) yield **different** digests, as does any
  changed priority, region, or body.
- **Residual, pinned deliberately** — a mid-word wrap of the same block yields a
  different digest; the test asserts this is the *known* behaviour so nobody
  later "fixes" it back into a collision, and its docstring names the
  spurious-re-offer consequence.
- **Narrow pane** — the `< _SENTINEL_SAFE_COLS` case where the sentinel itself
  wraps, so the detector correctly reports `None` and hands off to the fallback.

Also add the concurrency tests listed under "Shadow snapshot concurrency
contract". Every existing test in
`test_minimonitor_concern_action.py`, `test_minimonitor_shadow_pick.py`,
`test_concern_parser.py`, `test_monitor_shadow_status.py` must pass unmodified
except for import-path updates — that is this child's characterization net.

### t1216_2 — `SHADOW` zone: side-by-side shadow preview + key targeting

- `Zone.SHADOW` added to the enum (L80) and `ZONE_ORDER` (L85). `_switch_zone`
  (L1341) **skips** `SHADOW` when the selected agent has no bound shadow, so
  `Tab` behaves exactly as today for non-shadowed agents.
- **Leaving an already-active invalid zone.** Entry-time skipping is not enough:
  the shadow can vanish *while* `SHADOW` is focused — either permanently (the
  shadow pane died) or for a single tick (t1133's `LifecycleTests` establish
  that a transient capture failure legitimately drops the snapshot with no stale
  preservation). Yanking the user out on a one-tick blip would be its own bug,
  so the transition is explicit:
  - Snapshot absent, shadow still bound → hold the zone, render a
    `[dim](shadow unavailable)[/]` placeholder.
  - Absent for `SHADOW_ABSENT_GRACE_TICKS = 2` consecutive **full** refreshes, or
    the followed pane no longer has a bound shadow at all → fall back to
    `Zone.PREVIEW`, restore focus there, and notify once.
  - **While the shadow is absent, keystrokes in `SHADOW` are dropped, never
    forwarded.** They must not silently fall through to the agent pane — that
    would type a user's shadow input into a working agent. This is a safety
    property with its own test.
- Also switch away from `SHADOW` when the pane-list selection moves to a
  different agent that has no shadow (the selection drives which shadow is shown).
- `compose()` (L474-486): `#content-section` gains a `Horizontal` row holding
  two columns — `#agent-col` (existing `#preview-scroll` > `#content-preview`,
  keeping ids so nothing else breaks) and `#shadow-col`
  (`#shadow-scroll` > `#shadow-preview` + `#shadow-header`).
  `#shadow-col` is `display: none` unless a shadow is bound.
- **Width:** `#shadow-col.styles.width = shadow_snap.pane.width` (+ scrollbar
  gutter), and `#shadow-preview.styles.min_width = shadow_snap.pane.width` —
  mirroring what the agent preview already does at L1240. The heights are
  untouched, so `PREVIEW_SIZES` / `_apply_preview_size` (L1563) keep working
  unchanged.
- **Narrow fallback:** decided on the **mounted row's usable content width**,
  not `self.size.width`. `self.size.width` is the screen width and ignores
  `#content-section`'s border, `#preview-scroll`'s `scrollbar-gutter: stable`,
  padding, and the shadow column's own gutter — at the boundary that error is
  several columns and would leave the agent column too narrow or overflowing.
  Measure `self.query_one("#preview-row").content_region.width` (available only
  once mounted and laid out) and subtract the shadow column's full occupied
  width including its gutter; if the remainder is below
  `SHADOW_MIN_AGENT_COLS = 40`, do not split — render only the focused zone's
  column full-width. Evaluated on mount, in `on_resize` (L1606), and after
  `_apply_preview_size` (L1563), each via `call_after_refresh` so the
  measurement happens post-layout.
- **`t` (Tail) must follow the active column.** `action_scroll_preview_tail`
  (L1593-1604) is hard-wired to `#preview-scroll` and `_preview_scroll_state`;
  left alone it would silently tail the agent preview while the user is looking
  at the shadow. Note the constraint that fixes its meaning: `check_action`
  (L1417) disables every non-`switch_zone` binding while a preview zone is
  focused (keys there are forwarded to tmux), so **`t` is only ever pressable
  from `PANE_LIST`** — "the active column" cannot mean "the focused zone".
  Define it as the **last-focused preview column**: track
  `_active_preview_zone` (`PREVIEW` | `SHADOW`), updated by `_switch_zone` and
  `on_descendant_focus`, defaulting to `PREVIEW` and **reset to `PREVIEW`
  whenever the shadow column is hidden, absent, or the selection moves to an
  agent with no shadow**. `t` resumes tail-follow for that column, resetting its
  scroll state to `(True, None)` and scheduling the matching fast refresh
  (`_fast_preview_refresh` or `_fast_shadow_refresh`).
  `z` (`action_cycle_preview_size`, L1558) needs no such treatment — the split
  is horizontal, so the height presets apply to both columns unchanged.
- `_update_shadow_preview` mirrors `_update_content_preview` (L1171): its own
  render-generation counter, PAUSED/LIVE badge, frozen branch, per-shadow-pane
  scroll anchors in a `_shadow_scroll_state` map, and the offloaded
  `_ansi_to_rich_text` via `_run_offloaded`. **Reuse the existing helpers**
  (`_locate_anchor`, `_record_preview_scroll` parameterised by target) rather
  than cloning them.
- **Fast tick:** `_manage_preview_timer` (L1429) also starts the 0.3 s timer for
  `Zone.SHADOW`, driving `refresh_shadow_snapshot` from t1216_1. It runs **only**
  while the shadow zone is focused, so users with no shadows pay nothing.
- **Key targeting** — `on_key` (L1457): add a `Zone.SHADOW` branch **above** the
  existing PREVIEW catch-all at L1486, forwarding to the shadow pane id via
  `_forward_key_to_tmux`. `check_action` (L1417) must treat `SHADOW` like
  `PREVIEW`. Target the pane id resolved from `self._focused_pane_id` →
  `get_shadow_snapshot(...)`, **never** `_get_focused_pane_id()` (which returns
  `None` whenever focus is off a `PaneCard`).
- Docs: `website/content/docs/tuis/monitor/_index.md` layout section (currently
  says "four stacked areas" and lists five) + `reference.md` zone table.

**Tests** — new `tests/test_monitor_shadow_zone.py`: zone skipping with/without
a shadow; shadow column width derived from `pane.width`; key forwarding targets
the shadow pane in `SHADOW` and the agent pane in `PREVIEW` (spy on
`forward_key`); **negative control** that adding the zone leaves the shadow out
of `_snapshots`, the pane list, and kill/next-sibling targeting. Plus, for the
two contracts above:

- **Narrow-fallback boundary** — a mounted pilot (`run_test(size=(W, 30))`)
  driven at `W` = threshold−1 / threshold / threshold+1, asserting
  `#shadow-col.display` flips at exactly the intended column and that the agent
  column's laid-out width never drops below `SHADOW_MIN_AGENT_COLS`. Deriving
  `W` from the measured chrome (rather than hardcoding) is what proves the
  decision is not made on the raw screen width.
- **`t` targets the active column, independently for each** — after focusing the
  agent preview and returning to the pane list, `t` restores tail-follow on the
  agent column and leaves the shadow column's scroll anchor untouched; after
  focusing the shadow column, the reverse. Assert on both
  `_preview_scroll_state` / `_shadow_scroll_state` entries and on which fast
  refresh was scheduled, so a helper that tails "both" or the wrong one fails.
  Plus the reset cases: with no shadow bound, and after the shadow disappears,
  `t` falls back to the agent column.
- **Zone invalidation while focused** — shadow snapshot absent for 1 tick holds
  the zone and renders the placeholder; absent for `SHADOW_ABSENT_GRACE_TICKS`
  falls back to `PREVIEW`; shadow unbound entirely falls back immediately; and
  a key pressed while `SHADOW` is focused-but-absent results in **zero**
  `forward_key` calls (asserted against the agent pane id specifically).

Follow `test_monitor_shadow_status.py`'s
`_make_monitor` fixture (real `TmuxMonitor`, scripted coroutines, `_sync_offloaded`
— no tmux, no sleeps) and its `MountedCardRenderTests` pilot idiom for the
render assertions.

### t1216_3 — Concerns in the full monitor (badge + toast + picker)

- Per-tick, for each agent with a bound shadow, run `concern_block_signature`
  over `shadow_snap.content` (already captured — **zero extra tmux traffic**).
  Keep `_concern_sig_offered: dict[followed_pane_id, str]`.
- **Badge lifecycle — explicit state model.** The badge is *derived*, never a
  latched flag: `badge_on(pane) == sig is not None and sig != _concern_sig_offered.get(pane)`.
  The transitions that follow from that definition, each one tested:

  | Event | `_concern_sig_offered` | Badge |
  |---|---|---|
  | New block, signature differs from the stored one | unchanged | **on** (+ toast if selected) |
  | `c` pressed → `-J` capture returns `None` (failure/timeout) | **unchanged** | stays **on** |
  | `c` pressed → capture ok but parse yields 0 concerns, or still head-truncated after the deep retry | **unchanged** | stays **on** |
  | `c` pressed → modal actually pushed with ≥1 concern | set to the signature of the **captured** text | off |
  | Picker cancelled (Esc / Cancel) | already set at push | stays off — the user saw them |
  | Shadow re-issues a *different* block | differs again | **on** again |
  | Block scrolls out of the capture window (`sig is None`) | **retained** | off |
  | That same block scrolls back in | matches retained | stays off (no re-toast) |
  | Followed pane loses its shadow entirely | entry **evicted** | off |

  **The marker is set only once `ConcernPickerModal` has actually been pushed
  with at least one concern** — not on the keypress. Clearing at keypress would
  hide a block the user never saw whenever the authoritative capture fails,
  times out, or parses nothing, which is exactly when they most need the badge
  to persist. Setting it at push rather than on confirm is still deliberate: a
  user who opens the list and forwards nothing has seen the block, so
  re-toasting them would be noise.

  The value stored is the signature **of the text the picker actually captured**
  (recomputed from the `-J` capture), not the tick signature that raised the
  badge — the shadow may have emitted more between the badge and the keypress,
  and storing the older signature would leave the newer block permanently
  un-offered. Retaining the entry on `sig is None` rather than clearing it is
  what stops a block flickering in and out of the capture window from re-firing
  forever — and it matches minimonitor, which never clears
  `_last_concern_block_payload` on absence.
- **Badge:** a fresh signature marks the agent's card. Extend
  `format_shadow_glyph` in `monitor_shared.py` (or add a sibling formatter) so
  the `◆` gains a concern marker; non-shadowed rows must stay byte-identical, as
  t1133 established.
- **Toast:** only when the fresh agent is `self._focused_pane_id` —
  `"Shadow raised concerns — press 'c' to pick"`, once per signature, with the
  `" (⚠ STALE — agent moved on)"` suffix when `compute_shadow_staleness` says so.
- **`c` → `action_pick_concerns`:** resolve the selected agent's shadow, run the
  authoritative `capture_shadow_text` (`-J`, `--deep`), `parse_concerns`, the
  `block_head_truncated` → `_SHADOW_DEEP_RETRY_LINES` deep-retry, then
  `push_screen(ConcernPickerModal(concerns, narrow=False, stale=...))` and on
  confirm `build_clipboard_payload` → **`tui_clipboard.copy_to_system_clipboard`**
  (never `app.copy_to_clipboard`; `tests/test_tui_clipboard_seam.sh` enforces
  this and `monitor_app.py` has no clipboard usage today). `narrow=False` because
  the monitor is full-width, unlike minimonitor.
- Bind `c` (free in monitor). It is only active in `PANE_LIST` — in
  `PREVIEW`/`SHADOW` keys are forwarded to tmux, which is correct.
- Docs: monitor `reference.md` keybinding table + a "Picking shadow concerns"
  section in `how-to.md`, mirroring the minimonitor pages.

**Tests** — new `tests/test_monitor_concern_action.py` following
`test_minimonitor_concern_action.py`'s `__new__` + spy-lambda harness: modal
pushed with the parsed concerns; **nothing on the clipboard before confirm**;
cancel writes nothing; deep-retry on head-truncation; toast fires once per
signature and **only for the selected agent**; badge appears for a
non-selected agent that has fresh concerns (the N-agent case minimonitor cannot
cover); no-shadow and no-block negative controls; a test asserting the per-tick
path spawns **no** subprocess; **one test per row of the badge-lifecycle
table** above — in particular the three capture-failure negative controls
(capture returns `None`, parse yields zero concerns, still head-truncated after
the deep retry) each asserting `_concern_sig_offered` is **untouched** and the
badge still renders, plus the scroll-out/scroll-back no-re-toast case, eviction
on shadow loss, and a test that a shadow which emitted a *newer* block between
badge and keypress stores the captured signature (so the newer block is not
left permanently un-offered); and the narrow-pane fallback firing for the
selected agent only, throttled, with a negative control that a wide shadow pane
never triggers it.

### t1216_4 — Port shadow spawn (`e` / `E`)

- Lift `_spawn_shadow` (minimonitor L1191-1271) to a shared helper taking
  `companion_pane` as an **explicit parameter**. It currently reads
  `os.environ["TMUX_PANE"]` at L1262 meaning *"minimonitor's own pane"*; if the
  monitor passed its own `TMUX_PANE`, `aitask_companion_cleanup.sh` job 2 would
  **kill the monitor's pane** when the agent's window runs out of real agents.
  The monitor must pass `companion_pane = shadow_pane` (the fallback minimonitor
  already uses when `TMUX_PANE` is unset), which is safe: job 1 kills the bound
  shadow by `@aitask_shadow_target` regardless, and job 2's `kill-pane` on an
  already-dead pane is a no-op.
- Collapse the verbatim `_load_project_tmux_config` duplication
  (minimonitor L1695 / monitor_app L1993) into the shared module.
- `action_launch_shadow` (`e`) and `action_launch_shadow_pick` (`E`) on
  `MonitorApp`, acting on the **selected** agent (`self._focused_pane_id` →
  `_snapshots`), with the same pre-dialog duplicate guard using the **sync**
  reader.
- Docs: monitor `reference.md` + `how-to.md`; add the monitor as a spawn surface
  in `website/content/docs/workflows/shadow-agent.md` and the "Spawn path and
  binding" section of `aidocs/framework/shadow_agent.md`, which both currently
  say the shadow is launched from minimonitor.

**Tests** — new `tests/test_monitor_shadow_pick.py` mirroring
`test_minimonitor_shadow_pick.py`: binding registration for `e`/`E`; duplicate
guard fires **before** the dialog opens; `AgentCommandScreen` contract
(`operation="shadow"`, `operation_args`, prompt string); the confirm path uses
`screen.full_command`, stamps `SHADOW_TARGET_OPTION` exactly once, and — the new
assertion — calls `attach_shadow_cleanup_hook` with the **shadow** pane as
companion, with a negative control proving the monitor's own `TMUX_PANE` is
never passed.

### t1216_5 — Aggregate manual verification

Live checklist over all four children in a real tmux session: shadow preview
renders unwrapped at the real pane width, `Tab` targeting is unambiguous, keys
land in the right pane, badge/toast fire correctly with several agents, `c`
forwards to the clipboard, `e`/`E` spawn correctly and the shadow dies with its
agent while the monitor survives.

---

## Cross-cutting rules for every child

- `bash tests/test_no_raw_tmux.sh` must pass — all tmux goes through
  `TmuxClient` / `monitor.tmux_run*`. (`tests/` itself is not scanned.)
- Shadow work stays off the Textual event loop — use `TmuxMonitor._run_offloaded`
  (L1009), the t1111 offload seam.
- Run `bash tests/run_all_python_tests.sh` plus `tests/test_tui_clipboard_seam.sh`.
- No skill/`.j2` surfaces are touched, so no goldens regeneration and no
  cross-agent port task is needed.

## Verification

```bash
bash tests/test_no_raw_tmux.sh
bash tests/test_tui_clipboard_seam.sh
bash tests/run_all_python_tests.sh
```

Then, **from a shell outside the main aitasks tmux session** (see
`aidocs/framework/tui_conventions.md` — monitor work can destructively touch
tmux): start `ait ide`, launch two agents, spawn a shadow on one with `e`, and
walk the t1216_5 checklist.

## Risk

### Code-health risk: medium

- The zone model, `on_key`, and `check_action` in `monitor_app.py` are
  load-bearing for *all* monitor interaction; a mistake in the `SHADOW` branch
  can swallow or misroute every keystroke. · severity: high · → mitigation:
  t1216_2's key-routing tests plus its discovery-drop negative control
- t1216_1 rewires a **working** minimonitor feature onto lifted code, so a
  silent behavioural drift would regress shadow use in minimonitor while the
  monitor work looks fine. · severity: medium · → mitigation: the existing
  minimonitor/shadow suite must pass unmodified against the lifted code
  (t1216_1's characterization net)
- Adding a third strictness tier to `concern_parser` risks the trigger being
  mistaken for a parse path and used to build forwardable concerns from
  wrap-split text. · severity: medium · → mitigation: trigger-only contract
  stated in the module docstring's strictness table, with t1216_1 test coverage
  pinning that wrap-split input never yields forwardable concerns
- A second sub-second ticker sharing `TmuxMonitor`'s single global capture
  generation would widen the existing supersession window and let a
  single-shadow write clobber the wholesale-rebuilt `_shadow_snapshots` map.
  · severity: high · → mitigation: the three binding rules in "Shadow snapshot
  concurrency contract" (separate generation, stamped per-key merge,
  delete-only-from-discovery) with interleaving tests in both orders and a
  negative control that the shadow path never bumps `capture_generation`
- Blast radius is four modules plus five test files, but each child is
  independently testable and the discovery-drop invariant already has an
  enforcing test. · severity: low · → mitigation: none needed

### Goal-achievement risk: medium

- The side-by-side layout is unproven at real terminal widths: a 60-column
  shadow column may leave the agent preview too narrow to be useful, and the
  narrow-fallback threshold is a guess. Only live use will tell. · severity:
  medium · → mitigation: t1216_5's live manual verification is the deciding
  surface; accepted as a tune-after-shipping risk
- The cheap `concern_block_signature` trigger is a new detector; if sentinels do
  wrap at some pane width, badges silently never appear — a failure that is
  invisible rather than loud. · severity: medium · → mitigation: the digest is
  defined reflow-stable (ANSI-stripped, whitespace normalised to single spaces)
  and pinned as a stable-**and**-discriminating property across several widths;
  its one residual (mid-word wrap) is chosen to fail as a spurious re-offer
  rather than a miss, and pinned by its own test; the sub-24-column case where
  the sentinel itself wraps has an explicit, throttled authoritative fallback
  rather than silent absence; t1216_5 exercises it live with several agents
- Everything else (preview render, key forwarding, picker modal, spawn) is
  reuse of code already proven in production, so approach soundness is high.
  · severity: low · → mitigation: none needed

**Mitigation follow-up tasks:** none — reviewed with the user and declined; the
decomposition already carries the mitigating work (per-child tests, t1216_1's
characterization net, t1216_2's negative control, t1216_5's live verification).
