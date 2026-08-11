#!/usr/bin/env bash
# tests/lib/asserts.sh — shared assertion helpers for the test suite.
#
# Source AFTER tests/lib/test_scaffold.sh, via the absolute $PROJECT_DIR path:
#     . "$PROJECT_DIR/tests/lib/test_scaffold.sh"
#     . "$PROJECT_DIR/tests/lib/asserts.sh"
#
# These functions mutate the caller's file-local PASS / FAIL / TOTAL counters
# (referenced here as globals). Each test file keeps its own `PASS=0/FAIL=0/
# TOTAL=0` initialisation and prints its own results summary.
#
# A test file whose bodies run inside `( … )` subshells must instead opt into
# the file-backed counters below (assert_counters_init / assert_counters_load):
# an in-process increment does not survive a subshell, so such a file's footer
# would otherwise report zero failures and exit 0. See the "counters" section.
#
# Consolidates the helpers that were duplicated inline across ~136 test files
# (see t923). Single-use / domain-specific helpers (assert_exit_code,
# assert_yaml_valid, …) intentionally stay inline in their one file.
#
# BSD-safe: only POSIX/BSD grep flags (-qF, -qiF, -qE) and the t920 `--`
# end-of-options guard. No GNU-only grep/sed. See
# aidocs/framework/sed_macos_issues.md. bash-3.2-safe (no mapfile, declare -A,
# or ${var^^}).

# Idempotent: guard against double-sourcing (a file may transitively source us).
[[ -n "${_AIT_ASSERTS_LOADED:-}" ]] && return 0
_AIT_ASSERTS_LOADED=1

# --- counters --------------------------------------------------------------
# By default the helpers below mutate the caller's in-process PASS / FAIL /
# TOTAL, exactly as they always have. A file whose test bodies run inside
# `( … )` subshells loses those increments at subshell exit, so it opts into a
# file-backed record instead:
#
#     assert_counters_init                 # once, after sourcing this file
#     trap 'rm -f "$AIT_ASSERT_COUNTER_FILE"' EXIT
#     ...tests...
#     assert_counters_load                 # in the footer, before reporting
#     [[ "$FAIL" -eq 0 ]] || exit 1
#
# FAIL-CLOSED CONTRACT. Once counting is enabled, any failure to persist or
# re-read the record is itself a test failure. A record that is missing,
# unreadable, truncated or recreated must NEVER be reported as "0 failures" —
# that silent false-green is the exact defect this mechanism exists to remove
# (t1207: eleven files printed `FAIL:` lines and still exited 0 for two years).
#
# Two design points serve that contract:
#
#   * Enablement is tracked by AIT_ASSERT_COUNTERS_ENABLED, deliberately
#     SEPARATE from the path variable. "Enabled but no usable file" is then a
#     detectable state instead of degrading silently into the no-op branch.
#   * The first line is a sentinel. `>>` RECREATES a deleted file, so
#     absence-of-file is not observable at load time — absence of the sentinel
#     is. Any append failure deletes the record on purpose, converting an
#     undetectable short count into a detectable corrupted one.
#
# With AIT_ASSERT_COUNTERS_ENABLED unset every branch below is skipped and
# behaviour is identical to the pre-t1207 library, so the ~245 files that
# assert at top level are unaffected.

AIT_ASSERT_COUNTER_SENTINEL="#ait-assert-counters-v1"

assert_counters_init() {
    if ! AIT_ASSERT_COUNTER_FILE="$(mktemp "${TMPDIR:-/tmp}/ait_assert_counters_XXXXXX")"; then
        echo "FAIL: assert_counters_init could not create a counter file" >&2
        exit 1
    fi
    if ! printf '%s\n' "$AIT_ASSERT_COUNTER_SENTINEL" > "$AIT_ASSERT_COUNTER_FILE"; then
        echo "FAIL: assert_counters_init could not write $AIT_ASSERT_COUNTER_FILE" >&2
        exit 1
    fi
    AIT_ASSERT_COUNTERS_ENABLED=1
    PASS=0
    FAIL=0
    TOTAL=0
    return 0
}

