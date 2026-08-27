---
Task: t1569_5_roadmap_scoring_freshness_and_lanes.md
Parent Task: aitasks/t1569_background_work_roadmap_trail_for_followup_backlog.md
Sibling Tasks: aitasks/t1569/t1569_1_*.md, aitasks/t1569/t1569_2_*.md, aitasks/t1569/t1569_3_*.md, aitasks/t1569/t1569_4_*.md, aitasks/t1569/t1569_6_*.md
Archived Sibling Plans: aiplans/archived/p1569/p1569_*_*.md
Base branch: main
Output branch: main
---

# t1569_5 — Roadmap scoring, dual freshness, premise-drift, lanes

Consumer #2 of the shared checker: the **advisory** one. Pure library; everything
arrives as injected data — no git, no subprocess. Parallel with t1569_4.

## Step 1 (before anything else) — settle the premise-drift baseline

The reuse of `aitask_verification_stale.sh` is **conventions only**. That helper
reads its scope from `file_references:` (0 of 461 active tasks carry it —
explicitly rejected for this task) and its baseline from
`verification_baseline:` (absent on follow-ups). So the baseline must be
**invented**, and this is the most likely mid-implementation redesign in the tree.

Two candidates, both computable from t1569_2's `COMMIT:` index without shelling
git — which is exactly why that index carries `%ct`:

| option | shape | risk |
|---|---|---|
| `created_at` → nearest ancestor commit | minute granularity, no timezone; needs an ancestor guard | a follow-up spawned before its origin landed gets a baseline *after* the change it should detect |
| the origin's **last landed commit** | exact, no time arithmetic | wrong when the origin is still in flight (`UNKNOWN_HISTORY` — 41 of 260 candidates) |

Decide, justify in the design record, and encode the rejected option's failure
mode as a test. Whichever is chosen, an uncomputable baseline is `SKIP`
(fail-open, silent) — never a fabricated one.

## Step 2 — Lanes are the checker's verdicts

Call the checker with `--from origin --lock-freshness allow-cached`.

| verdict | lane |
|---|---|
| `CLEAR` | parallel-safe, `classification: core` |
| `CLEAR_CAVEATED` | parallel-safe, reduced `confidence`, unverified source named in `rationale` |
| `CONFLICT` | coordination, `classification: coordination_only` (glyph already rendered at `aitask_board.py:639`) |
| `UNCHECKABLE` | surfaced hedged — **never** silently in the safe lane |

Do **not** re-derive a verdict here. A second opinion is a second definition of
"safe", which is the whole thing t1569_3 exists to prevent.

Label the entire output an **estimate** — origin/topic evidence, in-flight state
as of the run, **reserving nothing** — explicitly distinct from t1569_4's live,
plan-derived admission decision. Say it in those words; the run summary in
t1569_6 repeats it.

## Step 3 — Scoring

Component-wise, transparent, overridable. Every component shown per entry.

| component | weight | rationale |
|---|---|---|
| origin `risk_code_health:` / `risk_goal_achievement:` | **primary value signal** | a `high`-risk mitigation outranks a `low` one |
| in-flight area affinity | strong but **advisory** boost | must surface relevant work while an area is active, but **must not bury urgent unrelated work** |
| `priority:` | weak, transparent tie-break only | on auto-spawned follow-ups it is mostly a seam default, not a judgement |
| `effort:` | capacity / scheduling constraint | **not value** |
| `followup_kind` | **not ordering-relevant** | its categories are not a severity model, and the trail schema declares it display-only (`implementation_trail.schema.json:395-396`) |

Enforce the last row: a test that permutes `followup_kind` across the fixture
corpus and asserts **byte-identical** ranking. That converts a settled decision
into an enforced one.

Note only 7 active tasks carry `risk_code_health:` while **186 of 287** archived
ones do — the primary signal comes from the *origin*, which is usually archived.
Resolve it through t1569_2's resolver plus the archived-task reader
(`lib/archive_iter.py`), and treat an unreadable origin as a missing component,
not a zero.

## Step 4 — Origin quality is carried, not hidden

Every entry states `exact` / `topic` / `unknown`. A `topic` or `unknown` entry is
**visibly hedged** — it must not read like an exact one.

## Step 5 — Freshness: two independent weights

- **Recency** — how recently the follow-up was spawned.
- **Premise validity** — evidence the origin files/plan have not churned since
  the baseline from Step 1.

Separate weights, so an old-but-still-valid task is not punished like a
recently-invalidated one.

## Step 6 — Premise drift behind a replaceable interface

A deliberately narrow, advisory signal. **Do not build a second permanent
staleness framework** — put it behind a small interface t1561 will substitute,
and create the adoption follow-up (below).

