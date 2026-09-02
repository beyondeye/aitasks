---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [framework, bash_scripts, concurrency]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-09-02 09:18
updated_at: 2026-09-02 16:51
---

# Guard `ait_ledger_lock_exit_trap` against being chained behind another command

Surfaced while implementing **t1657_2**, the seam's second consumer. Deferred
there as an upstream follow-up: t1657_2 fixed its own call site, but the hazard
lives in the seam's API and the next consumer will meet it unwarned.

## The defect

`ait_ledger_lock_exit_trap` (`.aitask-scripts/lib/ledger_block.sh`) opens with:

```bash
ait_ledger_lock_exit_trap() {
    local rc=$?
    ...
    exit "$rc"
}
```

Reading `$?` on entry is the whole point of the function — its own comment says
it exists to "capture the incoming status ... preserve a meaningful nonzero
status". But `$?` reflects **the command that ran immediately before it**, so a
consumer that needs its own cleanup and writes the natural-looking

```bash
trap 'my_cleanup; ait_ledger_lock_exit_trap' EXIT
```

silently destroys the status. `my_cleanup` succeeds, `$?` becomes 0, and the
trap exits 0 — **for a section that died**.

## Measured, not theoretical

This is exactly what happened in t1657_2. With that chain in place, a `die` from
`ait_ledger_lock_release_checked` (reachable: `stale_lock_release` returns 1 on
a retained lock or a retained guard) exited **0**, and the caller reported
`NOTE_APPENDED` — success — for an append whose lock was wedged. A failure
reported as success is strictly worse than a wrong error code.

The working call site now reads:

```bash
trap 'rc=$?; my_cleanup; (exit $rc); ait_ledger_lock_exit_trap' EXIT
```

## Why it belongs upstream

Nothing in the seam prevents or documents this. The gate ledger, the seam's
first consumer, happens to install the trap bare and so never hits it — which is
why it survived t1657_1's review. t1657_3 and t1657_4 both add consumers that
will want their own cleanup.

## Suggested fix

Either is defensible; pick one and say why in the code:

- **Document it loudly** — a comment on `ait_ledger_lock_exit_trap` stating that
  it MUST be the first command in the trap string, with the `(exit $rc)` idiom
  spelled out for consumers that need cleanup.
- **Take the status as an argument** — `ait_ledger_lock_exit_trap "$?"` with the
  no-arg form keeping today's behaviour, so a chained consumer has a correct
  spelling available rather than only a forbidden one.

A guard is preferable to a comment if one can be made to work, per the framework
preference for source enforcement over documentation.

## Verification

- A test that installs a chained trap, forces a death inside the guarded
  section, and asserts the exit status is preserved — it must FAIL against
  today's implementation, not merely pass after the fix.
- Every existing gate suite stays green on both backends: `gate` installs the
  trap bare and its behaviour must not change.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-02T13:51:32Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-02T14:03:56Z status=pass attempt=1 type=human
