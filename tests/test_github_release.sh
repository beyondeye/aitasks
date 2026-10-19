#!/usr/bin/env bash
# test_github_release.sh - Tests for the shared GitHub-release resolver
# (.aitask-scripts/lib/github_release.sh): API error classification, the
# git-tag fallback, and the combined resolver.
# Run: bash tests/test_github_release.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# Shared assertion helpers (see tests/lib/asserts.sh)
. "$PROJECT_DIR/tests/lib/asserts.sh"

# Unit under test
. "$PROJECT_DIR/.aitask-scripts/lib/github_release.sh"
set +euo pipefail

# --- Test doubles -----------------------------------------------------------
# `curl` stub: emits a body + a trailing "\n<http_code>" line, exactly like the
# real `curl -w '\n%{http_code}'` the helper uses. Behavior is driven by the
# MOCK_CURL_MODE global so each test can pick a response shape.
MOCK_CURL_MODE="ok"
curl() {
    case "$MOCK_CURL_MODE" in
        ok)        printf '%s\n%s' '{"tag_name": "v1.2.3", "name": "Release"}' '200' ;;
        ratelimit) printf '%s\n%s' '{"message":"API rate limit exceeded for 1.2.3.4"}' '403' ;;
        notfound)  printf '%s\n%s' '{"message":"Not Found"}' '404' ;;
        network)   printf '\n%s' '000' ;;   # connection failure: empty body, 000 status
        empty)     printf '' ;;             # curl produced no output at all
    esac
}

# `git` stub: only intercepts `ls-remote`; everything else passes through.
git() {
    if [[ "$1" == "ls-remote" ]]; then
        # Deliberately list 0.9.0 before 0.10.0 to catch lexical-sort regressions.
        printf '%s\t%s\n' \
            'abc123' 'refs/tags/v0.9.0' \
            'def456' 'refs/tags/v0.10.0' \
            'ghi789' 'refs/tags/v0.2.1'
        return 0
    fi
    command git "$@"
}

echo "=== GitHub Release Resolver Tests ==="
echo ""

# --- Test 1: valid release JSON → parsed version, exit 0 ---
echo "--- Test 1: valid release body ---"
MOCK_CURL_MODE="ok"
out="$(github_latest_release_version beyondeye/aitasks 2>/dev/null)"; rc=$?
assert_eq "returns parsed version without leading v" "1.2.3" "$out"
assert_eq "exit 0 on success" "0" "$rc"

# --- Test 2: rate-limited 403 → RATELIMIT / exit 2 ---
echo "--- Test 2: rate-limited response ---"
MOCK_CURL_MODE="ratelimit"
err="$(github_latest_release_version beyondeye/aitasks 2>&1 >/dev/null)"; rc=$?
assert_eq "exit 2 on rate limit" "2" "$rc"
assert_contains "classifies as RATELIMIT" "RATELIMIT" "$err"

# --- Test 3: 404 → NOTFOUND / exit 3 ---
echo "--- Test 3: not-found response ---"
MOCK_CURL_MODE="notfound"
err="$(github_latest_release_version beyondeye/aitasks 2>&1 >/dev/null)"; rc=$?
assert_eq "exit 3 on 404" "3" "$rc"
assert_contains "classifies as NOTFOUND" "NOTFOUND" "$err"

# --- Test 4: empty/unreachable → NETWORK / exit 4 ---
echo "--- Test 4: network failure (empty body, 000 status) ---"
MOCK_CURL_MODE="network"
err="$(github_latest_release_version beyondeye/aitasks 2>&1 >/dev/null)"; rc=$?
assert_eq "exit 4 on 000 status" "4" "$rc"
assert_contains "classifies as NETWORK" "NETWORK" "$err"

echo "--- Test 4b: curl produced no output at all ---"
MOCK_CURL_MODE="empty"
github_latest_release_version beyondeye/aitasks >/dev/null 2>&1; rc=$?
assert_eq "exit 4 on empty output" "4" "$rc"

