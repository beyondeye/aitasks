#!/usr/bin/env bash
# test_usage_update.sh - aitask_usage_update.sh records usage runs on the
# aitask-stats branch through aitask_model_stats.py (t1912_4).
#
# Every count is read back through the CLI's effective view (`mdfix_export`):
# legacy registry counters + branch counters, exactly as readers see them. The
# bucket arithmetic itself is pinned by tests/test_model_stats_parity.sh (golden
# from the former jq writers) and tests/test_model_stats_store.py; this file
# pins the writer: its CLI contract, its read-only registry check, the value it
# prints and its bridge to the stats CLI.
#
# Retired with the clone/push path t1912_4 deleted (concurrency of the new path
# is pinned by test_model_stats_store.py's forced-conflict and two-clone tests):
# the UPDATED_REMOTE_ONLY partial-result tests (that outcome no longer exists),
# the dirty-file stranding test (moved to test_stats_writers_leave_task_data.sh),
# t1928a-c (the writer no longer rewrites the registry, so a concurrent refresh
# cannot race it) and t2134 (no push classifier left).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

# shellcheck source=lib/metadata_update_fixture.sh
. "$PROJECT_DIR/tests/lib/metadata_update_fixture.sh"
. "$PROJECT_DIR/tests/lib/git_config_isolation.sh"
sync_isolate_git_config

SCRIPT=aitask_usage_update.sh
setup_repo() { setup_local_metadata_repo "$SCRIPT"; }

# seed <repo> <jq filter> — edit the registry's legacy counters and commit.
seed() {
    local tmp
    tmp="$(mktemp)"
    jq "$2" "$1/aitasks/metadata/models_claudecode.json" > "$tmp"
    mv "$tmp" "$1/aitasks/metadata/models_claudecode.json"
    (cd "$1" && git add -A && git commit -m seed --quiet)
}

usage() {  # usage <repo> <args...> — run the writer from <repo>
    local repo="$1"; shift
    (cd "$repo" && "./.aitask-scripts/$SCRIPT" --agent-string claudecode/opus4_6 "$@")
}

set +e

echo "=== aitask_usage_update.sh Tests ==="
echo ""

echo "--- Test 1: Fresh model (no usagestats key) — full block created ---"
T1="$(setup_repo)"
sha1="$(mdfix_registry_sha "$T1")"
output1=$(usage "$T1" --skill pick --date 2026-03-11 2>&1)
assert_contains "Structured success output" "UPDATED:claudecode/opus4_6:pick:1" "$output1"
assert_eq "all_time runs initialized to 1" "1" "$(mdfix_stat "$T1" '.usagestats.pick.all_time.runs')"
assert_eq "all_time has no score_sum" "null" "$(mdfix_stat "$T1" '.usagestats.pick.all_time.score_sum')"
assert_eq "month period set" "2026-03" "$(mdfix_stat "$T1" '.usagestats.pick.month.period')"
assert_eq "month runs = 1" "1" "$(mdfix_stat "$T1" '.usagestats.pick.month.runs')"
assert_eq "week period set" "2026-W11" "$(mdfix_stat "$T1" '.usagestats.pick.week.period')"
assert_eq "week runs = 1" "1" "$(mdfix_stat "$T1" '.usagestats.pick.week.runs')"
assert_eq "prev_month period empty" "" "$(mdfix_stat "$T1" '.usagestats.pick.prev_month.period')"
assert_eq "prev_month runs = 0" "0" "$(mdfix_stat "$T1" '.usagestats.pick.prev_month.runs')"
assert_eq "registry file byte-identical" "$sha1" "$(mdfix_registry_sha "$T1")"
assert_eq "the count is on the local aitask-stats branch" "yes" \
    "$(git -C "$T1" rev-parse -q --verify refs/heads/aitask-stats >/dev/null && echo yes || echo no)"
rm -rf "$T1"

echo "--- Test 2: Same-month bump — month increments, prev_month untouched ---"
T2="$(setup_repo)"
seed "$T2" '.models[0].usagestats.pick = {
        "all_time":   {"runs": 7},
        "prev_month": {"period": "2026-03", "runs": 5},
        "month":      {"period": "2026-04", "runs": 2},
        "week":       {"period": "2026-W17", "runs": 1}
    }'
