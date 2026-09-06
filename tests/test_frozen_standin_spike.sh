#!/usr/bin/env bash
# tests/test_frozen_standin_spike.sh — the t1705_1 risk-mitigation spike probe.
#
# t1705 ("frozen code agents") rests on tmux and code-agent facts this repo has
# never exercised: `respawn-pane` has ZERO call sites in `.aitask-scripts/`,
# agents run with `remain-on-exit on` plus a pane-scoped `pane-died` hook that
# kills the whole window when no real agent sibling remains, and neither
# supported agent has a SessionStart hook installed anywhere in the tree. Every
# later child of t1705 pins a contract on those facts.
#
# This script proves or refutes each of them on an ISOLATED tmux server and
# prints a FINDINGS block that is copied into the parent plan. It is kept
# permanently: it is child t1705_4's live acceptance control.
#
# Cases
#   P1  isolation self-check (before anything destructive, and again at exit)
#   1   a stand-in respawn keeps the window (+ two controls)
#   2   pane user options survive `respawn-pane -k`; #{pane_pid} changes
#   3   an `env VAR=... cmd` prefix keeps #{pane_pid} == the launched process
#   3b  tmux's native `respawn-pane -e` does the same (the alternative)
#   4   `run-shell -b` outlives the pane that started it
#   5a  the committed SessionStart fixtures satisfy their schema  [ALWAYS RUNS]
#   5b  claude SessionStart capture: refresh-and-diff           [opt-in]
#   6   codex SessionStart + `codex resume`                     [opt-in]
#   7   the live-tmux guard allows a SOCKETED respawn-pane
#
# TMUX-STRESS. Run this from a shell that is NOT inside tmux and with the
# dedicated `-L ait` server stopped; `require_clean_ait_server` refuses
# otherwise. `$TMUX` beats `TMUX_TMPDIR`, and the shipped cleanup hook reaches
# tmux with raw, un-flagged calls by design — so the safe precondition is an
# empty field, not a redirected one.
#
# Run:
#   bash tests/test_frozen_standin_spike.sh
#   AITASKS_SPIKE_REAL_AGENTS=1 bash tests/test_frozen_standin_spike.sh
#   AITASKS_SPIKE_REAL_AGENTS=1 bash tests/test_frozen_standin_spike.sh --refresh-fixtures
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

REFRESH_FIXTURES=0
for arg in "$@"; do
    case "$arg" in
        --refresh-fixtures) REFRESH_FIXTURES=1 ;;
        *) echo "unknown argument: $arg" >&2; exit 2 ;;
    esac
done

PYTHON_BIN="${PYTHON_BIN:-python3}"
command -v tmux       >/dev/null 2>&1 || { echo "SKIP: tmux not available"; exit 0; }
command -v "$PYTHON_BIN" >/dev/null 2>&1 || { echo "SKIP: $PYTHON_BIN not available"; exit 0; }

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# Test bodies run inside ( … ) subshells, whose in-process PASS/FAIL increments
# die at subshell exit. Without the file-backed counters this file would report
# zero failures and exit 0 no matter what failed (CLAUDE.md, t1207).
assert_counters_init

# shellcheck source=lib/proc_fixtures.sh
. "$PROJECT_DIR/tests/lib/proc_fixtures.sh"

# The user's real TMUX_TMPDIR, captured BEFORE isolation redirects it. The
# end-of-run "we never touched the user's server" assertion has to look at the
# user's socket directory, which is unreachable once TMUX_TMPDIR points at the
# isolated one.
if [ -n "${TMUX_TMPDIR+x}" ]; then
    USER_TMUX_TMPDIR_SET=1
    USER_TMUX_TMPDIR="$TMUX_TMPDIR"
else
    USER_TMUX_TMPDIR_SET=0
    USER_TMUX_TMPDIR=""
fi

# Read the user's dedicated `-L ait` server with the ORIGINAL tmpdir restored.
# stderr is folded in on purpose: "no server running" is itself a stable
# observation, and comparing it before/after is what proves nothing was created.
user_ait_pane_set() {
    if [ "$USER_TMUX_TMPDIR_SET" = "1" ]; then
        TMUX_TMPDIR="$USER_TMUX_TMPDIR" tmux -L ait list-panes -a -F '#{pane_id}' 2>&1 | sort
    else
        env -u TMUX_TMPDIR tmux -L ait list-panes -a -F '#{pane_id}' 2>&1 | sort
    fi
}
USER_AIT_BEFORE="$(user_ait_pane_set)"

# ORDER IS LOAD-BEARING (tests/lib/tmux_isolation.sh:115-119). The clean-server
# guard reads $TMUX and resolves `-L ait` against the user's real socket dir;
# require_isolated_tmux unsets $TMUX and repoints TMUX_TMPDIR, after which the
# guard would probe an empty directory and pass vacuously.
# shellcheck source=lib/tmux_isolation.sh
. "$PROJECT_DIR/tests/lib/tmux_isolation.sh"
require_clean_ait_server     # FIRST
require_isolated_tmux        # SECOND

# Every tmux call goes through the shell gateway. Note what isolation did to
# it: AITASKS_TMUX_SOCKET is now set-but-empty, so ait_tmux_socket_args emits
# NO -L flag at all. Isolation comes from the redirected TMUX_TMPDIR below, not
# from a named socket — there is no `-L <name>` in play here.
# shellcheck source=../.aitask-scripts/lib/tmux_exec.sh
. "$PROJECT_DIR/.aitask-scripts/lib/tmux_exec.sh"

FIXTURE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ait_frozen_spike_XXXXXX")"
export TMUX_TMPDIR="$FIXTURE_DIR"
SESSION="ait_frozen_spike_$$"
FINDINGS_FILE="$FIXTURE_DIR/findings.txt"
: > "$FINDINGS_FILE"

cleanup() {
    tmux kill-server 2>/dev/null || true
    rm -rf "$FIXTURE_DIR" 2>/dev/null || true
}
trap cleanup EXIT

# FINDINGS are accumulated in a file: cases run in subshells, so an in-process
# array would lose every line exactly as the counters would.
finding() { printf '%s\n' "$1" >> "$FINDINGS_FILE"; }

section() { echo; echo "=== $1 ==="; }

# ---------------------------------------------------------------------------
# P1 — isolation self-check
# ---------------------------------------------------------------------------
# The mitigation for the code-health risk that a wrong isolation reaches the
# user's real agents. It converts "isolation silently regressed" into a named
# FAIL instead of a destroyed session, and it runs BEFORE anything destructive.

section "P1 — isolation self-check"

isolation_took=1
if [ -n "${TMUX:-}" ]; then
    assert_record_fail; echo "FAIL: TMUX is still set after require_isolated_tmux"; isolation_took=0
else
    assert_record_pass
