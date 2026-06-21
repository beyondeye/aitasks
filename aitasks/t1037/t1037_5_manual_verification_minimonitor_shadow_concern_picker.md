---
priority: medium
effort: medium
depends: [t1037_4]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1037_1, 1037_2, 1037_3, 1037_4]
anchor: 1037
created_at: 2026-06-21 11:48
updated_at: 2026-06-21 11:48
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1037_1] parse_concerns extracts items from a real aitask_shadow_capture.sh snapshot, including a wrap-joined long-body concern (tmux visual wrapping rejoins).
- [ ] [t1037_1] Unknown priority degrades to low without dropping the item; multi-block input returns only the last block.
- [ ] [t1037_2] A live shadow run (plan-challenge) emits the ===AITASK-CONCERNS=== block after its prose list; the emitted block parses cleanly via concern_parser.
- [ ] [t1037_2] plan-challenge.md (and plan-assumptions.md if changed) are byte-identical across .claude / .agents / .opencode trees.
- [ ] [t1037_3] ConcernPickerModal renders one row per concern with ☑/☐ glyph (marked = bold yellow), priority badge, and region label; toggling, select-all, copy-all, and Esc behave correctly in the narrow companion-pane variant.
- [ ] [t1037_4] In a live tmux session: launch a code-agent, press 'e' to spawn the shadow, have the shadow emit a concern block, then press 'c' in minimonitor — the picker opens populated from the shadow pane.
- [ ] [t1037_4] Auto-offer surfaces (once) when a fresh concern block appears on the shadow pane; pressing 'c' with no shadow running shows the graceful warning.
- [ ] [END-TO-END] Tick a subset of concerns, confirm, and verify the system clipboard holds the preamble + exactly the selected concern blocks verbatim; paste into the code-agent pane and confirm it arrives intact (no escape damage). Confirm the shadow remained advisory-only (no keystrokes injected by minimonitor).
- [ ] [END-TO-END] Verify clipboard portability on the target platform (wl-copy/xclip on Linux, OSC 52 over SSH/tmux) via app.copy_to_clipboard().
