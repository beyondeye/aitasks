---
Task: t1569_5_roadmap_scoring_freshness_and_lanes.md
Parent Task: aitasks/t1569_background_work_roadmap_trail_for_followup_backlog.md
Sibling Tasks: aitasks/t1569/t1569_4_task_workflow_parallel_admission_preflight.md, aitasks/t1569/t1569_6_backlog_roadmap_skill_and_trail_authoring.md, aitasks/t1569/t1569_7_manual_verification_background_work_roadmap.md
Archived Sibling Plans: aiplans/archived/p1569/p1569_1_gatherer_inflight_and_planned_surface_facts.md, aiplans/archived/p1569/p1569_2_batch_task_file_sets_and_origin_resolution.md, aiplans/archived/p1569/p1569_3_shared_parallel_admission_checker.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-31 19:25
---

# t1569_5 — Roadmap scoring, dual freshness, premise-drift, lanes

## Context

59% of the active backlog is auto-spawned follow-up work nobody picks. t1569
delivers a **background-work roadmap** — a ranked, conflict-aware, two-lane
ordering of that backlog — plus a **shared parallel-admission checker** with two
consumers.

Siblings 1–3 have landed. This slice is **consumer #2: the advisory one**. It
turns the checker's verdicts and the gatherer's facts into a ranked, lane-assigned,
honestly-hedged roadmap, and it **ships the design record** `aidocs/framework/background_work_roadmap.md`
that t1569_6 implements its skill against.

