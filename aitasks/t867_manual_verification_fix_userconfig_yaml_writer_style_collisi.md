---
priority: medium
effort: medium
depends: [864]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [864]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-31 10:53
updated_at: 2026-06-02 09:53
boardidx: 100
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t864

## Verification Checklist

- [x] Launch ait board (and one other TUI, e.g. ait monitor) on a workspace whose userconfig.yaml has both shortcuts and last_used_labels — PASS 2026-06-02 09:53 auto: board+monitor both launch & draw (live tmux, no traceback); import-time load_user_overrides() reads a both-blocks config cleanly and degrades to {} on a corrupted file instead of raising ParserError
- [x] End-to-end cycle: open the in-TUI shortcut editor and save a custom shortcut (Python shortcut_persist writer), then run `ait create` and pick one or more labels (bash set_last_used_labels writer); re-launch ait board and confirm it still starts and userconfig.yaml is valid YAML with flow-style last_used_labels and the shortcuts block intact. — PASS 2026-06-02 09:53 auto: real shortcut_persist.save_override (Python) then bash set_last_used_labels end-to-end -> valid YAML, flow-style last_used_labels, shortcuts block intact, no orphaned '- item'; reload overrides OK
- [x] Confirm `ait create`'s interactive label picker pre-fills the previously-used labels after the shortcut-save + create cycle (get_last_used_labels reads correctly). — PASS 2026-06-02 09:53 auto: bash get_last_used_labels and python get-labels both read back the labels set in item 2 (ait create pre-fill source)