# --- Test 5: git-tag fallback picks highest version by numeric sort ---
echo "--- Test 5: github_latest_tag_version numeric sort ---"
out="$(github_latest_tag_version beyondeye/aitasks)"
assert_eq "0.10.0 sorts above 0.9.0 (numeric, not lexical)" "0.10.0" "$out"

# --- Test 6: combined resolver falls back to tags when API is rate-limited ---
echo "--- Test 6: github_resolve_latest_version fallback on rate limit ---"
MOCK_CURL_MODE="ratelimit"
out="$(github_resolve_latest_version beyondeye/aitasks 2>/dev/null)"; rc=$?
assert_eq "resolves via git-tag fallback" "0.10.0" "$out"
assert_eq "exit 0 once fallback succeeds" "0" "$rc"

# --- Test 7: combined resolver returns API version on the happy path ---
echo "--- Test 7: github_resolve_latest_version happy path ---"
MOCK_CURL_MODE="ok"
out="$(github_resolve_latest_version beyondeye/aitasks 2>/dev/null)"; rc=$?
assert_eq "returns API version directly" "1.2.3" "$out"
assert_eq "exit 0" "0" "$rc"

# --- Test 8-11: the bounded `git ls-remote` fallback (t1244) ---------------
# The defect these cover is a fallback with no time bound: on a wedged network
# (a connection that blackholes instead of refusing) it hangs forever, freezing
# `ait upgrade` / `ait setup`. Both curl paths above already carry --max-time.

STUB_PIDS="$(mktemp "${TMPDIR:-/tmp}/ait_stub_pids.XXXXXX")"
export STUB_PIDS
trap 'rm -f "$STUB_PIDS"' EXIT

# Hanging `git` stub. It must reproduce the real PROCESS SHAPE, not just the
# hang: the failure being fixed is a surviving *descendant* (git runs the
# transfer in a `git-remote-https` grandchild), so a stub that sleeps inline
# would only prove the direct child was killed. `bash -c 'sleep 30'` is not
# usable either — bash exec-optimizes a sole simple command and the process
# *becomes* `sleep`, leaving no grandchild.
#
# The NESTED shell records its own pid (`$$`) and its child's (`$!`) itself, the
# moment both exist. An earlier version had the parent poll `pgrep -P` for the
# grandchild instead, which made the fixture a race it had to win against the
# watchdog — observed failing as "fixture actually produced a grandchild = no".
# Nothing here polls or searches: the write is a single printf microseconds
# after the fork, against a multi-second watchdog.
git() {
    if [[ "${1:-}" == "ls-remote" ]]; then
        bash -c 'sleep 30 & printf "%s\n%s\n" "$$" "$!" > "$STUB_PIDS"; wait' &
        wait
        return 0
    fi
    command git "$@"
}

echo "--- Test 8: a hanging ls-remote is bounded, empty and non-fatal ---"
# 3s rather than 1s: the assertion below only needs to separate "bounded" from a
# 30s hang, and the headroom keeps the fixture's record comfortably ahead of the
# watchdog on a loaded machine.
start=$SECONDS
out="$(AIT_GIT_LSREMOTE_TIMEOUT=3 github_latest_tag_version beyondeye/aitasks)"; rc=$?
elapsed=$(( SECONDS - start ))
assert_eq "hanging ls-remote yields no version" "" "$out"
assert_eq "hanging ls-remote still exits 0" "0" "$rc"
assert_eq "bounded well inside the 30s stub hang" "yes" \
    "$( [[ $elapsed -le 8 ]] && echo yes || echo no )"

echo "--- Test 9: the watchdog kills the whole descendant tree ---"
nested_pid="$(sed -n 1p "$STUB_PIDS")"
grandchild_pid="$(sed -n 2p "$STUB_PIDS")"
# Guard the fixture itself: an empty grandchild means the nested shape stopped
# being produced and the cleanup assertion below would be vacuously true.
assert_eq "fixture actually produced a grandchild" "yes" \
    "$( [[ -n "$grandchild_pid" ]] && echo yes || echo no )"
