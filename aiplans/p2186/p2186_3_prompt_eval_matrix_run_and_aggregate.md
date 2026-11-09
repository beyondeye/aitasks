---
Task: t2186_3_prompt_eval_matrix_run_and_aggregate.md
Parent Task: aitasks/t2186_generic_agent_prompt_eval_harness.md
Sibling Tasks: aitasks/t2186/t2186_1_*.md, aitasks/t2186/t2186_2_*.md, aitasks/t2186/t2186_4_*.md, aitasks/t2186/t2186_5_*.md, aitasks/t2186/t2186_6_*.md, aitasks/t2186/t2186_7_*.md
Archived Sibling Plans: aiplans/archived/p2186/p2186_*_*.md
Base branch: main
Output branch: main
---

# t2186_3: Matrix run with resume, web-off probe, answer index, decision score and aggregator

Child 3 of t2186. The parent plan is `aiplans/p2186_generic_agent_prompt_eval_harness.md`; the task file carries the shared
constraints, the facts established during exploration and the target layout. Read both. Treat any deviation recorded in an archived sibling plan's Final Implementation Notes as authoritative over this plan.

## Context

Child 3 of t2186. It closes, generically, the "Harness gaps a future main run must close first"
list from the t2179_2 plan:
- a matrix `run` with `--resume`;
- limits blocks per command;
- the Codex web-off flag and its behavioural probe;
- all-scenario controls;
- a durable answer index;
- final-record-per-cell aggregation and the aggregator.

It also defines the **conservative decision score and coverage** that every later decision
(stopping, selection, comparisons) must read, so that excluding unresolved trials can never
inflate a decision.

### Pre-phase (risk mitigations)

1. [cli_flag_recheck] As the **first implementation step** of t2186_2 (adapters), t2186_3 (web
   flag) and t2186_5 (judge system-prompt arms): run `claude --help`, `codex exec --help` and
   `codex exec resume --help`; confirm that every flag the child's adapter code emits exists in
   the installed version; record `claude --version` and `codex --version` in the child plan; and
   add a test that pins the emitted argv for every agent × turn × option case. A missing or
   renamed flag **stops the child** and is reported to the user, never worked around silently.
   This step is copied verbatim into those three child task files.

## Implementation

### `prompt_eval_matrix_run_and_aggregate` (no spend)

Closes p2179_2's "Harness gaps a future main run must close first" list, generically.

1. **`pecore/matrix.py`** — `Cell`, `expand_matrix` (latin orders from the spec), `seeded_order`,
   `pending_cells` (launched sessions stand; setup failures / not_run are re-run).
2. **`run --batch B --matrix <file> --limits-block <name> [--resume]`** — runs
   `seeded_order(expand_matrix(...), seed)` through the approval gate; the limits block is chosen
   by command (`smoke` → `smoke`/`pilot`, `run` → `--limits-block`, required). The `--matrix`
   file's content hash and the expanded cell list's digest are manifest keys (child 2), so the
   approval covers the exact cells, not the file name. `--resume` rebuilds the same manifest and
   refuses if anything but the batch's own progress changed. Matrix
   projection in `plan run`: subject invocations per turn index, answers, answer judgings
   (answers × judges), control judgings (control scenarios × 2 × judges), and per-meter cost
   from a reference batch's `invocations.jsonl` means by purpose and turn index.
3. **Web-off probe** — `probe web --batch B`: one Codex invocation (`purpose: probe`, never a
   sample, budget-counted, approval-gated) that asks for a web lookup under the flag. Verdict:
   `WEB_OFF:CONFIRMED` only with positive evidence (a completed turn with activity and zero
   `web_search` items); any `web_search` item → `WEB_OFF:FAILED` (stop and report); no activity
   or an unparseable trace → `WEB_OFF:INCONCLUSIVE`, never "confirmed". The positive contrast is
   cited from the pilot (Codex web-searched in every fresh `>q` turn), not re-bought.
   Aggregation counts `web_search` items per trial.
4. **All-scenario controls** from `judging.controls.scenarios` (shadow_q: `"all"` → 4 scenarios).
5. **Durable answer index** — private `runs/<B>/answers.jsonl`, appended per valid trial under
   the lock with fsync; legacy `answers.json` still read; on `--resume` cross-checked against
   `trials.jsonl` + the private run dirs (a mismatch refuses).
6. **Final record per cell** — each `cell_id`'s last launched session supplies its trials;
   `retried`, never-launched setup failures and superseded `not_run` rows are reported under
   `superseded`, never in a denominator.
