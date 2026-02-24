#!/usr/bin/env bash
# test_sync.sh - Tests for ait sync / aitask_sync.sh
# Run: bash tests/test_sync.sh

set -e

TEST_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    expected="$(echo "$expected" | xargs)"
    actual="$(echo "$actual" | xargs)"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected '$expected', got '$actual')"
    fi
}

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if echo "$actual" | grep -q "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected', got '$actual')"
    fi
}

assert_file_exists() {
    local desc="$1" file="$2"
    TOTAL=$((TOTAL + 1))
    if [[ -f "$file" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (file '$file' does not exist)"
    fi
}

# --- Setup helpers ---

# Create a bare remote + local clone + second clone ("other PC")
# Sets up aitasks/ directory with a sample task file in all clones
setup_sync_repos() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    # Create bare remote
    git init --bare --quiet "$tmpdir/remote.git"

    # Clone to local (main test repo)
    git clone --quiet "$tmpdir/remote.git" "$tmpdir/local" 2>/dev/null
    (
        cd "$tmpdir/local"
        git config user.email "test@test.com"
        git config user.name "Test"
        mkdir -p aitasks aiplans
        echo "---
priority: high
status: Ready
---
Sample task" > aitasks/t1_sample.md
        git add -A
        git commit -m "init with task" --quiet
        git push --quiet 2>/dev/null
    )

    # Clone to pc2 (simulates another PC)
    git clone --quiet "$tmpdir/remote.git" "$tmpdir/pc2" 2>/dev/null
    (
        cd "$tmpdir/pc2"
        git config user.email "test2@test.com"
        git config user.name "Test2"
    )

    # Copy project scripts into local clone
    cp "$PROJECT_DIR/ait" "$tmpdir/local/ait"
    cp -r "$PROJECT_DIR/aiscripts" "$tmpdir/local/aiscripts"
    chmod +x "$tmpdir/local/ait"

    echo "$tmpdir"
}

# Create a local repo with no remote configured
setup_no_remote_repo() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    (
        cd "$tmpdir"
        git init --quiet
        git config user.email "test@test.com"
        git config user.name "Test"
        mkdir -p aitasks aiplans
        echo "---
priority: high
status: Ready
---
Sample task" > aitasks/t1_sample.md
        git add -A
        git commit -m "init" --quiet
    )

    # Copy project scripts
    cp "$PROJECT_DIR/ait" "$tmpdir/ait"
    cp -r "$PROJECT_DIR/aiscripts" "$tmpdir/aiscripts"
    chmod +x "$tmpdir/ait"

    echo "$tmpdir"
}

echo "=== ait sync Tests ==="
echo ""

# --- Test 1: NOTHING — clean repo, no changes ---
echo "--- Test 1: NOTHING - no changes anywhere ---"

TMPDIR_1="$(setup_sync_repos)"

output=$(cd "$TMPDIR_1/local" && ./ait sync --batch 2>/dev/null)
assert_eq "Clean repo returns NOTHING" "NOTHING" "$output"

rm -rf "$TMPDIR_1"

# --- Test 2: PUSHED — local uncommitted changes auto-committed and pushed ---
echo "--- Test 2: PUSHED - local uncommitted changes ---"

TMPDIR_2="$(setup_sync_repos)"

# Make uncommitted changes in aitasks/
echo "updated" >> "$TMPDIR_2/local/aitasks/t1_sample.md"

output=$(cd "$TMPDIR_2/local" && ./ait sync --batch 2>/dev/null)
assert_eq "Local uncommitted changes return PUSHED" "PUSHED" "$output"

# Verify the change reached the remote
git clone --quiet "$TMPDIR_2/remote.git" "$TMPDIR_2/verify" 2>/dev/null
assert_contains "Remote has updated content" "updated" "$(cat "$TMPDIR_2/verify/aitasks/t1_sample.md")"

rm -rf "$TMPDIR_2"

# --- Test 3: PULLED — remote-only changes pulled ---
echo "--- Test 3: PULLED - remote changes only ---"

TMPDIR_3="$(setup_sync_repos)"

# Push a change from pc2
(
    cd "$TMPDIR_3/pc2"
    echo "from-pc2" > aitasks/t2_from_pc2.md
    git add -A
    git commit -m "add task from pc2" --quiet
    git push --quiet 2>/dev/null
)

output=$(cd "$TMPDIR_3/local" && ./ait sync --batch 2>/dev/null)
assert_eq "Remote-only changes return PULLED" "PULLED" "$output"
assert_file_exists "Pulled file exists locally" "$TMPDIR_3/local/aitasks/t2_from_pc2.md"

