# Background-work roadmap

The background-work roadmap is a ranked, conflict-aware, **three-lane** ordering
of backlog work, estimating which items can be started *alongside whatever is
currently in flight*. It exists because auto-spawned follow-up work is
machine-authored and therefore never picked proactively, so it accumulates, goes
stale, and becomes the obstacle to choosing work at all.

The three lanes are **parallel-safe**, **coordination** and **unresolvable**. The
third is not decoration: "the comparison could not be made" is a distinct answer
from "this conflicts", and collapsing it into either of the others would either
hide work or assert a conflict the checker never found.

**The roadmap never certifies that anything is safe.** Its strongest verdict
means "no known conflict at check time" — a snapshot that reserves nothing. Read
the next section before relying on any lane.

This document is the design record for the roadmap's **policy layer** — scoring,
freshness, lane assignment, and the trail encoding contract. The skill that
drives it is `aitask-backlog-roadmap`; the shared collision verdict it consumes
is `aidocs/`-adjacent in `.aitask-scripts/lib/parallel_admission.py`.

## The output is an estimate

The roadmap labels its whole output an **estimate**: origin/topic evidence,
in-flight state as of the run, **reserving nothing**. It is explicitly distinct
from the parallel-admission preflight that `task-workflow` runs before
implementation, which is live and plan-derived.

`CLEAR` means **"no known conflict at check time"** — never "safe to run in
parallel". The checker observes; it does not reserve. Overlapping work can begin
in the instant after a `CLEAR`, and that residual closes only when a
declared-claims backend replaces the derived evidence.

## Architecture: facts, then policy

| layer | module | purity |
|---|---|---|
| in-flight and planned-surface facts | `lib/trail_gather.py` (`--with-inflight`) | impure |
| task → file sets, origin resolution | `lib/task_file_sets.py`, `lib/followup_origin.py` | pure |
| the collision verdict | `lib/parallel_admission.py` | pure |
| origin risk facts | `lib/roadmap_origin_facts.py` | **impure** |
| premise drift | `lib/roadmap_premise.py` | pure |
| scoring, lanes, trail encoding | `lib/roadmap_policy.py` | pure |

The policy layer imports `parallel_admission.decide` / `input_from_records`
**directly** and never the collector. `tests/test_parallel_admission_purity.py`
enforces both halves: an AST scan plus an import with `subprocess` poisoned, over
a `PURE_MODULES` list that includes `roadmap_policy` and `roadmap_premise`.

The two flags a reader may expect to see are **fields, not subprocess
arguments**:

| conceptual flag | actual |
|---|---|
| `--from origin` | `Surface(provenance="origin_derived")` |
| `--lock-freshness allow-cached` | `LockEvidence(mode="allow-cached")` (the default) |

**`data_tracked` is mandatory on the injected path.** `aitasks/` and `aiplans/`
are gitignored symlinks, so `git ls-files` on the code branch tracks none of
them and every task-data path arrives classified `phantom`. Omitting the set
means two tasks editing the same profile YAML report no conflict.

## Scoring

Ordering is a **lexicographic tuple**, not a weighted sum:

```
(-risk_band, -risk_axes_at_band, -premise_band, -affinity,
 -recency_band, -priority_band, canonical_sort_id)
```

That is what makes "in-flight area affinity must not bury urgent unrelated work"
a structural property rather than an artefact of tuning: affinity sits below
risk, so it reorders within a risk band and never across one.

| component | role |
|---|---|
| origin `risk_code_health` / `risk_goal_achievement` | **primary value signal** |
| premise validity | freshness weight 1 |
| in-flight area affinity | strong but **advisory** |
| recency | freshness weight 2 |
| `priority` | weak, transparent tie-break only — on auto-spawned follow-ups it is mostly a seam default |
| `effort` | a background-capacity constraint, **not value**; absent from the sort key |
| `followup_kind` | **not ordering-relevant**; never read by the scorer |

`followup_kind` is enforced, not merely asserted: a test permutes it across the
fixture corpus and requires a byte-identical ranking. The trail schema declares
it display-only and omits it from the digest and drift-code set.

### Combining the two risk axes

The two risk dimensions are assessed independently and must not be blended into
a single score, but ordering needs a total order. The combination is therefore
stated rather than left to whichever field an implementation reads first:

```python
AXIS_BAND = {"high": 3, "medium": 2, None: 1, "low": 0}
risk_band         = max(band(rch), band(rga))
risk_axes_at_band = (band(rch) == risk_band) + (band(rga) == risk_band)
```