sleep 0.5   # let the signals land and the orphans get reaped
assert_eq "nested shell was killed" "gone" \
    "$( kill -0 "$nested_pid" 2>/dev/null && echo alive || echo gone )"
assert_eq "its grandchild was killed too" "gone" \
    "$( [[ -n "$grandchild_pid" ]] && kill -0 "$grandchild_pid" 2>/dev/null \
        && echo alive || echo gone )"

echo "--- Test 9b: descendants die even when pgrep is unavailable ---"
# THE REGRESSION THIS PINS: a tree-walk built on `pgrep -P` alone silently
# degrades to a depth-1 kill on any system without procps (minimal containers
# ship none), leaving every descendant running — the exact leak the helper
# exists to prevent, measured as "nested ALIVE / grandchild ALIVE". Shadowing
# `pgrep` here proves the process GROUP kill, not the walk, is what does the
# work. A shell function shadows the unqualified `pgrep` the helper calls, and
# subshells inherit it, so no PATH surgery is needed.
pgrep() { return 1; }
: > "$STUB_PIDS"
out="$(AIT_GIT_LSREMOTE_TIMEOUT=3 github_latest_tag_version beyondeye/aitasks)"
nested_pid="$(sed -n 1p "$STUB_PIDS")"
grandchild_pid="$(sed -n 2p "$STUB_PIDS")"
assert_eq "fixture produced a grandchild (no-pgrep case)" "yes" \
    "$( [[ -n "$grandchild_pid" ]] && echo yes || echo no )"
sleep 0.5
assert_eq "nested shell killed without pgrep" "gone" \
    "$( kill -0 "$nested_pid" 2>/dev/null && echo alive || echo gone )"
assert_eq "its grandchild killed without pgrep" "gone" \
    "$( [[ -n "$grandchild_pid" ]] && kill -0 "$grandchild_pid" 2>/dev/null \
        && echo alive || echo gone )"
unset -f pgrep

# Back to the instant stub for the remaining tests.
git() {
    if [[ "$1" == "ls-remote" ]]; then
        printf '%s\t%s\n' \
            'abc123' 'refs/tags/v0.9.0' \
            'def456' 'refs/tags/v0.10.0' \
            'ghi789' 'refs/tags/v0.2.1'
        return 0
    fi
    command git "$@"
}

echo "--- Test 10: a malformed AIT_GIT_LSREMOTE_TIMEOUT falls back to the default ---"
# Unnormalized, "abc" aborts the helper under `set -u` ("abc: unbound variable")
# and takes the caller's command substitution with it; "" and 0 make the
# deadline expire instantly, silently disabling the fallback for good.
#
# Run under the CALLER's shell settings, not this file's. Tests run with
# `set +euo pipefail`, which suppresses exactly the `set -u` abort this guards
# against — the real callers (aitask_upgrade.sh, aitask_setup.sh) all run
# `set -euo pipefail`. `rc` is the subshell's status, so a strict-mode death
# shows up as a non-zero here instead of being silently absorbed.
for bad in abc "" 0 -5; do
    out="$(
        set -euo pipefail
        AIT_GIT_LSREMOTE_TIMEOUT="$bad" github_latest_tag_version beyondeye/aitasks 2>/dev/null
    )"; rc=$?
    assert_eq "timeout='$bad' still resolves the version" "0.10.0" "$out"
    assert_eq "timeout='$bad' survives set -euo pipefail" "0" "$rc"
done

