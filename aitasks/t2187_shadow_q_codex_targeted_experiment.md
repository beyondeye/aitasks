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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2333** id=2026-11-19T08:10:21Z.4bb20ed94274dc2f09878b89 from=t2333 from_verified=yes at=2026-11-19T08:10:21Z base=c443f811efd914e808d99dce252774f7a6f398de base_branch=main dirty=yes host=omg16
>
> | The shadow default model changed (advisory; checked against the tree at this note's base commit).
> | 
> | - t2333 (commit c443f811e) moved the `shadow` and `discuss` defaults from `codex/gpt6_1_sol` to `codex/gpt6_2_sol`, in both `seed/codeagent_config.json` and this project's `aitasks/metadata/codeagent_config.json`.
> | - Your design resolves the subject at run time (`aitask_codeagent.sh resolve shadow`). A re-run will therefore test `gpt-6.2-sol`, not the `gpt-6.1-sol` the pilot used, so its numbers would not be directly comparable with the pilot's unless that difference is accounted for.
> | - `codex/gpt6_1_sol` is still registered, now marked as superseded by `gpt6_2_sol`. If the experiment needs pilot parity, it can be pinned explicitly with `--agent-string codex/gpt6_1_sol`.

> **✉ note:t2368** id=2026-11-27T06:26:47Z.e1228dd5effe0006e25e5f86 from=t2368 from_verified=yes at=2026-11-27T06:26:47Z base=eec4dee54f471ccaab41adeaa84a8c67a916627b base_branch=main dirty=yes host=omg16
>
> | Advisory context from t2368 (landed as eec4dee54 on main, 2026-11-27). Check it against the tree before relying on it.
> | 
> | 1. The production shadow `>q` wording changed, and a second command was added.
> |    - `>q` is now a short answer: what is being decided, the followed agent's recommendation and its reason when it gives one, then the shadow's own recommendation. It asks for no pros and cons lists.
> |    - `>qd` is new: the full comparison, with a Pros list and a Cons list per substantive option, run only when a comparison is asked for.
> |    - So `aidocs/benchmarks/shadow_q/frozen/` and `variants/v1_baseline.md` no longer describe production, and a "v1 vs v2" comparison of one `>q` bullet no longer matches how decision help is split. `frozen/` and `v1`-`v4` were left untouched on purpose. `variants/v5_quick.md` is the production `>q` bullet; it is not in `VARIANTS`.
> | 
> | 2. A free measurement exists now: `aidocs/benchmarks/shadow_q/scan_sessions.py` reads the local Codex (or Claude) session logs and prints counts only, per shortcode, model and skill text (old / new / unknown). It answers part of the wording question without spend. Numbers at t2368, 2026-10 and 2026-11, on real use: `>q` gave no separate pros and cons lists in 404 answers on gpt-6.1-sol and 45 on gpt-6.2-sol (old wording). `>pd` had labelled `Pros:` / `Cons:` lines in 48 of 50 answers on gpt-6.1-sol and in 0 of 7 on gpt-6.2-sol.
> | 
> | 3. Hypothesis, not proven: Codex ships model-specific base instructions, and the gpt-6.2-sol text (27,750 chars in the sessions measured, carried by no other model's sessions) contains "Do not use colons to introduce explanations or examples, including after list labels" and "Don't use lead-in phrases or sentences that label a paragraph". That may be why 6.2 dropped the `Pros:` / `Cons:` lines. t2368 did not test the colon alone. What it did measure: with two headed lists stated as the answer's format, no colon, gpt-6.2-sol produced them in 1 of 1 `>qd` and 1 of 1 `>pd` replay answers, and gpt-6.1-sol likewise.
> | 
> | 4. Harness changes you would meet: `Experiment.turn_prompt` (default `>q`) sets what non-startup turns send; the validator has turn kinds `q` / `qd` / `pd`; `require_manifest` now checks the shared inputs plus only the fixtures of the scenarios a run names; a fifth fixture `workflow_menu` exists in the private store (aitasks_go commit 413dcf5, local and not pushed when this note was written) with its own `fixtures/MANIFEST_workflow_menu.json`. The pilot cell set, `VARIANTS` and `fixtures/MANIFEST.json` are unchanged.
> | 
> | 5. Cost data point: a fresh gpt-6.2-sol cell (startup turn plus one shortcode turn, effort high, Codex CLI 0.172.0) used about 90k non-cached tokens on average over 10 cells, against about 68k per cell in the gpt-6.1-sol pilot.
> | 
> | 6. t2376 was created for a pre-existing harness defect: `Budget` locks reservations in-process only, so two harness commands running at once on one batch can exceed the invocation cap.
