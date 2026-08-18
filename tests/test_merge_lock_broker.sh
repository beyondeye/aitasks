#!/usr/bin/env bash
# test_merge_lock_broker.sh - the Step 9 merge mutex + broker (t1560_1).
#
# Covers the enumerated concurrency cases mandated by
# aidocs/framework/testing_conventions.md:10,18 for a new concurrency primitive.
#
# Asserts run at TOP LEVEL (plain PASS/FAIL/TOTAL, the
# test_gate_lock_single_winner.sh shape) - only the broker INVOCATIONS are
# subshelled, so no counter increment is ever lost in a subshell.
#
# NOTE ON SESSIONS: lib/pid_anchor.sh memoizes this session's anchor triple
# process-wide, cached even when UNKNOWN. Flipping AIT_AGENT_PID and re-calling
# in the SAME shell changes nothing, so every "different session" case invokes
# the broker as a SEPARATE PROCESS with the differing anchor in its environment.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

BROKER="$PROJECT_DIR/.aitask-scripts/aitask_merge_task.sh"

AITASKS_LOCK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/test_mergelock_XXXXXX")"
export AITASKS_LOCK_DIR
LOCKD="$AITASKS_LOCK_DIR/merge"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_mergefix_XXXXXX")"

ANCHORS=""            # every fixture anchor pid we spawn
cleanup() {
    local p
    for p in $ANCHORS; do kill "$p" 2>/dev/null || true; done
    rm -rf "$TMP" "$AITASKS_LOCK_DIR"
}
trap cleanup EXIT

# spawn_anchor -> echo a live pid usable as AIT_AGENT_PID. proc_fixtures.sh
# provides only dead_pid_fixture(); a LIVE anchored process is the caller's job
# (its own comments say so), so this is the hand-rolled shape used by
# test_gate_lock_single_winner.sh:76-82.
spawn_anchor() {
    # Redirect the child's stdout/stderr: a background process that inherits
    # the command-substitution pipe holds its write end open, and `$(...)`
    # blocks reading until EOF - i.e. for the full sleep.
    sleep 600 >/dev/null 2>&1 &
    local p=$!
    ANCHORS="$ANCHORS $p"
    printf '%s' "$p"
}

enable_seams()  { : > "$AITASKS_LOCK_DIR/.ait_merge_test_seams"; }
disable_seams() { rm -f "$AITASKS_LOCK_DIR/.ait_merge_test_seams"; }

# broker <repo> <anchor_pid> <args...> — one broker run, as its own process.
broker() {
    local repo="$1" anchor="$2"; shift 2
    ( cd "$repo" && AIT_AGENT_PID="$anchor" "$BROKER" "$@" ) 2>/dev/null
}
broker_err() {                      # same, but stderr merged in (progress lines)
    local repo="$1" anchor="$2"; shift 2
    ( cd "$repo" && AIT_AGENT_PID="$anchor" "$BROKER" "$@" ) 2>&1
}

free_lock() { rm -rf "$LOCKD" "$LOCKD.gc"; }

# new_repo <name> — a fixture repo with the three branch shapes the recovery
# assertions need: cleanly-mergeable, conflicting, unrelated-history.
new_repo() {
    local r="$TMP/$1"
    rm -rf "$r"; mkdir -p "$r"
    (
        cd "$r" || exit 1
        git init -q -b main .
        git config user.email t@t; git config user.name t
        printf 'base\n' > shared.txt
        git add -A; git commit -qm base
        # clean: touches only its own file
        git checkout -q -b aitask/tclean
        printf 'clean\n' > clean.txt; git add -A; git commit -qm clean
        # clean2: a SECOND cleanly-mergeable task, for "usable again" proofs
        git checkout -q main; git checkout -q -b aitask/tclean2
        printf 'clean2\n' > clean2.txt; git add -A; git commit -qm clean2
        # conflicting: rewrites shared.txt, and so does main
        git checkout -q main; git checkout -q -b aitask/tconf
        printf 'theirs\n' > shared.txt; git add -A; git commit -qm theirs
        git checkout -q main
        printf 'ours\n' > shared.txt; git add -A; git commit -qm ours
        # unrelated history: merge fails BEFORE MERGE_HEAD exists
        git checkout -q --orphan aitask/tunrel
        git rm -rqf . 2>/dev/null || true
        printf 'orphan\n' > orphan.txt; git add -A; git commit -qm orphan
        git checkout -q main
    ) >/dev/null 2>&1
    printf '%s' "$r"
}

