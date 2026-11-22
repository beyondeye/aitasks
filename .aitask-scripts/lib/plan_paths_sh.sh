#!/usr/bin/env bash
# plan_paths_sh.sh - Shell bridge to lib/plan_paths.py (t1569_1, t1877).
#
# Sources cleanly into a caller shell script and exposes:
#   plan_paths_references <plan-file>   - reads candidate paths NUL-delimited on
#                                         stdin; prints `<kind>\t<path>` for each
#                                         one the plan references, codepoint-sorted
#                                         (<kind>: full | bare | suffix)
#
# The search is `plan_paths.reference_kinds()` -- the inverted, language-agnostic
# reference detection, reached at runtime by shelling out to lib/plan_paths.py so
# it has exactly one definition and shell consumers stay in sync with the Python
# ones (lib/shadow_scope.py). Same pattern as launch_modes_sh.sh /
# followup_kinds_sh.sh. Its callers are aitask_remote_drift_check.sh and
# aitask_change_surface.sh (the plan-scope signal, since t2310).
#
# Unlike followup_kinds_sh.sh this bridge does NOT memoise a vocabulary: the
# result depends on the plan file argument, so there is nothing constant to
# cache. It does memoise the resolved interpreter, which is the part that costs.
#
# FAILS CLOSED: if the module cannot be resolved or the plan cannot be read,
# plan_paths_references returns non-zero and prints nothing. Callers MUST treat
# that as "could not scan", never as "the plan references nothing" -- the two
# are the same shape (empty stdout) and only the exit status separates them. In
# the drift check a silent empty set would print NO_OVERLAP, a false all-clear on
# the pick hot path.
#
# Test hook: set AIT_PLAN_PATHS_DIR=/path to override the module search path.

[[ -n "${_AIT_PLAN_PATHS_LOADED:-}" ]] && return 0
_AIT_PLAN_PATHS_LOADED=1

_AIT_PLAN_PATHS_PY=""

# Resolve (and memoise) the interpreter used to reach lib/plan_paths.py.
_plan_paths_python() {
    if [[ -n "$_AIT_PLAN_PATHS_PY" ]]; then
        printf '%s' "$_AIT_PLAN_PATHS_PY"
        return 0
    fi
    # Interpreter order (t2339): the cached resolution, then an executable
    # $AIT_PYTHON, then lib/python_resolve.sh (venv → wrapper → PATH python3),
    # then bare python3 from PATH. An explicit AIT_PYTHON is honoured even when
    # the PATH python3 is the ~/.aitask/bin wrapper of another HOME.
    # python_resolve.sh is sourced lazily and only when HOME is set: every
    # candidate it adds beyond AIT_PYTHON lives under HOME, and its PATH
    # python3 fallback is the one this bridge keeps below. (python_resolve.sh
    # itself tolerates an unset HOME under `set -u` since t2347.) A
    # bridge copied on its own into a test scaffold (no python_resolve.sh
    # beside it) keeps the plain python3 fallback exactly as before.
    local pycmd="${_AIT_RESOLVED_PYTHON:-}"
    if [[ -z "$pycmd" && -n "${AIT_PYTHON:-}" && -x "${AIT_PYTHON:-}" ]]; then
        pycmd="$AIT_PYTHON"
    fi
    if [[ -z "$pycmd" && -n "${HOME:-}" ]]; then
        local _lib_dir
        _lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        if [[ -r "$_lib_dir/python_resolve.sh" ]]; then
            # shellcheck source=lib/python_resolve.sh
            source "$_lib_dir/python_resolve.sh"
            resolve_python >/dev/null
            pycmd="${_AIT_RESOLVED_PYTHON:-}"
        fi
    fi
    pycmd="${pycmd:-python3}"
    _AIT_PLAN_PATHS_PY="$pycmd"
    printf '%s' "$_AIT_PLAN_PATHS_PY"
}

# plan_paths_references <plan-file>   (candidates on stdin, NUL-delimited)
# Prints `<kind>\t<path>` lines. Returns non-zero (printing nothing) when the
# module cannot be resolved or the plan cannot be read.
plan_paths_references() {
    local plan_file="${1:-}"
    [[ -n "$plan_file" ]] || return 1
    local dir pycmd out rc=0
    dir="${AIT_PLAN_PATHS_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
    pycmd="$(_plan_paths_python)"
    # `--` before the path: a caller-supplied plan path may begin with a hyphen.
    out="$("$pycmd" "$dir/plan_paths.py" --references -- "$plan_file" 2>/dev/null)" || rc=$?
    [[ $rc -eq 0 ]] || return "$rc"
    printf '%s' "$out"
}