sha2="$(mdfix_registry_sha "$T2")"
output2=$(usage "$T2" --skill pick --date 2026-04-29 --silent 2>&1)
assert_eq "Same-month: structured output runs=3 (registry counters included)" \
    "UPDATED:claudecode/opus4_6:pick:3" "$output2"
assert_eq "Same-month: month runs = 3" "3" "$(mdfix_stat "$T2" '.usagestats.pick.month.runs')"
assert_eq "Same-month: month period unchanged" "2026-04" "$(mdfix_stat "$T2" '.usagestats.pick.month.period')"
assert_eq "Same-month: all_time runs = 8" "8" "$(mdfix_stat "$T2" '.usagestats.pick.all_time.runs')"
assert_eq "Same-month: prev_month period preserved" "2026-03" "$(mdfix_stat "$T2" '.usagestats.pick.prev_month.period')"
assert_eq "Same-month: prev_month runs preserved" "5" "$(mdfix_stat "$T2" '.usagestats.pick.prev_month.runs')"
assert_eq "Same-month: registry file byte-identical" "$sha2" "$(mdfix_registry_sha "$T2")"
rm -rf "$T2"

echo "--- Test 3: One-month rollover — prev_month gets old month, month resets ---"
T3="$(setup_repo)"
seed "$T3" '.models[0].usagestats.pick = {
        "all_time":   {"runs": 5},
        "prev_month": {"period": "", "runs": 0},
        "month":      {"period": "2026-04", "runs": 5},
        "week":       {"period": "2026-W17", "runs": 1}
    }'
usage "$T3" --skill pick --date 2026-05-01 --silent >/dev/null 2>&1
assert_eq "One-month rollover: prev_month period = old month" "2026-04" "$(mdfix_stat "$T3" '.usagestats.pick.prev_month.period')"
assert_eq "One-month rollover: prev_month runs = old month runs" "5" "$(mdfix_stat "$T3" '.usagestats.pick.prev_month.runs')"
assert_eq "One-month rollover: month period = 2026-05" "2026-05" "$(mdfix_stat "$T3" '.usagestats.pick.month.period')"
assert_eq "One-month rollover: month runs reset to 1" "1" "$(mdfix_stat "$T3" '.usagestats.pick.month.runs')"
assert_eq "One-month rollover: all_time runs = 6" "6" "$(mdfix_stat "$T3" '.usagestats.pick.all_time.runs')"
rm -rf "$T3"

echo "--- Test 4: Multi-month skip — prev_month zeroed, month resets ---"
T4="$(setup_repo)"
seed "$T4" '.models[0].usagestats.pick = {
        "all_time":   {"runs": 4},
        "prev_month": {"period": "2026-01", "runs": 1},
        "month":      {"period": "2026-02", "runs": 3},
        "week":       {"period": "2026-W08", "runs": 1}
    }'
usage "$T4" --skill pick --date 2026-05-01 --silent >/dev/null 2>&1
assert_eq "Multi-month skip: prev_month period zeroed" "" "$(mdfix_stat "$T4" '.usagestats.pick.prev_month.period')"
assert_eq "Multi-month skip: prev_month runs zeroed" "0" "$(mdfix_stat "$T4" '.usagestats.pick.prev_month.runs')"
assert_eq "Multi-month skip: month period = 2026-05" "2026-05" "$(mdfix_stat "$T4" '.usagestats.pick.month.period')"
assert_eq "Multi-month skip: month runs = 1" "1" "$(mdfix_stat "$T4" '.usagestats.pick.month.runs')"
rm -rf "$T4"

echo "--- Test 5: Two skills accumulate independently ---"
T5="$(setup_repo)"
usage "$T5" --skill pick --date 2026-03-11 --silent >/dev/null 2>&1
usage "$T5" --skill explore --date 2026-03-11 --silent >/dev/null 2>&1
assert_eq "Pick all_time runs = 1" "1" "$(mdfix_stat "$T5" '.usagestats.pick.all_time.runs')"
assert_eq "Explore all_time runs = 1" "1" "$(mdfix_stat "$T5" '.usagestats.explore.all_time.runs')"
assert_eq "Pick month runs = 1" "1" "$(mdfix_stat "$T5" '.usagestats.pick.month.runs')"
assert_eq "Explore month runs = 1" "1" "$(mdfix_stat "$T5" '.usagestats.explore.month.runs')"
rm -rf "$T5"

