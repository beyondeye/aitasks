#!/usr/bin/env bash
# test_sync_auto_commit_scoping.sh - aitask_sync.sh's pre-sync sweep (t1599_3).
#
# Run: bash tests/test_sync_auto_commit_scoping.sh
#
# Why this file exists
# --------------------
# `auto_commit` used to `add aitasks/ aiplans/` and then commit the WHOLE index,
# so any file another session was mid-edit on was swept into a commit whose
# message named a different task. Measured on the live data branch: 18 of 66
# sync auto-commits carried more than two task/plan files, and
# aitasks/metadata/stats_config.json has three of its four commits attributed to
# unrelated tasks.
#
# The sweep now groups by owning task, commits each group path-scoped, and
# refuses to commit anything it cannot vouch for. The bystander and ownerless
# assertions below are written to FAIL against the pre-fix `add aitasks/
# aiplans/` + bare commit.

set -uo pipefail

TEST_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

. "$PROJECT_DIR/tests/lib/asserts.sh"

. "$PROJECT_DIR/tests/lib/sync_fixture.sh"

# ==========================================================================
echo "=== aitask_sync.sh auto-commit scoping (t1599_3) ==="
echo ""

# --- Test 1: per-task grouping — one commit per owning task ---------------
echo "--- Test 1: dirty files are committed per owning task, not in one lump ---"
TMP1="$(setup_repo)"
(cd "$TMP1/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md \
                  && printf 'edit20\n' >> .aitask-data/aitasks/t20_beta.md)
OUT1="$(run_sync "$TMP1")"
LOG1="$(data_log "$TMP1")"

assert_contains "t10 gets its own commit naming t10" \
    "ait: Auto-commit t10 task data before sync" "$LOG1"
assert_contains "t20 gets its own commit naming t20" \
    "ait: Auto-commit t20 task data before sync" "$LOG1"

# THE bystander assertion. Pre-fix this fails: one commit carried both files.
F10="$(commit_files_for "$TMP1" 'Auto-commit t10')"
assert_contains "t10's commit carries t10's file" "aitasks/t10_alpha.md" "$F10"
assert_not_contains "t10's commit does NOT carry t20's file" "t20_beta" "$F10"

# --- Test 2: a LIVE lock leaves the file dirty ----------------------------
echo "--- Test 2: live lock -> skipped and left dirty ---"
TMP2="$(setup_repo)"
plant_lock "$TMP2" 10 "$(lock_yaml_live 10)"
(cd "$TMP2/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md \
                  && printf 'edit20\n' >> .aitask-data/aitasks/t20_beta.md)
OUT2="$(run_sync "$TMP2")"
LOG2="$(data_log "$TMP2")"
DIRTY2="$(cd "$TMP2/local" && git -C .aitask-data status --porcelain -- aitasks/)"

assert_not_contains "a live-locked task's file is NOT committed" "Auto-commit t10" "$LOG2"
assert_contains "t10's file is left dirty" "t10_alpha.md" "$DIRTY2"
assert_contains "the unlocked bystander t20 IS still committed" \
    "ait: Auto-commit t20 task data before sync" "$LOG2"
assert_contains "the report names the live holder" "LIVE session" "$(sync_err "$TMP2")"

# --- Test 3: a DEAD lock is the recovery case -----------------------------
echo "--- Test 3: dead lock -> committed ---"
TMP3="$(setup_repo)"
plant_lock "$TMP3" 10 "$(lock_yaml_dead 10)"
(cd "$TMP3/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
OUT3="$(run_sync "$TMP3")"
assert_contains "a dead holder's file IS committed (crash recovery)" \
    "ait: Auto-commit t10 task data before sync" "$(data_log "$TMP3")"

# --- Test 4: unknown liveness fails safe ----------------------------------
echo "--- Test 4: unknown liveness -> skipped ---"
TMP4="$(setup_repo)"
plant_lock "$TMP4" 10 "$(lock_yaml_unknown_pid 10)"
(cd "$TMP4/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
OUT4="$(run_sync "$TMP4")"
assert_not_contains "unverifiable liveness is treated as live, not committed" \
    "Auto-commit t10" "$(data_log "$TMP4")"

# --- Test 5: cross-host lock, PID absent locally (discriminating) ---------
echo "--- Test 5: cross-host lock -> skipped even though the local PID is gone ---"
TMP5="$(setup_repo)"
# hostname "otherbox" != this run's "testhost", and the PID does not exist here.
# WITHOUT the cross-host guard, lock_holder_liveness probes the LOCAL process
# table, reads `dead`, and the file gets committed — the exact defect.
plant_lock "$TMP5" 10 "$(lock_yaml_dead 10 otherbox)"
(cd "$TMP5/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
OUT5="$(run_sync "$TMP5")"
assert_not_contains "a cross-host lock is never resolved against the LOCAL process table" \
    "Auto-commit t10" "$(data_log "$TMP5")"

# --- Test 6: hostname "unknown" is not comparable -------------------------
echo "--- Test 6: hostname 'unknown' -> skipped ---"
TMP6="$(setup_repo)"
plant_lock "$TMP6" 10 "$(lock_yaml_dead 10 unknown)"
(cd "$TMP6/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
OUT6="$(run_sync "$TMP6")"
assert_not_contains "hostname 'unknown' is not comparable, so it is skipped" \
    "Auto-commit t10" "$(data_log "$TMP6")"

# --- Test 7: ownerless file is skipped, with a prescriptive report --------
echo "--- Test 7: ownerless file -> skipped, NOT committed, remedy reported ---"
TMP7="$(setup_repo)"
BASE7="$(data_head "$TMP7")"
(cd "$TMP7/local" && printf 'changed\n' >> .aitask-data/aitasks/metadata/stats_config.json \
                  && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
OUT7="$(run_sync "$TMP7")"
# Scoped to the commits THIS run made: the fixture's own "data init" legitimately
# contains stats_config.json.
ALLFILES7="$(files_since "$TMP7" "$BASE7")"
# Pre-fix this FAILS: the bare commit swept stats_config.json in under t10's name.
assert_not_contains "an ownerless file is never swept into any commit" \
    "stats_config.json" "$ALLFILES7"
assert_contains "the ownerless report names the remedy command" \
    "./ait git add" "$(sync_err "$TMP7")"
assert_contains "t10 is still committed alongside" \
    "ait: Auto-commit t10 task data before sync" "$(data_log "$TMP7")"

# --- Test 8: --commit-unowned is the opt-in -------------------------------
echo "--- Test 8: --commit-unowned -> ownerless file IS committed ---"
TMP8="$(setup_repo)"
(cd "$TMP8/local" && printf 'changed\n' >> .aitask-data/aitasks/metadata/stats_config.json)
OUT8="$(run_sync "$TMP8" --commit-unowned)"
assert_contains "the opt-in commits it under a message naming no task" \
    "ait: Auto-commit unowned task data before sync" "$(data_log "$TMP8")"

# --- Test 9: -uall — a new child task in a new directory ------------------
echo "--- Test 9: new child task in a new aitasks/t<P>/ dir is committed ---"
TMP9="$(setup_repo)"
(cd "$TMP9/local" && mkdir -p .aitask-data/aitasks/t10 \
    && printf -- '---\nstatus: Ready\n---\nchild\n' > .aitask-data/aitasks/t10/t10_1_child.md)
OUT9="$(run_sync "$TMP9")"
F9="$(commit_files_for "$TMP9" 'Auto-commit t10_1')"
# Without -uall git reports `?? aitasks/t10/`, which has no derivable owner and
# would be skipped as ownerless — a new child task would never be committed.
assert_contains "the child file itself is committed, not its collapsed dir" \
    "aitasks/t10/t10_1_child.md" "$F9"

# --- Test 10: a deletion is committed -------------------------------------
echo "--- Test 10: deletion -> committed (absent path state) ---"
TMP10="$(setup_repo)"
(cd "$TMP10/local" && rm .aitask-data/aitasks/t10_alpha.md)
OUT10="$(run_sync "$TMP10")"
assert_contains "the deletion is committed under t10" \
    "ait: Auto-commit t10 task data before sync" "$(data_log "$TMP10")"
STILL10="$(git -C "$TMP10/local/.aitask-data" rev-parse --verify --quiet HEAD:aitasks/t10_alpha.md || echo GONE)"
assert_eq "the path is absent from HEAD afterwards" "GONE" "$STILL10"

# --- Test 11: unstaged archive move (D + ??), same owner ------------------
echo "--- Test 11: same-owner archive move -> committed as add+delete ---"
TMP11="$(setup_repo)"
BASE11="$(data_head "$TMP11")"
(cd "$TMP11/local" && mkdir -p .aitask-data/aitasks/archived \
    && mv .aitask-data/aitasks/t10_alpha.md .aitask-data/aitasks/archived/t10_alpha.md)
OUT11="$(run_sync "$TMP11")"
# --no-renames: git's rename DETECTION would otherwise collapse the pair to the
# new path alone, hiding the delete half the commit really records.
F11="$(files_since "$TMP11" "$BASE11")"
assert_contains "the new archived path is in the commit" \
    "aitasks/archived/t10_alpha.md" "$F11"
assert_contains "the old path is in the same commit (the delete half)" \
    "aitasks/t10_alpha.md" "$F11"

# --- Test 12: lock branch unreadable -> nothing committed ----------------
echo "--- Test 12: LOCKS_UNAVAILABLE -> nothing committed; --assume-unlocked overrides ---"
TMP12="$(setup_repo)"
(cd "$TMP12/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
BEFORE12="$(data_commit_count "$TMP12")"
# Delete the lock branch from the remote: ls-remote then reports "reachable but
# absent" (LOCKS_UNINITIALIZED), so instead make origin itself unreachable for
# the lock probe by pointing the branch at a broken remote name.
(cd "$TMP12/local" && git push -q origin --delete aitask-locks 2>/dev/null)
OUT12_UNINIT="$(run_sync "$TMP12")"
assert_contains "no lock branch at all -> nothing CAN be locked -> committed" \
    "ait: Auto-commit t10 task data before sync" "$(data_log "$TMP12")"

# Now the genuinely unreadable case: a remote that exists but cannot be reached.
TMP12B="$(setup_repo)"
(cd "$TMP12B/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
BEFORE12B="$(data_commit_count "$TMP12B")"
(cd "$TMP12B/local" && git remote set-url origin "$TMP12B/nonexistent-remote.git")
OUT12B="$(run_sync "$TMP12B")"
AFTER12B="$(data_commit_count "$TMP12B")"
assert_eq "an unreadable lock branch commits NOTHING" "$BEFORE12B" "$AFTER12B"

OUT12C="$(run_sync "$TMP12B" --assume-unlocked)"
assert_contains "--assume-unlocked is the explicit override" \
    "ait: Auto-commit t10 task data before sync" "$(data_log "$TMP12B")"

# --- Test 13: nothing eligible -> clean no-op ----------------------------
echo "--- Test 13: nothing dirty -> no commit created ---"
TMP13="$(setup_repo)"
BEFORE13="$(data_commit_count "$TMP13")"
OUT13="$(run_sync "$TMP13")"
AFTER13="$(data_commit_count "$TMP13")"
assert_eq "a clean tree creates no commit" "$BEFORE13" "$AFTER13"

# --- Test 14: a path containing a space ----------------------------------
echo "--- Test 14: a path with a space survives the -z parser ---"
TMP14="$(setup_repo)"
(cd "$TMP14/local" && printf -- '---\nstatus: Ready\n---\nS\n' > ".aitask-data/aitasks/t40_with space.md")
OUT14="$(run_sync "$TMP14")"
F14="$(commit_files_for "$TMP14" 'Auto-commit t40')"
assert_contains "the spaced path is committed unquoted and intact" \
    "t40_with space.md" "$F14"

# --- Test 14b: filenames git allows but delimiters do not ----------------
echo "--- Test 14b: newline and pipe in a filename survive grouping ---"
# A git path may contain ANY byte but NUL. Joining the grouped path list on a
# newline split such a file into two bogus paths, which then missed in
# PATH_STATE and — under `set -u` — aborted the whole script with EMPTY stdout,
# i.e. the `ERROR: empty output` failure the sweep exists to avoid.
TMP14B="$(setup_repo)"
NL_PATH=".aitask-data/aitasks/t60_line"$'\n'"break.md"
printf -- '---\nstatus: Ready\n---\nN\n' > "$TMP14B/local/$NL_PATH"
printf -- '---\nstatus: Ready\n---\nP\n' > "$TMP14B/local/.aitask-data/aitasks/t61_pipe|char.md"
OUT14B="$(run_sync "$TMP14B")"
LOG14B="$(data_log "$TMP14B")"
assert_eq "stdout is a real token, not empty (pre-fix: empty, rc 1)" "PUSHED" "$OUT14B"
assert_contains "the newline-named file is committed under its own task" \
    "ait: Auto-commit t60 task data before sync" "$LOG14B"
assert_contains "the pipe-named file is committed under its own task" \
    "ait: Auto-commit t61 task data before sync" "$LOG14B"
DIRTY14B="$(git -C "$TMP14B/local/.aitask-data" status --porcelain -uall)"
assert_eq "and nothing is left dirty" "" "$DIRTY14B"

# --- Test 15: another session's staged entry is never touched ------------
echo "--- Test 15: staged_elsewhere -> group deferred, index byte-identical ---"
TMP15="$(setup_repo)"
(cd "$TMP15/local" \
    && printf 'staged-content\n' >> .aitask-data/aitasks/t10_alpha.md \
    && git -C .aitask-data add -- aitasks/t10_alpha.md \
    && printf 'worktree-only\n' >> .aitask-data/aitasks/t10_alpha.md \
    && printf 'edit20\n' >> .aitask-data/aitasks/t20_beta.md)
IDX_BEFORE15="$(git -C "$TMP15/local/.aitask-data" rev-parse :aitasks/t10_alpha.md)"
OUT15="$(run_sync "$TMP15")"
IDX_AFTER15="$(git -C "$TMP15/local/.aitask-data" rev-parse :aitasks/t10_alpha.md)"
assert_eq "the foreign staged blob is byte-identical after the run" \
    "$IDX_BEFORE15" "$IDX_AFTER15"
assert_not_contains "a group with a foreign staged entry is deferred, not committed" \
    "Auto-commit t10 " "$(data_log "$TMP15")"
assert_contains "the unrelated t20 group still commits" \
    "ait: Auto-commit t20 task data before sync" "$(data_log "$TMP15")"

# --- Test 16: tracked files are committed WITHOUT being staged -----------
echo "--- Test 16: a tracked eligible file is never git-add-ed ---"
TMP16="$(setup_repo)"
(cd "$TMP16/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
IDXB16="$(git -C "$TMP16/local/.aitask-data" diff --cached --name-only)"
OUT16="$(run_sync "$TMP16")"
IDXA16="$(git -C "$TMP16/local/.aitask-data" diff --cached --name-only)"
assert_eq "the shared index had no staged entries before" "" "$IDXB16"
assert_eq "and none after — commit -o needs no staging for a tracked path" "" "$IDXA16"
assert_contains "yet the file was committed" \
    "ait: Auto-commit t10 task data before sync" "$(data_log "$TMP16")"

# ==========================================================================
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
