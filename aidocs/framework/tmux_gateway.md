# tmux gateway — conventions for spawning and commanding tmux

The framework talks to tmux through a **single command gateway per language**.
The gateway is the only sanctioned place a raw `tmux` process is spawned, and it
owns five cross-cutting policies (socket, targeting, exec strategy, pane PATH,
client UTF-8 and the tmux text model)
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
  - The text model (policy 5): `TMUX_CLIENT_FLAGS` (`-u`), `TMUX_ENCODING` /
    `TMUX_ERRORS`, and `tmux_text_kwargs`, `decode_tmux_output`,
    `encode_tmux_wire`, `encode_tmux_argv`, `tmux_os_path`.
  - Module functions `tmux_socket_args`, `session_target`,
    `session_scope_target`, `window_target`, `normalize_spawn_path`,
    `resolve_spawn_exe`, `creates_pane`, and `TmuxClient.spawn_env` (see
    *Pane PATH*).
- **Shell** — `.aitask-scripts/lib/tmux_exec.sh`. Source it, then use:
  - `ait_tmux <args…>` — function form, client flags (`-u`) and socket flag
    auto-prepended, for captured / plain call sites.
  - `ait_tmux_client_args` — emitter (one arg per line: `AIT_TMUX_CLIENT_FLAGS`,
    then the socket flag) for `exec` / compound `\;` sites, where a shell
    function can't be used:
    `exec tmux $(ait_tmux_client_args) attach -t "$t" \; select-window -t "$w"`.
  - `ait_tmux_socket_args` — the socket flag alone (parity-pinned with Python's
    `tmux_socket_args`). Not for `exec` sites: it omits `-u`.
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

## The five centralized policies

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
  in `lib/spawn_path.sh` (shell; result in `$AIT_SPAWN_PATH`, no fork) is a
  minimal displacement. When a `$HOME/.local/bin` entry precedes the **last**
  mise entry (anything under `<mise_data>/` — `shims`, `installs/*`,
  `command-wrappers/bin`), those `~/.local/bin` entries move to just after it.
  Nothing else moves. Otherwise PATH is unchanged, byte for byte. The two
  implementations are pinned together by `TestShellParity` in
  `tests/test_tmux_exec.py`.
- **Why only `~/.local/bin`** — that is where Omarchy's `omarchy-mise-install`
  writes its self-referential `mise x` wrappers. Neither
  PATH shape nor shadowing tells the hazard apart from a healthy shell: a
  mise-activated shell legitimately puts user tool dirs such as
  `~/.opencode/bin` ahead of mise (an rc prepends them after activation), and
  their binaries shadow mise-managed names on purpose. That shell already has
  `~/.local/bin` behind every mise entry, so it reaches the pane untouched,
  every tool keeping its precedence (t2144).
