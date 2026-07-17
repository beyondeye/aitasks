---
priority: medium
effort: medium
depends: [t1157_7]
issue_type: documentation
status: Ready
labels: [workflows, remote, web_site, installation]
gates: [risk_evaluated]
anchor: 1157
created_at: 2026-07-17 16:53
updated_at: 2026-07-17 16:53
---

## Context

Eighth child of t1157. Document the multi-workflow host and migration only after the configuration, TUI, bug-intake, and remote-explore behavior is implemented. The documentation must make the distinction between focused bug intake and open-ended remote explore obvious, explain explicit approval/resume behavior, and give safe migration/operations guidance for one bot across projects/guilds.

## Key files to modify

- `website/content/docs/workflows/bug-report-intake.md`: revised bug workflow semantics, visible budgets, proposal/approval/resume behavior.
- New or extended website workflow documentation for remote explore and multi-workflow Chatlink setup.
- `aidocs/chat/chatlink_runtime.md`, `chatlink_sandbox.md`, and `qa_relay_protocol.md`: host/config/session/attempt contracts.
- Setup/known-issue documentation as required by the final implementation.

## Reference files

- Existing chatlink website workflow docs and t1149 documentation child records.
- t1157 child plans and archived sibling implementation notes.
- Documentation conventions and current source, not stale planning prose.

## Implementation plan

1. Re-read all landed t1157 child implementation records and derive docs from actual behavior.
2. Document layered project/host configuration, one-bot/many-guild setup, global host lifecycle, migration from legacy singleton config, and secret handling.
3. Explain channel triggers, intent selection, visible budget semantics, checkpoint/proposal states, explicit approval, Request Changes, Resume, Restart, Abort, and seven-day expiry.
4. State capability boundaries clearly: sandbox read-only, no implementation handoff, Discord-first host, and separate multi-agent runtime work.
5. Update runtime/protocol docs with durable session vs attempt identity, state transitions, cleanup/retention, and gateway validation ownership.
6. Add troubleshooting entries for duplicate channels, missing registered projects, expired/stale controls, paused attempts, and no-task-on-timeout behavior.

## Verification

- Website build succeeds and internal links resolve.
- Examples match final config/schema and current TUI/Discord text.
- No secret/token examples are committed or exposed; legacy/manual fallback remains documented where supported.
