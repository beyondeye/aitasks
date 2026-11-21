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

## Appendix B: implementation-time scripts and their output (2026-11-20)

Copied verbatim so the measurements can be re-run. They are not repo tests. Measured
with tmux 3.8, Codex 0.171.0 and OpenCode 1.18.34.

### `spike.py` (pre-phase `spike_bounce_and_notifications`)

Run from a scratch directory that also holds `probe.py` and `harness.py` from the
appendix above, with `SOCK = "t2051s"` in `harness.py` and its `fresh()` creating
sessions with `-c` set to that directory:
`env -u TMUX -u TMUX_PANE python3 spike.py`.

```python
#!/usr/bin/env python3
"""t2051 pre-phase spike (items a-i). Private tmux server only (-L t2051s)."""
import os, subprocess, sys, threading, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness
from harness import T, ENV, tm, fresh, kill_server, FakeTerm, probe

HELPER = "_ait_control"
MOPT = "@aitask_control_helper"
MARK = "aitasks-control-v1"
HOOK = ("if-shell -F '#{&&:#{==:#{client_control_mode},0},#{==:#{client_session},_ait_control}}' "
        "{ if-shell -F '#{==:#{server_sessions},1}' { detach-client } { switch-client -n } }")
UNGUARDED = ("if-shell -F '#{client_control_mode}' '' "
             "{ if-shell -F '#{==:#{server_sessions},1}' { detach-client } { switch-client -n } }")


def create_argv(project, hook=HOOK):
    a = ["has-session", "-t", "=" + project, ";",
         "new-session", "-s", HELPER, "-c", "/", "-f", "no-output,ignore-size",
         "exec sleep 2147483647", ";",
         "set-option", MOPT, MARK, ";",
         "set-option", "destroy-unattached", "on"]
    if hook:
        a += [";", "set-hook", "client-session-changed", hook]
    return a


def join_argv(project, hid):
    return ["has-session", "-t", "=" + project, ";",
            "attach-session", "-t", hid, "-f", "no-output,ignore-size"]


class Ctl:
    def __init__(self, argv):
        self.argv = argv
        self.p = subprocess.Popen([*T, "-C", *argv], env=ENV, stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.lines = []
        threading.Thread(target=self._rd, daemon=True).start()
        time.sleep(0.5)

    def _rd(self):
        for raw in self.p.stdout:
            self.lines.append(raw.decode(errors="replace").rstrip("\n"))

    def alive(self):
        return self.p.poll() is None

    def req(self, line, wait=0.4):
        n = len(self.lines)
        self.p.stdin.write(line.encode() + b"\n")
        self.p.stdin.flush()
        time.sleep(wait)
        return self.lines[n:]

    def close(self):
        try:
            self.p.stdin.close()
        except Exception:
            pass
        try:
            self.p.wait(timeout=2)
        except Exception:
            self.p.kill()


def clients():
    out = tm("list-clients", "-F", "#{client_name}|#{client_control_mode}|#{client_session}", check=False)
    return sorted(out.split("\n")) if out else []


def sessions():
    out = tm("list-sessions", "-F", "#{session_id}|#{session_name}", check=False)
    return out.split("\n") if out else []


def sid(name):
    for row in sessions():
        i, n = row.split("|", 1)
        if n == name:
            return i
    return None


def term_session(ft):
    """Where the fake terminal is now: session name, or DETACHED."""
    time.sleep(0.6)
    pid, _ = os.waitpid(ft.pid, os.WNOHANG)
    if pid:
        ft.pid_reaped = True
        return "DETACHED(exited)"
    rows = [r for r in clients() if r.split("|")[1] == "0"]
    return ",".join(r.split("|")[2] for r in rows) or "NO-REAL-CLIENT"


def term_name():
    rows = [r for r in clients() if r.split("|")[1] == "0"]
    return rows[0].split("|")[0]


def close_term(ft):
    if getattr(ft, "pid_reaped", False):
        try:
            os.close(ft.fd)
        except OSError:
            pass
        return
    ft.close()


def hdr(t):
    print(f"\n=== {t}", flush=True)


def main():
    print("tmux", subprocess.run(["tmux", "-V"], capture_output=True, text=True).stdout.strip())

    hdr("A/g: exact create list installs; marker + hook are session-local; no -t acts on new session")
    fresh("s")
    c = Ctl(create_argv("s"))
    print("  ctl alive:", c.alive(), "| startup lines:", c.lines[:12])
    print("  stderr:", c.p.stderr.read1(4096) if not c.alive() else "(alive)")
    H = sid(HELPER)
    print("  sessions:", sessions(), "helper id:", H)
    print("  local marker (show-options -qv -t H:):", repr(tm("show-options", "-qv", "-t", H + ":", MOPT)))
    print("  destroy-unattached local:", repr(tm("show-options", "-qv", "-t", H + ":", "destroy-unattached")))
    print("  show-hooks -t H: ->", repr(tm("show-hooks", "-t", H + ":")))
    print("  show-hooks -g client-session-changed ->", repr(tm("show-hooks", "-g", "client-session-changed", check=False)))
    print("  marker on project s (local):", repr(tm("show-options", "-qv", "-t", "=s:", MOPT)))
    print("  post-attach self query:", c.req("display-message -p '#{session_id}\t#{session_name}'"))
    print("  post-attach self marker:", c.req("show-options -qv " + MOPT))

    hdr("g/b: join by id; control join does nothing")
    c2 = Ctl(join_argv("s", H))
    print("  c2 alive:", c2.alive(), "clients:", clients())
    print("  c2 self:", c2.req("display-message -p '#{session_id}\t#{session_name}'"))
    c3 = Ctl(join_argv("s", "$999"))
    print("  join to bogus id alive:", c3.alive(), "stderr:", c3.p.stderr.read1(4096) if not c3.alive() else "")
    c3.close()

    hdr("i/h/e: listing through control; display-message on deleted; notifications")
    tm("new-session", "-d", "-s", "gone", "-c", harness.HERE)
    n0 = len(c.lines)
    print("  list-sessions via ctl:", c.req("list-sessions -F '#{session_id}\t#{session_name}'"))
    tm("kill-session", "-t", "=gone")
    time.sleep(0.4)
    print("  notifications after new+kill 'gone':", [l for l in c.lines[n0:] if l.startswith("%s")])
    print("  display-message -t =gone: via ctl:", c.req("display-message -p -t =gone: '#{session_id}'"))
    print("  has-session -t =gone via ctl:", c.req("has-session -t =gone"))
    print("  list-sessions via ctl after:", c.req("list-sessions -F '#{session_id}\t#{session_name}'"))
    n0 = len(c.lines)
    tm("new-session", "-d", "-s", "ren", "-c", harness.HERE)
    tm("rename-session", "-t", "=ren", "ren2")
    time.sleep(0.4)
    print("  notifications after new+rename:", [l for l in c.lines[n0:] if l.startswith("%s")])
    tm("kill-session", "-t", "=ren2")
    # kill and recreate under the same name in one command list
    tm("new-session", "-d", "-s", "p1", "-c", harness.HERE)
    old = sid("p1")
    n0 = len(c.lines)
    tm("kill-session", "-t", "=p1", ";", "new-session", "-d", "-s", "p1", "-c", harness.HERE)
    time.sleep(0.4)
    print("  kill+recreate p1: old id", old, "new id", sid("p1"),
          "| has-session:", c.req("has-session -t =p1"),
          "| notifs:", [l for l in c.lines[n0:] if l.startswith("%s")])
    tm("kill-session", "-t", "=p1")
    c2.close(); time.sleep(0.3)
    print("  after c2 leaves sessions:", sessions())
    c.close(); time.sleep(0.5)
    print("  after last ctl leaves sessions:", sessions())
    kill_server()

    hdr("d2: marker inheritance")
    fresh("s")
    tm("set-option", "-g", MOPT, MARK)
    tm("new-session", "-d", "-s", HELPER, "-c", harness.HERE)
    U = sid(HELPER)
    print("  format read:", repr(tm("list-sessions", "-F", "#{session_name}|#{" + MOPT + "}")))
    print("  show-options -qv -t U: ->", repr(tm("show-options", "-qv", "-t", U + ":", MOPT)))
    cc = Ctl(["attach-session", "-t", U, "-f", "no-output,ignore-size"])
    print("  via client, no target:", cc.req("show-options -qv " + MOPT))
    cc.close()
    kill_server()

    for dod in ("off", "on"):
        for others in (["p2"], ["p2", "p3"], []):
            hdr(f"a/d: bounce, detach-on-destroy={dod}, other sessions={others}")
            fresh("s", *others)
            tm("set", "-g", "detach-on-destroy", dod)
            c = Ctl(create_argv("s"))
            ft = FakeTerm("s")
            print("  before:", clients())
            tm("kill-session", "-t", "=s")
            print("  terminal now in:", term_session(ft), "| clients:", clients())
            c.close(); time.sleep(0.5)
            print("  after ctl leaves, sessions:", sessions())
            close_term(ft); kill_server()

    hdr("negative control: no hook, dod off, p2 present")
    fresh("s", "p2"); tm("set", "-g", "detach-on-destroy", "off")
    c = Ctl(create_argv("s", hook=None)); ft = FakeTerm("s")
    tm("kill-session", "-t", "=s")
    print("  terminal now in:", term_session(ft))
    c.close(); time.sleep(0.5)
    print("  after ctl leaves, sessions:", sessions())
    close_term(ft); kill_server()

    hdr("c: direct attach to the helper by a real client")
    fresh("s", "p2")
    c = Ctl(create_argv("s")); ft = FakeTerm(HELPER)
    print("  terminal now in:", term_session(ft))
    close_term(ft); c.close(); kill_server()

    hdr("c2: switch-client into the helper (prefix s)")
    fresh("s", "p2")
    c = Ctl(create_argv("s")); ft = FakeTerm("s")
    tm("switch-client", "-c", term_name(), "-t", "=" + HELPER)
    print("  terminal now in:", term_session(ft))
    close_term(ft); c.close(); kill_server()

    for label, hook in (("guarded", HOOK), ("UNGUARDED control", UNGUARDED)):
        hdr(f"finding 16: two switches in one command list ({label})")
        fresh("s", "p2", "p3")
        c = Ctl(create_argv("s", hook=hook)); ft = FakeTerm("s")
        tn = term_name()
        tm("switch-client", "-c", tn, "-t", "=" + HELPER, ";", "switch-client", "-c", tn, "-t", "=p3")
        print("  terminal now in:", term_session(ft))
        close_term(ft); c.close(); kill_server()

    hdr("colours: ide order with full create list (control first, then real)")
    fresh("s")
    c = Ctl(create_argv("s")); ft = FakeTerm("s")
    print("  probe:", probe("s")[0])
    close_term(ft); c.close(); kill_server()

    hdr("f: is an unmarked helper ever observable during create? (40 rounds)")
    seen_unmarked = 0; seen = 0
    for _ in range(40):
        fresh("s")
        stop = []
        obs = []
        def poll():
            while not stop:
                r = subprocess.run([*T, "list-sessions", "-F", "#{session_name}|#{" + MOPT + "}"],
                                   env=ENV, capture_output=True, text=True).stdout
                for row in r.split("\n"):
                    if row.startswith(HELPER + "|"):
                        obs.append(row)
        th = threading.Thread(target=poll, daemon=True); th.start()
        p = subprocess.Popen([*T, "-C", *create_argv("s")], env=ENV, stdin=subprocess.PIPE,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.15)
        stop.append(1); th.join()
        seen += len(obs); seen_unmarked += sum(1 for o in obs if o == HELPER + "|")
        p.stdin.close(); p.wait(timeout=2)
        kill_server()
    print(f"  helper rows observed: {seen}, unmarked: {seen_unmarked}")


if __name__ == "__main__":
    main()
```

