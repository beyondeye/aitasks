#!/usr/bin/env bash
# test_ide_frozen_offer.sh - `ait ide`'s frozen-agent offer (t1847).
#
# Drives `ide_offer_frozen_agents` from lib/ide_frozen_offer.sh against a STUB
# `aitask_frozen.sh` that logs its argv and answers `gone` from canned files
# (a first and a second answer, because R/P re-classify after reopening). No
# tmux, no store. The interactive branch is reached through the test-mode-only
# AIT_IDE_FROZEN_ASSUME_TTY seam; the answer arrives on stdin.
#
# Also checks that aitask_ide.sh accepts --no-frozen-check and documents it.
#
# Run: bash tests/test_ide_frozen_offer.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

LIB="$PROJECT_DIR/.aitask-scripts/lib/ide_frozen_offer.sh"
IDE="$PROJECT_DIR/.aitask-scripts/aitask_ide.sh"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/t1847_offer_XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

STUB="$TMP/frozen_stub.sh"
cat > "$STUB" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$STUB_LOG"
case "$1" in
    gone)
        n=$(( $(cat "$STUB_DIR/gone_count" 2>/dev/null || echo 0) + 1 ))
        echo "$n" > "$STUB_DIR/gone_count"
        [[ -f "$STUB_DIR/gone_fail" ]] && exit 1
        f="$STUB_DIR/gone$n"
        [[ -f "$f" ]] || f="$STUB_DIR/gone1"
        cat "$f"
        ;;
    reopen)
        if [[ -f "$STUB_DIR/reopen_crash" ]]; then
            echo "Traceback (most recent call last): boom" >&2
            exit 3
        fi
        echo "REOPENED:aaaaaaaa|fresh|S:w|%1"; echo "REOPEN_ALL:1/1" ;;
    restore) echo "RESTORED:$2|hook" ;;
esac
exit 0
STUB
chmod +x "$STUB"

