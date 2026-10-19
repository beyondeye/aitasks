#!/usr/bin/env bash
# test_crew_branch_delete_bounded.sh - the crew-branch deletion pushes are
# bounded (t2036).
#
# t2024 bounded every crew WRITE to origin; the three remote-branch deletions
# followed here: `ait crew cleanup --delete-branch`, the stale-branch fallback in
# `ait brainstorm delete`, and the brainstorm TUI's "clean and retry" worker. Each
# site gets a reachable-origin control (the routed push still deletes the remote
# branch) and a hanging-origin cell (bounded, local cleanup completes, the
# transport is reaped).
#
# The hanging origin is the fixture of tests/test_crew_publish_upstream.sh
# Tests 9-15, reproduced here: an ssh URL whose core.sshCommand stub ignores
# SIGTERM and sleeps 30s, so it dies only when the bound kills its group.
#
# Run: bash tests/test_crew_branch_delete_bounded.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=lib/venv_python.sh
. "$PROJECT_DIR/tests/lib/venv_python.sh"

PASS=0
FAIL=0
TOTAL=0

# Developer git config never reaches this file (a global push default or hook
# would change what the deletions do). Sourced after the counters: it asserts.
. "$PROJECT_DIR/tests/lib/git_config_isolation.sh"
sync_isolate_git_config
assert_git_config_isolated

CLEANUP_DIRS=()
cleanup() {
    for d in "${CLEANUP_DIRS[@]}"; do
        # A failed hang cell may leave its TERM-ignoring transport stub alive.
        [[ -f "$d/hang.pids" ]] && xargs kill -KILL < "$d/hang.pids" 2>/dev/null
        if [[ -d "$d/repo" ]]; then
            git -C "$d/repo" worktree prune 2>/dev/null
        fi
        rm -rf "$d" 2>/dev/null
    done
}
trap cleanup EXIT

# new_repo — a fake aitask repo carrying the whole script tree, a t999 task for
# brainstorm init, and an empty bare remote wired as origin.
# Sets: ROOT REPO REMOTE
new_repo() {
    ROOT="$(mktemp -d "${TMPDIR:-/tmp}/ait_crew_delete_XXXXXX")"
    CLEANUP_DIRS+=("$ROOT")
    REPO="$ROOT/repo"
    REMOTE="$ROOT/remote.git"

    mkdir -p "$REPO/aitasks/metadata"
    git -C "$REPO" init --quiet
    git -C "$REPO" config user.email "test@test.com"
    git -C "$REPO" config user.name "Test"
    cp -R "$PROJECT_DIR/.aitask-scripts" "$REPO/.aitask-scripts"
    find "$REPO/.aitask-scripts" -type d -name __pycache__ -prune -exec rm -rf {} +
    echo "email: test@test.com" > "$REPO/aitasks/metadata/userconfig.yaml"
    # brainstorm crew init looks up an agent_string per role here.
    cp "$PROJECT_DIR/aitasks/metadata/codeagent_config.json" "$REPO/aitasks/metadata/"
    cat > "$REPO/aitasks/t999_test_brainstorm.md" <<'TASK'
---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [test]
---

## Test task for brainstorm delete.
TASK
    git -C "$REPO" add -A
    git -C "$REPO" commit -m "Initial setup" --quiet

    git init --bare --quiet "$REMOTE"
    git -C "$REPO" remote add origin "$REMOTE"
}

# run_in_repo <cmd...> — run from $REPO; sets RC, OUT (stdout), ERR (stderr).
run_in_repo() {
    (cd "$REPO" && "$@") >"$ROOT/stdout" 2>"$ROOT/stderr"
    RC=$?
    OUT="$(cat "$ROOT/stdout")"
    ERR="$(cat "$ROOT/stderr")"
}

local_branch()  { git -C "$REPO" rev-parse -q --verify "refs/heads/$1" 2>/dev/null; }
remote_branch() { git -C "$REMOTE" rev-parse -q --verify "refs/heads/$1" 2>/dev/null; }

