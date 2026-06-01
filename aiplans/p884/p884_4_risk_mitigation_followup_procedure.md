---
Task: t884_4_risk_mitigation_followup_procedure.md
Parent Task: aitasks/t884_add_task_risk_evaluation_in_planning.md
Sibling Tasks: aitasks/t884/t884_*.md
Archived Sibling Plans: aiplans/archived/p884/p884_*_*.md
Worktree: aiwork/t884_4_risk_mitigation_followup_procedure
Branch: aitask/t884_4_risk_mitigation_followup_procedure
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-01 18:14
---

# Plan: t884_4 — Risk-mitigation procedure (before + after)

> Parent architecture & decisions: `aiplans/p884_add_task_risk_evaluation_in_planning.md`.
> Depends on t884_3 (`## Risk` + `risk_mitigations_planned`); uses t884_1's `risk_mitigation_tasks`.

## Verify-pass findings (2026-06-01, anchors confirmed against current tree)

- **t884_3 landed** — `risk-evaluation.md` exists, is profile-agnostic (in
  `WRAPPED_FILES_INVARIANT`), authors the two-subsection `## Risk` section with
  per-risk bullets `<description> · severity: <…> · → mitigation: <link or "TBD">`,
  and threads `risk_level_code_health` / `risk_level_goal_achievement` /
  `risk_mitigations_planned`. The `→ mitigation` placeholder is exactly the seam
  this task fills. ✅
- **planning.md §6.1** risk dispatch is at lines 272–273 (zero-footprint
  `{%- if profile.risk_evaluation is defined and profile.risk_evaluation %}`). The
  mitigation-proposal hook goes immediately after it (still inside the same gate),
  feeding `→ mitigation` links into the `## Risk` section just authored. ✅
- **SKILL.md Step 7** risk-field write hook is at lines 282–293 (same gate),
  right after the cross-repo-child-assignment hook (line 281). The "before"
  creation + dep-wiring hook slots alongside it, inside the same gate. ✅
- **SKILL.md Step 8c** (line 425) is the last sub-step before Step 9 (line 435);
  **Step 8d** suffixes cleanly with no renumber of 8b/8c. ✅
- **`aitask_update.sh`** exposes `--deps DEPS` (line 138: "replaces all"),
  `--risk-code-health` / `--risk-goal-achievement` (lines 250–251), and
  `--risk-mitigation-tasks IDS` (line 252). **Both `--deps` AND
  `--risk-mitigation-tasks` REPLACE the full list** — neither is additive — so the
  "before"-creation step must read-modify-write *both* the original's `depends:`
  and its `risk_mitigation_tasks:` (read current, append the new ID, write the
  full list back). ✅
- **Render test** (`tests/test_skill_render_task_workflow.sh`): `Test 5` already
  proves the `risk_evaluation: true` gate fires at the two t884_3 dispatch sites;
  extend it to also assert the new before/8d hooks. The new closure is
  profile-agnostic (no `{{ profile.* }}` — the propose-confirm always runs; only
  the dispatch sites are gated) → add it to `WRAPPED_FILES_INVARIANT` with one
  canonical golden, mirroring `risk-evaluation.md`. ✅

## Goal

Propose-and-confirm before/after risk-mitigation follow-up tasks, gated by
`risk_evaluation`. **before** = independent task the original DEPENDS ON (created
Step 7); **after** = post-implementation follow-up (created new Step 8d).

## Before-mitigation flow decision (user-confirmed 2026-06-01)

When a "before" mitigation is created at Step 7 and wired as a blocking
dependency, the original task **does not continue to implementation in the same
session**: Step 7 reverts the original to `Ready` (so it shows **Blocked** in
`ait ls` until the mitigation lands), releases its lock, and **ends the
workflow**. The user implements the mitigation, then re-picks the original — at
which point t884_5's force-reverify (Step 6.0a) fires because the codebase
changed under the plan. This matches the parent plan's "force re-verified on the
**next pick**" model and t884_4's own verification ("original shows Blocked until
it lands"). "After" mitigations (Step 8d) block nothing → the workflow proceeds
normally to Step 9.

## Steps

1. **New closure `.claude/skills/task-workflow/risk-mitigation-followup.md`**:
   - *Design-in-planning*: from `## Risk`, propose candidate before/after mitigations (AskUserQuestion, propose+confirm); record chosen + timing in the plan; thread a flag.
   - *Step 7 (before)*: create each via Batch Task Creation; **read-modify-write** the original's `depends:` to add the new ID (`--deps` REPLACES — read current first); **also read-modify-write** `risk_mitigation_tasks` (`--risk-mitigation-tasks` ALSO REPLACES — read current, append the new ID, write full list). Both can be set in one `aitask_update.sh --batch` call.
   - *Step 8d (after)*: create each via Batch Task Creation.
2. **`planning.md`** — gated design proposal hook feeding `## Risk` mitigation links.
3. **`SKILL.md`** — Step 7 "before" creation (gated, alongside t884_3 write); new **Step 8d** after 8c (SUFFIX — do not renumber 8b/8c).
4. **Regenerate** variants + goldens; run `aitask_skill_verify.sh` — same commit.

## Reference patterns

- `upstream-followup.md` (8b) + `manual-verification-followup.md` (8c) — propose-confirm + seeding + return contract.
- `cross-repo-child-assignment.md` — Step 7 creation + dep wiring + gating.
- `task-creation-batch.md` — create heredoc template.

## Verification

