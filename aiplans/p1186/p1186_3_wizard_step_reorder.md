---
Task: t1186_3_wizard_step_reorder.md
Parent Task: aitasks/t1186_chatlink_wizard_allowlist_live_pickers.md
Sibling Tasks: aitasks/t1186/t1186_1_authorization_modes.md, aitasks/t1186/t1186_2_discord_fetch_surface.md, aitasks/t1186/t1186_4_allowlist_picker_ui.md
Archived Sibling Plans: aiplans/archived/p1186/p1186_*_*.md
Worktree: (profile 'fast' — current branch)
Branch: main
Base branch: main
---

# p1186_3 — Wizard step reorder (derived numbering + declared seams)

Third sequential slice of t1186. Moves token + live check ahead of the allowlist so the
t1186_4 picker can fetch, and removes both reorder-hostile couplings. Line refs verified
2026-07-20 (re-verify against current wizard.py — siblings landed since).

## Steps

1. **Derived numbering** — `_WizardStep`: class attr `step_name: str`; `__init__`
   kwargs `step_no: int = 0`, `step_total: int = 0`; base `compose()` (:181 area)
   renders `f"Step {step_no}/{step_total} — {step_name}"` into `#wizard_title`.
   Convert all 7 `step_title` literals (:224-225, :256, :291, :312, :346, :385, :510)
   to `step_name` (text unchanged; AllowlistScreen wording is revised later by t1186_4).
2. **Declared seams** — `needs_seams: bool = False` on the base; `True` on
   `TokenScreen`/`LiveCheckScreen`/`SummaryScreen`. `make_step()` (:674-679): branch on
   `cls.needs_seams`, pass `step_no=idx+1`, `step_total=len(_STEPS)`; delete the
   hardcoded class tuple.
3. **Reorder `_STEPS`** (:697-698) to: IntakeChannel, Token, LiveCheck, Allowlist,
   DenyRepo, Ceilings, Summary. (LiveCheckScreen reads only provider/token/
   workspace_id/conversation_id/thread_id — all set by steps 1-2.)
4. **Tests** — `tests/test_chatlink_tui.sh` (:290-563): reorder pilot input sequences +
   `isinstance` progression assertions; add a `#wizard_title` derived-numbering
   assertion for one representative screen (TokenScreen → "Step 2/7").

## Verification

`bash tests/test_chatlink_tui.sh` fully green under the new order (escape-abort,
restart, Back-retains-state, empty-allowlist double-Next, live-check spy paths, app4
mid-run dismiss guard, save/replace/token-failure paths).
`bash tests/test_chatlink_wizard.sh` green (headless helpers untouched).

Post-implementation per task-workflow Step 9; archive via `aitask_archive.sh 1186_3`.
