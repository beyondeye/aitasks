---
priority: medium
effort: medium
depends: [1766]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1766]
anchor: 1705
followup_kind: manual_verification
created_at: 2026-09-10 12:18
updated_at: 2026-09-10 12:18
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1766

## Verification Checklist

- [ ] TODO: verify .aitask-scripts/frozenagent/frozenagent_app.py end-to-end in tmux
- [ ] Freeze a real agent, set `frozen.restore_ack_grace: 60` in the target project's project_config.yaml, then restore from the frozenagent viewer: the header must stay on `dispatching…` past 40s and report the eventual SUCCESS, never "still restoring after the grace — run reconcile".
- [ ] With the DEFAULT grace (no `frozen:` block), confirm the viewer still gives up at ~40s on a restore that genuinely stalls — the deadline must not have been removed, only made configuration-aware.
- [ ] Confirm the deadline follows the RECORD's project, not the viewer's cwd: launch the cross-project list mode (`ait frozenagent`, no --record) from a different repo and restore a record whose own project raised the grace.
- [ ] Confirm `drop` is unaffected — its own grace and terminal path are untouched by this change.
