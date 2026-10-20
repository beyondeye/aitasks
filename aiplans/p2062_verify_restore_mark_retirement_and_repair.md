---
Task: t2062_verify_restore_mark_retirement_and_repair.md
Base branch: main
Output branch: main
---

# t2062 — Verify restore-mark retirement, and repair a stale stamp on a `live` record

## Context

`agent_frozen_ops.retire_restore_marks(pane, record_id, nonce)` issues guarded `if-shell`
clears (the `@aitask_frozen` stamp, the gone-pane attempt mark) and never checks they took.
Its callers — the restore coordinator (`agent_restore._clear_frozen_stamp`, 4 success sites)
and reconcile's recovery of an abandoned restore (`agent_freeze._reconcile_restoring` →
`_retire_marks`, which since t2066 also runs `clear_restore_attempt_claiming` for a mark left
under an earlier pass's nonce) — then report a clean `RESTORED:` / `LIVE:`. A transient tmux
failure leaves a `live` record whose own pane still carries its stamp: `freeze_pane` answers
`FREEZE_SKIPPED … already frozen`, `freeze --all` and both monitors treat the pane as a
frozen stand-in (the stamp is authoritative in `monitor_core`), and no reconcile pass looks
at `live` records — the agent can never be frozen again. `if-shell`'s rc proves nothing (its
branch can fail while it answers 0), so only a re-read of the pane proves a clear.

A second defect of the same class (review of the first draft, reproduced with the freeze
fakes): `clear_stamp_if` guards on the record id ALONE, and a record id is reused across
freeze cycles. A clear issued late — after the record went `live` and was then frozen again —
strips the new stand-in's legitimate stamp, and `_reconcile_frozen` never restores it. Every
"retire after `live`" clear (coordinator, reconcile's confirm, and the new repair) must
therefore also be guarded on the pid of the agent that made the record `live`.

## Approach

1. **PID-guard the stamp clear.** At every point the record is `live`, the agent's pid is
   known; put it in the same `if-shell` condition as the stamp, exactly as t2066's
   `clear_restore_attempt_claiming` does for the mark.
2. **Verify once, after ALL cleanup**, with a read-only helper, and report what is left as a
   suffix on the success line (`…|marks_retained:stamp`). `ok` stays True: the record is
   `live` and the agent runs.
3. **Repair in reconcile**, not `freeze_pane`: `freeze --all` (`_eligible_by_session` skips
   `pane.frozen_record`) and the monitors' freeze actions never reach a stamped pane, while
   reconcile runs after every freeze/restore and on every monitor maintenance tick.

## Steps

### 1. `.aitask-scripts/lib/agent_frozen_ops.py`

- `clear_stamp_if(pane_id, record_id, pane_pid: int = 0)`: with `pane_pid > 0` the condition
  is `#{&&:#{==:#{@aitask_frozen},<id>},#{==:#{pane_pid},<pid>}}` (the t2066 shape); with 0
  it is today's record-only guard (kept for callers with no live pid — none of the
  "after `live`" paths below pass 0). Docstring: why the pid half exists (id reuse across
  freeze cycles).
- `retire_restore_marks(pane_id, record_id, nonce, pane_pid: int = 0)` passes `pane_pid` to
  the stamp clear. Return type stays `None` — it only dispatches.
- New read-only `restore_marks_left(pane_id, record_id, pane_pid) -> str`, run by each caller
  AFTER its complete cleanup sequence:
  ```python
  facts = window_facts(pane_id)          # one display-message: pane_pid, frozen, mark
  if facts is None:            return "marks_unverified"
  if not facts:                return ""        # pane gone: nothing left on it
  if pane_pid > 0 and int_or_zero(facts["pane_pid"]) != pane_pid:
      return ""      # no longer the agent's pane: its marks are not ours to report
  left = []
  if facts.get("frozen") == record_id:                         left.append("stamp")
  if restore_attempt_record("", facts.get("mark", "")) == record_id: left.append("mark")
  return f"marks_retained:{','.join(left)}" if left else ""
  ```
  The mark check is "any mark claiming this record", not the nonce-derived value — so a mark
  under an earlier nonce that the t2066 recovery failed to clear is still reported.

### 2. `.aitask-scripts/lib/agent_restore.py` — coordinator

- `_clear_frozen_stamp(pane_id, record_id, nonce, pane_pid) -> str`: retire (pid-guarded),
  then `restore_marks_left`; returns `f"|{detail}"` or `""`.
