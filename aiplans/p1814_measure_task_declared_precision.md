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
- Archived task descriptions may have been edited after the work started (hindsight), inflating description precision/recall; the plan side has `--plan-scope pre-implementation` but the description side has no equivalent cut · severity: medium · → mitigation: creation_time_description_hindsight
- Promotion (relabel to `plan_declared`) is a proxy for "if PINNED 6 were lifted"; it is exact only while provenance affects `decide` solely through the `task_declared` caveat and `declared` class · severity: low · → mitigation: none (PromotionTests pin the shipped-vs-promoted difference)
- The key-files heading regex is heuristic; a miss or false match moves the Q2 numbers · severity: low · → mitigation: none (report `SWEEP_KEYFILES` coverage alongside)

### Planned mitigations
- timing: pre-phase | name: baseline_sweep_parity | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — `_tally` refactor could move published plan-sweep numbers | desc: capture sweep output before any edit and diff it byte-for-byte after implementation
- timing: after | name: creation_time_description_hindsight | type: enhancement | priority: low | effort: medium | inline_risk: low | added_complexity: medium | addresses: goal-achievement — post-hoc description edits may inflate task_declared precision | desc: re-run the description sweep over each archived task file's first data-branch version (git log --diff-filter=A) and compare against the current version to bound hindsight bias
