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
module of the proposal. This is **M4 — Selection, freshness and feedback**:
the map put to use — what to run, what is stale, what the last run proved,
what the map got wrong.

This module delivers the change-surface intake and the graded selector with
`explain`, the stamp semantics and the `stale` tool, the evidence join that
turns `last_pass` anchors into `EVIDENCED` vs `STALE` per variant, the
feedback verbs (`score` after every full run, `attribute --propose`,
`readiness` with `LEVEL` / `NEXT`), and the engine `test` composite that runs
`select --include-stale → schedule → run` in one process.

This task carries the module's cut — submodules, owned files, the interfaces
it provides and consumes, the seams later modules land into it — and the
planning protocol. It does **not** restate the specification.

**Proposal (authoritative for every detail):**
`aidocs/testing_engine/n014_explorer_006_proposal.md` — start at the *Module
Map* entry `#### M4 — Selection, freshness and feedback`, then the
*Components* subsections tagged `(M4.x)` (listed under *Reading list* below),
then the narrative sections those components name. *Architecture*, *Design
decisions* and the *Invariants every module honours* apply to every module.

**Acceptance:** the union of the module's components' test lists (*Module Map —
How to read it*).

## Submodules (one child task each — settled at the coarse planning pass)

| submodule | scope | depends on | wave |
|---|---|---|---|
| **M4.1** Change-surface intake and selector | the `--changes -` line intake refusing `UNKNOWN:`, the graded walk with select / implies / escalate rules, variant expansion and axis join, test-dep at distance 1, `ESCALATE` on opaque files, the scoped join, kind-then-cost ranking, invocation groups, stale marks, `--include-stale`, the suite budget with `DEFERRED`, `--format lines\|json\|tokens`, the prediction record, `explain` and `explain --sources --format table`, the `edge(seeded:…)` and `adopted(…)` reasons, `SELECTED:` and `UNMAPPED_SOURCE:` ahead of the rows. Owns `internal/selectr`, `internal/changesurface`, verbs `select` and `explain` | M2.1, M2.3, M2.4, M2.5, M2.6, M3.4 | C — see *Known inconsistencies* |
| **M4.2** Freshness and staleness | stamp semantics (who may write one), `stale --task\|--all` with its line classes and encodings, `--confirm`, `--confirm-source`, `--confirm-evidenced`, `--retarget`, the `SEEDED:` / `ADOPTED:` summaries, the `adopted(…)` DISPLAY field, `bootstrap_until` / `require_stamp` / `flake_threshold`. Owns `internal/stale` (all but the join), verb `stale` | M2.2, M2.6, M4.1 | D |
| **M4.3** Evidence join | `last_pass` anchors per reached variant, flake and cause filtering, the ancestor check, one `git ls-tree` per sha, `EVIDENCED` vs `STALE` per variant, never rewriting. Owns the join in `internal/stale` + `internal/gitx` | M3.4, M4.2 | D |
| **M4.4** Feedback: score, attribute, readiness | automatic `score` after every full run (window scoring, per-task attribution, `REJECTION_CONTRADICTED`), `attribute` with `--propose` writing `seeded.yaml` rows of origin `observed`, `readiness` with `LEVEL` / `NEXT`, its criteria and counters. Owns `internal/feedback` (all but `cadence.go` and the `policy` package), verbs `score`, `attribute`, `readiness` | M2.6, M3.4, M4.1 | D |
| **M4.5** Engine `test` composite | `test --task --changes - \| --paths \| --all [--explain] [--budget-s] [--format] [--run <id>]` running `select --include-stale → schedule → run` in one process; `--all` as `run --all` honouring `subsumed_by` and triggering `score`. Owns verb `test` in `internal/selectr` | M3.2, M3.3, M4.1, M4.4 | C — see *Known inconsistencies* |

## Cross-module seams

**Provides** (defined here, consumed elsewhere):

- The ranked list, `SELECTED:`, `UNMAPPED_SOURCE:`, the prediction record,
  `explain --sources --format table` — M4.1 → M4.5, M5.1 (verdict), M9.1
  (procedure), M9.2 (QA).
- The `stale` report and the `adopted(…)` DISPLAY — M4.2 → M8.2, M8.3.
- Self-healing `STALE` rows — M4.3.
- The `readiness` lines, `LEVEL` / `NEXT`, the scored history the policy flip
  needs, the observed-seed path — M4.4 → M5.2, M6.1 (`status`), M6.5, M8.4,
  M8.5.
- The `test` composite's output — M4.5 → M5.1 (the one engine call the bash
  front makes).

**Consumes:** the loaded registry and the adoption tables (M2.1, M2.6); the
stamp format and the rewriter (M2.2); scanner facts (M2.3); variant expansion
(M2.4); the scoped join (M2.5); the builtins, the wave plan and the cost rows
(M3.2, M3.3, M3.4); the change-surface line intake `COMMITTED:` / `TASK:` /
`OTHER:` / `UNKNOWN:` produced by `aitask_change_surface.sh` (exists today —
M4.1 parses it, M4.2 / M5.1 / M7.4 reuse the parse).