Output:

```
tmux tmux 3.8

=== A/g: exact create list installs; marker + hook are session-local; no -t acts on new session
  ctl alive: True | startup lines: ['%begin 1795157233 317 0', '%end 1795157233 317 0', '%begin 1795157233 318 0', '%end 1795157233 318 0', '%sessions-changed', '%session-changed $1 _ait_control', '%begin 1795157233 319 0', '%end 1795157233 319 0', '%begin 1795157233 320 0', '%end 1795157233 320 0', '%begin 1795157233 321 0', '%end 1795157233 321 0']
  stderr: (alive)
  sessions: ['$1|_ait_control', '$0|s'] helper id: $1
  local marker (show-options -qv -t H:): 'aitasks-control-v1'
  destroy-unattached local: 'on'
  show-hooks -t H: -> 'client-session-changed[0] if-shell -F "#{&&:#{==:#{client_control_mode},0},#{==:#{client_session},_ait_control}}" { if-shell -F "#{==:#{server_sessions},1}" { detach-client } { switch-client -n } }'
  show-hooks -g client-session-changed -> 'client-session-changed'
  marker on project s (local): ''
  post-attach self query: ['%begin 1795157234 337 1', '$1\t_ait_control', '%end 1795157234 337 1']
  post-attach self marker: ['%begin 1795157234 338 1', 'aitasks-control-v1', '%end 1795157234 338 1']

=== g/b: join by id; control join does nothing
  c2 alive: True clients: ['client-1013032|1|_ait_control', 'client-1013781|1|_ait_control']
  c2 self: ['%begin 1795157235 345 1', '$1\t_ait_control', '%end 1795157235 345 1']
  join to bogus id alive: False stderr: b''

=== i/h/e: listing through control; display-message on deleted; notifications
  list-sessions via ctl: ['%begin 1795157236 351 1', '$1\t_ait_control', '$2\tgone', '$0\ts', '%end 1795157236 351 1']
  notifications after new+kill 'gone': ['%sessions-changed']
  display-message -t =gone: via ctl: ['%begin 1795157237 354 1', '', '%end 1795157237 354 1']
  has-session -t =gone via ctl: ['%begin 1795157237 355 1', "can't find session: gone", '%error 1795157237 355 1']
  list-sessions via ctl after: ['%begin 1795157237 356 1', '$1\t_ait_control', '$0\ts', '%end 1795157237 356 1']
  notifications after new+rename: ['%sessions-changed', '%session-renamed $3 ren2']
  kill+recreate p1: old id $4 new id $5 | has-session: ['%begin 1795157239 372 1', '%end 1795157239 372 1', '%unlinked-window-renamed @5 bash'] | notifs: ['%sessions-changed', '%sessions-changed']
  after c2 leaves sessions: ['$1|_ait_control', '$0|s']
  after last ctl leaves sessions: ['$0|s']

=== d2: marker inheritance
  format read: '_ait_control|aitasks-control-v1\ns|aitasks-control-v1'
  show-options -qv -t U: -> ''
  via client, no target: ['%begin 1795157241 329 1', '%end 1795157241 329 1']

=== a/d: bounce, detach-on-destroy=off, other sessions=['p2']
  before: ['/dev/pts/115|0|s', 'client-1017472|1|_ait_control']
  terminal now in: p2 | clients: ['/dev/pts/115|0|p2', 'client-1017472|1|_ait_control']
  after ctl leaves, sessions: ['$1|p2']

=== a/d: bounce, detach-on-destroy=off, other sessions=['p2', 'p3']
  before: ['/dev/pts/116|0|s', 'client-1018605|1|_ait_control']
  terminal now in: p2 | clients: ['/dev/pts/116|0|p2', 'client-1018605|1|_ait_control']
  after ctl leaves, sessions: ['$1|p2', '$2|p3']

=== a/d: bounce, detach-on-destroy=off, other sessions=[]
  before: ['/dev/pts/112|0|s', 'client-1019897|1|_ait_control']
  terminal now in: DETACHED(exited) | clients: ['client-1019897|1|_ait_control']
  after ctl leaves, sessions: []

=== a/d: bounce, detach-on-destroy=on, other sessions=['p2']
  before: ['/dev/pts/115|0|s', 'client-1021308|1|_ait_control']
  terminal now in: DETACHED(exited) | clients: ['client-1021308|1|_ait_control']
  after ctl leaves, sessions: ['$1|p2']

=== a/d: bounce, detach-on-destroy=on, other sessions=['p2', 'p3']
  before: ['/dev/pts/116|0|s', 'client-1023172|1|_ait_control']
  terminal now in: DETACHED(exited) | clients: ['client-1023172|1|_ait_control']
  after ctl leaves, sessions: ['$1|p2', '$2|p3']

=== a/d: bounce, detach-on-destroy=on, other sessions=[]
  before: ['/dev/pts/112|0|s', 'client-1025015|1|_ait_control']
  terminal now in: DETACHED(exited) | clients: ['client-1025015|1|_ait_control']
  after ctl leaves, sessions: []

=== negative control: no hook, dod off, p2 present
  terminal now in: _ait_control
  after ctl leaves, sessions: ['$2|_ait_control', '$1|p2']

=== c: direct attach to the helper by a real client
  terminal now in: p2

=== c2: switch-client into the helper (prefix s)
  terminal now in: p2

=== finding 16: two switches in one command list (guarded)
  terminal now in: p3

=== finding 16: two switches in one command list (UNGUARDED control)
  terminal now in: s

=== colours: ide order with full create list (control first, then real)
  probe: {'fg': 'rgb:cccc/dddd/eeee', 'bg': 'rgb:2222/3333/4444', 'pal1': 'rgb:f3f3/8b8b/a8a8', 'pal7': 'rgb:baba/c2c2/dede', 'da': True}

=== f: is an unmarked helper ever observable during create? (40 rounds)
  helper rows observed: 3711, unmarked: 0
```

