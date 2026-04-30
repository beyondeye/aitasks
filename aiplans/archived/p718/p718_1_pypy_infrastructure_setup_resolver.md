---
Task: t718_1_pypy_infrastructure_setup_resolver.md
Parent Task: aitasks/t718_pypy_optional_runtime_for_tui_perf.md
Sibling Tasks: aitasks/t718/t718_2_wire_long_running_tuis_to_fast_path.md, aitasks/t718/t718_3_documentation_pypy_runtime.md, aitasks/t718/t718_4_manual_verification_pypy_optional_runtime_for_tui_perf.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-30 12:17
---

# Plan: t718_1 — PyPy infrastructure (setup + venv + resolver)

## Verification status (this re-pick)

Existing plan at `aiplans/p718/p718_1_pypy_infrastructure_setup_resolver.md` was re-verified against the current codebase on 2026-04-30. **All file paths, line numbers, and assumptions still hold:**

- `lib/python_resolve.sh:32` — `AIT_VENV_PYTHON_MIN` constant ✓
- `lib/python_resolve.sh:87-89` — `require_ait_python` end-of-file insertion point ✓
- `lib/python_resolve.sh:34-35` — sources `terminal_compat.sh` (provides `die`) ✓
- `aitask_setup.sh:15` — sources `lib/python_resolve.sh` (so PyPy constants propagate)
- `aitask_setup.sh:378` — `find_modern_python` (pattern reference) ✓
- `aitask_setup.sh:403` — `install_modern_python` (pattern reference) ✓
- `aitask_setup.sh:444` — end of `_install_modern_python_linux` (insertion point for new helpers) ✓
- `aitask_setup.sh:447-528` — `setup_python_venv` (pattern reference) ✓
- `aitask_setup.sh:536-550` — `install_python_wrappers` (do not call for PyPy) ✓
- `aitask_setup.sh:3107` — `main()` entry (insertion point for `--with-pypy` flag parsing) ✓
- `aitask_setup.sh:3155` — call to `setup_python_venv` (insertion point for `setup_pypy_venv` call) ✓
- `aitask_setup.sh:3181-3191` — summary block (extension point for PyPy venv line) ✓

Existing test conventions: `tests/test_python_resolve.sh` uses HOME-isolated subshells with PATH-controlled stubs and `assert_eq`/`assert_contains` helpers. The new test file `tests/test_python_resolve_pypy.sh` will follow the same conventions (rather than the simpler draft template embedded in the previous plan).

No changes to the implementation strategy required. Proceeding with the existing plan.

## Context

First of three children under parent t718. Lands the entire PyPy plumbing layer **without flipping any TUI launcher to use it** — that's t718_2's job. This isolation is intentional: existing CPython users see zero behavior change after this task ships unless they explicitly run `ait setup --with-pypy`.

Reference: `aiplans/p718_pypy_optional_runtime_for_tui_perf.md` (parent plan) and `aidocs/python_tui_performance.md` (technical analysis).

## Files modified

- `.aitask-scripts/lib/python_resolve.sh` — new constants (`AIT_PYPY_PREFERRED`, `PYPY_VENV_DIR`), three new resolver functions (`resolve_pypy_python`, `require_ait_pypy`, `require_ait_python_fast`).
- `.aitask-scripts/aitask_setup.sh` — new helpers (`find_pypy`, `install_pypy`, `_install_pypy_macos`, `_install_pypy_linux`, `setup_pypy_venv`, `prompt_install_pypy_if_tty`), `--with-pypy` flag parsing in `main()`, conditional call to `setup_pypy_venv`, summary-block extension.
- `tests/test_python_resolve_pypy.sh` (new) — unit test for the `require_ait_python_fast` precedence table, modeled on `tests/test_python_resolve.sh`.

No new files under `.aitask-scripts/` (only new functions in existing files), so the **5-touchpoint helper-script whitelist checklist from CLAUDE.md does not apply**. No new `ait` dispatcher commands either.

