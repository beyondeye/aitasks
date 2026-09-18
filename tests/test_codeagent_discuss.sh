#!/usr/bin/env bash
# test_codeagent_discuss.sh - Tests for the discuss code-agent operation
# (t1823_3): dry-run composition per agent for the multi-node and single-node
# argv forms, the codex default-mode pin, resolution parity with shadow, and
# the empty/whitespace fail-closed argument guard.
#
# Resolution expectations are DERIVED from seed/codeagent_config.json and
# checked against an injected sentinel DEFAULT_AGENT_STRING (t1318) — never
# pinned to a literal model, which rots on the next default promotion.
# Run: bash tests/test_codeagent_discuss.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/test_scaffold.sh disable=SC1091
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0

# Shared assertion helpers (see tests/lib/asserts.sh)
# shellcheck source=lib/asserts.sh disable=SC1091
. "$PROJECT_DIR/tests/lib/asserts.sh"
# Derived-default helpers (see tests/lib/codeagent_defaults.sh)
# shellcheck source=lib/codeagent_defaults.sh disable=SC1091
. "$PROJECT_DIR/tests/lib/codeagent_defaults.sh"

# --- Test environment setup ---

# with_config=true copies the seeded codeagent_config.json (which assigns
# discuss the same default as shadow); with_config=false leaves no config so
# resolution falls through to DEFAULT_AGENT_STRING.
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

echo "=== test_codeagent_discuss.sh ==="
echo ""

TMPDIR_TEST="$(setup_test_env true)"
CODEAGENT="$TMPDIR_TEST/.aitask-scripts/aitask_codeagent.sh"

# Test 1: claudecode dry-run carries the skill prompt with all args in order
echo "--- Test 1: claudecode discuss dry-run (multi-node) ---"
output=$(cd "$TMPDIR_TEST" || exit 1 && bash "$CODEAGENT" --dry-run invoke discuss 42 n001 n002 2>&1)
assert_contains "claudecode dry-run starts with DRY_RUN:" "DRY_RUN:" "$output"
assert_contains "claudecode dry-run contains claude binary" "claude" "$output"
# Cross-check `invoke` against `resolve` rather than pinning a cli_id literal:
# the contract is that the composed command line carries the SAME model the
# resolver picks for this operation, whatever the seeded config says.
seeded_cli_id=$(codeagent_resolve_field CLI_ID \
    "$(cd "$TMPDIR_TEST" || exit 1 && bash "$CODEAGENT" resolve discuss 2>&1)")
assert_exit_zero "resolve discuss reports a cli_id" test -n "$seeded_cli_id"
assert_contains "claudecode dry-run uses the resolved default model" "$seeded_cli_id" "$output"
# %q-escaped: the whole slash command is ONE argument with args in order.
assert_contains "claudecode dry-run contains slash command + node ids in order" \
    '/aitask-brainstorm-discuss\ 42\ n001\ n002' "$output"

# Test 2: codex dry-run composes the skill prompt in default mode
echo "--- Test 2: codex discuss dry-run (multi-node) ---"
output=$(cd "$TMPDIR_TEST" || exit 1 && bash "$CODEAGENT" --agent-string codex/gpt5_4 --dry-run invoke discuss 42 n001 n002 2>&1)
assert_contains "codex dry-run starts with DRY_RUN:" "DRY_RUN:" "$output"
assert_contains "codex dry-run contains codex binary" "codex" "$output"
assert_contains "codex dry-run contains codex model" "gpt-5.4" "$output"
# %q-escaped composer prompt: one argument, $aitask-brainstorm-discuss + args.
assert_contains "codex dry-run contains skill composer + node ids in order" \
    'aitask-brainstorm-discuss\ 42\ n001\ n002' "$output"
# Default-mode pin: an advisory read-only discussion must NOT force plan mode
# or a sandbox.
assert_not_contains "codex dry-run has no plan-mode marker" "plan" "$output"
assert_not_contains "codex dry-run has no sandbox flag" "--sandbox" "$output"

# Test 3: opencode dry-run passes the discuss args through verbatim
echo "--- Test 3: opencode discuss dry-run (multi-node) ---"
output=$(cd "$TMPDIR_TEST" || exit 1 && bash "$CODEAGENT" --agent-string opencode/openai_gpt_5_4 --dry-run invoke discuss 42 n001 n002 2>&1)
assert_contains "opencode dry-run starts with DRY_RUN:" "DRY_RUN:" "$output"
assert_contains "opencode dry-run contains opencode binary" "opencode" "$output"
assert_contains "opencode dry-run contains --prompt slash command + node ids" \
    '/aitask-brainstorm-discuss\ 42\ n001\ n002' "$output"

