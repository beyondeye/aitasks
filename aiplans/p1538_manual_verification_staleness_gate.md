---
Task: t1538_manual_verification_staleness_gate.md
Branch: (current-branch mode — main)
Base branch: main
Output branch: main
---

# p1538 — Manual-verification staleness gate (design pass)

## Context

`issue_type: manual_verification` tasks carry a checklist authored once, then sit
`Ready` until someone picks them. If the code the checklist describes changes
meanwhile, `manual-verification.md` walks the user through verifying items that may
no longer describe reality. There is no staleness detection anywhere on that path
today (the only `stale|drift` hit in the whole MV path is an unrelated comment at
`aitask_verification_parse.py:40`).

This task is the **design pass only** — it lands a design document plus sized
follow-up tasks, no implementation.

### Measured exposure (this repo, today)

| Metric | Value |
|---|---|
| Active `manual_verification` tasks | **77** (76 `Ready`, 1 `Implementing`) |
| Age since `created_at` | median **20d**, p90 **89d**, max **116d** |
| Carrying `verifies:` | 72 / 77 |
| Carrying `file_references:` | **0 / 77** |
| Dispositions recorded to date | PASS 58, DEFER 19, SKIP 2, FAIL 1 |
| Recorded incidents of a stale checklist causing a bad verification | **0** |

Large exposure, **zero recorded harm**. That asymmetry is the single most
important input to the sizing.

## Scope discipline — why v1 is this small

An earlier draft of this design grew, one locally-reasonable fix at a time, into a
new task-state subsystem: persistent baselines derived by topological git ancestry,
first-pick curation with an unattended mode, a `[]` no-scope sentinel, presence
tracking in the **shared** `aitask_update.sh` writer, fold semantics in
`aitask_fold_mark.sh`, five skip reasons and four verdicts. Every one of those was
a real answer to a real edge case. The aggregate was still wrong: repo-wide changes
to a shared writer and to fold behaviour cannot be justified by a problem with no
recorded occurrences.

**v1 therefore has one hard precondition, and everything else follows from it:**

> The check runs **only** when the task already carries **both** a populated
> `file_references:` list **and** a persisted `verification_baseline:`.
> Otherwise it silently skips.

That precondition is what deletes the subsystem. Because absent fields simply mean
"skip", v1 needs no sentinel to distinguish "no scope" from "not yet curated" —
which in turn needs no presence tracking in the shared writer, and no fold rule.
Because the fields are written together at one moment when the origin has just
landed, v1 needs no lazy derivation — which needs no topological ancestry, no
dominance check and no unreachable-commit handling.

§5 lists everything deferred, with the evidence already gathered, so none of that
analysis is lost.

## Decisions

1. **Scope is explicit, never derived** — the check only ever consults a file list
   a human confirmed.
2. **Reuse `file_references:`** on manual-verification tasks; no new list field.
3. **Whole files only** — the parser accepts `path:N-M` ranges; v1 ignores range
   suffixes and the seeder writes bare paths (§4).
4. **`verification_baseline:`** — a new frontmatter field, written **once** at seed
   time and advanced on review (§1.2).
5. **Both fields present or silently skip** — the precondition above.
6. **Seed only the straightforward case**: Step 8c single-task follow-ups, after the
   origin's code has landed (§1.3).
7. **Advisory, never blocking** — a procedure pre-check step, not a declared gate
   (§3).
8. **Deliverable** — a design doc in `aidocs/framework/` plus follow-up tasks.

---

## 1. Task-file fields

### 1.1 Scope — `file_references:`

An explicit list of files whose change means the checklist may no longer describe
reality. No new machinery: the field and its plumbing already exist —
`--file-ref REF` (repeatable) with `validate_file_ref` at `aitask_create.sh:209`,
the `file_references: [...]` flow list at `:562-566`, and the reader
`get_file_references()` at `lib/task_utils.sh:1337`.

An MV task's frontmatter then reads `verifies:` = which **tasks**,
`file_references:` = which **files**.

Accepted cost: on other issue types the field means "context files", so the
consumer must be `issue_type`-scoped and the doc must say so.

### 1.2 Baseline — `verification_baseline: <sha> @ <YYYY-MM-DD HH:MM>`

The commit the checklist is known to match. Written at seed time, then advanced on
review.

