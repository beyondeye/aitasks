# Manual-verification checklist staleness

Design record for the staleness pre-check on `issue_type: manual_verification`
tasks: what v1 does, the one precondition that keeps it small, and what is
deliberately deferred — with the measurements behind each decision, so a later
promotion is an evidence-based call rather than a fresh guess.

Read this before touching the staleness pre-check in
`.claude/skills/task-workflow/manual-verification.md`, the
`verification_baseline:` field, or `file_references:` on a manual-verification
task.

**Implementation status.** This document is the design; the work is queued under
parent **t1555**, whose children are strictly sequential: t1555_1 (check helper +
`verification_baseline:` field) → t1555_2 (Step-8c seeding) → t1555_3 (the
procedure pre-check step) → t1555_4 (the manual-verification sibling covering all
three). Everything under "Deferred" below is deliberately **not** in that chain.

Also related: t1553, an upstream defect in `aitask_revert_analyze.sh` surfaced
while designing this — its `--task-files` output leaks task-metadata paths, which
matters because t1555_2 consumes that helper to propose candidate files.

The generalized sibling of this mechanism — advisory premise staleness for
ordinary backlog tasks, with its own `premise_baseline:` field — is designed in
`aidocs/framework/task_premise_staleness.md` (t1561); this seam stays narrow.

## The problem

A manual-verification checklist is authored once — at parent-task planning time
for aggregate siblings, or at Step 8c for single-task follow-ups (see
`manual-verification-followup.md`) — and then sits `Ready` until someone picks it.
If the code it describes changes meanwhile, the Pass/Fail/Skip/Defer loop walks
the user through verifying items that may no longer describe reality. Before this
check, nothing on that path detected it: the only `stale|drift` occurrence in the
whole manual-verification path is an unrelated comment in
`.aitask-scripts/aitask_verification_parse.py`.

### Measured exposure

| Metric | Value |
|---|---|
| Active `manual_verification` tasks | **77** (76 `Ready`, 1 `Implementing`) |
| Age since `created_at` | median **20 d**, p90 **89 d**, max **116 d** |
| Carrying `verifies:` | 72 / 77 |
| Carrying `file_references:` | **0 / 77** |
| Dispositions recorded to date | PASS 58, DEFER 19, SKIP 2, FAIL 1 |
| Recorded incidents of a stale checklist causing a bad verification | **0** |

Large exposure, **zero recorded harm**. That asymmetry is the primary input to
the sizing: the check must be cheap enough that its cost is justified by
prevention alone.

## Scope discipline — why v1 is deliberately small

The design has one hard precondition:

> The check runs **only** when the task already carries **both** a populated
> `file_references:` list **and** a persisted `verification_baseline:`.
> Otherwise it silently skips.

That single rule is what keeps this a guardrail instead of a task-state
subsystem, and the reasoning is worth preserving because the pressure to relax it
recurs every time a lifecycle edge case appears:

- Because an absent field simply means "skip", there is **no sentinel** needed to
  distinguish "deliberately no scope" from "not yet curated" — which means **no
  presence tracking in the shared `aitask_update.sh` writer**, and **no fold
  rule** in `aitask_fold_mark.sh`.
- Because both fields are written together at one moment when the origin's code
  has just landed, there is **no lazy derivation** — which means no topological
  ancestry resolution, no dominance verification, and no unreachable-commit
  handling.

Each of those mechanisms is a genuine answer to a genuine edge case, and each is
described under "Deferred" below. What made them the wrong call for v1 is the
aggregate: repo-wide changes to a shared writer and to fold behaviour cannot be
justified by a problem with no recorded occurrences. The precondition buys the
core value — *"warn me if the files this checklist explicitly cares about
changed"* — at a fraction of the surface.

**Corollary worth stating plainly:** v1 covers only tasks seeded through Step 8c
after their origin landed. All 77 existing tasks and all 26 aggregate tasks are
skipped. That is a known limit, not an oversight.