echo "========================="
echo "Merge lock + broker (t1560_1)"
echo "========================="

# ---------------------------------------------------------------------------
echo "--- Case 0: cross-process hold (positive control) ---"
# The load-bearing property: the reservation OUTLIVES the acquiring process.
# Fails loudly if merge_lock.sh ever inherits registry_lock.sh's EXIT trap.
free_lock; enable_seams
R0="$(new_repo r0)"; A0="$(spawn_anchor)"
out="$(broker "$R0" "$A0" begin tA main aitask/tclean)"
assert_contains "case0: first begin merges" "MERGE_OK:" "$out"
assert_dir_exists "case0: lock dir still present after begin's process exited" "$LOCKD"
out="$(broker "$R0" "$A0" status)"
assert_contains "case0: a SEPARATE process still sees the lock held" "HELD:tA|" "$out"
B0="$(spawn_anchor)"
out="$(broker "$R0" "$B0" begin tB main aitask/tclean2 --wait-secs 1)"
assert_contains "case0: a second process is excluded and names the holder" "BUSY:tA:" "$out"
out="$(broker "$R0" "$A0" finish tA)"
assert_eq "case0: holder releases" "RELEASED" "$out"
out="$(broker "$R0" "$B0" status)"
assert_eq "case0: lock free again" "FREE" "$out"
# ---------------------------------------------------------------------------
echo "--- Case 11: the test seams are NOT production-reachable ---"
# AITASKS_LOCK_DIR is a DEPLOYMENT seam (stale_lock.sh:39-42 tells admins to
# point it at a shared base), so it must NOT be what enables the seams.
free_lock; disable_seams
R11="$(new_repo r11)"; A11="$(spawn_anchor)"; B11="$(spawn_anchor)"
out="$(broker "$R11" "$A11" begin tA main aitask/tclean)"
assert_contains "case11: holder merges" "MERGE_OK:" "$out"
out="$( cd "$R11" && AIT_AGENT_PID="$B11" AIT_MERGE_LOCK_DISABLED=1 "$BROKER" begin tB main aitask/tclean2 --wait-secs 1 2>/dev/null )"
assert_contains "case11: AIT_MERGE_LOCK_DISABLED is IGNORED without the marker file" "BUSY:tA:" "$out"
enable_seams
out="$( cd "$R11" && AIT_AGENT_PID="$B11" AIT_MERGE_LOCK_DISABLED=1 "$BROKER" begin tB main aitask/tclean2 2>/dev/null )"
assert_not_contains "case11: with the marker present the seam takes effect" "BUSY:" "$out"
# ---------------------------------------------------------------------------
echo "--- Case 3: conflict-parked reservation ---"
free_lock; enable_seams
R3="$(new_repo r3)"; A3="$(spawn_anchor)"; B3="$(spawn_anchor)"
out="$(broker "$R3" "$A3" begin tA main aitask/tconf)"
assert_contains "case3: conflicting branch reports MERGE_CONFLICT" "MERGE_CONFLICT:" "$out"
assert_contains "case3: the conflicting path is named" "shared.txt" "$out"
assert_dir_exists "case3: the reservation is RETAINED across a conflict" "$LOCKD"
out="$(broker "$R3" "$B3" begin tB main aitask/tclean2 --wait-secs 1)"
assert_contains "case3: B does not enter and names A's task id" "BUSY:tA:" "$out"
out="$(broker "$R3" "$A3" abort tA)"
assert_eq "case3: abort clears the merge and releases" "ABORTED" "$out"
out="$(broker "$R3" "$B3" begin tB main aitask/tclean2)"
assert_contains "case3: B proceeds after the abort (different, cleanly mergeable task)" "MERGE_OK:" "$out"
broker "$R3" "$B3" finish tB >/dev/null

