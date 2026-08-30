---
Task: t1569_3_shared_parallel_admission_checker.md
Parent Task: aitasks/t1569_background_work_roadmap_trail_for_followup_backlog.md
Sibling Tasks: aitasks/t1569/t1569_1_*.md, aitasks/t1569/t1569_2_*.md, aitasks/t1569/t1569_4_*.md, aitasks/t1569/t1569_5_*.md, aitasks/t1569/t1569_6_*.md
Archived Sibling Plans: aiplans/archived/p1569/p1569_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-30 14:55
---

# t1569_3 — The shared parallel-admission checker

The **single definition of "safe"**. Two consumers: t1569_4 (`task-workflow`
required preflight) and t1569_5 (roadmap advisory preview). All collision
verdicts are computed here and nowhere else.

## Context

The framework has ownership locks, a remote-drift check and worktree/merge
protection, but **no authoritative check against other active tasks**. An agent
may notice a collision while planning; that is judgement, not a guard. This task
builds the one checker both consumers call, so there are never two subtly
different definitions of "safe".

Both dependencies have landed: t1569_1 (`lib/plan_paths.py`, the in-flight facts
in `lib/trail_gather.py`) and t1569_2 (`lib/task_file_sets.py`,
`lib/followup_origin.py`, `aitask_revert_analyze.sh --batch-map`).

---

## Verification pass — 2026-08-30

Re-verified against the landed dependency surfaces and the live corpus. The
three hazards, the four-verdict vocabulary and every cited reference line number
are **confirmed correct**. Measurement changed the design in one major way and
several smaller ones.

### The headline: narrowing-by-dropping is the wrong instrument

The original Step 1 dropped hub paths from the comparison. Built the confusion
matrix it asks for — ground truth is *did two tasks' actually-landed file sets
intersect*, over the 270 archived tasks that have both a plan surface and landed
files, all pairs:

| config | predicts CONFLICT | precision | **recall** |
|---|---|---|---|
| unnarrowed | 28.1% | 28% | **90%** |
| drop hubs, threshold 50 | 22.9% | 27% | **71%** |
| drop hubs, threshold 20 | 21.7% | 26% | **66%** |
| drop hubs, threshold 10 | 6.8% | 44% | **34%** |
| drop hubs, threshold 8 | 5.2% | 47% | **28%** |

**Dropping buys precision by discarding two-thirds of the real collisions.** That
is structural, not a bad threshold: a file touched by 91 tasks is by definition
the file two concurrent tasks are most likely to both edit. The parent task cites
t632's 91/73/72-task hubs as the argument *for* narrowing; they are equally the
argument against it. For a guard whose failure mode is *letting two agents
collide*, **recall is the governing metric**, and no threshold preserves it.

Step 1 is therefore rewritten to **demote rather than drop** — measured below at
**90% recall retained** with a 6.8% hard-stop rate.

Two related corrections fall out. First, the original rule "narrow the in-flight
side only, because narrowing the candidate side can manufacture a false CLEAR"
is **not sound**: dropping path *p* from either side has identical effect on
`A ∩ B`, so dropping is inherently symmetric and the question was not answerable
as posed. Under demotion it dissolves — nothing is dropped from either side.
Second, `all_narrowed` becomes **structurally impossible** and its `UNCHECKABLE`
reason is deleted; that is a stronger guarantee than the negative-control test
the original plan proposed, which only checked the hazard did not fire on the
fixtures.

### The other findings

**1. `git ls-files` misclassifies the task-data corpus as phantom.**
`aitasks/` and `aiplans/` are gitignored symlinks onto the **`aitask-data`
branch**, so `git ls-files` on the code branch tracks **zero** `aitasks/` paths.
Over the 112 active plans, 1167 tokens classify `phantom` while 157 are tracked
on that branch. 18 plans look all-phantom; 15 are recoverable.

But the payoff is **not** what it first looks like: of the 157 recovered tokens,
**137 are task/plan documents** — `Parent Task:` / `Sibling Tasks:` frontmatter
citations — and only **20 are real config** (`aitasks/metadata/project_config.yaml`,
`board_config.json`, `applink_profiles/*.yaml`). The 20 are the genuine win: two
tasks editing `aitasks/metadata/profiles/fast.yaml` is a real collision that is
invisible today. The 137 are noise, and they turn out to be a leading
false-CONFLICT driver. Take the union; remove citations by stripping the plan's
frontmatter before extraction (Step 1) rather than letting the union smuggle them
in as a "rescue" — and note that the fix is the strip, **not** a namespace rule
demoting anything under `aitasks/` or `aiplans/`, which measurement rejects.

Use the **git ref**, not `os.path.exists`. Three tokens exist on disk but are not
on the data branch — two *generated* skill wrappers and `userconfig.yaml`, a
machine-local file. Disk-existence admits build products and per-machine state as
shared collision surface; a ref listing is better evidence, is deterministic, and
is injectable into a pure core.

**2. t887 is invisible to both enumeration sources — a false CLEAR, not just a
missing class.** Verified live: `aitask_query_files.sh inflight` returns
`NO_INFLIGHT` (it requires a `## Gate Runs` ledger), and t887 holds no lock. So
`gate ∪ lock` does not contain it, and a task the checker never enumerates cannot
be classified at all — its absence reads as "no such in-flight work" **against a
task that has a usable plan**. The fix is a third enumeration probe, not a fifth
table row (Step 7).

**3. `plan_paths` has four classes, not two.** `planned_new` is a legitimately
planned new file. 141 such tokens across **65 of 112** plans; **4** plans whose
only resolved tokens are `planned_new` would be wrongly called all-phantom.

**4. t1569_2 emits paths raw — the `_enc()` hazard runs both ways.** Parse
right-to-left, encode on output.

**5. `--batch-map --help` already binds this script by name.** Recovered evidence
"may name an uncheckable cause or caveat a verdict, and may never assert a
conflict or move a verdict toward CLEAR". 96 of 105 `UNKNOWN_HISTORY` tasks
recover — which buys **actionable causes, not a lower UNCHECKABLE rate**.

**6. The in-flight side has no origin-derived fallback, structurally.** An
in-flight task has landed no commits, so `--batch-map` reports `UNKNOWN_HISTORY`
for it — verified for all of t887, t1576, t1555_2, t259 and the candidate. So
finding 1 fixes the candidate side only; t1576 and t1555_2 (`Implementing`, no
plan) force UNCHECKABLE on every pick on their own. That is the honest reason
t1569_4 ships defaulting to `warn`.

**7. Touch counts are a systematic lower bound.** 36 425 of 46 464 `COMMIT:` rows
carry an **empty** `task_ids` field (78%), and only 2 670 of 12 292 paths have any
attribution. Under-counting makes narrowing under-aggressive, which is the safe
direction — but a reader who takes it for a true touch count will misread the
threshold.

**8. Latency is a non-issue.** The full `--batch-map` runs in **0.66 s**.

**9. The in-flight set moves under you — observed, not theorised.** Three new
locks (t1603, t1636, t1638) were taken by concurrent sessions on this host
*during this planning session*, taking the population from 4 to 7. That is direct
evidence for t1569_4's rule that the preflight must re-read live state at call
time and never reuse the roadmap's snapshot, and for `require-fresh` being the
right default at the admission point.

Two smaller corrections: `aitask_verification_stale.sh` is **pure bash with no
Python lib** — it models the line protocol and exit-code split, not the wrapper;
copy the wrapper from `aitask_work_report_gather.sh`. And `ait lock --list`'s
degenerate lines go to **stdout with ANSI colour**, while `--check` prints the
whole lock YAML.

---

## Step 1 — Demote hub overlaps; never drop them

**Keep every overlapping path in the comparison. Grade the verdict by whether any
overlap is on a path that is specific to the work.** Each overlapping path gets a
class:

| class | test |
|---|---|
| `hub` | distinct-task touch count ≥ **10** |
| `specific` | everything else |

| overlap composition | verdict |
|---|---|
| ≥1 `specific` overlap, from a **blocking-eligible** source (Step 7) | **`CONFLICT`** |
| only `hub` overlaps | **`CLEAR_CAVEATED`** + `CAVEAT:inflight:<ref>\|hub_overlap_only:<path>` |
| none | `CLEAR` / `CLEAR_CAVEATED` per source evidence |

**There is deliberately no `citation` class.** An earlier draft demoted anything
matching the task/plan document namespace
`^(aitasks|aiplans)/(archived/)?([tp]\d+(_\d+)?/)?[tp]\d+`. Measurement rejects
it on both counts:

- it **buys nothing** — with frontmatter already stripped, adding the rule moves
  the CONFLICT rate 6.8% → 6.7% and leaves precision (44%), recall (34%) and
  union-recall (90%) **unchanged**;
- it **costs correctness** — a plan may legitimately declare a task or plan
  document as a file it modifies, and the rule cannot tell that from a "read this
  first" reference. Over the archived corpus, 2 of the 119 body-mentioned
  task/plan-document tokens were genuinely modified by that very task; the rule
  would have demoted a real concurrent edit to `CLEAR_CAVEATED`.

Citation noise is handled entirely by the frontmatter strip below, which removes
it **before** extraction rather than second-guessing the author's intent
afterwards. A document named in the plan *body* is treated like any other path.

Measured over the same 270-task ground truth:

```
CONFLICT rate 6.8%   precision 44%   recall 34%
hub-only overlaps → CLEAR_CAVEATED: 21.4% of pairs
recall of CONFLICT ∪ CLEAR_CAVEATED: 90%
```

