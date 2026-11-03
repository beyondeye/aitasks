---
Task: t2179_2_shadow_q_main_run_and_report.md
Parent Task: aitasks/t2179_shadow_q_definition_experiments.md
Sibling Tasks: aitasks/t2179/t2179_1_*.md
Archived Sibling Plans: aiplans/archived/p2179/p2179_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-03 18:08
---

# t2179_2: Shadow `>q` main run, blinded scoring, audit and report

Child 2 of t2179. The parent plan is `aiplans/p2179_shadow_q_definition_experiments.md`.
The primary record of what was actually built is the archived t2179_1 plan
(`aiplans/archived/p2179/p2179_1_shadow_q_harness_and_pilot.md`). Treat any harness
deviation recorded there as authoritative over this plan's assumptions.

## Status (2026-11-03): main run DECLINED at the approval gate, nothing spent

The approval gate (step 1) ran on 2026-11-03. With the re-checked projection below,
the user **declined** the main-run budget. **No paid invocation was made.** The
harness, the store and the frozen `matrix.json` are untouched. **Superseded the same
day by the Rescope section below:** the task now closes on the pilot's evidence with
no paid calls. The main run moves to t2186 / t2187.

Decisions taken at the gate:
- **Main-run budget: declined** ("Decline: stop here").
- **Web access: disable for both.** Codex runs with `-c web_search="disabled"`, for
  both subject and judge. Claude stays without web tools (none on its allowlist).
  This holds for any future main run unless the user reverses it.
- **Risk mitigations: none** (the cost levers below are listed for a future approval,
  not as tasks).

## Verification record (2026-11-03, aitasks HEAD `2bdd5d45a`)

Re-checked against the tree and the t2179_1 records:
1. **The public/private split supersedes this plan's old storage step.** aitasks is
   PUBLIC and aitasks_go is PRIVATE. Raw runs, answer texts, judge rationales,
   quotes, fixtures and the blinding map go to the aitasks_go store
   `aidocs/shadow_q_store/` (`./ait projects resolve aitasks_go`). Only
   numbers-only records (the `store.PublicSink` whitelist) go under
   `aidocs/benchmarks/shadow_q/`. Run `python3 aidocs/benchmarks/shadow_q/check_public.py --staged`
   before every public commit.
2. **The store is pushed.** `origin/main` of aitasks_go contains `3fcf4bd`, the last
   store commit. The t2179_1 note said "not pushed"; that was true when it was
   written and is stale now.
3. **Provenance correction.** The pre-decision t60_2 task body is aitasks_go data
   commit `e022bc0`, not code commit `b523a6bc`. `b523a6bc` holds only the
   instruction files and is the commit the t60_2 Step 0 measurements were taken at.
   Plan `d55e17a` already records the user's decisions, so it is used for measured
   facts only. See the store's `fixtures/PROVENANCE.md`.
4. **Re-checked projection** for the frozen `matrix.json`, re-derived offline with
   `harness.expand_matrix`: 196 sessions (fresh 144, minimal 40, repeated 12),
   416 subject invocations, 220 answers, 440 answer judgings and 16 control
   judgings, so **872 invocations**. The per-call figures come from the pilot's
   `runs/pilot/invocations.jsonl`.
   - The judge prompt now includes the task file. The 4 pilot re-judge calls made
     with it cost **$0.277-0.278 per Claude judge call** and **17.6-18.2k non-cached
     tokens per Codex judge call**. The frozen projection assumed $0.094 and 8.3k.
   - Subjects, by turn: Claude startup $0.295, `>q` turn 2 $0.60, repeated turns 3
     and 4 $0.77 and $0.93. Codex startup 28.2k, turn 2 43.5k, turns 3 and 4 25.6k
     and 31.0k.

   | | subjects | judging (228 calls per judge) | total | frozen threshold |
   |---|---|---|---|---|
   | Claude | ≈ $100 | ≈ $64 | **≈ $164** | $145 |
   | Codex (non-cached tokens) | ≈ 7.4M | ≈ 4.1M | **≈ 11.5M** | 10.5M |

   Wall clock is ≈ 2.3 h of subjects at 2 concurrent sessions, plus ≈ 3.7-4 h of
   sequential judging, or ≈ 2 h if each answer's two judges run concurrently.