### `agents_verify.py` (real-agent verification)

`env -u TMUX -u TMUX_PANE <framework python> agents_verify.py opencode`, and
`… agents_verify.py codex --turn` (one model turn). Uses the repo's
`tests/lib/fake_terminal.py` and the framework's `launch_in_tmux` on the private
socket `t2051v`.

```python
#!/usr/bin/env python3
"""t2051 real-agent verification (scratch script, not a repo test).

Usage: agents_verify.py <codex|opencode> [--turn]

Private tmux server only (AITASKS_TMUX_SOCKET=t2051v, started with -f /dev/null,
TMUX / TMUX_PANE dropped). Mirrors the live server's options that matter
(allow-passthrough on, *:RGB). Agents are launched through the framework's own
launch_in_tmux. Colours are counted from `capture-pane -e -p`.

Scenarios:
  A  backend (fix) first, then the fake terminal  -- the `ait ide` order
  B  no real client at launch; fake terminal attached afterwards
  C  control: OLD attach (control client in the project session) first
  D  agent started under C, then the old client leaves and the fix backend starts
With --turn (codex only) scenario A also runs one short turn and samples the
"Working" shimmer.
"""
import collections
import os
import re
import subprocess
import sys
import time

REPO = "/home/ddt/Work/aitasks"
SOCK = "t2051v"
for k in ("TMUX", "TMUX_PANE", "TMUX_TMPDIR"):
    os.environ.pop(k, None)
os.environ["AITASKS_TMUX_SOCKET"] = SOCK
sys.path[:0] = [REPO + "/.aitask-scripts", REPO + "/.aitask-scripts/lib", REPO + "/tests/lib"]

from agent_launch_utils import TmuxLaunchConfig, launch_in_tmux  # noqa: E402
from fake_terminal import FakeTerminal  # noqa: E402
from monitor.monitor_core import TmuxControlBackend  # noqa: E402

ENV = dict(os.environ)
T = ["tmux", "-L", SOCK, "-f", "/dev/null"]
WHICH = sys.argv[1]
TURN = "--turn" in sys.argv
COMMANDS = {"codex": "codex --sandbox read-only", "opencode": "opencode"}
WAIT = 9


def tm(*a, check=True):
    r = subprocess.run([*T, *a], env=ENV, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"tmux {a}: {r.stderr.strip()}")
    return r.stdout


def fresh():
    subprocess.run([*T, "kill-server"], env=ENV, capture_output=True)
    time.sleep(0.3)
    tm("new-session", "-d", "-s", "s", "-x", "120", "-y", "40", "-c", REPO, "sleep 36000")
    tm("set", "-g", "default-terminal", "tmux-256color")
    tm("set", "-g", "allow-passthrough", "on")
    tm("set", "-as", "terminal-overrides", ",*:RGB")
    tm("set", "-s", "extended-keys", "on")
    tm("set", "-g", "focus-events", "on")
    tm("set-environment", "-g", "COLORTERM", "truecolor")


def clients():
    return tm("list-clients", "-F", "#{client_control_mode}:#{client_session}", check=False).split()


def launch():
    pid, err = launch_in_tmux(COMMANDS[WHICH], TmuxLaunchConfig(
        session="s", window=f"agent-{WHICH}", new_session=False, new_window=True, cwd=REPO))
    if err:
        raise RuntimeError(err)
    panes = tm("list-panes", "-s", "-t", "=s:", "-F", "#{pane_id} #{window_name}").splitlines()
    return [p.split()[0] for p in panes if p.endswith(f"agent-{WHICH}")][-1]


def colours(pane):
    cap = tm("capture-pane", "-e", "-p", "-t", pane)
    fg = collections.Counter(re.findall(r"38;2;(\d+;\d+;\d+)", cap))
    bg = collections.Counter(re.findall(r"48;2;(\d+;\d+;\d+)", cap))
    text = re.sub(r"\x1b\[[0-9;]*m", "", cap)
    lines = [ln.strip()[:50] for ln in text.splitlines() if ln.strip()]
    return fg.most_common(5), bg.most_common(5), lines[:4]


def report(label, pane, terms=()):
    fg, bg, lines = colours(pane)
    print(f"== {WHICH} {label}\n   clients: {clients()}\n   fg: {fg}\n   bg: {bg}")
    print("   screen:", " | ".join(lines))
    if terms:
        print("   palette queries reaching the terminal:", [t.palette_queries for t in terms])
    sys.stdout.flush()


def shimmer(pane):
    """Send one short prompt and sample the 'Working' line's colours."""
    tm("send-keys", "-t", pane, "-l", "--", "reply with: ok")
    time.sleep(0.5)
    tm("send-keys", "-t", pane, "Enter")
    seen = collections.Counter()
    samples = 0
    end = time.time() + 25
    while time.time() < end:
        cap = tm("capture-pane", "-e", "-p", "-t", pane)
        for line in cap.splitlines():
            plain = re.sub(r"\x1b\[[0-9;]*m", "", line)
            if "Working" in plain:
                samples += 1
                seen.update(re.findall(r"38;2;(\d+;\d+;\d+)", line))
        time.sleep(0.1)
    print(f"   shimmer: {samples} 'Working' lines sampled; fg colours: {seen.most_common(12)}")
    print("   black (0;0;0) on the Working line:", seen.get("0;0;0", 0))
    sys.stdout.flush()


def old_attach():
    return subprocess.Popen([*T, "-C", "attach", "-t", "=s", "-f", "no-output,ignore-size"],
                            env=ENV, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)


def main():
    # A: fix, ide order
    fresh()
    b = TmuxControlBackend("s"); assert b.start()
    time.sleep(0.3)
    ft = FakeTerminal(T, ENV, "s", palette=True); time.sleep(1.0)
    pane = launch(); time.sleep(WAIT)
    report("A: fix, backend first then terminal (ide order)", pane, [ft])
    if TURN:
        shimmer(pane)
        report("A: after the turn", pane)
    ft.close(); b.stop()

    # B: no real client at launch
    fresh()
    b = TmuxControlBackend("s"); assert b.start()
    pane = launch(); time.sleep(WAIT)
    report("B1: fix, NO real client at launch", pane)
    ft = FakeTerminal(T, ENV, "s", palette=True); time.sleep(4.0)
    report("B2: same agent, terminal attached afterwards (+4s)", pane, [ft])
    ft.close(); b.stop()

    # C: control, old attach first
    fresh()
    old = old_attach(); time.sleep(0.5)
    ft = FakeTerminal(T, ENV, "s", palette=True); time.sleep(1.0)
    pane = launch(); time.sleep(WAIT)
    report("C: CONTROL, old attach first then terminal", pane, [ft])

    # D: the same agent, after the old client leaves and the fix starts
    old.stdin.close(); old.wait(timeout=3)
    b = TmuxControlBackend("s"); assert b.start()
    time.sleep(5.0)
    report("D: agent from C, old client gone + fix backend (+5s)", pane)
    tm("resize-window", "-t", "=s:", "-x", "110", "-y", "38", check=False)
    time.sleep(3.0)
    report("D2: same, after a resize (+3s)", pane)
    ft.close(); b.stop()
    subprocess.run([*T, "kill-server"], env=ENV, capture_output=True)


if __name__ == "__main__":
    main()
```

