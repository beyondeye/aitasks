---
priority: medium
effort: medium
depends: [t1216_4]
issue_type: manual_verification
status: Ready
labels: [verification, manual, tmux_destructive]
verifies: [t1216_1, t1216_2, t1216_3, t1216_4]
anchor: 1111
created_at: 2026-07-27 22:27
updated_at: 2026-07-28 18:27
---

## Pick-time safety guard — DO NOT pick from inside your working tmux

**Risk to running code agents: HIGH — this checklist deliberately kills agent
and shadow panes** ("Kill the shadow pane while the SHADOW zone is focused",
"Kill the followed agent: its shadow dies AND the monitor window survives").

**Safe to pick when:** you are in a shell whose tmux server carries no code
agents you care about — with `AITASKS_TMUX_SOCKET` unset that is the dedicated
`-L ait` server; check `tmux -L ait list-panes -a` first. Launch throwaway
agents for the verification rather than reusing ones doing real work.

Beyond the explicit kills, several items exercise `e` / `E`, which install a
persistent `pane-died` hook and `remain-on-exit on` on the **followed agent's**
pane (`lib/agent_launch_utils.py:1348-1370`). The cleanup that hook triggers
runs raw `tmux` with no socket flag by design, so it cannot be sandboxed — see
the guard in `t1216_4` for the full mechanism, the damage ceiling (panes only;
no `kill-session` / `kill-server` exists in the tree), and the
detect/disarm commands.

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] RUN EVERYTHING BELOW FROM A SHELL OUTSIDE THE MAIN AITASKS TMUX SESSION (aidocs/framework/tui_conventions.md, "Tmux-stress tasks") — these steps kill panes.
- [ ] [t1216_1] Minimonitor shadow behaviour is unchanged after the lift: press e to spawn a shadow, press c to pick concerns, confirm the stale banner still appears when the agent moves on after the shadow read.
- [ ] [t1216_1] The shadow's @aitask_shadow_analyzed_at stamp is still written only from inside a shadow pane: after a monitor-side capture, confirm the stamp did not advance.
- [ ] [t1216_2] With a shadow bound, Tab from the pane list cycles into the SHADOW column; with no shadow bound, Tab still cycles only pane list <-> preview.
- [ ] [t1216_2] The shadow column renders the shadow's content UNWRAPPED at the real shadow pane width (compare against the actual pane side by side).
- [ ] [t1216_2] The active column is visually unambiguous: the zone-active border and the LIVE badge track the focused column.
- [ ] [t1216_2] Typing in the SHADOW column lands in the shadow pane and NOT in the agent pane; typing in the PREVIEW column lands in the agent.
- [ ] [t1216_2] Narrow the terminal until the split no longer fits: the layout falls back to a single full-width column rather than squeezing the agent preview.
- [ ] [t1216_2] Press t from the pane list after focusing the agent column, then after focusing the shadow column: tail-follow resumes on the column you last focused, and the other column's scroll position is untouched.
- [ ] [t1216_2] Kill the shadow pane while the SHADOW zone is focused: the zone falls back to PREVIEW, and no keystroke typed during the transition reaches the agent pane.
- [ ] [t1216_3] Run two agents; spawn a shadow on the NON-selected one and have it emit a concern block: that agent's card shows the concern badge and NO toast fires.
- [ ] [t1216_3] Select that agent: the toast appears once, not on every refresh tick.
- [ ] [t1216_3] Press c, tick a subset of concerns, confirm: the clipboard payload pastes correctly into the followed agent, with the preamble.
- [ ] [t1216_3] Cancel the picker with Esc: nothing is written to the clipboard and the badge stays cleared.
- [ ] [t1216_3] With the agent moved on since the shadow's read, the picker shows the red stale banner and the toast carries the STALE marker.
- [ ] [t1216_3] Run several shadowed agents for a few minutes and confirm no per-tick subprocess churn (e.g. watch process count or CPU) — the badge path must spend no subprocesses.
- [ ] [t1216_4] Press e in the monitor on a selected agent: the shadow splits beside THAT agent, not beside the monitor.
- [ ] [t1216_4] Press e again on the same agent: refused with "A shadow is already running for this agent".
- [ ] [t1216_4] Press E: the agent/model picker dialog opens, and the launch uses the agent chosen in the dialog.
- [ ] [t1216_4] Kill the followed agent: its shadow dies AND the monitor window survives intact.
- [ ] [t1216_4] Set tmux.shadow_same_window to false and repeat the e spawn: the shadow opens in its own agent-shadow-* window and still dies with its agent.
- [ ] [t1216] Shadow panes never appear in the monitor's agent list, are never targeted by k (kill) or n (next sibling), and are not counted as real agents.
