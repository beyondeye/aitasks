---
Task: t2179_1_shadow_q_harness_and_pilot.md
Parent Task: aitasks/t2179_shadow_q_definition_experiments.md
Sibling Tasks: aitasks/t2179/t2179_2_*.md
Archived Sibling Plans: aiplans/archived/p2179/p2179_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-03 09:36
---

# t2179_1: Shadow `>q` harness, frozen variants and fixtures, and the bounded pilot

Child 1 of t2179. The parent plan is `aiplans/p2179_shadow_q_definition_experiments.md`.
This child stops at the freeze point (step 8). It does **not** run the main matrix.

## Context (from parent)

Repeated `>q` answers from the shadow agent (seen while it was shadowing aitasks_go
t60_2) jumped straight to a recommendation and gave little explanation of the
choice or of the options' trade-offs. That happened even though the skill already
asks for that explanation. The question is empirical: is a concise statement of
intent enough, or does more explicit wording make answers more consistent, and
does that differ by agent, by context and across repeated turns?

**User decisions:**
- **Budget: pilot only, then ask** (t2179 planning). Build the harness and run
  only the pilot. The main matrix is spent **only after the user explicitly
  approves the measured numbers** at the start of t2179_2.
- **Two child tasks** (t2179 planning). This one covers the harness, frozen
  variants, fixtures, rubric and pilot, ending at a freeze point. t2179_2 covers
  the main matrix, blinded scoring and audit, and the report.
- **Private store in aitasks_go** (verification, 2026-11-03). aitasks is
  **PUBLIC** and aitasks_go is **PRIVATE**
  (`gh repo view`: `beyondeye/aitasks` PUBLIC, `beyondeye/aitasks_go` PRIVATE).
  - The harness, variants, rubric and aggregate numbers stay in public aitasks.
  - Verbatim fixtures, raw outputs and per-answer judge text are committed in
    aitasks_go and referenced from aitasks by commit and sha256.

The production `>q` definition is **not** changed. Adopting a wording is a separate
follow-up, scoped only after the findings.

## Verification record (2026-11-03, HEAD `42b547c67`): what changed vs the first plan

Re-checked against the tree. The plan's core still holds:
- the `>q` bullet is still `.claude/skills/aitask-shadow/SKILL.md.j2:281-300`,
  with no commits to the shadow skill since;
- the Claude and Codex fast `SKILL.md` renders are byte-identical, and the same
  five procedure files differ;
- `aitask_skill_resolve_profile.sh shadow` resolves to `fast`;
- `aitask_codeagent.sh resolve shadow` resolves to `codex/gpt6_1_sol`
  (`gpt-6.1-sol`);
- `DEFAULT_AGENT_STRING=claudecode/opus5_5`;
- the dry-run launch lines are as recorded.

Corrections, all folded into the steps below:
1. **Fixture provenance was wrong.** t60_2 lives on aitasks_go's **data
   branch** (`.aitask-data`, branch `aitask-data`), not at code commit
   `b523a6bc`.
   - The *pre-decision* task body is at data commit `e022bc0`.
   - The first plan (`d55e17a`) already records the user's four decisions
     ("user decision 1…4"). It must never reach the subject or the scorer as
     input.
   - `b523a6bc` is the code commit that the t60_2 Step 0 measurements were taken
     at, and that holds `CLAUDE.md`/`AGENTS.md`.
2. **aitasks_go `CLAUDE.md` == `AGENTS.md`.** Its lines 2-167 are byte-identical
   to the public `seed/aitasks_agent_instructions.seed.md`. Only the 7-line
   `aidocs/aitasks_go/project_overview.md` pointer is project-specific. Both
   files still go to the private store, verbatim.
3. **The sandbox must live outside any repository.** The first plan put it under
   the run dir, inside the aitasks tree. There:
   - Claude loads ancestor `CLAUDE.md` files (it would pick up aitasks'
     `CLAUDE.md`);
   - the parent `.claude/skills/aitask-shadow/` production stub could shadow
     the variant;
   - a nested `git init` would show up as an embedded repo.
4. **The fast renders are gitignored** (`.gitignore:67-68`, `.claude/skills/*-/`
   and `.agents/skills/*-/`). So `freeze.py` must *copy* both render trees into
   the experiment dir; a sha256 alone is not enough. Sandboxes are built only
   from those copies.
5. **CLI flags, checked against `--help` today** (Claude Code **2.1.317**, no
   longer 2.1.316; codex-cli 0.166.0):
   - Claude has **no `--max-turns`**. The backstop is `--max-budget-usd`
     (print-only) plus the harness-side tool-call counter.
   - `codex exec resume` has **no `--sandbox` and no `-C`**. Resume runs with the
     subprocess cwd set to the sandbox and `-c sandbox_mode="read-only"`.
     Resume also filters sessions by cwd.
   - The Codex model is read from the CLI-written session rollout,
     `~/.codex/sessions/**/rollout-*-<thread_id>.jsonl`:
     `turn_context.model` / `.effort`, `session_meta.cli_version`.
     The rollout also holds account ids, so it is **never copied**.
6. **Claude reasoning settings conflict** and are recorded raw, never resolved:
   `effortLevel: high`, `env.ANTHROPIC_REASONING_EFFORT=high` and
   `modelSettings."claude-opus-5-5".effortLevel: xhigh`.
   - `~/.claude/settings.json` also carries org-environment text (`autoMode`).
     Only these keys plus the file's sha256 are recorded.
   - Codex: `model_reasoning_effort = "high"`,
     `plan_mode_reasoning_effort = "high"`, `personality = "pragmatic"`.
7. **More isolation facts:**
   - The user-level Claude SessionStart hook (`~/.claude/hooks/herdr-agent-state.sh`)
     acts only when `HERDR_ENV`/`HERDR_SOCKET_PATH`/`HERDR_PANE_ID` are set, so
     the harness unsets `HERDR_*` as well.
   - `codex features list` shows `memories false`, so there is no cross-trial
     memory. The list is recorded.
   - aitasks_go is `trust_level = "trusted"` in `~/.codex/config.toml`; a fresh
     sandbox path is not. See the startup smoke check.
