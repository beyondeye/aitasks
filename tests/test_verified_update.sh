#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

# Shared metadata fixtures (legacy-mode remote + real branch-mode worktree).
# shellcheck source=lib/metadata_update_fixture.sh
. "$PROJECT_DIR/tests/lib/metadata_update_fixture.sh"

setup_repo() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    (
        cd "$tmpdir"
        git init --quiet
        git config user.email "test@test.com"
        git config user.name "Test"
        populate_repo "$tmpdir"

        git add .
        git commit -m "Initial setup" --quiet
    )

    echo "$tmpdir"
}

populate_repo() {
    local repo_dir="$1"

    mkdir -p "$repo_dir/aitasks/metadata"
    setup_fake_aitask_repo "$repo_dir"

    cp "$PROJECT_DIR/.aitask-scripts/aitask_verified_update.sh" "$repo_dir/.aitask-scripts/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" "$repo_dir/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" "$repo_dir/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/verified_update_lib.sh" "$repo_dir/.aitask-scripts/lib/"
    chmod +x "$repo_dir/.aitask-scripts/aitask_verified_update.sh"

    cat > "$repo_dir/ait" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

case "${1:-}" in
    git)
        shift
        exec git "$@"
        ;;
    *)
        echo "unsupported test helper command" >&2
        exit 1
        ;;
esac
EOF
    chmod +x "$repo_dir/ait"

    cat > "$repo_dir/aitasks/metadata/models_claudecode.json" <<'EOF'
{
  "models": [
    {
      "name": "opus4_6",
      "cli_id": "claude-opus-4-6",
      "notes": "Test model",
      "verified": {
        "pick": 80,
        "explain": 60,
        "batch-review": 0
      }
    }
  ]
}
EOF
}

setup_remote_repo() {
    local basedir origin_dir seed_dir work_dir
    basedir="$(mktemp -d)"
    origin_dir="$basedir/origin.git"
    seed_dir="$basedir/seed"
    work_dir="$basedir/work"

    git init --bare --quiet "$origin_dir"
    mkdir -p "$seed_dir"

    (
        cd "$seed_dir"
        git init --quiet
        git config user.email "test@test.com"
        git config user.name "Test"
        populate_repo "$seed_dir"
        git add .
        git commit -m "Initial setup" --quiet
        git branch -M main
        git remote add origin "$origin_dir"
        git push --quiet -u origin main
    )

    git --git-dir="$origin_dir" symbolic-ref HEAD refs/heads/main
    git clone --quiet --branch main "$origin_dir" "$work_dir" >/dev/null 2>&1
    (
        cd "$work_dir"
        git config user.email "test@test.com"
        git config user.name "Test"
    )

    echo "$basedir"
}

json_get() {
    local repo_dir="$1" jq_filter="$2"
    jq -r "$jq_filter" "$repo_dir/aitasks/metadata/models_claudecode.json"
}

set +e

echo "=== aitask_verified_update.sh Tests ==="
echo ""

echo "--- Test 1: Valid update creates bucketed stats ---"
TMPDIR_1="$(setup_repo)"
output1=$(cd "$TMPDIR_1" && ./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill pick --score 4 --date 2026-03-11 2>&1)
assert_contains "Structured success output" "UPDATED:claudecode/opus4_6:pick:80" "$output1"
assert_eq "All-time runs initialized to 1" "1" "$(json_get "$TMPDIR_1" '.models[0].verifiedstats.pick.all_time.runs')"
assert_eq "All-time score sum initialized to 80" "80" "$(json_get "$TMPDIR_1" '.models[0].verifiedstats.pick.all_time.score_sum')"
assert_eq "Month period set" "2026-03" "$(json_get "$TMPDIR_1" '.models[0].verifiedstats.pick.month.period')"
assert_eq "Month runs initialized to 1" "1" "$(json_get "$TMPDIR_1" '.models[0].verifiedstats.pick.month.runs')"
assert_eq "Week period set" "2026-W11" "$(json_get "$TMPDIR_1" '.models[0].verifiedstats.pick.week.period')"
assert_eq "Week runs initialized to 1" "1" "$(json_get "$TMPDIR_1" '.models[0].verifiedstats.pick.week.runs')"
assert_eq "Verified pick initialized to 80" "80" "$(json_get "$TMPDIR_1" '.models[0].verified.pick')"
assert_eq "Existing verified key preserved (batch-review)" "0" "$(json_get "$TMPDIR_1" '.models[0].verified["batch-review"]')"
assert_eq "Existing verified key preserved (explain)" "60" "$(json_get "$TMPDIR_1" '.models[0].verified.explain')"
rm -rf "$TMPDIR_1"

echo "--- Test 2: Rolling average updates correctly ---"
TMPDIR_2="$(setup_repo)"
(cd "$TMPDIR_2" && ./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill pick --score 4 --date 2026-03-11 >/dev/null 2>&1)
output2=$(cd "$TMPDIR_2" && ./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill pick --score 5 --date 2026-03-11 2>&1)
assert_contains "Structured rolling average output" "UPDATED:claudecode/opus4_6:pick:90" "$output2"
assert_eq "All-time runs incremented to 2" "2" "$(json_get "$TMPDIR_2" '.models[0].verifiedstats.pick.all_time.runs')"
assert_eq "All-time score sum incremented to 180" "180" "$(json_get "$TMPDIR_2" '.models[0].verifiedstats.pick.all_time.score_sum')"
assert_eq "Month runs incremented to 2" "2" "$(json_get "$TMPDIR_2" '.models[0].verifiedstats.pick.month.runs')"
assert_eq "Week runs incremented to 2" "2" "$(json_get "$TMPDIR_2" '.models[0].verifiedstats.pick.week.runs')"
assert_eq "Verified pick rounded to 90" "90" "$(json_get "$TMPDIR_2" '.models[0].verified.pick')"
rm -rf "$TMPDIR_2"

