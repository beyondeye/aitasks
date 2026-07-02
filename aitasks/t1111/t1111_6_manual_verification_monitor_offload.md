---
priority: medium
effort: medium
depends: [t1111_5]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1111_1, 1111_2, 1111_3, 1111_4, 1111_5]
anchor: 1111
created_at: 2026-07-02 14:44
updated_at: 2026-07-02 14:44
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] Setup: launch `ait monitor` against ~8-10 live agents in `agent-`-prefixed tmux windows (real `agent-pick-*`, or the synthetic `agent-perf-*` windows from t1111_4's recipe — panes MUST be in `agent-`-named windows to classify as AGENT).
- [ ] [all-idle switch] With all agents idle, arrow focus-switch between panes is instant (no ~0.5s lag).
- [ ] [active switch] With >=1 agent actively producing ANSI-heavy output (spinner/colors), focus-switch to/among agents stays instant — the user-reported regression must be gone.
- [ ] [tick] The 3s status refresh no longer freezes input, both when idle and when agents are active.
- [ ] [gates] Gate columns still render and stay live as a task's gate ledger grows (mtime-driven update).
- [ ] [preview] Content preview renders correctly; scroll and pause/LIVE behavior are intact after switching.
- [ ] [detection] Idle detection and awaiting-input (prompt) detection still fire correctly for AGENT panes.
- [ ] [soak] Concurrency soak: hold/repeat arrow-nav continuously for ~1 min while >=2 agent- windows churn; confirm no crash, no wrong-pane preview, no stuck idle badge, and no runaway thread/memory growth (race-safety gate for the t1111_4/t1111_5 offload, per plan Risk invariants A-G).
- [ ] Cleanup: kill any synthetic scratch session (e.g. `tmux kill-session -t t1111perf`).
