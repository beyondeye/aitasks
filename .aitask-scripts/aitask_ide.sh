#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/tmux_exec.sh
source "$SCRIPT_DIR/lib/tmux_exec.sh"
# shellcheck source=lib/tmux_bootstrap.sh
source "$SCRIPT_DIR/lib/tmux_bootstrap.sh"

SESSION_OVERRIDE=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --session)
            SESSION_OVERRIDE="${2:-}"
            [[ -z "$SESSION_OVERRIDE" ]] && die "--session requires a name"
            shift 2
            ;;
        -h|--help)
            cat <<'EOF'
Usage: ait ide [--session NAME]

Starts (or attaches to) the configured tmux session and launches ait monitor.

This collapses the manual "tmux + ait monitor" startup into a single command
and always passes an explicit session name so ait monitor never has to fall
back to the SessionRenameDialog.

Options:
  --session NAME   Use NAME instead of the configured default_session.
  -h, --help       Show this help.

Note: The tmux session is shared, not per-terminal. If you run 'ait ide' in a
second terminal, you don't get a separate IDE — you get another view of the
same session, showing the same windows, panes, and TUIs. Changes in one
terminal (opening a window, resizing, switching TUIs) are visible in all the
others. To work on two projects side-by-side in parallel, start each one in
its own session with --session NAME (or configure a different default_session
under tmux in each project's aitasks/metadata/project_config.yaml).
EOF
            exit 0
            ;;
        *)
            die "Unknown option: $1 (try 'ait ide --help')"
            ;;
    esac
done

resolve_session() {
    if [[ -n "$SESSION_OVERRIDE" ]]; then
        echo "$SESSION_OVERRIDE"
        return
    fi
    _tmux_bootstrap_resolve_session "$(pwd)"
}

SESSION=$(resolve_session)
# Exact-match tmux target — prevents prefix-match collisions when another
# project's session name shares a prefix (e.g. 'aitasks' vs 'aitasks_mob').
SESSION_T="$(ait_tmux_session_target "$SESSION")"

command -v tmux >/dev/null || die "tmux is not installed. Install it first, then re-run 'ait ide'."

# Socket flag for the `exec tmux ...` sites below. A shell function cannot be
# exec'd (and exec must keep the `\;` separator intact), so the ait_tmux
# wrapper is unusable there — capture the emitter's args once instead.
# `-L ait` by default (the dedicated ait socket, t953); empty only when the
# legacy no-flag escape hatch is active (AITASKS_TMUX_SOCKET set but empty).
_IDE_SOCK_ARGS=()
while IFS= read -r _line; do _IDE_SOCK_ARGS+=("$_line"); done < <(ait_tmux_socket_args)
_IDE_SOCK_NAME="$(ait_tmux_socket_name)"

# Thin wrappers that delegate to the shared bootstrap helpers (t826_2).
set_project_registry() {
    _tmux_bootstrap_set_project_registry "$(pwd)" "$SESSION"
}

ensure_syncer_window() {
    _tmux_bootstrap_ensure_syncer_window "$(pwd)" "$SESSION"
}

if [[ -n "${TMUX:-}" ]]; then
    # Socket-identity check (t953): the gateway targets the dedicated socket,
    # so a gateway-routed self-probe from inside a FOREIGN server (the user's
    # personal tmux, or a pre-t953 legacy session) would query a server where
    # this client has no pane — failing under `set -e`. Compare the attached
    # server's socket name ($TMUX's first field is the socket path) against
    # the gateway's resolved name; bail out with guidance on mismatch. Skip
    # when the legacy no-flag escape hatch is active (empty name → ait_tmux
    # follows $TMUX, today's behavior).
    _attached_sock="$(basename "${TMUX%%,*}")"
    if [[ -n "$_IDE_SOCK_NAME" && "$_attached_sock" != "$_IDE_SOCK_NAME" ]]; then
        warn "You are inside a tmux server on socket '$_attached_sock', but ait sessions"
        warn "live on the dedicated socket '-L $_IDE_SOCK_NAME'."
        warn "Detach (Ctrl-b d) and re-run 'ait ide' to use the aitasks server, or run"
        warn "  AITASKS_TMUX_SOCKET=$_attached_sock ait ide"
        warn "to keep using the current server."
        exit 1
    fi
    current_session=$(ait_tmux display-message -p '#S')
    if [[ "$current_session" != "$SESSION" ]]; then
        warn "Already inside tmux session '$current_session', but configured session is '$SESSION'."
        warn "Refusing to nest tmux. Either detach (Ctrl-b d) and re-run 'ait ide', or"
        warn "pass '--session $current_session' to use the current session."
        exit 1
    fi
    set_project_registry
    if ! ait_tmux list-windows -F '#{window_name}' | grep -qx 'monitor'; then
        ait_tmux new-window -n monitor 'ait monitor'
    fi
    ensure_syncer_window
    exec tmux ${_IDE_SOCK_ARGS[@]+"${_IDE_SOCK_ARGS[@]}"} select-window -t "${SESSION_T}:monitor"
fi

if ait_tmux has-session -t "$SESSION_T" 2>/dev/null; then
    set_project_registry
    if ! ait_tmux list-windows -t "$SESSION_T" -F '#{window_name}' | grep -qx 'monitor'; then
        ait_tmux new-window -t "${SESSION_T}:" -n monitor 'ait monitor'
    fi
    ensure_syncer_window
    exec tmux ${_IDE_SOCK_ARGS[@]+"${_IDE_SOCK_ARGS[@]}"} attach -t "$SESSION_T" \; select-window -t "${SESSION_T}:monitor"
fi

# Legacy-session migration offer (t953): no session on the dedicated socket,
# but one with the same name may still live on the user's default server from
# before the socket move (tmux cannot move sessions between servers). Detect
# it so a user mid-flight is not stranded. Skipped when the gateway already
# targets the default server (opt-out / legacy escape hatch).
if [[ -n "$_IDE_SOCK_NAME" && "$_IDE_SOCK_NAME" != "default" ]] \
    && ait_tmux_legacy has-session -t "$SESSION_T" 2>/dev/null; then
    if [[ -t 0 && -t 1 ]]; then
        warn "Session '$SESSION' exists on the legacy default tmux server (pre-dedicated-socket)."
        printf 'Attach to it instead? [y/N] ' >&2
        read -r _legacy_answer || _legacy_answer=""
        if [[ "$_legacy_answer" =~ ^[Yy]$ ]]; then
            _IDE_LEGACY_ARGS=()
            while IFS= read -r _line; do _IDE_LEGACY_ARGS+=("$_line"); done < <(ait_tmux_legacy_socket_args)
            exec tmux "${_IDE_LEGACY_ARGS[@]}" attach -t "$SESSION_T"
        fi
        warn "Creating a fresh session on the dedicated socket. To reach the legacy one later:"
        warn "  AITASKS_TMUX_SOCKET=default ait ide"
    else
        warn "Session '$SESSION' also exists on the legacy default tmux server;"
        warn "run 'AITASKS_TMUX_SOCKET=default ait ide' to reach it."
    fi
fi

# Fresh-session path. spawn_session_detached handles new-session + env
# registry + syncer in one call (shared with the TUI switcher's
# inactive-project bootstrap path, t826_2). Then attach.
spawn_session_detached "$(pwd)"
exec tmux ${_IDE_SOCK_ARGS[@]+"${_IDE_SOCK_ARGS[@]}"} attach -t "$SESSION_T"