# ---------------------------------------------------------------------------
echo "--- Case 8b: non-conflict merge failure ---"
free_lock
R8b="$(new_repo r8b)"; A8b="$(spawn_anchor)"
out="$(broker "$R8b" "$A8b" begin tU main aitask/tunrel)"
assert_contains "case8b: unrelated history fails before MERGE_HEAD" "MERGE_FAILED:" "$out"
out="$(broker "$R8b" "$A8b" abort tU)"
assert_eq "case8b: abort reports RELEASED_NO_MERGE, not ABORT_FAILED" "RELEASED_NO_MERGE" "$out"
# The usable-again proof MUST come from a different, cleanly mergeable task -
# re-running tU would fail identically forever and prove nothing.
out="$(broker "$R8b" "$A8b" begin tV main aitask/tclean)"
assert_contains "case8b: a DIFFERENT cleanly-mergeable task proves the lock is usable" "MERGE_OK:" "$out"
broker "$R8b" "$A8b" finish tV >/dev/null

# ---------------------------------------------------------------------------
echo "--- Case 8: non-owner release refused ---"
free_lock
R8="$(new_repo r8)"; A8="$(spawn_anchor)"; C8="$(spawn_anchor)"
broker "$R8" "$A8" begin tA main aitask/tclean >/dev/null
out="$(broker "$R8" "$A8" finish tOTHER)"
assert_eq "case8a: another task id cannot release" "NOT_HOLDER:tA" "$out"
assert_dir_exists "case8a: A's lock is intact" "$LOCKD"
# (c) same task id, provably DIFFERENT live session - separate process, so the
# memoized self-anchor is that process's own.
out="$(broker "$R8" "$C8" finish tA)"
assert_contains "case8c: same task id, different session is refused" "NOT_OWNER_SESSION:tA" "$out"
assert_dir_exists "case8c: A's lock is still intact" "$LOCKD"
# (b) SAME task id, but a caller that cannot prove its own anchor. This is the
# hole a task-id-only check would leave: two unidentifiable sessions on one task
# id would both pass, and the second would free the first's live reservation.
out="$( cd "$R8" && env -u TMUX -u TMUX_PANE AIT_AGENT_PID=1 "$BROKER" finish tA 2>/dev/null )"
assert_contains "case8b: same task id with an unprovable anchor is refused" "NOT_OWNER_SESSION:tA" "$out"
assert_dir_exists "case8b: A's lock survived the unprovable-anchor release attempt" "$LOCKD"
out="$(broker "$R8" "$A8" finish tA)"
assert_eq "case8a: the real holder can still finish" "RELEASED" "$out"
# (e) no resolvable anchor -> nothing locked
out="$( cd "$R8" && env -u TMUX -u TMUX_PANE AIT_AGENT_PID=1 "$BROKER" begin tX main aitask/tclean2 2>/dev/null )"
assert_eq "case8e: begin refuses without a session anchor" "NO_SESSION_ANCHOR" "$out"
assert_dir_not_exists "case8e: nothing was locked" "$LOCKD"
# (d) planted lock dir with no task_id
mkdir -p "$LOCKD"; printf '%s\n' "$A8" > "$LOCKD/pid"; printf 'x\n' > "$LOCKD/owner"
out="$(broker "$R8" "$A8" status)"
assert_contains "case8d: an incomplete acquisition is its own state" "HOLDER_INCOMPLETE:" "$out"
out="$(broker "$R8" "$A8" force-release --yes)"
assert_contains "case8d: force-release clears it" "FORCE_RELEASED" "$out"
assert_dir_not_exists "case8d: the planted lock is gone" "$LOCKD"
# ---------------------------------------------------------------------------
echo "--- Case 4: stale-holder recovery ---"
free_lock
R4="$(new_repo r4)"; A4="$(spawn_anchor)"; B4="$(spawn_anchor)"
broker "$R4" "$A4" begin tA main aitask/tclean >/dev/null
assert_dir_exists "case4: holder acquired" "$LOCKD"
# live-anchored holder is NEVER displaced
out="$(broker "$R4" "$B4" begin tB main aitask/tclean2 --wait-secs 1)"
assert_contains "case4: a LIVE anchored holder is never displaced" "BUSY:tA:" "$out"
kill "$A4" 2>/dev/null; wait "$A4" 2>/dev/null || true
out="$(broker "$R4" "$B4" begin tB main aitask/tclean2 --wait-secs 5)"
assert_contains "case4: a DEAD anchor is reclaimed by the waiter" "MERGE_OK:" "$out"
broker "$R4" "$B4" finish tB >/dev/null
# an UNKNOWN anchor is never displaced
free_lock; mkdir -p "$LOCKD"
printf '0\n' > "$LOCKD/pid"; printf 'tZ\n' > "$LOCKD/task_id"; printf 'tok\n' > "$LOCKD/owner"
C4="$(spawn_anchor)"
out="$(broker "$R4" "$C4" status)"
assert_contains "case4: an unresolvable anchor reads as unknown" "|unknown" "$out"
out="$(broker "$R4" "$C4" begin tC main aitask/tclean2 --wait-secs 1)"
assert_contains "case4: an UNKNOWN holder is never auto-reclaimed" "BUSY:tZ:" "$out"
# ---------------------------------------------------------------------------
echo "--- Case 7 / wedge_recovery_probe: recovery terminates ---"
# (continues from the wedged unknown-anchor lock above)
out="$(broker "$R4" "$C4" force-release)"
assert_contains "case7: dry-run reports without touching anything" "DRY_RUN:" "$out"
assert_dir_exists "case7: dry-run left the lock intact" "$LOCKD"
out="$(broker "$R4" "$C4" force-release --yes)"
assert_contains "case7: force-release clears a wedged unknown holder" "FORCE_RELEASED:tZ" "$out"
out="$(broker "$R4" "$C4" begin tD main aitask/tclean2)"
assert_contains "case7: usable again, proved by a cleanly mergeable task" "MERGE_OK:" "$out"
broker "$R4" "$C4" finish tD >/dev/null
# a LIVE holder is refused
free_lock
D4="$(spawn_anchor)"
broker "$R4" "$D4" begin tL main aitask/tclean >/dev/null 2>&1 || true
out="$(broker "$R4" "$C4" force-release --yes)"
assert_contains "case7: force-release refuses a provably live holder" "REFUSED_LIVE_HOLDER:" "$out"
assert_dir_exists "case7: the live holder's lock is intact" "$LOCKD"
free_lock

