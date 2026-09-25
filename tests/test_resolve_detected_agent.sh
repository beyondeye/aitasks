#!/usr/bin/env bash
# test_resolve_detected_agent.sh - Tests for aitask_resolve_detected_agent.sh
# Run: bash tests/test_resolve_detected_agent.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Shared assertion helpers (see tests/lib/asserts.sh).
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
RESOLVE_SCRIPT="$PROJECT_DIR/.aitask-scripts/aitask_resolve_detected_agent.sh"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

# --- Tests ---

echo "=== Test: env var fast path ==="
result=$(AITASK_AGENT_STRING="claudecode/opus4_6" bash "$RESOLVE_SCRIPT" 2>&1)
assert_eq "env var returns AGENT_STRING" "AGENT_STRING:claudecode/opus4_6" "$result"

echo "=== Test: explicit args override env var ==="
result=$(AITASK_AGENT_STRING="custom/model" bash "$RESOLVE_SCRIPT" --agent codex --cli-id gpt-5.4 2>&1)
assert_eq "explicit --agent/--cli-id beats env var" "AGENT_STRING:codex/gpt5_4" "$result"

echo "=== Test: explicit cli-id wins over env var (t703 regression) ==="
result=$(AITASK_AGENT_STRING="claudecode/opus4_7_1m" bash "$RESOLVE_SCRIPT" --agent claudecode --cli-id claude-opus-4-6 2>&1)
assert_eq "t703: explicit claude-opus-4-6 resolves despite env var" "AGENT_STRING:claudecode/opus4_6" "$result"

echo "=== Test: exact match claudecode ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --agent claudecode --cli-id claude-opus-4-6 2>&1)
assert_eq "claudecode exact match" "AGENT_STRING:claudecode/opus4_6" "$result"

echo "=== Test: exact match claudecode opus4_7 ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --agent claudecode --cli-id claude-opus-4-7 2>&1)
assert_eq "claudecode opus4_7 exact match" "AGENT_STRING:claudecode/opus4_7" "$result"

echo "=== Test: exact match claudecode opus4_7_1m ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --agent claudecode --cli-id 'claude-opus-4-7[1m]' 2>&1)
assert_eq "claudecode opus4_7_1m exact match" "AGENT_STRING:claudecode/opus4_7_1m" "$result"

echo "=== Test: exact match codex ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --agent codex --cli-id gpt-5.4 2>&1)
assert_eq "codex exact match" "AGENT_STRING:codex/gpt5_4" "$result"

echo "=== Test: exact match codex GPT-5.6 Sol ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --agent codex --cli-id gpt-5.6-sol 2>&1)
assert_eq "codex GPT-5.6 Sol exact match" "AGENT_STRING:codex/gpt5_6_sol" "$result"

echo "=== Test: exact match opencode ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --agent opencode --cli-id "openai/codex-mini-latest" 2>&1)
assert_eq "opencode exact match" "AGENT_STRING:opencode/openai_codex_mini_latest" "$result"

echo "=== Test: opencode suffix match ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --agent opencode --cli-id "codex-mini-latest" 2>&1)
assert_eq "opencode suffix match" "AGENT_STRING:opencode/openai_codex_mini_latest" "$result"

echo "=== Test: exact match opencode GPT-5.6 Sol ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --agent opencode --cli-id "openai/gpt-5.6-sol" 2>&1)
assert_eq "opencode GPT-5.6 Sol exact match" "AGENT_STRING:opencode/openai_gpt_5_6_sol" "$result"

echo "=== Test: opencode GPT-5.6 Sol suffix match ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --agent opencode --cli-id "gpt-5.6-sol" 2>&1)
assert_eq "opencode GPT-5.6 Sol suffix match" "AGENT_STRING:opencode/openai_gpt_5_6_sol" "$result"

echo "=== Test: fallback for unknown cli_id ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --agent claudecode --cli-id unknown-model 2>&1)
assert_eq "fallback returns AGENT_STRING_FALLBACK" "AGENT_STRING_FALLBACK:claudecode/unregistered_unknown_model" "$result"

echo "=== Test: 1M-context Opus 5.5 is registered (t1884) ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --agent claudecode --cli-id 'claude-opus-5-5[1m]' 2>&1)
assert_eq "claude-opus-5-5[1m] exact match" "AGENT_STRING:claudecode/opus5_5_1m" "$result"

echo "=== Test: fallback normalisation into the reserved namespace (t1884) ==="
fallback_for() {
    AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --agent "$1" --cli-id "$2" 2>&1
}
assert_eq "1M-style id" "AGENT_STRING_FALLBACK:claudecode/unregistered_claude_opus_9_9_1m" \
    "$(fallback_for claudecode 'claude-opus-9-9[1m]')"
