---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [verification, task-workflow]
gates: [risk_evaluated]
children_to_implement: [t1555_2, t1555_3, t1555_4]
anchor: 1538
created_at: 2026-08-17 19:00
updated_at: 2026-08-18 10:21
boardcol: now
boardidx: 16454
---

Implement the manual-verification staleness pre-check designed in t1538.

**Read `aidocs/framework/manual_verification_staleness.md` first — it is the source
of truth for this whole tree.** Each child restates the constraints it needs, but
the doc carries the reasoning, the measurements, and the full deferred list.

## What is being built

An **advisory** pre-check that warns when files a manual-verification checklist
explicitly names have changed since a recorded baseline. It runs in
`.claude/skills/task-workflow/manual-verification.md`, between step 1 (ensure the
task has a checklist) and step 1.5 (the autonomous-verification offer). It never
blocks archival and never rewrites anything without the user accepting it.

## The one precondition that defines the scope

> The check runs **only** when the task already carries **both** a populated
> `file_references:` list **and** a persisted `verification_baseline:`.
> Otherwise it silently skips.

This is deliberately narrow and it is what keeps the feature a guardrail rather
than a task-state subsystem. Because an absent field simply means "skip":

- no sentinel is needed to distinguish "deliberately no scope" from "not yet
  curated" — so **no presence tracking in the shared `aitask_update.sh` writer**,
  and **no fold rule** in `aitask_fold_mark.sh`;
- both fields are written together at one moment when the origin's code has just
  landed, so **no lazy derivation** — no topological ancestry, no dominance
  verification, no unreachable-commit handling.

**If a child starts to need any of that, the precondition has been relaxed
somewhere.** Treat it as a signal to stop and re-read the doc's "Scope discipline"
and "Deferred" sections, not as a missing requirement. The design was cut back to
this shape on purpose, from a draft that had grown all of the above for a problem
with zero recorded incidents.

## Slices

1. **Check helper + `verification_baseline:` field** — the deterministic seam and
   the new frontmatter field, with tests.
2. **Step-8c seeding** — derive candidate files, narrow, confirm, write both fields.
3. **Procedure pre-check step** — the new step, the prompt, the review transaction,
   rerender + goldens.
4. **Manual verification** — drive the whole path live; this is the only check that
   distinguishes "correctly quiet" from "never runs".

The slices are strictly sequential; each child auto-depends on the previous one.

## Known limits (inherent, not gaps to close)

- **Coverage:** only tasks seeded through Step 8c after their origin landed. All 77
  existing manual-verification tasks and all 26 aggregate ones are skipped. That is
  the accepted cost of the precondition.
- **Change is not behavior:** an item can go stale with every curated file untouched
  (a default changed elsewhere), and can stay valid after a behavior-preserving
  refactor. Both error directions persist, which is why the verdict is advisory.

## Related

- t1538 (archived) — the design pass; its plan records the four post-approval
  contract corrections.
- t1553 — an upstream defect in `aitask_revert_analyze.sh` surfaced during the
  design (its `--task-files` leaks task-metadata paths). Independent of this tree,
  but slice 2 consumes that helper, so landing t1553 first would make slice 2's
  candidate derivation cleaner.