echo "--- Test 11: no matching tag is an empty string with exit 0, not a failure ---"
# Under `pipefail` a grep that matches nothing makes the pipeline exit 1, and
# aitask_upgrade.sh:67 / github_resolve_latest_version capture this in an
# unguarded $( ) under `set -e` — the script would die with no message instead
# of reaching its own error handling.
#
# THIS ASSERTION IS ONLY MEANINGFUL WITH `pipefail` ON. This file runs
# `set +euo pipefail`, under which the pipeline's status is `tail`'s 0 and the
# trailing `|| true` is never exercised at all — the test would pass with or
# without the fix. So mirror the caller's shell inside a subshell (and leave
# this file's own settings untouched).
git() { return 1; }
out="$(
    set -euo pipefail
    github_latest_tag_version beyondeye/aitasks 2>/dev/null
)"; rc=$?
assert_eq "no tags yields an empty version" "" "$out"
assert_eq "no tags survives set -euo pipefail" "0" "$rc"

# --- Test 12-15: the bounded_run path (t2035) -------------------------------
# With `git` NOT a shell function and a usable python, the ls-remote runs under
# lib/bounded_run.py. These cells use PATH stubs instead of functions, so the
# exec'd runner reaches them. The hang stub is a transport PARENT (its own sh,
# which dies on SIGTERM) and a DISTINCT CHILD that ignores SIGTERM: only a
# process-group SIGKILL reaches it, so a cleanup that kills the direct child
# alone -- or the group with SIGTERM alone, as the in-shell fallback does --
# leaves it running.
unset -f git
REAL_GIT="$(type -P git)"
STUB_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ait_ghr_stubs.XXXXXX")"
HANG_PIDS="$STUB_ROOT/hang.pids"
ENV_LOG="$STUB_ROOT/env.log"
PATH_LOG="$STUB_ROOT/path.log"
export REAL_GIT HANG_PIDS ENV_LOG PATH_LOG
trap 'rm -f "$STUB_PIDS"; rm -rf "$STUB_ROOT"' EXIT
export AIT_BOUNDED_RUN_GRACE=1   # the TERM->KILL grace the stubborn child waits out

# make_git_stub <dir> <ls-remote body>: a PATH `git` running <body> for
# ls-remote and the real git for everything else.
make_git_stub() {
    mkdir -p "$1"
    cat > "$1/git" <<EOF
#!/bin/sh
if [ "\${1:-}" = "ls-remote" ]; then
$2
fi
exec "\$REAL_GIT" "\$@"
EOF
    chmod +x "$1/git"
}
make_git_stub "$STUB_ROOT/stubborn" \
    '    sh -c '\''trap "" TERM; exec sleep 30'\'' &
    echo "$$ $!" >> "$HANG_PIDS"
    wait
    exit 0'
make_git_stub "$STUB_ROOT/yielding" \
    '    sh -c '\''exec sleep 30'\'' &
    echo "$$ $!" >> "$HANG_PIDS"
    wait
    exit 0'
make_git_stub "$STUB_ROOT/envrec" \
    '    printf "GIT_ASKPASS=%s|SSH_ASKPASS_REQUIRE=%s|DISPLAY=%s\n" \
        "${GIT_ASKPASS-unset}" "${SSH_ASKPASS_REQUIRE-unset}" "${DISPLAY-unset}" > "$ENV_LOG"
    printf "%s\t%s\n" abc refs/tags/v0.9.0 def refs/tags/v0.10.0
    exit 0'
make_git_stub "$STUB_ROOT/logging" \
    '    echo called >> "$PATH_LOG"
    exit 0'

# hang_pids_alive: every recorded pid still running ("" when all are gone).
hang_pids_alive() {
    local pid alive=""
    for pid in $(cat "$HANG_PIDS" 2>/dev/null); do
        kill -0 "$pid" 2>/dev/null && alive="$alive $pid"
    done
    printf '%s' "${alive# }"
}
hang_pids_kill() {
    local pid
    for pid in $(cat "$HANG_PIDS" 2>/dev/null); do kill -KILL "$pid" 2>/dev/null; done
    : > "$HANG_PIDS"
}

