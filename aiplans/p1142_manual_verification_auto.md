---
Task: t1142_manual_verification_dir_backend_real_mount.md
Worktree: (none — profile 'fast': worked on current branch)
Branch: main
Base branch: main
Output branch: main
---

# t1142 — Manual verification: dir backend against a real mount (auto-execution record)

Retroactive record of the autonomous auto-verification run (strategy:
`autonomous`, whole checklist) for the `dir` artifact backend introduced in
t1076_3.

## Environment

No NAS, USB, or network share was attached to this machine, and no FUSE
network filesystem was available (`sshfs`, `bindfs`, `rclone`, `gocryptfs` all
absent; no local `sshd`). A **real kernel mount** was constructed instead:

```bash
dd if=/dev/zero of=share.img bs=1M count=64
mkfs.ext4 -L aitshare -O ^has_journal -d seed/ share.img   # seed/ contains store/, owned by uid 1000
udisksctl loop-setup -f share.img       # -> /dev/loop0
udisksctl mount -b /dev/loop0           # -> /run/media/ddt/aitshare
```

Store root: `/run/media/ddt/aitshare/store`, registered as
`artifacts.backends.dir.path` in `aitasks/metadata/project_config.yaml`
(temporary; removed at end of run).

**Approximation, stated honestly:** this is a genuine, separately-mounted ext4
filesystem (`stat -c %d` → 1792 vs 58 for `/home`), so mount/unmount semantics
and the cross-filesystem copy boundary are real. It is **not** a network share,
so latency, partial-read, and network-dropout behavior were not exercised. One
mount-shape difference mattered and is called out under Item 4: udisks *removes*
`/run/media/<user>/<label>` on unmount, whereas an fstab/NAS mountpoint
directory persists. The persistent-mountpoint case was reproduced separately
with an empty directory at the configured path — behaviorally identical, since
the adapter's only root check is `[[ -d "$ARTIFACT_DIR_ROOT" ]]`.

Checkout B (Item 2) was a fresh `git clone` of the repo at a distinct path with
its own `aitask-data` worktree, carrying the manifest and project config but no
blobs — the "another user/path on one machine" fallback the checklist permits.

## Execution Log

### Item 1 — Mount a real share and register it as the dir backend

- **Item text:** Mount a real share (NAS / USB / network mount) and register it as the dir backend: `artifacts.backends.dir.path` in `aitasks/metadata/project_config.yaml`
- **Approach:** CLI invocation + file inspection against the loop mount described above.
- **Action run:** `udisksctl loop-setup/mount`; appended the `artifacts:` block to `project_config.yaml`; `python3 .aitask-scripts/lib/artifact_registry.py … backend-env dir`; `./ait artifact create 1142 v1.html --kind report --backend dir`.
- **Output (trimmed):**
  - `ARTIFACT_DIR_ROOT=/run/media/ddt/aitshare/store` (rc 0)
  - `Created artifact art:t1142-report (v1 sha256:943de0ae…) on t1142`
  - Store: `/run/media/ddt/aitshare/store/94/3de0ae61…` — content-addressed shard on the share.
  - Manifest `artifacts/manifests/t1142-report.json` records `"backend": "dir"`; the task frontmatter carries only the `art:t1142-report` handle.
- **Verdict:** pass

### Item 2 — Cross-checkout resolution with a cleared cache

- **Item text:** From checkout A, create an artifact on the dir backend; from a second DISTINCT checkout/environment with only the project config, clear `~/.cache/ait/artifacts` and resolve the handle — confirm fetch + cache + hash verify.
- **Approach:** CLI invocation from a second clone, plus two negative controls to prove the hash verification is real rather than incidentally satisfied.
- **Action run:**
  - `git clone` → checkout B; `git worktree add .aitask-data aitask-data`; symlinked `aitasks`/`aiplans`; wrote only the `artifacts:` config block into B's `project_config.yaml`.
  - Moved `~/.cache/ait/artifacts` aside (0 entries), then `./ait artifact get art:t1142-report --out fetchedB.html` from B.
  - Negative control A: overwrote the cache entry with `TAMPERED`, re-ran `get`.
  - Negative control B: overwrote the **store blob** on the share, cleared the cache, re-ran `get`.
