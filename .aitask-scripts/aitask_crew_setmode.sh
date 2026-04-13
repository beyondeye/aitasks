#!/usr/bin/env bash
# aitask_crew_setmode.sh - Change launch_mode for a Waiting agent in a crew.
#
# Usage: ait crew setmode --crew <id> --name <agent> --mode <headless|interactive>
#
# Refuses to mutate agents not in the Waiting state — launch_mode only
# influences pending launches. Used both from the command line and from the
# brainstorm TUI status-tab edit flow (sibling task t461_4 shells out to this
# script rather than re-implementing the yaml mutation).
#
# Output:
#   UPDATED:<agent>:<mode>   Successfully wrote new launch_mode

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/agentcrew_utils.sh
source "$SCRIPT_DIR/lib/agentcrew_utils.sh"

# --- Defaults ---
CREW_ID=""
AGENT_NAME=""
MODE=""

# --- Usage ---
show_help() {
    cat <<'HELP'
Usage: ait crew setmode --crew <id> --name <agent> --mode <headless|interactive>

Change the launch_mode of a Waiting agent in a crew. Refuses to mutate
agents in Running/Completed/Error/Aborted/Paused states (launch_mode only
applies to pending launches).

Required:
  --crew <id>       Crew identifier
  --name <agent>    Agent name
  --mode <mode>     New launch mode: 'headless' or 'interactive'

Options:
  --help            Show this help

Output:
  UPDATED:<agent>:<mode>

Example:
  ait crew setmode --crew sprint1 --name worker1 --mode interactive
HELP
}

# --- Argument parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --crew)
            [[ -z "${2:-}" ]] && die "--crew requires a value"
            CREW_ID="$2"; shift 2 ;;
        --name)
            [[ -z "${2:-}" ]] && die "--name requires a value"
            AGENT_NAME="$2"; shift 2 ;;
        --mode)
            [[ -z "${2:-}" ]] && die "--mode requires a value"
            MODE="$2"; shift 2 ;;
        --help|-h)
            show_help; exit 0 ;;
        *)
            die "Unknown option: $1. Run 'ait crew setmode --help' for usage." ;;
    esac
done

# --- Validation ---
[[ -z "$CREW_ID" ]] && die "Missing required --crew. Run 'ait crew setmode --help' for usage."
[[ -z "$AGENT_NAME" ]] && die "Missing required --name. Run 'ait crew setmode --help' for usage."
[[ -z "$MODE" ]] && die "Missing required --mode. Run 'ait crew setmode --help' for usage."

[[ "$MODE" =~ ^(headless|interactive)$ ]] || \
    die "--mode must be 'headless' or 'interactive' (got '$MODE')"

validate_crew_id "$CREW_ID"
validate_agent_name "$AGENT_NAME"

# --- Resolve crew worktree and locate status file ---
WT_PATH="$(resolve_crew "$CREW_ID")"
STATUS_FILE="$WT_PATH/${AGENT_NAME}_status.yaml"
if [[ ! -f "$STATUS_FILE" ]]; then
    die "Agent '$AGENT_NAME' not found in crew '$CREW_ID' (no $STATUS_FILE)"
fi

# --- Status gate: only Waiting agents are mutable ---
current_status="$(read_yaml_field "$STATUS_FILE" "status")"
if [[ "$current_status" != "$AGENT_STATUS_WAITING" ]]; then
    die "Agent '$AGENT_NAME' is in state '$current_status' — launch_mode only applies to pending launches"
fi

# --- Mutate launch_mode line in place (portable, no sed -i) ---
# launch_mode is always present in status files emitted by t461_1's
# aitask_crew_addwork.sh, but we still handle the missing-line case
# defensively in case an older agent file is encountered.
tmpfile="$(mktemp "${TMPDIR:-/tmp}/ait_setmode_XXXXXX.yaml")"
found=false
while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" == launch_mode:* ]]; then
        printf '%s\n' "launch_mode: ${MODE}"
        found=true
    else
        printf '%s\n' "$line"
    fi
done < "$STATUS_FILE" > "$tmpfile"

if ! $found; then
    printf '%s\n' "launch_mode: ${MODE}" >> "$tmpfile"
fi

mv "$tmpfile" "$STATUS_FILE"

# --- Commit inside the crew worktree (mirror addwork's commit block) ---
(
    cd "$WT_PATH"
    if ! git diff --quiet -- "${AGENT_NAME}_status.yaml" 2>/dev/null; then
        git add "${AGENT_NAME}_status.yaml"
        git commit -m "crew: Set launch_mode=${MODE} for agent '${AGENT_NAME}' in crew '${CREW_ID}'" --quiet
        git pull --rebase --quiet 2>/dev/null || true
        git push --quiet 2>/dev/null || warn "git push failed (offline?)"
    fi
)

# --- Structured success line for machine consumption (parsed by t461_4) ---
echo "UPDATED:${AGENT_NAME}:${MODE}"
