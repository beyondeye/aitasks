---
priority: medium
effort: medium
depends: [t952_1]
issue_type: refactor
status: Ready
labels: [tmux, ait_bridge]
created_at: 2026-06-10 12:48
updated_at: 2026-06-10 12:48
---

## Context

Stage 2 of the t952 tmux-centralization decomposition (see `aiplans/p952_*`).
Migrates the **simple, non-registry, synchronous** Python tmux call sites to
route through the `TmuxClient` gateway built in **t952_1**. Behavior-preserving:
pure routing substitution. Can proceed in parallel with t952_3 and t952_4
(no shared files). Depends on t952_1 only.

## Key files to modify
- `.aitask-scripts/lib/agent_launch_utils.py` — the non-registry sites:
  `get_tmux_sessions`, `get_tmux_windows`, `switch_to_pane_anywhere`,
  `_query_first_pane_pid`, `launch_in_tmux` (switch its new-session branch to
  `client.new_session_argv(...)`), `maybe_spawn_minimonitor`,
  `launch_or_focus_codebrowser`.
- `.aitask-scripts/lib/tui_switcher.py` — ~7 inline subprocess sites:
  `_detect_current_session`, `_spawn_in_session` (~617-625), `_switch_to`
  (~1009), `_teleport_if_cross` (~1035), `_launch_git_with_companion`
  (~1074-1083).
- `.aitask-scripts/agentcrew/agentcrew_runner.py` — the pipe-pane straggler
  (~447).

## Reference files for patterns
- `.aitask-scripts/lib/tmux_exec.py` (built in t952_1) — `run` / `run_async` /
  `spawn` and the mandatory `session_target` / `window_target` helpers.

## HARD BOUNDARY (do NOT cross)
Do **not** touch the two registry readers — `_read_registry_entry`
(`tmux show-environment -g AITASKS_PROJECT_*`) and the
`list-sessions`/`list-panes -s` walk inside `discover_aitasks_sessions`. Those
belong to **t952_5** (registry collapse); migrating them here creates a merge
collision and double-churns the most delicate code. Draw the migration line at
"non-registry sites" only.

## Implementation plan
1. Replace `subprocess.run(["tmux", ...])` → `client.run([...])`,
   `subprocess.Popen(["tmux", ...])` → `client.spawn([...])`,
   `asyncio.create_subprocess_exec("tmux", ...)` → `client.run_async([...])`
   (none of the simple sites are async, but keep the surface consistent).
2. Route **every** session/window `-t` target through the gateway's mandatory
   `session_target` / `window_target`.
3. Construct one `TmuxClient` per module (or pass through) — its socket args are
   cached at construction.

## Risks
- **Pane-scoped verbs:** `set-option -p` / `set-hook -p` (in
  `_launch_git_with_companion`) and other pane-id targets take a `%pane` id, NOT
  a session/window target — pass them through untouched; only session/window
  targets get the exact-match helper.
- **`agentcrew` pipe-pane** argv order is sensitive — preserve it exactly via
  `spawn`.

## Verification
- `tests/test_launch_in_tmux_pane_pid.py` stays green (the pane-pid capture
  path through `launch_in_tmux`).
- `tests/test_tmux_exact_session_targeting.sh` stays green.
- Pure routing — add no new behavior tests; the win is the existing suite
  passing unchanged. Run under `require_isolated_tmux`.
- This child gets its own Risk evaluation at pick time.
