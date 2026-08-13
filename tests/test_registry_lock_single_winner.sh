#!/usr/bin/env bash
# test_registry_lock_single_winner.sh - production contention test for the
# registry mutex (t1507), end-to-end through a real consumer: `ait projects add`.
#
# This is the t1073 scenario itself — `ait projects add` runs silently on every
# tmux session bootstrap, so a restart burst launches many concurrent
# whole-file read-modify-writes of ~/.config/aitasks/projects.yaml. Pins:
#   - a lock whose holder PID is alive is NEVER displaced, however old its
#     mtime — the add dies busy with the holder's lock intact and writes nothing;
#   - K contenders racing through one dead-holder lock serialize: exactly K
#     registry entries, exactly ONE reclaim, no lock or guard left behind.
#
# WHAT THIS TEST IS NOT. It does not pin the observe-then-destruct race the
# conversion closed: nothing in a free-running race forces one contender to form
# a staleness verdict and act on it AFTER another reclaimed and re-published, so
# this construction can pass against racy code. Its failure mode is a LOST
# UPDATE, which is what t1073 was about. The ordering pin is the forced
# interleaving (plus its negative control) in tests/test_registry_lock.sh
# cases 10-11; the two are complementary and neither substitutes for the other.
#
# Run: bash tests/test_registry_lock_single_winner.sh
# Expected runtime: ~15s (one ~10s exhaustion against the live holder).

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=lib/proc_fixtures.sh
. "$PROJECT_DIR/tests/lib/proc_fixtures.sh"

PASS=0
FAIL=0
TOTAL=0

PROJECTS="$PROJECT_DIR/.aitask-scripts/aitask_projects.sh"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_reglock_sw_XXXXXX")"
HOLDER_PID=""
cleanup() {
    [[ -n "$HOLDER_PID" ]] && kill "$HOLDER_PID" 2>/dev/null
    rm -rf "$TMP"
}
trap cleanup EXIT

# Isolated registry via the documented seam — never the user's real one.
REGISTRY="$TMP/projects.yaml"
export AITASKS_PROJECTS_INDEX="$REGISTRY"
LOCKD="${REGISTRY}.lockd"

K=4
for i in $(seq 1 "$K"); do
    mkdir -p "$TMP/proj$i/aitasks/metadata"
    printf 'project:\n  name: fixture_proj%s\n' "$i" \
        > "$TMP/proj$i/aitasks/metadata/project_config.yaml"
done

# Count registry entries matching <pattern> (default: any). A missing registry
# file is 0 entries, not the empty string — grep on a nonexistent path prints
# nothing, and "" would compare unequal to "0" and report a confusing failure
# for the perfectly ordinary "nothing was written" case.
entry_count() {
    local pat="${1:-^  - name: }" n=0
    if [[ -f "$REGISTRY" ]]; then
        n=$(grep -c "$pat" "$REGISTRY" 2>/dev/null || true)
    fi
    printf '%s\n' "${n:-0}"
}

# dead_pid_fixture() comes from tests/lib/proc_fixtures.sh (sourced above).

# ============================================================
echo "--- live holder: a backdated lock with a live PID is never stolen (~10s) ---"
# ============================================================
sleep 120 &
HOLDER_PID=$!
mkdir "$LOCKD"
printf '%s\n' "$HOLDER_PID" > "$LOCKD/pid"
printf '%s\n' "holders-own-token" > "$LOCKD/owner"
touch -t 202001010000 "$LOCKD"      # far past the stale window: liveness must win

out="$("$PROJECTS" add "$TMP/proj1" 2>&1)"; rc=$?
assert_exit_nonzero_rc "add against a live holder dies rather than proceeding" "$rc"
assert_contains "the die names the contention" "locked by another ait process" "$out"
assert_not_contains "no reclaim warn for a live holder" "Reclaiming" "$out"
assert_dir_exists "live holder's lock dir intact" "$LOCKD"
assert_eq "holder's pid file untouched" "$HOLDER_PID" "$(cat "$LOCKD/pid")"
assert_eq "holder's owner token untouched" "holders-own-token" "$(cat "$LOCKD/owner")"
assert_eq "nothing written to the registry while blocked" "0" "$(entry_count)"
kill "$HOLDER_PID" 2>/dev/null; wait "$HOLDER_PID" 2>/dev/null; HOLDER_PID=""
rm -rf "$LOCKD" "$LOCKD.gc"

# ============================================================
echo "--- concurrency: $K contenders through one dead-holder lock serialize ---"
# ============================================================
# Seed a DEAD PID, not a tokenless dir: the pre-conversion code skipped the
# steal outright when the pid file was missing (it read that as a holder
# mid-acquire and waited), so a tokenless seed would exercise only the newly
# reachable age-reclaim path and say nothing about the path both
# implementations share.
mkdir "$LOCKD"
printf '%s\n' "$(dead_pid_fixture)" > "$LOCKD/pid"
printf '%s\n' "dead-holders-token" > "$LOCKD/owner"

for i in $(seq 1 "$K"); do
    "$PROJECTS" add "$TMP/proj$i" >/dev/null 2>"$TMP/sw_err_$i.log" &
done
wait

if [[ "$(entry_count)" != "$K" ]]; then
    echo "DIAG: contention anomaly — contender stderr follows:"
    cat "$TMP"/sw_err_*.log
fi
assert_eq "$K contenders -> $K registry entries (no lost update)" "$K" "$(entry_count)"
for i in $(seq 1 "$K"); do
    assert_eq "fixture_proj$i registered exactly once" "1" \
        "$(entry_count "^  - name: fixture_proj$i\$")"
done
reclaims="$(cat "$TMP"/sw_err_*.log | grep -c 'Reclaiming' || true)"
assert_eq "exactly one reclaim across all contenders (single-winner)" "1" "$reclaims"
assert_dir_not_exists "no lock dir left behind" "$LOCKD"
assert_dir_not_exists "no guard dir left behind" "$LOCKD.gc"

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -gt 0 ]] && exit 1
echo "All tests PASSED"
