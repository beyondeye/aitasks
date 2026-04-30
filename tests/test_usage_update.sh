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

    cp "$PROJECT_DIR/.aitask-scripts/aitask_usage_update.sh" "$repo_dir/.aitask-scripts/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" "$repo_dir/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" "$repo_dir/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" "$repo_dir/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/verified_update_lib.sh" "$repo_dir/.aitask-scripts/lib/"
    chmod +x "$repo_dir/.aitask-scripts/aitask_usage_update.sh"

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
        "explain": 60
      },
      "verifiedstats": {
        "pick": {
          "all_time":   {"runs": 4, "score_sum": 320},
          "prev_month": {"period": "2026-02", "runs": 1, "score_sum": 80},
          "month":      {"period": "2026-03", "runs": 3, "score_sum": 240},
          "week":       {"period": "2026-W11", "runs": 1, "score_sum": 80}
        }
      }
    }
  ]
}
EOF
}

json_get() {
    local repo_dir="$1" jq_filter="$2"
    jq -r "$jq_filter" "$repo_dir/aitasks/metadata/models_claudecode.json"
}

json_raw() {
    local repo_dir="$1" jq_filter="$2"
    jq -c "$jq_filter" "$repo_dir/aitasks/metadata/models_claudecode.json"
}

set +e

echo "=== aitask_usage_update.sh Tests ==="
echo ""

echo "--- Test 1: Fresh model (no usagestats key) — full block created ---"
TMPDIR_1="$(setup_repo)"
output1=$(cd "$TMPDIR_1" && ./.aitask-scripts/aitask_usage_update.sh --agent-string claudecode/opus4_6 --skill pick --date 2026-03-11 2>&1)
assert_contains "Structured success output" "UPDATED:claudecode/opus4_6:pick:1" "$output1"
assert_eq "all_time runs initialized to 1" "1" "$(json_get "$TMPDIR_1" '.models[0].usagestats.pick.all_time.runs')"
assert_eq "all_time has no score_sum" "null" "$(json_get "$TMPDIR_1" '.models[0].usagestats.pick.all_time.score_sum')"
assert_eq "month period set" "2026-03" "$(json_get "$TMPDIR_1" '.models[0].usagestats.pick.month.period')"
assert_eq "month runs = 1" "1" "$(json_get "$TMPDIR_1" '.models[0].usagestats.pick.month.runs')"
assert_eq "week period set" "2026-W11" "$(json_get "$TMPDIR_1" '.models[0].usagestats.pick.week.period')"
assert_eq "week runs = 1" "1" "$(json_get "$TMPDIR_1" '.models[0].usagestats.pick.week.runs')"
assert_eq "prev_month period empty" "" "$(json_get "$TMPDIR_1" '.models[0].usagestats.pick.prev_month.period')"
assert_eq "prev_month runs = 0" "0" "$(json_get "$TMPDIR_1" '.models[0].usagestats.pick.prev_month.runs')"
rm -rf "$TMPDIR_1"

echo "--- Test 2: Same-month bump — month increments, prev_month untouched ---"
TMPDIR_2="$(setup_repo)"
tmp_json_2="$(mktemp)"
jq '.models[0].usagestats.pick = {
        "all_time":   {"runs": 7},
        "prev_month": {"period": "2026-03", "runs": 5},
        "month":      {"period": "2026-04", "runs": 2},
        "week":       {"period": "2026-W17", "runs": 1}
    }' \
    "$TMPDIR_2/aitasks/metadata/models_claudecode.json" > "$tmp_json_2"
