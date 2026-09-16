<!-- section: overview [dimensions: requirements_*] -->
## Overview

The baseline (n006) is complete as an *engine*: a static Go binary under
`$AITASKS_HOME/engine/v<VERSION>/`, a merged `aitestmap/` registry with member
units and variant axes, blob-digest stamps healed by a per-variant evidence
join, scoped rows under a suite budget, the graded walk, a real scheduler, the
cost ledger, automatic prediction scoring, three gates and two skills. Every one
of those pieces is kept unchanged here. What n006 leaves as a *procedure a
maintainer remembers* — the "Per-Repository Bootstrap Order" (`scan → classify
--suggest → areas --import-codemap → … → readiness`) and "how a project's tests
are run through the runners" — is exactly what this node turns into product:

1. **Onboarding existing tests is a skill that runs as an aitask.** Three new
   engine verbs (`detect`, `suggest`, `adopt`) do the deterministic work — find
   the test frameworks a repository already has, propose `covers` edges for
   every existing test from evidence, and write the registry files and
   annotation blocks through the engine's own line-targeted rewriter — and one
   new skill, `aitask-testmap-onboard`, supplies the judgement: it groups the
   proposals by evidence class, asks once per class rather than once per file,
   creates the onboarding task, and hands it to `task-workflow`, so the
   annotation diff is reviewed at Step 8 and the task's own `tests_pass` gate at
   Step 9 performs the **first full run that anchors every unit's `last_pass`**.
   The bootstrap order stops being a list in a document and becomes the plan
   of one task. Onboarding is graded in four levels so a repository is useful
   after level 0 (runners bound, `ait test --all` works, selection through the
   static closure) and gets sharper as each level lands as its own reviewed
   commit.

2. **Running tests is one verb, `ait test`, correct in every repository
   state.** With no `aitestmap/` it runs `test_command` and prints the
   onboarding hint; with a registry it resolves by itself whether it is the
   implementation loop or a completion gate, which task it is running for,
   and what the change set is — nothing is passed on the command line in the
   common case. It prints its own project-specific instructions
   (`ait test --howto`), computed from `runners.yaml` and `config.yaml`, so
   they cannot rot.

3. **No code agent relearns how to run tests.** The shared agent-instructions
   seed that `ait setup` already installs into `CLAUDE.md`'s managed block,
   `AGENTS.md`, `.codex/instructions.md` and the OpenCode mirror gains a
   `## Running Tests` section naming `./ait test` and forbidding direct tool
   invocation. It is agent-agnostic, project-agnostic and installed before
   onboarding, because the verb is right before onboarding too.

4. **The seam with `task-workflow` is data, not new steps.** The existing
   `tests_pass` gate runs `test_command`; onboarding sets `test_command:
   ./ait test`, and `ait test --gate` decides between the whole suite and the
   task's selection from a **committed completion policy** in
   `aitestmap/config.yaml` — `full` until `ait testmap readiness` reports
   `ADMISSIBLE` and a human writes `approved_by`, demoted back to `full`
   automatically if readiness regresses. n006's `testmap_run` gate is retired
   as a name; its verifier logic is `ait test --gate`, its `blocks_dependents`
   and `max_retries: 1` are `tests_pass`'s own, and its 1800 s timeout becomes
   a per-project `tests_pass.timeout_seconds` derived from the cost ledger.
   `testmap_check` now unlocks `tests_pass`. The command exit contract gains one
   row — 75 → verifier `error` for opted-in keys — in the one function that
   owns it. Profiles' `default_gates` carry the two gates. The workflow prose
   changes are one Step-7 paragraph, one `build-verification.md` branch, and
   `aitask-qa` reading the registry instead of naming conventions.

**Why the seed signal is the static closure and not the naming convention.**
Measured on this repository: 398 of 400 `tests/test_*.sh` name an
`aitask_*.sh` or `lib/*.sh|py` path literally (the two that do not are pure
fixture tests), 320 of 320 `tests/test_*.py` import a `.aitask-scripts/lib`
module through a `sys.path` bootstrap, and only **52 of 400** bash tests map to
`.aitask-scripts/aitask_<stem>.sh` by the `tests/test_<stem>.sh` convention
`aitask-qa`'s discovery step relies on today. On `aitasks_go` the subject is
deterministic (a `_test.go` covers the non-test files of its own package). The
`(t<id>)` commit convention gives a co-change signal for free — 336 task groups
in the last 400 commits touching tests or scripts — but a group averages 1.14
commits and pairs a few tests with a few scripts (t1159_1: 4 × 4) with nothing
inside the group to say which covers which, so co-change corroborates and never
decides. Every number here is reproduced by `ait testmap suggest --all --json`
on the day it runs; the skill shows them before anything is written.

**Scope of "rewrite".** Integrating an existing test means inserting
`testmap:` comment lines with the file's own comment leader — bash and Python
after the header comment block or module docstring, Go after the package
clause, Kotlin after the import block — plus, at level 2, `testmap:kind`,
`testmap:area`, `testmap:reads`, `testmap:batch no`, and at level 3
`testmap:unit` member blocks and a scaffolded runner script. The test's code is
never restructured: `git diff -w --ignore-blank-lines` of an adopted file shows
comments only. Where a test *should* be split or made runnable in isolation the
skill says so and proposes a follow-up task; it does not do it.
<!-- /section: overview -->

<!-- section: what_the_mandate_adds [dimensions: requirements_zero_config_entrypoint, requirements_onboarding_existing_tests, requirements_agent_instructions_seeded, requirements_workflow_seam_is_data, component_gates] -->
## What the Mandate Adds, and What It Changes in the Baseline

| mandate clause | n006 answer | this node | why |
|---|---|---|---|
| scan existing tests and integrate them | `scan` reads annotations that do not exist yet; `classify --suggest` and `areas --import-codemap` help; the bootstrap order is a list | `detect` / `suggest` / `adopt` verbs + `aitask-testmap-onboard` skill; four levels, each an aitask | the registry cannot be scanned into existence from files that carry no `testmap:` lines; evidence has to be joined and a human has to accept it in bulk |
| rewrite tests to use the architecture | `annotate --from-body` for one Kotlin member | `adopt` writes stamped blocks for every accepted edge through the same rewriter; comments only; provenance in `registry/adopted.yaml` | a machine-seeded claim must be distinguishable from a reviewed one until a human re-stamps it |
| how to actually run the tests | `ait testmap select … \| schedule \| run`, two gate verifiers, `tests_pass` beside `testmap_run` | `ait test` (interactive / completion / named / all / dirty / explain / howto), one completion gate under a committed policy | an agent should know one verb; which tests run at completion is a project decision that belongs in data, not in which of two gates a task declared |
| no configuration by the final user | `ait setup` installs the engine; the registry is hand-written | onboarding writes `config.yaml`, `runners.yaml`, `resources.yaml`, `areas.yaml`, `test_command`, `gate_command_exit_contract`, profiles' `default_gates`; `ait test` falls back to `test_command` and to `fallback_command` | every key the user would have typed is derived from what the repository already has, and confirmed once as a table |
| no re-learning per session | `aitask-testmap` skill teaches the verbs | `## Running Tests` in the seeded instructions block, `ait test --howto` computed | CLAUDE.md is where agents already learn `./ait git`; project specifics that would rot in prose are computed instead |
| seamless with task-workflow | `testmap_fresh` before the change summary; `testmap_check` → `testmap_run` | same procedure gate; `testmap_check` → `tests_pass`; `AIT_GATE_TASK_ID` export; 75 → error; one Step-7 paragraph; `aitask-qa` registry discovery | Step 9's verify block, the merge broker, archival and the orchestrator are untouched; the legacy no-gates path and `aitask-qa` inherit the selective lane through `test_command` |

Two baseline decisions are changed, both recorded in *Changes to the
Baseline* at the end: `testmap_run` is retired as a gate name, and the
command exit contract gains a 75 row for opted-in keys. Everything else in
n006 — engine, registry, axes, freshness, evidence, gates `testmap_fresh` and
`testmap_check`, the skills `aitask-testmap` and `aitask-gate-testmap-fresh`,
the per-user root and its migration verb — is inherited unchanged.
<!-- /section: what_the_mandate_adds -->

<!-- section: architecture [dimensions: component_test_entrypoint, component_onboarding_engine_verbs, component_onboarding_skill, component_agent_instructions, component_completion_policy, component_workflow_seam, component_qa_integration, component_go_engine] -->
## Architecture

### Process boundary, extended

