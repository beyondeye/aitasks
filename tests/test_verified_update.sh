#!/usr/bin/env bash
# test_verified_update.sh - aitask_verified_update.sh records satisfaction
# ratings on the aitask-stats branch through aitask_model_stats.py (t1912_4).
#
# Every count is read back through the CLI's effective view (`mdfix_export`):
# legacy registry counters + branch counters, exactly as readers see them, so
# the rollover tests below keep seeding legacy bucket state in the registry and
# keep their expected values (the store's merge re-slots months the way the old
# writer rolled them). The registry is only READ: its `verified` map is a static
# prior that the writer never updates (parent decision 4); readers derive the
# effective score from verifiedstats.
#
# Retired with the clone/push path t1912_4 deleted (concurrency of the new path
# is pinned by test_model_stats_store.py's forced-conflict and two-clone tests):
# Test 9 / 9t (remote retry, a data-branch tag), t2134a-d (push-failure
# classifier), 21-26 and 29-31 (local-ref convergence, out-params, the commit
# seam and the converge), 33A-E (the shared-index commit seam: no longer reached
# by this writer; the seam itself stays covered by test_verification_followup.sh)
# and t1928a-c (the writer no longer rewrites the registry). Test 22 (a dirty
# file never strands the commit) moved to test_stats_writers_leave_task_data.sh.

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

SCRIPT=aitask_verified_update.sh
setup_repo() { setup_local_metadata_repo "$SCRIPT"; }

# seed <repo> <jq filter> — edit the registry's legacy counters and commit.
seed() {
    local tmp
    tmp="$(mktemp)"
    jq "$2" "$1/aitasks/metadata/models_claudecode.json" > "$tmp"
    mv "$tmp" "$1/aitasks/metadata/models_claudecode.json"
    (cd "$1" && git add -A && git commit -m seed --quiet)
}

rate() {  # rate <repo> <args...> — run the writer from <repo>
    local repo="$1"; shift
    (cd "$repo" && "./.aitask-scripts/$SCRIPT" --agent-string claudecode/opus4_6 "$@")
}

registry() {  # registry <repo> <jq filter>
    jq -r ".models[0]$2" "$1/aitasks/metadata/models_claudecode.json"
}

set +e

echo "=== aitask_verified_update.sh Tests ==="
echo ""

echo "--- Test 1: Valid update creates bucketed stats ---"
T1="$(setup_repo)"
sha1="$(mdfix_registry_sha "$T1")"
output1=$(rate "$T1" --skill pick --score 4 --date 2026-03-11 2>&1)
assert_contains "Structured success output" "UPDATED:claudecode/opus4_6:pick:80" "$output1"
assert_eq "All-time runs initialized to 1" "1" "$(mdfix_stat "$T1" '.verifiedstats.pick.all_time.runs')"
assert_eq "All-time score sum initialized to 80" "80" "$(mdfix_stat "$T1" '.verifiedstats.pick.all_time.score_sum')"
assert_eq "Month period set" "2026-03" "$(mdfix_stat "$T1" '.verifiedstats.pick.month.period')"
assert_eq "Month runs initialized to 1" "1" "$(mdfix_stat "$T1" '.verifiedstats.pick.month.runs')"
assert_eq "Week period set" "2026-W11" "$(mdfix_stat "$T1" '.verifiedstats.pick.week.period')"
assert_eq "Week runs initialized to 1" "1" "$(mdfix_stat "$T1" '.verifiedstats.pick.week.runs')"
assert_eq "registry file byte-identical (verified prior not written)" "$sha1" "$(mdfix_registry_sha "$T1")"
assert_eq "verified prior kept (pick)" "80" "$(registry "$T1" '.verified.pick')"
assert_eq "verified prior kept (batch-review)" "0" "$(registry "$T1" '.verified["batch-review"]')"
assert_eq "verified prior kept (explain)" "60" "$(registry "$T1" '.verified.explain')"
assert_eq "registry carries no verifiedstats" "null" "$(registry "$T1" '.verifiedstats')"
rm -rf "$T1"

