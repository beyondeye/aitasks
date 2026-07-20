---
priority: medium
effort: medium
depends: [t1166_5]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1166_1, 1166_2, 1166_3, 1166_4, 1166_5]
anchor: 1166
created_at: 2026-07-20 12:11
updated_at: 2026-07-20 12:11
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1166_1] Scratch-repo family bootstrap: parent with family_worktree: true + 2 children; `aitask_family_worktree.sh ensure` creates aiwork/t<N> on aifamily/t<N>; second call reuses; after deleting the worktree dir, ensure reattaches the surviving branch
- [ ] [t1166_1] Concurrency refusal: with one child locked/Implementing (same-host and simulated cross-host lock), ensure for a sibling refuses with BLOCKED:active_sibling:<id>:<hostname>; --force overrides only after explicit confirmation
- [ ] [t1166_3] Per-child selective sync happy path: complete child 1 via /aitask-pick — eligible vs held-back proposal shown, NON-SKIPPABLE approval, sync-paths commit lands on main, main-side verification passes, mandatory sync-from-main follows
- [ ] [t1166_3] Failed main-side verification round: with a deliberately failing verify_build, the sync is rolled back via undo-sync, paths re-classified held-back, child completion unaffected
- [ ] [t1166_3] "Sync nothing this round" is accepted as a valid evaluation outcome (no sync commit, sync-from-main still runs)
- [ ] [t1166_4] Mid-family abort: aborting a child leaves aiwork/t<N> and aifamily/t<N> intact; DIRTY discard-vs-keep prompt behaves as documented
- [ ] [t1166_4] Crash-resume: kill the session mid-child; crash recovery surveys the family worktree (survey_dir = family DIR) and re-pick resumes inside it
- [ ] [t1166_3] Final child: last-child detection fires before archival — final-merge approval, verified merge to main, then archive (parent auto-archives), then teardown removes worktree + branch
- [ ] [t1166_3] Final-merge conflict/deferral: child stays Implementing/in-flight and re-enterable; nothing archives; re-pick resumes at post-implementation
- [ ] [t1166_4] FAMILY_UNMERGED recovery: archive via an abnormal path (--ignore-gates) with an unmerged family branch → FAMILY_UNMERGED line surfaces and the recovery-task offer works; `aitask_family_worktree.sh list` shows the leftover branch
- [ ] [t1166_2] family_worktree field: set at the child-creation checkpoint lands on the parent; ait update set/clear works; rejected on child tasks
- [ ] [t1166_5] Docs spot-check: parallel-development page describes family mode; profiles help mentions the create_worktree override; hugo build clean
- [ ] Retrospective: record whether path-level granularity sufficed in practice and whether the hunk-level sync / anchor-group family follow-ups are justified — create those tasks ONLY if the evidence supports them (Deferred follow-ups table in aiplans/p1166_shared_worktree_for_child_task_families.md)
