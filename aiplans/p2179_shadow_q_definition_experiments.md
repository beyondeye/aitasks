---
Task: t2179_shadow_q_definition_experiments.md
Base branch: main
Output branch: main
---

# t2179 — Shadow `>q` definition experiments (parent plan: decompose into 2 children)

## Context

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

## Decomposition (created after approval: plan mode is read-only)

Each child is created with `aitask_create.sh --batch --parent 2179` through the
Batch Task Creation Procedure. Each child task file carries the full context
sections, and each gets a plan at `aiplans/p2179/p2179_<n>_<name>.md`.
- The parent goes back to `Ready` (with `--plan-approved-at ""`) and its lock is
  released.
- t2179_2 depends on t2179_1 (siblings auto-depend).
- No aggregate manual-verification sibling: N=2, but neither child produces TUI
  behaviour, so the prompt is answered or skipped per the procedure.

### t2179_1 — `shadow_q_harness_and_pilot`

Everything lives in the new directory `aidocs/benchmarks/shadow_q/`, on the code
branch.

1. **`freeze.py`** — pins the baseline.
   - Record the repo SHA, plus the sha256 of `SKILL.md.j2` and of both
     fast renders.
   - Extract the `>q` bullet verbatim. Assert that it occurs exactly once.
   - Write `variants/v1_baseline.md` with the exact bytes.
2. **`variants/`** — four frozen bullet texts, `v1`…`v4`, with exact wording.
   - Steps 1-2 (recapture plus `--phase`, gather context) and step 5 (the user
     types the answer themselves) stay **identical** in every variant. Only the
     explanation and decision steps change.
   - v2, v3 and v4 share one identical sentence for the non-question state (the
     realistic moves wait / approve / answer / interrupt-or-redirect / `>d` `>pc`
     `>i`; a deeper capability is offered by shortcode and never started). v1
     keeps its own wording verbatim.
   - Variant texts (the replacement for steps 3-4):
     - **v2 (concise intent):** "Help the user understand the decision well
       enough to make it themselves; assume they are not an expert in this
       area. Explain what is being decided and, for each realistic option, what
       it would change and why that matters — then recommend one and say why."
       Then the shared sentence.
     - **v3 (explicit semantics, no layout):** "Explain the decision so the user
       can make it. In whatever form suits the situation, cover: what is
       happening and what is actually being decided, in language a non-expert
       can follow (define terms they may not know); for every realistic option,
       what choosing it does in practice and its real benefits and costs — an
       explanation of the option itself, not only a reason it loses to another;
       and your recommendation, reasoned from this task's goals and facts. Plain
       language is not the same as brevity: be as short as those explanations
       allow, not shorter. Do not invent drawbacks to balance an option." Then
       the shared sentence.
     - **v4 (prescriptive, from the shadow conversation):** "Explain the problem
       and why the choice matters, defining unfamiliar terms. For each option
       explain what happens if it is chosen, its main benefit, its main
       drawback, and when it makes sense. Then recommend an option and explain
       the recommendation in relation to the task. Before sending, check that
       every substantive option has an explanation and a trade-off, and that
       brevity has not removed required content." Then the shared sentence.
   - No optional extra variant (such as a worked example) is tested. The report
     states this.
   - `variants/README.md` holds each variant's hypothesis.
   - The harness builds each variant's full SKILL.md by exact-span substitution
     into the frozen fast render. It asserts that the diff touches only that
     span.
3. **`fixtures/<scenario>/`**
   - Model inputs per scenario:
     - `screen*.txt`: a reconstructed, cleaned pane capture that shows the
       followed agent's AskUserQuestion with its option labels and
       descriptions.
     - `phase.txt`, plus a task excerpt and a plan excerpt holding enough source
       facts.
   - Scorer-only file per scenario: `reference.md` lists the key facts and
     consequences an explanation should convey. It names **no expected answer**.
   - Scenarios:
     - **`file_selection`:** use the `go list` sets or add a reconstructed
       `go/build.MatchFile` check. Covers build context and toolchain, and an
       extra check versus duplicated matching logic.
     - **`runnable_examples`:** run examples as cases, or keep only Test/Fuzz
       and document it. Covers what an executable example is and the coverage
       consequences.
     - **`go_versions`:** fetch go 1.26 alongside 1.27, or claim support for 1.27
       only. Covers declared minimum versus locally tested versus CI coverage.
     - **`working_wait` (non-question coverage):** a long real-tool test run
       with no output. The decision is wait / interrupt / redirect / `>d`.
   - All screens are marked *reconstructed* and contain none of the user's
     later corrective explanation.
   - The facts are pinned to aitasks_go `b523a6bc`, the same SHA recorded in
     `fixtures/PROVENANCE.md`.
   - Surrounding instructions: frozen copies of aitasks_go `CLAUDE.md` and
     `AGENTS.md` (sha256 recorded), because that is where the failure happened.
