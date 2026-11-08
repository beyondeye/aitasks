---
Task: t2242_control_attach_exact_session_target.md
Base branch: main
Output branch: main
---

# t2242 — Control-mode attach uses an exact-match session target

## Context

`TmuxControlClient._attach_argv` (`.aitask-scripts/monitor/monitor_core.py:1541`)
builds `tmux -u [-L sock] -C attach -t <session> -f no-output,ignore-size` with the
**bare** session name. tmux prefix-matches a bare `-t`, so when the project's
session (`aitasks`) is not running but a prefix-sharing one (`aitasks_mob`) is,
the monitor's persistent control client attaches to the other project's session
and serves every per-tick query from it. This violates `tmux_gateway.md` policy 2,
whose table already lists `attach` as session-typed → `session_target()` (`=<s>`).

Both constructors (`TmuxMonitor.start_control_client` near `:1833` and the
supervisor reconnect near `:1907`) pass `self.session` raw, but **both go through
`_attach_argv`**, so fixing that one method covers both paths. It is the only
`attach` call site in `.aitask-scripts/` Python (grepped).

## Implementation

### 1. `.aitask-scripts/monitor/monitor_core.py`
- Add `session_target` to the existing `from tmux_exec import (...)` block (line 42).
- In `_attach_argv`, replace `"-t", self.session` with
  `"-t", session_target(self.session)`.
- Extend the docstring: one sentence saying the target is exact-match
  (`session_target`, policy 2) so an absent session fails the attach instead of
  prefix-matching a sibling project's session; covers both the initial start and
  the supervisor reconnect, which both build their argv here.

### 2. `tests/test_tmux_exec.py` — `TestControlAttachArgv`
- Update the two pinned argvs to expect `"-t", "=mysess"`.
- Add `test_attach_target_is_exact_match`: assert the argv element after `-t`
  equals `session_target("mysess")` (import from `tmux_exec`), so the pin is tied
  to the helper rather than to a literal only.

### 3. `tests/test_tmux_control.sh` — new Case 13: no prefix attach on `start()`
Own fixture/server (same `make_fixture`/`teardown_fixture` + `trap` pattern as the
other cases). Start **only** a decoy session `S_mob` (`S="ait_test_$$_m"`).
Python heredoc (via `monitor.monitor_core.TmuxControlClient`, `asyncio.run`):
1. **Pre-fix control (proves the fixture exercises prefix matching on this tmux):**
   a client whose `_attach_argv` is monkeypatched on the instance to the old bare
   form (`["tmux", *TMUX_CLIENT_FLAGS, *socket_args, "-C", "attach", "-t", S,
   "-f", "no-output,ignore-size"]`) must `start()` → True, and
   `request(["display-message", "-p", "#{session_name}"])` must answer `S_mob`.
   If it does not, fail loudly ("control did not reproduce the prefix match —
   regression below would be vacuous").
2. **Fix:** a real `TmuxControlClient(session=S)` must not attach: either
   `start()` returns False, or (tolerance for a slow attach-fail beyond the 50 ms
   window) it is not alive within 2 s — and in no case does a request answer
   `S_mob`.
3. **Exact match still attaches:** `TmuxControlClient(session=S_mob)` →
   `start()` True and `#{session_name}` == `S_mob`.
4. Close all clients.

### 4. `tests/test_tmux_control_resilience.sh` — new Case B2: reconnect does not prefix-attach
Modelled on Case B (target session destroyed → bounded retries → FALLBACK), with a
decoy: create `S` and `S_mob`, `TmuxControlBackend(session=S).start()`, then
`kill-session -t =S` (leaving `S_mob` up). Wait up to 30 s:
- final state must be `TmuxControlState.FALLBACK` (pre-fix, the reconnect would
  prefix-attach to `S_mob` and land in CONNECTED), `not b.is_alive`;
- no request issued during the wait answers `#{session_name}` == `S_mob`.
Pre-fix control for the reconnect path: before the real run, monkeypatch
`TmuxControlClient._attach_argv` (class-level, restored in `finally`) to the bare
form, run the same sequence on a fresh backend, and assert it reaches CONNECTED
with `#{session_name}` == `S_mob` — proving the reconnect path reproduces the
defect, so the FALLBACK assertion is not vacuous. Update the file's header case
list with B2.

### 5. Docs
`aidocs/framework/tmux_gateway.md` policy 2 already lists `attach` as
session-typed; no change needed. No website docs touched.

## Verification
- `bash tests/test_tmux_control.sh` (incl. Case 13)
- `bash tests/test_tmux_control_resilience.sh` (incl. Case B2)
- `bash tests/test_tmux_utf8_client_live.sh` (control attach to a non-ASCII session
  name now goes through `=<name>`)
- Framework interpreter (`require_ait_python` → `~/.aitask/venv/bin/python`):
  `-m pytest tests/test_tmux_exec.py tests/test_monitor_producer_seams.py -q`
- `bash tests/test_no_raw_tmux.sh`
- `shellcheck tests/test_tmux_control.sh tests/test_tmux_control_resilience.sh`

## Step 9 (Post-Implementation)
Commit code + tests as `bug: Attach the control client with an exact-match session target (t2242)`,
then archive via the standard Step 9 flow (current-branch mode, nothing to merge).

## Risk

### Code-health risk: low
None identified. One-line change inside an existing gateway-helper pattern; the
only `attach` call site; both constructors share `_attach_argv`.

### Goal-achievement risk: low
None identified. The live regressions carry in-test pre-fix controls for both the
`start()` and reconnect paths, and the `start()` assertion tolerates an attach-fail
slower than the 50 ms window, so the oracle is the defect itself (never attached
to the decoy), not timing.
