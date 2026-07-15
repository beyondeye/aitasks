---
Task: t1147_sync_seed_gates_registry_verifiers.md
Base branch: main
plan_verified: []
---

# t1147 — Sync gate registry verifiers (re-scoped to Part 1)

## Context

Downstream projects seeded from the framework cannot archive tasks under the
`fast` profile: every task blocks on `risk_evaluated` with
`blocked: no verifier configured (deferred)`, forcing a manual
`aitask_gate.sh append <id> risk_evaluated pass` before archival (observed
2026-07-10 in `thinking_app` archiving t37).

**Root cause:** `seed/gates.yaml` is stale vs the framework's live registry
(`.aitask-data/aitasks/metadata/gates.yaml`). The verifier keys landed in the
live registry (`93f63296a`, `2f3211df4`) but the seed copy was never updated, so
it ships **zero `verifier:` keys** and is missing `tests_pass` / `lint` /
`docs_updated` and the `signal`/`signal_target` fields. The orchestrator finds no
verifier for `risk_evaluated`, defers, and archival refuses.

**Scope decisions (confirmed with user over several rounds):**
1. **t1147 is re-scoped to Part 1 only** — make the shipped registry correct.
   Single source of truth = a new canonical `.aitask-scripts/gates_reference.yaml`
   (required because `seed/` is NOT synced to installed projects, but
   `.aitask-scripts/` is). **Design-agnostic**: a correct registry is right under
   any gate-activation model. Satisfies original AC#1 (new installs) + AC#3 (drift
   guard). It does **NOT** touch any profile's `default_gates`.
2. **Original Part 2 (reconcile existing installs) and Part 3 (early-warning) are
   deferred** into a new gate-activation redesign task (Part B), because they are
   entangled with the broader concern that gate integration is too rigid /
   over-activated.

---

## Part A — Implement (this task, t1147)

**Files:**
- **NEW** `.aitask-scripts/gates_reference.yaml` — byte-for-byte the current live
  `.aitask-data/aitasks/metadata/gates.yaml` (full canonical content: schema
  header comment + every `verifier` / `max_retries` / `timeout_seconds` /
  `signal` / `signal_target` / `kind` key). Its header comment declares the **edit
  protocol** (see below).
- `.aitask-scripts/aitask_setup.sh` (~1339–1353) — **[C1: seedless-safe]** the
  current `cp seed/gates.yaml` lives INSIDE `if [[ -d "$project_dir/seed" ]]`, so
  a seedless fresh-init (the downstream case this whole design targets) would skip
  gate-registry creation. Fix: **delete** the `cp seed/gates.yaml` line from the
  seed block and add an **independent** copy that runs whenever the reference
  exists, regardless of seed/:
  ```bash
  # Gate registry is canonical under .aitask-scripts/ (ships downstream even when
  # seed/ is absent) — copy independent of the seed metadata block.
  [[ -f "$project_dir/.aitask-scripts/gates_reference.yaml" ]] && \
    cp "$project_dir/.aitask-scripts/gates_reference.yaml" \
       "$project_dir/.aitask-data/aitasks/metadata/gates.yaml" 2>/dev/null || true
  ```
- `install.sh` `install_seed_gates_registry()` (~435) — repoint `src` from
  `$INSTALL_DIR/seed/gates.yaml` → `$INSTALL_DIR/.aitask-scripts/gates_reference.yaml`
  (keep `merge_seed`; `.aitask-scripts/` is already part of the tarball payload).
  Keep the two install paths in sync per the `_ait_framework_paths` note.
- **REMOVE** `seed/gates.yaml`; redirect `tests/test_dependency_unblock.sh:118`
  (`cp "$PROJECT_DIR/seed/gates.yaml" …`) → `.aitask-scripts/gates_reference.yaml`.
- **NEW** `tests/test_gates_reference_drift.sh` — **[C2: non-optional parity]**:
  1. *Structural (always):* load the reference via `gate_ledger.read_registry()`
     (reuse the canonical stdlib parser — no new YAML parsing); assert every
     machine gate with `kind` != `procedure` has a non-empty `verifier`
     (`risk_evaluated`, `build_verified`, `tests_pass`, `lint`) and the framework
     gate set is present.
  2. *Field-complete parity (non-optional in the framework repo):* read the live
     registry from the **branch ref, not the worktree** —
     `git show aitask-data:aitasks/metadata/gates.yaml` (verified working; falls
     to `./ait git show` in legacy mode) — and assert `read_registry(reference)
     == read_registry(live)` across ALL fields (verifier, signal, signal_target,
     max_retries, timeout_seconds, kind). This runs even without a `.aitask-data`
     worktree, closing the silent-drift gap. Only if the `aitask-data` branch ref
     is genuinely absent (rare) does it degrade — and then it **fails loudly as a
     validation gap**, never a silent pass. (Downstream projects don't run this
     framework-internal test.)
