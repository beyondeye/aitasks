---
Task: t952_2_migrate_python_subprocess_sites.md
Parent Task: aitasks/t952_centralize_tmux_invocations_shared_gateway.md
Sibling Tasks: aitasks/t952/t952_3_absorb_controlmode_repoint_monitor.md, aitasks/t952/t952_4_shell_gateway_migrate_shell_sites.md, aitasks/t952/t952_5_collapse_registry_and_lint_guard.md, aitasks/t952/t952_6_manual_verification_centralize_tmux_invocations_shared_gatew.md
Archived Sibling Plans: aiplans/archived/p952/p952_1_python_gateway_core.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-10 16:57
---

# t952_2 — Migrate simple Python subprocess tmux sites through `TmuxClient`

## Context

Stage 2 of the t952 tmux-centralization decomposition. t952_1 (done) added the
Python gateway `lib/tmux_exec.py` (`TmuxClient`) as the sole future owner of
`Popen(["tmux", ...])`, with `run` / `run_async` / `spawn`, mandatory
`session_target`/`window_target`, and a faithful `new_session_argv` persistence
ladder. This task migrates the **simple, non-registry, synchronous** Python
tmux call sites onto the gateway — behavior-preserving routing substitution.
Parallel-eligible with t952_3 / t952_4 (no shared files).

**HARD BOUNDARY (do NOT cross):** the two registry readers stay raw tmux —
`_read_registry_entry` (`show-environment -g`, `agent_launch_utils.py:235`) and
the `list-sessions` / `list-panes -s` walk in `discover_aitasks_sessions`
(`:399`, `:414`). They belong to t952_5; migrating them here double-churns the
most delicate code and collides with t952_5.

## Verification-pass findings (anchors re-checked against the live tree, 2026-06-10)

The original plan's survey was largely accurate, but the verify pass corrected
six points — folded into the steps below:

1. **Missing site added:** `_lookup_window_name` (`agent_launch_utils.py:697`) —
   a non-registry `list-windows` site used by board + codebrowser, not in the
   original list. Included now so the non-registry chokepoint is complete.
2. **Helper deletion breaks a test the plan claimed stays green.** Pointing
   `launch_in_tmux`'s new-session branch at `client.new_session_argv` orphans
   `_new_session_tmux_argv` / `_persistent_new_session_prefix` /
   `_systemd_user_available` (t952_1's notes say delete them). But
   `tests/test_launch_in_tmux_pane_pid.py` imports and tests those symbols
   directly. So the suite is **not** unchanged — the duplicated test classes
   must be removed (coverage is fully replicated in `test_tmux_exec.py`'s
   `TestNewSessionArgv` + socket tests — verified).
3. **A new-session unit test's mock goes dead.** `test_failure_returns_error`
   patches `agent_launch_utils.get_tmux_sessions` to stub the server probe;
   post-migration the probe runs via `client._server_running()`. The test must
   patch the client's probe instead, or it silently issues a real
   `list-sessions`.
4. **stderr is dropped from 3 error messages (accepted deviation).** The
   gateway's `run` returns `(rc, stdout)` only — stderr is captured but not
   returned. Three sites surface tmux's stderr today (`launch_in_tmux`
   new-window + split-window, agentcrew pipe-pane). After migration they keep
   the message prefix (so log-greps / tests matching the substring still pass)
   but lose tmux's own detail. This is the one accepted behavior delta.
5. **`_spawn_in_session` is not a 1:1 substitution.** Its capture path returns a
   `subprocess.CompletedProcess` whose `.returncode`/`.stdout` its single caller
   `_launch_git_with_companion` reads. The gateway's `run` returns a tuple, so
   the capture path's return contract changes to `(rc, stdout)` and that one
   caller is updated to unpack it.
6. **agentcrew pipe-pane is `client.run`, not `client.spawn`.** The original
   plan said `spawn`, but the site is a synchronous `subprocess.run` that checks
   `returncode` for a warning — `spawn` (fire-and-forget) would drop that. Use
   `run`.

Also confirmed correctly **excluded** as non-tmux: `tui_switcher.py:563`
(`bash tmux_bootstrap.sh`), `:743` (`desync_state.py`), `agentcrew:76`
(`git rev-parse`), `:780` (`./ait crew`).

