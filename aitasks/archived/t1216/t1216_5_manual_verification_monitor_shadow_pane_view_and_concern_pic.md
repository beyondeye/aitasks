---
priority: medium
effort: medium
depends: [t1216_4]
issue_type: manual_verification
status: Done
labels: [verification, manual, tmux_destructive]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [t1216_1, t1216_2, t1216_3, t1216_4]
assigned_to: dario-e@beyond-eye.com
anchor: 1111
created_at: 2026-07-27 22:27
updated_at: 2026-07-31 11:08
completed_at: 2026-07-31 11:08
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

- [x] RUN EVERYTHING BELOW FROM A SHELL OUTSIDE THE MAIN AITASKS TMUX SESSION (aidocs/framework/tui_conventions.md, "Tmux-stress tasks") — these steps kill panes. — PASS 2026-07-31 11:06 auto: ran on throwaway isolated tmux server (TMUX unset, private TMUX_TMPDIR); -L ait server verified empty before and after
- [x] [t1216_1] Minimonitor shadow behaviour is unchanged after the lift: press e to spawn a shadow, press c to pick concerns, confirm the stale banner still appears when the agent moves on after the shadow read. — PASS 2026-07-31 11:06 auto: live minimonitor c-picker + stale modal banner verified; pre-lift vs post-lift worktree A/B on same fixture behaved identically; e-spawn leg pinned by test_minimonitor_shadow_pick.py (OK)
- [x] [t1216_1] The shadow's @aitask_shadow_analyzed_at stamp is still written only from inside a shadow pane: after a monitor-side capture, confirm the stamp did not advance. — PASS 2026-07-31 11:06 auto: stamp 1000.0 on shadow pane unchanged after many monitor tick captures + zone focus; second shadow's stamp stayed empty across tick captures and an explicit c capture
- [x] [t1216_2] With a shadow bound, Tab from the pane list cycles into the SHADOW column; with no shadow bound, Tab still cycles only pane list <-> preview. — PASS 2026-07-31 11:06 auto: with shadow bound Tab cycled list->PREVIEW(LIVE)->SHADOW(LIVE)->list; without shadow Tab only cycled list<->preview, no Shadow header ever shown
- [x] [t1216_2] The shadow column renders the shadow's content UNWRAPPED at the real shadow pane width (compare against the actual pane side by side). — PASS 2026-07-31 11:06 auto: 100-char line wrapped at exactly the real 60-col shadow pane boundary in both the real pane and the monitor column (row2 identical); not re-wrapped at column width
- [x] [t1216_2] The active column is visually unambiguous: the zone-active border and the LIVE badge track the focused column. — PASS 2026-07-31 11:06 auto: LIVE badge tracked focused column in live captures; ANSI capture diff shows accent border styling shifts with zone state (48 vs 26 accent runs); final aesthetic judgement remains subjective
- [x] [t1216_2] Typing in the SHADOW column lands in the shadow pane and NOT in the agent pane; typing in the PREVIEW column lands in the agent. — PASS 2026-07-31 11:06 auto: typed text in SHADOW zone landed only in shadow pane (1/0), in PREVIEW zone only in agent pane (1/0)
- [x] [t1216_2] Narrow the terminal until the split no longer fits: the layout falls back to a single full-width column rather than squeezing the agent preview. — PASS 2026-07-31 11:06 auto: at 90 cols the shadow column disappeared and agent preview went full width with LIVE; restored at 220 cols
- [x] [t1216_2] Press t from the pane list after focusing the agent column, then after focusing the shadow column: tail-follow resumes on the column you last focused, and the other column's scroll position is untouched. — PASS 2026-07-31 11:06 auto: t after focusing agent column resumed agent tail, shadow column scroll byte-identical; t after focusing shadow column resumed shadow, agent stayed PAUSED and unmoved across the t press; minor text-anchor drift (~5 lines) observed on zone entry, an adjacent pre-existing anchor-restore behavior, not the t contract
- [x] [t1216_2] Kill the shadow pane while the SHADOW zone is focused: the zone falls back to PREVIEW, and no keystroke typed during the transition reaches the agent pane. — PASS 2026-07-31 11:07 auto: killed shadow with SHADOW zone focused while typing; zero keystrokes reached agent pane; zone fell back to PREVIEW LIVE with 'Shadow gone' toast
- [x] [t1216_3] Run two agents; spawn a shadow on the NON-selected one and have it emit a concern block: that agent's card shows the concern badge and NO toast fires. — PASS 2026-07-31 11:07 auto: concern block on non-selected agent's shadow lit the card badge (diamond-!) with zero toast
- [x] [t1216_3] Select that agent: the toast appears once, not on every refresh tick. — PASS 2026-07-31 11:07 auto: selecting the agent fired the toast exactly once; no re-toast over 15s of 1s refresh ticks
- [x] [t1216_3] Press c, tick a subset of concerns, confirm: the clipboard payload pastes correctly into the followed agent, with the preamble. — PASS 2026-07-31 11:07 auto: picker showed last block only; space-ticked 1 of 2; confirm wrote preamble + selected concern (only) to tmux buffer; paste-buffer into agent pane rendered payload correctly
- [x] [t1216_3] Cancel the picker with Esc: nothing is written to the clipboard and the badge stays cleared. — PASS 2026-07-31 11:07 auto: Esc on picker wrote nothing (no tmux buffer) and card badge stayed cleared (diamond without !)
- [x] [t1216_3] With the agent moved on since the shadow's read, the picker shows the red stale banner and the toast carries the STALE marker. — PASS 2026-07-31 11:07 auto: past analyzed_at stamp + fresh agent output -> toast carried 'STALE - agent moved on' marker and picker showed the red stale banner
- [x] [t1216_3] Run several shadowed agents for a few minutes and confirm no per-tick subprocess churn (e.g. watch process count or CPU) — the badge path must spend no subprocesses. — PASS 2026-07-31 11:07 auto: 30s /proc child sampling x2 configs (3 shadowed agents, badges off vs on): identical children (persistent tmux -C control client + 1 unrelated desync snapshot), CPU flat 32 vs 34 ticks; no capture-script processes; fixture ran shadowed agents ~40min total
- [x] [t1216_4] Press e in the monitor on a selected agent: the shadow splits beside THAT agent, not beside the monitor. — PASS 2026-07-31 11:07 auto: tests/test_monitor_shadow_spawn_live.sh case A (real action_launch_shadow on live tmux: shadow splits in the agent's window, monitor pane untouched) + e binding pinned by mocked suite
- [x] [t1216_4] Press e again on the same agent: refused with "A shadow is already running for this agent". — PASS 2026-07-31 11:07 auto: live monitor press of e on shadowed agent showed 'A shadow is already running for this agent'; DuplicateGuardTests pin the guard incl. live-query-not-cache
- [x] [t1216_4] Press E: the agent/model picker dialog opens, and the launch uses the agent chosen in the dialog. — PASS 2026-07-31 11:07 auto: live E opened the Shadow (pick agent) dialog with agent/model selector (codex/gpt5_6_terra shown; cancelled safely); chosen-agent launch args pinned by mocked suite (screen.full_command post-override)
- [x] [t1216_4] Kill the followed agent: its shadow dies AND the monitor window survives intact. — PASS 2026-07-31 11:07 auto: live smoke case E/F: agent death fired cleanup hook, shadow died, monitor stand-in pane survived; wrong-companion bypass control proved the kill is real
- [x] [t1216_4] Set tmux.shadow_same_window to false and repeat the e spawn: the shadow opens in its own agent-shadow-* window and still dies with its agent. — PASS 2026-07-31 11:07 auto: live smoke case B: shadow_same_window false -> shadow in own agent-shadow-<task> window, active window unmoved; same lethal cleanup hook armed with [agent,shadow] args (kill proven in case E/F on the split branch)
- [x] [t1216] Shadow panes never appear in the monitor's agent list, are never targeted by k (kill) or n (next sibling), and are not counted as real agents. — PASS 2026-07-31 11:07 auto: CODE AGENTS count stayed 2/3 with shadows bound, shadow panes never appeared as cards in live captures; cache-boundary + kill/sibling exclusion pinned by test_monitor_shadow_status.py; test_no_raw_tmux.sh PASS