8. **The helper set is wider** than the first plan listed. The renders also name
   `aitask_lock.sh` and `aitask_pick_own.sh` (in prohibitions). So the replay set
   is grepped only from the stub, Steps 0-2 and the `>q` bullet. Everything else
   is off-path.
   - The capture stub must also accept `--any-pane`.
   - **Startup does capture, after the greeting.** Step 0 forbids any capture or
     context fetch *before* the greeting. Step 1 and the proactive offer ("after
     every capture… the first capture") then capture and read `--phase` during
     startup. So a turn-1 capture after the greeting is compliant. The `>q` turn
     still needs its own fresh capture.
9. **Stubs cannot log by writing a file.** Under `codex exec -s read-only`, a
   stub is a tool subprocess of the sandbox, so an external log path is not
   writable. Helper-call evidence therefore comes from the CLI's own trace (see
   step 4). `codex sandbox [COMMAND]` (codex-cli 0.166.0) runs a command under
   the Codex Linux sandbox, so the stubs can be verified under the real
   read-only mode with **no model call**.
10. **The calibration cells were under-counted.** The repeated sessions (Claude
    ABC, Codex BCA) reach all three AUQ scenarios, so the pilot calibrates
    controls for all three: 12 judge invocations, not 4. The pilot allowance
    below is derived from an enumerated cell list.

## Public / private layout

**Public: aitasks `aidocs/benchmarks/shadow_q/`** (code branch). Code, plus text
that is already public or holds no private content:
- `freeze.py`, `harness.py`, `validate.py`, `judge.py`, `check_public.py`,
  `store.py`;
- `frozen/{claude,codex}/…` render trees and `frozen/FREEZE.json`;
- `variants/`, `rubric.md`, `judge_prompt.md` (generic; it embeds the scenario
  reference only at call time), `limits.json`, `matrix.json`;
- `fixtures/MANIFEST.json`: scenario ids, store project name, store commit and
  per-file sha256, with **no text**;
- `runs/pilot/sessions.jsonl` / `trials.jsonl`: whitelisted fields only — ids,
  hashes, classes, numbers, helper *names*;
- `runs/pilot/scores.json` (numbers only) and `pilot_report.md` (numbers and
  mechanics, no quotes).

**Private: aitasks_go `aidocs/shadow_q_store/`** (aitasks_go code branch `main`,
resolved by logical name with `./ait projects resolve aitasks_go`, never by
sibling path):
- `instructions/CLAUDE.md` and `instructions/AGENTS.md`, from `b523a6bc`;
- `fixtures/<scenario>/…`, including each scenario's `reference.md` and the
  calibration controls;
- `fixtures/PROVENANCE.md`;
- `runs/<batch>/<run_id>/`: raw stdout and stderr streams and the final text;
- `judging/<batch>/`: judge outputs with rationales, the blinding map and the
  stripping log;
- `pilot_notes.md`: representative excerpts for the user.

**Leak guards:**
- `store.py` has two sinks.
  - `PublicSink` accepts only records whose keys are in a frozen field
    whitelist; any other key raises.
  - `PrivateSink` writes under the store root.
- `check_public.py` scans every public file for any whitespace-normalized
  line of ≥ 40 chars that also occurs in any store text file. It exits 1 on a
  hit.
- It runs before every public commit (step 8) and in the test, against a fake
  store.

**Commits:**
- aitasks gets ordinary path-scoped commits (`test: … (t2179_1)`).
- aitasks_go gets path-scoped commits only:
  `git -C <root> add aidocs/shadow_q_store` then
  `git -C <root> commit -m 'test: … (aitasks#2179_1)' -- aidocs/shadow_q_store`.
  - aitasks_go has another session's uncommitted `goengines/` work (t60_2) that
    must never be staged.
  - **aitasks_go is not pushed without the user's explicit confirmation.**

## Implementation

### Pre-phase (risk mitigations)

This block runs after steps 1-6 are built and tested, and immediately before
step 7's pilot matrix. It is listed first because it gates the pilot.

1. [startup_smoke] **(a) Model-free stub preflight. It costs 0 invocations.**
   - For each agent's built sandbox, run every replay-stub form step 4 serves,
     from the sandbox cwd:
     - no-arg, `--deep`, explicit id and `--any-pane` capture;
     - `-` with stdin;
     - `--phase` with and without an id;
     - context;
     - resolve-profile;
     - render;
     - explain-context.

     Each must exit 0 and print exactly the bytes the harness expects.
   - For Codex, run the same forms again under the real sandbox:
     `codex sandbox -c sandbox_mode="read-only" -- <stub> <args>`.
   - **Negative control:** the same wrapper's attempt to create a file outside
     the sandbox must **fail**. This proves read-only is actually in force, so a
     pass is not vacuous. If the control succeeds, or the wrapper is unusable,
     the preflight cannot verify the mode: it stops and reports, and no paid
     call is made.

   **(b) Startup smoke.** Run one **startup-only** session per agent (turn 1
   only, `file_selection`, v1). These are 2 invocations of the cap; they are
   recorded as `condition: smoke` and never count as samples. Each must show:
   - the trace read the agent's own frozen variant file, covering the `>q`
     span, with its sha256 unchanged;
   - the profile-resolve and render stub calls appear in the CLI trace, each
     with exit 0 and the expected output;
   - **greeting before capture:**
     - no capture, `--phase` or context call precedes turn 1's first assistant
       text (Claude: stream-event order; Codex: item order);
     - a capture after the greeting is **allowed** (Step 1), and each such call
       must exit 0 with the expected bytes;
     - a capture before the greeting is recorded as the subject flag
       `capture_before_greeting`, here and on every later session, and
       reported. It is subject behaviour, not a harness failure, so on its own
       it does not stop the pilot;
   - Claude: no permission-denied event under the explicit `--allowedTools`
     list;
   - a CLI-reported model and its effort source were extracted (Claude
     `system/init`; Codex rollout `turn_context`).

   If Codex fails to discover `$aitask-shadow`, re-run its smoke **once** with
   `-c 'projects."<sandbox>".trust_level="trusted"'`. If that passes, record
   `codex_trust_override: true` for every Codex session in the pilot. This
   re-run comes out of the headroom.

   Any other smoke failure **stops**: no pilot cell launches, every cell is
   recorded as `not_run:pilot_stopped:smoke_failed`, and the failure is
   reported to the user. Failures that stop:
   - the variant was not read;
   - a stub error or unexpected stub bytes;
   - a denial on an allowed helper;
   - no reported model;
   - a variant sha change.

1. **`freeze.py`** pins the baseline.
   - Refuse if `git status --porcelain` shows the `.j2` or either stub dirty.
   - Run `./.aitask-scripts/aitask_skill_render.sh aitask-shadow --profile fast
     --agent claude` and the same with `--agent codex`.
   - Copy `.claude/skills/aitask-shadow-fast-/` to `frozen/claude/render/` and
     `.agents/skills/aitask-shadow-fast-codex-/` to `frozen/codex/render/`. Copy
     each production stub to `frozen/<agent>/stub/SKILL.md`.
   - Write `frozen/FREEZE.json` with:
     - the repo SHA;
     - the sha256 of the `.j2`;
     - every frozen file's sha256;
     - the `>q` bullet's line span per agent.
   - Extract the `>q` bullet verbatim: from the `- \`>q\`` line up to the next
     top-level `- ` bullet or `**` heading. Assert that it occurs **exactly
     once** in each agent's `SKILL.md`.
   - Write `variants/v1_baseline.md` with its exact bytes.
