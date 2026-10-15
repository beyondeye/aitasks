#!/usr/bin/env bash
# test_crew_pull_no_autostash.sh - every crew-worktree pull ignores a user's
# rebase.autoStash / merge.autoStash (t2008).
#
# A crew worktree routinely holds other live processes' uncommitted tracked
# files: agent heartbeats, non-terminal status writes, queued commands and the
# runner's own heartbeat. An autostash would stash and re-apply files the caller
# does not own. Each fixture gives the crew branch an upstream — without one the
# pull dies with "no tracking information" before any stash, and every cell
# would pass vacuously — and the controls (cells 1 and 3) prove the pull really
# reaches the rebase.
#
# Run: bash tests/test_crew_pull_no_autostash.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"
# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=lib/venv_python.sh
. "$PROJECT_DIR/tests/lib/venv_python.sh"

PASS=0
FAIL=0
TOTAL=0

# Developer git config never reaches this file: a global autoStash would hide
# the defect, and a global push.autoSetupRemote would change the fixture. The
# autoStash settings each cell needs are per-repo config, which still applies.
# Sourced AFTER the counter initialisation, because the probe asserts.
. "$PROJECT_DIR/tests/lib/git_config_isolation.sh"
sync_isolate_git_config
assert_git_config_isolated

CLEANUP_DIRS=()
cleanup() {
    for d in "${CLEANUP_DIRS[@]}"; do
        rm -rf "$d" 2>/dev/null
    done
}
trap cleanup EXIT

# Byte digest, and inode + ctime: a stash round trip restores the bytes but
# rewrites the file, so only the identity proves a file was never touched
# (the same pair tests/test_task_push.sh pins for the task-data pulls, t1987).
file_sha() { { sha256sum < "$1"; } 2>/dev/null | cut -d' ' -f1; }
file_ident() {
    python3 -c 'import os,sys; s=os.lstat(sys.argv[1]); print(s.st_ino, s.st_ctime_ns)' "$1" 2>/dev/null
}

CREW_ID="pull"

# setup_crew_remote_fixture <peer_change>
# A crew with one Waiting agent w1, its branch pushed with an upstream, and a
# peer commit on the remote the crew worktree has not pulled yet.
#   peer_change: peer_only    — the peer adds peer_only.txt (disjoint)
#                runner_stop  — the peer sets requested_action: stop in
#                               _runner_alive.yaml (overlaps the runner heartbeat)
# Sets: ROOT REPO WT PEER REMOTE BRANCH
setup_crew_remote_fixture() {
    local peer_change="$1"
    ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ait_crew_pull_XXXXXX")"
    CLEANUP_DIRS+=("$ROOT")
    REPO="$ROOT/repo"
    PEER="$ROOT/peer"
    REMOTE="$ROOT/remote.git"
    BRANCH="crew-$CREW_ID"
    WT="$REPO/.aitask-crews/$BRANCH"

    mkdir -p "$REPO/aitasks/metadata"
    git -C "$REPO" init --quiet
    git -C "$REPO" config user.email "test@test.com"
    git -C "$REPO" config user.name "Test"
    setup_fake_aitask_repo "$REPO"
    cp "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh"   "$REPO/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/launch_modes_sh.sh"   "$REPO/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/launch_modes.py"      "$REPO/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_crew_init.sh"      "$REPO/.aitask-scripts/"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_crew_addwork.sh"   "$REPO/.aitask-scripts/"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_crew_setmode.sh"   "$REPO/.aitask-scripts/"
    echo "email: test@test.com" > "$REPO/aitasks/metadata/userconfig.yaml"
    git -C "$REPO" add -A
    git -C "$REPO" commit -m "Initial setup" --quiet

    # No upstream exists yet, so the seeding addwork's own pull and push fail
    # quietly; that is the crew scripts' best-effort contract.
    (
        cd "$REPO" || exit 1
        bash .aitask-scripts/aitask_crew_init.sh --id "$CREW_ID" \
            --add-type impl:claudecode/opus4_6 --batch
        bash .aitask-scripts/aitask_crew_addwork.sh --crew "$CREW_ID" --name w1 \
            --work2do /dev/null --type impl --batch
    ) >/dev/null 2>&1

    # The runner's alive file, in write_runner_alive's key order.
    cat > "$WT/_runner_alive.yaml" <<'EOF'
status: running
pid: 4242
hostname: crewhost
started_at: '2026-10-15 10:00:00'
last_heartbeat: '2026-10-15 10:00:00'
next_check_at: '2026-10-15 10:00:30'
interval: 30
requested_action: null
EOF
    git -C "$WT" add _runner_alive.yaml
    git -C "$WT" commit -m "runner: started" --quiet

    git init --bare --quiet "$REMOTE"
    git -C "$REPO" remote add origin "$REMOTE"
    git -C "$WT" push --quiet -u origin "$BRANCH" 2>/dev/null
    assert_eq "fixture: the crew branch has an upstream" "origin/$BRANCH" \
        "$(git -C "$WT" rev-parse --abbrev-ref '@{u}' 2>/dev/null)"

    git clone --quiet -b "$BRANCH" "$REMOTE" "$PEER" 2>/dev/null
    git -C "$PEER" config user.email "peer@test.com"
    git -C "$PEER" config user.name "Peer"
    case "$peer_change" in
        peer_only)
            echo "from another host" > "$PEER/peer_only.txt"
            git -C "$PEER" add peer_only.txt
            git -C "$PEER" commit -m "peer: add peer_only.txt" --quiet
            ;;
        runner_stop)
            sed 's/^requested_action: null$/requested_action: stop/' \
                "$PEER/_runner_alive.yaml" > "$PEER/_runner_alive.yaml.tmp"
            mv "$PEER/_runner_alive.yaml.tmp" "$PEER/_runner_alive.yaml"
            git -C "$PEER" commit -am "peer: request runner stop" --quiet
            ;;
    esac
    git -C "$PEER" push --quiet 2>/dev/null
    assert_eq "fixture: the remote is ahead of the crew worktree" "1" \
        "$(git -C "$REMOTE" rev-list --count "$(git -C "$WT" rev-parse HEAD)..refs/heads/$BRANCH")"

    git -C "$REPO" config rebase.autoStash true
    git -C "$REPO" config merge.autoStash true
}

