---
Task: t1199_manual_verification_guard_install_create_data_dirs_dangling_.md
Worktree: .
Branch: main
Base branch: main
---

## Execution Log

### Item 1

- Item text: Run `bash tests/test_install_create_data_dirs.sh` on macOS and expect 40 passed, 0 failed.
- Approach: CLI test execution plus host inspection.
- Action run: `bash tests/test_install_create_data_dirs.sh` on Linux.
- Output (trimmed): `Results: 40 passed, 0 failed`.
- Verdict: defer — the requested macOS/BSD execution is unavailable; BSD `readlink` and `grep -qE` compatibility was not executed here.

### Item 2

- Item text: Verify missing `.aitask-data` recovery on a branch-mode project through `ait upgrade`.
- Approach: disposable branch-mode fixture and direct guard invocation.
- Action run: created a temporary git repository with an `aitask-data` ref and registered worktree, removed only its temporary `.aitask-data` directory, then ran `create_data_dirs` from the current installer.
- Output (trimmed): exited 1 with `git worktree prune && git worktree add .aitask-data aitask-data`; the dangling `aitasks` symlink remained intact.
- Verdict: defer — the guard behavior is verified, but the literal `ait upgrade` wrapper was not run against an installed branch-mode project.

### Item 3

- Item text: Fresh non-git install with a dangling canonical `aitasks` symlink.
- Approach: genuine release artifact and disposable non-git install directory.
- Action run: downloaded `aitasks-v0.28.0.tar.gz`, created `aitasks -> .aitask-data/aitasks`, then ran `bash install.sh --dir <temp> --local-tarball <release>`.
- Output (trimmed): exit 0; emitted `Replacing dangling symlink ...`; finished with `aitasks installed successfully`; no `not a git repository` output.
- Verdict: pass.

### Item 4

- Item text: Genuine release tarball carries no data-root symlinks, making the guard a no-op.
- Approach: release archive inspection.
- Action run: downloaded `aitasks-v0.28.0.tar.gz` and inspected all 840 archive entries for `aitasks` / `aiplans` symlink entries.
- Output (trimmed): no matching entries.
- Verdict: pass.

## Cleanup

- Removed all `/tmp/aitasks_*_verify_*` fixture directories after each check.
