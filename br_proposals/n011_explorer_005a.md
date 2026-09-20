<!-- section: overview [dimensions: requirements_*] -->
## Overview

### What the feature is

A framework feature, generic across `aitasks`, `thinking_app`,
`thinking_backend`, `aitasks_go` and `aitasks_mobile`, that keeps a **test
map** — a relation between source files and test units — and uses it in six
ways:

1. **Select.** A task's attributed change set becomes a ranked list of tests,
   each line carrying the reason it was selected.
2. **Run.** Selected tests execute through project-defined runners under one
   standard contract, scheduled against declared host resources.
3. **Track.** Every run records cost per unit and per variant, keyed by host
   class, and anchors evidence that the map's claims held.
4. **Learn.** Every full run scores the map's last prediction; misses feed a
   review queue rather than silently rotting the map.
5. **Enforce.** Gates keep the map fresh and consistent and make the
   completion test run a committed policy rather than a habit.
6. **Teach.** One verb, `ait test`, and one generic instructions section are
   how any agent learns to run tests in any onboarded project; one skill
   brings a repository's existing test tree onto the map in graded levels.

The engine is a static Go binary installed per user under
`$AITASKS_HOME/engine/v<VERSION>/`; the map lives in a committed `aitestmap/`
directory at the repository root; the adoption state of machine-proposed
edges is a three-file ledger (`seeded.yaml` → `adopted.yaml` → reviewed
stamps) whose transitions are driven by agents — a reader of the test body
corroborates each seed (`agent:review`), measured origins adopt on their
own, and the agent that wrote a change stamps its own pairs
(`agent:author`) — with a person kept only where a wrong answer changes
staleness semantics (kinds); onboarding is a resumable skill that runs one
aitask per level and reaches level 1 in attended and headless profiles
alike; the completion policy may flip itself (`completion.mode: auto`)
behind a cadence full run that keeps scoring alive; the run surface is
`ait test` in three modes (interactive, completion, advisory) over an engine
`test` composite, with a bash front that still answers correctly when no
registry or no engine exists.

### How this differs from the baseline

The engine, the map, selection, scheduling, cost, scoring, the run surface
and the one completion gate are unchanged. What changes is **who closes the
loop**. The baseline already selects adaptively the moment level 0 runs:
seeded edges select at distance 1 in every mode, and every full run scores
the last prediction. What it held behind a person were two things — whether
the map's claims are *enforced* (adoption, which needs a stamp) and whether
the completion gate *shrinks* from the full suite to the selection (the
policy flip). Until both happened, `tests_pass` ran everything and the
feature's value leaked. The baseline's stated reason for the person was the
gap between *executes* and *verifies*: static closure proves a test runs a
script, not that it checks it, and that is a semantic judgement. This node
keeps the judgement and changes who may make it: **a reader of the test
body**, which a person or an agent can be. Four additions follow:

1. **An `agent:review` origin (0.90).** A review pass reads each seeded
   pair — test body beside source — and answers *verifies*, *drives* or
   *unclear*, anchoring a *verifies* verdict to an assertion line the engine
   checks exists. The verdict is stored on the seed row with model, run id,
   test blob and rationale. Under the existing noisy-OR a static edge plus a
   verdict is 0.99; `onboard adopt --class` becomes autonomous for every
   class whose pairs carry a verdict, and the provenance row reads
   `adopted(static:invocation+agent:review 0.99)`, distinct from a human
   stamp. The reviewer is the agent already running the onboarding skill,
   never a spawned print-mode process (the framework's headless-billing
   rule); a crew of headless reviewers is an explicit opt-in.
2. **Measured origins adopt on their own.** The autonomous floor was
   "confidence 1.0"; it is now "a measurement": `static:package` (1.00) and
   `coverage` (0.95) are measured, not heuristic, so level 1 is headless for
   every Go project and for any Python, Go or Kotlin project that turns
   per-unit coverage on.
3. **A self-approving policy behind a cadence full run.**
   `completion.mode: auto` flips to selection when `readiness` reports
   `ADMISSIBLE`, records `approved_by: engine:readiness@<run>`, keeps the
   loud automatic demotion, and adds the safety net that replaces the
   person: a scheduled full run — every Nth completion, when the selection
   would cost more than a fraction of the full suite anyway, or after D days
   — whose score covers every prediction since the last full run, so scoring
   never stops and a miss is bounded by the cadence. The invariant "the
   policy can only fail toward running more" is kept and extended: a
   cadence full run is never skipped by a demotion or an empty selection.
4. **The authoring agent annotates.** The pre-review procedure's autonomous
   branch no longer only proposes. For a source or test on the task's own
   change surface, the agent that wrote the change writes the stamped
   `testmap:covers` line itself with origin `agent:author`, adopted with a
   provenance row and riding the `(t<id>)` commit through the Step-8 review.

Two things deliberately stay human. **Kind changes** (integration, e2e,
device) are confirmed individually because a wrong kind silently changes
staleness semantics and no run gives the agent evidence to check itself
against. And **an agent verdict never removes selection**: a *drives*
verdict parks a seed — it keeps selecting, leaves the adoptable set and is
listed for a person — because the loop's safe direction is "run more", and
the one thing an agent must not be able to do alone is make a test stop
running. Every heuristic-vs-claim rule of the baseline is otherwise kept:
seeds still claim nothing, `--strict` still counts only stamps, and the full
suite is still the completion gate until `ADMISSIBLE`.

### Reading guide

*Architecture* introduces the vocabulary, the process boundary, the registry
and the design decisions. *Data flow* walks a task, a completion run, the
onboarding levels and the policy flip. *The adoption model* is the seed →
adopted → reviewed ledger with its origin table. *Onboarding* is levels ×
phases and the per-repository detection results. *The run surface* is
`ait test` in full: forms, resolution, output, exit contract, `--howto` and
the seeded instructions section. *The workflow seam* is every concrete edit
to task-workflow, gates and `aitask-qa`, including the author branch of the
pre-review procedure and the `auto` completion policy. *Components*,
*Assumptions* and *Tradeoffs* are the reference sections; *Open questions*
closes.
<!-- /section: overview -->

<!-- section: architecture [dimensions: component_test_entrypoint, component_test_front_verb, component_onboarding_engine_verbs, component_onboarding_skill, component_seeder, component_agent_brief, component_agent_instructions, component_completion_policy, component_workflow_seam, component_workflow_integration, component_go_engine, component_registry_loader, component_engine_binary, component_gates, component_adoption_ledger] -->
## Architecture

### Concepts

**Test unit and id.** A unit is a test file, a member of a file
(`<path>#<member>`, opened by a `testmap:unit` block) or a variant of a unit
on a declared axis (`<unit>@<variant>`). Ids are what runners list and what
the cost ledger, evidence and predictions are keyed by.

**Edge.** A `testmap:covers <source>` line in a test file (or a member block)
says the unit exercises that source. A *stamped* edge carries
`@<date>/<blob10>` — the git blob digest of the source at the moment a person
confirmed the claim. The digest, never the mtime or the date, is the
staleness key.

**Seeded, adopted, reviewed.** A machine-proposed edge passes through up to
three states. *Seeded* rows live in `registry/seeded.yaml`, select tests and
claim nothing; a seed may carry an *agent verdict* (`verifies` / `drives` /
`unclear`) from the review pass, which changes what may adopt it and never
whether it selects. *Adopted* rows are stamped edges accepted as a whole
evidence class — by a person, or autonomously when the class is a measured
origin or every pair in it carries a `verifies` verdict — and the stamped
edges the authoring agent wrote for pairs on its own change surface; their
machine origin is recorded in `registry/adopted.yaml` until a person
re-stamps the pair. *Reviewed* edges are stamped edges a named person
confirmed pair by pair; they carry no provenance row.

**Kind and scoped row.** Unit tests are edges in the per-file graph.
Integration, e2e and device tests are *scoped rows* in
`registry/_scoped.yaml`: they declare areas, scope globs or trigger globs
instead of `covers`, join the ranked list at distance 1 as sinks, and are
never digest-stale.

**Axis and variant.** A project whose tests form a product of facets
(thinking_app: 49 screens × a matrix of locale × direction × geometry)
declares the axis in `axes.yaml`; the runner's `list` enumerates the
variants; the selector joins changed paths to facet values and selects only
the variants carrying them.

**Runner and resource.** A runner speaks `describe` / `list` / `run`; the
builtins (`bash-file`, `pytest`, `go-test`, `gradle-class`, `suite`,
`device`) cover the target repositories, and a project script may shadow one
by name. A resource (`mutex`, `semaphore`, `admission`, `allocator`) is a
declared host constraint the scheduler honours across worktrees.

**Level and phase.** A repository's *level* (0–3) is a property of its tree:
what the registry has. A *phase* is a step of the onboarding run recorded in
`aitestmap/onboard.yaml`. Levels say what exists; phases say how far a run
got.

**Mode and policy.** `ait test` runs in *interactive* mode (the developer
loop), *completion* mode (what the `tests_pass` gate executes) or *advisory*
mode (a pre-review run that can never block). The *completion policy* in
`aitestmap/config.yaml` decides whether completion runs the whole registry
or the task's selection: `full` always runs everything, `selected` runs the
selection after a person approved it, `auto` runs the selection once
`readiness` is `ADMISSIBLE` and runs the whole registry on a *cadence* — the
Nth completion, an expensive selection, or D days since the last full run.

### The process boundary

Parse, walk, match, digest, schedule, seed and adopt happen in Go. The gate
ledger, task files, profile files, `project_config.yaml`, `gates.yaml`,
agent-instructions files and the shell environment are owned by bash scripts
and skill prose. Concretely:

- The engine never writes `aitasks/`, `aiplans/`, `.aitask-data/`, a gate
  ledger, `project_config.yaml`, `gates.yaml`, a profile or `CLAUDE.md`, and
  never invokes an `aitask_*.sh` script.
- The `onboard` verbs never create a task, edit a profile or commit; the
  onboarding skill does those through `aitask_create.sh --batch`,
  `aitask_pick_own.sh`, the settings helpers and `aitask_task_commit.sh`.
  The engine reads `onboard.yaml`'s `task:` and `level:` fields and writes
  its phase rows.
- The bash front of `ait test` owns everything that must work with no
  engine: mode, task and intake resolution, the completion policy check, the
  `test_command` and `fallback_command` fallbacks, and the advisory verdict.
