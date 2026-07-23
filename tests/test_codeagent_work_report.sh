#!/usr/bin/env bash
# test_codeagent_work_report.sh - Tests for the work-report code-agent
# operation (t1162_2): dry-run composition per agent, codex default-mode pin,
# resolution equivalence with explain, the whitespace fail-closed guard, and
# verified-score parity across the models files.
# Run: bash tests/test_codeagent_work_report.sh

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

# with_config=true copies the seeded codeagent_config.json (work-report ->
# claudecode/sonnet4_6); with_config=false leaves no config so resolution
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

echo "=== test_codeagent_work_report.sh ==="
echo ""

TMPDIR_TEST="$(setup_test_env true)"
CODEAGENT="$TMPDIR_TEST/.aitask-scripts/aitask_codeagent.sh"

# Test 1: claudecode dry-run passes --columns/--tasks through verbatim
echo "--- Test 1: claudecode work-report dry-run ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --dry-run invoke work-report --columns now,next --tasks 12,34 2>&1)
assert_contains "claudecode dry-run starts with DRY_RUN:" "DRY_RUN:" "$output"
assert_contains "claudecode dry-run contains claude binary" "claude" "$output"
assert_contains "claudecode dry-run contains sonnet model (seeded default)" "claude-sonnet-4-6" "$output"
# %q-escaped: the whole slash command is ONE argument with args in order.
assert_contains "claudecode dry-run contains slash command + args verbatim" '/aitask-work-report\ --columns\ now\,next\ --tasks\ 12\,34' "$output"

# Test 2: codex dry-run composes the skill prompt in default mode
echo "--- Test 2: codex work-report dry-run ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --agent-string codex/gpt5_4 --dry-run invoke work-report --columns now,next --tasks 12,34 2>&1)
assert_contains "codex dry-run starts with DRY_RUN:" "DRY_RUN:" "$output"
assert_contains "codex dry-run contains codex binary" "codex" "$output"
assert_contains "codex dry-run contains codex model" "gpt-5.4" "$output"
# %q-escaped composer prompt: one argument, $aitask-work-report + ordered args.
assert_contains "codex dry-run contains skill composer + args verbatim" 'aitask-work-report\ --columns\ now\,next\ --tasks\ 12\,34' "$output"
# Default-mode pin: read-only analysis must NOT force plan mode or a sandbox.
assert_not_contains "codex dry-run has no plan-mode marker" "plan" "$output"
assert_not_contains "codex dry-run has no sandbox flag" "--sandbox" "$output"

# Test 3: opencode dry-run passes --columns/--tasks through verbatim
echo "--- Test 3: opencode work-report dry-run ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --agent-string opencode/openai_gpt_5_4 --dry-run invoke work-report --columns now,next --tasks 12,34 2>&1)
assert_contains "opencode dry-run starts with DRY_RUN:" "DRY_RUN:" "$output"
assert_contains "opencode dry-run contains opencode binary" "opencode" "$output"
assert_contains "opencode dry-run contains --prompt slash command + args verbatim" '/aitask-work-report\ --columns\ now\,next\ --tasks\ 12\,34' "$output"

# Test 4: resolution equivalence with explain (seeded config)
echo "--- Test 4: resolve work-report == resolve explain (seeded) ---"
output_wr=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" resolve work-report 2>&1)
output_ex=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" resolve explain 2>&1)
assert_contains "seeded resolve work-report is sonnet4_6" "AGENT_STRING:claudecode/sonnet4_6" "$output_wr"
assert_contains "seeded resolve explain is sonnet4_6" "AGENT_STRING:claudecode/sonnet4_6" "$output_ex"

# Test 5: resolution equivalence with explain (no config -> DEFAULT_AGENT_STRING)
echo "--- Test 5: resolve equivalence without config ---"
TMPDIR_NOCFG="$(setup_test_env false)"
CODEAGENT_NOCFG="$TMPDIR_NOCFG/.aitask-scripts/aitask_codeagent.sh"
output_wr=$(cd "$TMPDIR_NOCFG" && bash "$CODEAGENT_NOCFG" resolve work-report 2>&1)
output_ex=$(cd "$TMPDIR_NOCFG" && bash "$CODEAGENT_NOCFG" resolve explain 2>&1)
assert_contains "no-config resolve work-report falls to default" "AGENT_STRING:claudecode/opus4_8" "$output_wr"
assert_contains "no-config resolve explain falls to default" "AGENT_STRING:claudecode/opus4_8" "$output_ex"

# Test 6: whitespace guard rejects an arg with an embedded space (fail-closed)
echo "--- Test 6: whitespace guard ---"
assert_exit_nonzero "claudecode whitespace arg refused" \
    bash -c "cd '$TMPDIR_TEST' && bash '$CODEAGENT' --dry-run invoke work-report --columns 'my col'"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --dry-run invoke work-report --columns "my col" 2>&1 || true)
assert_contains "whitespace refusal names the cause" "whitespace" "$output"
assert_not_contains "whitespace refusal emits no DRY_RUN line" "DRY_RUN:" "$output"
# Guard fires before per-agent dispatch — same refusal under codex.
assert_exit_nonzero "codex whitespace arg refused" \
    bash -c "cd '$TMPDIR_TEST' && bash '$CODEAGENT' --agent-string codex/gpt5_4 --dry-run invoke work-report --tasks '12 34'"
# Control: whitespace-free args still dry-run cleanly (guard is not overbroad).
assert_exit_zero "whitespace-free args pass the guard" \
    bash -c "cd '$TMPDIR_TEST' && bash '$CODEAGENT' --dry-run invoke work-report --columns now,next"

# Test 7: verified-score parity — work-report mirrors explain in every
# models file (seed + live), and is absent where explain is absent.
echo "--- Test 7: verified-score parity across models files ---"
for f in "$PROJECT_DIR"/seed/models_*.json \
         "$PROJECT_DIR"/aitasks/metadata/models_*.json; do
    if jq -e '[.models[].verified
               | if has("explain") then (.["work-report"] == .explain)
                 else (has("work-report") | not) end] | all' "$f" >/dev/null; then
        PASS=$((PASS + 1)); TOTAL=$((TOTAL + 1))
        echo "PASS: parity holds in $(basename "$f")"
    else
        FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
        echo "FAIL: verified.work-report does not mirror verified.explain in $f"
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
