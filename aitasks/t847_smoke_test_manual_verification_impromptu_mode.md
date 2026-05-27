---
priority: medium
effort: medium
depends: [843]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [843]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-27 14:47
updated_at: 2026-05-27 15:58
boardidx: 70
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t843

## Verification Checklist

- [ ] Confirm `./.aitask-scripts/aitask_verification_parse.sh --help` exits 0 and prints a usage line mentioning `seed`, `parse`, `set`, `summary`.
- [ ] Confirm `aitasks/metadata/profiles/fast.yaml` parses as valid YAML and contains a top-level `name:` field equal to `fast`.
- [ ] Confirm `aitasks/metadata/profiles/default.yaml` parses as valid YAML and contains a top-level `name:` field equal to `default`.
- [ ] Confirm the `manual_verification_auto_mode` key is documented in `.claude/skills/task-workflow/profiles.md`.
