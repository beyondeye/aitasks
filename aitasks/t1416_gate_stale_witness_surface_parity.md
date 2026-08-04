---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [verification, backend]
gates: [risk_evaluated]
anchor: 635
created_at: 2026-08-04 18:35
updated_at: 2026-08-04 18:35
---

## Origin

Risk-mitigation ("after") follow-up for t1409, created at Step 8d after
implementation landed.

## Risk addressed

**Goal-achievement — ledger-only surfaces disagree with the enforcing decision.**
From t1409's plan `## Risk` section:

> Four agreeing-but-unfixed surfaces (`archive_status_from_text`,
> `read_task_gate_state`, `deps-unblock`, `unlocked`) remain ledger-only, so a
> board badge or `ait ls` row can disagree with the enforcing decision ·
> severity: low

## Background

t1409 made a code-bound human-gate signature re-validated on **every**
observation, not just before the first `pass`. Two surfaces enforce it:

- `gate_orchestrator.Engine._read_state()` — demotes stale-signed gates so the
  engine re-pends them.
- `gate_ledger.archive_status(task_file, registry_file)` — blocks archival,
  wired through `aitask_gate.sh archive-ready`.

Four other surfaces were deliberately left **ledger-only**, because each runs
per-task across many tasks per refresh and the freshness check costs a git
subprocess (`gate_ledger.code_digest()`):

| Surface | Consumer |
|---|---|
| `gate_ledger.archive_status_from_text()` | `lib/stats_data.py` active-task scan, `lib/trail_gather.py` |
| `gate_ledger.read_task_gate_state()` | board / monitor gate badge |
| `aitask_gate.sh deps-unblock` | `ait ls` dependency unblocking |
| `gate_orchestrator.unlocked()` | `ait gates unlocked` introspection |

The split is documented in each function's docstring and in
`aidocs/gates/gate-guarded-archival.md` ("Deliberately ledger-only surfaces").

## Goal

Resolve the split rather than leave it as tribal knowledge. Either:

1. **Thread a once-per-refresh digest.** The code digest is repo-global, so it
   can be computed once per board refresh / `ait ls` invocation / stats pass and
   passed down. `stale_signed_gates()` already accepts an explicit
   `current_digest` parameter for exactly this (its `_COMPUTE_DIGEST` sentinel
   distinguishes "compute lazily" from a caller-supplied value, including
   `None` = unverifiable). Measure the cost before committing to it — the board
   refresh budget is the binding constraint.

2. **Or ratify the surfaces as intentionally ledger-only, with a drift guard.**
   A test that fails if a new archival-readiness consumer is added without
   picking a side, so the split cannot silently grow.

Whichever is chosen, `deps-unblock` deserves its own decision: `review_approved`
carries `blocks_dependents: true`, so a stale signature arguably should not
release dependents either — that is a semantics question, not just a cost one.

## Verification

- If threading the digest: assert a board refresh over a realistic task count
  computes `code_digest()` at most once, and that a task with a stale signature
  renders a blocked badge.
- If ratifying: the drift guard must fail against a deliberately-added
  ledger-only consumer (negative control), then pass once it is registered.
