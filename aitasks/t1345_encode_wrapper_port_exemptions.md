---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [execution_profiles]
gates: [risk_evaluated]
anchor: 1311
followup_kind: upstream_defect
created_at: 2026-07-29 22:44
updated_at: 2026-08-13 23:06
boardidx: 104448
---

## Origin

Spawned from t1325 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_audit_wrappers.sh:36 — list_source_skills() reports the
  4 deliberately-unwrapped skills (aitask-explorechat, aitask-run-gates,
  aitask-gate-docs-updated, aitask-gate-template) as GAP: lines, so
  /aitask-audit-wrappers offers to create wrappers that must not exist. Nothing
  in the repo encodes that exclusion; it needs an explicit exemption marker on
  those skills. Its "user-invokable" comment is aspirational — the function never
  reads user-invocable frontmatter.`
- `tests/test_opencode_skill_legacy_pointers.sh:34 — the guard is correct but has
  no runner, so it sat able-to-fail (aitask-trail, 3386e1f43..2012a4575) without
  anyone noticing. CLAUDE.md deliberately keeps bash tests run-individually, so
  the fix is a CI touchpoint for the bash guard tests, not a local runner.`
- `.claude/skills/aitask-explorechat/SKILL.md:4 — declares user-invocable: true
  while its own description says "Not a user task command", making the field
  unusable as a ground truth for which skills are user-facing.`

## Diagnostic context

t1325 added cross-tree wrapper parity (`aitask_audit_wrappers.sh parity`, run by
`aitask_skill_verify.sh` and asserted as Test 0 of `tests/test_opencode_setup.sh`)
because `tests/test_opencode_setup.sh` derived its expected wrapper count from
the very tree it packaged.

While choosing the ground truth, three partial and mutually inconsistent sources
turned up, none authoritative:

1. `aitask_audit_wrappers.sh::list_source_skills()` — a glob over
   `.claude/skills/aitask-*`. t1325 fixed its inclusion of rendered
   trailing-hyphen variants, but it still reports the 4 deliberately-unwrapped
   skills as gaps.
2. `stub-skill-pattern.md` §3g plus the templated-skill tests — authoritative but
   scoped to the 12 (now 13) `.j2` skills only.
3. `skill_authoring_conventions.md` — declared a counting rule that was circular
   and off by 2; corrected in t1325.

The live 28-wrapper set is therefore `.claude/skills/aitask-*` minus those 4,
maintained entirely by hand. `user-invocable` is the natural marker but appears
on only 9 of ~80 dirs and is `true` for `aitask-explorechat`, which is
deliberately unwrapped — so it cannot be used as-is.

Cross-tree parity (what t1325 shipped) catches the realistic omission — a skill
added to some trees but not all, the exact aitask-trail failure — but by
construction cannot see a skill missing from *every* tree. An explicit exemption
marker would close that residual gap and give the wrapper set a genuine
source-of-truth anchor.

## Suggested fix

- Add an explicit exemption marker (e.g. `agent_wrappers: false` in frontmatter,
  or a sidecar) to `aitask-explorechat`, `aitask-run-gates`,
  `aitask-gate-docs-updated`, `aitask-gate-template`, and derive
  `list_source_skills()` from `.claude/skills/aitask-*` minus exempt. Fix the
  stale "user-invokable" comment at the same time, or make it true.
- Extend `cmd_parity` to compare the resulting source set against the wrapper
  trees, closing the "missing from all trees" residual limit documented in that
  function.
- Separately, give the bash guard tests a CI touchpoint so a correct-but-unrun
  guard cannot sit red unnoticed. Note CLAUDE.md deliberately keeps bash tests
  run-individually locally — this is about CI, not a local runner.

## Related

- t1325 (`skill_surface_guards_self_referential`) — added the parity guard and
  fixed the rendered-variant leak in `list_source_skills()`.
- t1317 (`templated_skill_dispatch_smoke`) — created the four-surface contract
  test and fixed the aitask-trail instance.