# make_terminal_crew <id> — an empty crew, published to origin, whose persisted
# status is Completed (crew_is_terminal's empty-crew fallback).
make_terminal_crew() {
    run_in_repo bash .aitask-scripts/aitask_crew_init.sh --id "$1" \
        --add-type impl:claudecode/opus4_6 --batch
    local cf="$REPO/.aitask-crews/crew-$1/_crew_status.yaml"
    sed "s/^status: .*/status: Completed/" "$cf" > "$cf.tmp" && mv "$cf.tmp" "$cf"
}

# make_stale_brainstorm — init the t999 brainstorm and publish its crew branch.
make_stale_brainstorm() {
    run_in_repo bash .aitask-scripts/aitask_brainstorm_init.sh 999
    git -C "$REPO/.aitask-crews/crew-brainstorm-999" push --quiet origin \
        HEAD:refs/heads/crew-brainstorm-999 2>/dev/null
}

# make_hanging_origin — point origin at an ssh URL whose transport never answers
# (records its pid, ignores SIGTERM, sleeps 30s).
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
    git -C "$REPO" remote set-url origin "ssh://crew-hang.invalid/repo.git"
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

# tui_clean_and_retry — run BrainstormApp._cleanup_stale_crew_branch_and_retry's
# real body inline (Textual's @work applies functools.wraps, so __wrapped__ is
# the undecorated function) from $REPO, with a mock app recording every
# call_from_thread dispatch. Sets TUI_OUT.
tui_clean_and_retry() {
    TUI_OUT="$(cd "$REPO" && "$AITASK_PYTHON" -c '
import sys
from unittest.mock import MagicMock
sys.path.insert(0, sys.argv[1])
from brainstorm.brainstorm_app import BrainstormApp
app = MagicMock()
app.task_num = "999"
BrainstormApp._cleanup_stale_crew_branch_and_retry.__wrapped__(app)
first = app.call_from_thread.call_args_list[0][0]
print("DISPATCH:" + ("notify" if first[0] is app.notify else "failure"))
print("ARGS:" + " ".join(str(a) for a in first[1:]))
' "$PROJECT_DIR/.aitask-scripts" 2>&1)"
}

echo "=== crew-branch deletion pushes are bounded (t2036) ==="

echo "--- Test 1: fixture control: the hanging origin stalls an unbounded delete ---"
new_repo
make_hanging_origin
git -C "$REPO" push origin --delete crew-x >/dev/null 2>&1 &
ctl_pid=$!
sleep 3
assert_eq "1: control: a plain git push --delete is still waiting after 3s" "running" \
    "$(kill -0 "$ctl_pid" 2>/dev/null && echo running || echo exited)"
kill -KILL "$ctl_pid" 2>/dev/null
xargs kill -KILL < "$HANG_PIDS" 2>/dev/null
wait "$ctl_pid" 2>/dev/null

echo "--- Test 2: crew cleanup deletes the remote branch (reachable origin) ---"
new_repo
make_terminal_crew c2
assert_eq "2: fixture: the crew branch was published" "yes" \
    "$([[ -n "$(remote_branch crew-c2)" ]] && echo yes || echo no)"
run_in_repo bash .aitask-scripts/aitask_crew_cleanup.sh --crew c2 --delete-branch --batch
assert_eq "2: cleanup exits 0" "0" "$RC"
assert_contains "2: cleanup reports CLEANED" "CLEANED:c2" "$OUT"
assert_eq "2: the local branch is gone" "" "$(local_branch crew-c2)"
assert_eq "2: the remote branch is gone" "" "$(remote_branch crew-c2)"

echo "--- Test 3: brainstorm delete deletes the remote branch (reachable origin) ---"
new_repo
make_stale_brainstorm
assert_eq "3: fixture: the crew branch was published" "yes" \
    "$([[ -n "$(remote_branch crew-brainstorm-999)" ]] && echo yes || echo no)"
