---
Task: t1814_measure_task_declared_precision.md
Base branch: main
Output branch: main
---

# t1814 — Measure `task_declared` precision over the archived corpus

## Context

t1688_1 shipped a description-derived fallback surface (`task_declared`) for the
parallel-admission checker and made its overlaps **non-blocking** (PINNED 6:
class `declared`, caveat `task_declared_overlap`, never CONFLICT) because nobody
had measured how precise description surfaces are. This task extends
`aitask_parallel_admission.sh sweep` (t1643's archived-pairs oracle) with a
task-description source and answers:

1. May a `task_declared` overlap ever grade CONFLICT? (precision vs the plan
   baseline)
2. Does a "key-files-section-preferred" extraction buy enough precision to
   justify it?

It **measures and recommends only** — no change to `decide`, PINNED 6, or any
shipped verdict.

### Findings from exploration (read-only prototype, scratchpad)

- `sweep` today: `sweep_population` (`parallel_admission_collect.py:1243`) walks
  loose `aiplans/archived/**/p*.md`, oracle = landed sets from
  `_BATCH_MAP(--with-recovered)`, `pas.confusion` tallies unordered pairs. ~3s.
- Loose archived task files: 452 (`aitasks/archived/t*.md`, child dirs
  `t<P>/`; `_b*/old*.tar.zst` bundles are ignored — same as plans).
- **Grading trap:** a description surface with its truthful `task_declared`
  provenance makes *every* pair `CLEAR_CAVEATED` (the `candidate|task_declared`
  caveat) → CONFLICT 0, precision undefined. Precision is only measurable under
  a counterfactual **promotion** (relabel provenance to `plan_declared` and let
  the shipped `decide` grade it). Under promotion, promoted-CONFLICT = exactly
  the pairs that ship as `CLEAR_CAVEATED` with a `task_declared_overlap`.
- Prototype numbers (hub threshold 10, not final — re-measured at implementation):
  plan(full) precision 0.394 / recall 0.881; task-promoted 0.435 / 0.492;
  keyfiles-promoted 0.553 / 0.408; 181/452 task files carry a key-files heading.

## Pre-phase (risk mitigations)

1. [baseline_sweep_parity] **Freeze the inputs first, then compare both code
   versions on that one dataset.** A code-commit worktree cannot restore the
   inputs: `aitasks/` and `aiplans/` are symlinks into the separate, ignored
   `.aitask-data` tree, and the batch map does not preserve document bodies or
   the tracked-path corpus. Concurrent archival can change the inputs while the
   code HEAD stays the same. Before any code edit, in the scratchpad
   (`$SP=/tmp/claude-1000/-home-ddt-Work-aitasks/c384901e-22ac-4001-bfc3-590f06b7cde6/scratchpad`):
   a. `snapshot/`: copy (`cp -L`, loose files only, preserving the
      `aiplans/archived/**` and `aitasks/archived/**` layout) every archived
      plan and task file. Dump `_batch_map(root, with_recovered=True)` lines to
      `snapshot/batch_map.txt`, and dump `plan_paths.tracked_sets(root)` plus
      `data_tracked_sets(root)` to `snapshot/corpus.json`. Write
      `snapshot/MANIFEST.sha256` (sha256 of every file) next to them.
   b. `baseline_lib/`: copy the current `.aitask-scripts/lib/` as it is now
      (working-tree state, before this task edits it). Do not stash or restore;
      the tree is shared.
   c. `frozen_sweep.py <lib_dir> <sweep args…>`: puts `<lib_dir>` first on
      `sys.path`, imports `parallel_admission_collect`, and patches the existing
      seams `_BATCH_MAP` (returns the batch_map.txt lines), `_TRACKED_SETS` and
      `_DATA_TREE` (return the corpus.json sets, with `None` as the data reason).
      Then it calls `main(["sweep", "--root", "$SP/snapshot", …])`. These seams
      exist in both code versions, so one driver serves both.
   d. Capture the baseline with `baseline_lib` for `--thresholds 8,10,20` and
      `--plan-scope pre-implementation --thresholds 8,10,20`.
   After implementation, verify `MANIFEST.sha256` (if it fails, the snapshot is
   discarded and both versions rerun on a fresh one). Rerun the same two
   commands with the working-tree lib and diff them after removing exactly the new
   `SWEEP_SOURCE:` and `SWEEP_COHORT:` lines from the revised output (with
   `grep -v '^SWEEP_SOURCE:\|^SWEEP_COHORT:'`). Every remaining line must be
   byte-identical to the baseline, in the same order. Each of the two new lines
   must appear exactly once. The cohort's own correctness is checked separately
   by the membership tests in Step 4.
   **Step 5 uses this same frozen snapshot for every measurement**, so all
   sources are scored on identical documents, oracle and corpus.

## Step 1 — `.aitask-scripts/lib/parallel_admission_sweep.py` (PURE)

- Update module docstring: the harness now scores plan **and** description
  surfaces; the grading-trap explanation above.
- `KEY_FILES_HEADING_RE` + docstring with the measured heading distribution
  (`key files to modify` 125, `key files` 32, `key files to create` 15,
  `key files to create/modify` 6, `files to modify/touch`, `files likely to
  touch`, `files in scope`; deliberately excluded: `reference files for
  patterns`, `key files for reference`, `files touched by those commits` —
  those name context, not edit targets). Regex over heading lines:
  `^(#{1,6})[ \t]+(?:key[ \t]+files?\b(?![^\n]*reference)|files?[ \t]+(?:to|likely[ \t]+to|in[ \t]+scope)\b)[^\n]*$`, case-insensitive, multiline.
- `key_files_sections(body)` → concatenated text of every key-files section
  (from the heading line's end to the next heading of the same or higher level,
  deeper subheadings kept), or `None` when no such heading exists.
- `key_files_preferred(body)` → `key_files_sections(body)` when not `None`, else
  `body` unchanged (the task's "use the section only when the body has one").
- `promoted(population)` → population with every `task_declared` surface
  relabelled `plan_declared` (via `dataclasses.replace`); other provenances
  untouched. Docstring: the counterfactual "what if PINNED 6 were lifted";
  `decide` still does all grading.
- Refactor `confusion` into a private `_tally(pairs, touch_counts,
  hub_threshold, now)` over an iterable of `(a_surf, a_landed, b_ref, b_surf,
  b_landed)`; `confusion` feeds it `itertools.combinations` (numbers unchanged —
  guarded by the pre-phase parity + existing tests).
- `cross_confusion(candidates, inflight, touch_counts, hub_threshold, now=0)`:
  ORDERED pairs — candidate A's surface (its description) vs in-flight B's
  surface (its plan), for every `A.ref != B.ref` with both refs present in both
  populations. `pairs = n(n-1)`. This models t1688_2's realistic case (a
  described candidate vs a planned in-flight task). Docstring: pairs are
  ordered because the two surfaces of one pair come from different documents,
  so (A desc, B plan) and (B desc, A plan) are distinct comparisons.

## Step 2 — `.aitask-scripts/lib/parallel_admission_collect.py`

- Generalise `_archived_plan_paths(root)` into
  `_archived_doc_paths(root, top, id_re)`; keep `_archived_plan_paths` as a thin
  wrapper; add `_archived_task_paths(root)` over `aitasks/archived` with
  `^t(\d+(?:_\d+)?)_.*\.md$`.
- `SWEEP_SOURCES = ("plan", "task", "task-keyfiles", "task-vs-plan")`.
- `sweep_population(root, plan_scope="full", batch_lines=None, corpus=None,
  source="plan")`:
  - `plan` — unchanged behaviour.
  - `task` — archived task files, `body_transform=plan_paths.cut_task_framework_sections`,
    surfaces built `as_surface(provenance="task_declared")` (truthful).
  - `task-keyfiles` — transform = cut then `pas.key_files_preferred`, same
    provenance.
  - Same inclusion rule (resolved extraction + resolved non-empty landed set),
    same `(tasks, kept, dropped)` drift accounting. Returns the same triple.
- `key_files_coverage(root)` → `(with_section, total)` over archived task files
  (reads bodies, applies the framework cut, `pas.key_files_sections(...) is not None`).
- `_run_sweep(opts)`:
  - Collect the batch map and corpus ONCE and pass them into every
    `sweep_population` call (one snapshot, as `replay --thresholds` does).
  - `task-vs-plan`: build `task`, `task-keyfiles` and `plan` populations and
    restrict all three to ONE cohort: refs resolved in all three, whatever
    `--population` says. Emit two blocks from the same cohort, plan scope,
    oracle and thresholds, so the Q2 narrowing comparison holds in the
    realistic pairing and not only in desc-vs-desc:
    - `SWEEP:` / `SWEEP_METRIC:` from
      `pas.cross_confusion(promoted(task_pop), plan_pop, ...)`, using the
      whole-body description;
    - `SWEEP_KF:` / `SWEEP_KF_METRIC:` (same field layout) from
      `pas.cross_confusion(promoted(keyfiles_pop), plan_pop, ...)`, where only the
      candidate description is narrowed.
    This adds no new CLI mode. `SWEEP_POP:` reports the shared cohort.
  - `task` / `task-keyfiles`: rows from `pas.confusion(promoted(pop), ...)`.
  - `--population common`: restrict every population used to refs resolved in
    ALL of `plan` (**at the same `--plan-scope` as the run**), `task` and
    `task-keyfiles`, for apples-to-apples comparison (default `own`). Allowed
    on every source, including `plan`. The cohort is computed by ONE helper,
    `_common_refs(root, plan_scope, batch_lines, corpus)`, and `task-vs-plan`
    uses that same helper, so at equal plan scope a `common` sweep of any
    source and a `task-vs-plan` sweep have identical task membership. Emit
    `SWEEP_COHORT:<sha256 of the sorted ref list, first 16 hex>|<n>` on every
    run so membership equality can be checked directly from the output.
  - Output: existing lines unchanged; add `SWEEP_SOURCE:<source>|<grade>|<population>`
    as the second line (`grade` = `as-shipped` for `plan`, `promoted` otherwise);
    for `task-vs-plan` add `SWEEP_DRIFT_PLAN:` for the plan side; for
    `task-keyfiles` add `SWEEP_KEYFILES:<with_section>|<total>`.
- `_parse_args`: new flags `--source` (default `plan`) and `--population`
  (default `own`). Refusals (exit 2, via `_die`, messages naming the reason):
  unknown values; either flag on `check`/`replay` ("only meaningful for
  `sweep`"); `--plan-scope pre-implementation` with `--source task|task-keyfiles`
  **and `--population own`**. In that combination no plan is read, so the flag
  would be silently accepted and ignored. The same scope is **accepted** with
  `--population common`, because the plan at that scope decides which tasks
  are in the shared cohort. It is also accepted with `task-vs-plan`, where it
  applies to both the plan side and the cohort.

## Step 3 — `.aitask-scripts/aitask_parallel_admission.sh`

Header comment: document `--source` / `--population`, the promoted grading, and
the new output lines.

## Step 4 — Tests

`tests/test_parallel_admission_sweep.py` (pure):
- `KeyFilesSectionTests`: section extracted up to the next same/higher heading;
  deeper subheading kept; multiple sections concatenated; `Reference files for
  patterns` / `Key files for reference` do NOT match; mid-line text not a
  heading; no heading → `key_files_preferred` returns body unchanged and
  `key_files_sections` returns `None`; case-insensitive.
- `PromotionTests`: shipped `task_declared` surfaces on an overlapping fixture
  yield CONFLICT 0 (pins why promotion exists — negative control); `promoted`
  yields CONFLICT > 0; `promoted` leaves `plan_declared`/`origin_derived`
  surfaces untouched.
- `CrossConfusionTests`: pairs = n(n-1); self pairs excluded; an asymmetric
  fixture where A's description overlaps B's plan but B's description does not
  overlap A's plan gives exactly one CONFLICT; refs missing from either side are
  excluded; `confusion` result unchanged after the `_tally` refactor (existing
  arithmetic tests already cover this).

`tests/test_parallel_admission_collect.py`:
- Extend `SweepPopulationTests` with archived task files (loose + child dir):
  `source="task"` reads descriptions with `task_declared` provenance and cuts
  `## Gate Runs`; `source="task-keyfiles"` narrows to the section when present
  and falls back to the whole body when absent; default source still reads plans.
- `_parse_args` refusals: bad `--source`/`--population`; either flag on `check`
  and `replay`; `--plan-scope pre-implementation` with `--source task` and with
  `--source task-keyfiles` under `--population own` (refused, exit 2); the same
  combinations under `--population common` (accepted); accepted with
  `task-vs-plan`.
- `main(["sweep", "--source", "task-vs-plan"])` over the fixture: emits
  `SWEEP_SOURCE:task-vs-plan|promoted|own`, `SWEEP_DRIFT_PLAN:`,
  `SWEEP_POP` pairs = n(n-1) over the three-way cohort, plus `SWEEP_KF:` rows.
  The fixture has one task whose key-files section drops an overlap that its
  whole body has, so the `SWEEP_KF` CONFLICT count differs from `SWEEP`, and a
  cohort-mismatch mutant cannot pass. `--population common` shrinks
  `plan`/`task`/`task-keyfiles` sweeps to the intersection. A membership test
  asserts that at the same `--plan-scope`, `SWEEP_COHORT:` is identical across
  `plan --population common`, `task --population common` and `task-vs-plan`.
  The fixture includes a plan that resolves only under `full` scope (its paths
  sit under `## Final Implementation Notes`), so the cohort must differ between
  scopes. A scope-blind cohort mutant fails this test.

`tests/test_parallel_admission_cli.sh`: one `assert_contains` that
`sweep --source task` emits `SWEEP_SOURCE:task|promoted|own`, and one exit-2
check for `check --source task`.

## Step 5 — Measurement (the deliverable)

Run every command through `frozen_sweep.py` with the working-tree lib against
the pre-phase snapshot (verify `MANIFEST.sha256` first). Use thresholds `8,10,20`:
- Plan baselines, **each with `--population own` AND `--population common`**:
  `sweep` (full) and `sweep --plan-scope pre-implementation`. The
  pre-implementation `common` run is the reference the Q1 rule compares against.
- `sweep --source task` and `--source task-keyfiles`, each with
  `--population own` and `common`.
- `sweep --source task-vs-plan`, with the plan side both full and
  pre-implementation. Each run gives whole-body (`SWEEP`) and
  candidate-narrowed (`SWEEP_KF`) rows on one cohort. **This pairing decides
  Q2.** The desc-vs-desc comparison is supporting evidence only.
- Finally, one live (unfrozen) `sweep --source task-vs-plan` as an end-to-end
  smoke check of the real CLI. Its numbers are not part of the table.

Record in the plan's Final Implementation Notes: a precision / recall /
hard-stopped / downgraded table per source and threshold, population sizes and
drift, key-files coverage, and the recommendation for Q1 (promote or keep
PINNED 6) and Q2 (adopt key-files narrowing or not), stating the decision rule
used. A promoted description source may hard-stop only if its CONFLICT
precision at the shipped threshold is ≥ the plan baseline under
`--plan-scope pre-implementation --population common`. The comparison is valid
only when the compared runs print the same `SWEEP_COHORT:` (same membership,
same plan scope); check that before writing the table. The recommendation also
weighs the hard-stop share that promotion adds. Q2 is decided on the
`task-vs-plan` `SWEEP` vs `SWEEP_KF` rows at pre-implementation scope. Their
cohort is the same by construction. The
recommendation is advisory; any contract change is t1688_2 / t1343's call.

Then send a note to t1688_2 (still Ready) with the table + recommendation via
`./ait note 1688_2 --from 1814 --file -`.

## Verification

- Pre-phase parity diff clean.
- `python3 -m pytest tests/test_parallel_admission_sweep.py tests/test_parallel_admission_collect.py tests/test_parallel_admission_purity.py -q` (or unittest).
- `bash tests/test_parallel_admission_cli.sh`.
- `bash tests/run_all_python_tests.sh --test-dir tests` — read the LAST line only.
- `shellcheck .aitask-scripts/aitask_parallel_admission.sh`.

## Step 9 (Post-Implementation)

Commit code (`enhancement: … (t1814)`), commit plan via
`aitask_task_commit.sh`, archive per task-workflow Step 9.

## Risk

### Code-health risk: low
- The `_tally` refactor of `confusion` could silently move the published plan-sweep numbers · severity: low (residual — addressed by inline pre-phase baseline_sweep_parity) · → mitigation: inline pre-phase baseline_sweep_parity
- Two new CLI flags widen the sweep's surface; accepted-and-ignored combinations are the known hazard · severity: low · → mitigation: none (refusals + tests in Step 2/4)

### Goal-achievement risk: medium
- Archived task descriptions may have been edited after the work started (hindsight), inflating description precision/recall; the plan side has `--plan-scope pre-implementation` but the description side has no equivalent cut · severity: medium · → mitigation: t1824
- Promotion (relabel to `plan_declared`) is a proxy for "if PINNED 6 were lifted"; it is exact only while provenance affects `decide` solely through the `task_declared` caveat and `declared` class · severity: low · → mitigation: none (PromotionTests pin the shipped-vs-promoted difference)
- The key-files heading regex is heuristic; a miss or false match moves the Q2 numbers · severity: low · → mitigation: none (report `SWEEP_KEYFILES` coverage alongside)

### Planned mitigations
- timing: pre-phase | name: baseline_sweep_parity | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — `_tally` refactor could move published plan-sweep numbers | desc: capture sweep output before any edit and diff it byte-for-byte after implementation
- timing: after | name: creation_time_description_hindsight | type: enhancement | priority: low | effort: medium | inline_risk: low | added_complexity: medium | addresses: goal-achievement — post-hoc description edits may inflate task_declared precision | desc: re-run the description sweep over each archived task file's first data-branch version (git log --diff-filter=A) and compare against the current version to bound hindsight bias

## Implementation progress (2026-09-17)

All steps implemented: pre-phase `baseline_sweep_parity`, Steps 1–4, and the
Step 5 measurement below.

### Pre-phase parity (frozen snapshot)

Snapshot: 907 loose archived plan + task files, 89652 batch-map lines, code
corpus 2102 files + task-data corpus 1685 files, `MANIFEST.sha256` verified
before and after every measurement. `baseline_lib` (the pre-edit
`.aitask-scripts/lib/`) and the revised lib were run on that one dataset for
`--thresholds 8,10,20` at both plan scopes. After removing the
`SWEEP_SOURCE:` / `SWEEP_COHORT:` lines (each present exactly once), the output
was **byte-identical** to the baseline. The live CLI `sweep --source
task-vs-plan --thresholds 10` then reproduced the frozen numbers exactly, so the
archive did not move during the session.

### Measurement (frozen snapshot; hub threshold 10 is the shipped default)

Columns: CONFLICT precision · flagged recall (CONFLICT ∪ CAVEATED) · share of
real collisions hard-stopped · share downgraded to a caveat. Description sources
are graded **promoted** (as if plan evidence). Graded as shipped they cannot
CONFLICT: `PromotionTests` pins that.

**Unordered pairs over the common cohort** (`SWEEP_COHORT:7b0461e726532b5c|400`,
79800 pairs, 6360 really colliding; the cohort is identical at both plan scopes,
because in this corpus no plan loses resolution under the pre-implementation cut):

| source | th | precision | recall | hard-stopped | downgraded | CONFLICT verdicts |
|---|---|---|---|---|---|---|
| plan, full | 8 | 0.3610 | 0.8794 | 0.2574 | 0.6220 | 4534 |
| plan, full | 10 | 0.3871 | 0.8794 | 0.3129 | 0.5665 | 5141 |
| plan, full | 20 | 0.2005 | 0.8794 | 0.6903 | 0.1892 | 21891 |
| **plan, pre-impl (reference)** | 8 | 0.3786 | 0.8535 | 0.2464 | 0.6071 | 4139 |
| **plan, pre-impl (reference)** | 10 | **0.4036** | 0.8535 | 0.2961 | 0.5574 | 4666 |
| **plan, pre-impl (reference)** | 20 | 0.2016 | 0.8535 | 0.6690 | 0.1844 | 21108 |
| task (whole body) | 8 | 0.4235 | 0.4888 | 0.0871 | 0.4017 | 1308 |
| task (whole body) | 10 | **0.4387** | 0.4888 | 0.1086 | 0.3802 | 1575 |
| task (whole body) | 20 | 0.2773 | 0.4888 | 0.2346 | 0.2542 | 5381 |
| task-keyfiles | 8 | 0.5315 | 0.4057 | 0.0505 | 0.3552 | 604 |
| task-keyfiles | 10 | 0.5568 | 0.4057 | 0.0640 | 0.3417 | 731 |
| task-keyfiles | 20 | 0.4780 | 0.4057 | 0.1335 | 0.2722 | 1776 |

**Ordered pairs, described candidate vs planned in-flight task** (`task-vs-plan`,
same cohort digest, 159600 ordered pairs, 12720 really colliding):

| plan side | candidate | th | precision | recall | hard-stopped | downgraded | CONFLICT | missed |
|---|---|---|---|---|---|---|---|---|
| pre-impl | whole body | 8 | 0.4056 | 0.6177 | 0.1214 | 0.4963 | 3807 | 4863 |
| pre-impl | whole body | 10 | **0.4333** | 0.6177 | 0.1548 | 0.4629 | 4544 | 4863 |
| pre-impl | whole body | 20 | 0.2328 | 0.6177 | 0.3772 | 0.2405 | 20609 | 4863 |
| pre-impl | key-files | 8 | 0.4472 | 0.5397 | 0.0899 | 0.4498 | 2558 | 5855 |
| pre-impl | key-files | 10 | **0.4685** | 0.5397 | 0.1109 | 0.4288 | 3012 | 5855 |
| pre-impl | key-files | 20 | 0.3096 | 0.5397 | 0.2551 | 0.2846 | 10480 | 5855 |
| full | whole body | 10 | 0.4258 | 0.6442 | 0.1599 | 0.4843 | 4777 | 4526 |
| full | key-files | 10 | 0.4596 | 0.5760 | 0.1153 | 0.4607 | 3192 | 5393 |

Own populations: plan 412 tasks (`41809b1907ca236f`), task 402
(`9ad7fe6de5380b9e`, precision 0.4368 at 10, within 0.002 of common), and
task-keyfiles 400. Drift (tasks|kept|dropped): plan full 412|5030|5806, plan
pre-impl 412|4686|5012, task 412|2486|1530, task-keyfiles 412|1765|925.
Key-files coverage: **180 / 457** archived task files carry a key-files heading.

### Recommendation (advisory; the contract change belongs to t1688_2 / t1343)

- **Q1: may a `task_declared` overlap grade CONFLICT?** The pre-set rule is met.
  Promoted description precision is at least the plan pre-implementation
  reference on the identical cohort, at every threshold. Unordered: 0.4235 /
  0.4387 / 0.2773 vs 0.3786 / 0.4036 / 0.2016. In the realistic
  description-vs-plan pairing: 0.4056 / 0.4333 / 0.2328. So the premise behind
  PINNED 6, that descriptions are too coarse to hard-stop *compared with plans*,
  is **not supported**. Description hard stops are about as trustworthy as plan
  hard stops. They are also rarer: 1575 vs 4666 CONFLICTs, and a hard-stopped
  share of 0.1086 vs 0.2961. The cost is recall, not precision (0.49 vs 0.85
  flagged). Two limits apply. First, both sources are wrong on about 56–60% of
  hard stops, so this argues for **parity** (grade description evidence like
  plan evidence) and not for making either one a blocking stop. The procedure's
  advisory-by-design posture stands. Second, the description numbers may carry
  hindsight bias from post-hoc edits. Recommendation: lifting PINNED 6 to parity
  is justified on precision, but **wait for the `creation_time_description_hindsight`
  follow-up** to bound that bias before changing the contract.
- **Q2: adopt key-files-section-preferred extraction?** **No.** Measured in the
  deciding pairing (description vs plan, pre-implementation, threshold 10),
  narrowing gains +3.5pp precision (0.4333 → 0.4685). It loses 7.8pp flagged
  recall (0.6177 → 0.5397), adds 992 missed real collisions (4863 → 5855), and
  applies to only 180/457 tasks. The larger desc-vs-desc gain (0.4387 → 0.5568)
  does **not** carry over to the realistic pairing, which is exactly why that
  comparison was added. Whole-body extraction (t1688_1) stays.

## Final Implementation Notes

- **Actual work done:** as planned. Steps 1–5 plus the inline pre-phase.
  - `parallel_admission_sweep.py` (pure): `key_files_sections` /
    `key_files_preferred` with `KEY_FILES_HEADING_RE`, `promoted`, `cross_confusion`
    (ordered pairs), `cohort_digest`, and a shared `_tally` counting loop behind
    `confusion`.
  - `parallel_admission_collect.py`: `_archived_doc_paths` (plans and tasks),
    `sweep_population(source=…)`, `key_files_coverage`, the `_common_refs` cohort,
    `--source plan|task|task-keyfiles|task-vs-plan`, `--population own|common`,
    and the new output lines `SWEEP_SOURCE:`, `SWEEP_COHORT:`,
    `SWEEP_DRIFT_PLAN:`, `SWEEP_KEYFILES:`, `SWEEP_KF:` / `SWEEP_KF_METRIC:`.
  - CLI header comment updated. Tests: 32 new Python tests, 4 new CLI checks.
  - The measurement table and recommendation are above.
- **Deviations from plan:** `_common_refs` takes the three already-built
  populations instead of `(root, plan_scope, batch_lines, corpus)`. `_run_sweep`
  builds each population once from a single batch map and corpus, and always
  passes the `plan` population at the run's own `--plan-scope`. That keeps it
  the single cohort definition without rebuilding anything.
  `SWEEP_DRIFT:` for `task-vs-plan` reports the description side over its full
  population, before the cohort restriction, matching every other source.
- **Issues encountered:**
  - The full Python suite reported `FAILED` only in
    `tests/test_minimonitor_bottom_pin_live.py` (test_2 / test_5, "no grab was
    observed"). That file is a live tmux TUI test in the serial carve-out, and
    run alone it passes 6/6. It is unrelated to this change; the checkout also
    carried other sessions' uncommitted tmux/TUI edits.
  - Mutation checks run in an isolated scratch copy: a scope-blind cohort fails
    `test_the_cohort_follows_the_plan_scope`, and a narrowed block built on the
    wrong population fails `test_task_vs_plan_scores_ordered_pairs_with_a_narrowed_block`.
  - In the live corpus, the cohort is identical at both plan scopes: no archived
    plan loses resolution under the pre-implementation cut. The scope sensitivity
    is therefore pinned by the fixture, not by the corpus.
- **Key decisions:**
  - Description sources are always graded **promoted**. As shipped, the
    candidate's own `task_declared` caveat makes every pair `CLEAR_CAVEATED`, so
    precision is undefined.
  - `task-vs-plan` always uses the three-way cohort, so its whole-body and
    key-files blocks share membership, plan scope, oracle and thresholds.
  - The key-files regex lives in the sweep module as a measured variant, not in
    `plan_paths`: the shipped grammar is untouched.
- **Upstream defects identified:** None
