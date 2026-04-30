---
Task: t727_fix_uv_binary_path_so_ait_setup_with_pypy_works_on_linux.md
Base branch: main
plan_verified: []
---

# Plan: Fix uv binary path + macOS PyPy install audit (t727)

## Context

`ait setup --with-pypy` fails on Linux with:

```
.aitask-scripts/aitask_setup.sh: line 505: /home/<user>/.aitask/uv/bin/uv: No such file or directory
[ait] Error: uv python install pypy@3.11 failed.
```

Root cause: uv 0.11.8's installer places binaries directly inside `$UV_INSTALL_DIR` — `~/.aitask/uv/uv`, not `~/.aitask/uv/bin/uv`. The script references `$uv_dir/bin/uv` at six sites across two duplicated install blocks.

A parallel audit of the macOS PyPy install path surfaced same-family bugs:
- `_install_pypy_macos` hardcodes the literal `pypy3.11` (3 occurrences) ignoring `AIT_PYPY_PREFERRED`.
- `find_pypy()` candidate list also hardcodes `pypy3.11`.
- The macOS install path does not create the user-scoped symlink that the Linux path does, so `find_pypy()` resolution on macOS depends on PATH state instead of a stable per-version path.

Scope per user direction: fold all three macOS issues into t727 and queue a manual-verification follow-up via Step 8c (the implementer can verify Linux directly; macOS needs a Mac).

Per the project's "single source of truth for cross-script constants" rule and the "refactor duplicates before adding to them" planning convention, the fix corrects the path **and** extracts the duplicated 11-line uv install/check block into a single helper so the path decision lives in one place.

## Files to Modify

- `.aitask-scripts/aitask_setup.sh` — extract `_ensure_uv()`; rewrite `_install_modern_python_linux` and `_install_pypy_linux` to call it; replace `pypy3.11` literals in `_install_pypy_macos` and `find_pypy()` with `pypy$AIT_PYPY_PREFERRED`; add a user-scoped symlink in `_install_pypy_macos` for layout symmetry with Linux.
- `tests/test_setup_python_install.sh` — fix the wrong-path assertion at line 67 and tighten the silent no-op guard.

## Implementation Steps

### Step 1 — Add `_ensure_uv()` helper in `aitask_setup.sh`

Insert immediately above `_install_modern_python_linux` (current line 421). Encapsulates the download/check block and returns the absolute uv binary path on stdout. Idempotent.

```bash
# Locate or install uv (the Astral binary). Echoes the absolute path to the
# uv binary on stdout. Idempotent: skips download if a usable binary is
# already present at the expected location. Single source of truth for the
# uv install layout — callers must not hardcode paths.
_ensure_uv() {
    local uv_dir="$HOME/.aitask/uv"
    local uv_bin="$uv_dir/uv"
    if [[ ! -x "$uv_bin" ]]; then
        info "Downloading uv (astral-sh/uv) into $uv_dir (user-scoped, no sudo)..."
        if ! command -v curl >/dev/null 2>&1; then
            die "curl is required to download uv. Install curl and re-run."
        fi
        UV_INSTALL_DIR="$uv_dir" \
        INSTALLER_NO_MODIFY_PATH=1 \
            sh -c 'curl -LsSf https://astral.sh/uv/install.sh | sh' \
            || die "uv install failed."
        [[ -x "$uv_bin" ]] || die "uv installer ran but binary not found at $uv_bin."
    fi
    printf '%s\n' "$uv_bin"
}
```

Notes:
- `$uv_dir/uv` matches what uv 0.11.8's installer actually creates (verified: `ls ~/.aitask/uv/` → `uv  uvx`).
- Post-install existence guard (`[[ -x "$uv_bin" ]] || die ...`) catches future drift if the installer ever relocates binaries again — fails loudly instead of silently.
- No new lib file: uv is consumed only by `aitask_setup.sh`. Keeping the helper local avoids inventing a `lib/uv_resolve.sh` for a single caller pair.

### Step 2 — Rewrite `_install_modern_python_linux` to call `_ensure_uv`

Replace the 11-line uv install/check block + 3 `$uv_dir/bin/uv` references (lines 421–444) with:

```bash
_install_modern_python_linux() {
    local uv_bin
    uv_bin="$(_ensure_uv)"
    info "Installing Python $AIT_VENV_PYTHON_PREFERRED via uv..."
    "$uv_bin" python install "$AIT_VENV_PYTHON_PREFERRED" \
        || die "uv python install $AIT_VENV_PYTHON_PREFERRED failed."
    local installed
    installed="$("$uv_bin" python find "$AIT_VENV_PYTHON_PREFERRED" 2>/dev/null)"
    [[ -z "$installed" || ! -x "$installed" ]] && \
        die "uv reported Python $AIT_VENV_PYTHON_PREFERRED installed but interpreter is not executable: ${installed:-<empty>}"
    mkdir -p "$HOME/.aitask/python/$AIT_VENV_PYTHON_PREFERRED/bin"
    ln -sf "$installed" "$HOME/.aitask/python/$AIT_VENV_PYTHON_PREFERRED/bin/python3"
    info "Python $AIT_VENV_PYTHON_PREFERRED installed at $installed (symlinked at ~/.aitask/python/$AIT_VENV_PYTHON_PREFERRED/bin/python3)."
    hash -r
}
```

