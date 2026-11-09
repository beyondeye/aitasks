---
Task: t2262_restart_server_version_spawns_foreign_code.md
Base branch: main
Output branch: main
---

# t2262 — `--restart-server --version V` must not spawn this tree's code under V's key

## Context

`ait monitor --restart-server --version V` (`status_server.py restart`,
`_cmd_restart` at `.aitask-scripts/monitor/status_server.py:1238`) retires V's
server for the current tmux server, then calls `ensure_server(version=V)`. That
spawns **this checkout's** `SERVER_SCRIPT` (`:134`, argv at `:323`) under V's
socket key with `--version V`. V's clients accept it, because the handshake only
compares the version string, and are then served by another release's producer
code. That breaks the "one server per (tmux server, `VERSION`)" rule
(`aidocs/framework/monitor_status_protocol.md` "Scope").

**Chosen fix: retire-only for a foreign version.** When `V` ≠ this checkout's
`framework_version()`, stop V's server (same verified SIGTERM via
`status_restart.retire_one`) and **do not** call `ensure_server`. V's own clients
respawn the server from their own files on reconnect: the documented loss path
is fallback, then a reconnect whose first delay is 0, and that reconnect's
`ensure` uses the client's own `VERSION` (`status_client.py:305`, `:497`). That
recovery path is already covered end-to-end by
`tests/test_monitor_status_client_live.py::test_server_killed_falls_back_then_reconnects`
(real SIGTERM → in-process fallback → the client's own `ensure` spawns a new
server → resubscribe), so it is in the verification list below; no new client
test machinery is needed. This matches the `ait upgrade` hook, which already
retires and lets clients respawn.
It is more useful than refusing outright, because an operator can still clear a
stuck server of another version from any checkout.

The `ensure --version V` CLI is left as it is. It is the test seam that the live
tests use throughout, and the task scopes the defect to the operator verb.

## Implementation

### 1. `.aitask-scripts/monitor/status_server.py` — `_cmd_restart`

- `own = framework_version()`; `version = args.version or own`.
- Keep the `tmux_socket is None` → `UNAVAILABLE:no_tmux_server` branch unchanged.
- Keep the retire block unchanged (`RETIRED` / `STALE` / `RETIRE_FAILED` → rc 1 /
  `NO_SERVER:`).
- New branch after the retire block, before `ensure_server`:
  ```python
  if version != own:
      print(f"RETIRE_ONLY:{target}|version={version}|installed={own}", flush=True)
      print(f"restart: {version} is not this project's framework version ({own}); "
            "its server was stopped but not restarted from this project's files. "
            f"Clients on {version} start a fresh one from their own files when they "
            f"reconnect; to start it now, run 'ait monitor --restart-server' from a "
            f"project on {version}.", file=sys.stderr, flush=True)
      return 0
  ```
  The `RETIRE_FAILED` early return still comes first, so a foreign server that
  did not stop still exits 1.
