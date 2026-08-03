---
priority: medium
effort: medium
depends: [t635_34]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: ['635_34']
created_at: 2026-07-27 23:28
updated_at: 2026-07-27 23:28
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

- [ ] On a REAL stale downstream install (not a fixture), run `ait gates sync-registry --dry-run` and confirm the report matches what the applying run later does.
- [ ] Apply `ait gates sync-registry` and confirm every comment line in the project's gates.yaml survives byte-for-byte (diff the `#` lines before/after).
- [ ] Confirm a locally customized value (e.g. a project's own `verifier:`) is reported as CONFLICT and left untouched on disk.
- [ ] Confirm a task that previously blocked on `no verifier configured (deferred)` now runs its verifier and archives with NO manual `aitask_gate.sh append`.
- [ ] Confirm the pick-time stderr warning appears when picking a task whose active gate has no verifier, and disappears after the reconcile.
- [ ] Confirm `ait gates sync-registry` a second time reports exactly NOOP and changes no bytes.
- [ ] Confirm the registry is NOT auto-committed and the stderr hint names `./ait git add`.