## `AIT_USE_PYPY` precedence (established here)

`require_ait_python_fast()` implements:

| `AIT_USE_PYPY` | PyPy installed? | Result |
|----------------|-----------------|--------|
| `1` | Yes | PyPy (forced) |
| `1` | No | `die`: "PyPy not found. Run 'ait setup --with-pypy' to install it." |
| `0` | (any) | CPython (user override) |
| unset / empty | Yes | PyPy (default once installed) |
| unset / empty | No | CPython (silent — current behavior preserved) |

`require_ait_python` semantics are **unchanged** — the new `require_ait_python_fast` is strictly additive.

## Implementation steps

### 1. `lib/python_resolve.sh` — constants and resolvers

Insert after the existing `AIT_VENV_PYTHON_MIN` declaration (line 32):

```bash
# PyPy interpreter — opt-in via `ait setup --with-pypy`. Single source of
# truth (per feedback_single_source_of_truth_for_versions.md): aitask_setup.sh
# reads these via the existing `source python_resolve.sh` line.
AIT_PYPY_PREFERRED="${AIT_PYPY_PREFERRED:-3.11}"
PYPY_VENV_DIR="${PYPY_VENV_DIR:-$HOME/.aitask/pypy_venv}"
```

Append three functions at the bottom of the file (after `require_ait_python`):

```bash
resolve_pypy_python() {
    if [[ -n "${_AIT_RESOLVED_PYPY:-}" ]]; then
        echo "$_AIT_RESOLVED_PYPY"
        return 0
    fi
    local cand resolved
    for cand in "${AIT_PYPY:-}" "$PYPY_VENV_DIR/bin/python"; do
        if [[ -n "$cand" && -x "$cand" ]]; then
            if "$cand" -c "import sys; sys.exit(0 if sys.implementation.name == 'pypy' else 1)" 2>/dev/null; then
                _AIT_RESOLVED_PYPY="$cand"
                echo "$cand"
                return 0
            fi
        fi
    done
    for cand in pypy3.11 pypy3; do
        resolved="$(command -v "$cand" 2>/dev/null || true)"
        if [[ -n "$resolved" && -x "$resolved" ]]; then
            _AIT_RESOLVED_PYPY="$resolved"
            echo "$resolved"
            return 0
        fi
    done
    return 0  # empty stdout = not found; never error
}

require_ait_pypy() {
    local p
    p="$(resolve_pypy_python)"
    [[ -z "$p" ]] && die "PyPy not found. Run 'ait setup --with-pypy' to install it."
    echo "$p"
}

require_ait_python_fast() {
    case "${AIT_USE_PYPY:-}" in
        1) require_ait_pypy; return 0 ;;
        0) require_ait_python; return 0 ;;
    esac
    local p
    p="$(resolve_pypy_python)"
    if [[ -n "$p" ]]; then
        echo "$p"
        return 0
    fi
    require_ait_python
}
```

### 2. `aitask_setup.sh` — new helpers

After `_install_modern_python_linux` ends (line 444), insert:

