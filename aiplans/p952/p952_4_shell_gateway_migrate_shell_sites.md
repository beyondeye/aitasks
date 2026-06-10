---
Task: t952_4_shell_gateway_migrate_shell_sites.md
Parent Task: aitasks/t952_centralize_tmux_invocations_shared_gateway.md
Sibling Tasks: aitasks/t952/t952_1_*.md, aitasks/t952/t952_2_*.md, aitasks/t952/t952_3_*.md, aitasks/t952/t952_5_*.md
Worktree: aiwork/t952_4_shell_gateway_migrate_shell_sites
Branch: aitask/t952_4_shell_gateway_migrate_shell_sites
Base branch: main
---

# t952_4 — Shell gateway `lib/tmux_exec.sh` + migrate shell sites

Stage 4 (highest blast-radius) — see parent plan
`aiplans/p952_centralize_tmux_invocations_shared_gateway.md`. Depends only on
**t952_1's contract** (`AITASKS_TMUX_SOCKET` name + default-empty), not its
code — parallel-eligible with t952_2 / t952_3. **Behavior-preserving.**

## Implementation steps

1. **New `.aitask-scripts/lib/tmux_exec.sh`**:
   - `#!/usr/bin/env bash`, `set -euo pipefail`, `die/warn/info` sourced from
     terminal_compat.sh, `_AIT_TMUX_EXEC_LOADED` double-source guard.
   - `ait_tmux <args...>` — function prepending `tmux` + socket args from
     `AITASKS_TMUX_SOCKET`.
   - `ait_tmux_socket_args` — **emitter** form for `exec`/compound sites where a
     function cannot be used.
   - `ait_tmux_session_target` / `ait_tmux_window_target` — mirror Python
     `=session` / `=session:window`.
2. **Migrate** (function form for captured calls):
   - `lib/tmux_bootstrap.sh` (`_tmux_bootstrap_set_project_registry`,
     `_tmux_bootstrap_ensure_syncer_window`, `spawn_session_detached`).
   - `lib/terminal_compat.sh` — route the 3 `ait_tmux_new_session_persistent`
     rungs through the socket-arg prepend.
   - `aitask_minimonitor.sh` (list-panes).
3. **`aitask_ide.sh`**: the `exec tmux attach ... \; select-window ...` compound
   command uses the **emitter** form: `exec tmux $(ait_tmux_socket_args) attach
   ... \; ...` — must not mangle the `\;` separator.

## DO NOT MIGRATE
`aitask_companion_cleanup.sh` — pane-died hook in a minimal env, inherits the
server socket via `$TMUX`. Leave raw; t952_5 whitelists it.

## SCAFFOLD COUPLING (same-commit)
If `tmux_exec.sh` joins `./ait`'s source chain, add
`cp "$PROJECT_DIR/.aitask-scripts/lib/tmux_exec.sh" "$repo_dir/.aitask-scripts/lib/"`
to `tests/lib/test_scaffold.sh::setup_fake_aitask_repo()` (next to the
terminal_compat.sh copy, ~line 17) in the **same commit** — else every
scaffolded test breaks.

## Verification
- `shellcheck` (HARD gate) on `tmux_exec.sh` + every migrated script.
- `tests/test_tmux_exact_session_targeting.sh`,
  `tests/test_tmux_persistent_scope.sh`, `tests/test_tmux_control.sh`.
- Full shell tmux suite under `require_isolated_tmux`.

See **Step 9 (Post-Implementation)** for archival.
