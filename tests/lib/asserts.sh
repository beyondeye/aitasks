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

# --- equality --------------------------------------------------------------

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
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
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
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
    TOTAL=$((TOTAL + 1))
    if printf '%s' "$haystack" | grep -qF -- "$needle"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$needle', got '$haystack')"
    fi
}

assert_not_contains() {
    local desc="$1" needle="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if printf '%s' "$haystack" | grep -qF -- "$needle"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output NOT containing '$needle', got '$haystack')"
    else
        PASS=$((PASS + 1))
    fi
}

# Case-insensitive (fixed-string) variants.
assert_contains_ci() {
    local desc="$1" needle="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if printf '%s' "$haystack" | grep -qiF -- "$needle"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing (ci) '$needle', got '$haystack')"
    fi
}

assert_not_contains_ci() {
    local desc="$1" needle="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if printf '%s' "$haystack" | grep -qiF -- "$needle"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output NOT containing (ci) '$needle', got '$haystack')"
    else
        PASS=$((PASS + 1))
    fi
}

# Extended-regex (case-sensitive) variants.
assert_contains_re() {
    local desc="$1" pattern="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if printf '%s' "$haystack" | grep -qE -- "$pattern"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output matching /$pattern/, got '$haystack')"
    fi
}

assert_not_contains_re() {
    local desc="$1" pattern="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if printf '%s' "$haystack" | grep -qE -- "$pattern"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output NOT matching /$pattern/, got '$haystack')"
    else
        PASS=$((PASS + 1))
    fi
}

# --- exit code -------------------------------------------------------------

assert_exit_zero() {
    local desc="$1"
    shift
    TOTAL=$((TOTAL + 1))
    if "$@" >/dev/null 2>&1; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (command exited non-zero)"
    fi
}

assert_exit_nonzero() {
    local desc="$1"
    shift
    TOTAL=$((TOTAL + 1))
    if "$@" >/dev/null 2>&1; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected non-zero exit, got 0)"
    else
        PASS=$((PASS + 1))
    fi
}

# Captured-return-code variants. Where the assert_exit_zero/_nonzero pair above
# RUNS a command, these assert on a numeric exit code the caller already
# captured (e.g. `cmd; rc=$?` after also grabbing stdout). Used by tests that
# need the command's output and its status separately. desc + rc, not a command.
assert_exit_zero_rc() {
    local desc="$1" rc="$2"
    TOTAL=$((TOTAL + 1))
    if [[ "$rc" -eq 0 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected zero exit, got $rc)"
    fi
}

assert_exit_nonzero_rc() {
    local desc="$1" rc="$2"
    TOTAL=$((TOTAL + 1))
    if [[ "$rc" -ne 0 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected non-zero exit, got 0)"
    fi
}

# --- filesystem ------------------------------------------------------------

assert_file_exists() {
    local desc="$1" path="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -f "$path" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (file not found: $path)"
    fi
}

assert_file_not_exists() {
    local desc="$1" path="$2"
    TOTAL=$((TOTAL + 1))
    if [[ ! -f "$path" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (file unexpectedly exists: $path)"
    fi
}

assert_dir_exists() {
    local desc="$1" path="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -d "$path" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (dir not found: $path)"
    fi
}

assert_dir_not_exists() {
    local desc="$1" path="$2"
    TOTAL=$((TOTAL + 1))
    if [[ ! -d "$path" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (dir unexpectedly exists: $path)"
    fi
}
