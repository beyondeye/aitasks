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

    # run_bounded <secs> <outfile> <cmd...>  -> the command's status, or 124 if
    # it had to be killed. Use it for ANY test whose command could hang: an
    # un-bounded assertion on a hang wedges the whole suite instead of failing
    # it, so the timeout is what converts "infinite loop" into a named FAIL.
    #
    # `timeout` is GNU coreutils. macOS is a supported platform and ships it
    # only as `gtimeout` via Homebrew coreutils, so a bare `timeout` exits 127
    # there and the test never reaches the behaviour it meant to check. The
    # third rung covers a macOS box with no Homebrew coreutils at all.
    #
    # Same guard the framework itself uses at aitask_sync.sh:97 and
    # aitask_remote_drift_check.sh:152. Lifted here verbatim from
    # tests/test_setup_help_flag.sh (its first home) when a second suite needed
    # it -- it lives here now so the two cannot drift.
    run_bounded() {
        local secs="$1" out="$2"; shift 2
        local runner=""
        command -v timeout >/dev/null 2>&1 && runner=timeout
        [ -z "$runner" ] && command -v gtimeout >/dev/null 2>&1 && runner=gtimeout
        if [ -n "$runner" ]; then
            "$runner" "$secs" "$@" >"$out" 2>&1 </dev/null
            return $?
        fi
        # macOS fallback. `set -m` puts the child in its own process group so
        # the watchdog can kill the whole tree -- a regression here spawns
        # children that a bare `kill $pid` would orphan.
        set -m
        "$@" >"$out" 2>&1 </dev/null &
        local pid=$!
        set +m
        local i=0
        while kill -0 "$pid" 2>/dev/null && [ "$i" -lt "$secs" ]; do
            sleep 1
            i=$((i + 1))
        done
        if kill -0 "$pid" 2>/dev/null; then
            kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
            return 124
        fi
        wait "$pid"
        return $?
    }

    # liveness_token_class <pid> -- classify the identity token this host
    # records for a LIVE <pid>, so a test can expect the verdict the product
    # actually reaches instead of hard-coding the Linux one. stdout + status:
    #   strong (0)  kind `proc`: lock_holder_liveness can answer `alive`
    #   weak   (0)  kind `ps` with a real, re-derivable ps token -- the supported
    #               no-/proc limitation (macOS/BSD); liveness reads `unknown`
    #               BY DESIGN (see lock_holder_liveness in pid_anchor.sh)
    #   nothing, 2  pid_anchor.sh is not sourced (fixture setup error)
    #   nothing, 3  no usable token, kind none/unrecognised, or a `ps` kind whose
    #               token does not re-derive from ps: identity is BROKEN
    #
    # FAIL CLOSED. Status 2/3 must fail the test, never select the weak branch:
    # a broken recorder (token `-`, kind `none`) also makes the product answer
    # `unknown`, so collapsing it into `weak` would let the platform-correct
    # assertion agree with the bug. Branch on the token, never on `uname`.
    liveness_token_class() {
        local pid="${1:-}" kind tok
        if ! declare -F get_pid_starttime_kind >/dev/null \
            || ! declare -F get_pid_starttime >/dev/null; then
            echo "proc_fixtures: source .aitask-scripts/lib/pid_anchor.sh before liveness_token_class" >&2
            return 2
        fi
        kind="$(get_pid_starttime_kind "$pid")"
        tok="$(get_pid_starttime "$pid")"
        if [[ -z "$tok" || "$tok" == "-" ]]; then
            echo "proc_fixtures: pid '$pid' has no usable identity token (kind=$kind)" >&2
            return 3
        fi
        case "$kind" in
            proc) echo strong ;;
            ps)
                if [[ "$(_pid_starttime_ps "$pid" 2>/dev/null)" != "$tok" ]]; then
                    echo "proc_fixtures: pid '$pid' has kind=ps but its token does not re-derive from ps" >&2
                    return 3
                fi
                echo weak ;;
            *)
                echo "proc_fixtures: pid '$pid' has unrecognised token kind '$kind'" >&2
                return 3 ;;
        esac
    }

    # expected_live_verdict <pid> -- the verdict a LIVE <pid> reads back as on
    # this host: `alive` (strong) or `unknown` (weak). On a class failure it
    # prints NOTHING and returns that status, so an assert_eq against it fails
    # loudly instead of agreeing with the product on `unknown`.
    expected_live_verdict() {
        local cls rc=0
        cls="$(liveness_token_class "${1:-}")" || rc=$?
        (( rc == 0 )) || return "$rc"
        case "$cls" in
            strong) echo alive ;;
            weak)   echo unknown ;;
        esac
    }

    # skip_weak_token <what> -- announce a case that needs a provably-alive
    # holder and cannot have one on this host. Same "— not counted" shape as
    # the suite's other conditional skips.
    skip_weak_token() {
        echo "SKIP: $1 (weak ps identity token, no /proc; liveness reads unknown by design) — not counted" >&2
    }
fi
