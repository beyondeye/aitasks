---
priority: medium
effort: high
depends: [t695_1]
issue_type: refactor
status: Ready
labels: [ait_setup, installation, python]
created_at: 2026-04-28 11:26
updated_at: 2026-04-28 11:26
---

## Context

This is child 2 of t695. Modifies `setup_python_venv()` in `aitask_setup.sh` so that instead of using whatever `python3` happens to be in PATH, it resolves a "modern" Python interpreter (≥3.11 by default), and if none exists, installs one in a strictly user-scoped manner (no sudo, no system-wide changes).

This is the heart of the fix for the user's reported problem: linkify breaks on macOS system Python 3.9. After this child lands, `~/.aitask/venv/` is created on top of a guaranteed-modern interpreter regardless of system Python age.

## Key Files to Modify

- `.aitask-scripts/aitask_setup.sh` — modify `setup_python_venv()` (lines 435-511) and `check_python_version()` (lines 372-432); add new helpers `find_modern_python()` and `install_modern_python()`.

## Reference Files for Patterns

- `.aitask-scripts/aitask_setup.sh:21-69` (`detect_os`) — OS dispatch returns `macos|debian|arch|fedora|wsl|linux-unknown`.
- `.aitask-scripts/aitask_setup.sh:307-365` (`check_bash_version`) — existing macOS brew install pattern with `read -p` confirmation, PATH guidance.
- `.aitask-scripts/aitask_setup.sh:395-428` — existing brew install path inside `check_python_version()`. Reuse / extract.
- `.aitask-scripts/aitask_setup.sh:435-511` (`setup_python_venv`) — current venv creation flow that hardcodes `python_cmd` from the system check.
- `https://github.com/astral-sh/uv` — install via `curl -LsSf https://astral.sh/uv/install.sh | sh` redirected to a framework-managed dir; `uv python install 3.13` fetches a python-build-standalone interpreter.

## Implementation Plan

1. **Add config constant** near the top of `aitask_setup.sh` (just below other constants like `VENV_DIR`):
   ```bash
   AIT_VENV_PYTHON_MIN="${AIT_VENV_PYTHON_MIN:-3.11}"
   AIT_VENV_PYTHON_PREFERRED="${AIT_VENV_PYTHON_PREFERRED:-3.13}"
   ```

2. **Add `find_modern_python <min_version>` helper** (in `aitask_setup.sh`, before `check_python_version`):
   - Iterate candidates: `python3.13`, `python3.12`, `python3.11` (or whatever ≥ min_version, parsed from arg).
   - Also check `~/.aitask/python/<version>/bin/python3` (the uv-installed location) and `~/.aitask/bin/python3` (the symlink, if t695_3 is in place).
   - For each: `command -v $candidate >/dev/null && { echo "$(command -v $candidate)"; return 0; }`.
   - Echo empty if nothing found; return 1.
   - Optionally validate the candidate's reported version meets min_version (defensive — handle cases where `python3.11` is somehow actually 3.9).

3. **Add `install_modern_python` helper** (OS-dispatched):
   - **macOS** (`$OS == "macos"`):
     - Check if `brew` exists. If not, print install instructions for Homebrew and abort.
     - Run `brew install python@$AIT_VENV_PYTHON_PREFERRED` (e.g., `python@3.13`). Match the existing pattern at lines 395-428.
     - After install, verify via `find_modern_python "$AIT_VENV_PYTHON_MIN"`.
   - **Linux** (everything else): strictly local, no sudo.
     - Set `UV_INSTALL_DIR="$HOME/.aitask/uv"`.
     - If `[[ ! -x "$UV_INSTALL_DIR/bin/uv" ]]`, download and install uv:
       ```bash
       curl -LsSf https://astral.sh/uv/install.sh | env \
         UV_INSTALL_DIR="$UV_INSTALL_DIR" \
         INSTALLER_NO_MODIFY_PATH=1 \
         sh
       ```
       (See uv install docs — these env vars redirect the installer.)
     - Run `"$UV_INSTALL_DIR/bin/uv" python install "$AIT_VENV_PYTHON_PREFERRED"`. uv places the interpreter under `~/.local/share/uv/python/cpython-<version>-...` by default.
     - Resolve the installed path via `"$UV_INSTALL_DIR/bin/uv" python find "$AIT_VENV_PYTHON_PREFERRED"`. Symlink it to a stable framework path:
       ```bash
       mkdir -p "$HOME/.aitask/python/$AIT_VENV_PYTHON_PREFERRED/bin"
       ln -sf "$installed_python_path" "$HOME/.aitask/python/$AIT_VENV_PYTHON_PREFERRED/bin/python3"
       ```
     - This stable path is what `find_modern_python` looks for next time.