Output, OpenCode:

```
== opencode A: fix, backend first then terminal (ide order)
   clients: ['1:_ait_control', '0:s']
   fg: [('255;255;255', 25), ('174;174;174', 13), ('204;221;238', 7), ('245;194;231', 6), ('69;82;95', 1)]
   bg: [('48;73;97', 5), ('69;82;95', 4), ('77;94;111', 4)]
   screen: ▄ | █▀▀█ █▀▀█ █▀▀█ █▀▀▄ █▀▀▀ █▀▀█ █▀▀█ █▀▀█ | █  █ █  █ █▀▀▀ █  █ █    █  █ █  █ █▀▀▀ | ▀▀▀▀ █▀▀▀ ▀▀▀▀ ▀▀▀▀ ▀▀▀▀ ▀▀▀▀ ▀▀▀▀ ▀▀▀▀
   palette queries reaching the terminal: [17]
== opencode B1: fix, NO real client at launch
   clients: ['1:_ait_control']
   fg: [('255;255;255', 25), ('128;128;128', 13), ('238;238;238', 7), ('92;156;245', 6), ('40;40;40', 1)]
   bg: [('10;10;10', 16), ('30;30;30', 5), ('40;40;40', 4), ('67;67;67', 4)]
   screen: ▄ | █▀▀█ █▀▀█ █▀▀█ █▀▀▄ █▀▀▀ █▀▀█ █▀▀█ █▀▀█ | █  █ █  █ █▀▀▀ █  █ █    █  █ █  █ █▀▀▀ | ▀▀▀▀ █▀▀▀ ▀▀▀▀ ▀▀▀▀ ▀▀▀▀ ▀▀▀▀ ▀▀▀▀ ▀▀▀▀
== opencode B2: same agent, terminal attached afterwards (+4s)
   clients: ['1:_ait_control', '0:s']
   fg: [('255;255;255', 25), ('128;128;128', 13), ('238;238;238', 7), ('92;156;245', 6), ('40;40;40', 1)]
   bg: [('10;10;10', 16), ('30;30;30', 5), ('40;40;40', 4), ('67;67;67', 4)]
   screen: ▄ | █▀▀█ █▀▀█ █▀▀█ █▀▀▄ █▀▀▀ █▀▀█ █▀▀█ █▀▀█ | █  █ █  █ █▀▀▀ █  █ █    █  █ █  █ █▀▀▀ | ▀▀▀▀ █▀▀▀ ▀▀▀▀ ▀▀▀▀ ▀▀▀▀ ▀▀▀▀ ▀▀▀▀ ▀▀▀▀
   palette queries reaching the terminal: [17]
== opencode C: CONTROL, old attach first then terminal
   clients: ['1:s', '0:s']
   fg: [('255;255;255', 25), ('180;180;180', 13), ('0;0;0', 7), ('245;194;231', 6), ('45;45;45', 1)]
   bg: [('25;25;25', 5), ('45;45;45', 4), ('0;0;0', 4)]
   screen: ▄ | █▀▀█ █▀▀█ █▀▀█ █▀▀▄ █▀▀▀ █▀▀█ █▀▀█ █▀▀█ | █  █ █  █ █▀▀▀ █  █ █    █  █ █  █ █▀▀▀ | ▀▀▀▀ █▀▀▀ ▀▀▀▀ ▀▀▀▀ ▀▀▀▀ ▀▀▀▀ ▀▀▀▀ ▀▀▀▀
   palette queries reaching the terminal: [17]
== opencode D: agent from C, old client gone + fix backend (+5s)
   clients: ['0:s', '1:_ait_control']
   fg: [('255;255;255', 25), ('180;180;180', 13), ('0;0;0', 7), ('245;194;231', 6), ('45;45;45', 1)]
   bg: [('25;25;25', 5), ('45;45;45', 4), ('0;0;0', 4)]
   screen: ▄ | █▀▀█ █▀▀█ █▀▀█ █▀▀▄ █▀▀▀ █▀▀█ █▀▀█ █▀▀█ | █  █ █  █ █▀▀▀ █  █ █    █  █ █  █ █▀▀▀ | ▀▀▀▀ █▀▀▀ ▀▀▀▀ ▀▀▀▀ ▀▀▀▀ ▀▀▀▀ ▀▀▀▀ ▀▀▀▀
== opencode D2: same, after a resize (+3s)
   clients: ['0:s', '1:_ait_control']
   fg: [('255;255;255', 25), ('180;180;180', 13), ('0;0;0', 7), ('245;194;231', 6), ('45;45;45', 1)]
   bg: [('25;25;25', 5), ('45;45;45', 4), ('0;0;0', 4)]
   screen: ▄ | █▀▀█ █▀▀█ █▀▀█ █▀▀▄ █▀▀▀ █▀▀█ █▀▀█ █▀▀█ | █  █ █  █ █▀▀▀ █  █ █    █  █ █  █ █▀▀▀ | ▀▀▀▀ █▀▀▀ ▀▀▀▀ ▀▀▀▀ ▀▀▀▀ ▀▀▀▀ ▀▀▀▀ ▀▀▀▀
```

