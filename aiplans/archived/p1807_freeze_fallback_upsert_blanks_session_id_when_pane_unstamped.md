---
Task: t1807_freeze_fallback_upsert_blanks_session_id_when_pane_unstamped.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1807 — Freeze fallback upsert blanks `codeagent_session_id` when the pane is unstamped

## Context

`bash tests/test_restore_flows_live.sh` failed Case 1 on a cold tmux server
(`RESTORE_FAILED:<rid>|no_session`) and passed on re-run. Mechanism (reproduced
in t1806 with `FAKE_AGENT_HOOK_DELAY=3`):

1. `make_frozen` launches the fake agent, `sleep 0.3`, upserts the record with
   `--session-id sess-orig`, then freezes. On a cold server the SessionStart
   hook has not yet stamped `@aitask_record` / `@aitask_agent_session`.
2. `agent_freeze._resolve_record` (`.aitask-scripts/lib/agent_freeze.py:245`)
   takes path 2 (no stamp) and upserts with `--session-id ""` (pane option
   unset). The store selects the fixture's record by pane identity, and
   `_apply_upsert_fields` (`.aitask-scripts/lib/agent_sessions.py:712`) treats
   `""` as a value (`if session_id is not None`), so `sess-orig` becomes `""`.
3. Restore sees an empty id → `no_session`.