# $1 = P | F. Never fails the caller directly: it usually runs deep inside a
# subshell, where a non-zero return would only abort that subshell and leave the
# parent none the wiser. An unpersistable record is destroyed instead, so
# assert_counters_load fails closed at the top level where the exit status is
# actually observed.
_assert_counter_append() {
    [ -n "${AIT_ASSERT_COUNTERS_ENABLED:-}" ] || return 0
    if ! printf '%s\n' "$1" >> "$AIT_ASSERT_COUNTER_FILE" 2>/dev/null; then
        rm -f "$AIT_ASSERT_COUNTER_FILE" 2>/dev/null || true
    fi
    return 0
}

# Record one passing / failing check. Callers that hand-roll a check instead of
# using an assert_* helper call these directly; as with the helpers, a failing
# caller prints its own `FAIL: …` line.
assert_record_pass() {
    TOTAL=$((TOTAL + 1))
    PASS=$((PASS + 1))
    _assert_counter_append P
    return 0
}

assert_record_fail() {
    TOTAL=$((TOTAL + 1))
    FAIL=$((FAIL + 1))
    _assert_counter_append F
    return 0
}

# Re-read the file-backed record into PASS / FAIL / TOTAL. A genuine no-op when
# counting was never enabled, so a footer may call it unconditionally. Call it
# bare, not as `assert_counters_load || true`: under `set -e` a corrupted record
# aborts the script non-zero on the spot, and for a caller without `set -e` the
# FAIL bump below makes the existing exit guard fire. Both paths are non-zero.
assert_counters_load() {
    local t f head
    [ -n "${AIT_ASSERT_COUNTERS_ENABLED:-}" ] || return 0

    if [ ! -r "${AIT_ASSERT_COUNTER_FILE:-}" ]; then
        echo "FAIL: assert counters enabled but the record is missing or unreadable (${AIT_ASSERT_COUNTER_FILE:-<unset>})"
        TOTAL=$((TOTAL + 1))
        FAIL=$((FAIL + 1))
        return 1
    fi
    head="$(head -n 1 "$AIT_ASSERT_COUNTER_FILE")"
    if [ "$head" != "$AIT_ASSERT_COUNTER_SENTINEL" ]; then
        echo "FAIL: assert counter record was truncated or recreated (sentinel missing) — counts cannot be trusted"
        TOTAL=$((TOTAL + 1))
        FAIL=$((FAIL + 1))
        return 1
    fi
    # `|| true`: grep -c exits 1 on zero matches, which would abort under set -e.
    # tr: BSD grep/wc pad their counts (see aidocs/framework/sed_macos_issues.md).
    t="$(grep -c '^[PF]$' "$AIT_ASSERT_COUNTER_FILE" || true)"
    f="$(grep -c '^F$'    "$AIT_ASSERT_COUNTER_FILE" || true)"
    t="$(printf '%s' "$t" | tr -d '[:space:]')"
    f="$(printf '%s' "$f" | tr -d '[:space:]')"
    TOTAL="${t:-0}"
    FAIL="${f:-0}"
    PASS=$((TOTAL - FAIL))
    return 0
}

# --- equality --------------------------------------------------------------

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    if [[ "$expected" == "$actual" ]]; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: $desc (expected '$expected', got '$actual')"
    fi
}

# Whitespace-trimming equality. Absorbs BSD `wc -l`'s leading-space padding on
# macOS (where `echo "$x" | wc -l` yields "       1", not "1"). Files whose
# inline assert_eq trimmed via xargs/tr migrate to this; non-trimming files
# stay on assert_eq above. See aidocs/framework/sed_macos_issues.md
# ("wc -l Output Whitespace").
assert_eq_trim() {
    local desc="$1" expected actual
    expected="$(printf '%s' "$2" | xargs)"
    actual="$(printf '%s' "$3" | xargs)"
    if [[ "$expected" == "$actual" ]]; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: $desc (expected '$expected', got '$actual')"
    fi
}

