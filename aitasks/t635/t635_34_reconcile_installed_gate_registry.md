---
priority: medium
effort: medium
depends: [635_33]
issue_type: enhancement
status: Ready
labels: [gates, task_workflow]
anchor: 635
created_at: 2026-07-17 11:05
updated_at: 2026-07-17 11:05
---

## Problem

Already-installed downstream projects that were seeded **before** the gate
registry-verifier fix (t1147 Part A) still carry a stale
`aitasks/metadata/gates.yaml` that is missing `verifier` / `kind` / `signal`
keys. Their tasks block on `risk_evaluated` with
`blocked: no verifier configured (deferred)`, forcing a manual
`aitask_gate.sh append <id> risk_evaluated pass` before archival (observed
2026-07-10 in `thinking_app` archiving t37).

t1147 Part A fixed **new** installs + shipped a drift guard by making
`.aitask-scripts/gates_reference.yaml` the canonical source (synced downstream
even when `seed/` is deleted). But **existing installs remain broken** until a
reconcile path lands. This task is the absorbed Part 2 (reconcile) + Part 3
(early warning) that t1147 deferred, and that t635_33 split out.

## Scope

### 1. `ait gates sync-registry` — reconcile installed registries (former t1147 Part 2)

Fill missing verifier/kind/signal/signal_target/max_retries/timeout_seconds
keys into an installed project's `aitasks/metadata/gates.yaml` from the
canonical `.aitask-scripts/gates_reference.yaml`, **additively**:

- **Additive merge only** — never clobber a project's customizations. A gate
  present in both with a *differing* value for a key is a **conflict**:
  report it, do NOT silently overwrite (see
  [[feedback_merge_dedup_conflict_over_silent_guess]] — degrade to
  manual-conflict on anomaly; guard + test the silent-decision path).
- Missing gates / missing keys are filled from the reference; identical
  values are no-ops; the command prints a summary (`FILLED:<gate>.<key>`,
  `CONFLICT:<gate>.<key>:<project>|<reference>`, `NOOP`).
- Reuse the canonical `gate_ledger.read_registry()` parser as the semantic
  diff oracle (no new YAML parsing).
- **Reconcile profile gate policy too**: under the t635_33 redesign the
  registry reconcile should also surface/repair profile `default_gates` /
  `rendered_gates` drift where a declared/rendered gate has no registry entry.
  Shape this against the active_gates / rendered_gates model landed in t635_33.

### 2. Early "no verifier" warning (former t1147 Part 3)

Warn at **pick / plan time** when a task's effectively-active gate has a
registry entry with no `verifier` and is not `kind: procedure`, instead of
silently deferring until archival blocks. Re-evaluate scope against t635_33:
a gate outside the profile's rendered ceiling is already filtered from
`active_gates` and never enforced, so the warning only needs to fire for a
gate that IS in `active_gates` but has no configured verifier — the genuine
"declared-and-active-but-unconfigured" case.

## Key files

- `.aitask-scripts/aitask_gate.sh` — new `sync-registry` subcommand + dispatch
  + help (or a dedicated `aitask_gates_sync.sh` helper it calls).
- `.aitask-scripts/lib/gate_ledger.py` — reuse `read_registry()`; add the
  additive-merge + conflict-detection primitive (pure, unit-testable).
- `.aitask-scripts/gates_reference.yaml` — the canonical source (read-only here).
- Pick/plan warning site: `.claude/skills/task-workflow/planning.md` (or the
  effective-gate resolution point) — thread the no-verifier check.
- Tests: `tests/test_gates_sync_registry.sh` (additive fill, conflict-report,
  no-op, profile-policy reconcile) — mirror `test_gates_reference_drift.sh`
  fixture style; drive the real `aitask_gate.sh` entry point.

## Depends

- **t635_33** (gate_activation_render_time) — MUST land first: sync-registry
  should reconcile profile gate policy against the `active_gates` /
  `rendered_gates` model, and the early-warning scope depends on the
  effective/active-set definition. (Set in `depends`.)
- Builds on **t1147 Part A** (landed): canonical
  `.aitask-scripts/gates_reference.yaml` + drift guard
  (`tests/test_gates_reference_drift.sh`).

## Reverse links

- t1147 (`aiplans/archived/p1147_sync_seed_gates_registry_verifiers.md`) — Part
  2/3 deferred here.
- t635_33 (`aitasks/t635/t635_33_gate_activation_render_time.md`) — split this
  scope out; provides the active_gates/rendered_gates model this reconciles against.

## Verification

- Fixture install with a stale `gates.yaml` (zero verifiers) →
  `ait gates sync-registry` fills the `risk_evaluated` verifier additively;
  a customized gate value is reported as CONFLICT, not overwritten.
- A task with an active gate lacking a verifier surfaces the early warning at
  pick/plan time (not only at archival).
- `shellcheck` clean; new test passes; `test_gates_reference_drift.sh` still passes.

## Step 9 (Post-Implementation)

Standard cleanup / archival / merge per task-workflow Step 9.