```bash
find_pypy() {
    local cand resolved
    local candidates=(
        "$PYPY_VENV_DIR/bin/python"
        "$HOME/.aitask/python/pypy-$AIT_PYPY_PREFERRED/bin/python3"
        pypy3.11 pypy3
    )
    for cand in "${candidates[@]}"; do
        if [[ "$cand" == /* ]]; then
            resolved="$cand"
        else
            resolved="$(command -v "$cand" 2>/dev/null || true)"
        fi
        [[ -z "$resolved" || ! -x "$resolved" ]] && continue
        if "$resolved" -c "import sys; sys.exit(0 if sys.implementation.name == 'pypy' else 1)" 2>/dev/null; then
            echo "$resolved"
            return 0
        fi
    done
    return 0
}

install_pypy() {
    case "$OS" in
        macos) _install_pypy_macos ;;
        *)     _install_pypy_linux ;;
    esac
}

_install_pypy_macos() {
    if ! command -v brew >/dev/null 2>&1; then
        die "Homebrew not found. Install from https://brew.sh and re-run 'ait setup --with-pypy'."
    fi
    info "Installing pypy3.11 via Homebrew..."
    brew install pypy3.11 \
        || brew install pypy3 \
        || die "brew install pypy3.11 / pypy3 failed."
    hash -r
}

_install_pypy_linux() {
    local uv_dir="$HOME/.aitask/uv"
    if [[ ! -x "$uv_dir/bin/uv" ]]; then
        info "Downloading uv (astral-sh/uv) into $uv_dir..."
        if ! command -v curl >/dev/null 2>&1; then
            die "curl is required to download uv. Install curl and re-run."
        fi
        UV_INSTALL_DIR="$uv_dir" \
        INSTALLER_NO_MODIFY_PATH=1 \
            sh -c 'curl -LsSf https://astral.sh/uv/install.sh | sh' \
            || die "uv install failed."
    fi
    info "Installing PyPy $AIT_PYPY_PREFERRED via uv..."
    "$uv_dir/bin/uv" python install "pypy@$AIT_PYPY_PREFERRED" \
        || die "uv python install pypy@$AIT_PYPY_PREFERRED failed."
    local installed
    installed="$("$uv_dir/bin/uv" python find "pypy@$AIT_PYPY_PREFERRED" 2>/dev/null)"
    [[ -z "$installed" || ! -x "$installed" ]] && \
        die "uv reported PyPy installed but interpreter is not executable: ${installed:-<empty>}"
    mkdir -p "$HOME/.aitask/python/pypy-$AIT_PYPY_PREFERRED/bin"
    ln -sf "$installed" "$HOME/.aitask/python/pypy-$AIT_PYPY_PREFERRED/bin/python3"
    info "PyPy $AIT_PYPY_PREFERRED installed at $installed."
    hash -r
}

setup_pypy_venv() {
    local pypy_cmd
    pypy_cmd="$(find_pypy)"
    if [[ -z "$pypy_cmd" ]]; then
        info "No PyPy $AIT_PYPY_PREFERRED found. Installing one..."
        install_pypy
        pypy_cmd="$(find_pypy)"
        [[ -z "$pypy_cmd" ]] && \
            die "PyPy install completed but interpreter still not found."
    fi
    info "Using PyPy for venv: $pypy_cmd ($("$pypy_cmd" --version 2>&1 | head -1))"

    if [[ -d "$PYPY_VENV_DIR" ]]; then
        local impl=""
        impl="$("$PYPY_VENV_DIR/bin/python" -c 'import sys; print(sys.implementation.name)' 2>/dev/null)" || impl=""
        if [[ "$impl" == "pypy" ]]; then
            info "PyPy virtual environment already exists at $PYPY_VENV_DIR"
        else
            warn "Existing $PYPY_VENV_DIR is not a PyPy venv (impl=$impl). Recreating..."
            rm -rf "$PYPY_VENV_DIR"
            mkdir -p "$(dirname "$PYPY_VENV_DIR")"
            "$pypy_cmd" -m venv "$PYPY_VENV_DIR"
        fi
    else
        info "Creating PyPy virtual environment at $PYPY_VENV_DIR..."
        mkdir -p "$(dirname "$PYPY_VENV_DIR")"
        "$pypy_cmd" -m venv "$PYPY_VENV_DIR"
    fi

    info "Installing/upgrading Python deps into PyPy venv..."
    "$PYPY_VENV_DIR/bin/pip" install --quiet --upgrade pip
    "$PYPY_VENV_DIR/bin/pip" install --quiet 'textual>=8.1.1,<9' 'pyyaml==6.0.3' 'linkify-it-py==2.1.0' 'tomli>=2.4.0,<3'

    success "PyPy venv ready at $PYPY_VENV_DIR — TUIs will auto-use it (set AIT_USE_PYPY=0 to override)."
}

prompt_install_pypy_if_tty() {
    [[ -t 0 ]] || return 1
    [[ -d "$PYPY_VENV_DIR" ]] && return 1  # already installed
    info "Optional: PyPy 3.11 for faster TUIs (board, codebrowser, settings, stats, brainstorm)."
    printf "  Install PyPy now? Adds ~100-150 MB in ~/.aitask/. [y/N] "
    read -r answer
    case "${answer:-N}" in
        [Yy]*) return 0 ;;
        *)     return 1 ;;
    esac
}
```

