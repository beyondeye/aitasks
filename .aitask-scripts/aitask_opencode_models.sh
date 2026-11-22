#!/usr/bin/env bash
# aitask_opencode_models.sh - Discover OpenCode models via CLI and update model config
#
# Uses `opencode models --verbose` to discover available models from connected
# providers and updates aitasks/metadata/models_opencode.json.
#
# Usage (there is no `ait` subcommand for this script; the
# /aitask-refresh-code-models skill runs it the same way):
#   bash .aitask-scripts/aitask_opencode_models.sh              # Discover and update model config
#   bash .aitask-scripts/aitask_opencode_models.sh --dry-run    # Show what would change without writing
#   bash .aitask-scripts/aitask_opencode_models.sh --list       # List discovered model names
#   bash .aitask-scripts/aitask_opencode_models.sh --sync-seed  # Also update seed/models_opencode.json

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/atomic_write.sh
source "$SCRIPT_DIR/lib/atomic_write.sh"
# shellcheck source=lib/registry_cas.sh
source "$SCRIPT_DIR/lib/registry_cas.sh"

# --- Constants ---
METADATA_DIR="${TASK_DIR:-aitasks}/metadata"
METADATA_FILE="$METADATA_DIR/models_opencode.json"
SEED_FILE="seed/models_opencode.json"
# Attempts at the compare-and-swap write before giving up (see registry_cas.sh)
MAX_SWAP_ATTEMPTS=5

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
            echo "Usage: bash .aitask-scripts/aitask_opencode_models.sh [--dry-run] [--list] [--sync-seed]"
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
# opencode/claude-opus-4-6 → opencode_claude_opus_4_6
# openai/gpt-5.3-codex     → openai_gpt_5_3_codex
#
# Not injective: '-', '.' and '_' all become '_', so opencode/foo-bar,
# opencode/foo.bar and opencode/foo_bar derive the same name. Rows (and the
# aitask-stats history) are keyed by name, so the row-identity guard below
# (collision_guard_message) refuses any run where that would merge two models.
convert_to_model_name() {
    local cli_id="$1"
    local provider="${cli_id%%/*}"
    local raw="${cli_id#*/}"
    local base="${raw//[-.]/_}"

    # All providers get their own explicit prefix so runtime/model attribution
    # stays aligned with the provider-qualified cli_id.
    echo "${provider}_${base}"
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
           "verified": {"pick": 0, "explain": 0, "batch-review": 0, "work-report": 0, "trail": 0}
        }]' <<< "$models_array"
}

