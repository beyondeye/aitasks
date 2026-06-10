---
priority: medium
effort: high
depends: [t952_1]
issue_type: refactor
status: Ready
labels: [tmux, ait_bridge]
created_at: 2026-06-10 12:48
updated_at: 2026-06-10 12:48
---

## Context

Stage 4 of the t952 tmux-centralization decomposition (see `aiplans/p952_*`).
Builds the **shell** tmux gateway `lib/tmux_exec.sh` mirroring the Python one
(socket flag + exact-match targeting) and migrates the shell call sites through
it. Behavior-preserving. Depends only on t952_1's **contract** (the
`AITASKS_TMUX_SOCKET` env var name + "default empty"), NOT its code — so this
child can proceed in parallel with t952_2 / t952_3 (different language, zero
shared files). This is the **highest-blast-radius** child.

## Key files to modify
- **NEW** `.aitask-scripts/lib/tmux_exec.sh` — provides:
  - `ait_tmux <args...>` — function prepending `tmux` + socket args from
    `AITASKS_TMUX_SOCKET`.
  - `ait_tmux_session_target` / `ait_tmux_window_target` — mirror the Python
    `=session` / `=session:window` formatting.
  - a socket-args **emitter** form (e.g. `ait_tmux_socket_args`) for `exec` /
    compound-command sites where a shell function cannot be used.
- `.aitask-scripts/lib/tmux_bootstrap.sh` — `_tmux_bootstrap_set_project_registry`
  (set-environment -g), `_tmux_bootstrap_ensure_syncer_window` (list-windows,
  new-window), `spawn_session_detached` (has-session).
- `.aitask-scripts/lib/terminal_compat.sh` — route the three
  `ait_tmux_new_session_persistent` rungs (systemd-run / setsid / plain) through
  the socket-arg prepend.
- `.aitask-scripts/aitask_ide.sh` — ~8 calls (display-message, list-windows x2,
  new-window x2, select-window, has-session, attach x2).
- `.aitask-scripts/aitask_minimonitor.sh` — list-panes.

## DO NOT MIGRATE (documented exception)
`.aitask-scripts/aitask_companion_cleanup.sh` is a tmux **pane-died HOOK** that
runs in a **minimal environment** and inherits the server socket via `$TMUX`
automatically. Leave it on raw `tmux` as a documented exception; threading
`AITASKS_TMUX_SOCKET` into it is unnecessary and risky. It will be whitelisted
by the anti-regression guard in t952_5.

## Reference files for patterns
- `.aitask-scripts/lib/terminal_compat.sh` — `die` / `warn` / `info` helpers,
  `_AIT_*_LOADED` double-source guard pattern.
- `aidocs/framework/shell_conventions.md` — shebang `#!/usr/bin/env bash`,
  `set -euo pipefail`, stderr-for-diagnostics, source-chain ↔ test-scaffold rule.

## Implementation plan
1. Write `lib/tmux_exec.sh` with the function + emitter forms, the two target
   helpers, `#!/usr/bin/env bash`, `set -euo pipefail`, `die/warn/info` from
   terminal_compat.sh, and an `_AIT_TMUX_EXEC_LOADED` double-source guard.
2. Migrate the shell sites to `ait_tmux` (function form) for captured calls.
3. For `aitask_ide.sh`'s `exec tmux attach ... \; select-window ...` compound
   command, use the **socket-args emitter** form (`exec tmux $(ait_tmux_socket_args)
   attach ... \; ...`) — a function cannot be `exec`'d and the wrapper must not
   mangle the `\;` separator.

## SCAFFOLD COUPLING (same-commit requirement)
If `lib/tmux_exec.sh` joins `./ait`'s source-on-startup chain, add the matching
`cp "$PROJECT_DIR/.aitask-scripts/lib/tmux_exec.sh" "$repo_dir/.aitask-scripts/lib/"`
to `tests/lib/test_scaffold.sh::setup_fake_aitask_repo()` (next to the
`terminal_compat.sh` copy, ~line 17) **in the same commit** — omitting it breaks
every scaffolded test.

## Verification
- `shellcheck` (HARD gate) on `lib/tmux_exec.sh` and every migrated script.
- `tests/test_tmux_exact_session_targeting.sh`,
  `tests/test_tmux_persistent_scope.sh` (covers the systemd-run/session.slice
  path being rewired), `tests/test_tmux_control.sh`.
- Run the full shell tmux suite under `require_isolated_tmux`.
- This child gets its own Risk evaluation at pick time.
