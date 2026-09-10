---
Task: t1773_restore_refuses_a_frozen_record_whose_window_was_closed.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1773 — Restore refuses a frozen record whose window was closed

## Context

Freeze an agent, then close its window (or restart the tmux server), then press
Restore. The result is:

```
RESTORE_FAILED:<id>|respawn:respawn-pane refused for %21
```

The record stays `frozen` and the capture survives — nothing is lost — but that
record can **never** be restored through this path again.

`agent_restore.restore()` binds `pane_id = rec.get("pane_id", "")`
(`.aitask-scripts/lib/agent_restore.py:334`) and then branches on `if pane_id:`
(`:393`) — on the **recorded** id, never on whether that pane still exists. A
retained frozen record keeps its old `%N` forever, so the branch takes
`frozen_ops.respawn()` against a dead pane instead of
`_launch_into_new_window()`.

This contradicts two shipped statements in `agent_freeze.drop_record()`'s
docstring: that `pane_id` is *"durable but NOT authoritative"* (which is why
`drop` preflights the live pane inventory and `restore` does not), and that a
frozen record *"stays restorable into a fresh window"*. The gone-pane branch is
today reachable **only** via the `freezing` + pane-gone reconcile row
(`agent_freeze.py:696`), which commits `--pane "" --pane-pid 0`. A record frozen
normally and later orphaned never gets there.

Intended outcome: an orphaned frozen record restores into a new window, exactly
as acceptance case 6a already proves the `_launch_into_new_window` branch can.
Only the routing into it is wrong.

## Measured facts this design rests on

Verified on tmux 3.6a during planning:

1. **Pane ids are monotonic within a server and never reused.** Killing `%1` and
   creating a pane yields `%2`. A **restarted server renumbers from `%0`** — so a
   server restart is the *only* mechanism that can make a recorded `%N` name a
   different pane.
2. **`if-shell -F` binds an identity check and a destructive command into one
   server dispatch:**
   ```
   tmux if-shell -F -t %N '#{==:#{@aitask_frozen},<rid>}' \
     'set-option -pu -t %N @aitask_standin_ready ; respawn-pane -k -e A=1 -e B=2 -t %N "<cmd>"'
   ```
   Match → the option is unset and the pane respawns. No match → the pane is
   **completely untouched** (same `pane_pid`, same `pane_start_command`).
   Repeated `-e` flags survive the wrapping (measured with two; the shipped path
   uses four).
3. **`if-shell` exits 0 either way**, so "did it fire" cannot be read from its
   exit status — and, per fact 1, *not* from a pid delta either: across a
   restart the before- and after-reads can describe two different panes, so a
   correctly rejected dispatch still shows a changed pid. Evidence must come
   from inside the matched branch (fact 5).
4. **tmux's lexer round-trips a command containing `'`, `"`, `$`, `;` and `>`**
   when wrapped in double quotes with `\`-escaping of `\`, `"` and `$`.
