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
   of the task): just before `exec "${CMD[@]}"` (i.e. *after* the `--dry-run`
   return), lazily source `lib/spawn_path.sh`, then
   `ait_spawn_path_normalize "${PATH-}"; export PATH="$AIT_SPAWN_PATH"`. The
   source is lazy and on the exec branch only, so the five test files that copy
   `aitask_codeagent.sh` into a scratch repo and only use `--dry-run`
   (`test_codeagent.sh`, `_op_wiring`, `_work_report`, `_discuss`, `_trail`)
   don't need the new lib. This covers `ait codeagent invoke` launched outside
   the gateway (e.g. from a `bash -lc`). The pane pid stays the agent (still
   `exec`). Not doing the task's shim-sniffing variant: it can't predict a loop
   without running the shim, and normalization removes the documented trigger.
6b. **Test scaffolds that copy `tmux_exec.sh`** (source-on-startup ↔
   test-scaffold rule, `aidocs/framework/shell_conventions.md`): once
   `tmux_exec.sh` sources `spawn_path.sh`, every scratch copy of it needs the
   new file next to it, or the sourcing fails at startup. There are two copy
   sites: `tests/lib/test_scaffold.sh:21` (`setup_fake_aitask_repo`, used by
   many suites) and `tests/test_session_hook.sh:44`. Add
   `lib/spawn_path.sh` to both `cp` lists. The other tests that use
   `tmux_exec.sh` source it from `$PROJECT_DIR` and are unaffected. Before
   finishing, re-grep `tests/` for `tmux_exec.sh` copy sites, including
   `cp -R .aitask-scripts`, which picks the file up automatically.
   `tmux_exec.sh` sources it with a plain
   `source "$(dirname "${BASH_SOURCE[0]}")/spawn_path.sh"`, matching the file's
   other sourced libs. There is deliberately no existence guard: a missing lib
   must fail loudly, not silently skip normalization.
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
  - The test resolves every lib from its own `REPO_ROOT` (`dirname "$0"/..`),
    never from `$PWD` or a hard-coded path. That is what lets the pre-fix control
    below run the same file against a scratch checkout.
- **`tests/test_codeagent.sh`, new real-invoke test** (covers step 6 directly;
  every existing invoke test is `--dry-run` and returns before the new code):
  - `setup_test_env` also copies `lib/spawn_path.sh`.
  - Fixture in a scratch `HOME`: `$HOME/.local/bin/claude` appends `SHIM` to a
    marker file and exits 1. `$HOME/.local/share/mise/shims/claude` writes
    `REAL` plus its argv (one arg per line) to the marker and exits 0. Both are
    harmless and bounded.
  - Spawning PATH is built from scratch only:
    `$HOME/.local/bin:$HOME/.local/share/mise/shims:<dirs of bash, jq, git, python3 via command -v>:/usr/bin:/bin`,
    so the developer's real `claude` can never be reached. First assert
    `PATH=<that> command -v claude` resolves to the fake shim (the hazard is
    really present).
  - Run `HOME=… PATH=… bash "$CODEAGENT" --agent-string claudecode/<seed model> invoke raw probe-arg`
    (no `--dry-run`). Assert the marker reads `REAL`, contains no `SHIM`, and
    the recorded argv carries `--model` plus `probe-arg`. Derive the model id
    the way the existing derived-default tests do, never pinned.
  - Healthy-order control: no mise dirs in PATH means the fake `~/.local/bin/claude`
    is still what runs (marker `SHIM`). That shows normalization is a no-op
    without mise entries.

## Verification

1. `python3 -m pytest tests/test_tmux_exec.py` (or the unittest runner) passes.
2. `bash tests/test_tmux_spawn_path_live.sh` passes. Live tmux preflight: run it
   from a plain terminal, or confirm `require_isolated_tmux` isolates (memory:
   live tmux suites).
