#!/usr/bin/env bash
# aitask_brainstorm_init.sh - Initialize a brainstorm session for a task.
#
# Usage: ait brainstorm init <task_num>
#
# Creates an AgentCrew crew and initializes brainstorm session files
# (br_session.yaml, br_graph_state.yaml, br_groups.yaml, subdirectories).
#
# Output: INITIALIZED:<task_num>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

# --- Python setup ---
VENV_PYTHON="$HOME/.aitask/venv/bin/python"
if [[ -x "$VENV_PYTHON" ]]; then
    PYTHON="$VENV_PYTHON"
else
    PYTHON="${PYTHON:-python3}"
    if ! command -v "$PYTHON" &>/dev/null; then
        die "Python not found. Run 'ait setup' to install dependencies."
    fi
    if ! "$PYTHON" -c "import yaml" 2>/dev/null; then
        die "Missing Python package: pyyaml. Run 'ait setup' or: pip install pyyaml"
    fi
fi

# --- Usage ---
show_help() {
    cat <<'HELP'
Usage: ait brainstorm init <task_num>

Initialize a brainstorm session for the given task. Creates an AgentCrew
crew worktree and brainstorm session files.

Arguments:
  <task_num>    Task number (required)

Output:
  INITIALIZED:<task_num>    Session successfully initialized

Example:
  ait brainstorm init 42
HELP
}

# --- Argument parsing ---
TASK_NUM=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            show_help; exit 0 ;;
        -*)
            die "Unknown option: $1. Run 'ait brainstorm init --help' for usage." ;;
        *)
            if [[ -z "$TASK_NUM" ]]; then
                TASK_NUM="$1"; shift
            else
                die "Unexpected argument: $1. Run 'ait brainstorm init --help' for usage."
            fi
            ;;
    esac
done

[[ -z "$TASK_NUM" ]] && die "Missing required <task_num>. Run 'ait brainstorm init --help' for usage."

# --- Resolve task file ---
resolve_output=$("$SCRIPT_DIR/aitask_query_files.sh" resolve "$TASK_NUM")
first_line=$(echo "$resolve_output" | head -1)

if [[ "$first_line" == "NOT_FOUND" ]]; then
    die "Task t${TASK_NUM} not found."
fi

TASK_FILE="${first_line#TASK_FILE:}"

# --- Check session doesn't already exist ---
exists_output=$("$PYTHON" "$SCRIPT_DIR/brainstorm/brainstorm_cli.py" exists --task-num "$TASK_NUM")
if [[ "$exists_output" == "EXISTS" ]]; then
    die "Brainstorm session for task $TASK_NUM already exists."
fi

# --- Resolve brainstorm agent strings from config ---
_get_brainstorm_agent_string() {
    local agent_type="$1"
    local default_val="$2"
    local config_key="brainstorm-${agent_type}"
    local val
    val=$("$PYTHON" -c "
import json, sys
for p in ['aitasks/metadata/codeagent_config.local.json', 'aitasks/metadata/codeagent_config.json']:
    try:
        d = json.load(open(p))
        v = d.get('defaults', {}).get('$config_key')
        if v:
            print(v)
            sys.exit(0)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
print('$default_val')
" 2>/dev/null) || val="$default_val"
    echo "$val"
}

# --- Create AgentCrew crew ---
info "Creating brainstorm crew for task $TASK_NUM..."
crew_output=$(bash "$SCRIPT_DIR/aitask_crew_init.sh" \
    --id "brainstorm-${TASK_NUM}" \
    --name "Brainstorm t${TASK_NUM}" \
    --add-type "explorer:$(_get_brainstorm_agent_string explorer claudecode/opus4_6)" \
    --add-type "comparator:$(_get_brainstorm_agent_string comparator claudecode/sonnet4_6)" \
    --add-type "synthesizer:$(_get_brainstorm_agent_string synthesizer claudecode/opus4_6)" \
    --add-type "detailer:$(_get_brainstorm_agent_string detailer claudecode/opus4_6)" \
    --add-type "patcher:$(_get_brainstorm_agent_string patcher claudecode/sonnet4_6)" \
    --batch 2>&1) || {
    die "Failed to create crew: $crew_output"
}

# --- Get user email ---
USER_EMAIL=""
if [[ -f "aitasks/metadata/userconfig.yaml" ]]; then
    USER_EMAIL=$(grep '^email:' "aitasks/metadata/userconfig.yaml" 2>/dev/null | sed 's/^email:[[:space:]]*//' | head -n 1)
fi

# --- Write task spec to temp file ---
SPEC_FILE=$(mktemp "${TMPDIR:-/tmp}/brainstorm_spec_XXXXXX.md")
trap 'rm -f "$SPEC_FILE"' EXIT
cat "$TASK_FILE" > "$SPEC_FILE"

# --- Initialize brainstorm session ---
init_output=$("$PYTHON" "$SCRIPT_DIR/brainstorm/brainstorm_cli.py" init \
    --task-num "$TASK_NUM" \
    --task-file "$TASK_FILE" \
    --email "$USER_EMAIL" \
    --spec-file "$SPEC_FILE") || {
    die "Failed to initialize brainstorm session: $init_output"
}

success "Brainstorm session initialized for task $TASK_NUM"
echo "INITIALIZED:${TASK_NUM}"