4. **`harness.py`** (Python stdlib). It builds sandboxes, runs sessions and
   records metadata.
   - **Sandbox per session, with an agent-specific layout.** A fresh
     `git init` dir under the run dir, built by the harness before launch,
     containing:
     - the instruction files;
     - fixture task and plan files;
     - each agent's **own** production stub, verbatim, and its own variant
       render, at the path that stub actually dispatches to:
       - **Claude:** `.claude/skills/aitask-shadow/SKILL.md` (it calls
         `--agent claude` and reads `.claude/skills/aitask-shadow-fast-/SKILL.md`),
         plus the rest of the Claude fast render's procedure files, unchanged;
       - **Codex:** `.agents/skills/aitask-shadow/SKILL.md` (it calls
         `--agent codex` and reads
         `.agents/skills/aitask-shadow-fast-codex-/SKILL.md`), plus the rest of
         the Codex fast render's procedure files, unchanged. Its cross-references
         already point at the `-codex-` paths.
     - The profile segment is `fast` for every variant, so the subject never
       sees a variant label.
     - `freeze.py` pins both agents' render trees (sha256 per file). The
       variant span substitution runs on each agent's own `SKILL.md`, and the
       occurs-once and only-the-span-differs assertions are checked per agent.
   - **Replay stubs** in the sandbox `.aitask-scripts/`:
     - `aitask_shadow_capture.sh` serves `screen_current.txt` (no-arg,
       `--deep`, explicit id, `-`) and `phase.txt` (`--phase`);
     - `aitask_shadow_context.sh` prints `TASK_FILE:`/`PLAN_FILE:`;
     - `aitask_skill_resolve_profile.sh` prints `fast`;
     - `aitask_skill_render.sh` is a no-op;
     - `aitask_explain_context.sh` prints "no history".
     - `reference.md` is **never** copied in; a self-check asserts its absence.
   - **Isolation (never touches a real pane):**
     - `TMUX`/`TMUX_PANE` are unset, and `TMUX_TMPDIR` points at an empty
       dir, so no tmux server is reachable.
     - The fake pane id is `%9999`.
     - Claude gets an explicit, self-sufficient `--allowedTools` list, so the
       run never depends on inherited permissions: `Read`, `Glob`, `Grep`, and
       `Bash(./.aitask-scripts/<h>:*)` for each replay helper the startup stub
       and the skill call (`aitask_skill_resolve_profile.sh`,
       `aitask_skill_render.sh`, `aitask_shadow_capture.sh`,
       `aitask_shadow_context.sh`, `aitask_explain_context.sh`).
       - The sha256 of the user-level `~/.claude/settings.json` is recorded,
         because it is still part of the real stack.
       - A pilot check confirms that startup succeeds from the explicit list
         alone, with no permission-denied event in the trace.
     - Codex runs with `--sandbox read-only`. The stubs only read, and the
       harness does all writes before launch.
   - **Trial validity, from the tool trace (fail closed).** Every turn is run
     with a machine-readable trace: Claude `--output-format stream-json
     --verbose`, Codex `exec --json`, which gives `command_execution` items.
     `validate.py` parses the trace. A response counts as a wording trial
     **only if** all three hold:
     1. **Turn 1** read the intended frozen variant file, the agent's own
        `aitask-shadow-fast[-codex]-/SKILL.md`. Accepted reads are a full
        `Read`/`cat`, or ranged reads (`sed -n 'a,bp'`, `head`, `nl`) whose
        union covers the `>q` bullet's line span. The file's sha256 must
        match the frozen variant both before and after the session.
     2. **The `>q` turn** ran `aitask_shadow_capture.sh` (a fresh fixture
        capture) and `--phase` **within that turn**.
     3. There was no permission-denied event or tool error on a replay helper.

     **Outcome classes.** Every attempted trial (each `>q` answer slot) gets
     exactly one class. The class decides what the trial counts toward:
     - **`infra_failure:<reason>`** — the experiment failed, not the subject.
       Reasons: `setup_failed`, a launch or CLI error before any assistant
       output, a stub error, a sha mismatch, a `permission_denied` on a
       helper the allowance was meant to cover (a harness bug), and a
       `limit_timeout` with **no** assistant output or tool events (a hang).
     - **`uncertain_load`** — the trace cannot tell whether the variant was
       read (an unparseable read form).
     - **`subject_noncompliance:<reason>`** — the subject observably failed to
       follow the command, with setup verified as working. Reasons:
       - `variant_not_loaded`: the stub path worked but the subject never
         read the dispatched file. Reported as *pre-variant*, because the
         wording was never seen;
       - `no_fresh_capture` in the `>q` turn;
       - `no_answer`;
       - `advisory_violation`: any attempt to reach tmux or send input;
       - `limit_tool_calls`;
       - `limit_timeout` after observed activity.
     - **`valid`** — scored by the judges.

     Off-path helper calls are flagged on the record but do not change its
     class. Pilot responses are classified the same way. The validator has
     its own fake-trace tests (see 9).
     - `AITASK_AGENT_STRING` is set explicitly, so the session hook records
       correctly or refuses.
   - **Agents.** Resolved at run time, never hard-coded:
     - Codex: `aitask_codeagent.sh resolve shadow`.
     - Claude: `DEFAULT_AGENT_STRING`, the same default `AgentCommandScreen`
       prefills when switching to claudecode. Child 1 confirms that path and
       records it.
     - Invocations mirror the dry-run launch line:
       - `claude --model <cli_id> -p --output-format json '/aitask-shadow %9999 60_2'`,
         then `--resume <session> '>q'`;
       - `codex exec --json -m <cli_id> -C <sandbox> '$aitask-shadow %9999 60_2'`,
         then `codex exec resume <id> --json '>q'`.
     - Exact flags are verified against each CLI's `--help` at execution time
       and recorded.
   - **Trial shape.** Turn 1 is the invocation (greeting) and is never scored.
     **Every `>q` answer is scored.**
     - **Fresh condition:** turn 2 is `>q`, and that is the one scored answer.
     - **Repeated-`>q` condition:** one session, three `>q` answers (turns 2,
       3 and 4). Before turns 3 and 4 the harness advances the stub screen to
       the next AskUserQuestion scenario. Each answer is scored and recorded
       with `conversation_id`, `turn_index`, `position` (1-3) and `scenario`.
     - **Scenario order is rotated** by a Latin square over the three AUQ
       scenarios: ABC, BCA and CAB, one order per conversation. In the main
       matrix, each agent × variant gets 3 conversations, so every scenario
       appears once at every position.
       - In the pilot, the two agents get different orders (Claude ABC, Codex
         BCA). The pilot only checks the mechanics.
     - **Persistence comparison:** each repeated-condition answer is compared
       with the **fresh-session answers to the same scenario × agent ×
       variant**: the per-dimension score difference and the failure-flag
       rate, by position. Position and scenario effects are reported
       separately, so they are not confounded.
     - The **minimal-context** condition has no `CLAUDE.md`/`AGENTS.md` and a
       SKILL.md trimmed to header + Step 1 + the `>q` bullet + Guardrail.
   - **Metadata (JSONL per session):**
     - identity: run_id, cell (scenario, variant, agent, condition, rep), order
       index plus seed, timestamps, latency;
     - environment: CLI versions, configured agent string and cli_id, the model
       **reported by the CLI's JSON output**, reasoning settings (codex config
       value; Claude settings), profile, sha256 of the variant, fixture and every
       instruction file;
     - usage: tokens and cost when exposed, tool calls made;
     - outcome: exit code, `status` (`ok`/`failed`/`setup_failed`) and `attempt`.
       A retry is recorded and never counted as an extra sample.
   - Raw stdout, stderr and final text go to `runs/<batch>/<run_id>/`.
   - Run order is shuffled with a recorded seed. At most 2 concurrent sessions.
   - **Execution limits** (enforced by the harness and frozen in `limits.json`
     before any run; each limit hit is a distinct recorded outcome):
     - **Wall clock per CLI invocation (one turn):** 600 s for a subject turn,
       300 s for a judge call. The harness runs each CLI in its own process
       group and, at the deadline, sends SIGTERM, then SIGKILL after 10 s.
       Outcome: `limit_timeout`.
     - **Tool calls per turn:** at most 15, counted harness-side from the
       streamed trace for both agents. Above that, the turn is killed with
       outcome `limit_tool_calls`. Claude also gets `--max-turns 20` as a
       backstop.
     - **Retries:** at most **1** per session. A retry is allowed only for a
       launch or transient failure *before any assistant output* (non-zero
       exit with no answer, `setup_failed`). A completed answer is never
       retried, whatever its quality, and neither is a limit hit. Each attempt
       is recorded, and a retry never adds a sample.
     - **Pilot-wide allowance** (judging included):
       - **Hard cap of 80 CLI invocations.** Subject turns: 8 fresh sessions
         × 2 = 16, 2 repeated × 4 = 8, 2 minimal × 2 = 4, so 28. Judge calls:
         (16 scored answers + 2 controls) × 2 judges = 36. That leaves 16 for
         retries and validator reruns.
       - **Claude reported-cost threshold:** $15 cumulative.
       - **Codex token threshold:** 2M non-cached input+output tokens
         cumulative.
       - **Semantics.** The invocation cap is a **strict ceiling**: it is
         checked before every launch, so it can never be exceeded. The cost
         and token values are **stop-launch thresholds** with an explicitly
         permitted and reported overrun. Once cumulative usage reaches a
         threshold, no new invocation launches.
         - Turns already in flight (at most 2, the concurrency limit) finish
           within their own per-turn limits.
         - The final totals may therefore exceed the threshold, by at most
           those in-flight turns' usage.
         - `pilot_report.md` states each threshold, the final total and the
           overrun.
         - This matches the user's approved pilot-only budget: the threshold
           bounds what the pilot *starts*, not a strict cap on spend.
       - **Circuit breaker:** 3 consecutive sessions for one agent classed as
         `subject_noncompliance` or `infra_failure` stop that agent's
         remaining pilot cells (`not_run:circuit_open`).
       - Hitting any cap or threshold stops new launches, and every
         un-launched cell is recorded as `not_run:pilot_stopped:<cap>`.
     - **Partial results are preserved.** Each turn's record is appended to
       the JSONL, and raw streams are flushed as they arrive, so a stop or kill
       leaves every completed and partial record on disk. `pilot_report.md`
       counts each outcome class.
     - Main-run limits are proposed in `matrix.json` from the pilot's
       measurements. They are approved together with the budget in t2179_2
       step 1.
