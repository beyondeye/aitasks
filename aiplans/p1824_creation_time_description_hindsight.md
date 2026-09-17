---
Task: t1824_creation_time_description_hindsight.md
Base branch: main
Output branch: main
---

# t1824 — Bound hindsight bias in t1814's `task_declared` precision

## Context

t1814 measured that promoted task-description overlaps grade CONFLICT with
precision ≥ the plan pre-implementation reference (0.4387 vs 0.4036 unordered,
0.4333 desc-vs-plan, threshold 10, cohort `7b0461e726532b5c|400`), and
recommended lifting PINNED 6 to parity **after** this follow-up bounds hindsight
bias: those numbers read the CURRENT archived task files, and a description
edited during/after the work would look more precise than at admission.

This is a **measurement task**: no shipped code changes. The deliverable is a
creation-time vs current table, a Q1 verdict, and a note to t1688_2 (Ready).

### Exploration findings (read-only)

- t1814's frozen snapshot still exists, manifest verifies:
  `SNAP0=/tmp/claude-1000/-home-ddt-Work-aitasks/c384901e-…/scratchpad/snapshot`
  (+ `frozen_sweep.py`, and `measure/*.txt` with the published outputs). It is in
  another session's `/tmp` scratchpad, so it gets copied first.
- Recovery in ONE git pass (1.5s) on the data branch:
  `git -C .aitask-data log --reverse --no-renames --diff-filter=A --name-only --format='C %H %s' -- aitasks/`,
  keyed by task id (`(?:^|/)t(\d+(?:_\d+)?)_[^/]*\.md$`), first occurrence wins.
  Keying by id (not path) handles renames and the later `archived/` move without
  `--follow`'s per-file heuristic.
- Of the snapshot's 457 archived task files: 454 recoverable; 3 first appear in a
  `Migrate task data from main branch` commit (creation predates the data
  branch → excluded); 1 was renamed after creation (kept, keyed by id).
- After the sweep's own framework cut (`cut_task_framework_sections`), **143/454**
  creation bodies differ from current (median +1686 chars; added headings include
  `Verification Checklist`, `Coordination (from tN)`, `Key Files to Modify`), so
  the comparison has real signal. 311 are identical.
- 21 first-add commits are `Start work on tN` commits — a new file riding
  another session's commit (shared-index leakage); its first committed version
  may already include pre-commit edits.

## Pre-phase

0. `SP=<this session's scratchpad>`. `cp -a $SNAP0 $SP/snapshot` and copy
   t1814's `measure/` outputs; `sha256sum -c` the manifest in the copy.
1. Write the **final** measurement tooling now, before any recovery, so what gets
   validated is exactly what later measures both roots:
   - `$SP/frozen_io.py` — the one place that loads `batch_map.txt` /
     `corpus.json` **from the fixed snapshot copy** (never from the root being
     swept) and patches `_BATCH_MAP`, `_TRACKED_SETS`, `_DATA_TREE` (logic
     copied from t1814's `frozen_sweep.py`).
   - `$SP/sweep_root.py <root> <sweep args…>` — imports `frozen_io`, asserts the
     imported module is `<repo>/.aitask-scripts/lib`, calls
     `main(["sweep", "--root", <root>, …])`.
   - `$SP/cohort.py` (Step 2) imports the same `frozen_io`.
2. Validate the root-aware wrapper against the **untouched** snapshot copy,
   `root=$SP/snapshot`: require byte-identity with t1814's published
   `measure/tvp_pre.txt`, `measure/task_pre_common.txt` and
   `measure/plan_pre_common.txt` (the three sources Step 3 uses, same args).
   Also run `cohort.py` on the untouched snapshot and require its cohort digest
   to equal `7b0461e726532b5c|400`. Any mismatch → stop and report; nothing is
   measured through an unvalidated wrapper or on moved code.

## Step 1 — Recover creation-time bodies (`$SP/recover.py`)

- Parse the one `git log` pass above into `{id: (commit, subject, path)}`.
- For every `aitasks/archived/**/t<id>_*.md` in the snapshot:
  - `excluded:migration` when the subject contains `Migrate task data`;
    `excluded:not_found` when the id never appears.
  - else `git show <commit>:<path>` → body.
- Write `$SP/roots/creation/` = copy of the snapshot with each recoverable task
  file's content replaced **at the same snapshot path** (so
  `_archived_task_paths` maps unchanged). Excluded task files are removed from
  this root.
