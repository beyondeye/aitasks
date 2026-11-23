---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [sitrep, tui_switcher, minimonitor, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2175
implemented_with: claudecode/opus5_5
created_at: 2026-11-19 15:33
updated_at: 2026-11-22 17:51
---

# Sitrep: a TUI-switcher row (open/switch like other TUIs) + minimonitor hint on the switcher line

## Request (user)

Today the sitrep window (sitrep agent + sitrep TUI + minimonitor companion) is
in practice opened from the minimonitor (`S`). It would make more sense to
open it, or switch to it, from the **TUI switcher like the other TUIs**. Also,
in the minimonitor's shortcut list, `S:sitrep` should sit **on the same line as
`j:switcher` and `m:monitor`**.

## Current state (explored 2026-11-19, upstream HEAD c443f811e)

- **Switcher already has a hidden `S`**: `lib/tui_switcher.py:488`
  `Binding("S", "shortcut_sitrep", "Sitrep", show=False)` (t2175_5);
  `action_shortcut_sitrep` (~1340) → `_dispatch_sitrep_open` →
  `_open_sitrep_async` (~1771) runs `aitask_sitrep.sh open --root <selected
  root> --session <selected session>` (45 s timeout, toast). But sitrep has
  **no list row**: not in `lib/tui_registry.py` `TUI_REGISTRY`, not in
  `_TUI_SHORTCUTS` (no `(S)` row hint), not in `_HINT_ITEMS` (row is ~122 cols,
  over budget — keep it out unless measured). Today the `agent-sitrep` window
  only appears under "Code Agents" (`_classify_window` ~373, `agent-` prefix).
- **Minimonitor**: `monitor/minimonitor_app.py:1511` `Binding("S",
  "open_sitrep", ...)`, handler in `monitor/sitrep_close.py` `SitrepCloseMixin`
  (`action_open_sitrep` ~655). Hint band = `FULL_HINT_LINES` in
  `monitor/minimonitor_keys.py:106-155`; switcher/monitor line at 126-129;
  `S:sitrep` currently on the 9th line (150) with loop/keys/multi.
- **Sitrep launch is already idempotent focus-or-spawn**: `aitask_sitrep.sh
  open` → `monitor/sitrep_open.py` → `monitor_core.spawn_sitrep` (~5504); one
  window per canonical repo root, found by pane stamps
  (`@aitask_sitrep_root`, `@aitask_sitrep_tui_root`) under a per-server lock;
  window name `agent-sitrep[-n]` (`SITREP_WINDOW_BASE`/`SITREP_WINDOW_RE`,
  `lib/sitrep_harvest.py:227-228`); repairs a missing role
  (added_tui / respawned_agent) rather than just focusing.

## Design constraints (why not a plain registry row)

- A plain `("sitrep", "Sitrep", "ait sitrep", True)` registry entry is wrong:
  `TUI_NAMES` feeds `monitor_core.spawn_tui` (~4495, runs `ait {name}` in a
  window named `{name}`) and applink `router.py` (~498) — it would create a
  stray `sitrep` window that then opens a separate `agent-sitrep` window.
- `_switch_to` (~1591) decides "running" by exact window name — misses
  `agent-sitrep-<n>` and stamp-only matches.
- Naming the entry `agent-sitrep` would pull the window out of "Code Agents"
  and still collide with agent classification in `monitor_core.classify_pane`
  (~2870) and `framework_version.py` (~182).

## Proposed approach (to be confirmed at planning)

1. **Switcher row**: add a special-cased "Sitrep" row (in `_build_tui_list`
   like the dynamic `git` row, or a registry row flagged so `spawn_tui`/applink
   never launch it). Selecting it (Enter or `S`) always goes through the
   existing `_dispatch_sitrep_open` path (focus-or-spawn for the selected
   session's repo root); add `_TUI_SHORTCUTS["sitrep"] = "S"` so the row shows
   `(S)`. Running dot = any window matching `SITREP_WINDOW_RE` (ideally the one
   stamped for the selected root). Decide whether the `agent-sitrep` window
   should then be de-duplicated out of "Code Agents" (watch
   `tests/test_tui_switcher_brainstorm_session.sh` grouping/dedupe). Follow
   `aidocs/framework/tui_conventions.md:624-642` (registry/row + shortcut +
   Binding + action) as far as it applies. The "is current" check: the sitrep
   TUI sets `current_tui_name = "sitrep_tui"` (`sitrep_tui/sitrep_tui_app.py`
   ~682).
2. **Minimonitor hint**: move `HintSeg(("open_sitrep",), "sitrep")` from the
   loop line to the switcher/monitor tuple → `j:switcher  m:monitor  S:sitrep`
   (31/38 cells). Re-measure the band at the narrow (15, 30) budget documented
   in the comment block (`minimonitor_keys.py:59-105`). Optionally move the
   `open_sitrep` `HelpEntry` (~436) next to "Full monitor" (~366) and mention
   sitrep in the switcher help text (~362).
3. Keep `S` identical across monitor, minimonitor and switcher.

## Touchpoints

- Code: `lib/tui_switcher.py`, `lib/tui_registry.py` (if used),
  `monitor/minimonitor_keys.py`, maybe `monitor/monitor_core.py` (only if
  spawn_tui/applink need a guard).
- Tests: `tests/test_git_tui_config.py` (`TestTuiRegistry`),
  `tests/test_tui_switcher_companion_spawn.py` (list population, `_switch_to`,
  key collisions), `tests/test_monitor_sitrep_harvest_close.py`
  (`SwitcherSitrepTests`), `tests/test_tui_switcher_brainstorm_session.sh`,
  `tests/test_tui_switcher_multi_session.sh`,
  `tests/test_tui_switcher_footer_fit.sh` (dialog max-height 30, one more row),
  `tests/test_minimonitor_key_hints_modes.py`,
  `tests/test_minimonitor_top_chrome_render.py` (band rows at narrow widths),
  `tests/test_tui_switcher_hint_text.py` (only if `_HINT_ITEMS` changes).
- Docs: `website/content/docs/tuis/_index.md` (~35, says the switcher hint row
  doesn't advertise sitrep), `website/content/docs/tuis/minimonitor/how-to.md`
  (~398-400, ~520-525), `website/content/docs/tuis/minimonitor/_index.md`
  (~38), `website/content/docs/workflows/sitrep.md` (~23),
  `website/content/docs/tuis/sitrep/_index.md`, `aidocs/framework/sitrep.md`
  (~29, ~59-62), `aidocs/framework/tui_conventions.md`; switcher screenshot
  scenes (`tui_switcher_dialog`, `_from_monitor`, `_from_minimonitor`) change
  with a new row.

## Related

- Topic: sitrep (t2175); t2211 built the three-pane window
  (`t2211_7` manual verification still Ready).

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2278_5** id=2026-11-20T06:49:32Z.be59ebbbf7af3b6ef5c7bd5d from=t2278_5 from_verified=yes at=2026-11-20T06:49:32Z base=b0bb6e2575e27ba8cd13b897b76f9c0d6f47c6ec base_branch=main dirty=yes host=omg16
>
> | Advisory, from t2278_5 (committed in 45539803d), as of that commit:
> | 
> | The docs now carry generated screenshots of the TUI switcher and of the
> | minimonitor, each recorded as a replayable recipe under
> | website/screenshots/scenes/:
> | - tui_switcher_dialog (4 pages), tui_switcher_from_monitor (2 pages),
> |   tui_switcher_from_minimonitor (1 page): they show today's switcher list and
> |   hint rows, without a sitrep entry.
> | - minimonitor_main_view: shows today's minimonitor key-hint lines.
> | 
> | Adding sitrep to the switcher or changing the minimonitor hint line makes
> | those images stale, and a recipe whose expected text changes will fail its
> | replay. After your change lands, refresh them with
> |   /aitask-docs-screenshots tui_switcher_dialog tui_switcher_from_monitor tui_switcher_from_minimonitor minimonitor_main_view
> | Do not edit the recipe files by hand. Contract:
> | aidocs/framework/docs_screenshots.md.
> | 
> | Related: t2339 covers the switcher dialog being clipped in the 40-column
> | minimonitor pane (fixed width 44 in lib/tui_switcher.py); a new hint or list
> | row there is clipped the same way.

> **✉ note:t2278_5** id=2026-11-20T07:01:42Z.ee73e899eebf5d569e83fed4 from=t2278_5 at=2026-11-20T07:01:42Z base=b0bb6e2575e27ba8cd13b897b76f9c0d6f47c6ec base_branch=main dirty=yes host=omg16
>
> | Correction to my earlier note (advisory): the switcher dialog being clipped in the 40-column minimonitor pane is tracked by t2340, not t2339 (t2339 was rescoped to two unrelated defects). t2340 requires that no switcher content is cut in a narrow pane; a sitrep row or hint added by this task should fit that layout, so coordinate with t2340.

> **✉ note:t2340** id=2026-11-22T15:47:38Z.787674b3a0f31ed21bf38b46 from=t2340 from_verified=yes at=2026-11-22T15:47:38Z base=81f352714a38bbc3fef851e3d6e1ed4e7285519c base_branch=main dirty=yes host=omg16
>
> | Advisory context from t2340, which landed on main as 81f352714 ("bug: Fit the TUI switcher to panes narrower than its dialog (t2340)"). It touches files your task also plans to edit. These are claims about that commit's tree; re-check them against main before relying on them.
> | 
> | - .aitask-scripts/lib/tui_switcher.py: `#switcher_dialog` now has `max-width: 100%`. A new module constant `_DIALOG_WIDTH = 44` must stay equal to the CSS `width: 44;`, and tests/test_tui_switcher_footer_fit.sh now asserts both (`max-width: 100%` and `width: {_DIALOG_WIDTH};`).
> | - While the screen is narrower than `_DIALOG_WIDTH` (any host, not only minimonitor), `TuiSwitcherOverlay._apply_compact` puts a `-compact` class on `#switcher_dialog`. Under that class the dialog's vertical padding, the title's bottom padding and the hint's top padding are 0, and `#switcher_list` has `min-height: 1`. It is re-applied on `on_resize`. `_schedule_reveal` / `_reveal_selection` scroll the highlighted row into view after layout: from `on_mount`, after `_populate_list_for` sets the index, and on resize. The `narrow` flag still governs only AgentCommandScreen.
> | - New tests/test_tui_switcher_narrow_fit.py (9 tests). Its footer checks are derived from `_HINT_ITEMS`, the companion segment and `_OVERLAY_OPEN_KEY`, so new hint items are picked up automatically. It does assert that every footer phrase fits inside the hint region at 40x18 (two sessions) and 34x20 (Monitor + companion), and that the selected row stays drawn above the footer at 40x17 / 40x18 / 34x18 (two sessions) and 40x14 (one session), including after Down/Up and a resize. A longer hint, or an extra fixed-height row (not a list row), uses up that vertical budget, so re-run this file after your change. Extra list rows land in the 1fr list and should be fine.
> | - Docs: website/static/imgs/aitasks_tui_switcher_from_minimonitor.svg still shows the old clipped dialog. t2340 deferred the refresh (`/aitask-docs-screenshots tui_switcher_from_minimonitor`). Since your task changes the same scenes, one refresh after both changes have landed may cover both.
> | 
> | As of when this note was written, t2338 was Implementing in another session. That status is moment-relative and may have changed.

> **👁 note:read** id=2026-11-22T16:36:05Z.e28e34dcc072f830e44d2c76 by=t2338 at=2026-11-22T16:36:05Z mode=explicit ids=2026-11-20T06:49:32Z.be59ebbbf7af3b6ef5c7bd5d,2026-11-20T07:01:42Z.ee73e899eebf5d569e83fed4,2026-11-22T15:47:38Z.787674b3a0f31ed21bf38b46

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-22T15:51:19Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-23T00:26:49Z status=pass attempt=1 type=human
