---
priority: medium
effort: medium
depends: [t1149_2, t1149_3]
issue_type: manual_verification
status: Done
labels: [verification, manual]
verifies: [t1149_2, t1149_3]
assigned_to: dario-e@beyond-eye.com
anchor: 1149
created_at: 2026-07-15 18:49
updated_at: 2026-07-19 12:43
completed_at: 2026-07-19 12:43
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t1149_2] Run `bash tests/test_chatlink_tui.sh` — PASS 2026-07-19 12:40
- [x] [t1149_2] `ait chatlink` with a broken/partial config shows per-check severity and fix hints; with a valid config shows all-pass — PASS 2026-07-19 12:41
- [x] [t1149_2] Panel stays responsive with docker stopped/absent — PASS 2026-07-19 12:41
- [x] [t1149_3] Wizard Pilot walk end-to-end writes the expected config (`bash tests/test_chatlink_tui.sh`) — PASS 2026-07-19 12:40
- [x] [t1149_3] Writer preservation: pre-existing `sandbox_env_passthrough: [FOO_KEY]` and an unknown future key survive a ceilings-only save; output parses via `load_config` with the same effective values — PASS 2026-07-19 12:40
- [x] [t1149_3] Manual: `ait chatlink` → `w` → complete flow → config written to working tree, token file 0600, final preflight screen shows results; the TUI made no git commit — PASS 2026-07-19 12:42
- [x] [t1149_3] Aborting mid-wizard leaves the config file and token file untouched — PASS 2026-07-19 12:40
