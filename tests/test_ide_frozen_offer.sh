#!/usr/bin/env bash
# test_ide_frozen_offer.sh - `ait ide`'s frozen-agent offer (t1847), over every
# project's records (t2039).
#
# Drives `ide_offer_frozen_agents` from lib/ide_frozen_offer.sh against a STUB
# `aitask_frozen.sh` that logs its argv and answers `gone --all-roots` from canned
# files (a first and a second answer, because R/P re-classify after reopening).
# No tmux, no store. The interactive branch is reached through the
# test-mode-only AIT_IDE_FROZEN_ASSUME_TTY seam; the answers arrive on stdin, one
# line per project that is asked.
#
# The stub's `reopen` answers per root: `REOPENED` into the `--session` it was
# given, or into `own_<basename>` when none was given (another project resolving
# its own session), or `REOPEN_FAILED:…|no_session_for_root:…` for a root listed
# in `reopen_fail`. `companions` answers from `companions_out` (default
# `COMPANION_COUNT:0`), or fails when `companions_fail` exists.
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
        if [[ -f "$STUB_DIR/gone_fail_from" && "$n" -ge "$(cat "$STUB_DIR/gone_fail_from")" ]]; then
            exit 1
        fi
        f="$STUB_DIR/gone$n"
        [[ -f "$f" ]] || f="$STUB_DIR/gone1"
        cat "$f"
        ;;
    reopen)
        if [[ -f "$STUB_DIR/reopen_crash" ]]; then
            echo "Traceback (most recent call last): boom" >&2
            exit 3
        fi
        root="$3"; session="own_${root##*/}"
        [[ "${4:-}" == --session ]] && session="$5"
        if grep -qxF -- "$root" "$STUB_DIR/reopen_fail" 2>/dev/null; then
            echo "REOPEN_FAILED:ffffffff|no_session_for_root:$root|bootstrap:session_name_taken:x"
            echo "REOPEN_ALL:0/1"
            exit 1
        fi
        echo "REOPENED:aaaaaaaa|fresh|$session:w|%1"; echo "REOPEN_ALL:1/1" ;;
    restore) echo "RESTORED:$2|hook" ;;
    companions)
        if [[ -f "$STUB_DIR/companions_fail" ]]; then
            echo "COMPANION_ERROR:*|tmux unreachable"; echo "COMPANION_COUNT:0"; exit 1
        fi
        if [[ -f "$STUB_DIR/companions_out" ]]; then cat "$STUB_DIR/companions_out"
        else echo "COMPANION_COUNT:0"; fi
        ;;
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

# offer <answers> <tty:0|1> [session] — run the offer; stdout+stderr in $OUT.
# <answers> is printf %b text: one line per project asked, e.g. 'V\nR\n'.
offer() {
    local answers="$1" tty="$2" session="${3:-S}" rc=0
    OUT="$(printf '%b' "$answers" | AITASKS_TEST_MODE=1 AIT_IDE_FROZEN_ASSUME_TTY="$tty" \
        bash -c 'set -euo pipefail; source "$1"; ide_offer_frozen_agents /proj "$2" "$3"' \
        _ "$LIB" "$session" "$STUB" 2>&1)" || rc=$?
    RC=$rc
    LOG="$(cat "$STUB_LOG")"
}

# logged <line> — 1 when the stub log holds exactly that argv line.
logged() { grep -qxF -- "$1" "$STUB_LOG" && echo 1 || echo 0; }
# line_of <regex> — first stub-log line number matching, or 0.
line_of() { grep -nE -- "$1" "$STUB_LOG" | head -1 | cut -d: -f1 || true; }

GR="GONE_ROOT:ok|proj|/proj"
A="GONE:aaaaaaaa|gone|agent-a|10|2026-09-21T22:40:00Z|ok|ok|/proj"
B="GONE:bbbbbbbb|stranded|agent-b|11|2026-09-21T22:41:00Z|ok|ok|/proj"
C="GONE:cccccccc|gone|agent-c||2026-09-21T22:42:00Z|no_session|no_task_id|/proj"
D="GONE:dddddddd|gone|agent-d|13|2026-09-21T22:43:00Z|no_session|ok|/proj"
# Another registered project, and list-only roots.
GR_O="GONE_ROOT:ok|other|/other"
E="GONE:eeeeeeee|gone|agent-e|20|2026-09-21T22:44:00Z|ok|ok|/other"
GR_O2="GONE_ROOT:ok|other2|/other2"
F="GONE:ffffffff|gone|agent-f|21|2026-09-21T22:45:00Z|ok|ok|/other2"
GR_M="GONE_ROOT:missing|gone_proj|/gone_proj"
M="GONE:11111111|gone|agent-m|30|2026-09-20T10:00:00Z|ok|ok|/gone_proj"
GR_U="GONE_ROOT:unregistered|unreg|/unreg"
U="GONE:22222222|gone|agent-u|31|2026-09-20T10:01:00Z|ok|ok|/unreg"
GR_W="GONE_ROOT:unverified|unver|/unver"
W="GONE:33333333|gone|agent-w|32|2026-09-20T10:02:00Z|ok|ok|/unver"