- Docs: `aidocs/gates/aitask-gate-framework.md` + the `gates_reference.yaml`
  header — **[C3: edit protocol]** document that `.aitask-scripts/gates_reference.yaml`
  is the canonical source maintainers **edit first**, and the framework's live
  runtime registry (`.aitask-data/aitasks/metadata/gates.yaml`) is refreshed from
  it (a documented one-line `cp` / `./ait git` commit). The drift test enforces
  equality in **either** direction, so a forgotten refresh (of either copy) fails
  CI rather than shipping stale.
- **[C4]** Update `aitasks/t1147_*.md` Acceptance to the **Part-1 scope** with
  explicit wording: *Part A fixes NEW installs + the drift guard only;
  **already-installed projects (incl. the thinking_app reproduction) remain broken
  until the reconcile path lands** in the redesign task.* Add bidirectional
  reverse links t1147 ↔ t635_33. Do not let the title / original 3-part acceptance
  imply the live failure class is fully resolved.

**Verification (Part A):**
- `bash tests/test_gates_reference_drift.sh` (new) + `bash tests/test_dependency_unblock.sh` (redirected) pass; `shellcheck` on touched scripts.
- **[C5: real install path]** Exercise the packaged/install path, not just
  local setup: from a staged copy of the tracked tree (what `git archive` ships),
  run `install.sh`/`install_seed_gates_registry` and assert the resulting
  `aitasks/metadata/gates.yaml` contains the `risk_evaluated` verifier (proving
  `.aitask-scripts/gates_reference.yaml` is present in the artifact and wired).
  If a packaging/install test already exists, add the assertion there.
- Fresh `ait setup` into a throwaway dir (incl. a **seedless** dir to exercise
  the C1 path) → its `aitasks/metadata/gates.yaml` has the `risk_evaluated`
  verifier; pick + archive a trivial task under `fast` completes with **no**
  manual gate append.

---

## Part B — Create the gate-activation redesign task (new, under t635)

Create `aitasks/t635/t635_33_gate_activation_render_time.md` (next free t635
child number; confirm at creation). Task-management only — no code — planned in a
fresh session. Reverse-link on t635, t635_25, t635_14, and t1147 (`./ait git`).

**Draft description content:**

- **Problem.** Gate integration into task-workflow is too rigid; gates
  run/record when not needed, appreciably slowing execution. t635_14 retired the
  render-time `{% if %}` risk-gating toggle in favour of a `default_gates` key +
  **runtime checks present in every rendered profile** (e.g. `default`'s SKILL.md
  grew ~717→766 lines for content it previously rendered nothing for).

- **Why render-time gating was removed (do not regress).** The original problem
  was gate *selection* split across two sources — task `gates:` metadata AND
  profile `default_gates`. t635_14 unified the **resolution rule** (task `gates:`
  wins when present, else profile default) so there's one place to reason about
  which gates a task runs. The redesign must preserve that single-source
  resolution while recovering render-time leanness.

