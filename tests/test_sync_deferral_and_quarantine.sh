#!/usr/bin/env bash
# test_sync_deferral_and_quarantine.sh - the sweep's two deferral outcomes and
# the durable publication quarantine (t1599_3).
#
# Run: bash tests/test_sync_deferral_and_quarantine.sh
#
# The sweep has TWO orthogonal non-success outcomes, and merging them breaks one
# of the two:
#
#   protected_dirty      files we could not commit are still dirty. Blocks the
#                        REBASE, and ONLY when remote_ahead > 0.
#   publication_blocked  we hold a commit whose content we cannot vouch for.
#                        Blocks the PUSH, REGARDLESS of remote_ahead — the race
#                        advances refs/heads/aitask-locks, never aitask-data, so
#                        remote_ahead == 0 is its normal shape.
#
# Several assertions below are written to FAIL against a specific wrong design;
# each says which. That is deliberate — an assertion that also passes against
# the shape being rejected proves nothing.

set -uo pipefail

TEST_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/sync_fixture.sh"

# Advance origin/aitask-data from a second clone, so the local repo is genuinely
# behind (remote_ahead > 0).
advance_remote() {
    local tmpdir="$1"
    rm -rf "$tmpdir/pc2"
    # --branch: never check out main, whose `aitasks` symlink would otherwise be
    # committed over the real directory by the `git add -A` below.
    git clone -q --branch aitask-data "$tmpdir/remote.git" "$tmpdir/pc2" 2>/dev/null
    (
        cd "$tmpdir/pc2"
        git config user.email pc2@test.com
        git config user.name PC2
        git config commit.gpgsign false
        printf 'from pc2\n' >> aitasks/t30_gamma.md
        git add -A && git commit -q -m "pc2: advance data branch"
        git push -q origin aitask-data 2>/dev/null
    ) >/dev/null 2>&1
    (cd "$tmpdir/local" && git -C .aitask-data fetch -q origin 2>/dev/null)
}

remote_data_sha() { git -C "$1/remote.git" rev-parse refs/heads/aitask-data 2>/dev/null; }
remote_blob() { git -C "$1/remote.git" show "refs/heads/aitask-data:$2" 2>/dev/null; }

# Turn the marker-gated seams on for this fixture's lock base.
enable_seams() { mkdir -p "$1/locks" && touch "$1/locks/.ait_sync_test_seams"; }
quarantine_file() { echo "$1/local/.git/worktrees/-aitask-data/ait-sync-quarantine"; }

# Run the sweep with a seam hook active.
run_sync_seam() {
    local tmpdir="$1" point="$2" hook="$3"; shift 3
    (
        cd "$tmpdir/local"
        export PATH="$PWD/bin:$PATH"
        export TEST_HOSTNAME="${TEST_HOSTNAME:-testhost}"
        export AITASKS_LOCK_DIR="$tmpdir/locks"
        export "AIT_SYNC_SEAM_${point}=$hook"
        ./.aitask-scripts/aitask_sync.sh --batch "$@" 2>"$tmpdir/sync_stderr"
    )
}

echo "=== aitask_sync.sh deferral + quarantine (t1599_3) ==="
echo ""

