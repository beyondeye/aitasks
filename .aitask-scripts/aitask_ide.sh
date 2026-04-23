#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

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
    local cfg="aitasks/metadata/project_config.yaml"
    if [[ -f "$cfg" ]]; then
        local name
        name=$(awk '
            /^tmux:/ { intmux=1; next }
            intmux && /^  default_session:/ {
                sub(/^  default_session:[ \t]*/, "")
                gsub(/"/, "")
                gsub(/'"'"'/, "")
                sub(/[[:space:]]+$/, "")
                print
                exit
            }
            /^[^ #]/ && !/^tmux:/ { intmux=0 }
        ' "$cfg")
        if [[ -n "$name" ]]; then
            echo "$name"
            return
        fi
    fi
    echo "aitasks"
}

SESSION=$(resolve_session)
# Exact-match tmux target — prevents prefix-match collisions when another
# project's session name shares a prefix (e.g. 'aitasks' vs 'aitasks_mob').
SESSION_T="=${SESSION}"

command -v tmux >/dev/null || die "tmux is not installed. Install it first, then re-run 'ait ide'."

# Register this project's root under a per-session global env var so that
# multi-session aitasks features (monitor, switcher) can detect the session as
# aitasks-like even before any pane cd's into the project directory. Cleaned
# up automatically when the tmux server exits.
set_project_registry() {
    tmux set-environment -g "AITASKS_PROJECT_${SESSION}" "$(pwd)" 2>/dev/null || true
}

if [[ -n "${TMUX:-}" ]]; then
    current_session=$(tmux display-message -p '#S')
    if [[ "$current_session" != "$SESSION" ]]; then
        warn "Already inside tmux session '$current_session', but configured session is '$SESSION'."
        warn "Refusing to nest tmux. Either detach (Ctrl-b d) and re-run 'ait ide', or"
        warn "pass '--session $current_session' to use the current session."
        exit 1
    fi
    set_project_registry
    if tmux list-windows -F '#{window_name}' | grep -qx 'monitor'; then
        exec tmux select-window -t "${SESSION_T}:monitor"
    else
        exec tmux new-window -n monitor 'ait monitor'
    fi
fi

if tmux has-session -t "$SESSION_T" 2>/dev/null; then
    set_project_registry
    if ! tmux list-windows -t "$SESSION_T" -F '#{window_name}' | grep -qx 'monitor'; then
        tmux new-window -t "${SESSION_T}:" -n monitor 'ait monitor'
    fi
    exec tmux attach -t "$SESSION_T" \; select-window -t "${SESSION_T}:monitor"
fi

# `new-session -s` takes a literal session name to create, not a target to
# resolve — do not prefix it with '='. Use -d + set-environment + attach so
# the registry write happens while the server is up but before the caller's
# process is replaced by the attached client.
tmux new-session -d -s "$SESSION" -n monitor 'ait monitor'
set_project_registry
exec tmux attach -t "$SESSION_T"
