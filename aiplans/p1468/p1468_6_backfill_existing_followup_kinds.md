---
Task: t1468_6_backfill_existing_followup_kinds.md
Parent Task: aitasks/t1468_mark_followup_task_provenance_and_surface_on_board.md
Sibling Tasks: aitasks/t1468/t1468_7_*.md, aitasks/t1468/t1468_8_*.md
Archived Sibling Plans: aiplans/archived/p1468/p1468_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-13 22:35
---

# p1468_6 — Backfill `followup_kind` on existing follow-ups

## Context

t1468_1..t1468_5 registered `followup_kind:` and made every creation seam emit
it, but **forward-only marking leaves the existing backlog unmarked** — and the
backlog is where the pain is. This child retro-classifies the follow-ups already
on disk so the board glyphs, `ait ls --followup-kind` and the pick queue describe
the whole corpus rather than only tasks created since t1468_2 landed.

Precondition satisfied: t1468_1 (field + CLI) and t1468_3/_4/_5 (read surfaces)
are all archived, so results are immediately reviewable.

## Verification of this plan (2026-08-13, claudecode/opus5)

Re-measured against live source. **Four corrections; the original plan is not
safe to execute as written.** All counts below were derived at run time.

| # | Finding | Effect |
|---|---|---|
| 1 | 8 tasks match **both** `issue_type: manual_verification` and the risk-mitigation producer prose. Two (`t1477`, `t1508`) are **already** marked `followup_kind: risk_mitigation` by the live Step-8d seam. | The spec's rule order would assign `manual_verification` to the other 6, splitting one cohort by creation date. **Order corrected** (user-confirmed). |
| 2 | Rules 1 and 3 as written hit `t1468` and `t1468_6` — the spec tasks quote the marker strings in their own rule tables. | **Producer-anchored patterns** (user-confirmed). Also fixes a real gap: the `"before"` variant omits the words "follow-up", which the plan's pattern missed. |
| 3 | The old plan's verification step 7 asserts `t1246` appears in the residue. It no longer does — the file now carries a `## Upstream defect` heading (line 19) and classifies correctly. | **That check would fail correct work. Replaced.** |
| 4 | `aitask_update.sh`'s `has_update` is flag-presence, not value-comparison, so a re-run rewrites every file and bumps `updated_at`. | Backfill **skips already-marked tasks** itself. |

Also confirmed: `--batch <id> --followup-kind <kind>` needs no other flag, works
for child ids, validates + enforces the MV invariant *before* any write, and
**does not commit** without `--commit` — so the one-commit design holds.

**Live measurement (corrected rules):** 411 active tasks · 16 already marked ·
**168 classified** (carry_over 7, risk_mitigation 59, manual_verification 58,
upstream_defect 39, verification_failure 4, review_finding 1, qa_test_gap 0,
docs_gap 0) · 227 residue. The corpus grew 409→411 *during planning* — counts
must be derived at run time, never asserted against a constant.

---

## Run state: manifest + journal

168 independent `aitask_update.sh` writes are **not atomic**. A mid-run failure or
a concurrent task edit leaves a partial backfill sitting uncommitted, and because
the driver skips already-marked tasks, a naive retry would silently report fewer
writes and **conceal that the reviewed corpus was only partly applied**. Two
durable artifacts close that hole. They live in `.aitask-backfill/`, a new
git-ignored runtime dir following the existing `.aitask-explain/`,
`.aitask-gates/`, `.aitask-shadow/` convention (one added `.gitignore` line).

| file | written by | contents |
|---|---|---|
| `<run-id>/manifest.tsv` | dry run | `task_id · kind · rel_path · sha256_at_review` — one row per intended write, in a fixed order |
| `<run-id>/preimages/<task_id>.md` | **before** each write | byte copy of the task file as it was when classified |
| `<run-id>/journal.tsv` | write-ahead, two phases | `INTENT · task_id · rel_path · sha256_before` then `DONE · task_id · rel_path · sha256_after` |
| `<run-id>/state` | transitions | `REVIEWED → APPLYING → COMPLETE`, or `FAILED` / `ABANDONED` |

**The manifest pins membership AND order**, so the set applied is provably the
set reviewed — not "whatever classifies at apply time".

### Why the journal is not the source of truth

