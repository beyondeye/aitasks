#!/usr/bin/env bash
# test_followup_backfill_recovery.sh - the manifest/journal recovery contract
# of aitask_followup_backfill.sh (t1468_6).
#
# The backfill makes ~170 non-atomic aitask_update.sh writes. Everything here
# tests what happens when that loop does NOT run to completion, because the
# failure mode is silent: a retry skips already-marked tasks and would report
# fewer writes without revealing that only part of the reviewed corpus landed.
#
# Faults are injected through DOCUMENTED SEAMS -- the journal file, the corpus,
# the run state -- never by patching the script under test. In particular the
# "write succeeded but the journal append was lost" window is injected by
# deleting the journal line after the fact, which is precisely the on-disk
# state a crash in that window leaves behind (lib/atomic_write.sh does no
# fsync, so any append can be lost).
#
# NOTE ON COMMITTING INJECTED DRIFT. There are two independent guards against a
# concurrently-edited task file, and which one fires depends on whether the
# edit is committed:
#   * UNcommitted -> the path is git-dirty, so check_baseline sees it.
#   * committed   -> the tree is clean, so the guard is the hash comparison
#                    (global preflight on a fresh apply, reconcile_row on a
#                    resume).
# Tests that mean to exercise the hash guards therefore COMMIT the injected
# edit; tests that mean to exercise the baseline guard leave it uncommitted.
# Getting this wrong silently tests the same guard twice.
#
# Run: bash tests/test_followup_backfill_recovery.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

cleanup() {
    local d
    for d in "${CLEANUP_DIRS[@]:-}"; do
        [[ -n "$d" && -d "$d" ]] && rm -rf "$d"
    done
}
trap cleanup EXIT

BACKFILL="$PROJECT_DIR/.aitask-scripts/aitask_followup_backfill.sh"

RISK_AFTER='Risk-mitigation ("after") follow-up for t900, created at Step 8d.'
CARRY='Carry-over of deferred manual-verification items from t901. Re-pick this task to continue the remaining checklist.'

TMP=""
BF=""

seed_task() { # seed_task <id> <issue_type> <body>
    local id="$1" itype="$2" body="$3"
    {
        echo "---"
        echo "priority: medium"
        echo "effort: medium"
        echo "depends: []"
        echo "issue_type: $itype"
        echo "status: Ready"
        echo "labels: []"
        echo "created_at: 2026-01-01 00:00"
        echo "updated_at: 2026-01-01 00:00"
        echo "---"
        echo
        echo "## Origin"
        echo
        echo "$body"
    } > "$TMP/aitasks/t${id}_fixture.md"
}

git_commit_all() {
    ( cd "$TMP" && git add -A && git -c user.email=t@t -c user.name=t commit -qm "$1" )
}

new_fixture() {
    TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_fk_backfill_XXXXXX")"
    CLEANUP_DIRS+=("$TMP")
    BF="$TMP/.aitask-backfill"
    mkdir -p "$TMP/aitasks/metadata"
    : > "$TMP/aitasks/metadata/labels.txt"
    printf 'feature\nbug\nchore\ntest\nmanual_verification\n' \
        > "$TMP/aitasks/metadata/task_types.txt"

    seed_task 801 test                "$RISK_AFTER"
    seed_task 802 test                "$RISK_AFTER"
    seed_task 803 manual_verification "$CARRY"
    seed_task 804 bug                 "## Upstream defect"$'\n\n'"broken elsewhere"
    seed_task 805 bug                 "Spawned from t700 during Step 8b review."

    ( cd "$TMP" && git init -q . )
    git_commit_all seed
}

bf() { ( cd "$TMP" && TASK_DIR=aitasks AIT_FOLLOWUP_BACKFILL_DIR=.aitask-backfill "$BACKFILL" "$@" ); }

dry_run_id() { bf >/dev/null 2>&1; ls "$BF" | sort | tail -n1; }

kind_of()  { awk -v f=followup_kind '$0=="---"{n++; next} n==1 && $0 ~ "^"f":"{sub("^"f":[[:space:]]*",""); print; exit}' "$1"; }
state_of() { cat "$BF/$1/state" 2>/dev/null; }
digest()   { cksum < "$1" | awk '{print $1"-"$2}'; }
row_field() { sed -n "$1p" "$BF/$2/manifest.tsv" | cut -f"$3"; }

# ============================================================================
echo "--- Part A: manifest, canary, and the canary->resume path ---"

new_fixture
RUN="$(dry_run_id)"
assert_eq "dry run leaves state=REVIEWED" "REVIEWED" "$(state_of "$RUN")"
assert_eq "manifest has 5 rows" "5" "$(wc -l < "$BF/$RUN/manifest.tsv" | tr -d ' ')"
assert_contains "manifest assigns risk_mitigation (corrected rule order)" \
    "risk_mitigation" "$(cut -f2 "$BF/$RUN/manifest.tsv" | sort -u | tr '\n' ' ')"