5. **Cost levers for a future approval** (measured or derived; none chosen):
   - Run the minimal-context block on `file_selection` only (20 sessions, not 40):
     saves ≈ $15 Claude and ≈ 1.1M Codex tokens. The total becomes ≈ $150 / ≈ 10.4M.
   - Group judge calls by scenario so the Claude judge's large shared prompt prefix
     can hit the prompt cache. Unmeasured: the pilot judged in shuffled order. A
     4-6-call probe would settle it.
   - Raised thresholds that fit the full matrix: invocation cap 920, Claude $200,
     Codex 14M.

## Harness gaps a future main run must close first (step 1b; code only, no spend)

`harness.py` was built for the pilot. These gaps were found by reading it at
`2bdd5d45a`:
- **There is no main-matrix command.** `cmd_pilot` runs `pilot_cells()`, and
  `expand_matrix()` exists but nothing calls it. Add `harness.py main --batch <B>`
  that runs `seeded_order(expand_matrix(matrix.json), matrix.seed)` with `--resume`
  (`pending_cells`).
- **Every cap is the pilot's.** `_experiment()` builds `Budget` from
  `limits["pilot"]`, and `_finish()` reads `limits["pilot"]["circuit_breaker_consecutive"]`.
  Add a frozen `limits.json` `"main"` block (cap, Claude and Codex thresholds,
  `reserve_for_controls: 16`, circuit breaker) holding the **approved** numbers,
  and select the block by command.
- **Web flag.** `subject_argv()` (turn 1 and resume) and `judge.judge_argv()` for
  Codex gain `-c web_search="disabled"`, recorded in session metadata. Before the
  main run, one probe invocation (`condition: probe`, never a sample) asks Codex
  under the flag to search the web, and expects **zero** `web_search` items. The
  pilot showed the unflagged behaviour as the contrast. If the probe still
  searches, stop and report. The main run also counts every `web_search` item and
  reports it.
- **Control scenarios.** `Experiment.control_scenarios` is hard-coded to the 3 AUQ
  scenarios. The main run needs all 4: `working_wait` has controls in the store
  that have never been judged.
- **A durable answer index.** `answers.json` is written only at the end of
  `cmd_pilot`, so an interrupted multi-hour run would lose it. Append it per session
  (under the existing lock), or rebuild it from `trials.jsonl` plus the private run
  dirs on resume.
- **Final record per cell.** On `--resume`, the pilot's `trials.jsonl` kept the
  superseded never-launched rows, and `cmd_summary` counted them. Aggregation must
  take each cell's last launched session and report the superseded rows separately.
- **Judging wall clock (optional).** Run each answer's two judges concurrently
  (2 workers). Blind ids are still assigned sequentially from the seeded RNG
  before dispatch.
- **`aggregate.py` does not exist yet** (step 4).
- **Tests** in `tests/test_shadow_q_harness.py` (offline, fake CLIs) cover:
  - the main expansion: 196 sessions, 872 planned invocations;
  - the selection of the `main` limits block;
  - the web flag in both argv builders;
  - the per-session answer index surviving an interrupt;
  - final-record-per-cell aggregation;
  - the aggregate metrics and the under-sampled flag, on synthetic trials.

## Rescope (2026-11-03, user decision): pilot-evidence closure, no paid calls

After the budget was declined, the user chose to **finish t2179_2 from t2179_1's
pilot results, with no further paid runs**. The "Implementation" section below is
kept for the record. Its main-run design moves to two new tasks:
- **t2186:** a generic agent-prompt eval harness, dev tooling under
  `aidocs/benchmarks/prompt_eval/`. It absorbs the "Harness gaps" list above.
