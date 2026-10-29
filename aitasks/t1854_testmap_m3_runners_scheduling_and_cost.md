---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [testing, testmap, go_engine]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
children_to_implement: [t1854_3, t1854_10, t1854_11, t1854_13, t1854_14]
anchor: 1852
created_at: 2026-09-22 09:19
updated_at: 2026-10-27 09:02
---

## Goal

Part of the **testing engine / test map** feature — ten parent tasks, one per
module of the proposal. This is **M3 — Runners, scheduling and cost**:
everything that executes a test and records what it cost.

This module delivers the runner contract every builtin and project script
implements (`describe` / `list` / `run --manifest`, `results.jsonl`, the exit
contract `0/1/2/75/64`), the reference runners for every target repository
(`bash-file`, `pytest`, `go-test`, `gradle-class`, `suite`, `device`,
`engine-test`), the scheduler over declared host resources with `flock(2)`
slot files and exit-75 deferral, and the cost ledger keyed by `(id, host
class)` that anchors `last_pass` evidence and stores predictions and the
policy file.

This task carries the module's cut — submodules, owned files, the interfaces
it provides and consumes, the seams later modules land into it — and the
planning protocol. It does **not** restate the specification.

**Proposal (authoritative for every detail):**
`aidocs/testing_engine/n014_explorer_006_proposal.md` — start at the *Module
Map* entry `#### M3 — Runners, scheduling and cost`, then the *Components*
subsections tagged `(M3.x)` (listed under *Reading list* below), then the
narrative sections those components name. *Architecture*, *Design decisions*
and the *Invariants every module honours* apply to every module.

**Acceptance:** the union of the module's components' test lists (*Module Map —
How to read it*).

## Submodules (one child task each — settled at the coarse planning pass)