Conventions to copy from `aitask_verification_stale.sh`: line protocol; always
exit 0 for content states while CLI misuse dies; tri-state with `SKIP` fail-open
and silent; **`UNKNOWN` drives the verdict** (a path that cannot be checked means
the check covers *less* scope than it claims, so `FRESH` would be a false
all-clear); `%`-then-`|` injective encoding; `:(literal)` pathspec guard.

## Step 7 — Resolution-quality measurement

The true direct origin of the **130** `topic`-only follow-ups is **unknown**, so
nothing can measure the fallback's impact on them. The only measurable set is the
**37 carrying both `verifies:` and `anchor:`** — and since `verifies:` is written
only by the manual-verification seams, those 37 are all MV-typed, i.e. **not
representative**.

Measured today on the 37: the exact and topic file sets differ in **21 cases**,
and the divergence is not merely "topic is wider" — t1497 (exact 3, topic 13,
**overlap 0**) and t1513 (exact 4, topic 13, **overlap 0**) show the topic root
can be **disjoint** from the true origin. The fallback can be actively wrong.

Emit per run:

1. the **mutually exclusive** `exact` / `topic` / `unknown` histogram — 86 / 130 /
   13 today. **Never quote the raw `anchor` count of 167**: it double-counts the
   37 overlap and would inflate the residual.
2. the count of estimates degraded to `UNCHECKABLE` by origin quality or
   `UNKNOWN_HISTORY`.
3. the counterfactual over the **dual-signal sample only**, phrased *"n of N
   dual-signal tasks (MV-typed) would rank differently"* — **never** extrapolated
   to the 130.

Assert the measurement in a fixture where the two sets provably differ, so it
cannot be vacuously zero.

**Enhancement threshold**, stated in the design record: a persisted
`followup_origins:` field is justified when the dual-signal counterfactual shows a
material rank or lane change **and** the corpus-wide UNCHECKABLE count
attributable to origin quality is non-trivial. The second condition is the one
that generalises, because it is measured over the whole corpus rather than the
biased 37.

## Step 8 — Score-component representation

`entry` is `additionalProperties: false` and `rendering_hints` allows only scalar
values and is top-level. So "every score component shown per entry" is
satisfiable **as prose in `rationale`** without a schema bump. Structured
components would require a `schema_version` bump touching both schema copies,
`SchemaCopyDrift` (`tests/test_trail_schema.py:68`), the validator and the
goldens.

**Recommendation: prose, no bump.** Settle it here — t1569_6 authors against it.

## Step 9 — Ship the design record

`aidocs/framework/background_work_roadmap.md`, covering: the scoring model, the
two freshness weights, the Step-1 baseline decision and its rejected alternative,
t1569_3's narrowing rule and threshold, the measured resolution-quality residual
and the enhancement threshold, **the residual race (CLEAR reserves nothing)**,
and the trail encoding contract below.

Follow `aidocs/framework/documentation_conventions.md` — current-state-only
prose. Per `feedback_no_volatile_sample_stats_in_reference_docs`, present the
corpus numbers as dated measurements, not as standing facts.

### Trail encoding contract (all existing vocabulary — no schema change)

- **waves**: wave 1 parallel-safe, wave 2+ coordination. A coordination item
  genuinely is "queue after the in-flight task", so the ordinal semantics are
  honest.
- **`relations[]`**: `{type: coordinates_with, provenance: advisory}`, backlog →
  in-flight.
- **`observations[]`**: `in_flight_conflict` | `shared_surface_collision` |
  `stale_premise`, each with `affects` and `evidence_refs` (`minItems: 1`).
- **`evidence[]`**: `source_type: command_output` naming the checker and
  gatherer invocations.

## Step 10 — Create the t1561 adoption follow-up

Consume t1561's generalized staleness mechanism in place of Step 6's local
interface. `--followup-of 1569`, `depends: [1561, 1569_5]`.

## Verification

```bash
bash tests/run_all_python_tests.sh --test-dir tests    # last line only
python3 -m unittest tests.test_trail_schema -v
```

Required tests:

1. **Overlap / no-overlap / missing-plan / all-phantom-plan** fixtures. The live
   corpus cannot exercise the coordination lane — simulated today it gives
   coordination **0**, parallel-safe **220**, unresolvable **40** — so these are
   the only proof the lane fires.
2. **`followup_kind` permutation → byte-identical ranking.**
3. Determinism: same fixture twice → byte-identical ranking.
4. The Step-7 measurement asserted in a fixture where exact and topic sets
   provably differ.
5. The Step-1 baseline's rejected alternative encoded as a failing case.
6. A live smoke asserting **shape only** — exit 0, histogram present, counts sum
   — and **never** lane counts. The live corpus is an unstable oracle by
   construction.