## Task-file fields

### Scope — `file_references:`

An explicit list of files whose change means the checklist may no longer describe
reality. No new machinery — the plumbing already exists:

| Piece | Location |
|---|---|
| writer flag `--file-ref REF` (repeatable) + `validate_file_ref` | `.aitask-scripts/aitask_create.sh` |
| `file_references: [...]` frontmatter flow list | `.aitask-scripts/aitask_create.sh` |
| reader `get_file_references()` | `.aitask-scripts/lib/task_utils.sh` |

So a manual-verification task's frontmatter reads `verifies:` = which **tasks**,
`file_references:` = which **files**.

Two accepted costs:

- On other issue types the field means "context files relevant to this task", so
  **the consumer must be `issue_type`-scoped**. The field is not a general
  verification-scope declaration.
- The reader also accepts `path:N`, `path:N-M` and multi-range
  `path:N-M^N-M`. **v1 ignores range suffixes** and the seeder writes bare paths.
  Ranges are deferred (see below), and recording them while ignoring them would
  invite the misreading that they are honoured.

### Baseline — `verification_baseline: <sha> @ <YYYY-MM-DD HH:MM>`

The commit the checklist is known to match. Written once at seed time, then
advanced on review.

`created_at` cannot serve as the baseline:

- `updated_at` is rewritten by **every** checklist state change
  (`_update_updated_at` in `aitask_verification_parse.py`), so it dates the last
  disposition, not the authoring.
- The carry-over path (`create_carryover_task` in `aitask_archive.sh`) re-seeds
  deferred item text verbatim into a **new task with a fresh `created_at`**.

| Event | Baseline |
|---|---|
| seeded at Step 8c (origin has landed) | set to **HEAD at that moment** |
| user answers "Proceed unchanged" | **advance to HEAD** — reviewed and dismissed |
| user answers "Amend the checklist" | **advance to HEAD**, written together with the item edits |
| user aborts | unchanged |
| deferred items carried over | **inherited**, not reset |

**Advancing on dismissal is load-bearing.** Without it, a user who judges a
change immaterial is re-prompted on every later pick and learns to ignore the
prompt — which destroys the feature's value more thoroughly than not having it.

Setting the baseline to HEAD at seed time is correct **because** seeding is
restricted to Step 8c: the origin's code has just landed, so HEAD *is* the
origin's landing point, and no ancestry computation is needed. This is precisely
the assumption that fails for aggregate tasks, which is why those are deferred
rather than special-cased.

`verification_baseline:` is a new field, so `aitask_update.sh` must know it. That
is an **additive** change per `aitasks_extension_points.md` — categorically
different from altering how an existing shared field is emitted.

**Setter interface** (the cross-task contract — both the seeder and the
advance-on-review path go through it, so it is specified here rather than left to
whichever slice lands first):

```bash
./.aitask-scripts/aitask_update.sh --batch <task_id> \
    --verification-baseline "<sha> @ <YYYY-MM-DD HH:MM>"
```

The value is a single scalar in exactly the stored form. An empty string clears the
field. Reads go through `read_yaml_field` like any other scalar; there is no
presence-vs-emptiness distinction to preserve, which is what keeps this additive.

## The check

```
aitask_verification_stale.sh check <task_file>
```

Always exits 0.

```
BASELINE:<sha>|<YYYY-MM-DD HH:MM>
FILES:<n>
CHANGED:<path>|<n_commits>|<task_ids>        0+ lines
DELETED:<path>|<culprit_task>|<subject>      0+ lines
UNKNOWN:<path>|<reason>                      0+ lines
DISPLAY:<one-line human summary>
DECISION:<FRESH|ASK_STALE|SKIP>
```

Ordered evaluation — the order is normative:

