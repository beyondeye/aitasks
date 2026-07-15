---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Done
labels: [gates, ait_setup, installation]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 635
implemented_with: claudecode/fable5
created_at: 2026-07-10 20:52
updated_at: 2026-07-15 19:22
completed_at: 2026-07-15 19:22
---

## Problem

Downstream projects seeded from the framework cannot archive tasks under the
`fast` profile: every task blocks on the `risk_evaluated` gate with
`blocked: no verifier configured (deferred)`, forcing the agent to hand-append a
pass (`aitask_gate.sh append <id> risk_evaluated pass`) before
`aitask_archive.sh` will proceed. Observed 2026-07-10 in the `thinking_app`
install while archiving t37.

## Root cause — `seed/gates.yaml` is stale relative to the live registry

The framework's OWN task-data registry
(`.aitask-data/aitasks/metadata/gates.yaml`) was updated in place when the real
verifiers landed:

- `93f63296a` — Register build/tests/lint gate verifiers in gates.yaml
- `2f3211df4` — Populate risk_evaluated gate verifier (t635_13)

But `seed/gates.yaml` — the copy that `aitask_setup.sh:1342`
(`cp "$project_dir/seed/gates.yaml" .../metadata/`) hands to downstream
projects — was never updated. Its git history stops at t635_1 / t635_3
(the gate substrate), so it still has NO `verifier:` keys for any gate.

`diff seed/gates.yaml .aitask-data/aitasks/metadata/gates.yaml` shows the seed is
missing, for every machine gate: `verifier:` (e.g. `aitask-gate-risk`),
`max_retries`, `timeout_seconds`, the `tests_pass` / `lint` / `docs_updated`
definitions, and the `signal: file-touch` / `signal_target` fields on
`review_approved` / `merge_approved`.

The failure chain in a seeded project:
1. `aitask_setup.sh` copies the stale `seed/gates.yaml` → project
   `aitasks/metadata/gates.yaml` (no verifier keys).
2. `seed/profiles/fast.yaml` declares `default_gates: [risk_evaluated]`, so every
   task picked under `fast` gets `gates: [risk_evaluated]` (injected at creation
   or backfilled at Step 7).
3. `.aitask-scripts/` IS framework-synced/overwritten, so the verifier *scripts*
   (`aitask_gate_risk.sh`, etc.) exist in the project.
4. But the registry that maps gate → verifier is stale, so the orchestrator finds
   no `verifier:` for `risk_evaluated` → defers → `aitask_archive.sh` refuses
   (`GATE_PENDING:risk_evaluated`).

The framework repo itself does not hit this because its `default_gates` point at
its OWN up-to-date live registry — which is exactly why the drift went unnoticed.

## Fix — RE-SCOPED to Part 1 only (2026-07-15)

**Scope decision:** during planning the user flagged that the overall gate
integration in task-workflow is too rigid (gates run when not needed, slowing
execution) and should move to a profile + skill-templating activation model.
The original Part 2 (reconcile already-installed projects) and the Optional
hardening (early "no verifier" warning) are **entangled with that redesign** and
were moved to **t635_33** (gate_activation_render_time, under the t635 gates
umbrella). This task keeps only the design-agnostic registry-correctness fix.

**Part 1 — canonical registry reference + sync + drift guard (new installs).**
Single source of truth = `.aitask-scripts/gates_reference.yaml` (it lives under
`.aitask-scripts/`, not `seed/`, so it also reaches installed projects — a
prerequisite for t635_33's future `ait gates sync-registry`). `aitask_setup.sh`
(fresh data init, seedless-safe) and `install.sh` copy from it; `seed/gates.yaml`
is removed; `tests/test_gates_reference_drift.sh` enforces field-level equality
between the reference and the framework's live registry plus
verifier-completeness of every command-driven machine gate.

## Moved to t635_33 (NOT fixed by this task)

**Already-installed projects — including the observed thinking_app
reproduction — remain broken after this task lands.** Re-running setup on an
existing install does not refresh `gates.yaml`; until t635_33's reconcile path
(`ait gates sync-registry`) ships, stale installs need the manual workaround
(`aitask_gate.sh append <id> risk_evaluated pass`) or a hand-copy of
`.aitask-scripts/gates_reference.yaml` over `aitasks/metadata/gates.yaml`.
The early "no verifier" pick/plan-time warning also moved there (likely subsumed
by activation-model changes).

## Acceptance (re-scoped)

- A freshly seeded project's `aitasks/metadata/gates.yaml` contains the
  `risk_evaluated` verifier; picking + archiving a task under `fast` completes
  without a manual gate append. This includes **seedless** installs (no `seed/`
  dir), which previously skipped registry seeding entirely.
- A drift guard prevents the shipped reference from silently falling behind the
  framework's live registry again (field-complete parity, both directions, no
  worktree required), and verifies the packaging/consumer wiring.
- ~~Existing-install migration (reconcile path, thinking_app verify)~~ →
  **moved to t635_33**.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-15T16:02:32Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-07-15T16:21:50Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-07-15T16:22:08Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:c286714ec7c100d7

> **✅ gate:risk_evaluated** run=2026-07-15T16:22:08Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1147/risk_evaluated_2026-07-15T16:22:08Z-risk_evaluated-a1.log`