# --- substring / pattern containment ---------------------------------------
# Default flavor is fixed-string (literal) match: the plurality flavor in the
# suite and the safest (no regex-metacharacter surprises). Use the _ci variant
# for case-insensitive matching and the _re variant for extended-regex.
# All carry the t920 `--` end-of-options guard.

assert_contains() {
    local desc="$1" needle="$2" haystack="$3"
    if printf '%s' "$haystack" | grep -qF -- "$needle"; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: $desc (expected output containing '$needle', got '$haystack')"
    fi
}

assert_not_contains() {
    local desc="$1" needle="$2" haystack="$3"
    if printf '%s' "$haystack" | grep -qF -- "$needle"; then
        assert_record_fail
        echo "FAIL: $desc (expected output NOT containing '$needle', got '$haystack')"
    else
        assert_record_pass
    fi
}

# Case-insensitive (fixed-string) variants.
assert_contains_ci() {
    local desc="$1" needle="$2" haystack="$3"
    if printf '%s' "$haystack" | grep -qiF -- "$needle"; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: $desc (expected output containing (ci) '$needle', got '$haystack')"
    fi
}

assert_not_contains_ci() {
    local desc="$1" needle="$2" haystack="$3"
    if printf '%s' "$haystack" | grep -qiF -- "$needle"; then
        assert_record_fail
        echo "FAIL: $desc (expected output NOT containing (ci) '$needle', got '$haystack')"
    else
        assert_record_pass
    fi
}

# Extended-regex (case-sensitive) variants.
assert_contains_re() {
    local desc="$1" pattern="$2" haystack="$3"
    if printf '%s' "$haystack" | grep -qE -- "$pattern"; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: $desc (expected output matching /$pattern/, got '$haystack')"
    fi
}

assert_not_contains_re() {
    local desc="$1" pattern="$2" haystack="$3"
    if printf '%s' "$haystack" | grep -qE -- "$pattern"; then
        assert_record_fail
        echo "FAIL: $desc (expected output NOT matching /$pattern/, got '$haystack')"
    else
        assert_record_pass
    fi
}

# --- exit code -------------------------------------------------------------

assert_exit_zero() {
    local desc="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: $desc (command exited non-zero)"
    fi
}

assert_exit_nonzero() {
    local desc="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        assert_record_fail
        echo "FAIL: $desc (expected non-zero exit, got 0)"
    else
        assert_record_pass
    fi
}

# Captured-return-code variants. Where the assert_exit_zero/_nonzero pair above
# RUNS a command, these assert on a numeric exit code the caller already
# captured (e.g. `cmd; rc=$?` after also grabbing stdout). Used by tests that
# need the command's output and its status separately. desc + rc, not a command.
assert_exit_zero_rc() {
    local desc="$1" rc="$2"
    if [[ "$rc" -eq 0 ]]; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: $desc (expected zero exit, got $rc)"
    fi
}

assert_exit_nonzero_rc() {
    local desc="$1" rc="$2"
    if [[ "$rc" -ne 0 ]]; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: $desc (expected non-zero exit, got 0)"
    fi
}

# --- filesystem ------------------------------------------------------------

assert_file_exists() {
    local desc="$1" path="$2"
    if [[ -f "$path" ]]; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: $desc (file not found: $path)"
    fi
}

assert_file_not_exists() {
    local desc="$1" path="$2"
    if [[ ! -f "$path" ]]; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: $desc (file unexpectedly exists: $path)"
    fi
}

assert_dir_exists() {
    local desc="$1" path="$2"
    if [[ -d "$path" ]]; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: $desc (dir not found: $path)"
    fi
}

assert_dir_not_exists() {
    local desc="$1" path="$2"
    if [[ ! -d "$path" ]]; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: $desc (dir unexpectedly exists: $path)"
    fi
}
