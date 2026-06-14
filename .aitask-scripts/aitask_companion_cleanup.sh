#!/usr/bin/env bash
# Pane-death cleanup for companion panes. Called via a tmux `pane-died` hook
# attached to a primary pane (e.g. lazygit or a coding agent). Two jobs:
#
#   1. Kill any *shadow* companion panes (t986) bound to the dying agent. A
#      shadow records the followed agent's pane id in the `@aitask_shadow_target`
#      pane user option, so when that agent ends its shadow must end too — even
#      if other agents still live in the window. Session-scoped, so a shadow
#      placed in a separate window (the configurable placement) is also cleaned.
#   2. Keep the minimonitor companion alive if any *real* agent sibling still
#      exists in the window (a user-added shell, another codeagent sharing the
#      companion, etc.). Shadow helper panes do NOT count as siblings.
#      Otherwise kill both primary and companion, letting tmux close the window
#      naturally.
#
# Usage: aitask_companion_cleanup.sh <primary_pane_id> <companion_pane_id>
#
# Raw `tmux` (no gateway / socket flag) is correct here BY DESIGN: hook
# commands run as tmux server jobs, and tmux fills `$TMUX` in the job
# environment, so every call below reaches exactly the server that fired the
# hook — including the dedicated `-L ait` server (t953) — with no flag needed.
set -euo pipefail

primary="${1:?primary pane id required}"
companion="${2:?companion pane id required}"

window="$(tmux display-message -p -t "$primary" "#{window_id}" 2>/dev/null || true)"
if [ -z "$window" ]; then
    exit 0
fi
session="$(tmux display-message -p -t "$primary" "#{session_id}" 2>/dev/null || true)"

# 1. Kill shadow panes bound to the dying agent. A shadow's
#    @aitask_shadow_target holds the pane id of the agent it follows; match it
#    against the dying primary. Scoped to the whole session so a separate-window
#    shadow is reached too (falls back to the window if the session is unknown).
shadow_scope="${session:-$window}"
while IFS=' ' read -r pane target; do
    if [ -n "$pane" ] && [ "$target" = "$primary" ]; then
        tmux kill-pane -t "$pane" 2>/dev/null || true
    fi
done < <(tmux list-panes -s -t "$shadow_scope" \
    -F '#{pane_id} #{@aitask_shadow_target}' 2>/dev/null)

# 2. Count real-agent siblings in the window. A pane keeps the companion alive
#    only if it is neither the dying primary, nor the companion, nor a shadow
#    helper (which carries @aitask_shadow_target).
others=0
while IFS=' ' read -r pane target; do
    if [ -n "$pane" ] && [ "$pane" != "$primary" ] && \
       [ "$pane" != "$companion" ] && [ -z "$target" ]; then
        others=$((others + 1))
    fi
done < <(tmux list-panes -t "$window" \
    -F '#{pane_id} #{@aitask_shadow_target}' 2>/dev/null)

if [ "$others" -eq 0 ]; then
    tmux kill-pane -t "$companion" 2>/dev/null || true
fi
tmux kill-pane -t "$primary" 2>/dev/null || true
