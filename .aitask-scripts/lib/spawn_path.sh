#!/usr/bin/env bash
# spawn_path.sh — the PATH a framework-spawned tmux pane / agent should carry.
#
# Shell mirror of lib/tmux_exec.py::normalize_spawn_path (t1689); the two are
# pinned together by tests/test_tmux_exec.py::TestShellParity.
#
# Why: tmux copies the PATH of the *client process that issued* new-window /
# split-window / new-session into the new pane, so a pane's PATH order is
# whatever the spawner happened to have. On a mise host a spawner with
# ~/.local/bin ahead of mise's shims dir (and no __MISE_* session vars) hands
# the pane an order under which a `mise x <agent> -- <agent>` wrapper in
# ~/.local/bin resolves back to itself and loops forever — a blank agent pane.
#
# Rule: when PATH holds a mise entry (<mise_data>/shims, or anything under
# <mise_data>/installs/), reorder to
#   framework bins that lead PATH, then every mise entry, then the rest
# keeping relative order inside each group and keeping empty entries. With no
# mise entry the input is returned unchanged, byte for byte. Idempotent.
#
# Side-effect free: sourcing defines one function and touches nothing else
# (unlike aitask_path.sh, which prepends ~/.aitask/bin on source).
#
# The reordering is for the pane only. A launcher run under the new PATH
# (`tmux`, `setsid`) must still be the binary the caller's PATH resolves, so
# ait_spawn_exe spells it absolute exactly when the two PATHs disagree.
#
# Usage (sourced):
#     source "$(dirname "${BASH_SOURCE[0]}")/spawn_path.sh"
#     ait_spawn_path_normalize "${PATH-}"   # result in $AIT_SPAWN_PATH (no fork)
#     ait_spawn_exe tmux "${PATH-}" "$AIT_SPAWN_PATH"   # -> $AIT_SPAWN_EXE

if [[ -n "${_AIT_SPAWN_PATH_LOADED:-}" ]]; then
    # shellcheck disable=SC2317  # `return` is reachable when sourced.
    return 0 2>/dev/null || true
fi
_AIT_SPAWN_PATH_LOADED=1

# _ait_spawn_path_strip <value> -> $_AIT_SP_STRIPPED
# Drop trailing slashes, keeping a lone "/" (an entry naming the root).
_ait_spawn_path_strip() {
    local v="$1"
    while [[ "$v" == */ && "$v" != / ]]; do v="${v%/}"; done
    _AIT_SP_STRIPPED="$v"
}

# _ait_spawn_path_base <value> -> $_AIT_SP_BASE
# Drop ALL trailing slashes from a base dir about to get "/<suffix>" appended.
_ait_spawn_path_base() {
    local v="$1"
    while [[ "$v" == */ ]]; do v="${v%/}"; done
    _AIT_SP_BASE="$v"
}