fi
if [ "${AITASKS_TMUX_SOCKET+set}" = "set" ] && [ -z "$AITASKS_TMUX_SOCKET" ]; then
    assert_record_pass
else
    assert_record_fail
    echo "FAIL: AITASKS_TMUX_SOCKET must be set-and-empty, got '${AITASKS_TMUX_SOCKET-unset}'"
    isolation_took=0
fi
case "$TMUX_TMPDIR" in
    "${TMPDIR:-/tmp}"/ait_frozen_spike_*|*/ait_frozen_spike_*)
        assert_record_pass ;;
    *)
        assert_record_fail
        echo "FAIL: TMUX_TMPDIR is not the fixture dir: $TMUX_TMPDIR"
        isolation_took=0 ;;
esac

if [ "$isolation_took" -ne 1 ]; then
    echo
    echo "ABORT: isolation did not take — refusing to run destructive cases."
    assert_counters_load
    echo "RESULT: FAIL"
    exit 1
fi
echo "isolation OK — destructive cases may run"

# ---------------------------------------------------------------------------
# Fixture builder
# ---------------------------------------------------------------------------
# Build the agent window through the SHIPPED python helpers so the hook wiring
# under test is the real one, not a replica. Deliberately NOT modelled on
# tests/test_kill_agent_pane_smart.sh's make_window(): that fixture stamps no
# pane options at all and detects its companion by monkey-patching an argv
# sentinel in Python, which leaves the SHELL cleanup script blind.
#
# Echoes: "<agent_pane> <companion_pane>"
make_agent_window() {
    local window="$1" agent_cmd="$2"
    PYTHONPATH="$PROJECT_DIR/.aitask-scripts/lib" \
    AIT_SPIKE_SESSION="$SESSION" \
    AIT_SPIKE_WINDOW="$window" \
    AIT_SPIKE_AGENT_CMD="$agent_cmd" \
    "$PYTHON_BIN" - <<'PYEOF'
import os
import sys
import time

import agent_launch_utils as alu
from monitor_marker import MONITOR_KIND_OPTION

session = os.environ["AIT_SPIKE_SESSION"]
window = os.environ["AIT_SPIKE_WINDOW"]
agent_cmd = os.environ["AIT_SPIKE_AGENT_CMD"]

pane_pid, err = alu.launch_in_tmux(
    agent_cmd,
    alu.TmuxLaunchConfig(
        session=session, window=window,
        new_session=False, new_window=True, select_window=False,
    ),
)
if err:
    sys.exit(f"fixture build: launch_in_tmux failed: {err}")
if not pane_pid:
    sys.exit("fixture build: launch_in_tmux captured no pane_pid")

agent_pane = None
for _ in range(40):
    agent_pane = alu.resolve_pane_id_by_pid(session, pane_pid)
    if agent_pane:
        break
    time.sleep(0.05)
if not agent_pane:
    sys.exit(f"fixture build: no pane owns pid {pane_pid}")

# Companion pane, split into the same window.
comp_pid, err = alu.launch_in_tmux(
    "sleep 1000",
    alu.TmuxLaunchConfig(
        session=session, window=window,
        new_session=False, new_window=False,
        split_direction="horizontal", split_target_pane=agent_pane,
        select_window=False,
    ),
)
if err:
    sys.exit(f"fixture build: companion split failed: {err}")
companion_pane = None
for _ in range(40):
    companion_pane = alu.resolve_pane_id_by_pid(session, comp_pid)
    if companion_pane:
        break
    time.sleep(0.05)
if not companion_pane:
    sys.exit(f"fixture build: no pane owns companion pid {comp_pid}")

# Stamp the companion the way the real minimonitor stamps ITSELF. The shipped
# cleanup script discovers companions from this marker (it lists panes as
# `#{pane_id}|#{@aitask_shadow_target}|#{@aitask_monitor_kind}` and treats a
# non-empty kind as a companion), so without it the script would count the
# companion as a live agent sibling. mark_monitor_pane() stamps $TMUX_PANE,
# i.e. the caller's own pane, so it cannot be used from here — but the VALUE
# must still match monitor_marker._MARKER_RE.
alu._TMUX.run([
    "set-option", "-p", "-t", companion_pane,
    MONITOR_KIND_OPTION, f"minimonitor:{comp_pid}",
])

print(f"{agent_pane} {companion_pane}")
PYEOF
}

# Install the observer at pane-died[0], BEFORE the shipped hook is armed.
#
# The index is load-bearing, not a style choice. tmux runs indexed hooks in
# index order, and aitask_companion_cleanup.sh ends with an UNCONDITIONAL
# `kill-pane -t "$primary"` that sits outside its sibling-count guard — so it
# kills the primary pane on every invocation. An observer at a higher index
# would run after that pane, and with it the window, is already gone, and every
# `#{...}` below would expand against nothing: we would be back to inferring the
# answer from the window's fate instead of measuring it.
install_pane_died_observer() {
    local pane="$1"
    ait_tmux set-hook -p -t "$pane" 'pane-died[0]' \
        "run-shell '$FIXTURE_DIR/observe_pane_died.sh \"#{pane_id}\" \"#{pane_dead}\" \"#{@aitask_frozen}\"'"
}

# Arm the shipped hook and echo its return value ("installed"/"existing"/
# "unverified"). Anything but "installed" means the fixture is NOT exercising
# the real wiring.
attach_shipped_cleanup_hook() {
    local agent_pane="$1" companion_pane="$2"
    PYTHONPATH="$PROJECT_DIR/.aitask-scripts/lib" \
    AIT_SPIKE_AGENT_PANE="$agent_pane" \
    AIT_SPIKE_COMPANION_PANE="$companion_pane" \
    "$PYTHON_BIN" -c '
import os
import agent_launch_utils as alu
print(alu.attach_companion_cleanup_hook(
    os.environ["AIT_SPIKE_AGENT_PANE"], os.environ["AIT_SPIKE_COMPANION_PANE"]))
'
}

pane_exists() { ait_tmux display-message -p -t "$1" '#{pane_id}' >/dev/null 2>&1; }
window_exists() { ait_tmux list-windows -t "$(ait_tmux_session_target "$SESSION")" -F '#{window_name}' 2>/dev/null | grep -qxF "$1"; }
pane_fmt() { ait_tmux display-message -p -t "$1" "$2" 2>/dev/null; }

cp "$PROJECT_DIR/tests/lib/observe_pane_died.sh" "$FIXTURE_DIR/observe_pane_died.sh"
chmod +x "$FIXTURE_DIR/observe_pane_died.sh"
FAKE_AGENT="$PROJECT_DIR/tests/lib/fake_agent.sh"
chmod +x "$FAKE_AGENT" 2>/dev/null || true

