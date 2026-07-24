---
priority: medium
effort: medium
depends: [1187]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1187]
created_at: 2026-07-24 10:56
updated_at: 2026-07-24 10:56
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1187

## Verification Checklist

- [ ] Re-run t1170 item #2: spawn a Codex shadow via minimonitor `e` on a plan review at a narrow pane width (~55 cols), with a concern whose region is a long full path — confirm the "Shadow raised concerns — press 'c' to pick" auto-offer FIRES (pre-fix it silently reported no concerns)
- [ ] Press `c` on that shadow and confirm it forwards the canonical `- [priority | region] body` payload intact, including a region whose bracket was hard-wrapped by the Codex renderer
- [ ] Force the truncated-head path with SHADOW_PLAN_CAPTURE_LINES=40 and confirm `c` reports the capture window explicitly ("Shadow's concern block is cut off above the capture window — increase SHADOW_PLAN_CAPTURE_LINES") instead of "No concerns detected on the shadow pane"
- [ ] Confirm the truncation warning appears at most once per shadow pane per episode (not on every ~3s refresh tick), and re-arms after a complete concern block is seen on that pane
- [ ] Confirm a genuinely concern-free shadow pane still reports the plain "No concerns detected on the shadow pane" and raises no capture-window warning
- [ ] Verify the minimonitor concern picker end-to-end in a live tmux session (interactive surface: minimonitor_app.py / concern_parser.py) — auto-offer, `c` picker modal, and forwarding to the followed pane
- [ ] Confirm a plan-review shadow now emits short regions (≤ ~30 chars, no full repo paths) per the rule newly stated in plan-challenge.md / plan-assumptions.md / plan-diagnose-errors.md
