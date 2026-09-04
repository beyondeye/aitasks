#!/usr/bin/env bash
# test_txn_snapshot.sh — lib/txn_snapshot.sh, the shared transaction boundary
# promoted from aitask_fold_mark.sh's private facility (t1698 / t1668).
#
# Drives the lib DIRECTLY, so each property is pinned once at its own level
# rather than only through a verb. Four groups:
#
#   A — txn_snap_add / txn_snap_restore round-trip, including the fail-closed
#       index read and the "second add after mutation is a no-op" rule.
#   B — txn_require_clean's dirt predicate, and BOTH orderings against
#       txn_snap_add (what proves the two dedup sets are independent).
#   C — the fail-loud restore contract: a failed restore is reported as a
#       failure, the snapshot directory survives it, a HOOK-only failure also
#       flips the verdict, and the partial message never claims a full rollback.
#   D — branch mode: a path under attachments/ (NOT one of the two symlinked
#       names) round-trips through the data worktree.
#
# Run: bash tests/test_txn_snapshot.sh
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
PASS=0; FAIL=0; TOTAL=0

TMP="$(mktemp -d)"
cleanup() { chmod -R u+w "$TMP" 2>/dev/null || true; rm -rf "$TMP"; }
trap cleanup EXIT

# Group C forces failures with `chmod a-w`. Root ignores the write bit, so under
# a root runner the forcing silently does nothing and every such case would pass
# VACUOUSLY. Skip visibly instead of reporting a pass.
CAN_FORCE_PERM=true
[[ "$(id -u)" -eq 0 ]] && CAN_FORCE_PERM=false

REPO="$TMP/repo"
mkdir -p "$REPO"
cd "$REPO" || exit 1
git init -q; git config user.email t@t.t; git config user.name tester
printf 'tracked-clean\n'    > clean.txt
printf 'tracked-staged\n'   > staged.txt
printf 'tracked-unstaged\n' > unstaged.txt
git add -A; git commit -q -m init

# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/txn_snapshot.sh"

idx_of() { git ls-files --stage -- "$1"; }
porc()   { git status --porcelain -- "$1"; }

echo "=== A — snapshot / restore round-trip ======================================="

# A1. A STAGED path comes back staged, with the same blob.
txn_snap_init
printf 'staged-v2\n' > staged.txt; git add staged.txt
IDX_BEFORE="$(idx_of staged.txt)"
PORC_BEFORE="$(porc staged.txt)"
txn_snap_add staged.txt
printf 'MUTATED\n' > staged.txt; git add staged.txt
txn_snap_restore
assert_eq "A1: staged path's bytes come back" "staged-v2" "$(cat staged.txt)"
assert_eq "A1: staged path's index entry comes back" "$IDX_BEFORE" "$(idx_of staged.txt)"
assert_eq "A1: staged path still reads as staged" "$PORC_BEFORE" "$(porc staged.txt)"
txn_snap_cleanup

# A2. An UNSTAGED-but-modified path comes back with its bytes, still unstaged.
txn_snap_init
printf 'unstaged-v2\n' > unstaged.txt          # dirty in the worktree only
txn_snap_add unstaged.txt
printf 'MUTATED\n' > unstaged.txt; git add unstaged.txt   # mutate AND stage it
txn_snap_restore
assert_eq "A2: unstaged path's bytes come back" "unstaged-v2" "$(cat unstaged.txt)"
assert_eq "A2: and it is unstaged again" " M unstaged.txt" "$(porc unstaged.txt)"
txn_snap_cleanup

# A3. A path with NO index entry stays out (the --force-remove half).
txn_snap_init
txn_snap_add untracked_new.txt                 # does not exist, not in the index
printf 'created by the transaction\n' > untracked_new.txt
git add untracked_new.txt
txn_snap_restore
assert_file_not_exists "A3: a transaction-created path is deleted on restore" untracked_new.txt
assert_eq "A3: and it is not left in the index" "" "$(idx_of untracked_new.txt)"
txn_snap_cleanup

