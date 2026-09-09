#!/usr/bin/env bash
# test_sync_protect_paths.sh - every `_protect` path still produces usable batch
# stdout (t1725_3, risk mitigation `characterize_sync_paths_never_empty_stdout`).
#
# Run: bash tests/test_sync_protect_paths.sh
#
# WHY THIS EXISTS
#
# aitask_sync.sh runs under `set -euo pipefail`, and two TUIs (syncer, board)
# parse its FIRST stdout line. Any path that aborts the script — an unset array
# index, an unabsorbed non-zero status — produces EMPTY stdout, which every
# consumer reports as `ERROR: empty output from sync script`: a diagnostic that
# names neither the cause nor the file. t1725_3 converts `_protect` from a flat
# reason list into eleven lockstep parallel arrays and rewrites the rebase gate,
# which is exactly the kind of change that can introduce such an abort on a
# rarely-taken branch.
#
# So this file is a CHARACTERIZATION harness: it drives every `_protect
# "<reason>"` literal in the script and asserts the run still emits a non-empty
# first line that starts with a recognised batch token. It is committed green
# against the pre-restructure script and must stay green through it.
#
# THE SCAN IS THE POINT. The reason list is read out of the source, not typed
# here, so a reason added later cannot silently escape coverage: an unscanned
# reason with no driver and no UNREACHABLE justification fails the file.
#
# Each driver also asserts EVIDENCE that its reason actually fired (a distinctive
# fragment of that reason's stderr report line). Without it a driver that quietly
# stopped reaching its branch would still "pass" on some other run's token — the
# vacuous-green failure mode this harness exists to prevent.

set -uo pipefail

TEST_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/sync_fixture.sh"

SYNC_SH="$PROJECT_DIR/.aitask-scripts/aitask_sync.sh"

# The batch protocol's first-token vocabulary, from the script's own header
# comment. A run that emits anything else — or nothing — is the failure.
RECOGNISED='SYNCED PUSHED PULLED NOTHING AUTOMERGED CONFLICT NO_NETWORK NO_REMOTE DEFERRED ERROR'

# --- The scan -------------------------------------------------------------
# Every protection reason literal in the script, deduplicated.
#
# THE RECEIVER LIST IS PART OF THE SCAN. A reason reaches the record set through
# any of three spellings — `_protect`, `_protect_task_paths` (a per-task
# protection expanded per path) and `_protect_group_paths` (the same for a
# commit group). Matching only the first is not a narrower scan, it is a SILENT
# one: when t1725_3 moved eight sites onto the two helpers, a `_protect`-only
# regex went from 12 reasons to 6 and the file still reported all green.
#
# The reverse check below is what makes that unrepeatable, so keep both.
scan_reasons() {
    grep -oE '_protect(_task_paths|_group_paths)?[[:space:]]+"[a-z_]+"' "$SYNC_SH" \
        | sed -E 's/.*"([a-z_]+)".*/\1/' | sort -u
}

# Every reason this file claims to drive.
driver_reasons() {
    declare -F | sed -n 's/^declare -f drive_//p' | sort -u
}

# --- Shared assertion -----------------------------------------------------
# assert_usable_stdout <label> <stdout> — non-empty, and the FIRST non-empty
# line's token (text before the first ':') is in the recognised set.
assert_usable_stdout() {
    local label="$1" out="$2" first token
    first="$(printf '%s\n' "$out" | grep -m1 -v '^[[:space:]]*$' || true)"
    if [[ -z "$first" ]]; then
        assert_record_fail
        echo "FAIL: $label — stdout was EMPTY (the ERROR:empty-output failure mode)"
        return 1
    fi
    token="${first%%:*}"
    if [[ " $RECOGNISED " == *" $token "* ]]; then
        assert_record_pass
        return 0
    fi
    assert_record_fail
    echo "FAIL: $label — first line '$first' has unrecognised token '$token'"
    return 1
}

# assert_reason_fired <label> <tmpdir> <fragment> — the reason's own stderr
# report line is present, so the driver provably reached the branch it claims.
assert_reason_fired() {
    local label="$1" tmpdir="$2" fragment="$3" err
    err="$(sync_err "$tmpdir")"
    assert_contains "$label: the reason actually fired" "$fragment" "$err"
}

