#!/usr/bin/env bash
# test_add_model.sh - Unit tests for aitask_add_model.sh
# Run: bash tests/test_add_model.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HELPER="$PROJECT_DIR/.aitask-scripts/aitask_add_model.sh"

PASS=0
FAIL=0
TOTAL=0

assert_eq() {
    local label="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$actual" == "$expected" ]]; then
        echo "  PASS: $label"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $label"
        echo "    expected: $expected"
        echo "    actual:   $actual"
        FAIL=$((FAIL + 1))
    fi
}

assert_contains() {
    local label="$1" needle="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$haystack" == *"$needle"* ]]; then
        echo "  PASS: $label"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $label"
        echo "    expected to contain: $needle"
        echo "    actual: $haystack"
        FAIL=$((FAIL + 1))
    fi
}

assert_not_contains() {
    local label="$1" needle="$2" haystack="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$haystack" != *"$needle"* ]]; then
        echo "  PASS: $label"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $label"
        echo "    expected NOT to contain: $needle"
        echo "    actual: $haystack"
        FAIL=$((FAIL + 1))
    fi
}

# --- Fixture helpers ---

setup_fixture() {
    # Creates a temp repo layout and exports AITASK_REPO_ROOT.
    FIXTURE_DIR=$(mktemp -d "${TMPDIR:-/tmp}/test_add_model_XXXXXX")
    export AITASK_REPO_ROOT="$FIXTURE_DIR"
    mkdir -p "$FIXTURE_DIR/aitasks/metadata" "$FIXTURE_DIR/seed" "$FIXTURE_DIR/.aitask-scripts"

    # Minimal models_claudecode.json with one existing entry carrying verified scores
    cat > "$FIXTURE_DIR/aitasks/metadata/models_claudecode.json" <<'EOF'
{
  "models": [
    {
      "name": "opus4_6",
      "cli_id": "claude-opus-4-6",
      "notes": "existing",
      "verified": { "pick": 98 },
      "verifiedstats": { "pick": { "all_time": { "runs": 10, "score_sum": 980 } } }
    }
  ]
}
EOF
    cat > "$FIXTURE_DIR/seed/models_claudecode.json" <<'EOF'
{
  "models": [
    {
      "name": "opus4_6",
      "cli_id": "claude-opus-4-6",
      "notes": "existing",
      "verified": {},
      "verifiedstats": {}
    }
  ]
}
EOF

    cat > "$FIXTURE_DIR/aitasks/metadata/codeagent_config.json" <<'EOF'
{
  "defaults": {
    "pick": "claudecode/opus4_6",
    "explain": "claudecode/sonnet4_6",
    "explore": "claudecode/opus4_6",
    "brainstorm-explorer": "claudecode/opus4_6",
    "brainstorm-synthesizer": "claudecode/opus4_6"
  }
}
EOF
    cat > "$FIXTURE_DIR/seed/codeagent_config.json" <<'EOF'
{
  "defaults": {
    "pick": "claudecode/opus4_6",
    "explain": "claudecode/sonnet4_6",
    "explore": "claudecode/opus4_6"
  }
}
EOF

    # Stub aitask_codeagent.sh with the two anchor lines the helper patches.
    # Keep the anchors byte-exact with the real file.
    cat > "$FIXTURE_DIR/.aitask-scripts/aitask_codeagent.sh" <<'EOF'
#!/usr/bin/env bash
# stub for tests

METADATA_DIR="aitasks/metadata"
DEFAULT_AGENT_STRING="claudecode/opus4_6"
DEFAULT_COAUTHOR_DOMAIN="aitasks.io"

# ...help text...
# Resolution chain (highest priority first):
#   1. --agent-string flag
#   2. aitasks/metadata/codeagent_config.local.json (per-user, gitignored)
#   3. aitasks/metadata/codeagent_config.json (per-project, git-tracked)
  4. Hardcoded default: claudecode/opus4_6
EOF
    chmod +x "$FIXTURE_DIR/.aitask-scripts/aitask_codeagent.sh"
}

teardown_fixture() {
    [[ -n "${FIXTURE_DIR:-}" && -d "$FIXTURE_DIR" ]] && rm -rf "$FIXTURE_DIR"
    unset AITASK_REPO_ROOT FIXTURE_DIR
}

# --- Tests ---