echo "--- Test 2: Rolling average updates correctly ---"
T2="$(setup_repo)"
rate "$T2" --skill pick --score 4 --date 2026-03-11 >/dev/null 2>&1
output2=$(rate "$T2" --skill pick --score 5 --date 2026-03-11 2>&1)
assert_contains "Structured rolling average output" "UPDATED:claudecode/opus4_6:pick:90" "$output2"
assert_eq "All-time runs incremented to 2" "2" "$(mdfix_stat "$T2" '.verifiedstats.pick.all_time.runs')"
assert_eq "All-time score sum incremented to 180" "180" "$(mdfix_stat "$T2" '.verifiedstats.pick.all_time.score_sum')"
assert_eq "Month runs incremented to 2" "2" "$(mdfix_stat "$T2" '.verifiedstats.pick.month.runs')"
assert_eq "Week runs incremented to 2" "2" "$(mdfix_stat "$T2" '.verifiedstats.pick.week.runs')"
assert_eq "verified prior NOT rewritten to the average" "80" "$(registry "$T2" '.verified.pick')"
rm -rf "$T2"

echo "--- Test 3: Invalid agent string fails ---"
T3="$(setup_repo)"
assert_exit_nonzero "Invalid agent string rejected" bash -c "cd '$T3' && ./.aitask-scripts/$SCRIPT --agent-string invalid --skill pick --score 4"
rm -rf "$T3"

echo "--- Test 4: Invalid score fails ---"
T4="$(setup_repo)"
assert_exit_nonzero "Invalid score rejected" bash -c "cd '$T4' && ./.aitask-scripts/$SCRIPT --agent-string claudecode/opus4_6 --skill pick --score 6"
assert_eq "Invalid score: nothing recorded" "no" \
    "$(git -C "$T4" rev-parse -q --verify refs/heads/aitask-stats >/dev/null && echo yes || echo no)"
rm -rf "$T4"

echo "--- Test 5: Missing model fails ---"
T5="$(setup_repo)"
assert_exit_nonzero "Missing model rejected" bash -c "cd '$T5' && ./.aitask-scripts/$SCRIPT --agent-string claudecode/sonnet4_6 --skill pick --score 4"
rm -rf "$T5"

echo "--- Test 6: Help exits 0 ---"
T6="$(setup_repo)"
assert_exit_zero "Help exits successfully" bash -c "cd '$T6' && ./.aitask-scripts/$SCRIPT --help"
help6="$(cd "$T6" && "./.aitask-scripts/$SCRIPT" --help)"
assert_contains "Help documents STATS_ERROR" "STATS_ERROR:<reason>" "$help6"
assert_contains "Help says verified is never written" "never written" "$help6"
assert_not_contains "Help no longer documents UPDATED_REMOTE_ONLY" "UPDATED_REMOTE_ONLY" "$help6"
rm -rf "$T6"

echo "--- Test 7: Missing verifiedstats is created automatically with buckets ---"
T7="$(setup_repo)"
rate "$T7" --skill explain --score 3 --date 2026-03-11 >/dev/null 2>&1
assert_eq "Explain all-time runs created" "1" "$(mdfix_stat "$T7" '.verifiedstats.explain.all_time.runs')"
assert_eq "Explain all-time score sum created" "60" "$(mdfix_stat "$T7" '.verifiedstats.explain.all_time.score_sum')"
assert_eq "Explain month runs created" "1" "$(mdfix_stat "$T7" '.verifiedstats.explain.month.runs')"
assert_eq "Explain week runs created" "1" "$(mdfix_stat "$T7" '.verifiedstats.explain.week.runs')"
assert_eq "Explain verified prior unchanged" "60" "$(registry "$T7" '.verified.explain')"
rm -rf "$T7"

echo "--- Test 8: Silent mode prints only structured result ---"
T8="$(setup_repo)"
output8=$(rate "$T8" --skill pick --score 4 --silent 2>&1)
assert_eq "Silent output is structured only" "UPDATED:claudecode/opus4_6:pick:80" "$output8"
rm -rf "$T8"

