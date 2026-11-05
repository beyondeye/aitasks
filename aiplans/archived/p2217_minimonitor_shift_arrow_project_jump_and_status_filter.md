---
Task: t2217_minimonitor_shift_arrow_project_jump_and_status_filter.md
Base branch: main
Output branch: main
---

# t2217 — minimonitor: shift+↑/↓ project jump, shift+←/→ status filter

## Context

`ait minimonitor` lists every agent across projects (one tmux session per
project, separated by `── <session> ──` dividers in multi-session mode). With
many agents there is no fast way to reach another project's group, and no way
to narrow the list to the agents in a given workflow phase. This adds two
shift+arrow pairs, a one-row filter indicator in the top chrome, and documents
both in the key band, the `H` help modal and the website how-to. Behaviour
decisions come from the task body (exploration); open choices are resolved
below.

## Decisions (resolving the task's open points)

- **Project jump scope: agent section only.** OTHER-section dividers are not
  jump targets (they group non-agent panes; the task recommends this).
- **Jump target row: the group's divider sits at the top of the list**, so the
  project name is visible; the group's first card (directly below it) is
  focused. (The task says "first card at the top"; the divider is the group's
  1-row heading. Easy to flip to the card's own `y` if preferred.)
- **True no-op when the list fits** (`max_scroll_y <= 0`), when fewer than 2
  agent groups exist (single-session mode), and when the list holds no cards.
  No focus move in those cases.
- **No explicit `unknown` stop** in the filter cycle — the cycle stays as
  specified: `all → PLAN → IMPLEMENT → POSTIMPL → parked → frozen → all`.
- **`parked` vs `frozen` are exclusive by displayed state**: frozen wins (the
  card renders `frozen` when both are true), so `frozen` = `s.frozen`,
  `parked` = `s.parked and not s.frozen`.
- **Key display for arrow chords**: `shift+up` renders `⇧↑` (arrow bases →
  `↑↓←→`, a lone `shift` on an arrow → `⇧`); a segment whose keys all share
  the `⇧` prefix with single-glyph bases joins compactly (`⇧↑↓`, `⇧←→`),
  otherwise the generic `/` join. All other keys render exactly as today.
- Session-bar mirror of the filter and surfacing the `P` state: **not done**
  (optional in the task); the indicator never contradicts `P` (phase filters
  exclude parked/frozen anyway; parked/frozen filters override `P`).
- Full-monitor parity: out of scope → offered as a follow-up.

## Implementation steps

### Pre-phase (risk mitigations)
- **measure_band_baseline** — before editing, render the app at widths
  15/18/22/40 (height 30, the `test_minimonitor_top_chrome_render` fixture) and
  record `#mini-key-hints` region heights (expected 28/22/19/10) so the after
  numbers are compared against a measured baseline, not the comment table.

### 1. `monitor/minimonitor_keys.py`
- `key_display`: map arrow bases `up/down/left/right` → `↑/↓/←/→`; when the only
  modifier is `shift` and the base is an arrow, render `⇧<glyph>`. Docstring
  updated. Everything else unchanged (`shift+tab`, `ctrl+…` still match Textual).
- New `join_keys(displays)` used by `_render_seg`, `render_collapsed` and
  `help_entry_keys`: if ≥2 displays all start with `⇧` and each remainder is one
  cell → `⇧` + remainders; else `"/".join`.
- `FULL_HINT_LINES`: add `HintSeg(("jump_project_prev","jump_project_next"),
  "project")` and `HintSeg(("filter_prev","filter_next"), "filter")` — placed by
  MEASUREMENT so width 40 stays 10 rows (≤38 cells/line) and (15, 30) stays ≤ 29.
  Starting candidates: `⇧↑↓:project` after `enter:send` on the `s/↑↓` line
  (36 cells), `⇧←→:filter` on the `d:detect` line (32 cells). Expected cost at
  width 15: +2 rows → pay one back by shortening `mark ★ (followed agent)` to
  `mark ★ (followed)` (same idiom as `info (followed)`; saves a wrapped row at
  width 15). Re-measure 15/18/22/40, update the comment's measurement table and
  history bullets.
- `KEY_HELP`: two entries (`jump_project_prev`+`next` as one entry → actions
  tuple of both; same for filter), each with a `# Source:` comment pointing at
  the new how-to sections; placed in band order.

### 2. `monitor/minimonitor_app.py`
- **BINDINGS**: `Binding("shift+up","jump_project_prev","Previous project")`,
  `("shift+down","jump_project_next","Next project")`,
  `("shift+left","filter_prev","Previous filter")`,
  `("shift+right","filter_next","Next filter")`, all `show=False`, with a
  comment (action ids are persisted override keys).
- **State**: module constant `_STATUS_FILTERS = ("all","PLAN","IMPLEMENT",
  "POSTIMPL","parked","frozen")`; class attribute `_status_filter = "all"`
  (class-level default because tests build the app with `__new__`), in-memory
  only.
- **Filter actions** `action_filter_next/prev` → `_cycle_status_filter(±1)`:
  index wraps both ways; `notify(f"Filter: {label}")`; `_set_filter_banner()`;
  sets `_filter_nav_target = <new filter>`; `call_later(self._refresh_data)`.
- **A filter change is navigation, not a passive refresh** (review finding,
  verified): the passive path would capture an anchor that cannot survive a
  disjoint result set → `_restore_list_scroll` falls back to `max_scroll_y`
  while `_restore_focus` focuses card 0 with `scroll_visible=False` (off-screen),
  and an armed bottom pin carries the old view's position into the new results.
  So in `_refresh_data`'s list step:
  - `_build_list_entries` records the filter it built with
    (`_entries_filter`). The nav is consumed **only if**
    `_filter_nav_target == _entries_filter` — an in-flight tick that built
    entries under the OLD filter never consumes it, and the next tick does
    (both completion orders; newest filter wins because a second press
    overwrites the target).
  - When consumed: `_abandon_scroll_restore()` (retire any restore pending from
    an earlier tick), `container.release_anchor()` (clears the pin and its
    suspension, before the rebuild so the compositor cannot reassert the
    bottom), then take the existing lock/gen/fail-safe-timer acquisition, force
    the full rebuild (skip `_capture_list_scroll`), focus the FIRST card of the
    new list with `scroll_visible=False` and set `_focused_pane_id` (cleared to
    `None` on an empty result), and schedule
    `_finish_filter_navigation(gen, 0)` instead of `_restore_list_scroll`.
  - `_finish_filter_navigation(gen, attempt)`: same superseded-gen guard and
    `list_layout_pending` readiness retry as the restore; target = `0` if the
    first card's `virtual_region.bottom` fits the viewport, else the card's
    own `y`; `scroll_to(y=target, animate=False, immediate=True, force=True)`;
    then stop the timer and release the lock after one more refresh (mirrors
    `_restore_list_scroll`'s finally block).
- **One phase per tick**: new `_live_phase(snap)` → `PhaseSignal | None`
  (task id → info → `_phase_for_snap`), the exact lookup `_agent_card_text`
  does today. `_agent_card_text(snap, phase=_UNSET)` takes an optional
  precomputed phase; `_UNSET` keeps today's behaviour for direct callers/tests.
- **`_build_list_entries`**: for each AGENT snap (own pane still excluded):
  - filter `parked` → keep only `parked and not frozen`; `frozen` → only
    `frozen`; both ignore `_hide_inactive` (explicit filter wins);
  - filter `all` → today's `P` rule;
  - phase filter → skip parked/frozen; compute `_live_phase` once, keep when
    `phase is not None and phase.phase == filter`;
  - live agents get their phase computed once in a `{pane_id: phase}` map;
    `append_group` passes it to `_agent_card_text` (so `all` costs exactly what
    it does now).
  - OTHER section omitted when the filter is not `all`.
- **Filter indicator**: `yield Static("", id="mini-filter-status")` after
  `#mini-loop-status` (adjacent to the list it describes); add to `_TOP_CHROME`;
  `_FILTER_STATUS_ROWS = 1` added to `_MAX_CHROME_ROWS`; CSS `display: none;
  height: 1; text-wrap: nowrap; text-overflow: ellipsis; background: $panel;
  text-style: bold; padding: 0 1` + stylesheet comment updated (compose order,
  five collapsible widgets). `_filter_banner_text()` (DOM-free seam) →
  `Content(f"filter: {label}  {keys}")` with keys = `join_keys` of the ACTIVE
  `filter_prev`/`filter_next` keys from `_active_keymap()` (never
  `resolve_key`); `""` for `all`. `_set_filter_banner()` updates + toggles
  `display`, then `_schedule_short_mode_refresh()`; suppressed like the other
  banner setters for `__new__` stubs.
- **Project jump** `action_jump_project_next/prev` → `_jump_project(±1)`:
  1. `container = query_one("#mini-pane-list")`; return if
     `container.max_scroll_y <= 0`.
  2. Walk `container.children` in order up to the first `.mini-section-header`
     (OTHER section): each `.mini-session-divider` starts a group; cards append
     to the current group. Return if < 2 groups or no cards.
  3. Current group = the one holding `self.focused` (a `MiniPaneCard`), else the
     last group whose divider `virtual_region.y <= container.scroll_y`, else 0.
  4. Target = `(cur + dir) % n`.
  5. `container.scroll_to(y=divider.virtual_region.y, animate=False)` —
     non-forced, so it goes through `MiniPaneList._scroll_to`, which retires any
     pending restore (`_abandon_scroll_restore`) and releases the bottom pin,
     exactly like a wheel gesture; never `scroll_to_region` (would be refused
     as uninvited under the lock) and never `force=True`.
  6. `first_card.focus(scroll_visible=False)`; set `_focused_pane_id`.
  Docstring cites the MiniPaneList seams (t1539/t1653).

### 3. Website `website/content/docs/tuis/minimonitor/how-to.md`
- New sections "How to Jump Between Projects" (after "How to Toggle the
  Multi-Session View") and "How to Filter the List by Phase or State" (near the
  `P` text, describing the cycle, wrap, `P` interaction, OTHER hidden, the
  indicator, in-memory, advisory phase).
- "How to Navigate the Agent List": mention both.
- Quick Reference rows: `Shift+Up` / `Shift+Down`, `Shift+Left` / `Shift+Right`.
- `_index.md`: check whether it lists keys; update if so.
- Run `python3 website/check_links.py --build` (and `hugo build` via it).

### 4. Tests
- `tests/test_minimonitor_key_hints_modes.py`: parity tests pick the new
  actions up automatically; update `test_default_keys_render_as_their_names`
  with an explicit table for the four arrow chords (`⇧↑` …); add `key_display`
  cases for `up`, `shift+up`, `ctrl+up` (stays `^↑`-style rule) and a
  `join_keys` test (compact join; falls back to `/` for a rebind like `alt+x`).
- `tests/test_minimonitor_top_chrome_render.py`: add `#mini-filter-status` to
  `CHROME_IDS`; `_populate(banners=True)` also activates a filter so the
  worst-case chrome includes it; update the `_MAX_CHROME_ROWS` arithmetic test
  and the FLOOR comment (11 → 12). Floor/narrow sweeps re-run as-is.
- New `tests/test_minimonitor_status_filter.py` (unittest; `run_test` app with
  synthetic snapshots like the existing parked-filter tests):
  cycle + wrap both ways (shift+← from `all` → `frozen`); each phase filter
  shows only matching live agents (phases stubbed via `_phase_for_snap`);
  UNKNOWN/no-task agents excluded; `parked`/`frozen` filters show those rows even
  with `P` hiding; OTHER section hidden under a filter; indicator hidden at
  `all`, visible with label otherwise, and shows a REBOUND key (override via
  composed BINDINGS); phase computed once per agent per build (call count on
  `_phase_for_snap`).
  **Filter-transition tests (review finding)** — two DISJOINT result sets, each
  overflowing the viewport (PLAN agents vs IMPLEMENT agents):
  (a) scroll the PLAN view to its end, press shift+→ → after settle the focused
  card is the first IMPLEMENT card, its region lies inside the viewport,
  `scroll_y` is at the top, no restore pending, lock released;
  (b) same from a bottom-PINNED PLAN view → additionally `is_bottom_pinned` is
  False after the change;
  (c) consumption rule: a tick whose entries were built under the old filter
  does not consume `_filter_nav_target`; the next tick does;
  (d) **negative control**: with the navigation path patched out (passive
  restore only) case (a) reproduces the defect (focused card outside the
  viewport), proving the test discriminates.
- New `tests/test_minimonitor_project_jump.py` (`run_test`, multi-session
  snapshots in 3 sessions, pane small enough to scroll): shift+↓ puts the next
  divider at `scroll_y` and focuses its first card; wrap last→first and
  first→last; current group from focus and from viewport when unfocused;
  no-op when the list fits (scroll and focus unchanged); no-op in
  single-session mode; **a jump while a restore is pending retires it** (set
  `_pending_scroll_state`/lock, press, assert generation bumped and the late
  `_restore_list_scroll` does not move the offset); a pinned list is unpinned.
- Re-run: `tests/test_minimonitor_*.py`, `tests/test_monitor_parked_filter.py`,
  `tests/test_monitor_frozen_filter.py`, `tests/test_shortcut_overrides_survive.py`,
  `tests/test_minimonitor_gate_phase_row.py`, then
  `bash tests/run_all_python_tests.sh` (read the final verdict line).

### Post-phase (risk mitigations)
- **jump_restore_regression_test** — the "jump during a pending restore" and
  "pinned list unpins" cases in `test_minimonitor_project_jump.py` above, plus a
  mutant control: with the jump forced through `force=True` the pending-restore
  case must fail (proves the test discriminates).

## Verification
- Unit/render tests above all PASS; full Python suite verdict
  `PYTHON SUITE: PASSED`.
- Band measurements at 15/18/22/40 recorded in the `FULL_HINT_LINES` comment;
  40-col band still 10 rows; (15, 30) ≤ 29.
- `python3 website/check_links.py --build` clean.
- Manual (offered as Step 8c follow-up): in a real tmux minimonitor with ≥3
  projects, shift+↑/↓ jumps and wraps, shift+←/→ cycles and the indicator shows.

## Step 9 reference
Post-implementation: commit code (`feature: … (t2217)`) and plan separately,
gate run, archival via `aitask_archive.sh 2217` (Step 9 of task-workflow).

## Risk

### Code-health risk: medium
- The jump writes the list's scroll offset, which the t1539 restore anchor and t1653 bottom pin also own; a wrong scroll call could be overwritten by a pending restore or misclassified · severity: medium · → mitigation: inline post-phase jump_restore_regression_test
- The key band and top chrome have tight, test-pinned row budgets (10 rows at 40 cols, ≤29 at (15,30), chrome floor); new segments and a new chrome row could push the list off-screen at narrow/short panes · severity: medium · → mitigation: inline pre-phase measure_band_baseline
- Threading a precomputed phase into `_agent_card_text` could change card text for existing callers · severity: low · → mitigation: TBD (covered by the optional-parameter design and existing gate_phase_row tests)
- A filter change swaps the whole result set; left to the passive restore it would scroll to `max_scroll_y` / keep the pin and focus an off-screen card (review finding, verified against `_restore_list_scroll` / `_restore_focus`) · severity: medium · → mitigation: addressed in the design (filter change = navigation: retire restore, release pin, focus first result, scroll it into view) + filter-transition tests with a negative control

### Goal-achievement risk: low
- shift+arrows must reach Textual as `shift+up` etc. through tmux; the pilot tests prove dispatch, not real terminal delivery · severity: low · → mitigation: TBD (manual check offered at Step 8c)

_Reassessed after inlining both mitigations: code-health stays medium (the
budgets and scroll seams remain the load-bearing surfaces, now guarded by
measurement and tests); goal-achievement stays low._

### Planned mitigations
- timing: pre-phase | name: measure_band_baseline | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: key band / chrome row budget | desc: Measure #mini-key-hints heights at widths 15/18/22/40 before editing and compare after
- timing: post-phase | name: jump_restore_regression_test | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: jump vs scroll restore / bottom pin | desc: Regression tests for jump-during-pending-restore and pin release, with a force=True mutant control

## Implementation progress

- [x] Pre-phase `measure_band_baseline`: measured `#mini-key-hints` (short class
  removed) at width 15/18/22/40, height 30 → 28/22/19/10 (matches the table).
- [x] `minimonitor_keys.py`: arrow glyphs + `⇧` for lone shift; `join_keys`;
  `⇧↑↓:project` / `⇧←→:filter` segments; "mark ★ (followed)"; two help
  entries. Re-measured: 29/23/21/10 (≤ 29 at width 15, 10 rows at 40).
- [x] `minimonitor_app.py`: bindings, filter state + cycle, filter-as-navigation
  (`_consume_filter_navigation`, `_navigate_list_after_filter`,
  `_finish_filter_navigation`, one-shot `_maybe_retick_for_filter`), one phase per
  tick, `#mini-filter-status` chrome row, project jump.
- [x] Website how-to + `_index.md`; `check_links.py --build` SWEEP: PASSED.
- [x] Tests (one new module `tests/test_minimonitor_filter_and_jump.py`, 24 cases)
  + updated chrome/key-hint/own-mark/concern-action tests.
- [x] Post-phase `jump_restore_regression_test`: in the new module, with the
  `force=True` negative control.

## Post-Review Changes

### Change Request 1 (2026-11-05 16:00)
- **Requested by user:** review finding (low, efficiency) — `_live_phase` resolved task info for the filter and `_agent_card_text` resolved it again, so each displayed live task cost two `get_task_info` calls (each a file-identity `os.stat` even on a cache hit) per refresh.
- **Changes made:** verified (one stat per `TaskInfoCache.get_task_info` call). `_live_phase` became `_live_task_phase` returning `(info, phase)`; the build-scoped `_build_phases` map now carries that pair and the card text reuses both. New test `test_task_info_is_resolved_once_per_live_agent_per_build` (mutant control: map disabled ⇒ fails).
- **Files affected:** .aitask-scripts/monitor/minimonitor_app.py, tests/test_minimonitor_filter_and_jump.py

## Final Implementation Notes
- **Actual work done:** shift+↑/↓ project jump (agent-section session groups, divider scrolled to the top, first card focused, wraps, true no-op when the list fits / <2 groups) and shift+←/→ status/phase filter (`all → PLAN → IMPLEMENT → POSTIMPL → parked → frozen`, wraps both ways; explicit parked/frozen stops override `P`; OTHER hidden under any filter; in-memory only). One-row `#mini-filter-status` chrome line (`filter: IMPLEMENT  ⇧←→`, active keys from composed BINDINGS) added to `_TOP_CHROME` / `_MAX_CHROME_ROWS`. Key band + `H` help entries; `key_display` renders arrows as glyphs and a lone shift on an arrow as `⇧`; `join_keys` folds `⇧↑`+`⇧↓` → `⇧↑↓`. Website how-to (two sections, quick-reference rows, navigation bullets) and `_index.md` comparison rows.
- **Deviations from plan:** (1) A filter change is handled as navigation (plan revision after review): `_consume_filter_navigation` (consumed only by a tick whose entries were built under the target filter), `_navigate_list_after_filter` (retire pending restore, release pin, forced rebuild, focus first result), `_finish_filter_navigation` (readiness retry, scroll to 0 or to the card's own row when divider+card do not fit). (2) Added a one-shot `_maybe_retick_for_filter` so a keypress landing during an in-flight tick does not lag a full interval. (3) The precomputed phase travels through a build-scoped `_build_phases` map instead of an `_agent_card_text` parameter — test hosts override that method with the one-argument signature. Post-review it carries `(info, phase)` so the card reuses the task info too (one task-file stat per agent per tick). (4) Tests live in ONE module, `tests/test_minimonitor_filter_and_jump.py` (shared host fixture), not two.
- **Issues encountered:** (a) Band budget: at width 15 the two new segments cost two wrapped rows; paid one back with "mark ★ (followed)" → 29 rows, exactly at the ≤29 budget (measured 28/22/19/10 → 29/23/21/10 at widths 15/18/22/40). (b) `test_minimonitor_top_chrome_render.py` failed deterministically only when run after the key-hints module: the extra chrome row made the first, pre-short-mode frame overflow at width 22 (12 + 21 > 30); production settles next frame, so the fixture now waits one more frame (documented). (c) The full-suite run flaked once in `test_sitrep_window.py::test_booting_companion_without_a_marker_does_not_match` (subprocess cmdline race under load; passes alone on both the working tree and a clean HEAD export; unrelated to minimonitor). (d) Existing audits updated: concern-action's every-binding audit now matches per rendered segment; own-mark asserts "mark ★ (followed)"; the default-key-name test has an explicit arrow-chord table.
- **Key decisions:** jump scope = agent section only; jump target row = the group's divider (keeps the project name visible); parked/frozen stops exclusive by displayed state (frozen wins); no `unknown` filter stop; no session-bar mirror and no `P` indicator; full-monitor parity left out of scope.
- **Upstream defects identified:** tests/test_sitrep_window.py:169 — `test_booting_companion_without_a_marker_does_not_match` classifies a just-`Popen`ed process by its cmdline and fails intermittently under a loaded parallel suite (cmdline not yet exec'd); observed once in this session's full run, passes in isolation.
