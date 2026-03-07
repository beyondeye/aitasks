#!/usr/bin/env bash
# aitask_opencode_models.sh - Discover OpenCode models via CLI and update model config
#
# Uses `opencode models --verbose` to discover available models from connected
# providers and updates aitasks/metadata/models_opencode.json.
#
# Usage:
#   ait opencode-models              # Discover and update model config
#   ait opencode-models --dry-run    # Show what would change without writing
#   ait opencode-models --list       # List discovered model names
#   ait opencode-models --sync-seed  # Also update seed/models_opencode.json

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

# --- Constants ---
METADATA_DIR="${TASK_DIR:-aitasks}/metadata"
METADATA_FILE="$METADATA_DIR/models_opencode.json"
SEED_FILE="seed/models_opencode.json"

# --- Flags ---
DRY_RUN=false
LIST_ONLY=false
SYNC_SEED=false

# --- Argument parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)  DRY_RUN=true; shift ;;
        --list)     LIST_ONLY=true; shift ;;
        --sync-seed) SYNC_SEED=true; shift ;;
        -h|--help)
            echo "Usage: ait opencode-models [--dry-run] [--list] [--sync-seed]"
            echo ""
            echo "Discover OpenCode models via CLI and update model config."
            echo ""
            echo "Options:"
            echo "  --dry-run     Show what would change without writing"
            echo "  --list        List discovered model names only"
            echo "  --sync-seed   Also update seed/models_opencode.json"
            echo "  -h, --help    Show this help"
            exit 0
            ;;
        *) die "Unknown option: $1" ;;
    esac
done

# --- Check prerequisites ---
if ! command -v opencode &>/dev/null; then
    die "opencode binary not found. Install OpenCode first: https://opencode.ai"
fi

if ! command -v jq &>/dev/null; then
    die "jq is required but not found"
fi

# --- Name conversion ---
# opencode/claude-opus-4-6 → zen_claude_opus_4_6  (opencode/Zen proxy gets zen_ prefix)
# openai/gpt-5.3-codex     → openai_gpt_5_3_codex (other providers get their own prefix)
convert_to_model_name() {
    local cli_id="$1"
    local provider="${cli_id%%/*}"
    local raw="${cli_id#*/}"
    local base="${raw//[-.]/_}"

    # All providers get a prefix to clearly indicate the source
    # opencode/ → zen_ (Zen proxy), openai/ → openai_, etc.
    if [[ "$provider" == "opencode" ]]; then
        echo "zen_${base}"
    else
        echo "${provider}_${base}"
    fi
}

# --- Discover models ---
discover_models() {
    local verbose_output
    verbose_output=$(opencode models --verbose 2>/dev/null) || die "Failed to run 'opencode models --verbose'"

    local current_cli_id=""
    local json_block=""
    local in_json=false

    # Build a JSON array of discovered models
    local models_json="[]"

    while IFS= read -r line; do
        # Model ID line: starts with a provider prefix (e.g., opencode/ or openai/)
        if [[ "$line" =~ ^[a-zA-Z]+/ ]] && [[ "$in_json" == "false" ]]; then
            # Process previous model if we have one
            if [[ -n "$current_cli_id" ]] && [[ -n "$json_block" ]]; then
                models_json=$(process_model "$current_cli_id" "$json_block" "$models_json")
            fi
            current_cli_id="$line"
            json_block=""
            in_json=false
            continue
        fi

        # Start of JSON block
        if [[ "$line" == "{" ]] && [[ -n "$current_cli_id" ]]; then
            in_json=true
            json_block="{"
            continue
        fi

        # End of JSON block
        if [[ "$line" == "}" ]] && [[ "$in_json" == "true" ]]; then
            json_block="${json_block}}"
            in_json=false
            continue
        fi

        # Accumulate JSON lines
        if [[ "$in_json" == "true" ]]; then
            json_block="${json_block}${line}"
        fi
    done <<< "$verbose_output"

    # Process last model
    if [[ -n "$current_cli_id" ]] && [[ -n "$json_block" ]]; then
        models_json=$(process_model "$current_cli_id" "$json_block" "$models_json")
    fi

    echo "$models_json"
}

