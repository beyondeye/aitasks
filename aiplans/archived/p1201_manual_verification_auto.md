# Plan: Auto-execution of manual verification for t1201

**Task:** t1201 — Manual verification carry-over: guard install create_data_dirs against dangling data symlink
**Verifies:** t1193
**Type:** manual_verification (auto-execution, autonomous strategy)
**Working directory:** /home/ddt/Work/aitasks (current branch, profile `fast`)
**Date:** 2026-07-21

## Execution Log

### Item 1 — Run `bash tests/test_install_create_data_dirs.sh` on macOS

- **Item text:** Run `bash tests/test_install_create_data_dirs.sh` on macOS (carried over from t1199, previously deferred: requires a macOS/BSD host).
- **Approach:** Not automatable on this host (Linux only) → static portability audit + Linux baseline run, then defer.
- **Action run:**
  - `bash tests/test_install_create_data_dirs.sh`
  - `grep -nE 'mapfile|readarray|declare -A|readlink -f|realpath|stat -c|grep -P|sed -i|timeout ' tests/test_install_create_data_dirs.sh tests/lib/asserts.sh`
  - same grep over `install.sh` lines 337-405 (`ensure_data_root` / `create_data_dirs`)
  - `shellcheck -s bash tests/test_install_create_data_dirs.sh`
- **Output (trimmed):**
  - `Results: 40 passed, 0 failed` on Linux.
  - No bash-4-only constructs (`mapfile`, `readarray`, `declare -A`, case-conversion expansions) in the test, `tests/lib/asserts.sh`, or the guard → runs under macOS system bash 3.2.
  - No GNU-only tool flags (`readlink -f`, `stat -c`, `sed -i`, `grep -P`, `timeout`) anywhere in the test or the guard; `ensure_data_root` uses only plain `readlink`, `mkdir -p`, `rm -f`, and `git`.
  - `shellcheck -s bash` clean apart from SC1091 (unfollowed source).
- **Residual risk (the only OS-dependent assumption):** Test 3's negative control asserts that an unguarded `mkdir -p` through a dangling symlink exits non-zero. BSD `mkdir(1)`'s `build()` does `stat()` → `ENOENT` → `mkdir()` → `EEXIST` → error, so the same failure is expected on macOS, but this was not executed on a real host.
- **Verdict:** skip at the interactive checkpoint — needs a macOS/BSD host. Moved to low-priority follow-up **t1206** (`aitasks/t1206_run_install_create_data_dirs_test_on_macos.md`), which carries the item plus these audit findings, rather than being dropped.

### Item 2 — Real branch-mode recovery via `ait upgrade`

- **Item text:** On an actual branch-mode project, `rm -rf .aitask-data`, then run `ait upgrade`. Expect the hard error naming `git worktree prune && git worktree add .aitask-data aitask-data`, and `aitasks`/`aiplans` still symlinks (no real directory created in their place).
- **Approach:** CLI invocation against a genuine, framework-created branch-mode project fabricated in scratch (previously deferred in t1199 only because no installed branch-mode project existed).
- **Action run:**
  1. Built a local tarball from the repo (`.aitask-scripts`, `ait`, `seed`, `packaging`) and installed it into a fresh git repo:
     `bash install.sh --dir <scratch>/proj --local-tarball <scratch>/ait.tar.gz`
  2. `./ait setup` (non-interactive) in that project → real branch mode: `.aitask-data/` worktree on the `aitask-data` orphan branch + `aitasks -> .aitask-data/aitasks`, `aiplans -> .aitask-data/aiplans`. (Setup later exited 1 on a sandboxed-HOME `uv python install` step — unrelated to and after the branch-mode setup.)
  3. `rm -rf .aitask-data` → both symlinks now dangle.
  4. **Negative control (literal entry point):** `./ait upgrade 0.27.0` — downloads and runs the pre-fix v0.27.0 installer.
  5. **Fixed path:** `bash install.sh --force --dir <scratch>/proj` — the exact command `aitask_upgrade.sh:152` runs after downloading the installer.
  6. **Recovery:** `git worktree prune && git worktree add .aitask-data aitask-data`, then re-ran the fixed installer.
- **Output (trimmed):**
  - Step 4 (pre-fix, rc=1): `mkdir: cannot create directory '<proj>/aitasks': File exists` — the original opaque abort, reproduced end-to-end through a literal `ait upgrade` on a real branch-mode project.
  - Step 5 (fixed, rc=1 by design):
    ```
    [ait] Error: <proj>/aitasks points at the aitask-data worktree, but .aitask-data/ is missing or unusable.
         Restore it, then re-run the install:
           git worktree prune && git worktree add .aitask-data aitask-data
    ```
    `aitasks` and `aiplans` both still symlinks pointing at `.aitask-data/...`; no real directory created in their place.
  - Step 6: recovery command succeeded, re-run of the installer exited 0 with zero `Error` lines, symlink preserved, and `.aitask-data/aitasks/metadata/` materialized on the data branch — the named recovery is actionable, not just descriptive.
- **Caveat:** `ait upgrade` could not fetch the *fixed* installer because the fix is unreleased (installed `0.28.0` == latest release `v0.28.0`, so the upgrade short-circuits at "Already up to date"). The fixed leg therefore used the identical post-download command line with the repo's local `install.sh`.
- **Verdict:** pass.

## Cleanup

- Scratch tree `<scratchpad>/av_1201/` (staging, tarball, `proj` git repo with its `.aitask-data` worktree, isolated `home`) — removed after execution.
- No tmux sessions created. No files outside the scratch tree and this task's checklist were mutated (`HOME` was redirected into the scratch tree so the installs never touched the real `~/.aitask`, `~/.local/bin`, or `~/.bashrc`).
