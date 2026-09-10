# tmux gateway — conventions for spawning and commanding tmux

The framework talks to tmux through a **single command gateway per language**.
The gateway is the only sanctioned place a raw `tmux` process is spawned, and it
owns three cross-cutting policies (socket, targeting, exec strategy) that used to
be scattered and duplicated across ~45–50 call sites. New code that touches tmux
— in any script or TUI, not just the obvious ones — must route through it.

Read this when writing or editing any shell or Python code under
`.aitask-scripts/` that creates, kills, captures, navigates, or sends keys to a
tmux session, window, or pane.

## The chokepoint rule

There are exactly two gateways. They are the **only** files allowed to spawn a
raw `tmux` process; everything else goes through them.

- **Python** — `.aitask-scripts/lib/tmux_exec.py`. `TmuxClient` is the sole owner
  of `subprocess`/`asyncio` `tmux` spawning. Key surface:
  - `run` / `run_async` — synchronous / async exec, returning `(rc, stdout)`
    (`(-1, "")` on `FileNotFoundError` / `OSError` / timeout).
  - `spawn` — fire-and-forget `Popen` for non-capturing UI updates
    (`switch-client`, `select-window`) and caller-managed `new-session` argvs.
  - `run_via_control` / `run_async_via_control` — the exec-strategy dispatcher
    (see below).
  - `resize_pane` — sole owner of the `resize-pane` verb.
  - `new_session_argv` — builds the socket-aware, persistence-wrapped
    `new-session` argv (mirrors `terminal_compat.sh`'s persistence ladder).
  - Module functions `tmux_socket_args`, `session_target`, `window_target`.
- **Shell** — `.aitask-scripts/lib/tmux_exec.sh`. Source it, then use:
  - `ait_tmux <args…>` — function form, socket flag auto-prepended, for captured
    / plain call sites.
  - `ait_tmux_socket_args` — emitter (one arg per line) for `exec` / compound
    `\;` sites, where a shell function can't be used:
    `exec tmux $(ait_tmux_socket_args) attach -t "$t" \; select-window -t "$w"`.
  - `ait_tmux_session_target` / `ait_tmux_window_target` — exact-match `-t`
    targets (see *Target formatting*).
  - `ait_tmux_socket_name` — the resolved socket name, for callers comparing
    against an attached server's socket.
  - `ait_tmux_legacy` / `ait_tmux_legacy_socket_args` — raw probes of the user's
    **default** server, for the migration window only (detect a pre-dedicated-socket
    session so a mid-flight user is not stranded). Not for general use.

## The three centralized policies

### 1. Socket selection (dedicated `-L ait` socket)

ait-managed tmux sessions live on a **dedicated named socket**, isolated from the
user's personal default tmux server (so a stray `tmux kill-server` on the default
server can't take ait down, and a hosted/served front-end has a stable backend
handle). The gateway resolves the socket flag from `AITASKS_TMUX_SOCKET` in one
place:

| `AITASKS_TMUX_SOCKET` | Socket flag | Meaning |
|---|---|---|
| unset | `-L ait` | the dedicated ait socket (default) |
| non-empty value | `-L <value>` | a named socket; `default` is the explicit opt-out to the user's default server |
| set but empty/whitespace | *(none)* | legacy escape hatch — follow `$TMUX`; used by the test isolation harness |

The socket name is `AIT_DEDICATED_SOCKET = "ait"` (mirrored verbatim in both
gateways). `-L` (socket name), not `-S` (socket path), so the value composes with
tmux's standard tmpdir resolution and the test isolation harness
(`tests/lib/tmux_isolation.sh`). The Python client reads the env var **once** at
construction (never per-call — the monitor fallback is a hot path).

### 2. Target formatting (mandatory exact match)

tmux resolves `-t <name>` as a **prefix** match by default, so `-t aitasks`
silently resolves to `aitasks_mob` when only the latter is running — crossing
project boundaries. The gateway's `session_target()` / `window_target()`
(`ait_tmux_session_target` / `ait_tmux_window_target` in shell) emit `=<session>`
exact-match targets and are **mandatory** — never hand-format a `-t` argument.

This doc owns the *mechanism* (use the helper). The *why* — one isolated tmux
session per project, multiple prefix-sharing projects side by side — lives in
`tui_conventions.md` ("Single tmux session per project").

### 3. Exec strategy (control client when alive, subprocess fallback)

For per-tick work the gateway dispatches "persistent control client when alive,
subprocess fallback on `rc == -1`". `run_via_control` / `run_async_via_control`
take a control-mode backend (`monitor/tmux_control.py`, a `tmux -C attach`
connection) duck-typed; if it is alive they route through it, otherwise they fall
back to `run` / `run_async`. The gateway owns the *strategy* without depending on
`monitor/`. The `(rc, stdout)` / `(-1, "")` fallback branch is load-bearing.

## The enforcement guard