3. **Pre-fix control, in isolation. Never `git stash` in this shared
   checkout.** The working tree can hold another session's uncommitted edits
   (it already has an unrelated `.claude/settings.local.json` change), and
   swapping the libraries would change what running sessions execute. Instead:
   ```bash
   ctl=<scratchpad>/prefix_ctl
   git worktree add --detach "$ctl" HEAD          # pre-fix libs, untouched
   cp tests/test_tmux_spawn_path_live.sh tests/test_codeagent.sh "$ctl/tests/"
   cp tests/test_tmux_exec.py "$ctl/tests/"        # the new unit tests
   (cd "$ctl" && bash tests/test_tmux_spawn_path_live.sh)   # expect FAIL: SHIM (python/shell/control cases)
   (cd "$ctl" && bash tests/test_codeagent.sh)              # expect FAIL: real-invoke test, marker SHIM
   (cd "$ctl" && python3 -m pytest tests/test_tmux_exec.py -q) # expect ImportError/FAIL on the new tests
   git worktree remove --force "$ctl"
   ```
   HEAD is the pre-implementation commit, as long as the implementation is
   still uncommitted when this runs, which Step 8 guarantees. If any helper
   the new tests need is missing from the old tree (e.g. `tests/lib/*`
   additions), copy those test-side files too, but **never** lib files. Expect
   the "built-in control" and "healthy order" cases to PASS pre-fix. Record the
   per-case outcomes in Final Implementation Notes.
4. `bash tests/test_no_raw_tmux.sh`, `bash tests/test_codeagent.sh`,
   `bash tests/test_session_hook.sh`, `bash tests/test_aitasks_home.sh`, plus
   two `setup_fake_aitask_repo` consumers that source `terminal_compat.sh`
   (pick via `grep -l setup_fake_aitask_repo tests/*.sh`). Together they cover
   the scaffold change (6b).
5. `shellcheck .aitask-scripts/lib/spawn_path.sh .aitask-scripts/lib/tmux_exec.sh .aitask-scripts/lib/terminal_compat.sh .aitask-scripts/aitask_codeagent.sh`.
6. Full suite: `set -o pipefail; bash tests/run_all_python_tests.sh 2>&1 | tail -5`, reading
   only the final `PYTHON SUITE:` line.
7. `cd website && python3 check_links.py --build`.

Out of scope: switching `aitask_path.sh` from `~/.aitask/bin` to
`$AITASKS_HOME/bin`. Unmigrated homes have only the legacy dir, and migrated
ones symlink it. Suggest a separate task if wanted.

Step 9 (Post-Implementation) handles commit, archival and merge as usual.

## Risk

### Code-health risk: medium
- Every gateway tmux subprocess (monitor, board, switcher, freeze/restore) can get a changed `env` on mise hosts — wide blast radius, though an identity no-op (no `env=` kwarg at all) wherever PATH has no mise entries · severity: low · → mitigation: none
- The systemd-run rung's new `--setenv=PATH=…` changes the first server's global PATH for **every** Linux/systemd user (user-manager PATH → caller's normalized PATH), and cannot be exercised live on this macOS host — only its argv is unit-tested · severity: medium · → mitigation: verify_on_mise_linux_host
- Python/shell normalizer mirror can drift · severity: low · → mitigation: none (the parity contract test is part of the plan)
- `tmux_exec.sh` gains a startup `source` of a new lib, so any scratch copy of it without `spawn_path.sh` breaks at source time. Many suites go through `setup_fake_aitask_repo` · severity: low · → mitigation: none (step 6b updates both copy sites, and verification step 4 runs their consumers)
- A pre-fix control that `git stash`es libs in the shared checkout would disturb concurrent sessions · severity: medium · → mitigation: none (verification step 3 runs the control in a detached scratch worktree, never stashing)

### Goal-achievement risk: medium
- The `mise x` re-resolution mechanism comes from the task's Omarchy-host analysis; mise is not installed here, so the fix is proven against a synthetic recursing shim and the real tmux PATH mechanics, not against real `mise x` + the Omarchy shim · severity: medium · → mitigation: verify_on_mise_linux_host
- The `cmd_invoke` guard (step 6) is unreachable from every existing invoke test (all `--dry-run`) · severity: low · → mitigation: none (the new real-invoke test in `test_codeagent.sh` exercises the exec path, with a pre-fix control)
- Panes created outside the framework (the user's own tmux bindings, hand-typed `tmux new-window`) still inherit the caller's PATH — out of scope by design · severity: low · → mitigation: none

### Planned mitigations
- timing: after | name: verify_on_mise_linux_host | type: manual_verification | priority: high | effort: low | inline_risk: high | added_complexity: low | addresses: systemd-run --setenv rung untestable on macOS; real `mise x` + Omarchy shim not exercised | desc: On the Omarchy/mise Linux host, re-run t1689's repro (bad-order PATH new-window via gateway, switcher x/e, minimonitor/monitor spawns, first-server systemd-run launch) and confirm the real agent binary boots in each
