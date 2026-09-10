#!/usr/bin/env bash
# tests/lib/frozen_fixtures.sh — the tmux/store fixture helpers shared by every
# live frozen-agent suite (t1705_8).
#
# `tests/test_freeze_engine_live.sh` (t1705_4) and
# `tests/test_restore_flows_live.sh` (t1705_5) grew the same thirteen helpers
# independently, and `tests/test_frozen_agents_acceptance.sh` needs all of them a
# third time. They are extracted here verbatim rather than re-implemented,
# because two of them are silent-failure traps if rewritten by hand:
#
#   * `pane_exists` — `display-message -p -t <gone pane>` exits ZERO with EMPTY
#     output, so the exit status says nothing. The OUTPUT is the signal.
#   * `agent_env` — the file it writes is SOURCED by a wrapper that then `exec`s
#     a separate program, so every line must carry `export`. A bare `NAME=value`
#     becomes a shell variable that `exec` does not pass on, and every
#     "controlled" case silently takes the happy path instead.
#
# CONTRACT. A sourcing suite must set these BEFORE the first call (not before
# the source — shell functions bind their variables at call time):
#
#   REAL_TMUX     absolute path to the real tmux binary
#   REAL_PATH     $PATH as it was before any fixture bin dir was prepended
#   SESSIONS_SH   path to the shipped aitask_agent_sessions.sh
#   FAKE_AGENT    path to tests/lib/fake_agent.sh (or a wrapper around it)
#   FIXTURE_DIR   the scratch dir `cleanup` removes
#   AGENT_ENV_FILE  only if agent_env / agent_env_clear are used
#
# Optional: FROZEN_WAIT_TRIES (default 120) is the poll count of every `wait_*`
# helper, at 0.1 s per try. The freeze suite pins it to 100 to keep its
# deliberately-timing-out indeterminate cases as short as they were before this
# extraction.

# The poll budget of every wait_* helper below, in 0.1 s units.
: "${FROZEN_WAIT_TRIES:=120}"

section() { echo; echo "=== $1 ==="; }

# --- tmux ------------------------------------------------------------------

# Always the REAL tmux: a suite may put a logging shim earlier on PATH to prove
# a coordinator ran detached, and the fixtures themselves must stay behind it.
tm() { "$REAL_TMUX" "$@"; }

pane_fmt() { tm display-message -p -t "$1" "$2" 2>/dev/null; }

# `display-message -p -t <gone pane>` exits ZERO with EMPTY output (measured on
# tmux 3.x), so the exit status says nothing about whether the pane exists. The
# output is the only usable signal — and it is why `agent_frozen_ops.pane_facts`
# and `pane_location` both validate the field count rather than the rc.
pane_exists() { [ -n "$(pane_fmt "$1" '#{pane_id}')" ]; }

window_exists() {
    tm list-windows -t "=$2" -F '#{window_name}' 2>/dev/null | grep -qxF "$1"
}

# --- store -----------------------------------------------------------------

store() { "$SESSIONS_SH" "$@"; }

record_of_pane() { pane_fmt "$1" '#{@aitask_record}'; }

record_field() { store show "$1" 2>/dev/null | sed -n "s/^$2://p"; }

# --- fixtures --------------------------------------------------------------

# An agent window rooted in a project dir. Echoes "<agent_pane> <companion_pane>".
# The companion is stamped the way the real minimonitor stamps ITSELF, so the
# cleanup script and the monitor both classify it as a helper.
make_agent_window() {
    local session="$1" window="$2" root="$3"
    local agent companion comp_pid
    agent="$(tm new-window -d -t "=$session" -n "$window" -c "$root" \
        -P -F '#{pane_id}' "$FAKE_AGENT")"
    companion="$(tm split-window -d -t "$agent" -c "$root" \
        -P -F '#{pane_id}' "sleep 1000")"
    comp_pid="$(pane_fmt "$companion" '#{pane_pid}')"
    tm set-option -p -t "$companion" @aitask_monitor_kind "minimonitor:$comp_pid"
    printf '%s %s\n' "$agent" "$companion"
}

wait_for_record_state() {
    local rid="$1" want="$2" i=0
    while [ "$i" -lt "$FROZEN_WAIT_TRIES" ]; do
        [ "$(record_field "$rid" state)" = "$want" ] && return 0
        sleep 0.1
        i=$((i + 1))
    done
    return 1
}

# Wait until the pane's `@aitask_standin_ready` names the record.
wait_for_ready() {
    local pane="$1" rid="$2" i=0
    while [ "$i" -lt "$FROZEN_WAIT_TRIES" ]; do
        [ "$(pane_fmt "$pane" '#{@aitask_standin_ready}')" = "$rid" ] && return 0
        sleep 0.1
        i=$((i + 1))
    done
    return 1
}

# Wait until a process is in the STOPPED state ('T'). Polling the real state is
# what makes the paused-coordinator cases honest: sleeping a fixed interval and
# hoping would race, and a race here reads as a spurious LEASE_HELD.
wait_stopped() {
    local pid="$1" i=0
    while [ "$i" -lt 100 ]; do
        case "$(ps -o state= -p "$pid" 2>/dev/null | tr -d ' ')" in
            T*) return 0 ;;
        esac
        sleep 0.1
        i=$((i + 1))
    done
    return 1
}

# --- per-case agent control -------------------------------------------------

# Set / clear the replacement agent's environment for ONE case.
#
# THE `export` IS LOAD-BEARING, NOT STYLE. `respawn-pane` runs its command in
# the TMUX SERVER's environment, captured at server start, so a per-case
# `FAKE_AGENT_EXIT=1 ./aitask_frozen.sh restore ...` in the test shell never
# reaches the replacement agent. The fixture `claude`/`codex` wrapper therefore
# SOURCES this file and `exec`s `fake_agent.sh` — a separate program that reads
# `${FAKE_AGENT_EXIT:-0}` and friends from its ENVIRONMENT. A bare
# `NAME=value` line would become a shell variable of the wrapper, which `exec`
# does not pass on, and the knob would be silently ignored.
agent_env() { printf 'export %s\n' "$@" > "$AGENT_ENV_FILE"; }
agent_env_clear() { : > "$AGENT_ENV_FILE"; }

# --- teardown ---------------------------------------------------------------

# Kill the isolated server and remove the fixture tree. `PATH="$REAL_PATH"` so a
# suite that shimmed tmux does not have its shim torn down by itself.
cleanup() {
    PATH="$REAL_PATH" "$REAL_TMUX" kill-server 2>/dev/null || true
    rm -rf "$FIXTURE_DIR" 2>/dev/null || true
}