`created_at` cannot serve: `updated_at` is clobbered by every `set` call
(`aitask_verification_parse.py::_update_updated_at`), and the carry-over path
(`aitask_archive.sh::create_carryover_task`) re-seeds deferred items into a **new
task with a fresh `created_at`**.

| Event | Baseline |
|---|---|
| seeded at 8c (origin has landed) | set to **HEAD at that moment** |
| "Proceed unchanged" | advance to HEAD — reviewed and dismissed |
| "Amend the checklist" | advance to HEAD, written with the item edits (§3) |
| abort | unchanged |
| deferred items carried over | **inherited**, not reset |

Advancing on dismissal is load-bearing: without it a user who judges a change
immaterial is re-prompted on every later pick and learns to ignore the prompt.

Setting the baseline to HEAD at seed time is correct **because of** decision 6:
the origin's code has just landed, so HEAD *is* the origin's landing point. No
ancestry computation is needed — and this is precisely the assumption that fails
for aggregate tasks, which is why those are deferred rather than special-cased
(§5).

This is a new field, so `aitask_update.sh` needs to know it. That is an **additive**
change following `aidocs/framework/aitasks_extension_points.md` — routine, and
categorically different from altering how an existing shared field is emitted.

## 2. The check

One helper, one question.

```
aitask_verification_stale.sh check <task_file>
```

Always exits 0.

```
BASELINE:<sha>|<YYYY-MM-DD HH:MM>
FILES:<n>
CHANGED:<path>|<n_commits>|<task_ids>        0+ lines
DELETED:<path>|<culprit_task>|<subject>      0+ lines
UNKNOWN:<path>|<reason>                      0+ lines, advisory only
DISPLAY:<one-line human summary>
DECISION:<FRESH|ASK_STALE|SKIP>
```

Ordered evaluation:

```
1. not a git repo                              -> SKIP
2. file_references: empty/absent               -> SKIP     (the precondition)
3. verification_baseline: absent               -> SKIP     (the precondition)
4. baseline not an ancestor of HEAD            -> SKIP     (history rewritten)
5. classify each curated path
6. any CHANGED / DELETED                       -> ASK_STALE
7. otherwise                                   -> FRESH
```

`SKIP` is **fail-open** and silent: "cannot tell" is never rendered as "stale"
(mirroring `lib/gate_ledger.py::code_digest`, where unverifiable is its own
answer). Steps 2 and 3 are the common case for all 77 existing tasks, and that is
intended.

**Existence is probed, not inferred.** `git log -- <path>` reports history but says
nothing about whether the path still exists — for the deleted
`website/content/docs/installation/arch-aur.md`, `git log <baseline>..HEAD --`
returns 2 commits while the file is gone. So each path is classified by two cheap
probes against the **committed** trees (not the dirty worktree):

```bash
git cat-file -e "<baseline>:<path>"   # present at baseline?
git cat-file -e "HEAD:<path>"         # present now?
```

| at baseline | at HEAD | result |
|---|---|---|
| yes | yes | history query below → `CHANGED:` or nothing |
| yes | no | `DELETED:` — culprit from `git log --diff-filter=D -M --name-status <baseline>..HEAD -- <path>` |
| no | — | `UNKNOWN:<path>|absent_at_baseline` — reported, does not drive the verdict |

The third row cannot arise from the seeder (it writes the paths and the baseline
together, from the same landed origin, so the paths exist at that commit by
construction); it exists only to keep a hand-edited list from silently
under-covering.

```bash
git log --format='%h|%ad|%s' <baseline>..HEAD -- <path>
```

Task ids for `CHANGED:` come from commit subjects via the existing
`\(t[0-9]+(_[0-9]+)?\)` convention. Latency is milliseconds — two `cat-file` probes
plus one `git log` per path — so there is no time-based trigger and **no profile
key** in v1.

## 3. Procedure wiring — a new pre-check step in `manual-verification.md`

Numbered `### 1.3` in that file's own scheme (its steps run 1, 1.5, 2, 3, 4, 5),
inserted **between §1 and §1.5**. The ordering is load-bearing: §1.5 can dispatch
autonomous verification, which would otherwise auto-verify stale items unattended.
It must sit after §1, whose seed path can create the checklist mid-step.

