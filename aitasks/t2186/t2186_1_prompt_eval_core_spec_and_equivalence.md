---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [test_infrastructure, testing, skills]
gates: [risk_evaluated]
anchor: 2179
created_at: 2026-11-09 23:09
updated_at: 2026-11-09 23:09
---

## Context

Child 1 of t2186, the generic agent-prompt eval harness. It builds the **offline half** of
the new core under `aidocs/benchmarks/prompt_eval/`: the spec format, the trace parsers, the
rule engine, outcomes, sinks, the leak check and offline re-classification. It also ports the
t2179 shadow `>q` experiment as the first spec, and proves the port does not change the pilot's
classification: `classify` and `summary` must be byte-identical, with no CLI calls. Every later
child builds on this code, and t2186_7 re-runs this proof at the end.

Parent plan (full design, read it first): `aiplans/p2186_generic_agent_prompt_eval_harness.md`. Parent task:
`aitasks/t2186_generic_agent_prompt_eval_harness.md`.

## Key Files to Modify

- new `aidocs/benchmarks/prompt_eval/README.md`, `prompt_eval.py` (CLI), `DESIGN_LEDGER.md`
- new `aidocs/benchmarks/prompt_eval/pecore/{__init__,spec,span,trace,rules,outcomes,store,leakcheck,classify}.py`
- new `aidocs/benchmarks/prompt_eval/specs/shadow_q/{spec.json,README.md}`
- new `aidocs/benchmarks/prompt_eval/tools/equiv_shadow_q.py`
- new `tests/test_prompt_eval_core.py`
- **untouched:** `aidocs/benchmarks/shadow_q/**`, `tests/test_shadow_q_harness.py` (t2179_2 owns them)

## Reference Files for Patterns

- `aidocs/benchmarks/shadow_q/validate.py`: parsers `:90-234`, command analysis `:241-343`,
  read coverage `:356-487`, classification `:494-728`, `adequate`/`summarise` `:731-793`
- `aidocs/benchmarks/shadow_q/qspan.py` (span finder and the only-span-changed proof)
- `aidocs/benchmarks/shadow_q/harness.py`: `build_variant`/`build_minimal` `:98-125`, `STUBS` and
  `expected_for` `:157-225`, `cmd_summary` `:1565-1591`, `reclassify_batch` `:1594-1663`
- `aidocs/benchmarks/shadow_q/store.py`, `check_public.py`
- `tests/test_shadow_q_harness.py`: fake CLI `:38-182`, `write_store` `:185-210`, `Base` `:213-280`,
  `TestValidator` `:603-806`, `TestPublicPrivate` `:481-571`
- `aiplans/archived/p2179/p2179_1_shadow_q_harness_and_pilot.md`: what was built, the review fixes
  (Change Requests 1-3) and the harness issues

## Implementation Plan

### This child: `prompt_eval_core_spec_and_equivalence` (no spend)

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

## Verification Steps

- `python3 aidocs/benchmarks/prompt_eval/tools/equiv_shadow_q.py` prints
  `EQUIV:historical:classify|IDENTICAL|…` and `EQUIV:historical:summary|IDENTICAL|…` and exits 0.
  The current-input report is printed separately. The script and its full output go verbatim
  into this plan's Final Implementation Notes.
- `python3 tests/test_prompt_eval_core.py` passes; the mutation controls go red on the mutated
  spec.
- `bash tests/run_all_python_tests.sh --test-dir <scratch dir holding only the new module>` is
  green (set `-o pipefail`, read the last line).
- `python3 aidocs/benchmarks/prompt_eval/prompt_eval.py --spec aidocs/benchmarks/prompt_eval/specs/shadow_q check-public --staged`
  passes before the public commit.
- `git diff --stat` shows nothing under `.claude/skills/`, `.agents/`, `.opencode/` or
  `aidocs/benchmarks/shadow_q/`.

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
