#!/usr/bin/env bash
# test_codeagent_trail.sh - Tests for the trail code-agent operation
# (t1210_3): dry-run composition per agent, codex default-mode pin,
# heavy-class resolution (seeded opus4_8 + no-config fallback), the
# whitespace fail-closed guard, and verified-score parity across the
# models files.
# Run: bash tests/test_codeagent_trail.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0

# Shared assertion helpers (see tests/lib/asserts.sh)
. "$PROJECT_DIR/tests/lib/asserts.sh"

# --- Test environment setup ---

# with_config=true copies the seeded codeagent_config.json (trail ->
# claudecode/opus4_8); with_config=false leaves no config so resolution
# falls through to DEFAULT_AGENT_STRING.
setup_test_env() {
    local with_config="$1"
    local tmpdir
    tmpdir="$(mktemp -d)"

    mkdir -p "$tmpdir/aitasks/metadata"
    setup_fake_aitask_repo "$tmpdir"

    cp "$PROJECT_DIR/.aitask-scripts/aitask_codeagent.sh" "$tmpdir/.aitask-scripts/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" "$tmpdir/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" "$tmpdir/.aitask-scripts/lib/"
    cp "$PROJECT_DIR/.aitask-scripts/lib/agent_string.sh" "$tmpdir/.aitask-scripts/lib/"
    chmod +x "$tmpdir/.aitask-scripts/aitask_codeagent.sh"

    # models_*.json stay present in BOTH envs: `resolve` needs them for CLI_ID.
    cp "$PROJECT_DIR/aitasks/metadata/models_claudecode.json" "$tmpdir/aitasks/metadata/"
    cp "$PROJECT_DIR/aitasks/metadata/models_codex.json" "$tmpdir/aitasks/metadata/"
    cp "$PROJECT_DIR/aitasks/metadata/models_opencode.json" "$tmpdir/aitasks/metadata/"
    if [[ "$with_config" == "true" ]]; then
        cp "$PROJECT_DIR/seed/codeagent_config.json" "$tmpdir/aitasks/metadata/"
    fi
    cp "$PROJECT_DIR/aitasks/metadata/project_config.yaml" "$tmpdir/aitasks/metadata/"

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

echo "=== test_codeagent_trail.sh ==="
echo ""

TMPDIR_TEST="$(setup_test_env true)"
CODEAGENT="$TMPDIR_TEST/.aitask-scripts/aitask_codeagent.sh"

# Test 1: claudecode dry-run passes the trail args through verbatim
echo "--- Test 1: claudecode trail dry-run ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --dry-run invoke trail --refresh art:trail-gates 2>&1)
assert_contains "claudecode dry-run starts with DRY_RUN:" "DRY_RUN:" "$output"
assert_contains "claudecode dry-run contains claude binary" "claude" "$output"
assert_contains "claudecode dry-run contains opus model (seeded default)" "claude-opus-4-8" "$output"
# %q-escaped: the whole slash command is ONE argument with args in order.
assert_contains "claudecode dry-run contains slash command + args verbatim" '/aitask-trail\ --refresh\ art:trail-gates' "$output"

# Test 2: codex dry-run composes the skill prompt in default mode
echo "--- Test 2: codex trail dry-run ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --agent-string codex/gpt5_4 --dry-run invoke trail --refresh art:trail-gates 2>&1)
assert_contains "codex dry-run starts with DRY_RUN:" "DRY_RUN:" "$output"
assert_contains "codex dry-run contains codex binary" "codex" "$output"
assert_contains "codex dry-run contains codex model" "gpt-5.4" "$output"
# %q-escaped composer prompt: one argument, $aitask-trail + ordered args.
assert_contains "codex dry-run contains skill composer + args verbatim" 'aitask-trail\ --refresh\ art:trail-gates' "$output"
# Default-mode pin: read-only analysis must NOT force plan mode or a sandbox.
assert_not_contains "codex dry-run has no plan-mode marker" "plan" "$output"
assert_not_contains "codex dry-run has no sandbox flag" "--sandbox" "$output"

# Test 3: opencode dry-run passes the trail args through verbatim
echo "--- Test 3: opencode trail dry-run ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --agent-string opencode/openai_gpt_5_4 --dry-run invoke trail --topics 635,890 2>&1)
assert_contains "opencode dry-run starts with DRY_RUN:" "DRY_RUN:" "$output"
assert_contains "opencode dry-run contains opencode binary" "opencode" "$output"
assert_contains "opencode dry-run contains --prompt slash command + args verbatim" '/aitask-trail\ --topics\ 635\,890' "$output"

# Test 4: heavy-class resolution (seeded config): trail == pick == opus4_8
echo "--- Test 4: resolve trail == resolve pick (seeded) ---"
output_tr=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" resolve trail 2>&1)
output_pk=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" resolve pick 2>&1)
assert_contains "seeded resolve trail is opus4_8" "AGENT_STRING:claudecode/opus4_8" "$output_tr"
assert_contains "seeded resolve pick is opus4_8" "AGENT_STRING:claudecode/opus4_8" "$output_pk"

# Test 5: no config -> DEFAULT_AGENT_STRING fallback
echo "--- Test 5: resolve without config ---"
TMPDIR_NOCFG="$(setup_test_env false)"
CODEAGENT_NOCFG="$TMPDIR_NOCFG/.aitask-scripts/aitask_codeagent.sh"
output_tr=$(cd "$TMPDIR_NOCFG" && bash "$CODEAGENT_NOCFG" resolve trail 2>&1)
assert_contains "no-config resolve trail falls to default" "AGENT_STRING:claudecode/opus4_8" "$output_tr"

# Test 6: whitespace guard rejects an arg with an embedded space (fail-closed)
echo "--- Test 6: whitespace guard ---"
assert_exit_nonzero "claudecode whitespace arg refused" \
    bash -c "cd '$TMPDIR_TEST' && bash '$CODEAGENT' --dry-run invoke trail --refresh 'art:trail one'"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --dry-run invoke trail --refresh "art:trail one" 2>&1 || true)
assert_contains "whitespace refusal names the cause" "whitespace" "$output"
assert_not_contains "whitespace refusal emits no DRY_RUN line" "DRY_RUN:" "$output"
# Guard fires before per-agent dispatch — same refusal under codex.
assert_exit_nonzero "codex whitespace arg refused" \
    bash -c "cd '$TMPDIR_TEST' && bash '$CODEAGENT' --agent-string codex/gpt5_4 --dry-run invoke trail --topics '635 890'"
# Control: whitespace-free args still dry-run cleanly (guard is not overbroad).
assert_exit_zero "whitespace-free args pass the guard" \
    bash -c "cd '$TMPDIR_TEST' && bash '$CODEAGENT' --dry-run invoke trail --topics 635,890"

# Test 7: verified-score parity — trail mirrors explain in every models
# file (seed + live), and is absent where explain is absent.
echo "--- Test 7: verified-score parity across models files ---"
for f in "$PROJECT_DIR"/seed/models_*.json \
         "$PROJECT_DIR"/aitasks/metadata/models_*.json; do
    if jq -e '[.models[].verified
               | if has("explain") then (.trail == .explain)
                 else (has("trail") | not) end] | all' "$f" >/dev/null; then
        PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1))
        echo "PASS: parity holds in $(basename "$f")"
    else
        FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
        echo "FAIL: verified.trail does not mirror verified.explain in $f"
    fi
done

# --- Cleanup ---

set +e
cleanup_test_env "$TMPDIR_TEST"
cleanup_test_env "$TMPDIR_NOCFG"

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