`tmux_session_target` / `tmux_window_target` stay in `agent_launch_utils.py`
(imported by board, codebrowser, tui_switcher, agentcrew, tests; the gateway
re-exports them verbatim). Migrated functions keep calling these module-level
helpers for `-t` formatting — identical output, zero blast radius.

## Implementation

### Common pattern

Add a module-level `_TMUX = TmuxClient()` to each module (socket args cached
once at import; `AITASKS_TMUX_SOCKET` normally unset → `[]` → argv byte-identical
to today). Then:
- `subprocess.run(["tmux", *args], capture_output=True, text=True, ...)` →
  `rc, out = _TMUX.run([*args])`; replace `result.returncode`/`result.stdout`
  with `rc`/`out`. The gateway folds `TimeoutExpired/FileNotFoundError/OSError`
  into `(-1, "")`, so the surrounding try/except collapses into the existing
  `rc != 0` failure branch (behavior-preserving).
- `subprocess.Popen(["tmux", *args], **kw)` → `_TMUX.spawn([*args], **kw)`.
  `spawn` does **not** swallow `FileNotFoundError`, so existing
  `except (FileNotFoundError, OSError)` guards still fire.

### `.aitask-scripts/lib/agent_launch_utils.py`

`from tmux_exec import TmuxClient`; `_TMUX = TmuxClient()`.

Migrate (non-registry only): `get_tmux_sessions`, `get_tmux_windows`,
`_lookup_window_name`, `switch_to_pane_anywhere` (the `_display` helper + the
`switch-client`/`select-window`/`select-pane` action loop), `_query_first_pane_pid`,
`maybe_spawn_minimonitor` (its `list-windows` / `list-panes` / split-window
`run`, and the select-pane refocus `Popen` → `spawn`), `launch_or_focus_codebrowser`
(`set-environment` / `list-windows` / `select-window` / `new-window`).

`launch_in_tmux`:
- new-session branch: `tmux_cmd = _TMUX.new_session_argv(config.session,
  config.window, command, cwd_args, config.cwd)`; keep
  `proc = subprocess.Popen(tmux_cmd, stderr=subprocess.PIPE)` (raw Popen —
  `new_session_argv` returns the full argv including any systemd-run/setsid
  prefix and the injected socket flag). Switch-client `Popen` → `_TMUX.spawn`.
