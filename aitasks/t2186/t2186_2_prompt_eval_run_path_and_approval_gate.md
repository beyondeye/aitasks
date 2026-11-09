---
priority: medium
effort: high
depends: [t2186_1]
issue_type: feature
status: Ready
labels: [test_infrastructure, testing, skills]
gates: [risk_evaluated]
anchor: 2179
created_at: 2026-11-09 23:09
updated_at: 2026-11-09 23:09
---

## Context

Child 2 of t2186. It builds the **subprocess half** of the core: the generic sandbox and
replay stubs, the Claude/Codex agent adapters (with an OpenCode/agy seam), the bounded runner,
the durable budget, the session loop and generic judging. It also builds the **approval gate**
every paid command passes through. That gate binds a frozen *effective execution manifest*
(content hashes, resolved agents, models, settings and code), not the path names that
describe a run. The shadow_q run path must stay behaviourally equivalent to t2179's: t2187
will run under it.

Parent plan (full design, read it first): `aiplans/p2186_generic_agent_prompt_eval_harness.md`. Parent task:
`aitasks/t2186_generic_agent_prompt_eval_harness.md`.

## Key Files to Modify

- new `aidocs/benchmarks/prompt_eval/pecore/agents/{__init__,base,claude,codex,unsupported}.py`
- new `aidocs/benchmarks/prompt_eval/pecore/{runner,budget,sandbox,replay,experiment,judge,manifest,approval}.py`
- new `aidocs/benchmarks/prompt_eval/specs/shadow_q/stubs/*.body` (verbatim from `harness.STUBS`)
- edit `prompt_eval.py` (commands), `specs/shadow_q/spec.json` (agents, judging, stubs),
  `README.md`, `DESIGN_LEDGER.md`
- new `tests/test_prompt_eval_run.py`

## Reference Files for Patterns

- `aidocs/benchmarks/shadow_q/harness.py`: stubs `:149-225`, sandbox `:197-361`, env/agents/argv
  `:367-470`, runner `:471-627`, `Budget` `:634-790`, usage/model `:797-849`, `Experiment`
  `:857-1178`, preflight `:1246-1294`, `_experiment`/smoke `:1365-1439`
- `aidocs/benchmarks/shadow_q/judge.py` (blinding, strict JSON plus one re-ask, calibration,
  dispute)
- `tests/test_shadow_q_harness.py`: `TestSandbox` `:343-479`, `TestRunner` `:808-1067`,
  `TestJudgingAndPlan` `:1069-1173`
- t2186_1's `pecore/` (spec, trace, rules, store)

## Implementation Plan

### Pre-phase (risk mitigations) — run first

1. [cli_flag_recheck] As the **first implementation step** of t2186_2 (adapters), t2186_3 (web
   flag) and t2186_5 (judge system-prompt arms): run `claude --help`, `codex exec --help` and
   `codex exec resume --help`; confirm that every flag the child's adapter code emits exists in
   the installed version; record `claude --version` and `codex --version` in the child plan; and
   add a test that pins the emitted argv for every agent × turn × option case. A missing or
   renamed flag **stops the child** and is reported to the user, never worked around silently.
   This step is copied verbatim into those three child task files.

### This child: `prompt_eval_run_path_and_approval_gate` (no spend)

The subprocess half: sandboxes, replay stubs, agent adapters, runner, budget, sessions, judging,
and the approval gate every paid command passes through.

1. **`pecore/agents/`** — `base.AgentAdapter`: `subject_argv(turn, prompt, sbx, session_id,
   limits, opts)`, `judge_argv(scratch, limits, opts)`, `parse(raw)` (the child-1 parsers),
   `count_tool_start(line, seen)`, `turn_usage(events)`, `meter` (`usd` | `tokens`) and
   `charge(usage)`, `session_id(events)`, `reported_model(events, session_id)` (Claude: stream
   init; Codex: rollout `turn_context.model`, never copied), `version()`, `reasoning_record()`
   (raw keys only, as `environment_record` does), `allowlist(sbx, helpers, readonly)` (Claude
   `--allowedTools`). `claude.py`, `codex.py` (option `web_search: "disabled"` adds
   `-c web_search="disabled"` to turn 1, resume and judge argv, recorded in session metadata),
   `unsupported.py` (`opencode`, `agy` → `AdapterNotImplemented`). `resolve_agents(spec)` uses
   the spec's `resolve` entries (`{"via":"codeagent","operation":"shadow"}` or
   `{"via":"default_agent_string","operation":"shadow"}`) and records the dry-run invoke line.