```
./ait test [...]                                   (agent · human · tests_pass verifier via test_command)
 └─ .aitask-scripts/aitask_test.sh                 bash, ~120 lines: MODE / TASK / INTAKE / POLICY / fallback resolution only
      │  no aitestmap/            → TESTMAP_ABSENT:<hint>  → aitask_run_project_command.sh test_command  (exit per its verdict)
      │  engine absent            → interactive: ENGINE_MISSING:<path>|<repair> exit 3
      │                             completion:  per config.yaml completion.engine_absent (error | fallback_command)
      │  MODE   completion iff --gate or $AIT_GATE_TASK_ID, else interactive
      │  TASK   --task > $AIT_GATE_TASK_ID > aitask/<task_name> branch > single own lock (aitask_lock.sh --list-mine) > NO_TASK
      │  INTAKE aitask_change_surface.sh list <id> | --dirty (every dirty path as TASK:, printed) | --all | <path|id>...
      │  POLICY completion: config.yaml completion.mode (full | selected) re-checked against `readiness`
      └─ .aitask-scripts/aitask_testmap.sh          the n006 shim, unchanged
           └─ ait-testmap select --include-stale … → schedule → run        (n006 pipeline, unchanged)
                internal/onboard                    NEW: detect · suggest · adopt · howto
                internal/registry                   + registry/adopted.yaml (seventh table, written only by adopt)
                internal/cost                       + costs --gate-timeout
                internal/feedback                   + readiness LEVEL / NEXT / ADOPTED_UNREVIEWED / POLICY lines

.claude/skills/aitask-testmap-onboard/             NEW skill: detect → suggest → level proposal → per-class confirmation
                                                   → config table → create onboarding aitask → task-workflow
.claude/skills/aitask-testmap/                     n006, unchanged
.claude/skills/aitask-gate-testmap-fresh/          n006, unchanged
seed/aitasks_agent_instructions.seed.md            + ## Running Tests   (installed by ait setup into all four agent surfaces)
.aitask-scripts/lib/gate_verifier_lib.sh           run_project_command_key(): + 75 → error (opted-in keys); exports AIT_GATE_TASK_ID / AIT_GATE_RUN_ID
.aitask-scripts/gates_reference.yaml               + testmap_fresh, testmap_check (unlocks: [tests_pass]);  no testmap_run
.aitask-scripts/aitask_gate_testmap_check.sh       n006, unchanged;  aitask_gate_testmap_run.sh is NOT written
```

The boundary rule is n006's: parse, walk, match, digest, schedule *and now
detect / suggest / adopt* in Go; gate ledger, task file, shell environment
*and every write to `project_config.yaml`, `gates.yaml`, profiles or
`CLAUDE.md`* in bash and the skill. The engine never edits a framework
configuration file; it writes `aitestmap/**` and the annotation blocks it is
asked to write, and prints `WROTE:` for each.

### Where the new state lives

| data | location | written by |
|---|---|---|
| completion policy, onboarding conventions, helper roots | `aitestmap/config.yaml` (`completion:`, `conventions:`, `helper_roots:`, `helper_fanin:`) | `adopt` (level 0); the skill's `--policy` re-entry (`completion.mode`, `run_gate_admission.approved_by`) |
| adopted-edge provenance | `aitestmap/registry/adopted.yaml` rows `{test, source, signals, confidence, adopted_at, task}` | `adopt`; rows deleted by `verify`, `annotate`, `stale --confirm-source` on that edge |
| suggest output for review and attachment | `.aitask-testmap/onboard/<run-id>/suggest.json` (gitignored), attached to the onboarding task with `ait attach` | `suggest --json --out` |
| the test entry in project config | `aitasks/metadata/project_config.yaml`: `test_command: ./ait test`, `gate_command_exit_contract: [test_command]` | the skill, through `aitask_settings`-compatible YAML edits, confirmed |
| gate declarations | `aitasks/metadata/profiles/*.yaml` `default_gates`; `aitasks/metadata/gates.yaml` `tests_pass.timeout_seconds` | the skill, confirmed; timeout from `costs --gate-timeout` after the first full run |
| agent instructions | `CLAUDE.md` `>>>aitasks` block, `AGENTS.md`, `.codex/instructions.md`, OpenCode mirror | `ait setup` from the seed; hand-maintained `CLAUDE.md` by the onboarding task |

Everything else — registry, runners, resources, axes, costs, predictions,
runs, ledger, deps cache, locks, engine binaries — is where n006 put it.

### `aitestmap/config.yaml`, the additions

```yaml
# n006 keys unchanged: unit_covers_max, suite_budget_s, bootstrap_until, require_stamp, broad_review_days,
# concurrency, broad_after_unit, device_policy, host_class, flake_threshold, symbol_scanners, run_gate_admission
completion:
  mode: full                 # full | selected — selected written only by the onboarding skill after READINESS_DECISION:ADMISSIBLE
  deferred: run              # run | fail — completion never silently drops a row the interactive budget would cut
  on_empty_selection: skip   # skip (exit 2 → gate skip under the opt-in) | full
  engine_absent: error       # error (exit 3) | fallback_command (the suite runner's fallback_command:, MODE:fallback)
conventions:                 # seeded by detect; used by suggest's `convention` signal (0.7)
  - {test: "tests/test_{stem}.sh", source: ".aitask-scripts/aitask_{stem}.sh"}
  - {test: "tests/test_{stem}.py", source: ".aitask-scripts/lib/{stem}.py"}
helper_roots: ["tests/lib/**", "**/testing/**", "**/testdata/**"]
helper_fanin: 0.05           # a closure path reached by ≥5% of a runner's units is a helper, not a subject
```
<!-- /section: architecture -->

<!-- section: entrypoint [dimensions: component_test_entrypoint, component_completion_policy, assumption_task_resolvable_from_session, assumption_gate_exit_contract_reused] -->
## `ait test`: One Verb, Every Repository State

### Surface

```
ait test                       selected tests for the task you are implementing, each with a reason
ait test <path|id>...          named units: a listed test file, file#member, file#member@variant, a directory of tests,
                               or a SOURCE path — treated as a one-file change set, so `ait test lib/foo.py` runs what covers it
ait test --all                 the whole registry: every runner's list, full: true suites once, subsumed runners skipped
ait test --explain             the selection with reasons, groups and estimated cost; runs nothing
ait test --howto               this project's runners, kinds, resources, completion policy, LEVEL, and the three commands an agent needs
ait test --tokens              select --format tokens (thinking_app: `| xargs tools/verification/screenshot-tests.sh preview`)
ait test --gate                completion mode — what tests_pass runs; implied by $AIT_GATE_TASK_ID
ait test --dirty               no task: every dirty path is a TASK: row; explicit, printed as INTAKE:dirty, never the default
ait test --task <id>           override task resolution
ait test --fresh-only          exclude stale-marked units (interactive only)
ait test --budget-s <n>        interactive suite budget override
```

### Resolution, in order

1. **Registry present?** No `aitestmap/config.yaml` → print
   `TESTMAP_ABSENT:run /aitask-testmap-onboard to enable change-aware selection`
   and delegate to `aitask_run_project_command.sh test_command` (with
   `--task-id` when a task resolved), exiting with its verdict. This is what
   makes the seed instruction "always `./ait test`" true on day one in a
   repository that has never heard of the engine.
2. **Engine present?** Through the n006 shim's strict handshake. Absent:
   interactive → `ENGINE_MISSING:<path>|run 'ait setup' or set AIT_TESTMAP_BIN`,
   exit 3; completion → `completion.engine_absent`: `error` (default, exit 3 →
   verifier `error`) or `fallback_command` (run the `full: true` suite runner's
   `fallback_command:`, print `MODE:fallback`, exit per the command).
3. **Mode.** `--gate` or `$AIT_GATE_TASK_ID` set → `completion`; else
   `interactive`. Printed as `MODE:`.