# ---------------------------------------------------------------------------
echo "--- Case 7b: the two residue remedies are distinct ---"
free_lock
R7="$(new_repo r7)"; A7="$(spawn_anchor)"
broker "$R7" "$A7" begin tA main aitask/tconf >/dev/null      # parks at MERGE_CONFLICT
kill "$A7" 2>/dev/null; wait "$A7" 2>/dev/null || true        # holder now dead
E7="$(spawn_anchor)"
out="$(broker "$R7" "$E7" force-release --yes)"
assert_contains "case7b: MERGE_HEAD present, no flag -> refused with its remedy" "RESIDUE_PRESENT:merge_head:--abort-merge" "$out"
assert_dir_exists "case7b: lock kept" "$LOCKD"
out="$(broker "$R7" "$E7" force-release --reset-hard --yes)"
assert_contains "case7b: the WRONG remedy is refused, never attempted" "RESIDUE_PRESENT:merge_head:--abort-merge" "$out"
out="$(broker "$R7" "$E7" force-release --abort-merge --yes)"
assert_contains "case7b: the matching remedy verifies clean and releases" "FORCE_RELEASED:tA" "$out"
out="$(broker "$R7" "$E7" begin tV main aitask/tclean)"
assert_contains "case7b: usable again via a different, cleanly mergeable task" "MERGE_OK:" "$out"
broker "$R7" "$E7" finish tV >/dev/null

