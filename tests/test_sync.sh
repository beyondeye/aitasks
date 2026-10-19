#!/usr/bin/env bash
# test_sync.sh - Tests for ait sync / aitask_sync.sh
# Run: bash tests/test_sync.sh

set -e

TEST_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---
# Core helpers live in tests/lib/asserts.sh. This file's original assert_eq
# trimmed whitespace (xargs) and assert_contains was regex (grep -q, case-
# sensitive); call sites are remapped to assert_eq_trim / assert_contains_re.
. "$PROJECT_DIR/tests/lib/asserts.sh"

# Developer git config never reaches this file (t1987, the leak t1792 closed in
# sync_fixture.sh); the per-repo user.* the fixtures set still applies. After the
# counter initialisation above, so a failed probe is not erased.
. "$PROJECT_DIR/tests/lib/git_config_isolation.sh"
sync_isolate_git_config
assert_git_config_isolated

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
        cd "$tmpdir/local" || exit 1
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
        cd "$tmpdir/pc2" || exit 1
        git config user.email "test2@test.com"
        git config user.name "Test2"
    )

    # Copy project scripts into local clone
    cp "$PROJECT_DIR/ait" "$tmpdir/local/ait"
    cp -r "$PROJECT_DIR/.aitask-scripts" "$tmpdir/local/.aitask-scripts"
    chmod +x "$tmpdir/local/ait"

    echo "$tmpdir"
}

# Create a local repo with no remote configured
setup_no_remote_repo() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    (
        cd "$tmpdir" || exit 1
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
    cp -r "$PROJECT_DIR/.aitask-scripts" "$tmpdir/.aitask-scripts"
    chmod +x "$tmpdir/ait"

    echo "$tmpdir"
}

echo "=== ait sync Tests ==="
echo ""

# --- Test 1: NOTHING — clean repo, no changes ---
echo "--- Test 1: NOTHING - no changes anywhere ---"

TMPDIR_1="$(setup_sync_repos)"

output=$(cd "$TMPDIR_1/local" && ./ait sync --batch 2>/dev/null)
assert_eq_trim "Clean repo returns NOTHING" "NOTHING" "$output"

rm -rf "$TMPDIR_1"

# --- Test 2: PUSHED — local uncommitted changes auto-committed and pushed ---
echo "--- Test 2: PUSHED - local uncommitted changes ---"

TMPDIR_2="$(setup_sync_repos)"

# Make uncommitted changes in aitasks/
echo "updated" >> "$TMPDIR_2/local/aitasks/t1_sample.md"

output=$(cd "$TMPDIR_2/local" && ./ait sync --batch 2>/dev/null)
assert_eq_trim "Local uncommitted changes return PUSHED" "PUSHED" "$output"

# Verify the change reached the remote
git clone --quiet "$TMPDIR_2/remote.git" "$TMPDIR_2/verify" 2>/dev/null
assert_contains_re "Remote has updated content" "updated" "$(cat "$TMPDIR_2/verify/aitasks/t1_sample.md")"

rm -rf "$TMPDIR_2"

# --- Test 3: PULLED — remote-only changes pulled ---
echo "--- Test 3: PULLED - remote changes only ---"

TMPDIR_3="$(setup_sync_repos)"

# Push a change from pc2
(
    cd "$TMPDIR_3/pc2" || exit 1
    echo "from-pc2" > aitasks/t2_from_pc2.md
    git add -A
    git commit -m "add task from pc2" --quiet
    git push --quiet 2>/dev/null
)

output=$(cd "$TMPDIR_3/local" && ./ait sync --batch 2>/dev/null)
assert_eq_trim "Remote-only changes return PULLED" "PULLED" "$output"
assert_file_exists "Pulled file exists locally" "$TMPDIR_3/local/aitasks/t2_from_pc2.md"

rm -rf "$TMPDIR_3"

# --- Test 4: SYNCED — both local and remote changes, no conflict ---
echo "--- Test 4: SYNCED - both local and remote, no conflict ---"