# ait_spawn_path_normalize [<path>]
# Set AIT_SPAWN_PATH to the normalized form of <path> (default: $PATH).
# Pure string work in the current shell — no subshell, no external command —
# because ait_tmux calls it on every tmux invocation.
# shellcheck disable=SC2034  # AIT_SPAWN_PATH is the output, read by callers.
ait_spawn_path_normalize() {
    local src
    if [[ $# -ge 1 ]]; then src="$1"; else src="${PATH-}"; fi
    AIT_SPAWN_PATH="$src"

    local home="${HOME-}" data=""
    if [[ -n "${MISE_DATA_DIR-}" ]]; then
        _ait_spawn_path_base "$MISE_DATA_DIR"; data="$_AIT_SP_BASE"
    elif [[ -n "${XDG_DATA_HOME-}" ]]; then
        _ait_spawn_path_base "$XDG_DATA_HOME"; data="$_AIT_SP_BASE/mise"
    elif [[ -n "$home" ]]; then
        _ait_spawn_path_base "$home"; data="$_AIT_SP_BASE/.local/share/mise"
    else
        return 0
    fi
    local shims="$data/shims" installs="$data/installs/"

    local fw1="" fw2=""
    if [[ -n "$home" ]]; then
        _ait_spawn_path_base "$home"; fw1="$_AIT_SP_BASE/.aitask/bin"
    fi
    if [[ -n "${AITASKS_HOME-}" ]]; then
        _ait_spawn_path_base "$AITASKS_HOME"; fw2="$_AIT_SP_BASE/bin"
    elif [[ -n "$home" ]]; then
        _ait_spawn_path_base "$home"; fw2="$_AIT_SP_BASE/.aitasks/bin"
    fi

    # Three groups as ':'-joined strings plus a count each — a count, not an
    # emptiness test, because a group may legitimately hold one empty entry.
    local lead="" mise="" rest="" n_lead=0 n_mise=0 n_rest=0
    local leading=1 s="$src" e n
    while :; do
        e="${s%%:*}"
        _ait_spawn_path_strip "$e"; n="$_AIT_SP_STRIPPED"
        if [[ "$n" == "$shims" || "$n" == "$installs"* ]]; then
            if (( n_mise )); then mise+=":$e"; else mise="$e"; fi
            n_mise=$(( n_mise + 1 ))
        elif (( leading )) && [[ -n "$n" && ( "$n" == "$fw1" || "$n" == "$fw2" ) ]]; then
            if (( n_lead )); then lead+=":$e"; else lead="$e"; fi
            n_lead=$(( n_lead + 1 ))
        else
            leading=0
            if (( n_rest )); then rest+=":$e"; else rest="$e"; fi
            n_rest=$(( n_rest + 1 ))
        fi
        [[ "$s" == *:* ]] || break
        s="${s#*:}"
    done

    (( n_mise )) || return 0

    local out="" n_out=0 g
    for g in lead mise rest; do
        case "$g" in
            lead) (( n_lead )) || continue; e="$lead" ;;
            mise) e="$mise" ;;
            rest) (( n_rest )) || continue; e="$rest" ;;
        esac
        if (( n_out )); then out+=":$e"; else out="$e"; fi
        n_out=$(( n_out + 1 ))
    done
    AIT_SPAWN_PATH="$out"
}

# _ait_spawn_path_which <name> <path> -> $_AIT_SP_WHICH (empty when not found)
# First executable regular file named <name> on <path>; an empty entry means
# ".". No fork. Mirror of tmux_exec.py::_which.
_ait_spawn_path_which() {
    local name="$1" s="$2" d
    _AIT_SP_WHICH=""
    while :; do
        d="${s%%:*}"
        [[ -n "$d" ]] || d="."
        if [[ -f "$d/$name" && -x "$d/$name" ]]; then
            _AIT_SP_WHICH="$d/$name"
            return 0
        fi
        [[ "$s" == *:* ]] || break
        s="${s#*:}"
    done
    return 0
}

# ait_spawn_exe <name> <original_path> <spawn_path>
# Set AIT_SPAWN_EXE to <name> spelled so a process running under <spawn_path>
# executes the file <original_path> resolves: the bare name when both resolve
# the same file (or <original_path> resolves none, so a launch fails exactly as
# before), else the absolute path <original_path> resolves. Mirror of
# tmux_exec.py::resolve_spawn_exe.
# shellcheck disable=SC2034  # AIT_SPAWN_EXE is the output, read by callers.
ait_spawn_exe() {
    local name="$1" orig_path="$2" spawn_path="$3" orig
    AIT_SPAWN_EXE="$name"
    [[ "$orig_path" == "$spawn_path" ]] && return 0
    _ait_spawn_path_which "$name" "$orig_path"
    orig="$_AIT_SP_WHICH"
    [[ -n "$orig" ]] || return 0
    _ait_spawn_path_which "$name" "$spawn_path"
    [[ "$_AIT_SP_WHICH" == "$orig" ]] && return 0
    AIT_SPAWN_EXE="$orig"
}
