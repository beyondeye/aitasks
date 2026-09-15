--- NODE_YAML_START ---
node_id: n000_init
parents: []
description: "A source-to-tests map with graded selection, a standard runner contract, and declared concurrency for aitasks."
proposal_file: br_proposals/n000_init.md
created_at: "2026-09-15 09:27"
created_by_group: bootstrap
reference_files:
  - "/home/ddt/Work/aitasks/aiwork/t1812_selective_testing_proposal.md"
  - "aitasks/t1812_selective_testing_source_to_tests_map_graded_selection_runne.md"
requirements_generic_across_projects: "A framework feature, generic across projects (aitasks, thinking_app, thinking_backend, aitasks_go, aitasks_mobile), that maintains a relation between source files and test units"
requirements_reason_per_selected_test: "Translates a task's change set into the set of tests that must run, with a reason on every line"
requirements_standard_runner_contract: "Runs selected tests through project-defined runners under a standard contract (describe/list/run verbs)"
requirements_cost_tracking: "Tracks cost per test unit, keyed by host class, using Welford's online update (n, mean, standard deviation, p95, last)"
requirements_feedback_loop: "Learns from failures the map did not predict, via a score/attribute feedback loop"
requirements_gate_enforcement: "Enforced by gates so the map cannot rot silently: a selection gate and a check gate, fail-closed with explicit waivers"
requirements_agent_skill: "Agent skills teach agents how to keep the map current as they write code and tests: annotate, attribute, waive"
assumption_static_granularity_v1: "Static file-level facts are enough for v1 - no scanner in use today produces symbol-level coverage; the schema keeps an optional symbols slot on an edge so a hunk-level matcher can be added later"
assumption_change_surface_is_intake: "The change-surface script's attribution (aitask_change_surface.sh) is the right intake; selection never reads a raw git diff, and an UNKNOWN path refuses selection"
assumption_existing_locks_wrappable: "Existing project locks and allocators (thinking_app's heavy-run lock, emulator allocation) can be wrapped as resources without changing them"
assumption_gate_exit_contract_reused: "The gate verifier's exit-contract mapping (gate_command_exit_contract) is reused unchanged for the new runner exit codes"
assumption_batch_per_unit_timing_reportable: "Runners can report per-unit timing inside a batch from their tool's own report format (JUnit XML, go test -json, pytest junitxml)"
assumption_target_repos_accept_aitestmap_root: "Every target repo will accept a root aitestmap/ directory and runner scripts committed into its code tree"
assumption_testmap_token_no_collision: "The annotation token 'testmap:' does not collide with existing prose comments in any target repo"
component_registry_loader: "Registry loader and writer: merges aitestmap/registry/*.yaml, enforces owns: routing and the check rules"
component_annotation_scanner: "Annotation scanner: per file type, produces _scanned.yaml from testmap:covers/kind/runner/needs/batch comment lines"
component_dependency_scanners: "Dependency scanners: per language, plugin slot, produce reverse-dependency facts cached by content digest"
component_selector: "Selector: the graded walk, rules engine (select/implies/escalate), change-set intake from the change-surface script, prediction record writer"
component_runner_contract: "Runner contract and runner repository: describe/list/run verbs, manifest and results.jsonl formats, exit contract 0/1/2/75, bindings, per-test overrides"
component_scheduler_resources: "Scheduler and resources: scopes (host/worktree/run), kinds (mutex/semaphore/admission/allocator), acquisition order, batching, the schedule report"
component_cost_ledger: "Cost ledger: local ledger under the XDG cache, committed per-host-class summaries, costs --update fold step"
component_feedback_tools: "Feedback tools: score splits a full run's failures into caught/missed against a prediction record; attribute records a missing-edge/test-wrong/source-wrong decision"
component_gates: "Gates: two machine gates registered in gates.yaml - a selection-run gate and a check gate"
component_skill: "Skill: teaches agents the annotation, attribution and waiver obligations"
component_reference_runners: "Reference runners: bash-file, pytest, go-test, gradle-class, a whole-suite wrapper, a device runner using an allocator"
tradeoff_computed_vs_prose: "Advantage: selection is computed, explained and scored rather than remembered; blast radius becomes data instead of prose"
tradeoff_registry_directory_complexity: "Disadvantage: a merged registry directory needs more CLI logic than a single file would"
tradeoff_fail_closed_bootstrap_cost: "Disadvantage: fail-closed enforcement means bootstrapping each repo requires an explicit waiver pass before the gate can be enabled"
tradeoff_static_scanner_overselection: "Disadvantage: static scanners overselect on hot files and cannot see runtime coupling"
tradeoff_resource_declaration_completeness: "Risk: declared resources are only as complete as the declarations; an undeclared interference is invisible until a full run or a probe finds it"
tradeoff_attribution_risk: "Risk: an agent that edits sources without attributing produces a map that looks current and is not, which only a full-run score can catch"
tradeoff_batch_misreport_risk: "Risk: a batch runner that misreports per-unit results corrupts both attribution and cost; a wrongly scoped resource either serialises everything or protects nothing"
--- NODE_YAML_END ---
--- PROPOSAL_START ---
<!-- section: overview [dimensions: requirements_*] -->
## Overview

