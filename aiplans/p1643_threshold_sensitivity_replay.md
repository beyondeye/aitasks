---
Task: t1643_threshold_sensitivity_replay.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1643 — Threshold sensitivity replay

Risk-mitigation ("after") follow-up for t1569_3. Retires two goal-achievement
risks recorded in `aiplans/archived/p1569/p1569_3_shared_parallel_admission_checker.md`.

## Context

t1569_3 shipped the shared parallel-admission checker with `HUB_THRESHOLD = 10`,
chosen from **one corpus snapshot measured during a single session**. Its plan
flags two goal-achievement risks:

1. the demotion model and its threshold rest on that snapshot, and the grading it
   produces is what t1569_4 blocks on;
2. the checker can be entirely correct and still measure ~100% `UNCHECKABLE`,
   because a task claimed but not yet planned blocks every candidate — a reviewer
   reading the headline rate alone concludes the design failed.

Both are live. Measured during planning:

```
replay --from plan --lock-freshness require-fresh   → RATES:118|0|0|2|116
                                                      CAUSE_RATE:no_plan|118
```

**98% UNCHECKABLE**, caused by three unplanned in-flight claims — `1641`, `1642`,
and **`1643` itself, the measuring session**. Today the live replay is degenerate:
the same verdict for every candidate at every threshold, carrying no decision.
That is risk (2) materialising.

### This task is evidence-only

**It does not decide the threshold.** t1643's own goal says it "produces the
numbers t1569_4 needs to decide"; the decision rule — what hard-stop versus
confirmation trade-off is acceptable — is t1569_4's, because only t1569_4 knows
what `block` will do with each verdict. This plan therefore reports the
**composition** that feeds such a rule and states no verdict on `HUB_THRESHOLD`.

That distinction is load-bearing, not pedantic. Recall of `CONFLICT ∪
CLEAR_CAVEATED` is threshold-invariant, but the two are **not
interchangeable to the consumer**: t1569_4 makes `CONFLICT` a stop-and-replan in
both `block` and `warn`, while `CLEAR_CAVEATED` is at most a confirmation the
agent can click through. So the threshold decides whether a real collision
hard-stops or merely prompts — and measured over the archived corpus that split
moves enormously (below). A summary reporting only invariant recall would hide
exactly the quantity the decision turns on.

### Two measurements, two populations

The task text asks for rates, recall, precision and `CAUSE_RATE` "over the live
corpus". Recall and precision **cannot** come from the live replay — in-flight
work has landed nothing, so there is no ground truth. Stating the split
explicitly rather than silently reinterpreting the ask:

| measurement | population | yields |
|---|---|---|
| **live sweep** | the ~118 candidates with an active plan | `RATES:` + `CAUSE_RATE:` per threshold |
| **archived-pairs oracle** | archived tasks with both a plan and landed files, all pairs | precision, recall, **composition** per threshold |

Ground truth is the same oracle t1569_3 used: over archived tasks, did the two
tasks' actually-landed file sets (`TASKFILES:` from
`aitask_revert_analyze.sh --batch-map`) intersect?

### Prototyped results (planning-time, 2026-08-30/31 — to be reproduced by the tool)

Archived-pairs oracle, `full` scope, 281 tasks / 39 340 pairs. Shares are **of
all true collisions**; the `pre-implementation` column is the same measurement
with the corrected cutoff:

| hub threshold | hard-stopped (`CONFLICT`) | downgraded (`CLEAR_CAVEATED`) | missed (`CLEAR`) | precision(`CONFLICT`) | hard-stopped, `pre-impl` |
|---|---|---|---|---|---|
| 8 | **28%** | 62% | 9% | 46% | 27% |
| 10 (shipped) | **32%** | 59% | 9% | 45% | 30% |
| 20 | **67%** | 23% | 9% | 25% | 65% |
| 50 | **72%** | 18% | 9% | 26% | 70% |

Four findings the tool must reproduce:

- **Recall of `CONFLICT ∪ CLEAR_CAVEATED` is threshold-invariant** (91% here;
  the missed 9% is constant). This is the demotion model's guarantee made
  measurable — the threshold re-*grades*, it never drops — and it retires
  risk (1)'s "a wrong threshold costs recall" concern.
- **But the grading it costs is large and is the decision-relevant quantity.**
  At the shipped threshold only ~a third of real collisions hard-stop; at 20,
  two-thirds do, at a 20pp precision cost. Whether that trade is acceptable is
  t1569_4's call.
- The unnarrowed control agrees with t1569_3's published unnarrowed row on
  precision (~28%) and recall (~90%), cross-validating the harness against the
  original method.
