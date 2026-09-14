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
