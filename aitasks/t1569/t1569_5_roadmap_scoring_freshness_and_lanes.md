---
priority: high
effort: high
depends: [t1569_3]
issue_type: feature
status: Ready
labels: [backlog, scheduling, planning]
gates: [risk_evaluated]
anchor: 1569
created_at: 2026-08-27 11:29
updated_at: 2026-08-27 11:29
---

Roadmap scoring, dual freshness, premise-drift and lane assignment — a pure
library. Slice 5 of 6 for t1569 — read the parent task and
`aiplans/p1569_background_work_roadmap_trail_for_followup_backlog.md` first.

Depends on t1569_3 (the shared checker). **Set `depends: [t1569_3]`** — the
sibling default would record t1569_4, which is a peer consumer, not a dependency.
Runs in parallel with t1569_4.

## Context

Consumer #2 of the shared checker: the **advisory** one. Everything here consumes
t1569_1's gatherer lines, t1569_2's index/resolver and t1569_3's checker as
**injected data** — no git, no subprocess, fully fixture-testable.

## Scope

### Lanes are the checker's verdicts, not a second opinion

- `CLEAR` -> parallel-safe (`classification: core`)
- `CLEAR_CAVEATED` -> parallel-safe but visibly caveated: reduced `confidence`,
  unverified source named in `rationale`
- `CONFLICT` -> coordination (`classification: coordination_only`, glyph U+21C4,
  already rendered at `aitask_board.py:639`)
- `UNCHECKABLE` -> surfaced hedged, **never** silently in the safe lane

Call the checker with `--from origin --lock-freshness allow-cached` and label the
whole output an **estimate** — origin/topic evidence, in-flight state as of the
run, reserving nothing — explicitly distinct from t1569_4's live, plan-derived
admission decision. Say so in those words in the run summary.

### Scoring — component-wise, transparent, overridable

- **Origin risk fields are the primary value signal**: `risk_code_health:` /
  `risk_goal_achievement:` on the task or its origin. A `high`-risk mitigation
  outranks a `low` one.
- **In-flight area affinity is a strong but advisory boost.** It must surface
  relevant improvements while an area is active but **must not bury urgent
  unrelated work**.
- **`priority:` is a weak, transparent tie-breaker only** — on auto-spawned
  follow-ups it is mostly a seam default, not a considered judgement.
- **`effort:` is a background-capacity / scheduling constraint, not value.**
- **`followup_kind` is NOT ordering-relevant.** Enforce it: a test that permutes
  `followup_kind` across the fixture corpus and asserts **byte-identical**
  ranking. That converts a settled decision into an enforced one.
- **Every score component shown per entry.**

### Origin quality is carried, not hidden

Every entry states `exact` / `topic` / `unknown`. A `topic` or `unknown` entry is
**visibly hedged** — it must not read like an exact one.

### Freshness — two independent weights

- **Recency** — how recently the follow-up was spawned.
- **Premise validity** — evidence the origin files/plan have not churned since.

Separate weights, so an old-but-still-valid task is not punished like a
recently-invalidated one.

### Premise drift — narrow now, shared later

A deliberately narrow, advisory signal behind a **small replaceable interface**
that t1561 will substitute. **Do not build a second permanent staleness
framework.**

Reuse `aitask_verification_stale.sh`'s conventions: line protocol; always exit 0
for content states (CLI misuse dies); tri-state with `SKIP` fail-open and silent;
**`UNKNOWN` drives the verdict** (a path that cannot be checked means the check
covers *less* scope than it claims, so `FRESH` would be a false all-clear);
`%`-then-`|` injective encoding; `:(literal)` pathspec guard.

**Step 1 of this task: settle the baseline.** The reuse is **conventions only** —
that helper reads scope from `file_references:` (0 of 461 active tasks carry it;
explicitly rejected for this task) and its baseline from `verification_baseline:`
(absent on follow-ups). So the baseline must be **invented**: `created_at` ->
nearest ancestor commit, or the origin's last landed commit. This is the most
likely mid-implementation redesign in the tree, which is why t1569_2 carries
commit timestamps — so the decision needs no reopening of a git helper.

### Resolution-quality measurement — a counterfactual on a biased sample