Output, Codex (lines cut at 600 characters):

```
== codex A: fix, backend first then terminal (ide order)
   clients: ['1:_ait_control', '0:s']
   fg: [('44;61;80', 8), ('56;72;89', 8), ('37;55;75', 7), ('58;74;89', 7), ('138;155;171', 7)]
   bg: [('60;75;90', 3)]
   screen: >_ OpenAI Codex (v0.171.0) | ~/Work/aitasks | ⣀⣤⣤⣤⣀⣀ | ⣠⣶⣿⣿⣿⣿⣿⣿⣿⣿⣦⣤⣤⣤⣤⣤⣤⡀
   palette queries reaching the terminal: [0]
   shimmer: 41 'Working' lines sampled; fg colours: [('204;221;238', 66), ('119;136;153', 41), ('151;168;185', 4), ('103;120;137', 4), ('65;82;99', 4), ('189;206;223', 3), ('120;137;154', 3), ('203;220;237', 3), ('150;167;184', 2), ('199;216;233', 2), ('51;68;85', 2), ('163;180;197', 1)]
   black (0;0;0) on the Working line: 0
== codex A: after the turn
   clients: ['1:_ait_control', '0:s']
   fg: [('138;155;171', 8), ('204;221;238', 3), ('242;181;144', 2), ('99;168;248', 1), ('246;226;183', 1)]
   bg: [('60;75;90', 3), ('69;83;97', 2)]
   screen: >_ OpenAI Codex (v0.171.0) | ~/Work/aitasks | › reply with: ok | • ok
== codex B1: fix, NO real client at launch
   clients: ['1:_ait_control']
   fg: [('99;168;248', 1), ('246;226;183', 1), ('171;223;167', 1), ('242;181;144', 1), ('196;167;103', 1)]
   bg: []
   screen: >_ OpenAI Codex (v0.171.0) | ~/Work/aitasks | ⣀⣤⣤⣤⣀⣀ | ⣠⣶⣿⣿⣿⣿⣿⣿⣿⣿⣦⣤⣤⣤⣤⣤⣤⡀
== codex B2: same agent, terminal attached afterwards (+4s)
   clients: ['1:_ait_control', '0:s']
   fg: [('99;168;248', 1), ('246;226;183', 1), ('171;223;167', 1), ('242;181;144', 1), ('196;167;103', 1)]
   bg: []
   screen: >_ OpenAI Codex (v0.171.0) | ~/Work/aitasks | ⣀⣤⣤⣤⣀⣀ | ⣠⣶⣿⣿⣿⣿⣿⣿⣿⣿⣦⣤⣤⣤⣤⣤⣤⡀
   palette queries reaching the terminal: [0]
== codex C: CONTROL, old attach first then terminal
   clients: ['1:s', '0:s']
   fg: [('30;31;33', 9), ('9;12;18', 8), ('28;30;32', 8), ('117;117;117', 8), ('16;19;23', 7)]
   bg: [('30;30;30', 3)]
   screen: >_ OpenAI Codex (v0.171.0) | ~/Work/aitasks | ⣀⣤⣤⣤⣀⣀ | ⣠⣶⣿⣿⣿⣿⣿⣿⣿⣿⣦⣤⣤⣤⣤⣤⣤⡀
   palette queries reaching the terminal: [0]
== codex D: agent from C, old client gone + fix backend (+5s)
   clients: ['0:s', '1:_ait_control']
   fg: [('30;31;33', 9), ('9;12;18', 8), ('28;30;32', 8), ('117;117;117', 8), ('16;19;23', 7)]
   bg: [('30;30;30', 3)]
   screen: >_ OpenAI Codex (v0.171.0) | ~/Work/aitasks | ⣀⣤⣤⣤⣀⣀ | ⣠⣶⣿⣿⣿⣿⣿⣿⣿⣿⣦⣤⣤⣤⣤⣤⣤⡀
== codex D2: same, after a resize (+3s)
   clients: ['0:s', '1:_ait_control']
   fg: [('30;31;33', 9), ('9;12;18', 8), ('28;30;32', 8), ('117;117;117', 8), ('16;19;23', 7)]
   bg: [('30;30;30', 3)]
   screen: >_ OpenAI Codex (v0.171.0) | ~/Work/aitasks | ⣀⣤⣤⣤⣀⣀ | ⣠⣶⣿⣿⣿⣿⣿⣿⣿⣿⣦⣤⣤⣤⣤⣤⣤⡀
```