# Process a single model's verbose JSON into our format
process_model() {
    local cli_id="$1"
    local json_block="$2"
    local models_array="$3"

    local name
    name=$(convert_to_model_name "$cli_id")

    local display_name context_limit
    display_name=$(echo "$json_block" | jq -r '.name // empty' 2>/dev/null) || display_name=""
    context_limit=$(echo "$json_block" | jq -r '.limit.context // empty' 2>/dev/null) || context_limit=""

    local provider_id
    provider_id="${cli_id%%/*}"

    local notes="$display_name"
    if [[ -n "$context_limit" ]]; then
        local ctx_k=$(( context_limit / 1000 ))
        notes="${notes} (${ctx_k}k context, ${provider_id} provider)"
    else
        notes="${notes} (${provider_id} provider)"
    fi

    # Add to models array
    jq --arg name "$name" \
       --arg cli_id "$cli_id" \
       --arg notes "$notes" \
       '. + [{
           "name": $name,
           "cli_id": $cli_id,
           "notes": $notes,
           "status": "active",
           "verified": {"task-pick": 0, "explain": 0, "batch-review": 0}
       }]' <<< "$models_array"
}

# --- Merge with existing config ---
# Preserves verified scores and marks disappeared models as unavailable
merge_with_existing() {
    local discovered="$1"
    local existing_file="$2"

    if [[ ! -f "$existing_file" ]]; then
        # No existing file — wrap discovered in models object
        jq '{"models": .}' <<< "$discovered"
        return
    fi

    local existing
    existing=$(cat "$existing_file")

    # Use jq to merge:
    # 1. For each discovered model, preserve existing verified scores if present
    # 2. For existing models not in discovered, mark as unavailable
    jq --argjson discovered "$discovered" '
        # Build lookup of discovered models by name
        ($discovered | map({(.name): .}) | add // {}) as $disc_map |

        # Build lookup of existing models by name
        (.models | map({(.name): .}) | add // {}) as $exist_map |

        # Discovered models: preserve existing verified scores
        ($discovered | map(
            .name as $n |
            if $exist_map[$n] then
                .verified = $exist_map[$n].verified
            else
                .
            end
        )) as $updated_discovered |

        # Existing models not in discovered: mark as unavailable
        (.models | map(
            .name as $n |
            if $disc_map[$n] then
                empty
            else
                . + {"status": "unavailable"}
            end
        )) as $unavailable |

        # Combine: discovered (updated) + unavailable
        {"models": ($updated_discovered + $unavailable)}
    ' <<< "$existing"
}

# --- Main ---

info "Discovering OpenCode models..."
discovered=$(discover_models)

model_count=$(jq 'length' <<< "$discovered")
info "Found $model_count models from connected providers"

# --- List mode ---
if [[ "$LIST_ONLY" == "true" ]]; then
    jq -r '.[].name' <<< "$discovered" | sort
    exit 0
fi

# --- Merge with existing ---
merged=$(merge_with_existing "$discovered" "$METADATA_FILE")

unavailable_count=$(jq '
    .models | map(select(.status == "unavailable")) | length
' <<< "$merged")

total_count=$(jq '.models | length' <<< "$merged")

# --- Dry run mode ---
if [[ "$DRY_RUN" == "true" ]]; then
    info "Dry run — showing what would be written to $METADATA_FILE"
    echo ""

    # Show new models
    jq -r --argjson disc "$discovered" '
        ($disc | map(.name)) as $disc_names |
        .models[] |
        if .status == "unavailable" then
            "  [UNAVAILABLE] \(.name) (\(.cli_id))"
        else
            "  [ACTIVE] \(.name) (\(.cli_id))"
        end
    ' <<< "$merged"

    echo ""
    info "Total: $total_count models ($model_count active, $unavailable_count unavailable)"
    exit 0
fi

# --- Write output ---
mkdir -p "$METADATA_DIR"

# Write with consistent formatting (2-space indent, sorted by name)
jq --indent 2 '.models |= sort_by(.name)' <<< "$merged" > "$METADATA_FILE"
success "Updated $METADATA_FILE ($total_count models: $model_count active, $unavailable_count unavailable)"

# --- Sync to seed if requested ---
if [[ "$SYNC_SEED" == "true" ]]; then
    if [[ -d "seed" ]]; then
        cp "$METADATA_FILE" "$SEED_FILE"
        success "Synced to $SEED_FILE"
    else
        warn "seed/ directory not found — skipping seed sync"
    fi
fi