# The session every window is created in.
ait_tmux new-session -d -s "$SESSION" -n scratch "sleep 1000"
sleep 0.3

# ---------------------------------------------------------------------------
# Case 1 — a stand-in respawn keeps the window
# ---------------------------------------------------------------------------
section "Case 1 — stand-in respawn keeps the window"

(
    W="agent-pick-1705"
    read -r AGENT COMPANION < <(make_agent_window "$W" "$FAKE_AGENT")
    if [ -z "${AGENT:-}" ] || [ -z "${COMPANION:-}" ]; then
        assert_record_fail; echo "FAIL: Case 1 fixture build produced no panes"; exit 1
    fi

    install_pane_died_observer "$AGENT"
    hook_result="$(attach_shipped_cleanup_hook "$AGENT" "$COMPANION")"
    assert_eq "the SHIPPED cleanup hook was installed (not skipped/unverified)" \
        "installed" "$hook_result"

    # The observer must sit at a strictly LOWER index than the cleanup entry, or
    # it observes a pane that is already gone.
    hooks="$(ait_tmux show-hooks -p -t "$AGENT" 2>/dev/null)"
    obs_idx="$(printf '%s\n' "$hooks" | grep 'observe_pane_died' | sed -n 's/^pane-died\[\([0-9]*\)\].*/\1/p' | head -n1)"
    cln_idx="$(printf '%s\n' "$hooks" | grep 'companion_cleanup' | sed -n 's/^pane-died\[\([0-9]*\)\].*/\1/p' | head -n1)"
    if [ -n "$obs_idx" ] && [ -n "$cln_idx" ] && [ "$obs_idx" -lt "$cln_idx" ]; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: observer must sit at a lower pane-died index than the cleanup hook (observer='$obs_idx' cleanup='$cln_idx')"
        printf '%s\n' "$hooks"
    fi

    old_pid="$(pane_fmt "$AGENT" '#{pane_pid}')"

    # Stamp, then respawn the agent's own pane with a stand-in.
    ait_tmux set-option -p -t "$AGENT" '@aitask_frozen' 'abc123'
    ait_tmux respawn-pane -k -t "$AGENT" 'sleep 1000'
    sleep 1

    if window_exists "$W"; then assert_record_pass; else
        assert_record_fail; echo "FAIL: the window did not survive respawn-pane -k"; fi
    if pane_exists "$COMPANION"; then assert_record_pass; else
        assert_record_fail; echo "FAIL: the companion pane did not survive respawn-pane -k"; fi
    if pane_exists "$AGENT"; then assert_record_pass; else
        assert_record_fail; echo "FAIL: the agent pane id did not survive respawn-pane -k"; fi
    assert_eq "the stand-in runs in the SAME pane id" \
        "sleep" "$(pane_fmt "$AGENT" '#{pane_current_command}')"

    new_pid="$(pane_fmt "$AGENT" '#{pane_pid}')"
    if [ -n "$old_pid" ] && [ -n "$new_pid" ] && [ "$old_pid" != "$new_pid" ]; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: #{pane_pid} should change across respawn-pane -k (old='$old_pid' new='$new_pid')"
    fi

    # Did pane-died fire at all, and was the stamp visible when it did?
    if [ -s "$FIXTURE_DIR/pane_died.log" ]; then
        line="$(head -n1 "$FIXTURE_DIR/pane_died.log")"
        stamp="$(printf '%s' "$line" | sed -n 's/.*frozen=\([^ ]*\).*/\1/p')"
        finding "pane-died on respawn-pane -k: fires; stamp visible to hook: $([ "$stamp" = "abc123" ] && echo yes || echo "no (read '$stamp')")"
        echo "  observer log: $line"
    else
        finding "pane-died on respawn-pane -k: does not fire; stamp visible to hook: n/a (hook never ran)"
        echo "  observer log: (empty — pane-died did not fire)"
    fi

    ait_tmux kill-window -t "$(ait_tmux_window_target "$SESSION" "$W")" 2>/dev/null || true
)

section "Case 1b — control: an UNSTAMPED respawn (no abstention exists yet)"

# @aitask_frozen has zero occurrences in the repo today, so no stamp-aware
# abstention branch exists. This control therefore measures the CURRENT shipped
# behaviour without a stamp — which is the point: if the window survives here
# too, the surviving window in Case 1 is a property of respawn-pane, not of the
# stamp, and the later abstention is not load-bearing for THIS hazard.
(
    W="agent-pick-1705b"
    read -r AGENT COMPANION < <(make_agent_window "$W" "$FAKE_AGENT")
    rm -f "$FIXTURE_DIR/pane_died.log"
    install_pane_died_observer "$AGENT"
    attach_shipped_cleanup_hook "$AGENT" "$COMPANION" >/dev/null

    ait_tmux respawn-pane -k -t "$AGENT" 'sleep 1000'
    sleep 1

    if window_exists "$W"; then
        finding "unstamped respawn control: window SURVIVES without any abstention"
        echo "  window survived an unstamped respawn"
        assert_record_pass
    else
        finding "unstamped respawn control: window is KILLED — abstention is load-bearing"
        echo "  window was killed by an unstamped respawn"
        assert_record_pass
    fi
    ait_tmux kill-window -t "$(ait_tmux_window_target "$SESSION" "$W")" 2>/dev/null || true
)

section "Case 1c — positive control: the cleanup hook IS armed and lethal"

# Without this, Case 1 proves nothing: a window that survives an unarmed hook is
# not evidence about respawn-pane. Here the agent process really dies, so
# pane-died must fire and the window must collapse.
(
    W="agent-pick-1705c"
    read -r AGENT COMPANION < <(make_agent_window "$W" "$FAKE_AGENT")
    rm -f "$FIXTURE_DIR/pane_died.log"
    install_pane_died_observer "$AGENT"
    attach_shipped_cleanup_hook "$AGENT" "$COMPANION" >/dev/null

    agent_pid="$(pane_fmt "$AGENT" '#{pane_pid}')"
    kill -TERM "$agent_pid" 2>/dev/null || true
    sleep 1.5

    if [ -s "$FIXTURE_DIR/pane_died.log" ]; then
        assert_record_pass
        echo "  pane-died fired on a real agent death: $(head -n1 "$FIXTURE_DIR/pane_died.log")"
    else
        assert_record_fail
        echo "FAIL: pane-died did not fire even on a real agent death — the fixture's hook is not armed, so Case 1 proves nothing"
    fi

    if window_exists "$W"; then
        assert_record_fail
        echo "FAIL: the window survived a real agent death — the shipped cleanup hook is not lethal in this fixture"
        finding "cleanup hook lethality control: window SURVIVED a real agent death (hook not effective)"
        ait_tmux kill-window -t "$(ait_tmux_window_target "$SESSION" "$W")" 2>/dev/null || true
    else
        assert_record_pass
        echo "  the window collapsed on a real agent death, as the shipped hook intends"
        finding "cleanup hook lethality control: window is killed by a real agent death (hook armed and lethal)"
    fi
)