# Stand-in for a running agent's uncommitted heartbeat write.
# Sets: dirty_file dirty_sha dirty_ident
dirty_agent_heartbeat() {
    dirty_file="$WT/w1_alive.yaml"
    echo "last_heartbeat: '2026-10-15 10:05:00'" >> "$dirty_file"
    dirty_sha="$(file_sha "$dirty_file")"
    dirty_ident="$(file_ident "$dirty_file")"
}

# The dirty file was never rewritten, never stashed, and never committed.
assert_dirty_untouched() {
    local label="$1" rel
    rel="$(basename "$dirty_file")"
    assert_eq "$label: the dirty file's bytes are unchanged" "$dirty_sha" "$(file_sha "$dirty_file")"
    assert_eq "$label: the dirty file was never rewritten (inode+ctime)" "$dirty_ident" "$(file_ident "$dirty_file")"
    assert_eq "$label: nothing was stashed" "" "$(git -C "$WT" stash list)"
    assert_eq "$label: the dirty file is still uncommitted" "dirty" \
        "$(git -C "$WT" diff --quiet -- "$rel" && echo clean || echo dirty)"
}

peer_file_state() {
    [[ -e "$WT/peer_only.txt" ]] && echo present || echo absent
}

remote_head() {
    git -C "$REMOTE" rev-parse "refs/heads/$BRANCH"
}

run_addwork_w2() {
    (cd "$REPO" && bash .aitask-scripts/aitask_crew_addwork.sh --crew "$CREW_ID" --name w2 \
        --work2do /dev/null --type impl --batch 2>&1)
}

run_setmode_w1() {
    (cd "$REPO" && bash .aitask-scripts/aitask_crew_setmode.sh --crew "$CREW_ID" --name w1 \
        --mode interactive 2>&1)
}

# The runner's per-iteration pull, through the real helper.
run_runner_pull() {
    "$AITASK_PYTHON" -c '
import sys
sys.path.insert(0, sys.argv[1])
from agentcrew_utils import git_pull
git_pull(sys.argv[2], batch=True)
' "$PROJECT_DIR/.aitask-scripts/agentcrew" "$WT"
}

echo "=== crew pulls ignore autoStash (t2008) ==="

# --- Test 1: addwork control — a clean tree pulls and pushes ---
echo "--- Test 1: addwork, clean worktree (control) ---"
setup_crew_remote_fixture peer_only
out="$(run_addwork_w2)"; rc=$?
assert_eq "1: addwork exits 0" "0" "$rc"
assert_contains "1: addwork reports ADDED" "ADDED:w2" "$out"
assert_eq "1: the pull reached the rebase (peer commit landed)" "present" "$(peer_file_state)"
assert_eq "1: the push landed" "$(git -C "$WT" rev-parse HEAD)" "$(remote_head)"
assert_eq "1: nothing was stashed" "" "$(git -C "$WT" stash list)"

