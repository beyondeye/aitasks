---
priority: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [test_infrastructure, testing, skills]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
children_to_implement: [t2186_1, t2186_2]
assigned_to: dario-e@beyond-eye.com
anchor: 2179
created_at: 2026-11-03 18:29
updated_at: 2026-11-09 23:09
---

## Problem and purpose

t2179 built a working, rigorous experiment harness in `aidocs/benchmarks/shadow_q/`, but only for one
prompt: the aitask-shadow `>q` bullet. Generalize it into a reusable harness that can take **any agent
prompt** (a skill instruction span, a command definition, a procedure step) and:

1. **Check it works as expected:** run it through the real code-agent CLIs on replay fixtures and verify
   the behaviour the prompt asks for.
2. **Measure quality** where behaviour alone is not enough (blinded LLM judges, calibration controls, an
   audit).
3. **Optimize it:** compare wording variants and find the simplest one that is reliable.
4. **Stay affordable.** t2179_2's main run was declined at the approval gate (≈ $164 Claude / ≈ 11.5M Codex
   tokens for 196 sessions). Cost control is a first-class requirement, not an afterthought.

## User decisions (2026-11-03)

- **One task, decomposition at planning time.** Planning decides the children. The scope candidates below
  are input to that decision, not a fixed split.
- **Developer tooling, under `aidocs/benchmarks/prompt_eval/`** (shadow_q stays in place, or becomes a
  thin spec on top of the core). No `ait` subcommand, no `ait setup` whitelisting, no website docs. Promote
  to a user-facing command only later, as a separate task, if it proves useful.

## What is already generic vs shadow-specific (in `aidocs/benchmarks/shadow_q/`)

| already generic (reuse) | shadow-specific (becomes a per-experiment spec) |
|---|---|
| `harness.run_cli`: bounded runner, process-group kill, live tool-call counter | `qspan.py`: the `>q` bullet span finder; becomes a generic instruction-span selector over a frozen render |
| `harness.Budget`: durable journal, cap and stop-launch thresholds, unreported-call bounds | `freeze.py`: renders `aitask-shadow` for the claude/codex `fast` profile; becomes a skill, profile and agent list |
| `validate.parse_claude` / `parse_codex`, `read_coverage`, `match_output`, the outcome classes | replay stubs (`aitask_shadow_capture.sh`, context, profile, render, explain): a helper-replay map with fixture outputs |
| `validate.summarise`: compliance and overall success side by side | turn script (`/aitask-shadow %9999 60_2`, then `>q`) |
| `judge.py`: blinding, strict JSON plus one re-ask, calibration controls, dispute flag | validator rules ("variant loaded; fresh capture and phase in the `>q` turn"): per-turn evidence rules |
| `store.py` `PublicSink` / `PrivateSink`, `check_public.py` leak check | `rubric.md` / `judge_prompt.md` (decision help: options, benefit and cost): a rubric with a declared JSON schema and adequacy rule |
| seeded order, Latin squares, `expand_matrix` | the private store location (aitasks_go `aidocs/shadow_q_store/`): store resolution by registry name |

## Scope candidates (for planning to decompose)