- `aitask_skill_verify.sh` passes; goldens committed together.
- Dry-run plan w/ `risk_evaluation: true` + a risk: offer appears; "before" creation adds dep edge (original Blocked in `ait ls`) + appends `risk_mitigation_tasks`; "after" created at 8d. Key absent ⇒ no offer.
- 8b/8c numbering unchanged.

## Notes for sibling tasks

`risk_mitigation_tasks` populated here is read by t884_5. Keep design/creation split clean — NO creation/mutation in plan mode.

## Post-Review Changes

### Change Request 1 (2026-06-01 18:25)
- **Requested by user:** Don't explain in the procedure body that it is "opt-in"
  / dispatched only when `risk_evaluation` is set — the runtime agent only ever
  reaches a rendered variant when already dispatched, so the gating explanation
  is wasted tokens. Also fix the same mistake in the previously-landed
  `risk-evaluation.md` (t884_3).
- **Changes made:** Removed the opt-in/gating paragraph from
  `risk-mitigation-followup.md` (kept the one behavioral line "the offer is
  always propose-and-confirm"). Removed the equivalent opt-in/gating paragraph
  from `risk-evaluation.md`. Regenerated both canonical goldens
  (`risk-mitigation-followup-default.md`, `risk-evaluation-default.md`); re-ran
  the render test (91/91) and `aitask_skill_verify.sh` (OK).
- **Files affected:** `.claude/skills/task-workflow/risk-mitigation-followup.md`,
  `.claude/skills/task-workflow/risk-evaluation.md`,
  `tests/golden/procs/task-workflow/risk-mitigation-followup-default.md`,
  `tests/golden/procs/task-workflow/risk-evaluation-default.md`.

## Final Implementation Notes

- **Actual work done:** Implemented the risk-mitigation procedure exactly as
  planned (after the verify pass).
  - New profile-agnostic closure `risk-mitigation-followup.md` with three parts:
    Part 1 design-in-planning (propose-and-confirm before/after mitigations,
    records a parseable `### Planned mitigations` block into the plan's `## Risk`
    section, threads `risk_mitigations_confirmed`); Part 2 Step 7 "before"
    creation (creates independent parent tasks the original depends on,
    **read-modify-writes BOTH `depends:` and `risk_mitigation_tasks`** since both
    `--deps` and `--risk-mitigation-tasks` REPLACE, back-fills plan links); Part 3
    Step 8d "after" creation (independent follow-up tasks, appends to
    `risk_mitigation_tasks`).
  - `planning.md` §6.1: mitigation-design dispatch bullet added inside the
    existing `{%- if profile.risk_evaluation ... %}` gate, right after the
    risk-eval bullet.
  - `SKILL.md` Step 7: gated "before" creation hook + the **stop-&-revert-to-Ready**
    branch (release lock, revert original to Ready→Blocked, push, END workflow)
    when `risk_before_created: true`. Step 8c→8d: inline conditional pointer
    (`Step 8d` when gated on / `Step 9` when off — byte-identical default). New
    gated `### Step 8d` "after" block before Step 9. No renumber of 8b/8c.
  - Tests: added `risk-mitigation-followup.md` to `WRAPPED_FILES_INVARIANT`,
    extended Test 5 (planning mitigation-design, Step 7 before hook, Step 8d,
    Step 8c→8d pointer, plus default-absence asserts), updated header counts
    (11 wrapped / 23 goldens). New canonical golden
    `risk-mitigation-followup-default.md`.
- **Deviations from plan:** None structural. One **user-confirmed design
  decision** the plan had left open: when a "before" mitigation is created at
  Step 7, the original is **stopped and reverted to Ready** (not implemented this
  session) — recorded under "Before-mitigation flow decision" above.
- **Post-review:** Removed the wasteful "opt-in / dispatched only when…" gating
  paragraph from both the new closure AND the previously-landed
  `risk-evaluation.md` (Change Request 1) — the runtime agent only reaches a
  rendered variant when already dispatched, so the gating explanation is dead
  tokens.
- **Issues encountered:** None. Render test 91/91, `aitask_skill_verify.sh` OK;
  committed planning/SKILL goldens stayed byte-identical (zero-footprint gate
  idiom `{%- if … is defined and … %}` verified for the new sites and the inline
  Step 8c pointer).
- **Key decisions:** (1) before/after mitigations are **independent parent
  tasks** (not children) — `update_parent_children_to_implement` untouched.
  (2) `risk_mitigation_tasks` is a REPLACE flag like `--deps`, so both need RMW —
  flagged explicitly in the closure. (3) The new closure is profile-agnostic →
  `WRAPPED_FILES_INVARIANT` (one canonical golden), gates live only at the three
  dispatch sites.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **t884_5** (force-reverify) reads `risk_mitigation_tasks` populated by Part 2
    / Part 3 here; it adds Step 6.0a (suffix). The "before"-creation stop-&-revert
    path is what makes force-reverify meaningful: the original is re-picked after
    the mitigation lands.
  - **t884_6** (docs) should document the `### Planned mitigations` plan block and
    the before=blocking-dep / after=follow-up semantics, plus the stop-&-revert
    behavior.
  - **t884_7** already tracks the Codex/OpenCode ports of these skill changes —
    no new port task filed here.
  - Plan record contract: mitigations are recorded as
    `- timing: before|after | name: … | type: … | priority: … | effort: … | addresses: … | desc: …`
    lines under `### Planned mitigations` inside `## Risk`; creation parts parse
    that block.