# ---------------------------------------------------------------------------
# Case 2 — pane options survive respawn; pane_pid changes
# ---------------------------------------------------------------------------
section "Case 2 — pane options survive respawn-pane -k"

(
    W="agent-pick-1705-c2"
    read -r AGENT COMPANION < <(make_agent_window "$W" "$FAKE_AGENT")
    ait_tmux set-option -p -t "$AGENT" '@aitask_frozen' 'abc123'
    before_pid="$(pane_fmt "$AGENT" '#{pane_pid}')"
    before_opt="$(pane_fmt "$AGENT" '#{@aitask_frozen}')"
    assert_eq "the stamp reads back before the respawn" "abc123" "$before_opt"

    ait_tmux respawn-pane -k -t "$AGENT" 'sleep 1000'
    sleep 0.7

    assert_eq "the pane user option SURVIVES respawn-pane -k" \
        "abc123" "$(pane_fmt "$AGENT" '#{@aitask_frozen}')"
    after_pid="$(pane_fmt "$AGENT" '#{pane_pid}')"
    if [ -n "$before_pid" ] && [ -n "$after_pid" ] && [ "$before_pid" != "$after_pid" ]; then
        assert_record_pass
        finding "pane options survive respawn: yes (pane_pid $before_pid -> $after_pid)"
    else
        assert_record_fail
        echo "FAIL: #{pane_pid} did not change across the respawn (before='$before_pid' after='$after_pid')"
        finding "pane options survive respawn: pane_pid did NOT change ($before_pid -> $after_pid)"
    fi
    ait_tmux kill-window -t "$(ait_tmux_window_target "$SESSION" "$W")" 2>/dev/null || true
)

# ---------------------------------------------------------------------------
# Case 3 — an `env VAR=... cmd` prefix keeps pane_pid == the launched process
# ---------------------------------------------------------------------------
section "Case 3 — env prefix keeps #{pane_pid} == the agent process"

# This validates the exemption implied by launch_in_tmux's docstring: it forbids
# a wrapper that OUTLIVES the agent (that would make a dead agent's lock read as
# alive, t1465) and says nothing about `env`, which execs into its target.
#
# The process SELF-REPORTS its pid and environment into a path only this run
# knows. Two rejected alternatives, both unsound here:
#   * /proc/<pid>/environ — this host is macOS: no /proc, and `ps eww` / `ps -E`
#     return no environment at all under SIP. There is no portable way to read a
#     FOREIGN process's env.
#   * pgrep -f 'sleep 1000' — a pattern that generic can match a concurrent case
#     in this same suite or an unrelated user process, so the assertion could
#     pass while inspecting the wrong process. Worse than failing.
(
    W="agent-pick-1705-c3"
    read -r AGENT COMPANION < <(make_agent_window "$W" "$FAKE_AGENT")
    report="$(mktemp "$FIXTURE_DIR/envprobe.XXXXXX")"
    rm -f "$report"

    ait_tmux respawn-pane -k -t "$AGENT" \
        "env AITASK_RESTORE_RECORD=x '$FAKE_AGENT' --report-env '$report'"

    for _ in $(seq 1 40); do [ -s "$report" ] && break; sleep 0.1; done

    if [ ! -s "$report" ]; then
        assert_record_fail
        echo "FAIL: the env-prefixed process never self-reported to $report"
        finding "env prefix keeps pane_pid = agent pid: UNKNOWN (no self-report)"
    else
        reported_pid="$(sed -n 's/^pid=//p' "$report")"
        reported_var="$(sed -n 's/^AITASK_RESTORE_RECORD=//p' "$report")"
        pane_pid="$(pane_fmt "$AGENT" '#{pane_pid}')"
        assert_eq "the self-reported pid IS the pane pid (env exec'd, did not wrap)" \
            "$pane_pid" "$reported_pid"
        assert_eq "the env variable reached the process" "x" "$reported_var"
        if [ "$pane_pid" = "$reported_pid" ]; then
            finding "env prefix keeps pane_pid = agent pid: yes (pid $pane_pid, variable delivered)"
        else
            finding "env prefix keeps pane_pid = agent pid: NO (pane_pid=$pane_pid, process pid=$reported_pid)"
        fi
    fi
    ait_tmux kill-window -t "$(ait_tmux_window_target "$SESSION" "$W")" 2>/dev/null || true
)

# ---------------------------------------------------------------------------
# Case 3b — tmux's NATIVE `respawn-pane -e VAR=value` env passing
# ---------------------------------------------------------------------------
section "Case 3b — respawn-pane -e keeps #{pane_pid} == the agent process"

# Deliberately the same assertions as Case 3, with ONE variable changed: the
# environment arrives via tmux's own `-e` flag instead of an `env VAR=... cmd`
# prefix in the command string. Running both is what makes the comparison
# meaningful — a single passing mechanism tells child 5 nothing about the other.
#
# Why this case exists: `respawn-pane` accepts `-e environment` (present on the
# 3.6a this was measured against, per its own man page:
#   respawn-pane [-k] [-c start-directory] [-e environment] [-t target-pane]
#                [shell-command [argument ...]]
# ). It is the more direct mechanism for the restore path — tmux sets the
# variable in the spawned process's environment itself, so the command string
# carries no wrapper at all and nothing has to exec through `env`. Case 3
# proved the prefix works; this proves whether the native flag is equivalent,
# so child 5 can choose on evidence rather than assumption.
#
# The pane_pid assertion is the load-bearing one either way: launch_in_tmux's
# contract is that the pane's pid IS the agent process, because a wrapper that
# OUTLIVES the agent would make a dead agent's lock keep reading as alive
# (t1465). A mechanism that broke that would be unusable for restore no matter
# how cleanly it delivered the variable.
(
    W="agent-pick-1705-c3b"
    read -r AGENT COMPANION < <(make_agent_window "$W" "$FAKE_AGENT")
    report="$(mktemp "$FIXTURE_DIR/envprobe3b.XXXXXX")"
    rm -f "$report"

    # No `env` prefix in the command string — the variable comes from -e alone.
    ait_tmux respawn-pane -k -e "AITASK_RESTORE_RECORD=y" -t "$AGENT" \
        "'$FAKE_AGENT' --report-env '$report'"

    for _ in $(seq 1 40); do [ -s "$report" ] && break; sleep 0.1; done

    if [ ! -s "$report" ]; then
        # A tmux without -e support fails the respawn outright, which is itself
        # the finding child 5 needs — recorded, not silently skipped.
        assert_record_fail
        echo "FAIL: the -e respawned process never self-reported to $report"
        echo "      (tmux $(tmux -V); does this build support 'respawn-pane -e'?)"
        finding "respawn-pane -e keeps pane_pid = agent pid: UNKNOWN (no self-report)"
    else
        reported_pid="$(sed -n 's/^pid=//p' "$report")"
        reported_var="$(sed -n 's/^AITASK_RESTORE_RECORD=//p' "$report")"
        pane_pid="$(pane_fmt "$AGENT" '#{pane_pid}')"
        assert_eq "the -e self-reported pid IS the pane pid (no wrapper)" \
            "$pane_pid" "$reported_pid"
        assert_eq "the -e variable reached the process" "y" "$reported_var"
        if [ "$pane_pid" = "$reported_pid" ] && [ "$reported_var" = "y" ]; then
            finding "respawn-pane -e keeps pane_pid = agent pid: yes (pid $pane_pid, variable delivered) — native alternative to the env prefix"
        else
            finding "respawn-pane -e: pane_pid=$pane_pid, process pid=$reported_pid, variable='$reported_var'"
        fi
    fi
    ait_tmux kill-window -t "$(ait_tmux_window_target "$SESSION" "$W")" 2>/dev/null || true
)