- **t2187:** a Codex-only v1 vs v2 (± v3) targeted experiment. Postponed, depends on
  t2186, with web search disabled.

### Rescoped implementation (what this task now does)

0. **No CLI invocations.** Invocation records may only be read, never added: the
   pilot's `runs/pilot/invocations.jsonl` must still hold 79 records at the end.
   Use a scratch copy for anything exploratory.
1. **`aggregate.py`** (new, stdlib, public numbers only). It reads the public
   `runs/pilot/{sessions,trials,scores}.json[l]` plus `matrix.json`, reuses
   `validate.summarise()` and `harness.judgments_by_trial()`, and writes
   `results/summary.json` with:
   - **Final record per cell.** For each `cell_id`, take the trials of its last
     launched session. The pilot's 8 `infra_failure:setup_failed` and 2
     `not_run:circuit_open` rows, which were re-run with `--resume`, are reported
     under `superseded`, never in a denominator.
   - Per cell, per agent, per variant, per condition and per scenario:
     - compliance and **overall success side by side**, never one without the
       other;
     - the sensitivity lines;
     - outcome-class counts;
     - Wilson intervals labelled small-sample (n = 1 makes them trivially wide;
       report them anyway).
   - Conditional quality over valid answers, per judge:
     - rubric dimensions, option coverage, `could_choose`, failure flags;
     - judge calibration (6/6) and disputes (8/16).
   - The persistence view for the 2 repeated conversations: each answer against
     the fresh answer of the same agent × variant × scenario where one exists. The
     pilot has fresh answers only for `file_selection`; say so.
   - Mechanics covariates: answer length (not scored), greeting and
     capture-before-greeting flags, web-search counts, instruction length per
     variant.
   - **Gap list:** every `harness.expand_matrix(matrix.json)` cell, as
     `not_run:budget_declined`, with counts by block.
   - Writes through a whitelisted record (keys asserted by the test). Paired with
     `check_public.py`.
2. **Independent audit, all 16 answers.**
   - Read each answer from the private store, with the screen, the task file and
     the `reference.md`. Score it against `rubric.md` blind to both judges'
     numbers first, then compare.
   - For each answer: my scores, which judge I side with per disputed dimension,
     and why (factual-correctness disputes first).
   - Private: `aidocs/shadow_q_store/audit/pilot_audit.md`, with quotes.
   - Public: `results/audit.md`, with trial ids, numbers and dispositions only.
   - Record whether the audit changes any adequacy verdict. It reports, and never
     overwrites the judges' scores.
3. **`report.md`** (public, no quotes; examples cited by trial id and store commit
   in the private `report_examples.md`):
   - **Setup:** frozen baseline, the variants and their hypotheses, agents and
     versions, the matrix as frozen versus what ran.
   - **Results:** what the pilot measured, as observations.
   - **Answers to the acceptance questions:**
     - concise-intent sufficiency and consistency: not determinable at n = 1;
     - agent: an observed difference in style and length; whether it reflects
       quality is disputed between the judges, and the audit says which way;
     - context and repeated turns: one observation each, not evidence.
   - **Hypotheses**, labelled.
   - **Recommendation:** the simplest definition the evidence supports. Expected:
     keep the current definition, because nothing measured justifies a change.
     Stated with its uncertainty.
   - **Unmet acceptance line**, with the reason.
   - **Targeted follow-up:** t2187, with its re-derivable cost estimate.
4. **`matrix.json`:** set `status` to "NOT RUN: main-run budget declined by the
   user on 2026-11-03 (t2179_2); see report.md". Cells and limits are unchanged.
   Update `README.md`'s file table.
5. **Tests** (`tests/test_shadow_q_harness.py`, offline):
   - final-record-per-cell drops superseded rows;
   - the gap list equals the `expand_matrix` count (196 sessions / 220 slots);
   - overall success is never emitted without compliance;
   - the summary record carries no non-whitelisted key.
