---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [trails, tui, board]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-10-05 23:14
updated_at: 2026-10-06 09:24
---

## Goal

`ait trails` (`.aitask-scripts/board/trails_app.py`) shows one trail at a time.
To look at another trail, `s` rescans everything and then activates the new
trail, which throws away the old trail's in-memory state. Instead, keep several
**explicitly opened** trails in memory, each in its own tab, and make switching
between them instant.

## Findings (exploration)

- **Discovery already loads every trail document.** `discover_trails()`
  (`.aitask-scripts/lib/trail_discovery.py`) scans the task frontmatter and then
  calls `load_trail_blob()` for every trail. That is one `ait artifact get`
  subprocess per trail, each with a 15s timeout. The results are cached in
  `TrailScreenMixin._trail_infos`, and each cached `TrailInfo` carries its `doc`.
- **The slow switch is self-inflicted.** `action_trail_select` (`s`) calls
  `_open_trail_select(rescan=True)` every time, so the cache is never used for
  selection. `_on_trail_reload` (`d`) also sets `_trail_infos = None`.
- **What a switch loses today.** `_activate_trail` resets the drift verdict and
  re-runs drift (subprocess), stops the artifact-version watch (`_stop_trail_watch`)
  even when an agent refresh for the old trail is still running, and drops the
  focus position.
- **All trail state is single-trail.** About 15 scalar fields are set in
  `TrailScreenMixin._init_trail_state()` (`board_trail_screen.py`):
  `active_trail_handle`, `_trail_doc`, `_trail_error`,
  `_trail_versions_fallback`, `_trail_drift`, `_trail_owner_id`,
  `_trail_owner_archived`, `_trail_gen`, `_trail_watch_*` and
  `_trail_launch_pending`. The mixin is **shared with the board's embedded `z`
  view** (`KanbanApp` in `aitask_board.py`). Roughly 40 test references read
  these fields (`tests/test_trails_app.py`, `test_board_bytrail_view.py`,
  `test_board_trail_view.py`, `test_trail_screen_host_protocol.py`,
  `tests/lib/board_fixture.py`, `tests/perf/trails_pilot_bench.py`).
- **Trail cards and lanes set no DOM ids**, so several trails' widgets would not
  collide. However, nav and focus code in `trails_app.py` uses global
  `query(TaskCard)` / `query(TrailColumn)` lookups.

## Design (draft, Option B, recommended)

```
┌ aitasks trails ─────────────── gate-framework · ✓ fresh ┐
│ [1 gate-framework ✓] [2 testmap ⟳] [3 applink ⚠ •]       │  ← textual `Tabs`, can_focus=False
├──────────────────────────────────────────────────────────┤
│ Wave 1        │ Wave 2        │ Wave 3        │ …         │  ← #board_container (unchanged)
├──────────────────────────────────────────────────────────┤
│ summary pane (follows the active tab)                     │
│ [/] tab  ^w close  s open trail  r d R v T  ? j q         │
└──────────────────────────────────────────────────────────┘
```

1. **Tabs only for explicitly opened trails.** Discovery fills the selector list
   and never creates a tab. On boot with no tabs, keep today's behaviour: open
   the selector, and show the empty-state hint if it is cancelled.
2. **Cache-first selector.** `s` opens `TrailSelectScreen` from `_trail_infos`
   and runs discovery only when the cache is empty. A new `r` binding inside the
   selector rescans. Rows for trails that are already open show `● open`.
   Picking an open trail switches to its tab. Picking any other trail opens a
   new tab and makes it active.
3. **Per-trail state object.** Add a `TrailSession` dataclass (handle, doc,
   error, versions_fallback, drift, owner_id, owner_archived, gen, last focused
   filename and column, dirty flag). The mixin holds `_trail_sessions:
   dict[handle, TrailSession]` plus the active handle. Turn the existing scalar
   fields into **properties that delegate to the active session**, so that the
   board's `z` view (always one session, no tab strip) and the existing tests
   keep working unchanged. The discovery supersession token is split from the
   per-session `gen`.
