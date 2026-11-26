---
Task: t2349_sitrep_focus_bind_client_check_to_switch.md
Base branch: main
Output branch: main
---

# t2349 — bind the sitrep jump's client check to the switch (atomic on every tmux)

## Context

`monitor_core.spawn_sitrep`'s cold cross-session jump (t2338) works in three
steps:
1. It reads the initiating client at launch (`_sitrep_launch_client`).
2. After the companion spawn it re-checks that client
   (`_sitrep_client_still_attached`, which uses `list-clients`).
3. It switches the client in a SEPARATE call
   (`switch_to_pane_anywhere(agent, client=name)`).

A client that closes between steps 2 and 3 and is replaced by a new terminal on
the same freed `/dev/pts/N` gets moved. The goal is to bind the identity check
to the switch, server-side, so no other client is ever moved. Constraint: leave
`switch_to_pane_anywhere` and its other callers unchanged.

**User decision (2026-11-26):** on tmux < 3.4, use a guarded best-effort jump.
There is no two-call fallback anywhere. When the identity cannot be checked
atomically, nothing moves and the open reports a `focus_skipped` warning.

### Measured (private `-L` sockets, tmux 3.8 and real tmux 3.3a, this session)

| probe | 3.8 | 3.3a |
|---|---|---|
| `#{L:#{?<name==&&pid==>,1,}}` (client loop; first shipped in 3.4) | `1` / `""` | literal `L:1` / `L:`, which is truthy, so `if-shell -F` **moved a wrong-pid client** (review finding 1) |
| `#{==:#{L:…},1}` (exact match) | `1` only for the right name+pid | `0` always (never fires) |
| `display-message -p 'ABSENT:#{L:1}'` | `ABSENT:1` with clients, `ABSENT:` with none | `ABSENT:` |
| `if-shell -F -t <pane> '#{&&:#{==:#{client_name},N},#{==:#{client_pid},P}}'` | evaluates against the client tmux resolves for the command, which **depends on the dispatching process's context**, not on `-t`'s pane. With the caller's `TMUX`/`TMUX_PANE` (session A), it resolves the terminal viewing A (the initiator) and matches. Unscoped, or with session D's context, it resolves another terminal (measured: the most recently attached or active one) and skips. A wrong pid is always FALSE | same (both contexts measured on both versions) |
| three-command branch (`switch-client -t $S ; select-window ; select-pane`) when the pane dies after the id lookup | rc 1, but **the client is left in the destination session** (review finding 2) | — |
| ONE `switch-client -c 'N' -t '$S:@W.%P'` | live pane: moves and selects the window and pane. Pane killed, or moved by `break-pane`, after the lookup: "can't find pane", rc 1, nothing moves | same |
| hostile session name `sb x$HOME` | harmless (only ids are spliced, inside single quotes) | — |
| argv brace blocks `{ … }` | refused ("too many arguments"), so the nested command is a string | — |

Atomicity: with `-F`, `if-shell` evaluates the condition and inserts the chosen
branch right after itself in the same command-queue pass (no shell, no wait).
The single-threaded server runs it before any client attach or detach. This is
a claim from the tmux source; live case 8 models the gap.

## Implementation