echo "--- Test 6: Verified data untouched by usage update ---"
T6="$(setup_repo)"
seed "$T6" '.models[0].verifiedstats.pick = {"all_time": {"runs": 4, "score_sum": 320}}'
vs_before="$(mdfix_export "$T6" | jq -c '.models.opus4_6.verifiedstats')"
sha6="$(mdfix_registry_sha "$T6")"
usage "$T6" --skill pick --date 2026-03-11 --silent >/dev/null 2>&1
assert_eq "verifiedstats unchanged" "$vs_before" "$(mdfix_export "$T6" | jq -c '.models.opus4_6.verifiedstats')"
assert_eq "registry file (incl. verified) byte-identical" "$sha6" "$(mdfix_registry_sha "$T6")"
assert_eq "usagestats was created" "1" "$(mdfix_stat "$T6" '.usagestats.pick.all_time.runs')"
rm -rf "$T6"

echo "--- Test 7: Unknown agent fails ---"
T7="$(setup_repo)"
assert_exit_nonzero "Unknown agent rejected" bash -c "cd '$T7' && ./.aitask-scripts/$SCRIPT --agent-string fakeagent/whatever --skill pick"
rm -rf "$T7"

echo "--- Test 8: Missing model fails ---"
T8="$(setup_repo)"
assert_exit_nonzero "Missing model rejected" bash -c "cd '$T8' && ./.aitask-scripts/$SCRIPT --agent-string claudecode/sonnet4_6 --skill pick"
assert_eq "Missing model: nothing recorded" "no" \
    "$(git -C "$T8" rev-parse -q --verify refs/heads/aitask-stats >/dev/null && echo yes || echo no)"
rm -rf "$T8"

echo "--- Test 9: --score flag rejected ---"
T9="$(setup_repo)"
assert_exit_nonzero "--score flag rejected" bash -c "cd '$T9' && ./.aitask-scripts/$SCRIPT --agent-string claudecode/opus4_6 --skill pick --score 5"
rm -rf "$T9"

echo "--- Test 10: Help exits 0 ---"
T10="$(setup_repo)"
assert_exit_zero "Help exits successfully" bash -c "cd '$T10' && ./.aitask-scripts/$SCRIPT --help"
help10="$(cd "$T10" && "./.aitask-scripts/$SCRIPT" --help)"
assert_contains "Help documents STATS_ERROR" "STATS_ERROR:<reason>" "$help10"
assert_not_contains "Help no longer documents UPDATED_REMOTE_ONLY" "UPDATED_REMOTE_ONLY" "$help10"
rm -rf "$T10"

echo "--- Test 11: Silent mode prints only structured result ---"
T11="$(setup_repo)"
output11=$(usage "$T11" --skill pick --silent 2>&1)
assert_eq "Silent output is structured only" "UPDATED:claudecode/opus4_6:pick:1" "$output11"
rm -rf "$T11"

echo "--- Test 11c: every non-empty skill the writer always accepted still records ---"
# The writer took any non-empty --skill (a JSON key); routing it through the
# stats CLI must not narrow its public interface (t1912_4).
T11C="$(setup_repo)"
for skill_11c in "custom/skill" "a:b" "two words" '*glob[x]' "ñandú" "x|y" \
        "-custom" "--looks-like-a-flag" "-h" "a=b" "--skill=x"; do
    rc=0; out=$(usage "$T11C" --skill "$skill_11c" --silent 2>/dev/null) || rc=$?
    assert_eq "skill '$skill_11c' recorded, echoed verbatim" \
        "UPDATED:claudecode/opus4_6:${skill_11c}:1|0" "$out|$rc"
    assert_eq "skill '$skill_11c' is a key in the store" "1" \
        "$(mdfix_export "$T11C" | jq -r --arg s "$skill_11c" '.models.opus4_6.usagestats[$s].all_time.runs')"
