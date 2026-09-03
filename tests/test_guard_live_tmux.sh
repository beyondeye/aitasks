#!/usr/bin/env bash
# test_guard_live_tmux.sh — pins the PreToolUse guard that blocks an agent
# Bash command from reaching a tmux server it did not name (t1699).
#
# On 2026-09-03 09:39:54 an ad-hoc probe run from inside a live `ait` pane —
#     TMUX_TMPDIR=$D tmux new-session -d -s probe ... ; TMUX_TMPDIR=$D tmux kill-server
# — killed the user's real `tmux -L ait` server and every pane in it, because
# tmux resolves its socket from $TMUX and ignores TMUX_TMPDIR whenever $TMUX is
# set. `.claude/hooks/guard_live_tmux.py` denies that shape.
#
# The guard is driven through its REAL entry point (hook JSON on stdin), not a
# helper function, so a change to the payload contract fails here too.
#
# Run: bash tests/test_guard_live_tmux.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

GUARD="$PROJECT_DIR/.claude/hooks/guard_live_tmux.py"

if [[ ! -x "$GUARD" ]]; then
    echo "FAIL: guard hook missing or not executable: $GUARD"
    exit 1
fi

# Feed a Bash command through the hook exactly as Claude Code would, and echo
# the resulting permission decision ("deny" or "allow").
decision_for() {
    local cmd="$1" out
    out="$(printf '%s' "$cmd" \
        | python3 -c 'import json,sys; print(json.dumps({"tool_name":"Bash","tool_input":{"command":sys.stdin.read()}}))' \
        | "$GUARD" 2>/dev/null)"
    if [[ -z "$out" ]]; then
        echo "allow"
    else
        printf '%s' "$out" \
            | python3 -c 'import json,sys; print(json.load(sys.stdin)["hookSpecificOutput"]["permissionDecision"])' \
            2>/dev/null || echo "unparseable:$out"
    fi
}

reason_for() {
    local cmd="$1"
    printf '%s' "$cmd" \
        | python3 -c 'import json,sys; print(json.dumps({"tool_name":"Bash","tool_input":{"command":sys.stdin.read()}}))' \
        | "$GUARD" 2>/dev/null
}

echo "=== DENY: the shapes that cost a live server ==="

# The verbatim command from the t1699 session transcript (06:39:52 UTC).
# Single-quoted on purpose: the guard must judge the command as written,
# so nothing in it may expand here.
# shellcheck disable=SC2016
T1699_PROBE='D=$(mktemp -d) && TMUX_TMPDIR=$D tmux new-session -d -s probe "tail -f /dev/null" 2>/dev/null && TMUX_TMPDIR=$D tmux split-window -t probe "tail -f /dev/null" && TMUX_TMPDIR=$D tmux kill-server 2>/dev/null; rm -rf $D'
assert_eq "the verbatim t1699 probe is denied" "deny" "$(decision_for "$T1699_PROBE")"

assert_eq "bare kill-server is denied" "deny" "$(decision_for 'tmux kill-server')"
assert_eq "bare kill-session is denied" "deny" "$(decision_for 'tmux kill-session -t probe')"
assert_eq "bare kill-pane is denied" "deny" "$(decision_for 'tmux kill-pane -t %53')"
assert_eq "bare respawn-pane is denied" "deny" "$(decision_for 'tmux respawn-pane -k -t %53')"
assert_eq "a destructive call in a later segment is denied" "deny" "$(decision_for 'echo hi && tmux kill-server')"
assert_eq "TMUX_TMPDIR with no -L is denied even for a read-only verb" "deny" "$(decision_for 'TMUX_TMPDIR=/tmp/x tmux list-panes -a')"
assert_eq "an absolute tmux path is denied too" "deny" "$(decision_for '/usr/bin/tmux kill-server')"

# The message must teach the fix, not merely refuse (a bare refusal gets worked
# around; this is the half that changes the next command).
REASON="$(reason_for 'tmux kill-server')"
assert_contains "the denial names the -L flag as the fix" "-L" "$REASON"
assert_contains "the denial cites the incident" "t1699" "$REASON"
assert_contains "the denial points at the test helper" "tmux_isolation.sh" "$REASON"

echo
echo "=== ALLOW: everything legitimate stays unblocked ==="

assert_eq "an explicitly-socketed throwaway kill is allowed" "allow" "$(decision_for 'tmux -L throwaway kill-server')"
assert_eq "the attached -L form is recognised" "allow" "$(decision_for 'tmux -Lthrowaway kill-server')"
assert_eq "-S counts as naming the server" "allow" "$(decision_for 'tmux -S /tmp/sock kill-server')"
assert_eq "a deliberate, explicit kill on the live server is allowed" "allow" "$(decision_for 'tmux -L ait kill-pane -t %53')"
assert_eq "socketed read-only calls are allowed" "allow" "$(decision_for 'tmux -L ait list-panes -a')"
assert_eq "stripping TMUX makes the TMUX_TMPDIR redirect real, so it is allowed" "allow" "$(decision_for 'env -u TMUX TMUX_TMPDIR=/tmp/x tmux new-session -d -s probe')"
assert_eq "a command with no tmux in it is allowed" "allow" "$(decision_for 'git status')"
assert_eq "running a tmux test script is allowed (isolation is the script's job)" "allow" "$(decision_for 'bash tests/test_kill_agent_pane_smart.sh')"
assert_eq "searching for the phrase is not issuing it" "allow" "$(decision_for 'grep -rn "tmux kill-server" tests/')"

# Authoring a fixture must stay possible: a heredoc writes a file, it does not
# run tmux, and the later `bash file.sh` carries no tmux token for the hook to
# judge. Documented as a known boundary in the hook.
HEREDOC='cat > /tmp/f.sh <<EOF
unset TMUX
tmux kill-server
EOF'
assert_eq "a heredoc body is authoring, not execution (documented boundary)" "allow" "$(decision_for "$HEREDOC")"

echo
echo "=== Fail-closed on an unparseable command ==="
assert_eq "an unparseable command naming a destructive verb is denied, not waved through" "deny" "$(decision_for 'tmux kill-server "unbalanced')"

echo
echo "==================== SUMMARY ===================="
echo "Total:  $TOTAL"
echo "Passed: $PASS"
echo "Failed: $FAIL"
if [[ "$FAIL" -eq 0 ]]; then
    echo "RESULT: PASS"
    exit 0
else
    echo "RESULT: FAIL"
    exit 1
fi
