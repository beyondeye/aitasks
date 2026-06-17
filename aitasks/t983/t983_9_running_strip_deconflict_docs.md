---
priority: medium
effort: medium
depends: [t983_8]
issue_type: refactor
status: Implementing
labels: [brainstorming, tui, ait_brainstorm]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-14 11:40
updated_at: 2026-06-17 11:32
---

## Context
Final child of t983. Renames the opaque Status tab to **Running**, adds the
always-on header status strip (runner state + active-op count) the target IA
calls for, lands t535's Running-tab agent actions, and finishes the keybinding /
footer / CSS / docs deconflict. Every prior child already fixed its own test
assertions, so this child only owns its own surfaces' tests. Coordinates with
**t535** (its kill/cleanup/retry actions land here).

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
  guards, and `action_tab_status`.
- Re-scope `f`/`H` (and any others) in `_TAB_SCOPED_ACTIONS` / `check_action`
  to the new tab ids.
- The Session tab (`tab_session`, key `s`) is final — leave it as-is.

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
1. Rename `tab_status`→`tab_running` (`r`); update all references.
2. Extract a **pure** header-strip derivation (runner state + active-op count
   from runtime state) and render it in a custom header widget always-on above
   the tabs.
3. Implement t535's agent actions (kill/cleanup/retry) within the Running tab.
4. Final keybinding deconflict: `b`/`s`/`r` tabs, `v` toggle, `space` mark, `c`
   compare-overlay (from t983_7); re-scope `f` (toggle_deferred), `H` (op_help)
   to the new tab ids in `_TAB_SCOPED_ACTIONS` + `check_action`. (`D`/diff is no
   longer app-level — it moved into `CompareMatrixModal` in t983_7.)
5. Update inline CSS, `tui_conventions.md`, website TUI pages.

## Verification
- Pure unit: `tests/test_brainstorm_header_strip.py` — count/state derivation.
- Pilot: Running tab renders; agent actions (kill/cleanup/retry) dispatch.
- Suite: full `tests/test_brainstorm*.py` green; run
  `./.aitask-scripts/aitask_skill_verify.sh` if any skill/doc surface touched.
- Manual: `b`/`s`/`r` navigate; header strip shows runner + running count; `f`/
  `H`/`D` work under their new tabs.
