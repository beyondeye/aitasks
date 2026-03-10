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

        mkdir -p .aitask-scripts/lib aitasks/metadata

        cp "$PROJECT_DIR/.aitask-scripts/aitask_verified_update.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
        chmod +x .aitask-scripts/aitask_verified_update.sh

        cat > ait <<'EOF'
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
        chmod +x ait

        cat > aitasks/metadata/models_claudecode.json <<'EOF'
{
  "models": [
    {
      "name": "opus4_6",
      "cli_id": "claude-opus-4-6",
      "notes": "Test model",
      "verified": {
        "task-pick": 80,
        "explain": 60,
        "batch-review": 0
      }
    }
  ]
}
EOF

        git add .
        git commit -m "Initial setup" --quiet
    )

    echo "$tmpdir"
}

json_get() {
    local repo_dir="$1" jq_filter="$2"
    jq -r "$jq_filter" "$repo_dir/aitasks/metadata/models_claudecode.json"
}

set +e

echo "=== aitask_verified_update.sh Tests ==="
echo ""

echo "--- Test 1: Valid update creates stats ---"
TMPDIR_1="$(setup_repo)"
output1=$(cd "$TMPDIR_1" && ./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill pick --score 4 2>&1)
assert_contains "Structured success output" "UPDATED:claudecode/opus4_6:pick:80" "$output1"
assert_eq "Runs initialized to 1" "1" "$(json_get "$TMPDIR_1" '.models[0].verifiedstats.pick.runs')"
assert_eq "Score sum initialized to 80" "80" "$(json_get "$TMPDIR_1" '.models[0].verifiedstats.pick.score_sum')"
assert_eq "Verified pick initialized to 80" "80" "$(json_get "$TMPDIR_1" '.models[0].verified.pick')"
assert_eq "Existing verified key preserved (task-pick)" "80" "$(json_get "$TMPDIR_1" '.models[0].verified["task-pick"]')"
assert_eq "Existing verified key preserved (explain)" "60" "$(json_get "$TMPDIR_1" '.models[0].verified.explain')"
rm -rf "$TMPDIR_1"

echo "--- Test 2: Rolling average updates correctly ---"
TMPDIR_2="$(setup_repo)"
(cd "$TMPDIR_2" && ./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill pick --score 4 >/dev/null 2>&1)
output2=$(cd "$TMPDIR_2" && ./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill pick --score 5 2>&1)
assert_contains "Structured rolling average output" "UPDATED:claudecode/opus4_6:pick:90" "$output2"
assert_eq "Runs incremented to 2" "2" "$(json_get "$TMPDIR_2" '.models[0].verifiedstats.pick.runs')"
assert_eq "Score sum incremented to 180" "180" "$(json_get "$TMPDIR_2" '.models[0].verifiedstats.pick.score_sum')"
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

echo "--- Test 7: Missing verifiedstats is created automatically ---"
TMPDIR_7="$(setup_repo)"
(cd "$TMPDIR_7" && ./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill explain --score 3 >/dev/null 2>&1)
assert_eq "Explain runs created" "1" "$(json_get "$TMPDIR_7" '.models[0].verifiedstats.explain.runs')"
assert_eq "Explain score sum created" "60" "$(json_get "$TMPDIR_7" '.models[0].verifiedstats.explain.score_sum')"
assert_eq "Explain verified updated" "60" "$(json_get "$TMPDIR_7" '.models[0].verified.explain')"
rm -rf "$TMPDIR_7"

echo "--- Test 8: Silent mode prints only structured result ---"
TMPDIR_8="$(setup_repo)"
output8=$(cd "$TMPDIR_8" && ./.aitask-scripts/aitask_verified_update.sh --agent-string claudecode/opus4_6 --skill pick --score 4 --silent 2>&1)
assert_eq "Silent output is structured only" "UPDATED:claudecode/opus4_6:pick:80" "$output8"
rm -rf "$TMPDIR_8"

echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
