---
Task: t953_ait_tmux_dedicated_persistent_socket.md
Worktree: (current directory — profile 'fast', no worktree)
Branch: main
Base branch: main
---

# Plan: t953 — Run `ait` tmux sessions on a dedicated, persistent socket

## Context

All `ait`-managed tmux sessions currently live on the user's shared default
tmux server. A stray `tmux kill-server` takes `ait` down too, the framework
cannot present a stable backend handle to a remote/hosted front-end
(`aidocs/applink/wish_ssh_evaluation.md`, use case 3), and there is no clean
boundary for per-verb permission gating. This is candidate approach #1 from
t943, rejected there for blast radius, and explicitly unblocked by t952: both
tmux gateways (`lib/tmux_exec.py::TmuxClient` / `lib/tmux_exec.sh::ait_tmux`)
already read the `AITASKS_TMUX_SOCKET` env var and thread the `-L` flag into
every invocation — including the t943 persistence ladder
(`terminal_compat.sh::ait_tmux_new_session_persistent` and
`TmuxClient.new_session_argv`, both of which put the socket flag inside the
systemd-run/setsid argv). **The persistence axis is therefore already done; this
task flips the socket axis and handles the fallout.**

Decided with user (all recommendations accepted):
1. **Gateway-baked default** — flip in the two gateway mirrors, not the `ait`
   dispatcher (direct script invocation is a documented pattern; a
   dispatcher-only export would split-brain across two servers).
2. **Socket name `ait`** — ONE shared dedicated server for all aitasks
   projects; sessions stay per-project, multi-session `j` switcher keeps working.
3. **Migration**: interactive legacy-attach offer in `ait ide` + stderr warning
   in the non-interactive bootstrap path.
4. **Include the `TODO(socket-move)` Layer-A holdouts** (monitor_app.py,
   codebrowser_app.py) that t952 explicitly deferred to this task.

## New env-var semantics (the core change)

| `AITASKS_TMUX_SOCKET` | Gateway emits | Meaning |
|---|---|---|
| **unset** | `-L ait` | NEW dedicated default |
| set, non-empty (e.g. `mysock`) | `-L mysock` | custom socket (unchanged) |
| set to `default` | `-L default` | explicit opt-out → user's default server (tmux's default socket is literally named `default`) |
| set, empty/whitespace | *(no flag)* | legacy escape hatch — follows `$TMUX` ambient resolution; used by the test isolation harness |

`-L` (not `-S`) stays per the t952 decision: composes with `$TMUX_TMPDIR`
resolution and the test isolation harness. `-S` for hosted absolute paths is
future work if needed.

## Implementation steps

### 1. Gateway default flip (2 mirrors)

- `.aitask-scripts/lib/tmux_exec.py` — `tmux_socket_args()` (~line 61):
  ```python
  AIT_DEDICATED_SOCKET = "ait"   # mirrored verbatim in lib/tmux_exec.sh
  ...
  raw = os.environ.get(TMUX_SOCKET_ENV)
  if raw is None:
      return ["-L", AIT_DEDICATED_SOCKET]
  sock = raw.strip()
  return ["-L", sock] if sock else []
  ```
- `.aitask-scripts/lib/tmux_exec.sh` — `ait_tmux_socket_args()` (~line 42):
  unset check via `[[ -z "${AITASKS_TMUX_SOCKET+x}" ]]` → emit `-L` / `ait`;
  otherwise existing trim logic (set-empty → nothing).
- Add `ait_tmux_socket_name()` (shell) emitting the resolved socket name
  (`ait` / custom / empty when no flag) — needed by the `ait ide`
  socket-identity check (step 3) so the comparison has one source of truth.
- Add legacy helpers to `tmux_exec.sh` (gateway file = inside the lint-guard
  allowlist):
  - `ait_tmux_legacy() { command tmux -L default "$@"; }` — probe form.
  - `ait_tmux_legacy_socket_args()` emitting `-L` / `default` one-per-line —
    for `exec tmux ... attach \; ...` sites (functions can't be exec'd).
