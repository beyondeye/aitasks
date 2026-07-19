---
priority: medium
effort: medium
depends: [t1076_3]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: ['1076_3']
created_at: 2026-07-09 11:26
updated_at: 2026-07-09 11:26
boardidx: 200
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1076_3

## Verification Checklist

- [ ] [t1076_3] Mount a real share (NAS / USB / network mount) and register it as the dir backend: artifacts.backends.dir.path in aitasks/metadata/project_config.yaml
- [ ] [t1076_3] From checkout A, create an artifact on the dir backend (ait artifact create ... --backend dir); from a second DISTINCT checkout/environment (ideally another machine, or at minimum another user/path on one machine) with only the project config, clear ~/.cache/ait/artifacts and resolve the handle (ait artifact get) — confirm fetch + cache + hash verify
- [ ] [t1076_3] Confirm the same-absolute-path mount assumption holds or fails clearly: with the share mounted at a DIFFERENT path than config says, operations must die actionably (not corrupt or invent a store)
- [ ] [t1076_3] Unmount the share and confirm operations fail closed with "is the share mounted?" — nothing is written into the empty mountpoint dir
- [ ] [t1076_3] Run ait artifact move local->dir and back against the real mount; confirm atomic put across the mount boundary (no .put.* residue in the store, manifest-only commits, source blobs intact)