| submodule | scope | depends on | wave |
|---|---|---|---|
| **M3.1** Runner contract and repository | `describe` / `list` / `run --manifest` (with the allocator-handle field), `runners.yaml` bindings, the `builtin:` scheme, `command:` / `cwd:` overrides, shadow-by-name, **the canonical grouping function** `(runner, group_by group, resource set, wave class, batch identity)` (`batch: no` units are singletons; the wave class is the caller's input), per-unit timeouts, `results.jsonl` (top-level / child rows) / `runner.json`, reconciliation as mechanism failures, the engine's per-invocation record (`cause`, HEAD at start and end, the modified-path set), the exit contract `0/1/2/75/64`, `subsumed_by:`, `fallback_command:`, `full: true` + `children:`; the runner-backed unit lister for `scan` / `check` (named extension of M2.1); `batch` / `needs` into the registry (named extension of M2.2); the `run` verb over a plan-executor seam (built-in serial plan refusing a non-empty resource set until M3.3) with an ordered multi-subscriber post-run hook. `axis:` / `token_format:` are M2.4's extension. Owns `internal/runner` (contract, repository, the `run` verb) | M1.2, M2.1, M2.2 | B |
| **M3.2** Reference runners | **Re-decomposed 2026-10-21 into M3.2a–k (t1854_2, t1854_5 – t1854_14): see *M3.2 re-decomposition (2026-10-21)* below.** Original scope: `bash-file`, `pytest` (junitxml, `testmap:batch no`), `go-test`, `gradle-class`, `suite`, `device` (reads the manifest's allocator handle), `engine-test`; the `full` suite wrapper's `children:` post-processors (pytest junitxml, bash-file per-file exit, `go test -json`). Owns `internal/runner/builtin/*`, `ait-testmap runner <name>`. (No `list --invocations` — the seeder reads M2.3's facts directly; the serial carve-out drift-test pin is M10.1's.) | M3.1 | B |
| **M3.3** Scheduler and resources | resource kinds and scopes, `resources.yaml`, `flock(2)` slot files, admission with 75 deferral and backoff, the allocator with signal-safe release (filling the manifest's handle field), `errgroup` execution of the invocations M3.1's grouping function forms (never re-formed), the kind → wave class mapping from M2.5, `broad_after_unit` waves as an ordering over wave-homogeneous invocations, admission-holding invocations last, `concurrency: serial\|parallel`, the schedule report and its check half `schedule --check`; plugs the scheduler into M3.1's `run` (named extension). Owns `internal/sched`, verb `schedule` | M3.1, M2.5 | C |
| **M3.4** Cost ledger | Welford / P² per `(id, host class)`, `.aitask-testmap/ledger.jsonl` as a subscriber of M3.1's post-run hook, anchor eligibility at run time (no cause, HEAD unmoved, modified paths disjoint from the test, its test-side closure, `covers` sources, the closure's `reads` globs and the runner configuration; empty for an opaque closure), `costs --update`, `last_pass` from eligible passes only, flake rate, the per-group estimate over top-level ids (disjoint accounting) and the full-suite p95, `costs/predictions.yaml` (store only), `costs --gate-timeout` (`GATE_TIMEOUT_SUGGESTED:` homed here), the run-id prefixes, the `costs/policy.yaml` file format (read/write helpers only). Owns `internal/cost`, verb `costs` | M3.1, M2.3, M2.5 | C |

## Cross-module seams

**Provides** (defined here, consumed elsewhere):

- The runner contract and `results.jsonl` — M3.1 → M3.2 (builtins), M3.3
  (execution), M3.4 (ledger rows), M6.1 (`detect` writes `runners.yaml`).
- Runners for every target repository without a project script — M3.2 → M4.5,
  M6.2, M8.4 (`fallback_command`), M10.4 (`gradle-class`, `device`), M10.5.
- `resources.yaml` and the wave plan `run` executes; exit 75 semantics — M3.3 →
  M4.5, M6.1 (`RESOURCE_HINT` → entries), M6.4 (`needs:` bindings).
- Cost rows, `last_pass`, the per-group estimate, `predictions.yaml`, the
  `costs/policy.yaml` format — M3.4 → M4.1 (ranking, budget), M4.3 (anchors),
  M4.4 (score, readiness), M6.5 (`--gate-timeout`), M8.5 (cadence state).

**Consumes:** M1.2 (the binary, the harnesses); the loaded registry (M2.1); the `batch` / `needs` annotations (M2.2); the dependency closure and plugin `reads` (M2.3, for M3.4's eligibility rule); the kind data and helpers' `testmap:reads` (M2.5, for M3.3 and M3.4).

**Hooks and extensions** (a file has one owner; a later submodule lands its
edit as the owner's named extension). The cut was corrected at the coarse
pass — proposal commit `6a3a81efc`; the rationale is the *Deviations* section
of `aiplans/p1854_testmap_m3_runners_scheduling_and_cost.md`:

- M3.1's `run` exposes a plan-executor seam; **M3.3** plugs the scheduler in
  and fills the manifest's allocator-handle field.
- M3.1's `run` exposes an ordered multi-subscriber post-run hook; **M3.4**
  subscribes (the ledger); **M4.4**'s `score` may.
- M3.1 owns the canonical grouping function; M3.3, M4.1 and M3.4's estimate
  call it with the same inputs; nobody re-forms an invocation.
- `axis:` / `token_format:` in `describe` are **M2.4**'s named extension.
- The `SCAFFOLD_TODO` recognition and its `check` report are **M6.4**'s named
  extension of M3.1's lister and M2.1's `check`.
- `costs/predictions.yaml` is a store here; **M4.4**'s `score` writes it.
- `costs/policy.yaml`: the format and its read/write helpers are M3.4's; the
  writer logic (`POLICY_WRITE:`, `approved_by: engine:readiness@<run>`) is
  **M8.5**'s.
- `component_broad_test_scopes` is split: the registry / staleness half is
  **M2.5**, the scheduling half is M3.3.
- The `pytest` runner honours `testmap:batch no`; the aitasks carve-out
  annotations and the agreement check in
  `tests/test_serial_carveout_doc_drift.sh` are **M10.1**'s.
- Invariant 1 (the loop can only fail toward running more) and invariant 4
  (the engine never launches a code agent) bind the runner and the scheduler.

**Automation-first (user directive, 2026-10-11).** No M3 verb makes a human
action a precondition of any path: `concurrency`, `--serial` / `--parallel`,
`resources.yaml` and `costs --gate-timeout` are values and computed
suggestions, the schedule report and `schedule --check` are informational,
and M3 encodes no "awaiting a person" state. The two human-flavoured steps
next to M3 (trusting `concurrency` after reviewing the schedule report;
confirming `runners.yaml` per runner) belong to onboarding (M6).

## Reading list in the proposal

- *Module Map* — `#### M3`, *How to read it*, *Cross-module interfaces*,
  *Suggested implementation order* (waves B, C).
- *Components* — *Runner contract and repository (M3.1)*, *Reference runners
  (M3.2)*, *Scheduler and resources (M3.3)*, *Broad-test scheduling and
  staleness policy (M3.3 scheduling half)*, *Cost ledger (M3.4)*.
- *Architecture* — *Process map*, *Where state lives*, *Line-protocol index*.
- *Running Tests*; *The Run Surface — Output and exit contract*.
- *Assumptions* — *Variants, broad tests and runners (M2, M3)*; *Tradeoffs* —
  *Map and registry structure (M2, M3)*; *Open questions*.
- Framework rules that apply: `aidocs/framework/tmux_gateway.md` if any
  runner or resource touches tmux; the serial carve-out contract in
  `CLAUDE.md` (Testing).

## Planning and implementation protocol (binding for this task and every child)

This feature spans **ten parent tasks**, one per module of the proposal (see the
module → task map at the end). The modules are cut by ownership of files, verbs
and line protocols, not by Go package or by script, so children of different
parents touch the same packages and scripts and meet on the interfaces listed
above. Two consequences are binding.

### 1. Coarse planning pass — all ten modules, before any submodule is implemented

- Plan this task through the normal workflow (`/aitask-pick` → planning). In the
  Complexity Assessment choose **"Yes, create child tasks"** and decompose into
  **one child task per submodule row** in the table above (keep the `M<n>.<m>`
  id in the child name); let the workflow write the child plan files; at the
  child-task checkpoint choose **"Stop here"** so nothing is implemented. Do the
  same for the other nine parents, in wave order (A → I), **before implementing
  any child of any parent**.
- Keep the coarse plan coarse. A child's plan records what the proposal fixes for
  that submodule — scope, owned files, provided and consumed interfaces, the
  component test lists that are its acceptance — and its wave. It does **not**
  design internals against providers that do not exist yet; that is the reality
  check's job (§2 below), and the child plan must say so in as many words.
- Express cross-module order in task data, not in prose. Each child's `depends:`
  names the child ids of the other parents it consumes, in the `t<parent>_<m>`
  form (for example `depends: [t<M2 parent>_1]`), taken from the "depends on"
  column above. When the provider parent has not been planned yet, the child body
  records the `M<n>.<m>` reference and the dependency is filled with
  `./.aitask-scripts/aitask_update.sh --batch <child-id> --deps ...` as soon as
  the provider's children exist. After all ten parents are planned, one
  cross-linking pass checks every "depends on" cell against a real `depends:`
  entry, and checks the module → task map below against the parents' real ids.
- Parent-level `depends:` stays empty on purpose: module-level dependencies form
  a cycle (M6.5 → M8.2 / M8.4, M8.3 → M7.1 / M7.2, M7.1 → M6.2) and would block
  wrongly; the real graph is acyclic only at submodule granularity.
- Deviations from the proposal found while planning go into a **"Deviations from
  the proposal"** section of the plan. A wrong cut — a file two submodules must
  own, a dependency the wave table contradicts — is fixed **in the proposal**, not
  patched in a plan; that is the proposal's own falsifier
  (`assumption_modules_map_to_parent_tasks`). Send a note (`/aitask-note`) to
  every parent whose tables the change touches.

### 2. Reality check at child implementation time — a mandatory step in every child's plan

The coarse plan is a hypothesis written before its providers existed. **Every
child task's plan MUST carry an explicit "Reality check" step, executed before
any code is written, and its outcome MUST be recorded in the child's plan
file.** The step:

1. Re-reads the proposal's Module Map row for this submodule, its component
   subsections, and the row of every interface it consumes (the *Cross-module
   interfaces* table).
2. Inspects the **actual current state** of every provider it consumes — the
   verbs, line protocols, files, hooks and tests as they exist on the merge
   target now — and names the task and commit that landed each one. The
   proposal's description of a provider and the coarse plan's description of it
   are both claims to be verified, never facts to be assumed.
3. Tabulates every difference in three columns: *proposal says* / *coarse plan
   says* / *repository has*.
4. Decides, per difference: adapt this child to reality; or revise this child's
   coarse plan; or revise the proposal (cut errors and interface changes go
   there, per §1). Records the decision and its reason.
5. Sends a note (`/aitask-note`) to every downstream child whose assumptions a
   difference or a decision breaks, hedging what cannot be proven from the tree.
6. Re-confirms that every file this child will touch is owned by this submodule,
   or that the edit lands as the owner's named extension (the "one owning
   submodule" rule in *Module Map — How to read it*).

A child whose plan lacks this step, or whose step is not recorded as executed,
is not implementing this task as specified.

## Module → task map

| module | parent task |
|---|---|
| M1 — Engine foundation and distribution | t1852 |
| M2 — Registry and map model | t1853 |
| M3 — Runners, scheduling and cost | t1854 |
| M4 — Selection, freshness and feedback | t1855 |
| M5 — Run surface | t1856 |
| M6 — Onboarding | t1857 |
| M7 — Agent review and author annotation | t1858 |
| M8 — Completion policy and gates | t1859 |
| M9 — Workflow integration, skills and documentation | t1860 |
| M10 — Rollout to the target repositories | t1861 |

All ten share the topic anchor of the M1 task, so the board's By-Topic view
shows the whole feature as one lane.

## M3.2 re-decomposition (2026-10-21)

M3.2 ("Reference runners") was **re-decomposed around trustworthy test
evidence**, at the user's direction, during the t1854_2 planning session. The
single seven-builtin child was rejected: it inferred per-test results through
injected `BASH_ENV` traps and pytest plugins, listed tests by source scan,
verified Gradle / device against fakes only, guarded hangs with a panic timer,
and refused recursion lexically. The M3.2 Submodules row above now resolves to
the eleven siblings below. Every child body carries the full guarantee table
(G1–G10, incl. G1a / G1b / G8a), the carried reality-check facts and its
acceptance criteria.

### Guarantees (summary — the full table is in every M3.2 child body)

- **G1 / G1a / G1b.** "The command succeeded" is never "every test was accounted for". The accounting classes are `cases | unit | aggregate`. Case reconciliation is identity-based and owned by the engine: each expected identity has exactly one terminal result, and a duplicate, unexpected or missing identity is an error whatever the totals. The engine derives statuses and counters.
- **G2 / G3 / G4.** Missing, ambiguous, stale or incomplete evidence is never a pass and never an unexplained skip. Zero tests is an explicit policy (`zero_tests: error|skip`, default `error`). A skip comes only from the tool's own verdicts.
- **G5 / G6.** Discovery is declared (`native | inventory | candidates`) and kept separate from execution. Native discovery shares the execution configuration and is bounded. Reports are read only from a fresh per-invocation directory.
- **G7.** Child rows come only through a registered reporting contract (t1854_14), through the same shared reconciler. Until then `children:` is refused.
- **G8 / G8a** (revised 2026-10-24 in t1854_6: the dedicated-supervisor design). Every contained process start runs under a per-start supervisor (`ait-testmap __supervise`), a subreaper of its own subtree only, which a descendant cannot leave by `setsid()`. Its cleanup ends only at `wait4` ECHILD, a kernel proof that the subtree is empty. Per-invocation cleanup ownership survives the death of every process that runs test code (runner, builtin, tool). The supervisor's own death is a stated residual: its subtree may be left running; the death is recorded `cleanup_unverified` and halts all further work in the process. Invocations may overlap on every Linux host (`Overlappable()`). On a platform without containment (darwin), production adapters refuse and invocations run serially. cgroup v2 hardening is a deferred follow-up.
- **G9.** Runtime recursion refusal for the same repository, in `Run` and `Load`, including `env -i`. Calls against fixture repositories are allowed. It is a prerequisite of every adapter.
- **G10.** An adapter is "supported" only for what real-tool integration tests cover. Otherwise it is pending.

### Siblings (dependency order)

| id | scope | depends | wave |
|---|---|---|---|
| t1854_2 (rescoped) | M3.2a evidence contract: G1–G7, G10 in the runner contract; the shared reconciler; no runner enabled | t1854_1, t1985 | 1 |
| t1854_5 | M3.2b shared hang watchdog (refactor of t1985 / t1998) | — | 1 |
| t1854_7 | M3.2d recursion guard (G9) | — | 1 |
| t1854_6 | M3.2c supervised execution foundation (G8 / G8a), the `runner <name>` verb, the scaffold, no production adapter | t1854_2, t1854_5, t1854_7 | 2 |
| t1854_8 | M3.2e `bash-file` (`unit`, `inventory`) | t1854_6 | 3 |
| t1854_9 | M3.2f `pytest` (`cases`, `native`) | t1854_6 | 3 |
| t1854_10 | M3.2g `go-test` + `engine-test` (`cases`, `native`) | t1854_6 | 3 |
| t1854_11 | M3.2h `gradle-class` (`cases`, native via `--test-dry-run` if Step 0 confirms; pending without a real Gradle environment) | t1854_6 | 3 |
| t1854_12 | M3.2i `suite` aggregate (no children) | t1854_6, t1854_7 | 3 |
| t1854_13 | M3.2j `device` — **Postponed** (no emulator environment; needs M3.3's allocator) | t1854_11, t1854_3 | 4 |
| t1854_14 | M3.2k suite reporting contract (explicit reports, verified attribution) | t1854_12, t1854_8, t1854_9, t1854_10 | 4 |

Also re-pointed:

- t1854_3 (M3.3) now depends on t1854_6: parallel invocations need overlappable boundaries.
- t1859_4 (M8.4) depends on t1854_12 + t1854_7, where it used to depend on t1854_2.
- t2082 depends on t1854_8 / t1854_9 / t1854_10 / t1854_11.

### Deferred (standalone, anchor 1852 — tracked, not v1)

- **t2117** `testmap_auto_bash_exit_integration` — Postponed, depends t1854_14.
- **t2118** `testmap_auto_pytest_report_integration` — Postponed, depends t1854_14.
- **t2119** `testmap_pidns_invocation_boundary` — Ready, depends t1854_6, t1854_7. (Since t1854_6's dedicated supervisor, invocations no longer run serially without a delegated cgroup; see t1854_6's note on t2119.)

### Closure rule

M3 closes only when every M3.2 sibling above is archived. The Postponed device
adapter (t1854_13) therefore keeps M3 open until an emulator environment
exists; that is the honest state. t2117 / t2118 / t2119 do not hold M3 open.

### Requirement coverage audit (2026-10-21)

Each requirement of the original M3.2 scope, of the user's directive and of
the plan review is mapped to the task whose body owns it. Every row was
checked by grepping that body for its acceptance text. A dependency walk over
every edge above found no dangling id and no cycle.

| source | requirement | owner |
|---|---|---|
| original | `ait-testmap runner <name>` verb + builtin registration | t1854_6 |
| original | `bash-file` builtin | t1854_8 |
| original | `pytest` junitxml | t1854_9 |
| original | `testmap:batch no` honoured | t1854_9 |
| original | `go-test` per-file `-run`, `-json` | t1854_10 |
| original | `gradle-class` `--tests` batch, one invocation per `group_by` group | t1854_11 |
| original | JUnit XML inverted to ids through the list table | t1854_11 |
| original | zero-match trap (now: a listed case with no result is `error:incomplete`, never pass) | t1854_11 |
| original | `suite`: any command as one unit | t1854_12 |
| original | `device` reads the manifest handle, refuses without one | t1854_13 |
| original | `engine-test` over `goengines/` (lists its packages) | t1854_10 |
| original | `full` suite child rows (pytest junitxml, bash per-file exit, `go test -json`) | t1854_14 |
| original | recursion: a `full` suite reaching `./ait test` is refused | t1854_7 |
| original | `command:` / `cwd:` overrides | t1854_6 |
| original | each builtin declares and proves its timeout mode | t1854_8 |
| original | hang guard for builtin tests (t1985 / t1998 notes) | t1854_5 |
| original | what each runner reads (t2081 note → t2082) | t1854_9 |
| directive | guarantees defined first; what each result proves | t1854_2 |
| directive | command success ≠ all tests accounted for | t1854_2 |
| directive | missing / ambiguous / stale / incomplete never pass or unexplained skip | t1854_2 |
| directive | explicit zero-test policy | t1854_2 |
| directive | discovery separated from execution; native / inventory / candidates | t1854_2 |
| directive | native discovery bounded like execution | t1854_6 |
| directive | discovery and execution share configuration | t1854_9 |
| directive | arbitrary suites start aggregate only | t1854_12 |
| directive | automatic shell exit hooks deferred | t2117 |
| directive | injected pytest plugins deferred | t2118 |
| directive | individual results need a documented reporting contract and verified attribution | t1854_14 |
| directive | supervision complete before runners; watchdog reused | t1854_6 |
| directive | timeout / cancellation / crash / descendant cleanup specified and tested | t1854_6 |
| directive | runtime recursion protection, fixture repos allowed | t1854_7 |
| directive | recursion coordinated with owning tasks | t1854_7 |
| directive | real tools, versions, pending without an environment | t1854_11 |
| directive | deferred prerequisites block the feature (children:) | t1854_2 |
| review | identity-based case reconciliation, equal-count substitutions tested | t1854_2 |
| review | containment survives `setsid()` | t1854_6 |
| review | guard before every adapter; recursion from discovery and execution | t1854_7 |
| review | guard before every adapter (edge) | t1854_6 |
| review | per-invocation cleanup ownership surviving a builtin crash; overlap test | t1854_6 |
| review | t1854_3 coordination for parallel execution | t1854_6 |
| review | suite child evidence through the shared reconciler | t1854_14 |
| review | pidns deferred with forced-backend, `env -i` recursion and cleanup acceptance | t2119 |
| original | no `bash-file list --invocations` (Dev 5) | dropped, unchanged |
| original | serial carve-out drift pin | M10.1 (t1861), unchanged (Dev 6) |

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1852** id=2026-09-22T14:31:22Z.ecd6180d0e75396a6f96fae7 from=t1852 at=2026-09-22T14:31:22Z base=d0836b4f1750fde12e5e30260cd0d34396793a17 base_branch=main dirty=yes host=omg16
>
> | **Sequencing clarification (advisory, from the t1852 coarse pass, 2026-09-22).** The user asked that M1's children be *implemented* before M2 (t1853) is *planned*. Read the "plan all ten parents before implementing any child" paragraph in this task's body as an upper bound on how far planning may run ahead, not a requirement to plan against providers that do not exist. The rule is submodule-granular, never whole-parent (module-level deps form a cycle: M6.5 -> M8.2/M8.4, M8.3 -> M7.1/M7.2, M7.1 -> M6.2): start this parent's coarse pass once the specific provider submodules its wave-earliest children consume have landed in the tree, and implement its children in proposal wave order. A standalone cross-linking chore task (created from t1852's pass, followup_kind risk_mitigation) checks every "depends on" cell against real depends entries once all ten parents are decomposed; it accepts archived children as evidence and never rewrites M10.2-M10.5 (cross-repo).
> | 
> | **Go source layout (proposal fix, commit 07a546087 on main).** The engine source directory is `goengines/`, not `engine/`: one Go module (`github.com/beyondeye/aitasks/goengines`) for every distributable Go executable, `goengines/cmd/ait-testmap/`, shared packages `goengines/internal/{gitx,platform,lineproto}`, and every testmap-specific package under `goengines/internal/testmap/<pkg>`. Wherever the proposal (and this task's owns cells) write `internal/<pkg>`, read `goengines/internal/testmap/<pkg>`. Unchanged: the binary name `ait-testmap`, `$AITASKS_HOME/engine/v<V>/`, the `ait engine` verbs. CI workflow is `goengines-check.yml`; the release job is `goengines`. M1.2 (t1852_2) creates the module root; each later submodule adds only its own package and replaces only its own stub verb.

> **✉ note:t1852_2** id=2026-09-24T06:18:23Z.806d7ec4977018b28bdd2d48 from=t1852_2 from_verified=yes at=2026-09-24T06:18:23Z base=33012bff731972003d827cd6b152419d11ab9353 base_branch=main dirty=yes host=omg16
>
> | The M1.2 engine skeleton landed (t1852_2, commit 33012bff7). Your first engine children build on it; goengines/README.md ("Rules for engine submodules", "## Interfaces") is the reference:
> | - Verb table: cmd/ait-testmap/verbs.go registers every verb as stub("<verb>"). A submodule replaces only its own row with {Name, Run, Exits}; Exits is the verb's exit contract, and a code outside it becomes exit 3.
> | - Packages go under goengines/internal/testmap/<pkg>. Shared: internal/gitx (read-only git, BlobDigest, IsAncestor, LsTree), internal/platform (PoolCap 8, NewGroup, Lock, CacheRoot), internal/lineproto (Format/Line/Emit, exit codes).
> | - Registry contract: testmap.Contract = 1; testmap.CheckContract(path, data) returns *ContractMismatchError (Line() → CONTRACT_MISMATCH:<path>|<file>|<engine>, exit 3). contract: must be a non-negative int; merge keys and aliases are resolved.
> | - Cache: testmap.CacheDir() = ${XDG_CACHE_HOME:-$HOME/.cache}/aitasks/testmap.
> | - Fixtures: fixture.New(t, [SHA256()]) with Write/Remove/Commit(t, task, type, desc)/History/Run gives deterministic `(t<id>)` histories, isolated from the caller's git config. Add your own fixture constructors on top of Repo.
> | - Benchmarks: add BenchmarkX for each latency budget, record with `go run ./internal/tools/benchgate -baseline bench/baseline.txt -update`, and add budget=<d> where the proposal pins one. The full gate fails if a baseline benchmark disappears.
> | - Dependencies are allowlisted (yaml.v3, doublestar/v4, x/sync — doublestar is added by its first importer). Invariants 4-5 have a lexical tripwire in guards_test.go; a legitimate look-alike literal is exempted per line with `// invariant5-ok: <reason>`.

> **✉ note:t1853** id=2026-10-11T14:44:00Z.81faa743d19fd4b459a3bc75 from=t1853 at=2026-10-11T14:44:00Z base=3bc0de8ac7a9c9d1f60173e1257715a744efc451 base_branch=main dirty=yes host=omg16
>
> | Advisory, from the t1853 (M2) coarse pass. Proposal M2 cut fixed in commit 3bc0de8ac on main.
> | 
> | - **M3.1 gains a named extension:** the runner-backed unit lister that M2.1's `scan` / `check` call. M2.1 ships both verbs over an injected lister, tested with a fixture; M3.1 plugs the runner repository in. This was added to M3.1's Module Map row.
> | - **M2.4 now depends on M3.1** (`describe`'s `axis:` / `token_format:` land in M3.1's `describe` parse as M2.4's named extension). When you create your children, add the M3.1 child id to t1853_4's `depends:`, e.g. `./.aitask-scripts/aitask_update.sh --batch 1853_4 --deps "t1853_1,t1854_<m>"` (read the list first: --deps replaces it). t1853_4's body says "M3.1 (pending: t1854 not decomposed)".
> | 
> | **Automation-first (user directive, stated 2026-10-11 during the t1853 pass).** Human review belonged to an older design; the finalized test-map feature must run without a person wherever possible. At your coarse pass, treat any proposal step that makes a human action a precondition as a candidate to automate (record the decision in your plan; cut changes go into the proposal per protocol §1).

> **✉ note:t1853_1** id=2026-10-12T08:28:19Z.bb643c747c78eef51dac4376 from=t1853_1 from_verified=yes at=2026-10-12T08:28:19Z base=c07193265578ec723aa5994ca4bf20ed5116222e base_branch=main dirty=yes host=omg16
>
> | For M3.1 (not yet decomposed): M2.1 (registry core) landed in 0d04347ab; the proposal contract is at c07193265. Advisory, as of that tree; re-verify when M3.1 is planned.
> | 
> | The runner repository plugs into scan/check as registry.UnitLister (goengines/internal/testmap/registry/inputs.go):
> | - List(ctx, root) ([]Listing, error)
> | - Listing{Runner; Bound []string (test files the runner's bindings match: the UNREGISTERED candidates); ArtifactGlobs []string (describe's artifact_glob:); Units []ListedUnit{ID registry.ID, Kind, Lowering, Artifact}}
> | 
> | Wire it by setting Lister in testmapInputs() in goengines/cmd/ait-testmap/scancheck.go. Until then scan and check exit 3 with INPUT_UNAVAILABLE.
> | 
> | Ids must satisfy the id grammar (registry.ParseID: <path>[#<member>][@<variant>]). Invalid ids, invalid globs or a List error become INPUT_ERROR:lister|<detail>, exit 3.
> | 
> | How the fields are used:
> | - variant ids are persisted as variants: on their base unit in _scanned.yaml
> | - the Artifact column feeds UNMAPPED_ARTIFACT
> | - a listed unit of an exclude:d test path claims nothing

> **✉ note:t1853_3** id=2026-10-13T12:53:06Z.f007341165d9982df9324fe7 from=t1853_3 from_verified=yes at=2026-10-13T12:53:06Z base=2c04a9639cc377ce62858e5af12bbc3a0f76412b base_branch=main dirty=yes host=omg16
>
> | Advisory, from t1853_3 (M2.3 dependency scanners), as landed in 2c04a9639. Verify against the code.
> | 
> | For M3.2: `bash-file list --invocations` overlaps M2.3's bash facts. `deps.Scan(...).Static(path)` already yields `static:invocation` edges with anchor lines, and `Facts(path)` adds the closure-only ones. The bash scanner covers:
> | - `SCRIPT_DIR` / `PROJECT_DIR` bindings, where every binding of a variable counts
> | - `source` / `.`, exec and interpreter calls
> | - embedded `python3 -c` / heredoc imports
> | - suffix matching for non-literal words
> | 
> | Printing those facts rather than re-scanning would keep one bash resolver. That is a suggestion, not a requirement. No human-only step was needed in M2.3.

> **👁 note:read** id=2026-10-13T14:42:18Z.e459ab7e4339e7252aea8abd by=t1854 at=2026-10-13T14:42:18Z mode=explicit ids=2026-09-22T14:31:22Z.ecd6180d0e75396a6f96fae7,2026-09-24T06:18:23Z.806d7ec4977018b28bdd2d48,2026-10-11T14:44:00Z.81faa743d19fd4b459a3bc75,2026-10-12T08:28:19Z.bb643c747c78eef51dac4376,2026-10-13T12:53:06Z.f007341165d9982df9324fe7

> **✉ note:t15** id=2026-10-25T08:53:45Z.eeb12517a59945a2e10e57dd from=aitasks_go#t15 at=2026-10-25T08:53:45Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
>
> | Coordination notice from aitasks_go (t15 ship-path decision; schedule in trail
> | art:trail-go-ship-path owned by aitasks_go#t22). Advisory context, not an
> | instruction. It does not change this task's scope.
> | 
> | WHAT IS PLANNED
> | ait-testmap Go development (public goengines/) will move ONCE into the private
> | aitasks_go repository, at a cutover performed by aitasks_go#t22. After that,
> | goengines/ here receives exported snapshots only (no tests, bench or ci), and
> | engine work happens in aitasks_go. As of 2026-10-25 the cutover has no date.
> | Its prerequisites are aitasks_go t20 and t21 and aitasks t2138.
> | 
> | UNTIL THE CUTOVER: CONTINUE THIS TASK HERE, AS NORMAL
> | To keep the cutover cheap and safe:
> | 1. Land goengines/ changes on main promptly. Avoid long-lived branches,
> |    worktrees or unmerged PRs touching goengines/, because the cutover has to
> |    wait for, or hand off, every one of them.
> | 2. Keep engine commits (goengines/**) separate from framework-side commits
> |    (the aitask_testmap.sh shim, installer/setup, skills, docs, aitestmap/).
> |    Mixed tasks will be split along that line, and separate commits keep both
> |    the split and the history migration clean.
> | 3. If goengines tests start reading data from outside goengines/ (as with the
> |    t1954 corpus under aidocs/testing_engine/), record that path in this
> |    task's plan. The migration must copy it into the private module.
> | 4. Add no new Go binary or non-testmap package to goengines/. ait-monitord is
> |    being re-homed to aitasks_go (aitasks_go#t23), and ait-tui is developed
> |    there.
> | 5. Keep the contracts and guards as usual: the dependency allowlist, the
> |    Invariant 4-5 tripwire, the hang guard, bench baselines, and the
> |    version/verb/exit-code interface. The migration carries them over verbatim
> |    and checks that nothing changed.
> | 
> | FREEZE PROTOCOL
> | Shortly before the cutover, aitasks_go#t22 will send this task a
> | "goengines freeze in effect" note. From that note until a matching
> | "goengines freeze lifted" note, do not claim or start goengines work here. A
> | task that is Implementing or locked at that time is never relocated under its
> | agent: t22 waits for it to land, or arranges an explicit checkpointed handoff
> | (commit/push, handoff note, release the lock, back to Ready).
> | 
> | AFTER THE CUTOVER
> | If this task still has engine work pending, it is re-homed to aitasks_go
> | (engine-only) or split (the Go part there, the framework part here), and the
> | original carries a pointer. Framework-side work (the shim, installer, skills,
> | docs, aitestmap/ and the n014 spec) stays in this repository permanently. An
> | emergency public fix to goengines/ after the cutover needs a
> | `Return-To: aitasks_go` trailer plus a return task in aitasks_go
> | (`ait create --batch --project aitasks_go`).

> **✉ note:t2141** id=2026-10-26T09:55:37Z.b84fb3c9416123269a123637 from=t2141 from_verified=yes at=2026-10-26T09:55:37Z base=7f49dbd62e8c9ab5ae05de2935184d3bf72256d7 base_branch=main dirty=no host=omg16
>
> | Advisory context from t2141 (observing goengines-check after t2138). It doesn't change this task's scope.
> | 
> | As of runs 40187609686 (309e0b8c6), 40279191111 (6e315def2) and 40301069108 (a probe identical to 6e315def2), `Go engines check` → `check` → `go test ./...` fails on GitHub-hosted runners in `internal/procsup`. The cause is hangguard LEAK reports from TestHaltStartInterleavings (3/3 runs) and TestSupervisorDeathHalts (1/3), tests that t1854_6 landed in 60ca89154. They pass locally. Filed as t2148 (bug, high).
> | 
> | Consequence for pending children: until t2148 lands, any push touching goengines/ will show `check` red at `go test`, and every later step (cross-build, sums loop, guards) is skipped. A red `check` there is not by itself evidence of a regression in a child's change. Look for `LEAK:Test…` lines under `internal/procsup`. The run-time observations are moment-relative; re-check `gh run list --workflow goengines-check.yml` before relying on them.

> **✉ note:t22_3** id=2026-10-29T22:22:23Z.0d3a1e60df5f62a3e019937b from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:22:23Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.
