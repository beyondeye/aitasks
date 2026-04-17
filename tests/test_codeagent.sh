#!/usr/bin/env bash
# test_codeagent.sh - Tests for aitask_codeagent.sh
# Run: bash tests/test_codeagent.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

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
    if echo "$actual" | grep -qi "$expected"; then
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

# --- Test environment setup ---

setup_test_env() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    # Create minimal project structure
    mkdir -p "$tmpdir/aitasks/metadata"
    mkdir -p "$tmpdir/.aitask-scripts/lib"

    # Copy required scripts
    cp "$PROJECT_DIR/.aitask-scripts/aitask_codeagent.sh" "$tmpdir/.aitask-scripts/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" "$tmpdir/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" "$tmpdir/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" "$tmpdir/.aitask-scripts/lib/"
    chmod +x "$tmpdir/.aitask-scripts/aitask_codeagent.sh"

    # Copy model configs
    cp "$PROJECT_DIR/aitasks/metadata/models_claudecode.json" "$tmpdir/aitasks/metadata/"
    cp "$PROJECT_DIR/aitasks/metadata/models_geminicli.json" "$tmpdir/aitasks/metadata/"
    cp "$PROJECT_DIR/aitasks/metadata/models_codex.json" "$tmpdir/aitasks/metadata/"
    cp "$PROJECT_DIR/aitasks/metadata/models_opencode.json" "$tmpdir/aitasks/metadata/"
    cp "$PROJECT_DIR/seed/codeagent_config.json" "$tmpdir/aitasks/metadata/"
    cp "$PROJECT_DIR/aitasks/metadata/project_config.yaml" "$tmpdir/aitasks/metadata/"

    # Initialize git repo (task_utils.sh needs it)
    (cd "$tmpdir" && git init --quiet && git config user.email "test@test.com" && git config user.name "Test")

    echo "$tmpdir"
}

cleanup_test_env() {
    [[ -n "${1:-}" && -d "$1" ]] && rm -rf "$1"
}

# --- Check prerequisites ---

if ! command -v jq &>/dev/null; then
    echo "SKIP: jq is required for these tests"
    exit 0
fi

# --- Tests ---

echo "=== test_codeagent.sh ==="
echo ""

# Test 1: Syntax check
echo "--- Test 1: Syntax check ---"
assert_exit_zero "bash -n syntax check" bash -n "$PROJECT_DIR/.aitask-scripts/aitask_codeagent.sh"

# Setup test environment
TMPDIR_TEST="$(setup_test_env)"
CODEAGENT="$TMPDIR_TEST/.aitask-scripts/aitask_codeagent.sh"

# Test 2: list-agents outputs all 4 agents
echo "--- Test 2: list-agents ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" list-agents 2>&1)
assert_contains "list-agents shows claudecode" "AGENT:claudecode" "$output"
assert_contains "list-agents shows geminicli" "AGENT:geminicli" "$output"
assert_contains "list-agents shows codex" "AGENT:codex" "$output"
assert_contains "list-agents shows opencode" "AGENT:opencode" "$output"

# Test 3: list-models claudecode shows expected models
echo "--- Test 3: list-models claudecode ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" list-models claudecode 2>&1)
assert_contains "list-models shows opus4_6" "MODEL:opus4_6" "$output"
assert_contains "list-models shows sonnet4_6" "MODEL:sonnet4_6" "$output"
assert_contains "list-models shows haiku4_5" "MODEL:haiku4_5" "$output"
assert_contains "list-models shows opus4_7" "MODEL:opus4_7" "$output"
assert_contains "list-models shows opus4_7_1m" "MODEL:opus4_7_1m" "$output"
assert_contains "list-models shows cli_id" "CLI_ID:claude-opus-4-6" "$output"
assert_contains "list-models shows notes" "NOTES:" "$output"
assert_contains "list-models shows verified" "VERIFIED:" "$output"

