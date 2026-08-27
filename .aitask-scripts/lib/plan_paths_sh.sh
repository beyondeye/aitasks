#!/usr/bin/env bash
# plan_paths_sh.sh - Shell bridge to lib/plan_paths.py (t1569_1).
#
# Sources cleanly into a caller shell script and exposes:
#   plan_paths_extract <plan-file>   - prints one path token per line,
#                                      ./-stripped, deduped, codepoint-sorted
#
# The grammar is derived at runtime by shelling out to lib/plan_paths.py, so the
# extraction has exactly one definition and shell consumers stay in sync with the
# Python ones (lib/trail_gather.py, and t1569_3's admission checker) with no
# second copy to drift. Same pattern as launch_modes_sh.sh / followup_kinds_sh.sh.
#
# Unlike followup_kinds_sh.sh this bridge does NOT memoise a vocabulary: the
# result depends on the plan file argument, so there is nothing constant to
# cache. It does memoise the resolved interpreter, which is the part that costs.
#
# FAILS CLOSED: if the module cannot be resolved or the plan cannot be read,
# plan_paths_extract returns non-zero and prints nothing. Callers MUST treat that
# as "could not extract", never as "extracted nothing" -- the two are the same
# shape (empty stdout) and only the exit status separates them. In the drift
# check a silent empty set would print NO_OVERLAP, a false all-clear on the
# pick hot path.
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
    # Defensive: this lib may be sourced before python_resolve.sh. If the cache
    # is set, use it; otherwise rely on python3 from PATH (the t695_3 symlink in
    # $HOME/.aitask/bin/python3 means python3 still resolves to the framework
    # interpreter on local installs).
    _AIT_PLAN_PATHS_PY="${_AIT_RESOLVED_PYTHON:-python3}"
    printf '%s' "$_AIT_PLAN_PATHS_PY"
}

# plan_paths_extract <plan-file>
# Prints one token per line. Returns non-zero (printing nothing) when the module
# cannot be resolved or the file cannot be read.
plan_paths_extract() {
    local plan_file="${1:-}"
    [[ -n "$plan_file" ]] || return 1
    local dir pycmd out rc=0
    dir="${AIT_PLAN_PATHS_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
    pycmd="$(_plan_paths_python)"
    # `--` before the path: the token charset admits a leading hyphen, and so
    # can a caller-supplied plan path.
    out="$("$pycmd" "$dir/plan_paths.py" -- "$plan_file" 2>/dev/null)" || rc=$?
    [[ $rc -eq 0 ]] || return "$rc"
    printf '%s' "$out"
}
