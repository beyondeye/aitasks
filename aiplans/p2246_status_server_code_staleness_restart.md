---
Task: t2246_status_server_code_staleness_restart.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2246 — Reliable explicit restart of the monitor status server (verified SIGTERM + update integration)

## Context

The shared monitor status server (t2037) is keyed on (tmux socket, framework
`VERSION`) only. A commit that changes producer code without a `VERSION` bump
never retires the running server: it exits only after 30 s with no
subscriber, which never happens while a minimonitor is open. Producer fixes
are therefore silently masked.

Found live on 2026-11-08: the `agent-sitrep` window showed the sitrep TUI as an
agent card. The t2211_2 filter was in the code, but server pid 3870908, started
2026-11-06, still ran the pre-filter discovery.

**Scope, narrowed at the user's direction (the Go server, aitasks_go#t47, is
planned to replace the Python one; minimise complexity before then):**
- **In:** an explicit, verified-SIGTERM restart procedure;
- **In:** the operator verbs `ait monitor --restart-server` / `--server-status`;
- **In:** integration with `ait upgrade`;
- **In:** a written restart contract for the Go binary.
- **Deferred:**
  - content-derived code identity, source watching, socket keying on code and
    the TUI mismatch signal, all to a follow-up task;
  - a `retire` protocol request and forced termination (SIGKILL), until their
    necessity is demonstrated. A hung server is reported and recovered by hand.

**No protocol change and no server behaviour change.** The server already
handles SIGTERM as a graceful `request_exit("signal")`
(`status_server.py:_serve_main`): it closes every connection and the control
client, and unlinks its own socket.

## The restart procedure

Every outcome is backed by positive evidence about the old server's
**process**. Socket silence is never treated as evidence, and neither is the
lock, because a reconnecting client can legitimately take the lock for a fresh
server mid-procedure. The procedure is bounded and never loops.

For each target socket:

1. **Identify the process.** Run `ps -ww -eo pid=,args=`; `-ww` keeps args
   from being truncated on both procps and BSD ps. Keep the entries whose args
   contain ` serve ` and `--socket <sock>`, where the socket path is followed
   by a space or the end of the string.
   - Exactly one match gives the pid.
   - No match, and the socket path no longer accepts a connection →
     `STALE:<sock>`. This is not a failure: `ensure` removes stale sockets
     under the lock.
   - No match, but the socket accepts a connection →
     `RETIRE_FAILED:<sock>|unverified`, and no signal is sent.
   - More than one match → `RETIRE_FAILED:<sock>|ambiguous_pids`, and no
     signal is sent.
2. **Owner filter** (`--owner-path P`, used only by the upgrade hook): skip the
   target unless its args contain `P serve `. P is realpath'd, and
   `SERVER_SCRIPT` is already the resolved path. A skip prints
   `SKIPPED:<sock>|other_owner`.
3. **Re-verify the args for that pid** (`ps -ww -o args= -p <pid>`), then send
   `SIGTERM`.
4. **Wait up to 5 s for the pid to be gone.** Gone means `kill(pid, 0)` raises
   `ProcessLookupError`, **or** the pid's args no longer match. The args check
   covers a zombie (a detached server can stay a zombie child of the
   minimonitor that spawned it) and a recycled pid.
5. **Report.**
   - Success: `RETIRED:<sock>|pid=<p>`.
   - Failure: `RETIRE_FAILED:<sock>|pid=<p>|still_running`, with a stderr hint
     to inspect the pid and end it by hand. There is no SIGKILL escalation.

**Clients need no change.** On SIGTERM the server closes every connection.
Each client takes its existing loss path: fallback, then the reconnect loop,
whose first delay is 0. Its `ensure` spawns a fresh server from the files on
disk. That includes TUIs started before this change, because `SERVER_SCRIPT`
is a path on disk.

### Target selection (one rule per entry point)

| Entry point | Targets | Then |
|---|---|---|
| `ait monitor --restart-server [--version V]` | **Only the current tmux server's socket for V**: `server_paths(tmux_socket_path(), V).socket`, with V defaulting to the installed `VERSION`. Other tmux servers' sockets in the shared runtime dir are never touched. | `ensure_server(version=V)` **in-process**, so V propagates. It prints the ensure line plus the replacement's socket and welcome version. |
| `ait monitor --server-status` | Read-only: every socket of the current tmux key, at any version. | Each line: `SERVER:<sock>|pid=<p or ->|started=<ps lstart or ->|version=<slug>|script=<argv path>`, or `NO_SERVER`. |
| `ait upgrade` hook (`install.sh`) | **Owner-scoped, intentionally broad.** Sockets at any tmux key and any version whose verified process args name *this install's* `status_server.py`. | Nothing. Clients reconnect and respawn from the new files. |

