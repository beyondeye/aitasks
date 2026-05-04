#!/usr/bin/env bash
# test_codex_model_detect.sh — Batch test Codex CLI model self-identification
#
# Tests various prompt formulations across multiple models to find the most
# reliable way for Codex to self-report its model ID. Uses `codex exec` in
# non-interactive mode with --json output to capture both ground truth
# (from turn_context) and the model's self-reported answer.
#
# Requires: codex CLI, OpenAI API access, jq
#
# Usage:
#   bash tests/test_codex_model_detect.sh
#   bash tests/test_codex_model_detect.sh --models gpt-5.4,gpt-5.3-codex
#   bash tests/test_codex_model_detect.sh --prompts 1,3
#   bash tests/test_codex_model_detect.sh --models gpt-5.4 --prompts 1,2,3,4
#   bash tests/test_codex_model_detect.sh --timeout 45
#
# Output: Results matrix + CSV log + best prompt recommendation

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- Configuration ---

# Read the model list from aitasks/metadata/models_codex.json so the test
# stays in sync with the canonical model registry. The dispatcher already
# requires `jq` (early skip if unavailable), so this adds no new dependency.
MODELS_JSON="${MODELS_JSON:-aitasks/metadata/models_codex.json}"
ALL_MODELS=()
if [[ -f "$MODELS_JSON" ]]; then
    while IFS= read -r m; do
        [[ -n "$m" ]] && ALL_MODELS+=("$m")
    done < <(jq -r '.models[].cli_id' "$MODELS_JSON")
