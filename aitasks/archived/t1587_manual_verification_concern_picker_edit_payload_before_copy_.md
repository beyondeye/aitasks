---
priority: medium
effort: medium
depends: [1582]
issue_type: manual_verification
status: Done
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1582]
assigned_to: dario-e@beyond-eye.com
anchor: 1037
followup_kind: manual_verification
created_at: 2026-08-24 17:22
updated_at: 2026-08-24 18:15
completed_at: 2026-08-24 18:15
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1582

## Verification Checklist

- [x] TODO: verify .aitask-scripts/monitor/monitor_shared.py end-to-end in tmux — the concern picker in a live `ait minimonitor` companion pane — PASS 2026-08-24 18:14 auto: live tmux -- real ait minimonitor companion pane (40 cols) beside a real agent window, real capture -> parse -> picker
- [x] Follow a real agent with a shadow, press `c`, tick a row, press `e`: the editor opens seeded with the exact outgoing payload from a REAL concern block (every automated test uses a synthetic host App, never a real capture -> parse -> forward round trip) — PASS 2026-08-24 18:14 auto: live -- c, Space, e opened the editor seeded with the exact built payload (preamble + blank + canonical marker) from a real pane-captured block; agent/shadow were fixture panes, everything downstream was production code
- [x] Select a span with shift+left/right, type over it, `ctrl+s`, then `Enter` — paste and confirm the clipboard holds the edited text, in BOTH `ait minimonitor` and the full `ait monitor` — PASS 2026-08-24 18:14 auto: live -- shift+right span typed over in minimonitor, shift+left span typed over in ait monitor; ctrl+s + Enter; tmux paste-buffer into a sink pane returned the edited text byte-for-byte in both
- [x] Press `e` with nothing ticked for forwarding; confirm the refusal notify appears rather than an empty editor box — PASS 2026-08-24 18:14 auto: live -- e with nothing ticked: no editor, toast 'Nothing marked for forwarding - press Space on a row first'
- [x] Empty the editor buffer and press `ctrl+s`; confirm the editor stays open with a warning and that Esc still cancels — PASS 2026-08-24 18:14 auto: live -- F7+Backspace emptied the buffer, ctrl+s kept the editor open with 'Editor is empty - nothing to copy. Esc to cancel, or type a payload.'; Esc returned to the intact picker with the tick preserved
- [x] Edit the payload, then tick another row, then `Enter`; confirm the warning fires and the REGENERATED payload (not the edit) reaches the clipboard — PASS 2026-08-24 18:14 auto: live -- edited, then ticked a second row, then Enter: both toasts fired ('Selection changed after editing...' + 'Concerns copied to clipboard.') and the clipboard held the regenerated 2-concern payload, not the edit
- [x] On a run where the payload was edited, also reject a concern; confirm the rejection store received the ORIGINAL marker text (reopen `R` on the next round and check it still matches) — PASS 2026-08-24 18:14 auto: live -- same run edited the payload and rejected a concern: clipboard got the mangled edit, rejected.md and the R view both hold the original canonical marker line
- [x] Click Save and Cancel with the mouse at 80 columns; confirm they behave exactly as `ctrl+s` and `Esc` — PASS 2026-08-24 18:14 auto: live -- SGR mouse clicks at 80 cols: Save committed the edit and Save on an empty buffer showed the same refusal (== ctrl+s); Cancel dismissed with no override (== Esc)
