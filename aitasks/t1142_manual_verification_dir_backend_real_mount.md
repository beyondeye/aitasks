---
priority: medium
effort: medium
depends: [t1076_3]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [t1076_3]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-09 11:26
updated_at: 2026-07-28 11:27
boardcol: tests
boardidx: 20
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1076_3

## Verification Checklist

- [x] [t1076_3] Mount a real share (NAS / USB / network mount) and register it as the dir backend: artifacts.backends.dir.path in aitasks/metadata/project_config.yaml — PASS 2026-07-28 11:21 auto: ext4 loop image mounted via udisks at /run/media/ddt/aitshare (distinct fs, dev 1792 vs 58); store root /run/media/ddt/aitshare/store registered as artifacts.backends.dir.path; registry resolves ARTIFACT_DIR_ROOT and create wrote blob 94/3de0... into the share
- [x] [t1076_3] From checkout A, create an artifact on the dir backend (ait artifact create ... --backend dir); from a second DISTINCT checkout/environment (ideally another machine, or at minimum another user/path on one machine) with only the project config, clear ~/.cache/ait/artifacts and resolve the handle (ait artifact get) — confirm fetch + cache + hash verify — PASS 2026-07-28 11:24 auto: checkout B (fresh clone + aitask-data worktree, config only, no blobs) resolved art:t1142-report from the share with cache cleared; cache filled as a regular file; negative controls: tampered cache entry self-healed with warning, tampered store blob rejected (backend returned wrong bytes) and bad cache entry removed
- [fail] [t1076_3] Confirm the same-absolute-path mount assumption holds or fails clearly: with the share mounted at a DIFFERENT path than config says, operations must die actionably (not corrupt or invent a store) — FAIL 2026-07-28 11:25 follow-up t1283
- [fail] [t1076_3] Unmount the share and confirm operations fail closed with "is the share mounted?" — nothing is written into the empty mountpoint dir — FAIL 2026-07-28 11:25 follow-up t1284
- [x] [t1076_3] Run ait artifact move local->dir and back against the real mount; confirm atomic put across the mount boundary (no .put.* residue in the store, manifest-only commits, source blobs intact) — PASS 2026-07-28 11:25 auto: 2-version artifact moved local->dir->local across the real mount boundary (home fs dev 58 -> loop fs dev 1792); both move commits touched only artifacts/manifests/*.json; zero .put.* residue; source blobs intact on both sides; round-trip get returned correct bytes; negative control: corrupted store entry triggered the documented content-verify repair with correct bytes restored
