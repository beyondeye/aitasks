<!-- section: overview [dimensions: requirements_*] -->
## Overview

The goal is unchanged: a framework feature, generic across `aitasks`,
`thinking_app`, `thinking_backend`, `aitasks_go` and `aitasks_mobile`, that
maintains a relation between source files and test units, translates a task's
change set into a ranked list of tests with a reason on every line, runs them
through project-defined runners under a standard contract, tracks cost per
unit by host class, learns from failures the map did not predict, is enforced
by gates, and is taught to agents by a skill. The engine — a static Go binary
under `$AITASKS_HOME/engine/v<VERSION>/`, per-edge blob-digest stamps healed by
a per-variant evidence join, scoped rows under a suite budget, member units
and variant axes, the graded walk, the real scheduler, the cost ledger,
automatic prediction scoring — is the n006 baseline that both n007 and n008
kept unchanged, and it is kept unchanged here. n001 and n002, the two
first-round parents, are the origin of that engine: every one of their
dimensions survives in n006 and therefore here, with the resolutions n003 made
between them (blob digest over commit-sha stamps, `_scoped.yaml` over a second
`suites/` directory, `engine/` over `go/`, built-in runners over bash scripts,
`$AITASKS_HOME/engine/` over `~/.aitask/bin/`) carried and recorded in
*Conflict Resolutions* rather than re-argued.

The two third-round parents answered the same mandate — *how does a repository
with an existing test tree get onto the map, how does any agent run tests
without learning the project, and how does that sit inside task-workflow* —
with designs that agree on most of the machinery and disagree on four things.
This node takes the stronger answer for each and bridges what the other side
got right:

**1. Machine-seeded edges have three provenances, not two.** n007 keeps every
heuristic edge in a `registry/seeded.yaml` queue that *selects but never
claims* until a person accepts it row by row; n008 lets a class-level "accept
all static edges" write stamped `testmap:covers` lines at once and records
their machine origin in `registry/adopted.yaml` until a human re-stamps them.
Both are right about different moments. The merged model is
**seeded → adopted → reviewed**: `onboard seed` fills the queue (select-only,
no stamp, invisible to `stale`, excluded from `--strict`, `SEEDED:<n>`
everywhere it matters); `onboard adopt --class <origin>` promotes a whole
evidence class to stamped edges with an `adopted.yaml` provenance row shown as
`adopted(...)` in `stale` and `explain` and counted as `ADOPTED_UNREVIEWED` by
`readiness`; `onboard adopt <test> <source>` (or the accept step inside the
`testmap_fresh` gate) promotes one reviewed pair with no provenance row. A seed
never satisfies `require_stamp`; an adopted edge does, because a person
accepted its class. Autonomous profiles may seed and may adopt only origins
whose confidence is a *language rule* (a `_test.go` file's own package, 1.0) —
never a heuristic — which is n007's "acceptance is the one act that turns a
heuristic into a claim" and n008's headless level 1 reconciled by the number
that distinguishes them.

**2. One seed table, one confidence vocabulary, measured on both sides.**
n007's five origins (naming, literal invocation, direct imports, `(t<id>)`
co-change, opt-in per-unit coverage) and n008's five signals (static closure,
convention, co-change, plan, prose) are the same facts named twice. The merged
table: `static:package` 1.0, `coverage` 0.95, `static:invocation` 0.90,
`static:import` 0.85, `observed` 0.70, `convention` 0.60, `plan` 0.50,
`prose` 0.30, `cochange` 0.20 + 0.20 per distinct task group, capped at 0.60
and requiring two distinct tasks — n008's cap because the measurement that
matters is that a `(t<id>)` group pairs a few tests with a few scripts and
nothing inside it says which covers which, so co-change corroborates and can
never reach the 0.85 class-acceptance threshold alone. Noisy-OR combination;
the queue is ordered by confidence and never hides a row.

**3. Onboarding is levels × phases, one aitask per level.** n008's four
graded levels (0 runners and universe, 1 stamped edges, 2 kinds / areas /
reads / batch / resources, 3 axes / members / runner scaffold) say *what* a
repository has; n007's phase ledger (`aitestmap/onboard.yaml`, every phase
idempotent and committed under `(t<id>)`, `ONBOARD_NEXT:` on re-entry) says
*how far a level's run got*. Each level is one aitask (a level may wait weeks
on full-run history); within it the skill's phase procedures run at
task-workflow Step 7 and commit per phase, Step 8 reviews the annotation diff,
and the level-0 task's own `tests_pass` at Step 9 is the **first full run that
anchors every unit's `last_pass`**. `readiness` prints `LEVEL:` from what
exists; `onboard status` prints `ONBOARD_NEXT:` from the ledger.

**4. One verb, one gate, one thin procedure.** `ait test` is n008's bash front
(`aitask_test.sh`: resolves mode, task, intake and completion policy by itself;
falls back to `test_command` where no registry exists and to a recorded
`fallback_command` where the engine is absent at completion) over n007's engine
`test` composite (select → schedule → run with `SELECTED:` /
`UNMAPPED_SOURCE:` / `RESULT:` summary lines). It gains one mode from n007's
workflow helper, `--advisory`, which always answers with `VERDICT:/REASON:`
lines and treats every absence as a printed skip — that is what lets a Step-7
affected run sit in every profile including the one Claude Code Web runs with
no engine. The completion gate is n008's: the existing `tests_pass` runs
`./ait test --gate` under a committed `completion:` policy in
`aitestmap/config.yaml` (`full` until `readiness` is `ADMISSIBLE` and a human
records `approved_by`; demoted back to `full` automatically), `testmap_check`
unlocks it, `testmap_run` is retired as a gate name, and the command exit
contract gains the 75 → error and 3 → error rows for opted-in keys in the one
function that owns it. The workflow seam is n008's data (project config,
profiles, gates, two environment variables, one Step-7 paragraph) plus n007's
one procedure — the **pre-review affected run** before Step 8 — kept because it
is the run that writes the prediction record the next full run scores: without
it no prediction is ever scored and `readiness` can never be reached. The
`## Running Tests` section of the seeded agent-instructions block is one
merged text: never call the tool directly; `./ait test`, `./ait test
<path>...`, `./ait test --all`, `./ait test --howto`; `UNANNOTATED_TEST` →
`annotate --suggest`; `UNMAPPED_SOURCE` → map it before the gate;
`TESTMAP_ABSENT` → `/aitask-testmap-onboard`; the exit-code table.

What this does not change: the engine's process boundary, the registry's six
n006 tables and check rules, the id grammar, axes, the runner contract, the
scheduler, the ledger, the evidence join, the per-user root and its migration
verb, the `testmap_fresh` and `testmap_check` verifiers, and the
`aitask-testmap` skill's maintenance obligations. The additions are one engine
package family (`internal/{seed,onboard,brief}`), three registry-adjacent
files (`seeded.yaml`, `adopted.yaml`, `onboard.yaml`), one bash front, one
completion-policy block, one skill, one instructions section, one Step-7
procedure and one profile key.
<!-- /section: overview -->

<!-- section: decision_matrix [dimensions: component_*, assumption_*] -->
## Decision Matrix: What Was Taken From Which Parent, and Why

| aspect | n007_explorer_003a | n008_explorer_003b | chosen | why |
|---|---|---|---|---|
| machine-seeded edge state | `seeded.yaml`: selects, never claims; per-row accept writes the stamp | `adopt` writes stamped blocks per accepted class; `adopted.yaml` provenance until re-stamped | **both, as three states** | a queue that cannot claim is right *before* anyone accepted; a stamped edge with provenance is right *after* a class was accepted; per-row acceptance is a reviewed claim and needs no provenance row |
| autonomous acceptance | never (OQ2: acceptance turns a heuristic into a claim) | headless: level 0 + static-only level 1 at 0.95 | **n007's rule, n008's mechanism at 1.0** | a language-rule origin (Go package) is not a heuristic; everything below 1.0 is |
| seed origins and weights | naming 0.6 / invocation 0.9 / imports 0.85 / cochange 0.5–0.8 / coverage 0.95 / observed 0.7 | static 0.9 (go 1.0) / convention 0.7 / cochange 0.2+0.2n ≤ 0.6 / plan 0.5 / prose 0.3 | **one table** | same facts; n008's co-change cap is the measured one (groups do not disambiguate); n007's coverage and observed origins have no n008 counterpart and are kept |
| class-acceptance threshold | none (per row) | 0.85 | **0.85 for `--class`**; per-row has none | static alone qualifies, convention alone does not, co-change never |
| onboarding structure | 9 phases in `onboard.yaml`, one task, resumable at `ONBOARD_NEXT:` | 4 levels, one task each, `readiness` derives `LEVEL` | **levels × phases** | levels are the grade of the registry; phases are the ledger of a run; both are needed to make a half-migrated repo a known state |
| first full run | phase 6 `full_run` = `ait test --all` | the level-0 task's own `tests_pass` at Step 9 | **n008** | it is the same run and it lands under the task's gate ledger; n007's `costs --update` and anchoring happen inside it |
| `bootstrap_until` | enable + 30 d | adopt (level 0) + 90 d | **+90 d at level 0** | level 0 is unstamped by design and a 1,000-seed queue is not accepted in 30 days; `finish` may shorten it |
| skill shape | static, attended-only, no stub | profile-aware stub + `.j2`, headless behaviour defined | **n008** | the merged design has a defined headless behaviour (seed; adopt 1.0 origins only; no kinds; no policy flip) |
| task shape | one `testmap_onboarding` task, per-phase commits, `--no-task` | one task per level through task-workflow, adopt at Step 7 | **n008's task per level, n007's per-phase commits and re-entry** | a level may wait weeks; a phase may span sessions |
| front verb | engine `test` composite via the shim: `--task`, `<path>...`, `--all`, `brief`, `--mode show` | `aitask_test.sh`: MODE / TASK / INTAKE / POLICY resolution, `test_command` and `fallback_command` fallbacks, `--howto`, `--dirty`, `--explain`, `--tokens` | **both layers** | the fallbacks must be bash (they run with no engine); the composite must be Go (it is the pipeline) |
| workflow helper | `aitask_affected_tests.sh` → `VERDICT:/REASON:`, 0/1/2/3, absence = skip | none; Step-7 paragraph names `./ait test` | **n007's contract as `ait test --advisory`** | one script, two modes; the advisory mode is what Web needs |
| Step 7 | `affected-tests.md` at two points behind `affected_tests: run\|show\|off` | one paragraph | **paragraph for the loop, procedure for the pre-review run** | the pre-review run writes the prediction the full run scores; the loop needs no procedure |
| gates | `testmap_fresh` → `testmap_check` → `testmap_run` (kept from n006); enabled by `enable` phase | `testmap_check` → `tests_pass` = `./ait test --gate` under `completion:`; `testmap_run` retired; 75 → error row | **n008** | one gate an agent learns; the legacy Step-9 path and `aitask-qa` reach the lane through `test_command`; demotion fails toward running more |
| `UNMAPPED_SOURCE` / `UNANNOTATED_TEST` | `UNMAPPED_SOURCE:` on `test` and `check`; Step-7 offer | `UNANNOTATED_TEST:` + `HINT:` | **both** | one is the source side, the other the test side |
| instructions section | 12 lines: four verbs incl. `brief`, `UNMAPPED_SOURCE`, `TESTMAP:absent` | rule + four forms incl. `--howto`, `UNANNOTATED_TEST`, exit table | **one merged section** | `--howto` is the flag family; `brief` is the engine verb behind it |
| task resolution | `--task <id>` explicit | `--task` > `AIT_GATE_TASK_ID` > `aitask/<name>` branch > single own lock > `NO_TASK` | **n008** | the advisory mode still passes the id explicitly |
| `ait setup` state line | `TESTMAP:absent\|bootstrapping\|onboarded\|engine-missing` | — | **n007** | |
| `aitask-qa` | `explain --sources <paths> --format table`; 4a prefers `ait test --task` | `explain --source` per path; 4a via `aitask_run_project_command.sh --task-id`; 4c `REFUSED`; 4d edges | **n007's verb form, n008's four edits** | |
| annotation placement | bash after header; Python appended to docstring; Kotlin block before KDoc / inside member block | comment lines only; Python `#` after docstring (never inside — `__doc__`); Go after package; Kotlin after imports | **n008, plus n007's member-block placement** | rewriting a docstring changes behaviour; a member seed belongs in its `testmap:unit` block |
| `attribute --propose` | → `seeded.yaml` origin `observed` | — | **n007** | the autonomous-safe half of feedback |
| `costs --gate-timeout` / run-id prefixes | `test-` / `full-` prefixes | `GATE_TIMEOUT_SUGGESTED = max(600, 3 × p95)` | **both** | |
| runner keys | `runner scaffold`, `full` wrapper from `test_command`, `bash-file list --invocations` | `subsumed_by:`, `fallback_command:` | **both** | |
| `verify_build`-wired suite | detect proposes moving it to `test_command` | ask, default keep, add `test_command: ./ait test` | **n008** | the lint half |
| config additions | `exclude:`, `docs:`, `notes:`, `broad_threshold_s` | `completion:`, `conventions:`, `helper_roots:`, `helper_fanin:` | **all** | |

Lineage rows for the first-round parents — resolved in n003 and n006, carried
here unchanged: n001's `testmap:verified <sha>` and `git log` anchor walk
versus n002's `@<date>/<blob10>` digest → **digest plus the evidence join**;
n001's `suites/` directory versus n002's `_scoped.yaml` → **`_scoped.yaml`**;
n001's `go/` + `make install-dev` + `AIT_TESTMAP_DEV=1` versus n002's
`engine/` + `ait engine build` + `AIT_ENGINE=dev` → **n002's**; n001's bash
reference runners versus n002's builtins → **builtins with shadow-by-name**;
n001's `~/.aitask/bin/ait-testmap-<V>` versus n002's `~/.aitask/engine/v<V>/`
→ n002's shape under **`$AITASKS_HOME`** (n005); n001's `testmap_run` /
n002's `testmap_select` → n003's `testmap_run` → **retired here in favour of
`tests_pass` under policy**; n002's cobra and gofrs/flock → **stdlib `flag` and
`syscall.Flock`** (n006).
<!-- /section: decision_matrix -->

<!-- section: architecture [dimensions: component_test_entrypoint, component_test_front_verb, component_onboarding_engine_verbs, component_onboarding_skill, component_seeder, component_agent_brief, component_agent_instructions, component_completion_policy, component_workflow_seam, component_workflow_integration, component_go_engine, component_registry_loader, component_engine_binary, component_gates] -->
## Architecture

### Process boundary (n006's, with the additions marked)