`SKIP` / `FRESH` → continue silently. On `ASK_STALE`, print `DISPLAY:` verbatim —
e.g. *"2 of the 3 files this checklist covers changed since it was last reviewed
(2026-06-01): `lib/agent_launch_utils.py` (t1451, t1029), `tests/test_tmux_…sh`
(t1029)"* — then prompt, mirroring `planning.md`'s `ASK_STALE` shape:

- **"Amend the checklist"** — the agent shows the changed files' diffs against the
  baseline beside the current checklist and proposes item edits; the user accepts /
  edits / rejects per item.
- **"Proceed unchanged"** — staleness noted, judged immaterial.
- **"Abort"** — Task Abort Procedure; baseline untouched.

Advisory only: it never blocks archival, and nothing is rewritten without the user
accepting it.

**Review transaction — ordering is load-bearing.** On the amend path the baseline
advance happens **only after** the user's final accept/edit decision, and the
checklist edit and the baseline update are written **together**. Advancing first
and then failing (or the user abandoning the edit) would permanently dismiss the
change the user was brought in to review — and with the baseline at HEAD, no later
pick would ever raise it again. Both writes target the same file (baseline in
frontmatter, items in body), so they compose into one `ait_atomic_render` call from
the existing `lib/atomic_write.sh`. Rule: **decide → write both → commit**, never
advance → edit.

Amendment is a direct edit: `seed` refuses when a section exists
(`aitask_verification_parse.py:292`), and v1 adds **no** `amend` verb. The audit
trail is the task file's git history plus the advanced baseline.

## 4. Seeding — Step 8c only, after the origin landed

At Step 8c the origin task's code has just been committed, so its files are
discoverable and HEAD is its landing point. The seeder:

1. derives candidates via `aitask_revert_analyze.sh --task-files <origin>`, which
   returns `FILE|<path>|<ins>|<del>`;
2. the authoring agent **narrows** to the files the checklist actually exercises,
   using the plan `## Verification` bullets it is already reading;
3. the **user confirms** the shortlist;
4. both fields are written: the paths as repeatable `--file-ref` arguments (bare
   paths, no range suffixes) and `verification_baseline:` = HEAD.

Curation is what makes the signal worth having. For origin t632 the derived set was
10 files, but the per-file "how many distinct tasks have touched this since April"
counts show why it must be narrowed:

```
lib/agent_launch_utils.py     40 tasks   (+49 lines)  <- relevant
test_tmux_exact_session_...sh  4 tasks   (+149)       <- relevant
board/aitask_board.py         91 tasks   (+7)         <- incidental call site
monitor/monitor_app.py        73 tasks   (+7)         <- incidental call site
monitor/minimonitor_app.py    72 tasks   (+11)        <- incidental call site
```

Writing the unfiltered set would reproduce the always-fires behaviour that made a
derived file set useless (§5).

**Only the promptable path is in scope.** Where 8c cannot prompt, no fields are
written and the task simply skips — and that costs nothing today, because
`manual_verification_followup_mode: never` on `remote.yaml` and both seed profiles
means those profiles create no MV task at 8c in the first place. If the shortlist
comes out empty, write nothing: the task skips, and no sentinel is needed to record
it.

## 5. Deferred, with the evidence already gathered

Recorded in the design doc so none of this is re-derived, and so each promotion is
an evidence-based decision rather than a fresh guess.

**Promotion trigger:** v1 proves useful *and* its precondition proves too narrow —
concretely, users seed the fields and then report either that the prompt is noisy
or that tasks they care about are being skipped. Until that is observed, none of
the following is built.

- **Aggregate / parent-planning tasks (26 of 77).** Seeding happens during parent
  planning, **before** any child is implemented: `t1505_5` was seeded
  **2026-08-13 12:31** while its four origins landed 2026-08-13 21:43 through
  **08-17 11:36**. So at seed time `--task-files` returns empty and HEAD is not the
  origins' landing point — a baseline set there would flag every curated file on the
  first pick. Supporting this needs lazy resolution *and* a topological definition of
  the origins' landing point, which needs ancestry handling (below). Deferred whole.