- **Archived plans are contaminated by hindsight** — they carry
  `## Final Implementation Notes` written *after* the work landed. Cutting the
  body there approximates the plan as it stood at admission time and moves recall
  **91% → 88%** (missed 9% → 12%), leaving the threshold ranking unchanged.
  t1569_3's figure is optimistic; the `pre-implementation` scope is the honest
  admission-time one.

  **88% is a conservative floor, not an exact figure.** The cut fires on the one
  unambiguously post-work heading only (see Step 1). Other post-hoc sections
  survive it — notably `## Post-Review Changes`, present in 79 archived plans, of
  which 73 sit *before* `## Final Implementation Notes`. Cutting there too was
  rejected because it is not *proven* post-work, and a wrong cut discards genuine
  admission-time paths. So the residual bias runs in the optimistic direction:
  true admission-time recall is **at most** 88%.

### Out of scope

- The `parallel_admission: block|warn|off` knob and the helper whitelist entry —
  both t1569_4.
- Any change to `decide`, the verdict vocabulary, `HUB_THRESHOLD`, or a default.
  This task measures; `check` behaviour is unchanged.

---

## Step 1 — New pure module `.aitask-scripts/lib/parallel_admission_sweep.py`

Pure (no `os`/`time`/`subprocess`), importing only `parallel_admission`. Holds
the confusion-matrix math and the single place a two-task comparison is built, so
the harness cannot drift from `decide`.

Module docstring states the invariant it exists to pin (recall invariance under
demotion) and that the numbers themselves are volatile corpus statistics
deliberately **not** frozen here.

- `PlanExtraction` — frozen dataclass `(ref, paths, resolution, tokens_total,
  tokens_dropped)`. **Defined here (pure) and populated by the impure collector**
  — this is the one dataflow that carries phantom-token accounting out of
  extraction, so nothing re-extracts to count drops (see Step 3).
- `Confusion` — frozen dataclass of **counts only**: `pairs`, `colliding`,
  `verdicts` (dict), and per-verdict true-positive tallies `tp_conflict`,
  `tp_caveated`, `missed`, plus `pred_conflict`, `pred_flagged`, `tp_flagged`.
  No floats stored.
- Derived accessors returning `None` on a zero denominator (an empty population
  must never read as 100%): `precision_conflict`, `recall_flagged`,
  `share_hard_stopped`, `share_downgraded`, `share_missed`.
- `pair_input(cand_surface, other_ref, other_surface, touch_counts, hub_threshold, now)`
  → `AdmissionInput`. Fixed neutral scaffolding so only the surfaces and the
  threshold vary: three `ok` probes, `LockEvidence("require-fresh","fetched",0)`,
  two `ok` corpora, one `live` / `same_host=True` / `claim_at_s=now` blocking
  claim. Every knob that could silently yield `UNCHECKABLE` is pinned healthy, so
  the three-way grading is the only signal.
- `confusion(population, touch_counts, hub_threshold, now=0)` — `population` is
  `((ref, plan_surface, landed_paths_frozenset), ...)`; iterates
  `itertools.combinations`, calls `pa.decide(pair_input(...))`, tallies.
- `POST_WORK_HEADINGS` — the named set the cut fires on, currently the single
  entry `Final Implementation Notes`. One constant, so a future task can extend it
  *with proof* rather than a second regex growing at a call site.
- `cut_post_implementation(body)` — body truncated at the first heading in
  `POST_WORK_HEADINGS` (multiline regex, any heading depth); unchanged when none
  is present.

  **`Verification pass` is deliberately NOT a cut marker.** A re-verification
  section is written when a plan is *re-picked*, i.e. **before** the
  implementation it precedes — in `p1569_3` itself it sits at line 32, ahead of
  the entire Step 1–8 body. Cutting there would discard the whole plan and drop
  the task from the population for lack of a resolved surface. Measured: 11 of
  298 archived plans carry such an early heading, and cutting on it removed **9
  tasks** from the population outright and inflated the reported hindsight
  correction from 3pp to 6pp. The 85% figure an earlier draft of this plan
  reported was that artefact, not a measurement.

## Step 2 — `replay`: one snapshot, many thresholds, both populations

**The live half of this task is unsound without this step.** `replay` today takes
a single `--hub-threshold` and re-collects state on every invocation (`main` calls
`_BATCH_MAP` and `collect` per run). Four invocations at 8/10/20/50 would
therefore judge four *different worlds* — and the population demonstrably moves on
this box: t1569_3 saw CLEAR go 48% → 58% in an hour with no code change, and the
archived corpus grew 279 → 281 *during this planning session*. A rate difference
between two such runs cannot be attributed to the threshold, which is the only
question the task asks. `_respin` already guarantees one snapshot **within** an
invocation; the fix is to make the whole sweep one invocation.

In `.aitask-scripts/lib/parallel_admission_collect.py`:

- **`--thresholds <csv>` on `replay`** — sweeps within the single collected
  snapshot. `_respin` already rebuilds the `AdmissionInput` per candidate; it
  gains a `hub_threshold=None` override so the per-(candidate, threshold) re-aim
  is the same operation with one more field varied. No second collection, no
  second verdict path.