run_in_repo bash .aitask-scripts/aitask_brainstorm_delete.sh 999 --yes
assert_eq "3: delete exits 0" "0" "$RC"
assert_contains "3: delete reports DELETED" "DELETED:999" "$OUT"
assert_eq "3: the local branch is gone" "" "$(local_branch crew-brainstorm-999)"
assert_eq "3: the remote branch is gone" "" "$(remote_branch crew-brainstorm-999)"

echo "--- Test 4: TUI clean-and-retry deletes the remote branch (reachable origin) ---"
new_repo
make_stale_brainstorm
rm -rf "$REPO/.aitask-crews/crew-brainstorm-999"   # the stale state: branch, no worktree
tui_clean_and_retry
assert_contains "4: the retry takes the success path" "DISPATCH:notify" "$TUI_OUT"
assert_eq "4: the local branch is gone" "" "$(local_branch crew-brainstorm-999)"
assert_eq "4: the remote branch is gone" "" "$(remote_branch crew-brainstorm-999)"

export AIT_CREW_GIT_TIMEOUT=2 AIT_BOUNDED_RUN_GRACE=1

echo "--- Test 5: crew cleanup against a hanging origin is bounded ---"
new_repo
make_terminal_crew c5
make_hanging_origin
start=$SECONDS
run_in_repo bash .aitask-scripts/aitask_crew_cleanup.sh --crew c5 --delete-branch --batch
within "5" "cleanup" 10 $(( SECONDS - start ))
assert_eq "5: cleanup exits 0" "0" "$RC"
assert_contains "5: cleanup still reports CLEANED" "CLEANED:c5" "$OUT"
assert_eq "5: the timed-out delete stays silent" "" "$ERR"
assert_eq "5: the worktree is gone" "no" \
    "$([[ -d "$REPO/.aitask-crews/crew-c5" ]] && echo yes || echo no)"
assert_eq "5: the local branch is gone" "" "$(local_branch crew-c5)"
assert_hang_reaped "5" 1

echo "--- Test 6: brainstorm delete against a hanging origin is bounded ---"
new_repo
make_stale_brainstorm
make_hanging_origin
start=$SECONDS
run_in_repo bash .aitask-scripts/aitask_brainstorm_delete.sh 999 --yes
within "6" "brainstorm delete" 10 $(( SECONDS - start ))
assert_eq "6: delete exits 0" "0" "$RC"
assert_contains "6: delete still reports DELETED" "DELETED:999" "$OUT"
assert_contains "6: the stale local branch is removed" \
    "Cleaned: stale crew-brainstorm-999 branch removed" "$OUT$ERR"
assert_eq "6: the local branch is gone" "" "$(local_branch crew-brainstorm-999)"
assert_hang_reaped "6" 1

echo "--- Test 7: TUI clean-and-retry against a hanging origin is bounded ---"
new_repo
make_stale_brainstorm
rm -rf "$REPO/.aitask-crews/crew-brainstorm-999"
make_hanging_origin
start=$SECONDS
tui_clean_and_retry
within "7" "clean-and-retry" 10 $(( SECONDS - start ))
assert_contains "7: a timed-out remote delete does not fail the retry" "DISPATCH:notify" "$TUI_OUT"
assert_not_contains "7: no traceback" "Traceback" "$TUI_OUT"
assert_eq "7: the local branch is gone" "" "$(local_branch crew-brainstorm-999)"
assert_hang_reaped "7" 1

unset AIT_CREW_GIT_TIMEOUT AIT_BOUNDED_RUN_GRACE

echo ""
echo "=== Results ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "TOTAL: $TOTAL"

[[ "$FAIL" -eq 0 ]] || { echo "SOME TESTS FAILED"; exit 1; }
echo "ALL TESTS PASSED"