No tmux server answering → `--restart-server` prints
`UNAVAILABLE:no_tmux_server` and exits 1; `--server-status` prints
`NO_SERVER`.

**Known limit, documented:** two trees at the same `VERSION` with different
code share whichever server one of them spawned, and a restart does not choose
which tree respawns it. This is the deferred code-identity work.

### Python vs the future Go binary

The procedure is a **process contract**, not Python internals. Its core lives
in a stdlib-only module, `monitor/status_restart.py`, which applies to
whichever implementation answers at the socket. The protocol doc gets a new
"Restart" section stating this contract for `ait-monitord`:

| Contract | Python (now) | Go `ait-monitord` (t47) |
|---|---|---|
| Process args contain `serve --socket <sock>` | `<python> <tree>/.aitask-scripts/monitor/status_server.py serve --socket …` (already) | `<binary> serve --socket …` |
| SIGTERM → graceful exit (close connections and the control client, unlink its own socket); exit releases the flock | already | required |
| Socket path and key | `server_paths()` (already) | same rule (already required by the protocol spec) |
| Owner path for the upgrade hook | `<tree>/.aitask-scripts/monitor/status_server.py` | the installed binary path (`$AITASKS_HOME/engine/v<V>/ait-monitord`, or `engine/dev/`) |
| Update hook | `install.sh` → `retire --all-keys --all-versions --owner-path <script>` | the engine install (`install_engine_binary` in setup and upgrade; `ait engine build` for dev) runs the same call with `--owner-path <binary>` after replacing the binary |

The Go side therefore needs no new protocol message, only the args shape and
SIGTERM handling it already mirrors. After implementation I will send this
contract to aitasks_go#t47 with `./ait note 47 --project aitasks_go`.

## Implementation steps

1. **`monitor/status_paths.py`** (new, stdlib only).
   - Move from `status_server.py`: `RUNTIME_SUBDIR`, `FALLBACK_RUNTIME_DIR`,
     `_SLUG_RE`, `runtime_dir()`, `version_slug()`, `lock_path_for()`, and the
     socket-stem/key derivation (`tmux_key(tmux_socket)` → 16 hex).
   - `status_server.py` imports these back, so `ss.runtime_dir`,
     `ss.server_paths` and friends keep working for every caller and test.
     `server_paths` stays in `status_server` and uses `tmux_key`.
   - Add `SOCKET_NAME_RE = r"^monitor-(?P<key>[0-9a-f]{16})-(?P<slug>[A-Za-z0-9._+-]{1,64})\.sock$"`.
   - Add `list_server_sockets(directory, *, key=None, version=None)`, filtering
     on the exact key and on `slug == version_slug(version)`, so `0.40.1` never
     matches `0.40.10`.
   - Why the split: the upgrade hook needs these without importing
     `status_server`, which pulls in `monitor_core` → `task_yaml` → `yaml`,
     possibly missing at install time.

2. **`monitor/status_restart.py`** (new, stdlib only; imports
   `status_paths`).
   - Seams for tests: `ps_runner`, `kill`, `sleep`/`clock`.
   - The functions:
     - `server_processes()` parses `ps -ww -eo pid=,args=` through
       `subprocess.run(..., timeout=5)`;
     - `args_match(args, sock, owner=None)`;
     - `socket_connectable(sock)`;
     - `pid_gone(pid, sock)`;
     - `retire_one(sock, owner=None, wait=5.0)`, which runs steps 1-5 and
       returns its line;
     - `retire(sockets, owner=None)`.
   - CLI for the hook only:
     `retire --all-keys --all-versions --owner-path P [--runtime-dir D]`.
     Both `--all-*` flags are required, so the stdlib entry point never
     performs an unscoped retire.

3. **`monitor/status_server.py`** — new CLI verbs, which run with the venv
   python and can reach tmux:
   - `restart [--version V] [--deadline D]`:
     1. `tmux_socket_path()`; `None` → `UNAVAILABLE:no_tmux_server`, exit 1;
     2. the single target is `server_paths(sock_key, V).socket`;
     3. if that file exists → `status_restart.retire_one(target)`;
     4. then `ensure_server(version=V, deadline=D)`, in-process;
     5. print the retire line, the ensure line, and
        `REPLACEMENT:<sock>|pid=<p>|version=<welcome version>` from a
        `probe(sock, V)`.

     Exit 1 on a `RETIRE_FAILED` line or an `UNAVAILABLE` ensure line.
   - `status`: `list_server_sockets(runtime_dir(), key=<current>)`, then the
     per-socket `SERVER:` lines (ps for pid, `lstart` and the script path),
     or `NO_SERVER`.
   - The module docstring gets the CLI list.