1. **Extract the core plus a declarative experiment spec, no spend.**
   - Port shadow_q as the first spec.
   - **Equivalence proof:** `classify` and `summary` over the saved pilot batch give byte-identical results
     before and after the extraction (no CLI calls).
   - Absorb the gaps listed in `aiplans/archived/p2179/p2179_2_*.md` (section "Harness gaps a future main
     run must close first"):
     - a matrix-run command with `--resume`;
     - per-run `limits.json` blocks;
     - the Codex `-c web_search="disabled"` flag, plus a behavioural probe;
     - all-scenario controls;
     - a durable per-session answer index;
     - final-record-per-cell aggregation;
     - an aggregator.
2. **A second spec on a different prompt** to prove the format is general. Prefer one with deterministic
   behavioural checks (expected helper or tool calls, refusals, ordering) and no LLM judge, so it is cheap to
   run.
3. **Cost optimization:**
   - judge calls grouped by scenario so the shared prompt prefix can hit the prompt cache (measure it: in
     the t2179 pilot, a task-aware Claude judge call cost ≈ $0.28);
   - adaptive or sequential sampling with pre-registered stopping rules, so a cell stops once its interval
     is decided;
   - a single-judge plus sampled-audit mode, calibrated against two-judge runs;
   - `plan` prints a projection, and a paid `run` refuses without a recorded user approval of those numbers.
4. **Prompt-optimization loop:**
   - propose variants from analysed failures;
   - evaluate them on a small budget;
   - confirm on held-out scenarios.
   - Every spend is approval-gated. It never edits a production skill: adoption is always a separately
     scoped task.

## Constraints carried over from t2179

- **Real clients only.** Resolve the agents and models at run time through the framework paths
  (`aitask_codeagent.sh resolve`, `lib/agent_string.sh`). Record the CLI versions and the raw reasoning
  settings. Never substitute a model, and never trust a model's claim about itself.
- **Never touch a real pane.** Use the isolation pattern: no `TMUX` / `HERDR_*`, an empty `TMUX_TMPDIR`, a
  fake pane id, and a sandbox outside every repository.
- **Public/private split.** aitasks is public. Fixtures that quote private projects, raw outputs and
  rationales go to a private store. Public files hold whitelisted numbers only, and `check_public.py` runs
  before each public commit.
- **Claude Code headless (`-p`) is an explicit, documented opt-in** (`aidocs/framework/shell_conventions.md`,
  the `claude -p` caveat: billed at a higher rate).
- **Agents:** Claude Code and Codex now. Design an adapter seam for OpenCode and agy later, without
  building them.
- **Prior art to evaluate:** Claude Code's `claude plugin eval` could serve the Claude side. It cannot
  replace the harness, because the framework must cover the other agents too.

## Acceptance (draft; planning finalizes it)

- The core plus spec format exists, with shadow_q ported and the byte-identical equivalence proof.
- A second spec runs end-to-end: on a small user-approved budget, or under the offline fake-CLI tests only
  when no budget is approved.
- The cost features are implemented and their effect measured, or recorded as unmeasured.
- Offline tests (fake `claude`/`codex` on PATH, a synthetic store) cover the core, the spec loading and the
  cost features.
- Nothing changes under `.claude/skills/`, `.agents/` or `.opencode/`.

## Pointers

- `aidocs/benchmarks/shadow_q/` (`README.md`, `pilot_report.md`, `harness.py`, `validate.py`, `judge.py`,
  `store.py`, `check_public.py`)
- `aiplans/archived/p2179/p2179_1_shadow_q_harness_and_pilot.md`: what was built, every review fix and the
  harness issues found.
- `aiplans/archived/p2179/p2179_2_*.md`: the re-checked cost projection, the harness gaps and the cost
  levers.
- `tests/test_shadow_q_harness.py`: 82 offline tests, which are the pattern for the new tests.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2258** id=2026-11-09T12:34:10Z.9772ed8f8ca99f4bc87b7afb from=t2258 at=2026-11-09T12:34:10Z base=eaa6af1abe9037b1ecc23e3f108816e67d9c7d20 base_branch=main dirty=yes host=omg16
>
> | Advisory context from t2258 (doc audience levels and newcomer-readable prose). This is not a request and not a dependency.
> | 
> | t2258 plans to add new agent instructions:
> | - a newcomer prose rule pack in aitasks/metadata/doc_update_guide.md;
> | - a review pass in the docs_updated gate (.claude/skills/aitask-gate-docs-updated/SKILL.md) that runs a fresh-reader sub-agent with a persona based on the page's level.
> | 
> | Those instructions could later become a spec for this harness. The question it would answer: does the review pass work reliably across Claude Code and Codex, including agents that have no sub-agents?
> | 
> | It is judge-scored (readability), so it fits only once the harness supports judge-scored specs. It is not a candidate for the cheap, deterministic second spec this task describes.
> | 
> | No dependency in either direction: t2258 does not wait for t2186, and adopting any result would be a separately scoped task.
> | 
> | Hedge: as of this note, t2258 is Ready and unplanned. The rule pack and the review pass do not exist yet.
