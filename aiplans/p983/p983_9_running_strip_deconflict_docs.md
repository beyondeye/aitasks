---
Task: t983_9_running_strip_deconflict_docs.md
Parent Task: aitasks/t983_redesign_brainstorm_tui_ux_unified_browse_contextual_ops.md
Sibling Tasks: aitasks/t983/t983_*_*.md
Archived Sibling Plans: aiplans/archived/p983/p983_*_*.md
Worktree: aiwork/t983_9_running_strip_deconflict_docs
Branch: aitask/t983_9_running_strip_deconflict_docs
Base branch: main
---

# p983_9 — Running rename + header strip + deconflict + docs

Final child of t983. Renames Status→Running, adds the always-on header status
strip, lands **t535** agent actions, and finishes keybinding/CSS/docs deconflict.
Prior children already fixed their own tests, so this child owns only its own
surfaces' tests.

## Goal
Complete the 3-tab IA: `b`/`s`/`r` tabs, `v` toggle, `space` mark; a header strip
showing runner state + active-op count; Running-tab agent actions; docs.

## Steps
1. Rename `tab_status`→`tab_running` (`r`); update all references; Running content
   is the existing `_refresh_status_tab`/`#status_content`
   (`.aitask-scripts/brainstorm/brainstorm_app.py:5320+`).
2. Extract a **pure** header-strip derivation (runner state + active-op count from
   runtime state); render it always-on above the tabs in a custom header widget.
3. Implement **t535** agent actions (kill/cleanup/retry) within the Running tab
   (see `aitasks/t535_brainstorm_status_tab_agent_actions.md`).
4. Final keybinding deconflict: tabs `b`/`s`/`r`, `v`, `space`; re-scope `f`
   (toggle_deferred), `H` (op_help), `D` (diff) in `_TAB_SCOPED_ACTIONS` (:3385) +
   `check_action` (:3459) to the new tab ids (else they silently hide).
5. Update inline CSS; `aidocs/framework/tui_conventions.md`; website TUI pages
   (keep `brainstorm` in the user-facing TUI list).

## Verification
- Pure unit: `tests/test_brainstorm_header_strip.py` — count/state derivation.
- Pilot: Running tab renders; agent actions (kill/cleanup/retry) dispatch.
- Suite: full `tests/test_brainstorm*.py` green; run
  `./.aitask-scripts/aitask_skill_verify.sh` only if a skill/stub surface is
  touched (docs alone do not require it).
- Manual: `b`/`s`/`r` navigate; header strip shows runner + running count;
  `f`/`H`/`D` work under their new tabs.

## Step 9
Archive via `./.aitask-scripts/aitask_archive.sh 983_9` — the parent t983 archives
automatically when this last child completes.