- **Chosen model — Model 1 (profile renders the ceiling; task selects within it
  at runtime).**
  - The **execution profile** declares a render-time gate set (the machinery
    rendered into that profile's task-workflow variant). Lean profiles render
    none → fast, minimal skill. Rendering stays **per-profile cached** (no
    per-task render cost).
  - The **task `gates:` metadata** selects/narrows WITHIN the rendered set at
    runtime. Both layers "activate": profile decides what is *rendered*, task
    decides what *executes*.
  - **Ceiling behavior (confirmed):** a gate filtered out by the profile is
    **invisible**, or at most reported as **"skipped: execution profile"** —
    **never a hard error**. Assume the user intended the filter when they chose
    the profile. The skipped-notice may be omitted if that makes the
    implementation easier/safer.

- **CRITICAL correctness invariant (the central implementation risk the user
  flagged — "be very careful").** A task's `gates:` may still declare a gate the
  profile did NOT render. The rendered skill has no machinery to record it, but
  the runtime enforcers (`aitask_gate.sh effective-gates`, `ait gates run`, and
  especially the `aitask_archive.sh` gate guard) read the task's declared `gates:`
  directly — so a declared-but-unrendered gate would **block archival with no way
  to satisfy it**, recreating the t1147 bug via profile filtering.
  - **Invariant:** the profile filter must apply at **every** layer, not just
    rendering. Define `effective_gates(task) = resolve(task.gates,
    profile.default_gates) ∩ profile.rendered_set` — always a **subset of what is
    rendered**. Filtered gates are treated as skipped/absent **everywhere**
    (resolution, orchestrator, archival guard, dependency-unblock), so they can
    neither break the rendered skill nor block archival.
  - **Where the filtered set is persisted + who consumes it (the enforcement
    substrate — critical).** Many enforcement paths run with **no live profile in
    scope**: dependency-unblock computes from a *dependent* task's perspective;
    the board, cross-session picks, and `ait gates run` may not carry the picking
    profile. So a purely runtime-recomputed filter is fragile. **Recommended:
    materialize a durable `active_gates` field** on the task, written once at
    pick/claim time (and **re-derived on every re-pick under the CURRENT
    profile**) = `resolve(task.gates, profile.default_gates) ∩
    profile.rendered_set`. **Every** runtime enforcer must consume `active_gates`,
    **never raw `gates:` alone**:
    - `aitask_gate.sh archive-ready` + the `aitask_archive.sh` gate guard,
    - dependency-unblock (`blocks_dependents` computed over `active_gates`),
    - procedure-gate dispatch (`aitask_gate.sh procedure-gates`),
    - `ait gates run` orchestrator, and `effective-gates` / `should-self-record`.

    Raw `gates:` stays the task's **declared intent**; `active_gates` is the
    profile-filtered **effective set** that governs rendering AND enforcement in
    lockstep — one persisted value that survives the no-profile-context callers.
    *(Alt considered: thread a durable profile context into every command so each
    re-derives the set — rejected as primary because dependency-unblock genuinely
    has no profile to thread.)*
  - **Staleness / supersession:** `active_gates` must be recomputed at claim time
    under the current profile — a re-pick under a *different* profile updates the
    effective set; a stale `active_gates` would silently enforce the wrong gates.
    Apply the framework's supersession discipline (never leave `active_gates`
    temporarily untrue vs the governing profile).
  - **Provenance (auditability):** persist the set **with the profile that
    produced it** — `active_gates_profile: <name>` (or similar) alongside
    `active_gates`. Recompute-at-claim keeps enforcement *correct*; provenance
    makes staleness **detectable and explainable** — a checker can compare the
    stamped profile against the currently-governing profile and flag "computed
    under `fast`, now governed by `default` → recompute" after a profile switch,
    a manual `gates:` edit, or a re-pick under another profile. Optionally also
    stamp a digest of the inputs (raw `gates:` + profile rendered-set) to detect a
    manual `gates:` edit that leaves the profile name unchanged. Without the stamp,
    runtime can still enforce, but stale `active_gates` is silent and unauditable.
  - One shared definition of "active under this profile" drives BOTH rendering and
    runtime enforcement — extending t635_14's single-source discipline to the
    render layer. **Negative-control tests (must-have):** a task whose `gates:`
    includes a profile-filtered gate must (a) render without that gate's
    machinery, (b) archive without blocking on it, and (c) unblock its dependents
    without waiting on it.
  - Open sub-decision for the redesign: whether the render ceiling is a reused
    `default_gates` (task can only narrow) or a distinct `rendered_gates` superset
    (backward-compatible default = render-all when unset). Reconcile with
    t635_14's current override semantics (task `gates:` beyond profile default).

- **Coordination (explicit — user flagged t635 is incomplete).**
  - **t635_25** (leaner_gate_check_invocation): leans the *call shape* but
    explicitly declines render-time omission — this redesign **extends** it to
    render-time. Decide fold vs sequence.
  - **t635_14**: the resolution rule being extended; don't regress its agent-error
    mitigation (tested helpers, not prose conditionals).
  - **t635 umbrella** (13 children pending): align with t635_24 (remove legacy
    verify_build), t635_28 (docs_updated activation), t635_31.
  - **t1147**: Part 1 (registry correctness) landed; reverse-pointer here.