- **Mutually exclusive with `--hub-threshold`, exit 2.** Accepting both leaves
  which one wins ambiguous, and a silently-losing threshold is precisely the
  accepted-and-ignored hazard `--plan` already dies on for `replay`.
- **`--candidates auto`** — derives the list from the active plan files
  (`aiplans/p*.md` + `aiplans/p*/p*_*.md` → task ids), so the measurement is one
  reproducible command rather than an ad-hoc shell pipeline whose population
  nobody can reconstruct later. `<file>` and `-` keep working unchanged. Echo
  `CANDIDATES:<n>|<auto|file>` so the record says which population was measured.
- **`--exclude-no-plan`** — derives the excluded set **from the collected base
  snapshot itself**, after `collect()` has built it and before any verdict is
  computed. Naming the ids by hand cannot work: obtaining them needs a prior
  `check`/`replay`, which is a *second collection*, and between the two a claim
  can appear, gain a plan, or vanish — all three observed on this box during this
  session, when `1641`/`1642`/`1643` materialised mid-planning. A hand-listed set
  can therefore leave the "counterfactual" still `UNCHECKABLE` via a claim that
  arrived after the list was taken, or exclude a task that has since planned.
  Deriving it inside the one snapshot makes the exclusion and the measurement the
  same observation.

  **The predicate is `pa.tier(claim, …) == "blocking"` and
  `claim.surface.resolution == "no_plan"`** — both halves required, and both
  reusing the canonical functions rather than restating eligibility:
  - the resolution check matches `decide` exactly, because for a blocking claim
    `decide` appends the cause as `surf.resolution` itself, so
    `resolution == "no_plan"` *is* the set producing
    `UNCHECKABLE_CAUSE:inflight:<id>|no_plan`;
  - the tier check is not cosmetic. `tier` returns `excluded` for a provably-dead
    holder however recent its claim, and such a claim drives no cause at all.
    Live right now: `1555_2` and `1576` are `no_plan` **and dead**, while only
    `1641`/`1642`/`1643` force the `UNCHECKABLE`. Without the tier filter
    `EXCLUDED:` would name five ids where three matter, and the record would
    misdescribe the counterfactual it reports.

  Sibling causes are deliberately **not** swept up: `all_phantom` (t259 today) is
  a plan that resolves to nothing — a genuine evidence gap, not a mid-claim
  artefact — and excluding it would answer a different question than the one this
  flag is named for. `--exclude` and `--exclude-no-plan` may be combined; the
  `EXCLUDED:` line lists the canonical, sorted union actually applied.
- **`--exclude` / `--exclude-no-plan` emit *both* populations from the one
  snapshot** (see below), so a counterfactual rate can never be reported without
  its unexcluded twin. This turns the "report it alongside, never instead of"
  rule from a discipline the operator must remember into a property of the
  output.

Output. The **single-threshold path is unchanged** — `RATES:` / `CAUSE_RATE:`
keep the exact shape t1569_3 shipped and the existing tests pin. The
threshold-qualified lines appear **only** under `--thresholds`:

```
SNAPSHOT:<collected_at_epoch>|<n_inflight>
CANDIDATES:<n>|<auto|file>
EXCLUDED:<canonicalised csv>                       # only with --exclude
RATES_AT:<th>|<n>|<clear>|<cc>|<conflict>|<unch>
CAUSE_RATE_AT:<th>|<cause>|<n>
RATES_AT_EXCL:<th>|<n>|<clear>|<cc>|<conflict>|<unch>    # only with --exclude
CAUSE_RATE_AT_EXCL:<th>|<cause>|<n>                      # only with --exclude
```

One invocation therefore produces the entire live table — every threshold, both
populations, one world.

## Step 2b — `--exclude` scoping

In `.aitask-scripts/lib/parallel_admission_collect.py` `_parse_args`:

- Add `--exclude <csv>` (canonicalised via `pa.canonical_ref`) and the derived
  `--exclude-no-plan` to the flag table. **Both are `replay`-only** — `replay` is
  the only verb with a live in-flight claim set to filter — and the rejections
  below apply to both.
