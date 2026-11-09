---
Task: t2186_2_prompt_eval_run_path_and_approval_gate.md
Parent Task: aitasks/t2186_generic_agent_prompt_eval_harness.md
Sibling Tasks: aitasks/t2186/t2186_1_*.md, aitasks/t2186/t2186_3_*.md, aitasks/t2186/t2186_4_*.md, aitasks/t2186/t2186_5_*.md, aitasks/t2186/t2186_6_*.md, aitasks/t2186/t2186_7_*.md
Archived Sibling Plans: aiplans/archived/p2186/p2186_*_*.md
Base branch: main
Output branch: main
---

# t2186_2: Run path: sandbox, replay stubs, agent adapters, runner, budget, judge, approval gate

Child 2 of t2186. The parent plan is `aiplans/p2186_generic_agent_prompt_eval_harness.md`; the task file carries the shared
constraints, the facts established during exploration and the target layout. Read both. Treat any deviation recorded in an archived sibling plan's Final Implementation Notes as authoritative over this plan.

## Context

Child 2 of t2186. It builds the **subprocess half** of the core: the generic sandbox and
replay stubs, the Claude/Codex agent adapters (with an OpenCode/agy seam), the bounded runner,
the durable budget, the session loop and generic judging. It also builds the **approval gate**
every paid command passes through. That gate binds a frozen *effective execution manifest*
(content hashes, resolved agents, models, settings and code), not the path names that
describe a run. The shadow_q run path must stay behaviourally equivalent to t2179's: t2187
will run under it.

### Pre-phase (risk mitigations)

1. [cli_flag_recheck] As the **first implementation step** of t2186_2 (adapters), t2186_3 (web
   flag) and t2186_5 (judge system-prompt arms): run `claude --help`, `codex exec --help` and
   `codex exec resume --help`; confirm that every flag the child's adapter code emits exists in
   the installed version; record `claude --version` and `codex --version` in the child plan; and
   add a test that pins the emitted argv for every agent × turn × option case. A missing or
   renamed flag **stops the child** and is reported to the user, never worked around silently.
   This step is copied verbatim into those three child task files.

## Implementation

### `prompt_eval_run_path_and_approval_gate` (no spend)

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

## Step 9

Archive via the normal Step 9 (Post-Implementation). The parent t2186 auto-archives with its last child.

## Verification

- The run-path equivalence tests (stub text, allowlist, argv, env, sandbox tree, judge prompt
  bytes, public records) pass against the live shadow_q code.
- Every approval-binding case refuses before any launch with a key-level diff; an unchanged
  rebuild is accepted.
- `python3 tests/test_prompt_eval_run.py` and `bash tests/run_all_python_tests.sh --test-dir <dir>`
  are green.
- `check-public --staged` passes; `git diff --stat` shows nothing under `.claude/skills/`,
  `.agents/`, `.opencode/` or `aidocs/benchmarks/shadow_q/`.
- No real CLI is invoked by this child (no spend).

## Risk

### Code-health risk: low
- New code only, plus one test module; the timing-sensitive tests bound every wait.
  · severity: low · → mitigation: none (contained by design)

### Goal-achievement risk: medium
- An approval could bind what describes a run rather than what runs. · severity: high (residual
  low) · → mitigation: none (addressed in design: the effective execution manifest, rebuilt and
  compared before every launch, one test per changed key)
- CLI drift (Claude Code 2.1.319 / codex-cli 0.167.0 against the pilot's 2.1.317 / 0.166.0)
  could drop or rename an emitted flag. · severity: low (residual — addressed by inline
  pre-phase cli_flag_recheck) · → mitigation: inline pre-phase cli_flag_recheck
- Run-path drift from shadow_q would make t2187's runs incomparable with the pilot.
  · severity: medium · → mitigation: none (addressed in design: run-path equivalence tests
  against the live shadow_q code; every intended difference goes in the ledger)

### Planned mitigations
- timing: pre-phase | name: cli_flag_recheck | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: CLI drift silently dropping or renaming an emitted flag | desc: check every emitted flag against the installed `--help`, record both CLI versions, pin the emitted argv in a test; a missing flag stops the child and is reported