2. **`variants/`** holds four frozen bullet texts, `v1`…`v4`.
   - Steps 1-2 (recapture plus `--phase`, gather context) and step 5 (the user
     types the answer themselves) stay **identical** in every variant. Only the
     explanation and decision steps (3-4) change.
   - v2, v3 and v4 share one identical sentence for the non-question state:
     > In any other state (still working, stuck or erroring, a plan waiting for
     > approval, finished), the realistic moves are to wait, approve the plan,
     > answer, interrupt or redirect the agent, or ask for a deeper shadow
     > capability such as `>d`, `>pc` or `>i`; a deeper capability is offered
     > by its shortcode and never started on your own.

     v1 keeps its own wording, verbatim.
   - The variant texts (the replacement for steps 3-4), verbatim:
     - **v2 (concise intent):** "Help the user understand the decision well
       enough to make it themselves; assume they are not an expert in this area.
       Explain what is being decided and, for each realistic option, what it
       would change and why that matters — then recommend one and say why."
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
   - `variants/README.md` holds each variant's hypothesis. No optional extra
     variant (such as a worked example) is tested; the README and the report say
     so.
   - `harness.build_variant(agent, v)` does an exact-span substitution into
     that agent's frozen `SKILL.md`. It asserts that the bullet occurs once and
     that a `difflib` diff touches only that span. The result is cached as
     `frozen/<agent>/variants/<v>.SKILL.md` with its sha256 in `FREEZE.json`.
   - The minimal-context SKILL.md (header + Step 1 + the `>q` bullet + the
     Guardrail) is built the same way, per agent and per variant.
3. **Fixtures (private store)**, `aidocs/shadow_q_store/fixtures/<scenario>/`.
   - **Per scenario:**
     - `screen_1.txt` (and `screen_2.txt` … for the repeated condition):
       a *reconstructed*, cleaned pane capture, marked reconstructed in
       PROVENANCE. It shows the followed agent's explanation and the
       AskUserQuestion with its option labels and descriptions.
     - `phase.txt`: one line in the real `--phase` format,
       `PHASE:PLAN|WAITING:…|SOURCE:…|CONSULTED:…|RECORDING:…|DETAIL:…`
       (see `SHADOW_PHASE_UNKNOWN_LINE` in `.aitask-scripts/aitask_shadow_capture.sh:221`
       and `lib/workflow_phase.format_signal`).
     - `context.txt`: what the context stub prints.
     - `reference.md` (scorer-only): the key facts and consequences an
       explanation should convey, and **no expected answer**. It never names
       the option the user picked.
     - `controls/{shallow,adequate}.md`: hand-written calibration answers, not
       length-correlated.
   - **AUQ scenarios** (`file_selection`, `runnable_examples`, `go_versions`):
     - The task file is a verbatim copy of the pre-decision t60_2 task at data
       commit `e022bc0`, at `aitasks/t60/t60_2_m3_2g_go_test_adapter.md`.
     - `context.txt` = `TASK_FILE:<that path>` + `PLAN_FILE:NOT_FOUND`. The AUQs
       were asked in plan mode, before any plan existed.
     - The measured facts shown on screen come only from the **"measured"**
       column of `d55e17a`'s Step 0 table, never from its "decision" column or
       its decision list.
     - None of the user's later corrective explanation is included.
   - **`working_wait`** (non-question coverage): a long real-tool test run with
     no output; the decision is wait / interrupt / redirect / `>d`.
     - The task and plan come from data commit `b009005`.
     - `context.txt` names both files.
     - `phase.txt` gives `PHASE:IMPLEMENT`.
   - The scenario contents:
     - **`file_selection`:** the `go list` file sets versus an added
       reconstructed `go/build.MatchFile` check. It covers the build
       context / toolchain release-tag issue and the extra check versus
       duplicated matching logic.
     - **`runnable_examples`:** run examples as cases, or keep only Test/Fuzz
       and document it. It covers what an executable example is and the
       coverage consequence.
     - **`go_versions`:** download go 1.26 alongside 1.27, or claim support only
       for 1.27. It covers the declared minimum versus locally tested versus CI
       coverage.
   - `instructions/CLAUDE.md` and `instructions/AGENTS.md` are verbatim from
     `b523a6bc`.
   - `PROVENANCE.md` records:
     - the three aitasks_go SHAs, each with its role;
     - each fixture's source lines;
     - which content is reconstructed;
     - the seed-identity fact (correction 2).
   - The store is committed **before the pilot**. Its commit and per-file sha256
     go into the public `fixtures/MANIFEST.json`. The harness refuses to build a
     sandbox when the store's hashes differ from the manifest (fail closed).
