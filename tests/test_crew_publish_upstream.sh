#!/usr/bin/env bash
# test_crew_publish_upstream.sh - crew branches reach origin with an upstream
# (t2016).
#
# aitask_crew_init.sh creates crew-<id> with update-ref + worktree add, so the
# branch starts with no upstream. Before t2016 nothing ever ran `push -u`, and
# every crew push died with "has no upstream branch" (misreported as
# "offline?") unless the user set push.autoSetupRemote.
#
# Each crew entry point that pushes gets its own FIRST-publish cell (3-5): once
# an upstream exists, a bare `git push` succeeds under the default
# push.default=simple, so a cell that runs an entry point after init already
# published cannot tell the fixed push from the old one. make_offline_crew
# builds a crew whose branch is unpublished and has no upstream, then points
# origin at a real remote, so the entry point under test is the first push that
# can succeed.
#
# Run: bash tests/test_crew_publish_upstream.sh

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

# Developer git config never reaches this file: a global push.autoSetupRemote
# would give every crew branch an upstream and hide the defect. Sourced AFTER
# the counter initialisation, because the probe asserts.
. "$PROJECT_DIR/tests/lib/git_config_isolation.sh"
sync_isolate_git_config
assert_git_config_isolated

CLEANUP_DIRS=()
cleanup() {
    for d in "${CLEANUP_DIRS[@]}"; do
        # A failed hang cell may leave its TERM-ignoring transport stub alive.
        [[ -f "$d/hang.pids" ]] && xargs kill -KILL < "$d/hang.pids" 2>/dev/null
        rm -rf "$d" 2>/dev/null
    done
}
trap cleanup EXIT

# git's own text for an unreachable origin (git 2.x, local-path remote).
GIT_UNREACHABLE="does not appear to be a git repository"

# new_crew_repo — a fake aitask repo carrying the crew scripts, plus an empty
# bare remote that is NOT yet wired as origin.
# Sets: ROOT REPO REMOTE
new_crew_repo() {
    ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ait_crew_publish_XXXXXX")"
    CLEANUP_DIRS+=("$ROOT")
    REPO="$ROOT/repo"
    REMOTE="$ROOT/remote.git"

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

    git init --bare --quiet "$REMOTE"
}

# run_in_repo <cmd...> — run from $REPO; sets RC, OUT (stdout), ERR (stderr).
run_in_repo() {
    (cd "$REPO" && "$@") >"$ROOT/stdout" 2>"$ROOT/stderr"
    RC=$?
    OUT="$(cat "$ROOT/stdout")"
    ERR="$(cat "$ROOT/stderr")"
}

crew_init() {
    run_in_repo bash .aitask-scripts/aitask_crew_init.sh --id "$1" \
        --add-type impl:claudecode/opus4_6 --batch
}
crew_addwork() {
    run_in_repo bash .aitask-scripts/aitask_crew_addwork.sh --crew "$1" --name "$2" \
        --work2do /dev/null --type impl --batch
}
crew_setmode() {
    run_in_repo bash .aitask-scripts/aitask_crew_setmode.sh --crew "$1" --name "$2" \
        --mode interactive
}
# The real `ait crew status set` CLI, called the way
# tests/test_agentcrew_terminal_push.sh does (ait cd's to its own repo).
crew_status_set() {
    run_in_repo "$AITASK_PYTHON" "$PROJECT_DIR/.aitask-scripts/agentcrew/agentcrew_status.py" \
        --crew "$1" --agent "$2" set --status "$3"
}

crew_wt()    { echo "$REPO/.aitask-crews/crew-$1"; }
local_tip()  { git -C "$(crew_wt "$1")" rev-parse HEAD; }
remote_tip() { git -C "$REMOTE" rev-parse -q --verify "refs/heads/crew-$1" 2>/dev/null; }
upstream()   { git -C "$(crew_wt "$1")" rev-parse --abbrev-ref '@{u}' 2>/dev/null; }
remote_file() { git -C "$REMOTE" show "crew-$1:$2" 2>/dev/null; }

