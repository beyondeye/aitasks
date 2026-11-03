---
priority: medium
effort: medium
depends: []
issue_type: test
status: Implementing
labels: [shadow, skills, testing]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
children_to_implement: [t2179_1]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-11-02 17:45
updated_at: 2026-11-03 08:34
---

## Problem and purpose

Experiment with alternative definitions of the aitask-shadow `>q` command and measure the quality and consistency of the resulting decision help across the current default agents in Codex and Claude Code.

This request arose while shadowing aitasks_go task t60_2. The existing skill already required the agent to explain the situation in simple words, explain each option and its trade-offs, and then suggest an answer with reasoning. Repeated `>q` responses nevertheless jumped straight to a recommendation with a short justification, giving little explanation of the underlying choice or the benefits and costs of each option.

The user's central concern is that advanced agents should understand a clear statement of intent without needing an over-specified output format. Do not assume that adding more instructions or a rigid response template is the correct remedy. Treat this as an empirical question, including variation between independent runs of the same agent, rather than immediately adopting the most detailed prompt.

This task belongs in the aitasks framework repository. The originating task t60_2 belongs to aitasks_go and is context only, not a dependency or parent of this task.

## Definitions to compare

Freeze and version the actual current authoring/rendered definition as the unchanged baseline, then compare at least these alternatives:

1. **Current baseline.** Preserve the existing wording and surrounding skill instructions, including the requirement to explain the situation first, explain each option and its trade-offs, and recommend an answer with reasoning.
2. **Concise intent-focused definition.** State the purpose clearly: help a non-expert understand the decision well enough to choose; explain what each option changes and why it matters before recommending one. Leave presentation and length to the agent.
3. **Explicit semantic requirements without a prescribed layout.** Require meaningful explanations of the situation and all options, their practical benefits/costs, and recommendation reasoning; distinguish accessible language from mere brevity. Do not prescribe headings, bullets, word counts, or a fixed response shape.
4. **More prescriptive proposal from the shadow conversation.** Explain the problem and why the choice matters, defining unfamiliar terms; for each option explain what happens, its main benefit, its main drawback, and when it makes sense; then recommend an option in relation to the task. Before sending, check that every substantive option has an explanation and trade-off, and that brevity has not removed required content.

Record the exact wording of every variant. Preserve the common advisory-only and fresh-context requirements across variants so differences are attributable to the definition being tested. Do not give the detailed variant more source evidence than the concise variants. Additional variants, such as a worked example, are optional and must have a stated hypothesis.

## Agents and experiment design

- At execution time resolve the currently configured default model/agent and reasoning settings for Codex and Claude Code from their real configuration/framework resolution paths. Record exact CLI versions, configured and resolved model identifiers where available, reasoning settings, profile, relevant instruction sources, and run date. Do not infer model identity from the model's own claims or hard-code today's defaults into the experiment.
- Run through the actual Codex and Claude Code clients so their instruction stacks and defaults are represented. Use isolated replay fixtures rather than interacting with a working agent's pane. Never send input to the followed pane as part of these tests.
- Use a bounded pilot to check the harness and estimate cost, then freeze the main matrix, rubric, repetition count, and budget before evaluating results. Target at least three representative decision scenarios, all four variants, both default agents, and at least five independent fresh-session runs per cell. Report any unavailable cells or justified budget reductions; do not silently substitute another model or count a retry as an additional successful sample.
- Include realistic surrounding skill/repository instructions and the normal brevity preference, not just an isolated prompt sentence. Add a small paired comparison with minimal context to investigate whether long surrounding context affects compliance. Keep the primary comparisons otherwise identical and randomize or balance run order.
- Keep fresh-session repetitions distinct from a small repeated-`>q` conversation condition. The originating failure happened over several turns; check whether previous terse answers establish a pattern that persists. Never mix the user's later corrective explanation into baseline trials.

## Scenarios

Include the originating decisions as reproducible fixtures with enough source facts to assess them without browsing or running project tests:

- **File selection:** use the project's `go list` test-file sets, or add a reconstructed `go/build.MatchFile` check. Explain the build-context/toolchain issue and the trade-off between another check and duplicated matching logic.
- **Runnable examples:** include runnable Go examples as cases, or restrict cases to Test/Fuzz and document that examples will not run. Explain what an executable example is and the practical coverage/scope consequences.
- **Supported Go versions:** download and test Go 1.26 alongside the available 1.27, or claim support only for 1.27. Include the distinction between the declared minimum, locally tested compatibility, and ongoing CI coverage.

Do not include expected recommendations in the model input. Fixture reference notes should support scoring the explanation, not force one preferred answer. Include at least a small coverage check for `>q` outside an on-screen multiple-choice question, since the command also helps decide whether to wait, redirect, approve, or seek a deeper review.

## Evaluation

Define an anchored rubric before the main run. Assess factual correctness, explanation of the underlying decision in accessible language, substantive coverage of every option's benefits and costs, task-specific recommendation reasoning, unsupported claims, readability, and adherence to advisory-only behavior. Distinguish a reason to prefer one option from an actual explanation of the other option.

Do not score quality by response length, headings, keyword presence, or conformity to the detailed variant's format. Longer answers may still be shallow; concise answers may be sufficient. Avoid inventing drawbacks merely to fill a required slot. Assess whether a user can understand the consequences well enough to choose.

An automated evaluator may assist, but preserve its prompt/version and audit representative high, low, borderline, and disputed judgments independently. Blind variant/agent labels during assessment where practical. Keep raw outputs so the user can compare examples and reassess scores without rerunning paid calls.

Report per-agent, per-variant and per-scenario results, the distribution across repeats and failure frequency, not just an average or one selected example. Show representative outputs and counterexamples. Report latency, token usage/cost when exposed, and instruction length as trade-offs. Separate observed results from hypotheses about why an agent behaved that way; do not claim that self-explanations reveal its internal cause or that a small sample guarantees future reliability.

## Deliverables and acceptance

- A rerunnable experiment harness or documented runnable procedure, frozen fixtures/variants, and machine-readable run metadata and results, using existing framework agent-launch/evaluation facilities where suitable.
- Durable raw response artifacts and rubric/scoring evidence, stored through repository conventions rather than only in temporary files or terminal history.
- Completed repeated runs for both actual default agents, or explicit evidence of unavailable clients/models and the remaining gap.
- A comparison report that directly answers whether a concise intent-based definition is sufficient, whether more explicit wording materially improves consistency, and whether the result differs by agent, context, or repeated conversation turns.
- An evidence-based recommendation for the simplest reliable definition, including the possibility of keeping the current definition or finding that no tested wording is sufficiently reliable. Record uncertainties and any targeted follow-up experiment needed.
- Do not replace the production `>q` definition merely to set up the experiment. Keep variants isolated; any production adoption should follow the findings and be scoped explicitly as a follow-up.

## Source pointers

- `.claude/skills/aitask-shadow/SKILL.md.j2` is the authoring source; the inline `>q` procedure was around lines 281-300 at the time of the report. Re-resolve locations at execution time.
- `.agents/skills/aitask-shadow-default-codex-/SKILL.md` and corresponding Claude rendered skills are generated variants; record the render profile and source revision rather than treating a generated edit as durable.
- `.aitask-scripts/aitask_skill_render.sh` and existing agent/model resolution and launch utilities should be inspected before building new plumbing.
