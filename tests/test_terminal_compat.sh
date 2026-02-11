#!/bin/bash
# test_terminal_compat.sh - Automated tests for terminal capability detection
# Run: bash tests/test_terminal_compat.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$PROJECT_DIR/aiscripts/lib/terminal_compat.sh"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

clean_env() {
    unset COLORTERM WT_SESSION TERM_PROGRAM TERM TMUX STY AIT_TERMINAL_CAPABLE AIT_SKIP_TERMINAL_CHECK 2>/dev/null || true
}

assert_capable() {
    local desc="$1"
    TOTAL=$((TOTAL + 1))
    unset AIT_TERMINAL_CAPABLE 2>/dev/null || true
    if ait_check_terminal_capable; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected capable)"
    fi
}

assert_not_capable() {
    local desc="$1"
    TOTAL=$((TOTAL + 1))
    unset AIT_TERMINAL_CAPABLE 2>/dev/null || true
    if ait_check_terminal_capable; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected NOT capable)"
    else
        PASS=$((PASS + 1))
    fi
}

assert_output_contains() {
    local desc="$1" expected="$2" output="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$output" | grep -qi "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected')"
    fi
}

assert_output_empty() {
    local desc="$1" output="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -z "$output" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected empty output, got: '$(echo "$output" | head -1)...')"
    fi
}

echo "=== Terminal Compatibility Tests ==="
echo ""

# --- COLORTERM detection tests ---
echo "--- COLORTERM detection ---"

clean_env
COLORTERM=truecolor
assert_capable "COLORTERM=truecolor"

clean_env
COLORTERM=24bit
assert_capable "COLORTERM=24bit"

clean_env
COLORTERM=256color
assert_not_capable "COLORTERM=256color (not truecolor)"

clean_env
COLORTERM=""
assert_not_capable "COLORTERM=empty string"

# --- WT_SESSION detection ---
echo "--- WT_SESSION detection ---"

clean_env
WT_SESSION="{some-guid-value}"
assert_capable "WT_SESSION set"

# --- TERM_PROGRAM detection ---
echo "--- TERM_PROGRAM detection ---"

clean_env
TERM_PROGRAM=WezTerm
assert_capable "TERM_PROGRAM=WezTerm"

clean_env
TERM_PROGRAM=Alacritty
assert_capable "TERM_PROGRAM=Alacritty"

clean_env
TERM_PROGRAM=vscode
assert_capable "TERM_PROGRAM=vscode"

clean_env
TERM_PROGRAM="iTerm.app"
assert_capable "TERM_PROGRAM=iTerm.app"

clean_env
TERM_PROGRAM=Hyper
assert_capable "TERM_PROGRAM=Hyper"

clean_env
TERM_PROGRAM=Tabby
assert_capable "TERM_PROGRAM=Tabby"

clean_env
TERM_PROGRAM=tmux
assert_capable "TERM_PROGRAM=tmux"

clean_env
TERM_PROGRAM=unknown
assert_not_capable "TERM_PROGRAM=unknown"

# --- TERM detection ---
echo "--- TERM detection ---"

clean_env
TERM=xterm-256color
assert_capable "TERM=xterm-256color"

clean_env
TERM=xterm-kitty
assert_capable "TERM=xterm-kitty"

clean_env
TERM=alacritty
assert_capable "TERM=alacritty"

clean_env
TERM=tmux-256color
assert_capable "TERM=tmux-256color"

clean_env
TERM=screen-256color
assert_capable "TERM=screen-256color"

clean_env
TERM=dumb
assert_not_capable "TERM=dumb"

clean_env
TERM=vt100
assert_not_capable "TERM=vt100"

# --- TMUX/Screen detection ---
echo "--- TMUX/Screen detection ---"

clean_env
TMUX="/tmp/tmux-1000/default,12345,0"
assert_capable "TMUX set"

clean_env
STY="12345.pts-0.host"
assert_capable "STY set (screen)"

# --- No indicators ---
echo "--- No indicators ---"

clean_env
assert_not_capable "All vars unset"

# --- Caching tests ---
# Note: these must NOT use assert_capable/assert_not_capable since those reset the cache
echo "--- Caching tests ---"

clean_env
AIT_TERMINAL_CAPABLE=1
TOTAL=$((TOTAL + 1))
if ait_check_terminal_capable; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Cached capable=1 (expected capable)"
fi

clean_env
AIT_TERMINAL_CAPABLE=0
TOTAL=$((TOTAL + 1))
if ait_check_terminal_capable; then
    FAIL=$((FAIL + 1))
    echo "FAIL: Cached capable=0 (expected not capable)"
else
    PASS=$((PASS + 1))
fi

# --- Warning function tests ---
echo "--- Warning function tests ---"

# Test suppression via AIT_SKIP_TERMINAL_CHECK
clean_env
AIT_SKIP_TERMINAL_CHECK=1
output=$(ait_warn_if_incapable_terminal 2>&1)
assert_output_empty "AIT_SKIP_TERMINAL_CHECK=1 suppresses output" "$output"

# Test capable terminal produces no warning
clean_env
COLORTERM=truecolor
output=$(ait_warn_if_incapable_terminal 2>&1)
assert_output_empty "Capable terminal produces no warning" "$output"

# Test incapable terminal shows warning
clean_env
output=$(ait_warn_if_incapable_terminal 2>&1)
assert_output_contains "Incapable terminal shows warning" "terminal" "$output"

# Test warning mentions suppression env var
clean_env
output=$(ait_warn_if_incapable_terminal 2>&1)
assert_output_contains "Warning mentions AIT_SKIP_TERMINAL_CHECK" "AIT_SKIP_TERMINAL_CHECK" "$output"

# --- Syntax checks for modified scripts ---
echo "--- Syntax checks ---"

for script in aitask_create.sh aitask_update.sh aitask_issue_import.sh \
              aitask_board.sh aitask_clear_old.sh aitask_issue_update.sh; do
    TOTAL=$((TOTAL + 1))
    if bash -n "$PROJECT_DIR/aiscripts/$script" 2>/dev/null; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: bash -n $script (syntax error)"
    fi
done

# Syntax check for the library itself
TOTAL=$((TOTAL + 1))
if bash -n "$PROJECT_DIR/aiscripts/lib/terminal_compat.sh" 2>/dev/null; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: bash -n lib/terminal_compat.sh (syntax error)"
fi

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
