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

# `|` is the field separator throughout, not a space: a marker value contains
# `:` and IFS=' ' collapses runs, which silently shifts fields whenever a middle
# column is empty. With IFS='|' empty fields are preserved.

# 1. Kill shadow panes bound to the dying agent. A shadow's
#    @aitask_shadow_target holds the pane id of the agent it follows; match it
#    against the dying primary. Scoped to the whole session so a separate-window
#    shadow is reached too (falls back to the window if the session is unknown).
shadow_scope="${session:-$window}"
while IFS='|' read -r pane target; do
    if [ -n "$pane" ] && [ "$target" = "$primary" ]; then
        tmux kill-pane -t "$pane" 2>/dev/null || true
    fi
done < <(tmux list-panes -s -t "$shadow_scope" \
    -F '#{pane_id}|#{@aitask_shadow_target}' 2>/dev/null)

# 2. Count real-agent siblings in the window. A pane keeps companions alive only
#    if it is neither the dying primary, nor a companion pane, nor a shadow
#    helper.
#
#    Companion panes are DISCOVERED from @aitask_monitor_kind (t1451), not
#    trusted from "$companion". One pane-died hook carries one companion id and
#    the hook is append-only, so whichever companion armed it first is the only
#    one the argument can ever name: with a shadow-first ordering the argument
#    holds the shadow's pane, and a minimonitor sharing the window then counted
#    as a live AGENT sibling — sparing itself and, worse, keeping the named
#    companion alive on a bogus count. Job 1 already solved this shape for
#    shadows by matching a marker instead of an argument; this does the same.
#    "$companion" is still honoured as a fallback for a pane predating the
#    marker.
#
#    Liveness is deliberately NOT consulted here: this runs at pane death and is
#    killing panes, not deciding whether to launch. A stale-marked pane in a
#    window whose last real agent just died should be closed regardless.
others=0
companions=""
while IFS='|' read -r pane target kind; do
    [ -n "$pane" ] || continue
    [ "$pane" = "$primary" ] && continue
    if [ -n "$kind" ] || [ "$pane" = "$companion" ]; then
        companions="$companions $pane"
        continue
    fi
    [ -n "$target" ] && continue        # shadow helper
    others=$((others + 1))
done < <(tmux list-panes -t "$window" \
    -F '#{pane_id}|#{@aitask_shadow_target}|#{@aitask_monitor_kind}' 2>/dev/null)

if [ "$others" -eq 0 ]; then
    for pane in $companions; do
        tmux kill-pane -t "$pane" 2>/dev/null || true
    done
fi
tmux kill-pane -t "$primary" 2>/dev/null || true