- The engine never runs a code agent. The review pass is two verbs on the
  engine side — `onboard review` writes batch files and `onboard review
  --answer` consumes verdict lines — and the reading in between is done by
  the agent already in session (the onboarding skill's agent, the
  pre-review procedure's agent), or by crew agents a person launched behind
  the framework's explicit headless opt-in. No script of this feature
  invokes `claude -p` or its equivalents.

### Process map

```
./ait test [...]                                   agent · human · tests_pass verifier (test_command) · pre-review procedure (--advisory)
 └─ .aitask-scripts/aitask_test.sh                 bash front, ~150 lines: MODE / TASK / INTAKE / POLICY / fallback / advisory
      │  no aitestmap/            → TESTMAP_ABSENT:<hint> → aitask_run_project_command.sh test_command   (advisory: VERDICT:skip REASON:registry_absent)
      │  engine absent            → interactive: ENGINE_MISSING:<path>|<repair> exit 3     (advisory: VERDICT:skip REASON:testmap_absent)
      │                             completion: per config.yaml completion.engine_absent (error | fallback_command)
      │  MODE   completion iff --gate or $AIT_GATE_TASK_ID · advisory iff --advisory · else interactive
      │  TASK   --task > $AIT_GATE_TASK_ID > aitask/<task_name> branch > single own lock (aitask_lock.sh --list-mine) > NO_TASK
      │  INTAKE aitask_change_surface.sh list <id> | --dirty (printed) | --all | <path|id>...
      │  POLICY completion: config.yaml completion.mode full|selected|auto re-checked against `readiness`; auto → cadence check (full_every_n / full_when_selection_over / full_after_days)
      └─ .aitask-scripts/aitask_testmap.sh          the shim: resolves $AIT_TESTMAP_BIN > AIT_ENGINE=dev > $AITASKS_HOME/engine/v<V>/
           └─ ait-testmap test … | select | schedule | run | brief | onboard … | readiness | costs …
                internal/registry       six tables + seeds (registry/seeded.yaml) + adopted (registry/adopted.yaml)
                internal/seed           origins static:{package,invocation,import} · coverage · agent:{review,author} · observed · convention · plan · prose · cochange; noisy-OR
                internal/onboard        detect · inventory · seed · review (batches ⇄ --answer) · classify · adopt (--auto) · reject · scaffold · status · finish; the onboard.yaml phase ledger
                internal/brief          the generated run brief (`brief`, rendered by `ait test --howto [--md]`)
                internal/selectr        graded walk + seeded edges at d1 · explain --sources · the `test` summary lines
                internal/runner         contract + subsumed_by: · fallback_command: · the `full` suite wrapper · bash-file list --invocations
                internal/annot          grammar v3 + line-targeted rewriter; adopt is a caller, at the fixed per-language position
                internal/deps           scanners; direct-invocation, direct-import and package facts exposed to internal/seed
                internal/cost           ledger + costs --gate-timeout; run_id prefixes test- / gate- / full-
                internal/feedback       score (window scoring after a cadence full run) · attribute (+ --propose) · readiness (+ LEVEL / NEXT / ADOPTED_UNREVIEWED / SEEDED / POLICY / CADENCE / REVIEW_AGREEMENT)
                internal/{axes,changesurface,sched,stale,gitx,platform}
                  ├─ exec:  git, runner scripts / builtins, admission / allocator commands, scanner plugins
                  └─ files: aitestmap/** · .aitask-testmap/ (runs, ledger, onboard/<run>/seed.json, onboard/<run>/review/<n>.md) · XDG cache (deps; cochange matrix by HEAD sha)

.aitask-scripts/lib/gate_verifier_lib.sh           run_project_command_key(): + 75 → error (command_refused), 3 → error (command_errored) for opted-in keys;
                                                   exports AIT_GATE_TASK_ID / AIT_GATE_RUN_ID around the command
.aitask-scripts/gates_reference.yaml               + testmap_fresh (procedure), testmap_check (unlocks: [tests_pass]); no separate selection gate
.aitask-scripts/aitask_gate_testmap_check.sh       machine verifier; reports SEEDED:<n>, ADOPTED:<n>, UNMAPPED_SOURCE:<path>
.aitask-scripts/aitask_gate_tests_pass.sh          unchanged; runs test_command = ./ait test under the opt-in
.aitask-scripts/aitask_setup.sh                    install_engine_binary() + report_testmap_state() → TESTMAP:<state>
.claude/skills/aitask-testmap-onboard/             profile-aware stub + SKILL.md.j2 + one procedure file per phase (review.md reads batches, writes verdicts)
.claude/skills/aitask-testmap/                     maintenance skill; opens with `ait test --howto`; hands an un-onboarded repo to onboard; `annotate --author`
.claude/skills/aitask-gate-testmap-fresh/          procedure gate + "adopt seeds on touched test files" step (verdict-bearing seeds shown with their rationale)
.claude/skills/task-workflow/SKILL.md.j2           Step 7: one paragraph (the loop) + the pre-review Affected Tests Procedure (affected-tests.md; autonomous branch = annotate --author)
.claude/skills/task-workflow/build-verification.md + one branch: verdict error / command_refused | command_errored
.claude/skills/aitask-qa/{test-discovery,test-execution}.md   registry-first branches
seed/aitasks_agent_instructions.seed.md            + `## Running Tests` (generic; installed into every agent surface by ait setup)
engine/                                             Go source — framework repo only, excluded from the tarball
```

### The registry directory

```
aitestmap/
  config.yaml            unit_covers_max, suite_budget_s, bootstrap_until, require_stamp, broad_review_days, concurrency,
                         broad_after_unit, device_policy, host_class, flake_threshold, symbol_scanners, run_gate_admission
                         + completion: {mode full|selected|auto, deferred, on_empty_selection, engine_absent,
                                        auto: {full_every_n, full_when_selection_over, full_after_days}}
                         + agent_review: {confidence 0.90, batch 25, min_agreement 0.85, calibration_min 30}
                         + conventions: [{test, source}]  helper_roots: [...]  helper_fanin: 0.05
                         + exclude: [globs]  docs: [paths]  notes: | (<=10 lines)  broad_threshold_s: 60
  onboard.yaml           phase ledger: {contract, task, level, phases{...}, rejections[], reviews[]}
  axes.yaml · runners.yaml · resources.yaml      runners.yaml written by onboard detect --write, confirmed per runner
  registry/
    _scanned.yaml · _scoped.yaml · observed.yaml · areas.yaml · <area>.yaml
    seeded.yaml          the queue; generated by onboard seed; a row gains an agent verdict on review --answer; rows leave on adopt / reject
    adopted.yaml         provenance of class-adopted and author-written edges; a row leaves when a human re-stamps the edge
  costs/ · runners/ · scanners/                  runners/<name>.sh may come from onboard scaffold --runner
```

The onboarding additions to `config.yaml`:

```yaml
completion:
  mode: auto                 # full | selected | auto — detect --write writes auto; selected is written only by the
                             # skill's --policy re-entry after READINESS_DECISION:ADMISSIBLE with a human approved_by;
                             # auto behaves as full until readiness is ADMISSIBLE, then runs the selection and lets
                             # the cadence below force full runs; a project that wants a person in the flip sets full
  deferred: run              # run | fail — completion never silently drops a row the interactive budget would cut
  on_empty_selection: skip   # skip (exit 2 → gate skip under the opt-in) | full
  engine_absent: error       # error (exit 3) | fallback_command (the full: true suite runner's fallback_command:, MODE:fallback)
  auto:                      # the cadence that replaces the human approver under mode: auto — each rule is a printed reason
    full_every_n: 5          # the Nth completion run since the last full run is full (a miss survives at most N-1 tasks)
    full_when_selection_over: 0.6   # a selection estimated at >= 60 % of the full-suite p95 runs full — the saving is not worth the window
    full_after_days: 7       # a completion run more than 7 days after the last full run is full
agent_review:                # the agent:review origin (see The Adoption Model)
  confidence: 0.90           # provisional; REVIEW_AGREEMENT below min_agreement over >= calibration_min human-reviewed pairs demotes it to 0.60
  batch: 25                  # pairs per review batch file
  min_agreement: 0.85
  calibration_min: 30
conventions:                 # seeded by onboard detect per framework; the `convention` origin (0.60)
  - {test: "tests/test_{stem}.sh", source: ".aitask-scripts/aitask_{stem}.sh"}
  - {test: "tests/test_{stem}.sh", source: ".aitask-scripts/lib/{stem}.sh"}
  - {test: "tests/test_{stem}.py", source: ".aitask-scripts/lib/{stem}.py"}
helper_roots: ["tests/lib/**", "**/testing/**", "**/testdata/**"]
helper_fanin: 0.05           # a closure path reached by ≥5 % of a runner's units is a helper, not a subject
exclude: ["tests/golden/**", "tests/data/**"]                          # never listed, never UNREGISTERED
docs: [aidocs/testing/change-aware-verification.md]                    # printed by --howto
notes: |                                                               # printed by --howto verbatim, <=10 lines
  A shared component change (ui/components/*) must run the full gate; preview renders without a verdict.
broad_threshold_s: 60        # classify signal — a recorded p95 above this proposes a broad kind
```

### Where state lives

| data | location | written by |
|---|---|---|
| seed queue | `aitestmap/registry/seeded.yaml` rows `{test[#member], covers, origin[], confidence, evidence{}, proposed_at, verdict?}` — `evidence.agent_review {verdict, assert_line, rationale, model, run, test_blob, at}` once reviewed | `onboard seed --apply`; `attribute --propose`; `onboard review --answer` (adds the origin and the verdict, never removes a row); rows removed by `onboard adopt` / `reject` |
| adopted-edge provenance | `aitestmap/registry/adopted.yaml` rows `{test, source, origin[], confidence, adopted_at, task, by}` — `by` is `human`, `auto:measured`, `auto:review` or `author` | `onboard adopt --class` (a person or `--auto`); `annotate --author`; rows deleted when `verify`, `annotate`, `stale --confirm-source` or a per-row `adopt` re-stamps that edge |
| phase ledger | `aitestmap/onboard.yaml` `{contract, task, level, phases{detect, inventory, seed, waivers, enable, full_run, review, adopt, classify, scaffold, finish: {status, at, by, counts}}, rejections[], reviews[]}` — `reviews[]` is the verdict memory `{test, source, verdict, test_blob, run}` so a pair is never re-reviewed for the same test bytes | the engine's `onboard` verbs; read by `onboard status`, `report_testmap_state()`, the skill's re-entry |
| seed dump for review | `.aitask-testmap/onboard/<run-id>/seed.json` (gitignored), attached to the level task with `ait attach` | `onboard seed --json --out` |
| review batches | `.aitask-testmap/onboard/<run-id>/review/<n>.md` (gitignored): ≤ `agent_review.batch` `REVIEW_ITEM` blocks per file, each with the pair, the seed's evidence, the test excerpt around every invocation / import line and the source's header and exported symbols | `onboard review`; read by the session agent (or a crew agent); answered through `onboard review --answer <file>` |
| completion policy, cadence, review knobs, conventions, helper roots, docs, notes, excludes | `aitestmap/config.yaml` | `onboard detect --write` (level 0: `completion.mode auto`, `completion.auto`, `agent_review`); the skill's `enable` phase (`docs:`, `notes:`); the `--policy selected` re-entry (`completion.mode`, `run_gate_admission.approved_by {who, at, statement}`); `ait test --gate` under `auto` (`run_gate_admission.approved_by {who: engine:readiness, run, at}` on the first admissible run, `last_full_run` after every full run) |
| test entry and exit-contract opt-in | `aitasks/metadata/project_config.yaml`: `test_command: ./ait test`, `gate_command_exit_contract: [test_command]` | the skill's `enable` phase, confirmed once as a table |
| gate declarations | profiles' `default_gates` (`tests_pass`, `testmap_check`, `testmap_fresh`; `rendered_gates` where present); `gates.yaml` `tests_pass.timeout_seconds` | the skill's `enable` phase; the timeout from `costs --gate-timeout` after the first full run |
| agent instructions | `CLAUDE.md` `>>>aitasks` block, `AGENTS.md`, `.codex/instructions.md`, the OpenCode mirror | `ait setup` from the seed; a hand-maintained `CLAUDE.md` by the level-0 task |
| runs, ledger, predictions | `.aitask-testmap/runs/<run-id>/`, `.aitask-testmap/ledger.jsonl` (gitignored); `aitestmap/costs/<hostclass>.yaml`, `aitestmap/costs/predictions.yaml` (committed) | every run; `costs --update`; `score` |
<!-- /section: architecture -->

<!-- section: design_decisions [dimensions: component_adoption_ledger, component_seeder, component_onboarding_skill, component_test_entrypoint, component_test_front_verb, component_gates, component_completion_policy, component_workflow_integration, component_annotation_scanner, assumption_seeds_select_never_evidence, assumption_cochange_is_corroboration, assumption_onboarding_is_a_task, assumption_helper_degrades_when_absent, assumption_gate_exit_contract_reused, assumption_annotation_is_comment_only, assumption_task_resolvable_from_session] -->
## Design decisions

Each decision names the alternative it rejects, because the alternative is
the shortest way to say what the choice protects.

1. **Three adoption states, not two.** A queue that *selects but never
   claims* is the right state before anyone has accepted an edge; a stamped
   edge with a provenance row is the right state after a whole evidence
   class was accepted; a per-pair acceptance is a reviewed claim and needs no
   provenance. Collapsing to "queue or stamped" would either force per-row
   review of ~720 files or let a class-level yes masquerade as review.

2. **Autonomous adoption needs a measurement or a reader of the test body,
   never a heuristic alone.** Acceptance is the one act that turns evidence
   into a claim the freshness machinery enforces, and the judgement it needs
   — does this test *verify* this source or only *drive* it — is a reading
   of the test body, which a person or an agent can do; a static closure
   cannot. So a headless profile may adopt three things: a *measured* origin
   (`static:package`, `coverage` — a language rule or a runtime
   observation, never a guess), any pair carrying an agent `verifies`
   verdict anchored to an assertion line (`agent:review`), and the pairs the
   authoring agent stamped on its own change surface (`agent:author`).
   `static:invocation`, `static:import`, `convention`, `plan`, `prose`,
   `cochange` and `observed` remain heuristics: they select, order the
   queue and raise a verdict's combined confidence, and none of them adopts
   by itself. "Only a person" became "only a reader" — the number that
   distinguishes measured from heuristic (1.0 / 0.95 versus ≤ 0.90) is kept
   so a reader of the provenance still sees which kind of evidence stamped
   the edge.

3. **One origin table, co-change capped.** The evidence sources that seed
   edges are one measured table with one confidence vocabulary. Co-change is
   capped at 0.60 and needs two distinct task groups because the measured
   group shape (336 groups in 400 aitasks commits, 1.14 commits per group,
   a few tests paired with a few scripts) never says which test covers which
   script — it corroborates a static edge and cannot manufacture one.

4. **Levels × phases, one aitask per level.** Levels describe the registry
   (what exists); phases describe a run (how far it got). Both are needed
   for a half-migrated repository to be a known state with a next step. A
   level is one aitask because it may wait weeks on full-run history; a
   phase commits on its own because it may span sessions.

5. **The first full run is the level-0 task's own `tests_pass`.** A separate
   "full run" phase would be the same run outside the gate ledger. Landing it
   as the task's Step-9 gate puts every unit's `last_pass` anchor, the cost
   fold and the (empty) prediction score under one `(t<id>)`.

6. **`bootstrap_until` is level-0 day + 90.** Level 0 is unstamped by
   design and a thousand-row seed queue is not adopted in 30 days; `finish`
   may shorten it.

7. **One verb, two layers.** The parts that must run with no engine
   (fallbacks, task resolution, the advisory verdict) are bash; the pipeline
   (select → schedule → run) is one Go composite. A single Go verb would
   leave a repository with no engine unable to run its own `test_command`.

8. **Advisory is a mode, not a second script.** The pre-review helper's
   `VERDICT:/REASON:` contract and its degrade-to-skip rule are
   `ait test --advisory`. One script, one exit-contract statement, one set
   of permission touchpoints.

9. **The loop is a paragraph; the pre-review run is a procedure.** The
   in-loop call needs no procedure: "run `./ait test` after each meaningful
   change". The pre-review run needs one because it has a branch table and
   because it is the run guaranteed to write a prediction record in every
   profile.

10. **One completion gate under a committed policy that may approve
    itself, behind a cadence full run.** The existing `tests_pass` runs
    `./ait test --gate`; whether that is the whole registry or the task's
    selection is `completion.mode` in `config.yaml`. Under `selected` a
    person flipped it after `ADMISSIBLE`; under `auto` the engine flips it
    on the first admissible completion run, records
    `approved_by: engine:readiness@<run>`, and is demoted automatically and
    loudly exactly as before. What replaces the person's judgement is not
    trust in the map but a **cadence**: the Nth completion since the last
    full run, a selection estimated at more than a fraction of the full
    suite, or D days without a full run each force `run --all`, and that
    run scores every prediction since the last full run. The invariant
    holds and is extended: the policy can only fail toward running more,
    and a cadence full run is never skipped by `on_empty_selection` or by a
    demotion. A second, selection-only gate would give an agent two
    commands to learn and a project two declarations to keep consistent,
    and the legacy Step-9 path and `aitask-qa` would never reach the
    selective lane.

11. **Adoption writes comment lines only.** A Python module docstring is
    read by the grammar but never written into, because that changes
    `__doc__`; a member seed lands inside its `testmap:unit` block; a file
    with no comment leader the grammar knows is skipped, not restructured.

12. **A suite wired as `verify_build` is asked about, not moved.**
    thinking_backend's `run_script_tests.sh` also enforces a shellcheck
    baseline; moving it would drop the lint half, leaving it would run the
    suite twice. The skill asks and defaults to keeping it, adding
    `test_command: ./ait test` over the detected units.

13. **Task resolution is implicit with an explicit override.** The worktree
    branch (`aitask/<task_name>`) or the single Implementing lock this user
    holds identifies the task; `--task` overrides; two candidates are
    `AMBIGUOUS_TASK`; the advisory form always passes `--task` because the
    procedure knows the id.

14. **An agent verdict moves an edge only toward more claims, never toward
    less selection.** A `verifies` verdict makes a seed adoptable; a
    `drives` or `unclear` verdict *parks* it — the row stays in
    `seeded.yaml`, keeps selecting at distance 1, leaves the adoptable set,
    is never re-reviewed for the same test bytes, and is listed for a
    person as `REVIEW_PARKED:<n>`. Only a person's `onboard reject` removes
    a seed. The alternative — letting the agent's rejection land as a
    rejection — would let one wrong reading make a test stop running for a
    change, which is the one direction the whole design refuses to fail in.

15. **The reviewer is the agent already in session, never a spawned
    print-mode process.** The engine writes review batches and consumes
    verdict lines; the reading between them is done by the agent running
    the onboarding skill (attended or headless — the `remote` profile's
    agent is headless already) or by crew agents a person launched with the
    framework's explicit `--headless` opt-in, which is where the higher
    per-token rate of print mode is accepted knowingly. A verifier that
    shelled out to `claude -p` would put that cost on every gate run and
    would violate the rule every other script of the framework follows.

16. **The authoring agent stamps only what it touched.** `annotate
    --author <test> <source>` refuses a pair unless both the test and the
    source are on the current task's change surface
    (`ANNOTATE_REFUSED:outside-change-surface`); a pair with no static
    relation between them is accepted but flagged `AUTHOR_UNCORROBORATED`
    so a person can see a claim the closure does not support. Letting the
    agent annotate anything would turn `UNMAPPED_SOURCE` silencing into a
    habit; limiting it to the change surface keeps the claim inside the diff
    a reviewer already reads at Step 8.

17. **Kinds stay human.** A wrong `covers` edge over-selects and shows its
    provenance; a wrong kind moves a test between the digest-stale and the
    area-stale regimes and no run gives an agent evidence to check its
    answer against. `onboard classify` keeps printing proposals with reasons
    in every profile; a headless run records them as `CLASSIFY_PENDING`
    and writes no kind line.
<!-- /section: design_decisions -->
<!-- section: data_flow [dimensions: component_test_entrypoint, component_test_front_verb, component_onboarding_engine_verbs, component_onboarding_skill, component_seeder, component_completion_policy, component_workflow_integration, component_workflow_seam, component_selector, component_annotation_scanner, component_freshness, component_feedback_tools, component_cost_ledger, component_registry_loader, component_staleness_tool, component_engine_packaging] -->
## Data Flow

### A task in steady state

```
Step 7  edit source ──▶ ./ait test                      MODE:interactive TASK:<id> (branch | lock) INTAKE:change-surface
                        change surface ──▶ test composite ──▶ select (edges ∪ adopted ∪ seeds ∪ deps ∪ rules ∪ axes ∪ test-dep) --include-stale
                        ──▶ schedule ──▶ run ──▶ ledger rows (run_id test-…) ──▶ SELECTED: / UNMAPPED_SOURCE: / UNANNOTATED_TEST: / RESULT:
                        ──▶ prediction record for this task (newest wins)
        before Step 8 ──▶ ./ait test --advisory --task <id> ──▶ VERDICT:/REASON:/LOG: ──▶ prediction record ──▶ plan Final Implementation Notes
                        UNMAPPED_SOURCE / UNANNOTATED_TEST ──attended offer──▶ annotate --author (default) | attribute --propose | continue
                                                           ──autonomous──▶ annotate --author <test> <source> for pairs on the change surface
                                                                           (→ stamped line + adopted.yaml {origin agent:author, by author, task}) else continue
Step 8  procedure gates ──▶ testmap_fresh ──▶ stale --task (STALE / EVIDENCED / UNSTAMPED, adopted(...) shown) + adopt seeds on touched test files
                                              (a verdict-bearing seed shows its rationale; a `verifies` seed is adopted without asking in autonomous profiles)
Step 9  ait gates run ──▶ testmap_check (SEEDED:, ADOPTED:, UNMAPPED_SOURCE:, strict past bootstrap) ──▶ tests_pass = ./ait test --gate (policy)
        POLICY:full     ──▶ run --all ──▶ score the newest prediction
        POLICY:auto     ──▶ readiness ADMISSIBLE? no → full · yes → cadence due? yes → full (window score) · no → selection (MODE:selected|policy:auto|full_in:<k>)
        full run ──▶ automatic score against every unscored prediction since the last full run ──▶ PREDICTION_MISSED:<id>|<task> ──▶ attribute (decide | --propose → seeded.yaml)
```

Every task-scoped selection writes the task's prediction record; the newest
one is what the next full run scores. The interactive loop may run many
times or never; the pre-review advisory run happens once in every profile,
which is why a scored prediction exists for every task that reaches
completion.

### A completion run under policy

```
ait gates run 1234 → testmap_check → pass → unlocks tests_pass
   → aitask_gate_tests_pass.sh → run_command_gate → export AIT_GATE_TASK_ID=1234 AIT_GATE_RUN_ID=<run> → `./ait test`
      MODE:completion  POLICY:full                       → run --all (subsumed_by honoured) → exit 0/1/2/3/75
      MODE:completion  POLICY:selected                   → readiness: all met → task selection, deferred rows RUN
      MODE:completion  POLICY:selected → POLICY_DEMOTED:selected->full|max_false_negatives → run --all
      MODE:completion  POLICY:auto                       → readiness NOT_YET → POLICY:auto|full|not_admissible → run --all (identical to full)
      MODE:completion  POLICY:auto, first ADMISSIBLE run  → POLICY_FLIPPED:auto->selected|engine:readiness@<run> → config.yaml approved_by written (ait: commit by the verifier's caller) → selection
      MODE:completion  POLICY:auto, cadence due           → POLICY:auto|full|cadence(every_n 5/5 | selection_over 0.63 | days 8) → run --all → window score
      MODE:completion  POLICY:auto, otherwise             → task selection, deferred rows RUN, full_in:<k> printed
   → run_project_command_key: 0 pass · 1 fail · 2 skip · 3 error(command_errored) · 75 error(command_refused)   [opted-in key]
   → ledger block result="MODE:full|720 units|policy:full" or result="MODE:selected|14|policy:auto|full_in:3" → orchestrator: pass / fail / skip / error (retry within max_retries)
   → after any full run: PREDICTION_SCORED:<r1..rk>|<run> PREDICTION_FALSE_NEGATIVES:<n> → costs/predictions.yaml (every prediction since the last full run scored, each miss attributed to the task whose change surface reaches the failing unit, culprit ids from `git log -M` when history is reachable) → readiness input; last_full_run recorded
```

### Onboarding level 0: existing tests → registry → first anchored run

```
repository (tests, scripts, build files, project_config.yaml, code_areas.yaml, git history)
   ▼  onboard detect [--write]        FRAMEWORK: / AGGREGATE_RUNNER: / SERIAL_LIST: / RESOURCE_HINT: / SUITE_CANDIDATE: / UNIVERSE: / UNLISTED: / RUNNER_SCRIPT_NEEDED:
   │                                  --write → aitestmap/{config,runners,resources}.yaml · registry/areas.yaml   (runner table confirmed per runner)
   ▼  onboard inventory               scan + every runner list + check → _scanned.yaml · UNREGISTERED: resolved (bind | exclude:)
   ▼  onboard seed [--apply] [--json --out]   deps facts (invocation, imports, package) + conventions + git log (t<id>) + plans + prose [+ coverage]
   │                                  → SEED:<test>|<source>|<origins>|<confidence> · SEED_HELPER: · SEED_READS: · SEED_KIND: · SEED_BATCH_NO: · SEED_MEMBER: · SEED_AXIS:
   │                                  --apply → registry/seeded.yaml ;  --json --out → .aitask-testmap/onboard/<run>/seed.json (attached to the task)
   ▼  check / explain --sources       UNMAPPED_SOURCE clusters → rules for hot directories · expiring waivers (+90d) · leave unmapped   (waivers phase)
   ▼  enable (skill)                  test_command: ./ait test (previous value → full: true suite runner with fallback_command:) · gate_command_exit_contract += test_command
   │                                  profiles default_gates += tests_pass, testmap_check, testmap_fresh · docs: · notes: · hand-maintained CLAUDE.md paragraph
   ▼  task-workflow Step 8            annotation diff reviewed (none at level 0); testmap_fresh: nothing STALE
   ▼  task-workflow Step 9            ./ait gates run → testmap_check (non-strict) → tests_pass → ./ait test --gate
   │                                  MODE:completion POLICY:full → run --all → ledger rows → last_pass per unit · costs --update · PREDICTION_SCORED:none
   ▼  after the run (full_run phase)  costs --gate-timeout tests_pass → gates.yaml tests_pass.timeout_seconds (ait: commit) · readiness → LEVEL:0 NEXT:adopt
   ▼  every phase                     onboard.yaml row · chore: Onboard testmap — <phase> (t<id>) commit, paths named
```

### Level 1: seeds → verdicts → stamped edges

```
onboard adopt --class static:package --auto          measured origins: no verdict needed → stamp + adopted.yaml {by: auto:measured}
onboard adopt --class coverage --auto                (same; per-unit coverage present)
onboard review [--class static:invocation] [--batch 25] [--out .aitask-testmap/onboard/<run>/review/]
   → REVIEW_BATCHES:<n>|<pairs>  (pairs already in onboard.yaml reviews[] for the same test blob are skipped: REVIEW_MEMO:<n>)
   → the session agent reads review/<n>.md — per pair: the seed's evidence line, the test excerpt around every invocation / import,
     the source's header and exported symbols — and writes review/<n>.answer:
        REVIEW_VERDICT:<test>|<source>|verifies|<file:line of the assertion that checks the source's effect>|<rationale ≤ 200 chars>
        REVIEW_VERDICT:<test>|<source>|drives|-|<rationale>            REVIEW_VERDICT:<test>|<source>|unclear|-|<rationale>
onboard review --answer review/<n>.answer
   → validates: pair is in the batch · test blob unchanged since the batch · assert_line exists in the test file and names the source's stem,
     its command, an output path or a symbol the source exports   → else REVIEW_INVALID:<pair>|<reason> (row untouched)
   → verifies: seeded.yaml row origin[] += agent:review, evidence.agent_review{...}, confidence = noisy-OR (0.90 + 0.90 = 0.99)
   → drives | unclear: row keeps selecting, verdict recorded, excluded from --auto adoption → REVIEW_PARKED
   → onboard.yaml reviews[] memory · REVIEW_APPLIED:<verifies>|<drives>|<unclear>|<invalid> · REVIEW_AGREEMENT:<agree>/<human-reviewed pairs> when any exist
onboard adopt --class static:invocation --auto        every pair with a verifies verdict → stamp + adopted.yaml {by: auto:review}; provenance adopted(static:invocation+agent:review 0.99)
onboard adopt --class static:invocation --accept-min 0.85 [--scope <glob>]   (attended: accept all | review a sample of ten | skip — a person may still adopt without verdicts)
   → rewriter: testmap:covers <src> @<date>/<blob10> at the fixed position → WROTE:<file> · registry/adopted.yaml rows · rows leave seeded.yaml
   → ADOPT_REFUSED:dirty-foreign · ADOPT_SKIP:duplicate|unregistered|no-leader · ADOPT_SUMMARY:1|<edges>|<files>|<skipped>
onboard adopt --area <a> --batch 50        (per row, evidence beside each: file pair, file:line, task ids, coverage run, the verdict and its rationale) → stamp, no provenance row
onboard reject <test> <source> --reason    → onboard.yaml rejections[]; never re-proposed — a person's verb; an agent verdict never lands here
Step 8 testmap_fresh, any later task       → seeds on this task's touched test files: adopt / reject / leave per row (rationale shown) → rides the (t<id>) commit;
                                             autonomous profiles adopt the verifies rows and leave the rest
human re-stamp (verify · stale --confirm-source · annotate) → adopted.yaml row deleted → REVIEWED
```

### The policy flip

```
completion.mode: auto  (written by detect --write; the default)
   every ./ait test --gate → readiness → READINESS:min_scored_full_runs|met|34  READINESS:max_false_negatives|met|0  READINESS:require_opaque_proofs|met
                                        READINESS:approved_by|met|engine (auto)  READINESS:cadence_declared|met  READINESS_DECISION:ADMISSIBLE
   first admissible run → POLICY_FLIPPED:auto->selected|engine:readiness@gate-…  → config.yaml run_gate_admission.approved_by {who: engine:readiness, run, at}
                          → the verifier's caller commits it (`ait:` commit, paths named) → this run and the next ones run the selection
   cadence               → POLICY:auto|full|cadence(every_n 5/5)  → run --all → PREDICTION_SCORED over the 5-task window → last_full_run
   regression            → POLICY_DEMOTED:auto->full|max_false_negatives → full until readiness is ADMISSIBLE again; approved_by cleared

completion.mode: full + /aitask-testmap-onboard --policy selected   (the attended alternative, unchanged)
   → readiness → … READINESS:approved_by|unmet|-  → LEVEL:2 NEXT:scaffold  ADOPTED_UNREVIEWED:618|0.61  SEEDED:412  POLICY:full|would run selected: 14 units
   → AskUserQuestion: record approval {who, statement} → config.yaml completion.mode: selected, run_gate_admission.approved_by → ait: commit
   → the next tests_pass runs the selection; any later unmet criterion demotes it loudly; no cadence unless completion.auto is also declared
```

### Reading the map without running anything

```
ait test --howto ──▶ registry + ledger + config.yaml docs:/notes: + onboard.yaml ──▶ TESTMAP:/RUNNER:/FULL_GATE:/GATE:/VERBS:/AXES:/RESOURCE:/NEW_TEST:/DOCS:/NOTES:
aitask-qa 3a ──▶ ait testmap explain --sources <changed> --format table ──▶ Covered | Covered (adopted) | Covered (seeded) | GAP
ait setup ──▶ report_testmap_state() ──▶ TESTMAP:<state>
onboard status ──▶ phases · ONBOARD_NEXT: · seed queue per origin · verdicts (verifies / parked / unreviewed) · adopted unreviewed by `by` · AUTHOR_UNCORROBORATED · ratios · oldest pending
readiness ──▶ … POLICY:auto|selected|full_in:3 · CADENCE:last_full <run> <n> tasks ago · REVIEW_AGREEMENT:41/44
```
<!-- /section: data_flow -->

<!-- section: adoption_model [dimensions: component_adoption_ledger, component_seeder, component_onboarding_engine_verbs, component_registry_loader, component_annotation_scanner, component_dependency_scanners, assumption_seed_sources_measured, assumption_static_closure_seeds_edges, assumption_cochange_is_corroboration, assumption_seeds_select_never_evidence, assumption_helpers_separable_by_fanin, assumption_annotation_is_comment_only] -->
## The Adoption Model

### The idea

A machine can find evidence that a test exercises a source; only a
*reader of the test body* — a person, or an agent that reads the test and
the source side by side — can turn that evidence into a claim the freshness
machinery will enforce, and a *measurement* (a language rule, a coverage
run) may do so without a reader. The adoption model keeps finding and
claiming apart with three states, makes every transition an explicit,
printed verb, and lets an agent take every transition except the one that
removes a seed.

### The three states

```
                onboard seed --apply                          onboard adopt --class <origin> [--accept-min 0.85] [--scope <glob>]   (a person)
   (none) ─────────────────────────────▶ SEEDED ──────────────────────────────────────────────────────────────▶ ADOPTED (stamp + adopted.yaml row {by})
   attribute --propose ──────────────────▶  │  (selects at d1, no stamp,     onboard adopt --class <measured> --auto   (by: auto:measured) │
                                            │   invisible to stale,          onboard adopt --class <origin> --auto over verifies verdicts (by: auto:review)
                                            │   never --strict)                                                                          │
                                            │ ◀── onboard review --answer: verdict on the row (verifies → adoptable; drives|unclear → PARKED, still selects)
                                            │                                                                                            │ human re-stamp: verify · stale --confirm* · annotate
                                            │ onboard adopt <test> <source> | --area <a> --batch <n> | in-gate row                        ▼
                                            ├────────────────────────────────────────────────────────────────▶ REVIEWED (stamp, no provenance row)
                                            │ onboard reject <test> <source> --reason   (a person; never an agent verdict)
                                            ▼
                                        REJECTED (onboard.yaml; never re-proposed)
   annotate --author <test> <source> (the task's own change surface) ────────────────────────────────────────▶ ADOPTED (stamp + adopted.yaml row {by: author})
```

- **Seeded** rows select — a seeded edge is walked like an annotation edge at
  distance 1 with reason `edge(seeded:<origins>)` — and claim nothing: no
  stamp, no freshness verdict, never counted under `--strict`, never
  satisfying `require_stamp`.
- **Adopted** edges are stamped and therefore evidenced, stale-checked and
  enforced like any annotation, but their `adopted.yaml` row keeps the
  machine origin and the adopter visible: `stale` and `explain` print
  `adopted(<origins> <confidence>)` on the row —
  `adopted(static:invocation+agent:review 0.99)`, `adopted(coverage 0.95)`,
  `adopted(agent:author 0.90)` — `readiness` counts them as
  `ADOPTED_UNREVIEWED:<n>|<ratio>` and `onboard status` splits the count by
  `by` (`human`, `auto:measured`, `auto:review`, `author`).
- **Parked** is not a fourth state but a mark on a seeded row: a `drives` or
  `unclear` verdict leaves the row selecting, keeps it out of `--auto`
  adoption, and lists it as `REVIEW_PARKED:<n>` for a person, who may adopt
  it per row or reject it.
- **Reviewed** edges are stamped edges a named person confirmed for that
  pair; a per-row `adopt`, a `verify`, an `annotate` or a `stale
  --confirm-source` produces one and deletes any provenance row.
- **Rejected** pairs are remembered in `onboard.yaml` and never re-proposed.

Surfaces that show the state: `check` prints `SEEDED:<n>` and `ADOPTED:<n>`
(informational); `stale --all` prints the same two summary lines;
`readiness` prints `ADOPTED_UNREVIEWED` and `SEEDED`; `onboard status` is
the one place the ratios live. Two load rules keep the states disjoint: a
seed with the same `(test, covers)` as any stamped edge is dropped at load
with `SEED_SHADOWED`; an adopted row whose edge no longer carries a stamp is
`ADOPTED_ORPHAN`.

**What may adopt autonomously.** A headless profile, an autonomous branch
of a procedure, or `onboard adopt --auto` in any profile may adopt (a) a
*measured* origin — `static:package`, `coverage` — with no verdict; (b) any
seeded pair carrying an agent `verifies` verdict, whatever its other
origins; (c) the authoring agent's own pairs on its change surface. It may
never adopt a heuristic origin without a verdict, never change a kind, and
never reject a seed. The rule is stated once here and enforced in
`internal/onboard` (`ADOPT_REFUSED:<pair>|not-autonomous` names the missing
verdict).

### The origin table

| origin | rule | measured | confidence |
|---|---|---|---|
| `static:package` *(measured)* | a `_test.go` file's subject is the non-test files of its own package | aitasks_go: deterministic over 85 packages | **1.00** |
| `coverage` *(measured)* | per-unit runtime coverage, opt-in: coverage.py dynamic contexts, `go test -run <unit> -coverprofile`, LCOV with a test column, a project plugin's `{test, covers}` lines (JaCoCo per-test sessions) | opt-in | 0.95 |
| `agent:review` *(reader)* | a `verifies` verdict from the review pass: an agent read the test body beside the source and named the assertion line that checks the source's effect; the engine verified that line exists and names the source, its command, an output path or an exported symbol; evidence `{assert_line, rationale, model, run, test_blob}`; attaches only to an existing seed, never creates one | provisional until `REVIEW_AGREEMENT` is measured against human-reviewed pairs (the first calibration set is aitasks' in-gate adoptions); demoted to 0.60 below `min_agreement` | 0.90 |
| `agent:author` *(reader)* | the agent implementing a task stamps a `(test, source)` pair with both files on its own change surface — the author's claim about the test it just wrote or edited; evidence `{task, run, static: <the closure relation or none>}`; `AUTHOR_UNCORROBORATED` when the closure holds no relation | — | 0.90 |
| `static:invocation` | a literal repo path the test executes or sources (bash: `./.aitask-scripts/x.sh`, `source lib/y.sh`, `$SCRIPT_DIR`- and `$PROJECT_DIR`-relative forms resolved against every source root) | aitasks bash: 398 of 400 tests, avg 3 paths | 0.90 |
| `static:import` | a direct import of a main-root file (Python through the file's own `sys.path` bootstrap; Kotlin imports; same-package facts excluded) | aitasks Python: 320 of 320, avg 1; thinking_app: 139 of 339, avg 3 | 0.85 |
| `observed` | an `attribute --propose` row from a scored full-run miss | — | 0.70 |
| `convention` | `config.yaml conventions:` patterns seeded by `detect` per framework (`test_<x>.sh → aitask_<x>.sh \| lib/<x>.{sh,py}`, `test_<x>.py → <x>.py`, `<Stem>Test.kt → <Stem>.kt`) | aitasks: 52–72 of 400 bash, 62 of 320 Python; thinking_app: 48 Kotlin | 0.60 |
| `plan` | an `aiplans/` file naming both paths, through the `aitask_explain_extract_raw_data.sh` cache when present | — | 0.50 |
| `prose` | a literal path in the unit's header comment or a `# Covers:` line (38 in aitasks) — shown beside the seed as reviewer context, never matched by the annotation scanner | — | 0.30 |
| `cochange` | `(test, source)` co-occurring in ≥ 2 distinct `(t<id>)` task groups over one `git log --name-status -M --format=%H%x00%s` pass, cached by HEAD sha; per-commit grouping where the convention is absent; `SEED_HISTORY:shallow\|<n>` on a shallow clone | aitasks: 439 of 600 task commits touch tests and scripts together (2.8 × 2.6, tight), but 336 groups in 400 commits at 1.14 commits each with nothing inside a group saying which covers which; thinking_app: 127 of 400 at 7.2 main files (noisy) | 0.20 + 0.20 × groups, **cap 0.60** |

**Combination.** Noisy-OR, `1 − Π(1 − cᵢ)`. The default class-acceptance
threshold is 0.85: `static:invocation` or `static:import` alone qualifies
for a *person's* class adoption, `convention` alone (0.60) does not,
`cochange` (≤ 0.60) never does, and `convention + cochange` (0.84 at the
cap) does not either — corroboration raises a static edge's rank and cannot
manufacture one. A verdict composes the same way: `static:invocation +
agent:review` is 0.99, `convention + agent:review` 0.96, `agent:review`
alone 0.90 — and because a verdict only ever attaches to an existing seed,
"alone" means a seed whose other origins are below the threshold, which the
verdict lifts on the strength of a read assertion. Confidence orders the
queue and never hides a row; the threshold governs a person's `--accept-min`
and the *autonomous* rule above is stated in kinds of evidence, not in a
number.

**Where the static facts come from.** The static origins read the same
`internal/deps` facts the selector's test-side closure uses — once, from the
blob-keyed cache. Only the *direct* relation is seeded; the deeper closure
stays the selector's distance-2 walk and is never written as an edge.

### The agent review pass

`onboard review` is how a heuristic seed acquires a reader. It writes batch
files, not prompts: `.aitask-testmap/onboard/<run>/review/<n>.md` holds at
most `agent_review.batch` (25) `REVIEW_ITEM` blocks, each with the pair, the
seed's origins and evidence line, the test excerpt (±40 lines around every
invocation or import of the source, or the whole file under 200 lines), and
the source's header comment and exported symbols (functions, `main`
options, output paths the deps scanner already extracted). Pairs whose
`(test_blob, source)` is already in `onboard.yaml reviews[]` are skipped
(`REVIEW_MEMO:<n>`); a test whose bytes changed is reviewed again.

The reader answers with one line per pair — `REVIEW_VERDICT:<test>|<source>|
verifies|<file:line>|<rationale>` or `…|drives|-|<rationale>` or
`…|unclear|-|<rationale>` — and `onboard review --answer <file>` validates
before it writes: the pair must be in that batch, the test blob must match
the batch, and for `verifies` the named line must exist in the test file
and mention the source's stem, its command form, an output path or an
exported symbol; anything else is `REVIEW_INVALID:<pair>|<reason>` and the
row is untouched. A valid `verifies` adds `agent:review` to the row's
`origin[]` with `evidence.agent_review {verdict, assert_line, rationale ≤
200 chars, model, run: rev-<id>, test_blob, at}`; `drives` and `unclear`
park the row. `model` is the agent string the framework already carries
(`AIT_AGENT_STRING`, `claudecode/<model>` form) or `unknown`.

**Who reads.** The agent running the onboarding skill reads the batches in
its own session — attended or headless, it is the same procedure file
(`review.md`): open `review/<n>.md`, write `review/<n>.answer`, run
`--answer`, next batch. aitasks' queue is ~700 heuristic pairs, 28 batches,
about 1.5 M input tokens at ~2 k per pair — one long session or, when a
person wants it parallel, `onboard review --crew <id>` which registers one
reviewer agent per batch in an agentcrew (`ait crew addwork`, launch mode
`headless`, the `review.md` procedure as `work2do`) and `--collect` reads
the outputs back; the crew path is the explicit place where print-mode
billing is accepted, and no gate or verifier ever takes it.

**Calibration.** Every pair a person adopts per row or rejects is a
labelled example. `onboard review --answer` prints
`REVIEW_AGREEMENT:<agree>/<labelled>` over pairs that carry both a verdict
and a human decision; `readiness` repeats it. Below
`agent_review.min_agreement` (0.85) over at least `calibration_min` (30)
labelled pairs the engine demotes `agent:review` to 0.60 for combination
(`REVIEW_ORIGIN_DEMOTED`), which drops verdict-only pairs under the class
threshold while `--auto` adoption of `verifies` pairs stops until agreement
recovers; a project with no labelled pairs runs at the provisional 0.90 and
`onboard status` says so (`REVIEW_AGREEMENT:none`).

### Helpers before subjects

A closure path is a helper, not a subject, when it is under `helper_roots`
(`tests/lib/**`, `**/testing/**`, `**/src/test/**` for Kotlin,
`**/testdata/**`) or when its fan-in reaches `helper_fanin` (5 % of the
runner's units). A helper gets `test-dep` selection through the closure for
free and, when it globs the tree (`ls tests/*.sh`, `glob.glob`, `rglob`,
`find`, `git ls-files`, `os.walk` — aitasks: `tests/lib/import_isolated.py`,
`board_fixture.py`, `validate_session_hook_fixtures.py`), a proposed
`testmap:reads` line (`SEED_READS:<helper>|<glob>|<evidence>`) written at
level 2 on class acceptance. A hot production module misread as a helper
keeps `test-dep` selection (it over-selects), and every fan-in
reclassification is listed for review.

### Kinds, members and axes as seeds

`onboard classify` wraps `classify --suggest` with three onboarding signals
— a recorded p95 above `broad_threshold_s` from the first full run, a
source-set or directory convention (`androidTest/`, `androidDeviceTest/`,
`*_live.py`, `*_integration.sh`, `parity/`), a resource named in the file
(tmux, `App.run_test`, `install.sh --dir`, real `.git` use, emulator, docker,
network) — plus `fanout:<n>` above `unit_covers_max`, each printed as the
reason on `CLASSIFY:<test>|<kind>|<reason>`, with areas from the closure's
directories intersected with `code_areas.yaml`. `SEED_BATCH_NO` comes from an
aggregate runner's serial list; `SEED_MEMBER` and `SEED_AXIS` from the grid
heuristic. Kind changes are confirmed individually, never per class and
never by an agent, because a wrong kind changes staleness semantics rather
than selection breadth; a headless run prints `CLASSIFY_PENDING:<test>|
<kind>|<reason>` and writes nothing.

### Placement: comment lines only

`onboard adopt` writes through the line-targeted rewriter at a fixed position
per language: bash after the header comment block (after the shebang and the
leading `#` block); Python as `#` lines after the module docstring — the
grammar reads docstring lines, but adoption never writes into one because
that changes `__doc__`; Go after the package clause; Kotlin after the import
block, or inside the member's `testmap:unit` block for a member seed. `git
diff -w --ignore-blank-lines` of an adopted file shows comments only.

Refusals and skips are explicit: `ADOPT_REFUSED:<path>|dirty-foreign` for a
file dirty outside the current task's change surface;
`ADOPT_SKIP:<path>|duplicate` (already annotated — `SEED_SHADOWED` at load);
`ADOPT_SKIP:<path>|unregistered` (no runner lists it);
`ADOPT_SKIP:<path>|no-leader`; `WROTE:<path>` per file and one
`ADOPT_SUMMARY:<level>|<edges>|<files>|<skipped>`. Each written stamp is
`@<date>/<blob10>` at adopt time; a class-adopted edge also gets its
`adopted.yaml` row.

### What seeding cannot do

thinking_app's tests resolve imports for 139 of 339 files because
same-package references need no import and "same package is fully connected"
is too coarse to seed. Fixture-driven tests and screen members seed through
`annotate --from-body` and level 3. Sources reached by no origin stay
`UNMAPPED_SOURCE:` until a rule, a waiver, a coverage import or the
authoring agent maps them — the pre-review procedure's `annotate --author`
is the one origin that reaches a coupling no scanner sees, because the
agent that wrote the test knows what it checks; it is limited to the task's
change surface so it maps couplings as they are created, never the backlog.
`onboard status` reports the state ("selecting on 84 % of tests, claiming
on 18 %, of which 61 % by verdict") rather than hiding it.
<!-- /section: adoption_model -->

<!-- section: onboarding [dimensions: component_onboarding_skill, component_onboarding_engine_verbs, component_seeder, requirements_zero_config_onboarding, requirements_onboarding_existing_tests, requirements_incremental_adoption, assumption_test_tools_detectable, assumption_onboarding_is_a_task, assumption_full_run_expressible_per_repo] -->
## Onboarding: Levels × Phases

### The idea

A repository with an existing test tree is brought onto the map by runs of
`/aitask-testmap-onboard`, attended or headless, with nothing typed by
hand. The skill detects the test tools, generates `aitestmap/`, inventories
every unit, seeds edges from the origin table, proposes waivers for the
remainder, enables the gates, and runs the existing full suite once as the
level-0 task's own completion gate. Level 1 reviews the seeds — the skill's
own agent reads each pair — and adopts the measured origins and the
`verifies` verdicts; a person adopts what remains, or nothing. Later levels
classify broad tests (a person confirms kinds) and scaffold axes. Every
phase is idempotent and resumable from the committed ledger; every level is
an aitask whose writes land under `(t<id>)` commits, are reviewed at Step 8
and are attributed by the change surface.

### Levels and phases

| level | phases in the level's task | what `onboard` writes | what the repository gains | who accepts |
|---|---|---|---|---|
| **0 — runners and universe** | **detect** (`--write`) → **inventory** → **seed** → **waivers** → **enable** → **full_run** (= the task's `tests_pass` at Step 9) | `config.yaml` (`bootstrap_until` today + 90, `require_stamp false`, `concurrency serial`, `completion.mode full`, `conventions:`, `helper_roots:`), `runners.yaml` (builtins + bindings by glob; a `full: true` suite runner from `test_command` with `fallback_command:`), `resources.yaml` from hints, `registry/areas.yaml` via `areas --import-codemap`, `_scanned.yaml`, `registry/seeded.yaml`, rules and expiring waivers in `registry/<area>.yaml` | the universe (`list`), `ait test --all`, per-unit cost and `last_pass` from the first full run, selection through seeds and the test-file closure, scoring of every later full run; nothing stamped | the runner table (keep / edit command / drop, per runner), `UNREGISTERED` files (bind / `exclude:` / not a test), the config table once — headless-safe |
| **1 — edges** | **review** (`onboard review` batches of 25, read and answered by the skill's agent; `--crew` optional) → **adopt** — `--auto` over measured origins and `verifies` verdicts, then per evidence class (`--class static:invocation`, …) or per area (`--scope <glob> --batch 50`) for a person, then incrementally inside `testmap_fresh` | verdicts on `seeded.yaml` rows and `onboard.yaml reviews[]`; stamped `testmap:covers` blocks; `registry/adopted.yaml` rows `{by: auto:measured \| auto:review \| human}`; rows leave `seeded.yaml`; parked rows stay | freshness and the evidence join apply; `stale` reports; `testmap_check` is meaningful; `UNMAPPED_SOURCE` shrinks; `REVIEW_AGREEMENT` starts accumulating | autonomous for measured origins and `verifies` pairs; a person per class (accept all / review a sample of ten / skip) or per row for the rest; headless: the same, minus the person |
| **2 — kinds** | **classify** (per batch of 20, kind changes individually) → `scan --apply` | `testmap:kind integration\|e2e\|device` + `testmap:area` / `testmap:scope` on broad tests, `testmap:reads` on tree-scanning helpers, `testmap:batch no` from serial lists, `needs:` bindings from resource hints, `resources.yaml` entries | scoped rows, the suite budget, `broad_after_unit`, enforced do-not-overlap (aitasks: `repo-git-index` mutex, worktree scope) | per kind, individually, by a person — headless prints `CLASSIFY_PENDING` and writes nothing |
| **3 — product** | **scaffold** (`--axes`, `--runner <builtin> --as <name>`, `--members`) → `annotate --from-body` per member | `axes.yaml` skeleton, `aitestmap/runners/<name>.sh` with `describe`/`run` delegating to the builtin and `list` printing `SCAFFOLD_TODO` until filled (check reports it), `testmap:unit` member blocks | variant selection | the maintainer, with the skill |
| **finish** | a phase of whichever level task the maintainer names last, or `finish --auto` at the end of a headless level-1 task | `require_stamp: true`; `check --strict`; `bootstrap_until` shortened | enforcement | `onboard status` green: no pending phase, `check` clean, and every remaining seed is either under the user-set threshold (default 0) or parked with a verdict — `FINISH:auto\|parked <n>` says how many a person still owns |

The skill's preflight (engine present, ledger state) precedes the level-0
phases and is not itself a ledger phase.

### Two views that agree by construction

`readiness` derives `LEVEL:<0-3>` from what exists — `runners.yaml` → 0, any
stamped `_scanned` edge → 1, any `_scoped` row or `reads` → 2, `axes.yaml` →
3 — and prints `NEXT:<the phase or level that raises it>`. `onboard status`
prints the ledger's `ONBOARD_NEXT:<phase>`, the seed queue per origin, the
adopted-unreviewed count, tests-with-any-edge and sources-with-any-edge
ratios, the oldest pending seed's age and the rejections count. `LEVEL` is a
property of the tree, `ONBOARD_NEXT` a property of the run.

### Invocation and task shape

`/aitask-testmap-onboard [--level <n>] [--policy selected] [--no-task]`.

**Preconditions.** `ait testmap version` (absent → stop with the `ait setup`
hint). An `aitestmap/` with a finished ledger → *refresh mode* (seed limited
to units newer than `adopted.yaml`'s last row, same flow). An unfinished
ledger → re-enter at `ONBOARD_NEXT:`.

**Survey.** Read-only: `onboard detect` and `onboard seed --json --out
.aitask-testmap/onboard/<run>/seed.json`, then the level proposal —
frameworks and counts, edges per evidence class with three samples each,
helpers found and which glob, kind candidates with reasons, `UNLISTED`
files, `RUNNER_SCRIPT_NEEDED` if any, and the config writes.

**The level task.** The skill creates the level's aitask
(`aitask_create.sh --batch --name "testmap onboarding level <n>" --type chore
--labels testing,testmap`), attaches the seed dump with `ait attach`, claims
it with `aitask_pick_own.sh`, writes the id and level into `onboard.yaml`,
and continues into task-workflow honouring the profile (the
`explore_auto_continue` shape). The plan is the phase list. At Step 7 each
phase ends with `chore: Onboard testmap — <phase> (t<id>)` through
`aitask_task_commit.sh` with paths named, so `aitask_change_surface.sh`
attributes the files and a resumed session re-enters at `ONBOARD_NEXT:`.
Step 8 reviews the annotation diff and dispatches `testmap_fresh` (nothing
`STALE` yet — every stamp is today's). Step 9's `tests_pass` runs `./ait test
--gate` under `completion.mode: full`, which for the level-0 task is the
**first full run**: every unit's `last_pass` anchored, `PREDICTION_SCORED:none`
because nothing was predicted yet, `costs --update` folded. The archive
commits registry, annotations and config under one `(t<id>)`.

**After the level-0 run** (the `full_run` phase's procedure): `costs
--gate-timeout tests_pass` → `GATE_TIMEOUT_SUGGESTED:tests_pass|<s>` =
`max(600, 3 × p95)` written into the project's `gates.yaml`; `readiness` →
`LEVEL` / `NEXT`; the next level's task created with `depends:` on this one.

**Variants.** `--no-task` writes without committing and prints the commit
lines, for a repository that forbids tasks on the code branch. The
`--policy selected` re-entry runs `readiness` and only on
`READINESS_DECISION:ADMISSIBLE` writes `completion.mode: selected` and
`run_gate_admission.approved_by {who, at, statement}` in one `ait:` commit;
`NOT_YET` prints the unmet criteria and stops.

**Headless (`remote`) profile.** Level 0 in full (every write is a
registry file or a seed; `completion.mode: auto` and the cadence are
`detect --write`'s defaults). Level 1 in full: `onboard adopt --auto` over
the measured origins, then the review pass — the skill's agent reads every
batch in its own session and answers, `--answer` validates, `onboard adopt
--auto` stamps every `verifies` pair with `by: auto:review` — then `finish
--auto` when `check` is clean, leaving parked rows selecting and listed.
Level 2 prints `CLASSIFY_PENDING` rows and writes no kind; level 3 does not
run. The policy flip needs no re-entry: `auto` flips itself on the first
admissible completion run of any later task. No prompts — the level
proposal, the verdict counts and the parked rows are printed, not asked;
the level-1 task's Step-8 diff is where a person sees the stamps if they
look.

### Detection, per target repository

| repository | `onboard detect` | level 0 runners and resources | full run (`completion.mode: full`) | levels 1–3 |
|---|---|---|---|---|
| **aitasks** | `FRAMEWORK:bash-file\|tests/**/test_*.sh\|400`, `FRAMEWORK:pytest\|tests/test_*.py\|320`, `AGGREGATE_RUNNER:tests/run_all_python_tests.sh`, `SERIAL_LIST:…\|4`, `RESOURCE_HINT:repo-git-index\|~40 tests`, `SUITE_CANDIDATE:test_command\|null`, `UNIVERSE:720 UNLISTED:0` | `bash-file`, `pytest` (`testmap:batch no` on the four carve-out modules, pinned by extending `test_serial_carveout_doc_drift.sh`); `resources.yaml`: `repo-git-index {kind: mutex, scope: worktree}` — the "invocation policy, not a guarantee" comment in `run_all_python_tests.sh` becomes enforced | `ait test --all` (no suite command existed; `tests_pass` gates for the first time); `fallback_command` derived: `for f in tests/test_*.sh; do bash "$f"; done && bash tests/run_all_python_tests.sh` | 1: 398 + 320 static edges, 52–72 corroborated by convention; helpers `tests/lib/` (27; 3 `reads`); the review pass over ~700 pairs in 28 batches, headless-safe — a bash test that runs `aitask_x.sh` and asserts on its stdout token is `verifies`, a test that sources `asserts.sh` is a helper and never a pair, a test that runs `aitask_create.sh` only to build a fixture for `aitask_archive.sh` is `drives` on the first and `verifies` on the second; 2: ~40 tmux / live-TUI / real-install tests → `integration` over codemap areas (a person); 3: `tests/golden/` as a skill × profile × agent axis |
| **thinking_app** | gradle-class 374 classes, `RUNNER_SCRIPT_NEEDED:grid` (screen × matrix), `SUITE_CANDIDATE:test_command\|verify-active`, `RESOURCE_HINT:heavy-run` (exit-75 lock script) | `gradle-class` builtin until the project runner exists; `verify-active {unit: suite, full: true, children: …, fallback_command: tools/verification/screenshot-tests.sh verify-active}`; `heavy-run {kind: admission, exec: heavy-run-lock.sh}` | `verify-active` once (`screen-matrix` and `gradle-class` `subsumed_by: verify-active`) — identical to today's `test_command` | 3: `onboard scaffold --runner gradle-class --as screen-matrix` → `tools/verification/testmap_runner.sh` whose `list` the project fills from the manifests; `axes.yaml`; `testmap:unit` blocks in `ScreenFixtures.kt`; `completion.mode` stays `full` until readiness — the project's own rule |
| **thinking_backend** | bash-file 22 + pytest 18 under `scripts/tests/`, `SUITE_CANDIDATE:verify_build\|scripts/tests/run_script_tests.sh` | `bash-file`, `pytest` with `cwd:`; the skill asks: keep `verify_build` (it also enforces a shellcheck baseline) and add `test_command: ./ait test` — the default | `ait test --all` over the 40 units; `build_verified` still runs the script | 1: static edges into `scripts/server/**` and `db_target.py`; 2: `golden/` fixtures as `reads` |
| **aitasks_go** | go-test: 85 packages, 55 `_test.go` files, `Makefile test`, `parity/run_parity.sh` (tmux + venv) | `go-test` (per package, `-run`, `-json`); `parity` as `suite`, kind e2e, resource `tmux` | `go test ./...` = `ait test --all` | 1 fully automatic and headless-safe with no review pass: `static:package` is measured; `go test -coverprofile` per unit adds `coverage` rows for cross-package edges, also measured |
| **aitasks_mobile** | kmp-sourceset: `commonTest` 36 (dbaccess 2, domain 25, shared 9), `androidHostTest` 1, `androidDeviceTest` 3 | `gradle-class` × modules on `:<module>:jvmTest` / `testDebugUnitTest`; `device` on `connectedDebugAndroidTest` with `emulator {kind: allocator}` | unit kinds only; device kind under `device_policy: filter_by_resource` — the source set is a runner/kind distinction, not an axis | 1: Kotlin import closure (`domain/src/commonMain/**`) |

In every row the user typed nothing; the skill showed the table and asked
for one confirmation per runner, one per kind change and one per config
write; evidence classes were adopted by measurement or by verdict, with a
person asked only about the parked remainder — and in the headless profile
not even that.
<!-- /section: onboarding -->
<!-- section: run_surface [dimensions: component_test_entrypoint, component_test_front_verb, component_agent_brief, component_agent_instructions, requirements_zero_config_entrypoint, requirements_agent_run_surface, requirements_agent_instructions_seeded, assumption_task_resolvable_from_session, assumption_helper_degrades_when_absent, assumption_instructions_block_reaches_agents, assumption_instruction_block_is_read, assumption_change_surface_is_intake] -->
## The Run Surface

### The idea

An agent learns one verb once. `ait test` is correct at every stage of a
repository's adoption: before onboarding it runs the project's
`test_command` and prints the onboarding hint; with a registry it selects,
schedules and runs by itself, resolving the task from the session; in
completion mode it is what the `tests_pass` gate executes; in advisory mode
it can never block. Project specifics are never prose an agent has to find —
they are `ait test --howto`'s computed output.

### Forms

```
ait test                       selected tests for the task you are implementing, each with a reason
ait test <path|id>...          named units: a listed test file, file#member, file#member@variant, a directory of tests,
                               or a SOURCE path — treated as a one-file TASK: change set, so `ait test lib/foo.py` runs what covers it
ait test --all                 the whole registry: every runner's list, full: true suites once, subsumed_by runners skipped
ait test --task <id>           override task resolution
ait test --gate                completion mode — what tests_pass runs; implied by $AIT_GATE_TASK_ID
ait test --advisory --task <id> [--explain]
                               the pre-review form: VERDICT:/REASON:/DETAIL:/LOG: lines, exit 0/1/2/3, every absence a printed skip
ait test --explain             the selection with reasons, groups and estimated cost; runs nothing
ait test --howto [--md]        this project's runners, kinds, resources, full gate, axes, completion policy, LEVEL, docs, notes
ait test --tokens              select --format tokens (thinking_app: `| xargs tools/verification/screenshot-tests.sh preview`)
ait test --dirty               no task: every dirty path as a TASK: row; explicit, printed as INTAKE:dirty, never the default
ait test --fresh-only          exclude stale-marked units (interactive only)
ait test --budget-s <n>        interactive suite budget override
ait test --json                one object instead of lines
```

### Resolution, in order

1. **Registry present?** No `aitestmap/config.yaml` → `TESTMAP_ABSENT:run
   /aitask-testmap-onboard to enable change-aware selection`, then delegate
   to `aitask_run_project_command.sh test_command` (with `--task-id` when a
   task resolved), exiting with its verdict; `--howto` prints the same line
   plus the `test_command`. This is what makes "always `./ait test`" true on
   day one. Advisory mode: `VERDICT:skip REASON:registry_absent`.
2. **Engine present?** Through the shim's strict handshake. Absent:
   interactive → `ENGINE_MISSING:<path>|run 'ait setup' or set
   AIT_TESTMAP_BIN`, exit 3; completion → `completion.engine_absent`:
   `error` (default, exit 3 → verifier `error`) or `fallback_command` (run
   the `full: true` suite runner's `fallback_command:`, print
   `MODE:fallback`, exit per the command); advisory → `VERDICT:skip
   REASON:testmap_absent`.
3. **Mode.** `--gate` or `$AIT_GATE_TASK_ID` → `completion`; `--advisory` →
   `advisory`; else `interactive`. Printed as `MODE:`.
4. **Task.** `--task` > `$AIT_GATE_TASK_ID` > the current worktree's branch
   if it matches `aitask/t<id>_*` (task-workflow's naming) > the locks this
   user holds on this host (`aitask_lock.sh --list-mine`, a listing verb
   added to the lock script): exactly one → that task; several →
   `AMBIGUOUS_TASK:<ids>`, exit 64 unless `--task`; none → `TASK:none`.
5. **Intake.** Named paths → units by registry lookup, or a source path → a
   synthetic `TASK:<path>` change set; `--all` → every runner's `list`; a
   resolved task → `aitask_change_surface.sh list <id>` piped to `--changes
   -` (`UNKNOWN:` refuses — advisory: `VERDICT:skip REASON:unknown_paths`
   naming them; `aitasks/`, `aiplans/`, `.aitask-data/` excluded); `--dirty`
   → `git status --porcelain` paths as `TASK:` rows; nothing → `NO_TASK:`
   with the three ways out, exit 64 (advisory: 3).
6. **Policy (completion only).** `completion.mode`; if `selected`, run
   `readiness` first: every criterion met → the task selection with
   `deferred: run`; any unmet → `POLICY_DEMOTED:selected->full|<criterion>`
   and run `full`. If `auto`: `readiness` not `ADMISSIBLE` → full with
   `POLICY:auto|full|not_admissible`; admissible and the cadence due (`n`
   selected completions since the last full run ≥ `full_every_n`, the
   selection estimate ≥ `full_when_selection_over × full p95`, or `last_full_run`
   older than `full_after_days`) → full with the reason printed; otherwise
   the selection with `full_in:<k>`; the first admissible run also prints
   `POLICY_FLIPPED` and writes `approved_by`. `full` → `run --all` with
   `subsumed_by` honoured. `on_empty_selection: skip` → exit 2 → the
   opted-in `tests_pass` records `skip`, never `pass` — except that a
   cadence full run ignores `on_empty_selection` and runs.
7. **Run.** The engine `test` composite: `select --include-stale
   [--budget-s] [--format …] --run <run-id>` → `schedule` → `run`; prints
   `SELECTED:<n>|<groups>|<est_s>|<seeded_n>|<adopted_n>`, one
   `UNMAPPED_SOURCE:<path>` per changed source no unit reaches, the ranked
   rows with their reasons (a seeded edge reads
   `edge(seeded:static:invocation,cochange)`, an adopted one `edge(annotation)
   adopted(static:invocation 0.90)`), `DEFERRED:` in interactive mode only,
   the waves, results per id, `RESULT:`. The front prefixes the run id
   (`test-`, `gate-`, `full-`; see *Cost ledger*).
8. **New-test and new-source notices.** `UNANNOTATED_TEST:<path>` +
   `HINT:./ait testmap annotate --suggest <path>` for a listed test in the
   change surface with no `testmap:` block, no seed and no adopted row;
   `UNMAPPED_SOURCE:<path>` for a changed source with no edge, seed, rule or
   waiver. Informational in interactive mode; the pre-review procedure
   offers the fix; in completion mode `testmap_check` owns enforcement.

### Output and exit contract

```
MODE:interactive|completion|advisory|fallback   TASK:<id>|none   INTAKE:change-surface|dirty|all|named
POLICY:full|selected|auto|<sub-state…>   SELECTED:<units>|<groups>|<est_s>|<seeded>|<adopted>   RUN:<run-id>   [FULL_IN:<k>]
ESCALATE:… DEFERRED:… UNMAPPED_SOURCE:… UNANNOTATED_TEST:… HINT:…       (engine line classes pass through)
RESULT:pass|fail|skip|error|refused|<n passed>|<n failed>|<n skipped>
advisory only:  VERDICT:pass|fail|skip   REASON:all_passed|command_failed|testmap_absent|registry_absent|unknown_paths|no_selection|admission_refused
                DETAIL:<one line>   LOG:.aitask-gates/<task>/affected_<run-id>.log
```

| exit | meaning | as `test_command` under the opt-in | advisory mode |
|---|---|---|---|
| 0 | every selected unit passed | pass | `VERDICT:pass` |
| 1 | a unit failed, or a mechanism failure | fail | `VERDICT:fail REASON:command_failed` |
| 2 | nothing ran: empty selection, or `TESTMAP_ABSENT` + no `test_command` | skip | `VERDICT:skip REASON:no_selection` (+ `UNMAPPED_SOURCE:` lines) |
| 3 | framework error: engine missing / mismatched, `CONTRACT_MISMATCH`, `UNKNOWN:` intake | **error** (`command_errored`) | `VERDICT:skip` with the reason (`testmap_absent`, `registry_absent`, `unknown_paths`); exit 3 only when the log cannot be written |
| 75 | admission refused after the in-engine deferral to the run deadline | **error** (`command_refused`) | `VERDICT:skip REASON:admission_refused` |
| 64 | usage: `NO_TASK`, `AMBIGUOUS_TASK`, bad flag | fail | 3 |

Advisory mode speaks `aitask_run_project_command.sh`'s `0/1/2/3` domain and
the `set -e` capture form `build-verification.md` already teaches, so the
pre-review procedure cannot disagree with the Step-9 path about an exit
code. It writes the engine's full output to the log, appends nothing to any
gate ledger, and is the one deliberate exception to "a missing engine is an
error": an *advisory* run must never block a task the way a declared gate
legitimately does; the skip is printed, never silent.

### The two environment variables

`run_command_gate` exports `AIT_GATE_TASK_ID=<task-id>` and
`AIT_GATE_RUN_ID=<run-id>` around the command; `aitask_run_project_command.sh
--task-id <id>` exports the first. That is how `./ait test` knows it is a
completion run and for which task in all three call sites (the `tests_pass`
verifier, the legacy Step-9 helper, `aitask-qa`) with no argument in
`test_command`; the run id names the gate run in
`.aitask-testmap/runs/<run-id>/` so a ledger row and a gate log share an
identifier.

### `ait test --howto` (engine verb `brief`)

For thinking_app after level 3, on this host class:

```
TESTMAP:onboarded|since 2026-09-16|LEVEL:3|POLICY:auto→selected|full_in 3|seeds pending 412 (parked 96)|adopted unreviewed 618 (review 402, author 31)
RUNNER:gradle-class|unit|374 classes|screenshot-tests.sh unit-tests --tests <class>|heavy-run
RUNNER:screen-matrix|unit (variant, axis matrix)|49 members, 297 variants over 10 matrices|screenshot-tests.sh unit-tests --tests <class>.<method>|heavy-run
RUNNER:verify-active|suite (full)|1|screenshot-tests.sh verify-active|heavy-run|subsumes screen-matrix,gradle-class
FULL_GATE:verify-active|p95 1180s|= project_config test_command|tests_pass timeout 3540s
GATE:testmap_fresh (procedure, before commit) -> testmap_check -> tests_pass = ./ait test --gate (auto: selected now, full every 5 / >=60 % / 7 d)
VERBS:./ait test | ./ait test <path>... | ./ait test --all | ./ait test --howto
AXES:matrix|facets locale,direction,geometry|10 values
RESOURCE:heavy-run|admission (tools/verification/heavy-run-lock.sh)|refusal = exit 75 -> deferred to run deadline
NEW_TEST:./ait testmap annotate --suggest <path>
DOCS:aidocs/testing/rendering-verification.md
DOCS:aidocs/testing/change-aware-verification.md
NOTES:A shared component change (ui/components/*) must run the full gate; preview renders without a verdict.
NOTES:Never run ./gradlew test directly - the harness owns the heavy-run slot and the run id.
```

Everything above `DOCS:` is computed from the registry, the ledger and
`config.yaml`; `DOCS:` and `NOTES:` are what the `enable` phase asked the
maintainer for — the judgement calls a registry cannot hold, kept to ten
lines and reached through one verb. `--md` renders the same as markdown;
`ONBOARD_NEXT:` appears while a ledger is unfinished; < 100 ms warm.

### The generic instructions section

Added to `seed/aitasks_agent_instructions.seed.md`, therefore inserted
between the `>>>aitasks` / `<<<aitasks` markers of every supported agent's
instructions file (`CLAUDE.md`, `AGENTS.md`, `.codex/instructions.md`, the
OpenCode mirror) on the next `ait setup` or `ait upgrade` by
`assemble_aitasks_instructions()` / `insert_aitasks_instructions()`, with no
per-project edit:

```markdown
## Running Tests

Run tests only through the framework entrypoint — never call pytest, go test, gradle
or a test script directly.

    ./ait test              # tests selected for the task you are implementing, a reason per line
    ./ait test <path>...    # a named test file or unit; a SOURCE path runs what covers it
    ./ait test --all        # the whole suite — what completion runs while the project's policy is `full`
    ./ait test --howto      # this project's runners, kinds, resources, full gate, policy and notes

`UNANNOTATED_TEST:<path>` for a test you added → `./ait testmap annotate --suggest <path>`.
`UNMAPPED_SOURCE:<path>` for a source no test reaches → map it before the gate (`/aitask-testmap`).
`TESTMAP_ABSENT` means the project is not onboarded → `/aitask-testmap-onboard`.
Exit codes: 0 pass · 1 fail · 2 nothing ran · 3 framework error (run `ait setup`) · 75 host refused (already waited; retry later).
```

Fourteen lines, no agent named, no project specifics (those are `--howto`'s
computed output, so the current-state-only documentation rule holds and no
constant condenses `runners.yaml`), correct before onboarding (the verb runs
`test_command`). `tests/test_agent_instructions.sh` gains one case asserting
the heading in all four rendered surfaces through a real `install.sh --dir`.
This repository's own hand-maintained `CLAUDE.md` (sentinel present, no
markers) is edited by its level-0 onboarding task to point at `./ait test`
and keep the runner-specific notes (`run_all_python_tests.sh` lanes, the
`PIPESTATUS` caveat) as background.
<!-- /section: run_surface -->

<!-- section: workflow_seam [dimensions: component_workflow_seam, component_workflow_integration, component_gates, component_completion_policy, component_qa_integration, requirements_workflow_seam, requirements_workflow_seam_is_data, requirements_gate_enforcement, assumption_gate_exit_contract_reused] -->
## The Workflow Seam and the One Completion Gate

### The idea

The change-aware run is reached from the existing workflows without a new
workflow and without a new gate. The seam is data — project config,
profiles, gate declarations, the completion policy, two environment
variables — plus one paragraph for the implementation loop and one procedure
for the pre-review run. Every seam degrades to a printed skip where the
engine or the registry is absent.

### The concrete edits

| where | change | kind |
|---|---|---|
| `task-workflow/SKILL.md.j2` Step 7, after *Follow the approved plan* | one paragraph: "**Test loop.** Run `./ait test` after each meaningful change — it selects from this task's change surface and prints a reason per unit. `UNANNOTATED_TEST:<path>` → `./ait testmap annotate --suggest <path>`; `UNMAPPED_SOURCE:<path>` → map it (`/aitask-testmap`). Do not invoke the project's test tool directly; `./ait test <path>` runs one unit." | prose, every profile; goldens regenerated |
| `task-workflow/SKILL.md.j2` Step 7, once before Step 8 | the **pre-review affected run**: the Affected Tests Procedure (`affected-tests.md`) under `{% if profile.affected_tests is not defined or profile.affected_tests != 'off' %}` | procedure |
| `task-workflow/affected-tests.md` | `./ait test --advisory --task <id> [--explain]` with the `set -e` capture form; the branch table below; the autonomous branch of `no_selection` / `UNANNOTATED_TEST` runs `ait testmap annotate --author`; the verdict line recorded in the plan's Final Implementation Notes, never in the gate ledger | procedure file |
| `task-workflow/profiles.md`, `remote.yaml` | profile keys `affected_tests: run\|show\|off` (default `run`; `default.yaml` and `fast.yaml` omit it; `remote.yaml` sets `run`) and `unmapped_source_autonomous: author\|propose` (default `author`; a project that wants no agent-stamped edges sets `propose`) | data + two doc rows |
| Step 8 | the `testmap_fresh` procedure-gate dispatch before the change summary; inside the gate, one new step: for each `COMMITTED:`/`TASK:` test file with rows in `seeded.yaml`, show the seeds with evidence and offer adopt / reject / leave per row — accepted rows ride the same `(t<id>)` commit | one step |
| Step 9 verify block (`./ait gates run`) | none — the orchestrator runs `testmap_check` → `tests_pass` (= `./ait test --gate`) | none |
| Step 9 no-gates branch (`build-verification.md`, `verify_build`) | none in prose; a project reaches the test lane by declaring `tests_pass`, which onboarding writes into `default_gates` | data |
| `build-verification.md` | one branch: verdict `error` with reason `command_refused` / `command_errored` → host refused resources or the framework could not run; do not fix code, do not record a pass, report and re-run later | prose |
| `lib/gate_verifier_lib.sh` `run_project_command_key()` | opted-in keys: 75 → `error`/3/`command_refused`, 3 → `error`/3/`command_errored`; exports `AIT_GATE_TASK_ID`, `AIT_GATE_RUN_ID` around the command; docblock table updated — the single canonical statement | code; `tests/test_gate_verifiers.sh` extended |
| `aitask_run_project_command.sh` | `--task-id` also exports `AIT_GATE_TASK_ID`; inherits the new rows | code |
| `gates_reference.yaml` → `gates.yaml` sync | + `testmap_fresh` (procedure, verifier `aitask-gate-testmap-fresh`), + `testmap_check` (`unlocks: [tests_pass]`, `max_retries: 0`, `timeout_seconds: 120`); `tests_pass` unchanged in the reference, `timeout_seconds` tuned per project from the ledger | data |
| project profiles | `default_gates` += `tests_pass`, `testmap_check`, `testmap_fresh` (the onboarding `enable` phase, confirmed; `rendered_gates` when present) | data |
| `aitask_gate_testmap_check.sh` | the machine verifier; rows `SEEDED:<n>`, `ADOPTED:<n>` (informational), `UNMAPPED_SOURCE:<path>` (reported during bootstrap, fails under `--strict` past `bootstrap_until`) | code |
| `aitask-qa/test-discovery.md` 3a–3c | with `aitestmap/`: `ait testmap explain --sources <changed files> --format table` → Source / Test / Reason / Status with `Covered`, `Covered (adopted)`, `Covered (seeded)`, `GAP` (= `UNMAPPED_SOURCE`); else the legacy convention scan | prose |
| `aitask-qa/test-execution.md` 4a–4d | 4a: the configured `./ait test` through `aitask_run_project_command.sh test_command --task-id <id>`; 4b: named units via `ait test <path>`; 4c: `REFUSED (host resources)` row, treated as `SKIP` in the health score; 4d: coverage from registry edges (seeded counted as `Covered (seeded)`) | prose |
| `aitask-pickrem`, `aitask-pickweb`, `aitask-resume` | inherit through task-workflow and `build-verification.md`; pickweb (no `ait setup`) sees `VERDICT:skip REASON:testmap_absent` at Step 7 and the `engine_absent` policy at completion | none |
| `aitask_setup.sh` | `report_testmap_state()` after `install_engine_binary()`: `TESTMAP:engine-missing\|absent\|bootstrapping\|<next>\|onboarded`, hint `run /aitask-testmap-onboard` on `absent`; setup never onboards | code; `test_install_engine_binary.sh` asserts each state |
| `ait` dispatcher | `test)` → `aitask_test.sh`; help line | code |
| permission touchpoints (5) | `aitask_test.sh` (its `--advisory` form is the only helper); `tests/test_touchpoint_count_contract.sh` re-pinned | config |
| `aidocs/framework/aitasks_extension_points.md` | "Adding a test-framework detector" (closed list, evidence line, fixture repo, `UNLISTED` behaviour) and "Adding a seed origin" (confidence row, evidence field, fixture) | doc |
| `aitask_skill_verify.sh` + goldens | task-workflow, aitask-qa, the new onboarding stub, every profile × agent | test |

### The pre-review Affected Tests Procedure

```bash
if at_out="$(./ait test --advisory --task <task_id> {{ '--explain' if profile.affected_tests == 'show' else '' }})"; then
  at_rc=0
else
  at_rc=$?
fi
at_verdict="$(printf '%s\n' "$at_out" | sed -n 's/^VERDICT://p')"
at_reason="$(printf '%s\n' "$at_out"  | sed -n 's/^REASON://p')"
at_detail="$(printf '%s\n' "$at_out"  | sed -n 's/^DETAIL://p')"
at_log="$(printf '%s\n' "$at_out"     | sed -n 's/^LOG://p')"
at_selected="$(printf '%s\n' "$at_out" | sed -n 's/^SELECTED://p')"
```

| branch | action |
|---|---|
| `at_rc` 3 or empty verdict | infrastructure — diagnose the entrypoint / engine; never "fix the code"; never a pass |
| `pass` | display `SELECTED:` and continue |
| `fail` | read `at_log`; caused by this task → fix and re-run; unrelated → log under **Affected tests** in the plan's Final Implementation Notes and proceed (the `build-verification.md` loop, verbatim) |
| `skip` · `no_selection` | display the `UNMAPPED_SOURCE:` paths; **offer** (`AskUserQuestion`, non-skippable in attended profiles): *Annotate as author* (default — `ait testmap annotate --author <test> <source>` for each unmapped source and the test on this change surface that checks it; stamped, `adopted.yaml {origin agent:author, by author, task}`, rides the `(t<id>)` commit) · *Annotate by hand* (`/aitask-testmap` → `annotate` / a rule) · *Propose for review* (`attribute --propose`, lands in `seeded.yaml` with origin `observed`) · *Continue unmapped*. Autonomous profiles take *Annotate as author* for every unmapped source that a test on the change surface checks (the agent names the pair; `ANNOTATE_REFUSED:outside-change-surface` for anything else) and *Continue unmapped* for the rest, printing `AUTHOR_UNCORROBORATED` pairs; `unmapped_source_autonomous: propose` restores the baseline branch |
| `UNANNOTATED_TEST` on any verdict | a test this task added or edited with no `testmap:` block, seed or adopted row: the same offer, with `annotate --author <test> <sources>` naming the sources on the change surface the test checks; autonomous profiles annotate |
| `skip` · `unknown_paths` | the scope prompt `aitask-gate-docs-updated` already uses: include / subset / exclude; autonomous profiles exclude and log |
| `skip` · `admission_refused` | print `at_detail` (the host refused the heavy slot until the deadline); continue — nothing failed |
| `skip` · `testmap_absent` / `registry_absent` | one line; continue — not onboarded, or this host has no engine |

Why a procedure exists when the loop is a paragraph and the gate is
`tests_pass`: the advisory run is the one task-scoped selection guaranteed
to happen in every profile, so it guarantees a prediction record exists for
the completion run to score (`PREDICTION_SCORED` /
`PREDICTION_FALSE_NEGATIVES` into `costs/predictions.yaml`); `readiness`
counts those rows toward `min_scored_full_runs`. A repository whose tasks
never run the advisory form may never accumulate scored predictions and
could never flip its policy. The verdict line (`- **Affected tests:** pass
(14 units, est 41 s) — log …`) goes into the plan's Final Implementation
Notes and never into the gate ledger: no double record, no `record_gates`
guard needed.

### Gates

```yaml
  testmap_fresh:
    type: machine
    kind: procedure
    description: "Coverage annotations on this task's changed sources reviewed, re-stamped, and touched test files' seeds adopted or rejected"
    blocks_dependents: false
    verifier: aitask-gate-testmap-fresh
  testmap_check:
    type: machine
    description: "Test map consistent: rotted paths fail; structural rot and unmapped sources fail under --strict past bootstrap"
    blocks_dependents: false
    verifier: aitask-gate-testmap-check
    max_retries: 0
    timeout_seconds: 120
    unlocks: [tests_pass]
  # tests_pass: unchanged in the reference (blocks_dependents: true, max_retries: 1, timeout_seconds: 600).
  # In an onboarded project test_command is `./ait test`, gate_command_exit_contract lists test_command,
  # and the project's gates.yaml carries timeout_seconds from `costs --gate-timeout`.
```

There is no separate selection gate. Everything such a gate would own has a
home: its verifier logic is `ait test --gate`; `blocks_dependents` and
`max_retries: 1` are `tests_pass`'s own; its timeout is the per-project
`tests_pass.timeout_seconds` from the ledger; its exit mapping (0/1/2/75/64
→ 0/1/2/3/3) is the shared lib's new rows; `testmap_check` unlocks
`tests_pass`; `--include-stale` is applied by the composite; deferred rows
run under `completion.deferred: run`. An `unlocks:` target absent from a
task's active set is ignored, so `testmap_check` declared alone is linear as
before, and a project whose completion invariant is a full suite keeps
`tests_pass` exactly as today with `completion.mode: full`.
`run_gate_admission` and `readiness` gate the **policy flip** rather than a
second gate's declaration; the engine never enables a gate and never writes
a profile.

### Completion policy

Two flips exist. The human one (`completion.mode: full` plus
`/aitask-testmap-onboard --policy selected` after `ADMISSIBLE`,
`approved_by {who, at, statement}` recorded) is unchanged. The engine's one
(`completion.mode: auto`, the default `detect --write` writes) flips on the
first admissible completion run, records `approved_by {who:
engine:readiness, run, at}`, and is bounded by the cadence in
`completion.auto`: every `full_every_n`-th completion since the last full
run, any selection whose estimate reaches `full_when_selection_over` of the
full-suite p95, and any completion `full_after_days` after the last full run
is a full run that scores the window of predictions behind it. The demotion
is automatic and loud in both; the policy can only fail toward running
more; a cadence full run is never skipped by `on_empty_selection` or a
demotion. thinking_app's rule — full `verify-active` as the completion gate
until admissible — is preserved exactly by `auto` until `ADMISSIBLE` and by
`full` forever; the project chooses in `config.yaml`, and `--howto` prints
which. The completion flow itself is drawn under *Data Flow*.

### Verification of the seam

`tests/test_ait_test_entrypoint.sh` drives a fixture repository with
`AIT_TESTMAP_BIN` pointing at a fake engine replaying scripted exits, in all
three modes and every `REASON:`, plus the `auto` policy's three cadence
reasons, the flip's `approved_by` write and the demotion;
`tests/test_gate_verifiers.sh` covers 75 and the env export; engine tests
for `onboard review`: batch content per language, every `REVIEW_INVALID`
reason (pair not in batch, blob changed, assert line absent, assert line
naming nothing of the source), the memo skip, agreement and demotion at the
threshold, `--auto` refusing a heuristic without a verdict, `annotate
--author` refusing outside the change surface, and window scoring
attributing a miss to the right task; `tests/test_agent_instructions.sh` gains the
Running-Tests case; `tests/test_testmap_onboard_ledger.sh` (resume from each
phase, idempotent re-run, `--no-task`, one task per level with `depends:`);
engine tests per detector, per seed origin on fixture repos with synthetic
`(t<id>)` histories, the fan-in reclassification, golden files for block
placement per language, every `ADOPT_*` refusal branch; the task-workflow and
onboarding goldens; `tests/test_touchpoint_count_contract.sh`;
`tests/test_install_engine_binary.sh` for each `TESTMAP:` state.
<!-- /section: workflow_seam -->
<!-- section: components [dimensions: component_*] -->
## Components

Components are grouped by layer. *Core* components are the engine, map,
selection and scheduling machinery; *adoption layer* components are the
onboarding, run-surface and workflow additions. Every component names its
package or file, its verbs or keys, and how it is tested.

**Engine and packaging**

<!-- section: component_go_engine [dimensions: component_go_engine] -->
### Go engine and CLI *(core)*

`engine/cmd/ait-testmap` with packages
`internal/{registry,axes,annot,deps,changesurface,selectr,sched,runner,cost,feedback,stale,gitx,platform}`
plus `internal/seed`, `internal/onboard` and `internal/brief`. Go 1.26 with a
pinned toolchain, `CGO_ENABLED=0`, `-trimpath -buildvcs=false -ldflags "-s -w
-X version/commit/contract"`; dependencies `gopkg.in/yaml.v3`,
`bmatcuk/doublestar/v4`, `golang.org/x/sync` only; stdlib `flag` verb table,
`syscall.Flock`, `os/exec` git; line-protocol stdout, `--json`, per-verb exit
contracts. It never writes `aitasks/`, `aiplans/`, `.aitask-data/`, a gate
ledger, `project_config.yaml`, `gates.yaml`, profiles or `CLAUDE.md`; never
invokes `aitask_*.sh`; never needs its own install root. Fixture repositories
in `t.TempDir()` carry synthetic `(t<id>)` histories for the co-change
origin, one fixture per detect shape (bash-only, pytest, go, gradle,
gradle-per-source-set) and one per opaque-scanner branch.
<!-- /section: component_go_engine -->

<!-- section: component_engine_binary [dimensions: component_engine_binary] -->
### Engine binary identity and budget *(core)*

Version, commit and contract are embedded; `version --json` prints
`ENGINE:<path>`; a newer contract in any registry file is refused with
`CONTRACT_MISMATCH` (`seeded.yaml`, `adopted.yaml` and `onboard.yaml` carry
their own `contract:` field and are refused the same way; the contract stays
1). Pools are capped at 8. The verb table is `test`, `select`, `schedule`,
`run`, `scan`, `check`, `stale`, `annotate`, `verify`, `explain`, `axes`,
`areas`, `classify`, `costs` (+ `--gate-timeout`), `score`, `attribute`,
`readiness`, `brief`, `onboard {detect, inventory, seed, review, classify,
adopt, reject, scaffold, status, finish}`, `annotate --author`, `version`.
Budgets pinned by `go test -bench` fixtures with a 2× regression rule:
`select` < 200 ms warm on the aitasks shape and < 250 ms with axis expansion
on the thinking_app shape, `scan` / `check` / `stale --task` < 300 ms,
`stale --all` < 2 s, cold `select` < 1.5 s, `brief` < 100 ms warm, `onboard
seed` static + convention < 2 s and co-change < 5 s over 600 commits,
`onboard status` < 200 ms, `onboard review` batch writing < 1 s per 100
pairs and `--answer` validation < 200 ms per batch (the reading between
them is the agent's time, not the engine's), the cadence check inside `ait
test --gate` < 50 ms.
`detect` is excluded from the latency table: it runs once per onboarding,
executes `git log` and every runner's `list`, and is on no gate path.
<!-- /section: component_engine_binary -->

<!-- section: component_binary_distribution [dimensions: component_binary_distribution] -->
### Binary distribution *(core)*

`engine/build.sh` is the single build and matrix command. The release
`engine` job (`actions/setup-go` from `engine/go.mod`, `go vet`, `go test`,
`build.sh all`) produces `ait-testmap_<V>_{linux,darwin}_{amd64,arm64}` and
`ait-testmap_<V>_SHA256SUMS.txt`, attached by both `action-gh-release` steps
with `release needs: [plan, engine]`; the VERSION-matches-tag guard is
unchanged. `engine-check.yml` runs gofmt, vet, test and the 2× bench rule on
push / PR for `engine/**`. `lib/platform_detect.sh` maps `uname`. The shim's
strict handshake: `AIT_TESTMAP_BIN` (with an override notice) > `AIT_ENGINE=dev`
slot at `$AITASKS_HOME/engine/dev/` requiring `<V>-dev+<sha>` >
`$AITASKS_HOME/engine/v<V>/` requiring `== VERSION` > `ENGINE_MISSING:<path>`
exit 3 with the repair hint. Tests: `test_testmap_shim.sh` (with an
`AITASKS_HOME` host), `test_platform_detect.sh`, `test_aitasks_home.sh`.
Docs: `aidocs/framework/go_engine.md`, a `CLAUDE.md` Engine block, a
`packaging_strategy.md` paragraph naming `~/.aitasks/engine/`.
`release-packaging.yml` and nfpm `arch: all` are untouched.
<!-- /section: component_binary_distribution -->

<!-- section: component_engine_packaging [dimensions: component_engine_packaging] -->
### Engine install, upgrade and state report *(core + adoption layer)*

`install_engine_binary()` in `aitask_setup.sh`, reached by `ait setup` and by
`ait upgrade` through `install.sh`'s `--source-only` path: source order
`--local-engine` > exact-version release asset > `--engine-from-source` >
`ENGINE_MISSING` warning; `sha256sum -c` / `shasum -a 256` with a `.sha256`
sidecar short-circuit; atomic install to `$AITASKS_HOME/engine/v<V>/`;
`version --json` must echo `<V>`; `.dev`-marked binaries are never
overwritten without `--force-engine`; `--no-testmap` / `AIT_TESTMAP_FETCH=0`
print `TESTMAP_BINARY:skipped`; `HOME_LEGACY:` hint when legacy tenants
exist; `.aitask-testmap/` gitignored by setup; `aitask_engine.sh` with `ait
engine build|test|cross|prune|home [--migrate]`. After it,
`report_testmap_state()` prints `TESTMAP:engine-missing` (binary absent),
`TESTMAP:absent` with `run /aitask-testmap-onboard` (no `aitestmap/`),
`TESTMAP:bootstrapping|<next phase>` (an unfinished ledger) or
`TESTMAP:onboarded`; setup reports and never onboards. The re-inserted
instructions block carries the Running Tests section. `aitask_test.sh` is a
framework script shipped in the tarball like every `aitask_*.sh` — nothing
to install. `tests/test_install_engine_binary.sh`, through a real
`install.sh --dir --local-engine`, asserts the `$AITASKS_HOME` path and each
`TESTMAP:` state.
<!-- /section: component_engine_packaging -->

<!-- section: component_user_root [dimensions: component_user_root] -->
### Per-user root *(core)*

`.aitask-scripts/lib/aitasks_home.sh` exports
`AITASKS_HOME=${AITASKS_HOME:-$HOME/.aitasks}`, `aitasks_engine_dir
<version|dev>` and `$AITASKS_HOME/.home.lock`; sourced by the shim,
`install_engine_binary`, `aitask_engine.sh`, the verifiers and
`aitask_test.sh`; never falls back to `~/.aitask/`. `ait setup` creates
`$AITASKS_HOME/engine/` (0755) and prints `AITASKS_HOME:<path>` beside the
venv line so both roots are visible; `ait engine prune` walks only
`$AITASKS_HOME/engine/v*/`. `test_aitasks_home.sh` pins the default, the env
override, and that no framework script of this feature names `~/.aitask/`.
<!-- /section: component_user_root -->

<!-- section: component_framework_home [dimensions: component_framework_home] -->
### Framework home report and migration verb *(core)*

`ait engine home` prints `HOME_ROOT:<path>`, `HOME_LEGACY:<path>|<tenants>`,
`HOME_SYMLINK:none|<target>` and `HOME_NEXT:<what --migrate would do>`. `ait
engine home --migrate` runs under `flock $AITASKS_HOME/.home.lock`; refuses
and reports `no-legacy-root`, `already-migrated`, `foreign-symlink:<target>`,
`cross-device` or `unknown-entry:<name>`; moves each present entry of the
known set `{venv, pypy_venv, python, bin, uv, dev_tier, update_check,
engine}` with a same-device `mv`, `rmdir`s the emptied legacy root and leaves
`ln -s $AITASKS_HOME ~/.aitask` behind; prints `HOME_MIGRATED:<n>` or
`HOME_SKIPPED:<reason>`. In this release `ait setup` only prints the
`HOME_LEGACY:` hint; flipping the default (reserving `--no-home-migration` /
`AIT_HOME_MIGRATE=0`) is a named follow-up admitted when
`tests/test_aitasks_home.sh`, through a real `install.sh --dir`, covers fresh
install, migration with a working venv and PyPy venv afterwards, idempotent
re-run, a hostile pre-existing symlink, cross-device refusal and the
`AITASKS_HOME` override, and the 18 doc files naming `~/.aitask` are updated.
<!-- /section: component_framework_home -->

**The map: registry, annotations, scanners, axes**

<!-- section: component_registry_loader [dimensions: component_registry_loader] -->
### Registry loader and writer *(core + adoption layer)*

`internal/registry` merges `aitestmap/registry/*.yaml` plus `axes.yaml` into
eight tables: the six core tables (edges, scopes, areas, rules, waivers,
axes) with unit ids `<path>[#<member>][@<variant>]`, each member's
`variants:` list from `_scanned.yaml`, `owns:` routing by glob for edges and
rules and by area name for hand-declared scopes, observed axis sources merged
widen-only, deterministic sorted writes only on change, and the check rules
(`STALE_PATH`, `UNSTAMPED` past bootstrap under `require_stamp`,
`DEAD_SCOPE`, `DEAD_AXIS_SOURCE`, `UNKNOWN_VARIANT`, `UNCOVERED_VALUE`,
`UNANNOTATED_MEMBER`, `DEAD_MEMBER`, `UNREGISTERED`, `UNMAPPED_ARTIFACT`,
`KIND_MISMATCH|CONVERT_TO_SUITE`, `CONTRACT_MISMATCH`); plus **seeds** from
`registry/seeded.yaml` (rows `{test[#member], covers, origin[], confidence,
evidence{}, proposed_at}`) and **adopted** from `registry/adopted.yaml` (rows
`{test, source, origin[], confidence, adopted_at, task}`). Load rules: a seed
whose `(test, covers)` also exists as any stamped edge is dropped with
`SEED_SHADOWED` (reported by `check`); an adopted row whose edge no longer
carries a stamp is `ADOPTED_ORPHAN`. A seed row may carry `verdict:` and
`evidence.agent_review{}`; an adopted row carries `by: human | auto:measured
| auto:review | author`. Write routing: `onboard seed` → `seeded.yaml`;
`onboard review --answer` → `seeded.yaml` (origin and verdict added on the
row, never a removal) + `onboard.yaml reviews[]`; `onboard adopt` →
`seeded.yaml` (row removed) + `adopted.yaml` (class and `--auto` adoption)
+ the test file through the rewriter; `annotate --author` → the test file +
`adopted.yaml {by: author}`; `onboard reject` → `seeded.yaml` (row removed)
+ `onboard.yaml` (rejection recorded); `attribute --propose` →
`seeded.yaml`; a human re-stamp (`verify`, `annotate`, `stale
--confirm-source`, per-row `adopt`) → `adopted.yaml` (row removed). `config.yaml` gains `completion:`, `conventions:`, `helper_roots:`,
`helper_fanin:`, `exclude:` (never listed, never `UNREGISTERED`), `docs:`,
`notes:` (≤ 10 lines) and `broad_threshold_s`. Golden tests pin the two new
table merges, the shadow rule and the id grammar.
<!-- /section: component_registry_loader -->

<!-- section: component_annotation_scanner [dimensions: component_annotation_scanner] -->
### Annotation scanner and rewriter *(core; adopt as a caller)*

`internal/annot`, grammar v3: `testmap:unit <Member>` opens a member block
that owns every following `testmap:` line until the next `testmap:unit` or
end of file (a file-level block precedes the first unit); `testmap:kind`,
`testmap:covers <path> @<date>/<blob10>`, `testmap:area`, `testmap:scope`,
`testmap:trigger`, `testmap:reads <glob>` (helper files only), `testmap:axis
<axis>.<facet>=<value>`, `testmap:reviewed`, `runner` / `needs` / `batch` —
per comment leader, with Python module docstrings read; unknown keys are
refused with a line number. The line-targeted rewriter edits stamps by
`(file, line, current text)` and refuses on `REWRITE_CONFLICT`; `annotate
--from-body` seeds covers for a member from the Kotlin scanner's symbol
resolution of the block's own lines; both generated files are produced from
every runner's `list` output. `onboard adopt` is a new caller of the
rewriter, not a new writer: it inserts `testmap:covers` lines at the fixed
per-language position (bash after the shebang and leading `#` block; Python
as `#` lines after the module docstring, never inside it; Go after the
package clause; Kotlin after the import block, or inside the member's
`testmap:unit` block for a member seed), each stamped `@<date>/<blob10>` at
adopt time, one file rewritten per adopted item. Existing `# Covers:` prose
headers are shown beside seeds as reviewer context and read by the `prose`
origin at 0.30, never matched by the annotation scanner and never rewritten.
<!-- /section: component_annotation_scanner -->

<!-- section: component_dependency_scanners [dimensions: component_dependency_scanners] -->
### Dependency scanners *(core; facts shared with the seeder)*

`internal/deps`: built-in bash, python, go (`go list -deps -json` cached by
`go.sum` digest), kotlin with the opaque contract over main and test roots,
Gradle module graph; executable plugins under `aitestmap/scanners/` speaking
one JSON line per file `{file, deps, opaque?, reads?}`; the opt-in
`android-res` symbol scanner; forward deps cached per source blob under
`${XDG_CACHE_HOME:-~/.cache}/aitasks/testmap/deps/<blob-sha1>.json` and
inverted in memory. The bash scanner's literal-invocation facts (a test that
runs `./.aitask-scripts/x.sh` or sources `lib/y.sh`, including `$SCRIPT_DIR`-
and `$PROJECT_DIR`-relative forms resolved against every source root), the
python and kotlin scanners' direct imports of a main-root file (Python through
the file's own `sys.path` bootstrap) and the go scanner's package membership
are exposed to `internal/seed` as the `static:invocation`, `static:import`
and `static:package` origins — same scan, same cache, read once. The deeper
closure stays the selector's distance-2 walk and is never seeded as an edge.
<!-- /section: component_dependency_scanners -->

<!-- section: component_variant_axes [dimensions: component_variant_axes] -->
### Variant axes *(core)*

`internal/axes`, read by registry, selector, runner and cost.
`aitestmap/axes.yaml` declares axes `{name, facets[], values{value: {facet:
v}}, sources{facet: {v: [globs]}}}`; a runner's `describe` names the axis its
variants live on and a `token_format`; `list` emits `<unit>@<value>` ids. The
selector joins changed paths to facet values through `sources` and selects
the variants carrying them (reason `axis(<axis>.<facet>=<v>) <- <path>`) plus
plain units carrying `testmap:axis` for that value, or every variant of a
unit reached by an edge, dep, rule or test-dep; `--axis <axis>.<facet>=<v>`
forces a facet. Costs, `last_pass`, evidence and score are per variant;
`check` enforces `DEAD_AXIS_SOURCE`, `UNKNOWN_VARIANT` and `UNCOVERED_VALUE`;
observed sources widen only. The engine holds no project axis — the first
consumer is thinking_app's `matrix` axis with facets locale / direction /
geometry over its 10 recording matrices. Level-3 `onboard scaffold --axes`
writes only the skeleton the maintainer fills; the grid heuristic proposes, a
person declares.
<!-- /section: component_variant_axes -->

<!-- section: component_axes [dimensions: component_axes] -->
### Axis resolver verbs *(core)*

`ait testmap axes --list` prints every declared axis with its facets, values
and the variant count each value has in `list`; `--check` runs the axis
rules (`DEAD_AXIS_SOURCE`, `UNKNOWN_VARIANT`, `UNCOVERED_VALUE`); `--explain
<path>` prints `AXIS:<axis>.<facet>|<value or ->|<why>` per facet for one file
— which glob matched, or that no source is declared — so a maintainer sees
where a file lands before anything is trusted. `-` means no axis hit, which
selects every variant.
<!-- /section: component_axes -->

<!-- section: component_cell_enumeration [dimensions: component_cell_enumeration] -->
### Enumeration and reconciliation *(core)*

There is no generated cell table: the runner's `list` verb is the
enumeration surface, and `scan --apply` persists its output as the
`variants:` list on each member row of `_scanned.yaml` (49 rows with at most
ten values for thinking_app), so `select` never executes a runner and only
`scan` and `check` call `list`. Two-way reconciliation is `UNCOVERED_VALUE:<axis>|<value>`
(a declared value no runner lists) and `UNMAPPED_ARTIFACT:<path>|<runner>` (a
file matching a runner's declared `artifact_glob:` that no listed id's
artifact column claims), both failing `check --strict` after bootstrap.
`onboard detect`'s `UNIVERSE:` is the same count taken before runners exist;
`onboard inventory` is the first consumer of `UNREGISTERED:` rows as a to-do
list.
<!-- /section: component_cell_enumeration -->

<!-- section: component_suite_registry [dimensions: component_suite_registry] -->
### Scoped-row registry and areas *(core; classify signals added)*

`registry/areas.yaml` plus `areas:` blocks in hand files, seedable via `areas
--import-codemap`; `_scoped.yaml` rows `{test, kind, runner, areas, globs,
triggers, reads_from, needs, reviewed_at, line}`; `owns:` by area name for
hand-declared rows; the distance-1 join, kind ranking, the suite budget
(`suite_budget_s` default 600) with `DEFERRED` lines and budget-exempt
triggers; check rules including `DEAD_SCOPE` and
`KIND_MISMATCH|CONVERT_TO_SUITE`; `ait testmap areas`; missing-trigger /
area-too-narrow in `attribute`; a rule may `select:` a scoped test or a
member by name. `classify --suggest` gains the three onboarding signals (a
recorded p95 above `broad_threshold_s`, a source-set or directory convention,
a resource declaration or use in the file) plus `fanout:<n>` above
`unit_covers_max`, each printed as the reason on the
`CLASSIFY:<test>|<kind>|<reason>` line the skill confirms per batch of 20
with kind changes confirmed individually; `onboard classify --apply` writes
the confirmed rows' source lines at level 2.
<!-- /section: component_suite_registry -->

<!-- section: component_broad_test_scopes [dimensions: component_broad_test_scopes] -->
### Broad-test scheduling and staleness policy *(core)*

Kind `integration|e2e|device` selects the scoped association form;
`broad_after_unit: true` waves run scoped rows only after a green unit wave;
`device_policy: filter_by_resource` by default; scoped rows are exempt from
per-edit digest staleness, with `STALE_AREA` as the evidence-based drift
signal and `REVIEW_DUE` as an opt-in cadence; `attribute` widens areas by
evidence; `covers` on a scoped row is allowed for digest-stamped fixture
pins; a suite row marked `full: true` with a `children:` post-processor
anchors registered ids on every run; variant-bearing units are unit kind,
never area-scoped, and ride the unit wave with admission-holding invocations
ordered last. `completion.deferred: run` means the suite budget applies to
the interactive loop only.
<!-- /section: component_broad_test_scopes -->

**Freshness and evidence**

<!-- section: component_freshness [dimensions: component_freshness] -->
### Freshness *(core; one stamp writer and one gate step added)*

Per-edge `@<date>/<blob10>` stamps, scoped to the member block, written only
by `verify`, `annotate` (including `--author`), `stale --confirm*` and
`onboard adopt` (a person's or `--auto`); variants carry no stamp; `last_pass` per id; `bootstrap_until`, `require_stamp`,
`flake_threshold`. The `testmap_fresh` procedure gate is dispatched by the
existing procedure-gate block before the change summary so rewrites ride the
`(t<id>)` commit; it is not a git hook and not a code-agent hook. It gains
one step: offering to adopt or reject the seeds of the test files this task
touched — the stamp then rides the same commit as the test edit, which is
the moment the reviewer has the file open and the claim is cheapest to
check. An adopted stamp is a stamp like any other; the gate handles it
identically, with the `adopted(...)` display as context.
<!-- /section: component_freshness -->

<!-- section: component_staleness_tool [dimensions: component_staleness_tool] -->
### Staleness tool *(core; seeded edges excluded, adopted rows displayed)*

`internal/stale`: `stale --task --changes - | --all` with the
`SURFACE` / `EDGES` / `STALE_PATH` / `STALE` / `EVIDENCED` / `UNSTAMPED` /
`STALE_AREA` / `REVIEW_DUE` / `UNKNOWN` / `DISPLAY` / `DECISION` line classes
and `%25` / `%7C` encoding; a `STALE` row on a unit with variants carries a
trailing `|<unevidenced variants>` field; `--all` adds `CHECK_STRUCTURAL:<n>`;
content states exit 0, `--strict` exits 1 on `STALE_PATH`; compares blob
digests of the working tree only, consults the per-variant evidence join,
adds rename hints and culprit task ids from `git log --name-status -M` when
history is reachable; mutates stamps via `--confirm`, `--confirm-source`,
`--confirm-evidenced`, `--retarget` through the rewriter with a re-scan of
touched files. Seeded edges are excluded from every class; `stale --all`
adds `SEEDED:<n>` and `ADOPTED:<n>` summary lines beside `CHECK_STRUCTURAL`;
a `STALE` or `EVIDENCED` row whose edge has an `adopted.yaml` row carries
`adopted(<origins> <confidence>)` in its `DISPLAY` line so the procedure gate
knows it is confirming a class-accepted claim, not a per-pair reviewed one.
<!-- /section: component_staleness_tool -->

<!-- section: component_evidence_join [dimensions: component_evidence_join] -->
### Evidence join *(core)*

`internal/stale` + `internal/gitx`, reading `internal/cost`: for every edge
whose stamped blob differs from the current blob, collect `last_pass` shas
per reached variant from the local ledger and committed costs (any host
class), drop candidates from invocations with a cause or ids over the flake
threshold, keep shas that are ancestors of `HEAD`, and run one `git ls-tree`
per distinct sha; an edge is `EVIDENCED` when every reached variant has a sha
whose source object id equals the current blob, otherwise `STALE` with the
unevidenced variants listed. It never rewrites — `stale --confirm-evidenced`
is the explicit re-stamp and the only bulk confirmation an autonomous profile
may run. Seeded edges are not joined (no stamp to heal); adopted edges are
joined like any stamped edge; the level-0 task's first full run is what
first populates the anchors it reads.
<!-- /section: component_evidence_join -->

**Selection, scheduling, running, cost**

<!-- section: component_selector [dimensions: component_selector] -->
### Selector *(core; seeded edges, `explain --sources`, summary lines)*

`internal/selectr` + `internal/changesurface`: line-protocol intake refusing
`UNKNOWN:`, the graded walk with select / implies / escalate rules, variant
expansion and axis join, test-dep at distance 1, `ESCALATE` on opaque files,
scoped join, kind-then-cost ranking, invocation groups, stale marks from
digest compare plus the per-variant evidence join, `--include-stale`, the
suite budget with `DEFERRED` lines and budget-exempt triggers and reads, cut
knobs including `--axis`, `--format lines|json|tokens`, the prediction
record, `explain`. A seeded edge is walked exactly like an annotation edge at
distance 1 with reason `edge(seeded:<origins>)` and never contributes a stale
mark; an adopted edge is an annotation edge whose reason carries
`adopted(<origins> <confidence>)`. `explain --sources <path>... --format
table` prints the reverse view (every unit reaching each source with its
reason and provenance, or `UNMAPPED_SOURCE`) as the table `aitask-qa`'s test
discovery consumes. The `test` composite prints one
`SELECTED:<n>|<groups>|<est_s>|<seeded_n>|<adopted_n>` line and
`UNMAPPED_SOURCE:<path>` lines before the ranked rows so the front can build
its verdict without parsing the rows; `ait test <source path>` reaches it as
a one-row `TASK:` change set.
<!-- /section: component_selector -->

<!-- section: component_scheduler_resources [dimensions: component_scheduler_resources] -->
### Scheduler and resources *(core)*

`internal/sched`: resource kinds `mutex` / `semaphore` / `admission` /
`allocator`, scopes `host` / `worktree` / `run`, `acquired_by` planning;
`flock(2)` slot files taken in canonical order; admission exec with 75
deferral and backoff to the run deadline; allocator exec with signal-safe
release; goroutines under `errgroup`; batching (variants of one runner and
resource set batch into one invocation per `group_by` group, so
thinking_app's whole selection is one Gradle run holding one heavy-run
slot); `broad_after_unit` waves with variant-bearing units in the unit wave
and, within a wave, invocations holding an admission resource ordered last;
`concurrency: serial|parallel` defaulting to serial at bootstrap with
`--serial` / `--parallel` overrides; the schedule report and its check half.
`detect`'s `RESOURCE_HINT` rows become `resources.yaml` entries the
scheduler already understands (aitasks: `repo-git-index` mutex, worktree
scope); a refusal at the deadline is exit 75 (advisory:
`skip:admission_refused`).
<!-- /section: component_scheduler_resources -->

<!-- section: component_runner_contract [dimensions: component_runner_contract] -->
### Runner contract and repository *(core; two keys and a scaffold added)*

`internal/runner`: `describe` (`unit file|class|method|variant|suite`,
`axis:`, `batch`, `needs`, `group_by:`, `token_format:`, `filter_scope:`,
`full:`, `children:`, `artifact_glob:`), `list` as TSV `<id> <kind>
<lowering> [<artifact>]` with member and variant ids, `run --manifest` with
ids, lowerings and groups, `results.jsonl` per id with optional child rows
under a suite parent, `runner.json` with per-group overhead rows,
first-match bindings and per-test override, the `builtin:` scheme with
`command:` / `cwd:` overrides and shadow-by-name, batching by `(runner, group,
resource set, batch flag)`, per-unit timeouts, `units_expected` /
`units_reported` reconciliation with zero-reported-some-expected and
no-registered-id as mechanism failures, exit contract `0/1/2/75` plus `64`.
Repository keys added: `subsumed_by: <suite>` on a runner whose units are
the child rows of a `full: true` suite runner, so `run --all` executes the
suite once and never the subsumed runner beside it (thinking_app:
`screen-matrix` and `gradle-class` subsumed by `verify-active`); and
`fallback_command:` on a suite runner — the pre-onboarding `test_command` or
a detect-derived equivalent — which `ait test --gate` runs when the engine is
absent and `completion.engine_absent` is `fallback_command`. `onboard
scaffold --runner <builtin> --as <name>` emits `aitestmap/runners/<name>.sh`
whose `describe` and `run` exec the builtin and whose `list` prints
`SCAFFOLD_TODO` until the project fills it, which `check` reports.
<!-- /section: component_runner_contract -->

<!-- section: component_reference_runners [dimensions: component_reference_runners] -->
### Reference runners *(core; detect seeds the repository)*

Built into the binary as `ait-testmap runner <name>`: `bash-file`; `pytest`
(junitxml; `testmap:batch no` honoured, the serial carve-out pinned by
extending `tests/test_serial_carveout_doc_drift.sh`); `go-test` (per-file
`-run` regex, `-json`); `gradle-class` (`--tests <lowering>` batch, one
invocation per `group_by` group, JUnit XML inverted to ids through the list
table, zero-match trap as a mechanism failure); `suite` (any command as one
unit, optional child rows from a `children:` post-processor); `device`
(allocator handle); `command:` / `cwd:` overrides; shadow-by-name with
`explain` showing which won; `engine-test` over `engine/`. thinking_app's
`tools/verification/testmap_runner.sh` (`screen-matrix`: `list` from the
two membership manifests plus `matrix_classes` with an artifact column, `run`
through `screenshot-tests.sh unit-tests --tests`) and `verify-active` as a
`full: true` suite runner whose child rows come from
`lib/screenshot-diff-set.sh`. `onboard detect` seeds the repository:
`bash-file` for `tests/**/test_*.sh`; `pytest` for `test_*.py` / `*_test.py`
(an aggregate runner script's serial carve-out list becomes `testmap:batch
no` candidates); `go-test` per package from `go list`; `gradle-class` for
`src/test/**/*.kt|java`; a `kmp-sourceset` detector mapping `commonTest` /
`androidHostTest` to gradle-class unit runners (`:<module>:jvmTest`,
`testDebugUnitTest`) and `androidDeviceTest` to the device runner
(`connectedDebugAndroidTest`, `needs: [emulator]`); and a `full: true` suite
runner named `full` wrapping `project_config.yaml test_command` (or
`verify_build` only when the user names it as the suite) whose `children:`
post-processor is a builtin inverting pytest junitxml, bash-file names from
the per-file exit and `go test -json` events to registered ids, and whose
`fallback_command:` is the previous `test_command` — so the existing full
gate anchors evidence from day one without a project script. The
`bash-file` builtin gains `list --invocations`, printing the literal repo
paths a test references, for the seeder's `static:invocation` origin.
<!-- /section: component_reference_runners -->

<!-- section: component_cost_ledger [dimensions: component_cost_ledger] -->
### Cost ledger *(core; run-id prefixes and `--gate-timeout` added)*

`internal/cost`: Welford per `(id, host class)` where id may be a variant,
with P² p95 and last; the per-repo ledger `.aitask-testmap/ledger.jsonl` with
`run_id` / `id` / `status` / `duration_ms` / `head_sha` per result and
`{run_id, group, overhead_ms, units_reported}` per invocation; `costs
--update` folds both into `aitestmap/costs/<hostclass>.yaml` and truncates;
`last_pass {sha, at, run_id}` per id and a flake rate against
`flake_threshold`; the estimate for a selection is the sum over invocation
groups of `overhead.p95` plus the p95 of each selected id, reported per kind;
`costs/predictions.yaml` holds the last 200 scored full runs. **Run-id
prefixes**, stated here once: `test-` for interactive and advisory runs,
`gate-` for completion runs, `full-` for `--all`; all three write ordinary
rows and feed cost and evidence exactly like any run, and the ledger says
which surface produced a row. The `SELECTED:` estimate is the same per-group
sum the budget uses. `costs --gate-timeout tests_pass` prints
`GATE_TIMEOUT_SUGGESTED:<gate>|<seconds>` = `max(600, 3 × p95 of the newest
full run on this host class)`, which the onboarding `full_run` phase writes
into the project's `gates.yaml` after the first measured full run.
<!-- /section: component_cost_ledger -->

<!-- section: component_feedback_tools [dimensions: component_feedback_tools] -->
### Feedback tools *(core; `--propose` and the readiness lines added)*

`internal/feedback`: `score` runs automatically after `run --all` and after a
`full: true` suite run, printing `PREDICTION_SCORED` /
`PREDICTION_FALSE_NEGATIVES:<n>` / `PREDICTION_MISSED:<id>` and appending to
`costs/predictions.yaml`; `attribute` records missing-edge / test-wrong /
source-wrong, missing-axis-source (widen only), missing-trigger /
area-too-narrow. An `attribute` decision may be `propose` (default in
autonomous profiles), which writes the row to `seeded.yaml` with origin
`observed` (0.70) and the run id as evidence instead of to `observed.yaml`,
so autonomous runs grow the review queue and never the accepted map.
`readiness` prints `LEVEL:<0-3>`, `NEXT:<the phase or level that raises
it>`, `ADOPTED_UNREVIEWED:<n>|<ratio of covers edges>` and `SEEDED:<n>` as
informational criteria, `POLICY:<completion.mode>|<what ait test --gate
would run now>[|full_in:<k>]`, `CADENCE:<last full run>|<selected
completions since>|<days since>`, `REVIEW_AGREEMENT:<agree>/<labelled>` or
`none`, and `REVIEW_PARKED:<n>`; under `auto` the `approved_by` criterion
reads `met|engine` once the flip is recorded and a new criterion
`cadence_declared` requires `completion.auto` to hold all three rules. After
a cadence full run, `score` scores every `costs/predictions.yaml` row since
the last full run, attributing each miss to the earliest task in the window
whose change surface reaches the failing unit through an edge, a dep or a
scoped row (culprit task ids from `git log --name-status -M` when history is
reachable), printing `PREDICTION_MISSED:<id>|<task>` per miss; `readiness`
still enables nothing and `ait test --gate` is the only writer of the flip.
<!-- /section: component_feedback_tools -->

**Adoption and onboarding**

<!-- section: component_adoption_ledger [dimensions: component_adoption_ledger, component_registry_loader, component_seeder, component_onboarding_engine_verbs] -->
### Adoption ledger: seeded → adopted → reviewed *(adoption layer)*

The three-file state of a machine-proposed edge and the rules that move it —
`registry/seeded.yaml` (select-only, no stamp, invisible to `stale`, never
`--strict`, `SEEDED:<n>` on `check` / `stale --all` / `readiness`),
`registry/adopted.yaml` (provenance of a stamped edge accepted by evidence
class; `adopted(<origins> <confidence>)` on `stale` and `explain` rows;
`ADOPTED_UNREVIEWED:<n>|<ratio>` on `readiness`, `ADOPTED:<n>` on `check`) and
`onboard.yaml`'s `rejections[]`. Transitions: `onboard seed` / `attribute
--propose` → seeded; `onboard adopt --class <origin> [--accept-min 0.85]
[--scope <glob>]` → adopted (stamp + provenance row); `onboard adopt <test>
<source>` / `--area <a> --batch <n>` / the `testmap_fresh` in-gate step →
reviewed (stamp, no provenance row); a human re-stamp → reviewed; `onboard
reject` → rejected; `onboard review --answer` → a verdict on the seeded row
(`verifies` → adoptable by `--auto`; `drives` / `unclear` → parked, still
selecting); `onboard adopt --class <origin> --auto` → adopted `{by:
auto:measured | auto:review}` for measured origins and `verifies` pairs;
`annotate --author` → adopted `{by: author}`. Load rules: `SEED_SHADOWED`,
`ADOPTED_ORPHAN`. Autonomous profiles may seed, may review, may adopt
measured origins, `verifies` pairs and their own author pairs, and may never
reject a seed or change a kind. The full model is drawn under *The Adoption
Model*; its costs are recorded under
`tradeoff_two_edge_states_during_adoption`, `tradeoff_seed_precision` and
`tradeoff_agent_judgement_unmeasured`.
<!-- /section: component_adoption_ledger -->

<!-- section: component_seeder [dimensions: component_seeder] -->
### Seeder *(adoption layer)*

`internal/seed`, verb `ait testmap onboard seed [--from
static,convention,cochange,plan,prose,coverage] [--min-cochange 2]
(the two `agent:*` origins are never seeded here: `agent:review` is written
onto an existing row by `onboard review --answer` and `agent:author` by
`annotate --author`)
[--accept-min 0.85] [--coverage-report <f>|--per-unit] [--apply] [--json
--out <f>]`, produces `registry/seeded.yaml` rows `{test[#member], covers,
origin[], confidence, evidence{static: file:line, convention: pair, cochange:
[task ids], plan: path, prose: line, coverage: run id}, proposed_at}`.
`static:{package, invocation, import}` read `internal/deps` facts for the
test file only (direct, never the closure; same-package facts excluded).
`convention` applies `config.yaml conventions:` patterns seeded by `detect`
per runner (bash-file: `test_<x>.sh → aitask_<x>.sh | lib/<x>.sh |
lib/<x>.py`; pytest: `test_<x>.py → <x>.py` under the main roots; go-test:
`<x>_test.go → <x>.go` same dir; gradle-class: `<Stem>[Test|*Test].kt →
<Stem>.kt` under main). `cochange` parses one `git log --name-status -M
--format=%H%x00%s` pass over commits whose subject matches `(t<id>)` and
counts `(test, source)` pairs across distinct tasks (per-commit grouping
fallback), cached by HEAD sha, `SEED_HISTORY:shallow|<n>`. `plan` reads the
`aitask_explain_extract_raw_data.sh` cache; `prose` reads header comments and
`# Covers:` lines; `coverage` imports coverage.py contexts JSON, `go
-coverprofile` per unit, LCOV with a test-id column, or a project plugin's
`{test, covers}` lines. The confidence table is the one under *The Adoption
Model*; combination is noisy-OR, ordering only. Helpers are separated first
by `helper_roots` and `helper_fanin` with `SEED_HELPER:` and
`SEED_READS:<helper>|<glob>|<evidence>` lines; `SEED_KIND:`, `SEED_BATCH_NO:`,
`SEED_MEMBER:`, `SEED_AXIS:` come from `onboard classify`'s signals. A
rejected pair is never re-proposed; a pair already stamped is dropped with
`SEED_SHADOWED`; `--apply` writes deterministically sorted, otherwise prints
`SEED:<test>|<source>|<origins>|<confidence>` lines; `--json --out` writes the
dump the skill attaches to the level task. Budget: static + convention < 2 s
and co-change < 5 s over 600 commits on the aitasks shape. Fixtures: a
synthetic repo per origin with a `(t<id>)` history.
<!-- /section: component_seeder -->

<!-- section: component_onboarding_engine_verbs [dimensions: component_onboarding_engine_verbs] -->
### Onboarding verbs *(adoption layer)*

`internal/onboard` behind `onboard detect [--write] | inventory | seed |
review | classify [--apply] | adopt | reject | scaffold | status | finish`
and the `aitestmap/onboard.yaml` phase ledger `{contract, task, level,
phases{detect, inventory, seed, waivers, enable, full_run, review, adopt,
classify, scaffold, finish: {status, at, by, counts}}, rejections[],
reviews[]}`.

- `detect` prints `FRAMEWORK:<kind>|<glob>|<count>|<builtin>|<evidence>` for a
  closed detector list (`bash-file`, `pytest`, `go-test`, `gradle-class`,
  `kmp-sourceset`, `suite-from-config`), `UNIVERSE:<n>`, `UNLISTED:<n>`
  (test-looking files no detector claims), `AGGREGATE_RUNNER:<path>` and
  `SERIAL_LIST:<path>|<n>` for a runner script with a carve-out list,
  `RESOURCE_HINT:<name>|<n tests>|<evidence>` (real-repo git use, flock, a
  lock script), `SUITE_CANDIDATE:test_command|verify_build|<cmd>`,
  `RUNNER_SCRIPT_NEEDED:<reason>` from the grid heuristic. `--write` emits
  the level-0 files (`config.yaml` with `bootstrap_until` today + 90,
  `require_stamp false`, `concurrency serial`, `completion.mode full`,
  `conventions:`, `helper_roots:`; `runners.yaml` with builtins, bindings and
  the `full: true` suite runner with `fallback_command:`; `resources.yaml`
  from hints; `areas --import-codemap`) and on an existing table prints
  `DETECT_DIFF:` and writes nothing without `--force`.
- `inventory` runs `scan` + every `list` + `check` and prints `UNREGISTERED:`
  as the to-do list.
- `seed` is the seeder.
- `review [--class <origin>] [--batch 25] [--out <dir>] [--crew <id>]`
  writes the batch files and prints `REVIEW_BATCHES:<n>|<pairs>` and
  `REVIEW_MEMO:<skipped>`; `review --answer <file>` validates and applies
  verdict lines, printing `REVIEW_APPLIED:<verifies>|<drives>|<unclear>|<invalid>`,
  one `REVIEW_INVALID:<pair>|<reason>` per refusal, `REVIEW_AGREEMENT` when
  labelled pairs exist and `REVIEW_ORIGIN_DEMOTED` when agreement falls
  under `min_agreement`; `review --collect <crew-id>` reads a crew's
  outputs as answer files. The verb is *component_agent_review*.
- `classify` wraps `classify --suggest` with the three onboarding signals and
  on `--apply` writes the level-2 kind / area / scope / reads / batch lines
  and `needs:` bindings for confirmed rows; without a confirmed row it
  prints `CLASSIFY_PENDING` and writes nothing — there is no `--auto`.
- `adopt`: `--class <origin> [--accept-min 0.85] [--scope <glob>]
  [--dry-run]` for a person's bulk adoption with an `adopted.yaml` row per
  edge; `--class <origin> --auto` for the autonomous form, which adopts
  every pair of a measured origin, or every pair of the class carrying a
  `verifies` verdict, and refuses anything else with
  `ADOPT_REFUSED:<pair>|not-autonomous`; `<test> [<source>]` / `--area <a>
  --batch <n>` / `--files-from -` for reviewed per-row adoption; writes
  stamped `testmap:covers` lines through the rewriter at the fixed
  per-language position; refuses `ADOPT_REFUSED:<path>|dirty-foreign`; skips
  duplicate / unregistered / no-leader; prints `WROTE:` per file and
  `ADOPT_SUMMARY:<level>|<edges>|<files>|<skipped>|<by>`.
- `reject <test> <source> --reason` — a person's verb; the engine refuses it
  when `AIT_PROFILE_HEADLESS=1` is exported by the skill's headless
  invocation (`REJECT_REFUSED:headless`), so no autonomous path can remove
  a seed.
- `scaffold --axes | --runner <builtin> --as <name> | --members` writes the
  level-3 `axes.yaml` skeleton, `aitestmap/runners/<name>.sh` with a
  `SCAFFOLD_TODO` list, and `testmap:unit` member blocks.
- `status` prints phase rows, `ONBOARD_NEXT:<phase>`, seed queue counts per
  origin and per verdict (`verifies` / parked / unreviewed),
  `ADOPTED_UNREVIEWED` split by `by`, `AUTHOR_UNCORROBORATED:<n>`,
  `REVIEW_AGREEMENT`, tests-with-any-edge and sources-with-any-edge ratios,
  the oldest pending seed age and the rejections count.
- `finish` requires status green (no pending phase, `check` clean, every
  remaining seed either under the user-set threshold or parked with a
  verdict), flips `require_stamp` and `--strict`, records the phase;
  `--auto` is the same test with `FINISH:auto|parked <n>` printed, so a
  headless level-1 task can close enforcement.

The engine reads `onboard.yaml`'s `task:` and `level:` and writes phase
rows; it never creates a task, edits a profile, `project_config.yaml`,
`gates.yaml` or `CLAUDE.md`, or commits — those are the skill's through the
framework's own scripts. Go tests on fixture repositories: one per detector
and per detect shape, the fan-in reclassification, golden files for block
placement per language, every refusal branch, resume from each phase.
<!-- /section: component_onboarding_engine_verbs -->

<!-- section: component_onboarding_skill [dimensions: component_onboarding_skill] -->
### Onboarding skill `aitask-testmap-onboard` *(adoption layer)*

`.claude/skills/aitask-testmap-onboard/` as a profile-aware stub +
`SKILL.md.j2` (resolver key `onboard`) with one procedure file per phase
(`detect.md`, `inventory.md`, `seed.md`, `waivers.md`, `enable.md`,
`full-run.md`, `review.md`, `adopt.md`, `classify.md`, `scaffold.md`,
`finish.md`); Claude Code first, Codex and OpenCode ports as follow-up
tasks; rendered goldens under `tests/golden/skills/aitask-testmap-onboard/`.
`review.md` is the reader's procedure: run `onboard review`, open each batch
file, decide per pair with the test excerpt and the source's symbols in
view, write the answer file in the verdict grammar naming the assertion
line for every `verifies`, run `--answer`, read `REVIEW_INVALID` lines and
correct or park them, next batch; it is the same file in every profile and
names no agent. Flow: preconditions →
read-only survey and level proposal → one aitask per level created with the
seed dump attached and claimed → task-workflow (phases at Step 7 with
per-phase commits, the diff at Step 8, the first full run at Step 9) → the
timeout from the ledger, `readiness`, the next level's task with `depends:`.
Confirmations: per runner (keep / edit command / drop); per evidence class
for what `--auto` did not adopt (accept all / review a sample of ten /
skip — the parked rows with their rationales); per kind change
individually;
`UNLISTED` files (bind / not a test / later); the config table once
(`test_command` → `./ait test` with the previous value moved to a `full:
true` suite runner; `verify_build` left alone unless the user names it as
the suite; `gate_command_exit_contract` += `test_command`; profiles
`default_gates` += `tests_pass`, `testmap_check`, `testmap_fresh`;
`bootstrap_until`; `docs:` and `notes:`; a hand-maintained `CLAUDE.md`
Testing paragraph). Re-entry at `ONBOARD_NEXT:`; every phase idempotent;
`--no-task`; the `--policy selected` re-entry writes the flip only on
`ADMISSIBLE` with `approved_by`, for a project that chose `completion.mode:
full`. Headless: level 0, then level 1 in full — `adopt --auto` over the
measured origins, the review pass read by the skill's own agent, `adopt
--auto` over the verdicts, `finish --auto` — no prompts, no kinds
(`CLASSIFY_PENDING` printed), no scaffold, and no policy re-entry because
`auto` flips itself. The skill exports `AIT_PROFILE_HEADLESS=1` around the
engine in the headless profile so `reject` and `classify --apply` refuse.
The full flow is under *Onboarding*.
<!-- /section: component_onboarding_skill -->

**The run surface**

<!-- section: component_test_entrypoint [dimensions: component_test_entrypoint] -->
### Test entrypoint `ait test` *(adoption layer)*

`.aitask-scripts/aitask_test.sh`, a ~150-line bash front over the shim, with
flags `--task <id> | --gate | --advisory | --all | --dirty | --explain |
--howto [--md] | --tokens | --fresh-only | --budget-s <n> | --json` and
positional `<path|id>...`. It resolves `MODE` (completion iff `--gate` or
`$AIT_GATE_TASK_ID`; advisory iff `--advisory`; else interactive), `TASK`
(`--task` > `$AIT_GATE_TASK_ID` > `aitask/<task_name>` branch > single own
lock via `aitask_lock.sh --list-mine` > `NO_TASK`), `INTAKE` (change surface
piped; `--dirty`; `--all`; named paths, a source path as a one-file `TASK:`
set) and `POLICY` (completion: `config.yaml completion.mode` re-checked
against `readiness`); calls the engine `test` composite (interactive: the
budget applies and `DEFERRED` is printed; completion: deferred rows run);
with no `aitestmap/` prints `TESTMAP_ABSENT:<hint>` and delegates to
`aitask_run_project_command.sh test_command`; with the engine absent prints
`ENGINE_MISSING:<path>|<repair>` and exits 3 interactively, runs the suite
runner's `fallback_command` in completion mode when
`completion.engine_absent` is `fallback_command`, and prints `VERDICT:skip
REASON:testmap_absent` in advisory mode. Advisory mode prints
`VERDICT:pass|fail|skip` /
`REASON:all_passed|command_failed|testmap_absent|registry_absent|unknown_paths|no_selection|admission_refused`
/ `DETAIL:` / `LOG:.aitask-gates/<task>/affected_<run-id>.log` / `SELECTED:`
/ `UNMAPPED_SOURCE:` / `UNKNOWN:` lines, exits `0/1/2/3` with
`aitask_run_project_command.sh`'s capture contract, and appends nothing to
any ledger. Every mode prints `MODE / TASK / INTAKE / POLICY / SELECTED /
RUN / RESULT`, `UNANNOTATED_TEST:<path>` + `HINT` (a listed test in the
change surface with no `testmap:` block, no seed and no adopted row) and
`UNMAPPED_SOURCE:<path>`; exits `0 / 1 / 2 / 3 / 75 / 64`. Dispatcher arm
`test)` in `ait`; five permission touchpoints (no second helper script;
`tests/test_touchpoint_count_contract.sh` re-pinned).
`tests/test_ait_test_entrypoint.sh` drives a fixture repository with
`AIT_TESTMAP_BIN` pointing at a fake engine that replays scripted exits, in
all three modes and every `REASON`.
<!-- /section: component_test_entrypoint -->

<!-- section: component_test_front_verb [dimensions: component_test_front_verb] -->
### Engine `test` composite *(adoption layer)*

`internal/selectr` + `sched` + `runner`, reached by `aitask_test.sh`: `test
--task <id> --changes - | --paths <p>... | --all [--explain] [--budget-s]
[--format lines|json|tokens] [--run <id>]` runs `select --include-stale` →
`schedule` → `run` in one process and prints
`SELECTED:<n>|<groups>|<est_s>|<seeded_n>|<adopted_n>`, one
`UNMAPPED_SOURCE:<path>` per changed source no unit reaches, the ranked rows
with their reasons (a seeded edge reads `edge(seeded:<origins>)`, an adopted
one `edge(annotation) adopted(<origins> <confidence>)`), the schedule's wave
lines, results per id and `RESULT:pass|fail|skip|deferred|<run_id>`. `--all`
is `run --all` (anchors evidence, scores the newest prediction, honours
`subsumed_by`); `--explain` stops after `select`; the run id is prefixed by
the front. It never resolves a task, reads a profile, applies a completion
policy or touches a gate ledger — those are the bash front's.
<!-- /section: component_test_front_verb -->

<!-- section: component_agent_brief [dimensions: component_agent_brief] -->
### Agent brief *(adoption layer)*

`internal/brief`, verb `brief [--md]`, surfaced as `ait test --howto [--md]`
and `ait testmap brief`: `TESTMAP:<state>|since|LEVEL:<n>|POLICY:<mode>|seeds
pending <n>|adopted unreviewed <n>`; one `RUNNER:<name>|<kind>|<units>|<how
it is invoked>|<resources>[|subsumes ...]` line per runner;
`FULL_GATE:<runner>|<p95 est>|<= project_config test_command>|<tests_pass
timeout>`; `GATE:` (the chain `testmap_fresh` → `testmap_check` →
`tests_pass` and what `--gate` would run now); `VERBS:` (the four forms);
`AXES:` per declared axis with facets and value counts; `RESOURCE:` per
declared resource with its kind and what a refusal looks like; `NEW_TEST:`
(the `annotate --suggest` hint); `DOCS:<path>` per `config.yaml docs:` entry;
`NOTES:` the `config.yaml notes:` lines verbatim (≤ 10); `ONBOARD_NEXT:`
while a ledger is unfinished. Before onboarding it prints `TESTMAP_ABSENT`
plus the `test_command`. `--md` renders the same as markdown. < 100 ms warm.
The worked example is under *The Run Surface*.
<!-- /section: component_agent_brief -->

<!-- section: component_agent_instructions [dimensions: component_agent_instructions] -->
### Agent instructions *(adoption layer)*

The fourteen-line `## Running Tests` section (text under *The Run Surface*)
in `seed/aitasks_agent_instructions.seed.md`, installed unchanged into
`CLAUDE.md`'s `>>>aitasks` block, `AGENTS.md`, `.codex/instructions.md` and
the OpenCode mirror by the existing `assemble_aitasks_instructions()` /
`insert_aitasks_instructions()` on every `ait setup` and `ait upgrade`. The
seed carries no project specifics and names no agent — `ait test --howto`
computes them, so the current-state-only documentation rule holds and
nothing condensed from `runners.yaml` lives in a constant.
`tests/test_agent_instructions.sh` gains one case asserting the heading in
all four rendered surfaces through a real `install.sh --dir`. The
hand-maintained `CLAUDE.md` case (sentinel present, no markers) is the
level-0 onboarding task's edit.
<!-- /section: component_agent_instructions -->

**Workflow and gates**

<!-- section: component_completion_policy [dimensions: component_completion_policy] -->
### Completion policy *(adoption layer)*

`aitestmap/config.yaml completion:`: `mode full|selected|auto` (`auto` is
what `detect --write` writes; `selected` is written only by the onboarding
skill's `--policy` re-entry after `READINESS_DECISION:ADMISSIBLE`, beside a
human `run_gate_admission.approved_by`; `full` is the project's opt-out of
any flip), `deferred run|fail` (what completion does with rows the
interactive budget would cut; default run), `on_empty_selection skip|full`
(default skip → exit 2 → gate skip under the opt-in; ignored by a cadence
full run), `engine_absent error|fallback_command` (default error), and
`auto: {full_every_n, full_when_selection_over, full_after_days}` — the
cadence, all three required when the mode is `auto`
(`READINESS:cadence_declared`). `ait test --gate` re-checks `readiness` on
every completion run: under `selected`, an unmet criterion prints
`POLICY_DEMOTED:selected->full|<criterion>` and runs full; under `auto`, a
not-yet-admissible map runs full (`POLICY:auto|full|not_admissible`), the
first admissible run prints `POLICY_FLIPPED:auto->selected|engine:readiness@<run>`
and writes `approved_by {who: engine:readiness, run, at}` for its caller
to commit, a later unmet criterion prints `POLICY_DEMOTED:auto->full|<criterion>`
and clears `approved_by`, and a due cadence rule runs full with
`POLICY:auto|full|cadence(<rule>)` and records `last_full_run`. The human
flip and the engine flip are both bounded by the same automatic demotion,
and the engine flip additionally by the cadence, so the policy can only
fail toward running more. The full-run cadence is the knob that sets how
long a miss can survive (`full_every_n − 1` tasks, `full_after_days` days)
and is printed by `--howto` so a project sees what it chose. `readiness`
prints `POLICY:<mode>|<what --gate would run now>[|full_in:<k>]`; the
gate-run ledger block carries `result="MODE:<full|selected>|<n
units>|policy:<mode>[|full_in:<k>|cadence:<rule>]"`.
<!-- /section: component_completion_policy -->

<!-- section: component_gates [dimensions: component_gates] -->
### Gates *(adoption layer)*

`testmap_fresh` (kind procedure, verifier `aitask-gate-testmap-fresh`, no
unlocks; gains the adopt / reject / leave step for seeds on the task's
touched test files) and `testmap_check` (machine, `max_retries 0`, `timeout
120`, `unlocks: [tests_pass]`) in `gates_reference.yaml` synced to
`gates.yaml`. The completion test gate is the existing `tests_pass` with
`test_command: ./ait test` and `gate_command_exit_contract: [test_command]`,
so `ait gates run` needs no new verifier for running tests and the legacy
no-gates path needs no new prose — a project reaches the selective lane by
declaring `tests_pass`, which onboarding's `enable` phase writes into the
profiles' `default_gates` with `testmap_check` and `testmap_fresh`, with
confirmation; never by hand, never by `ait setup`. There is no selection-only
gate and no `aitask_gate_testmap_run.sh`. `aitask_gate_testmap_check.sh`
reports `SEEDED:<n>` and `ADOPTED:<n>` (informational, never fail) and
`UNMAPPED_SOURCE:<path>` (a changed source with no edge, seed, rule or waiver
— reported during bootstrap, failing under `--strict` past
`bootstrap_until`; the strict flip is onboarding's `finish` phase). An
`unlocks:` target absent from a task's active set is ignored, so
`testmap_check` declared alone is linear as before. `run_gate_admission` and
`ait testmap readiness` gate the completion policy flip rather than a second
gate's declaration; under `completion.mode: auto` the verifier's `./ait
test --gate` performs the flip and the `tests_pass` ledger block's `result=`
field names `policy:auto` with `full_in:<k>` or `cadence:<rule>`, so a
ledger reader sees whether the whole suite ran and why.
<!-- /section: component_gates -->

<!-- section: component_workflow_seam [dimensions: component_workflow_seam] -->
### Workflow seam — the data edits *(adoption layer)*

`task-workflow/SKILL.md.j2` Step 7 gains one paragraph after *Follow the
approved plan* — run `./ait test` as the implementation test loop, answer
`UNANNOTATED_TEST` with `annotate --suggest` and `UNMAPPED_SOURCE` by mapping
the source, never call the test tool directly (rendered into every profile;
goldens regenerated). `build-verification.md` gains a branch for verdict
`error` / reason `command_refused | command_errored` (host refused resources
or the framework could not run: do not fix code, do not record pass, re-run
later — the entrypoint already deferred to its deadline).
`lib/gate_verifier_lib.sh run_project_command_key()` gains the 75 → error and
3 → error rows for opted-in keys and exports `AIT_GATE_TASK_ID` /
`AIT_GATE_RUN_ID` around the command; `aitask_run_project_command.sh
--task-id` exports the former. `gates_reference.yaml` adds `testmap_fresh`
and `testmap_check` (`unlocks: [tests_pass]`). The project's profiles gain
`tests_pass`, `testmap_check` and `testmap_fresh` in `default_gates` via
onboarding. The `ait` dispatcher gains `test)`.
`aidocs/framework/aitasks_extension_points.md` gains *Adding a test-framework
detector* and *Adding a seed origin*. `tests/test_gate_verifiers.sh` covers
75 and the env export; `tests/test_serial_carveout_doc_drift.sh` is extended
for the pytest carve-out pin; `tests/test_no_unscoped_task_commit.sh` is
unaffected because the skill commits through `aitask_task_commit.sh`.
<!-- /section: component_workflow_seam -->

<!-- section: component_workflow_integration [dimensions: component_workflow_integration] -->
### Workflow integration — the procedure edits *(adoption layer)*

task-workflow gains `affected-tests.md` (the Affected Tests Procedure),
called once from Step 7 before proceeding to Step 8, wrapped in `{% if
profile.affected_tests is not defined or profile.affected_tests != 'off' %}`;
the procedure runs `./ait test --advisory --task <id>` (with `--explain` when
the key is `show`) in the `set -e` capture form and branches per the table
under *The Workflow Seam*; its autonomous `no_selection` and
`UNANNOTATED_TEST` branches run `ait testmap annotate --author <test>
<source>` for pairs on the change surface (*component_author_annotation*),
so a headless task stamps the couplings it created; the verdict line is
recorded in the plan's Final Implementation Notes and never in the gate
ledger. Profile keys `affected_tests: run|show|off` and
`unmapped_source_autonomous: author|propose` are documented in
`profiles.md`; `default.yaml` and `fast.yaml` omit both (run, author);
`remote.yaml` sets `run` and `author`. The in-loop call is
the Step-7 paragraph, not the procedure. Step 8 (`testmap_fresh` dispatch
plus its adopt-on-touched-files step) and Step 9 (gate orchestrator,
`build-verification.md`) are otherwise unchanged. `aitask-gate-testmap-fresh`
gains the adopt-on-touched-files step. `aitask-qa`'s `test-discovery.md`
uses `ait testmap explain --sources <changed> --format table` when
`aitestmap/` exists and `test-execution.md` runs `./ait test` through
`aitask_run_project_command.sh --task-id`. pickrem and pickweb inherit Step 7
and see a printed skip on Web. `ait setup` prints `TESTMAP:<state>`. Goldens
under `tests/golden/` are regenerated for every profile × agent;
`aitask_skill_verify.sh` is run.
<!-- /section: component_workflow_integration -->

<!-- section: component_qa_integration [dimensions: component_qa_integration] -->
### aitask-qa integration *(adoption layer)*

`aitask-qa` reads the registry when `aitestmap/` exists: `test-discovery.md`
3a–3c map the changed sources through `ait testmap explain --sources <paths>
--format table` (edges, test-deps, scoped rows; `Covered` / `Covered
(adopted)` / `Covered (seeded)` / `GAP` for a source with no edge and no
test-dep), falling back to the naming-convention scan only when no registry
exists; `test-execution.md` 4a runs the configured `./ait test` through
`aitask_run_project_command.sh test_command --task-id <id>` (which exports
`AIT_GATE_TASK_ID` so the run is the task's selection), 4b runs named units
through `ait test <path>`, 4c gains a `REFUSED (host resources)` row for
verdict error / `command_refused`, and 4d's coverage component uses registry
edges rather than file-name matches, with seeded rows counted as coverage
that exists (QA measures whether a test exists, not whether its claim is
fresh); the health score's Tests component treats `REFUSED` like `SKIP`.
<!-- /section: component_qa_integration -->

<!-- section: component_skill [dimensions: component_skill] -->
### Skills *(core + adoption layer)*

Three skills. **`aitask-testmap`** (maintenance: annotate a file / member /
coordinate — including `annotate --author` for the task's own pairs —
declare axis sources, `reads` on helpers, `axes --explain`, `attribute`
before the gate, `verify` after editing, `classify --suggest`, `select
--format tokens` into a render loop) opens with `ait test --howto` and hands
a repository without `aitestmap/` to `aitask-testmap-onboard`.
**`aitask-gate-testmap-fresh`** (the procedure gate: `stale --task`, `git
diff` per `STALE` row with unevidenced variants, retarget `STALE_PATH`,
re-stamp `EVIDENCED`, resolve `check`'s structural rows, prompt on
`UNSTAMPED` past bootstrap, never guess `UNKNOWN`, never confirm `STALE`
autonomously; an `adopted(...)` row is confirmed knowing it is a
class-accepted claim) gains one step: for each `COMMITTED:` / `TASK:` test
file with rows in `seeded.yaml` it shows the seeds with their evidence and
verdict rationale and offers adopt / reject / leave per row — autonomous
profiles adopt the `verifies` rows and leave the rest — so a map migrates a
few files per task through ordinary work. **`aitask-testmap-onboard`** is
the new profile-aware onboarding skill, whose `review.md` phase is where an
agent reads seeds. Every skill's runtime knowledge of how to run
tests is the seeded `## Running Tests` block plus `./ait test --howto`, never
prose in a `SKILL.md`. All ship Claude Code first, with wrapper surfaces
regenerated by `aitask_audit_wrappers.sh apply-wrapper`; Codex and OpenCode
ports are separate tasks.
<!-- /section: component_skill -->

**Agent-driven adoption**

<!-- section: component_agent_review [dimensions: component_agent_review] -->
### Agent review pass *(adoption layer; new)*

`internal/onboard/review.go` behind `onboard review [--class <origin>]
[--batch 25] [--out <dir>] [--crew <id>]`, `onboard review --answer <file>`
and `onboard review --collect <crew-id>`. Batch writer: selects seeded rows
without a verdict for the current test blob (memo in `onboard.yaml
reviews[]`), groups them by test file so one file's pairs land in one
batch, and writes `review/<n>.md` — per `REVIEW_ITEM`: `PAIR:<test>|<source>`,
`ORIGINS:<list>|<confidence>`, `EVIDENCE:<line>`, the test excerpt (±40
lines around every line the deps scanner attributed to the source, or the
whole file under 200 lines, with line numbers), and `SOURCE:` (header
comment, exported functions / options / output tokens from the deps
scanner's facts); a trailing `ANSWER_FORMAT:` block states the verdict
grammar. Answer validator: pair ∈ batch; `test_blob` unchanged; for
`verifies`, `assert_line` parses as `<test path>:<n>`, the line exists and
contains the source's stem, its invocation form, an output path the source
writes or an exported symbol; rationale ≤ 200 chars, `|` encoded as `%7C`.
Writes: the row's `origin[] += agent:review`, `evidence.agent_review`,
recomputed noisy-OR confidence; `reviews[]` memo; prints `REVIEW_APPLIED`,
`REVIEW_INVALID`, `REVIEW_PARKED:<n>`, `REVIEW_AGREEMENT:<a>/<l>`,
`REVIEW_ORIGIN_DEMOTED` at the threshold. `model` from `AIT_AGENT_STRING`,
`run` = `rev-<run-id>`. `--crew` registers one reviewer per batch through
`aitask_crew_addwork.sh --type reviewer --work2do review.md` and prints the
`ait crew runner` line for a person to start; `--collect` reads each agent's
`_output.md` as an answer file. Config: `agent_review {confidence 0.90,
batch 25, min_agreement 0.85, calibration_min 30}`. Tests: fixture repos
per language for batch content; every `REVIEW_INVALID` reason; the memo;
agreement crossing the threshold both ways; a `verifies` line naming a
homonym stem from another source is `REVIEW_INVALID:assert_line_names_other`.
<!-- /section: component_agent_review -->

<!-- section: component_auto_policy [dimensions: component_auto_policy] -->
### Auto completion policy and cadence *(adoption layer; new)*

`internal/feedback/cadence.go` and the `auto` arm of `aitask_test.sh`'s
policy step. State: `config.yaml completion.auto {full_every_n,
full_when_selection_over, full_after_days}`, `run_gate_admission.approved_by
{who: engine:readiness, run, at}` and `last_full_run {run, at, sha}`
(committed, written by the verifier's caller through the same `ait:` commit
path the human flip uses — the engine prints `CONFIG_WRITE:<key>` and the
bash front commits under `ait: testmap policy <flip|full-run> (t<id>)` with
the path named); the count of selected completions since `last_full_run`
comes from the ledger (`gate-` runs with `MODE:selected`). Decision order
inside `ait test --gate` under `auto`: `readiness` → `NOT_YET` → full;
`ADMISSIBLE` and no `approved_by` → `POLICY_FLIPPED`, write, selection;
cadence rule due → full with `POLICY:auto|full|cadence(<rule>)`; else
selection with `FULL_IN:<k>` = `full_every_n − n`. A cadence full run
ignores `on_empty_selection`, honours `subsumed_by` and `deferred: run`, and
triggers the window score (*component_feedback_tools*). `readiness` adds
`cadence_declared` (all three rules present and sane: `full_every_n ≥ 2`,
`0 < full_when_selection_over ≤ 1`, `full_after_days ≥ 1`) and the `CADENCE:`
line. `--howto` prints the cadence on the `GATE:` line. Tests:
`tests/test_ait_test_entrypoint.sh` with the fake engine replaying
`readiness` states and ledger counts for each rule, the flip write and
commit, the demotion clearing `approved_by`; engine tests for the window
score.
<!-- /section: component_auto_policy -->

<!-- section: component_author_annotation [dimensions: component_author_annotation] -->
### Author annotation *(adoption layer; new)*

`ait testmap annotate --author <test> <source>... [--task <id>]` in
`internal/annot` as a caller of the rewriter with an `adopted.yaml` write:
resolves the task as `ait test` does, reads the change surface through
`aitask_change_surface.sh list <id>` (`--changes -`), refuses
`ANNOTATE_REFUSED:<pair>|outside-change-surface` unless both the test and
the source are `COMMITTED:` or `TASK:` rows, refuses an unregistered test
(`ANNOTATE_REFUSED:unregistered`), writes the stamped `testmap:covers` line
at the fixed per-language position (or into the member block), and adds
`adopted.yaml {test, source, origin: [agent:author], confidence: 0.90 (0.99
with a static relation), adopted_at, task, by: author, evidence {run,
static: <invocation|import|package|none>}}`; prints `WROTE:<file>`,
`AUTHOR_STAMPED:<pair>|<static or none>` and `AUTHOR_UNCORROBORATED:<pair>`
when the closure holds no relation. The pre-review procedure's autonomous
branch is its only automatic caller; the attended offer's *Annotate as
author* is the same verb; `aitask-testmap` documents it. `stale` and
`explain` show `adopted(agent:author 0.90)`; a later human re-stamp deletes
the row like any adopted row; `readiness` and `onboard status` count
`AUTHOR_UNCORROBORATED`. Tests: the refusal outside the surface, member
placement, the corroborated and uncorroborated confidences, the row leaving
on `verify`.
<!-- /section: component_author_annotation -->
<!-- /section: components -->
<!-- section: assumptions [dimensions: assumption_*] -->
## Assumptions

Every assumption of the baseline is inherited; two are rewritten
(`assumption_seeds_select_never_evidence`, `assumption_seed_sources_measured`)
and four are new (`assumption_agent_can_judge_verifies`,
`assumption_cadence_full_run_bounds_miss`,
`assumption_author_annotates_own_surface`,
`assumption_session_agent_is_reviewer`). Each is stated with its falsifier
where one is known. Full text is in the node metadata.

### Engine, distribution and install

- **`assumption_go_toolchain_available`** — Go ≥ 1.26 is available in release
  CI through an `actions/setup-go` step this design adds to `release.yml`
  (`go-version-file: engine/go.mod`) and on framework developers' machines;
  target-project users never need Go.
- **`assumption_go_toolchain_ci_and_dev_only`** — Go is a build-time
  dependency only: `release.yml` has no Go step today and the repository's
  only `setup-go` is `hugo.yml`'s for the website, so the engine job
  provisions its own toolchain; users receive prebuilt binaries.
- **`assumption_platform_matrix_sufficient`** — linux/darwin × amd64/arm64
  covers every target host (WSL reports Linux); any other platform builds
  from source via `--engine-from-source`.
- **`assumption_release_asset_reachable`** — a host running `ait setup` or
  `ait upgrade` can reach the GitHub release over HTTPS, as it already must
  for the framework tarball; the shim never downloads, so a gate run never
  performs a network fetch.
- **`assumption_release_assets_reachable`** — air-gapped or off-matrix hosts
  supply the binary via `--local-engine`, `--engine-from-source`,
  `AIT_TESTMAP_BIN` or a pre-seeded `$AITASKS_HOME/engine/`; `--no-testmap` /
  `AIT_TESTMAP_FETCH=0` skip the fetch and nothing else in setup depends on it.
- **`assumption_one_engine_per_framework_version`** — one engine build per
  framework version suffices; the per-user versioned directory resolves
  per-project VERSION differences without a compatibility matrix, and the
  shim never falls back to newest-wins.
- **`assumption_engine_latency_targets`** — on the aitasks shape (~720 units,
  2,500–3,000 edges, ~270 scanned sources) `select` < 200 ms warm, `scan` /
  `check` / `stale --task` < 300 ms, `stale --all` < 2 s, cold `select` <
  1.5 s; on the thinking_app shape (297 variants over 49 members, 374 JVM
  classes, ~900 Kotlin files) `select` with axis expansion < 250 ms warm,
  reading the committed variants list and never executing a runner; pinned by
  committed `go test -bench` fixtures with a 2× regression failing
  `engine-check.yml`, validated before the gates are enabled.
- **`assumption_home_symlink_compatibility`** — every existing consumer of
  the legacy `~/.aitask` tree keeps resolving when it becomes a symlink to
  `~/.aitasks`, because all of them dereference a path rather than compare
  one: verified across the 35 references in 8 framework files, the venv's
  console-script shebangs, the `~/.aitask/bin/python3` wrappers, the
  `python/<ver>/bin/python3` symlinks and `pyvenv.cfg`; no `==`, `-ef`,
  `realpath` or `samefile` on the home path anywhere. This is the
  precondition of `ait engine home --migrate`, re-checked by
  `tests/test_aitasks_home.sh` before the default is flipped.
- **`assumption_legacy_user_root_coexists`** — in this release `~/.aitasks/`
  (engine) and `~/.aitask/` (venv, pypy_venv, python, bin, uv, dev_tier,
  update_check) coexist without either reading the other; the migration
  exists as an explicit verb and nothing in this feature depends on it having
  run.
- **`assumption_target_repos_accept_aitestmap_root`** — every target repo
  accepts a root `aitestmap/` directory of committed YAML (now also
  `onboard.yaml`, `seeded.yaml` and `adopted.yaml`) and an optional
  `axes.yaml`; runner scripts and axes are optional because the reference
  runners are built in; thinking_app commits one runner script because its
  lowering is the harness's own routing.
- **`assumption_testmap_token_no_collision`** — the token `testmap:` collides
  with no existing prose comment in any target repo; the 38 `# Covers:`
  headers in aitasks are behavioural prose and are not matched.

### The map and freshness

- **`assumption_blob_digest_is_staleness_key`** — the git blob digest of the
  covered source is the staleness key; mtime and the annotation date are
  never compared; the blob id doubles as the join key into any commit's tree.
- **`assumption_git_history_is_freshness_clock`** — git history is the
  evidence clock, not the staleness key: commit reachability decides which
  `last_pass` anchors may suppress a `STALE` row, never whether an edge is
  stale; a shallow clone reports `STALE`, not `EVIDENCED`, and stays
  functional. Co-change reads history as a *seed* source, never as a
  freshness or evidence source.
- **`assumption_passing_run_anchors_edges`** — a passing run of a variant at
  commit C, on any host class, from an invocation without a cause and for an
  id under the flake threshold, is evidence that its annotated edges held
  against C's tree; a unit with variants is `EVIDENCED` only when every
  reached variant has such a pass; a `verify-active` full run's child rows
  anchor all 297 goldens at once.
- **`assumption_static_granularity_v1`** — file-level facts are the default,
  with two narrower granularities in use: member units and the edge's
  symbols slot (first consumer: the opt-in `android-res` scanner); no
  scanner produces symbol-level coverage of Kotlin or Python code; a change
  anywhere in a member file is a change to every member until hunk-level
  attribution exists.
- **`assumption_kotlin_scanner_fail_closed`** — a closed construct list
  over-approximates the Kotlin import graph, and every construct that defeats
  it (inline functions, `const val`, DI bindings, reflection, generated
  sources, an unreadable file) is detectable by pattern and marks the file
  opaque so a change escalates; measured on thinking_app, 42 main files
  declare `const val` or `inline fun` and 63 carry DI annotations, so
  escalation is frequent by design; each opaque branch is red-proved by a
  fixture test.
- **`assumption_annotation_is_comment_only`** — integrating an existing test
  never changes what it does: `onboard adopt` inserts `testmap:` comment
  lines at the fixed per-language position (never into a Python docstring,
  because that changes `__doc__`; inside the member's `testmap:unit` block
  for a member seed); `git diff -w --ignore-blank-lines` shows comments only;
  a file with no known comment leader is skipped with `ADOPT_SKIP:no-leader`
  and stays seeded; `# Covers:` prose headers are shown as context and read by
  the `prose` origin, never rewritten.

### Variants, broad tests and runners

- **`assumption_variant_universe_from_runner_list`** — a runner's `list`
  enumerates the complete universe its run filter can address, so whole-run
  selection is sound; a class absent from `list` is `UNREGISTERED`, never
  silently unfiltered; `scan --apply` persists each member's listed variants
  so `select` reads the committed table.
- **`assumption_cells_enumerable_by_plugin`** — the variant universe is
  enumerable from the project's existing routing statement through the
  runner's `list` verb (thinking_app: `matrix_classes()` crossed with the two
  membership manifests; aitasks: the rendered `tests/golden/` tree); the
  framework never infers a variant. Falsifier: tests knowable only by running
  the build — `list` may exec the build's own list task at the cost of a
  slower `scan` / `check`, since `select` never calls it.
- **`assumption_axis_sources_declarable`** — the sources that reach one
  facet value are declarable as globs (thinking_app's locale facet:
  `values-<q>/**`, `raw-<q>/**`, the per-family fonts); sources every locale
  reads are ordinary edges or one hand rule and reach every variant; the
  geometry and direction facets have no axis sources because they are
  test-side constants reached through the test-dep closure.
- **`assumption_axis_membership_declarable`** — which facet value a source
  belongs to is declarable by the people who own the suite because the
  project already routes by that shape; a source matching no axis source
  reaches units only through edges and dependencies, which select every
  variant. Falsifier: genuinely dynamic membership — declare no sources on
  that facet.
- **`assumption_batch_per_unit_timing_reportable`** — runners report
  per-unit timing inside a batch from their tool's own report (JUnit XML, `go
  test -json`, pytest junitxml), invert a report row to a registered id
  through the runner's own routing table, and JUnit XML reports each method
  with its own duration, which is what makes a variant's marginal cost
  measurable apart from its class's boot.
- **`assumption_areas_express_suite_blast_radius`** — a broad test's blast
  radius is expressible as area glob sets plus scope globs plus
  budget-exempt trigger globs plus the `reads` globs of helpers in its
  closure; what that misses surfaces through `score` as an observed trigger
  or area member.
- **`assumption_broad_tests_area_scoped`** — integration, e2e and device
  tests can be described by areas or globs whose membership changes rarely,
  so evidence-based drift (`STALE_AREA`) plus `attribute` widening is
  adequate; the calendar cadence is opt-in.
- **`assumption_existing_locks_wrappable`** — existing project locks and
  allocators (thinking_app's heavy-run lock with exit-75 admission, the
  emulator allocator) can be wrapped as resources without changing them; the
  admission and allocator kinds exec the project's commands and honour their
  exit codes, deferring on 75 until the run deadline.

### Seeding and adoption

- **`assumption_seed_sources_measured`** *(rewritten)* — one origin table
  seeds edges, each heuristic origin measured on 2026-09-16 and none of them
  trusted alone; the two *measured* origins (`static:package`, `coverage`)
  and the two *reader* origins (`agent:review`, `agent:author`) are the
  only ones an autonomous path may adopt on, and `agent:review`'s 0.90 is
  provisional until `REVIEW_AGREEMENT` measures it against human-labelled
  pairs; confidence combines by noisy-OR, orders the queue and never hides a
  row; seeding is partial by construction and the remainder is rules,
  waivers, author annotation and incremental adoption.
- **`assumption_static_closure_seeds_edges`** — the test-file static closure
  is a sufficient primary seed on the target shapes and naming conventions
  are not: 398 of 400 aitasks bash tests name their subject path literally
  (the two that do not are pure fixture tests), 320 of 320 Python tests
  import a lib module, only 52 of 400 bash tests match the `test_<stem>.sh →
  aitask_<stem>.sh` convention; Go's subject is deterministic; Kotlin's is
  the same import scanner the selector uses. Only the direct relation is
  seeded. Falsifier: tests reaching subjects only through a dynamic
  dispatcher — no static rows; conventions plus co-change, or level 0 only.
- **`assumption_cochange_is_corroboration`** — `(t<id>)` history
  corroborates and never decides: 336 task groups in 400 aitasks commits at
  1.14 commits each, pairing a few tests with a few scripts with nothing in
  the group saying which covers which; hence 0.20 + 0.20 × groups, capped at
  0.60, ≥ 2 distinct tasks, unreachable to the 0.85 class threshold alone or
  with convention (0.84); per-commit grouping where the convention is absent;
  one `git log` pass cached by HEAD sha; `SEED_HISTORY:shallow|<n>` on a
  shallow clone.
- **`assumption_helpers_separable_by_fanin`** — within a closure, helpers are
  separable from subjects by declared helper roots and by fan-in ≥ 5 % of the
  runner's units; helpers get `test-dep` through the closure and, when they
  glob the tree, a proposed `testmap:reads`. Falsifier: a hot production
  module imported by most tests is misread as a helper — it keeps `test-dep`
  selection (over-selects) and every reclassification is listed for review.
- **`assumption_seeds_select_never_evidence`** *(rewritten)* — a seed may
  cause a test to run and may never suppress `STALE`, anchor evidence,
  satisfy `require_stamp` or count under `--strict`; a verdict on a seed
  changes none of that; it becomes a claim only through an explicit adopt,
  by class (with provenance) or by row, and an autonomous adopt needs a
  measured origin, a `verifies` verdict or the author's own surface; no
  agent path removes a seed. Falsifier: a suite so expensive that seeded
  over-selection is itself the problem — the suite budget and `--format
  tokens` are the levers, not trusting seeds.
- **`assumption_agent_can_judge_verifies`** *(new)* — an agent that reads a
  test body beside the source it names can tell a test that *verifies* the
  source (asserts on its output, exit, side effect or a symbol it exports)
  from one that only *drives* it (runs it to build state for another
  assertion), and can name the assertion line, with agreement ≥ 0.85 against
  human per-row decisions; the engine's check that the named line exists
  and names the source turns a free-text judgement into one with a
  machine-checkable anchor. Measured nowhere yet — the first calibration set
  is the in-gate and per-row adoptions on aitasks. Falsifier: agreement
  under `min_agreement` over `calibration_min` pairs → `REVIEW_ORIGIN_DEMOTED`
  to 0.60 and autonomous verdict adoption stops; a project can also set
  `agent_review.confidence: 0.60` from day one to keep verdicts as
  corroboration.
- **`assumption_session_agent_is_reviewer`** *(new)* — the agent running
  the onboarding skill or the pre-review procedure is the reader; no script
  of this feature spawns a print-mode process, so the review pass costs the
  session's ordinary tokens (aitasks: ~1.5 M input tokens over 28 batches)
  and never a gate run's; the crew form exists for parallel review behind
  the framework's `--headless` opt-in and is started by a person.
  Falsifier: a harness whose session cannot read 25 pairs of excerpts in
  one file — lower `agent_review.batch`.
- **`assumption_author_annotates_own_surface`** *(new)* — the agent that
  wrote or edited a test within a task knows which source on the same
  change surface it checks at least as well as any static seed, and its
  claim is safe to adopt because it is limited to pairs whose two files are
  both in the task's diff, is shown as `adopted(agent:author 0.90)`, is
  flagged `AUTHOR_UNCORROBORATED` when no static relation supports it, and
  rides the Step-8 review. Falsifier: an agent stamping every touched pair
  to silence `UNMAPPED_SOURCE` — visible as a rising uncorroborated count
  in `onboard status`, and `unmapped_source_autonomous: propose` turns the
  branch off.

### Onboarding

- **`assumption_test_tools_detectable`** — every target repo's test tools
  are detectable from the tree and the project config without executing a
  build (pytest markers, `go.mod` + `_test.go`, `gradlew` + source-set
  roots, `tests/test_*.sh` + `asserts.sh`, `package.json`, a `Makefile`
  target, `test_command` / `verify_build`); verified on the five
  repositories; every `FRAMEWORK:` row carries its evidence. Falsifier:
  build-time test generation — `DETECT_UNKNOWN`, the skill asks.
- **`assumption_full_run_expressible_per_repo`** — every target's completion
  suite is `ait test --all` over its runners or one `full: true` suite
  runner generated from `test_command` with a `children:` post-processor and
  a `fallback_command:` (thinking_app's `verify-active`; thinking_backend's
  `run_script_tests.sh`, kept as `verify_build` by default; aitasks_go's `go
  test ./...`; aitasks_mobile's `./gradlew check` minus the device classes;
  aitasks' 720 units which had no suite command and gain one).
- **`assumption_onboarding_is_a_task`** — onboarding writes committed files
  across several sessions, so each level runs as an aitask the skill creates
  and claims, committing per phase under `(t<id>)`, re-entering at
  `ONBOARD_NEXT:`, with the level-0 task's `tests_pass` as the first full
  run and the next level's task depending on it; a headless level-1 task is
  the same shape with the review pass as its longest phase. Falsifier: a
  repo that forbids tasks on the code branch — `--no-task`.
- **`assumption_cadence_full_run_bounds_miss`** *(new)* — under
  `completion.mode: auto` a coupling the map does not know can let a task
  land with an affected test unrun, and the damage is bounded by the
  cadence: the miss surfaces at the next cadence full run (at most
  `full_every_n − 1` selected completions or `full_after_days` later), is
  scored against every prediction in the window and attributed to the task
  whose surface reaches the failing unit, and one miss over
  `max_false_negatives` demotes the policy to full until readiness is
  admissible again. Falsifier: a project whose full suite is too expensive
  to run every N tasks — raise N, lower `full_when_selection_over`, or set
  `mode: full`; the cost is stated in `--howto`, never hidden.

### Run surface and workflow

- **`assumption_change_surface_is_intake`** — `aitask_change_surface.sh`'s
  attribution is the intake for every `--task` path (the gate verifiers, all
  three `ait test` modes, `stale --task`): its `COMMITTED:` / `TASK:` /
  `OTHER:` / `UNKNOWN:` lines are piped to `--changes -`, selection never
  reads a raw git diff, an `UNKNOWN:` row refuses selection (advisory:
  `VERDICT:skip REASON:unknown_paths`); `<path>...` is the one explicit-list
  intake, `--dirty` the explicit and printed no-task intake, `--all` has none;
  before-content for a symbol scanner comes from `HEAD:<path>` or the parent
  of the first `(t<id>)` commit.
- **`assumption_task_resolvable_from_session`** — the worktree branch
  `aitask/<task_name>` yields the id in worktree mode; the single
  Implementing lock this user holds yields it in current-branch mode; two or
  more are `AMBIGUOUS_TASK`; gate context supplies `AIT_GATE_TASK_ID`; the
  advisory form always passes `--task`. Falsifier: an agent outside the
  workflow — `ait test --dirty`.
- **`assumption_helper_degrades_when_absent`** — `ait test --advisory` can
  always answer: engine missing → `skip:testmap_absent`; no `aitestmap/` →
  `skip:registry_absent`; `UNKNOWN:` rows → `skip:unknown_paths`; empty
  selection → `skip:no_selection`; admission refused after the deadline →
  `skip:admission_refused`; only an executed run is pass / fail; only an
  unwritable log is 3. This is what admits the pre-review procedure into
  every profile including `remote` with no per-environment conditional; the
  interactive and completion modes keep the rule that a missing engine is an
  error.
- **`assumption_gate_exit_contract_reused`** — the verifier contract
  `0/1/2/3` is reached through the existing `tests_pass` verifier running
  `test_command`; `run_project_command_key()` — the single canonical
  statement of the command exit contract — gains 75 → error
  (`command_refused`) and 3 → error (`command_errored`) for opted-in keys, so
  a post-deferral refusal or a missing engine is a verifier error the
  orchestrator retries, never a code failure and never a skip; 2 stays the
  opt-in skip; the verifier exports `AIT_GATE_TASK_ID` / `AIT_GATE_RUN_ID`
  and `aitask_run_project_command.sh --task-id` exports the former, so the
  legacy Step-9 path, `aitask-qa` and the gate agree by construction;
  `testmap_check` keeps its own verifier shell; advisory mode speaks the
  `0/1/2/3` domain with 75 folded into a skip reason.
- **`assumption_instructions_block_reaches_agents`** — the seeded
  agent-instructions block is inserted between `>>>aitasks` / `<<<aitasks`
  markers into every supported agent's instructions file by `ait setup` and
  refreshed on re-run and on upgrade (verified in `aitask_setup.sh`), so a
  section added to the seed reaches every project on its next setup; the
  section names no agent, carries no project specifics and stays at fourteen
  lines; the hand-maintained `CLAUDE.md` case is the level-0 task's edit.
- **`assumption_instruction_block_is_read`** — code agents load
  `CLAUDE.md` / `AGENTS.md` at session start and follow a managed block that
  names one command, as the framework already relies on for `./ait git`,
  notes and the commit format. Falsifier: a harness that ignores the file —
  `ait test --howto` is the one-call fallback.
<!-- /section: assumptions -->

<!-- section: tradeoffs [dimensions: tradeoff_*] -->
## Tradeoffs

Every tradeoff of the baseline is inherited; the ones the agent-driven loop
touches are rewritten in place (`tradeoff_autonomous_confirmation_weak`,
`tradeoff_bulk_confirmation_granularity`, `tradeoff_seed_precision`,
`tradeoff_seed_noise`, `tradeoff_fail_closed_bootstrap_cost`,
`tradeoff_one_gate_not_two`, `tradeoff_onboarding_partial_coverage`) and
three are new (`tradeoff_agent_judgement_unmeasured`,
`tradeoff_cadence_window_misses`, `tradeoff_review_token_cost`). Advantages
first, then costs and risks by area, each with its mitigation.

### Advantages

- **`tradeoff_computed_vs_prose`** — selection is computed, explained and
  scored rather than remembered, and so is the run surface: `--howto` is
  generated, the instructions section is identical everywhere, and a
  200-line testing chapter becomes ten declared `notes:` lines plus `docs:`
  pointers reached through one verb; thinking_app's "shared component → full
  gate" rule is an axis join, a fan-out and an `ESCALATE:` line.
- **`tradeoff_engine_speed_enables_per_task_use`** — sub-second select /
  check / stale on a 720-test repo and sub-250 ms select over 297 variants
  with axis expansion make selection overhead negligible against the
  shortest test and let `check` run at every commit step.
- **`tradeoff_real_scheduler`** — goroutines plus `flock(2)` give correct
  cross-worktree contention and a critical-path report; the shell suite and
  the pytest lane get the enforced do-not-overlap that is only a comment
  today; a variant batch is one Gradle invocation holding one heavy-run slot.
- **`tradeoff_noarch_packages_preserved`** — Homebrew, AUR, .deb, .rpm and
  the tarball ship nothing compiled; the per-arch concern is one release job
  and one setup function.
- **`tradeoff_one_gate_not_two`** *(rewritten)* — *advantage:* one
  completion gate whose behaviour is a committed policy; an agent learns one
  command and one gate; the legacy Step-9 path and `aitask-qa` reach the
  selective lane through `test_command`; the flip is one line after
  readiness, written by a person under `selected` or by the engine under
  `auto`. *Disadvantage:* a ledger `tests_pass: pass` no longer says by
  itself whether the whole suite ran, and under `auto` not even a person
  decided that it should not — mitigated by
  `result="MODE:<full|selected>|<n>|policy:<mode>|full_in:<k>|cadence:<rule>"`
  on the gate-run block, the `gate-` run-id prefix, `POLICY_FLIPPED` and
  `POLICY_DEMOTED` being loud, `approved_by` naming `engine:readiness@<run>`
  so no one mistakes it for a person's approval, and `readiness` printing
  what `--gate` would run and when the next full run is due.

### Engine and distribution

- **`tradeoff_compiled_component_cost`** — the framework gains a compiled
  component: engine contributors need Go, a release fails if `go test` fails,
  install gains a fetch and checksum step; mitigated by one `build.sh`
  matrix, `ait engine build`, and the engine being optional until a testmap
  gate is enabled.
- **`tradeoff_two_toolchains`** — bash and Go in one framework; mitigated by
  the boundary rule, `engine-check.yml`, and Go source confined to `engine/`
  and excluded from the tarball.
- **`tradeoff_setup_network_fetch`** — `ait setup` gains its first
  self-downloaded release asset; mitigated by reusing the URL family
  `install.sh` already uses, SHA256SUMS verification, the `.sha256` sidecar,
  `--no-testmap` / `AIT_TESTMAP_FETCH=0`, the shim never fetching, and setup
  never depending on the binary for anything else.
- **`tradeoff_engine_version_skew`** — several ~10 MB binaries under
  `$AITASKS_HOME/engine/` for a user on several framework versions; mitigated
  by exact-version resolution and `ait engine prune` against the project
  registry, never count-based.
- **`tradeoff_strict_version_handshake`** — the binary must match `VERSION`
  exactly, so an upgrade on a host that cannot fetch leaves `ait testmap`
  refusing until a matching binary is supplied; intended fail-closed
  behaviour; the error names the fix and the path.
- **`tradeoff_engine_absent_on_host`** — an unsigned macOS binary or a
  blocked download leaves a host without an engine; mitigated by
  `ENGINE_MISSING` naming the path and repair verb, the source fallbacks, and
  declared gates exiting 3 (never skip). Two deliberate, printed exceptions:
  `ait test --advisory` reports `VERDICT:skip REASON:testmap_absent` so the
  pre-review run in task-workflow, pickrem and pickweb (which has no `ait
  setup`) continues, and a project may set `completion.engine_absent:
  fallback_command` for the Web lane with `MODE:fallback` visible.
- **`tradeoff_fallback_runs_more`** — with the engine absent and
  `engine_absent: fallback_command`, completion runs the pre-onboarding suite
  command — never less than before, never selective, no per-unit results, no
  anchors, no scoring; mitigated by the default being `error`, by
  `ENGINE_MISSING` naming the repair, and by `MODE:fallback` in the result.

### The per-user root

- **`tradeoff_two_user_roots`** — until `ait engine home --migrate` runs, a
  host carries `~/.aitask/` and `~/.aitasks/` side by side and a user who
  deletes one removes half the install; mitigated by one variable with one
  library owner, setup printing both roots and the `HOME_LEGACY:` hint,
  `ENGINE_MISSING` naming the exact path, `ait engine home` reporting the
  state, a test that fails if any script of this feature names `~/.aitask/`,
  and the migration verb existing now.
- **`tradeoff_split_home_rejected`** — installing only the engine at
  `~/.aitasks/engine/` and leaving the rest at `~/.aitask/` forever would be
  zero-risk but would leave two dot-directories one character apart holding
  halves of one install, explained forever by every doc page; chosen: the
  split as the transition, the migration designed, shipped as an explicit
  verb and reversible through the symlink, becoming the default in a named
  follow-up.
- **`tradeoff_home_migration_window`** — the migration has a sub-millisecond
  window between `rmdir ~/.aitask` and `ln -s` during which a process that
  hardcodes the legacy path sees ENOENT; narrowed by the flock, symlinking
  immediately after the rmdir, and refusing while another `ait` holds the
  home lock — not eliminated. Measured surface: 8 framework files with 35
  references, 20 test files, 18 doc files, the venv's absolute shebangs and
  two symlink trees — none rewritten, all resolving through the symlink. The
  refusal cases are the ones a designer does not see on their own host (the
  known-entry set once lacked `pypy_venv`), which is why the verb is explicit
  in this release.

### Map and registry structure

- **`tradeoff_registry_directory_complexity`** — a merged registry directory
  needs more CLI logic than a single file: eight tables, two generated files,
  one ledger, an id grammar with member and variant fragments; kept to one
  directory with one merge rule in one Go package with golden tests, no
  second plugin directory or generated cell table, and the axis table empty
  for every project that declares none.
- **`tradeoff_cell_table_size`** — instead of ~2,500 generated cell rows,
  `_scanned.yaml` carries 49 member rows with a `variants:` list of at most
  ten values; the price is that `scan` and `check` exec each runner's `list`
  and a matrix added to the manifests is invisible to `select` until the next
  `scan --apply`, which `check` reports as drift the same day. Enumerating
  at every `select` was rejected because it would put a build-adjacent exec
  on the hot path of every gate.
- **`tradeoff_member_annotation_drift`** — a member's annotation is keyed by
  name and the runner's `list` keys the same member by another artifact; a
  rename on one side orphans the other; mitigated by `UNANNOTATED_MEMBER` and
  `DEAD_MEMBER`, both fail-closed, by `scan --apply` refusing rather than
  guessing, and by thinking_app's own manifest / `@Test` drift loop.
- **`tradeoff_static_scanner_overselection`** — static scanners overselect on
  hot files and cannot see runtime coupling; a shared component fans out to
  most screens on every matrix, which is the correct answer and close to a
  full run; kind ranking, the suite budget and `--budget-s` trim scoped rows
  first, the `android-res` scanner narrows a catalog edit, a project scanner
  plugin can narrow a hot resource file, and hunk-level attribution is the
  later tool.
- **`tradeoff_area_glob_coarseness`** — area and scope globs are coarser
  than edges: a broad area over-selects on every edit inside it and a scoped
  test depending on a file outside its scope is under-selected until a full
  run scores it; mitigated by the suite budget with explicit `DEFERRED`
  lines, budget-exempt triggers and `reads` globs, and the missing-trigger /
  area-too-narrow attribution path.
- **`tradeoff_broad_scope_coarseness`** — a test scoped to a large area is
  selected for any change inside it; mitigated by ranking last at its
  distance, running only after a green unit wave, being cut first by the
  budget with the cut printed, and the cost visible in `schedule`.
- **`tradeoff_axis_declaration_burden`** — axes are a third authoring
  surface and a wrong declaration gives confidently wrong selection;
  thinking_app must declare ten matrix values with three facets, four locale
  source-glob sets, one `values/**` rule, one runner script and one
  `testmap:axis` line per non-capturing coordinate test; mitigated by
  membership being declarative and checkable (`DEAD_AXIS_SOURCE`,
  `UNKNOWN_VARIANT`, `UNCOVERED_VALUE`, `axes --explain`) and by an
  undeclared source reaching every variant.
- **`tradeoff_axis_projection_coarseness`** — the default axis join is
  file-level: a one-key edit to `values-ru/strings.xml` selects every
  enrolled screen on both ru matrices (~65 variants) rather than the screens
  naming that key; mitigated by the opt-in `android-res` symbol scanner,
  `select --format tokens` feeding the project's own preview loop, and the
  group-costed budget.
- **`tradeoff_intersection_can_underselect`** — an axis-source hit is
  sharper than a file edge and can miss a coupling a plain `covers` edge
  would have caught (a font family assigned to the wrong locale's glob);
  narrowed structurally: under-selection needs an explicit, reviewable wrong
  glob, never an omission; `score` raises missing-axis-source; observed
  sources only widen; every variant row prints the facet value that placed
  it.
- **`tradeoff_whole_run_filter_soundness`** — where a runner's filter
  restricts a whole run (Gradle `--tests`), every class not selected is
  silently not run, so a narrow selection is only as sound as the test-side
  closure, the `reads` globs and the opaque contract; mitigated by `list`
  enumerating the whole universe, the test-dep closure over abstract bases
  and helpers, `testmap:reads` on tree-scanning helpers, `ESCALATE` on opaque
  files, red-proof fixtures per branch, `readiness` gating the policy flip on
  scored history, and the full suite staying the completion gate until then.
- **`tradeoff_resource_declaration_completeness`** — declared resources are
  only as complete as the declarations; an undeclared interference is
  invisible until a full run or a probe finds it; serial-by-default at
  bootstrap means declarations are reviewed in the schedule report before
  concurrency is trusted.

### Freshness and evidence

- **`tradeoff_stamp_churn`** — confirming stamps rewrites test files (a
  source named by 72 tests could yield a 72-file diff; `EVIDENCED` needs no
  rewrite, `--confirm-source` is one commit, member blocks keep a screen's
  stamps in one file, variants carry no stamp); onboarding adds the largest
  rewrite of all — level 1 on aitasks touches ~720 test files with one to
  eight comment lines each — mitigated by seeds selecting without any
  rewrite, adoption batched per class or per area into `chore: Onboard
  testmap — adopt <class|area> (t<id>)` commits that add comment lines only
  (`git blame -w` and every runner ignore them), `ADOPT_REFUSED:dirty-foreign`,
  the reviewed `(t<id>)` commit, and the in-gate path that adopts a file's
  seeds only when a task already has it open.
- **`tradeoff_flaky_pass_anchors`** — a flaky pass anchors evidence as surely
  as a real one; mitigated by per-run status in the ledger exposing a flake
  rate per id, and an id above `flake_threshold` being excluded from the
  evidence join.
- **`tradeoff_evidence_requires_reachable_history`** — the evidence join can
  only suppress a `STALE` row when the anchoring commit is reachable, so a
  depth-1 clone sees the precise digest verdict with no self-healing; the
  safe direction, and why `stale --strict` fails only on `STALE_PATH`; a
  repo-wide `stale --all --strict` job should run on a full clone.
- **`tradeoff_autonomous_confirmation_weak`** *(rewritten)* — autonomous
  acts on the map are weaker than review, and this design has four of them:
  `--confirm-evidenced` (a green run on every reached variant whose tree
  held the current bytes re-stamps an edge, `confirmed_by: <run_id>`,
  re-opened by a later miss), `adopt --auto` over measured origins (a
  language rule or a coverage run — a measurement, not a judgement),
  `adopt --auto` over `verifies` verdicts (an agent's reading, anchored to
  an assertion line the engine checked, provenance `adopted(…+agent:review)`,
  calibrated by `REVIEW_AGREEMENT` and demoted below the threshold) and the
  `auto` policy flip (the engine's, bounded by the cadence full run). What
  no autonomous path may do: confirm a `STALE` row, reject a seed, change a
  kind, or make the completion gate run less without a scheduled full run
  behind it. The residual risk moved from "reviewer fatigue on a thousand
  seeds" to "a wrong agent verdict stamps an edge that over-claims, or a
  wrong policy flip lets a miss survive until the next cadence run" — both
  visible in provenance and both bounded by knobs the config exposes
  (`agent_review.confidence`, `completion.auto`).
- **`tradeoff_attribution_risk`** — an agent that edits sources without
  attributing produces a map that looks current and is not; narrowed three
  ways: such a source shows as `STALE` in the next task and as a stale mark
  on every selection; the Step-7 run reports `UNMAPPED_SOURCE:<path>` at the
  moment the source is introduced and the pre-review procedure offers
  annotate / propose / waiver right there; and under a full completion policy
  every miss is counted by the automatic score within one task. What still
  escapes is a coupling to a source that already has some edge, which only
  `score` can find.
- **`tradeoff_batch_misreport_risk`** — a batch runner that misreports
  per-unit results corrupts attribution, cost and evidence (a false pass
  could manufacture an `EVIDENCED` row); the JUnit inversion and the
  method-granularity zero-match trap are two places to misreport; mitigated
  by `units_expected` / `units_reported` reconciliation per id, a row
  inverting to no registered id and zero-reported-some-expected both being
  mechanism failures, and no line from an invocation with a cause anchoring.

### Seeding, adoption and onboarding

- **`tradeoff_seed_noise`** *(rewritten)* — heuristic seeds are wrong in
  both directions (a convention pairs a homonym, an import names a helper,
  co-change ties every file of a wide task to every test of it —
  thinking_app: 7.2 main files per co-changing commit); mitigated by seeds
  selecting and never claiming, confidence ordering review rather than
  gating it, the 0.60 co-change cap and `min_cochange 2`, direct imports
  only, helpers separated before scoring, evidence beside every row,
  rejection memory, and the suite budget and `--format tokens` where
  over-selection is expensive; the reviewer fatigue that remained on a
  1,000-seed queue is now the review pass's job — a noisy seed gets a
  `drives` or `unclear` verdict and is parked, still selecting, and a person
  sees `REVIEW_PARKED:<n>` instead of a thousand rows; what remains is that
  parked rows still over-select until a person rejects them.
- **`tradeoff_seed_precision`** *(rewritten)* — an adopted `covers` edge is
  a machine claim in a human annotation's clothes: the closure says the test
  *executes* the script, not that it *verifies* it, and a test that drives
  three scripts to set up one would adopt edges to all three under a
  class-level yes; this is exactly the gap the review pass closes — the
  reader marks the two set-up scripts `drives` and only the third
  `verifies`, and `--auto` adopts one edge, not three; narrowed further by
  the `adopted.yaml` provenance and `by` shown in `stale` / `explain`,
  `ADOPTED_UNREVIEWED` in `readiness`, the over-claim direction only
  over-selecting, the 0.85 threshold keeping convention-only, prose-only and
  co-change-only edges out of a person's class adoption, three samples per
  class, and the seeded state existing at all for a project that wants no
  machine claims; a wrong `verifies` reproduces the original over-claim for
  one pair, with `agent:review` in its provenance; a coupling the closure
  does not contain is caught by the author's annotation when the task that
  creates it runs the pre-review procedure, and otherwise only by a full
  run's score.
- **`tradeoff_two_edge_states_during_adoption`** — until both queues are
  empty a repo has three provenances of edge (seeded, adopted, reviewed) a
  reader must keep apart; mitigated by the origin or `adopted(...)` on every
  row, `SEEDED:` / `ADOPTED:` on `check` and `stale --all`,
  `ADOPTED_UNREVIEWED` in `readiness`, `onboard status` as the one place the
  ratios live, and the rule that no seed ever changes a freshness verdict;
  the cost is real: `--strict` cannot be enabled while `UNMAPPED_SOURCE` rows
  are only seed-covered, so a repo that never adopts stays at bootstrap
  enforcement indefinitely, which `onboard status` makes visible; the review pass means
  "never adopts" is now a choice (`agent_review.confidence: 0.60` and no
  `--auto`) rather than the default outcome of nobody having time.
- **`tradeoff_agent_judgement_unmeasured`** *(new)* — `agent:review`'s
  0.90 is a provisional number: no measurement of an agent's *verifies*
  precision exists on day one, and a confident wrong verdict stamps a
  claim in the map with a rationale that reads well; narrowed by the
  assertion-line anchor the engine checks (a verdict must point at a real
  line naming the source), by the verdict attaching only to an existing
  seed (the agent corroborates, never invents a pair), by
  `REVIEW_AGREEMENT` against every human per-row decision with automatic
  demotion to corroboration-only under `min_agreement` over
  `calibration_min` pairs, by `by: auto:review` in every provenance row, by
  a wrong verdict over-claiming (over-selects, then is confirmed or
  retargeted at `testmap_fresh` like any adopted edge) and never
  under-selecting, and by the per-project `agent_review.confidence` knob;
  what remains is the first thirty pairs, during which the number is trust.
- **`tradeoff_cadence_window_misses`** *(new)* — under `auto` a coupling no
  edge, seed, rule or verdict knows lets a task land with an affected test
  unrun until the next cadence full run; the window is `full_every_n − 1`
  tasks or `full_after_days`, and the miss is then scored against every
  prediction in the window and attributed by change surface and history
  rather than pinned to the task that happened to trigger the full run;
  narrowed by the three cadence rules being required (`cadence_declared`),
  by `full_when_selection_over` running full whenever the saving is small,
  by one miss over `max_false_negatives` demoting to full, by `--howto`
  and `readiness` printing the window, and by `mode: full` remaining the
  one-line opt-out; the cost is real and per-project — the config exposes
  it rather than the design hiding it.
- **`tradeoff_review_token_cost`** *(new)* — the review pass is paid in
  agent tokens, not engine time: ~2 k input tokens per pair, ~1.5 M for
  aitasks' 700 heuristic pairs, more for thinking_app's Kotlin excerpts, and
  a re-review whenever a test's bytes change; crewed review pays print-mode
  rates on top; mitigated by the `reviews[]` memo (a pair is read once per
  test blob), batching by test file so one excerpt serves several pairs,
  `--class` limiting a pass to the origins worth reading (`static:*` first,
  `convention` only when nothing else corroborates), measured origins
  needing no reading at all, the in-gate path reviewing only touched files,
  and the crew form being an explicit opt-in a person starts.
- **`tradeoff_bulk_confirmation_granularity`** *(rewritten)* — a person's
  class adoption (398 static edges in one answer) trades review depth for
  feasibility; the review pass restores per-pair depth without a person
  (every `--auto` adoption of a heuristic class is per pair, by verdict,
  with a rationale and an assertion line on the row), and the person's
  class-level yes remains for what the pass parked; mitigated by the
  three-sample display, `review a sample` drawing ten random members with
  their signals and verdicts, `--accept-min`, `--scope` onboarding one area
  per task, the `adopted.yaml` provenance and `by` so nothing pretends to
  be reviewed by a person, the per-row path for anyone who wants depth,
  autonomous adoption limited to measured origins, verdicts and the author's
  surface, and kind changes confirmed individually by a person because a
  wrong kind changes staleness semantics.
- **`tradeoff_accept_rewrites_history`** — adoption inserts comment lines
  into hundreds of test files, so `git blame` on any test header points at
  the adoption commit and a concurrent task editing the same file hits a
  header conflict; mitigated by fixed insertion positions, batch commits
  named for what they are, the in-task incremental path,
  `ADOPT_REFUSED:dirty-foreign` and `REWRITE_CONFLICT`; a project that wants
  no comment churn keeps seeds unadopted and accepts selection-only
  enforcement, reported as such.
- **`tradeoff_onboarding_partial_coverage`** *(rewritten)* — onboarding
  cannot map what no origin reaches (thinking_app's same-package tests,
  fixture-driven tests, any source with no static, convention, plan, prose,
  co-change or coverage relation), so a freshly onboarded repo has
  `UNMAPPED_SOURCE` rows and area-only coverage for a share of its tree;
  mitigated by the waivers phase (rules for hot directories, expiring
  waivers for the rest) so `check` can be enabled non-strict, opt-in
  per-unit coverage (now auto-adoptable, so turning it on maps and claims
  in one step), the authoring agent stamping every coupling a task creates
  from now on, and the full gate staying the completion policy until
  admissible; the honest reading of `onboard status` after one headless
  session is "selecting on most tests, claiming on the measured and the
  verified, the rest parked", treated as a state, not a failure — and the
  backlog no origin reaches is still a person's or the next task's.
- **`tradeoff_fail_closed_bootstrap_cost`** — fail-closed enforcement means
  each repo needs a waiver pass before `testmap_check` can be enabled, a
  first green full run before `require_stamp` and `--strict`, a green runner
  list before structural rules can fail, and `min_scored_full_runs` before
  the policy may flip; narrowed by making the bootstrap one aitask per level
  that the skill creates and runs — `detect` and `seed` read-only until
  `--write` / `--apply`, level 0 writing only registry files and seeds, the
  seeder replacing most of the hand waiver pass (88 % of bash and 80 % of
  Python tests on aitasks seed at least one edge), the level-0 task's own
  `tests_pass` being the first anchoring full run, `bootstrap_until` set to
  +90 days, adoption incremental by class, area or in-gate, and `readiness`
  printing `LEVEL` / `NEXT`; and by level 1 no longer waiting for a person:
  the review pass and `adopt --auto` stamp the measured and the verified
  edges in the same headless task that ran level 0, and `finish --auto`
  closes enforcement with the parked rows still selecting; what remains: a
  headless repo stops at level 1 (kinds are a person's), the review pass is
  a long session, and the judgement in classify is one no reader may take
  alone.
- **`tradeoff_verify_build_wired_suites`** — a suite wired as `verify_build`
  (thinking_backend's `run_script_tests.sh`, which also enforces a shellcheck
  baseline) cannot be onboarded mechanically: moving it would drop the lint
  half from `build_verified`, leaving it would run the suite twice at
  completion; `detect` reports `SUITE_CANDIDATE:verify_build` and the skill
  asks (keep and add `test_command: ./ait test`; or split the script),
  defaulting to keep and recording the answer; headless keeps.

### Run surface and workflow

- **`tradeoff_dispatcher_verb_added`** — `ait test` is a new top-level verb
  beside `ait testmap`, two surfaces for one engine; justified by the
  extension-points rule (a human plausibly types `ait test`, and the seed
  instruction needs one memorable verb), kept thin (mode / task / intake /
  policy / fallback / advisory only), with `ait testmap` staying the
  maintainer surface; removing a verb later is a breaking change, so
  `--howto` documents `ait test` as the stable one.
- **`tradeoff_generated_brief_limits`** — a brief computed from the registry
  cannot say what a project's people know about when a narrow run is
  acceptable or why RTL is the design gate; mitigated by `config.yaml docs:`
  (named paths one hop away) and `notes:` (≤ 10 verbatim lines for the rules
  that must not be one hop away), and by the seeded instructions telling
  agents to read `--howto` before touching a test tool; `notes:` is still
  prose an agent may misread, which the gates and the full completion policy
  backstop.
- **`tradeoff_workflow_surface_growth`** — the seam adds one task-workflow
  procedure file, one profile key, one dispatcher verb, one skill-invoked
  script with a second mode (five allowlist touchpoints pinned by
  `tests/test_touchpoint_count_contract.sh`), a Step-7 render change across
  every profile × agent golden, one build-verification branch, two
  `aitask-qa` edits, a seed-instructions edit and a profile-aware skill with
  two wrapper surfaces; mitigated by all of it degrading to a printed skip
  where the engine is absent (no environment conditionals), by the advisory
  mode reusing the exact `VERDICT:` / `REASON:` contract and capture form the
  build-verification path already teaches, by there being one script rather
  than two, and by `aitask_skill_verify.sh` plus the goldens catching a
  drifted render before commit.
<!-- /section: tradeoffs -->

<!-- section: open_questions -->
## Open Questions

1. Should `affected_tests` default to `run` or `show` when a repository's
   affected run is expensive (thinking_app: one Gradle boot under the
   heavy-run lock, ~40 s minimum)? Proposed: `run`, because the scheduler
   defers on a refused slot and the estimate is printed first; a project may
   set `show` in its profile.
2. Should a person's `onboard adopt --class static:invocation` skip the
   ten-sample review once the review pass has run over the class — the
   verdicts are per pair and the sample would re-read what the agent read?
   Proposed: yes when every pair of the class carries a verdict and
   `REVIEW_AGREEMENT` is at or above `min_agreement`; otherwise the sample
   stays.
3. Should `completion.on_empty_selection` default to `full` rather than `skip`
   once `require_stamp: true`? An empty selection with a non-empty change
   surface is a strong "the map does not know this file" signal. Proposed:
   `skip` during bootstrap, `full` after `finish`; `readiness` prints the
   recommendation.
4. `AIT_GATE_TASK_ID` is visible to any other `test_command` — should the
   export be limited to commands matching `./ait test*`? Proposed: no; a
   variable a command ignores is harmless and a project wrapper may want it.
5. Where does the `--policy selected` approval statement live for a project
   without a design record like thinking_app's
   `change-aware-verification.md#what-this-cannot-do`? Proposed: the skill
   writes `aitestmap/ADMISSION.md` from the readiness output and the user's
   statement, and `approved_by.statement` points at it.
6. `aitask_lock.sh --list-mine` is a new verb on an existing script; is an
   `ait ls`-based query (`status Implementing`, `assigned_to` = me) preferable
   so no lock-format knowledge leaves the lock script? Either satisfies the
   resolution rule; the lock is proposed because it is host-scoped.
7. Should `onboard finish` refuse while any `pending` seeds remain, or accept
   a user-set threshold? Proposed: threshold, default 0, printed in `status`.
8. Should the `full` suite wrapper's `children:` post-processor for bash-file
   tests infer per-file results from the runner's own per-file exit or require
   junit-style output? Proposed: the per-file exit; a monolithic script gets
   suite-level evidence only.
9. Should `readiness` count only scored predictions whose selection was
   non-trivial (at least one unit) toward `min_scored_full_runs`? A
   `no_selection` advisory run scored against a green full run says nothing.
   Proposed: yes.
10. Should an `adopted.yaml` row age out — a class-adopted edge that has been
    `EVIDENCED` by N scored full runs without a miss becoming reviewed
    automatically? Proposed: no in v1; evidence removes nags, it does not
    review claims, and `ADOPTED_UNREVIEWED` is meant to be read — the same
    answer for `by: auto:review` and `by: author` rows.
11. The engine-level questions recorded before the adoption layer existed
    (scanner plugin contracts, symbol-level attribution, the default-flip of
    the home migration) remain open and are not restated here; the one about
    aitasks_mobile's source sets is answered: they are runner / kind
    distinctions, not an axis.
12. Should `detect --write` default `completion.mode` to `auto` or to
    `full` with `auto` opt-in? Proposed: `auto`, because until `ADMISSIBLE`
    it is `full` byte for byte and the cadence is printed in the level
    proposal; the counter-argument is that a project should choose to let
    its gate shrink, not discover that it did.
13. Should a `drives` verdict ever remove selection — say after N cadence
    full runs in which the parked test never failed for a change to that
    source? Proposed: no; a person rejects, and `REVIEW_PARKED` is the list
    they read.
14. What are the right cadence defaults per repository shape? `5 / 0.6 / 7`
    is a guess for aitasks (full ≈ 111 s); thinking_app's `verify-active`
    (p95 1180 s) may want `10 / 0.5 / 14`. Proposed: `detect --write` scales
    `full_every_n` from the first full run's p95 after `full_run`, printed.
15. Where does calibration come from in a purely headless project that
    never adopts per row? Proposed: nowhere — `REVIEW_AGREEMENT:none` is
    printed, the provisional 0.90 stands, and `agent_review.confidence` is
    the project's knob; a second, cheaper cross-check (a different model
    re-reading a random 5 %) is a follow-up, not v1.
16. Should the review batch carry the source's full text under some size
    rather than header and symbols? Proposed: header and symbols by
    default, `--source-lines <n>` for a project whose sources are small.
<!-- /section: open_questions -->