# --- Drivers --------------------------------------------------------------
# One per reason. Each returns having asserted both stdout usability and that
# its own branch was reached. Names are `drive_<reason>` and are looked up by
# the scan below, so adding a reason without a driver is a hard failure.

# The userconfig email matches the planted lock's `locked_by`, so the holder
# classifies as `self` and the report names the user's OWN session. Without it
# the class would be `unverified` (an absent local email must never compare
# equal to an absent lock email), which is correct but proves less.
drive_live_lock() {
    local t; t="$(setup_repo)"
    plant_lock "$t" 10 "$(lock_yaml_live 10)"
    set_userconfig_email "$t" other@x.com
    (cd "$t/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
    local out; out="$(run_sync "$t")"
    assert_usable_stdout "live_lock" "$out"
    assert_reason_fired "live_lock" "$t" "held by YOUR OWN live session"
    # The wrong-by-construction wording this task removes.
    assert_not_contains "live_lock: the old roll-up wording is gone" \
        "held by other sessions" "$(sync_err "$t")"
}

drive_unknown_liveness() {
    local t; t="$(setup_repo)"
    plant_lock "$t" 10 "$(lock_yaml_unknown_pid 10)"
    (cd "$t/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
    local out; out="$(run_sync "$t")"
    assert_usable_stdout "unknown_liveness" "$out"
    assert_reason_fired "unknown_liveness" "$t" "could not be verified as gone"
}

# Deterministic backend failure: replace aitask_lock.sh with a stub that exits
# non-zero, so _lock_snapshot records LOCKS_UNAVAILABLE. Breaking the network
# instead would work too, but it would short-circuit the run at do_fetch and the
# NO_NETWORK token would satisfy the assertion without this branch ever running.
drive_locks_unavailable() {
    local t; t="$(setup_repo)"
    (cd "$t/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md \
        && printf '#!/usr/bin/env bash\nexit 1\n' > .aitask-scripts/aitask_lock.sh)
    local out; out="$(run_sync "$t")"
    assert_usable_stdout "locks_unavailable" "$out"
    assert_reason_fired "locks_unavailable" "$t" "lock branch unreadable"
}

drive_ownerless() {
    local t; t="$(setup_repo)"
    (cd "$t/local" && printf 'changed\n' >> .aitask-data/aitasks/metadata/stats_config.json)
    local out; out="$(run_sync "$t")"
    assert_usable_stdout "ownerless" "$out"
    assert_reason_fired "ownerless" "$t" "ownerless, NOT auto-committed"
}

# git only emits an `R` porcelain entry when BOTH halves are staged, so the
# rename must go through `git mv`. t10 -> t20 crosses tasks, so no owner agrees.
drive_ambiguous_rename() {
    local t; t="$(setup_repo)"
    (cd "$t/local/.aitask-data" && git mv aitasks/t10_alpha.md aitasks/t20_renamed.md)
    local out; out="$(run_sync "$t")"
    assert_usable_stdout "ambiguous_rename" "$out"
    assert_reason_fired "ambiguous_rename" "$t" "ambiguous cross-task rename"
}

# _path_state returns 1 when the path EXISTS but cannot be hashed. chmod 000 is
# the portable way to make `git hash-object` fail on a file that is still -e.
drive_unverifiable() {
    local t; t="$(setup_repo)"
    (cd "$t/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md \
        && chmod 000 .aitask-data/aitasks/t10_alpha.md)
    local out; out="$(run_sync "$t")"
    chmod 644 "$t/local/.aitask-data/aitasks/t10_alpha.md" 2>/dev/null || true
    assert_usable_stdout "unverifiable" "$out"
    assert_reason_fired "unverifiable" "$t" "could not hash"
}

# A path another session already staged: _commit_group refuses the whole group
# rather than replacing an index entry it does not own.
drive_staged_elsewhere() {
    local t; t="$(setup_repo)"
    (cd "$t/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md \
        && git -C .aitask-data add aitasks/t10_alpha.md)
    local out; out="$(run_sync "$t")"
    assert_usable_stdout "staged_elsewhere" "$out"
    assert_reason_fired "staged_elsewhere" "$t" "has staged"
}

# Both remaining drivers need the pre_commit_phase seam, which fires after the
# dirty scan populated PATH_STATE and BEFORE the 5a.2 CAS and the commit.
#
# pre_group_commit is the wrong seam for either: it fires AFTER the 5a.3 state
# re-check, so a rewrite there is caught by the 5a.4 publication guard and
# quarantined instead of skipped. (Measured — an earlier draft of this file used
# it and the evidence assertion below is what caught the mistake.)
enable_seams_for() { mkdir -p "$1/locks" && touch "$1/locks/.ait_sync_test_seams"; }

# The seam body is eval'd INSIDE the sync process, which cannot see this shell's
# functions — so write the plumbing to a script the seam can invoke.
write_plant_script() {
    local tmpdir="$1" tid="$2"
    cat > "$tmpdir/plant.sh" <<PLANTEOF
#!/usr/bin/env bash
cd "$tmpdir/local" || exit 0
git fetch origin aitask-locks --quiet 2>/dev/null
parent=\$(git rev-parse origin/aitask-locks)
tree=\$(git rev-parse "origin/aitask-locks^{tree}")
blob=\$(printf '%s' "$(lock_yaml_live "$tid")" | git hash-object -w --stdin)
newtree=\$( { git ls-tree "\$tree" | grep -v "	t${tid}_lock\.yaml\$" || true
              printf "100644 blob %s\tt%s_lock.yaml\n" "\$blob" "$tid"; } | git mktree )
commit=\$(echo "seam: plant lock" | git commit-tree "\$newtree" -p "\$parent")
git push --quiet origin "\$commit:refs/heads/aitask-locks" 2>/dev/null
PLANTEOF
    chmod +x "$tmpdir/plant.sh"
}

drive_content_changed() {
    local t; t="$(setup_repo)"
    enable_seams_for "$t"
    (cd "$t/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
    local out
    out="$(AIT_SYNC_SEAM_pre_commit_phase="printf 'raced\n' >> $t/local/.aitask-data/aitasks/t10_alpha.md" \
        run_sync "$t")"
    assert_usable_stdout "content_changed" "$out"
    assert_reason_fired "content_changed" "$t" "changed after classification"
}

# A lock acquired between the first enumeration and the CAS re-enumeration: the
# two verdicts disagree, so the group is dropped rather than committed.
drive_lock_acquired_during_scan() {
    local t; t="$(setup_repo)"
    enable_seams_for "$t"
    write_plant_script "$t" 10
    (cd "$t/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
    local out
    out="$(AIT_SYNC_SEAM_pre_commit_phase="bash $t/plant.sh" run_sync "$t")"
    assert_usable_stdout "lock_acquired_during_scan" "$out"
    assert_reason_fired "lock_acquired_during_scan" "$t" "was locked while we were scanning"
}

# mktemp fails when TMPDIR names a directory that does not exist.
drive_scan_failed() {
    local t; t="$(setup_repo)"
    (cd "$t/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
    local out; out="$(TMPDIR="$t/no_such_dir" run_sync "$t")"
    assert_usable_stdout "scan_failed" "$out"
    assert_reason_fired "scan_failed" "$t" "nothing swept"
}

drive_lock_contended() {
    local t; t="$(setup_repo)"
    (cd "$t/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
    # Hold the data-index lock with a LIVE pid so the reclaim path cannot steal
    # it: this shell is alive for the duration of the run. BOTH files are
    # required — a dir carrying `pid` but no `owner` is a tokenless lock, which
    # is exactly what the reclaimer is allowed to take, and the acquire then
    # succeeds and this driver proves nothing.
    #
    # The base is the fixture's, NOT one of ours: run_sync unconditionally
    # exports AITASKS_LOCK_DIR="$tmpdir/locks", so a value passed in from here
    # is discarded. (Also measured — the evidence assertion caught it.)
    local lockbase="$t/locks"
    mkdir -p "$lockbase/data_index"
    printf '%s\n' "$$" > "$lockbase/data_index/pid"
    printf '%s\n' "$$-held-by-test" > "$lockbase/data_index/owner"
    local out; out="$(run_sync "$t")"
    assert_usable_stdout "lock_contended" "$out"
    assert_reason_fired "lock_contended" "$t" "holds the data-index lock"
}

drive_commit_failed() {
    local t; t="$(setup_repo)"
    (cd "$t/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
    # Worktrees share the common git dir's hooks, so this refuses the data
    # worktree's commit while leaving the fixture's own setup commits intact.
    mkdir -p "$t/local/.git/hooks"
    printf '#!/usr/bin/env bash\nexit 1\n' > "$t/local/.git/hooks/pre-commit"
    chmod +x "$t/local/.git/hooks/pre-commit"
    local out; out="$(run_sync "$t")"
    assert_usable_stdout "commit_failed" "$out"
    assert_reason_fired "commit_failed" "$t" "commit failed"
}

# --commit-for-task reaches a group whose own session is live; --expect-path
# then finds the dirty set has grown since the caller confirmed it.
drive_commit_scope_changed() {
    local t; t="$(setup_repo)"
    plant_lock "$t" 10 "$(lock_yaml_live 10)"
    set_userconfig_email "$t" other@x.com
    (cd "$t/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md \
                   && printf 'extra\n' > .aitask-data/aitasks/t10_extra.md)
    # Only ONE of t10's two dirty paths is declared.
    local out
    out="$(run_sync "$t" --commit-for-task 10 --expect-path "aitasks/t10_alpha.md")"
    assert_usable_stdout "commit_scope_changed" "$out"
    assert_reason_fired "commit_scope_changed" "$t" "the dirty set changed after it was confirmed"
}

# --require-waiting with no probe available. This is the ONLY direction
# reachable until t1725_4 lands the pane helpers, and it is the fail-closed one:
# no probe must mean "not waiting", never "assume waiting".
drive_holder_not_waiting() {
    local t; t="$(setup_repo)"
    plant_lock "$t" 10 "$(lock_yaml_live 10)"
    set_userconfig_email "$t" other@x.com
    (cd "$t/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
    local out; out="$(run_sync "$t" --commit-for-task 10 --require-waiting)"
    assert_usable_stdout "holder_not_waiting" "$out"
    assert_reason_fired "holder_not_waiting" "$t" "is not parked on a prompt"
    assert_not_contains "holder_not_waiting: nothing was committed" \
        "Auto-commit t10" "$(data_log "$t")"
}

# Reasons with no reachable driver. Each MUST carry a justification: an empty
# excuse here is how a scan turns vacuous.
declare -A UNREACHABLE=()

# --- Run ------------------------------------------------------------------
echo "=== _protect path characterization (t1725_3) ==="
echo ""

mapfile -t REASONS < <(scan_reasons)

if (( ${#REASONS[@]} == 0 )); then
    echo "FAIL: the source scan found no _protect literals — the scan itself broke"
    exit 1
fi

echo "Scanned ${#REASONS[@]} reason(s) from $(basename "$SYNC_SH"): ${REASONS[*]}"
echo ""

# REVERSE CHECK: every driver must correspond to a scanned reason.
#
# The forward check (scanned reason -> driver or UNREACHABLE) catches a reason
# ADDED to the script. Only this one catches the script moving a reason onto a
# call spelling the scan does not match: the reason vanishes from REASONS, its
# driver is simply never invoked, and the forward check has nothing to complain
# about. Measured — this is exactly what happened when the per-task and
# per-group helpers landed.
orphaned=0
while read -r d; do
    [[ -z "$d" ]] && continue
    if [[ " ${REASONS[*]} " != *" $d "* ]]; then
        assert_record_fail
        echo "FAIL: drive_$d() exists but '$d' is not in the source scan — the scan regex has stopped matching a call site"
        orphaned=1
    fi
done < <(driver_reasons)
if (( orphaned == 0 )); then
    assert_record_pass
fi
echo ""

for reason in "${REASONS[@]}"; do
    if [[ -n "${UNREACHABLE[$reason]:-}" ]]; then
        echo "--- $reason: UNREACHABLE (${UNREACHABLE[$reason]}) ---"
        continue
    fi
    if ! declare -F "drive_$reason" >/dev/null; then
        assert_record_fail
        echo "FAIL: reason '$reason' has no drive_$reason() and no UNREACHABLE justification"
        continue
    fi
    echo "--- $reason ---"
    "drive_$reason"
done

echo ""
echo "=================================="
echo "Results: $PASS passed, $FAIL failed (of $TOTAL)"
echo "=================================="
[[ "$FAIL" -eq 0 ]]