- **Output (trimmed):**
  - Fetch succeeded; output sha256 `943de0ae…` matches; cache filled as a **regular file** (correct for a non-`local` backend — `local` would symlink to the worktree blob).
  - Control A: `Warning: artifact_resolve: corrupted cache entry … — re-fetching from backend`; cache re-healed to the correct hash; rc 0.
  - Control B: `Error: artifact_resolve: backend returned wrong bytes … (bad cache entry removed)`; rc 1; no cache entry left behind.
- **Verdict:** pass

### Item 3 — Same-absolute-path mount assumption

- **Item text:** Confirm the same-absolute-path mount assumption holds or fails clearly: with the share mounted at a DIFFERENT path than config says, operations must die actionably (not corrupt or invent a store).
- **Approach:** CLI invocation with the share mounted at `/run/media/ddt/aitshare` and the config pointing elsewhere, in two variants.
- **Action run / output (trimmed):**
  - **3a — configured path does not exist** (`/mnt/aitshare_expected/store`):
    ```
    Error: artifact_dir: backend root not found: /mnt/aitshare_expected/store (is the share mounted?)
    Error: artifact_dir: backend root not found: /mnt/aitshare_expected/store (is the share mounted?)
    mkdir: cannot create directory '/34': Permission denied
    mktemp: failed to create file via template '/34/.put.XXXXXX': No such file or directory
    Error: artifact_dir_put: mktemp failed in /34   (rc 1)
    ```
    `_artifact_dir_root`'s `die` runs inside a command substitution under
    `with_attach_lock`'s errexit-suppressed call tree, so it prints but does not
    abort. The empty root makes `_artifact_dir_blob_path` emit `/<2hex>/<62hex>` —
    the code then attempts to build a blob store **at the filesystem root**. Only
    `/` being unwritable stopped it. The final user-visible error names `/34`, not
    the real cause.
  - **3b — configured path exists but is not the share** (empty directory):
    ```
    Created artifact art:t1142-report3b (v1 sha256:1834e867…) on t1142   (rc 0)
    <dir>/18/34e86792…      # blob written outside the share
    ```
    Exit 0, manifest committed claiming `"backend": "dir"`, blob written to a
    non-share directory. Any other checkout resolving that handle gets
    `blob not found`. The adapter's only root check is `[[ -d … ]]`.
- **Verdict:** **fail** → follow-up **t1283**

### Item 4 — Unmounted share fails closed

- **Item text:** Unmount the share and confirm operations fail closed with "is the share mounted?" — nothing is written into the empty mountpoint dir.
- **Approach:** `udisksctl unmount` then CLI invocation; plus the persistent-mountpoint reproduction (see Environment).
- **Action run / output (trimmed):**
  - After unmount, `create` emits `Error: artifact_dir: backend root not found: /run/media/ddt/aitshare/store (is the share mounted?)` and exits 1 — **message clause satisfied**. But the same swallowed-`die` path as 3a follows: `mkdir: cannot create directory '/d0'`, `mktemp failed in /d0`. The failure is not *closed*; it is a write attempt at `/` that only permissions blocked.
  - `get` after unmount: root-not-found error, then `blob not found for sha256:943de0ae… (cache miss and backend miss)`, rc 1. Correct.
  - Transaction rollback after the failed `create` was clean: no stray manifest, no task-frontmatter entry, no leaked local blob.
  - **"nothing is written into the empty mountpoint dir" fails** for a persistent mountpoint — see item 3b: blobs land inside the empty directory and the command reports success. udisks removes its mountpoint on unmount, which is why this setup cannot show it directly.
- **Verdict:** **fail** → follow-up **t1284**

### Item 5 — `move` local↔dir across the real mount