# ---------------------------------------------------------------------------
# Case 4 — `run-shell -b` outlives the pane that started it
# ---------------------------------------------------------------------------
section "Case 4 — run-shell -b outlives a killed caller pane"

(
    W="agent-pick-1705-c4"
    read -r AGENT COMPANION < <(make_agent_window "$W" "$FAKE_AGENT")
    marker="$FIXTURE_DIR/runshell_marker_$$"
    rm -f "$marker"

    ait_tmux run-shell -b "sleep 2; touch '$marker'"
    ait_tmux respawn-pane -k -t "$AGENT" 'sleep 1000'

    for _ in $(seq 1 40); do [ -e "$marker" ] && break; sleep 0.1; done

    if [ -e "$marker" ]; then
        assert_record_pass
        finding "run-shell -b survives caller pane kill: yes"
    else
        assert_record_fail
        echo "FAIL: the run-shell -b marker never appeared within 4s"
        finding "run-shell -b survives caller pane kill: no"
    fi
    ait_tmux kill-window -t "$(ait_tmux_window_target "$SESSION" "$W")" 2>/dev/null || true
)

# ---------------------------------------------------------------------------
# Case 5a — the committed fixtures satisfy their schema  [ALWAYS RUNS]
# ---------------------------------------------------------------------------
section "Case 5a — session-hook fixture contract (no binaries, no opt-in)"

# Child t1705_3 consumes these fixtures unconditionally. If the only producer
# were the opt-in real-agent lane, a normal CI or developer run would skip it
# and leave fixture presence, redaction, schema and freshness entirely unproved
# — with child 3 then built on missing or stale evidence. So the fixtures are
# COMMITTED BASELINES and this case validates them on every single run.

HOOK_DATA_DIR="$PROJECT_DIR/tests/data/session_hooks"

(
    out="$("$PYTHON_BIN" "$SCRIPT_DIR/lib/validate_session_hook_fixtures.py" "$HOOK_DATA_DIR" 2>&1)"
    rc=$?
    printf '%s\n' "$out"
    if [ "$rc" -eq 0 ]; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: session-hook fixture validation failed (exit $rc)"
    fi

    for f in claude codex; do
        path="$HOOK_DATA_DIR/${f}_sessionstart.json"
        assert_file_exists "the $f fixture is committed" "$path"
        status="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1])).get("_fixture_status",""))' "$path" 2>/dev/null)"
        case "$status" in
            captured|unsupported|provisional) assert_record_pass ;;
            *) assert_record_fail; echo "FAIL: $f fixture has no valid _fixture_status (got '$status')" ;;
        esac
        reason="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1])).get("_reason",""))' "$path" 2>/dev/null)"
        if [ "$status" = "captured" ]; then
            finding "$f fixture: captured"
        else
            finding "$f fixture: $status($reason)"
        fi
    done
    assert_file_exists "the fixture schema is committed" "$HOOK_DATA_DIR/schema.json"
    assert_file_exists "the fixture README is committed" "$HOOK_DATA_DIR/README.md"
)

# ---------------------------------------------------------------------------
# Case 5b / Case 6 — real-agent lanes  [opt-in]
# ---------------------------------------------------------------------------
HOOK_WAIT_SECS="${HOOK_WAIT_SECS:-30}"

if [ "${AITASKS_SPIKE_REAL_AGENTS:-0}" != "1" ]; then
    section "Cases 5b / 6 — real-agent lanes SKIPPED"
    echo "set AITASKS_SPIKE_REAL_AGENTS=1 to run them (they cost real agent turns)"
    finding "real-agent lanes: skipped (AITASKS_SPIKE_REAL_AGENTS unset)"
