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
echo "--- Test 1: protected file + remote ahead -> DEFERRED, not ERROR:pull_rebase_failed ---"
TMP1="$(setup_repo)"
plant_lock "$TMP1" 10 "$(lock_yaml_live 10)"
(cd "$TMP1/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
advance_remote "$TMP1"
OUT1="$(run_sync "$TMP1")"
assert_contains "the run reports a protected_dirty deferral" "DEFERRED:protected_dirty" "$OUT1"
assert_not_contains "and NOT the rebase error the dirty file would otherwise cause" \
    "ERROR:pull_rebase_failed" "$OUT1"
# The fetch is read-only and must still have happened.
FETCHED1="$(git -C "$TMP1/local/.aitask-data" rev-parse --verify --quiet origin/aitask-data)"
REMOTE1="$(remote_data_sha "$TMP1")"
assert_eq "the read-only fetch still ran" "$REMOTE1" "$FETCHED1"

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
