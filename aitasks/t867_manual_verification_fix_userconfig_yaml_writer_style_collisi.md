---
priority: medium
effort: medium
depends: [864]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [864]
created_at: 2026-05-31 10:53
updated_at: 2026-05-31 10:53
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

- [ ] Launch ait board (and one other TUI, e.g. ait monitor) on a workspace whose userconfig.yaml has both shortcuts and last_used_labels — confirm they draw without a yaml ParserError crash at import (the original t864 symptom).
- [ ] End-to-end cycle: open the in-TUI shortcut editor and save a custom shortcut (Python shortcut_persist writer), then run `ait create` and pick one or more labels (bash set_last_used_labels writer); re-launch ait board and confirm it still starts and userconfig.yaml is valid YAML with flow-style last_used_labels and the shortcuts block intact.
- [ ] Confirm `ait create`'s interactive label picker pre-fills the previously-used labels after the shortcut-save + create cycle (get_last_used_labels reads correctly).
