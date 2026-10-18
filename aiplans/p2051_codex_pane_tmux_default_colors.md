---
Task: t2051_codex_pane_tmux_default_colors.md
Base branch: main
Output branch: main
---

# t2051: stop the monitor's control clients from blacking out every pane's default colours

> **Status: UNAPPROVED DRAFT (2026-10-18).** Planning was aborted and the task
> postponed before approval. The user chose the shared root-cause fix (option 4:
> control clients move to an owned helper session, no Codex-specific style). Review
> rounds already folded in: helper ownership marker and foreign-collision fallback,
> detection of project deletion while connected, and keeping `request()`'s transport
> teardown. Re-verify against the current code before implementing; nothing below
> has been implemented.

## Context

Codex draws its "Working" shimmer by blending the terminal's default fg/bg, which it
learns through OSC 10/11. Inside the ait tmux server, tmux answers those queries.
All of the following was measured during planning on a throwaway server
(`-L t2051probe`, tmux 3.8), with a pty-driven fake terminal client that answers
tmux's own colour queries with `#ccddee` / `#223344`:

| clients attached to the pane's session | OSC 10 / 11 reply in that session |
|---|---|
| none | no reply |
| a control-mode client (`tmux -C attach -t <s> -f no-output,ignore-size`, which is exactly what monitor/minimonitor run) | `rgb:0000/0000/0000` for both — **the bug** |
| real client + control client attached **earlier** | black (tmux queried the real terminal and got `#ccddee`/`#223344`, but still answered black) |
| real client only, or real client first and control client later | `rgb:cccc/dddd/eeee` / `rgb:2222/3333/4444`, even for a `-d` background window |
| real client + control clients attached to **another** session | real colours |

**Root cause.** tmux takes a pane's "client colours" from the first client attached
to the pane's session whose colours are set. A control client never learns colours
and reports zero, i.e. black. So it is not Codex-specific: every pane in a session
that holds a monitor/minimonitor control client (Claude panes included) gets
black/black, depending on client order. The live `ait` server has ~8 such clients.

**Fix (user-chosen: shared root-cause fix, no Codex-specific style).** Attach the
control clients to a dedicated helper session instead of the project session. tmux
then answers from the real terminal client, which already queries the outer terminal
itself. That removes any need for our own probing, fallback colours or light/dark
handling, and it is terminal-agnostic.

Mechanism, measured:
- `tmux -C new-session -A -s _ait_control -c / -f no-output,ignore-size 'exec sleep 2147483647' \; set-option -t =_ait_control: destroy-unattached on`
  creates the helper or joins it atomically (two clients joined one helper).
- The helper and its `sleep` are destroyed when the last control client leaves, so it
  never keeps a server alive.
- `-t =_ait_control` (no colon) fails for `set-option`; it needs the
  session-scope `=…:` form.
- A sessionless control client (`tmux -C start-server`) exits right after its command,
  so that is not an option.

Audit of everything routed through the control client
(`monitor.tmux_run` / `tmux_run_async` / `_tmux_async`): every call already passes an
explicit `=<session>:` / pane / window-id target except two:
- `monitor_app.py:1760`: `display-message -p '#S'` with no `-t` would answer the
  helper's name.
- `monitor_shared.py:1042`: `run-shell -b` with no `-t` would run the frozen
  coordinator in the helper session's cwd (`/`). tmux uses the client's session cwd
  for `run-shell`.

The helper is unregistered and its pane cwd is `/`, so discovery's
stamp → pane-vote → registry rule already skips it. It is filtered by name anyway, at
every session-listing surface a user sees.

## Implementation

### 1. Helper-session constant + reservation (`.aitask-scripts/lib/tmux_exec.py`, `tmux_exec.sh`)
- `AIT_CONTROL_SESSION = "_ait_control"`, `AIT_CONTROL_MARKER_OPTION =
  "@aitask_control_helper"` and `AIT_CONTROL_MARKER = "aitasks-control-v1"` in
  `tmux_exec.py`. Mirror the name in `tmux_exec.sh` as `AIT_CONTROL_SESSION`.
- Reservation is **secondary**: it only stops the framework from creating a project
  session with that name. Safety against pre-existing or raw-tmux sessions comes from
  the ownership marker (§2). Reserve the name at every session-name writer, failing
  closed before anything is created:
  - `tmux_bootstrap.sh::_tmux_bootstrap_session_name_ok` (used by `ait ide --session`,
    `ait setup` and the default-session scan): return 1 for `_ait_control`. Adjust the
    `ait ide` refusal message (`aitask_ide.sh:21`) to say "reserved" for that case.
  - `agent_launch_utils._tmux_session_name_ok` and `agent_restore.session_name_ok`
    (its documented twins): same rule.

