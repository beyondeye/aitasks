---
Task: t1206_run_install_create_data_dirs_test_on_macos.md
Worktree: (current branch — no worktree; profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# Auto-execution record — manual verification of t1206

Strategy: **autonomous** (approach chosen per item at execution time; this file
is the retroactive record of what was actually run).

t1193 added the dangling data-symlink guard (`ensure_data_root`) to
`install.sh`'s `create_data_dirs()`. `tests/test_install_create_data_dirs.sh`
pins it, and t1201 ran that suite green on Linux but had no macOS host, so one
assumption stayed open: **Test 3**, the negative control, asserts that an
*unguarded* `mkdir -p` through a dangling symlink exits non-zero. If BSD `mkdir`
behaved differently, Test 3 would pass vacuously on macOS and stop attributing
Test 2's success to the guard.

This run executed the suite on a real macOS/BSD host and additionally probed the
`mkdir` primitive directly, so the negative control is confirmed non-vacuous
rather than merely green.

## Host

| | |
|---|---|
| OS | macOS 15.7.3 (build 24G419), Darwin 24.6.0, arm64 |
| PATH `bash` | GNU bash 5.3.9(1) (aarch64-apple-darwin24.6.0) |
| system `bash` | GNU bash 3.2.57(1) (arm64-apple-darwin24) |
| `mkdir` | `/bin/mkdir` (BSD userland) |

## Execution Log

### Item 1

- Item text: Run `bash tests/test_install_create_data_dirs.sh` on a macOS/BSD
  host — expect 40/40 pass, and in particular confirm Test 3 (negative control)
  still exits non-zero, i.e. BSD `mkdir -p` also fails through a dangling symlink
- Approach: CLI invocation (run the suite), twice under different bash builds,
  plus a standalone probe of the `mkdir -p` primitive the negative control rests on
- Action run:
  ```bash
  # 1. the suite under PATH bash (5.3.9)
  bash tests/test_install_create_data_dirs.sh; echo "EXIT=$?"

  # 2. the suite under macOS system bash (3.2.57) — closes the bash-3.2 assumption
  /bin/bash tests/test_install_create_data_dirs.sh; echo "EXIT=$?"

  # 3. direct probe of the primitive Test 3 asserts on
  d=$(mktemp -d)
  ln -s "$d/nonexistent_target" "$d/aitasks"
  mkdir -p "$d/aitasks/metadata"; echo "rc=$?"
  ```
- Output (trimmed):
  ```
  # 1. PATH bash 5.3.9
  Results: 40 passed, 0 failed
  EXIT=0

  # 2. system bash 3.2.57
  Results: 40 passed, 0 failed
  EXIT=0

  # 3. primitive probe
  which mkdir: /bin/mkdir
  mkdir: .../mkdirprobe_cgCW3m/aitasks: No such file or directory
  BSD mkdir -p through dangling symlink rc=1
  ```
- Verdict: **pass**

## Findings

1. **40/40 assertions pass on macOS, exit 0** — under both the PATH bash 5.3.9
   the checklist's literal `bash tests/...` invocation picks up, *and* the macOS
   system bash 3.2.57. The second run was not required by the checklist but
   closes t1201's other substitute-evidence assumption (no bash-4-only
   constructs) by execution rather than by inspection.

2. **Test 3 is non-vacuous on BSD.** `mkdir -p` through a dangling symlink exits
   **1** on macOS, so the negative control genuinely discriminates and Test 2
   remains attributable to `ensure_data_root` rather than to `mkdir -p` having
   been harmless all along. This closes the open portability assumption t1206
   was created for.

3. **The failure *mode* differs from t1201's prediction, the exit status does
   not.** t1201 reasoned that BSD `mkdir(1)`'s `build()` would go
   `stat()` → `ENOENT` → `mkdir()` → `EEXIST` and report `File exists`, matching
   GNU. BSD in fact reports **`No such file or directory` (ENOENT)**, not
   `File exists`. Test 3 asserts only a non-zero exit
   (`assert_exit_nonzero_rc`), so it passes on both platforms — but any future
   assertion tightened to match GNU's *message* would be a macOS-only failure.
   Recorded here rather than filed as a follow-up: the current test is correct
   as written, and this is a constraint on future edits, not a present defect.

## Cleanup

- `$SCRATCHPAD/mkdirprobe_*` probe dir — removed (`rm -rf`) at end of the probe.
- Suite logs `$SCRATCHPAD/t1206_bash5.log`, `$SCRATCHPAD/t1206_bash32.log` —
  session scratchpad only, outside the repo; nothing to remove from the tree.
- The suite manages its own fixtures under `mktemp -d` with an `EXIT` trap.
- No tmux sessions were created.
