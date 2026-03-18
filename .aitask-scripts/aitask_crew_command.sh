#!/usr/bin/env bash
# aitask_crew_command.sh - Send commands to agents in an agentcrew.
#
# Usage: ait crew command <send|send-all|list|ack> --crew <id> --agent <name> [options]
#
# Commands are written to <agent>_commands.yaml in the crew worktree.
# Valid commands: kill, pause, resume, update_instructions
#
# Output:
#   COMMAND_SENT:<cmd>        Command appended to agent's pending queue
#   COMMANDS_ACKED:<agent>    Pending commands cleared
#   NO_COMMANDS               No pending commands found

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/agentcrew_utils.sh
source "$SCRIPT_DIR/lib/agentcrew_utils.sh"

# --- Valid commands ---
VALID_COMMANDS="kill pause resume update_instructions"

# --- Defaults ---
CREW_ID=""
AGENT_NAME=""
COMMAND=""
SENT_BY="user"
GROUP_NAME=""
SUBCMD=""

# --- Usage ---
show_help() {
    cat <<'HELP'
Usage: ait crew command <sub-command> --crew <id> [options]

Send commands to agents in an agentcrew.

Sub-commands:
  send        Send a command to a specific agent
  send-all    Send a command to all Running agents
  send-group  Send a command to all agents in a group
  list        List pending commands for an agent
  ack         Acknowledge (clear) pending commands for an agent

Options:
  --crew <id>             Crew identifier (required)
  --agent <name>          Agent name (required for send, list, ack)
  --group <name>          Group name (required for send-group)
  --command <cmd>         Command to send (required for send, send-all, send-group)
                          Valid: kill, pause, resume, update_instructions
  --sent-by <who>         Who sent the command: runner|user (default: user)
  --help                  Show this help

Output (batch mode):
  COMMAND_SENT:<cmd>      Command sent to agent
  COMMANDS_ACKED:<agent>  Pending commands cleared
  NO_COMMANDS             No pending commands

Examples:
  ait crew command send --crew sprint1 --agent worker1 --command kill
  ait crew command send-all --crew sprint1 --command pause
  ait crew command list --crew sprint1 --agent worker1
  ait crew command ack --crew sprint1 --agent worker1
HELP
}

# --- Argument parsing ---
# First argument is the sub-command
SUBCMD="${1:-}"
if [[ -z "$SUBCMD" ]]; then
    show_help
    exit 1
fi
shift

case "$SUBCMD" in
    send|send-all|send-group|list|ack) ;;
    --help|-h) show_help; exit 0 ;;
    *) die "Unknown sub-command: $SUBCMD. Valid: send, send-all, send-group, list, ack" ;;
esac

while [[ $# -gt 0 ]]; do
    case "$1" in
        --crew)
            [[ -z "${2:-}" ]] && die "--crew requires a value"
            CREW_ID="$2"; shift 2 ;;
        --agent)
            [[ -z "${2:-}" ]] && die "--agent requires a value"
            AGENT_NAME="$2"; shift 2 ;;
        --command)
            [[ -z "${2:-}" ]] && die "--command requires a value"
            COMMAND="$2"; shift 2 ;;
        --group)
            [[ -z "${2:-}" ]] && die "--group requires a value"
            GROUP_NAME="$2"; shift 2 ;;
        --sent-by)
            [[ -z "${2:-}" ]] && die "--sent-by requires a value"
            SENT_BY="$2"; shift 2 ;;
        --help|-h)
            show_help; exit 0 ;;
        *)
            die "Unknown option: $1" ;;
    esac
done

# --- Validation ---
[[ -z "$CREW_ID" ]] && die "Missing required --crew. Run 'ait crew command --help' for usage."
validate_crew_id "$CREW_ID"

WT_PATH="$(resolve_crew "$CREW_ID")"

# Validate command value
validate_command() {
    local cmd="$1"
    local found=false
    for valid in $VALID_COMMANDS; do
        if [[ "$cmd" == "$valid" ]]; then
            found=true
            break
        fi
    done
    if ! $found; then
        die "Invalid command '$cmd'. Valid: $VALID_COMMANDS"
    fi
}

# --- Timestamp ---
get_utc_timestamp() {
    date -u '+%Y-%m-%d %H:%M:%S'
}