- **Topological baseline resolution.** "Newest origin commit" is not a date-max:
  `aitask_revert_analyze.sh` searches `git log --all` (`:132`, `:207`), which spans
  the **`aitask-data`** branch, and those commits carry `(tNN)` tags too. Live case
  **t1362**: origin commit `749f9e597` (*"ait: Amend contract D…"*) exists only on
  `aitask-data`, is unreachable from HEAD, and is in no ancestor relation with the
  date-newest `8cdea3473`; selecting it makes `baseline..HEAD` the entire
  **2199-commit** history. Measured: of the 15 multi-origin MV tasks with origin
  commits, **14 satisfy ancestry, 1 violates it**. A full version needs: filter to
  HEAD-reachable commits, select topologically via `git rev-list --topo-order`,
  verify dominance with `merge-base --is-ancestor`, fall back to HEAD.
- **Multi-origin candidate derivation.** `verifies:` is plural on **22 of 72** tasks
  (up to 11 origins), and the union needs dedup — t623's six origins yield 29 raw
  `FILE|` entries for 24 unique paths.
- **Unattended / auto-curation** on non-promptable paths, with recorded provenance
  distinguishing agent-selected from user-confirmed scope.
- **The `[]` no-scope sentinel** and everything it drags in: `file_references` is
  value-tracked in `aitask_update.sh` (`:590`, `:785`) so any unrelated update — a
  plain `--status Done` — drops an empty list; expressing a durable "no scope"
  requires the presence-tracked `active_gates` pattern (`:453-456`, `:765-770`), new
  `--file-refs-none` / `--file-refs-clear` verbs, and a fold rule, because
  `union_file_references()` (`:1378`) reads through `get_file_references()` and
  cannot tell absent from empty, so `aitask_fold_mark.sh:176-186` would either
  adopt a folded child's scope or drop the marker. v1 needs none of it: an absent
  field already means "skip".
- **Legacy-task support** for the 77 existing tasks — they carry no fields and are
  skipped. Backfilling is a curation exercise, not a code change.
- **Line ranges.** `file_references:` already has the grammar and a ranged query is
  fast (0.019s via `git log -L <a>,<b>:<file>`) and names the culprit task, but
  **range stability** is unsolved: a range recorded against one revision does not
  stay meaningful as the file changes around it, and `git log -L` errors when the
  range no longer exists.
- **Line-survival scoring.** `git blame -w -M` survival over the `<ins>`
  denominator. Discriminating: t632 aggregate **63%** with a real per-file spread
  (100/85/65/44/14/0/0%); t623 aggregate **33%** with 7 origin files deleted (e.g.
  `arch-aur.md` deleted by t766, `packaging_strategy.md` by t901). Costs ~3.7s for
  10 files, needs a calibrated threshold and a profile key (7 surfaces).
- **A derived-file fallback.** Only viable *with* scoring: plain file-level matching
  over derived files is useless — **201** later commits touched t632's files, and
  across 10 sampled tasks the commits-since-seed were 121, 81, 63, 35, 29, 14, 7, 5,
  5, 3, i.e. **10/10 would flag**.
- **An `amend` verb** with per-item audit annotations, respecting the
  `SUFFIX_SPLIT = " — "` convention and right-to-left `_strip_annotation` scan.
- **Time-based triggers.** Rejected as a *verdict*: median checklist age is 20
  **days**, so all 77 are stale under any hours-scale threshold. Unnecessary as a
  trigger, since the check is already milliseconds.

## 6. Why not a declared gate — a hard blocker, not a preference

`lib/task_utils.sh:711` defines an **allowlist**:

```bash
MANUAL_VERIFICATION_REACHABLE_GATES="build_verified tests_pass lint"
```

`filter_gates_for_issue_type()` strips **any** gate outside it from a
`manual_verification` task — deliberately, per t1156, so a new gate can never make
one unarchivable. A `verification_not_stale` gate would be **silently stripped**
unless the allowlist and `tests/test_create_manual_verification_gates.sh` were also
amended; combined with `max_retries: 0` and MV tasks skipping Steps 6–8, a gate here
risks holding tasks in-flight forever. The precedent agrees: plan staleness is a
procedure step in `planning.md` §6.0, not a gate.

## 7. Reuse — seams v1 composes (verified live)

- `get_file_references()` / `validate_file_ref` / `--file-ref` — §1.1.
- `aitask_revert_analyze.sh --task-files <id>` → `FILE|<path>|<ins>|<del>`, used
  **only at seed time** to propose candidates. Children-inclusive: `(t623)` matches
  **0** commits directly (all work landed in children) yet `--task-files 623`
  returns 24 files, where the naive `git log --grep "(tNN)"` used by 5 of the 7
  existing copies of that lookup finds nothing.