- Update the `_cmd_restart` docstring and the `restart` subparser help ("…and
  start a fresh one; a foreign --version is retire-only").

### 2. `.aitask-scripts/monitor/monitor_app.py:4163` — `--restart-server` help

Replace "--version V picks another version" with: "--version V of another
framework version only stops that server; its own clients restart it".

### 3. Docs (current-state only)

- `website/content/docs/tuis/monitor/reference.md:233` — the `--restart-server`
  row: "Add `--version V` to stop the server of another framework version; it is
  not restarted from this project — clients on V start a fresh one when they
  reconnect."
- `website/content/docs/tuis/monitor/how-to.md` (~line 425, the paragraph about a
  server listed with another version): add the `--version V` route and its
  `RETIRE_ONLY:<socket>|version=<V>|installed=<this>` output, keeping "run
  `--restart-server` from a project on V" as the way to start one immediately.
- `aidocs/framework/monitor_status_protocol.md:970`, the Entry points row: the
  "Then" cell becomes "V = installed `VERSION`: `ensure_server` in-process, then
  a probe → `REPLACEMENT:…`. Any other V: retire only — `RETIRE_ONLY:<sock>|
  version=<V>|installed=<v>`; no ensure, since the replacement would run this
  tree's code under V's key; V's clients respawn it." Also adjust the CLI
  listing near `:760` if its description implies a restart for every version.
- Run `python3 check_links.py --build` in `website/`.

### 4. Tests

**Pre-fix control first.** Write the new tests before the code change and run
them against the unmodified `status_server.py`. Each foreign-version test must
fail on HEAD (HEAD prints `STARTED:`/`REPLACEMENT:` and creates the socket).
Then apply step 1 and run them green.

`tests/test_monitor_status_server_live.py`, `RestartTests` (real isolated tmux
plus scratch `XDG_RUNTIME_DIR`):
- The existing `test_restart_replaces_this_tmux_servers_server_only` and
  `test_restart_without_a_running_server_starts_one` use the made-up versions
  `rst`/`fresh`, which are now foreign. Switch them to the installed version
  (`ss.framework_version()`, imported the same way the file imports
  `status_paths`). The runtime dir and the tmux server are scratch, so this
  cannot touch real servers. Their assertions stay as they are.
- New `test_foreign_version_restart_retires_without_spawning`: `ensure
  --version foreignX` (p1), then `restart --version foreignX`. Expect rc 0,
  lines `RETIRED:<sock>|pid=p1` and then
  `RETIRE_ONLY:<sock>|version=foreignX|installed=<own>`, no
  `STARTED`/`REPLACEMENT` line, p1 gone, socket absent after a short settle, and
  `status` → `NO_SERVER`. This shows that this tree's script was never spawned
  under the foreign key.
- New `test_foreign_version_restart_without_server_starts_nothing`: `restart
  --version foreignY` with nothing running → `NO_SERVER:<sock>`, `RETIRE_ONLY:…`,
  rc 0, socket still absent.

`tests/test_monitor_status_server.py`: new tmux-free `RestartVerbTests`. It
patches `ss.tmux_socket_path`, `ss.server_paths` (scratch dir),
`ss.srst.retire_one` and `ss.ensure_server` with `unittest.mock.patch.object`
and calls `ss._cmd_restart(SimpleNamespace(...))`:
- foreign version → `ensure_server` never called, `RETIRE_ONLY` printed, rc 0;
- foreign version plus `RETIRE_FAILED` → rc 1, `ensure_server` not called;
- installed version (`args.version=None` and `args.version=VERSION`) →
  `ensure_server` called once with `version=VERSION` (the fix must not regress
  the own-version path).

## Verification

```bash
python3 tests/test_monitor_status_server.py
python3 tests/test_monitor_status_server_live.py
python3 tests/test_monitor_status_restart.py
bash tests/test_monitor_server_restart_hook.sh
python3 tests/test_monitor_status_client_live.py   # client recovery the retire-only design relies on

(cd website && python3 check_links.py --build)
```

Manual: `ait monitor --restart-server --version bogus` in a live tmux → prints
`NO_SERVER:` / `RETIRE_ONLY:` plus the stderr hint, and `ait monitor
--server-status` shows no `bogus` server.

Post-implementation: Step 9 (commit, archive, merge per the workflow).

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** `_cmd_restart` (`.aitask-scripts/monitor/status_server.py`) now compares the target version with `framework_version()`; a foreign version keeps the existing retire block (`RETIRED` / `STALE` / `NO_SERVER`, `RETIRE_FAILED` → rc 1) and then prints `RETIRE_ONLY:<sock>|version=<V>|installed=<own>` plus a stderr hint, returning 0 without calling `ensure_server`. Help text updated in the `restart` subparser and `monitor_app.py --restart-server`. Docs: `reference.md` `--restart-server` row, `how-to.md` foreign-version paragraph (with `RETIRE_ONLY` output), protocol doc Entry points row. Tests: new tmux-free `RestartVerbTests` (4) in `tests/test_monitor_status_server.py`; two new live tests in `RestartTests`; the two existing live restart tests moved from the invented versions `rst` / `fresh` to the installed version (`sr.framework_version()`), since those versions are now foreign.
- **Deviations from plan:** The stderr hint first said "its server was stopped" unconditionally; the manual run with no server showed that was false, so it now says "its server was stopped" only when a `RETIRED:` pid was seen, else "no server of it was running". The protocol doc's CLI listing (~line 760) needed no change — it makes no per-version claim.
- **Issues encountered:** `aidocs/framework/monitor_status_protocol.md` carried another session's uncommitted hunks (~lines 1080–1099, client startup prose); only the line-970 hunk is this task's and only it is committed. Concurrent sessions also touched `status_client.py`, `applink/server.py`, `tests/test_monitor_status_client.py` during the work — untouched and not committed here.
- **Key decisions:** Retire-only rather than refuse — it keeps an operator able to clear another version's stuck server, and matches the `ait upgrade` hook (retire, clients respawn). The respawn path it relies on is covered by `tests/test_monitor_status_client_live.py::test_server_killed_falls_back_then_reconnects` (added to verification after plan review). The `ensure --version V` CLI is deliberately unchanged: it is the live tests' isolation seam, and reconnecting clients always pass their own `VERSION`.
- **Pre-fix control:** against HEAD's `status_server.py`, the 2 foreign unit tests and 2 foreign live tests failed (`ensure_server(version='0.0.0-foreign')` called / `REPLACEMENT:` printed); `test_foreign_version_retire_failure_still_fails` and `test_installed_version_still_restarts` passed on HEAD by design (they pin preserved behaviour). After the fix all pass. Full verification: `test_monitor_status_server.py` 44 OK, `_live` 13 OK, `test_monitor_status_restart.py` 23 OK, `test_monitor_server_restart_hook.sh` 13/13, `test_monitor_status_client_live.py` 1 OK, `check_links.py --build` PASSED.
- **Upstream defects identified:** None