Journaling only *after* a successful write leaves a window: crash, disk-full, or
a failed append between the task file being rewritten and the row being recorded
produces a **changed but unjournaled** path — which `--resume` would read as
foreign drift and `--abandon` would not restore. Two things close it, and the
second is the load-bearing one:

1. **Write-ahead.** Per row, in order: copy the file to `preimages/`, append
   `INTENT`, then write, then append `DONE`. The preimage is the durable recovery
   material and it exists before the file is ever touched.
2. **Recovery reconciles against the corpus, not the journal.**
   `lib/atomic_write.sh:14` is explicit that the framework's atomic write gives
   *visibility*, not crash durability — **there is no fsync** — so even an
   `INTENT` row can be lost by a hard power cut. Correctness therefore cannot
   rest on the journal being complete. At `--resume` / `--abandon`, every manifest
   row is classified by **hashing the file**:

   | preimage | file hash | state | `--resume` | `--abandon` |
   |---|---|---|---|---|
   | absent | `== sha256_at_review` | **NOT_STARTED** | create preimage, apply | no-op (untouched) |
   | absent | anything else | **UNRECOVERABLE** | refuse, name the path | refuse, name the path |
   | present | `== preimage` | **STARTED_NOT_LANDED** | apply | no-op, drop preimage |
   | present | differs **only** by the expected `followup_kind: <kind>` + `updated_at:` | **LANDED** | skip, record `DONE` | restore preimage |
   | present | differs any other way | **FOREIGN_DRIFT** | refuse, name the path | refuse, name the path |

   The journal then serves as intent record and accelerator; the hashes decide.
   This is what makes the write-success/journal-failure window a resolvable state
   rather than a stuck one.

   **`NOT_STARTED` is a first-class state, not an error.** Without it the plan
   contradicts itself: `--limit 3` deliberately leaves 165 rows with no preimage,
   so treating "preimage missing" as unrecoverable would make the prescribed
   canary→resume path unable to ever reach `COMPLETE`. Refusal is reserved for
   the genuinely unsafe case — a file that *could* have been modified and that we
   have **no preimage to restore to**. A missing preimage on a file still
   byte-identical to what was classified is simply a row that has not been
   reached yet, and is indistinguishable from a fresh row at first apply.

### Restore is preimage-based, never `git checkout`

`--abandon` restores by atomically rewriting each affected path **from its
preimage** (`ait_atomic_write_text`), not `task_git checkout -- <path>`.
`git checkout -- <path>` restores from the index, discarding whatever is in the
worktree — so it silently destroys a pre-existing uncommitted edit on a selected
path, and its correctness quietly depends on that path having been clean. The
preimage is byte-exact, HEAD-independent, works in legacy mode, and cannot touch
anything outside the run.

### Lifecycle

1. **Dry run** (default) — classify, print the table + residue, write the
   manifest, `state=REVIEWED`, print the run-id.
2. **Review with the user.** This is the acceptance criterion.
3. **`--apply --run <id>`** — refuses unless `state=REVIEWED`.
   - **Baseline, with selected paths held to a stricter rule.**
     `task_git status --porcelain -- aitasks/` is partitioned against the
     manifest:
     - **A dirty *selected* path aborts the run — always, in every mode.**
       `--allow-dirty-baseline` does **not** relax this. Two independent reasons:
       the row's `sha256_at_review` no longer describes the bytes that were
       classified, so the reviewed decision is stale; and the preimage captured
       at apply time would bake a foreign edit into the run's own restore
       material.
     - A dirty **non-selected** task path aborts by default; `--allow-dirty-baseline`
       records it in the **exclusion set** and proceeds. The exclusion set is
       used for exactly one thing — subtracting those paths from the §6 delta
       set-equality check — and is never written to, restored, or committed.
   - **Global preflight, immediately before the first write:** re-hash every
     manifest row. Any mismatch, or any file that has gained a `followup_kind:`
     since review, is reported `DRIFTED:<id>` and the run **aborts with zero
     writes** — the reviewed set no longer matches disk, so re-review rather than
     write. This is the cheap fail-fast: nothing has been touched, so the outcome
     is "go re-review", not "recover a partial run".
   - **Per-row re-check, immediately before each preimage copy.** The global
     preflight hashes once; the loop then runs ~168 `aitask_update.sh`
     invocations, a **multi-minute** window during which a concurrent session can
     edit a row not yet reached. Without a per-row check that edit would be
     copied into the row's preimage and silently adopted as its baseline, even
     though it differs from the bytes that were classified. So: re-hash the row
     against its manifest `sha256_at_review` **immediately before** copying the
     preimage. On mismatch → `state=FAILED`, **stop at that row**, name it, and
     leave the run recoverable via `--resume` / `--abandon`. Unlike the global
     preflight this does *not* rewind — earlier rows legitimately landed and
     their preimages exist.

     This check is also what makes the state table above sound: a preimage is
     only ever captured from bytes matching `sha256_at_review`, so
     `preimage hash == sha256_at_review` is an invariant rather than an
     assumption.
   - Writes proceed in manifest order, each one write-ahead: re-check → preimage
     copy → `INTENT` → write → `DONE`. Any non-zero `aitask_update.sh` →
     `state=FAILED`, stop immediately, print the recovery contract below.
   - `--limit N` applies only the first N manifest rows. **This is how the canary
     runs** — same run, same journal, so nothing is double-counted.