A blocking consumer hard-stops on 6.8% of pairs; the other 56% of real collisions
reach the user as a **named caveat** instead of silence. Dropping at the same
threshold would have discarded them entirely.

**Strip the plan's frontmatter before extracting.** `plan_paths.extract` reads the
whole file, and the workflow-written `Parent Task:` / `Sibling Tasks:` lines are
metadata of identical shape in every plan, never a work surface. Stripping alone
moves pairwise overlap 12.0% → 10.8%.

**Threshold 10 for both provenances.** It is the knee: 20 → 10 moves precision
26% → 44%; 10 → 8 buys 3pp of precision for 5pp of recall. Because demotion never
discards evidence, a wrong threshold now costs verdict *grading*, not recall —
which is what makes 10 safe to pick from one snapshot.

**Emit every demoted and every stripped path** for audit. A `hub` record is a
relabelling (the path is still compared); a `frontmatter` record is the one place
a token really is removed, so it must be visible:

```
NARROWED:<path>|<hub|frontmatter>|<n_tasks_touching>
```

**Compute distinct tasks, not commits.** `commit_index()` returns
`{path: [(sha, ct, [task_ids])]}`; `len(idx[path])` is a commit count and is the
wrong number.

```python
n_tasks = len({tid for _, _, ids in idx.get(path, ()) for tid in ids})
```

Skip empty `task_ids` (78% of rows) and document the result as a lower bound.

Record the rule, the threshold and the measured recall in the Final
Implementation Notes; t1569_5's design record cites them.

## Step 2 — The CLI and line protocol

```
./.aitask-scripts/aitask_parallel_admission.sh check \
    --candidate <id> --from plan|origin|auto [--plan <path>] \
    --lock-freshness require-fresh|allow-cached [--max-lock-age <s>]
    [--max-claim-age <s>]        # default: MAX_CLAIM_AGE_S (14 days), shared by both consumers
```

Shell entry point over a pure Python lib — the shell is what makes it
whitelistable for skills and callable from `task-workflow`; the Python is what
makes the verdict logic fixture-testable without git.

**Wrapper model: `.aitask-scripts/aitask_work_report_gather.sh`** (19 lines) —
`set -euo pipefail`, `SCRIPT_DIR`, source `lib/aitask_path.sh` +
`lib/python_resolve.sh`, `PYTHON="$(require_ait_python)"`, then
`exec "$PYTHON" …`. Not `aitask_verification_stale.sh`, which has no Python half.

**`--from auto`** is new: with frontmatter stripped, 16 of 112 plans declare no
code paths at all — 14% UNCHECKABLE on the candidate side before any
origin-derived reason. `auto` uses the plan and falls back to origin when the
plan yields nothing, reporting
`CANDIDATE:<ref>|plan_declared+origin_fallback|…`, rather than making each
consumer pick a provenance blind.

**Emission order is fixed and normative**, in exactly this sequence — a golden
test pins it:

```
CORPUS:<code|data>|<ok|unavailable>|<n_files>|<reason|->
INFLIGHT_SOURCE:<gate|lock|status>|<ok|degraded|unavailable|not_consulted>|<age_seconds|->|<reason|->
CANDIDATE:<ref>|<plan_declared|origin_derived|plan_declared+origin_fallback>|<n_paths>|<resolved|unresolved:<reason>>|<exact|topic|unknown|n/a>
LOCKS:<fetched|cached|unavailable>|<age_seconds|->|<reason|->
INFLIGHT:<ref>|<sources_csv>|<live|status_only|lock_only|dead|unknown>|<n_paths>|<resolved|phantom|mixed|none>
OVERLAP:<ref>|<specific|hub>|<n_tasks_touching>|<path>
NARROWED:<path>|<hub|frontmatter>|<n_tasks_touching>
CAVEAT:<inflight:<ref>|locks|corpus>|<reason>
UNCHECKABLE_CAUSE:<candidate|inflight:<ref>|locks>|<reason>
DISPLAY:<one-line human summary>
VERDICT:<CLEAR|CLEAR_CAVEATED|CONFLICT|UNCHECKABLE>
```

`CORPUS:` and `INFLIGHT_SOURCE:` are emitted **unconditionally and exactly once
each** — three `INFLIGHT_SOURCE:` lines in the fixed order `gate`, `lock`,
`status`, whatever their health. A probe that was never run reports
`not_consulted`, never absence: an absent record is indistinguishable from a
source the reader forgot about, which is the "unverifiable is not negative"
failure this whole checker exists to avoid.

- **field 1** — `gate | lock | status`. This checker's enumeration probes. Note
  it deliberately differs from t1569_1's third name (`tracked`): corpus health is
  carried by `CORPUS:` here, and `status` is the new probe from Step 7.
- **field 2** — `ok | degraded | unavailable | not_consulted`, probe health only,
  reusing t1569_1's vocabulary verbatim.
- **field 3** — `age_seconds` for `lock` (from `_locks_cache_age`); `-` for
  `gate` and `status`, which have no cached ref.
- **field 4** — `-` when ok, else the closed vocabulary
  `no_local_ref | unreadable_tree | no_reflog | clock_skew | timeout |
  scan_error`.

An `unavailable` **enumeration** source means in-flight work may exist that was
never listed, so it contributes an `UNCHECKABLE_CAUSE:` under `require-fresh` and
a `CAVEAT:` under `allow-cached` — it is never silent. The same rule applies to
`CORPUS:data|unavailable`, because a classification run over a corpus that could
not be read would otherwise look healthy.

`OVERLAP:` carries the class and touch count so a consumer can render *why* a
collision did or did not hard-stop, with the free-ish `path` last.

**`RATES:` is a second verb, not a record of `check`.** One `check` yields one
verdict; a rate exists only over a population.

```
./.aitask-scripts/aitask_parallel_admission.sh replay --candidates <file|-> --from plan|origin|auto
    → VERDICT_FOR:<ref>|<verdict> per candidate, then
      RATES:<n>|<clear>|<clear_caveated>|<conflict>|<uncheckable>
      CAUSE_RATE:<cause>|<n_candidates_affected>
```

The **cause histogram is not optional**: a bare "UNCHECKABLE 100%" cannot
distinguish *"this design does not work"* from *"two named tasks need a plan"* —
and today it is entirely the latter. `replay` is `check` in a loop over one
collected snapshot: same `decide`, no second verdict logic.

Copy `aitask_verification_stale.sh`'s conventions verbatim:

- one record per line, free-ish field **last**, split with
  `maxsplit = fieldcount - 1` (`:18-24`);
- **always exit 0** for every content state; CLI misuse still `die`s (`:26-32`);
- `_enc()` on output: `%` → `%25` **first**, then `|` → `%7C` (`:122-127`);
- `:(literal)` on every `git log -- <path>` (`:55-65`);
- closed reason vocabularies for `CAVEAT:` and `UNCHECKABLE_CAUSE:`.

**Parsing t1569_2's output is the mirror-image hazard.** Its paths are raw, so a
left-to-right split corrupts any path containing `|`:

| line | safe parse |
|---|---|
| `COMMIT:<path>\|<sha>\|<ct>\|<ids>` | `rest.rsplit("|", 3)` — path is field 1, unbounded |
| `TASKFILES:<id>\|<path>` | `rest.split("|", 1)` — id bounded, path last |
| `TRACKED:<path>` | everything after the prefix |

### The reason vocabulary is a table in code, not prose

`CAVEAT:` and `UNCHECKABLE_CAUSE:` reasons appear at a dozen sites in this
document and come in **two shapes** — bare codes (`no_plan`) and codes carrying a
parameter (`stale_claim:184d`, `hub_overlap_only:<path>`). A guard written against
a flat list of strings would either duplicate an implicit list or silently accept
anything with a suffix. So the vocabulary is **one table in one module**, and both
`render` and the exhaustiveness test import it — neither restates it.

**Record grammar**, stated once. Both records are
`<PREFIX>:<scope>|<reason>`, split on the **first `|`**; `reason` is the free-ish
last field. `scope` and `reason` each split on their **first `:`**:

```
CAVEAT:inflight:t259|stale_claim:184d
        └─scope─┘ └───reason───┘
```

A path parameter is `_enc()`-encoded, so an embedded `|` or `%` cannot break the
split.

**`.aitask-scripts/lib/parallel_admission_vocab.py`** — pure, no imports beyond
`re`:

```python
NONE = None                       # bare code, no suffix permitted
PATH = "path"                     # ':' + an _enc()-encoded path
DAYS = "days"                     # ':' + <int> + 'd'
# a tuple literal = a closed sub-vocabulary of permitted suffix tokens

CAVEAT_REASONS = {
    "hub_overlap_only":    PATH,   # Step 1
    "stale_claim_overlap": PATH,   # Step 7 2b, advisory tier
    "stale_claim":         DAYS,   # Step 3
    "unknown_claim_age":   ("absent", "malformed", "clock_skew"),   # Step 3
    "no_liveness_token":   NONE,   # Step 7, status_only
    "lock_only_holder":    NONE,
    "unknown_liveness":    NONE,
    "cross_host_lock":     NONE,
    "locks_cached":        DAYS,   # Step 6, allow-cached
    "corpus_unavailable":  ("code", "data"),                        # Step 5a
    "source_unavailable":  ("gate", "lock", "status"),              # Step 2
    "source_degraded":     ("gate", "lock", "status"),
    "recovered_only":      NONE,   # Step 5b
}

UNCHECKABLE_REASONS = {
    # imported verbatim from t1569_1's INFLIGHT_PATH: sentinels — do not fork
    "no_plan": NONE, "no_tokens": NONE, "unreadable": NONE, "unclassified": NONE,
    # imported verbatim from _locks_cache_age
    "no_local_ref": NONE, "unreadable_tree": NONE, "no_reflog": NONE,
    "clock_skew": NONE, "timeout": NONE, "scan_error": NONE,
    # this checker's own
    "all_phantom": NONE, "no_extractable_paths": NONE,
    "unknown_history": NONE, "unknown_origin": NONE,
    "source_unavailable": ("gate", "lock", "status"),
}

def format_reason(code: str, param=None) -> str: ...   # validates against the table; raises on a bad pair
def parse_reason(s: str) -> "tuple[str, str | None]": ...
```