**Hooks and extensions** (a file has one owner; a later submodule lands its
edit as the owner's named extension):

- `readiness` (M4.4) gains `CALIBRATION:` / `REVIEW_AGREEMENT:` from **M7.3**
  and `POLICY:`, `CADENCE:`, `approved_by\|engine` from **M8.4 / M8.5** — all
  additive; the base protocol is M4.4's.
- `internal/feedback` is M4.4's; **M8.4** adds the `policy` package and
  **M8.5** adds `cadence.go`.
- The `testmap_fresh` gate's role on top of freshness is **M8.3**'s; M4.2
  provides the report it consumes and never the workflow.
- `score` (M4.4) writes `costs/predictions.yaml`, whose store is **M3.4**'s;
  the window-score trigger is reused by M8.5's cadence.
- The `edge(seeded:…)` / `adopted(…)` reasons and `--propose` rows depend on
  the M2.6 tables — see the inconsistency below.
- Invariant 2 (a stamp is a claim; a seed is not) is enforced here: seeds
  never suppress `STALE`, anchor evidence, satisfy `require_stamp` or count
  under `--strict`.
- Named follow-up (not v1): hunk-level attribution inside a member file (with
  M2.3).

## Known inconsistencies in the proposal — settle at the coarse pass

- **Wave order vs. stated dependencies.** M4.1 (wave C), M4.2 and M4.4 (wave
  D) list M2.6 (wave E) as a dependency, and M4.5 (wave C) lists M4.4 (wave D).
  Either M2.6 moves to wave C and M4.5 to wave D, or the selector, `stale` and
  `readiness` ship without seeded / adopted rows and M2.6 extends them
  additively (and `test --all` ships without triggering `score`). Decide with
  the M2 and M8 parents and fix the proposal's tables (protocol §1).

## Reading list in the proposal

- *Module Map* — `#### M4`, *How to read it*, *Cross-module interfaces*,
  *Suggested implementation order* (waves C, D).
- *Components* — *Selector (M4.1)*, *Freshness (M4.2)*, *Staleness tool
  (M4.2)*, *Evidence join (M4.3)*, *Feedback tools (M4.4)*, *Engine `test`
  composite (M4.5)*.
- *Data Flow* — *A task in steady state*, *Reading the map without running
  anything*, *The policy flip* (what `score` and `readiness` feed).
- *The Run Surface* — *Resolution, in order*, *Output and exit contract*.
- *Architecture* — *Line-protocol index*.
- *Assumptions* — *The map and freshness (M2, M4)*; *Tradeoffs* — *Freshness
  and evidence (M4)*; *Open questions*.

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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1852** id=2026-09-22T14:31:28Z.8641bc6cad150c1cfe062eb9 from=t1852 at=2026-09-22T14:31:28Z base=d0836b4f1750fde12e5e30260cd0d34396793a17 base_branch=main dirty=yes host=omg16
>
> | **Sequencing clarification (advisory, from the t1852 coarse pass, 2026-09-22).** The user asked that M1's children be *implemented* before M2 (t1853) is *planned*. Read the "plan all ten parents before implementing any child" paragraph in this task's body as an upper bound on how far planning may run ahead, not a requirement to plan against providers that do not exist. The rule is submodule-granular, never whole-parent (module-level deps form a cycle: M6.5 -> M8.2/M8.4, M8.3 -> M7.1/M7.2, M7.1 -> M6.2): start this parent's coarse pass once the specific provider submodules its wave-earliest children consume have landed in the tree, and implement its children in proposal wave order. A standalone cross-linking chore task (created from t1852's pass, followup_kind risk_mitigation) checks every "depends on" cell against real depends entries once all ten parents are decomposed; it accepts archived children as evidence and never rewrites M10.2-M10.5 (cross-repo).
> | 
> | **Go source layout (proposal fix, commit 07a546087 on main).** The engine source directory is `goengines/`, not `engine/`: one Go module (`github.com/beyondeye/aitasks/goengines`) for every distributable Go executable, `goengines/cmd/ait-testmap/`, shared packages `goengines/internal/{gitx,platform,lineproto}`, and every testmap-specific package under `goengines/internal/testmap/<pkg>`. Wherever the proposal (and this task's owns cells) write `internal/<pkg>`, read `goengines/internal/testmap/<pkg>`. Unchanged: the binary name `ait-testmap`, `$AITASKS_HOME/engine/v<V>/`, the `ait engine` verbs. CI workflow is `goengines-check.yml`; the release job is `goengines`. M1.2 (t1852_2) creates the module root; each later submodule adds only its own package and replaces only its own stub verb.