4. **`--resume --run <id>`** — reconciles every manifest row by hash (table
   above), applies the `NOT_STARTED` and `STARTED_NOT_LANDED` rows (subject to
   the same per-row re-check), skips `LANDED`, and refuses on `FOREIGN_DRIFT` or
   `UNRECOVERABLE`. `state=COMPLETE` when every manifest row reconciles as
   `LANDED`. `--limit` is honoured here too, so the canary is just the first
   `--resume` of the same run.
5. **`--abandon --run <id>`** — restores from preimage, **only** the `LANDED`
   rows (never a blanket restore); `NOT_STARTED` / `STARTED_NOT_LANDED` need
   nothing. Then `state=ABANDONED`. Refuses on `FOREIGN_DRIFT` or
   `UNRECOVERABLE`, so it can never discard someone else's concurrent edit.

**A second `--apply` against a `FAILED` or `APPLYING` run is refused** until it is
reconciled with `--resume` or `--abandon`. That refusal is the thing that stops a
retry from hiding a partial application.

## Pre-phase (risk mitigations)

**`negctrl_classifier_rules`.** Write the classifier unit test in its final form
**first** and confirm it goes RED against the spec's original rule order: a
fixture matching both the risk-mitigation producer sentence and
`issue_type: manual_verification` must classify `risk_mitigation`. Record the
failing test id and message in Final Implementation Notes. A test written after
the corrected order would pass vacuously and would not catch a silent revert to
the written spec.

**`frontmatter_delta_canary`.** Run `--apply --run <id> --limit 3` (3
representative rows: one carry_over, one risk_mitigation-over-MV, one
upstream_defect) and assert the delta contract of §"Delta assertion" below over
those three journaled paths. The backfill drives `aitask_update.sh`, which
rebuilds frontmatter from scratch across ~34 positional fields; a latent
round-trip defect in *any* of them would be amplified across 168 files in one
run. t1468_1 proved the round trip for `followup_kind` only. Because the canary
is `--limit` on the same run, the subsequent full `--resume` covers the remaining
165 and the accounting stays exact.

## Implementation

### 1. Classifier — `.aitask-scripts/lib/followup_backfill_classify.py`

A **pure** classifier, kept separate from the driver so rule order is unit-testable
without touching a task file. Reuses `lib/task_yaml.py::parse_frontmatter` — the
canonical, board-shared parser — for every frontmatter-derived rule. Body rules
are line-scoped regexes.

Reads a list of task paths, emits TSV: `id · matched_rule · assigned_kind`, plus
an `origin_annotation` column (see §4). No writes, no git, no subprocess.

**Frontmatter rules MUST be scoped to the leading `---` block.** A naive
whole-file grep for `^issue_type: manual_verification` false-positives on
`t583_9_meta_dogfood_aggregate_verification.md`, which quotes an example
frontmatter block in its body; its real type is `test`. `parse_frontmatter`
handles this by construction — that is why it is used rather than grep.

### 2. Rules — corrected order, producer-anchored patterns

First match wins:

