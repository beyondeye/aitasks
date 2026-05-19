---
Task: t777_23_swap_task_workflown_to_task_workflow.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_10_convert_aitask_fold.md, aitasks/t777/t777_11_convert_aitask_qa.md, aitasks/t777/t777_12_convert_aitask_pr_import.md, aitasks/t777/t777_13_convert_aitask_revert.md, aitasks/t777/t777_14_convert_aitask_pickrem.md, aitasks/t777/t777_15_convert_aitask_pickweb.md, aitasks/t777/t777_16_extract_profile_editor_widget.md, aitasks/t777/t777_17_per_run_profile_edit_in_agentcommandscreen.md, aitasks/t777/t777_18_docs_update_claudemd_and_website.md, aitasks/t777/t777_19_retrospective_evaluation.md, aitasks/t777/t777_20_profile_modification_invalidation.md, aitasks/t777/t777_8_convert_aitask_explore.md, aitasks/t777/t777_9_convert_aitask_review.md
Archived Sibling Plans: aiplans/archived/p777/p777_1_minijinja_dep_renderer_paths_resolver.md, aiplans/archived/p777/p777_21_map_pick_reference_closure_and_profile_keys.md, aiplans/archived/p777/p777_22_extend_renderer_for_uniform_recursive_rendering.md, aiplans/archived/p777/p777_25_refactor_stubs_direct_helper_paths.md, aiplans/archived/p777/p777_26_template_completeness_and_resolver_key.md, aiplans/archived/p777/p777_2_aitask_skill_render_subcommand.md, aiplans/archived/p777/p777_3_stub_skill_design_and_gitignore.md, aiplans/archived/p777/p777_4_aitask_skill_verify_and_precommit.md, aiplans/archived/p777/p777_5_aitask_skillrun_wrapper_dispatcher.md, aiplans/archived/p777/p777_6_convert_aitask_pick_template_and_stubs.md, aiplans/archived/p777/p777_7_convert_task_workflow_shared_procs.md
Base branch: main
plan_verified: []
---

# t777_23 — Swap staged `task-workflown/` back to `task-workflow/`

## Context

t777_7 introduced a staging pattern (per the `feedback-stage-under-parallel-name` memory rule): rather than overwrite the actively-running `.claude/skills/task-workflow/` directory with the new Jinja-wrapped procedures, the new content was staged at a parallel name, `.claude/skills/task-workflown/`. The live `task-workflow/` (the unwrapped originals) stayed in place to keep every existing skill working during the staging window.

t777_6 (pilot pick conversion) just landed (commit `b6dabc19`) and references the staged `task-workflown/` paths. Its manual-verification follow-up (t777_24) is archived. Dependencies t777_22 and t777_6 are satisfied. It is now time to do the atomic swap: move `task-workflown/` back to `task-workflow/` so the canonical name is restored, and update every reference from `task-workflown` to `task-workflow`.

## Preconditions verified

- `.claude/skills/task-workflow/` (unwrapped originals) and `.claude/skills/task-workflown/` (Jinja-wrapped staging) both exist as sibling dirs (25 `.md` files each).
- t777_22 archived (renderer/dep-walker ready), t777_6 archived (pilot pick uses staged refs), t777_24 archived (manual verify passed).
- Per-profile rendered dirs `.claude/skills/{task-workflown,aitask-pick}-{default,fast,remote}-/` and their mirrors in `.agents/skills/`, `.gemini/skills/`, `.opencode/skills/` are all gitignored (`.gitignore` lines 32–35 `*-/` glob). They regenerate on demand.

## Scope (single commit)

### A. Move the staged dir into place

1. `rm -rf .claude/skills/task-workflow/` — remove the unwrapped originals.
2. `git mv .claude/skills/task-workflown .claude/skills/task-workflow`.
3. Update SKILL.md frontmatter (in moved dir):
   - `name: task-workflown` → `name: task-workflow`
   - Description: strip the `[t777_7 staged] ` prefix.

### B. Update the only `.j2` template that references the staged dir

`.claude/skills/aitask-pick/SKILL.md.j2` — 3 occurrences of `task-workflown` (lines 185, 206, 207) → `task-workflow`. (`grep -rln "task-workflown" .claude/skills/*/SKILL.md.j2` confirms `aitask-pick` is the only such template at this point — t777_8..t777_15 have not yet landed.)

