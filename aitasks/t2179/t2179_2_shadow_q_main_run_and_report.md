---
priority: medium
effort: medium
depends: [t2179_1]
issue_type: test
status: Ready
labels: [shadow, skills, testing]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
anchor: 2179
created_at: 2026-11-03 08:35
updated_at: 2026-11-03 18:35
---

## Context

Child 2 of t2179 (shadow `>q` definition experiments). Depends on t2179_1, which
builds the harness under `aidocs/benchmarks/shadow_q/`, freezes four `>q` variants
(v1 baseline, v2 concise intent, v3 explicit semantics without layout,
v4 prescriptive), fixtures, rubric, judge prompt, limits and a proposed
`matrix.json`, and runs only a bounded pilot. Its `pilot_report.md` gives the
measured cost/tokens/latency and the projected main-run total.

The user chose **"pilot only, then ask"** for the budget. So this child MUST NOT
spend on the main matrix until the user explicitly approves the projection (or a
stated reduction) at its start.

The full design is in the parent plan `aiplans/p2179_shadow_q_definition_experiments.md`
and in this child's plan `aiplans/p2179/p2179_2_shadow_q_main_run_and_report.md`.
Read both, plus the archived t2179_1 plan, which is the primary record of what was
actually built and any harness deviations.

## Rescope (2026-11-03, user decisions): pilot-evidence closure, no paid calls

At the approval gate on 2026-11-03 the user **declined the main-run budget**. The
re-checked projection was ≈ $164 Claude / ≈ 11.5M Codex tokens, against frozen
thresholds of $145 / 10.5M. The user then chose to **finish this task from
t2179_1's pilot results, with no further paid runs.** This section supersedes the
main-run steps below.

- **No CLI invocation of any kind** (subject or judge). Everything is built from
  the saved pilot batch: the public `runs/pilot/`, plus the private store
  `runs/pilot/` and `judging/pilot/`.
- **Independent audit of all 16 pilot answers** by the implementing agent, against
  `rubric.md`, read from the private store. That is every answer, because 8 of 16
  are disputed between the judges.
  - Prioritise factual-correctness disputes: the Codex judge was much stricter.
  - Resolve each disagreement in writing.
  - Quotes go to the private store only.
- **Numbers-only `results/summary.json`:**
  - pilot cells with compliance and overall success side by side, plus
    conditional quality per judge;
  - the final record per cell (the pilot's superseded never-launched rows are
    reported separately);
  - a **gap list**: every frozen `matrix.json` cell, marked
    `not_run:budget_declined`.
- **`report.md`** answers each acceptance question directly:
  - "not determinable at n = 1" where that is the honest answer (concise-intent
    sufficiency, consistency);
  - the pilot observations as observations, never as evidence (Codex v1 terse and
    recommendation-first; Claude explaining at length under every variant; the
    single failure flag on Codex · v1 · minimal);
  - hypotheses kept separate.
  - The recommendation follows the evidence. The expected outcome is "keep the
    current definition: nothing measured justifies a change".
  - It names the targeted follow-up: **t2187**, a Codex-only v1 vs v2 (± v3)
    experiment, Postponed until the user approves a spend.
- **Acceptance gap, recorded and not redefined:** the parent's line "completed
  repeated runs for both actual default agents" is **unmet**, because of the user's
  budget decision.
  - The report and the archived plan state this.
  - t2187 carries the Codex side.
  - The Claude side is covered only by t2187's optional ceiling check.
- **Web access decision** (for any later run): disabled for both agents.
- **Related follow-ups created 2026-11-03:**
  - **t2186:** a generic agent-prompt eval harness (dev tooling under
    `aidocs/benchmarks/prompt_eval/`). It absorbs the harness gaps listed in this
    task's plan.
  - **t2187:** the targeted Codex experiment, which depends on t2186.

## Key Files to Create/Modify (rescoped)

Under `aidocs/benchmarks/shadow_q/` (public, numbers only):
- `aggregate.py`: pilot aggregation with final-record-per-cell and the frozen-matrix gap list.
- `results/summary.json`, `results/audit.md` (trial ids and scores, no quotes), `report.md`.
- `matrix.json`: `status` updated to record "not run: budget declined 2026-11-03" (cells unchanged).
- `README.md`: list the new files.
- `tests/test_shadow_q_harness.py`: offline tests for `aggregate.py`.

In the private aitasks_go store `aidocs/shadow_q_store/`:
- `audit/pilot_audit.md`: per-answer reading with quotes.
- `report_examples.md`: representative outputs and counterexamples cited by `report.md`.

(The original main-run file list: `runs/main/…`, judgements, a `runs.tar.zst` bundle. It is
not produced under the rescope.)