| order | kind | detection (producer-anchored) |
|---|---|---|
| 1 | `carry_over` | body: `Carry-over of deferred manual-verification items from t<id>` |
| 2 | `risk_mitigation` | body: `Risk-mitigation ("before"\|"after") [follow-up] for t<id>` |
| 3 | `upstream_defect` | body: `^## Upstream defect` **or** `Spawned from t<id> during Step 8b review` |
| 4 | `verification_failure` | body: `^## Failed verification item from t` |
| 5 | `manual_verification` | frontmatter `issue_type: manual_verification` |
| 6 | `review_finding` | frontmatter `labels` contains exact token `review` |
| 7 | `qa_test_gap` | `labels` contains exact token `qa` |
| 8 | `docs_gap` | filename matches `docs_gaps_since_` |

**Why prose beats `issue_type` (the correction).** Body prose records *who
spawned the task* — provenance. `issue_type` records *what kind of work it is*.
A risk-mitigation follow-up that happens to be a manual-verification checklist is
a risk mitigation whose work is verification; the live Step-8d seam agrees
(`t1477`, `t1508`). `manual_verification` is therefore the **fallback** for
MV-typed tasks with no more specific provenance. `carry_over` stays first — it is
a strict subset of MV and its producer is `aitask_archive.sh:601`.

This keeps the MV cross-field invariant satisfied **by construction**: rule 5 is
the only producer of `followup_kind: manual_verification`, and it fires only when
`issue_type` already equals `manual_verification`.

**Anchor on the full producer sentence, not the prefix.** `aitask_archive.sh:601`
emits `… items from t<id>. Re-pick this task …`; `risk-mitigation-followup.md:409,524`
emit `Risk-mitigation ("before") for t<id>,` and `Risk-mitigation ("after")
follow-up for t<id>,`. Requiring the `from t<id>` / `for t<id>` tail drops both
self-referential spec-table quotes and admits the `"before"` variant. Verified:
carry_over 7 (the expected count), rule 2 catches `t1192`'s older
`("after") for t1186` form.

**Disjointness of rules 2–8 is asserted, not assumed** — measured empty today.
Two matches on one task is a rule bug and is reported as a `CONFLICT` row, never
silently resolved by ordering. Rules 1 and 5 are *expected* to co-occur (7 tasks)
and are excluded from the conflict check with a comment.

**Rules 6–8 stay in despite 1/0/0 matches.** Their producers now self-mark
(`aitask-review/SKILL.md.j2:190` emits `followup_kind: review_finding` at all
three creation sites), so only the legacy `t804_planning_md_skill_authoring_review.md`
remains. The zeros for `qa_test_gap`/`docs_gap` are **asserted explicitly** — an
unexamined zero is not evidence.

### 3. Driver — `.aitask-scripts/aitask_followup_backfill.sh`

Modelled on `aitask_backfill_pid_anchor.sh` (the closest precedent: one-shot,
`find -L` enumeration, self-test before mutating, single batch commit) and on
`aitask_fold_mark.sh:325-361` for the `aitask_update.sh --batch … --silent` loop
discipline.

- `#!/usr/bin/env bash`, `set -euo pipefail`; sources `lib/terminal_compat.sh`
  **before** `lib/followup_kinds_sh.sh` (the latter calls `die` but does not
  source it).
- **Dry-run by default**; `--apply` writes. `--scope active|all`, default
  `active` (user-confirmed: archived tasks are never picked or filtered, so
  marking them doubles blast radius for no benefit; the flag ships anyway).
- Enumeration: `find -L` over `$TASK_DIR`, pruning `$ARCHIVED_DIR`. **`aitasks/`
  is a symlink to `.aitask-data/aitasks` — `-L` is mandatory.** Do *not* drive
  off `ait ls`: it defaults to `--status Ready` and hides children.
- **Skips tasks that already carry `followup_kind:`** and reports them as a
  separate `already-marked` count. Without this, a re-run churns `updated_at` on
  every file.
- Writes: `aitask_update.sh --batch <id> --followup-kind <kind> --silent`, **no
  `--commit`** — then one `./ait git` commit at the end.
- All git goes through **`task_git`**, never a hardcoded `.aitask-data` path:
  `_ait_detect_data_worktree` falls back to `.` in legacy mode
  (`lib/task_utils.sh:35-42`), and a hardcoded path would break there.
