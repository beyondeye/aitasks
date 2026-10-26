---
Task: t2151_fix_macos_scan_failed_mktemp_fault_injection.md
Base branch: main
Output branch: main
---

# t2151 — Portable mktemp fault injection for the `scan_failed` driver

## Context

`tests/test_sync_protect_paths.sh` drives every `_protect "<reason>"` branch of
`aitask_sync.sh`. `drive_scan_failed` (line ~241) needs `auto_commit`'s
`dirtyf="$(mktemp)"` (`aitask_sync.sh:1007`) to fail, and does that by running
the sweep with `TMPDIR="$t/no_such_dir"`. That works with GNU mktemp, but BSD
mktemp on macOS falls back to the per-user confstr temp dir when `$TMPDIR` does
not exist, and exits 0. So the branch is never reached on macOS, and the
evidence assertion fails:

    FAIL: scan_failed: the reason actually fired (expected output containing 'nothing swept', got '')

I reproduced this on this machine (Darwin 24.6): `Results: 30 passed, 1 failed (of 31)`.
That run is the pre-fix control.

## Approach

Use a PATH shim `mktemp` that always exits 1, on a PATH prefix for this one
driver only. This works on every platform. It keeps the semantics of the
TMPDIR injection on Linux, where every `mktemp` in the run failed, so no other
reachable path changes.

Facts that make this safe:
- `run_sync` (`tests/lib/sync_fixture.sh:187`) runs `export PATH="$PWD/bin:$PATH"`
  on the PATH it inherits. A caller-side `PATH="$t/failbin:$PATH" run_sync "$t"`
  therefore gives `$t/local/bin:$t/failbin:…`. The fixture's own `bin/`
  (hostname shim only) still wins, and the shim is found before the system
  mktemp.
- `run_sync`'s own prologue (`sync_isolate_git_config`, exports, the stderr
  redirect) calls no `mktemp`.
- `main()` does `_ait_detect_data_worktree`, `_worktree_wedged`, `check_remote`
  and then `auto_commit`, so the first `mktemp` reached is line 1007. Later
  `mktemp` sites (1527, 1653) already return 1 on failure. That is the same
  behaviour as on Linux today.
- The shim goes in a per-driver dir `$t/failbin` that is not in the fixture's
  git tree. `setup_repo` gives each driver its own `$t`, so no other driver
  sees it.
- `bare "mktemp"` at line 1007 is resolved through PATH: there is no absolute
  path and no `command -p`.

## Implementation

**File:** `tests/test_sync_protect_paths.sh`. Only `drive_scan_failed` and its
comment change.

```bash
# mktemp fails: a PATH shim that always exits 1, ahead of the real one.
# NOT `TMPDIR=<missing dir>`: BSD mktemp (macOS) falls back to the per-user
# confstr temp dir when $TMPDIR does not exist and succeeds, so that injection
# never reached the branch there (t2151). run_sync prepends the fixture's own
# bin/ to the PATH it inherits, so the shim dir sits right behind it.
drive_scan_failed() {
    local t; t="$(setup_repo)"
    (cd "$t/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
    mkdir -p "$t/failbin"
    printf '#!/usr/bin/env bash\nexit 1\n' > "$t/failbin/mktemp"
    chmod +x "$t/failbin/mktemp"
    local out; out="$(PATH="$t/failbin:$PATH" run_sync "$t")"
    assert_usable_stdout "scan_failed" "$out"
    assert_reason_fired "scan_failed" "$t" "could not allocate a scratch file"
}
```

Keep both assertions, but tighten the evidence fragment. `scan_failed` has two
sites that both end in "— nothing swept": the mktemp one (1007) and the
`git status` one (1015). The old fragment could not tell which branch fired.
"could not allocate a scratch file" names the branch this seam drives.

The pre-existing uncommitted change to `tests/test_bounded_run.py` in the
working tree is not part of this task. Leave it untouched and keep it out of
the commit.

## Verification

1. Pre-fix control (already run, macOS): `bash tests/test_sync_protect_paths.sh`
   gives `30 passed, 1 failed (of 31)`, with the scan_failed evidence assertion
   failing.
2. After the fix: `bash tests/test_sync_protect_paths.sh`. Expect
   `0 failed`, and a passing `scan_failed` section (the `live_lock` SKIP line
   from t2146 is expected on macOS and is not counted).
3. Control for the tightened fragment: run the fixed driver with the old
   TMPDIR injection on macOS and confirm it still FAILS. That shows the new
   assertion is not vacuous. Run it from a scratchpad copy, not committed.
4. `shellcheck tests/test_sync_protect_paths.sh` gives no new warnings.

## Step 9 (Post-Implementation)

Current-branch mode: commit the code (`test: … (t2151)`) and the plan
separately, then archive via the standard Step 9 flow.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** `drive_scan_failed` in `tests/test_sync_protect_paths.sh` now injects the mktemp failure with a PATH shim (`$t/failbin/mktemp`, `exit 1`) passed as `PATH="$t/failbin:$PATH" run_sync "$t"`, replacing `TMPDIR=<missing dir>`. The evidence fragment was tightened from "nothing swept" to "could not allocate a scratch file". Implemented as planned.
- **Deviations from plan:** None in the change. The commit scope deviated: a concurrent session had an unrelated uncommitted `live_lock` hunk (strong `bsdinfo` token on macOS) in the same file, plus edits to ~11 other files. With the user's approval, only the `drive_scan_failed` hunk was staged (`git apply --cached`) and committed. The other session's hunk was left untouched in the working tree.
- **Issues encountered:** None in the fix. Verified on macOS (Darwin 24.6): pre-fix `30 passed, 1 failed (of 31)`; post-fix `31 passed, 0 failed (of 31)`. Control: the tightened fragment with the old TMPDIR injection still FAILS (`30 passed, 1 failed`), so the assertion is not vacuous. shellcheck shows only the pre-existing SC1091 source-following infos.
- **Key decisions:** An unconditionally failing shim, rather than one that fails only the first call. It reproduces the Linux semantics of the old injection (every `mktemp` in the run fails), so no other reachable path changes. The shim dir lives outside the fixture's git tree, and `setup_repo` scopes it to this driver's `$t`.
- **Upstream defects identified:** None