rm -rf "$TMPDIR_3"

# --- Test 4: SYNCED — both local and remote changes, no conflict ---
echo "--- Test 4: SYNCED - both local and remote, no conflict ---"

TMPDIR_4="$(setup_sync_repos)"

# Push a change from pc2 (different file)
(
    cd "$TMPDIR_4/pc2"
    echo "remote-task" > aitasks/t3_remote.md
    git add -A
    git commit -m "add remote task" --quiet
    git push --quiet 2>/dev/null
)

# Make local uncommitted change (different file)
echo "local-change" > "$TMPDIR_4/local/aitasks/t4_local.md"

output=$(cd "$TMPDIR_4/local" && ./ait sync --batch 2>/dev/null)
assert_eq "Both changes return SYNCED" "SYNCED" "$output"
assert_file_exists "Remote file pulled" "$TMPDIR_4/local/aitasks/t3_remote.md"
assert_file_exists "Local file still exists" "$TMPDIR_4/local/aitasks/t4_local.md"

# Verify local changes reached remote
git clone --quiet "$TMPDIR_4/remote.git" "$TMPDIR_4/verify" 2>/dev/null
assert_file_exists "Local file pushed to remote" "$TMPDIR_4/verify/aitasks/t4_local.md"

rm -rf "$TMPDIR_4"

# --- Test 5: CONFLICT — conflicting edits in batch mode ---
echo "--- Test 5: CONFLICT - conflicting edits (batch mode) ---"

TMPDIR_5="$(setup_sync_repos)"

# Push a change from pc2 to the SAME file
(
    cd "$TMPDIR_5/pc2"
    echo "---
priority: low
status: Done
---
Modified by pc2" > aitasks/t1_sample.md
    git add -A
    git commit -m "modify t1 from pc2" --quiet
    git push --quiet 2>/dev/null
)

# Make conflicting local change to same file (committed, not just dirty)
(
    cd "$TMPDIR_5/local"
    echo "---
priority: high
status: Implementing
---
Modified locally" > aitasks/t1_sample.md
    git add -A
    git commit -m "modify t1 locally" --quiet
)

output=$(cd "$TMPDIR_5/local" && ./ait sync --batch 2>/dev/null)
assert_contains "Conflict returns CONFLICT prefix" "CONFLICT:" "$output"
assert_contains "Conflict mentions the file" "t1_sample" "$output"

# Verify rebase was aborted (no rebase in progress)
TOTAL=$((TOTAL + 1))
if (cd "$TMPDIR_5/local" && git status --porcelain 2>/dev/null) >/dev/null 2>&1; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Rebase should have been aborted after CONFLICT"
fi

rm -rf "$TMPDIR_5"

# --- Test 6: NO_REMOTE — repo with no remote ---
echo "--- Test 6: NO_REMOTE - no remote configured ---"

TMPDIR_6="$(setup_no_remote_repo)"

output=$(cd "$TMPDIR_6" && ./ait sync --batch 2>/dev/null)
assert_eq "No remote returns NO_REMOTE" "NO_REMOTE" "$output"

rm -rf "$TMPDIR_6"

# --- Test 7: Legacy mode — sync works without .aitask-data ---
echo "--- Test 7: Legacy mode - no .aitask-data worktree ---"

TMPDIR_7="$(setup_sync_repos)"