7. **`aggregate --batch B`** → public `runs/<B>/summary.json` through a whitelisted `aggregate`
   record kind: per cell / agent / variant / condition / scenario — compliance **and** overall
   success side by side (the writer refuses one without the other), sensitivity lines,
   outcome-class counts, Wilson 95% intervals labelled small-sample, an under-sampled flag
   (classifiable < frozen reps), a gap list against `expand_matrix` (`not_run:<reason>` per
   missing cell, counts by block); conditional quality per judge over valid answers;
   calibration and disputes; covariates (answer chars, `web_search` counts, session flags);
   usage and latency by purpose. Next to them, the decision quantities from step 7a.
7a. **The conservative decision score and coverage** (`pecore/outcomes.py`, new functions; the
   historical `summarise` is untouched, so child 1's equivalence still holds):
   - **eligible** = attempted − `infra_failure:*` − `not_run:*` (harness faults, not the
     prompt's); `uncertain_*` trials **stay eligible**;
   - **decision score** = successes / eligible. A success is `valid`, and also adequate when the
     spec judges. Every unresolved trial therefore counts as **not a success**: an exclusion can
     never raise the score;
   - the **optimistic bound** counts unresolved trials as successes. It is used only to decide
     that a cell has *failed* (child 5);
   - **coverage** = resolved / eligible, where resolved = eligible − `uncertain_*`;
   - `min_coverage` is pre-registered in the spec (proposed 0.8) and bound into the digest. Below
     it, a cell or candidate is "insufficient coverage" and can neither be selected nor stop as a
     success.
   The aggregate emits the decision score, its Wilson interval, the optimistic bound and coverage
   beside the historical metrics, each labelled ("decision" vs "historical, excludes
   uncertain").
8. **Concurrent judges** (2 workers per answer); blind ids assigned from the seeded RNG before
   dispatch.
9. **Tests** (`tests/test_prompt_eval_matrix.py`): the shadow_q main matrix expands to 196
   sessions and the projection to 872 invocations; limits-block selection and refusal of a
   missing block; the web flag in both argv builders; the probe's three verdicts (fake CLI with
   and without `web_search` items, and with no activity); the answer index survives a kill
   mid-batch; final-record-per-cell drops superseded rows; aggregate metrics, Wilson bounds and
   the under-sampled flag on synthetic trials; overall success never emitted without compliance;
   the summary record carries no non-whitelisted key. **Decision-score properties:**
   - moving any trial from a success to `uncertain_*`, or adding an `uncertain_*` trial, never
     raises the decision score (checked over a seeded set of random trial lists);
   - 1 complete + 9 `uncertain` trials score 1/10 with coverage 0.1, so they are "insufficient
     coverage", while the historical `compliance_rate` for the same list still reads 1/1;
   - the historical `summarise` output for the shadow_q pilot is byte-identical before and after
     these functions land.

## Step 9

Archive via the normal Step 9 (Post-Implementation). The parent t2186 auto-archives with its last child.

## Verification

- The shadow_q main matrix expands to 196 sessions and the projection to 872 invocations.
- The probe's three verdicts are covered under fake CLIs; `WEB_OFF:CONFIRMED` requires positive
  evidence.
- The decision score is monotone under exclusions; the pilot's historical `summarise` output is
  unchanged.
- `python3 tests/test_prompt_eval_matrix.py` and `run_all_python_tests.sh --test-dir` are green;
  `check-public --staged` passes; `git diff --stat` is clean outside the allowed paths.
- No paid call is made by this child.

## Risk

### Code-health risk: low
- New code and additions inside `pecore/`; `summarise` untouched. · severity: low
  · → mitigation: none (contained by design)

### Goal-achievement risk: medium
- Rates that exclude unresolved trials could reward incomplete answers. · severity: high
  (residual low) · → mitigation: none (addressed in design: the decision score plus coverage,
  with monotonicity tests)
- A silently ignored web flag would make the web-off condition false. · severity: low (residual
  — addressed by inline pre-phase cli_flag_recheck and the positive-evidence probe)
  · → mitigation: inline pre-phase cli_flag_recheck

### Planned mitigations
- timing: pre-phase | name: cli_flag_recheck | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: CLI drift silently dropping or renaming the web_search config flag | desc: check every emitted flag against the installed `--help`, record both CLI versions, pin the emitted argv in a test; a missing flag stops the child and is reported