# assert_published <cell> <id> — the remote holds the crew branch at the local
# tip, and the local branch tracks it.
assert_published() {
    local cell="$1" id="$2"
    assert_eq "$cell: the remote crew branch is at the local tip" "$(local_tip "$id")" \
        "$(remote_tip "$id")"
    assert_eq "$cell: the crew branch tracks origin" "origin/crew-$id" "$(upstream "$id")"
}

# make_offline_crew <cell> <id> [agent] — init (and addwork <agent>) while origin
# points at a path that does not exist, then point origin at $REMOTE. Leaves the
# crew branch unpublished and without an upstream.
# Sets: OFFLINE_INIT_ERR OFFLINE_ADDWORK_ERR
make_offline_crew() {
    local cell="$1" id="$2" agent="${3:-}"
    OFFLINE_INIT_ERR=""
    OFFLINE_ADDWORK_ERR=""
    git -C "$REPO" remote add origin "$ROOT/no-such-remote.git"
    crew_init "$id"
    assert_eq "$cell: offline init exits 0" "0" "$RC"
    assert_contains "$cell: offline init still reports CREATED" "CREATED:$id" "$OUT"
    OFFLINE_INIT_ERR="$ERR"
    if [[ -n "$agent" ]]; then
        crew_addwork "$id" "$agent"
        assert_eq "$cell: offline addwork exits 0" "0" "$RC"
        assert_contains "$cell: offline addwork still reports ADDED" "ADDED:$agent" "$OUT"
        OFFLINE_ADDWORK_ERR="$ERR"
    fi
    assert_eq "$cell: fixture: no upstream while offline" "" "$(upstream "$id")"
    assert_eq "$cell: fixture: the remote has no crew branch" "" "$(remote_tip "$id")"
    git -C "$REPO" remote set-url origin "$REMOTE"
}

echo "=== crew branches are published with an upstream (t2016) ==="

# --- Test 1: init publishes ---
echo "--- Test 1: init publishes the crew branch ---"
new_crew_repo
git -C "$REPO" remote add origin "$REMOTE"
crew_init c1
assert_eq "1: init exits 0" "0" "$RC"
assert_contains "1: init reports CREATED" "CREATED:c1" "$OUT"
assert_not_contains "1: git's tracking message stays off stdout" "track" "$OUT"
assert_not_contains "1: no push warning" "push" "$ERR"
assert_published "1" c1

# --- Test 2: steady-state addwork (sanity; cells 3-5 discriminate) ---
echo "--- Test 2: addwork after an online init ---"
crew_addwork c1 w1
assert_eq "2: addwork exits 0" "0" "$RC"
assert_contains "2: addwork reports ADDED" "ADDED:w1" "$OUT"
assert_not_contains "2: git's tracking message stays off stdout" "track" "$OUT"
assert_not_contains "2: no push warning" "push" "$ERR"
assert_published "2" c1

# --- Test 3: offline init, then addwork is the first publish ---
echo "--- Test 3: offline init heals through addwork ---"
new_crew_repo
make_offline_crew "3" c3
assert_contains "3: the offline init warning carries git's own text" \
    "$GIT_UNREACHABLE" "$OFFLINE_INIT_ERR"
assert_not_contains "3: the offline init warning does not guess 'offline?'" \
    "offline?" "$OFFLINE_INIT_ERR"
crew_addwork c3 w1
assert_eq "3: addwork exits 0" "0" "$RC"
assert_contains "3: addwork reports ADDED" "ADDED:w1" "$OUT"
assert_not_contains "3: git's tracking message stays off stdout" "track" "$OUT"
assert_published "3" c3

# --- Test 4: offline crew, then setmode is the first publish ---
echo "--- Test 4: offline crew heals through setmode ---"
new_crew_repo
make_offline_crew "4" c4 w1
assert_contains "4: the offline addwork warning carries git's own text" \
    "$GIT_UNREACHABLE" "$OFFLINE_ADDWORK_ERR"
assert_not_contains "4: the offline addwork warning does not guess 'offline?'" \
    "offline?" "$OFFLINE_ADDWORK_ERR"
crew_setmode c4 w1
assert_eq "4: setmode exits 0" "0" "$RC"
assert_contains "4: setmode reports UPDATED" "UPDATED:w1:interactive" "$OUT"
assert_not_contains "4: git's tracking message stays off stdout" "track" "$OUT"
assert_published "4" c4
assert_contains "4: the remote carries the new launch mode" "launch_mode: interactive" \
    "$(remote_file c4 w1_status.yaml)"