4. **Task.** `--task` > `$AIT_GATE_TASK_ID` > the current worktree's branch if
   it matches `aitask/t<id>_*` (task-workflow's own naming) > the locks this
   user holds on this host (`aitask_lock.sh --list-mine`, a listing verb added
   to the lock script): exactly one → that task; several →
   `AMBIGUOUS_TASK:<ids>`, exit 64 unless `--task`; none → `TASK:none`.
5. **Intake.** Named paths → units by registry lookup, or a source path → a
   synthetic `TASK:<path>` change set; `--all` → every runner's `list`; a
   resolved task → `aitask_change_surface.sh list <id>` piped to `--changes -`
   (the n006 intake: `UNKNOWN:` refuses, `aitasks/` `aiplans/` `.aitask-data/`
   excluded); `--dirty` → `git status --porcelain` paths as `TASK:` rows with
   `INTAKE:dirty (no task attribution)`; nothing resolved → `NO_TASK:` with the
   three ways out (`--task`, `--dirty`, `--all`), exit 64.
6. **Policy (completion only).** Read `completion.mode`; if `selected`, run
   `ait testmap readiness` first: every criterion met → selected; any unmet →
   `POLICY_DEMOTED:selected->full|<criterion>` and run `full`. `full` →
   `run --all` with `subsumed_by` honoured (thinking_app: `verify-active`
   once, never `screen-matrix` beside it). `deferred: run` means the budget is
   not applied in completion mode; `on_empty_selection: skip` means a selected
   run with zero units exits 2, which the opted-in `tests_pass` records as
   `skip`, not `pass`.
7. **Run.** `select --include-stale [--budget-s] [--format …] --run <run-id>`
   → `schedule` → `run`, exactly the n006 pipeline. Interactive mode prints
   `DEFERRED:` rows; completion mode runs them.
8. **New-test notice.** For every `TASK:` / `COMMITTED:` path a runner lists
   that has no `testmap:` block and no `adopted.yaml` row:
   `UNANNOTATED_TEST:<path>` + `HINT:./ait testmap annotate --suggest <path>`.
   Informational in interactive mode; in completion mode `testmap_check` owns
   the enforcement (`UNSTAMPED` past bootstrap under `require_stamp`).

### Output and exit contract

```
MODE:interactive|completion|fallback   TASK:<id>|none   INTAKE:change-surface|dirty|all|named
POLICY:full|selected|<demoted…>        SELECTED:<units>|<groups>|<est_s>   RUN:<run-id>
ESCALATE:… DEFERRED:… UNANNOTATED_TEST:… HINT:…          (n006 line classes pass through)
RESULT:pass|fail|skip|error|refused|<n passed>|<n failed>|<n skipped>
```

| exit | meaning | as `test_command` under `gate_command_exit_contract: [test_command]` |
|---|---|---|
| 0 | every selected unit passed | pass |
| 1 | a unit failed, or a mechanism failure (`units_reported == 0`, unregistered row) | fail |
| 2 | nothing ran: empty selection, or `TESTMAP_ABSENT` + no `test_command` | skip |
| 3 | framework error: engine missing / mismatched, registry `CONTRACT_MISMATCH`, `UNKNOWN:` intake | **error** (new row) |
| 75 | admission refused after the in-engine deferral to the run deadline | **error** (new row) |
| 64 | usage: `NO_TASK`, `AMBIGUOUS_TASK`, bad flag | fail (a verifier cannot skip on a usage error) |

The 3 and 75 rows are the one change to `run_project_command_key()`'s table:
for a key listed in `gate_command_exit_contract`, exit 75 → `PROJECT_CMD_STATUS=error`,
`CODE=3`, `REASON=command_refused`, and exit 3 → `error` / `command_errored`.
For a key not opted in, both stay `fail` as today. The verifier appends
`error`, exits 3, and the orchestrator treats it as a verifier infrastructure
failure — retried within `max_retries`, never "fix the code", never a skip
that releases dependents. `build-verification.md` gains the matching branch.

### The two environment variables

`run_command_gate` exports `AIT_GATE_TASK_ID=<task-id>` and
`AIT_GATE_RUN_ID=<run-id>` around the command; `aitask_run_project_command.sh
--task-id <id>` exports the first. That is the whole mechanism by which
`./ait test` knows it is a completion run and for which task, in all three
existing call sites (the `tests_pass` verifier, the legacy Step-9 helper,
`aitask-qa`), with no argument in `test_command`. The run id lets the engine
name the gate run in `.aitask-testmap/runs/<run-id>/` so a ledger row and a
gate log share an identifier.
<!-- /section: entrypoint -->

<!-- section: onboarding [dimensions: component_onboarding_engine_verbs, component_onboarding_skill, assumption_static_closure_seeds_edges, assumption_cochange_is_corroboration, assumption_helpers_separable_by_fanin, assumption_annotation_is_comment_only, component_annotation_scanner, component_dependency_scanners] -->
## Onboarding Existing Tests

### Four levels, each one reviewed aitask

| level | what `adopt` writes | what the repository gains | who accepts |
|---|---|---|---|
| **0 — runners** | `config.yaml`, `runners.yaml` (builtins + bindings by glob, a `full: true` suite runner from `test_command` / `verify_build` with `fallback_command:`), `resources.yaml` from hints, `registry/areas.yaml` via `areas --import-codemap` | the universe (`list`), `ait test --all`, per-unit cost and `last_pass`, selection through the test-file static closure (`test-dep`), scoring on full runs; nothing stamped, nothing to go stale | nobody per edge — headless-safe |
| **1 — edges** | stamped `testmap:covers` blocks for accepted subject edges; `registry/adopted.yaml` rows | freshness and the evidence join apply; `stale` reports; `testmap_check` meaningful | per evidence class |
| **2 — kinds** | `testmap:kind integration\|e2e\|device` + `testmap:area` on broad tests, `testmap:reads` on tree-scanning helpers, `testmap:batch no` from serial lists, `needs:` on runners from resource hints | scoped rows, budget, `broad_after_unit`, enforced do-not-overlap | per kind reclassification, individually |
| **3 — product** | `axes.yaml` skeleton, `aitestmap/runners/<name>.sh` scaffold (`describe` / `list` / `run` stubs), `testmap:unit` member blocks | variant selection (n006's thinking_app mapping) | the maintainer, with the skill |

`readiness` derives the level from what exists (`runners.yaml` → 0, any
`_scanned` edge → 1, any `_scoped` row or `reads` → 2, `axes.yaml` → 3) and
prints `LEVEL:<n>` and `NEXT:<the adopt or skill step that raises it>`.

### `detect`

A closed detector list; each row carries its evidence so a reader can dispute it:

```
FRAMEWORK:bash-file|tests/**/test_*.sh|400|bash-file|bash shebang; sources tests/lib/asserts.sh
FRAMEWORK:pytest|tests/test_*.py|320|pytest|unittest/pytest imports; tests/run_all_python_tests.sh
AGGREGATE_RUNNER:tests/run_all_python_tests.sh|serial carve-out list found
SERIAL_LIST:tests/run_all_python_tests.sh|4                       → testmap:batch no candidates
RESOURCE_HINT:repo-git-index|~40 tests|git status/add against the real repo; .git/index.lock in comments
UNIVERSE:720   UNLISTED:0
SUITE_CANDIDATE:test_command|null
```

Detectors: `bash-file` (`tests/**/test_*.sh`, `scripts/tests/test_*.sh`, bash
shebang), `pytest` (`test_*.py` / `*_test.py`, `pytest.ini` / `pyproject
[tool.pytest]` / `conftest.py` / unittest imports), `go-test` (`go.mod` +
`*_test.go`, packages from `go list ./...`), `gradle-class` (`build.gradle(.kts)` +
`src/test/**/*.kt|java`; task `testDebugUnitTest` for Android modules, `test`
for JVM), `kmp-sourceset` (a `kotlin { }` multiplatform block; `commonTest` →
`gradle-class` on `:<module>:jvmTest` or `allTests`, `androidHostTest` →
`testDebugUnitTest`, `androidDeviceTest` → the `device` runner on
`connectedDebugAndroidTest` with `needs: [emulator]`), `suite-from-config`
(`test_command` / `verify_build` values that look like a test runner).
`RUNNER_SCRIPT_NEEDED:<reason>` when the grid heuristic (n006's `classify
--suggest`) finds a product space or when listed files are not lowerable by a
builtin. `UNLISTED:<n>` is the set that would fail `UNREGISTERED` after
adoption, printed so the skill can ask whether they are tests at all.

### `suggest`: the evidence join

For every unit a runner lists, one row per candidate source:

```
SUGGEST:tests/test_gate_verifiers.sh|.aitask-scripts/lib/gate_verifier_lib.sh|static,cochange:3|0.94
SUGGEST:tests/test_gate_verifiers.sh|.aitask-scripts/aitask_gate_tests_pass.sh|static|0.90
SUGGEST:tests/test_gate_pass.sh|.aitask-scripts/aitask_gate_pass.sh|static,convention|0.97
SUGGEST_HELPER:tests/test_gate_verifiers.sh|tests/lib/asserts.sh|helper_root
SUGGEST_READS:tests/lib/import_isolated.py|.aitask-scripts/lib/**/*.py|glob.glob
SUGGEST_KIND:tests/test_board_header_row_live.py|integration|tmux;real-git;areas:board,scripts
SUGGEST_BATCH_NO:tests/test_board_header_row_live.py|SERIAL_LIST
```

| signal | how | confidence |
|---|---|---|
| `static` | the unit's forward closure from the n006 dependency scanners — bash `source` / `.` / exec of a repo path including `$SCRIPT_DIR`- and `$PROJECT_DIR`-relative forms resolved against every source root; Python imports resolved through the file's own `sys.path` bootstrap; a `_test.go`'s own package; Kotlin imports — minus helpers | 0.9; Go package 1.0 |
| `convention` | `config.yaml conventions:` patterns, seeded by `detect` per framework | 0.7 |
| `cochange` | `git log --name-only` on the unit's last 50 commits, grouped by `(t<id>)` tag when present else by commit; a source-root path present in ≥ 2 groups | 0.2 + 0.2 × groups, cap 0.6 |
| `plan` | an `aiplans/` file naming both paths, through the `aitask_explain_extract_raw_data.sh` cache when present | 0.5 |
| `prose` | a literal path in the unit's header comment or a `# Covers:` line — a hint, never matched by the scanner | 0.3 |

Combined confidence is `1 − Π(1 − cᵢ)`; the default acceptance threshold is
0.85, so `static` alone qualifies, `convention` alone (0.7) does not, and
`cochange` can never qualify alone. **Helpers are separated from subjects
before scoring**: a closure path under `helper_roots` or with fan-in ≥
`helper_fanin` (5 % of the runner's units) is a helper — it gets `test-dep`
through the closure for free and, when it globs the tree (`ls tests/*.sh`,
`glob.glob`, `rglob`, `find`, `git ls-files`, `os.walk`), a proposed
`testmap:reads`. On this repository that is `tests/lib/` (27 files, 3 of which
glob). Kind classification: `integration` when the unit spawns tmux or a TUI
(`App.run_test`), boots a real install (`install.sh --dir`), touches the real
repository's git, or has more subjects than `unit_covers_max` (reason
`fanout:<n>`), with areas from the closure's directories intersected with
`code_areas.yaml`; `device` for `androidDeviceTest`; else `unit`. Members and
axes come from n006's grid heuristic.

### `adopt`: writing through the engine

`adopt --from suggest.json [--accept-min 0.85] [--scope <glob>] [--level 0..3]
[--dry-run]` writes level-0 files first, then for every accepted edge a
stamped block through `internal/annot`'s line-targeted rewriter:

```bash
# tests/test_gate_verifiers.sh - Tests for the project-command machine-gate verifiers …
# Run: bash tests/test_gate_verifiers.sh
# testmap:covers .aitask-scripts/lib/gate_verifier_lib.sh      @2026-09-16/3f9a1c07be
# testmap:covers .aitask-scripts/aitask_gate_tests_pass.sh     @2026-09-16/91be0d2a4c
# testmap:covers .aitask-scripts/aitask_gate_build.sh          @2026-09-16/c02d7e5f18
```

Placement per language: bash and Python after the header comment block (Python
after the module docstring, as `#` lines — the grammar also accepts docstring
lines, but rewriting a docstring changes `__doc__`, so adoption does not); Go
after the package clause; Kotlin after the import block. Every edge written
gets a row in `registry/adopted.yaml` (`test, source, signals, confidence,
adopted_at, task`), deleted when a human `verify` / `annotate` /
`--confirm-source` re-stamps that edge. Refusals and skips are explicit:
`ADOPT_REFUSED:<path>|dirty-foreign` for a file dirty outside the current
task's change surface (adoption never mixes with concurrent work),
`ADOPT_SKIP:<path>|duplicate` for an edge already annotated,
`ADOPT_SKIP:<path>|unregistered` for a file no runner lists (fix `runners.yaml`
first), `ADOPT_SKIP:<path>|no-leader` for a file whose comment leader the
grammar does not know. `WROTE:<path>` per file and one
`ADOPT_SUMMARY:<level>|<edges>|<files>|<skipped>`.

### The skill, step by step

1. **Preconditions.** `ait testmap version` — absent → stop with the `ait
   setup` hint. `aitestmap/` present → *refresh mode*: `suggest` limited to
   units newer than the last `adopted.yaml` row, same flow.
2. **Read-only survey.** `detect`; `suggest --all --json --out
   .aitask-testmap/onboard/<run>/suggest.json`. Display the level proposal:
   frameworks and counts, edges per evidence class with three samples each,
   helpers found and which glob, kind candidates with reasons, `UNLISTED`
   files, `RUNNER_SCRIPT_NEEDED` if any, and the four config writes.
3. **Confirm per class.** `AskUserQuestion` per evidence class — *accept all /
   review a sample (ten random members with their signals) / skip* — and per
   kind reclassification individually (non-skippable: a kind changes staleness
   semantics). `UNLISTED` files: *test — bind to runner X / not a test /
   decide later*. Headless (`remote`) profile: level 0 plus static-only level 1
   at `--accept-min 0.95`, no prompts, no kinds.
4. **Confirm the config table once.** `test_command` → `./ait test`, with a
   previous value moved to a `full: true` suite runner (`verify_build` is left
   alone unless the user names it as the suite — thinking_backend);
   `gate_command_exit_contract` += `test_command`; project profiles'
   `default_gates` += `tests_pass`, `testmap_check`; the `### Testing`
   paragraph when `CLAUDE.md` is hand-maintained (the sentinel guard in
   `update_claudemd_git_section` is exactly how the skill knows).
5. **Create the onboarding aitask and continue into task-workflow.**
   `aitask_create.sh --batch --name "testmap onboarding level <n>" --type chore
   --labels testing,testmap`, `ait attach` the `suggest.json`; the plan is the
   `adopt` command lines and the config writes; continue as `aitask-explore`
   does (`explore_auto_continue`-style, honouring the profile). Step 7 runs
   `adopt`; Step 8 reviews the diff — the user sees every inserted line; Step
   9's `tests_pass` runs `./ait test --gate` under `completion.mode: full`,
   which is the **first full run**: every unit's `last_pass` is anchored,
   `PREDICTION_SCORED:none` is printed because nothing was predicted yet, and
   the archive commits registry, annotations and config under one `(t<id>)`.
6. **After the first run.** `ait testmap costs --gate-timeout tests_pass` →
   `GATE_TIMEOUT_SUGGESTED:tests_pass|<s>` = `max(600, 3 × p95)` → written into
   the project's `gates.yaml`; `readiness` → `LEVEL` / `NEXT`; the next level's
   task is created with `depends:` on this one.
7. **`--policy selected` re-entry**, later: run `readiness`; only on
   `READINESS_DECISION:ADMISSIBLE` write `completion.mode: selected` and
   `run_gate_admission.approved_by {who, at, statement}`; one `ait:` commit.
   `NOT_YET` → print the unmet criteria and stop.
<!-- /section: onboarding -->

<!-- section: worked_onboarding [dimensions: assumption_full_run_expressible_per_repo, component_reference_runners, component_runner_contract, component_scheduler_resources, assumption_existing_locks_wrappable] -->
## Worked Onboarding: the Five Target Repositories

| repository | `detect` | level 0 runners and resources | full run (`completion.mode: full`) | levels 1–3 |
|---|---|---|---|---|
| **aitasks** | bash-file 400, pytest 320, `AGGREGATE_RUNNER` with a 4-module `SERIAL_LIST`, `RESOURCE_HINT:repo-git-index`, `test_command: null` | `bash-file`, `pytest` (`testmap:batch no` on the carve-out); `resources.yaml`: `repo-git-index {kind: mutex, scope: worktree}` needed by both runners — the "invocation policy, not a guarantee" comment in `run_all_python_tests.sh` becomes enforced | `ait test --all` (no suite existed; `tests_pass` gates for the first time); `fallback_command` derived: `for f in tests/test_*.sh; do bash "$f"; done && bash tests/run_all_python_tests.sh` | 1: 398 + 320 static edges, 52 corroborated by convention; helpers `tests/lib/` (27; 3 `reads`); 2: ~40 tmux / live-TUI / real-install tests → `integration` over codemap areas; 3: the goldens tree `tests/golden/` as a skill × profile × agent axis (n006's example) |
| **thinking_app** | gradle-class 374 classes, `RUNNER_SCRIPT_NEEDED:grid` (screen × matrix), `SUITE_CANDIDATE:test_command\|verify-active`, `RESOURCE_HINT:heavy-run` (exit 75 lock script) | `gradle-class` builtin until the project runner exists; `verify-active {unit: suite, full: true, children: …, fallback_command: tools/verification/screenshot-tests.sh verify-active}`; `heavy-run {kind: admission, exec: heavy-run-lock.sh}` | `verify-active` once (`screen-matrix`, `gradle-class` `subsumed_by: verify-active`) — identical to today's `test_command` | 3 = n006's worked mapping: `axes.yaml`, `tools/verification/testmap_runner.sh`, `testmap:unit` blocks in `ScreenFixtures.kt`; `completion.mode` stays `full` until readiness, exactly t388's rule |
| **thinking_backend** | bash-file 22 + pytest 18 under `scripts/tests/`, `SUITE_CANDIDATE:verify_build\|scripts/tests/run_script_tests.sh` | `bash-file`, `pytest` with `cwd:`; the skill asks: keep `verify_build` (it also enforces a shellcheck baseline — half lint) and add `test_command: ./ait test` — default | `ait test --all` over the 40 units; `build_verified` still runs the script | 1: static edges into `scripts/server/**` and `db_target.py`; 2: `golden/` fixtures as `reads` |
| **aitasks_go** | go-test: 85 packages, 55 `_test.go` files | `go-test` (per-package `-run`, `-json`) | `go test ./...` = `ait test --all` | 1 fully automatic: a test's package is its subject at confidence 1.0 — level 1 is headless-safe here |
| **aitasks_mobile** | kmp-sourceset: `commonTest` 36 (dbaccess 2, domain 25, shared 9), `androidHostTest` 1, `androidDeviceTest` 3 | `gradle-class` × modules on `:<module>:jvmTest` / `testDebugUnitTest`; `device` runner on `connectedDebugAndroidTest` with `emulator {kind: allocator}` | unit kinds only; device kind under `device_policy: filter_by_resource` — n006's open question 9 is answered: the source set is a runner/kind distinction, no axis | 1: Kotlin import closure (`domain/src/commonMain/**`) |

In every row the user typed nothing; the skill showed the table and asked for
one confirmation per class and one per config write.
<!-- /section: worked_onboarding -->

<!-- section: agent_instructions [dimensions: component_agent_instructions, assumption_instruction_block_is_read, requirements_agent_instructions_seeded] -->
## Agent Instructions: Installed, Not Learned

`seed/aitasks_agent_instructions.seed.md` gains one section, installed by the
existing `assemble_aitasks_instructions()` into every agent surface on every
`ait setup` (the `>>>aitasks` block is regenerated each run since t1612):

```markdown
## Running Tests

Run tests only through the framework entrypoint — never call pytest, go test,
gradle, or a test script directly.

    ./ait test              # tests selected for the task you are implementing, each line with its reason
    ./ait test <path>...    # a named test file or unit; a SOURCE path runs what covers it
    ./ait test --all        # the whole suite — what completion runs while the project's policy is `full`
    ./ait test --howto      # this project's runners, kinds, resources, completion policy and level

`./ait test` chooses tests from your task's change surface. When it prints
`UNANNOTATED_TEST:<path>` for a test you added, run
`./ait testmap annotate --suggest <path>` and accept or edit the proposal.
Exit codes: 0 pass · 1 fail · 2 nothing ran · 3 framework error (run `ait setup`) · 75 host refused
(resources; the run already waited — try later).
```

Three properties make this safe to install everywhere at once: the verb is
correct before onboarding (it runs `test_command`), the section carries no
project specifics (those are `--howto`'s computed output, so the
current-state-only documentation rule holds and no constant condenses
`runners.yaml`), and it is agent-agnostic (the shared Layer-1 seed, not the
per-agent Layer-2 files). `tests/test_agent_instructions.sh` gains T40: the
heading present in all four rendered surfaces. This repository's own
`CLAUDE.md` is hand-maintained (sentinel present, no markers), so its
`### Testing` block is edited by the onboarding task to point at `./ait test`
and keep the runner-specific notes (`run_all_python_tests.sh` lanes, the
`PIPESTATUS` caveat) as background.

`ait test --howto` prints, for aitasks after level 2:

```
HOWTO:aitasks LEVEL:2 POLICY:full
RUN   ./ait test                     selected for your task     ./ait test --all    720 units, ~4 min p95 on this host class
RUNNER bash-file   400 units  tests/**/test_*.sh          needs: repo-git-index
RUNNER pytest      320 units  tests/test_*.py             needs: repo-git-index   batch:no ×4 (serial carve-out)
KIND   unit 679 · integration 41 (areas: board, monitor, setup)
GATE   tests_pass runs `./ait test --gate` → full; testmap_check unlocks it; testmap_fresh before commit
NEW TEST  ./ait testmap annotate --suggest <path>
```
<!-- /section: agent_instructions -->

<!-- section: workflow_seam [dimensions: component_workflow_seam, component_gates, component_qa_integration, assumption_gate_exit_contract_reused, requirements_workflow_seam_is_data, requirements_gate_enforcement] -->
## The task-workflow Seam

| where | change | kind |
|---|---|---|
| `task-workflow/SKILL.md.j2` Step 7, after *Follow the approved plan* | one paragraph: "**Test loop.** Run `./ait test` after each meaningful change — it selects from this task's change surface and prints a reason per unit. When it prints `UNANNOTATED_TEST:<path>` for a test you added, run `./ait testmap annotate --suggest <path>` and accept or edit. Do not invoke the project's test tool directly; `./ait test <path>` runs one unit." | prose, rendered into every profile; goldens regenerated |
| Step 8 | n006's `testmap_fresh` procedure-gate dispatch before the change summary | inherited |
| Step 9 verify block (`./ait gates run`) | none — the orchestrator runs `testmap_check` → `tests_pass` (= `./ait test --gate`) | none |
| Step 9 no-gates branch (`build-verification.md`, `verify_build`) | none in prose; a project reaches the test lane by declaring `tests_pass`, which onboarding writes into `default_gates` | data |
| `build-verification.md` | one branch: verdict `error` with reason `command_refused` / `command_errored` → host refused resources or the framework could not run; do not fix code, do not record a pass, report and re-run later | prose |
| `lib/gate_verifier_lib.sh` `run_project_command_key()` | opted-in keys: 75 → `error`/3/`command_refused`, 3 → `error`/3/`command_errored`; export `AIT_GATE_TASK_ID`, `AIT_GATE_RUN_ID` around the command; docblock table updated (the single statement) | code; `tests/test_gate_verifiers.sh` extended |
| `aitask_run_project_command.sh` | `--task-id` also exports `AIT_GATE_TASK_ID`; inherits the new rows | code |
| `gates_reference.yaml` → `gates.yaml` sync | + `testmap_fresh` (procedure), + `testmap_check` (`unlocks: [tests_pass]`, `max_retries: 0`, `timeout_seconds: 120`); **no `testmap_run`**; `tests_pass` unchanged in the reference, `timeout_seconds` tuned per project from the ledger | data |
| project profiles (`aitasks/metadata/profiles/*.yaml`) | `default_gates` += `tests_pass`, `testmap_check` (onboarding, confirmed) | data |
| `aitask-qa/test-discovery.md` 3a–3c | with `aitestmap/`: per changed source `ait testmap explain --source <path>` → edges, test-deps, scoped rows; `GAP` = no edge and no test-dep; else the legacy convention scan | prose |
| `aitask-qa/test-execution.md` 4a–4d | 4a: the configured `./ait test` through `aitask_run_project_command.sh test_command --task-id <id>`; 4b: named units via `ait test <path>`; 4c: `REFUSED (host resources)` row; 4d coverage from registry edges | prose |
| `aitask-pickrem`, `aitask-pickweb`, `aitask-resume` | inherit through task-workflow and `build-verification.md`; pickweb (no `ait setup`) is the `engine_absent` case | none |
| `ait` dispatcher | `test)` → `aitask_test.sh`; help line | code |
| permission touchpoints (5) | `aitask_test.sh`, `aitask_testmap.sh` | config |
| `aidocs/framework/aitasks_extension_points.md` | "Adding a test-framework detector" (closed list, evidence line, fixture repo, `UNLISTED` behaviour) | doc |
| `aitask_skill_verify.sh` + goldens | task-workflow, aitask-qa, the new stub | test |

Three things the seam deliberately does **not** do: it does not add a Step-9
test step for tasks without gates (declaring `tests_pass` is the framework's
existing way to say "run tests at completion", and onboarding writes the
declaration); it does not make the engine write any framework file; and it
does not touch the merge broker, archival or the gate orchestrator.
<!-- /section: workflow_seam -->

<!-- section: data_flow [dimensions: component_test_entrypoint, component_onboarding_engine_verbs, component_onboarding_skill, component_completion_policy, component_workflow_seam, component_selector, component_cost_ledger, component_feedback_tools, component_registry_loader, component_staleness_tool] -->
## Data Flow

### Onboarding: existing tests → registry → first anchored run

```
repository (tests, scripts, build files, project_config.yaml, code_areas.yaml, git history)
   │
   ▼  ait testmap detect                        FRAMEWORK: / AGGREGATE_RUNNER: / SERIAL_LIST: / RESOURCE_HINT: / SUITE_CANDIDATE: / UNLISTED:
   ▼  ait testmap suggest --all --json           SUGGEST: (static·convention·cochange·plan·prose → confidence) / SUGGEST_HELPER: / SUGGEST_READS: / SUGGEST_KIND: / SUGGEST_BATCH_NO: / SUGGEST_MEMBER:
   │                                             → .aitask-testmap/onboard/<run>/suggest.json
   ▼  skill: level proposal → per-class AskUserQuestion → config table → aitask_create.sh --batch (+ ait attach suggest.json)
   ▼  task-workflow Step 7:  ait testmap adopt --from suggest.json --level 0 [--level 1 --accept-min 0.85] [--scope <glob>]
   │      writes aitestmap/config.yaml runners.yaml resources.yaml registry/areas.yaml           (level 0)
   │             testmap: blocks via the line-targeted rewriter + registry/adopted.yaml         (level 1)
   │      skill writes project_config.yaml test_command / gate_command_exit_contract, profiles default_gates, CLAUDE.md paragraph
   ▼  task-workflow Step 8:  the annotation diff reviewed; testmap_fresh (n006) — nothing STALE yet, every stamp is today's
   ▼  task-workflow Step 9:  ./ait gates run → testmap_check (non-strict during bootstrap) → tests_pass → ./ait test --gate
   │      MODE:completion POLICY:full → run --all → ledger.jsonl rows → last_pass per unit → PREDICTION_SCORED:none
   ▼  archive: one (t<id>) commit with registry, annotations, config;  ait: commit for gates.yaml timeout after costs --gate-timeout
   ▼  readiness → LEVEL:<n> NEXT:<step>;  the next level's task created with depends:
```

### Implementing a task: the interactive loop

```
agent edits code → ./ait test
   MODE:interactive  TASK:1234 (aitask/t1234_… branch)  INTAKE:change-surface
   aitask_change_surface.sh list 1234 | ait-testmap select --task 1234 --changes - --include-stale --budget-s <suite_budget_s> --run r1
   ├─ SELECTED:14|3|41s   …/test_gate_verifiers.sh d=1 unit edge(annotation) lib/gate_verifier_lib.sh  adopted(static 0.90)
   ├─ DEFERRED:tests/test_t167_integration.sh|budget                              (interactive only)
   ├─ UNANNOTATED_TEST:tests/test_ait_test_entrypoint.sh  HINT:./ait testmap annotate --suggest tests/test_ait_test_entrypoint.sh
   └─ schedule → run → RESULT:pass|14|0|0   prediction.json written for task 1234 (scored by the next full run)
agent: ./ait testmap annotate --suggest tests/test_ait_test_entrypoint.sh   → SUGGEST: rows → accept → block written, stamp today
```

### Completion: `tests_pass` → `./ait test --gate`

```
ait gates run 1234 → testmap_check (aitask_gate_testmap_check.sh) → pass → unlocks tests_pass
   → aitask_gate_tests_pass.sh → run_command_gate → export AIT_GATE_TASK_ID=1234 AIT_GATE_RUN_ID=<run> → `./ait test`
      MODE:completion  POLICY:full                       → run --all (subsumed_by honoured) → exit 0/1/2/3/75
      MODE:completion  POLICY:selected                   → readiness: all met → task selection, deferred rows RUN → exit …
      MODE:completion  POLICY:selected → POLICY_DEMOTED:selected->full|max_false_negatives  → run --all
   → run_project_command_key: 0 pass · 1 fail · 2 skip · 3 error(command_errored) · 75 error(command_refused)   [opted-in key]
   → ledger block result="MODE:full|720 units|policy:full" → orchestrator: pass / fail / skip / error(retry within max_retries: 1)
   → after any full run: PREDICTION_SCORED:<r1>|<run> PREDICTION_FALSE_NEGATIVES:<n> → costs/predictions.yaml → readiness input
```

### Policy flip

```
/aitask-testmap-onboard --policy selected
   → ait testmap readiness → READINESS:min_scored_full_runs|met|34  READINESS:max_false_negatives|met|0
                              READINESS:require_opaque_proofs|met  READINESS:approved_by|unmet|-
   → AskUserQuestion: record approval {who, statement}  → config.yaml completion.mode: selected, run_gate_admission.approved_by
   → ait: commit → the next tests_pass runs the selection; any later unmet criterion demotes it loudly
```
<!-- /section: data_flow -->

<!-- section: components [dimensions: component_*] -->
## Components

*(inherited from n006)* means unchanged in substance; *(modified)* names the
clause added here; *(new)* is a component n006 did not have.

<!-- section: component_test_entrypoint [dimensions: component_test_entrypoint] -->
### Test entrypoint `ait test` *(new)*

`.aitask-scripts/aitask_test.sh`, a ~120-line bash front over the n006 shim:
resolves `MODE` (completion iff `--gate` or `$AIT_GATE_TASK_ID`), `TASK`
(`--task` > `$AIT_GATE_TASK_ID` > `aitask/<task_name>` branch > single own lock
via `aitask_lock.sh --list-mine` > `NO_TASK`), `INTAKE` (change surface piped;
`--dirty`; `--all`; named paths, a source path as a one-file `TASK:` set) and
`POLICY` (completion: `config.yaml completion.mode` re-checked against
`readiness`); runs `select --include-stale → schedule → run`; falls back to
`aitask_run_project_command.sh test_command` when `aitestmap/` is absent and
to the suite runner's `fallback_command` when the engine is absent and the
policy allows; prints `MODE / TASK / INTAKE / POLICY / SELECTED / RUN /
RESULT` and `UNANNOTATED_TEST` + `HINT`; exits 0 / 1 / 2 / 3 / 75 / 64;
dispatcher arm `test)`; five permission touchpoints;
`tests/test_ait_test_entrypoint.sh` drives a fixture repository with
`AIT_TESTMAP_BIN` pointing at a fake engine that replays scripted exits.
<!-- /section: component_test_entrypoint -->

<!-- section: component_onboarding_engine_verbs [dimensions: component_onboarding_engine_verbs] -->
### Onboarding verbs `detect` / `suggest` / `adopt` / `howto` *(new)*

`internal/onboard`. `detect`: the closed detector list with an evidence field
per row, `UNIVERSE`, `UNLISTED`, `AGGREGATE_RUNNER`, `SERIAL_LIST`,
`RESOURCE_HINT`, `SUITE_CANDIDATE`, `RUNNER_SCRIPT_NEEDED`. `suggest`: the
five-signal join over the n006 dependency scanners with helper/subject
separation by root and fan-in, `SUGGEST_*` line classes, `--json`. `adopt`:
level-0 registry files, stamped blocks through `internal/annot`'s rewriter,
`registry/adopted.yaml`, level-2 lines and `needs:` bindings, level-3
`axes.yaml` skeleton and runner scaffold; `ADOPT_REFUSED` / `ADOPT_SKIP` /
`WROTE` / `ADOPT_SUMMARY`. `howto`: the `--howto` renderer over
`runners.yaml`, `resources.yaml`, `config.yaml` and the cost ledger. Go tests
on fixture repositories in `t.TempDir()`: one per detector, the fan-in
reclassification, a synthetic `(t<id>)` history for co-change, golden files
for block placement per language, every refusal branch.
<!-- /section: component_onboarding_engine_verbs -->

<!-- section: component_onboarding_skill [dimensions: component_onboarding_skill] -->
### Onboarding skill `aitask-testmap-onboard` *(new)*

Profile-aware stub + `SKILL.md.j2` (resolver key `onboard`), Claude Code first,
Codex and OpenCode ports as follow-up tasks. Preconditions → read-only survey
→ level proposal → per-class and per-kind confirmation → config table →
onboarding aitask created with the suggest JSON attached → task-workflow
(adopt at Step 7, diff at Step 8, first full run at Step 9) → timeout from
the ledger, `readiness`, next-level task with `depends:`. Headless: level 0 +
static-only level 1 at 0.95. `--policy selected` re-entry writes the flip only
on `ADMISSIBLE`. Rendered goldens under `tests/golden/skills/aitask-testmap-onboard/`.
<!-- /section: component_onboarding_skill -->

<!-- section: component_agent_instructions [dimensions: component_agent_instructions] -->
### Agent instructions *(new)*

`## Running Tests` in `seed/aitasks_agent_instructions.seed.md`, installed by
`assemble_aitasks_instructions()` into `CLAUDE.md`'s `>>>aitasks` block,
`AGENTS.md`, `.codex/instructions.md` and the OpenCode mirror on every `ait
setup`; no project specifics (computed by `--howto`); `tests/test_agent_instructions.sh`
T40 pins the heading in all four surfaces; the hand-maintained `CLAUDE.md`
case is the onboarding task's edit.
<!-- /section: component_agent_instructions -->

<!-- section: component_completion_policy [dimensions: component_completion_policy] -->
### Completion policy *(new)*

`aitestmap/config.yaml completion: {mode, deferred, on_empty_selection,
engine_absent}`; `mode: selected` written only by the skill after
`ADMISSIBLE` with `approved_by`; `ait test --gate` re-checks readiness on
every completion run and demotes loudly (`POLICY_DEMOTED:`) — the flip is
human, the demotion automatic, so the policy fails only toward running more.
<!-- /section: component_completion_policy -->

<!-- section: component_qa_integration [dimensions: component_qa_integration] -->
### aitask-qa integration *(new)*

`test-discovery.md` 3a–3c read the registry (`explain --source`) when
`aitestmap/` exists and fall back to the naming-convention scan otherwise;
`test-execution.md` 4a runs the configured `./ait test` through
`aitask_run_project_command.sh test_command --task-id <id>`, 4b runs named
units through `ait test <path>`, 4c gains the `REFUSED` row, 4d scores
coverage from edges; `REFUSED` is treated as `SKIP` in the health score.
<!-- /section: component_qa_integration -->

<!-- section: component_workflow_seam [dimensions: component_workflow_seam] -->
### Workflow seam *(new)*

The concrete edit list of the previous section: the Step-7 paragraph, the
`build-verification.md` branch, the two rows and two exports in
`run_project_command_key()`, `--task-id` export in
`aitask_run_project_command.sh`, `gates_reference.yaml` entries (no
`testmap_run`), profiles' `default_gates`, the `test)` dispatcher arm, the
extension-points section, the extended `tests/test_gate_verifiers.sh` and
regenerated goldens.
<!-- /section: component_workflow_seam -->

<!-- section: component_gates [dimensions: component_gates] -->
### Gates *(modified)*

`testmap_fresh` (procedure) and `testmap_check` (machine, `unlocks:
[tests_pass]`) in the reference registry; the completion test gate is the
existing `tests_pass` with `test_command: ./ait test` and the opt-in;
`testmap_run` retired as a name, its logic `ait test --gate`, its timeout a
project `tests_pass.timeout_seconds` from `costs --gate-timeout`, its 75 →
error mapping in the shared lib; `aitask_gate_testmap_run.sh` not written;
`run_gate_admission` and `readiness` gate the policy flip instead of a second
gate's declaration.
<!-- /section: component_gates -->

<!-- section: component_skill [dimensions: component_skill] -->
### Skills *(modified)*

`aitask-testmap` and `aitask-gate-testmap-fresh` as in n006, plus
`aitask-testmap-onboard`; the runtime knowledge an agent needs is the seeded
block plus `--howto`, never prose in a SKILL.md.
<!-- /section: component_skill -->

<!-- section: component_runner_contract [dimensions: component_runner_contract] -->
### Runner contract and repository *(modified)*

n006's `describe` / `list` / `run` contract unchanged; two repository keys
added: `subsumed_by: <suite>` (so `run --all` executes a `full: true` suite
once and never its subsumed runners beside it) and `fallback_command:` on a
suite runner (what completion runs when the engine is absent and the policy
allows).
<!-- /section: component_runner_contract -->

<!-- section: component_reference_runners [dimensions: component_reference_runners] -->
### Reference runners *(modified)*

n006's builtins; `detect` seeds the repository — bash-file, pytest (serial
carve-out → `testmap:batch no`), go-test per package, gradle-class, the
`kmp-sourceset` mapping (`commonTest` / `androidHostTest` → gradle-class unit
runners, `androidDeviceTest` → `device` with `needs: [emulator]`), and a
`full: true` suite runner from `test_command` / `verify_build`.
<!-- /section: component_reference_runners -->

<!-- section: component_registry_loader [dimensions: component_registry_loader] -->
### Registry loader and writer *(modified)*

n006's six tables plus `registry/adopted.yaml`, written only by `adopt`, rows
removed when a human re-stamps the edge — the set of covers edges nobody has
reviewed yet.
<!-- /section: component_registry_loader -->

<!-- section: component_staleness_tool [dimensions: component_staleness_tool] -->
### Staleness tool *(modified)*

n006's line classes; a row whose edge has an `adopted.yaml` entry carries
`adopted(<signals> <confidence>)` in its `DISPLAY` line so the procedure gate
knows it is confirming a machine-seeded claim.
<!-- /section: component_staleness_tool -->

<!-- section: component_feedback_tools [dimensions: component_feedback_tools] -->
### Feedback tools *(modified)*

n006's `score` / `attribute` / `readiness`; `readiness` additionally prints
`LEVEL`, `NEXT`, `ADOPTED_UNREVIEWED:<n>|<ratio>` and `POLICY:<mode>|<what
--gate would run now>`; still enables nothing.
<!-- /section: component_feedback_tools -->

<!-- section: component_cost_ledger [dimensions: component_cost_ledger] -->
### Cost ledger *(modified)*

n006's Welford / P² / invocation-group ledger; `costs --gate-timeout <gate>`
prints `GATE_TIMEOUT_SUGGESTED:<gate>|max(600, 3 × p95 of the newest full run)`.
<!-- /section: component_cost_ledger -->

<!-- section: component_go_engine [dimensions: component_go_engine] -->
### Go engine and CLI *(modified)*

n006's packages plus `internal/onboard`; verbs gain `detect | suggest | adopt |
howto`; the engine still never writes `project_config.yaml`, `gates.yaml`,
profiles or `CLAUDE.md`.
<!-- /section: component_go_engine -->

<!-- section: component_engine_binary [dimensions: component_engine_binary] -->
### Engine binary identity and budget *(inherited from n006)*

Version / commit / contract embedding, `version --json`, `CONTRACT_MISMATCH`,
the bench budget. `detect` and `suggest` are excluded from the latency table
(they run once per onboarding, exec `git log`, and are not on any gate path).
<!-- /section: component_engine_binary -->

<!-- section: component_binary_distribution [dimensions: component_binary_distribution] -->
### Binary distribution *(inherited from n006)*

Unchanged: `engine/build.sh`, the release `engine` job, `engine-check.yml`,
the shim's strict handshake, `platform_detect.sh`.
<!-- /section: component_binary_distribution -->

<!-- section: component_engine_packaging [dimensions: component_engine_packaging] -->
### Engine install and developer regeneration *(inherited from n006)*

Unchanged: `install_engine_binary()`, `ait engine build|test|cross|prune|home`.
`aitask_test.sh` is a framework script shipped in the tarball like every
`aitask_*.sh`; nothing to install.
<!-- /section: component_engine_packaging -->

<!-- section: component_user_root [dimensions: component_user_root] -->
### Per-user root *(inherited from n006)*

`lib/aitasks_home.sh`, `$AITASKS_HOME/engine/`; unchanged.
<!-- /section: component_user_root -->

<!-- section: component_framework_home [dimensions: component_framework_home] -->
### Framework home report and migration verb *(inherited from n006)*

`ait engine home [--migrate]`; unchanged, default flip still a named follow-up.
<!-- /section: component_framework_home -->

<!-- section: component_variant_axes [dimensions: component_variant_axes] -->
### Variant axes *(inherited from n006)*

`axes.yaml`, `<unit>@<variant>`, the facet join; unchanged. Level-3 adoption
writes only the skeleton the maintainer fills.
<!-- /section: component_variant_axes -->

<!-- section: component_axes [dimensions: component_axes] -->
### Axis resolver verbs *(inherited from n006)*

`axes --list | --check | --explain`; unchanged.
<!-- /section: component_axes -->

<!-- section: component_cell_enumeration [dimensions: component_cell_enumeration] -->
### Enumeration and reconciliation *(inherited from n006)*

The runner's `list` as the universe, `UNCOVERED_VALUE`, `UNMAPPED_ARTIFACT`;
unchanged. `detect`'s `UNIVERSE:` is the same count taken before runners exist.
<!-- /section: component_cell_enumeration -->

<!-- section: component_annotation_scanner [dimensions: component_annotation_scanner] -->
### Annotation scanner and rewriter *(inherited from n006)*

Grammar v3 and the line-targeted rewriter; unchanged — `adopt` is a new
*caller* of the rewriter, not a new writer.
<!-- /section: component_annotation_scanner -->

<!-- section: component_dependency_scanners [dimensions: component_dependency_scanners] -->
### Dependency scanners *(inherited from n006)*

bash / python / go / kotlin / gradle scanners and plugins; unchanged —
`suggest`'s `static` signal is their forward closure read from the same
blob-keyed cache.
<!-- /section: component_dependency_scanners -->

<!-- section: component_selector [dimensions: component_selector] -->
### Selector *(inherited from n006)*

Intake, graded walk, variant expansion, budget, formats; unchanged. `ait test
<source path>` reaches it as a one-row `TASK:` change set from the shim.
<!-- /section: component_selector -->

<!-- section: component_scheduler_resources [dimensions: component_scheduler_resources] -->
### Scheduler and resources *(inherited from n006)*

Unchanged; `detect`'s `RESOURCE_HINT` rows become `resources.yaml` entries the
scheduler already understands (aitasks: `repo-git-index` mutex, worktree scope).
<!-- /section: component_scheduler_resources -->

<!-- section: component_evidence_join [dimensions: component_evidence_join] -->
### Evidence join *(inherited from n006)*

Unchanged; the onboarding task's first full run is what first populates the
anchors it reads.
<!-- /section: component_evidence_join -->

<!-- section: component_freshness [dimensions: component_freshness] -->
### Freshness *(inherited from n006)*

Unchanged; an adopted stamp is a stamp like any other and the procedure gate
handles it identically, with the `adopted(...)` display as context.
<!-- /section: component_freshness -->

<!-- section: component_suite_registry [dimensions: component_suite_registry] -->
### Scoped-row registry and areas *(inherited from n006)*

Unchanged; level-0 adoption calls `areas --import-codemap`, level 2 writes the
scoped rows' source lines.
<!-- /section: component_suite_registry -->

<!-- section: component_broad_test_scopes [dimensions: component_broad_test_scopes] -->
### Broad-test scheduling policy *(inherited from n006)*

Unchanged; `completion.deferred: run` means the suite budget applies to the
interactive loop only.
<!-- /section: component_broad_test_scopes -->
<!-- /section: components -->

<!-- section: assumptions [dimensions: assumption_*] -->
## Assumptions

**Inherited unchanged from n006** (the full text is in the node metadata):
`assumption_areas_express_suite_blast_radius`, `assumption_axis_membership_declarable`,
`assumption_axis_sources_declarable`, `assumption_batch_per_unit_timing_reportable`,
`assumption_blob_digest_is_staleness_key`, `assumption_broad_tests_area_scoped`,
`assumption_cells_enumerable_by_plugin`, `assumption_change_surface_is_intake`,
`assumption_engine_latency_targets`, `assumption_existing_locks_wrappable`,
`assumption_git_history_is_freshness_clock`, `assumption_go_toolchain_available`,
`assumption_go_toolchain_ci_and_dev_only`, `assumption_home_symlink_compatibility`,
`assumption_kotlin_scanner_fail_closed`, `assumption_legacy_user_root_coexists`,
`assumption_one_engine_per_framework_version`, `assumption_passing_run_anchors_edges`,
`assumption_platform_matrix_sufficient`, `assumption_release_asset_reachable`,
`assumption_release_assets_reachable`, `assumption_static_granularity_v1`,
`assumption_target_repos_accept_aitestmap_root`, `assumption_testmap_token_no_collision`,
`assumption_variant_universe_from_runner_list`.

**Modified:**

- **`assumption_gate_exit_contract_reused`** — the verifier contract is reached
  through the *existing* `tests_pass` verifier running `test_command: ./ait
  test`; `run_project_command_key()` gains the 75 → error and 3 → error rows for
  opted-in keys; the verifier exports `AIT_GATE_TASK_ID` / `AIT_GATE_RUN_ID`;
  `testmap_check` keeps its own shell. n006 reused the contract through two
  dedicated shells; here it is one shell plus one row in the shared lib, which
  is what lets the legacy Step-9 helper and `aitask-qa` agree by construction.

**New:**

- **`assumption_static_closure_seeds_edges`** — measured: 398/400 bash tests
  name their subject path literally, 320/320 Python tests import a lib module,
  52/400 match the naming convention; Go's subject is deterministic; Kotlin's
  is the n006 import closure. *Falsifier:* tests reaching subjects only through
  a dynamic dispatcher — `suggest` emits no static rows, and the answer is
  conventions plus co-change, or level 0.
- **`assumption_cochange_is_corroboration`** — 336 task groups in 400 commits,
  1.14 commits per group, few-to-few pairing inside a group; capped at 0.6 so
  it never decides alone; per-commit grouping where the `(t<id>)` convention is
  absent.
- **`assumption_helpers_separable_by_fanin`** — helper roots plus fan-in ≥ 5 %
  of a runner's units; a misread hot production module keeps `test-dep`
  selection (over-selects) and every reclassification is listed for review.
- **`assumption_task_resolvable_from_session`** — the `aitask/<task_name>`
  branch in worktree mode, the single own lock in current-branch mode,
  `AIT_GATE_TASK_ID` in gate context; `AMBIGUOUS_TASK` and `--dirty` cover the
  rest. *Falsifier:* work outside the workflow — explicit intake only.
- **`assumption_full_run_expressible_per_repo`** — each of the five targets'
  completion suite is `ait test --all` or one `full: true` suite runner, with a
  derivable `fallback_command`; thinking_backend's suite is wired as
  `verify_build` and is the case the skill asks about.
- **`assumption_annotation_is_comment_only`** — adoption inserts comment lines
  only; `git diff -w --ignore-blank-lines` of an adopted file shows comments;
  `ADOPT_SKIP:no-leader` otherwise.
- **`assumption_instruction_block_is_read`** — agents follow the managed
  `CLAUDE.md` / `AGENTS.md` block, as the framework already relies on for `./ait
  git`; `ait setup` regenerates it on every run. *Falsifier:* a harness that
  ignores the file — `--howto` is the one-call fallback.
<!-- /section: assumptions -->

<!-- section: tradeoffs [dimensions: tradeoff_*] -->
## Tradeoffs

**Inherited unchanged from n006** (full text in the node metadata):
`tradeoff_area_glob_coarseness`, `tradeoff_attribution_risk`,
`tradeoff_autonomous_confirmation_weak`, `tradeoff_axis_declaration_burden`,
`tradeoff_axis_projection_coarseness`, `tradeoff_batch_misreport_risk`,
`tradeoff_broad_scope_coarseness`, `tradeoff_cell_table_size`,
`tradeoff_compiled_component_cost`, `tradeoff_computed_vs_prose`,
`tradeoff_engine_absent_on_host`, `tradeoff_engine_speed_enables_per_task_use`,
`tradeoff_engine_version_skew`, `tradeoff_evidence_requires_reachable_history`,
`tradeoff_flaky_pass_anchors`, `tradeoff_home_migration_window`,
`tradeoff_intersection_can_underselect`, `tradeoff_member_annotation_drift`,
`tradeoff_noarch_packages_preserved`, `tradeoff_real_scheduler`,
`tradeoff_registry_directory_complexity`, `tradeoff_resource_declaration_completeness`,
`tradeoff_setup_network_fetch`, `tradeoff_split_home_rejected`,
`tradeoff_static_scanner_overselection`, `tradeoff_strict_version_handshake`,
`tradeoff_two_toolchains`, `tradeoff_two_user_roots`, `tradeoff_whole_run_filter_soundness`.

**Modified:**

- **`tradeoff_fail_closed_bootstrap_cost`** — *narrowed.* The bootstrap order
  becomes one aitask the skill creates and runs; `detect` and `suggest` are
  read-only; level 0 writes only registry files; the onboarding task's own
  `tests_pass` is the first anchoring full run; `bootstrap_until` is set by
  `adopt`; `readiness` prints `LEVEL` / `NEXT`. What remains: a repository is
  level 0 (bound, closure-selected, unstamped) until a human accepts level 1,
  and headless profiles stop at level 0 plus static-only edges.
- **`tradeoff_stamp_churn`** — *one clause added.* Level 1 on aitasks touches
  ~720 files with one to eight comment lines each; mitigated by `--scope
  <glob>` per area across tasks, the diff being comments only, `ADOPT_REFUSED`
  on dirty-foreign files, and the reviewed `(t<id>)` commit.

**New:**

- **`tradeoff_one_gate_not_two`** — *Advantage:* one completion gate whose
  behaviour is a committed policy; one command for agents; the legacy Step-9
  path and `aitask-qa` reach the selective lane through `test_command`; the
  flip is one line after readiness. *Disadvantage:* a ledger `tests_pass: pass`
  no longer says by itself whether the whole suite ran — mitigated by
  `result="MODE:<full|selected>|<n>|policy:<mode>"` on the gate-run block,
  `POLICY_DEMOTED` being loud, and `readiness` printing what `--gate` would run.
- **`tradeoff_seed_precision`** — *Risk:* an adopted `covers` edge says the
  test *executes* the source, not that it *verifies* it; a test that drives
  three scripts to set up one adopts three edges. Narrowed by `adopted.yaml`
  provenance shown in `stale` / `explain`, `ADOPTED_UNREVIEWED` in readiness,
  the over-claim direction only over-selecting, the 0.85 threshold, and
  three-sample display per class; a coupling the closure does not contain is
  still caught only by a full run's score, as in n006.
- **`tradeoff_fallback_runs_more`** — *Disadvantage:* with the engine absent and
  `engine_absent: fallback_command`, completion runs the pre-onboarding suite
  command — never less than before, never selective, no per-unit results or
  anchors; the default is `error`, and `MODE:fallback` is visible.
- **`tradeoff_verify_build_wired_suites`** — *Disadvantage:* a suite wired as
  `verify_build` (thinking_backend, half lint) cannot be moved mechanically
  without either dropping the lint half or double-running; the skill asks,
  defaults to keeping it, records the answer in the plan; headless keeps.
- **`tradeoff_dispatcher_verb_added`** — *Disadvantage:* `ait test` beside `ait
  testmap`, two surfaces for one engine; justified by the human-would-type-it
  rule and the seed's need for one verb; kept thin; `ait testmap` remains the
  maintainer surface; `--howto` names `ait test` as the stable one.
- **`tradeoff_bulk_confirmation_granularity`** — *Risk:* per-class acceptance
  trades review depth for feasibility; mitigated by samples, `review a sample`,
  `--accept-min`, `--scope`, `adopted.yaml`, and individual confirmation of
  kind changes because a wrong kind changes staleness semantics.
<!-- /section: tradeoffs -->

<!-- section: changes_to_baseline [dimensions: component_gates, assumption_gate_exit_contract_reused, requirements_gate_enforcement] -->
## Changes to the Baseline, Stated

1. **`testmap_run` is retired as a gate name.** n006 had `tests_pass` (full,
   the completion gate) beside `testmap_run` (selected, `blocks_dependents`,
   `max_retries: 1`, `timeout_seconds: 1800`, unlocked by `testmap_check`,
   declared only when `readiness` is admissible). Here `tests_pass` runs
   `./ait test --gate` and the *policy* is what readiness admits. Every
   property of `testmap_run` has a home: its verifier logic is `ait test
   --gate`; `blocks_dependents` and `max_retries: 1` are `tests_pass`'s own;
   its timeout is a per-project `tests_pass.timeout_seconds` from the ledger;
   its exit mapping (0/1/2/75/64 → 0/1/2/3/3) is the shared lib's new rows;
   `testmap_check` unlocks `tests_pass`. Reason: an agent should know one gate
   and one command, and "which tests run at completion" is a project decision
   that belongs in committed data with an automatic demotion, not in which of
   two gates a task happened to declare. n006's thinking_app rule — full
   suite as the completion gate until admissible — is preserved exactly by
   `completion.mode: full`.
2. **The command exit contract gains two rows for opted-in keys.** 75 →
   `error` (`command_refused`), 3 → `error` (`command_errored`), in
   `run_project_command_key()`'s docblock and body — the single canonical
   statement — inherited by the three verifiers, the legacy helper and
   `aitask-qa`. Non-opted-in keys are unchanged. This is the smallest change
   that keeps n006's "75 → verifier 3, never skip" once the verifier is the
   command-driven `tests_pass`.
3. **`aitask_gate_testmap_run.sh` is not written**; `aitask_gate_testmap_check.sh`
   is. Everything else in n006's component list is unchanged or extended by a
   clause named in *Components*.
<!-- /section: changes_to_baseline -->

<!-- section: open_questions -->
## Open Questions

1. Should level 1 be accepted automatically for `go-test` projects (confidence
   1.0, deterministic subject) even under attended profiles? Proposed: yes, with
   the summary still shown.
2. Should `adopt` write `testmap:reads` into a helper under `tests/lib/` without
   asking, given a missing `reads` under-selects? Proposed: propose always,
   write on class acceptance, because the fallback (`test-dep`) still selects
   every importer on the helper's own change — only the *glob* is the addition.
3. `AIT_GATE_TASK_ID` is also visible to any other `test_command` — should the
   export be limited to commands matching `./ait test*`? Proposed: no; an
   environment variable a command ignores is harmless, and a project's own
   wrapper may want it.
4. Should `completion.on_empty_selection` default to `full` rather than `skip`
   for a `selected` policy? An empty selection with a non-empty change surface
   is a strong "the map does not know this file" signal. Proposed: `skip`
   during bootstrap, `full` once `require_stamp: true` — `readiness` prints the
   recommendation.
5. Where does the onboarding skill's `--policy selected` approval statement
   live for a project without a design record like thinking_app's
   `change-aware-verification.md#what-this-cannot-do`? Proposed: the skill
   writes `aitestmap/ADMISSION.md` from the readiness output and the user's
   statement, and `approved_by.statement` points at it.
6. `aitask_lock.sh --list-mine` is a new verb on an existing script; is a
   `ait ls`-based query (`status Implementing`, `assigned_to` = me) preferable
   so no lock-format knowledge leaves the lock script? Either satisfies the
   resolution rule; the proposal names the lock because it is host-scoped.
7. Should the onboarding task be *one* task per level or one parent with a
   child per level? Proposed: one task per level with `depends:`, because a
   level may wait weeks on the full-run history and a parent would sit
   Implementing the whole time.
8. Baseline questions still open (n006 §Open Questions 1–11) are unchanged;
   n006's question 9 (aitasks_mobile axis) is answered here: no axis, source
   sets are runner/kind distinctions.
<!-- /section: open_questions -->