`tests/test_no_raw_tmux.sh` greps `.aitask-scripts/` for raw `tmux` spawns and
**fails** if any non-allowlisted file issues one. It is a **freeze**, not a
migration: the small allowlist (the two gateways, Layer-A backends like
`monitor/tmux_control.py` and `aitask_companion_cleanup.sh`, and ambient `$TMUX`
self-probes of the *user's default* server) is documented per-entry with a
reason. Gateway-routed calls carry no `"tmux"` argv literal and are invisible to
the guard by construction.

**Do not extend the allowlist to make new code pass.** Route through the gateway
instead. The allowlist exists for the genuinely-ambient self-probes and the
backends that already reach the gateway socket — not as an escape hatch.

## Writing new tmux code — checklist

1. Spawn nothing raw. Python → `TmuxClient`; shell → `source lib/tmux_exec.sh`
   and use `ait_tmux` / `ait_tmux_socket_args`.
2. Never hand-format `-t`. Use `session_target` / `window_target`
   (`ait_tmux_session_target` / `ait_tmux_window_target`).
3. Don't thread `-L` / `-S` yourself — the gateway owns the socket flag.
4. Don't add yourself to the `test_no_raw_tmux.sh` allowlist.
5. Run `bash tests/test_no_raw_tmux.sh` before committing.

## Multiple real agents per window — state keyed by `pane_id`

A tmux **window** may hold more than one real coding agent. The monitor /
minimonitor layer therefore keys its per-agent state by **`pane_id`**, not by
`window_name` — once a window holds N agents (or an agent plus a companion),
`window_name` no longer identifies a single agent. The gateway and
`capture-pane` were already pane-keyed; the app layer was brought in line so the
window-vs-pane kill decision, task-id resolution, and sibling-pane lookup all
resolve per pane.

The **shadow** companion — an advisory second agent spawned beside the agent it
follows (see `shadow_agent.md`) — is excluded from the agent lists via a
pane-scoped tmux **user option**, `@aitask_shadow_target`, set to the followed
agent's `pane_id`. That option is the *authoritative* shadow classifier: a
same-window shadow shares its neighbor's window name, so a window-name marker
alone cannot identify it. It doubles as the lifecycle binding — see the
companion-pane section in `tui_conventions.md`. Enumerate it through the gateway
(`list-panes -F '#{@aitask_shadow_target}'`); never hand-spawn raw `tmux` to
read or set it.

## `@aitask_*` pane options — the inventory

Pane-scoped tmux **user options** are how the framework attaches identity to a
pane that a window name cannot distinguish. They are the only server-observable
per-pane state the monitors and engines read, alongside `#{pane_pid}`.
`#{pane_current_command}` is a process basename and is **never** identity.

Two properties make them load-bearing, and both cut in a direction that is easy
to get wrong:

- **They die with the pane.** A recycled `%N` therefore never carries a stale
  option — which is what lets an option, rather than a pane id, be the join key.
- **They survive `respawn-pane`.** The process is replaced; the options are not.
  So an option that must mean "the *current* occupant is up" has to be explicitly
  cleared (`set-option -pu`) before each respawn, and one that must survive a
  freeze/restore cycle on the same pane simply does.

| Option | Set by | Cleared by | Read by | Meaning |
|---|---|---|---|---|
| `@aitask_shadow_target` | the shadow launcher, to the followed agent's `pane_id` | pane death | agent-list filters, companion cleanup | this pane is an advisory shadow, not an agent |
| `@aitask_monitor_kind` | the monitor / minimonitor app, on its own pane | pane death | pane classification, companion cleanup | this pane is a monitor companion |
| `@aitask_record` | the SessionStart hook, or the freeze engine as fallback | `drop`; pane death | freeze engine, restore coordinator, the hook itself | the pane-visible join to its session-store record |
| `@aitask_frozen` | the freeze engine, immediately before `respawn-pane` | the restore-confirm path; `drop` | pane enumeration, `kill_agent_pane_smart`, companion cleanup, minimonitor auto-spawn occupancy | **authoritative**: this pane is a frozen stand-in |
| `@aitask_standin_ready` | **the viewer itself**, after mount | freeze engine and restore coordinator, before *every* `respawn-pane`; `drop` | `reconcile` | positive proof the stand-in is up — the one signal that separates "stamped, viewer running" from "stamped, agent still running" |
| `@aitask_agent_session` | the SessionStart hook, on `$TMUX_PANE` | pane death | freeze engine, when the store has no session id | the code agent's own session id |

Two of these are self-stamped by the app that owns the pane
(`@aitask_monitor_kind`, `@aitask_standin_ready`) and must stay that way — see
the companion-pane section in `tui_conventions.md` for why a stamp applied on
another process's behalf cannot mean what it claims.

`respawn-pane` and `run-shell -b` are ordinary gateway calls like everything
else here. `run-shell -b` in particular is how a TUI dispatches an operation that
must **outlive the pane it is issued from** — a freeze or a restore respawns the
issuing pane, so the coordinator cannot be a child of it.

## See also

- `aidocs/framework/tui_conventions.md` — single tmux session per project,
  companion-pane auto-despawn, and the "tmux-stress tasks run outside the main
  aitasks tmux" rule.
- `aidocs/framework/shadow_agent.md` — the shadow companion agent architecture
  (capture → context-fetch → skill) and the `@aitask_shadow_target` binding.
- `aidocs/framework/shell_conventions.md` — general shell-script conventions,
  including platform/archive CLI encapsulation.
