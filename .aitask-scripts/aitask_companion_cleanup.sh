#!/usr/bin/env bash
# Pane-death cleanup for companion minimonitor panes. Called via a tmux
# `pane-died` hook attached to a primary pane (e.g. lazygit). Keeps the
# companion alive if any other sibling pane still exists in the window
# (a user-added shell, a codeagent sharing the same companion, etc.).
# Otherwise kills both primary and companion, letting tmux close the window
# naturally.
#
# Usage: aitask_companion_cleanup.sh <primary_pane_id> <companion_pane_id>
set -euo pipefail

primary="${1:?primary pane id required}"
companion="${2:?companion pane id required}"

window="$(tmux display-message -p -t "$primary" "#{window_id}" 2>/dev/null || true)"
if [ -z "$window" ]; then
    exit 0
fi

others=0
while IFS= read -r pane; do
    if [ -n "$pane" ] && [ "$pane" != "$primary" ] && [ "$pane" != "$companion" ]; then
        others=$((others + 1))
    fi
done < <(tmux list-panes -t "$window" -F '#{pane_id}' 2>/dev/null)

if [ "$others" -eq 0 ]; then
    tmux kill-pane -t "$companion" 2>/dev/null || true
fi
tmux kill-pane -t "$primary" 2>/dev/null || true
