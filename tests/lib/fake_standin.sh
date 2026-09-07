#!/usr/bin/env bash
# tests/lib/fake_standin.sh — a stand-in for the frozen-agent viewer TUI.
#
# The real viewer is `ait frozenagent --record <id>` and does not exist until
# t1705_6. Live freeze tests point `AITASKS_FROZEN_STANDIN_CMD` at this script
# instead, so the freeze transaction's step 5 (`respawn-pane -k` into the
# stand-in command) can be exercised end to end today.
#
# It reproduces exactly the one behaviour reconcile depends on: **the viewer
# stamps its OWN pane** with `@aitask_standin_ready=<record id>` after mounting.
# That is the `mark_monitor_pane` rule — only an app stamps its own pane —
# and the stamp is the only positive evidence that separates "stamped, viewer
# up" from "stamped, agent still running".
#
# The record id is NOT passed as an argument, because
# `AITASKS_FROZEN_STANDIN_CMD` is one fixed string for the whole process and
# every pane would then get the same id. It is read from the pane's own
# `@aitask_frozen`, which the freeze engine stamped immediately before the
# respawn and which survives it (pane options are pane-scoped, not
# process-scoped) — the same place the real viewer will read it from.
#
# Usage (via the env seam, never directly):
#   AITASKS_FROZEN_STANDIN_CMD=/path/to/fake_standin.sh
#   FAKE_STANDIN_NO_STAMP=1   -> mount but NEVER stamp: models a viewer that is
#                                still booting, or one that is broken. This is
#                                the fixture for reconcile's INDETERMINATE row.
#   FAKE_STANDIN_SLEEP=<n>    -> foreground sleep duration (default 1000)
#
# Like `fake_agent.sh` this ends in a FOREGROUND `exec sleep`: nothing may fork,
# or `#{pane_pid}` would stop naming this process and every `standin_pid`
# assertion built on it would be measuring a shell instead.
set -uo pipefail

FAKE_STANDIN_SLEEP="${FAKE_STANDIN_SLEEP:-1000}"

# `$TMUX_PANE` is set by tmux in every pane's environment, including one created
# by `respawn-pane`. Using it (rather than a `display-message` round trip) is
# what makes this self-identification and not a guess about which pane we are.
pane="${TMUX_PANE:-}"

if [ -n "$pane" ] && [ "${FAKE_STANDIN_NO_STAMP:-0}" != "1" ]; then
    # Read the id the freeze engine stamped, then stamp readiness with it. A
    # missing or malformed value means we were not respawned by a freeze; stamp
    # nothing rather than inventing an id, so the pane lands on reconcile's
    # indeterminate row instead of falsely claiming a viewer is up.
    record="$(tmux display-message -p -t "$pane" '#{@aitask_frozen}' 2>/dev/null || true)"
    if [[ "$record" =~ ^[0-9a-f]{8}$ ]]; then
        tmux set-option -p -t "$pane" @aitask_standin_ready "$record" 2>/dev/null || true
        echo "fake_standin: mounted for record $record"
    else
        echo "fake_standin: no usable @aitask_frozen on $pane — not stamping" >&2
    fi
else
    echo "fake_standin: mounted without stamping (FAKE_STANDIN_NO_STAMP)"
fi

exec sleep "$FAKE_STANDIN_SLEEP"