1. **`.aitask-scripts/lib/agent_launch_utils.py`**: add next to
   `switch_to_pane_anywhere` (unchanged):
   - Splice regexes:
     - client name `[A-Za-z0-9/._-]+`, which excludes `#{},'` and whitespace
     - pid `[0-9]+`
     - ids `%[0-9]+` (pane), `\$[0-9]+` (session), `@[0-9]+` (window)
   - `_client_identity_condition(name, pid) -> str`: `helper_panes.all_of([
     "#{==:#{client_name},N}", "#{==:#{client_pid},P}"])`. It is a separate
     function so the live mutant can drop the pid half.
   - `switch_client_to_pane(pane_id, *, client, client_pid) -> str`. The
     result is `"moved" | "absent" | "skipped" | "failed"`:
     1. A malformed `pane_id` → `"failed"` (no call). A name or pid that
        fails its regex → `"skipped"` (it cannot be spliced, so it cannot be
        checked atomically; no call).
     2. `display-message -p -t <pane> '#{session_id}\t#{window_id}'`. A
        failure or malformed ids → `"failed"`. Otherwise
        `target = f"{sid}:{wid}.{pane}"`.
     3. The common branch for both stages is
        `then = "switch-client -c '<N>' -t '<target>' ; display-message -p MOVED"`.
        Every classification checks the exit status first: a nonzero exit is
        `"failed"`, whatever was printed. Success requires both exit 0 and a
        `MOVED` line.
        It is ONE full-target switch, which validates the pane before it moves
        anything.
     4. **Stage A, the client loop (tmux ≥ 3.4):**
        `["if-shell", "-F", "-t", pane_id, "#{==:#{L:#{?<ident>,1,}},1}", then, "display-message -p 'ABSENT:#{L:1}'"]`.
        Classify the result:
        - rc ≠ 0 → `"failed"`.
        - `MOVED` → `"moved"`.
        - `ABSENT:<non-empty>` → `"absent"`.
        - `ABSENT:` empty → stage B. The empty probe means tmux < 3.4, or no
          client attached at all.
        - Anything else → `"failed"`.
     5. **Stage B, the resolved client (best effort, any version):**
        `["if-shell", "-F", "-t", pane_id, <ident>, then, "display-message -p 'SKIPPED:#{client_name}'"]`.
        Classify the result:
        - rc ≠ 0 → `"failed"`.
        - `MOVED` → `"moved"`.
        - `SKIPPED:` with an empty name (no client resolved, so nobody is
          attached) → `"absent"`.
        - `SKIPPED:<name>` → `"skipped"`. tmux resolved another client; ours
          may or may not be attached. Which client tmux resolves depends on
          the dispatching process's context (`TMUX`/`TMUX_PANE`; see the
          table), and the docstring says so.
        - Anything else → `"failed"`.
   - The docstring carries the measured table and the version behaviour. Each
     stage is a single dispatch, so no check is ever separated from its switch.

2. **`.aitask-scripts/monitor/monitor_core.py`**:
   - In the cold-spawn tail (around line 6102), replace the re-check-and-switch
     pair:
     ```python
     if launch_client is not None and launch_client.session != session:
         jump = switch_client_to_pane(agent, client=launch_client.name,
                                      client_pid=launch_client.pid)
         if jump == "failed":
             warns.append("focus_failed")
         elif jump == "skipped":
             warns.append("focus_skipped")
     ```
     `"absent"` adds no warning, the same as today's failed re-check.
   - **Delete** `_sitrep_client_still_attached` and `_SITREP_CLIENTS_FORMAT`.
     They are now unused: the only production `list-clients` call is gone.
   - Rewrite the comment block above the jump, and import the helper next to
     `switch_to_pane_anywhere` (line ~73).
   - The `focused` and repair branches stay unchanged (follow-up in step 7).

3. **Warning vocabulary `focus_skipped`.** Add it to:
   - `.aitask-scripts/aitask_sitrep.sh` header (lines 27–29)
   - `.aitask-scripts/monitor/sitrep_open.py` docstring (line ~13)
   - `aidocs/framework/sitrep.md` line ~369

   `sitrep_cli.sitrep_open_message` already renders any warning generically
   ("Sitrep window opened (focus_skipped)", severity warning).

4. **`tests/test_control_routed_explicit_targets.py`**: the `TARGET_FREE
   ["list-clients"]` reason names the deleted sitrep re-check. Reword it to a
   neutral "server-wide: lists every client", or drop the entry if nothing
   routed uses it (decide by running the scanner).