- **Absorbed deferred scope from t1147.**
  - **Reconcile existing installs** (former Part 2): `ait gates sync-registry`
    filling missing verifier keys in an installed project's registry without
    clobbering customizations (additive merge, conflict-reported). Largely
    design-agnostic, but under the redesign it should also reconcile profile
    gate policy — shape it here.
  - **Early "no verifier" warning** (former Part 3): likely **subsumed** by "only
    activate gates when required" — re-evaluate whether still needed.

---

## Risk (t1147 / Part A implementation)

### Code-health risk: low
- Repointing the two copy sites (`aitask_setup.sh`, `install.sh`) to the new
  canonical path — a wrong path leaves fresh installs with no registry ·
  severity: medium · → mitigation: covered by the drift test + fresh-`ait setup`
  verification.
- Otherwise contained: one added file, one removed stale file, one redirected
  test, one new test reusing the canonical `read_registry` parser; no new
  abstractions · severity: low · → mitigation: TBD.

### Goal-achievement risk: low
- Install-tarball packaging: `install.sh` must find
  `.aitask-scripts/gates_reference.yaml` in the extracted tarball · severity: low
  · → mitigation: verify the tarball includes the `.aitask-scripts/` payload.
- AC#2 (reconcile) intentionally out of scope for t1147 (moved to the redesign) —
  a confirmed scope decision, not a coverage gap · severity: low · → mitigation:
  none needed.

## Final Implementation Notes

- **Actual work done:** Implemented Part A exactly as planned: created the
  canonical `.aitask-scripts/gates_reference.yaml` (live-registry content + edit
  protocol header), refreshed the live registry from it (data-branch commit),
  moved the setup gate-registry copy OUTSIDE the `[[ -d seed ]]` guard in
  `aitask_setup.sh` (seedless-safe), repointed `install.sh`
  `install_seed_gates_registry()` to the reference, removed `seed/gates.yaml`,
  redirected `tests/test_dependency_unblock.sh`, added
  `tests/test_gates_reference_drift.sh` (structural verifier-completeness +
  field-complete parity via `git show aitask-data:` branch-ref + packaging/wiring
  guards), extended `tests/test_data_branch_setup.sh` (Test 1 registry
  assertions + new seedless Test 1b), and documented the canonical
  reference/edit protocol in `aidocs/gates/aitask-gate-framework.md`. Part B:
  created **t635_33** (gate_activation_render_time) carrying the full redesign
  design (Model 1 ceiling, `active_gates` + `active_gates_profile` provenance,
  enforcement-substrate invariant, negative controls) and the absorbed t1147
  scope (reconcile path, early warning); re-scoped the t1147 task file; added
  the reverse pointer on t635_25.
- **Deviations from plan:** None material. The drift test's Part 3
  (packaging/wiring guards) was added during implementation per the C5 review
  concern — it asserts the reference is git-tracked/staged and that both install
  consumers read the canonical path (and neither reads seed/gates.yaml).
- **Issues encountered:** (1) The negative-control mutation of the reference
  could not be restored via `git checkout` (file untracked at that point) —
  restored by editing the line back and confirmed byte-identical to the live
  registry. (2) The Part-3 tracked-check initially failed because the new file
  was untracked; staged it (`git add`) ahead of the Step-8 commit, which is the
  state the guard is designed to require.
- **Key decisions:** Canonical file under `.aitask-scripts/` (framework-synced
  downstream) rather than seed-only + drift test — required by the future
  `ait gates sync-registry` (t635_33) which must run in installed projects where
  `seed/` is deleted. Parity check reads the live registry from the
  `aitask-data` BRANCH REF (`git show`), making it non-optional without a
  worktree and failing loudly (never silently skipping) when no source exists.
  Reused `gate_ledger.read_registry()` as the semantic diff oracle (no new YAML
  parsing).
- **Upstream defects identified:** None
- **Verification results:** test_gates_reference_drift 10/10 (negative control:
  mutated reference correctly failed 2 checks); test_data_branch_setup 70/70
  (incl. seedless Test 1b); test_dependency_unblock 12/12; gate regression
  suites (ledger 27, effective-gates 12, orchestrator 40, risk-verifier 26,
  verifiers 47, cli-wiring 15) all pass; functional install.sh check from
  staged tracked files only → `INSTALL_PATH_OK`; shellcheck clean on changed
  lines (remaining warnings pre-existing).