# --- Test 2: addwork never autostashes another agent's heartbeat ---
echo "--- Test 2: addwork ignores rebase.autoStash=true ---"
setup_crew_remote_fixture peer_only
dirty_agent_heartbeat
out="$(run_addwork_w2)"; rc=$?
assert_eq "2: addwork exits 0 (best-effort pull)" "0" "$rc"
assert_contains "2: addwork reports ADDED" "ADDED:w2" "$out"
assert_dirty_untouched "2"
assert_eq "2: the pull refused (peer commit did not land)" "absent" "$(peer_file_state)"
assert_contains "2: addwork's own commit was made" "crew: Add agent 'w2'" \
    "$(git -C "$WT" log -1 --format=%s)"

# --- Test 3: setmode control — a clean tree pulls and pushes ---
echo "--- Test 3: setmode, clean worktree (control) ---"
setup_crew_remote_fixture peer_only
out="$(run_setmode_w1)"; rc=$?
assert_eq "3: setmode exits 0" "0" "$rc"
assert_contains "3: setmode reports UPDATED" "UPDATED:w1:interactive" "$out"
assert_eq "3: the pull reached the rebase (peer commit landed)" "present" "$(peer_file_state)"
assert_eq "3: the push landed" "$(git -C "$WT" rev-parse HEAD)" "$(remote_head)"
assert_eq "3: nothing was stashed" "" "$(git -C "$WT" stash list)"

# --- Test 4: setmode never autostashes another agent's heartbeat ---
echo "--- Test 4: setmode ignores rebase.autoStash=true ---"
setup_crew_remote_fixture peer_only
dirty_agent_heartbeat
out="$(run_setmode_w1)"; rc=$?
assert_eq "4: setmode exits 0 (best-effort pull)" "0" "$rc"
assert_contains "4: setmode reports UPDATED" "UPDATED:w1:interactive" "$out"
assert_dirty_untouched "4"
assert_eq "4: the pull refused (peer commit did not land)" "absent" "$(peer_file_state)"
assert_contains "4: setmode's own commit was made" "Set launch_mode=interactive" \
    "$(git -C "$WT" log -1 --format=%s)"

# --- Test 5: the runner's merge pull, disjoint edit ---
# Git's default merges around a dirty file the incoming commit does not touch,
# so the peer commit lands — which also proves the merge ran. Disjoint edits
# only: this cell says nothing about recovery from an overlapping one.
echo "--- Test 5: runner git_pull ignores merge.autoStash=true (disjoint) ---"
setup_crew_remote_fixture peer_only
dirty_agent_heartbeat
run_runner_pull
assert_dirty_untouched "5"
assert_eq "5: the merge ran (peer commit landed)" "present" "$(peer_file_state)"
assert_eq "5: HEAD is the remote head" "$(remote_head)" "$(git -C "$WT" rev-parse HEAD)"

# --- Test 6: the runner's merge pull, overlapping edit ---
# run_loop rewrites _runner_alive.yaml (update_runner_heartbeat) right before
# every git_pull. When an incoming commit touches that file, git's default
# merge refuses — on every iteration. This cell pins that accepted refusal: no
# stash, no rewrite, no merge state. It does NOT pin recovery; the remote stop
# request stays unseen, and convergence is the crew_runner_pull_refusal_recovery
# follow-up's scope (t2008's plan, Risk).
echo "--- Test 6: runner git_pull ignores merge.autoStash=true (overlapping) ---"
setup_crew_remote_fixture runner_stop
dirty_file="$WT/_runner_alive.yaml"
sed -e "s/^last_heartbeat: .*/last_heartbeat: '2026-10-15 10:05:00'/" \
    -e "s/^next_check_at: .*/next_check_at: '2026-10-15 10:05:30'/" \
    "$dirty_file" > "$dirty_file.tmp"
mv "$dirty_file.tmp" "$dirty_file"
dirty_sha="$(file_sha "$dirty_file")"
dirty_ident="$(file_ident "$dirty_file")"
head_before="$(git -C "$WT" rev-parse HEAD)"
run_runner_pull
assert_dirty_untouched "6"
assert_eq "6: the merge refused (HEAD did not move)" "$head_before" "$(git -C "$WT" rev-parse HEAD)"
assert_eq "6: no merge was left in progress" "" \
    "$(git -C "$WT" rev-parse -q --verify MERGE_HEAD 2>/dev/null)"

echo ""
echo "=== Results ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "TOTAL: $TOTAL"

[[ "$FAIL" -eq 0 ]] || { echo "SOME TESTS FAILED"; exit 1; }
echo "ALL TESTS PASSED"