5. **Unit tests.**
   - **`tests/test_multi_session_primitives.sh`**, a new tier. It is
     mock-based (subprocess patched like Tier 1b) and covers:
     - argv for stage A: an id read, then one `if-shell -F -t %42`. The
       condition starts with `#{==:#{L:` and ends with `,1}`. The then
       branch has exactly one `switch-client -c '/dev/pts/7' -t '$3:@5.%42'`
       followed by `display-message -p MOVED`, and **no** `select-window` or
       `select-pane`. The else branch is `ABSENT:#{L:1}`.
     - stage B runs only after an `ABSENT:` empty result. Its condition is
       `_client_identity_condition`, and its else branch is
       `SKIPPED:#{client_name}`.
     - every classification row in step 1. `ABSENT:L:1` (a 3.3a literal) →
       `"absent"`, never moved.
     - an unsafe name or pid (`/dev/pts/1,x`, `a'b`, `#{x}`, `1a`) →
       `"skipped"` with zero calls. A malformed pane (`=s:1`) → `"failed"`
       with zero calls.
     - `switch_to_pane_anywhere`'s existing assertions are unchanged.
   - **`tests/test_sitrep_window.py`**: patch `mc.switch_client_to_pane`
     (`self.jump` → `"moved"`) in `_SpawnFixture`. The cold-jump tests assert:
     - the helper is called with `("%42", client=…, client_pid="5150")`, with
       no `focus` and no `list-clients` calls
     - `"failed"` → `focus_failed`; `"skipped"` → `focus_skipped`;
       `"absent"` → no warning
     - the same-session, no-caller, control-client, no-select and
       unparseable-read cases → `jump` not called
     - the reused-pty, gone-initiator and unreadable-listing tests are
       replaced by the helper's own tests (primitives and live 9).
       `test_the_identity_is_rechecked_after_the_companion_spawn` becomes
       "the jump runs after the companion spawn".
     - `test_the_focus_follows_the_companion_spawn` follows `jump`.

6. **`tests/test_sitrep_window_select_live.sh`** (live; cases 1–7 keep their
   assertions):
   - **Version knob.** `AIT_LIVE_TMUX_BIN=<path>` puts a `tmux` shim for that
     binary first on `PATH` (in `$FIX`) before anything starts. The server,
     the `script` clients and the Python `TmuxClient` all resolve `tmux`
     through `PATH`. After the clients attach, a capability probe sets
     `HAS_CLIENT_LOOP` (`T display-message -p '#{L:x}'` non-empty). The run
     prints `NOTE: tmux <ver>, client loop: <0|1>`.
   - **Mutants rewired.** The old two-call code is copied verbatim into the
     driver as the control (it is deleted from production):
     - `NO_FIRST_FOCUS`: the first helper call is a no-op that returns
       `"moved"`.
     - `NO_PID_CHECK`: `alu._client_identity_condition` drops the pid half
       (the name-only identity), so stage A and stage B both get it.
     - `IMPLICIT_CLIENT`: the helper becomes
       `switch_to_pane_anywhere(pane)`, which names no client.
     - `TWO_CALL`: the helper becomes the copied t2338 logic: a
       `list-clients` name+pid check, then
       `switch_to_pane_anywhere(pane, client=name)`.
   - **`AIT_LIVE_REPLACE_IN_GAP=<spec>`** runs `_replace` at the last moment
     after the last identity read and before the switch. In the fix, it runs
     immediately before the helper (the check and the switch are one call).
     Under `TWO_CALL` it runs between that mutant's check and its switch.
   - **Case 8:** the initiator closes in the gap and a replacement attaches to
     D. The replacement is not moved, and the status is `spawned`. This holds
     on both versions: on 3.3a, stage B's pid guard refuses the replacement.
   - **Case 8X** (`TWO_CALL`): with a reused pty name the replacement IS moved
     (the control). Without reuse it prints `NOTE:`, as 6X does.
   - **Case 9**, which calls the helper directly against the real server:
     - **9a.** The right name with a wrong pid returns `"absent"` (≥ 3.4) or
       `"skipped"` (< 3.4). **The client is not moved on either version** (the
       3.3a review repro).
     - **9b.** The right name and pid with one terminal attached returns
       `"moved"`, and the client is on the pane on both versions (stage A on
       3.8, stage B on 3.3a).
     - **9c.** Two terminals: the initiator in A, and a second one in D. Each
       sub-case pins the dispatching context explicitly, by giving the helper
       call `TMUX`/`TMUX_PANE`. The helper's `_TMUX.run` subprocess inherits
       them.
       - **9c-i, the caller's context** (`TMUX` = A, `TMUX_PANE` = the caller
         pane; this is what `sitrep_open` runs with). The right pid returns
         `"moved"` on both versions, and only the initiator moves.
       - **9c-ii, D's context** (`TMUX` = D, `TMUX_PANE` = D's pane).
         - Precondition: under that same context,
           `if-shell -F -t <dest> 1 "display-message -p '#{client_name}'"`
           must name the SECOND terminal. If it does not, the run fails as a
           setup error instead of asserting.
         - ≥ 3.4: `"moved"`, and only the initiator moves (stage A does not
           depend on context).
         - < 3.4: `"skipped"`, and neither moves. This is the documented
           best-effort limit.
       - Then, in both contexts on both versions, a wrong pid moves neither.
     - **9d.** The destination dies between the lookup and the dispatch (a
       `_TMUX.run` wrapper kills it right after the id read; the window
       survives as a two-pane window). It returns `"failed"` and the client
       is still in A. A `break-pane` move gives the same result.
     - **9d control.** The same seam against a scratch copy of the pre-fix
       three-command branch leaves the client in the destination session on
       ≥ 3.4. This is the reviewer's repro, and it proves the seam bites.
   - Header comment: cases 8, 8X and 9 and the version knob.