mv "$tmp_json_2" "$TMPDIR_2/aitasks/metadata/models_claudecode.json"
(cd "$TMPDIR_2" && git add -A && git commit -m "seed usage" --quiet)
output2=$(cd "$TMPDIR_2" && ./.aitask-scripts/aitask_usage_update.sh --agent-string claudecode/opus4_6 --skill pick --date 2026-04-29 --silent 2>&1)
assert_eq "Same-month: structured output runs=3" "UPDATED:claudecode/opus4_6:pick:3" "$output2"
assert_eq "Same-month: month runs = 3" "3" "$(json_get "$TMPDIR_2" '.models[0].usagestats.pick.month.runs')"
assert_eq "Same-month: month period unchanged" "2026-04" "$(json_get "$TMPDIR_2" '.models[0].usagestats.pick.month.period')"
assert_eq "Same-month: all_time runs = 8" "8" "$(json_get "$TMPDIR_2" '.models[0].usagestats.pick.all_time.runs')"
assert_eq "Same-month: prev_month period preserved" "2026-03" "$(json_get "$TMPDIR_2" '.models[0].usagestats.pick.prev_month.period')"
assert_eq "Same-month: prev_month runs preserved" "5" "$(json_get "$TMPDIR_2" '.models[0].usagestats.pick.prev_month.runs')"
rm -rf "$TMPDIR_2"

echo "--- Test 3: One-month rollover — prev_month gets old month, month resets ---"
TMPDIR_3="$(setup_repo)"
tmp_json_3="$(mktemp)"
jq '.models[0].usagestats.pick = {
        "all_time":   {"runs": 5},
        "prev_month": {"period": "", "runs": 0},
        "month":      {"period": "2026-04", "runs": 5},
        "week":       {"period": "2026-W17", "runs": 1}
    }' \
    "$TMPDIR_3/aitasks/metadata/models_claudecode.json" > "$tmp_json_3"
mv "$tmp_json_3" "$TMPDIR_3/aitasks/metadata/models_claudecode.json"
(cd "$TMPDIR_3" && git add -A && git commit -m "seed pre-rollover" --quiet)
(cd "$TMPDIR_3" && ./.aitask-scripts/aitask_usage_update.sh --agent-string claudecode/opus4_6 --skill pick --date 2026-05-01 --silent >/dev/null 2>&1)
assert_eq "One-month rollover: prev_month period = old month" "2026-04" "$(json_get "$TMPDIR_3" '.models[0].usagestats.pick.prev_month.period')"
assert_eq "One-month rollover: prev_month runs = old month runs" "5" "$(json_get "$TMPDIR_3" '.models[0].usagestats.pick.prev_month.runs')"
assert_eq "One-month rollover: month period = 2026-05" "2026-05" "$(json_get "$TMPDIR_3" '.models[0].usagestats.pick.month.period')"
assert_eq "One-month rollover: month runs reset to 1" "1" "$(json_get "$TMPDIR_3" '.models[0].usagestats.pick.month.runs')"
assert_eq "One-month rollover: all_time runs = 6" "6" "$(json_get "$TMPDIR_3" '.models[0].usagestats.pick.all_time.runs')"
rm -rf "$TMPDIR_3"

echo "--- Test 4: Multi-month skip — prev_month zeroed, month resets ---"
TMPDIR_4="$(setup_repo)"
tmp_json_4="$(mktemp)"
jq '.models[0].usagestats.pick = {
        "all_time":   {"runs": 4},
        "prev_month": {"period": "2026-01", "runs": 1},
        "month":      {"period": "2026-02", "runs": 3},
        "week":       {"period": "2026-W08", "runs": 1}
    }' \
    "$TMPDIR_4/aitasks/metadata/models_claudecode.json" > "$tmp_json_4"
mv "$tmp_json_4" "$TMPDIR_4/aitasks/metadata/models_claudecode.json"
(cd "$TMPDIR_4" && git add -A && git commit -m "seed multi-month-skip" --quiet)
(cd "$TMPDIR_4" && ./.aitask-scripts/aitask_usage_update.sh --agent-string claudecode/opus4_6 --skill pick --date 2026-05-01 --silent >/dev/null 2>&1)
assert_eq "Multi-month skip: prev_month period zeroed" "" "$(json_get "$TMPDIR_4" '.models[0].usagestats.pick.prev_month.period')"
assert_eq "Multi-month skip: prev_month runs zeroed" "0" "$(json_get "$TMPDIR_4" '.models[0].usagestats.pick.prev_month.runs')"
assert_eq "Multi-month skip: month period = 2026-05" "2026-05" "$(json_get "$TMPDIR_4" '.models[0].usagestats.pick.month.period')"
assert_eq "Multi-month skip: month runs = 1" "1" "$(json_get "$TMPDIR_4" '.models[0].usagestats.pick.month.runs')"
rm -rf "$TMPDIR_4"