4. **`aitask_monitor.sh`**: `--restart-server [--version V]` → `exec "$PYTHON"
   "$SCRIPT_DIR/monitor/status_server.py" restart …`, and `--server-status` →
   `… status`. Both are parsed before the textual/tmux checks, in the same
   argument loop as `--headless-for-applink`; a mixed `--version` is
   forwarded. This is a flag on the existing user-facing `ait monitor`, not a
   new dispatcher case. Mention the flags in the monitor help, if the launcher
   flags are listed there.

5. **Upgrade hook**
   - `aitask_setup.sh`: new `report_monitor_server_restart()`, next to
     `report_home_legacy`. Never fatal. It does nothing when
     `AIT_MONITOR_RESTART=0`. Otherwise:
     1. `py="$(resolve_python)"`; empty → `MONITOR_SERVER:skipped:no_python`;
     2. run `"$py" "$SCRIPT_DIR/monitor/status_restart.py" retire --all-keys --all-versions --owner-path "$SCRIPT_DIR/monitor/status_server.py"`;
     3. relay `RETIRED:` / `RETIRE_FAILED:` lines as `MONITOR_SERVER:<line>`
        and stay silent otherwise.
   - `install.sh`: call it after `commit_installed_files` /
     `commit_installed_data_files`, behind `declare -F` (older tarballs) and
     only when `EXISTING_INSTALL == true`. Verify while implementing that the
     sourced script's `SCRIPT_DIR` resolves to `$INSTALL_DIR/.aitask-scripts`.
   - `ait setup` is not hooked: it does not replace `.aitask-scripts` code.
     The Go engine install gets the binary form when `ait-monitord` ships.

6. **Docs**
   - `aidocs/framework/monitor_status_protocol.md`:
     - CLI list: `restart`, `status`, and `status_restart.py retire`;
     - Exit: note that `restart` and the upgrade hook use SIGTERM;
     - new "Restart" section: the procedure, its evidence rules and deadline,
       the output lines, the target-selection table, the Python/Go contract,
       and the same-`VERSION` known limit;
     - no schema changes.
   - `website/content/docs/tuis/monitor/reference.md`: the two flags in the
     options table, plus one sentence that `ait upgrade` restarts servers
     started from the upgraded project. Run
     `cd website && python3 check_links.py --build`.

7. **Tests**
   - `tests/test_monitor_status_restart.py` (new, unittest, scratch runtime
     dir). It uses `tests/lib/fake_status_server.py`, a real child process
     launched as `… serve --socket <sock> --mode <graceful|hung>`, which binds
     the socket. `graceful` exits on SIGTERM and unlinks the socket; `hung`
     ignores SIGTERM. The cases:
     - graceful → `RETIRED`, the pid is gone, the socket is unlinked;
     - hung → `RETIRE_FAILED:…|still_running` within the scaled deadline, and
       the process is still alive (the test cleans it up);
     - **safety negative:** an in-process listener (no matching ps entry) →
       `RETIRE_FAILED:…|unverified`, and the test process is still alive;
     - ambiguous pids (fake `ps_runner`) → `ambiguous_pids`, and no `kill` is
       recorded;
     - owner filter: a matching path is retired; another path →
       `SKIPPED:…|other_owner`, and that process is untouched;
     - `STALE` for a socket file with no process and no listener;
     - zombie: a fake `ps_runner` reporting `[python3] <defunct>` → `pid_gone`;
     - `list_server_sockets`: `0.40.1` vs `0.40.10`, hash-form slugs, key
       filtering;
     - the `retire` CLI refuses without both `--all-keys` and
       `--all-versions`.
   - `tests/test_monitor_status_server_live.py` (isolated tmux), new e2e:
     1. `ensure --version rst` → old pid P1 and socket S. A second
        fake/graceful server sits on a socket with **another tmux key** at
        version `rst` in the same runtime dir.
     2. `status_server.py restart --version rst`.
     3. Assert `RETIRED:S|pid=P1` and that P1 is gone. There is no
        old-log assertion: the replacement truncates the shared
        `monitor-<key>-<v>.log` (`_spawn_server` opens it with `O_TRUNC`).
     4. Assert the ensure line is `STARTED` at socket **S**, and that
        `REPLACEMENT:S|pid=P2|version=rst` has P2 ≠ P1.
     5. Assert that a fresh `probe(S, "rst")` welcome reports version `rst`
        and pid P2.
     6. Assert the other-key server is **still alive and untouched**.
   - `tests/test_monitor_server_restart_hook.sh` (new): source
     `aitask_setup.sh --source-only` with a scratch `SCRIPT_DIR` and a scratch
     `XDG_RUNTIME_DIR`. Then:
     - a fake server owned by another path survives
       `report_monitor_server_restart`;
     - one owned by the scratch path is retired (`MONITOR_SERVER:RETIRED:`);
     - `AIT_MONITOR_RESTART=0` → no output and no signal.
   - Existing `status_server` tests keep passing through the re-exported
     names.