bf --apply --run "$RUN" --limit 3 >/dev/null 2>&1
assert_eq "canary (--limit 3) leaves state=APPLYING" "APPLYING" "$(state_of "$RUN")"
assert_eq "canary journaled exactly 3 DONE rows" "3" "$(grep -c '^DONE' "$BF/$RUN/journal.tsv")"

# THE NON-VACUITY CHECK for the state table. The 2 unapplied rows have no
# preimage. If "preimage missing" were treated as unrecoverable, this resume
# could never complete -- and the plan REQUIRES the canary-then-resume path.
# An earlier draft of the design deadlocked exactly here.
bf --resume --run "$RUN" >/dev/null 2>&1
assert_eq "canary->resume reaches COMPLETE (preimage-less rows are NOT_STARTED)" \
    "COMPLETE" "$(state_of "$RUN")"
assert_eq "all 5 rows journaled after resume" "5" "$(grep -c '^DONE' "$BF/$RUN/journal.tsv")"
assert_eq "t801 written" "risk_mitigation" "$(kind_of "$TMP/aitasks/t801_fixture.md")"
assert_eq "t803 carry_over beats the MV fallback" "carry_over" "$(kind_of "$TMP/aitasks/t803_fixture.md")"

bf --verify-delta --run "$RUN" >/dev/null 2>&1
assert_eq "verify-delta passes on a clean complete run" "0" "$?"

# ============================================================================
echo "--- Part B: a second --apply is refused ---"

new_fixture
RUN="$(dry_run_id)"
bf --apply --run "$RUN" --limit 2 >/dev/null 2>&1
out="$(bf --apply --run "$RUN" 2>&1)"; rc=$?
assert_eq "second --apply against an APPLYING run exits non-zero" "1" "$rc"
assert_contains "refusal names the hazard" "Refusing a second --apply" "$out"
assert_contains "refusal offers resume" "--resume" "$out"
assert_contains "refusal offers abandon" "--abandon" "$out"

# ============================================================================
echo "--- Part C: drift BEFORE the first write -> ZERO writes ---"
# Committed, so the tree is clean and the GLOBAL PREFLIGHT is the guard under
# test (not check_baseline).

new_fixture
RUN="$(dry_run_id)"
echo "concurrent edit" >> "$TMP/aitasks/t804_fixture.md"
git_commit_all drift
out="$(bf --apply --run "$RUN" 2>&1)"; rc=$?
assert_eq "global preflight drift aborts non-zero" "1" "$rc"
assert_contains "abort states that nothing was written" "ZERO writes" "$out"
assert_eq "state stays REVIEWED after a zero-write abort" "REVIEWED" "$(state_of "$RUN")"
assert_eq "no task was written" "" "$(kind_of "$TMP/aitasks/t801_fixture.md")"
assert_eq "no journal was created" "false" \
    "$([ -f "$BF/$RUN/journal.tsv" ] && echo true || echo false)"

# ============================================================================
echo "--- Part D: drift AFTER the preflight, before a later row ---"
# The reported TOCTOU: the preflight hashes once, then a concurrent session
# edits a row the loop has not reached yet. Committed, so reconcile_row is the
# guard under test.

new_fixture
RUN="$(dry_run_id)"
bf --apply --run "$RUN" --limit 2 >/dev/null 2>&1          # rows 1-2 land
DRIFT_ROW="$(row_field 3 "$RUN" 3)"
DRIFT_ID="$(row_field 3 "$RUN" 1)"
echo "edited by another session" >> "$TMP/$DRIFT_ROW"
git_commit_all laterdrift
DRIFT_DIGEST="$(digest "$TMP/$DRIFT_ROW")"

out="$(bf --resume --run "$RUN" 2>&1)"; rc=$?
assert_eq "resume stops when a later row drifted" "1" "$rc"
assert_eq "state=FAILED after mid-run drift" "FAILED" "$(state_of "$RUN")"
assert_contains "the stop names the offending task" "$DRIFT_ID" "$out"
assert_eq "the drifted row's foreign bytes are left untouched" \
    "$DRIFT_DIGEST" "$(digest "$TMP/$DRIFT_ROW")"
assert_eq "no preimage was captured from the drifted bytes" "false" \
    "$([ -f "$BF/$RUN/preimages/$DRIFT_ID.md" ] && echo true || echo false)"
assert_eq "rows before the drift stayed landed" "2" "$(grep -c '^DONE' "$BF/$RUN/journal.tsv")"

# NEGATIVE CONTROL: abandon must refuse rather than clobber the other session.
out="$(bf --abandon --run "$RUN" 2>&1)"; rc=$?
assert_eq "abandon refuses while a foreign-drifted row is present" "1" "$rc"
assert_contains "refusal explains why" "discard someone else's edit" "$out"
assert_eq "the foreign edit survives the refusal" \
    "$DRIFT_DIGEST" "$(digest "$TMP/$DRIFT_ROW")"

