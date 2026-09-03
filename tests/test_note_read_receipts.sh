#!/usr/bin/env bash
# test_note_read_receipts.sh - `ait note read` + the unread query (t1657_3).
#
# Drives the REAL entry points (.aitask-scripts/aitask_note.sh and
# aitask_query_files.sh) against a throwaway fixture repo, never a stub, so the
# in-lock subtraction, the commit transaction and the output contract are all
# exercised as shipped. Modeled on test_note_append.sh.
#
# Coverage map:
#
#   acknowledgement lifecycle        display -> keep unread -> ack -> not shown
#   receipt identity                 --by is always the TARGET (enforced)
#   same-checkout idempotency        retry / partial overlap / query-lock window
#   cross-checkout duplication       accepted: unions, read exactly once
#   malformed receipts               driven through the REAL unread query, where
#                                    no merge ever runs -- the note stays VISIBLE
#   commit-failure transaction       rollback; next query reports it UNREAD
#   rollback vs a concurrent writer  their block survives (a snapshot would not)
#   rollback failure                 surfaced, never swallowed
#   push failure                     durable-but-unsynced, not an error
#   listings are read-only           the batched query writes NO receipt
#
# Run: bash tests/test_note_read_receipts.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

NOTE="$PROJECT_DIR/.aitask-scripts/aitask_note.sh"
QUERY="$PROJECT_DIR/.aitask-scripts/aitask_query_files.sh"

AITASKS_LOCK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/test_noteread_lockbase_XXXXXX")"
export AITASKS_LOCK_DIR

TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_noteread_XXXXXX")"
cleanup() { rm -rf "$TMP" "$AITASKS_LOCK_DIR"; }
trap cleanup EXIT

# --- fixture ---------------------------------------------------------------

CODE="$TMP/code"
mkdir -p "$CODE"
git -C "$CODE" init -q -b main
git -C "$CODE" config user.email t@example.com
git -C "$CODE" config user.name Test
echo one > "$CODE/f.txt"
git -C "$CODE" add -A && git -C "$CODE" commit -qm first

REMOTE="$TMP/remote.git"
git init -q --bare -b main "$REMOTE"
DATA="$TMP/data"
git clone -q "$REMOTE" "$DATA" 2>/dev/null
mkdir -p "$DATA/aitasks"
git -C "$DATA" config user.email t@example.com
git -C "$DATA" config user.name Test

make_task() {
    cat > "$DATA/aitasks/t${1}_x.md" <<EOF
---
status: Ready
---
Body for t${1}.
EOF
}
for id in 800 801 802 803 804 805 806 807 808 809 810; do make_task "$id"; done
git -C "$DATA" add -A && git -C "$DATA" commit -qm "tasks"
git -C "$DATA" push -q origin main 2>/dev/null || true
( cd "$DATA" && "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh" --init ) >/dev/null 2>&1 || true

run_note()  { ( cd "$DATA" && AIT_DIR="$CODE" "$NOTE" "$@" ); }
run_query() { ( cd "$DATA" && "$QUERY" "$@" ); }
task_file() { echo "$DATA/aitasks/t${1}_x.md"; }
task_body() { cat "$(task_file "$1")"; }

# Number of receipt blocks in a task file. The DERIVED state would look correct
# even while the file accumulated duplicates, so idempotency is asserted by
# COUNTING BLOCKS, never by re-checking NO_UNREAD.
receipt_count() { grep -c 'note:read' "$(task_file "$1")" 2>/dev/null || true; }

# Send a note and echo its id.
send_note() {
    run_note "$1" --from "$2" --text "${3:-hi}" 2>/dev/null \
        | sed -n 's/^NOTE_APPENDED:\([^|]*\)|.*/\1/p'
}

echo "=== ait note read: receipts and the unread query (t1657_3) ==="

# --- 1. Acknowledgement lifecycle ------------------------------------------

N1="$(send_note 800 801 "first note")"
assert_contains_re "1a. a note was appended with an id" \
    '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:]+Z\.[0-9a-f]{24}$' "$N1"

out="$(run_query inbox 800)"
assert_contains "1b. first display: the note is UNREAD" "INBOX_UNREAD:800|$N1|t801" "$out"
assert_eq "1c. displaying wrote NO receipt" "0" "$(receipt_count 800)"

# The "keep unread" branch: not acknowledging leaves it shown again.
out="$(run_query inbox 800)"
assert_contains "1d. deferred acknowledgement: shown again" "INBOX_UNREAD:800|$N1" "$out"
assert_eq "1e. still no receipt" "0" "$(receipt_count 800)"