- Write `$SP/roots/current/` = the snapshot with the same excluded files removed.
- Emit `$SP/recovery.tsv` (id, commit, subject, first path, identical-after-cut
  y/n, rider y/n where rider = the subject does not name `t<id>`) and counts.

## Step 2 — One cohort for both roots (`$SP/cohort.py`)

The shipped CLI computes its `common` cohort internally, so the two roots would
diverge wherever a creation body does not resolve. Fix membership explicitly:

- With the frozen batch map + corpus patched exactly as `frozen_sweep.py` does,
  call `parallel_admission_collect.sweep_population(root, plan_scope=
  "pre-implementation", source=s, batch_lines=…, corpus=…)` for
  `s in plan, task, task-keyfiles` on each root; `C_root = _common_refs([...])`.
- `COHORT = C_current ∩ C_creation`. Dropout accounting from the t1814 400:
  `excluded:migration`, `excluded:not_found`, `unresolved_at_creation`
  (`C_current − C_creation`), `resolved_only_at_creation` (`C_creation −
  C_current`, expected 0; reported), = `|COHORT|`. Record the dropped ids.
- Prune both roots to `COHORT` (remove task AND plan files outside it). Then the
  CLI's own intersection equals `COHORT` on both, with no new code path.

## Step 3 — Measure with the shipped CLI (frozen inputs)

Using the pre-phase-validated `sweep_root.py`, for
`R in current, creation`, thresholds `8,10,20`, all `--plan-scope pre-implementation`:

- `--source plan --population common` (the Q1 reference)
- `--source task --population common`
- `--source task-vs-plan` (gives `SWEEP` whole-body and `SWEEP_KF` rows)

Checks before any table is written:
- All six outputs print the same `SWEEP_COHORT:` digest and `n = |COHORT|`.
- The two `plan` outputs are byte-identical across roots (control: only task
  bodies differ).
- Negative control: `task` output for `current` ≠ `creation` (otherwise the
  replacement did not take effect). Verify the manifest in `$SP/snapshot` again
  at the end.

## Step 4 — Verdict, conditional bracket, records

- Table: precision / recall / hard-stopped / downgraded / CONFLICT count per
  root × source × threshold, plus the recovery and cohort accounting.
- **Selection effect, separated from hindsight.** Dropping tasks is not
  neutral: whether a creation body resolves depends on its content, so precision
  can move either way. Measure it instead of assuming it, all on CURRENT bodies:
  the t1814 published rows (400 cohort) vs the `current` root on `COHORT`, for
  `plan`, `task` and `task-vs-plan` at 8/10/20. The difference is the selection
  effect; `current@COHORT − creation@COHORT` is the hindsight effect. Also
  characterize the dropped subset: count, share of the 400's real colliding
  pairs that involve ≥1 dropped task, and those tasks' `issue_type` mix vs the
  cohort's.
- **Q1 rule (same as t1814), stated cohort-conditionally:** on `COHORT`,
  creation-time promoted `task` precision ≥ `plan` pre-implementation precision
  at threshold 10, and likewise for `task-vs-plan` whole body; report 8 and 20
  alongside. The verdict is written as "holds / fails **on the N-task cohort of
  tasks whose creation description resolves**", never as t1814's 400-task
  conclusion surviving unqualified. If the selection effect alone moves the
  plan-vs-task gap by as much as the margin, say the verdict is not
  distinguishable from selection.
