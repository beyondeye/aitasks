#!/usr/bin/env bash
# tests/lib/proc_fixtures.sh — process fixtures for the shell test suite.
#
# Source via the absolute $PROJECT_DIR path, alongside tests/lib/asserts.sh:
#     . "$PROJECT_DIR/tests/lib/asserts.sh"
#     . "$PROJECT_DIR/tests/lib/proc_fixtures.sh"

if [[ -z "${_AIT_PROC_FIXTURES_LOADED:-}" ]]; then
    _AIT_PROC_FIXTURES_LOADED=1

    # A PID that has already exited AND been reaped. Command substitution waits
    # for the child, so there is no zombie — `kill -0` succeeds on a zombie, so
    # only a reaped PID answers it with failure — and there is no signal to lose.
    #
    # Do NOT write this as `sleep 60 & dead_pid=$!; kill "$dead_pid"; wait
    # "$dead_pid"`. That `kill` fires microseconds after `&`, inside bash's
    # fork->exec window, where the signal can be dropped; the `wait` — which is
    # load-bearing, since only reaping makes the PID answer `kill -0` with
    # failure — then blocks for the child's full 60s. Observed live in t1507
    # (2m04s wall against 0.2s of CPU) and again in t1512 (62s against a
    # documented ~10s). Such a construction passes only by scheduling luck.
    #
    # This is specifically for fixtures that need a *dead* PID. A live-holder
    # fixture (`sleep 120 &` kept alive across an assertion, killed afterwards)
    # is a different, sound shape: its kill runs long after the fork->exec
    # window and is not affected by any of the above.
    dead_pid_fixture() { bash -c 'echo $$'; }
fi