assert_eq "opencode provider id" "AGENT_STRING_FALLBACK:opencode/unregistered_acme_model_9_x" \
    "$(fallback_for opencode 'acme/model-9.x')"
assert_eq "uppercase and dots" "AGENT_STRING_FALLBACK:codex/unregistered_gpt_9_9_turbo" \
    "$(fallback_for codex 'GPT-9.9.Turbo')"
assert_eq "all-punctuation id" "AGENT_STRING_FALLBACK:claudecode/unregistered_unknown" \
    "$(fallback_for claudecode '-[.]-')"

echo "=== Test: control characters and non-ASCII stay inside one name (t1884) ==="
# sed would normalise per line; an embedded newline must not split the output.
result=$(fallback_for codex $'foo\nbar')
assert_eq "embedded newline is a separator" "AGENT_STRING_FALLBACK:codex/unregistered_foo_bar" "$result"
assert_eq "embedded newline keeps output on one line" "1" "$(printf '%s\n' "$result" | wc -l | tr -d ' ')"
assert_eq "CR and tab are separators" "AGENT_STRING_FALLBACK:codex/unregistered_x_y" \
    "$(fallback_for codex $'x\r\ty')"
assert_eq "newline-only id" "AGENT_STRING_FALLBACK:codex/unregistered_unknown" \
    "$(fallback_for codex $'\n\n')"
assert_eq "non-ASCII bytes are separators" "AGENT_STRING_FALLBACK:codex/unregistered_n_c_de" \
    "$(fallback_for codex 'Ünï-CÔDE')"

echo "=== Test: fallback never collides with a registered name (t1884) ==="
# opus5-5 is not a registered cli_id, but plain normalisation would yield
# opus5_5 -- the registered Opus 5.5 -- and misattribute the run.
result=$(fallback_for claudecode 'opus5-5')
assert_eq "opus5-5 stays in the reserved namespace" "AGENT_STRING_FALLBACK:claudecode/unregistered_opus5_5" "$result"
assert_not_contains "opus5-5 never resolves to opus5_5" "claudecode/opus5_5" "${result/unregistered_opus5_5/}"

echo "=== Test: every fallback round-trips through parse_agent_string (t1884) ==="
for pair in "claudecode|claude-opus-9-9[1m]" "claudecode|opus5-5" "opencode|acme/model-9.x" \
            "codex|GPT-9.9.Turbo" "claudecode|-[.]-" "claudecode|unknown-model" \
            $'codex|foo\nbar' $'codex|x\r\ty' "codex|Ünï-CÔDE"; do
    agent="${pair%%|*}"; cli_id="${pair#*|}"
    out=$(fallback_for "$agent" "$cli_id")
    agent_string="${out#AGENT_STRING_FALLBACK:}"
    rc=0
    parsed=$(bash -c 'source "$1/.aitask-scripts/lib/agent_string.sh" && parse_agent_string "$2" && echo "$PARSED_AGENT/$PARSED_MODEL"' _ "$PROJECT_DIR" "$agent_string" 2>&1) || rc=$?
    assert_exit_zero_rc "parse_agent_string accepts '$agent_string'" "$rc"
    assert_eq "parse round-trips '$agent_string'" "$agent_string" "$parsed"
done

echo "=== Test: coauthor accepts a fallback without borrowing a registered label (t1884) ==="
rc=0
coauthor=$(bash "$PROJECT_DIR/.aitask-scripts/aitask_codeagent.sh" coauthor "claudecode/unregistered_opus5_5" 2>&1) || rc=$?
assert_exit_zero_rc "coauthor exits 0 on a fallback" "$rc"
assert_contains "coauthor trailer names the fallback" \
    "AGENT_COAUTHOR_TRAILER:Co-Authored-By: Claude Code/unregistered_opus5_5 <" "$coauthor"
assert_not_contains "coauthor never uses the Opus 5.5 label" "Opus 5.5" "$coauthor"

echo "=== Test: no shipped registry uses the reserved prefix (t1884) ==="
for f in "$PROJECT_DIR"/aitasks/metadata/models_*.json "$PROJECT_DIR"/seed/models_*.json; do
    [[ -f "$f" ]] || continue
    reserved=$(jq -r '.models[].name | select(startswith("unregistered_"))' "$f")
    assert_eq "no unregistered_* name in ${f#"$PROJECT_DIR"/}" "" "$reserved"
done

echo "=== Test: invalid agent ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --agent invalidagent --cli-id foo 2>&1 || true)
assert_contains "invalid agent dies" "Invalid agent" "$result"

echo "=== Test: missing --agent ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --cli-id foo 2>&1 || true)
assert_contains "missing agent dies" "Missing required argument: --agent" "$result"

echo "=== Test: missing --cli-id ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --agent claudecode 2>&1 || true)
assert_contains "missing cli-id dies" "Missing required argument: --cli-id" "$result"

# --- Summary ---
echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