- `aitask_remote_drift_check.sh` — structural template: always exit 0, fixed tokens
  plus variable lines, and it already does "changed paths ∩ paths I care about".
- `aitask_plan_verified.sh decide` — verdict-line shape; note `decide` tolerates a
  missing artifact while `read` dies. Mirror that split.
- `lib/atomic_write.sh::ait_atomic_render` — the single-file transaction in §3.

## Files this task lands

- **New:** `aidocs/framework/manual_verification_staleness.md` — the design record:
  measured exposure, the v1 design, the scope-discipline rationale, and §5's
  deferred list with its evidence.
- **New:** `aiplans/p1538_manual_verification_staleness_gate.md` (this plan).
- **Pointer:** one `CLAUDE.md` "Read …" line so the doc is discoverable.

No code changes — the non-goal is respected.

## Follow-up tasks to spawn (independent, dependency-chained)

1. **Check helper + `verification_baseline:` field** — `aitask_verification_stale.sh
   check` (the ordered evaluation, existence probes, history query) plus additive
   write support for the new field in `aitask_update.sh` and carry-over inheritance.

   Tests — bash with `tests/lib/asserts.sh`, fixed deterministic timestamps in the
   style of `tests/test_risk_mitigation_landed.sh`, over a sandbox git repo:
   - **positive:** a curated file **modified** since the baseline ⇒ `ASK_STALE` with
     a `CHANGED:` line naming the culprit task
   - **positive:** a curated file **deleted** ⇒ `ASK_STALE` with a `DELETED:` line,
     asserting detection via the `git cat-file -e HEAD:<path>` probe rather than
     inferred from history — a history-only implementation passes the modified case
     and silently fails this one
   - **mixed:** one changed, one deleted, one untouched ⇒ exactly two evidence
     lines, `FILES:3`, `ASK_STALE`
   - **negative control:** curated files untouched ⇒ `FRESH`, with a named failing
     id if not — a detector that cannot say FRESH is the failure mode §5's
     measurements are all about
   - **precondition skips:** populated list but no baseline ⇒ `SKIP`; baseline but
     no list ⇒ `SKIP`; neither ⇒ `SKIP`; baseline not an ancestor of HEAD ⇒ `SKIP`.
     Each asserts no `CHANGED:` / `DELETED:` line
   - **baseline advance:** after "Proceed unchanged" the baseline is at HEAD and a
     re-run reports `FRESH` — the prompt does not re-fire
   - **transaction:** a failure injected between decision and write leaves the task
     file **byte-identical** — neither items nor baseline advanced (the
     `tests/test_atomic_task_file_writes.sh` shape)
   - `verification_baseline:` round-trips and survives an unrelated update
2. **Step-8c seeding** — derive candidates, agent narrows, user confirms, write both
   fields. Promptable path only; write nothing when the shortlist is empty or the
   context cannot prompt. Depends on 1.
3. **Procedure step + rerender** — the new pre-check step, the three-option prompt,
   the transaction-ordered baseline advance, rerender per profile
   (`aitask_skill_rerender.sh`) and regenerate goldens. Depends on 1, 2.

Plus one **aggregate manual-verification sibling** covering 1–3: land a task through
8c with curated files, change one, confirm the prompt fires, dismiss it, confirm it
does not re-fire. Depends on 3.

### Post-phase (risk mitigations)

- **commit_scope_check** — before committing, run `git status --short` and stage the
  doc, plan and `CLAUDE.md` by **explicit path** (`git commit -o -- <paths>`); never
  `git add -A`. Confirm the commit's diff contains no `.aitask-scripts/` or `tests/`
  path — `main` already carries unrelated uncommitted minimonitor / review_loop
  edits.
- **accepted_costs_stated** — the doc must write the accepted costs down explicitly
  rather than glossing them: (a) `file_references:` means "context files" on other
  issue types, so the consumer is `issue_type`-scoped and range suffixes are
  ignored; (b) v1 covers **only** tasks seeded through 8c after their origin landed
  — all 77 existing tasks and all 26 aggregate tasks are skipped; (c) a task whose
  fields were never written is silently skipped, by design.
