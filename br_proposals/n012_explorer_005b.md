<!-- section: overview [dimensions: requirements_*] -->
## Overview

### What the feature is

A framework feature, generic across `aitasks`, `thinking_app`,
`thinking_backend`, `aitasks_go` and `aitasks_mobile`, that keeps a **test
map** — a relation between source files and test units — and uses it to
select, run, track, learn, enforce and teach. The engine is a static Go binary
under `$AITASKS_HOME/engine/v<VERSION>/`; the map is a committed `aitestmap/`
directory; machine-proposed edges pass through a three-file adoption ledger
(`seeded.yaml` → `adopted.yaml` → reviewed stamps); onboarding is a resumable
skill that runs one aitask per level; the run surface is one verb, `ait test`,
in interactive, completion and advisory modes.

### How this approach differs from the baseline

The baseline's loop is automatic everywhere except at two points, and both
sit on the path from "the map exists" to "the completion gate shrinks":

1. **Acceptance.** A seeded edge becomes a claim only when a person accepts
   it, because the closure proves a test *executes* a script, not that it
   *verifies* it, and the baseline assumes only a person can tell the two
   apart. Until acceptance happens, `--strict` cannot be enabled and
   `readiness` cannot count stamped coverage.
2. **The policy flip.** `completion.mode: selected` is written only by a
   human after `readiness` reports `ADMISSIBLE`. Until then `tests_pass` runs
   the whole suite, and the per-change-set selection that every interactive
   run already computes never reaches the gate.

This proposal replaces the assumption behind (1) and the human behind (2),
and names precisely what stays human. The statement it rests on is: *the
judgement "does this test verify this source, or only drive it?" needs a
reader of the test body, and an agent is a reader.* Four changes follow:

- **Two reading origins.** `agent:review` (0.90) — a headless-safe verdict
  from an agent that read a bounded packet of the test and the source —
  and `agent:author` (0.90) — the agent that just wrote the test or the
  source naming the pair itself. Under the existing noisy-OR a static edge
  plus a reading clears the 0.85 class threshold
  (`static:invocation + agent:review` = 0.99), and a reading alone clears it
  too. Every reading carries who read (an agent-string), which run, what
  packet (a digest), and a one-line rationale, so an adopted row never
  pretends to be a human review.
- **The autonomous floor is "rule, measurement or reading", not "1.0".**
  `static:package` is a rule, `coverage` is a measurement, `agent:*` is a
  reading; a headless profile may adopt any class whose every member
  carries at least one of them. Heuristic-only classes (`static:invocation`
  alone, `convention`, `cochange`, `plan`, `prose`) still need a reading on
  top. This makes level 1 headless on all five target repositories.
- **A self-approving policy with a scheduled full run.**
  `completion.mode: auto` lets `ait test --gate` flip to the selection when
  `readiness` is `ADMISSIBLE`, recording `approved_by: engine:readiness@<run>`
  with `mode: auto` (the same `explicit | auto` vocabulary `ait note read`
  already uses), and demote loudly as before. The person is replaced by a
  cadence — `full_run_every: {tasks, selection_ratio_above, days}` — so
  scoring never stops and a miss is caught within a bounded number of
  tasks. The invariant "the policy can only fail toward running more" holds.
- **The authoring agent annotates.** The pre-review procedure's autonomous
  branch no longer only proposes: for a source it introduced or a test it
  wrote, the agent writes the `testmap:covers` line through `annotate
  --author`, adopted with origin `agent:author`.

Two things are deliberately kept human: **kind changes** (a wrong kind
silently changes staleness semantics and no run evidence can check it) and
**axis declaration** (level 3). One thing is made *safer* than the baseline:
an **agent rejection is evidence-revocable** — a scored full-run miss whose
`(test, source)` pair sits in `rejections[]` with `by: agent:*` re-seeds the
pair and counts against `readiness`, because a wrong "only drives" verdict is
the one agent judgement that can under-select, and it is the one that a full
run *can* catch. A wrong "verifies" only over-selects, which is the
direction seeds were already allowed to err in.

The cost, stated once: the residual risk moves from reviewer fatigue to "a
wrong agent verdict lets a task land while an affected test never ran,
until the next full run". The knob for that risk is the full-run cadence,
per project, in `config.yaml`, printed by `--howto`.

### Reading guide

*Architecture* introduces the vocabulary, the process boundary and the
rewritten design decisions. *Data flow* walks a task, a completion run under
`auto`, headless onboarding through level 1, and the revocation path. *The
adoption model* holds the extended origin table and the new autonomous floor.
*Onboarding* has the headless row rewritten. *The agent review pass* is the
new mechanism in full. *Components*, *Assumptions* and *Tradeoffs* are the
reference sections, marking what is inherited, modified or new.
<!-- /section: overview -->

<!-- section: architecture [dimensions: component_test_entrypoint, component_test_front_verb, component_onboarding_engine_verbs, component_onboarding_skill, component_seeder, component_agent_brief, component_agent_instructions, component_completion_policy, component_workflow_seam, component_workflow_integration, component_go_engine, component_registry_loader, component_engine_binary, component_gates, component_adoption_ledger, component_agent_review_pass] -->
## Architecture

### Concepts

**Test unit and id.** A unit is a test file, a member of a file
(`<path>#<member>`) or a variant on a declared axis (`<unit>@<variant>`).
Unchanged.

**Edge.** A `testmap:covers <source>` line, stamped `@<date>/<blob10>` with
the source's git blob digest at confirmation. The digest is the staleness
key. Unchanged.

**Seeded, adopted, reviewed — and who accepted.** A machine-proposed edge
passes through up to three states. *Seeded* rows select and claim nothing.
*Adopted* rows are stamped edges accepted as a whole evidence class; their
`adopted.yaml` row now records **`by:`** — `human:<email>` or
`agent:<agent-string>` — beside the origins. *Reviewed* edges are stamped
edges a named person confirmed pair by pair. **New:** a row adopted from a
reading origin is an adopted row like any other; the `by:` field and the
`agent:*` origin are what keep it distinct from a human class acceptance.