TMPDIR_4="$(setup_sync_repos)"

# Push a change from pc2 (different file)
(
    cd "$TMPDIR_4/pc2" || exit 1
    echo "remote-task" > aitasks/t3_remote.md
    git add -A
    git commit -m "add remote task" --quiet
    git push --quiet 2>/dev/null
)

# Make local uncommitted change (different file)
echo "local-change" > "$TMPDIR_4/local/aitasks/t4_local.md"

output=$(cd "$TMPDIR_4/local" && ./ait sync --batch 2>/dev/null)
assert_eq_trim "Both changes return SYNCED" "SYNCED" "$output"
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
    cd "$TMPDIR_5/pc2" || exit 1
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
    cd "$TMPDIR_5/local" || exit 1
    echo "---
priority: high
status: Implementing
---
Modified locally" > aitasks/t1_sample.md
    git add -A
    git commit -m "modify t1 locally" --quiet
)

output=$(cd "$TMPDIR_5/local" && ./ait sync --batch 2>/dev/null)
assert_contains_re "Conflict returns CONFLICT prefix" "CONFLICT:" "$output"
assert_contains_re "Conflict mentions the file" "t1_sample" "$output"

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
assert_eq_trim "No remote returns NO_REMOTE" "NO_REMOTE" "$output"

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
assert_eq_trim "Legacy mode sync returns PUSHED" "PUSHED" "$output"

rm -rf "$TMPDIR_7"

# --- Test 8: Auto-commit — verify uncommitted changes are committed ---
echo "--- Test 8: Auto-commit - uncommitted changes committed before sync ---"

TMPDIR_8="$(setup_sync_repos)"

# Make uncommitted changes in aitasks/ and aiplans/
echo "uncommitted-task" > "$TMPDIR_8/local/aitasks/t6_uncommitted.md"
echo "uncommitted-plan" > "$TMPDIR_8/local/aiplans/p6_uncommitted.md"

output=$(cd "$TMPDIR_8/local" && ./ait sync --batch 2>/dev/null)
assert_eq_trim "Auto-commit + push returns PUSHED" "PUSHED" "$output"

# Verify both files are committed (working tree clean)
dirty=$(cd "$TMPDIR_8/local" && git status --porcelain -- aitasks/ aiplans/ 2>/dev/null)
assert_eq_trim "Working tree clean after auto-commit" "" "$dirty"

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
    cd "$TMPDIR_9/pc2" || exit 1
    echo "pc2-file" > aitasks/t7_pc2.md
    git add -A
    git commit -m "add t7 from pc2" --quiet
    git push --quiet 2>/dev/null
)

# Commit locally (different file, no conflict)
(
    cd "$TMPDIR_9/local" || exit 1
    echo "local-file" > aitasks/t8_local.md
    git add -A
    git commit -m "add t8 locally" --quiet
)

output=$(cd "$TMPDIR_9/local" && ./ait sync --batch 2>/dev/null)
assert_eq_trim "Rebase + push returns SYNCED" "SYNCED" "$output"

# Verify both files exist locally and remotely
assert_file_exists "Remote file pulled locally" "$TMPDIR_9/local/aitasks/t7_pc2.md"
git clone --quiet "$TMPDIR_9/remote.git" "$TMPDIR_9/verify" 2>/dev/null
assert_file_exists "Local file pushed to remote" "$TMPDIR_9/verify/aitasks/t8_local.md"
assert_file_exists "pc2 file still on remote" "$TMPDIR_9/verify/aitasks/t7_pc2.md"

rm -rf "$TMPDIR_9"

# --- Test 10: --help flag ---
echo "--- Test 10: --help flag ---"

TOTAL=$((TOTAL + 1))
if help_output=$(bash "$PROJECT_DIR/.aitask-scripts/aitask_sync.sh" --help 2>&1); then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: --help should exit 0"
fi
assert_contains_re "--help mentions batch" "batch" "$help_output"

# --- Test 11: Syntax check + shellcheck ---
echo "--- Test 11: Syntax check ---"

