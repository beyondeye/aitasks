---
Task: t695_3_aitask_bin_symlink_path.md
Parent Task: aitasks/t695_install_python_if_sys_python_old.md
Sibling Tasks: aitasks/t695/t695_1_python_resolve_helper.md, aitasks/t695/t695_2_venv_python_upgrade.md, aitasks/t695/t695_4_refactor_python_callers.md
Archived Sibling Plans: aiplans/archived/p695/p695_*_*.md
Worktree: aiwork/t695_3_aitask_bin_symlink_path
Branch: aitask/t695_3_aitask_bin_symlink_path
Base branch: main
---

# Plan — t695_3: ~/.aitask/bin/python3 symlink + PATH integration

## Context

Third child of t695. After t695_2 builds the venv on a modern interpreter,
this child exposes that interpreter via `~/.aitask/bin/python3` and adds
`~/.aitask/bin` to PATH ahead of `~/.local/bin`. This is the "fast path"
that makes shebang `#!/usr/bin/env python3` and bare `python3` invocations
resolve to the venv-Python on local installs without per-script changes.

The remote-sandbox case is still handled by t695_4's helper-based migration
— the symlink only fixes the local case.

## Files

- `.aitask-scripts/aitask_setup.sh` — modify `setup_python_venv()` (append
  symlink creation block) and `ensure_path_in_profile()` (extend PATH
  block to include `~/.aitask/bin`).

## Implementation Steps

### Step 1 — Symlink creation in `setup_python_venv()`

At the end of the function, after the pip install succeeds:

```bash
# Expose venv-Python via stable symlinks for shell PATH resolution
mkdir -p "$HOME/.aitask/bin"
ln -sf "$VENV_DIR/bin/python" "$HOME/.aitask/bin/python3"
ln -sf "$VENV_DIR/bin/python" "$HOME/.aitask/bin/python"
info "Created framework Python symlinks at ~/.aitask/bin/python3."
```

Use `ln -sf` (force overwrite) so re-running setup updates the symlink
target if `$VENV_DIR/bin/python` changed (e.g., venv recreated on a newer
interpreter).

### Step 2 — Extend `ensure_path_in_profile()`

Read the current implementation first (lines 516+ of `aitask_setup.sh`).
The current function appends `~/.local/bin` to a shell rc file. Two
expected shapes:

**Shape A — single PATH export block**:

```bash
# aitasks PATH (managed by ait setup)
export PATH="$HOME/.local/bin:$PATH"
```

If this is the shape, change to:

```bash
# aitasks PATH (managed by ait setup)
export PATH="$HOME/.aitask/bin:$HOME/.local/bin:$PATH"
```

**Shape B — separate idempotent grep-then-append blocks**:

If this is the shape, add a parallel block for `~/.aitask/bin` placed BEFORE
the `~/.local/bin` block in the rc file (so it ends up earlier in PATH on
subsequent shell loads):

```bash
if ! grep -q '/.aitask/bin' "$rc"; then
  printf '\n# aitasks Python PATH (managed by ait setup)\nexport PATH="$HOME/.aitask/bin:$PATH"\n' >> "$rc"
fi
```

Match whichever shape the existing function uses. The key invariants:
- `~/.aitask/bin` resolves earlier than `~/.local/bin` and earlier than
  system paths.
- Re-running setup is idempotent (no duplicate appends).
- The change is reversible (a one-line block the user can delete).

### Step 3 — First-run notice

After the symlinks + PATH update are in place, print a one-line notice
guiding the user to reload their shell. Re-use the existing first-run
signal in `ensure_path_in_profile()` (e.g., a return code or output flag
indicating the rc was actually modified) — only print the notice on first
modification, not on idempotent re-runs.

```bash
info "Reload your shell or run: source ~/.zshrc (or ~/.bashrc) to use the framework Python."
```

### Step 4 — Test

Extend `tests/test_setup_python_install.sh` (created in t695_2) with new
assertions, OR add a focused `tests/test_aitask_bin_symlink.sh`:

```bash
# After ait setup completes:
[[ -L "$HOME/.aitask/bin/python3" ]]   # symlink exists
[[ -L "$HOME/.aitask/bin/python" ]]
ls -l "$HOME/.aitask/bin/python3" | grep -q ".aitask/venv/bin/python"

# Symlink resolves to a working interpreter
"$HOME/.aitask/bin/python3" -V | grep -E "Python 3\.(1[1-9]|[2-9][0-9])"
"$HOME/.aitask/bin/python3" -c "import linkify_it"

# PATH was updated
profile="$(detect_profile_for_shell)"   # or hardcode based on test env
grep -q '/.aitask/bin' "$profile"

# Idempotency: re-run setup, confirm rc file did not gain a duplicate entry
before="$(grep -c '/.aitask/bin' "$profile")"
./ait setup --yes
after="$(grep -c '/.aitask/bin' "$profile")"
[[ "$before" == "$after" ]]
```

### Step 5 — Verification with shell session

The PATH update only takes effect in NEW shells. Document this in the
plan's Final Implementation Notes for testers.

## Verification

- `bash tests/test_setup_python_install.sh` (or focused test) passes.
- `shellcheck .aitask-scripts/aitask_setup.sh` clean.
- After running setup in a fresh sandbox, `which python3` (in a freshly
  spawned shell) resolves to `~/.aitask/bin/python3`.
- Open a fresh shell after setup and confirm `python3 -c "import
  linkify_it"` succeeds.

## Dependencies / Sequencing

Depends on t695_2 — `$VENV_DIR/bin/python` only exists after t695_2's venv
build succeeds.

## Step 9 — Post-Implementation

Standard archival flow. No special cleanup. Note that the new PATH entry
is sticky in the user's shell rc — that's intentional and is the whole
point of the change.
