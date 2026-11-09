---
priority: medium
effort: medium
depends: [t2186_5]
issue_type: feature
status: Ready
labels: [test_infrastructure, testing, skills]
gates: [risk_evaluated]
anchor: 2179
created_at: 2026-11-09 23:10
updated_at: 2026-11-09 23:10
---

## Context

Child 6 of t2186. It builds the prompt-optimization loop:
- analyse a batch's failures;
- propose candidate variants (a gated proposer call, or hand-written);
- evaluate them on a small budget over the tuning scenarios;
- confirm on pre-registered held-out scenarios, with an **achievable** selection rule.

Every spend is approval-gated. The loop never edits a production skill: adoption is always a
separately scoped task.

Parent plan (full design, read it first): `aiplans/p2186_generic_agent_prompt_eval_harness.md`. Parent task:
`aitasks/t2186_generic_agent_prompt_eval_harness.md`.

## Key Files to Modify

- new `aidocs/benchmarks/prompt_eval/pecore/optimize.py`
- edit `pecore/spec.py` (`scenario_split`, `selection`, achievability validation),
  `prompt_eval.py`, `DESIGN_LEDGER.md`, `README.md`
- new `tests/test_prompt_eval_optimize.py`

## Reference Files for Patterns

- t2186_1's `pecore/span.py` (the substitution guard) and `pecore/leakcheck.py`
- t2186_3's decision score and coverage; t2186_5's `pecore/sequential.py`
- `aidocs/benchmarks/shadow_q/variants/README.md` (how variants and hypotheses are written)

## Implementation Plan

### This child: `prompt_eval_optimization_loop` (small gated run optional)

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

## Verification Steps

- The loop runs end-to-end offline; held-out scenarios are never used before confirm.
- The mostly incomplete candidate never wins on exclusions; the perfect-baseline regression
  passes (selectable with sufficient evidence, unselected with insufficient).
- The tests and `run_all_python_tests.sh --test-dir` are green; `check-public --staged` passes;
  `git diff --stat` shows nothing under `.claude/skills/`, `.agents/`, `.opencode/` or
  `aidocs/benchmarks/shadow_q/`.
- Any paid step runs only after a recorded approval of its printed manifest.

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
