---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [testing, testmap, go_engine]
anchor: 1852
created_at: 2026-09-22 09:19
updated_at: 2026-09-22 09:19
---

## Goal

Part of the **testing engine / test map** feature — ten parent tasks, one per
module of the proposal. This is **M2 — Registry and map model**: everything
that reads and writes `aitestmap/` without running a test.

The map lives in a committed `aitestmap/` directory at the repository root.
This module delivers its layout and loader (the id grammar, the eight tables,
`config.yaml` and `check`), the `testmap:` annotation grammar and its
line-targeted rewriter (the only writer of `testmap:` lines), the dependency
scanners for bash / python / go / kotlin / Gradle with the plugin protocol,
variant axes, scoped rows and areas, and the adoption tables (`seeded` /
`adopted` / the `onboard.yaml` read tables) whose rows the onboarding and
review modules write.

This task carries the module's cut — submodules, owned files, the interfaces
it provides and consumes, the seams later modules land into it — and the
planning protocol. It does **not** restate the specification.

**Proposal (authoritative for every detail):**
`aidocs/testing_engine/n014_explorer_006_proposal.md` — start at the *Module
Map* entry `#### M2 — Registry and map model`, then the *Components*
subsections tagged `(M2.x)` (listed under *Reading list* below), then the
narrative sections those components name. *Architecture*, *Design decisions*
and the *Invariants every module honours* apply to every module.

**Acceptance:** the union of the module's components' test lists (*Module Map —
How to read it*).

## Submodules (one child task each — settled at the coarse planning pass)

| submodule | scope | depends on | wave |
|---|---|---|---|
| **M2.1** Registry core | the directory layout, the id grammar `<path>[#<member>][@<variant>]`, the six core tables, the `config.yaml` schema with every key and default, `check` and its rules, `scan --apply` persisting `variants:`, deterministic sorted writes, `CONTRACT_MISMATCH`, `exclude:` globs, `UNCOVERED_VALUE` / `UNMAPPED_ARTIFACT` reconciliation. Owns `internal/registry`, verbs `scan` and `check`, golden tests for the merges and the id grammar | M1.2 | A |
| **M2.2** Annotation grammar and rewriter | grammar v3 (`testmap:unit` blocks and every key), per-language comment leaders incl. Python docstrings read-only, unknown-key refusal, the line-targeted rewriter with `REWRITE_CONFLICT`, fixed per-language insertion positions, `annotate` / `annotate --suggest` / `annotate --from-body`, `verify`, `# Covers:` prose never matched. Owns `internal/annot` (all but `--author`), verbs `annotate` and `verify`, placement goldens per language | M2.1 | A |
| **M2.3** Dependency scanners | bash, python, go, kotlin (opaque contract), the Gradle module graph, the plugin protocol under `aitestmap/scanners/`, the opt-in `android-res` symbol scanner, the XDG blob cache, the exported facts (`static:invocation` / `static:import` / `static:package`, anchor lines, declared symbols). Owns `internal/deps`, one red-proved fixture per opaque branch | M1.2 | B |
| **M2.4** Axes and variants | `axes.yaml`, the runner-side `axis:` / `token_format:`, `<unit>@<value>` ids, the facet join, `--axis`, `axes --list\|--check\|--explain`, the three axis check rules. Owns `internal/axes`, verb `axes` | M2.1 | C |
| **M2.5** Scoped rows and areas | `_scoped.yaml`, `registry/areas.yaml` and `areas:` blocks, `areas --import-codemap`, `owns:` by area name, kind ranking data, triggers, `reads`, `DEAD_SCOPE` / `KIND_MISMATCH\|CONVERT_TO_SUITE`, `classify --suggest` with the three onboarding signals and `fanout:<n>`, the digest-exemption of scoped rows. Owns the scoped tables in `internal/registry`, verbs `areas` and `classify --suggest` | M2.1 | B |
| **M2.6** Adoption tables | the `seeds` and `adopted` tables in the loader; `onboard.yaml`'s `rejections[]` / `reviews[]` / `kind_proposals[]` / `calibration[]` as read tables; the load rules `SEED_SHADOWED` / `ADOPTED_ORPHAN` / absent-`by:`-is-human; the write routing for every verb that touches the three files; `SEEDED:` / `ADOPTED:` counts on `check`. Owns the two tables in `internal/registry`, the `onboard.yaml` reader, goldens for the `by:` merge and the shadow rule | M2.1, M2.2 | E — see *Known inconsistencies* |

## Cross-module seams

**Provides** (defined here, consumed elsewhere):

- The loaded registry (eight tables, id grammar, config keys) — M2.1, M2.6 →
  every engine package.