```
1. not a git repo                              -> SKIP
2. file_references: empty/absent               -> SKIP   (the precondition)
3. verification_baseline: absent               -> SKIP   (the precondition)
4. baseline not an ancestor of HEAD            -> SKIP   (history rewritten)
5. classify each curated path
6. any CHANGED / DELETED / UNKNOWN             -> ASK_STALE
7. otherwise                                   -> FRESH
```

**`UNKNOWN` drives the verdict — it is not advisory.** A curated path that cannot
be checked means the check is covering *less scope than it claims*, and reporting
`FRESH` in that state would be a false assurance. So an `UNKNOWN:` line raises
`ASK_STALE` exactly like a change does, and the `DISPLAY:` line distinguishes the
two causes, because the remedy differs: a changed file suggests amending the
checklist, an uncheckable path suggests fixing `file_references:`.

`SKIP` is **fail-open** and silent: "cannot tell" is never rendered as "stale".
This mirrors `code_digest` in `.aitask-scripts/lib/gate_ledger.py`, where
unverifiable is its own answer rather than a failure. Steps 2 and 3 are the
common case for every existing task, and that is intended.

### Existence is probed, not inferred

`git log -- <path>` reports history but says **nothing** about whether the path
still exists. Concretely: for a since-deleted
`website/content/docs/installation/arch-aur.md`, `git log <baseline>..HEAD --`
returns 2 commits while the file is gone. A history-only implementation therefore
handles modification correctly and silently misses deletion — the more important
signal.

So each curated path is classified by two cheap probes against the **committed**
trees, not the working tree (which may be dirty):

```bash
git cat-file -e "<baseline>:<path>"   # present at baseline?
git cat-file -e "HEAD:<path>"         # present now?
```

| at baseline | at HEAD | result |
|---|---|---|
| yes | yes | run the history query below → `CHANGED:` or nothing |
| yes | no | `DELETED:` — culprit named by `git log --diff-filter=D -M --name-status <baseline>..HEAD -- <path>` |
| no | — | `UNKNOWN:<path>` — raises `ASK_STALE` (see above) |

The third row cannot arise from the seeder, which writes the paths and the
baseline together from the same landed origin, so every path exists at that commit
by construction. It exists for hand-edited or otherwise invalid entries — and it
must raise a prompt rather than being swallowed, because an unreachable scope entry
means the check silently inspects less than the task claims. Reporting `FRESH` over
a partly-uncheckable scope list is the one outcome this design must not produce:
it is indistinguishable, to the user, from a real all-clear.

History query for surviving paths:

```bash
git log --format='%h|%ad|%s' <baseline>..HEAD -- <path>
```

Task ids on the `CHANGED:` line come from commit subjects via the existing
parenthesised-tag convention (the `(tNN)` / `(tNN_M)` suffix that
`aitask_revert_analyze.sh` and friends already match).

Latency is milliseconds — two `cat-file` probes plus one `git log` per path — so
there is no time-based trigger and **no profile key** in v1.

## Procedure placement

The pre-check is a step in `.claude/skills/task-workflow/manual-verification.md`,
inserted **between step 1 (ensure the task has a checklist) and step 1.5 (the
autonomous-verification offer)**. Both bounds matter:

- It must run **before** 1.5, because that step can dispatch autonomous
  verification, which would otherwise work through stale items unattended.
- It must run **after** 1, because step 1's seed path can create the checklist
  mid-step.

`SKIP` and `FRESH` continue silently. On `ASK_STALE` the `DISPLAY:` line is
printed verbatim and the user is prompted — mirroring the `ASK_STALE` prompt
shape in `planning.md` — with three options: amend the checklist, proceed
unchanged, or abort.

It is **advisory**: it never blocks archival, and nothing is rewritten without
the user accepting it.

### The review transaction

On the amend path the baseline advance happens **only after** the user's final
accept/edit decision, and it is written **together with** every other mutation the
amend produced.

