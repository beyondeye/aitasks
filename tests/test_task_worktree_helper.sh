#!/usr/bin/env bash
# test_task_worktree_helper.sh - Tests for aitask_task_worktree.sh (t1548).
# Run: bash tests/test_task_worktree_helper.sh
#
# The helper is the single canonical classifier for "where does this task's
# worktree actually live", and it is destructive. These tests therefore cover
# three families:
#
#   * the t1548 regression itself (cases 3, 5): a worktree moved out of
#     aiwork/<task_name> must be found and removed. Case 5 fails against the old
#     hardcoded trio, which removed nothing;
#   * every refusal that stands between the helper and someone's data (6-9, 13,
#     17, 19) - each one is load-bearing, not defensive garnish;
#   * the transport and verdict contracts the callers rely on (10, 11, 16, 20).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"
HELPER="$PROJECT_DIR/.aitask-scripts/aitask_task_worktree.sh"

PASS=0
FAIL=0
TOTAL=0

ROOTS=()
cleanup() {
    cd "$PROJECT_DIR" || true
    local r
    for r in "${ROOTS[@]:-}"; do
        [[ -n "$r" && -d "$r" ]] && chmod -R u+w "$r" 2>/dev/null
        [[ -n "$r" ]] && rm -rf "$r"
    done
    return 0
}
trap cleanup EXIT

# fresh_repo -> creates a temp repo, cds into it, sets REPO / PRIMARY / OUTSIDE.
fresh_repo() {
    local root
    root="$(mktemp -d "${TMPDIR:-/tmp}/t1548test.XXXXXX")"
    ROOTS+=("$root")
    OUTSIDE="$root"
    REPO="$root/repo"
    mkdir -p "$REPO"
    git -C "$REPO" init -q
    git -C "$REPO" config user.email t@t
    git -C "$REPO" config user.name t
    git -C "$REPO" commit -q --allow-empty -m init
    cd "$REPO"
    PRIMARY="$(git symbolic-ref --short HEAD)"
}

# run_helper <args...> -> stdout in OUT, stderr in ERR, exit status in RC.
run_helper() {
    local errfile
    errfile="$(mktemp "${TMPDIR:-/tmp}/t1548err.XXXXXX")"
    RC=0
    OUT="$("$HELPER" "$@" 2>"$errfile")" || RC=$?
    ERR="$(cat "$errfile")"
    rm -f "$errfile"
}

echo "=== Case 1: resolve, nothing exists ==="
fresh_repo
run_helper resolve tA
assert_eq "1: resolve prints NONE" "NONE" "$OUT"
assert_eq "1: resolve exits 0" "0" "$RC"

echo "=== Case 2: resolve, conventional worktree ==="
fresh_repo
git worktree add -q -b aitask/tA aiwork/tA "$PRIMARY"
run_helper resolve tA
assert_eq "2: USABLE at the conventional path" "USABLE $(cd aiwork/tA && pwd -P)" "$OUT"

echo "=== Case 3: resolve after 'git worktree move' (t1548 core) ==="
fresh_repo
git worktree add -q -b aitask/tA aiwork/tA "$PRIMARY"
git worktree move aiwork/tA "$OUTSIDE/moved"
run_helper resolve tA
assert_eq "3: USABLE at the NEW path" "USABLE $OUTSIDE/moved" "$OUT"
assert_not_contains "3: never reports the conventional path" "aiwork/tA" "$OUT"

echo "=== Case 4: resolve after a manual mv (stale record) ==="
fresh_repo
git worktree add -q -b aitask/tA aiwork/tA "$PRIMARY"
mv aiwork/tA "$OUTSIDE/mv1"
run_helper resolve tA
assert_contains "4: reports STALE, not USABLE/NONE" "STALE " "$OUT"
assert_contains "4: names the recorded (old) path" "aiwork/tA" "$OUT"

echo "=== Case 5: remove --force on a moved worktree (THE t1548 REGRESSION) ==="
# Against the old hardcoded trio this case fails: nothing is removed and the
# procedure still reports a clean abort.
fresh_repo
git worktree add -q -b aitask/tA aiwork/tA "$PRIMARY"
git worktree move aiwork/tA "$OUTSIDE/moved"
run_helper remove tA --force
assert_contains "5: worktree reported removed" "WORKTREE_REMOVED $OUTSIDE/moved" "$OUT"
assert_contains "5: branch reported deleted" "BRANCH_DELETED aitask/tA" "$OUT"
assert_contains "5: verdict CLEAN" "CLEAN" "$OUT"
assert_eq "5: exits 0" "0" "$RC"
assert_eq "5: moved directory is gone on disk" "gone" "$([ -e "$OUTSIDE/moved" ] && echo present || echo gone)"
assert_eq "5: branch is gone" "" "$(git branch --list aitask/tA)"

