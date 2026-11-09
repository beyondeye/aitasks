---
priority: medium
effort: medium
depends: [t2186_6]
issue_type: test
status: Ready
labels: [test_infrastructure, testing, skills]
gates: [risk_evaluated]
anchor: 2179
created_at: 2026-11-09 23:10
updated_at: 2026-11-09 23:10
---

## Context

Child 7 of t2186, the trailing retrospective. It records the state of the implementation, then
runs a **post-implementation investigation** of five design trade-offs, with the implemented
design as the baseline:
1. separate port vs shared implementation;
2. declarative rules vs small Python extensions;
3. cached judge structure vs the original prompt;
4. sequential sampling vs fixed repetitions;
5. one judge plus audit vs two judges throughout.

Each is pre-registered before it runs and ends at "retain", "change" or "insufficient
evidence", with a reason. Implementation changes and missing evidence become separately scoped
follow-up tasks; no implementation change lands in this child.

Parent plan (full design, read it first): `aiplans/p2186_generic_agent_prompt_eval_harness.md`. Parent task:
`aitasks/t2186_generic_agent_prompt_eval_harness.md`.

## Key Files to Modify

- new `aidocs/benchmarks/prompt_eval/investigations/{PREREG.md,README.md,I1_*.md … I5_*.md}`
- read: `aidocs/benchmarks/prompt_eval/DESIGN_LEDGER.md` (duplicated fixes, drift, authoring
  friction, lever data)
- scratch worktrees for prototypes (never committed)

## Reference Files for Patterns

- `aiplans/archived/p2186/p2186_*_*.md` (what each sibling built, plus its Final Implementation
  Notes)
- `aidocs/benchmarks/prompt_eval/tools/equiv_shadow_q.py`
- `aidocs/benchmarks/shadow_q/` and `tests/test_shadow_q_harness.py` (for I1)
- the t2179_2 independent audit (`aidocs/shadow_q_store/audit/` in aitasks_go), if t2179_2 has
  landed (for I3)

## Implementation Plan

### This child: `prompt_eval_retrospective`

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

## Verification Steps

- `investigations/PREREG.md` is committed before the first measurement: its commit precedes
  every outcome file's.
- Each of I1-I5 has exactly one outcome (retain, change or insufficient evidence) with a reason.
  Every "change" and every missing-evidence item names a created follow-up task.
- No implementation change lands in this child; paid comparisons ran only after their own
  approval.
- The t2187 note returns `NOTE_APPENDED:`.

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
