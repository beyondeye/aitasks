---
priority: medium
effort: low
depends: [t695_2]
issue_type: refactor
status: Implementing
labels: [ait_setup, installation, python]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-28 11:27
updated_at: 2026-04-28 13:24
---

## Context

This is child 3 of t695. After t695_2 creates the venv on top of a modern interpreter, this child exposes that interpreter via a stable symlink at `~/.aitask/bin/python3` and adds `~/.aitask/bin` to PATH.

This is the "fast path" for local setups — once `~/.aitask/bin` is on PATH ahead of `~/.local/bin` and `/usr/bin`, every shebang `#!/usr/bin/env python3` and every `python3` invocation in scripts (including `${PYTHON:-python3}` patterns) automatically resolves to the venv-Python without any per-script changes. t695_4 then completes the migration for scripts that need the helper-based resolver (for remote-sandbox resilience).

## Key Files to Modify

- `.aitask-scripts/aitask_setup.sh` — modify `setup_python_venv()` (add symlink creation after venv build) and `ensure_path_in_profile()` (add `~/.aitask/bin` to PATH).

## Reference Files for Patterns

- `.aitask-scripts/aitask_setup.sh:516+` (`ensure_path_in_profile`) — current PATH management; appends `~/.local/bin` to shell rc files. Pattern to extend.
- `.aitask-scripts/aitask_setup.sh:529-535` — shell profile detection (zsh on macOS, bash on Linux, fallback to `.profile`).
- `.aitask-scripts/aitask_setup.sh:435-511` (`setup_python_venv`) — where to insert the symlink-creation block after the venv pip-install completes.

## Implementation Plan

1. **Symlink creation in `setup_python_venv()`**:
   - At the end of the function, after the `pip install` block succeeds:
     ```bash
     # Expose venv-Python via stable symlinks for shell PATH resolution
     mkdir -p "$HOME/.aitask/bin"
     ln -sf "$VENV_DIR/bin/python" "$HOME/.aitask/bin/python3"
     ln -sf "$VENV_DIR/bin/python" "$HOME/.aitask/bin/python"
     info "Created framework Python symlinks at ~/.aitask/bin/python3 (and python)."
     ```
   - Use `ln -sf` (force overwrite) so re-running setup updates symlinks if the venv path changed.

2. **PATH integration in `ensure_path_in_profile()`**:
   - Currently the function adds `~/.local/bin` to PATH. Extend it to also add `~/.aitask/bin` BEFORE `~/.local/bin` so framework-resolved Python wins over system Python.
   - The exact PATH update pattern depends on the existing implementation. Read the current function and extend it. Two common approaches:
     - **Approach A — append both with explicit ordering**: write a single `export PATH="$HOME/.aitask/bin:$HOME/.local/bin:$PATH"` block to the shell rc.
     - **Approach B — separate idempotent blocks**: each block grep-checks the rc file for its specific PATH entry before appending.
   - Match whichever style the existing function uses. If it currently writes a single `# aitasks PATH` marker block, extend that block to include the new entry.
   - Idempotency: re-running setup must not duplicate the entry. The existing code already does this for `~/.local/bin` — extend the same guard.

3. **One-line user-facing notice** after the symlinks + PATH update are in place:
   ```bash
   info "Reload your shell or run: export PATH=\"\$HOME/.aitask/bin:\$PATH\" to use the framework Python."
   ```
   Only print this on first install (when the rc file was actually modified, not on idempotent re-runs). Re-use whatever first-run signal the existing function uses.

4. **Test**:
   - Add to `tests/test_setup_python_install.sh` (created in t695_2) or a new test:
     - After `ait setup`, assert:
       - `[[ -L "$HOME/.aitask/bin/python3" ]]` and `readlink "$HOME/.aitask/bin/python3"` matches `~/.aitask/venv/bin/python`.
       - `~/.aitask/bin/python3 -V` returns the venv-Python version.
       - `grep -q '/.aitask/bin' ~/.zshrc` (or whichever profile is detected) succeeds.
       - Re-running `ait setup` does not duplicate the PATH line.

## Verification Steps

- `bash tests/test_setup_python_install.sh` (or whatever test was added) passes.
- `shellcheck .aitask-scripts/aitask_setup.sh` clean.
- After running setup in a fresh sandbox, `which python3` (with `~/.aitask/bin` exported to PATH) resolves to the framework symlink.
- Open a fresh shell after setup and confirm `python3 -c "import linkify_it"` succeeds without sourcing the venv manually.

## Dependencies

- t695_2 must be in place — this child reads from `$VENV_DIR/bin/python` which exists only after t695_2 builds the venv on the modern interpreter.

## Notes for sibling tasks

- t695_4 will refactor scripts to source `lib/python_resolve.sh`. After this child lands, those scripts may not even need the helper for the LOCAL case (PATH symlink is enough), but they still need the helper for the REMOTE case (where ~/.aitask/ doesn't exist). So the helper-based migration in t695_4 is still required.
- The symlink targets `$VENV_DIR/bin/python` (not `bin/python3`) intentionally — `python -m venv` creates `python` as the canonical interpreter and `python3` as a symlink to it; pointing our framework symlink at `python` follows the same convention.