- **stage2_evidence_recorded** — the doc must carry §5's deferred list *with* its
  measurements (t1362 unreachable-origin, 14/15 ancestry, 201-commit and 10/10
  derived-set results, the survival spreads, the `git log -L` range-stability
  blocker, the `aitask_update.sh` value-tracking defect) **and** the promotion
  trigger, so each deferral stays revisitable on evidence rather than being
  re-derived. It must also record *why* the earlier over-built draft was cut, since
  that reasoning is the most reusable part of this task.

## Verification

Documentation only, so verification is doc-level plus re-runnability of the
evidence:

1. `aidocs/framework/manual_verification_staleness.md` exists and states the v1
   design, the one-line precondition, and the scope-discipline rationale.
2. The doc's §5 equivalent lists every deferred item **with** the number or live
   case that motivates it, and the promotion trigger.
3. The reuse claims resolve to real code: `get_file_references` at
   `lib/task_utils.sh:1337`, `--file-ref` at `aitask_create.sh:209`,
   `MANUAL_VERIFICATION_REACHABLE_GATES` at `lib/task_utils.sh:711`. Spot-check
   `./.aitask-scripts/aitask_revert_analyze.sh --task-files 623` (24 files).
4. The doc states the baseline lifecycle table, including that it advances on
   "Proceed unchanged" — the fix for re-firing, and the easiest thing to omit.
5. The doc states the transaction rule as "decide → write both → commit".
6. The doc states that `git log -- <path>` cannot detect deletion and that existence
   is probed with `git cat-file -e`.
7. The three follow-ups exist with correct `depends:` edges (spawned follow-ups do
   not get deps automatically), and none contains deferred scope — in particular
   none touches `aitask_update.sh`'s existing field emission, `union_file_references`
   or `aitask_fold_mark.sh`.
8. No source file outside `aidocs/`, `aiplans/`, `CLAUDE.md` is modified —
   `git status --short` shows only those; the pre-existing unrelated
   minimonitor/review_loop edits on `main` stay untouched and unstaged.

## Step 9 (Post-Implementation)

Commit the doc + `CLAUDE.md` pointer as `documentation: … (t1538)`, commit the plan
via `./ait git`, merge to `main` (current-branch mode: no worktree to remove),
archive t1538.

## Risk

### Code-health risk: low
- Lands one new `aidocs/` document plus a one-line `CLAUDE.md` pointer; no code, no
  behavior change · severity: low · → mitigation: none needed
- Selective staging on a `main` working tree that already carries unrelated
  uncommitted edits, so a careless `git add -A` would capture foreign
  work · severity: low · → mitigation: inline post-phase commit_scope_check
- Reusing `file_references:` couples two meanings to one key; a reader that forgets
  the `issue_type` scope would misinterpret it on other task
  types · severity: low · → mitigation: inline post-phase accepted_costs_stated
- v1's follow-ups touch `aitask_update.sh` only **additively** (a new field), not by
  changing how an existing shared field is emitted — the change the earlier draft
  required and which carried repo-wide blast radius · severity: low · → mitigation: none — verification item 7 asserts no follow-up touches existing field emission, `union_file_references` or `aitask_fold_mark.sh`

### Goal-achievement risk: medium
- v1 covers **only** tasks seeded through 8c after their origin landed: all 77
  existing tasks and all 26 aggregate tasks are skipped, so the measured exposure
  that motivates the work is not addressed until a promotion
  lands · severity: medium · → mitigation: inline post-phase accepted_costs_stated
- The design's value rests on curation quality, which is entirely unexercised — no
  task has ever carried this field · severity: low · → mitigation: none — follow-up 2 owns it; the `CHANGED:` output names the file and culprit task, so a bad curation is visible rather than silent
- A silent-skip precondition can hide a broken implementation: if seeding never
  writes the fields, the feature is indistinguishable from working
  correctly · severity: medium · → mitigation: none — the aggregate MV sibling drives the whole path live (seed → change → prompt → dismiss), which is the only check that distinguishes "correctly quiet" from "never runs"
- The check measures **change, not behavior**: an item can go stale with an
  untouched file (a default changed elsewhere) and stay valid after a
  behavior-preserving refactor · severity: medium · → mitigation: inline post-phase accepted_costs_stated

