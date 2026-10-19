---
Task: t2066_retire_mark_after_replaced_lease.md
Base branch: main
Output branch: main
---

# t2066 — Retire the attempt mark after a replaced lease nonce

## Context

t2045 made `agent_freeze._reconcile_restoring` retire a recovered restore's
marks after a successful `restore-confirm`, via
`frozen_ops.retire_restore_marks(pane_id, record_id, coordinator_nonce)`. The
attempt mark's value (`<id>:<nonce8>`) is derived from the PRE-lease
`rec["op_nonce"]`. If an EARLIER reconcile pass took the lease on the same
`restoring` record and then failed to settle it (`RECONCILE_FAILED` from a store
error on `restore-confirm` or on the abort path), `op_nonce` is that dead pass's
nonce. The next pass retires the stamp but derives the wrong mark value, so the
mark stays. The live, tracked pane then reads as a restore survivor of its own
record (`frozen_ops.find_restore_survivors`) whenever no stand-in is mounted.
That blocks drop/restore/reopen.

Fix: after the nonce-derived retire, recover the mark from the pane itself and
clear it if it claims this record. The clear uses one compound `if-shell -F`
dispatch: the mark value AND `pane_pid == launch_pid`. This keeps the t1875
recycled-`%N` rule.

## Implementation

1. **`.aitask-scripts/lib/agent_frozen_ops.py`**: add a new primitive
   `clear_restore_attempt_claiming(pane_id, record_id, pane_pid)` next to
   `clear_restore_attempt` (around l.611):
   - Return early on an empty `pane_id`, on `pane_pid <= 0`, or on a
     `record_id` that is not 8 hex characters (same guard style as
     `clear_stamp_if`).
   - Read `facts = window_facts(pane_id)`. A `None` (unreachable) or `{}`
     (gone) result is a no-op.
   - `mark = facts.get("mark", "")`. Skip the clear unless
     `restore_attempt_record("", mark) == record_id`. The empty window name is
     deliberate: only the MARK is recovered, and that helper returns an id only
     for a `^hex8:hex8$` value. That also keeps the value safe to put into a
     format.
   - Dispatch one guarded unset:
     ```python
     cond = (f"#{{&&:#{{==:#{{{RESTORE_ATTEMPT_OPTION}}},{mark}}},"
             f"#{{==:#{{pane_pid}},{pane_pid}}}}}")
     run(["if-shell", "-F", "-t", pane_id, cond,
          f"set-option -pu -t {pane_id} {RESTORE_ATTEMPT_OPTION}"])
     ```
   - The docstring explains:
     - why the read value is re-checked inside the dispatch (a server restart
       between the read and the unset can recycle `%N`);
     - why `pane_pid` is checked inside the same dispatch rather than in Python;
     - that this is the recovery half of `retire_restore_marks` for a replaced
       `op_nonce` (t2066).
   - The pid half is enforced ONLY in the dispatch, never as a Python
     pre-check. That way the negative control below exercises the dispatch
     guard and not a shortcut.

2. **`.aitask-scripts/lib/agent_freeze.py`** `_reconcile_restoring`:
   - Add a local `_retire_marks(pane_id)` closure next to
     `_abort_back_to_frozen`. It calls
     `frozen_ops.retire_restore_marks(pane_id, record_id, coordinator_nonce)`
     and then `frozen_ops.clear_restore_attempt_claiming(pane_id, record_id,
     launch_pid)`.
   - Replace both existing `retire_restore_marks` calls (the rollout confirm
     at l.1277 and the liveness confirm at l.1291) with `_retire_marks(
     observed.pane_id)`.
   - Rewrite the "Residual (t2045)" comment at l.1207-1212. The nonce-derived
     value covers the normal case. A replaced nonce (earlier failed lease) is
     recovered from the pane under the compound guard (t2066). The pid half is
     what keeps the recovery to the pane this record now tracks.
   - When the derived value already matched, the mark is gone by the time of
     the read, so the fallback is a read plus a no-op. That costs one extra
     `display-message` per confirm and nothing else.
   - The coordinator (`agent_restore`) is unchanged: it holds its own nonce.