## Post-Review Changes

### Change Request 1 (2026-11-20 10:30)
- **Requested by user:** four review findings, all confirmed. (1) A project deleted
  between a request timeout and the reconnect reached FALLBACK with `exit_seen`
  unset, so the status server never refreshed. (2) `parse_session_rows` used
  `str.splitlines()`, which cuts a session name containing U+2028 / U+0085 in two.
  (3) The explicit-target guard scanned only positional argv, missing `args=`.
  (4) `test_deletion_during_a_check_is_not_lost` paused before the first query, so
  it passed even with notifications dropped during a check.
- **Changes made:** (1) the backend remembers the last connected client's project
  session id and passes it to each reconnecting client (`expected_project_id`); a
  successful start listing that shows it gone or replaced sets `lost_project`, and
  the supervisor then raises `exit_seen`. A failed listing sets nothing. (2) rows
  are split on `"\n"` only. (3) the guard also reads the `args=` keyword. (4) the
  test now holds a first result that already saw the project present, deletes the
  project during the hold, and requires a second query to report `gone`. Each fix
  has a regression test and a pre-fix control.
- **Files affected:** `.aitask-scripts/monitor/monitor_core.py`,
  `.aitask-scripts/lib/tmux_exec.py`, `tests/test_control_helper_session_live.py`,
  `tests/test_control_routed_explicit_targets.py`, `tests/test_tmux_exec.py`.