The **provenance comments are load-bearing**: the imported halves must stay
byte-identical to t1569_1's goldens-pinned vocabulary
(`.claude/skills/aitask-trail/SKILL.md.j2`) and to `_locks_cache_age`. Reusing
them rather than minting parallel ones is why `no_local_ref` vs `timeout` — the
distinction `--lock-freshness` turns on — means the same thing here as there.

`render` **must** build every reason through `format_reason`; a literal reason
string anywhere else is the defect the guard exists to catch.

## Step 3 — Verdicts

| verdict | meaning |
|---|---|
| `CLEAR` | fully evidenced on **both** sides, no collision found |
| `CLEAR_CAVEATED` | no collision found on a `specific` path, but some evidence was *unverified* rather than absent |
| `CONFLICT` | a `specific` overlap, with the task(s) and file(s) named |
| `UNCHECKABLE` | the comparison could not be made at all |

`CLEAR_CAVEATED` and `UNCHECKABLE` are distinct because their remedies differ:
"I compared and found nothing, but one input was unverified" versus "I could not
compare". Collapsing the former into `CLEAR` would make a real-but-unverified
holder look identical to a fully evidenced all-clear.

### CLEAR is an observation, not a reservation

The checker takes a snapshot; it does **not** reserve the candidate's planned
surface. Another agent can begin overlapping work in the instant after
`VERDICT:CLEAR` — the task lock reserves the *task*, never the *file surface*.

Fix the wording at the source: `DISPLAY:` says **"no known conflict at check
time"**, never "safe to run in parallel". Both consumers inherit it. Document the
residual in the helper's header; it closes only when **t1343**'s declared-claims
backend is adopted.

### Plain CLEAR must remain reachable

A verdict that never occurs teaches both consumers to read `CLEAR_CAVEATED` as
`CLEAR`, collapsing the distinction this section defends. Today t259's
185-day-old anchorless lock (`locked_at: 2026-02-26`) would caveat **every**
future check forever. So bound it: `--max-claim-age <s>`, measured against
`locked_at` from the lock YAML and `updated_at` from the task frontmatter (both
free). A claim past the bound is reported as
`CAVEAT:inflight:<ref>|stale_claim:<age_days>d` but **stops contributing to the
verdict** — it neither caveats nor blocks. Its overlap eligibility is defined in
Step 7's matrix, which is the single place that question is answered. Without
this bound the caveat channel saturates and stops carrying information.

**One shared default, defined once.** `--max-claim-age` is optional, and two
consumers using different bounds would be two definitions of "safe" — the exact
failure this task exists to prevent. The default is a constant in the pure core,
**`MAX_CLAIM_AGE_S = 14 days`**, and both consumers inherit it; the flag and any
future profile knob are overrides, never independent defaults. `decide` records
the effective value on the `DISPLAY:` line so a verdict is reproducible.

14 days is chosen from the live claim ages, which separate cleanly: every
anchored lock is ≤ 11 days old (t1555_2 and t1576 at 11d, three taken today),
while t259 — the anchorless 2026-02-26 lock this bound exists for — is 184 days.
The gap is two orders of magnitude, so the exact value is not load-bearing; it
only has to sit inside it.

