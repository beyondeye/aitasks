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
# Tests: wrap-join (-J) over a live tmux pane (t1037_4)
# ============================================================
# Proves the script actually passes `capture-pane -J`: a logical line longer
# than the pane width must come back contiguous, not split mid-string by a
# soft-wrap (the concern parser's capture-join contract). Runs on an isolated
# dedicated socket so it never touches the user's tmux server; skipped when
# tmux is unavailable or a test pane cannot be started.
echo "--- wrap-join (-J) live tmux ---"
if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not available — -J join test skipped"
else
    JSOCK="ait_jtest_$$"
    LONG="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    # 20-col pane forces the 62-char string to soft-wrap across display rows.
    tmux -L "$JSOCK" new-session -d -x 20 -y 10 \
        "printf '%s' '$LONG'; sleep 30" 2>/dev/null || true
    jpane=""
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        jpane=$(tmux -L "$JSOCK" list-panes -F '#{pane_id}' 2>/dev/null | head -1 || true)
        [[ -n "$jpane" ]] && break
        sleep 0.1
    done
    jout=""
    if [[ -n "$jpane" ]]; then
        # Poll until the pane's printf output has rendered (the pane exists
        # before its command emits anything — capturing too early races to "").
        for _ in 1 2 3 4 5 6 7 8 9 10; do
            jout=$(AITASKS_TMUX_SOCKET="$JSOCK" "$CAPTURE" "$jpane" 2>/dev/null || true)
            [[ -n "$jout" ]] && break
            sleep 0.1
        done
    fi
    tmux -L "$JSOCK" kill-server 2>/dev/null || true
    if [[ -z "$jpane" ]]; then
        echo "SKIP: could not start test tmux pane — -J join test skipped"
    else
        assert_contains "-J rejoins a soft-wrapped logical line (contiguous)" \
            "$LONG" "$jout"
    fi
fi

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
