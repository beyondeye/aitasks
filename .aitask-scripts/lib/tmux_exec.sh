#!/usr/bin/env bash
# tmux_exec.sh - Shell tmux command gateway (mirror of lib/tmux_exec.py).
#
# The single place shell code routes a `tmux` invocation through, so the
# socket flag and exact-match target formatting live in ONE source. Mirrors
# the Python gateway's contract (t952_1):
#   * AITASKS_TMUX_SOCKET selects the socket — empty/unset => default socket
#     (today's behavior); non-empty => `-L <value>`.
#   * targets are exact-match `=session` / `=session:window`.
#
# Usage (sourced):
#     source "$SCRIPT_DIR/lib/tmux_exec.sh"
#     ait_tmux has-session -t "$(ait_tmux_session_target "$s")"
#     # exec / compound-command sites cannot use the function form (a shell
#     # function cannot be exec'd, and the wrapper must not mangle the `\;`
#     # separator) — use the emitter instead:
#     exec tmux $(ait_tmux_socket_args) attach -t "$t" \; select-window -t "$w"
#
# Depends on terminal_compat.sh for die/warn/info (sourced below, one-way).
# terminal_compat.sh in turn pulls THIS file in lazily inside
# ait_tmux_new_session_persistent (guarded), so there is no file-scope cycle.

# Guard against double-sourcing.
if [[ -n "${_AIT_TMUX_EXEC_LOADED:-}" ]]; then
    # shellcheck disable=SC2317  # `return` is reachable when sourced.
    return 0 2>/dev/null || true
fi
_AIT_TMUX_EXEC_LOADED=1

_TMUX_EXEC_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Pull in die/warn/info. terminal_compat.sh is a file-scope leaf (it never
# sources us back at file scope), so this one-way edge has no cycle.
# shellcheck source=terminal_compat.sh disable=SC1091
source "$_TMUX_EXEC_LIB_DIR/terminal_compat.sh"

# ait_tmux_socket_args
# Emit the socket flag for every tmux invocation, from one source (mirror of
# tmux_exec.py::tmux_socket_args). One argument per line: empty/unset
# AITASKS_TMUX_SOCKET => nothing (default socket); non-empty => `-L` then the
# value. `-L` (socket name) not `-S` (socket path) so the value composes with
# tmux's standard tmpdir resolution and the test isolation harness.
ait_tmux_socket_args() {
    local sock="${AITASKS_TMUX_SOCKET:-}"
    # Trim surrounding whitespace to match the Python .strip().
    sock="${sock#"${sock%%[![:space:]]*}"}"
    sock="${sock%"${sock##*[![:space:]]}"}"
    [[ -n "$sock" ]] && printf '%s\n' "-L" "$sock"
    return 0
}

# ait_tmux <args...>
# Function form: run `tmux` with the socket flag prepended. For captured /
# plain call sites. Returns tmux's exit code. (exec / compound sites use the
# ait_tmux_socket_args emitter instead — see header.)
ait_tmux() {
    local -a _argv=(tmux)
    local _line
    while IFS= read -r _line; do _argv+=("$_line"); done < <(ait_tmux_socket_args)
    _argv+=("$@")
    command "${_argv[@]}"
}

# ait_tmux_session_target <session>  -> "=<session>"
# Exact-match `-t` session target. tmux resolves `-t <name>` as a prefix match
# by default, so the `=` prefix is mandatory whenever prefix-sharing session
# names (e.g. `aitasks` vs `aitasks_mob`) can run side by side.
ait_tmux_session_target() {
    printf '=%s' "$1"
}

# ait_tmux_window_target <session> <window>  -> "=<session>:<window>"
# Only the session part is anchored with `=`. Pass window="" for the
# trailing-colon `new-window` idiom ("create in this session").
ait_tmux_window_target() {
    printf '=%s:%s' "$1" "$2"
}