- Update the now-false header/docstring prose in both mirrors ("empty/unset =>
  default socket (today's behavior)").

### 2. Stale-comment sweep at call sites

Update "unset today → default socket" comments: `lib/agent_launch_utils.py:30`,
`lib/tui_switcher.py:62`, `agentcrew/agentcrew_runner.py:56`,
`monitor/tmux_control.py:89/111/338`, and the t943 prose in
`lib/terminal_compat.sh` (~131–157) that asserts "Socket unchanged (default)".

### 3. `ait ide` migration UX (`.aitask-scripts/aitask_ide.sh`)

- **Socket-identity check** (top of the `[[ -n "${TMUX:-}" ]]` branch, line 81):
  resolve attached server's socket name as `basename "${TMUX%%,*}"`; resolve
  gateway socket via `ait_tmux_socket_name`. If gateway emits a name and it
  differs from the attached socket → warn ("you are inside a tmux server that
  is not the aitasks server (`-L ait`); detach (Ctrl-b d) and re-run, or run
  `AITASKS_TMUX_SOCKET=default ait ide` to keep using the legacy server") and
  `exit 1`. If gateway emits no flag (legacy escape hatch) → skip the check
  (today's behavior). This fixes the otherwise-fatal line 82
  `ait_tmux display-message -p '#S'` cross-server probe under `set -e`.
- **Legacy-session offer** (between the failed `has-session` at line 97 and
  `spawn_session_detached` at line 109): skip when the resolved socket is the
  default server already (`ait_tmux_socket_name` empty or `default`). Otherwise
  if `ait_tmux_legacy has-session -t "$SESSION_T" 2>/dev/null`:
  - TTY (`[[ -t 0 && -t 1 ]]`): prompt
    "Session '<S>' exists on the legacy default tmux server (pre-dedicated-socket).
    Attach to it instead? [y/N]". On `y`: capture
    `ait_tmux_legacy_socket_args` into an array and
    `exec tmux "${_LEGACY_ARGS[@]}" attach -t "$SESSION_T"`. On anything else:
    fall through to spawn on the dedicated socket (one-time hint printed).
  - non-TTY: stderr warning with the `AITASKS_TMUX_SOCKET=default ait ide` hint,
    fall through.
- Fix the stale `_IDE_SOCK_ARGS` comment (lines 65–68, "Empty by default …
  byte-identical to before").

### 4. Bootstrap warning (`.aitask-scripts/lib/tmux_bootstrap.sh`)

In `spawn_session_detached` inside the `if ! ait_tmux has-session` block,
before `ait_tmux_new_session_persistent`: same skip-guard as above, then
`ait_tmux_legacy has-session ... && warn "session '<s>' also exists on the
legacy default tmux server; run AITASKS_TMUX_SOCKET=default ait ide to reach
it"` (stderr; the tui_switcher `_ensure_session_live` path only surfaces stderr
on failure — accepted, warn-only there).

### 5. `TODO(socket-move)` holdout routing

- `monitor/monitor_app.py`: add module-level `_TMUX = TmuxClient()`
  (+ `tmux_session_target` import; `lib/` already on sys.path):
  - `has-session` site (~line 516): `rc, _ = _TMUX.run(["has-session", "-t", session_target(self._expected_session)])`, branch on `rc == 0`.
  - `rename-session` site (~line 251, SessionRenameDialog): route via `_TMUX.run`
    and add explicit `-t =<current>` target (dialog holds `self._current`) so the
    migration-window failure mode is a clean rc≠0 → existing notify path.
  - `rename-window` self-probe (line 63) and `_detect_tmux_session` (line 1832)
    stay raw (ambient; `tests/test_monitor_rename_window_target.sh` pins the raw
    argv).
- `codebrowser/codebrowser_app.py`: module-level `_TMUX = TmuxClient()`:
  - `show-environment` (~518) / `set-environment` (~540) → `_TMUX.run([...])`,
    `rc != 0 → None` mapping unchanged. (The matching *writer* is already
    gateway-routed: `agent_launch_utils.py:756`.) `_detect_*` probes stay raw.
- `tests/test_no_raw_tmux.sh` allowlist comments: drop the `TODO(socket-move)`
  halves for monitor_app/codebrowser; fix the stale `tmux_monitor.py` reason
  ("raw per-tick fallback helpers" — none remain; entry can likely be dropped,
  verify guard still passes).

### 6. Test updates

- `tests/lib/tmux_isolation.sh::require_isolated_tmux`: add
  `export AITASKS_TMUX_SOCKET=""` (pins gateway to no-flag so fixtures spawned
  raw and gateway-routed app code agree inside the isolated `TMUX_TMPDIR`; also
  shields the suite from a user's custom env value — latent leak even today).
  All 9 live-tmux shell tests source this helper (verified, incl.
  `test_tmux_persistent_scope.sh`).
- `tests/test_tmux_exec.py`:
  - `test_unset_is_empty` → assert `["-L", "ait"]`, rename
    `test_unset_is_dedicated_default`.
  - keep whitespace test (→ `[]`) but re-comment as the escape hatch; add
    `test_empty_string_is_no_flag` and `test_default_value_is_default_socket`
    (`"default"` → `["-L", "default"]`).
  - rename `test_no_socket_when_unset` → `..._when_empty` (already constructs
    `socket_args=[]` explicitly).
- `tests/test_discover_default_unchanged.py` + `tests/test_discover_include_registered.py`:
  mocks prefix-match `argv[:2] == ["tmux", "list-sessions"]` and break post-flip
  (module-level `_TMUX` caches env at import). Set
  `os.environ["AITASKS_TMUX_SOCKET"] = ""` **before** `import agent_launch_utils`.
- `tests/test_launch_in_tmux_pane_pid.py::TestLaunchInTmuxIntegration`: currently
  un-isolated live-tmux test — post-flip it would touch a real `-L ait` server.
  Add isolation in setUp/tearDown (private `TMUX_TMPDIR`, `AITASKS_TMUX_SOCKET=<testsock>`,
  `AIT_NO_SYSTEMD_RUN=1`, and rebuild/restore `agent_launch_utils._TMUX` since it
  is cached at import; do cleanup through that client), mirroring
  `test_tmux_exec.py::TestGatewayIntegration`.

### 7. Documentation

- `aidocs/applink/wish_ssh_evaluation.md` ~219–223: "default socket today" →
  dedicated `-L ait` by default (t953); ~234–238 Layer-B wording → "whatever
  server `$TMUX` points at".
- `website/content/docs/installation/terminal-setup.md`: line 85 example →
  `tmux -L ait new-session ...`; line 88 attach hint → `tmux -L ait attach ...`;
  line 73 note the shared dedicated server; add the `AITASKS_TMUX_SOCKET`
  semantics table (this is the knob's user-facing home).
- `website/content/docs/installation/macos.md:88`: `tmux kill-server` →
  `tmux -L ait kill-server`.
- `aidocs/framework/tui_conventions.md` (~328–336 tmux-stress section): note
  sessions live on `-L ait`; isolation helper pins `AITASKS_TMUX_SOCKET=""`.
- One comment line in `aitask_companion_cleanup.sh` documenting why raw is
  correct (tmux fills `$TMUX` in hook/server-job environments, so hook commands
  always reach the server that fired them).

## Explicitly out of scope / rejected

- **`-S <runtime-dir>` socket paths**: `-L` retained per t952 decision (composes
  with `TMUX_TMPDIR` + test isolation). Revisit only when the hosted deployment
  needs an absolute path.
- **Dispatcher-export and config-file knobs**: rejected (split-brain risk for
  direct script invocation; t952 already rejected project_config for
  server-level state).
- **Auto-migrating legacy sessions**: impossible — tmux cannot move sessions
  between servers. Detection + offer + hint is the whole story.
- **Routing ambient `$TMUX` self-probes through the gateway**: deliberately NOT
  done — they must follow the server the TUI actually runs in (Layer B).

## Verification

1. `bash tests/test_tmux_exec.py` (via python), `bash tests/test_no_raw_tmux.sh`,
   `bash tests/test_tmux_run_parity.sh`, `bash tests/test_discover_default_unchanged.py`
   (python), `bash tests/test_launch_in_tmux_pane_pid.py` (python) — plus the
   full live-tmux set: `test_multi_session_primitives.sh`,
   `test_tui_switcher_multi_session.sh`, `test_tmux_persistent_scope.sh`,
   `test_monitor_rename_window_target.sh`.
2. `shellcheck .aitask-scripts/aitask_ide.sh .aitask-scripts/lib/tmux_exec.sh .aitask-scripts/lib/tmux_bootstrap.sh`.
3. Manual smoke (live box): `ait ide` from a clean shell → session lands on
   `-L ait` (`tmux -L ait ls`), survives `systemctl --user status` check under
   `session.slice`; `tmux ls` (default server) unaffected; legacy-offer prompt
   fires when a same-name default-socket session exists; `AITASKS_TMUX_SOCKET=default ait ide`
   reaches the legacy server.
4. Step 9 (Post-Implementation): archive via `aitask_archive.sh 953`, push.

## Risk

### Code-health risk: medium
- The default flips at the gateway chokepoint that every tmux invocation flows
  through; any code path that constructs a gateway client before the test
  harness/env pins `AITASKS_TMUX_SOCKET` (module-level `_TMUX` singletons cache
  at import) silently targets the wrong server. The known cases
  (test_discover_*, test_launch_in_tmux_pane_pid) are fixed in-plan; un-audited
  stragglers are possible · severity: medium · → mitigation: manual_verification_dedicated_socket
- Migration-window cross-server semantics: gateway-routed self-probes invoked
  from a foreign server (user's personal tmux, legacy session) change meaning
  post-flip. The three entry points (ide socket-identity check, bootstrap
  warning, switcher) are guarded; ambient probes elsewhere are accepted
  · severity: medium · → mitigation: manual_verification_dedicated_socket
- Stale prose/comments asserting "default socket" semantics scattered across
  call sites; sweep is in-plan but a missed one misleads future editors
  · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- Legacy-attach offer can hit tmux "protocol version mismatch" if the default
  server runs an older binary than the new `-L ait` server (post-upgrade);
  legacy path is best-effort by design, must fail with a clear message, not a
  crash · severity: low · → mitigation: TBD

### Planned mitigations
- timing: after | name: manual_verification_dedicated_socket | type: manual_verification | priority: medium | effort: low | addresses: chokepoint default flip + migration-window cross-server semantics (code-health) | desc: live-box checklist — ait ide lands on `tmux -L ait` under session.slice; default server untouched; legacy-session prompt fires; AITASKS_TMUX_SOCKET=default opt-out reaches legacy server; `j` switcher cross-session teleport works on the dedicated server

## Final Implementation Notes
- **Actual work done:** Implemented exactly per plan. Gateway default flipped in both mirrors (`tmux_exec.py::tmux_socket_args` returns `["-L", "ait"]` when env unset via new `AIT_DEDICATED_SOCKET` constant; shell mirror uses `[[ -z "${AITASKS_TMUX_SOCKET+x}" ]]`). Added `ait_tmux_socket_name()`, `ait_tmux_legacy()`, `ait_tmux_legacy_socket_args()` to the shell gateway. `aitask_ide.sh` gained the inside-tmux socket-identity check (compares `basename "${TMUX%%,*}"` against `ait_tmux_socket_name`) and the interactive legacy-attach offer with `[[ -t 0 && -t 1 ]]` TTY guard; `tmux_bootstrap.sh::spawn_session_detached` gained the non-interactive stderr warning. Holdouts routed: monitor_app.py `has-session` + `rename-session` (the latter now passes an explicit `-t =<current>` target) and codebrowser_app.py `show/set-environment`, each via a module-level `_TMUX = TmuxClient()`. Allowlist comments updated and the stale `tmux_monitor.py` entry dropped (no raw spawns remain there). Tests: isolation harness pins `AITASKS_TMUX_SOCKET=""`; `test_tmux_exec.py` updated/extended (unset→`-L ait`, empty→no flag, `default` opt-out); NEW `tests/test_tmux_socket_args_sh.sh` pins the shell mirror semantics + shell/python parity (13 cases); `test_launch_in_tmux_pane_pid.py::TestLaunchInTmuxIntegration` fully isolated (private TMUX_TMPDIR + test socket + `AIT_NO_SYSTEMD_RUN` + singleton swap). Docs: wish_ssh_evaluation.md, terminal-setup.md (new "The dedicated tmux server" section with the knob table and migration note), macos.md, tui_conventions.md, companion_cleanup.sh raw-by-design comment.
- **Deviations from plan:** One: the discover tests' env-pin-before-import approach from the plan failed under `run_all_python_tests.sh` (single process — another module imports `agent_launch_utils` first and freezes the cached socket args), so both discover test files instead swap `agent_launch_utils._TMUX` with a `TmuxClient(socket_args=[])` in setUp and restore in tearDown. Deterministic regardless of import order.
- **Issues encountered:** `tests/lib/asserts.sh::assert_eq` takes `<desc> <expected> <actual>` (desc first) — initial new-test draft had the args reversed; fixed. Aggregate python suite surfaced the import-order issue above; standalone runs had masked it.
- **Key decisions:** Opt-out spelling is `AITASKS_TMUX_SOCKET=default` — tmux's default socket is literally named `default`, so no sentinel parsing was needed in the gateway. Set-but-empty stays the no-flag escape hatch (load-bearing for test isolation, where fixtures spawned raw without `-L` must agree with gateway-routed app code). The `monitor_app.py` `rename-window` self-probe and all `_detect_*` `display-message` probes deliberately stay raw (ambient Layer-B, follow `$TMUX`); `tests/test_monitor_rename_window_target.sh` pins the raw argv byte-for-byte.
- **Upstream defects identified:**
  - `tests/test_settings_shortcuts_tab.py:?? (test_tab_titles_carry_current_shortcut)` — fails ONLY under `tests/run_all_python_tests.sh` (aggregate single-process run; `'Proje(c)t Config' != 'Proje(C)t Config'`), passes standalone. Pre-existing on HEAD before this task (verified via git stash); looks like cross-test state leakage in shortcut-label casing (possibly `shortcut_label_case` config or shared registry bleeding between test modules).
- **Build verification:** No `verify_build` configured. Full test battery run instead: all 11 live-tmux shell tests pass, `test_no_raw_tmux.sh` passes, new socket-args test 13/13, full python suite (1187 tests) back to HEAD baseline (the one pre-existing aggregate-only failure above).