fi
if [[ ${#ALL_MODELS[@]} -eq 0 ]]; then
    echo "ERROR: Could not read model list from $MODELS_JSON" >&2
    exit 2
fi

# Prompt formulations to test
declare -A PROMPT_TEXTS
PROMPT_TEXTS[1]="What is your exact model ID? Reply with ONLY the model ID string, nothing else."
PROMPT_TEXTS[2]="You are a GPT model. Your model identifier follows a pattern like gpt-X.Y or gpt-X.Y-suffix. What is your exact model identifier? Reply with ONLY that string."
PROMPT_TEXTS[3]="Your session turn context metadata includes a model field with your exact model identifier. What is the value of that field? Reply ONLY with that value, like gpt-5.4."
PROMPT_TEXTS[4]="Do NOT guess. Read your turn_context or session metadata to find your model identifier. It will be in the format gpt-X.Y or gpt-X.Y-suffix. Report ONLY that exact string."

declare -A PROMPT_LABELS
PROMPT_LABELS[1]="P1:direct"
PROMPT_LABELS[2]="P2:format-hint"
PROMPT_LABELS[3]="P3:context-directed"
PROMPT_LABELS[4]="P4:assertive-context"

ALL_PROMPT_IDS=(1 2 3 4)

TIMEOUT=30
RESULTS_DIR=""
CSV_FILE=""

# --- Argument parsing ---

SELECTED_MODELS=()
SELECTED_PROMPTS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --models)
            IFS=',' read -ra SELECTED_MODELS <<< "$2"
            shift 2
            ;;
        --prompts)
            IFS=',' read -ra SELECTED_PROMPTS <<< "$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: bash tests/test_codex_model_detect.sh [--models M1,M2] [--prompts 1,2,3,4] [--timeout SECS]"
            echo ""
            echo "Options:"
            echo "  --models    Comma-separated list of model IDs to test (default: all 6)"
            echo "  --prompts   Comma-separated list of prompt IDs 1-4 (default: all 4)"
            echo "  --timeout   Timeout per codex exec run in seconds (default: 30)"
            echo ""
            echo "Models: ${ALL_MODELS[*]}"
            echo "Prompts: 1=direct, 2=format-hint, 3=context-directed, 4=assertive-context"
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

# Default to all if not specified
if [[ ${#SELECTED_MODELS[@]} -eq 0 ]]; then
    SELECTED_MODELS=("${ALL_MODELS[@]}")
fi
if [[ ${#SELECTED_PROMPTS[@]} -eq 0 ]]; then
    SELECTED_PROMPTS=("${ALL_PROMPT_IDS[@]}")
fi

# --- Prerequisites ---

if ! command -v codex &>/dev/null; then
    echo "SKIP: codex CLI not installed — skipping test"
    exit 0
fi
if ! command -v jq &>/dev/null; then
    echo "SKIP: jq not installed — skipping test"
    exit 0
fi

# --- Setup ---

RESULTS_DIR="$(mktemp -d "${TMPDIR:-/tmp}/codex_model_test_XXXXXX")"
CSV_FILE="$RESULTS_DIR/results.csv"
echo "model,prompt_id,prompt_label,ground_truth,reported,normalized_reported,status" > "$CSV_FILE"

echo "=== Codex Model Self-Identification Test ==="
echo "Date: $(date '+%Y-%m-%d %H:%M')"
echo "Codex version: $(codex --version 2>/dev/null || echo 'unknown')"
echo "Models: ${SELECTED_MODELS[*]}"
echo "Prompts: ${SELECTED_PROMPTS[*]}"
echo "Timeout: ${TIMEOUT}s per run"
echo "Results dir: $RESULTS_DIR"
echo ""

# --- Counters ---

TOTAL=0
MATCH=0
PARTIAL=0
MISMATCH=0
ERROR=0

# Track per-prompt stats
declare -A PROMPT_MATCH_COUNT
declare -A PROMPT_TOTAL_COUNT
for pid in "${SELECTED_PROMPTS[@]}"; do
    PROMPT_MATCH_COUNT[$pid]=0
    PROMPT_TOTAL_COUNT[$pid]=0
done

# --- Helper functions ---

# Normalize a model string for comparison:
# - trim whitespace, backticks, quotes
# - lowercase
# - strip leading/trailing punctuation
normalize_model() {
    local raw="$1"
    # Remove backticks, quotes, leading/trailing whitespace
    local cleaned
    cleaned=$(echo "$raw" | tr -d '`"'"'" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    # Remove trailing period or comma
    cleaned="${cleaned%.}"
    cleaned="${cleaned%,}"
    # Lowercase
    echo "$cleaned" | tr '[:upper:]' '[:lower:]'
}

# Extract ground truth model from JSON stream (turn_context event)
extract_ground_truth() {
    local json_file="$1"
    # Look for turn_context event and extract .payload.model
    jq -r 'select(.type == "turn_context") | .payload.model // empty' "$json_file" 2>/dev/null | head -1
}

# Extract the model's final text response from JSON stream
extract_reported_model() {
    local json_file="$1"
    # The last agent_message item contains the final response
    # Try item.completed with type agent_message first
    local result
    result=$(jq -r 'select(.type == "item.completed" and .item.type == "agent_message") | .item.text // empty' "$json_file" 2>/dev/null | tail -1)
    if [[ -z "$result" ]]; then
        # Fallback: try response_item with agent_message
        result=$(jq -r 'select(.type == "response_item" and .payload.type == "message") | .payload.content[]? | select(.type == "output_text") | .text // empty' "$json_file" 2>/dev/null | tail -1)
    fi
    echo "$result"
}

# Compare ground truth with reported model
compare_models() {
    local ground_truth="$1"
    local reported="$2"

    local gt_norm reported_norm
    gt_norm=$(normalize_model "$ground_truth")
    reported_norm=$(normalize_model "$reported")

    if [[ -z "$reported_norm" ]]; then
        echo "ERROR"
        return
    fi

    if [[ "$gt_norm" == "$reported_norm" ]]; then
        echo "MATCH"
        return
    fi

    # Check partial match (ground truth is substring of reported or vice versa)
    if [[ "$reported_norm" == *"$gt_norm"* ]] || [[ "$gt_norm" == *"$reported_norm"* ]]; then
        echo "PARTIAL"
        return
    fi

    echo "MISMATCH"
}

# --- Run tests ---

run_count=0
total_runs=$(( ${#SELECTED_MODELS[@]} * ${#SELECTED_PROMPTS[@]} ))

for model in "${SELECTED_MODELS[@]}"; do
    for pid in "${SELECTED_PROMPTS[@]}"; do
        run_count=$((run_count + 1))
        prompt="${PROMPT_TEXTS[$pid]}"
        label="${PROMPT_LABELS[$pid]}"

        echo -n "[$run_count/$total_runs] Model: $model | $label ... "

        json_file="$RESULTS_DIR/${model//\./_}_p${pid}.jsonl"
        output_file="$RESULTS_DIR/${model//\./_}_p${pid}_output.txt"

        # Run codex exec
        local_status="OK"
        if ! timeout "${TIMEOUT}" codex exec \
            --ephemeral \
            --json \
            -m "$model" \
            -s read-only \
            -o "$output_file" \
            "$prompt" \
            > "$json_file" 2>/dev/null; then
            local_status="TIMEOUT_OR_ERROR"
        fi

        # Extract ground truth and reported model
        ground_truth=$(extract_ground_truth "$json_file")
        reported=$(extract_reported_model "$json_file")
        reported_norm=$(normalize_model "${reported:-}")

        # If no ground truth from JSON, use the model we specified
        if [[ -z "$ground_truth" ]]; then
            ground_truth="$model"
        fi

        # Compare
        if [[ "$local_status" == "TIMEOUT_OR_ERROR" && -z "$reported" ]]; then
            status="ERROR"
        else
            status=$(compare_models "$ground_truth" "$reported")
        fi

        # Update counters
        TOTAL=$((TOTAL + 1))
        PROMPT_TOTAL_COUNT[$pid]=$((PROMPT_TOTAL_COUNT[$pid] + 1))
        case "$status" in
            MATCH)
                MATCH=$((MATCH + 1))
                PROMPT_MATCH_COUNT[$pid]=$((PROMPT_MATCH_COUNT[$pid] + 1))
                ;;
            PARTIAL) PARTIAL=$((PARTIAL + 1)) ;;
            MISMATCH) MISMATCH=$((MISMATCH + 1)) ;;
            ERROR) ERROR=$((ERROR + 1)) ;;
        esac

        # Log to CSV
        echo "$model,$pid,$label,$ground_truth,\"$reported\",\"$reported_norm\",$status" >> "$CSV_FILE"

        # Print inline result
        case "$status" in
            MATCH)    echo "MATCH (reported: $reported_norm)" ;;
            PARTIAL)  echo "PARTIAL (reported: $reported_norm, expected: $ground_truth)" ;;
            MISMATCH) echo "MISMATCH (reported: $reported_norm, expected: $ground_truth)" ;;
            ERROR)    echo "ERROR (no response or timeout)" ;;
        esac
    done
done

# --- Results Matrix ---

echo ""
echo "=== Results Matrix ==="
echo ""

# Header
printf "%-22s" "MODEL"
for pid in "${SELECTED_PROMPTS[@]}"; do
    printf "| %-20s" "${PROMPT_LABELS[$pid]}"
done
echo ""

# Separator
printf "%-22s" "----------------------"
for pid in "${SELECTED_PROMPTS[@]}"; do
    printf "|%-20s" "--------------------"
done
echo ""

# Data rows
for model in "${SELECTED_MODELS[@]}"; do
    printf "%-22s" "$model"
    for pid in "${SELECTED_PROMPTS[@]}"; do
        # Look up result from CSV
        result=$(grep "^${model},${pid}," "$CSV_FILE" | cut -d',' -f7 | head -1)
        reported=$(grep "^${model},${pid}," "$CSV_FILE" | cut -d'"' -f4 | head -1)
        if [[ "$result" == "MATCH" ]]; then
            printf "| %-20s" "MATCH"
        elif [[ "$result" == "PARTIAL" ]]; then
            printf "| %-20s" "PARTIAL($reported)"
        elif [[ "$result" == "MISMATCH" ]]; then
            printf "| %-20s" "MISS($reported)"
        else
            printf "| %-20s" "ERROR"
        fi
    done
    echo ""
done

# --- Prompt Rankings ---

echo ""
echo "=== Prompt Rankings ==="
echo ""

for pid in "${SELECTED_PROMPTS[@]}"; do
    total="${PROMPT_TOTAL_COUNT[$pid]}"
    matches="${PROMPT_MATCH_COUNT[$pid]}"
    if [[ "$total" -gt 0 ]]; then
        pct=$((matches * 100 / total))
    else
        pct=0
    fi
    echo "${PROMPT_LABELS[$pid]}: $matches/$total matched ($pct%)"
done

# --- Overall Summary ---

echo ""
echo "=== Overall Summary ==="
echo "Total runs: $TOTAL"
echo "MATCH: $MATCH  PARTIAL: $PARTIAL  MISMATCH: $MISMATCH  ERROR: $ERROR"
echo ""
echo "CSV results: $CSV_FILE"
echo "JSON logs: $RESULTS_DIR/"
echo ""

# Find best prompt
best_pid=""
best_count=0
for pid in "${SELECTED_PROMPTS[@]}"; do
    if [[ "${PROMPT_MATCH_COUNT[$pid]}" -gt "$best_count" ]]; then
        best_count="${PROMPT_MATCH_COUNT[$pid]}"
        best_pid="$pid"
    fi
done

if [[ -n "$best_pid" ]]; then
    echo "BEST PROMPT: ${PROMPT_LABELS[$best_pid]} ($best_count/${PROMPT_TOTAL_COUNT[$best_pid]} matches)"
    echo "Text: ${PROMPT_TEXTS[$best_pid]}"
fi

# This test is a calibration tool: it identifies the prompt that best elicits
# a clean model ID from codex CLI. Codex's self-reported model name is known
# to drift (e.g. newer models report themselves as gpt-5.5 mid-rollout, and
# preview models like gpt-5.3-codex-spark are auth-gated and time out under
# non-Pro accounts). Requiring 100% match across all (model, prompt) pairs
# is therefore unrealistic.
#
# Pass when the best prompt achieves >= 1 MATCH AND the test is not entirely
# in error (calibration produced a usable result). The BEST PROMPT line is
# the actionable output — feed it into aitask_resolve_detected_agent.sh.
threshold=1

if [[ "$best_count" -ge "$threshold" && "$ERROR" -lt "$TOTAL" ]]; then
    echo ""
    echo "PASS: best prompt ${PROMPT_LABELS[$best_pid]} achieved $best_count/${PROMPT_TOTAL_COUNT[$best_pid]} matches."
    exit 0
else
    echo ""
    echo "FAIL: no prompt achieved any match (calibration failed). Review results above — likely a codex CLI / auth / network issue."
    exit 1
fi