4. **Callbacks keyed by handle, not by "active".** The drift, reload and watch
   callbacks write into the session whose handle matches, validated against
   that session's `gen`. They re-render only if that session is the active tab.
   Otherwise they set the tab's `•` (updated) marker. Switching tabs must
   **no longer stop** a pending agent-refresh watch. The watch belongs to its
   handle, and closing that handle's tab is what stops it. `_on_trail_reload`
   updates the matching cached `TrailInfo` in place instead of discarding the
   whole cache.
5. **Tab switching is in-memory only.** Store the current focus into the
   outgoing session, swap the active handle, run `_rerender_trail` (zero
   subprocesses), and refocus the incoming session's last card. Do not re-run
   drift on a switch. The drift result is cached per session, and `d` still
   re-checks it explicitly.
6. **Keys (trails app only, declared under the `board` shortcut scope).** `[` /
   `]` move to the previous/next tab, `1`–`9` jump to a tab, and `ctrl+w`
   closes the active tab. These are free in the board scope, where `x`, `w`, `X`
   and `tab` are already taken. Closing the last tab returns to the empty
   state. Gate the bindings in `check_action` (hidden when no tabs are open)
   and with a guard inside each action method.
7. **Tab labels.** Show the index, the trail title (truncated), and a drift
   glyph (`✓` / `⚠` / `⟳` while checking), plus `•` for a background update.
   Tab ids are generated (for example `trail_tab_<n>`) and mapped to handles,
   because handles such as `art:…` are not valid widget ids. Clicking a tab
   (`Tabs.TabActivated`) switches to it.

**Alternative (Option A):** `TabbedContent` with one `TabPane` per trail. It
keeps each tab's scroll position for free, but hidden panes stay in the DOM.
That means every `query(TaskCard)` / `query(TrailColumn)` in
`trails_app.py` (`_first_card`, `_column_cards`, `_columns`, `_refocus`,
`apply_filter`) and the `#board_container` / `#trail_summary` lookups in the
mixin would have to be scoped to the active pane. Rejected for the draft
because of the extra churn. Reconsider it if per-tab horizontal scroll turns
out to matter.

## Scope / out of scope

- In scope: `trails_app.py`, `board_trail_screen.py` (state refactor),
  `board_trail_view.py` (`TrailSelectScreen` open-marker and rescan key), and
  tests.
- The board's `z` view stays single-trail, with no tab strip. It must not
  regress. Only its `s` behaviour may become cache-first, if that is shared
  code. Decide this explicitly and pin it with a test.
- Open tabs are session-only and never persisted, which matches the existing
  "session-only, never persisted" rule for trail view state (t1210_4).
  Restoring tabs across restarts is a possible follow-up.
- Shortcut ownership (C10): the new tab bindings are trails-only rows. Make
  sure the `?` shortcut editor and the keybinding registry lint accept them
  under the `board` scope without colliding with board rows.

## Verification

- Pilot tests (`App.run_test`): open two trails and switch with `[` / `]` / `2`.
  Assert that no subprocess runs on a switch (patch `load_trail_blob`,
  `run_trail_drift` and `discover_trails` and count calls), that focus is
  restored, and that the subtitle and summary follow the active tab.
- Choosing an already-open trail from the selector switches to it and does not
  open a duplicate tab.
- A drift or watch callback for a background tab updates only that session,
  marks the tab `•`, and does not re-render the active tab.
- A watch survives a tab switch, and closing its tab stops it.
- Closing the last tab shows the empty-state hint.
- Existing suites stay green: `tests/test_trails_app.py`,
  `test_board_bytrail_view.py`, `test_board_trail_view.py`,
  `test_trail_screen_host_protocol.py` and the keymap characterization test.
- Read `aidocs/framework/tui_conventions.md` and
  `aidocs/framework/testing_conventions.md` (`@work` workers under
  `run_test`) before implementing.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-06T06:24:13Z status=pass attempt=1 type=human