- The `testmap:` grammar, the stamp format `@<date>/<blob10>`, the rewriter
  API — M2.2 → M4.2 (`--confirm*`), M6.3 (`adopt`), M7.2 (`--agent-verdicts`),
  M7.4 (`--author`).
- Scanner facts: the closure, invocation / import / package facts, anchor
  lines, declared symbols — M2.3 → M4.1 (closure), M6.2 (origins), M7.1
  (packets), M7.4 (corroboration).
- Variant expansion — M2.4 → M4.1 (selector), M3.4 (cost), M4.3 (evidence),
  M6.4 (`scaffold --axes`).
- The scoped join, the kind vocabulary, the three onboarding signals — M2.5 →
  M4.1, M6.4.
- The seeded-edge and adopted-edge rows, the `registry/seeded.yaml` schema —
  M2.6 → M4.1 (`edge(seeded:…)`), M4.2, M4.4 (`--propose`), M6.2 (writes the
  rows), M6.3, M7.1, M7.2, M8.2.

**Consumes:** M1.2 (the binary, the fixture and bench harnesses). Nothing
else — M2 never runs a test.

**Hooks and extensions** (a file has one owner; a later submodule lands its
edit as the owner's named extension):

- `internal/annot` is M2.2's; **M7.4** lands the `--author` arm as its named
  extension.
- `internal/registry` spans M2.1 and M2.6 by table (both in this parent).
- `classify --suggest` (M2.5) computes the onboarding signals; **M6.4**
  consumes them in `onboard classify`.
- Every verb that touches `seeded.yaml` / `adopted.yaml` / `onboard.yaml`
  (`stale` in M4.2, the `onboard` verbs in M6.x / M7.x, `attribute --propose`
  in M4.4) writes through M2.6's write routing, never around it.
- Invariant 6: adoption writes comment lines only, at a fixed position per
  language, never into a Python docstring — the rewriter (M2.2) is where this
  is enforced.
- Named follow-ups (not v1): a versioned scanner-plugin contract beyond the
  one-JSON-line-per-file form (M2.3); symbol-level attribution of Kotlin and
  Python changes and hunk-level attribution inside a member file (M2.3 / M4.1).

## Known inconsistencies in the proposal — settle at the coarse pass

- **M2.6's wave contradicts its consumers.** The wave table puts M2.6 in wave
  E, but the Module Map names it as a dependency of M4.1 (wave C), M4.2, M4.4
  and M8.2 (wave D). M2.6's own dependencies (M2.1, M2.2) are wave A, so the
  simplest repair is to plan M2.6 for wave C; the alternative is that the
  selector, `stale`, `readiness` and `testmap_check` ship without seeded /
  adopted rows and M2.6 extends them additively. Decide with the M4 and M8
  parents and fix the proposal's tables (protocol §1).

## Reading list in the proposal

- *Module Map* — `#### M2`, *How to read it*, *Cross-module interfaces*,
  *Suggested implementation order* (waves A, B, C, E).
- *Components* — *Registry loader and writer (M2.1 core; M2.6 adoption
  tables)*, *Annotation scanner and rewriter (M2.2)*, *Dependency scanners
  (M2.3)*, *Variant axes (M2.4)*, *Axis resolver verbs (M2.4)*, *Enumeration
  and reconciliation (M2.1)*, *Scoped-row registry and areas (M2.5)*,
  *Broad-test scheduling and staleness policy (M2.5 staleness half)*,
  *Adoption ledger: seeded → adopted → reviewed (M2.6 data)*.
- *Architecture* — *Vocabulary*, *The registry directory*, *Where state
  lives*, *Line-protocol index*.
- *The Adoption Model* — *The three states, with `by:`*, *The origin table*,
  *Placement: comment lines only*.
- *Assumptions* — *The map and freshness (M2, M4)*, *Variants, broad tests
  and runners (M2, M3)*; *Tradeoffs* — *Map and registry structure (M2, M3)*;
  *Open questions*.

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
| M1 — Engine foundation and distribution | @@M1@@ |
| M2 — Registry and map model | @@M2@@ |
| M3 — Runners, scheduling and cost | @@M3@@ |
| M4 — Selection, freshness and feedback | @@M4@@ |
| M5 — Run surface | @@M5@@ |
| M6 — Onboarding | @@M6@@ |
| M7 — Agent review and author annotation | @@M7@@ |
| M8 — Completion policy and gates | @@M8@@ |
| M9 — Workflow integration, skills and documentation | @@M9@@ |
| M10 — Rollout to the target repositories | @@M10@@ |

All ten share the topic anchor of the M1 task, so the board's By-Topic view
shows the whole feature as one lane.