- The 4 success sites pass the live agent's pid and append the suffix:
  liveness fallback → `observed_pid`; `_rollout_confirm` → `pane_pid`; `_decide_from_record`
  hook/rollout and liveness → `int_or_zero(rec["pane_pid"])` (the hook ack and
  `restore-confirm` both `_set_location` the agent's pid). Nobody parses these lines (the
  coordinator is a detached `run-shell -b` job); only tests read them.

### 3. `.aitask-scripts/lib/agent_freeze.py` — reconcile

- `_reconcile_restoring._retire_marks(pane_id, pane_pid) -> str`: `retire_restore_marks(…,
  pane_pid)` → `clear_restore_attempt_claiming(…, launch_pid)` → `restore_marks_left(…,
  pane_pid)` LAST; returns the `|detail` suffix. Both confirm sites pass `observed.pane_pid`
  (== `launch_pid` on that branch) and return `f"LIVE:{record_id}|rollout{suffix}"` /
  `…|liveness{suffix}`.
- New `_repair_live_stamp(record_id) -> str` (the one `live` shape reconcile now touches):
  1. `store_show` (to learn `pane_id`) → `pane_facts(pane_id)` → `store_show` again, which
     decides: `state == live`, same `pane_id`, nonzero `pane_pid` == the pane's pid, pane
     not dead, stamp == `record_id`. Stamp read BEFORE the deciding state read: a freeze
     that set the stamp had already left `live` (`freeze-begin` precedes the stamp).
  2. `clear_stamp_if(pane_id, record_id, pane_pid)` — pid-guarded in the dispatch.
  3. `restore_marks_left(pane_id, record_id, pane_pid)` but reading only the stamp verdict:
     `""` → `REPAIRED:<id>|stale_stamp`; stamp still there →
     `RECONCILE_FAILED:<id>|stale_stamp:retained`; `marks_unverified` →
     `RECONCILE_FAILED:<id>|stale_stamp:unverified`. If the pane is gone or its pid changed
     after the clear (someone else repaired and re-froze it), the result is `""` → no line.
     (Implementation: a small shared `_stamp_left` read, or `restore_marks_left` with the
     mark half ignored — whichever reads cleaner; the mark is not this path's concern.)
  - No lease: it issues no store verb (`_Lease`: "no action, no lease").
- `reconcile()`: `stamped_ids = {p.frozen for p in observed_by_pane.values() if p.frozen}`;
  the `STATE_LIVE` branch runs `_repair_live_stamp` only for ids in `stamped_ids`, appends a
  non-empty line, then `continue`s — healthy live records cost zero extra reads (t2041).
  Docstring updated ("every non-`live` record, plus one `live` shape: a stale own-pane
  stamp").
- Residual, in the docstring (safe direction): a NEW freeze that stamps the pane between the
  deciding re-read and the clear — before its respawn, so the pid still matches — loses that
  stamp; its stamp-guarded respawn then misses and it fails `FREEZE_FAILED:respawn` with the
  agent untouched. After the respawn the pid guard declines (the race the review found).

### 4. Tests

`tests/test_agent_frozen_ops.py` (`GuardedClearTests`):
- `clear_stamp_if` with a pid dispatches the exact `#{&&:…}` condition; without one, today's
  condition. `retire_restore_marks` tests updated for the pid argument.
- `restore_marks_left`: stamp/mark (incl. a mark under ANOTHER nonce of this record) →
  `marks_retained:stamp,mark`; another record's stamp/mark → `""`; pid changed → `""`;
  gone → `""`; rc `-1` → `marks_unverified`.

`tests/test_agent_freeze.py`:
- `_FakeTmux` gains `unset_fail: set[str]` — a `set-option -pu` of a listed option answers 1
  (inside `if-shell`, which still answers 0, as tmux does).
- `ReconcileRestoringTests` (reusing `_abandoned_and_marked` / `_recover`), liveness and
  rollout via `subTest`: stamp clear fails → `…|marks_retained:stamp`; mark clear fails →
  `…|marks_retained:mark`; both (`set_option_ok = False`, the task's repro) →
  `…|marks_retained:stamp,mark`.
- **t2066 path** (`_replaced_by_a_failed_pass`): attempt-mark unset injected to fail → the
  older-nonce mark survives the claiming clear and the line is `…|marks_retained:mark`, never
  a clean `LIVE:<id>|liveness`.
- **Repair through the real `reconcile()`** (patch `discover_aitasks_sessions` as
  `FreezeAllSelectionTests` does): after the repro, `set_option_ok = True`; precondition
  `freeze_pane` → `FREEZE_SKIPPED`; `reconcile()` → `REPAIRED:<id>|stale_stamp`;
  `freeze_pane` → `FROZEN:<id>`.
- **Two repairs overlapping a completed new freeze** (the review's sequence): wrap
  `agent_frozen_ops.store_show` so that at repair A's deciding read it first runs repair B to
  completion and then a full `freeze_pane` (succeeds; pane now the stand-in, pid 8888,
  stamp = id, record `frozen`), and hands A the `live` snapshot it read before. A then
  clears: the stand-in keeps its stamp, the record stays `frozen`, A emits no line, B emitted
  `REPAIRED`. **Mutant control:** the same interleaving with the clear forced to `pane_pid=0`
  strips the stamp — proving the test detects the bug.
- `LiveStampRepairTests` negative controls (through `reconcile()`): a mounted stand-in of a
  `frozen` record — kept, `KEEP:` only; a `live` record stamped but with a different pid (a
  viewer) — kept; dead pane — kept; ANOTHER record's stamp — kept; a healthy unstamped `live`
  record — no `show` issued for it; the clear fails during repair →
  `RECONCILE_FAILED:<id>|stale_stamp:retained`.

`tests/test_agent_restore.py`:
- `_Server`: `_cond` learns the binary `#{&&:A,B}` of equalities (as `test_agent_freeze`'s
  fake did for t2066), and gains `unset_fails: set[str]`.
- `_clear_frozen_stamp` returns `"|marks_retained:stamp"` / `"|marks_retained:mark"` / `""`;
  a delayed coordinator clear after the pane was re-frozen (pid changed) keeps the stand-in's
  stamp. Existing clear tests pass the pid.
- One end-to-end line: a `restore()` run (the `TestHookWinsTheLaunchRace` shape) whose arity-7
  `window_facts` answer still carries the stamp → `RESTORED:7f3a2c1d|hook|marks_retained:stamp`,
  `ok` True, no rollback.

### 5. Docs — `website/content/docs/workflows/freeze-and-restore-agents.md`

One sentence in "When something goes wrong" (reconcile paragraph): an agent that was restored
but still shows as frozen, because its marker could not be removed, is unmarked by reconcile
and can then be frozen again. Then `python3 check_links.py --build`.

### Post-phase (risk mitigations)

1. [transitional_states_never_repaired] In `LiveStampRepairTests`, pin the state filter
   against in-flight transactions: a `freezing` record (stamp on the agent's own pane, pid ==
   the record's — the stale shape except for state) and a `restoring` record past
   `restore-launched` are never unstamped: `_repair_live_stamp` returns `""` and issues no
   `if-shell`; `reconcile()` emits no `REPAIRED:`. Include a variant where the first
   `store_show` says `live` and the deciding one says `freezing`, pinning the re-read order.

## Verification

```bash
~/.aitask/venv/bin/python -m pytest -q tests/test_agent_frozen_ops.py tests/test_agent_freeze.py tests/test_agent_restore.py tests/test_frozen_restore_verdict.py tests/test_frozenagent_restore_poll_characterization.py tests/test_monitor_frozen_filter.py
bash tests/test_no_raw_tmux.sh
bash tests/run_all_python_tests.sh --test-dir tests   # verdict: last line
cd website && python3 check_links.py --build
```
Red proofs: verification removed (`restore_marks_left` → `""`) fails the `marks_retained`
tests incl. the t2066 one; the `STATE_LIVE` branch reverted to `continue` fails the repair
test; the pid guard dropped fails the overlap test (and its mutant control shows why).

## Step 9 (Post-Implementation)

Commit code (`bug: … (t2062)`) and plan separately; archive per the shared workflow.

## Risk

### Code-health risk: low
- The new `live` branch sits in reconcile's main loop; a wrong filter could unstamp a real stand-in or an in-flight freeze's stamp, which monitors and `drop` rely on · severity: medium · → mitigation: inline post-phase transitional_states_never_repaired
- Record-id-only stamp clears race a completed re-freeze (id reuse); now pid-guarded on all after-`live` paths, with an overlap test and mutant control · severity: medium · → mitigation: none (addressed in Steps 1–4)
- Success-line wording changes on two engines; strict test fakes (`_ScriptedTmux` raises on an unscripted read arity) may need fixture updates · severity: low · → mitigation: none (accepted; fixtures updated in Step 4)

### Goal-achievement risk: low
- Repair lives in reconcile, so a stuck agent heals on the next pass (after the next freeze/restore or monitor tick ≤600 s), not instantly on a manual `freeze <pane>` · severity: low · → mitigation: none (accepted)

### Planned mitigations
- timing: post-phase | name: transitional_states_never_repaired | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: wrong live-branch filter unstamping an in-flight transaction | desc: negative controls that freezing/restoring records (and a live→freezing re-read) are never repaired