echo "=== Case 6: remove --force after a manual mv (must NOT prune or delete) ==="
fresh_repo
git worktree add -q -b aitask/tA aiwork/tA "$PRIMARY"
ADMIN="$(git rev-parse --path-format=absolute --git-common-dir)/worktrees/tA"
mv aiwork/tA "$OUTSIDE/mv1"
run_helper remove tA --force
assert_contains "6: refuses with stale_record" "WORKTREE_KEPT stale_record" "$OUT"
assert_contains "6: branch delete skipped" "BRANCH_KEPT skipped aitask/tA" "$OUT"
assert_contains "6: verdict RESIDUE" "RESIDUE" "$OUT"
assert_eq "6: exits 1" "1" "$RC"
assert_eq "6: moved directory survives" "present" "$([ -d "$OUTSIDE/mv1" ] && echo present || echo gone)"
assert_eq "6: branch survives" "1" "$(git branch --list aitask/tA | wc -l | tr -d ' ')"
assert_eq "6: admin metadata intact (not pruned)" "present" "$([ -d "$ADMIN" ] && echo present || echo gone)"

echo "=== Case 7: an UNRELATED stale worktree survives (no repo-global prune) ==="
fresh_repo
git worktree add -q -b aitask/tA aiwork/tA "$PRIMARY"
git worktree add -q -b other/tZ aiwork/tZ "$PRIMARY"
mv aiwork/tZ "$OUTSIDE/unrelated"
OTHER_ADMIN="$(git rev-parse --path-format=absolute --git-common-dir)/worktrees/tZ"
run_helper remove tA --force
assert_contains "7: our own worktree was removed" "WORKTREE_REMOVED" "$OUT"
assert_eq "7: unrelated admin metadata survives" "present" "$([ -d "$OTHER_ADMIN" ] && echo present || echo gone)"
assert_contains "7: unrelated stale record still listed" "aiwork/tZ" "$(git worktree list --porcelain)"
assert_eq "7: unrelated branch survives" "1" "$(git branch --list other/tZ | wc -l | tr -d ' ')"

echo "=== Case 8: remove --force on a LOCKED worktree ==="
fresh_repo
git worktree add -q -b aitask/tA aiwork/tA "$PRIMARY"
git worktree lock aiwork/tA --reason "user lock"
run_helper remove tA --force
assert_contains "8: refuses with locked" "WORKTREE_KEPT locked" "$OUT"
assert_contains "8: verdict RESIDUE" "RESIDUE" "$OUT"
assert_eq "8: exits 1" "1" "$RC"
assert_eq "8: directory survives" "present" "$([ -d aiwork/tA ] && echo present || echo gone)"
assert_eq "8: branch survives" "1" "$(git branch --list aitask/tA | wc -l | tr -d ' ')"
assert_contains "8: lock survives" "locked" "$(git worktree list --porcelain)"
git worktree unlock aiwork/tA

echo "=== Case 9: worktree path containing a TAB ==="
fresh_repo
TABPATH="$(printf '%s/tab\there' "$OUTSIDE")"
git worktree add -q -b aitask/tA "$TABPATH" "$PRIMARY"
run_helper resolve tA
assert_contains "9: resolve reports UNSAFE" "UNSAFE " "$OUT"
assert_not_contains "9: the raw tab never reaches stdout" "$(printf '\t')" "$OUT"
run_helper remove tA --force
assert_contains "9: remove refuses with unsafe_path" "WORKTREE_KEPT unsafe_path" "$OUT"
assert_eq "9: exits 1" "1" "$RC"
assert_eq "9: directory untouched" "present" "$([ -d "$TABPATH" ] && echo present || echo gone)"
assert_eq "9: branch untouched" "1" "$(git branch --list aitask/tA | wc -l | tr -d ' ')"

echo "=== Case 10: remove when nothing exists (pre-fork abort stays quiet) ==="
# Five abort call sites are reached BEFORE any fork; this no-op must stay silent.
fresh_repo
run_helper remove tA --force
assert_eq "10: three exact lines" "WORKTREE_NONE
BRANCH_NONE
CLEAN" "$OUT"
assert_eq "10: exits 0" "0" "$RC"
assert_eq "10: stderr is empty" "" "$ERR"

