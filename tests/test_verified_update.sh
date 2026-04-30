#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected '$expected', got '$actual')"
    fi
}

assert_contains() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if printf '%s' "$actual" | grep -Fq "$expected"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected output containing '$expected', got '$actual')"
    fi
}

assert_exit_zero() {
    local desc="$1"
    shift
    TOTAL=$((TOTAL + 1))
    if "$@" >/dev/null 2>&1; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (command exited non-zero)"
    fi
}

assert_exit_nonzero() {
    local desc="$1"
    shift
    TOTAL=$((TOTAL + 1))
    if "$@" >/dev/null 2>&1; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected non-zero exit, got 0)"
    else
        PASS=$((PASS + 1))
    fi
}

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

    mkdir -p "$repo_dir/.aitask-scripts/lib" "$repo_dir/aitasks/metadata"

    cp "$PROJECT_DIR/.aitask-scripts/aitask_verified_update.sh" "$repo_dir/.aitask-scripts/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" "$repo_dir/.aitask-scripts/lib/"
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

echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
