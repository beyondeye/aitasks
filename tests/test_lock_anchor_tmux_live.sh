#!/usr/bin/env bash
# test_lock_anchor_tmux_live.sh — LIVE isolated-tmux proof of the task lock's
# DEFAULT anchor rung (t1465).
#
# `tests/test_crash_recovery_pid_anchor.sh` pins the same anchor contract
# without tmux: it drives the writer through the `AIT_AGENT_PID` override seam,
# and it drives the tmux rung's FAILURE branch (unreachable socket → UNKNOWN).
# Neither exercises the rung every managed agent actually uses.
#
# That gap is dangerous in one specific way: a socket mismatch, a quoting slip,
# or an over-strict same-server guard in `ait_tmux_self_pane_pid` would make
# every real claim silently record `pid: -`. The claim still succeeds, the
# whole non-live suite still passes, and crash detection is simply gone. Only
# a real pane can answer whether the resolved pid is the RIGHT one.
#
# What this asserts, against a throwaway tmux server:
#   1. A claim executed INSIDE a pane, with no AIT_AGENT_PID override, records
#      an anchor equal to that pane's `#{pane_pid}`.
#   2. That anchor is not the UNKNOWN sentinel (stated separately, so a
#      regression reads as "fell back to UNKNOWN", not as a bare inequality).
#   3. The recorded token + kind read back as `alive` while the pane is up.
#   4. NEGATIVE CONTROL: the identical claim, in a real pane, with only the
#      gateway socket repointed at a server that does not exist, records `-`.
#      Without this, assertion 1 could pass vacuously on a broken guard.
#
# Isolation: creates its own server on a private `-L` socket and kills it in a
# trap. `require_isolated_tmux` additionally detaches this process from any
# inherited server, so a stray call cannot reach the user's session. This test
# arms no hooks and kills no shared server, so it does NOT need
# `require_clean_ait_server` (every framework tmux call it triggers is
# gateway-routed).
#
# Not part of tests/run_all_python_tests.sh (a bash test, deliberately opt-in).
#
# Run: bash tests/test_lock_anchor_tmux_live.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=../.aitask-scripts/lib/pid_anchor.sh
. "$PROJECT_DIR/.aitask-scripts/lib/pid_anchor.sh"

PASS=0
FAIL=0
TOTAL=0

if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not available"
    exit 0
fi

# shellcheck source=lib/tmux_isolation.sh
. "$SCRIPT_DIR/lib/tmux_isolation.sh"
require_isolated_tmux

# The override must be absent for the DEFAULT rung to be what is measured.
unset AIT_AGENT_PID

# Set up paired bare+local repo, copy framework files, init lock branch.
# Per-file fixture, matching the convention of the other lock tests (each of
# tests/test_task_lock.sh, test_lock_force.sh, test_lock_reclaim.sh,
# test_lock_diag.sh, test_crash_recovery_pid_anchor.sh carries its own).
setup_paired_repos() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    git init --bare --quiet "$tmpdir/remote.git"
    git clone --quiet "$tmpdir/remote.git" "$tmpdir/local" 2>/dev/null
    (
        cd "$tmpdir/local"
        git config user.email "test@test.com"
        git config user.name "Test"

        mkdir -p aitasks/archived aitasks/metadata aiplans bin

        cat > aitasks/t1_test_task.md <<'TASK'
---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: []
created_at: 2026-01-01 00:00
updated_at: 2026-01-01 00:00
---

Test task for the live tmux anchor test.
TASK

        cat > bin/hostname <<'SH'
#!/usr/bin/env bash
echo "${TEST_HOSTNAME:-unknown-host}"
SH
        chmod +x bin/hostname

        setup_fake_aitask_repo "$PWD"
        cp "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_pick_own.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/pid_anchor.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/ait" . 2>/dev/null || true
        chmod +x .aitask-scripts/*.sh ait 2>/dev/null || true

        git add -A
        git commit -m "Initial setup" --quiet
        git push --quiet 2>/dev/null
    )

    echo "$tmpdir"
}

lock_field() {
    local tmpdir="$1" key="$2"
    (cd "$tmpdir/local" && git fetch origin aitask-locks --quiet 2>/dev/null \
        && git show "origin/aitask-locks:t1_lock.yaml" 2>/dev/null) \
        | awk -v k="^${key}:" '$0 ~ k { sub(/^[^:]*: */, ""); print; exit }'
}

# Wait (bounded) for the in-pane claim to write its exit-status file. Polling a
# result FILE rather than capture-pane: the claim redirects its own output, so
# there is nothing on screen to capture.
wait_for_claim() {
    local rc_file="$1" _i
    for _i in $(seq 1 120); do
        [[ -s "$rc_file" ]] && return 0
        sleep 0.25
    done
    return 1
}

SOCK="ait_anchorlive_$$"
TMPDIR_LIVE=""

cleanup() {
    tmux -L "$SOCK" kill-server 2>/dev/null || true
    [[ -n "$TMPDIR_LIVE" ]] && rm -rf "$TMPDIR_LIVE"
}
trap cleanup EXIT

TMPDIR_LIVE="$(setup_paired_repos)"
LOCAL_DIR="$TMPDIR_LIVE/local"
(cd "$LOCAL_DIR" && PATH="$LOCAL_DIR/bin:$PATH" TEST_HOSTNAME=pc-A \
    ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1)