# planted unmerged-index-WITHOUT-MERGE_HEAD: the other residue state
free_lock
R7b="$(new_repo r7b)"; A7b="$(spawn_anchor)"
broker "$R7b" "$A7b" begin tA main aitask/tconf >/dev/null
( cd "$R7b" && rm -f "$(git rev-parse --git-dir)/MERGE_HEAD" )
kill "$A7b" 2>/dev/null; wait "$A7b" 2>/dev/null || true
F7="$(spawn_anchor)"
out="$(broker "$R7b" "$F7" force-release --abort-merge --yes)"
assert_eq "case7b: --abort-merge on an unmerged index with no MERGE_HEAD is refused" "WRONG_REMEDY:no_merge_head" "$out"
assert_dir_exists "case7b: lock kept on the wrong-remedy refusal" "$LOCKD"
out="$(broker "$R7b" "$F7" force-release --reset-hard --yes)"
assert_contains "case7b: --reset-hard reaches a verified-clean tree and releases" "FORCE_RELEASED:tA" "$out"
out="$(broker "$R7b" "$F7" begin tV main aitask/tclean)"
assert_contains "case7b: usable again after the reset-hard rung" "MERGE_OK:" "$out"
broker "$R7b" "$F7" finish tV >/dev/null

# ---------------------------------------------------------------------------
echo "--- Case 8b(2) / abort on a planted unsafe state ---"
free_lock
R8u="$(new_repo r8u)"; A8u="$(spawn_anchor)"
broker "$R8u" "$A8u" begin tA main aitask/tconf >/dev/null
( cd "$R8u" && rm -f "$(git rev-parse --git-dir)/MERGE_HEAD" )
out="$(broker "$R8u" "$A8u" abort tA)"
assert_contains "case8b: abort reports the state AND its remedy flag" "ABORT_UNSAFE:unmerged_index_no_merge_head:--reset-hard" "$out"
assert_dir_exists "case8b: the lock is KEPT on ABORT_UNSAFE" "$LOCKD"
broker "$R8u" "$A8u" force-release --reset-hard --yes >/dev/null

# ---------------------------------------------------------------------------
echo "--- Case 8c: the verification window does not strand the lock ---"
free_lock
R8c="$(new_repo r8c)"; A8c="$(spawn_anchor)"
# A REAL task worktree, so a cleanup regression that removes the worktree while
# leaving the branch cannot pass this proof. (Merging a branch that is checked
# out in another worktree is fine - only checking it out twice is refused.)
WT8c="$R8c/aiwork/tclean"
( cd "$R8c" && git worktree add -q "$WT8c" aitask/tclean ) >/dev/null 2>&1
assert_dir_exists "case8c: the task worktree exists before the verification window" "$WT8c"
out="$(broker "$R8c" "$A8c" begin tA main aitask/tclean)"
assert_contains "case8c: merge lands" "MERGE_OK:" "$out"
sha_before="$( cd "$R8c" && git rev-parse HEAD )"
# a scripted Step-9 mimic takes the "release and stop" branch: finish WITHOUT
# cleanup, so the branch and its worktree survive for the resume.
out="$(broker "$R8c" "$A8c" finish tA)"
assert_eq "case8c: finish releases without cleanup" "RELEASED" "$out"
assert_dir_not_exists "case8c: the lock is free" "$LOCKD"
rc=0; ( cd "$R8c" && git rev-parse --verify --quiet refs/heads/aitask/tclean >/dev/null ) || rc=$?
assert_eq "case8c: the task branch still exists for the resume" "0" "$rc"
assert_dir_exists "case8c: the task WORKTREE also survives the release-and-stop exit" "$WT8c"
wt_listed="$( cd "$R8c" && git worktree list --porcelain | grep -c 'refs/heads/aitask/tclean' || true )"
assert_eq "case8c: the worktree record survives too (not just the directory)" "1" "$wt_listed"
out="$(broker "$R8c" "$A8c" begin tA main aitask/tclean)"
assert_contains "case8c: re-reservation is idempotent" "MERGE_OK:" "$out"
sha_after="$( cd "$R8c" && git rev-parse HEAD )"
assert_eq "case8c: the idempotent re-merge creates NO new commit" "$sha_before" "$sha_after"
broker "$R8c" "$A8c" finish tA >/dev/null

