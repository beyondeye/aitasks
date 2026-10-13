---
priority: low
effort: medium
depends: []
issue_type: manual_verification
status: Ready
labels: [bug]
verifies: [1960]
anchor: 1065
followup_kind: risk_mitigation
created_at: 2026-10-13 11:37
updated_at: 2026-10-13 11:37
---

## Origin

Risk-mitigation ("after") follow-up for t1960, created at Step 8d after implementation landed.

## Risk addressed

real umount / umount -l semantics are argued, not exercised

- The tests simulate an unmount with `mv`/`rm -rf` of the held directory; real `umount` (EBUSY) and `umount -l` (detached fs) are argued, not exercised · severity: medium · → mitigation: dir_backend_real_unmount_probe

## Goal

t1960 made every `dir` artifact backend op (`.aitask-scripts/lib/artifact_backends/dir.sh`) enter the store root once, validate the `.ait-artifact-store` marker through that held cwd, and work relative to it. Its tests pull the share with `mv` / `rm -rf` shims. This task confirms the behaviour on a REAL mount, with root (sudo), on a scratch directory — never a real share:

1. Mount a tmpfs (or loop device) at a persistent mountpoint directory, e.g. `sudo mount -t tmpfs none /mnt/aitstore`, then `ait artifact init-store dir` with `artifacts.backends.dir.path` pointing at it.
2. Start a large `ait artifact create … --backend dir` (or a put slowed with a `mkdir`/`cp` shim). While it holds the cwd, run a plain `sudo umount /mnt/aitstore`. It is expected to fail with EBUSY, and the put completes into the share.
3. Repeat with `sudo umount -l /mnt/aitstore`. The put must not write anything into the now-exposed underlying `/mnt/aitstore` directory (`find /mnt/aitstore -mindepth 1` empty). Note whether the op succeeds, since writes go to the detached filesystem.
4. With the share unmounted, `head` / `get` / `list` / `delete` refuse ("not an initialized artifact store"), and `delete` returns rather than dying.
