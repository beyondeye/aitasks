---
priority: medium
effort: medium
depends: [t1111_5]
issue_type: manual_verification
status: Done
labels: [verification, manual]
verifies: [t1111_1, t1111_2, t1111_3, t1111_4, t1111_5]
assigned_to: dario-e@beyond-eye.com
anchor: 1111
created_at: 2026-07-02 14:44
updated_at: 2026-07-05 23:51
completed_at: 2026-07-05 23:51
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] Setup: launch `ait monitor` against ~8-10 live agents in `agent-`-prefixed tmux windows (real `agent-pick-*`, or the synthetic `agent-perf-*` windows from t1111_4's recipe — PASS 2026-07-05 23:50 Synthetic t1111perf session created with 8 agent-classified windows plus monitor; three churn panes, task-named gate pane, and prompt pane used.
- [x] [all-idle switch] With all agents idle, arrow focus-switch between panes is instant (no ~0.5s lag). — PASS 2026-07-05 23:50 All-idle single-session roster showed 8 idle synthetic agents; arrow focus switched immediately and preview updated to agent-perf-1.
- [x] [active switch] With >=1 agent actively producing ANSI-heavy output (spinner/colors), focus-switch to/among agents stays instant — PASS 2026-07-05 23:50 With agent-perf-2/3/4 producing ANSI-heavy output, focus switched to active panes and preview updated without observed lag.
- [x] [tick] The 3s status refresh no longer freezes input, both when idle and when agents are active. — PASS 2026-07-05 23:50 Multiple 3s refresh ticks completed while three panes churned; monitor remained responsive and state counts updated.
- [x] [gates] Gate columns still render and stay live as a task's gate ledger grows (mtime-driven update). — PASS 2026-07-05 23:50 agent-pick-1111 row showed gates: 0/1 pass, 1 pending, then updated live to gates: 1/1 pass after appending terminal gate result.
- [x] [preview] Content preview renders correctly; scroll and pause/LIVE behavior are intact after switching. — PASS 2026-07-05 23:50 Preview rendered idle and ANSI-heavy active panes, stayed matched after focus switches, and showed LIVE in preview zone.
- [x] [detection] Idle detection and awaiting-input (prompt) detection still fire correctly for AGENT panes. — PASS 2026-07-05 23:50 Idle/active classification worked for agent panes; bottom-positioned Yes, proceed (y) prompt was detected as PROMPT with kind codex_yes_proceed.
- [x] [soak] Concurrency soak: hold/repeat arrow-nav continuously for ~1 min while >=2 agent- windows churn; confirm no crash, no wrong-pane preview, no stuck idle badge, and no runaway thread/memory growth (race-safety gate for the t1111_4/t1111_5 offload, per plan Risk invariants A-G). — PASS 2026-07-05 23:50 Ran ~1 minute repeated Up/Down navigation while three ANSI-heavy panes churned; monitor pane stayed alive, no wrong preview/stuck badge observed, gate state remained correct.
- [x] Cleanup: kill any synthetic scratch session (e.g. `tmux kill-session -t t1111perf`). — PASS 2026-07-05 23:51 Killed synthetic t1111perf tmux session after verification.