**Rule, measurement, reading, heuristic.** The origin table is partitioned
into four classes by *what kind of fact produced the row*: a **rule**
(`static:package`: deterministic from the language), a **measurement**
(`coverage`: the test ran and the source's lines executed), a **reading**
(`agent:review`, `agent:author`: something read the test body and answered
the verify-or-drive question) and a **heuristic** (everything else). The
autonomous adoption floor is stated in these terms.

**Verdict.** The unit of an agent reading: `verifies | drives | unsure` on
one `(test, source)` pair, with a rationale, the reader's agent-string, the
run id and the digest of the packet it read. Verdicts enter the engine
through one intake (`onboard adopt --agent-verdicts -`), whatever site
produced them.

**Mode and policy.** `ait test` runs in interactive, completion or advisory
mode. The completion policy is `full`, `selected` or **`auto`**. Under
`auto` the engine decides per run: the selection when `readiness` is
`ADMISSIBLE` and no cadence trigger fires; the whole registry otherwise, with
the reason printed.

**Cadence.** `completion.full_run_every` — `{tasks: N, selection_ratio_above:
R, days: D}`; any trigger fires a full completion run under `auto`, which is
what keeps scoring alive without a person scheduling anything.

### The process boundary

Parse, walk, match, digest, schedule, seed, adopt, review-packet assembly
and verdict intake happen in Go. Reading a test body and answering
verifies-or-drives is an **agent** act, performed in a skill; the engine
never calls a model. The gate ledger, task files, profile files,
`project_config.yaml`, `gates.yaml`, agent-instructions files and the shell
environment stay bash and skill prose. Concretely:

- The engine never writes `aitasks/`, `aiplans/`, `.aitask-data/`, a gate
  ledger, `project_config.yaml`, `gates.yaml`, a profile or `CLAUDE.md`,
  never invokes an `aitask_*.sh` script, and **never launches a code agent**.
- The reading happens in three places, all agent sessions: the
  `testmap_fresh` procedure gate (the task's touched test files), the
  pre-review Affected Tests procedure (the task's own new pairs) and the
  `aitask-testmap-review` skill (bulk, during onboarding or on demand).
- No site uses headless print mode by default. Bulk review runs as an
  interactive skill launch (`ait skillrun testmap-review`) or inside the
  onboarding task's session; `ait codeagent testmap-review --headless` is
  the explicit opt-in, mirroring `batch-review`, because the framework's
  shell conventions forbid `claude -p` without one.

### Process map (additions in bold)

```
./ait test [...]                                   agent · human · tests_pass verifier · pre-review procedure (--advisory)
 └─ .aitask-scripts/aitask_test.sh                 bash front: MODE / TASK / INTAKE / POLICY / fallback / advisory
      │  POLICY completion: config.yaml completion.mode ∈ {full, selected, **auto**}; auto → readiness + **cadence** → full | selected, reason printed
      └─ .aitask-scripts/aitask_testmap.sh          the shim
           └─ ait-testmap test … | select | run | brief | onboard … | readiness | costs … | **annotate --author**
                internal/registry       six tables + seeds + adopted (rows now carry **by:** / run / rationale / packet_sha)
                internal/seed           origins static:{package,invocation,import} · coverage · **agent:review · agent:author** · observed · convention · plan · prose · cochange
                internal/onboard        detect · inventory · seed · **review** · classify · adopt (**--agent-verdicts**) · reject · scaffold · status · finish
                internal/feedback       score (**+ rejection revocation**) · attribute · readiness (**+ agent criteria**)
                internal/cost           ledger · **costs/policy.yaml** (last full run, tasks since, cadence state)
                internal/brief          --howto (**POLICY:auto|next full in <n> tasks**)

.claude/skills/aitask-gate-testmap-fresh/          in-gate seeds step: **autonomous → the agent's verdicts are the adoption**
.claude/skills/task-workflow/affected-tests.md     autonomous branch: **annotate --author** for the task's own pairs
.claude/skills/aitask-testmap-review/              **NEW** profile-aware skill: packets in, verdicts out, batch of 20, resumable
.claude/skills/aitask-testmap-onboard/             adopt phase gains the **review** sub-phase; headless completes level 1
.aitask-scripts/aitask_codeagent.sh                **testmap-review** operation (interactive; --headless opt-in as batch-review)
seed/models_<agent>.json                           **verified.testmap-review** score per model (the existing per-operation table)
```

### The registry directory (additions)

```
aitestmap/
  config.yaml            + completion: {mode: full|selected|auto, full_run_every: {tasks, selection_ratio_above, days}, …}
                         + agent_review: {enabled, accept_min, batch, packet_lines, max_pairs_per_run, rejections_revocable}
                         + readiness: {…, min_full_runs_since_map_change, max_revoked_rejections}
  onboard.yaml           phases gain `review: {status, at, by, counts{reviewed, adopted, rejected, unsure}}`;
                         rejections[] rows gain `by:` and `revocable:`; calibration[] rows
  registry/adopted.yaml  rows {test, source, origin[], confidence, adopted_at, task, by, run?, rationale?, packet_sha?}
  costs/policy.yaml      {last_full_run: {run_id, at, task, sha}, selected_since_full: n, approved_by: {who, at, mode, statement}}
```

```yaml
completion:
  mode: auto                     # full | selected | auto — auto: the engine flips when readiness is ADMISSIBLE
  full_run_every:                # any trigger → this completion run is full (POLICY:auto|full|cadence:<trigger>)
    tasks: 5                     # at most N selected completion runs between full runs
    selection_ratio_above: 0.60  # a selection costing ≥ 60 % of the full p95 saves little — run full and score
    days: 7                      # wall-clock ceiling on the gap between full runs
  deferred: run
  on_empty_selection: skip
  engine_absent: error
agent_review:
  enabled: true                  # false → agent:* origins are never written; the baseline's human-only adoption
  accept_min: 0.85               # the class threshold agent-backed rows must clear (noisy-OR)
  batch: 20                      # pairs per review packet
  packet_lines: 120              # ceiling on REVIEW_TEST lines per pair
  max_pairs_per_run: 400         # a bulk review stops here and records the phase as partial
  rejections_revocable: true     # a scored miss re-seeds an agent-rejected pair
readiness:
  min_scored_full_runs: 20
  max_false_negatives: 0
  require_opaque_proofs: true
  min_full_runs_since_map_change: 3   # bulk adoption / revocation resets the counter
  max_revoked_rejections: 0           # over the predictions window
```

### Design decisions (rewritten where the mandate touches them)

1. **Three adoption states, not two.** Unchanged.

2. **Autonomous adoption needs a rule, a measurement or a reading — never a
   heuristic alone.** The act that turns evidence into a claim needs a
   *reader of the test body*, and a reader may be a person or an agent. The
   rejected alternative — "only a person" — was a proxy for "only something
   that read the test", and it left every headless repository at level 0
   forever. A headless profile may therefore adopt `static:package` (rule),
   `coverage` (measurement), and any pair carrying `agent:review` or
   `agent:author` (reading) whose noisy-OR clears `accept_min`; it may never
   adopt `static:invocation`, `static:import`, `convention`, `cochange`,
   `plan` or `prose` without a reading on top. The reading is recorded with
   `by:`, run, rationale and packet digest, and is displayed as
   `adopted(… by agent:<string>)` so it can never be mistaken for a human
   class acceptance.

3. **One origin table, co-change capped.** Unchanged; two rows added.

4–9. Unchanged (levels × phases; the first full run is the level-0 gate;
`bootstrap_until`; one verb, two layers; advisory is a mode; the loop is a
paragraph).

10. **One completion gate under a committed policy, and the policy may
    self-approve.** `tests_pass` runs `./ait test --gate`; `completion.mode`
    decides what that is. `full` and `selected` keep their baseline
    meaning. `auto` lets the engine flip per run — the selection when
    `readiness` is `ADMISSIBLE` and no cadence trigger fires, the whole
    registry otherwise — and records `approved_by: {who:
    engine:readiness@<run-id>, mode: auto}`. The rejected alternative, a
    human flip, is kept as `selected` for a project that wants it; the
    rejected alternative to the cadence — trusting the demotion criteria
    alone — was rejected because scoring only happens on full runs, and a
    policy that never runs full can never demote itself.

11–13. Unchanged (comment lines only; `verify_build` asked about; task
resolution implicit).

14. **A wrong "verifies" over-selects; a wrong "drives" under-selects; only
    the second is revocable by evidence.** Agent rejections carry
    `revocable: true`; a scored miss on a rejected pair re-seeds it and
    counts toward `max_revoked_rejections`. Human rejections are never
    revoked, only contradicted with a printed `REJECTION_CONTRADICTED:` line.
    The rejected alternative — treating all rejections alike — would either
    let evidence overrule a person or let an agent's error persist silently.

15. **Kind changes and axes stay human.** A kind changes staleness
    semantics, not selection breadth, and no run evidence checks it; an axis
    is a declaration of the project's product space. Headless profiles
    *propose* kinds (`kind_proposals[]` in `onboard.yaml`) and never apply
    them.

16. **The engine never calls a model.** The reading is a skill act. Bulk
    review is an interactive skill launch by default; headless print mode
    is an explicit opt-in flag on `ait codeagent`, as the framework already
    requires for `batch-review`.
<!-- /section: architecture -->

<!-- section: data_flow [dimensions: component_test_entrypoint, component_test_front_verb, component_onboarding_engine_verbs, component_onboarding_skill, component_seeder, component_completion_policy, component_workflow_integration, component_workflow_seam, component_selector, component_annotation_scanner, component_freshness, component_feedback_tools, component_cost_ledger, component_registry_loader, component_staleness_tool, component_agent_review_pass] -->
## Data Flow

### A task in steady state (autonomous profile)

```
Step 7  edit source ──▶ ./ait test                      MODE:interactive TASK:<id> INTAKE:change-surface
                        ──▶ select (edges ∪ adopted ∪ seeds ∪ deps ∪ rules ∪ axes ∪ test-dep) ──▶ run ──▶ prediction record
        before Step 8 ──▶ ./ait test --advisory --task <id> ──▶ VERDICT:/REASON:/LOG:
                        UNMAPPED_SOURCE:<src>  ──▶ the agent names the test it wrote for it
                                               ──▶ ait testmap annotate --author <test> <src> --task <id> --by <agent-string>
                                               ──▶ stamped covers line + adopted.yaml {origin:[agent:author], by, run}
                                               ──▶ no test known → attribute --propose (seeded, observed) as before
                        UNANNOTATED_TEST:<t>   ──▶ annotate --suggest <t> ──▶ the agent confirms rows → --author
Step 8  testmap_fresh ──▶ stale --task; then seeds on touched test files:
                        attended  → agent pre-fills verifies/drives/unsure per row; human confirms (by: human) or "trust batch" (by: agent)
                        autonomous → the agent's verdicts ARE the adoption: onboard adopt --agent-verdicts - --by <agent-string> --run <run>
Step 9  ait gates run ──▶ testmap_check ──▶ tests_pass = ./ait test --gate
                        POLICY:auto → readiness ADMISSIBLE? cadence fired? → selected | full (reason printed)
        full run ──▶ score ──▶ PREDICTION_MISSED:<id> ──▶ attribute --propose
                             ──▶ pair in rejections[] by agent:* ──▶ AGENT_REJECTION_REVOKED:<test>|<source> ──▶ re-seeded
```

### A completion run under `auto`

```
tests_pass → export AIT_GATE_TASK_ID / AIT_GATE_RUN_ID → ./ait test --gate
   POLICY:auto
     readiness → NOT_YET|<criterion>            → POLICY:auto|full|not_yet:<criterion>       → run --all
     readiness → ADMISSIBLE, first time          → costs/policy.yaml approved_by {engine:readiness@<run>, mode: auto}
     cadence: selected_since_full ≥ tasks        → POLICY:auto|full|cadence:tasks             → run --all, selected_since_full := 0
     cadence: est_s / full_p95 ≥ ratio           → POLICY:auto|full|cadence:selection_ratio  → run --all
     cadence: now − last_full_run ≥ days         → POLICY:auto|full|cadence:days             → run --all
     otherwise                                   → POLICY:auto|selected|next_full_in:<n>     → the task selection, deferred rows run
   → every full run scores the newest prediction; a miss demotes exactly as before (POLICY_DEMOTED:auto->full|max_false_negatives)
   → ledger block result="MODE:selected|14 units|policy:auto|next_full_in:3"
```

### Headless onboarding, level 0 → level 1 with no person

```
/aitask-testmap-onboard (remote profile)
   level 0   detect --write · inventory · seed --apply · waivers (rules + expiring) · enable · Step-9 tests_pass = first full run   (as baseline)
   level 1   adopt --class static:package --accept-min 1.0              rule        → aitasks_go: 55 files, done
             adopt --class coverage                                      measurement → any repo with a coverage import
             review phase:                                               reading
               loop  onboard review --next 20 --json > packet
                     the skill reads the packet, answers per pair
                     onboard adopt --agent-verdicts - --by claudecode/opus5 --run onboard-<run>
                     ADOPT_SUMMARY:1|<edges>|<files>|<skipped>  REJECTED:<n>  UNSURE:<n>
               until the queue is empty, max_pairs_per_run is reached, or the class is exhausted
             onboard.yaml phases.review {reviewed, adopted, rejected, unsure}; chore: Onboard testmap — review (t<id>)
             calibrate: onboard review --calibrate 50 (against coverage facts where present, else skipped and printed)
   level 2   classify → CLASSIFY: rows recorded as kind_proposals[]; nothing applied          (human)
   level 3   not entered                                                                        (human)
   policy    completion.mode: auto written by detect --write when the profile is headless and agent_review.enabled
```

### Revocation

```
full run (gate- or full- prefixed) → score → PREDICTION_MISSED:tests/test_x.sh
   for each changed source S in the run's change surface:
     (tests/test_x.sh, S) ∈ onboard.yaml rejections[] ?
        by: agent:*  → row removed · re-seeded {origin: [observed, <original origins>], evidence.revoked_from: <run>} · AGENT_REJECTION_REVOKED:<test>|<S>|<run>
        by: human:*  → REJECTION_CONTRADICTED:<test>|<S>|<run> (advisory; the row stays)
   costs/predictions.yaml row gains revoked: [<pairs>]
   readiness: max_revoked_rejections counts rows in the window → NOT_YET until min_full_runs_since_map_change clean runs pass
```

### Reading the map without running anything

```
ait test --howto   → TESTMAP:…|POLICY:auto|next full in 3 tasks|seeds pending 412|adopted 618 (agent 540, human 78)|revoked 0
onboard status     → … AGENT_ADOPTED:<n>  AGENT_REJECTED:<n>  UNSURE:<n>  REVOKED:<n>  CALIBRATION:<agree>/<n>|none
readiness          → READINESS:min_full_runs_since_map_change|met|4   READINESS:max_revoked_rejections|met|0   READINESS:approved_by|met|engine:readiness@gate-…
```
<!-- /section: data_flow -->

<!-- section: adoption_model [dimensions: component_adoption_ledger, component_seeder, component_onboarding_engine_verbs, component_registry_loader, component_annotation_scanner, component_dependency_scanners, component_agent_review_pass, assumption_seed_sources_measured, assumption_static_closure_seeds_edges, assumption_cochange_is_corroboration, assumption_seeds_select_never_evidence, assumption_helpers_separable_by_fanin, assumption_annotation_is_comment_only, assumption_agent_reads_verify_vs_drive, assumption_wrong_positive_claim_only_overselects, assumption_agent_rejection_is_revocable] -->
## The Adoption Model

### The idea

A machine can find evidence that a test exercises a source; a *reader of
the test body* can turn that evidence into a claim; the freshness machinery
enforces claims. The baseline made "reader" mean "person". This model makes
it mean "person or agent", records which, and treats the two kinds of agent
error asymmetrically: a wrong claim over-selects and is tolerated the way
seeds are; a wrong rejection under-selects and is revocable by the next full
run.

### The three states, with `by:`

```
                onboard seed --apply · attribute --propose · revocation
   (none) ─────────────────────────────────────────────▶ SEEDED ──────────────────────────────────────────▶ ADOPTED (stamp + adopted.yaml row, by: human|agent)
                                                            │   onboard adopt --class <origin> [--accept-min]              │
                                                            │   onboard adopt --agent-verdicts - --by agent:<s> --run <r>   │ human re-stamp
                                                            │   annotate --author (agent:author, adopted on write)          ▼
                                                            ├──────────────────────────────────────────────────────▶ REVIEWED (stamp, no provenance row)
                                                            │ onboard reject <test> <source> --reason        (by: human, revocable: false)
                                                            │ VERDICT:<id>|drives                             (by: agent,  revocable: true)
                                                            ▼
                                                        REJECTED (onboard.yaml rejections[] {test, source, by, run, rationale, revocable})
                                                            │ scored miss on the pair, by: agent → AGENT_REJECTION_REVOKED → back to SEEDED
```

Surfaces: `check` prints `SEEDED:<n>` and `ADOPTED:<n>|agent <a>|human <h>`;
`stale --all` the same; `readiness` prints `ADOPTED_UNREVIEWED`, `SEEDED`,
`REVOKED:<n>`; `onboard status` is the one place every ratio lives. The two
load rules (`SEED_SHADOWED`, `ADOPTED_ORPHAN`) are unchanged; a third is
added: a rejection row without `by:` is read as `by: human, revocable:
false` (the baseline's rows, never revoked).

### The autonomous floor

> An autonomous profile may seed everything and may adopt a class only when
> every member of the class carries at least one **rule**, **measurement**
> or **reading** origin and its noisy-OR confidence clears
> `agent_review.accept_min` (default 0.85). A heuristic origin never
> qualifies alone, however high its measured precision.

| class | origin | headless-adoptable | why |
|---|---|---|---|
| rule | `static:package` | yes | deterministic from the language |
| measurement | `coverage` | yes | the source's lines executed under the test |
| reading | `agent:review`, `agent:author` | yes | something read the test body and answered verifies-or-drives |
| heuristic | `static:invocation`, `static:import`, `observed`, `convention`, `plan`, `prose`, `cochange` | **no** — needs a reading on top | the fact is "executes" or "co-occurs", never "verifies" |

`static:invocation` at 0.90 alone therefore stays seeded in a headless
profile — the 398/400 precision measured on aitasks says the test *runs* the
script, which is exactly the gap the baseline named — and becomes adoptable
at 0.99 the moment an agent verdict of `verifies` lands on it. The attended
profile keeps every baseline path (class acceptance with a ten-sample
review, per-row adoption, the in-gate step); in it the agent pre-fills
verdicts and a person confirms.

### The origin table

| origin | class | rule | evidence recorded | confidence |
|---|---|---|---|---|
| `static:package` | rule | a `_test.go` file's subject is its own package | — | **1.00** |
| `coverage` | measurement | per-unit runtime coverage (coverage.py contexts, `go -coverprofile` per `-run`, LCOV with a test column, JaCoCo per-test sessions) | run id | 0.95 |
| **`agent:review`** | reading | an agent read the review packet for the pair and answered `verifies` | `{by: agent:<agent-string>, run, rationale (≤ 2 lines), packet_sha, test_blob, source_blob}` | **0.90** |
| **`agent:author`** | reading | the agent implementing a task named the pair for a test it wrote or a source it introduced, through `annotate --author` | `{by, task, run, rationale}` | **0.90** |
| `static:invocation` | heuristic | a literal repo path the test executes or sources | file:line | 0.90 |
| `static:import` | heuristic | a direct import of a main-root file | file:line | 0.85 |
| `observed` | heuristic | an `attribute --propose` row from a scored miss, or a **revoked agent rejection** | run id | 0.70 |
| `convention` | heuristic | `config.yaml conventions:` patterns | pair | 0.60 |
| `plan` | heuristic | an `aiplans/` file naming both paths | path | 0.50 |
| `prose` | heuristic | a literal path in the header comment | line | 0.30 |
| `cochange` | heuristic | `(test, source)` in ≥ 2 distinct `(t<id>)` groups | task ids | 0.20 + 0.20/group, cap 0.60 |

**Combination.** Noisy-OR as before. `static:invocation + agent:review` =
0.99; `static:import + agent:review` = 0.985; `agent:review` alone = 0.90;
`convention + agent:review` = 0.96; `cochange(cap) + agent:review` = 0.96.
A reading alone clears the threshold because a reading *is* the
verify-or-drive judgement; the static origins beneath it raise the rank and
supply the packet's anchor line. Two `unsure` verdicts on one pair mark it
`REVIEW_HUMAN` and drop it from further agent packets.

**Why 0.90 and not 1.0.** A reading is a judgement, not a rule; 0.90 keeps a
lone agent verdict below `static:package`, above every heuristic, and
exactly where a single static fact plus a reading reaches the top of the
queue. The number is calibratable: `onboard review --calibrate <n>` compares
agent verdicts against the project's coverage facts where a coverage import
exists (measurement as ground truth), else against the human-reviewed rows
and human rejections where those exist, and prints `CALIBRATION:agree
<a>|disagree <d>|<ratio>`. A ratio under 0.90 lowers `agent:review`'s
effective confidence to the measured ratio for that repository (written to
`config.yaml agent_review.measured_confidence`), and under `accept_min` it
disables headless adoption from that origin and says so in `readiness`.

### Where the reading happens

| site | who reads | what | verdict path | provenance |
|---|---|---|---|---|
| `testmap_fresh` in-gate step (Step 8) | the task's agent; a person in attended profiles | seeds on the test files this task touched — the file is open, the diff is in front of the reader | attended: agent pre-fills, human confirms per row (`by: human`) or "trust this batch" (`by: agent`); autonomous: `onboard adopt --agent-verdicts -` | `adopted(<origins>+agent:review <c> by agent:<s>)` |
| pre-review Affected Tests procedure (Step 7) | the task's agent | `UNMAPPED_SOURCE` / `UNANNOTATED_TEST` for the task's own change | `ait testmap annotate --author <test> <source> --task <id>`; no known test → `attribute --propose` | `adopted(agent:author 0.90 by agent:<s>)` |
| `aitask-testmap-review` skill (bulk) | a dedicated skill session | `onboard review --next 20` packets over the seed queue, by class or scope | `onboard adopt --agent-verdicts -` per batch; resumable; `review` phase in `onboard.yaml` | as above, run id `review-<n>` |

### Helpers, kinds, placement, what seeding cannot do

Unchanged from the baseline: helpers are separated by roots and fan-in
before any origin scores; kinds, members and axes are proposed by
`classify` and `scaffold`; adoption writes comment lines only at the fixed
per-language position; a source reached by no origin stays
`UNMAPPED_SOURCE` until a rule, a waiver, a pre-review prompt, a coverage
import — **or an author annotation** — maps it. The agent:author path is
the new thing that closes the same-package gap on thinking_app: the agent
that edits a screen and its test knows the pair even when no import says so.
<!-- /section: adoption_model -->

<!-- section: agent_review_pass [dimensions: component_agent_review_pass, component_onboarding_engine_verbs, component_skill, component_freshness, component_workflow_integration, assumption_agent_reads_verify_vs_drive, assumption_headless_launch_is_explicit_opt_in, assumption_wrong_positive_claim_only_overselects] -->
## The Agent Review Pass

### The idea

The engine assembles a bounded, digest-stamped **packet** per seeded pair;
an agent reads packets and returns **verdicts**; the engine turns verdicts
into adopted rows, rejections or `unsure` marks through the same rewriter
and ledger every other adoption uses. The engine never calls a model; the
skill never writes a test file. A packet is what the agent saw, and its
digest is stored beside the verdict so a later reader can reproduce the
judgement's inputs.

### The packet

`ait testmap onboard review [--next N] [--class <origin>] [--scope <glob>]
[--ids <csv>] [--json] [--calibrate <n>]`:

```
REVIEW_PAIR:<id>|<test>[#member]|<source>|<origins>|<confidence>|<unsure_count>
REVIEW_ANCHOR:<id>|<file:line>                 the static fact's line (invocation / import), when one exists
REVIEW_TEST:<id>|<line>|<flag>|<text>          the anchor ±20 lines, then every line containing an assertion call
                                               (assert_eq / assert_contains / assert / expect / require / t.Fatal* /
                                               assertEquals / shouldBe / grep -q on captured output) flagged `!`;
                                               ceiling agent_review.packet_lines per pair
REVIEW_SOURCE:<id>|<symbol>|<kind>             the source's declared symbols (bash: function names + top-level verbs;
                                               Python: def/class; Go: exported idents; Kotlin: declarations) — never the body
REVIEW_PROSE:<id>|<line>                       the test's header comment / `# Covers:` lines
REVIEW_MEMBER:<id>|<block>                     for a member seed, the testmap:unit block's own lines
REVIEW_END:<id>|<packet_sha>
```

The packet deliberately excludes the source body: the question is whether
the *test* checks something the source does, and the source's symbol list is
enough to see whether the flagged assertion lines name its behaviour. The
`--json` form is one object per pair with the same fields. `--calibrate <n>`
samples `n` pairs with a ground truth (coverage rows, reviewed edges, human
rejections) and marks them so the intake compares instead of adopting.

### The verdict

Fed to `ait testmap onboard adopt --agent-verdicts - --by <agent-string>
--run <run-id>`, one line per pair:

```
VERDICT:<id>|verifies|<rationale ≤ 160 chars>
VERDICT:<id>|drives|<rationale>
VERDICT:<id>|unsure|<rationale>
```

| verdict | effect | printed |
|---|---|---|
| `verifies` | `agent:review` added to the row's origins; noisy-OR recomputed; ≥ `accept_min` → adopted through the rewriter with an `adopted.yaml` row `{…, by: agent:<s>, run, rationale, packet_sha, test_blob, source_blob}`; below → stays seeded with the origin recorded | `WROTE:<file>` / `ADOPT_SUMMARY:` |
| `drives` | row leaves `seeded.yaml`; `onboard.yaml rejections[] += {test, source, by: agent:<s>, run, rationale, revocable: true}` | `REJECTED:<test>|<source>|agent` |
| `unsure` | `evidence.agent.unsure += 1`; at 2 the pair is `REVIEW_HUMAN` and leaves the agent queue | `UNSURE:<test>|<source>|<n>` |
| any, packet_sha ≠ current | the pair's files changed since the packet was cut | `VERDICT_STALE:<id>` — ignored, re-packeted next batch |
| `--by` not an agent-string | refused: `parse_agent_string` must accept it; humans use the per-row verbs | exit 64 |
| `--calibrate` run | no writes; `CALIBRATION:agree <a>|disagree <d>|<ratio>` appended to `onboard.yaml calibration[]` | as printed |

`--by` is validated against `lib/agent_string.sh`'s grammar
(`<agent>/<model>`, agents `claudecode|codex|opencode`), so a `by:` value is
always resolvable to a model row in `models_<agent>.json`; the operation
`testmap-review` is added to each model's `verified:` table, the existing
per-operation score the framework keeps for `batch-review`, `pick`,
`explain`, `work-report` and `trail`.

### The skill `aitask-testmap-review`

`.claude/skills/aitask-testmap-review/` as a profile-aware stub +
`SKILL.md.j2` (resolver key `testmap-review`), one procedure file
`review-batch.md`. Flow: preconditions (`ait testmap version`; `aitestmap/`
present; `agent_review.enabled`) → `onboard review --next <batch> [--class]
[--scope]` → for each pair, read the packet and decide by the rule *"a test
verifies a source when a flagged assertion line checks an output, a state or
an exit status that the source's symbols produce; it only drives it when the
source appears solely in setup, teardown or as a path argument whose result
is never checked"* → emit the `VERDICT:` lines → `onboard adopt
--agent-verdicts - --by <agent-string> --run review-<n>` → repeat until the
queue is empty, `max_pairs_per_run` is reached, or (attended) the user stops
→ commit the rewritten files under `chore: Onboard testmap — review
(t<id>)` when running inside an onboarding task, else print the commit
lines. Attended profile: the agent shows each batch's verdicts as a table
and the user confirms, edits or trusts the batch; autonomous profile: no
prompts. The skill ships Claude Code first; Codex and OpenCode ports are
follow-up tasks; goldens under `tests/golden/skills/aitask-testmap-review/`.

**Launch surfaces.** Inside an onboarding task the skill is a sub-procedure
of the `adopt` phase (`review.md`). On demand: `ait skillrun testmap-review
[--profile <p>] [-- --class static:invocation]`, an interactive launch as
every skill run is. `ait codeagent testmap-review` mirrors `batch-review`:
interactive by default, `--print` only under `--headless`, because the
framework bills headless print mode at a higher rate and its shell
conventions forbid `claude -p` without an explicit opt-in. No engine code
path, gate or hook launches an agent.

### The in-gate site (Step 8)

`aitask-gate-testmap-fresh`'s seeds step becomes: for each `COMMITTED:` /
`TASK:` test file with rows in `seeded.yaml`, run `onboard review --ids
<those rows>` and read the packets — the agent already has the diff open.
Attended: the agent's verdict is pre-filled on each row; the user confirms
(`by: human`), overrides, or answers "trust this batch" once (`by: agent`).
Autonomous: `onboard adopt --agent-verdicts - --by <agent-string> --run
<gate-run-id>`. Either way the stamps ride the `(t<id>)` commit as before.

### The authoring site (Step 7)

The pre-review Affected Tests procedure's `skip · no_selection` branch in an
autonomous profile: for each `UNMAPPED_SOURCE:<src>`, the agent names the
test unit it wrote or edited for that source in this task (it must be in the
change surface or reach `<src>` through the static closure — `annotate
--author` refuses `AUTHOR_REFUSED:<test>|not-in-task` otherwise, keeping a
bulk-claim from riding the author path) and runs `ait testmap annotate
--author <test> <src> --task <id> --by <agent-string>`; the engine writes the
stamped line through the rewriter and an `adopted.yaml` row with origin
`[agent:author]`. No known test → `attribute --propose` as in the baseline.
`UNANNOTATED_TEST:<t>` → `annotate --suggest <t>` then `--author` on the
rows the agent confirms from its own knowledge of what it wrote. Attended
profiles keep the baseline's *Annotate now / Propose / Continue* prompt with
the agent's proposed pairs pre-filled.

### Budgets

Packet assembly is static (no runner, no model): `onboard review --next 20`
< 300 ms warm on the aitasks shape. A bulk pass over aitasks' ~720 static
seeds is 36 packets; at `packet_lines: 120` a packet is ≤ 2,400 lines of test
excerpt plus symbol lists — bounded, and the reason the source body is
excluded. `annotate --author` is one rewriter call.
<!-- /section: agent_review_pass -->

<!-- section: onboarding [dimensions: component_onboarding_skill, component_onboarding_engine_verbs, component_seeder, component_agent_review_pass, requirements_zero_config_onboarding, requirements_onboarding_existing_tests, requirements_incremental_adoption, requirements_autonomous_loop_closure, assumption_test_tools_detectable, assumption_onboarding_is_a_task, assumption_full_run_expressible_per_repo] -->
## Onboarding: Levels × Phases

### Levels and phases

| level | phases | what `onboard` writes | who accepts (attended) | who accepts (headless) |
|---|---|---|---|---|
| **0 — runners and universe** | detect → inventory → seed → waivers → enable → full_run | as baseline; `detect --write` sets `completion.mode: auto` when the profile is headless and `agent_review.enabled` | the runner table, `UNREGISTERED`, the config table | nothing to ask — as baseline |
| **1 — edges** | adopt (rule → measurement → **review**) then incrementally in `testmap_fresh` | stamped `testmap:covers` blocks; `adopted.yaml` rows with `by:`; `rejections[]` with `by:`; `phases.review` counts; `calibration[]` | per class with the agent's verdicts pre-filled, or per row | **the agent**: `static:package` and `coverage` by class; every other class through the review loop until the queue is empty or `max_pairs_per_run` |
| **2 — kinds** | classify → `scan --apply` | as baseline | per kind, individually | **proposes only**: `CLASSIFY:` rows land in `onboard.yaml kind_proposals[]`; nothing applied; `readiness` prints `KIND_PROPOSALS:<n>` |
| **3 — product** | scaffold → `annotate --from-body` | as baseline | the maintainer | not entered |
| **finish** | a phase of the last level task | `require_stamp: true`; `check --strict`; `bootstrap_until` shortened | `onboard status` green | `onboard status` green **and** `REVOKED:0` in the window **and** `REVIEW_HUMAN:0` — the finish is headless-safe when the map has no pair the agent could not judge |

### The headless (`remote`) profile — rewritten

Level 0 in full; level 1 in full by rule, measurement and reading (no
prompts; the level proposal is printed; the review loop runs to the
`max_pairs_per_run` budget and records a partial phase it re-enters on the
next run); level 2 proposes kinds and applies none; level 3 not entered;
the policy is `auto`, so no flip is written by anyone — the engine flips per
run when `readiness` is `ADMISSIBLE`. A headless repository therefore
reaches "the completion gate runs the selection" with no person having
typed anything, and the things that remain human — kinds, axes, the
`REVIEW_HUMAN` pairs — are listed by `onboard status` rather than assumed
done.

### Detection, per target repository — level 1 headless outcome

| repository | rule | measurement | reading | level 1 headless result |
|---|---|---|---|---|
| **aitasks** | — | opt-in (`coverage.py` contexts for the 320 Python tests) | 398 bash `static:invocation` + 320 Python `static:import` seeds through the review loop (36 packets) | ~718 adopted at 0.99 / 0.985; the 2 fixture-only tests stay seeded; conventions corroborate |
| **thinking_app** | — | JaCoCo per-test sessions when enabled (0.95, adoptable by class) | 139 `static:import` files through review; same-package pairs reach the map through `agent:author` as tasks touch them | level 1 partial by construction (the same-package gap), stated by `onboard status`; `verify-active` stays the completion gate until `auto` finds `ADMISSIBLE` |
| **thinking_backend** | — | opt-in | 40 units through review (2 packets) | full |
| **aitasks_go** | `static:package` 1.0 over 55 `_test.go` files | `go -coverprofile` per `-run` | none needed | full, as in the baseline |
| **aitasks_mobile** | — | JaCoCo where the Gradle modules enable it | 36 + 1 unit classes through review; the 3 device classes stay `device` kind (a kind, not adopted) | full for unit kinds |

Everything else in this section — invocation and task shape, preconditions,
survey, the level task, the after-level-0 procedure, `--no-task`, the
`--policy selected` re-entry (still available for a project that wants a
human flip) — is unchanged from the baseline.
<!-- /section: onboarding -->

<!-- section: run_surface [dimensions: component_test_entrypoint, component_test_front_verb, component_agent_brief, component_agent_instructions, requirements_zero_config_entrypoint, requirements_agent_run_surface, requirements_agent_instructions_seeded, assumption_task_resolvable_from_session, assumption_helper_degrades_when_absent, assumption_instructions_block_reaches_agents, assumption_instruction_block_is_read, assumption_change_surface_is_intake] -->
## The Run Surface

Unchanged from the baseline in forms, resolution order, output and exit
contract, the two environment variables and the generic instructions
section, with these additions:

- **`POLICY:` line under `auto`.** `POLICY:auto|selected|next_full_in:<n>` or
  `POLICY:auto|full|cadence:<tasks|selection_ratio|days>` or
  `POLICY:auto|full|not_yet:<criterion>`; the gate-run ledger block carries
  the same in `result=`.
- **`--howto`** gains `next full in <n> tasks` on the `TESTMAP:` line, an
  `agent <a>, human <h>` split on the adopted count, `REVOKED:<n>` when
  non-zero, and one `AGENT_REVIEW:enabled|<measured_confidence>|<calibration>`
  line; `FULL_GATE:` names the cadence (`every 5 tasks / ≥ 60 % / 7 d`).
- **`ait testmap annotate --author <test> <source> --task <id> --by
  <agent-string>`** — the one new maintainer-surface form, used by the
  pre-review procedure; refuses `AUTHOR_REFUSED:not-in-task` when the test
  is neither in the task's change surface nor reaches the source through the
  static closure.
- The `## Running Tests` section is **unchanged** (fourteen lines, no agent
  named); the author path is taught by the procedure that uses it, not by
  the seed, because it is a workflow act rather than a run form.

`ait test --howto` for aitasks after headless level 1, on this host class:

```
TESTMAP:onboarded|since 2026-09-20|LEVEL:1|POLICY:auto|next full in 3 tasks|seeds pending 14|adopted 718 (agent 718, human 0)
RUNNER:bash-file|unit|400|bash <file>|repo-git-index
RUNNER:pytest|unit|320|run_all_python_tests.sh lanes; 4 serial|repo-git-index
FULL_GATE:ait test --all|p95 412s|every 5 tasks / ≥ 60 % / 7 d|tests_pass timeout 1236s
GATE:testmap_fresh (procedure, before commit) -> testmap_check -> tests_pass = ./ait test --gate (auto: selected, 14 units now)
AGENT_REVIEW:enabled|0.90|calibration 47/50 (coverage)
VERBS:./ait test | ./ait test <path>... | ./ait test --all | ./ait test --howto
NEW_TEST:./ait testmap annotate --suggest <path>
```
<!-- /section: run_surface -->

<!-- section: workflow_seam [dimensions: component_workflow_seam, component_workflow_integration, component_gates, component_completion_policy, component_qa_integration, component_agent_review_pass, requirements_workflow_seam, requirements_workflow_seam_is_data, requirements_gate_enforcement, assumption_gate_exit_contract_reused] -->
## The Workflow Seam and the One Completion Gate

### The idea

Still no new workflow and no new gate. The seam is the baseline's data plus
one procedure, with the two autonomous branches that previously only
*proposed* now *acting* through engine verbs, and one new skill for bulk
review. Every seam degrades to a printed skip where the engine or the
registry is absent.

### The concrete edits (delta from the baseline)

| where | change | kind |
|---|---|---|
| `task-workflow/affected-tests.md` | `skip · no_selection`, autonomous branch: for each `UNMAPPED_SOURCE` the agent names its own test → `ait testmap annotate --author …`; none known → `attribute --propose` (baseline). `UNANNOTATED_TEST` → `--suggest` then `--author` on confirmed rows. Attended: the baseline prompt with the agent's pairs pre-filled | procedure |
| `aitask-gate-testmap-fresh` | the seeds step reads packets (`onboard review --ids`); attended: pre-filled verdicts, confirm / override / trust-batch; autonomous: `onboard adopt --agent-verdicts -` | procedure gate |
| `aitask-testmap-review/` | **new** profile-aware skill; `review-batch.md`; goldens; Codex / OpenCode ports as follow-ups | skill |
| `aitask-testmap-onboard/adopt.md` | rule → measurement → review sub-phase (`review.md`); headless row rewritten; `finish.md` adds the `REVOKED:0` / `REVIEW_HUMAN:0` conditions | procedure |
| `aitask_codeagent.sh` | operation `testmap-review` (`/aitask-testmap-review`), interactive by default, `--print` under `--headless`; `list-models` shows `verified.testmap-review` | code |
| `seed/models_{claudecode,codex,opencode}.json` | `verified.testmap-review` key per model (0 until measured); `aitask-add-model` seeds it | data |
| `aitestmap/config.yaml` (written by `detect --write`) | `completion.mode: auto` in headless profiles; `full_run_every`; `agent_review`; `readiness` block | data |
| `ait test --gate` (`aitask_test.sh` + `test` composite) | `auto` resolution: readiness + cadence → `POLICY:` line; writes `costs/policy.yaml` | code |
| `internal/feedback score` | revocation of `by: agent` rejections on a miss; `REJECTION_CONTRADICTED:` for human ones; `revoked:` in the predictions row | code |
| `internal/feedback readiness` | criteria `min_full_runs_since_map_change`, `max_revoked_rejections`; `approved_by` satisfied by `engine:readiness@<run>` under `auto`; `KIND_PROPOSALS:`, `REVIEW_HUMAN:` lines | code |
| `internal/onboard` | `review` verb; `adopt --agent-verdicts`; `review` phase; `rejections[].by/revocable`; `kind_proposals[]`; `calibration[]` | code |
| `internal/annot` | `annotate --author` (a rewriter caller with the not-in-task refusal) | code |
| `internal/registry` | `adopted.yaml` rows `by, run, rationale, packet_sha, test_blob, source_blob`; rejection load rule (absent `by:` = human) | code |
| `internal/brief` | the `--howto` additions | code |
| `profiles.md` | no new profile key — `agent_review.enabled` is project config, not a profile choice, because the map's provenance must not depend on who ran the task | doc |
| `aidocs/framework/aitasks_extension_points.md` | "Adding a seed origin" gains the class column (rule / measurement / reading / heuristic) and the autonomous-floor rule | doc |
| tests | `test_ait_test_entrypoint.sh` gains the `auto` matrix (ADMISSIBLE × cadence triggers × NOT_YET); engine tests for packet assembly per language, every verdict branch, `VERDICT_STALE`, `--by` refusal, calibration, revocation on a synthetic miss, the not-in-task refusal; `test_testmap_onboard_ledger.sh` covers the partial `review` phase re-entry; goldens for the two skills and the rewritten gate skill; `test_codeagent.sh` pins `testmap-review` interactive-by-default | test |

Everything else in the baseline table stands: Step 7's paragraph, the
pre-review procedure's other branches, the `affected_tests` key, Step 9's
verify block, `run_project_command_key()`'s new rows, `gates_reference.yaml`
(`testmap_fresh`, `testmap_check → tests_pass`; no selection gate),
`aitask-qa`'s registry-first branches (which now show `Covered (adopted by
agent)` where the row says so), `report_testmap_state()`, the dispatcher
arm, the five touchpoints.

### Gates

Unchanged in `gates_reference.yaml`. `run_gate_admission` under `auto` is
`{who: engine:readiness@<run-id>, at, mode: auto, statement: <the readiness
lines at the flip>}` written to `costs/policy.yaml`, not `config.yaml`, so
the committed policy file stays a human-authored declaration and the
engine's approvals live beside the other engine-written ledgers.

### Completion policy

`full` and `selected` as the baseline. `auto`: the flip is the engine's,
per run, loud (`POLICY:auto|…` on every completion run); the demotion is
automatic as before; the cadence guarantees full runs keep happening; the
policy can only fail toward running more. thinking_app's rule — full
`verify-active` until admissible — is preserved by `auto` exactly as by
`full` until `readiness` says otherwise, and its cadence would be the
project's to set (a 1,180 s full run every 5 tasks is the price of the
selection on the other 4).
<!-- /section: workflow_seam -->

<!-- section: components [dimensions: component_*] -->
## Components

Grouped by layer; each marked *(inherited)*, *(modified)* or *(new)*. An
inherited component is summarised; its full text is in the node metadata
and is unchanged from the baseline.

**Engine and packaging**

<!-- section: component_go_engine [dimensions: component_go_engine] -->
### Go engine and CLI *(modified: never launches an agent)*

`engine/cmd/ait-testmap` with the baseline's packages plus `internal/seed`,
`internal/onboard`, `internal/brief`; Go 1.26, `CGO_ENABLED=0`, the three
dependencies, line-protocol stdout. Boundary additions: the engine never
launches a code agent, never reads `models_<agent>.json` beyond validating
an agent-string's grammar, and never decides a verdict — `onboard review`
assembles packets and `onboard adopt --agent-verdicts` consumes lines. One
fixture per verdict branch and one per packet language join the fixture
set.
<!-- /section: component_go_engine -->

<!-- section: component_engine_binary [dimensions: component_engine_binary] -->
### Engine binary identity and budget *(modified: two verbs, two budgets)*

Verb table gains `onboard review` and `annotate --author`; budgets: `onboard
review --next 20` < 300 ms warm (static packet assembly, no exec); `annotate
--author` is one rewriter call. Contract stays 1; `adopted.yaml` rows with
`by:` and `rejections[]` with `by:` are additive fields an older engine
ignores.
<!-- /section: component_engine_binary -->

<!-- section: component_binary_distribution [dimensions: component_binary_distribution] -->
### Binary distribution *(inherited)*

`engine/build.sh`, the release `engine` job, `engine-check.yml`, the shim's
strict handshake and the platform matrix are unchanged.
<!-- /section: component_binary_distribution -->

<!-- section: component_engine_packaging [dimensions: component_engine_packaging] -->
### Engine install, upgrade and state report *(inherited)*

`install_engine_binary()`, `report_testmap_state()` and the `TESTMAP:` line
are unchanged.
<!-- /section: component_engine_packaging -->

<!-- section: component_user_root [dimensions: component_user_root] -->
### Per-user root *(inherited)*

`lib/aitasks_home.sh`, `$AITASKS_HOME`, unchanged.
<!-- /section: component_user_root -->

<!-- section: component_framework_home [dimensions: component_framework_home] -->
### Framework home report and migration verb *(inherited)*

`ait engine home [--migrate]`, unchanged.
<!-- /section: component_framework_home -->

**The map: registry, annotations, scanners, axes**

<!-- section: component_registry_loader [dimensions: component_registry_loader] -->
### Registry loader and writer *(modified: provenance fields)*

As the baseline, plus: `adopted.yaml` rows are `{test, source, origin[],
confidence, adopted_at, task, by: human:<email>|agent:<agent-string>, run?,
rationale?, packet_sha?, test_blob?, source_blob?}`; `onboard.yaml
rejections[]` rows are `{test, source, reason|rationale, by, run?, revocable}`
with the load rule that an absent `by:` reads as `human, revocable: false`;
`kind_proposals[]` and `calibration[]` are read for `status` and
`readiness`. Write routing adds: `adopt --agent-verdicts` → `seeded.yaml`
(rows removed) + `adopted.yaml` + test files, or `onboard.yaml rejections[]`;
`annotate --author` → the test file + `adopted.yaml`; `score` revocation →
`onboard.yaml` (row removed) + `seeded.yaml` (row re-added). `config.yaml`
gains `completion.full_run_every`, `agent_review`, `readiness`. Golden tests
pin the `by:` merge and the absent-`by:` rule.
<!-- /section: component_registry_loader -->

<!-- section: component_annotation_scanner [dimensions: component_annotation_scanner] -->
### Annotation scanner and rewriter *(modified: one more caller)*

Grammar v3 and the line-targeted rewriter are unchanged. `annotate --author
<test> <source> --task <id> --by <agent-string>` is a new caller: it checks
the test is in the task's change surface or reaches the source through the
static closure (`AUTHOR_REFUSED:<test>|not-in-task` otherwise), inserts the
stamped `testmap:covers` line at the fixed per-language position, and writes
the `adopted.yaml` row with origin `[agent:author]`. A member seed lands in
the `testmap:unit` block as before.
<!-- /section: component_annotation_scanner -->

<!-- section: component_dependency_scanners [dimensions: component_dependency_scanners] -->
### Dependency scanners *(modified: packet facts)*

The scanners expose two more read-only facts to `internal/onboard review`:
the anchor line of a static fact (file:line of the invocation or import)
and a source's declared symbols (bash function names and top-level verbs,
Python `def`/`class`, Go exported identifiers, Kotlin declarations) from the
same blob-keyed cache — no new scan, no source bodies in packets.
<!-- /section: component_dependency_scanners -->

<!-- section: component_variant_axes [dimensions: component_variant_axes] -->
### Variant axes *(inherited)*

`axes.yaml`, the facet join, `--axis`, unchanged; axis declaration stays a
human act (design decision 15).
<!-- /section: component_variant_axes -->

<!-- section: component_axes [dimensions: component_axes] -->
### Axis resolver verbs *(inherited)*

`ait testmap axes --list|--check|--explain`, unchanged.
<!-- /section: component_axes -->

<!-- section: component_cell_enumeration [dimensions: component_cell_enumeration] -->
### Enumeration and reconciliation *(inherited)*

The runner's `list` as the enumeration surface, `UNCOVERED_VALUE`,
`UNMAPPED_ARTIFACT`, unchanged.
<!-- /section: component_cell_enumeration -->

<!-- section: component_suite_registry [dimensions: component_suite_registry] -->
### Scoped-row registry and areas *(modified: headless proposes kinds)*

As the baseline; `classify --suggest`'s `CLASSIFY:` rows in a headless
profile are written to `onboard.yaml kind_proposals[]` by `onboard classify
--propose` and never applied; `readiness` prints `KIND_PROPOSALS:<n>` so a
later attended session finds them.
<!-- /section: component_suite_registry -->

<!-- section: component_broad_test_scopes [dimensions: component_broad_test_scopes] -->
### Broad-test scheduling and staleness policy *(inherited)*

Kinds, `broad_after_unit`, `STALE_AREA`, `device_policy`, unchanged.
<!-- /section: component_broad_test_scopes -->

**Freshness and evidence**

<!-- section: component_freshness [dimensions: component_freshness] -->
### Freshness *(modified: the in-gate step acts)*

Stamps are written by `verify`, `annotate` (including `--author`), `stale
--confirm*` and `onboard adopt` (including `--agent-verdicts`). The
`testmap_fresh` procedure gate's seeds step now reads packets for the
touched test files: attended, the agent pre-fills verdicts and the person
confirms per row or trusts the batch; autonomous, the agent's verdicts are
the adoption through `onboard adopt --agent-verdicts -`. The stamps ride the
`(t<id>)` commit as before; an agent-adopted stamp is a stamp like any
other, displayed with `by agent:<s>`.
<!-- /section: component_freshness -->

<!-- section: component_staleness_tool [dimensions: component_staleness_tool] -->
### Staleness tool *(modified: display)*

As the baseline; a row whose edge has an `adopted.yaml` row carries
`adopted(<origins> <confidence> by <human|agent:<s>>)` in its `DISPLAY` line,
and `stale --all` prints `ADOPTED:<n>|agent <a>|human <h>`.
<!-- /section: component_staleness_tool -->

<!-- section: component_evidence_join [dimensions: component_evidence_join] -->
### Evidence join *(inherited)*

Per-variant `last_pass` anchors, `git ls-tree` per sha, `--confirm-evidenced`
as the only bulk confirmation; unchanged, and unchanged in that evidence
removes nags and never reviews a claim — an agent-adopted edge is joined like
any stamped edge.
<!-- /section: component_evidence_join -->

**Selection, scheduling, running, cost**

<!-- section: component_selector [dimensions: component_selector] -->
### Selector *(modified: reason text)*

As the baseline; an adopted edge's reason reads
`edge(annotation) adopted(static:invocation+agent:review 0.99 by agent:claudecode/opus5)`
or `adopted(agent:author 0.90 by agent:…)`; `explain --sources` prints
`Covered (adopted by agent)` / `Covered (adopted by human)` for `aitask-qa`.
<!-- /section: component_selector -->

<!-- section: component_scheduler_resources [dimensions: component_scheduler_resources] -->
### Scheduler and resources *(inherited)*

Unchanged.
<!-- /section: component_scheduler_resources -->

<!-- section: component_runner_contract [dimensions: component_runner_contract] -->
### Runner contract and repository *(inherited)*

`describe / list / run`, `subsumed_by`, `fallback_command`, scaffold;
unchanged.
<!-- /section: component_runner_contract -->

<!-- section: component_reference_runners [dimensions: component_reference_runners] -->
### Reference runners *(inherited)*

The builtins and `detect`'s repository seeding; unchanged.
<!-- /section: component_reference_runners -->

<!-- section: component_cost_ledger [dimensions: component_cost_ledger] -->
### Cost ledger *(modified: policy state)*

As the baseline, plus `aitestmap/costs/policy.yaml` `{last_full_run:
{run_id, at, task, sha}, selected_since_full: <n>, approved_by: {who, at,
mode, statement}}`, written by `ait test --gate` under `auto`; the cadence's
`selection_ratio_above` compares the selection's per-group estimate to the
newest full run's p95 on this host class; run-id prefixes unchanged
(`review-` is added for bulk review runs, which write no cost rows).
<!-- /section: component_cost_ledger -->

<!-- section: component_feedback_tools [dimensions: component_feedback_tools] -->
### Feedback tools *(modified: revocation and criteria)*

`score` gains the revocation step: for each `PREDICTION_MISSED:<id>` and each
changed source in the run's surface, a `rejections[]` row for the pair with
`by: agent:*` is removed, the pair re-seeded with origins `[observed] ∪
<original>` and `evidence.revoked_from: <run>`, and
`AGENT_REJECTION_REVOKED:<test>|<source>|<run>` printed; a `by: human` row
prints `REJECTION_CONTRADICTED:` and stays. The predictions row records
`revoked: [...]`. `readiness` gains `min_full_runs_since_map_change` (reset
by any bulk adoption, revocation or `--author` write; counted in clean scored
full runs) and `max_revoked_rejections` (over the predictions window),
satisfies `approved_by` from `costs/policy.yaml` under `auto`, and prints
`AGENT_ADOPTED:<n>|<ratio>`, `REVOKED:<n>`, `REVIEW_HUMAN:<n>`,
`KIND_PROPOSALS:<n>`. `attribute --propose` is unchanged.
<!-- /section: component_feedback_tools -->

**Adoption and onboarding**

<!-- section: component_adoption_ledger [dimensions: component_adoption_ledger, component_registry_loader, component_seeder, component_onboarding_engine_verbs, component_agent_review_pass] -->
### Adoption ledger *(modified: `by:`, revocation, the autonomous floor)*

The three-file state as the baseline, with `by:` on adopted and rejected
rows, `revocable:` on rejections, and one more transition: a scored miss on
an agent-rejected pair → seeded. The autonomous rule is rewritten: a
headless profile may seed everything and may adopt a class only when every
member carries a rule, a measurement or a reading origin and clears
`accept_min`; heuristic-only classes need a reading on top. Costs are
recorded under `tradeoff_two_edge_states_during_adoption`,
`tradeoff_seed_precision`, `tradeoff_wrong_positive_invisible_to_score`.
<!-- /section: component_adoption_ledger -->

<!-- section: component_seeder [dimensions: component_seeder] -->
### Seeder *(modified: two reading origins)*

As the baseline, plus origins `agent:review` (0.90; written by `onboard adopt
--agent-verdicts`, never by `onboard seed`) and `agent:author` (0.90; written
by `annotate --author`), with `evidence.agent: {by, run, rationale,
packet_sha, test_blob, source_blob, unsure: <n>}`; each origin row carries a
`class:` (rule / measurement / reading / heuristic) that the autonomous floor
reads; `--calibrate` mode; `config.yaml agent_review.measured_confidence`
overrides 0.90 for this repository when calibration measured lower.
<!-- /section: component_seeder -->

<!-- section: component_agent_review_pass [dimensions: component_agent_review_pass] -->
### Agent review pass *(new)*

The mechanism drawn under *The Agent Review Pass*: `onboard review` assembles
bounded, digest-stamped packets (`REVIEW_PAIR` / `REVIEW_ANCHOR` /
`REVIEW_TEST` with assertion lines flagged / `REVIEW_SOURCE` symbols /
`REVIEW_PROSE` / `REVIEW_MEMBER` / `REVIEW_END:<packet_sha>`), `--json`,
`--class`, `--scope`, `--ids`, `--next`, `--calibrate`; `onboard adopt
--agent-verdicts - --by <agent-string> --run <id>` consumes `VERDICT:<id>|
verifies|drives|unsure|<rationale>` lines with the six outcomes (adopt,
reject-revocable, unsure-count, `VERDICT_STALE`, `--by` refusal,
calibration); three sites (in-gate, authoring, bulk) share the intake; the
`aitask-testmap-review` skill is the bulk reader (`review-batch.md`,
profile-aware, resumable through `onboard.yaml phases.review`,
`max_pairs_per_run`); launch surfaces `ait skillrun testmap-review`
(interactive) and `ait codeagent testmap-review [--headless]`
(print mode only under the flag); `verified.testmap-review` in
`models_<agent>.json`; `config.yaml agent_review:` block; budgets: packet
assembly < 300 ms warm, packets bounded by `packet_lines`. Tests: engine
fixtures per language for packet shape and anchor/assertion flagging, every
verdict branch, `VERDICT_STALE`, `--by` grammar refusal, calibration against
a coverage fixture, revocation on a synthetic miss; skill goldens;
`test_codeagent.sh` pins interactive-by-default.
<!-- /section: component_agent_review_pass -->

<!-- section: component_onboarding_engine_verbs [dimensions: component_onboarding_engine_verbs] -->
### Onboarding verbs *(modified)*

As the baseline, plus `review` (packets), `adopt --agent-verdicts` (intake),
`classify --propose` (headless: `kind_proposals[]`, nothing applied), the
`review` phase in the ledger `{status, at, by, counts{reviewed, adopted,
rejected, unsure}, partial: bool}` re-entered at `ONBOARD_NEXT:review` while
partial, `rejections[].by/revocable`, `calibration[]`, and `finish`'s two new
green conditions (`REVOKED:0` in the window, `REVIEW_HUMAN:0`). `detect
--write` writes `completion.mode: auto` and the `agent_review` / `readiness`
blocks when the profile is headless. The engine still never creates a task,
edits a profile or commits.
<!-- /section: component_onboarding_engine_verbs -->

<!-- section: component_onboarding_skill [dimensions: component_onboarding_skill] -->
### Onboarding skill `aitask-testmap-onboard` *(modified: headless row)*

As the baseline, plus `adopt.md` ordering rule → measurement → reading with
`review.md` as the reading sub-procedure (batches of 20, the
`aitask-testmap-review` flow inlined), the attended confirmation per class
showing the agent's verdicts pre-filled, and the rewritten headless row:
level 0 and level 1 in full (rule, measurement, review to budget), level 2
proposes kinds, level 3 not entered, no policy flip because `auto` needs
none. `finish` under a headless profile requires `REVOKED:0` and
`REVIEW_HUMAN:0`.
<!-- /section: component_onboarding_skill -->

**The run surface**

<!-- section: component_test_entrypoint [dimensions: component_test_entrypoint] -->
### Test entrypoint `ait test` *(modified: `auto` resolution)*

As the baseline; under `completion.mode: auto` the POLICY step runs
`readiness`, reads `costs/policy.yaml`, applies the three cadence triggers
and prints `POLICY:auto|selected|next_full_in:<n>` or
`POLICY:auto|full|<cadence:…|not_yet:…>`, writing the first `ADMISSIBLE` as
`approved_by {engine:readiness@<run>, mode: auto}`; the `result=` field
carries the same. `tests/test_ait_test_entrypoint.sh` gains the `auto`
matrix against the fake engine.
<!-- /section: component_test_entrypoint -->

<!-- section: component_test_front_verb [dimensions: component_test_front_verb] -->
### Engine `test` composite *(inherited)*

`select → schedule → run` in one process; the policy is the front's;
unchanged.
<!-- /section: component_test_front_verb -->

<!-- section: component_agent_brief [dimensions: component_agent_brief] -->
### Agent brief *(modified)*

As the baseline, plus `next full in <n> tasks` and the `agent <a>, human
<h>` split on the `TESTMAP:` line, `REVOKED:<n>` when non-zero, the cadence
on `FULL_GATE:`, and one `AGENT_REVIEW:enabled|<confidence>|<calibration>`
line.
<!-- /section: component_agent_brief -->

<!-- section: component_agent_instructions [dimensions: component_agent_instructions] -->
### Agent instructions *(inherited)*

The fourteen-line `## Running Tests` section, unchanged; the author path is
a procedure act, not a run form.
<!-- /section: component_agent_instructions -->

**Workflow and gates**

<!-- section: component_completion_policy [dimensions: component_completion_policy] -->
### Completion policy *(modified: `auto` and the cadence)*

`completion.mode: full|selected|auto`. `auto`: `ait test --gate` runs
`readiness` on every completion run; `NOT_YET` → full with the criterion
printed; `ADMISSIBLE` → the selection unless a cadence trigger fires
(`full_run_every.tasks` counted in `costs/policy.yaml selected_since_full`;
`selection_ratio_above` against the newest full p95; `days` against
`last_full_run.at`), each printed as `POLICY:auto|full|cadence:<trigger>`;
the first `ADMISSIBLE` writes `approved_by {who: engine:readiness@<run-id>,
at, mode: auto, statement: <readiness lines>}` to `costs/policy.yaml`; a
human-written `selected` still needs `approved_by` in `config.yaml` as
before; demotion (`POLICY_DEMOTED:auto->full|<criterion>`) is automatic and
loud; the policy can only fail toward running more; `readiness` prints what
`--gate` would run now and when the next cadence full run falls.
<!-- /section: component_completion_policy -->

<!-- section: component_gates [dimensions: component_gates] -->
### Gates *(modified: where the engine's approval lives)*

`testmap_fresh`, `testmap_check → tests_pass` as the baseline; no selection
gate. Under `auto` the approval record lives in `costs/policy.yaml`, written
by the engine, so `config.yaml` stays a human-authored declaration. The
verifier contract and the exit rows are unchanged.
<!-- /section: component_gates -->

<!-- section: component_workflow_seam [dimensions: component_workflow_seam] -->
### Workflow seam — the data edits *(modified: two config keys, one operation)*

As the baseline, plus `aitask_codeagent.sh`'s `testmap-review` operation,
`verified.testmap-review` in the three `models_*.json` seeds, and the
`agent_review` / `readiness` / `completion.full_run_every` blocks in
`config.yaml`. No profile key is added.
<!-- /section: component_workflow_seam -->

<!-- section: component_workflow_integration [dimensions: component_workflow_integration] -->
### Workflow integration — the procedure edits *(modified: the autonomous branches act)*

As the baseline, plus: `affected-tests.md`'s autonomous `no_selection`
branch runs `annotate --author` for the task's own pairs before falling back
to `attribute --propose`; `aitask-gate-testmap-fresh`'s seeds step reads
packets and, autonomous, adopts through `--agent-verdicts`; the onboarding
skill's `adopt.md` gains `review.md`; the new `aitask-testmap-review` skill;
goldens regenerated for every profile × agent; `aitask_skill_verify.sh`
run.
<!-- /section: component_workflow_integration -->

<!-- section: component_qa_integration [dimensions: component_qa_integration] -->
### aitask-qa integration *(modified: display)*

As the baseline; the discovery table shows `Covered (adopted by agent)` /
`Covered (adopted by human)`; QA still measures whether a test exists, not
who accepted the claim.
<!-- /section: component_qa_integration -->

<!-- section: component_skill [dimensions: component_skill] -->
### Skills *(modified: one skill added, one gate skill changed)*

Four skills: `aitask-testmap` (maintenance; unchanged), `aitask-gate-testmap-fresh`
(the seeds step reads packets; attended pre-fill / confirm / trust-batch;
autonomous adopts), `aitask-testmap-onboard` (the headless row),
**`aitask-testmap-review`** (bulk reader). Every skill's runtime knowledge of
how to run tests is still the seeded block plus `--howto`. All ship Claude
Code first; Codex and OpenCode ports are separate tasks.
<!-- /section: component_skill -->
<!-- /section: components -->

<!-- section: assumptions [dimensions: assumption_*] -->
## Assumptions

Inherited assumptions are listed by key with a one-line restatement; their
full text is in the node metadata and unchanged. Modified and new ones are
stated in full.

### Engine, distribution and install *(all inherited)*

- **`assumption_go_toolchain_available`** — Go ≥ 1.26 in release CI and on
  framework developers' machines; users never need Go.
- **`assumption_go_toolchain_ci_and_dev_only`** — Go is build-time only.
- **`assumption_platform_matrix_sufficient`** — linux/darwin × amd64/arm64.
- **`assumption_release_asset_reachable`** — setup can reach the release
  over HTTPS; the shim never downloads.
- **`assumption_release_assets_reachable`** — air-gapped hosts have the
  fallbacks.
- **`assumption_one_engine_per_framework_version`** — versioned per-user
  directory, exact-version resolution.
- **`assumption_engine_latency_targets`** — the pinned budgets; `onboard
  review` joins the table at < 300 ms warm.
- **`assumption_home_symlink_compatibility`** — every legacy consumer
  dereferences the path.
- **`assumption_legacy_user_root_coexists`** — the two roots coexist this
  release.
- **`assumption_target_repos_accept_aitestmap_root`** — a root `aitestmap/`
  of committed YAML, now also `costs/policy.yaml`.
- **`assumption_testmap_token_no_collision`** — `testmap:` collides with no
  prose.

### The map and freshness *(all inherited)*

- **`assumption_blob_digest_is_staleness_key`**,
  **`assumption_git_history_is_freshness_clock`**,
  **`assumption_passing_run_anchors_edges`**,
  **`assumption_static_granularity_v1`**,
  **`assumption_kotlin_scanner_fail_closed`**,
  **`assumption_annotation_is_comment_only`** — unchanged; `annotate
  --author` and `--agent-verdicts` write comment lines at the same fixed
  positions.

### Variants, broad tests and runners *(all inherited)*

- **`assumption_variant_universe_from_runner_list`**,
  **`assumption_cells_enumerable_by_plugin`**,
  **`assumption_axis_sources_declarable`**,
  **`assumption_axis_membership_declarable`**,
  **`assumption_batch_per_unit_timing_reportable`**,
  **`assumption_areas_express_suite_blast_radius`**,
  **`assumption_broad_tests_area_scoped`**,
  **`assumption_existing_locks_wrappable`** — unchanged.

### Seeding and adoption

- **`assumption_seed_sources_measured`** *(modified)* — one origin table,
  each origin measured and none below 1.0 trusted alone as a *heuristic*;
  the table gains two **reading** origins, `agent:review` and `agent:author`
  at 0.90, whose confidence is calibratable per repository (`onboard review
  --calibrate`, ground truth = coverage facts, else human-reviewed rows) and
  is lowered to the measured agreement ratio when that is below 0.90; every
  origin row carries a class (rule / measurement / reading / heuristic) that
  the autonomous floor reads.
- **`assumption_static_closure_seeds_edges`** *(inherited)* — the static
  closure is the primary seed; it now also supplies the packet's anchor line.
- **`assumption_cochange_is_corroboration`** *(inherited)* — capped at 0.60.
- **`assumption_helpers_separable_by_fanin`** *(inherited)*.
- **`assumption_seeds_select_never_evidence`** *(modified)* — a seed may
  cause a test to run and may never suppress `STALE`, anchor evidence,
  satisfy `require_stamp` or count under `--strict`; it becomes a claim only
  through an explicit adopt. **Autonomous profiles may seed everything and
  may adopt a class only when every member carries a rule, a measurement or
  a reading origin** (`static:package`, `coverage`, `agent:review`,
  `agent:author`) and clears `accept_min`; a heuristic-only class is never
  adopted headless. Falsifier unchanged.
- **`assumption_agent_reads_verify_vs_drive`** *(new)* — an agent given the
  review packet (the anchor line ±20, the test's assertion lines flagged, the
  source's declared symbols, the prose header) distinguishes "verifies" from
  "only drives" at least as precisely as the baseline's ten-sample human
  review of a class, because the judgement is local to the test body: does a
  flagged assertion check something the named source produces? Measured on
  a calibration sample before it is trusted: `onboard review --calibrate 50`
  against coverage facts where a coverage import exists, else against
  human-reviewed rows; agreement ≥ 0.90 keeps the 0.90 confidence, lower
  agreement lowers it, agreement below `accept_min` disables headless
  adoption from this origin and `readiness` says so. Falsifier: a repository
  whose tests assert through an opaque harness (a golden-diff script that
  never names what it checks) — for it the packet has no flagged lines, the
  agent answers `unsure`, and the pair lands in `REVIEW_HUMAN` rather than
  being guessed.
- **`assumption_wrong_positive_claim_only_overselects`** *(new)* — a wrong
  `verifies` verdict produces a stamped edge to a source the test only
  drives; the cost is a needless run when that source changes and a `STALE`
  nag the evidence join usually heals; it never hides a coupling, never
  suppresses a `STALE` row on another edge, and never satisfies
  `UNMAPPED_SOURCE` for a source the test truly does not reach (the closure
  had to contain the source for the packet to exist, or the author had to
  name it inside the task). So agent adoption errs in the direction seeds
  were already allowed to err in, and the only agent verdict that can
  under-select is a rejection. Falsifier: a project that runs `--strict`
  with `on_empty_selection: full` and relies on `UNMAPPED_SOURCE` to force
  full runs — a wrong positive there converts a forced full run into a
  selection; mitigated by the cadence.
- **`assumption_agent_rejection_is_revocable`** *(new)* — a scored full-run
  miss (`PREDICTION_MISSED:<test>`) on a run whose change surface contains
  `<source>` is evidence that `(test, source)` is a real coupling; when that
  pair sits in `rejections[]` with `by: agent:*`, the rejection was wrong
  and is revoked (row removed, pair re-seeded, `AGENT_REJECTION_REVOKED:`
  printed, `max_revoked_rejections` counted); a `by: human` rejection is
  contradicted in print and kept, because evidence removes nags and never
  overrules a person. Falsifier: a miss caused by a coupling through a
  *third* file (the test reaches the source only via a helper) — the
  revocation re-seeds a pair that is then adopted on re-review as `drives`
  again; the second rejection of a revoked pair is marked `REVIEW_HUMAN`.
- **`assumption_headless_launch_is_explicit_opt_in`** *(new)* — no engine
  path, gate, hook or default skill flow launches a code agent in headless
  print mode: the in-gate and authoring sites run inside the session that
  already holds the task; bulk review is `ait skillrun testmap-review`
  (interactive) or, only under `--headless`, `ait codeagent testmap-review`
  — the same opt-in `batch-review` requires, because Claude Code bills print
  mode higher and the framework's shell conventions forbid `claude -p`
  without it. Falsifier: a CI lane with no terminal — for which `--headless`
  is the documented, explicit choice.
- **`assumption_cadence_bounds_exposure`** *(new)* — under `auto`, a wrong
  agent verdict or an unmapped coupling that lets a task land without an
  affected test running is caught by the next cadence full run, which is at
  most `tasks` selected completion runs, `days` wall-clock, or the next
  selection costing ≥ `selection_ratio_above` of full away — whichever comes
  first; every full run scores, so the exposure window is a project-set
  number, printed on every completion run as `next_full_in:<n>`. Falsifier:
  a project whose tasks arrive faster than its full run completes — for it
  `tasks: 1` is `full` with extra steps and the project should stay `full`.

### Onboarding *(inherited)*

- **`assumption_test_tools_detectable`**,
  **`assumption_full_run_expressible_per_repo`**,
  **`assumption_onboarding_is_a_task`** — unchanged; the `review` phase is
  one more phase committed under the level-1 task.

### Run surface and workflow *(all inherited)*

- **`assumption_change_surface_is_intake`** — also the intake for
  `annotate --author`'s not-in-task check.
- **`assumption_task_resolvable_from_session`**,
  **`assumption_helper_degrades_when_absent`**,
  **`assumption_gate_exit_contract_reused`**,
  **`assumption_instructions_block_reaches_agents`**,
  **`assumption_instruction_block_is_read`** — unchanged.
<!-- /section: assumptions -->

<!-- section: tradeoffs [dimensions: tradeoff_*] -->
## Tradeoffs

Inherited tradeoffs are listed by key with a one-line restatement; modified
and new ones are stated in full.

### Advantages

- **`tradeoff_computed_vs_prose`** *(inherited)* — selection, the run
  surface and now acceptance are computed, explained and recorded rather
  than remembered.
- **`tradeoff_engine_speed_enables_per_task_use`** *(inherited)*.
- **`tradeoff_real_scheduler`** *(inherited)*.
- **`tradeoff_noarch_packages_preserved`** *(inherited)*.
- **`tradeoff_one_gate_not_two`** *(modified)* — *advantage:* one completion
  gate whose behaviour is a committed policy, and under `auto` the policy
  needs no one to flip it — a headless repository reaches the selective lane
  by itself. *Disadvantage:* a ledger `tests_pass: pass` says even less by
  itself about what ran; mitigated by `result="MODE:…|policy:auto|
  next_full_in:<n>"`, the `POLICY:auto|…` line on every run, the `gate-` run
  id, `POLICY_DEMOTED` being loud and `readiness` printing what `--gate`
  would run now.
- **`tradeoff_loop_closes_without_a_person`** *(new)* — *advantage:* the
  value the mandate names is realised: seeding, adoption, the policy flip and
  the safety net are each performed by a machine or an agent under a
  committed policy, so a repository onboarded by a headless profile gets a
  per-change-set completion gate within `min_scored_full_runs + 3` tasks of
  level 0 with nobody typing anything; what remains human is a printed list
  (`KIND_PROPOSALS`, `REVIEW_HUMAN`, axes), not an assumed step.
  *Disadvantage:* the map's provenance is now mostly `by: agent` in such a
  repository, and a reader who wants human-reviewed claims must look for the
  `human` split in `onboard status` — it is never hidden, but it is no longer
  the default state.

### Engine and distribution *(all inherited)*

- **`tradeoff_compiled_component_cost`**, **`tradeoff_two_toolchains`**,
  **`tradeoff_setup_network_fetch`**, **`tradeoff_engine_version_skew`**,
  **`tradeoff_strict_version_handshake`**,
  **`tradeoff_engine_absent_on_host`**, **`tradeoff_fallback_runs_more`** —
  unchanged.

### The per-user root *(all inherited)*

- **`tradeoff_two_user_roots`**, **`tradeoff_split_home_rejected`**,
  **`tradeoff_home_migration_window`** — unchanged.

### Map and registry structure *(all inherited)*

- **`tradeoff_registry_directory_complexity`** — one more committed ledger
  file (`costs/policy.yaml`) and three more row fields; still one merge rule.
- **`tradeoff_cell_table_size`**, **`tradeoff_member_annotation_drift`**,
  **`tradeoff_static_scanner_overselection`**,
  **`tradeoff_area_glob_coarseness`**, **`tradeoff_broad_scope_coarseness`**,
  **`tradeoff_axis_declaration_burden`**,
  **`tradeoff_axis_projection_coarseness`**,
  **`tradeoff_intersection_can_underselect`**,
  **`tradeoff_whole_run_filter_soundness`**,
  **`tradeoff_resource_declaration_completeness`** — unchanged.

### Freshness and evidence

- **`tradeoff_stamp_churn`** *(inherited)* — headless level 1 on aitasks now
  performs the ~720-file rewrite the baseline reserved for an attended
  session; the same mitigations apply (comment lines only, batched commits
  named `chore: Onboard testmap — review (t<id>)`, `ADOPT_REFUSED:
  dirty-foreign`), and `max_pairs_per_run` splits the rewrite across runs.
- **`tradeoff_flaky_pass_anchors`**,
  **`tradeoff_evidence_requires_reachable_history`**,
  **`tradeoff_batch_misreport_risk`** *(inherited)* — unchanged.
- **`tradeoff_autonomous_confirmation_weak`** *(modified)* — risk: an
  autonomous run now does more than confirm evidence — it accepts claims
  (`agent:review`, `agent:author`) and flips the policy (`auto`). Narrowed:
  `--confirm-evidenced` remains the only bulk *re-stamp*; an agent
  acceptance is a fresh stamp with `by: agent` provenance that `stale`,
  `explain`, `check` and `readiness` all display and count; the acceptance
  needs a packet the engine cut and a rationale the agent wrote, both
  stored; a `STALE` row is still never confirmed without a person; the
  policy flip is bounded by the cadence and reversed by the demotion; and
  `agent_review.enabled: false` restores the baseline exactly.
- **`tradeoff_attribution_risk`** *(inherited)* — narrowed one more way: the
  authoring agent maps its own new sources at the pre-review step through
  `annotate --author`, so the "looks current and is not" window closes
  during the task in autonomous profiles too.

### Seeding, adoption and onboarding

- **`tradeoff_seed_noise`** *(inherited)* — reviewer fatigue on a
  1,000-seed queue is now spread over agent batches as well as class
  adoption; the noise itself is unchanged.
- **`tradeoff_seed_precision`** *(modified)* — an adopted `covers` edge is a
  machine claim in a human annotation's clothes; with agent adoption it is a
  *reading's* claim, and the reading answers exactly the executes-vs-verifies
  question the closure could not. Narrowed as before (provenance shown,
  `ADOPTED_UNREVIEWED`, over-claim only over-selects, the 0.85 threshold)
  plus: `by: agent` on the row, the stored packet digest and rationale, the
  calibration sample, and `unsure` as an allowed answer so the agent is never
  forced to guess. A coupling the closure does not contain is still caught
  only by a full run's score — or named by the author at the moment it is
  created.
- **`tradeoff_wrong_positive_invisible_to_score`** *(new)* — risk: a wrong
  `verifies` verdict is never detected by the feedback loop, because a
  claimed edge that should not exist can only over-select, and score
  measures under-selection. Its cost is bounded — needless runs of that test
  when the driven source changes, and `STALE` nags on a pair the evidence
  join heals when the test passes — but it accumulates silently in the
  `agent <a>` share of the adopted count. Mitigated by the packet flagging
  assertion lines so the agent answers from evidence, by `unsure` and
  `REVIEW_HUMAN`, by calibration against coverage or human rows before the
  origin is trusted, by `agent_review.measured_confidence` lowering the
  weight where calibration is poor, by the human re-stamp path deleting the
  provenance row, and by `onboard status` reporting the agent share so a
  maintainer can sample it. What remains: a repository with neither coverage
  nor any human-reviewed rows has no calibration ground truth and runs on
  the 0.90 prior, which `readiness` states as `CALIBRATION:none`.
- **`tradeoff_auto_policy_exposure_window`** *(new)* — risk: under `auto` a
  task may land while an affected test never ran, until the next cadence
  full run — the residual risk the mandate names. Its size is a project
  choice: `full_run_every.tasks` (default 5) bounds it in tasks, `days` in
  time, `selection_ratio_above` makes the cheap-to-run-full case run full;
  every completion run prints `next_full_in:<n>`; the demotion still fires on
  the first scored miss; and a project that cannot accept any window keeps
  `full` or `selected`. What remains: `tasks − 1` tasks may merge on a wrong
  selection before the miss is scored, and their dependents may have built
  on them; `blocks_dependents` on `tests_pass` does not help here because the
  gate passed. The mitigation that is honest is the number itself, printed.
- **`tradeoff_periodic_full_run_cost`** *(new)* — disadvantage: the cadence
  spends full runs a human flip would not — one in every `tasks` completion
  runs plus the `days` and ratio triggers. On aitasks (p95 ≈ 400 s full,
  typical selection ≈ 40 s) `tasks: 5` keeps ≈ 80 % of the saving; on
  thinking_app (1,180 s full) the same cadence keeps ≈ 75 % and the project
  may raise `tasks` once its calibration and revocation counters have been
  zero for a while. Mitigated by the ratio trigger (a selection that would
  cost ≥ 60 % of full runs full and scores, so the cadence counter resets
  for free), by every full run doing double duty (evidence anchors, cost
  fold, score), and by `readiness` printing the cadence so it is a decision,
  not a surprise.
- **`tradeoff_agent_review_token_cost`** *(new)* — disadvantage: bulk review
  costs model tokens — 36 packets of ≤ 2,400 excerpt lines on aitasks — and
  a headless launch costs more per token. Mitigated by the packet excluding
  source bodies and capping test excerpts, by the in-gate and authoring
  sites reading in a session that already has the files open (no extra
  launch), by `max_pairs_per_run` bounding one run, by rule and measurement
  classes adopting without any reading, and by the headless launch being an
  explicit flag rather than a default.
- **`tradeoff_two_edge_states_during_adoption`** *(modified)* — until both
  queues are empty a repository has *four* provenances a reader must keep
  apart: seeded, adopted by human, adopted by agent, reviewed; mitigated by
  `by:` printed on every adopted row, the `agent <a>|human <h>` split on
  `check`, `stale --all`, `readiness` and `--howto`, `onboard status` as the
  one place the ratios live, and the rule that no seed and no agent verdict
  ever changes a freshness verdict on another edge. The cost that was real —
  `--strict` waiting on adoption forever in a repo no one reviews — is
  removed for headless repositories and replaced by the exposure window
  above.
- **`tradeoff_bulk_confirmation_granularity`** *(modified)* — adopting per
  evidence class traded depth for feasibility; agent review restores depth
  at feasibility's price: every pair is read, but by an agent. Mitigated as
  before (samples, `--accept-min`, `--scope`, provenance, the per-row path)
  plus the attended pre-fill / confirm / trust-batch choice, and kind changes
  still confirmed individually by a person.
- **`tradeoff_accept_rewrites_history`** *(inherited)* — unchanged; the
  bulk rewrite now also happens headless.
- **`tradeoff_onboarding_partial_coverage`** *(inherited)* — the
  same-package gap on thinking_app is now closed incrementally by
  `agent:author` as tasks touch pairs, not by onboarding; `onboard status`
  still reports the honest ratio.
- **`tradeoff_fail_closed_bootstrap_cost`** *(modified)* — the bootstrap
  order is unchanged and one cost is removed: a repository is no longer
  level 0 "until a human adopts level 1" — a headless profile adopts by
  rule, measurement and reading, and `auto` flips the policy when the scored
  history allows. What remains: kinds and axes are human, `REVIEW_HUMAN`
  pairs wait for a person, and `min_scored_full_runs` full runs must still
  happen before any selection reaches the gate.
- **`tradeoff_verify_build_wired_suites`** *(inherited)* — unchanged;
  headless keeps `verify_build`.

### Run surface and workflow *(all inherited)*

- **`tradeoff_dispatcher_verb_added`** — unchanged; `annotate --author` is a
  `testmap` subverb, not a new dispatcher verb.
- **`tradeoff_generated_brief_limits`** — unchanged.
- **`tradeoff_workflow_surface_growth`** — one more skill
  (`aitask-testmap-review`) with two wrapper surfaces, one `codeagent`
  operation, three `models_*.json` keys, and no new profile key; the same
  mitigations (printed skips, one contract, goldens).
<!-- /section: tradeoffs -->

<!-- section: open_questions -->
## Open Questions

1. Should `agent:author` require a static fact (the test reaches the source
   through the closure) to be adopted, or is "in this task's change
   surface" enough? Proposed: either suffices, because both bind the claim
   to the task; a claim satisfying neither is refused, never seeded.
2. Should the review packet include the source *body* for small sources
   (< 40 lines)? Proposed: no in v1 — the symbol list keeps the packet bounded
   and the question is about the test, not the source.
3. What is the right default for `full_run_every.tasks`? 5 keeps most of the
   saving and bounds exposure to four tasks; a project with dependents
   building on every task may want 2. Proposed: 5, printed by `readiness`
   with the measured saving so the number is chosen with a cost in view.
4. Should a revoked agent rejection re-enter the agent queue or go straight
   to `REVIEW_HUMAN`? Proposed: re-enter once with `evidence.revoked_from`
   in the packet's `REVIEW_PROSE` line; a second `drives` on a revoked pair is
   `REVIEW_HUMAN`.
5. Should calibration be a `readiness` criterion (`agent_review_calibrated`)
   or advisory? Proposed: advisory in v1, printed as `CALIBRATION:none` when
   no ground truth exists, because a repository with neither coverage nor
   human rows would otherwise never reach `ADMISSIBLE` — which is the
   baseline's failure mode restated.
6. Should `verified.testmap-review` in `models_<agent>.json` gate which
   models may write `--by`? Proposed: no — `verified` is informational
   across every operation today; a project that wants a floor sets
   `agent_review.min_verified: <n>` (reserved, not implemented).
7. The baseline's open questions 1–11 stand; question 10 (should adopted
   rows age out into reviewed) is sharpened by agent adoption: with most
   rows `by: agent`, "reviewed" would come to mean "old". Proposed: still
   no; `ADOPTED_UNREVIEWED` and the `agent` share are meant to be read.
<!-- /section: open_questions -->