# ---------------------------------------------------------------------------
echo "--- Case 10: cleanup authorization, delegation and partial failure ---"
free_lock
R10="$(new_repo r10)"; A10="$(spawn_anchor)"; G10="$(spawn_anchor)"
broker "$R10" "$A10" begin tA main aitask/tclean >/dev/null
out="$(broker "$R10" "$G10" cleanup tA tclean --task-complete)"
assert_contains "case10: a non-owner session cannot clean up" "NOT_OWNER_SESSION" "$out"
out="$(broker "$R10" "$A10" cleanup tA tclean)"
assert_eq "case10: cleanup refuses without --task-complete" "CLEANUP_REQUIRES_COMPLETION" "$out"
rc=0; ( cd "$R10" && git rev-parse --verify --quiet refs/heads/aitask/tclean >/dev/null ) || rc=$?
assert_eq "case10: the branch is intact after the refusal" "0" "$rc"
out="$(broker "$R10" "$A10" cleanup tA tOTHERNAME --task-complete)"
assert_contains "case10: a task_name disagreeing with the record removes nothing" "TARGET_MISMATCH:aitask/tclean" "$out"
rc=0; ( cd "$R10" && git rev-parse --verify --quiet refs/heads/aitask/tclean >/dev/null ) || rc=$?
assert_eq "case10: still intact after TARGET_MISMATCH" "0" "$rc"
out="$(broker "$R10" "$A10" cleanup tA tclean --task-complete)"
assert_contains "case10: an authorized cleanup delegates and reports CLEANED" "CLEANED" "$out"
rc=0; ( cd "$R10" && git rev-parse --verify --quiet refs/heads/aitask/tclean >/dev/null ) || rc=$?
assert_eq "case10: the merged task branch is gone" "1" "$rc"
broker "$R10" "$A10" finish tA >/dev/null

# unmerged branch -> CLEANED_PARTIAL, reservation KEPT
free_lock
R10b="$(new_repo r10b)"; A10b="$(spawn_anchor)"
broker "$R10b" "$A10b" begin tA main aitask/tclean >/dev/null
# Advance the task branch AFTER the merge, so it is no longer fully merged -
# the realistic "agent committed once more" shape. `git branch -d` then refuses,
# and a refusal must never be reported as a completed cleanup.
( cd "$R10b" && git checkout -q aitask/tclean &&
  printf 'later\n' > later.txt && git add -A && git commit -qm later &&
  git checkout -q main ) >/dev/null 2>&1
out="$(broker "$R10b" "$A10b" cleanup tA tclean --task-complete)"
assert_contains "case10: an unmerged branch is a PARTIAL cleanup, never CLEANED" "CLEANED_PARTIAL:" "$out"
assert_dir_exists "case10: CLEANED_PARTIAL keeps the reservation" "$LOCKD"
broker "$R10b" "$A10b" finish tA >/dev/null

# ---------------------------------------------------------------------------
echo "--- Case 14: the guarded section preserves caller traps ---"
# stale_lock_guarded_section is a shared-library export and the file's first
# trap-installing function: `trap -` would strip a handler the caller installed.
tf="$TMP/trapcheck.sh"
cat > "$tf" <<'INNER'
set -u
PROJECT_DIR="$1"; LOCKBASE="$2"; MODE="$3"; SENT="$4"
export AITASKS_LOCK_DIR="$LOCKBASE"
. "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"
. "$PROJECT_DIR/.aitask-scripts/lib/stale_lock.sh"
d="$LOCKBASE/tsec"; mkdir -p "$d"
caller_handler() { printf 'CALLER_HANDLER_RAN\n' > "$SENT"; }
case "$MODE" in
  prior)   trap caller_handler INT ;;
  # Write the marker to the SENTINEL FILE, not stdout: the trap fires while the
  # guarded-section call is redirected to /dev/null, so a printf would vanish.
  signal)  trap 'printf "CALLER_TERM_RAN\n" > "$SENT"; exit 0' TERM ;;
  none)    : ;;
esac
body_ok()   { return 0; }
body_fail() { return 7; }
body_signal() { kill -TERM $$; sleep 5; return 0; }
case "$MODE" in
  prior)  stale_lock_guarded_section "$d" body_ok     >/dev/null 2>&1 ;;
  none)   stale_lock_guarded_section "$d" body_ok     >/dev/null 2>&1 ;;
  signal) stale_lock_guarded_section "$d" body_signal >/dev/null 2>&1 ;;
