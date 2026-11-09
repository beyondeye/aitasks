---
Task: t2186_generic_agent_prompt_eval_harness.md
Base branch: main
Output branch: main
---

# t2186 — Generic agent-prompt eval harness (parent plan: decompose into 7 children)

## Context

t2179 built a rigorous experiment harness in `aidocs/benchmarks/shadow_q/`, but for one
prompt only (the aitask-shadow `>q` bullet). This task generalizes it into reusable
developer tooling under `aidocs/benchmarks/prompt_eval/` that takes **any agent prompt**
(a skill instruction span, a command definition, a procedure step) and can:
1. check it works as expected on replay fixtures, through the real Claude Code and Codex CLIs;
2. measure quality where behaviour alone is not enough (blinded judges, calibration controls, audit);
3. optimize it (compare wording variants, find the simplest reliable one);
4. stay affordable: t2179_2's main run was declined at ≈ $164 Claude / ≈ 11.5M Codex tokens.

**User decisions:**
- (task, 2026-11-03) One task, decomposed at planning; developer tooling only under
  `aidocs/benchmarks/prompt_eval/` — no `ait` subcommand, no `ait setup` whitelisting, no
  website docs. Promotion is a later, separate task, only if justified.
- (planning, 2026-11-09) **7 children**, as listed under Decomposition, including a trailing
  retrospective child.
- (planning) **Second spec = the `aitask-note` send flow** (explicit target), deterministic
  checks, no judge, both agents.
- (planning) **Spend: plan small gated probes.** Children design small paid probes with
  projections; each asks for approval when it runs, and a declined probe records the effect
  as unmeasured.
- (planning, plan review) **t2186_7 carries a post-implementation investigation** of five
  trade-offs, each with the implemented design as the baseline. Criteria are pre-registered,
  offline evidence comes first, and paid comparisons are projected and approved separately.
  Each ends at retain, change or insufficient evidence, with a reason. Changes and missing
  evidence become separately scoped tasks. Consequences: every child keeps a design ledger, and
  child 5's levers ship opt-in with the defaults unchanged.
- (t2179_2 gate, 2026-11-03, carried over) Codex web search **disabled** for subject and judge
  (`-c web_search="disabled"`) in any future main run.

## Facts established during exploration (for the children)

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
  `### Step 2`-`### Step 4` = the send flow, `:117-210`); Codex reads it through the wrapper
  `.agents/skills/aitask-note/SKILL.md` + `.agents/skills/codex_tool_mapping.md`. Not
  profile-rendered. The explicit-target path (`/aitask-note 42 --from 40 --text "..."`) asks
  nothing, so it runs headless.
- `claude -p` is billed at a higher rate (`aidocs/framework/shell_conventions.md:259-266`):
  every paid command is an explicit opt-in, and its printed projection says so.

## Constraints every child carries (copy into each child task)

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

## Target layout (built up across the children)

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

## Decomposition (created after approval: plan mode is read-only)

Each child is created with `aitask_create.sh --batch --parent 2186` through the Batch Task
Creation Procedure, with the full context sections, and gets a plan at
`aiplans/p2186/p2186_<n>_<name>.md`. Siblings auto-depend in order. The parent goes back to
`Ready` (`--plan-approved-at ""`) and its lock is released. No aggregate manual-verification
sibling is expected (no TUI behaviour); the procedure's prompt is still asked.

### Pre-phase (risk mitigations)

1. [cli_flag_recheck] As the **first implementation step** of t2186_2 (adapters), t2186_3 (web
   flag) and t2186_5 (judge system-prompt arms): run `claude --help`, `codex exec --help` and
   `codex exec resume --help`; confirm that every flag the child's adapter code emits exists in
   the installed version; record `claude --version` and `codex --version` in the child plan; and
   add a test that pins the emitted argv for every agent × turn × option case. A missing or
   renamed flag **stops the child** and is reported to the user, never worked around silently.
   This step is copied verbatim into those three child task files.

### t2186_1 — `prompt_eval_core_spec_and_equivalence` (no spend)

The offline half of the core, the spec format, the shadow_q spec, and the byte-identical proof.

1. **`pecore/spec.py`** — load and validate `spec.json` (`spec_version: 1`; unknown keys
   refused; every path required to exist). **Path base, explicit:** a path is either relative to
   the spec file's own directory, or `@<root>/<rel>` against a **named root** declared in the
   spec's `roots` map (each root itself relative to the spec directory). The CLI's
   `--root <name>=<dir>` overrides a named root for one invocation; the override is recorded in
   every output that depends on it, and is what lets the equivalence proof point the shadow_q
   spec at an archived snapshot (step 9). `digest()` =
   sha256 over the canonical spec JSON plus every referenced public file (frozen renders,
   variants, rubric, judge prompt, limits, matrix, stub bodies). The digest is what approvals
   (child 2) and pre-registration (children 5-6) bind to. Sections: `name`, `store`
   (`project`, `subdir`, `env_override`, `manifest`, `manifest_dirs`), `public_runs`, `limits`,
   `matrix`, `seed`, `agents.<name>` (layout: `skills_dir`, `stub`, `render`, `frozen`,
   `dispatch_suffix`, `skill_names`; `resolve`; `invoke_args` — `resolve` is used in child 2),
   `prompt` (`render_file`, `span`, `variants_dir`, `variants`, `baseline`, `freeze`),
   `conditions` (per condition: `instructions` on/off, `excerpt` keep-list or full render),
   `scenarios`, `replay` (helper declarations), `turns`, `vars`, `rules`, `judging`.