### 2. Control client attaches to an **owned** helper (`.aitask-scripts/monitor/monitor_core.py`, `TmuxControlClient`)

**Ownership marker.** The framework writes the session user option
`@aitask_control_helper = aitasks-control-v1` (`AIT_CONTROL_MARKER` in `tmux_exec.py`)
in the **same control command list** that creates the helper, so a helper is never
observable unmarked. Only a session carrying the marker is ever joined, filtered or
relied on for `destroy-unattached`. Nothing ever writes to a session without it.

**`start()` protocol** (bounded: 3 passes; `_attach_argv(mode)` builds the argv per
mode so each is unit-testable):
1. Pre-check the project through the gateway (`TmuxClient.run_async`, same socket
   args): `has-session -t =<project>`. If it is missing, return False (today's contract).
2. Inspect: `list-sessions -F '#{session_name}\t#{@aitask_control_helper}'`, then
   match the exact name `_ait_control`.
   - **absent → create:**
     `has-session -t =<p> ; new-session -s _ait_control -c / -f no-output,ignore-size 'exec sleep 2147483647' ; set-option -t =_ait_control: @aitask_control_helper aitasks-control-v1 ; set-option -t =_ait_control: destroy-unattached on`.
     No `-A`: if another backend created it in between, `new-session` fails, the
     client exits, and the next pass joins.
   - **marker == ours → join:** `has-session -t =<p> ; attach-session -t =_ait_control -f no-output,ignore-size`.
     It changes no option. If the helper vanished in between (its last client
     left), the attach fails and the next pass creates.
   - **present with any other marker value, or none → foreign:** never join, filter
     or modify it. Use the **legacy** argv (`attach -t =<p> -f no-output,ignore-size`,
     today's behaviour, functional with today's black colours) and record
     `self.helper_mode = "legacy:foreign-helper"` for diagnostics.
3. A pass that fails after the project pre-check succeeded is treated as a helper
   race and retried. After 3 passes, return False.
- The in-list leading `has-session` keeps the project guard atomic with the attach.
- The startup commands' responses are flag-0 server blocks, which the existing parser
  already drops (measured: `%begin … 0` / `%end … 0` for each).

### 2b. Detect project deletion while connected (`TmuxControlClient` reader)
Once relocated, the client no longer dies with its project session. Measured: a
`no-output` control client receives `%sessions-changed` whenever any session is created
or destroyed. Today's reader discards it. Change:
- On `%sessions-changed`, the reader schedules (`loop.create_task`, never awaited
  inside the reader, so no self-deadlock) a liveness check that sends
  `has-session -t =<project>` through this same client.
- **Only** an `%error` whose body is `can't find session` counts as gone. Then the
  client closes **its own** connection (`close()`), and the supervisor's existing path
  takes over: reconnect attempts fail the project pre-check, and the backend reaches
  FALLBACK. Its departure releases the helper if it was the last client
  (`destroy-unattached`).
- The check's three outcomes stay distinct and are recorded as
  `self.last_project_check ∈ {"present", "gone", "transport"}`:
  - `rc 0` → **present**: nothing happens.
  - `rc 1` with `can't find session` → **gone**: `close()` as above.
  - `rc -1` (timeout, broken pipe, client already dead) → **transport**. The check
    does nothing of its own. `request()`'s existing contract has already torn the
    client down (`_teardown_pending()`; later replies can't be correlated), and that
    teardown is **kept**. The supervisor's normal recovery runs: the reconnect's
    project pre-check passes because the project still exists, so the backend returns
    to CONNECTED. A transport failure is never read as proof the project is gone,
    and never forces the client alive.
  - Any other `rc 1` body → treated as **present**: no teardown we did not cause.
- The check is coalesced, with at most one in flight, and uses its own short timeout
  (`_PROJECT_CHECK_TIMEOUT = 2.0`).
- Other projects' backends sharing the helper are unaffected: their own checks
  report their project present.

### 3. Explicit targets for the two implicit-target calls
- `monitor_app.py::_read_attached_session`: `display-message -p -t <own pane> '#S'`,
  with `<own pane>` = `$TMUX_PANE` when set. Otherwise fall back to
  `tmux_session_scope_target(self._monitor.session)`. Both give today's answer (the
  monitor's own session).
- `monitor_shared.py::_run_frozen_detached`: `run-shell -b -t <scope target of the
  monitor's session>` so the job keeps the project session's cwd. Find the session
  attribute the owning app already holds; it has `self._session` / `self._monitor.session`.

### 4. Keep the **owned** helper off user-facing session lists
- `agent_launch_utils.get_tmux_sessions()` feeds `AgentCommandScreen`'s session
  picker, `agentcrew_runner` and `syncer_app`. Change its format to
  `#{session_name}\t#{@aitask_control_helper}` and drop a row only when the name is
  `_ait_control` **and** the marker is ours. A foreign `_ait_control` stays listed.
- Discovery (`_parse_session_list` → sync, async and checked) gets **no name filter**.
  The owned helper is unattributable by the canonical rule: no stamp, pane cwd `/`
  gives a pane vote of None, and there is no legacy registry entry. So it is already
  excluded, while a foreign session of that name holding project panes is still
  attributed normally, which is correct. The live test pins both cases.
- `tmux_exec.TmuxClient._server_running` stays unfiltered on purpose: a server
  holding only the helper is still a running server.
- Shell: `tmux_bootstrap.sh` only reads one named session's stamp, so no change.

### Post-phase (risk mitigations)
1. [guard_control_routed_explicit_targets] Add `tests/test_control_routed_explicit_targets.py`.
   It is the planning audit made permanent: it scans `.aitask-scripts/**/*.py` for
   `tmux_run(` / `tmux_run_async(` / `_tmux_async(` calls and fails on any argv
   without `"-t"`, other than a short allowlist of genuinely target-free verbs. Each
   allowlist entry carries a reason. It also checks that no `-t` value is a bare
   window name. Include a planted-probe control: the scanner flags a synthetic
   `tmux_run(["display-message", "-p", "#S"])` snippet.

### 5. Docs
- `aidocs/framework/tmux_gateway.md` "Exec strategy": the control client lives in the
  reserved `_ait_control` helper session (why: client colours), and commands through
  it must always carry explicit targets.
- One line in `aidocs/framework/tui_conventions.md` ("Single tmux session per
  project"): the helper session exists and is reserved.

## Tests
- `tests/test_tmux_exec.py` (attach-argv cases, ~line 557): update the pinned argv to
  the new shape, socket flag threading included.
- Unit: the name filter in `get_tmux_sessions` / `_parse_session_list`. The reserved
  name is refused by all three validators, including `ait ide --session _ait_control`
  through the bash twin. `_read_attached_session` and `_run_frozen_detached` send
  explicit `-t`.
- New live test `tests/test_control_helper_session_live.py`. It uses a private socket
  via `AITASKS_TMUX_SOCKET`, rebuilds gateway singletons as
  `tests/lib/tmux_socket_containment.py` documents, and uses the pty fake-terminal
  client and OSC probe from planning, moved into `tests/lib/`:
  1. Project session `s`, a real (fake-terminal) client attached, and a
     `TmuxControlBackend(s)` started: `list-clients` shows the control client in
     `_ait_control`, not `s`.
  2. OSC probe in a `-d` window of `s` → `#ccddee`/`#223344`, not black.
  3. **Negative control**: attach a control client with the **old** argv (`attach -t s`)
     before the real client → black. This reproduces the bug in the same fixture.
  4. Monitor commands still target the project: through the backend,
     `display-message -p -t =s: '#S'` → `s`, `_read_attached_session` → `s`, and the
     `run-shell -b` job writes `pwd` = `s`'s cwd.
  5. The owned helper is absent from `get_tmux_sessions()`,
     `discover_aitasks_sessions()` and `discover_aitasks_sessions_async()`. It carries
     the marker and `destroy-unattached on`.
  6. Stop the backend → `_ait_control` is gone (no server keep-alive).
  7. **Collision (foreign helper-named session preserved).** Before any backend
     starts, create a raw `_ait_control` session with its own pane (`sleep 600`) and
     a second window. Set `@user_opt keep` and an explicit `destroy-unattached off`.
     Start a backend for `s`, and assert:
     - the backend is alive, in `legacy:foreign-helper` mode, with its client in `s`;
     - the foreign session is unchanged: same window/pane ids and pids,
       `@user_opt keep`, `destroy-unattached off`, no `@aitask_control_helper`;
     - it is still listed by `get_tmux_sessions()`.
     Stop the backend and assert the foreign session and panes are still alive and
     unchanged. A second variant marks the foreign session with a **different**
     marker value and gets the same outcome.
  8. **Project deletion, shared helper.** Projects `p1` and `p2`, backends B1 and B2
     (`_RECONNECT_BACKOFFS` patched short), both clients in the one owned helper.
     `kill-session p1` only, never touching the control processes:
     - B1 closes its own client and reaches FALLBACK;
     - the helper still exists with exactly one client;
     - B2 stays CONNECTED, and `B2.request_sync(["display-message", "-p", "-t", "=p2:", "#S"])`
       returns `p2` through the control channel;
     - a probe in `p2` still gets the real colours.
     Then stop B2 → helper gone.
  8b. **Real timeout path, project still present** (no mocks of `request`): backend B
     for `p2` connected, with a short check timeout. `SIGSTOP` the private tmux server
     (its pid from `display-message -p '#{pid}'`). Call B's project check directly →
     it returns after the timeout with `last_project_check == "transport"`, the client
     is marked dead through `request()`'s own teardown, and B is not FALLBACK.
     `SIGCONT` the server. The supervisor reconnects (pre-check passes) → CONNECTED
     within the patched backoff, and `request_sync(display-message -p -t =p2: '#S')`
     → `p2`. `p2` was never treated as gone, and the helper is still owned and marked.
  9. **Create/join race.** Start two backends concurrently against an absent helper:
     both end CONNECTED in one helper (one creates, the other's `new-session` fails and
     it joins on retry), with no duplicate-name session and no legacy fallback.
- `tests/test_tmux_control_resilience.sh` case B (kill-session → FALLBACK) must now
  pass through §2b's detection, unchanged as a test. If it was relying on attach
  failure alone, keep it as the regression proof of §2b.
- Re-run: `tests/test_tmux_control.sh`, `tests/test_tmux_control_resilience.sh`,
  `tests/test_tmux_exec.py`, `tests/test_no_raw_tmux.sh`,
  `tests/test_list_panes_session_scope_live.sh`, `tests/test_restore_flows_live.sh`,
  then `bash tests/run_all_python_tests.sh` (read the last line). Run
  `shellcheck` on the touched `.sh`.

## Real Codex verification (user-requested; a scratchpad script, not a repo test)
It needs Codex auth and network and costs a turn, so it runs once during
implementation. The results go into the plan's Final Implementation Notes. Private
socket, a temp git dir, Codex launched through the real `launch_in_tmux`, a short
prompt ("reply with: ok"), and `capture-pane -e -p` polled every ~100 ms during the
turn to extract the shimmer's `38;2;R;G;B` values:
- **A, attached:** fake-terminal client attached to `s`, monitor backend running
  (helper session), launch Codex, run a turn → expect non-black shimmer RGB between
  the fake fg and bg.
- **B, unattended then attached:** no real client at launch (backend running), so
  Codex's startup query gets no reply. Attach the fake client, then run a turn → record
  whether the shimmer is legible, i.e. whether Codex re-queries or falls back sanely.
- **C, control:** old attach argv in `s` before the real client → black shimmer, which
  confirms the harness reproduces the bug.

**Decision rule (option 4):** if B shows an unreadable shimmer (all `0;0;0`, or no
contrast), create a follow-up task to reconsider a Codex-specific pane style for the
"no real client viewing the session" case, carrying these measurements. If B is
legible, create none.

## Step 9
Commit the code with `bug: … (t2051)`, commit the plan via the task-commit helper,
then archive per task-workflow Step 9.

## Risk

### Code-health risk: medium
- The control backend is the monitor/minimonitor hot path. Changing its attach shape
  and session could break the ack/flag parsing or the reconnect/FALLBACK contract ·
  severity: medium · → mitigation: none (covered by live test items 1/6/8/9 plus the
  existing control and resilience suites)
- Joining or destroying a user's own `_ait_control` session would lose user work ·
  severity: low (designed out: only marker-carrying sessions are joined, filtered or
  given `destroy-unattached`; a foreign one gets the legacy attach) · → mitigation:
  none (live test item 7 pins preservation of panes and options)
- `start()` gains a multi-step create/join protocol with retries. A helper race could
  degrade to FALLBACK · severity: low · → mitigation: none (bounded passes, live test item 9)
- A command through the control client that relies on an implicit target would
  silently start acting on the helper session. Two such calls were found and fixed;
  future ones would regress silently · severity: low (residual — addressed by inline
  post-phase guard_control_routed_explicit_targets) · → mitigation: inline post-phase guard_control_routed_explicit_targets
- The helper session is visible in raw tmux surfaces (`tmux ls`, `choose-tree`), which
  can't be hidden · severity: low · → mitigation: none (documented; destroyed with the
  last control client)

### Goal-achievement risk: medium
- With no real client attached to the session when Codex starts (unattended or
  launched into an unviewed session), tmux sends no reply rather than black. How Codex
  handles that, and whether it re-queries after a client attaches, is unknown ·
  severity: medium · → mitigation: none (real-Codex scenario B measures it; the
  option-4 decision rule creates the follow-up if needed)

### Planned mitigations
- timing: post-phase | name: guard_control_routed_explicit_targets | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: implicit-target control-routed commands silently retargeting the helper session | desc: source scan failing any control-routed tmux call without an explicit -t, with a planted-probe control