# Test 4: list-models with invalid agent
echo "--- Test 4: list-models invalid agent ---"
assert_exit_nonzero "list-models with invalid agent" bash -c "cd '$TMPDIR_TEST' && bash '$CODEAGENT' list-models notanagent"

# Test 5: resolve pick returns claudecode/opus4_7_1m (current default)
echo "--- Test 5: resolve pick ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" resolve pick 2>&1)
assert_contains "resolve returns opus4_7_1m for pick" "AGENT_STRING:claudecode/opus4_7_1m" "$output"
assert_contains "resolve returns agent" "AGENT:claudecode" "$output"
assert_contains "resolve returns model" "MODEL:opus4_7_1m" "$output"
assert_contains "resolve returns cli_id" "CLI_ID:claude-opus-4-7\[1m\]" "$output"

# Test 6: resolve with --agent-string override
echo "--- Test 6: resolve with --agent-string override ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --agent-string geminicli/gemini2_5pro resolve pick 2>&1)
assert_contains "override agent string" "AGENT_STRING:geminicli/gemini2_5pro" "$output"
assert_contains "override resolves geminicli" "AGENT:geminicli" "$output"

# Test 7: resolve with local config overrides project config
echo "--- Test 7: resolve with local config ---"
cat > "$TMPDIR_TEST/aitasks/metadata/codeagent_config.local.json" << 'LOCALEOF'
{
  "defaults": {
    "pick": "geminicli/gemini3pro"
  }
}
LOCALEOF
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" resolve pick 2>&1)
assert_contains "local config overrides project config" "AGENT_STRING:geminicli/gemini3pro" "$output"
# Clean up local config
rm "$TMPDIR_TEST/aitasks/metadata/codeagent_config.local.json"

# Test 8: check valid agent string (claude should be in PATH on dev machines)
echo "--- Test 8: check valid agent string ---"
if command -v claude &>/dev/null; then
    output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" check "claudecode/sonnet4_6" 2>&1)
    assert_contains "check shows OK" "OK" "$output"
else
    # claude not in PATH - check should fail with binary-not-found, not format error
    output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" check "claudecode/sonnet4_6" 2>&1) || true
    assert_contains "check reports binary not found" "not found" "$output"
    TOTAL=$((TOTAL + 1))
    PASS=$((PASS + 1))  # This is expected behavior
fi

# Test 9: check with invalid format
echo "--- Test 9: check invalid format ---"
assert_exit_nonzero "check rejects invalid format" bash -c "cd '$TMPDIR_TEST' && bash '$CODEAGENT' check 'not-valid-format'"
assert_exit_nonzero "check rejects dots in model" bash -c "cd '$TMPDIR_TEST' && bash '$CODEAGENT' check 'claudecode/sonnet4.6'"

# Test 10: check with unknown model
echo "--- Test 10: check unknown model ---"
assert_exit_nonzero "check rejects unknown model" bash -c "cd '$TMPDIR_TEST' && bash '$CODEAGENT' check 'claudecode/nonexistent_model'"

# Test 11: --dry-run invoke
echo "--- Test 11: --dry-run invoke ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --dry-run invoke pick 42 2>&1)
assert_contains "dry-run starts with DRY_RUN:" "DRY_RUN:" "$output"
assert_contains "dry-run contains claude" "claude" "$output"
assert_contains "dry-run contains model flag" "claude-opus-4-7" "$output"
assert_contains "dry-run contains aitask-pick" "aitask-pick" "$output"
assert_contains "dry-run contains task number" "42" "$output"

# Test 12: coauthor-domain reads configured domain
echo "--- Test 12: coauthor-domain configured ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor-domain 2>&1)
assert_contains "coauthor-domain returns configured domain" "COAUTHOR_DOMAIN:aitasks.io" "$output"

