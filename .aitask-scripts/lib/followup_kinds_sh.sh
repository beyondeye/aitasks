#!/usr/bin/env bash
# followup_kinds_sh.sh - Shell bridge to lib/followup_kinds.py (t1468_1).
#
# Sources cleanly into a caller shell script and exposes:
#   followup_kinds_pipe      - prints "carry_over|docs_gap|..." (sorted)
#   is_valid_followup_kind   - returns 0 iff $1 is a known kind
#
# The vocabulary is derived at runtime by shelling out to lib/followup_kinds.py,
# so adding a kind there propagates to every shell consumer with no shell-side
# edit and no second copy to drift.
#
# Unlike launch_modes_sh.sh this bridge resolves **lazily**, on first use, and
# memoises. Sourcing is on the hot path of every `ait create` / `ait update`
# invocation, while the vocabulary is only needed when --followup-kind is
# actually supplied; an eager bridge would add a Python startup to every call,
# including the ~171-task backfill loop in t1468_6.
#
# FAILS CLOSED: if the module cannot be resolved, followup_kinds_pipe returns
# non-zero and prints nothing, so is_valid_followup_kind rejects rather than
# accepting an unvalidated value.
#
# Test hook: set AIT_FOLLOWUP_KINDS_DIR=/path to override the Python module
# search path.

[[ -n "${_AIT_FOLLOWUP_KINDS_LOADED:-}" ]] && return 0
_AIT_FOLLOWUP_KINDS_LOADED=1

_AIT_FOLLOWUP_KINDS_PIPE=""

followup_kinds_pipe() {
    if [[ -n "$_AIT_FOLLOWUP_KINDS_PIPE" ]]; then
        printf '%s' "$_AIT_FOLLOWUP_KINDS_PIPE"
        return 0
    fi
    local dir="${AIT_FOLLOWUP_KINDS_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
    # Defensive: this lib may be sourced before python_resolve.sh. If the cache
    # is set, use it; otherwise rely on python3 from PATH (the t695_3 symlink in
    # $HOME/.aitask/bin/python3 means python3 still resolves to the framework
    # interpreter on local installs).
    local pycmd="${_AIT_RESOLVED_PYTHON:-python3}"
    local out
    out="$("$pycmd" -c "
import sys
sys.path.insert(0, '$dir')
from followup_kinds import followup_kinds_pipe
sys.stdout.write(followup_kinds_pipe())
" 2>/dev/null)" || return 1
    [[ -n "$out" ]] || return 1
    _AIT_FOLLOWUP_KINDS_PIPE="$out"
    printf '%s' "$_AIT_FOLLOWUP_KINDS_PIPE"
}

# is_valid_followup_kind <value>
# Returns 0 iff the value is a known kind. Returns non-zero when the vocabulary
# cannot be resolved -- callers must treat that as "reject", never "accept".
is_valid_followup_kind() {
    local value="$1" pipe
    pipe="$(followup_kinds_pipe)" || return 1
    [[ -n "$pipe" ]] || return 1
    [[ "$value" =~ ^(${pipe})$ ]]
}

# enforce_manual_verification_kind_invariant <resulting_type> <resulting_kind>
#
# `followup_kind: manual_verification` REQUIRES `issue_type: manual_verification`
# -- otherwise a task would show the MV provenance while taking the bug/feature
# workflow. The converse is deliberately NOT required: an MV task may legitimately
# carry `carry_over`.
#
# Both arguments must be the values the write is about to PERSIST, not the flags
# the user passed. The pair can be broken from either side -- by supplying the
# kind, or by changing only the type on a task that already carries the kind --
# and a flag-level check sees only the first. Callers must therefore resolve
# `<flag> or <current value>` for BOTH before calling.
#
# Dies (non-zero, file untouched) on violation; returns 0 otherwise.
enforce_manual_verification_kind_invariant() {
    local resulting_type="$1" resulting_kind="$2"
    if [[ "$resulting_kind" == "manual_verification" \
       && "$resulting_type" != "manual_verification" ]]; then
        die "followup_kind 'manual_verification' requires issue_type 'manual_verification' (resulting issue_type would be '${resulting_type:-<unset>}'). Set both together, or choose a different followup_kind."
    fi
    return 0
}
