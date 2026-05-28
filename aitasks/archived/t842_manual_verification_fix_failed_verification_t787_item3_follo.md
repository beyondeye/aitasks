---
priority: medium
effort: medium
depends: [837]
issue_type: manual_verification
status: Done
labels: [verification, manual]
verifies: [837]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-27 11:10
updated_at: 2026-05-28 09:24
completed_at: 2026-05-28 09:24
boardidx: 40
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t837

## Verification Checklist

- [x] Trigger an explore op with 2 parallel explorers in `ait brainstorm <task>`, let auto-apply run, confirm both nodes are added to the DAG and no banner is shown. — PASS 2026-05-28 09:23 tmux TUI session .aitask-crews/crew-brainstorm-842 auto-applied two completed explorer outputs; DAG showed n001_retry_variant_a and n002_retry_variant_b with no failure banner.
- [x] Truncate one explorer's `_output.md` inside its NODE_YAML block (delete contents between `NODE_YAML_START` and `NODE_YAML_END`), press `ctrl+shift+x`, expect the apply banner to show "Explorer <agent> apply failed: ... — run `ait brainstorm apply-explorer <task> <agent>` to retry". — PASS 2026-05-28 09:23 Corrupted explorer_001b NODE_YAML block, sent Textual ctrl+shift+x key sequence via tmux, and observed banner: Explorer explorer_001b apply failed ... run ait brainstorm apply-explorer 842 explorer_001b to retry.
- [x] Run the suggested CLI command and confirm it surfaces the same error. — PASS 2026-05-28 09:23 Ran ait brainstorm apply-explorer 842 explorer_001b; it exited nonzero with APPLY_FAILED:explorer NODE_YAML block did not parse as a dict, matching the TUI banner error.
- [x] After clearing all corrupted outputs (or in a session with no Completed explorers), press `ctrl+shift+x` and expect the toast notification "No completed explorer agents to retry." (new behavior — PASS 2026-05-28 09:23 Changed synthetic explorer statuses to Waiting so no Completed explorers remained; pressing ctrl+shift+x in tmux showed toast: No completed explorer agents to retry.
- [x] TODO: verify `brainstorm_app.py` end-to-end in tmux (interactive surface). — PASS 2026-05-28 09:23 Verified brainstorm_app.py end-to-end through a tmux-hosted Textual TUI: session launch, auto-apply poll, retry banner, CLI fallback, and no-candidates toast.
