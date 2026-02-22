---
Task: t206_fix_install_global_shim_path.md
Created by: aitask-wrap (retroactive documentation)
---

## Summary

Fixed the `ait` command not being found after running `curl -fsSL .../install.sh | bash` on macOS. The root cause was a chicken-and-egg problem: `install.sh` told users to run `ait setup`, but the global shim (`~/.local/bin/ait`) was only installed by `ait setup` itself. Additionally, `~/.local/bin` is not in PATH by default on macOS.

## Files Modified

- **aiscripts/aitask_setup.sh** — Added `ensure_path_in_profile()` function (~40 lines) that idempotently detects the user's shell profile (`~/.zshrc` on macOS/zsh, `~/.bashrc` on bash, `~/.profile` fallback) and appends `export PATH="$HOME/.local/bin:$PATH"` if not already present. Updated `install_global_shim()` to call this function instead of only warning about PATH.

- **install.sh** — After file extraction and `set_permissions`, now sources `aitask_setup.sh --source-only` and calls `install_global_shim()` to create the shim and update the shell profile. No code duplication — reuses the function from setup. Updated final instructions to mention shell restart and `./ait setup` as an immediate fallback.

- **README.md** — Updated post-install instructions (line 91) to mention restarting the shell and the `./ait setup` alternative.

## Probable User Intent

After a fresh curl-pipe install on macOS, the user expected `ait` to be available as a global command. The framework should handle PATH setup automatically during installation, not defer it to a command that itself requires PATH to be set up.

## Final Implementation Notes

- **Actual work done:** Added `ensure_path_in_profile()` to `aitask_setup.sh`, wired it into both `install.sh` (via `--source-only` sourcing) and `ait setup`. Updated README.
- **Deviations from plan:** N/A (retroactive wrap — no prior plan existed)
- **Issues encountered:** N/A (changes were already made before wrapping)
- **Key decisions:** Avoided code duplication by having `install.sh` source `aitask_setup.sh --source-only` (which was already supported) rather than duplicating the shim heredoc. The `ensure_path_in_profile()` function uses broad idempotency (`grep -qF '.local/bin'`) to prevent duplicates regardless of how the PATH line was formatted.