4. **`harness.py`** (Python stdlib only). It builds sandboxes, runs sessions and
   records metadata.
   - **Sandbox location.**
     - Root: `$AIT_SHADOW_Q_SANDBOX_ROOT`, default
       `/tmp/aitasks_shadow_q/<batch>/<run_id>/sandbox`.
     - Before launch, assert that no ancestor of the sandbox contains a
       `CLAUDE.md`, `AGENTS.md`, `.claude/`, `.agents/` or `.codex/`.
     - The sandbox is a fresh `git init` repo, built entirely by the harness
       before launch.
     - After the session, raw files are copied into the private store run dir.
       The sandbox is deleted only after that copy is verified.
   - **Sandbox contents:**
     - the instruction files (omitted in the minimal-context condition);
     - the fixture task file, and the plan file when the scenario has one;
     - the agent's **own** frozen production stub, verbatim, and its own
       variant render, at the path that stub dispatches to:
       - **Claude:** `.claude/skills/aitask-shadow/SKILL.md`, and the variant
         as `.claude/skills/aitask-shadow-fast-/SKILL.md`, plus the rest of the
         frozen Claude procedure files, unchanged;
       - **Codex:** `.agents/skills/aitask-shadow/SKILL.md`, and the variant as
         `.agents/skills/aitask-shadow-fast-codex-/SKILL.md`, plus the rest of
         the frozen Codex procedure files. Their cross-references already point
         at the `-codex-` paths.
     - The profile segment is `fast` for every variant, so the subject never
       sees a variant label.
   - **Replay stubs** in the sandbox `.aitask-scripts/`:
     - `aitask_shadow_capture.sh` serves the current `screen_<k>.txt` for the
       no-arg, `--deep`, explicit-id, `--any-pane` and `-` forms, and serves
       `phase.txt` for `--phase [<id>]`.
     - `aitask_shadow_context.sh` prints `context.txt`.
     - `aitask_skill_resolve_profile.sh` prints `fast`.
     - `aitask_skill_render.sh` is a no-op.
     - `aitask_explain_context.sh` prints "no history".
     - **Stubs write nothing and print no marker.** Their output is exactly
       what the real helper would print for that fixture, so the subject sees
       only realistic output, and they work under Codex's read-only sandbox.
       - The screen for the next turn is advanced by the harness, which
         rewrites `.aitask-scripts/.replay/current` *between* turns, while no
         subject process is running.
     - **Helper-call evidence comes from the CLI's own trace only:**
       - Claude: the `tool_use` Bash `input.command` and its `tool_result`.
       - Codex: the `command_execution` `command`, `exit_code` and
         `aggregated_output`.
       - Commands are parsed through shell wrappers such as `bash -lc '…'`.
       - Every served form is deterministic, so the validator matches the
         traced output against the bytes the harness served. That is a full
         match, or a recorded head + tail match (512 bytes each) when the CLI
         truncated the output.
       - A mismatch is `infra_failure:stub_output_mismatch`.
       - The startup_smoke preflight verifies this channel under the real
         read-only mode before any paid call.
     - `reference.md` and the controls are **never** copied in; a self-check
       asserts their absence.
   - **Isolation (never touches a real pane):**
     - Unset `TMUX`, `TMUX_PANE` and `HERDR_*`. Point `TMUX_TMPDIR` at an empty
       dir. Use the fake pane id `%9999`. Set `AITASK_AGENT_STRING` explicitly.
     - **Claude** gets:
       - `-p --output-format stream-json --verbose`;
       - `--permission-mode dontAsk --permission-prompts none` (an
         unallowed tool is denied and shows as a trace event; it never
         prompts or hangs);
       - an explicit `--allowedTools` list: `Read`, `Glob`, `Grep`, and
         `Bash(./.aitask-scripts/<h>:*)` for each replay helper;
       - `--max-budget-usd` at the per-turn cap from `limits.json`.

       Record the sha256 of `~/.claude/settings.json` and the raw values of the
       effort keys (correction 6). The startup smoke check confirms that
       startup succeeds from the explicit list alone.
     - **Codex** gets:
       - turn 1: `codex exec --json -m <cli_id> -s read-only -C <sandbox> …`;
       - resume turns: cwd set to the sandbox,
         `codex exec resume <thread_id> --json -c sandbox_mode="read-only" '>q'`.

       The trust override is
       `-c 'projects."<sandbox>".trust_level="trusted"'`. It mirrors the
       trusted aitasks_go project and is added only if the startup smoke check
       shows that skill discovery needs it. Whether it was used is recorded per
       session.
   - **Agents**, resolved at run time and never hard-coded:
     - Codex: `aitask_codeagent.sh resolve shadow`.
     - Claude: `DEFAULT_AGENT_STRING` from `lib/agent_string.sh`, the same
       default `AgentCommandScreen` prefills, mapped to its CLI id through the
       same `aitask_codeagent.sh --agent-string … --dry-run invoke shadow`
       path.
     - Both dry-run launch lines are recorded.
   - **Reported model (CLI-written, never self-claimed):**
     - Claude: the `system`/`init` `model` and the `result.modelUsage` keys.
     - Codex: the rollout's `turn_context.model` and `effort` (correction 5),
       with `model_source` recorded.
     - A missing reported model gives `infra_failure:model_unverified`.
   - **Trial validity, from the trace (fail closed).** `validate.py` parses
     Claude's stream-json or Codex's `--json` items (`command_execution` and
     `agent_message`, in order). Helper output is matched against the served
     bytes. A response counts as a wording trial **only if** all three hold:
     1. **Turn 1** read the agent's own `aitask-shadow-fast[-codex]-/SKILL.md`.
        - Accepted reads are a full `Read` or `cat`, or ranged reads
          (`sed -n 'a,bp'`, `head`, `nl`, `Read` offset/limit) whose union
          covers the `>q` span.
        - The file's sha256 must match the frozen variant both before and
          after the session.
        - Turn 1 **may** capture and read `--phase` after its greeting
          (Step 1). The greeting-before-capture order is recorded as the flag
          `capture_before_greeting`; it does not change the class. A turn-1
          capture never satisfies rule 2.
     2. **The `>q` turn** ran `aitask_shadow_capture.sh` (a fresh capture) and
        `--phase` *within that turn*. Each call's traced output matches the
        bytes served for that turn's screen.
     3. There was no permission-denied event, no tool error and no output
        mismatch on a replay helper.
   - **Outcome classes.** Every attempted `>q` answer slot gets exactly one
     class:
     - **`infra_failure:<reason>`**, when the experiment failed, not the
       subject. Reasons: `setup_failed`; a launch or CLI error before any
       assistant output; a stub error; `stub_output_mismatch`; a sha mismatch;
       `model_unverified`;
       `permission_denied` on an allowed helper; `limit_timeout` with no
       assistant output and no tool events.
     - **`uncertain_load`**, when the trace cannot show whether the variant
       was read.
     - **`subject_noncompliance:<reason>`**, when the subject failed to follow
       the command with setup verified as working. Reasons:
       - `variant_not_loaded`, reported as *pre-variant*;
       - `no_fresh_capture`;
       - `no_answer`;
       - `advisory_violation`: any tmux or send-keys attempt;
       - `limit_tool_calls`;
       - `limit_timeout` after observed activity.
     - **`valid`**, which is judged.

     Off-path helper calls are flagged on the record but do not change its
     class.
   - **Trial shape.** Turn 1 (the greeting) is never scored. **Every `>q`
     answer is scored.**
     - **Fresh condition:** turn 2 is `>q`.
     - **Repeated condition:** one session with three `>q` answers (turns 2-4).
       The harness advances the stub screen to the next AUQ scenario before
       turns 3 and 4. Each answer carries `conversation_id`, `turn_index`,
       `position` and `scenario`.
     - **Latin-square scenario orders:** ABC, BCA, CAB. In the main matrix,
       3 conversations per agent × variant. In the pilot, Claude runs ABC and
       Codex runs BCA.
     - **Persistence comparison:** each repeated answer is compared against the
       fresh answers to the same scenario × agent × variant, by position.
       Position and scenario effects are reported separately.
   - **Metadata.** Two records, both whitelisted:
     - `sessions.jsonl`, public:
       - identity: run_id, cell, order index and seed, timestamps, latency;
       - versions and models: CLI versions; configured agent string and
         cli_id; reported model and its source;
       - reasoning settings: the raw keys only;
       - profile;
       - sha256 of the variant, every fixture and every instruction file;
       - the trust override flag and `codex features` memories state;
       - usage: tokens and cost when exposed, tool-call count, helper names;
       - outcome: exit code, `status`, `attempt`, class.
     - `trials.jsonl`, per answer slot.

     Raw streams go to the private run dir, flushed as they arrive. Run order
     is shuffled with a recorded seed. At most 2 sessions run concurrently.
   - **Execution limits** (frozen in `limits.json` before any run):
     - **Per-invocation wall clock:** 600 s for a subject turn, 300 s for a
       judge call. Each runs in its own process group: SIGTERM at the deadline,
       then SIGKILL after 10 s. Outcome: `limit_timeout`.
     - **Tool calls per turn:** at most 15, counted harness-side from the
       streamed trace. Above that, the turn is killed with `limit_tool_calls`.
       Claude's backstop is `--max-budget-usd`.
     - **Retries:** at most 1 per session, and only for a pre-output launch or
       transient failure. A completed answer and a limit hit are never retried.
       A retry never adds a sample.
     - **Pilot allowance, judging included.** The **hard cap is 80 CLI
       invocations**, checked before every launch. The planned total is derived
       from this enumerated cell list. `harness.plan_pilot()` computes it from
       the list, and the test pins it:

       | item | cells | invocations |
       |---|---|---|
       | stub preflight | every stub form × 2 agents, run directly and under `codex sandbox` | 0 (no model call) |
       | startup smoke | 2 agents × turn 1 | 2 |
       | fresh sessions | `file_selection` × v1-v4 × 2 agents = 8 sessions × 2 turns | 16 |
       | repeated sessions | 1 conversation per agent (Claude ABC, Codex BCA) × 4 turns | 8 |
       | minimal-context sessions | `file_selection` × v1 × 2 agents × 2 turns | 4 |
       | answer judging | 16 answers (8 fresh + 6 repeated + 2 minimal) × 2 judges | 32 |
       | calibration controls | {`file_selection`, `runnable_examples`, `go_versions`} × {shallow, adequate} × 2 judges | 12 |
       | **planned total** | | **74** |
       | headroom | Codex trust re-smoke, pre-output retries, judge JSON re-asks | 6 |

       - **Why three control scenarios:** the repeated sessions reach all three
         AUQ scenarios, and every answer that is judged needs a judge that was
         calibrated on its scenario.
       - `working_wait` has no pilot cells. Its controls are written now and
         first judged in t2179_2.
       - **Launch priority under the strict cap:** smoke, then subject sessions,
         then controls, then answer judging.
         - If the headroom runs out, the cap still holds. The remaining calls
           are recorded as `not_run:pilot_stopped:invocation_cap` and reported.
         - Answer judgments are dropped before controls, because an
           uncalibrated judge's scores are unusable anyway.
       - **Claude reported cost:** a $15 stop-launch threshold.
       - **Codex tokens:** a 2M non-cached input+output stop-launch
         threshold.
       - At most 2 in-flight turns may finish past a threshold. Any overrun is
         reported.
     - **Circuit breaker:** 3 consecutive non-valid sessions for one agent give
       `not_run:circuit_open` for that agent's remaining cells.
     - Any cap or threshold stops new launches; each remaining cell is recorded
       as `not_run:pilot_stopped:<cap>`.
     - Partial records always survive.