# --- 1. nothing to offer ------------------------------------------------------
scenario empty "GONE_COUNT:0\n"
offer "" 1
assert_eq "no records: status 0" "0" "$RC"
assert_eq "no records: silent" "" "$OUT"
assert_eq "no records: the listing, then the companion top-up" \
    "$(printf 'gone --all-roots\ncompanions --all-roots')" "$LOG"

# --- 2. non-interactive: hint only --------------------------------------------
scenario notty "$GR\n$A\nGONE_COUNT:1\n"
offer "" 0
assert_eq "non-tty: status 0" "0" "$RC"
assert_contains "non-tty: one-line hint names ait frozenagent" "ait frozenagent" "$OUT"
assert_contains "non-tty: this project's count" \
    "Note: 1 frozen agent(s) of this project have no open viewer — run" "$OUT"
assert_not_contains "non-tty: no reopen" "reopen" "$LOG"
assert_not_contains "non-tty: no restore" "restore" "$LOG"
assert_contains "non-tty: the companion top-up still runs" "companions --all-roots" "$LOG"

scenario notty_both "$GR\n$A\n$GR_O\n$E\nGONE_COUNT:2\n"
offer "" 0
assert_contains "non-tty: other projects are counted too" \
    "1 frozen agent(s) of this project have no open viewer (1 more in 1 other project(s))" "$OUT"

scenario notty_other "$GR_O\n$E\nGONE_COUNT:1\n"
offer "" 0
assert_contains "non-tty: only other projects have records" \
    "Note: 1 frozen agent(s) in 1 other project(s) have no open viewer" "$OUT"

# --- 3. V / empty → reopen in the selected session ----------------------------
scenario viewers "$GR\n$A\n$B\n$C\nGONE_COUNT:3\n"
offer "" 1
assert_eq "V default: status 0" "0" "$RC"
assert_contains "the table lists every record" "agent-c" "$OUT"
assert_contains "a stranded record is marked" "(viewer open, untracked)" "$OUT"
assert_contains "a record that can do neither is view only" "(view only)" "$OUT"
assert_contains "this project's group is labelled" "proj (this project) — 3" "$OUT"
assert_contains "the prompt shows the restore count" "Restore 2 of 3" "$OUT"
assert_contains "the prompt shows the re-pick count" "Re-pick 2 of 3" "$OUT"
assert_eq "empty answer reopens in the session" "1" "$(logged "reopen --root /proj --session S")"
assert_not_contains "V never restores" "restore" "$LOG"
assert_not_contains "a lone project gets no other-sessions line" "Other projects'" "$OUT"

scenario viewers_n "$GR\n$A\nGONE_COUNT:1\n"
offer "v\n" 1 "-n"
assert_eq "an option-like session is passed verbatim" "1" \
    "$(logged "reopen --root /proj --session -n")"

# --- 4. R → reopen, re-classify, restore the tracked/gone eligible ones -------
# Second `gone`: B is still stranded (its adoption failed); A and D are tracked
# now; C is still gone. C cannot resume, D cannot resume.
scenario restore "$GR\n$A\n$B\n$C\n$D\nGONE_COUNT:4\n" "$GR\n$B\n$C\nGONE_COUNT:2\n"
offer "R\n" 1
assert_eq "R: status 0" "0" "$RC"
assert_eq "R reopens first" "1" "$(logged "reopen --root /proj --session S")"
assert_eq "R re-classifies after reopening" "2" "$(grep -c '^gone ' "$STUB_LOG")"
assert_eq "R restores a tracked eligible record in the session" "1" \
    "$(logged "restore aaaaaaaa --session S")"