done
rm -rf "$T11C"

echo "--- Test 11b: --date format and calendar validation ---"
T11B="$(setup_repo)"
rc=0; out=$(usage "$T11B" --skill pick --date 2026/03/11 --silent 2>&1) || rc=$?
assert_exit_nonzero_rc "malformed --date rejected" "$rc"
assert_contains "malformed --date message" "--date must be in YYYY-MM-DD format" "$out"
rc=0; out=$(usage "$T11B" --skill pick --date 2026-02-30 --silent 2>/dev/null) || rc=$?
assert_exit_nonzero_rc "impossible calendar date rejected" "$rc"
assert_contains "impossible date is a STATS_ERROR usage refusal" "STATS_ERROR:usage:" "$out"
assert_eq "nothing recorded for a refused date" "no" \
    "$(git -C "$T11B" rev-parse -q --verify refs/heads/aitask-stats >/dev/null && echo yes || echo no)"
rm -rf "$T11B"

# =====================================================================
# Remote: the store's leased-push path
# =====================================================================

echo "--- Test 12: a remote write lands on origin's and the local aitask-stats ---"
B12="$(setup_remote_stats_repo "$SCRIPT")"
W12="$B12/work"
sha12="$(mdfix_registry_sha "$W12")"
main12="$(git -C "$B12/origin.git" rev-parse refs/heads/main)"
rc=0; out12=$(usage "$W12" --skill pick --date 2026-03-11 --silent 2>/dev/null) || rc=$?
assert_eq "remote: UPDATED / exit 0" "UPDATED:claudecode/opus4_6:pick:1|0" "$out12|$rc"
origin12="$(git -C "$B12/origin.git" rev-parse -q --verify refs/heads/aitask-stats)"
assert_eq "remote: origin's aitask-stats == local aitask-stats" "$origin12" \
    "$(git -C "$W12" rev-parse -q --verify refs/heads/aitask-stats)"
assert_eq "remote: origin's blob holds the run" "1" \
    "$(git -C "$B12/origin.git" show refs/heads/aitask-stats:claudecode.json | jq -r '.models.opus4_6.usagestats.pick.all_time.runs')"
assert_eq "remote: origin's code branch untouched" "$main12" "$(git -C "$B12/origin.git" rev-parse refs/heads/main)"
assert_eq "remote: registry file byte-identical" "$sha12" "$(mdfix_registry_sha "$W12")"
# Tracked files only: the CLI's bytecode cache (lib/__pycache__) is untracked
# noise in a fixture that has no .gitignore.
assert_eq "remote: no tracked file changed (no counter edit)" "" \
    "$(git -C "$W12" status --porcelain --untracked-files=no)"
assert_eq "remote: no commit on the checked-out branch" "$main12" "$(git -C "$W12" rev-parse HEAD)"
rm -rf "$B12"

echo "--- Test 14: unreachable origin — STATS_ERROR, non-zero, nothing recorded ---"
# Replaces the UPDATED_REMOTE_ONLY partial-result test: a store write either
# lands (UPDATED:) or reports STATS_ERROR: — there is no partial outcome.
B14="$(setup_remote_stats_repo "$SCRIPT")"
W14="$B14/work"
git -C "$W14" remote set-url origin "$B14/does-not-exist.git"
sha14="$(mdfix_registry_sha "$W14")"
rc=0; out14=$(usage "$W14" --skill pick --silent 2>/dev/null) || rc=$?
assert_exit_nonzero_rc "unreachable: exit non-zero" "$rc"
assert_contains "unreachable: STATS_ERROR names the cause" "STATS_ERROR:unreachable:" "$out14"
assert_not_contains "unreachable: never claims UPDATED" "UPDATED:" "$out14"
assert_eq "unreachable: registry file byte-identical" "$sha14" "$(mdfix_registry_sha "$W14")"
assert_eq "unreachable: no local stats ref" "no" \
    "$(git -C "$W14" rev-parse -q --verify refs/heads/aitask-stats >/dev/null && echo yes || echo no)"
rm -rf "$B14"