Advancing first and then failing — or the user abandoning the edit — would
permanently dismiss the very change the user was brought in to review, and with
the baseline already at HEAD no later pick would raise it again. That is a silent,
unrecoverable loss of the signal the feature exists to produce.

The amend path can produce **three** mutations, and all three target the same
file:

| Mutation | Location | When |
|---|---|---|
| checklist item text | body | items are stale |
| `file_references:` | frontmatter | an `UNKNOWN:` path needs the scope list repaired |
| `verification_baseline:` | frontmatter | always, on accept |

Because it is one file, they compose into a single `ait_atomic_render` pass from
`.aitask-scripts/lib/atomic_write.sh`. Prefer that.

**A scope repair removes the bad entry; appending is not a repair.**
`--file-ref` appends with exact-string dedup and never displaces an existing
entry, so adding a replacement while leaving the bogus path behind means the next
check still emits `UNKNOWN:` and `ASK_STALE` — with the baseline already advanced.
That is the forbidden state, reachable by an incomplete repair. The repair shape
is therefore:

```bash
./.aitask-scripts/aitask_update.sh --batch <task_id> \
    --remove-file-ref "<bad_path>" \
    [--file-ref "<replacement_path>"] \
    --verification-baseline "<sha> @ <YYYY-MM-DD HH:MM>"
```

`process_file_references_operations` handles the add and remove sets in one pass
(append first, then exact-string removal), so this is a single atomic re-emit.
Dropping the entry outright is a legitimate repair, as is replacing it with the
path the file moved to.

**The invariant, which holds however the writes are decomposed: the baseline may
advance only after every other mutation has durably succeeded.** If the
implementation does use separate writes, the baseline advance must be strictly
last and must be skipped when any earlier write failed. That confines every
failure state to "scope and/or items updated, baseline not advanced" — which
re-prompts on the next pick and is idempotent. The forbidden state is the mirror
image: a baseline at HEAD sitting over an invalid scope list or half-applied
items, which is silently unreviewable forever.

**Rule: decide → write everything → advance the baseline last → commit.** Never
advance → edit.

Amendment is a direct edit of the item text. `seed` refuses to run when a
checklist section already exists, and v1 adds no `amend` verb; the audit trail is
the task file's git history plus the advanced baseline.

## Seeding — Step 8c only

At Step 8c the origin task's code has just been committed, so its files are
discoverable and HEAD is its landing point:

1. derive candidates with
   `./.aitask-scripts/aitask_revert_analyze.sh --task-files <origin>`, which
   returns `FILE|<path>|<ins>|<del>`;
2. the authoring agent **narrows** to the files the checklist actually exercises,
   using the plan `## Verification` bullets it is already reading;
3. the **user confirms** the shortlist;
4. both fields are written — the paths as repeatable `--file-ref` arguments (bare
   paths), and `verification_baseline:` = HEAD.

### Narrowing is mandatory, not a nicety

Writing the derived set unfiltered reproduces the always-fires behaviour that
makes the whole check worthless. For origin t632 the derived set was 10 files;
counting how many distinct tasks have touched each shows why:

```
lib/agent_launch_utils.py     40 tasks   (+49 lines)  <- relevant
test_tmux_exact_session_...sh  4 tasks   (+149)       <- relevant
board/aitask_board.py         91 tasks   (+7)         <- incidental call site
monitor/monitor_app.py        73 tasks   (+7)         <- incidental call site
monitor/minimonitor_app.py    72 tasks   (+11)        <- incidental call site
```

The hub files were touched by a one-line call-site update each. A curated
two-entry list is informative; the unfiltered ten-entry list fires on almost
every commit.

### Only the promptable path is in scope

Where Step 8c cannot prompt, no fields are written and the task simply skips.
That costs nothing today: `manual_verification_followup_mode: never` on
`remote.yaml` and both seed profiles means those profiles create no
manual-verification task at 8c in the first place.

If the shortlist comes out empty, write nothing. The task skips, and no sentinel
is needed to record the decision — which is exactly the simplification the
precondition buys.

