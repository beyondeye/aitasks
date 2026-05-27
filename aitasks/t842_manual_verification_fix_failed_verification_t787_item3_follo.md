---
priority: medium
effort: medium
depends: [837]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [837]
created_at: 2026-05-27 11:10
updated_at: 2026-05-27 11:10
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t837

## Verification Checklist

- [ ] Trigger an explore op with 2 parallel explorers in `ait brainstorm <task>`, let auto-apply run, confirm both nodes are added to the DAG and no banner is shown.
- [ ] Truncate one explorer's `_output.md` inside its NODE_YAML block (delete contents between `NODE_YAML_START` and `NODE_YAML_END`), press `ctrl+shift+x`, expect the apply banner to show "Explorer <agent> apply failed: ... — run `ait brainstorm apply-explorer <task> <agent>` to retry".
- [ ] Run the suggested CLI command and confirm it surfaces the same error.
- [ ] After clearing all corrupted outputs (or in a session with no Completed explorers), press `ctrl+shift+x` and expect the toast notification "No completed explorer agents to retry." (new behavior — previously silent no-op).
- [ ] TODO: verify `brainstorm_app.py` end-to-end in tmux (interactive surface).