3. **`tests/test_agent_freeze.py`** `_FakeTmux._if_shell`: evaluate compound
   conditions.
   - Add `_AND = re.compile(r"^#\{&&:(.*)\}$")` and a `_cond_holds(cond,
     pane)` method. On `&&` it splits the body at depth-0 commas (brace-aware)
     and asserts exactly 2 operands. tmux's `&&` is binary, so anything else
     fails loudly. It then recurses. The `==` leaf keeps today's `_COND` regex
     and its assert.
   - `_if_shell` calls `_cond_holds(args[-2], pane)` in place of the inline
     match. Branch execution is unchanged. Update the docstring.

4. **`tests/test_agent_freeze.py`** `ReconcileRestoringTests`: add a t2066
   block after the t2045 block.
   - Helper `_replaced_by_a_failed_pass()`. It builds the shape with the real
     machinery, not by setting a field:
     1. `_abandoned_and_marked()`: stamp plus the N1 mark, coordinator dead.
     2. Set `self.store.fail_verbs["restore-confirm"] = 1`, then run
        `_recover(...)` and assert `RECONCILE_FAILED`. That is a real
        `lease-take` minting N_dead.
     3. Clear `fail_verbs`, then age the dead pass's lease (`op_owner_pid`
        set to a dead pid, `op_started_at` to an old time).
     4. Assert the precondition: `snapshot["op_nonce"] == N_dead != N1`, and
        the pane still carries `restore_attempt_value(rid, N1)`.
     5. Return `(n1, n_dead, snapshot)`.
   - `test_a_replaced_nonce_still_retires_the_attempt_mark`, run for
     `evidence` in miss and match (liveness and rollout confirm):
     - the result is `LIVE:<rid>|…`;
     - the stamp and the mark are both `""`;
     - `find_restore_survivors(rid) == []`;
     - `freeze_pane` returns `FROZEN:<rid>`.
     Run against the pre-fix code first (red proof): the mark assertion must
     fail there.
   - Negative control `test_a_replaced_nonce_keeps_another_records_mark`: the
     pane's mark is `0badf00d:12345678`, and that mark is kept. This covers the
     Python-side claim check.
   - Negative control `test_a_recycled_pane_pid_keeps_the_mark`: wrap
     `agent_frozen_ops.window_facts` so that, after the real read, it sets the
     pane model's `pane_pid` to `31337`. That models a server restart between
     the read and the dispatch. The record's mark is kept. This covers the
     pid half of the dispatch guard.
   - Negative control `test_a_mark_swapped_after_the_read_is_kept`: the same
     wrapper changes the mark to `0badf00d:12345678` after the read, and the
     new mark is kept. This covers the mark half of the dispatch guard.
   - Each wrapper fires once, on its first call. It is installed with
     `self._patch(agent_frozen_ops, "window_facts", …)`.

### Post-phase (risk mitigations)

1. [probe_compound_condition_live] Probe the exact condition against real
   tmux, on a private server only.
   - Start the server with `tmux -L t2066probe -f /dev/null new-session -d`.
     Never the default socket, and never `kill-server` without `-L`.
   - Set `@aitask_restore_attempt=deadbeef:12345678` on its pane and read its
     `#{pane_pid}`.
   - Build the condition with the SAME f-string as
     `clear_restore_attempt_claiming`. Import the module, or print the built
     condition from a stubbed `run`.
   - Run `if-shell -F -t <pane> "<cond>" "set-option -pu -t <pane>
     @aitask_restore_attempt"` three times:
     - (a) matching mark and the real pid → the option is now empty;
     - (b) after re-setting the mark, matching mark and pid+1 → the mark
       survives;
     - (c) a mismatching mark value and the real pid → the mark survives.
   - Finish with `tmux -L t2066probe kill-server`.
   - Record the `tmux -V` version and the three outcomes in the Final
     Implementation Notes. If (a) fails, stop and report: the fake would be
     modelling a condition tmux does not honour.

## Verification

- `python3 -m pytest tests/test_agent_freeze.py -q`, or `python3 -m unittest
  tests.test_agent_freeze` if pytest is absent. Whole file green.
