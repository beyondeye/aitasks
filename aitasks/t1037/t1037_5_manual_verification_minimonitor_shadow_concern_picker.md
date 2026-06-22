---
priority: medium
effort: medium
depends: [t1037_4]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [t1037_1, t1037_2, t1037_3, t1037_4]
assigned_to: dario-e@beyond-eye.com
anchor: 1037
created_at: 2026-06-21 11:48
updated_at: 2026-06-22 16:47
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t1037_1] parse_concerns extracts items from a real aitask_shadow_capture.sh snapshot, including a wrap-joined long-body concern (tmux visual wrapping rejoins). — PASS 2026-06-22 16:46 Verified by python3 -m unittest tests.test_concern_parser tests.test_concern_picker_modal tests.test_minimonitor_concern_action (33 tests OK) plus bash tests/test_shadow_capture.sh (12/12 OK, including live tmux wrap-join -J).
- [x] [t1037_1] Unknown priority degrades to low without dropping the item; multi-block input returns only the last block. — PASS 2026-06-22 16:46 Verified by tests.test_concern_parser: test_unknown_priority_degrades_to_low and test_multi_block_last_wins passed in the 33-test unittest run.
- [defer] [t1037_2] A live shadow run (plan-challenge) emits the ===AITASK-CONCERNS=== block after its prose list; the emitted block parses cleanly via concern_parser. — DEFER 2026-06-22 16:46 Deferred: static producer/parser contract verified (.claude plan-challenge and plan-assumptions include AITASK-CONCERNS fences; parser tests pass), but a live shadow plan-challenge run was not launched/observed in this execution environment.
- [skip] [t1037_2] plan-challenge.md (and plan-assumptions.md if changed) are byte-identical across .claude / .agents / .opencode trees. — SKIP 2026-06-22 16:46 Not applicable after t1037_2 architecture correction: .agents and .opencode contain no shadow plan-*.md files; their aitask-shadow SKILL.md files delegate to .claude/skills/aitask-shadow/SKILL.md as source of truth.
- [x] [t1037_3] ConcernPickerModal renders one row per concern with ☑/☐ glyph (marked = bold yellow), priority badge, and region label; toggling, select-all, copy-all, and Esc behave correctly in the narrow companion-pane variant. — PASS 2026-06-22 16:46 Verified by tests.test_concern_picker_modal plus direct render check: rows render checkbox glyphs, selected mark is bold yellow, priority badge and region label are present, modal narrow=True is supported, and select-all/copy-all/Esc behavior passed in unittest.
- [defer] [t1037_4] In a live tmux session: launch a code-agent, press 'e' to spawn the shadow, have the shadow emit a concern block, then press 'c' in minimonitor — DEFER 2026-06-22 16:47 Deferred: requires an observed live tmux flow with a launched code-agent, shadow spawn via 'e', concern emission, and pressing 'c' in minimonitor. Pure capture/parser/action pieces passed, but the full live flow was not launched here.
- [x] [t1037_4] Auto-offer surfaces (once) when a fresh concern block appears on the shadow pane; pressing 'c' with no shadow running shows the graceful warning. — PASS 2026-06-22 16:47 Verified by tests.test_minimonitor_concern_action: closed block fires once, unchanged surrounding text does not re-fire, changed concern re-fires, unclosed block does not fire, and no-shadow 'c' path notifies without clipboard/modal side effects.
- [defer] [END-TO-END] Tick a subset of concerns, confirm, and verify the system clipboard holds the preamble + exactly the selected concern blocks verbatim; paste into the code-agent pane and confirm it arrives intact (no escape damage). Confirm the shadow remained advisory-only (no keystrokes injected by minimonitor). — DEFER 2026-06-22 16:47 Deferred: build_clipboard_payload subset/preamble behavior and no-side-effect-before-confirm are covered by tests, but live clipboard contents, paste into code-agent pane, escape integrity, and advisory-only no-keystroke-injection were not observed end-to-end.
- [defer] [END-TO-END] Verify clipboard portability on the target platform (wl-copy/xclip on Linux, OSC 52 over SSH/tmux) via app.copy_to_clipboard(). — DEFER 2026-06-22 16:47 Deferred: app.copy_to_clipboard call path is verified in minimonitor tests, but target-platform clipboard portability (wl-copy/xclip or OSC 52 over SSH/tmux) was not exercised interactively in this environment.