2. **`pecore/runner.py`** (`run_cli`, `kill_group`, `RunResult`, adapter tool counter) and
   **`pecore/budget.py`** (`Budget` with per-meter thresholds; the journal format is unchanged
   so shadow_q batches stay recoverable; `limits_block(limits, name)` refuses a missing block).
3. **`pecore/sandbox.py`** + **`pecore/replay.py`** — generic sandbox from the spec
   (instructions on/off per condition, skill listing, the frozen stub and render at the
   dispatch paths, the excerpt or full variant, task fixtures with dir aliases, replay data per
   position, stubs = prelude + the real helper's header + a body file from the spec, scorer-only
   leak guard, `git init` snapshot with the replay dir excluded). shadow_q's bodies move
   verbatim from `harness.STUBS` into `specs/shadow_q/stubs/*.body`. Preflight forms come from
   the spec.
4. **`pecore/experiment.py`** — the session loop driven by the spec's `turns` (per-agent
   startup prompt templates over `vars`; answer turns per scenario position), retries, circuit
   breaker, not-run records, the `_finish` records, the limits block chosen by the caller.
5. **`pecore/judge.py`** — generic judging from the spec's `judging` section: rubric schema
   (scalar dimensions with ranges, the nested `options` list with its sub-dimensions, booleans,
   the composite as a declared sum), blinding regex, prompt template placeholders, controls per
   scenario (`controls.scenarios`: a list or `"all"`), the calibration rule (shallow composite <
   adequate composite), the dispute rule, one re-ask.
6. **`pecore/manifest.py` + `pecore/approval.py`** — the gate binds what will **actually run**,
   not the path names that describe it.
   - **Effective execution manifest.** `plan <command> --batch B [...]` builds it from scratch:
     - the command and its normalised arguments;
     - the spec digest (it already content-hashes every referenced file) and any `--root`
       overrides;
     - the **content sha256 of every input file named on the command line** — `--matrix`, a
       limits file, candidate variants, anything later children add. Content, never the path:
       a same-path edit that keeps the counts still changes the digest;
     - the expanded cell list's digest;
     - the selected limits block's full content;
     - per agent, the **freshly resolved** `agent_string`, `cli_id` and resolve source, the
       dry-run invoke line's sha256, the CLI version string, the raw reasoning record (the Codex
       config keys; the Claude settings keys plus `settings.json`'s sha256), and the adapter
       options (web-search mode, trust override);
     - the sha256 over `pecore/**/*.py` and `prompt_eval.py`, because code changes what runs
       too;
     - the projection numbers.

     It is written as public `runs/<B>/manifest.json` (a whitelisted `manifest` record kind; the
     dry-run line appears as its sha only, as in session records). The printed projection carries
     the `claude -p` billing note. The settings and config paths take env overrides
     (`PE_CLAUDE_SETTINGS`, `PE_CODEX_CONFIG`), and agent resolution takes an injectable resolver,
     so tests never read the real `~/.claude` / `~/.codex` or call the real framework resolver.
   - **Approval.** `approve --batch B --digest <manifest digest> --by "<who/when>"` writes
     `runs/<B>/approval.json`. The agent runs it only after the user approved the printed numbers
     in an `AskUserQuestion`; the record is the durable trace.
   - **Verified before launching.** Every paid command (`smoke`, `judge`, and later `run`,
     `probe`, `optimize evaluate|confirm`) **rebuilds the manifest from scratch** at start: it
     re-resolves the agents, re-reads the files and re-hashes the code. It refuses unless the
     rebuilt digest equals the approved one, printing a key-level diff of what changed. During a
     run, each session start re-checks the CLI version (Claude Code auto-updates). Each session's
     CLI-reported model is compared with the manifest's `cli_id` under a declared, test-pinned
     equality rule. A mismatch stops new launches (`not_run:manifest_changed:<key>`) and is
     reported, never absorbed.