t1569_4 (consumer #1, the blocking preflight) runs in parallel; neither depends on
the other. Nothing in this slice is in flight elsewhere — verified 2026-08-31.

### What the verify pass changed

This plan existed but had never been verified. Checking it against the landed code
found six things wrong or missing:

1. **Mechanism.** The plan said "call the checker with `--from origin
   --lock-freshness allow-cached`". `parallel_admission.py:5-8` says the opposite:
   the roadmap **imports `decide` / `input_from_records` directly and NEVER the
   collector**, and `tests/test_parallel_admission_purity.py::BoundaryTests::test_the_roadmap_path_never_needs_the_collector`
   already enforces it. Those two flags are *field values*, not a subprocess.
2. **`aitask_board.py:639` is wrong** — the `coordination_only` `⇄` glyph is at
   **`aitask_board.py:893`** (`TRAIL_CLASSIFICATION_GLYPHS`). Fixed here and in
   the design record.
3. **`confidence` is an enum** `high|medium|low`, not a number — "reduced
   confidence" needs an explicit mapping table (Step 2).
4. **`caveats[]` exists** on `entry` (array of string, optional). Hedging belongs
   there, not crammed into `rationale`.
5. **A wave requires `minItems: 1` entries** — so an empty coordination wave is
   *invalid*, and coordination is **0** on the live corpus. Waves must be built
   only when non-empty.
6. **No producer exists for origin risk fields.** 203 of them sit on *archived*
   origins; the gatherer only emits `MEMBER_EXT:` for in-scope members. Closed by
   a small impure collector (Step 3).

A review round then found four more, all confirmed against the live corpus and
addressed above:

7. **Two risk axes, one band, no combination rule** — `(high, low)` and
   `(low, high)` would have ranked differently depending on which field the code
   read first. Now an explicit symmetric `max` table with a tie-break (Step 4).
8. **The baseline could be moved by a metadata commit.** Confirmed live:
   **61 of 1714** `(tNN)`-tagged commits touch no code path, and **35 of 1615**
   tagged ids — t1636_3, t1544_8, **t1569 itself** — have a metadata-only *newest*
   tagged commit, which would silently mask real drift as a false `FRESH`. The
   baseline is now a qualified commit class (Step 1).
9. **A stale premise could stay a high-confidence wave-1 entry** — the confidence
   table keyed only on conflict evidence. Now a ceiling composition, with a
   mandatory caveat and the `stale_premise` observation the encoding contract
   named but nothing produced (Step 2).
10. **Nothing proved the cross-slice flow.** Units, a hand-authored document and a
   shape smoke can all pass while real output is wrong. Now one deterministic
   end-to-end fixture with two negative controls (Verification #12).

A second review round found two more, both confirmed live:

11. **`ORIGIN_FACT:` collapsed many origins into one risk pair.** Measured
   2026-08-31: **25 of 89** exact follow-ups carry >1 origin (up to 11), **13 of
   those 25 disagree on a risk level**, and **6 span mixed sources** — so a
   first-origin implementation reports t1064 as `low` while one origin is
   `medium`. The record is now one row per `(task, origin)` and the reduction is
   a stated policy rule (Step 3).
12. **The collector itself was never exercised.** Verification #12 begins from
   synthetic records, so a producer/consumer mismatch passes every test. Now a
   fixture drives the **real wrapper** over temp active + archived data into the
   same policy path (Verification #14).

Corpus figures re-measured **2026-08-31** (the plan's were 2026-08-27): origin
quality **89 exact / 132 topic / 13 unknown** (was 86/130/13); dual-signal overlap
**40** (was 37); raw `anchor` **172** (was 167). `file_references:` coverage is
**0 of 483** active task files, and `risk_code_health:` is on **8** active vs
**203** archived — the structural claims all hold; only the digits moved.

---

## Deliverables

| path | purity | role |
|---|---|---|
| `.aitask-scripts/lib/roadmap_policy.py` | **PURE** | scoring, lanes, freshness, trail encoding, measurement |
| `.aitask-scripts/lib/roadmap_premise.py` | **PURE** | the small replaceable premise-drift interface t1561 substitutes |
| `.aitask-scripts/lib/roadmap_origin_facts.py` | impure | reads active + archived frontmatter, emits `ORIGIN_FACT:` |
| `.aitask-scripts/aitask_backlog_origin_facts.sh` | wrapper | thin `exec` over the collector |
| `aidocs/framework/background_work_roadmap.md` | doc | the design record t1569_6 builds against |
| `tests/test_roadmap_policy.py`, `tests/test_roadmap_premise.py`, `tests/test_roadmap_origin_facts.py` | tests | |

Reuse, never re-derive: `parallel_admission` (`decide`, `input_from_records`,
`canonical_ref`), `parallel_admission_vocab` (`encode_path`, `check_member`,
the closed vocabularies), `plan_paths` (the path grammar —
`tests/test_plan_paths_seam.sh` fails a fork), `followup_origin.resolve_detailed`,
`task_file_sets`, `archive_iter`, `dep_resolution.canonical_dep_id`.

---

### Pre-phase (risk mitigations)

**`narrow_the_premise_seam`** — runs before Step 6 writes `roadmap_premise.py`.
Pin the module's public surface to exactly `baseline_for` and `check` (plus the
`FRESH`/`ASK_STALE`/`SKIP`/`REASONS` constants and the `PremiseResult` record),
and state in the module docstring that **t1561 is the substitution point** and
that omitting `DELETED:` is an accepted narrowing, not an oversight. Add a test
asserting the module exports nothing beyond that surface, so the seam cannot
quietly grow into a second permanent staleness framework.

---

## Step 1 — Premise-drift baseline: the origin's last landed commit

**Settled.** The baseline is the newest **landing** commit for the origin — and
"landing" is a *qualified* class, not just "newest row mentioning the id":

```python
def is_task_data(path, data_prefixes):
    return path.startswith(data_prefixes)      # prefixes INJECTED, never hardcoded

landing = {(sha, ct) for path, sha, ct, ids in commit_rows
           if origin_id in ids and not is_task_data(path, data_prefixes)}
baseline = max(landing, key=lambda r: (r[1], r[0])) if landing else None
```

**Why the qualification is load-bearing.** Commit subjects carry `(tNN)`, and
`ait git commit` tags **task-data** commits the same way — `ait: Add t1636_3 final
implementation notes (t1636_3)` touches only `aitasks/`. An unqualified
`max(committed_at)` lets such a commit move the baseline *forward past real code
changes*, which then read as pre-baseline and are silently not drift. That is a
false `FRESH` — the exact false all-clear this interface exists to avoid.

Measured 2026-08-31 with `task_file_sets.parse_log_stream` over the whole
history: **61 of 1714** `(tNN)`-tagged commits touch no code path, and **35 of
1615** tagged ids have a **metadata-only newest tagged commit** — t1636_3,
t1544_8 and t1569 itself among them. Not a theoretical case.

`data_prefixes` defaults to `("aitasks/", "aiplans/", ".aitask-gates/")` but is a
**parameter**, because `TASK_DIR` / `PLAN_DIR` are configurable and a pure module
must not hardcode a deployment's layout. The caller passes the resolved values.

Three terminal states, not two:

| state | reason | decision |
|---|---|---|
| no tagged commits at all | t1569_2's `STATUS:<id>\|UNKNOWN_HISTORY` | `SKIP` |
| tagged commits exist, all task-data | **`metadata_only`** (new reason) | `SKIP` |
| ≥1 landing commit | — | proceed |

Chosen over `created_at` → nearest ancestor commit because it is an exact sha
needing no time arithmetic and no timezone, and because when the origin has not
landed it degrades into a state t1569_2 **already names** — `STATUS:<id>|UNKNOWN_HISTORY`
→ `SKIP`, fail-open and silent. It invents nothing.

`created_at` was rejected for a **production-reachable** failure: a
`risk_mitigation` "before" follow-up is created by `task-workflow` Step 7 *before*
its origin's code lands, so its `created_at` baseline precedes the origin's own
landing commit, and that commit then reads as drift — a false `ASK_STALE` on
every such task. Encode this as the rejected-alternative test (Verification #5).

An uncomputable baseline is `SKIP`. Never fabricate one.

**Accepted narrowing, stated in the design record and pinned by a test:** the
`COMMIT:` index records paths *touched*, not whether they were deleted, so this
interface emits **no `DELETED:` record** — unlike `aitask_verification_stale.sh`.
A deletion surfaces as `CHANGED:`. That is a smaller claim, not a silent one.

---

## Step 2 — Lanes are the checker's verdicts, called in-process

`roadmap_policy` builds an `AdmissionInput` per candidate and calls
`parallel_admission.decide`. **Never** `parallel_admission_collect`, never the
shell CLI, never a second verdict rule.

```python
import parallel_admission as pa
import parallel_admission_vocab as vocab

inp = pa.input_from_records(
    candidate_ref=ref,
    candidate_surface=pa.Surface(ref, "origin_derived", paths, resolution, quality),
    inflight_lines=inflight_lines,          # t1569_1 INFLIGHT* records
    batch_map_lines=batch_map_lines,        # t1569_2 TASKFILES:/COMMIT:/STATUS:
    inflight_claims=claims,
    locks=pa.LockEvidence(mode="allow-cached"),
    data_tracked=data_tracked,              # MANDATORY — see below
    now=now,                                # injected; the module has no clock
)
result = pa.decide(inp)                     # AdmissionResult(verdict, lines)
```

The two former CLI flags map to **fields**:

| plan's old wording | actual |
|---|---|
| `--from origin` | `Surface(provenance="origin_derived")` — the exact `vocab.PROVENANCES` spelling |
| `--lock-freshness allow-cached` | `LockEvidence(mode="allow-cached")` — already the default |

**`data_tracked` is mandatory.** `aitasks/` and `aiplans/` are gitignored symlinks,
so `git ls-files` on the code branch tracks none of them and every task-data path
reads as `phantom` — two tasks editing the same profile YAML would report no
conflict. Omitting it reproduces exactly the blind spot t1569_3 fixed.

### Lane, classification, confidence

| verdict | wave | `classification` | notes |
|---|---|---|---|
| `CLEAR` | 1 parallel-safe | `core` | |
| `CLEAR_CAVEATED` | 1 parallel-safe | `core` | confidence one step down; unverified source named in `caveats[]` |
| `CONFLICT` | 2 coordination | `coordination_only` | `⇄`, `aitask_board.py:893` |
| `UNCHECKABLE` | 3 unresolvable | `optional` | hedged; **never** wave 1 |

`UNCHECKABLE` gets **its own wave**, not the coordination one: "cannot tell" is not
"conflicts with". Placing it in wave 2 would assert a conflict the checker did not
find.

`confidence` is `enum: [high, medium, low]`, so "reduced" is this table — origin
quality is carried *into* confidence, which is what makes a `topic` entry unable to
read like an `exact` one:

| verdict | `exact` | `topic` / `unknown` |
|---|---|---|
| `CLEAR` | high | medium |
| `CLEAR_CAVEATED` | medium | low |
| `CONFLICT` | high | medium |
| `UNCHECKABLE` | low | low |

### Premise validity caps confidence — composition rule

The table above keys on **conflict** evidence only. Freshness is a second,
independent axis, and without a stated rule a premise *known to have changed*
could still be rendered as a `high`-confidence wave-1 recommendation — more
reassuring than an advisory freshness signal warrants. The composition is a
**ceiling**, applied after the table:

```python
RANK    = {"low": 0, "medium": 1, "high": 2}
CEILING = {"FRESH": "high", "SKIP": "medium", "ASK_STALE": "low"}
confidence = min(table_confidence, CEILING[premise], key=RANK.__getitem__)
```

- **`ASK_STALE`** — ceiling `low`, **plus** a mandatory `caveats[]` string naming
  the changed/unknown path count, **plus** a `stale_premise` observation with
  `affects` and non-empty `evidence_refs`. The encoding contract already lists
  `stale_premise`; this is the rule that actually produces one. The lane is
  **unchanged** — the shared checker remains the sole conflict verdict, and a
  stale premise is a value/confidence signal, never a conflict.
- **`SKIP`** — ceiling `medium`, and **no per-entry caveat**: `SKIP` is fail-open
  and silent per the convention copied from `aitask_verification_stale.sh`, and it
  will be the common state (any origin with no landed code). The run summary
  reports the `SKIP` count so it is not invisible in aggregate.
- **`FRESH`** — ceiling `high`; the table governs.

The tension is deliberate and recorded in the design record: capping `SKIP` at
`medium` is a small departure from "silent", justified because `high` confidence
should require that the premise was actually verified. What it does **not** buy:
a `medium`-confidence entry is not evidence the premise is sound — only that it
was not contradicted.

**Do not re-derive a verdict.** A second opinion is a second definition of "safe",
which is the thing t1569_3 exists to prevent.

Label the whole output an **estimate** — origin/topic evidence, in-flight state as
of the run, **reserving nothing** — explicitly distinct from t1569_4's live,
plan-derived admission decision. Say it in those words. Never "safe to run in
parallel"; the fixed wording is `_DISPLAY_CLEAR` = **"no known conflict at check
time"**.

---

## Step 3 — Origin facts: a small impure collector

`.aitask-scripts/lib/roadmap_origin_facts.py` + `aitask_backlog_origin_facts.sh`.
The same pure/impure split `parallel_admission.py` / `parallel_admission_collect.py`
already uses.

Reads active task frontmatter and archived frontmatter via
`archive_iter.iter_archived_frontmatter(archived_dir, parse_fn)` /
`find_archived_markdown_by_id`, resolves origins with
`followup_origin.resolve_detailed`, and emits one record per candidate:

**One record per `(task, origin)` pair — never one row per task.** A follow-up can
verify many origins, and collapsing them in the collector would bake a policy
decision into a facts producer:

```
ORIGIN_FACT:<task_id>|<origin_id>|<quality>|<risk_code_health>|<risk_goal_achievement>|<source>
```

`<quality>` ∈ `followup_origin`'s `exact|topic|unknown` (a property of the *task*,
repeated on each of its rows). `<source>` ∈ `active|archived|absent` — a
**per-origin** fact. Every field has a sentinel `-`; a task whose quality is
`unknown` still gets exactly one row, with `origin_id` = `-`, so **absence is
never inferred**. Fields are `vocab.encode_path`-encoded; the free-ish field is
last. Every content state exits 0; CLI misuse exits 2.

### Multi-origin reduction — policy, not facts

Measured 2026-08-31: **25 of 89** exact follow-ups carry more than one origin (up
to 11); **13 of those 25 have conflicting risk levels across their origins**, and
**6 span mixed sources**. A "first origin wins" implementation silently reports
t1064 as `low` while one of its origins is `medium`. The reduction is therefore
stated, lives in `roadmap_policy` (where it is purely testable), and is applied
**per axis before** the two-axis combination of Step 4:

```python
rch_band = max(axis_band(r.risk_code_health)      for r in rows_for(task))
rga_band = max(axis_band(r.risk_goal_achievement) for r in rows_for(task))
# then Step 4's combination runs on (rch_band, rga_band) exactly as before
```

`max` for the same reason as Step 4: worst-case, symmetric, monotone, and it can
never discard the most urgent origin. An `absent`/unreadable origin contributes
band 1 (`unknown`), never 0.

Provenance is a **set**, not a first value:

| origin `source` values | rendered `origin_provenance` |
|---|---|
| all `active` | `active` |
| all `archived` | `archived` |
| any combination of the two | `mixed` |
| all `absent` | `absent` |
| some `absent`, some readable | `mixed` + a caveat naming the unreadable ids |

Two mandatory `caveats[]` strings so the reduction is never invisible: one when
origins **disagree** on either axis, naming the origin that set the band; one when
any origin is `absent`. Both raw per-origin values appear in `rationale`.

Whitelist the wrapper across all five touchpoints:

```bash
./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist aitask_backlog_origin_facts.sh
./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist aitask_backlog_origin_facts.sh
```

---

## Step 4 — Scoring: a lexicographic key, not tuned weights

Every component is surfaced per entry. Ordering is a **lexicographic tuple**, so
"affinity must not bury urgent unrelated work" is structural rather than an
accident of weight tuning:

```python
sort_key = (-risk_band, -risk_axes_at_band, -premise_band, -affinity,
            -recency_band, -priority_band, canonical_sort_id)
```

| component | role | encoding |
|---|---|---|
| origin `risk_code_health` / `risk_goal_achievement` | **primary value** | see the combination table below |
| premise validity | freshness weight 1 | `FRESH 2 > SKIP 1 > ASK_STALE 0` |
| in-flight area affinity | strong but **advisory** | `1` if the candidate's paths intersect any in-flight surface, else `0` |
| recency | freshness weight 2 | injected day-ordinal delta, bucketed |
| `priority` | weak, transparent tie-break only | `high 2 / medium 1 / low 0` |
| `effort` | capacity constraint, **not value** | carried for display/filtering; **absent from `sort_key`** |
| `followup_kind` | **not ordering-relevant** | never read by the scorer |

### Combining the two risk axes

`risk-evaluation.md` assesses code-health and goal-achievement **independently**
and forbids blending them into one score. Ordering nonetheless needs a total
order, so the combination is stated explicitly rather than left to whichever
field the implementation happens to read first:

```python
AXIS_BAND = {"high": 3, "medium": 2, None: 1, "low": 0}   # None == absent/unreadable

def axis_band(v):
    v = v or None                       # "" and "-" normalise to absent
    if v not in AXIS_BAND:              # an undeclared value is a bug, not "unknown"
        raise VocabularyError("risk axis: %r" % (v,))
    return AXIS_BAND[v]

a, b = axis_band(rch), axis_band(rga)
risk_band         = max(a, b)
risk_axes_at_band = (a == risk_band) + (b == risk_band)
```

An **undeclared** axis value raises rather than folding into `unknown` — the same
`check_member` discipline `parallel_admission` uses. Silently absorbing a typo'd
level into band 1 would be a fail-open on the primary value signal.

**`max`, and the two axes are peers.** A task is as urgent as its worst axis, and
neither axis outranks the other — `max` is the only combination that is both
symmetric (so `(high, low)` and `(low, high)` are identical) and monotone (so
raising either axis can never lower the rank). `risk_axes_at_band` breaks ties
*within* a band, so `(high, high)` precedes `(high, low)` without either axis
being privileged.

Pin these mixed cases in tests — the symmetric pair especially, since an
implementation that reads only `risk_code_health` passes every same-value case:

| `rch` | `rga` | `risk_band` | `axes_at_band` |
|---|---|---|---|
| high | low | 3 | 1 |
| low | high | 3 | 1 |
| high | high | 3 | 2 |
| medium | absent | 2 | 1 |
| low | absent | 1 | 1 |
| absent | absent | 1 | 2 |
| low | low | 0 | 2 |

**A missing axis is `unknown` (band 1), never zero.** `unknown` sits between
`medium` and `low` deliberately: an unknown risk could be high, so ranking it
below `low` would hide it and above `medium` would over-claim. Only 8 active
tasks carry `risk_code_health:` while 203 archived ones do — the signal comes
from the *origin*, which is usually archived, which is what Step 3 exists for.

Both raw axis values appear verbatim in the entry's `rationale`, and an entry
with **either** axis absent carries a `caveats[]` string naming which one — so
the blend is always visible and overridable rather than an opaque number.

`canonical_sort_id` is `(parent:int, child:int)` so `1569_10` sorts after
`1569_9`. It is a **comparison key only** — the original ref string is what gets
written to the trail.

**Enforce the `followup_kind` decision, don't just state it:** a test that permutes
`followup_kind` across the fixture corpus and asserts **byte-identical** ranking.

---

## Step 5 — Origin quality is carried, not hidden

Every entry states `exact` / `topic` / `unknown`. A `topic` or `unknown` entry is
hedged in **three** places, so it cannot read like an exact one: reduced
`confidence` (Step 2 table), a `caveats[]` string naming the fallback, and the
quality word in `rationale`.

---

## Step 6 — Premise drift behind a replaceable interface

`.aitask-scripts/lib/roadmap_premise.py` — pure, deliberately narrow, advisory,
and the single swap point for t1561. **Do not build a second permanent staleness
framework.**

```python
FRESH, ASK_STALE, SKIP = "FRESH", "ASK_STALE", "SKIP"
REASONS = ("unknown_history", "no_origin", "absent_at_baseline")

def baseline_for(origin_ids, commit_rows) -> tuple  # (sha|None, committed_at|None, reason|None)
def check(origin_ids, origin_paths, commit_rows, baseline) -> PremiseResult
```

Conventions copied from `aitask_verification_stale.sh` (conventions **only** — that
helper reads scope from `file_references:`, which 0 of 483 active tasks carry, and
its baseline from `verification_baseline:`, absent on follow-ups):

```
BASELINE:<sha>|<committed_at>      or  BASELINE:NONE
FILES:<n>
CHANGED:<encoded path>|<n_commits>|<task_ids>
UNKNOWN:<encoded path>|<reason>
DISPLAY:<free-form, last>
DECISION:FRESH|ASK_STALE|SKIP
```

- Every content state returns; only programming errors raise.
- **`UNKNOWN` drives the verdict.** Implement it the way the shell helper does —
  push `UNKNOWN` records into the *same* evidence list as `CHANGED`, and let the
  verdict be a pure emptiness test on that list. A path that cannot be checked
  means the check covers *less* scope than it claims, so `FRESH` would be a false
  all-clear.
- `SKIP` is fail-open and silent.
- Encoding is `%`-then-`|`, injective — **call `vocab.encode_path` / `decode_path`**,
  do not re-implement the rule.
- No `:(literal)` guard is needed and none is added: this interface runs no git.
  Say so in the design record so a reader does not look for it.

---

## Step 7 — Resolution-quality measurement

The true origin of the **132** `topic`-only follow-ups is unknown, so nothing can
measure the fallback's impact on them. The only measurable set is the **40**
carrying both `verifies:` and `anchor:` — and because `verifies:` is written only
by the manual-verification seams, those 40 are all MV-typed, i.e. **not
representative**.

The divergence is not merely "topic is wider": t1497 (exact 3, topic 13, **overlap
0**) and t1513 (exact 4, topic 13, **overlap 0**) show the topic root can be
**disjoint** from the true origin, so the fallback can be *actively wrong*.

Both signals are already in hand — `MEMBER_EXT:<ref>|<created_at>|<anchor>|<verifies csv>|<risk_code_health>|<risk_goal_achievement>`
carries `anchor` and `verifies` **separately**, so the counterfactual needs no new
`followup_origin` API. Rank the corpus twice (once with `verifies:` origins, once
with the `anchor:` root) and count position changes.

Emit per run:

```
ORIGIN_QUALITY:<exact>|<topic>|<unknown>
DEGRADED:<n>|<cause csv>
COUNTERFACTUAL:<n>|<N>|dual_signal_mv_typed
```

- The histogram is **mutually exclusive**. **Never quote the raw `anchor` count**
  (172 today): it double-counts the 40 overlap.
- `COUNTERFACTUAL` is phrased *"n of N dual-signal tasks (MV-typed) would rank
  differently"* and is **never** extrapolated to the 132.

**Enhancement threshold**, stated in the design record: a persisted
`followup_origins:` field is justified when the dual-signal counterfactual shows a
material rank or lane change **and** the corpus-wide `UNCHECKABLE` count
attributable to origin quality is non-trivial. The second condition is the one
that generalises — it is measured over the whole corpus, not the biased 40.

---

## Step 8 — Score components as prose; hedges as `caveats[]`

`entry` is `additionalProperties: false`; `rationale` is `minLength: 1` with **no
maxLength**; `caveats` is an optional array of strings; `rendering_hints` is
**top-level** and scalar-only. So the whole requirement is satisfiable with **no
`schema_version` bump** — which would otherwise touch both schema copies,
`SchemaCopyDrift` (`tests/test_trail_schema.py:68`, a **byte-for-byte** compare),
the validator and the goldens.

**Settled: prose in `rationale`, hedges in `caveats[]`, no bump.** t1569_6 authors
against this.

---

## Step 9 — Ship the design record

`aidocs/framework/background_work_roadmap.md`, covering: the scoring model, its
lexicographic key and the **two-axis risk combination rule** (`max`, symmetric,
with the tie-break); the two freshness weights and the **premise→confidence
ceiling** with its stated `SKIP` tension; the Step-1 baseline decision — including
**which commit class qualifies as a landing** and why, its rejected alternative,
and the accepted `DELETED:` narrowing; t1569_3's narrowing
rule and hub threshold; the measured resolution-quality residual and the
enhancement threshold; **the residual race — `CLEAR` reserves nothing**; and the
trail encoding contract below.

Follow `aidocs/framework/documentation_conventions.md` — current-state-only prose.
Present every corpus number as a **dated measurement** (2026-08-31), not a
standing fact.

### Trail encoding contract — all existing vocabulary, no schema change

- **depth `deep`, not `lite`.** A `lite` document must omit `observations`,
  `relations`, `exclusions` and per-entry `evidence_refs` and carry exactly one
  `evidence` record — and this contract needs all of them. `lite` is the
  **default**, so t1569_6 must pass the deep flag and `aitask_trail_depth.sh
  validate --expect-depth deep`.
- **waves**: 1 parallel-safe, 2 coordination, 3 unresolvable. `wave.entries` is
  `minItems: 1`, so **build only non-empty waves** and number `ordinal` 1..n in
  lane order (strictly increasing, not necessarily contiguous with the lane
  numbering). Coordination is **0** on the live corpus today, so an
  emit-always-three-waves author produces an invalid document on the very first
  real run.
- **`relations[]`**: `{type: coordinates_with, provenance: advisory}`, backlog →
  in-flight. Endpoints must resolve to referenced tasks.
- **`observations[]`**: `in_flight_conflict` | `shared_surface_collision` |
  `stale_premise`. Required: `observation_id`, `kind`, `statement`,
  `evidence_refs` (**`minItems: 1`**). `affects` is *optional* with no `minItems` —
  carry it anyway, but the mandatory-non-empty field is `evidence_refs`.
- **`evidence[]`**: `source_type: command_output`, naming the gatherer / batch-map
  / origin-facts invocations. All five of `evidence_id`, `source_type`, `ref`,
  `observed_at`, `summary` are required; `observed_at` matches
  `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?Z$`.
- **`snapshot.followup_kind`**: **omit the key** when the gatherer's `MEMBER:`
  value is the sentinel `unknown` or `invalid` — writing a sentinel in invalidates
  the whole document.
- Refs are canonical `<project>#<id>` copied **byte-identically** from the
  gatherer; digest provenance depends on it.

---

## Step 10 — Create the t1561 adoption follow-up

Consume t1561's generalized staleness mechanism in place of Step 6's local
interface. `--followup-of 1569`, **`depends: [1561, 1569_5]`** — spawned follow-ups
ship with no `depends:` unless it is set explicitly. t1561 is still `Ready`, so the
adoption is genuinely pending.

---

### Post-phase (risk mitigations)

**`purity_and_whitelist_guard`** — after implementation, add `roadmap_policy` and
`roadmap_premise` to `PURE_MODULES` in `tests/test_parallel_admission_purity.py:25-26`
and widen that module's docstring to say it guards the pure roadmap surface too.
Then run `aitask_audit_wrappers.sh audit-helper-whitelist aitask_backlog_origin_facts.sh`
and confirm it emits no `MISSING:` line. Both are executable checks, not review
items.

**`encode_a_real_document`** — build the **end-to-end integration fixture** of
Verification #12 and let it author the trail document, rather than hand-writing
one. It drives the real path (`ORIGIN_FACT:` → `roadmap_policy` →
`parallel_admission.decide` → emitted document) and produces waves, `entries`,
`relations` with `coordinates_with`/`advisory`, `observations` with non-empty
`evidence_refs` (including `stale_premise`), `evidence` with
`source_type: command_output`, and `rendering_hints.depth: deep`. A hand-authored
document proves only that a human can write valid JSON; this proves the code
emits it. Run:

```bash
./.aitask-scripts/aitask_trail_depth.sh validate <file> --expect-depth deep   # VALID:<trail_id>
```

This is the only thing that proves the encoding contract **before** t1569_6
depends on it, and it catches the empty-wave (`entries` `minItems: 1`) and
sentinel-`followup_kind` traps by construction. Keep the document as a committed
fixture so a later contract edit has to update it deliberately.

---

## Verification

```bash
bash tests/run_all_python_tests.sh --test-dir tests    # last line ONLY
python3 -m unittest tests.test_roadmap_policy tests.test_roadmap_premise -v
python3 -m unittest tests.test_parallel_admission_purity -v
shellcheck .aitask-scripts/aitask_backlog_origin_facts.sh
```

`tests/run_all_python_tests.sh` piped through `tail` returns `tail`'s status —
use `set -o pipefail` or read `${PIPESTATUS[0]}`.

**Purity is enforced, not asserted.** Add `roadmap_policy` and `roadmap_premise`
to `PURE_MODULES` in `tests/test_parallel_admission_purity.py:25-26` and widen its
module docstring to say it guards the pure roadmap surface too. That file's
AST scan + poisoned-`subprocess` import is the existing machinery; extending the
one list is cheaper and less error-prone than duplicating it, at the cost of a
filename that now under-describes its scope — noted rather than renamed.

Required tests:

1. **Overlap / no-overlap / missing-plan / all-phantom-plan** fixtures. Simulated
   on the live corpus the coordination lane gives **0**, so these synthetic
   fixtures are the only proof it fires at all.
2. **`followup_kind` permutation → byte-identical ranking.**
3. **Determinism**: same fixture twice → byte-identical output. Copy
   `tests/test_parallel_admission.py:427` (`test_determinism_same_input_twice_is_byte_identical`).
4. The Step-7 measurement asserted in a fixture where the exact and topic file sets
   **provably differ**, so it cannot pass vacuously at zero.
5. The Step-1 rejected alternative as a failing case: a follow-up whose `created_at`
   precedes its origin's landing commit — the chosen rule yields that commit as the
   baseline, the rejected rule yields a pre-landing baseline that reports the
   origin's own landing commit as drift.
6. **Baseline commit class**: a fixture whose origin has a code landing at `T1`
   and a **later** `(tNN)`-tagged commit at `T2` touching only `aitasks/`. Assert
   the baseline is `T1`'s sha, and that a code change at `T1 < t < T2` is still
   reported as `CHANGED:`. A sibling fixture whose origin has *only* task-data
   commits must yield `DECISION:SKIP` with reason `metadata_only` — distinct from
   `unknown_history`.
7. **Wave construction**: a corpus with zero coordination entries emits **two**
   waves, not an empty one, and validates.
8. **Risk-axis combination**: the mixed-case table in Step 4, asserted row by row.
   The `(high, low)` / `(low, high)` pair must produce **identical** keys — an
   implementation reading only `risk_code_health` passes every same-value case and
   fails exactly here.
9. **Premise confidence ceiling**: `ASK_STALE` never yields `high` or `medium`
   confidence and always emits a `stale_premise` observation and a caveat;
   `SKIP` never yields `high` and emits **no** per-entry caveat; the lane is
   unchanged in both cases.
10. **Confidence mapping** table pinned in both directions, including that no
   `topic` entry ever reaches `high`.
11. **Negative controls** for 2 and 3: a deliberate ranking change *must* change the
   output, so the byte-identity assertions cannot pass vacuously.
12. **End-to-end integration fixture (deterministic).** One fixture that drives the
   **whole real path** in a single pass — synthetic `ORIGIN_FACT:` records +
   `INFLIGHT*` records + `COMMIT:`/`TASKFILES:`/`STATUS:` rows → `roadmap_policy`'s
   public entry point → `parallel_admission.decide` → the emitted trail document —
   and asserts **together**, on the same entries: wave/ordinal, `classification`,
   `confidence`, `caveats[]`, `observations[]` (including the `stale_premise` one),
   `evidence[]`, and the score components in `rationale`. Then validate the emitted
   document with `aitask_trail_depth.sh validate --expect-depth deep`.

   Units, a hand-authored document and a shape smoke can all pass while the real
   output is wrong: a record-parser mismatch or an omitted `data_tracked` is
   invisible to every one of them. Two **negative controls** make that
   non-vacuous — each must change the result, and the test asserts the change:
   - omitting `data_tracked` (task-data paths collapse to `phantom`, so a real
     collision disappears);
   - flipping one axis of a mixed `(rch, rga)` pair, which must not change the
     ranking (symmetry), while raising it must.
13. **Multi-origin reduction**: a fixture reproducing the live shapes — origins
    disagreeing on one axis, on both, an `absent` origin among readable ones, and
    a mixed `active`/`archived` set. Assert the reduced band is the **max**, that
    the disagreement and absent caveats fire, that `origin_provenance` is `mixed`,
    and — the discriminating case — that a **reordered** origin list produces a
    byte-identical result. A first-origin implementation passes every
    single-origin test and fails exactly that assertion.
14. **Real-collector integration.** Verification #12 starts from *synthetic*
    `ORIGIN_FACT:` lines, so it proves the policy path but **not** that
    `roadmap_origin_facts.py` emits records that path accepts — an escaping,
    sentinel, archive-lookup or field-order mismatch passes every other test here
    and breaks real runs. So: build a temp repo with **active task files and a
    real archived bundle**, invoke the **wrapper** `aitask_backlog_origin_facts.sh`
    (not the module), and feed its stdout **verbatim** into the same policy path as
    #12, asserting the same fields.

    Include one task id and one origin whose values contain `|` and `%`, so the
    `%`-then-`|` encoding is proven to round-trip **producer → consumer**, not just
    within the encoder's own unit test. This module shells out, so it is a test,
    not a `PURE_SOURCES` member — keep it out of the purity guard's list.
15. A **live smoke** asserting shape only — exit 0, histogram present, counts sum to
   the candidate total — and **never** lane counts. A live-corpus assertion belongs
   on the invariant, never on the current verdict.

Fixture helpers to reuse: `tests/test_parallel_admission.py`'s `enum()`,
`surface()`, `claim()`, `build()` with frozen `NOW`; `tests/test_task_file_sets.py`'s
`record(sha, ct, message, paths)` for synthesising `COMMIT:`/`TASKFILES:` input;
`tests/test_trail_gather.py`'s `InflightCase.snap_inflight()` for `INFLIGHT*` lines.

Post-implementation cleanup, archival and merge run at **Step 9** of the shared
task-workflow.

---

## Risk

### Code-health risk: medium

- The premise-drift interface is a **second** staleness mechanism alongside
  `aitask_verification_stale.sh`, and t1561 is meant to replace both. Left
  unbounded it becomes permanent duplication · severity: medium · → mitigation:
  inline pre-phase `narrow_the_premise_seam`
- New surface is wide for one slice: two pure modules, one impure collector, a new
  whitelisted `.sh` helper (5 touchpoints), and a design record · severity: medium
  · → mitigation: inline post-phase `purity_and_whitelist_guard`
- The trail encoding contract is authored **here** but executed **in t1569_6**, so
  a contract error surfaces one slice later, in prose rather than code · severity:
  medium · → mitigation: inline post-phase `encode_a_real_document`

### Goal-achievement risk: medium

- The coordination lane is **unexercisable on the live corpus** (0 today), so its
  correctness rests entirely on synthetic fixtures. A fixture that encodes the same
  misunderstanding as the code passes · severity: high · → mitigation: inline
  post-phase `encode_a_real_document`
- The resolution-quality counterfactual is measured on a **biased 40-task MV-typed
  sample** and feeds an enhancement threshold. Over-reading it would justify a
  persisted `followup_origins:` field on evidence that does not generalise ·
  severity: medium · → mitigation: none (accepted residual — bounded by
  Step 7's never-extrapolate wording and Verification #4)
- Scoring quality cannot be validated against ground truth — there is no oracle for
  "the right order". The lexicographic key makes the *policy* testable, but not
  *correct* · severity: medium · → mitigation: none (accepted residual — the ranking is
  advisory and every component is shown per entry so a human can override it)

### Planned mitigations

```
- timing: pre-phase | name: narrow_the_premise_seam | type: refactor | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — second staleness mechanism becomes permanent duplication | desc: Pin roadmap_premise's public surface to two functions, name t1561 as the substitution point and DELETED: as an accepted narrowing, and test that nothing else is exported.
- timing: post-phase | name: purity_and_whitelist_guard | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — wide new surface for one slice | desc: Add both pure modules to PURE_MODULES and confirm all five helper-whitelist touchpoints emit no MISSING: line.
- timing: post-phase | name: encode_a_real_document | type: test | priority: high | effort: medium | inline_risk: low | added_complexity: medium | addresses: goal-achievement — coordination lane unexercisable on the live corpus; code-health — encoding contract authored here but executed in t1569_6 | desc: Build the end-to-end integration fixture (Verification #12) that drives ORIGIN_FACT records through roadmap_policy and parallel_admission.decide into a complete trail document, assert lane/confidence/caveat/observation/evidence together, validate it with --expect-depth deep, and keep it committed with its two negative controls.
```

`encode_a_real_document`'s metrics alone would lean spawn (`added_complexity:
medium`). It is inlined deliberately: a spawned "after" task lands *after*
t1569_6 may already have built against the contract, which is precisely when the
proof is worthless.

### Reassessment after inlining and the review round

Steps 1–2 re-run against the augmented plan. Both levels **stay medium**.

The review round materially reduced goal-achievement risk without changing its
level: the two-axis combination rule and the premise ceiling remove the "an
incidental implementation choice decides the ranking" failure, and the end-to-end
fixture removes "every check passes while real output is wrong". What keeps it at
medium is unchanged — there is still no oracle for whether the resulting order is
*good*. The second round closed the last two places where a plausible
implementation could be silently wrong and still green: multi-origin reduction
(28% of exact follow-ups, 13 of them with genuinely conflicting levels) and the
untested producer→consumer seam. Code-health stays medium for the same reason as before, slightly
reinforced: the plan now carries three more decision tables, and a table is
another thing that can drift from the code implementing it (mitigated only by the
row-by-row tests in Verification #6/#8/#9). The
three phases bound each risk with executable checks rather than removing it: the
premise seam is pinned but still a second mechanism until t1561 lands;
`ORIGIN_FACT:` is a new cross-slice line protocol whose cost surfaces in t1569_6;
and validating a real document proves the encoding *shape*, not that the
verdict→lane mapping matches intent. The scoring-quality bullet is unmitigated by
design — there is no oracle for "the right order", which is why every component is
shown per entry.

---

## Final Implementation Notes

Landed as planned. Seven things are worth recording, six of them deviations or
measurements the plan could not have contained.

### What the post-phase mitigation actually caught

`encode_a_real_document` earned its place immediately. The first complete
document failed validation with `relation_endpoint: endpoint 'aitasks#900' not
referenced anywhere else in the document` — a `coordinates_with` relation may
only point at a task the document already mentions, and an in-flight task has no
entry of its own. The fix is semantically right rather than a workaround: the
`in_flight_conflict` observation now carries **both** ends in `affects`, which is
true (the collision affects the in-flight task too) and is one of the four places
the validator resolves an endpoint against. Without the mitigation this would
have surfaced inside t1569_6, in prose, one slice later — exactly the risk the
`## Risk` section named.

### Deviations from the approved plan

1. **`REASONS` split into `BASELINE_REASONS` + `PATH_REASONS`** (union kept as
   `REASONS`). Two of the reasons describe why no *baseline* exists and two
   describe why one *path* could not be checked; one flat bag made the record
   protocol ambiguous about which field a reason belonged to.
2. **`PATH_REASONS` gained `no_index_history`** beside `absent_at_baseline`. "The
   path has no commit row at all" and "rows exist, but none at or before the
   baseline" are genuinely different states with different remedies. Both drive
   the verdict, as `UNKNOWN` must.
3. **The risk reduction includes the candidate's own axis** alongside its
   origins'. The parent task's signal is "`risk_code_health:` on the task **or**
   its origin", and folding both into the same `max` keeps the rule symmetric and
   monotone instead of needing a precedence tie-break.
4. **The collector emits a row plus a stderr warning for a named-but-missing task
   id.** Returning silence would have made "no origin facts", "no such task" and
   "filtered out" indistinguishable — the infer-from-an-absent-line hazard the
   record format exists to prevent. The row carries the fact; stderr carries the
   caller bug, so the line protocol stays clean.
5. **Verification #12 lives in its own module**, `tests/test_roadmap_integration.py`,
   because it is pure; #14 and #15 live in `tests/test_roadmap_origin_facts.py`,
   the one roadmap module that shells out.

### A measurement that changed nothing, recorded so it is not re-litigated

Task-data paths (a plan file, a task file) are inside the checked scope, so plan
churn can register as premise drift. Measured over the live corpus: of 169
follow-ups with a resolvable origin and file set, **zero** are `ASK_STALE` *only*
because of task-data churn — every stale verdict has real code churn behind it.
Narrowing the checked scope to code paths was therefore considered, measured and
**not** done. The `data_prefixes` parameter still governs the *baseline* rule,
where it is load-bearing.

Separately: 153 of those 169 land on `ASK_STALE` and 14 on `SKIP`, so the premise
band is nearly constant across today's corpus and contributes almost nothing to
*ordering*. Its value is the per-entry hedge — the confidence ceiling and the
caveat — not discrimination. Recorded in the design record as a dated
"what this does not buy".

### Suite status

`bash tests/run_all_python_tests.sh --test-dir tests` → `PYTHON SUITE: PASSED
(runner=pytest, exit=0)`, 6144 passed.

One run in four failed on
`tests/test_minimonitor_startup_input_latency.py::MountWindowProbeTests::test_mount_returns_while_the_window_probe_is_still_blocked`.
It is a **pre-existing load flake, not a regression**: it passes 3/3 in
isolation, references nothing this task touched, and asserts a mount-latency
bound that a loaded worker pool invalidates. Another agent was actively editing
board code in the same checkout throughout (t1603_3), which is the contention.

### Concurrency note

The working tree carried a concurrent session's changes to
`.aitask-scripts/board/aitask_board.py`, `tests/test_board_dialog_run_dispatch.py`,
`tests/test_board_gate_digest_budget.py` and `tests/test_board_inflight_planned_lane.py`
(t1603_3). Every commit for this task was made path-scoped so none of it was
swept in; the five whitelist config files were diff-checked to confirm they
carried only this task's entry.

### Post-review fixes (four confirmed defects)

A review round after implementation found four real defects. All were reproduced
before being fixed, and each now has a test that fails without the fix.

1. **`counterfactual_rank_delta` measured a proxy while claiming the metric.**
   It ignored its ranking argument entirely and counted *file-set inequality*,
   which overstates the effect — two different surfaces routinely leave every
   position and lane untouched — and the enhancement threshold for a persisted
   direct-origin field keys off that number. Rewritten to compare each
   dual-signal task's **actual position and lane** across two real policy runs,
   with `dual_signal_refs()` as its companion. `CounterfactualTests` pins the
   discriminating fixture: **sets differ, ranking does not → 0**. That test reads
   1 if the metric ever regresses to the proxy.
2. **A resolved baseline over an empty file surface returned `FRESH`** — "all 0
   origin file(s) unchanged", which reads as verified and lifted the confidence
   ceiling to `high` for a task whose premise was never examined. That is exactly
   the false all-clear the module's own `UNKNOWN`-drives-the-verdict rule
   forbids, and it is reachable (a candidate whose batch-map status is
   `NO_FILES`). Now `SKIP` with a new `SCOPE_REASONS` value `empty_scope`, an
   `UNCHECKED:empty_scope` record, and `PremiseResult.reason`. Deliberately not
   `ASK_STALE`: there is no evidence the premise moved, only nothing to check.
3. **`to_trail` emitted `waves: []` for a zero-candidate scope**, an artifact
   that can never validate, while the function's docstring promised a complete
   document. Now raises `EmptyRoadmapError` — what a zero-candidate run means is
   the caller's decision, not the encoder's to guess.
4. **The design record's opening contradicted the implemented contract**: it said
   "two-lane" (there are three) and "safe to start" (the contract is "no known
   conflict at check time", and the run-summary rules forbid the word "safe").
   Since this is the document t1569_6 implements against, it could have
   propagated both a missing lane and an unsafe guarantee. Rewritten, and the
   three fixes above are now documented there too.

Recovered from one self-inflicted error along the way: a scripted edit sliced the
policy module from `counterfactual_rank_delta` to EOF, deleting the trail
encoder. Restored from a scratch backup and re-applied both later fixes; the 60
unrelated tests passing immediately afterwards confirmed the restore was faithful
before the two counterfactual tests were rewritten.

Full suite re-run after all four fixes: `PYTHON SUITE: PASSED (runner=pytest,
exit=0)`.