# --- Test 5: offline crew, then a terminal status transition is the first publish ---
echo "--- Test 5: offline crew heals through 'ait crew status set' ---"
new_crew_repo
make_offline_crew "5" c5 w1
for st in Ready Running; do
    crew_status_set c5 w1 "$st"
    assert_eq "5: status set $st exits 0" "0" "$RC"
done
assert_eq "5: control: non-terminal transitions do not publish" "" "$(remote_tip c5)"
crew_status_set c5 w1 Completed
assert_eq "5: status set Completed exits 0" "0" "$RC"
assert_contains "5: status set reports the transition" "STATUS_SET:w1:Running:Completed" "$OUT"
assert_published "5" c5
assert_contains "5: the remote carries the terminal status" "status: Completed" \
    "$(remote_file c5 w1_status.yaml)"

# --- Test 6: no origin remote — nothing to publish, nothing to warn about ---
echo "--- Test 6: a repository without origin stays quiet ---"
new_crew_repo
crew_init c6
assert_eq "6: init exits 0" "0" "$RC"
assert_not_contains "6: init prints no push warning" "push" "$ERR"
crew_addwork c6 w1
assert_eq "6: addwork exits 0" "0" "$RC"
assert_contains "6: addwork reports ADDED" "ADDED:w1" "$OUT"
assert_not_contains "6: addwork prints no push warning" "push" "$ERR"
assert_eq "6: no upstream without origin" "" "$(upstream c6)"

# --- Test 7: the Python helper, no origin, non-batch ---
echo "--- Test 7: git_commit_push_if_changes without origin stays quiet ---"
wt7="$(crew_wt c6)"
echo "note" > "$wt7/note.txt"
head_before="$(git -C "$wt7" rev-parse HEAD)"
py_err="$("$AITASK_PYTHON" -c '
import sys
sys.path.insert(0, sys.argv[1])
from agentcrew_utils import git_commit_push_if_changes
git_commit_push_if_changes(sys.argv[2], "test: commit", batch=False)
' "$PROJECT_DIR/.aitask-scripts/agentcrew" "$wt7" 2>&1 >/dev/null)"
assert_eq "7: control: the change was committed (the push step was reached)" "different" \
    "$([[ "$(git -C "$wt7" rev-parse HEAD)" != "$head_before" ]] && echo different || echo same)"
assert_not_contains "7: no push warning without origin" "git push warning" "$py_err"

# --- Test 8: the push names its destination ---
echo "--- Test 8: push.default=matching does not publish other branches ---"
new_crew_repo
git -C "$REPO" remote add origin "$REMOTE"
primary="$(git -C "$REPO" symbolic-ref --short HEAD)"
git -C "$REPO" push --quiet origin "$primary" 2>/dev/null
primary_remote_before="$(git -C "$REMOTE" rev-parse "refs/heads/$primary")"
git -C "$REPO" commit --allow-empty -m "local only" --quiet
git -C "$REPO" config push.default matching
assert_eq "8: fixture: the local primary is ahead of the remote" "1" \
    "$(git -C "$REPO" rev-list --count "$primary_remote_before..$primary")"
crew_init c8
crew_addwork c8 w1
assert_eq "8: addwork exits 0" "0" "$RC"
assert_published "8" c8
assert_eq "8: the remote primary branch is untouched" "$primary_remote_before" \
    "$(git -C "$REMOTE" rev-parse "refs/heads/$primary")"

