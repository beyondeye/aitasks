#!/usr/bin/env bash
# aitask_crew_init.sh - Initialize an agentcrew: create branch, worktree, and metadata files.
#
# Usage: ait crew init --id <crew_id> [--name <display_name>] [--add-type <type_id>:<agent_string>] [--batch]
#
# Creates:
#   - Git branch crew-<id> from current HEAD
#   - Worktree at .aitask-crews/crew-<id>/
#   - _crew_meta.yaml (static configuration)
#   - _crew_status.yaml (dynamic state)
#
# Output: CREATED:<id>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/launch_modes_sh.sh
source "$SCRIPT_DIR/lib/launch_modes_sh.sh"
# shellcheck source=lib/agentcrew_utils.sh
source "$SCRIPT_DIR/lib/agentcrew_utils.sh"

# --- Defaults ---
CREW_ID=""
CREW_DISPLAY_NAME=""
# shellcheck disable=SC2034  # reserved for interactive mode
BATCH_MODE=false
declare -a ADD_TYPES=()

# --- Usage ---
show_help() {
    cat <<'HELP'
Usage: ait crew init --id <crew_id> [options]

Create a new agentcrew with its own git branch and worktree.

Required:
  --id <id>                 Crew identifier (lowercase alphanumeric, hyphens, underscores)

Options:
  --name <display_name>     Human-readable name (defaults to id)
  --add-type <id>:<agent>[:<launch_mode>]
                            Register an agent type (repeatable). Optional
                            third field sets launch_mode, one of:
                            headless, interactive, openshell_headless,
                            openshell_interactive.
                            Example: --add-type impl:claudecode/sonnet4_6
                                     --add-type detailer:claudecode/opus4_6:interactive
  --batch                   Non-interactive mode (no prompts)
  --help                    Show this help

Output (batch mode):
  CREATED:<id>              Crew successfully initialized

Example:
  ait crew init --id sprint1 --add-type impl:claudecode/opus4_6 --add-type review:claudecode/sonnet4_6:interactive --batch
HELP
}

# --- Argument parsing ---
# shellcheck disable=SC2034
while [[ $# -gt 0 ]]; do
    case "$1" in
        --id)
            [[ -z "${2:-}" ]] && die "--id requires a value"
            CREW_ID="$2"; shift 2 ;;
        --name)
            [[ -z "${2:-}" ]] && die "--name requires a value"
            CREW_DISPLAY_NAME="$2"; shift 2 ;;
        --add-type)
            [[ -z "${2:-}" ]] && die "--add-type requires a value in format type_id:agent_string[:launch_mode]"
            ADD_TYPES+=("$2"); shift 2 ;;
        --batch)
            BATCH_MODE=true; shift ;;
        --help|-h)
            show_help; exit 0 ;;
        *)
            die "Unknown option: $1. Run 'ait crew init --help' for usage." ;;
    esac
done

# --- Validation ---
[[ -z "$CREW_ID" ]] && die "Missing required --id. Run 'ait crew init --help' for usage."
validate_crew_id "$CREW_ID"

[[ -z "$CREW_DISPLAY_NAME" ]] && CREW_DISPLAY_NAME="$CREW_ID"

# Validate --add-type format
add_type_regex="^[a-z0-9_]+:[^:]+(:(${LAUNCH_MODES_PIPE}))?$"
for at in "${ADD_TYPES[@]+"${ADD_TYPES[@]}"}"; do
    if ! [[ "$at" =~ $add_type_regex ]]; then
        die "Invalid --add-type format '$at': expected type_id:agent_string[:launch_mode] (launch_mode one of: ${LAUNCH_MODES_PIPE//|/, })"
    fi
done

# --- Check branch doesn't already exist ---
BRANCH_NAME="$(crew_branch_name "$CREW_ID")"
WT_PATH="$(agentcrew_worktree_path "$CREW_ID")"

if git show-ref --verify "refs/heads/$BRANCH_NAME" &>/dev/null; then
    die "Branch '$BRANCH_NAME' already exists. Crew '$CREW_ID' may already be initialized."
fi

if [[ -d "$WT_PATH" ]]; then
    die "Worktree path '$WT_PATH' already exists."
fi

# --- Create branch and worktree ---
info "Creating agentcrew '$CREW_ID'..."

mkdir -p "$AGENTCREW_DIR"

# Create orphan branch with empty tree (no source code in crew worktrees)
empty_tree_hash=$(printf '' | git mktree)
commit_hash=$(echo "crew: Initialize agentcrew '$CREW_ID'" | git commit-tree "$empty_tree_hash")
git update-ref "refs/heads/$BRANCH_NAME" "$commit_hash"
git worktree add "$WT_PATH" "$BRANCH_NAME" --quiet

# --- Build agent_types YAML block ---
AGENT_TYPES_YAML=""
if [[ ${#ADD_TYPES[@]} -gt 0 ]]; then
    for at in "${ADD_TYPES[@]}"; do
        IFS=':' read -r local_type_id local_agent_string local_launch_mode <<< "$at"
        AGENT_TYPES_YAML="${AGENT_TYPES_YAML}  ${local_type_id}:
    agent_string: ${local_agent_string}
    max_parallel: 0
"
        if [[ -n "${local_launch_mode:-}" ]]; then
            AGENT_TYPES_YAML="${AGENT_TYPES_YAML}    launch_mode: ${local_launch_mode}
"
        fi
    done
fi

# --- Write _crew_meta.yaml ---
NOW="$(date -u '+%Y-%m-%d %H:%M:%S')"
USER_EMAIL=""
if [[ -f "aitasks/metadata/userconfig.yaml" ]]; then
    USER_EMAIL=$(grep '^email:' "aitasks/metadata/userconfig.yaml" 2>/dev/null | sed 's/^email:[[:space:]]*//' | head -n 1)
fi

META_CONTENT="id: ${CREW_ID}
name: ${CREW_DISPLAY_NAME}
created_at: ${NOW}
created_by: ${USER_EMAIL}
agents: []"

if [[ -n "$AGENT_TYPES_YAML" ]]; then
    META_CONTENT="${META_CONTENT}
agent_types:
${AGENT_TYPES_YAML}"
else
    META_CONTENT="${META_CONTENT}
agent_types: {}"
fi

write_yaml_file "$WT_PATH/_crew_meta.yaml" "$META_CONTENT"

# --- Write _crew_status.yaml ---
STATUS_CONTENT="status: ${CREW_STATUS_INITIALIZING}
progress: 0
started_at:
updated_at: ${NOW}"

write_yaml_file "$WT_PATH/_crew_status.yaml" "$STATUS_CONTENT"

# --- Commit in worktree ---
(
    cd "$WT_PATH"
    git add _crew_meta.yaml _crew_status.yaml
    git commit -m "crew: Initialize agentcrew '$CREW_ID'" --quiet
)

success "Agentcrew '$CREW_ID' initialized at $WT_PATH"
echo "CREATED:${CREW_ID}"