assert_not_contains "R skips a record still stranded" "restore bbbbbbbb" "$LOG"
assert_contains "R reports the stranded skip" "agent-b: viewer open but not tracked" "$OUT"
assert_not_contains "R never restores a record that cannot resume" "restore cccccccc" "$LOG"
assert_not_contains "R leaves a no-session record as a viewer" "restore dddddddd" "$LOG"
assert_contains "R summary" "Restored 1, viewers 2, failed 0, skipped 1." "$OUT"
first_reopen="$(line_of '^reopen')"
first_restore="$(line_of '^restore')"
assert_eq "R: reopen runs before any restore" "1" \
    "$([[ "$first_reopen" -lt "$first_restore" ]] && echo 1 || echo 0)"

# A record still `gone` after reopen (no viewer anywhere) is restorable.
scenario restore_gone "$GR\n$A\nGONE_COUNT:1\n" "$GR\n$A\nGONE_COUNT:1\n"
offer "r\n" 1
assert_eq "R restores a record that is still gone" "1" "$(logged "restore aaaaaaaa --session S")"

# An unreachable re-check skips everything it names.
scenario restore_err "$GR\n$A\nGONE_COUNT:1\n" \
    "$GR\nGONE_ERROR:aaaaaaaa|tmux_unreachable|/proj\nGONE_COUNT:0\n"
offer "r\n" 1
assert_not_contains "R skips a record that could not be re-checked" "restore aaaaaaaa" "$LOG"
assert_contains "R reports the unchecked skip" "could not be checked" "$OUT"

# A re-check that fails outright restores nothing, and says so.
scenario restore_refail "$GR\n$A\nGONE_COUNT:1\n"
echo 2 > "$STUB_DIR/gone_fail_from"
offer "r\n" 1
assert_eq "refail: status 0" "0" "$RC"
assert_eq "refail: the viewers were still reopened" "1" "$(logged "reopen --root /proj --session S")"
assert_contains "refail: warns" "could not re-check the frozen agents; nothing restored" "$OUT"
assert_not_contains "refail: nothing is restored" "restore" "$LOG"

# --- 5. P → the same with --repick, by task presence --------------------------
scenario repick "$GR\n$A\n$C\n$D\nGONE_COUNT:3\n" "GONE_COUNT:0\n"
offer "p\n" 1
assert_eq "P re-picks a task-bearing record" "1" "$(logged "restore aaaaaaaa --repick --session S")"
assert_eq "P re-picks a no-session record that has a task" "1" \
    "$(logged "restore dddddddd --repick --session S")"
assert_not_contains "P skips a record with no task" "restore cccccccc" "$LOG"

# --- 6. S → nothing -----------------------------------------------------------
scenario skip "$GR\n$A\nGONE_COUNT:1\n"
offer "s\n" 1
assert_eq "S: only the listing and the top-up ran" \
    "$(printf 'gone --all-roots\ncompanions --all-roots')" "$LOG"
assert_contains "S points at ait frozenagent" "ait frozenagent" "$OUT"

# --- 7. a failing listing never blocks startup --------------------------------
scenario fail "$GR\n$A\n"
touch "$STUB_DIR/gone_fail"
offer "" 1
assert_eq "gone failure: status 0" "0" "$RC"
assert_contains "gone failure: warns" "could not check for frozen agents" "$OUT"

# --- 7b. a reopen that dies before any wire line is reported, not "0 failed" ---
scenario crash "$GR\n$A\nGONE_COUNT:1\n"
touch "$STUB_DIR/reopen_crash"
offer "" 1
assert_eq "crash: status 0 (startup continues)" "0" "$RC"
assert_contains "crash: the non-zero exit is reported" "failed (exit 3)" "$OUT"
assert_contains "crash: with the last thing the command said" "Traceback" "$OUT"

scenario explained "$GR\n$A\nGONE_COUNT:1\n"
cat > "$STUB_DIR/../explained_stub.sh" <<'EOS'
#!/usr/bin/env bash
case "$1" in
    gone) printf 'GONE_ROOT:ok|proj|/proj\nGONE:aaaaaaaa|gone|agent-a|10|t|ok|ok|/proj\nGONE_COUNT:1\n' ;;
    reopen) echo "REOPEN_FAILED:aaaaaaaa|launch:rc=1"; exit 1 ;;
    companions) echo "COMPANION_COUNT:0" ;;
esac
EOS
chmod +x "$STUB_DIR/../explained_stub.sh"
OUT="$(printf '\n' | AITASKS_TEST_MODE=1 AIT_IDE_FROZEN_ASSUME_TTY=1 bash -c \
    'set -euo pipefail; source "$1"; ide_offer_frozen_agents /proj S "$2"' \
    _ "$LIB" "$STUB_DIR/../explained_stub.sh" 2>&1)"
assert_not_contains "a failure a REOPEN_FAILED line explains adds no warning" \
    "Warning: bringing" "$OUT"