```
./ait test [...]                                   agent · human · tests_pass verifier (test_command) · Step-7 procedure (--advisory)
 └─ .aitask-scripts/aitask_test.sh                 ← NEW  bash front, ~150 lines: MODE / TASK / INTAKE / POLICY / fallback / advisory
      │  no aitestmap/            → TESTMAP_ABSENT:<hint> → aitask_run_project_command.sh test_command   (advisory: VERDICT:skip REASON:registry_absent)
      │  engine absent            → interactive: ENGINE_MISSING:<path>|<repair> exit 3     (advisory: VERDICT:skip REASON:testmap_absent)
      │                             completion: per config.yaml completion.engine_absent (error | fallback_command)
      │  MODE   completion iff --gate or $AIT_GATE_TASK_ID · advisory iff --advisory · else interactive
      │  TASK   --task > $AIT_GATE_TASK_ID > aitask/<task_name> branch > single own lock (aitask_lock.sh --list-mine) > NO_TASK
      │  INTAKE aitask_change_surface.sh list <id> | --dirty (printed) | --all | <path|id>...
      │  POLICY completion: config.yaml completion.mode re-checked against `readiness`
      └─ .aitask-scripts/aitask_testmap.sh          the n006 shim, unchanged: resolves $AIT_TESTMAP_BIN > AIT_ENGINE=dev > $AITASKS_HOME/engine/v<V>/
           └─ ait-testmap test … | select | schedule | run | brief | onboard … | readiness | costs …
                internal/registry       six tables (n006) + seeds (registry/seeded.yaml) + adopted (registry/adopted.yaml)
                internal/seed           ← NEW  origins static:{package,invocation,import} · convention · cochange · plan · prose · coverage · observed; noisy-OR
                internal/onboard        ← NEW  detect · inventory · seed · classify · adopt · reject · scaffold · status · finish; the onboard.yaml phase ledger
                internal/brief          ← NEW  the generated run brief (`brief`, rendered by `ait test --howto [--md]`)
                internal/selectr        graded walk (n006) + seeded edges at d1 · explain --sources · the `test` summary lines
                internal/runner         contract (n006) + subsumed_by: · fallback_command: · the `full` suite wrapper · bash-file list --invocations
                internal/annot          grammar v3 + rewriter (n006); adopt is a caller, at the fixed per-language position
                internal/deps           scanners (n006); direct-invocation and direct-import facts exposed to internal/seed
                internal/cost           ledger (n006) + costs --gate-timeout; run_id prefixes test- / full- / gate-
                internal/feedback       score · attribute (+ --propose) · readiness (+ LEVEL / NEXT / ADOPTED_UNREVIEWED / SEEDED / POLICY)
                internal/{axes,changesurface,sched,stale,gitx,platform}   unchanged
                  ├─ exec:  git, runner scripts / builtins, admission / allocator commands, scanner plugins
                  └─ files: aitestmap/** · .aitask-testmap/ (runs, ledger, onboard/<run>/seed.json) · XDG cache (deps; cochange matrix by HEAD sha)

.aitask-scripts/lib/gate_verifier_lib.sh           run_project_command_key(): + 75 → error (command_refused), 3 → error (command_errored) for opted-in keys;
                                                   exports AIT_GATE_TASK_ID / AIT_GATE_RUN_ID around the command
.aitask-scripts/gates_reference.yaml               + testmap_fresh (procedure), testmap_check (unlocks: [tests_pass]);  NO testmap_run
.aitask-scripts/aitask_gate_testmap_check.sh       machine verifier (n006); reports SEEDED:<n>, ADOPTED:<n>, UNMAPPED_SOURCE:<path>
.aitask-scripts/aitask_gate_tests_pass.sh          unchanged; runs test_command = ./ait test under the opt-in
.aitask-scripts/aitask_setup.sh                    install_engine_binary (n006) + report_testmap_state() → TESTMAP:<state>
.claude/skills/aitask-testmap-onboard/             ← NEW  profile-aware stub + SKILL.md.j2 + one procedure file per phase
.claude/skills/aitask-testmap/                     n006; opens with `ait test --howto`; hands an un-onboarded repo to onboard
.claude/skills/aitask-gate-testmap-fresh/          n006 procedure gate + "adopt seeds on touched test files" step
.claude/skills/task-workflow/SKILL.md.j2           Step 7: one paragraph (the loop) + the pre-review Affected Tests Procedure (affected-tests.md)
.claude/skills/task-workflow/build-verification.md + one branch: verdict error / command_refused | command_errored
.claude/skills/aitask-qa/{test-discovery,test-execution}.md   registry-first branches
seed/aitasks_agent_instructions.seed.md            + `## Running Tests` (generic; installed into every agent surface by ait setup)
engine/                                             Go source — framework repo only, excluded from the tarball
```

The boundary rule is n001's, made precise by n006 and not bent: parse, walk,
match, digest, schedule, seed and adopt in Go; gate ledger, task file,
profile file, `project_config.yaml`, `gates.yaml`, `CLAUDE.md` and the shell
environment in bash and skill prose. `onboard` never creates a task, never
edits a profile and never commits — the skill does those through
`aitask_create.sh --batch`, `aitask_pick_own.sh`, the settings helpers and
`aitask_task_commit.sh`; the engine reads `onboard.yaml`'s `task:` and writes
its phase rows. The engine still never writes `aitasks/`, `aiplans/`,
`.aitask-data/` or a gate ledger and never invokes `aitask_*.sh`.

### Registry directory (n006's, with the additions marked)

```
aitestmap/
  config.yaml            n006 keys (unit_covers_max, suite_budget_s, bootstrap_until, require_stamp, broad_review_days,
                         concurrency, broad_after_unit, device_policy, host_class, flake_threshold, symbol_scanners, run_gate_admission)
                         + completion: {mode, deferred, on_empty_selection, engine_absent}        ← n008
                         + conventions: [{test, source}]  helper_roots: [...]  helper_fanin: 0.05   ← n008 (seeded by detect)
                         + exclude: [globs]  docs: [paths]  notes: | (<=10 lines)  broad_threshold_s: 60   ← n007
  onboard.yaml           ← n007  phase ledger: {contract, task, level, phases{...}, rejections[]}
  axes.yaml · runners.yaml · resources.yaml      n006; runners.yaml written by onboard detect --write, confirmed per runner
  registry/
    _scanned.yaml · _scoped.yaml · observed.yaml · areas.yaml · <area>.yaml    n006
    seeded.yaml          ← n007  the queue; generated by onboard seed; rows leave on adopt / reject
    adopted.yaml         ← n008  provenance of class-adopted edges; a row leaves when a human re-stamps the edge
  costs/ · runners/ · scanners/                  n006; runners/<name>.sh may come from onboard scaffold --runner
```

### `aitestmap/config.yaml`, the additions

```yaml
completion:                  # n008
  mode: full                 # full | selected — selected written only by the onboarding skill's --policy re-entry after READINESS_DECISION:ADMISSIBLE
  deferred: run              # run | fail — completion never silently drops a row the interactive budget would cut
  on_empty_selection: skip   # skip (exit 2 → gate skip under the opt-in) | full
  engine_absent: error       # error (exit 3) | fallback_command (the full: true suite runner's fallback_command:, MODE:fallback)
conventions:                 # n008; seeded by onboard detect per framework; the `convention` origin (0.60)
  - {test: "tests/test_{stem}.sh", source: ".aitask-scripts/aitask_{stem}.sh"}
  - {test: "tests/test_{stem}.sh", source: ".aitask-scripts/lib/{stem}.sh"}
  - {test: "tests/test_{stem}.py", source: ".aitask-scripts/lib/{stem}.py"}
