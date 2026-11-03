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