- **Rejected on `check`, exit 2**, message pointing at `replay` — same shape and
  reasoning as the existing threshold floors (`_parse_args` "SAFETY THRESHOLDS
  ARE ONE-WAY ON `check`" block). Excluding an in-flight task at an admission
  point hides a real collision: fail-open, the one direction that block forbids.
- **Rejected on `sweep` too, exit 2**, for a different reason that the message
  must state: `sweep`'s population is archived pairs, which has no in-flight
  claim set at all, so the flag has nothing to filter. A shared parser that
  accepted it would silently ignore it and report the *full* archive while the
  operator believed a population had been excluded — the same
  "accepted-and-ignored" hazard `--plan` already dies on for `replay`. (To
  exclude archived tasks would need a separate, explicitly designed population
  filter with its own output line; that is not in this task.)
- On `replay`, drop the named refs from the claim set `_respin` returns. Under
  `--thresholds` this produces the paired `*_EXCL` rows of Step 2; under a single
  threshold it produces `RATES:` for the excluded population plus `EXCLUDED:`.

Without this the live sweep is unusable: excluding only the measuring session
(`1643`) changes nothing, because `1641` and `1642` each independently force
`UNCHECKABLE` — verified during planning. The honest decomposition is "exclude
every unplanned in-flight claim", reported *alongside* the unexcluded number,
never instead of it.

## Step 3 — `sweep` verb

New verb in the same CLI; the wrapper already forwards `"$@"`, so only its header
comment needs the new verb.

```
sweep [--thresholds 8,10,20,50] [--plan-scope full|pre-implementation] [--root .]
```

**Extraction dataflow (one extractor, no duplication).** Add a collector function
`plan_extraction(ref, path, tracked, dirs, body_transform=None)` returning the
pure `PlanExtraction` record: it reads the file, applies `strip_frontmatter`, then
`body_transform` when given, runs `plan_paths.extract`, partitions tokens by
`plan_paths.classify`, and reports both the kept paths and `tokens_dropped`.
`surface_from_plan` is **reimplemented as a thin delegation to it**, preserving
its current `(surface, stripped)` return so `check`, `replay` and t1569_5 call
sites are untouched. The drift probe reads `tokens_dropped` off the same record
that produced the surface — it never re-extracts, so the count cannot disagree
with the surface it describes.

Population = archived tasks having **both** a resolved archived-plan surface and
a resolved non-empty `TASKFILES:` set. `--plan-scope pre-implementation` passes
`cut_post_implementation` as the `body_transform`.

Line protocol (positional, house style; counts, not rates):

```
SWEEP_SCOPE:<full|pre-implementation>
SWEEP_POP:<tasks>|<pairs>|<colliding>
SWEEP_DRIFT:<tasks>|<tokens_kept>|<tokens_dropped>
SWEEP:<th>|<clear>|<clear_caveated>|<conflict>|<uncheckable>|<pred_conflict>|<tp_conflict>|<tp_caveated>|<missed>
SWEEP_METRIC:<th>|<precision_conflict>|<recall_flagged>|<share_hard_stopped>|<share_downgraded>
```

`SWEEP_METRIC` values are 4dp, or `-` when undefined. Misuse (bad `--thresholds`,
non-positive threshold, unknown `--plan-scope`) exits 2, matching the contract.

## Step 4 — Tests

`tests/test_parallel_admission_sweep.py` (pure, fixture-driven):

- **Symmetry** — `verdict(A,B) == verdict(B,A)`, so counting unordered pairs is
  proven sound rather than assumed.
- **Arithmetic** — a hand-built 4-task population with known landed sets pins
  exact counts, precision, recall and all three composition shares.
- **Recall invariance** at `1, 8, 10, 20, 50, 10**9`, *paired with a negative
  control asserting precision and `share_hard_stopped` DIFFER across the same
  thresholds*. Without the control the invariance test passes on any degenerate
  fixture.
- **Monotonicity** — `pred_conflict` non-decreasing in the threshold.
- **`cut_post_implementation`** — three fixtures, covering both directions:
  - cuts at `## Final Implementation Notes`, and does so in a body where the cut
    **provably changes the extracted path set and the resulting counts** (a cut
    that silently did nothing would leave the whole `pre-implementation` scope
    inert while every number still looked right). This fixture — not a
    live-corpus comparison — is what proves the scope flag works;
  - a no-op when no post-work heading is present;
  - **a body with an early `## Verification pass` heading followed by real
    implementation steps: the paths after it MUST still be extracted.** This is
    the regression guard for the artefact described in Step 1 — without it, a
    future widening of `POST_WORK_HEADINGS` silently amputates plan bodies and
    every downstream count still looks plausible.
- **Undefined metrics** — a population with zero colliding pairs yields `None` /
  `-`, never `1.0`.
- Add `"parallel_admission_sweep"` to `PURE_MODULES` in
  `tests/test_parallel_admission_purity.py` (the canonical set both the poison
  and AST guards derive from).

`tests/test_parallel_admission_collect.py`:

- **`--exclude` behaviour, not just its marker.** Extend the existing
  `ReplayInvariantTests` scaffold (synthetic root, injected `_GATE_PROBE` /
  `_LOCK_PROBE` / `_BATCH_MAP` / `_TRACKED_SETS`, with `t9` the in-flight task
  whose plan collides). Assert:
  - a plain `replay` reports the collision, and `replay --exclude 9` **removes
    that claim from the comparison and changes `RATES:` in the named direction**;
  - `--exclude t9` and `--exclude 9` produce **identical** rates (canonicalisation
    is exercised, not assumed);
  - `--exclude 12345`, naming no present claim, leaves `RATES:` **unchanged**
    (negative control — an exclusion that silently drops everything, or nothing,
    would otherwise pass the first assertion).
  A marker-only test would let a regression that canonicalises wrong, filters only
  self-exclusion, or drops nothing still print `EXCLUDED:` over an unchanged 100%
  `UNCHECKABLE`.
- **One snapshot across the whole sweep** — extend the existing seam-counting
  assertion (`self.calls["batch"] == 1`, `self.calls["corpus"] == 1`, currently
  proved for one threshold over many candidates) to a `--thresholds 8,10,20,50`
  run **with** `--exclude`: still exactly **one** `_BATCH_MAP` and **one**
  `_TRACKED_SETS` call. This is the direct proof that the four rates are
  comparable; without it the sweep silently degrades to the four-invocations
  hazard it exists to remove.
- **`--thresholds` actually varies the verdict** — a synthetic population where a
  path's touch count sits between two swept thresholds must produce *different*
  `RATES_AT:` rows for those two thresholds (a sweep that returns four identical
  rows because the override never reached `_respin` would otherwise pass every
  other assertion), plus `RATES_AT:` for a single-element `--thresholds` equalling
  the legacy `RATES:` for the same `--hub-threshold`.
- **`--thresholds` and `--hub-threshold` together exit 2.**
- **`--exclude-no-plan` selects exactly the right claims** — on a synthetic
  snapshot carrying, deliberately, one blocking `no_plan` claim, one **dead**
  `no_plan` claim, one blocking `all_phantom` claim and one resolved claim, the
  `EXCLUDED:` line names **only the first**. Each of the other three is an
  independent negative control: the dead one proves the `tier` half is applied
  (it is the case live data actually contains), the `all_phantom` one proves the
  predicate is not "any invisible surface", and the resolved one proves the
  filter is not indiscriminate. Assert too that the excluded run's `RATES_AT_EXCL:`
  no longer carries that claim's `no_plan` cause, so the flag is shown to change
  the verdict and not merely the label.
- **`--candidates auto`** — resolves to the active-plan population and emits
  `CANDIDATES:<n>|auto`; a run with an explicit file emits `|file`. Assert the
  auto list equals the ids the fixture root's plan files imply, so a silent
  mis-glob is caught rather than reported as a smaller population.
- **`plan_extraction` in both scopes** — `tokens_dropped` is non-zero for a plan
  with a known phantom token, zero when every token is tracked, and the record's
  `paths` equal what `surface_from_plan` returns for the same input (pinning the
  delegation, so the two cannot diverge).
- Arg parsing: `--exclude` accepted **only** on `replay`; rejected on `check`
  **and on `sweep`** (exit 2), with each rejection asserted to name its own
  reason on stderr — the two refusals are not interchangeable, and a shared
  message would let `sweep`'s "nothing to filter" case be mistaken for the
  admission-safety refusal. `sweep` threshold/scope misuse exits 2.

`tests/test_parallel_admission_cli.sh` — wrapper exit-status contract: `sweep`
exits 0 and emits `SWEEP:`; `replay --exclude` emits `EXCLUDED:` and a plain
`replay` does not; `check --exclude` exits 2, names `replay` on stderr, and emits
no `VERDICT:`.

## Step 5 — Record the measurement

The whole measurement is **three commands**, each self-contained and reproducible:

```bash
./.aitask-scripts/aitask_parallel_admission.sh replay --candidates auto \
    --from plan --lock-freshness require-fresh \
    --thresholds 8,10,20,50 --exclude-no-plan
./.aitask-scripts/aitask_parallel_admission.sh sweep --thresholds 8,10,20,50
./.aitask-scripts/aitask_parallel_admission.sh sweep --thresholds 8,10,20,50 \
    --plan-scope pre-implementation
```

The first yields the entire live table — four thresholds × both populations —
from **one** collected snapshot, with the exclusion derived inside that same
snapshot rather than from a prior run. It takes **no hand-supplied ids at all**;
the ones it selected come back on the `EXCLUDED:` line, and together with
`SNAPSHOT:` and `CANDIDATES:` make the counterfactual fully reconstructable.

- Record all of it, dated, in this plan's **Final Implementation Notes**, with
  t1569_3's volatility warning restated and the composition table as the
  headline. Present it as evidence; state no threshold verdict.
- Add a `## Coordination — threshold sensitivity (t1643)` section to
  `aitasks/t1569/t1569_4_task_workflow_parallel_admission_preflight.md`,
  committed separately via `./ait git`. That file currently names t1569_3's rates
  as its entry criterion, which this task supersedes — so the pointer is a
  correctness fix, not a gratuitous cross-task write, and the picker of t1569_4
  reads its task file, not this plan. It must say that the decision (and any
  `HUB_THRESHOLD` change) is t1569_4's, and where the composition numbers live.

### Post-phase (risk mitigations)

1. `[corpus_drift_probe]` Emit `SWEEP_DRIFT:` from the `PlanExtraction` records
   (Step 3), and assert in `tests/test_parallel_admission_sweep.py` /
   `tests/test_parallel_admission_collect.py` that a fixture with a known-dropped
   token reports a non-zero drop and an all-tracked fixture reports zero — so the
   probe discriminates rather than always printing a number. Record the live
   value beside the recall figures, so the recall is read next to the size of its
   own unmeasured bias. (Planning-time reading: ~54% of extracted tokens are
   dropped as phantom — a large bias, and the reason this probe is not optional.)

2. `[excluded_run_marker]` Pin the marker in `tests/test_parallel_admission_cli.sh`
   — `replay --exclude` **must** emit `EXCLUDED:` naming the canonicalised ids and
   a plain `replay` must **not**. Both directions: a marker always present labels
   nothing, and one always absent labels nothing either. Additionally pin the
   **pairing** introduced in Step 2: under `--thresholds --exclude`, every
   `RATES_AT_EXCL:` row must be accompanied by the `RATES_AT:` row for the same
   threshold, so an excluded rate is structurally incapable of appearing alone.
   The marker and the pairing are the labelling half; the Step 4 collector
   assertions are the behavioural half, and neither substitutes for the other.

## Verification

```bash
bash tests/run_all_python_tests.sh --test-dir tests   # read the LAST line
bash tests/test_parallel_admission_cli.sh
shellcheck .aitask-scripts/aitask_parallel_admission.sh
```

Behavioural, on the live corpus: the three commands of Step 5, plus the
back-compat check that a single-threshold `replay` still emits the legacy
`RATES:` line and no `RATES_AT:`.

Acceptance — **invariants** (must hold; enforced by fixtures or by construction):

- Fixture proof that `--plan-scope pre-implementation` changes the extracted path
  set and the resulting counts; that an early `## Verification pass` heading does
  **not** truncate the body after it; and that `plan_extraction` and
  `surface_from_plan` agree on the same input.
- `check` and `sweep` reject **both** `--exclude` and `--exclude-no-plan`, exit 2,
  each naming its own distinct reason; `replay` accepts both and exits 0.
- `--exclude-no-plan` names only blocking `no_plan` claims — a dead `no_plan`
  claim, an `all_phantom` claim and a resolved claim are each left in.
- Exactly one `_BATCH_MAP` and one `_TRACKED_SETS` call for a four-threshold,
  many-candidate, `--exclude`d `replay` — the proof that the four live rates come
  from one world and are comparable.
- A single-threshold `replay` emits the legacy `RATES:` / `CAUSE_RATE:` lines
  unchanged and no `RATES_AT:`; `--thresholds` with one value agrees with the
  legacy line for the same threshold.
- `--thresholds` together with `--hub-threshold` exits 2.
- Fixture proof that excluding a canonicalised blocking claim removes it from the
  comparison and moves the rates, that `9`/`t9` behave identically, and that an
  absent id is a no-op.
- Within one scope, `recall_flagged` is identical across all four thresholds
  while `precision_conflict` and `share_hard_stopped` are not.
- The unnarrowed control agrees with t1569_3's published unnarrowed row on
  precision ≈ 28% and recall ≈ 90% — agreement on the two *rates*, not raw
  counts: the archived corpus grows continuously (270 → 281 tasks between
  t1569_3 and this planning session, and 279 → 281 *within* it), so a count
  equality would fail on the next archival for no defect.

Acceptance — **recorded observations** (dated values written to the Final
Implementation Notes; deliberately *not* pass/fail, because each is a corpus
statistic that a correct implementation may legitimately change):

- live `RATES:` / `CAUSE_RATE:` per threshold, unexcluded and excluded;
- archived-pairs counts, precision, recall and composition per threshold, in
  both plan scopes;
- `SWEEP_DRIFT:` in both scopes.

Post-implementation cleanup, archival and merge are handled by **Step 9**.

## Risk

### Code-health risk: low
- The harness re-implements no verdict logic — it builds an `AdmissionInput` and
  calls `pa.decide`, so it cannot drift from the checker. The one genuinely new
  surface is `--exclude`, a knob that *weakens* the comparison; it is rejected on
  `check`, the only verb that renders an admission decision. · severity: low ·
  → mitigation: none needed — Step 2's rejection and Step 4's exit-status test
  are the guard, in the plan body proper
- `surface_from_plan` is re-expressed as a delegation to `plan_extraction`. A
  shared seam read by `check`, `replay` and t1569_5 changes shape internally even
  though its signature and return are preserved. · severity: low ·
  → mitigation: none needed — Step 4 pins the delegation by asserting both
  functions agree on the same input

### Goal-achievement risk: medium
- **The archived-plan oracle is not the admission-time world.** Tokens are
  classified against *today's* corpus, so a file an old task created and a later
  task deleted classifies `phantom` and silently leaves the surface — ~54% of
  tokens at planning time. This biases both scopes in a direction I cannot
  correct, only size. · severity: medium ·
  → mitigation: inline post-phase corpus_drift_probe
- **The live half stays degenerate.** The excluded run is a counterfactual, not
  an observation: it reports what the checker *would* say if no agent were
  mid-claim. On a busy box the real answer stays `UNCHECKABLE`, which is a fact
  about the fleet, not the threshold. If t1569_4 reads the excluded number as its
  availability figure it will ship `block` on a rate that never occurs.
  · severity: medium · → mitigation: inline post-phase excluded_run_marker;
  availability_timeseries

### Planned mitigations
- timing: post-phase | name: corpus_drift_probe | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: the archived-plan oracle scored against today's corpus, biasing recall by an unmeasured amount | desc: Emit SWEEP_DRIFT: from the PlanExtraction records counting plan tokens dropped as phantom, with fixtures pinning both a non-zero and a zero drop count, and record the live value beside the recall figures.
- timing: post-phase | name: excluded_run_marker | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: a counterfactual excluded rate being misread as the live availability figure | desc: Assert in the CLI test that replay --exclude always emits EXCLUDED: naming the canonicalised ids and that a plain replay never does — both directions, so the marker actually discriminates.
- timing: after | name: availability_timeseries | type: test | priority: medium | effort: medium | inline_risk: high | added_complexity: high | addresses: one snapshot of the UNCHECKABLE rate cannot support promoting parallel_admission to block | desc: Sample the live replay rates repeatedly over days to produce a distribution of the UNCHECKABLE rate as agents actually experience it, rather than a single reading taken while 2-3 agents were mid-claim.

### Post-inline reassessment

Both inline mitigations are additive reporting and test-only work with no new
production behaviour, so the levels are unchanged: **code-health low**,
**goal-achievement medium**. Goal-achievement does not drop — `corpus_drift_probe`
*sizes* the oracle bias without correcting it, and `excluded_run_marker` stops the
counterfactual being mislabelled without supplying the real availability
distribution, which is what `availability_timeseries` is spawned to do.

---

## Final Implementation Notes

### What landed

| file | role |
|---|---|
| `.aitask-scripts/lib/parallel_admission_sweep.py` | **new, pure** — `PlanExtraction`, `Confusion`, `pair_input`/`pair_verdict`, `confusion`, the derived metrics, `POST_WORK_HEADINGS` + `cut_post_implementation` |
| `.aitask-scripts/lib/parallel_admission_collect.py` | `plan_extraction` (the one extractor; `surface_from_plan` now delegates to it), `no_plan_claims`, `_respin` threshold/exclusion overrides, `--thresholds` / `--exclude` / `--exclude-no-plan` / `--candidates auto` / `--plan-scope`, the `sweep` verb |
| `.aitask-scripts/aitask_parallel_admission.sh` | header only — the new verb and why the measurement flags are refused on `check` |
| `tests/test_parallel_admission_sweep.py` | **new** — 27 pure tests |
| `tests/test_parallel_admission_collect.py` | +40 tests; `_ReplayScaffold` extracted (see Defects) |
| `tests/test_parallel_admission_cli.sh` | 38 → 49 wrapper assertions |
| `tests/test_parallel_admission_purity.py` | `parallel_admission_sweep` added to `PURE_MODULES` |

No change to `decide`, the verdict vocabulary, `HUB_THRESHOLD`, or any default.

### The measurement — 2026-08-31 09:09 UTC

**These are volatile corpus statistics, not constants.** t1569_3 saw CLEAR move
48% → 58% in an hour with no code change; during *this* task the archived
population moved 279 → 281 and the in-flight set turned over completely
(`1641,1642,1643` at planning → `1210_5,1644,1646` at measurement). Re-run
`sweep` / `replay --thresholds` when a number has to carry a decision.

**Archived-pairs oracle** — 281 tasks, 39 340 pairs, 3 378 genuinely colliding.
Shares are of all true collisions; `pre-impl` cuts each plan at
`## Final Implementation Notes`:

| hub threshold | hard-stopped | downgraded | missed | precision | hard-stopped (pre-impl) |
|---|---|---|---|---|---|
| 8 | 28.5% | 62.1% | 9.5% | 45.9% | 27.2% |
| **10 (shipped)** | **31.8%** | **58.7%** | 9.5% | 44.8% | **30.4%** |
| 20 | 67.1% | 23.5% | 9.5% | 25.3% | 65.3% |
| 50 | 72.1% | 18.5% | 9.5% | 25.8% | 70.3% |
| unnarrowed control | 90.5% | 0% | 9.5% | 27.0% | 87.6% |

**Live replay** — 118 candidates with an active plan, one snapshot, both
populations. `EXCLUDED:1210_5,1644,1646` was derived from that same snapshot:

| threshold | CLEAR / CAVEATED / CONFLICT / UNCHECKABLE | same, unplanned claims excluded |
|---|---|---|
| 8 | 0 / 0 / 5 / 113 | 84 / 15 / 5 / 14 |
| 10 | 0 / 0 / 5 / 113 | 84 / 15 / 5 / 14 |
| 20 | 0 / 0 / 20 / 98 | 84 / 0 / 20 / 14 |
| 50 | 0 / 0 / 20 / 98 | 84 / 0 / 20 / 14 |

`CAUSE_RATE_AT:10` — `no_plan` 118, `stale_claim` 118 (non-driving),
`all_phantom` 5, `no_extractable_paths` 9, `hub_overlap_only` 5. Excluded:
`no_plan` **gone**, `hub_overlap_only` 5 → 20.

`SWEEP_DRIFT:281|3089|3580` — **54% of extracted plan tokens are dropped as
phantom** against today's corpus.

### What the numbers say — and what they do not

1. **Recall of `CONFLICT ∪ CLEAR_CAVEATED` is threshold-invariant.** 0.9053 in
   every `full` row, 0.8763 in every `pre-impl` row, and the missed count is
   constant (320 / 418). Demotion re-*grades* an overlap and never discards one,
   so a wrong threshold cannot cost recall. **This retires the first risk.**
2. **But grading is the quantity t1569_4 decides on, and it moves enormously.**
   At the shipped threshold only **32%** of real collisions hard-stop; 59% are
   downgraded to a confirmation the agent can click through. At 20 it is 67% /
   23%, for 20pp of precision. Invariant recall hides this entirely, which is why
   the composition is reported.
3. **The threshold decision is NOT made here.** Whether 32%-hard-stop at 45%
   precision beats 67% at 25% depends on what `block` does with each verdict —
   t1569_4's question. This task is evidence.
4. **t1569_3's recall was optimistic.** Archived plans carry post-hoc
   `## Final Implementation Notes`; cutting them moves recall 91% → 88%.
   **88% is a conservative floor**: `## Post-Review Changes` (79 plans, 73 of them
   *before* the notes) is probably also hindsight but was not *proven* so, and a
   wrong cut deletes genuine admission-time paths. True admission-time recall is
   **at most** 88%.
5. **The unnarrowed control reproduces t1569_3's published row** — 27.0%
   precision, 90.5% recall against its 28% / 90% — so the harness implements the
   original method rather than a lookalike.
6. **The live half is still degenerate, and that is a fleet fact.** 113 of 118
   UNCHECKABLE, entirely from three unplanned claims. The excluded column is a
   **counterfactual**, not an availability figure: it says what the checker would
   answer if nobody were mid-claim. On a busy box the real answer stays
   UNCHECKABLE. `availability_timeseries` (spawned at Step 8d) is what would
   supply the real distribution.

### Defects found — both in this task's own work

1. **The `pre-implementation` cutoff was wrong, and it corrupted the headline.**
   The first draft also cut at `## Verification pass`. That heading is written
   when a plan is *re-picked*, so it precedes the implementation body — in
   `p1569_3` it is at line 32, ahead of the whole Step 1–8 plan. Cutting there
   removed **9 of 281 tasks** from the population outright and inflated the
   reported hindsight correction from 3pp to **6pp**; the "85% recall" an earlier
   draft reported was that artefact. `POST_WORK_HEADINGS` is now one proven entry
   with a regression fixture.
2. **Three new test classes inherited from a concrete test class.** Caught by
   `tests/test_collection_structure.py`: `unittest` and `pytest` both collect
   inherited test methods, so the module silently re-ran `ReplayInvariantTests`
   three extra times (125 → 101 tests after the fix). Resolved as that guard
   prescribes — a test-free `_ReplayScaffold` base.

### Upstream defects identified

None. Both defects listed above were introduced by this task and fixed in it;
no pre-existing bug in another script, helper or module was surfaced.

### How the suite was shown to discriminate

Mutation-tested rather than assumed: removing hub demotion fails 5 sweep tests,
demoting everything fails 6, and an off-by-one (`>` for `>=`) fails 1 — the last
only after a **boundary fixture pinned ON the threshold** was added, because the
original touch counts merely straddled it. Injecting `import os` into the new
pure module fails the purity guard, proving it is really in scope. Three seeded
mutations of the CLI file each exit 1.

### Deviations from the plan

1. **`--exclude-no-plan` also refuses on `sweep`, with its own message.** The
   plan said `--exclude` was refused there; the derived flag needed the same
   treatment, and the two refusals are asserted to differ.
2. **The live "precision differs across thresholds" assertion was dropped from
   the CLI test.** Whether two thresholds grade differently depends on whether a
   path's touch count falls between them — a corpus statistic that could fail for
   no defect. It is pinned against a designed fixture instead; only the
   *structural* recall invariance is asserted live. (Same reasoning the plan
   applies to the full-vs-pre-impl comparison.)
3. **`--thresholds` preserves caller order rather than sorting**, so the rows can
   be read against the command that produced them.
4. `tests/test_parallel_admission_cli.sh` now takes ~35s: every assertion is a
   real invocation against the live corpus. It is run on its own, not from the
   Python lane.

Post-implementation cleanup, archival and merge are handled by **Step 9**.
