---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: [t1076_3]
issue_type: bug
status: Implementing
labels: [verification, bug]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1065
followup_kind: verification_failure
implemented_with: claudecode/opus5_5
created_at: 2026-07-28 11:25
updated_at: 2026-10-13 23:42
boardidx: 57344
---

## Failed verification item from t1076_3

> [t1076_3] Unmount the share and confirm operations fail closed with "is the share mounted?" — nothing is written into the empty mountpoint dir

### Source

- **Manual-verification task:** `aitasks/t1142_manual_verification_dir_backend_real_mount.md` (item #4)
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

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t1142 item #4.

### Observed behavior (t1142 verification run, 2026-07-28)

Setup: ext4 loop image mounted via udisks at `/run/media/ddt/aitshare`, store
root `/run/media/ddt/aitshare/store` registered as `artifacts.backends.dir.path`.

**Clause 1 — "fails closed with 'is the share mounted?'": partially satisfied.**
After `udisksctl unmount`, the message is emitted, and `create` / `get` both
exit 1:

```
$ ./ait artifact create 1142 v4.html --kind report4 --backend dir
Error: artifact_dir: backend root not found: /run/media/ddt/aitshare/store (is the share mounted?)
Error: artifact_dir: backend root not found: /run/media/ddt/aitshare/store (is the share mounted?)
mkdir: cannot create directory '/d0': Permission denied
mktemp: failed to create file via template '/d0/.put.XXXXXX': No such file or directory
Error: artifact_dir_put: mktemp failed in /d0
```

But the failure is not *closed*: the `die` is swallowed inside the command
substitution under `with_attach_lock`'s errexit-suppressed call tree, so the
code proceeds to attempt a blob store at `/<2hex>/<62hex>` — **the filesystem
root**. Only `/` being unwritable stopped it. Transaction rollback was clean
(no stray manifest, no task-file entry, no local blob). See **t1283** D1 for the
same mechanism reached via a wrong configured path.

**Clause 2 — "nothing is written into the empty mountpoint dir": FAILS for a
persistent mountpoint.** udisks removes `/run/media/<user>/<label>` on unmount,
so this setup cannot exercise the clause directly. The realistic NAS/fstab case
— a mountpoint directory created once by an admin, which survives unmount — was
reproduced with an empty directory at the configured path (behaviorally
identical: the adapter's only root check is `[[ -d "$ARTIFACT_DIR_ROOT" ]]`):

```
$ ./ait artifact create 1142 v3b.html --kind report3b --backend dir
Created artifact art:t1142-report3b (v1 sha256:1834e867...) on t1142
$ find <mountpoint dir>
  <mountpoint>/18/34e86792b81e0b9ea802e569396fa6cee4091e945a10cd32c2475d08a7b6e6
```

Blobs land on the local root filesystem inside the unmounted mountpoint, the
manifest is committed claiming `"backend": "dir"`, and the command exits 0.
Remounting the share then hides those blobs, and every other checkout resolving
the handle gets `blob not found`. This is exactly the data-loss trap `dir.sh`'s
header comment claims to prevent — the "never `mkdir -p` the root" rule only
covers a *missing* mountpoint, not an *empty* one.

### Suggested direction

- Detect that the configured root is a live mount rather than a bare directory
  (store marker file written at first use, and/or a mountpoint check), and
  refuse to write when the marker is absent.
- Make the root-resolution failure genuinely abort the transaction (see t1283).

Shares a root cause with **t1283**. Fix together, or fix the root-resolution
seam in t1283 and use this task for the mount-liveness check.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1283** id=2026-10-12T18:45:46Z.a5712ced3aa6d85b8d88df3f from=t1283 from_verified=yes at=2026-10-12T18:45:46Z base=4acd6253afec0c49f99c3af88cac46b5290120d7 base_branch=main dirty=yes host=omg16
>
> | t1283 (commit 9d818998f) fixed the root-resolution seam this task's unmount scenario exercises. Tree-relative claims as of that commit:
> | 
> | - Clause 1: dir ops now validate the store root in the op's own shell, so "backend root not found ... (is the share mounted?)" aborts for real under with_attach_lock. No /<2hex>/<62hex> path is derived, and no mkdir/mktemp is attempted at the filesystem root.
> | - Clause 2 (persistent mountpoint dir): every dir op now requires a `.ait-artifact-store` marker in the root. Only the new `ait artifact init-store dir` writes it (run once, with the share mounted). An empty mountpoint directory is refused with "not an initialized artifact store", and nothing is written into it.
> | - Both clauses are pinned by automated tests: tests/test_artifact_dir_backend.sh §E and tests/test_artifact_share_resolution.sh §J.
> | 
> | So this task now looks like a re-verification on the real share. The store must be initialized once with `ait artifact init-store dir` before re-running item #4.
> | 
> | Not covered: a share unmounted mid-operation, between root validation and put's shard write. That is tracked by t1960.

> **✉ note:t1960** id=2026-10-13T08:41:43Z.05cb5fd934af450a272251dd from=t1960 from_verified=yes at=2026-10-13T08:41:43Z base=c491c32c598789519c12c1e247a26e5a2cc30d25 base_branch=main dirty=yes host=omg16
>
> | t1960 (commit 86025fc28) addresses the dir backend's mid-operation unmount window, which t1283's marker guard left open.
> | 
> | - Every dir op except init now enters the store root once (`_artifact_dir_held` in .aitask-scripts/lib/artifact_backends/dir.sh), checks the .ait-artifact-store marker relative to that held cwd, and writes only relative to it.
> | - A share pulled before entry is refused ("not an initialized artifact store").
> | - A share moved after entry: writes land in the held store.
> | - A held store that dies after entry: put fails.
> | - In the simulated cases (mv / rm -rf shims, tests/test_artifact_dir_backend.sh section F), the persistent mountpoint directory received no shard, temp file or blob.
> | - head/get/list refuse, and delete returns 1, rather than answering "absent" or "deleted" for a dead store.
> | 
> | Advisory, my reading only: with t1283 + t1960 in place, what remains of your clause 2 may be just real-mount verification (plain umount gives EBUSY while a cwd is held; umount -l leaves the exposed mountpoint empty). That is now tracked as manual-verification task t1968. Your own re-verification decides whether this task can close.

> **👁 note:read** id=2026-10-13T19:26:01Z.07ffd0659eec65a1b4e27018 by=t1284 at=2026-10-13T19:26:01Z mode=explicit ids=2026-10-12T18:45:46Z.a5712ced3aa6d85b8d88df3f,2026-10-13T08:41:43Z.05cb5fd934af450a272251dd

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-13T20:42:27Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-13T21:32:31Z status=pass attempt=1 type=human
