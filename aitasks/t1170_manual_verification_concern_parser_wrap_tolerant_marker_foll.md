---
priority: medium
effort: medium
depends: [1167]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1167]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-20 09:48
updated_at: 2026-07-20 12:17
boardidx: 30
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1167

## Verification Checklist

- [x] verify .aitask-scripts/monitor/concern_parser.py end-to-end in tmux (unit tests cover the pure parser only; the capture path is untested) — PASS 2026-07-20 12:17 auto: disposable 55-column tmux pane captured through aitask_shadow_capture.sh; split full-path marker parsed and strict auto-offer predicate returned true
- [defer] Spawn a Codex shadow via minimonitor `e` on a plan review at a narrow pane width (~55 cols), with a concern whose region is a long full path — DEFER 2026-07-20 12:17 auto: requires a live user-driven Codex shadow launched with minimonitor e and visual narrow-pane confirmation
- [defer] Confirm the picker renders the rejoined region label readably, and that forwarding the selected concern to the followed agent produces the correct `- [priority | region] body` payload — DEFER 2026-07-20 12:17 auto: canonical payload was reconstructed from live tmux capture, but picker readability and forwarding to a followed live agent need interactive confirmation
- [x] Confirm a normal short-region shadow review (producer rule respected) is unaffected — PASS 2026-07-20 12:17 auto: full Python regression suite passed (unittest fallback); parser and minimonitor concern-action coverage retain short-region behavior
- [x] Confirm a marker split wider than 3 rows is still dropped without crashing or corrupting adjacent concerns (the documented envelope limit) — PASS 2026-07-20 12:17 auto: TestSplitMarkerJoin over-bound negative control passed; four-row split is dropped without swallowing the following valid marker