5. **`rubric.md`** (anchored, frozen before the main run). Each dimension is
   scored 0-3 with written anchors:
   - factual correctness;
   - accessible explanation of the underlying decision;
   - per-option coverage: what the option does, its benefit and its cost.
     Scored **per option**, and "a reason to prefer A" is distinguished from
     "an explanation of B";
   - task-specific recommendation reasoning;
   - unsupported claims;
   - readability;
   - advisory-only adherence (pass/fail);
   - a holistic "could a non-expert choose?" score.

   The **failure flag** is a recommendation without a substantive explanation
   of a non-recommended option. Length, headings, keywords and conformity to
   v4's format are explicitly **not** scored.
6. **`judge.py`** (blinded).
   - Outputs get random ids. Agent self-references and variant hints are
     stripped, and the stripping is logged to the private store.
   - The judge input is the frozen `judge_prompt.md` (sha256 recorded) plus the
     scenario's private `reference.md`.
   - Both agents judge every answer, headless:
     - **Claude:** `-p --tools ""` in an empty scratch dir.
     - **Codex:** `exec -s read-only` in an empty scratch dir. Any
       `command_execution` is recorded on the judgment.

     The output must be strict JSON. A parse failure is retried once and
     counted.
   - A judges' disagreement beyond 1 point on any dimension is flagged
     *disputed*.
   - Scores (numbers) go public; rationales go private.
   - **Calibration controls are per scenario × judge.** Each judge must score
     the shallow control below the adequate one **for that scenario**.
     - If it does not, that judge's scores for that scenario are not used, and
       the result is reported.
     - The pilot's calibration claim covers exactly the three AUQ scenarios it
       ran controls for.
7. **Pilot** (bounded by the pilot allowance above).
   - Cells, as enumerated in the allowance table:
     - `file_selection` × v1-v4 × both agents × 1 rep (8 sessions);
     - 1 repeated-`>q` conversation per agent;
     - 1 minimal-context session (`file_selection`, v1) per agent.

     That is 12 sessions and 16 `>q` answers. The startup_smoke sessions are
     extra and are never samples.
   - Then judge the controls first (12 calls), then every `valid` answer.
   - The validator runs first. Every other class is counted and not judged.
   - Pilot scores are **harness validation only, never evidence**.
   - **Fidelity check:** does v1 reproduce shallow option coverage? Stated as
     observed; *inconclusive* is allowed.