- Red proof: run the new positive test against the pre-fix
  `agent_freeze.py`, in a scratch copy and never in the shared worktree. The
  mark assertion fails there.
- Mutants, applied in a scratch copy of `.aitask-scripts/lib` and `tests/`
  (never in the shared dirty worktree):
  - drop the `pane_pid` half of the compound condition → the recycled-pid
    control fails;
  - drop the Python claim check → the other-record control fails;
  - drop the mark half → the swapped-mark control fails.
- Related suites:
  - `tests/test_agent_restore.py`
  - `tests/test_agent_frozen_ops*.py`, if present
  - `bash tests/run_all_python_tests.sh --test-dir tests`: read only the final
    verdict line, with `set -o pipefail`.
- `bash tests/test_no_raw_tmux.sh`: the new dispatch goes through `run`, the
  gateway.

## Step 9

Post-implementation: commit the code, archive the task and plan via the
standard Step 9 flow (current branch, no merge).

## Risk

### Code-health risk: low
- None identified.

### Goal-achievement risk: low
- The compound `#{&&:#{==:…},#{==:…}}` condition is only checked against the
  test fake. If real tmux evaluated it differently, the clear would silently
  never fire. That is the fail-safe direction: the mark stays, as before the
  fix. · severity: low (residual — addressed by inline post-phase
  probe_compound_condition_live) · → mitigation: inline post-phase
  probe_compound_condition_live

### Planned mitigations
- timing: post-phase | name: probe_compound_condition_live | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — compound tmux condition only checked against the fake | desc: Evaluate the exact compound if-shell condition on a private-socket tmux server (match, pid mismatch, mark mismatch)

## Final Implementation Notes
- **Actual work done:** All four planned steps implemented as written.
  - `agent_frozen_ops.clear_restore_attempt_claiming(pane_id, record_id, pane_pid)`
    reads the pane's mark via `window_facts`. It proceeds only when
    `restore_attempt_record("", mark) == record_id`. It then dispatches one
    `if-shell -F` with
    `#{&&:#{==:#{@aitask_restore_attempt},<mark>},#{==:#{pane_pid},<pid>}}`.
  - `_reconcile_restoring` gained a `_retire_marks()` closure. It runs the
    nonce-derived `retire_restore_marks` and then the new fallback (guarded on
    `launch_pid`). It is used by both the rollout and the liveness confirm
    branches.
  - `_FakeTmux._cond_holds` evaluates binary `#{&&:A,B}` with a brace-aware
    split.
  - Five new tests (one positive with two subtests, three negative controls).
- **Deviations from plan:** None.
- **Issues encountered:** None. The live suites `test_freeze_engine_live.sh`
  and `test_restore_flows_live.sh` refuse (exit 2) on this box because live
  tmux sessions are running. They were not forced and were not run.
- **Key decisions:**
  - The pid half is enforced only inside the dispatch, never as a Python
    pre-check. That way the recycled-pid control exercises the dispatch guard.
  - The fallback runs after the derived retire, so on a normal confirm it is a
    read plus a no-op.
- **Verification evidence:**
  - Red proof: a pre-fix copy fails the positive test (`find_restore_survivors`
    returns the tracked pane).
  - Mutants in isolated scratch copies:
    - drop the pid half → only `test_a_recycled_pane_pid_keeps_the_mark` fails;
    - drop the claim check → only
      `test_a_replaced_nonce_keeps_another_records_mark` fails;
    - drop the mark half → only `test_a_mark_swapped_after_the_read_is_kept`
      fails.
  - `test_agent_freeze.py`: 140 passed.
  - Restore/frozen_ops/reopen tests: 262 passed.
  - `test_no_raw_tmux.sh`: passed.
  - Full suite: `PYTHON SUITE: PASSED (runner=pytest, exit=0)`.
- **probe_compound_condition_live (inline post-phase):** tmux 3.8, private
  socket `-L t2066probe`, killed afterwards. The condition was built by the real
  function with a stubbed `run`.
  - (a) mark and pid match → mark cleared;
  - (b) pid+1 → mark kept;
  - (c) mismatching mark value → mark kept.
- **Upstream defects identified:** None