# --- Merge with existing config ---
# Preserves every field discovery does not own (verified priors, ...) and marks
# disappeared models as unavailable. <existing_file> is the registry to merge
# from (the CAS snapshot on the write path), or "" / a missing path when there is
# none.
#
# Legacy usagestats / verifiedstats counters on an existing row are CARRIED, never
# added and never dropped: until the stats migration (t1912_5) has absorbed them
# into the aitask-stats branch they are the only copy, and dropping them here
# would lose them. New rows get none (the counters live on aitask-stats).
#
# Other registry writers (the migration's no-remote strip, ...) can rewrite the
# same file, so the write path merges from a byte snapshot and swaps the result
# in only if the registry still matches it (ait_cas_rewrite, lib/registry_cas.sh):
# a write landing while this runs makes the swap re-merge on the fresh content.
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
    # 1. For each discovered model, carry over every existing field discovery does not own
    # 2. For existing models not in discovered, mark as unavailable
    jq --argjson discovered "$discovered" '
        # Build lookups of discovered models by name and cli_id
        ($discovered | map({(.name): .}) | add // {}) as $disc_name_map |
        ($discovered | map({(.cli_id): .}) | add // {}) as $disc_cli_map |

        # Build lookups of existing models by name and cli_id
        (.models | map({(.name): .}) | add // {}) as $exist_name_map |
        (.models | map({(.cli_id): .}) | add // {}) as $exist_cli_map |

        # Discovered models: discovery owns name/cli_id/notes/status; every
        # other field on the existing row (verified, verifiedstats, usagestats,
        # ...) is written by other updaters and is carried over, even when the
        # stored model name changes but cli_id remains stable. Null fields fall
        # back to the discovered defaults.
        ($discovered | map(
            .name as $n |
            .cli_id as $id |
            ($exist_name_map[$n] // $exist_cli_map[$id]) as $existing |
            if $existing then
                . + ($existing
                     | del(.name, .cli_id, .notes, .status)
                     | with_entries(select(.value != null)))
            else
                .
            end
        )) as $updated_discovered |

        # Existing models not in discovered: mark as unavailable
        (.models | map(
            .name as $n |
            .cli_id as $id |
            if $disc_name_map[$n] or $disc_cli_map[$id] then
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

# --- Reserved-name guard (fails closed BEFORE any write) ---
# Names starting with this prefix are reserved for agent-string fallbacks of
# unregistered models (aitask_resolve_detected_agent.sh). convert_to_model_name
# copies the provider verbatim, so a provider literally named "unregistered"
# would derive one. Renaming cannot escape it (any in-grammar rename is some
# other provider's derived name) and skipping/deleting would lose models and
# their verified stats, so refuse the whole run and leave the registry intact.
RESERVED_FALLBACK_PREFIX="unregistered_"

# reserved_guard_message <registry_file> — print the refusal message when the
# discovered set or <registry_file>'s rows carry a reserved name; print nothing
# when both are clean. <registry_file> may be "" (no registry yet).
reserved_guard_message() {
    local registry_file="$1"
    local reserved_discovered reserved_existing="" msg
    reserved_discovered=$(jq -r --arg p "$RESERVED_FALLBACK_PREFIX" \
        '.[] | select(.name | startswith($p)) | "  \(.name) (\(.cli_id))"' <<< "$discovered") || return 1
    if [[ -n "$registry_file" && -f "$registry_file" ]]; then
        reserved_existing=$(jq -r --arg p "$RESERVED_FALLBACK_PREFIX" \
            '.models[] | select(.name | startswith($p)) | "  \(.name) (\(.cli_id))"' "$registry_file") || return 1
    fi
    if [[ -z "$reserved_discovered" && -z "$reserved_existing" ]]; then
        return 0
    fi
    msg="Refusing to update $METADATA_FILE: model names starting with '${RESERVED_FALLBACK_PREFIX}' are reserved for agent-string fallbacks of unregistered models (see aitask_resolve_detected_agent.sh). Nothing was written."
    if [[ -n "$reserved_discovered" ]]; then
        # Editing the registry cannot fix these: the name is re-derived from
        # the provider id on every discovery run.
        msg+="
Discovered models whose provider id derives a reserved name:
$reserved_discovered
  Fix: the name comes from the OpenCode provider id, so editing $METADATA_FILE does not help. Rename that provider in your OpenCode configuration (a custom provider's id in opencode.json) or disconnect it, so no model id starts with 'unregistered/', then re-run."
    fi
    if [[ -n "$reserved_existing" ]]; then
        msg+="
Existing rows in $METADATA_FILE with a reserved name:
$reserved_existing
  Fix: rename or remove each listed row by hand, carrying its verified and verifiedstats over to the new name. If its cli_id is still discovered, fix the provider id first (see above), or the next run derives the reserved name again."
    fi
    printf '%s\n' "$msg"
}

# --- Row-identity guard (fails closed BEFORE any write) ---
# merge_with_existing selects rows through name -> row and cli_id -> row maps
# built with `add`, which silently keep the LAST row of a repeated key, and the
# usage/verification history on the aitask-stats branch (lib/model_stats_store.py)
# is keyed by model name too. So the merge is only sound when every name and
# every cli_id names one model. Refuse when:
#   (a) a name repeats in the discovered set (convert_to_model_name is not
#       injective: opencode/foo-bar and opencode/foo.bar both derive
#       opencode_foo_bar);
#   (b) a name repeats in the registry (even with one cli_id — the rows can hold
#       different verified values);
#   (c) a name is on both sides with different cli_ids (the discovered model
#       would take over the registry row's name and its aitask-stats history);
#   (d) a cli_id repeats in the registry under different names (the merge keeps
#       one row and drops the other).
# One matching row per side, and the cli_id-keyed rename (registry
# legacy_name/<id> -> discovered derived_name/<id>), break none of these.
# The advice never says to rename: renaming or removing a row does not move the
# aitask-stats history recorded under its name.

# collision_guard_message <registry_file> — print the refusal message when any
# of (a)-(d) holds; print nothing when clean. <registry_file> may be "" (no
# registry yet). Returns 1 only when jq fails.
collision_guard_message() {
    local registry_file="$1"
    # The registry goes in as a jq file input, never as an argv string: a large
    # registry (thousands of unavailable rows) would exceed the per-argument
    # limit and fail with "Argument list too long". No registry yet is an
    # explicit empty document.
    local -a reg_input=(--argjson regdoc '[{"models": []}]')
    if [[ -n "$registry_file" && -f "$registry_file" ]]; then
        reg_input=(--slurpfile regdoc "$registry_file")
    fi
    jq -r "${reg_input[@]}" --arg file "$METADATA_FILE" '
        ($regdoc[0].models // [] | map({name, cli_id})) as $reg |
        def dups(f): group_by(f) | map(select(length > 1));
        def by_name: "  \(.[0].name): " + (map("\(.cli_id) (\(.src))") | join(", "));
        def by_cli: "  \(.[0].cli_id): " + (map("\(.name) (\(.src))") | join(", "));
        (map({name, cli_id, src: "discovered"})) as $d |
        ($reg | map(. + {src: "registry"})) as $r |
        ($d | dups(.name)) as $a |
        ($r | dups(.name)) as $b |
        ([$d[], $r[]] | group_by(.name)
            | map(select(length == 2
                         and (map(.src) | unique | length) == 2
                         and (map(.cli_id) | unique | length) == 2))) as $c |
        ($r | dups(.cli_id)) as $x |
        if ($a + $b + $c + $x | length) == 0 then empty else
            ["Refusing to update \($file): its rows (and the usage/verification history on the aitask-stats branch) are keyed by model name, and these models would be merged into one. Nothing was written."]
            + (if ($a | length) > 0 then
                ["Discovered models that derive the same name:"]
                + ($a | map(by_name))
                + ["  Fix: the name is derived from the cli_id (with every - and . replaced by _), so the naming scheme cannot tell these apart and editing \($file) cannot fix it. Disconnect one of them in OpenCode and report the collision."]
               else [] end)
            + (if ($c | length) > 0 then
                ["Discovered models that would take over the name of a registry row:"]
                + ($c | map(by_name))
                + ["  Fix: if the discovered cli_id is the same model under a new id, change the cli_id of that registry row to it and keep its name, so the history recorded under the name stays with the model it belongs to. Otherwise leave the row as it is: renaming or removing it would not move that history, and the discovered model would inherit it. A different model cannot be registered under this name."]
               else [] end)
            + (if ($b | length) + ($x | length) > 0 then
                ["Duplicate rows in \($file):"]
                + ($b | map(by_name))
                + ($x | map(by_cli))
                + ["  Fix: leave these rows in place. Each may carry its own verified values and legacy counters, and each name may have its own usage/verification history on the aitask-stats branch; this refresh cannot tell which is right. Do not delete either one until you have reconciled their metadata and any separate history by hand. The refresh changes nothing until then."]
               else [] end)
            | join("\n")
        end
    ' <<< "$discovered"
}

reserved_msg="$(reserved_guard_message "$METADATA_FILE")" || die "Failed to read $METADATA_FILE"
if [[ -n "$reserved_msg" ]]; then
    die "$reserved_msg"
fi
collision_msg="$(collision_guard_message "$METADATA_FILE")" || die "Failed to read $METADATA_FILE"
if [[ -n "$collision_msg" ]]; then
    die "$collision_msg"
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
# Render for ait_cas_rewrite: re-merge from the snapshot it hands us. Runs once
# per attempt, so a row a concurrent writer changed is merged, never erased.
# Must return, never die (registry_cas.sh); GUARD_MSG tells the caller why.
# Both guards re-run on every snapshot, so a guarded row a concurrent writer
# lands between the pre-write check and the swap is still refused.
#
# RENDERED_REGISTRY keeps the exact bytes this render produced. ait_atomic_render
# runs the render in this shell ("$@" > tmp), and each retry overwrites it, so
# after a successful swap it holds the bytes that were swapped in — the bytes
# both guards checked. The seed sync below renders from them, never from a
# re-read of the live file.
GUARD_MSG=""
RENDERED_REGISTRY=""
render_refresh() {
    local rendered
    GUARD_MSG="$(reserved_guard_message "$1")" || return 1
    [[ -z "$GUARD_MSG" ]] || return 1
    GUARD_MSG="$(collision_guard_message "$1")" || return 1
    [[ -z "$GUARD_MSG" ]] || return 1
    merged="$(merge_with_existing "$discovered" "$1")" || return 1
    # Consistent formatting: 2-space indent, sorted by name
    rendered="$(jq --indent 2 '.models |= sort_by(.name)' <<< "$merged")" || return 1
    RENDERED_REGISTRY="$rendered"
    printf '%s\n' "$rendered"
}

cas_rc=0
ait_cas_rewrite "$METADATA_FILE" "$MAX_SWAP_ATTEMPTS" render_refresh || cas_rc=$?
if [[ -n "$GUARD_MSG" ]]; then
    # A guarded row (reserved name or row-identity conflict) arrived after the
    # pre-write guard (e.g. through a pull or a concurrent writer).
    die "$GUARD_MSG"
fi
if (( cas_rc == 2 )); then
    die "$METADATA_FILE kept changing during the refresh ($MAX_SWAP_ATTEMPTS attempts) — a concurrent writer (usage/verified update, sync) is active. Nothing was written; re-run."
fi
if (( cas_rc != 0 )); then
    die "Failed to write $METADATA_FILE. Nothing was written."
fi
if (( AIT_CAS_ATTEMPTS > 1 )); then
    info "$METADATA_FILE changed while merging; re-merged on the fresh content ($AIT_CAS_ATTEMPTS attempts)"
fi

unavailable_count=$(jq '
    .models | map(select(.status == "unavailable")) | length
' <<< "$merged")
total_count=$(jq '.models | length' <<< "$merged")
success "Updated $METADATA_FILE ($total_count models: $model_count active, $unavailable_count unavailable)"

# --- Sync to seed if requested ---
# The seed never carries stats counters (t1912_5): they live on the
# aitask-stats branch, and a fresh project must start without any.
#
# It is rendered from the bytes this run's guards checked (RENDERED_REGISTRY),
# never from a re-read of the live registry, which a concurrent writer may have
# changed since the swap. And it is published only while the registry still
# holds those bytes: otherwise a newer refresh that already wrote both files
# would have its seed overwritten by this older one. The compare runs AFTER the
# seed is staged and immediately before the rename (registry_unchanged, via
# ait_atomic_write_text_nofollow_if), so a refresh completing during staging is
# still caught; only the rename itself is left (without a lock it cannot be
# closed).
#
# Published with the nofollow writer: staged beside the seed (so the rename
# never degrades into a cross-filesystem copy a reader could see half-written)
# and never dereferencing the seed path itself. A symlink at
# seed/models_opencode.json is REPLACED, as the plain `mv` this replaces did;
# following it could overwrite its target — e.g. the live registry — with the
# stripped seed, dropping its counters.
registry_unchanged() {
    local live
    live="$(cat "$METADATA_FILE" 2>/dev/null)" || return 1
    [[ "$live" == "$RENDERED_REGISTRY" ]]
}

if [[ "$SYNC_SEED" == "true" ]]; then
    if [[ -d "seed" ]]; then
        seed_content=""
        seed_content="$(jq -f "$SCRIPT_DIR/lib/model_stats_strip.jq" <<< "$RENDERED_REGISTRY")" || seed_content=""
        if [[ -z "$seed_content" ]]; then
            warn "Could not render $SEED_FILE without stats counters — seed not synced"
        else
            seed_rc=0
            ait_atomic_write_text_nofollow_if "$SEED_FILE" "$seed_content" registry_unchanged || seed_rc=$?
            case "$seed_rc" in
                0) success "Synced to $SEED_FILE (stats counters stripped)" ;;
                3) warn "$METADATA_FILE changed after this refresh wrote it (a concurrent refresh or writer) — $SEED_FILE not synced; re-run with --sync-seed" ;;
                *) warn "Could not write $SEED_FILE — seed not synced" ;;
            esac
        fi
    else
        warn "seed/ directory not found — skipping seed sync"
    fi
fi
