#!/usr/bin/env bash
# agentcrew_utils.sh - Shared utility functions for the AgentCrew infrastructure.
# Provides constants, validation, crew resolution, YAML helpers, and DAG cycle detection.

# --- Guard against double-sourcing ---
[[ -n "${_AIT_AGENTCREW_UTILS_LOADED:-}" ]] && return 0
_AIT_AGENTCREW_UTILS_LOADED=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=terminal_compat.sh
source "$SCRIPT_DIR/terminal_compat.sh"

# --- Constants ---
AGENTCREW_BRANCH_PREFIX="crew-"
AGENTCREW_DIR=".aitask-crews"

# --- Status constants (used by downstream scripts: crew_status, crew_runner) ---
# shellcheck disable=SC2034
{
AGENT_STATUS_WAITING="Waiting"
AGENT_STATUS_RUNNING="Running"
AGENT_STATUS_MISSED_HEARTBEAT="MissedHeartbeat"
AGENT_STATUS_COMPLETED="Completed"
AGENT_STATUS_ABORTED="Aborted"
AGENT_STATUS_READY="Ready"
AGENT_STATUS_ERROR="Error"
AGENT_STATUS_PAUSED="Paused"

CREW_STATUS_INITIALIZING="Initializing"
CREW_STATUS_RUNNING="Running"
CREW_STATUS_COMPLETED="Completed"
CREW_STATUS_KILLING="Killing"
CREW_STATUS_PAUSED="Paused"
CREW_STATUS_ERROR="Error"
}

# crew_branch_name <crew_id>
# Returns the git branch name for an agentcrew.
crew_branch_name() {
    local crew_id="$1"
    echo "${AGENTCREW_BRANCH_PREFIX}${crew_id}"
}

# agentcrew_worktree_path <crew_id>
# Returns the worktree filesystem path for an agentcrew.
agentcrew_worktree_path() {
    local crew_id="$1"
    echo "${AGENTCREW_DIR}/crew-${crew_id}"
}

# validate_crew_id <id>
# Validates that a crew ID matches [a-z0-9_-]+. Dies on failure.
validate_crew_id() {
    local id="$1"
    if [[ -z "$id" ]]; then
        die "Crew ID cannot be empty"
    fi
    if ! [[ "$id" =~ ^[a-z0-9_-]+$ ]]; then
        die "Invalid crew ID '$id': must match [a-z0-9_-]+"
    fi
}

# validate_agent_name <name>
# Validates that an agent name matches [a-z0-9_]+. Dies on failure.
validate_agent_name() {
    local name="$1"
    if [[ -z "$name" ]]; then
        die "Agent name cannot be empty"
    fi
    if ! [[ "$name" =~ ^[a-z0-9_]+$ ]]; then
        die "Invalid agent name '$name': must match [a-z0-9_]+"
    fi
}

# resolve_crew <crew_id>
# Verifies the agentcrew worktree exists and echoes its path. Dies if not found.
resolve_crew() {
    local crew_id="$1"
    local wt_path
    wt_path="$(agentcrew_worktree_path "$crew_id")"
    if [[ ! -d "$wt_path" ]]; then
        die "Crew '$crew_id' not found: worktree '$wt_path' does not exist"
    fi
    echo "$wt_path"
}

# read_yaml_field <file> <field>
# Extracts a simple scalar value from a YAML file (grep+sed).
# Returns empty string if field not found. Safe under pipefail.
read_yaml_field() {
    local file="$1"
    local field="$2"
    { grep "^${field}:" "$file" 2>/dev/null || true; } | sed "s/^${field}:[[:space:]]*//" | head -n 1
}

# read_yaml_list <file> <field>
# Extracts a YAML list field as newline-separated values.
# Handles both inline [a, b] and block list formats.
read_yaml_list() {
    local file="$1"
    local field="$2"

    local line
    line=$({ grep "^${field}:" "$file" 2>/dev/null || true; } | head -n 1)
    [[ -z "$line" ]] && return 0

    local value
    value=$(echo "$line" | sed "s/^${field}:[[:space:]]*//")

    # Inline format: [a, b, c]
    if [[ "$value" =~ ^\[.*\]$ ]]; then
        echo "$value" | tr -d "[]'\"" | tr ',' '\n' | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//' | grep -v '^$'
        return 0
    fi

    # Block format: lines starting with "- "
    local in_list=false
    while IFS= read -r fline; do
        if [[ "$fline" == "${field}:"* ]]; then
            in_list=true
            continue
        fi
        if $in_list; then
            if [[ "$fline" =~ ^[[:space:]]*-[[:space:]] ]]; then
                echo "$fline" | sed 's/^[[:space:]]*-[[:space:]]*//'
            else
                break
            fi
        fi
    done < "$file"
}

# write_yaml_file <file> <content>
# Writes YAML content to a file via heredoc (content passed as string).
write_yaml_file() {
    local file="$1"
    local content="$2"
    printf '%s\n' "$content" > "$file"
}

