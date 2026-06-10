---
priority: medium
effort: medium
depends: [672]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [672]
created_at: 2026-06-10 13:51
updated_at: 2026-06-10 13:51
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t672

## Verification Checklist

- [ ] Launch a brainstorm session whose initializer agent fails (status Error/Aborted); confirm the polling indicator (#initializer_polling_indicator) stops and is no longer flashing.
- [ ] Confirm the error toast no longer contains "Watching for output" and still shows the "press ctrl+r or run `ait brainstorm apply-initializer <N>`" retry hint.
- [ ] Confirm ctrl+r still forces an apply retry (action_retry_initializer_apply) after the agent has failed.
- [ ] Confirm that when the agent wrote a complete delimited output (all four NODE_YAML/PROPOSAL delimiters) before failing, the one-shot apply on the Error/Aborted branch still imports the proposal into n000_init.
- [ ] Confirm no background timer keeps re-polling after Error/Aborted (no 30s slow-watcher) — e.g. the session does not silently re-apply output minutes later.
