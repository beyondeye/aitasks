---
Task: t1166_4_family_failure_recovery_surfaces.md
Parent Task: aitasks/t1166_shared_worktree_for_child_task_families.md
Sibling Tasks: aitasks/t1166/t1166_1_family_worktree_helper_script.md, aitasks/t1166/t1166_2_family_worktree_frontmatter_field.md, aitasks/t1166/t1166_3_task_workflow_family_mode_main_path.md, aitasks/t1166/t1166_5_family_worktree_docs_and_profile_surface.md
Base branch: main
---

# Plan: t1166_4 — family failure/recovery surfaces

## Context

Family-awareness for the failure paths: abort, crash recovery, plan-header emission, and the **durable archive-side guard** that keeps "archived but family branch unmerged" visible. Normal flow (t1166_3) makes stranded state impossible; this child covers the abnormal archival paths that bypass Step 9's family logic (task-workflow Step 3 Check 1/2/4 backstops, `aitask_archive.sh --ignore-gates`, board-driven archival). Fix at the shared sink (`aitask_archive.sh` output), not per-path.

Depends on t1166_1/2. If t1166_3 is in flight concurrently, sequence after it (shared goldens/render surfaces).

## Steps

1. **`task-abort.md`** (~41-47, verbatim file): replace the unconditional cleanup: run `./.aitask-scripts/aitask_family_worktree.sh status <task_id>`; `FAMILY_MODE:true` → do NOT remove worktree/branch; if `DIRTY:true` → AskUserQuestion "Discard the aborted child's uncommitted changes in the shared family worktree?" (Discard: `git -C aiwork/t<N> checkout -- . && git clean -fd` / Keep them); inform: committed work remains on the family branch and resurfaces at the next sync evaluation / final merge (revert there via `aitask-revert` if unwanted). Non-family path byte-identical to today.
2. **`crash-recovery.md`** Step 1 survey (~29-35): for child tasks also run `status`; `FAMILY_MODE:true` + `EXISTS:true` → `survey_dir = DIR` (family worktree takes precedence; the `refs/heads/aitask/<task_name>` match cannot fire for `aifamily/` refs). Survey remains read-only; the decline path still never removes worktrees.
3. **`aitask_plan_externalize.sh`** (~304-311): after the per-task `[[ -d "aiwork/${task_name}" ]]` branch, add: basename matches `t<p>_<n>_*` (child) AND `aiwork/t<p>` exists → emit `Worktree: aiwork/t<p>` + `Branch: aifamily/t<p>`. Structural check only (no frontmatter read), mirroring the existing heuristic.
4. **`aitask_archive.sh` FAMILY_UNMERGED guard**: in the archival path (both direct child/parent archival and the parent auto-archive branch ~458-510), after resolving the family parent id N: if branch `aifamily/t<N>` exists and `git rev-list --count main..aifamily/t<N>` > 0 → emit `FAMILY_UNMERGED:aifamily/t<N>:<ahead>` to stdout. Archival PROCEEDS (merge-independent semantics pinned); the line is informational output for callers.
5. **Workflow routing** (SKILL.md Step 9 "Parse the script output" list — small additive edit; t1166_3 owns the big restructure): add `FAMILY_UNMERGED:<branch>:<ahead>` → follow family-sync.md's Recovery section: AskUserQuestion "Family branch <branch> still carries <ahead> unmerged commit(s). Run the final merge now, or create a recovery task?" → "Merge now" (family-sync final mode) / "Create recovery task" (`aitask_create.sh --batch --name merge_family_branch_t<N> --type chore …` with a description pointing at the Recovery section) / "Ignore" (warn it stays discoverable only via `aitask_family_worktree.sh list`).
6. **Tests**: extend `tests/test_plan_externalize.sh` (family-header case: child basename + `aiwork/t<p>` present → both lines; dir absent → neither); new archive-guard test (fixture: scratch repo, `aifamily/t<N>` with one unmerged commit → archive child → `FAMILY_UNMERGED:` line present; branch merged or absent → line absent — negative control). Regenerate goldens for any templated file touched (SKILL.md edit → the three SKILL goldens + rerender, same commit).

## Verification

- `bash tests/test_plan_externalize.sh`
- New/extended archive test passes both positive and negative-control cases
- `shellcheck .aitask-scripts/aitask_plan_externalize.sh .aitask-scripts/aitask_archive.sh`
- `bash tests/test_skill_render_task_workflow.sh` + `./.aitask-scripts/aitask_skill_verify.sh` (SKILL.md changed)
- Manual: abort negative control (family worktree survives a child abort) is exercised in t1166_6.