esac
rc_section=$?
printf 'SECTION_RC=%s\n' "$rc_section"
printf 'TRAP_AFTER=%s\n' "$(trap -p INT | tr -d '\n')"
# the assertion that matters: does it still FIRE?
kill -INT $$ 2>/dev/null || true
sleep 0.2
[[ -f "$SENT" ]] && printf 'FIRED\n' || printf 'NOT_FIRED\n'
INNER
chmod +x "$tf"
sent="$TMP/sentinel_prior"; rm -f "$sent"
out="$(bash "$tf" "$PROJECT_DIR" "$AITASKS_LOCK_DIR" prior "$sent" 2>/dev/null || true)"
assert_contains "case14: the guarded section returns its fn's status" "SECTION_RC=0" "$out"
assert_contains "case14: the caller's INT handler is restored verbatim" "caller_handler" "$out"
assert_contains "case14: the restored handler actually FIRES (not just present)" "FIRED" "$out"
# The signal path: the section must release the guard, restore the caller's
# handler, and RE-RAISE so that handler actually runs.
sentS="$TMP/sentinel_signal"; rm -f "$sentS"
bash "$tf" "$PROJECT_DIR" "$AITASKS_LOCK_DIR" signal "$sentS" >/dev/null 2>&1 || true
assert_contains "case14: a signal inside the section re-raises into the caller's handler" "CALLER_TERM_RAN" "$(cat "$sentS" 2>/dev/null || true)"
assert_file_exists "case14: the caller's handler really ran on the signal path" "$sentS"
assert_dir_not_exists "case14: the guard was released on the signal path" "$AITASKS_LOCK_DIR/tsec.gc"
sent2="$TMP/sentinel_none"; rm -f "$sent2"
out="$(bash "$tf" "$PROJECT_DIR" "$AITASKS_LOCK_DIR" none "$sent2" 2>/dev/null || true)"
assert_contains "case14: negative control ran" "TRAP_AFTER=" "$out"
assert_not_contains "case14: a caller with NO prior handler ends with none installed, not ours" "_stale_lock_guard_on_signal" "$out"
# ---------------------------------------------------------------------------
echo "--- Case 9: publish is atomic with acquire ---"
free_lock
pf="$TMP/publishfail.sh"
cat > "$pf" <<'INNER'
set -u
PROJECT_DIR="$1"; LOCKBASE="$2"
export AITASKS_LOCK_DIR="$LOCKBASE"
. "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"
. "$PROJECT_DIR/.aitask-scripts/lib/stale_lock.sh"
d="$LOCKBASE/pubfail"
failing_publish() { return 1; }
STALE_LOCK_PUBLISH_FN=failing_publish
if stale_lock_acquire "$d" 2 0.05 "pubfail"; then printf 'ACQUIRED\n'; else printf 'REFUSED\n'; fi
[[ -e "$d" ]] && printf 'LOCK_LEFT\n' || printf 'NO_LOCK_LEFT\n'
unset STALE_LOCK_PUBLISH_FN
if stale_lock_acquire "$d" 5 0.05 "pubfail"; then printf 'CONTENDER_OK\n'; else printf 'CONTENDER_FAILED\n'; fi
INNER
out="$(bash "$pf" "$PROJECT_DIR" "$AITASKS_LOCK_DIR" 2>/dev/null || true)"
assert_contains "case9: a failing publish fn makes acquire fail closed" "REFUSED" "$out"
assert_contains "case9: no lock dir is left behind" "NO_LOCK_LEFT" "$out"
assert_contains "case9: the next attempt succeeds" "CONTENDER_OK" "$out"