### Step 3 — Rewrite `_install_pypy_linux` to call `_ensure_uv`

Same shape, swap target. Replace lines 492–515:

```bash
_install_pypy_linux() {
    local uv_bin
    uv_bin="$(_ensure_uv)"
    info "Installing PyPy $AIT_PYPY_PREFERRED via uv..."
    "$uv_bin" python install "pypy@$AIT_PYPY_PREFERRED" \
        || die "uv python install pypy@$AIT_PYPY_PREFERRED failed."
    local installed
    installed="$("$uv_bin" python find "pypy@$AIT_PYPY_PREFERRED" 2>/dev/null)"
    [[ -z "$installed" || ! -x "$installed" ]] && \
        die "uv reported PyPy installed but interpreter is not executable: ${installed:-<empty>}"
    mkdir -p "$HOME/.aitask/python/pypy-$AIT_PYPY_PREFERRED/bin"
    ln -sf "$installed" "$HOME/.aitask/python/pypy-$AIT_PYPY_PREFERRED/bin/python3"
    info "PyPy $AIT_PYPY_PREFERRED installed at $installed (symlinked at ~/.aitask/python/pypy-$AIT_PYPY_PREFERRED/bin/python3)."
    hash -r
}
```

### Step 4 — Fix `_install_pypy_macos`: kill hardcoded `pypy3.11`, add symlink

Replace lines 481–490:

```bash
_install_pypy_macos() {
    if ! command -v brew >/dev/null 2>&1; then
        die "Homebrew not found. Install from https://brew.sh and re-run 'ait setup --with-pypy'."
    fi
    local formula="pypy$AIT_PYPY_PREFERRED"
    info "Installing $formula via Homebrew..."
    brew install "$formula" \
        || brew install pypy3 \
        || die "brew install $formula / pypy3 failed."
    hash -r

    # Layout symmetry with the Linux path: create a stable user-scoped symlink
    # so find_pypy()'s ~/.aitask/python/pypy-<ver>/bin/python3 candidate is
    # honored regardless of PATH state.
    local brew_pypy
    brew_pypy="$(command -v "pypy$AIT_PYPY_PREFERRED" 2>/dev/null \
                 || command -v pypy3 2>/dev/null \
                 || true)"
    if [[ -n "$brew_pypy" && -x "$brew_pypy" ]]; then
        # Confirm it is actually PyPy (not a brew CPython picked up via fallback).
        if "$brew_pypy" -c "import sys; sys.exit(0 if sys.implementation.name == 'pypy' else 1)" 2>/dev/null; then
            mkdir -p "$HOME/.aitask/python/pypy-$AIT_PYPY_PREFERRED/bin"
            ln -sf "$brew_pypy" "$HOME/.aitask/python/pypy-$AIT_PYPY_PREFERRED/bin/python3"
            info "PyPy symlinked at ~/.aitask/python/pypy-$AIT_PYPY_PREFERRED/bin/python3 → $brew_pypy"
        else
            warn "Resolved PyPy candidate $brew_pypy is not a PyPy interpreter; skipping symlink."
        fi
    else
        warn "Brew install reported success but no pypy binary was found on PATH; skipping symlink."
    fi
}
```

Notes:
- Homebrew formula name is `pypy3.11` (dot, no `@`). Since `AIT_PYPY_PREFERRED=3.11` already includes the dot, the derived form `pypy$AIT_PYPY_PREFERRED` → `pypy3.11` matches the actual formula. No string surgery needed.
- The `pypy3` meta-formula remains the fallback (matches existing intent).
- The post-install symlink mirrors the Linux path's `~/.aitask/python/pypy-<ver>/bin/python3` so `find_pypy()` candidates 1 and 2 both work on macOS too.
- The symlink is best-effort: if brew installs successfully but the binary lookup fails (rare — environment-specific PATH issue), warn and continue. The framework still works because `find_pypy()` falls back to candidates 3/4 (`pypy3.11`, `pypy3` on PATH).

### Step 5 — Drop hardcoded `pypy3.11` from `find_pypy()` candidate list

Current lines 451–457:

```bash
find_pypy() {
    local cand resolved
    local candidates=(
        "$PYPY_VENV_DIR/bin/python"
        "$HOME/.aitask/python/pypy-$AIT_PYPY_PREFERRED/bin/python3"
        pypy3.11 pypy3
    )
```

