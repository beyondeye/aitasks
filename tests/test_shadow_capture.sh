#!/usr/bin/env bash
# test_shadow_capture.sh - Automated tests for aitask_shadow_capture.sh
# Run: bash tests/test_shadow_capture.sh
#
# Exercises the clean/strip logic via the `-` stdin seam (no live tmux) plus
# argument validation as a subprocess. The tmux capture path itself is covered
# by the manual-verification sibling (t986_7) and tests/test_no_raw_tmux.sh
# (gateway-only routing).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

CAPTURE="$PROJECT_DIR/.aitask-scripts/aitask_shadow_capture.sh"

ESC=$(printf '\033')

# ============================================================
# Tests: ANSI / CSI escape stripping (stdin seam)
# ============================================================
echo "--- ansi stripping ---"

out=$(printf '%s[31mRED%s[0m and %s[1mBOLD%s[0m\n' "$ESC" "$ESC" "$ESC" "$ESC" | "$CAPTURE" -)
assert_eq "SGR colour/bold codes stripped, text kept" "RED and BOLD" "$out"
assert_not_contains "no raw ESC byte remains" "$ESC" "$out"

# Cursor-movement CSI (parameter + intermediate + final bytes)
out=$(printf '%s[2J%s[1;1Hhello\n' "$ESC" "$ESC" | "$CAPTURE" -)
assert_eq "cursor/clear CSI stripped" "hello" "$out"

# Plain text passes through unchanged
out=$(printf 'plain line one\nplain line two\n' | "$CAPTURE" -)
assert_eq "plain text unchanged" "plain line one
plain line two" "$out"

# ============================================================
# Tests: whitespace / trailing-blank normalization
# ============================================================
echo "--- whitespace normalization ---"

out=$(printf 'trailing spaces   \n' | "$CAPTURE" -)
assert_eq "trailing whitespace per line stripped" "trailing spaces" "$out"

# Trailing blank + whitespace-only lines dropped; interior blank kept
out=$(printf 'a\n\nb\n   \n\n' | "$CAPTURE" -)
assert_eq "trailing blank lines dropped, interior blank kept" "a

b" "$out"

# ============================================================
# Tests: argument validation
# ============================================================
echo "--- input validation ---"

out=$("$CAPTURE" 2>&1 </dev/null || true)
assert_contains "missing pane id rejected" "pane id required" "$out"

rc=0
"$CAPTURE" </dev/null >/dev/null 2>&1 || rc=$?
assert_eq "missing pane id exits non-zero" "1" "$rc"

out=$("$CAPTURE" --bogus 2>&1 </dev/null || true)
assert_contains "unknown option rejected" "Unknown option" "$out"

out=$("$CAPTURE" %1 %2 2>&1 </dev/null || true)
assert_contains "extra argument rejected" "Unexpected extra argument" "$out"

out=$("$CAPTURE" --help 2>&1)
assert_contains "help shows usage" "Usage:" "$out"

# ============================================================
# Summary
# ============================================================
echo ""
echo "=============================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=============================="

if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
