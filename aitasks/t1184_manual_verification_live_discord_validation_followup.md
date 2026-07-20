---
priority: medium
effort: medium
depends: [1149_5]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1149_5]
created_at: 2026-07-20 12:37
updated_at: 2026-07-20 12:37
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1149_5

## Verification Checklist

- [ ] [t1149_5] Real bot token, valid config: run wizard live validation — all four rows pass (login, intents, channel visible, permissions)
- [ ] [t1149_5] Revoked/garbage token → live_login row fails with the token fix hint
- [ ] [t1149_5] Privileged intent toggled off in the portal → live_intents row fails (names both intents); no hang
- [ ] [t1149_5] Bot removed from the intake channel/server → live_channel_visible row fails
- [ ] [t1149_5] A required channel permission revoked → live_permissions row lists the missing name(s)
- [ ] [t1149_5] UI never hangs: validation completes or times out within ~30s; Continue works mid-run; skipping the step entirely works
- [ ] [t1149_5] Wizard save succeeds regardless of failing live rows (advisory-only); token value never appears anywhere on screen