# --- Sub-command: send ---
cmd_send() {
    [[ -z "$AGENT_NAME" ]] && die "Missing required --agent for 'send'. Run 'ait crew command --help' for usage."
    [[ -z "$COMMAND" ]] && die "Missing required --command for 'send'. Run 'ait crew command --help' for usage."
    validate_agent_name "$AGENT_NAME"
    validate_command "$COMMAND"

    local cmd_file="$WT_PATH/${AGENT_NAME}_commands.yaml"
    if [[ ! -f "$cmd_file" ]]; then
        die "Agent '$AGENT_NAME' commands file not found in crew '$CREW_ID'"
    fi

    local ts
    ts="$(get_utc_timestamp)"

    # Check if file has existing block-style entries (lines starting with "- command:")
    local has_entries=false
    if { grep -q '^- command:' "$cmd_file" 2>/dev/null || false; }; then
        has_entries=true
    fi

    local tmpfile
    tmpfile=$(mktemp "${TMPDIR:-/tmp}/ait_cmd_XXXXXX.yaml")

    if $has_entries; then
        # Append to existing block-style list
        cp "$cmd_file" "$tmpfile"
        cat >> "$tmpfile" <<EOF
- command: ${COMMAND}
  sent_at: '${ts}'
  sent_by: ${SENT_BY}
EOF
    else
        # Start fresh block-style list (replaces "pending_commands: []")
        cat > "$tmpfile" <<EOF
pending_commands:
- command: ${COMMAND}
  sent_at: '${ts}'
  sent_by: ${SENT_BY}
EOF
    fi

    mv "$tmpfile" "$cmd_file"
    echo "COMMAND_SENT:${COMMAND}"
}

# --- Sub-command: send-all ---
cmd_send_all() {
    [[ -z "$COMMAND" ]] && die "Missing required --command for 'send-all'. Run 'ait crew command --help' for usage."
    validate_command "$COMMAND"

    local count=0
    local status_file agent_name agent_status

    for status_file in "$WT_PATH"/*_status.yaml; do
        [[ -f "$status_file" ]] || continue
        [[ "$(basename "$status_file")" == "_crew_status.yaml" ]] && continue

        agent_name=$(read_yaml_field "$status_file" "agent_name")
        [[ -z "$agent_name" ]] && continue

        agent_status=$(read_yaml_field "$status_file" "status")
        if [[ "$agent_status" == "Running" ]]; then
            AGENT_NAME="$agent_name"
            cmd_send
            count=$((count + 1))
        fi
    done

    if [[ $count -eq 0 ]]; then
        info "No Running agents found in crew '$CREW_ID'"
    fi
}

# --- Sub-command: send-group ---
cmd_send_group() {
    [[ -z "$GROUP_NAME" ]] && die "Missing required --group for 'send-group'. Run 'ait crew command --help' for usage."
    [[ -z "$COMMAND" ]] && die "Missing required --command for 'send-group'. Run 'ait crew command --help' for usage."
    validate_command "$COMMAND"

    local count=0
    local status_file agent_name agent_group

    for status_file in "$WT_PATH"/*_status.yaml; do
        [[ -f "$status_file" ]] || continue
        [[ "$(basename "$status_file")" == "_crew_status.yaml" ]] && continue

        agent_group=$(read_yaml_field "$status_file" "group")
        if [[ "$agent_group" == "$GROUP_NAME" ]]; then
            agent_name=$(read_yaml_field "$status_file" "agent_name")
            [[ -z "$agent_name" ]] && continue
            AGENT_NAME="$agent_name"
            cmd_send
            count=$((count + 1))
        fi
    done

    if [[ $count -eq 0 ]]; then
        info "No agents found in group '$GROUP_NAME' in crew '$CREW_ID'"
    fi
}

# --- Sub-command: list ---
cmd_list() {
    [[ -z "$AGENT_NAME" ]] && die "Missing required --agent for 'list'. Run 'ait crew command --help' for usage."
    validate_agent_name "$AGENT_NAME"

    local cmd_file="$WT_PATH/${AGENT_NAME}_commands.yaml"
    if [[ ! -f "$cmd_file" ]]; then
        die "Agent '$AGENT_NAME' commands file not found in crew '$CREW_ID'"
    fi

    # Check if file has block-style command entries
    if { grep -q '^- command:' "$cmd_file" 2>/dev/null || false; }; then
        cat "$cmd_file"
    else
        echo "NO_COMMANDS"
    fi
}

# --- Sub-command: ack ---
cmd_ack() {
    [[ -z "$AGENT_NAME" ]] && die "Missing required --agent for 'ack'. Run 'ait crew command --help' for usage."
    validate_agent_name "$AGENT_NAME"

    local cmd_file="$WT_PATH/${AGENT_NAME}_commands.yaml"
    if [[ ! -f "$cmd_file" ]]; then
        die "Agent '$AGENT_NAME' commands file not found in crew '$CREW_ID'"
    fi

    write_yaml_file "$cmd_file" "pending_commands: []"
    echo "COMMANDS_ACKED:${AGENT_NAME}"
}

# --- Dispatch ---
case "$SUBCMD" in
    send)       cmd_send ;;
    send-all)   cmd_send_all ;;
    send-group) cmd_send_group ;;
    list)       cmd_list ;;
    ack)        cmd_ack ;;
esac