assert_contains "and the failure line is shown" "REOPEN_FAILED:aaaaaaaa|launch:rc=1" "$OUT"

# --- 8. every project: groups, own sessions, per-project answers (t2039) -------
# This project answers V, the other registered project answers R.
scenario two "$GR\n$A\n$GR_O\n$E\nGONE_COUNT:2\n" "$GR_O\nGONE_COUNT:0\n"
offer "V\nR\n" 1
assert_eq "two projects: status 0" "0" "$RC"
assert_eq "this project reopens into the session being opened" "1" \
    "$(logged "reopen --root /proj --session S")"
assert_eq "the other project reopens with NO --session (its own session)" "1" \
    "$(logged "reopen --root /other")"
assert_eq "the other project's record restores with NO --session" "1" \
    "$(logged "restore eeeeeeee")"
assert_not_contains "this project's V restores nothing" "restore aaaaaaaa" "$LOG"
assert_contains "the other group says where it lands" "other — 1 · lands in its own tmux session" "$OUT"
p_line="$(grep -n 'proj (this project) — ' <<<"$OUT" | head -1 | cut -d: -f1)"
o_line="$(grep -n '^  other — ' <<<"$OUT" | head -1 | cut -d: -f1)"
assert_eq "this project is listed first" "1" \
    "$([[ -n "$p_line" && -n "$o_line" && "$p_line" -lt "$o_line" ]] && echo 1 || echo 0)"
assert_eq "one question per project" "2" "$(grep -o 'Choice for ' <<<"$OUT" | wc -l | tr -d ' ')"
assert_contains "the user is told where the other project's agents are" \
    "Other projects' agents are in their own tmux sessions: other (own_other)" "$OUT"
assert_eq "R re-classifies once, after every reopen" "2" "$(grep -c '^gone ' "$STUB_LOG")"
last_reopen="$(grep -n '^reopen' "$STUB_LOG" | tail -1 | cut -d: -f1)"
second_gone="$(grep -n '^gone ' "$STUB_LOG" | sed -n 2p | cut -d: -f1)"
assert_eq "the re-check follows both reopens" "1" \
    "$([[ "$last_reopen" -lt "$second_gone" ]] && echo 1 || echo 0)"

# Records of roots that may not be acted on are listed, never asked, never touched.
scenario listonly "$GR\n$A\n$GR_M\n$M\n$GR_U\n$U\n$GR_W\n$W\nGONE_COUNT:4\n"
offer "V\n" 1
assert_eq "list-only: only this project is asked" "1" \
    "$(grep -o 'Choice for ' <<<"$OUT" | wc -l | tr -d ' ')"
assert_contains "a missing project says so" \
    "gone_proj — 1 · project directory gone — not touched; drop them with 'ait frozenagent'" "$OUT"
assert_contains "an unregistered project says so" \
    "unreg — 1 · not a registered project — not touched; run 'ait ide' there, or 'ait projects add /unreg'" "$OUT"
assert_contains "an unverified registry says so" \
    "unver — 1 · project registry unreadable — not touched" "$OUT"
assert_contains "list-only rows are still shown" "agent-m" "$OUT"
for r in /gone_proj /unreg /unver; do
    assert_not_contains "list-only: $r is never reopened" "reopen --root $r" "$LOG"
done
assert_not_contains "list-only: nothing is restored" "restore" "$LOG"

# One project's refused bootstrap is reported under it and never stops the next.
scenario onefails "$GR\n$A\n$GR_O\n$E\n$GR_O2\n$F\nGONE_COUNT:3\n"
printf '/other\n' > "$STUB_DIR/reopen_fail"
offer "V\nV\nV\n" 1
assert_eq "one fails: status 0" "0" "$RC"
assert_contains "the refusal is shown" "REOPEN_FAILED:ffffffff|no_session_for_root:/other" "$OUT"
assert_eq "the next project is still reopened" "1" "$(logged "reopen --root /other2")"
assert_contains "and named as reachable" "other2 (own_other2)" "$OUT"
assert_not_contains "the failed project is not named as reachable" "other (own_other)" "$OUT"

# Only another project has records: still offered.
scenario onlyother "$GR_O\n$E\nGONE_COUNT:1\n"
offer "V\n" 1
assert_contains "only-other: offered" "Choice for other [V/r/p/s]" "$OUT"
assert_not_contains "only-other: no 'this project' group" "(this project)" "$OUT"
assert_eq "only-other: reopened into its own session" "1" "$(logged "reopen --root /other")"