### Change Request 2 (2026-11-21)
- **Requested by user:** one review finding, confirmed. After a request timeout, a
  tmux shutdown while the timed-out client was closing reached FALLBACK with
  `exit_seen` unset: the client's `%exit` is ignored while it closes, and a
  reconnect listing cannot prove project loss once the server is gone.
- **Changes made:** when a reconnect's listing fails, the client asks the gateway's
  classified probe (`TmuxClient.run_checked`) whether tmux reports no server. Only
  that answer sets `lost_project = "server_gone"`, which raises `exit_seen`. A
  timeout or any other failure sets nothing. Tests: shutdown between timeout and
  reconnect, its pre-fix control, and a server stalled through every reconnect
  attempt (must not read as a shutdown).
- **Files affected:** `.aitask-scripts/monitor/monitor_core.py`,
  `tests/test_control_helper_session_live.py`.

## Final Implementation Notes
- **Actual work done:** The monitor's control clients (`TmuxControlClient`) attach to
  the `_ait_control` helper session instead of the project session, in three shapes
  (create / join by session id / legacy attach when a foreign session has the name).
  Added: the gateway primitives in `lib/tmux_exec.py` (constants, bounce hook text,
  `parse_session_rows`, `control_helper_owned`), the name reservation in the three
  validators, the owned-helper filter in `get_tmux_sessions()`, the project check
  (`check_project`, scheduled on `%sessions-changed` / `%session-renamed`), explicit
  targets for `_read_attached_session` and `_run_frozen_detached`, the supervisor's
  close-before-replace and `_starting` ownership, docs (`tmux_gateway.md`,
  `tui_conventions.md`, website monitor reference). Tests: new
  `tests/test_control_helper_session_live.py` (47 cases) and
  `tests/test_control_routed_explicit_targets.py` (11), helpers
  `tests/lib/fake_terminal.py` and `tests/lib/osc_probe.py`, and rewrites of the
  control, resilience (B2, B3), status-server-live, argv, UTF-8, frozen-filter and
  refresh tests that asked the client for its session with no target.