echo "--- Test 8b: every non-empty skill the writer always accepted still records ---"
# The writer took any non-empty --skill (a JSON key); routing it through the
# stats CLI must not narrow its public interface (t1912_4).
T8B="$(setup_repo)"
for skill_8b in "custom/skill" "a:b" "two words" '*glob[x]' "-custom" "--score"; do
    rc=0; out=$(rate "$T8B" --skill "$skill_8b" --score 4 --silent 2>/dev/null) || rc=$?
    assert_eq "skill '$skill_8b' recorded, echoed verbatim" \
        "UPDATED:claudecode/opus4_6:${skill_8b}:80|0" "$out|$rc"
done
rm -rf "$T8B"

echo "--- Test 10: Old schema migration on update ---"
T10="$(setup_repo)"
seed "$T10" '.models[0].verifiedstats.pick = {"runs": 3, "score_sum": 240}'
sha10="$(mdfix_registry_sha "$T10")"
output10=$(rate "$T10" --skill pick --score 5 --date 2026-03-11 --silent 2>&1)
assert_eq "Migration: structured output (registry counters included)" "UPDATED:claudecode/opus4_6:pick:85" "$output10"
assert_eq "Migration: all-time runs = old + 1" "4" "$(mdfix_stat "$T10" '.verifiedstats.pick.all_time.runs')"
assert_eq "Migration: all-time score_sum = old + 100" "340" "$(mdfix_stat "$T10" '.verifiedstats.pick.all_time.score_sum')"
assert_eq "Migration: month runs = 1 (fresh)" "1" "$(mdfix_stat "$T10" '.verifiedstats.pick.month.runs')"
assert_eq "Migration: month period set" "2026-03" "$(mdfix_stat "$T10" '.verifiedstats.pick.month.period')"
assert_eq "Migration: week runs = 1 (fresh)" "1" "$(mdfix_stat "$T10" '.verifiedstats.pick.week.runs')"
assert_eq "Migration: the flat registry entry is left as it was" "$sha10" "$(mdfix_registry_sha "$T10")"
rm -rf "$T10"

echo "--- Test 11: Month rollover resets month but keeps all-time ---"
T11="$(setup_repo)"
rate "$T11" --skill pick --score 4 --date 2026-01-15 --silent >/dev/null 2>&1
rate "$T11" --skill pick --score 5 --date 2026-02-15 --silent >/dev/null 2>&1
assert_eq "Month rollover: all-time runs = 2" "2" "$(mdfix_stat "$T11" '.verifiedstats.pick.all_time.runs')"
assert_eq "Month rollover: all-time score_sum = 180" "180" "$(mdfix_stat "$T11" '.verifiedstats.pick.all_time.score_sum')"
assert_eq "Month rollover: month period updated" "2026-02" "$(mdfix_stat "$T11" '.verifiedstats.pick.month.period')"
assert_eq "Month rollover: month runs reset to 1" "1" "$(mdfix_stat "$T11" '.verifiedstats.pick.month.runs')"
assert_eq "Month rollover: month score_sum reset" "100" "$(mdfix_stat "$T11" '.verifiedstats.pick.month.score_sum')"
rm -rf "$T11"

echo "--- Test 12: Week rollover resets week but keeps all-time ---"
T12="$(setup_repo)"
rate "$T12" --skill pick --score 4 --date 2026-03-09 --silent >/dev/null 2>&1
rate "$T12" --skill pick --score 5 --date 2026-03-16 --silent >/dev/null 2>&1
assert_eq "Week rollover: all-time runs = 2" "2" "$(mdfix_stat "$T12" '.verifiedstats.pick.all_time.runs')"
assert_eq "Week rollover: week period updated" "2026-W12" "$(mdfix_stat "$T12" '.verifiedstats.pick.week.period')"
assert_eq "Week rollover: week runs reset to 1" "1" "$(mdfix_stat "$T12" '.verifiedstats.pick.week.runs')"
assert_eq "Week rollover: week score_sum reset" "100" "$(mdfix_stat "$T12" '.verifiedstats.pick.week.score_sum')"
assert_eq "Week rollover: month still same (March)" "2026-03" "$(mdfix_stat "$T12" '.verifiedstats.pick.month.period')"
assert_eq "Week rollover: month runs accumulated" "2" "$(mdfix_stat "$T12" '.verifiedstats.pick.month.runs')"
rm -rf "$T12"

