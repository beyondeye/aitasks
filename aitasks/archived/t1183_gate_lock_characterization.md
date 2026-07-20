---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: test
status: Done
labels: [gates]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 635
implemented_with: claudecode/fable5
created_at: 2026-07-20 12:25
updated_at: 2026-07-20 18:12
completed_at: 2026-07-20 18:12
boardidx: 50
---

## Origin

Risk-mitigation ("before") for t635_30, created at Step 7 from the approved
plan's risk evaluation (`aiplans/p635/p635_30_task_gate_editing_surface.md`).
t635_30 depends on this task and cannot be implemented until it lands.

## Risk addressed

Code-health risk (severity: medium) — *"Changing the gate lock key from raw
argument to resolved file alters mutual-exclusion for the **existing**
`append`/`materialize-active` verbs. A wrong derivation over-excludes or
under-excludes on a load-bearing path."*

t635_30 will replace `local key="${task_id//\//_}"` in
`.aitask-scripts/aitask_gate.sh` (`cmd_materialize_active`, ~line 648) with a
key derived from the **resolved task file**, because the current key is computed
from the raw argument: `ait gate append t635_30` and `ait gate append 635_30`
today take *different* locks (`/tmp/aitask_gate_lock_t635_30` vs
`/tmp/aitask_gate_lock_635_30`) and therefore do **not** mutually exclude. That
is a real pre-existing bug, but fixing it changes concurrency behavior on a
load-bearing path used by every gate append and every claim-time
materialization.

## Goal

Pin the **current** mutual-exclusion behavior of `aitask_gate.sh` with
characterization tests, so the lock-key change in t635_30 is provably safe for
existing callers rather than an unverified swap.

Cover at least:

1. **Same-spelling exclusion holds today** — two concurrent `append` calls using
   the *identical* task-id spelling serialize (no interleaved/lost ledger
   block). This behavior must survive the change.
2. **Key derivation = raw argument** (corrected premise, verified during
   planning). The originally stated cross-spelling scenario is unreachable:
   `resolve_task_file` runs *before* the lock is taken and a `t`-prefixed id
   dies there ("No task file found"), so `append t<id>` never acquires any
   lock. The real divergence t635_30 fixes — raw-argument key vs
   resolved-file key — is pinned instead by pre-holding lock directories:
   today a held `/tmp/aitask_gate_lock_<raw-id>` blocks `append <id>` while a
   held `/tmp/aitask_gate_lock_<file-basename>` is ignored; t635_30 flips
   exactly that pair. Additionally assert the t-spelling status quo (dies at
   resolve, pre-lock) as an alias-introduction tripwire. (This is the
   characterization test's real payload.)
3. **`materialize-active` vs `append`** on the same task serialize under the
   same-spelling case.
4. **Lock lifecycle** — the `mkdir` lock directory is released on normal exit
   and on `die` (the `trap release_gate_lock EXIT` path), and the >120s stale
   lock is reclaimed with the `warn` message.
5. **Retry exhaustion** — a held lock causes `die` after the 20-attempt budget
   rather than proceeding unlocked (fail-closed).

Note `acquire_gate_lock` (`.aitask-scripts/aitask_gate.sh:70-91`) is a
**non-reentrant** `mkdir` lock — a nested acquisition of the same key retries
20x at 0.3s and then dies. Tests must not accidentally rely on reentrancy.

## Reference

- `.aitask-scripts/aitask_gate.sh:68-97` — `acquire_gate_lock` /
  `release_gate_lock`.
- `.aitask-scripts/aitask_gate.sh:648` — the raw-argument key to be replaced.
- `aitask_create.sh acquire_child_lock` — the mirrored lock pattern.
- Test conventions: `tests/lib/asserts.sh`, fixture pattern in
  `tests/test_gate_cli_wiring.sh:20-27`.
- Consumer plan: `aiplans/p635/p635_30_task_gate_editing_surface.md` §1.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-20T10:01:19Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-20T15:07:47Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-20T15:12:02Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:6f39503aa2146515

> **✅ gate:risk_evaluated** run=2026-07-20T15:12:02Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1183/risk_evaluated_2026-07-20T15:12:02Z-risk_evaluated-a1.log`