- **Pre-phase spike (`spike_bounce_and_notifications`):** every item a–i held on
  tmux 3.8; script and full output are in Appendix B. Notable: a direct attach to
  the helper also fires `client-session-changed`, so one hook is enough; startup
  command replies are flag-0 blocks; an unmarked helper was never observable during
  creation (3711 rows over 40 rounds).
- **Real-agent verification (Appendix B):** fix in the `ait ide` order: Codex shimmer
  0 black of 41 sampled lines, backgrounds `60;75;90`; OpenCode text `204;221;238`,
  no `0;0;0`. Old attach (control): Codex `30;30;30` backgrounds, OpenCode text and
  panels `0;0;0`. No real client at launch: OpenCode uses its built-in theme
  (readable); Codex start screen readable, shimmer in that case NOT sampled (it
  would cost a second model turn). Neither agent re-queries after the fix lands, so
  the website text says agents keep startup colours until restarted. Decision rule
  outcome: no follow-up task created for the no-client case.
- **Deviations from plan:**
  - `close()` now sets `_closing`, and a `%exit` that arrives while closing does not
    set `saw_exit`. Closing a timed-out client (new in §3b) makes tmux send `%exit`,
    which would otherwise read as "the session went away" on a path where server
    and project are both alive.
  - The backend carries the project session id into reconnects
    (`expected_project_id` → `lost_project`), and a reconnect whose listing fails
    asks `run_checked` whether tmux reports no server (Change Requests 1 and 2).
  - Plan live case 15b's "bounce failure detaches" became "the hook starts no job"
    when the hook changed to tmux commands only (already in the approved plan).
  - The plan's status-server item 16 is covered by the rewritten cases in
    `tests/test_monitor_status_server_live.py`, not by the new file. The served
    session is now passed with `--session s1` because the control client no longer
    sits in it.
  - The notes to t2161 and t2038 are sent at Step 8e, after this commit.
- **Issues encountered:** the first full Python run had 2 failures, both tests
  pinning the old untargeted argv (`test_monitor_frozen_filter.py`,
  `test_monitor_refresh_no_sync_tmux.py`); updated. A pre-fix control in
  `tests/test_tmux_utf8_client_live.sh` no longer reached the strict encoder because
  start() now looks the project up by name first; it now injects the name into a
  request. tmux socket paths under the long scratchpad directory exceed the
  AF_UNIX limit, so private servers use a short `-L` name in the default directory.
- **Tests not run:** seven live shell tests refuse to run beside a live `ait` tmux
  server (exit 2): `test_restore_flows_live.sh`, `test_freeze_engine_live.sh`,
  `test_cleanup_rule_parity.sh`, `test_monitor_harvest_close_live.sh`,
  `test_scratchpad_spawn_live.sh`, `test_monitor_shadow_spawn_live.sh`,
  `test_sitrep_window_hook_live.sh`. The full Python suite was run once, before the
  two review rounds (12,683 + 62 passed, 2 failed and since fixed); after the review
  fixes only the affected suites were re-run.
- **Key decisions:** identity is the tmux session id everywhere (join, project
  check, reconnect); ownership is the session-local marker read through one helper;
  the bounce hook is tmux commands only and lands on the next session by name (user
  decision); absence is proved only by a whole `list-sessions` reply or tmux's own
  no-server answer, never by a failed probe.
- **Upstream defects identified:**
  - `tests/test_workflow_phase_standalone.sh:155-157 — Guard 3 expects 2 matches of 'agent_key_from_command(shadow_command)' in minimonitor_app.py; the committed file has 0, so the test fails at HEAD`
  - `.aitask-scripts/monitor/monitor_core.py:_supervisor_loop — any exception other than CancelledError raised by a reconnect's start() ends the supervisor task silently and leaves the backend in RECONNECTING forever`
