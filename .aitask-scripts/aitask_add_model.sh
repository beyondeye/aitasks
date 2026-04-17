#!/usr/bin/env bash
# aitask_add_model.sh - Register a known code-agent model and optionally
# promote it to the operational default.
#
# Companion to aitask-refresh-code-models. refresh-code-models discovers
# models via web research and only writes the registry; this helper skips
# web research, takes known inputs, and can additionally promote the new
# model to default across codeagent_config.json + DEFAULT_AGENT_STRING.
#
# Subcommands:
#   add-json                       Append model entry to models_<agent>.json + seed
#   promote-config                 Update codeagent_config.json defaults for ops
#   promote-default-agent-string   Update DEFAULT_AGENT_STRING + resolution-chain
#                                  note in aitask_codeagent.sh (claudecode only)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/terminal_compat.sh"

REPO_ROOT="${AITASK_REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"

SUPPORTED_AGENTS=(claudecode geminicli codex)

# --- Common helpers ---

require_jq() {
    command -v jq >/dev/null 2>&1 || die "jq is required. Install via your package manager."
}

validate_agent() {
    local a="$1"
    [[ -z "$a" ]] && die "--agent is required"
    if [[ "$a" == "opencode" ]]; then
        die "Agent 'opencode' is not supported. Use aitask-refresh-code-models for opencode (models are provider-gated and CLI-discovered)."
    fi
    local v
    for v in "${SUPPORTED_AGENTS[@]}"; do
        [[ "$a" == "$v" ]] && return 0
    done
    die "Unknown agent: '$a'. Supported: ${SUPPORTED_AGENTS[*]} (opencode → use aitask-refresh-code-models)."
}

validate_name() {
    local n="$1"
    [[ -z "$n" ]] && die "--name is required"
    [[ "$n" =~ ^[a-z][a-z0-9_]*$ ]] || die "Invalid model name: '$n'. Must match ^[a-z][a-z0-9_]*\$ (lowercase alphanumerics and underscores, starting with a letter)."
}

validate_cli_id() {
    local id="$1"
    [[ -n "$id" ]] || die "--cli-id is required"
}

# Print a unified diff between `file` (pre-change) and the proposed content
# in `proposed`. Headers use the original path so users can spot it in
# dry-run output even though the proposed bytes sit in a tempfile.
print_diff() {
    local file="$1"
    local proposed="$2"
    if [[ -f "$file" ]]; then
        diff -u --label "a/$file" --label "b/$file" "$file" "$proposed" || true
    else
        diff -u --label "a/$file" --label "b/$file" /dev/null "$proposed" || true
    fi
}

# --- Subcommand: add-json ---