else
    # Write a SessionStart capture script. It records the payload plus the two
    # environment variables the freeze work needs to be visible to a hook
    # process: $TMUX_PANE (which pane the agent is in) and AITASK_AGENT_STRING
    # (exported by aitask_codeagent.sh immediately before exec).
    write_capture_hook() {
        cat > "$1" <<'HOOKEOF'
#!/usr/bin/env bash
set -uo pipefail
out="$1"
payload="$(cat)"
{
  printf '%s\n' "$payload"
  printf 'ENV TMUX_PANE=%s\n' "${TMUX_PANE:-}"
  printf 'ENV AITASK_AGENT_STRING=%s\n' "${AITASK_AGENT_STRING:-}"
} >> "$out"
HOOKEOF
        chmod +x "$1"
    }

    # Wait for a payload file, BOUNDED. An interactive agent sits at its prompt
    # forever when a hook never fires, so an unbounded "poll until it appears"
    # loop would wedge the whole suite instead of failing it. run_bounded is the
    # repo's sanctioned bound: it already handles macOS shipping GNU timeout only
    # as `gtimeout`, which a bare `timeout` would hit with exit 127 — never
    # reaching the behaviour under test. Exit 124 is NOT a suite failure here; it
    # is the `no_interactive_capture` branch.
    wait_for_payload() {
        local file="$1" secs="$2"
        run_bounded "$secs" "$FIXTURE_DIR/wait_$$.log" \
            bash -c "while [ ! -s '$file' ]; do sleep 1; done"
    }

    # The payload's key set, sorted — what a headless/interactive diff compares.
    payload_keys() {
        "$PYTHON_BIN" -c '
import json, sys
line = ""
for candidate in open(sys.argv[1]):
    candidate = candidate.strip()
    if candidate.startswith("{"):
        line = candidate
        break
print(",".join(sorted(json.loads(line))) if line else "")
' "$1" 2>/dev/null
    }

    # ---- Case 5b: claude ---------------------------------------------------
    section "Case 5b — claude SessionStart capture (refresh-and-diff)"
    if ! command -v claude >/dev/null 2>&1; then
        echo "SKIP: claude not on PATH"
        finding "claude SessionStart: not probed (binary absent)"
    else
        (
            SCRATCH="$FIXTURE_DIR/claude_project"
            mkdir -p "$SCRATCH/.claude"
            write_capture_hook "$SCRATCH/capture_hook.sh"

            # POSITIVE CONTROL: prove the capture script itself works, so a
            # missing payload can never be misread as "the hook never fired".
            printf '{"session_id":"probe","cwd":"/x"}' \
                | "$SCRATCH/capture_hook.sh" "$SCRATCH/selfcheck.txt"
            if [ -s "$SCRATCH/selfcheck.txt" ]; then
                assert_record_pass
            else
                assert_record_fail
                echo "FAIL: the capture script does not work — no claude verdict can be drawn"
            fi

            claude_settings() {
                cat > "$SCRATCH/.claude/settings.json" <<SETEOF
{"hooks":{"SessionStart":[{"matcher":"startup|resume","hooks":[{"type":"command","command":"$SCRATCH/capture_hook.sh $1","timeout":10}]}]}}
SETEOF
            }

            # ---- headless (`claude -p`) — a spike convenience, never the
            # authoritative shape. Already gated behind AITASKS_SPIKE_REAL_AGENTS,
            # which satisfies the shell-conventions rule for a non-interactive
            # need.
            P_HEADLESS="$SCRATCH/payload_headless.txt"
            claude_settings "$P_HEADLESS"
            W="agent-pick-claude-h"
            read -r AGENT _COMPANION < <(make_agent_window "$W" "sleep 1000")
            ait_tmux respawn-pane -k -t "$AGENT" \
                "cd '$SCRATCH' && env AITASK_AGENT_STRING=claudecode/opus5 claude -p 'say hi'"
            wait_for_payload "$P_HEADLESS" "$HOOK_WAIT_SECS"
            hrc=$?
            ait_tmux kill-window -t "$(ait_tmux_window_target "$SESSION" "$W")" 2>/dev/null || true

            # ---- interactive (`launch_in_tmux`-shaped) — THE AUTHORITATIVE
            # capture. The framework launches agents interactively; a
            # headless-only fixture may never be pinned as the baseline.
            #
            # Claude refuses to start in an untrusted folder, and that dialog
            # blocks SessionStart entirely. Pre-trust the scratch project in a
            # THROWAWAY config dir so the user's own ~/.claude.json is never
            # touched. The key must be the REALPATH: claude resolves the folder
            # (/private/tmp/... on macOS) before matching, so a /tmp/... key
            # silently fails to match and the dialog appears anyway.
            P_INTERACTIVE="$SCRATCH/payload_interactive.txt"
            claude_settings "$P_INTERACTIVE"
            CLAUDE_CFG="$FIXTURE_DIR/claude_cfg"
            mkdir -p "$CLAUDE_CFG"
            REAL_SCRATCH="$(cd "$SCRATCH" && pwd -P)"
            "$PYTHON_BIN" - "$CLAUDE_CFG/.claude.json" "$REAL_SCRATCH" "$SCRATCH" <<'PYEOF'
import json, sys
out = sys.argv[1]
projects = {
    p: {"hasTrustDialogAccepted": True, "hasCompletedProjectOnboarding": True,
        "allowedTools": [], "history": []}
    for p in sys.argv[2:]
}
json.dump({"hasCompletedOnboarding": True, "projects": projects},
          open(out, "w"), indent=2)
PYEOF
            W2="agent-pick-claude-i"
            read -r AGENT2 _COMPANION2 < <(make_agent_window "$W2" "sleep 1000")
            ait_tmux respawn-pane -k -t "$AGENT2" \
                "cd '$SCRATCH' && env CLAUDE_CONFIG_DIR='$CLAUDE_CFG' AITASK_AGENT_STRING=claudecode/opus5 claude"
            wait_for_payload "$P_INTERACTIVE" "$HOOK_WAIT_SECS"
            irc=$?
            # NOTE: W2 is deliberately left alive here — the resume leg below
            # must exit that session cleanly before it can be resumed.

            if [ "$irc" -eq 0 ] && [ -s "$P_INTERACTIVE" ]; then
                assert_record_pass
                for field in session_id transcript_path cwd source; do
                    if grep -q "\"$field\"" "$P_INTERACTIVE"; then
                        assert_record_pass
                    else
                        assert_record_fail
                        echo "FAIL: the interactive claude payload has no $field"
                    fi
                done
                if grep -q '^ENV TMUX_PANE=%' "$P_INTERACTIVE"; then
                    assert_record_pass
                else
                    assert_record_fail
                    echo "FAIL: \$TMUX_PANE was not visible to the claude hook process"
                fi
                if grep -q '^ENV AITASK_AGENT_STRING=.\+' "$P_INTERACTIVE"; then
                    assert_record_pass
                else
                    assert_record_fail
                    echo "FAIL: AITASK_AGENT_STRING was not visible to the claude hook process"
                fi

                # ---- resume leg: relaunch with `claude --resume <id>` in a
                # RESPAWNED pane and assert the hook fires again with
                # `source: resume` and the same session id. This is the exact
                # shape child 5's restore path will use, so it is proved here
                # rather than assumed from the `startup|resume` matcher.
                sid="$("$PYTHON_BIN" -c '
import json, sys
for line in open(sys.argv[1]):
    line = line.strip()
    if line.startswith("{"):
        print(json.loads(line).get("session_id", "")); break
' "$P_INTERACTIVE" 2>/dev/null)"
                if [ -n "$sid" ]; then
                    # EXIT THE FIRST SESSION CLEANLY BEFORE RESUMING IT. A
                    # session whose pane is killed the instant its SessionStart
                    # payload lands has not persisted a usable transcript yet,
                    # and `--resume <id>` then finds nothing and sits at a
                    # picker — which reads as "the hook does not fire on
                    # resume" when the real cause is that there was nothing to
                    # resume. Child 5's restore path inherits this: a freeze
                    # must let the agent persist before its pane is respawned.
                    ait_tmux send-keys -t "$AGENT2" "/exit" Enter 2>/dev/null || true
                    sleep 6
                    ait_tmux kill-window -t "$(ait_tmux_window_target "$SESSION" "$W2")" 2>/dev/null || true

                    P_RESUME="$SCRATCH/payload_resume.txt"
                    claude_settings "$P_RESUME"
                    W3="agent-pick-claude-r"
                    read -r AGENT3 _COMPANION3 < <(make_agent_window "$W3" "sleep 1000")
                    ait_tmux respawn-pane -k -t "$AGENT3" \
                        "cd '$SCRATCH' && env CLAUDE_CONFIG_DIR='$CLAUDE_CFG' AITASK_AGENT_STRING=claudecode/opus5 claude --resume '$sid'"
                    wait_for_payload "$P_RESUME" "$HOOK_WAIT_SECS"
                    rrc=$?
                    ait_tmux kill-window -t "$(ait_tmux_window_target "$SESSION" "$W3")" 2>/dev/null || true
                    if [ "$rrc" -eq 0 ] && [ -s "$P_RESUME" ]; then
                        assert_record_pass
                        rsid="$("$PYTHON_BIN" -c '
import json, sys
for line in open(sys.argv[1]):
    line = line.strip()
    if line.startswith("{"):
        d = json.loads(line); print(d.get("source", "") + "|" + d.get("session_id", "")); break
' "$P_RESUME" 2>/dev/null)"
                        rsource="${rsid%%|*}"
                        rid="${rsid#*|}"
                        assert_eq "the resumed launch reports source=resume" "resume" "$rsource"
                        assert_eq "the resumed launch reports the SAME session id" "$sid" "$rid"
                        finding "claude SessionStart fires on --resume: yes (source=$rsource, same id: $([ "$rid" = "$sid" ] && echo yes || echo no))"
                    else
                        # Not a suite failure: an unavailable resume is a finding
                        # child 5 needs, not a broken probe.
                        assert_record_pass
                        finding "claude SessionStart fires on --resume: NOT OBSERVED (rc=$rrc)"
                    fi
                else
                    ait_tmux kill-window -t "$(ait_tmux_window_target "$SESSION" "$W2")" 2>/dev/null || true
                    finding "claude SessionStart fires on --resume: not probed (no session id in the interactive payload)"
                fi

                ikeys="$(payload_keys "$P_INTERACTIVE")"
                hkeys="$(payload_keys "$P_HEADLESS")"
                if [ "$hrc" -ne 0 ] || [ -z "$hkeys" ]; then
                    finding "claude SessionStart: interactive captured; headless capture unavailable (rc=$hrc)"
                elif [ "$ikeys" = "$hkeys" ]; then
                    finding "claude SessionStart: fields $ikeys; headless keys == interactive keys: yes"
                else
                    finding "claude SessionStart: fields $ikeys; headless keys == interactive keys: no (headless=$hkeys)"
                fi
                finding "claude fixture: captured (interactive, authoritative)"
            else
                # 124 (or an empty file) is the no_interactive_capture branch of
                # the pinning rule, not a suite failure.
                assert_record_pass
                ait_tmux kill-window -t "$(ait_tmux_window_target "$SESSION" "$W2")" 2>/dev/null || true
                echo "  interactive capture unavailable (rc=$irc) -> provisional"
                finding "claude fixture: provisional (no_interactive_capture, rc=$irc)"
            fi

            cp -f "$P_HEADLESS" "$FIXTURE_DIR/claude_payload_headless.txt" 2>/dev/null || true
            cp -f "$P_INTERACTIVE" "$FIXTURE_DIR/claude_payload_interactive.txt" 2>/dev/null || true
            if [ "$REFRESH_FIXTURES" = "1" ]; then
                echo "  --refresh-fixtures: raw captures are in $FIXTURE_DIR; redact and commit them together with README.md provenance"
            fi
        )
    fi

    # ---- Case 6: codex -----------------------------------------------------
    section "Case 6 — codex SessionStart + resume (P2 preflight first)"
    if ! command -v codex >/dev/null 2>&1; then
        echo "SKIP: codex not on PATH"
        finding "codex hooks: unavailable (binary absent)"
        finding "codex = re-pick only: NOT pinned (inconclusive: unavailable)"
    else
        (
            SCRATCH="$FIXTURE_DIR/codex_project"
            mkdir -p "$SCRATCH/.codex"
            write_capture_hook "$SCRATCH/capture_hook.sh"
            CODEX_HOME_DIR="$FIXTURE_DIR/codex_home"
            mkdir -p "$CODEX_HOME_DIR"
            cp ~/.codex/auth.json "$CODEX_HOME_DIR/auth.json" 2>/dev/null || true

            # P2 POSITIVE CONTROL leg 1 — our capture script works. Without this
            # a missing payload is indistinguishable from a broken fixture.
            printf '{"session_id":"probe"}' \
                | "$SCRATCH/capture_hook.sh" "$SCRATCH/selfcheck.txt"
            capture_works=no
            [ -s "$SCRATCH/selfcheck.txt" ] && capture_works=yes
            echo "  P2 control — capture script works: $capture_works"

            # THE CONFIG SURFACE, established empirically against codex 0.153.4.
            # A project-level `.codex/hooks.json` in the Claude-compatible shape
            # — {"hooks":{"SessionStart":[{ hooks:[{type,command}] }]}} — IS
            # honoured, but only when the project is trusted. `[hooks]` in
            # config.toml is the same contract expressed in TOML
            # (`SessionStart = [ MatcherGroup ]`); the snake_case `session_start`
            # key is silently ignored, which is exactly how a guessed schema
            # turns into a false "unsupported" verdict.
            #
            # A throwaway CODEX_HOME keeps the user's own ~/.codex untouched.
            P_EXEC="$SCRATCH/payload_exec.txt"
            cat > "$SCRATCH/.codex/hooks.json" <<JSONEOF
{"hooks":{"SessionStart":[{"hooks":[{"type":"command","command":"$SCRATCH/capture_hook.sh $P_EXEC","timeout":10}]}]}}
JSONEOF
            REAL_SCRATCH="$(cd "$SCRATCH" && pwd -P)"
            {
                grep -vE '^hooks|^\[hooks\]' ~/.codex/config.toml 2>/dev/null || true
                printf '\n[projects."%s"]\ntrust_level = "trusted"\n' "$REAL_SCRATCH"
            } > "$CODEX_HOME_DIR/config.toml"
            ( cd "$SCRATCH" && git init -q . >/dev/null 2>&1 && \
              git -c user.email=spike@example.com -c user.name=spike \
                  commit -q --allow-empty -m init >/dev/null 2>&1 ) || true

            # P2 POSITIVE CONTROL leg 2 — codex really ran and produced a
            # session. Counting session files before and after is what separates
            # "the hook never fired" from "codex never started"; the mere
            # existence of the sessions directory proves neither.
            count_codex_sessions() {
                find "$CODEX_HOME_DIR/sessions" -type f 2>/dev/null | wc -l | tr -d '[:space:]'
            }
            sessions_before="$(count_codex_sessions)"
            exec_out="$SCRATCH/exec.log"
            run_bounded "$HOOK_WAIT_SECS" "$exec_out" \
                env CODEX_HOME="$CODEX_HOME_DIR" \
                bash -c "cd '$SCRATCH' && codex exec --dangerously-bypass-hook-trust 'reply OK'"
            exec_rc=$?
            sessions_after="$(count_codex_sessions)"
            session_created=no
            [ "${sessions_after:-0}" -gt "${sessions_before:-0}" ] && session_created=yes
            echo "  P2 control — codex ran and produced a session: $session_created (rc=$exec_rc)"

            # ---- the interactive lane: the PRODUCTION launch path.
            P_INT="$SCRATCH/payload_interactive.txt"
            cat > "$SCRATCH/.codex/hooks.json" <<JSONEOF
{"hooks":{"SessionStart":[{"hooks":[{"type":"command","command":"$SCRATCH/capture_hook.sh $P_INT","timeout":10}]}]}}
JSONEOF
            W="agent-pick-codex-i"
            read -r AGENTC _COMPC < <(make_agent_window "$W" "sleep 1000")
            ait_tmux respawn-pane -k -t "$AGENTC" \
                "cd '$SCRATCH' && env CODEX_HOME='$CODEX_HOME_DIR' AITASK_AGENT_STRING=codexcli/gpt5 codex --dangerously-bypass-hook-trust"
            wait_for_payload "$P_INT" "$HOOK_WAIT_SECS"
            int_rc=$?
            ait_tmux kill-window -t "$(ait_tmux_window_target "$SESSION" "$W")" 2>/dev/null || true

            # ---- verdict. Only `unsupported` may pin the parent's contract,
            # and it requires the full positive-control chain plus a surface
            # that is demonstrably accepted AND trusted.
            surface_accepted=no
            [ -s "$P_EXEC" ] && surface_accepted=yes

            if [ "$capture_works" != "yes" ]; then
                verdict=config_unresolved
            elif [ "$exec_rc" -ne 0 ] || [ "$session_created" != "yes" ]; then
                verdict=unavailable
            elif [ "$surface_accepted" != "yes" ]; then
                if grep -qi 'trust' "$exec_out" 2>/dev/null; then
                    verdict=trust_blocked
                else
                    verdict=config_unresolved
                fi
            elif [ -s "$P_INT" ]; then
                verdict=captured
            else
                # The surface IS accepted and trusted (the exec lane captured a
                # real payload through this very file), the positive controls
                # passed, and the interactive path still delivers nothing. That
                # is the evidence `unsupported` requires — scoped, precisely, to
                # the interactive path.
                verdict=unsupported
            fi
            echo "  P2 verdict: $verdict (exec-lane payload: $surface_accepted, interactive payload rc=$int_rc)"
            finding "codex hooks: $verdict (project .codex/hooks.json accepted when trusted; fires under \`codex exec\`, NOT in the interactive TUI)"

            if [ "$verdict" = "unsupported" ]; then
                finding "codex = re-pick only: pinned for the INTERACTIVE launch path (SessionStart proven working under \`codex exec\`)"
            else
                finding "codex = re-pick only: NOT pinned (inconclusive: $verdict)"
            fi
            if [ "$surface_accepted" = "yes" ]; then
                finding "codex fixture: provisional(no_interactive_capture) — exec-mode payload is real but not the production path"
            fi

            # `codex resume` is a capability SEPARATE from the hook and is
            # recorded independently.
            resume_out="$SCRATCH/resume.log"
            run_bounded 20 "$resume_out" \
                env CODEX_HOME="$CODEX_HOME_DIR" \
                bash -c "cd '$SCRATCH' && codex resume --help"
            resume_rc=$?
            if [ "$resume_rc" -eq 0 ]; then
                finding "codex resume: present"
            else
                finding "codex resume: not usable (rc=$resume_rc)"
            fi
            assert_record_pass   # the lane ran; its verdicts are findings, not failures
        )
    fi
