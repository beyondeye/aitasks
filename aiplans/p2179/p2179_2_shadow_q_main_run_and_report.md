---
Task: t2179_2_shadow_q_main_run_and_report.md
Parent Task: aitasks/t2179_shadow_q_definition_experiments.md
Sibling Tasks: aitasks/t2179/t2179_1_*.md
Archived Sibling Plans: aiplans/archived/p2179/p2179_*_*.md
Base branch: main
Output branch: main
---

# t2179_2: Shadow `>q` main run, blinded scoring, audit and report

Child 2 of t2179. The parent plan is `aiplans/p2179_shadow_q_definition_experiments.md`.
The primary record of what was actually built is the archived t2179_1 plan. Read it
first, and treat any harness deviation recorded there as authoritative over this
plan's assumptions.

## Context (from parent)

Repeated `>q` answers from the shadow agent (seen while it was shadowing aitasks_go
t60_2) jumped straight to a recommendation and gave little explanation of the
choice or of the options' trade-offs. That happened even though the skill already
asks for that explanation. The question is empirical: is a concise statement of
intent enough, or does more explicit wording make answers more consistent, and
does that differ by agent, by context and across repeated turns?

**User decisions taken during planning:**
- **Budget: pilot only, then ask.** Build the harness and run only the pilot. The
  main matrix is spent **only after the user explicitly approves the measured
  numbers.**
- **Structure: two child tasks.** t2179_1 covers the harness, frozen variants,
  fixtures, rubric and the pilot, ending at a freeze point. t2179_2 covers the main
  matrix, blinded scoring and audit, and the report with its recommendation.

The production `>q` definition is **not** changed by either child. Adopting a
wording is a separate follow-up, scoped only after the findings.

## Facts established during exploration (for the children)

