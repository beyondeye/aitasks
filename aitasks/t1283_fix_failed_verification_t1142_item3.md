---
priority: medium
effort: medium
depends: [t1076_3]
issue_type: bug
status: Ready
labels: [verification, bug]
anchor: 1065
created_at: 2026-07-28 11:25
updated_at: 2026-07-28 11:25
boardidx: 56320
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

### Observed behavior (t1142 verification run, 2026-07-28)

Setup: ext4 loop image mounted via udisks at `/run/media/ddt/aitshare`, store
root `/run/media/ddt/aitshare/store` registered as `artifacts.backends.dir.path`.

Two distinct defects, both in `.aitask-scripts/lib/artifact_backends/dir.sh`:

**D1 — `_artifact_dir_root`'s `die` is swallowed; the store path degenerates to
the filesystem root.** With the share mounted but the config pointing at a
non-existent path (`/mnt/aitshare_expected/store`):

```
$ ./ait artifact create 1142 v3a.html --kind report3a --backend dir
Error: artifact_dir: backend root not found: /mnt/aitshare_expected/store (is the share mounted?)
Error: artifact_dir: backend root not found: /mnt/aitshare_expected/store (is the share mounted?)
mkdir: cannot create directory '/34': Permission denied
mktemp: failed to create file via template '/34/.put.XXXXXX': No such file or directory
Error: artifact_dir_put: mktemp failed in /34
```

`_artifact_dir_root` is called from `_artifact_dir_blob_path` inside a command
substitution, and `cmd_create` runs under `with_attach_lock`'s
errexit-suppressed call tree — so `die` prints but does **not** abort. The
substitution yields the empty string and `printf '%s/%s'` produces
`/<2hex>/<62hex>`: the code then tries to **create a blob store at the
filesystem root**. Here it was stopped only by `/` not being writable — a
permissions accident, not fail-closed design. The final, user-visible error
(`mktemp failed in /34`) does not name the real cause. This is the same hazard
`artifact_registry.sh` already calls out ("Explicit `|| die`: callers run inside
with_attach_lock's errexit-suppressed call tree, where a failed capture would
NOT abort") — the dir adapter's own helpers do not apply it.

**D2 — an existing directory that is NOT the share is silently accepted as the
store.** With the share mounted at `/run/media/ddt/aitshare` and the config
pointing at an unrelated empty directory:

```
$ ./ait artifact create 1142 v3b.html --kind report3b --backend dir
Created artifact art:t1142-report3b (v1 sha256:1834e867...) on t1142
$ find <that dir>
  <dir>/18/34e86792b81e0b9ea802e569396fa6cee4091e945a10cd32c2475d08a7b6e6
```

Exit 0, manifest committed with `"backend": "dir"`, blob written outside the
share. Every other checkout resolving that handle gets `blob not found`. The
adapter's only root check is `[[ -d "$ARTIFACT_DIR_ROOT" ]]`, so it cannot tell
the share from any other directory that happens to sit at that path.

### Suggested direction

- Make root resolution abort for real under `with_attach_lock` (capture with an
  explicit `|| die` at every call site, or resolve the root once at activation
  and validate there rather than per blob-path derivation).
- Never derive a blob path from an empty root — treat an empty root as fatal.
- Validate that the configured root is actually the intended store, not merely
  an existing directory: e.g. require a store marker file written at
  first use and refuse to write when the root exists but the marker is absent.

Shares a root cause with **t1284** (unmounted share + persistent mountpoint
dir). Fix the two together, or fix the root-resolution seam here and let t1284
verify the unmount case.
