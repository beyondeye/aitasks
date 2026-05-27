---
priority: medium
effort: medium
depends: [739]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [739]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-18 15:40
updated_at: 2026-05-27 08:10
boardidx: 90
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t739

## Verification Checklist

- [x] Open `ait brainstorm <task>` TUI with an existing session; trigger an explore operation with 2 parallel explorers; wait for both Completed; confirm TUI auto-applies both nodes and DAG refreshes. — PASS 2026-05-27 08:10
- [x] After auto-apply, inspect `br_graph_state.yaml`: head advanced, `next_node_id` incremented, `active_dimensions` extended with any keys the explorer emitted in `NEW_DIMENSIONS`. — PASS 2026-05-27 08:10
- [fail] Corrupt one explorer's `_output.md` (e.g. truncate the NODE_YAML block), press `ctrl+shift+x`, verify the apply banner shows the `apply-explorer` CLI hint. — FAIL 2026-05-27 08:10 follow-up t837
- [x] Run the suggested CLI command (`ait brainstorm apply-explorer <task> <agent>`) and confirm it surfaces the same error. — PASS 2026-05-27 08:10
- [x] Verify the new `apply-explorer` row appears in `ait brainstorm --help`. — PASS 2026-05-27 08:10
- [x] TODO: verify `brainstorm_app.py` end-to-end in tmux (interactive surface). — PASS 2026-05-27 08:10