TOTAL=$((TOTAL + 1))
if bash -n "$PROJECT_DIR/.aitask-scripts/aitask_sync.sh" 2>/dev/null; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: bash -n aitask_sync.sh (syntax error)"
fi

if command -v shellcheck &>/dev/null; then
    TOTAL=$((TOTAL + 1))
    sc_errors=$(shellcheck --severity=error "$PROJECT_DIR/.aitask-scripts/aitask_sync.sh" 2>&1 | wc -l | tr -d ' ')
    if [[ "$sc_errors" -eq 0 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: shellcheck found errors in aitask_sync.sh"
        shellcheck --severity=error "$PROJECT_DIR/.aitask-scripts/aitask_sync.sh" 2>&1 | head -20
    fi
fi

# --- Test 12: AUTOMERGED — frontmatter-only conflict auto-resolved (batch) ---
echo "--- Test 12: AUTOMERGED - frontmatter-only conflict auto-resolved ---"

TMPDIR_12="$(setup_sync_repos)"

# Create a richer task file with multiple frontmatter fields
(
    cd "$TMPDIR_12/local" || exit 1
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
    cd "$TMPDIR_12/pc2" || exit 1
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
    cd "$TMPDIR_12/local" || exit 1
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
assert_eq_trim "Frontmatter-only conflict returns AUTOMERGED" "AUTOMERGED" "$output"

# Verify merged content
merged=$(cat "$TMPDIR_12/local/aitasks/t1_sample.md")
assert_contains_re "Merged file keeps local boardcol" "boardcol: backlog" "$merged"
assert_contains_re "Merged file has merged labels" "api" "$merged"
assert_contains_re "Merged file has merged labels" "ui" "$merged"

rm -rf "$TMPDIR_12"

# --- Test 13: AUTOMERGED — priority uses remote default in batch ---
echo "--- Test 13: AUTOMERGED - priority uses remote default in batch ---"

TMPDIR_13="$(setup_sync_repos)"

# Create task with priority field
(
    cd "$TMPDIR_13/local" || exit 1
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
    cd "$TMPDIR_13/pc2" || exit 1
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
    cd "$TMPDIR_13/local" || exit 1
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
assert_eq_trim "Priority conflict returns AUTOMERGED" "AUTOMERGED" "$output"

# Verify remote value was kept (batch default)
merged=$(cat "$TMPDIR_13/local/aitasks/t1_sample.md")
assert_contains_re "Priority uses remote value in batch" "priority: low" "$merged"

rm -rf "$TMPDIR_13"

# --- Test 14: CONFLICT preserved when body differs ---
echo "--- Test 14: CONFLICT preserved when body differs (partial merge) ---"

TMPDIR_14="$(setup_sync_repos)"

# Create task
(
    cd "$TMPDIR_14/local" || exit 1
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
    cd "$TMPDIR_14/pc2" || exit 1
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
    cd "$TMPDIR_14/local" || exit 1
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
assert_contains_re "Body conflict returns CONFLICT" "CONFLICT:" "$output"

rm -rf "$TMPDIR_14"

# --- Test 15: AUTOMERGED — concurrent '## Gate Runs' appends union (t635_21) ---
# Two PCs each append a different gate-run block to the same task's append-only
# ledger (the cross-PC gate-pass scenario). The rebase must auto-merge via the
# merge_body() gate-runs union — no manual conflict — with both blocks surviving.
echo "--- Test 15: AUTOMERGED - concurrent gate-runs appends union ---"

TMPDIR_15="$(setup_sync_repos)"
# pc2 needs the scripts too so it can run the REAL append path.
cp -r "$PROJECT_DIR/.aitask-scripts" "$TMPDIR_15/pc2/.aitask-scripts"

# Stage only the task file path — the copied .aitask-scripts/ dirs are untracked
# in both clones; committing them would make the other clone's pull abort on
# "untracked working tree files would be overwritten".
# local: seed a shared gate-run block via the real append path, push.
(
    cd "$TMPDIR_15/local" || exit 1
    ./.aitask-scripts/aitask_gate.sh append 1 tests_pass pass >/dev/null 2>&1
    git add aitasks/t1_sample.md
    git commit -m "gate: seed tests_pass on t1" --quiet
    git push --quiet 2>/dev/null
)

# pc2: pull the shared block, then append a DIFFERENT gate, push.
(
    cd "$TMPDIR_15/pc2" || exit 1
    git pull --quiet 2>/dev/null
    ./.aitask-scripts/aitask_gate.sh append 1 lint pass >/dev/null 2>&1
    git add aitasks/t1_sample.md
    git commit -m "gate: append lint on t1 (pc2)" --quiet
    git push --quiet 2>/dev/null
)

# local: append yet another gate concurrently (not yet pulled pc2's commit).
(
    cd "$TMPDIR_15/local" || exit 1
    ./.aitask-scripts/aitask_gate.sh append 1 docs_updated pass >/dev/null 2>&1
    git add aitasks/t1_sample.md
    git commit -m "gate: append docs_updated on t1 (local)" --quiet
)

output=$(cd "$TMPDIR_15/local" && ./ait sync --batch 2>/dev/null)
assert_eq_trim "Concurrent gate appends return AUTOMERGED" "AUTOMERGED" "$output"

merged=$(cat "$TMPDIR_15/local/aitasks/t1_sample.md")
assert_contains_re "Merged ledger keeps tests_pass" "gate:tests_pass" "$merged"
assert_contains_re "Merged ledger keeps lint (from pc2)" "gate:lint" "$merged"
assert_contains_re "Merged ledger keeps docs_updated (local)" "gate:docs_updated" "$merged"

# No manual conflict markers should remain.
TOTAL=$((TOTAL + 1))
if ! grep -q '<<<<<<<' "$TMPDIR_15/local/aitasks/t1_sample.md"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: merged ledger still contains conflict markers"
fi

# Derivation must still work over the merged file (all three gates current).
status_out=$(cd "$TMPDIR_15/local" && ./.aitask-scripts/aitask_gate.sh status 1 2>/dev/null)
assert_contains_re "Derived status lists tests_pass" "tests_pass" "$status_out"
assert_contains_re "Derived status lists lint" "lint" "$status_out"
assert_contains_re "Derived status lists docs_updated" "docs_updated" "$status_out"

rm -rf "$TMPDIR_15"

# --- Test 16-19: bounded fetch/push and the prompt policy (t2035) ---
# _git_with_timeout runs fetch/push through lib/bounded_run.py. The hanging
# origin is an ssh URL whose core.sshCommand stub records its pid, ignores
# SIGTERM and sleeps: git (the parent) -> the stub (a DISTINCT child only a
# process-group SIGKILL reaches). The old `timeout 10 git` sent SIGTERM alone
# and left it running. NETWORK_TIMEOUT is a fixed 10s, so each hang cell takes
# ~11s; AIT_BOUNDED_RUN_GRACE=1 keeps the TERM->KILL grace short.
SYNC_HANG_PIDS="$(mktemp)"

# make_sync_hang_stub <repo>: install the stub; prints its URL.
make_sync_hang_stub() {
    cat > "$1/hang-ssh" <<EOF
#!/bin/sh
echo \$\$ >> "$SYNC_HANG_PIDS"
trap '' TERM
exec sleep 30
EOF
    chmod +x "$1/hang-ssh"
    git -C "$1" config core.sshCommand "$1/hang-ssh"
    git -C "$1" config ssh.variant ssh
    echo "ssh://sync-hang.invalid/repo.git"
}
sync_hang_alive() {
    local pid alive=""
    while read -r pid; do
        [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null && alive="$alive $pid"
    done < "$SYNC_HANG_PIDS"
    printf '%s' "${alive# }"
}
sync_hang_reset() {
    xargs kill -KILL < "$SYNC_HANG_PIDS" 2>/dev/null || true
    : > "$SYNC_HANG_PIDS"
}
# assert_sync_hang_bounded <cell> <elapsed>: reached, bounded, all reaped.
assert_sync_hang_bounded() {
    sleep 0.3
    assert_eq "$1: fixture: the hanging transport was reached" "yes" \
        "$( [[ -s "$SYNC_HANG_PIDS" ]] && echo yes || echo no )"
    assert_eq "$1: returns within 20s (the stub hangs 30s)" "yes" \
        "$( (( $2 <= 20 )) && echo yes || echo "no: ${2}s" )"
    assert_eq "$1: every hanging transport process was killed" "" "$(sync_hang_alive)"
    sync_hang_reset
}

echo "--- Test 16: control: a direct-child kill leaves the transport running ---"
TMPDIR_16="$(setup_sync_repos)"
git -C "$TMPDIR_16/local" remote set-url origin "$(make_sync_hang_stub "$TMPDIR_16/local")"
git -C "$TMPDIR_16/local" fetch --quiet origin >/dev/null 2>&1 &
ctl_pid=$!
for _ in $(seq 100); do [[ -s "$SYNC_HANG_PIDS" ]] && break; sleep 0.05; done
kill -KILL "$ctl_pid" 2>/dev/null || true
wait "$ctl_pid" 2>/dev/null || true
sleep 0.2
assert_eq "16: control: the stub outlives a direct-child kill" "yes" \
    "$( [[ -n "$(sync_hang_alive)" ]] && echo yes || echo no )"
sync_hang_reset

echo "--- Test 17: a hanging fetch is bounded and fully reaped ---"
start=$SECONDS
output=$(cd "$TMPDIR_16/local" && AIT_BOUNDED_RUN_GRACE=1 ./ait sync --batch 2>/dev/null)
elapsed=$(( SECONDS - start ))
assert_eq_trim "17: a hanging fetch reports NO_NETWORK" "NO_NETWORK" "$output"
assert_sync_hang_bounded "17" "$elapsed"

echo "--- Test 17b: AIT_SYNC_ALLOW_PROMPT=1 keeps the bound and the cleanup ---"
start=$SECONDS
output=$(cd "$TMPDIR_16/local" && AIT_SYNC_ALLOW_PROMPT=1 AIT_BOUNDED_RUN_GRACE=1 \
    ./ait sync --batch 2>/dev/null)
elapsed=$(( SECONDS - start ))
assert_eq_trim "17b: a hanging fetch still reports NO_NETWORK" "NO_NETWORK" "$output"
assert_sync_hang_bounded "17b" "$elapsed"
rm -rf "$TMPDIR_16"

echo "--- Test 18: a hanging push is bounded and fully reaped ---"
TMPDIR_18="$(setup_sync_repos)"
git -C "$TMPDIR_18/local" config remote.origin.pushurl "$(make_sync_hang_stub "$TMPDIR_18/local")"
echo "unpushed" >> "$TMPDIR_18/local/aitasks/t1_sample.md"
start=$SECONDS
output=$(cd "$TMPDIR_18/local" && AIT_BOUNDED_RUN_GRACE=1 ./ait sync --batch 2>/dev/null)
elapsed=$(( SECONDS - start ))
assert_eq_trim "18: a hanging push reports NO_NETWORK" "NO_NETWORK" "$output"
assert_sync_hang_bounded "18" "$elapsed"
rm -rf "$TMPDIR_18"
rm -f "$SYNC_HANG_PIDS"

echo "--- Test 19: prompts off by default; AIT_SYNC_ALLOW_PROMPT=1 (only) restores them ---"
# A PATH git wrapper logs the prompt environment of every git that
# bounded_run.py started (it alone sets AIT_BOUNDED_RUN_GRACE in the child, so
# this file must not export it here), then execs the real git.
SYNC_ENV_DIR="$(mktemp -d)"
SYNC_ENV_LOG="$SYNC_ENV_DIR/env.log"
SYNC_REAL_GIT="$(type -P git)"
export SYNC_ENV_LOG SYNC_REAL_GIT
cat > "$SYNC_ENV_DIR/git" <<'EOF'
#!/bin/sh
if [ -n "${AIT_BOUNDED_RUN_GRACE+set}" ]; then
    for a in "$@"; do
        case "$a" in fetch|push)
            printf '%s GIT_ASKPASS=%s|SSH_ASKPASS=%s|SSH_ASKPASS_REQUIRE=%s|DISPLAY=%s\n' \
                "$a" "${GIT_ASKPASS-unset}" "${SSH_ASKPASS-unset}" \
                "${SSH_ASKPASS_REQUIRE-unset}" "${DISPLAY-unset}" >> "$SYNC_ENV_LOG"
            break ;;
        esac
    done
fi
exec "$SYNC_REAL_GIT" "$@"
EOF
chmod +x "$SYNC_ENV_DIR/git"
PROMPT_OFF="GIT_ASKPASS=|SSH_ASKPASS=unset|SSH_ASKPASS_REQUIRE=never|DISPLAY=unset"
PROMPT_ON="GIT_ASKPASS=unset|SSH_ASKPASS=/fake/askpass|SSH_ASKPASS_REQUIRE=unset|DISPLAY=:99"

# sync_prompt_env <cell> <AIT_SYNC_ALLOW_PROMPT value or "-" for unset> <expected>
sync_prompt_env() {
    local cell="$1" allow="$2" expected="$3" tmp out distinct
    tmp="$(setup_sync_repos)"
    echo "change-$cell" >> "$tmp/local/aitasks/t1_sample.md"
    : > "$SYNC_ENV_LOG"
    out=$(
        cd "$tmp/local" || exit 1
        unset GIT_ASKPASS SSH_ASKPASS_REQUIRE AIT_BOUNDED_RUN_GRACE AIT_SYNC_ALLOW_PROMPT
        export DISPLAY=:99 SSH_ASKPASS=/fake/askpass
        [[ "$allow" == "-" ]] || export AIT_SYNC_ALLOW_PROMPT="$allow"
        PATH="$SYNC_ENV_DIR:$PATH" ./ait sync --batch 2>/dev/null
    )
    assert_eq_trim "$cell: a local change is PUSHED" "PUSHED" "$out"
    assert_eq "$cell: fixture: the bounded fetch was logged" "yes" \
        "$(grep -q '^fetch ' "$SYNC_ENV_LOG" && echo yes || echo no)"
    assert_eq "$cell: fixture: the bounded push was logged" "yes" \
        "$(grep -q '^push ' "$SYNC_ENV_LOG" && echo yes || echo no)"
    distinct="$(sed 's/^[a-z]* //' "$SYNC_ENV_LOG" | sort -u)"
    assert_eq "$cell: every bounded fetch/push saw the expected prompt env" \
        "$expected" "$distinct"
    rm -rf "$tmp"
}
sync_prompt_env "19a (default)" "-" "$PROMPT_OFF"
sync_prompt_env "19b (=1)" "1" "$PROMPT_ON"
sync_prompt_env "19c (=yes is not 1)" "yes" "$PROMPT_OFF"
rm -rf "$SYNC_ENV_DIR"

echo "--- Test 20: no usable python is a named error, never NO_NETWORK ---"
# The bounded runner cannot start without an interpreter. Reporting that as
# NO_NETWORK would read as "offline, retry later" for a broken install.
TMPDIR_20="$(setup_sync_repos)"
output=$(cd "$TMPDIR_20/local" && _AIT_RESOLVED_PYTHON=/nonexistent/python \
    ./ait sync --batch 2>/dev/null) || true
assert_eq_trim "20: a missing interpreter reports ERROR:no_python" "ERROR:no_python" "$output"
output=$(cd "$TMPDIR_20/local" && ./ait sync --batch 2>/dev/null)
assert_eq_trim "20: control: the same repo syncs with the real interpreter" "NOTHING" "$output"
rm -rf "$TMPDIR_20"

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