- **Accepted limitation: wrappers in other dirs** — a self-referential wrapper
  in any other dir ahead of mise (e.g. a user-authored project `bin/`, as in
  jdx/mise#8560) is not covered. Covering it would mean reordering legitimate
  tool dirs or sniffing file contents. On the one Omarchy host and the Omarchy
  sources examined, every such wrapper was in `~/.local/bin`, and
  `omarchy-mise-install` hard-codes that dir. Other platforms were not
  examined (t2153). Reproduced on mise 2026.10.12 with no `__MISE_*`
  variables and the tool installed by mise: the order
  `wrapper:shims:installs/<tool>/…/bin` loops. `wrapper:shims`,
  `wrapper:installs`, `installs:wrapper:shims` and `shims:installs:wrapper` do
  not loop. The full matrix and the probe are in the archived t2153 plan.
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

### 5. Client UTF-8 and the tmux text model (`tmux -u`)

tmux rewrites every non-printable or non-ASCII byte of command output to `_`
when the **client** process has no UTF-8 locale (no `LC_ALL` / `LC_CTYPE` /
`LANG` naming UTF-8). The client's locale decides it, not the server's.
Measured on tmux 3.8 against private sockets (3.4 and 3.6a behave the same):

| client env | TAB | `ó` | `\x1f` |
|---|---|---|---|
| none / `LANG=C` / `LC_ALL=C` | `_` | `_` | `_` |
| `LANG=C.UTF-8` / `LC_CTYPE=C.UTF-8` | kept | kept | kept |
| no locale + `tmux -u` | kept | kept | kept |
| control mode (`-C attach`), no locale | `_` | `_` | — |
| control mode with `-u`, no locale | kept | kept | — |

The TAB in `_SESSION_LIST_FORMAT` turns into `_`, every session name gains a
trailing `_`, and discovery finds nothing. Python sees this under `LC_ALL=C` /
`POSIX` or a non-UTF-8 named locale (with no locale at all, PEP 538 coercion
hides it). Shell callers see it whenever the locale is unset.

**The rule: every tmux client the framework spawns passes `-u`.** That covers
`TmuxClient._argv`, `new_session_argv`, the control-mode `_attach_argv`, the
Python ambient `$TMUX` probes, `ait_tmux`, `ait_tmux_legacy`,
`ait_tmux_client_args` and the persistence ladder. `-u` is better than forcing
`LC_CTYPE` because it is a *client* flag: it never leaks into the panes tmux
creates, and it does not need an installed `C.UTF-8` locale (macOS has none).
On an interactive `attach` it makes the client assume a UTF-8 terminal, which
is what every framework TUI already emits.

**Python: `-u` alone is not enough.** With `-u`, tmux speaks UTF-8 in both
directions whatever the locale. Before, a client with no locale got only ASCII
`_` back, so no Python decoder ever saw a high byte. Measured:

| observation | consequence |
|---|---|
| `text=True` decodes with the *locale* codec | under `LC_ALL=C PYTHONUTF8=0 PYTHONCOERCECLOCALE=0` (fs encoding `ascii`), `run` / `run_checked` raise an uncaught `UnicodeDecodeError` on `prój` |
| format output passes invalid UTF-8 through raw | a cwd or option `b\xffd` comes back as `/b\377d` |
| `capture-pane -p` substitutes U+FFFD for invalid bytes | captured screen text is always valid UTF-8 |
| `os.fsdecode` under an `ascii` fs encoding turns *valid* UTF-8 into surrogates | text consumers crash (`concern_block_signature` encodes the text as UTF-8; the control channel strict-encoded its line), so `fsdecode` is the wrong decoder for tmux output |

So strings read from tmux are **tmux text** — real Unicode — and the gateway
converts at three boundaries:

- **Decode** (tmux → Python): UTF-8 + `surrogateescape`, via
  `tmux_text_kwargs()` (for `subprocess.run`, in place of `text=True`) and
  `decode_tmux_output()` (`run_async`, the control reader, raw readers). Valid
  UTF-8 always reads as Unicode, and an invalid byte becomes a lone surrogate
  that round-trips.
- **Encode** (Python → tmux): `encode_tmux_wire(s)` is `os.fsencode(s)` when
  the OS codec can represent `s`, otherwise UTF-8 + `surrogateescape`. An OS
  string such as `os.getcwd()` therefore keeps its native bytes, and tmux text
  falls back to UTF-8 only where the OS codec cannot hold it.
  - `encode_tmux_argv` applies this per argv element and keeps an element as
    `str` whenever that is what `subprocess` would send anyway (always, on a
    UTF-8 host). The control client applies it **per argument** (`monitor_core._control_line`),
    never to the joined line: one non-encodable argument must not re-encode a
    native OS-path argument beside it.
  - `set_clipboard` stdin is buffer content, so it is always UTF-8.
- **Filesystem**: a path read from tmux (`#{pane_current_path}`, the
  `@aitask_project_root` / `@aitask_sitrep_root` / `@aitask_sitrep_tui_root` /
  `@aitask_scratchpad_store` stamps, `AITASKS_PROJECT_<s>`) goes through
  `tmux_os_path()` before `Path(…)` / `open` / `is_dir` or a comparison with an
  OS path. It is the identity on any UTF-8 host. Values that only go back to
  tmux or into records / display stay as tmux text.

**Scope of support (user decision, t2236).**

- **Fully supported**: UTF-8 locales, and C/POSIX with or without Python's
  UTF-8 mode or locale coercion. Names, paths, captured text and the control
  channel all round-trip.
- **Single-byte named locales** (e.g. ISO-8859-1) are **partially** supported:
  - The TAB separator, ASCII content and captured screen text work.
  - OS paths keep their native bytes in both directions: `-c <dir>` and
    path-valued options go out natively, and read-back paths reach the OS via
    `tmux_os_path`.
  - **Limitation:** a non-ASCII *tmux-text* argument, such as a session or
    window name read back from tmux, whose characters all lie in the locale
    codec's repertoire (`wïn` under Latin-1) is sent in the locale codec rather
    than UTF-8. So it does not round-trip into a `-t` target, `has-session` or
    a control request.
  - Characters outside the repertoire (`€`, CJK) cannot be `fsencode`d, so they
    are sent as UTF-8 and do round-trip.
  - **Consequence for discovery:** pane-vote discovery issues
    `list-panes -t =wïn:`; tmux answers "can't find session", which
    `discover_aitasks_sessions_checked` classifies as gone. Such a session is
    therefore **silently absent**, with `complete=True`, and a control attach
    to it fails. A stamped session is still discovered (its root comes with
    `list-sessions`) but cannot be targeted by its name.
  - Cause: a `str` reaching the gateway does not say whether it is a native OS
    path or tmux text. Full support means typing the OS-path inputs at their
    builders as native bytes (follow-up t2244; see also the t2236
    archived plan).
  - Evidence: the codec behaviour is pinned by the codec-patched table in
    `tests/test_tmux_exec.py`. The live lane in
    `tests/test_tmux_utf8_client_live.sh` runs only where `locale -a` lists a
    single-byte locale.

**Not covered:** `aitask_companion_cleanup.sh` stays raw by design. It reads
only pane ids and empty / non-empty option values with a `|` separator, so
mangling cannot change any decision it makes. Its call shapes are pinned by
`test_cleanup_rule_parity.sh`.

`tests/test_tmux_utf8_client_live.sh` reproduces the defect on a private server
in probe-selected locale lanes, with pre-fix controls (blanked `-u`, the old
decoders) proving each lane triggers what it claims to test.

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
5. Never `text=True`, `.decode()` or `.encode()` on tmux I/O — use
   `tmux_text_kwargs()` / `decode_tmux_output()` / `encode_tmux_wire()`. Convert
   a tmux-sourced path with `tmux_os_path()` before the filesystem sees it. A
   caller that `Popen`s a gateway-built argv wraps it:
   `Popen(encode_tmux_argv(argv), env=client.spawn_env())`. A shell `exec` site
   uses `ait_tmux_client_args`, never the bare socket emitter. A `-F` format's
   TAB separator is a real byte (`$'\t'` in shell): tmux keeps a single-quoted
   `\t` literally (see *Client UTF-8*).
6. Don't add yourself to the `test_no_raw_tmux.sh` allowlist.
7. Run `bash tests/test_no_raw_tmux.sh` before committing.

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
| `@aitask_sitrep_root` | the sitrep spawn (`monitor_core.spawn_sitrep`), to the canonical project root, on the sitrep agent's pane | pane death | the one-sitrep-per-root duplicate lookup | which repository this sitrep agent serves; **not** a helper marker (the pane is an agent) |
| `@aitask_sitrep_tui_root` | the sitrep spawn (`monitor_core.spawn_sitrep`), to the canonical project root, on the sitrep TUI's pane | pane death | the one-TUI-per-root lookup; agent listings that must skip it (discovery, the sitrep agent matcher, the minimonitor sibling to follow, the `h` identity read) | this pane is the sitrep TUI: **not** an agent for listings, **not** a helper marker either — a real occupant for cleanup, smart kill, freeze and auto-close (`lib/helper_panes.py` `is_sitrep_tui_pane`, frozen first) |
| `@aitask_trails_app` | the `ait trails` app, on its own pane, to its pid (after its baseline mailbox read) | unset on app exit; pane death (a dead pid is not a receiver) | `launch_or_focus_trails` (the receiver lookup) | this pane is a live trails mailbox receiver; **not** a helper marker |
| `@aitask_trails_card_focus` | the `ait trails` app, on its own pane, to its pid — set just BEFORE its `@aitask_trails_app` stamp | unset on app exit (after the receiver stamp); pane death | `launch_or_focus_trails` with a task id (one `display-message` read of both options; it counts only when both name the same pid) | this receiver understands the task form of `@aitask_trails_focus`; **not** a helper marker |
| `@aitask_trails_focus` | `launch_or_focus_trails`, to `"<32-hex request id> <art: handle>"` on the first live receiver — or `"<32-hex request id> <art: handle> <task id>"` (show that member's card too; task id in `BOARD_TASK_ID_RE` grammar) when that receiver carries a matching `@aitask_trails_card_focus`. An older app refuses the task form as malformed, so it never gets it: it gets the bare handle and the writer returns a warning | never unset (overwritten; the reader remembers the last id) | the trails app's own mailbox poll (`parse_trails_focus_target`) | a request to open that trail, and optionally to focus that task's card |
| `@aitask_board_app` | the `ait board` app (`board_focus_request.py`), on its own pane, to its pid (after its baseline mailbox read) | unset on app exit; pane death | `launch_or_focus_board` (the receiver lookup) | this pane is a live board mailbox receiver; **not** a helper marker |
| `@aitask_board_focus` | `launch_or_focus_board` (the sitrep TUI's "open in board"), to `"<32-hex request id> <task id>"` on the first live receiver | never unset (overwritten; the reader remembers the last id) | the board's own mailbox poll | a request to focus that task's card |
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