## Why this is not a declared gate

`lib/task_utils.sh` defines an **allowlist**:

```bash
MANUAL_VERIFICATION_REACHABLE_GATES="build_verified tests_pass lint"
```

`filter_gates_for_issue_type()` strips **any** gate outside that list from a
`manual_verification` task, deliberately, so that a newly added gate can never
render one unarchivable. A `verification_not_stale` gate would therefore be
**silently stripped** unless the allowlist and
`tests/test_create_manual_verification_gates.sh` were amended too — and combined
with `max_retries: 0` and manual-verification tasks skipping workflow steps 6–8,
a gate here risks holding tasks in-flight indefinitely.

The precedent agrees: plan-verification staleness is a procedure step in
`planning.md`, not a gate.

## Reuse — the seams this composes

- `get_file_references()` / `validate_file_ref` / `--file-ref` — the scope field.
- `aitask_revert_analyze.sh --task-files <id>` → `FILE|<path>|<ins>|<del>`, used
  **only at seed time** to propose candidates. It is **children-inclusive**, which
  matters: `(t623)` matches **0** commits directly because all that work landed
  under child ids, yet `--task-files 623` correctly returns 24 files. The naive
  `git log --grep "(tNN)"` lookup — of which the repo contains several
  independent copies — finds nothing for such a parent.
- `aitask_remote_drift_check.sh` — the structural template: always exit 0, fixed
  protocol tokens plus variable evidence lines, and it already implements
  "changed paths ∩ paths I care about".
- `aitask_plan_verified.sh decide` — the verdict-line shape. Note its deliberate
  split: `decide` tolerates a missing artifact and emits a verdict, while `read`
  dies on one.
- `ait_atomic_render` in `lib/atomic_write.sh` — the single-file transaction.

## Deferred, with the evidence

None of the following is built. Each entry records the measurement that would
justify it, so promotion is an evidence-based decision.

**Promotion trigger:** v1 proves useful *and* its precondition proves too narrow
— concretely, users seed the fields and then report either that the prompt is
noisy, or that tasks they care about are being skipped.

### Aggregate / parent-planning tasks (26 of 77)

Seeding happens during parent planning, **before** any child is implemented.
Measured: `t1505_5` was seeded **2026-08-13 12:31** while its four origins landed
**2026-08-13 21:43**, **08-14 10:12**, **08-16 10:59** and **08-17 11:36**.

So at seed time `--task-files` returns **empty** for every origin, and HEAD is not
the origins' landing point — a baseline set there would flag every curated file on
the first pick, training the user to dismiss the first prompt they ever see.
Supporting this needs lazy resolution *and* a topological definition of the
origins' landing point.

### Topological baseline resolution

"Newest origin commit" is **not** a date-max. `aitask_revert_analyze.sh` searches
`git log --all`, which spans the **`aitask-data`** branch, and those commits carry
`(tNN)` tags too.

Live case **t1362**: its origin set contains a commit
(`ait: Amend contract D — drop the seed resolution tier (t1223_4)`) that exists
only on `aitask-data`, is **unreachable from HEAD**, and stands in no ancestor
relation to the date-newest origin commit. Selecting it as a baseline makes
`baseline..HEAD` the entire **2199-commit** history, so every curated file reads
as changed.

Measured across the 15 multi-origin manual-verification tasks whose origins have
commits: **14 satisfy ancestry, 1 violates it**.

A correct implementation must: filter candidates to HEAD-reachable commits
(`git merge-base --is-ancestor`), select topologically
(`git rev-list --topo-order`), verify the selection dominates every other
candidate, and fall back to HEAD when it does not.

### Multi-origin candidate derivation

`verifies:` is plural on **22 of 72** tasks, up to **11** origins. The union needs
deduplication: t623's six origins yield **29** raw `FILE|` entries for **24**
unique paths.

### Unattended / auto-curation

