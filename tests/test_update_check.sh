#!/usr/bin/env bash
# test_update_check.sh - regression for t706 update-check cache validation
#
# Verifies that the `ait` dispatcher's update-check path is robust against:
#   - corrupt cached_version (the live-observed failure: a JSON token left
#     by a prior buggy parse)
#   - corrupt cached_time (non-numeric token in the time slot)
#   - empty cache file
#
# The dispatcher must run cleanly (no arithmetic-syntax noise on stderr) and
# self-recover the cache file on next invocation.
#
# Run: bash tests/test_update_check.sh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/test_update_check.XXXXXX")"
trap 'rm -rf "$SCRATCH"' EXIT

PASS=0
FAIL=0
TOTAL=0

assert_no_match() {
    local desc="$1" pattern="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$haystack" | grep -qE "$pattern"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc"
        echo "  expected NOT to contain: $pattern"
        echo "  actual stderr:"
        echo "$haystack" | sed 's/^/    /'
    else
        PASS=$((PASS + 1))
    fi
}

assert_match() {
    local desc="$1" pattern="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$haystack" | grep -qE "$pattern"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc"
        echo "  expected to contain: $pattern"
        echo "  actual: $haystack"
    fi
}

# `ait ls -h` is a fast, side-effect-free command that DOES trigger
# check_for_updates (the meta-command exclusion list does not include `ls`).
# We capture stderr only — the background curl child writes nothing to stderr
# in normal operation, but spurious arithmetic errors from check_for_updates
# would land on the foreground stderr.
run_ait() {
    HOME="$SCRATCH" "$PROJECT_DIR/ait" ls -h 2>&1 1>/dev/null || true
}

mkdir -p "$SCRATCH/.aitask"

# === Case 1: corrupt cached_version (the live-observed failure) ===========
printf '%s\n' '1777387840   "tag_name": "v0.19.1",' > "$SCRATCH/.aitask/update_check"
err="$(run_ait)"
assert_no_match "Case 1: no syntax error on corrupt cached_version" \
    'syntax error|value too great' "$err"
# Cache must auto-recover — either removed or rewritten with a valid version.
if [[ -f "$SCRATCH/.aitask/update_check" ]]; then
    line="$(head -1 "$SCRATCH/.aitask/update_check")"
    ver="$(echo "$line" | awk '{print $2}')"
    if [[ -n "$ver" && ! "$ver" =~ ^[0-9]+(\.[0-9]+)*$ ]]; then
        FAIL=$((FAIL + 1))
        TOTAL=$((TOTAL + 1))
        echo "FAIL: Case 1: cache not recovered: $line"
    else
        PASS=$((PASS + 1))
        TOTAL=$((TOTAL + 1))
    fi
else
    # Removed entirely is also acceptable recovery.
    PASS=$((PASS + 1))
    TOTAL=$((TOTAL + 1))
fi

# === Case 2: corrupt cached_time (non-numeric) ============================
printf '%s\n' 'notatime 0.18.1' > "$SCRATCH/.aitask/update_check"
err="$(run_ait)"
assert_no_match "Case 2: no syntax error on non-numeric cached_time" \
    'syntax error|value too great' "$err"

# === Case 3: empty cache file ============================================
: > "$SCRATCH/.aitask/update_check"
err="$(run_ait)"
assert_no_match "Case 3: no errors on empty cache" \
    'syntax error|value too great' "$err"

# === Case 4: missing cache file (fresh install) ==========================
rm -f "$SCRATCH/.aitask/update_check"
err="$(run_ait)"
assert_no_match "Case 4: no errors when cache file does not exist" \
    'syntax error|value too great' "$err"

# === Case 5: valid cache file is preserved (no rewrite needed) ============
# A fresh, valid cache must NOT be rewritten by the validator path.
printf '%s\n' "$(date +%s) 0.18.1" > "$SCRATCH/.aitask/update_check"
err="$(run_ait)"
assert_no_match "Case 5: no errors on valid cache" \
    'syntax error|value too great' "$err"
# The cached version should still be present and well-formed.
if [[ -f "$SCRATCH/.aitask/update_check" ]]; then
    line="$(head -1 "$SCRATCH/.aitask/update_check")"
    ver="$(echo "$line" | awk '{print $2}')"
    assert_match "Case 5: valid cache preserved" '^[0-9]+(\.[0-9]+)*$' "$ver"
fi

echo ""
echo "Tests: $TOTAL  Pass: $PASS  Fail: $FAIL"
if (( FAIL > 0 )); then
    exit 1
fi
