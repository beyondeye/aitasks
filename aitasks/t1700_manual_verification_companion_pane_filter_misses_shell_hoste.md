---
priority: medium
effort: medium
depends: [1686]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1686]
anchor: 1382
followup_kind: manual_verification
created_at: 2026-09-02 23:14
updated_at: 2026-09-02 23:14
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1686

## Verification Checklist

- [ ] Verify .aitask-scripts/monitor/monitor_core.py end-to-end in tmux (interactive surface changed)
- [ ] Run `ait minimonitor` from an interactive shell inside a live agent window; confirm every OTHER monitor/minimonitor lists that window exactly once (t1686 verified this on an isolated server; re-verify against the real ait socket)
- [ ] Confirm the same window is listed once in `ait monitor` too, not just `ait minimonitor` — cross-TUI parity was never exercised against a real TUI
- [ ] Kill the last real agent in a window holding a shell-hosted companion: the WINDOW must close, not just the pane
- [ ] In a window holding two real agents with the unmarked one listed last, kill one: only the PANE must die and the sibling must survive
- [ ] Exit a shell-hosted minimonitor WITHOUT closing its pane; the leftover shell pane must reappear as an ordinary pane on the very next tick (stale marker, no TTL wait)
- [ ] Press the companion-jump affordance (prefer_companion) on an agent whose minimonitor was started from a shell: focus must land on the companion pane, not fall back to the agent pane