echo "--- Test 3: Invalid agent string fails ---"
TMPDIR_3="$(setup_repo)"
assert_exit_nonzero "Invalid agent string rejected" bash -c "cd '$TMPDIR_3' && ./.aitask-scripts/aitask_verified_update.sh --agent-string invalid --skill pick --score 4"
rm -rf "$TMPDIR_3"

echo "--- Test 4: Invalid score fails ---"
TMPDIR_4="$(setup_repo)"
assert_exit_nonzero "Invalid score rejected" bash -c "cd '$TMPDIR_4' && ./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill pick --score 6"
rm -rf "$TMPDIR_4"

echo "--- Test 5: Missing model fails ---"
TMPDIR_5="$(setup_repo)"
assert_exit_nonzero "Missing model rejected" bash -c "cd '$TMPDIR_5' && ./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/sonnet4_6 --skill pick --score 4"
rm -rf "$TMPDIR_5"

echo "--- Test 6: Help exits 0 ---"
TMPDIR_6="$(setup_repo)"
assert_exit_zero "Help exits successfully" bash -c "cd '$TMPDIR_6' && ./.aitask-scripts/aitask_verified_update.sh --help"
rm -rf "$TMPDIR_6"

echo "--- Test 7: Missing verifiedstats is created automatically with buckets ---"
TMPDIR_7="$(setup_repo)"
(cd "$TMPDIR_7" && ./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill explain --score 3 --date 2026-03-11 >/dev/null 2>&1)
assert_eq "Explain all-time runs created" "1" "$(json_get "$TMPDIR_7" '.models[0].verifiedstats.explain.all_time.runs')"
assert_eq "Explain all-time score sum created" "60" "$(json_get "$TMPDIR_7" '.models[0].verifiedstats.explain.all_time.score_sum')"
assert_eq "Explain month runs created" "1" "$(json_get "$TMPDIR_7" '.models[0].verifiedstats.explain.month.runs')"
assert_eq "Explain week runs created" "1" "$(json_get "$TMPDIR_7" '.models[0].verifiedstats.explain.week.runs')"
assert_eq "Explain verified updated" "60" "$(json_get "$TMPDIR_7" '.models[0].verified.explain')"
rm -rf "$TMPDIR_7"

echo "--- Test 8: Silent mode prints only structured result ---"
TMPDIR_8="$(setup_repo)"
output8=$(cd "$TMPDIR_8" && ./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill pick --score 4 --silent 2>&1)
assert_eq "Silent output is structured only" "UPDATED:claudecode/opus4_6:pick:80" "$output8"
rm -rf "$TMPDIR_8"

echo "--- Test 9: Remote retry preserves concurrent updates ---"
TMPDIR_9="$(setup_remote_repo)"
WORKDIR_9="$TMPDIR_9/work"
ORIGIN_9="$TMPDIR_9/origin.git"
HOOK_FLAG_9="$TMPDIR_9/hook-ran"
cat > "$TMPDIR_9/hook.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [[ "${AITASK_VERIFIED_UPDATE_ATTEMPT:-}" != "1" ]]; then
    exit 0
fi

if [[ -f "${AITASK_VERIFIED_UPDATE_HOOK_FLAG:-}" ]]; then
    exit 0
fi

touch "$AITASK_VERIFIED_UPDATE_HOOK_FLAG"

