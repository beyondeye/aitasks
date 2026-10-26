# tmux gateway — conventions for spawning and commanding tmux

The framework talks to tmux through a **single command gateway per language**.
The gateway is the only sanctioned place a raw `tmux` process is spawned, and it
owns four cross-cutting policies (socket, targeting, exec strategy, pane PATH)
that used to be scattered and duplicated across ~45–50 call sites. New code that touches tmux
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
  - Module functions `tmux_socket_args`, `session_target`,
    `session_scope_target`, `window_target`, `normalize_spawn_path`,
    `resolve_spawn_exe`, `creates_pane`, and `TmuxClient.spawn_env` (see
    *Pane PATH*).
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
  - `ait_tmux_pane_for_pid <pid>` — the gateway pane owning a process (the pane's
    own pid, or an ancestor at most `AIT_TMUX_PANE_WALK_MAX` hops up), echoed as
    `<pane_id>\t<session>:<window_id>.<pane_id>`; returns 1 when no gateway pane
    owns it. Turns a task lock's pid into a pane (live note delivery, sync
    deferrals).
  - `ait_tmux_legacy` / `ait_tmux_legacy_socket_args` — raw probes of the user's
    **default** server, for the migration window only (detect a pre-dedicated-socket
    session so a mid-flight user is not stranded). Not for general use.

## The four centralized policies

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

**Pick the helper by the `-t` TYPE the command takes, not by what you mean to
address.** The tmux man page names most commands' type (`target-session`,
`target-window`, `target-pane`). `list-panes` is the exception: its
synopsis says only `-t target`, and its prose says that with `-s` "target is a
session", yet tmux 3.7c still resolves that target as a window first. Treat it
as window-typed.

| `-t` type | Addressing | Helper | Emits |
|---|---|---|---|
| session (`has-session`, `list-windows`, `set-environment`, `attach`, `switch-client`, …) | a session | `session_target` | `=<s>` |
| window / pane (`list-panes`, `display-message`, `new-window`, …) | a whole session — e.g. `list-panes -s` | `session_scope_target` (shell: `ait_tmux_window_target "$s" ""`) | `=<s>:` |
| window / pane | one window | `window_target` | `=<s>:<w>` |

A bare `=<s>` on a window- or pane-typed `-t` is looked up as a **window name
first**, in the current session (with no client, the most recently used one).
If that session has a window called `<s>`, tmux answers about **that** session.
A window named after another session is common:
`automatic-rename-format '#{b:pane_current_path}'` produces one from any pane
whose cwd basename matches a session name. `list-panes -s -t =<s>` then lists
the wrong session's panes, with exit 0 and no error. Discovery maps the session
to the wrong project, the monitor attributes panes to the wrong session, and
freeze reconcile treats the wrong windows as observed. The trailing colon makes
the session part explicit, so it cannot match a window.
`tests/test_list_panes_session_scope_live.sh` reproduces the collision on a
private server. It runs discovery (sync, async, checked), freeze reconcile's
enumeration, and the monitor's single- and multi-session pane discovery against
it. Its source guard is narrow: it greps Python under `.aitask-scripts/` for a
same-line `"list-panes", "-s", "-t", session_target(` /
`tmux_session_target(` call. A multi-line call, a shell call site, or a
hand-formatted `=<s>` target gets past it, so a new `list-panes -s` site needs
this rule applied at review, not left to the guard.

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

**Pane-creating verbs never ride the control client.** `new-session`,
`new-window`, `split-window`, `respawn-pane` and `respawn-window` (anywhere in
the argv, so `\;` chains count) go straight to `run` / `run_async` even when the
backend is alive — see *Pane PATH* for why.

### 4. Pane PATH (the pane's PATH must not depend on its spawner)

tmux gives a new pane the PATH of the **client process that issued the
command**. Measured on tmux 3.6a against a scratch server:

| issuing client | PATH the new pane gets |
|---|---|
| a fresh `tmux new-window` subprocess (unattached client) | the **client's** PATH — it even overrides `-e PATH=…` |
| an attached `tmux -C attach` control client | the **server's global PATH**, frozen when the server started; the control client's own PATH is ignored |