- Reports **MV cross-field violations as residue rather than writing them**
  (t1468_1 makes the pair unwritable through the CLI, so a pre-existing violation
  must surface, not fail mid-run). Zero today, by construction of rule 5.

### 4. Residue is a first-class output — and honestly reported

227 tasks match no rule. The bulk are genuine new work, but **the residue is
listed in full**, not sampled: the acceptance criterion is "every follow-up is
either classified or listed as reviewed residue".

I tested a `## Origin`-heading heuristic as a triage filter and **rejected it**:
its recall over the 167 known follow-ups is only **59%** (98 with / 69 without),
so absence of `## Origin` is not evidence of "not a follow-up" and using it as a
filter would silently hide real follow-ups. It ships as an **annotation column
with its measured recall printed in the report header**, so nobody mistakes it
for a gate.

### 5. Helper whitelist

Register the new script across the five touchpoints via the existing helper —
do not hand-edit them:

```bash
./.aitask-scripts/aitask_audit_wrappers.sh apply-helper-whitelist aitask_followup_backfill.sh
```

Precedent: `aitask_backfill_pid_anchor.sh` is present exactly once in all five.
**No `ait` dispatcher subcommand** — same precedent, invoked by full path.

### 6. Delta assertion — baseline, aggregate, and scoped

Run **after** `state=COMPLETE` and **before** commit 2. Three separate assertions,
because `aitasks/` and `aiplans/` share one data worktree and only the first is
subject to the two-line rule.

1. **Task files — set equality, not count equality.**
   `changed := task_git status --porcelain -- aitasks/` (paths), minus the
   baseline **exclusion set** (dirty *non-selected* paths recorded at preflight;
   a dirty selected path can never reach here, it aborts the run). Assert
   `changed == rows reconciled as landed` **as sets**. Set equality is what makes
   the canary safe: its 3 rows and the resumed 165 belong to one run, so there is
   no canary-vs-full-run count to diverge. It also catches an *extra* file the
   script never reported, which a count comparison can mask. Deriving the
   expected side from **hash reconciliation** rather than from journal rows keeps
   the assertion honest even if a `DONE` append was lost.
2. **Per-file shape.** For each changed task file, the diff adds exactly one
   `followup_kind:` line and modifies exactly one `updated_at:` line — no other
   key added, removed, reordered or reformatted.
3. **Plan file, separately.** The only changed path under `aiplans/` is this
   plan file; it is **exempt** from rule 2 (it carries the classification table
   in Final Implementation Notes). Assert it changed, that it contains the table,
   and that no other `aiplans/` path changed.

A failure in any of the three aborts before the commit.

### 7. Two commits, path-allowlisted

The original plan demanded a globally clean tree. **Relaxed (user-confirmed):**
the main worktree carries 5 files from a concurrent session (codebrowser/board
startup-focus work). Those files live in the main worktree and can never enter an
`./ait git` task-data commit, so commit 2's revertibility is unaffected. Stage
each commit with an **explicit path allowlist**:

1. `git commit -o -- .aitask-scripts/aitask_followup_backfill.sh
   .aitask-scripts/lib/followup_backfill_classify.py .gitignore tests/…
   <5 whitelist files>` → `chore: Add followup_kind backfill script (t1468_6)`
