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

command -v tmux >/dev/null || die "tmux is not installed. Install it first, then re-run 'ait ide'."

if [[ -n "${TMUX:-}" ]]; then
    current_session=$(tmux display-message -p '#S')
    if [[ "$current_session" != "$SESSION" ]]; then
        warn "Already inside tmux session '$current_session', but configured session is '$SESSION'."
        warn "Refusing to nest tmux. Either detach (Ctrl-b d) and re-run 'ait ide', or"
        warn "pass '--session $current_session' to use the current session."
        exit 1
    fi
    if tmux list-windows -F '#{window_name}' | grep -qx 'monitor'; then
        exec tmux select-window -t "$SESSION:monitor"
    else
        exec tmux new-window -n monitor 'ait monitor'
    fi
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
    if ! tmux list-windows -t "$SESSION" -F '#{window_name}' | grep -qx 'monitor'; then
        tmux new-window -t "$SESSION:" -n monitor 'ait monitor'
    fi
    exec tmux attach -t "$SESSION" \; select-window -t "$SESSION:monitor"
fi

exec tmux new-session -s "$SESSION" -n monitor 'ait monitor'