# Test 13: coauthor-domain falls back when field is missing
echo "--- Test 13: coauthor-domain fallback on missing field ---"
cat > "$TMPDIR_TEST/aitasks/metadata/project_config.yaml" << 'YAMLEOF'
verify_build:
YAMLEOF
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor-domain 2>&1)
assert_contains "coauthor-domain falls back to default" "COAUTHOR_DOMAIN:aitasks.io" "$output"

# Test 14: coauthor-domain falls back on empty field
echo "--- Test 14: coauthor-domain fallback on empty field ---"
cat > "$TMPDIR_TEST/aitasks/metadata/project_config.yaml" << 'YAMLEOF'
codeagent_coauthor_domain:
verify_build:
YAMLEOF
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor-domain 2>&1)
assert_contains "coauthor-domain empty field falls back" "COAUTHOR_DOMAIN:aitasks.io" "$output"

# Restore project config for remaining tests
cp "$PROJECT_DIR/aitasks/metadata/project_config.yaml" "$TMPDIR_TEST/aitasks/metadata/project_config.yaml"

# Test 15: coauthor returns Codex metadata
echo "--- Test 15: coauthor Codex metadata ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor codex/gpt5_4 2>&1)
assert_contains "coauthor returns agent string" "AGENT_STRING:codex/gpt5_4" "$output"
assert_contains "coauthor returns name" "AGENT_COAUTHOR_NAME:Codex/GPT5.4" "$output"
assert_contains "coauthor returns email" "AGENT_COAUTHOR_EMAIL:codex@aitasks.io" "$output"
assert_contains "coauthor returns trailer" "AGENT_COAUTHOR_TRAILER:Co-Authored-By: Codex/GPT5.4 <codex@aitasks.io>" "$output"

# Test 16: coauthor uses configured custom domain
echo "--- Test 16: coauthor custom domain ---"
cat > "$TMPDIR_TEST/aitasks/metadata/project_config.yaml" << 'YAMLEOF'
codeagent_coauthor_domain: codex.example
verify_build:
YAMLEOF
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor codex/gpt5_3codex 2>&1)
assert_contains "coauthor uses custom domain for email" "AGENT_COAUTHOR_EMAIL:codex@codex.example" "$output"
assert_contains "coauthor uses model-aware trailer" "AGENT_COAUTHOR_TRAILER:Co-Authored-By: Codex/GPT5.3-Codex <codex@codex.example>" "$output"

# Test 17: coauthor falls back to raw model token when model is unknown
echo "--- Test 17: coauthor unknown model fallback ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor codex/custom_model 2>&1)
assert_contains "coauthor falls back to raw model token" "AGENT_COAUTHOR_NAME:Codex/custom_model" "$output"

# Restore project config before Claude coauthor tests
cp "$PROJECT_DIR/aitasks/metadata/project_config.yaml" "$TMPDIR_TEST/aitasks/metadata/project_config.yaml"

# Test 18: coauthor returns Claude Code metadata
echo "--- Test 18: coauthor Claude Code metadata ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor claudecode/opus4_6 2>&1)
assert_contains "coauthor returns agent string" "AGENT_STRING:claudecode/opus4_6" "$output"
assert_contains "coauthor returns name" "AGENT_COAUTHOR_NAME:Claude Code/Opus 4.6" "$output"
assert_contains "coauthor returns email" "AGENT_COAUTHOR_EMAIL:claudecode@aitasks.io" "$output"
assert_contains "coauthor returns trailer" "AGENT_COAUTHOR_TRAILER:Co-Authored-By: Claude Code/Opus 4.6 <claudecode@aitasks.io>" "$output"

# Test 19: coauthor Claude Code uses configured custom domain
echo "--- Test 19: coauthor Claude Code custom domain ---"
cat > "$TMPDIR_TEST/aitasks/metadata/project_config.yaml" << 'YAMLEOF'
codeagent_coauthor_domain: claude.example
verify_build:
YAMLEOF
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor claudecode/sonnet4_6 2>&1)
assert_contains "coauthor uses custom domain for email" "AGENT_COAUTHOR_EMAIL:claudecode@claude.example" "$output"
assert_contains "coauthor uses model-aware trailer" "AGENT_COAUTHOR_TRAILER:Co-Authored-By: Claude Code/Sonnet 4.6 <claudecode@claude.example>" "$output"