echo "--- Test 13: New skill entry gets full bucketed structure ---"
T13="$(setup_repo)"
rate "$T13" --skill review --score 3 --date 2026-06-15 --silent >/dev/null 2>&1
assert_eq "New skill: all-time runs = 1" "1" "$(mdfix_stat "$T13" '.verifiedstats.review.all_time.runs')"
assert_eq "New skill: all-time score_sum = 60" "60" "$(mdfix_stat "$T13" '.verifiedstats.review.all_time.score_sum')"
assert_eq "New skill: month period" "2026-06" "$(mdfix_stat "$T13" '.verifiedstats.review.month.period')"
assert_eq "New skill: month runs = 1" "1" "$(mdfix_stat "$T13" '.verifiedstats.review.month.runs')"
assert_eq "New skill: week period" "2026-W25" "$(mdfix_stat "$T13" '.verifiedstats.review.week.period')"
assert_eq "New skill: week runs = 1" "1" "$(mdfix_stat "$T13" '.verifiedstats.review.week.runs')"
assert_eq "New skill: no verified prior invented" "null" "$(registry "$T13" '.verified.review')"
assert_eq "New skill: prev_month seeded empty" "" "$(mdfix_stat "$T13" '.verifiedstats.review.prev_month.period')"
assert_eq "New skill: prev_month runs = 0" "0" "$(mdfix_stat "$T13" '.verifiedstats.review.prev_month.runs')"
rm -rf "$T13"

echo "--- Test 14: Same-month bump leaves existing prev_month untouched ---"
T14="$(setup_repo)"
seed "$T14" '.models[0].verifiedstats.pick = {
        "all_time":   {"runs": 7, "score_sum": 660},
        "prev_month": {"period": "2026-03", "runs": 5, "score_sum": 480},
        "month":      {"period": "2026-04", "runs": 2, "score_sum": 180},
        "week":       {"period": "2026-W17", "runs": 1, "score_sum": 80}
    }'
rate "$T14" --skill pick --score 5 --date 2026-04-29 --silent >/dev/null 2>&1
assert_eq "Same-month bump: month runs = 3" "3" "$(mdfix_stat "$T14" '.verifiedstats.pick.month.runs')"
assert_eq "Same-month bump: month score_sum = 280" "280" "$(mdfix_stat "$T14" '.verifiedstats.pick.month.score_sum')"
assert_eq "Same-month bump: month period unchanged" "2026-04" "$(mdfix_stat "$T14" '.verifiedstats.pick.month.period')"
assert_eq "Same-month bump: prev_month period preserved" "2026-03" "$(mdfix_stat "$T14" '.verifiedstats.pick.prev_month.period')"
assert_eq "Same-month bump: prev_month runs preserved" "5" "$(mdfix_stat "$T14" '.verifiedstats.pick.prev_month.runs')"
assert_eq "Same-month bump: prev_month score_sum preserved" "480" "$(mdfix_stat "$T14" '.verifiedstats.pick.prev_month.score_sum')"
rm -rf "$T14"

echo "--- Test 15: One-month rollover copies month into prev_month ---"
T15="$(setup_repo)"
seed "$T15" '.models[0].verifiedstats.pick = {
        "all_time":   {"runs": 5, "score_sum": 480},
        "prev_month": {"period": "", "runs": 0, "score_sum": 0},
        "month":      {"period": "2026-04", "runs": 5, "score_sum": 480},
        "week":       {"period": "2026-W17", "runs": 1, "score_sum": 80}
    }'
rate "$T15" --skill pick --score 4 --date 2026-05-01 --silent >/dev/null 2>&1
assert_eq "One-month rollover: prev_month period = old month" "2026-04" "$(mdfix_stat "$T15" '.verifiedstats.pick.prev_month.period')"
assert_eq "One-month rollover: prev_month runs = old month runs" "5" "$(mdfix_stat "$T15" '.verifiedstats.pick.prev_month.runs')"
assert_eq "One-month rollover: prev_month score_sum = old month sum" "480" "$(mdfix_stat "$T15" '.verifiedstats.pick.prev_month.score_sum')"
assert_eq "One-month rollover: month period updated" "2026-05" "$(mdfix_stat "$T15" '.verifiedstats.pick.month.period')"
assert_eq "One-month rollover: month runs reset to 1" "1" "$(mdfix_stat "$T15" '.verifiedstats.pick.month.runs')"
assert_eq "One-month rollover: month score_sum = 80" "80" "$(mdfix_stat "$T15" '.verifiedstats.pick.month.score_sum')"
rm -rf "$T15"