cmd_add_json() {
    local agent="" name="" cli_id="" notes="" dry_run=false
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --agent)   agent="$2"; shift 2 ;;
            --name)    name="$2"; shift 2 ;;
            --cli-id)  cli_id="$2"; shift 2 ;;
            --notes)   notes="$2"; shift 2 ;;
            --dry-run) dry_run=true; shift ;;
            *) die "Unknown argument to add-json: '$1'" ;;
        esac
    done

    validate_agent "$agent"
    validate_name "$name"
    validate_cli_id "$cli_id"

    local metadata_rel="aitasks/metadata/models_${agent}.json"
    local seed_rel="seed/models_${agent}.json"
    local metadata_file="$REPO_ROOT/$metadata_rel"
    local seed_file="$REPO_ROOT/$seed_rel"

    [[ -f "$metadata_file" ]] || die "Model registry not found: $metadata_rel"

    if jq -e --arg n "$name" 'any(.models[]?; .name == $n)' "$metadata_file" >/dev/null; then
        die "Model '$name' already exists in $metadata_rel"
    fi

    local tmp_metadata
    tmp_metadata=$(mktemp "${TMPDIR:-/tmp}/aitask_add_model_meta_XXXXXX.json")
    jq \
        --arg name "$name" \
        --arg cli_id "$cli_id" \
        --arg notes "$notes" \
        '.models += [{
            "name": $name,
            "cli_id": $cli_id,
            "notes": $notes,
            "verified": {},
            "verifiedstats": {}
        }]' \
        "$metadata_file" > "$tmp_metadata"
    jq . "$tmp_metadata" >/dev/null || { rm -f "$tmp_metadata"; die "Produced JSON is invalid for $metadata_rel"; }

    local tmp_seed=""
    if [[ -f "$seed_file" ]]; then
        if jq -e --arg n "$name" 'any(.models[]?; .name == $n)' "$seed_file" >/dev/null; then
            rm -f "$tmp_metadata"
            die "Model '$name' already exists in $seed_rel"
        fi
        tmp_seed=$(mktemp "${TMPDIR:-/tmp}/aitask_add_model_seed_XXXXXX.json")
        jq \
            --arg name "$name" \
            --arg cli_id "$cli_id" \
            --arg notes "$notes" \
            '.models += [{
                "name": $name,
                "cli_id": $cli_id,
                "notes": $notes,
                "verified": {},
                "verifiedstats": {}
            }]' \
            "$seed_file" > "$tmp_seed"
        jq . "$tmp_seed" >/dev/null || { rm -f "$tmp_metadata" "$tmp_seed"; die "Produced JSON is invalid for $seed_rel"; }
    fi

    if $dry_run; then
        print_diff "$metadata_rel" "$tmp_metadata"
        [[ -n "$tmp_seed" ]] && print_diff "$seed_rel" "$tmp_seed"
        rm -f "$tmp_metadata" "$tmp_seed"
        return 0
    fi

    mv "$tmp_metadata" "$metadata_file"
    [[ -n "$tmp_seed" ]] && mv "$tmp_seed" "$seed_file"
    info "Added model $agent/$name to $metadata_rel${tmp_seed:+ (+ $seed_rel)}"
}

# --- Subcommand: promote-config ---