# --- Bounded network operations (t2024) ---
# An origin that is routable but never answers must not stall any crew write.
# make_hanging_origin points origin at an ssh URL whose transport (a configured
# core.sshCommand stub) never answers: it records its pid, ignores SIGTERM and
# sleeps 30s, so it dies only when the bound kills the operation's whole
# process group with SIGKILL. AIT_BOUNDED_RUN_GRACE=1 shortens the TERM→KILL
# grace that stub always waits out; tests/test_bounded_run.py owns the grace
# itself. Every elapsed bound below sits far under the stub's 30s.
make_hanging_origin() {
    HANG_PIDS="$ROOT/hang.pids"
    : > "$HANG_PIDS"
    cat > "$ROOT/hang-ssh" <<EOF
#!/bin/sh
echo \$\$ >> "$HANG_PIDS"
trap '' TERM
exec sleep 30
EOF
    chmod +x "$ROOT/hang-ssh"
    git -C "$REPO" config core.sshCommand "$ROOT/hang-ssh"
    git -C "$REPO" config ssh.variant ssh
    if git -C "$REPO" remote get-url origin >/dev/null 2>&1; then
        git -C "$REPO" remote set-url origin "ssh://crew-hang.invalid/repo.git"
    else
        git -C "$REPO" remote add origin "ssh://crew-hang.invalid/repo.git"
    fi
}

# assert_hang_reaped <cell> [times] — the transport was reached ([times] times),
# and every stub process is gone.
assert_hang_reaped() {
    local cell="$1" times="${2:-}" pid alive=""
    sleep 0.3   # let the kernel finish reaping
    assert_eq "$cell: fixture: the hanging transport was reached" "yes" \
        "$([[ -s "$HANG_PIDS" ]] && echo yes || echo no)"
    if [[ -n "$times" ]]; then
        assert_eq "$cell: the transport was reached $times time(s)" "$times" \
            "$(wc -l < "$HANG_PIDS" | tr -d ' ')"
    fi
    while read -r pid; do
        kill -0 "$pid" 2>/dev/null && alive="$alive $pid"
    done < "$HANG_PIDS"
    assert_eq "$cell: every hanging transport process was killed" "" "$alive"
}

# within <cell> <what> <max-seconds> <elapsed>
within() {
    assert_eq "$1: $2 returns within ${3}s (the stub hangs 30s)" "yes" \
        "$( (( $4 <= $3 )) && echo yes || echo "no: ${4}s")"
}

echo "--- Test 9: fixture control: the hanging origin stalls an unbounded call ---"
new_crew_repo
make_hanging_origin
git -C "$REPO" ls-remote origin >/dev/null 2>&1 &
ctl_pid=$!
sleep 3
assert_eq "9: control: a plain git ls-remote is still waiting after 3s" "running" \
    "$(kill -0 "$ctl_pid" 2>/dev/null && echo running || echo exited)"
kill -KILL "$ctl_pid" 2>/dev/null
xargs kill -KILL < "$HANG_PIDS" 2>/dev/null
wait "$ctl_pid" 2>/dev/null

export AIT_CREW_GIT_TIMEOUT=2 AIT_BOUNDED_RUN_GRACE=1

echo "--- Test 10: init against a hanging origin is bounded ---"
: > "$HANG_PIDS"
start=$SECONDS
crew_init c10
within "10" "init" 10 $(( SECONDS - start ))
assert_eq "10: init exits 0" "0" "$RC"
assert_contains "10: init still reports CREATED" "CREATED:c10" "$OUT"
assert_contains "10: the warning names the timeout" "timed out after 2s" "$ERR"
assert_contains "10: the warning names the knob" "AIT_CREW_GIT_TIMEOUT" "$ERR"
assert_not_contains "10: nothing from git reaches stdout" "track" "$OUT"
assert_eq "10: a timed-out push sets no upstream" "" "$(upstream c10)"
assert_hang_reaped "10" 1

echo "--- Test 11: a timed-out init heals through the next publish ---"
git -C "$REPO" remote set-url origin "$REMOTE"
crew_addwork c10 w1
assert_eq "11: addwork exits 0" "0" "$RC"
assert_contains "11: addwork reports ADDED" "ADDED:w1" "$OUT"
assert_published "11" c10

echo "--- Test 12: addwork against a hanging origin (fetch and push bounded) ---"
new_crew_repo
git -C "$REPO" remote add origin "$REMOTE"
crew_init c12
crew_addwork c12 w1
assert_published "12: fixture" c12
remote_before="$(remote_tip c12)"
make_hanging_origin
start=$SECONDS
crew_addwork c12 w2
within "12" "addwork" 16 $(( SECONDS - start ))
assert_eq "12: addwork exits 0" "0" "$RC"
assert_contains "12: addwork reports ADDED" "ADDED:w2" "$OUT"
assert_contains "12: the push warning names the timeout" "timed out after 2s" "$ERR"
assert_hang_reaped "12" 2
assert_contains "12: the agent was committed locally" "crew: Add agent 'w2'" \
    "$(git -C "$(crew_wt c12)" log -1 --format=%s)"