echo "--- Test 16: Multi-month skip zeros prev_month ---"
T16="$(setup_repo)"
seed "$T16" '.models[0].verifiedstats.pick = {
        "all_time":   {"runs": 5, "score_sum": 400},
        "prev_month": {"period": "2026-01", "runs": 2, "score_sum": 160},
        "month":      {"period": "2026-02", "runs": 3, "score_sum": 240},
        "week":       {"period": "2026-W08", "runs": 1, "score_sum": 80}
    }'
rate "$T16" --skill pick --score 5 --date 2026-05-01 --silent >/dev/null 2>&1
assert_eq "Multi-month skip: prev_month period zeroed" "" "$(mdfix_stat "$T16" '.verifiedstats.pick.prev_month.period')"
assert_eq "Multi-month skip: prev_month runs zeroed" "0" "$(mdfix_stat "$T16" '.verifiedstats.pick.prev_month.runs')"
assert_eq "Multi-month skip: prev_month score_sum zeroed" "0" "$(mdfix_stat "$T16" '.verifiedstats.pick.prev_month.score_sum')"
assert_eq "Multi-month skip: month period updated" "2026-05" "$(mdfix_stat "$T16" '.verifiedstats.pick.month.period')"
assert_eq "Multi-month skip: month runs = 1" "1" "$(mdfix_stat "$T16" '.verifiedstats.pick.month.runs')"
assert_eq "Multi-month skip: month score_sum = 100" "100" "$(mdfix_stat "$T16" '.verifiedstats.pick.month.score_sum')"
rm -rf "$T16"

echo "--- Test 17: Migration from flat seeds prev_month empty ---"
T17="$(setup_repo)"
seed "$T17" '.models[0].verifiedstats.pick = {"runs": 10, "score_sum": 920}'
rate "$T17" --skill pick --score 5 --date 2026-04-15 --silent >/dev/null 2>&1
assert_eq "Migration flat: all_time runs = 11" "11" "$(mdfix_stat "$T17" '.verifiedstats.pick.all_time.runs')"
assert_eq "Migration flat: all_time score_sum = 1020" "1020" "$(mdfix_stat "$T17" '.verifiedstats.pick.all_time.score_sum')"
assert_eq "Migration flat: prev_month period empty" "" "$(mdfix_stat "$T17" '.verifiedstats.pick.prev_month.period')"
assert_eq "Migration flat: prev_month runs = 0" "0" "$(mdfix_stat "$T17" '.verifiedstats.pick.prev_month.runs')"
assert_eq "Migration flat: month runs = 1" "1" "$(mdfix_stat "$T17" '.verifiedstats.pick.month.runs')"
assert_eq "Migration flat: month score_sum = 100" "100" "$(mdfix_stat "$T17" '.verifiedstats.pick.month.score_sum')"
rm -rf "$T17"

echo "--- Test 18: Migration from bucketed-but-no-prev_month adds empty prev_month ---"
T18="$(setup_repo)"
seed "$T18" '.models[0].verifiedstats.pick = {
        "all_time": {"runs": 4, "score_sum": 320},
        "month":    {"period": "2026-04", "runs": 1, "score_sum": 80},
        "week":     {"period": "2026-W17", "runs": 1, "score_sum": 80}
    }'
rate "$T18" --skill pick --score 5 --date 2026-04-29 --silent >/dev/null 2>&1
assert_eq "Bucketed-no-prev: all_time runs = 5" "5" "$(mdfix_stat "$T18" '.verifiedstats.pick.all_time.runs')"
assert_eq "Bucketed-no-prev: prev_month period empty" "" "$(mdfix_stat "$T18" '.verifiedstats.pick.prev_month.period')"
assert_eq "Bucketed-no-prev: prev_month runs = 0" "0" "$(mdfix_stat "$T18" '.verifiedstats.pick.prev_month.runs')"
assert_eq "Bucketed-no-prev: month period unchanged" "2026-04" "$(mdfix_stat "$T18" '.verifiedstats.pick.month.period')"
assert_eq "Bucketed-no-prev: month runs incremented" "2" "$(mdfix_stat "$T18" '.verifiedstats.pick.month.runs')"
assert_eq "Bucketed-no-prev: month score_sum incremented" "180" "$(mdfix_stat "$T18" '.verifiedstats.pick.month.score_sum')"
rm -rf "$T18"