8. **Freeze point and commits.**
   - `matrix.json` holds the proposed main matrix:
     - 4 scenarios (`working_wait` at 3 reps) × 4 variants × 2 agents × 5 reps;
     - minimal context: (v1, v2) × 1-2 scenarios × 2 agents × 5;
     - repeated `>q`: (v1, v2) × 2 agents × 3 conversations;
     - proposed main-run limits.
   - Also frozen: the rubric, the judge prompt and the seeds.
   - `pilot_report.md` gives:
     - measured cost, tokens and latency per call;
     - the projected main-run total;
     - the outcome-class counts;
     - each threshold, its final total and any overrun;
     - harness issues;
     - the fidelity observation.
   - Commit the private store (path-scoped, step "Commits" above), then run
     `python3 aidocs/benchmarks/shadow_q/check_public.py --store <store>`. It
     must pass before the public path-scoped commit.
   - Send t2179_2 a note (`/aitask-note`) about:
     - the public/private split and the store location;
     - the corrected t60_2 provenance (its plan still cites `b523a6bc` for the
       task, and `aidocs/benchmarks/shadow_q/runs|results/` for raw runs);
     - the leak check it must run before each public commit.
   - End by presenting the `pilot_report.md` numbers to the user. **The main
     spend needs explicit approval at the start of t2179_2.** Also ask whether
     to push the aitasks_go store commit.
9. **Tests: `tests/test_shadow_q_harness.py`.** Offline and unittest-style. It
   uses a **fake `claude`/`codex` on PATH** that emits canned stream-json /
   `--json`, and a fake rollout file, a fake store and a fake aitasks_go.
   It checks:
   - **Freezing and layout:**
     - variant span substitution: only the span differs, and an occurs-once
       violation fails;
     - the sandbox ancestor check refuses a parent with `CLAUDE.md` or
       `.claude/`;
     - the sandbox has no `reference.md` and no controls, and no tmux is
       reachable;
     - the per-agent sandbox layout matches each frozen stub's dispatch path;
     - Claude's `--allowedTools` covers every helper that the stubs, Steps 0-2
       and the `>q` bullet invoke. That list is grepped from the frozen
       renders, not hand-copied;
     - a store hash mismatch against `MANIFEST.json` refuses the build.
   - **Recorded metadata:**
     - metadata is parsed from the canned JSON, including the Codex model from
       the fake rollout;
     - a missing model gives `infra_failure:model_unverified`;
     - no account id is ever copied.
   - **Public/private split:**
     - `PublicSink` rejects a non-whitelisted key;
     - `check_public.py` flags a planted ≥ 40-char store line in a public file,
       and passes when there is none.
   - **The validator, against fake traces:**
     - valid;
     - variant not read;
     - a ranged read that misses the span;
     - no capture in the `>q` turn;
     - a capture only in turn 1, which does not satisfy rule 2;
     - permission denied;
     - an unparseable read giving `uncertain_load`.
   - **Greeting order:**
     - a compliant turn 1 (greeting text, *then* capture and `--phase`) passes
       the smoke check with no flag;
     - a capture before the first assistant text sets
       `capture_before_greeting` but does not fail the smoke on its own;
     - both orders are tested in Claude stream-json and in Codex `--json` item
       order.
   - **Helper evidence channel:**
     - traced stub output that matches the served bytes passes;
     - a truncated output passes on the head + tail match, and the match kind is
       recorded;
     - a mismatched output gives `infra_failure:stub_output_mismatch`;
     - commands wrapped in `bash -lc '…'` are still attributed;
     - the replay stubs write nothing: running each one in a read-only bind of
       the sandbox (a `chmod -R a-w` copy) exits 0 with the expected bytes;
     - the stub preflight refuses when a fake `codex sandbox` lets the
       negative-control write succeed, and when the wrapper is missing.
   - **Pilot planner:** `plan_pilot()` derives exactly 74 planned invocations
     (0 + 2 + 16 + 8 + 4 + 32 + 12) from the enumerated cell list, with 6 of
     headroom under the cap of 80. When the cap is reached mid-judging,
     answer judgments are recorded as `not_run:pilot_stopped:invocation_cap`
     before any control is.
   - **Outcome classification and aggregation:**
     - each fake trace maps to its class, including the two `limit_timeout`
       cases split by activity;
     - overall success excludes only `infra_failure` and `uncertain_load` from
       the denominator;
     - the sensitivity line includes them;
     - conditional quality uses `valid` only.
   - **Thresholds:** a mid-turn crossing lets the in-flight turn finish and
     launches nothing after it, and the overrun is recorded. The invocation
     ceiling is never exceeded.
   - **The repeated condition:** records carry `turn_index`, `position` and
     `scenario`; every `>q` is scored; the Latin squares are balanced.
   - **Limits:**
     - a looping fake is killed with `limit_tool_calls`;
     - a hanging fake gets `limit_timeout`, with its process group gone;
     - a pre-output failure is retried exactly once and a completed answer
       never is;
     - a cap trip marks the remaining cells `not_run:pilot_stopped:<cap>`;
     - the circuit breaker opens after 3;
     - a retry is never counted as a sample.
   - **Judging and the matrix:**
     - blinding strips the labels;
     - matrix expansion and order are seed-stable.
   - **Mutant check:** break the occurs-once assert, and the test goes red.

### Post-phase (risk mitigations)

This block runs after step 8's private-store commit and before the public
aitasks commit.

1. [public_leak_audit] Before the public aitasks commit:
   - Keep a private list of distinctive t60_2 identifiers (adapter, function
     and file names taken from the fixtures) in the store as
     `aidocs/shadow_q_store/leak_terms.txt`.
   - Run `python3 aidocs/benchmarks/shadow_q/check_public.py --store <store>`.
     It checks both the ≥ 40-char shared-line rule and the `leak_terms.txt`
     terms (whole-word), against the **staged** public files.
   - Then read `git diff --cached -- aidocs/benchmarks/shadow_q tests/test_shadow_q_harness.py`
     in full, by eye.

   Any hit, or any private-looking text, **blocks** the commit: fix it, re-stage
   and re-run. The test also covers the `leak_terms.txt` rule: a planted term
   is flagged, and an unrelated word that merely contains a term as a substring
   is not.

## Step 9

Archive via the normal Step 9 (Post-Implementation) once the store and public
commits have landed and the pilot numbers have been presented to the user.

## Verification

- `python3 tests/test_shadow_q_harness.py` passes, and its mutant goes red.
- `bash tests/run_all_python_tests.sh --test-dir <dir containing only the new module>`
  is green.
- `check_public.py --store <real store>` passes, and the planted-line test shows
  it can fail.
- The pilot JSONL accounts for all 12 sessions and 16 `>q` answers.
  - Each has exactly one outcome class.
  - Each launched session has a CLI-reported model.
  - At least one `valid` trial per agent shows the intended variant loaded and
    a fresh capture in the `>q` turn.
- The stub preflight passed under the real `codex sandbox` read-only mode, with
  its negative control refused, before the first paid call.