2. `./ait git` commit over task data only — the 168 field writes **plus** the
   reviewed classification table written into this plan's Final Implementation
   Notes (already on the data branch, the framework's durable record).

Note the ordering constraint this creates: the classification table must be
written into the plan file **before** commit 2 and **after** the apply, which is
exactly where assertion 3 above sits.

A mis-classification is then a revert of commit 2 alone.

## Verification

1. `negctrl_classifier_rules` RED before implementation (record id + message),
   GREEN after, assertion byte-unchanged.
2. Dry-run table reviewed **with the user before any write**. This is the
   acceptance criterion, not a courtesy.
3. Every count derived at run time; **no baked-in total** anywhere in script or
   tests (the corpus moved 409→411 during planning alone).
4. Rule precedence proven by unit test: carry_over beats manual_verification;
   **risk_mitigation beats manual_verification** (the corrected edge — fixture
   modelled on `t1477`).
5. Frontmatter scoping proven: a fixture with an example `---` block in its body
   (the `t583_9` shape) is **not** classified from it.
6. Self-reference proven excluded: fixtures quoting the bare marker strings in a
   markdown table (the `t1468`/`t1468_6` shape) classify as residue.
7. `t804_planning_md_skill_authoring_review.md` → `review_finding`.
8. `qa_test_gap` and `docs_gap` counts asserted zero explicitly.
9. Disjointness check fires a `CONFLICT` row (not a silent first-match) when two
   of rules 2–8 hit one task; proven with a fixture.
10. Residue listed in full with the `## Origin` recall figure disclosed in the
    header. **(Replaces the stale "confirm t1246 appears in residue" check —
    t1246 now carries `## Upstream defect` and classifies correctly.)**
11. **Manifest/journal contract, proven by fault injection through the documented
    seams** (fixture corpus, not the real one):
    - drifted file → preflight aborts with **zero** writes;
    - **a dirty *selected* path aborts even under `--allow-dirty-baseline`**; a
      dirty *non-selected* path is excluded and the delta check still passes;
    - injected failure mid-run → `state=FAILED`, a second `--apply` is
      **refused**;
    - **the write-success/journal-failure window, injected exactly:** force the
      `DONE` append to fail after `aitask_update.sh` succeeded, then assert
      `--resume` reconciles that row as *landed* (not drift) and does not
      re-write it, and that `--abandon` *does* restore it. Repeat with the
      `INTENT` append forced to fail, covering the no-fsync case where the
      journal has no record at all;
    - **the prescribed canary→resume path reaches `COMPLETE`**: `--limit 3` then
      `--resume` classifies the 165 preimage-less rows as `NOT_STARTED` (not
      `UNRECOVERABLE`) and applies them. This is the non-vacuity check on the
      state table — it is the exact path the plan requires, and an earlier draft
      of this design deadlocked on it;
    - **drift introduced after the global preflight but before a later row**
      (edit row N while row N-1 is being written): the run stops **at row N**,
      rows `< N` are `LANDED` with valid preimages, the drifted row's preimage is
      never created, and its foreign bytes are preserved. `--abandon` then
      restores exactly rows `< N`;
    - `--resume` applies exactly the not-landed remainder;
    - `--abandon` restores byte-exactly from preimage — including for a row whose
      `DONE` was never journaled — and refuses on a foreign-drifted or
      preimage-missing row;
    - **negative control:** a task edited by a "concurrent session" between
      review and recovery is refused by both `--resume` and `--abandon`, and its
      edit survives untouched.
12. `frontmatter_delta_canary` (`--limit 3`), then the three delta assertions of
    §6 over the completed run; spot-check ~5 tasks per category on disk after.
13. **Round-trip safety on real data:** pick a backfilled task, run an unrelated
    `ait update --status`, confirm `followup_kind` survives.
14. `ait ls --followup-kind risk_mitigation` returns a plausible count; board
    shows the glyphs.
15. `shellcheck .aitask-scripts/aitask_followup_backfill.sh`;
    `bash tests/run_all_python_tests.sh` — read the **last** line
    (`set -o pipefail` if piping).

## Risk

### Code-health risk: medium

- The backfill drives `aitask_update.sh` across 168 files, and that script
  rebuilds frontmatter from scratch over ~34 positional fields — a latent
  round-trip defect in **any** of them would be amplified corpus-wide in one run,
  silently · severity: medium (residual — addressed by inline pre-phase
  `frontmatter_delta_canary` and the §6 delta assertions) · → mitigation: inline
  pre-phase frontmatter_delta_canary
- The manifest/journal/state machine is real added machinery (preflight, resume,
  abandon, refusal) for a one-shot script, and it is itself a source of bugs ·
  severity: medium (residual — addressed by inline post-phase
  `recovery_contract_fault_injection`) · → mitigation: inline post-phase
  recovery_contract_fault_injection
- 168 task files change `updated_at`, adding noise to any subsequent
  recently-modified query or sync · severity: low · → mitigation: none (intended
  and bounded; the skip-already-marked rule prevents repeat churn)
- Five whitelist touchpoints, three of them seed files shipped into user
  projects, plus one `.gitignore` line · severity: low · → mitigation: none
  (applied by the existing `aitask_audit_wrappers.sh` helper, not hand-edited)

### Goal-achievement risk: medium

- Classification is heuristic over prose written by templates that have changed
  shape over time (the `"before"` variant already diverges from the `"after"`
  one); an unrecognised older variant lands silently in a 227-task residue nobody
  reads line by line · severity: medium · → mitigation: none (covered by
  verification 2 and 10 — the residue is listed in full and reviewed before any
  write, and the `## Origin` triage heuristic was measured at 59% recall and
  deliberately **rejected** as a filter)
- The corrected rule order overrides an order the task file and parent plan state
  explicitly; if a later reader restores the written spec, 8 tasks silently flip
  kind · severity: medium (residual — addressed by inline pre-phase
  `negctrl_classifier_rules`) · → mitigation: inline pre-phase
  negctrl_classifier_rules
- The corpus is live and grew during planning, and the apply loop is a
  multi-minute window, so a concurrent session can edit a row **after** the global
  preflight and **before** that row is reached — adopting foreign bytes as the
  row's baseline · severity: medium (residual — addressed by the per-row re-check
  immediately before each preimage copy, which stops the run and leaves it
  recoverable) · → mitigation: inline post-phase recovery_contract_fault_injection