# Test 4: the single-node form composes for every agent (cardinality is >= 1)
echo "--- Test 4: single-node form per agent ---"
output=$(cd "$TMPDIR_TEST" || exit 1 && bash "$CODEAGENT" --dry-run invoke discuss 42 n001 2>&1)
assert_contains "claudecode single-node slash command" '/aitask-brainstorm-discuss\ 42\ n001' "$output"
output=$(cd "$TMPDIR_TEST" || exit 1 && bash "$CODEAGENT" --agent-string codex/gpt5_4 --dry-run invoke discuss 42 n001 2>&1)
assert_contains "codex single-node composer prompt" 'aitask-brainstorm-discuss\ 42\ n001' "$output"
output=$(cd "$TMPDIR_TEST" || exit 1 && bash "$CODEAGENT" --agent-string opencode/openai_gpt_5_4 --dry-run invoke discuss 42 n001 2>&1)
assert_contains "opencode single-node slash command" '/aitask-brainstorm-discuss\ 42\ n001' "$output"

# Test 5: resolution parity with shadow (seeded config), sentinel-checked.
# discuss is the advisory companion of the brainstorm TUI, seeded to the same
# default as the shadow companion. Asserting against the seed FILE (not a
# literal) keeps this green across default promotions; injecting a registered
# non-seeded sentinel as DEFAULT_AGENT_STRING is what distinguishes "read the
# config" from "fell through to the hardcoded default".
echo "--- Test 5: resolve discuss == resolve shadow (seeded) ---"
seed_cfg="$PROJECT_DIR/seed/codeagent_config.json"
seeded_shadow=$(codeagent_config_default shadow "$seed_cfg")
sentinel=$(codeagent_sentinel_excluding "$TMPDIR_TEST/aitasks/metadata" "$seeded_shadow")

assert_exit_zero "seed config declares a shadow default" test -n "$seeded_shadow"

output_di=$(cd "$TMPDIR_TEST" || exit 1 && DEFAULT_AGENT_STRING="$sentinel" bash "$CODEAGENT" resolve discuss 2>&1)
output_sh=$(cd "$TMPDIR_TEST" || exit 1 && DEFAULT_AGENT_STRING="$sentinel" bash "$CODEAGENT" resolve shadow 2>&1)
assert_eq "seeded resolve discuss matches the configured shadow default" \
    "$seeded_shadow" "$(codeagent_resolve_field AGENT_STRING "$output_di")"
assert_eq "seeded resolve discuss == resolve shadow" "$output_sh" "$output_di"

# Test 6: no config -> DEFAULT_AGENT_STRING fallback.
# Asserting the INJECTED sentinel (rather than the shipped constant) proves the
# fallback path is live without pinning a literal that a promotion would rot,
# and makes Test 5's "not the sentinel" result non-vacuous.
echo "--- Test 6: resolve without config ---"
TMPDIR_NOCFG="$(setup_test_env false)"
CODEAGENT_NOCFG="$TMPDIR_NOCFG/.aitask-scripts/aitask_codeagent.sh"
output_di=$(cd "$TMPDIR_NOCFG" || exit 1 && DEFAULT_AGENT_STRING="$sentinel" bash "$CODEAGENT_NOCFG" resolve discuss 2>&1)
assert_eq "no-config resolve discuss falls to DEFAULT_AGENT_STRING" \
    "$sentinel" "$(codeagent_resolve_field AGENT_STRING "$output_di")"

# Test 7: empty and whitespace args are refused — including under --dry-run,
# which is by design: flattening argv into one slash-command string cannot
# preserve those boundaries, so the refusal must fire before composition.
echo "--- Test 7: empty / whitespace argument guard ---"
for agent_flag in "" "--agent-string codex/gpt5_4"; do
    label="claudecode"
    [[ -n "$agent_flag" ]] && label="codex"

    # shellcheck disable=SC2086  # agent_flag is a deliberate two-token flag
    assert_exit_nonzero "$label whitespace-bearing node id refused" \
        bash -c "cd '$TMPDIR_TEST' || exit 1; bash '$CODEAGENT' $agent_flag --dry-run invoke discuss 42 'n001 n002'"
    # shellcheck disable=SC2086
    output=$(cd "$TMPDIR_TEST" || exit 1 && bash "$CODEAGENT" $agent_flag --dry-run invoke discuss 42 "n001 n002" 2>&1 || true)
    assert_contains "$label whitespace refusal names the cause" "argument contains whitespace" "$output"
    assert_not_contains "$label whitespace refusal emits no DRY_RUN line" "DRY_RUN:" "$output"

    # shellcheck disable=SC2086
    assert_exit_nonzero "$label empty node id refused" \
        bash -c "cd '$TMPDIR_TEST' || exit 1; bash '$CODEAGENT' $agent_flag --dry-run invoke discuss 42 ''"
    # shellcheck disable=SC2086
    output=$(cd "$TMPDIR_TEST" || exit 1 && bash "$CODEAGENT" $agent_flag --dry-run invoke discuss 42 "" 2>&1 || true)
    assert_contains "$label empty refusal names the cause" "argument is empty" "$output"
    assert_not_contains "$label empty refusal emits no DRY_RUN line" "DRY_RUN:" "$output"
done

# Control: the guard is not overbroad — whitespace-free argv still composes.
assert_exit_zero "whitespace-free discuss argv still composes" \
    bash -c "cd '$TMPDIR_TEST' || exit 1; bash '$CODEAGENT' --dry-run invoke discuss 42 n001 n002"

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
