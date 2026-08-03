---
priority: medium
effort: medium
depends: [1382]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1382]
created_at: 2026-08-03 16:34
updated_at: 2026-08-03 16:34
boardidx: 19456
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1382

## Verification Checklist

- [ ] Rename an `agent-*` window in a running session (`tmux rename-window -t <win> noam_bugs`); `ait monitor` shows exactly ONE `OTHER` card for it — the companion minimonitor pane is gone
- [ ] From another session's minimonitor, the renamed window appears under the `── other (n) ──` header
- [ ] On an `OTHER` card in minimonitor, `s` switches tmux focus to that window
- [ ] On an `OTHER` card in minimonitor, `d` / `i` / `space` each report a guard notice and change nothing
- [ ] On an `OTHER` card in `ait monitor`, `space` now reports "Marks apply to agent panes only" (shared-mixin change — this used to succeed)
- [ ] In the minimonitor INSIDE the renamed window, `k` / `n` / `e` / `I` report "no followed agent" (deliberate: a rename takes the window out of the agent rotation)
- [ ] In that same minimonitor, the docked panel still shows the OLD window name under `── this agent ──` — one-shot by design, expected, not a defect
- [ ] Relaunch the minimonitor inside the renamed window; its docked panel now builds at all and reads `── this window ──` with the new name (before this task it was never built)
- [ ] The `── other (n) ──` header and the `○` rows are not clipped in a real 40-column minimonitor pane — confirm with a tmux capture, not only the headless renderer
- [ ] Rename the window back to `agent-*`; both TUIs restore the agent presentation within one 3s refresh tick (already-built docked panels do not change)
- [ ] Launch a fresh `ait monitor` and watch another monitor/minimonitor list it: the launching companion pane must never appear as a card, not even for one tick during its startup (the exec-in-place transition the memo must not hide)
- [ ] With several agent windows open, confirm no visible refresh stutter in either TUI after the companion probe was widened to every pane
