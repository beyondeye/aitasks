#!/usr/bin/env bash
# tmux_exec.sh - Shell tmux command gateway (mirror of lib/tmux_exec.py).
#
# The single place shell code routes a `tmux` invocation through, so the
# socket flag and exact-match target formatting live in ONE source. Mirrors
# the Python gateway's contract (t952_1, t953):
#   * AITASKS_TMUX_SOCKET selects the socket — unset => `-L ait` (the
#     dedicated ait socket); non-empty => `-L <value>` (`default` is the
#     explicit opt-out: tmux's default socket is literally named `default`);
#     set-but-empty => no flag (legacy escape hatch, follows $TMUX — used by
#     the test isolation harness).
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

# The dedicated socket name every ait-managed tmux session lives on when the
# env var is unset (t953). Mirrored verbatim in lib/tmux_exec.py.
AIT_DEDICATED_SOCKET="ait"

# ait_tmux_socket_args
# Emit the socket flag for every tmux invocation, from one source (mirror of
# tmux_exec.py::tmux_socket_args). One argument per line (t953 semantics):
#   * unset AITASKS_TMUX_SOCKET => `-L` then `ait` (the dedicated default);
#   * non-empty => `-L` then the value (`default` = explicit opt-out to the
#     user's default server);
#   * set-but-empty/whitespace => nothing (legacy escape hatch, follows $TMUX
#     — used by the test isolation harness).
# `-L` (socket name) not `-S` (socket path) so the value composes with
# tmux's standard tmpdir resolution and the test isolation harness.
ait_tmux_socket_args() {
    if [[ -z "${AITASKS_TMUX_SOCKET+x}" ]]; then
        printf '%s\n' "-L" "$AIT_DEDICATED_SOCKET"
        return 0
    fi
    local sock="$AITASKS_TMUX_SOCKET"
    # Trim surrounding whitespace to match the Python .strip().
    sock="${sock#"${sock%%[![:space:]]*}"}"
    sock="${sock%"${sock##*[![:space:]]}"}"
    [[ -n "$sock" ]] && printf '%s\n' "-L" "$sock"
    return 0
}

# ait_tmux_socket_name
# Echo the resolved socket *name* the gateway targets (`ait`, a custom value,
# or empty when the legacy no-flag escape hatch is active). Single source of
# truth for callers that need to compare against the attached server's socket
# (e.g. the `ait ide` socket-identity check, t953).
ait_tmux_socket_name() {
    if [[ -z "${AITASKS_TMUX_SOCKET+x}" ]]; then
        printf '%s' "$AIT_DEDICATED_SOCKET"
        return 0
    fi
    local sock="$AITASKS_TMUX_SOCKET"
    sock="${sock#"${sock%%[![:space:]]*}"}"
    sock="${sock%"${sock##*[![:space:]]}"}"
    printf '%s' "$sock"
}

# ait_tmux_legacy <args...>
# Run `tmux` against the user's LEGACY default server (`-L default`),
# bypassing the gateway socket. Migration-window probes only (t953): detect a
# pre-dedicated-socket session so the user is not stranded. Lives here so the
# raw-tmux lint guard (tests/test_no_raw_tmux.sh) keeps a single allowlisted
# home for raw spawns.
ait_tmux_legacy() {
    command tmux -L default "$@"
}

# ait_tmux_legacy_socket_args
# Emitter form of ait_tmux_legacy for `exec tmux ... attach \; ...` sites
# (a shell function cannot be exec'd). One argument per line.
ait_tmux_legacy_socket_args() {
    printf '%s\n' "-L" "default"
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