out="$(run_note read 800 --by 800 --ids "$N1" --mode explicit 2>/dev/null)"
assert_contains_re "1f. READ_RECORDED with id, path and count" \
    '^READ_RECORDED:[0-9]{4}-[^|]*\|aitasks/t800_x\.md\|1$' "$out"
assert_contains "1g. receipt records mode=explicit" "mode=explicit" "$(task_body 800)"
assert_contains "1h. receipt is a note:read block" "note:read" "$(task_body 800)"
assert_contains "1i. receipt by= is the target" "by=t800" "$(task_body 800)"
assert_not_contains "1j. receipt carries NO provenance" "dirty=" \
    "$(task_body 800 | grep 'note:read')"

out="$(run_query inbox 800)"
assert_eq "1k. returning session: not shown" "NO_UNREAD:800" "$out"

# --- 2. Receipt identity (--by is always the target) ------------------------

N2="$(send_note 801 802 "for 801")"
before="$(task_body 801)"
out="$(run_note read 801 --by 802 --ids "$N2" 2>/dev/null)"
assert_eq "2a. --by naming another task is refused" \
    "READ_ERROR:by-must-be-target:802" "$out"
assert_eq "2b. ... and the file is UNCHANGED" "$before" "$(task_body 801)"
assert_eq "2c. ... so no receipt exists" "0" "$(receipt_count 801)"

out="$(run_note read 801 --ids "$N2" 2>/dev/null)"
assert_eq "2d. --by omitted is refused" "READ_ERROR:missing-by" "$out"
assert_eq "2e. ... and still no receipt" "0" "$(receipt_count 801)"

# The t-prefixed and bare forms are the same identity.
out="$(run_note read 801 --by t801 --ids "$N2" 2>/dev/null)"
assert_contains "2f. t-prefixed --by is accepted" "READ_RECORDED:" "$out"

out="$(run_note read 999999 --by 999999 --ids "$N2" 2>/dev/null)"
assert_eq "2g. missing target" "READ_TARGET_MISSING:999999" "$out"

# --- 3. Same-checkout idempotency (the in-lock subtraction) -----------------

N3="$(send_note 802 803 "for 802")"
run_note read 802 --by 802 --ids "$N3" >/dev/null 2>&1
assert_eq "3a. one receipt after the first ack" "1" "$(receipt_count 802)"

out="$(run_note read 802 --by 802 --ids "$N3" 2>/dev/null)"
assert_eq "3b. plain retry returns READ_NOOP" "READ_NOOP:802" "$out"
assert_eq "3c. ... and appends NO second receipt" "1" "$(receipt_count 802)"

# Partial overlap: {A} acknowledged, now ask for {A,B} -> only B is covered.
NA="$(send_note 803 804 "A")"
NB="$(send_note 803 805 "B")"
run_note read 803 --by 803 --ids "$NA" >/dev/null 2>&1
out="$(run_note read 803 --by 803 --ids "$NA,$NB" 2>/dev/null)"
assert_contains "3d. partial overlap: n-ids counts only the remainder" \
    "|1" "$out"
assert_eq "3e. exactly one new receipt" "2" "$(receipt_count 803)"
newest="$(grep 'note:read' "$(task_file 803)" | tail -n1)"
assert_contains "3f. the new receipt covers B" "$NB" "$newest"
assert_not_contains "3g. ... and does NOT re-assert A" "$NA" "$newest"
assert_eq "3h. both notes now read" "NO_UNREAD:803" "$(run_query inbox 803)"

# The query->lock window: another process acknowledges between the caller's
# unread query and its own acknowledging call.
NW="$(send_note 804 805 "window")"
run_query inbox 804 >/dev/null            # the caller's query
run_note read 804 --by 804 --ids "$NW" >/dev/null 2>&1   # the OTHER process
out="$(run_note read 804 --by 804 --ids "$NW" 2>/dev/null)"
assert_eq "3i. query->lock window collapses to READ_NOOP" "READ_NOOP:804" "$out"
assert_eq "3j. ... with no duplicate receipt" "1" "$(receipt_count 804)"

# An id naming no note in this file is a caller bug, refused before any write.
before="$(task_body 805)"
out="$(run_note read 805 --by 805 --ids "2026-01-01T00:00:00Z.$(printf 'f%.0s' {1..24})" 2>/dev/null)"
assert_contains "3k. unknown note id is refused" "READ_ERROR:unknown-note-id:" "$out"
assert_eq "3l. ... and the file is byte-identical" "$before" "$(task_body 805)"

# --- 4. Malformed receipts, through the REAL unread query -------------------
#
# The point: these must be rejected on a purely local read path where no merge
# ever runs. A malformed receipt acknowledges NOTHING, so the note stays visible.

