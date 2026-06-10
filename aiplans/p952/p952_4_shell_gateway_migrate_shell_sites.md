---
Task: t952_4_shell_gateway_migrate_shell_sites.md
Parent Task: aitasks/t952_centralize_tmux_invocations_shared_gateway.md
Sibling Tasks: aitasks/t952/t952_1_*.md, aitasks/t952/t952_2_*.md, aitasks/t952/t952_3_*.md, aitasks/t952/t952_5_*.md
Archived Sibling Plans: aiplans/archived/p952/p952_*_*.md
Worktree: aiwork/t952_4_shell_gateway_migrate_shell_sites
Branch: aitask/t952_4_shell_gateway_migrate_shell_sites
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-10 18:49
---

# t952_4 — Shell gateway `lib/tmux_exec.sh` + migrate shell sites

## Context

Stage 4 (highest blast-radius) of the t952 tmux-centralization decomposition
(parent plan `aiplans/p952_centralize_tmux_invocations_shared_gateway.md`).
t952_1/2/3 already landed the Python gateway and migrated the Python sites; this
child builds the **shell** mirror and routes the shell call sites through it.
Depends only on **t952_1's contract** — the `AITASKS_TMUX_SOCKET` env var (empty
→ no socket args; non-empty → `-L <value>`), not its code. **Behavior-preserving
by construction:** with the var unset (today's state) the gateway prepends
nothing, so every migrated call is byte-identical to the raw call it replaces.

## Verification findings (verify pass, 2026-06-10)

Re-checked all anchors against the live tree — the existing plan was accurate;
three refinements result:

1. **All file paths and call sites confirmed.** `tmux_bootstrap.sh`
   (set-environment `:99`, list-windows `:115`, new-window `:116`, has-session
   `:156`); `terminal_compat.sh` 3 persistent rungs `:171/:175/:178`,
   `ait_tmux_new_session_persistent` defined `:158`; `aitask_minimonitor.sh`
   list-panes `:39`; `aitask_companion_cleanup.sh` (DO NOT MIGRATE — confirmed
   pane-died hook, raw `tmux` at `:15/:25/:28/:30`).

2. **`aitask_ide.sh` has THREE `exec tmux` sites, not one.** `:85`
   (`exec tmux select-window …`), `:94` (compound `exec tmux attach … \;
   select-window …`), `:101` (`exec tmux attach …`). A shell **function cannot be
   `exec`'d**, so ALL THREE use the **emitter** form, not just the compound one.
   The remaining ide.sh calls (`:73` display-message, `:81/:90` list-windows,
   `:82/:91` new-window, `:88` has-session) are captured/plain and use the
   `ait_tmux` function form.

3. **terminal_compat.sh is a file-scope LEAF today** (sources nothing; defines
   `die/warn/info` itself) and is copied **unconditionally** by
   `tests/lib/test_scaffold.sh::setup_fake_aitask_repo()` (`:17`). This drives the
   wiring decision below and the scaffold-coupling requirement.

## Wiring decision (cleanliness / blast-radius)

The naive reading creates a **circular file-scope dependency**: `tmux_exec.sh`
wants `die/warn/info` from `terminal_compat.sh`, while `terminal_compat.sh`'s
rungs want socket args from `tmux_exec.sh`. Sourcing both at file scope "works"
via the `_AIT_*_LOADED` guards but is fragile and — worse — makes the broad base
leaf `terminal_compat.sh` hard-depend on `tmux_exec.sh`, forcing **every**
terminal_compat consumer (and the base scaffold) to always carry it.

**Chosen approach (one-way file-scope dep + lazy in-function source):**

- `tmux_exec.sh` sources `terminal_compat.sh` **at file scope** (one direction
  only) for `die/warn/info`. Its socket/target helpers are otherwise pure.
- `terminal_compat.sh` does **NOT** source `tmux_exec.sh` at file scope. Instead
  `ait_tmux_new_session_persistent` sources it **lazily at the top of the
  function body** (guarded — a cheap no-op after first load) to obtain
  `ait_tmux_socket_args`. This keeps terminal_compat a file-scope leaf, adds no
  always-on dependency to its many consumers, and removes the file-scope cycle
  entirely (guards still make the lazy re-source safe in any load order).
- Consumers (`tmux_bootstrap.sh`, `aitask_ide.sh`, `aitask_minimonitor.sh`)
  source `tmux_exec.sh` at the top, next to their existing
  `terminal_compat.sh`/`tmux_bootstrap.sh` sources.

*Rejected:* terminal_compat.sh sourcing tmux_exec.sh at file scope — simpler to
read but maximal blast radius (every consumer + base scaffold always loads
tmux_exec) and a real circular dep.

## New file: `.aitask-scripts/lib/tmux_exec.sh`

`#!/usr/bin/env bash`, `set -euo pipefail`, `_AIT_TMUX_EXEC_LOADED` double-source
guard, `source` of sibling `terminal_compat.sh` (resolved via `BASH_SOURCE`).
Provides:

- `ait_tmux_socket_args` — **emitter**: prints `-L <value>` when
  `AITASKS_TMUX_SOCKET` is non-empty, nothing otherwise (mirrors
  `tmux_exec.py::tmux_socket_args`, `-L` form per t952_1).
- `ait_tmux <args...>` — function form: runs
  `command tmux $(ait_tmux_socket_args) "$@"` (read socket args into an array to
  stay safe under `set -u` / empty expansion). Returns tmux's exit code.
- `ait_tmux_session_target <session>` → `=<session>`;
  `ait_tmux_window_target <session> <window>` → `=<session>:<window>` (mirror the
  Python `session_target`/`window_target`; preserve the trailing-colon
  `new-window` idiom used at the existing call sites).

## Migration (function form for captured/plain calls)

- **`lib/tmux_bootstrap.sh`** — source `tmux_exec.sh`; rewrite `:99`
  set-environment, `:115` list-windows, `:116` new-window, `:156` has-session to
  `ait_tmux …`. (The new-session itself is delegated to
  `ait_tmux_new_session_persistent`, handled below.)
- **`lib/terminal_compat.sh`** — in `ait_tmux_new_session_persistent` (`:158`),
  lazily source `tmux_exec.sh`, read `ait_tmux_socket_args` into an array, and
  prepend it to the three rungs `:171` (systemd-run → wrapped `tmux`), `:175`
  (`setsid tmux …`), `:178` (plain `tmux …`). Keep the systemd-run/setsid/plain
  ladder otherwise **byte-for-byte** (load-bearing for t943/t956 server
  survival). For the systemd-run rung the socket args go into the `tmux` argv
  *inside* the unit command, matching the t952_1 Python note.
- **`aitask_minimonitor.sh`** — source `tmux_exec.sh`; rewrite `:39` list-panes
  to `ait_tmux list-panes …`.

## Migration (emitter form for `exec`/compound sites) — `aitask_ide.sh`

Source `tmux_exec.sh` at top. Function form for `:73/:81/:82/:88/:90/:91`.
Emitter form for the three `exec` sites — capture socket args once
(`socket_args=( $(ait_tmux_socket_args) )` or inline `$(…)`), then:
- `:85` → `exec tmux "${socket_args[@]}" select-window -t …`
- `:94` → `exec tmux "${socket_args[@]}" attach -t … \; select-window -t …`
  (the `\;` separator must reach `exec` intact — do not route through a function)
- `:101` → `exec tmux "${socket_args[@]}" attach -t …`

## DO NOT MIGRATE (documented exception)

`aitask_companion_cleanup.sh` — pane-died **hook** running in a minimal env that
inherits the server socket via `$TMUX`. Leave raw; t952_5 whitelists it in the
anti-regression guard.

## SCAFFOLD COUPLING (same-commit requirement)

Add, in the **same commit**, to
`tests/lib/test_scaffold.sh::setup_fake_aitask_repo()` (next to the
`terminal_compat.sh` copy, `:17`):
```bash
cp "$PROJECT_DIR/.aitask-scripts/lib/tmux_exec.sh" "$repo_dir/.aitask-scripts/lib/"
```
Rationale: `terminal_compat.sh` is copied unconditionally and now lazily sources
`tmux_exec.sh` (via `ait_tmux_new_session_persistent`); the tmux tests below
exercise that path. Omitting the copy breaks every scaffolded test that reaches
the persistent-spawn path. (The original plan gated this on "joins `./ait`'s
source chain" — `./ait` only sources `aitask_path.sh`, so the real trigger is
terminal_compat's chain, not `./ait`'s. Same conclusion, corrected rationale.)

## Risk

### Code-health risk: medium
- Highest-blast-radius child: touches the base leaf `terminal_compat.sh` plus 4
  consumer scripts. Mitigated by behavior-preservation (empty `AITASKS_TMUX_SOCKET`
  → emitter prints nothing → byte-identical calls) and the full tmux suite below
  · severity: medium · → mitigation: in-plan verification (no follow-up task).
- Circular/ordering hazard between `terminal_compat.sh` and `tmux_exec.sh`
  · severity: medium · → mitigation: one-way file-scope dep + lazy in-function
  source + double-source guards (Wiring decision above); no follow-up task.
- Scaffold coupling: omitting the `tmux_exec.sh` copy breaks scaffolded tests
  · severity: medium · → mitigation: same-commit scaffold edit + `shellcheck`
  HARD gate; no follow-up task.
- The three `aitask_ide.sh` `exec` sites must keep the `\;` separator intact and
  must not be routed through the (non-exec'able) function · severity: low · →
  mitigation: emitter form + `test_tmux_exact_session_targeting.sh`.

### Goal-achievement risk: low
- Contract (`AITASKS_TMUX_SOCKET`, `-L` form) is pinned by t952_1 and already
  proven in `tmux_exec.py`; this is a direct mirror with a concrete, existing
  verification suite · severity: low · → mitigation: none needed. None identified
  beyond this.

## Verification
- `shellcheck` (HARD gate) on `lib/tmux_exec.sh` and every migrated script:
  `shellcheck .aitask-scripts/lib/tmux_exec.sh .aitask-scripts/lib/tmux_bootstrap.sh
  .aitask-scripts/lib/terminal_compat.sh .aitask-scripts/aitask_ide.sh
  .aitask-scripts/aitask_minimonitor.sh`
- `bash tests/test_tmux_exact_session_targeting.sh`,
  `bash tests/test_tmux_persistent_scope.sh` (covers the systemd-run/session.slice
  rung being rewired), `bash tests/test_tmux_control.sh`.
- Run the full shell tmux suite under `require_isolated_tmux`.
- Sanity: with `AITASKS_TMUX_SOCKET` unset, `ait_tmux_socket_args` prints nothing;
  with it set, prints `-L <value>`; target helpers emit `=session` /
  `=session:window`.

See **Step 9 (Post-Implementation)** of the task-workflow for archival.