6. **Commits:**
   - the store first, path-scoped
     (`git -C <aitasks_go> add aidocs/shadow_q_store/audit aidocs/shadow_q_store/report_examples.md`,
     then `commit -- aidocs/shadow_q_store`);
   - ask before pushing aitasks_go;
   - then `check_public.py --staged` and the public path-scoped commit
     (`test: … (t2179_2)`).

### Rescoped verification

- `results/summary.json` accounts for all 16 final pilot slots plus the superseded
  rows, and the gap list covers all 196 frozen sessions / 220 slots.
- The audit covers 16/16 answers, with every disagreement dispositioned in writing.
- `report.md` answers each acceptance question and states the unmet line.
- `runs/pilot/invocations.jsonl` still holds 79 records.
- The tests pass; `check_public.py --staged` passes.
- Nothing changes under `.claude/skills/` or `.agents/`.

## Implementation (original main-run design; NOT executed, carried by t2186/t2187)

1. **Approval gate, before any spend.** Present this plan's re-checked projection,
   plus `pilot_report.md` and `matrix.json`, and get explicit approval of the
   matrix and thresholds, or of a stated reduction. **2026-11-03: declined. The
   task stopped here.** If declined again, stop with the harness intact.
1b. **Close the harness gaps** above (no spend). Run the offline tests. Then run
   the model-free `preflight` on the new batch.
2. Run the web-off probe (1 invocation). Then run a startup `smoke` on a **new batch
   name** (for example `main1`): the budget journal and its baseline are per batch.
   Then run the approved matrix in the background with `harness.py main --batch main1`.
   - Re-resolve agents at run time. If a resolved model or CLI version differs
     from the pilot's (`claude-opus-5-5`, Claude Code 2.1.317; `gpt-6.1-sol`,
     codex-cli 0.166.0), record it and ask before running.
   - Never substitute another model. Report any unavailable cell or client
     explicitly.
   - **Between subjects and judging:** if the actual subject spend plus the
     projected judging spend exceeds the approved thresholds, stop and ask.
3. **Blinded judging** of every valid answer by both judges, controls first, for
   all 4 scenarios (`harness.py judge --batch main1`).
   - Then an independent audit of a stratified sample (high, low, borderline,
     disputed; ≥ 2 per agent × variant) by the implementing agent, reading raw
     outputs against the rubric. Prioritise factual-correctness disputes: the
     Codex judge was much stricter there in the pilot, with 8 of 16 answers
     disputed.
   - Size the sample for about half the answers being disputed.
   - The audit with quotes goes to the store (`audit/main1_audit.md`). A
     numbers-and-ids `results/audit.md` goes public. Disagreements are resolved in
     writing, never silently.
4. **`aggregate.py`** writes `results/summary.json` (public, numbers only). It
   reuses `validate.summarise()` per cell and per marginal, and joins
   `runs/<B>/scores.json`. It reports two metrics side by side for every cell, and
   never one without the other:
   - **Overall success** = trials that are `valid` **and** adequate (every
     calibrated judgment has the failure flag false, and mean `could_choose` ≥ 2),
     divided by **all attempted trials minus `infra_failure`, `uncertain_*` and
     `not_run`**.
     - `subject_noncompliance` counts as failure. That includes
       `variant_not_loaded`, which is broken out because it says nothing about the
       wording.
     - A sensitivity line repeats the rate with every attempted trial in the
       denominator.
   - **Conditional explanation quality** = rubric distributions over `valid`
     responses only, labelled as conditional on compliance.
   - The recommendation rests on overall success first, with conditional quality
     as the second criterion.
   - Per-cell counts of every outcome class, an *under-sampled* flag for any cell
     with fewer classifiable trials than its frozen rep count, and a gap list
     against `expand_matrix()`.
   - Per-agent, per-variant, per-scenario and per-condition distributions.
   - Failure frequency with Wilson intervals, stated as small-sample.
   - The persistence comparison for repeated `>q`: each repeated answer against
     the fresh answers to the same scenario × agent × variant, with position and
     scenario effects reported separately.
   - Latency, tokens and cost, instruction length, web-search item counts, and
     the Claude startup-behaviour covariate (greeting skipped and proactive
     pre-explanation; kept as real behaviour and reported).