- Write the table, verdict and accounting into this plan's Final Implementation
  Notes, then (after the post-phase) send a note to t1688_2 either way (survives
  or not; t1814's recommendation said to wait for this), stating that the
  claim-time bracket is a separate follow-up:
  `./ait note 1688_2 --from 1824 --file - <<'EOF' … EOF`.

### Post-phase (risk mitigations)

1. [rider_sensitivity] Classify each cohort task's first-add commit by
   **structure**, not by whether the subject names the id (from the same
   `git log` pass, plus `git show --name-status` of that commit):
   - `create_single` — the commit adds exactly one task-id file (this one);
   - `multi_task_add` — the commit adds task files for ≥2 distinct ids;
   - `start_work` — subject begins `ait: Start work on`;
   - `sync_autocommit` — subject begins `ait: Auto-commit task changes`;
   - `other` — anything else (counted and listed).
   Groups can overlap (a start-work commit that also adds several tasks); report
   the overlap. For each non-`create_single` group, and for their union, remove
   those tasks from both pruned roots, re-derive `COHORT` per Step 2, and re-run
   the threshold-10 `plan` / `task --population common` and `task-vs-plan`
   sweeps with the same digest-equality checks. Report per group: size, new
   cohort size, precisions, and whether the Q1 verdict changes. State the limit
   explicitly: this is a **structural heuristic** for contamination. A
   `create_single` commit can still carry pre-commit edits, which no commit
   metadata reveals. Include this in the table and the t1688_2 note.

## Verification

- Pre-phase: the final `sweep_root.py` on the untouched snapshot is byte-identical
  to t1814's `tvp_pre` / `task_pre_common` / `plan_pre_common`, and `cohort.py`
  reproduces `7b0461e726532b5c|400`.
- Step 3 digest equality, plan byte-identity, and the negative control.
- No repo code changes: `git status` shows no new modifications from this task
  (other sessions' dirty files are pre-existing and untouched).

## Step 9 (Post-Implementation)

No code commit. Commit the plan with `aitask_task_commit.sh`, then archive per
task-workflow Step 9.

## Risk

### Code-health risk: low
None identified. (Scratch scripts only; git access on the data branch is read-only.)

### Goal-achievement risk: medium
- The cohort conditions on the creation body resolving to paths. Resolution correlates with description content, so dropping the non-resolving tasks can move precision and recall either way · severity: medium · → mitigation: none (Step 4 measures the selection effect on current bodies, separately from hindsight; the verdict is stated as conditional on the cohort)
- The wrapper that measures both roots is new code; a wrong root, corpus or batch-map binding could make the two roots agree while measuring the wrong population · severity: low (residual — addressed by pre-phase validation of the final wrapper against t1814's published outputs) · → mitigation: none
- Creation-time is stricter than admission-time; legitimate pre-claim edits (coordination sections, checklists) are admission-visible, so creation time is only the strict bound · severity: low · → mitigation: claim_time_bracket
- A first committed version may already include edits (rider commits, uncommitted drafts), which understates the hindsight effect · severity: low (residual — addressed by inline post-phase rider_sensitivity) · → mitigation: inline post-phase rider_sensitivity

### Planned mitigations
- timing: post-phase | name: rider_sensitivity | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — first committed version may already include edits | desc: classify first-add commits structurally (single create / multi-task add / start-work / sync autocommit / other), re-run threshold-10 sweeps excluding each suspect group, report whether Q1 changes, qualified as a heuristic
- timing: after | name: claim_time_bracket | type: enhancement | priority: low | effort: medium | inline_risk: low | added_complexity: medium | addresses: goal-achievement — creation time is stricter than admission time | desc: measure the task body as of just before its own `Start work on t<id>` commit as an admission-time bracket between t1824's creation-time and current numbers

## Implementation progress (2026-09-17)

All steps done: pre-phase, Steps 1–4 and post-phase `rider_sensitivity`. Every
measurement ran on t1814's frozen snapshot, copied into this session's
scratchpad; `MANIFEST.sha256` verified before and after.

### Pre-phase validation

The final root-aware wrapper (`sweep_root.py` over `frozen_io.py`) run on the
untouched snapshot produced output **byte-identical** to t1814's published
`tvp_pre`, `task_pre_common` and `plan_pre_common`. `cohort.py` reproduced
`7b0461e726532b5c|400`.

### Recovery and cohort accounting

- 457 archived task files in the snapshot. 454 were recovered from their first
  data-branch add (one `git log --reverse --no-renames --diff-filter=A` pass,
  keyed by task id); 3 were excluded because they were first added in a
  `Migrate task data from main branch` commit.
- After the framework cut, 311 creation bodies are identical to the current
  version and 143 differ. Within the final cohort: 297 identical, 96 differ.
- From t1814's 400: −1 migration (`t219`) = 399 resolvable on current bodies.
  Then −6 whose creation description does not resolve (`1657_7`, `369_1`,
  `369_2`, `369_3`, `417_9`, `635_36`), and +0 that resolve only at creation.
  **COHORT = `e845e8423e8130f9|393`.**
- Dropped subset (7): 4 feature (`369_1`–`369_3`, `417_9`), 1
  manual_verification (`1657_7`), 1 refactor (`219`), 1 chore (`635_36`), vs
  the cohort's feature 35.9% / bug 35.4% and no bugs dropped. So the dropped
  tasks are feature-heavy, but they touch only **74 of the 400
  cohort's 6360 real colliding pairs (1.16%)**.
- Controls: all six Step 3 outputs print `e845e8423e8130f9|393`. The `plan`
  outputs are byte-identical across roots. The `task` outputs differ across
  roots (negative control).

### Measurement (pre-implementation plan scope, frozen inputs)

Columns: CONFLICT precision · flagged recall · hard-stopped · downgraded · CONFLICT verdicts.

**Unordered pairs, `--population common`, COHORT 393 (77028 pairs, 6286 colliding):**

| source | th | precision | recall | hard-stop | downgr. | CONFLICT |
|---|---|---|---|---|---|---|
| plan (reference) | 8 | 0.3814 | 0.8540 | 0.2475 | 0.6064 | 4080 |
| plan (reference) | 10 | **0.4068** | 0.8540 | 0.2972 | 0.5568 | 4592 |
| plan (reference) | 20 | 0.2019 | 0.8540 | 0.6737 | 0.1802 | 20974 |
| task, current | 8 | 0.4285 | 0.4878 | 0.0872 | 0.4006 | 1279 |
| task, current | 10 | 0.4461 | 0.4878 | 0.1087 | 0.3791 | 1531 |
| task, current | 20 | 0.2779 | 0.4878 | 0.2358 | 0.2520 | 5332 |
| task, creation | 8 | 0.4393 | 0.4803 | 0.0853 | 0.3950 | 1220 |
| task, creation | 10 | **0.4562** | 0.4803 | 0.1053 | 0.3750 | 1451 |
| task, creation | 20 | 0.2776 | 0.4803 | 0.2310 | 0.2493 | 5231 |

**Ordered pairs, `task-vs-plan`, COHORT 393 (154056 pairs, 12572 colliding):**

| candidate | th | precision | recall | hard-stop | downgr. | CONFLICT |
|---|---|---|---|---|---|---|
| whole body, current | 8 | 0.4107 | 0.6168 | 0.1217 | 0.4951 | 3725 |
| whole body, current | 10 | 0.4393 | 0.6168 | 0.1549 | 0.4620 | 4432 |
| whole body, current | 20 | 0.2331 | 0.6168 | 0.3793 | 0.2375 | 20460 |
| whole body, creation | 8 | 0.4176 | 0.6078 | 0.1189 | 0.4889 | 3580 |
| whole body, creation | 10 | **0.4467** | 0.6078 | 0.1514 | 0.4564 | 4260 |
| whole body, creation | 20 | 0.2327 | 0.6078 | 0.3751 | 0.2327 | 20269 |
| key-files, current | 10 | 0.4743 | 0.5380 | 0.1106 | 0.4274 | 2933 |
| key-files, creation | 10 | 0.4857 | 0.5276 | 0.1078 | 0.4198 | 2790 |

### Selection vs hindsight (threshold 10)

| quantity | t1814 @400 (current) | current @393 | creation @393 |
|---|---|---|---|
| plan pre-impl precision | 0.4036 | 0.4068 | 0.4068 |
| task precision | 0.4387 | 0.4461 | 0.4562 |
| task − plan gap | +0.0351 | +0.0393 | +0.0494 |
| task-vs-plan precision | 0.4333 | 0.4393 | 0.4467 |

- **Selection effect** (400 → 393, current bodies) raises the task-minus-plan
  gap by +0.0042 (task +0.0074, plan +0.0032).
- **Hindsight effect** (creation − current on the same 393): later edits
  *lowered* precision rather than inflating it. Creation minus current: task
  +0.0101, task-vs-plan +0.0074, key-files +0.0114. Creation-time
  descriptions are slightly MORE precise and slightly less recalling (task
  recall −0.0075, task-vs-plan −0.0090). At thresholds 8 and 20 the direction is
  the same or flat (task at 20: 0.2779 → 0.2776).
- The creation-time margin over the plan reference (+0.0494) is more than 10×
  the selection effect on the gap (+0.0042). So the verdict is distinguishable
  from selection.
- Unverified explanation for the direction: content added after creation
  (verification checklists, `Coordination (from tN)` sections, extra key-files
  lists) names more paths, some of which are never edited. No per-heading
  attribution was run.

### Post-phase: rider_sensitivity (structural heuristic)

Each cohort task's first-add commit, classified by structure: `create_single`
393/393 (the commit adds files for exactly one task id), `multi_task_add` 0,
`start_work` 0, `sync_autocommit` 0, `other` 1. The single `other` is
`635_13`, first added by `ait: Reparent tN as tN …`. Its id was reassigned, so
its "first version" under the current id is the reparent-time body and not its
true creation. Excluding it (union of suspect groups, cohort
`713a0c19e5c88b29|392`, same controls passed) at threshold 10: plan 0.4068;
task current 0.4481 → creation **0.4582**; task-vs-plan 0.4398 → **0.4475**;
key-files 0.4751 → 0.4868. **Q1 verdict unchanged.** Limit: this is a
structural heuristic. A `create_single` commit can still carry pre-commit edits
(a draft edited before its first commit), and no commit metadata reveals that.

### Verdict (Q1, cohort-conditional)

On the **393-task cohort of tasks whose creation-time description resolves**,
t1814's Q1 rule **holds**. Creation-time promoted description precision is ≥ the
plan pre-implementation reference at every threshold. Unordered: 0.4393 /
0.4562 / 0.2776 vs 0.3814 / 0.4068 / 0.2019. Description-vs-plan: 0.4176 /
0.4467 / 0.2327. The hindsight concern t1814 raised does not inflate
description precision in this corpus; if anything it slightly deflates it. The
statement does not extend to the 7 excluded tasks (1.16% of real collisions).
Creation time is the strict bound; the admission-time (claim-time) bracket is
the spawned follow-up `claim_time_bracket`.

## Final Implementation Notes

- **Actual work done:** Measurement only, no repo code changes. Scratch tooling
  (this session's scratchpad): `frozen_io.py`, `sweep_root.py`, `cohort.py`,
  `recover.py`, `prune.py`, `rider.py`; outputs `m/*.txt`, `rider/*.txt`,
  `recovery.tsv`, `cohort_ids.txt`, `dropped_ids.txt`.
- **Deviations from plan:** `recovery.tsv` records `ids_added_in_commit` (the
  structural field) instead of the dropped subject-names-id `rider` flag, per
  the revised post-phase. The dropped-subset issue_type mix is reported as
  counts per id, since 7 tasks are too few for a percentage mix.
- **Issues encountered:** One reparented task (`635_13`): keying first-add by
  task id cannot see history under a previous id. Only 1 cohort task is affected
  and the verdict holds without it. None of the 21 `Start work on` rider adds
  seen during exploration belong to cohort tasks.
- **Key decisions:** The cohort is fixed explicitly (intersection across both
  roots) and imposed by pruning the roots, so the shipped CLI's own `common`
  cohort computes it with no new code path. The wrapper was validated in its
  final form before use.
- **Upstream defects identified:** None
