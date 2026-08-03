#!/usr/bin/env bash
# python_resolve.sh - Python interpreter resolution for the aitasks framework.
# Source this file from aitask scripts; do not execute directly.
#
# Provides:
#   resolve_python           - echo the first usable Python path, or empty
#   require_python           - resolve_python or die with a clear error
#   require_modern_python X  - resolve_python and assert version >= X (e.g. 3.11)
#   require_ait_python       - require_modern_python "$AIT_VENV_PYTHON_MIN"
#                              (zero-arg canonical entry point — preferred over
#                              hardcoding the version literal in caller scripts)
#
# Resolution order:
#   1. $AIT_PYTHON                         (explicit override)
#   2. $HOME/.aitask/venv/bin/python       (framework venv, t695_2 — canonical)
#   3. $HOME/.aitask/bin/python3           (framework wrapper, t706, was t695_3 symlink)
#   4. command -v python3                  (system fallback / remote sandboxes)
#
# The venv path comes first as defense-in-depth: a wrapper regression on
# bin/python3 cannot mask the venv when explicit lookups go through the
# canonical interpreter first. PATH-based subprocess resolution still hits
# the wrapper (via lib/aitask_path.sh prepending ~/.aitask/bin to PATH).
#
# The result is cached in _AIT_RESOLVED_PYTHON for the lifetime of the shell.

[[ -n "${_AIT_PYTHON_RESOLVE_LOADED:-}" ]] && return 0
_AIT_PYTHON_RESOLVE_LOADED=1

# Framework minimum Python version. Single source of truth — every migrated
# script picks up this constant by sourcing this file. Override via env for
# testing only.
AIT_VENV_PYTHON_MIN="${AIT_VENV_PYTHON_MIN:-3.11}"

# PyPy interpreter — opt-in via `ait setup --with-pypy`. Single source of
# truth (per feedback_single_source_of_truth_for_versions.md): aitask_setup.sh
# reads these via the existing `source python_resolve.sh` line.
AIT_PYPY_PREFERRED="${AIT_PYPY_PREFERRED:-3.11}"
PYPY_VENV_DIR="${PYPY_VENV_DIR:-$HOME/.aitask/pypy_venv}"

# Import names a PyPy interpreter must actually provide before the fast path
# will use it — the framework's shared runtime set. Declared HERE, not in
# aitask_setup.sh, because resolve_pypy_python() below needs it and setup
# sources this file (never the reverse); aitask_setup.sh derives its
# AIT_IMPORTS_COMMON from this array so the list has exactly one home.
# Keep in step with AIT_PIP_SPECS_COMMON in aitask_setup.sh (the distribution
# names that install these: pyyaml->yaml, linkify-it-py->linkify_it).
AIT_PYPY_RUNTIME_IMPORTS=(textual yaml linkify_it tomli)

# shellcheck source=terminal_compat.sh
source "$(dirname "${BASH_SOURCE[0]}")/terminal_compat.sh"

resolve_python() {
    if [[ -n "${_AIT_RESOLVED_PYTHON:-}" ]]; then
        echo "$_AIT_RESOLVED_PYTHON"
        return 0
    fi

    local cand resolved
    for cand in \
        "${AIT_PYTHON:-}" \
        "$HOME/.aitask/venv/bin/python" \
        "$HOME/.aitask/bin/python3"; do
        if [[ -n "$cand" && -x "$cand" ]]; then
            _AIT_RESOLVED_PYTHON="$cand"
            echo "$cand"
            return 0
        fi
    done

    resolved="$(command -v python3 2>/dev/null || true)"
    if [[ -n "$resolved" && -x "$resolved" ]]; then
        _AIT_RESOLVED_PYTHON="$resolved"
        echo "$resolved"
        return 0
    fi

    return 0
}

require_python() {
    local p
    p="$(resolve_python)"
    if [[ -z "$p" ]]; then
        die "No Python interpreter found. Run 'ait setup' locally, or install python3 system-wide for remote use."
    fi
    echo "$p"
}

