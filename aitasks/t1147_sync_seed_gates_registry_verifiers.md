---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [gates, ait_setup, installation]
assigned_to: dario-e@beyond-eye.com
anchor: 635
implemented_with: claudecode/fable5
created_at: 2026-07-10 20:52
updated_at: 2026-07-15 19:02
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

## Fix — two parts

**Part 1 — bring `seed/gates.yaml` in sync (new installs).**
Update `seed/gates.yaml` to match the canonical registry: add `verifier` +
`max_retries` / `timeout_seconds` for `risk_evaluated`, `build_verified`,
`tests_pass`, `lint`, `docs_updated`, and the `signal: file-touch` /
`signal_target` fields on `review_approved` / `merge_approved`. Prevent
recurrence: either make the live framework registry and `seed/gates.yaml` a
single source of truth, or add a test/CI check that fails when the two diverge on
the shipped gate set (a seed-vs-reference drift guard, analogous to how other
seed files are kept honest).

**Part 2 — migrate already-installed projects.**
`aitask_setup.sh` only seeds metadata in the fresh-init branch (when
`.aitask-data` does not yet exist), so re-running setup on an existing install
never refreshes `gates.yaml`. Provide a reconcile path so projects seeded before
the fix pick up the verifier keys WITHOUT clobbering project-specific
customizations — e.g. a `setup --upgrade` / `ait gates sync-registry` that merges
in verifier definitions for the framework's known gates while preserving any
project-added gates or edited commands. Confirm the fix end-to-end in a stale
install (thinking_app is a live reproduction: its
`aitasks/metadata/gates.yaml` currently has zero `verifier:` keys).

## Optional hardening

The mismatch only surfaces at archival, deep into the workflow. Consider surfacing
it earlier: when a task declares a gate (via `default_gates` injection or Step-7
backfill) whose registry entry has no `verifier` and is not a `kind: procedure`
gate, warn at pick/plan time rather than silently deferring until
`aitask_archive.sh` blocks.

## Acceptance

- A freshly seeded project's `aitasks/metadata/gates.yaml` contains the
  `risk_evaluated` verifier; picking + archiving a task under `fast` completes
  without a manual gate append.
- An existing (pre-fix) install can be migrated to the same state via the
  documented reconcile path, verified against thinking_app.
- A drift guard prevents `seed/gates.yaml` from silently falling behind the
  reference registry again.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-15T16:02:32Z status=pass attempt=1 type=human
