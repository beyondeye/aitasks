---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Done
labels: []
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [t1037_1, t1037_2, t1037_3, t1037_4]
assigned_to: dario-e@beyond-eye.com
anchor: 1037
created_at: 2026-06-22 16:47
updated_at: 2026-07-23 16:38
completed_at: 2026-07-23 16:38
boardcol: tests
boardidx: 80
---

Carry-over of deferred manual-verification items from t1037_5. Re-pick this task to continue the remaining checklist.

## Verification Checklist

- [x] [t1037_2] A live shadow run (plan-challenge) emits the ===AITASK-CONCERNS=== block after its prose list; the emitted block parses cleanly via concern_parser. — PASS 2026-07-23 16:36
- [x] [t1037_4] In a live tmux session: launch a code-agent, press 'e' to spawn the shadow, have the shadow emit a concern block, then press 'c' in minimonitor — PASS 2026-07-23 16:36
- [x] [END-TO-END] Tick a subset of concerns, confirm, and verify the system clipboard holds the preamble + exactly the selected concern blocks verbatim; paste into the code-agent pane and confirm it arrives intact (no escape damage). Confirm the shadow remained advisory-only (no keystrokes injected by minimonitor). — PASS 2026-07-23 16:37
- [defer] [END-TO-END] Verify clipboard portability on the target platform (wl-copy/xclip on Linux, OSC 52 over SSH/tmux) via app.copy_to_clipboard(). — DEFER 2026-07-23 16:37