echo "=== Test 1: add-json appends entry and preserves existing verified/verifiedstats ==="
setup_fixture
bash "$HELPER" add-json --agent claudecode --name opus4_7 --cli-id claude-opus-4-7 --notes "new flagship" >/dev/null
count=$(jq '.models | length' "$FIXTURE_DIR/aitasks/metadata/models_claudecode.json")
assert_eq "metadata has 2 models" "2" "$count"
new_name=$(jq -r '.models[1].name' "$FIXTURE_DIR/aitasks/metadata/models_claudecode.json")
assert_eq "new model is opus4_7" "opus4_7" "$new_name"
preserved_score=$(jq -r '.models[0].verified.pick' "$FIXTURE_DIR/aitasks/metadata/models_claudecode.json")
assert_eq "existing verified.pick preserved" "98" "$preserved_score"
preserved_runs=$(jq -r '.models[0].verifiedstats.pick.all_time.runs' "$FIXTURE_DIR/aitasks/metadata/models_claudecode.json")
assert_eq "existing verifiedstats preserved" "10" "$preserved_runs"
seed_count=$(jq '.models | length' "$FIXTURE_DIR/seed/models_claudecode.json")
assert_eq "seed also synced (2 models)" "2" "$seed_count"
teardown_fixture

echo "=== Test 2: add-json second run errors clearly (idempotent-with-error) ==="
setup_fixture
bash "$HELPER" add-json --agent claudecode --name opus4_7 --cli-id claude-opus-4-7 --notes "n" >/dev/null
result=$(bash "$HELPER" add-json --agent claudecode --name opus4_7 --cli-id claude-opus-4-7 --notes "n" 2>&1 || true)
assert_contains "second run errors with 'already exists'" "already exists" "$result"
teardown_fixture

echo "=== Test 3: promote-config updates only listed ops, including brainstorm-* ==="
setup_fixture
bash "$HELPER" promote-config --agent claudecode --name opus4_7 \
    --ops pick,brainstorm-explorer >/dev/null
pick_val=$(jq -r '.defaults.pick' "$FIXTURE_DIR/aitasks/metadata/codeagent_config.json")
explain_val=$(jq -r '.defaults.explain' "$FIXTURE_DIR/aitasks/metadata/codeagent_config.json")
explore_val=$(jq -r '.defaults.explore' "$FIXTURE_DIR/aitasks/metadata/codeagent_config.json")
brainstorm_ex=$(jq -r '.defaults["brainstorm-explorer"]' "$FIXTURE_DIR/aitasks/metadata/codeagent_config.json")
brainstorm_syn=$(jq -r '.defaults["brainstorm-synthesizer"]' "$FIXTURE_DIR/aitasks/metadata/codeagent_config.json")
assert_eq "pick updated" "claudecode/opus4_7" "$pick_val"
assert_eq "brainstorm-explorer updated" "claudecode/opus4_7" "$brainstorm_ex"
assert_eq "brainstorm-synthesizer untouched" "claudecode/opus4_6" "$brainstorm_syn"
assert_eq "explain untouched" "claudecode/sonnet4_6" "$explain_val"
assert_eq "explore untouched" "claudecode/opus4_6" "$explore_val"
# Seed: pick exists (should update), brainstorm-explorer does NOT (should skip silently)
seed_pick=$(jq -r '.defaults.pick' "$FIXTURE_DIR/seed/codeagent_config.json")
seed_has_brainstorm=$(jq 'has("defaults") and (.defaults | has("brainstorm-explorer"))' "$FIXTURE_DIR/seed/codeagent_config.json")
assert_eq "seed pick updated" "claudecode/opus4_7" "$seed_pick"
assert_eq "seed does not gain brainstorm-explorer" "false" "$seed_has_brainstorm"
teardown_fixture

echo "=== Test 4: promote-default-agent-string rejects non-claudecode + updates lines 21 & 663 ==="
setup_fixture
# Rejection path
result=$(bash "$HELPER" promote-default-agent-string --agent geminicli --name gemini3pro 2>&1 || true)
assert_contains "rejects non-claudecode" "only supports agent 'claudecode'" "$result"
# Apply path
bash "$HELPER" promote-default-agent-string --agent claudecode --name opus4_7 >/dev/null
src="$FIXTURE_DIR/.aitask-scripts/aitask_codeagent.sh"
line21=$(grep '^DEFAULT_AGENT_STRING=' "$src")
assert_eq "DEFAULT_AGENT_STRING updated" 'DEFAULT_AGENT_STRING="claudecode/opus4_7"' "$line21"
resolution_line=$(grep '^  4\. Hardcoded default:' "$src")
assert_eq "resolution-chain note updated" "  4. Hardcoded default: claudecode/opus4_7" "$resolution_line"
# Executable bit preserved
if [[ -x "$src" ]]; then
    echo "  PASS: executable bit preserved"
    PASS=$((PASS + 1))
