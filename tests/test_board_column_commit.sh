#!/usr/bin/env bash
# test_board_column_commit.sh - `aitask_board_column.sh create` owns its config (t1677).
#
# Run: bash tests/test_board_column_commit.sh
#
# Separate from tests/test_board_column_cli.sh on purpose: that file's fixture is
# a hand-built tree with no git repo ("stays readable in one screen"), and the
# behaviour here is entirely about what lands on the aitask-data branch. This one
# borrows tests/lib/sync_fixture.sh, which builds the real branch-mode topology.
#
# Why it exists: creating a column from minimonitor wrote board_config.json and
# stopped. `ait sync` cannot attribute a file under aitasks/metadata/, so it
# refused to commit it too — the column change sat dirty and blocked task-data
# sync until a human cleared it.

set -uo pipefail

TEST_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/sync_fixture.sh"

COLUMN_SH="./.aitask-scripts/aitask_board_column.sh"

# Run the CLI inside <tmpdir>'s clone; sets CL_OUT / CL_ERR / CL_RC here.
_cl() {
    local tmpdir="$1"; shift
    CL_RC=0
    CL_OUT="$(
        cd "$tmpdir/local" || exit 99
        export PATH="$PWD/bin:$PATH" TEST_HOSTNAME=testhost
        export AITASKS_LOCK_DIR="$tmpdir/locks"
        "$COLUMN_SH" "$@" 2>"$tmpdir/cl_stderr"
    )" || CL_RC=$?
    CL_ERR="$(cat "$tmpdir/cl_stderr" 2>/dev/null)"
}

data_git() { local t="$1"; shift; git -C "$t/local/.aitask-data" "$@" 2>/dev/null; }

seed_board_config() {   # <tmpdir>
    local t="$1"
    (
        cd "$t/local" || exit 1
        cat > .aitask-data/aitasks/metadata/board_config.json <<'JSON'
{
  "columns": [{"id": "now", "title": "now", "color": "#FF5555"}],
  "column_order": ["now"]
}
JSON
        git -C .aitask-data add -- aitasks/metadata/board_config.json
        git -C .aitask-data commit -q -m "seed board_config"
    ) >/dev/null 2>&1
}

echo "=== aitask_board_column.sh create commits board_config.json (t1677) ==="
echo ""

# --- Test 1: a successful create commits, path-scoped ---------------------
echo "--- Test 1: create -> committed, worktree clean ---"
TMP1="$(setup_repo)"
seed_board_config "$TMP1"
_cl "$TMP1" create --root . --title "shipped"

assert_eq "create still exits 0" "0" "$CL_RC"
assert_contains "stdout still carries the machine protocol line" "CREATED:" "$CL_OUT"
assert_eq "the config was committed, named after the file" \
    "ait: Update board_config.json" "$(data_git "$TMP1" log -1 --format=%s)"
assert_contains "the commit carries board_config.json" \
    "aitasks/metadata/board_config.json" "$(data_git "$TMP1" show --name-only --format= HEAD)"
assert_eq "the metadata worktree is clean afterwards" \
    "" "$(data_git "$TMP1" status --porcelain -- aitasks/metadata/)"
assert_eq "no warning on the success path" "" "$CL_ERR"

# --- Test 2: an unrelated dirty task file is not swept in ------------------
echo "--- Test 2: a bystander task file does not ride along ---"
TMP2="$(setup_repo)"
seed_board_config "$TMP2"
(cd "$TMP2/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
_cl "$TMP2" create --root . --title "scoped"

assert_not_contains "the commit does NOT carry the bystander" \
    "t10_alpha" "$(data_git "$TMP2" show --name-only --format= HEAD)"
assert_contains "the bystander is still dirty" "t10_alpha.md" \
    "$(data_git "$TMP2" status --porcelain)"

# --- Test 3: a failed commit is reported on stderr, never on stdout --------
# stdout is the machine protocol minimonitor parses; a diagnostic there would
# be read as a record. The column exists either way, so the create still
# succeeds — only the commit failed.
echo "--- Test 3: commit failure -> stderr warning, stdout intact, exit 0 ---"
TMP3="$(setup_repo)"
seed_board_config "$TMP3"
printf '#!/bin/sh\nexit 1\n' > "$TMP3/local/.git/hooks/pre-commit"
chmod +x "$TMP3/local/.git/hooks/pre-commit"
_cl "$TMP3" create --root . --title "unowned"

assert_eq "create still exits 0 — the column was created" "0" "$CL_RC"
assert_contains "stdout still carries CREATED:" "CREATED:" "$CL_OUT"
assert_not_contains "stdout is NOT polluted by the diagnostic" "WARN:" "$CL_OUT"
assert_contains "stderr warns that the commit failed" \
    "WARN:commit_failed:aitasks/metadata/board_config.json" "$CL_ERR"
assert_contains "and the config change survives on disk" "unowned" \
    "$(cat "$TMP3/local/.aitask-data/aitasks/metadata/board_config.json")"
assert_not_contains "nothing of ours is left staged" "board_config.json" \
    "$(data_git "$TMP3" diff --cached --name-only)"

# --- Test 4: read-only verbs are untouched --------------------------------
# `create` is the only verb that stopped using exec; the others must still
# stream straight through and commit nothing.
echo "--- Test 4: list-columns commits nothing and still streams ---"
TMP4="$(setup_repo)"
seed_board_config "$TMP4"
BASE4="$(data_head "$TMP4")"
_cl "$TMP4" list-columns --root .
assert_eq "list-columns exits 0" "0" "$CL_RC"
assert_contains "list-columns still emits COLUMN: records" "COLUMN:now" "$CL_OUT"
assert_eq "and made no commit" "$BASE4" "$(data_head "$TMP4")"

echo ""
echo "=== Results: $PASS passed, $FAIL failed (of $TOTAL) ==="
[[ "$FAIL" -eq 0 ]]
