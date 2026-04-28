#!/usr/bin/env bash
# python_resolve.sh - Python interpreter resolution for the aitasks framework.
# Source this file from aitask scripts; do not execute directly.
#
# Provides:
#   resolve_python           - echo the first usable Python path, or empty
#   require_python           - resolve_python or die with a clear error
#   require_modern_python X  - resolve_python and assert version >= X (e.g. 3.11)
#
# Resolution order:
#   1. $AIT_PYTHON                         (explicit override)
#   2. $HOME/.aitask/bin/python3           (framework symlink, t695_3)
#   3. $HOME/.aitask/venv/bin/python       (framework venv, t695_2)
#   4. command -v python3                  (system fallback / remote sandboxes)
#
# The result is cached in _AIT_RESOLVED_PYTHON for the lifetime of the shell.

[[ -n "${_AIT_PYTHON_RESOLVE_LOADED:-}" ]] && return 0
_AIT_PYTHON_RESOLVE_LOADED=1

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
        "$HOME/.aitask/bin/python3" \
        "$HOME/.aitask/venv/bin/python"; do
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