The true direct origin of the **130** `topic`-only follow-ups is **unknown**, so
nothing can measure the fallback's impact on them. The only tasks where both an
exact origin and a topic root exist are the **37 carrying both signals** — and
because `verifies:` is written only by the manual-verification seams, those 37
are all MV-typed, i.e. **not representative** of the 130.

Measured today on those 37: the two file sets differ in **21 cases**, and the
divergence is not merely "topic is wider" — t1497 (exact 3 files, topic 13,
**overlap 0**) and t1513 (exact 4, topic 13, **overlap 0**) show the topic root
can be **disjoint** from the true origin. The fallback can be actively wrong, not
just conservatively broad.

Emit per run:

- the **mutually exclusive** `exact` / `topic` / `unknown` histogram (86 / 130 /
  13 today — never quote the raw `anchor` count of 167, which double-counts the
  37 overlap);
- the count of estimates degraded to UNCHECKABLE by origin quality or
  `UNKNOWN_HISTORY`;
- the counterfactual over the **dual-signal sample only**, reported as *"n of N
  dual-signal tasks (MV-typed) would rank differently"* — **never extrapolated to
  the 130**.

Assert the measurement in a fixture where the two file sets provably differ, so
it cannot be vacuously zero.

**Enhancement threshold** (state it in the design record): a persisted
`followup_origins:` field is justified when the dual-signal counterfactual shows
a material rank or lane change **and** the corpus-wide UNCHECKABLE count
attributable to origin quality is non-trivial. The second condition is the one
that generalises, because it is measured over the whole corpus rather than the
biased 37.

### Ships the design record

`aidocs/framework/background_work_roadmap.md` — scoring model, the two freshness
weights, the baseline decision, the narrowing rule, the measured residual, the
residual race (CLEAR reserves nothing), and the **trail encoding contract**
below. t1569_6 implements against it, so it lands here.

### Settle the score-component representation here

`entry` is `additionalProperties: false` and `rendering_hints` allows only scalar
values and is top-level, so "every score component shown per entry" is
satisfiable **as prose in `rationale`** without a schema bump. Structured
components would require a `schema_version` bump touching both schema copies,
`SchemaCopyDrift` (`tests/test_trail_schema.py:68`), the validator and the
goldens. **Recommendation: prose, no bump.**

### Trail encoding contract — all existing vocabulary, no schema change

- waves: wave 1 parallel-safe, wave 2+ coordination ("queue after the in-flight
  task" — ordinal semantics are honest here)
- `relations[]`: `{type: coordinates_with, provenance: advisory}` backlog ->
  in-flight
- `observations[]`: `in_flight_conflict` | `shared_surface_collision` |
  `stale_premise`, each with `affects` + `evidence_refs` (`minItems: 1`)
- `evidence[]`: `source_type: command_output` naming the checker / gatherer
  invocations

## Follow-up to create

**t1561 adoption** — consume t1561's generalized staleness mechanism in place of
this task's local interface. `depends: [1561, 1569_5]`.

## Reference files for patterns

- `.aitask-scripts/aitask_verification_stale.sh` + `aidocs/framework/manual_verification_staleness.md`
- `.aitask-scripts/lib/implementation_trail.schema.json` — observation/relation
  enums (L234-243, L216), `$defs.entry` (L351-434), the `followup_kind`
  display-only declaration (L395-396)
- `.aitask-scripts/lib/followup_backfill_classify.py` — pure-module contract
- `tests/test_trail_schema.py` — validation and digest contract tests

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` (last line only)
- `python3 -m unittest tests.test_trail_schema -v`

Required tests:

1. **Overlap / no-overlap / missing-plan / all-phantom-plan** fixtures — the live
   corpus cannot exercise the coordination lane (simulated today: coordination
   **0**, parallel-safe **220**, unresolvable **40**), so these are the only
   proof it fires.
2. **`followup_kind` permutation -> byte-identical ranking.**
3. Determinism: same fixture twice -> byte-identical ranking.
4. The resolution-quality measurement asserted in a fixture where exact and topic
   sets provably differ.
5. A live smoke asserting **shape only** — exit 0, histogram present, counts sum
   — and **never** lane counts. The live corpus is an unstable oracle by
   construction.