- Total invocations are ≤ 80 (a strict ceiling) against 74 planned. The report
  lists the headroom used, item by item. No invocation launched after a
  threshold was reached, and any in-flight overrun is reported.
- For each of the three AUQ scenarios, each judge that is used scored its
  controls in the right order.
- `git diff --stat` in aitasks shows nothing under `.claude/skills/` or
  `.agents/`.
- The aitasks_go commit touches only `aidocs/shadow_q_store/`.

## Risk

### Code-health risk: low
- All new code sits in an isolated `aidocs/benchmarks/shadow_q/` directory plus
  one offline test module. Production skills are untouched, and the test and
  the `git diff --stat` check assert that.
  · severity: low · → mitigation: none (contained by design)
- The cross-repo store commits land in aitasks_go while another session has
  uncommitted `goengines/` work there (t60_2), so a broad commit could sweep it
  in.
  · severity: low · → mitigation: none (addressed in design: path-scoped
  `add`/`commit -- aidocs/shadow_q_store` only, and no push without
  confirmation)

### Goal-achievement risk: medium
- Headless replay (`-p`/`exec`, stubbed capture) may not reproduce the
  interactive terse pattern, so differences could reflect the harness and not
  the wording.
  · severity: medium · → mitigation: none (addressed in design: real clients
  and instruction stack, a repeated-`>q` condition, and a pilot fidelity check
  that may come out inconclusive)
- The LLM judge's validity (self-preference, length bias).
  · severity: medium · → mitigation: none (addressed in design: blinding,
  cross-agent judges, ordered calibration controls, an independent audit in
  t2179_2, raw outputs kept)
- Quota or cost, or a looping client, could overrun the pilot.
  · severity: low · → mitigation: none (addressed in design: frozen per-turn,
  tool-call and retry limits, a strict 80-invocation ceiling, stop-launch
  thresholds, a circuit breaker)
- A replay startup mismatch, most likely Codex not discovering repo skills in a
  fresh untrusted sandbox path, or a Claude allowlist gap. Responses that never
  loaded the variant would then waste pilot invocations, or look like wording
  trials.
  · severity: low (residual — addressed by inline pre-phase startup_smoke:
  a model-free stub preflight under the real read-only sandbox, then a startup
  smoke turn; the fail-closed validator still classifies any later miss) · → mitigation:
  inline pre-phase startup_smoke
- Private aitasks_go content could leak into the public repo through a
  metadata field, a report quote or a frozen copy, and a push cannot be undone.
  · severity: low (residual — addressed by inline post-phase public_leak_audit,
  on top of the whitelisted public sink and `check_public.py`) · → mitigation:
  inline post-phase public_leak_audit
- Repeated-condition evidence could be discarded, or confounded with scenario
  order.
  · severity: low (residual) · → mitigation: none (addressed in design: every
  `>q` answer is scored, Latin-square rotation, comparison with fresh answers
  to the same scenario)

### Planned mitigations
- timing: pre-phase | name: startup_smoke | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: replay startup mismatch / Codex skill discovery in a fresh sandbox | desc: a model-free stub preflight (stub forms run directly and under `codex sandbox` read-only, with a write negative control), then one startup-only turn per agent; verifies variant load, greeting-before-capture order (a capture after the greeting is allowed), the allowlist, model extraction and trace-matched stub output; stops the pilot on a harness failure
- timing: post-phase | name: public_leak_audit | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: private aitasks_go content leaking into the public repo | desc: before the public commit, run check_public.py with the real store plus the private leak_terms.txt, and read the staged public diff in full; any hit blocks the commit

## Post-Review Changes

### Change Request 1 (2026-11-03 11:40)
- **Requested by user:** five blocking review findings, each to be verified and fixed if valid.
  1. `validate.variant_load` granted coverage without checking that the read succeeded or delivered the bullet.
  2. `match_output` accepted piped/head-only capture output as a fresh capture.
  3. Budget recovery restored only the periodic snapshot, so calls journalled after it were lost.
  4. `run_cli` stopped enforcing the deadline once stdout reached EOF, and waited unbounded.
  5. `check_public` exempted the current contents of `frozen/` and `variants/`, letting a candidate file certify its own text.
- **Changes made:** all five were confirmed, then fixed.
  1. Reads count only if they succeeded *and* their returned text contains every `>q` bullet line; otherwise the result is `uncertain_load`. Skill-tool loads need the injected content.
  2. Rule 2 needs a delivered (`full` or `head_tail`) screen and phase capture. A transformed one is `subject_noncompliance:capture_not_delivered`; head-only is `uncertain_delivery`, excluded from the denominator.
  3. `Budget` writes an fsynced `reserve` record before every launch and a `usage` record after it, to `runs/<batch>/budget_journal.jsonl`. Recovery takes the maximum over the journal, `invocations.jsonl` and the snapshot. Unreported or interrupted calls are charged frozen bounds (`limits.json`: Claude $2.00, Codex 200k tokens).
  4. `run_cli` enforces the deadline over the process lifetime, bounds every wait, and kills leftover group members.
  5. Exemptions come only from HEAD-committed public sources, read from git objects. Raw streams are decoded fail-safe, minus the text from skill-file reads as recorded in the store's own trace.
  - New offline tests cover each finding (75 tests in total).
  - `harness.py classify` re-validated the saved pilot streams: 16/16 still `valid`, 0 changed (`runs/pilot/trials_reclassified.jsonl`).
  - Real-trace negative controls show the checks are not vacuous: a failed read gives `not_loaded`; truncated output gives `uncertain`; a private line planted in a new `frozen/` file gets a hit.
- **Files affected:** `aidocs/benchmarks/shadow_q/{validate.py,harness.py,check_public.py,store.py,judge.py,limits.json,pilot_report.md,README.md}`, `runs/pilot/trials_reclassified.jsonl`, `tests/test_shadow_q_harness.py`.

### Change Request 2 (2026-11-03 12:15)
- **Requested by user:** five further findings, each to be verified and fixed if valid.
  1. Budget recovery took a max over journal and history, so a pending reservation in a pre-journal batch was absorbed: 79 historical calls + 1 reservation recovered as 79.
  2. `summarise` labelled the valid-only rate "overall success". The approved definition requires valid **and** adequate (failure flag false, holistic ≥ 2).
  3. The live Codex tool counter counted only `command_execution`.
  4. Each threshold gated only its own agent's launches.
  5. Per-option judge scores were type-checked but not bounded.