NM="$(send_note 806 807 "must stay visible")"
append_raw() { printf '\n%s\n' "$2" >> "$(task_file "$1")"; }
rid() { printf '2026-09-04T00:00:00Z.%s' "$(printf "$1%.0s" {1..24})"; }

check_malformed() {   # <label> <marker-line>
    local label="$1" block="$2"
    cp "$(task_file 806)" "$TMP/806.bak"
    append_raw 806 "$block"
    local out; out="$(run_query inbox 806)"
    assert_contains "$label: the note stays VISIBLE" "INBOX_UNREAD:806|$NM" "$out"
    assert_contains "$label: the bad block is REPORTED" "INBOX_MALFORMED:806|" "$out"
    cp "$TMP/806.bak" "$(task_file 806)"
}

check_malformed "4a. receipt carrying provenance" \
    "> **👁 note:read** id=$(rid 5) by=t806 at=2026-09-04T00:00:00Z mode=explicit ids=$NM base=$(printf 'a%.0s' {1..40})"
check_malformed "4b. out-of-vocabulary mode" \
    "> **👁 note:read** id=$(rid 6) by=t806 at=2026-09-04T00:00:00Z mode=sideways ids=$NM"
check_malformed "4c. unknown key" \
    "> **👁 note:read** id=$(rid 7) by=t806 at=2026-09-04T00:00:00Z mode=explicit ids=$NM extra=1"
check_malformed "4d. non-t<N> by=" \
    "> **👁 note:read** id=$(rid 8) by=someone at=2026-09-04T00:00:00Z mode=explicit ids=$NM"
check_malformed "4e. malformed ids= member" \
    "> **👁 note:read** id=$(rid 9) by=t806 at=2026-09-04T00:00:00Z mode=explicit ids=not-a-note-id"

# An invalid receipt must NOT suppress a real acknowledgement of the same id.
append_raw 806 "> **👁 note:read** id=$(rid 5) by=t806 at=2026-09-04T00:00:00Z mode=sideways ids=$NM"
out="$(run_note read 806 --by 806 --ids "$NM" 2>/dev/null)"
assert_contains "4f. an invalid receipt covers nothing: the ack proceeds" \
    "READ_RECORDED:" "$out"
assert_eq "4g. ... and the note is now genuinely read" "NO_UNREAD:806" \
    "$(run_query inbox 806 | grep -v INBOX_MALFORMED)"

# A malformed NOTE is reported, and valid siblings still come back.
NV="$(send_note 807 808 "valid sibling")"
append_raw 807 "> **✉ note:t809** id=$(rid 1) from=t809 at=2026-09-04T00:00:00Z base=nope dirty=no host=pc"
out="$(run_query inbox 807)"
assert_contains "4h. malformed note is reported" "INBOX_MALFORMED:807|" "$out"
assert_contains "4i. ... and the valid sibling still returns" "INBOX_UNREAD:807|$NV" "$out"

# --- 5. Commit-failure transaction (the rollback) ---------------------------

NC="$(send_note 808 809 "commit failure")"
before="$(task_body 808)"
out="$(AIT_NOTE_READ_FAIL_COMMIT=1 run_note read 808 --by 808 --ids "$NC" 2>/dev/null)"
assert_eq "5a. commit failure reports READ_ERROR, not READ_RECORDED*" \
    "READ_ERROR:git-commit-failed" "$out"
assert_eq "5b. the receipt was rolled back (file byte-identical)" \
    "$before" "$(task_body 808)"
assert_eq "5c. receipt count restored" "0" "$(receipt_count 808)"
# THE assertion that actually pins the fail-safe rule. A rollback bug leaves the
# exit status looking right while the note is silently hidden.
assert_contains "5d. the next local query reports the note UNREAD" \
    "INBOX_UNREAD:808|$NC" "$(run_query inbox 808)"
assert_eq "5e. nothing left staged" "" \
    "$(git -C "$DATA" status --porcelain -- aitasks/t808_x.md)"
# A subsequent acknowledgement must APPEND, not short-circuit to READ_NOOP.
out="$(run_note read 808 --by 808 --ids "$NC" 2>/dev/null)"
assert_contains "5f. a later ack appends (not READ_NOOP)" "READ_RECORDED:" "$out"

# --- 6. Rollback must not damage a concurrent writer ------------------------
#
# The case a snapshot restore would fail: another writer appends to the same
# file while our receipt is in flight.

