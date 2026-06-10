---
Task: t952_2_migrate_python_subprocess_sites.md
Parent Task: aitasks/t952_centralize_tmux_invocations_shared_gateway.md
Sibling Tasks: aitasks/t952/t952_1_*.md, aitasks/t952/t952_3_*.md, aitasks/t952/t952_4_*.md, aitasks/t952/t952_5_*.md
Worktree: aiwork/t952_2_migrate_python_subprocess_sites
Branch: aitask/t952_2_migrate_python_subprocess_sites
Base branch: main
---

# t952_2 — Migrate simple Python subprocess sites

Stage 2 — see parent plan `aiplans/p952_centralize_tmux_invocations_shared_gateway.md`.
Depends on **t952_1** only; parallel-eligible with t952_3 / t952_4.
**Behavior-preserving routing substitution.**

## HARD BOUNDARY
Do NOT touch `_read_registry_entry` (`show-environment`) or the
`list-sessions`/`list-panes -s` walk in `discover_aitasks_sessions` — those are
t952_5's. Migrate **non-registry** sites only.

## Implementation steps

1. Construct a `TmuxClient` per module (socket args cached at construction).
2. Substitute, routing every session/window `-t` through the gateway's
   mandatory `session_target` / `window_target`:
   - `subprocess.run(["tmux", ...])` → `client.run([...])`
   - `subprocess.Popen(["tmux", ...])` → `client.spawn([...])`
3. **`agent_launch_utils.py`** non-registry sites: `get_tmux_sessions`,
   `get_tmux_windows`, `switch_to_pane_anywhere`, `_query_first_pane_pid`,
   `launch_in_tmux` (point its new-session branch at `client.new_session_argv`),
   `maybe_spawn_minimonitor`, `launch_or_focus_codebrowser`.
4. **`lib/tui_switcher.py`** (~7 sites): `_detect_current_session`,
   `_spawn_in_session` (~617-625), `_switch_to` (~1009), `_teleport_if_cross`
   (~1035), `_launch_git_with_companion` (~1074-1083).
5. **`agentcrew/agentcrew_runner.py`** pipe-pane (~447) via `client.spawn`.

## Risks
- Pane-scoped verbs (`set-option -p` / `set-hook -p`, pane-id `%N` targets)
  pass through untouched — only session/window targets get the exact-match
  helper.
- `agentcrew` pipe-pane argv order is sensitive — preserve exactly.

## Verification
- `tests/test_launch_in_tmux_pane_pid.py` and
  `tests/test_tmux_exact_session_targeting.sh` stay green (run under
  `require_isolated_tmux`). No new behavior tests — pure routing.

See **Step 9 (Post-Implementation)** for archival.