echo "--- Test 15: positive control — the same run with origin reachable is UPDATED / 0 ---"
B15="$(setup_remote_stats_repo "$SCRIPT")"
rc=0; out15=$(usage "$B15/work" --skill pick --silent 2>/dev/null) || rc=$?
assert_eq "reachable: UPDATED / 0" "UPDATED:claudecode/opus4_6:pick:1|0" "$out15|$rc"
rm -rf "$B15"

echo "--- Test 16: the local (no-remote) path reports the correct count ---"
T16="$(setup_repo)"
rc16=0
output16=$(usage "$T16" --skill pick --silent 2>/dev/null) || rc16=$?
assert_eq "no-remote path exits 0" "0" "$rc16"
assert_eq "no-remote path carries the correct value" "UPDATED:claudecode/opus4_6:pick:1" "$output16"
output16b=$(usage "$T16" --skill pick --silent 2>/dev/null)
assert_eq "no-remote: a second run counts on" "UPDATED:claudecode/opus4_6:pick:2" "$output16b"
rm -rf "$T16"

echo "--- Test 17: real entry point from a NON-ROOT cwd (t1658_2) ---"
# The registry path is cwd-relative and the stats CLI is pointed at the cwd, so
# without ait_cd_repo_root a non-root launch dies with "Model config not found"
# (or records into the wrong project). EACH cwd gets its own fixture so the
# discriminating values stay identical.
for launch_17 in subdir unrelated; do
    B17="$(setup_remote_stats_repo "$SCRIPT")"
    W17="$B17/work"
    mkdir -p "$W17/website"
    case "$launch_17" in
        subdir)    cwd_17="$W17/website" ;;
        unrelated) cwd_17="$B17" ;;
    esac
    rc17=0
    out17=$(cd "$cwd_17" && "$W17/.aitask-scripts/$SCRIPT" \
        --agent-string claudecode/opus4_6 --skill pick --silent 2>/dev/null) || rc17=$?
    assert_eq "17/$launch_17: reports UPDATED from a non-root cwd" \
        "UPDATED:claudecode/opus4_6:pick:1" "$out17"
    assert_eq "17/$launch_17: exits 0 (not the 'Model config not found' die)" "0" "$rc17"
    assert_eq "17/$launch_17: the run landed in THIS project's store" "1" \
        "$(git -C "$B17/origin.git" show refs/heads/aitask-stats:claudecode.json 2>/dev/null \
            | jq -r '.models.opus4_6.usagestats.pick.all_time.runs')"
    rm -rf "$B17"
done

echo "--- Test t1884: resolver fallbacks reach the registry check, not a format error ---"
# A resolver fallback (claudecode/unregistered_*) parses, has no registry row,
# and must be refused with an agent-specific registration hint -- never with
# "Invalid agent string format", and never recorded against another row.
TFB="$(setup_repo)"
before_fb="$(cat "$TFB/aitasks/metadata/models_claudecode.json")"
rc=0
out_fb=$(cd "$TFB" && "./.aitask-scripts/$SCRIPT" --agent-string claudecode/unregistered_opus4_6 --skill pick --date 2026-03-11 2>&1) || rc=$?
assert_exit_nonzero_rc "usage: fallback string exits non-zero" "$rc"
assert_not_contains "usage: fallback passes the format check" "Invalid agent string format" "$out_fb"
assert_contains "usage: fallback is refused as unregistered" "Model 'unregistered_opus4_6' not found" "$out_fb"
assert_contains "usage: claudecode hint names /aitask-add-model" "/aitask-add-model" "$out_fb"
assert_eq "usage: registry unchanged after refusal" "$before_fb" \
    "$(cat "$TFB/aitasks/metadata/models_claudecode.json")"
assert_eq "usage: nothing recorded on the stats branch" "no" \
    "$(git -C "$TFB" rev-parse -q --verify refs/heads/aitask-stats >/dev/null && echo yes || echo no)"