# Tests 19-20 pin the verified-score ownership boundary (t1232): the generic
# accumulator persists an INDEPENDENT score for an explain-shadow operation
# (work-report / trail) even when the model has NO explain key. This is exactly
# what a "refrain from recording when explain is absent" accumulator special-case
# would break; these guards fail loudly if that data is ever silently discarded.
# Parity of work-report/trail with explain is a seed-authoring convention only
# (see Test 7 in test_codeagent_{work_report,trail}.sh), NOT a live invariant —
# real per-skill scores are legitimately independent. The score now lives in
# verifiedstats on the stats branch; the registry's `verified` prior is never
# written, so no key is added to it either.
echo "--- Test 19: work-report score persists on a model lacking explain (t1232) ---"
T19="$(setup_repo)"
seed "$T19" 'del(.models[0].verified.explain)'
out19=$(rate "$T19" --skill work-report --score 4 --date 2026-03-11 --silent 2>/dev/null)
assert_eq "work-report score recorded without explain partner" "UPDATED:claudecode/opus4_6:work-report:80" "$out19"
assert_eq "work-report all-time runs = 1" "1" "$(mdfix_stat "$T19" '.verifiedstats["work-report"].all_time.runs')"
assert_eq "accumulator did NOT fabricate an explain key" "false" "$(registry "$T19" '.verified | has("explain")')"
assert_eq "no work-report prior written to the registry" "false" "$(registry "$T19" '.verified | has("work-report")')"
rm -rf "$T19"

echo "--- Test 20: trail score persists on a model lacking explain (t1232) ---"
T20="$(setup_repo)"
seed "$T20" 'del(.models[0].verified.explain)'
out20=$(rate "$T20" --skill trail --score 4 --date 2026-03-11 --silent 2>/dev/null)
assert_eq "trail score recorded without explain partner" "UPDATED:claudecode/opus4_6:trail:80" "$out20"
assert_eq "trail all-time runs = 1" "1" "$(mdfix_stat "$T20" '.verifiedstats.trail.all_time.runs')"
assert_eq "accumulator did NOT fabricate an explain key" "false" "$(registry "$T20" '.verified | has("explain")')"
assert_eq "no trail prior written to the registry" "false" "$(registry "$T20" '.verified | has("trail")')"
rm -rf "$T20"

echo "--- Test 20b: the printed average includes the registry's legacy counters ---"
T20B="$(setup_repo)"
seed "$T20B" '.models[0].verifiedstats.pick = {"all_time": {"runs": 4, "score_sum": 320}}'
out20b=$(rate "$T20B" --skill pick --score 5 --date 2026-03-11 --silent 2>/dev/null)
assert_eq "effective average (320+100)/5 = 84, not the branch-only 100" \
    "UPDATED:claudecode/opus4_6:pick:84" "$out20b"
rm -rf "$T20B"

# =====================================================================
# Remote: the store's leased-push path
# =====================================================================

echo "--- Test 21: a remote write lands on origin's and the local aitask-stats ---"
B21="$(setup_remote_stats_repo "$SCRIPT")"
W21="$B21/work"
sha21="$(mdfix_registry_sha "$W21")"
rc=0; out21=$(rate "$W21" --skill pick --score 4 --silent 2>/dev/null) || rc=$?
assert_eq "remote: UPDATED / exit 0" "UPDATED:claudecode/opus4_6:pick:80|0" "$out21|$rc"
assert_eq "remote: origin's aitask-stats == local aitask-stats" \
    "$(git -C "$B21/origin.git" rev-parse -q --verify refs/heads/aitask-stats)" \
    "$(git -C "$W21" rev-parse -q --verify refs/heads/aitask-stats)"