### Planned mitigations
- timing: post-phase | name: commit_scope_check | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — foreign uncommitted edits on main | desc: Stage doc/plan/CLAUDE.md by explicit path and confirm no code paths entered the commit
- timing: post-phase | name: accepted_costs_stated | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health file_references overload + goal-achievement coverage and change-vs-behavior gaps | desc: Write the accepted costs down explicitly — issue_type-scoped semantics and ignored ranges, the 8c-only coverage limit skipping all 77 existing and 26 aggregate tasks, silent-skip by design, and change-is-not-behavior
- timing: post-phase | name: stage2_evidence_recorded | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — deferred work re-derived from scratch | desc: Record every deferred item with its measurement plus the promotion trigger, and why the over-built draft was cut

## Post-Review Changes

### Change Request 1 (2026-08-17 15:02) — follow-up tasks were missing
- **Requested by user:** blocking — the change set contained only the doc and the
  `CLAUDE.md` pointer; the plan's four follow-up tasks with dependency edges had
  not been created, so committing would archive a design with none of the queued
  work that makes it actionable.
- **Changes made:** created t1549 (check helper + `verification_baseline:` field),
  t1550 (Step-8c seeding, `depends: [1549]`), t1551 (procedure pre-check step,
  `depends: [1549, 1550]`) and t1552 (manual-verification sibling,
  `depends: [1551]`, `verifies: [1549, 1550, 1551]`, 8 seeded items). All anchored
  to 1538. Each carries the design's negative guards inline so a fresh context
  cannot re-derive the deferred scope. Added an "Implementation status" paragraph
  to the design doc naming the chain, so the design is traceable to its queued
  work.
- **Files affected:** `aitasks/t1549_*.md`, `aitasks/t1550_*.md`,
  `aitasks/t1551_*.md`, `aitasks/t1552_*.md`,
  `aidocs/framework/manual_verification_staleness.md`.

### Change Request 2 (2026-08-17 15:14) — UNKNOWN was self-contradictory
- **Requested by user:** blocking — the design said an unresolvable curated path
  emits `UNKNOWN` but does not drive the verdict, while claiming that row prevents
  silent under-coverage. A hand-edited `file_references:` entry would therefore
  report `FRESH` over a partly-uncheckable scope list. Also (non-blocking): t1549
  said only "add write support" for `verification_baseline:` without defining a
  setter, so t1550 would have had to invent one.
- **Changes made:** `UNKNOWN` now raises `ASK_STALE`, with `DISPLAY:`
  distinguishing the two causes (changed code → amend items; uncheckable path →
  repair `file_references:`). Added tests pinning that a bogus hand-edited path
  yields `ASK_STALE` and explicitly not `FRESH`/`SKIP`, plus a mixed valid+invalid
  case; tightened the negative control to "untouched **and all valid**". Pinned the
  setter as a cross-task contract —
  `aitask_update.sh --batch <id> --verification-baseline "<sha> @ <ts>"` — in the
  doc and t1549, with a parse/set/preserve round-trip test, and pointed t1550 at it.
  Added a live invalid-scope item to t1552.
- **Files affected:** `aidocs/framework/manual_verification_staleness.md`,
  `aitasks/t1549_*.md`, `aitasks/t1550_*.md`, `aitasks/t1551_*.md`,
  `aitasks/t1552_*.md`.

### Change Request 3 (2026-08-17 15:26) — scope repair fell outside the transaction
- **Requested by user:** blocking — routing `UNKNOWN` through "Amend" introduced a
  third mutation (`file_references:`) that the transaction contract did not cover,
  so a failure between the scope repair and the baseline advance could leave an
  invalid scope under an advanced baseline — permanently unreviewable.
- **Changes made:** the transaction contract now enumerates all three mutations
  (item text in the body, `file_references:` and `verification_baseline:` in
  frontmatter) and states the invariant that survives any decomposition: **the
  baseline may advance only after every other mutation has durably succeeded**, so
  every failure state is re-promptable and the mirror state is impossible. Added an
  injected-failure test between scope repair and baseline advance, an assertion that
  the forbidden state never occurs, and an ordering guard proving the advance is
  genuinely last.
- **Files affected:** `aidocs/framework/manual_verification_staleness.md`,
  `aitasks/t1551_*.md`.

