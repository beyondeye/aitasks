#!/usr/bin/env bash
# test_setup_metadata_commit_scope.sh - `ait setup` owns what IT wrote (t1677).
#
# Run: bash tests/test_setup_metadata_commit_scope.sh
#
# `ait setup`'s populate-missing / backfill passes write tracked files under
# aitasks/metadata/ and used to commit none of them, leaving an ownerless dirty
# config that blocks task-data sync.
#
# THE ASSERTION THAT MATTERS is Test 1's second half. The obvious fix — "after
# setup, commit everything dirty under aitasks/metadata/" — commits whatever a
# CONCURRENT session was mid-editing, publishing content this run never wrote.
# That is the raced-publication failure t1599_3 built a quarantine to prevent,
# and it would be re-created by the very task that closes its sibling gap. So
# each ensure_* records only the path IT wrote, and the flush commits exactly
# those. Test 1 fails against a blanket sweep.
#
# Test 3 covers the stale-signal hazard the per-invocation array inherits from
# `AIT_LABELS_ADDED` (t1662): every ensure_* early-exits in the common case, so
# an entry that outlives its phase would be committed under a later one.

set -uo pipefail

TEST_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/sync_fixture.sh"

# Source the setup script for its functions (never runs main).
source "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" --source-only
set +euo pipefail

data_git() { local t="$1"; shift; git -C "$t/local/.aitask-data" "$@" 2>/dev/null; }

# A fixture repo whose seed/ carries the two configs the ensure_* passes copy.
setup_with_seed() {
    local t
    t="$(setup_repo)"
    mkdir -p "$t/local/seed"
    printf 'intake_channel: {}\n' > "$t/local/seed/chatlink_config.yaml"
    printf 'runner: {}\n'        > "$t/local/seed/crew_runner_config.yaml"
    printf '%s' "$t"
}

# Run the ensure_* phase + flush IN THIS SHELL (a subshell would lose the array),
# with SCRIPT_DIR pointed at the fixture's own copy of the framework.
run_ensure_phase() {   # <tmpdir> <ensure fn>...
    local t="$1"; shift
    local saved_dir="$PWD" saved_script="$SCRIPT_DIR" fn
    cd "$t/local" || return 1
    SCRIPT_DIR="$t/local/.aitask-scripts"
    AIT_SETUP_METADATA_NEW=(); AIT_SETUP_METADATA_EXISTING=()
    for fn in "$@"; do
        "$fn" >/dev/null 2>&1
    done
    commit_setup_metadata_writes >/dev/null 2>&1
    SCRIPT_DIR="$saved_script"
    cd "$saved_dir" || return 1
}

echo "=== ait setup commits only the metadata IT wrote (t1677) ==="
echo ""

# --- Test 1: writes are committed; a foreign dirty file is NOT ------------
echo "--- Test 1: the created config is committed, a concurrent edit is not ---"
TMP1="$(setup_with_seed)"
# A concurrent session is mid-edit on a DIFFERENT tracked metadata file.
(cd "$TMP1/local" && printf 'concurrent-work-in-progress\n' \
    >> .aitask-data/aitasks/metadata/stats_config.json)
run_ensure_phase "$TMP1" ensure_chatlink_config

FILES1="$(data_git "$TMP1" show --name-only --format= HEAD)"
assert_contains "the file setup created IS committed" \
    "aitasks/metadata/chatlink_config.yaml" "$FILES1"
# Fails against "commit everything dirty under aitasks/metadata/".
assert_not_contains "the concurrent session's file is NOT in the commit" \
    "stats_config.json" "$FILES1"
assert_contains "and is left dirty for its own session to commit" \
    "stats_config.json" "$(data_git "$TMP1" status --porcelain)"
assert_contains "the concurrent edit is intact on disk" \
    "concurrent-work-in-progress" \
    "$(cat "$TMP1/local/.aitask-data/aitasks/metadata/stats_config.json")"
assert_contains "the commit names the file, not a task" \
    "ait: Update chatlink_config.yaml" "$(data_git "$TMP1" log -1 --format=%s)"

# --- Test 2: a no-op run commits nothing ---------------------------------
# Every ensure_* early-exits when its target already exists; that is the common
# case, and it must not produce an empty or spurious commit.
echo "--- Test 2: nothing written -> no commit at all ---"
TMP2="$(setup_with_seed)"
(cd "$TMP2/local" && printf 'already: here\n' \
    > .aitask-data/aitasks/metadata/chatlink_config.yaml \
    && git -C .aitask-data add -A && git -C .aitask-data commit -q -m "pre-existing")
BASE2="$(data_head "$TMP2")"
run_ensure_phase "$TMP2" ensure_chatlink_config
assert_eq "the data branch did not move" "$BASE2" "$(data_head "$TMP2")"

# --- Test 3: the per-invocation signal does not leak across runs ----------
# The t1662 hazard: a path recorded by an earlier phase that is still in the
# array when a later, write-free phase flushes.
echo "--- Test 3: a later write-free run does not re-commit an earlier path ---"
TMP3="$(setup_with_seed)"
run_ensure_phase "$TMP3" ensure_chatlink_config
AFTER_FIRST="$(data_head "$TMP3")"
# Second run: chatlink_config.yaml now exists, so ensure_* writes nothing.
run_ensure_phase "$TMP3" ensure_chatlink_config ensure_crew_runner_config
FILES3="$(data_git "$TMP3" show --name-only --format= HEAD)"
assert_contains "the second run commits only what it wrote" \
    "aitasks/metadata/crew_runner_config.yaml" "$FILES3"