### C. Rename the test file + rewrite its internals

1. `git mv tests/test_skill_render_task_workflown.sh tests/test_skill_render_task_workflow.sh`.
2. Edit the renamed file:
   - Header comment: replace `task-workflown` → `task-workflow` (file name + dir refs).
   - `STAGED_DIR=".claude/skills/task-workflown"` → `STAGED_DIR=".claude/skills/task-workflow"`.
   - `GOLDEN_DIR="tests/golden/procs/task-workflown"` → `tests/golden/procs/task-workflow"`.
   - `ORIG_DIR=".claude/skills/task-workflow"` → delete the variable (no longer meaningful).
   - **Delete Test 4 entirely** (the “20 identity-passthrough files byte-identical to task-workflow/ siblings”). After the swap, the staged dir IS the canonical dir; there is nothing to compare against. Tests 1, 2, 3, 3b, 5 still validate the rendering correctness of the 5 wrapped files and the synthetic profile branch.

### D. Rename the golden procs dir

`git mv tests/golden/procs/task-workflown tests/golden/procs/task-workflow`.

### E. Update the pilot-pick render test + rendered golden files

1. `tests/test_skill_render_aitask_pick.sh` — replace `task-workflown` → `task-workflow` (4 assertions; lines around 117–124).
2. `tests/golden/skills/aitask-pick/SKILL-*.md` (12 files: 3 profiles × 4 agents) — replace `task-workflown` → `task-workflow`. These are the rendered outputs that the test diff-checks against, so they must mirror the j2 source change exactly.

### F. Update author-facing aidocs

- `aidocs/skill_authoring_conventions.md`
- `aidocs/stub-skill-pattern.md`

Each has prose references to `task-workflown` (the staging pattern doc). Replace `task-workflown` → `task-workflow` only where the prose refers to the *path/dir*, not where it discusses the staging-pattern *concept*. (Concept references should be reworded to past tense: "the staged-under-parallel-name pattern previously used to introduce task-workflown" → "...used to introduce task-workflow without overwriting the live dir during t777_7".) Read both files first; minimum-touch edits.

### G. Clean stale gitignored rendered dirs (safety, not strictly required)

```
rm -rf {.claude,.agents,.gemini,.opencode}/skills/task-workflown-*-/
rm -rf {.claude,.agents,.gemini,.opencode}/skills/aitask-pick-*-/
```
These are gitignored; their absence forces a fresh re-render on the next skill invocation. Tests below re-render aitask-pick anyway (Test 4 of `test_skill_render_aitask_pick.sh` uses `--force`).

## Verification

1. `./ait skill verify` — must exit 0. (Walks every `.j2` authoring template, currently only `aitask-pick/SKILL.md.j2`, under the default profile across all 4 agents.)
2. `bash tests/test_skill_render_task_workflow.sh` — must pass after rename (Tests 1, 2, 3, 3b, 5 only; Test 4 removed in §C).
3. `bash tests/test_skill_render_aitask_pick.sh` — must pass with the updated goldens (§E).
4. `bash tests/test_skill_template.sh` and `bash tests/test_skill_render.sh` — must still pass (neither references `task-workflown` directly, but they exercise the renderer).
5. Final grep: `grep -rln "task-workflown" .claude/ .agents/ .gemini/ .opencode/ tests/ aidocs/ CLAUDE.md` — must return nothing.

## Out of scope

- Re-running any wrap work — the wrapped procedures are already in the staged dir; this task only moves them.
- Updating t777_8..t777_15 templates — none have landed yet, so there is nothing to update there.
- Re-rendering `.agents/`, `.gemini/`, `.opencode/` per-profile dirs explicitly — they regenerate on demand from the renamed source.
- Manual-verification follow-up — this swap is purely mechanical; the live smoke `/aitask-pick <some_task>` in a fresh agent session is the only post-merge check listed in the task and is the user's call to run (no new aitask is needed).

## Step 9 (Post-Implementation)

After approval and commit, do the standard archive flow per `task-workflow/SKILL.md` Step 9: no separate branch was created (profile 'fast': working on current branch), so no merge step; run `./.aitask-scripts/aitask_archive.sh 777_23`, push.