helper_roots: ["tests/lib/**", "**/testing/**", "**/testdata/**"]     # n008
helper_fanin: 0.05           # n008: a closure path reached by ≥5 % of a runner's units is a helper, not a subject
exclude: ["tests/golden/**", "tests/data/**"]                          # n007: never listed, never UNREGISTERED
docs: [aidocs/testing/change-aware-verification.md]                    # n007: printed by --howto
notes: |                                                               # n007: printed by --howto verbatim, <=10 lines
  A shared component change (ui/components/*) must run the full gate; preview renders without a verdict.
broad_threshold_s: 60        # n007: classify signal — a recorded p95 above this proposes a broad kind
```

### Where the new state lives

| data | location | written by |
|---|---|---|
| seed queue | `aitestmap/registry/seeded.yaml` rows `{test[#member], covers, origin[], confidence, evidence{}, proposed_at}` | `onboard seed --apply`; `attribute --propose`; rows removed by `onboard adopt` / `reject` |
| adopted-edge provenance | `aitestmap/registry/adopted.yaml` rows `{test, source, origin[], confidence, adopted_at, task}` | `onboard adopt --class`; rows deleted when `verify`, `annotate`, `stale --confirm-source` or a per-row `adopt` re-stamps that edge |
| phase ledger | `aitestmap/onboard.yaml` `{contract, task, level, phases{detect,inventory,seed,waivers,enable,full_run,adopt,classify,scaffold,finish: {status, at, by, counts}}, rejections[]}` | the engine's `onboard` verbs; read by `onboard status`, `report_testmap_state()`, the skill's re-entry |
| the seed dump for review and attachment | `.aitask-testmap/onboard/<run-id>/seed.json` (gitignored), attached to the level task with `ait attach` | `onboard seed --json --out` |
| completion policy, conventions, helper roots, docs, notes, excludes | `aitestmap/config.yaml` | `onboard detect --write` (level 0); the skill's `enable` phase (`docs:`, `notes:`); the `--policy` re-entry (`completion.mode`, `run_gate_admission.approved_by`) |
| test entry and exit-contract opt-in | `aitasks/metadata/project_config.yaml`: `test_command: ./ait test`, `gate_command_exit_contract: [test_command]` | the skill's `enable` phase, confirmed once as a table |
| gate declarations | profiles' `default_gates` (`tests_pass`, `testmap_check`, `testmap_fresh`); `gates.yaml` `tests_pass.timeout_seconds` | the skill's `enable` phase; the timeout from `costs --gate-timeout` after the first full run |
| agent instructions | `CLAUDE.md` `>>>aitasks` block, `AGENTS.md`, `.codex/instructions.md`, OpenCode mirror | `ait setup` from the seed; a hand-maintained `CLAUDE.md` by the level-0 task |

### The three-state adoption model

```
                onboard seed --apply                          onboard adopt --class <origin> [--accept-min 0.85] [--scope <glob>]
   (none) ─────────────────────────────▶ SEEDED ────────────────────────────────────────────────────────────▶ ADOPTED (stamp + adopted.yaml row)
   attribute --propose ──────────────────▶  │  (selects at d1, no stamp,                                            │
                                            │   invisible to stale, never --strict)                                  │ human re-stamp: verify · stale --confirm* · annotate
                                            │ onboard adopt <test> <source> | --area <a> --batch <n> | in-gate row   ▼
                                            ├──────────────────────────────────────────────────────────────▶ REVIEWED (stamp, no provenance row)
                                            │ onboard reject <test> <source> --reason
                                            ▼
                                        REJECTED (onboard.yaml; never re-proposed)
```

`SEEDED` selects; `ADOPTED` and `REVIEWED` claim; only `REVIEWED` is a claim a
named person made about that pair. `check` prints `SEEDED:<n>` and
`ADOPTED:<n>` (informational); `readiness` prints `ADOPTED_UNREVIEWED:<n>|<ratio>`
and `SEEDED:<n>`; `stale` and `explain` show `adopted(<origins> <confidence>)`
on an adopted edge's `DISPLAY` line so the procedure gate knows it is
confirming a class-accepted claim. A seed with the same `(test, covers)` as any
stamped edge is dropped at load with `SEED_SHADOWED`.
<!-- /section: architecture -->

<!-- section: adoption_model [dimensions: component_seeder, component_onboarding_engine_verbs, component_registry_loader, component_annotation_scanner, component_dependency_scanners, assumption_seed_sources_measured, assumption_static_closure_seeds_edges, assumption_cochange_is_corroboration, assumption_seeds_select_never_evidence, assumption_helpers_separable_by_fanin, assumption_annotation_is_comment_only] -->
## Seeds: Origins, Confidence, Helpers, Placement

### One origin table

| origin | rule | measured (n007 / n008, 2026-09-16) | confidence |
|---|---|---|---|
| `static:package` | a `_test.go`'s subject is the non-test files of its own package | aitasks_go: deterministic, 85 packages | **1.00** |
| `coverage` | per-unit runtime coverage, opt-in: coverage.py dynamic contexts, `go test -run <unit> -coverprofile`, LCOV with a test column, a project plugin's `{test, covers}` lines (JaCoCo per-test sessions) | opt-in | 0.95 |
| `static:invocation` | a literal repo path the test executes or sources (bash: `./.aitask-scripts/x.sh`, `source lib/y.sh`, `$SCRIPT_DIR`- and `$PROJECT_DIR`-relative forms resolved against every source root) | aitasks bash: 350/400 (n007) … 398/400 (n008 counting `lib/` too), avg 3 paths | 0.90 |
| `static:import` | a direct import of a main-root file (Python through the file's own `sys.path` bootstrap; Kotlin imports; same-package facts excluded) | aitasks Python 255–320/320, avg 1; thinking_app 139/339, avg 3 | 0.85 |
| `observed` | an `attribute --propose` row from a scored full-run miss | — | 0.70 |
| `convention` | `config.yaml conventions:` patterns seeded by `detect` per framework (`test_<x>.sh → aitask_<x>.sh \| lib/<x>.{sh,py}`, `test_<x>.py → <x>.py`, `<Stem>Test.kt → <Stem>.kt`) | 52–72/400 bash, 62/320 Python, 48/307 Kotlin | 0.60 |
| `plan` | an `aiplans/` file naming both paths, through the `aitask_explain_extract_raw_data.sh` cache when present | — | 0.50 |
| `prose` | a literal path in the unit's header comment or a `# Covers:` line (38 in aitasks) — displayed beside the seed as reviewer context, never matched by the annotation scanner | — | 0.30 |
| `cochange` | `(test, source)` co-occurring in ≥ 2 distinct `(t<id>)` task groups over one `git log --name-status -M --format=%H%x00%s` pass, cached by HEAD sha; per-commit grouping where the convention is absent; `SEED_HISTORY:shallow\|<n>` on a shallow clone | aitasks: 439/600 task commits, 2.8 × 2.6 (tight); 336 groups in 400 commits at 1.14 commits each with nothing inside a group saying which covers which; thinking_app: 127/400 at 7.2 main files (noisy) | 0.20 + 0.20 × groups, **cap 0.60** |

Combination is noisy-OR, `1 − Π(1 − cᵢ)`. The default class-acceptance
threshold is 0.85: `static:invocation` or `static:import` alone qualifies,
`convention` alone (0.60) does not, `cochange` (≤ 0.60) never does, and
`convention + cochange` (0.84 at the cap) does not either — corroboration
raises a static edge's rank and cannot manufacture one. Confidence orders the
queue and never hides a row. The static origins read the same `internal/deps`
facts the selector's test-side closure uses — once, from the blob-keyed
cache; only the *direct* relation is seeded, the deeper closure stays the d2
walk.

### Helpers before subjects

A closure path is a helper, not a subject, when it is under `helper_roots`
(`tests/lib/**`, `**/testing/**`, `**/src/test/**` for Kotlin, `**/testdata/**`)
or when its fan-in reaches ≥ `helper_fanin` (5 % of the runner's units). A
helper gets `test-dep` selection through the closure for free and, when it
globs the tree (`ls tests/*.sh`, `glob.glob`, `rglob`, `find`, `git
ls-files`, `os.walk` — aitasks: `tests/lib/import_isolated.py`,
`board_fixture.py`, `validate_session_hook_fixtures.py`), a proposed
`testmap:reads` line (`SEED_READS:<helper>|<glob>|<evidence>`) written at
level 2 on class acceptance. A hot production module misread as a helper keeps
`test-dep` selection (over-selects), and every fan-in reclassification is
listed for review.

### Kinds, members, axes as seeds

`onboard classify` wraps n006's `classify --suggest` with the three
onboarding signals — a recorded p95 above `broad_threshold_s` from the first
full run, a source-set or directory convention (`androidTest/`,
`androidDeviceTest/`, `*_live.py`, `*_integration.sh`, `parity/`), a resource
named in the file (tmux, `App.run_test`, `install.sh --dir`, real `.git` use,
emulator, docker, network) and `fanout:<n>` above `unit_covers_max` — each
printed as the reason on `CLASSIFY:<test>|<kind>|<reason>`, with areas from
the closure's directories intersected with `code_areas.yaml`; `SEED_BATCH_NO`
from an aggregate runner's serial list; `SEED_MEMBER` / `SEED_AXIS` from the
grid heuristic. Kind changes are confirmed individually, never per class,
because a wrong kind changes staleness semantics rather than selection breadth.

### Placement: comments only

`onboard adopt` writes through `internal/annot`'s line-targeted rewriter at a
fixed position per language, comment lines only: bash after the header
comment block (after the shebang and leading `#` block); Python as `#` lines
after the module docstring — the grammar reads docstring lines (n001/n002)
but adoption never writes into one because that changes `__doc__`; Go after
the package clause; Kotlin after the import block, or inside the member's
`testmap:unit` block for a member seed. `git diff -w --ignore-blank-lines` of
an adopted file shows comments only. Refusals and skips are explicit:
`ADOPT_REFUSED:<path>|dirty-foreign` for a file dirty outside the current
task's change surface, `ADOPT_SKIP:<path>|duplicate` (already annotated —
`SEED_SHADOWED` at load), `ADOPT_SKIP:<path>|unregistered` (no runner lists
it), `ADOPT_SKIP:<path>|no-leader`; `WROTE:<path>` per file and one
`ADOPT_SUMMARY:<level>|<edges>|<files>|<skipped>`. Each written stamp is
`@<date>/<blob10>` at adopt time; a class-adopted edge also gets its
`adopted.yaml` row.

### What seeding cannot do, stated

thinking_app's tests resolve imports for 139 of 339 files because same-package
references need no import and "same package is fully connected" is too coarse
to seed; fixture-driven tests and screen members seed through `annotate
--from-body` (n006) and level 3; sources reached by no origin stay
`UNMAPPED_SOURCE:` until a rule, a waiver, a Step-7 prompt or a coverage import
maps them. `onboard status` reports that state ("selecting on 84 % of tests,
claiming on 18 %") rather than hiding it.
<!-- /section: adoption_model -->

<!-- section: onboarding [dimensions: component_onboarding_skill, component_onboarding_engine_verbs, component_seeder, requirements_zero_config_onboarding, requirements_onboarding_existing_tests, requirements_incremental_adoption, assumption_test_tools_detectable, assumption_onboarding_is_a_task, assumption_full_run_expressible_per_repo] -->
## Onboarding: Levels × Phases, One Aitask per Level

### Levels (what the registry has) and phases (how a level's task gets there)

| level | phases in the level's task | what `onboard` writes | what the repository gains | who accepts |
|---|---|---|---|---|
| **0 — runners and universe** | preflight → **detect** (`--write`) → **inventory** → **seed** → **waivers** → **enable** → **full_run** (= the task's `tests_pass` at Step 9) | `config.yaml` (`bootstrap_until` today + 90, `require_stamp false`, `concurrency serial`, `completion.mode full`, `conventions:`, `helper_roots:`), `runners.yaml` (builtins + bindings by glob; a `full: true` suite runner from `test_command` with `fallback_command:`), `resources.yaml` from hints, `registry/areas.yaml` via `areas --import-codemap`, `_scanned.yaml`, `registry/seeded.yaml`, rules and expiring waivers in `registry/<area>.yaml` | the universe (`list`), `ait test --all`, per-unit cost and `last_pass` from the first full run, selection through seeds and the test-file closure, scoring of every later full run; nothing stamped | the runner table (keep / edit command / drop, per runner), `UNREGISTERED` files (bind / `exclude:` / not a test), the config table once — headless-safe |
| **1 — edges** | **adopt** per evidence class (`--class static:invocation`, …) or per area (`--scope <glob> --batch 50`), then incrementally inside `testmap_fresh` | stamped `testmap:covers` blocks; `registry/adopted.yaml` rows for class adoptions; rows leave `seeded.yaml` | freshness and the evidence join apply; `stale` reports; `testmap_check` is meaningful; `UNMAPPED_SOURCE` shrinks | per class (accept all / review a sample of ten / skip) or per row; headless: `static:package` only |
| **2 — kinds** | **classify** (per batch of 20, kind changes individually) → `scan --apply` | `testmap:kind integration\|e2e\|device` + `testmap:area` / `testmap:scope` on broad tests, `testmap:reads` on tree-scanning helpers, `testmap:batch no` from serial lists, `needs:` bindings from resource hints, `resources.yaml` entries | scoped rows, the suite budget, `broad_after_unit`, enforced do-not-overlap (aitasks: `repo-git-index` mutex, worktree scope) | per kind, individually |
| **3 — product** | **scaffold** (`--axes`, `--runner <builtin> --as <name>`, `--members`) → `annotate --from-body` per member | `axes.yaml` skeleton, `aitestmap/runners/<name>.sh` with `describe`/`run` delegating to the builtin and `list` printing `SCAFFOLD_TODO` until filled (check reports it), `testmap:unit` member blocks | variant selection (n006's thinking_app mapping) | the maintainer, with the skill |
| **finish** | a phase of whichever level task the maintainer names last | `require_stamp: true`; `check --strict`; `bootstrap_until` shortened | enforcement | `onboard status` green: no pending phase, seed queue ≤ a user-set threshold (default 0), `check` clean |

`readiness` derives `LEVEL:<0-3>` from what exists (`runners.yaml` → 0, any
stamped `_scanned` edge → 1, any `_scoped` row or `reads` → 2, `axes.yaml` →
3) and prints `NEXT:<the phase or level that raises it>`; `onboard status`
prints the ledger's `ONBOARD_NEXT:<phase>`, the seed queue per origin, the
adopted-unreviewed count, tests-with-any-edge and sources-with-any-edge
ratios, the oldest pending seed's age, and the rejections count. The two
agree by construction: `LEVEL` is a property of the tree, `ONBOARD_NEXT` a
property of the run.

### Invocation and task shape

`/aitask-testmap-onboard [--level <n>] [--policy selected] [--no-task]`.
Preconditions: `ait testmap version` (absent → stop with the `ait setup`
hint); `aitestmap/` present with a finished ledger → *refresh mode* (seed
limited to units newer than `adopted.yaml`'s last row, same flow); an
unfinished ledger → re-enter at `ONBOARD_NEXT:`. The read-only survey runs
`onboard detect` and `onboard seed --json --out .aitask-testmap/onboard/<run>/seed.json`
and shows the level proposal: frameworks and counts, edges per evidence class
with three samples each, helpers found and which glob, kind candidates with
reasons, `UNLISTED` files, `RUNNER_SCRIPT_NEEDED` if any, and the config
writes. The skill then creates the level's aitask (`aitask_create.sh --batch
--name "testmap onboarding level <n>" --type chore --labels testing,testmap`,
`ait attach` the seed dump), claims it (`aitask_pick_own.sh`), writes the id
and level into `onboard.yaml`, and continues into task-workflow honouring the
profile (the `explore_auto_continue` shape). The plan is the phase list; at
Step 7 each phase ends with `chore: Onboard testmap — <phase> (t<id>)`
through `aitask_task_commit.sh` with paths named, so `aitask_change_surface.sh`
attributes the files and a resumed session re-enters at `ONBOARD_NEXT:`; Step
8 reviews the annotation diff and dispatches `testmap_fresh` (nothing `STALE`
yet — every stamp is today's); Step 9's `tests_pass` runs `./ait test --gate`
under `completion.mode: full`, which for the level-0 task is the **first full
run**: every unit's `last_pass` anchored, `PREDICTION_SCORED:none` because
nothing was predicted yet, `costs --update` folded; the archive commits
registry, annotations and config under one `(t<id>)`. After it: `costs
--gate-timeout tests_pass` → `GATE_TIMEOUT_SUGGESTED:tests_pass|<s>` =
`max(600, 3 × p95)` written into the project's `gates.yaml`; `readiness` →
`LEVEL` / `NEXT`; the next level's task created with `depends:` on this one.
`--no-task` writes without committing and prints the commit lines, for a repo
that forbids tasks on the code branch. The `--policy selected` re-entry runs
`readiness` and only on `READINESS_DECISION:ADMISSIBLE` writes
`completion.mode: selected` and `run_gate_admission.approved_by {who, at,
statement}` in one `ait:` commit; `NOT_YET` prints the unmet criteria and
stops.

Headless (`remote`) profile: level 0 in full (every write is a registry file
or a seed), adoption of `static:package` origins only (`--accept-min 1.0`), no
kinds, no scaffold, no policy flip, no prompts — the level proposal is
printed, not asked.

### Detection, per target repository

| repository | `onboard detect` | level 0 runners and resources | full run (`completion.mode: full`) | levels 1–3 |
|---|---|---|---|---|
| **aitasks** | `FRAMEWORK:bash-file\|tests/**/test_*.sh\|400`, `FRAMEWORK:pytest\|tests/test_*.py\|320`, `AGGREGATE_RUNNER:tests/run_all_python_tests.sh`, `SERIAL_LIST:…\|4`, `RESOURCE_HINT:repo-git-index\|~40 tests`, `SUITE_CANDIDATE:test_command\|null`, `UNIVERSE:720 UNLISTED:0` | `bash-file`, `pytest` (`testmap:batch no` on the four carve-out modules, pinned by extending `test_serial_carveout_doc_drift.sh`); `resources.yaml`: `repo-git-index {kind: mutex, scope: worktree}` — the "invocation policy, not a guarantee" comment in `run_all_python_tests.sh` becomes enforced | `ait test --all` (no suite command existed; `tests_pass` gates for the first time); `fallback_command` derived: `for f in tests/test_*.sh; do bash "$f"; done && bash tests/run_all_python_tests.sh` | 1: 398 + 320 static edges, 52–72 corroborated by convention; helpers `tests/lib/` (27; 3 `reads`); 2: ~40 tmux / live-TUI / real-install tests → `integration` over codemap areas; 3: `tests/golden/` as a skill × profile × agent axis |
| **thinking_app** | gradle-class 374 classes, `RUNNER_SCRIPT_NEEDED:grid` (screen × matrix), `SUITE_CANDIDATE:test_command\|verify-active`, `RESOURCE_HINT:heavy-run` (exit-75 lock script) | `gradle-class` builtin until the project runner exists; `verify-active {unit: suite, full: true, children: …, fallback_command: tools/verification/screenshot-tests.sh verify-active}`; `heavy-run {kind: admission, exec: heavy-run-lock.sh}` | `verify-active` once (`screen-matrix` and `gradle-class` `subsumed_by: verify-active`) — identical to today's `test_command` | 3 = n006's worked mapping: `onboard scaffold --runner gradle-class --as screen-matrix` → `tools/verification/testmap_runner.sh` whose `list` the project fills from the manifests; `axes.yaml`; `testmap:unit` blocks in `ScreenFixtures.kt`; `completion.mode` stays `full` until readiness — t388's rule |
| **thinking_backend** | bash-file 22 + pytest 18 under `scripts/tests/`, `SUITE_CANDIDATE:verify_build\|scripts/tests/run_script_tests.sh` | `bash-file`, `pytest` with `cwd:`; the skill asks: keep `verify_build` (it also enforces a shellcheck baseline) and add `test_command: ./ait test` — the default | `ait test --all` over the 40 units; `build_verified` still runs the script | 1: static edges into `scripts/server/**` and `db_target.py`; 2: `golden/` fixtures as `reads` |
| **aitasks_go** | go-test: 85 packages, 55 `_test.go` files, `Makefile test`, `parity/run_parity.sh` (tmux + venv) | `go-test` (per package, `-run`, `-json`); `parity` as `suite`, kind e2e, resource `tmux` | `go test ./...` = `ait test --all` | 1 fully automatic and headless-safe: `static:package` at 1.0 |
| **aitasks_mobile** | kmp-sourceset: `commonTest` 36 (dbaccess 2, domain 25, shared 9), `androidHostTest` 1, `androidDeviceTest` 3 | `gradle-class` × modules on `:<module>:jvmTest` / `testDebugUnitTest`; `device` on `connectedDebugAndroidTest` with `emulator {kind: allocator}` | unit kinds only; device kind under `device_policy: filter_by_resource` — n006's open question 9 answered: the source set is a runner/kind distinction, no axis | 1: Kotlin import closure (`domain/src/commonMain/**`) |

In every row the user typed nothing; the skill showed the table and asked for
one confirmation per runner, one per evidence class, one per kind change and
one per config write.
<!-- /section: onboarding -->

<!-- section: run_surface [dimensions: component_test_entrypoint, component_test_front_verb, component_agent_brief, component_agent_instructions, requirements_zero_config_entrypoint, requirements_agent_run_surface, requirements_agent_instructions_seeded, assumption_task_resolvable_from_session, assumption_helper_degrades_when_absent, assumption_instructions_block_reaches_agents, assumption_instruction_block_is_read, assumption_change_surface_is_intake] -->
## The Run Surface an Agent Learns Once

### `ait test`

```
ait test                       selected tests for the task you are implementing, each with a reason
ait test <path|id>...          named units: a listed test file, file#member, file#member@variant, a directory of tests,
                               or a SOURCE path — treated as a one-file TASK: change set, so `ait test lib/foo.py` runs what covers it
ait test --all                 the whole registry: every runner's list, full: true suites once, subsumed_by runners skipped
ait test --task <id>           override task resolution
ait test --gate                completion mode — what tests_pass runs; implied by $AIT_GATE_TASK_ID
ait test --advisory --task <id> [--explain]
                               the Step-7 form: VERDICT:/REASON:/DETAIL:/LOG: lines, exit 0/1/2/3, every absence a printed skip
ait test --explain             the selection with reasons, groups and estimated cost; runs nothing (n007's --mode show)
ait test --howto [--md]        this project's runners, kinds, resources, full gate, axes, completion policy, LEVEL, docs, notes
ait test --tokens              select --format tokens (thinking_app: `| xargs tools/verification/screenshot-tests.sh preview`)
ait test --dirty               no task: every dirty path as a TASK: row; explicit, printed as INTAKE:dirty, never the default
ait test --fresh-only          exclude stale-marked units (interactive only)
ait test --budget-s <n>        interactive suite budget override
ait test --json                one object instead of lines
```

### Resolution, in order

1. **Registry present?** No `aitestmap/config.yaml` → `TESTMAP_ABSENT:run
   /aitask-testmap-onboard to enable change-aware selection`, then delegate to
   `aitask_run_project_command.sh test_command` (with `--task-id` when a task
   resolved), exiting with its verdict; `--howto` prints the same line plus the
   `test_command`. This is what makes "always `./ait test`" true on day one.
   Advisory mode: `VERDICT:skip REASON:registry_absent`.
2. **Engine present?** Through the n006 shim's strict handshake. Absent:
   interactive → `ENGINE_MISSING:<path>|run 'ait setup' or set AIT_TESTMAP_BIN`,
   exit 3; completion → `completion.engine_absent`: `error` (default, exit 3 →
   verifier `error`) or `fallback_command` (run the `full: true` suite runner's
   `fallback_command:`, print `MODE:fallback`, exit per the command); advisory
   → `VERDICT:skip REASON:testmap_absent`.
3. **Mode.** `--gate` or `$AIT_GATE_TASK_ID` → `completion`; `--advisory` →
   `advisory`; else `interactive`. Printed as `MODE:`.
4. **Task.** `--task` > `$AIT_GATE_TASK_ID` > the current worktree's branch if
   it matches `aitask/t<id>_*` (task-workflow's naming) > the locks this user
   holds on this host (`aitask_lock.sh --list-mine`, a listing verb added to
   the lock script): exactly one → that task; several → `AMBIGUOUS_TASK:<ids>`,
   exit 64 unless `--task`; none → `TASK:none`.
5. **Intake.** Named paths → units by registry lookup, or a source path → a
   synthetic `TASK:<path>` change set; `--all` → every runner's `list`; a
   resolved task → `aitask_change_surface.sh list <id>` piped to `--changes -`
   (`UNKNOWN:` refuses — advisory: `VERDICT:skip REASON:unknown_paths` naming
   them; `aitasks/`, `aiplans/`, `.aitask-data/` excluded); `--dirty` → `git
   status --porcelain` paths as `TASK:` rows; nothing → `NO_TASK:` with the
   three ways out, exit 64 (advisory: 3).
6. **Policy (completion only).** `completion.mode`; if `selected`, run
   `readiness` first: every criterion met → the task selection with `deferred:
   run`; any unmet → `POLICY_DEMOTED:selected->full|<criterion>` and run
   `full`. `full` → `run --all` with `subsumed_by` honoured. `on_empty_selection:
   skip` → exit 2 → the opted-in `tests_pass` records `skip`, never `pass`.
7. **Run.** The engine `test` composite: `select --include-stale [--budget-s]
   [--format …] --run <run-id>` → `schedule` → `run`; prints `SELECTED:<n>|<groups>|<est_s>|<seeded_n>|<adopted_n>`,
   one `UNMAPPED_SOURCE:<path>` per changed source no unit reaches, the ranked
   rows with n006's reasons (a seeded edge reads `edge(seeded:static:invocation,cochange)`,
   an adopted one `edge(annotation) adopted(static:invocation 0.90)`), `DEFERRED:`
   in interactive mode only, the waves, results per id, `RESULT:`. The run id is
   prefixed `test-` (interactive), `gate-` (completion) or `full-` (`--all`), so
   the ledger says which surface produced a row; all three anchor evidence.
8. **New-test and new-source notices.** `UNANNOTATED_TEST:<path>` + `HINT:./ait
   testmap annotate --suggest <path>` for a listed test in the change surface
   with no `testmap:` block, no seed and no adopted row; `UNMAPPED_SOURCE:<path>`
   for a changed source with no edge, seed, rule or waiver. Informational in
   interactive mode; the Step-7 procedure offers the fix; in completion mode
   `testmap_check` owns enforcement.

### Output and exit contract

```
MODE:interactive|completion|advisory|fallback   TASK:<id>|none   INTAKE:change-surface|dirty|all|named
POLICY:full|selected|<demoted…>   SELECTED:<units>|<groups>|<est_s>|<seeded>|<adopted>   RUN:<run-id>
ESCALATE:… DEFERRED:… UNMAPPED_SOURCE:… UNANNOTATED_TEST:… HINT:…       (n006/n007/n008 line classes pass through)
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
Step-7 procedure cannot disagree with the Step-9 path about an exit code. It
writes the engine's full output to the log, appends nothing to any gate
ledger, and is the one deliberate exception to "a missing engine is an error":
an *advisory* run must never block a task the way a declared gate legitimately
does; the skip is printed, never silent.

### The two environment variables

`run_command_gate` exports `AIT_GATE_TASK_ID=<task-id>` and
`AIT_GATE_RUN_ID=<run-id>` around the command; `aitask_run_project_command.sh
--task-id <id>` exports the first. That is how `./ait test` knows it is a
completion run and for which task in all three call sites (the `tests_pass`
verifier, the legacy Step-9 helper, `aitask-qa`) with no argument in
`test_command`; the run id names the gate run in `.aitask-testmap/runs/<run-id>/`
so a ledger row and a gate log share an identifier.

### `ait test --howto` (engine verb `brief`)

For thinking_app after level 3, on this host class:

```
TESTMAP:onboarded|since 2026-09-16|LEVEL:3|POLICY:full|seeds pending 412|adopted unreviewed 618
RUNNER:gradle-class|unit|371 classes|screenshot-tests.sh unit-tests --tests <class>|heavy-run
RUNNER:screen-matrix|unit (variant, axis matrix)|49 members x 10 matrices = 297|screenshot-tests.sh unit-tests --tests <class>.<method>|heavy-run
RUNNER:verify-active|suite (full)|1|screenshot-tests.sh verify-active|heavy-run|subsumes screen-matrix,gradle-class
FULL_GATE:verify-active|p95 1180s|= project_config test_command|tests_pass timeout 3540s
GATE:testmap_fresh (procedure, before commit) -> testmap_check -> tests_pass = ./ait test --gate (full)
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
`test_command`). `tests/test_agent_instructions.sh` gains T40 asserting the
heading in all four rendered surfaces through a real `install.sh --dir`. This
repository's own hand-maintained `CLAUDE.md` (sentinel present, no markers) is
edited by its level-0 onboarding task to point at `./ait test` and keep the
runner-specific notes (`run_all_python_tests.sh` lanes, the `PIPESTATUS`
caveat) as background.
<!-- /section: run_surface -->

<!-- section: workflow_seam [dimensions: component_workflow_seam, component_workflow_integration, component_gates, component_completion_policy, component_qa_integration, requirements_workflow_seam, requirements_workflow_seam_is_data, requirements_gate_enforcement, assumption_gate_exit_contract_reused] -->
## The Workflow Seam and the One Completion Gate

### The concrete edits

| where | change | kind | from |
|---|---|---|---|
| `task-workflow/SKILL.md.j2` Step 7, after *Follow the approved plan* | one paragraph: "**Test loop.** Run `./ait test` after each meaningful change — it selects from this task's change surface and prints a reason per unit. `UNANNOTATED_TEST:<path>` → `./ait testmap annotate --suggest <path>`; `UNMAPPED_SOURCE:<path>` → map it (`/aitask-testmap`). Do not invoke the project's test tool directly; `./ait test <path>` runs one unit." | prose, every profile; goldens regenerated | n008 |
| `task-workflow/SKILL.md.j2` Step 7, once before Step 8 | the **pre-review affected run**: the Affected Tests Procedure (`affected-tests.md`) under `{% if profile.affected_tests is not defined or profile.affected_tests != 'off' %}` | procedure | n007 |
| `task-workflow/affected-tests.md` | `./ait test --advisory --task <id> [--explain]` with the `set -e` capture form; the branch table below; the verdict line recorded in the plan's Final Implementation Notes, never in the gate ledger | procedure file | n007 |
| `task-workflow/profiles.md`, `remote.yaml` | profile key `affected_tests: run\|show\|off` (default `run`; `default.yaml` and `fast.yaml` omit it; `remote.yaml` sets `run`) | data + one doc row | n007 |
| Step 8 | n006's `testmap_fresh` procedure-gate dispatch before the change summary; inside the gate, one new step: for each `COMMITTED:`/`TASK:` test file with rows in `seeded.yaml`, show the seeds with evidence and offer adopt / reject / leave per row — accepted rows ride the same `(t<id>)` commit | inherited + one step | n007 |
| Step 9 verify block (`./ait gates run`) | none — the orchestrator runs `testmap_check` → `tests_pass` (= `./ait test --gate`) | none | n008 |
| Step 9 no-gates branch (`build-verification.md`, `verify_build`) | none in prose; a project reaches the test lane by declaring `tests_pass`, which onboarding writes into `default_gates` | data | n008 |
| `build-verification.md` | one branch: verdict `error` with reason `command_refused` / `command_errored` → host refused resources or the framework could not run; do not fix code, do not record a pass, report and re-run later | prose | n008 |
| `lib/gate_verifier_lib.sh` `run_project_command_key()` | opted-in keys: 75 → `error`/3/`command_refused`, 3 → `error`/3/`command_errored`; exports `AIT_GATE_TASK_ID`, `AIT_GATE_RUN_ID` around the command; docblock table updated — the single canonical statement | code; `tests/test_gate_verifiers.sh` extended | n008 |
| `aitask_run_project_command.sh` | `--task-id` also exports `AIT_GATE_TASK_ID`; inherits the new rows | code | n008 |
| `gates_reference.yaml` → `gates.yaml` sync | + `testmap_fresh` (procedure, verifier `aitask-gate-testmap-fresh`), + `testmap_check` (`unlocks: [tests_pass]`, `max_retries: 0`, `timeout_seconds: 120`); **no `testmap_run`**; `tests_pass` unchanged in the reference, `timeout_seconds` tuned per project from the ledger | data | n008 |
| project profiles | `default_gates` += `tests_pass`, `testmap_check`, `testmap_fresh` (the onboarding `enable` phase, confirmed; `rendered_gates` when present) | data | n007 + n008 |
| `aitask_gate_testmap_check.sh` | n006's verifier; rows `SEEDED:<n>`, `ADOPTED:<n>` (informational), `UNMAPPED_SOURCE:<path>` (reported during bootstrap, fails under `--strict` past `bootstrap_until`) | code | n007 |
| `aitask-qa/test-discovery.md` 3a–3c | with `aitestmap/`: `ait testmap explain --sources <changed files> --format table` → Source / Test / Reason / Status with `Covered`, `Covered (adopted)`, `Covered (seeded)`, `GAP` (= `UNMAPPED_SOURCE`); else the legacy convention scan | prose | n007 verb, n008 edits |
| `aitask-qa/test-execution.md` 4a–4d | 4a: the configured `./ait test` through `aitask_run_project_command.sh test_command --task-id <id>`; 4b: named units via `ait test <path>`; 4c: `REFUSED (host resources)` row, treated as `SKIP` in the health score; 4d: coverage from registry edges (seeded counted as `Covered (seeded)`) | prose | n008 |
| `aitask-pickrem`, `aitask-pickweb`, `aitask-resume` | inherit through task-workflow and `build-verification.md`; pickweb (no `ait setup`) sees `VERDICT:skip REASON:testmap_absent` at Step 7 and the `engine_absent` policy at completion | none | both |
| `aitask_setup.sh` | `report_testmap_state()` after `install_engine_binary()`: `TESTMAP:engine-missing\|absent\|bootstrapping\|<next>\|onboarded`, hint `run /aitask-testmap-onboard` on `absent`; setup never onboards | code; `test_install_engine_binary.sh` asserts each state | n007 |
| `ait` dispatcher | `test)` → `aitask_test.sh`; help line | code | both |
| permission touchpoints (5) | `aitask_test.sh` (its `--advisory` form replaces a second helper); `tests/test_touchpoint_count_contract.sh` re-pinned | config | both |
| `aidocs/framework/aitasks_extension_points.md` | "Adding a test-framework detector" (closed list, evidence line, fixture repo, `UNLISTED` behaviour) and "Adding a seed origin" (confidence row, evidence field, fixture) | doc | n008 + new |
| `aitask_skill_verify.sh` + goldens | task-workflow, aitask-qa, the new onboarding stub, every profile × agent | test | both |

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
| `skip` · `no_selection` | display the `UNMAPPED_SOURCE:` paths; **offer** (`AskUserQuestion`, non-skippable in attended profiles): *Annotate now* (`/aitask-testmap` → `annotate` / a rule) · *Propose for review* (`attribute --propose`, lands in `seeded.yaml` with origin `observed`) · *Continue unmapped*. Autonomous profiles take *Propose for review* |
| `skip` · `unknown_paths` | the Step-2b-style scope prompt from `aitask-gate-docs-updated`: include / subset / exclude; autonomous profiles exclude and log |
| `skip` · `admission_refused` | print `at_detail` (the host refused the heavy slot until the deadline); continue — nothing failed |
| `skip` · `testmap_absent` / `registry_absent` | one line; continue — not onboarded, or this host has no engine |

Why the procedure exists when the loop is a paragraph and the gate is
`tests_pass`: the advisory run is the one that writes the task's
`prediction.json`; the completion run (`full` policy) scores it
(`PREDICTION_SCORED` / `PREDICTION_FALSE_NEGATIVES`) into
`costs/predictions.yaml`; `readiness` counts those rows toward
`min_scored_full_runs`. A repository whose tasks never run the advisory form
never accumulates scored predictions and can never flip its policy. The
verdict line (`- **Affected tests:** pass (14 units, est 41 s) — log …`) goes
into the plan's Final Implementation Notes and never into the gate ledger: no
double record, no `record_gates` guard needed.

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
  # tests_pass: unchanged in the reference. In an onboarded project test_command is `./ait test`,
  # gate_command_exit_contract lists test_command, and gates.yaml carries timeout_seconds from `costs --gate-timeout`.
```

`testmap_run` is retired as a gate name. Every property it had has a home:
its verifier logic is `ait test --gate`; `blocks_dependents` and
`max_retries: 1` are `tests_pass`'s own; its 1800 s timeout becomes a
per-project `tests_pass.timeout_seconds` from the ledger; its exit mapping
(0/1/2/75/64 → 0/1/2/3/3) is the shared lib's new rows; `testmap_check`
unlocks `tests_pass`; `--include-stale` is applied by the composite; deferred
rows run under `completion.deferred: run`. An `unlocks:` target absent from a
task's active set is ignored, so `testmap_check` declared alone is linear as
before, and a project whose completion invariant is a full suite keeps
`tests_pass` exactly as today with `completion.mode: full`. `run_gate_admission`
and `readiness` (n006) gate the **policy flip** rather than a second gate's
declaration; the engine never enables a gate and never writes a profile.

### Completion policy

```
ait gates run 1234 → testmap_check → pass → unlocks tests_pass
   → aitask_gate_tests_pass.sh → run_command_gate → export AIT_GATE_TASK_ID=1234 AIT_GATE_RUN_ID=<run> → `./ait test`
      MODE:completion  POLICY:full                       → run --all (subsumed_by honoured) → exit 0/1/2/3/75
      MODE:completion  POLICY:selected                   → readiness: all met → task selection, deferred rows RUN
      MODE:completion  POLICY:selected → POLICY_DEMOTED:selected->full|max_false_negatives → run --all
   → run_project_command_key: 0 pass · 1 fail · 2 skip · 3 error(command_errored) · 75 error(command_refused)   [opted-in key]
   → ledger block result="MODE:full|720 units|policy:full" → orchestrator: pass / fail / skip / error (retry within max_retries)
   → after any full run: PREDICTION_SCORED:<r1>|<run> PREDICTION_FALSE_NEGATIVES:<n> → costs/predictions.yaml → readiness input
```

The flip is human (`/aitask-testmap-onboard --policy selected` after
`ADMISSIBLE`, `approved_by` recorded); the demotion is automatic and loud; the
policy can only fail toward running more. thinking_app's rule — full
`verify-active` as the completion gate until admissible (t388) — is preserved
exactly by `completion.mode: full`.

### Verification of the seam itself

`tests/test_ait_test_entrypoint.sh` drives a fixture repository with
`AIT_TESTMAP_BIN` pointing at a fake engine replaying scripted exits, in all
three modes and every `REASON:` (n007's helper cases folded in);
`tests/test_gate_verifiers.sh` covers 75 and the env export;
`tests/test_agent_instructions.sh` T40; `tests/test_testmap_onboard_ledger.sh`
(resume from each phase, idempotent re-run, `--no-task`, one task per level
with `depends:`); engine tests per detector, per seed origin on fixture repos
with synthetic `(t<id>)` histories, the fan-in reclassification, golden files
for block placement per language, every `ADOPT_*` refusal branch; the
task-workflow and onboarding goldens; `tests/test_touchpoint_count_contract.sh`;
`tests/test_install_engine_binary.sh` for each `TESTMAP:` state.
<!-- /section: workflow_seam -->

<!-- section: data_flow [dimensions: component_test_entrypoint, component_test_front_verb, component_onboarding_engine_verbs, component_onboarding_skill, component_seeder, component_completion_policy, component_workflow_integration, component_workflow_seam, component_selector, component_annotation_scanner, component_freshness, component_feedback_tools, component_cost_ledger, component_registry_loader, component_staleness_tool, component_engine_packaging] -->
## Data Flow

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
   ▼  after the run                   costs --gate-timeout tests_pass → gates.yaml tests_pass.timeout_seconds (ait: commit) · readiness → LEVEL:0 NEXT:adopt
   ▼  every phase                     onboard.yaml row · chore: Onboard testmap — <phase> (t<id>) commit, paths named
```

### Level 1: seeds → stamped edges

```
onboard adopt --class static:invocation --accept-min 0.85 [--scope <glob>]   (attended: accept all | review a sample of ten | skip)
   → rewriter: testmap:covers <src> @<date>/<blob10> at the fixed position → WROTE:<file> · registry/adopted.yaml rows · rows leave seeded.yaml
   → ADOPT_REFUSED:dirty-foreign · ADOPT_SKIP:duplicate|unregistered|no-leader · ADOPT_SUMMARY:1|<edges>|<files>|<skipped>
onboard adopt --area <a> --batch 50        (per row, evidence beside each: file pair, file:line, task ids, coverage run) → stamp, no provenance row
onboard reject <test> <source> --reason    → onboard.yaml rejections[]; never re-proposed
Step 8 testmap_fresh, any later task       → seeds on this task's touched test files: adopt / reject / leave per row → rides the (t<id>) commit
human re-stamp (verify · stale --confirm-source · annotate) → adopted.yaml row deleted → REVIEWED
```

### A task, steady state

```
Step 7  edit source ──▶ ./ait test                      MODE:interactive TASK:<id> (branch | lock) INTAKE:change-surface
                        change surface ──▶ test composite ──▶ select (edges ∪ adopted ∪ seeds ∪ deps ∪ rules ∪ axes ∪ test-dep) --include-stale
                        ──▶ schedule ──▶ run ──▶ ledger rows (run_id test-…) ──▶ SELECTED: / UNMAPPED_SOURCE: / UNANNOTATED_TEST: / RESULT:
        before Step 8 ──▶ ./ait test --advisory --task <id> ──▶ VERDICT:/REASON:/LOG: ──▶ prediction.json for this task ──▶ plan Final Implementation Notes
                        UNMAPPED_SOURCE ──offer──▶ annotate | attribute --propose (→ seeded.yaml, origin observed) | continue
Step 8  procedure gates ──▶ testmap_fresh ──▶ stale --task (n006: STALE / EVIDENCED / UNSTAMPED, adopted(...) shown) + adopt seeds on touched test files
Step 9  ait gates run ──▶ testmap_check (SEEDED:, ADOPTED:, UNMAPPED_SOURCE:, strict past bootstrap) ──▶ tests_pass = ./ait test --gate (policy)
        full run ──▶ automatic score against the newest prediction ──▶ PREDICTION_MISSED:<id> ──▶ attribute (decide | --propose → seeded.yaml)
```

### Policy flip

```
/aitask-testmap-onboard --policy selected
   → readiness → READINESS:min_scored_full_runs|met|34  READINESS:max_false_negatives|met|0  READINESS:require_opaque_proofs|met  READINESS:approved_by|unmet|-
               → LEVEL:2 NEXT:scaffold  ADOPTED_UNREVIEWED:618|0.61  SEEDED:412  POLICY:full|would run selected: 14 units
   → AskUserQuestion: record approval {who, statement} → config.yaml completion.mode: selected, run_gate_admission.approved_by → ait: commit
   → the next tests_pass runs the selection; any later unmet criterion demotes it loudly
```

### Reading the map without running anything

```
ait test --howto ──▶ registry + ledger + config.yaml docs:/notes: + onboard.yaml ──▶ TESTMAP:/RUNNER:/FULL_GATE:/GATE:/VERBS:/AXES:/RESOURCE:/NEW_TEST:/DOCS:/NOTES:
aitask-qa 3a ──▶ ait testmap explain --sources <changed> --format table ──▶ Covered | Covered (adopted) | Covered (seeded) | GAP
ait setup ──▶ report_testmap_state() ──▶ TESTMAP:<state>
onboard status ──▶ phases · ONBOARD_NEXT: · seed queue per origin · adopted unreviewed · ratios · oldest pending
```
<!-- /section: data_flow -->

<!-- section: components [dimensions: component_*] -->
## Components

*(inherited from n006)* means carried as n006 specified it, which is itself
the resolution of n001 and n002; *(merged from n007 and n008)* names what
each contributed; *(new: introduced to bridge n007 and n008)* is a component
neither parent had in that form.

<!-- section: component_adoption_ledger [dimensions: component_registry_loader, component_seeder, component_onboarding_engine_verbs] -->
### Adoption ledger: seeded → adopted → reviewed *(new: introduced to bridge n007 and n008)*

The three-file state of a machine-proposed edge and the rules that move it:
`registry/seeded.yaml` (n007's queue: select-only, no stamp, invisible to
`stale`, never `--strict`), `registry/adopted.yaml` (n008's provenance: a
stamped edge accepted by class, shown as `adopted(...)`, counted as
`ADOPTED_UNREVIEWED`, cleared by a human re-stamp) and `onboard.yaml`'s
`rejections[]`. Transitions: `onboard seed` / `attribute --propose` → seeded;
`onboard adopt --class` → adopted; `onboard adopt <row>` / the `testmap_fresh`
in-gate step → reviewed; `verify` / `stale --confirm*` / `annotate` → reviewed;
`onboard reject` → rejected. Load rule: a seed shadowed by any stamped edge is
dropped with `SEED_SHADOWED`. Autonomous profiles may seed, and may adopt only
origins at confidence 1.0. Its tradeoffs are recorded under
`tradeoff_two_edge_states_during_adoption` (three provenances a reader must
keep apart) and `tradeoff_seed_precision` (an adopted edge is still a machine
claim in a human annotation's clothes).
<!-- /section: component_adoption_ledger -->

<!-- section: component_seeder [dimensions: component_seeder] -->
### Seeder *(merged from n007 and n008)*

`internal/seed`, verb `onboard seed [--from static,convention,cochange,plan,prose,coverage]
[--min-cochange 2] [--accept-min 0.85] [--coverage-report <f>|--per-unit] [--apply] [--json --out <f>]`:
the origin table above — `static:{package,invocation,import}` from
`internal/deps` facts for the test file only (direct, never the closure),
`convention` from `config.yaml conventions:` (seeded by `detect` per runner),
`cochange` from one `git log --name-status -M --format=%H%x00%s` pass over
`(t<id>)` commits (pairs counted per distinct task, `--min-cochange 2`,
per-commit grouping fallback, cached by HEAD sha, `SEED_HISTORY:shallow|<n>`),
`plan` through the explain cache, `prose` from header comments and `# Covers:`
lines, `coverage` opt-in (coverage.py contexts, `go -coverprofile` per unit,
LCOV with a test column, plugin `{test, covers}` lines). Confidence table
1.0 / 0.95 / 0.90 / 0.85 / 0.70 / 0.60 / 0.50 / 0.30 / 0.20+0.20n ≤ 0.60,
noisy-OR, ordering only. Helpers separated first (roots + fan-in) with
`SEED_HELPER:` and `SEED_READS:` lines; `SEED_KIND:`, `SEED_BATCH_NO:`,
`SEED_MEMBER:`, `SEED_AXIS:` from `onboard classify`'s signals. Output
`SEED:<test>|<source>|<origins>|<confidence>`; `--apply` writes
`registry/seeded.yaml` deterministically sorted; rejected pairs never
re-proposed; shadowed pairs dropped. Budget: static + convention < 2 s,
cochange < 5 s over 600 commits on the aitasks shape. Fixtures: a synthetic
repo per origin with a `(t<id>)` history.
<!-- /section: component_seeder -->

<!-- section: component_onboarding_engine_verbs [dimensions: component_onboarding_engine_verbs] -->
### Onboarding verbs *(merged from n007 and n008)*

`internal/onboard` behind `onboard detect [--write] | inventory | seed |
classify [--apply] | adopt | reject | scaffold | status | finish` and the
`onboard.yaml` phase ledger. `detect`: the closed detector list with an
evidence field per row (`bash-file`, `pytest`, `go-test`, `gradle-class`,
`kmp-sourceset`, `suite-from-config`), `UNIVERSE:`, `UNLISTED:`,
`AGGREGATE_RUNNER:`, `SERIAL_LIST:`, `RESOURCE_HINT:`, `SUITE_CANDIDATE:`,
`RUNNER_SCRIPT_NEEDED:`; `--write` emits the level-0 files and `conventions:`;
re-running on an existing table prints `DETECT_DIFF:` and writes nothing
without `--force`. `inventory`: `scan` + every `list` + `check`, `UNREGISTERED:`
as the to-do list. `classify`: n006's `classify --suggest` plus the three
onboarding signals; `--apply` writes the level-2 lines and `needs:` bindings
for confirmed rows. `adopt`: `--class <origin> [--accept-min] [--scope <glob>]
[--dry-run]` (bulk, provenance row) or `<test> [<source>]` / `--area <a>
--batch <n>` / `--files-from -` (per row, reviewed); writes through the
rewriter; `ADOPT_REFUSED` / `ADOPT_SKIP` / `WROTE` / `ADOPT_SUMMARY`.
`reject <test> <source> --reason`. `scaffold --axes | --runner <builtin> --as
<name> | --members` (level 3). `status`: phase rows, `ONBOARD_NEXT:`, seed
queue per origin, `ADOPTED_UNREVIEWED`, ratios, oldest pending seed. `finish`:
requires status green; flips `require_stamp` and `--strict`; records the
phase. The engine reads `onboard.yaml`'s `task:` and `level:` and writes
phase rows; task creation, profile edits, `project_config.yaml`, `gates.yaml`,
`CLAUDE.md` and commits are the skill's, through the framework's own scripts.
Go tests on fixture repositories in `t.TempDir()`: one per detector and per
detect shape (bash-only, pytest, go, gradle, gradle-per-source-set), the
fan-in reclassification, golden files for block placement per language,
every refusal branch, resume from each phase.
<!-- /section: component_onboarding_engine_verbs -->

<!-- section: component_onboarding_skill [dimensions: component_onboarding_skill] -->
### Onboarding skill `aitask-testmap-onboard` *(merged from n007 and n008)*

Profile-aware stub + `SKILL.md.j2` (resolver key `onboard`) with one
procedure file per phase (`detect.md`, `inventory.md`, `seed.md`,
`waivers.md`, `enable.md`, `full-run.md`, `adopt.md`, `classify.md`,
`scaffold.md`, `finish.md`), Claude Code first, Codex and OpenCode ports as
follow-up tasks; rendered goldens under
`tests/golden/skills/aitask-testmap-onboard/`. Flow: preconditions → read-only
survey and level proposal → one aitask per level created with the seed dump
attached and claimed → task-workflow (phases at Step 7 with per-phase
commits, the diff at Step 8, the first full run at Step 9) → timeout from the
ledger, `readiness`, the next level's task with `depends:`. Confirmations:
per runner, per evidence class (accept all / review a sample of ten / skip),
per kind change individually, `UNLISTED` files (bind / not a test / later),
the config table once (`test_command` → `./ait test` with the previous value
moved to a `full: true` suite runner; `verify_build` left alone unless the
user names it as the suite — thinking_backend; `gate_command_exit_contract`
+= `test_command`; profiles `default_gates` += `tests_pass`, `testmap_check`,
`testmap_fresh`; `bootstrap_until`; `docs:` and `notes:`; a hand-maintained
`CLAUDE.md` Testing paragraph). Re-entry at `ONBOARD_NEXT:`; every phase
idempotent; `--no-task`; `--policy selected` re-entry writes the flip only on
`ADMISSIBLE` with `approved_by`. Headless: level 0 + `static:package`
adoption only, no prompts, no kinds, no policy flip.
<!-- /section: component_onboarding_skill -->

<!-- section: component_test_entrypoint [dimensions: component_test_entrypoint] -->
### Test entrypoint `ait test` *(merged from n007 and n008)*

`.aitask-scripts/aitask_test.sh`, a ~150-line bash front over the n006 shim:
resolves `MODE` (completion iff `--gate` or `$AIT_GATE_TASK_ID`; advisory iff
`--advisory`; else interactive), `TASK` (`--task` > `$AIT_GATE_TASK_ID` >
`aitask/<task_name>` branch > single own lock via `aitask_lock.sh --list-mine`
> `NO_TASK`), `INTAKE` (change surface piped; `--dirty`; `--all`; named
paths, a source path as a one-file `TASK:` set) and `POLICY` (completion:
`config.yaml completion.mode` re-checked against `readiness`); calls the
engine `test` composite; falls back to `aitask_run_project_command.sh
test_command` when `aitestmap/` is absent and to the suite runner's
`fallback_command` when the engine is absent and the policy allows; in
`--advisory` mode (n007's `aitask_affected_tests.sh` folded in) prints
`VERDICT:/REASON:/DETAIL:/LOG:/SELECTED:/UNMAPPED_SOURCE:/UNKNOWN:`, exits
`0/1/2/3` on `aitask_run_project_command.sh`'s contract, maps every absence
and a post-deadline refusal to a skip reason, writes the log under
`.aitask-gates/<task>/affected_<run-id>.log` and appends nothing to any
ledger; prints `MODE / TASK / INTAKE / POLICY / SELECTED / RUN / RESULT`,
`UNANNOTATED_TEST` + `HINT`, `UNMAPPED_SOURCE`; exits `0 / 1 / 2 / 3 / 75 /
64`; dispatcher arm `test)`; five permission touchpoints;
`tests/test_ait_test_entrypoint.sh` drives a fixture repository with
`AIT_TESTMAP_BIN` pointing at a fake engine in all three modes.
<!-- /section: component_test_entrypoint -->

<!-- section: component_test_front_verb [dimensions: component_test_front_verb] -->
### Engine `test` composite *(inherited from n007; brief split out)*

The engine side of the front: `test --task <id> --changes - | --paths <p>... |
--all [--explain] [--budget-s] [--format lines|json|tokens] [--run <id>]`
runs `select --include-stale` → `schedule` → `run` in one process and prints
`SELECTED:<n>|<groups>|<est_s>|<seeded_n>|<adopted_n>`, `UNMAPPED_SOURCE:<path>`
lines, the ranked rows, waves, results per id and `RESULT:pass|fail|skip|deferred|<run_id>`
before the front adds its own lines; `--all` is `run --all` (anchors evidence,
scores the newest prediction, honours `subsumed_by`); `--explain` stops after
`select`. It never resolves a task, reads a profile or touches a gate ledger —
those are the bash front's.
<!-- /section: component_test_front_verb -->

<!-- section: component_agent_brief [dimensions: component_agent_brief] -->
### Agent brief *(merged from n007 and n008)*

`internal/brief`, verb `brief [--md]`, surfaced as `ait test --howto [--md]`
and `ait testmap brief`: `TESTMAP:<state>|LEVEL:|POLICY:|seeds pending|adopted
unreviewed`, `RUNNER:` per runner (name, kind, unit count from `list`,
invocation shape, resources, `subsumes`), `FULL_GATE:` (the `full` runner, its
p95, `= test_command`, the `tests_pass` timeout), `GATE:` (the gate chain and
what `--gate` would run now), `VERBS:`, `AXES:`, `RESOURCE:` with refusal
semantics, `NEW_TEST:`, `DOCS:` per `config.yaml docs:`, `NOTES:` verbatim,
`ONBOARD_NEXT:` while a ledger is unfinished; before onboarding
`TESTMAP_ABSENT` plus the `test_command`; < 100 ms warm.
<!-- /section: component_agent_brief -->

<!-- section: component_agent_instructions [dimensions: component_agent_instructions] -->
### Agent instructions *(merged from n007 and n008)*

The `## Running Tests` section above in `seed/aitasks_agent_instructions.seed.md`,
installed by `assemble_aitasks_instructions()` into `CLAUDE.md`'s `>>>aitasks`
block, `AGENTS.md`, `.codex/instructions.md` and the OpenCode mirror on every
`ait setup` and `ait upgrade`; fourteen lines, no agent named, no project
specifics; `tests/test_agent_instructions.sh` T40 pins the heading in all four
surfaces through a real `install.sh --dir`; the hand-maintained `CLAUDE.md`
case is the level-0 task's edit.
<!-- /section: component_agent_instructions -->

<!-- section: component_completion_policy [dimensions: component_completion_policy] -->
### Completion policy *(inherited from n008)*

`aitestmap/config.yaml completion: {mode, deferred, on_empty_selection,
engine_absent}`; `mode: selected` written only by the skill's `--policy`
re-entry after `ADMISSIBLE` with `approved_by`; `ait test --gate` re-checks
`readiness` on every completion run and demotes loudly (`POLICY_DEMOTED:`);
the flip is human, the demotion automatic, so the policy fails only toward
running more; `readiness` prints `POLICY:<mode>|<what --gate would run now>`.
<!-- /section: component_completion_policy -->

<!-- section: component_workflow_seam [dimensions: component_workflow_seam] -->
### Workflow seam — the data edits *(inherited from n008)*

The Step-7 test-loop paragraph, the `build-verification.md` branch, the two
rows and two exports in `run_project_command_key()`, `--task-id`'s export in
`aitask_run_project_command.sh`, `gates_reference.yaml` entries (no
`testmap_run`), profiles' `default_gates`, the `test)` dispatcher arm, the
extension-points sections, the extended `tests/test_gate_verifiers.sh`,
`tests/test_serial_carveout_doc_drift.sh` per n006, regenerated goldens;
`tests/test_no_unscoped_task_commit.sh` unaffected because the skill commits
through `aitask_task_commit.sh`.
<!-- /section: component_workflow_seam -->

<!-- section: component_workflow_integration [dimensions: component_workflow_integration] -->
### Workflow integration — the procedure edits *(inherited from n007; helper folded into the entrypoint)*

`task-workflow/affected-tests.md` called once before Step 8 behind
`affected_tests: run|show|off` (`run` default; `show` → `--explain`; `off`
renders it away); the branch table; the verdict in the plan's Final
Implementation Notes, never in the gate ledger. `aitask-gate-testmap-fresh`
gains the adopt-on-touched-files step. `aitask-qa` `test-discovery.md`
registry-first with `explain --sources … --format table`, `test-execution.md`
4a–4d. `profiles.md` row; `remote.yaml: affected_tests: run`. `ait setup`
prints `TESTMAP:`. pickrem / pickweb inherit and see a printed skip on Web.
Goldens regenerated for every profile × agent; `aitask_skill_verify.sh` run.
<!-- /section: component_workflow_integration -->

<!-- section: component_qa_integration [dimensions: component_qa_integration] -->
### aitask-qa integration *(merged from n007 and n008)*

`test-discovery.md` 3a–3c map the changed sources through `ait testmap
explain --sources <paths> --format table` when `aitestmap/` exists (`Covered`,
`Covered (adopted)`, `Covered (seeded)`, `GAP` = no edge and no test-dep),
falling back to the naming-convention scan otherwise; `test-execution.md` 4a
runs the configured `./ait test` through `aitask_run_project_command.sh
test_command --task-id <id>`, 4b runs named units through `ait test <path>`,
4c gains the `REFUSED (host resources)` row treated as `SKIP` in the health
score, 4d scores coverage from registry edges with seeded rows counted as
coverage that exists (QA measures whether a test exists, not whether its
claim is fresh).
<!-- /section: component_qa_integration -->

<!-- section: component_gates [dimensions: component_gates] -->
### Gates *(merged from n007 and n008; n001/n002's three-gate shape replaced)*

`testmap_fresh` (procedure; the in-gate adopt step added) and `testmap_check`
(machine, `max_retries 0`, `timeout 120`, `unlocks: [tests_pass]`) in
`gates_reference.yaml` synced to `gates.yaml`; the completion test gate is the
existing `tests_pass` with `test_command: ./ait test` and
`gate_command_exit_contract: [test_command]`; `testmap_run` retired as a name;
`aitask_gate_testmap_run.sh` not written; `aitask_gate_testmap_check.sh` stays
and reports `SEEDED:<n>`, `ADOPTED:<n>` (informational) and
`UNMAPPED_SOURCE:<path>` (fails under `--strict` past `bootstrap_until`);
`run_gate_admission` and `readiness` gate the policy flip; gates are enabled by
the onboarding `enable` phase with confirmation, never by hand and never by
`ait setup`.
<!-- /section: component_gates -->

<!-- section: component_skill [dimensions: component_skill] -->
### Skills *(merged from n007 and n008)*

`aitask-testmap` (n006's obligations; opens with `ait test --howto`; hands an
un-onboarded repo to `aitask-testmap-onboard`); `aitask-gate-testmap-fresh`
(n006's procedure gate plus the adopt / reject / leave step for seeds on the
task's touched test files; an `adopted(...)` row is confirmed knowing it is a
class-accepted claim); `aitask-testmap-onboard` (new, above). Every skill's
runtime knowledge of how to run tests is the seeded block plus `--howto`,
never prose in a `SKILL.md`. Claude Code first; wrapper surfaces regenerated
by `aitask_audit_wrappers.sh apply-wrapper`; Codex and OpenCode ports as
separate tasks.
<!-- /section: component_skill -->

<!-- section: component_go_engine [dimensions: component_go_engine] -->
### Go engine and CLI *(inherited from n006; three packages added)*

`engine/cmd/ait-testmap` with n006's `internal/{registry,axes,annot,deps,changesurface,selectr,sched,runner,cost,feedback,stale,gitx,platform}`
plus `internal/seed`, `internal/onboard`, `internal/brief`; Go 1.26 with a
pinned toolchain, `CGO_ENABLED=0`, `-trimpath -buildvcs=false -ldflags "-s -w
-X version/commit/contract"`; deps `gopkg.in/yaml.v3`, `bmatcuk/doublestar/v4`,
`golang.org/x/sync` only; stdlib `flag` verb table, `syscall.Flock`, `os/exec`
git; line-protocol stdout, `--json`, per-verb exit contracts; never writes
`aitasks/`, `aiplans/`, `.aitask-data/`, a gate ledger, `project_config.yaml`,
`gates.yaml`, profiles or `CLAUDE.md`; never invokes `aitask_*.sh`; never
needs its own install root. Fixture repos in `t.TempDir()` gain synthetic
`(t<id>)` histories and one fixture per detect shape.
<!-- /section: component_go_engine -->

<!-- section: component_engine_binary [dimensions: component_engine_binary] -->
### Engine binary identity and budget *(inherited from n006; verbs and budgets added)*

Version / commit / contract embedding, `version --json` printing `ENGINE:<path>`,
`CONTRACT_MISMATCH`, the `go test -bench` budgets with the 2× rule, pools
capped at 8; verb table extended by `test`, `brief`, `onboard {detect,
inventory, seed, classify, adopt, reject, scaffold, status, finish}` and
`costs --gate-timeout`; budgets added: `brief` < 100 ms warm, `onboard seed`
static + convention < 2 s and cochange < 5 s over 600 commits on the aitasks
shape, `onboard status` < 200 ms; `detect` is excluded from the latency table
(once per onboarding, not on any gate path). Contract stays 1; `seeded.yaml`,
`adopted.yaml` and `onboard.yaml` carry `contract:` and a newer one is refused
the same way.
<!-- /section: component_engine_binary -->

<!-- section: component_engine_packaging [dimensions: component_engine_packaging] -->
### Engine install, upgrade, regeneration *(inherited from n006; `report_testmap_state()` added)*

`install_engine_binary()` reached by `ait setup` and `ait upgrade` (through
`install.sh`'s `--source-only` path); source order `--local-engine` >
exact-version release asset > `--engine-from-source` > `ENGINE_MISSING`
warning; checksum; atomic install to `$AITASKS_HOME/engine/v<V>/`; `version
--json` self-check; `.dev` marker; `--no-testmap` / `AIT_TESTMAP_FETCH=0`;
`HOME_LEGACY:` hint; `.aitask-testmap/` gitignored by setup;
`aitask_engine.sh build|test|cross|prune|home [--migrate]`. After it,
`report_testmap_state()` prints `TESTMAP:engine-missing|absent|bootstrapping|<next>|onboarded`
with the onboarding hint on `absent`; the re-inserted instructions block
carries the Running Tests section. `aitask_test.sh` is a framework script
shipped in the tarball like every `aitask_*.sh`; nothing to install.
`tests/test_install_engine_binary.sh` through a real `install.sh --dir`
asserts the path and each `TESTMAP:` state.
<!-- /section: component_engine_packaging -->

<!-- section: component_binary_distribution [dimensions: component_binary_distribution] -->
### Binary distribution *(inherited from n006)*

`engine/build.sh` as the single build and matrix command; the release
`engine` job (`setup-go` from `engine/go.mod`, `go vet`, `go test`, `build.sh
all`) producing `ait-testmap_<V>_{linux,darwin}_{amd64,arm64}` and
`ait-testmap_<V>_SHA256SUMS.txt`, attached by both `action-gh-release` steps
with `release needs: [plan, engine]`; the unchanged VERSION-matches-tag guard;
`engine-check.yml` on push / PR for `engine/**`; `lib/platform_detect.sh`; the
shim's strict handshake; `test_testmap_shim.sh`, `test_platform_detect.sh`,
`test_aitasks_home.sh`; `aidocs/framework/go_engine.md`; `release-packaging.yml`
and nfpm `arch: all` untouched.
<!-- /section: component_binary_distribution -->

<!-- section: component_user_root [dimensions: component_user_root] -->
### Per-user root *(inherited from n006)*

`lib/aitasks_home.sh` exporting `AITASKS_HOME=${AITASKS_HOME:-$HOME/.aitasks}`
and `aitasks_engine_dir`; no fallback to `~/.aitask/`; sourced by the shim,
`install_engine_binary`, `aitask_engine.sh`, the verifiers and now
`aitask_test.sh`; `ait setup` prints `AITASKS_HOME:<path>`.
<!-- /section: component_user_root -->

<!-- section: component_framework_home [dimensions: component_framework_home] -->
### Framework home report and migration verb *(inherited from n006)*

`ait engine home [--migrate]` with the known set including `pypy_venv`; `ait
setup` hints, does not migrate; the default flip is a named follow-up
admitted after `tests/test_aitasks_home.sh` through a real `install.sh --dir`.
<!-- /section: component_framework_home -->

<!-- section: component_registry_loader [dimensions: component_registry_loader] -->
### Registry loader and writer *(merged from n007 and n008)*

n006's six tables (edges, scopes, areas, rules, waivers, axes), id grammar
`<path>[#<member>][@<variant>]`, `owns:` routing, deterministic writes and
check rules unchanged; two tables added: `seeds` from `registry/seeded.yaml`
(rows `{test[#member], covers, origin[], confidence, evidence{}, proposed_at}`)
and `adopted` from `registry/adopted.yaml` (rows `{test, source, origin[],
confidence, adopted_at, task}`); a seed whose `(test, covers)` also exists as a
stamped edge is dropped at load with `SEED_SHADOWED`; an adopted row whose
edge no longer carries a stamp is `ADOPTED_ORPHAN` (check); write routing
gains `onboard seed → seeded.yaml`, `onboard adopt → seeded.yaml (row removed)
+ adopted.yaml (class only) + the test file`, `onboard reject → seeded.yaml +
onboard.yaml`, `attribute --propose → seeded.yaml`; `config.yaml` gains
`completion:`, `conventions:`, `helper_roots:`, `helper_fanin:`, `exclude:`,
`docs:`, `notes:`, `broad_threshold_s`; golden tests pin the two new merges and
the shadow rule.
<!-- /section: component_registry_loader -->

<!-- section: component_variant_axes [dimensions: component_variant_axes] -->
### Variant axes *(inherited from n006)*

`axes.yaml`, `<unit>@<variant>`, the facet join, `testmap:axis`, `--axis`;
unchanged. Level-3 `onboard scaffold --axes` writes only the skeleton the
maintainer fills; the grid heuristic proposes, a person declares.
<!-- /section: component_variant_axes -->

<!-- section: component_axes [dimensions: component_axes] -->
### Axis resolver verbs *(inherited from n006)*

`axes --list | --check | --explain <path>`; unchanged.
<!-- /section: component_axes -->

<!-- section: component_cell_enumeration [dimensions: component_cell_enumeration] -->
### Enumeration and reconciliation *(inherited from n006)*

The runner's `list` is the universe; `variants:` persisted by `scan --apply`;
`UNCOVERED_VALUE`, `UNMAPPED_ARTIFACT`. `onboard detect`'s `UNIVERSE:` is the
same count taken before runners exist; `onboard inventory` is the first
consumer of `UNREGISTERED:` rows as a to-do list.
<!-- /section: component_cell_enumeration -->

<!-- section: component_annotation_scanner [dimensions: component_annotation_scanner] -->
### Annotation scanner and rewriter *(inherited from n006; adopt as a caller)*

Grammar v3 (`testmap:unit` blocks; kind / covers / area / scope / trigger /
reads / axis / reviewed / runner / needs / batch; per comment leader and
Python module docstrings read; unknown keys refused with a line number), the
line-targeted rewriter with `REWRITE_CONFLICT`, `annotate --from-body`
unchanged. `onboard adopt` is a new caller writing `testmap:covers` lines at
the fixed per-language position (comments only, never into a docstring, inside
the member's `testmap:unit` block for a member seed), each stamped
`@<date>/<blob10>` at adopt time. `# Covers:` prose headers are shown beside
seeds as reviewer context and read by the `prose` origin at 0.30, never
matched by the annotation scanner.
<!-- /section: component_annotation_scanner -->

<!-- section: component_dependency_scanners [dimensions: component_dependency_scanners] -->
### Dependency scanners *(inherited from n006; facts shared with the seeder)*

bash / python / go / kotlin (opaque contract) / Gradle scanners, plugins, the
opt-in `android-res` symbol scanner, the XDG blob-keyed cache — unchanged.
The bash scanner's literal-invocation facts, the python / kotlin scanners'
direct main-root imports and the go scanner's package membership are exposed
to `internal/seed` as `static:{invocation,import,package}` — same scan, same
cache, read once; the deeper closure stays the selector's d2 walk and is never
seeded as an edge.
<!-- /section: component_dependency_scanners -->

<!-- section: component_selector [dimensions: component_selector] -->
### Selector *(inherited from n006; seeded edges, `explain --sources`, summary lines)*

Intake, the graded walk, variant expansion and axis join, test-dep, `ESCALATE`,
scoped join, ranking, invocation groups, stale marks, `--include-stale`, the
suite budget, cut knobs, formats, prediction record, explain — unchanged. A
seeded edge is walked like an annotation edge at d1 with reason
`edge(seeded:<origins>)` and never contributes a stale mark; an adopted edge
is an annotation edge whose reason carries `adopted(<origins> <confidence>)`;
`explain --sources <path>... --format table` prints the reverse view for
`aitask-qa`; the `test` composite prints `SELECTED:` and `UNMAPPED_SOURCE:`
ahead of the rows; `ait test <source path>` reaches it as a one-row `TASK:`
change set.
<!-- /section: component_selector -->

<!-- section: component_runner_contract [dimensions: component_runner_contract] -->
### Runner contract and repository *(merged from n007 and n008)*

n006's `describe` / `list` / `run` contract, TSV list with member and variant
ids, `results.jsonl` with child rows, `runner.json` overhead, bindings,
`builtin:` with `command:`/`cwd:` and shadow-by-name, batching, timeouts,
reconciliation, exit contract `0/1/2/75/64` — unchanged. Repository keys
added: `subsumed_by: <suite>` (so `run --all` executes a `full: true` suite
once and never its subsumed runners beside it) and `fallback_command:` on a
suite runner (what completion runs when the engine is absent and
`completion.engine_absent` is `fallback_command`); `onboard scaffold --runner
<builtin> --as <name>` writes a project script whose `describe` / `run`
delegate to the builtin and whose `list` prints `SCAFFOLD_TODO` until filled.
<!-- /section: component_runner_contract -->

<!-- section: component_reference_runners [dimensions: component_reference_runners] -->
### Reference runners *(merged from n007 and n008)*

n006's builtins (bash-file, pytest with junitxml and the serial carve-out
pinned, go-test, gradle-class with JUnit inversion and the zero-match trap,
suite with `children:` post-processor, device with the allocator handle;
`engine-test` over `engine/`) and thinking_app's project runner unchanged;
`onboard detect` seeds the repository — bash-file for `tests/**/test_*.sh`,
pytest for `test_*.py` / `*_test.py` with an aggregate runner's serial list
becoming `testmap:batch no` candidates, go-test per package from `go list`,
gradle-class for `src/test/**/*.kt|java`, the `kmp-sourceset` mapping
(`commonTest` / `androidHostTest` → gradle-class unit runners on
`:<module>:jvmTest` / `testDebugUnitTest`, `androidDeviceTest` → `device` on
`connectedDebugAndroidTest` with `needs: [emulator]`), and a `full: true`
suite runner named `full` wrapping `test_command` (or `verify_build` only when
the user names it as the suite) whose `children:` post-processor is a builtin
inverting pytest junitxml, bash-file names from the per-file exit and `go test
-json` events to registered ids, and whose `fallback_command:` is the previous
`test_command`; `bash-file list --invocations` prints the literal paths a test
references for the seeder.
<!-- /section: component_reference_runners -->

<!-- section: component_scheduler_resources [dimensions: component_scheduler_resources] -->
### Scheduler and resources *(inherited from n006)*

Kinds, scopes, `flock(2)` slots, admission deferral, allocators, waves,
`broad_after_unit`, admission-holding invocations ordered last, `concurrency:
serial|parallel` — unchanged. `detect`'s `RESOURCE_HINT` rows become
`resources.yaml` entries the scheduler already understands (aitasks:
`repo-git-index` mutex, worktree scope); an `ait test` run on thinking_app is
one Gradle invocation under the heavy-run slot, and a refusal at the deadline
is exit 75 (advisory: `skip:admission_refused`).
<!-- /section: component_scheduler_resources -->

<!-- section: component_cost_ledger [dimensions: component_cost_ledger] -->
### Cost ledger *(merged from n007 and n008)*

n006's Welford / P² / invocation-group ledger, `costs --update`, `last_pass`
and flake per id, group costing, `costs/predictions.yaml` — unchanged. Run ids
are prefixed `test-` (interactive and advisory), `gate-` (completion) and
`full-` (`--all`) so ordinary rows say which surface produced them; all three
feed cost and evidence exactly like gate runs; the `SELECTED:` estimate is the
same per-group sum the budget uses; `costs --gate-timeout tests_pass` prints
`GATE_TIMEOUT_SUGGESTED:<gate>|max(600, 3 × p95 of the newest full run on this
host class)`, which onboarding writes into the project's `gates.yaml` after the
first measured full run.
<!-- /section: component_cost_ledger -->

<!-- section: component_evidence_join [dimensions: component_evidence_join] -->
### Evidence join *(inherited from n006)*

Per reached variant; `EVIDENCED` only when every variant is anchored; never
rewrites; `--confirm-evidenced` the only bulk autonomous confirmation. Seeded
edges are not joined (no stamp to heal); adopted edges are joined like any
stamped edge; the level-0 task's first full run is what first populates the
anchors it reads.
<!-- /section: component_evidence_join -->

<!-- section: component_feedback_tools [dimensions: component_feedback_tools] -->
### Feedback tools *(merged from n007 and n008)*

`score` automatic after `run --all` and after a `full: true` suite run;
`attribute` (missing-edge / test-wrong / source-wrong, missing-axis-source
widen-only, missing-trigger / area-too-narrow) gains `--propose` (default in
autonomous profiles) writing the row to `seeded.yaml` with origin `observed`
and the run id as evidence instead of to `observed.yaml`, so autonomous runs
grow the review queue and never the accepted map; `readiness` additionally
prints `LEVEL:<0-3>`, `NEXT:`, `ADOPTED_UNREVIEWED:<n>|<ratio>`, `SEEDED:<n>`
and `POLICY:<completion.mode>|<what ait test --gate would run now>`; it still
enables nothing.
<!-- /section: component_feedback_tools -->

<!-- section: component_freshness [dimensions: component_freshness] -->
### Freshness *(inherited from n006; one stamp writer, one gate step)*

Per-edge `@<date>/<blob10>` stamps written only by `verify`, `annotate`,
`stale --confirm*` and now `onboard adopt`; member-block scoping; variants
carry no stamp; `last_pass` per id; `bootstrap_until`, `require_stamp`,
`flake_threshold`; the `testmap_fresh` procedure gate dispatched before the
change summary so rewrites ride the `(t<id>)` commit, gaining the step that
offers to adopt the seeds of the test files this task touched; not a git hook
and not a code-agent hook. An adopted stamp is a stamp like any other and the
procedure gate handles it identically, with the `adopted(...)` display as
context.
<!-- /section: component_freshness -->

<!-- section: component_staleness_tool [dimensions: component_staleness_tool] -->
### Staleness tool *(merged from n007 and n008)*

n006's `stale --task --changes - | --all` line classes, `%25`/`%7C` encoding,
unevidenced variants on `STALE` rows, `CHECK_STRUCTURAL:<n>`, `--strict` on
`STALE_PATH`, rename hints, `--confirm`, `--confirm-source`,
`--confirm-evidenced`, `--retarget` — unchanged. Seeded edges are excluded
from every class; `stale --all` adds `SEEDED:<n>` and `ADOPTED:<n>` summary
lines; a `STALE` or `EVIDENCED` row whose edge has an `adopted.yaml` row
carries `adopted(<origins> <confidence>)` in its `DISPLAY` line so the
procedure gate knows it is confirming a class-accepted claim.
<!-- /section: component_staleness_tool -->

<!-- section: component_suite_registry [dimensions: component_suite_registry] -->
### Scoped-row registry and areas *(inherited from n006; classify signals added)*

`areas.yaml` seedable via `areas --import-codemap`, `_scoped.yaml` rows with
`reads_from`, `owns:` by area, the d1 join, the suite budget with `DEFERRED`,
`DEAD_SCOPE` and `KIND_MISMATCH|CONVERT_TO_SUITE`, missing-trigger /
area-too-narrow — unchanged; `classify --suggest` gains the three onboarding
signals (recorded p95 above `broad_threshold_s`, a source-set or directory
convention, a resource named in the file) printed as the reason on each
`CLASSIFY:` line, and `onboard classify --apply` writes the confirmed rows'
source lines at level 2.
<!-- /section: component_suite_registry -->

<!-- section: component_broad_test_scopes [dimensions: component_broad_test_scopes] -->
### Broad-test scheduling policy *(inherited from n006)*

`broad_after_unit`, `device_policy`, `STALE_AREA`, opt-in `REVIEW_DUE`,
attribute widening, fixture pins, `full: true` suite rows with child rows —
unchanged; `completion.deferred: run` means the suite budget applies to the
interactive loop only.
<!-- /section: component_broad_test_scopes -->
<!-- /section: components -->

<!-- section: assumptions [dimensions: assumption_*] -->
## Assumptions

**Inherited unchanged from n006** (full text in the node metadata; each
originates in n001 or n002 and was made precise in n003–n006):
`assumption_areas_express_suite_blast_radius`, `assumption_axis_membership_declarable`,
`assumption_axis_sources_declarable`, `assumption_batch_per_unit_timing_reportable`,
`assumption_blob_digest_is_staleness_key`, `assumption_broad_tests_area_scoped`,
`assumption_cells_enumerable_by_plugin`, `assumption_engine_latency_targets`,
`assumption_existing_locks_wrappable`, `assumption_git_history_is_freshness_clock`
(co-change reads history as a *seed* source, never as a freshness or evidence
source), `assumption_go_toolchain_available`, `assumption_go_toolchain_ci_and_dev_only`,
`assumption_home_symlink_compatibility`, `assumption_kotlin_scanner_fail_closed`,
`assumption_legacy_user_root_coexists`, `assumption_one_engine_per_framework_version`,
`assumption_passing_run_anchors_edges`, `assumption_platform_matrix_sufficient`,
`assumption_release_asset_reachable`, `assumption_release_assets_reachable`,
`assumption_static_granularity_v1`, `assumption_target_repos_accept_aitestmap_root`
(now also `onboard.yaml`, `seeded.yaml` and `adopted.yaml` under that root),
`assumption_testmap_token_no_collision`, `assumption_variant_universe_from_runner_list`.

**Merged (both parents modified them):**

- **`assumption_change_surface_is_intake`** — the change surface is the intake
  for every `--task` path: the gate verifiers, `ait test` in all three modes,
  `stale --task`. `<path>...` is the one explicit-list intake (`TASK:` rows),
  `--dirty` the explicit and printed no-task intake, `--all` has none. An
  `UNKNOWN:` row refuses selection in interactive and completion mode and is
  `VERDICT:skip REASON:unknown_paths` naming the paths in advisory mode. The
  before content a symbol scanner needs comes from `HEAD:<path>` or the parent
  of the first `(t<id>)` commit (n005).
- **`assumption_gate_exit_contract_reused`** — the verifier contract `0/1/2/3`
  is reached through the *existing* `tests_pass` verifier running
  `test_command: ./ait test`; `run_project_command_key()` gains the 75 → error
  and 3 → error rows for opted-in keys and exports `AIT_GATE_TASK_ID` /
  `AIT_GATE_RUN_ID`; `testmap_check` keeps its own shell; advisory mode speaks
  `aitask_run_project_command.sh`'s `0/1/2/3` with 75 folded into a skip
  reason. n001 reused the contract through two dedicated shells; here it is
  one shell plus one row in the shared lib, which is what lets the legacy
  Step-9 helper and `aitask-qa` agree by construction.

**From n007, carried (with the resolution edits):**

- **`assumption_test_tools_detectable`** — verified on all five repositories;
  falsifier: build-time test generation → `DETECT_UNKNOWN`, the skill asks.
- **`assumption_seed_sources_measured`** — the merged origin table, with
  n008's co-change cap replacing n007's 0.5–0.8 ladder because the measured
  group shape does not disambiguate pairs.
- **`assumption_seeds_select_never_evidence`** — a *seed* may cause a test to
  run and may never suppress `STALE`, anchor evidence, satisfy `require_stamp`
  or count under `--strict`; promotion is an explicit adopt, by class (with
  provenance) or by row. Falsifier unchanged.
- **`assumption_instructions_block_reaches_agents`** — the mechanism: the
  `>>>aitasks` block is written and refreshed into every supported agent's
  file by `ait setup` / `ait upgrade`; fourteen lines, no agent named.
- **`assumption_helper_degrades_when_absent`** — restated for the advisory
  mode of `ait test`: absent engine / registry / `UNKNOWN:` rows / empty
  selection / admission refusal after the deadline are `skip` reasons; only an
  executed run is pass / fail; only an unwritable log is 3. This is what
  admits the pre-review procedure into every profile including `remote`.
- **`assumption_onboarding_is_a_task`** — onboarding writes committed files
  over several sessions, so each level runs as an aitask created and claimed
  by the skill, committing per phase under `(t<id>)`, re-entering at
  `ONBOARD_NEXT:`, archived by task-workflow with `finish` recorded in the
  ledger; `--no-task` for a repo that forbids tasks on the code branch.

**From n008, carried (with the resolution edits):**

- **`assumption_static_closure_seeds_edges`** — measured: 398/400 bash tests
  name their subject path literally, 320/320 Python tests import a lib module,
  52–72/400 match a naming convention; Go's subject is deterministic; Kotlin's
  is the n006 import closure. Falsifier: tests reaching subjects only through
  a dynamic dispatcher — no static rows; conventions plus co-change, or level 0.
- **`assumption_cochange_is_corroboration`** — 336 task groups in 400 commits
  at 1.14 commits each, few-to-few pairing; capped at 0.60 so it never decides
  alone; per-commit grouping where `(t<id>)` is absent; `min_cochange 2`.
- **`assumption_helpers_separable_by_fanin`** — helper roots plus fan-in ≥ 5 %;
  a misread hot module keeps `test-dep` selection; every reclassification
  listed.
- **`assumption_task_resolvable_from_session`** — the `aitask/<task_name>`
  branch in worktree mode, the single own lock in current-branch mode,
  `AIT_GATE_TASK_ID` in gate context; `AMBIGUOUS_TASK` and `--dirty` cover the
  rest; the advisory form always passes `--task` explicitly.
- **`assumption_full_run_expressible_per_repo`** — each target's completion
  suite is `ait test --all` or one `full: true` suite runner with a derivable
  `fallback_command`; thinking_backend's `verify_build` suite is the case the
  skill asks about.
- **`assumption_annotation_is_comment_only`** — adoption inserts comment lines
  only, never into a docstring; `ADOPT_SKIP:no-leader` otherwise; a member
  seed lands inside its `testmap:unit` block.
- **`assumption_instruction_block_is_read`** — agents follow the managed
  block, as the framework already relies on for `./ait git`; falsifier: a
  harness that ignores the file — `--howto` is the one-call fallback.
<!-- /section: assumptions -->

<!-- section: tradeoffs [dimensions: tradeoff_*] -->
## Tradeoffs

**Inherited unchanged from n006** (full text in the node metadata):
`tradeoff_area_glob_coarseness`, `tradeoff_autonomous_confirmation_weak`,
`tradeoff_axis_declaration_burden`, `tradeoff_axis_projection_coarseness`,
`tradeoff_batch_misreport_risk`, `tradeoff_broad_scope_coarseness`,
`tradeoff_cell_table_size`, `tradeoff_compiled_component_cost`,
`tradeoff_engine_speed_enables_per_task_use`, `tradeoff_engine_version_skew`,
`tradeoff_evidence_requires_reachable_history`, `tradeoff_flaky_pass_anchors`,
`tradeoff_home_migration_window`, `tradeoff_intersection_can_underselect`,
`tradeoff_member_annotation_drift`, `tradeoff_noarch_packages_preserved`,
`tradeoff_real_scheduler`, `tradeoff_registry_directory_complexity` (two more
generated files and one ledger, under the same root and merge rule),
`tradeoff_resource_declaration_completeness`, `tradeoff_setup_network_fetch`,
`tradeoff_split_home_rejected`, `tradeoff_static_scanner_overselection`,
`tradeoff_strict_version_handshake`, `tradeoff_two_toolchains`,
`tradeoff_two_user_roots`, `tradeoff_whole_run_filter_soundness`.

**Merged (both parents modified them):**

- **`tradeoff_computed_vs_prose`** — *Advantage.* Selection is computed,
  explained and scored (n006); so is the run surface: `--howto` is generated,
  the instructions section is identical everywhere, and a 200-line testing
  chapter becomes ten declared `notes:` lines plus `docs:` pointers reached
  through one verb; thinking_app's "shared component → full gate" rule is an
  axis join, a fan-out and an `ESCALATE:` line.
- **`tradeoff_fail_closed_bootstrap_cost`** — *Disadvantage, narrowed.* The
  bootstrap order becomes one aitask per level that the skill creates and
  runs; `detect` and `seed` are read-only until `--write` / `--apply`; level 0
  writes only registry files and seeds; the level-0 task's own `tests_pass` is
  the first anchoring full run; `bootstrap_until` is set to +90 days by level
  0; the seeder replaces most of the hand waiver pass (88 % / 80 % of aitasks
  tests seed at least one edge); `readiness` prints `LEVEL` / `NEXT`. What
  remains: a repository is level 0 (bound, closure- and seed-selected,
  unstamped) until a human adopts level 1; headless profiles stop there plus
  language-rule origins; and the judgement in classify and adopt, which no
  seeder can take.
- **`tradeoff_attribution_risk`** — *Risk, narrowed twice.* `STALE` on the
  next task and the stale mark on every selection (n006); the Step-7
  `UNMAPPED_SOURCE:` report at the moment a source is introduced, with
  annotate / propose / waiver offered right there (n007); the automatic score
  within one task wherever completion runs the full suite (n008). What still
  escapes is a coupling to a source that already has some edge, which only
  `score` can find.
- **`tradeoff_stamp_churn`** — *Disadvantage.* `EVIDENCED` needs no rewrite,
  `--confirm-source` is one commit, member blocks keep a screen's stamps in one
  file, variants carry no stamp (n006); onboarding adds the largest rewrite of
  all — level 1 on aitasks touches ~720 test files with one to eight comment
  lines each — mitigated by seeds selecting without any rewrite, `--scope
  <glob>` per area across tasks, per-class and per-area batch commits that add
  comment lines only (`git blame -w` and every runner ignore them),
  `ADOPT_REFUSED:dirty-foreign`, the reviewed `(t<id>)` commit, and the
  in-gate path that adopts a file's seeds only when a task already has it open.
- **`tradeoff_engine_absent_on_host`** — *Risk.* `ENGINE_MISSING` names the
  path and repair verb; the fallbacks; declared gates exit 3, never skip
  (n006). Two deliberate exceptions: the advisory Step-7 run prints
  `VERDICT:skip REASON:testmap_absent` so task-workflow, pickrem and pickweb
  continue (n007), and a project may choose `completion.engine_absent:
  fallback_command` for the Web lane (n008) — both printed, never silent.

**From n007, carried (with the resolution edits):**

- **`tradeoff_seed_noise`** — heuristic seeds are wrong in both directions;
  mitigated by seeds selecting and never claiming, confidence ordering review
  rather than gating it, the 0.60 co-change cap and `min_cochange 2`, direct
  imports only, evidence beside every row, rejection memory, and the suite
  budget for a repo where over-selection is expensive; reviewer fatigue on a
  1,000-row queue is spread by class acceptance, per-area batches and the
  in-gate path.
- **`tradeoff_two_edge_states_during_adoption`** — now *three* provenances
  (seeded, adopted, reviewed) a reader must keep apart; mitigated by the origin
  or `adopted(...)` on every row, `SEEDED:` / `ADOPTED:` on `check` and `stale
  --all`, `onboard status` as the one place the ratios live, and the rule that
  no seed ever changes a freshness verdict; `--strict` cannot be enabled while
  `UNMAPPED_SOURCE` rows are only seed-covered, which is visible rather than
  silent.
- **`tradeoff_generated_brief_limits`** — a computed brief cannot hold a
  project's judgement calls; `docs:` and `notes:` carry them one hop away; the
  full completion gate backstops a misread note.
- **`tradeoff_workflow_surface_growth`** — one procedure file, one profile key,
  one dispatcher verb, one skill-invoked script with a second mode (five
  allowlist touchpoints), a Step-7 render across every profile × agent golden,
  two QA edits, a seed edit and a profile-aware skill with two wrappers;
  mitigated by uniform degradation to a printed skip, the reused `VERDICT:`
  contract, and `aitask_skill_verify.sh` plus the goldens; smaller than n007's
  by one script.
- **`tradeoff_accept_rewrites_history`** — adoption inserts comment lines into
  hundreds of test files (blame noise, header conflicts); mitigated by fixed
  insertion positions, batch commits named for what they are, the in-task
  incremental path and `REWRITE_CONFLICT`; a project may keep seeds unadopted
  and live with selection-only enforcement, reported as such.
- **`tradeoff_onboarding_partial_coverage`** — what no origin reaches stays
  `UNMAPPED_SOURCE` or area-only; mitigated by rules and expiring waivers, the
  Step-7 prompt, opt-in coverage, and the full gate as the completion criterion.

**From n008, carried (with the resolution edits):**

- **`tradeoff_one_gate_not_two`** — *Advantage:* one completion gate whose
  behaviour is a committed policy; one command; the legacy Step-9 path and
  `aitask-qa` reach the selective lane through `test_command`; the flip is one
  line after readiness. *Disadvantage:* a ledger `tests_pass: pass` no longer
  says by itself whether the whole suite ran — mitigated by
  `result="MODE:<full|selected>|<n>|policy:<mode>"` on the gate-run block,
  `POLICY_DEMOTED` being loud, `readiness` printing what `--gate` would run, and
  the `gate-` run-id prefix in the ledger.
- **`tradeoff_seed_precision`** — *Risk:* an adopted `covers` edge says the
  test *executes* the source, not that it *verifies* it; narrowed by the
  `adopted.yaml` provenance shown in `stale` / `explain`, `ADOPTED_UNREVIEWED`
  in `readiness`, the over-claim direction only over-selecting, the 0.85
  threshold with co-change unable to reach it, three-sample display per class,
  and the seeded state existing at all — a project that wants no machine
  claims stops at seeds; a coupling the closure does not contain is still
  caught only by a full run's score.
- **`tradeoff_fallback_runs_more`** — with the engine absent and
  `engine_absent: fallback_command`, completion runs the pre-onboarding suite
  command — never less than before, never selective; default `error`;
  `MODE:fallback` visible.
- **`tradeoff_verify_build_wired_suites`** — a suite wired as `verify_build`
  (thinking_backend, half lint) cannot be moved mechanically; the skill asks,
  defaults to keeping it, records the answer; headless keeps.
- **`tradeoff_dispatcher_verb_added`** — `ait test` beside `ait testmap`;
  justified by the human-would-type-it rule and the seed's need for one verb;
  kept thin; `ait testmap` remains the maintainer surface; `--howto` documents
  `ait test` as the stable one.
- **`tradeoff_bulk_confirmation_granularity`** — per-class acceptance trades
  review depth for feasibility; mitigated by samples, `review a sample`,
  `--accept-min`, `--scope`, the `adopted.yaml` provenance so nothing pretends
  to be reviewed, the per-row path for anyone who wants depth, and individual
  confirmation of kind changes.
<!-- /section: tradeoffs -->

<!-- section: conflict_resolutions [dimensions: component_*, assumption_*, tradeoff_*] -->
## Conflict Resolutions

Strategy labels follow the synthesizer's priority order: **bridge** (a
component or mode that lets both sides stand), **assumption update** (one
side's premise changed, stated), **replacement** (one side's component
dropped for another's), **carried** (resolved in n003/n006 between n001 and
n002; recorded so no first-round dimension is silently dropped).

1. **Seeded queue (n007) vs. stamped adopted edges (n008) — bridge.** Both
   states exist: `seeded.yaml` is the select-only queue, `adopted.yaml` the
   provenance of class-accepted stamped edges, a per-row acceptance is a
   reviewed claim with no provenance row. Introduced as the *adoption ledger*
   bridging component; `check` / `stale --all` / `readiness` report all three
   counts. n007's `assumption_seeds_select_never_evidence` now speaks of
   *seeds*; n008's `tradeoff_seed_precision` now has a state below it.
2. **Autonomous acceptance — assumption update.** n008 let headless profiles
   adopt static-only edges at 0.95; n007 allowed no autonomous acceptance.
   Resolved by the number that separates a language rule from a heuristic:
   headless profiles seed everything and adopt only origins at confidence
   1.0 (`static:package`). The `adopted.yaml` provenance keeps even that
   distinguishable. This also answers n007 OQ2 and n008 OQ1.
3. **Two confidence tables — bridge.** One origin vocabulary
   (`static:{package,invocation,import}`, `coverage`, `observed`,
   `convention`, `plan`, `prose`, `cochange`); n008's co-change cap (0.60,
   corroboration only) replaces n007's 0.5–0.8 ladder because the measured
   group shape (1.14 commits per group, few-to-few pairing) cannot say which
   test covers which script; n007's `coverage` and `observed` origins have no
   n008 counterpart and are kept; convention takes n007's 0.60 (the weakest
   positive signal, 16–19 % coverage, homonym risk); n008's 0.85 class
   threshold applies to `--class` only. `assumption_seed_sources_measured` and
   `assumption_cochange_is_corroboration` both hold under the merged table.
4. **Phase ledger (n007) vs. graded levels (n008) — bridge.** Levels describe
   the registry, phases describe a run; `onboard.yaml` records both (`level:`
   plus phase rows); `readiness` derives `LEVEL` from the tree, `onboard
   status` prints `ONBOARD_NEXT` from the ledger. One aitask per level (n008
   OQ7) with n007's per-phase commits and re-entry inside each.
5. **First full run: `full_run` phase (n007) vs. the task's `tests_pass`
   (n008) — replacement.** They are the same run; it lands as the level-0
   task's Step-9 gate so it is in the gate ledger, and n007's `costs --update`
   and anchoring happen inside it. `full-run.md` remains as the phase
   procedure that reads its results and writes the timeout.
6. **`bootstrap_until` +30 at enable (n007) vs. +90 at level 0 (n008) —
   assumption update.** +90 at level 0: level 0 is unstamped by design and a
   1,000-seed queue is not adopted in 30 days; `finish` may shorten it.
7. **Skill static/attended-only (n007) vs. profile-aware (n008) —
   replacement.** Profile-aware, because the merged design has a defined
   headless behaviour (resolution 2); the phase procedure files (n007) live
   under the profile-aware skill.
8. **Engine `test` composite (n007) vs. `aitask_test.sh` front (n008) —
   bridge.** Both layers, split by what must run without an engine: the front
   resolves mode / task / intake / policy and owns the `test_command` and
   `fallback_command` fallbacks; the composite is the pipeline. n007's `--mode
   show` becomes `--explain`; n007's `ait test brief` becomes `--howto`
   backed by the engine `brief` verb; n007's `ait test explain <path>` is
   dropped in favour of `ait testmap explain`.
9. **`aitask_affected_tests.sh` (n007) vs. no helper (n008) — bridge.** The
   helper's `VERDICT:/REASON:` contract and its degrade-to-skip rule become
   `ait test --advisory`, a mode of the one front; the second script is not
   written; `tests/test_affected_tests_helper.sh`'s cases fold into
   `tests/test_ait_test_entrypoint.sh`. `assumption_helper_degrades_when_absent`
   is restated for the mode.
10. **Step 7: procedure file + profile key (n007) vs. one paragraph (n008) —
    bridge.** The loop is n008's paragraph; the pre-review run before Step 8
    is n007's procedure, kept because it writes the prediction record the
    completion run scores — without it `readiness` cannot accumulate
    `min_scored_full_runs`. The profile key governs only that run.
    `requirements_workflow_seam_is_data` (n008) now reads "data plus one
    procedure"; `requirements_workflow_seam` (n007) drops the in-loop call.
11. **Three gates with `testmap_run` (n001 → n006 → n007) vs. one completion
    gate under policy (n008) — replacement.** `testmap_run` is retired; every
    property it had is placed (verifier logic → `ait test --gate`;
    `blocks_dependents` and `max_retries: 1` → `tests_pass`; timeout → the
    ledger-derived `tests_pass.timeout_seconds`; exit mapping → the shared
    lib's rows; `--include-stale` → the composite; unlock → `testmap_check`
    unlocks `tests_pass`). n001's `requirements_gate_enforcement` ("a
    selection gate and a check gate") is satisfied: the selection gate *is*
    `tests_pass` under `completion.mode: selected`. n007's enable phase keeps
    its role — it writes `tests_pass`, `testmap_check` and `testmap_fresh`
    into the profile.
12. **`UNMAPPED_SOURCE` (n007) and `UNANNOTATED_TEST` (n008) — bridge.** Both
    printed by `ait test`; both answered by the Step-7 paragraph and the
    pre-review procedure.
13. **Two `## Running Tests` texts — bridge.** One fourteen-line section
    carrying n008's rule and exit table and n007's `UNMAPPED_SOURCE` and
    not-onboarded lines; `--howto` is the flag, `brief` the engine verb.
    Pinned by extending `tests/test_agent_instructions.sh` (n008's T40)
    rather than a new test file, through a real `install.sh --dir` (n007).
14. **Task resolution — replacement.** n008's resolution order replaces n007's
    explicit-only `--task`; the advisory form still passes the id.
15. **`aitask-qa` verb form — bridge.** n007's `explain --sources <paths>
    --format table` (one call for the whole change set) with n008's 4a–4d
    edits; seeded rows are `Covered (seeded)` (n007 OQ5, taken as yes).
16. **Annotation placement — assumption update.** n008's comment-only rule
    (never into a docstring, because it changes `__doc__`) replaces n007's
    "appended to the module docstring"; n007's member-block placement and
    Go's package-clause position are added. `assumption_annotation_is_comment_only`
    holds.
17. **`verify_build`-wired suites — replacement.** n008's ask-and-keep replaces
    n007's detect proposal to move the command; the lint half decides it.
18. **Verb naming — bridge.** n007's `seed` and `onboard {detect, inventory,
    status, accept, reject, finish}` and n008's `detect | suggest | adopt |
    howto` become one family: `onboard detect | inventory | seed | classify |
    adopt | reject | scaffold | status | finish` plus `brief`; `suggest` is
    `onboard seed` (its `--json --out` dump kept), `accept` is `onboard adopt`
    (with `--class` for n008's bulk form), `runner scaffold` is `onboard
    scaffold --runner`.
19. **First-round positions resolved upstream — carried.** n001's `testmap:verified
    <sha>` stamp, `git log` anchor walk and `STALE_RUN` / `UNVERIFIED` classes
    → n002's `@<date>/<blob10>` digest with n003's evidence join and `STALE` /
    `EVIDENCED` / `UNSTAMPED`; n001's `suites/` directory → n002's
    `_scoped.yaml`; n001's `go/` + `make install-dev` + `AIT_TESTMAP_DEV=1` →
    n002's `engine/` + `ait engine build` + `AIT_ENGINE=dev`; n001's bash
    reference runners → n002's builtins with shadow-by-name; n001's
    `~/.aitask/bin/` → n002's versioned engine directory under n005's
    `$AITASKS_HOME`; n001's `concurrency: report|execute` → n002's `--serial`
    knob → n006's `serial|parallel`; n001's `max_covers_per_test` /
    `require_anchor` → n002's `unit_covers_max` / `require_stamp`; n002's
    cobra and gofrs/flock → n006's stdlib `flag` and `syscall.Flock`; n001's
    `go-check` PR job → n006's `engine-check.yml`; n002's `testmap_select` /
    `testmap_current` names → n003's `testmap_check` / `testmap_fresh`. Every
    dimension of n001 and n002 is present in the metadata with the n006 text;
    the two references specific to dropped n002 choices (cobra, gofrs/flock)
    are removed from `reference_files`.
<!-- /section: conflict_resolutions -->

<!-- section: open_questions -->
## Open Questions

1. Should `affected_tests` default to `run` or `show` when a repository's
   affected run is expensive (thinking_app: one Gradle boot under the
   heavy-run lock, ~40 s minimum)? Proposed: `run`, because the scheduler
   defers on a refused slot and the estimate is printed first; a project may
   set `show` in its profile.
2. Should `onboard adopt --class` be permitted for `static:invocation` (0.90)
   under an attended profile without the ten-sample review, given the measured
   398/400 precision on aitasks? Proposed: no — the sample costs a minute and
   is what makes the class-level yes defensible.
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
    review claims (the n005 rule), and `ADOPTED_UNREVIEWED` is meant to be
    read.
11. Baseline questions still open (n006 §Open Questions 1–8, 10–11)
    unchanged; n006's question 9 (aitasks_mobile axis) is answered by both
    parents identically: no axis, source sets are runner/kind distinctions.
<!-- /section: open_questions -->