echo "--- Test 12: a stubborn ls-remote transport is bounded and fully reaped ---"
: > "$HANG_PIDS"
start=$SECONDS
out="$(PATH="$STUB_ROOT/stubborn:$PATH" AIT_GIT_LSREMOTE_TIMEOUT=3 \
    github_latest_tag_version beyondeye/aitasks)"; rc=$?
elapsed=$(( SECONDS - start ))
sleep 0.3
assert_eq "12: hanging ls-remote yields no version" "" "$out"
assert_eq "12: hanging ls-remote still exits 0" "0" "$rc"
assert_eq "12: bounded well inside the 30s stub hang" "yes" \
    "$( [[ $elapsed -le 8 ]] && echo yes || echo "no: ${elapsed}s" )"
assert_eq "12: fixture: the parent and its distinct child both started" "2" \
    "$(wc -w < "$HANG_PIDS" | tr -d ' ')"
assert_eq "12: parent and stubborn child were both killed" "" "$(hang_pids_alive)"
hang_pids_kill

echo "--- Test 12c: control: killing the direct child alone leaves the transport ---"
PATH="$STUB_ROOT/stubborn:$PATH" git ls-remote control >/dev/null 2>&1 &
ctl_pid=$!
for _ in $(seq 50); do [[ -s "$HANG_PIDS" ]] && break; sleep 0.05; done
kill -KILL "$ctl_pid" 2>/dev/null
wait "$ctl_pid" 2>/dev/null
sleep 0.2
assert_eq "12c: control: the stubborn child outlives a direct-child kill" "yes" \
    "$( [[ -n "$(hang_pids_alive)" ]] && echo yes || echo no )"
hang_pids_kill

echo "--- Test 13: the bounded ls-remote runs with no prompt channel ---"
out="$(
    unset GIT_ASKPASS SSH_ASKPASS_REQUIRE
    export DISPLAY=:99
    PATH="$STUB_ROOT/envrec:$PATH" github_latest_tag_version beyondeye/aitasks
)"
assert_eq "13: resolves the version" "0.10.0" "$out"
assert_eq "13: GIT_ASKPASS empty, ssh askpass never, no display" \
    "GIT_ASKPASS=|SSH_ASKPASS_REQUIRE=never|DISPLAY=unset" "$(cat "$ENV_LOG" 2>/dev/null)"

echo "--- Test 14: a shell-function git still wins over the exec'd runner ---"
git() {
    if [[ "$1" == "ls-remote" ]]; then
        printf '%s\t%s\n' 'abc123' 'refs/tags/v0.9.0' 'def456' 'refs/tags/v0.10.0'
        return 0
    fi
    command git "$@"
}
: > "$PATH_LOG"
out="$(PATH="$STUB_ROOT/logging:$PATH" github_latest_tag_version beyondeye/aitasks)"
assert_eq "14: the function stub answered" "0.10.0" "$out"
assert_eq "14: the PATH git was never exec'd" "" "$(cat "$PATH_LOG")"
unset -f git

echo "--- Test 15: without a usable python the in-shell fallback still bounds it ---"
: > "$HANG_PIDS"
start=$SECONDS
out="$(PATH="$STUB_ROOT/yielding:$PATH" _AIT_RESOLVED_PYTHON="$(type -P false)" \
    AIT_GIT_LSREMOTE_TIMEOUT=3 github_latest_tag_version beyondeye/aitasks)"; rc=$?
elapsed=$(( SECONDS - start ))
sleep 0.3
assert_eq "15: fallback yields no version" "" "$out"
assert_eq "15: fallback exits 0" "0" "$rc"
assert_eq "15: fallback is bounded" "yes" \
    "$( [[ $elapsed -le 8 ]] && echo yes || echo "no: ${elapsed}s" )"
assert_eq "15: fixture: both stub processes started" "2" \
    "$(wc -w < "$HANG_PIDS" | tr -d ' ')"
assert_eq "15: the fallback's group SIGTERM reaped them" "" "$(hang_pids_alive)"
hang_pids_kill
unset AIT_BOUNDED_RUN_GRACE

# --- Summary ---
echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
