---
priority: medium
effort: medium
depends: []
issue_type: test
status: Ready
labels: [test, documentation, git]
anchor: 1560
followup_kind: risk_mitigation
created_at: 2026-08-24 23:05
updated_at: 2026-08-24 23:05
---

## Origin

Risk-mitigation ("after") follow-up for t1560_3, created at Step 8d after implementation landed.

## Risk addressed

Destructive-remedy mis-mapping + liveness asymmetry (goal-achievement).

From t1560_3's plan `## Risk` section:

- The published recovery ladder documents a **destructive** remedy:
  `--reset-hard` discards tracked working-tree state. If the prose blurs which
  residue state maps to which flag, a reader could run the wrong one and lose
  work · severity: medium
- The liveness rule is asymmetric — on acquire, `alive` **and** `unknown` are
  both left alone; on `force-release`, only a literal `alive` refuses. Stating
  it backwards would tell users either that a wedged unverifiable lock cannot
  be cleared, or that a live holder can be displaced · severity: medium

## Goal

`website/content/docs/concepts/locks.md` now republishes a recovery mapping the
merge broker owns: which working-tree residue state requires which
`force-release` flag, and which liveness verdicts refuse. That is duplicated
knowledge, and the duplicate can rot silently — a broker change would leave the
website telling users to run the wrong destructive command.

Add a test that pins the **curated published mapping** against the broker's
actual behaviour:

- `MERGE_HEAD` present → `--abort-merge`
- unmerged index / dirty tree with no `MERGE_HEAD` → `--reset-hard`
- a mismatched flag is refused (`WRONG_REMEDY`), never attempted
- a provably live holder is refused (`REFUSED_LIVE_HOLDER`); `unknown` is not
- failure keeps the lock rather than releasing it (`RECOVERY_FAILED`)

**Scope the guard to that curated set — deliberately NOT to the broker's full
`--list-verdicts` vocabulary.** That vocabulary contains workflow-internal,
non-recovery verdicts (`CLEANUP_REQUIRES_COMPLETION`, `TARGET_MISMATCH`,
`NOT_OWNER_SESSION`, …) which the website has no reason to publish, so a
full-coverage rule would fail the website guard every time an unrelated verdict
is added. Full `(verb, verdict)` coverage is already enforced for the *rendered
workflow* by `tests/test_merge_broker_rendered_verdicts.sh` — do not duplicate
that here.

The guard must be able to fail: verify it by mutating one documented remedy flag
in the page and confirming the test reports that specific mapping.

## Key files

- `website/content/docs/concepts/locks.md` — the published mapping (section
  "Recovering a stuck merge mutex")
- `.aitask-scripts/aitask_merge_task.sh:399-435` — the `force-release` branches
- `.aitask-scripts/lib/merge_lock.sh:50-54` — the acquire-path liveness rule
- `tests/test_merge_broker_rendered_verdicts.sh` — the existing, differently
  scoped coverage test