Replace with:

```bash
find_pypy() {
    local cand resolved
    local candidates=(
        "$PYPY_VENV_DIR/bin/python"
        "$HOME/.aitask/python/pypy-$AIT_PYPY_PREFERRED/bin/python3"
        "pypy$AIT_PYPY_PREFERRED" pypy3
    )
```

`AIT_PYPY_PREFERRED=3.11` → `pypy3.11` — same lookup as before in the default case, but a future bump to `3.12` resolves the `pypy3.12` binary on PATH instead of stale-matching 3.11.

### Step 6 — Fix the silently-no-op guard in `tests/test_setup_python_install.sh`

Currently lines 65–73:

```bash
if [[ "$(uname)" == "Linux" ]] && [[ -x "$FAKE_HOME/.aitask/uv/bin/uv" ]]; then
    echo "uv was installed at $FAKE_HOME/.aitask/uv/bin/uv"
    if [[ -L "$FAKE_HOME/.aitask/python/3.13/bin/python3" ]]; then
        echo "PASS: uv installed Python 3.13 with symlink at $FAKE_HOME/.aitask/python/3.13/bin/python3"
    fi
elif [[ "$(uname)" == "Darwin" ]]; then
    echo "Note: macOS host — brew install path expected (not asserting brew artifacts)."
else
    echo "Note: Linux host had a modern system Python; uv path not exercised."
fi
```

Two problems: wrong path, and the inner `if` no-ops on missing files. Replace with:

```bash
if [[ "$(uname)" == "Linux" ]] && [[ -d "$FAKE_HOME/.aitask/uv" ]]; then
    # Linux host where the uv path was taken (uv dir present).
    if [[ ! -x "$FAKE_HOME/.aitask/uv/uv" ]]; then
        echo "FAIL: expected uv binary at $FAKE_HOME/.aitask/uv/uv (uv installer puts binaries directly in UV_INSTALL_DIR)"
        exit 1
    fi
    echo "PASS: uv was installed at $FAKE_HOME/.aitask/uv/uv"
    # Find a python symlink under .aitask/python/<ver>/bin/python3 — version digit can vary.
    if ! ls -d "$FAKE_HOME/.aitask/python/"*"/bin/python3" 2>/dev/null | grep -q .; then
        echo "FAIL: expected uv-installed Python symlink at $FAKE_HOME/.aitask/python/<ver>/bin/python3"
        exit 1
    fi
    echo "PASS: uv installed Python with symlink at .aitask/python/<ver>/bin/python3"
elif [[ "$(uname)" == "Darwin" ]]; then
    echo "Note: macOS host — brew install path expected (not asserting brew artifacts)."
else
    echo "Note: Linux host had a modern system Python; uv path not exercised."
fi
```

The detection inverts: instead of "binary exists at wrong path → run inner check, else silently skip", we now say "if `~/.aitask/uv/` exists (meaning the uv path *was* taken), the binary MUST be at the corrected path; fail loudly otherwise". This catches both the original t695 path drift and any future regression.

### Step 7 — Implementer smoke test on Linux (reporter's machine)

After applying the patch:

```bash
ait setup --with-pypy
```

Expected:
- Detects existing `~/.aitask/uv/uv` (left over from the failed run); skips re-download.
- `uv python install pypy@3.11` runs successfully.
- `~/.aitask/python/pypy-3.11/bin/python3` symlink created.
- `~/.aitask/pypy_venv/` venv built with textual, pyyaml, linkify-it-py, tomli.
- Final line: `[ait] PyPy venv ready at ~/.aitask/pypy_venv — TUIs will auto-use it (set AIT_USE_PYPY=0 to override).`

Then:

```bash
AIT_USE_PYPY=1 ait board
```

Confirm board launches via PyPy.

## Step 8c — Manual Verification Follow-up

The implementer cannot verify the macOS fixes (Steps 4 and 5) directly. At Step 8c the standard `manual-verification-followup.md` procedure offers to spawn a standalone manual-verification task. **Accept the offer** and seed the checklist with macOS-focused items:

- `Run 'ait setup --with-pypy' on macOS (Apple Silicon and/or Intel) — confirm 'brew install pypy3.11' runs and exits 0.`
- `Confirm '~/.aitask/python/pypy-3.11/bin/python3' symlink is created and points into the brew Cellar.`
- `Confirm find_pypy() resolves the brew-installed PyPy: 'bash -c "source .aitask-scripts/lib/python_resolve.sh; find_pypy"' echoes the symlink path.`
- `Run 'AIT_USE_PYPY=1 ait board' on macOS — confirm board launches via PyPy (footer/title shows pypy build, no startup error).`
- `Override test: 'AIT_PYPY_PREFERRED=3.12 ait setup --with-pypy' (assuming a 3.12 brew formula exists) — confirm the dynamic 'pypy$AIT_PYPY_PREFERRED' lookup tries the 3.12 formula, not 3.11. If no 3.12 formula exists yet, document the failure mode (brew install returns 'No available formula') as expected.`
- `Re-run 'ait setup --with-pypy' twice in a row on macOS — confirm idempotent behavior (no re-install, symlink unchanged).`

