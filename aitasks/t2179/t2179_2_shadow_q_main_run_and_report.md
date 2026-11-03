---
priority: medium
effort: high
depends: [t2179_1]
issue_type: test
status: Ready
labels: [shadow, skills, testing]
gates: [risk_evaluated]
anchor: 2179
created_at: 2026-11-03 08:35
updated_at: 2026-11-03 08:35
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

## Key Files to Create/Modify

Under `aidocs/benchmarks/shadow_q/`:
- `runs/main/…`: raw outputs and per-turn JSONL from the main matrix.
- `results/judgements*.jsonl`, `audit.md`, `aggregate.py`, `results/summary.json`.
- `report.md`: the comparison report and the evidence-based recommendation.
- Optionally a `runs.tar.zst` bundle registered with `ait artifact create 2179 … --kind report`.

## Reference Files for Patterns

- `aidocs/benchmarks/shadow_q/` as left by t2179_1 (harness.py, validate.py,
  judge.py, rubric.md, matrix.json, limits.json, pilot_report.md).
- `aiplans/archived/p2179/p2179_1_*.md`: the archived sibling plan (primary context).
- Original task requirements: `aitasks/t2179_shadow_q_definition_experiments.md`.

## Implementation Plan

Follow `aiplans/p2179/p2179_2_shadow_q_main_run_and_report.md`:
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

- `results/summary.json` covers every frozen matrix cell, with counts equal to the
  frozen matrix or an explicit gap list.
- `report.md` answers: is concise intent sufficient; does explicit wording
  materially improve consistency; do agent, context or repeated turns matter. It
  gives the simplest reliable definition, which may be "keep current" or "none
  reliable".
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