echo "--- Test 5: Two skills accumulate independently ---"
TMPDIR_5="$(setup_repo)"
(cd "$TMPDIR_5" && ./.aitask-scripts/aitask_usage_update.sh --agent-string claudecode/opus4_6 --skill pick --date 2026-03-11 --silent >/dev/null 2>&1)
(cd "$TMPDIR_5" && ./.aitask-scripts/aitask_usage_update.sh --agent-string claudecode/opus4_6 --skill explore --date 2026-03-11 --silent >/dev/null 2>&1)
assert_eq "Pick all_time runs = 1" "1" "$(json_get "$TMPDIR_5" '.models[0].usagestats.pick.all_time.runs')"
assert_eq "Explore all_time runs = 1" "1" "$(json_get "$TMPDIR_5" '.models[0].usagestats.explore.all_time.runs')"
assert_eq "Pick month runs = 1" "1" "$(json_get "$TMPDIR_5" '.models[0].usagestats.pick.month.runs')"
assert_eq "Explore month runs = 1" "1" "$(json_get "$TMPDIR_5" '.models[0].usagestats.explore.month.runs')"
rm -rf "$TMPDIR_5"

echo "--- Test 6: Verified data untouched by usage update ---"
TMPDIR_6="$(setup_repo)"
verified_before="$(json_raw "$TMPDIR_6" '.models[0].verifiedstats')"
verified_flat_before="$(json_raw "$TMPDIR_6" '.models[0].verified')"
(cd "$TMPDIR_6" && ./.aitask-scripts/aitask_usage_update.sh --agent-string claudecode/opus4_6 --skill pick --date 2026-03-11 --silent >/dev/null 2>&1)
verified_after="$(json_raw "$TMPDIR_6" '.models[0].verifiedstats')"
verified_flat_after="$(json_raw "$TMPDIR_6" '.models[0].verified')"
assert_eq "verifiedstats unchanged" "$verified_before" "$verified_after"
assert_eq "verified (flat) unchanged" "$verified_flat_before" "$verified_flat_after"
assert_eq "usagestats was created" "1" "$(json_get "$TMPDIR_6" '.models[0].usagestats.pick.all_time.runs')"
rm -rf "$TMPDIR_6"

echo "--- Test 7: Unknown agent fails ---"
TMPDIR_7="$(setup_repo)"
assert_exit_nonzero "Unknown agent rejected" bash -c "cd '$TMPDIR_7' && ./.aitask-scripts/aitask_usage_update.sh --agent-string fakeagent/whatever --skill pick"
rm -rf "$TMPDIR_7"

echo "--- Test 8: Missing model fails ---"
TMPDIR_8="$(setup_repo)"
assert_exit_nonzero "Missing model rejected" bash -c "cd '$TMPDIR_8' && ./.aitask-scripts/aitask_usage_update.sh --agent-string claudecode/sonnet4_6 --skill pick"
rm -rf "$TMPDIR_8"

echo "--- Test 9: --score flag rejected ---"
TMPDIR_9="$(setup_repo)"
assert_exit_nonzero "--score flag rejected" bash -c "cd '$TMPDIR_9' && ./.aitask-scripts/aitask_usage_update.sh --agent-string claudecode/opus4_6 --skill pick --score 5"
rm -rf "$TMPDIR_9"

echo "--- Test 10: Help exits 0 ---"
TMPDIR_10="$(setup_repo)"
assert_exit_zero "Help exits successfully" bash -c "cd '$TMPDIR_10' && ./.aitask-scripts/aitask_usage_update.sh --help"
rm -rf "$TMPDIR_10"

echo "--- Test 11: Silent mode prints only structured result ---"
TMPDIR_11="$(setup_repo)"
output11=$(cd "$TMPDIR_11" && ./.aitask-scripts/aitask_usage_update.sh --agent-string claudecode/opus4_6 --skill pick --silent 2>&1)
assert_eq "Silent output is structured only" "UPDATED:claudecode/opus4_6:pick:1" "$output11"
rm -rf "$TMPDIR_11"

echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