2. **`pecore/span.py`** — generic selectors with the occurs-once and only-span-changed proofs
   (port of `qspan.py`, difflib check intact): `bullet` (`start_prefix`; ends before the next
   `- ` / `**` / `#` line; trailing blank lines excluded) and `heading` (`heading` line; ends
   before the next heading of the same or higher level — used by child 4). `excerpt(text,
   keep)` builds the minimal-context render declaratively: shadow_q's keep-list is
   `[{"until_heading":"## Step 0"}, {"section":"## Step 1"}, {"heading_line":"## Step 3"},
   {"span":true}, {"section":"## Guardrail"}]` joined by a blank line plus a trailing newline
   (= `harness.build_minimal`).
3. **`pecore/trace.py`** — `Event`, `Turn`, `parse_claude`, `parse_codex` (verbatim ports,
   in a `PARSERS` registry by agent family that child 2's adapters use), `unwrap_shell`,
   `match_output`, `read_coverage(event, dispatch_suffix, skill_names, nlines)`, `covers`, and
   a generic `helper_calls(command, helper_table)`. The table is built from the spec's `replay`
   declarations: per helper an invocation regex (default
   `(?:[^\s'";|&()]*/)?<dir>/(<name>)`), an off-path pattern (shadow_q:
   `\.aitask-scripts/(aitask_[A-Za-z0-9_]+\.sh)`) and an ordered `form_rules` list, first match
   wins. shadow_q's capture forms: `[["phase",{"has":"--phase"}], ["stdin",{"has":"-"}],
   ["deep",{"has":"--deep"}], ["any_pane",{"has":"--any-pane"}],
   ["explicit_id",{"positional":true}], ["noarg",{}]]`; other helpers → `default`. Keep the
   segment splitting, `piped` detection and the redirect filter exactly.
4. **`pecore/rules.py`** — `classify_session(turns, session_spec, rules)`. The core runs the
   infra checks first (setup, earlier turn dead, sha changed, model unverified, this turn dead,
   cumulative helper infra), always records `web_tools`, then applies the spec's **ordered**
   `q_turn` list. Rule types needed by shadow_q only (child 4 adds the rest):
   - `command_flag` (`flag`, `outcome`): fail when a command-flag fired in this turn;
   - `limits`: `limit_tool_calls` then `limit_timeout`;
   - `variant_load` (turn-1 coverage of the span + delivered bullet lines; `uncertain_load` /
     `subject_noncompliance:variant_not_loaded`);
   - `helper_forms` (`helper`, `require_any`, `require_all`, `outcome`, `flag_on_fail`);
   - `delivery` (`helper`, `groups`, `transformed_outcome`, `else_outcome`, `flag_on_fail`;
     delivered = `full` | `head_tail`);
   - `answer_nonempty`.
   Session-level flags: `command_flags` (`regex` with `unwrap`, or `substring`), `greeting`
   (distinct regex matches ≥ n in a text/final event), `helper_before` (named helpers called
   before the greeting index), `off_path_helpers`, `helper_infra`, `match_kinds`,
   `denied_off_path`. Expected outputs per turn come from the session spec, built from the
   replay map (`expected: {form: "replay:screen" | literal}`).
5. **`pecore/outcomes.py`** — outcome vocabulary, `summarise` (same keys and denominators), and
   `adequate(judgments, rule)` with the rule from the spec (shadow_q: every calibrated judgment
   flag-free and mean `could_choose` ≥ 2; unknown counted as not adequate and reported).
6. **`pecore/store.py`** and **`pecore/leakcheck.py`** — ports of `store.py` (sinks, manifest,
   `resolve_store(project, subdir, env_override)`; core `PUBLIC_FIELDS` kinds plus per-spec
   additions; `MAX_PUBLIC_STR` 160) and `check_public.py` (public paths default to
   `aidocs/benchmarks/prompt_eval/**`, the spec's `public_runs`, and
   `tests/test_prompt_eval_*.py`; HEAD-committed exemptions only; leak terms from the store).
   CLI: `prompt_eval.py --spec <s> check-public [--staged]`.
7. **`pecore/classify.py`** — generic `reclassify_batch(spec, batch, store, runs_public)` (port
   of `harness.py:1594-1663`: rebuild each launched session's dispatched text from the spec,
   refuse on a dispatched-sha or fixture-hash mismatch, rebuild expected outputs from the
   replay map, q-turns from the condition, smoke rows) and `summary(spec, batch)` (port of
   `cmd_summary`, identical output). CLI: `classify --batch B [--write | --out PATH]` (prints by
   default, writes only on request) and `summary --batch B`.
8. **`specs/shadow_q/spec.json`** (+ `README.md`) — declares `"roots": {"shadow_q":
   "../../../shadow_q"}` (from `aidocs/benchmarks/prompt_eval/specs/shadow_q/` that resolves to
   `aidocs/benchmarks/shadow_q/`; `../../shadow_q` would wrongly land in
   `aidocs/benchmarks/prompt_eval/shadow_q/`), and references
   `@shadow_q/{frozen,variants,rubric.md,judge_prompt.md,fixtures/MANIFEST.json,limits.json,
   matrix.json}` and `public_runs: @shadow_q/runs`. Store `aitasks_go` / `aidocs/shadow_q_store`, env override
   `AIT_SHADOW_Q_STORE`, seed 2179, the q-turn rule list in the precedence above, the
   `minimal` excerpt keep-list, the replay map and its expected outputs.
9. **`tools/equiv_shadow_q.py`** — the byte-identical proof. **Both implementations read the
   same pinned, archived inputs**, so the verdict never depends on what later happens to the live
   shadow_q files (t2179_2 edits `matrix.json`'s status field, for example):
   - extract `git archive 6930f54e2 aidocs/benchmarks/shadow_q` and
     `git -C <aitasks_go> archive 3fcf4bd aidocs/shadow_q_store` into a fresh scratch dir outside
     every repository (`check_ancestors`), record both tree ids;
   - **before**: a subprocess running the pinned `harness.py --store <scratch store> classify
     --batch pilot` (it writes only inside the scratch copy) and `summary --batch pilot`;
   - **after**: a subprocess running the live `prompt_eval.py --spec specs/shadow_q
     --root shadow_q=<scratch>/aidocs/benchmarks/shadow_q --store <scratch store>` with
     `classify --out <scratch file>` and `summary` — the new code over the archived inputs;
   - compare bytes; print `EQUIV:historical:classify|IDENTICAL|<sha256>` and
     `EQUIV:historical:summary|IDENTICAL|<sha256>` (or `DIFFERENT` plus the first differing
     record); exit 0 only when both are identical. This is the verdict.
   - **Current-input compatibility, reported separately and never gating:** list each live file
     the spec references as `same` / `changed` against its pinned copy, then run the after side
     once more on the live inputs and report whether its classify/summary still equal the
     historical output (`EQUIV:current:…|SAME|DIFFERS`, with the changed files named). A
     changed `matrix.json` status field therefore shows up as a reported input change, not a
     failed proof.
   - Also report, as information only, whether the committed
     `runs/pilot/trials_reclassified.jsonl` equals the pinned "before" output.
   - The script and its output go verbatim into the child plan's Final Implementation Notes
     (durable closure evidence).
10. **Tests `tests/test_prompt_eval_core.py`** (offline):
    - differential validator: every synthetic turn set from `TestValidator` in
      `tests/test_shadow_q_harness.py` classified by the live `validate.classify_session` and by
      `pecore.rules` → identical;
    - synthetic-run equivalence: a batch produced by the **old** harness under the fake CLIs
      (modes `good`, `no_read`, `no_capture`, `deny`, `mismatch`, `no_answer`, `capture_first`,
      `no_model`, both agents, fresh/minimal/repeated) → old vs new `reclassify_batch` and
      `summary` identical;
    - **mutation control**: a temp copy of the shadow_q spec with two rules swapped (delivery
      before helper_forms) or the tmux rule dropped makes the differential fail on the cases
      built to hit them;
    - span/excerpt: every variant × agent substitution and minimal excerpt equals
      `qspan`/`build_variant`/`build_minimal` over the frozen public renders;
    - spec loader: unknown key, missing path, digest changes when a referenced file changes;
      **the shipped `specs/shadow_q/spec.json` loads from the documented layout** and every
      `@shadow_q/...` path resolves under `aidocs/benchmarks/shadow_q/` (asserted by absolute
      path, so a `../../` slip fails); a `--root shadow_q=<dir>` override redirects every one of
      them and nothing else;
    - equivalence tool on synthetic archives: two scratch "commits" whose referenced inputs
      differ only in `matrix.json`'s `status` give a historical `IDENTICAL` and a current-input
      report naming `matrix.json` as `changed`; a planted classifier difference gives
      `DIFFERENT` and a non-zero exit;
    - leak check: ported planted-line, leak-term, identifier-only, self-certification and
      decoded-stream cases.

### t2186_2 — `prompt_eval_run_path_and_approval_gate` (no spend)

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

### t2186_3 — `prompt_eval_matrix_run_and_aggregate` (no spend)

Closes p2179_2's "Harness gaps a future main run must close first" list, generically.

1. **`pecore/matrix.py`** — `Cell`, `expand_matrix` (latin orders from the spec), `seeded_order`,
   `pending_cells` (launched sessions stand; setup failures / not_run are re-run).
2. **`run --batch B --matrix <file> --limits-block <name> [--resume]`** — runs
   `seeded_order(expand_matrix(...), seed)` through the approval gate; the limits block is chosen
   by command (`smoke` → `smoke`/`pilot`, `run` → `--limits-block`, required). The `--matrix`
   file's content hash and the expanded cell list's digest are manifest keys (child 2), so the
   approval covers the exact cells, not the file name. `--resume` rebuilds the same manifest and
   refuses if anything but the batch's own progress changed. Matrix
   projection in `plan run`: subject invocations per turn index, answers, answer judgings
   (answers × judges), control judgings (control scenarios × 2 × judges), and per-meter cost
   from a reference batch's `invocations.jsonl` means by purpose and turn index.
3. **Web-off probe** — `probe web --batch B`: one Codex invocation (`purpose: probe`, never a
   sample, budget-counted, approval-gated) that asks for a web lookup under the flag. Verdict:
   `WEB_OFF:CONFIRMED` only with positive evidence (a completed turn with activity and zero
   `web_search` items); any `web_search` item → `WEB_OFF:FAILED` (stop and report); no activity
   or an unparseable trace → `WEB_OFF:INCONCLUSIVE`, never "confirmed". The positive contrast is
   cited from the pilot (Codex web-searched in every fresh `>q` turn), not re-bought.
   Aggregation counts `web_search` items per trial.
4. **All-scenario controls** from `judging.controls.scenarios` (shadow_q: `"all"` → 4 scenarios).
5. **Durable answer index** — private `runs/<B>/answers.jsonl`, appended per valid trial under
   the lock with fsync; legacy `answers.json` still read; on `--resume` cross-checked against
   `trials.jsonl` + the private run dirs (a mismatch refuses).
6. **Final record per cell** — each `cell_id`'s last launched session supplies its trials;
   `retried`, never-launched setup failures and superseded `not_run` rows are reported under
   `superseded`, never in a denominator.
7. **`aggregate --batch B`** → public `runs/<B>/summary.json` through a whitelisted `aggregate`
   record kind: per cell / agent / variant / condition / scenario — compliance **and** overall
   success side by side (the writer refuses one without the other), sensitivity lines,
   outcome-class counts, Wilson 95% intervals labelled small-sample, an under-sampled flag
   (classifiable < frozen reps), a gap list against `expand_matrix` (`not_run:<reason>` per
   missing cell, counts by block); conditional quality per judge over valid answers;
   calibration and disputes; covariates (answer chars, `web_search` counts, session flags);
   usage and latency by purpose. Next to them, the decision quantities from step 7a.
7a. **The conservative decision score and coverage** (`pecore/outcomes.py`, new functions; the
   historical `summarise` is untouched, so child 1's equivalence still holds):
   - **eligible** = attempted − `infra_failure:*` − `not_run:*` (harness faults, not the
     prompt's); `uncertain_*` trials **stay eligible**;
   - **decision score** = successes / eligible. A success is `valid`, and also adequate when the
     spec judges. Every unresolved trial therefore counts as **not a success**: an exclusion can
     never raise the score;
   - the **optimistic bound** counts unresolved trials as successes. It is used only to decide
     that a cell has *failed* (child 5);
   - **coverage** = resolved / eligible, where resolved = eligible − `uncertain_*`;
   - `min_coverage` is pre-registered in the spec (proposed 0.8) and bound into the digest. Below
     it, a cell or candidate is "insufficient coverage" and can neither be selected nor stop as a
     success.
   The aggregate emits the decision score, its Wilson interval, the optimistic bound and coverage
   beside the historical metrics, each labelled ("decision" vs "historical, excludes
   uncertain").
8. **Concurrent judges** (2 workers per answer); blind ids assigned from the seeded RNG before
   dispatch.
9. **Tests** (`tests/test_prompt_eval_matrix.py`): the shadow_q main matrix expands to 196
   sessions and the projection to 872 invocations; limits-block selection and refusal of a
   missing block; the web flag in both argv builders; the probe's three verdicts (fake CLI with
   and without `web_search` items, and with no activity); the answer index survives a kill
   mid-batch; final-record-per-cell drops superseded rows; aggregate metrics, Wilson bounds and
   the under-sampled flag on synthetic trials; overall success never emitted without compliance;
   the summary record carries no non-whitelisted key. **Decision-score properties:**
   - moving any trial from a success to `uncertain_*`, or adding an `uncertain_*` trial, never
     raises the decision score (checked over a seeded set of random trial lists);
   - 1 complete + 9 `uncertain` trials score 1/10 with coverage 0.1, so they are "insufficient
     coverage", while the historical `compliance_rate` for the same list still reads 1/1;
   - the historical `summarise` output for the shadow_q pilot is byte-identical before and after
     these functions land.

### t2186_4 — `prompt_eval_aitask_note_spec` (small gated paid run optional)

The second spec, to prove the format is general: a different skill, a non-`.aitask-scripts`
helper (`./ait note`), a heading span, single-turn sessions, no judge.

1. **Generic `pecore/freeze.py`** + `freeze` command — copies the spec's declared source files
   (Claude: `.claude/skills/aitask-note/SKILL.md`; Codex: `.agents/skills/aitask-note/SKILL.md`
   + `.agents/skills/codex_tool_mapping.md` + the Claude file it points to) into
   `specs/aitask_note/frozen/`, refuses dirty sources, records `FREEZE.json` (repo sha, per-file
   sha256, the span per agent) and writes the baseline variant.
2. **`specs/aitask_note/spec.json`** — span `heading` `### Step 4 — Report both outcomes` (one
   alternative variant, to exercise heading spans); instructions = the public
   `seed/aitasks_agent_instructions.seed.md` as `CLAUDE.md`/`AGENTS.md`; synthetic public fixtures
   under `specs/aitask_note/fixtures/` (manifest-pinned); raw streams to a private store
   (aitasks_go `aidocs/prompt_eval_store/aitask_note/`).
3. **Replay**: an `ait` stub at the sandbox root and an `.aitask-scripts/aitask_note.sh` stub
   (one logical writer). Turn: `/aitask-note 42 --from 40 --text "<line>"` (Codex:
   `$aitask-note ...`). Each scenario declares its writer output, whether that output is
   **id-bearing** (and the id), and the outcome the report must convey. That last part is what the
   variant under test, `### Step 4 — Report both outcomes`, governs:

   | scenario | writer stdout (stderr) | id-bearing | report must convey | report must not claim |
   |---|---|---|---|---|
   | `live_none` | `NOTE_APPENDED:n7f3a\|aitasks/t42_x.md`, `LIVE_NONE:no_holder` | yes (`n7f3a`) | the note was written (durable success); live delivery unavailable | delivered / received / read / acknowledged; a failure or partial failure |
   | `uncommitted` | `NOTE_APPENDED_UNCOMMITTED:n7f3a\|aitasks/t42_x.md\|commit_failed` (stderr: the recovery command) | yes (`n7f3a`) | written but **not committed**; the recovery command | committed / sent successfully; delivered or read |
   | `target_missing` | `NOTE_TARGET_MISSING:42` | **no** | nothing was written; the target was not found | a note was sent or appended; any note id |

4. **New rule types** in `pecore/rules.py`, each with unit tests:
   - `helper_count` — the writer exactly once: no resend after `LIVE_NONE`, no retry after a
     terminal line;
   - `helper_args` — target `42`, `--from 40`, `--with-live`, and a body via `--text` or
     `--file -`; no other target id on any call;
   - `forbidden` commands — tmux `send-keys`, an edit of `aitasks/t42*`, `ait create` /
     `aitask_create.sh`, reading the live-delivery adapter after `LIVE_NONE`;
   - `report` — **scenario-dependent**, driven by the table above:
     - `require_id` applies **only when the scenario's output is id-bearing**: the exact id token
       must appear. Its absence gives `subject_noncompliance:report_missing_id`. `target_missing`
       has no id requirement, and naming an id there counts as a forbidden claim.
     - `require` / `forbid` list **claim classes** (`durable_success`, `live_unavailable`,
       `delivered_or_read`, `committed`, `uncommitted`, `recovery_given`, `nothing_written`).
       These are pre-registered lexical detectors in `specs/aitask_note/claims.json`, included in
       the spec digest.
     - Detection skips code spans and raw protocol lines (`^[A-Z_]+:`), so an answer that quotes
       `NOTE_APPENDED_UNCOMMITTED:` is not read as a success claim. The quoted line still counts
       for the id.
     - Detection is negation-aware within a sentence: "not delivered live" and "has not read it"
       are not `delivered_or_read` claims.
     - A forbidden class found **unambiguously** (non-negated) gives
       `subject_noncompliance:false_outcome_claim:<class>`.
     - A required class that is not detected, or an ambiguous sentence (a claim and its negation
       together), gives `uncertain_report`: excluded from the compliance denominator and reported
       like `uncertain_delivery`. A lexical miss never becomes a noncompliance verdict.
     - Each firing detector's sentence goes to the private store, so a disputed verdict can be
       reviewed.
   - Flag only: an `aitask_relations.sh related-work` call on the explicit-target path.

   The detectors are validated before any run by a labelled corpus test. It covers each class's
   positive, negated, future-tense ("will be read when the task is picked") and quoted-protocol
   forms. The test reports per-class precision and recall and fails below the pre-registered
   bounds.
5. **Generality record** in the spec README and the ledger's authoring-friction section: every
   core change this spec needed, every special case, and whether any needed a Python hook (= a
   format gap, fixed in the core here, not worked around).
6. **Tests** (`tests/test_prompt_eval_note_spec.py`), fake-CLI end-to-end for both agents and all
   three scenarios:
   - the compliant path is `valid` in each scenario; for `target_missing` that answer carries no
     id at all (the id requirement is conditional);
   - resend, a missing `--from`, tmux and a task edit each give their own class;
   - **negative traces with correct helper calls and correct ids but wrong outcome claims**, each
     with its expected `false_outcome_claim:<class>`:
     - `live_none` + "delivered; the agent has read note n7f3a";
     - `uncommitted` + "note n7f3a sent and committed";
     - `target_missing` + "note sent to t42" (and a variant naming an invented id);
   - negation controls stay `valid`: `live_none` + "n7f3a written; not delivered live; the
     recipient has not read it";
   - a missing id in an id-bearing scenario gives `report_missing_id`;
   - an answer that omits the live lane gives `uncertain_report`, not `valid`.
7. **Optional paid run** (gated): `plan run` for 2 agents × 3 scenarios × 2 reps (12
   single-turn sessions; projected from one smoke per agent), approval prompt, `run`,
   `aggregate`. Declined → the offline tests are the evidence (task acceptance allows this).

### t2186_5 — `prompt_eval_cost_levers` (small gated probe)

**Every lever ships as an opt-in mode. The defaults stay as they are:** two judges throughout,
fixed repetitions, the original (v1) judge-prompt structure. This child builds and measures; it
recommends no new default. Whether an alternative should become the default is decided by
t2186_7's pre-registered investigations, against evidence this child alone cannot provide.
Passing calibration controls is recorded as necessary, never as proof of equivalence.

1. **Cache-grouped judging** — answer judgings grouped by scenario (seeded order within a group),
   blind ids pre-assigned. A pre-registered judge-prompt v2 for Claude moves the shared context
   (rubric, reference, screen, task) into the system prompt (`--append-system-prompt-file`,
   flag verified) with the answer alone in the user message; same text bytes, so calibration
   controls are re-run under v2 before v2 scores anything. Codex keeps the v1 structure (the
   answer is already last) and only gains grouping. A second Claude arm,
   `--system-prompt-file` (replacing Claude Code's default system prompt), is offered in the
   same probe as a separate pre-registered option.
2. **Probe** (approval-gated, ≈ 4-6 Claude + 4-6 Codex judge calls on the pilot's controls):
   measure cost, `cache_read_input_tokens` / `cached_input_tokens`, and calibration under each
   arm against the pilot's $0.277 / 18k per call. Declined → recorded unmeasured. The probe keeps
   every per-call verdict (private) and its numbers (public, `DESIGN_LEDGER.md` lever data), so
   t2186_7 can reuse them as part of, never all of, its structure comparison.
3. **Sequential sampling** — `pecore/sequential.py`: a pre-registered rule in the spec
   (`sampling: {min_reps, max_reps, wave, rule: "wilson_decided", target, z}`, plus t2186_3's
   `min_coverage`), bound into the approval digest. `run` schedules reps in waves and decides per
   cell, **only on t2186_3's decision quantities, never on an exclusion-based rate**:
   - **stop as success** only when the decision score's Wilson lower bound ≥ target **and**
     coverage ≥ `min_coverage`;
   - **stop as failure** only when even the optimistic bound's Wilson upper bound < target;
   - otherwise continue to `max_reps`. A cell that ends below `min_coverage` is reported as
     "insufficient coverage", never as decided;
   - the target must be achievable: < 1, and reachable by an all-success cell at `max_reps`. The
     spec loader refuses otherwise.

   The effect is measured offline by seeded simulation: expected reps saved and the actual
   decision error rate across true rates, unresolved rates and look counts. No spend.
4. **Single judge + sampled audit** — `pecore/audit.py`: the primary judge scores every answer;
   the second judge scores a pre-registered audit sample (every borderline answer — any failure
   flag, or a `could_choose` mean within a margin of the threshold — plus a seeded fraction of the
   rest); controls for both. A first offline look against the pilot's two-judge `scores.json`
   (16 answers): agreement, missed disagreements and false passes against the two-judge verdict,
   Wilson intervals, labelled n = 16 and **not sufficient for a default**; projected savings for
   the shadow_q main matrix.
5. **Tests** (`tests/test_prompt_eval_cost.py`): grouping order and blind-id stability, v2
   prompt bytes = v1 bytes split at the declared boundary, recalibration before scoring, the
   stopping rule on synthetic streams, simulation determinism, audit-sample selection and the
   pilot-derived agreement numbers. **Exclusion regression:** a mostly incomplete cell is fed
   repeating waves of 1 complete answer + 9 `uncertain_report` answers. It never stops as a
   success at any wave up to `max_reps`, though its historical `compliance_rate` is 100%. A
   consistently complete cell at the same true rate stops as a success.

### t2186_6 — `prompt_eval_optimization_loop` (small gated run optional)

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

### t2186_7 — `prompt_eval_retrospective`

#### Part A — state of the implementation

1. An effect table from `DESIGN_LEDGER.md`: each cost lever measured or unmeasured, with its
   numbers and source batch.
2. Re-run the child-1 equivalence proof at HEAD (still identical?) and the full offline suite.
3. Whether to promote the harness to an `ait` command: recommend only; a promotion is its own,
   separately scoped task.

#### Part B — post-implementation investigation

**The implemented design is the baseline.** Each investigation asks whether an alternative would
be better, and where the evidence to decide is still missing, it creates a scoped follow-up task
to collect it instead of guessing.

**Protocol — the same for all five:**
1. **Pre-register before running anything.** For each investigation, record in
   `aidocs/benchmarks/prompt_eval/investigations/PREREG.md`:
   - the baseline;
   - the alternative;
   - the evidence needed;
   - the estimated effort and spend;
   - the decision criterion.

   Commit it before the first measurement. The criteria proposed below are starting points that
   this child finalizes in PREREG.md; a criterion is never changed after its data is seen.
2. **Offline evidence first.** Use the ledger, saved batches, simulation, replay and prototypes
   in scratch worktrees (not committed).
3. **Paid comparisons separately.** Each one gets its own `plan` projection and its own approval
   prompt. A declined comparison leaves that investigation at "insufficient evidence".
4. **One outcome per investigation:** "retain", "change" or "insufficient evidence", each with
   its reason, written to `investigations/<id>.md`. Public files hold numbers and ids; quotes go
   to the private store.
5. **Changes are separate tasks.** Any implementation change becomes a separately scoped task,
   never an edit in this child. Missing evidence becomes a scoped follow-up task that carries
   its PREREG entry verbatim.

**I1 — Separate port vs shared implementation**

- **Baseline:** `pecore/` is a separate port, and shadow_q stays as a frozen copy.
- **Alternative:** shadow_q becomes a thin wrapper that runs its commands through `pecore/` with
  the shadow_q spec.
- **Evidence:**
  - The ledger's duplicated fixes and behaviour drift across children 1-6: counts, kinds, and
    which ones were intended.
  - A thin-wrapper prototype in a scratch worktree. It must pass the child-1 equivalence proof
    on the pinned pilot, the run-path equivalence tests, and `tests/test_shadow_q_harness.py`
    (with only import or argv adaptations, each listed).
  - Reproducibility of the original experiment: the pinned `git archive 6930f54e2` route must
    still rebuild the pilot classification byte for byte, whichever copy is live.
  - The status of t2179_2 and t2187, the tasks that own or use shadow_q.
- **Effort and spend:** medium; no spend.
- **Proposed criterion:**
  - **Change** if (a) the ledger shows at least one unintended drift or at least two duplicated
    fixes, (b) the prototype passes all three equivalence checks, and (c) t2179_2 has landed.
  - **Retain** if the ledger shows neither.
  - **Insufficient evidence** otherwise.

**I2 — Declarative rules vs small Python extensions**

- **Baseline:** a declarative spec over the core rule library.
- **Alternative:** a small extension interface. A spec-local module registers rule functions
  with one fixed signature over turns and helper facts, and each returns an outcome or nothing.
- **Evidence:**
  - From the ledger's authoring-friction section (child 4's generality record): awkward
    configuration, special cases, and core changes a spec forced.
  - Then **one additional, structurally different prompt**, authored both ways, offline with
    fake CLIs. A candidate is a multi-turn procedure step that branches on a helper's last line,
    e.g. the premise-staleness check (silent on `SKIP`, asks on `ASK_STALE`). It is unlike both
    the shadow `>q` bullet and the single-turn note send.
  - Ease of **authoring**: lines and files written, core changes needed.
  - Ease of **debugging**: time and the steps needed to localise a planted rule fault, and the
    quality of the error message.
  - Ease of **maintaining**: files touched for one rule change, and test coverage reachable
    without the core.
- **Effort and spend:** medium to high; no spend. Building both versions of the third prompt is
  likely its own scoped follow-up task, which this child creates with the PREREG entry.
- **Proposed criterion:**
  - **Change** (add the interface) if the declarative version of the third prompt needs a core
    change or a special case that the extension version keeps in one self-contained file, and
    the planted fault is localised at least as fast.
  - **Retain** if the declarative version needs no core change and is no harder to debug.
  - **Insufficient evidence** otherwise.

**I3 — Cached judge structure vs the original prompt**

- **Baseline:** the original (v1) judge-prompt structure.
- **Alternative:** the cached structure (v2, shared context in the system prompt), and the
  system-prompt-replacement arm if child 5 measured it.
- **Evidence:** both structures on **the same blinded answers**, including the difficult ones
  (the pilot's 8 disputed answers, borderline `could_choose` means, flagged answers). Measure:
  - cost per call;
  - per-dimension score deltas;
  - adequacy-verdict flips.

  All of it is measured against **independently reviewed reference judgments**, recorded
  privately before either arm's scores are read. A candidate source is the t2179_2 independent
  audit, if it has landed; otherwise a fresh blind review of the reference set. Child 5's probe
  data is reused but is not sufficient. **Passing calibration controls alone does not establish
  equivalence.**
- **Effort and spend:**
  - an offline part (reuse child 5's verdicts);
  - a paid comparison, projected separately: about 16 answers × 2 structures × the Claude judge,
    roughly $6-9 at pilot prices, re-derived at the gate.

  Codex's structure is unchanged, so it is compared on grouping cost only.
- **Proposed criterion:**
  - **Change** (adopt v2 as the default) only if, against the reference, v2's adequacy
    disagreements are no more than v1's, no difficult case flips without reference support, and
    the cost per call drops by a pre-registered margin.
  - **Retain** if v2 is worse on any of those.
  - **Insufficient evidence** without a reference set or with too few difficult cases.

**I4 — Sequential sampling vs fixed repetitions**

- **Baseline and alternative:** the two modes child 5 implemented. Fixed repetitions is the
  default, sequential sampling is opt-in.
- **Evidence:**
  - Seeded simulation over true success rates, concentrated **near the acceptance threshold**
    (target ± 0.1).
  - **Replayed data**: bootstrap resampling of real per-trial outcomes from the saved batches
    (the pilot; child 4's run if one was approved).
  - Metrics, all on the decision score: expected repetitions (cost), wrong-decision rate,
    undecided-at-max rate, insufficient-coverage rate. Simulations include non-zero unresolved
    rates, so the comparison covers cells that answer incompletely.
  - Whether fixed repetitions give a better reliability/cost trade-off for **small experiments**
    (≤ 5 reps per cell).
- **Effort and spend:** low; no spend.
- **Proposed criterion:**
  - **Change** (make sequential the default for a stated size class) if near the threshold its
    wrong-decision rate stays within a pre-registered δ of fixed repetitions' and it saves at
    least a pre-registered fraction of repetitions.
  - **Retain** fixed repetitions where either fails, including the small-experiment class if
    savings there are below the margin.
  - **Insufficient evidence** if the replay data is too thin to confirm the simulation (stated).

**I5 — One judge plus audit vs two judges throughout**

- **Baseline:** two judges throughout.
- **Alternative:** one judge plus the pre-registered audit sample.
- **Evidence:**
  - **Missed disagreements**: answers the two judges dispute that the audit did not sample.
  - **False passes**: audit-mode "adequate" where the two-judge rule says "inadequate".
  - Aggregate agreement.
  - All of it on **evidence beyond the 16-answer pilot**: a two-judge dataset of a
    pre-registered minimum size (proposed ≥ 60 answers). shadow_q has no more answers today, and
    aitask_note has no judge. So this child runs the replay on the pilot as a first look,
    labelled insufficient, and creates a scoped follow-up task that runs once such data exists.
    It also notes t2187 to judge with two judges throughout, so its run can be that data.
- **Effort and spend:** low offline; the data comes from t2187, or from a separately projected
  re-judging.
- **Proposed criterion:**
  - **Change** (make audit mode the default) only if, on at least the minimum answer count, the
    false-pass rate's upper Wilson 95% bound and the missed-disagreement rate stay within
    pre-registered bounds, and judging cost drops by the pre-registered margin.
  - **Retain** two judges if a bound fails.
  - **Insufficient evidence** below the minimum count.

#### Part C — hand-off

- A summary table in `investigations/README.md`: investigation → outcome → reason → follow-up
  task.
- Send t2187 a note (`./ait note 2187 --from 2186_7`) with:
  - the concrete commands;
  - the I3/I5 status, and the request to judge with two judges throughout;
  - the CLI-version drift.

  t2187 stays `Postponed` until the user decides to spend.

## Step 9

Each child archives through the normal Step 9 (Post-Implementation). The parent auto-archives
when its last child is archived.

## Verification

- t2186_1:
  - `tools/equiv_shadow_q.py` prints `EQUIV:historical:…|IDENTICAL` for classify and summary,
    both implementations reading the archived inputs; the current-input report is printed
    separately;
  - the shipped spec loads from the documented layout with every `@shadow_q/` path under
    `aidocs/benchmarks/shadow_q/`;
  - `python3 tests/test_prompt_eval_core.py` passes and its mutation controls go red on the
    mutated spec.
- t2186_2:
  - the run-path equivalence tests pass;
  - every approval-binding case refuses before any launch with a key-level diff;
  - an unchanged rebuild is accepted.
- t2186_3: 196 sessions / 872 invocations for the shadow_q main matrix; the aggregate never emits
  overall success without compliance; the decision score is monotone under exclusions; the
  pilot's historical `summarise` output is unchanged.
- t2186_4:
  - the aitask_note spec runs end-to-end under fake CLIs for both agents;
  - every wrong-outcome-claim trace gets its `false_outcome_claim:<class>` despite correct
    helper calls and ids;
  - the negation controls and the id-less `target_missing` answer stay `valid`;
  - the claim-detector corpus test meets its pre-registered bounds;
  - the generality record lists every core change.
- t2186_5: each lever measured or recorded unmeasured; simulation and pilot-calibration numbers
  reproducible from committed inputs; the mostly incomplete cell never stops as a success.
- t2186_6: the loop runs end-to-end offline; held-out scenarios are never used before confirm;
  the mostly incomplete candidate never wins on exclusions.
- t2186_7: `investigations/PREREG.md` is committed before the first measurement (its commit
  precedes every outcome file's); each of I1-I5 has exactly one outcome — retain, change or
  insufficient evidence — with a reason; every "change" and every missing-evidence item names a
  created follow-up task; no implementation change lands in this child.
- Every child: `bash tests/run_all_python_tests.sh --test-dir <dir with its new module>` green;
  `prompt_eval.py check-public --staged` passes before each public commit; `git diff --stat`
  shows nothing under `.claude/skills/`, `.agents/`, `.opencode/` or `aidocs/benchmarks/shadow_q/`.

## Risk

### Code-health risk: low
- All new code lives under `aidocs/benchmarks/prompt_eval/` plus new `tests/test_prompt_eval_*`
  modules; production skills and shadow_q are untouched, checked by `git diff --stat` per child.
  · severity: low · → mitigation: none (contained by design)
- The port duplicates ≈ 3-4k lines of shadow_q, which stays as the frozen t2179 record, so two
  copies can drift. · severity: low · → mitigation: none (addressed in design: shadow_q is
  frozen evidence owned by t2179_2; the retrospective child decides on a thin-wrapper retirement
  after t2179_2 and t2187)
- The declarative spec and rule format could grow into an ad-hoc DSL that is hard to change.
  · severity: low · → mitigation: none (addressed in design: a rule type is added only when a
  spec needs it — shadow_q in child 1, aitask_note in child 4 — each with unit tests, and the
  generality record reports any hook)
- Timing-sensitive runner tests (hang, timeout, CPU bound) could flake under the xdist lane.
  · severity: low · → mitigation: none (addressed in design: the ported tests bound every wait,
  and each child runs its module under `run_all_python_tests.sh --test-dir`)

### Goal-achievement risk: medium
- Byte-identical equivalence may be out of reach if a shadow_q rule is subtler than the rule
  types (the tmux-before-limits order, delivery kinds, smoke rows). · severity: medium
  · → mitigation: none (addressed in design: the precedence is recorded above, the ordered rule
  list can place `limits`, a per-case differential test plus mutation controls; any difference
  is explained, never accepted silently)
- The spec format could fit shadow_q only. · severity: medium · → mitigation: none (addressed
  in design: the second spec differs on every axis — skill, helper kind, span kind, turn count,
  no judge — and its gaps are fixed in the core in child 4)
- CLI drift (Claude Code 2.1.319 and codex-cli 0.167.0, against the pilot's 2.1.317 / 0.166.0)
  could rename or drop a flag such as `--permission-prompts` or the `web_search` config key; a
  silently ignored flag would make the web-off condition false. · severity: low (residual —
  addressed by inline pre-phase cli_flag_recheck, plus the web probe's positive-evidence verdict)
  · → mitigation: inline pre-phase cli_flag_recheck
- Cost levers may stay unmeasured if the user declines the probes, and the cache lever changes
  the judge's structure, so its scores are not directly comparable with the pilot's.
  · severity: low · → mitigation: none (addressed in design: the acceptance allows "recorded as
  unmeasured"; the v2 judge prompt is pre-registered and recalibrated before it scores)
- Sequential stopping with repeated looks inflates the error rate. · severity: low
  · → mitigation: none (addressed in design: a conservative z, and the simulation reports the
  actual error rate)
- The optimization loop could overfit the tuning scenarios, and few scenarios mean low power.
  · severity: medium · → mitigation: none (addressed in design: a pre-registered held-out split
  and selection rule; the report states the power)
- An approval could be bound to what describes a run (paths, counts) rather than what actually
  runs (file contents, the resolved model, settings, code), so a same-path edit or a
  re-resolved agent would spend under a stale approval. · severity: high (residual low)
  · → mitigation: none (addressed in design: child 2's effective execution manifest, rebuilt and
  compared before every launch and re-checked per session, with a test per changed key)
- The second spec's reporting checks are lexical, so a detector could pass a false outcome claim
  or flag a correct, differently worded answer. · severity: medium (residual low)
  · → mitigation: none (addressed in design: scenario-dependent claim classes, a conditional id
  requirement, negation- and quote-aware detection validated on a labelled corpus,
  `uncertain_report` instead of noncompliance for a missed required claim, and negative traces
  with correct calls and ids but wrong claims)
- Rates that exclude unresolved trials could reward incomplete answers in stopping or selection:
  1 complete + 9 uncertain reads as 100%. · severity: high (residual low) · → mitigation: none
  (addressed in design: the uncertain classes stay, the historical metrics stay for reporting,
  but every decision reads t2186_3's conservative decision score plus a coverage requirement,
  with exclusion regressions in t2186_3, t2186_5 and t2186_6)
- The trade-off investigations could be decided on thin or post-hoc evidence (criteria tuned
  after the data, a lever "proven" by calibration controls alone, a default chosen from 16
  answers). · severity: medium · → mitigation: none (addressed in design: child 5 ships every
  lever opt-in with the defaults unchanged; t2186_7 commits PREREG.md before any measurement,
  requires independent reference judgments for I3 and a minimum answer count for I5, and ends
  each investigation at "insufficient evidence" plus a scoped follow-up task when the evidence is
  missing)
- Private content could leak through the new public outputs (aggregate summaries, candidate
  variants, proposer output). · severity: low · → mitigation: none (addressed in design:
  whitelisted record kinds, candidates private until the leak check passes, `check-public`
  before every public commit)

### Planned mitigations
- timing: pre-phase | name: cli_flag_recheck | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: CLI drift (Claude Code 2.1.319 / codex-cli 0.167.0 vs the pilot) silently dropping or renaming an emitted flag, e.g. the web_search config key | desc: first step of t2186_2, t2186_3 and t2186_5 — check every emitted flag against the installed `--help`, record both CLI versions, pin the emitted argv in a test; a missing flag stops the child and is reported