# Test 20: coauthor Claude Code falls back to raw model token when unknown
echo "--- Test 20: coauthor Claude Code unknown model fallback ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor claudecode/unknown_model 2>&1)
assert_contains "coauthor falls back to raw model token" "AGENT_COAUTHOR_NAME:Claude Code/unknown_model" "$output"

# Test 21: coauthor Claude Code handles haiku model with date suffix in cli_id
echo "--- Test 21: coauthor Claude Code haiku model ---"
cp "$PROJECT_DIR/aitasks/metadata/project_config.yaml" "$TMPDIR_TEST/aitasks/metadata/project_config.yaml"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor claudecode/haiku4_5 2>&1)
assert_contains "coauthor strips date suffix from haiku" "AGENT_COAUTHOR_NAME:Claude Code/Haiku 4.5" "$output"

# Test 22: coauthor returns OpenCode metadata (Claude model via opencode)
echo "--- Test 22: coauthor OpenCode metadata ---"
cp "$PROJECT_DIR/aitasks/metadata/project_config.yaml" "$TMPDIR_TEST/aitasks/metadata/project_config.yaml"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor opencode/opencode_claude_opus_4_6 2>&1)
assert_contains "coauthor returns agent string" "AGENT_STRING:opencode/opencode_claude_opus_4_6" "$output"
assert_contains "coauthor returns name" "AGENT_COAUTHOR_NAME:OpenCode/Claude Opus 4.6" "$output"
assert_contains "coauthor returns email" "AGENT_COAUTHOR_EMAIL:opencode@aitasks.io" "$output"
assert_contains "coauthor returns trailer" "AGENT_COAUTHOR_TRAILER:Co-Authored-By: OpenCode/Claude Opus 4.6 <opencode@aitasks.io>" "$output"

# Test 23: coauthor OpenCode uses configured custom domain
echo "--- Test 23: coauthor OpenCode custom domain ---"
cat > "$TMPDIR_TEST/aitasks/metadata/project_config.yaml" << 'YAMLEOF'
codeagent_coauthor_domain: opencode.example
verify_build:
YAMLEOF
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor opencode/opencode_gpt_5_4 2>&1)
assert_contains "coauthor uses custom domain for email" "AGENT_COAUTHOR_EMAIL:opencode@opencode.example" "$output"
assert_contains "coauthor uses model-aware trailer" "AGENT_COAUTHOR_TRAILER:Co-Authored-By: OpenCode/GPT 5.4 <opencode@opencode.example>" "$output"

# Test 24: coauthor OpenCode falls back to raw model token when unknown
echo "--- Test 24: coauthor OpenCode unknown model fallback ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor opencode/custom_model 2>&1)
assert_contains "coauthor falls back to raw model token" "AGENT_COAUTHOR_NAME:OpenCode/custom_model" "$output"

# Test 25: coauthor OpenCode with GPT-style model (openai provider prefix)
echo "--- Test 25: coauthor OpenCode GPT model ---"
cp "$PROJECT_DIR/aitasks/metadata/project_config.yaml" "$TMPDIR_TEST/aitasks/metadata/project_config.yaml"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor opencode/openai_gpt_5_1_codex 2>&1)
assert_contains "coauthor returns GPT name" "AGENT_COAUTHOR_NAME:OpenCode/GPT 5.1 Codex" "$output"

# Test 25b: coauthor OpenCode with GPT 5.4 openai provider entry
echo "--- Test 25b: coauthor OpenCode GPT 5.4 openai provider ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor opencode/openai_gpt_5_4 2>&1)
assert_contains "coauthor returns GPT 5.4 name" "AGENT_COAUTHOR_NAME:OpenCode/GPT 5.4" "$output"