# ============================================================================
echo "--- Part E: the write-succeeded / journal-append-lost window ---"
# Injected by deleting the journal line(s) after a successful write -- exactly
# the on-disk state a crash in that window leaves, and the case where trusting
# the journal instead of the hashes would strand recovery.

for LOST in DONE BOTH; do
    new_fixture
    RUN="$(dry_run_id)"
    bf --apply --run "$RUN" --limit 2 >/dev/null 2>&1
    ROW_ID="$(row_field 2 "$RUN" 1)"
    ROW_PATH="$(row_field 2 "$RUN" 3)"
    BEFORE="$(digest "$TMP/$ROW_PATH")"

    if [[ "$LOST" == DONE ]]; then
        awk -F'\t' -v id="$ROW_ID" '!($1=="DONE" && $2==id)' "$BF/$RUN/journal.tsv" > "$BF/$RUN/j.tmp"
    else
        awk -F'\t' -v id="$ROW_ID" '$2!=id' "$BF/$RUN/journal.tsv" > "$BF/$RUN/j.tmp"
    fi
    mv "$BF/$RUN/j.tmp" "$BF/$RUN/journal.tsv"

    bf --resume --run "$RUN" >/dev/null 2>&1
    assert_eq "[$LOST lost] resume still reaches COMPLETE" "COMPLETE" "$(state_of "$RUN")"
    assert_eq "[$LOST lost] the written row was NOT re-written (reconciled LANDED)" \
        "$BEFORE" "$(digest "$TMP/$ROW_PATH")"

    bf --abandon --run "$RUN" >/dev/null 2>&1
    assert_eq "[$LOST lost] abandon succeeds" "ABANDONED" "$(state_of "$RUN")"
    assert_eq "[$LOST lost] the unjournaled row was still restored from preimage" \
        "" "$(kind_of "$TMP/$ROW_PATH")"
done

# ============================================================================
echo "--- Part F: abandon restores byte-exactly ---"

new_fixture
declare -A ORIG
for f in "$TMP"/aitasks/t80*.md; do ORIG["$f"]="$(digest "$f")"; done
RUN="$(dry_run_id)"
bf --apply --run "$RUN" >/dev/null 2>&1
assert_eq "full apply completes" "COMPLETE" "$(state_of "$RUN")"
assert_eq "field written before abandon" "risk_mitigation" "$(kind_of "$TMP/aitasks/t801_fixture.md")"

bf --abandon --run "$RUN" >/dev/null 2>&1
allmatch=true
for f in "$TMP"/aitasks/t80*.md; do
    [[ "${ORIG[$f]}" == "$(digest "$f")" ]] || allmatch=false
done
assert_eq "every task file is byte-identical to its pre-run state" "true" "$allmatch"
assert_eq "state=ABANDONED" "ABANDONED" "$(state_of "$RUN")"

# ============================================================================
echo "--- Part G: dirty baseline, selected vs non-selected ---"
# Uncommitted on purpose: check_baseline is the guard under test here.

new_fixture
RUN="$(dry_run_id)"
SEL="$(row_field 1 "$RUN" 3)"
printf '\nuncommitted work\n' >> "$TMP/$SEL"
out="$(bf --apply --run "$RUN" --allow-dirty-baseline 2>&1)"; rc=$?
assert_eq "dirty SELECTED path aborts even with --allow-dirty-baseline" "1" "$rc"
assert_contains "message says the flag does not cover it" "does NOT relax this" "$out"
assert_eq "nothing was written" "" "$(kind_of "$TMP/aitasks/t802_fixture.md")"

new_fixture
seed_task 806 feature "Just ordinary new work, matching no rule."
git_commit_all add806
RUN="$(dry_run_id)"
printf '\nuncommitted\n' >> "$TMP/aitasks/t806_fixture.md"
out="$(bf --apply --run "$RUN" 2>&1)"; rc=$?
assert_eq "dirty NON-selected path aborts by default" "1" "$rc"

out="$(bf --apply --run "$RUN" --allow-dirty-baseline 2>&1)"; rc=$?
assert_eq "dirty NON-selected path proceeds with --allow-dirty-baseline" "0" "$rc"
assert_eq "run completes" "COMPLETE" "$(state_of "$RUN")"
assert_contains "excluded set records it" "t806" "$(cat "$BF/$RUN/baseline_excluded.txt")"
bf --verify-delta --run "$RUN" >/dev/null 2>&1
assert_eq "verify-delta passes with the excluded path subtracted" "0" "$?"

# ============================================================================
echo
echo "Results: $PASS passed, $FAIL failed (of $TOTAL)"
[[ "$FAIL" -eq 0 ]]