require_modern_python() {
    local min="${1:?usage: require_modern_python <major.minor>}"
    local p major minor found
    p="$(require_python)"
    major="${min%%.*}"
    minor="${min##*.}"
    if ! "$p" -c "import sys; sys.exit(0 if sys.version_info >= ($major, $minor) else 1)" 2>/dev/null; then
        found="$("$p" --version 2>&1 | awk '{print $2}')"
        die "Python >=$min required (found ${found:-unknown} at $p). Run 'ait setup' to install a newer interpreter."
    fi
    echo "$p"
}

require_ait_python() {
    require_modern_python "$AIT_VENV_PYTHON_MIN"
}

# Resolve a PyPy interpreter that can actually RUN the framework's TUIs, or
# print nothing so the caller falls back to the CPython venv.
#
# A candidate must satisfy BOTH conditions: it is PyPy, AND it can see the
# framework's Python dependencies. Identity alone is not enough, and testing
# only identity was a real defect on two paths:
#
#   * `pypy3` / `pypy<ver>` on PATH is a candidate, so a system PyPy installed
#     for unrelated reasons was selected for `ait board` even on a machine that
#     never ran `ait setup --with-pypy` — the board then died at `import textual`.
#   * `setup_pypy_venv` degrades by REMOVING $PYPY_VENV_DIR so the board falls
#     back to CPython. With an identity-only probe that fallback did not hold
#     whenever a system PyPy was on PATH: resolution simply moved on to it, and
#     the removal bought nothing.
#
# The probe IMPORTS the whole $AIT_PYPY_RUNTIME_IMPORTS set rather than merely
# locating one module. Both halves of that matter:
#
#   * One module is not enough — aitask_board.py imports `yaml` directly as well
#     as Textual, so a PyPy carrying textual but missing pyyaml still crashes.
#   * Locating is not importing — importlib.util.find_spec() answers "present"
#     for a package whose __init__ raises (a broken install, or a missing
#     transitive dependency of Textual itself). Only the import proves usable.
#
# The identity check runs FIRST so a non-PyPy candidate is rejected without
# paying for any imports. Cost when the candidate IS PyPy: ~186ms vs ~16ms,
# once per launch and memoized in _AIT_RESOLVED_PYPY — it is the same import
# work the board is about to do anyway, and a board settles in ~3s. Fail-closed:
# any error exits non-zero and the candidate is rejected.
#
# NOTE: aitask_setup.sh's find_pypy() deliberately keeps an identity-only probe.
# It looks for a bare interpreter to CREATE the venv from, which by definition
# has no deps yet. The asymmetry is intentional — do not "harmonize" them.
resolve_pypy_python() {
    if [[ -n "${_AIT_RESOLVED_PYPY:-}" ]]; then
        echo "$_AIT_RESOLVED_PYPY"
        return 0
    fi
    local cand resolved mods
    # printf -v, not "${arr[*]}": builds the comma list without depending on IFS.
    printf -v mods '%s, ' "${AIT_PYPY_RUNTIME_IMPORTS[@]}"
    mods="${mods%, }"
    local candidates=(
        "${AIT_PYPY:-}"
        "$PYPY_VENV_DIR/bin/python"
        "pypy$AIT_PYPY_PREFERRED"
        pypy3
    )
    for cand in "${candidates[@]}"; do
        [[ -z "$cand" ]] && continue
        if [[ "$cand" == /* ]]; then
            resolved="$cand"
        else
            resolved="$(command -v "$cand" 2>/dev/null || true)"
        fi
        [[ -z "$resolved" || ! -x "$resolved" ]] && continue
        # BOTH streams are discarded, not just stderr. This function's contract
        # is "echo the interpreter path", and importing the runtime set really
        # does write to stdout: `import yaml` under PyPy emits Cython diagnostic
        # lines, which would otherwise be captured by the caller's $(...) and
        # handed to exec as part of the interpreter path.
        if "$resolved" -c "import sys
if sys.implementation.name != 'pypy':
    sys.exit(1)
import $mods
sys.exit(0)" >/dev/null 2>&1; then
            _AIT_RESOLVED_PYPY="$resolved"
            echo "$resolved"
            return 0
        fi
    done
    return 0
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
