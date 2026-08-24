---
priority: medium
effort: medium
depends: [1582]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1582]
anchor: 1037
followup_kind: manual_verification
created_at: 2026-08-24 17:22
updated_at: 2026-08-24 17:22
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1582

## Verification Checklist

- [ ] TODO: verify .aitask-scripts/monitor/monitor_shared.py end-to-end in tmux — the concern picker in a live `ait minimonitor` companion pane
- [ ] Follow a real agent with a shadow, press `c`, tick a row, press `e`: the editor opens seeded with the exact outgoing payload from a REAL concern block (every automated test uses a synthetic host App, never a real capture -> parse -> forward round trip)
- [ ] Select a span with shift+left/right, type over it, `ctrl+s`, then `Enter` — paste and confirm the clipboard holds the edited text, in BOTH `ait minimonitor` and the full `ait monitor`
- [ ] Press `e` with nothing ticked for forwarding; confirm the refusal notify appears rather than an empty editor box
- [ ] Empty the editor buffer and press `ctrl+s`; confirm the editor stays open with a warning and that Esc still cancels
- [ ] Edit the payload, then tick another row, then `Enter`; confirm the warning fires and the REGENERATED payload (not the edit) reaches the clipboard
- [ ] On a run where the payload was edited, also reject a concern; confirm the rejection store received the ORIGINAL marker text (reopen `R` on the next round and check it still matches)
- [ ] Click Save and Cancel with the mouse at 80 columns; confirm they behave exactly as `ctrl+s` and `Esc`
