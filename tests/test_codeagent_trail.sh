#!/usr/bin/env bash
# test_codeagent_trail.sh - Tests for the trail code-agent operation
# (t1210_3): dry-run composition per agent, codex default-mode pin,
# heavy-class resolution (seeded config + no-config fallback), the
# whitespace fail-closed guard, and verified-score parity across the
# models files.
#
# Resolution expectations are DERIVED from seed/codeagent_config.json and
# checked against an injected sentinel DEFAULT_AGENT_STRING (t1318) — never
# pinned to a literal model, which is what left this file red after t1241
# promoted the defaults to claudecode/opus5.
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
# Derived-default helpers (see tests/lib/codeagent_defaults.sh)
. "$PROJECT_DIR/tests/lib/codeagent_defaults.sh"

# --- Test environment setup ---

# with_config=true copies the seeded codeagent_config.json (which assigns trail
# to the heavy class, alongside pick); with_config=false leaves no config so
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

echo "=== test_codeagent_trail.sh ==="
echo ""

TMPDIR_TEST="$(setup_test_env true)"
CODEAGENT="$TMPDIR_TEST/.aitask-scripts/aitask_codeagent.sh"

# Test 1: claudecode dry-run passes the trail args through verbatim
echo "--- Test 1: claudecode trail dry-run ---"
output=$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" --dry-run invoke trail --refresh art:trail-gates 2>&1)
assert_contains "claudecode dry-run starts with DRY_RUN:" "DRY_RUN:" "$output"
assert_contains "claudecode dry-run contains claude binary" "claude" "$output"
# Cross-check `invoke` against `resolve` rather than pinning a cli_id literal:
# the contract is that the composed command line carries the SAME model the
# resolver picks for this operation, whatever the seeded config says.
seeded_cli_id=$(codeagent_resolve_field CLI_ID \
    "$(cd "$TMPDIR_TEST" && bash "$CODEAGENT" resolve trail 2>&1)")
assert_exit_zero "resolve trail reports a cli_id" test -n "$seeded_cli_id"
assert_contains "claudecode dry-run uses the resolved default model" "$seeded_cli_id" "$output"
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

# Test 4: heavy-class resolution (seeded config): trail == pick, both from config
echo "--- Test 4: resolve trail == resolve pick (seeded) ---"
# The fixture copies seed/codeagent_config.json, so that file — not the live
# aitasks/metadata one — is what the resolutions below read. The two diverge
# (seed shadow is claudecode/*, live shadow is codex/*).
seed_cfg="$PROJECT_DIR/seed/codeagent_config.json"
seeded_pick=$(codeagent_config_default pick "$seed_cfg")
# Registered but not the seeded value: injecting it as DEFAULT_AGENT_STRING is
# what distinguishes "read the config" from "fell through to the hardcoded
# default", which are otherwise identical (both claudecode/opus5 today).
sentinel=$(codeagent_sentinel_excluding "$TMPDIR_TEST/aitasks/metadata" "$seeded_pick")

assert_exit_zero "seed config declares a pick default" test -n "$seeded_pick"

output_tr=$(cd "$TMPDIR_TEST" && DEFAULT_AGENT_STRING="$sentinel" bash "$CODEAGENT" resolve trail 2>&1)
output_pk=$(cd "$TMPDIR_TEST" && DEFAULT_AGENT_STRING="$sentinel" bash "$CODEAGENT" resolve pick 2>&1)
assert_eq "seeded resolve trail matches the configured heavy-class default" \
    "$seeded_pick" "$(codeagent_resolve_field AGENT_STRING "$output_tr")"
assert_eq "seeded resolve pick matches the configured heavy-class default" \
    "$seeded_pick" "$(codeagent_resolve_field AGENT_STRING "$output_pk")"
# The contract this test exists for: trail is in the same class as pick.
assert_eq "seeded resolve trail == resolve pick" "$output_pk" "$output_tr"

# Test 5: no config -> DEFAULT_AGENT_STRING fallback
# Asserting the INJECTED sentinel (rather than the shipped constant) proves the
# fallback path is live without pinning a literal that a promotion would rot,
# and makes Test 4's "not the sentinel" result non-vacuous.
echo "--- Test 5: resolve without config ---"
TMPDIR_NOCFG="$(setup_test_env false)"
CODEAGENT_NOCFG="$TMPDIR_NOCFG/.aitask-scripts/aitask_codeagent.sh"
output_tr=$(cd "$TMPDIR_NOCFG" && DEFAULT_AGENT_STRING="$sentinel" bash "$CODEAGENT_NOCFG" resolve trail 2>&1)
assert_eq "no-config resolve trail falls to DEFAULT_AGENT_STRING" \
    "$sentinel" "$(codeagent_resolve_field AGENT_STRING "$output_tr")"

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

# Test 7: verified-score parity — trail's SEED verified score mirrors explain's,
# and is absent where explain is absent. This is a SEED-AUTHORING baseline
# convention on the verified SCORES only: at seed time trail had no independent
# measured history, so its baseline score was seeded by copying explain's. NOTE
# this score convention is DECOUPLED from model resolution — trail has its own
# independently-editable codeagent_config key and currently resolves to the heavy
# class like pick, NOT explain (Test 4 checks trail == pick; Test 5 the no-config
# fallback). Parity is asserted over seed/models_*.json ONLY — NOT the live
# aitasks/metadata/models_*.json — because live satisfaction feedback
# (aitask_verified_update.sh) accumulates INDEPENDENT per-skill scores, so strict
# trail == explain equality cannot hold on live files by design (a real trail run
# persists its own measured average, even on a model with no explain key). The
# accumulator-side ownership boundary (independent scores persist without an
# explain partner) is pinned by tests/test_verified_update.sh (Test 19/20). (t1232)
echo "--- Test 7: verified-score parity across seed models files ---"
for f in "$PROJECT_DIR"/seed/models_*.json; do
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
