---
Task: t1689_immunize_tmux_agent_spawns_against_client_path_order.md
Base branch: main
Output branch: main
---

# t1689 — Immunize tmux agent spawns against the client's PATH order

## Context

On a mise + Omarchy host, pressing `x`/`e` in the TUI switcher sometimes opened
an agent pane that stayed blank forever. The cause: the pane's PATH had
`~/.local/bin` (holding the Omarchy `claude` mise-shim) ahead of mise's shims
dir, and none of the `__MISE_*` session vars. Under that combination
`mise x claude -- claude` resolves back to the shim, which `exec`s itself in a
loop. tmux hands a new pane the PATH of the **client process that issued the
command**, so the pane's PATH order depends on whoever happened to spawn it.
The goal is to make every framework spawn independent of the caller's PATH order.

### Mechanism, re-measured here (tmux 3.6a, scratch server)

| issuing client | PATH the new pane gets |
|---|---|
| plain `tmux new-window` subprocess (unattached client) | the **client's** PATH. It even overrides `-e PATH=…` |
| `tmux -C attach` control client (attached) | the **server's global PATH**, frozen at server start. The control client's own PATH is ignored |

The second row corrects the task's assumption that a control-mode spawn uses
the PATH the control client had at attach. In fact it uses the global PATH of
whichever process started the server. On Linux that is the `systemd-run`
user-manager environment (the t1811 note).

## Design

One rule, owned by the gateway: **every tmux client the framework launches
carries a normalized PATH, and every pane-creating command goes through such a
client.**

**Normalization rule** (`normalize_spawn_path`, user-confirmed "mise first"):
- Split on `:`, keeping empty entries. Compare entries with trailing `/` stripped.
- *mise entries* are `<mise_data>/shims` and anything under
  `<mise_data>/installs/`, where
  `mise_data = $MISE_DATA_DIR || ${XDG_DATA_HOME:-$HOME/.local/share}/mise`.
- *framework entries* are `$HOME/.aitask/bin` and `${AITASKS_HOME:-$HOME/.aitasks}/bin`.
  Both spellings name the same dir after `ait engine home --migrate` symlinks
  the legacy root.
- Output: the framework entries that appear before the first other non-mise
  entry, then all mise entries, then everything else. Relative order is kept
  inside each group.
- **No mise entries → returned unchanged.** Hosts without mise (this Mac, CI)
  then see byte-for-byte identical subprocess calls, with no `env=` kwarg at all.
  Idempotent.