### Acceptance-criterion update (from Change Request 3)
Verification item 5 above reads: *the doc states the transaction rule as "decide →
write both → commit"*. That wording described a two-mutation transaction and is
**superseded**. The criterion is now: the doc states the rule as **"decide → write
everything → advance the baseline last → commit"**, and states the invariant that
the baseline may advance only after every other mutation has durably succeeded.
Recorded here rather than applied silently, since it relaxes nothing but does
change the pinned string.

### Change Request 4 (2026-08-17 15:38) — scope repair must remove, not append
- **Requested by user:** blocking — t1551's only concrete combined-update example
  was `--file-ref … --verification-baseline …`, but `--file-ref` appends: the bogus
  reference would survive, so the next check still yields `UNKNOWN:`/`ASK_STALE`
  while the baseline had advanced. Following the documented example therefore
  produced the exact forbidden state Change Request 3 established.
- **Changes made:** verified in `aitask_update.sh` that `--file-ref` is
  append-with-exact-string-dedup and `--remove-file-ref` is exact-string removal,
  and that `process_file_references_operations` handles both sets in **one** pass
  (append first, then removal), so a combined invocation is a single atomic
  re-emit. The repair shape is now specified in both the doc and t1551 as
  `--remove-file-ref <bad> [--file-ref <replacement>] --verification-baseline …`,
  with the append-is-not-a-repair trap called out explicitly. Added a
  successful-repair test asserting the bogus entry is **gone** (not merely joined by
  a replacement), the valid entry survives, and a clean re-run returns `FRESH` with
  no `UNKNOWN:` line — without which the suite would pass an append-only
  implementation.
- **Files affected:** `aidocs/framework/manual_verification_staleness.md`,
  `aitasks/t1551_*.md`.

## Final Implementation Notes

- **Actual work done:** Landed the design as
  `aidocs/framework/manual_verification_staleness.md` (531 lines) plus a one-line
  `CLAUDE.md` pointer, committed as `documentation: … (t1538)`. Spawned the queued
  work as t1549 → t1550 → t1551 (strictly sequential) with t1552 as the
  manual-verification sibling (`verifies: [1549, 1550, 1551]`, 9 items), all
  anchored to 1538. No code changes, per the task's non-goal.
- **Deviations from plan:** Four review rounds changed the design's contracts after
  approval; each is logged above in Post-Review Changes, and one superseded a
  pinned acceptance-criterion string (also recorded above). The substantive
  deviations are: `UNKNOWN` now drives the verdict instead of being advisory; the
  amend transaction covers three mutations rather than two, under a
  "baseline advances last" invariant; and scope repair requires
  `--remove-file-ref` rather than `--file-ref` alone.
- **Issues encountered:** The design initially grew well past its justification —
  persistent baselines via topological git ancestry, first-pick curation, a `[]`
  sentinel, presence tracking in the shared `aitask_update.sh` writer, and fold
  semantics — before being cut back to a single precondition (both fields present
  or silently skip). That cut removed the shared-writer and fold changes entirely
  and halved the plan. The deferred analysis is preserved in the doc with its
  measurements so the deferral stays revisitable.
- **Key decisions:** Reuse `file_references:` rather than add a parallel field;
  procedure pre-check rather than a declared gate (the
  `MANUAL_VERIFICATION_REACHABLE_GATES` allowlist would silently strip one);
  existence probed with `git cat-file -e` rather than inferred from `git log`;
  seeding restricted to Step 8c so HEAD is the origin's landing point and no
  ancestry computation is needed.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_revert_analyze.sh:132,207 — commit lookup greps `git log --all`, which spans the `aitask-data` branch, so `--task-commits` / `--task-files` report task-metadata edits as part of a task's code change surface (verified: `--task-files 1223_4` returns `aitasks/t1223/t1223_5_*.md` and `t1223_6_*.md`); the sibling helper `aitask_change_surface.sh` deliberately excludes `aitasks/**` / `aiplans/**` via its `EXCLUDES`, so the two disagree about the same question`
- **Notes for related tasks:** `seed/profiles/fast.yaml` lacks the
  `plan_verification_required` / `plan_verification_stale_after_hours` keys that
  live `fast.yaml` sets. This is **not** a defect today — the consuming Jinja uses
  `| default(1)` / `| default(24)`, which match the live values exactly — but the
  drift means a future change to the live values would not reach a fresh install.
  Noted rather than filed.
