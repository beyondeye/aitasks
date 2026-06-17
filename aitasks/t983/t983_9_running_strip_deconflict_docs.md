---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: [t983_8]
issue_type: refactor
status: Implementing
labels: [brainstorming, tui, ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-14 11:40
updated_at: 2026-06-17 11:58
---

## Context
Last child of t983's *original* decomposition (NOT the final pending child —
**t983_10** manual-verification and **t983_11** wizard-rehost remain in
`children_to_implement`, so the parent does **not** archive on this child's
completion). Renames the opaque Status tab to **Running**, adds the always-on
header status strip (runner state + active-op count) the target IA calls for,
lands the remaining **t535** Running-tab agent actions, and finishes the
keybinding / CSS / docs deconflict. Every prior child already fixed its own test
assertions, so this child only owns its own surfaces' tests.

**t535 scope reconciliation:** kill (`k`/`K`), pause/resume (`p`), and reset
(`w`, Error→Waiting) **already shipped** on the Running surface. This child adds
the two genuine gaps: **Cleanup** (`x`, remove a finished/failed agent's
artifacts behind a confirm modal) and a **distinct Retry** (`R`, reset + ensure
the runner relaunches).

### Coordination with t983_7 (landed — compare overlay)
t983_7 deleted the Compare **tab** and re-homed the dimension matrix into a
`CompareMatrixModal` overlay, which changes the Browse keymap this child
finalizes:
- **`c`** is now bound to `compare_matrix` (opens the overlay on the marked
  set), **not** `tab_compare`. Pick the final Browse keymap (`b`/`s`/`r` tabs)
  around this — `c` is a Browse action key, not a tab key.
- **`r`** (was `compare_regenerate`) is **freed** — t983_7 removed it, so this
  child can take `r` for the Running tab without a collision.
- **`D`** (was the app-level `compare_diff`) is **gone from the app level** — it
  now lives inside `CompareMatrixModal`. Do **NOT** re-scope `D` in
  `_TAB_SCOPED_ACTIONS` / `check_action` (there is no app-level `D` to scope).

### Coordination with t983_8 (Session tab — landed)
t983_8 added the **Session** tab and already took **`s`** for it, provisionally
moving the Status tab to the free **`r`** key with a plain `"Status"` label
(`tab_status` id/`action_tab_status` unchanged). So this child's "final b/s/r
deconflict" no longer needs to *assign* the keys — `b`/`s`/`r` are already in
place. What remains here:
- Rename `tab_status` → `tab_running` and relabel `"Status"` → `"(R)unning"`
  (the key is **already** `r`). Update the `tab_status` references in the
  down-from-tab-bar focus map (`tab_to_container`), `on_pane`/`_refresh_status_tab`
  guards, and `action_tab_status` (9 sites total — verified, not the stale
  "~5320+").
- **No `f`/`H`/`D` re-scoping is needed** (original task assumption was wrong):
  `_TAB_SCOPED_ACTIONS` only holds `open_node_detail`; `f`(toggle_deferred) and
  `H`(op_help) are hardcoded in `check_action` to `tab_browse`/`tab_actions`
  respectively, and `D` is fully modal-scoped inside `CompareMatrixModal`. None
  are Running-scoped, so the rename does not touch them.
- `b` is **not** currently bound (Browse is reached via `d`/`g`); finalizing
  `b/s/r` means **adding** a `b`→Browse-tab binding. The Session tab
  (`tab_session`, key `s`) is final — leave it as-is.

## Key Files to Modify
- `.aitask-scripts/brainstorm/brainstorm_app.py` — rename Status→Running (`r`);
  add a custom header status-strip widget with the count/state derivation as a
  **pure** function; add t535 agent actions (kill/cleanup/retry) on the Running
  surface; finalize keybindings `b`/`s`/`r`, `v`, `space`; re-scope `f`/`H`/`D`
  in `_TAB_SCOPED_ACTIONS` (:3385) + `check_action` (:3459) to the new tab ids;
  update inline CSS.
- `aidocs/framework/tui_conventions.md` — reflect the new 3-tab IA.
- `website/content/docs/...` TUI pages — keep `brainstorm` in the user-facing TUI
  list (board, monitor, minimonitor, codebrowser, settings, brainstorm).
- `tests/test_brainstorm_header_strip.py` — NEW.

## Reference Files for Patterns
- Status tab: `_refresh_status_tab` / `#status_content` (:5320+) — becomes
  Running.
- `_TAB_SCOPED_ACTIONS` (:3385) + `check_action` (:3459) — the tab-scoped key
  gating that must move to the new ids or keys silently hide.
- t535 task (`aitasks/t535_brainstorm_status_tab_agent_actions.md`) — the
  kill/cleanup/retry actions to implement here.

## Implementation Plan
1. Rename `tab_status`→`tab_running` (`r`) across the 9 verified sites; grep-sweep
   to confirm no stale reference survives.
2. Extract a **pure** runtime-strip derivation (`derive_runner_state` /
   `format_status_strip`: runner state + active-op count) and render it in an
   always-on `Static` strip above the tabs (sibling of `initializer_row`),
   refreshed off-tab via `_refresh_status_strip`.
3. Add the remaining t535 Running-tab actions: **Cleanup** (`x`, confirm modal)
   and a **distinct Retry** (`R`, reset + ensure runner relaunches). Kill/pause/
   reset already exist.
4. Final keybinding deconflict: **add** `b`→Browse tab; `s`/`r` already final;
   `v` toggle, `space` mark, `c` compare-overlay unchanged. (No `f`/`H`/`D`
   re-scope — they are not Running-scoped.)
5. Update inline CSS + `aidocs/framework/tui_conventions.md` (3-tab IA note);
   keep `brainstorm` in the website TUI list; create a follow-up task for the
   full website brainstorm docs (out of scope here).

## Verification
- Pure unit: `tests/test_brainstorm_header_strip.py` — state/count derivation +
  a `b/s/r` keymap + rename-completeness assertion.
- Suite: full `tests/test_brainstorm*.py` green (598 tests). No skill/stub
  surface touched, so `aitask_skill_verify.sh` is not required (docs-only).
- Manual: `b`/`s`/`r` navigate; always-on strip shows runner state + running
  count and updates off-tab; on Running, `x` (cleanup, confirmed) and `R`
  (retry→relaunch) dispatch on a focused failed agent; `p`/`k`/`K`/`w`/`e`/`L`
  still work.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-17T08:58:12Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-17T08:58:13Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-17T09:11:08Z status=pass attempt=1 type=human