8. **Follow-ups (post-approval writes):**
   - create a deferred task: "Status server: content-derived code identity,
     source watching and mismatch signal". It carries this session's analysis:
     policy (a)+(c), the ping-pong argument against (b), the input-set and
     hash-before-import notes, and that `retire` and SIGKILL escalation were
     deferred pending demonstrated need. Low priority, to be picked after t47's
     shape is known;
   - send the restart-contract note to aitasks_go#t47.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` (the last line must be
  `PYTHON SUITE: PASSED`), `bash tests/test_monitor_server_restart_hook.sh`,
  `shellcheck .aitask-scripts/aitask_setup.sh .aitask-scripts/aitask_monitor.sh install.sh`,
  `cd website && python3 check_links.py --build`.
- Scratch install flow: install into a scratch dir twice, the second time as
  an upgrade, with a fake server owned by the scratch tree. It is retired, and
  the real servers are unchanged (compare `ait monitor --server-status` before
  and after).
- Live:
  1. `ait monitor --server-status` shows the 2026-11-06 server.
  2. `ait monitor --restart-server` → `RETIRED`, then `STARTED`, then
     `REPLACEMENT:…|version=0.40.1`.
  3. The `agent-sitrep` minimonitor lists exactly one item (the agent), and the
     sitrep TUI pane is absent from both monitor and minimonitor.
- Step 9 (Post-Implementation) handles the commit, the archival and the merge
  (current branch).

## Risk

### Code-health risk: medium
- New code sends SIGTERM; a wrong pid match would stop an unrelated process. Contained by an args check before the signal (`serve` plus the exact `--socket <sock>`, re-verified for the pid), by refusing unverified or ambiguous pids, and by negative tests asserting the test process is never signalled · severity: medium · → mitigation: none
- The `ait upgrade` hook runs on every user's upgrade and in install-flow tests, which share the real `XDG_RUNTIME_DIR`. Contained by `--owner-path` (only servers spawned from the upgraded tree), the mandatory `--all-keys`/`--all-versions` flags, the `AIT_MONITOR_RESTART=0` opt-out, never-fatal handling and a `declare -F` guard, plus the hook test and the scratch install flow · severity: medium · → mitigation: none
- Moving the path helpers into `status_paths.py` touches imports used by existing callers and tests. The re-exports keep the `ss.*` names · severity: low · → mitigation: none

### Goal-achievement risk: medium
- The user-visible fix (SIGTERM-retire the 2026-11-06 server, then one item in the `agent-sitrep` minimonitor) and the upgrade-hook scoping can only be confirmed live · severity: medium · → mitigation: sitrep_window_live_check
- A hung server is reported, not forced (deferred SIGKILL), so it needs a manual `kill` · severity: low · → mitigation: none
- Dev checkouts still rely on an explicit `ait monitor --restart-server` after producer commits. Automatic detection is deferred to the follow-up task · severity: low · → mitigation: none
- Trees at the same `VERSION` with different code share one server; a restart does not choose which tree respawns it. This is a documented known limit · severity: low · → mitigation: none

### Planned mitigations
- timing: after | name: sitrep_window_live_check | type: manual_verification | priority: medium | effort: low | inline_risk: low | added_complexity: medium | addresses: live confirmation of the restart against the real pre-change server, the agent-sitrep single-item result, and upgrade-hook scoping | desc: Live check — --server-status shows the old server; --restart-server retires it and prints STARTED plus REPLACEMENT with the requested version at the same socket; agent-sitrep minimonitor lists exactly one item; a scratch ait upgrade retires only servers owned by the upgraded tree