The result is the order a mise-activated interactive shell already has, which
is the known-working configuration (task's control repro).

## Implementation steps

1. **`.aitask-scripts/lib/tmux_exec.py`**
   - Add `normalize_spawn_path(path: str, environ=None) -> str` (the rule
     above) and module constant `_PANE_CREATING_VERBS = frozenset({"new-session",
     "new-window", "split-window", "respawn-pane", "respawn-window"})`, plus
     `creates_pane(args) -> bool` (any token in the set, which also covers `\;` chains).
     The framework spells verbs in full, so aliases are deliberately not matched (documented).
   - `TmuxClient.spawn_env(base=None) -> dict | None`: `None` when normalization
     changes nothing (inherit, today's behavior). Otherwise a copy of
     `base or os.environ` with `PATH` replaced.
   - `run`, `run_checked`, `set_clipboard`, `run_async`: pass `env=` **only when**
     `spawn_env()` is not `None` (a private `_env_kwargs()` → `{}` / `{"env": …}`).
     This keeps existing strict test fakes unaffected on non-mise hosts.
   - `spawn(args, **popen_kwargs)`: if the caller passed `env`, normalize that
     env's PATH; otherwise apply `_env_kwargs()`.
   - `run_via_control` / `run_async_via_control`: if `creates_pane(args)`, skip
     the backend and go straight to `run` / `run_async`. Comment why (an attached
     client doesn't donate PATH, measured above). Covers `monitor_core.spawn_tui`
     and the minimonitor `new-window` (both go through `monitor.tmux_run`).
   - `_persistent_new_session_prefix`: add
     `--setenv=PATH=<normalize_spawn_path(os.environ PATH)>` before `--`
     (omitted when PATH is unset), so the systemd-run rung hands the first window
     the same PATH the setsid/plain rungs do (user-confirmed).
   - Update the module docstring: a 4th policy, "pane PATH".
2. **`.aitask-scripts/lib/agent_launch_utils.py`** (`launch_in_tmux`
   new-session branch, ~line 2083): `subprocess.Popen(tmux_cmd, stderr=…,
   env=_TMUX.spawn_env())`. `None` means inherit, so nothing changes on non-mise hosts.
3. **New `.aitask-scripts/lib/spawn_path.sh`**: a side-effect-free leaf lib with a
   double-source guard, holding `ait_spawn_path_normalize [<path>]`. It sets
   `AIT_SPAWN_PATH` without forking, using a `${s%%:*}`/`${s#*:}` loop so empty
   entries survive (`read -a` drops trailing ones). It is a shell mirror of the
   Python function and parity-tested. It lives in its own leaf, not in
   `aitask_path.sh`, because sourcing that file prepends `~/.aitask/bin`, a side
   effect tests deliberately avoid (t1917).
4. **`.aitask-scripts/lib/tmux_exec.sh`**: source `spawn_path.sh`. In `ait_tmux`
   call `ait_spawn_path_normalize "${PATH-}"` and run
   `PATH="$AIT_SPAWN_PATH" command "${_argv[@]}"`. Bash looks up the command
   with the temporary PATH (verified), and the entries are unchanged, so `tmux`
   still resolves. This covers `aitask_ide.sh` and `tmux_bootstrap.sh`.
5. **`.aitask-scripts/lib/terminal_compat.sh`** (`ait_tmux_new_session_persistent`):
   after its lazy `source tmux_exec.sh`, normalize once. Then systemd rung:
   add `--setenv=PATH="$AIT_SPAWN_PATH"`; setsid/plain rungs: prefix
   `PATH="$AIT_SPAWN_PATH"`. This stays invisible to `test_no_raw_tmux.sh`'s
   command-position pattern (`tmux ${sock…}`), as today.
6. **`.aitask-scripts/aitask_codeagent.sh`** `cmd_invoke` (belt-and-braces, item 2
   of the task): source `lib/spawn_path.sh`. Just before `exec "${CMD[@]}"`,
   `ait_spawn_path_normalize; export PATH="$AIT_SPAWN_PATH"`. This covers
   `ait codeagent invoke` launched outside the gateway (e.g. from a `bash -lc`).
   The pane pid stays the agent (still `exec`). Not doing the task's
   shim-sniffing variant: it can't predict a loop without running the shim, and
   normalization removes the documented trigger.
7. **Docs**
   - `aidocs/framework/tmux_gateway.md`: "three centralized policies" → four. New
     `### 4. Pane PATH`: the measured table, the rule, the control-mode bypass,
     the systemd `--setenv`. Note in `### 3. Exec strategy` that pane-creating
     verbs never ride the control client. Add checklist item: "never hand tmux a
     PATH yourself; never send a pane-creating verb over the control client".
   - `website/content/docs/commands/codeagent.md`: a short `### Troubleshooting`
     entry after "TUI Integration": "agent pane stays blank". Explain that a
     wrapper in `~/.local/bin` that re-resolves the agent through `mise x` can
     loop when `~/.local/bin` precedes mise's shims, that framework spawns now
     normalize this, and what to run when launching manually. Keep agent names
     generic (documentation conventions), then run `python3 check_links.py --build`.

## Tests

- **`tests/test_tmux_exec.py`** (extend):
  - `TestNormalizeSpawnPath` table: no mise → identical; shims after
    `~/.local/bin` → after `~/.aitask/bin`, before `~/.local/bin`; installs
    entries move too; `MISE_DATA_DIR` / `XDG_DATA_HOME` overrides; trailing
    slashes; empty entries kept; mise-before-framework input; `AITASKS_HOME/bin`
    counts as framework; idempotence.
  - Env plumbing: with a mise PATH, `run`/`run_checked`/`set_clipboard`/`spawn`/
    `run_async` receive `env["PATH"]` normalized. Without one, **no `env` kwarg**
    (key absent). `spawn(env=custom)` normalizes the custom env.
  - Control bypass: alive fake backend + `new-window` args → backend
    `request_sync`/`request_async` **not called**, subprocess called;
    `list-panes` → backend called.
  - `new_session_argv` systemd rung contains `--setenv=PATH=<normalized>` before `--`.
  - `TestShellParity`: the same table through
    `bash -c 'source lib/spawn_path.sh; ait_spawn_path_normalize "$1"; printf %s "$AIT_SPAWN_PATH"'`,
    asserted equal to the Python output (contract test for the mirror).
- **New `tests/test_tmux_spawn_path_live.sh`** (`require_isolated_tmux`, own short
  `TMUX_TMPDIR=$(mktemp -d /tmp/aitspXXXX)`, since macOS rejects long socket paths;
  `AITASKS_TMUX_SOCKET=""`; scratch `HOME`):
  - Fixture: `$HOME/.local/share/mise/shims/fakeagent` writes `REAL` to a marker.
    `$HOME/.local/bin/fakeagent` writes `SHIM` and exits 1 (a bounded stand-in
    for the recursing shim). Spawning PATH = `$HOME/.local/bin:<shims>:/usr/bin:/bin`
    plus the tmux dir.
  - **Built-in control**: raw `command tmux new-window … fakeagent` with that PATH
    → marker `SHIM`. This proves the fixture reproduces the hazard.
  - Python `TmuxClient().run(["new-window", …, "fakeagent"])` → `REAL`.
  - Shell `ait_tmux new-window … fakeagent` → `REAL`.
  - Control-mode: the server is started with the bad PATH. A real
    `monitor_core.TmuxControlBackend(session, socket_args=[])` (`start()` /
    `stop()`, following `tests/test_tmux_control_resilience.sh`) sends
    `new-window` through `TmuxClient.run_via_control` → `REAL`. Pre-fix, this
    is the case that gets the server's global (bad) PATH.
  - Healthy order unchanged: PATH with no mise dirs → pane PATH equals the
    spawner's PATH exactly.
  - Uses the file-backed counters if any body runs in a subshell (CLAUDE.md t1207).

## Verification

1. `python3 -m pytest tests/test_tmux_exec.py` (or the unittest runner) passes.
2. `bash tests/test_tmux_spawn_path_live.sh` passes. **Pre-fix control**: `git stash` the
   lib changes (keep the tests), re-run, and confirm the Python/shell/control cases
   FAIL with `SHIM`. Record that in Final Implementation Notes.
3. `bash tests/test_no_raw_tmux.sh`, `bash tests/test_codeagent.sh`,
   `bash tests/test_aitasks_home.sh`.
4. `shellcheck .aitask-scripts/lib/spawn_path.sh .aitask-scripts/lib/tmux_exec.sh .aitask-scripts/lib/terminal_compat.sh .aitask-scripts/aitask_codeagent.sh`.
5. Full suite: `set -o pipefail; bash tests/run_all_python_tests.sh 2>&1 | tail -5`, reading
   only the final `PYTHON SUITE:` line.
6. `cd website && python3 check_links.py --build`.

Out of scope: switching `aitask_path.sh` from `~/.aitask/bin` to
`$AITASKS_HOME/bin`. Unmigrated homes have only the legacy dir, and migrated
ones symlink it. Suggest a separate task if wanted.

Step 9 (Post-Implementation) handles commit, archival and merge as usual.

## Risk

### Code-health risk: medium
- Every gateway tmux subprocess (monitor, board, switcher, freeze/restore) can get a changed `env` on mise hosts — wide blast radius, though an identity no-op (no `env=` kwarg at all) wherever PATH has no mise entries · severity: low · → mitigation: none
- The systemd-run rung's new `--setenv=PATH=…` changes the first server's global PATH for **every** Linux/systemd user (user-manager PATH → caller's normalized PATH), and cannot be exercised live on this macOS host — only its argv is unit-tested · severity: medium · → mitigation: verify_on_mise_linux_host
- Python/shell normalizer mirror can drift · severity: low · → mitigation: none (the parity contract test is part of the plan)

### Goal-achievement risk: medium
- The `mise x` re-resolution mechanism comes from the task's Omarchy-host analysis; mise is not installed here, so the fix is proven against a synthetic recursing shim and the real tmux PATH mechanics, not against real `mise x` + the Omarchy shim · severity: medium · → mitigation: verify_on_mise_linux_host
- Panes created outside the framework (the user's own tmux bindings, hand-typed `tmux new-window`) still inherit the caller's PATH — out of scope by design · severity: low · → mitigation: none

### Planned mitigations
- timing: after | name: verify_on_mise_linux_host | type: manual_verification | priority: high | effort: low | inline_risk: high | added_complexity: low | addresses: systemd-run --setenv rung untestable on macOS; real `mise x` + Omarchy shim not exercised | desc: On the Omarchy/mise Linux host, re-run t1689's repro (bad-order PATH new-window via gateway, switcher x/e, minimonitor/monitor spawns, first-server systemd-run launch) and confirm the real agent binary boots in each