5. **`rubric.md`** (anchored, frozen before the main run). Each dimension is
   scored 0-3 with written anchors:
   - factual correctness;
   - accessible explanation of the underlying decision;
   - per-option coverage: does it explain what the option does, its benefit and
     its cost? This is scored **per option**, and "a reason to prefer A" is
     distinguished from "an explanation of B";
   - task-specific recommendation reasoning;
   - unsupported claims;
   - readability;
   - advisory-only adherence (pass/fail);
   - a holistic "could a non-expert choose?" score.
   - **Failure flag:** the observed failure, a recommendation without a
     substantive explanation of a non-recommended option.
   - Length, headings, keywords and conformity to v4's format are explicitly
     **not** scored.
6. **`judge.py`** (blinded scoring).
   - Outputs get random ids. Agent self-references and variant hints are
     stripped (the stripping is logged).
   - Frozen judge prompt (`judge_prompt.md`, sha256 recorded) plus the scenario's
     `reference.md`.
   - Run by **both** agents' judges, headless with no tools. Disagreement beyond
     1 point on any dimension is flagged *disputed*.
   - **Calibration controls:** hand-written control answers per scenario, one
     shallow (recommendation-only) and one adequate, with no length correlation.
     The judges must score the shallow one below the adequate one. If they do
     not, the judge is not used and the result is reported.