- new-window branch: `rc, out = _TMUX.run([...])`; failure message becomes
  `f"tmux new-window failed (rc={rc})"` (drops stderr — finding #4).
- split-window branch: same as new-window; select-window `Popen` → `_TMUX.spawn`.

Delete the now-orphaned `_new_session_tmux_argv`, `_persistent_new_session_prefix`,
`_systemd_user_available` (the gateway owns them). Do **not** touch
`_read_registry_entry` or `discover_aitasks_sessions` (hard boundary).

### `.aitask-scripts/lib/tui_switcher.py`

`from tmux_exec import TmuxClient`; `_TMUX = TmuxClient()`.

- `_detect_current_session`: `display-message -p #S` → `_TMUX.run`.
- `_spawn_in_session`: async path → `_TMUX.spawn(inner_argv, stdout=DEVNULL,
  stderr=DEVNULL)`; capture path → `rc, out = _TMUX.run(inner_argv)` and
  **return `(rc, out)`** (finding #5). Update the docstring.
- `_switch_to`: `select-window` `Popen` → `_TMUX.spawn`.
- `_teleport_if_cross`: `switch-client` `Popen` → `_TMUX.spawn`.
- `_launch_git_with_companion`: unpack `rc, primary_pane = self._spawn_in_session(
  "git", cmd, capture_pane_id=True)`; the `set-option -p` and `set-hook -p`
  `Popen`s → `_TMUX.spawn` — their `-t <%pane>` pane-id targets pass through
  **untouched** (no `session_target` wrapping).

### `.aitask-scripts/agentcrew/agentcrew_runner.py`

`from lib.tmux_exec import TmuxClient`; `_TMUX = TmuxClient()`.

- pipe-pane (`:446`): `rc, _ = _TMUX.run(["pipe-pane", "-O", "-o", "-t",
  f"{tmux_window_target(session, win_idx)}.0", "cat >> …"])`; warn on `rc != 0`
  (drops `pp.stderr` — finding #4). Argv order preserved exactly.

### `tests/test_launch_in_tmux_pane_pid.py` (required edits — finding #2/#3)

- Drop the dead imports `_new_session_tmux_argv`, `_systemd_user_available`.
- Remove `TestNewSessionPersistentSpawn` and `TestSystemdUserAvailable`
  (coverage fully replicated in `tests/test_tmux_exec.py`).
- In `TestLaunchInTmuxNewSession.test_failure_returns_error`, replace the
  `patch.object(agent_launch_utils, "get_tmux_sessions", …)` with
  `patch.object(agent_launch_utils._TMUX, "_server_running", return_value=True)`
  so the attach path is taken without a real `list-sessions`.
- The new-window / split-window pid-capture tests stay as-is (argv with empty
  socket args is byte-identical; assertions check `-P`/`-F`/pid only).

## Risk

### Code-health risk: medium
- `launch_in_tmux` is a load-bearing agent-launch path and the migration spans
  ~16 sites across 3 modules + 1 test file; three sites are not pure 1:1
  substitutions (stderr drop, `_spawn_in_session` contract, helper deletion) ·
  severity: medium · → mitigation: the existing regression suite
  (`test_launch_in_tmux_pane_pid.py`, `test_tmux_exact_session_targeting.sh`,
  `test_tmux_exec.py`) run green under `require_isolated_tmux`, plus the t952_5
  lint guard that will forbid raw tmux outside the gateway (no follow-up task
  needed — mitigated in-plan + in-decomposition).
- One accepted behavior delta: tmux's stderr text is dropped from 3 error/warn
  messages (message prefixes preserved) · severity: low · → mitigation: prefixes
  kept so log-greps and the substring-asserting tests still match.

### Goal-achievement risk: low
- The approach is proven in t952_1 and the requirement map is now complete
  (the missed `_lookup_window_name` site is included; registry hard boundary
  honored) · severity: low · → mitigation: none identified beyond the
  verification below.

## Verification

- `python3 tests/test_launch_in_tmux_pane_pid.py` — green after the edits above
  (run under `require_isolated_tmux`).
- `bash tests/test_tmux_exact_session_targeting.sh` — green (exact-match
  targeting unchanged).
- `python3 tests/test_tmux_exec.py` — green (gateway unchanged; confirms the
  persistence-ladder coverage that replaces the removed classes).
- `shellcheck` n/a (Python-only change). Sanity-import the three modules to
  catch import/name errors.
- Pure routing otherwise — no new behavior tests added.

See **Step 9 (Post-Implementation)** of the task-workflow for archival.

## Final Implementation Notes

- **Actual work done:** Added a module-level `_TMUX = TmuxClient()` to
  `agent_launch_utils.py`, `tui_switcher.py`, and `agentcrew_runner.py`
  (`from tmux_exec import TmuxClient`; agentcrew uses `from lib.tmux_exec …`).
  Migrated every non-registry tmux call site onto it:
  - `agent_launch_utils.py`: `get_tmux_sessions`, `get_tmux_windows`,
    `_lookup_window_name`, `switch_to_pane_anywhere` (`_display` + action loop),
    `_query_first_pane_pid`, `launch_in_tmux` (new-session →
    `_TMUX.new_session_argv(...)` then raw `Popen`; new-window/split →
    `_TMUX.run`; switch-client/select-window → `_TMUX.spawn`),
    `maybe_spawn_minimonitor` (list-windows/list-panes/split via `run`,
    select-pane refocus via `spawn`), `launch_or_focus_codebrowser`
    (set-environment/list-windows/select-window/new-window via `run`). Deleted
    the now-orphaned `_new_session_tmux_argv`, `_persistent_new_session_prefix`,
    `_systemd_user_available` (the gateway owns them). The two registry readers
    (`_read_registry_entry`, `discover_aitasks_sessions` walk) were left raw —
    HARD BOUNDARY for t952_5.
  - `tui_switcher.py`: `_detect_current_session`, `_spawn_in_session`,
    `_switch_to`, `_teleport_if_cross`, `_launch_git_with_companion`. The
    `set-option -p` / `set-hook -p` pane-scoped verbs keep their `-t %pane`
    targets untouched (routed through `spawn` only for socket consistency).
  - `agentcrew_runner.py`: pipe-pane via `_TMUX.run`.
  - `tests/test_launch_in_tmux_pane_pid.py`: dropped dead imports + removed
    `TestNewSessionPersistentSpawn` / `TestSystemdUserAvailable` (coverage
    replicated in `test_tmux_exec.py::TestNewSessionArgv`); repointed
    `test_failure_returns_error` to patch `_TMUX._server_running`.
- **Deviations from plan:** none beyond the verify-pass findings already folded
  into the plan body. The original plan's "agentcrew via client.spawn" was
  corrected to `client.run` (it checks a returncode), and `_spawn_in_session`'s
  capture-path return contract was changed from `CompletedProcess` to
  `(rc, stdout)` with its one caller updated.
- **Issues encountered:** The live integration tests in
  `test_launch_in_tmux_pane_pid.py` (`TestLaunchInTmuxIntegration`) fail under
  isolated `TMUX_TMPDIR` unless `AIT_NO_SYSTEMD_RUN=1` is set — `systemd-run
  --user` spawns the server in a transient unit that does not inherit
  `TMUX_TMPDIR`, so the probe and the created server land on different sockets.
  This is the **same pre-existing condition t952_1 documented** (and why
  `test_tmux_exec.py`'s integration sets `AIT_NO_SYSTEMD_RUN=1`); verified
  identical on the un-migrated code via `git stash`. Not a regression. With the
  flag set, all 17 tests pass.
- **Key decisions:** (1) Kept `tmux_session_target` / `tmux_window_target` as
  module-level functions in `agent_launch_utils.py` (widely imported; the
  gateway re-exports them verbatim) — migrated code still calls them for `-t`
  formatting, zero blast radius. (2) The new-session branch keeps a raw
  `subprocess.Popen` on the full argv returned by `new_session_argv` (which
  already carries the socket flag + any systemd-run/setsid prefix) rather than
  `spawn`, which would double-prepend `tmux`.
- **Upstream defects identified:** None. (Note: the gateway's `run` returns
  `(rc, stdout)` only — stdout, no stderr. Three sites that previously surfaced
  tmux's stderr in an error/warn string now show only a prefix + rc. This is an
  intentional, accepted behavior delta of routing through the gateway, not a
  defect; message prefixes are preserved so substring-matching tests/log-greps
  still work.)
- **Notes for sibling tasks:**
  - The migration pattern for the remaining children: `from tmux_exec import
    TmuxClient`, one module-level `_TMUX`, then `subprocess.run(["tmux", …])` →
    `rc, out = _TMUX.run([…])` and `Popen(["tmux", …])` → `_TMUX.spawn([…])`.
    The gateway folds `TimeoutExpired/FileNotFoundError/OSError` into `(-1, "")`,
    so wrapping try/except collapses into the existing `rc != 0` branch;
    `spawn` does NOT swallow `FileNotFoundError` (guard with
    `is_tmux_available()` / an `except` as the call sites already do).
  - **t952_3 (control-mode + monitor):** when threading the socket into
    `tmux -C attach`, reuse `tmux_socket_args()` / a `TmuxClient` so the value
    matches; mind the systemd-run/`TMUX_TMPDIR` note above if a custom tmpdir is
    introduced.
  - **t952_5 (registry collapse):** the only raw `["tmux", …]` calls left in
    `agent_launch_utils.py` are `_read_registry_entry` (`show-environment -g`)
    and the `list-sessions` / `list-panes -s` walk in
    `discover_aitasks_sessions` — these are yours. A lint guard forbidding raw
    tmux outside the gateway can now assume every other Python site is migrated.
  - If `run` ever needs to surface tmux's stderr for an error message, that is a
    gateway enhancement (add a stderr-returning method), not a per-site fix.