7. **Follow-up** (from the t2338 note; out of scope, because the task says to
   keep other callers unchanged). In Step 8, create a task for the remaining
   implicit-client switches:
   - the `spawn_sitrep` `focused` branch (~6016) and repair branch (~6125),
     which can use `switch_client_to_pane` with the launch-time `_SitrepClient`
   - the monitor jump (~4589), which needs its own client source

   Record in it that `switch_to_pane_anywhere`'s three-call shape has the
   dead-destination partial move measured here.

8. **`aidocs/framework/sitrep.md`**: in the "Focus" bullet, describe the cold
   cross-session jump:
   - one guarded dispatch per stage: the client loop on ≥ 3.4, then a
     best-effort resolved-client check
   - an exact name+pid match, then one full-target switch
   - nothing moves when the identity cannot be checked, and the open warns
     `focus_skipped`
   - the < 3.4 limit is stated as context-dependent: the jump happens when the
     client tmux resolves for the caller's context is the initiator, which is
     the normal `sitrep_open` case

   Add `focus_skipped` to the warning list (line ~369) and a test-table pointer
   (live cases 8 and 9, `AIT_LIVE_TMUX_BIN`).

### Post-phase (risk mitigations)
1. [pin_jump_outcome_routing] In `tests/test_sitrep_window.py`, add a test that
   records calls in order for each helper outcome:
   - `moved` → `[jump]`, no warning
   - `absent` → `[jump]`, no warning
   - `skipped` → `[jump]` + `focus_skipped`
   - `failed` → `[jump]` + `focus_failed`

   Every outcome must make zero `list-clients` calls and zero
   `switch_to_pane_anywhere` calls on the cold path. It must pass.
2. [prove_mutant_controls_bite] Run `bash tests/test_sitrep_window_select_live.sh`
   as shipped (all green), then confirm each control goes red under its mutant:
   - X (`NO_FIRST_FOCUS`)
   - 3 and 4 (`ALWAYS_FOCUS`)
   - 5X (`IMPLICIT_CLIENT`)
   - 6X (`NO_PID_CHECK`)
   - 8X (`TWO_CALL`)
   - the 9d control

   Record a table (assertion | fix | mutant | pty reuse) in Final
   Implementation Notes. A run without pty reuse is "not exercised", never a
   pass.