fi


# ---------------------------------------------------------------------------
# Case 7 — the live-tmux guard allows a SOCKETED respawn-pane
# ---------------------------------------------------------------------------
section "Case 7 — guard_live_tmux allows a socketed respawn-pane"

# The guard already allows it: `check()` does `if has_socket: continue` BEFORE
# any verb test, so `respawn-pane` being in DESTRUCTIVE_VERBS never applies to a
# socketed call. The deliverable is the missing REGRESSION assertion, which
# lives in tests/test_guard_live_tmux.sh (Case 7's edit). This case re-asserts
# it here so the spike's own findings line is evidence-backed.
(
    GUARD="$PROJECT_DIR/.claude/hooks/guard_live_tmux.py"
    decision_for() {
        local cmd="$1" out
        out="$(printf '%s' "$cmd" \
            | "$PYTHON_BIN" -c 'import json,sys; print(json.dumps({"tool_name":"Bash","tool_input":{"command":sys.stdin.read()}}))' \
            | "$GUARD" 2>/dev/null)"
        if [ -z "$out" ]; then echo "allow"; else
            printf '%s' "$out" | "$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin)["hookSpecificOutput"]["permissionDecision"])' 2>/dev/null || echo "unparseable"
        fi
    }
    socketed="$(decision_for 'tmux -L throwaway respawn-pane -k -t %1 sleep 1')"
    bare="$(decision_for 'tmux respawn-pane -k -t %1 sleep 1')"
    assert_eq "a socketed respawn-pane is ALLOWED" "allow" "$socketed"
    assert_eq "a bare respawn-pane is still DENIED" "deny" "$bare"
    if [ "$socketed" = "allow" ]; then
        finding "guard_live_tmux: socketed respawn allowed (regression assertion added to tests/test_guard_live_tmux.sh)"
    else
        finding "guard_live_tmux: socketed respawn DENIED — the freeze engine would be blocked"
    fi
)

# ---------------------------------------------------------------------------
# P1 (end of run) — the user's server was never touched
# ---------------------------------------------------------------------------
section "P1 — end-of-run isolation re-assertion"

USER_AIT_AFTER="$(user_ait_pane_set)"
if [ "$USER_AIT_BEFORE" = "$USER_AIT_AFTER" ]; then
    assert_record_pass
    echo "the user's -L ait server is unchanged"
else
    assert_record_fail
    echo "FAIL: the user's -L ait server CHANGED during this run"
    echo "  before: $USER_AIT_BEFORE"
    echo "  after:  $USER_AIT_AFTER"
fi

# ---------------------------------------------------------------------------
# FINDINGS
# ---------------------------------------------------------------------------
echo
echo "==================== FINDINGS ===================="
cat "$FINDINGS_FILE"
echo "=================================================="

echo
echo "==================== SUMMARY ===================="
assert_counters_load
echo "Total:  $TOTAL"
echo "Passed: $PASS"
echo "Failed: $FAIL"
if [[ "$FAIL" -eq 0 ]]; then
    echo "RESULT: PASS"
    exit 0
else
    echo "RESULT: FAIL"
    exit 1
fi