Every other variable comes from the server's global environment, so session
variables a shell activation set (mise's `__MISE_*`) never reach the pane. On a
mise host that combination is a hazard: a `mise x <agent> -- <agent>` wrapper in
`~/.local/bin` resolves back to itself and `exec`s forever when `~/.local/bin`
precedes mise's shims dir, leaving a blank agent pane (t1689).

The gateway therefore owns the PATH every tmux client carries:

- **The rule** — `normalize_spawn_path` (Python) / `ait_spawn_path_normalize`
  in `lib/spawn_path.sh` (shell; result in `$AIT_SPAWN_PATH`, no fork). When
  PATH holds a mise entry (`<mise_data>/shims`, or anything under
  `<mise_data>/installs/`), reorder to: the framework bins that lead PATH
  (`$HOME/.aitask/bin`, `${AITASKS_HOME:-$HOME/.aitasks}/bin`), then every mise
  entry, then the rest. No mise entry → unchanged, byte for byte. That is the
  order a mise-activated interactive shell already has. The two
  implementations are pinned together by `TestShellParity` in
  `tests/test_tmux_exec.py`.
- **Python** — `run`, `run_checked`, `set_clipboard`, `run_async` and `spawn`
  pass `env=TmuxClient.spawn_env()` only when normalization changed something,
  so hosts without mise see exactly the calls they always did. A caller that
  `Popen`s `new_session_argv` itself passes `env=client.spawn_env()`
  (`None` = inherit).
- **Shell** — `ait_tmux` runs the client as `PATH="$AIT_SPAWN_PATH" command tmux …`
  when it differs; `ait_tmux_new_session_persistent` (in `terminal_compat.sh`)
  prefixes its setsid / plain rungs the same way.
- **New server** — the systemd-run rung of both persistence ladders adds
  `--setenv=PATH=<normalized>`: the unit runs in the user manager's environment,
  which would otherwise become the new server's global PATH.
- **Direct agent launches** — `ait codeagent invoke` normalizes PATH just
  before it `exec`s the agent, covering launches that bypass the gateway.
- **The launcher is not reordered** — only the pane's PATH is. `tmux` (and
  `setsid` / `systemd-run` in the persistence ladders) stays the binary the
  caller's PATH resolves: `resolve_spawn_exe` / `ait_spawn_exe` spell it as that
  absolute path whenever the reordered PATH would pick a different file (e.g. a
  mise-managed `tmux` behind a working system one), and leave the bare name
  otherwise.

Panes created outside the framework (the user's own key bindings, a hand-typed
`tmux new-window`) still inherit whatever their client had.

`tests/test_tmux_spawn_path_live.sh` reproduces the hazard with a bounded fake
wrapper on a private server and drives every route above against it.

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
2. Never hand-format `-t`. Use `session_target` / `session_scope_target` /
   `window_target` (`ait_tmux_session_target` / `ait_tmux_window_target`), chosen
   by the command's `-t` type — a whole-session query on a window-typed `-t`
   (`list-panes -s`) takes `session_scope_target`, never `session_target` (see
   *Target formatting*).
3. Don't thread `-L` / `-S` yourself — the gateway owns the socket flag.
4. Never hand tmux a PATH yourself, and never send a pane-creating verb over the
   control client — the gateway owns the pane PATH (see *Pane PATH*). A caller
   that `Popen`s a gateway-built argv passes `env=client.spawn_env()`.
5. Don't add yourself to the `test_no_raw_tmux.sh` allowlist.
6. Run `bash tests/test_no_raw_tmux.sh` before committing.

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
| `@aitask_shadow_target` | the shadow launcher, to the followed agent's `pane_id` | pane death | agent-list filters, frozen-aware classifier, minimonitor auto-spawn occupancy, minimonitor sibling fallback, companion cleanup | bound helper: this pane is an advisory shadow, not an agent |
| `@aitask_monitor_kind` | the monitor / minimonitor app, on its own pane | pane death | pane classification, companion cleanup | this pane is a monitor companion |
| `@aitask_scratchpad_target` | the scratchpad spawn, to the followed agent's `pane_id` | pane death | the same consumers as `@aitask_shadow_target` | bound helper: this pane is a scratchpad notes editor, not an agent |
| `@aitask_scratchpad_store` | the scratchpad spawn, to the pad's canonical absolute store directory (empty for an unsaved pad) | pane death | the one-pad-per-store duplicate lookup | which task store this pad writes; **not** a helper marker |
| `@aitask_record` | the SessionStart hook (only when the hook descends from that pane's process, with no codex app-server daemon in between), or the freeze engine as fallback | `drop`; pane death | freeze engine, restore coordinator, the hook itself | the pane-visible join to its session-store record |
| `@aitask_frozen` | the freeze engine, immediately before `respawn-pane` | the restore-confirm path; `drop` | pane enumeration, `kill_agent_pane_smart`, companion cleanup, minimonitor auto-spawn occupancy | **authoritative**: this pane is a frozen stand-in |
| `@aitask_standin_ready` | **the viewer itself**, after mount | freeze engine and restore coordinator, before *every* `respawn-pane`; `drop` | `reconcile` | positive proof the stand-in is up — the one signal that separates "stamped, viewer running" from "stamped, agent still running" |
| `@aitask_agent_session` | the SessionStart hook, on `$TMUX_PANE` (same process-tree condition) | pane death | freeze engine, when the store has no session id | the code agent's own session id |

The two **bound-helper targets** (`@aitask_shadow_target`,
`@aitask_scratchpad_target`) are defined once, in `lib/helper_panes.py`
(`BOUND_HELPER_TARGET_OPTIONS`, `is_bound_helper`), and every Python consumer
reads them from there; `aitask_companion_cleanup.sh` is the one bash copy, held
in step by `tests/test_helper_panes.py` and `tests/test_cleanup_rule_parity.sh`.
`@aitask_frozen` outranks both: a stamped pane is never a helper, whatever
target it retained (see the companion-pane section in `tui_conventions.md`).

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