4. **Modify `setup_python_venv()`**:
   - Replace the current "find python_cmd" preamble with:
     ```bash
     local python_cmd
     python_cmd="$(find_modern_python "$AIT_VENV_PYTHON_MIN")"
     if [[ -z "$python_cmd" ]]; then
       info "No Python ≥$AIT_VENV_PYTHON_MIN found. Installing one (user-scoped)..."
       install_modern_python || die "Failed to install a modern Python interpreter."
       python_cmd="$(find_modern_python "$AIT_VENV_PYTHON_MIN")"
       [[ -z "$python_cmd" ]] && die "Modern Python install completed but interpreter still not found."
     fi
     info "Using Python for venv: $python_cmd ($("$python_cmd" --version))"
     ```
   - Keep the rest of the function (venv creation via `"$python_cmd" -m venv "$VENV_DIR"`, pip install of textual/pyyaml/linkify-it-py/tomli) unchanged.

5. **`check_python_version()`** — leave the 3.9+ floor as-is. It's still needed for the install.sh pre-setup merge step. Consider adding a brief comment that distinguishes "system minimum (3.9 — for bootstrap scripts)" from "venv minimum (`AIT_VENV_PYTHON_MIN` — for TUI deps)".

6. **Test the full install flow** per CLAUDE.md "Test the full install flow for setup helpers" — add `tests/test_setup_python_install.sh`:
   - `bash install.sh --dir /tmp/scratchXY` then `cd /tmp/scratchXY && ./ait setup` (with non-interactive flags / mocked prompts where needed).
   - Verify `~/.aitask/venv/bin/python -V` returns ≥3.11.
   - Verify `~/.aitask/venv/bin/python -c "import linkify_it; import textual"` exits 0.
   - On Linux with old Python: verify `~/.aitask/uv/bin/uv` was downloaded and `~/.aitask/python/3.13/bin/python3` exists.
   - This test may need to be skipped or guarded if `brew` / network is unavailable in the test env — gate with `command -v brew` check on macOS or skip on Linux without network.

## Verification Steps

- `bash tests/test_setup_python_install.sh` passes on macOS and Linux test hosts.
- `shellcheck .aitask-scripts/aitask_setup.sh` clean.
- Manual: on a macOS host with system Python 3.9, run `ait setup` and verify the brew flow triggers.
- Manual: on a Linux host (Debian 11) with system Python 3.9, run `ait setup` and verify uv download + python install path triggers, with NO sudo prompts.

## Dependencies

- t695_1 (python_resolve.sh) should be merged first. This child does not directly source the resolver, but `find_modern_python` benefits from being consistent with the resolver's lookup paths (`~/.aitask/bin`, `~/.aitask/venv/bin`, `~/.aitask/python/X/bin`).

## Notes for sibling tasks

- The uv installer respects `UV_INSTALL_DIR` and `INSTALLER_NO_MODIFY_PATH=1` — confirm both at implementation time and document any deviation.
- After install, the venv created by `python -m venv` will copy/symlink the chosen interpreter into `~/.aitask/venv/bin/python`. That's the path t695_3 will symlink from `~/.aitask/bin/python3`.
- If brew install requires the user to type their password (sudo for `/usr/local/bin` writes on Intel Macs), that's brew's behavior — not framework sudo. Document the difference.
