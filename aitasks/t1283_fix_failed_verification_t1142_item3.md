---
priority: medium
effort: medium
depends: [1076_3]
issue_type: bug
status: Ready
labels: [verification, bug]
anchor: 1065
created_at: 2026-07-28 11:25
updated_at: 2026-07-28 11:25
---

## Failed verification item from t1076_3

> [t1076_3] Confirm the same-absolute-path mount assumption holds or fails clearly: with the share mounted at a DIFFERENT path than config says, operations must die actionably (not corrupt or invent a store)

### Source

- **Manual-verification task:** `aitasks/t1142_manual_verification_dir_backend_real_mount.md` (item #3)
- **Origin feature task:** t1076_3
- **Origin archived plan:** `aiplans/archived/p1076/p1076_3_share_handle_resolution.md`

### Commits that introduced the failing behavior

- 640fc94f4 feature: Add share-handle backend registry, dir backend, and move verb (t1076_3)

### Files touched by those commits

- aidocs/task_attachments_design.md
- aidocs/unified_artifact_design.md
- ait
- .aitask-scripts/aitask_artifact.sh
- .aitask-scripts/lib/artifact_backends/dir.sh
- .aitask-scripts/lib/artifact_backend.sh
- .aitask-scripts/lib/artifact_cache.sh
- .aitask-scripts/lib/artifact_manifest.py
- .aitask-scripts/lib/artifact_registry.py
- .aitask-scripts/lib/artifact_registry.sh
- seed/project_config.yaml
- tests/test_artifact_cli.sh
- tests/test_artifact_dir_backend.sh
- tests/test_artifact_share_resolution.sh

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t1142 item #3.