# --- Test 1: protected_dirty blocks the REBASE when the remote is ahead ----
#
# The t20 edit is load-bearing, not scenery: it gives the run a LOCAL commit to
# replay, which is what makes a rebase necessary and therefore blockable. With
# local_ahead == 0 there is nothing to replay and the tracked protected file no
# incoming commit touches is fast-forwarded instead — deliberately, since
# t1725_3 (that case is Test 1c below). Dropping the t20 edit does not weaken
# this test, it silently converts it into the opposite one.
echo "--- Test 1: protected file + remote ahead -> DEFERRED, not ERROR:pull_rebase_failed ---"
TMP1="$(setup_repo)"
plant_lock "$TMP1" 10 "$(lock_yaml_live 10)"
(cd "$TMP1/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md \
                  && printf 'edit20\n' >> .aitask-data/aitasks/t20_beta.md)
advance_remote "$TMP1"
OUT1="$(run_sync "$TMP1")"
assert_contains "the run reports a protected_dirty deferral" "DEFERRED:protected_dirty" "$OUT1"
assert_not_contains "and NOT the rebase error the dirty file would otherwise cause" \
    "ERROR:pull_rebase_failed" "$OUT1"
# The fetch is read-only and must still have happened.
FETCHED1="$(git -C "$TMP1/local/.aitask-data" rev-parse --verify --quiet origin/aitask-data)"
REMOTE1="$(remote_data_sha "$TMP1")"
assert_eq "the read-only fetch still ran" "$REMOTE1" "$FETCHED1"

# --- Tests 1a-1d: the tree-state rebase gate, all four directions (t1725_3) -
#
# The old gate was "any protected file AND remote_ahead > 0". It deferred two
# cases nothing actually blocks, and one parked session could stall a branch
# indefinitely. These four pin the replacement in BOTH directions, because a
# gate that only ever says "blocked" would pass a one-sided test just as well.

# 1a: an UNTRACKED protected file no incoming commit touches. git rebase ignores
# an untracked path entirely, so there is nothing to defer for.
echo "--- Test 1a: untracked protected file, not incoming -> no deferral, converges ---"
TMP1A="$(setup_repo)"
plant_lock "$TMP1A" 10 "$(lock_yaml_live 10)"
(cd "$TMP1A/local" && printf 'draft\n' > .aitask-data/aiplans/p10_x.md \
                   && printf 'edit20\n' >> .aitask-data/aitasks/t20_beta.md)
advance_remote "$TMP1A"          # touches t30_gamma.md only
OUT1A="$(run_sync "$TMP1A")"
assert_not_contains "an untracked protected file does not block the rebase" \
    "DEFERRED" "$OUT1A"
assert_contains "pc2's commit was pulled" "from pc2" \
    "$(cat "$TMP1A/local/.aitask-data/aitasks/t30_gamma.md")"
assert_contains "the protected file is still there, untouched" "draft" \
    "$(cat "$TMP1A/local/.aitask-data/aiplans/p10_x.md")"

# 1b: the SAME position but the protected file is modified-tracked. A rebase
# needs a clean tree, so this one must still defer. Paired with 1a, this is what
# proves the gate discriminates on tree state rather than on "is anything
# protected".
echo "--- Test 1b: tracked protected file in the same position -> still defers ---"
TMP1B="$(setup_repo)"
plant_lock "$TMP1B" 10 "$(lock_yaml_live 10)"
(cd "$TMP1B/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md \
                   && printf 'edit20\n' >> .aitask-data/aitasks/t20_beta.md)
advance_remote "$TMP1B"
OUT1B="$(run_sync "$TMP1B")"
assert_contains "a tracked protected file still blocks the rebase" \
    "DEFERRED:protected_dirty" "$OUT1B"

# 1c: behind-only (local_ahead == 0) with a TRACKED protected file that no
# incoming commit touches. A fast-forward never conflicts and git refuses one
# that would overwrite a dirty file, so this converges instead of deferring —
# t1696's scenario, and the case Test 1 used to assert the opposite of.
echo "--- Test 1c: local_ahead == 0, tracked dirty, not incoming -> fast-forwards ---"
TMP1C="$(setup_repo)"
plant_lock "$TMP1C" 10 "$(lock_yaml_live 10)"
(cd "$TMP1C/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
advance_remote "$TMP1C"
OUT1C="$(run_sync "$TMP1C")"
assert_not_contains "a behind-only branch converges rather than deferring" \
    "DEFERRED" "$OUT1C"
assert_contains "pc2's commit arrived by fast-forward" "from pc2" \
    "$(cat "$TMP1C/local/.aitask-data/aitasks/t30_gamma.md")"
assert_contains "and the protected file kept its uncommitted edit" "edit10" \
    "$(cat "$TMP1C/local/.aitask-data/aitasks/t10_alpha.md")"

# 1d: untracked, but an incoming commit CREATES the same path. This is the one
# untracked case that must block: the checkout would overwrite it.
echo "--- Test 1d: untracked protected file that IS incoming -> defers ---"
TMP1D="$(setup_repo)"
plant_lock "$TMP1D" 10 "$(lock_yaml_live 10)"
(cd "$TMP1D/local" && printf 'mine\n' > .aitask-data/aiplans/p10_x.md)
# pc2 creates the very path we are protecting.
rm -rf "$TMP1D/pc2"
git clone -q --branch aitask-data "$TMP1D/remote.git" "$TMP1D/pc2" 2>/dev/null
(
    cd "$TMP1D/pc2"
    git config user.email pc2@test.com; git config user.name PC2
    git config commit.gpgsign false
    # aiplans/ holds no committed file in the fixture, so git never tracked the
    # directory and the clone does not have it. Without this the redirect below
    # fails, the whole subshell is silently swallowed, and the remote never
    # advances — the test then passes or fails for the wrong reason entirely.
    mkdir -p aiplans
    printf 'theirs\n' > aiplans/p10_x.md
    git add -A && git commit -q -m "pc2: create p10_x"
    git push -q origin aitask-data 2>/dev/null
) >/dev/null 2>&1
(cd "$TMP1D/local" && git -C .aitask-data fetch -q origin 2>/dev/null)
OUT1D="$(run_sync "$TMP1D")"
assert_contains "an incoming commit on the protected path defers" \
    "DEFERRED:protected_dirty" "$OUT1D"
assert_contains "and the local bytes are untouched" "mine" \
    "$(cat "$TMP1D/local/.aitask-data/aiplans/p10_x.md")"

# --- Test 2: control — nothing protected, the rebase still runs -----------
echo "--- Test 2: control - nothing protected -> the rebase runs normally ---"
TMP2="$(setup_repo)"
(cd "$TMP2/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
advance_remote "$TMP2"
OUT2="$(run_sync "$TMP2")"
assert_not_contains "an unprotected run does not defer" "DEFERRED" "$OUT2"
assert_contains "pc2's commit was actually pulled" "from pc2" \
    "$(cat "$TMP2/local/.aitask-data/aitasks/t30_gamma.md")"

# --- Test 3: the ASYMMETRY — protected_dirty does NOT block a push --------
echo "--- Test 3: protected file + remote NOT ahead -> the eligible commit IS pushed ---"
TMP3="$(setup_repo)"
plant_lock "$TMP3" 10 "$(lock_yaml_live 10)"
(cd "$TMP3/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md \
                  && printf 'edit20\n' >> .aitask-data/aitasks/t20_beta.md)
BEFORE3="$(remote_data_sha "$TMP3")"
OUT3="$(run_sync "$TMP3")"
AFTER3="$(remote_data_sha "$TMP3")"
assert_not_contains "with the remote level, a protected file is not a deferral" \
    "DEFERRED" "$OUT3"
if [[ "$BEFORE3" != "$AFTER3" ]]; then
    assert_record_pass
else
    assert_record_fail
    echo "FAIL: the eligible t20 commit should still have been pushed"
fi
# Pins the asymmetry in the direction OPPOSITE to Test 5, so neither guard can
# be widened into the other.

# --- Test 4: Hazard A measure 2 — lock acquired during the scan -----------
echo "--- Test 4: a lock taken between enumeration and commit -> group dropped ---"
TMP4="$(setup_repo)"
enable_seams "$TMP4"
(cd "$TMP4/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
# The seam fires AFTER the first enumeration and BEFORE the CAS re-enumeration,
# so the CAS is the only thing that can catch this.
HOOK4="cd '$TMP4/local' && git fetch origin aitask-locks --quiet 2>/dev/null; \
 p=\$(git rev-parse origin/aitask-locks); t=\$(git rev-parse origin/aitask-locks^{tree}); \
 b=\$(printf 'task_id: 10\nlocked_by: o@x\nlocked_at: 2026-01-01 00:00\nhostname: testhost\npid: $$\npid_starttime: $(awk '{print $22}' /proc/$$/stat)\npid_starttime_kind: proc' | git hash-object -w --stdin); \
 nt=\$( { git ls-tree \$t | grep -v 't10_lock.yaml' || true; printf '100644 blob %s\tt10_lock.yaml\n' \$b; } | git mktree ); \
 c=\$(echo seam | git commit-tree \$nt -p \$p); git push -q origin \$c:refs/heads/aitask-locks 2>/dev/null"
OUT4="$(run_sync_seam "$TMP4" pre_commit_phase "$HOOK4")"
assert_not_contains "the raced group is not committed" \
    "Auto-commit t10" "$(data_log "$TMP4")"
assert_contains "and the reason names the CAS" \
    "locked while we were scanning" "$(cat "$TMP4/sync_stderr")"

# --- Test 5: Hazard A measures 3+4 — the publication guard ----------------
# THE case a remote_ahead-gated deferral misses: only the LOCK branch moved, so
# the data branch is level and do_push would otherwise succeed.
echo "--- Test 5: file rewritten during the commit -> withheld, remote unchanged ---"
TMP5="$(setup_repo)"
enable_seams "$TMP5"
(cd "$TMP5/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
BEFORE5="$(remote_data_sha "$TMP5")"
PRE5="$(remote_blob "$TMP5" aitasks/t10_alpha.md)"
OUT5="$(run_sync_seam "$TMP5" pre_group_commit \
    "printf 'RACED\n' >> '$TMP5/local/.aitask-data/aitasks/t10_alpha.md'")"
AFTER5="$(remote_data_sha "$TMP5")"
assert_contains "the run reports a publication_blocked deferral" \
    "DEFERRED:publication_blocked" "$OUT5"
assert_eq "origin/aitask-data did NOT advance" "$BEFORE5" "$AFTER5"
assert_eq "the raced bytes never reached the remote" \
    "$PRE5" "$(remote_blob "$TMP5" aitasks/t10_alpha.md)"
# This FAILS against a remote_ahead-gated deferral: the data branch is level
# here, so that shape would detect the mismatch and then push anyway.

# --- Test 6: negative control 1 — no seam marker, normal push -------------
echo "--- Test 6: control - seams disabled -> the same edit commits and pushes ---"
TMP6="$(setup_repo)"
(cd "$TMP6/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
BEFORE6="$(remote_data_sha "$TMP6")"
OUT6="$(run_sync "$TMP6")"
AFTER6="$(remote_data_sha "$TMP6")"
assert_not_contains "an unraced run does not defer" "DEFERRED" "$OUT6"
if [[ "$BEFORE6" != "$AFTER6" ]]; then
    assert_record_pass
else
    assert_record_fail
    echo "FAIL: the unraced commit should have been pushed"
fi

# --- Test 7: negative control 2 — seam fires, IDENTICAL bytes -------------
echo "--- Test 7: control - seam fires but writes identical bytes -> pushes ---"
TMP7="$(setup_repo)"
enable_seams "$TMP7"
(cd "$TMP7/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
BEFORE7="$(remote_data_sha "$TMP7")"
# `touch` fires the seam without changing content, so the guard must NOT trip.
OUT7="$(run_sync_seam "$TMP7" pre_group_commit \
    "touch '$TMP7/local/.aitask-data/aitasks/t10_alpha.md'")"
AFTER7="$(remote_data_sha "$TMP7")"
assert_not_contains "an identical-bytes rewrite is not a publication failure" \
    "DEFERRED:publication_blocked" "$OUT7"
if [[ "$BEFORE7" != "$AFTER7" ]]; then
    assert_record_pass
else
    assert_record_fail
    echo "FAIL: an identical-bytes seam must still push"
fi
# Proves the guard discriminates on CONTENT, not on the seam having fired — it
# fails if the seam is mis-placed or the comparison is vacuous.

# --- Test 8: the quarantine SURVIVES the process (two-run regression) -----
echo "--- Test 8: run 2, no new race, owner still live -> still withheld ---"
TMP8="$(setup_repo)"
enable_seams "$TMP8"
plant_lock "$TMP8" 10 "$(lock_yaml_live 10)"
(cd "$TMP8/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
BEFORE8="$(remote_data_sha "$TMP8")"
# Run 1: create the raced commit. The lock exists, so the sweep would normally
# skip t10 — --assume-unlocked lets it commit, and the seam then races it.
OUT8A="$(run_sync_seam "$TMP8" pre_group_commit \
    "printf 'RACED\n' >> '$TMP8/local/.aitask-data/aitasks/t10_alpha.md'" --assume-unlocked)"
assert_contains "run 1 withholds" "DEFERRED:publication_blocked" "$OUT8A"
QF8="$(quarantine_file "$TMP8")"
if [[ -s "$QF8" ]]; then assert_record_pass; else
    assert_record_fail; echo "FAIL: run 1 must persist a quarantine entry"
fi
# Run 2: NO seam, so no new race can be detected. The hold must come from the
# persisted entry alone.
OUT8B="$(run_sync "$TMP8")"
AFTER8="$(remote_data_sha "$TMP8")"
assert_contains "run 2 withholds from the PERSISTED entry" \
    "DEFERRED:publication_blocked" "$OUT8B"
assert_eq "origin/aitask-data still has not advanced" "$BEFORE8" "$AFTER8"

# --- Test 9: negative control — delete the file, run 2 pushes -------------
echo "--- Test 9: control - quarantine file removed between runs -> run 2 pushes ---"
TMP9="$(setup_repo)"
enable_seams "$TMP9"
plant_lock "$TMP9" 10 "$(lock_yaml_live 10)"
(cd "$TMP9/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
BEFORE9="$(remote_data_sha "$TMP9")"
OUT9A="$(run_sync_seam "$TMP9" pre_group_commit \
    "printf 'RACED\n' >> '$TMP9/local/.aitask-data/aitasks/t10_alpha.md'" --assume-unlocked)"
rm -f "$(quarantine_file "$TMP9")"
OUT9B="$(run_sync "$TMP9")"
AFTER9="$(remote_data_sha "$TMP9")"
if [[ "$BEFORE9" != "$AFTER9" ]]; then
    assert_record_pass
else
    assert_record_fail
    echo "FAIL: without the persisted entry run 2 must push (else Test 8 proves nothing)"
fi
# Without this control, Test 8 would also pass if something incidental happened
# to block the push.

# --- Test 10: a CLEAN worktree alone must NOT release --------------------
echo "--- Test 10: clean worktree + LIVE lock -> STILL held ---"
# After the race the path is clean BY CONSTRUCTION: commit -o committed the
# worktree bytes. A cleanliness-only release clause would fire on run 1.
TMP10="$(setup_repo)"
enable_seams "$TMP10"
plant_lock "$TMP10" 10 "$(lock_yaml_live 10)"
(cd "$TMP10/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
BEFORE10="$(remote_data_sha "$TMP10")"
OUT10A="$(run_sync_seam "$TMP10" pre_group_commit \
    "printf 'RACED\n' >> '$TMP10/local/.aitask-data/aitasks/t10_alpha.md'" --assume-unlocked)"
DIRTY10="$(git -C "$TMP10/local/.aitask-data" status --porcelain -- aitasks/t10_alpha.md)"
assert_eq "the raced path really is clean after the commit" "" "$DIRTY10"
OUT10B="$(run_sync "$TMP10")"
assert_contains "yet the entry is STILL held, because the holder is live" \
    "DEFERRED:publication_blocked" "$OUT10B"
assert_eq "and nothing was published" "$BEFORE10" "$(remote_data_sha "$TMP10")"
# FAILS against a cleanliness-only release clause.

# --- Test 11: release clause 2 — the owner's lock goes away --------------
echo "--- Test 11: holder gone + path settled -> released, and the run pushes ---"
TMP11="$(setup_repo)"
enable_seams "$TMP11"
plant_lock "$TMP11" 10 "$(lock_yaml_live 10)"
(cd "$TMP11/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
BEFORE11="$(remote_data_sha "$TMP11")"
OUT11A="$(run_sync_seam "$TMP11" pre_group_commit \
    "printf 'RACED\n' >> '$TMP11/local/.aitask-data/aitasks/t10_alpha.md'" --assume-unlocked)"
# The owning session ends: replace the live anchor with a provably dead one.
plant_lock "$TMP11" 10 "$(lock_yaml_dead 10)"
OUT11B="$(run_sync "$TMP11")"
AFTER11="$(remote_data_sha "$TMP11")"
assert_not_contains "the entry is released once the holder is gone" \
    "DEFERRED:publication_blocked" "$OUT11B"
if [[ "$BEFORE11" != "$AFTER11" ]]; then
    assert_record_pass
else
    assert_record_fail
    echo "FAIL: after release the withheld commit must publish"
fi

# --- Test 12: an unreadable lock branch must NOT release ----------------
echo "--- Test 12: LOCKS_UNAVAILABLE -> still held ---"
TMP12="$(setup_repo)"
enable_seams "$TMP12"
plant_lock "$TMP12" 10 "$(lock_yaml_live 10)"
(cd "$TMP12/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
OUT12A="$(run_sync_seam "$TMP12" pre_group_commit \
    "printf 'RACED\n' >> '$TMP12/local/.aitask-data/aitasks/t10_alpha.md'" --assume-unlocked)"
BEFORE12="$(remote_data_sha "$TMP12")"
(cd "$TMP12/local" && git remote set-url origin "$TMP12/gone.git")
OUT12B="$(run_sync "$TMP12")"
# An unreachable origin makes do_fetch report NO_NETWORK and exit before the
# publication guard is even consulted — so assert the SAFETY property, which is
# what actually matters: the entry survives and nothing is published.
QF12="$(quarantine_file "$TMP12")"
assert_contains "the entry is NOT released while the lock branch is unreadable" \
    "aitasks/t10_alpha.md" "$(cat "$QF12" 2>/dev/null)"
(cd "$TMP12/local" && git remote set-url origin "$TMP12/remote.git")
assert_eq "and nothing reached the remote" "$BEFORE12" "$(remote_data_sha "$TMP12")"

# --- Test 13: age NEVER releases ----------------------------------------
echo "--- Test 13: past the warn age with a LIVE holder -> still held, report escalates ---"
TMP13="$(setup_repo)"
enable_seams "$TMP13"
plant_lock "$TMP13" 10 "$(lock_yaml_live 10)"
(cd "$TMP13/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
BEFORE13="$(remote_data_sha "$TMP13")"
OUT13A="$(run_sync_seam "$TMP13" pre_group_commit \
    "printf 'RACED\n' >> '$TMP13/local/.aitask-data/aitasks/t10_alpha.md'" --assume-unlocked)"
QF13="$(quarantine_file "$TMP13")"
# Backdate the entry well past any warn age.
awk -F'|' 'BEGIN{OFS="|"} {$4=1; print}' "$QF13" > "$QF13.b" && mv "$QF13.b" "$QF13"
OUT13B="$(
    cd "$TMP13/local"
    PATH="$PWD/bin:$PATH" TEST_HOSTNAME=testhost AITASKS_LOCK_DIR="$TMP13/locks" \
    AIT_SYNC_QUARANTINE_WARN_AGE=1 \
        ./.aitask-scripts/aitask_sync.sh --batch 2>"$TMP13/sync_stderr"
)"
assert_contains "an expired entry with a live holder is STILL held" \
    "DEFERRED:publication_blocked" "$OUT13B"
assert_eq "and still nothing is published" "$BEFORE13" "$(remote_data_sha "$TMP13")"
assert_contains "the report escalates" "QUARANTINE HELD" "$(cat "$TMP13/sync_stderr")"
assert_contains "and names the only escape" "--release-quarantine" "$(cat "$TMP13/sync_stderr")"
# FAILS against an age-based release, which would publish exactly the raced
# content the hold exists to withhold.

# --- Test 14: --release-quarantine is the operator escape ---------------
echo "--- Test 14: --release-quarantine -> published deliberately ---"
TMP14="$(setup_repo)"
enable_seams "$TMP14"
plant_lock "$TMP14" 10 "$(lock_yaml_live 10)"
(cd "$TMP14/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
BEFORE14="$(remote_data_sha "$TMP14")"
OUT14A="$(run_sync_seam "$TMP14" pre_group_commit \
    "printf 'RACED\n' >> '$TMP14/local/.aitask-data/aitasks/t10_alpha.md'" --assume-unlocked)"
OUT14B="$(run_sync "$TMP14" --release-quarantine)"
AFTER14="$(remote_data_sha "$TMP14")"
if [[ "$BEFORE14" != "$AFTER14" ]]; then
    assert_record_pass
else
    assert_record_fail
    echo "FAIL: --release-quarantine must publish the withheld commit"
fi

# --- Test 15: a wedged worktree defers instead of dying silently --------
echo "--- Test 15: wedged data worktree -> DEFERRED:worktree_wedged, never empty stdout ---"
TMP15="$(setup_repo)"
(cd "$TMP15/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
mkdir -p "$TMP15/local/.git/worktrees/-aitask-data/rebase-merge"
OUT15="$(run_sync "$TMP15")"
assert_contains "the wedged state is reported as a deferral" \
    "DEFERRED:worktree_wedged" "$OUT15"
# task_git add/reset/commit all die() mid-rebase, and die is `exit 1` with no
# batch_out — which every consumer reads as `ERROR: empty output`.
if [[ -n "$OUT15" ]]; then assert_record_pass; else
    assert_record_fail; echo "FAIL: stdout must never be empty"
fi
rm -rf "$TMP15/local/.git/worktrees/-aitask-data/rebase-merge"

# --- Test 16: a malformed lock blob must not abort the sweep ------------
echo "--- Test 16: unparseable lock record -> still a recognised token ---"
TMP16="$(setup_repo)"
plant_lock "$TMP16" 10 "this is not yaml at all"
(cd "$TMP16/local" && printf 'edit20\n' >> .aitask-data/aitasks/t20_beta.md)
OUT16="$(run_sync "$TMP16")"
if [[ -n "$OUT16" ]]; then assert_record_pass; else
    assert_record_fail; echo "FAIL: a malformed lock blob must not produce empty stdout"
fi
assert_not_contains "and it is not reported as an error" "ERROR:" "$OUT16"

# --- Test 17: CAS state transition absent -> present --------------------
echo "--- Test 17: a deleted file recreated before the commit -> group skipped ---"
TMP17="$(setup_repo)"
enable_seams "$TMP17"
(cd "$TMP17/local" && rm .aitask-data/aitasks/t10_alpha.md)
# Recreating it flips the recorded state absent -> present, which a hash-only
# check cannot see at all.
OUT17="$(run_sync_seam "$TMP17" pre_commit_phase \
    "printf 'BACK\n' > '$TMP17/local/.aitask-data/aitasks/t10_alpha.md'")"
assert_contains "the state transition is caught" \
    "changed after classification" "$(cat "$TMP17/sync_stderr")"
assert_not_contains "and the group is not committed" \
    "Auto-commit t10" "$(data_log "$TMP17")"

# --- Test 18: an ambiguous cross-task rename is never attributed --------
echo "--- Test 18: cross-task rename -> skipped and reported ---"
TMP18="$(setup_repo)"
(cd "$TMP18/local" \
    && git -C .aitask-data mv aitasks/t10_alpha.md aitasks/t20_stolen.md 2>/dev/null)
OUT18="$(run_sync "$TMP18")"
assert_contains "the rename is reported as ambiguous" \
    "ambiguous cross-task rename" "$(cat "$TMP18/sync_stderr")"
assert_not_contains "and neither task claims it" \
    "Auto-commit t10" "$(data_log "$TMP18")"
assert_not_contains "neither task claims it (t20)" \
    "Auto-commit t20" "$(data_log "$TMP18")"

# --- Test 18b: the quarantine record round-trips a hostile path ---------
echo "--- Test 18b: a path with | and % survives the persisted record ---"
# The record is `<path>|<blob>|<task>|<epoch>`, one per line. A `|` or a newline
# in the path would corrupt it, and a mangled path is then checked against the
# WRONG file — which can release a hold that should stand.
TMP18B="$(setup_repo)"
enable_seams "$TMP18B"
plant_lock "$TMP18B" 62 "$(lock_yaml_live 62)"
HOSTILE="aitasks/t62_pipe|and%pct.md"
printf -- '---\nstatus: Ready\n---\nH\n' > "$TMP18B/local/.aitask-data/$HOSTILE"
BEFORE18B="$(remote_data_sha "$TMP18B")"
OUT18BA="$(run_sync_seam "$TMP18B" pre_group_commit \
    "printf 'RACED\n' >> '$TMP18B/local/.aitask-data/$HOSTILE'" --assume-unlocked)"
assert_contains "run 1 withholds the hostile-named path" \
    "DEFERRED:publication_blocked" "$OUT18BA"
QF18B="$(quarantine_file "$TMP18B")"
assert_contains "the record stores the path ENCODED, so the | cannot split it" \
    "t62_pipe%7Cand%25pct.md" "$(cat "$QF18B" 2>/dev/null)"
LINES18B="$(wc -l < "$QF18B")"
assert_eq "exactly one record was written" "1" "$LINES18B"
# Run 2 proves the DECODE side: the hold can only stand if the path read back
# out of the record resolves to the same file.
OUT18BB="$(run_sync "$TMP18B")"
assert_contains "run 2 still holds it, so the path decoded correctly" \
    "DEFERRED:publication_blocked" "$OUT18BB"
assert_eq "and nothing was published" "$BEFORE18B" "$(remote_data_sha "$TMP18B")"

# --- Test 19/20: the push-retry race ------------------------------------
# Injected through a documented git seam, not a production hook: a `pre-push`
# hook that, on its FIRST invocation only, pushes a commit from a sibling clone
# to the same remote. Our push is then genuinely rejected exactly once, which is
# what deterministically enters do_push's retry path.
install_racing_pre_push() {
    local tmpdir="$1"
    mkdir -p "$tmpdir/local/.git/hooks"
    cat > "$tmpdir/local/.git/hooks/pre-push" <<HOOKEOF
#!/usr/bin/env bash
# git EXPORTS GIT_DIR (and friends) into hooks. Left set, the clone below fails,
# the \`cd\` into it fails too, and the sibling-clone edits then land in the
# hook's OWN cwd — this repo's data worktree — surfacing much later as an
# inexplicable "cannot pull with rebase: You have unstaged changes".
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX GIT_COMMON_DIR
marker="$tmpdir/prepush_fired"
[ -e "\$marker" ] && exit 0
touch "\$marker"
rm -rf "$tmpdir/racer"
git clone -q --branch aitask-data "$tmpdir/remote.git" "$tmpdir/racer" >/dev/null 2>&1 || exit 0
(
  cd "$tmpdir/racer" || exit 0
  git config user.email racer@test.com
  git config user.name Racer
  git config commit.gpgsign false
  printf 'racer\n' >> aitasks/t30_gamma.md
  git add -A && git commit -q -m "racer: advance"
  git push -q origin aitask-data
) >/dev/null 2>&1
exit 0
HOOKEOF
    chmod +x "$tmpdir/local/.git/hooks/pre-push"
}

echo "--- Test 19: push rejected mid-run + protected file -> DEFERRED, not ERROR:push_failed ---"
TMP19="$(setup_repo)"
plant_lock "$TMP19" 10 "$(lock_yaml_live 10)"
(cd "$TMP19/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md \
                   && printf 'edit20\n' >> .aitask-data/aitasks/t20_beta.md)
install_racing_pre_push "$TMP19"
OUT19="$(run_sync "$TMP19")"
assert_not_contains "the protected file is not blamed on the push" \
    "ERROR:push_failed" "$OUT19"
assert_contains "the run defers instead" "DEFERRED:protected_dirty" "$OUT19"

echo "--- Test 20: control - same race, nothing protected -> rebase+retry succeeds ---"
TMP20="$(setup_repo)"
(cd "$TMP20/local" && printf 'edit20\n' >> .aitask-data/aitasks/t20_beta.md)
install_racing_pre_push "$TMP20"
OUT20="$(run_sync "$TMP20")"
assert_not_contains "an unprotected run recovers rather than failing" \
    "ERROR:push_failed" "$OUT20"
assert_not_contains "and it does not defer" "DEFERRED" "$OUT20"
RACED20="$(remote_blob "$TMP20" aitasks/t20_beta.md)"
assert_contains "our commit reached the remote after the retry" "edit20" "$RACED20"

# --- Tests 21-26: commit-on-behalf (t1725_3) -------------------------------
#
# --commit-for-task lets a user release their OWN parked session's edits rather
# than waiting on a pane they have walked away from. Every one of these has a
# negative control, because a flag that committed in every case would satisfy
# the positive tests just as well.

echo "--- Test 21: --commit-for-task on your OWN verified lock -> committed ---"
TMP21="$(setup_repo)"
plant_lock "$TMP21" 10 "$(lock_yaml_live 10)"
set_userconfig_email "$TMP21" other@x.com     # matches the lock's locked_by -> `self`
(cd "$TMP21/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
OUT21="$(run_sync "$TMP21" --commit-for-task 10)"
assert_contains "the group is committed under t10's own message" \
    "ait: Auto-commit t10 task data before sync" "$(data_log "$TMP21")"
assert_contains "the run publishes" "PUSHED" "$OUT21"
assert_contains "and says plainly that a live session's edits were taken" \
    "its uncommitted edits were committed as they stand now" "$(sync_err "$TMP21")"

echo "--- Test 22: control - same lock, no flag -> still protected ---"
TMP22="$(setup_repo)"
plant_lock "$TMP22" 10 "$(lock_yaml_live 10)"
set_userconfig_email "$TMP22" other@x.com
(cd "$TMP22/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
run_sync "$TMP22" >/dev/null
assert_not_contains "without the flag the file is left for its session" \
    "Auto-commit t10" "$(data_log "$TMP22")"

echo "--- Test 23: control - the lock is someone ELSE's -> refused ---"
TMP23="$(setup_repo)"
plant_lock "$TMP23" 10 "$(lock_yaml_live 10)"
set_userconfig_email "$TMP23" someone-else@x.com    # != locked_by -> `other`
(cd "$TMP23/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
run_sync "$TMP23" --commit-for-task 10 >/dev/null
assert_not_contains "another user's live lock is never committed on behalf" \
    "Auto-commit t10" "$(data_log "$TMP23")"
assert_contains "and the refusal names the class" \
    "refused: the lock is other" "$(sync_err "$TMP23")"

echo "--- Test 24: control - identity unverifiable -> refused ---"
# No userconfig email at all. An absent local email must NOT compare equal to an
# absent lock email, which would make every anonymous lock look like your own.
TMP24="$(setup_repo)"
plant_lock "$TMP24" 10 "$(lock_yaml_live 10)"
(cd "$TMP24/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
run_sync "$TMP24" --commit-for-task 10 >/dev/null
assert_not_contains "an unverifiable identity is never treated as your own" \
    "Auto-commit t10" "$(data_log "$TMP24")"
assert_contains "and the refusal says so" \
    "refused: the lock is unverified" "$(sync_err "$TMP24")"

echo "--- Test 25: --expect-path matching set -> committed; a comma path round-trips ---"
# A comma is a legal character in a git path and _pct_encode leaves it alone,
# which is exactly why --expect-path is repeatable rather than a CSV.
TMP25="$(setup_repo)"
plant_lock "$TMP25" 10 "$(lock_yaml_live 10)"
set_userconfig_email "$TMP25" other@x.com
(cd "$TMP25/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md \
                   && mkdir -p .aitask-data/aiplans \
                   && printf 'x\n' > ".aitask-data/aiplans/p10_a,b.md")
run_sync "$TMP25" --commit-for-task 10 \
    --expect-path "aitasks/t10_alpha.md" --expect-path "aiplans/p10_a,b.md" >/dev/null
COMMITTED25="$(commit_files_for "$TMP25" "Auto-commit t10")"
assert_contains "the declared set is committed" "t10_alpha.md" "$COMMITTED25"
assert_contains "including the path containing a comma" "p10_a,b.md" "$COMMITTED25"

echo "--- Test 26: control - the group grew after confirmation -> nothing committed ---"
TMP26="$(setup_repo)"
plant_lock "$TMP26" 10 "$(lock_yaml_live 10)"
set_userconfig_email "$TMP26" other@x.com
(cd "$TMP26/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md \
                   && printf 'surprise\n' > .aitask-data/aitasks/t10_extra.md)
OUT26="$(run_sync "$TMP26" --commit-for-task 10 --expect-path "aitasks/t10_alpha.md")"
assert_not_contains "a set that grew since confirmation commits NOTHING" \
    "Auto-commit t10" "$(data_log "$TMP26")"
assert_contains "and the record names the delta" \
    "the dirty set changed after it was confirmed" "$(sync_err "$TMP26")"

echo "--- Test 27: --require-waiting with no probe available -> fails closed ---"
# t1725_4 owns the probe; until it lands this flag must refuse, never assume.
TMP27="$(setup_repo)"
plant_lock "$TMP27" 10 "$(lock_yaml_live 10)"
set_userconfig_email "$TMP27" other@x.com
(cd "$TMP27/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
run_sync "$TMP27" --commit-for-task 10 --require-waiting >/dev/null
assert_not_contains "no probe means NOT waiting, so nothing is committed" \
    "Auto-commit t10" "$(data_log "$TMP27")"
assert_contains "and the record reports the observed state" \
    "is not parked on a prompt (observed: unresolvable)" "$(sync_err "$TMP27")"

echo ""

# --- Tests 28-31: the push-retry re-gate, and record/status coupling -------

echo "--- Test 28: the retry fetch fails -> NO_NETWORK, not a verdict from stale @{u} ---"
# do_push's retry used to swallow the fetch failure with `|| true`. Recomputing
# the gate on a stale @{u} can read remote_ahead == 0, conclude "not blocked",
# and act on a world it never saw -- surfacing later as a generic push/rebase
# error rather than the true outcome.
TMP28="$(setup_repo)"
plant_lock "$TMP28" 10 "$(lock_yaml_live 10)"
(cd "$TMP28/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md \
                   && printf 'edit20\n' >> .aitask-data/aitasks/t20_beta.md)
# The remote must break BETWEEN the two fetches, which means from inside the
# pre-push hook. Breaking it before the run instead makes the step-5 do_fetch
# fail and emit NO_NETWORK on its own -- the assertions below would then pass
# without do_push's retry path ever executing. (Measured: it did.)
mkdir -p "$TMP28/local/.git/hooks"
cat > "$TMP28/local/.git/hooks/pre-push" <<HOOK28
#!/usr/bin/env bash
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX GIT_COMMON_DIR
[ -e "$TMP28/prepush_fired" ] && exit 0
touch "$TMP28/prepush_fired"
# 1. advance the remote so THIS push is rejected
rm -rf "$TMP28/racer"
git clone -q --branch aitask-data "$TMP28/remote.git" "$TMP28/racer" >/dev/null 2>&1 || exit 0
(
  cd "$TMP28/racer" || exit 0
  git config user.email racer@test.com; git config user.name Racer
  git config commit.gpgsign false
  printf 'racer\\n' >> aitasks/t30_gamma.md
  git add -A && git commit -q -m "racer: advance"
  git push -q origin aitask-data
) >/dev/null 2>&1
# 2. then take the remote away, so the RETRY fetch is what fails
git -C "$TMP28/local/.aitask-data" remote set-url origin "$TMP28/no_such_remote.git"
exit 0
HOOK28
chmod +x "$TMP28/local/.git/hooks/pre-push"
OUT28="$(run_sync "$TMP28")"
assert_contains "an unreachable retry fetch reports the network" "NO_NETWORK" "$OUT28"
assert_not_contains "and not a rebase error" "ERROR:push_rebase_failed" "$OUT28"
assert_not_contains "and not a push error" "ERROR:push_failed" "$OUT28"

echo "--- Test 29: control - the retry fetch succeeds -> the normal outcome ---"
# Test 19/20 already pin both retry outcomes; this is the paired control for 28
# specifically, so a change that made every retry report NO_NETWORK would fail.
TMP29="$(setup_repo)"
(cd "$TMP29/local" && printf 'edit20\n' >> .aitask-data/aitasks/t20_beta.md)
install_racing_pre_push "$TMP29"
OUT29="$(run_sync "$TMP29")"
assert_not_contains "a reachable remote never reports NO_NETWORK" "NO_NETWORK" "$OUT29"

echo "--- Test 30: a deferring run leaves no temp file behind ---"
# The incoming-set scratch file is allocated on a path that exits from a nested
# function. This script has no trap at all, so the allocation, the read and the
# rm must sit in one exit-free window -- which is what _load_incoming is for.
TMP30="$(setup_repo)"
mkdir -p "$TMP30/tmpdir_probe"
plant_lock "$TMP30" 10 "$(lock_yaml_live 10)"
(cd "$TMP30/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md \
                   && printf 'edit20\n' >> .aitask-data/aitasks/t20_beta.md)
advance_remote "$TMP30"
(
    cd "$TMP30/local"
    export PATH="$PWD/bin:$PATH" TEST_HOSTNAME=testhost
    export AITASKS_LOCK_DIR="$TMP30/locks" TMPDIR="$TMP30/tmpdir_probe"
    ./.aitask-scripts/aitask_sync.sh --batch >/dev/null 2>&1
)
LEFTOVER30="$(find "$TMP30/tmpdir_probe" -type f 2>/dev/null | wc -l)"
assert_eq "the deferring run left no scratch files" "0" "$LEFTOVER30"

echo "--- Test 31: DEFERRED_FILE records appear only WITH a status line ---"
# Four tests in this file assert not_contains "DEFERRED" over whole stdout, and
# DEFERRED_FILE: contains that substring. So records must be bound to the status
# line rather than emitted whenever the record set is non-empty -- otherwise a
# run that HAS protected files and correctly does NOT defer would start
# emitting them. Test 3's shape is exactly that run.
TMP31="$(setup_repo)"
plant_lock "$TMP31" 10 "$(lock_yaml_live 10)"
(cd "$TMP31/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md \
                   && printf 'edit20\n' >> .aitask-data/aitasks/t20_beta.md)
OUT31="$(run_sync "$TMP31")"          # remote NOT ahead -> records exist, no deferral
assert_not_contains "a non-deferring run emits no records" "DEFERRED_FILE:" "$OUT31"

# And in a run that DOES defer, the count in the status line equals the number
# of records that follow it.
TMP31B="$(setup_repo)"
plant_lock "$TMP31B" 10 "$(lock_yaml_live 10)"
(cd "$TMP31B/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md \
                    && printf 'more10\n' > .aitask-data/aitasks/t10_extra.md \
                    && printf 'edit20\n' >> .aitask-data/aitasks/t20_beta.md)
advance_remote "$TMP31B"
OUT31B="$(run_sync "$TMP31B")"
STATUS_N="$(printf '%s\n' "$OUT31B" | sed -n 's/^DEFERRED:protected_dirty:\([0-9]*\) .*/\1/p')"
RECORD_N="$(printf '%s\n' "$OUT31B" | grep -c '^DEFERRED_FILE:')"
assert_contains "the deferral names both of t10's files" "2" "$STATUS_N"
assert_eq "the status count equals the number of records" "$STATUS_N" "$RECORD_N"
assert_eq "the status line is still the FIRST line" \
    "DEFERRED" "$(printf '%s\n' "$OUT31B" | head -n1 | cut -d: -f1)"

echo ""

echo "--- Test 32: a refused commit-on-behalf leaves NOTHING staged ---"
# Both commit-on-behalf guards abandon the group with `return 0`. If they ran
# after the staging loop, an untracked path this run had already `git add`-ed
# would stay in the SHARED index -- where it blocks the rebase exactly like an
# unstaged one, and where the next session would carry it into an unrelated
# commit. The guards therefore run before anything is staged; this pins it.
TMP32="$(setup_repo)"
plant_lock "$TMP32" 10 "$(lock_yaml_live 10)"
set_userconfig_email "$TMP32" other@x.com
(cd "$TMP32/local" && mkdir -p .aitask-data/aiplans \
                   && printf 'draft\n' > .aitask-data/aiplans/p10_new.md \
                   && printf 'more\n' > .aitask-data/aitasks/t10_extra.md)
# --expect-path names only one of the two, so the scope check refuses the group.
run_sync "$TMP32" --commit-for-task 10 --expect-path "aiplans/p10_new.md" >/dev/null
STAGED32="$(cd "$TMP32/local" && git -C .aitask-data diff --cached --name-only)"
assert_eq "the refused group left the index untouched" "" "$STAGED32"
assert_not_contains "and committed nothing" "Auto-commit t10" "$(data_log "$TMP32")"

echo ""

echo "--- Test 33: the wire row names the holder class, all four directions ---"
# The holder class is what decides the wording a TUI shows and whether
# commit-on-behalf is even offered, so each class needs its own row asserted.
# `self` is deliberately the hardest to reach: same verified host AND the same
# email on both sides.
wire_row_for() {                      # <tmpdir> -> the DEFERRED_FILE row for t10
    printf '%s\n' "$2" | grep -m1 '^DEFERRED_FILE:.*|10|'
}

# self: lock host == this host, lock email == userconfig email.
TMP33="$(setup_repo)"
plant_lock "$TMP33" 10 "$(lock_yaml_live 10)"
set_userconfig_email "$TMP33" other@x.com
(cd "$TMP33/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md \
                   && printf 'edit20\n' >> .aitask-data/aitasks/t20_beta.md)
advance_remote "$TMP33"
ROW_SELF="$(wire_row_for "$TMP33" "$(run_sync "$TMP33")")"
assert_contains "self: the row carries the class" "|tracked|self|" "$ROW_SELF"
assert_contains "self: and the encoded email" "other@x.com" "$ROW_SELF"
assert_contains "self: and the host" "testhost" "$ROW_SELF"
assert_contains "self: and the action offers commit-on-behalf" \
    "--commit-for-task 10" "$ROW_SELF"

# other: same verified host, a different non-empty email.
TMP33B="$(setup_repo)"
plant_lock "$TMP33B" 10 "$(lock_yaml_live 10)"
set_userconfig_email "$TMP33B" someone-else@x.com
(cd "$TMP33B/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md \
                    && printf 'edit20\n' >> .aitask-data/aitasks/t20_beta.md)
advance_remote "$TMP33B"
ROW_OTHER="$(wire_row_for "$TMP33B" "$(run_sync "$TMP33B")")"
assert_contains "other: the row carries the class" "|tracked|other|" "$ROW_OTHER"
assert_contains "other: and never offers commit-on-behalf" \
    "left for that session" "$ROW_OTHER"

# remote: a different host entirely -- liveness is not decidable from here.
TMP33C="$(setup_repo)"
plant_lock "$TMP33C" 10 "$(lock_yaml_live 10 otherhost)"
set_userconfig_email "$TMP33C" other@x.com
(cd "$TMP33C/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md \
                    && printf 'edit20\n' >> .aitask-data/aitasks/t20_beta.md)
advance_remote "$TMP33C"
ROW_REMOTE="$(wire_row_for "$TMP33C" "$(run_sync "$TMP33C")")"
assert_contains "remote: the row carries the class" "|tracked|remote|" "$ROW_REMOTE"
assert_contains "remote: and names the host it is held on" "otherhost" "$ROW_REMOTE"

# unverified: no userconfig email. An ABSENT local email must never compare
# equal to an absent lock email -- that would make every anonymous lock look
# like the user's own and eligible for --commit-for-task.
TMP33D="$(setup_repo)"
plant_lock "$TMP33D" 10 "$(lock_yaml_live 10)"
(cd "$TMP33D/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md \
                    && printf 'edit20\n' >> .aitask-data/aitasks/t20_beta.md)
advance_remote "$TMP33D"
ROW_UNVER="$(wire_row_for "$TMP33D" "$(run_sync "$TMP33D")")"
assert_contains "unverified: the row carries the class" "|tracked|unverified|" "$ROW_UNVER"
assert_not_contains "unverified: and is never called self" "|self|" "$ROW_UNVER"

echo ""

echo "--- Test 34: --commit-for-task bypasses NO other guard ---"
# The override changes exactly one thing: the holder verdict. It must not become
# a way to skip the 5a.4 publication guard, or "commit my own parked session's
# work" would quietly turn into "publish content that was rewritten underneath
# the commit". Same seam, same expected outcome, with the flag as without it.
TMP34="$(setup_repo)"
enable_seams "$TMP34"
plant_lock "$TMP34" 10 "$(lock_yaml_live 10)"
set_userconfig_email "$TMP34" other@x.com
(cd "$TMP34/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
BEFORE34="$(remote_data_sha "$TMP34")"
OUT34="$(run_sync_seam "$TMP34" pre_group_commit \
    "printf 'raced\\n' >> $TMP34/local/.aitask-data/aitasks/t10_alpha.md" \
    --commit-for-task 10)"
AFTER34="$(remote_data_sha "$TMP34")"
assert_contains "a file raced during the commit is still withheld" \
    "DEFERRED:publication_blocked" "$OUT34"
assert_eq "and nothing reached the remote" "$BEFORE34" "$AFTER34"

echo "--- Test 35: control - same flag, no race -> the group does publish ---"
# Without this, Test 34 would also pass against a build where
# --commit-for-task never committed anything at all.
TMP35="$(setup_repo)"
enable_seams "$TMP35"
plant_lock "$TMP35" 10 "$(lock_yaml_live 10)"
set_userconfig_email "$TMP35" other@x.com
(cd "$TMP35/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
BEFORE35="$(remote_data_sha "$TMP35")"
OUT35="$(run_sync_seam "$TMP35" pre_group_commit "true" --commit-for-task 10)"
AFTER35="$(remote_data_sha "$TMP35")"
assert_not_contains "an unraced commit-on-behalf is not withheld" \
    "DEFERRED:publication_blocked" "$OUT35"
assert_contains "the group is committed" \
    "ait: Auto-commit t10 task data before sync" "$(data_log "$TMP35")"
if [[ "$BEFORE35" != "$AFTER35" ]]; then
    assert_record_pass
else
    assert_record_fail
    echo "FAIL: the commit-on-behalf should have reached the remote"
fi

echo ""

echo "--- Test 36: an unreadable lock branch reports holder=unverified, never none ---"
# `none` is a CLOSED value meaning "unlocked". Emitting it here would put a
# false fact on a record that advertises itself as the complete snapshot: this
# branch exists precisely because the lock branch could NOT be read, so whether
# the task is held is unknown. A consumer reading holder=none could reasonably
# offer "nobody holds this, commit it".
TMP36="$(setup_repo)"
(cd "$TMP36/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md \
                   && printf '#!/usr/bin/env bash\nexit 1\n' > .aitask-scripts/aitask_lock.sh)
# The incoming commit touches the same path, so the gate blocks and a record is
# actually emitted (with nothing committable, local_ahead stays 0 and the run
# would otherwise fast-forward without deferring at all).
rm -rf "$TMP36/pc2"
git clone -q --branch aitask-data "$TMP36/remote.git" "$TMP36/pc2" 2>/dev/null
(
    cd "$TMP36/pc2"
    git config user.email pc2@test.com; git config user.name PC2
    git config commit.gpgsign false
    printf 'theirs\n' >> aitasks/t10_alpha.md
    git add -A && git commit -q -m "pc2: touch t10"
    git push -q origin aitask-data 2>/dev/null
) >/dev/null 2>&1
(cd "$TMP36/local" && git -C .aitask-data fetch -q origin 2>/dev/null)
OUT36="$(run_sync "$TMP36")"
ROW36="$(printf '%s\n' "$OUT36" | grep -m1 '^DEFERRED_FILE:locks_unavailable')"
assert_contains "an unreadable snapshot yields unverified" "|unverified|" "$ROW36"
assert_not_contains "and never claims the task is unlocked" "|none|" "$ROW36"

# Parsed, not just pattern-matched: the field has to survive the real consumer.
HOLDER36="$(printf '%s' "$OUT36" | python3 -c '
import sys
sys.path.insert(0, "'"$PROJECT_DIR"'/.aitask-scripts/lib")
from sync_action_runner import parse_sync_output
r = parse_sync_output(sys.stdin.read())
print(r.deferred_files[0].holder if r.deferred_files else "NO_RECORDS")
')"
assert_eq "the parsed record carries unverified" "unverified" "$HOLDER36"

echo "--- Test 37: --expect-path refuses an ambiguous multi-task invocation ---"
# --expect-path states ONE task's dirty set and _commit_group compares it to
# each group in turn, so with two ids each task sees the other's paths as
# missing and BOTH are refused -- the combined form would silently commit
# nothing while appearing to work.
TMP37="$(setup_repo)"
plant_lock "$TMP37" 10 "$(lock_yaml_live 10)"
plant_lock "$TMP37" 20 "$(lock_yaml_live 20)"
set_userconfig_email "$TMP37" other@x.com
(cd "$TMP37/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md \
                   && printf 'edit20\n' >> .aitask-data/aitasks/t20_beta.md)
run_sync "$TMP37" --commit-for-task 10,20 \
    --expect-path "aitasks/t10_alpha.md" --expect-path "aitasks/t20_beta.md" >/dev/null
assert_contains "the ambiguous combination is refused up front" \
    "cannot be combined with more than one --commit-for-task id" "$(sync_err "$TMP37")"
assert_not_contains "and nothing is committed" "Auto-commit t" "$(data_log "$TMP37")"

echo "--- Test 38: control - one task at a time still commits with --expect-path ---"
# Without this, Test 37 would also pass against a build where --expect-path
# refused everything.
TMP38="$(setup_repo)"
plant_lock "$TMP38" 10 "$(lock_yaml_live 10)"
set_userconfig_email "$TMP38" other@x.com
(cd "$TMP38/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
run_sync "$TMP38" --commit-for-task 10 --expect-path "aitasks/t10_alpha.md" >/dev/null
assert_contains "a single-task invocation is unaffected" \
    "ait: Auto-commit t10 task data before sync" "$(data_log "$TMP38")"

echo "--- Test 39: the two flags are refused without --commit-for-task ---"
TMP39="$(setup_repo)"
(cd "$TMP39/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
run_sync "$TMP39" --expect-path "aitasks/t10_alpha.md" >/dev/null
assert_contains "--expect-path alone is refused" \
    "only meaningful with --commit-for-task" "$(sync_err "$TMP39")"
run_sync "$TMP39" --require-waiting >/dev/null
assert_contains "--require-waiting alone is refused" \
    "only meaningful with --commit-for-task" "$(sync_err "$TMP39")"

echo ""

echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -eq 0 ]]; then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "SOME TESTS FAILED"
    exit 1
fi