**An unknown age is not a stale age.** `claim_age_s` is `None` whenever
`locked_at` / `updated_at` is absent, unparseable, or in the future (the
`clock_skew` case t1569_1's `_locks_cache_age` already names). The tier matrix
compares against an `int`, so `None` must never reach it. Resolve it
conservatively and explicitly, **before** the comparison:

> An unknown age keeps the source **blocking-eligible** and adds
> `CAVEAT:inflight:<ref>|unknown_claim_age:<absent|malformed|clock_skew>`.

Conservative here means "cannot miss a collision": an unparseable timestamp must
not become a back door that demotes a live holder to advisory. It costs a caveat,
which is the cheap direction. The comparison itself is `>` — a claim exactly at
the bound is still blocking — so the boundary is pinned rather than left to the
implementer.

## Step 4 — Self-exclusion (hazard a)

`task-workflow` claims the candidate at **Step 4** — `status: Implementing` **and**
the lock — long before Step 6 writes the plan. Re-verified live: this task was
`Implementing` and in `ait lock --list` while this plan was being written.

Since the checker unions its sources, the candidate lands in its own comparison
set and overlaps every path of its own plan: a guaranteed `CONFLICT` on every
pick.

**Remove the candidate ref from every source before overlap is evaluated** — all
three `SourceResult.ids` dicts and the derived surfaces. Not by filtering results
afterwards: a post-filter leaves the `INFLIGHT:` records and the `RATES:` counts
wrong, and the next reader re-introduces the bug.

Match on the canonical ref via `dep_resolution.canonical_dep_id`, which accepts
`t423_6` / `423_6` / `423` / `423` (int). Strip t1569_1's `<project>#` prefix
before comparing; the candidate may be a child.

## Step 5 — Unresolved candidate surface ⇒ UNCHECKABLE (hazard b)

An empty intersection is meaningless when the candidate side is unknown. Emit
`CANDIDATE:...|unresolved:<reason>` → `UNCHECKABLE` for each of:

| reason | live incidence (2026-08-30) |
|---|---|
| `no_extractable_paths` — the extension list misses the project's language, or the plan declares only prose | **16 of 112** once frontmatter is stripped — the reason `--from auto` exists |
| `all_phantom` — no `tracked` / `planned_new` token remains after the corpus union | **3 of 112** (was 18 before Step 5a) |
| `unknown_history` — `STATUS:<id>\|UNKNOWN_HISTORY`, origin provenance | 105 of 1 731 |
| `unknown_origin` — `followup_origin.resolve` returned `unknown` | 13 of 230 follow-ups (exact 87 / topic 130 / unknown 13) |

`all_narrowed` is **deleted**: Step 1 demotes rather than drops, so narrowing can
no longer empty a surface. Keep a test asserting that no configuration of
thresholds can produce an empty candidate surface — the guard that catches a
future change back to dropping.

### Step 5a — Union the task-data corpus (finding 1)

`plan_paths.classify` answers "is this tracked **on the code branch**" — the right
question for `aitask_remote_drift_check.sh`, which intersects plan paths with
files changed on that branch's remote, where a data path can never appear. Its
blindness is not a tolerated bug; the code-branch corpus is correct for the
question it asks. It is the **wrong** corpus for admission.

`classify(token, tracked, tracked_dirs)` already takes the corpus as
**parameters**, so the seam exists and **`plan_paths.py` needs no edit**:

```python
tracked, dirs   = plan_paths.tracked_sets(root)      # code branch
dtracked, ddirs = data_tracked_sets(root)            # git ls-tree -r --name-only aitask-data
cls = plan_paths.classify(tok, tracked | dtracked, dirs | ddirs)
```

Passing different sets to the *same* shared classifier is the strongest available
statement that the two consumers have not forked. Do **not** widen
`plan_paths.CLASSES`: it is pinned by t1569_1's 8-value `INFLIGHT_PATH:`
vocabulary and three skill goldens, and widening it would give the drift check
the opposite of its correct blindness.

A missing `aitask-data` ref is a **content state**, not an error: on a
single-branch clone `aitasks/` is already in `git ls-files`, the union is empty,
and behaviour degrades to today's. Report it as
`CORPUS:data|unavailable|0|no_local_ref` plus a `CAVEAT:` — test this legacy path.

### Step 5b — `--with-recovered` and `UNKNOWN_HISTORY`

`UNKNOWN_HISTORY` means *"unrecognized by the oracle's disk-derived expansion"* —
not "touched no files". `aitask_revert_analyze.sh --help` already binds this
checker as `--with-recovered`'s only sanctioned caller:

> recovered evidence **may** name an uncheckable cause or caveat a verdict, and
> **may never** assert a conflict or move a verdict toward CLEAR.

**Measured leverage, and what it does not buy.** 96 of the 105 `UNKNOWN_HISTORY`
tasks recover to `FILES` (all with `RECOVERED_DIVERGES > 0`), leaving 9. That does
**not** lower the UNCHECKABLE rate — the contract forbids moving a verdict in
either direction. It means 96 of 105 UNCHECKABLE verdicts carry a **specific,
actionable cause** instead of an undifferentiated "unknown". That is the
difference between a guard the user acts on and one they dismiss.

`RECOVERED_*` may populate `UNCHECKABLE_CAUSE:…|unknown_history` with detail and
raise `CLEAR` → `CLEAR_CAVEATED`. It may **never** produce an `OVERLAP:` record
and never move a verdict toward `CLEAR`. Pin both as negative controls.

## Step 6 — Lock freshness as a parameter (hazard c)

`trail_gather.probe_lock_source` reads `origin/aitask-locks` **without fetching**
so the shared gatherer stays offline-safe — right for an estimate, fatal for an
admission decision: a stale ref hides a lock another agent took seconds ago.

- `require-fresh` (t1569_4) — attempt a bounded fetch. On fetch failure, or a ref
  older than `--max-lock-age`, emit `LOCKS:cached|<age>|<reason>` or
  `LOCKS:unavailable|-|<reason>` → **UNCHECKABLE**.
- `allow-cached` (t1569_5) — accept the cached read, label it, contribute a
  `CAVEAT:` rather than UNCHECKABLE.

**Neither mode may report `CLEAR` on lock evidence it could not establish.**

Reuse `_locks_cache_age(root) → (age|None, reason|None)`. `age` is `-`, never
`0`, when unknown; a negative age becomes `-` with `clock_skew`.

## Step 7 — Availability

A naive rule — any incomplete in-flight source ⇒ UNCHECKABLE — yields
**UNCHECKABLE on 100% of picks today**. A guard that prompts on every pick is one
the user learns to dismiss.

**There is no origin-derived fallback for the in-flight side — this is
structural.** An in-flight task has not landed its work, so no commit carries its
id; verified `UNKNOWN_HISTORY` for all of t887, t1576, t1555_2, t259 and the
candidate. The in-flight surface can therefore come **only** from a plan file,
with no second source. The candidate side is the opposite case: `--from origin`
works for a *backlog* candidate precisely because its origin's work **has**
landed. That is why the two `--from` modes are not interchangeable, and why
Step 5a fixes the candidate side but cannot fix the in-flight side.

### 1. Enumerate all three sources (finding 2)

`gate ∪ lock` does not cover the state `task-workflow` actually writes. Live:
four tasks are `status: Implementing`; the gate probe returns `NO_INFLIGHT` (it
requires a `## Gate Runs` ledger) and the lock ref names four, but **t887 is in
neither** — and t887 has a usable plan. A task never enumerated cannot be
classified, and its absence reads as a clean all-clear.

Add **`probe_status_source(root) -> SourceResult`** (name `status`) — a bounded
frontmatter scan of active task files for `status: Implementing`. Pure
filesystem, no git, no subprocess; mirrors `probe_gate_source` /
`probe_lock_source` exactly, and is the cheapest of the three with the fullest
coverage of the Step-4 state. Report it on its own `INFLIGHT_SOURCE:status|…`
line per Step 2's grammar. This checker does **not** re-emit t1569_1's
`INFLIGHT_SCAN:` aggregate — enumeration health is carried per source, one record
each, which is what makes an unavailable probe attributable to a named source
rather than folded into a single roll-up field.

### 2. Classify by which sources named the task

| class | test | effect when no `specific` overlap |
|---|---|---|
| `live` | lock present, **hostname matches**, holder `alive` | evidenced — allows `CLEAR` |
| `status_only` | `Implementing`, **no lock** (t887) | `CAVEAT:…\|no_liveness_token` → `CLEAR_CAVEATED` |
| `lock_only` | locked, `status != Implementing` (t259 since 2026-02-26) | `CAVEAT:` → `CLEAR_CAVEATED` |
| `unknown` | locked + `Implementing`, liveness `unknown`, **or any cross-host lock** | `CAVEAT:` → `CLEAR_CAVEATED` |
| `dead` | holder provably `dead` **on this host** | excluded from the comparison entirely — see 2b |

**Why `status_only` caveats rather than counting as evidenced:** its *surface* is
knowable, so a real overlap still yields `CONFLICT` — and it must. What is missing
is **liveness**. `status` is a durable claim of intent written at Step 4 and
cleared only by archival; liveness is perishable. t887 carries
`updated_at: 2026-08-13` — 17 days stale, no lock, no ledger; almost certainly not
concurrent work, but nothing observable proves it. Note the symmetry: `lock_only`
is a lock without a status, `status_only` a status without a lock. Both are
half-evidenced; treating one as evidenced and not the other would be arbitrary.

**The hostname guard is mandatory before any `dead` claim.**
`lock_holder_liveness` compares the recorded PID against the **local** process
table, so on a different host an absent PID yields `dead` — a fabricated crash
claim about a live agent elsewhere, and `dead` is the one class we **drop**.
`aitask_lock.sh:221-223` already gates the anchor check on
`locked_hostname == current_hostname` and excludes a literal `unknown` hostname
("two machines both reporting it would compare equal"), routing the mismatch to
`LOCK_RECLAIM`. Copy that guard verbatim: **cross-host ⇒ `unknown`, never
`dead`.**

Three further properties of `lock_holder_liveness` (L148-173): it **echoes on
stdout and always exits 0** (never branch on `$?`); it returns `unknown`, **not**
`dead`, when the token is absent; and `is_lock_holder_alive` (L178-180) collapses
`dead` and `unknown` to false, so the **tri-state** is required here.

**`probe_lock_source` does not carry the anchor.** Its `.ids` is
`{task_id: (resume_point, archive_status)}` — enumeration only. Read the lock
YAML from the ref directly (`git show <locks-ref>:t<id>_lock.yaml`). Verified
shape — a fresh lock carries the triple; a pre-PID-anchor lock omits it entirely
and is therefore `unknown`:

```yaml
task_id: 1569_3          # t259 (locked 2026-02-26) has the first four keys
locked_by: …             # and none of the three below
locked_at: 2026-08-30 08:31
hostname: omg16
pid: 37050
pid_starttime: 112467
pid_starttime_kind: proc     # proc | ps — a `ps` token is weak and also yields `unknown`
```

### 2b. Overlap eligibility — which classes may block, caveat, or neither

The table above answers only the *no-overlap* case. This one answers the other
half, and it is the single place the question is decided. Without it a `dead`
holder — or an abandoned claim whose plan still names live files — would
hard-stop current work **indefinitely**, since a class that is "dropped" for
caveat purposes was still contributing paths to the comparison.

Liveness and age are applied **before** overlap is evaluated. Each in-flight
source lands in exactly one tier:

| tier | classes | contributes paths? | max verdict it can cause |
|---|---|---|---|
| **blocking-eligible** | `live`, `status_only`, `lock_only`, `unknown` — **and** `claim_age ≤ max_claim_age`, **or `claim_age` unknown** (Step 3) | yes | `CONFLICT` on a `specific` overlap |
| **advisory-only** | any class whose `claim_age > max_claim_age` | yes | `CLEAR_CAVEATED` — emits `OVERLAP:` and `CAVEAT:inflight:<ref>\|stale_claim_overlap:<path>`, **never** `CONFLICT` |
| **excluded** | `dead` (provably dead **on this host**) | **no** | none — one `INFLIGHT:` record for auditability, no `OVERLAP:`, no `CAVEAT:` |

The age test is evaluated **only after** `claim_age_s` has been resolved to an
`int` or to the unknown branch of Step 3 — `None` never reaches the comparison.
Liveness outranks age: a `dead` holder is excluded regardless of how recent its
claim is, because age cannot make a dead process concurrent.

Three consequences, stated so neither consumer has to infer them:

- **`dead` is excluded from the comparison itself**, not merely from the caveat
  set. A provably-dead holder is not concurrent work, so its declared surface is
  not evidence of anything. It still gets an `INFLIGHT:` line so the exclusion is
  visible rather than silent.
- **A stale claim degrades to advisory rather than vanishing.** Dropping it from
  the comparison entirely would hide a real collision if the task turns out to be
  active; keeping it blocking-eligible lets a months-old lock veto every future
  pick. Advisory is the only tier that is wrong in neither direction — the user
  still sees the overlap and its age, and can act on it.
- **Only the blocking tier can reach `CONFLICT`.** Step 7's aggregation rule
  ("any `specific` `OVERLAP:` → `CONFLICT`") is scoped to blocking-eligible
  sources; an `OVERLAP:` record from the advisory tier grades to
  `CLEAR_CAVEATED`.

Within the blocking tier, a `status_only` / `lock_only` / `unknown` source still
produces **CONFLICT** on a real `specific` overlap — the half-evidenced classes
weaken the *all-clear*, never the *collision*. That is what keeps this mitigation
from buying availability at the cost of silent under-reporting.

### 3. Per-source, named causes

`UNCHECKABLE_CAUSE:inflight:t1576|no_plan` lets the consumer say "cannot rule out
a collision with **t1576**" and offer a per-task remedy — plan it, or release its
lock — instead of an undifferentiated "something is unknown". Two tasks are
blocking the entire guard today, and the remedy is cheap.

**Verdict aggregation, stated once so both consumers agree.** Evaluated in this
order, after 2b has assigned every source a tier:

1. a `specific` `OVERLAP:` from a **blocking-eligible** source → `CONFLICT`;
2. else an unresolved **candidate** surface, or a blocking-eligible in-flight
   source with no visible surface at all (`no_plan` / `all_phantom` /
   `unreadable` / `no_tokens`), or an `unavailable` enumeration source under
   `require-fresh` → `UNCHECKABLE`;
3. else any `CAVEAT:` — including a `hub`-only overlap and any advisory-tier
   overlap → `CLEAR_CAVEATED`;
4. else `CLEAR`.

Note that an **excluded** (`dead`) source reaches none of these rules: it
contributes no surface, so it cannot produce step 1's overlap nor step 2's
`no_plan` cause. That is deliberate — a dead holder must not be able to make the
verdict *worse* in either direction.

**Parsing `ait lock --list`.** Four degenerate strings ("No locks (no remote
configured)", "No locks (branch not initialized)", "No locks", "No active locks")
go to **stdout with ANSI colour** via `info()`, exit 0. Prefer
`probe_lock_source`, which reads the ref directly and sidesteps this entirely.

## Step 8 — Module boundary: one verdict logic, two consumers

t1569_5 requires "no git, no subprocess, fully fixture-testable"; t1569_4 requires
live `require-fresh` state. Satisfy both with a **pure core over an injected
snapshot**.

**Pure core — `.aitask-scripts/lib/parallel_admission.py`.** No `subprocess`, no
`os`, no `time`. Everything, including the clock, is a field.

```python
@dataclass(frozen=True)
class Surface:
    ref: str                  # canonical "<project>#<id>"
    provenance: str           # plan_declared | origin_derived | plan_declared+origin_fallback
    paths: "tuple[str, ...]"  # RAW, codepoint-sorted; encoding happens at render
    resolution: str           # resolved | no_plan | unreadable | no_tokens |
                              # no_extractable_paths | all_phantom |
                              # unknown_history | unknown_origin
    quality: str              # exact | topic | unknown | n/a

@dataclass(frozen=True)
class InflightClaim:
    ref: str
    sources: "tuple[str, ...]"    # subset of ("gate", "lock", "status")
    task_status: str
    liveness: str                 # alive | dead | unknown | n/a (post hostname guard)
    same_host: "bool | None"      # None ⇒ unknown ⇒ liveness forced to "unknown"
    claim_age_s: "int | None"
    surface: Surface

@dataclass(frozen=True)
class SourceEvidence:
    name: str                     # gate | lock | status
    status: str                   # ok | degraded | unavailable | not_consulted
    age_s: "int | None"
    reason: "str | None"

@dataclass(frozen=True)
class AdmissionInput:
    candidate: Surface
    enumeration: "tuple[SourceEvidence, ...]"   # EXACTLY three: gate, lock, status
    inflight: "tuple[InflightClaim, ...]"
    locks: LockEvidence           # mode, state, age_s, reason
    corpora: "tuple[CorpusEvidence, ...]"   # name, status, n_files, reason
    touch_counts: "Mapping[str, int]"       # path -> DISTINCT-task count
    hub_threshold: int
    max_lock_age_s: int
    max_claim_age_s: int          # default MAX_CLAIM_AGE_S; see Step 3
    now: int                      # injected; the core never calls time()

def decide(inp: AdmissionInput) -> "AdmissionResult": ...   # total; no exceptions for content states
def tier(c: InflightClaim, max_claim_age_s: int) -> str: ...  # blocking | advisory | excluded
def render(res: "AdmissionResult") -> str: ...              # both consumers byte-identical
def encode_path(p: str) -> str: ...                         # '%'→'%25' first, then '|'→'%7C'
```

`tier` is a **derived** function of `liveness`, `same_host` and `claim_age_s`
against `max_claim_age_s` — not a stored field. Keeping it derived is what makes
Step 7's eligibility matrix a single expression that the fixtures can drive
directly, instead of a property a collector could set inconsistently.

**`enumeration` is what makes the pure core able to keep its own promises.**
Without it the core holds only the *tasks that were found*, so it cannot tell an
`unavailable` or `not_consulted` probe from a healthy probe that found nothing —
and "no in-flight tasks" is exactly the shape of a false `CLEAR`. It is also the
only source for the three mandated `INFLIGHT_SOURCE:` records, which `render`
must emit without consulting the collector. So:

- it carries **exactly three** entries, in the order `gate`, `lock`, `status`.
  A missing, duplicated or unknown name is a **programming error, not a content
  state** — `decide` raises rather than emitting a partial record set, because a
  silently absent record is precisely the failure the completeness rule exists to
  prevent;
- `render` emits one `INFLIGHT_SOURCE:` line per entry, verbatim from this field;
- `decide` reads it for the verdict: any entry with `status == "unavailable"`
  contributes `UNCHECKABLE_CAUSE:` under `require-fresh` and `CAVEAT:` under
  `allow-cached`, per Step 7's aggregation. `not_consulted` is treated as
  `unavailable` for verdict purposes — a probe that never ran rules nothing out —
  while `degraded` contributes a `CAVEAT:` in both modes.

A healthy-but-empty probe is therefore `SourceEvidence("status", "ok", None,
None)` with no matching `InflightClaim`, and is the *only* shape that permits a
plain `CLEAR`.

**Consequence for t1569_5, stated so it is not quietly faked.** t1569_1's
gatherer emits `INFLIGHT_SOURCE:` for `gate`, `lock` and `tracked` — it has no
`status` probe. So a roadmap run built from gatherer output alone must supply
`SourceEvidence("status", "not_consulted", None, None)`, and every roadmap entry
therefore caveats and can never reach plain `CLEAR`. That is the correct outcome,
not a defect: the roadmap is explicitly an estimate over a snapshot, and
t1569_5's own scope says to label it one. The implementer must **not** synthesise
an `ok` here to make the lane look cleaner — that would be the false-CLEAR this
field was added to prevent, reintroduced by the consumer.

Also pure — **adapters from the two upstream line protocols**, since parsing text
is pure. This is what lets t1569_5 reuse the verdict logic with no subprocess:

```python
def surfaces_from_inflight_records(lines, local_name) -> "dict[str, Surface]"
def touch_counts_from_batch_map(lines) -> "dict[str, int]"
def surfaces_from_batch_map(lines, ids) -> "dict[str, Surface]"
def input_from_records(*, inflight_lines, batch_map_lines, candidate_ref, ...) -> AdmissionInput
```

**Impure collector — `.aitask-scripts/lib/parallel_admission_collect.py`.** Owns
every subprocess, exactly as `aitask_revert_analyze.sh` owns them for
`task_file_sets.py`:

```python
def collect(root, candidate_id, source, plan_path, freshness,
            max_lock_age_s, max_claim_age_s, now=None) -> AdmissionInput
```

with injectable seams in the established `_GATE_PROBE` / `_LOCK_PROBE` style:
`_STATUS_PROBE`, `_TRACKED_SETS`, `_DATA_TREE`, `_LIVENESS`, `_FETCH`,
`_BATCH_MAP`, `_LOCAL_HOST`.

**Shell entry** — `collect()` → `decide()` → `render()` → stdout; always exit 0
for content, `die` on CLI misuse.

**Three files, and only the middle one is impure:**

| file | role | pure? |
|---|---|---|
| `lib/parallel_admission_vocab.py` | the reason/enum table + `format_reason` / `parse_reason` | yes |
| `lib/parallel_admission.py` | `Surface` … `AdmissionInput`, `tier`, `decide`, `render`, the record adapters | yes |
| `lib/parallel_admission_collect.py` | `collect()` and every subprocess | no |
| `aitask_parallel_admission.sh` | 19-line wrapper (`check`, `replay`) | — |

The purity guard covers the first two together: with `subprocess` poisoned, both
must import and `decide`/`render` must still emit the golden bytes.

**Consumers:** t1569_4 calls the shell (whitelistable, `require-fresh`);
t1569_5 does `from parallel_admission import decide, input_from_records` and
**never imports the collector**.

**Enforce the boundary with a test, not a docstring** (the same move t1569_5
makes for `followup_kind`, and the AST-guard pattern t1569_1 already uses):
poison `sys.modules["subprocess"] = None` (likewise `shutil`, `socket`), import
`parallel_admission`, and assert `decide` still produces the golden bytes; plus
an AST assertion that the module contains no `import os` / `import time`.

### Post-phase (risk mitigations)

Run after Step 8, once the core and collector exist. Each is a bounded, separately
verifiable addition — none of them can reshape the plan.

**`purity_guard`** — a test module that enforces the Step 8 boundary rather than
documenting it:

```python
for mod in ("subprocess", "shutil", "socket"):
    sys.modules[mod] = None
import parallel_admission                    # must still import
assert parallel_admission.render(parallel_admission.decide(FIXTURE)) == GOLDEN
```

plus an `ast`-based assertion that `parallel_admission.py` contains no
`import os` / `import time` and no `time.time()` call. Follow the AST-guard
pattern t1569_1 already established in `tests/test_trail_gather.py` (~L2082-2205).

**`vocabulary_exhaustiveness_guard`** — imports
`parallel_admission_vocab` and drives every assertion **from that table**; it must
not contain a second copy of the vocabulary, which is the duplication this
mitigation exists to prevent. Three parts:

1. **Round-trip.** For every `(code, shape)` in `CAVEAT_REASONS` and
   `UNCHECKABLE_REASONS`, `parse_reason(format_reason(code, param))` returns
   `(code, param)` for a valid param, and `format_reason` **raises** for a param
   of the wrong shape — a bare code given a suffix, a `DAYS` code given a path, a
   sub-vocabulary code given a token outside its tuple.
2. **No literals escape the table.** Run every fixture in the suite, parse each
   emitted `CAVEAT:` / `UNCHECKABLE_CAUSE:` line with `parse_reason`, and assert
   the code is a declared key **and** its param matches the declared shape. Then
   the reverse direction: an `ast` scan asserting no string literal matching
   `^[a-z_]+:` is passed to a `CAVEAT`/`UNCHECKABLE_CAUSE` construction anywhere
   in `parallel_admission.py` — every reason must come through `format_reason`.
3. **The other closed sets.** Same treatment for verdicts, overlap classes
   (`specific|hub`), `NARROWED:` classes (`hub|frontmatter`), liveness classes,
   tiers, `CORPUS:` and `LOCKS:` states, and `INFLIGHT_SOURCE:` names and
   statuses: every value `render` emits is a declared member, and `decide`
   **raises** rather than defaulting when handed an undeclared one.

Plus a **drift guard on the imported halves**: assert the `INFLIGHT_PATH:`
sentinel codes and the `_locks_cache_age` reason codes in the table match the
upstream sources, so a future change to t1569_1's goldens-pinned vocabulary
breaks here loudly instead of forking silently.

**`clear_wording_pin`** — assert the `DISPLAY:` line contains the exact string
`no known conflict at check time` and never the substring
`safe to run in parallel`, across a CLEAR and a CLEAR_CAVEATED fixture. This is
the only executable defence of the observation-not-reservation guarantee, which
both consumers inherit verbatim.

## Verification

```bash
bash tests/run_all_python_tests.sh --test-dir tests    # last line only
shellcheck .aitask-scripts/aitask_parallel_admission.sh
./.aitask-scripts/aitask_parallel_admission.sh check --candidate 1569_3 --from auto \
    --lock-freshness allow-cached
```

Required fixtures — **overlap, no-overlap, missing-plan, all-phantom-plan,
unknown-history, self-as-candidate, stale-locks, unresolved-candidate-surface,
lock-only-holder, unknown-liveness-holder** — plus, from this verification pass:

- **demotion**: a hub-only overlap yields `CLEAR_CAVEATED` with a named caveat,
  **never** `CONFLICT` and **never** plain `CLEAR`; a `specific` overlap on the
  same fixture yields `CONFLICT`; and the hub path still appears as an
  `OVERLAP:` record in both cases (it is demoted, not removed).
- **no configuration empties a surface** — the standing guard replacing
  `all_narrowed`.
- **`status_only` holder**: `Implementing`, no lock, usable plan. No overlap →
  `CLEAR_CAVEATED`; **with** overlap → `CONFLICT`.
- **third enumeration source**: a task visible only to the status probe is
  enumerated and classified — the t887 false-CLEAR regression.
- **`INFLIGHT_SOURCE:` completeness**: all three records are emitted, in the fixed
  order, on every run — including when a probe is `unavailable`, when it returns
  an **empty** id set (`ok`, zero tasks — distinct from unavailable), and when
  only the `status` probe finds anything. An `unavailable` enumeration source
  yields `UNCHECKABLE` under `require-fresh` and a `CAVEAT:` under
  `allow-cached`, never silence; `not_consulted` behaves as `unavailable` and
  `degraded` caveats in both modes.
- **healthy-empty vs unavailable are not interchangeable** — the false-CLEAR
  regression this field exists for. Two fixtures identical except for the
  `status` probe's `SourceEvidence`: `ok` with zero claims → `CLEAR`;
  `unavailable` with zero claims → **never** `CLEAR`. Plus the completeness
  invariant: an `enumeration` tuple missing a name, duplicating one, or naming an
  unknown source makes `decide` **raise**, not emit a partial record set.
- **claim age — absent, malformed, skewed, and both sides of the boundary.**
  `locked_at` absent, unparseable, and in the future each resolve to unknown age
  → the source stays **blocking-eligible** and carries
  `CAVEAT:…|unknown_claim_age:<absent|malformed|clock_skew>`; none of them may
  crash and none may silently demote to advisory. Boundary: a claim at exactly
  `max_claim_age` is blocking, one second past it is advisory — asserted on both
  sides so the `>` is pinned rather than left open. Plus a default test: with no
  `--max-claim-age`, the effective bound is `MAX_CLAIM_AGE_S` and it appears on
  the `DISPLAY:` line, so the two consumers provably share one value.
- **dead holder with matching paths**: an in-flight task classified `dead` whose
  plan declares a path the candidate also declares produces **no `OVERLAP:`
  record and no `CAVEAT:`**, and the verdict is `CLEAR` — not `CONFLICT`. Its
  `INFLIGHT:` line is still present. Positive control: the same fixture with the
  holder `alive` yields `CONFLICT`, proving the fixture's paths really do
  intersect.
- **stale holder with matching paths**: an in-flight task past
  `--max-claim-age` whose plan declares an overlapping path yields
  `CLEAR_CAVEATED` with an `OVERLAP:` record and
  `CAVEAT:…|stale_claim_overlap:<path>` — **never** `CONFLICT`. Boundary control:
  the same fixture one second **inside** the bound yields `CONFLICT`, pinning the
  edge rather than leaving the assertion shape open.
- **a body-declared task document is a modification target**: a plan whose body
  names `aitasks/t<N>_*.md` as a file it modifies produces a `specific` overlap
  and `CONFLICT` against another task declaring the same file — the regression
  the rejected `citation` namespace rule would have introduced.
- **cross-host liveness**: a lock whose `hostname` differs from the local host
  classifies `unknown`, **never** `dead`, even when the PID is absent locally.
  Negative control: the same fixture same-host does classify `dead`.
- **plain CLEAR is reachable**: a fixture past `--max-claim-age` yields `CLEAR`,
  not a permanently saturated `CLEAR_CAVEATED`.
- **`untracked_data` union**: a candidate whose paths are all `aitasks/`-style
  data paths resolves and **overlaps** an in-flight task declaring the same path.
  Legacy control: with the ref absent and `aitasks/` in `git ls-files`, identical
  behaviour, plus `CORPUS:data|unavailable`.
- **`planned_new` is resolved**: a plan that only creates new files must not
  report `all_phantom`.
- **frontmatter is not a surface**: `Parent Task:` / `Sibling Tasks:` citations
  never reach the comparison, and each stripped token appears as
  `NARROWED:<path>|frontmatter|<n>` so the removal is auditable rather than
  silent.
- **`RECOVERED_*` prohibitions**: recovered-only overlap evidence must not yield
  `CONFLICT`; recovered-only caveat evidence must not yield plain `CLEAR`.
- **raw-path parse**: a path containing `|` round-trips through
  `COMMIT:`/`TASKFILES:` parsing and is `_enc()`-encoded on output.
- **purity**: `subprocess` poisoned + AST guard (Step 8).
- **determinism**: same fixture twice → byte-identical output.
- **negative controls**: a demoted path, an empty candidate surface, and an
  unverified holder must **none** of them produce plain `CLEAR`.
- **self-non-conflict**: the candidate present in *all three* sources yields no
  `OVERLAP:` against itself, and the `RATES:` counts exclude it.

**Entry criterion for t1569_4 — record recall, not just precision.** For a gate
whose failure mode is letting two agents collide, recall governs. Record from a
`replay` over recent real picks: the `CONFLICT` rate, precision, **recall of
`CONFLICT ∪ CLEAR_CAVEATED`**, and the `CAUSE_RATE:` histogram, in the Final
Implementation Notes. On the measured numbers, `parallel_admission: warn` is the
only defensible default today.

Fixture scaffold: `tests/test_change_surface.sh` (one `FIXTURE_ROOT` + `trap
cleanup EXIT`; assertions at **top level**, so `assert_counters_init` is not
needed unless a test body moves into a subshell) and `tests/test_task_file_sets.py`
for the pure-Python half.

Post-implementation cleanup, archival and merge are handled by **Step 9
(Post-Implementation)** of the task workflow.

## Risk

### Code-health risk: medium
- The pure/impure split is the whole design; if `decide` reaches for git, the
  clock or the filesystem, t1569_5's "no subprocess" requirement breaks and a
  second definition of "safe" grows back. · severity: medium · → mitigation: inline post-phase purity_guard
- A third enumeration source, a fifth liveness class and a three-way overlap
  class widen vocabularies that both consumers read; a value added here and
  unhandled downstream degrades silently rather than loudly. · severity: medium ·
  → mitigation: inline post-phase vocabulary_exhaustiveness_guard
- The corpus union is expressed by passing wider sets to the shared
  `plan_paths.classify` rather than by forking it, so no duplicate classifier
  exists — but two *corpora* now coexist and a future reader may not see why the
  drift check keeps the narrower one. · severity: low · → mitigation: TBD

### Goal-achievement risk: medium
- The demotion model and its threshold rest on one corpus snapshot. Demotion
  makes a wrong threshold cost verdict *grading* rather than recall, which bounds
  the damage — but the grading is what t1569_4 blocks on. · severity: medium ·
  → mitigation: spawned after task threshold_sensitivity_replay
- The checker can be entirely correct and still measure ~100% UNCHECKABLE today,
  because the in-flight side has no fallback and two tasks lack plans. A reviewer
  reading the headline rate alone will reasonably conclude the design failed;
  only `CAUSE_RATE:` distinguishes the two. · severity: medium ·
  → mitigation: spawned after task threshold_sensitivity_replay
- `CLEAR` is an observation, not a reservation, and the residual race stays open
  until t1343. If either consumer's wording drifts to "safe to run in parallel",
  the guard over-promises. · severity: low · → mitigation: inline post-phase clear_wording_pin

### Planned mitigations
- timing: post-phase | name: purity_guard | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: pure/impure split eroding | desc: Poison sys.modules for subprocess/shutil/socket, import the core, assert decide still emits the golden bytes; plus an AST guard forbidding import os/time.
- timing: post-phase | name: vocabulary_exhaustiveness_guard | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: widened vocabularies degrading silently downstream | desc: Drive every closed-vocabulary assertion from lib/parallel_admission_vocab.py — reason round-trip with shape validation, an AST scan proving no reason literal bypasses format_reason, and a drift guard pinning the codes imported from t1569_1.
- timing: after | name: threshold_sensitivity_replay | type: test | priority: medium | effort: medium | inline_risk: medium | added_complexity: medium | addresses: threshold and availability rates resting on one snapshot | desc: Re-run replay at hub thresholds 8/10/20/50 over the live corpus, recording precision, recall of CONFLICT u CLEAR_CAVEATED, and the CAUSE_RATE histogram as t1569_4's entry criterion.
- timing: post-phase | name: clear_wording_pin | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: observation-not-reservation guarantee drifting | desc: Assert the DISPLAY line contains "no known conflict at check time" and never the substring "safe to run in parallel".

---

## Final Implementation Notes

### What landed

| file | role | pure? |
|---|---|---|
| `.aitask-scripts/lib/parallel_admission_vocab.py` | the reason/enum table, `format_reason` / `parse_reason`, `encode_path` | yes |
| `.aitask-scripts/lib/parallel_admission.py` | dataclasses, `tier`, `decide`, `render`, the record adapters | yes |
| `.aitask-scripts/lib/parallel_admission_collect.py` | `collect()`, the three probes, liveness, CLI `main` | no |
| `.aitask-scripts/aitask_parallel_admission.sh` | 19-line wrapper over `require_ait_python` | — |
| `tests/test_parallel_admission.py` | 69 core tests | — |
| `tests/test_parallel_admission_vocab.py` | 17 tests — inline mitigation `vocabulary_exhaustiveness_guard` | — |
| `tests/test_parallel_admission_purity.py` | 7 tests — inline mitigation `purity_guard` | — |
| `tests/test_parallel_admission_collect.py` | 40 collector tests via the injectable seams | — |
| `tests/test_parallel_admission_cli.sh` | 24 wrapper/exit-status assertions, incl. `clear_wording_pin` | — |

### Measured rates — t1569_4's entry criterion

Replay over the **124** candidates that have an active plan file, 2026-08-30:

| `--from` / `--lock-freshness` | CLEAR | CLEAR_CAVEATED | CONFLICT | UNCHECKABLE |
|---|---|---|---|---|
| `plan` / `require-fresh` | **60 (48%)** | 25 (20%) | **24 (19%)** | **15 (12%)** |
| `plan` / `allow-cached` | 0 | 85 | 24 | 15 |
| `origin` / `require-fresh` | 17 | 1 | 14 | 92 (74%) |

**These rates are a snapshot, not a constant — re-measure before using them.**
The in-flight population changed twice *during this one session*: three locks
appeared mid-implementation, and by the end two sibling tasks had advanced to
their next child (`1603_1`→`1603_2`, `1636_1`→`1636_2`) with a new `t1640`
freshly claimed. Re-running the identical command an hour later gave
`124|72|18|17|17` — CLEAR 48%→58%, CONFLICT 19%→14% — with **no code change**.
The movement is real signal, not noise: a task that has just been claimed but has
not yet externalised a plan is blocking-eligible with `no_plan`, so it legitimately
makes the check UNCHECKABLE for everyone until its plan lands. Availability is
therefore coupled to how many agents are mid-claim at that moment. Treat the
table as one measurement of the method, and re-run `replay` when the number
actually has to carry a decision.

`CAUSE_RATE` for the `plan` / `require-fresh` row: `all_phantom` 5,
`no_extractable_paths` 9, `no_plan` 1 — **every UNCHECKABLE is candidate-side**;
`hub_overlap_only` 39; `stale_claim` 124 (informational, non-driving).

**The availability prediction was wrong, in the good direction.** The plan
expected ~100% UNCHECKABLE because t1576 and t1555_2 are `Implementing` with no
plan. In practice both are **provably `dead`** (their sessions ended 11 days
ago), so the Step 7 2b matrix *excludes* them and they produce no cause at all.
Combined with Step 5a's corpus union — which cut candidate-side `all_phantom`
from 18 to 5 — UNCHECKABLE lands at **12%**, not 100%. Plain `CLEAR` is reachable
(48%), which is what the `--max-claim-age` bound was added to protect.

`allow-cached` never yields plain `CLEAR` by construction (the cached ref is
always a caveat). That is correct and is why t1569_5's roadmap output is labelled
an estimate.

`origin` provenance is dominated by `unknown_origin`: most of these 124 are
ordinary tasks with no `verifies:`/`anchor:`, so there is no origin to derive a
surface from. It is the right mode for a *follow-up*, not for this population.

### Deviations from the plan, and why

1. **`InflightClaim` carries `claim_at_s` + `claim_age_reason`, not a
   precomputed `claim_age_s`.** The plan declared the latter and a separate
   `now`. Deriving the age inside `decide` makes `now` load-bearing rather than
   decorative, and moves clock-skew detection into the pure, fixture-testable
   half. The plan's contract is unchanged: unknown age ⇒ blocking + caveat,
   boundary pinned at `>`.
2. **`--from origin` resolves the candidate's ORIGIN via `followup_origin`,**
   not its own id. A first pass looked up the candidate's own file set, which is
   always `UNKNOWN_HISTORY` for unlanded work — the mode was inert. Caught by
   `--from auto` and `--from plan` returning byte-identical rates.
3. **`replay` re-aims one snapshot (`_respin`)** instead of re-collecting per
   candidate. The plan specified this; the first pass did not, costing ~2.5 s per
   candidate (~5 min for 124) *and* judging each candidate against a slightly
   different world, which makes the rates incomparable. Now 3.4 s total.
4. **`surfaces_from_inflight_records` takes `data_tracked`.** Without it the
   injected (t1569_5) path inherits the gatherer's code-branch-only
   classification and reproduces the very blind spot Step 5a fixes.
5. **`DISPLAY:` cites only verdict-*driving* caveats.** A `stale_claim` is
   reported but does not drive the verdict, so naming it as the reason for
   `CLEAR_CAVEATED` was misleading.

### Defects found by the tests

- **Identity-key mismatch** in `input_from_records`: surfaces were keyed by the
  gatherer's raw ref (`t9`) and looked up by canonical ref (`9`), so every
  surface silently missed and read as `no_plan` — an UNCHECKABLE that looked
  like a real evidence gap. Both sides are now canonicalised.
- Mutation-tested: removing dead-exclusion fails 4 tests, removing hub demotion
  fails 3, splicing a reason literal past `format_reason` fails the AST guard,
  and the shell test exits 1 on a seeded failure. The suite discriminates.

### Latency

A full `check` is **~2.5 s** (batch map 0.7 s, three probes, per-lock `git show`,
two corpus listings). The plan's "well under a second" described the batch map
alone. `replay` over 124 candidates is 3.4 s.

### Not in scope here

The helper whitelist entries (`aitask_audit_wrappers.sh apply-helper-whitelist`)
and the profile knob `parallel_admission: block|warn|off` belong to **t1569_4**,
which wires this into `task-workflow`.

### Summary bullets

- **Actual work done:** Delivered the shared checker as four source files and
  five test files (3 048 lines, all new — **no existing file was modified**).
  Pure core (`parallel_admission.py`) with a separate vocabulary table
  (`parallel_admission_vocab.py`) and an impure collector
  (`parallel_admission_collect.py`) behind a 19-line shell wrapper. All eight
  plan steps landed, including the three inline post-phase risk mitigations.
  157 tests across the five files, plus the full suite green (5 704 passed).
- **Deviations from plan:** Five, all listed under "Deviations from the plan, and
  why" above — the load-bearing ones are deriving claim age inside `decide`
  (so `now` is real and clock-skew is pure), routing `--from origin` through
  `followup_origin` to resolve the candidate's *origin* rather than its own id,
  and making `replay` re-aim one snapshot as the plan actually specified.
- **Issues encountered:** (1) An identity-key mismatch in `input_from_records` —
  surfaces keyed by raw ref, looked up by canonical ref — which silently degraded
  every injected surface to `no_plan`; found by the boundary test, fixed by
  canonicalising both sides. (2) `--from auto` and `--from plan` returning
  byte-identical rates, which exposed that origin resolution was never wired in.
  (3) Two of my own fixtures were wrong (a hard-coded epoch aged the holder past
  `--max-claim-age`; `allow-cached` always caveats so plain `CLEAR` was
  unreachable) — corrected by anchoring `now` to the fixture's own timestamp.
- **Key decisions:** Demote hub overlaps rather than drop them (dropping costs
  ~two-thirds of real collisions); union the task-data corpus by passing wider
  sets to the *same* `plan_paths.classify` rather than forking it or widening its
  pinned vocabulary; add a third `status` enumeration probe rather than a fifth
  table row; keep `tier` derived rather than stored; treat an unknown claim age
  as blocking-eligible (conservative) with a named caveat.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_lock.sh:416,421,427,437 — list_locks() writes four
    degenerate informational strings ("No locks (no remote configured)", "No
    locks (branch not initialized)", "No locks", "No active locks") to STDOUT via
    info(), which is `echo -e "${BLUE}$1${NC}"` in lib/terminal_compat.sh:19 —
    i.e. non-record prose WITH ANSI escapes on a machine-readable stream. Its
    sibling warn() correctly redirects to stderr. Any parser of `ait lock --list`
    must strip ANSI and pattern-match the record shape to avoid treating these as
    locks.`
- **Notes for sibling tasks:**
  - **t1569_4 (blocking preflight):** call
    `./.aitask-scripts/aitask_parallel_admission.sh check --candidate <id>
    --from plan --lock-freshness require-fresh`. Read `VERDICT:` (always exit 0);
    exit 2 means CLI misuse, not a verdict. `UNCHECKABLE_CAUSE:` is already
    per-source and named, so the operator remedy can name the blocking task.
    **Measured today: CLEAR 48% / CLEAR_CAVEATED 20% / CONFLICT 19% /
    UNCHECKABLE 12%** — materially better than the 100%-UNCHECKABLE projection
    the parent task recorded, because provably-dead holders are excluded. That is
    the entry-criterion evidence for revisiting the `warn` default, but note the
    rate depends on the live in-flight population and should be re-measured.
    Still owed by t1569_4: the helper whitelist entries and the
    `parallel_admission: block|warn|off` profile knob.
  - **t1569_5 (roadmap):** `from parallel_admission import decide,
    input_from_records` — do **not** import `parallel_admission_collect`; a test
    asserts the roadmap path never needs it. Pass `data_tracked=` to
    `input_from_records` or you inherit the gatherer's code-branch-only
    classification and every `aitasks/` path reads as phantom. The gatherer has
    no `status` probe, so supply `SourceEvidence("status", "not_consulted")` —
    which correctly means the roadmap can never emit plain `CLEAR`. Do not
    synthesise `ok` to make the lane look cleaner.
  - **Shared gotcha:** `MAX_CLAIM_AGE_S` and `HUB_THRESHOLD` are module constants
    in the pure core. Both consumers must inherit them; a second default would be
    a second definition of "safe".

### Defects found in Step 8 review — all four in `replay`

The `check` path was sound; every one of these was in the batch verb, and two
could corrupt the very metric t1569_4 uses as its entry criterion.

1. **Self-exclusion leaked across the whole run (high).** `replay` built its base
   snapshot with `_collect_one(opts, cands[0])`, and `collect` removes the
   candidate from the comparison population. `_respin` then removed only the
   *current* candidate and never restored the first one — so whichever candidate
   was listed first became permanently invisible. If it was itself in flight,
   every later candidate was judged against a world where that active task did
   not exist. **Measured: listing live in-flight `t1603_1` first moved CONFLICT
   from 24 to 17 of 124** — a 29% understatement, controlled entirely by input
   order. Fixed with `collect(..., exclude_self=False)` for the base; the
   per-candidate exclusion stays in `_respin`. Pinned by
   `test_rates_do_not_depend_on_candidate_order` plus a discriminating control
   asserting the colliding candidate still reports CONFLICT from either
   position.
2. **Non-positive safety thresholds silently disarmed the guard (high).**
   `--hub-threshold 0` (or negative) makes every path satisfy
   `count >= threshold` — including untouched paths, count 0 — so every
   `specific` overlap is demoted to a hub caveat. `--max-claim-age 0` puts every
   claim past the bound and into the advisory tier. Both were *accepted*
   invocations, not rejected misuse. Verified against live conflicting candidate
   t1061: `--hub-threshold 10` → CONFLICT, `0` / `-1` → CLEAR_CAVEATED; same for
   `--max-claim-age`. Rejected at parse time (exit 2) with a message naming the
   consequence.

   **First fix was insufficient — corrected in a second review round.** Bounding
   the knobs at `>= 1` still let an ordinary `check` flag override a concrete
   CONFLICT: almost every real path has at least one task touch, so
   `--hub-threshold 1` demotes essentially the whole surface (measured over 124
   candidates: **CONFLICT 24 -> 3**), and `--max-claim-age 1` makes every claim
   older than a second advisory. The "1 is still count-dependent" reasoning was
   wrong in practice.

   Both knobs are **monotone in strictness** — verified against t1061:
   `--hub-threshold` 1 -> CLEAR_CAVEATED, 5/10/50/500 -> CONFLICT;
   `--max-claim-age` 1 -> CLEAR_CAVEATED, 86400/1209600/99999999 -> CONFLICT.
   Raising either only turns hub overlaps back into specific ones and advisory
   claims back into blocking ones; it can never hide a collision. So the rule is
   **one-way on `check`**: the floor is the shared default
   (`HUB_THRESHOLD`, `MAX_CLAIM_AGE_S`), anything stricter is accepted, anything
   looser exits 2 with a message pointing at `replay`. `replay` renders no
   admission decision and sweeping thresholds is its purpose, so it accepts any
   positive value. This is what makes "a CONFLICT is not overridable" true of the
   CLI and not just of the verdict logic.
3. **`replay --plan` was accepted and ignored (medium).** `_respin` always calls
   `plan_path_for()` and never sees `opts["plan"]`, so a caller measuring a
   proposed plan silently got rates for the on-disk one. `--plan` names a single
   candidate's file and has no defensible meaning across many, so it is now
   rejected for `replay` with a message pointing at `check`.
4. **Two batch maps per run (medium).** `_collect_one` fetched one inside
   `collect` and `replay` immediately fetched another, so a concurrent commit
   could leave the base's touch counts disagreeing with the candidates'
   origin-derived surfaces. `collect` now accepts injected `batch_lines` and
   `corpus`, and `replay` resolves each exactly once — asserted by counting the
   seam invocations: **1 `_BATCH_MAP` and 1 `_TRACKED_SETS` for 124 candidates.**
   The corpus resolution was a third, unreported instance of the same problem and
   is fixed by the same change (`resolve_corpora`).

All four are mutation-tested: restoring the self-exclusion leak fails 2 tests,
re-fetching the batch map per candidate fails 1. The recorded rates above are the
post-fix ones (the pre-fix baseline read `61|24|24|15`).

**Process note:** the review also caught that an appended test class landed after
this file's `if __name__ == "__main__"` block and therefore never ran — the test
count stayed at 46 instead of 51. Worth checking the count, not just the status,
after adding tests to an existing module.

### Fifth defect — the snapshot did not cover plan files

Found in a later review round. `replay` froze the lock probes, the batch map and
the corpora, but `_respin()` still called `surface_from_plan()` **inside the
reporting loop**. Two consequences, both breaking the one-snapshot contract the
entry-criterion rates depend on:

- a plan edited mid-run produced rates mixed across two plan states, describing
  no world that ever existed;
- the first candidate's plan was read **twice** — once building the base, once
  when its own turn came — so it alone could be judged against a state no other
  candidate saw.

Fixed in two parts. `_respin` no longer touches disk at all: it takes an
already-resolved `Surface`. `replay` resolves **every** candidate surface up
front, before it computes any verdict, via the new standalone
`resolve_candidate_surface()`.

**And a third read the first fix missed, surfaced by the new test.** A task can
appear twice in one run in two different roles — as the candidate *and* as an
in-flight claim — and both read the same plan file. `_plan_surface()` memoises
per run on `(ref, path)`, so one plan file is read once regardless of role.

Pinned by three tests, all mutation-verified (re-reading in the loop fails 3;
dropping the shared cache fails 2):

- `test_every_candidate_surface_is_read_before_any_verdict` — instruments both
  `surface_from_plan` and `decide` and asserts **no plan read occurs after the
  first verdict**. This is an ordering assertion, not a count, so it catches a
  re-read wherever it is reintroduced.
- `test_each_candidate_plan_is_read_exactly_once` — the double-read regression.
- `test_a_repeated_candidate_is_still_read_once` — a candidate listed twice.

**Live note from this round:** a concurrent session claimed `t1640` mid-review.
It is `live` with no externalised plan yet, so it is blocking-eligible with an
invisible surface and correctly makes every candidate `UNCHECKABLE`
(`CAUSE_RATE:no_plan|124`). That is the design working, and it is precisely the
case the cause histogram exists to distinguish from "the method is broken" — one
named task, one cheap remedy.

### A fragile test of my own, found by the same round

`tests/test_parallel_admission_cli.sh` asserted the CLEAR-path wording ("no known
conflict at check time") **unconditionally** against live output. When the
concurrent-session claim of `t1640` pushed the live verdict to `UNCHECKABLE` —
whose `DISPLAY:` correctly says "could not compare" — the assertion failed. The
code was right; the test had pinned one outcome of an environment-dependent run.

Both live assertions are now scoped correctly:

- the **forbidden** phrase ("safe to run in parallel") stays unconditional — no
  verdict may ever claim it;
- the **required** phrase is asserted only for `CLEAR` / `CLEAR_CAVEATED`, with a
  non-clear verdict instead required to explain itself;
- the determinism check compares only the records that do not depend on the live
  in-flight set (`CORPUS:`, `INFLIGHT_SOURCE:`, `CANDIDATE:`). On a repo with
  concurrent agents, asserting byte-equality over `INFLIGHT:`/`VERDICT:` across
  two runs seconds apart is a race, not a determinism check.

The strong guarantees stay pinned deterministically in Python over frozen inputs
(`RenderTests::test_determinism_same_input_twice_is_byte_identical`,
`ClearWordingTests`). **General lesson for the siblings: a live-corpus assertion
belongs on the invariant, never on the current verdict.** Re-ran the shell test
three times for stability and re-verified its negative control (a seeded failure
still exits 1).