- **Authoring source:** `.claude/skills/aitask-shadow/SKILL.md.j2`. The `>q` bullet
  is lines 281-300 at HEAD `42b547c67`, with steps 1-5 in the bullet.
  - The two `SKILL.md` renders,
    `.claude/skills/aitask-shadow-fast-/SKILL.md` and
    `.agents/skills/aitask-shadow-fast-codex-/SKILL.md`, are byte-identical.
  - Five procedure files **differ** between the two agents' renders:
    concern-format, impl-challenge, plan-assumptions, plan-challenge and
    plan-diagnose-errors. So each agent's sandbox carries its own render tree.
  - The stubs differ too. The Claude stub (`--agent claude`) dispatches to
    `.claude/skills/aitask-shadow-<profile>-/`; the Codex stub (`--agent codex`)
    dispatches to `.agents/skills/aitask-shadow-<profile>-codex-/`. Both call
    `aitask_skill_resolve_profile.sh` and `aitask_skill_render.sh`.
  - Helpers the renders invoke: capture, context, explain_context (on the `>q`
    path), and also shadow_rejected, shadow_scope and revert_analyze (in
    sub-procedures only).
    - Stubs are provided for the `>q` path and the startup path.
    - A call to any other helper is recorded as an off-path trace event (not
      allowed in Claude's list; "command not found" in the Codex sandbox) and
      flagged by the validator.
- **Shadow profile:** `aitask_skill_resolve_profile.sh shadow` resolves to `fast`,
  through `userconfig.yaml` `default_profiles.shadow: fast`.
  `fast.yaml` sets `shadow_impl_review_tier: advanced`.
- **Agent resolution:**
  - `./.aitask-scripts/aitask_codeagent.sh resolve shadow` gives
    `codex/gpt6_1_sol` (CLI_ID `gpt-6.1-sol`).
  - The framework default is `DEFAULT_AGENT_STRING=claudecode/opus5_5` in
    `lib/agent_string.sh`.
  - `--agent-string X --dry-run invoke shadow <pane> <task>` prints the real
    launch line, for example
    `codex -c tui.* … -m gpt-6.1-sol '$aitask-shadow %5 42'` and
    `claude --model claude-opus-5-5 /aitask-shadow\ %5`.
  - Minimonitor launches through `resolve_dry_run_command(…, "shadow", …)` in
    `lib/agent_launch_utils.py`.
- **Reasoning effort is not framework-managed.** Codex takes it from
  `~/.codex/config.toml` (`model_reasoning_effort = "high"`,
  `personality = "pragmatic"`); Claude takes it from its own settings. Both must
  be recorded by the harness.
- **No headless shadow launch exists.** `claude -p` is discouraged
  (`aidocs/framework/shell_conventions.md` ~259-266), mainly because headless
  print mode is billed at a higher rate. Here it is an explicit, documented
  opt-in. `codex exec` is unused in the scripts.
- **Prior-art layout:** `aidocs/testing_engine/t1954_parser_research/`, where a
  pinned harness, fixtures, committed `results/` and a final report all live
  under `aidocs/`. `aidocs/benchmarks/` holds scripts plus result notes.
- **Originating facts:** `aitasks_go` `aitasks/t60/t60_2_m3_2g_go_test_adapter.md`
  at aitasks_go `b523a6bc`. It covers the `go/build MatchFile` cross-check, the
  `go list ./...` coverage, the go 1.26 floor versus local go 1.27.2, and the
  rule that examples without `// Output:` never run. aitasks_go has its own
  `CLAUDE.md` and `AGENTS.md`.
- Installed: Claude Code 2.1.316, codex-cli 0.166.0. There is no
  `~/.claude/CLAUDE.md` and no `~/.codex/AGENTS.md`.


## Implementation


1. **Approval gate, before any spend.** Show `pilot_report.md`'s projection and
   get explicit user approval of the matrix and budget, or of a stated
   reduction. If approval is declined, stop with the harness intact.
2. Run the frozen `matrix.json` in the background with batch metadata.
   - Report any unavailable cell or client explicitly. Never substitute another
     model.
   - Re-resolve agents at run time. If a resolved model differs from the
     pilot's, record it and ask before mixing batches.
3. Blinded judging of every output by both judges, plus the controls.
   - Then an independent audit of a stratified sample (high, low, borderline,
     disputed; ≥2 per agent × variant) by the implementing agent, reading raw
     outputs against the rubric, recorded in `audit.md`.
   - Disagreements are resolved in writing, never silently.
4. `aggregate.py` writes `results/summary.json`. It reports two metrics **side
   by side** for every cell, and never one without the other:
   - **Overall success** = trials that are `valid` **and** adequate (failure
     flag false and holistic ≥ 2), divided by **all attempted trials minus
     `infra_failure` and `uncertain_load`**.
     - `subject_noncompliance` therefore counts as failure. That includes
       `variant_not_loaded`, which is also broken out because it says nothing
       about the wording.
     - A sensitivity line repeats the rate with every attempted trial in the
       denominator, infra included.
   - **Conditional explanation quality** = rubric distributions over `valid`
     responses only, labelled as conditional on compliance.
   - The recommendation in `report.md` rests on overall success first, with
     conditional quality as the second criterion. A variant whose few valid
     answers are excellent but whose trials often fail cannot win on
     conditional quality alone.
   - Per-cell counts of every outcome class, and an *under-sampled* flag for
     any cell where infra failures or uncertain loads leave fewer than the
     frozen rep count of classifiable trials.
   - Per-agent, per-variant, per-scenario and per-condition distributions;
   - failure frequency, with intervals stated as small-sample;
   - latency, tokens and cost, and instruction length.
5. `report.md`. It answers the task's direct questions:
   - Is concise intent sufficient?
   - Does explicit wording materially improve consistency?
   - Do agent, context or repeated turns make a difference?
   - It includes representative outputs and counterexamples, separates
     observations from hypotheses, and gives the simplest reliable definition.
     That may be "keep current" or "none reliable".
   - It also covers uncertainties and any targeted follow-up experiment.
6. Durable storage:
   - raw runs, scores and the audit committed under
     `aidocs/benchmarks/shadow_q/runs|results/`;
   - a `runs.tar.zst` bundle registered with
     `ait artifact create 2179 … --kind report` if the raw size makes that
     preferable.
   - An adoption follow-up task is suggested only, never applied.


## Step 9

Archive via the normal Step 9 (Post-Implementation). The parent t2179 auto-archives with its last child.

## Verification

- t2179_2: `summary.json` covers every matrix cell, with counts equal to the
  frozen matrix or an explicit gap list. `report.md` answers each acceptance
  question.


## Risk

### Code-health risk: low
- All new code sits in an isolated `aidocs/benchmarks/shadow_q/` directory plus
  one offline test module. Production skills are untouched, and the test asserts
  that.
  · severity: low · → mitigation: none (contained by design)

### Goal-achievement risk: medium
- Headless replay (`-p`/`exec`, stubbed capture) may not reproduce the
  interactive terse pattern, so differences could reflect the harness and not
  the wording.
  · severity: medium · → mitigation: none (addressed in design — pilot fidelity
  check with an inconclusive outcome, real clients and instruction stack,
  repeated-`>q` condition)
- The LLM judge's validity, including self-preference and length bias.
  · severity: medium · → mitigation: none (addressed in design — blinding,
  cross-agent judges, ordered calibration controls, independent audit, raw
  outputs kept)
- Quota or cost could make the full matrix infeasible, or a looping client
  could overrun the pilot.
  · severity: low · → mitigation: none (addressed in design — pilot-only
  budget, frozen per-turn, tool-call and retry limits, pilot-wide caps plus a
  circuit breaker, and an explicit approval gate in t2179_2; reductions are
  reported)
- A replay startup mismatch (wrong stub dispatch path, missing helper
  permission) could make responses that never loaded the variant look like
  wording trials.
  · severity: medium (residual low) · → mitigation: none (addressed in design —
  agent-specific sandbox layout, an explicit helper allowance, and the
  fail-closed trace validator)
- Repeated-condition evidence could be discarded, or confounded with scenario
  order.
  · severity: medium (residual low) · → mitigation: none (addressed in design —
  every `>q` answer is scored, Latin-square rotation, and comparison with
  fresh answers to the same scenario)