- **Changes made:** all five were confirmed, then fixed.
  1. The journal opens with a `baseline` record (the historical totals for a pre-journal batch). `reserve` and `usage` records share a global `seq`. Recovery: used = max(baseline, highest seq); spend = baseline + matched usage + bound per unmatched reservation.
  2. `compliance_rate` is the valid-only rate. `overall_success` is valid **and** adequate over calibrated judgments (every calibrated judgment flag-free, and mean `could_choose` ≥ 2; unknown counted as not adequate and reported). `scores.json` now carries `failure_flag`. Pilot: compliance 16/16, overall success 14/16.
  3. Tool invocations of every kind (`command_execution`, `web_search`, `mcp_tool_call`, `file_change`; Claude `tool_use`) count once per item id. Recounted pilot maximum: still 8.
  4. Any threshold refuses every new launch, of either agent, subject or judge.
  5. Every option score must be finite and in [0, 3]; otherwise the judgment is re-asked once, then `parse_failed`. All 48 saved pilot judgments pass.
  - Tests for each: 81 in total.
- **Files affected:** `aidocs/benchmarks/shadow_q/{harness.py,validate.py,judge.py,pilot_report.md}`, `runs/pilot/scores.json`, `tests/test_shadow_q_harness.py`.

### Change Request 3 (2026-11-03 12:30)
- **Requested by user:** two findings.
  1. `test_empty_ancestor_dirs_are_flagged_not_refused` asserted the whole `check_ancestors` result, so it failed whenever empty `/tmp/.agents` / `/tmp/.codex` existed.
  2. `run_cli` busy-polled after stdout EOF (`done.wait` returns at once once the event is set).
- **Changes made:** both were confirmed, then fixed.
  1. The test asserts only the fixture parent's entries and keeps the populated-dir refusal. It passes with empty `/tmp/.agents` and `/tmp/.codex` present (reproduced).
  2. After EOF the loop waits on the process with a bounded `proc.wait(timeout=0.2)`. The new test bounds harness CPU while a child sleeps with stdout closed (82 tests).
- **Files affected:** `aidocs/benchmarks/shadow_q/harness.py`, `tests/test_shadow_q_harness.py`.

## Final Implementation Notes

- **Actual work done:**
  - **Public harness** in `aidocs/benchmarks/shadow_q/`:
    - `freeze.py` / `qspan.py` freeze both fast render trees and stubs at aitasks `d46b2bb6`, with the `>q` span at 281-300.
    - `variants/` holds v1-v4 plus hypotheses.
    - `harness.py`: sandboxes, replay stubs, the real CLI runner with limits, the durable budget journal, and the `plan` / `manifest` / `preflight` / `smoke` / `pilot` (`--resume`) / `judge` / `rejudge` / `summary` / `classify` commands.
    - `validate.py`, `judge.py`, `rubric.md`, `judge_prompt.md`, `store.py` and `check_public.py`.
    - `limits.json`, plus `matrix.json` (proposed, unapproved).
    - The numbers-only `runs/pilot/`, `pilot_report.md` and a README.
  - **Private store** in aitasks_go `aidocs/shadow_q_store/`, in 4 path-scoped local commits (`828ee8a`, `9eb52dd`, `90c419b`, `3fcf4bd`). **Not pushed.** It holds:
    - the verbatim instructions and skill listing at `b523a6bc`;
    - the pre-decision t60_2 task (data `e022bc0`);
    - reconstructed screens, references and controls, plus PROVENANCE;
    - the raw streams, judgments and `pilot_notes.md`.
  - **Pilot results:**
    - 79 of 80 invocations (74 planned, +1 Claude re-smoke, +4 judge-fix check);
    - $10.17 Claude cost and 744,563 Codex tokens, with neither threshold reached;
    - 16/16 valid, compliance 16/16, overall success 14/16;
    - calibration 6/6, with 8/16 answers disputed.
  - **Main-run projection:** 872 invocations, about $123 and about 9.0M tokens (in `matrix.json`).
  - **Tests:** `tests/test_shadow_q_harness.py`, 82 offline tests.
- **Deviations from plan:**
  - The private store lives in aitasks_go (user decision during verification).
  - The sandbox also carries aitasks_go's skill listing and the overview doc that `AGENTS.md` points to (fidelity).
  - Claude's allowlist gained read-only utilities (`echo`, `printf`, `true`, `cat`, `head`, `tail`, `wc`, `ls`, `nl`, `sed -n`, `grep`) after the startup smoke.
  - The judge prompt includes the task file the subject could read.
  - The ancestor guard refuses only content-bearing ancestors (and flags empty ones).
  - Task fixtures are stored as `_aitasks/` / `_aiplans/`.
  - `pilot --resume` was added to re-run cells that never launched.
  - The 4-invocation re-judge check used headroom.
- **Issues encountered:** each was found by the preflight, the smoke, the pilot or review, and fixed.
  - The stdin strip needed `LC_ALL=C`.
  - A `dontAsk` compound-command denial (`helper; echo`).
  - Transient empty `/tmp/.agents` and `/tmp/.codex` refused 8 sandboxes before launch (0 invocations lost).
  - aitasks_go's `.gitignore` silently dropped the task copies.
  - The judge could not see the task file.
  - Review rounds 1-3: read and capture delivery, a durable budget with a migration baseline, bounded waits, a non-self-certifying leak check, quality-aware overall success, counting of every tool kind, a global threshold stop, option-score bounds, and the post-EOF busy wait.
- **Key decisions:**
  - Pilot scores are mechanics only.
  - The "adequate" rule: every calibrated judgment flag-free and mean `could_choose` ≥ 2; a flag from either judge counts.
  - Unreported or interrupted calls are charged frozen bounds (Claude $2.00, Codex 200k tokens).
  - Exemptions for the leak check come only from HEAD-committed public sources.
- **Upstream defects identified:** None
- **Notes for sibling tasks (t2179_2):**
  1. Start with the approval gate on `matrix.json` and `pilot_report.md`. Re-check the thresholds, since the task-aware judge prompt adds about 6-8k tokens per judge call.
  2. Decide on web access first: Codex web-searched in every fresh `>q` turn, while Claude had no web tools. The recommendation is to disable it for both.
  3. Use a **new batch name**. The journal and its baseline are per batch.
  4. Raw outputs, rationales and any quote go to the aitasks_go store, never the public repo. Run `check_public.py --staged` before each public commit.
  5. The audit should prioritise factual-correctness disputes: the Codex judge is much stricter there.
  6. Claude usually skipped the Step 0 greeting and pre-explained the AUQ at startup. Treat that as a covariate.
  7. t2179_2's plan still cites `b523a6bc` for the t60_2 task, and `aidocs/benchmarks/shadow_q/runs|results/` for raw outputs. Both are superseded by the split, and a note is sent.