Every target project runs either its whole test suite per task or nothing.
This repo has about 415 shell test files and 335 python test files under
`tests/` and sets `test_command: null`, so no test runs as a gate.
thinking_app has one heavy gate (`screenshot-tests.sh verify-active`, about 8
minutes, behind a host-wide lock with memory admission) and a narrower
`unit-tests --tests <fqn>` that needs the caller to already know the class
names. thinking_backend runs one monolithic script as `verify_build`.
aitasks_go runs `go test ./...`. aitasks_mobile runs `./gradlew check`.

The blast-radius knowledge that would let a task run only the tests its
change can affect exists today only as prose (thinking_app's CLAUDE.md: "a
localized screen change may use preview or the RTL tier; a shared component
or tooling change must run the full gate") or as naming conventions
(`tests/test_gate_pass.sh` tests `aitask_gate_pass.sh`). Agents cannot
compute it, and nothing tracks when it goes stale.

The goal is a framework feature, generic across projects, that maintains a
relation between source files and test units, translates a task's change set
into the set of tests that must run with a reason on every line, runs them
through project-defined runners under a standard contract, tracks cost per
test unit, learns from failures the map did not predict, and is enforced by
gates so the map cannot rot silently. Agent skills teach agents how to keep
the map current as they write code and tests.
<!-- /section: overview -->

<!-- section: target_projects -->
## Target Projects and What Each Demands of the Design

| repo | test units | how they run today | constraint the design must carry |
|---|---|---|---|
| aitasks | 415 sh files, 335 py files | `bash tests/test_x.sh`; `tests/run_all_python_tests.sh` with an xdist lane | sh tests own the real git index and must not overlap the py suite |
| thinking_app | Gradle test classes, per screenshot matrix | `screenshot-tests.sh verify-active` or `unit-tests --tests <fqn>` | heavy-run lock, admission exit 75, protected screenshot baselines, escalation rules written in prose |
| thinking_backend | about 40 sh and py files under `scripts/tests/` | one monolithic `run_script_tests.sh` wired as `verify_build` | the runner also owns a shellcheck baseline |
| aitasks_go | about 20 `_test.go` files across widget packages | `go test ./...` | the package is Go's natural unit, not the file |
| aitasks_mobile | KMP commonTest, androidHostTest, androidDeviceTest | `./gradlew check` | device tests need an emulator; the module graph decides blast radius |

Measured on the aitasks repo on 2026-09-15: of 145 scripts in
`.aitask-scripts/`, 123 are named by at least one test file; of 121 lib
files, 110 are. `aitask_update.sh` is named by 72 test files. So a static
scan can bootstrap most direct edges, and fan-out is skewed enough that a
hand-typed per-file tier list would be wrong from day one.
<!-- /section: target_projects -->

<!-- section: decisions -->
## Decisions Already Taken (Decided)

- **Primary targets**: aitasks, thinking_app, thinking_backend, aitasks_go, aitasks_mobile.
- **Source of truth for direct edges**: a central registry, updated by a CLI that scans in-test annotations. Annotations are the input; the registry is the truth.
- **Where the map lives**: in the code tree, versioned with the code, so a test rename and its map update land in one commit. Not on the task-data branch.
- **Registry layout**: a directory, not one file. Every file under it is merged. This costs CLI complexity and buys independent management of associations per area.
- **Selection is mechanical**: no hand-typed basic/deep/deepest labels per file. The translation from change set to test set is the main added value of the system; profile-named tiers that collapse it into three buckets would throw that value away.
- **Derivation**: static scanners plus manual updates through agent skills, for example when a test failure is fixed by editing a source file the map had no edge to.
- **Enforcement**: fail-closed, with explicit waivers.
- **Full run**: build the machinery so the whole suite can be run by CI or on demand, producing the same evidence format as a selected run.
- **Runners**: a runner template per test kind plus the option to assign a runner to an individual test file. A repository maps runner name to runner script. The runner input and output contract is a standard. Designing the runner and how it is flexibly assigned to test files is one of the most important design points.
- **Cost**: track cost per test file with count, mean, standard deviation and similar, keyed by host class.
- **Go granularity**: per test file, with the runner deriving a `-run` regex from the `func Test` names in the file. Shared package setup counts against every file in the package.
- **Concurrency**: abstracting which test sets may run concurrently, and the locks between them, is a main added value and must be designed and characterised, not left as a serial group flag.
<!-- /section: decisions -->

<!-- section: vocabulary -->
## Vocabulary

- **Source unit**: a path in the code tree.
- **Test unit**: a path the registry keys on, plus a kind (unit, integration, e2e, device) and a runner. The runner owns the translation from path to what it actually executes (a bash file, a pytest module, a Go package with a `-run` regex, a Gradle class FQN, or a whole suite).
- **Edge**: source unit to test unit, with a provenance (annotation, declared, observed) and a scope (file or area).
- **Rule**: a blast-radius declaration matching changed paths and producing an effect (select tests, imply a virtual change, escalate to everything).
- **Distance**: the number of hops from a changed path to a test unit in the walk described below. Every selected unit carries its minimal distance and the path that produced it.
- **Prediction record**: what a selection wrote down, so a later full run can score it.
- **Resource**: a named lock-like thing with a scope and a capacity that a test unit needs while it runs.
<!-- /section: vocabulary -->

<!-- section: registry_directory [dimensions: component_registry_loader] -->
## Registry Directory

Proposed root: `aitestmap/`, in the `ai*` family the framework already uses (`aitasks/`, `aiplans/`, `aidocs/`, `aiwork/`).

```
aitestmap/
  runners.yaml          runner repository and path-to-runner bindings
  resources.yaml        named resources for concurrency
  registry/
    _scanned.yaml       written only by `scan --apply` from annotations; never hand-edited
    observed.yaml       written only by `attribute`
    gates.yaml          hand-written edges, rules and waivers for one area; declares `owns:` globs
    ui_components.yaml  another area file
  costs/
    <hostclass>.yaml    committed cost summaries per host class
  runners/
    bash_file.sh, pytest.sh, go_test.sh, ...   project-local runner scripts
```

Merge rule: every file under `registry/` contributes rows to the same three
tables (edges, rules, waivers). Write routing: `scan --apply` writes only
`_scanned.yaml`; `attribute` writes only `observed.yaml`; every hand-written
file declares `owns:` as a list of globs, a declared edge or rule for a path
outside the file's `owns` fails `check`, and `declare` picks its target file
by matching the path against `owns`. A duplicate edge across files is a
harmless union and is reported. Two rules with the same name, or a waiver for
a path that also has an edge, fail `check`.

Drift is fail-closed. A row with provenance `annotation` whose annotation is
gone makes `check` fail until `scan --apply` removes it or someone promotes
it to `declared`. A waiver past its `until` date fails the same way.

```yaml
# aitestmap/registry/gates.yaml
contract: 1
owns: [".aitask-scripts/aitask_gate*.sh", ".aitask-scripts/lib/gate_*.sh", "aitasks/metadata/gates.yaml"]
edges:
  - {test: tests/test_gate_orchestrator.sh, covers: [.aitask-scripts/lib/task_utils.sh], from: declared}
rules:
  - name: gates-area
    when: [".aitask-scripts/aitask_gate*.sh", "aitasks/metadata/gates.yaml"]
    select: ["tests/test_gate_*.sh"]
    distance: 2
waivers:
  - {path: .aitask-scripts/aitask_gate_log.sh, reason: "display-only; manual verification t1200", until: 2027-03-01}
```
<!-- /section: registry_directory -->

<!-- section: annotations [dimensions: component_annotation_scanner] -->
## Annotations in Test Files

The existing `# Covers:` lines in aitasks are sometimes prose ("Covers:
create/update/draft round-trip"), so the token must be namespaced. The
comment leader follows the file type (`#`, `//`, `--`).

```
# testmap:covers .aitask-scripts/aitask_gate_pass.sh
# testmap:covers .aitask-scripts/lib/gate_verifier_lib.sh
# testmap:kind unit            unit | integration | e2e | device
# testmap:runner bash-file     optional override of the binding
# testmap:needs git-index      optional resource
# testmap:batch no             optional: run in its own invocation
```

`scan` reads every test unit a runner's `list` verb reports, extracts these
lines, and rewrites `_scanned.yaml`. A test unit with no `testmap:covers` and
no declared edge fails `check`, which is how a new test file that nobody
registered is caught.
<!-- /section: annotations -->

<!-- section: runner_contract [dimensions: component_runner_contract] -->
## Runner Contract

The registry keys everything by path. The runner owns the translation to
whatever it executes and reports back per execution unit. That keeps the
registry uniform across the five repos while letting Go run packages and
Gradle run classes.

```yaml
# aitestmap/runners.yaml
runners:
  bash-file:     {exec: aitestmap/runners/bash_file.sh, unit: file,    batch: false, needs: [git-index]}
  pytest:        {exec: aitestmap/runners/pytest.sh,    unit: file,    batch: true,  needs: [git-index]}
  go-test:       {exec: aitestmap/runners/go_test.sh,   unit: file,    batch: true}
  gradle-class:  {exec: tools/verification/testmap_runner.sh, unit: class, batch: true, needs: [heavy-run]}
  verify-active: {exec: tools/verification/screenshot-tests.sh, unit: suite}
  device-test:   {exec: aitestmap/runners/gradle_device.sh, unit: class, needs: [emulator]}
bindings:        # first match wins; a per-test annotation beats all bindings; no match refuses
  - {glob: "tests/test_*.sh",             runner: bash-file}
  - {glob: "tests/test_*.py",             runner: pytest}
  - {glob: "**/*_test.go",                runner: go-test}
  - {glob: "**/src/androidDeviceTest/**", runner: device-test}
  - {glob: "**/src/*Test/**/*.kt",        runner: gradle-class}
```

Every runner speaks three verbs.

- `describe` prints its contract version, unit kind, batch flag, default resources, and fixed invocation overhead if known.
- `list` enumerates the test units it owns on disk. This is how `check` finds unregistered tests and how the full run enumerates everything.
- `run --manifest <file> --out <dir>` executes and writes results.

```json
// manifest
{"contract":1,"run_id":"r-20260915-143012-a1b2","task":"t1234","repo_root":"/path",
 "resources":{"emulator":{"serial":"emulator-5554"}},
 "units":[{"id":"tests/test_gate_pass.sh","timeout_s":300}]}

// <out>/results.jsonl: one line per execution unit, stamped with the run id
{"run_id":"r-...","id":"tests/test_gate_pass.sh","status":"pass","duration_ms":4120,"log":"logs/test_gate_pass.log"}

// <out>/runner.json: the invocation-level verdict
{"run_id":"r-...","status":"completed","exit":0,"cause":null,"units_expected":1,"units_reported":1,"overhead_ms":850}
```

Exit codes follow the contract thinking_app already uses and that the gate
verifier already maps through `gate_command_exit_contract`: 0 every unit
passed; 1 a unit failed or the mechanism broke, with `cause=` present only in
the mechanism case; 2 did not run for a self-clearing reason; 75 admission
refused.

Two consequences. Results are files stamped with the run id, so a stale
results directory can never satisfy a gate. `units_expected` against
`units_reported` catches a runner that silently dropped a unit, which is a
known failure mode of batched test runners.

Assignment resolution is deterministic and printable: an explicit
`testmap:runner` annotation in the test, else the first matching binding,
else refuse. `explain <test>` prints the chain.

Batching: one runner invocation carrying many units, against one invocation
per unit. Gradle pays a daemon start per invocation and pytest pays an
interpreter and import pass, so a batch of ten classes is far cheaper than
ten runs. The costs are that a hang in one unit can take the batch down,
that state can leak between units in one process, and that the batch holds
the union of its units' resources for its whole duration. Per-unit timing
inside a batch comes from the tool's own report (JUnit XML, `go test
-json`, pytest junitxml). A unit that needs isolation says `testmap:batch
no`.

Whole-suite runners with `unit: suite` take no selectors and are one unit
for cost and selection purposes. This is how an existing monolithic gate is
wrapped without rewriting it.
<!-- /section: runner_contract -->

<!-- section: selection [dimensions: component_selector] -->
## Selection: a Graded Walk, Not Tiers

The core is a graph walk that assigns every test unit a distance and a
cause.

- **Distance 0**: a changed test file itself; and, under escalation, everything.
- **Distance 1**: a unit with a direct edge from a changed source.
- **Distance 2**: a unit with a direct edge from a source that depends on a changed source, one hop through the scanned dependency graph. Distance 3 is two hops, and so on.
- **Rules inject at a declared distance**: `select` adds units at the rule's distance; `implies` adds a virtual change and the walk continues from it; `escalate` sets everything to distance 0.

The output of `select` is the whole ranked list with a reason per line.
Every cut is a knob applied afterwards: maximum distance, a time budget from
the cost stats, a kind filter, a resource filter. A gate profile may carry a
default knob and a project may name cuts, but the system never needs the
names.

```
tests/test_gate_pass.sh            d=1  edge(annotation)  .aitask-scripts/aitask_gate_pass.sh
tests/test_gate_orchestrator.sh    d=2  dep  lib/gate_verifier_lib.sh <- aitask_gate_pass.sh
tests/test_gate_ledger.sh          d=2  rule gates-area
LoginScreenRenderTest              d=2  dep  ui/components/PinField.kt <- LoginScreen.kt
```

Reverse dependencies come from per-language scanners: bash `source` lines
and sibling-script invocations, python imports, `go list -deps`, Kotlin
imports inside a module, the Gradle module graph across modules. Computed
at select time and cached by content digest. Project-specific scanners are
a plugin slot: a scanner that maps a changed `R.string` name to the Kotlin
files referencing it turns a `strings.xml` edit into a precise set of
screens instead of a full run.

The change set comes from `aitask_change_surface.sh list <task>`, which
attributes paths to a task with proven and declared signals and leaves the
rest UNKNOWN. An UNKNOWN path refuses selection with exit 1, so the set can
never silently widen or narrow. A changed source with no edge, no matching
rule, and no waiver refuses the same way.

For thinking_app this replaces the prose rule. With a Kotlin import
scanner, a change to a shared component selects every screen that imports
it at distance 2, and the render test classes annotated as covering those
screens come along. The escalation rule shrinks to what a scanner cannot
see: the verification tooling, the screenshot policy files, the catalogs a
scanner does not yet understand.
<!-- /section: selection -->

<!-- section: concurrency [dimensions: component_scheduler_resources] -->
## Concurrency as Declared Resources

A serial group is one special case. The general object is a named resource
with a scope and a capacity; every test unit carries the set of resources
it needs, taken from its runner's defaults, its annotations, or a rule.

```yaml
# aitestmap/resources.yaml
resources:
  git-index: {kind: mutex,     scope: worktree}
  heavy-run: {kind: admission, scope: host, command: tools/verification/heavy-run-lock.sh, acquired_by: runner}
  emulator:  {kind: allocator, scope: host,
              acquire: "tools/verification/emulator-allot.sh ensure --task {task}",
              release: "tools/verification/emulator-allot.sh release --task {task}"}
  cpu-heavy: {kind: semaphore, scope: host, capacity: 2}
```

- **Scope** says who contends. Host scope is a lock under the XDG runtime directory keyed by name, so two task worktrees contend correctly. Worktree scope is keyed by checkout path. Run scope only orders units inside one scheduler invocation.
- **Kind** says how it is held. A mutex or semaphore is a plain lock. An admission resource runs an existing project command and honours its exit contract, so an existing lock is wrapped, never reimplemented. An allocator returns a handle that the manifest hands to the runner.
- **Acquired by** matters when a project already locks inside its own tool. thinking_app's Gradle build acquires the heavy-run slot itself in a shared BuildService, so the scheduler must plan around it without taking it twice.
- The scheduler acquires in canonical name order to avoid deadlock, holds for the unit or for the batch, and releases on every exit path.

Characterising this is a command: `schedule` takes a selected set and
prints the waves, what each unit holds, the critical path, and the
estimated wall time against the serial sum. Its check half flags a unit
whose runner defaults to a resource it does not declare, and a heuristic
scan can flag a shell test that runs git in the repo root without creating
its own repository. Whether two undeclared units truly interfere cannot be
proven statically; a probe that runs a pair concurrently several times is
possible but expensive and is left out of the first design.
<!-- /section: concurrency -->

<!-- section: cost_model [dimensions: component_cost_ledger] -->
## Cost Model

Cost is tracked per execution unit with Welford's online update, so the
committed summary carries n, mean, standard deviation, p95 and last, keyed
by unit and host class. Host class is a configured value defaulting to the
hostname, because a dev box and CI will not agree on durations. Every
result line updates a local ledger under the XDG cache; `costs --update`
folds the ledger into the committed summary, so `select` can print an
estimate on a fresh clone. The estimate for a selection is the sum of unit
times plus one recorded overhead per runner invocation.
<!-- /section: cost_model -->

<!-- section: feedback_loop [dimensions: component_feedback_tools] -->
## Feedback Loop

`select` writes a prediction record: task, knobs, change set, selected
units with distances, escalations fired, estimated seconds against the
full suite. `score` takes that record plus a full run's results directory
and splits failures into caught and missed. Each miss becomes a proposed
observed edge that `attribute` accepts with a decision of missing-edge,
test-wrong or source-wrong, recording the task and run id as evidence.

The rule for agents is the manual half: when a failing test is fixed by
editing a source it had no edge to, attribution must happen before the
gate. When a source file is added, it must be given an edge, a rule, or a
waiver. When a test is written, it must annotate what it covers.
<!-- /section: feedback_loop -->

<!-- section: gates_and_cli [dimensions: component_gates] -->
## Gates and CLI Surface

- A machine gate runs `select` for the task under the profile's default knobs and executes the result through the runners, mapping the exit contract as the existing `tests_pass` verifier does.
- A second machine gate runs `check`: every changed source has an edge, a rule, or a waiver; every test unit on disk is registered; no scanned row has lost its annotation; no waiver has expired; every rule name is unique; the merged registry parses.
- The full run is the same machinery with every unit selected, invoked by CI or by hand, writing the same evidence.

CLI shape, all batch-safe with structured output lines and the shared exit
contract: `ait testmap scan | check | select | run | schedule | score |
attribute | declare | explain | costs`.
<!-- /section: gates_and_cli -->

<!-- section: components [dimensions: component_*] -->
## Components

- Registry loader and writer: merges `aitestmap/registry/*.yaml`, enforces `owns:` routing and the check rules.
- Annotation scanner: per file type, produces `_scanned.yaml`.
- Dependency scanners: per language, plugin slot, produce reverse-dependency facts cached by digest.
- Selector: the graded walk, rules engine, change-set intake from the change-surface script, prediction record writer.
- Runner contract and runner repository: verbs, manifest and results formats, exit contract, bindings, per-test overrides.
- Scheduler and resources: scopes, kinds, acquisition, batching, the `schedule` report.
- Cost ledger: local ledger, committed summaries, host classes.
- Feedback tools: `score` and `attribute`.
- Gates: two machine gates registered in `gates.yaml`.
- Skill: teaches agents the annotation, attribution and waiver obligations.
- Reference runners: bash-file, pytest, go-test, gradle-class, a whole-suite wrapper, a device runner using an allocator.
<!-- /section: components -->

<!-- section: assumptions [dimensions: assumption_*] -->
## Assumptions

- Static file-level facts are enough for v1. No scanner we have produces symbol-level coverage; the schema keeps an optional `symbols` slot on an edge so a hunk-level matcher can be added later.
- The change-surface script's attribution is the right intake; selection never reads a raw `git diff`.
- Existing project locks and allocators can be wrapped as resources without changing them.
- The gate verifier's exit-contract mapping is reused unchanged.
- Runners can report per-unit timing inside a batch from their tool's own report format.
- Every target repo will accept a root `aitestmap/` directory and runner scripts in its code tree.
- The annotation token `testmap:` does not collide with existing prose in any target repo.
<!-- /section: assumptions -->

<!-- section: tradeoffs [dimensions: tradeoff_*] -->
## Tradeoffs

Advantages: selection is computed, explained and scored rather than
remembered; blast radius becomes data instead of prose; fail-closed checks
make the map's rot visible; the runner contract lets five very different
repos share one selector, one scheduler and one cost model; wrapping
existing locks and gates avoids rewriting proven tooling.

Disadvantages: a merged registry directory needs more CLI logic than one
file; fail-closed enforcement means bootstrapping each repo requires an
explicit waiver pass before the gate can be enabled; static scanners
overselect on hot files and cannot see runtime coupling; declared resources
are only as complete as the declarations, and an undeclared interference is
invisible until a full run or a probe finds it.

Risks: an agent that edits sources without attributing produces a map that
looks current and is not, which only `score` on a full run can catch; a
batch runner that misreports per-unit results corrupts both attribution
and cost; a wrongly scoped resource either serialises everything or
protects nothing.
<!-- /section: tradeoffs -->

<!-- section: open_questions -->
## Open Questions

1. Is distance-graded selection with cut knobs the right core, and is file-level change granularity acceptable for v1 with a schema slot for symbols?
2. Are `select`, `implies` and `escalate` enough for the blast-radius rules the five repos need, or is there a case they cannot express?
3. Should the scheduler in v1 actually run runners concurrently across resources, or run serially while printing the schedule it would have used, so resource declarations get validated before they gate anything?
4. Which file receives a new declared edge when no hand-written file's `owns:` matches: refuse, or a default file?
5. Is the default policy for device units (selected by distance but filtered by resource availability) a per-project config value, and what is the framework default?
6. Are cost summaries committed per host class, or kept local only with the committed file as an optional export?
7. How does CI consume the evidence: the results directory as an artifact, a JUnit export, or both?
8. How is the thinking_app screenshot gate wrapped: `verify-active` as a whole-suite runner plus a `gradle-class` runner over `unit-tests --tests`, and does the protected-baseline rule need a resource or a rule of its own?
9. What is the bootstrap procedure for a repo: scan, report unmapped sources, write waivers, enable the check gate, then the selection gate?
<!-- /section: open_questions -->
--- PROPOSAL_END ---
