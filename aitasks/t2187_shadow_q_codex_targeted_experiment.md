---
priority: medium
effort: medium
depends: [2186]
issue_type: test
status: Postponed
labels: [shadow, skills, testing]
gates: [risk_evaluated]
anchor: 2179
created_at: 2026-11-03 18:30
updated_at: 2026-11-03 18:30
---

## Context

t2179 asks whether a concise intent-based definition of the aitask-shadow `>q` command is enough, or
whether more explicit wording makes the decision help more reliable. t2179_1 built the harness and ran a
pilot. **t2179_2's main run was declined at the approval gate on 2026-11-03** (≈ $164 Claude /
≈ 11.5M Codex tokens), so t2179_2 was closed on the pilot's evidence. Its acceptance line "completed
repeated runs for both actual default agents" is recorded as **unmet**.

The pilot ran n = 1 per cell, so it is not evidence. It does suggest where a wording effect could exist:
- **Codex under v1** answered in 800-1,100 chars, recommendation first, one line per option. This is the
  closest match to the originating terse pattern. The only answer both judges flagged ("recommends without
  explaining the alternative") was Codex · v1 · minimal context.
- **Claude** explained every option at length under every variant, v1 included, so its baseline may already
  be at ceiling.

This task is the targeted experiment that t2179_2's report names. **It stays Postponed until the user decides
to spend.**

## Goal

With ≥ 5 independent fresh sessions per cell, determine whether **v2 (concise intent)** gives Codex a higher
*overall success* than **v1 (baseline)**, and optionally whether **v3 (explicit semantics)** does. Overall
success means a valid answer that is also adequate (see `validate.summarise` and the t2179 rubric).

## Design (re-check every number at the approval gate)

- **Subjects:** Codex only, the shadow agent resolved at run time (`aitask_codeagent.sh resolve shadow`;
  `codex/gpt6_1_sol` in the pilot). Never substitute a model.
- **Cells:** fresh condition × {v1, v2} (optionally + v3) × the 3 AUQ scenarios (`file_selection`,
  `runnable_examples`, `go_versions`) × 5 reps.
- **Optional:** the repeated-`>q` condition (v1, v2 × Latin orders ABC/BCA/CAB) for the persistence
  question.
- **Optional Claude ceiling check:** v1 × 3 scenarios × 5 reps, run only if separately approved. It tests
  the pilot's "Claude is already at ceiling" hypothesis.
- **Web search disabled** for Codex (user decision 2026-11-03), as `-c web_search="disabled"` on subject and
  judge calls. A one-invocation probe must first show zero `web_search` items under the flag.
- **Judging:** both judges plus per-scenario calibration controls, the pilot-proven method. Or use the
  cheaper calibrated judging mode from t2186, if it lands with evidence that it agrees with two-judge
  scoring.
- **Frozen inputs:** reuse the frozen variants, fixtures (private aitasks_go store, pinned by
  `fixtures/MANIFEST.json`), rubric and judge prompt from `aidocs/benchmarks/shadow_q/`. Use a **new batch
  name**: the budget journal is per batch.

**Budget estimate**, from pilot means (Codex ≈ 71.7k non-cached tokens per fresh session; a task-aware
judge call ≈ $0.28 Claude / ≈ 18k Codex tokens):

| scope | sessions | Claude (judge) | Codex tokens |
|---|---|---|---|
| v1 + v2 | 30 | ≈ $10 | ≈ 2.8M |
| v1 + v2 + v3 | 45 | ≈ $14 | ≈ 4.2M |
| + Claude ceiling check | +15 | +≈ $18 | +≈ 0.3M |

**Approval gate first:** present the re-derived projection and get explicit approval before any paid call.

## Dependency

Depends on **t2186** (generic agent-prompt eval harness), which provides:
- the matrix-run command with `--resume` and per-run limit blocks;
- the web flag and its probe;
- a durable answer index;
- final-record-per-cell aggregation and the cost features.

**Fallback:** if this experiment is wanted before t2186 lands, drop the dependency and close only the
"Harness gaps a future main run must close first" list from the archived t2179_2 plan
(`aiplans/archived/p2179/p2179_2_*.md`) inside this task.

## Deliverables

- Raw outputs, answer texts, judge rationales and audit quotes go to the private store
  (`./ait projects resolve aitasks_go` → `aidocs/shadow_q_store/`), in path-scoped commits only. Push only
  with the user's confirmation.
- Numbers-only results go to `aidocs/benchmarks/shadow_q/`: `runs/<batch>/`, a `results/` summary, and an
  addendum to `report.md` that answers "does v2 (or v3) materially improve Codex's overall success over v1?"
  with small-sample intervals.
- Run `check_public.py --staged` before every public commit.
- An independent stratified audit (high, low, borderline, disputed), prioritising factual-correctness
  disputes.
- **The production `>q` definition is not changed.** Suggest an adoption follow-up only if the evidence
  supports one.

## Pointers

- `aidocs/benchmarks/shadow_q/report.md` and `pilot_report.md`.
- `aiplans/archived/p2179/`: the t2179_1 harness record, and t2179_2's re-checked projection, cost levers and
  harness gaps.
- `aitasks/t2186_generic_agent_prompt_eval_harness.md`.