echo "=== Case 11: remove --force with an unmerged branch -> PRESERVED ==="
fresh_repo
git worktree add -q -b aitask/tA aiwork/tA "$PRIMARY"
git -C aiwork/tA commit -q --allow-empty -m "work"
run_helper remove tA --force
assert_contains "11: worktree removed" "WORKTREE_REMOVED" "$OUT"
assert_contains "11: branch kept, reason names the compared ref" "BRANCH_KEPT unmerged_into:$PRIMARY aitask/tA" "$OUT"
assert_contains "11: verdict PRESERVED" "PRESERVED" "$OUT"
assert_eq "11: exits 0 without --strict" "0" "$RC"
assert_eq "11: the commits are still reachable" "1" "$(git branch --list aitask/tA | wc -l | tr -d ' ')"

echo "=== Case 12: remove WITHOUT --force on a dirty worktree ==="
fresh_repo
git worktree add -q -b aitask/tA aiwork/tA "$PRIMARY"
echo "uncommitted" > aiwork/tA/dirty.txt
run_helper remove tA
assert_contains "12: refuses with dirty" "WORKTREE_KEPT dirty" "$OUT"
assert_contains "12: verdict RESIDUE" "RESIDUE" "$OUT"
assert_eq "12: exits 1" "1" "$RC"
assert_eq "12: the uncommitted file survives" "uncommitted" "$(cat aiwork/tA/dirty.txt)"

echo "=== Case 13: aitask/<n> checked out at the MAIN root ==="
fresh_repo
git checkout -q -b aitask/tA
run_helper resolve tA
assert_contains "13: resolve reports MAIN" "MAIN " "$OUT"
run_helper remove tA --force
assert_contains "13: refuses with main_worktree" "WORKTREE_KEPT main_worktree" "$OUT"
assert_eq "13: exits 1" "1" "$RC"
assert_eq "13: the repository is intact" "present" "$([ -d "$REPO/.git" ] && echo present || echo gone)"
assert_eq "13: git still works" "aitask/tA" "$(git symbolic-ref --short HEAD)"

echo "=== Case 14: remove --force with cwd INSIDE the worktree ==="
fresh_repo
git worktree add -q -b aitask/tA aiwork/tA "$PRIMARY"
cd aiwork/tA
run_helper remove tA --force
cd "$REPO"
assert_contains "14: worktree removed from inside itself" "WORKTREE_REMOVED" "$OUT"
assert_contains "14: verdict CLEAN" "CLEAN" "$OUT"
assert_eq "14: exits 0" "0" "$RC"
assert_eq "14: directory gone" "gone" "$([ -e "$REPO/aiwork/tA" ] && echo present || echo gone)"

echo "=== Case 15: leftover aiwork/<n> directory with NO record ==="
# The superset property: the old 'rm -rf aiwork/<task_name>' caught this, so the
# record-aware replacement must too.
fresh_repo
mkdir -p aiwork/tA
echo leftover > aiwork/tA/stale.txt
run_helper remove tA --force
assert_contains "15: leftover reported removed" "WORKTREE_REMOVED" "$OUT"
assert_contains "15: verdict CLEAN" "CLEAN" "$OUT"
assert_eq "15: leftover directory gone" "gone" "$([ -e "$REPO/aiwork/tA" ] && echo present || echo gone)"

echo "=== Case 16: Step 9 shape (--strict, no --force) with an unmerged branch ==="
# Step 9 calls the helper bare; a surviving branch must block archival.
fresh_repo
git worktree add -q -b aitask/tA aiwork/tA "$PRIMARY"
git -C aiwork/tA commit -q --allow-empty -m "work"
run_helper remove tA --strict
assert_contains "16: verdict PRESERVED on stdout" "PRESERVED" "$OUT"
assert_contains "16: the surviving branch is named" "BRANCH_KEPT unmerged_into:$PRIMARY aitask/tA" "$OUT"
assert_eq "16: --strict exits non-zero on PRESERVED" "1" "$RC"

echo "=== Case 17: hostile 'gitdir:' pointer in an unregistered directory ==="
# The unregistered fallback must never follow a pointer stored inside the
# directory it is about to delete.
fresh_repo
mkdir -p aiwork/tA
printf 'gitdir: %s/.git\n' "$REPO" > aiwork/tA/.git
run_helper remove tA --force
assert_eq "17: the leftover directory is gone" "gone" "$([ -e "$REPO/aiwork/tA" ] && echo present || echo gone)"
assert_eq "17: the repository .git SURVIVES" "present" "$([ -d "$REPO/.git" ] && echo present || echo gone)"
assert_eq "17: git still works" "$PRIMARY" "$(git symbolic-ref --short HEAD)"

