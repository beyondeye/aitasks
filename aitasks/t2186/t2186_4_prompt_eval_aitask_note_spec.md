---
priority: medium
effort: medium
depends: [t2186_3]
issue_type: feature
status: Ready
labels: [test_infrastructure, testing, skills]
gates: [risk_evaluated]
anchor: 2179
created_at: 2026-11-09 23:09
updated_at: 2026-11-09 23:09
---

## Context

Child 4 of t2186. It writes the **second spec**, to prove the format is general. It differs from
shadow_q on every axis:
- a different skill, the `aitask-note` send flow with an explicit target;
- a non-`.aitask-scripts` helper (`./ait note`);
- a heading span;
- single-turn sessions;
- no LLM judge.

Its checks are deterministic. They include **scenario-dependent reporting checks**, because the
variant under test governs how the durable and live outcomes are reported. A small paid run is
optional and goes through the approval gate. Without approval, the offline fake-CLI tests are
the evidence.

Parent plan (full design, read it first): `aiplans/p2186_generic_agent_prompt_eval_harness.md`. Parent task:
`aitasks/t2186_generic_agent_prompt_eval_harness.md`.

## Key Files to Modify

- new `aidocs/benchmarks/prompt_eval/pecore/freeze.py` (generic freeze)
- edit `pecore/rules.py` (`helper_count`, `helper_args`, `forbidden`, `report`), `pecore/trace.py`
  (helpers outside `.aitask-scripts/`), `prompt_eval.py`, `DESIGN_LEDGER.md`
- new `aidocs/benchmarks/prompt_eval/specs/aitask_note/{spec.json,claims.json,README.md,fixtures/,frozen/,stubs/,variants/}`
- new `tests/test_prompt_eval_note_spec.py`

## Reference Files for Patterns

- `.claude/skills/aitask-note/SKILL.md` (Steps 2-4 at `:117-210`), `.agents/skills/aitask-note/SKILL.md`,
  `.agents/skills/codex_tool_mapping.md`
- `.aitask-scripts/aitask_note.sh`: the real output grammar. Verify every `NOTE_*` / `LIVE_*`
  line the stubs serve against the real helper; capture real outputs for the fixtures rather
  than inventing them.
- `aidocs/benchmarks/shadow_q/freeze.py` (freeze pattern), `seed/aitasks_agent_instructions.seed.md`
- t2186_1-3's `pecore/` and `specs/shadow_q/`

## Implementation Plan

### This child: `prompt_eval_aitask_note_spec` (small gated paid run optional)

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

## Verification Steps

- The spec runs end-to-end under fake CLIs for both agents and all three scenarios.
- Every wrong-outcome-claim trace gets its `false_outcome_claim:<class>` despite correct helper
  calls and ids. The negation controls and the id-less `target_missing` answer stay `valid`.
- The claim-detector corpus test meets its pre-registered bounds.
- The generality record (spec README and the ledger) lists every core change and special case.
- The tests and `run_all_python_tests.sh --test-dir` are green; `check-public --staged` passes;
  `git diff --stat` is clean outside the allowed paths.
- A paid run happens only after a recorded approval of its printed manifest.

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