5. **A pane option set inside the matched branch is positive, branch-specific
   evidence.** It survives the `respawn-pane -k` in the same sequence, and a
   no-match dispatch leaves it untouched (measured: after a rejected dispatch
   the pane still carried the *previous* call's token, never the new one).
   Because pane options die with the pane, a recycled `%N` on a restarted
   server cannot carry it.
6. **A failing command aborts the rest of an `if-shell` command sequence**, so a
   token written *last* proves the respawn before it succeeded.

## Approach

Two independent defects, one root cause — the recorded `pane_id` is trusted as a
target instead of a hint:

- **Routing** — decide the branch from what the *server* says, not from the
  record. This is the reported bug.
- **Identity at the moment of action** — a probe and a `respawn-pane -k` in two
  separate tmux calls leave a window a server restart can slip through, after
  which the recorded `%N` may be an unrelated live agent that the respawn would
  kill. Close it by making the stamp check and the respawn **one** dispatch
  (fact 2), rather than a check that was true a moment ago.

`agent_freeze._probe_pane()` is already the correct resolver and keeps the
tri-state its docstring insists on: `present` / `gone` / `unknown` (tmux
unreachable). Collapsing `unknown` into `gone` would launch a **second** agent
while the original stand-in may still be alive.
`agent_frozen_ops.pane_facts()` cannot make that distinction, so rather than
duplicate a weaker probe, promote the existing one into the shared module.

`agent_restore` **must not import `agent_freeze`** (module docstring, one-way
dependency arrow), so `agent_frozen_ops` is the only correct home.

### Deliberately out of scope

- **`drop_record()` and `_respawn_standin()` ship the same two-call
  probe-then-act pattern.** This task puts the atomic primitive in the shared
  module and adopts it in `restore` only; converging the freeze-side sites is a
  follow-up (§9), so the one path that deletes a session's only capture is not
  rewritten inside a bug fix.
- **No tmux session for the record's project root.** `_launch_into_new_window`
  requires `discover_aitasks_sessions()` to find a session with a pane whose cwd
  walks up to the record's root. Restore runs via `run-shell -b` from a TUI pane
  that sits in the project, so the ordinary server-restart flow finds one. When
  none exists (restoring from a different project, or a bare `~` shell) the
  restore fails `no_session_for_root` and rolls back — fail-safe and retryable,
  but unfixed. This is pre-existing (case 6a shares it); §3 makes the message
  actionable and §9 files the recovery work.

## Changes

### 1. `.aitask-scripts/lib/agent_frozen_ops.py` — shared surface

**(a) Promote the probe.** Move `_probe_pane` and `_TMUX_UNREACHABLE` in from
`agent_freeze.py:865-895` as public names, behaviour unchanged:

- `TMUX_UNREACHABLE = -1` (the `TmuxClient.run` contract for
  `FileNotFoundError` / `OSError` / timeout);
- `probe_pane(pane_id) -> tuple[str, dict[str, str] | None]` returning
  `("present", {"pane_id", "frozen", "dead"})` / `("gone", None)` /
  `("unknown", None)`.

Keep the docstring verbatim — it is the record of *why* the three verdicts must
not be collapsed — and add one line noting it now serves the restore router.
`FROZEN_OPTION` is already imported here (`:77`).

**(b) `tmux_quote(s) -> str`.** One nesting level for tmux's own lexer
(fact 4):

```python
def tmux_quote(s: str) -> str:
    """Quote a command string for tmux's lexer, for commands nested in `if-shell`.

    tmux parses the command argument of `if-shell` itself, so a command string
    that has already been shell-quoted needs ONE more level. Double-quote form
    with `\\`-escaping of `\\ " $` round-trips `'`, `"`, `$`, `;` and `>`.
    """
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$") + '"'
```

**(c) `respawn_if_stamped(...) -> tuple[bool, str, int, str]`.** The atomic
replacement, returning `(fired, pane_id, pane_pid, reason)`:

```python
def respawn_if_stamped(pane_id, command, *, option, expect,
                       env=None, unset=None) -> tuple[bool, str, int, str]:
    """`respawn-pane -k`, but ONLY if the pane still carries ``option == expect``.

    The identity check and the destructive replacement travel as ONE
    `if-shell -F` command, so the server evaluates the stamp and respawns inside
    a single command-queue execution. A two-call probe-then-respawn leaves a
    window a tmux SERVER RESTART can slip through: pane ids are monotonic within
    a server and never reused, but a restarted server renumbers from `%0`, so a
    recorded `%N` can come back as an unrelated live agent's pane — and
    `respawn-pane -k` would kill it.

    `if-shell` exits 0 whether or not its branch ran, so "did it fire" needs
    evidence. **A pid delta is NOT that evidence** — the same restart window
    makes the before-read describe the old stamped pane and the after-read an
    unrelated recycled `%N`, so a correctly REJECTED dispatch still shows a
    changed pid. Reading that as success would record a stranger's pid as
    `launch_pid`, and `restore-confirm` would then liveness-confirm somebody
    else's agent as the restored one.

    The evidence is therefore POSITIVE and BRANCH-SPECIFIC: a fresh
    per-call token written by a `set-option` that is the LAST command of the
    matched branch. Pane options die with the pane, so a recycled `%N` cannot
    carry it; a rejected branch never runs it; and an `if-shell` sequence aborts
    after a failing command, so the token also proves the respawn ahead of it
    succeeded. Absent token ⇒ NOTHING was touched.

    ``reason`` names why a non-firing dispatch did not fire —
    ``stamp-mismatch``, ``server-restarted`` (the server generation moved
    between the two reads) or ``pane-gone`` — for the caller's log and the
    persisted `last_error`. It is diagnostic only; the token alone decides.
    """
```

Body:

1. `run(["display-message", "-p", "-t", pane_id, "#{pid}"])` → `server_before`;
   a non-zero rc returns `(False, "", 0, "pane-gone")` with nothing dispatched.
2. `token = secrets.token_hex(8)`. Build the inner sequence, joined with `" ; "`:
   `set-option -pu -t <pane> <unset>` (when `unset` is given), then
   `respawn-pane -k` with one `-e NAME=value` per env entry, `-t <pane>` and
   `tmux_quote(command)`, then **last**
   `set-option -p -t <pane> <RESPAWN_TOKEN_OPTION> <token>`.
3. `frozen_ops.pause_at("respawn_dispatch")` — a new stage on the existing
   `AITASKS_FROZEN_PAUSE_AT` seam, placed **between the pre-read and the
   dispatch** so a test can restart a real tmux server at exactly that boundary
   (§8b). Add it to the seam list in the module docstring.
4. Dispatch `if-shell -F -t <pane> '#{==:#{<option>},<expect>}' '<inner>'`.
5. One read for all the after-facts:
   `display-message -p -t <pane> '#{<RESPAWN_TOKEN_OPTION>}\t#{pane_id}\t#{pane_pid}\t#{pid}'`.
6. Token equals ours ⇒ `set-option -pu` the token (it is per-attempt) and return
   `(True, <pane from that same read>, <pid from that same read>, "")`.
7. Otherwise return `(False, "", 0, reason)` — **never** the observed pane or
   pid, so a caller cannot adopt a stranger's pane. `reason` is `"pane-gone"`
   when the read failed, `"server-restarted"` when the server pid moved, else
   `"stamp-mismatch"`.

`respawn()` is left exactly as it is — the freeze engine calls it on a pane it
has just stamped itself, where there is no window to guard.

**(d) The token option constant.** Add
`RESPAWN_TOKEN_OPTION = "@aitask_respawn_token"` to
`.aitask-scripts/monitor/monitor_core.py` beside `FROZEN_OPTION` /
`STANDIN_READY_OPTION` (`:426-438`) — that file is the pane-option vocabulary,
so a new name belongs there where nobody can collide with it. Document it as
**transient and coordinator-private**: written and cleared within one
`respawn_if_stamped` call, never classified, never part of `PANE_FACT_FORMAT`.
No shell counterpart is needed in `lib/agent_sessions.sh` (no shell code reads
it), so the spelling contract in `tests/test_agent_sessions_stamp.sh` is
unaffected.

### 2. `.aitask-scripts/lib/agent_freeze.py` — delegate

Delete the local `_probe_pane` / `_TMUX_UNREACHABLE` and call
`frozen_ops.probe_pane(...)` at the two existing sites (`:1006`, `:1030`, both
in `drop_record`). Calling through the module keeps the `_TMUX` test seam
working. Nothing outside `agent_freeze.py` references either name (verified by
grep), so this is a pure move.

### 3. `.aitask-scripts/lib/agent_restore.py` — hint, not target

**(a) Preflight (routing + fail-closed).** In `restore()`, inside the
*"everything that can fail WITHOUT touching the store"* block (after the argv
build at `:353`, before `restore-begin` at `:388`):

```python
# The recorded `pane_id` is a HINT, not a target: a retained frozen record
# keeps its old `%N` after the window is closed or the tmux server restarts
# (`_reconcile_frozen` returns `KEEP:<id>|pane_gone` and writes nothing).
# Resolve it against the SERVER before choosing the branch — the same rule
# `agent_freeze.drop_record()` applies for the same reason.
if pane_id:
    verdict, facts = frozen_ops.probe_pane(pane_id)
    if verdict == "unknown":
        # Fail CLOSED, before any write. Reading an unreachable tmux as "gone"
        # would mint a lease and drive a new-window launch that cannot work.
        return RestoreResult(
            record_id, False, "preflight",
            f"RESTORE_FAILED:{record_id}|preflight:tmux unreachable")
    if verdict != "present" or not facts or facts["frozen"] != record_id:
        pane_id = ""   # gone, or a recycled `%N` that is not ours
```

**(b) Respawn stage (identity, atomically).** Replace the `:393-400` block:

```python
if pane_id:
    fired, new_pane, new_pid, why = frozen_ops.respawn_if_stamped(
        pane_id, command, option=FROZEN_OPTION, expect=record_id,
        env=env, unset=STANDIN_READY_OPTION)
    if not fired:
        # The pane stopped being ours between the preflight and the dispatch —
        # only a server restart can do that. NOTHING was killed, and the helper
        # returned no location, so there is no stranger's pid to adopt.
        print(f"WARNING:{record_id}|recorded pane {pane_id} not reused: {why}",
              file=sys.stderr)
        pane_id = ""
if not pane_id:
    new_pane, new_pid, error = _launch_into_new_window(rec, command, env)
    if error:
        raise OSError(error)
```

The preflight's rebinding is what fixes the reported bug; the `fired` fallback
is what makes the destructive call safe. Every later use of the local `pane_id`
flows from these two bindings and is already correct for the empty case:

| site | with an empty effective `pane_id` |
|---|---|
| `:403/:423/:452/:471` `_rollback(..., pane_id, ...)` | skips the stand-in respawn and commits `--pane "" --pane-pid 0`, the shape `_reconcile_restoring` already uses to keep a record restorable |
| `:464` `pane_location(pane_id or new_pane)` | observes the **new** pane, so the liveness fallback cannot false-report `agent_exited` |
| `:488` `_clear_frozen_stamp(pane_id)` | no-op; a fresh pane never carried the stamp |

`_decide_from_record` (`:520-541`) is untouched: it reads a **re-read** record,
whose `pane_id` is updated to the new pane by `restore-launched`.

**(c) `_rollback` uses the same primitive.** `_rollback` (`:243-249`) respawns
the stand-in over the recorded pane with the identical two-call exposure. Switch
it to `respawn_if_stamped(pane_id, standin_command, option=FROZEN_OPTION,
expect=record_id, unset=STANDIN_READY_OPTION)`; when it does not fire, commit
`--pane "" --pane-pid 0` (the existing empty-pane branch), so a rolled-back
restore leaves the record restorable rather than re-stamping a stranger's pane
— and, because the helper returns no location on a miss, `standin-respawned`
can never record one.

**(d) Make the no-session failure actionable.** `_launch_into_new_window`'s
`"no_session_for_root"` becomes
`f"no_session_for_root:{rec.get('root','')}"`, so the persisted `last_error`
names the project whose session is missing instead of leaving the user to guess.

## Tests

### 4. `tests/test_agent_frozen_ops.py` — pin the new shared surface

Add `"probe_pane"`, `"tmux_quote"`, `"respawn_if_stamped"` to
`PROMISED_CALLABLES` and `"TMUX_UNREACHABLE"` to `PROMISED_VALUES` (`:47-56`),
then:

- `ProbePaneTests` — rc `0` + a 3-field line → `("present", {...})` with
  `frozen` / `dead` mapped; rc `1` → `("gone", None)`; rc `-1` →
  `("unknown", None)` (the distinction that must never collapse); a short read
  or empty first field → `("gone", None)`.
- `TmuxQuoteTests` — round-trip a command containing `'`, `"`, `$`, `;`, `>`
  and `\`; assert `\` `"` `$` are escaped and the result is double-quoted.
- `RespawnIfStampedTests` (scripted `_TMUX`) — the evidence rule is the point
  of this class:
  - the emitted argv is a single
    `if-shell -F -t <pane> '#{==:#{@aitask_frozen},<rid>}' '<inner>'`, whose
    inner string carries the ready-unset, the respawn with one `-e` per env
    entry, and the token `set-option` **last**;
  - the token is fresh per call (two calls emit different tokens);
  - **token returned ⇒ `fired=True`**, with the pane and pid taken from that
    same read, and the token then unset;
  - **no token but a CHANGED pid ⇒ `fired=False` and `("", 0)`** — the exact
    inference this design rejects: a pid delta alone must never be read as
    success, or a stranger's pid becomes `launch_pid`;
  - no token and a changed server pid ⇒ `reason == "server-restarted"`;
    no token, same server pid ⇒ `"stamp-mismatch"`;
  - a failed pre-read short-circuits with `reason == "pane-gone"` and **no**
    `if-shell` issued at all.

### 5. `tests/test_agent_restore.py` — fixture discrimination, then routing

**(a) The fake must discriminate — this breaks the existing tests otherwise.**
`probe_pane` (3 fields), `pane_facts` (10 fields) and `pane_location`
(2 fields) are *all* `display-message`, so a subcommand-only fake cannot serve
them. Both existing positive tests (`TestRestoreEnvDelivery:377`,
`TestHookWinsTheLaunchRace:410`) script `_FakeTmux(out="%104\t51000")`; with the
probe added, that 2-field answer parses as `gone` and diverts them into the
new-window branch, failing their `respawn-pane` assertions.

Add a `_ScriptedTmux` that dispatches on the **requested format**, not the
subcommand — match the format argument against `ops.PANE_FACT_FORMAT`, the
probe's 3-field format, and the 2-field pane-location format, returning a
correctly-shaped answer for each (and `(0, "")` for everything else). Update
both existing fixtures to use it so they supply all three shapes; their existing
assertions must then pass unchanged. Their `respawn-pane` assertions also move
to inspecting the `if-shell` inner command string.

**(b) `TestRecordedPaneIsOnlyAHint`** — using `_ScriptedTmux`, `_SwapMixin` and
`_rec()`:

1. **gone pane → new window**: probe rc `1`; patch
   `agent_restore._launch_into_new_window`; assert it was called and that no
   `respawn-pane` / `if-shell` argv reached tmux.
2. **present + our stamp → respawn**: probe returns `frozen == record id`;
   assert one `if-shell` targeting the recorded pane and no new-window call.
3. **recycled `%N` → new window, no kill**: probe returns a *different* record
   id in `frozen`; assert the new-window branch and that nothing targeted that
   pane.
4. **tmux unreachable → fail closed**: probe rc `-1`; assert
   `RESTORE_FAILED:<id>|preflight:tmux unreachable` and `store.verbs() == []`
   — nothing written, mirroring `TestPreflightsWriteNothing`.
5. **restart between the read and the dispatch** — the transition case no
   steady-state test reaches. Script the probe to say *present and ours*, then
   the post-dispatch read to return **no token, a different `pane_pid`, and a
   different server `#{pid}`** (a recycled `%N` on a restarted server, with the
   `if-shell` having correctly rejected the missing stamp). Assert: the restore
   completes via `_launch_into_new_window`; `restore-launched` is called with
   the **new window's** pane and pid and never with the stranger's; and the
   record therefore cannot be liveness-confirmed onto somebody else's agent.
6. **stamp lost without a restart**: same as 5 but with the server pid
   unchanged — `fired=False`, `reason == "stamp-mismatch"`, same routing.

### 6. `tests/test_frozen_agents_acceptance.sh` — complete case 6b

Case 6b (`:796-829`) currently asserts only the fail-safe half and names t1773
in its comment. Replace that narrative with what the case now proves, and lift
the assertions to match case 6a:

- `RESTORED:$RID` in the restore output;
- a window with the recorded name is back (`window_exists "$W" "$SESSION"`);
- the record is `live`;
- `pane_id` now names a pane that is **not** the dead `%N` and does exist;
- no second record was created; `window_slot` unchanged;
- the captures were deleted (hook ack), replacing the "capture is intact"
  fail-safe assertion.

### 7. `tests/test_restore_flows_live.sh` — case 7 is tautological today

Case 7 (`:382-405`) is titled *"a gone pane restores into a NEW window"* but its
only assertions — the output mentions the record id, and no second record exists
— hold just as well when the restore **fails**, which is what happens today: the
record is already `frozen`, so its `reconcile` returns `KEEP:<id>|pane_gone` and
writes nothing, leaving the dead `%N` in place. Add the assertions the title
promises: `RESTORED:$RID` in the output, and a window named `agent-pick-1711`
back in the session.

### 8. `tests/test_frozen_respawn_atomic_live.sh` — new file, real tmux

The scripted tests in §4-5 assert the *decision* given a response, but they
**assume** the pane-option lifecycle and rejected-dispatch behaviour the whole
mechanism rests on. Those were measured by hand during planning and nothing in
the suite pins them: a tmux version bump or a platform difference would leave
every mock green while the mechanism is broken. No existing live suite restarts
a server — they only kill a window.

New self-contained bash suite (run individually, like every other bash test),
sourcing `tests/lib/tmux_isolation.sh` (`require_isolated_tmux`, so the server it
kills is its own per-`TMUX_TMPDIR` one, never the user's) and
`tests/lib/frozen_fixtures.sh` for `tm` / `pane_fmt` / `pane_exists` /
`wait_stopped` / `section`. It drives `respawn_if_stamped` directly from a small
Python driver rather than through the whole coordinator, because the contract
under test is the helper's.

**(a) The tmux facts the design rests on** — one case per numbered fact above,
so a tmux change fails here with a named reason instead of somewhere downstream:

- matched dispatch → token present, `pane_start_command` changed, the `unset`
  option cleared, helper returns `(True, %N, <new pid>, "")`;
- rejected dispatch (wrong `expect`) → the pane is **completely untouched**:
  same `pane_pid`, same `pane_start_command`, no token; helper returns
  `(False, "", 0, "stamp-mismatch")`;
- pane options do **not** survive a server restart — stamp a pane, restart the
  server, recreate the same `%N`, assert `@aitask_frozen` is empty;
- pane ids renumber from `%0` on a fresh server (fact 1, the premise for
  "a restart is the only recycle vector");
- a command string containing `'`, `"`, `$`, `;` and `>` survives `tmux_quote`
  into the real pane's `pane_start_command`.

**(b) The boundary case — a real restart between the pre-read and the dispatch.**
This is the race the token exists for, and it is only reachable with the new
`respawn_dispatch` pause stage:

1. Fresh isolated server; stamp its first pane (`%0`) with
   `@aitask_frozen=<rid>` running a recognisable command; record the server pid.
2. Start the Python driver in the background with `AITASKS_TEST_MODE=1
   AITASKS_FROZEN_PAUSE_AT=respawn_dispatch`, calling `respawn_if_stamped` on
   that pane and printing the returned 4-tuple.
3. `wait_stopped $driver` — it has taken its `#{pid}` pre-read and is SIGSTOPped
   before dispatching.
4. `tm kill-server`; start a fresh server on the same socket; create panes until
   one carries the **same `%N`**, running an unrelated marker (`sleep 4242`);
   record that marker's pid.
5. `kill -CONT $driver`; wait for it.
6. Assert: the driver printed `fired=False`, pane `""`, pid `0`, reason
   `server-restarted`; **the marker process is still alive with the same pid**;
   the recreated pane's `pane_start_command` is still the marker; and it carries
   no `@aitask_respawn_token`.

Step 6 is the whole point: under the pid-delta inference this plan rejected, the
driver would have returned `fired=True` with the stranger's pane and pid.

## Verification

```bash
# Fast unit lane (no tmux):
python3 tests/test_agent_restore.py
python3 tests/test_agent_frozen_ops.py
bash tests/run_all_python_tests.sh          # whole suite; read the LAST line only

# Live tmux lanes (the ones that exercise the branch):
bash tests/test_frozen_agents_acceptance.sh   # cases 5, 6a, 6b, 7 (drop/reconcile too)
bash tests/test_restore_flows_live.sh         # case 7 + the freeze/drop flows
bash tests/test_frozen_respawn_atomic_live.sh # the tmux facts + the restart boundary
```

The two scenarios the task names now each have live coverage: **window closed**
by acceptance case 6b, **server restarted** by §8b.

The Python runner's verdict is its last line
(`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`); a piped run discards the
exit status, so use `set -o pipefail` or `${PIPESTATUS[0]}`.

Manual end-to-end (the user-facing reproduction): `ait board` → launch an agent
→ freeze it → `tmux kill-window` on its window → Restore → expect the agent back
in a **new** window with the recorded name, one record, state `live`.

## Risk

### Code-health risk: medium

- Promoting `_probe_pane` moves the resolver used by `drop_record`'s
  **destructive** kill preflight; a botched move could make `drop` kill a pane
  it should leave alone, or refuse to drop a droppable record ·
  severity: medium · → mitigation: inline post-phase `freeze_side_regression_sweep`
- `tmux_quote` adds a new escaping layer on the path every restore takes; a bug
  there breaks all restores, not just the racy ones · severity: medium ·
  → mitigation: none needed (pinned by the §4 round-trip tests and by §8a,
  which drives a metacharacter-laden command into a real pane)
- The atomic mechanism depends on tmux behaviours measured by hand at planning
  time (the pane-option lifecycle, rejected-dispatch inertness, id renumbering).
  Mocks would stay green if any of them changed · severity: medium ·
  → mitigation: none needed (§8a pins each measured fact as its own live case,
  and §8b exercises the real restart boundary)
- The recycled-`%N` guard makes the respawn conditional on the `@aitask_frozen`
  stamp. A frozen record whose stand-in somehow lost its stamp would now route
  to a new window and leave the stale stand-in behind — a duplicate viewer,
  never a lost record · severity: low ·
  → mitigation: inline pre-phase `pre_fix_control_for_routing`
- `restore` and `drop`/`_respawn_standin` now differ in their safety guarantee
  until §9 lands · severity: low · → mitigation: follow-up task (§9)
- `@aitask_respawn_token` adds a fifth entry to the pane-option vocabulary. It
  is written and cleared inside one helper call, but a crash between the two
  leaves a stale option on a live pane · severity: low · → mitigation: none
  needed (the token is per-call and compared for equality, so a stale one can
  only ever read as "did not fire" — the fail-safe direction)

### Goal-achievement risk: low

- The task's headline scenario says "or restart the tmux server". That works
  only when a session with a pane under the project root exists; the no-session
  case is documented and deferred (§9), not fixed · severity: low ·
  → mitigation: none needed (scope confirmed at planning)

### Planned mitigations

- timing: pre-phase | name: pre_fix_control_for_routing | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the stamp-conditional respawn branch, and the routing defect itself | desc: Write the routing unit tests and the strengthened live case 7 assertions FIRST and watch them fail against unfixed code, so the suite is proven to detect the defect rather than merely pass beside it.
- timing: post-phase | name: freeze_side_regression_sweep | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the `_probe_pane` promotion touching `drop`'s destructive preflight | desc: After the promotion, run the freeze-side live suites end to end and confirm `drop`'s kill/verify preflight behaves identically to pre-move.

## Implementation steps

### Pre-phase (risk mitigations)

**P0. `pre_fix_control_for_routing`** — before any source edit, write the new
assertions and run them against **unfixed** code:

1. Add `_ScriptedTmux` and the six `TestRecordedPaneIsOnlyAHint` cases (§5) and
   run `python3 tests/test_agent_restore.py`. Expected pre-fix: **all six
   FAIL** — 1, 3, 5 and 6 because the unfixed code respawns the recorded pane
   instead of routing to a new window; 4 because there is no preflight, so the
   store is written; and 2 because it asserts an `if-shell` dispatch that does
   not exist yet (the unfixed code issues a bare `respawn-pane`). Case 2 is the
   one whose pre-fix failure is a *shape* mismatch rather than a behaviour
   defect — note that distinction when recording the control, so a green 2
   after the fix is not read as evidence about routing.
2. Add the case-7 assertions (§7) and run `bash tests/test_restore_flows_live.sh`.
   Expected pre-fix: the new `RESTORED:` assertion FAILS.
3. Record the observed pre-fix failure lines in the task's Final Implementation
   Notes. A test that has never been watched to fail is not evidence.

### Main steps

1. Add `RESPAWN_TOKEN_OPTION` to `monitor/monitor_core.py` (§1d), then
   `probe_pane` / `TMUX_UNREACHABLE` / `tmux_quote` / `respawn_if_stamped` to
   `agent_frozen_ops.py` (§1a-c).
2. Delete the local copies in `agent_freeze.py` and delegate (§2).
3. Add the preflight, the atomic respawn stage, the `_rollback` switch and the
   actionable no-session error to `agent_restore.py` (§3).
4. Pin the new shared surface in `tests/test_agent_frozen_ops.py` (§4).
5. Update the two existing restore fixtures to `_ScriptedTmux` (§5a).
6. Complete acceptance case 6b (§6) and case 7 (§7).
7. Write `tests/test_frozen_respawn_atomic_live.sh` (§8) and confirm §8b fails
   when `respawn_if_stamped` is temporarily reverted to the pid-delta inference
   — that revert-and-watch is the pre-fix control for the token mechanism, which
   P0 cannot cover because the helper does not exist pre-fix.
8. Run the full verification set above; all suites green.

### Post-phase (risk mitigations)

**P1. `freeze_side_regression_sweep`** — after step 7, re-run the freeze-side
lanes and confirm `drop`'s preflight is unchanged:
`bash tests/test_frozen_agents_acceptance.sh` (drop/reconcile cases) and
`python3 tests/test_agent_frozen_ops.py`. Confirm no `DROP_FAILED:…|preflight:`
or `…|kill:` line appears where none appeared before.

## 9. Follow-up tasks (create at Step 8d)

1. **Converge the freeze-side destructive sites on `respawn_if_stamped` /
   a stamp-conditional kill** — `agent_freeze.drop_record()` (`:1006-1035`)
   probes then kills in two calls, and `_respawn_standin()` respawns a recorded
   pane the same way. Both carry the server-restart race this task closes for
   `restore`. `drop`'s kill is the one path that deletes a session's only
   capture, so it gets its own task rather than riding along in a bug fix.
2. **Restore into a session that does not exist yet** — when no tmux session has
   a pane under the record's project root, `_launch_into_new_window` returns
   `no_session_for_root:<root>` and the restore rolls back. Decide between
   falling back to the invoking pane's session (with `cwd = record root`) and
   creating a dedicated session, and cover it with an end-to-end
   server-restart-with-no-project-session test.

## Post-Implementation

Step 9 applies as usual: commit under `bug: … (t1773)`, merge to the resolved
output branch, and archive the task with its plan.