# resolve_template_includes <base_dir>
# Reads template content from stdin, writes resolved content to stdout.
# Resolves <!-- include: filename --> directives relative to base_dir.
# One-level only (included files are not scanned for further includes).
# Missing includes emit a warning and preserve the directive line as-is.
resolve_template_includes() {
    local base_dir="$1"
    local line
    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$line" =~ \<\!--[[:space:]]+include:[[:space:]]+([^[:space:]]+)[[:space:]]+--\> ]]; then
            local inc_file="$base_dir/${BASH_REMATCH[1]}"
            if [[ -f "$inc_file" ]]; then
                cat "$inc_file"
            else
                warn "Template include not found: $inc_file"
                printf '%s\n' "$line"
            fi
        else
            printf '%s\n' "$line"
        fi
    done
}

# append_yaml_list_item <file> <field> <value>
# Appends a value to a YAML inline list field [a, b] -> [a, b, c].
# If the field has an empty list [], sets it to [value].
append_yaml_list_item() {
    local file="$1"
    local field="$2"
    local value="$3"

    local current
    current=$({ grep "^${field}:" "$file" 2>/dev/null || true; } | head -n 1)

    if [[ -z "$current" ]]; then
        # Field doesn't exist, append it
        echo "${field}: [${value}]" >> "$file"
        return 0
    fi

    local list_content
    list_content=$(echo "$current" | sed "s/^${field}:[[:space:]]*//" | tr -d "[]'\"" | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')

    local new_line
    if [[ -z "$list_content" ]]; then
        new_line="${field}: [${value}]"
    else
        new_line="${field}: [${list_content}, ${value}]"
    fi

    # Replace the line in-place
    local tmpfile
    tmpfile=$(mktemp "${TMPDIR:-/tmp}/ait_yaml_XXXXXX")
    while IFS= read -r line; do
        if [[ "$line" == "${field}:"* ]]; then
            echo "$new_line"
        else
            echo "$line"
        fi
    done < "$file" > "$tmpfile"
    mv "$tmpfile" "$file"
}

# detect_circular_deps <worktree_path> [new_agent_name] [new_agent_deps_csv]
# DFS cycle detection across all *_status.yaml files in the worktree.
# If new_agent_name and new_agent_deps_csv are provided, includes them
# as a proposed (not yet created) agent for pre-validation.
# Returns 0 if no cycle, exits with die() if cycle found.
detect_circular_deps() {
    local wt_path="$1"
    local new_name="${2:-}"
    local new_deps_csv="${3:-}"

    # Build adjacency list: agent -> deps (space-separated)
    # Using associative array (bash 4+)
    declare -A adj
    declare -A all_agents

    # Read existing agents from status files (skip _crew_status.yaml)
    local status_file agent_name
    for status_file in "$wt_path"/*_status.yaml; do
        [[ -f "$status_file" ]] || continue
        # Skip crew-level status file
        [[ "$(basename "$status_file")" == "_crew_status.yaml" ]] && continue
        agent_name=$(read_yaml_field "$status_file" "agent_name")
        [[ -z "$agent_name" ]] && continue
        all_agents["$agent_name"]=1

        local deps_str
        deps_str=$(read_yaml_list "$status_file" "depends_on" | tr '\n' ' ')
        adj["$agent_name"]="${deps_str:-}"
    done

    # Add proposed new agent if provided
    if [[ -n "$new_name" ]]; then
        all_agents["$new_name"]=1
        if [[ -n "$new_deps_csv" ]]; then
            adj["$new_name"]=$(echo "$new_deps_csv" | tr ',' ' ')
        else
            adj["$new_name"]=""
        fi
    fi

    # DFS cycle detection
    # States: 0=unvisited, 1=in-progress, 2=done
    declare -A state
    local agent
    for agent in "${!all_agents[@]}"; do
        state["$agent"]=0
    done

    # Recursive DFS via stack (to avoid bash recursion limits)
    _dfs_check_cycle() {
        local start="$1"
        local -a stack=("$start")
        local -a path=()
        local -A on_path

        while [[ ${#stack[@]} -gt 0 ]]; do
            local current="${stack[-1]}"
            unset 'stack[-1]'
            stack=("${stack[@]}")

            if [[ "${state[$current]:-0}" -eq 2 ]]; then
                continue
            fi

            if [[ "${on_path[$current]:-0}" -eq 1 ]]; then
                # Backtrack: mark done and remove from path
                state["$current"]=2
                on_path["$current"]=0
                if [[ ${#path[@]} -gt 0 ]]; then
                    unset 'path[-1]'
                    path=("${path[@]}")
                fi
                continue
            fi

            state["$current"]=1
            on_path["$current"]=1
            path+=("$current")

            # Push backtrack marker
            stack+=("$current")

            # Push dependencies
            local dep
            for dep in ${adj[$current]:-}; do
                if [[ "${on_path[$dep]:-0}" -eq 1 ]]; then
                    die "Circular dependency detected: ${path[*]} -> $dep"
                fi
                if [[ "${state[$dep]:-0}" -eq 0 ]]; then
                    stack+=("$dep")
                fi
            done
        done
    }

    for agent in "${!all_agents[@]}"; do
        if [[ "${state[$agent]}" -eq 0 ]]; then
            _dfs_check_cycle "$agent"
        fi
    done

    return 0
}