7. CLI: `manifest`, `preflight`, `smoke`, `judge`, `plan`, `approve` (plus child 1's commands).
8. **Run-path equivalence tests** (`tests/test_prompt_eval_run.py`, offline, vs the live
   shadow_q code): stub text for all 5 helpers; the Claude allowlist; `subject_argv` and
   `judge_argv` for every agent × turn × trust case (identical with the web flag off; the exact
   one-flag delta with it on); `subject_env`; the sandbox file list + sha256 for fresh / minimal /
   repeated on the synthetic store (`.git` excluded); judge prompt bytes for an answer and both
   controls; public session/trial/invocation records and budget journal records from a fake-CLI
   session, equal after normalising timestamps, latency and run-id stamps.
9. Ported runner / budget / judge tests (group kill, timeouts, the post-EOF CPU bound,
   tool-call limit, retries, thresholds stop every launch, journal recovery and migration,
   calibration, re-ask, out-of-range scores, cap ordering), plus `opencode` / `agy` failing with
   the seam error.
10. **Approval-binding tests** (all fake, no real resolver or settings file). Each case below
    refuses before any launch, and its diff names the changed key:
    - a paid command with no approval;
    - a **same-path, same-count** matrix edit (one scenario name swapped, cell count unchanged);
    - a changed value inside the selected limits block;
    - a fake resolver that returns a different `cli_id`, then a different `agent_string`;
    - a changed reasoning setting (the fake settings file's effort level);
    - a changed `--version` string from the fake CLI;
    - a one-byte change in `pecore/`.

    Two run-time cases stop new launches with `not_run:manifest_changed:<key>`: a version
    change between two sessions, and a reported model that differs from `cli_id`. An unchanged
    rebuild is accepted.

## Verification Steps

- The run-path equivalence tests (stub text, allowlist, argv, env, sandbox tree, judge prompt
  bytes, public records) pass against the live shadow_q code.
- Every approval-binding case refuses before any launch with a key-level diff; an unchanged
  rebuild is accepted.
- `python3 tests/test_prompt_eval_run.py` and `bash tests/run_all_python_tests.sh --test-dir <dir>`
  are green.
- `check-public --staged` passes; `git diff --stat` shows nothing under `.claude/skills/`,
  `.agents/`, `.opencode/` or `aidocs/benchmarks/shadow_q/`.
- No real CLI is invoked by this child (no spend).

## Context from the parent plan (shared by every t2186 child)

### Facts established during exploration (for the children)

- **shadow_q stays in place, untouched by t2186.** t2179_2 (status `Ready`) still owns that
  directory: its rescoped plan adds `aggregate.py`, edits `matrix.json` / `README.md` and
  `tests/test_shadow_q_harness.py`. Editing it here would collide with that task and would
  also move the "before" side of the equivalence proof. The new core is a **generalized port**;
  the shadow_q spec references shadow_q's frozen inputs by path. Whether shadow_q later becomes
  a thin wrapper over the core is the retrospective child's call, after t2179_2 and t2187.
- **Pinned baselines (immutable, for the equivalence proof):** aitasks `6930f54e2` is the only
  commit touching `aidocs/benchmarks/shadow_q/` and `tests/test_shadow_q_harness.py` (both clean
  at planning). The private store is aitasks_go `aidocs/shadow_q_store/` (`./ait projects resolve
  aitasks_go` → `/home/ddt/Work/aitasks_go`), last commit `3fcf4bd`, clean. The pilot's raw
  streams are in the store at `runs/pilot/<run_id>/turn<N>.stdout.jsonl` + `meta.json`.
- **CLI drift since the pilot:** Claude Code is now **2.1.319** (pilot 2.1.317), codex-cli
  **0.167.0** (pilot 0.166.0). Flags present today (from `--help`): Claude `--system-prompt`,
  `--append-system-prompt`, the `[-file]` forms, `--tools`, `--max-budget-usd`, `--bare`,
  `--exclude-dynamic-system-prompt-sections`, `--setting-sources`; Codex exec `-c`, `-C`,
  `--json`, `--output-schema`, `--ephemeral`, `--skip-git-repo-check`, `-o`. Every adapter flag
  is re-checked against `--help` when its child is implemented (see the pre-phase below).
- **Generic vs specific, by code location** (shadow_q at `6930f54e2`):
  - generic, port as-is: `harness.run_cli`/`kill_group`/`_count_tool_start` (`harness.py:484-627`),
    `Budget` (`:634-790`), `turn_usage`/`codex_noncached_tokens`/`claude_model`/
    `codex_rollout_facts` (`:797-849`), `seeded_order`/`expand_matrix` (`:1218-1239`),
    `pending_cells` (`:1445-1456`), `check_ancestors`/`subject_env` (`:236-255`, `:367-377`);
    `validate.py` parsers (`:90-234`), `unwrap_shell`/`match_output`/`read_coverage`/`covers`
    (`:241-487`), `summarise`/`adequate` (`:731-793`); `judge.py` blinding, strict JSON + one
    re-ask, calibration, dispute; `store.py`; `check_public.py`.
  - shadow-specific, becomes spec data: `qspan.py` (span selector), `freeze.py` (skill/profile/
    agent list), `STUBS` + `expected_for` (`harness.py:157-225`, replay map), the turn script
    (`:988-991`), `_capture_form` + `REPLAY_HELPERS` + `DISPATCH_*` (`validate.py:26-41`,
    `:269-280`), the q-turn rule order (`validate.py:677-728`), `build_minimal` (`:115-125`),
    `pilot_cells`, `AUQ_SCENARIOS`/`LATIN`, `control_scenarios` (hard-coded AUQ, `:899`), the
    `limits["pilot"]` reads (`:1129`, `:1369`).
- **The shadow_q q-turn precedence** that the rule engine must reproduce exactly
  (`validate.py:684-728`): setup failure → an earlier turn dead → dispatched-file sha changed →
  model unverified → this turn dead → cumulative helper infra (`stub_error` >
  `stub_output_mismatch` > `permission_denied`) → **tmux** (`advisory_violation`) → limits
  (`limit_tool_calls`, then `limit_timeout`) → `uncertain_load` / `variant_not_loaded` → capture
  forms (`no_fresh_capture`, flag `capture_forms`) → delivery (`capture_not_delivered` /
  `uncertain_delivery`, flag `capture_delivery`) → `no_answer` → `valid`. Note the tmux rule
  sits **before** the limit checks, so the spec must be able to place `limits` in its ordered
  rule list.
- **Main-matrix counts** (p2179_2, re-derived with `expand_matrix`): 196 sessions (fresh 144,
  minimal 40, repeated 12), 416 subject invocations, 220 answers, 440 answer judgings, 16
  control judgings = **872 invocations**. Pilot per-call costs: Claude judge (task-aware)
  $0.277-0.278; Codex judge 17.6-18.2k non-cached tokens; Claude subject turns $0.295 / $0.60 /
  $0.77 / $0.93; Codex 28.2k / 43.5k / 25.6k / 31.0k.
- **The judge prompt already puts the answer last** (`judge_prompt.md`: rubric → reference →
  screen → task → answer), so Codex's automatic prefix caching can hit when same-scenario calls
  run back to back (the pilot shuffled them). Claude `-p` caches by block: the shared context
  only becomes a reusable cached prefix if it moves into the system prompt (e.g.
  `--append-system-prompt-file`), which changes the judge's structure and so needs recalibration.
- **Prior art — `claude plugin eval`** (Claude Code 2.1.319): case.yaml / prompt.md + graders,
  deterministic "free" graders (e.g. `tool_used`) next to paid LLM graders (default haiku), a
  no-plugin ablation arm, `--max-cost-usd` checked before each launch, `--runs` default 3. **Not
  adopted as a backend**: it runs only Claude, so Claude and Codex cells would not be comparable,
  and it cannot express replay stubs over the real instruction stack. Concepts borrowed: the
  free-vs-paid grader split (deterministic rules first, judges only where needed), a cost
  ceiling checked before every launch (the Budget already does this), and an optional
  no-variant ablation condition.
- **aitask-note** (second spec target): `.claude/skills/aitask-note/SKILL.md` (234 lines,
  `#### Step 2`-`#### Step 4` = the send flow, `:117-210`); Codex reads it through the wrapper
  `.agents/skills/aitask-note/SKILL.md` + `.agents/skills/codex_tool_mapping.md`. Not
  profile-rendered. The explicit-target path (`/aitask-note 42 --from 40 --text "..."`) asks
  nothing, so it runs headless.
- `claude -p` is billed at a higher rate (`aidocs/framework/shell_conventions.md:259-266`):
  every paid command is an explicit opt-in, and its printed projection says so.

### Constraints every child carries (copy into each child task)

- **Real clients only.** Agents and models resolved at run time through
  `aitask_codeagent.sh resolve <op>` and `lib/agent_string.sh`; CLI versions and raw reasoning
  settings recorded, never resolved; the model comes from the CLI's own trace (Claude stream
  init) or rollout (Codex), never from the model's claim; never substitute a model.
- **Never touch a real pane:** strip `TMUX*`, `HERDR_*`, `CLAUDE*`, `CODEX_THREAD*`,
  `CODEX_SANDBOX*`; empty `TMUX_TMPDIR`; a fake pane id; sandboxes outside every repository
  (ancestor check).
- **Public/private split.** Public files hold whitelisted numbers only (`PublicSink`); fixtures
  quoting private projects, raw streams (their init events carry environment details such as
  MCP tool names), answers and rationales go to a private store. The leak check runs before
  every public commit.
- **Every paid invocation is approval-gated**: a paid command refuses unless a recorded approval
  matches the projection it printed (child 2 builds the gate).
- **Adapter seam** for OpenCode and agy: registered names that fail with a clear "not built"
  error. Do not build them.
- **Nothing changes** under `.claude/skills/`, `.agents/`, `.opencode/`, or
  `aidocs/benchmarks/shadow_q/` (t2179_2 owns it). `git diff --stat` checks this per child.
- **Offline tests** use fake `claude`/`codex` on PATH and a synthetic store (pattern:
  `tests/test_shadow_q_harness.py:38-280`), run both as scripts and under
  `bash tests/run_all_python_tests.sh --test-dir <dir>`, with bounded waits only.
- Stdlib only (Python ≥ 3.11 for `tomllib`; the box has 3.14.9).
- Commits: `feature: <desc> (t2186_<n>)`, path-scoped. Store commits: `git -C <root> add
  aidocs/<store subdir>` then `commit -- aidocs/<store subdir>`; never push aitasks_go without
  the user's confirmation.
- **Decisions use the conservative decision score; historical metrics only report.** `uncertain_*`
  outcomes (`uncertain_load`, `uncertain_delivery`, `uncertain_report`, …) stay honest
  classifications, and the historical shadow_q metrics (`compliance_rate`, `overall_success`
  and their sensitivity lines, which exclude them) keep their exact definitions for
  equivalence and reporting. **Every decision** reads the score defined in t2186_3, whose
  denominator keeps eligible unresolved trials, together with its coverage requirement: a
  sequential stop, a candidate selection, a variant comparison, or a t2186_7 investigation
  verdict. No decision rule may read an exclusion-based rate.
- **Keep the design ledger** — `aidocs/benchmarks/prompt_eval/DESIGN_LEDGER.md` (public: ids,
  paths, counts, no quotes). Child 1 creates it; every child appends, in the same commit as the
  code it describes. It is the evidence t2186_7's investigations start from, so an entry is
  written when the event happens, never reconstructed later:
  - **duplicated fix** — a defect fixed in `pecore/` that also exists in the frozen shadow_q copy
    (or the reverse): both locations by path and line, the commit, whether shadow_q was left as is;
  - **behaviour drift** — every difference between `pecore/` and shadow_q behaviour, intended
    (e.g. the web flag) or found later, with the test that pins it;
  - **authoring friction** — awkward configuration, special cases and core changes a spec needed
    (child 4's generality record feeds this section);
  - **lever data** — each cost lever's measured numbers, or "unmeasured" and why, with the source
    batch.

### Target layout (built up across the children)

```
aidocs/benchmarks/prompt_eval/
  README.md               # what it is, spec format, commands, cost model, public/private split
  prompt_eval.py          # CLI: prompt_eval.py --spec <spec dir> <command> ...
  pecore/                 # the core package (stdlib only)
    spec.py span.py trace.py rules.py outcomes.py store.py leakcheck.py classify.py   # child 1
    agents/{base,claude,codex,unsupported}.py runner.py budget.py sandbox.py replay.py
    experiment.py judge.py approval.py                                                 # child 2
    matrix.py aggregate.py probe.py                                                    # child 3
    freeze.py (generic)                                                                # child 4
    sequential.py audit.py                                                             # child 5
    optimize.py                                                                        # child 6
  specs/shadow_q/         # spec.json + stub bodies; named root shadow_q = ../../../shadow_q
  specs/aitask_note/      # child 4
  tools/equiv_shadow_q.py # child 1's byte-identical proof
  DESIGN_LEDGER.md        # duplicated fixes, drift, authoring friction, lever data (all children)
  investigations/         # child 7: PREREG.md + one outcome file per investigation
tests/test_prompt_eval_{core,run,matrix,note_spec,cost,optimize}.py
```

The package is `pecore/` (not `pe/`) so the CLI script never shadows its own package.
