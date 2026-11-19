---
Task: t2051_codex_pane_tmux_default_colors.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/fable5_2 @ 2026-11-20 01:35
---

# t2051: stop the monitor's control clients from blacking out every pane's default colours

> Re-verified 2026-11-19 against `main` @ c443f811e. This replaces the unapproved
> draft of 2026-10-18. What changed in this round is listed under "Re-verification
> findings". Nothing below has been implemented.

## Context

Codex and OpenCode build part of their UI from the terminal's default fg/bg, which
they learn through OSC 10/11. Inside the ait tmux server, tmux answers. tmux takes a
pane's default colours from the **first client attached to the pane's session**
(`window.c`, `window_pane_get_fg` / `_get_bg`), and it does not skip control-mode
clients, which report colour 0. Monitor and minimonitor attach a control client
(`tmux -C attach -t =<session> -f no-output,ignore-size`) to the project session, and
`ait ide` always attaches it before the real terminal. So every pane in the session
gets black/black: Codex's "Working" shimmer is black on dark, and OpenCode's
`system` theme draws black text. The full measurement tables are in the task file.

**Fix (user-chosen, transport layer, no UI, no agent- or terminal-specific logic):**
the control clients attach to a dedicated helper session, `_ait_control`, instead of
the project session. tmux then answers from the real terminal client. The change
lives in the shared control-client code (`monitor/monitor_core.py`), so every TUI
that opens one gets it, including the shared status server.

Mechanism, measured on tmux 3.8 (2026-10-18 and again 2026-11-18):
- Two control clients joined one `_ait_control` helper. A pane in the project session
  then answered with the real colours, also in the `ait ide` order (control first).
- The helper and its `sleep` are destroyed when the last control client leaves
  (`destroy-unattached on`), so it never keeps a server alive.
- `set-option -t =_ait_control` (no colon) fails. It needs the session-scope `=…:` form.
- A sessionless control client (`tmux -C start-server`) exits after its command, so
  that is not an option.

## Re-verification findings (2026-11-19)

1. **Line numbers moved, the audit result did not.** An AST scan of all 74
   control-routed calls (`tmux_run`, `tmux_run_async`, `_tmux_async`,
   `run_via_control`, `run_async_via_control`, `request_sync`, `request_async`)
   finds the same two implicit-target calls and no others:
   `monitor_app.py:1901` (`_read_attached_session`, `display-message -p '#S'`) and
   `monitor_shared.py:1367` (`_run_frozen_detached`, `run-shell -b`). The remaining
   target-free calls are `list-panes -a` and `delete-buffer -b`, which need no target.
   `switch-client` is only ever sent through the subprocess gateway, never through
   the control client.
2. **t2245 landed and it interacts.** `TmuxControlClient` now anchors the id of the
   session it attached to (first `%session-changed`) and ends itself, with
   `saw_exit = True`, when tmux moves it to another session. In the helper the
   anchor is the helper's id, which is correct and needs no change: if someone kills
   the helper, the client ends (through `%exit` or the switch) and the supervisor's
   reconnect recreates it.
3. **A consumer of `saw_exit` exists that the draft did not know: the shared status
   server** (`monitor/status_server.py::_watchdog` → `_handle_exit_seen`, t2037). It
   relies on `saw_exit` to notice that the served session was destroyed and to
   re-pick a live one. Once the client lives in the helper, destroying the project
   session produces neither `%exit` nor `%session-changed`. So the new
   project-deletion detection (§3) **must set `saw_exit = True`**, or the status
   server keeps serving a dead session.
4. **Existing tests ask the control client "which session are you in?" with no
   target** (`WHO = ["display-message", "-p", "#{session_name}"]` in
   `tests/test_tmux_control_resilience.sh`, and the t2245 cases in
   `tests/test_monitor_status_server_live.py`). After the move they would answer
   `_ait_control`. The draft's "unchanged as a test" claim for resilience case B is
   wrong. These tests are rewritten (see Tests).
5. **The `detach-on-destroy off` gap** (task file, measured): destroying the project
   session moves the real terminal into `_ait_control`, and the helper then never
   goes away. New §4 handles it with a bounce hook on the helper.
6. **OpenCode** is added to verification and acceptance.
7. Validators, `get_tmux_sessions()`, the docs anchors and the test files named in
   the draft all still exist. `tests/test_tmux_exec.py` attach-argv cases are now at
   lines 773–805.
8. **A timed-out client is not closed** (review round, confirmed in the code).
   `request()` on timeout only calls `_teardown_pending()`: it marks the client dead
   and drains the pending futures, and the `tmux -C` process keeps running and stays
   attached. `_supervisor_loop` then assigns `self._client = new_client` without
   closing the old one (the `_detach_switched_client` docstring says so), and
   `stop()` closes only the current client. Today the leaked client sits in the
   project session. In the helper it would pin the helper forever, because
   `destroy-unattached` never fires. The draft's "that teardown is kept" wording
   was wrong about what the teardown does. Fixed in §3b.
9. **Names are not identities** (review round). Two places in the draft acted on a
   name after checking it: the helper join (inspect the marker, then attach and set
   the hook by name) and the project check (`has-session` by name). A same-name
   replacement between the two steps is accepted as the original. Both now use the
   tmux session id (`$N`, never reused within a server). See §2 and §3.
10. **`display-message -t` cannot prove absence** (review round, measured on 3.8).
    Over the helper's control connection, `display-message -p -t =<deleted>:
    '#{session_id}'` returned `rc 0` with an empty body, because that verb tolerates
    a target it cannot find. An earlier revision of §3 waited for `rc 1`, so an
    ordinary deletion would never have been noticed. Both the start listing and the
    check now use `list-sessions`.
11. **A start that is cancelled has no owner for its process** (review round,
    measured). `stop()` cancels the reconnect and closes only `self._client`. A
    candidate that had attached but was not yet assigned stayed attached and kept
    the helper alive. The multi-step `start()` of §2 widens that window. Fixed in
    §2 ("Cancellation and caller timeouts") and §3b.
12. **The post-attach check must know the mode** (review round). In
    `legacy:foreign-helper` mode the client is in the project session, so a check
    that demands the helper's name and marker would abandon a valid connection.
13. **A hook that runs a checkout's script can outlive the checkout** (review round,
    measured). See §4: the bounce hook names no file.
15. **An inline shell job in hook text needs two escaping layers and acts late**
    (review round, measured on 3.8). tmux's parser expands `$` in the hook text
    ("invalid environment variable"), and `run-shell` expands `#{…}` before the
    shell sees it, so the unescaped job detached the terminal although `p2`
    existed. A paused job also moved a terminal that had already gone to `p3` back
    to `p2`. The user chose a hook made of tmux commands only (§4), which has
    neither problem.
16. **A hook runs after the rest of its command list** (review round, measured on
    3.8). An unguarded native hook acted on a terminal that had already left the
    helper. See §4: the hook is guarded on the client still being in `_ait_control`.