3. [measure_old_tmux] Run the whole live file under
   `AIT_LIVE_TMUX_BIN=/tmp/aitask-2349-tmux.opQN0foR/usr/bin/tmux` (the real
   tmux 3.3a; skip with a note if it is gone). Required:
   - cases 1–6, 8 and 9 pass with their < 3.4 expectations
   - 9a never moves a client

   Record per-case outcomes. Record any 3.3a-only divergence in pre-existing
   cases (e.g. case 7's control-client read) as a measured fact: fix it in
   scope if this change causes it, otherwise report it for a follow-up. Never
   skip it silently.

## Verification

- `bash tests/test_multi_session_primitives.sh`
- `python3 -m unittest tests.test_sitrep_window`
- `bash tests/test_sitrep_window_select_live.sh`, both on tmux 3.8 and with
  `AIT_LIVE_TMUX_BIN=<3.3a>`
- `python3 tests/test_control_routed_explicit_targets.py`,
  `bash tests/test_no_raw_tmux.sh`, `bash tests/test_multi_session_monitor.sh`,
  `bash tests/test_sitrep_window_live.sh`,
  `python3 -m unittest tests.test_monitor_sitrep_harvest_close` (it reads
  `sitrep_open_message`). Also add one `sitrep_open_message` assertion for a
  `SITREP_WARN:focus_skipped` line to `tests/test_sitrep_window.py`.
- `shellcheck tests/test_sitrep_window_select_live.sh tests/test_multi_session_primitives.sh .aitask-scripts/aitask_sitrep.sh`

Step 9 (Post-Implementation): commit, then archive per the workflow.

## Risk

### Code-health risk: low
- Two guarded stages with their own output grammars (exit status first, then `MOVED`/`ABSENT:`/`SKIPPED:`) must be classified exactly. A loose parse could read a 3.3a literal or a partial run as success (pinned: rc ≠ 0 with `MOVED` printed is `"failed"`) · severity: low (residual — addressed by inline post-phase pin_jump_outcome_routing and the primitives classification rows) · → mitigation: inline post-phase pin_jump_outcome_routing
- Rewiring the live mutants (the old code copied into the driver) can leave a control that no longer bites · severity: low (residual — addressed by inline post-phase prove_mutant_controls_bite) · → mitigation: inline post-phase prove_mutant_controls_bite

### Goal-achievement risk: low
- tmux < 3.4: the guard is now exact (`0` measured on real 3.3a), and stage B's name+pid guard is atomic. With several terminals, a legitimate jump can be skipped (warned `focus_skipped`), as the user decided · severity: low (residual — measured by inline post-phase measure_old_tmux) · → mitigation: inline post-phase measure_old_tmux
- Destination pane dying or moving between the id lookup and the dispatch: the single full-target switch is used, measured on 3.8 and 3.3a, and pinned by 9d plus a control · severity: low · → mitigation: none (in the main design)
- Atomicity rests on tmux's single-threaded command queue (`if-shell -F` inserting its branch in the same pass), a source-level claim. Case 8 models the gap but cannot prove the absence of interleaving · severity: low · → mitigation: none

### Planned mitigations
- timing: post-phase | name: pin_jump_outcome_routing | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: exact classification of the two guarded stages | desc: unit-pin each helper outcome's warning and that the cold path makes no list-clients / switch_to_pane_anywhere call (was pin_fallback_routing; the fallback no longer exists)
- timing: post-phase | name: prove_mutant_controls_bite | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: rewired live mutants losing their bite | desc: run every live mutant control red/green and record the per-assertion table
- timing: post-phase | name: measure_old_tmux | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: tmux < 3.4 guard behaviour | desc: run the live file against the real tmux 3.3a binary and record per-case results (was 'after' spawn measure_old_tmux_L_fallback; inlined after review because a real 3.3a binary is available)
