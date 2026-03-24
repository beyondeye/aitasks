#!/usr/bin/env bash
# aitask_crew_addwork.sh - Register a new agent (subagent) in an existing agentcrew.
#
# Usage: ait crew addwork --crew <id> --name <agent_name> --work2do <file> --type <type_id> [--depends <a,b>] [--batch]
#
# Creates 7 agent files in the crew worktree:
#   <name>_work2do.md, <name>_status.yaml, <name>_input.md, <name>_output.md,
#   <name>_instructions.md, <name>_commands.yaml, <name>_alive.yaml
#
# Output: ADDED:<name>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/agentcrew_utils.sh
source "$SCRIPT_DIR/lib/agentcrew_utils.sh"

# --- Defaults ---
CREW_ID=""
AGENT_NAME=""
WORK2DO_FILE=""
DEPENDS_CSV=""
AGENT_TYPE=""
GROUP=""
# shellcheck disable=SC2034  # reserved for interactive mode
BATCH_MODE=false

# --- Usage ---
show_help() {
    cat <<'HELP'
Usage: ait crew addwork --crew <id> --name <agent_name> --work2do <file> --type <type_id> [options]

Register a new agent in an agentcrew. Creates all agent coordination files.

Required:
  --crew <id>               Crew identifier
  --name <agent_name>       Agent name (lowercase alphanumeric, underscores)
  --work2do <file>          Path to the work-to-do markdown file (or "-" for stdin)
  --type <type_id>          Agent type ID (must exist in crew's agent_types)

Options:
  --depends <a,b>           Comma-separated list of agent names this agent depends on
  --group <name>            Operation group name (e.g. explore_001)
  --batch                   Non-interactive mode (no prompts)
  --help                    Show this help

Output (batch mode):
  ADDED:<name>              Agent successfully registered

Example:
  ait crew addwork --crew sprint1 --name planner --work2do tasks/plan.md --type impl --batch
  ait crew addwork --crew sprint1 --name coder --work2do tasks/code.md --type impl --depends planner --batch
HELP
}

# --- Argument parsing ---
# shellcheck disable=SC2034
while [[ $# -gt 0 ]]; do
    case "$1" in
        --crew)
            [[ -z "${2:-}" ]] && die "--crew requires a value"
            CREW_ID="$2"; shift 2 ;;
        --name)
            [[ -z "${2:-}" ]] && die "--name requires a value"
            AGENT_NAME="$2"; shift 2 ;;
        --work2do)
            [[ -z "${2:-}" ]] && die "--work2do requires a value"
            WORK2DO_FILE="$2"; shift 2 ;;
        --depends)
            [[ -z "${2:-}" ]] && die "--depends requires a value"
            DEPENDS_CSV="$2"; shift 2 ;;
        --type)
            [[ -z "${2:-}" ]] && die "--type requires a value"
            AGENT_TYPE="$2"; shift 2 ;;
        --group)
            [[ -z "${2:-}" ]] && die "--group requires a value"
            GROUP="$2"; shift 2 ;;
        --batch)
            BATCH_MODE=true; shift ;;
        --help|-h)
            show_help; exit 0 ;;
        *)
            die "Unknown option: $1. Run 'ait crew addwork --help' for usage." ;;
    esac
done

# --- Validation ---
[[ -z "$CREW_ID" ]] && die "Missing required --crew. Run 'ait crew addwork --help' for usage."
[[ -z "$AGENT_NAME" ]] && die "Missing required --name. Run 'ait crew addwork --help' for usage."
[[ -z "$WORK2DO_FILE" ]] && die "Missing required --work2do. Run 'ait crew addwork --help' for usage."
[[ -z "$AGENT_TYPE" ]] && die "Missing required --type. Run 'ait crew addwork --help' for usage."

validate_crew_id "$CREW_ID"
validate_agent_name "$AGENT_NAME"

# Resolve crew worktree
WT_PATH="$(resolve_crew "$CREW_ID")"