assert_eq "remote: origin's blob holds the rating" '{"runs":1,"score_sum":80}' \
    "$(git -C "$B21/origin.git" show refs/heads/aitask-stats:claudecode.json | jq -c '.models.opus4_6.verifiedstats.pick.all_time')"
assert_eq "remote: registry file byte-identical" "$sha21" "$(mdfix_registry_sha "$W21")"
rm -rf "$B21"

echo "--- Test 24: unreachable origin — STATS_ERROR, non-zero, nothing recorded ---"
B24="$(setup_remote_stats_repo "$SCRIPT")"
W24="$B24/work"
git -C "$W24" remote set-url origin "$B24/does-not-exist.git"
rc=0; out24=$(rate "$W24" --skill pick --score 4 --silent 2>/dev/null) || rc=$?
assert_exit_nonzero_rc "unreachable: exit non-zero" "$rc"
assert_contains "unreachable: STATS_ERROR names the cause" "STATS_ERROR:unreachable:" "$out24"
assert_not_contains "unreachable: never claims UPDATED" "UPDATED:" "$out24"
rm -rf "$B24"

echo "--- Test 25: positive control — the same run with origin reachable is UPDATED / 0 ---"
B25="$(setup_remote_stats_repo "$SCRIPT")"
rc=0; out25=$(rate "$B25/work" --skill pick --score 4 --silent 2>/dev/null) || rc=$?
assert_eq "reachable: UPDATED / 0" "UPDATED:claudecode/opus4_6:pick:80|0" "$out25|$rc"
rm -rf "$B25"

echo "--- Test 27: non-silent value integrity (no diagnostics spliced in) ---"
B27="$(setup_remote_stats_repo "$SCRIPT")"
out27=$(rate "$B27/work" --skill pick --score 4 2>/dev/null)
assert_eq "non-silent: the last stdout line is the structured result" \
    "UPDATED:claudecode/opus4_6:pick:80" "$(printf '%s\n' "$out27" | tail -n 1)"
assert_contains "non-silent: a human success line precedes it" "verified score to 80" "$out27"
rm -rf "$B27"

echo "--- Test 28: the local (no-remote) path reports the correct count ---"
T28="$(setup_repo)"
rc28=0
out28=$(rate "$T28" --skill pick --score 4 --silent 2>/dev/null) || rc28=$?
assert_eq "no-remote path exits 0" "0" "$rc28"
assert_eq "no-remote path carries the correct value" "UPDATED:claudecode/opus4_6:pick:80" "$out28"
rm -rf "$T28"

echo "--- Test 32: real entry point from a NON-ROOT cwd (t1658_2) ---"
B32="$(setup_remote_stats_repo "$SCRIPT")"
W32="$B32/work"
mkdir -p "$W32/website"
rc32=0
out32=$(cd "$W32/website" && "$W32/.aitask-scripts/$SCRIPT" \
    --agent-string claudecode/opus4_6 --skill pick --score 4 --silent 2>/dev/null) || rc32=$?
assert_eq "32: reports UPDATED from a non-root cwd" "UPDATED:claudecode/opus4_6:pick:80|0" "$out32|$rc32"
assert_eq "32: the rating landed in THIS project's store" "1" \
    "$(git -C "$B32/origin.git" show refs/heads/aitask-stats:claudecode.json 2>/dev/null \
        | jq -r '.models.opus4_6.verifiedstats.pick.all_time.runs')"
rm -rf "$B32"

echo "--- Test t1884: resolver fallbacks reach the registry check, not a format error ---"
# A resolver fallback (claudecode/unregistered_*) parses, has no registry row,
# and must be refused with an agent-specific registration hint -- never with
# "Invalid agent string format", and never recorded against another row.
TFB="$(setup_repo)"
before_fb="$(cat "$TFB/aitasks/metadata/models_claudecode.json")"
rc=0
out_fb=$(cd "$TFB" && "./.aitask-scripts/$SCRIPT" --agent-string claudecode/unregistered_opus4_6 --skill pick --score 4 --date 2026-03-11 2>&1) || rc=$?
assert_exit_nonzero_rc "verified: fallback string exits non-zero" "$rc"
assert_not_contains "verified: fallback passes the format check" "Invalid agent string format" "$out_fb"
assert_contains "verified: fallback is refused as unregistered" "Model 'unregistered_opus4_6' not found" "$out_fb"
assert_contains "verified: claudecode hint names /aitask-add-model" "/aitask-add-model" "$out_fb"
assert_eq "verified: registry unchanged after refusal" "$before_fb" \
    "$(cat "$TFB/aitasks/metadata/models_claudecode.json")"