# A4. FAIL CLOSED on an unreadable index — never record "absent", which would
# make --force-remove delete the caller's real entry on rollback.
txn_snap_init
printf 'garbage' > "$TMP/bad.idx"
A4_OUT="$( GIT_INDEX_FILE="$TMP/bad.idx" \
    bash -c 'source "$1/.aitask-scripts/lib/terminal_compat.sh"
             source "$1/.aitask-scripts/lib/task_utils.sh"
             source "$1/.aitask-scripts/lib/txn_snapshot.sh"
             txn_snap_init
             txn_snap_add clean.txt
             echo "REACHED_PAST_ADD"' _ "$PROJECT_DIR" 2>&1 )"
A4_RC=$?
assert_exit_nonzero_rc "A4: txn_snap_add dies on an unreadable index" "$A4_RC"
assert_not_contains "A4: and does not continue past the add" "REACHED_PAST_ADD" "$A4_OUT"
assert_contains "A4: naming the path and why it refuses" "could not read the index entry" "$A4_OUT"
txn_snap_cleanup

# A5. A SECOND txn_snap_add after mutation is a no-op, so restore yields the
# PRE-transaction bytes. Without the dedup the later snapshot would win (restore
# replays in index order).
txn_snap_init
printf 'pre-transaction\n' > clean.txt; git add clean.txt; git commit -q -m a5
txn_snap_add clean.txt
printf 'MUTATED\n' > clean.txt
txn_snap_add clean.txt                          # must NOT capture the mutation
txn_snap_restore
assert_eq "A5: restore yields the pre-transaction bytes" "pre-transaction" "$(cat clean.txt)"
txn_snap_cleanup

echo "=== B — txn_require_clean, and both orderings =============================="

# require_clean runs in a subshell so its `die` cannot kill the test file; the
# helper's whole contract is that it terminates.
rc_of() {  # rc_of <relpath>  -> sets RC_OUT, returns the helper's status
    RC_OUT="$( txn_require_clean "probe" "$1" 2>&1 )"
}

git checkout -q -- . 2>/dev/null || true
git reset -q HEAD -- . 2>/dev/null || true

# B1. Clean tracked path, and a path that does not exist, are both accepted.
txn_snap_init; ( rc_of clean.txt ); assert_exit_zero_rc "B1: a clean tracked path is accepted" "$?"
txn_snap_init; ( rc_of nope.txt );  assert_exit_zero_rc "B1: a non-existent path is accepted" "$?"

# B2. Each of the three dirt shapes is refused, and the message names the path
# and the remedy — the message IS the guard, so it is asserted, not assumed.
txn_snap_init; printf 'dirty\n' >> unstaged.txt
( rc_of unstaged.txt ); assert_exit_nonzero_rc "B2: an unstaged modification is refused" "$?"
txn_snap_init; rc_of_out="$( ( txn_require_clean "probe" unstaged.txt ) 2>&1 )" || true
assert_contains "B2: the refusal names the path"   "unstaged.txt" "$rc_of_out"
assert_contains "B2: and names the remedy"         "./ait git commit --" "$rc_of_out"
assert_contains "B2: and says why it refuses"      "absorb your edit" "$rc_of_out"
git checkout -q -- unstaged.txt

txn_snap_init; printf 'dirty\n' >> staged.txt; git add staged.txt
( rc_of staged.txt ); assert_exit_nonzero_rc "B2: a staged modification is refused" "$?"
git reset -q HEAD -- staged.txt; git checkout -q -- staged.txt

txn_snap_init; printf 'new\n' > brandnew.txt
( rc_of brandnew.txt ); assert_exit_nonzero_rc "B2: an untracked-but-present path is refused" "$?"
rm -f brandnew.txt

# B3/B4. BOTH orderings. A single `seen` set is unsound: clean-check-first would
# mark the path and make the snapshot skip (nothing to restore); snapshot-first
# would mark it and make the clean check skip (a dirty path committed).
txn_snap_init
( rc_of clean.txt ) >/dev/null
txn_snap_add clean.txt
assert_eq "B3: require_clean -> snap_add still snapshots" "1" "${#_TXN_SNAP_PATHS[@]}"