### 3. `aitask_setup.sh` — flag parsing in `main()`

At the top of `main()` (line 3107), before the first `echo ""`, insert:

```bash
INSTALL_PYPY=0
local args=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --with-pypy) INSTALL_PYPY=1; shift ;;
        --) shift; args+=("$@"); break ;;
        *)  args+=("$1"); shift ;;
    esac
done
set -- "${args[@]}"
```

After `setup_python_venv` (line 3155) and before `install_global_shim`, add:

```bash
if [[ "$INSTALL_PYPY" == "1" ]] || prompt_install_pypy_if_tty; then
    setup_pypy_venv
    echo ""
fi
```

In the final summary block (lines 3181-3191), add:

```bash
if [[ -d "$PYPY_VENV_DIR" ]]; then
    info "  PyPy venv: $PYPY_VENV_DIR"
fi
```

### 4. New unit test — `tests/test_python_resolve_pypy.sh`

Modeled on `tests/test_python_resolve.sh` (HOME-isolated subshells, PATH stubs, `assert_eq`/`assert_contains` helpers). Cover the four cases from the precedence table:

- Case 1: `AIT_USE_PYPY=1` + no PyPy → die with "PyPy not found"
- Case 2: `AIT_USE_PYPY=1` + PyPy stub → returns PyPy path
- Case 3: `AIT_USE_PYPY=0` + PyPy installed → returns CPython path (not PyPy)
- Case 4: unset + PyPy installed → returns PyPy path
- Case 5 (bonus): unset + no PyPy → falls back to CPython

The PyPy stub is a tiny bash script that responds to `-c "import sys; sys.exit(0 if sys.implementation.name == 'pypy' else 1)"` with exit 0, and to `--version` with `Python 3.11.x [PyPy 7.x.x]`. Place under `$SCRATCH/bin/pypy3` or write to `$SCRATCH/.aitask/pypy_venv/bin/python` for the venv-path test.

### 5. Manual integration test — fresh install

Per CLAUDE.md "Test the full install flow for setup helpers", verify the full chain manually:

```bash
bash install.sh --dir /tmp/aitt718_1 --force
cd /tmp/aitt718_1
./ait setup --with-pypy
test -x ~/.aitask/pypy_venv/bin/python
~/.aitask/pypy_venv/bin/python -c "import sys, textual; assert sys.implementation.name == 'pypy'"
```

Then a no-flag baseline test:

```bash
bash install.sh --dir /tmp/aitt718_1b --force
cd /tmp/aitt718_1b
./ait setup
# Move PyPy venv aside before testing the no-flag path on a machine where it already exists
test ! -d ~/.aitask/pypy_venv  # must NOT exist after a no-flag run on a clean machine
```

(Caveat: `~/.aitask/` is per-user. On a machine where PyPy is already installed from a previous run, temporarily move `~/.aitask/pypy_venv` aside, or use a Docker container.)

## Verification (this task)

1. `shellcheck .aitask-scripts/aitask_setup.sh .aitask-scripts/lib/python_resolve.sh` clean.
2. `bash tests/test_python_resolve_pypy.sh` passes — covers the precedence table.
3. `bash tests/test_python_resolve.sh` still passes (regression check).
4. Fresh install + `--with-pypy` produces `~/.aitask/pypy_venv/bin/python` (PyPy 3.11) with `textual` importable.
5. Fresh install without the flag does **not** create `~/.aitask/pypy_venv`.
6. `git diff --stat` shows changes only in `lib/python_resolve.sh`, `aitask_setup.sh`, and `tests/test_python_resolve_pypy.sh`. **No TUI launcher script may be modified in this task** — that is t718_2's scope.