tmpdir="$(mktemp -d)"
git clone --quiet "$AITASK_VERIFIED_UPDATE_TEST_ORIGIN" "$tmpdir/repo" >/dev/null 2>&1
(
    cd "$tmpdir/repo"
    git config user.email "test@test.com"
    git config user.name "Test"
    tmp_json="$(mktemp)"
    jq '
        .models |= map(
            if .name == "opus4_6" then
                .verified = (.verified // {}) |
                .verifiedstats = (.verifiedstats // {}) |
                .verifiedstats.pick = {
                    "runs": ((.verifiedstats.pick.runs // 0) + 1),
                    "score_sum": ((.verifiedstats.pick.score_sum // 0) + 80)
                } |
                .verified.pick = ((.verifiedstats.pick.score_sum / .verifiedstats.pick.runs) | round)
            else
                .
            end
        )
    ' aitasks/metadata/models_claudecode.json > "$tmp_json"
    mv "$tmp_json" aitasks/metadata/models_claudecode.json
    git add aitasks/metadata/models_claudecode.json
    git commit -m "competing verified update" --quiet
    git push --quiet origin main
)
rm -rf "$tmpdir"
EOF
chmod +x "$TMPDIR_9/hook.sh"
output9=$(cd "$WORKDIR_9" && \
    AITASK_VERIFIED_UPDATE_BEFORE_PUSH_HOOK="$TMPDIR_9/hook.sh" \
    AITASK_VERIFIED_UPDATE_HOOK_FLAG="$HOOK_FLAG_9" \
    AITASK_VERIFIED_UPDATE_TEST_ORIGIN="$ORIGIN_9" \
    ./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill pick --score 4 --silent 2>&1)
assert_eq "Remote retry keeps structured silent output" "UPDATED:claudecode/opus4_6:pick:80" "$output9"
assert_eq "Concurrent remote updates both counted" "2" "$(json_get "$WORKDIR_9" '.models[0].verifiedstats.pick.all_time.runs')"
assert_eq "Concurrent score sum preserved" "160" "$(json_get "$WORKDIR_9" '.models[0].verifiedstats.pick.all_time.score_sum')"
rm -rf "$TMPDIR_9"

echo "--- Test 10: Old schema migration on update ---"
TMPDIR_10="$(setup_repo)"
# Inject old-format verifiedstats manually
tmp_json_10="$(mktemp)"
jq '.models[0].verifiedstats.pick = {"runs": 3, "score_sum": 240}' \
    "$TMPDIR_10/aitasks/metadata/models_claudecode.json" > "$tmp_json_10"
mv "$tmp_json_10" "$TMPDIR_10/aitasks/metadata/models_claudecode.json"
(cd "$TMPDIR_10" && git add -A && git commit -m "old format" --quiet)
output10=$(cd "$TMPDIR_10" && ./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill pick --score 5 --date 2026-03-11 --silent 2>&1)
assert_eq "Migration: structured output" "UPDATED:claudecode/opus4_6:pick:85" "$output10"
assert_eq "Migration: all-time runs = old + 1" "4" "$(json_get "$TMPDIR_10" '.models[0].verifiedstats.pick.all_time.runs')"
assert_eq "Migration: all-time score_sum = old + 100" "340" "$(json_get "$TMPDIR_10" '.models[0].verifiedstats.pick.all_time.score_sum')"
assert_eq "Migration: month runs = 1 (fresh)" "1" "$(json_get "$TMPDIR_10" '.models[0].verifiedstats.pick.month.runs')"
assert_eq "Migration: month period set" "2026-03" "$(json_get "$TMPDIR_10" '.models[0].verifiedstats.pick.month.period')"
assert_eq "Migration: week runs = 1 (fresh)" "1" "$(json_get "$TMPDIR_10" '.models[0].verifiedstats.pick.week.runs')"
assert_eq "Migration: verified avg correct" "85" "$(json_get "$TMPDIR_10" '.models[0].verified.pick')"
rm -rf "$TMPDIR_10"

echo "--- Test 11: Month rollover resets month but keeps all-time ---"
TMPDIR_11="$(setup_repo)"
(cd "$TMPDIR_11" && ./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill pick --score 4 --date 2026-01-15 --silent >/dev/null 2>&1)
(cd "$TMPDIR_11" && ./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill pick --score 5 --date 2026-02-15 --silent >/dev/null 2>&1)
assert_eq "Month rollover: all-time runs = 2" "2" "$(json_get "$TMPDIR_11" '.models[0].verifiedstats.pick.all_time.runs')"
assert_eq "Month rollover: all-time score_sum = 180" "180" "$(json_get "$TMPDIR_11" '.models[0].verifiedstats.pick.all_time.score_sum')"
assert_eq "Month rollover: month period updated" "2026-02" "$(json_get "$TMPDIR_11" '.models[0].verifiedstats.pick.month.period')"
assert_eq "Month rollover: month runs reset to 1" "1" "$(json_get "$TMPDIR_11" '.models[0].verifiedstats.pick.month.runs')"
assert_eq "Month rollover: month score_sum reset" "100" "$(json_get "$TMPDIR_11" '.models[0].verifiedstats.pick.month.score_sum')"
rm -rf "$TMPDIR_11"

echo "--- Test 12: Week rollover resets week but keeps all-time ---"
TMPDIR_12="$(setup_repo)"
(cd "$TMPDIR_12" && ./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill pick --score 4 --date 2026-03-09 --silent >/dev/null 2>&1)
(cd "$TMPDIR_12" && ./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill pick --score 5 --date 2026-03-16 --silent >/dev/null 2>&1)
assert_eq "Week rollover: all-time runs = 2" "2" "$(json_get "$TMPDIR_12" '.models[0].verifiedstats.pick.all_time.runs')"
assert_eq "Week rollover: week period updated" "2026-W12" "$(json_get "$TMPDIR_12" '.models[0].verifiedstats.pick.week.period')"
assert_eq "Week rollover: week runs reset to 1" "1" "$(json_get "$TMPDIR_12" '.models[0].verifiedstats.pick.week.runs')"
assert_eq "Week rollover: week score_sum reset" "100" "$(json_get "$TMPDIR_12" '.models[0].verifiedstats.pick.week.score_sum')"
assert_eq "Week rollover: month still same (March)" "2026-03" "$(json_get "$TMPDIR_12" '.models[0].verifiedstats.pick.month.period')"
assert_eq "Week rollover: month runs accumulated" "2" "$(json_get "$TMPDIR_12" '.models[0].verifiedstats.pick.month.runs')"
rm -rf "$TMPDIR_12"

echo "--- Test 13: New skill entry gets full bucketed structure ---"
TMPDIR_13="$(setup_repo)"
(cd "$TMPDIR_13" && ./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill review --score 3 --date 2026-06-15 --silent >/dev/null 2>&1)
assert_eq "New skill: all-time runs = 1" "1" "$(json_get "$TMPDIR_13" '.models[0].verifiedstats.review.all_time.runs')"
assert_eq "New skill: all-time score_sum = 60" "60" "$(json_get "$TMPDIR_13" '.models[0].verifiedstats.review.all_time.score_sum')"
assert_eq "New skill: month period" "2026-06" "$(json_get "$TMPDIR_13" '.models[0].verifiedstats.review.month.period')"
assert_eq "New skill: month runs = 1" "1" "$(json_get "$TMPDIR_13" '.models[0].verifiedstats.review.month.runs')"
assert_eq "New skill: week period" "2026-W25" "$(json_get "$TMPDIR_13" '.models[0].verifiedstats.review.week.period')"
assert_eq "New skill: week runs = 1" "1" "$(json_get "$TMPDIR_13" '.models[0].verifiedstats.review.week.runs')"
assert_eq "New skill: verified avg = 60" "60" "$(json_get "$TMPDIR_13" '.models[0].verified.review')"
assert_eq "New skill: prev_month seeded empty" "" "$(json_get "$TMPDIR_13" '.models[0].verifiedstats.review.prev_month.period')"
assert_eq "New skill: prev_month runs = 0" "0" "$(json_get "$TMPDIR_13" '.models[0].verifiedstats.review.prev_month.runs')"
rm -rf "$TMPDIR_13"

echo "--- Test 14: Same-month bump leaves existing prev_month untouched ---"
TMPDIR_14="$(setup_repo)"
tmp_json_14="$(mktemp)"
jq '.models[0].verifiedstats.pick = {
        "all_time":   {"runs": 7, "score_sum": 660},
        "prev_month": {"period": "2026-03", "runs": 5, "score_sum": 480},
        "month":      {"period": "2026-04", "runs": 2, "score_sum": 180},
        "week":       {"period": "2026-W17", "runs": 1, "score_sum": 80}
    }' \
    "$TMPDIR_14/aitasks/metadata/models_claudecode.json" > "$tmp_json_14"
mv "$tmp_json_14" "$TMPDIR_14/aitasks/metadata/models_claudecode.json"
(cd "$TMPDIR_14" && git add -A && git commit -m "seed prev_month" --quiet)
(cd "$TMPDIR_14" && ./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill pick --score 5 --date 2026-04-29 --silent >/dev/null 2>&1)
assert_eq "Same-month bump: month runs = 3" "3" "$(json_get "$TMPDIR_14" '.models[0].verifiedstats.pick.month.runs')"
assert_eq "Same-month bump: month score_sum = 280" "280" "$(json_get "$TMPDIR_14" '.models[0].verifiedstats.pick.month.score_sum')"
assert_eq "Same-month bump: month period unchanged" "2026-04" "$(json_get "$TMPDIR_14" '.models[0].verifiedstats.pick.month.period')"
assert_eq "Same-month bump: prev_month period preserved" "2026-03" "$(json_get "$TMPDIR_14" '.models[0].verifiedstats.pick.prev_month.period')"
assert_eq "Same-month bump: prev_month runs preserved" "5" "$(json_get "$TMPDIR_14" '.models[0].verifiedstats.pick.prev_month.runs')"
assert_eq "Same-month bump: prev_month score_sum preserved" "480" "$(json_get "$TMPDIR_14" '.models[0].verifiedstats.pick.prev_month.score_sum')"
rm -rf "$TMPDIR_14"

echo "--- Test 15: One-month rollover copies month into prev_month ---"
TMPDIR_15="$(setup_repo)"
tmp_json_15="$(mktemp)"
jq '.models[0].verifiedstats.pick = {
        "all_time":   {"runs": 5, "score_sum": 480},
        "prev_month": {"period": "", "runs": 0, "score_sum": 0},
        "month":      {"period": "2026-04", "runs": 5, "score_sum": 480},
        "week":       {"period": "2026-W17", "runs": 1, "score_sum": 80}
    }' \
    "$TMPDIR_15/aitasks/metadata/models_claudecode.json" > "$tmp_json_15"
mv "$tmp_json_15" "$TMPDIR_15/aitasks/metadata/models_claudecode.json"
(cd "$TMPDIR_15" && git add -A && git commit -m "seed pre-rollover" --quiet)
(cd "$TMPDIR_15" && ./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill pick --score 4 --date 2026-05-01 --silent >/dev/null 2>&1)
assert_eq "One-month rollover: prev_month period = old month" "2026-04" "$(json_get "$TMPDIR_15" '.models[0].verifiedstats.pick.prev_month.period')"
assert_eq "One-month rollover: prev_month runs = old month runs" "5" "$(json_get "$TMPDIR_15" '.models[0].verifiedstats.pick.prev_month.runs')"
assert_eq "One-month rollover: prev_month score_sum = old month sum" "480" "$(json_get "$TMPDIR_15" '.models[0].verifiedstats.pick.prev_month.score_sum')"
assert_eq "One-month rollover: month period updated" "2026-05" "$(json_get "$TMPDIR_15" '.models[0].verifiedstats.pick.month.period')"
assert_eq "One-month rollover: month runs reset to 1" "1" "$(json_get "$TMPDIR_15" '.models[0].verifiedstats.pick.month.runs')"
assert_eq "One-month rollover: month score_sum = 80" "80" "$(json_get "$TMPDIR_15" '.models[0].verifiedstats.pick.month.score_sum')"
rm -rf "$TMPDIR_15"

echo "--- Test 16: Multi-month skip zeros prev_month ---"
TMPDIR_16="$(setup_repo)"
tmp_json_16="$(mktemp)"
jq '.models[0].verifiedstats.pick = {
        "all_time":   {"runs": 5, "score_sum": 400},
        "prev_month": {"period": "2026-01", "runs": 2, "score_sum": 160},
        "month":      {"period": "2026-02", "runs": 3, "score_sum": 240},
        "week":       {"period": "2026-W08", "runs": 1, "score_sum": 80}
    }' \
    "$TMPDIR_16/aitasks/metadata/models_claudecode.json" > "$tmp_json_16"
mv "$tmp_json_16" "$TMPDIR_16/aitasks/metadata/models_claudecode.json"
(cd "$TMPDIR_16" && git add -A && git commit -m "seed multi-month-skip" --quiet)
(cd "$TMPDIR_16" && ./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill pick --score 5 --date 2026-05-01 --silent >/dev/null 2>&1)
assert_eq "Multi-month skip: prev_month period zeroed" "" "$(json_get "$TMPDIR_16" '.models[0].verifiedstats.pick.prev_month.period')"
assert_eq "Multi-month skip: prev_month runs zeroed" "0" "$(json_get "$TMPDIR_16" '.models[0].verifiedstats.pick.prev_month.runs')"
assert_eq "Multi-month skip: prev_month score_sum zeroed" "0" "$(json_get "$TMPDIR_16" '.models[0].verifiedstats.pick.prev_month.score_sum')"
assert_eq "Multi-month skip: month period updated" "2026-05" "$(json_get "$TMPDIR_16" '.models[0].verifiedstats.pick.month.period')"
assert_eq "Multi-month skip: month runs = 1" "1" "$(json_get "$TMPDIR_16" '.models[0].verifiedstats.pick.month.runs')"
assert_eq "Multi-month skip: month score_sum = 100" "100" "$(json_get "$TMPDIR_16" '.models[0].verifiedstats.pick.month.score_sum')"
rm -rf "$TMPDIR_16"

echo "--- Test 17: Migration from flat seeds prev_month empty ---"
TMPDIR_17="$(setup_repo)"
tmp_json_17="$(mktemp)"
jq '.models[0].verifiedstats.pick = {"runs": 10, "score_sum": 920}' \
    "$TMPDIR_17/aitasks/metadata/models_claudecode.json" > "$tmp_json_17"
mv "$tmp_json_17" "$TMPDIR_17/aitasks/metadata/models_claudecode.json"
(cd "$TMPDIR_17" && git add -A && git commit -m "seed flat" --quiet)
(cd "$TMPDIR_17" && ./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill pick --score 5 --date 2026-04-15 --silent >/dev/null 2>&1)
assert_eq "Migration flat: all_time runs = 11" "11" "$(json_get "$TMPDIR_17" '.models[0].verifiedstats.pick.all_time.runs')"
assert_eq "Migration flat: all_time score_sum = 1020" "1020" "$(json_get "$TMPDIR_17" '.models[0].verifiedstats.pick.all_time.score_sum')"
assert_eq "Migration flat: prev_month period empty" "" "$(json_get "$TMPDIR_17" '.models[0].verifiedstats.pick.prev_month.period')"
assert_eq "Migration flat: prev_month runs = 0" "0" "$(json_get "$TMPDIR_17" '.models[0].verifiedstats.pick.prev_month.runs')"
assert_eq "Migration flat: month runs = 1" "1" "$(json_get "$TMPDIR_17" '.models[0].verifiedstats.pick.month.runs')"
assert_eq "Migration flat: month score_sum = 100" "100" "$(json_get "$TMPDIR_17" '.models[0].verifiedstats.pick.month.score_sum')"
rm -rf "$TMPDIR_17"

echo "--- Test 18: Migration from bucketed-but-no-prev_month adds empty prev_month ---"
TMPDIR_18="$(setup_repo)"
tmp_json_18="$(mktemp)"
jq '.models[0].verifiedstats.pick = {
        "all_time": {"runs": 4, "score_sum": 320},
        "month":    {"period": "2026-04", "runs": 1, "score_sum": 80},
        "week":     {"period": "2026-W17", "runs": 1, "score_sum": 80}
    }' \
    "$TMPDIR_18/aitasks/metadata/models_claudecode.json" > "$tmp_json_18"
mv "$tmp_json_18" "$TMPDIR_18/aitasks/metadata/models_claudecode.json"
(cd "$TMPDIR_18" && git add -A && git commit -m "seed bucketed-no-prev" --quiet)
(cd "$TMPDIR_18" && ./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill pick --score 5 --date 2026-04-29 --silent >/dev/null 2>&1)
assert_eq "Bucketed-no-prev: all_time runs = 5" "5" "$(json_get "$TMPDIR_18" '.models[0].verifiedstats.pick.all_time.runs')"
assert_eq "Bucketed-no-prev: prev_month period empty" "" "$(json_get "$TMPDIR_18" '.models[0].verifiedstats.pick.prev_month.period')"
assert_eq "Bucketed-no-prev: prev_month runs = 0" "0" "$(json_get "$TMPDIR_18" '.models[0].verifiedstats.pick.prev_month.runs')"
assert_eq "Bucketed-no-prev: month period unchanged" "2026-04" "$(json_get "$TMPDIR_18" '.models[0].verifiedstats.pick.month.period')"
assert_eq "Bucketed-no-prev: month runs incremented" "2" "$(json_get "$TMPDIR_18" '.models[0].verifiedstats.pick.month.runs')"
assert_eq "Bucketed-no-prev: month score_sum incremented" "180" "$(json_get "$TMPDIR_18" '.models[0].verifiedstats.pick.month.score_sum')"
rm -rf "$TMPDIR_18"

# Tests 19-20 pin the verified-score ownership boundary (t1232): the generic
# accumulator persists an INDEPENDENT verified score for an explain-shadow
# operation (work-report / trail) even when the model has NO explain key. This is
# exactly what a "refrain from creating verified entries when explain is absent"
# accumulator special-case would break; these guards fail loudly if that data is
# ever silently discarded. Parity of work-report/trail with explain is a
# seed-authoring convention only (see Test 7 in test_codeagent_{work_report,trail}.sh),
# NOT a live-file invariant — real per-skill scores are legitimately independent.
echo "--- Test 19: work-report score persists on a model lacking explain (t1232) ---"
TMPDIR_19="$(setup_repo)"
# Drop the explain key so opus4_6 has no parity partner.
tmp_json_19="$(mktemp)"
jq 'del(.models[0].verified.explain)' \
    "$TMPDIR_19/aitasks/metadata/models_claudecode.json" > "$tmp_json_19"
mv "$tmp_json_19" "$TMPDIR_19/aitasks/metadata/models_claudecode.json"
(cd "$TMPDIR_19" && git add -A && git commit -m "drop explain key" --quiet)
(cd "$TMPDIR_19" && ./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill work-report --score 4 --date 2026-03-11 --silent >/dev/null 2>&1)
assert_eq "work-report verified persisted without explain partner" "80" "$(json_get "$TMPDIR_19" '.models[0].verified["work-report"]')"
assert_eq "work-report all-time runs = 1" "1" "$(json_get "$TMPDIR_19" '.models[0].verifiedstats["work-report"].all_time.runs')"
assert_eq "accumulator did NOT fabricate an explain key" "false" "$(json_get "$TMPDIR_19" '.models[0].verified | has("explain")')"
rm -rf "$TMPDIR_19"

echo "--- Test 20: trail score persists on a model lacking explain (t1232) ---"
TMPDIR_20="$(setup_repo)"
tmp_json_20="$(mktemp)"
jq 'del(.models[0].verified.explain)' \
    "$TMPDIR_20/aitasks/metadata/models_claudecode.json" > "$tmp_json_20"
mv "$tmp_json_20" "$TMPDIR_20/aitasks/metadata/models_claudecode.json"
(cd "$TMPDIR_20" && git add -A && git commit -m "drop explain key" --quiet)
(cd "$TMPDIR_20" && ./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill trail --score 4 --date 2026-03-11 --silent >/dev/null 2>&1)
assert_eq "trail verified persisted without explain partner" "80" "$(json_get "$TMPDIR_20" '.models[0].verified.trail')"
assert_eq "trail all-time runs = 1" "1" "$(json_get "$TMPDIR_20" '.models[0].verifiedstats.trail.all_time.runs')"
assert_eq "accumulator did NOT fabricate an explain key" "false" "$(json_get "$TMPDIR_20" '.models[0].verified | has("explain")')"
rm -rf "$TMPDIR_20"

# =====================================================================
# Local-ref invariant and the partial-result contract (t1658_1)
#
# The metadata commit is built in a throwaway clone and pushed straight to
# origin, so "the update succeeded" and "the commit is on the LOCAL data
# branch" are two different claims. Everything below asserts the second one.
# =====================================================================

echo "--- Test 21: successful remote update reaches the LOCAL branch ---"
TMPDIR_21="$(setup_remote_repo)"
WORK_21="$TMPDIR_21/work"
out21=$(cd "$WORK_21" && ./.aitask-scripts/aitask_verified_update.sh \
    --agent-string claudecode/opus4_6 --skill pick --score 4 --silent 2>/dev/null)
rc21=$?
assert_eq "remote update reports UPDATED" "UPDATED:claudecode/opus4_6:pick:80" "$out21"
assert_eq "remote update exits 0" "0" "$rc21"
assert_eq "nothing left unpulled — the commit is local" "0" \
    "$(cd "$WORK_21" && git rev-list --count 'HEAD..@{u}' 2>/dev/null)"
origin_sha_21="$(cd "$WORK_21" && git rev-parse '@{u}')"
(cd "$WORK_21" && git merge-base --is-ancestor "$origin_sha_21" HEAD 2>/dev/null)
assert_eq "the pushed commit is an ancestor of local HEAD" "0" "$?"
rm -rf "$TMPDIR_21"

echo "--- Test 22: an unrelated dirty file no longer strands the commit ---"
# This is the reported bug: a dirty data worktree made the compensating
# `pull --rebase` refuse before it even fetched, so the commit stayed on origin.
TMPDIR_22="$(setup_remote_repo)"
WORK_22="$TMPDIR_22/work"
printf 'unrelated local edit\n' > "$WORK_22/unrelated.txt"
out22=$(cd "$WORK_22" && ./.aitask-scripts/aitask_verified_update.sh \
    --agent-string claudecode/opus4_6 --skill pick --score 4 --silent 2>/dev/null)
rc22=$?
assert_eq "dirty-but-unrelated still reports UPDATED" "UPDATED:claudecode/opus4_6:pick:80" "$out22"
assert_eq "dirty-but-unrelated still exits 0" "0" "$rc22"
assert_eq "dirty-but-unrelated: commit reached the local branch" "0" \
    "$(cd "$WORK_22" && git rev-list --count 'HEAD..@{u}' 2>/dev/null)"
assert_eq "the unrelated dirty file is untouched" "unrelated local edit" \
    "$(cat "$WORK_22/unrelated.txt")"
rm -rf "$TMPDIR_22"

echo "--- Test 23: divergence prevention — a local unpushed commit is published first ---"
TMPDIR_23="$(setup_remote_repo)"
WORK_23="$TMPDIR_23/work"
printf 'local work\n' > "$WORK_23/local_only.txt"
(cd "$WORK_23" && git add local_only.txt && git commit -m "local unpushed" --quiet)
out23=$(cd "$WORK_23" && ./.aitask-scripts/aitask_verified_update.sh \
    --agent-string claudecode/opus4_6 --skill pick --score 4 --silent 2>/dev/null)
rc23=$?
assert_eq "pre-converge keeps the result a full success" "UPDATED:claudecode/opus4_6:pick:80" "$out23"
assert_eq "pre-converge keeps exit 0" "0" "$rc23"
assert_eq "not left ahead" "0" "$(cd "$WORK_23" && git rev-list --count '@{u}..HEAD' 2>/dev/null)"
assert_eq "not left behind" "0" "$(cd "$WORK_23" && git rev-list --count 'HEAD..@{u}' 2>/dev/null)"
rm -rf "$TMPDIR_23"

echo "--- Test 24: partial result — dirty metadata file yields UPDATED_REMOTE_ONLY / exit 3 ---"
TMPDIR_24="$(setup_remote_repo)"
WORK_24="$TMPDIR_24/work"
# Dirty the very file the update touches: the fast-forward then fails closed,
# so the commit is on origin but cannot reach the local branch.
printf '\n' >> "$WORK_24/aitasks/metadata/models_claudecode.json"
set +e
out24=$(cd "$WORK_24" && ./.aitask-scripts/aitask_verified_update.sh \
    --agent-string claudecode/opus4_6 --skill pick --score 4 --silent 2>/dev/null)
rc24=$?
set -e
# The exit status is captured SEPARATELY and asserted to be exactly 3 — not
# merely non-zero, and not inferred from the stdout token: the whole point is
# that the verdict crossed the function boundary into main().
assert_eq "partial result exit status is exactly 3" "3" "$rc24"
assert_eq "partial result token" "UPDATED_REMOTE_ONLY:claudecode/opus4_6:pick:80" "$out24"
assert_eq "the value is still correct on origin" "80" \
    "$(cd "$TMPDIR_24" && git --git-dir=origin.git show main:aitasks/metadata/models_claudecode.json | jq -r '.models[0].verified.pick')"
# The warning must be on stderr only — stdout stays a clean machine channel.
assert_not_contains "no warning text on stdout" "local data branch" "$out24"
rm -rf "$TMPDIR_24"

echo "--- Test 25: positive control — the same run with a clean file is UPDATED / 0 ---"
# Paired with Test 24: the dirty overlap is the ONLY discriminator between them.
TMPDIR_25="$(setup_remote_repo)"
WORK_25="$TMPDIR_25/work"
set +e
out25=$(cd "$WORK_25" && ./.aitask-scripts/aitask_verified_update.sh \
    --agent-string claudecode/opus4_6 --skill pick --score 4 --silent 2>/dev/null)
rc25=$?
set -e
assert_eq "control: clean file exits 0" "0" "$rc25"
assert_eq "control: clean file reports UPDATED" "UPDATED:claudecode/opus4_6:pick:80" "$out25"
rm -rf "$TMPDIR_25"

echo "--- Test 26: the out-param boundary itself ---"
TMPDIR_26="$(setup_remote_repo)"
WORK_26="$TMPDIR_26/work"
boundary_out="$(cd "$WORK_26" && bash -c '
set -uo pipefail
SCRIPT_DIR="$PWD/.aitask-scripts"
SILENT=true
source .aitask-scripts/lib/terminal_compat.sh
source .aitask-scripts/lib/task_utils.sh
source .aitask-scripts/lib/verified_update_lib.sh
update_model_file() {
    jq -r --arg m "$2" ".models[] | select(.name==\$m) | .verified[\"$3\"]" "$1"
}
ensure_model_exists() { :; }
_AIT_UPDATE_MODEL_FILE_FN=update_model_file
_AIT_COMMIT_PREFIX="ait: Update verified score"

# DIRECT call — not inside $( ). This is the shape production uses.
AIT_METADATA_LOCAL_CONVERGED="PRECALL"
commit_metadata_update aitasks/metadata/models_claudecode.json \
    claudecode/opus4_6 pick opus4_6 4 >/dev/null 2>&1
echo "direct_value=${AIT_METADATA_VALUE:-UNSET}"
echo "direct_converged=${AIT_METADATA_LOCAL_CONVERGED:-UNSET}"

# NEGATIVE CONTROL — the identical call wrapped in $( ). A subshell discards
# the assignment, so a future refactor back to a substitution fails HERE
# instead of silently reporting every partial update as a success.
AIT_METADATA_LOCAL_CONVERGED="PRECALL"
_discard="$(commit_metadata_update aitasks/metadata/models_claudecode.json \
    claudecode/opus4_6 pick opus4_6 5 2>/dev/null)"
echo "subshell_converged=${AIT_METADATA_LOCAL_CONVERGED:-UNSET}"
')"
assert_contains "direct call sets AIT_METADATA_VALUE in the caller scope" "direct_value=80" "$boundary_out"
assert_contains "direct call sets AIT_METADATA_LOCAL_CONVERGED in the caller scope" \
    "direct_converged=1" "$boundary_out"
assert_contains "control: a \$( ) wrapper leaves the verdict at its pre-call value" \
    "subshell_converged=PRECALL" "$boundary_out"
rm -rf "$TMPDIR_26"

echo "--- Test 27: non-silent value integrity (no git summary spliced in) ---"
# git commit writes its summary to STDOUT, and run_git_quiet leaves it
# unredirected when SILENT=false. Under the old substitution that text became
# the value.
TMPDIR_27="$(setup_remote_repo)"
WORK_27="$TMPDIR_27/work"
out27=$(cd "$WORK_27" && ./.aitask-scripts/aitask_verified_update.sh \
    --agent-string claudecode/opus4_6 --skill pick --score 4 2>/dev/null | grep '^UPDATED:')
value27="${out27##*:}"
assert_contains_re "non-silent value field is a bare integer" '^[0-9]+$' "$value27"
rm -rf "$TMPDIR_27"

echo "--- Test 28: the local (no-remote) path reports the correct count ---"
# main() bypasses commit_metadata_update entirely without a remote, so every
# assertion above leaves this route uncovered — and it is exactly the route the
# out-param contract can corrupt. The COUNT is the discriminator: a helper that
# clobbers AIT_METADATA_VALUE still prints UPDATED:, just with an empty value.
TMPDIR_28="$(setup_repo)"
set +e
out28=$(cd "$TMPDIR_28" && ./.aitask-scripts/aitask_verified_update.sh \
    --agent-string claudecode/opus4_6 --skill pick --score 4 --silent 2>/dev/null)
rc28=$?
set -e
assert_eq "no-remote path exits 0" "0" "$rc28"
assert_eq "no-remote path carries the correct value" "UPDATED:claudecode/opus4_6:pick:80" "$out28"
rm -rf "$TMPDIR_28"

echo "--- Test 29: commit_metadata_update_local preserves the value on BOTH returns ---"
# The early `diff --cached --quiet` return is unreachable from main() —
# update_model_file always stages a change first — so the contract "sets the
# verdict, never touches the value" is pinned here, at helper level.
TMPDIR_29="$(setup_repo)"
helper_out="$(cd "$TMPDIR_29" && bash -c '
set -uo pipefail
SCRIPT_DIR="$PWD/.aitask-scripts"
SILENT=true
source .aitask-scripts/lib/terminal_compat.sh
source .aitask-scripts/lib/task_utils.sh
source .aitask-scripts/lib/verified_update_lib.sh
_AIT_COMMIT_PREFIX="ait: Update verified score"
f=aitasks/metadata/models_claudecode.json

# (a) clean index -> the EARLY return
AIT_METADATA_VALUE="SENTINEL_A"
AIT_METADATA_LOCAL_CONVERGED="PRECALL"
commit_metadata_update_local "$f" claudecode/opus4_6 pick >/dev/null 2>&1
echo "early_value=${AIT_METADATA_VALUE:-UNSET}"
echo "early_converged=${AIT_METADATA_LOCAL_CONVERGED:-UNSET}"

# (b) a real staged change -> the COMMITTING return
printf "\n" >> "$f"
AIT_METADATA_VALUE="SENTINEL_B"
AIT_METADATA_LOCAL_CONVERGED="PRECALL"
commit_metadata_update_local "$f" claudecode/opus4_6 pick >/dev/null 2>&1
echo "commit_value=${AIT_METADATA_VALUE:-UNSET}"
echo "commit_converged=${AIT_METADATA_LOCAL_CONVERGED:-UNSET}"
')"
assert_contains "early return preserves the caller's value" "early_value=SENTINEL_A" "$helper_out"
assert_contains "early return still sets the verdict" "early_converged=1" "$helper_out"
assert_contains "committing return preserves the caller's value" "commit_value=SENTINEL_B" "$helper_out"
assert_contains "committing return sets the verdict" "commit_converged=1" "$helper_out"
rm -rf "$TMPDIR_29"

echo "--- Test 30: [post-phase branch_mode_metadata_fixture] the seam in branch mode ---"
# Every assertion above runs in LEGACY mode, where _ait_data_git is plain `git`
# in the cwd — so a mode-specific defect in the converge seam would be
# invisible. This runs the same invariant and outcome assertions through a real
# .aitask-data worktree with aitasks/ and aiplans/ symlinks, the shape
# production actually uses.
TMPDIR_30="$(setup_branch_mode_metadata_repo aitask_verified_update.sh)"
WORK_30="$TMPDIR_30/work"
DATA_30="$WORK_30/.aitask-data"

set +e
out30=$(cd "$WORK_30" && ./.aitask-scripts/aitask_verified_update.sh \
    --agent-string claudecode/opus4_6 --skill pick --score 4 --silent 2>/dev/null)
rc30=$?
set -e
assert_eq "branch mode: reports UPDATED" "UPDATED:claudecode/opus4_6:pick:80" "$out30"
assert_eq "branch mode: exits 0" "0" "$rc30"
assert_eq "branch mode: nothing left unpulled on the DATA branch" "0" \
    "$(git -C "$DATA_30" rev-list --count 'HEAD..@{u}' 2>/dev/null)"
origin_sha_30="$(git -C "$DATA_30" rev-parse '@{u}')"
git -C "$DATA_30" merge-base --is-ancestor "$origin_sha_30" HEAD 2>/dev/null
assert_eq "branch mode: the pushed commit is an ancestor of the local data HEAD" "0" "$?"
# DISCRIMINATING assertions. `verified.pick` stays 80 either way (the seed
# value equals the average of one score-4 run), and the ancestry check passes
# trivially on an untouched branch — so if the fixture silently degraded to
# legacy mode both would pass vacuously. These two cannot:
#   - the data branch must have GAINED a commit;
#   - verifiedstats is absent from the seed, so runs==1 proves the write landed
#     on the data branch and not on the code checkout.
assert_eq "branch mode: the data branch gained the metadata commit" "2" \
    "$(git -C "$DATA_30" rev-list --count HEAD)"
assert_eq "branch mode: the update wrote verifiedstats on the DATA branch" "1" \
    "$(jq -r '.models[0].verifiedstats.pick.all_time.runs' "$DATA_30/aitasks/metadata/models_claudecode.json")"
assert_eq "branch mode: the code checkout has no aitasks/ of its own" "1" \
    "$([ -L "$WORK_30/aitasks" ] && echo 1 || echo 0)"

# And the partial outcome, in branch mode too.
printf '\n' >> "$DATA_30/aitasks/metadata/models_claudecode.json"
set +e
out30b=$(cd "$WORK_30" && ./.aitask-scripts/aitask_verified_update.sh \
    --agent-string claudecode/opus4_6 --skill pick --score 4 --silent 2>/dev/null)
rc30b=$?
set -e
assert_eq "branch mode: partial result exits 3" "3" "$rc30b"
assert_contains "branch mode: partial result token" "UPDATED_REMOTE_ONLY:" "$out30b"
rm -rf "$TMPDIR_30"

echo "--- Test 31: [post-phase converge_race_stress] a competing pusher never strands silently ---"
# Drives the update against a competing writer injected through the DOCUMENTED
# AITASK_VERIFIED_UPDATE_BEFORE_PUSH_HOOK seam — deterministic, no sleeping.
# Every run must end EITHER UPDATED:/0 with the local-ref invariant holding,
# OR UPDATED_REMOTE_ONLY:/3. Never a silent strand, and never UPDATED: while
# the commit is missing locally.
TMPDIR_31="$(setup_remote_metadata_repo aitask_verified_update.sh)"
WORK_31="$TMPDIR_31/work"
ORIGIN_31="$TMPDIR_31/origin.git"

cat > "$TMPDIR_31/race_hook.sh" <<'HOOKEOF'
#!/usr/bin/env bash
set -euo pipefail
# Land a competing commit on origin on the first attempt only.
[[ "${AITASK_VERIFIED_UPDATE_ATTEMPT:-}" != "1" ]] && exit 0
[[ -f "${AITASK_VERIFIED_UPDATE_HOOK_FLAG:-}" ]] && exit 0
touch "$AITASK_VERIFIED_UPDATE_HOOK_FLAG"
tmp="$(mktemp -d)"
git clone --quiet "$AITASK_VERIFIED_UPDATE_TEST_ORIGIN" "$tmp/repo" >/dev/null 2>&1
(
    cd "$tmp/repo"
    git config user.email "racer@test.com"
    git config user.name "Racer"
    echo "competing" > competing.txt
    git add competing.txt
    git commit -m "competing writer" --quiet
    git push --quiet origin HEAD:main
)
rm -rf "$tmp"
HOOKEOF
chmod +x "$TMPDIR_31/race_hook.sh"

for round in 1 2; do
    flag_31="$TMPDIR_31/hook_fired_$round"
    set +e
    out31=$(cd "$WORK_31" && \
        AITASK_VERIFIED_UPDATE_BEFORE_PUSH_HOOK="$TMPDIR_31/race_hook.sh" \
        AITASK_VERIFIED_UPDATE_HOOK_FLAG="$flag_31" \
        AITASK_VERIFIED_UPDATE_TEST_ORIGIN="$ORIGIN_31" \
        ./.aitask-scripts/aitask_verified_update.sh \
        --agent-string claudecode/opus4_6 --skill pick --score 4 --silent 2>/dev/null)
    rc31=$?
    set -e

    behind_31="$(cd "$WORK_31" && git rev-list --count 'HEAD..@{u}' 2>/dev/null)"
    case "$out31" in
        UPDATED:*)
            assert_eq "race round $round: UPDATED implies exit 0" "0" "$rc31"
            # The load-bearing half: UPDATED may NEVER be reported while the
            # commit is missing from the local branch.
            assert_eq "race round $round: UPDATED implies the invariant holds" "0" "$behind_31" ;;
        UPDATED_REMOTE_ONLY:*)
            assert_eq "race round $round: partial implies exit 3" "3" "$rc31" ;;
        *)
            assert_eq "race round $round: outcome is one of the two contract tokens" \
                "UPDATED|UPDATED_REMOTE_ONLY" "$out31" ;;
    esac
    assert_contains "race round $round: the value field is present" ":pick:" "$out31"
done
rm -rf "$TMPDIR_31"

echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
