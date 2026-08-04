---
priority: medium
effort: medium
depends: [t635_34]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [t635_34]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-27 23:28
updated_at: 2026-08-04 11:49
boardidx: 45056
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t635_34

## Verification Checklist

- [x] On a REAL stale downstream install (not a fixture), run `ait gates sync-registry --dry-run` and confirm the report matches what the applying run later does. — PASS 2026-08-04 11:49 auto: real stale install aitasks_mobile (fw 0.27.0, zero verifier keys); dry-run stdout byte-identical to the applying run (cmp -s), file cksum unchanged by dry-run
- [x] Apply `ait gates sync-registry` and confirm every comment line in the project's gates.yaml survives byte-for-byte (diff the `#` lines before/after). — PASS 2026-08-04 11:49 auto: all 3 project comment lines byte-identical after apply (diff showed additions only, from NEW_GATE lexical copies). Comments seeded first -- every downstream install here had its comments destroyed by the old merge_yaml upgrade path, so the check would otherwise be vacuous
- [x] Confirm a locally customized value (e.g. a project's own `verifier:`) is reported as CONFLICT and left untouched on disk. — PASS 2026-08-04 11:49 auto: seeded 'verifier: our-custom-build' reported as CONFLICT:build_verified.verifier:our-custom-build|aitask-gate-build and left byte-intact on disk, adjacent comment preserved
- [x] Confirm a task that previously blocked on `no verifier configured (deferred)` now runs its verifier and archives with NO manual `aitask_gate.sh append`. — PASS 2026-08-04 11:49 auto: real task t33 (gates: [risk_evaluated]) went 'blocked: no verifier configured (deferred)' -> verifier dispatched -> pass (attempt 1) -> ALL_PASS -> archived COMMITTED:f0f0822, zero manual aitask_gate.sh append
- [x] Confirm the pick-time stderr warning appears when picking a task whose active gate has no verifier, and disappears after the reconcile. — PASS 2026-08-04 11:49 auto: warning fires at materialize-active on BOTH the write and the NOOP re-pick path, names ait gates sync-registry, stdout stays one status line; absent after reconcile
- [x] Confirm `ait gates sync-registry` a second time reports exactly NOOP and changes no bytes. — PASS 2026-08-04 11:49 auto: exactly NOOP + zero bytes changed on the conflict-resolved real registry, and NOOP on a second real install (thinking_backend). Note: an UNRESOLVED conflict correctly keeps reporting CONFLICT instead of NOOP
- [x] Confirm the registry is NOT auto-committed and the stderr hint names `./ait git add`. — PASS 2026-08-04 11:49 auto: git status shows ' M aitasks/metadata/gates.yaml' with HEAD unmoved; stderr hint reads 'registry updated but NOT committed - review it, then: ./ait git add aitasks/metadata/gates.yaml', suppressed on a no-change run