cat > "$TFB/aitasks/metadata/models_opencode.json" <<'EOF_OC'
{ "models": [ { "name": "opencode_foo", "cli_id": "opencode/foo", "notes": "t", "verified": {}, "verifiedstats": {} } ] }
EOF_OC
rc=0
out_oc=$(cd "$TFB" && "./.aitask-scripts/$SCRIPT" --agent-string opencode/unregistered_x --skill pick --score 4 --date 2026-03-11 2>&1) || rc=$?
assert_exit_nonzero_rc "verified: opencode fallback exits non-zero" "$rc"
assert_contains "verified: opencode hint names /aitask-refresh-code-models" "/aitask-refresh-code-models" "$out_oc"
assert_not_contains "verified: opencode hint does not offer add-model as the route" "register it with /aitask-add-model" "$out_oc"

cp "$PROJECT_DIR/.aitask-scripts/aitask_resolve_detected_agent.sh" "$TFB/.aitask-scripts/"
rc=0
out_cli=$(cd "$TFB" && "./.aitask-scripts/$SCRIPT" --agent claudecode --cli-id 'claude-opus-9-9[1m]' --skill pick --score 4 --date 2026-03-11 2>&1) || rc=$?
assert_exit_nonzero_rc "verified: --agent/--cli-id fallback exits non-zero" "$rc"
assert_not_contains "verified: --cli-id fallback passes the format check" "Invalid agent string format" "$out_cli"
assert_contains "verified: --cli-id fallback is refused as unregistered" "Model 'unregistered_claude_opus_9_9_1m' not found" "$out_cli"
assert_eq "verified: registry unchanged after --cli-id refusal" "$before_fb" \
    "$(cat "$TFB/aitasks/metadata/models_claudecode.json")"
assert_eq "verified: nothing recorded on the stats branch" "no" \
    "$(git -C "$TFB" rev-parse -q --verify refs/heads/aitask-stats >/dev/null && echo yes || echo no)"
rm -rf "$TFB"

# The bridge (lib/verified_update_lib.sh model_stats_write) is exercised in
# full by tests/test_usage_update.sh; here only the verified writer's own use of
# it: the score is passed through and an unknown average is a recorded success.
echo "--- Test bridge: the verified writer's CLI call ---"
TB="$(setup_repo)"
cat > "$TB/.aitask-scripts/aitask_model_stats.py" <<'PY'
import sys
argv = sys.argv[1:]
score = next((a.split("=", 1)[1] for a in argv if a.startswith("--score=")), "missing")
sys.stderr.write(f"stub got verb={argv[0]} score={score}\n")
print("UPDATED:claudecode/opus4_6:pick:unknown")
PY
rc=0; outb=$(rate "$TB" --skill pick --score 3 --silent 2>"$TB/err") || rc=$?
assert_eq "bridge: unknown average is a recorded success" "UPDATED:claudecode/opus4_6:pick:unknown|0" "$outb|$rc"
assert_contains "bridge: record-verified is called with the raw score" "verb=record-verified score=3" "$(cat "$TB/err")"
outb_ns=$(rate "$TB" --skill pick --score 3 2>/dev/null)
assert_contains "bridge: non-silent unknown says the rating was recorded" "current average unavailable" "$outb_ns"
printf 'import sys\nprint("STATS_ERROR:boom")\nsys.exit(1)\n' > "$TB/.aitask-scripts/aitask_model_stats.py"
rc=0; outb=$(rate "$TB" --skill pick --score 3 --silent 2>/dev/null) || rc=$?
assert_eq "bridge: STATS_ERROR passes through, exit non-zero" "STATS_ERROR:boom|1" "$outb|$rc"
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
