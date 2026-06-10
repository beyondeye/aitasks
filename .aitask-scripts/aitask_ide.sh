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
# wrapper is unusable there — capture the emitter's args once instead. Empty by
# default (default socket), so the exec lines are byte-identical to before.
_IDE_SOCK_ARGS=()
while IFS= read -r _line; do _IDE_SOCK_ARGS+=("$_line"); done < <(ait_tmux_socket_args)

# Thin wrappers that delegate to the shared bootstrap helpers (t826_2).
set_project_registry() {
    _tmux_bootstrap_set_project_registry "$(pwd)" "$SESSION"
}

ensure_syncer_window() {
    _tmux_bootstrap_ensure_syncer_window "$(pwd)" "$SESSION"
}

if [[ -n "${TMUX:-}" ]]; then
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

# Fresh-session path. spawn_session_detached handles new-session + env
# registry + syncer in one call (shared with the TUI switcher's
# inactive-project bootstrap path, t826_2). Then attach.
spawn_session_detached "$(pwd)"
exec tmux ${_IDE_SOCK_ARGS[@]+"${_IDE_SOCK_ARGS[@]}"} attach -t "$SESSION_T"
