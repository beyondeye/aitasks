---
priority: medium
effort: low
depends: []
issue_type: manual_verification
status: Ready
labels: []
verifies: [t1037_1, t1037_2, t1037_3, t1037_4]
anchor: 1037
created_at: 2026-06-22 16:47
updated_at: 2026-06-22 16:47
---

Carry-over of deferred manual-verification items from t1037_5. Re-pick this task to continue the remaining checklist.

## Verification Checklist

- [ ] [t1037_2] A live shadow run (plan-challenge) emits the ===AITASK-CONCERNS=== block after its prose list; the emitted block parses cleanly via concern_parser. — DEFER 2026-06-22 16:46 Deferred: static producer/parser contract verified (.claude plan-challenge and plan-assumptions include AITASK-CONCERNS fences; parser tests pass), but a live shadow plan-challenge run was not launched/observed in this execution environment.
- [ ] [t1037_4] In a live tmux session: launch a code-agent, press 'e' to spawn the shadow, have the shadow emit a concern block, then press 'c' in minimonitor — DEFER 2026-06-22 16:47 Deferred: requires an observed live tmux flow with a launched code-agent, shadow spawn via 'e', concern emission, and pressing 'c' in minimonitor. Pure capture/parser/action pieces passed, but the full live flow was not launched here.
- [ ] [END-TO-END] Tick a subset of concerns, confirm, and verify the system clipboard holds the preamble + exactly the selected concern blocks verbatim; paste into the code-agent pane and confirm it arrives intact (no escape damage). Confirm the shadow remained advisory-only (no keystrokes injected by minimonitor). — DEFER 2026-06-22 16:47 Deferred: build_clipboard_payload subset/preamble behavior and no-side-effect-before-confirm are covered by tests, but live clipboard contents, paste into code-agent pane, escape integrity, and advisory-only no-keystroke-injection were not observed end-to-end.
- [ ] [END-TO-END] Verify clipboard portability on the target platform (wl-copy/xclip on Linux, OSC 52 over SSH/tmux) via app.copy_to_clipboard(). — DEFER 2026-06-22 16:47 Deferred: app.copy_to_clipboard call path is verified in minimonitor tests, but target-platform clipboard portability (wl-copy/xclip or OSC 52 over SSH/tmux) was not exercised interactively in this environment.