# A root containing `|` survives the wire: it is the last field.
scenario pipe "GONE_ROOT:ok|we|/we|ird\nGONE:44444444|gone|agent-p|40|t|ok|ok|/we|ird\nGONE_COUNT:1\n"
offer "V\n" 1
assert_eq "a root with a pipe is reopened verbatim" "1" "$(logged "reopen --root /we|ird")"

# ...including a TRAILING pipe, which `read` would silently drop from its last
# variable — turning the root into a different directory.
scenario pipe_tail "GONE_ROOT:ok|tail|/tail|\nGONE:55555555|gone|agent-t|41|t|ok|ok|/tail|\nGONE_COUNT:1\n"
offer "V\n" 1
assert_eq "a root ending in a pipe is reopened verbatim" "1" "$(logged "reopen --root /tail|")"
assert_eq "...and never as the truncated directory" "0" "$(logged "reopen --root /tail")"

# The CURRENT project ending in a pipe: still recognised as this project, so it
# keeps its session pin.
scenario pipe_cur "GONE_ROOT:ok|cur|/cur|\nGONE:66666666|gone|agent-c|42|t|ok|ok|/cur|\nGONE_COUNT:1\n"
OUT="$(printf 'V\n' | AITASKS_TEST_MODE=1 AIT_IDE_FROZEN_ASSUME_TTY=1 bash -c \
    'set -euo pipefail; source "$1"; ide_offer_frozen_agents "/cur|" S "$2"' \
    _ "$LIB" "$STUB" 2>&1)"
assert_contains "a pipe-ending current project is this project" "cur (this project) — 1" "$OUT"
assert_eq "...and keeps its session pin" "1" "$(logged "reopen --root /cur| --session S")"

# A line with too few fields is skipped, never read with a field as the root.
scenario short "$GR\n$A\nGONE:77777777|gone|agent-s\nGONE_COUNT:2\n"
offer "V\n" 1
assert_not_contains "a short GONE line is not listed" "agent-s" "$OUT"
assert_eq "...and only the real root is reopened" "1" \
    "$(grep -c '^reopen' "$STUB_LOG")"

# A project whose directory cannot be looked up is listed, never touched.
scenario inaccessible "$GR\n$A\nGONE_ROOT:inaccessible|locked|/locked\nGONE:88888888|gone|agent-l|43|t|ok|ok|/locked\nGONE_COUNT:2\n"
offer "V\n" 1
assert_contains "an inaccessible project says so" \
    "locked — 1 · project directory unreadable — not touched" "$OUT"
assert_not_contains "...and is never reopened" "reopen --root /locked" "$LOG"

# --- 9. the companion top-up ---------------------------------------------------
scenario comp "$GR\n$A\nGONE_COUNT:1\n"
printf 'COMPANION_SPAWNED:aaaaaaaa|S:agent-a|%%5\nCOMPANION_SPAWNED:bbbbbbbb|S:agent-b|%%6\nCOMPANION_COUNT:2\n' \
    > "$STUB_DIR/companions_out"
offer "s\n" 1
assert_contains "spawned companions are reported" \
    "Companions: 2 viewer window(s) got their minimonitor back." "$OUT"
assert_eq "the top-up runs last" "companions --all-roots" "$(tail -1 "$STUB_LOG")"

scenario comp_empty "GONE_COUNT:0\n"
printf 'COMPANION_SPAWNED:aaaaaaaa|S:agent-a|%%5\nCOMPANION_COUNT:1\n' > "$STUB_DIR/companions_out"
offer "" 1
assert_contains "the top-up runs with nothing to offer too" "Companions: 1 viewer window(s)" "$OUT"

scenario comp_fail "GONE_COUNT:0\n"
touch "$STUB_DIR/companions_fail"
offer "" 1
assert_eq "a failed top-up never fails startup" "0" "$RC"
assert_contains "a failed top-up warns with its reason" \
    "could not give every frozen viewer its minimonitor (exit 1): COMPANION_ERROR:*|tmux unreachable" "$OUT"

# --- 10. aitask_ide.sh wiring --------------------------------------------------
help="$(bash "$IDE" --help)"
assert_contains "ait ide --help documents --no-frozen-check" "--no-frozen-check" "$help"
assert_contains "ait ide --help explains the offer" "Frozen agents:" "$help"
assert_contains "ait ide --help says every project is offered" "for
every project, grouped by project" "$help"
calls="$(grep -c '^ *offer_frozen_agents$' "$IDE")"
assert_eq "the offer runs before each of the three attach/select paths" "3" "$calls"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
echo "ALL TESTS PASSED"