## Step 9 (Post-Implementation)

Standard child-task archival per `task-workflow/SKILL.md` Step 9: the archive script moves task and plan files to `aitasks/archived/t718/` and `aiplans/archived/p718/` and updates `children_to_implement` on the parent.

## Notes for sibling tasks

- t718_2 will rely on `require_ait_python_fast` from this task. The function's contract (precedence + zero-arg signature) is fixed by this task — do not change it without updating t718_2.
- The interactive `--with-pypy` prompt in `setup_python_venv` is a hint; t718_2 does **not** depend on the user having opted in. The fast-path functions handle the no-PyPy case silently.
- t718_3 (docs) will document the `AIT_USE_PYPY` env var and `--with-pypy` flag.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned. (1) Added `AIT_PYPY_PREFERRED` and `PYPY_VENV_DIR` constants to `lib/python_resolve.sh:34-38`, plus `resolve_pypy_python`, `require_ait_pypy`, and `require_ait_python_fast` at end-of-file. (2) Added `find_pypy`, `install_pypy`, `_install_pypy_macos`, `_install_pypy_linux`, `setup_pypy_venv`, `prompt_install_pypy_if_tty` to `aitask_setup.sh` between `_install_modern_python_linux` and `setup_python_venv`. (3) Added `INSTALL_PYPY` flag-parsing to top of `main()`, conditional `setup_pypy_venv` call after `setup_python_venv`, and a PyPy summary line in the post-setup info block. (4) Created `tests/test_python_resolve_pypy.sh` with 8 cases covering the full `AIT_USE_PYPY` precedence table plus the misnamed-CPython rejection path and the double-source guard.
- **Deviations from plan:** Two minor refinements during implementation:
  1. `prompt_install_pypy_if_tty` declares `local answer=""` before `read -r` (rather than relying on the implicit global the original snippet would have created). Cleaner and matches the rest of the file's local-var discipline.
  2. The Linux installer logs `(symlinked at ~/.aitask/python/pypy-$AIT_PYPY_PREFERRED/bin/python3)` for parity with `_install_modern_python_linux`, not present in the plan snippet.
- **Issues encountered:** None. Plan was already verified against current line numbers during the verify-mode pass at task pick time, so all insertion points landed cleanly. The pre-existing `SC1091` shellcheck info on `source` lines is upstream noise (path resolution from the CWD); not introduced here.
- **Key decisions:** The test file follows the existing `tests/test_python_resolve.sh` pattern (HOME-isolated subshells, PATH-controlled stubs, `assert_eq`/`assert_contains` helpers) rather than the simpler draft template embedded in the previous version of this plan. The richer harness covers the full precedence table including a guard against misnamed CPython at `$PYPY_VENV_DIR/bin/python` (Test 7) and a double-source idempotence check (Test 8).
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - `require_ait_python_fast` is the single zero-arg entry point t718_2 should use to pick PyPy when available. Function name and signature are fixed.
  - `_AIT_RESOLVED_PYPY` is the cache variable; downstream code should NOT touch it directly. Tests can use it to fake a PyPy install for unit-level coverage (see Test 4 of `test_python_resolve_pypy.sh`).
  - The interactive prompt is silent on non-TTY stdin (CI / scripted setup) and a no-op when the venv already exists, so no regression risk for existing CPython users.
  - macOS uses `brew install pypy3.11` with `pypy3` fallback; Linux uses `uv python install pypy@3.11`. Both branches symlink the resolved interpreter into `~/.aitask/python/pypy-3.11/bin/python3` for parallel structure with the CPython install path. t718_3 should call this out in user docs.
