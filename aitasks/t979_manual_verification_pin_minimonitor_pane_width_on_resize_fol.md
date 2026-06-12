---
priority: medium
effort: medium
depends: [978]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [978]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-11 16:35
updated_at: 2026-06-12 11:31
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t978

## Verification Checklist

- [x] ait pick <N> → confirm the agent-* window spawns a minimonitor companion pane at ~40 columns — PASS 2026-06-12 11:26 auto: companion pane spawns at 40 cols (tmux split -l 40); minimonitor renders. Verified on isolated socket.
- [fail] Detach tmux (prefix d) → resize the terminal much wider → reattach (tmux attach) → confirm the minimonitor pane snaps back to ~40 columns instead of staying proportionally wide (the reported bug) — FAIL 2026-06-12 11:28 follow-up t981
- [skip] Resize the terminal live (no detach) → confirm the minimonitor pane stays pinned to ~40 columns — SKIP 2026-06-12 11:31 FAILS on widening: same root cause as t981 (immediate control-client resize-pane lost during window-growth reflow). Shrink re-pins fine. Consolidated into t981, not a duplicate bug.
- [skip] Set tmux.minimonitor.width: 50 in aitasks/metadata/project_config.yaml, relaunch → confirm the pane pins to 50 columns — SKIP 2026-06-12 11:31 Config plumbing correct (target_width read from tmux.minimonitor.width); pin-on-growth inherits the t981 defect, so not independently passable. Tracked via t981.
- [x] TODO: verify .aitask-scripts/monitor/minimonitor_app.py end-to-end in tmux — PASS 2026-06-12 11:31 auto: e2e tmux verification performed via PTY-attached real client on isolated socket. Spawn-at-40 verified; growth re-pin broken -> t981. The 'verify e2e in tmux' TODO is satisfied.