7. **Pilot** (bounded by the pilot-wide allowance above).
   - `file_selection` × v1-v4 × both agents × 1 rep (8 sessions), plus 1
     repeated-`>q` conversation per agent and 1 minimal-context session per
     agent: 12 sessions and 16 `>q` answers.
   - Then judging of every `valid` answer, plus the controls.
   - The trace validator runs first. Trials in every other class are counted
     in their class and not judged.
   - Pilot scores are **harness validation only, never evidence.**
   - The pilot also records a **fidelity check**: whether v1 reproduces shallow
     option coverage. It is stated as observed, with an *inconclusive* outcome
     allowed.
8. **Freeze point.**
   - `matrix.json` holds the proposed main matrix: 4 scenarios
     (`working_wait` at 3 reps) × 4 variants × 2 agents × 5 reps; minimal
     context (v1, v2) × 1-2 scenarios × 2 agents × 5; repeated-`>q` (v1, v2) × 2
     agents × 3 conversations.
   - Also frozen: the rubric, the judge prompt and seeds.
   - `pilot_report.md` gives measured cost, tokens and latency per call, the
     projected main-run total, harness issues and the fidelity observation.
   - Child 1 ends by presenting those numbers. **The main spend needs explicit
     user approval at the start of t2179_2.**
9. **Tests:** `tests/test_shadow_q_harness.py`, offline. It uses a **fake
   `claude`/`codex` binary on PATH** that emits canned JSON and checks:
   - variant span substitution (only the span differs; an occurs-once violation
     fails);
   - the sandbox has no `reference.md` and no tmux reachable;
   - metadata fields are parsed from the canned JSON;
   - the per-agent sandbox layout matches each production stub's dispatch path
     (Claude `.claude/skills/aitask-shadow-fast-/`, Codex
     `.agents/skills/aitask-shadow-fast-codex-/`), and Claude's
     `--allowedTools` covers every helper both stubs and the skill invoke. The
     helper list is grepped from the frozen renders, not hand-copied;
   - the trace validator, against fake traces: valid; variant not read; a
     ranged read that misses the `>q` span; no capture in the `>q` turn;
     permission denied; an unparseable read giving `unverified_load`;
   - outcome classification: each fake trace maps to the expected class
     (infra versus uncertain versus subject noncompliance, including the two
     `limit_timeout` cases split by observed activity). Aggregation fixtures
     check that overall success excludes only `infra_failure` and
     `uncertain_load` from the denominator, that the sensitivity line includes
     them, and that conditional quality uses `valid` only;
   - threshold semantics: a fake whose usage crosses the threshold mid-turn
     lets the in-flight turn finish, launches nothing after it, and records
     the overrun. The invocation ceiling is never exceeded;
   - repeated-condition records carry `turn_index`, `position` and
     `scenario`, every `>q` turn is scored, and the Latin-square orders are
     balanced;
   - limits: a fake that loops on tool calls is killed with
     `limit_tool_calls`; a fake that hangs gets `limit_timeout`, with its
     process group gone afterwards; a pre-output failure is retried exactly
     once and a completed answer never is; a cost or token cap trip marks the
     remaining cells `not_run:pilot_stopped:<cap>` with partial records kept;
     the circuit breaker opens after 3;
   - a retry is not counted as a sample;
   - blinding strips the labels;
   - matrix expansion and seed-stable order.
   - Plus a mutant check: break the occurs-once assert, and the test goes red.

### t2179_2 — `shadow_q_main_run_and_report`

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

Each child archives through the normal Step 9 (Post-Implementation). The parent
auto-archives when both children are archived.

## Verification

- t2179_1:
  - `python3 tests/test_shadow_q_harness.py` passes, and its mutant goes red.
  - `bash tests/run_all_python_tests.sh --test-dir …` passes for the new module.
  - The pilot JSONL accounts for all 12 sessions and 16 `>q` answers. Each has
    exactly one outcome class (`valid` / `subject_noncompliance:*` /
    `infra_failure:*` / `uncertain_load` / `not_run:*`) and a CLI-reported
    model per launched session. At least one `valid` trial per agent shows the
    intended variant loaded and a fresh capture in the `>q` turn.
  - `pilot_report.md` shows overall success and conditional quality side by
    side. These are mechanics only, not evidence.
  - Total invocations are ≤ 80, a strict ceiling. No invocation launched after
    a cost or token threshold was reached. Any overrun from in-flight turns is
    reported with its amount.
  - The judge controls are ordered correctly.
  - `git diff --stat` shows no change under `.claude/skills/` or `.agents/`.
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
