---
priority: medium
effort: medium
depends: [1272]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1272]
created_at: 2026-08-05 18:06
updated_at: 2026-08-05 18:06
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1272

## Verification Checklist

- [ ] Bullet renders exactly once in all three profile goldens (tests/golden/procs/task-workflow/SKILL-{default,fast,remote}.md) and is NOT profile-conditional — automated, was green at implementation time
- [ ] All six committed remote prerenders carry the bullet: 3x task-workflow-remote-*/SKILL.md + 3x aitask-pickrem-remote-*/materialize-active.md — automated, was green
- [ ] bash tests/test_skill_render_task_workflow.sh passes (181/181 at implementation time)
- [ ] ./.aitask-scripts/aitask_skill_verify.sh passes
- [ ] The staging gate printed GATE_OK and exited 0; the code commit's git show --stat lists exactly the 11 allowlisted paths
- [ ] Concurrent-session containment held: the 8 worktree-modified aitask-trail files present at staging time were left unstaged by the path-explicit git add
- [ ] END-TO-END (the substantive item — 1-6 only prove the text shipped, not that it works): point a task at a gate that is unverifiable (no registry entry in aitasks/metadata/gates.yaml, or a machine command gate with an empty `verifier`), ensure that gate lands in the task's ACTIVE set, then /aitask-pick the task under a profile that materializes gates. Confirm the agent (a) notices the `Warning: materialize-active: active gate '<gate>' has ... — it will block archival.` line on stderr, (b) surfaces it to the user rather than continuing silently, and (c) suggests `ait gates sync-registry`. Repeat once in the remote lane via aitask-pickrem, where the bullet says "display the warning verbatim in the run output".
- [ ] Negative control for the item above: with a fully-satisfiable active gate set, confirm NO such warning is emitted and the agent does not invent one — the instruction must not fire on healthy tasks.
- [ ] Confirm the exit-code contract is unchanged: a run that emits the warning still exits 0 and the pick CONTINUES (it must not be treated as an abort); a genuinely nonzero materialize-active exit still aborts the pick.