## Reference Files for Patterns

- `aidocs/benchmarks/shadow_q/` as left by t2179_1 (harness.py, validate.py,
  judge.py, rubric.md, matrix.json, limits.json, pilot_report.md).
- `aiplans/archived/p2179/p2179_1_*.md`: the archived sibling plan (primary context).
- Original task requirements: `aitasks/t2179_shadow_q_definition_experiments.md`.

## Implementation Plan

**Superseded by the Rescope above.** Follow the "Rescope" section of
`aiplans/p2179/p2179_2_shadow_q_main_run_and_report.md`. The original main-run steps
are kept below for the record:
1. Approval gate before any spend.
2. Run the frozen matrix (background), re-resolving agents at run time, with no
   model substitution.
3. Blinded judging with both judges plus controls, then an independent stratified
   audit (`audit.md`).
4. Aggregate: overall success (denominator = attempted trials minus infra_failure
   and uncertain_load) side by side with conditional quality (valid only), plus the
   persistence comparison for repeated `>q`.
5. Write the report, answering the acceptance questions directly.
6. Durable storage, and an adoption follow-up suggested (not applied).

## Verification Steps

- `results/summary.json` accounts for every pilot `>q` slot (16 final valid answers,
  plus the superseded never-launched rows reported separately). It also lists every
  frozen `matrix.json` cell in the gap list, as `not_run:budget_declined`.
- The audit covers all 16 pilot answers, with every judge disagreement resolved in
  writing.
- `report.md` answers each question: is concise intent sufficient; does explicit
  wording materially improve consistency; do agent, context or repeated turns
  matter.
  - It gives the simplest reliable definition the evidence supports, which may be
    "keep current" or "none reliable".
  - It states the unmet acceptance line, and points to t2187.
- The pilot invocation total is unchanged (79): no CLI was called by this task.
- `python3 tests/test_shadow_q_harness.py` passes.
- `check_public.py --staged` passes before the public commit.
- No change under `.claude/skills/` or `.agents/`.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2179_1** id=2026-11-03T15:32:28Z.3351765a05fe162208dbc102 from=t2179_1 from_verified=yes at=2026-11-03T15:32:28Z base=2bdd5d45ad43388ab469245d481e253847d1c78a base_branch=main dirty=no host=omg16
>
> | From t2179_1 (harness + pilot, committed at 6930f54e2). Advisory context; your own plan and gates decide what to do with it.
> | 
> | 1. Public/private split (a user decision taken during t2179_1 verification). aitasks is PUBLIC and aitasks_go is PRIVATE.
> |    - Raw runs, per-answer judge text, quotes, fixtures and the blinding map live in the aitasks_go store `aidocs/shadow_q_store/` (resolve with `./ait projects resolve aitasks_go`). It has 4 local commits, ending at 3fcf4bd2, and was NOT pushed as of this note.
> |    - Your plan's "raw runs, scores and the audit committed under aidocs/benchmarks/shadow_q/runs|results/" no longer fits as written. Only numbers-only records belong there (PublicSink whitelist).
> |    - Run `python3 aidocs/benchmarks/shadow_q/check_public.py --staged` before every public commit.
> | 2. Provenance correction. Your plan cites aitasks_go `b523a6bc` for t60_2. That commit holds only the code and instruction files; t60_2 is on the aitask-data branch. The pre-decision task body is data `e022bc0`. Plan `d55e17a` already records the user's decisions, so it is used for measured facts only. See the store's fixtures/PROVENANCE.md.
> | 3. Start from the approval gate: `aidocs/benchmarks/shadow_q/pilot_report.md` plus `matrix.json`.
> |    - The main-run projection is 872 invocations, about $123 Claude and about 9.0M Codex tokens. It was made BEFORE the judge prompt gained the task file (roughly 6-8k extra tokens per judge call), so re-check the thresholds.
> |    - Open decision: Codex web-searched in every fresh >q turn; Claude has no web tools. The pilot report recommends disabling web access for both.
> | 4. Mechanics to reuse:
> |    - Use a NEW batch name: the budget journal and its baseline are per batch.
> |    - `harness.py summary` gives compliance_rate and overall_success (valid AND adequate, from calibrated judgments) side by side.
> |    - `harness.py classify` re-validates the saved raw streams offline.
> |    - Judges disagreed on 8 of 16 pilot answers, mostly on factual_correctness, where the Codex judge is much stricter. Size the audit for that.

> **👁 note:read** id=2026-11-03T15:55:35Z.ccb118d100c0912fcf2049fa by=t2179_2 at=2026-11-03T15:55:35Z mode=explicit ids=2026-11-03T15:32:28Z.3351765a05fe162208dbc102
