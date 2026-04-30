---
Task: t718_1_pypy_infrastructure_setup_resolver.md
Parent Task: aitasks/t718_pypy_optional_runtime_for_tui_perf.md
Sibling Tasks: aitasks/t718/t718_2_wire_long_running_tuis_to_fast_path.md, aitasks/t718/t718_3_documentation_pypy_runtime.md
Archived Sibling Plans: (none — first child of parent t718)
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# Plan: t718_1 — PyPy infrastructure (setup + venv + resolver)

## Context

First of three children under parent t718. Lands the entire PyPy plumbing layer
**without flipping any TUI launcher to use it** — that's t718_2's job. This
isolation is intentional: existing CPython users see zero behavior change after
this task ships unless they explicitly run `ait setup --with-pypy`.

Reference: `aiplans/p718_pypy_optional_runtime_for_tui_perf.md` (parent plan)
and `aidocs/python_tui_performance.md` (technical analysis).

## Files modified

- `.aitask-scripts/lib/python_resolve.sh` — new constants, three new resolver functions.
- `.aitask-scripts/aitask_setup.sh` — new helpers (`find_pypy`, `install_pypy`, `_install_pypy_macos`, `_install_pypy_linux`, `setup_pypy_venv`, `prompt_install_pypy_if_tty`), `--with-pypy` flag parsing, conditional call from `main()`.
- `tests/test_python_resolve_pypy.sh` (new) — unit test for the precedence table.

No new files under `.aitask-scripts/` (only new functions in existing files), so
the **5-touchpoint helper-script whitelist checklist from CLAUDE.md does not
apply**. No new framework dispatcher commands either, so the `ait` dispatcher
is also untouched.

## Implementation steps

### 1. `lib/python_resolve.sh` — constants and resolvers

Insert after the existing `AIT_VENV_PYTHON_MIN` declaration (currently line 32):

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

`require_ait_python` semantics are unchanged — the new `_fast` variant is
strictly additive.

### 2. `aitask_setup.sh` — new helpers

After `_install_modern_python_linux` ends (around line 444), insert:

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

At the very top of `main()` (currently line 3107), insert flag parsing
**before** any `info` / `echo` lines:

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

Also surface the PyPy venv in the final summary block (around line 3181-3191):

```bash
if [[ -d "$PYPY_VENV_DIR" ]]; then
    info "  PyPy venv: $PYPY_VENV_DIR"
fi
```

### 4. New unit test — `tests/test_python_resolve_pypy.sh`

A minimal assertion suite for the `require_ait_python_fast` precedence table.
Use the existing `tests/` helper conventions (assert_eq, assert_contains).
Mock PyPy presence by toggling `_AIT_RESOLVED_PYPY` directly inside the test.

Template:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

source .aitask-scripts/lib/python_resolve.sh

# Stub die so we can capture failure messages without exiting the test.
die() { echo "DIE: $1" >&2; return 1; }

# Case 1: AIT_USE_PYPY=1 with PyPy missing -> die
unset _AIT_RESOLVED_PYPY
AIT_USE_PYPY=1
result="$(require_ait_python_fast 2>&1 || true)"
[[ "$result" == DIE:* ]] || { echo "FAIL: forced=1 with no PyPy should die"; exit 1; }

# Case 2: AIT_USE_PYPY=1 with PyPy faked installed -> returns fake path
_AIT_RESOLVED_PYPY="/tmp/fake-pypy"; touch /tmp/fake-pypy; chmod +x /tmp/fake-pypy
result="$(AIT_USE_PYPY=1 require_ait_python_fast)"
[[ "$result" == "/tmp/fake-pypy" ]] || { echo "FAIL: forced=1 should return PyPy path"; exit 1; }

# Case 3: AIT_USE_PYPY=0 -> CPython regardless
unset _AIT_RESOLVED_PYPY
result="$(AIT_USE_PYPY=0 require_ait_python_fast 2>/dev/null || true)"
[[ "$result" != "/tmp/fake-pypy" ]] || { echo "FAIL: forced=0 should not return PyPy"; exit 1; }

# Case 4: unset + PyPy installed -> PyPy
_AIT_RESOLVED_PYPY="/tmp/fake-pypy"
result="$(unset AIT_USE_PYPY; require_ait_python_fast)"
[[ "$result" == "/tmp/fake-pypy" ]] || { echo "FAIL: unset+PyPy should auto-PyPy"; exit 1; }

rm -f /tmp/fake-pypy
echo "PASS: test_python_resolve_pypy.sh"
```

(The exact assertion helpers should match the existing `tests/` convention —
read one or two of the existing tests to align style.)

### 5. Manual integration test — fresh install

Per CLAUDE.md "Test the full install flow for setup helpers", verify the full
chain manually, not just the unit:

```bash
bash install.sh --dir /tmp/aitt718_1 --force
cd /tmp/aitt718_1
./ait setup --with-pypy
test -x ~/.aitask/pypy_venv/bin/python
~/.aitask/pypy_venv/bin/python -c "import sys, textual; assert sys.implementation.name == 'pypy'"
```

Then run a no-flag baseline test on a separate dir to confirm zero impact:

```bash
bash install.sh --dir /tmp/aitt718_1b --force
cd /tmp/aitt718_1b
./ait setup
test ! -d ~/.aitask/pypy_venv  # must NOT exist if --with-pypy was not passed
```

(Caveat: `~/.aitask/` is per-user, so the second test will *find* PyPy from
the first test on the same machine. Run on a clean machine, in a Docker
container, or by temporarily moving `~/.aitask/pypy_venv` aside.)

## Verification (this task)

1. `shellcheck .aitask-scripts/aitask_setup.sh .aitask-scripts/lib/python_resolve.sh` clean.
2. `bash tests/test_python_resolve_pypy.sh` passes.
3. Fresh install + `--with-pypy` produces `~/.aitask/pypy_venv/bin/python` (PyPy 3.11) with `textual` importable.
4. Fresh install without the flag does **not** create `~/.aitask/pypy_venv`.
5. `git diff --stat` shows changes only in `lib/python_resolve.sh`, `aitask_setup.sh`, and `tests/test_python_resolve_pypy.sh`. **No TUI launcher script may be modified in this task.**

## Step 9 (Post-Implementation)

Standard child-task archival: per `task-workflow/SKILL.md` Step 9, the archive
script will move task and plan files to `aitasks/archived/t718/` and
`aiplans/archived/p718/` respectively, and update `children_to_implement` on
the parent. No special handling.