`max`, and **the two axes are peers**. It is the only combination that is
symmetric — `(high, low)` and `(low, high)` rank identically — and monotone —
raising either axis can never lower the rank. `risk_axes_at_band` breaks ties
*within* a band, so `(high, high)` precedes `(high, low)` without privileging
either axis.

**A missing axis is `unknown` (band 1), never zero.** `unknown` sits between
`medium` and `low` deliberately: an unknown risk could be high, so ranking it
below `low` would hide it and above `medium` would over-claim. An **undeclared**
value (a typo'd level) raises rather than folding into `unknown` — silently
absorbing it would be a fail-open on the primary value signal.

### Multi-origin reduction

A follow-up can verify many origins. Per axis the reduction is `max` over the
origins **and the candidate's own value** — the signal is "risk on the task *or*
its origin", and including both keeps the rule symmetric instead of needing a
precedence tie-break. An absent origin contributes the `unknown` band, never 0.

Provenance is a **set**, not a first value: uniform origins render as `active` /
`archived` / `absent`, and any mixture renders as `mixed`.

Two caveats are mandatory so the reduction is never invisible: one when origins
**disagree** on either axis, naming the origin that set the band, and one when
any origin could not be read.

**`rationale` carries the pre-reduction values, not just the winner.** With two
origins at `(high, low)` and `(low, low)`, the reduced pair alone reads
`high / unknown` and a caveat naming only the setter — the losing origin's values
would be invisible, and a `max` a human cannot audit is a number they cannot
override. Every origin is therefore rendered as `900=high/low, 901=low/low`, in
full rather than truncated (the live maximum is 11 origins), and a single-origin
entry names its source instead.

*Measured 2026-08-31:* 25 of 89 exact follow-ups carry more than one origin (up
to 11); 13 of those disagree on a risk level; 6 span mixed sources. A
"first origin wins" reduction reports t1064 as `low` while one of its origins is
`medium`.

### Where origin risk comes from

Origin risk lives on the *origin*, which is usually archived. *Measured
2026-08-31:* 8 active task files carry `risk_code_health:` against 203 archived
ones. The gatherer emits extended member facts only for members in scope, so
archived origins have no producer there — `lib/roadmap_origin_facts.py` is that
producer. It emits **one record per `(task, origin)` pair**:

```
ORIGIN_FACT:<task_id>|<origin_id>|<quality>|<rch>|<rga>|<source>
```

`quality` is `exact | topic | unknown` and is a property of the *task*, repeated
on each of its rows; `source` is `active | archived | absent` and is a property
of the *origin*. Fields are `%`-then-`|` encoded, the free-ish field is last, and
a task with no resolvable origin still gets exactly one row — **absence is
reported, never inferred from a missing line**.

## Freshness: two independent weights

**Recency** and **premise validity** are separate weights, so an
old-but-still-valid task is not punished like a recently-invalidated one.

### The premise-drift baseline is the origin's last *landing* commit

A landing commit names an origin id **and** touches at least one path outside the
task-data trees. The qualification is load-bearing: `ait git commit` tags
task-data commits `(tNN)` too, so an unqualified "newest tagged commit" lets a
bookkeeping commit move the baseline forward past real code changes, which then
read as pre-baseline and are silently reported fresh.

*Measured 2026-08-31 over the whole history:* 61 of 1714 `(tNN)`-tagged commits
touch no code path, and 35 of 1615 tagged ids have a **metadata-only newest
tagged commit**.

The task-data prefixes are a **parameter**, not a hardcoded layout, because the
task and plan directories are configurable.

| state | reason | decision |
|---|---|---|
| no origin resolved | `no_origin` | `SKIP` |
| no tagged commit at all | `unknown_history` | `SKIP` |
| tagged commits exist, all task-data | `metadata_only` | `SKIP` |
| baseline resolved, but **no files to check** | `empty_scope` | `SKIP` |
| ≥1 landing commit and a non-empty surface | — | proceed |

`empty_scope` is the one that is easy to get wrong. A resolved baseline over an
empty file surface has checked **nothing**, so reporting fresh would be the
module's own false all-clear — "all 0 files unchanged" reads as verified, and it
would lift the confidence ceiling to `high` for a task whose premise was never
examined. It is reachable: a candidate whose batch-map status is `NO_FILES` has
an empty surface. It is not `ASK_STALE` either — there is no evidence the premise
moved, only an absence of anything to check.

**The rejected alternative** was `created_at` → nearest ancestor commit. It fails
on a production-reachable case: a `risk_mitigation` "before" follow-up is created
*before* its origin's code lands, so its `created_at` baseline precedes the
origin's own landing commit and that commit then reads as drift — a false stale
verdict on every such task. It also needs timezone-free minute-granularity time
arithmetic that the pure module cannot perform. The failure is pinned as a test.

### Conventions borrowed, and two narrowings

The line protocol, the always-return contract, the `FRESH` / `ASK_STALE` / `SKIP`
tri-state with fail-open `SKIP`, and the `%`-then-`|` injective encoding are
borrowed from the manual-verification staleness helper — **conventions only**,
since that helper's scope and baseline fields do not exist on follow-ups.

**`UNKNOWN` drives the verdict; it is not advisory.** A path that cannot be
checked means the check covers *less* scope than it claims, so a fresh verdict
would be a false all-clear. It is implemented the way the shell helper does it:
unknown records go into the *same* evidence list as changed ones, and the verdict
is an emptiness test over that list, so the two cannot drift apart.

Two accepted narrowings, stated so a reader does not go looking for them:

1. **No `DELETED:` record.** The commit index records paths *touched*, not
   whether a commit deleted them, so a deletion surfaces as `CHANGED:`.
2. **No `:(literal)` pathspec guard.** That guard exists because git
   fnmatch-globs a pathspec; this interface runs no git.

### What the premise signal does not buy

*Measured 2026-08-31:* of 169 follow-ups with a resolvable origin and file set,
153 land on `ASK_STALE` and 14 on `SKIP`. The band is therefore nearly constant
across today's corpus and contributes almost nothing to *ordering*. Its value is
in the per-entry hedge — the confidence ceiling and the caveat — not in
discrimination. A separate measurement found **zero** follow-ups that are stale
only because of task-data churn, so restricting the checked scope to code paths
would change nothing today and was not done.

## Lanes and confidence

The lanes **are the checker's verdicts**. Nothing in the policy layer re-derives
a collision — a second opinion would be a second definition of "safe".

| verdict | wave | `classification` |
|---|---|---|
| `CLEAR` | 1 parallel-safe | `core` |
| `CLEAR_CAVEATED` | 1 parallel-safe | `core` (reduced confidence, unverified source named in `caveats[]`) |
| `CONFLICT` | 2 coordination | `coordination_only` (rendered `⇄` by the board's `TRAIL_CLASSIFICATION_GLYPHS`) |
| `UNCHECKABLE` | 3 unresolvable | `optional` |

`UNCHECKABLE` gets its **own** lane rather than joining coordination: "cannot
tell" is not "conflicts with", and filing it under coordination would assert a
conflict the checker did not find. What it may never be is wave 1.

`confidence` is an enum (`high | medium | low`), so "reduced" is a table. Origin
quality is carried *into* confidence, which is what stops a `topic` entry from
reading like an `exact` one:

| verdict | `exact` | `topic` / `unknown` |
|---|---|---|
| `CLEAR` | high | medium |
| `CLEAR_CAVEATED` | medium | low |
| `CONFLICT` | high | medium |
| `UNCHECKABLE` | low | low |

### Premise validity caps confidence

The table above keys on **conflict** evidence only. Freshness is an independent
axis, and without a rule a premise known to have changed could still render as a
high-confidence wave-1 recommendation. The composition is a ceiling applied
afterwards:

| premise | ceiling | additional |
|---|---|---|
| `FRESH` | high | — |
| `SKIP` | medium | none — `SKIP` stays silent per the borrowed convention |
| `ASK_STALE` | low | a mandatory caveat **and** a `stale_premise` observation |

The lane is unchanged in every case: a stale premise is a value and confidence
signal, never a conflict.

Capping `SKIP` at `medium` is a small, deliberate departure from "silent",
justified because high confidence should require that the premise was actually
verified. What it does **not** buy: a medium-confidence entry is not evidence
that the premise is sound, only that it was not contradicted. The run summary
reports the `SKIP` count so the state is visible in aggregate.

## Origin quality is carried, not hidden

Every entry states `exact` / `topic` / `unknown`, and a `topic` or `unknown`
entry is hedged in three places: reduced confidence, a `caveats[]` string naming
the fallback, and the quality word in `rationale`.

## Resolution-quality measurement

The true direct origin of the topic-only population is **unknown**, so nothing
can measure the fallback's impact on it. The only measurable set is the tasks
carrying **both** an exact-origin signal and a topic root — and because the exact
signal is written only by the manual-verification seams, that sample is entirely
manual-verification-typed and therefore **not representative**.

The divergence is not merely "topic is wider". Two live examples had an exact set
of 3 and 4 files against a topic set of 13, with an overlap of **zero** — the
topic root can be *disjoint* from the true origin, so the fallback can be
actively wrong rather than conservatively broad.

Each run emits:

```
ORIGIN_QUALITY:<exact>|<topic>|<unknown>
DEGRADED:<n>|<cause csv>
COUNTERFACTUAL:<n>|<N>|dual_signal_mv_typed
```

The histogram is **mutually exclusive** — the exact signal wins where both are
present. Never quote the raw topic-signal population as the topic count: it
double-counts every dual-signal task and would inflate the residual. The
counterfactual is phrased *"n of N dual-signal tasks (manual-verification-typed)
would rank differently"* and is **never** extrapolated to the topic-only
population.

*Measured 2026-08-31:* origin quality is 89 exact / 132 topic / 13 unknown, from
raw signal populations of 89 and 172 with a 40-task overlap.

### Enhancement threshold

A persisted direct-origin frontmatter field is justified when the dual-signal
counterfactual shows a material rank or lane change **and** the corpus-wide
`UNCHECKABLE` count attributable to origin quality is non-trivial. The second
condition is the one that generalises, because it is measured over the whole
corpus rather than the biased dual-signal sample.

## Trail encoding contract

All existing vocabulary — **no schema change**.

- **Depth is `deep`, not the default `lite`.** A lite document must omit
  `observations`, `relations`, `exclusions` and per-entry `evidence_refs` and
  carry exactly one `evidence` record; this contract needs all of them.
- **A zero-candidate scope has no valid encoding.** Both `waves` and each wave's
  `entries` are `minItems: 1`, so the encoder raises rather than emitting
  `waves: []` — an artifact that could never validate. What a zero-candidate run
  means (usually: report it and publish nothing) is the caller's decision, not
  the encoder's to guess.
- **Waves**: 1 parallel-safe, 2 coordination, 3 unresolvable. `wave.entries` is
  `minItems: 1`, so **only non-empty waves are built** and ordinals are assigned
  `1..n` over the lanes that actually have entries. The coordination lane is
  empty on the live corpus today, so an author that always emits three waves
  produces an invalid document on its very first real run.
- **`relations[]`**: `{type: coordinates_with, provenance: advisory}`, backlog →
  in-flight. An advisory edge must not be written back to task metadata.
- **`observations[]`**: `in_flight_conflict` | `shared_surface_collision` |
  `stale_premise`, each with `evidence_refs` (`minItems: 1`, and every ref must
  resolve to an `evidence[].evidence_id`).
  An `in_flight_conflict` observation carries **both** ends in `affects`. That is
  semantically right, and it is also what makes the matching relation legal: a
  relation endpoint resolves against entry tasks, exclusions, snapshot `depends`
  and observation `affects`, and an in-flight task has no entry of its own.
- **`evidence[]`**: `source_type: command_output`, naming the checker, gatherer
  and origin-facts invocations.
- **Score components are prose in `rationale`; hedges are `caveats[]`.** `entry`
  is `additionalProperties: false`, `rationale` has no maximum length, and
  `rendering_hints` is top-level and scalar-only, so structured per-entry
  components would require a `schema_version` bump touching both schema copies,
  the copy-drift guard, the validator and the goldens — for no gain.
- **Sentinels are omitted, not written.** The gatherer's transport sentinels
  (`unknown` / `invalid`) must never be written into `priority`, `effort`,
  `boardcol` or `followup_kind`; those are closed enums and a sentinel
  invalidates the whole document.
- Refs are canonical `<project>#<id>`, copied byte-identically from the gatherer,
  because digest provenance depends on it.

## Run-summary honesty requirements

These are correctness, not tone.

- State plainly that the lanes are an **estimate** that reserves nothing, and
  that the live preflight runs before implementation.
- **Never** say "safe to run in parallel". Say "no known conflict at check time".
- Surface the origin-quality histogram, so the persisted-origin-field question
  stays visible and evidence-backed.
- Show `UNCHECKABLE` counts with their named causes, not just the safe lane.

## Staleness is narrow now and shared later

`lib/roadmap_premise.py` is deliberately narrow and exists behind a small
replaceable interface, frozen in its `__all__`. When the framework's generalized
task-staleness mechanism lands, the roadmap drops this module and consumes that
instead; the module must not grow into a second permanent staleness framework in
the meantime, and a test fails if a name appears that `__all__` does not list.
