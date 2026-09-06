#!/usr/bin/env bash
# tests/lib/fake_agent.sh — a long-running stand-in for a code-agent CLI.
#
# Live tmux fixtures need a process that behaves like `claude` / `codex` in the
# two ways the freeze/restore work actually depends on:
#
#   1. it stays in the foreground of its pane until killed, so `#{pane_pid}`
#      keeps naming it and `remain-on-exit` / `pane-died` behave as they do for
#      a real agent;
#   2. it accepts a resume argument in BOTH shapes the two supported agents use
#      — claude's `--resume <id>` and codex's bare `resume <id>` — and reports
#      the id it was asked to resume.
#
# It deliberately does NOT wrap anything. `launch_in_tmux` hands tmux the bare
# command line so the pane's pid IS the agent process (the task-lock anchor,
# t1465); a fixture agent that forked a child would break every `#{pane_pid}`
# assertion built on it. Every mode below ends in a foreground `sleep`.
#
# Usage:
#   fake_agent.sh                            # just run
#   fake_agent.sh --resume <id>              # claude-shaped resume
#   fake_agent.sh resume <id>                # codex-shaped resume
#   fake_agent.sh --report-env <file>        # self-report pid + env, then run
#   FAKE_AGENT_EXIT=1 fake_agent.sh          # exit 1 immediately (death fixture)
#
# --report-env exists because there is no portable way to read a FOREIGN
# process's environment: macOS has no /proc, and `ps eww` / `ps -E` return
# nothing under SIP. The process must self-report, and it writes to a path only
# the calling run knows, so the reader can never be inspecting a different
# process by accident (a `pgrep -f 'sleep 1000'` can).
set -uo pipefail

FAKE_AGENT_SLEEP="${FAKE_AGENT_SLEEP:-1000}"

# A death fixture: used to make a pane die on demand so `pane-died` fires.
if [ "${FAKE_AGENT_EXIT:-0}" = "1" ]; then
    echo "fake_agent: exiting on FAKE_AGENT_EXIT"
    exit 1
fi

resume_id=""
report_env=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        --resume)
            resume_id="${2:-}"
            shift 2 || shift
            ;;
        --resume=*)
            resume_id="${1#--resume=}"
            shift
            ;;
        resume)
            # codex shape: `codex resume [SESSION_ID] [PROMPT]`
            resume_id="${2:-}"
            shift 2 || shift
            ;;
        --report-env)
            report_env="${2:-}"
            shift 2 || shift
            ;;
        *)
            shift
            ;;
    esac
done

if [ -n "$resume_id" ]; then
    echo "fake_agent: resuming session $resume_id"
fi

if [ -n "$report_env" ]; then
    # One self-report, written before the sleep so a reader that sees the file
    # knows the process reached its steady state. `$$` is this script's own pid,
    # which is the pane's pid precisely because nothing wrapped us.
    {
        printf 'pid=%s\n' "$$"
        printf 'AITASK_RESTORE_RECORD=%s\n' "${AITASK_RESTORE_RECORD:-}"
        printf 'AITASK_AGENT_STRING=%s\n' "${AITASK_AGENT_STRING:-}"
        printf 'TMUX_PANE=%s\n' "${TMUX_PANE:-}"
        printf 'resume_id=%s\n' "$resume_id"
    } > "$report_env"
fi

exec sleep "$FAKE_AGENT_SLEEP"