txn_snap_init
printf 'entry-dirty\n' >> unstaged.txt
txn_snap_add unstaged.txt
( rc_of unstaged.txt ); assert_exit_nonzero_rc "B4: snap_add -> require_clean still refuses" "$?"
txn_snap_restore >/dev/null; txn_snap_cleanup
git checkout -q -- unstaged.txt

echo "=== C — the fail-loud restore contract ====================================="

if [[ "$CAN_FORCE_PERM" != true ]]; then
    echo "SKIP: C1-C2 need an unwritable file to force a restore failure;"
    echo "      running as root, where the write bit is ignored and the forcing"
    echo "      would silently do nothing (the cases would pass vacuously)."
else
    # C1. A failed BYTES restore is reported as a failure, names the path, and
    # preserves the snapshot directory — the only remaining copy of the
    # pre-transaction bytes.
    mkdir -p sub; printf 'pre\n' > sub/f.txt; git add sub/f.txt; git commit -q -m c1
    txn_snap_init
    txn_snap_add sub/f.txt
    printf 'MUTATED\n' > sub/f.txt
    # The FILE, not the directory: cp over an existing file opens and truncates
    # it, so only the file's own write bit stops it (verified — an unwritable
    # parent directory lets the copy through and the case would pass vacuously).
    chmod a-w sub/f.txt
    txn_snap_restore; C1_RC=$?
    chmod u+w sub/f.txt
    assert_exit_nonzero_rc "C1: txn_snap_restore reports a failed restore" "$C1_RC"
    assert_contains "C1: the failure names the path" "sub/f.txt" "${_TXN_RESTORE_FAILED[*]}"
    assert_eq "C1: the snapshot half is marked incomplete" "true" "$_TXN_SNAP_RESTORE_INCOMPLETE"
    C1_DIR="$_TXN_SNAP_DIR"
    txn_snap_cleanup
    assert_dir_exists "C1: the snapshot directory survives a failed restore" "$C1_DIR"
    rm -rf "$C1_DIR"; _TXN_SNAP_RESTORE_INCOMPLETE=false; _TXN_SNAP_DIR=""
    git checkout -q -- sub/f.txt

    # C2. The EXIT-trap message tells the truth: the PARTIAL report, naming the
    # items and the recovery directory, and NOT the full-rollback claim.
    C2_OUT="$( bash -c '
        source "$1/.aitask-scripts/lib/terminal_compat.sh"
        source "$1/.aitask-scripts/lib/task_utils.sh"
        source "$1/.aitask-scripts/lib/txn_snapshot.sh"
        txn_begin "ait probe verb"
        txn_snap_add sub/f.txt
        printf "MUTATED\n" > sub/f.txt
        chmod a-w sub/f.txt
        exit 7' _ "$PROJECT_DIR" 2>&1 )"
    C2_RC=$?
    chmod u+w sub/f.txt
    assert_eq "C2: the dying status survives the trap" "7" "$C2_RC"
    assert_contains "C2: the report says the rollback did not fully restore" \
        "did NOT fully restore" "$C2_OUT"
    assert_contains "C2: it names the un-restored path" "sub/f.txt" "$C2_OUT"
    assert_contains "C2: it names the recovery directory" "ait_txn_snap" "$C2_OUT"
    assert_not_contains "C2: and NEVER claims a full rollback" \
        "rolled back every mutation" "$C2_OUT"
    git checkout -q -- sub/f.txt 2>/dev/null || true

    # C2b. The positive control. Without it, C2 would pass against a build that
    # never prints the full-rollback message at all.
    C2B_OUT="$( bash -c '
        source "$1/.aitask-scripts/lib/terminal_compat.sh"
        source "$1/.aitask-scripts/lib/task_utils.sh"
        source "$1/.aitask-scripts/lib/txn_snapshot.sh"
        txn_begin "ait probe verb"
        txn_snap_add sub/f.txt
        printf "MUTATED\n" > sub/f.txt
        exit 7' _ "$PROJECT_DIR" 2>&1 )"
    assert_contains "C2b: a clean rollback DOES claim every mutation was rolled back" \
        "rolled back every mutation" "$C2B_OUT"
    assert_not_contains "C2b: and does not print the partial report" \
        "did NOT fully restore" "$C2B_OUT"
    assert_eq "C2b: the bytes really came back" "pre" "$(cat sub/f.txt)"