Two layers: a **product** defect of the same class as t1802 (a blank value
overwrites a good stored one), and a **fixture** race (`sleep 0.3` instead of
waiting for the hook's stamp).

Blast-radius check done in planning: the only callers that pass a session id to
the store are the SessionStart hook (which never sends a blank — contract 4,
`aitask_session_hook.sh:86`) and the freeze fallback. No test relies on a blank
clearing the id. The `restore_of` resume-mismatch comparison
(`agent_sessions.py:792`, `(session_id or "") != rec.codeagent_session_id`) runs
**before** `_apply_upsert_fields` and is unaffected.

**Why the fixture must fail loudly once the product is fixed.** After step 1 the
unstamped fallback no longer blanks `sess-orig`. A `make_frozen` whose stamp wait
merely timed out would therefore let a case pass through path 2 while proving
nothing about the ordering the fixture exists to establish. So a missed stamp
must fail the case, not warn. Every caller reads `make_frozen` through
`read -r RID PANE < <(make_frozen …)`, and process substitution discards the
function's exit status, so returning non-zero is not enough on its own. Two facts
make detection reliable. First, `read` returns 1 on empty input. Second, this
suite uses the file-backed counters (`assert_counters_init`, line 59), whose
file is addressed by shell variables that a process-substitution child inherits.

I confirmed that no case disables the hook for its **first** agent:
- every `FAKE_AGENT_NO_HOOK` / `FAKE_AGENT_HOOK_DELAY` / `FAKE_AGENT_SESSION` is
  set via `agent_env` (sourced only by the fixture `claude` wrapper, i.e.
  restore relaunches) or on an explicit `respawn-pane` (line 275);
- every such call comes after that case's `make_frozen`;
- `make_agent_window` runs `$FAKE_AGENT` directly.

A mandatory stamp is therefore safe for all 16 callers.

Mode: current branch (profile `fast`), no worktree.

## Implementation

1. **Store rule — `.aitask-scripts/lib/agent_sessions.py` `_apply_upsert_fields`.**
   Change `if session_id is not None:` → `if session_id:`. Update the docstring
   so the "a blank means not supplied" paragraph covers both `agent_string`
   (t1802) and `session_id` (t1807): the freeze engine's fallback upsert sends
   the pane's `@aitask_agent_session`, which is unset until the hook's step 9, and
   the store selects an existing record by pane identity, so a blank would
   downgrade a resumable record to re-pick-only. Note that the `restore_of`
   resume comparison still reads a blank as a mismatch (it runs before this
   function), so this rule changes nothing on the ack path. The create path
   (`_create` → `_apply_upsert_fields`) is unaffected: the field defaults to `""`.

2. **Hook comment — `.aitask-scripts/aitask_session_hook.sh`** (comments only;
   code and the `empty session_id` stderr text are unchanged, since
   `tests/test_session_hook.sh:234` asserts it). Contract 4 (lines 23-24) and
   the block at 80-85 currently say the store would overwrite a good id with
   `""`; after step 1 that is false. Reword: the store now ignores a blank id
   on an ordinary update, but the hook's no-op is still required because on a
   restore ack the store compares `(session_id or "")` against the stored id
   before applying fields, so a blank would persist `<nonce>:session_mismatch`
   and abort a legitimate restore. It also avoids an upsert and stamp for a
   session that could never be resumed.

3. **Freeze caller comment — `.aitask-scripts/lib/agent_freeze.py` `_resolve_record`.**
   Add a short comment by the `--session-id` / `--agent-string ""` args: both may
   be blank here, and the store treats a blank for either as "not supplied", so
   a record already selected by pane identity keeps its id and agent string.
   (No behavior change; this is the call site that relies on the rule.)

4. **Store unit tests — `tests/test_agent_sessions_identity.py`.**
   Add `BlankSessionIdTests(_UpsertTestCase)` beside `BlankAgentStringTests`:
   - `test_a_blank_update_keeps_the_stored_session_id`: `up(session_id="sess-orig")`,
     then `up(session_id="")` → `UPSERTED:<rid>|updated`, and
     `codeagent_session_id == "sess-orig"`.
   - `test_a_non_blank_update_still_replaces_it`: `sess-orig` → `sess-new` wins.
   - In the class that defines `_restoring` (around line 250), add
     `test_a_blank_resume_ack_is_still_a_mismatch`: a `resume`-mode restoring
     record with `session_id="sid-1"`, acked with `session_id=""`, still raises
     `SessionMismatch` and persists `<nonce>:session_mismatch`. This pins that
     the new rule did not reach the ack comparison.

5. **Freeze unit test — `tests/test_agent_freeze.py` `RecordResolutionTests`.**
   Add `test_an_unstamped_pane_keeps_the_stored_session_id`. Seed the setUp
   record with `codeagent_session_id = "sess-orig"` (via `agent_sessions.upsert`
   on `self.store.sf` with `session_id="sess-orig"`, pane `AGENT_PANE`). Set the
   pane's `RECORD_OPTION` and `AGENT_SESSION_OPTION` to `""`, then run
   `freeze_pane(AGENT_PANE)`. Assert:
   - `result.ok`;
   - `result.record_id == self.rid`, since the fallback selected the existing
     record by pane identity and did not create a new one;
   - the pane stamp names `self.rid`;
   - `self.rec().codeagent_session_id == "sess-orig"`.
   The fake store (`_FakeStore._dispatch` "upsert", line 278) calls the real
   `agent_sessions.upsert` with `session_id=` from the argv, so this exercises
   the real rule end to end through the engine.

6. **Shared fixture helper — `tests/lib/frozen_fixtures.sh`.**
   Move `wait_for_record_stamp` there from `tests/test_frozen_agents_acceptance.sh:340`,
   with an optional poll budget: `wait_for_record_stamp <pane> [tries]`. It
   defaults to `$FROZEN_WAIT_TRIES`, polls `record_of_pane` every 0.1 s, echoes
   the id and returns 0, or returns 1 on timeout. Place it with the other
   `wait_*` helpers.

7. **Acceptance suite — `tests/test_frozen_agents_acceptance.sh`.**
   Delete the local `wait_for_record_stamp` definition (lines 339-349). At its
   two call sites (lines 356 and 1168), pass `150` explicitly so the suite keeps
   its current 15 s budget. The acceptance suite's own behavior is unchanged.

8. **Restore-flows fixture — `tests/test_restore_flows_live.sh` `make_frozen`.**
   This step fails definitively and is guarded at every caller. Rewrite
   `make_frozen` so that, in this order:
   1. After `make_agent_window`, it runs
      `hook_rid="$(wait_for_record_stamp "$agent")"`. This replaces the
      `sleep 0.3` at line 154.
   2. It runs the fixture upsert as today, but **captures** its output instead
      of discarding it, and requires exactly `UPSERTED:$hook_rid|updated`. This
      proves the fixture seeded `sess-orig` onto the hook's own record, after
      the hook wrote it.
   3. It freezes, then requires `record_of_pane "$agent"` to still equal
      `$hook_rid`. This proves the freeze took path 1 on the stamped record,
      not the fallback.
   4. Only on success does it `printf '%s %s\n' "$hook_rid" "$agent"`.

   On any failure — no stamp within the budget, an unexpected upsert
   disposition, or a changed stamp after the freeze — it:
   - calls `assert_record_fail`, which persists through the file-backed counters
     from inside the process-substitution child, so the footer verdict fails
     even at a caller missing its guard;
   - writes `FAIL: make_frozen(<window>): <reason>` to **stderr**, because
     stdout is the `read` channel;
   - kills its own window, so a half-built agent does not leak into later
     cases' `restore --all` and reconcile counts;
   - `return 1` with **nothing on stdout**.

   A comment on the function states this contract: the function prints nothing
   and records a FAIL when setup fails, and callers must guard because process
   substitution drops the exit status. It also records why the order is wait,
   then upsert, then freeze:
   - the hook's own upsert must land first, because the fake agent reports
     `fakesess-$$` and would otherwise overwrite `sess-orig`;
   - the freeze must see a stamped pane.

   Next, change **all 16 call sites** (lines 171, 221, 261, 302, 347, 382, 408,
   448, 479, 529, 547, 568, 595, 626, 658 and 667) from
   `read -r RID PANE < <(make_frozen …)` to
   `read -r RID PANE < <(make_frozen …) || exit 1`. Case 13 reads into
   `RID_OK PANE_OK` and `RID_BAD PANE_BAD`, and gets the same guard. `read`
   fails on the empty stream, so the guard ends that case's `( … )` subshell
   before it can act on an empty `RID`.

   Add `wait_for_record_stamp` to the shared-helper list in the comment at
   lines 128-130. Leave the `sleep 0.3` in Case 7 (line 417) alone: it follows
   a `kill-window` and is unrelated.

Post-implementation: Step 9 of the task workflow (build verification, archival).
No merge, since this is current-branch mode.

## Verification

- **Pre-fix control (product).** Add the tests from steps 4 and 5 first. Run
  them with step 1 reverted (stash `agent_sessions.py`), and confirm these two
  fail with `''` in place of `sess-orig`:
  - `test_a_blank_update_keeps_the_stored_session_id`
  - `test_an_unstamped_pane_keeps_the_stored_session_id`

  Then restore step 1 and confirm they pass. The mismatch-pin and non-blank
  tests pass both ways; they are guards, not reproductions.
- **Guard control (fixture).** Watch the step-8 guard fail. Run
  `FROZEN_WAIT_TRIES=5 FAKE_AGENT_HOOK_DELAY=3 bash tests/test_restore_flows_live.sh`,
  where the hook arrives after a 0.5 s budget. Expect all of the following:
  - every case logs `FAIL: make_frozen(…): no @aitask_record stamp…` on stderr;
  - each case exits at its guard, with no downstream assertion run against an
    empty `RID`;
  - the footer reports `SOME TESTS FAILED`;
  - the suite exits non-zero.

  This demonstrates, rather than assumes, that the process-substitution
  failure reaches the verdict.
- Unit modules:
  `python3 -m unittest tests.test_agent_sessions_identity tests.test_agent_freeze tests.test_agent_sessions tests.test_agent_sessions_contract_call_sites tests.test_agent_restore -v`.
- Hook contracts: `bash tests/test_session_hook.sh`.
- Live suites, which exercise the fixture and shared-lib change:
  - `bash tests/test_restore_flows_live.sh`, run twice back to back; the first
    run gets a cold isolated server. Both runs must pass.
  - `bash tests/test_frozen_agents_acceptance.sh`
  - `bash tests/test_freeze_engine_live.sh`
- Hook-delay stress: `FAKE_AGENT_HOOK_DELAY=3 bash tests/test_restore_flows_live.sh`,
  where the default 12 s budget exceeds the 3 s delay. Case 1 must pass. The
  delay also slows restore acks, so if another case fails, run the same command
  on the pre-change tree before attributing it to this change.
- Full Python suite:
  `set -o pipefail; bash tests/run_all_python_tests.sh 2>&1 | tail -5`, reading
  the final `PYTHON SUITE:` line.
- `shellcheck .aitask-scripts/aitask_session_hook.sh`; `bash -n` on the three
  edited test shell files.

## Risk

### Code-health risk: low
None identified. The store rule change is one condition, mirrors the t1802 rule
beside it, and its only affected caller is the freeze fallback. I verified that
the hook never sends a blank, and that the restore-ack comparison precedes the
field write; a test pins the latter. The fixture change moves an existing helper
into the shared lib, and the acceptance suite keeps its budget. The 16
call-site guards are mechanical, and the guard control exercises them.

### Goal-achievement risk: low
None identified. Both layers the task names are fixed, and each has a regression
test. The product fix has a pre-fix-controlled unit test at both the store and
freeze-engine layers. The fixture now fails definitively whenever the ordering
it exists to establish does not hold. The guard control exercises that failure
path, and the hook-delay stress run exercises the success path.

## Implementation Progress (2026-09-14)

- Steps 1–8 implemented as planned.
- **Pre-fix control (product).** Run against the unfixed store:
  - exactly the two reproductions failed with `'' != 'sess-orig'`:
    `test_a_blank_update_keeps_the_stored_session_id` and
    `test_an_unstamped_pane_keeps_the_stored_session_id`;
  - the five guard tests passed.

  After the fix, the five named modules pass: 223 tests OK.
- Hook contracts (`tests/test_session_hook.sh`): 66/66.
- **Deviation — live suites not run in-session.** This session runs inside the
  `-L ait` tmux server. `require_clean_ait_server` refuses (exit 2,
  "cannot run from inside a tmux session") for:
  - `test_restore_flows_live.sh`, run twice;
  - `test_frozen_agents_acceptance.sh`;
  - `test_freeze_engine_live.sh`;
  - the guard control;
  - the stress run.

  The only override (`AIT_LIVE_TMUX_TEST_FORCE=1`) is documented as
  CI-box-only, because pane-died cleanup hooks run raw `tmux`, so it was not
  used. The user chose: a scratch harness now, plus a manual-verification
  follow-up for the live suites run outside tmux.
- **Substitute evidence — scratch harness** (scratchpad only, not committed). It
  sources the real `tests/lib/asserts.sh` and `tests/lib/frozen_fixtures.sh`,
  plus `make_frozen_fail` / `make_frozen` extracted from the working tree, with
  tmux, store and freeze stubbed. Result: 25/25 checks passed.
  - The success path returns the hook's record, and parses the last upsert
    line.
  - Each failure — no stamp, wrong seed disposition, re-stamp after the freeze:
    - prints nothing on stdout;
    - records exactly one FAIL through the file-backed counters, from inside
      the process-substitution child;
    - fails the suite-shaped verdict;
    - kills the half-built window;
    - never reaches the guarded caller's body.
  - An unguarded caller still fails the verdict.
  - Pre-fix control: HEAD's `make_frozen` proceeds silently without a stamp,
    and its verdict passes.
- **Deviation — stress delay.** The planned `FAKE_AGENT_HOOK_DELAY=3` was
  changed to `1`. A 3 s delay equals the suite's `AITASKS_RESTORE_ACK_GRACE=3`,
  so it would push every restore ack past the grace and fail cases for reasons
  unrelated to this change. The stress run did not execute either (tmux guard),
  so it moves to the live follow-up with delay 1.

## Post-Review Changes

### Change Request 1 (2026-09-14 23:43)
- **Requested by user:** `make_frozen` discarded the freeze command's output
  and exit status, and only checked that `@aitask_record` was unchanged. A
  freeze that fails at capture or `freeze-begin` never re-stamps the pane, so it
  handed the caller a record and pane with no frozen setup behind them. Check
  the freeze's status and its `FROZEN:$hook_rid` result, and route a failure
  through `make_frozen_fail` before the stamp check.
- **Verified before changing:** a successful single-pane freeze prints exactly
  `FROZEN:<rid>` (`agent_freeze.py:441`). Failures print
  `FREEZE_FAILED:capture|…` / `FREEZE_FAILED:begin|…` / `FREEZE_SKIPPED:…`, and
  `main()` exits 1 unless every result is ok. `aitask_frozen.sh` `exec`s the
  engine, so that status is the script's own.
- **Changes made:** `make_frozen` now captures the freeze's stdout and status.
  It fails through `make_frozen_fail` on a non-zero exit ("the freeze failed
  (…)"), or when no line is exactly `FROZEN:$hook_rid` ("the freeze did not
  report FROZEN:…"). Only then does it run the unchanged stamp check. The
  function's comment now lists the three post-seed checks and says why the stamp
  alone cannot tell a failed freeze from a successful one.
- **Verification:**
  - The scratch harness gained two scenarios: a freeze exiting 1 with
    `FREEZE_FAILED:begin|…`, and a freeze exiting 0 but reporting
    `FROZEN:<other record>`. Result: 35/35 checks. Each new scenario stops at
    the caller's guard, records exactly one FAIL, fails the verdict, kills the
    window, and names its reason on stderr.
  - Pre-change control: the previous `make_frozen` was rebuilt, and confirmed
    to still run the freeze with `>/dev/null 2>&1`. On the same injected freeze
    failure it proceeds silently: it reaches the body with `FAIL=0` and exits 0.
  - `bash -n` passes, and `shellcheck -S warning` reports only the four
    pre-existing `SC2034` warnings.
- **Files affected:** `tests/test_restore_flows_live.sh`.

### Change Request 2 (2026-09-15 17:49)
- **Requested by user:** `make_frozen_fail` killed only the test window. A
  freeze that fails after `freeze-begin` (e.g. at commit) can leave the record
  `freezing` in the shared store. With its pane gone, a later reconcile commits
  it `frozen`, and a later `restore --all` or reconcile assertion can observe
  the failed fixture as a real record. Clean up the fixture's owned record(s) on
  the failure path before killing the window, and cover a transitional freeze
  failure in the harness.
- **Verified before changing:**
  - The store's `drop` without `--nonce` is the unconditional form: it removes
    a record in any state and prints `DROPPED:<id>`. It is the form the suite's
    own `drop_record` helper already uses.
  - I checked this against real code: after `freeze_begin` the record was
    `freezing` with a lease nonce held, and the nonce-less drop still returned
    `DROPPED:<id>`, leaving zero records.
  - The engine-level `aitask_frozen.sh drop` is the wrong tool here. It would
    refuse a held lease (`DROP_REFUSED:…|in_flight`), and it kills stand-in
    panes.
- **Changes made:**
  - `make_frozen_fail <window> <reason> [record_id...]` drops each given
    record id, de-duplicated, BEFORE killing the window. A drop whose answer is
    not `DROPPED:<id>` is appended to the failure reason
    ("record <id> was NOT dropped (…)"), never swallowed.
  - `make_frozen` passes the hook's record at every failure site after the
    stamp is known. It additionally passes the record a seed CREATED (parsed
    from `UPSERTED:<id>|…`) on the bad-seed path, and the foreign stamp on the
    re-stamp path.
  - The stamp-timeout path owns no known record, so it drops nothing: killing
    the window stops the agent, and with it the hook.
  - Both contract comments now describe the cleanup and why it goes first.
- **Verification:**
  - The scratch harness stubs now log store and tmux calls to one shared event
    log, so the order of a drop and a kill is observable. Result: 67/67 checks.
    - Every post-stamp failure drops the hook's record, and the drop precedes
      the kill. The failures covered are: bad seed, freeze exiting 1 at
      `begin`, freeze exiting 1 at `commit` (the transitional case), a wrong
      `FROZEN:` line, and a re-stamp.
    - The bad seed also drops the seed-created record, and the re-stamp also
      drops the stamped record.
    - A commit failure drops exactly one record.
    - A refused drop is reported in the reason.
    - The success path drops and kills nothing.
    - The stamp timeout drops nothing.
  - Pre-change control: the version from before this change was snapshotted
    and run on the same commit-stage failure. The case still fails, but the
    record is left behind (no drop) and only the window is killed.
  - `bash -n` passes, and `shellcheck -S warning` reports only the four
    pre-existing `SC2034` warnings.
- **Files affected:** `tests/test_restore_flows_live.sh`.

## Final Implementation Notes
- **Actual work done:** All eight plan steps, plus two post-review change
  requests to the fixture.
  - **Product:** `_apply_upsert_fields` (`agent_sessions.py`) applies
    `session_id` only when it is non-blank. Its docstring states the rule, and
    why the restore-ack comparison is unaffected. Comment-only updates went into
    `aitask_session_hook.sh` (contract 4 and the blank-id block) and
    `agent_freeze._resolve_record`.
  - **Tests:**
    - `BlankSessionIdTests`: a blank update keeps the stored id, and a
      non-blank one replaces it.
    - `RestoreAckTests.test_a_blank_resume_ack_is_still_a_mismatch`.
    - `RecordResolutionTests.test_an_unstamped_pane_keeps_the_stored_session_id`.
  - **Fixture:**
    - `wait_for_record_stamp [tries]` now lives in
      `tests/lib/frozen_fixtures.sh`; the acceptance suite passes `150`.
    - `make_frozen` runs stamp, then seed (`UPSERTED:<hook>|updated`), then
      freeze (exit 0 and `FROZEN:<hook>`), then checks the stamp is unchanged.
    - Every failure goes through `make_frozen_fail`. It records a FAIL, drops
      the owned records first, gives the reason on stderr, kills the window,
      and prints nothing on stdout.
    - All 16 callers end with `|| exit 1`.
- **Deviations from plan:**
  1. The live suites could not run in-session. This session lives in the
     `-L ait` server, and `require_clean_ait_server` refuses; the CI-only
     override was not used. By the user's choice, a scratch harness
     substituted, with tmux, store and freeze stubbed and the real asserts and
     fixtures libraries. A manual-verification follow-up carries the live runs.
  2. The stress delay changed from 3 to 1, because 3 s equals
     `AITASKS_RESTORE_ACK_GRACE`.
  3. Change Request 1: check the freeze's exit status and its `FROZEN:` result.
  4. Change Request 2: drop the owned records on the failure path.
- **Issues encountered:**
  - The shell is zsh, so `${PIPESTATUS[0]}` read empty. Verdicts were re-read
    from logs, without pipes.
  - BSD `grep` did not match the `$` in `"$agent"` literally in a pattern, and
    reported a misleading 0 in the CR1 control. `grep -F` confirmed the
    control function.
- **Key decisions:**
  - Fix at the store rather than by omitting `--session-id` at the freeze
    caller. This mirrors t1802, protects any future blank sender, and the only
    affected caller was verified.
  - The fixture's failure path uses the unconditional, nonce-less store drop.
    The exited freeze coordinator's lease makes the leased form refuse, and
    `aitask_frozen.sh drop` also refuses a held lease.
  - The stamp-timeout path drops nothing: no record is known, and killing the
    window stops the agent and its hook.
- **Upstream defects identified:** None
- **Verification summary:**
  - Unit modules: 223 OK.
  - Hook contracts: 66/66.
  - Full Python suite: PASSED, 7440 tests, unittest runner.
  - Scratch harness: 67/67, including the HEAD, pre-CR1 and pre-CR2 controls.
  - Live suites: pending the manual-verification follow-up.
