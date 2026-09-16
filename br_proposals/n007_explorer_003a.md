<!-- section: overview [dimensions: requirements_*] -->
## Overview

The baseline (n006) is a complete change-aware testing engine — a static Go
binary under `~/.aitasks/engine/`, a committed `aitestmap/` registry of
source→test edges with blob-digest stamps healed by run evidence, member units
and variant axes for product-shaped suites, a runner contract, a real
scheduler, a cost ledger, a feedback loop, three gates and a maintenance skill.
What it does not say is how a repository that already has 300–700 test files
**gets onto** that map, and how an agent that opens the repository tomorrow
**runs tests** without first reading a 200-line testing section of `CLAUDE.md`.
Its "Per-Repository Bootstrap Order" is one paragraph of prose; its
`component_skill` teaches an agent to *maintain* a map that someone else has
already built by hand.

This node keeps every mechanism of n006 unchanged and adds the adoption layer
the mandate asks for, in three parts, each shaped by a measurement taken on the
target repositories rather than by preference:

**1. Onboarding as a resumable, task-shaped skill, not a runbook.**
`/aitask-testmap-onboard` detects the repository's test tools from the tree and
`project_config.yaml`, generates `aitestmap/` (config, runner table with
bindings, resources stub, areas imported from `code_areas.yaml`), inventories
every test unit through the runners' own `list`, classifies broad tests with the
reasons printed, **seeds** edges, proposes rules and waivers for what no seed
reaches, wraps the project's existing `test_command` as a `full: true` suite
runner and runs it once so evidence exists from day one, then accepts seeds in
batches and enables the gates. Every phase is idempotent and recorded in a
committed ledger (`aitestmap/onboard.yaml`); the run is an aitask so its writes
land under `(t<id>)` commits and a resumed session re-enters at
`ONBOARD_NEXT:`. The user types no YAML.