# Verify no .aitask-data directory exists (legacy mode)
TOTAL=$((TOTAL + 1))
if [[ ! -d "$TMPDIR_7/local/.aitask-data" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: .aitask-data should not exist in legacy mode test"
fi

# Make a change and sync
echo "legacy-change" > "$TMPDIR_7/local/aitasks/t5_legacy.md"
output=$(cd "$TMPDIR_7/local" && ./ait sync --batch 2>/dev/null)
assert_eq "Legacy mode sync returns PUSHED" "PUSHED" "$output"

rm -rf "$TMPDIR_7"

# --- Test 8: Auto-commit — verify uncommitted changes are committed ---
echo "--- Test 8: Auto-commit - uncommitted changes committed before sync ---"

TMPDIR_8="$(setup_sync_repos)"

# Make uncommitted changes in aitasks/ and aiplans/
echo "uncommitted-task" > "$TMPDIR_8/local/aitasks/t6_uncommitted.md"
echo "uncommitted-plan" > "$TMPDIR_8/local/aiplans/p6_uncommitted.md"

output=$(cd "$TMPDIR_8/local" && ./ait sync --batch 2>/dev/null)
assert_eq "Auto-commit + push returns PUSHED" "PUSHED" "$output"

# Verify both files are committed (working tree clean)
dirty=$(cd "$TMPDIR_8/local" && git status --porcelain -- aitasks/ aiplans/ 2>/dev/null)
assert_eq "Working tree clean after auto-commit" "" "$dirty"

# Verify files reached remote
git clone --quiet "$TMPDIR_8/remote.git" "$TMPDIR_8/verify" 2>/dev/null
assert_file_exists "Auto-committed task reached remote" "$TMPDIR_8/verify/aitasks/t6_uncommitted.md"
assert_file_exists "Auto-committed plan reached remote" "$TMPDIR_8/verify/aiplans/p6_uncommitted.md"

rm -rf "$TMPDIR_8"

# --- Test 9: Push after pull — local + remote changes, pull rebase then push ---
echo "--- Test 9: Push after pull - rebase then push ---"

TMPDIR_9="$(setup_sync_repos)"

# Push from pc2
(
    cd "$TMPDIR_9/pc2"
    echo "pc2-file" > aitasks/t7_pc2.md
    git add -A
    git commit -m "add t7 from pc2" --quiet
    git push --quiet 2>/dev/null
)

# Commit locally (different file, no conflict)
(
    cd "$TMPDIR_9/local"
    echo "local-file" > aitasks/t8_local.md
    git add -A
    git commit -m "add t8 locally" --quiet
)

output=$(cd "$TMPDIR_9/local" && ./ait sync --batch 2>/dev/null)
assert_eq "Rebase + push returns SYNCED" "SYNCED" "$output"

# Verify both files exist locally and remotely
assert_file_exists "Remote file pulled locally" "$TMPDIR_9/local/aitasks/t7_pc2.md"
git clone --quiet "$TMPDIR_9/remote.git" "$TMPDIR_9/verify" 2>/dev/null
assert_file_exists "Local file pushed to remote" "$TMPDIR_9/verify/aitasks/t8_local.md"
assert_file_exists "pc2 file still on remote" "$TMPDIR_9/verify/aitasks/t7_pc2.md"

rm -rf "$TMPDIR_9"

# --- Test 10: --help flag ---
echo "--- Test 10: --help flag ---"

TOTAL=$((TOTAL + 1))
if help_output=$(bash "$PROJECT_DIR/aiscripts/aitask_sync.sh" --help 2>&1); then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: --help should exit 0"
fi
assert_contains "--help mentions batch" "batch" "$help_output"

# --- Test 11: Syntax check + shellcheck ---
echo "--- Test 11: Syntax check ---"

TOTAL=$((TOTAL + 1))
if bash -n "$PROJECT_DIR/aiscripts/aitask_sync.sh" 2>/dev/null; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: bash -n aitask_sync.sh (syntax error)"
fi

if command -v shellcheck &>/dev/null; then
    TOTAL=$((TOTAL + 1))
    sc_errors=$(shellcheck --severity=error "$PROJECT_DIR/aiscripts/aitask_sync.sh" 2>&1 | wc -l | tr -d ' ')
    if [[ "$sc_errors" -eq 0 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: shellcheck found errors in aitask_sync.sh"
        shellcheck --severity=error "$PROJECT_DIR/aiscripts/aitask_sync.sh" 2>&1 | head -20
    fi
fi

# --- Test 12: AUTOMERGED — frontmatter-only conflict auto-resolved (batch) ---
echo "--- Test 12: AUTOMERGED - frontmatter-only conflict auto-resolved ---"

TMPDIR_12="$(setup_sync_repos)"

# Create a richer task file with multiple frontmatter fields
(
    cd "$TMPDIR_12/local"
    cat > aitasks/t1_sample.md <<'TASKEOF'
---
priority: high
status: Ready
boardcol: backlog
labels: [ui]
updated_at: 2026-01-01 10:00
---
Task body stays the same
TASKEOF
    git add -A
    git commit -m "setup rich task" --quiet
    git push --quiet 2>/dev/null
)

# Sync pc2
(cd "$TMPDIR_12/pc2" && git pull --quiet 2>/dev/null)

# pc2: change boardcol
(
    cd "$TMPDIR_12/pc2"
    cat > aitasks/t1_sample.md <<'TASKEOF'
---
priority: high
status: Ready
boardcol: now
labels: [ui]
updated_at: 2026-01-01 10:00
---
Task body stays the same
TASKEOF
    git add -A
    git commit -m "pc2: change boardcol" --quiet
    git push --quiet 2>/dev/null
)

# local: change labels (different field, same body)
(
    cd "$TMPDIR_12/local"
    cat > aitasks/t1_sample.md <<'TASKEOF'
---
priority: high
status: Ready
boardcol: backlog
labels: [api, ui]
updated_at: 2026-01-01 10:00
---
Task body stays the same
TASKEOF
    git add -A
    git commit -m "local: change labels" --quiet
)

output=$(cd "$TMPDIR_12/local" && ./ait sync --batch 2>/dev/null)
assert_eq "Frontmatter-only conflict returns AUTOMERGED" "AUTOMERGED" "$output"

# Verify merged content
merged=$(cat "$TMPDIR_12/local/aitasks/t1_sample.md")
assert_contains "Merged file keeps local boardcol" "boardcol: backlog" "$merged"
assert_contains "Merged file has merged labels" "api" "$merged"
assert_contains "Merged file has merged labels" "ui" "$merged"

rm -rf "$TMPDIR_12"

# --- Test 13: AUTOMERGED — priority uses remote default in batch ---
echo "--- Test 13: AUTOMERGED - priority uses remote default in batch ---"

TMPDIR_13="$(setup_sync_repos)"

# Create task with priority field
(
    cd "$TMPDIR_13/local"
    cat > aitasks/t1_sample.md <<'TASKEOF'
---
priority: high
status: Ready
updated_at: 2026-01-01 10:00
---
Same body
TASKEOF
    git add -A
    git commit -m "setup priority task" --quiet
    git push --quiet 2>/dev/null
)

# Sync pc2
(cd "$TMPDIR_13/pc2" && git pull --quiet 2>/dev/null)

# pc2: change priority to low
(
    cd "$TMPDIR_13/pc2"
    cat > aitasks/t1_sample.md <<'TASKEOF'
---
priority: low
status: Ready
updated_at: 2026-01-01 10:00
---
Same body
TASKEOF
    git add -A
    git commit -m "pc2: priority low" --quiet
    git push --quiet 2>/dev/null
)

# local: change priority to medium
(
    cd "$TMPDIR_13/local"
    cat > aitasks/t1_sample.md <<'TASKEOF'
---
priority: medium
status: Ready
updated_at: 2026-01-01 10:00
---
Same body
TASKEOF
    git add -A
    git commit -m "local: priority medium" --quiet
)

output=$(cd "$TMPDIR_13/local" && ./ait sync --batch 2>/dev/null)
assert_eq "Priority conflict returns AUTOMERGED" "AUTOMERGED" "$output"

# Verify remote value was kept (batch default)
merged=$(cat "$TMPDIR_13/local/aitasks/t1_sample.md")
assert_contains "Priority uses remote value in batch" "priority: low" "$merged"

rm -rf "$TMPDIR_13"

# --- Test 14: CONFLICT preserved when body differs ---
echo "--- Test 14: CONFLICT preserved when body differs (partial merge) ---"

TMPDIR_14="$(setup_sync_repos)"

# Create task
(
    cd "$TMPDIR_14/local"
    cat > aitasks/t1_sample.md <<'TASKEOF'
---
priority: high
status: Ready
updated_at: 2026-01-01 10:00
---
Original body
TASKEOF
    git add -A
    git commit -m "setup body task" --quiet
    git push --quiet 2>/dev/null
)

# Sync pc2
(cd "$TMPDIR_14/pc2" && git pull --quiet 2>/dev/null)

# pc2: change body
(
    cd "$TMPDIR_14/pc2"
    cat > aitasks/t1_sample.md <<'TASKEOF'
---
priority: high
status: Ready
updated_at: 2026-01-01 10:00
---
Modified by pc2
TASKEOF
    git add -A
    git commit -m "pc2: change body" --quiet
    git push --quiet 2>/dev/null
)

# local: change body differently
(
    cd "$TMPDIR_14/local"
    cat > aitasks/t1_sample.md <<'TASKEOF'
---
priority: high
status: Ready
updated_at: 2026-01-01 10:00
---
Modified locally
TASKEOF
    git add -A
    git commit -m "local: change body" --quiet
)

output=$(cd "$TMPDIR_14/local" && ./ait sync --batch 2>/dev/null)
assert_contains "Body conflict returns CONFLICT" "CONFLICT:" "$output"

rm -rf "$TMPDIR_14"

# --- Summary ---
echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
