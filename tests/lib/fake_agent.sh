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
# Restore-fixture knobs (t1705_5), all documented at their use site below:
#   FAKE_AGENT_SESSION=<id>   report THIS session id to the hook (mismatch case)
#   FAKE_AGENT_NO_HOOK=1      never invoke the hook (liveness-fallback case)
#   FAKE_AGENT_HOOK_DELAY=<s> sleep before the hook (V12 race ordering)
#   AITASKS_FAKE_AGENT_HOOK   override the hook path (defaults to the shipped one)
#   FAKE_AGENT_HOOK_LOG       append the hook's stderr here for diagnosis
#
# --report-env reports all four AITASK_RESTORE_* names, because the restore
# coordinator delivers them as four separate `respawn-pane -e` flags and the
# spike must be able to prove that every one of them arrives (Case 3c).
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
    # All four AITASK_RESTORE_* names are reported, not just RECORD: the restore
    # coordinator passes four separate `respawn-pane -e` flags, and tmux
    # documents `-e` as repeatable but the spike had only ever measured ONE. A
    # build that honoured just the last `-e` would drop AITASK_RESTORE_NONCE,
    # which demotes every hook ack to a NONCE_MISMATCH and routes every restore
    # down the liveness fallback — a silent degradation that still looks like
    # success. Spike Case 3c is what turns that into a measured fact.
    {
        printf 'pid=%s\n' "$$"
        printf 'AITASK_RESTORE_RECORD=%s\n' "${AITASK_RESTORE_RECORD:-}"
        printf 'AITASK_RESTORE_NONCE=%s\n' "${AITASK_RESTORE_NONCE:-}"
        printf 'AITASK_RESTORE_MODE=%s\n' "${AITASK_RESTORE_MODE:-}"
        printf 'AITASK_RESTORE_EXPECT_SESSION=%s\n' "${AITASK_RESTORE_EXPECT_SESSION:-}"
        printf 'AITASK_AGENT_STRING=%s\n' "${AITASK_AGENT_STRING:-}"
        printf 'TMUX_PANE=%s\n' "${TMUX_PANE:-}"
        printf 'resume_id=%s\n' "$resume_id"
    } > "$report_env"
fi

# --- SessionStart hook (t1705_5) -------------------------------------------
# The restore acknowledgement path is the whole point of the restore protocol,
# so the fixture drives the REAL, SHIPPED hook rather than simulating it: this
# process invokes `aitask_session_hook.sh` with a synthetic payload and the
# environment it inherited, and the hook does its own tmux round trip and its
# own `upsert --restore-of --nonce` against the real store. What the live tests
# then assert is the genuine hook -> wrapper -> store path, not a stand-in for it.
#
# Which session id is reported:
#   FAKE_AGENT_SESSION   -> report THAT (the session-mismatch fixture: the store
#                           must persist "<nonce>:session_mismatch" and the
#                           coordinator must abort WITHOUT waiting out the grace)
#   else $resume_id      -> report the id we were asked to resume (happy resume)
#   else a fresh id      -> a brand-new session (happy re-pick, where the store
#                           adopts whatever session id comes back)
#
# FAKE_AGENT_NO_HOOK=1   -> never call the hook at all, which is how the liveness
#                           fallback is exercised: nothing ever acknowledges, so
#                           the coordinator must wait out the grace and confirm
#                           on `launch_pid` alone, KEEPING the captures.
# FAKE_AGENT_HOOK_DELAY  -> seconds to sleep BEFORE calling the hook. `0` (the
#                           default) makes the hook ack as early as possible,
#                           which is what forces the V12 race: the hook wins, the
#                           record is already `live`, and the coordinator's
#                           `restore-launched` is refused. Forcing the ordering
#                           beats hoping for it.
if [ "${FAKE_AGENT_NO_HOOK:-0}" != "1" ]; then
    _hook="${AITASKS_FAKE_AGENT_HOOK:-}"
    if [ -z "$_hook" ]; then
        # RESOLVE SYMLINKS FIRST. Live fixtures put this script on PATH under
        # the agent's real name (a `claude` symlink in a temp bin dir), so
        # BASH_SOURCE is that symlink and `../..` from it lands in the temp dir
        # instead of the repo. The failure is silent in the worst way: no hook
        # runs, nothing acknowledges, and every restore quietly degrades to the
        # liveness fallback — which still reports success.
        # bash 3.2 (macOS) has no `readlink -f`, so walk the chain by hand.
        _src="${BASH_SOURCE[0]}"
        while [ -L "$_src" ]; do
            _dir="$(cd -P "$(dirname "$_src")" && pwd)"
            _src="$(readlink "$_src")"
            case "$_src" in
                /*) ;;
                *) _src="$_dir/$_src" ;;
            esac
        done
        _self_dir="$(cd -P "$(dirname "$_src")" && pwd)"
        _hook="$_self_dir/../../.aitask-scripts/aitask_session_hook.sh"
    fi

    if [ -x "$_hook" ]; then
        _session_id="${FAKE_AGENT_SESSION:-}"
        [ -n "$_session_id" ] || _session_id="$resume_id"
        [ -n "$_session_id" ] || _session_id="fakesess-$$"

        _delay="${FAKE_AGENT_HOOK_DELAY:-0}"
        [ "$_delay" = "0" ] || sleep "$_delay"

        # The hook parses this with python3's json module, so the payload must be
        # real JSON. Only the four keys it reads are emitted.
        _payload="$(FAKE_SID="$_session_id" FAKE_CWD="$PWD" python3 -c '
import json, os
print(json.dumps({
    "session_id": os.environ["FAKE_SID"],
    "transcript_path": "",
    "cwd": os.environ["FAKE_CWD"],
    "source": "startup",
}))')"

        # Contract 1 of the hook: it ALWAYS exits 0 and never writes stdout, so
        # a failure here must not take the fixture agent down with it.
        printf '%s' "$_payload" | "$_hook" >/dev/null 2>>"${FAKE_AGENT_HOOK_LOG:-/dev/null}" || true
        echo "fake_agent: session hook invoked for $_session_id"
    else
        echo "fake_agent: no session hook at $_hook" >&2
    fi
fi

exec sleep "$FAKE_AGENT_SLEEP"