cmd_promote_config() {
    local agent="" name="" ops_csv="" dry_run=false
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --agent)   agent="$2"; shift 2 ;;
            --name)    name="$2"; shift 2 ;;
            --ops)     ops_csv="$2"; shift 2 ;;
            --dry-run) dry_run=true; shift ;;
            *) die "Unknown argument to promote-config: '$1'" ;;
        esac
    done

    validate_agent "$agent"
    validate_name "$name"
    [[ -z "$ops_csv" ]] && die "--ops is required (comma-separated)"

    local metadata_rel="aitasks/metadata/codeagent_config.json"
    local seed_rel="seed/codeagent_config.json"
    local metadata_file="$REPO_ROOT/$metadata_rel"
    local seed_file="$REPO_ROOT/$seed_rel"

    [[ -f "$metadata_file" ]] || die "Config not found: $metadata_rel"

    local new_value="${agent}/${name}"
    local ops_json
    ops_json=$(printf '%s' "$ops_csv" | jq -R -c 'split(",")')

    # Only patch keys that already exist. Missing keys are silently skipped
    # per-file — e.g. seed has only the canonical 6 ops, so brainstorm-* keys
    # are skipped in seed without failing the command.
    local tmp_metadata
    tmp_metadata=$(mktemp "${TMPDIR:-/tmp}/aitask_add_model_cfg_XXXXXX.json")
    jq \
        --argjson ops "$ops_json" \
        --arg new_value "$new_value" \
        '
        reduce $ops[] as $op (.;
            if (.defaults // {}) | has($op) then .defaults[$op] = $new_value else . end
        )
        ' "$metadata_file" > "$tmp_metadata"
    jq . "$tmp_metadata" >/dev/null || { rm -f "$tmp_metadata"; die "Produced JSON is invalid for $metadata_rel"; }

    local tmp_seed=""
    if [[ -f "$seed_file" ]]; then
        tmp_seed=$(mktemp "${TMPDIR:-/tmp}/aitask_add_model_cfg_seed_XXXXXX.json")
        jq \
            --argjson ops "$ops_json" \
            --arg new_value "$new_value" \
            '
            reduce $ops[] as $op (.;
                if (.defaults // {}) | has($op) then .defaults[$op] = $new_value else . end
            )
            ' "$seed_file" > "$tmp_seed"
        jq . "$tmp_seed" >/dev/null || { rm -f "$tmp_metadata" "$tmp_seed"; die "Produced JSON is invalid for $seed_rel"; }
    fi

    if $dry_run; then
        print_diff "$metadata_rel" "$tmp_metadata"
        [[ -n "$tmp_seed" ]] && print_diff "$seed_rel" "$tmp_seed"
        rm -f "$tmp_metadata" "$tmp_seed"
        return 0
    fi

    mv "$tmp_metadata" "$metadata_file"
    [[ -n "$tmp_seed" ]] && mv "$tmp_seed" "$seed_file"
    info "Promoted $new_value for ops: $ops_csv"
}

# --- Subcommand: promote-default-agent-string ---

cmd_promote_default_agent_string() {
    local agent="" name="" dry_run=false
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --agent)   agent="$2"; shift 2 ;;
            --name)    name="$2"; shift 2 ;;
            --dry-run) dry_run=true; shift ;;
            *) die "Unknown argument to promote-default-agent-string: '$1'" ;;
        esac
    done

    validate_agent "$agent"
    validate_name "$name"

    if [[ "$agent" != "claudecode" ]]; then
        die "promote-default-agent-string only supports agent 'claudecode' (got '$agent'). Other agents do not have a hardcoded DEFAULT_AGENT_STRING."
    fi

    local src_rel=".aitask-scripts/aitask_codeagent.sh"
    local src_file="$REPO_ROOT/$src_rel"
    [[ -f "$src_file" ]] || die "Source file not found: $src_rel"

    local new_value="${agent}/${name}"

    local tmp_src
    tmp_src=$(mktemp "${TMPDIR:-/tmp}/aitask_add_model_src_XXXXXX.sh")
    cp "$src_file" "$tmp_src"

    sed_inplace "s|^DEFAULT_AGENT_STRING=\".*\"|DEFAULT_AGENT_STRING=\"${new_value}\"|" "$tmp_src"
    sed_inplace "s|^\(  4\. Hardcoded default: \).*|\1${new_value}|" "$tmp_src"

    if ! grep -q "^DEFAULT_AGENT_STRING=\"${new_value}\"$" "$tmp_src"; then
        rm -f "$tmp_src"
        die "Failed to update DEFAULT_AGENT_STRING in $src_rel (anchor pattern did not match)"
    fi
    if ! grep -q "^  4\. Hardcoded default: ${new_value}$" "$tmp_src"; then
        rm -f "$tmp_src"
        die "Failed to update resolution-chain note in $src_rel (anchor pattern did not match)"
    fi

    if $dry_run; then
        print_diff "$src_rel" "$tmp_src"
        rm -f "$tmp_src"
        return 0
    fi

    # Preserve the source file's mode (executable bit) by rewriting content
    # in place instead of `mv`-ing a non-executable tempfile over it.
    cat "$tmp_src" > "$src_file"
    rm -f "$tmp_src"
    info "Updated DEFAULT_AGENT_STRING to $new_value in $src_rel"
}

# --- Main dispatcher ---

usage() {
    cat <<'EOF'
Usage: aitask_add_model.sh <subcommand> [options]

Subcommands:
  add-json                     --agent <a> --name <n> --cli-id <id> --notes <s> [--dry-run]
  promote-config               --agent <a> --name <n> --ops <csv>             [--dry-run]
  promote-default-agent-string --agent <a> --name <n>                         [--dry-run]

Supported agents: claudecode, geminicli, codex.
Use aitask-refresh-code-models for opencode (provider-gated, CLI-discovered).

--dry-run prints a unified diff and exits without writing any file.

The AITASK_REPO_ROOT env var overrides the repo root used for file
resolution (defaults to the parent dir of .aitask-scripts). This is used
by tests to run against isolated fixtures.
EOF
}

main() {
    require_jq
    local cmd="${1:-}"
    shift || true
    case "$cmd" in
        add-json)                     cmd_add_json "$@" ;;
        promote-config)               cmd_promote_config "$@" ;;
        promote-default-agent-string) cmd_promote_default_agent_string "$@" ;;
        ""|help|-h|--help)            usage ;;
        *)                            die "Unknown subcommand: '$cmd' (see --help)" ;;
    esac
}

main "$@"
