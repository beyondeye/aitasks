---
Task: t530_fix_shim_active_guard_leak.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# Plan: Fix `_AIT_SHIM_ACTIVE` guard leak through exec

## Context

The global `ait` shim installed by `install_global_shim()` in
`.aitask-scripts/aitask_setup.sh` sets `_AIT_SHIM_ACTIVE=1` as a recursion
guard, then `exec`s the project-local `ait` dispatcher if one is found. The
variable is `export`ed, so it leaks into every subprocess the project-local
dispatcher launches — including `tmux new-session` panes.

That broke `ait ide`: `aitask_ide.sh:100` does
`exec tmux new-session -s aitasks -n monitor 'ait monitor'`; the pane shell
inherits `_AIT_SHIM_ACTIVE=1`, so when it runs `ait monitor` it hits the
guard and exits with "ait dispatcher not found in any parent directory".
The only window exits, the session dies, and the user sees a brief flash of
the tmux status bar before the prompt returns.

The sibling "ait setup bootstrap" path at `aitask_setup.sh:639` already
`unset _AIT_SHIM_ACTIVE`s before its `exec`. Only the primary walk-up path
(around line 575) was missed.

The existing `tests/test_global_shim.sh` didn't catch this because line 9
clears `_AIT_SHIM_ACTIVE` at the top of the file, and no downstream test
inspects the child's environment after the shim dispatches.

## Fix

### Change 1 — `.aitask-scripts/aitask_setup.sh` (walk-up exec path)

Add `unset _AIT_SHIM_ACTIVE` immediately before the `exec "$dir/ait" "$@"`
inside the walk-up loop of the shim heredoc.

**Current (lines 572–578):**
```bash
dir="$PWD"
while [[ "$dir" != "/" ]]; do
    if [[ -x "$dir/ait" && -d "$dir/.aitask-scripts" ]]; then
        exec "$dir/ait" "$@"
    fi
    dir="$(dirname "$dir")"
done
```

**After:**
```bash
dir="$PWD"
while [[ "$dir" != "/" ]]; do
    if [[ -x "$dir/ait" && -d "$dir/.aitask-scripts" ]]; then
        unset _AIT_SHIM_ACTIVE
        exec "$dir/ait" "$@"
    fi
    dir="$(dirname "$dir")"
done
```

That's the only code change. The bootstrap path at line 639 is already
correct. The in-process recursion guard (lines 565–568) still fires when
the shim is re-entered within the same process (e.g. PATH loop before a
project has been found), so the guard's original purpose is preserved.

### Change 2 — `tests/test_global_shim.sh` (regression test)

Add a new test case that verifies the guard does NOT leak into the
project-local `ait` process. Pattern follows existing tests 5/6:

- Create a temp "project" dir with `.aitask-scripts/` and a fake local
  `ait` that writes a count derived from `env` to a marker file.
- Invoke the shim from inside the temp project.
- Assert the marker file contents show `_AIT_SHIM_ACTIVE` is NOT set in
  the child environment.

Concrete sketch:

```bash
# --- Test 9: Walk-up exec clears _AIT_SHIM_ACTIVE before dispatching ---
echo "--- Test 9: Walk-up exec unsets shim guard ---"

TMPDIR_9="$(mktemp -d)"
SHIM_PATH_9="$(generate_test_shim "$TMPDIR_9/shimbin")"

mkdir -p "$TMPDIR_9/project/.aitask-scripts"
cat > "$TMPDIR_9/project/ait" << 'EOF'
#!/usr/bin/env bash
# Record whether _AIT_SHIM_ACTIVE leaked into this child process.
env | grep -c '^_AIT_SHIM_ACTIVE=' > "$(dirname "$0")/guard_count"
echo "local ait called"
EOF
chmod +x "$TMPDIR_9/project/ait"

output=$(cd "$TMPDIR_9/project" && "$SHIM_PATH_9" ls 2>&1)

guard_count="$(cat "$TMPDIR_9/project/guard_count" 2>/dev/null | tr -d ' ')"
assert_eq "Guard variable not leaked to child ait" "0" "$guard_count"

rm -rf "$TMPDIR_9"
```

Notes on portability (per CLAUDE.md conventions):
- `wc -l` / `grep -c` output may be padded on macOS — strip with `tr -d ' '`
  before comparing as a string.
