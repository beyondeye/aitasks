---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [sitrep, crash_recovery]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2299
followup_kind: upstream_defect
created_at: 2026-11-16 17:08
updated_at: 2026-11-16 17:21
---

## Origin

Spawned from t2299_4 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/sitrep_crash.py:138-139 — BACKGROUND["stale_lock"] says "no live session holds" the lock, but row 5 (no PID anchor) never proves the holder dead; the stored background over-claims for unanchored locks`

## Diagnostic context

While documenting crash-recovery items (t2299_4), a review found that the docs had described `stale_lock` the way this background text does: "A lock remains for this task but no live session holds it (no PID anchor, or the task is no longer Implementing)." The decision table (`recovery_verdict`, same file) shows that this holds for only one of the two routes into the category:

- row 5, `liveness == "noanchor"` → `stale_lock` for ANY task status. A lock with no PID anchor has no process to check, so its holder's liveness is unknown, not proven dead.
- row 7, a dead anchored holder on a task that is no longer Implementing → `stale_lock`. Here the holder is proven gone.
- a holder proven alive is row 3 (`done`) and never reaches `stale_lock`.

The docs were corrected in t2299_4 (skill, `aidocs/framework/sitrep.md`, website) to describe a stale lock as "check who holds it, never proof that nobody does". The stored background text in each `stale_lock` item's context still over-claims.

## Suggested fix

Reword `BACKGROUND["stale_lock"]` to describe both routes without claiming the holder is gone. For example: "A lock remains for this task: it records no PID anchor, so its holder cannot be checked, or its holder is gone and the task is no longer Implementing."

Mind the idempotence rule (the module header): changing the background changes every stored stale_lock item's context. The next detector pass therefore rewrites each of them once (`APPLIED`, new `checked_at`). Confirm that this is acceptable, or note it in the commit. Update any test that pins the background text (`tests/test_sitrep_crash.py`, `tests/test_sitrep_crash.sh`).