5. **`report.md`** (public, numbers and mechanics, no quotes). It answers the
   task's questions directly:
   - Is concise intent sufficient?
   - Does explicit wording materially improve consistency?
   - Do agent, context or repeated turns make a difference?
   - It gives the simplest reliable definition, which may be "keep current" or
     "none reliable".
   - It separates observations from hypotheses, and covers uncertainties and a
     targeted follow-up experiment.
   - Representative outputs and counterexamples live in the store
     (`report_examples.md`). The report cites them by trial id and store commit.
6. **Durable storage.**
   - The store gets path-scoped commits: `git -C <root> commit -- aidocs/shadow_q_store`.
     The raw main run is ≈ 40 MB, mostly stream JSONL. Commit it loose so that
     `harness.py classify` keeps working.
   - Push aitasks_go only with the user's confirmation.
   - Public commits are path-scoped, after `check_public.py --staged`.
   - An adoption follow-up task is suggested only, never applied. The production
     `>q` definition and anything under `.claude/skills/` or `.agents/` stay
     untouched.

## Step 9

Archive via the normal Step 9 (Post-Implementation) once the report lands. The parent
t2179 auto-archives with its last child.

## Verification

- `results/summary.json` covers every frozen matrix cell, with counts equal to the
  frozen (or approved, reduced) matrix or an explicit gap list.
- `report.md` answers each acceptance question.
- `python3 tests/test_shadow_q_harness.py` passes, including the new main-run tests.
- The web-off probe shows zero `web_search` items.
- `check_public.py --staged` passes before each public commit.
- `git diff --stat` shows nothing under `.claude/skills/` or `.agents/`.

## Risk

### Code-health risk: low
- Step 1b adds a `main` command, a `limits.json` `main` block, a web flag,
  `aggregate.py` and tests. All of it sits in the isolated
  `aidocs/benchmarks/shadow_q/` directory plus its one offline test module.
  Production skills are untouched.
  · severity: low · → mitigation: none (contained by design)

### Goal-achievement risk: high
- The main-run budget was declined on 2026-11-03. The re-checked projection
  (≈ $164 / ≈ 11.5M) exceeds the frozen thresholds. Until a spend is approved, the
  matrix, scores, audit and report, and with them the task's acceptance, cannot be
  produced.
  · severity: high · → mitigation: none (a user budget decision; the cost levers are
  listed in the verification record)
- **Rescope (pilot-evidence closure):** n = 1 per cell cannot answer the
  wording-consistency questions, and the "repeated runs for both agents" acceptance
  line stays unmet. The risk is that the report overstates the pilot.
  · severity: high (accepted by the user's rescope) · → mitigation: none (addressed
  in design: the report answers "not determinable" where it is, keeps observations
  apart from evidence, records the unmet line, and names t2187 as the targeted
  follow-up)
- Headless replay may not reproduce the interactive terse pattern. In the pilot,
  Claude under v1 already explained at length, so its baseline may be at ceiling.
  · severity: medium · → mitigation: none (addressed in design: real clients and
  instruction stack, the repeated-`>q` condition, and a fidelity observation that
  may come out inconclusive)
- LLM judge validity: self-preference, length bias, and strictness disagreement
  (8 of 16 pilot answers disputed).
  · severity: medium · → mitigation: none (addressed in design: blinding,
  cross-agent judges, per-scenario calibration controls, and an audit sized for the
  disputes)
- Disabling Codex web search changes its condition relative to the pilot, and the
  flag's effect cannot be read from the rollout.
  · severity: low · → mitigation: none (addressed in design: a one-invocation
  behavioural probe before the run, and `web_search` item counts reported)
- Repeated-condition evidence could be confounded with scenario order.
  · severity: low (residual) · → mitigation: none (addressed in design: every `>q`
  answer is scored, Latin-square rotation, and comparison with fresh answers to the
  same scenario)