## Post-Review Changes

### Change Request 1 (2026-11-09 11:40)
- **Requested by user:** fix four review findings: the owner scope was missing
  from the pre-signal recheck; a failed `ps` was read as absence; `--wait inf`
  was accepted; the website promised a reconnect timing. Also check the
  website coverage of the shared server and create a follow-up if it is
  missing.
- **Changes made:**
  - `status_restart.py`:
    - the pre-signal re-read now applies `owner` (→ `SKIPPED|other_owner`);
    - `run_ps` returns `None` on any nonzero exit, so absence is proven only by
      `kill(pid, 0)`, and a recheck that cannot read the args checks `kill`
      before choosing `STALE` vs `ps_unavailable`;
    - `_positive` requires a finite value, and `retire_one` raises on a
      non-finite or non-positive `wait`.
  - `reference.md`: "reconnect … automatically".
  - Tests added: `InspectionFailureTests` (through the real `run_ps`; both
    fail under the old `run_ps` — pre-fix control run), `OwnerRecheckTests`,
    and `test_wait_must_be_finite`.
  - Created t2256 (website docs for the shared monitor status server).
- **Files affected:** `.aitask-scripts/monitor/status_restart.py`,
  `tests/test_monitor_status_restart.py`,
  `website/content/docs/tuis/monitor/reference.md`

## Final Implementation Notes
- **Actual work done:** as planned.
  - `monitor/status_paths.py`: the stdlib path helpers moved out of
    `status_server.py` (re-exported) and `list_server_sockets()` added.
  - `monitor/status_restart.py`: stdlib verified-SIGTERM procedure, and the
    owner-scoped `retire` CLI.
  - `status_server.py` gained the `restart` (current tmux key only; in-process
    `ensure_server(version=V)`; `REPLACEMENT:` probe) and `status` verbs.
  - `ait monitor --restart-server` / `--server-status`: `aitask_monitor.sh`
    intercepts them, and `monitor_app.py` declares them for `--help`.
  - `aitask_setup.sh:report_monitor_server_restart` is called from
    `install.sh` on existing installs.
  - Docs: the protocol doc "Restart" section, and the website reference rows.
  - Follow-ups created: t2253 (the deferred code identity / source watching /
    mismatch signal) and t2256 (website docs gap).
- **Deviations from plan:**
  - `restart` refuses to run `ensure` after a `RETIRE_FAILED`, since `ensure`
    would reuse the server that did not stop. It also reports
    `REPLACEMENT_FAILED` when the probed pid equals the retired one.
  - With `--owner-path`, a socket that something answers but no verifiable
    process owns is reported as `SKIPPED|unverified`, not as a failure.
  - The hook reports `MONITOR_SERVER:failed:helper_exit_<rc>` when the helper
    cannot run.
- **Issues encountered:**
  - Scratch install verification: the first upgrade run left the scratch
    server alive. The resolved `~/.aitask/bin/python3` is a shim to
    `$HOME/.aitask/venv/bin/python`, missing under a scratch `HOME`, so it
    exited 127. The hook had swallowed this silently; fixed by reporting the
    helper failure, and covered by case 5 of the hook test. With
    `AIT_PYTHON=/usr/bin/python3`, the scratch upgrade retired only the
    scratch-owned server, and the real 0.40.1 server was untouched.
  - Install-flow bash tests failed under `/tmp` with "Disk quota exceeded"
    (per-user tmpfs quota exhausted by other sessions' leftovers). They pass
    with a disk-backed `TMPDIR` (`test_install_changelog_preservation`,
    `test_install_upgrade_dirty_baseline`,
    `test_upgrade_prunes_retired_scripts`, `test_aitasks_home` 460/460).
  - t2245 (another session) held uncommitted hunks in `status_server.py`,
    `test_monitor_status_server_live.py` and the protocol doc. It committed
    `a5763bd4e` with only its own hunks, and afterwards those files diffed
    only by t2246's hunks. They were re-tested against the new HEAD (190
    status-server tests passed).
- **Key decisions:**
  - Verified SIGTERM only: no `retire` protocol request and no SIGKILL; a hung
    server is reported for manual recovery.
  - Evidence is the process (`ps -ww` args `serve --socket <sock>` plus
    `kill(pid, 0)`), never socket silence or the lock.
  - The operator restart is scoped to the current tmux key; only the
    owner-scoped upgrade hook scans every key and version.
  - No `ait` dispatcher case: these are flags on `ait monitor`.
- **Upstream defects identified:** None