- `env | grep -c '^_AIT_SHIM_ACTIVE='` uses only BRE — no PCRE or lookaround.
- `mktemp -d` is portable; template suffixes aren't needed here.

No change needed to the existing line-9 `unset _AIT_SHIM_ACTIVE` — it
protects the test *runner* from a leaked parent env, which is a separate
concern from what this new test verifies about the shim's *own* child
process.

### Change 3 — Re-installation note (no code change)

Users who already installed the shim before this fix will still have the
buggy shim in `~/.local/bin/ait`. The changelog for this fix should
mention that existing users need to re-run `ait setup` (or
`install_global_shim`) to regenerate the shim. No in-repo action required
for this task beyond flagging it to the user at hand-off time — the
changelog is normally produced by `/aitask-changelog` during release.

## Files touched

- `.aitask-scripts/aitask_setup.sh` — add one line inside the shim heredoc
- `tests/test_global_shim.sh` — add Test 9 (regression test)

## Verification

1. `bash -n .aitask-scripts/aitask_setup.sh` — syntax check the setup script.
2. `bash tests/test_global_shim.sh` — all existing tests should still pass,
   plus the new Test 9 should pass.
3. Manual local reproduction:
   - Regenerate the shim by running `./.aitask-scripts/aitask_setup.sh`
     (or by hand-patching `~/.local/bin/ait`).
   - From a fresh terminal, run `ait ide` — it should create the `aitasks`
     tmux session, attach, and show the monitor TUI instead of flashing
     and exiting.
   - Inside the tmux session, open another window and run `ait ls` — it
     should dispatch normally via the shim (confirms guard is properly
     cleared for in-tmux use).

## Step 9 (Post-Implementation)

After review and approval in Step 8, the shared task-workflow will handle:
- Committing the code changes (`.aitask-scripts/aitask_setup.sh` and
  `tests/test_global_shim.sh`) with message
  `bug: Unset _AIT_SHIM_ACTIVE before shim walk-up exec (t530)`.
- Committing this plan file via `./ait git` with message
  `ait: Update plan for t530`.
- Running `./.aitask-scripts/aitask_archive.sh 530` to archive task + plan.
- Pushing via `./ait git push`.

## Final Implementation Notes

- **Actual work done:** Added a single `unset _AIT_SHIM_ACTIVE` line inside
  the shim's walk-up loop in `.aitask-scripts/aitask_setup.sh` (just before
  `exec "$dir/ait" "$@"`), and added `Test 9` to `tests/test_global_shim.sh`
  that asserts the project-local `ait` receives zero `_AIT_SHIM_ACTIVE`
  entries in its env. All 16 tests pass (was 15 before).
- **Deviations from plan:** None. Implementation matches the plan exactly.
- **Issues encountered:** During Step 8 review the user noted that
  `ait ide` was still failing after the code fix. Root cause: the installed
  shim at `~/.local/bin/ait` was generated before this fix and still
  contained the buggy walk-up loop. Fixed by regenerating it with
  `source .aitask-scripts/aitask_setup.sh --source-only && install_global_shim`.
  Verified the regenerated shim contains the `unset` line at line 15.
  The current Claude Code shell still has `_AIT_SHIM_ACTIVE=1` leaked from
  the original pre-fix invocation, so `ait ls` from this shell still trips
  the guard — but `env -u _AIT_SHIM_ACTIVE ait ls` (fresh-shell simulation)
  dispatches correctly, and any fresh terminal will work.
- **Key decisions:**
  - Placed `unset _AIT_SHIM_ACTIVE` immediately before `exec` (not at loop
    entry) so the in-process recursion guard still fires if the walk-up
    fails to find a project and re-entry ever happens.
  - Used `env | grep -c '^_AIT_SHIM_ACTIVE='` in the regression test (not
    `[[ -v _AIT_SHIM_ACTIVE ]]`) to avoid bash-version/portability issues
    and to match the style of surrounding tests.
  - Stripped `grep -c` output with `tr -d ' '` per CLAUDE.md's macOS `wc
    -l`/`grep -c` portability note.
- **User-facing follow-up:** Existing users who installed the shim before
  this fix need to re-run `ait setup` (or `install_global_shim`) to
  regenerate it. This should be mentioned in the changelog entry for the
  next release.