# Check agent name uniqueness
if [[ -f "$WT_PATH/${AGENT_NAME}_status.yaml" ]]; then
    die "Agent '$AGENT_NAME' already exists in crew '$CREW_ID'"
fi

# Validate agent type exists in _crew_meta.yaml
META_FILE="$WT_PATH/_crew_meta.yaml"
if [[ ! -f "$META_FILE" ]]; then
    die "Crew meta file not found: $META_FILE"
fi

# Check type exists under agent_types: block
if ! grep -q "^  ${AGENT_TYPE}:" "$META_FILE"; then
    available=$({ grep -E '^  [a-z0-9_]+:' "$META_FILE" || true; } | sed 's/://' | sed 's/^  //' | tr '\n' ', ' | sed 's/,$//')
    die "Agent type '$AGENT_TYPE' not found in crew '$CREW_ID'. Available types: $available"
fi

# Validate dependencies exist
if [[ -n "$DEPENDS_CSV" ]]; then
    IFS=',' read -ra DEPS <<< "$DEPENDS_CSV"
    for dep in "${DEPS[@]}"; do
        dep="$(echo "$dep" | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')"
        if [[ ! -f "$WT_PATH/${dep}_status.yaml" ]]; then
            die "Dependency agent '$dep' not found in crew '$CREW_ID'"
        fi
    done
fi

# Check for circular dependencies
detect_circular_deps "$WT_PATH" "$AGENT_NAME" "$DEPENDS_CSV"

# --- Read work2do content ---
WORK2DO_CONTENT=""
if [[ "$WORK2DO_FILE" == "-" ]]; then
    WORK2DO_CONTENT="$(cat)"
elif [[ "$WORK2DO_FILE" == "/dev/null" ]]; then
    WORK2DO_CONTENT=""
else
    if [[ ! -f "$WORK2DO_FILE" ]]; then
        die "Work2do file not found: $WORK2DO_FILE"
    fi
    WORK2DO_CONTENT="$(cat "$WORK2DO_FILE")"
fi

# --- Create agent files ---
info "Adding agent '$AGENT_NAME' to crew '$CREW_ID'..."

NOW="$(date -u '+%Y-%m-%d %H:%M:%S')"

# Build depends_on YAML
DEPENDS_YAML="[]"
if [[ -n "$DEPENDS_CSV" ]]; then
    DEPENDS_YAML="[$(echo "$DEPENDS_CSV" | sed 's/,/, /g')]"
fi

# 1. <name>_work2do.md
write_yaml_file "$WT_PATH/${AGENT_NAME}_work2do.md" "$WORK2DO_CONTENT"

# 2. <name>_status.yaml
STATUS_CONTENT="agent_name: ${AGENT_NAME}
agent_type: ${AGENT_TYPE}
group: ${GROUP}
status: ${AGENT_STATUS_WAITING}
depends_on: ${DEPENDS_YAML}
created_at: ${NOW}
started_at:
completed_at:
progress: 0
pid:
error_message:"

write_yaml_file "$WT_PATH/${AGENT_NAME}_status.yaml" "$STATUS_CONTENT"

# 3. <name>_input.md
write_yaml_file "$WT_PATH/${AGENT_NAME}_input.md" "# Input for agent: ${AGENT_NAME}

This file is populated by the crew runner or upstream agents before this agent starts."

# 4. <name>_output.md
write_yaml_file "$WT_PATH/${AGENT_NAME}_output.md" "# Output from agent: ${AGENT_NAME}

This file is populated by the agent during/after execution."

# 5. <name>_instructions.md
write_yaml_file "$WT_PATH/${AGENT_NAME}_instructions.md" "# Lifecycle Instructions for agent: ${AGENT_NAME}