assert_eq "12: the remote is untouched" "$remote_before" "$(remote_tip c12)"
assert_eq "12: the upstream survives" "origin/crew-c12" "$(upstream c12)"

echo "--- Test 13: setmode against a hanging origin ---"
: > "$HANG_PIDS"
start=$SECONDS
crew_setmode c12 w1
within "13" "setmode" 16 $(( SECONDS - start ))
assert_eq "13: setmode exits 0" "0" "$RC"
assert_contains "13: setmode reports UPDATED" "UPDATED:w1:interactive" "$OUT"
assert_hang_reaped "13" 2
assert_contains "13: the change was committed locally" "Set launch_mode=interactive" \
    "$(git -C "$(crew_wt c12)" log -1 --format=%s)"
assert_eq "13: the remote is untouched" "$remote_before" "$(remote_tip c12)"

echo "--- Test 14: a terminal 'ait crew status set' against a hanging origin ---"
for st in Ready Running; do
    crew_status_set c12 w1 "$st"
done
: > "$HANG_PIDS"
start=$SECONDS
crew_status_set c12 w1 Completed
within "14" "status set" 10 $(( SECONDS - start ))
assert_eq "14: status set exits 0" "0" "$RC"
assert_contains "14: status set reports the transition" "STATUS_SET:w1:Running:Completed" "$OUT"
# status set pushes with batch=True, which never warns: the timeout is silent
# like any other failed push there, and must not surface as a traceback.
assert_not_contains "14: the timed-out push is silent (batch push)" "git push warning" "$ERR"
assert_not_contains "14: no traceback" "Traceback" "$ERR"
assert_hang_reaped "14" 1
assert_eq "14: the remote is untouched" "$remote_before" "$(remote_tip c12)"

echo "--- Test 15: the runner's git_pull against a hanging origin ---"
: > "$HANG_PIDS"
start=$SECONDS
pull_out="$("$AITASK_PYTHON" -c '
import sys
sys.path.insert(0, sys.argv[1])
from agentcrew_utils import crew_merge_state, git_pull
status, detail = git_pull(sys.argv[2], batch=False)
print(f"PULL_RESULT:{status}|{detail}")
print(f"MERGE_STATE:{crew_merge_state(sys.argv[2])}")
' "$PROJECT_DIR/.aitask-scripts/agentcrew" "$(crew_wt c12)" 2>"$ROOT/pull.err")"
within "15" "git_pull" 10 $(( SECONDS - start ))
assert_contains "15: the pull defers on the timed-out fetch" \
    "PULL_RESULT:deferred|fetch_failed: timed out after 2s" "$pull_out"
assert_contains "15: non-batch warns" "git pull warning: fetch_failed: timed out" \
    "$(cat "$ROOT/pull.err")"
assert_contains "15: no merge state is left" "MERGE_STATE:None" "$pull_out"
assert_hang_reaped "15" 1

unset AIT_CREW_GIT_TIMEOUT AIT_BOUNDED_RUN_GRACE

echo "--- Test 16: AIT_CREW_GIT_TIMEOUT is normalized ---"
for pair in ":10" "0:10" "-1:10" "abc:10" "08x:10" "1234567:10" "08:8" "3:3"; do
    raw="${pair%:*}"
    want="${pair##*:}"
    got="$(AIT_CREW_GIT_TIMEOUT="$raw" bash -c \
        '. "$1/.aitask-scripts/lib/agentcrew_utils.sh" && crew_git_timeout' _ "$PROJECT_DIR")"
    assert_eq "16: AIT_CREW_GIT_TIMEOUT='$raw' → $want" "$want" "$got"
done

echo ""
echo "=== Results ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "TOTAL: $TOTAL"

[[ "$FAIL" -eq 0 ]] || { echo "SOME TESTS FAILED"; exit 1; }
echo "ALL TESTS PASSED"