fi

# C3. A HOOK-only failure also flips the verdict. This is the case that
# separates "restore verdict" from "rollback verdict": the snapshot half
# succeeds, so anything deriving the verdict from txn_snap_restore alone would
# announce a complete rollback. Runs on every platform — no chmod needed.
c3_hook() { txn_rollback_failed "blob sha256:deadbeef on backend dir — created by this transaction and could not be deleted"; }
txn_snap_init
_TXN_ACTIVE=true
txn_on_rollback c3_hook
txn_snap_add clean.txt
txn_rollback; C3_RC=$?
assert_exit_nonzero_rc "C3: a hook-only failure makes txn_rollback report failure" "$C3_RC"
assert_contains "C3: the hook's item is in the report" "backend dir" "${_TXN_RESTORE_FAILED[*]}"
assert_eq "C3: but the snapshot half is NOT marked incomplete" \
    "false" "$_TXN_SNAP_RESTORE_INCOMPLETE"
assert_dir_not_exists "C3: so the snapshot dir is still cleaned up" "$_TXN_SNAP_DIR"

# C4. The clean control for C3: same shape, hook records nothing.
c4_hook() { return 0; }
txn_snap_init
_TXN_ACTIVE=true
txn_on_rollback c4_hook
txn_snap_add clean.txt
txn_rollback; C4_RC=$?
assert_exit_zero_rc "C4: a clean rollback reports success" "$C4_RC"
assert_eq "C4: with nothing recorded" "0" "${#_TXN_RESTORE_FAILED[@]}"

echo "=== D — branch mode (the data-worktree path resolution) ====================="

# In branch mode only aitasks/ and aiplans/ are symlinked into the checkout
# (lib/data_symlinks.sh: AIT_DATA_LINKS), so `attachments/…` does NOT resolve
# from the repo root. Resolving the relpath against the CWD records "absent" and
# a restore then DELETES the real file. No existing test covers this: both
# test_fold_mark.sh and test_attach_fold_rebind.sh state legacy-mode fixtures.
BREPO="$TMP/brepo"
mkdir -p "$BREPO"
cd "$BREPO" || exit 1
git init -q; git config user.email t@t.t; git config user.name tester
printf 'code\n' > README.md; git add -A; git commit -q -m init
git worktree add -q --detach "$BREPO/.aitask-data" HEAD 2>/dev/null
( cd .aitask-data && git checkout -q --orphan aitask-data && git rm -rq --cached . 2>/dev/null || true
  rm -f README.md
  mkdir -p aitasks attachments/meta/ab
  printf 'pre-transaction meta\n' > attachments/meta/ab/cdef.json
  git add -A && git commit -q -m "data init" )
ln -s .aitask-data/aitasks aitasks
_AIT_DATA_WORKTREE=""          # force re-detection for this repo
_ait_detect_data_worktree
assert_eq "D0: fixture really is in branch mode" ".aitask-data" "$_AIT_DATA_WORKTREE"

txn_snap_init
txn_snap_add attachments/meta/ab/cdef.json
assert_file_exists "D1: the snapshot captured bytes (not 'absent')" "$_TXN_SNAP_DIR/0.blob"
printf 'MUTATED\n' > .aitask-data/attachments/meta/ab/cdef.json
txn_snap_restore
assert_eq "D1: a non-symlinked data path round-trips through the data worktree" \
    "pre-transaction meta" "$(cat .aitask-data/attachments/meta/ab/cdef.json)"
txn_snap_cleanup

echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
  echo "ALL TESTS PASSED"
else
  echo "SOME TESTS FAILED"
  exit 1
fi