## Status Updates
Call the crew status update script to report your status:
\`\`\`bash
ait crew status --crew ${CREW_ID} --agent ${AGENT_NAME} set --status <status>
\`\`\`
Valid statuses: Running, Completed, Aborted, Error

## Progress Reporting
Update your progress (0-100):
\`\`\`bash
ait crew status --crew ${CREW_ID} --agent ${AGENT_NAME} set --progress <N>
\`\`\`

## Heartbeat / Alive Signal
Periodically write to your alive file to signal you are active:
\`\`\`bash
ait crew status --crew ${CREW_ID} --agent ${AGENT_NAME} heartbeat
\`\`\`

## Reading Commands
Check for intra-run commands (e.g., force stop):
\`\`\`bash
ait crew command list --crew ${CREW_ID} --agent ${AGENT_NAME}
\`\`\`

## Writing Output
Write your results to: ${AGENT_NAME}_output.md

## Checkpoints
At each checkpoint in your work2do flow:
1. Send heartbeat
2. Check for pending commands
3. Update progress
4. If a 'kill' command is received, run your abort procedure and set status to Aborted"

# 6. <name>_commands.yaml
write_yaml_file "$WT_PATH/${AGENT_NAME}_commands.yaml" "pending_commands: []"

# 7. <name>_alive.yaml
write_yaml_file "$WT_PATH/${AGENT_NAME}_alive.yaml" "last_heartbeat:
last_message:"

# --- Update _crew_meta.yaml agents list ---
append_yaml_list_item "$META_FILE" "agents" "$AGENT_NAME"

# --- Update _groups.yaml if --group was provided ---
GROUPS_FILE="$WT_PATH/_groups.yaml"
GIT_ADD_GROUPS=""
if [[ -n "$GROUP" ]]; then
    if [[ ! -f "$GROUPS_FILE" ]]; then
        write_yaml_file "$GROUPS_FILE" "groups: []"
    fi
    # Check if group already exists
    if ! grep -q "name: ${GROUP}" "$GROUPS_FILE" 2>/dev/null; then
        # Compute next sequence number
        NEXT_SEQ=1
        LAST_SEQ=$({ grep 'sequence:' "$GROUPS_FILE" || true; } | tail -1 | sed 's/.*sequence:[[:space:]]*//' | tr -d ' ')
        if [[ -n "$LAST_SEQ" ]]; then
            NEXT_SEQ=$((LAST_SEQ + 1))
        fi
        GROUP_NOW="$(date -u '+%Y-%m-%d %H:%M:%S')"
        # Append group entry (replace empty list or append to existing)
        if grep -q 'groups: \[\]' "$GROUPS_FILE" 2>/dev/null; then
            # Replace empty list with first entry
            tmpfile="$(mktemp "${TMPDIR:-/tmp}/groups_XXXXXX")"
            cat > "$tmpfile" <<GROUPEOF
groups:
- name: ${GROUP}
  sequence: ${NEXT_SEQ}
  description: ''
  created_at: '${GROUP_NOW}'
GROUPEOF
            mv "$tmpfile" "$GROUPS_FILE"
        else
            # Append new group entry
            cat >> "$GROUPS_FILE" <<GROUPEOF
- name: ${GROUP}
  sequence: ${NEXT_SEQ}
  description: ''
  created_at: '${GROUP_NOW}'
GROUPEOF
        fi
    fi
    GIT_ADD_GROUPS="_groups.yaml"
fi

# --- Commit in worktree ---
(
    cd "$WT_PATH"
    # shellcheck disable=SC2086
    git add "${AGENT_NAME}_work2do.md" "${AGENT_NAME}_status.yaml" \
            "${AGENT_NAME}_input.md" "${AGENT_NAME}_output.md" \
            "${AGENT_NAME}_instructions.md" "${AGENT_NAME}_commands.yaml" \
            "${AGENT_NAME}_alive.yaml" "_crew_meta.yaml" $GIT_ADD_GROUPS
    git commit -m "crew: Add agent '${AGENT_NAME}' to crew '${CREW_ID}'" --quiet
    git pull --rebase --quiet 2>/dev/null || true
    git push --quiet 2>/dev/null || warn "git push failed (offline?)"
)

success "Agent '$AGENT_NAME' added to crew '$CREW_ID'"
echo "ADDED:${AGENT_NAME}"
