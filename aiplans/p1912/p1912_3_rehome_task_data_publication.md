---
Task: t1912_3_rehome_task_data_publication.md
Parent Task: aitasks/t1912_move_codeagent_stats_to_plumbing_branch.md
Sibling Tasks: aitasks/t1912/t1912_*_*.md
Archived Sibling Plans: aiplans/archived/p1912/p1912_*_*.md
Base branch: main
Output branch: main
---

# t1912_3 — Re-home task-data publication (plan)

Full spec and site inventory: `aitasks/t1912/t1912_3_rehome_task_data_publication.md`.

## Steps

1. Re-derive the inventory: grep every satisfaction-feedback caller and every
   stop/end exit that follows a task-data commit (`aitask_task_commit.sh`,
   `aitask_create.sh --commit`, `./ait git commit`) across `.claude/skills/**`
   and `.aitask-scripts/skill_templates/`. Reconcile it with the task's table
   and record the final list here.
2. Edit each source (`.md.j2` / `SKILL.md` / shared template): after the
   last task-data commit, add a best-effort `./ait git push`. Report the
   result and never fail on it. Where the step shows the end banner, feed
   `pushed:` from this push.
3. Decide the failed-L1211-push second-attempt case (likely: nothing beyond
   the banner's `pushed: no`) and record it.
4. Rerender all profiles, regenerate the goldens in the same commit, and run
   `./.aitask-scripts/aitask_skill_verify.sh`.
5. Suggest port tasks for `.agents/` / `.opencode/` trees that are not
   rendered from these sources.

## Verification

- `aitask_skill_verify.sh` is clean.
- The golden and render tests pass.
- Spot-read the rendered fast/default/remote variants for each site.

## Step 9

Post-Implementation per task-workflow.