# Test 26: coauthor returns Gemini CLI metadata
echo "--- Test 26: coauthor Gemini CLI metadata ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor geminicli/gemini2_5pro 2>&1)
assert_contains "coauthor returns agent string" "AGENT_STRING:geminicli/gemini2_5pro" "$output"
assert_contains "coauthor returns name" "AGENT_COAUTHOR_NAME:Gemini CLI/2.5 Pro" "$output"
assert_contains "coauthor returns email" "AGENT_COAUTHOR_EMAIL:geminicli@aitasks.io" "$output"
assert_contains "coauthor returns trailer" "AGENT_COAUTHOR_TRAILER:Co-Authored-By: Gemini CLI/2.5 Pro <geminicli@aitasks.io>" "$output"

# Test 26b: coauthor Gemini CLI custom domain
echo "--- Test 26b: coauthor Gemini CLI custom domain ---"
cat > "$TMPDIR_TEST/aitasks/metadata/project_config.yaml" << 'YAMLEOF'
codeagent_coauthor_domain: gemini.example
verify_build:
YAMLEOF
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor geminicli/gemini3_1pro 2>&1)
assert_contains "coauthor uses custom domain for email" "AGENT_COAUTHOR_EMAIL:geminicli@gemini.example" "$output"
assert_contains "coauthor uses model-aware trailer" "AGENT_COAUTHOR_TRAILER:Co-Authored-By: Gemini CLI/3.1 Pro Preview <geminicli@gemini.example>" "$output"

# Test 26c: coauthor Gemini CLI falls back to raw model token when unknown
echo "--- Test 26c: coauthor Gemini CLI unknown model fallback ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" coauthor geminicli/unknown_model 2>&1)
assert_contains "coauthor falls back to raw model token" "AGENT_COAUTHOR_NAME:Gemini CLI/unknown_model" "$output"

# Restore project config before help and remaining tests
cp "$PROJECT_DIR/aitasks/metadata/project_config.yaml" "$TMPDIR_TEST/aitasks/metadata/project_config.yaml"

# Test 27: --help shows usage
echo "--- Test 27: --help ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --help 2>&1)
assert_contains "help shows Usage" "Usage:" "$output"
assert_contains "help shows list-agents" "list-agents" "$output"
assert_contains "help shows list-models" "list-models" "$output"
assert_contains "help shows coauthor" "coauthor <agent-string>" "$output"
assert_contains "help shows coauthor-domain" "coauthor-domain" "$output"
assert_contains "help shows resolution chain" "Resolution chain" "$output"

# Test 28: resolve explain uses sonnet
echo "--- Test 28: resolve explain uses sonnet ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" resolve explain 2>&1)
assert_contains "resolve explain returns sonnet4_6" "AGENT_STRING:claudecode/sonnet4_6" "$output"

# Test 29: resolve with unknown operation
echo "--- Test 29: resolve unknown operation ---"
assert_exit_nonzero "resolve rejects unknown operation" bash -c "cd '$TMPDIR_TEST' && bash '$CODEAGENT' resolve unknown-op"

# Test 30: no command shows help
echo "--- Test 30: no command shows help ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" 2>&1)
assert_contains "no command shows usage" "Usage:" "$output"

# Test 31: unknown command fails
echo "--- Test 31: unknown command ---"
assert_exit_nonzero "unknown command fails" bash -c "cd '$TMPDIR_TEST' && bash '$CODEAGENT' nonexistent-command"

# --- Cleanup ---

set +e
cleanup_test_env "$TMPDIR_TEST"

# --- Summary ---

echo ""
echo "=== Results ==="
echo "PASS: $PASS / $TOTAL"
if [[ $FAIL -gt 0 ]]; then
    echo "FAIL: $FAIL"
    exit 1
else
    echo "All tests passed."
    exit 0
fi