- **Item text:** Run `ait artifact move` local→dir and back against the real mount; confirm atomic put across the mount boundary (no `.put.*` residue in the store, manifest-only commits, source blobs intact).
- **Approach:** CLI invocation on a two-version artifact created on `local`, plus a corruption negative control.
- **Action run / output (trimmed):**
  - `create --backend local` + `update` → versions `97d06ff8…` (v1) and `e7a919ab…` (current).
  - `move --to dir`: `2 version(s) copied; source blobs on 'local' were NOT deleted`. Both blobs present in the share; **0** `.put.*` files; both local source blobs intact.
  - Commit shape: `artifacts/manifests/t1142-movetest.json | 4 ++--` — **manifest-only**, no blob paths.
  - `move --to local`: same manifest-only commit shape; dir-side source blobs left intact; `get` after clearing the cache returned the correct v2 bytes.
  - Negative control: corrupted the store entry for `e7a919ab…`, re-ran `move --to dir` → `Warning: artifact_dir_put: corrupt store entry … — repairing with verified bytes`; blob restored to the correct hash; still 0 `.put.*` residue.
  - Atomicity confirmed structurally: the staging `mktemp` lives in the destination shard directory (`stat -c %d` → 1792, the store's filesystem), so the final `mv` is a same-filesystem rename; the cross-boundary copy is the `cp` into the staged temp, which is hash-verified before install.
- **Verdict:** pass

## Cleanup

All performed at the end of the run:

- `ait artifact rm` for `art:t1142-report` and `art:t1142-movetest` (test artifacts); leftover local blobs removed from `.aitask-data/attachments/blobs/` and the empty `artifacts:` frontmatter key stripped from the task file (see Upstream defects).
- Temporary `artifacts:` block removed from `aitasks/metadata/project_config.yaml`; verified byte-identical to the pre-run backup.
- `udisksctl unmount` + `loop-delete`; `share.img`, the mkfs seed dir, the simulated mountpoint dir, and checkout B deleted from the scratchpad.
- `~/.cache/ait/artifacts` restored from backup (41 entries, as before the run).

## Final Implementation Notes

- **Actual work done:** All 5 checklist items reached a terminal state — 3 pass, 2 fail. No production code was changed; this task is verification only. Two follow-up bug tasks were created from the failures (t1283, t1284), each enriched with the reproduction, the exact command output, the root-cause analysis, and a suggested direction.
- **Deviations from plan:** The checklist assumes a real NAS/USB/network share. None was available, so a udisks-mounted ext4 loop image stood in — a real kernel mount on a distinct filesystem, but not a network share. The mount-shape difference (udisks removes its mountpoint on unmount) was worked around by reproducing the persistent-mountpoint case with a plain empty directory, which is behaviorally identical for this adapter. Both approximations are stated above rather than papered over.
- **Issues encountered:** udisks mounts ext4 root-owned, so the image was pre-seeded via `mkfs.ext4 -d` with a `store/` subdirectory owned by uid 1000 — which also matches the realistic "store is a subdirectory of the share" layout.
- **Key decisions:** Every passing item was backed by a negative control (tampered cache entry, tampered store blob, corrupted store entry during `put`), so a pass reflects verification that actually discriminates rather than a command that merely exited 0.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/artifact_backends/dir.sh:29-36 — _artifact_dir_root's die is swallowed inside the $(…) in _artifact_dir_blob_path under with_attach_lock's errexit-suppressed call tree; the empty root yields /<2hex>/<62hex> and the code attempts to create a blob store at the filesystem root` (filed as t1283)
  - `.aitask-scripts/lib/artifact_backends/dir.sh:29-33 — the root check is [[ -d ]] only, so any existing directory at the configured path is silently accepted as the store; blobs are written outside the share and the command exits 0` (filed as t1284)
  - `.aitask-scripts/aitask_artifact.sh:461 — ait artifact rm leaves an empty artifacts: key in the task frontmatter after removing the last artifact, instead of dropping the key`
  - `.aitask-scripts/aitask_artifact.sh:461 — ait artifact rm reports "0 orphan blob(s) swept" and leaves git-tracked local blobs behind when the manifest's current backend is not local, even though the blobs originated on local (adjacent to the known cross-backend reaping gap in t1135)`