cat > "$TFB/aitasks/metadata/models_opencode.json" <<'EOF_OC'
{ "models": [ { "name": "opencode_foo", "cli_id": "opencode/foo", "notes": "t", "verified": {}, "verifiedstats": {} } ] }
EOF_OC
rc=0
out_oc=$(cd "$TFB" && "./.aitask-scripts/$SCRIPT" --agent-string opencode/unregistered_x --skill pick --date 2026-03-11 2>&1) || rc=$?
assert_exit_nonzero_rc "usage: opencode fallback exits non-zero" "$rc"
assert_contains "usage: opencode hint names /aitask-refresh-code-models" "/aitask-refresh-code-models" "$out_oc"
assert_not_contains "usage: opencode hint does not offer add-model as the route" "register it with /aitask-add-model" "$out_oc"
rm -rf "$TFB"

# =====================================================================
# The bridge to the stats CLI (lib/verified_update_lib.sh model_stats_write)
# =====================================================================
# The scaffold's aitask_model_stats.py is replaced by a stub, so each CLI
# outcome is driven exactly; the writer's mapping is the unit under test.

echo "--- Test bridge: CLI outcomes map onto the writer's contract ---"
TB="$(setup_repo)"
STUB="$TB/.aitask-scripts/aitask_model_stats.py"
# stub <stdout line> <exit> [stderr line]
stub() {
    STUB_OUT="$1" STUB_RC="$2" STUB_ERR="${3:-}" python3 - "$STUB" <<'PY'
import os, sys
with open(sys.argv[1], "w") as fh:
    fh.write("import sys\n")
    if os.environ["STUB_ERR"]:
        fh.write(f"sys.stderr.write({os.environ['STUB_ERR']!r} + '\\n')\n")
    fh.write(f"print({os.environ['STUB_OUT']!r})\n")
    fh.write(f"sys.exit({int(os.environ['STUB_RC'])})\n")
PY
}
bridge() {  # bridge → "<stdout>|<rc>", stderr to $TB/err
    local rc=0 out
    out=$(usage "$TB" --skill pick --silent 2>"$TB/err") || rc=$?
    printf '%s|%s' "$out" "$rc"
}

stub "UPDATED:claudecode/opus4_6:pick:unknown" 0
assert_eq "bridge: an unknown total is a recorded success" \
    "UPDATED:claudecode/opus4_6:pick:unknown|0" "$(bridge)"

stub "UPDATED:claudecode/opus4_6:pick:7" 0 "model-stats: recorded on origin, but the local ref was not advanced"
assert_eq "bridge: integer value passes through" "UPDATED:claudecode/opus4_6:pick:7|0" "$(bridge)"
assert_contains "bridge: the CLI's stderr is forwarded even under --silent" \
    "local ref was not advanced" "$(cat "$TB/err")"

stub "STATS_ERROR:boom" 1
assert_eq "bridge: STATS_ERROR passes through, exit non-zero" "STATS_ERROR:boom|1" "$(bridge)"

stub "STATS_DIVERGED:aaa|bbb" 1
assert_eq "bridge: divergence becomes STATS_ERROR:diverged" \
    "STATS_ERROR:diverged:aaa|bbb|1" "$(bridge)"

stub "UPDATED:claudecode/other_model:pick:1" 0
assert_eq "bridge: an UPDATED for another target is refused" \
    "STATS_ERROR:unexpected_output|1" "$(bridge)"

stub "UPDATED:claudecode/opus4_6:pick:1" 1
assert_eq "bridge: UPDATED with a failure exit is refused" \
    "STATS_ERROR:unexpected_output|1" "$(bridge)"

stub "UPDATED:claudecode/opus4_6:pick:12abc" 0
assert_eq "bridge: a malformed value is refused" \
    "STATS_ERROR:unexpected_output|1" "$(bridge)"

stub "something else" 0
assert_eq "bridge: an unrecognised line is refused" \
    "STATS_ERROR:unexpected_output|1" "$(bridge)"

rm -f "$STUB"
assert_eq "bridge: a missing CLI is STATS_ERROR:cli_missing" \
    "STATS_ERROR:cli_missing|1" "$(bridge)"

out_ns=$(cd "$TB" && "./.aitask-scripts/$SCRIPT" --agent-string claudecode/opus4_6 --skill pick 2>&1)
assert_contains "bridge: non-silent failure warns that nothing was recorded" \
    "was not recorded (cli_missing)" "$out_ns"
rm -rf "$TB"

echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
