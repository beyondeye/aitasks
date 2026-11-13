#!/usr/bin/env bash
# test_model_stats_refresh_routes.sh - the aitask-stats refresh routes (t1912_1).
#
# Readers only read refs/heads/aitask-stats and never fetch, so another clone's
# stats reach this one only through a refresh route. Covered here, against the
# branch-mode sync fixture:
#   - `ait sync --batch` (aitask_sync.sh) and `aitask_pick_own.sh --sync` bring
#     a writer clone's counters in; the CLI `refresh` verb does too;
#   - the sync's --batch stdout status line and exit code are byte-identical
#     when the refresh fails (held ref lock, diverged local ref, broken CLI),
#     and each failure really ran (it is reported on stderr);
#   - with no aitask-stats branch on origin the refresh is silent.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

PASS=0
FAIL=0
TOTAL=0

. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/sync_fixture.sh"

set +e

CLI="$PROJECT_DIR/.aitask-scripts/aitask_model_stats.py"
PY="$(command -v python3)"

# The writer: a plain clone of the fixture's origin, recording via the CLI.
make_writer() {
    local t="$1"
    git clone -q "$t/remote.git" "$t/writer" 2>/dev/null
    git -C "$t/writer" config user.email w@test.com
    git -C "$t/writer" config user.name W
}

bump() {  # bump <tmpdir> — one usage run from the writer clone
    (sync_isolate_git_config
     "$PY" "$CLI" bump-usage --root "$1/writer" --agent claudecode --model opus \
         --skill pick --date 2026-11-12) >/dev/null
}

# Effective all_time runs as the fixture clone's loader sees them (no fetch).
local_runs() {
    (sync_isolate_git_config
     "$PY" "$CLI" export --root "$1/local" --agent claudecode) \
        | jq -r '.models.opus.usagestats.pick.all_time.runs // 0'
}

origin_tip() { git -C "$1/remote.git" rev-parse --verify -q refs/heads/aitask-stats; }
local_ref() { git -C "$1/local" rev-parse --verify -q refs/heads/aitask-stats; }

run_pick_sync() {
    local tmpdir="$1"
    (
        cd "$tmpdir/local" || exit 1
        sync_isolate_git_config
        export PATH="$PWD/bin:$PATH" TEST_HOSTNAME=testhost
        export AITASKS_LOCK_DIR="$tmpdir/locks"
        export AITASKS_TMUX_SOCKET="ait_syncfx_nosrv_$$"
        ./.aitask-scripts/aitask_pick_own.sh --sync 2>"$tmpdir/pick_stderr"
    )
}

echo "=== model-stats refresh routes ==="

echo "--- 1. no aitask-stats branch on origin: silent no-op ---"
T1="$(setup_repo)"
out1="$(run_sync "$T1")"; rc1=$?
assert_eq "sync ok with no stats branch" "0" "$rc1"
assert_not_contains "no refresh noise when the branch is absent" "model-stats" "$(sync_err "$T1")"
assert_eq "no local stats ref created" "" "$(local_ref "$T1")"
[[ -n "$out1" ]] || assert_eq "sync printed a status line" "non-empty" "empty"

echo "--- 2. ait sync brings the writer's counters in ---"
make_writer "$T1"
bump "$T1"; bump "$T1"
assert_eq "before sync: the loader does not fetch" "0" "$(local_runs "$T1")"
run_sync "$T1" >/dev/null; rc2=$?
assert_eq "sync ok" "0" "$rc2"
assert_eq "after sync: local ref = origin tip" "$(origin_tip "$T1")" "$(local_ref "$T1")"
assert_eq "after sync: the new value" "2" "$(local_runs "$T1")"
assert_not_contains "a successful refresh is quiet" "model-stats" "$(sync_err "$T1")"

echo "--- 3. aitask_pick_own.sh --sync brings them in too ---"
bump "$T1"
assert_eq "before pick sync: still 2" "2" "$(local_runs "$T1")"
pout="$(run_pick_sync "$T1")"
assert_contains "pick sync reports its own outcome" "SYNC" "$pout"
assert_not_contains "pick sync stdout carries no refresh text" "REFRESH" "$pout"
assert_eq "after pick sync: the new value" "3" "$(local_runs "$T1")"

echo "--- 4. the CLI refresh verb ---"
bump "$T1"
rout="$( (sync_isolate_git_config; "$PY" "$CLI" refresh --root "$T1/local") )"
assert_eq "refresh verb reports the tip" "REFRESHED:$(origin_tip "$T1")" "$rout"
assert_eq "after refresh verb: the new value" "4" "$(local_runs "$T1")"

echo "--- 5. --batch stdout is byte-identical when the refresh fails ---"
control="$(run_sync "$T1")"; control_rc=$?
assert_not_contains "control run: refresh quiet" "model-stats" "$(sync_err "$T1")"

# 5a. a held lock on the local stats ref
bump "$T1"
touch "$T1/local/.git/refs/heads/aitask-stats.lock"
o="$(run_sync "$T1")"; rc=$?
rm -f "$T1/local/.git/refs/heads/aitask-stats.lock"
assert_eq "held ref lock: stdout identical" "$control" "$o"
assert_eq "held ref lock: exit identical" "$control_rc" "$rc"
assert_contains "held ref lock: the failure was reported" "model-stats refresh: REFRESH_SKIPPED:error" "$(sync_err "$T1")"
assert_eq "held ref lock: local ref not moved" "4" "$(local_runs "$T1")"

# 5b. a diverged local ref
saved="$(local_ref "$T1")"
lonely="$(git -C "$T1/local" commit-tree "$(git -C "$T1/local" mktree </dev/null)" -m lonely)"
git -C "$T1/local" update-ref refs/heads/aitask-stats "$lonely"
o="$(run_sync "$T1")"; rc=$?
assert_eq "diverged: stdout identical" "$control" "$o"
assert_eq "diverged: exit identical" "$control_rc" "$rc"
assert_contains "diverged: reported" "model-stats refresh: STATS_DIVERGED:$lonely|" "$(sync_err "$T1")"
assert_eq "diverged: local ref not moved" "$lonely" "$(local_ref "$T1")"
git -C "$T1/local" update-ref refs/heads/aitask-stats "$saved"

# 5c. a broken CLI in the clone's framework copy
cli_copy="$T1/local/.aitask-scripts/aitask_model_stats.py"
cp "$cli_copy" "$T1/cli.bak"
printf 'import sys\nprint("GARBAGE")\nsys.exit(3)\n' > "$cli_copy"
o="$(run_sync "$T1")"; rc=$?
cp "$T1/cli.bak" "$cli_copy"
assert_eq "broken CLI: stdout identical" "$control" "$o"
assert_eq "broken CLI: exit identical" "$control_rc" "$rc"
assert_contains "broken CLI: reported" "model-stats refresh: GARBAGE" "$(sync_err "$T1")"

# The route still works once the faults are gone.
run_sync "$T1" >/dev/null
assert_eq "after the faults: caught up" "5" "$(local_runs "$T1")"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