Use `aitask_create_manual_verification.sh --related 727 --name manual_verification_pypy_install_macos_followup --verifies 727 --items <tmp_checklist>` (the procedure handles the `--related` form for standalone follow-ups).

## Verification

1. **Local smoke** (Step 7) — primary user-facing fix.
2. **Existing tests still pass** for non-uv paths:
   ```bash
   bash tests/test_python_resolve_pypy.sh
   bash tests/test_setup_find_modern_python.sh
   ```
3. **Updated integration test** (gated):
   ```bash
   AIT_RUN_INTEGRATION_TESTS=1 bash tests/test_setup_python_install.sh
   ```
   On a Linux host without system Python 3.11+ this must complete and print the new PASS lines for the corrected uv binary path.
4. **shellcheck**:
   ```bash
   shellcheck .aitask-scripts/aitask_setup.sh
   ```
   No new warnings introduced.

## Out of Scope

- A standalone `lib/uv_resolve.sh`: not justified for a single in-script caller pair; revisit if a third caller appears.
- A `pypy` label: not needed; existing `python` and `installation` labels suffice.
- Reworking `find_pypy()` beyond Step 5 (e.g., adding `pypy3.10`, `pypy3.12` candidates): the candidate list already falls back through the framework venv → user-scoped symlink → preferred-version → generic `pypy3`, which is sufficient.
- macOS `_install_modern_python_macos`: already uses `python@$AIT_VENV_PYTHON_PREFERRED` correctly — unaffected.

## Step 9 (Post-Implementation)

Standard archival per task-workflow `SKILL.md` Step 9. No worktree to remove (`fast` profile sets `create_worktree: false`). Run `./.aitask-scripts/aitask_archive.sh 727`, then `./ait git push`. The Step 8c manual-verification follow-up task remains open for whoever picks it up on macOS.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned. Added `_ensure_uv()` helper above `_install_modern_python_linux`. Rewrote `_install_modern_python_linux` and `_install_pypy_linux` to use `_ensure_uv` (drops 6 occurrences of the wrong `$uv_dir/bin/uv` path). Replaced hardcoded `pypy3.11` with `pypy$AIT_PYPY_PREFERRED` in `_install_pypy_macos` and `find_pypy()` candidate list. Added a user-scoped symlink in `_install_pypy_macos` for layout symmetry with Linux. Tightened the silently-no-op guard in `tests/test_setup_python_install.sh` to fail loudly when the uv binary is missing at the corrected path.
- **Deviations from plan:** None.
- **Issues encountered:** End-to-end smoke test on Linux passed first try — `ait setup --with-pypy` ran clean, `~/.aitask/pypy_venv/bin/python` resolves to PyPy 3.11.15, `sys.implementation.name == 'pypy'`. The existing `~/.aitask/uv/uv` binary from the reporter's failed run was correctly detected by the new `[[ -x "$uv_bin" ]]` check; uv was not re-downloaded.
- **Key decisions:** Kept `_ensure_uv()` as a local helper inside `aitask_setup.sh` rather than promoting it to a `lib/uv_resolve.sh` — uv is consumed by exactly one caller pair, all in this script. Promotion would be premature abstraction; revisit if a third caller appears.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/python_resolve.sh:112 — resolve_pypy_python() hardcodes 'pypy3.11 pypy3' candidate list, ignoring AIT_PYPY_PREFERRED. Same single-source-of-truth violation as the find_pypy() literal that was fixed in aitask_setup.sh during this task. Bumping AIT_PYPY_PREFERRED to 3.12 will silently match a stale 3.11 binary on PATH first.`
  - `tests/test_python_resolve_pypy.sh — pre-existing failure on main before this task (verified via 'git stash'): the PyPy stub at $SCRATCH/.aitask/pypy_venv/bin/python is not detected as PyPy by resolve_pypy_python() inside the test subshell, so 'AIT_USE_PYPY=1 require_ait_python_fast' dies with 'PyPy not found' even when the stub is present. Test was broken before this task; not caused by t727.`
- **Verification outside this task:** `bash tests/test_setup_find_modern_python.sh` → 6/6 pass. `shellcheck .aitask-scripts/aitask_setup.sh` → no new warnings (only pre-existing SC1091/SC2015/SC2034 unrelated to this change).