- The framework's atomic write offers visibility, not crash durability
  (`lib/atomic_write.sh:14` — no fsync), so a hard power cut can lose a journal
  append and leave a written-but-unrecorded task file · severity: medium
  (residual — addressed by hash reconciliation against stored preimages, which
  makes recovery independent of journal completeness) · → mitigation: inline
  post-phase recovery_contract_fault_injection

### Planned mitigations
- timing: pre-phase | name: negctrl_classifier_rules | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: silent reversion to the spec's rule order flipping 8 tasks | desc: write the rule-order unit test in final form and confirm RED against the original spec order before implementing the corrected one
- timing: pre-phase | name: frontmatter_delta_canary | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: corpus-wide amplification of a latent aitask_update.sh round-trip defect | desc: apply the first 3 manifest rows via --limit and assert the scoped delta contract before resuming the remaining writes
- timing: post-phase | name: recovery_contract_fault_injection | type: test | priority: high | effort: medium | inline_risk: low | added_complexity: medium | addresses: a partial apply being concealed by a retry, an unjournaled-but-written path stranding recovery, mid-run drift adopted as a row baseline, and the recovery machinery itself being wrong | desc: drive every state-table row on a fixture corpus — canary-then-resume reaching COMPLETE, drift before the first write and drift after the global preflight but before a later row, dirty selected paths, mid-run failure, the write-success/journal-failure window in both INTENT and DONE positions — asserting zero-write abort, stop-at-the-drifted-row with earlier rows recoverable, refusal of a second apply, exact not-landed remainder on resume, byte-exact preimage restore, and refusal on foreign drift

## Notes for sibling tasks

- **Rule order is prose-provenance-first**, deviating from the parent plan and
  task file: `carry_over → risk_mitigation → upstream_defect →
  verification_failure → manual_verification → …`. The parent task file and
  `aiplans/p1468_*.md` still state the old order and should be corrected when the
  parent is closed.
- `followup_kind: manual_verification` is only ever produced by the `issue_type`
  rule, so the MV cross-field invariant holds by construction, not by a check.
- `aitasks/` **and** `aiplans/` are symlinks into the one `.aitask-data`
  worktree — corpus scans need `find -L`, and any `task_git status` assertion
  must be path-scoped or it will mix plan edits into task-file accounting.
- `aitask_update.sh --batch` does **not** commit without `--commit`, and its
  `has_update` is flag-presence not value-comparison (re-running churns
  `updated_at`).
- Bulk writers over the corpus should reuse the manifest/preimage/journal shape
  here rather than re-deriving intent at apply time — it is what makes "the set
  applied is the set reviewed" checkable. Two rules travel with it: **recover by
  reconciling hashes against stored preimages, not by trusting the journal**
  (`lib/atomic_write.sh` does no fsync, so any append can be lost), and **restore
  from preimage, never `git checkout -- <path>`**, which discards uncommitted
  worktree edits and is only accidentally correct on clean paths.
- This is the last child. When it lands, re-run the parent's end-to-end
  verification list in `aiplans/p1468_*.md` before archiving the parent.
