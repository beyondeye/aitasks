---
priority: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [testing, testmap, go_engine, install, ait_setup]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
artifacts:
  - handle: art:trail-testmap-feature
    kind: implementation_trail
    name: "Test map feature: module landing order"
created_at: 2026-09-22 09:19
updated_at: 2026-09-22 12:15
---

## Goal

Part of the **testing engine / test map** feature — ten parent tasks, one per
module of the proposal. This is **M1 — Engine foundation and distribution**:
the engine as a buildable, installable, resolvable binary, with nothing
project-specific in it yet.

The test map engine (`ait-testmap`) is a static Go binary installed per user
under `$AITASKS_HOME/engine/v<VERSION>/`. This module delivers the per-user
root and its resolver, the Go module skeleton with the verb table and the
test harnesses every later engine package builds on, the build / CI / release
path, the `ait testmap` shim and its strict handshake, the installer and
developer verbs with the `TESTMAP:<state>` report, and the framework-home
migration verb.

This task carries the module's cut — submodules, owned files, the interfaces
it provides and consumes, the seams later modules land into it — and the
planning protocol. It does **not** restate the specification.

**Proposal (authoritative for every detail):**
`aidocs/testing_engine/n014_explorer_006_proposal.md` — start at the *Module
Map* entry `#### M1 — Engine foundation and distribution`, then the
*Components* subsections tagged `(M1.x)` (listed under *Reading list* below),
then the narrative sections those components name. *Architecture*
(vocabulary, process boundary, registry directory, line-protocol index),
*Design decisions* and the *Invariants every module honours* apply to every
module.

**Acceptance:** the union of the module's components' test lists (*Module Map —
How to read it*).

## Submodules (one child task each — settled at the coarse planning pass)

| submodule | scope | depends on | wave |
|---|---|---|---|
| **M1.1** Per-user root | `AITASKS_HOME` resolution, `aitasks_engine_dir`, the home lock; `ait setup` printing `AITASKS_HOME:`. Owns `.aitask-scripts/lib/aitasks_home.sh`, `tests/test_aitasks_home.sh` (the default, the env override, the no-`~/.aitask/` grep) | — | A |
| **M1.2** Engine skeleton | `engine/` Go module, `cmd/ait-testmap`, the verb table (`version` live, every other verb a stub exiting 64), line-protocol / `--json` / per-verb exit-contract helpers, `-X version/commit/contract`, the `CONTRACT_MISMATCH` helper, pool cap 8, `internal/platform`, `internal/gitx` (git exec, blob digests, `merge-base --is-ancestor`, `ls-tree`), the `t.TempDir()` fixture harness with synthetic `(t<id>)` histories, the `go test -bench` harness with the 2× rule. Owns `engine/**` except later packages, `engine/go.mod` | — | A |
| **M1.3** Build, CI and release | `engine/build.sh` (matrix, `CGO_ENABLED=0`, ldflags), `.github/workflows/engine-check.yml`, the `engine` job in `release.yml` with `release needs: [plan, engine]`, SHA256SUMS. Owns `engine/build.sh`, the two workflow edits, `aidocs/framework/go_engine.md` (build half) | M1.2 | B |
| **M1.4** Shim and handshake | `.aitask-scripts/aitask_testmap.sh` (strict handshake `AIT_TESTMAP_BIN` > `AIT_ENGINE=dev` > `$AITASKS_HOME/engine/v<V>/` > `ENGINE_MISSING` exit 3), `lib/platform_detect.sh`, the `ait testmap` dispatcher arm. Owns those two scripts, the dispatcher arm, `tests/test_testmap_shim.sh`, `tests/test_platform_detect.sh` | M1.1, M1.2 | B |
| **M1.5** Install, upgrade and developer verbs | `install_engine_binary()` (source order, checksum, atomic install, self-check, `--force-engine`, `--no-testmap` / `AIT_TESTMAP_FETCH=0`, `.aitask-testmap/` gitignore), `install.sh --source-only` reaching it, `aitask_engine.sh build\|test\|cross\|prune`, `report_testmap_state()` with the states `engine-missing` / `absent` / `onboarded`. Owns the two functions in `aitask_setup.sh`, `aitask_engine.sh` (except `home`), `tests/test_install_engine_binary.sh`, the `packaging_strategy.md` paragraph, the `CLAUDE.md` Engine block | M1.1, M1.3, M1.4 | C |
| **M1.6** Framework home report and migration | `ait engine home [--migrate]`, the `HOME_LEGACY:` hint in setup, the migration cases in `tests/test_aitasks_home.sh`. Owns the `home` arm of `aitask_engine.sh` | M1.1, M1.5 | H |

## Cross-module seams

**Provides** (defined here, consumed elsewhere):

- M1.1 → the one `AITASKS_HOME` path resolver every other bash piece sources.
- M1.2 → the binary every engine submodule of M2–M8 adds a package to; the
  fixture and bench harnesses every engine test uses.
- M1.3 → the release assets `ait-testmap_<V>_<os>_<arch>` + sums that M1.5
  installs.
- M1.4 → `ait testmap <verb>` for every later bash caller (M5.1, M6.5, M7.4,
  M7.5, M8.2, M8.3, M9.3).
- M1.5 → an installed engine on every host that ran `ait setup`;
  `TESTMAP:<state>`.
- M1.6 → the migration verb.

**Consumes:** nothing from the other modules — M1.1 and M1.2 are the roots of
the whole dependency graph. It edits existing framework surfaces: the `ait`
dispatcher, `aitask_setup.sh`, `install.sh`, `release.yml`, `CLAUDE.md`.

**Hooks and extensions** (a file has one owner; a later submodule lands its
edit as the owner's named extension):

- `report_testmap_state()` (M1.5) ships with three states; **M6.1** adds the
  `bootstrapping\|<next>` state as its named extension. Shipping without it is
  a deliberate interim state (`tradeoff_module_boundaries_cut_across_packages`).
- The verb table (M1.2) registers every later verb as a stub exiting 64; each
  later engine submodule replaces only its own stub.
- `aitask_engine.sh` is M1.5's except its `home` arm (M1.6).
- `aidocs/framework/go_engine.md`: build half M1.3, engine half **M9.4**.
- Invariant 5 binds every engine package: the engine never writes `aitasks/`,
  `aiplans/`, `.aitask-data/`, a gate ledger, `project_config.yaml`,
  `gates.yaml`, a profile or `CLAUDE.md`, never invokes an `aitask_*.sh`
  script and never commits.
- Named follow-up (not v1): flipping `ait engine home --migrate` to the setup
  default.

## Reading list in the proposal

- *Module Map* — `#### M1`, *How to read it*, *Cross-module interfaces*,
  *Suggested implementation order* (waves A, B, C, H).
- *Components* — *Go engine and CLI (M1.2)*, *Engine binary identity and
  budget (M1.2)*, *Binary distribution (M1.3, M1.4)*, *Engine install, upgrade
  and state report (M1.5)*, *Per-user root (M1.1)*, *Framework home report and
  migration verb (M1.6)*.
- *Architecture* — *The process boundary*, *Process map*, *Where state lives*.
- *Assumptions* — *Engine, distribution and install (M1)*; *Tradeoffs* —
  *Engine and distribution (M1)*, *The per-user root (M1)*; *Open questions*.
- Framework rules that apply: `aidocs/framework/aitasks_extension_points.md`
  (install flow, framework PATH / binary shimming, new helper scripts) and
  `aidocs/framework/shell_conventions.md`.

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