# scenario <name> <gone1 body> [gone2 body] — fresh stub state.
scenario() {
    STUB_DIR="$TMP/$1"
    mkdir -p "$STUB_DIR"
    printf '%b' "$2" > "$STUB_DIR/gone1"
    if [[ $# -ge 3 ]]; then printf '%b' "$3" > "$STUB_DIR/gone2"; fi
    STUB_LOG="$STUB_DIR/log"
    : > "$STUB_LOG"
    export STUB_DIR STUB_LOG
}

# offer <answer> <tty:0|1> [session] — run the offer; stdout+stderr in $OUT.
offer() {
    local answer="$1" tty="$2" session="${3:-S}" rc=0
    OUT="$(printf '%s\n' "$answer" | AITASKS_TEST_MODE=1 AIT_IDE_FROZEN_ASSUME_TTY="$tty" \
        bash -c 'set -euo pipefail; source "$1"; ide_offer_frozen_agents /proj "$2" "$3"' \
        _ "$LIB" "$session" "$STUB" 2>&1)" || rc=$?
    RC=$rc
    LOG="$(cat "$STUB_LOG")"
}

A="GONE:aaaaaaaa|gone|agent-a|10|2026-09-21T22:40:00Z|ok|ok"
B="GONE:bbbbbbbb|stranded|agent-b|11|2026-09-21T22:41:00Z|ok|ok"
C="GONE:cccccccc|gone|agent-c||2026-09-21T22:42:00Z|no_session|no_task_id"
D="GONE:dddddddd|gone|agent-d|13|2026-09-21T22:43:00Z|no_session|ok"

# --- 1. nothing to offer ------------------------------------------------------
scenario empty "GONE_COUNT:0\n"
offer "" 1
assert_eq "no records: status 0" "0" "$RC"
assert_eq "no records: silent" "" "$OUT"
assert_eq "no records: only the listing ran" "gone --root /proj" "$LOG"

# --- 2. non-interactive: hint only --------------------------------------------
scenario notty "$A\nGONE_COUNT:1\n"
offer "" 0
assert_eq "non-tty: status 0" "0" "$RC"
assert_contains "non-tty: one-line hint names ait frozenagent" "ait frozenagent" "$OUT"
assert_not_contains "non-tty: no reopen" "reopen" "$LOG"
assert_not_contains "non-tty: no restore" "restore" "$LOG"

# --- 3. V / empty → reopen in the selected session ----------------------------
scenario viewers "$A\n$B\n$C\nGONE_COUNT:3\n"
offer "" 1
assert_eq "V default: status 0" "0" "$RC"
assert_contains "the table lists every record" "agent-c" "$OUT"
assert_contains "a stranded record is marked" "(viewer open, untracked)" "$OUT"
assert_contains "a record that can do neither is view only" "(view only)" "$OUT"
assert_contains "the prompt shows the restore count" "Restore 2 of 3" "$OUT"
assert_contains "the prompt shows the re-pick count" "Re-pick 2 of 3" "$OUT"
assert_contains "empty answer reopens in the session" "reopen --root /proj --session S" "$LOG"
assert_not_contains "V never restores" "restore" "$LOG"

scenario viewers_n "$A\nGONE_COUNT:1\n"
offer "v" 1 "-n"
assert_contains "an option-like session is passed verbatim" "reopen --root /proj --session -n" "$LOG"

# --- 4. R → reopen, re-classify, restore the tracked/gone eligible ones -------
# Second `gone`: B is still stranded (its adoption failed); A and D are tracked
# now; C is still gone. C cannot resume, D cannot resume.
scenario restore "$A\n$B\n$C\n$D\nGONE_COUNT:4\n" "$B\n$C\nGONE_COUNT:2\n"
offer "R" 1
assert_eq "R: status 0" "0" "$RC"
assert_contains "R reopens first" "reopen --root /proj --session S" "$LOG"
assert_eq "R re-classifies after reopening" "2" "$(grep -c '^gone ' "$STUB_LOG")"
assert_contains "R restores a tracked eligible record in the session" \
    "restore aaaaaaaa --session S" "$LOG"
assert_not_contains "R skips a record still stranded" "restore bbbbbbbb" "$LOG"
assert_contains "R reports the stranded skip" "agent-b: viewer open but not tracked" "$OUT"
assert_not_contains "R never restores a record that cannot resume" "restore cccccccc" "$LOG"
assert_not_contains "R leaves a no-session record as a viewer" "restore dddddddd" "$LOG"
assert_contains "R summary" "Restored 1, viewers 2, failed 0, skipped 1." "$OUT"
first_reopen="$(grep -n '^reopen' "$STUB_LOG" | head -1 | cut -d: -f1)"
first_restore="$(grep -n '^restore' "$STUB_LOG" | head -1 | cut -d: -f1)"
assert_eq "R: reopen runs before any restore" "1" \
    "$([[ "$first_reopen" -lt "$first_restore" ]] && echo 1 || echo 0)"

# A record still `gone` after reopen (no viewer anywhere) is restorable.
scenario restore_gone "$A\nGONE_COUNT:1\n" "$A\nGONE_COUNT:1\n"
offer "r" 1
assert_contains "R restores a record that is still gone" "restore aaaaaaaa --session S" "$LOG"

# An unreachable re-check skips everything it names.
scenario restore_err "$A\nGONE_COUNT:1\n" "GONE_ERROR:aaaaaaaa|tmux_unreachable\nGONE_COUNT:0\n"
offer "r" 1
assert_not_contains "R skips a record that could not be re-checked" "restore aaaaaaaa" "$LOG"
assert_contains "R reports the unchecked skip" "could not be checked" "$OUT"

# --- 5. P → the same with --repick, by task presence --------------------------
scenario repick "$A\n$C\n$D\nGONE_COUNT:3\n" "GONE_COUNT:0\n"
offer "p" 1
assert_contains "P re-picks a task-bearing record" "restore aaaaaaaa --repick --session S" "$LOG"
assert_contains "P re-picks a no-session record that has a task" \
    "restore dddddddd --repick --session S" "$LOG"
assert_not_contains "P skips a record with no task" "restore cccccccc" "$LOG"

# --- 6. S → nothing -----------------------------------------------------------
scenario skip "$A\nGONE_COUNT:1\n"
offer "s" 1
assert_eq "S: only the listing ran" "gone --root /proj" "$LOG"
assert_contains "S points at ait frozenagent" "ait frozenagent" "$OUT"

# --- 7. a failing listing never blocks startup --------------------------------
scenario fail "$A\n"
touch "$STUB_DIR/gone_fail"
offer "" 1
assert_eq "gone failure: status 0" "0" "$RC"
assert_contains "gone failure: warns" "could not check for frozen agents" "$OUT"

# --- 7b. a reopen that dies before any wire line is reported, not "0 failed" ---
scenario crash "$A\nGONE_COUNT:1\n"
touch "$STUB_DIR/reopen_crash"
offer "" 1
assert_eq "crash: status 0 (startup continues)" "0" "$RC"
assert_contains "crash: the non-zero exit is reported" "failed (exit 3)" "$OUT"
assert_contains "crash: with the last thing the command said" "Traceback" "$OUT"

scenario explained "$A\nGONE_COUNT:1\n"
cat > "$STUB_DIR/../explained_stub.sh" <<'EOS'
#!/usr/bin/env bash
case "$1" in
    gone) printf 'GONE:aaaaaaaa|gone|agent-a|10|t|ok|ok\nGONE_COUNT:1\n' ;;
    reopen) echo "REOPEN_FAILED:aaaaaaaa|launch:rc=1"; exit 1 ;;
esac
EOS
chmod +x "$STUB_DIR/../explained_stub.sh"
OUT="$(printf '\n' | AITASKS_TEST_MODE=1 AIT_IDE_FROZEN_ASSUME_TTY=1 bash -c \
    'set -euo pipefail; source "$1"; ide_offer_frozen_agents /proj S "$2"' \
    _ "$LIB" "$STUB_DIR/../explained_stub.sh" 2>&1)"
assert_not_contains "a failure a REOPEN_FAILED line explains adds no warning" \
    "Warning: bringing" "$OUT"
assert_contains "and the failure line is shown" "REOPEN_FAILED:aaaaaaaa|launch:rc=1" "$OUT"

# --- 8. aitask_ide.sh wiring --------------------------------------------------
help="$(bash "$IDE" --help)"
assert_contains "ait ide --help documents --no-frozen-check" "--no-frozen-check" "$help"
assert_contains "ait ide --help explains the offer" "Frozen agents:" "$help"
calls="$(grep -c '^ *offer_frozen_agents$' "$IDE")"
assert_eq "the offer runs before each of the three attach/select paths" "3" "$calls"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
echo "ALL TESTS PASSED"