echo "=== Case 18: admin cleanup touches only the target's own entry ==="
# The forced rm -rf fallback is defensive: `git worktree remove --force` on a
# registered, unlocked, present worktree does not fail in practice, so only the
# success path is deterministically reachable here. What is asserted is the
# property that matters either way - no OTHER worktree's metadata is disturbed.
fresh_repo
git worktree add -q -b aitask/tA aiwork/tA "$PRIMARY"
git worktree add -q -b other/tZ aiwork/tZ "$PRIMARY"
COMMON="$(git rev-parse --path-format=absolute --git-common-dir)"
run_helper remove tA --force
assert_eq "18: the target's admin entry is gone" "gone" "$([ -d "$COMMON/worktrees/tA" ] && echo present || echo gone)"
assert_eq "18: the unrelated admin entry survives" "present" "$([ -d "$COMMON/worktrees/tZ" ] && echo present || echo gone)"
assert_eq "18: the unrelated worktree still works" "other/tZ" "$(git -C aiwork/tZ symbolic-ref --short HEAD)"

echo "=== Case 19: newline path whose PREFIX directory exists ==="
# A line-based porcelain parser captures the prefix here; if that prefix exists
# it is unrelated data the helper would otherwise delete.
fresh_repo
mkdir -p "$OUTSIDE/nl/foo"
echo "unrelated data" > "$OUTSIDE/nl/foo/keepme.txt"
NLPATH="$(printf '%s/nl/foo\nbar' "$OUTSIDE")"
git worktree add -q -b aitask/tA "$NLPATH" "$PRIMARY"
run_helper resolve tA
assert_contains "19: resolve reports UNSAFE" "UNSAFE " "$OUT"
assert_not_contains "19: never resolves to the bare prefix" "USABLE" "$OUT"
assert_eq_trim "19: single line of output (no split record)" "1" "$(printf '%s\n' "$OUT" | wc -l)"
run_helper remove tA --force
assert_contains "19: remove refuses with unsafe_path" "WORKTREE_KEPT unsafe_path" "$OUT"
assert_eq "19: exits 1" "1" "$RC"
assert_eq "19: the unrelated PREFIX directory survives" "unrelated data" "$(cat "$OUTSIDE/nl/foo/keepme.txt")"

echo "=== Case 20: a producer error is its own state, never a negative result ==="
fresh_repo
NOREPO="$(mktemp -d "${TMPDIR:-/tmp}/t1548norepo.XXXXXX")"
ROOTS+=("$NOREPO")
cd "$NOREPO"
run_helper resolve tA
assert_eq "20: resolve outside a repo exits non-zero" "3" "$RC"
assert_eq "20: resolve prints no state" "" "$OUT"
assert_contains "20: resolve explains itself on stderr" "not inside a git repository" "$ERR"
run_helper remove tA --force
assert_eq "20: remove outside a repo exits non-zero" "3" "$RC"
assert_not_contains "20: remove never claims CLEAN" "CLEAN" "$OUT"
assert_not_contains "20: remove never claims NONE" "NONE" "$OUT"
cd "$PROJECT_DIR"

echo "=== Case 21: a failed run produces NO stdout (the callers' fail-closed premise) ==="
# Both call sites parse stdout. `read -r state path <<<"$(helper resolve X)"`
# succeeds with an empty state when the helper never ran, so the prose guards in
# SKILL.md / task-abort.md key on the exit status instead. That is only sound if
# a failed run is guaranteed to print nothing a caller could mistake for a
# result - which is what this case pins.
fresh_repo
run_helper resolve            # missing <task_name>
assert_eq "21: missing argument exits 2" "2" "$RC"
assert_eq "21: missing argument prints no stdout" "" "$OUT"
run_helper frobnicate tA
assert_eq "21: unknown subcommand exits 2" "2" "$RC"
assert_eq "21: unknown subcommand prints no stdout" "" "$OUT"
run_helper resolve tA --force
assert_eq "21: --force on resolve exits 2" "2" "$RC"
assert_eq "21: --force on resolve prints no stdout" "" "$OUT"
run_helper remove tA --bogus
assert_eq "21: unknown option exits 2" "2" "$RC"
assert_eq "21: unknown option prints no stdout" "" "$OUT"
assert_contains "21: usage goes to stderr" "Usage:" "$ERR"

echo
echo "=== Results ==="
echo "Total:  $TOTAL"
echo "Pass:   $PASS"
echo "Fail:   $FAIL"

if [[ $FAIL -eq 0 ]]; then
    echo "PASS"
    exit 0
else
    echo "FAIL"
    exit 1
fi
