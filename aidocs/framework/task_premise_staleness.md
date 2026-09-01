# Task premise staleness — the generalized advisory mechanism

Decision record for t1561 ("generalize task staleness detection"). It selects
and fixes the design that the implementation task tree (see "Implementation
tree" at the bottom) lands; the tree's children treat this file as their
durable context anchor. The generalization is **accepted**, not rejected: the
framework already committed to it twice — `lib/roadmap_premise.py`'s docstring
declares itself a temporary stand-in for this mechanism, and t1655 is filed to
delete that module once this lands.

Read together with:

- `aidocs/framework/manual_verification_staleness.md` — the deliberately
  narrow manual-verification seam (t1555) whose conventions this generalizes
  without widening. Its field (`verification_baseline:`) is **not** reused.
- `aidocs/framework/plan_path_reference_extraction_findings.md` — six verified
  defects in the framework's only heuristic "which files does this text
  reference?" implementation; the reason the heuristic tier is deferred.
- `aidocs/framework/background_work_roadmap.md` — the roadmap's premise-drift
  signal (t1569_5), this mechanism's second consumer via t1655.

## The problem

A task can sit `Ready` for months while the codebase, the surrounding task
graph, and the product direction move under it. The task stays syntactically
valid — its dependencies resolve, its status is honest — but its **premise**
(the state of the world it was written against) may no longer hold. The
framework had three isolated freshness checks (plan-review age in
`planning.md` §6.0, the t1555 manual-verification pre-check, the roadmap's
premise signal) and no way to surface premise drift when an ordinary backlog
task is picked.

## What "staleness" means here — three classes, two of them out of scope

1. **Detectable evidence** — commits landed on files the task's premise
   depends on, after the point the premise was last known valid. This is what
   the mechanism measures, and the only thing it claims.
2. **Heuristic signals** — age, broad architectural change, path-shaped
   tokens scraped from task prose. Excluded from v1. Time is rejected as a
   verdict outright (t1555's measurement: at a 20-day median backlog age, any
   hours-scale threshold marks everything stale — zero information). Prose
   path-extraction is rejected until the six defects in
   `plan_path_reference_extraction_findings.md` are paid down: the current
   grammar silently truncates real paths and skips most languages, and a
   wrong scope silently becomes a false all-clear.
3. **Human / product judgment** — "is this still worth doing?" The mechanism
   never claims this. A `FRESH` verdict means "the watched files did not
   change", not "the task is still a good idea".

Weak evidence is never presented as an all-clear: an uncheckable scope entry
drives the verdict toward `ASK_STALE` (never `FRESH`), and a task the
mechanism cannot evaluate reads `SKIP` — silent, and distinct from `FRESH` in
every consumer.

## Selected design

### Field — `premise_baseline: <sha> @ <YYYY-MM-DD HH:MM>`

The commit at which the task's premise was last known valid, in the exact
grammar of `verification_baseline:`. A **new** field, because reusing
`verification_baseline:` would widen a deliberately issue-type-scoped seam:
on a `manual_verification` task that field means "the checklist matches this
commit", which is a different statement with a different review transaction.
t1561's own constraints forbid the widening.

Written by `aitask_update.sh --premise-baseline` (update-path only, like
`plan_approved_at`; empty string clears). Merge rule:
`_BASE_AWARE_FIELDS` in `board/aitask_merge.py` with `deletion_aware=True` —
the same two documented failure modes apply verbatim (a presence-based merge
resurrects a dismissed baseline after sync; an `updated_at`-newer merge lets
an unrelated `--status` edit win a field it never touched). This is the third
user of `_normalize_opaque_scalar`, which its own comment says promotes the
helper out of copy-paste.

### Scope and baseline are orthogonal axes

**Scope** (which files the premise depends on) resolves in tiers:

- **Tier A — curated:** `file_references:` when present (range suffixes
  stripped, as in the t1555 helper). Any issue type.
- **Tier B — derived:** for follow-up tasks, resolve the origin with
  `lib/followup_origin.py` (quality `exact` only — `topic` and `unknown`
  refuse to claim causation); scope = the files the origin's landing commits
  touched outside the task-data prefixes (`aitasks/`, `aiplans/`,
  `.aitask-gates/`).
- Neither → silent `SKIP`.

**Baseline** (since when) resolves separately:

- A stored `premise_baseline:` always wins.
- Without one, v1 reads `SKIP`. The **computed** origin-landing baseline
  (`roadmap_premise.baseline_for` semantics: the newest commit that names an
  origin id AND touches a path outside the task-data prefixes) is **deferred
  behind a profile key** — a no-go outcome of the measured pre-phase below,
  not a guess. When enabled it gives legacy follow-ups a first-pick prompt
  against their origin's landing point.

The landing-commit qualifier is load-bearing and must not be re-derived:
measured 2026-08-31, 61 of 1714 `(tNN)`-tagged commits touch no code path,
and 35 of 1615 tagged ids have a metadata-only *newest* tagged commit — an
unqualified "newest tagged commit" baseline silently masks real drift as
`FRESH`.

Manual-verification tasks never reach this mechanism: task-workflow Step 3
Check 3 routes them to their own procedure before the premise check runs, so
the t1555 seam and this one cannot double-prompt.

### Verdict engine — protocol

One impure producer, `aitask_premise_stale.sh check <task_file>`, emitting
the fixed line protocol (modeled on `aitask_verification_stale.sh`, with two
additions):

```
BASELINE:<sha>|<YYYY-MM-DD HH:MM>   or  BASELINE:NONE
CHECKED:<sha>
FINGERPRINT:<digest>
FILES:<n>
CHANGED:<path>|<n_commits>|<task_ids>
DELETED:<path>|<culprit_task>|<subject>
UNKNOWN:<path>|<reason>
DISPLAY:<one-line human summary>
DECISION:<FRESH|ASK_STALE|SKIP>
```

- Always exit 0 for every content state; `die` on CLI misuse (a typo'd path
  must not read as `SKIP`).
- **`UNKNOWN` drives the verdict**: uncheckable entries share one evidence
  list with `CHANGED`/`DELETED`, and the verdict is an emptiness test over
  that list, so the two cannot drift apart.
- **Empty scope → `SKIP`, never `FRESH`** — a resolved baseline over nothing
  checked nothing.
- History rewrite: a stored baseline not an ancestor of the checked revision
  (`git merge-base --is-ancestor`, treating exit 1 and exit 128 alike) →
  `SKIP`.
- Probes run against **committed trees, never the worktree** (`git cat-file
  -e "<rev>:<path>"` + `git log <sha>..<rev> -- ":(literal)<path>"`), so a
  dirty worktree is invisible by construction. `%`-then-`|` injective
  encoding; `:(literal)` pathspec guard on every history query.

**`CHECKED:<sha>`** records the revision the evidence was evaluated against
(HEAD at check time). Every later baseline advance writes **that** sha, never
write-time HEAD: the check and the write are separated by the ownership claim
(task-workflow Step 4), HEAD can move in between, and advancing to write-time
HEAD would silently mark commits the user never saw as reviewed. Commits
after the checked revision stay uncovered and surface at the next pick.

**`FINGERPRINT:<digest>`** binds the *metadata* inputs the verdict depended
on — a digest over the canonicalized tuple (baseline source + sha, scope
tier, sorted scope path list, resolved origin ids). `CHECKED:` alone cannot
detect a concurrent mutation of `file_references:`, the origin fields, or the
stored baseline itself between prompt and write (another session, a sync
merge). After the lock is acquired and before any baseline write, the
producer is re-run and the fingerprints compared: equal → write proceeds;
different → the prompted confirmation is void, the fresh evidence is shown,
and a fresh decision is required. (The claim-time `active_gates_digest` is
the in-repo precedent for digesting a decision's inputs.)

### Architecture — the pure/impure split (the t1655 contract)

- `lib/task_premise.py` — **pure** core (no `os`/`time`/`subprocess`/I/O;
  listed in `PURE_MODULES` in `tests/test_parallel_admission_purity.py`),
  generalizing `roadmap_premise.baseline_for` + `check` over already-
  materialized text rows. Keeps `metadata_only` distinct from
  `unknown_history` (the remedies differ), keeps `SKIP` fail-open and silent,
  keeps `UNKNOWN`-drives-verdict.
- `aitask_premise_stale.sh` — the git-facing producer. Because it runs git,
  it restores the two narrowings `roadmap_premise` accepted: a `DELETED:`
  record (via `cat-file -e` probes at both ends — history alone misses
  deletions) and the `:(literal)` pathspec guard.

t1655 swaps the roadmap onto this core and deletes `roadmap_premise.py`. The
four properties its tests pin — landing-commit baseline, `UNKNOWN` drives the
verdict, silent `SKIP` with distinct reasons, purity — must survive the swap
unchanged.

### Interaction — task-workflow Step 3 Check 6

A new check after Check 5, on every entry path (pick, board agent launch,
explore), for `Ready` tasks only — resume paths and the archival checks route
away first. `FRESH` and `SKIP` are silent. `ASK_STALE` presents one
NON-SKIPPABLE `AskUserQuestion` with the evidence inside the widget text and
four options:

| Option | Effect on the baseline | Route |
|---|---|---|
| Proceed — premise still valid | advance to the `CHECKED:` sha (post-lock, fingerprint-gated) | continue to Step 4 |
| Review & replan with this evidence | **unchanged** at dismissal; advances to the `CHECKED:` sha only after the renewed plan is approved (Step 7 post-approval writes) | continue, evidence threaded into planning; an existing plan is force-verified (§6.0a's `force_verify` shape) |
| Postpone task | unchanged | status → `Postponed`, end |
| Pick a different task | unchanged | back to selection |

The write transaction is the t1555 invariant with the fingerprint check in
front: **re-check fingerprint → decide → write everything → advance the
baseline last → commit.** Advancing on dismissal is load-bearing (the same
evidence must never re-prompt), but advancement always requires an explicit
premise confirmation — a dismissal or an approved replan — never a mere
workflow transit.

No profile key gates the check in v1: it costs milliseconds, and
advance-on-dismissal already bounds prompt frequency to once per actual
change window. (The deferred computed-baseline tier is where a profile key
enters — see below.)

### Seeding

`aitask_create.sh` stamps `premise_baseline` = HEAD at creation **when the
new task has a derivable scope** — `--followup-of` (Tier B will resolve an
origin) or `--file-ref` (Tier A). A task with no derivable scope is not
seeded; the field would be dead weight. Carry-over tasks
(`create_carryover_task` in `aitask_archive.sh`) **inherit** the origin
task's baseline rather than re-stamping — the carried-over premise is as old
as its source, exactly the t1555 carryover rule.

Seeding at creation is premise-correct even for "before"-timed
risk-mitigation follow-ups (created before their origin lands): the creator's
knowledge of the world *is* HEAD at creation, and the origin landing
afterwards is genuine premise-relevant news for such a task. (Contrast the
roadmap's rejection of `created_at`-anchored baselines for its *origin-drift*
question, which this mechanism does not re-ask.)

## The measured pre-phase and the no-go decision

Measured 2026-09-01 on this repository (the plan's
`sample_live_backlog_prompt_rate` pre-phase; script recomputable from
`aitask_backlog_origin_facts.sh` + `aitask_revert_analyze.sh --batch-map` +
`roadmap_premise.check` over Ready follow-ups):

- Active corpus: 481 tasks, 228 of them `Ready` follow-ups; **87** carried an
  `exact`-quality resolvable origin (the computed-baseline candidates).
- First-pick verdicts: **`ASK_STALE` 78/87 = 89.7 %**, `SKIP` 9
  (`unknown_history`).
- Actionability audit, deterministic sample (pool = the 78 `ASK_STALE` ids
  sorted ascending; stride indices 0, 15, 31, 46, 62): **t623_7, t1113,
  t1291, t1391, t1541** — **0 of 5 actionable** under the pre-registered bar
  ("names ≤10 concrete drift tasks/commits the user can realistically
  inspect"). Every sample aggregated far more than 10 distinct drift tasks;
  hot-file churn dominates (`aitask_setup.sh`: 44 commits by ~40 tasks inside
  t623_7's scope; `minimonitor_app.py`: 32–49 commits in t1113/t1391).

The pre-registered go bar (≥3/5 actionable) was missed, so the **computed
origin-landing baseline for legacy follow-ups is a no-go for v1**. It is
deferred behind a profile key (below) rather than deleted: the mechanism is
sound, but against year-scale windows over hot framework files its evidence
is undifferentiated churn, and 78 unactionable prompts would train users to
click through — destroying the signal for the cases that matter.

The narrowing is precise: **only the computed-baseline source is removed.**
Derived origin *scope* (Tier B) and creation-time seeding stay in v1 — a
seeded follow-up carries a stored baseline and derives its scope from its
origin, so every new follow-up is checkable from day one, over windows
bounded by its own review history rather than its origin's entire afterlife.
Legacy tasks without a stored baseline read `SKIP`, silently — the phased
rollout t1561's constraints asked for.

## Baseline lifecycle

| Event | `premise_baseline` |
|---|---|
| task created with `--followup-of` or `--file-ref` | seeded to HEAD at creation |
| task created without derivable scope | not written |
| carry-over task created at archival | **inherited** from the origin task |
| "Proceed — premise still valid" | advance to the `CHECKED:` sha (post-lock, fingerprint-gated) |
| "Review & replan" chosen, plan later approved | advance to the `CHECKED:` sha at the Step 7 post-approval writes |
| "Review & replan" chosen, plan not approved (abort/stop) | unchanged |
| Postpone / pick-another / session abort | unchanged |
| fingerprint mismatch at write time | no write; fresh evidence, fresh decision |

## Why this is not a gate

Unchanged from t1555's analysis, which generalizes: gates are per-task
declarations whose purpose is *blocking* (`archive-ready` requires every
declared gate to pass), they run during/after implementation, and their runs
feed the re-entry ledger. An advisory pre-selection check that must never
block, runs before ownership exists, and must stay silent for most tasks is
the wrong shape for that substrate. The "reviewed" memory is a frontmatter
baseline field, exactly as t1555 chose; the check itself is a procedure step,
exactly as plan-review freshness chose.

## Deferred, each with its disposition

- **Computed origin-landing baseline for legacy follow-ups** — behind a new
  profile key, off by default; promoted only if the retrospective child finds
  seeded-task evidence quality holds and users ask for backlog-wide coverage.
  The evidence-bounding work (e.g. capping displayed drift sources, windowing)
  belongs to that follow-up.
- **Heuristic prose path-extraction (Tier C)** — blocked on the six defects
  in `plan_path_reference_extraction_findings.md`; any future attempt starts
  from `lib/plan_paths.py`, not a new grammar.
- **Task-graph evidence axis** (dependencies landed, statuses changed, plan
  content hash) — `lib/trail_gather.py` already digests exactly these inputs
  for trails; a premise version is a separate evidence class with its own
  noise profile, so it needs its own measured case before joining.
- **Read-surface markers** (`ait ls -v` flag, board card badge) — owned by
  the implementation tree's retrospective child; the precedent is the
  `plan_approved_at` visibility contract (verbose-only marker + dedicated
  filter flags, never the plain listing).
- **Topic-quality origins, cross-repo scopes** — refuse-to-claim in v1
  (`SKIP`); revisit only with a concrete consumer.

## Known limits

- **The check measures change, not behavior.** A behavior-preserving refactor
  reads as drift; a distant default change that invalidates the premise reads
  as fresh. Both directions persist at any scope quality.
- **Product/purpose drift is out of scope.** `FRESH` never means "still worth
  doing".
- **A silent-skip precondition can mask a broken implementation.** Only the
  end-to-end exercise (seed → change a scope file → prompt fires → dismiss →
  advance → no re-fire) distinguishes "correctly quiet" from "never runs";
  the implementation tree carries it as a required test, not a nicety.

## Implementation tree

The mechanism lands under parent **t1663** with strictly sequential children:
t1663_1 (core engine + producer) → t1663_2 (`premise_baseline` field
end-to-end) → t1663_3 (creation-time seeding + carryover inheritance) →
t1663_4 (task-workflow Step 3 Check 6 + procedure file) → t1663_5 (website
docs) → t1663_6 (retrospective evaluation, which owns the deferred
dispositions above). t1655 (roadmap adoption) depends on t1663. The tree's
task files name their own contracts; this record is their shared design
context.