Narrowing without a user confirmation on non-promptable paths, with recorded
provenance distinguishing agent-selected from user-confirmed scope.

### The `[]` no-scope sentinel — and everything it drags in

Expressing a durable "curated, deliberately no scope" state is not a one-line
change. `file_references` is **value-tracked** in `aitask_update.sh`, and emitted
only when non-empty, so any unrelated update — a plain `--status Done` — drops an
empty list. Making it durable requires:

- the **presence-tracked** pattern already used for `active_gates: []` in the same
  file, whose own comment states the reason: value emptiness cannot express
  "explicitly empty";
- new writer verbs to *set* `[]` and to *remove* the field, since "no scope
  declared" and "not yet curated" become different states;
- a fold rule, because `union_file_references()` reads through
  `get_file_references()` and cannot tell absent from empty, so
  `aitask_fold_mark.sh` would either adopt a folded child's scope or drop the
  marker.

v1 needs none of it: an absent field already means "skip".

### Legacy-task support

The 77 existing tasks carry neither field and are skipped. Backfilling is a
curation exercise, not a code change.

### Line ranges

`file_references:` already carries the grammar, and a ranged query is fast
(measured 0.019 s via `git log -L <a>,<b>:<file>`, roughly 20× cheaper than a
per-file blame) and names the culprit task. The blocker is **range stability**: a
range recorded against one revision does not stay meaningful as the file changes
around it, and `git log -L` errors outright when the range no longer exists. A
range-rebasing or range-invalidation story is needed first.

### Line-survival scoring

`git blame -w -M` survival of the origin commits' own lines, over the `<ins>`
denominator that `--task-files` already returns. It genuinely discriminates:

- origin **t632** (10 files, 270 added lines): aggregate **63 %**, per-file
  100 / 85 / 65 / 44 / 14 / 0 / 0 %  — the two zeros being files rewritten
  wholesale;
- origin **t623** (24 files, 2031 added lines): aggregate **33 %**, with **7
  origin files deleted** — e.g. an installation page removed by t766 *"Regroup
  installation pages"*, and a packaging doc removed by t901 *"Reorganize
  aidocs"*.

Costs ~3.7 s for 10 files and ~9 s for 24, and needs a calibrated threshold plus
a profile key (which touches seven surfaces). `-w -M` matters: whitespace and
move churn otherwise reads as a rewrite. `-C` is expensive and adds almost
nothing.

### A derived-file fallback

Deriving the file set from `verifies:` instead of curating it is only viable
*with* the scoring layer. Plain file-level matching over a derived set is
useless: **201** later commits touched t632's files, and across 10 sampled tasks
the commits-since-seed were 121, 81, 63, 35, 29, 14, 7, 5, 5, 3 — **10 of 10
would flag**.

### An `amend` verb

Per-item amendment with audit annotations, respecting the existing item
annotation convention (` — ` as the annotation separator, with a right-to-left
strip scan).

### Time-based triggers

Rejected as a **verdict**: median checklist age is 20 **days**, so all 77 tasks
are stale under any hours-scale threshold — zero information. Unnecessary as a
**trigger**, because the check is already milliseconds.

## Known limits of the approach itself

Two are inherent and will not be fixed by any of the deferred work:

- **The check measures change, not behavior.** An item can go stale with every
  curated file untouched (a default changed elsewhere, an upstream dependency
  bump), and can stay perfectly valid after a behavior-preserving refactor
  rewrites the file. Both error directions persist. This is why the verdict is
  advisory and evidence-presenting rather than authoritative or blocking.
- **A silent-skip precondition can mask a broken implementation.** If seeding
  never writes the fields, the check is indistinguishable from one that is
  working correctly and staying quiet. Only an end-to-end exercise — seed a task
  with curated files, change one, confirm the prompt fires, dismiss it, confirm
  it does not re-fire — distinguishes "correctly quiet" from "never runs".
