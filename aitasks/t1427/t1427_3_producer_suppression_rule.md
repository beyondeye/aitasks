---
priority: high
effort: medium
depends: [t1427_2]
issue_type: feature
status: Ready
labels: [shadow, aitask_monitormini, aitask_monitor]
gates: [risk_evaluated]
anchor: 1159
created_at: 2026-08-05 17:18
updated_at: 2026-08-05 17:18
---

Producer-side suppression rule for t1427. Depends on t1427_1 (helper exists)
and t1427_2 (rejections are being persisted). Parent plan
`aiplans/p1427_reject_shadow_concerns_suppress_next_round.md` is binding.

## Context

The shadow re-words concern bodies between review rounds, so suppression of
rejected concerns must be SEMANTIC and performed by the shadow agent, not by
`concern_parser.py`. Shadow Step 2 (context fetch) is explicitly optional, so
a context-fetch-only delivery has an unreachable trigger — the rule lives in
`concern-format.md` (source of truth) AND inlined in each producer, following
the existing short-region-rule precedent (rules are inlined because "an extra
file read is a rule the agent may skip").

## The rule (common wording, all four producers)

Placed as (a) a pre-emit directive at the head of each emit step — stylistic
precedent: the bolded directive at `impl-challenge.md:373` — and (b) a bullet
in the "load-bearing for minimonitor's parser" rules list:

> Before emitting the block, if a source task id is known, run
> `./.aitask-scripts/aitask_shadow_rejected.sh list <task_id>`. Drop any fresh
> concern that is substantively the same as a rejected entry, even when
> reworded. Report `Suppressed N previously-rejected concern(s).` in the
> prose before the block whenever N >= 1. When unsure whether a fresh concern
> matches a rejected one, keep it and say why (fail-open — consistent with
> `needs_addressing()` treating unspecified disposition as actionable). When
> no task id is resolved, state that rejection suppression was skipped.

## Key files

- `.claude/skills/aitask-shadow/concern-format.md` — new "Rejected-concern
  suppression" section documenting the store path
  (`.aitask-shadow/<task_id>/rejected.md`), the helper `list` call, the
  fail-open contract, and the drift guard (mirroring the region-rule
  provenance note at :59-63).
- The four producers, each carrying the inlined rule:
  `.claude/skills/aitask-shadow/plan-challenge.md` (rules list :71, emit step
  6 :53-101), `plan-assumptions.md` (:75, step 6 :50-104),
  `plan-diagnose-errors.md` (:64, step 4 :44-88), `impl-challenge.md` (:390,
  emit section :366-436).
- `.claude/skills/aitask-shadow/SKILL.md.j2` Step 2 (:151-185) — one sentence:
  resolving the source task id also enables rejection suppression.

## Drift guards (tests/test_concern_parser.py)

New `TestProducerRejectionSuppressionRule`, a one-for-one mirror of
`TestProducerRegionRequiredRule` (:870-922):
- module-level predicate `_states_rejection_suppression_rule(text)` matching
  two substrings after whitespace collapse: `"previously-rejected"` and
  `"aitask_shadow_rejected.sh list"` — make the chosen rule wording contain
  both exactly;
- reuse `SHADOW_DIR` / `PRODUCER_MARKER` / `KNOWN_PRODUCERS` /`_producers`
  from `TestProducerShortRegionRule` by reference;
- duplicate `test_producer_set_is_the_known_set`;
- offenders test + negative control (synthetic text, mutates no repo file).

Extend `TestRenderedShadowDocsKeepTheGuarantees` (:925-1027) with the rendered
check for the new rule (alongside
`test_every_rendered_producer_states_both_region_rules`).

## Skill-surface hygiene

`SKILL.md.j2` edit → regenerate affected goldens in the same commit and run
`./.aitask-scripts/aitask_skill_verify.sh` (see skill_authoring_conventions).
Producers live ONLY in the Claude tree (per concern-format.md "Where it
lives") — no cross-agent port tasks needed. The helper whitelist was applied
in t1427_1; verify `audit-helper-whitelist aitask_shadow_rejected.sh` reports
no MISSING.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` — new drift guards
  green; negative control proven able to fail.
- `./.aitask-scripts/aitask_skill_verify.sh` clean.
- Live: with a rejection stored for a task, run a shadow plan-challenge round
  and confirm the suppression report line appears and the rejected concern is
  absent from the block.
