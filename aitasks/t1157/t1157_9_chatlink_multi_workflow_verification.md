---
priority: high
effort: high
depends: [t1157_8]
issue_type: test
status: Ready
labels: [testing, workflows, remote, crash_recovery, python]
gates: [risk_evaluated]
anchor: 1157
created_at: 2026-07-17 16:54
updated_at: 2026-07-17 16:54
---

## Context

Ninth implementation child of t1157. Consolidate the multi-workflow regression and soak coverage after all feature children land. This child incorporates the complete randomized concurrency, restart, completion-vs-death, and single-writer requirements merged from t1144, expanded for durable sessions, multiple projects, workflows, budgets, proposals, approvals, resumes, and revisions.

## Key files to modify

- `tests/test_chatlink_flow.sh`: deterministic seeded multi-session/multi-project workflow stress harness.
- `tests/test_chatlink_daemon.sh`, `test_chatlink_relay.sh`, `test_chatlink_config.sh`, `test_chatlink_tui.sh`, and sandbox tests as needed.
- New focused tests for proposal approval, retention, controls, and live/Manual Verification handoff.
- Test documentation or helper scripts only when required for reproducible runs.

## Reference files

- Folded t1144 requirements embedded in the parent task.
- Existing `Env`, `FakeLauncher`, spy creation script, and `wait_until` helpers in `tests/test_chatlink_flow.sh`.
- All t1157 sibling plans and archived implementation notes.

## Implementation plan

1. Build a seeded randomized harness covering N sessions across workflow types, projects, guilds, and attempts. Print the seed on failure for reproduction.
2. Interleave intake/intent events, questions/answers, checkpoint/proposal writes, approval/revision/resume/restart actions, payload completion, agent death, queue saturation, and repeated daemon restarts.
3. Assert strict route isolation, one terminal outcome per attempt/session, supersession correctness, no lost level-triggered event, and one sequential mutation writer.
4. Cover deadline/retention boundaries: soft synthesis, hard pause, approval outside sandbox lifetime, seven-day expiry, stale control rejection, and latest-HEAD resume metadata.
5. Exercise multi-project container labels/reaping and gateway task creation routing without live platform calls.
6. Add opt-in live smoke/manual checklist artifacts for two workflow channels, explicit approval, revision, resume/restart, budgets, and the TUI.

## Verification

- All chatlink automated suites pass repeatedly with fixed and randomized seeds.
- Fault injection never creates cross-talk, double creation, or partial task/fold mutation.
- Existing single-repo bug-intake test behavior remains covered.
- Live validation instructions are complete enough for the aggregate manual-verification sibling.