else
    echo "  FAIL: executable bit NOT preserved"
    FAIL=$((FAIL + 1))
fi
TOTAL=$((TOTAL + 1))
teardown_fixture

echo "=== Test 5: --dry-run emits diffs AND leaves filesystem unchanged across all subcommands ==="
setup_fixture
checksum_before=$(find "$FIXTURE_DIR" -type f -print0 | sort -z | xargs -0 cat | md5sum | awk '{print $1}')

dry1=$(bash "$HELPER" add-json --dry-run --agent claudecode --name opus4_7 \
    --cli-id claude-opus-4-7 --notes "n" 2>&1)
assert_contains "add-json dry-run emits diff (metadata)" "+++ b/aitasks/metadata/models_claudecode.json" "$dry1"
assert_contains "add-json dry-run emits diff (seed)" "+++ b/seed/models_claudecode.json" "$dry1"
assert_contains "add-json dry-run mentions new name" "opus4_7" "$dry1"

dry2=$(bash "$HELPER" promote-config --dry-run --agent claudecode --name opus4_7 \
    --ops pick,brainstorm-explorer 2>&1)
assert_contains "promote-config dry-run emits diff" "+++ b/aitasks/metadata/codeagent_config.json" "$dry2"

dry3=$(bash "$HELPER" promote-default-agent-string --dry-run --agent claudecode \
    --name opus4_7 2>&1)
assert_contains "promote-default dry-run emits diff" "+++ b/.aitask-scripts/aitask_codeagent.sh" "$dry3"

checksum_after=$(find "$FIXTURE_DIR" -type f -print0 | sort -z | xargs -0 cat | md5sum | awk '{print $1}')
assert_eq "filesystem unchanged after all dry-runs" "$checksum_before" "$checksum_after"

# Produced JSON always validates (cover both real writes and dry-run internals)
bash "$HELPER" add-json --agent claudecode --name opus4_7 --cli-id claude-opus-4-7 --notes "n" >/dev/null
if jq . "$FIXTURE_DIR/aitasks/metadata/models_claudecode.json" >/dev/null 2>&1; then
    echo "  PASS: metadata JSON validates after apply"
    PASS=$((PASS + 1))
else
    echo "  FAIL: metadata JSON invalid after apply"
    FAIL=$((FAIL + 1))
fi
TOTAL=$((TOTAL + 1))
if jq . "$FIXTURE_DIR/seed/models_claudecode.json" >/dev/null 2>&1; then
    echo "  PASS: seed JSON validates after apply"
    PASS=$((PASS + 1))
else
    echo "  FAIL: seed JSON invalid after apply"
    FAIL=$((FAIL + 1))
fi
TOTAL=$((TOTAL + 1))
teardown_fixture

echo "=== Test 6: invalid inputs fail with clear errors ==="
setup_fixture
r1=$(bash "$HELPER" add-json --agent unknownagent --name x --cli-id y --notes z 2>&1 || true)
assert_contains "unknown agent rejected" "Unknown agent" "$r1"

r2=$(bash "$HELPER" add-json --agent claudecode --name BadName --cli-id y --notes z 2>&1 || true)
assert_contains "uppercase name rejected" "Invalid model name" "$r2"

r3=$(bash "$HELPER" add-json --agent claudecode --name has_space --cli-id "" --notes z 2>&1 || true)
assert_contains "empty cli-id rejected" "--cli-id is required" "$r3"

r4=$(bash "$HELPER" add-json --agent opencode --name x --cli-id y --notes z 2>&1 || true)
assert_contains "opencode rejected with pointer" "aitask-refresh-code-models" "$r4"

r5=$(bash "$HELPER" add-json --agent claudecode --name "has space" --cli-id y --notes z 2>&1 || true)
assert_contains "name with space rejected" "Invalid model name" "$r5"
teardown_fixture

# --- Summary ---
echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