**2. Seeds that select but never claim.** The one genuinely new registry
object is `registry/seeded.yaml`: edges proposed by four measured heuristic
origins — naming (`test_gate_pass.sh` ↔ `aitask_gate_pass.sh`; 16–19 % of tests
in the target repos), **literal invocation and direct imports** (a bash test
that runs `./.aitask-scripts/x.sh`, a Python or Kotlin test that imports a main
file; 88 % / 80 % of aitasks tests, 41 % of thinking_app's), **`(t<id>)`
co-change history** (439 of the last 600 aitasks task commits touch tests and
scripts together, 2.8 scripts × 2.6 tests each — tight; thinking_app's 127 of
400 average 7.2 main files — noisy, hence a minimum of two distinct tasks), and
opt-in per-unit runtime coverage where the tool supports it. A seeded edge is
walked like an annotation edge at distance 1 (over-selection is the safe
direction) but carries no stamp, is invisible to `stale`, anchors nothing and
cannot satisfy `--strict`. **Acceptance** — a review act with the evidence
printed beside every row — is what writes the `testmap:covers` line and the
stamp, in per-area batches during onboarding or, inside the `testmap_fresh`
gate, for the test files a task already has open. Adoption is therefore
incremental and measurable (`onboard status`), never a big-bang rewrite, and a
half-migrated repository is a known state with a next step.

**3. One run surface, learned once.** `ait test` is the only verb an agent
needs: `--task <id>` (the tests the task's *attributed* change reaches, a reason
per row), `<path>...`, `--all` (the full registered suite — the completion
gate), and `brief` (this project's runners, resources, full gate, axes, doc
pointers and declared notes, generated from the registry). The seeded
`>>>aitasks` agent-instructions block that `ait setup` already writes into every
supported agent's instructions file gains a generic **Running Tests** section
— the same twelve lines in aitasks, thinking_app and aitasks_mobile — so the
project-specific facts come from `ait test brief`, never from prose an agent
has to find. The workflow seam is one helper, `aitask_affected_tests.sh`,
speaking the `VERDICT:/REASON:/LOG:` contract `aitask_run_project_command.sh`
already established, called from a new task-workflow Step-7 procedure behind
an `affected_tests` profile key; `aitask-qa`'s test discovery reads the map
instead of naming conventions; Step 8's procedure-gate dispatch and Step 9's
gate orchestrator are untouched; and every seam degrades to a **printed skip**
where the engine or registry is absent, which is what lets it sit in every
profile including the one Claude Code Web runs with no engine at all.

What this does not change: the engine's process boundary, the registry's six
tables and check rules, the id grammar, axes, the runner contract, the
scheduler, the ledger, the evidence join, the three gates' verifiers and the
per-user root. The seeds table is a seventh table with one rule (a seed that
duplicates an accepted edge is dropped with `SEED_SHADOWED`); the `test`,
`brief`, `seed` and `onboard` verbs are additions to the same binary; and the
freshness model gains exactly one new stamp writer (`onboard accept`), which is
also the only place a seed becomes a claim.
<!-- /section: overview -->

<!-- section: architecture [dimensions: component_onboarding_skill, component_seeder, component_test_front_verb, component_agent_brief, component_workflow_integration, component_go_engine, component_registry_loader, component_engine_binary] -->
## Architecture

### Process boundary (additions in bold-face comments)

```
ait test <form> ...                              (agent / user)            ← NEW alias
ait testmap <verb> ...                           (user / skill / gate verifier)
 └─ .aitask-scripts/aitask_testmap.sh            bash shim (n006), gains `test` passthrough
      │   resolve $AIT_TESTMAP_BIN > AIT_ENGINE=dev > $AITASKS_HOME/engine/v<VERSION>/ait-testmap
      │   for --task forms: aitask_change_surface.sh list <id> | <bin> <verb> --changes - ...
      └─ $AITASKS_HOME/engine/v<VERSION>/ait-testmap --repo-root "$AIT_DIR" <verb> ...
           internal/registry        six tables (n006) + seeds table from registry/seeded.yaml; SEED_SHADOWED
           internal/seed            ← NEW  naming / invocation / imports / cochange / coverage origins; confidence table
           internal/onboard         ← NEW  detect, inventory, phase ledger (onboard.yaml), accept / reject, status, finish
           internal/brief           ← NEW  the generated run brief (lines and --md)
           internal/selectr         graded walk (n006) + seeded edges at d1 with reason edge(seeded:<origins>); explain --sources
           internal/runner          contract (n006) + `runner scaffold`, the `full` suite wrapper, bash-file `list --invocations`
           internal/annot           grammar v3 + rewriter (n006); accept writes lines at the fixed header position
           internal/deps            scanners (n006); invocation + direct-import facts exposed to internal/seed
           internal/{axes,changesurface,sched,cost,feedback,stale,gitx,platform}   unchanged
             ├─ exec:  git, runner scripts / builtins, admission / allocator commands, scanner plugins
             └─ files: aitestmap/** · .aitask-testmap/ (runs, ledger) · XDG cache (deps, cochange matrix by HEAD sha)
.aitask-scripts/aitask_affected_tests.sh         ← NEW  workflow seam: `ait test --task` → VERDICT:/REASON:/DETAIL:/LOG:/SELECTED:/UNMAPPED_SOURCE:
.aitask-scripts/aitask_gate_testmap_check.sh     machine verifier (n006); reports SEEDED:<n>, UNMAPPED_SOURCE:<path>
.aitask-scripts/aitask_gate_testmap_run.sh       machine verifier (n006)
.aitask-scripts/aitask_setup.sh                  install_engine_binary (n006) + report_testmap_state() → TESTMAP:<state>   ← NEW line
.claude/skills/aitask-testmap-onboard/           ← NEW  static attended skill: SKILL.md + detect.md inventory.md classify.md seed.md
                                                        waivers.md full-run.md accept.md enable.md finish.md
.claude/skills/aitask-testmap/                   n006 skill; opens with `ait test brief`; hands an un-onboarded repo to onboard
.claude/skills/aitask-gate-testmap-fresh/        n006 procedure gate + "accept seeds for touched test files" step
.claude/skills/task-workflow/affected-tests.md   ← NEW  Affected Tests Procedure (Step 7)
.claude/skills/aitask-qa/{test-discovery,test-execution}.md   registry-first branches
seed/aitasks_agent_instructions.seed.md          + `## Running Tests` (generic; reaches CLAUDE.md / AGENTS.md via ait setup)
engine/                                           Go source — framework repo only
```

The boundary rule is n006's and is not bent: parse, walk, match, digest,
schedule and now *seed* in Go; gate ledger, task file, profile file and shell
environment in bash and skill prose. `onboard` never creates a task, never
edits a profile and never commits — the skill does those through
`aitask_create.sh --batch`, `aitask_pick_own.sh`, the settings helpers and
`git commit -- <paths>`; the engine reads `onboard.yaml`'s `task:` field and
writes `onboard.yaml`'s phase rows. The engine still never writes `aitasks/`,
`aiplans/`, `.aitask-data/` or a gate ledger and never invokes `aitask_*.sh`.

### Registry directory (n006's, with the additions marked)

```
aitestmap/
  config.yaml            n006 keys · exclude: [globs]            ← never listed, never UNREGISTERED (fixtures, helpers, generated)
                         · docs: [paths]                          ← printed by brief
                         · notes: |  (<=10 lines)                 ← printed by brief verbatim
                         · broad_threshold_s: 60                  ← classify signal
                         · bootstrap_until  (set by onboard enable, +30d)
  onboard.yaml           ← NEW  phase ledger: {contract: 1, task: t<id>, phases{...}, rejections[]}
  axes.yaml · runners.yaml · resources.yaml     (n006; runners.yaml written by onboard detect, confirmed per runner)
  registry/
    _scanned.yaml · _scoped.yaml · observed.yaml · areas.yaml · <area>.yaml    (n006)
    seeded.yaml          ← NEW  generated by `seed`; edited only by `onboard accept` (row removed) / `reject` (row removed)
  costs/ · runners/ · scanners/                  (n006; runners/<name>.sh may come from `runner scaffold`)
```

`seeded.yaml` rows:

```yaml
contract: 1
seeded:
  - test: tests/test_gate_pass.sh
    covers: .aitask-scripts/aitask_gate_pass.sh
    origin: [naming, invocation, cochange]
    confidence: 0.99          # noisy-OR of 0.6, 0.9, 0.6 — ordering only
    evidence:
      naming: "test_gate_pass.sh ~ aitask_gate_pass.sh"
      invocation: "tests/test_gate_pass.sh:41"
      cochange: [t635_15, t1147]
    proposed_at: 2026-09-16
  - test: app/src/test/java/com/softman/thinking/testing/ScreenFixtures.kt#Welcome
    covers: app/src/main/java/com/softman/thinking/ui/mvvm/auth/welcome/WelcomeScreen.kt
    origin: [imports]
    confidence: 0.85
    evidence: {imports: "ScreenFixtures.kt:212"}
    proposed_at: 2026-09-16
```

`onboard.yaml`:

```yaml
contract: 1
task: t1830
started_at: 2026-09-16 12:30
phases:
  detect:    {status: done,    at: 2026-09-16 12:41, by: daelyasy@hotmail.com, runners: 3}
  inventory: {status: done,    at: 2026-09-16 13:02, units: 721, unregistered_resolved: 12, excluded: 4}
  classify:  {status: partial, reviewed: 41, pending: 7}
  seed:      {status: done,    at: 2026-09-16 13:20, rows: 1184, tests_with_seed: 605, sources_with_seed: 233}
  waivers:   {status: done,    rules: 4, waivers: 9}
  full_run:  {status: done,    run_id: full-2026-09-16T13.40-3f1c, anchored: 721}
  accept:    {status: partial, accepted: 210, rejected: 14, pending: 960}
  enable:    {status: pending}
  finish:    {status: pending}
rejections:
  - {test: tests/test_board_header_row_live.py, source: .aitask-scripts/lib/tmux_exec.py,
     reason: "gateway used, not covered", at: 2026-09-16 13:55}
```

### The seed → accept state machine

```
                seed --apply                    onboard accept <test> | --area | --batch N
   (none) ───────────────────▶ SEEDED ──────────────────────────────────────────▶ ACCEPTED (testmap:covers line + stamp)
                                  │                                                  ▲
                                  │ onboard reject <test> <source>                    │ annotate / attribute (n006 paths, unchanged)
                                  ▼                                                  │
                              REJECTED (onboard.yaml; never re-proposed)              (none) ───────────────────────────────┘
   attribute --propose (autonomous) ───▶ SEEDED with origin observed
```

`SEEDED` selects; only `ACCEPTED` claims. Nothing moves a row right without a
person or an attended agent naming the row.
<!-- /section: architecture -->

<!-- section: onboarding [dimensions: component_onboarding_skill, component_seeder, requirements_zero_config_onboarding, requirements_incremental_adoption, assumption_test_tools_detectable, assumption_seed_sources_measured, assumption_seeds_select_never_evidence, assumption_onboarding_is_a_task] -->
## Onboarding a Repository: Phases, Ledger, Seeds

### Invocation and shape

`/aitask-testmap-onboard [<task-id>]`. Without an argument the skill creates and
claims `testmap_onboarding` (`aitask_create.sh --batch --name testmap_onboarding
--type chore --labels testmap --priority medium`, then `aitask_pick_own.sh`),
writes the id into `onboard.yaml`, and from then on every phase ends with one
commit of the files it produced — `chore: Onboard testmap — <phase> (t<id>)`,
paths named — so `aitask_change_surface.sh` attributes them and the framework's
own re-entry (`/aitask-pick <id>`, which finds `onboard.yaml` and dispatches
back to this skill) resumes at `ONBOARD_NEXT:`. The skill is **static and
attended-only** (no profile stub, no `.j2`): every phase is a judgement call, and
a repository is onboarded once. It refuses on Claude Code Web (`TESTMAP:engine-missing`).

### Phases

| # | phase | engine verb | what the skill confirms | commit |
|---|---|---|---|---|
| 0 | preflight | `version --json`, `onboard status` | engine present, repo root, no `aitestmap/` or an unfinished ledger to resume | — |
| 1 | **detect** | `onboard detect [--write]` | the runner table, one `AskUserQuestion` per detected runner: keep / edit command / drop; the `full` suite wrapper of `test_command` (or `verify_build` when that is the only test-running key — thinking_backend — with the proposal to move it) | `aitestmap/{config,runners,resources}.yaml`, `registry/areas.yaml` |
| 2 | **inventory** | `scan`, every runner `list`, `check` | `UNREGISTERED:` files → bind to a runner or add an `exclude:` glob (fixtures, `tests/lib/`, `tests/golden/`); `areas --import-codemap` when `code_areas.yaml` has areas | `registry/_scanned.yaml`, `config.yaml` |
| 3 | **classify** | `classify --suggest` | each `CLASSIFY:<test>\|<kind>\|<reason>` candidate in batches of 20: accept kind, set areas / scope / trigger; unit stays the default | `registry/_scoped.yaml` via `scan --apply` |
| 4 | **seed** | `seed --from naming,invocation,imports,cochange [--apply]` | the counts: rows, tests with ≥1 seed, sources with ≥1 seed, per-origin share; opt-in `--from coverage` when the tool supports per-unit contexts | `registry/seeded.yaml` |
| 5 | **waivers** | `check`, `explain --sources` | for each `UNMAPPED_SOURCE:` directory cluster: a `rules:` entry (glob → runner set) for hot directories, an expiring waiver (`expires: +90d`) for the rest, or "leave unmapped" | `registry/<area>.yaml` |
| 6 | **full_run** | `ait test --all`, `costs --update` | the full gate ran through the suite wrapper; child rows anchored `last_pass` on every registered id; `PREDICTION_SCORED:none` | `costs/<hostclass>.yaml` |
| 7 | **accept** | `onboard accept --area <a> --batch 50` | every seed with its evidence — the file pair, the `file:line`, the task ids, the coverage run — accept / reject / leave; a file's `# Covers:` prose header (38 in aitasks) is shown beside its seeds as context | one commit per batch: the rewritten test files |
| 8 | **enable** | `readiness` | which profile(s) get `testmap_check` and `testmap_fresh` in `default_gates` (and `rendered_gates` when present); `bootstrap_until` = today + 30; `docs:` paths and `notes:` lines for the brief; `testmap_run` only if `READINESS_DECISION:ADMISSIBLE` | `aitasks/metadata/profiles/<p>.yaml` (via `./ait git`), `config.yaml` |
| 9 | **finish** | `onboard finish` | `onboard status` green (no `pending` phase, seed queue ≤ a threshold the user sets, `check` clean); flips `require_stamp: true` and `--strict`; archives the task | `config.yaml` |

Phase 7 may be left `partial`: the remainder migrates through the
`testmap_fresh` gate a few files per task. `enable` and `finish` do not wait
for it. A repository that finishes onboarding with 960 pending seeds is
"selecting on 84 % of tests, claiming on 18 %", and `onboard status` says so.

### Detection, per target repository

| repo | detected | runner table written | scaffold needed |
|---|---|---|---|
| aitasks | `tests/test_*.sh` + `tests/lib/asserts.sh`; `tests/run_all_python_tests.sh` (pytest lane with the serial carve-out); `test_command` unset | `bash-file` over `tests/test_*.sh`; `pytest` (`testmap:batch no` on the four carve-out modules, pinned by extending `test_serial_carveout_doc_drift.sh`); `full` = `bash tests/run_all_python_tests.sh` + every bash test, children from junitxml and per-file exit | none |
| thinking_app | `gradlew`, `app/src/test/java` (334 files), `test_command: screenshot-tests.sh verify-active`, the two membership manifests, `matrix_classes` | `gradle-class`; `screen-matrix` (axis detected by the grid heuristic: 297 goldens over 10 matrices); `verify-active` as `full: true` with `children:` | `runner scaffold gradle-class --as screen-matrix` → `tools/verification/testmap_runner.sh`, whose `list` the project fills from the manifests (n006's runner, arrived at by scaffold) |
| thinking_backend | `scripts/tests/run_script_tests.sh` under `verify_build`; `test_*.sh` and `test_*.py` under `scripts/tests/` | `bash-file`, `pytest`; `full` = `run_script_tests.sh`; detect proposes `test_command:` = the same script with confirmation | none |
| aitasks_go | `go.mod`, 55 `_test.go`, `Makefile test`, `parity/run_parity.sh` (tmux + venv) | `go-test`; `parity` as `suite`, kind e2e, areas from `widget/`, `style/`, resource `tmux` | none |
| aitasks_mobile | `gradlew`; `shared/src/{commonTest,androidHostTest}`, `domain/src/{commonTest,androidDeviceTest}`, `dbaccess/src/{commonTest,androidDeviceTest}` | one `gradle-class` per source set: `commonTest` and `androidHostTest` unit, `androidDeviceTest` kind device with an `emulator` allocator resource — a kind/runner distinction, no axis (n006 open question 9) | none |

### Seed origins, measured

| origin | rule | aitasks bash (400) | aitasks Python (320) | thinking_app (307–339) | base confidence |
|---|---|---|---|---|---|
| naming | `test_<x>.sh → aitask_<x>.sh \| lib/<x>.{sh,py}`; `test_<x>.py → <x>.py`; `<Stem>Test.kt → <Stem>.kt` | 72 (18 %) | 62 (19 %) | 48 (16 %) | 0.60 |
| invocation | a literal `.aitask-scripts/…` path in the test body | 350 (88 %), 3 paths avg | — | — | 0.90 |
| imports | direct `import` / `from` of a main-root file (same-package facts excluded) | — | 255 (80 %), 1 avg | 139 (41 %), 3 avg | 0.85 |
| cochange | (test, source) in ≥ `min_cochange` distinct `(t<id>)` commits | 439/600 commits, 2.8 × 2.6 | same pass | 127/400 commits, 7.2 main files avg | 0.50 + 0.10/extra task ≤ 0.80 |
| coverage | per-unit runtime coverage (coverage.py dynamic contexts; `go test -run <unit> -coverprofile`; LCOV with a test column; project plugin) | opt-in | opt-in | JaCoCo per-test sessions = project plugin | 0.95 |

The invocation and imports origins are the same facts `internal/deps` already
scans for the test-side closure — read once, cached by blob. Only the **direct**
relation is seeded; the deeper closure is the selector's d2 walk and would be
noise as an edge. Co-change is one `git log --name-status -M
--format=%H%x00%s` pass over commits whose subject matches `(t<id>)`, counted
per distinct task id, cached by HEAD sha under the XDG cache; a shallow clone
seeds fewer rows and says so (`SEED_HISTORY:shallow|<n commits>`). Confidence
is a fixed table combined by noisy-OR; it orders the review queue and never
hides a row.

### What seeding cannot do, stated

thinking_app's tests resolve imports for 139 of 339 files because same-package
references need no import and the Kotlin scanner's "same package is fully
connected" fact is too coarse to seed; fixture-driven tests and screen members
seed through `annotate --from-body` (n006) rather than through this table;
sources reached by no origin stay `UNMAPPED_SOURCE:` until a rule, a waiver, a
Step-7 prompt or a coverage import maps them. The design treats that as a state
the ledger reports, not a failure it hides.
<!-- /section: onboarding -->

<!-- section: run_surface [dimensions: component_test_front_verb, component_agent_brief, requirements_agent_run_surface, assumption_instructions_block_reaches_agents, assumption_helper_degrades_when_absent, assumption_change_surface_is_intake] -->
## The Run Surface an Agent Learns Once

### `ait test`

```
ait test --task <id> [--mode run|show] [--json]     the tests the task's attributed change reaches
ait test <path>... [--mode run|show]                the tests reaching those sources; a test path runs that unit (and its variants)
ait test --all                                      every registered unit through the runners — the completion gate
ait test brief [--md]                               this project's run brief
ait test explain <path>                             = ait testmap explain (why a unit is or is not selected)
```

Output of a `--task` run, in order: `SELECTED:<n>|<est_s>|<seeded_n>`, one
`UNMAPPED_SOURCE:<path>` per changed source no unit reaches, the ranked rows
with n006's reasons (a seeded edge reads `edge(seeded:invocation,cochange)`),
the schedule's wave lines, results per id, and `RESULT:pass|fail|skip|deferred|<run_id>`.
`--task` goes through the change surface exactly as the gates do — `UNKNOWN:`
refuses with the paths named; `OTHER:` is never selected on. `<path>...` is the
one explicit-list intake (treated as `TASK:` rows). `--all` has no intake and
is `run --all`: it anchors evidence and scores the newest prediction.

### `ait test brief` on thinking_app (after onboarding)

```
TESTMAP:onboarded|since 2026-09-16|seeds pending 412
RUNNER:gradle-class|unit|371 classes|screenshot-tests.sh unit-tests --tests <class>|heavy-run
RUNNER:screen-matrix|unit (variant, axis matrix)|49 members x 10 matrices = 297|screenshot-tests.sh unit-tests --tests <class>.<method>|heavy-run
RUNNER:verify-active|suite (full)|1|screenshot-tests.sh verify-active|heavy-run
FULL_GATE:verify-active|p95 1180s|= project_config test_command
VERBS:ait test --task <id> | ait test <path>... | ait test --all | ait test brief
AXES:matrix|facets locale,direction,geometry|10 values
RESOURCE:heavy-run|admission (tools/verification/heavy-run-lock.sh)|refusal = exit 75 -> deferred to run deadline
DOCS:aidocs/testing/rendering-verification.md
DOCS:aidocs/testing/change-aware-verification.md
NOTES:A shared component change (ui/components/*) must run the full gate; preview renders without a verdict.
NOTES:Never run ./gradlew test directly - the harness owns the heavy-run slot and the run id.
```

`--md` renders the same facts as markdown. Everything above `DOCS:` is computed
from the registry; `DOCS:` and `NOTES:` are what the onboarding `enable` phase
asked the maintainer for — the judgement calls the registry cannot hold, kept
to ten lines and reached through one verb.

### The generic instructions block

Added to `seed/aitasks_agent_instructions.seed.md`, therefore inserted between
the `>>>aitasks` / `<<<aitasks` markers of every supported agent's instructions
file on the next `ait setup` or `ait upgrade` — the mechanism
`assemble_aitasks_instructions()` / `insert_aitasks_instructions()` already
implements — with no per-project edit:

```markdown
## Running Tests

This project's tests may be registered with the change-aware test map (`aitestmap/`).

- `ait test brief` — this project's runners, resources, full gate, and notes. Run it
  before invoking any test tool directly; prefer the registered runner it names.
- `ait test --task <id>` — the tests the task's change reaches, with a reason per row.
- `ait test <path>...` — the tests reaching those sources, or those test files.
- `ait test --all` — the full registered suite; this is the completion gate.
- A new test file needs `testmap:` annotations (`/aitask-testmap`); a changed source
  no test reaches is reported as `UNMAPPED_SOURCE` — map it before the gate.
- `TESTMAP:absent` means the project is not onboarded — `/aitask-testmap-onboard`.
```

Twelve lines, no agent named, identical everywhere. What varies per project
comes out of `brief`.

### The workflow helper

```
./.aitask-scripts/aitask_affected_tests.sh <task_id> [--mode run|show]
  stdout (data channel, KEY:value only):
    VERDICT:pass|fail|skip
    REASON:all_passed|command_failed|testmap_absent|registry_absent|unknown_paths|no_selection|admission_refused
    DETAIL:<one line>
    LOG:.aitask-gates/<task>/affected_<run-id>.log
    SELECTED:<n>|<est_s>|<seeded_n>
    UNMAPPED_SOURCE:<path>          (0..n lines)
    UNKNOWN:<path>                  (0..n lines, with REASON:unknown_paths)
  exit: 0 pass · 1 fail · 2 skip · 3 usage / log unwritable   (aitask_run_project_command.sh's contract)
```

It sources `lib/aitasks_home.sh` and the shim, writes the engine's full output
to the log, appends nothing to any ledger, and is allowlisted on the five
touchpoints (`tests/test_touchpoint_count_contract.sh` re-pinned). Every
absence is a *reason*, never an error: this is what lets the procedure below
run in `remote` on Claude Code Web, where there is no engine, and print one
line.
<!-- /section: run_surface -->

<!-- section: workflow_seam [dimensions: component_workflow_integration, requirements_workflow_seam, assumption_gate_exit_contract_reused, assumption_helper_degrades_when_absent] -->
## The Workflow Seam

### task-workflow Step 7 — the Affected Tests Procedure (`affected-tests.md`)

Rendered into Step 7 under `{% if profile.affected_tests is not defined or
profile.affected_tests != 'off' %}`, at two points:

- **While implementing.** One sentence after "Follow the approved plan": *"After
  editing a source, run the Affected Tests Procedure (`affected-tests.md`) rather
  than the full suite; the full gate remains the completion criterion."* This is
  the iteration loop the mandate asks for — an agent runs the right tests
  without deciding which those are.
- **Before Step 8.** Once, the pre-review affected run, so the reviewer sees a
  verdict for the tests the change reaches before approving the commit.

The procedure body, mirroring `build-verification.md` so the two cannot
disagree about an exit code:

```bash
if at_out="$(./.aitask-scripts/aitask_affected_tests.sh <task_id> --mode {{ 'show' if profile.affected_tests == 'show' else 'run' }})"; then
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
| `at_rc` 3 or empty verdict | infrastructure — diagnose the helper / engine; never "fix the code"; never a pass |
| `pass` | display `SELECTED:` and continue |
| `fail` | read `at_log`; caused by this task → fix and re-run; unrelated → log under **Affected tests** in the plan's Final Implementation Notes and proceed (the `build-verification.md` loop, verbatim) |
| `skip` · `no_selection` | display the `UNMAPPED_SOURCE:` paths; **offer** (`AskUserQuestion`, non-skippable in attended profiles): *Annotate now* (`/aitask-testmap` → `annotate` / a rule) · *Propose for review* (`attribute --propose`, lands in `seeded.yaml`) · *Continue unmapped*. Autonomous profiles take *Propose for review*. This is the moment a new coupling is cheapest to record |
| `skip` · `unknown_paths` | the Step-2b-style scope prompt from `aitask-gate-docs-updated`: include / subset / exclude; autonomous profiles exclude and log |
| `skip` · `admission_refused` | print `at_detail` (the host refused the heavy slot until the deadline); continue — nothing failed |
| `skip` · `testmap_absent` / `registry_absent` | one line; continue — the repository is not onboarded or this host has no engine |

The verdict line (`- **Affected tests:** pass (14 units, est 41 s) — log …`)
is written into the plan's Final Implementation Notes and **never** into the
gate ledger: Step 7's run is advisory, and a task that declares `testmap_run`
has the Step-9 orchestrator record the real gate. No double record, no
`record_gates` guard needed.

Profile key `affected_tests: run|show|off` — `run` when omitted (the whole
point is that an agent runs the right tests without being told); `show` prints
the selection and runs nothing; `off` renders the procedure away. `default.yaml`
and `fast.yaml` omit it; `remote.yaml` sets `run` (on Web the helper prints
`skip:testmap_absent`, so the key costs nothing there). Documented as one row in
`profiles.md`; goldens regenerated for every profile × agent;
`aitask_skill_verify.sh` run before commit.

### Step 8 — unchanged dispatch, one new step inside the gate

The procedure-gate block already dispatches `testmap_fresh` before the change
summary (n006). Inside `aitask-gate-testmap-fresh`, after the `STALE` /
`STALE_PATH` / `UNSTAMPED` handling, one new step: for every `COMMITTED:` /
`TASK:` path that is a test file with rows in `seeded.yaml`, show the seeds
with their evidence and offer *accept / reject / leave* per row. Accepted rows
are written through the rewriter and ride the same `(t<id>)` commit as the
test edit. This is the incremental half of adoption — and the reason
onboarding's `accept` phase may stop early.

### Step 9 — untouched

The gate orchestrator runs `testmap_check` / `testmap_run` when declared; the
legacy path runs `build-verification.md` (`verify_build`). Neither changes. A
project whose completion gate is a full suite keeps `tests_pass` (n006).

### aitask-qa

- `test-discovery.md` 3a–3c: when `aitestmap/` exists, `ait testmap explain
  --sources <changed files> --format table` gives the Source / Test / Reason /
  Status map directly — `Covered` for an accepted edge, `Covered (seeded)` for a
  seed, `GAP` for `UNMAPPED_SOURCE`; the naming-convention scan stays as the
  fallback for a repository without a map. The health score's coverage
  component reads the same rows.
- `test-execution.md` 4a: prefer `ait test --task <id>` and keep its
  `SELECTED:`; `test_command` remains what the exhaustive tier's verification
  gate (4e) re-runs fresh, because that step is defined as the full run.

### aitask-pickrem / aitask-pickweb / ait setup

Both inherit Step 7 through the shared task-workflow; pickweb sees a printed
`skip:testmap_absent`. `ait setup` prints `TESTMAP:absent|bootstrapping|<next>|onboarded|engine-missing`
after the engine line and, on `absent`, the hint `run /aitask-testmap-onboard`.
Setup never onboards.

### Verification of the seam itself

`tests/test_affected_tests_helper.sh` (every `REASON:` against fixture
registries in scratch git repos; an absent engine; exit-code ↔ verdict
agreement with `aitask_run_project_command.sh`'s table);
`tests/test_agent_instructions_running_tests.sh` (the section lands in
`CLAUDE.md` / `AGENTS.md` through a real `install.sh --dir`);
`tests/test_testmap_onboard_ledger.sh` (resume from each phase; idempotent
re-run; `--no-task`); engine tests for each seed origin on fixture repos with
synthetic `(t<id>)` histories and one fixture per detect shape; the
task-workflow goldens; `tests/test_touchpoint_count_contract.sh`.
<!-- /section: workflow_seam -->

<!-- section: data_flow [dimensions: component_onboarding_skill, component_seeder, component_test_front_verb, component_workflow_integration, component_selector, component_annotation_scanner, component_freshness, component_feedback_tools, component_cost_ledger, component_engine_packaging] -->
## Data Flow

### Onboarding (once per repository)

```
tree + project_config.yaml ──▶ onboard detect --write ──▶ aitestmap/{config,runners,resources}.yaml · registry/areas.yaml
                                                          (runner table confirmed per runner by the skill)
runners' list + scan ─────────▶ onboard inventory ───────▶ _scanned.yaml · UNREGISTERED: resolved (bind | exclude:)
classify --suggest ───────────▶ CLASSIFY:<test>|<kind>|<reason> ──confirm──▶ _scoped.yaml (scan --apply)
deps facts (invocation, imports) + naming rules + git log (t<id>) co-change [+ coverage] ──▶ seed --apply ──▶ registry/seeded.yaml
check / explain --sources ────▶ UNMAPPED_SOURCE clusters ──confirm──▶ rules / waivers in registry/<area>.yaml
ait test --all ───────────────▶ runs · child rows · ledger.jsonl ──costs --update──▶ costs/<hostclass>.yaml (last_pass on every id)
onboard accept --area <a> --batch 50 ──▶ rewriter ──▶ testmap:covers lines + stamps in test files; rows leave seeded.yaml
readiness + profile edit ─────▶ default_gates += [testmap_check, testmap_fresh] · bootstrap_until · docs: · notes:
onboard finish ───────────────▶ require_stamp: true · strict · task archived
every phase ──▶ onboard.yaml row ──▶ chore: Onboard testmap — <phase> (t<id>) commit (paths named)
```

### A task, steady state

```
Step 7  edit source ──▶ aitask_affected_tests.sh <id> ──▶ change surface ──▶ test --task ──▶ select (edges ∪ seeds ∪ deps ∪ rules ∪ axes)
                                                             ──▶ schedule ──▶ run ──▶ ledger rows (run_id test-…) ──▶ VERDICT:/SELECTED:/UNMAPPED_SOURCE:
        UNMAPPED_SOURCE ──offer──▶ annotate | attribute --propose (→ seeded.yaml, origin observed) | continue
Step 8  procedure gates ──▶ testmap_fresh ──▶ stale --task … (n006) + accept seeds on touched test files ──▶ rewrites ride the (t<id>) commit
Step 9  ait gates run ──▶ testmap_check (SEEDED:<n>, UNMAPPED_SOURCE:, strict past bootstrap) ──▶ testmap_run | tests_pass (n006)
full run (any) ──▶ automatic score ──▶ PREDICTION_MISSED:<id> ──▶ attribute (decide | --propose → seeded.yaml)
```

### Reading the map without running anything

```
ait test brief ──▶ registry + config.yaml docs:/notes: + onboard.yaml ──▶ TESTMAP:/RUNNER:/FULL_GATE:/VERBS:/AXES:/RESOURCE:/DOCS:/NOTES:
aitask-qa 3a ──▶ ait testmap explain --sources <changed> --format table ──▶ Covered | Covered (seeded) | GAP
ait setup ──▶ report_testmap_state() ──▶ TESTMAP:<state>
```
<!-- /section: data_flow -->

<!-- section: components [dimensions: component_*] -->
## Components

*(inherited from n006, unchanged)* means the component is carried as n006
specified it; *(n006 + …)* names the addition; *(new)* is introduced here.

<!-- section: component_onboarding_skill [dimensions: component_onboarding_skill] -->
### Onboarding skill and verbs *(new)*

`.claude/skills/aitask-testmap-onboard/` — a static, attended-only skill:
`SKILL.md` (invocation, task creation, `onboard status` → `ONBOARD_NEXT:`
dispatch) plus one procedure file per phase (`detect.md`, `inventory.md`,
`classify.md`, `seed.md`, `waivers.md`, `full-run.md`, `accept.md`,
`enable.md`, `finish.md`), each ending with the phase's commit and ledger row.
Engine verbs: `onboard detect [--write]` (prints `DETECT:<tool>|<root>|<evidence>`
and `RUNNER_PROPOSED:<name>|<builtin>|<glob>|<command>`; `--write` emits the
skeleton), `onboard inventory`, `onboard status` (phase rows, seed queue per
origin, tests-with-edge and sources-with-edge ratios, oldest pending seed,
`ONBOARD_NEXT:`), `onboard accept (<test>[#member] | --area <a> | --batch <n> |
--files-from -) [--min-confidence]`, `onboard reject <test> <source> --reason`,
`onboard finish`. All phases idempotent; re-running `detect --write` on an
existing table prints `DETECT_DIFF:` and writes nothing without `--force`.
Wrapper surfaces for Codex and OpenCode regenerated with
`aitask_audit_wrappers.sh apply-wrapper`. Tests: `test_testmap_onboard_ledger.sh`
and one engine fixture per detect shape.
<!-- /section: component_onboarding_skill -->

<!-- section: component_seeder [dimensions: component_seeder] -->
### Seeder *(new)*

`internal/seed`: origins **naming** (per-runner stem rules), **invocation**
(bash literal paths), **imports** (direct main-root imports from the python /
kotlin / go scanners; same-package facts excluded), **cochange** (one
`git log --name-status -M --format=%H%x00%s` pass over `(t<id>)` commits,
pairs counted per distinct task, `--min-cochange 2`, cached by HEAD sha,
`SEED_HISTORY:shallow|<n>` on a shallow clone) and **coverage** (opt-in:
coverage.py contexts JSON, `go test -run <unit> -coverprofile`, LCOV with a
test column, or a plugin printing `{test, covers}` lines). Confidence table
naming 0.60 / invocation 0.90 / imports 0.85 / cochange 0.50 + 0.10 per extra
task ≤ 0.80 / coverage 0.95 / observed 0.70, combined by noisy-OR; ordering
only. Output `SEED:<test>|<source>|<origins>|<confidence>` lines, `--apply`
writes `registry/seeded.yaml` deterministically sorted. Rejected pairs
(`onboard.yaml`) are never re-proposed; accepted pairs are dropped with
`SEED_SHADOWED`. Budget: naming+invocation+imports < 2 s, cochange < 5 s over
600 commits on the aitasks shape. Fixtures: a synthetic repo per origin.
<!-- /section: component_seeder -->

<!-- section: component_test_front_verb [dimensions: component_test_front_verb] -->
### Front verb and workflow helper *(new)*

`ait test` in the dispatcher → `aitask_testmap.sh test` → engine `test`
composite (`--task`, `<path>...`, `--all`, `brief`, `--mode run|show`,
`--json`) printing `SELECTED:`, `UNMAPPED_SOURCE:`, the rows, waves, results
and `RESULT:`. `aitask_affected_tests.sh <task_id> [--mode]` is the workflow
seam: the `VERDICT:/REASON:/DETAIL:/LOG:/SELECTED:/UNMAPPED_SOURCE:/UNKNOWN:`
lines, exit `0/1/2/3` on `aitask_run_project_command.sh`'s contract, stderr for
humans only, log under `.aitask-gates/<task>/affected_<run-id>.log`, no ledger
append. Five allowlist touchpoints. `tests/test_affected_tests_helper.sh`.
<!-- /section: component_test_front_verb -->

<!-- section: component_agent_brief [dimensions: component_agent_brief] -->
### Agent brief and instructions *(new)*

`internal/brief`: `brief [--md]` → `TESTMAP:`, `RUNNER:` per runner (name, kind,
unit count from `list`, invocation shape from `runners.yaml` / the builtin,
resources), `FULL_GATE:` (the `full` runner, its p95 from costs, `= test_command`
when it wraps it), `VERBS:`, `AXES:`, `RESOURCE:` per declared resource with
its refusal semantics, `DOCS:` per `config.yaml docs:`, `NOTES:` verbatim,
`ONBOARD_NEXT:` while bootstrapping; < 100 ms warm. The generic `## Running
Tests` section in `seed/aitasks_agent_instructions.seed.md` (twelve lines, no
agent named). `tests/test_agent_instructions_running_tests.sh`.
<!-- /section: component_agent_brief -->

<!-- section: component_workflow_integration [dimensions: component_workflow_integration] -->
### Workflow integration *(new)*

`task-workflow/affected-tests.md` at two Step-7 points behind `affected_tests`
(`run` default; `show`; `off`); the branch table above; the plan-notes record;
no ledger write. `aitask-gate-testmap-fresh` gains the accept-on-touched-files
step. `aitask-qa/test-discovery.md` registry-first, `test-execution.md` 4a
prefers `ait test --task`. `profiles.md` row; `remote.yaml: affected_tests:
run`. Goldens regenerated; `aitask_skill_verify.sh`. pickrem / pickweb inherit;
`ait setup` prints `TESTMAP:`.
<!-- /section: component_workflow_integration -->

<!-- section: component_go_engine [dimensions: component_go_engine] -->
### Go engine and CLI *(n006 + three packages)*

n006's `engine/cmd/ait-testmap` and `internal/*` unchanged; adds
`internal/seed`, `internal/onboard`, `internal/brief`. Same toolchain, deps
and boundary: the engine reads `onboard.yaml`'s `task:` and writes its phase
rows; task creation, profile edits and commits are the skill's, through the
framework's scripts. Fixture repos gain synthetic `(t<id>)` histories.
<!-- /section: component_go_engine -->

<!-- section: component_engine_binary [dimensions: component_engine_binary] -->
### Engine binary *(n006 + verbs and budgets)*

Verb table + `test`, `brief`, `seed`, `onboard {detect,inventory,status,accept,reject,finish}`,
`runner scaffold`. Budgets added (brief < 100 ms, seed < 2 s / cochange < 5 s,
onboard status < 200 ms) under the same `go test -bench` 2× rule. Contract
stays 1; `seeded.yaml` and `onboard.yaml` carry `contract:` and a newer one is
refused with `CONTRACT_MISMATCH`.
<!-- /section: component_engine_binary -->

<!-- section: component_user_root [dimensions: component_user_root] -->
### Per-user root *(inherited from n006, unchanged)*

`lib/aitasks_home.sh`, `AITASKS_HOME` defaulting to `~/.aitasks`, no fallback;
sourced additionally by `aitask_affected_tests.sh`.
<!-- /section: component_user_root -->

<!-- section: component_framework_home [dimensions: component_framework_home] -->
### Framework home: report and migration verb *(inherited from n006, unchanged)*

`ait engine home [--migrate]` as n006 specified, known set including
`pypy_venv`, default flip a named follow-up.
<!-- /section: component_framework_home -->

<!-- section: component_binary_distribution [dimensions: component_binary_distribution] -->
### Binary distribution *(inherited from n006, unchanged)*

`engine/build.sh`, the `engine` job, `engine-check.yml`, the shim's handshake,
`test_testmap_shim.sh` / `test_platform_detect.sh` / `test_aitasks_home.sh`.
<!-- /section: component_binary_distribution -->

<!-- section: component_engine_packaging [dimensions: component_engine_packaging] -->
### Engine install, upgrade, regeneration *(n006 + `report_testmap_state()`)*

`install_engine_binary()` as n006; after it, `report_testmap_state()` prints
`TESTMAP:engine-missing|absent|bootstrapping|<next>|onboarded` with the
onboarding hint on `absent`. The re-inserted instructions block carries the
Running Tests section. `test_install_engine_binary.sh` asserts each state.
<!-- /section: component_engine_packaging -->

<!-- section: component_registry_loader [dimensions: component_registry_loader] -->
### Registry loader and writer *(n006 + the seeds table)*

Six tables plus `seeds` from `registry/seeded.yaml`; `SEED_SHADOWED` at load;
write routing `seed → seeded.yaml`, `onboard accept/reject → seeded.yaml +
onboard.yaml`; `config.yaml` `exclude:`, `docs:`, `notes:`, `broad_threshold_s`.
n006's id grammar, `owns:` routing, deterministic writes and check rules
unchanged; golden tests pin the seed merge and the shadow rule.
<!-- /section: component_registry_loader -->

<!-- section: component_variant_axes [dimensions: component_variant_axes] -->
### Variant axes *(inherited from n006, unchanged)*

`axes.yaml`, facets / values / sources, `<unit>@<variant>`, the facet join,
`testmap:axis`, `--axis`. The onboarding grid heuristic proposes an axis; a
person declares it.
<!-- /section: component_variant_axes -->

<!-- section: component_axes [dimensions: component_axes] -->
### Axis resolver verbs *(inherited from n006, unchanged)*

`axes --list | --check | --explain <path>`.
<!-- /section: component_axes -->

<!-- section: component_cell_enumeration [dimensions: component_cell_enumeration] -->
### Enumeration and reconciliation *(inherited from n006, unchanged)*

The runner's `list` is the universe; `variants:` persisted by `scan --apply`;
`UNCOVERED_VALUE` / `UNMAPPED_ARTIFACT`. Onboarding's inventory phase is the
first consumer of `UNREGISTERED:` rows as a to-do list.
<!-- /section: component_cell_enumeration -->

<!-- section: component_annotation_scanner [dimensions: component_annotation_scanner] -->
### Annotation scanner and rewriter *(n006 + accept as a writer)*

Grammar v3 and the rewriter unchanged; `onboard accept` inserts
`testmap:covers` lines at a fixed position per language (after the bash header
block; appended to the Python module docstring; a `//` block before the class
KDoc, or inside the member's `testmap:unit` block), stamped at accept time;
`# Covers:` prose headers shown as context, never parsed.
<!-- /section: component_annotation_scanner -->

<!-- section: component_dependency_scanners [dimensions: component_dependency_scanners] -->
### Dependency scanners *(n006; facts shared with the seeder)*

bash / python / go / kotlin / gradle scanners, the opaque contract, plugins,
`android-res`, the XDG cache — unchanged. Invocation and direct-import facts
for a test file are exposed to `internal/seed`; the closure is never seeded.
<!-- /section: component_dependency_scanners -->

<!-- section: component_selector [dimensions: component_selector] -->
### Selector *(n006 + seeded edges, `explain --sources`, the `test` summary lines)*

Seeded edges walked at d1 with `edge(seeded:<origins>)`, no stale mark;
`explain --sources <path>... --format table` for QA; `SELECTED:` and
`UNMAPPED_SOURCE:` lines ahead of the rows in `test`. Everything else as n006.
<!-- /section: component_selector -->

<!-- section: component_runner_contract [dimensions: component_runner_contract] -->
### Runner contract and repository *(inherited from n006, unchanged)*

`describe` / `list` / `run`, manifests, `results.jsonl`, `runner.json`,
bindings, `builtin:` with `command:` / `cwd:`, shadow-by-name, batching,
timeouts, reconciliation, exit contract `0/1/2/75/64`.
<!-- /section: component_runner_contract -->

<!-- section: component_scheduler_resources [dimensions: component_scheduler_resources] -->
### Scheduler and resources *(inherited from n006, unchanged)*

Kinds, scopes, `flock(2)` slots, admission deferral, allocators, waves,
`broad_after_unit`, ordering of admission-holding invocations last. An `ait
test --task` run on thinking_app is one Gradle invocation under the heavy-run
slot, and a refusal at the deadline is `VERDICT:skip REASON:admission_refused`.
<!-- /section: component_scheduler_resources -->

<!-- section: component_cost_ledger [dimensions: component_cost_ledger] -->
### Cost ledger *(n006; Step-7 runs are ordinary rows)*

Welford per (id, host class), invocation overhead rows, `costs --update`,
`last_pass`, flake rate, group costing, `predictions.yaml`. Affected runs use
`run_id` prefix `test-`, full runs `full-`; the `SELECTED:` estimate is the
budget's per-group sum.
<!-- /section: component_cost_ledger -->

<!-- section: component_evidence_join [dimensions: component_evidence_join] -->
### Evidence join *(inherited from n006, unchanged)*

Per reached variant; `EVIDENCED` only when every variant is anchored; never
rewrites. Seeded edges are not joined — they have no stamp to heal.
<!-- /section: component_evidence_join -->

<!-- section: component_feedback_tools [dimensions: component_feedback_tools] -->
### Feedback tools *(n006 + `attribute --propose`, `onboard status` metrics)*

`score` automatic after full runs; `attribute` gains `--propose` (default in
autonomous profiles) writing to `seeded.yaml` with origin `observed`;
`readiness` unchanged; `onboard status` reports the queue and ratios.
<!-- /section: component_feedback_tools -->

<!-- section: component_gates [dimensions: component_gates] -->
### Gates *(n006 + `SEEDED:` / `UNMAPPED_SOURCE:` rows; enabling sited in onboarding)*

`testmap_fresh`, `testmap_check`, `testmap_run` and their verifiers unchanged;
`testmap_check` reports `SEEDED:<n>` (never fails) and `UNMAPPED_SOURCE:<path>`
(fails under `--strict` past `bootstrap_until`); the onboarding `enable` phase
is what adds the gates to a profile, with confirmation; `testmap_run` only on
`READINESS_DECISION:ADMISSIBLE`.
<!-- /section: component_gates -->

<!-- section: component_skill [dimensions: component_skill] -->
### Skills *(n006 + onboarding hand-off and accept-in-gate)*

`aitask-testmap` opens with `ait test brief` and hands an un-onboarded repo to
`aitask-testmap-onboard`; `aitask-gate-testmap-fresh` gains the accept step for
touched test files; the onboarding skill is new (above). Claude Code first,
wrappers regenerated.
<!-- /section: component_skill -->

<!-- section: component_reference_runners [dimensions: component_reference_runners] -->
### Reference runners *(n006 + scaffold, the `full` wrapper, `list --invocations`)*

Builtins unchanged; `runner scaffold <builtin> --as <name>` emits a project
script whose `list` prints `SCAFFOLD_TODO` until filled (check reports it);
`onboard detect` writes the `full` suite runner wrapping `test_command` with a
builtin `children:` post-processor for pytest junitxml, bash-file names and
`go test -json`; `bash-file list --invocations` for the seeder.
<!-- /section: component_reference_runners -->

<!-- section: component_freshness [dimensions: component_freshness] -->
### Freshness *(n006 + one stamp writer, one gate step)*

Stamps written by `verify`, `annotate`, `stale --confirm*` and now `onboard
accept`; the `testmap_fresh` gate offers acceptance for the test files the
task touched, so the stamp rides the same commit as the edit.
<!-- /section: component_freshness -->

<!-- section: component_staleness_tool [dimensions: component_staleness_tool] -->
### Staleness tool *(n006; seeds excluded, `SEEDED:` summary)*

`stale` classes unchanged; seeded edges excluded from every class; `stale
--all` adds `SEEDED:<n>` beside `CHECK_STRUCTURAL:<n>`.
<!-- /section: component_staleness_tool -->

<!-- section: component_suite_registry [dimensions: component_suite_registry] -->
### Scoped-row registry and areas *(n006 + classify signals)*

`classify --suggest` adds the three onboarding signals — recorded p95 above
`broad_threshold_s`, a directory / source-set convention, a resource named in
the file — each printed as the reason on the `CLASSIFY:` line. Everything else
as n006.
<!-- /section: component_suite_registry -->

<!-- section: component_broad_test_scopes [dimensions: component_broad_test_scopes] -->
### Broad-test scheduling policy *(inherited from n006, unchanged)*

`broad_after_unit`, `device_policy`, `STALE_AREA`, opt-in `REVIEW_DUE`,
attribute widening, fixture pins, `full: true` suite rows with child rows.
<!-- /section: component_broad_test_scopes -->
<!-- /section: components -->

<!-- section: assumptions [dimensions: assumption_*] -->
## Assumptions

**New in this node**

- **assumption_test_tools_detectable** — the test tools of every target repo
  are recognisable from the tree and `project_config.yaml` without a build:
  verified on all five (aitasks bash + pytest lane; thinking_app gradlew +
  harness; thinking_backend `run_script_tests.sh` under `verify_build`;
  aitasks_go `Makefile test` + parity; aitasks_mobile three source-set roots).
  Falsifier: build-time test generation → `DETECT_UNKNOWN`, the skill asks.
- **assumption_seed_sources_measured** — the four origins seed what the table
  above says (naming 16–19 %, invocation 88 %, imports 80 % / 41 %, co-change
  439/600 tight vs 127/400 noisy), measured 2026-09-16; coverage is the fifth,
  opt-in; confidence orders, never hides; seeding is partial by construction.
- **assumption_seeds_select_never_evidence** — a seed may cause a test to run
  and may never suppress `STALE`, anchor evidence, satisfy `require_stamp` or
  count under `--strict`; the only promotion is an explicit accept. Falsifier:
  a suite so expensive that over-selection is the cost problem — the budget and
  tokens preview are the levers, not trusting seeds.
- **assumption_instructions_block_reaches_agents** — the `>>>aitasks` marker
  block is written and refreshed by `ait setup` / `ait upgrade` into every
  supported agent's instructions file (verified in `assemble_aitasks_instructions`
  / `insert_aitasks_instructions`), so one seed edit reaches every project; the
  section names no agent and stays under twelve lines.
- **assumption_helper_degrades_when_absent** — `aitask_affected_tests.sh`
  always answers: absent engine / registry / `UNKNOWN:` rows / empty selection /
  admission refusal are `skip` reasons; only an executed run is pass / fail;
  only an unwritable log is 3. This is what admits the procedure into every
  profile including `remote`.
- **assumption_onboarding_is_a_task** — onboarding writes committed files over
  several sessions, so it runs as an aitask created and claimed by the skill,
  commits per phase under `(t<id>)`, resumes at `ONBOARD_NEXT:`, archives on
  `finish`; `--no-task` prints the commits to run for a repo that forbids tasks
  on the code branch.

**Modified from n006**

- **assumption_change_surface_is_intake** — also the intake for `ait test
  --task` and the helper, so the Step-7 run is attributed exactly as the gates
  are; `<path>...` is the one explicit-list intake; `--all` has none.

**Inherited from n006 unchanged** — carried verbatim in the node metadata:
assumption_areas_express_suite_blast_radius, assumption_axis_membership_declarable,
assumption_axis_sources_declarable, assumption_batch_per_unit_timing_reportable,
assumption_blob_digest_is_staleness_key, assumption_broad_tests_area_scoped,
assumption_cells_enumerable_by_plugin, assumption_engine_latency_targets,
assumption_existing_locks_wrappable, assumption_gate_exit_contract_reused (the
helper's `0/1/2/3` is `aitask_run_project_command.sh`'s table, not a third
mapping), assumption_git_history_is_freshness_clock (co-change reads history
as a *seed* source, never as a freshness or evidence source),
assumption_go_toolchain_available, assumption_go_toolchain_ci_and_dev_only,
assumption_home_symlink_compatibility, assumption_kotlin_scanner_fail_closed,
assumption_legacy_user_root_coexists, assumption_one_engine_per_framework_version,
assumption_passing_run_anchors_edges, assumption_platform_matrix_sufficient,
assumption_release_asset_reachable, assumption_release_assets_reachable,
assumption_static_granularity_v1, assumption_target_repos_accept_aitestmap_root
(now also `onboard.yaml` and `registry/seeded.yaml` under that root),
assumption_testmap_token_no_collision, assumption_variant_universe_from_runner_list.
<!-- /section: assumptions -->

<!-- section: tradeoffs [dimensions: tradeoff_*] -->
## Tradeoffs

**Advantages**

- **tradeoff_computed_vs_prose** *(n006, extended)* — selection is computed,
  explained and scored; so now is the run surface: the brief is generated, the
  instructions section is identical everywhere, and a 200-line testing chapter
  becomes ten declared `notes:` lines plus `docs:` pointers reached through one
  verb.
- **tradeoff_engine_speed_enables_per_task_use**, **tradeoff_real_scheduler**,
  **tradeoff_noarch_packages_preserved** *(inherited from n006, unchanged)*.

**Disadvantages and risks — new**

- **tradeoff_seed_noise** — heuristic seeds are wrong in both directions
  (homonyms, helper imports, wide co-changing tasks at 7.2 files); mitigated by
  seeds selecting and never claiming, confidence ordering review not gating it,
  `min_cochange 2` across distinct tasks, direct imports only, evidence beside
  every row, rejection memory, and the suite budget for a repo where
  over-selection is expensive; reviewer fatigue on a 1,000-row queue is spread
  by per-area batches and the in-gate path.
- **tradeoff_two_edge_states_during_adoption** — until the queue empties a
  repo has accepted and seeded edges side by side; mitigated by the origin on
  every row, `SEEDED:<n>` on check and stale, `onboard status` as the one ratio;
  the real cost is that `--strict` cannot be enabled while `UNMAPPED_SOURCE`
  rows are only seed-covered, which is visible rather than silent.
- **tradeoff_generated_brief_limits** — a computed brief cannot hold a
  project's judgement calls; `docs:` and `notes:` carry them one hop away, and
  the full gate backstops a misread note.
- **tradeoff_workflow_surface_growth** — one procedure file, one profile key,
  one dispatcher verb, one skill-invoked helper (five allowlist touchpoints), a
  Step-7 render across every profile × agent golden, two QA edits, a seed edit
  and a static skill with two wrappers; mitigated by uniform degradation to a
  printed skip, the reused `VERDICT:` contract, and `aitask_skill_verify.sh`
  plus the goldens.
- **tradeoff_accept_rewrites_history** — acceptance inserts comment lines into
  hundreds of test files (blame noise, header conflicts); mitigated by fixed
  insertion positions, per-area batch commits, the in-task incremental path and
  `REWRITE_CONFLICT`; a project may keep seeds unaccepted and live with
  selection-only enforcement, reported as such.
- **tradeoff_onboarding_partial_coverage** — what no origin reaches stays
  `UNMAPPED_SOURCE` or area-only (thinking_app's same-package tests, fixture
  tests); mitigated by rules and expiring waivers, the Step-7 prompt that maps a
  source the first time a task touches it, opt-in coverage, and the full gate as
  the completion criterion.

**Disadvantages and risks — modified from n006**

- **tradeoff_fail_closed_bootstrap_cost** — now owned by the onboarding ledger
  rather than described: the seeder replaces most of the hand waiver pass, the
  first full run is the existing `test_command` wrapped, acceptance is
  incremental; what remains is the judgement in classify and accept.
- **tradeoff_attribution_risk** — narrowed further by the Step-7
  `UNMAPPED_SOURCE` prompt at the moment a source is introduced; a coupling to
  an already-edged source is still only caught by score.
- **tradeoff_stamp_churn** — onboarding's acceptance is the largest rewrite of
  all; mitigated by seeds selecting without any rewrite, batch commits that add
  comment lines only, and the incremental path.
- **tradeoff_engine_absent_on_host** — the workflow helper is the one
  deliberate exception to "never skip": an advisory Step-7 run prints
  `skip:testmap_absent` and the task continues; declared gates still exit 3.

**Inherited from n006 unchanged** — carried verbatim in the node metadata:
tradeoff_area_glob_coarseness, tradeoff_autonomous_confirmation_weak,
tradeoff_axis_declaration_burden, tradeoff_axis_projection_coarseness,
tradeoff_batch_misreport_risk, tradeoff_broad_scope_coarseness,
tradeoff_cell_table_size, tradeoff_compiled_component_cost,
tradeoff_engine_version_skew, tradeoff_evidence_requires_reachable_history,
tradeoff_flaky_pass_anchors, tradeoff_home_migration_window,
tradeoff_intersection_can_underselect, tradeoff_member_annotation_drift,
tradeoff_registry_directory_complexity (one more generated file and one
ledger, both under the same root and merge rule),
tradeoff_resource_declaration_completeness, tradeoff_setup_network_fetch,
tradeoff_split_home_rejected, tradeoff_static_scanner_overselection,
tradeoff_strict_version_handshake, tradeoff_two_toolchains,
tradeoff_two_user_roots, tradeoff_whole_run_filter_soundness.
<!-- /section: tradeoffs -->

<!-- section: open_questions -->
## Open Questions

1. Should `affected_tests` default to `run` or `show` when a repository's
   affected run is expensive (thinking_app: one Gradle boot under the heavy-run
   lock, ~40 s minimum)? Proposed: `run`, because the scheduler already defers
   on a refused slot and the estimate is printed first; a project may set
   `show` in its profile.
2. Should `onboard accept --batch` be allowed to auto-accept rows above a
   confidence threshold (e.g. invocation + naming ≥ 0.95) in an autonomous
   profile? Proposed: no — acceptance is the one act that turns a heuristic
   into a claim; `attribute --propose` and seeds already give autonomy the
   safe half.
3. Where does the co-change origin stop being useful — should it be off by
   default for repositories whose task commits average more than N files
   (thinking_app's 7.2)? Proposed: keep it on with `min_cochange 2` and print
   the noise figure in the seed report so the maintainer decides.
4. Should the Running Tests section be a Layer-2 (per-agent) addition instead
   of Layer 1, so a project that has not installed the engine sees nothing?
   Proposed: Layer 1 — the section's last line is the not-onboarded case, and a
   uniform block is the point.
5. Should `aitask-qa`'s health score treat a seeded edge as coverage (proposed:
   yes, shown as `Covered (seeded)` and weighted the same — QA measures whether
   a test exists, not whether its claim is fresh) or discount it?
6. Should the `full` suite wrapper's `children:` post-processor for bash-file
   tests infer per-file results from the runner's own per-file exit (available
   when `full` iterates the files) or require junit-style output? Proposed: the
   per-file exit; a project with a monolithic script gets suite-level evidence
   only.
7. Should `onboard finish` refuse while any `pending` seeds remain, or accept a
   user-set threshold? Proposed: threshold, default 0, printed in `status`.
8. Baseline questions still open (n006 §Open Questions 1–11), unchanged, with
   9 (aitasks_mobile's axis) answered here as a kind/runner distinction.
<!-- /section: open_questions -->