# ---------------------------------------------------------------------------
echo "--- Case 15: a released pre-merge failure never claims MERGE_FAILED ---"
# MERGE_FAILED's contract is that the reservation is RETAINED. A caller told
# MERGE_FAILED runs the held-lock recovery path; emitting it for a path that
# RELEASES sends that recovery at an already-free lock.
free_lock
R15="$(new_repo r15)"; A15="$(spawn_anchor)"
# an untracked file that checking out `other` would overwrite
( cd "$R15" && git checkout -q -b other main && printf 'o\n' > collide.txt &&
  git add -A && git commit -qm o && git checkout -q main &&
  printf 'untracked\n' > collide.txt ) >/dev/null 2>&1
out="$(broker "$R15" "$A15" begin tA other aitask/tclean)"
assert_contains "case15: a failed checkout reports a PREFLIGHT verdict" "PREFLIGHT_CHECKOUT_FAILED:" "$out"
assert_not_contains "case15: and NOT MERGE_FAILED, whose contract is 'lock retained'" "MERGE_FAILED" "$out"
assert_dir_not_exists "case15: the lock really was released, matching the verdict" "$LOCKD"
out="$(broker "$R15" "$A15" status)"
assert_eq "case15: status agrees the lock is free" "FREE" "$out"
# every verdict the broker can emit must be exported for t1560_2
vocab="$("$BROKER" --list-verdicts)"
assert_contains "case15: PREFLIGHT_CHECKOUT_FAILED is exported" "PREFLIGHT_CHECKOUT_FAILED" "$vocab"
assert_contains "case15: PREFLIGHT_HEAD_MISMATCH is exported" "PREFLIGHT_HEAD_MISMATCH" "$vocab"
assert_contains "case15: RETAINED is exported for begin" "RETAINED" "$vocab"

# ---------------------------------------------------------------------------
echo "--- Case 16: a failed release is its own machine-readable state ---"
# A leaked .gc makes stale_lock_release fail. Reporting the ordinary refusal
# verdict would tell the caller the lock is NOT held, so it would call neither
# finish nor abort, and the reservation would wedge with no verdict naming it.
free_lock
R16="$(new_repo r16)"; A16="$(spawn_anchor)"
broker "$R16" "$A16" begin tA main aitask/tclean >/dev/null      # holds the lock
broker "$R16" "$A16" finish tA >/dev/null
# Re-acquire, then dirty the tree so the NEXT begin takes a pre-merge refusal,
# and leak the guard so its release cannot succeed.
broker "$R16" "$A16" begin tA main aitask/tclean2 >/dev/null
# A path that genuinely RELEASES (clean tree, nothing to abort) - the leaked
# guard is what makes that release fail. A path like ABORT_UNSAFE deliberately
# KEEPS the lock and never reaches the release at all.
mkdir -p "$LOCKD.gc"                                             # the leaked guard
out="$(broker "$R16" "$A16" abort tA)"
assert_contains "case16: a release that failed reports RETAINED, not the bare verdict" "RETAINED:" "$out"
assert_contains "case16: and preserves the original context inside it" "RELEASED_NO_MERGE" "$out"
assert_dir_exists "case16: the reservation really is still held, matching the verdict" "$LOCKD"
rmdir "$LOCKD.gc"                                                # the documented cure
free_lock

# ---------------------------------------------------------------------------
echo "--- Case 17: the dry-run emits an opaque, copy-safe holder token ---"
free_lock
R17="$(new_repo r17)"; A17="$(spawn_anchor)"; C17="$(spawn_anchor)"
broker "$R17" "$A17" begin tA main aitask/tclean >/dev/null
kill "$A17" 2>/dev/null; wait "$A17" 2>/dev/null || true
out="$(broker "$R17" "$C17" force-release)"
tok="${out#DRY_RUN:}"
assert_contains "case17: the dry-run verdict carries a token" "DRY_RUN:" "$out"
assert_contains_re "case17: the token is opaque and shell-safe (hex only)" "^[0-9a-f]+$" "$tok"
err="$(broker_err "$R17" "$C17" force-release)"
assert_contains "case17: the exact copy-safe --expect command is printed" "--yes --expect $tok" "$err"
out="$(broker "$R17" "$C17" force-release --yes --expect "$tok")"
assert_contains "case17: the printed token is accepted verbatim" "FORCE_RELEASED:tA" "$out"
free_lock

echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -gt 0 ]] && exit 1
echo "All tests PASSED"