NX="$(send_note 809 810 "concurrent")"
# The concurrent writer's block, landing after ours would.
CONC="$(send_note 809 801 "from a second writer")"
out="$(AIT_NOTE_READ_FAIL_COMMIT=1 run_note read 809 --by 809 --ids "$NX" 2>/dev/null)"
assert_eq "6a. rollback still reports READ_ERROR" "READ_ERROR:git-commit-failed" "$out"
assert_eq "6b. our receipt is gone" "0" "$(receipt_count 809)"
assert_contains "6c. the other writer's note SURVIVED" "$CONC" "$(task_body 809)"
assert_contains "6d. ... and is still readable as a note" "INBOX_UNREAD:809|$CONC" \
    "$(run_query inbox 809)"

# --- 7. Rollback failure is surfaced, never swallowed -----------------------

out="$(AIT_NOTE_READ_FAIL_COMMIT=1 AIT_NOTE_READ_FAIL_ROLLBACK=1 \
       run_note read 809 --by 809 --ids "$NX" 2>/dev/null)"
assert_contains_re "7a. rollback failure is its own terminal state" \
    '^READ_ERROR:rollback-failed:[0-9]{4}-' "$out"
assert_eq "7b. the receipt is still on disk (a human must settle it)" \
    "1" "$(receipt_count 809)"
err="$(AIT_NOTE_READ_FAIL_COMMIT=1 AIT_NOTE_READ_FAIL_ROLLBACK=1 \
       run_note read 809 --by 809 --ids "$CONC" 2>&1 >/dev/null)"
assert_contains "7c. stderr carries a recovery hint" "rollback failed" "$err"

# --- 8. Push failure is durable-but-unsynced, not an error ------------------

NP="$(send_note 810 801 "push failure")"
out="$(AIT_NOTE_READ_FAIL_PUSH=1 run_note read 810 --by 810 --ids "$NP" 2>/dev/null)"
assert_contains_re "8a. READ_RECORDED_UNPUSHED, not an error" \
    '^READ_RECORDED_UNPUSHED:[0-9]{4}-[^|]*\|aitasks/t810_x\.md\|1$' "$out"
assert_eq "8b. the receipt IS committed locally" "" \
    "$(git -C "$DATA" status --porcelain -- aitasks/t810_x.md)"
assert_eq "8c. locally the note reads as acknowledged" "NO_UNREAD:810" \
    "$(run_query inbox 810)"

# --- 9. Listings are READ-ONLY ---------------------------------------------
#
# The invariant that stops an agent which merely SAW a task in a candidate menu
# from hiding that task's notes from the agent who later picks it.

NL1="$(send_note 800 801 "listing candidate 1")"
NL2="$(send_note 801 802 "listing candidate 2")"
sum_before="$(cat "$(task_file 800)" "$(task_file 801)" "$(task_file 802)" | md5sum)"
run_query inbox 800 801 802 803 804 >/dev/null
sum_after="$(cat "$(task_file 800)" "$(task_file 801)" "$(task_file 802)" | md5sum)"
assert_eq "9a. a batched listing writes NOTHING" "$sum_before" "$sum_after"
assert_contains "9b. ... and still reports the unread notes" "INBOX_UNREAD:800|$NL1" \
    "$(run_query inbox 800 801)"
assert_contains "9c. ... for each task, attributed by id" "INBOX_UNREAD:801|$NL2" \
    "$(run_query inbox 800 801)"
# Batched output must not cross-attribute.
out="$(run_query inbox 800 802)"
assert_not_contains "9d. no cross-attribution between batched tasks" \
    "INBOX_UNREAD:802|$NL1" "$out"
assert_contains "9e. a task with no section reports NO_INBOX" "NO_INBOX:" \
    "$(run_query inbox 805)"
assert_contains "9f. an unknown task is its own state, not 'no notes'" \
    "INBOX_ERROR:999999|task-not-found" "$(run_query inbox 999999)"

# --- 10. Cross-checkout duplication is ACCEPTED -----------------------------
#
# Two PCs acknowledging the same note produce overlapping receipts; no local
# lock can prevent that, and set-union makes it harmless. Deliberately NOT
# folded into the idempotency group above -- the local subtraction is not
# claimed to cover it.

ND="$(send_note 802 803 "cross-checkout")"
run_note read 802 --by 802 --ids "$ND" >/dev/null 2>&1
# A second, independently-authored receipt covering the same id, as if from
# another checkout that never saw ours.
append_raw 802 "> **👁 note:read** id=$(rid 3) by=t802 at=2026-09-04T01:00:00Z mode=auto ids=$ND"
out="$(run_query inbox 802)"
assert_eq "10a. overlapping receipts union: read exactly once" "NO_UNREAD:802" "$out"
assert_not_contains "10b. neither is reported malformed" "INBOX_MALFORMED" "$out"

echo
echo "Results: $PASS passed, $FAIL failed (of $TOTAL)"
[[ "$FAIL" -eq 0 ]]
