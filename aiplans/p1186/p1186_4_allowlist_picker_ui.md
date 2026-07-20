---
Task: t1186_4_allowlist_picker_ui.md
Parent Task: aitasks/t1186_chatlink_wizard_allowlist_live_pickers.md
Sibling Tasks: aitasks/t1186/t1186_1_authorization_modes.md, aitasks/t1186/t1186_2_discord_fetch_surface.md, aitasks/t1186/t1186_3_wizard_step_reorder.md
Archived Sibling Plans: aiplans/archived/p1186/p1186_*_*.md
Worktree: (profile 'fast' — current branch)
Branch: main
Base branch: main
---

# p1186_4 — Allowlist picker UI (mode selectors + SelectionList pickers + validation)

Final sequential slice of t1186. Consumes t1186_1 (`policy.effective_posture`, mode
fields), t1186_2 (`allowlist_fetch.run_allowlist_fetch`, `dedupe_ids`,
`invalid_snowflakes`), t1186_3 (reorder, `needs_seams`, derived numbering). The task
file pins the full screen state model and the required tests — follow it exactly.
Re-verify wizard.py line refs against current source (siblings landed since planning).

## Steps

1. **Seam plumbing** — `WizardSeams` + `allowlist_fetch_runner` (default
   `allowlist_fetch.run_allowlist_fetch` in `resolve_seams()`); `chatlink_app.py`
   init param + `action_wizard` wiring (test seam).
2. **State round-trip** — `initial_state()` / `build_edits()`: six keys
   (`user_authorization_mode`, `role_authorization_mode`, `allowed_user_ids`,
   `denied_user_ids`, `allowed_role_ids`, `denied_role_ids`); inactive lists preserved,
   never cleared.
3. **Screen rebuild** — `AllowlistScreen` (`needs_seams = True`): two `CycleField`
   mode selectors (one per dimension); Inputs relabel with mode and always edit the
   active-mode list. Mode toggle: parse Input → outgoing list, load Input ← incoming
   list. SelectionList selected-state recomputed on toggle; selection handler reads
   mode at event time (stale-event guard); filter narrows rows only.
4. **Fetch worker** — "Fetch from Discord" Button (discord provider only; token from
   `state["token"] or seams.token_reader()`); thread worker + generation guard per
   `LiveCheckScreen` (:409-453 pattern); two SelectionLists (label `"{name} ({id})"`,
   `aitask_board.py:3097-3143` precedent) + filter Input; pre-select ids already in the
   active Input; write-back = preserved manual ids ∪ selected fetched ids; truncation
   notice; per-stage advisory errors — manual entry never blocked.
5. **Validation + warning** — `_accept()`: dedupe always; discord →
   `invalid_snowflakes` hard-blocks with named bad tokens; posture-aware one-shot
   warning via `policy.effective_posture()` (deny_all / open_members texts per task
   file; restricted advances silently).
6. **Summary** — per-dimension `users: <mode>: <ids or (none)>` / `roles: ...` lines.
7. **TUI tests** — fake fetch-runner spy suite + the four REQUIRED state-model tests
   (mode-toggle-after-selection, filter-after-toggle, toggle round-trip, Back/Next
   retention) + posture warnings + end-to-end saved-config round-trip, per task file.

## Verification

`bash tests/test_chatlink_tui.sh` green (new suites + all existing);
`test_chatlink_wizard.sh`, `test_chatlink_config.sh`, `test_chatlink_preflight.sh`
green. Live picker behavior (real fetch, unchunked cache, visibility exclusion, filter
on large lists) delegated to the aggregate manual-verification sibling.

Post-implementation per task-workflow Step 9; archive via `aitask_archive.sh 1186_4`
(last implementation child; the MV sibling follows).
