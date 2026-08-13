---
priority: medium
effort: medium
depends: [1507]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1507]
anchor: 1171
followup_kind: manual_verification
created_at: 2026-08-13 20:49
updated_at: 2026-08-13 20:49
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1507

## Verification Checklist

- [ ] [t1507] Live t1073 scenario: restart a tmux session so the bootstrap fires several concurrent silent `ait projects add`, then confirm the REAL ~/.config/aitasks/projects.yaml kept every entry's project_group and last_opened (the automated test uses an isolated AITASKS_PROJECTS_INDEX and cannot cover the real file).
- [ ] [t1507] Wedged-guard recovery, end to end: create <data-worktree>/attachments/.attach.lock.gc by hand, confirm `ait attach add` reports busy, then remove the guard and confirm the next add succeeds — the documented cure has never been run against a real lock path.
- [ ] [t1507] Run `ait gates sync-registry` concurrently with a second invocation and confirm one wins cleanly with no leftover /tmp/aitask_gate_registry_sync or .gc dir.
