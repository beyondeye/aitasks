---
priority: medium
effort: medium
depends: [866]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [866]
created_at: 2026-05-31 11:32
updated_at: 2026-05-31 11:32
boardidx: 110
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t866

## Verification Checklist

- [ ] Launch `ait codeagent invoke qa <archived-task-id>` with a `codex/*` agent string — confirm Codex starts in DEFAULT mode (composer does NOT show /plan) and that a request_user_input prompt actually surfaces during the qa flow.
- [ ] Launch `ait codeagent invoke explain <source-file>` with a `codex/*` agent string — confirm DEFAULT mode and that any request_user_input prompt surfaces (not silently skipped).
- [ ] Launch `ait codeagent invoke pick <task-id>` with a `codex/*` agent string — confirm the composer DOES show /plan (plan mode still forced for the planning skill).
- [ ] Launch `ait codeagent invoke explore` with a `codex/*` agent string — confirm the composer DOES show /plan (plan mode still forced).
- [ ] Run `ait skillrun qa <id> --agent-string codex/<model>` then `ait skillrun pick <id> --agent-string codex/<model>` — confirm qa launches directly (no aitask_codex_plan_invoke) and pick uses the plan helper (parity with `ait codeagent`).