14. **A formatted user option is inherited** (review round, measured on 3.8). A
    user-created `_ait_control` read back the expected marker text from a global
    option through `#{@aitask_control_helper}`, while `show-options -qv` on the
    session returned empty. See §2: ownership reads are session-local.

## Implementation

### Pre-phase (risk mitigations)

1. [spike_bounce_and_notifications] Before writing code, measure on a private server
   (`-L t2051s`, `-f /dev/null`, `TMUX` / `TMUX_PANE` dropped), reusing the appendix
   harness (`FakeTerm`, `Ctl`). Record every result in the plan's Final
   Implementation Notes, with the exact argv used. Implementation then copies that
   argv, not a paraphrase of it.
   - a. A session-scoped `client-session-changed` hook set on the helper fires when
     tmux moves a real client into the helper because its session was destroyed
     (`detach-on-destroy off`). `#{hook_client}` names that client and
     `#{hook_session}` is the helper's id.
   - b. The same hook also fires when a control client joins the helper, and
     `if-shell -F '#{client_control_mode}'` in the hook tells the two apart before
     any job is started.
   - c. Whether a direct `tmux attach -t =_ait_control` fires `client-session-changed`
     or only `client-attached`. If only the latter, the hook is set on both.
   - d. The **exact create command list of §2**, hook included, passed as argv the
     way `start()` will pass it, installs without error. Then the destination of the
     real terminal is observed, not inferred: with a second session present it ends
     in the next session by name, and with the helper as the only session it is
     detached. `switch-client -n` and `detach-client` with no target act on the
     client that fired the hook, and `#{server_sessions}` counts the helper.
     The guard's formats (`#{client_control_mode}`, `#{client_session}`) describe
     the hook's client at run time: a control client's join does nothing, and the
     two-switch command list of finding 16 leaves the terminal where it ended.
     Controls from the review rounds, recorded as measured: the inline shell version
     fails to install unescaped ("invalid environment variable"), and with only the
     `$` escaped it detaches although another session exists.
   - d2. `show-options -qv -t '$N:' @aitask_control_helper` and, through a client,
     `show-options -qv @aitask_control_helper` return only a **session-local**
     value: empty for a session that merely inherits the text from
     `set-option -g`. Control: `#{@aitask_control_helper}` in a `list-sessions`
     format returns the inherited text for that same session.
   - e. A `no-output` control client in the helper receives `%sessions-changed` when
     another session is destroyed, and `%session-renamed` when one is renamed.
   - f. The create command list (§2) leaves no window where the helper exists
     without its marker: `list-sessions` from a second client during creation never
     shows an unmarked `_ait_control`.
   - g. The exact target form that addresses a session **by id**:
     `attach-session -t '$N'`. Also that, inside the create list, `set-option` and
     `set-hook` with **no** `-t` act on the session the client just created, and
     that the hook is then session-local (a `-g` hook of the same name is
     untouched).
   - h. Reproduce the review findings as pre-fix controls: an unmarked same-name
     session swapped in between inspect and a by-name join is joined and hooked; a
     project killed and recreated under the same name in one command list still
     answers `has-session`; `display-message -p -t =<deleted>: '#{session_id}'`
     over the helper's control connection answers `rc 0` with an empty body.
   - i. `list-sessions -F '#{session_id}\t#{session_name}'` over the helper's control
     connection always includes the helper's own row, and omits a deleted project.
   **Decision rule.** If (d2) fails, stop and ask: ownership cannot be read safely.
   If (a) or (d) fails, the bounce falls back to the session-option
   candidate: `detach-on-destroy no-detached` set on the helper's sibling project
   sessions is **not** acceptable without asking (it changes the user's own option),
   so in that case stop and ask the user before continuing. If (e) fails, §3 uses a
   periodic check from the supervisor loop (every 5 s) instead of the notification.

### 1. Helper-session constants and name reservation

`.aitask-scripts/lib/tmux_exec.py`, mirrored in `lib/tmux_exec.sh`:
- `AIT_CONTROL_SESSION = "_ait_control"`,
  `AIT_CONTROL_MARKER_OPTION = "@aitask_control_helper"`,
  `AIT_CONTROL_MARKER = "aitasks-control-v1"`.
- Add `@aitask_control_helper` to the `@aitask_*` option inventory in
  `aidocs/framework/tmux_gateway.md` (it is a session option, the others are pane
  options; say so).

Reserve the name at every session-name writer, failing closed before anything is
created. Reservation is secondary: it only stops the framework from creating a
project session with that name. Safety against a pre-existing session comes from the
marker (§2).
- `lib/tmux_bootstrap.sh::_tmux_bootstrap_session_name_ok`: return 1 for
  `_ait_control`. `aitask_ide.sh:21` reports "reserved" for that case instead of
  "invalid chars".
- `lib/agent_launch_utils.py::_tmux_session_name_ok` and
  `lib/agent_restore.py::session_name_ok`: same rule.

### 2. The control client attaches to an owned helper

`.aitask-scripts/monitor/monitor_core.py`, `TmuxControlClient`.

**Ownership marker.** The framework writes `@aitask_control_helper =
aitasks-control-v1` in the same command list that creates the helper. Only a session
carrying that marker is joined, filtered or relied on for `destroy-unattached`.
Nothing is ever written to a session without it.

**The marker must be the session's own value (finding 14).** A format such as
`#{@aitask_control_helper}` follows tmux's option inheritance, so a session that sets
nothing reads back a global user option of the same name. Every ownership read
therefore uses `show-options -qv` on the session itself, which returns only the
session-local value: `-t 'H:'` from outside, no target through a client that is in
the session. One shared helper in `lib/tmux_exec.py`,
`control_helper_owned(run, session_id) -> bool | None` (`None` = could not ask, and
the caller treats that as **foreign**), is used by `start()`, by the post-attach
check and by `get_tmux_sessions()` (§6), so the three cannot drift.

**`start()` protocol**, at most 3 passes:
1. One listing through the gateway (`TmuxClient.run_async`, same socket args):
   `list-sessions -F '#{session_id}\t#{session_name}'`, parsed by exact name in
   Python. It answers two questions:
   - the project: no row named `<project>` → return False (today's contract). Its id
     is stored as `self._project_id` (§3 compares against it). **Never
     `display-message -t`** for this: that verb tolerates a missing target and
     answers `rc 0` with an empty body (measured on 3.8, see finding 10).
   - the helper: the row named `_ait_control`, if any, and its id `H`. When there is
     one, `control_helper_owned(…, H)` reads its session-local marker.
2. Branch on the helper row:
   - **absent → create:**
     `has-session -t =<p> ; new-session -s _ait_control -c / -f no-output,ignore-size 'exec sleep 2147483647' ; set-option @aitask_control_helper aitasks-control-v1 ; set-option destroy-unattached on ; set-hook client-session-changed <§4 hook text>`.
     The option and hook commands carry **no `-t`**: they act on the session this
     client just created, whatever happens to the name meanwhile, and they write
     session-local values. No `-A`: if another backend created it in between,
     `new-session` fails, the client exits, and the next pass joins.
   - **session-local marker is ours → join, by id:**
     `has-session -t =<p> ; attach-session -t 'H' -f no-output,ignore-size`.
     The attach names the **inspected id `H`**, never the name. If that session is
     gone (its last client left, or it was replaced by a same-name session), the
     attach fails, the client exits, and the next pass inspects again. **A join
     writes nothing to the helper**: the hook was installed by the creator and
     depends on no file (§4), so there is nothing to refresh.
   - **present, and the session-local marker is another value, empty, inherited
     only, or unreadable → foreign:** never join, filter or modify it, and leave its
     hooks alone. Use the **legacy** argv (`attach -t =<p> …`, today's behaviour,
     with today's colours) and record `self.helper_mode = "legacy:foreign-helper"`.
3. **Verify after attach, through the new client itself:**
   `display-message -p '#{session_id}\t#{session_name}'` and, in the helper modes,
   `show-options -qv @aitask_control_helper` (no target on purpose: both ask about
   the session this client is in, and the second returns only its own value). What
   counts as success depends on the mode the pass chose:
   - **create:** the name is `_ait_control` and the marker is ours.
   - **join:** the same, and the id equals `H`.
   - **legacy:** the id equals `self._project_id`. The client is in the project
     session on purpose, so there is no helper name or marker to find.
   Any other answer abandons the pass. These are the only target-free calls the
   post-phase guard allowlists, with this reason.
4. A pass that fails after the listing found the project is a helper race: retry
   from step 1. After 3 passes return False. **Every abandoned pass closes its
   process** (`close()`), so a failed pass never leaves a client attached.

**Cancellation and caller timeouts (finding 11).** `start()` now awaits several
times between spawning the process and returning, and both of its callers can give
up in that window: `stop()` cancels the supervisor task mid-reconnect, and
`TmuxControlBackend.start()` stops waiting after `_BACKEND_START_TIMEOUT`. Until
`start()` returns True nobody else holds the process, so two rules apply:
- `start()` owns what it spawned. On `CancelledError` (or any other exception)
  after the spawn, it ends the process **synchronously** (close stdin, `kill()`,
  cancel the reader task) and re-raises. No `await` in that handler: a task that is
  being cancelled cannot rely on one.
- The backend keeps the candidate in `self._starting` from before `start()` is
  scheduled until ownership moves to `self._client`. `stop()` closes `_starting` as
  well as `_client`. `TmuxControlBackend.start()` cancels the scheduled coroutine
  when its wait times out, before calling `stop()`.

Details that must hold:
- `_attach_argv()` stays callable with no arguments (tests and the pre-fix controls
  override it class-wide). It returns the argv for the mode the current pass chose.
  The socket flag and `TMUX_CLIENT_FLAGS` stay where they are.
- `new-session` here is the control client's own spawn in `monitor_core.py`, not a
  gateway-routed verb, so the "pane-creating verbs never ride the control client"
  rule (*Pane PATH*) is not involved. The helper pane runs `exec sleep` and depends
  on no PATH entry beyond the server's own.
- The startup commands' replies are flag-0 server blocks, which the reader already
  drops. The first `%session-changed` anchors the **helper's** id (t2245 code,
  unchanged).

### 3. Notice project deletion while connected

`TmuxControlClient` reader, same file. The client no longer dies with its project.

- The project is identified by its **session id**, not its name. `self._project_id`
  is recorded by the `start()` listing (§2 step 1).
- On `%sessions-changed` or `%session-renamed`, the reader schedules
  (`loop.create_task`, never awaited inside the reader) a check that sends
  `list-sessions -F '#{session_id}\t#{session_name}'` through this same client, with
  its own timeout `_PROJECT_CHECK_TIMEOUT = 2.0`, and looks the project up by exact
  name in the reply. A listing reports absence unambiguously, which
  `display-message -t` does not (finding 10). The same check runs once right after a
  successful attach, which closes the gap between the listing and the attach.
- A listing only counts as evidence when it is **whole**: it must contain the row of
  the session this client is attached to (the anchored id). A reply without that
  row is unreadable, not "project gone".
- One check in flight at most. A notification that arrives during a check sets a
  "again" flag, and the check re-runs once it finishes, so a deletion that lands
  mid-check is never lost.
- Outcomes, recorded as `self.last_project_check`:
  - whole listing, the project's row carries `self._project_id` → `present`:
    nothing happens.
  - whole listing, the project's row carries **another id** → `replaced`: the
    session was destroyed and a new one took its name. Handled exactly like `gone`.
    The supervisor's reconnect then succeeds against the new session and records the
    new id, and the status server runs its refresh path, which is what the original
    session's exit would have triggered before this change.
  - whole listing with **no row** for the project → `gone`: **set
    `saw_exit = True`**, then `close()`. The supervisor's reconnect finds no project
    and the backend reaches FALLBACK. The status server's `_handle_exit_seen`
    re-picks a live session exactly as it does today after `%exit`.
  - `rc -1` → `transport`: the check sets nothing. `request()` has marked the client
    dead, the supervisor closes that process and reconnects (§3b), and the pre-check
    passes because the project still exists. A transport failure is never read as
    "project gone", and `saw_exit` stays unset.
  - `rc 1`, or a listing that is not whole → `unknown`: nothing happens. Unknown is
    never read as gone.
- A renamed project session reads as `gone` (the name no longer resolves). That
  matches what already happens to every explicit `=<name>:` target after a rename.

### 3b. Close a dead client's process before replacing it

`TmuxControlBackend._supervisor_loop` and `stop()`, same file (finding 8).

- When the supervisor finds the current client dead, it `await`s `old.close()`
  **before** the first reconnect attempt. `close()` already does the right thing for
  a hung process: close stdin, wait `_DEFAULT_CLOSE_TIMEOUT` (2 s), then kill. It is
  idempotent, so the `%exit` and `gone` routes, where the process has already ended
  or been closed, pay nothing.
- A reconnect attempt whose `start()` returns False leaves no process behind (§2
  step 4), and one that is cancelled or times out ends its own process (§2,
  "Cancellation and caller timeouts").
- The supervisor sets `self._starting = new_client` before `await
  new_client.start()` and clears it when it assigns `self._client`.
- `stop()` cancels the supervisor, then closes `self._starting` and
  `self._client`. Live cases 10 and 10b assert that nothing is left attached.
- Cost: a reconnect after a timeout starts up to 2 s later than today.

### 4. Bounce a real client that lands in the helper

**The hook is tmux commands only: no shell, no job, no file (findings 13 and 15,
user decision 2026-11-19).** The helper is shared by every project on the server and
can outlive the checkout whose backend created it, so the hook may name no file of
any checkout. There is **no** `aitask_control_bounce.sh` and no `run-shell`. The hook
text is one constant, `AIT_CONTROL_BOUNCE_HOOK` in `lib/tmux_exec.py`, installed
once by the creator (§2).

Shape (the exact text is fixed by pre-phase item d, then copied verbatim):

```
if-shell -F '#{&&:#{==:#{client_control_mode},0},#{==:#{client_session},_ait_control}}' {
  if-shell -F '#{==:#{server_sessions},1}' { detach-client } { switch-client -n }
}
```

- **The guard is evaluated when the hook runs, and both conditions are required
  (finding 16).** tmux queues a hook behind whatever is left of the command list
  that triggered it. Measured on 3.8: a list that switched a terminal into
  `_ait_control` and straight on to `p3` ran the unguarded hook while the terminal
  was already in `p3`, and moved it to `s`. With the guard (not a control client,
  **and** still in `_ait_control`) the terminal stayed in `p3`, and ordinary entry,
  project destruction and detach-when-alone still worked. Neither action runs
  outside the guard.

- **Where the terminal lands:** the next session in name order (`switch-client -n`).
  This is the user's choice over "most recently active", which needs a shell job.
  When the helper is the only session, the terminal is detached, which is what
  `detach-on-destroy off` does natively when no session is left.
- Control clients are filtered by the guard, so the monitor's own joins do nothing.
- Both commands carry no `-c` / `-t`: they act on the client that fired the hook.
  The guard, the inner test and the action run back to back inside the server, with
  no job in between, so the session the guard saw is the session the action leaves.
- The text contains no `$`, no nested format inside a job string and no quoting
  beyond tmux's own, which removes the two escaping layers the shell version needed.
- `tests/test_no_raw_tmux.sh` is not involved: the constant spawns nothing.

This handles both ways of landing there: tmux moving the terminal after the project
session was destroyed, and a user choosing the helper in `prefix s`. No project
session option is changed, so the user's `detach-on-destroy` setting keeps its
meaning. The hook is session-local, so a user's global `client-session-changed`
hook is not modified. The helper still shows in tmux's own session lists; that
cannot be filtered and is documented.

Out of scope (noted on t2211): bouncing onto another project's sitrep window.

### 5. Explicit targets for the two implicit-target calls

- `monitor_app.py::_read_attached_session` (line 1901):
  `display-message -p -t <own pane> '#S'`, with `<own pane>` = `$TMUX_PANE` when set,
  else `tmux_session_scope_target(self._monitor.session)`.
- `monitor_shared.py::_run_frozen_detached` (line 1367):
  `run-shell -b -t <scope target of the monitor's session>`, so the job keeps the
  project session's cwd instead of the helper's `/`.

### 6. Keep the owned helper off framework session lists

- `agent_launch_utils.get_tmux_sessions()`: format
  `#{session_id}\t#{session_name}`. When a row is named `_ait_control`, ask
  `control_helper_owned(…, <its id>)` and drop the row only on `True`. A foreign
  `_ait_control`, including one that merely inherits the marker text, stays listed,
  and so does one whose marker could not be read. The extra call is made only when
  such a row exists.
- Discovery (`_parse_session_list` and its sync/async/checked callers) gets no name
  filter: the owned helper has no stamp, its pane cwd is `/` and it has no registry
  entry, so it is already unattributable. The live test pins that, and also that the
  monitor's pane inventory holds no pane of the helper.
- `TmuxClient._server_running` stays unfiltered: a server holding only the helper is
  still running.

### 7. Docs

- `aidocs/framework/tmux_gateway.md`, "Exec strategy": the control client lives in
  the reserved `_ait_control` helper session (why: client colours), commands through
  it must always carry an explicit target, and `saw_exit` now also means "the project
  session is gone".
- `aidocs/framework/tui_conventions.md`, "Single tmux session per project": the
  helper exists, is reserved, and bounces real clients to the next session by name.
- Website: one short paragraph on the monitor page that describes tmux sessions,
  stating that `_ait_control` appears in tmux's session list, what it is for, and
  that agents started before the fix (or with no terminal attached) keep the colours
  they read at startup until restarted, unless the real-agent check below shows they
  re-query. Run `python3 check_links.py --build` in `website/`.

### Post-phase (risk mitigations)

1. [guard_control_routed_explicit_targets] Add
   `tests/test_control_routed_explicit_targets.py`: the planning audit made
   permanent. It walks the AST of `.aitask-scripts/**/*.py` for calls to the seven
   control-routed names listed in finding 1 and fails on any list-literal argv with
   no `"-t"`, other than an allowlist of target-free verbs (`list-panes -a`,
   `delete-buffer -b`, `list-sessions`, and the one post-attach self-verification
   call of §2 step 3), each entry with a reason. Non-literal argv
   sites are pinned by an explicit per-site list, so a new one fails until reviewed.
   Planted-probe control: the scanner flags a synthetic
   `tmux_run(["display-message", "-p", "#S"])`.

## Tests

Existing tests that change:
- `tests/test_tmux_exec.py:773-805`: pinned argv updated to the create / join /
  legacy shapes, socket flag threading included.
- `tests/test_tmux_control_resilience.sh` (cases B, B2, B3),
  `tests/test_monitor_status_server_live.py:477-516`,
  `tests/test_tmux_control.sh:655`, `tests/test_monitor_producer_seams.py`: the
  untargeted `WHO` query becomes `display-message -p -t =<session>: '#{session_name}'`,
  and "the client died" is now reached through §3. For each, write a table that
  classifies every assertion (still discriminates / now vacuous / needs a new
  control) before editing, and keep each pre-fix control as the exact old code
  injected at the real seam. B2's decoy (`<session>_mob`) must still prove that the
  exact-match pre-check refuses a prefix match.
- Unit: the three validators refuse `_ait_control`, including
  `ait ide --session _ait_control` through the bash twin. `get_tmux_sessions`
  filters only an owned helper. `_read_attached_session` and `_run_frozen_detached`
  send an explicit `-t`.

New live test `tests/test_control_helper_session_live.py` (private socket through
`AITASKS_TMUX_SOCKET`, gateway singletons rebuilt as
`tests/lib/tmux_socket_containment.py` documents, the fake terminal and OSC probe
moved from the appendix into `tests/lib/`). The skip gate checks only for `tmux` and
a usable pty, never by running the code under test.
1. Project `s`, fake terminal attached, `TmuxControlBackend(s)` started:
   `list-clients` shows the control client in `_ait_control`, not `s`.
2. OSC probe in a `-d` window of `s` → `#ccddee` / `#223344`. Repeated in the
   `ait ide` order (backend first, fake terminal second).
3. **Negative control:** the old argv (`attach -t =s`) attached before the fake
   terminal → black for both.
4. Commands still act on the project: `display-message -p -t =s: '#S'` → `s`,
   `_read_attached_session` → `s`, and the `run-shell -b` job writes `pwd` = `s`'s cwd.
5. The owned helper is absent from `get_tmux_sessions()`, both discovery functions
   and the monitor's pane inventory. It carries a **session-local** marker,
   `destroy-unattached on` and the bounce hook. `show-hooks` on it contains no
   absolute path and no path of this checkout.
6. Stop the backend → `_ait_control` is gone.
7. **Foreign helper preserved.** A raw `_ait_control` session with its own panes,
   `@user_opt keep` and `destroy-unattached off`, created before any backend: the
   backend runs in `legacy:foreign-helper` mode with its client in `s`, **reaches
   CONNECTED, and serves a request** (`display-message -p -t =s: '#S'` → `s`): the
   post-attach check accepts the project id in this mode. The foreign
   session keeps its window/pane ids, pids, options and hooks, has no marker, and is
   still listed. A second variant carries a different marker value.
   **Inherited-only marker:** `set-option -g @aitask_control_helper
   aitasks-control-v1`, then a user-created `_ait_control` that sets nothing itself
   and has its own `client-session-changed` hook. The backend takes the legacy
   path, the session stays listed by `get_tmux_sessions()`, and its hooks and
   options are byte-identical before and after (`show-hooks`, `show-options`).
   Pre-fix control: the format-based read reports that session as owned.
   **Replacement between inspect and join:** an owned helper exists (held by a
   first backend). A second client's inspect step is wrapped so that, after it
   returns the owned id, the test kills the helper and creates an unmarked
   `_ait_control` with `@user_opt keep` before the join runs. Assert: the join by
   id fails, the replacement is never attached to by that client, carries no
   marker and no bounce hook, and the retry lands in `legacy:foreign-helper`.
   Pre-fix control: the same swap with a by-name join attaches to the replacement
   and installs the hook there.
8. **Project deletion, shared helper.** `p1` and `p2`, backends B1 and B2 (short
   `_RECONNECT_BACKOFFS`). `kill-session p1`: B1's check reports `gone`, B1 reports
   `exit_seen`, closes its client and reaches FALLBACK. Pre-fix control: the
   `display-message -t` probe reads the same deletion as present (`rc 0`, empty
   body) and `exit_seen` stays unset. The helper keeps exactly one client. B2 stays
   CONNECTED and answers for `p2`. A probe in `p2` still gets the real colours.
   Stop B2 → helper gone.
9. **Deletion during a check.** Two sessions destroyed back to back: the second
   deletion is still detected (the "again" flag).
9b. **Kill and recreate under the same name, in one command list**
    (`kill-session -t =p1 ; new-session -d -s p1`): B1's check reports `replaced`,
    `exit_seen` is set, and B1 reconnects, ends CONNECTED and holds the **new**
    session id. Pre-fix control: the by-name `has-session` check reports `present`
    and `exit_seen` stays unset.
10. **Real timeout, project present.** `SIGSTOP` the private server, call the check:
    `last_project_check == "transport"`, B is not FALLBACK. `SIGCONT`: B returns to
    CONNECTED and `exit_seen` was never set by the check. Then assert the cleanup:
    `list-clients` shows **exactly one** control client for B, the old client's
    process has exited, and after `B.stop()` no control client is left and
    `_ait_control` is gone. Pre-fix control: with the supervisor's `close()` call
    removed, two clients remain after recovery and the helper survives `stop()`.
10b. **Stop during startup verification.** The post-attach verification is held
    open by a test seam (an event the test controls), in two variants: during a
    **reconnect** (kill the first client's process, wait until the candidate is
    attached and waiting) and during the **initial** `backend.start()` (short
    `_BACKEND_START_TIMEOUT`, so the caller times out). Then `stop()`. Assert: no
    control client is left in `list-clients`, the candidate's process has exited,
    and `_ait_control` is gone. Pre-fix control: without the cancellation handler
    and `_starting`, the candidate stays attached and the helper survives.
11. **Create/join race.** Two backends started together against an absent helper end
    CONNECTED in one helper, with no legacy fallback.
12. **Helper killed by hand** (`kill-session -t =_ait_control`), under both
    `detach-on-destroy` settings: the backend reconnects and the helper is back,
    marked.
13. **Bounce, `detach-on-destroy off`.** Fake terminal in `s`, a second project `p2`,
    backend running. `kill-session s`: the fake terminal ends in `p2`, the helper
    holds only control clients. Variant with `p2` and `p3`: it ends in the next
    session by name after `_ait_control`. Variant with no other session: the fake
    terminal is detached. Variant: a direct `attach -t =_ait_control` is bounced.
    **Negative control:** with the hook unset, the terminal lands and stays in the
    helper (the measured gap).
14. **Bounce, `detach-on-destroy on`.** `kill-session s` detaches the terminal and
    the helper is destroyed with its last control client.
15. **Bounce survives the checkout.** The backend runs as a subprocess from a
    throwaway copy of the framework (`tests/lib/framework_copy.sh`). After the
    helper and its hook exist, the copy is **renamed**, and in a second variant
    **deleted**, with no other backend joining. Then `kill-session s` under
    `detach-on-destroy off`: the fake terminal still ends in `p2`, and after the
    backend is stopped the helper is gone. Pre-fix control: a hook that runs a
    script inside the copy leaves the terminal in `_ait_control` and the helper
    alive.
15b. **The hook starts no job.** `show-hooks` on the helper contains neither
    `run-shell` nor `$`. A terminal that was bounced to `p2` and then moved by the
    test to `p3` stays in `p3`: nothing acts on it afterwards (the stale-job case
    measured against the shell version, which moved it back to `p2`).
    **Two switches in one command list:** `switch-client -c <term> -t
    =_ait_control ; switch-client -c <term> -t =p3` leaves the terminal in `p3`.
    Pre-fix control: the same list with the unguarded hook moves it out of `p3`.
16. Status server: destroying the served session makes it re-pick a live one, under
    both settings (the rewritten t2245 cases).

Re-run: `tests/test_tmux_control.sh`, `tests/test_tmux_control_resilience.sh`,
`tests/test_tmux_exec.py`, `tests/test_no_raw_tmux.sh`,
`tests/test_list_panes_session_scope_live.sh`, `tests/test_restore_flows_live.sh`,
`tests/test_monitor_status_server.py`, `tests/test_monitor_status_server_live.py`,
`./.aitask-scripts/aitask_skill_verify.sh` is not needed (no skill change), then
`bash tests/run_all_python_tests.sh` (read the last line; the new live test boots no
TUI, so it stays in the parallel lane). `shellcheck` on every touched `.sh`.

## Real-agent verification (scratchpad scripts, not repo tests)

Private socket with the live server's options (`allow-passthrough on`, `*:RGB`), a
temp git dir, agents launched through the real `launch_in_tmux`, colours counted
from `capture-pane -e -p`. Results go into Final Implementation Notes, and the
scripts go verbatim into the plan appendix.

| | Codex 0.170+ | OpenCode, `theme: system` |
|---|---|---|
| **A** backend first, then fake terminal (the `ait ide` order) | one short turn ("reply with: ok"), poll every ~100 ms: shimmer RGB is not `0;0;0` | start screen only: text is not `38;2;0;0;0`, panels are not `48;2;0;0;0` |
| **B** no real client at launch, attached afterwards | record what is drawn and whether it changes after attach | same |
| **C** control: old argv before the fake terminal | black shimmer / `30;30;30` backgrounds | black text and panels |
| **D** agent started under C, then backend restarted with the fix | record whether the agent re-queries | same |

Codex scenario A costs one model turn and needs auth and network. Everything else
spends no turn.

**Decision rules.** If B is unreadable for either agent, create a follow-up task for
the per-pane style on that case only, carrying these measurements. If B is readable,
create none. D decides the wording of the website note ("restart the agent" or not).

## After implementation

- Send notes with `./ait note` to **t2161** (Ready, control client quoting and nested
  dispatch) and **t2038** (Postponed, Go status server): the control client now
  attaches to `_ait_control`, the three argv shapes, and that whichever lands later
  must keep the helper attach and the explicit-target rule.
- Step 9: commit the code with `bug: … (t2051)`, commit the plan through the
  task-commit helper, then archive per task-workflow Step 9.

## Risk

### Code-health risk: medium
- The control backend is the monitor / minimonitor / status-server hot path. A new
  attach shape and session could break the ack parsing or the reconnect / FALLBACK
  contract · severity: medium · → mitigation: none (live items 1, 6, 8, 10, 11, 12
  and the existing control, resilience and status-server suites)
- `saw_exit` gains a second meaning (project gone, detected by a check) that the
  status server depends on. A missed detection leaves it serving a dead session ·
  severity: medium · → mitigation: none (live items 8, 9, 16)
- Joining or destroying a user's own `_ait_control` session would lose user work ·
  severity: low (designed out by the marker, the by-id join and the post-attach
  verification) · → mitigation: none (live item 7, including the replacement
  between inspect and join)
- A control client that timed out keeps running and would pin the helper session ·
  severity: medium · → mitigation: none (§3b closes it before the reconnect; live
  item 10 asserts one client after recovery and no helper after shutdown)
- A project session killed and recreated under the same name would pass a by-name
  check, and the status server would never refresh · severity: low (designed out by
  comparing session ids) · → mitigation: none (live item 9b)
- A start that is cancelled or times out after spawning could leave its client
  attached and pin the helper · severity: medium · → mitigation: none (`start()`
  ends what it spawned, `_starting` is closed by `stop()`; live item 10b, both
  variants)
- The deletion check depends on reading absence correctly; the first probe chosen
  could not report it · severity: low (designed out by a whole-listing lookup) · →
  mitigation: none (live items 8 and 9b assert `gone` and `replaced` separately)
- The bounce is hook text stored in the tmux server. Which events fire it and which
  client its target-free commands act on was not measured before this plan ·
  severity: low (residual — addressed by inline pre-phase
  spike_bounce_and_notifications; the hook is tmux commands only, names no file,
  starts no job and acts only while the client is still in the helper) · → mitigation: inline pre-phase spike_bounce_and_notifications
- The terminal lands on the next session by name, which may not be the one the user
  last used · severity: low (accepted by the user in exchange for a hook with no
  shell) · → mitigation: none (documented on the website page)
- A session that only inherits the marker text would be taken for the framework's
  own · severity: low (designed out by session-local reads through one shared
  helper) · → mitigation: none (live item 7, inherited-only variant)
- A future control-routed command with an implicit target would silently act on the
  helper session · severity: low (residual — addressed by inline post-phase
  guard_control_routed_explicit_targets) · → mitigation: inline post-phase guard_control_routed_explicit_targets
- Several existing tests asked the client for its session with no target. A careless
  rewrite turns them vacuous · severity: low · → mitigation: none (assertion
  classification table required before editing)
- The helper session is visible in raw tmux surfaces · severity: low · →
  mitigation: none (documented; bounced; destroyed with the last control client)

### Goal-achievement risk: medium
- With no real client attached when the agent starts, tmux sends no reply at all,
  and the helper does not change that. Agents already running keep the colours they
  read · severity: medium · → mitigation: none (real-agent scenarios B and D measure
  it; the decision rule creates the follow-up if needed)
- The bounce depends on tmux behaviour that is assumed, not measured: the session
  hook firing on a destroy-driven move · severity: low (residual — addressed by
  inline pre-phase spike_bounce_and_notifications, with a stop-and-ask rule if it
  fails) · → mitigation: inline pre-phase spike_bounce_and_notifications

### Planned mitigations
- timing: pre-phase | name: spike_bounce_and_notifications | type: spike | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: unmeasured tmux behaviour behind the bounce hook and the deletion notification | desc: private-server measurements a–f with a decision rule, results and exact argv recorded in the plan
- timing: post-phase | name: guard_control_routed_explicit_targets | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: implicit-target control-routed commands silently retargeting the helper session | desc: AST scan failing any control-routed tmux call without an explicit -t, with a planted-probe control

## Appendix: re-verification probe scripts (2026-11-18)

These are the scratch scripts behind the measurements recorded in the task file
(`aitasks/t2051_codex_pane_tmux_default_colors.md`, "Root cause" and "`ait ide`
integration"). They are copied verbatim so the measurements can be re-run. They are
not repo tests. Measured with tmux 3.8, Codex 0.170.0 and OpenCode 1.18.34.

How to run: put the four files in one scratch directory and run them from there.
They use a private tmux server (`-L t2051r`, `-f /dev/null`) and drop `TMUX` /
`TMUX_PANE` from the environment, so they never touch the live server.

- `python3 harness.py`: the client-order matrix (OSC 10/11 replies per scenario).
- `python3 agents.py opencode` / `python3 agents.py codex`: start the real agent in
  both client orders and count the truecolor values on its start screen. No turn is
  spent. It needs an `agentdir/` subdirectory to launch the agent in, and mirrors the
  live server's options (`allow-passthrough on`, `*:RGB`).
- `python3 dod.py`: where the real terminal goes when the project session is
  destroyed, for both `detach-on-destroy` settings, plus the `ait ide` attach order
  with the helper session.

Known limits: the `refresh-client -r` attempt in `harness.py` (S8) changed nothing and
may be wrongly quoted, so treat that alternative as untested. `agents.py` waits a fixed
8 s for the agent's start screen.

### `probe.py`

```python
#!/usr/bin/env python3
"""Runs INSIDE a tmux pane: ask the terminal (tmux) for default fg/bg + palette."""
import os, sys, termios, tty, select, time

out = sys.argv[1]
fd = os.open("/dev/tty", os.O_RDWR)
old = termios.tcgetattr(fd)
tty.setraw(fd)
try:
    q = b"\x1b]10;?\x1b\\" b"\x1b]11;?\x1b\\" b"\x1b]4;1;?\x1b\\" b"\x1b]4;7;?\x1b\\" b"\x1b[c"
    os.write(fd, q)
    buf = b""
    end = time.time() + 1.5
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.1)
        if r:
            buf += os.read(fd, 4096)
            if b"\x1b[?" in buf and buf.rstrip().endswith(b"c"):
                break
finally:
    termios.tcsetattr(fd, termios.TCSANOW, old)
with open(out + ".tmp", "w") as f:
    f.write(repr(buf))
os.rename(out + ".tmp", out)
```

### `harness.py`

```python
#!/usr/bin/env python3
"""t2051 re-verification harness. Private tmux server only (-L t2051r)."""
import os, pty, re, subprocess, sys, threading, time, fcntl, struct, termios, signal

HERE = os.path.dirname(os.path.abspath(__file__))
SOCK = "t2051r"
ENV = {k: v for k, v in os.environ.items() if k not in ("TMUX", "TMUX_PANE")}
ENV["TERM"] = "xterm-256color"
T = ["tmux", "-L", SOCK, "-f", "/dev/null"]
FG, BG = "cccc/dddd/eeee", "2222/3333/4444"
PALETTE = True
_P = ["1e1e2e","f38ba8","a6e3a1","f9e2af","89b4fa","f5c2e7","94e2d5","bac2de",
      "585b70","f38ba8","a6e3a1","f9e2af","89b4fa","f5c2e7","94e2d5","a6adc8"]
PAL = ["/".join(h[i:i+2]*2 for i in (0,2,4)) for h in _P]
LIVE_LIKE = False


def tm(*a, check=True):
    r = subprocess.run([*T, *a], env=ENV, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"tmux {a}: {r.stderr.strip()}")
    return r.stdout.strip()


def kill_server():
    subprocess.run([*T, "kill-server"], env=ENV, capture_output=True)
    time.sleep(0.2)


class FakeTerm:
    """A pty-backed 'real' client that answers OSC 10/11 like an outer terminal."""

    def __init__(self, session, answer=True):
        self.answer = answer
        self.seen = b""
        self.palq = 0
        pid, fd = pty.fork()
        if pid == 0:
            os.execvpe("tmux", [*T, "attach", "-t", "=" + session], ENV)
        self.pid, self.fd = pid, fd
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
        self.stop = False
        self.t = threading.Thread(target=self._loop, daemon=True)
        self.t.start()
        time.sleep(0.6)

    def _loop(self):
        tail = b""
        while not self.stop:
            try:
                d = os.read(self.fd, 65536)
            except OSError:
                return
            if not d:
                return
            self.seen += d
            tail = (tail + d)[-200000:]
            if not self.answer:
                continue
            while True:
                m = re.search(rb"\x1b\](10|11|4;\d+);\?(\x1b\\|\x07)", tail)
                if not m:
                    break
                k = m.group(1)
                if k.startswith(b"4;"):
                    self.palq += 1
                    n = int(k[2:])
                    rgb = PAL[n % 16] if PALETTE else None
                else:
                    rgb = FG if k == b"10" else BG
                if rgb:
                    os.write(self.fd, b"\x1b]" + k + b";rgb:" + rgb.encode() + b"\x1b\\")
                tail = tail[m.end():]

    def close(self):
        self.stop = True
        try:
            os.kill(self.pid, signal.SIGHUP)
        except ProcessLookupError:
            pass
        try:
            os.close(self.fd)
        except OSError:
            pass
        try:
            os.waitpid(self.pid, 0)
        except ChildProcessError:
            pass


class Ctl:
    def __init__(self, argv):
        self.p = subprocess.Popen([*T, "-C", *argv], env=ENV, stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        time.sleep(0.5)

    def send(self, line):
        self.p.stdin.write(line.encode() + b"\n")
        self.p.stdin.flush()
        time.sleep(0.3)

    def close(self):
        try:
            self.p.stdin.close()
        except Exception:
            pass
        try:
            self.p.wait(timeout=2)
        except Exception:
            self.p.kill()


def attach_ctl(session):
    return Ctl(["attach", "-t", "=" + session, "-f", "no-output,ignore-size"])


def probe(session, n=[0]):
    n[0] += 1
    out = f"{HERE}/out/p{os.getpid()}_{n[0]}"
    os.makedirs(f"{HERE}/out", exist_ok=True)
    pane = tm("new-window", "-d", "-P", "-F", "#{pane_id}", "-t", "=" + session + ":",
              f"python3 {HERE}/probe.py {out}; sleep 30")
    return wait_out(out), pane


def probe_in_pane_style(session, style):
    """probe where the pane style is set BEFORE the program queries."""
    out = f"{HERE}/out/s{os.getpid()}_{time.time_ns()}"
    pane = tm("new-window", "-d", "-P", "-F", "#{pane_id}", "-t", "=" + session + ":",
              f"sleep 1; python3 {HERE}/probe.py {out}; sleep 30")
    tm("select-pane", "-t", pane, "-P", style)
    return wait_out(out, 5), pane


def wait_out(out, t=4):
    end = time.time() + t
    while time.time() < end:
        if os.path.exists(out):
            return summarize(open(out).read())
        time.sleep(0.1)
    return "PROBE-TIMEOUT"


def summarize(rep):
    raw = eval(rep)
    res = {}
    for k, pat in (("fg", rb"\]10;(rgb:[0-9a-f/]+)"), ("bg", rb"\]11;(rgb:[0-9a-f/]+)"),
                   ("pal1", rb"\]4;1;(rgb:[0-9a-f/]+)"), ("pal7", rb"\]4;7;(rgb:[0-9a-f/]+)")):
        m = re.search(pat, raw)
        res[k] = m.group(1).decode() if m else "no-reply"
    res["da"] = b"\x1b[?" in raw
    return res


def fresh(*sessions):
    kill_server()
    for s in sessions:
        tm("new-session", "-d", "-s", s, "-x", "120", "-y", "40", "-c", "/tmp")
    tm("set", "-g", "default-terminal", "tmux-256color")
    if LIVE_LIKE:
        tm("set", "-g", "allow-passthrough", "on")
        tm("set", "-as", "terminal-overrides", ",*:RGB")
        tm("set", "-s", "extended-keys", "on")
        tm("set", "-g", "focus-events", "on")


def show(name, r):
    print(f"{name:58s} {r}", flush=True)


def main():
    print("tmux", subprocess.run(["tmux", "-V"], capture_output=True, text=True).stdout.strip())
    # S1 no clients
    fresh("s")
    show("S1 no clients", probe("s")[0])
    # S2 control only
    fresh("s"); c = attach_ctl("s")
    show("S2 control client only", probe("s")[0])
    # S10 control only + pane style
    show("S10 control only + pane style fg=#cdd6f4,bg=#1e1e2e", probe_in_pane_style("s", "fg=#cdd6f4,bg=#1e1e2e")[0])
    show("S10b control only + pane style fg only", probe_in_pane_style("s", "fg=#cdd6f4")[0])
    c.close()
    # S3 control first then real
    fresh("s"); c = attach_ctl("s"); f = FakeTerm("s")
    show("S3 control FIRST, then real client   [BUG]", probe("s")[0])
    show("S6 S3 + pane style", probe_in_pane_style("s", "fg=#cdd6f4,bg=#1e1e2e")[0])
    tm("set", "-w", "-t", "=s:", "window-style", "fg=#aabbcc,bg=#112233")
    show("S7 S3 + window-style on a window (probe in new window)", probe("s")[0])
    r, pane = None, tm("display-message", "-p", "-t", "=s:", "#{pane_id}")
    out = f"{HERE}/out/w{os.getpid()}"
    tm("respawn-pane", "-k", "-t", pane, f"python3 {HERE}/probe.py {out}; sleep 30")
    show("S7b S3 + window-style, probe in the styled window", wait_out(out))
    # S8 refresh-client -r report
    r, pane = probe("s")
    c.send(f"refresh-client -r '{pane}:\\033]10;rgb:9999/8888/7777\\033\\\\'")
    out = f"{HERE}/out/r{os.getpid()}"
    tm("respawn-pane", "-k", "-t", pane, f"python3 {HERE}/probe.py {out}; sleep 30")
    show("S8 S3 + control client refresh-client -r report (fg)", wait_out(out))
    c.close(); f.close()
    # S3b control first, real, then control leaves
    fresh("s"); c = attach_ctl("s"); f = FakeTerm("s"); c.close(); time.sleep(0.3)
    show("S3b control first, real, control LEAVES", probe("s")[0])
    f.close()
    # S4 real first then control
    fresh("s"); f = FakeTerm("s"); c = attach_ctl("s")
    show("S4 real FIRST, then control", probe("s")[0])
    c.close(); f.close()
    # S5 control in other session
    fresh("s", "other"); c = attach_ctl("other"); f = FakeTerm("s")
    show("S5 control (first) in OTHER session + real in s", probe("s")[0])
    c.close(); f.close()
    # S9 helper-session mechanism from the plan
    fresh("s")
    c = Ctl(["new-session", "-A", "-s", "_ait_control", "-c", "/", "-f", "no-output,ignore-size",
             "exec sleep 2147483647"])
    c.send("set-option -t =_ait_control: destroy-unattached on")
    c2 = Ctl(["new-session", "-A", "-s", "_ait_control", "-c", "/", "-f", "no-output,ignore-size",
              "exec sleep 2147483647"])
    f = FakeTerm("s")
    show("S9 two control clients in helper session + real in s", probe("s")[0])
    print("   clients:", tm("list-clients", "-F", "#{client_control_mode}:#{client_session}").split())
    c.close(); time.sleep(0.3)
    print("   after 1st ctl leaves, sessions:", tm("list-sessions", "-F", "#S").split())
    c2.close(); time.sleep(0.5)
    print("   after last ctl leaves, sessions:", tm("list-sessions", "-F", "#S").split())
    f.close()
    # S11 real client that does NOT answer colour queries
    fresh("s"); f = FakeTerm("s", answer=False)
    show("S11 real client only, terminal never answers OSC 10/11", probe("s")[0])
    c = attach_ctl("s")
    show("S11b same + control client attached later", probe("s")[0])
    c.close(); f.close()
    # S12 real attached then detached (unattended)
    fresh("s"); f = FakeTerm("s"); f.close(); time.sleep(0.3)
    show("S12 real client attached, then detached", probe("s")[0])
    kill_server()


if __name__ == "__main__":
    main()
```

### `agents.py`

```python
import sys, time, re, collections, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness
from harness import *
harness.LIVE_LIKE = True

def colours(pane):
    cap = tm("capture-pane", "-e", "-p", "-t", pane)
    fg = collections.Counter(re.findall(r"\x1b\[[0-9;]*?38;2;(\d+;\d+;\d+)", cap))
    bg = collections.Counter(re.findall(r"\x1b\[[0-9;]*?48;2;(\d+;\d+;\d+)", cap))
    idx = collections.Counter(re.findall(r"\x1b\[((?:3|4|9|10)[0-7]|[34]8;5;\d+)m", cap))
    text = re.sub(r"\x1b\[[0-9;]*m", "", cap)
    return fg.most_common(6), bg.most_common(6), idx.most_common(4), text

def run(label, order, cmd, wait):
    fresh("s")
    cl = []
    for o in order:
        cl.append(attach_ctl("s") if o == "ctl" else FakeTerm("s"))
    pane = tm("new-window", "-P", "-F", "#{pane_id}", "-t", "=s:", "-c", f"{HERE}/agentdir", "-e", "COLORTERM=truecolor", cmd)
    time.sleep(wait)
    fg, bg, idx, text = colours(pane)
    print(f"== {label}\n   fg truecolor: {fg}\n   bg truecolor: {bg}\n   indexed: {idx}")
    lines = [l for l in text.splitlines() if l.strip()]
    print("   screen:", " | ".join(l.strip()[:60] for l in lines[:6]))
    print("   palette queries reaching outer terminal:", [c.palq for c in cl if isinstance(c, FakeTerm)])
    for c in cl: c.close()
    kill_server()

which = sys.argv[1]
cmd, wait = {"opencode": ("opencode", 8), "codex": ("codex", 8)}[which]
run(f"{which}: control FIRST then real (bug order)", ["ctl", "real"], cmd, wait)
run(f"{which}: real FIRST then control (good order)", ["real", "ctl"], cmd, wait)
```

### `dod.py`

```python
from harness import *
def helper():
    c = Ctl(["new-session","-A","-s","_ait_control","-c","/","-f","no-output,ignore-size","exec sleep 2147483647"])
    c.send("set-option -t =_ait_control: destroy-unattached on"); return c
def state(tag):
    print(f"  {tag}: sessions={tm('list-sessions','-F','#S',check=False).split()} clients={tm('list-clients','-F','#{client_control_mode}:#{client_session}',check=False).split()}")
for dod in ("off","on"):
    for others in ([], ["proj2"]):
        fresh("s", *others); tm("set","-g","detach-on-destroy",dod)
        c = helper(); f = FakeTerm("s")
        print(f"detach-on-destroy={dod} other project sessions={others}")
        tm("kill-session","-t","=s"); time.sleep(0.5); state("after kill-session s")
        c.close(); time.sleep(0.5); state("after control client leaves")
        f.close(); kill_server()
# ide order: session + monitor(control) first, real attaches after, with helper
fresh("s"); c = helper(); f = FakeTerm("s")
print("ide order w/ helper:", probe("s")[0]); c.close(); f.close(); kill_server()
```

