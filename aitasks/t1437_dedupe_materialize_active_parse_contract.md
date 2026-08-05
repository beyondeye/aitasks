---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [gates, task_workflow]
gates: [risk_evaluated]
anchor: 635
created_at: 2026-08-05 17:59
updated_at: 2026-08-05 17:59
---

## Origin

Spawned from t1272 during Step 8b review.

## Upstream defect

- `.claude/skills/aitask-pickrem/materialize-active.md:12-46 — the materialize-active stdout-parse contract is duplicated verbatim-in-substance from .claude/skills/task-workflow/SKILL.md Step 4 (now 6 bullets each), hand-maintained in both files with no drift guard. This task's own planning only found the second copy incidentally, while verifying an unrelated concern; t635_34 shipped its warning into neither. A canonical-site + drift-guard follow-up (shared include, or a test asserting bullet-set parity) would prevent the next contract change from landing in one lane only.`

## Diagnostic context

t1272's job was to document the `materialize-active` stderr warning in "the
Step-4 parse contract". Its written Scope named exactly one file:
`.claude/skills/task-workflow/SKILL.md`.

The second copy was found only by accident. While verifying an unrelated user
concern about the breadth of `aitask_skill_rerender.sh remote`, a grep for
"Materialize the active-gates tuple" across `.claude/skills/` returned
`aitask-pickrem/SKILL.md.j2` as well — which delegates to
`aitask-pickrem/materialize-active.md`, carrying the same five bullets and
stating outright that it "mirrors the attended workflow's Step 4".

That is the failure mode worth fixing: t635_34 (which *introduced* the warning)
documented it in neither lane, and t1272 was scoped to only one. Both surfaces
now carry the bullet, but nothing prevents the next change to this contract from
landing in one lane again.

Note the two copies are **not** byte-identical and should not be naively merged:
- line width differs (task-workflow uses long single-line bullets; pickrem wraps);
- the abort target differs (`Step 5` vs `Step 6`), as does the archival step
  referenced in the new bullet (`Step 9` vs `Step 10`);
- the attended lane says "surface to the user"; the remote lane is
  non-interactive and says "display in the run output".

So the fix must preserve per-lane wording while binding the two to one another.

## Suggested fix

Two directions, in rough order of preference:

1. **Drift guard (cheap, no restructuring):** add a test asserting the two files
   expose the same *set* of parse-outcome tokens (`MATERIALIZED`,
   `MATERIALIZED_UNCOMMITTED`, `NOOP`, `NOOP_UNCOMMITTED`, nonzero exit, the
   stderr warning). Token-set parity tolerates the legitimate per-lane wording
   and step-number differences while failing loudly when one lane gains an
   outcome the other lacks.
2. **Canonical site (more invasive):** extract the contract into a shared
   include rendered into both trees, with the lane-specific bits
   (step numbers, surface-vs-display) as template parameters.

Check whether `aitask-web-merge/materialize-gates.md` is a third instance —
it covers a different helper (`aitask_web_merge.sh materialize`), so it may be
genuinely separate rather than a copy.