assert_not_contains "not the file the FIRST run already committed" \
    "chatlink_config.yaml" "$FILES3"

# --- Test 4: a commit failure warns and never aborts setup ---------------
echo "--- Test 4: commit failure -> warning, setup continues ---"
TMP4="$(setup_with_seed)"
printf '#!/bin/sh\nexit 1\n' > "$TMP4/local/.git/hooks/pre-commit"
chmod +x "$TMP4/local/.git/hooks/pre-commit"
BASE4="$(data_head "$TMP4")"

saved_dir="$PWD"; saved_script="$SCRIPT_DIR"
cd "$TMP4/local" || exit 1
SCRIPT_DIR="$TMP4/local/.aitask-scripts"
AIT_SETUP_METADATA_NEW=(); AIT_SETUP_METADATA_EXISTING=()
ensure_chatlink_config >/dev/null 2>&1
# aitask_setup.sh overrides warn() to write to STDOUT (:143), alongside its
# info()/success() narrative — setup's stdout is prose, not a data channel.
FLUSH_OUT="$(commit_setup_metadata_writes 2>&1)"
FLUSH_RC=$?
SCRIPT_DIR="$saved_script"; cd "$saved_dir" || exit 1

assert_eq "the flush returns 0 — a failed commit must not abort setup" "0" "$FLUSH_RC"
assert_contains "it warns, naming the remedy command" \
    "aitask_metadata_commit.sh" "$FLUSH_OUT"
assert_eq "nothing was committed" "$BASE4" "$(data_head "$TMP4")"
assert_file_exists "the file setup wrote is still on disk" \
    "$TMP4/local/.aitask-data/aitasks/metadata/chatlink_config.yaml"

# --- Test 5: the BACKFILL pass must not publish an untracked file ---------
# `--allow-new` is a PER-PATH permission ("this run created the file"), not a
# batch mode. ensure_project_config_defaults has two write branches: it CREATES
# project_config.yaml from seed, and it EDITS an existing one to backfill
# codeagent_coauthor_domain. Only the first may carry the flag.
#
# NEGATIVE CONTROL (run against the pre-fix code): a single --allow-new batch
# for everything setup wrote commits the untracked file below, publishing local
# content this run merely edited. That is what these assertions fail on.
echo "--- Test 5: a backfilled pre-existing untracked config is refused ---"
TMP5="$(setup_with_seed)"
# An untracked, project-layer config that already exists and lacks the key, so
# the backfill branch (not the create branch) is the one that runs.
printf 'verify_build:\n' > "$TMP5/local/aitasks/metadata/project_config.yaml"
BASE5="$(data_head "$TMP5")"
run_ensure_phase "$TMP5" ensure_project_config_defaults

assert_eq "the data branch did not move — an edited untracked file is refused" \
    "$BASE5" "$(data_head "$TMP5")"
assert_not_contains "and it is still not tracked" \
    "project_config.yaml" "$(data_git "$TMP5" ls-files)"
assert_contains "the backfill edit itself survives on disk" \
    "codeagent_coauthor_domain" \
    "$(cat "$TMP5/local/aitasks/metadata/project_config.yaml")"

# --- Test 6: the CREATE branch still gets --allow-new --------------------
# The other half of the split: narrowing must not break the case the flag is
# for. Without it this commits nothing and Test 5 would pass vacuously.
echo "--- Test 6: a config setup created IS committed ---"
TMP6="$(setup_with_seed)"
printf 'verify_build:\n' > "$TMP6/local/seed/project_config.yaml"
rm -f "$TMP6/local/aitasks/metadata/project_config.yaml"
run_ensure_phase "$TMP6" ensure_project_config_defaults

assert_contains "the created config is committed" \
    "aitasks/metadata/project_config.yaml" \
    "$(data_git "$TMP6" show --name-only --format= HEAD)"
assert_contains "and is now tracked" \
    "project_config.yaml" "$(data_git "$TMP6" ls-files)"

# --- Test 7: a mixed run splits into two admissions ----------------------
# Both branches in ONE flush: a created file and an edited pre-existing untracked
# one. The created file must land; the edited one must not ride along on its
# flag. A single-batch implementation commits both.
echo "--- Test 7: created and edited paths do not share an admission ---"
TMP7="$(setup_with_seed)"
printf 'verify_build:\n' > "$TMP7/local/aitasks/metadata/project_config.yaml"
run_ensure_phase "$TMP7" ensure_project_config_defaults ensure_chatlink_config

TRACKED7="$(data_git "$TMP7" ls-files)"
assert_contains "the created config is tracked" "chatlink_config.yaml" "$TRACKED7"
assert_not_contains "the edited pre-existing one is NOT" \
    "project_config.yaml" "$TRACKED7"

echo ""
echo "=== Results: $PASS passed, $FAIL failed (of $TOTAL) ==="
[[ "$FAIL" -eq 0 ]]
