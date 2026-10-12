---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [bug]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1065
followup_kind: risk_mitigation
created_at: 2026-10-12 21:45
updated_at: 2026-10-12 22:02
---

## Origin

Risk-mitigation ("after") follow-up for t1283, created at Step 8d after implementation landed.

## Risk addressed

concurrent unmount between validation and put's shard write

- Concurrent unmount between validation and `put`'s shard write is not protected · severity: medium · → mitigation: dir_put_concurrent_unmount_guard

## Goal

t1283 made the `dir` artifact backend (`.aitask-scripts/lib/artifact_backends/dir.sh`)
validate its store root at op entry: the root must exist and carry the
`.ait-artifact-store` marker (written by `ait artifact init-store dir`). That
validation is a one-time pathname check. `artifact_dir_put` then works on
absolute paths — `mkdir -p` of the shard dir, `mktemp` of the staging file,
the final `mv` — so if the share is unmounted BETWEEN validation and those
writes, a persistent underlying mountpoint directory receives the shard dir,
the temp file and possibly the blob, even though it carries no marker. The
boundary is documented in the `dir.sh` header comment and in
`aidocs/unified_artifact_design.md` §6.

This task closes that window:

- Keep every filesystem operation of `put` (shard mkdir, temp file, final mv)
  tied to the validated root itself — e.g. hold the validated directory as an
  fd / cwd (a subshell that `cd`s into the validated root once and then uses
  only relative paths), so nothing is re-resolved by pathname after
  validation. Consider whether `get`/`delete`/`list` need the same treatment
  (reads cannot plant data, but a delete against the wrong tree can report a
  false success).
- **Acceptance:** a test that makes the share disappear between validation and
  mutation (e.g. a hook/shim that moves the store away and leaves an empty
  directory at the old path after the root check but before the shard write)
  and shows that **no shard, temp file or final blob** lands in the
  underlying mountpoint directory, and that the op fails with an actionable
  error.
- **Explicitly out:** pathname re-checks of any kind — re-testing the marker,
  or comparing the root's device/inode before the final `mv`. They race the
  same way, and a check placed before `mv` comes after `mkdir`/`mktemp` have
  already written into the underlying directory.
- Keep t1283's contracts: `artifact_dir_delete` returns non-zero rather than
  dying (it runs from rollback hooks inside the EXIT trap); the root is never
  created; tests in `tests/test_artifact_dir_backend.sh` and
  `tests/test_artifact_share_resolution.sh` stay green.
