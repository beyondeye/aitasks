---
Task: t127_intalling_ait_in_new_project.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Auto-bootstrap aitasks via `ait setup` in new projects

## Context

Currently, installing aitasks in a new project requires two steps:
1. `curl -fsSL .../install.sh | bash` (downloads framework files)
2. `ait setup` (installs CLI tools, git config, venv, global shim, permissions)

Once the global shim exists at `~/.local/bin/ait`, users expect `ait setup` to work in any directory. But the shim only walks up the directory tree looking for an existing project — if none is found, it errors out. The goal is to make `ait setup` in a new project directory automatically download and install the framework first, then continue with normal setup.

## Approach

Modify the global shim template in `aitask_setup.sh::install_global_shim()` so that when the directory walk fails and the command is `setup`:
1. Ask user for confirmation (interactive only)
2. Download `install.sh` to a temp file (not piped, so stdin stays on the terminal)
3. Run `bash "$tmpfile" --dir "$PWD"` to install framework files
4. `exec "$PWD/ait" setup` to continue with normal setup

For any other command (`ls`, `create`, etc.), show an improved error suggesting `ait setup`.

## Files Modified

- [x] `aiscripts/aitask_setup.sh` — Updated `install_global_shim()` heredoc (lines 200-282)
- [x] `tests/test_global_shim.sh` — New test file (8 test groups, 15 assertions)

## Key Design Decisions

- **Download to temp file, not pipe**: Preserves terminal interactivity for install.sh prompts
- **`unset _AIT_SHIM_ACTIVE` before exec**: Clears recursion guard so local ait runs normally
- **Check `$1` after directory walk**: Ensures existing projects dispatch normally from subdirectories
- **Only `setup` triggers bootstrap**: Other commands still error — framework install shouldn't happen accidentally
- **Updated fallback error message**: Now suggests `ait setup` as primary path

## Verification

- [x] `bash -n aiscripts/aitask_setup.sh` — syntax check passes
- [x] `bash tests/test_global_shim.sh` — 15/15 tests pass
- [x] `bash tests/test_setup_git.sh` — pre-existing failures in tests 3,5 (unrelated, confirmed same on unmodified code)

## Final Implementation Notes

- **Actual work done:** Modified the global shim heredoc in `aitask_setup.sh::install_global_shim()` to auto-bootstrap aitasks when `ait setup` is run from a directory with no existing installation. Added comprehensive test suite (`tests/test_global_shim.sh`) with 15 assertions covering dispatch, subdirectory lookup, recursion guard, bootstrap flow, and syntax validation.
- **Deviations from plan:** None — implementation matched the plan exactly.
- **Issues encountered:** The test for "user declines bootstrap" required adjustment since piping input makes stdin non-terminal, causing the confirmation prompt to be skipped. Changed the test to verify non-interactive behavior (skips prompt, attempts download) instead.
- **Key decisions:** Chose to download `install.sh` to a temp file rather than piping it, so that `install.sh`'s own interactive prompts work correctly when the user is at a terminal.
- **Activation:** Users need to run `ait setup` once from an existing project to regenerate the global shim with the new bootstrap logic. After that, `ait setup` works from any new project directory.
