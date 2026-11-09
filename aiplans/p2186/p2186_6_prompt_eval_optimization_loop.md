---
Task: t2186_6_prompt_eval_optimization_loop.md
Parent Task: aitasks/t2186_generic_agent_prompt_eval_harness.md
Sibling Tasks: aitasks/t2186/t2186_1_*.md, aitasks/t2186/t2186_2_*.md, aitasks/t2186/t2186_3_*.md, aitasks/t2186/t2186_4_*.md, aitasks/t2186/t2186_5_*.md, aitasks/t2186/t2186_7_*.md
Archived Sibling Plans: aiplans/archived/p2186/p2186_*_*.md
Base branch: main
Output branch: main
---

# t2186_6: Prompt-optimization loop: analyse, propose, evaluate, confirm on held-out

Child 6 of t2186. The parent plan is `aiplans/p2186_generic_agent_prompt_eval_harness.md`; the task file carries the shared
constraints, the facts established during exploration and the target layout. Read both. Treat any deviation recorded in an archived sibling plan's Final Implementation Notes as authoritative over this plan.

## Context

Child 6 of t2186. It builds the prompt-optimization loop:
- analyse a batch's failures;
- propose candidate variants (a gated proposer call, or hand-written);
- evaluate them on a small budget over the tuning scenarios;
- confirm on pre-registered held-out scenarios, with an **achievable** selection rule.

Every spend is approval-gated. The loop never edits a production skill: adoption is always a
separately scoped task.

## Implementation

### `prompt_eval_optimization_loop` (small gated run optional)

1. A pre-registered `scenario_split` (`tuning`, `heldout`) and `selection` rule, in the spec,
   bound into the digest before the first optimization batch. The rule reads **only t2186_3's
   decision score and coverage**, for candidates and baseline alike, and it must be
   **achievable**. A candidate's interval is never measured against the baseline's *observed*
   score: the Wilson lower bound of n/n is n/(n+z²) < 1, so a baseline scoring 1.0 could never
   be matched. A candidate qualifies on held-out when all three hold:
   - **absolute reliability:** its decision score's one-sided Wilson lower bound ≥
     `reliability_target` (pre-registered, < 1; proposed 0.8 at z = 1.645);
   - **non-inferiority:** the lower bound of the difference (candidate − baseline), by
     Newcombe's hybrid score interval built from the two Wilson intervals (stdlib), is ≥ −δ
     (pre-registered margin; proposed δ = 0.15, one-sided z = 1.645). For a perfect baseline and
     a perfect candidate at n each, the bound is −z²/(n+z²), which meets −0.15 from n = 16;
   - **coverage:** ≥ `min_coverage` for both the candidate and the baseline.

   Among qualifiers, the shortest by word count wins. "None reliable" is a valid outcome, but
   never a forced one.
   - **Feasibility, checked before any spend:** `plan optimize confirm` prints the smallest
     held-out n per arm at which an all-success candidate could meet both bounds against the
     baseline's observed score. It refuses to project a budget below that n.
   - The spec loader refuses a `reliability_target` (and child 5's stopping `target`) ≥ 1, or one
     that `max_reps` all-success can never reach.

   The historical rates appear in the report as context only.
2. `optimize analyse --batch B` — failure summary (outcome classes, inadequate answers by failed
   dimension or flag): public numbers, private failure brief with quotes.
3. `optimize propose --analysis <a> --n K` — a gated proposer call through a real CLI (the frozen
   span + the failure brief + a hypothesis template) or hand-written candidates; every candidate
   passes the span-substitution guard and the leak check, and lands in the private store first;
   it is promoted to the public `variants/` only after the leak check.
4. `optimize evaluate` (tuning scenarios, sequential sampling from child 5) and `optimize confirm`
   (held-out scenarios, the pre-registered criterion), both gated.
5. Report `optimize_report.json` + `.md`; adoption is a suggested, separately scoped task only;
   the loop never writes outside its spec dir and store (tested).
6. **Tests** (`tests/test_prompt_eval_optimize.py`): the whole loop under fake CLIs; a candidate
   that changes text outside the span is refused; a held-out scenario never reaches propose or
   evaluate; selection ties and the "none reliable" outcome. **Exclusion regression:** a mostly
   incomplete candidate (1 complete + 9 `uncertain_report`) competes with a consistently complete
   one (8 `valid` + 2 noncompliant). Its historical `compliance_rate` (1/1) beats the complete
   candidate's (8/10), yet the complete candidate is selected; the incomplete one is never
   selected, and is "insufficient coverage". The same holds when the incomplete candidate is the
   shorter one.

   **Perfect-baseline regression** (baseline 30/30 with full coverage, proposed defaults):
   - a shorter candidate at 30/30 with full coverage **qualifies and is selected**. Its absolute
     lower bound is 30/32.7 ≈ 0.917; its difference bound is −2.706/32.7 ≈ −0.083 ≥ −0.15;
   - the same candidate at 5/5 **stays unselected**, as insufficient evidence. Its absolute
     lower bound is ≈ 0.65 and its difference bound ≈ −0.35;
   - the outcome is not "none reliable" merely because the baseline had zero failures;
   - the feasibility check reports n = 16 per arm for this baseline;
   - a `reliability_target` of 1.0 is refused at load.

   Optional small paid run on the cheap `aitask_note` spec, gated.

## Step 9

Archive via the normal Step 9 (Post-Implementation). The parent t2186 auto-archives with its last child.

## Verification

- The loop runs end-to-end offline; held-out scenarios are never used before confirm.
- The mostly incomplete candidate never wins on exclusions; the perfect-baseline regression
  passes (selectable with sufficient evidence, unselected with insufficient).
- The tests and `run_all_python_tests.sh --test-dir` are green; `check-public --staged` passes;
  `git diff --stat` shows nothing under `.claude/skills/`, `.agents/`, `.opencode/` or
  `aidocs/benchmarks/shadow_q/`.
- Any paid step runs only after a recorded approval of its printed manifest.

## Risk

### Code-health risk: low
- New module plus spec fields. · severity: low · → mitigation: none (contained by design)

### Goal-achievement risk: medium
- Overfitting the tuning scenarios; few scenarios mean low power. · severity: medium
  · → mitigation: none (addressed in design: a pre-registered held-out split and selection rule;
  the report states the power)
- A selection rule could be unsatisfiable (a perfect baseline) or exclusion-inflated.
  · severity: high (residual low) · → mitigation: none (addressed in design: an absolute target
  < 1, Newcombe non-inferiority, a feasibility check, the decision score and coverage,
  regressions)