set +e

echo "=== Lock anchor: live tmux pane rung (t1465) ==="
echo ""

# --- Case A: a real in-pane claim anchors to the pane's own process ---------
#
# The claim runs as the pane's command, so tmux — not the fixture — supplies
# $TMUX and $TMUX_PANE. Setting those by hand would test the fixture instead of
# the product. The trailing `sleep` keeps the pane (and therefore the anchored
# process) alive while the assertions run.

echo "--- Case A: in-pane claim records the pane's pid ---"

# Resolve the pane's PATH in THIS shell: a `$PATH` left for the inner shell
# would sit inside single quotes and never expand.
INNER_PATH="$LOCAL_DIR/bin:$PATH"

claim_cmd="cd '$LOCAL_DIR' && PATH='$INNER_PATH' TEST_HOSTNAME=pc-A"
claim_cmd="$claim_cmd AITASKS_TMUX_SOCKET='$SOCK'"
claim_cmd="$claim_cmd ./.aitask-scripts/aitask_pick_own.sh 1 --email 'alice@test.com'"
claim_cmd="$claim_cmd > claim.out 2>&1; echo \$? > claim.rc; sleep 120"

tmux -L "$SOCK" new-session -d -x 80 -y 10 -n anchor "$claim_cmd" 2>/dev/null

PANE_PID=""
for _ in $(seq 1 20); do
    PANE_PID=$(tmux -L "$SOCK" list-panes -F '#{pane_pid}' 2>/dev/null | head -1)
    [[ -n "$PANE_PID" ]] && break
    sleep 0.2
done

TOTAL=$((TOTAL + 1))
if [[ -n "$PANE_PID" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: could not start a test pane"
fi

if [[ -n "$PANE_PID" ]] && wait_for_claim "$LOCAL_DIR/claim.rc"; then
    claim_rc=$(cat "$LOCAL_DIR/claim.rc")
    claim_out=$(cat "$LOCAL_DIR/claim.out" 2>/dev/null)

    assert_eq "In-pane claim exits 0" "0" "$claim_rc"
    assert_contains "In-pane claim succeeds" "OWNED:1" "$claim_out"

    rec_pid=$(lock_field "$TMPDIR_LIVE" pid)
    rec_tok=$(lock_field "$TMPDIR_LIVE" pid_starttime)
    rec_kind=$(lock_field "$TMPDIR_LIVE" pid_starttime_kind)

    # The headline assertion: the anchor IS the pane process.
    assert_eq "Anchor equals the pane's pane_pid" "$PANE_PID" "$rec_pid"
    # Stated separately so a regression reports the actual failure mode.
    TOTAL=$((TOTAL + 1))
    if [[ "$rec_pid" != "$AIT_PID_ANCHOR_UNKNOWN" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: the tmux rung did not resolve — anchor fell back to UNKNOWN"
    fi
    assert_eq "Identity token recorded" "$(get_pid_starttime "$PANE_PID")" "$rec_tok"
    assert_eq "Token kind recorded" "$(get_pid_starttime_kind "$PANE_PID")" "$rec_kind"
    assert_eq "Anchor reads back as alive while the pane is up" \
        "alive" "$(lock_holder_liveness "$rec_pid" "$rec_tok" "$rec_kind")"
else
    TOTAL=$((TOTAL + 1)); FAIL=$((FAIL + 1))
    echo "FAIL: in-pane claim did not finish within the budget"
fi

# --- Case B: negative control — same pane shape, unreachable gateway socket --
#
# Identical claim in a real pane; the ONLY change is that the gateway is
# pointed at a server that does not exist, so `ait_tmux_self_pane_pid` cannot
# confirm the pane. This proves Case A's equality can fail, i.e. that it is not
# passing for some incidental reason.

echo "--- Case B: negative control (gateway socket repointed) ---"

nc_cmd="cd '$LOCAL_DIR' && PATH='$INNER_PATH' TEST_HOSTNAME=pc-A"
nc_cmd="$nc_cmd AITASKS_TMUX_SOCKET='ait_nonexistent_$$'"
nc_cmd="$nc_cmd ./.aitask-scripts/aitask_pick_own.sh 1 --email 'alice@test.com'"
nc_cmd="$nc_cmd > claim2.out 2>&1; echo \$? > claim2.rc; sleep 60"

tmux -L "$SOCK" new-window -d -n negctrl "$nc_cmd" 2>/dev/null

if wait_for_claim "$LOCAL_DIR/claim2.rc"; then
    assert_eq "Negative-control claim still exits 0" "0" "$(cat "$LOCAL_DIR/claim2.rc")"
    assert_contains "Negative-control claim still succeeds" "OWNED:1" \
        "$(cat "$LOCAL_DIR/claim2.out" 2>/dev/null)"
    assert_eq "Unreachable gateway ⇒ UNKNOWN anchor" \
        "$AIT_PID_ANCHOR_UNKNOWN" "$(lock_field "$TMPDIR_LIVE" pid)"
else
    TOTAL=$((TOTAL + 1)); FAIL=$((FAIL + 1))
    echo "FAIL: negative-control claim did not finish within the budget"
fi

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
